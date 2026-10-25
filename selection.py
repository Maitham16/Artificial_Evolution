"""Fitness evaluation and selection of candidates after a completed run."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from creature import Creature


SURVIVAL_REWARD = 1.0
FOOD_REWARD = 10.0
SELECTION_FRACTION = 0.2


def fitness_score(survival_seconds: float, food_eaten: int) -> float:
    """Reward actual simulated time alive and meals consumed."""
    if not math.isfinite(survival_seconds) or survival_seconds < 0:
        raise ValueError("Survival time must be finite and non-negative.")
    if not math.isfinite(food_eaten) or food_eaten < 0:
        raise ValueError("Food consumed must be finite and non-negative.")
    score = SURVIVAL_REWARD * survival_seconds + FOOD_REWARD * food_eaten
    if not math.isfinite(score):
        raise ValueError("Fitness must be finite.")
    return score


@dataclass(frozen=True)
class FitnessEntry:
    creature_id: int
    survival_seconds: float
    food_eaten: int
    fitness: float
    alive: bool


@dataclass(frozen=True)
class FitnessEvaluation:
    """A read-only ranking; parent IDs are populated only after extinction."""

    ranking: tuple[FitnessEntry, ...]
    selected_ids: tuple[int, ...]
    complete: bool
    selection_fraction: float

    @property
    def best(self) -> FitnessEntry | None:
        return self.ranking[0] if self.ranking else None

    @property
    def mean_fitness(self) -> float:
        if not self.ranking:
            return 0.0
        return sum(entry.fitness for entry in self.ranking) / len(self.ranking)


def evaluate_population(
    creatures: Iterable[Creature], *, selection_fraction: float = SELECTION_FRACTION
) -> FitnessEvaluation:
    """Rank everyone by fitness, breaking exact ties by lower creature ID."""
    if not math.isfinite(selection_fraction) or not 0 < selection_fraction <= 1:
        raise ValueError("Selection fraction must be greater than 0 and at most 1.")
    entries = [
        FitnessEntry(creature.creature_id, creature.age, creature.food_eaten,
                     creature.fitness, creature.alive)
        for creature in creatures
    ]
    if len({entry.creature_id for entry in entries}) != len(entries):
        raise ValueError("A creature may appear only once in a fitness evaluation.")
    ranking = tuple(sorted(entries, key=lambda entry: (-entry.fitness, entry.creature_id)))
    complete = bool(ranking) and not any(entry.alive for entry in ranking)
    count = math.ceil(len(ranking) * selection_fraction) if complete else 0
    selected_ids = tuple(entry.creature_id for entry in ranking[:count])
    return FitnessEvaluation(ranking, selected_ids, complete, selection_fraction)
