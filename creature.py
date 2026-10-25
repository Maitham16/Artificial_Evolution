"""Creature state, survival, movement, drawing, and population generation."""

from dataclasses import dataclass, field
import math
import random

import numpy as np
import pygame

from brain import MAX_TURN_RATE, NeuralNetwork
from food import Food
from selection import fitness_score


POPULATION_SIZE = 100
MAX_ENERGY = 100.0
BASE_ENERGY_COST = 2.0  # energy per simulated second
MOVEMENT_ENERGY_COST = 0.05  # energy per pixel travelled
COLORS = (
    (101, 219, 181),  # mint
    (105, 194, 237),  # blue
    (187, 155, 236),  # lilac
    (239, 167, 120),  # peach
    (232, 137, 168),  # rose
    (224, 205, 117),  # gold
)


@dataclass
class Creature:
    """A creature that moves along its heading and reflects off arena walls."""

    creature_id: int
    x: float
    y: float
    radius: int
    color: tuple[int, int, int]
    heading: float  # radians clockwise from the positive x axis
    speed: float  # pixels per second
    energy: float = 100.0
    turn_rate: float = 0.0  # radians per second
    turn_time_remaining: float = 0.0
    food_eaten: int = 0
    age: float = 0.0
    lifespan: float = 90.0
    death_cause: str | None = None
    max_speed: float = field(init=False)
    brain: NeuralNetwork | None = field(default=None, repr=False, compare=False)
    generation: int = 1
    parent_id: int | None = None
    mutation_count: int = 0

    def __post_init__(self) -> None:
        self.max_speed = abs(self.speed)

    def apply_controls(self, turn: float, throttle: float) -> None:
        """Apply a signed turn and a forward throttle fraction to living bodies."""
        if not self.alive:
            return
        if not math.isfinite(turn) or not math.isfinite(throttle):
            raise ValueError("Movement controls must be finite.")
        self.turn_rate = max(-1.0, min(1.0, turn)) * MAX_TURN_RATE
        self.speed = max(0.0, min(1.0, throttle)) * self.max_speed

    @property
    def alive(self) -> bool:
        return self.death_cause is None and self.energy > 0 and self.age < self.lifespan

    @property
    def fitness(self) -> float:
        """Current earned score; age and meal count stop changing after death."""
        return fitness_score(self.age, self.food_eaten)

    @property
    def hunger(self) -> float:
        """Energy deficit, from 0 (full) to 1 (empty)."""
        return max(0.0, min(1.0, 1.0 - self.energy / MAX_ENERGY))

    @property
    def hunger_state(self) -> str:
        if not self.alive:
            return "Dead"
        if self.hunger >= 0.8:
            return "Starving"
        if self.hunger >= 0.5:
            return "Hungry"
        return "Sated"

    @property
    def energy_cost_per_second(self) -> float:
        return BASE_ENERGY_COST + MOVEMENT_ENERGY_COST * abs(self.speed)

    def update_survival(self, dt: float) -> None:
        """Age and consume energy up to the first fatal limit in this interval."""
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Survival time must be finite and non-negative.")
        if self.death_cause is not None:
            return

        life_remaining = max(0.0, self.lifespan - self.age)
        energy_remaining = max(0.0, self.energy) / self.energy_cost_per_second
        lived = min(dt, life_remaining, energy_remaining)
        self.age = min(self.lifespan, self.age + lived)
        self.energy = max(0.0, self.energy - self.energy_cost_per_second * lived)
        if (
            life_remaining <= dt and life_remaining <= energy_remaining
        ) or self.age >= self.lifespan:
            self.death_cause = "old_age"
        elif energy_remaining <= dt or self.energy <= 0:
            self.energy = 0.0
            self.death_cause = "starvation"

    def eat(self, food: Food) -> bool:
        """Receive a meal after the world resolves ownership of a food collision."""
        if not self.alive or self.energy >= MAX_ENERGY:
            return False
        self.energy = min(MAX_ENERGY, self.energy + food.energy)
        self.food_eaten += 1
        return True

    def rotate(self, angle: float) -> None:
        """Rotate clockwise by an angle in radians, keeping a normalized heading."""
        if not self.alive:
            return
        self.heading = (self.heading + angle) % math.tau

    def move(self, dt: float, width: int, height: int) -> None:
        """Move for dt seconds, reflecting excess travel at radius-aware walls."""
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Movement time must be finite and non-negative.")
        if min(width, height) <= 2 * self.radius:
            raise ValueError("The arena must be wider and taller than the creature.")
        if dt == 0 or not self.alive:
            return

        dx = math.cos(self.heading) * self.speed * dt
        dy = math.sin(self.heading) * self.speed * dt
        self.x, reflected_x = _reflect_axis(
            self.x + dx, dx, self.radius, width - self.radius
        )
        self.y, reflected_y = _reflect_axis(
            self.y + dy, dy, self.radius, height - self.radius
        )
        if reflected_x:
            self.heading = math.pi - self.heading
        if reflected_y:
            self.heading = -self.heading
        self.heading %= math.tau

    def draw(self, surface: pygame.Surface, *, selected: bool = False) -> None:
        if not self.alive:
            return
        center = (round(self.x), round(self.y))
        halo = tuple(channel // 4 for channel in self.color)
        pygame.draw.circle(surface, halo, center, self.radius + 3)
        pygame.draw.circle(surface, self.color, center, self.radius)
        pygame.draw.circle(surface, (11, 24, 30), center, self.radius, width=1)

        # A small eye makes each creature's initial facing direction visible.
        eye = (
            round(self.x + math.cos(self.heading) * self.radius * 0.5),
            round(self.y + math.sin(self.heading) * self.radius * 0.5),
        )
        pygame.draw.circle(surface, (238, 247, 245), eye, 2)
        if selected:
            pygame.draw.circle(surface, (229, 241, 242), center, self.radius + 6, width=1)

        bar_color = (101, 219, 181)
        if self.hunger >= 0.8:
            bar_color = (238, 115, 127)
        elif self.hunger >= 0.5:
            bar_color = (235, 192, 105)
        bar = pygame.Rect(
            center[0] - self.radius, center[1] + self.radius + 4,
            2 * self.radius, 2,
        )
        pygame.draw.rect(surface, (40, 53, 59), bar)
        fill = bar.copy()
        fill.width = round(bar.width * (1.0 - self.hunger))
        if fill.width:
            pygame.draw.rect(surface, bar_color, fill)


def _reflect_axis(
    position: float, delta: float, lower: float, upper: float
) -> tuple[float, bool]:
    """Fold travel into an interval, including multiple bounces and exact hits."""
    span = upper - lower
    phase = (position - lower) % (2 * span)
    if phase == 0:
        return lower, delta < 0
    if phase == span:
        return upper, delta > 0
    if phase > span:
        return upper - (phase - span), True
    return lower + phase, False


def create_population(
    width: int, height: int, rng: random.Random, population_size: int = POPULATION_SIZE,
) -> list[Creature]:
    """Place the requested population inside the arena with space between bodies."""
    if type(population_size) is not int or population_size < 1:
        raise ValueError("Population size must be a positive integer.")
    if min(width, height) < 35:
        raise ValueError("The arena is too small for the creatures.")

    creatures = []
    for creature_id in range(1, population_size + 1):
        radius = rng.randint(6, 9)
        margin = radius + 8
        for _ in range(1000):
            x = rng.uniform(margin, width - margin)
            y = rng.uniform(margin, height - margin)
            if all(
                math.hypot(x - other.x, y - other.y) >= radius + other.radius + 8
                for other in creatures
            ):
                break
        else:
            raise ValueError(f"The arena is too crowded to place {population_size} creatures.")

        creatures.append(
            Creature(
                creature_id=creature_id,
                x=x,
                y=y,
                radius=radius,
                color=rng.choice(COLORS),
                heading=rng.uniform(0.0, math.tau),
                speed=rng.uniform(40.0, 80.0),
            )
        )
    # Assign lifespan after placement to preserve the existing seeded positions.
    for creature in creatures:
        creature.lifespan = rng.uniform(60.0, 120.0)
    # Brains are initialized after physical traits and use their own NumPy stream.
    brain_rng = np.random.default_rng(rng.getrandbits(128))
    for creature in creatures:
        creature.brain = NeuralNetwork(brain_rng)
    return creatures
