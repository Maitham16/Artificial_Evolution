"""Matched habitat training, balanced curricula, frozen cross-tests, and niche evidence."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from analyze_intelligence import bank_digest
from creature import create_population
from experiment_selection import RecordedMutationRNG
from experiment_specialization import (DEFAULT_SEEDS, HABITATS, REGIMES, HabitatWorld, analyze_results,
    bodies_digest, curriculum, load_models, main, run_study, train_group)
from plot_specialization import build_specialization_figure, save_specialization_plot
from reproduction import reproduce_brains


def short_population(*args):
    population = create_population(*args)
    for c in population:
        c.lifespan = 0.005
    return population


class CurriculumTests(unittest.TestCase):
    def test_equal_exposure_and_all_six_orders_are_counterbalanced(self):
        schedules = [curriculum(seed, "generalist", 9) for seed in DEFAULT_SEEDS]
        for schedule in schedules:
            self.assertEqual(Counter(schedule), Counter({h: 3 for h in HABITATS}))
            for index in (0, 3, 6):
                self.assertEqual(set(schedule[index:index + 3]), set(HABITATS))
        for index in (0, 3, 6):
            self.assertEqual(sorted(Counter(tuple(s[index:index + 3]) for s in schedules).values()), [3] * 6)
        self.assertEqual(Counter(s[-1] for s in schedules), Counter({h: 6 for h in HABITATS}))
        for habitat in HABITATS:
            self.assertEqual(curriculum(1901, habitat, 9), [habitat] * 9)

    def test_actual_worlds_apply_food_treatments_with_identical_founders_and_bodies(self):
        worlds = [HabitatWorld(1901, r, 9) for r in REGIMES]
        self.assertEqual(len({bodies_digest(w) for w in worlds}), 1)
        self.assertEqual(len({bank_digest({c.creature_id: c.brain for c in w.creatures}) for w in worlds}), 1)
        for regime, world in zip(REGIMES, worlds):
            habitat = curriculum(1901, regime, 9)[0]
            self.assertEqual(world.food_count, HABITATS[habitat]["food_count"])
            self.assertEqual(len(world.food), world.food_count)
            self.assertEqual(world.food_distribution, HABITATS[habitat]["food_distribution"])
            self.assertTrue(all(c.speed == c.max_speed == 60 for c in world.creatures))

    def test_final_selection_is_included_in_frozen_offspring_genomes(self):
        with patch("world.create_population", side_effect=short_population):
            training, transitions, banks = train_group(11, 3)
        for regime in REGIMES:
            self.assertEqual(len(training[regime]), 3)
            self.assertEqual(len(transitions[regime]), 3)
            self.assertEqual(transitions[regime][-1]["to_generation"], 4)
            bank = {key: b.copy() for key, b in banks["founder"].items()}
            for trace in transitions[regime]:
                parents = [SimpleNamespace(creature_id=key, brain=bank[key]) for key in trace["parent_ids"]]
                rng = RecordedMutationRNG(trace["mutation_seed"])
                children = reproduce_brains(parents, rng)
                self.assertEqual(rng.digest.hexdigest(), trace["mutation_draws_sha256"])
                bank = {index: child.brain for index, child in enumerate(children, 1)}
            self.assertEqual(bank_digest(bank), bank_digest(banks[regime]))
        for index in range(3):
            self.assertEqual(len({transitions[r][index]["mutation_draws_sha256"] for r in REGIMES}), 1)

    def test_bad_curricula_fail(self):
        for rounds in (0, 2, 4, 10, True):
            with self.assertRaises(ValueError):
                curriculum(1901, "generalist", rounds)
        with self.assertRaises(ValueError):
            curriculum(1901, "unknown", 9)


class SpecializationStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("world.create_population", side_effect=short_population):
            cls.report = run_study([11, 22], rounds=3, repeats=2)

    def test_complete_matrix_has_equal_budgets_and_matched_frozen_tests(self):
        r = self.report
        self.assertEqual(r["protocol"]["planned_new_training_cohorts"], 24)
        self.assertEqual(r["protocol"]["planned_test_cohorts"], 48)
        self.assertEqual(np.array(r["analysis"]["performance_matrices"]["mean_fitness"]).shape, (4, 3))
        for trial in r["trials"]:
            self.assertEqual(trial["frozen_birth_generation"], 4)
            for test in trial["tests"]:
                self.assertEqual(set(test["conditions"]), set(REGIMES))
                self.assertEqual(len({v["initial_conditions"] for v in test["conditions"].values()}), 1)
                for regime, data in test["conditions"].items():
                    self.assertEqual(data["genomes_sha256"], trial["genome_hashes"][regime])
                    self.assertFalse(data["report"]["evolution_enabled"])
                    self.assertEqual(data["report"]["food_count"], HABITATS[test["habitat"]]["food_count"])

    def test_repeats_stay_within_seed_groups_and_primary_family_has_nine(self):
        r = deepcopy(self.report)
        for trial, outcomes in zip(r["trials"], ((2, 4), (6, 8))):
            for test, value in zip([t for t in trial["tests"] if t["habitat"] == "uniform"], outcomes):
                stats = test["conditions"]["uniform"]["report"]["generations"][0]
                stats.update(mean_food_eaten=value, mean_fitness=stats["mean_survival_seconds"] + 10 * value)
        result = analyze_results(r)
        self.assertEqual(result["habitats"]["uniform"]["seed_values"]["uniform"]["mean_food_eaten"], [3, 7])
        count = 0
        for data in result["habitats"].values():
            for metrics in data["home_contrasts"].values():
                self.assertEqual(metrics["mean_fitness"]["n_pairs"], 2)
                self.assertIn("holm_adjusted_p", metrics["mean_fitness"])
                self.assertNotIn("sign_test_p", metrics["mean_food_eaten"])
                count += 1
        self.assertEqual(count, 9)

    def test_missing_corrupt_or_unmatched_studies_are_rejected(self):
        def cell(r):
            return r["trials"][0]["tests"][0]["conditions"]["uniform"]
        changes = [
            lambda r: r["trials"].pop(),
            lambda r: r["trials"][0]["tests"].pop(),
            lambda r: r["trials"][0]["tests"][0]["conditions"].pop("generalist"),
            lambda r: cell(r).update(genomes_sha256="bad"),
            lambda r: cell(r)["report"].update(fixed_speed=30),
            lambda r: cell(r)["report"].update(food_count=50),
            lambda r: r["trials"][0].update(frozen_birth_generation=3),
            lambda r: r["trials"][0]["transitions"]["sparse"].pop(),
            lambda r: r["trials"][0]["training"]["generalist"][0].update(habitat="invalid"),
            lambda r: r["protocol"]["curricula"]["11"]["generalist"].reverse(),
        ]
        for change in changes:
            r = deepcopy(self.report)
            change(r)
            with self.assertRaises(ValueError):
                analyze_results(r)

    def test_model_roundtrip_replay_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as directory, patch("world.create_population", side_effect=short_population):
            original = run_study([11, 22], rounds=3, models_dir=directory)
            with patch("experiment_specialization.train_group", side_effect=AssertionError("No retraining")):
                replay = run_study([11, 22], rounds=3, models_dir=directory, reuse=True)
            self.assertEqual(original["trials"], replay["trials"])
            self.assertEqual(original["analysis"], replay["analysis"])
            path = Path(directory) / "seed-11.npz"
            training, traces, banks = load_models(path, 11, 3)
            banks["uniform"][1].input_weights[0, 0] += 1
            self.assertNotEqual(bank_digest(banks["uniform"]), bank_digest(load_models(path, 11, 3)[2]["uniform"]))
            with self.assertRaises(ValueError):
                load_models(path, 22, 3)
            with self.assertRaises(ValueError):
                run_study([11, 22], rounds=3, models_dir=directory)

    def test_parallel_determinism_and_running_checkpoints(self):
        checkpoints = []
        with patch("world.create_population", side_effect=short_population), patch("experiment_specialization.ProcessPoolExecutor", ThreadPoolExecutor):
            parallel = run_study([11, 22], rounds=3, repeats=2, workers=2, checkpoint=lambda r: checkpoints.append(deepcopy(r)))
        self.assertEqual(parallel, self.report)
        self.assertEqual([r["status"] for r in checkpoints], ["running", "running", "running", "complete"])
        with self.assertRaises(ValueError):
            build_specialization_figure(checkpoints[-2])

    def test_heatmaps_have_four_by_three_cells_and_export_formats(self):
        figure = build_specialization_figure(self.report)
        matrices = [axis.images[0].get_array() for axis in figure.axes if axis.images]
        self.assertEqual([m.shape for m in matrices], [(4, 3), (4, 3)])
        np.testing.assert_allclose(matrices[1][-1], 0)
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("png", "svg", "pdf"):
                output = Path(directory) / f"figure.{suffix}"
                save_specialization_plot(self.report, output)
                self.assertGreater(output.stat().st_size, 1000)

    def test_cli_declaration_models_matrix_and_source_protection(self):
        with tempfile.TemporaryDirectory() as directory, patch("world.create_population", side_effect=short_population):
            output, protocol = Path(directory) / "report.json", Path(directory) / "protocol.json"
            args = ["experiment_specialization.py", "--seeds", "11", "22", "--rounds", "3", "--models-dir", str(Path(directory) / "models"),
                    "--output", str(output), "--protocol-output", str(protocol)]
            with patch("sys.argv", args), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            r = json.loads(output.read_text())
            self.assertEqual(r["status"], "complete")
            self.assertEqual(r["protocol"], json.loads(protocol.read_text())["protocol"])
            self.assertTrue((Path(directory) / "models/seed-11.npz").exists())
            args[args.index("--output") + 1] = "results/step18-selection.json"
            with patch("sys.argv", args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main()

    def test_invalid_budgets_fail_before_work(self):
        for kwargs in ({"seeds": [1]}, {"seeds": [1, 1]}, {"rounds": 4}, {"rounds": 0}, {"workers": 0}, {"repeats": 0}, {"reuse": True}):
            with self.assertRaises(ValueError):
                run_study(**kwargs)


class ReciprocalEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("world.create_population", side_effect=short_population):
            cls.base = run_study(list(range(2001, 2019)), rounds=3)

    def synthetic(self, kind):
        r = deepcopy(self.base)
        for trial in r["trials"]:
            for test in trial["tests"]:
                for regime, record in test["conditions"].items():
                    if kind == "crossover":
                        meals = 20 if regime == "generalist" else 30 if regime == test["habitat"] else 10
                    else:
                        meals = {"uniform": 30, "clustered": 20, "sparse": 10, "generalist": 15}[regime]
                    stats = record["report"]["generations"][0]
                    stats.update(mean_food_eaten=meals, mean_fitness=stats["mean_survival_seconds"] + meals * 10)
        return analyze_results(r)

    def test_reciprocal_home_wins_and_specialist_vs_generalist_are_detected(self):
        result = self.synthetic("crossover")
        self.assertTrue(result["all_home_specialists_beat_generalist"])
        self.assertTrue(all(row["supported"] for row in result["reciprocal_specialization"].values()))

    def test_universally_stronger_policy_is_not_mistaken_for_reciprocal_specialization(self):
        result = self.synthetic("universal")
        self.assertFalse(result["all_home_specialists_beat_generalist"])
        self.assertFalse(any(row["supported"] for row in result["reciprocal_specialization"].values()))


if __name__ == "__main__":
    unittest.main()
