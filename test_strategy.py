"""Saved-brain attribution with matched ancestral controls and sensor interventions."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from analyze_intelligence import bank_digest, save_checkpoint
from brain import NeuralNetwork
from compare_creatures import initial_conditions_digest
from creature import create_population
from experiment_speed import train_lineage, classify_primary
from experiment_strategy import (CONDITIONS, ENVIRONMENTS, METRICS, analyze_results, file_digest,
    load_unselected, main, movement_probe, prepare_lineage, primary_effects, run_study)
from plot_strategy import build_strategy_figure, save_strategy_plot
from world import SIMULATION_STEP, World


def short_population(*args):
    creatures = create_population(*args)
    for creature in creatures:
        creature.lifespan = 0.005
    return creatures


def make_sources(directory):
    directory = Path(directory)
    models = directory / "models"
    trials = []
    for seed in (11, 22):
        training, starts, bank = train_lineage(seed, 2)
        save_checkpoint(models / f"seed-{seed}.npz", training, starts, {"evolved": bank})
        trials.append({"seed": seed, "training_initial_conditions": starts,
                       "genomes_sha256": bank_digest(bank), "tests": []})
    prior = directory / "source.json"
    prior.write_text(json.dumps({"status": "complete", "trials": trials}))
    return {"models_dir": models, "prior_report": prior, "generations": 2}


class ProbeTests(unittest.TestCase):
    def test_straight_and_circular_open_space_policies_have_expected_displacement(self):
        brain = NeuralNetwork(np.random.default_rng(42))
        for p in brain.parameters:
            p[:] = 0
        straight = movement_probe({1: brain})
        self.assertEqual(straight["mean_abs_turn"], 0)
        self.assertEqual(straight["mean_straightness_12s"], 1)
        brain.output_bias[0] = np.arctanh(1 / 3)
        circular = movement_probe({1: brain})
        self.assertAlmostEqual(circular["mean_abs_turn"], 1 / 3)
        self.assertAlmostEqual(circular["mean_straightness_12s"], 0)

    def test_movement_probe_clamps_hunger_and_changes_no_weights(self):
        brain = NeuralNetwork(np.random.default_rng(42))
        before = bank_digest({1: brain})
        seen = []
        original = brain.forward
        brain.forward = lambda s: seen.append(s.copy()) or original(s)
        movement_probe({1: brain})
        self.assertEqual(bank_digest({1: brain}), before)
        self.assertEqual(len(seen), 2)
        np.testing.assert_array_equal(seen[0], [0, 0, 0, 0.25, 1, 1, 1, 1])
        np.testing.assert_array_equal(seen[1], [0, 0, 0, 0.75, 1, 1, 1, 1])
        with self.assertRaises(ValueError):
            movement_probe({})

    def test_interventions_keep_fixed_speed_energy_and_truthful_observations(self):
        from food import Food
        for mode, sign in (("intact", 1), ("mirrored", -1), ("hidden", 0)):
            world = World(seed=42, population_size=1, food_count=0, fixed_speed=60, food_sensor_mode=mode)
            c = world.creatures[0]
            c.x, c.y, c.heading = 500, 300, 0
            world.food = [Food(550, 350)]
            c.brain.forward = lambda s: np.array([s[1], -1])
            self.assertTrue(world.perceive_food(c).visible)
            world.update(SIMULATION_STEP)
            self.assertEqual(np.sign(c.turn_rate), sign)
            self.assertEqual(c.speed, 60)
            self.assertAlmostEqual(c.energy, 100 - 5 * SIMULATION_STEP)
            self.assertTrue(world.perceive_food(c).visible)


class StrategyStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        with patch("world.create_population", side_effect=short_population):
            cls.options = make_sources(cls.temporary.name)
            cls.report = run_study([11, 22], repeats=2, **cls.options)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_reuses_models_and_reconstructs_exact_ancestral_founders_without_training(self):
        before = {p.name: file_digest(p) for p in self.options["models_dir"].glob("*.npz")}
        with patch("world.create_population", side_effect=short_population), patch("experiment_speed.train_lineage", side_effect=AssertionError("No retraining")):
            training, starts, banks, _ = prepare_lineage(11, 2, self.options["models_dir"])
            original = World(seed=11, fixed_speed=60.0)
            self.assertEqual(initial_conditions_digest(original), starts[0])
            self.assertEqual(bank_digest(banks["unselected"]), bank_digest({c.creature_id: c.brain for c in original.creatures}))
            self.assertNotEqual(bank_digest(banks["evolved"]), bank_digest(banks["unselected"]))
            self.assertEqual(training["completed_generations"], 2)
        self.assertEqual(before, {p.name: file_digest(p) for p in self.options["models_dir"].glob("*.npz")})

    def test_all_seven_conditions_are_matched_frozen_unseen_and_fixed_speed(self):
        r = self.report
        self.assertEqual(r["protocol"]["training_cohorts"], 0)
        self.assertEqual(r["protocol"]["planned_test_cohorts"], 84)
        for trial in r["trials"]:
            self.assertEqual(len(trial["tests"]), 6)
            for test in trial["tests"]:
                self.assertEqual(set(test["conditions"]), set(CONDITIONS))
                self.assertEqual(len({r["initial_conditions"] for r in test["conditions"].values()}), 1)
                for name, record in test["conditions"].items():
                    bank, mode = ("evolved", "intact") if name == "random" else name.split("_", 1)
                    self.assertEqual(record["report"]["food_sensor_mode"], mode)
                    self.assertEqual(record["genomes_sha256"], trial["genome_hashes"][bank])
                    self.assertNotIn(record["initial_conditions"], r["protocol"]["excluded_initial_conditions"])
                    self.assertFalse(record["report"]["evolution_enabled"])
                    self.assertAlmostEqual(record["report"]["generations"][0]["mean_speed"], 60)

    def test_difference_in_differences_uses_within_lineage_sensor_effects(self):
        values = {c: {m: [0, 0] for m in METRICS} for c in CONDITIONS}
        for c, meals in {"evolved_intact": [10, 20], "evolved_mirrored": [5, 10],
                         "unselected_intact": [8, 8], "unselected_mirrored": [4, 4]}.items():
            values[c]["mean_food_eaten"] = meals
        effects = primary_effects(values, "uniform")
        row = effects["evolved_bearing_benefit"]
        self.assertEqual(row["n_pairs"], 2)
        self.assertEqual(row["mean_difference"], 3.5)
        self.assertEqual(row["difference_ci95"], [1, 6])
        rows = [{"sign_test_p": 0.001, "difference_ci95": [1, 2]} for _ in range(12)]
        classify_primary(rows)
        for row in rows:
            self.assertAlmostEqual(row["holm_adjusted_p"], 0.012)

    def test_repeats_do_not_inflate_sample_size_and_nonconfirmation_does_not_select_a_strategy(self):
        r = deepcopy(self.report)
        for trial, outcomes in zip(r["trials"], ((2, 4), (6, 8))):
            for test, outcome in zip([t for t in trial["tests"] if t["environment"] == "uniform"], outcomes):
                stats = test["conditions"]["evolved_intact"]["report"]["generations"][0]
                stats.update(mean_food_eaten=outcome, mean_fitness=stats["mean_survival_seconds"] + outcome * 10)
        result = analyze_results(r)["environments"]["uniform"]
        self.assertEqual(result["seed_values"]["evolved_intact"]["mean_food_eaten"], [3, 7])
        self.assertEqual(result["primary_tests"]["useful_bearing"]["n_pairs"], 2)
        self.assertEqual(result["primary_tests"]["useful_bearing"]["conclusion"], "inconclusive")
        self.assertFalse(result["evidence"]["evolved_food_guidance_supported"])
        self.assertIn("does not identify an exclusive", result["evidence"]["interpretation_limit"])
        self.assertNotIn("sign_test_p", result["secondary"]["evolved_hidden_vs_random"]["mean_fitness"])

    def test_missing_mismatched_or_mutated_records_fail_validation(self):
        def condition(r):
            return r["trials"][0]["tests"][0]["conditions"]["evolved_intact"]
        changes = [
            lambda r: r["trials"].pop(),
            lambda r: r["trials"][0]["tests"].pop(),
            lambda r: r["trials"][0]["tests"][0]["conditions"].pop("unselected_mirrored"),
            lambda r: r["trials"][0].update(source_model_sha256="bad"),
            lambda r: condition(r).update(genomes_sha256="bad"),
            lambda r: condition(r)["report"].update(food_sensor_mode="hidden"),
            lambda r: condition(r)["report"].update(fixed_speed=None),
            lambda r: condition(r)["report"].update(evolution_enabled=True),
            lambda r: condition(r)["report"]["generations"][0].update(mean_speed=30),
            lambda r: r["trials"][0]["tests"][0].update(seed=0),
            lambda r: r["trials"][0]["probes"]["evolved"]["movement"].update(mean_abs_turn=0.999),
        ]
        for change in changes:
            r = deepcopy(self.report)
            change(r)
            with self.assertRaises(ValueError):
                analyze_results(r)

    def test_every_previous_layout_is_excluded_even_from_other_source_lineages(self):
        r = deepcopy(self.report)
        start = r["trials"][1]["tests"][0]["conditions"]["random"]["initial_conditions"]
        r["protocol"]["excluded_initial_conditions"].append(start)
        with self.assertRaises(ValueError):
            analyze_results(r)

    def test_serial_and_parallel_results_match_and_checkpoints_stay_incomplete(self):
        checkpoints = []
        with patch("world.create_population", side_effect=short_population), patch("experiment_strategy.ProcessPoolExecutor", ThreadPoolExecutor):
            r = run_study([11, 22], repeats=2, workers=2, checkpoint=lambda r: checkpoints.append(deepcopy(r)), **self.options)
        self.assertEqual(r, self.report)
        self.assertEqual([r["status"] for r in checkpoints], ["running", "running", "running", "complete"])
        with self.assertRaises(ValueError):
            build_strategy_figure(checkpoints[-2])

    def test_unselected_archives_roundtrip_and_cannot_overwrite_original_models(self):
        with tempfile.TemporaryDirectory() as directory, patch("world.create_population", side_effect=short_population):
            _, starts, banks, path = prepare_lineage(11, 2, self.options["models_dir"], directory)
            metadata, loaded = load_unselected(path, 11)
            self.assertEqual(metadata["initial_conditions"], starts[0])
            self.assertEqual(bank_digest(loaded), bank_digest(banks["unselected"]))
            loaded[1].input_weights[0, 0] += 1
            self.assertEqual(bank_digest(load_unselected(path, 11)[1]), bank_digest(banks["unselected"]))
            before = file_digest(path)
            prepare_lineage(11, 2, self.options["models_dir"], directory)
            self.assertEqual(file_digest(path), before)
            with self.assertRaises(ValueError):
                load_unselected(path, 22)
            with self.assertRaises(ValueError):
                run_study([11, 22], unselected_dir=self.options["models_dir"], **self.options)

    def test_wrong_source_report_or_founder_generation_is_rejected_before_testing(self):
        with tempfile.TemporaryDirectory() as directory, patch("world.create_population", side_effect=short_population):
            prior = json.loads(self.options["prior_report"].read_text())
            prior["trials"][0]["genomes_sha256"] = "wrong"
            path = Path(directory) / "prior.json"
            path.write_text(json.dumps(prior))
            with self.assertRaises(ValueError):
                run_study([11, 22], **{**self.options, "prior_report": path})
            with self.assertRaises(ValueError):
                prepare_lineage(11, 3, self.options["models_dir"])
            with patch("experiment_strategy.initial_conditions_digest", return_value="changed"):
                with self.assertRaises(ValueError):
                    prepare_lineage(11, 2, self.options["models_dir"])

    def test_plot_shows_lineage_points_and_exports_all_formats(self):
        figure = build_strategy_figure(self.report)
        self.assertEqual(len(figure.axes), 9)
        for axis in figure.axes[:3]:
            self.assertEqual([len(c.get_offsets()) for c in axis.collections], [2, 1] * 7)
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("png", "svg", "pdf"):
                path = Path(directory) / f"figure.{suffix}"
                save_strategy_plot(self.report, path)
                self.assertGreater(path.stat().st_size, 1000)

    def test_cli_preserves_sources_and_writes_protocol_models_and_complete_report(self):
        with tempfile.TemporaryDirectory() as directory, patch("world.create_population", side_effect=short_population):
            output = Path(directory) / "study.json"
            declaration = Path(directory) / "protocol.json"
            args = ["experiment_strategy.py", "--seeds", "11", "22", "--source-generations", "2",
                    "--models-dir", str(self.options["models_dir"]), "--prior-report", str(self.options["prior_report"]),
                    "--unselected-models-dir", str(Path(directory) / "founders"), "--output", str(output), "--protocol-output", str(declaration)]
            with patch("sys.argv", args), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            report = json.loads(output.read_text())
            protocol = json.loads(declaration.read_text())
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["protocol"], protocol["protocol"])
            self.assertTrue((Path(directory) / "founders/seed-11.npz").exists())
            self.assertEqual(report["protocol"]["planned_test_cohorts"], 42)
            args[args.index("--output") + 1] = str(self.options["prior_report"])
            with patch("sys.argv", args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main()

    def test_invalid_budgets_are_rejected(self):
        for kwargs in ({"seeds": [1]}, {"seeds": [1, 1]}, {"repeats": 0}, {"workers": 0}, {"generations": 1}):
            with self.assertRaises(ValueError):
                run_study(**kwargs)


if __name__ == "__main__":
    unittest.main()
