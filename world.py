"""The 2D habitat. Coordinates are local to the arena, in pixels."""

import math
import random

import numpy as np
import pygame

from brain import VISION_RANGE
from creature import MAX_ENERGY, Creature, create_population
from food import FOOD_COUNT, FOOD_RADIUS, Food


SIMULATION_STEP = 1.0 / 60.0


class World:
    """A rectangular arena where creatures move, feed, age, and survive."""

    BACKGROUND = (17, 29, 35)
    GRID = (24, 39, 46)
    MAJOR_GRID = (31, 49, 56)
    BORDER = (64, 91, 100)

    def __init__(
        self,
        width: int = 1000,
        height: int = 600,
        *,
        seed: int | None = None,
        food_count: int = FOOD_COUNT,
        controller: str = "neural",
    ) -> None:
        if food_count < 0:
            raise ValueError("Food count must be non-negative.")
        if controller not in ("neural", "random"):
            raise ValueError("Controller must be 'neural' or 'random'.")
        self.width = width
        self.height = height
        self.food_count = food_count
        self.controller = controller
        self.grid_spacing = 40
        self.show_grid = True
        self.paused = False
        self.surface = pygame.Surface((width, height))
        self.regenerate_population(seed)

    def regenerate_population(self, seed: int | None = None) -> None:
        """Reset creatures, food, counters, and time from a reproducible seed."""
        seed = seed if seed is not None else random.SystemRandom().randrange(2**32)
        creatures = create_population(self.width, self.height, random.Random(seed))
        self.seed = seed
        self.creatures = creatures
        self.dead_creatures: list[Creature] = []
        self.selected_creature: Creature | None = creatures[0]
        self._motion_rng = random.Random(f"motion:{seed}")
        self._food_rng = random.Random(f"food:{seed}")
        self.food: list[Food] = []
        self.total_food_eaten = 0
        for _ in range(self.food_count):
            self.food.append(self._spawn_food())
        self._accumulator = 0.0
        self.elapsed_time = 0.0

    def _spawn_food(self) -> Food:
        """Place a pellet in free space, clear of creatures and existing food."""
        margin = FOOD_RADIUS + 3
        for _ in range(1000):
            candidate = Food(
                self._food_rng.uniform(margin, self.width - margin),
                self._food_rng.uniform(margin, self.height - margin),
            )
            if any(
                candidate.overlaps_circle(creature.x, creature.y, creature.radius + 2)
                for creature in self.creatures
            ):
                continue
            if any(
                candidate.overlaps_circle(food.x, food.y, food.radius + 2)
                for food in self.food
            ):
                continue
            return candidate
        raise ValueError("The arena is too crowded to place food in free space.")

    def _resolve_food_collisions(self) -> None:
        """Award each touched pellet once, then replenish after all meals."""
        remaining = []
        for food in self.food:
            eater = min(
                (
                    creature for creature in self.creatures
                    if creature.alive and creature.energy < MAX_ENERGY
                    and food.overlaps_circle(creature.x, creature.y, creature.radius)
                ),
                key=lambda creature: (
                    (creature.x - food.x) ** 2 + (creature.y - food.y) ** 2,
                    creature.creature_id,
                ),
                default=None,
            )
            if eater is None:
                remaining.append(food)
            else:
                if eater.eat(food):
                    self.total_food_eaten += 1
                else:
                    remaining.append(food)

        self.food = remaining
        for _ in range(self.food_count - len(self.food)):
            self.food.append(self._spawn_food())

    def get_sensory_inputs(
        self, creature: Creature, food_positions: np.ndarray | None = None
    ) -> np.ndarray:
        """Sense local food and radius-aware wall clearance in the body's frame."""
        if food_positions is None:
            food_positions = np.array([(food.x, food.y) for food in self.food],
                                      dtype=np.float64).reshape(-1, 2)
        cosine, sine = math.cos(creature.heading), math.sin(creature.heading)
        forward, right, visible = 0.0, 0.0, 0.0
        if len(food_positions):
            offsets = food_positions - (creature.x, creature.y)
            distances_squared = np.sum(offsets * offsets, axis=1)
            nearest = int(np.argmin(distances_squared))
            if distances_squared[nearest] <= VISION_RANGE ** 2:
                dx, dy = offsets[nearest]
                forward = (cosine * dx + sine * dy) / VISION_RANGE
                right = (-sine * dx + cosine * dy) / VISION_RANGE
                visible = 1.0

        directions = ((cosine, sine), (-sine, cosine),
                      (-cosine, -sine), (sine, -cosine))
        walls = [self._wall_clearance(creature, dx, dy) for dx, dy in directions]
        return np.array([forward, right, visible, creature.hunger, *walls],
                        dtype=np.float64)

    def _wall_clearance(self, creature: Creature, dx: float, dy: float) -> float:
        """Return a normalized ray distance to the nearest center-position limit."""
        distances = [VISION_RANGE]
        if dx > 1e-12:
            distances.append((self.width - creature.radius - creature.x) / dx)
        elif dx < -1e-12:
            distances.append((creature.radius - creature.x) / dx)
        if dy > 1e-12:
            distances.append((self.height - creature.radius - creature.y) / dy)
        elif dy < -1e-12:
            distances.append((creature.radius - creature.y) / dy)
        return max(0.0, min(distances)) / VISION_RANGE

    def update(self, dt: float) -> None:
        """Advance survival, living creatures' motion, and eating in fixed steps."""
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Simulation time must be finite and non-negative.")
        if self.paused or dt == 0:
            return

        self._accumulator += dt
        while self._accumulator + 1e-12 >= SIMULATION_STEP:
            food_positions = np.array([(food.x, food.y) for food in self.food],
                                      dtype=np.float64).reshape(-1, 2)
            survivors = []
            for creature in self.creatures:
                uses_brain = self.controller == "neural" and creature.brain is not None
                if creature.alive:
                    if uses_brain:
                        sensors = self.get_sensory_inputs(creature, food_positions)
                        turn, throttle = creature.brain.forward(sensors)
                        creature.apply_controls(float(turn), (float(throttle) + 1.0) / 2.0)
                    elif creature.turn_time_remaining <= 0:
                        creature.turn_rate = self._motion_rng.uniform(
                            -math.pi / 2, math.pi / 2
                        )
                        creature.turn_time_remaining = self._motion_rng.uniform(0.75, 2.0)
                creature.update_survival(SIMULATION_STEP)
                if not creature.alive:
                    self.dead_creatures.append(creature)
                    continue
                survivors.append(creature)
                creature.rotate(creature.turn_rate * SIMULATION_STEP)
                creature.move(SIMULATION_STEP, self.width, self.height)
                if not uses_brain:
                    creature.turn_time_remaining -= SIMULATION_STEP
            self.creatures = survivors
            if self.selected_creature not in self.creatures:
                self.selected_creature = None
            self._resolve_food_collisions()
            self.elapsed_time += SIMULATION_STEP
            self._accumulator = max(0.0, self._accumulator - SIMULATION_STEP)

    def select_creature(self, position: tuple[int, int]) -> None:
        """Select the nearest creature under a click in arena coordinates."""
        x, y = position
        nearest = min(
            self.creatures,
            key=lambda creature: math.hypot(x - creature.x, y - creature.y),
            default=None,
        )
        if nearest is None:
            self.selected_creature = None
            return
        distance = math.hypot(x - nearest.x, y - nearest.y)
        self.selected_creature = nearest if distance <= nearest.radius + 6 else None

    def draw(self, screen: pygame.Surface, origin: tuple[int, int]) -> None:
        """Draw the arena at an offset without changing its coordinates."""
        self.surface.fill(self.BACKGROUND)

        if self.show_grid:
            for x in range(0, self.width, self.grid_spacing):
                color = self.MAJOR_GRID if x % 200 == 0 else self.GRID
                pygame.draw.line(self.surface, color, (x, 0), (x, self.height - 1))
            for y in range(0, self.height, self.grid_spacing):
                color = self.MAJOR_GRID if y % 200 == 0 else self.GRID
                pygame.draw.line(self.surface, color, (0, y), (self.width - 1, y))

        for food in self.food:
            food.draw(self.surface)

        for creature in self.creatures:
            if creature is not self.selected_creature:
                creature.draw(self.surface)
        if self.selected_creature is not None:
            self.selected_creature.draw(self.surface, selected=True)

        pygame.draw.rect(self.surface, self.BORDER, self.surface.get_rect(), width=2)
        screen.blit(self.surface, origin)
