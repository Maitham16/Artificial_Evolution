"""Fairness, provenance, inference, and complete lifetime reporting for Step 27."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from analyze_intelligence import bank_digest
from brain import NeuralNetwork
from compare_creatures import holm_adjust
from creature import create_population
from evaluation_world import EvaluationWorld
from food import Food
from simulation import EvolutionSimulation
from compare_creatures import complete_generation
from world import World
from experiment_evaluation import (ARMS, BASELINES, ENVIRONMENTS, GENERATIONS, TRAINING_CONFIG,
    analyze_results, conditions_for, effect, genetic_diversity, load_raw, main, mean_interval,
    neural_features, prepare_protocol, replay_diversity, run_lineage, run_study, validate_individuals,
    validate_study)
from experiment_selection import load_models, save_models, train_pair
from experiment_strategy import file_digest
from plot_evaluation import build_effects_figure, build_mechanisms_figure, build_performance_figure, save_plots
from plot_traits import export


def short_energy_population(*args):
    people = create_population(*args)
    for c in people:
        c.energy = .01  # Fast test fixture; preserve ordinary body and lifespan draws.
    return people


class CollisionExecutionTests(unittest.TestCase):
    def assert_same_state(self, a, b):
        self.assertEqual(a.creatures, b.creatures)
        self.assertEqual(a.dead_creatures, b.dead_creatures)
        self.assertEqual(a.food, b.food)
        self.assertEqual(a.total_food_eaten, b.total_food_eaten)
        self.assertEqual(a._food_rng.getstate(), b._food_rng.getstate())
        self.assertEqual(a._motion_rng.getstate(), b._motion_rng.getstate())
        self.assertEqual(EvolutionSimulation(a).report(), EvolutionSimulation(b).report())
        for name in ("_alive_time", "_speed_time", "_food_visible_time", "_food_facing_time"):
            self.assertEqual(getattr(a, name), getattr(b, name))

    def test_full_size_states_match_scalar_physics_in_all_controller_food_modes(self):
        for controller in ("random", "greedy", "neural"):
            for distribution in ("uniform", "clustered"):
                with self.subTest(controller=controller, distribution=distribution):
                    kwargs = dict(seed=270027, controller=controller, food_distribution=distribution, fixed_speed=60)
                    a, b = World(**kwargs), EvaluationWorld(**kwargs)
                    for _ in range(2):
                        a.update(1.)
                        b.update(1.)
                        self.assert_same_state(a, b)

    def test_complete_lifetimes_and_reports_match_scalar_reference(self):
        for controller in ("random", "greedy", "neural"):
            for distribution in ("uniform", "clustered"):
                kwargs = dict(seed=270028, controller=controller, food_distribution=distribution,
                              fixed_speed=60, population_size=8, food_count=12)
                a, b = World(**kwargs), EvaluationWorld(**kwargs)
                sa, sb = EvolutionSimulation(a, auto_advance=False), EvolutionSimulation(b, auto_advance=False)
                complete_generation(sa)
                complete_generation(sb)
                self.assert_same_state(a, b)
                self.assertEqual(sa.report(), sb.report())

    def test_contact_ties_full_stocks_dead_actors_and_near_tangent_rejection_match(self):
        worlds = [kind(seed=270029, population_size=5, food_count=0) for kind in (World, EvaluationWorld)]
        for w in worlds:
            for c in w.creatures:
                c.x, c.y, c.radius, c.energy = 100., 100., 8, 80.
            w.creatures[0].energy = 100.
            w.creatures[2].energy = 0.
            w.creatures.reverse()  # Equal contacts resolve by ID rather than list position.
            w.food = [Food(111. + 1e-12, 100.), Food(111., 100.), Food(100., 100.), Food(100., 100.)]
            w.food_count = 4
            w._resolve_food_collisions()
        self.assert_same_state(*worlds)
        self.assertEqual(worlds[0].total_food_eaten, 3)
        self.assertEqual(worlds[0].food[0], Food(111. + 1e-12, 100.))

    def test_empty_population_and_empty_food_keep_replenishment_draws(self):
        a, b = World(seed=270030, food_count=3), EvaluationWorld(seed=270030, food_count=3)
        for w in (a, b):
            w.creatures = []
            w.food = []
            w._resolve_food_collisions()
        self.assert_same_state(a, b)


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.models = cls.root / "models"
        cls.source = cls.root / "source.json"
        trials = []
        with patch("world.create_population", side_effect=short_energy_population):
            for seed in (42, 43):
                training, starts, transitions, banks = train_pair(seed, GENERATIONS)
                save_models(cls.models / f"seed-{seed}.npz", seed, training, starts, transitions, banks)
                trials.append({"seed": seed, "training": training, "training_initial_conditions": starts,
                               "transitions": transitions, "genome_hashes": {k: bank_digest(b) for k, b in banks.items()}})
        cls.source.write_text(json.dumps({"status": "complete", "protocol": {"seeds": [42, 43],
            "generations": GENERATIONS, "training_configuration": TRAINING_CONFIG}, "trials": trials}))
        with patch("world.create_population", side_effect=short_energy_population):
            cls.report = run_study([42, 43], repeats=2, models_dir=cls.models, source_report=cls.source,
                                   runs_dir=cls.root / "runs")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_declared_baselines_share_unseen_starts_and_frozen_weights(self):
        validate_study(self.report)
        self.assertEqual(self.report["status"], "complete")
        self.assertEqual(self.report["protocol"]["planned_test_cohorts"], 132)
        for trial in self.report["trials"]:
            for test in trial["tests"]:
                records = test["conditions"]
                self.assertTrue(set(BASELINES) <= set(records))
                self.assertEqual(len({r["initial_conditions"] for r in records.values()}), 1)
                self.assertTrue(all(r["report"]["fixed_speed"] == 60 and not r["report"]["evolution_enabled"] for r in records.values()))
                self.assertEqual(records["evolved"]["genomes_sha256"], trial["genome_hashes"]["selection"])
                self.assertEqual(records["neutral"]["genomes_sha256"], trial["genome_hashes"]["random_parent"])

    def test_barren_has_no_redundant_sensor_probes(self):
        self.assertEqual(conditions_for("barren"), (*BASELINES, "founder"))
        self.assertIn("neutral_hidden", conditions_for("sparse"))
        for trial in self.report["trials"]:
            for test in trial["tests"]:
                if test["environment"] != "barren":
                    self.assertEqual(test["conditions"]["evolved_hidden"]["report"]["food_sensor_mode"], "hidden")
                    self.assertEqual(test["conditions"]["evolved_hidden"]["genomes_sha256"], test["conditions"]["evolved"]["genomes_sha256"])

    def test_mutation_replay_checks_genomes_draws_and_genealogy(self):
        _, _, transitions, banks = load_models(self.models / "seed-42.npz", 42, GENERATIONS)
        rows = replay_diversity(42, transitions, banks)
        self.assertEqual(len(rows["selection"]), 10)
        self.assertEqual(rows["selection"][0], rows["random_parent"][0])
        self.assertEqual(rows["selection"][0]["founder_families"], 100)
        self.assertLessEqual(rows["random_parent"][-1]["founder_families"], 20)
        transitions["selection"][0]["mutation_draws_sha256"] = "wrong"
        with self.assertRaises(ValueError):
            replay_diversity(42, transitions, banks)

    def test_rms_matches_direct_pairwise_distances_and_ignores_throttle_in_steering(self):
        bank = {i: NeuralNetwork(np.random.default_rng(i)) for i in range(4)}
        x = neural_features(bank)
        expected = np.sqrt(np.mean([np.sum((x[i] - x[j]) ** 2) for i in range(4) for j in range(i)]))
        stats = genetic_diversity(bank, {i: i // 2 for i in bank})
        self.assertAlmostEqual(stats["full_rms"], expected)
        self.assertAlmostEqual(stats["effective_founder_families"], 2)
        before = neural_features(bank, True)
        bank[0].output_weights[:, 1] += 100
        bank[0].output_bias[1] += 100
        np.testing.assert_array_equal(before, neural_features(bank, True))
        self.assertGreater(genetic_diversity(bank, {i: i for i in bank})["full_rms"], stats["full_rms"])

    def test_raw_lifetimes_reproduce_metrics_and_failure_rates(self):
        raw = load_raw(self.report["trials"][0])
        record = raw["tests"][0]["conditions"]["evolved"]
        validate_individuals(record)
        self.assertEqual(len(record["individuals"]), 100)
        self.assertEqual(record["failure_rates"], {"starvation_rate": 1., "zero_meal_rate": 1.})
        for key, value in (("age", -1), ("food_eaten", -1), ("death_cause", "old_age"), ("fitness", 500)):
            broken = deepcopy(record)
            broken["individuals"][0][key] = value
            with self.assertRaises(ValueError):
                validate_individuals(broken)

    def test_missing_duplicate_or_changed_physical_cells_rejected(self):
        for change in ("missing", "duplicate", "speed", "controller", "genome", "layout", "budget", "condition"):
            r = deepcopy(self.report)
            test = r["trials"][0]["tests"][0]
            if change == "missing": r["trials"][0]["tests"].pop()
            elif change == "duplicate": r["trials"][0]["tests"][-1] = deepcopy(test)
            elif change == "speed": test["conditions"]["random"]["report"]["fixed_speed"] = 80
            elif change == "controller": test["conditions"]["greedy"]["report"]["controller"] = "random"
            elif change == "genome": test["conditions"]["evolved"]["genomes_sha256"] = "wrong"
            elif change == "layout": test["conditions"]["neutral"]["initial_conditions"] = "wrong"
            elif change == "budget": r["protocol"]["inherited_transitions"] = 10
            elif change == "condition": del test["conditions"]["founder"]
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_study(r, verify_files=False)

    def test_raw_checksums_and_summary_corruption_are_detected(self):
        trial = deepcopy(self.report["trials"][0])
        trial["raw_sha256"] = "wrong"
        with self.assertRaises(ValueError): load_raw(trial)
        trial = deepcopy(self.report["trials"][0])
        trial["tests"][0]["conditions"]["random"]["failure_rates"]["starvation_rate"] = 0
        with self.assertRaises(ValueError): load_raw(trial)

    def test_source_archives_must_agree_with_published_training(self):
        p = prepare_protocol([42, 43], 1, self.models, self.source)
        self.assertEqual(len(p["source_models"]), 2)
        r = deepcopy(self.report)
        r["protocol"]["source_report_sha256"] = "wrong"
        with self.assertRaises(ValueError): validate_study(r)
        source = json.loads(self.source.read_text())
        source["trials"][0]["genome_hashes"]["selection"] = "wrong"
        path = self.root / "broken-source.json"
        path.write_text(json.dumps(source))
        with self.assertRaises(ValueError): prepare_protocol([42, 43], 1, self.models, path)

    def test_exact_sign_tests_ties_intervals_and_correction(self):
        row = effect(np.ones(16), np.zeros(16), "known", True)
        self.assertEqual(row["sign_test_p"], 2 / 2 ** 16)
        self.assertEqual(row["difference_ci95"], [1., 1.])
        self.assertEqual(row["left_mean"], 1)
        tied = effect([0, 1e-12], [0, 0], "ties", True)
        self.assertEqual((tied["wins"], tied["losses"], tied["ties"], tied["sign_test_p"]), (0, 0, 2, 1.))
        self.assertEqual(holm_adjust([.01, .03, .04]), [.03, .06, .06])
        self.assertEqual(mean_interval([1, 2, 3], "fixed"), mean_interval([1, 2, 3], "fixed"))
        with self.assertRaises(ValueError): mean_interval([np.nan, 2], "bad")

    def test_complete_primary_and_exploratory_families_include_failure_ties(self):
        a = self.report["analysis"]
        self.assertEqual((a["primary_test_count"], a["exploratory_test_count"]), (45, 21))
        for data in a["environments"].values():
            for row in data["comparisons"].values():
                for effect_row in row.values():
                    self.assertEqual(effect_row["n_pairs"], 2)
                    self.assertEqual(effect_row["conclusion"], "inconclusive")
                    self.assertEqual(effect_row["holm_adjusted_p"], 1)
            self.assertEqual(len(data["nonpositive_fitness_seed_cases"]["random"]), 2)

    def test_repeats_average_within_training_seed_before_inference(self):
        r = deepcopy(self.report)
        for index, trial in enumerate(r["trials"]):
            for test in trial["tests"]:
                stats = test["conditions"]["evolved"]["report"]["generations"][0]
                meals = (index + 1) * test["repeat"]
                stats.update(mean_food_eaten=meals, mean_fitness=stats["mean_survival_seconds"] + 10 * meals)
        a = analyze_results(r, verify_files=False)
        row = a["environments"]["uniform"]
        self.assertEqual(row["seed_values"]["evolved"]["mean_food_eaten"], [1.5, 3.])
        self.assertEqual(row["comparisons"]["evolved_minus_random"]["mean_food_eaten"]["n_pairs"], 2)
        self.assertAlmostEqual(row["food_sensor_intervention"]["mean_food_eaten"]["selection_minus_neutral_sensor_loss"]["mean_difference"], 2.25)

    def test_serial_and_parallel_are_identical(self):
        with patch("world.create_population", side_effect=short_energy_population), patch("experiment_evaluation.ProcessPoolExecutor", ThreadPoolExecutor):
            parallel = run_study([42, 43], repeats=2, workers=2, models_dir=self.models, source_report=self.source,
                                 runs_dir=self.root / "parallel")
        self.assertEqual(parallel["analysis"], self.report["analysis"])
        for a, b in zip(parallel["trials"], self.report["trials"]):
            self.assertEqual(a["tests"], b["tests"])
            self.assertEqual(a["raw_sha256"], b["raw_sha256"])

    def test_invalid_requests_and_existing_records_fail_before_work(self):
        for kwargs in ({"seeds": [42, 42]}, {"seeds": [42]}, {"repeats": 0}, {"workers": 0}):
            with self.assertRaises(ValueError): run_study(**kwargs)
        with self.assertRaises(ValueError):
            run_study([42, 43], models_dir=self.models, source_report=self.source, runs_dir=self.root / "runs")
        with self.assertRaises(ValueError): prepare_protocol([1, 2], 1, self.models, self.source)

    def test_all_scientific_figure_exports_and_incomplete_rejection(self):
        for function, count, suffix in ((build_performance_figure, 15, ".png"), (build_effects_figure, 15, ".svg"),
                                        (build_mechanisms_figure, 6, ".pdf")):
            figure = function(self.report["analysis"])
            self.assertEqual(len(figure.axes), count)
            path = self.root / (function.__name__ + suffix)
            export(figure, path)
            self.assertGreater(path.stat().st_size, 1000)
        with self.assertRaises(ValueError): save_plots({"status": "running"}, self.root / "no.png")

    def test_cli_preserves_existing_outputs(self):
        existing = self.root / "existing.json"
        existing.write_text("preserve me")
        with patch("sys.argv", ["experiment_evaluation.py", "--output", str(existing)]), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error: main()
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(existing.read_text(), "preserve me")


if __name__ == "__main__":
    unittest.main()
