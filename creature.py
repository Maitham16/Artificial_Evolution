"""Creature properties, movement, drawing, and initial population generation."""

from dataclasses import dataclass
import math
import random

import pygame

from food import Food


POPULATION_SIZE = 100
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

    def eat(self, food: Food) -> None:
        """Receive a meal after the world resolves ownership of a food collision."""
        self.energy += food.energy
        self.food_eaten += 1

    def rotate(self, angle: float) -> None:
        """Rotate clockwise by an angle in radians, keeping a normalized heading."""
        self.heading = (self.heading + angle) % math.tau

    def move(self, dt: float, width: int, height: int) -> None:
        """Move for dt seconds, reflecting excess travel at radius-aware walls."""
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Movement time must be finite and non-negative.")
        if min(width, height) <= 2 * self.radius:
            raise ValueError("The arena must be wider and taller than the creature.")
        if dt == 0:
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


def create_population(width: int, height: int, rng: random.Random) -> list[Creature]:
    """Place 100 creatures inside the arena, leaving space between their bodies."""
    if min(width, height) < 35:
        raise ValueError("The arena is too small for the creatures.")

    creatures = []
    for creature_id in range(1, POPULATION_SIZE + 1):
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
            raise ValueError("The arena is too crowded to place 100 creatures.")

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
    return creatures
