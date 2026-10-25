"""The 2D habitat. Coordinates are local to the arena, in pixels."""

import pygame


class World:
    """A rectangular arena, ready for creatures and food in later steps."""

    BACKGROUND = (17, 29, 35)
    GRID = (24, 39, 46)
    MAJOR_GRID = (31, 49, 56)
    BORDER = (64, 91, 100)

    def __init__(self, width: int = 1000, height: int = 600) -> None:
        self.width = width
        self.height = height
        self.grid_spacing = 40
        self.show_grid = True
        self.surface = pygame.Surface((width, height))

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

        pygame.draw.rect(self.surface, self.BORDER, self.surface.get_rect(), width=2)
        screen.blit(self.surface, origin)
