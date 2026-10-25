"""Asexual inheritance of selected brains, with independently mutated offspring."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from brain import (
    DEFAULT_MUTATION_RATE, DEFAULT_MUTATION_SCALE,
    NeuralNetwork, validate_mutation_parameters,
)

if TYPE_CHECKING:
    from creature import Creature


@dataclass(frozen=True)
class OffspringBrain:
    parent_id: int
    brain: NeuralNetwork
    mutations: int


def reproduce_brains(
    parents: Sequence[Creature], rng: np.random.Generator, *,
    offspring_count: int = 100,
    mutation_rate: float = DEFAULT_MUTATION_RATE,
    mutation_scale: float = DEFAULT_MUTATION_SCALE,
) -> list[OffspringBrain]:
    """Balance offspring across ranked parents, then shuffle their birth slots."""
    validate_mutation_parameters(mutation_rate, mutation_scale)
    if not parents:
        raise ValueError("Reproduction requires selected parents.")
    if not isinstance(offspring_count, int) or offspring_count < 1:
        raise ValueError("Offspring count must be a positive integer.")
    if len({parent.creature_id for parent in parents}) != len(parents):
        raise ValueError("Selected parent IDs must be unique.")
    if any(parent.brain is None for parent in parents):
        raise ValueError("Every selected parent must have a neural network.")

    slots = np.arange(offspring_count) % len(parents)
    rng.shuffle(slots)
    offspring = []
    for slot in slots:
        parent = parents[int(slot)]
        child = parent.brain.mutated_copy(
            rng, mutation_rate=mutation_rate, mutation_scale=mutation_scale,
        )
        changes = sum(
            int(np.count_nonzero(before != after))
            for before, after in zip(parent.brain.parameters, child.parameters)
        )
        offspring.append(OffspringBrain(parent.creature_id, child, changes))
    return offspring
