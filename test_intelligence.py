"""Truthful sensing, frozen model archives, repeated trials, and food-guidance tests."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from copy import deepcopy
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

from analyze_intelligence import (
    CONDITIONS, ENVIRONMENTS, analyze_results, bank_digest, effect, load_checkpoint,
    main, primary_decisions, run_study, save_checkpoint, steering_probe, train_lineage,
)
from brain import NeuralNetwork, food_inputs_for_control
from creature import create_population
from food import Food
from plot_intelligence import build_intelligence_figure, save_intelligence_plot
from world import SIMULATION_STEP, World


def short_population(*args):
    creatures = create_population(*args)
    for creature in creatures:
        creature.lifespan = 0.005
    return creatures


def directional_brain(sign=1):
    brain = NeuralNetwork(np.random.default_rng(42))
    for parameter in brain.parameters:
        parameter[:] = 0
    brain.input_weights[1, 0] = 2
    brain.output_weights[0, 0] = 2 * sign
    return brain


class FoodInterventionTests(unittest.TestCase):
    def test_only_food_inputs_change_and_truthful_array_stays_intact(self):
        truth = np.array([0.75, 0.25, 1, 0.6, 0.1, 0.2, 0.3, 0.4])
        before = truth.copy()
        mirror = food_inputs_for_control(truth, "mirrored")
        hidden = food_inputs_for_control(truth, "hidden")
        np.testing.assert_array_equal(mirror, [0.75, -0.25, 1, 0.6, 0.1, 0.2, 0.3, 0.4])
        np.testing.assert_array_equal(hidden, [0, 0, 0, 0.6, 0.1, 0.2, 0.3, 0.4])
        np.testing.assert_array_equal(truth, before)
        np.testing.assert_array_equal(food_inputs_for_control(truth, "intact"), truth)
        self.assertFalse(np.shares_memory(truth, mirror))
        self.assertFalse(np.shares_memory(truth, hidden))

    def test_mirroring_preserves_behind_boundary_and_is_reversible(self):
        for direction in (-1, -0.9, 0, 0.25, 0.9):
            truth = np.array([0.5, direction, 1, 0.5, 1, 1, 1, 1])
            mirrored = food_inputs_for_control(truth, "mirrored")
            self.assertTrue(-1 <= mirrored[1] < 1)
            np.testing.assert_allclose(food_inputs_for_control(mirrored, "mirrored"), truth)
        absent = np.array([0, 0, 0, 0.5, 1, 1, 1, 1])
        np.testing.assert_array_equal(food_inputs_for_control(absent, "mirrored"), absent)

    def test_bad_modes_shapes_and_nonfinite_inputs_are_rejected(self):
        for mode in ("guess", None):
            with self.assertRaises(ValueError):
                World(food_sensor_mode=mode)
            with self.assertRaises(ValueError):
                food_inputs_for_control(np.zeros(8), mode)
        for inputs in (np.zeros(7), np.full(8, math.nan)):
            with self.assertRaises(ValueError):
                food_inputs_for_control(inputs, "hidden")

    def test_world_controls_use_intervention_but_observations_use_real_food(self):
        for mode in ("intact", "mirrored", "hidden"):
            with self.subTest(mode=mode):
                world = World(seed=42, population_size=1, food_count=0, food_sensor_mode=mode)
                creature = world.creatures[0]
                creature.x = creature.y = 250
                creature.heading, creature.energy, creature.lifespan = 0, 50, 0.005
                world.food = [Food(300, 300)]
                truth = world.get_sensory_inputs(creature)
                observed = []
                creature.brain.forward = lambda sensors: observed.append(sensors.copy()) or np.zeros(2)
                world.update(SIMULATION_STEP)
                np.testing.assert_allclose(observed[0], food_inputs_for_control(truth, mode))
                stats = world.generation_stats[0]
                self.assertAlmostEqual(stats.food_visible_seconds, 0.005)
                self.assertAlmostEqual(stats.food_facing_seconds, 0.005)
                world.regenerate_population(42)
                self.assertEqual(world.food_sensor_mode, mode)

    def test_known_food_seeker_reaches_a_target_and_mirroring_breaks_pursuit(self):
        meals = []
        for mode in ("intact", "mirrored"):
            world = World(seed=42, population_size=1, food_count=0, food_sensor_mode=mode)
            creature = world.creatures[0]
            creature.x, creature.y, creature.heading = 500, 300, 0
            creature.energy, creature.max_speed, creature.lifespan = 50, 20, 120
            creature.brain = directional_brain()
            creature.brain.output_bias[1] = 2
            world.food = [Food(500, 380)]
            world.update(8.0)
            meals.append(creature.food_eaten)
        self.assertEqual(meals, [1, 0])


class SteeringProbeTests(unittest.TestCase):
    def test_known_positive_negative_and_indifferent_policies_are_distinguished(self):
        # These hand-wired brains validate the instrument; the real study trains random founders.
        for sign in (1, -1, 0):
            bank = {1: directional_brain(sign)}
            before = bank_digest(bank)
            result = steering_probe(bank)
            self.assertEqual(bank_digest(bank), before)
            self.assertEqual(result["pose_pairs_per_brain"], 12)
            gain = result["mean_steering_gain"]
            self.assertEqual(np.sign(gain), sign)
            self.assertEqual(result["mean_both_sides_correct_fraction"], 1 if sign == 1 else 0)

    def test_counterfactual_pairs_change_only_target_side(self):
        seen = []
        brain = directional_brain()
        def response(sensors):
            seen.append(sensors.copy())
            return np.array([sensors[1], 0])
        brain.forward = response
        result = steering_probe({1: brain})
        self.assertEqual(result["mean_steering_gain"], 0.375)
        self.assertEqual(len(seen), 24)
        for right, left in zip(seen[::2], seen[1::2]):
            self.assertEqual(right[1], -left[1])
            np.testing.assert_array_equal(np.delete(right, 1), np.delete(left, 1))

    def test_empty_probe_is_not_silently_reported_as_no_response(self):
        with self.assertRaises(ValueError):
            steering_probe({})


class RepeatedStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("world.create_population", side_effect=short_population):
            cls.base = run_study([11, 22], generations=2, repeats=2)

    def test_all_conditions_are_matched_frozen_and_unseen(self):
        report = self.base
        self.assertEqual(report["protocol"]["planned_training_cohorts"], 4)
        self.assertEqual(report["protocol"]["planned_test_cohorts"], 40)
        for trial in report["trials"]:
            self.assertEqual(len(trial["tests"]), 4)
            self.assertEqual(len({test["seed"] for test in trial["tests"]}), 4)
            for test in trial["tests"]:
                self.assertEqual(set(test["conditions"]), set(CONDITIONS))
                self.assertEqual(len({row["initial_conditions"] for row in test["conditions"].values()}), 1)
                for name, record in test["conditions"].items():
                    self.assertNotIn(record["initial_conditions"], trial["training_initial_conditions"])
                    self.assertFalse(record["report"]["evolution_enabled"])
                    self.assertEqual(record["report"]["arena_size"], list(ENVIRONMENTS[test["environment"]]))
                    if name != "random":
                        source = "founder" if name == "founder" else "evolved"
                        self.assertEqual(record["genomes_sha256"], trial["genome_hashes"][source])

    def test_repeats_are_averaged_without_inflating_independent_sample_count(self):
        report = deepcopy(self.base)
        for trial, outcomes in zip(report["trials"], ((2, 4), (6, 8))):
            standard = [test for test in trial["tests"] if test["environment"] == "standard"]
            for test, outcome in zip(standard, outcomes):
                test["conditions"]["intact"]["report"]["generations"][0]["mean_food_eaten"] = outcome
                test["conditions"]["mirrored"]["report"]["generations"][0]["mean_food_eaten"] = 0
        analysis = analyze_results(report)
        self.assertEqual(analysis["environments"]["standard"]["seed_values"]["intact"]["mean_food_eaten"], [3, 7])
        row = analysis["primary_tests"]["food_direction_standard"]
        self.assertEqual(row["n_pairs"], 2)
        self.assertEqual(row["mean_difference"], 5)
        self.assertEqual(row["difference_ci95"], [3, 7])

    def test_missing_or_duplicate_arenas_and_wrong_sensor_labels_are_rejected(self):
        missing = deepcopy(self.base)
        missing["trials"][0]["tests"].pop()
        with self.assertRaises(ValueError):
            analyze_results(missing)
        repeated = deepcopy(self.base)
        repeated["trials"][0]["tests"][1]["seed"] = repeated["trials"][0]["tests"][0]["seed"]
        with self.assertRaises(ValueError):
            analyze_results(repeated)
        mislabeled = deepcopy(self.base)
        mislabeled["trials"][0]["tests"][0]["conditions"]["intact"]["report"]["food_sensor_mode"] = "hidden"
        with self.assertRaises(ValueError):
            analyze_results(mislabeled)

    def test_altered_genomes_and_probe_summaries_cannot_pass_analysis(self):
        altered = deepcopy(self.base)
        altered["trials"][0]["tests"][0]["conditions"]["mirrored"]["genomes_sha256"] = "bad"
        with self.assertRaises(ValueError):
            analyze_results(altered)
        altered = deepcopy(self.base)
        altered["trials"][0]["probes"]["evolved"]["mean_steering_gain"] += 1
        with self.assertRaises(ValueError):
            analyze_results(altered)

    def test_serial_and_parallel_execution_produce_identical_results(self):
        with patch("world.create_population", side_effect=short_population), patch("analyze_intelligence.ProcessPoolExecutor", ThreadPoolExecutor):
            parallel = run_study([11, 22], generations=2, repeats=2, workers=2)
        self.assertEqual(parallel, self.base)

    def test_wrong_budgets_duplicate_seeds_and_reuse_without_models_fail_early(self):
        for changes in ({"seeds": [1]}, {"seeds": [1, 1]}, {"generations": 1},
                        {"repeats": 0}, {"workers": 0}, {"reuse": True}):
            args = dict(seeds=[11, 22], generations=2, repeats=1)
            args.update(changes)
            with self.subTest(changes=changes), patch("analyze_intelligence.run_lineage") as lineage:
                with self.assertRaises(ValueError):
                    run_study(**args)
                lineage.assert_not_called()

    def test_four_corrected_primary_tests_are_all_required(self):
        def results(delta=1):
            return {str(index): effect([delta] * 8, [0] * 8, str(index), primary=True) for index in range(4)}
        positive = results()
        self.assertTrue(primary_decisions(positive))
        self.assertTrue(all(row["holm_adjusted_p"] == 0.03125 for row in positive.values()))
        negative = results()
        negative["0"] = effect([-1] * 8, [0] * 8, "negative", primary=True)
        self.assertFalse(primary_decisions(negative))
        self.assertEqual(negative["0"]["conclusion"], "lower")
        incomplete = results()
        incomplete.pop("0")
        self.assertFalse(primary_decisions(incomplete))
        positive_interval_only = results()
        positive_interval_only["0"] = effect([10] * 7 + [-1], [0] * 8, "weak", primary=True)
        self.assertFalse(primary_decisions(positive_interval_only))
        self.assertGreater(positive_interval_only["0"]["difference_ci95"][0], 0)

    def test_plots_show_lineage_means_not_individual_repeat_points(self):
        figure = build_intelligence_figure(self.base)
        self.addCleanup(figure.clear)
        self.assertEqual(len(figure.axes), 6)
        self.assertEqual(len(figure.axes[0].collections[0].get_offsets()), 2)
        figure.canvas.draw()
        unfinished = deepcopy(self.base)
        unfinished["status"] = "running"
        with self.assertRaises(ValueError):
            build_intelligence_figure(unfinished)

    def test_png_svg_and_pdf_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            for extension, signature in (("png", b"\x89PNG"), ("svg", b"<?xml"), ("pdf", b"%PDF")):
                output = Path(directory) / f"analysis.{extension}"
                save_intelligence_plot(self.base, output)
                self.assertTrue(output.read_bytes().startswith(signature))


class FrozenArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("world.create_population", side_effect=short_population):
            cls.training, cls.initial, cls.banks = train_lineage(11, 2)

    def test_roundtrip_preserves_all_genomes_without_sharing_arrays(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "brains.npz"
            save_checkpoint(path, self.training, self.initial, self.banks)
            training, initial, banks = load_checkpoint(path, 11, 2)
            self.assertEqual(training, self.training)
            self.assertEqual(initial, self.initial)
            for name in ("evolved", "founder"):
                self.assertEqual(bank_digest(banks[name]), bank_digest(self.banks[name]))
                self.assertFalse(np.shares_memory(banks[name][1].input_weights, self.banks[name][1].input_weights))
            with self.assertRaises(ValueError):
                load_checkpoint(path, 12, 2)
            with self.assertRaises(ValueError):
                load_checkpoint(path, 11, 3)

    def test_bad_shapes_and_modified_arrays_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "brains.npz"
            save_checkpoint(path, self.training, self.initial, self.banks)
            with np.load(path, allow_pickle=False) as archive:
                arrays = {name: archive[name].copy() for name in archive.files}
            shape_error = dict(arrays)
            shape_error["evolved_0"] = arrays["evolved_0"][:1]
            np.savez_compressed(Path(directory) / "shape.npz", **shape_error)
            with self.assertRaises(ValueError):
                load_checkpoint(Path(directory) / "shape.npz", 11, 2)
            arrays["evolved_0"][0, 0, 0] += 0.5
            np.savez_compressed(Path(directory) / "changed.npz", **arrays)
            with self.assertRaisesRegex(ValueError, "hash"):
                load_checkpoint(Path(directory) / "changed.npz", 11, 2)

    def test_reused_models_reproduce_test_results_without_retraining(self):
        with tempfile.TemporaryDirectory() as directory, patch("world.create_population", side_effect=short_population):
            original = run_study([11, 22], generations=2, repeats=1, models_dir=directory)
            with patch("analyze_intelligence.train_lineage", side_effect=AssertionError("Unexpected retraining")):
                repeated = run_study([11, 22], generations=2, repeats=1, models_dir=directory, reuse=True)
            self.assertEqual(original["analysis"], repeated["analysis"])
            self.assertEqual(original["trials"], repeated["trials"])
            self.assertEqual(repeated["protocol"]["planned_training_cohorts"], 0)

    def test_cli_writes_complete_report_and_verified_model_archives(self):
        with tempfile.TemporaryDirectory() as directory, patch("world.create_population", side_effect=short_population):
            report, models = Path(directory) / "study.json", Path(directory) / "models"
            argv = ["analyze_intelligence.py", "--seeds", "11", "22", "--generations", "2",
                    "--repeats", "1", "--models-dir", str(models), "--output", str(report)]
            with patch("sys.argv", argv), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            self.assertEqual(json.loads(report.read_text())["status"], "complete")
            self.assertEqual(len(list(models.glob("*.npz"))), 2)


if __name__ == "__main__":
    unittest.main()
