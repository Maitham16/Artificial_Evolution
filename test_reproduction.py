"""Inheritance, independent mutations, and transitions between generations."""

from collections import Counter
from dataclasses import asdict
import math
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

from brain import NeuralNetwork
from creature import MAX_ENERGY
from reproduction import reproduce_brains
from world import SIMULATION_STEP, World


def finish_generation(world: World) -> None:
    """End a short controlled run with different earned meal scores."""
    for creature in world.creatures:
        creature.lifespan = 0.005
        creature.food_eaten = creature.creature_id % 7
    world.update(SIMULATION_STEP)


class BrainInheritanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parent = NeuralNetwork(np.random.default_rng(42))
        self.before = [parameter.copy() for parameter in self.parent.parameters]

    def assert_parent_unchanged(self) -> None:
        for before, after in zip(self.before, self.parent.parameters):
            np.testing.assert_array_equal(before, after)

    def test_copy_inherits_all_weights_and_biases_without_shared_memory(self) -> None:
        child = self.parent.copy()
        self.assertEqual(child.parameter_count, 90)
        for parent_array, child_array in zip(self.parent.parameters, child.parameters):
            np.testing.assert_array_equal(parent_array, child_array)
            self.assertFalse(np.shares_memory(parent_array, child_array))
            child_array.flat[0] += 1
        self.assert_parent_unchanged()

    def test_zero_rate_or_scale_makes_independent_exact_clones(self) -> None:
        for rate, scale in ((0.0, 0.1), (1.0, 0.0)):
            with self.subTest(rate=rate, scale=scale):
                child = self.parent.mutated_copy(
                    np.random.default_rng(9), mutation_rate=rate, mutation_scale=scale,
                )
                self.assertEqual(child, self.parent)
                for source, clone in zip(self.parent.parameters, child.parameters):
                    self.assertFalse(np.shares_memory(source, clone))
        self.assert_parent_unchanged()

    def test_full_rate_changes_every_parameter_including_biases(self) -> None:
        child = self.parent.mutated_copy(np.random.default_rng(8), mutation_rate=1.0)
        for source, mutated in zip(self.parent.parameters, child.parameters):
            self.assertTrue(np.all(source != mutated))
            self.assertTrue(np.all(np.isfinite(mutated)))
        self.assert_parent_unchanged()

    def test_default_mutations_are_partial_and_reproducible(self) -> None:
        first = self.parent.mutated_copy(np.random.default_rng(19))
        same = self.parent.mutated_copy(np.random.default_rng(19))
        different = self.parent.mutated_copy(np.random.default_rng(20))
        self.assertEqual(first, same)
        self.assertNotEqual(first, different)
        changed = sum(np.count_nonzero(a != b) for a, b in zip(self.parent.parameters, first.parameters))
        self.assertGreater(changed, 0)
        self.assertLess(changed, self.parent.parameter_count)
        first.input_weights[0, 0] += 10
        self.assertNotEqual(first, same)
        self.assert_parent_unchanged()

    def test_invalid_mutation_settings_are_rejected(self) -> None:
        for rate, scale in ((-0.1, 0.1), (1.1, 0.1), (math.nan, 0.1),
                            (math.inf, 0.1), (0.1, -0.1), (0.1, math.nan), (0.1, math.inf)):
            with self.subTest(rate=rate, scale=scale), self.assertRaises(ValueError):
                self.parent.mutated_copy(
                    np.random.default_rng(1), mutation_rate=rate, mutation_scale=scale,
                )
        self.assert_parent_unchanged()

    def test_nonfinite_parent_is_rejected_even_without_mutation(self) -> None:
        self.parent.hidden_bias[0] = math.nan
        with self.assertRaises(ValueError):
            self.parent.mutated_copy(np.random.default_rng(1), mutation_rate=0)


class BreedingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parents = World(seed=42, food_count=0).creatures[:20]

    def test_twenty_parents_produce_five_independent_offspring_each(self) -> None:
        offspring = reproduce_brains(self.parents, np.random.default_rng(5), mutation_rate=0)
        self.assertEqual(len(offspring), 100)
        self.assertEqual(Counter(child.parent_id for child in offspring),
                         Counter({parent.creature_id: 5 for parent in self.parents}))
        by_id = {parent.creature_id: parent for parent in self.parents}
        for child in offspring:
            self.assertEqual(child.brain, by_id[child.parent_id].brain)
            self.assertEqual(child.mutations, 0)
        siblings = [child.brain for child in offspring if child.parent_id == self.parents[0].creature_id]
        siblings[0].output_bias[0] += 1
        for sibling in siblings[1:]:
            self.assertEqual(sibling, self.parents[0].brain)
        self.assertNotEqual(siblings[0], self.parents[0].brain)

    def test_mutation_counts_match_actual_changes_and_only_selected_brains_are_used(self) -> None:
        snapshots = [parent.brain.copy() for parent in self.parents]
        offspring = reproduce_brains(self.parents, np.random.default_rng(7))
        parents = {parent.creature_id: parent for parent in self.parents}
        changes = []
        for child in offspring:
            self.assertIn(child.parent_id, parents)
            parent = parents[child.parent_id]
            count = sum(int(np.count_nonzero(a != b))
                        for a, b in zip(parent.brain.parameters, child.brain.parameters))
            self.assertEqual(child.mutations, count)
            changes.append(count)
            for source, inherited in zip(parent.brain.parameters, child.brain.parameters):
                self.assertFalse(np.shares_memory(source, inherited))
        self.assertGreater(sum(changes), 0)
        self.assertEqual([parent.brain for parent in self.parents], snapshots)

    def test_seed_controls_parent_assignment_and_mutations(self) -> None:
        first = reproduce_brains(self.parents, np.random.default_rng(8))
        same = reproduce_brains(self.parents, np.random.default_rng(8))
        different = reproduce_brains(self.parents, np.random.default_rng(9))
        self.assertEqual(first, same)
        self.assertNotEqual(first, different)
        self.assertNotEqual([child.parent_id for child in first],
                            sorted(child.parent_id for child in first))

    def test_non_divisible_offspring_count_stays_balanced(self) -> None:
        offspring = reproduce_brains(self.parents[:3], np.random.default_rng(1), offspring_count=8)
        self.assertEqual(Counter(child.parent_id for child in offspring), {1: 3, 2: 3, 3: 2})

    def test_invalid_parent_pools_and_counts_are_rejected(self) -> None:
        for parents in ([], [self.parents[0], self.parents[0]]):
            with self.assertRaises(ValueError):
                reproduce_brains(parents, np.random.default_rng(1))
        for count in (0, -1, 1.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                reproduce_brains(self.parents, np.random.default_rng(1), offspring_count=count)
        self.parents[0].brain = None
        with self.assertRaises(ValueError):
            reproduce_brains(self.parents, np.random.default_rng(1))


class GenerationTests(unittest.TestCase):
    def test_active_generation_cannot_be_bred_or_change_seeded_run(self) -> None:
        attempted = World(seed=42)
        untouched = World(seed=42)
        self.assertFalse(attempted.advance_generation())
        attempted.update(SIMULATION_STEP)
        untouched.update(SIMULATION_STEP)
        self.assertFalse(attempted.advance_generation())
        self.assertEqual(attempted.generation, 1)
        self.assertEqual([asdict(c) for c in attempted.creatures],
                         [asdict(c) for c in untouched.creatures])
        self.assertEqual(attempted.food, untouched.food)

    def test_completed_generation_breeds_only_selected_parents_and_resets_survival(self) -> None:
        world = World(seed=42)
        finish_generation(world)
        final = world.final_evaluation
        old = {c.creature_id: c for c in world.dead_creatures}
        snapshots = {key: asdict(c) for key, c in old.items()}
        world.total_food_eaten = 123
        self.assertTrue(world.advance_generation())
        self.assertEqual((world.generation, world.seed), (2, 42))
        self.assertEqual(len(world.creatures), 100)
        self.assertEqual(world.dead_creatures, [])
        self.assertIsNone(world.final_evaluation)
        self.assertEqual(world.generation_history, [final])
        self.assertEqual(world.elapsed_time, 0)
        self.assertEqual(world.total_food_eaten, 0)
        self.assertEqual(len(world.food), 150)
        self.assertEqual(Counter(c.parent_id for c in world.creatures),
                         Counter({parent_id: 5 for parent_id in final.selected_ids}))
        for child in world.creatures:
            self.assertEqual(child.generation, 2)
            self.assertEqual((child.age, child.energy, child.food_eaten, child.fitness),
                             (0, MAX_ENERGY, 0, 0))
            self.assertTrue(child.alive)
            self.assertIsNone(child.death_cause)
            self.assertGreaterEqual(child.lifespan, 60)
            self.assertLessEqual(child.lifespan, 120)
            self.assertGreaterEqual(child.x, child.radius)
            self.assertLessEqual(child.x, world.width - child.radius)
            self.assertGreaterEqual(child.y, child.radius)
            self.assertLessEqual(child.y, world.height - child.radius)
            parent = old[child.parent_id]
            changed = sum(int(np.count_nonzero(a != b))
                          for a, b in zip(parent.brain.parameters, child.brain.parameters))
            self.assertEqual(child.mutation_count, changed)
            for source, inherited in zip(parent.brain.parameters, child.brain.parameters):
                self.assertFalse(np.shares_memory(source, inherited))
        self.assertEqual({key: asdict(c) for key, c in old.items()}, snapshots)
        self.assertTrue(any((c.x, c.y, c.lifespan) != (old[c.creature_id].x, old[c.creature_id].y,
                                                    old[c.creature_id].lifespan)
                            for c in world.creatures))
        for index, child in enumerate(world.creatures):
            for other in world.creatures[index + 1:]:
                self.assertGreater(math.hypot(child.x - other.x, child.y - other.y),
                                   child.radius + other.radius)
            self.assertFalse(any(food.overlaps_circle(child.x, child.y, child.radius)
                                 for food in world.food))

    def test_zero_mutation_generation_inherits_exact_selected_genomes(self) -> None:
        world = World(seed=42, food_count=0, mutation_rate=0)
        finish_generation(world)
        old = {c.creature_id: c.brain.copy() for c in world.dead_creatures}
        self.assertTrue(world.advance_generation())
        for child in world.creatures:
            self.assertEqual(child.brain, old[child.parent_id])
            self.assertEqual(child.mutation_count, 0)

    def test_reproduction_is_seeded_and_independent_of_wait_after_extinction(self) -> None:
        for seed in (42, -42):
            with self.subTest(seed=seed):
                first, second = World(seed=seed), World(seed=seed)
                finish_generation(first)
                finish_generation(second)
                second.update(2.0)
                self.assertTrue(first.advance_generation())
                self.assertTrue(second.advance_generation())
                self.assertEqual([asdict(c) for c in first.creatures],
                                 [asdict(c) for c in second.creatures])
                self.assertEqual(first.food, second.food)
                first.update(SIMULATION_STEP)
                second.update(SIMULATION_STEP)
                self.assertEqual([asdict(c) for c in first.creatures],
                                 [asdict(c) for c in second.creatures])

    def test_history_records_once_per_generation_and_survives_repeated_breeding(self) -> None:
        world = World(seed=42, food_count=0)
        finish_generation(world)
        first = world.final_evaluation
        world.update(0.1)
        self.assertEqual(world.generation_history, [first])
        self.assertTrue(world.advance_generation())
        self.assertFalse(world.advance_generation())
        finish_generation(world)
        second = world.final_evaluation
        self.assertEqual(world.generation_history, [first, second])
        self.assertTrue(world.advance_generation())
        self.assertEqual(world.generation, 3)
        self.assertEqual(world.generation_history, [first, second])
        self.assertTrue(all(c.generation == 3 for c in world.creatures))

    def test_reset_restores_founders_and_clears_history_and_lineage(self) -> None:
        world = World(seed=42)
        initial = [asdict(c) for c in world.creatures]
        initial_food = world.food.copy()
        finish_generation(world)
        world.advance_generation()
        world.regenerate_population(42)
        self.assertEqual(world.generation, 1)
        self.assertEqual(world.generation_history, [])
        self.assertEqual([asdict(c) for c in world.creatures], initial)
        self.assertEqual(world.food, initial_food)
        self.assertTrue(all(c.parent_id is None and c.mutation_count == 0 for c in world.creatures))

    def test_controls_and_random_baseline_survive_next_generation(self) -> None:
        world = World(seed=42, food_count=0, controller="random")
        finish_generation(world)
        world.paused, world.show_grid = True, False
        world.show_perception, world.show_fitness = False, True
        self.assertTrue(world.advance_generation())
        self.assertTrue(world.paused)
        self.assertFalse(world.show_grid)
        self.assertFalse(world.show_perception)
        self.assertTrue(world.show_fitness)
        self.assertEqual(world.controller, "random")
        world.update(SIMULATION_STEP)
        self.assertEqual(world.elapsed_time, 0)
        world.paused = False
        for creature in world.creatures:
            creature.brain.forward = lambda _: self.fail("Random mode used a neural decision")
        world.update(SIMULATION_STEP)
        self.assertTrue(all(c.age > 0 for c in world.creatures))

    def test_invalid_world_mutation_settings_are_rejected(self) -> None:
        for kwargs in ({"mutation_rate": 1.1}, {"mutation_scale": -0.1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                World(seed=42, **kwargs)


if __name__ == "__main__":
    unittest.main()
