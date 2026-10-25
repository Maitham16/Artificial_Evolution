"""The 2D habitat. Coordinates are local to the arena, in pixels."""

import math
import random

import pygame

from creature import Creature, create_population


class World:
    """A rectangular arena with an initial population of 100 creatures."""

    BACKGROUND = (17, 29, 35)
    GRID = (24, 39, 46)
    MAJOR_GRID = (31, 49, 56)
    BORDER = (64, 91, 100)

    def __init__(
        self, width: int = 1000, height: int = 600, *, seed: int | None = None
    ) -> None:
        self.width = width
        self.height = height
        self.grid_spacing = 40
        self.show_grid = True
        self.surface = pygame.Surface((width, height))
        self.regenerate_population(seed)

    def regenerate_population(self, seed: int | None = None) -> None:
        """Generate a fresh population and retain its seed for reproducibility."""
        seed = seed if seed is not None else random.SystemRandom().randrange(2**32)
        creatures = create_population(self.width, self.height, random.Random(seed))
        self.seed = seed
        self.creatures = creatures
        self.selected_creature: Creature | None = creatures[0]

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

        for creature in self.creatures:
            if creature is not self.selected_creature:
                creature.draw(self.surface)
        if self.selected_creature is not None:
            self.selected_creature.draw(self.surface, selected=True)

        pygame.draw.rect(self.surface, self.BORDER, self.surface.get_rect(), width=2)
        screen.blit(self.surface, origin)
