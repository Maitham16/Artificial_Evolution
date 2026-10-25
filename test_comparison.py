"""Fair cohort construction, held-out evaluation, and analysis across independent runs."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict
import io
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

from compare_creatures import (
    CONDITIONS, analyze_trials, complete_generation, derived_seed, genome_digest,
    holm_adjust, initial_conditions_digest, main, paired_summary, run_experiment, run_trial,
)
from creature import create_population
from plot_comparison import build_comparison_figure, save_comparison_plot
from simulation import EvolutionSimulation
from world import World


def short_population(*args):
    creatures = create_population(*args)
    for creature in creatures:
        creature.lifespan = 0.005
    return creatures


def fake_trials(differences):
    trials = []
    for seed, delta in enumerate(differences, start=1):
        conditions = {}
        for condition in CONDITIONS:
            fitness = 100 + delta if condition == "evolved" else 100
            conditions[condition] = {"evaluation": {"completed_generations": 1, "generations": [{
                "mean_fitness": fitness, "survival_rate": fitness / 200,
                "mean_food_eaten": fitness / 10, "mean_survival_seconds": fitness / 2,
            }]}}
        trials.append({"seed": seed, "conditions": conditions})
    return trials


def fake_report(differences):
    trials = fake_trials(differences)
    return {"status": "complete", "protocol": {
        "training_seeds": [trial["seed"] for trial in trials], "training_generations": 10,
    }, "trials": trials, "comparisons": analyze_trials(trials)}


class CohortTests(unittest.TestCase):
    def setUp(self):
        self.spawning = patch("world.create_population", side_effect=short_population)
        self.spawning.start()
        self.addCleanup(self.spawning.stop)

    def test_without_evolution_newborn_brains_are_fresh_and_bodies_still_match(self):
        evolved = World(seed=42)
        control = World(seed=42, evolution_enabled=False)
        self.assertEqual([asdict(c) for c in evolved.creatures], [asdict(c) for c in control.creatures])
        for world in (evolved, control):
            complete_generation(EvolutionSimulation(world, auto_advance=False))
            self.assertTrue(world.advance_generation())
        self.assertEqual(initial_conditions_digest(evolved), initial_conditions_digest(control))
        self.assertTrue(all(c.parent_id is None and c.mutation_count == 0 for c in control.creatures))
        self.assertTrue(all(c.parent_id is not None for c in evolved.creatures))
        self.assertNotEqual(genome_digest(evolved.creatures), genome_digest(control.creatures))

    def test_trial_matches_all_initial_conditions_and_uses_frozen_brains_on_fresh_arena(self):
        trial = run_trial(101, 3)
        self.assertNotEqual(trial["evaluation_seed"], trial["seed"])
        self.assertEqual(trial["evaluation_seed"], derived_seed("step13:held-out:101"))
        arms = trial["conditions"]
        evolved = arms["evolved"]
        for condition, arm in arms.items():
            self.assertEqual(arm["training"]["completed_generations"], 3)
            self.assertEqual(arm["training"]["evolution_enabled"], condition == "evolved")
            self.assertEqual(arm["training_initial_conditions"], evolved["training_initial_conditions"])
            self.assertEqual(arm["evaluation_initial_conditions"], evolved["evaluation_initial_conditions"])
            self.assertNotIn(arm["evaluation_initial_conditions"], arm["training_initial_conditions"])
            self.assertEqual(arm["evaluation"]["completed_generations"], 1)
            self.assertEqual(arm["evaluation"]["generations"][0]["population_size"], 100)
            self.assertEqual(arm["evaluation"]["seed"], trial["evaluation_seed"])
            self.assertFalse(arm["evaluation"]["evolution_enabled"])
        self.assertEqual(evolved["training"]["generations"][0], arms["unselected"]["training"]["generations"][0])

    def test_trials_are_deterministic_but_independent_seeds_change_worlds(self):
        first = run_trial(101, 2)
        self.assertEqual(first, run_trial(101, 2))
        second = run_trial(202, 2)
        self.assertNotEqual(first["evaluation_seed"], second["evaluation_seed"])
        self.assertNotEqual(first["conditions"]["evolved"]["evaluation_initial_conditions"],
                            second["conditions"]["evolved"]["evaluation_initial_conditions"])

    def test_parallel_results_match_serial_and_follow_planned_seed_order(self):
        sequential = run_experiment([202, 101], generations=2)
        with patch("compare_creatures.ProcessPoolExecutor", ThreadPoolExecutor):
            parallel = run_experiment([202, 101], generations=2, workers=2)
        self.assertEqual(parallel, sequential)
        self.assertEqual([trial["seed"] for trial in parallel["trials"]], [202, 101])

    def test_checkpoints_do_not_claim_complete_or_analyze_partial_runs(self):
        snapshots = []
        run_experiment([101, 202], generations=2, checkpoint=lambda report: snapshots.append(deepcopy(report)))
        self.assertEqual([snapshot["status"] for snapshot in snapshots], ["running", "running", "running", "complete"])
        self.assertTrue(all("comparisons" not in snapshot for snapshot in snapshots[:-1]))
        self.assertEqual(len(snapshots[-1]["trials"]), 2)

    def test_invalid_experiments_fail_before_running_any_trial(self):
        for seeds, generations, workers in (([1], 2, 1), ([1, 1], 2, 1), ([1, 2], 1, 1),
                                            ([1, 2], 2, 0), ([1, "2"], 2, 1)):
            with self.subTest(seeds=seeds, generations=generations, workers=workers):
                with patch("compare_creatures.run_trial") as trial, self.assertRaises(ValueError):
                    run_experiment(seeds, generations=generations, workers=workers)
                trial.assert_not_called()

    def test_stalled_generation_raises_instead_of_hanging(self):
        world = World(seed=42)
        world.paused = True
        with self.assertRaises(RuntimeError):
            complete_generation(EvolutionSimulation(world))

    def test_cli_saves_complete_report_and_plot(self):
        with tempfile.TemporaryDirectory() as directory:
            report, plot = Path(directory) / "comparison.json", Path(directory) / "comparison.png"
            argv = ["compare_creatures.py", "--seeds", "101", "202", "--generations", "2",
                    "--output", str(report), "--plot", str(plot)]
            with patch("sys.argv", argv), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            self.assertEqual(json.loads(report.read_text())["status"], "complete")
            self.assertTrue(plot.is_file())


class PairedStatisticsTests(unittest.TestCase):
    def test_effect_is_mean_of_seed_pair_differences_and_resampling_is_seeded(self):
        result = paired_summary([20, 40, 60], [10, 35, 70])
        self.assertEqual(result["n_pairs"], 3)
        self.assertAlmostEqual(result["mean_difference"], 5 / 3)
        self.assertEqual((result["wins"], result["losses"], result["ties"]), (2, 1, 0))
        self.assertEqual(result, paired_summary([20, 40, 60], [10, 35, 70]))
        self.assertTrue(all(math.isfinite(value) for value in result["difference_ci95"]))

    def test_exact_sign_test_excludes_ties_and_handles_all_ties(self):
        result = paired_summary([1] * 8 + [0], [0] * 9)
        self.assertEqual(result["sign_test_p"], 2 / 2**8)
        self.assertEqual(result["ties"], 1)
        tied = paired_summary([1, 2, 3], [1, 2, 3])
        self.assertEqual(tied["sign_test_p"], 1)
        self.assertEqual(tied["difference_ci95"], [0, 0])

    def test_holm_adjustment_is_monotonic_in_sorted_p_values(self):
        np.testing.assert_allclose(holm_adjust([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])
        self.assertEqual(holm_adjust([1, 1]), [1, 1])

    def test_fitness_decision_uses_both_predeclared_tests_and_can_report_lower(self):
        for delta, expected in ((10, "higher"), (-10, "lower"), (0, "inconclusive")):
            with self.subTest(delta=delta):
                comparisons = analyze_trials(fake_trials([delta] * 8))
                for contrast in comparisons.values():
                    result = contrast["mean_fitness"]
                    self.assertEqual(result["conclusion"], expected)
                    if delta:
                        self.assertEqual(result["holm_adjusted_p"], 4 / 2**8)
        # A positive bootstrap interval alone is not a significant fitness result.
        result = analyze_trials(fake_trials([10] * 7 + [-1]))["evolved_vs_random"]["mean_fitness"]
        self.assertGreater(result["difference_ci95"][0], 0)
        self.assertEqual(result["conclusion"], "inconclusive")

    def test_insufficient_duplicate_or_nonfinite_pairs_are_rejected(self):
        for left, right in (([1], [0]), ([1, 2], [0]), ([1, math.nan], [1, 2])):
            with self.assertRaises(ValueError):
                paired_summary(left, right)
        duplicate = fake_trials([1, 2])
        duplicate[1]["seed"] = duplicate[0]["seed"]
        with self.assertRaises(ValueError):
            analyze_trials(duplicate)
        partial = fake_trials([1, 2])
        partial[0]["conditions"]["random"]["evaluation"]["completed_generations"] = 0
        with self.assertRaises(ValueError):
            analyze_trials(partial)


class ComparisonFigureTests(unittest.TestCase):
    def test_plot_shows_paired_outcomes_and_percentage_point_differences(self):
        report = fake_report([10] * 8)
        before = deepcopy(report)
        figure = build_comparison_figure(report)
        self.addCleanup(figure.clear)
        self.assertEqual(len(figure.axes), 6)
        self.assertEqual(figure.axes[1].get_ylim(), (0, 100))
        self.assertIn("percentage points", figure.axes[4].get_title())
        self.assertEqual(len(figure.axes[0].lines), 8)
        self.assertEqual(report, before)
        figure.canvas.draw()

    def test_incomplete_or_missing_planned_seeds_cannot_be_plotted(self):
        report = fake_report([10] * 8)
        report["status"] = "running"
        with self.assertRaises(ValueError):
            build_comparison_figure(report)
        report["status"] = "complete"
        report["trials"].pop()
        with self.assertRaises(ValueError):
            build_comparison_figure(report)

    def test_export_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            for extension, signature in (("png", b"\x89PNG"), ("svg", b"<?xml"), ("pdf", b"%PDF")):
                output = Path(directory) / f"comparison.{extension}"
                save_comparison_plot(fake_report([10] * 8), output)
                self.assertTrue(output.read_bytes().startswith(signature))


if __name__ == "__main__":
    unittest.main()
