"""Local food perception: distance, relative bearing, and neural signals."""

from dataclasses import dataclass
import math

import numpy as np


VISION_RANGE = 160.0


@dataclass(frozen=True)
class FoodPerception:
    """A read-only observation of the nearest food within sensing range."""

    vision_range: float = VISION_RANGE
    target_position: tuple[float, float] | None = None
    distance: float | None = None
    direction: float | None = None  # radians relative to facing, [-pi, pi)
    nearby_count: int = 0

    @property
    def visible(self) -> bool:
        return self.target_position is not None

    @property
    def proximity(self) -> float:
        if self.distance is None:
            return 0.0
        return max(0.0, min(1.0, 1.0 - self.distance / self.vision_range))

    @property
    def neural_signals(self) -> tuple[float, float, float]:
        direction = 0.0 if self.direction is None else self.direction / math.pi
        return self.proximity, direction, float(self.visible)


def sense_food(
    x: float,
    y: float,
    heading: float,
    food_positions: np.ndarray,
    *,
    vision_range: float = VISION_RANGE,
) -> FoodPerception:
    """Sense food centers in a full circle; equal distances retain list order."""
    if not all(math.isfinite(value) for value in (x, y, heading, vision_range)):
        raise ValueError("The sensing pose and range must be finite.")
    if vision_range <= 0:
        raise ValueError("The sensing range must be positive.")
    positions = np.asarray(food_positions, dtype=np.float64)
    if positions.size == 0:
        return FoodPerception(vision_range=vision_range)
    if positions.ndim != 2 or positions.shape[1] != 2 or not np.all(np.isfinite(positions)):
        raise ValueError("Food positions must be finite (x, y) pairs.")

    offsets = positions - (x, y)
    distances = np.hypot(offsets[:, 0], offsets[:, 1])
    nearest = int(np.argmin(distances))
    distance = float(distances[nearest])
    if distance > vision_range:
        return FoodPerception(vision_range=vision_range)

    dx, dy = offsets[nearest]
    direction = 0.0 if distance == 0 else (
        (math.atan2(dy, dx) - heading + math.pi) % math.tau - math.pi
    )
    return FoodPerception(
        vision_range=vision_range,
        target_position=(float(positions[nearest, 0]), float(positions[nearest, 1])),
        distance=distance,
        direction=direction,
        nearby_count=int(np.count_nonzero(distances <= vision_range)),
    )
