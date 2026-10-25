"""The 2D habitat. Coordinates are local to the arena, in pixels."""

import math
import random

import pygame

from creature import Creature, create_population
from food import FOOD_COUNT, FOOD_RADIUS, Food


SIMULATION_STEP = 1.0 / 60.0


class World:
    """A rectangular arena with 100 creatures and replenishing food."""

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
    ) -> None:
        if food_count < 0:
            raise ValueError("Food count must be non-negative.")
        self.width = width
        self.height = height
        self.food_count = food_count
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
                    if food.overlaps_circle(creature.x, creature.y, creature.radius)
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
                eater.eat(food)
                self.total_food_eaten += 1

        self.food = remaining
        for _ in range(self.food_count - len(self.food)):
            self.food.append(self._spawn_food())

    def update(self, dt: float) -> None:
        """Advance motion and food contact in fixed time steps."""
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Simulation time must be finite and non-negative.")
        if self.paused or dt == 0:
            return

        self._accumulator += dt
        while self._accumulator + 1e-12 >= SIMULATION_STEP:
            for creature in self.creatures:
                if creature.turn_time_remaining <= 0:
                    creature.turn_rate = self._motion_rng.uniform(
                        -math.pi / 2, math.pi / 2
                    )
                    creature.turn_time_remaining = self._motion_rng.uniform(0.75, 2.0)
                creature.rotate(creature.turn_rate * SIMULATION_STEP)
                creature.move(SIMULATION_STEP, self.width, self.height)
                creature.turn_time_remaining -= SIMULATION_STEP
            self._resolve_food_collisions()
            self.elapsed_time += SIMULATION_STEP
            self._accumulator = max(0.0, self._accumulator - SIMULATION_STEP)

    def select_creature(self, position: tuple[int, int]) -> None:
        """Select the nearest creature under a click in arena coordinates."""
        x, y = position
        nearest = min(
            self.creatures, key=lambda creature: math.hypot(x - creature.x, y - creature.y)
        )
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
