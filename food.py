"""Food pellets, circle collision checks, and drawing."""

from dataclasses import dataclass

import pygame


FOOD_COUNT = 150
FOOD_RADIUS = 3


@dataclass(frozen=True)
class Food:
    """One stationary meal, removed from the world when consumed."""

    x: float
    y: float
    radius: int = FOOD_RADIUS
    energy: float = 20.0

    def overlaps_circle(self, x: float, y: float, radius: float) -> bool:
        """Include edge contact using the radii of both circles."""
        dx, dy = self.x - x, self.y - y
        return dx * dx + dy * dy <= (self.radius + radius) ** 2

    def draw(self, surface: pygame.Surface) -> None:
        x, y = round(self.x), round(self.y)
        pygame.draw.circle(surface, (35, 55, 27), (x, y), self.radius + 2)
        pygame.draw.polygon(
            surface,
            (166, 220, 100),
            [(x, y - self.radius), (x + self.radius, y),
             (x, y + self.radius), (x - self.radius, y)],
        )
        pygame.draw.circle(surface, (223, 244, 179), (x, y), 1)
