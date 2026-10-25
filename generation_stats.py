"""Completed-generation observations, separate from selection and reproduction."""

from dataclasses import dataclass


SURVIVAL_CHECKPOINT_SECONDS = 60.0


@dataclass(frozen=True)
class GenerationStats:
    generation: int
    population_size: int
    duration_seconds: float
    mean_fitness: float
    best_fitness: float
    mean_food_eaten: float
    mean_survival_seconds: float
    mean_speed: float
    food_visible_seconds: float
    food_facing_seconds: float
    survival_checkpoint_seconds: float = SURVIVAL_CHECKPOINT_SECONDS
    survivors_at_checkpoint: int | None = None

    @property
    def survival_rate(self) -> float | None:
        """Fraction of the original population that reached the checkpoint age."""
        if self.survivors_at_checkpoint is None or self.population_size == 0:
            return None
        return self.survivors_at_checkpoint / self.population_size

    @property
    def food_facing_fraction(self) -> float | None:
        """Share of visible-food creature-time with food within 45 degrees ahead."""
        if self.food_visible_seconds == 0:
            return None
        return self.food_facing_seconds / self.food_visible_seconds
