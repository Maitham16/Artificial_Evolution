"""Fitness components, complete-population ranking, and final candidate selection."""

from dataclasses import FrozenInstanceError, asdict
import math
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from creature import Creature
from food import Food
from selection import evaluate_population, fitness_score
from world import SIMULATION_STEP, World


def make_creature(creature_id: int, **changes: float) -> Creature:
    properties = dict(
        creature_id=creature_id, x=50.0, y=50.0, radius=6,
        color=(101, 219, 181), heading=0.0, speed=0.0,
        turn_time_remaining=10.0,
    )
    properties.update(changes)
    return Creature(**properties)


class FitnessTests(unittest.TestCase):
    def test_score_rewards_both_actual_survival_and_meals(self) -> None:
        self.assertEqual(fitness_score(12.5, 3), 42.5)
        self.assertGreater(fitness_score(13.5, 3), fitness_score(12.5, 3))
        self.assertGreater(fitness_score(12.5, 4), fitness_score(12.5, 3))

    def test_creature_score_updates_from_age_and_food_without_accumulating_on_reads(self) -> None:
        creature = make_creature(1, energy=50.0)
        self.assertEqual(creature.fitness, 0.0)
        creature.eat(Food(50, 50))
        creature.update_survival(2.0)
        for _ in range(5):
            self.assertEqual(creature.fitness, 12.0)

    def test_remaining_energy_is_not_an_extra_fitness_bonus(self) -> None:
        full = make_creature(1, age=10.0, food_eaten=2, energy=100.0)
        hungry = make_creature(2, age=10.0, food_eaten=2, energy=20.0)
        self.assertEqual(full.fitness, hungry.fitness)

    def test_dead_creature_keeps_its_earned_score(self) -> None:
        creature = make_creature(1, energy=1.0, food_eaten=2)
        creature.update_survival(10.0)
        self.assertFalse(creature.alive)
        self.assertEqual(creature.fitness, 20.5)
        creature.update_survival(100.0)
        self.assertFalse(creature.eat(Food(50, 50)))
        self.assertEqual(creature.fitness, 20.5)

    def test_negative_and_nonfinite_components_are_rejected(self) -> None:
        for age, food in ((-1, 0), (0, -1), (math.nan, 0), (math.inf, 0), (0, math.inf)):
            with self.subTest(age=age, food=food), self.assertRaises(ValueError):
                fitness_score(age, food)


class PopulationEvaluationTests(unittest.TestCase):
    def test_ranking_includes_dead_creatures_and_live_scores_are_provisional(self) -> None:
        creatures = [
            make_creature(1, age=10.0, food_eaten=2),
            make_creature(2, age=25.0),
            make_creature(3, age=5.0, food_eaten=4, energy=0.0, death_cause="starvation"),
        ]
        evaluation = evaluate_population(creatures)
        self.assertEqual([entry.creature_id for entry in evaluation.ranking], [3, 1, 2])
        self.assertEqual([entry.fitness for entry in evaluation.ranking], [45.0, 30.0, 25.0])
        self.assertEqual(evaluation.best.creature_id, 3)
        self.assertAlmostEqual(evaluation.mean_fitness, 100.0 / 3)
        self.assertFalse(evaluation.complete)
        self.assertEqual(evaluation.selected_ids, ())

    def test_ties_use_id_and_evaluation_does_not_reorder_or_modify_creatures(self) -> None:
        creatures = [make_creature(3, age=10.0, food_eaten=1),
                     make_creature(1, age=20.0), make_creature(2, food_eaten=2)]
        before = [asdict(creature) for creature in creatures]
        evaluation = evaluate_population(creatures)
        self.assertEqual([entry.creature_id for entry in evaluation.ranking], [1, 2, 3])
        self.assertEqual([asdict(creature) for creature in creatures], before)

    def test_completed_population_selects_top_twenty_percent(self) -> None:
        creatures = [
            make_creature(index, age=10.0 + index / 10, food_eaten=index % 7,
                          death_cause="old_age")
            for index in range(1, 101)
        ]
        evaluation = evaluate_population(creatures)
        self.assertTrue(evaluation.complete)
        self.assertEqual(len(evaluation.ranking), 100)
        self.assertEqual(len(evaluation.selected_ids), 20)
        self.assertEqual(evaluation.selected_ids,
                         tuple(entry.creature_id for entry in evaluation.ranking[:20]))
        self.assertEqual(evaluation.selection_fraction, 0.2)

    def test_small_populations_round_candidate_count_up(self) -> None:
        creatures = [make_creature(index, death_cause="starvation") for index in range(1, 4)]
        self.assertEqual(evaluate_population(creatures).selected_ids, (1,))
        self.assertEqual(evaluate_population(creatures, selection_fraction=0.5).selected_ids, (1, 2))

    def test_empty_evaluation_has_no_candidates_or_division_by_zero(self) -> None:
        evaluation = evaluate_population([])
        self.assertEqual(evaluation.ranking, ())
        self.assertEqual(evaluation.selected_ids, ())
        self.assertEqual(evaluation.mean_fitness, 0.0)
        self.assertIsNone(evaluation.best)
        self.assertFalse(evaluation.complete)

    def test_entries_are_immutable_snapshots(self) -> None:
        creature = make_creature(1, age=5.0)
        evaluation = evaluate_population([creature])
        creature.age = 10.0
        self.assertEqual(evaluation.best.fitness, 5.0)
        self.assertEqual(evaluate_population([creature]).best.fitness, 10.0)
        with self.assertRaises(FrozenInstanceError):
            evaluation.best.fitness = 1000.0

    def test_duplicate_ids_and_invalid_selection_fractions_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_population([make_creature(1), make_creature(1)])
        for fraction in (0.0, -0.1, 1.1, math.inf, math.nan):
            with self.subTest(fraction=fraction), self.assertRaises(ValueError):
                evaluate_population([], selection_fraction=fraction)


class WorldSelectionTests(unittest.TestCase):
    def test_live_evaluation_keeps_dead_scores_and_waits_for_run_completion(self) -> None:
        world = World(seed=42, food_count=0)
        starving = make_creature(1, age=5.0, food_eaten=2, energy=0.01)
        living = make_creature(2, age=10.0, food_eaten=1)
        world.creatures = [starving, living]
        world.update(SIMULATION_STEP)
        evaluation = world.get_fitness_evaluation()
        self.assertEqual(len(evaluation.ranking), 2)
        self.assertEqual(evaluation.best.creature_id, 1)
        self.assertFalse(evaluation.complete)
        self.assertIsNone(world.final_evaluation)

    def test_final_selection_is_frozen_and_does_not_create_offspring(self) -> None:
        world = World(seed=42, food_count=0)
        world.creatures = [
            make_creature(index, age=5.0, lifespan=5.005, food_eaten=index % 3)
            for index in range(1, 21)
        ]
        world.update(SIMULATION_STEP)
        final = world.final_evaluation
        self.assertIsNotNone(final)
        self.assertTrue(final.complete)
        self.assertEqual(len(final.ranking), 20)
        self.assertEqual(len(final.selected_ids), 4)
        world.update(10.0)
        self.assertIs(world.get_fitness_evaluation(), final)
        self.assertEqual(world.creatures, [])
        self.assertEqual(len(world.dead_creatures), 20)

    def test_reset_clears_selection_and_starts_fresh_scores(self) -> None:
        world = World(seed=42, food_count=0)
        for creature in world.creatures:
            creature.energy = 0.0
        world.update(SIMULATION_STEP)
        self.assertEqual(len(world.final_evaluation.selected_ids), 20)
        world.show_fitness = True
        world.regenerate_population(42)
        self.assertIsNone(world.final_evaluation)
        self.assertTrue(world.show_fitness)
        evaluation = world.get_fitness_evaluation()
        self.assertEqual(len(evaluation.ranking), 100)
        self.assertEqual(evaluation.best.fitness, 0.0)
        self.assertEqual(evaluation.selected_ids, ())

    def test_reading_rankings_does_not_change_motion_food_or_brains(self) -> None:
        observed = World(seed=42)
        unobserved = World(seed=42)
        for _ in range(60):
            observed.update(SIMULATION_STEP)
            unobserved.update(SIMULATION_STEP)
            for _ in range(3):
                observed.get_fitness_evaluation()
        self.assertEqual([asdict(creature) for creature in observed.creatures],
                         [asdict(creature) for creature in unobserved.creatures])
        self.assertEqual(observed.food, unobserved.food)
        self.assertEqual(observed.total_food_eaten, unobserved.total_food_eaten)

    def test_final_rankings_match_at_different_frame_rates(self) -> None:
        evaluations = []
        for fps in (30, 60, 144):
            world = World(seed=42, food_count=0)
            for index, creature in enumerate(world.creatures):
                creature.lifespan = 0.5 + index / 300.0
                if index % 10 == 0:
                    creature.energy = 0.01
            for _ in range(fps):
                world.update(1.0 / fps)
            self.assertTrue(world.final_evaluation.complete)
            self.assertEqual(len(world.final_evaluation.selected_ids), 20)
            evaluations.append(world.final_evaluation)
        self.assertEqual(evaluations[0], evaluations[1])
        self.assertEqual(evaluations[0], evaluations[2])


if __name__ == "__main__":
    unittest.main()
