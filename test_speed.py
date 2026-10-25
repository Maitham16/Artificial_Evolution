"""Fixed-speed fairness, greedy controls, clustered food, and seed-level inference."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
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
from brain import MAX_TURN_RATE
from compare_creatures import complete_generation, initial_conditions_digest
from creature import create_population
from experiment_speed import (CONDITIONS, ENVIRONMENTS, FIXED_SPEED, METRICS, analyze_results,
                              classify_primary, load_model, main, paired_metrics, run_study, train_lineage)
from food import Food
from main import main as world_main
from plot_speed import build_speed_figure, save_speed_plot
from simulation import EvolutionSimulation
from world import CLUSTER_COUNT, SIMULATION_STEP, World


def short_population(*args):
    creatures = create_population(*args)
    for creature in creatures:
        creature.lifespan = 0.005
    return creatures


class FixedSpeedTests(unittest.TestCase):
    def test_all_controllers_have_the_same_speed_and_energy_cost_before_first_tick(self):
        worlds = [World(seed=42, controller=controller, fixed_speed=60, food_count=0) for controller in ("neural", "random", "greedy")]
        self.assertEqual(len({initial_conditions_digest(world) for world in worlds}), 1)
        for world in worlds:
            for creature in world.creatures:
                self.assertEqual((creature.speed, creature.max_speed, creature.energy_cost_per_second), (60, 60, 5))
                creature.brain.forward = lambda _: np.array([0.3, -1.0])
            world.update(SIMULATION_STEP)
            for creature in world.creatures:
                self.assertEqual(creature.speed, 60)
                self.assertAlmostEqual(creature.energy, 100 - 5 * SIMULATION_STEP)

    def test_constraint_survives_breeding_restart_pause_and_external_speed_changes(self):
        with patch("world.create_population", side_effect=short_population):
            world = World(seed=42, fixed_speed=60, food_distribution="clustered")
            simulation = EvolutionSimulation(world, auto_advance=False)
            start = initial_conditions_digest(world)
            complete_generation(simulation)
            self.assertTrue(simulation.advance_generation())
            self.assertTrue(all(c.speed == c.max_speed == 60 for c in world.creatures))
            self.assertEqual(world.food_distribution, "clustered")
            simulation.restart(42)
            self.assertEqual(initial_conditions_digest(world), start)
            world.paused = True
            world.update(1)
            self.assertTrue(all(c.age == 0 for c in world.creatures))
            world.paused = False
            for c in world.creatures:
                c.speed = 0
            complete_generation(simulation)
            self.assertAlmostEqual(world.generation_stats[0].mean_speed, 60)

    def test_invalid_speed_distribution_and_controller_fail(self):
        for speed in (0, -1, math.nan, math.inf, True):
            with self.assertRaises(ValueError):
                World(fixed_speed=speed)
        with self.assertRaises(ValueError):
            World(food_distribution="unknown")
        with self.assertRaises(ValueError):
            World(controller="unknown")

    def test_default_throttle_still_controls_speed(self):
        world = World(seed=42, food_count=0)
        for c in world.creatures:
            c.brain.forward = lambda _: np.array([0, -1])
        world.update(SIMULATION_STEP)
        self.assertTrue(all(c.speed == 0 for c in world.creatures))

    def test_greedy_turns_toward_nearest_detected_food_with_shared_turn_limit(self):
        for direction in (-1, 1):
            world = World(seed=42, controller="greedy", population_size=1, food_count=0, fixed_speed=60)
            c = world.creatures[0]
            c.x, c.y, c.heading = 500, 300, 0
            world.food = [Food(500, 300 + direction * 80), Food(500, 300 - direction * 120)]
            world.update(SIMULATION_STEP)
            self.assertAlmostEqual(c.turn_rate, direction * MAX_TURN_RATE)
            self.assertAlmostEqual(c.heading % math.tau, (direction * MAX_TURN_RATE * SIMULATION_STEP) % math.tau)

    def test_greedy_does_not_overshoot_small_angles_or_use_unseen_targets(self):
        world = World(seed=42, controller="greedy", population_size=1, food_count=0, fixed_speed=60)
        c = world.creatures[0]
        c.x, c.y, c.heading = 500, 300, 0
        angle = 0.001
        world.food = [Food(500 + 80 * math.cos(angle), 300 + 80 * math.sin(angle))]
        world.update(SIMULATION_STEP)
        self.assertAlmostEqual(c.heading, angle)
        world.food = [Food(800, 300)]
        c.turn_time_remaining = 1
        c.turn_rate = -0.4
        world.update(SIMULATION_STEP)
        self.assertEqual(c.turn_rate, -0.4)

    def test_greedy_can_reach_and_eat_a_visible_target(self):
        world = World(seed=42, controller="greedy", population_size=1, food_count=0, fixed_speed=60)
        c = world.creatures[0]
        c.x, c.y, c.heading, c.energy = 500, 300, 0, 50
        world.food = [Food(500, 380)]
        world.update(3)
        self.assertEqual(c.food_eaten, 1)

    def test_clusters_are_reproducible_clear_and_replenished_in_the_same_regions(self):
        a = World(seed=42, food_distribution="clustered", fixed_speed=60)
        b = World(seed=42, food_distribution="clustered", fixed_speed=60)
        self.assertEqual(initial_conditions_digest(a), initial_conditions_digest(b))
        self.assertEqual(a.food_cluster_centers, b.food_cluster_centers)
        self.assertEqual(len(a.food_cluster_centers), CLUSTER_COUNT)
        distances = [min(math.hypot(f.x - x, f.y - y) for x, y in a.food_cluster_centers) for f in a.food]
        self.assertLess(np.mean(distances), 80)
        for index, pellet in enumerate(a.food):
            self.assertTrue(0 < pellet.x < a.width and 0 < pellet.y < a.height)
            self.assertFalse(any(pellet.overlaps_circle(c.x, c.y, c.radius + 2) for c in a.creatures))
            self.assertFalse(any(pellet.overlaps_circle(f.x, f.y, f.radius + 2) for f in a.food[index + 1:]))
        centers = a.food_cluster_centers.copy()
        a.food = a.food[:10]
        a._resolve_food_collisions()
        self.assertEqual(len(a.food), 150)
        self.assertEqual(a.food_cluster_centers, centers)
        a._start_generation(2)
        self.assertNotEqual(a.food_cluster_centers, centers)

    def test_cli_exposes_greedy_clustered_fixed_speed_and_records_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "world.json"
            args = ["main.py", "--headless", "--frames", "1", "--controller", "greedy", "--fixed-speed", "60",
                    "--food-distribution", "clustered", "--report", str(output)]
            with patch("sys.argv", args), redirect_stdout(io.StringIO()):
                self.assertEqual(world_main(), 0)
            report = json.loads(output.read_text())
            self.assertEqual((report["controller"], report["fixed_speed"], report["food_distribution"]), ("greedy", 60, "clustered"))


class SpeedStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("world.create_population", side_effect=short_population):
            cls.report = run_study([11, 22], generations=2, repeats=2)

    def test_complete_matched_frozen_unseen_tests_and_exact_cohort_budget(self):
        r = self.report
        self.assertEqual(r["status"], "complete")
        self.assertEqual(r["protocol"]["planned_training_cohorts"], 4)
        self.assertEqual(r["protocol"]["planned_test_cohorts"], 36)
        for trial in r["trials"]:
            self.assertEqual(len(trial["tests"]), 6)
            for test in trial["tests"]:
                self.assertEqual(set(test["conditions"]), set(CONDITIONS))
                self.assertEqual(len({c["initial_conditions"] for c in test["conditions"].values()}), 1)
                for record in test["conditions"].values():
                    self.assertNotIn(record["initial_conditions"], trial["training_initial_conditions"])
                    self.assertEqual(record["genomes_sha256"], trial["genomes_sha256"])
                    self.assertFalse(record["report"]["evolution_enabled"])
                    self.assertAlmostEqual(record["report"]["generations"][0]["mean_speed"], 60)

    def test_repeat_averaging_keeps_lineages_as_the_independent_unit(self):
        r = deepcopy(self.report)
        for trial, outcomes in zip(r["trials"], ((2, 4), (6, 8))):
            tests = [t for t in trial["tests"] if t["environment"] == "uniform"]
            for test, outcome in zip(tests, outcomes):
                row = test["conditions"]["evolved"]["report"]["generations"][0]
                row["mean_food_eaten"] = outcome
                row["mean_fitness"] = row["mean_survival_seconds"] + outcome * 10
        result = analyze_results(r)["environments"]["uniform"]
        self.assertEqual(result["seed_values"]["evolved"]["mean_food_eaten"], [3, 7])
        self.assertEqual(result["contrasts"]["random"]["mean_food_eaten"]["n_pairs"], 2)
        self.assertNotIn("sign_test_p", result["contrasts"]["greedy"]["mean_fitness"])

    def test_corrupted_or_incomplete_studies_are_rejected(self):
        mutations = [
            lambda r: r["trials"].pop(),
            lambda r: r["trials"][0]["tests"].pop(),
            lambda r: r["trials"][0]["tests"][0]["conditions"].pop("greedy"),
            lambda r: r["trials"][0]["tests"][0].update(seed=0),
            lambda r: r["trials"][0]["training"].update(fixed_speed=None),
            lambda r: r["trials"][0]["tests"][0]["conditions"]["evolved"].update(genomes_sha256="bad"),
            lambda r: r["trials"][0]["tests"][0]["conditions"]["random"]["report"].update(fixed_speed=59),
            lambda r: r["trials"][0]["tests"][0]["conditions"]["random"]["report"].update(evolution_enabled=True),
            lambda r: r["trials"][0]["tests"][0]["conditions"]["random"]["report"]["generations"][0].update(mean_speed=59),
            lambda r: r["trials"][0]["tests"][0]["conditions"]["random"]["report"]["generations"][0].update(survival_rate=0.5),
        ]
        for mutate in mutations:
            r = deepcopy(self.report)
            mutate(r)
            with self.assertRaises(ValueError):
                analyze_results(r)

    def test_nine_primary_tests_apply_holm_and_require_matching_effect_intervals(self):
        rows = [{"sign_test_p": 0.001, "difference_ci95": [1, 2]} for _ in range(9)]
        classify_primary(rows)
        self.assertTrue(all(r["conclusion"] == "higher" for r in rows))
        for row in rows:
            self.assertAlmostEqual(row["holm_adjusted_p"], 0.009)
        rows[0].update(sign_test_p=0.5, difference_ci95=[1, 2])
        rows[1].update(difference_ci95=[-2, -1])
        rows[2].update(difference_ci95=[-1, 1])
        classify_primary(rows)
        self.assertEqual([r["conclusion"] for r in rows[:3]], ["inconclusive", "lower", "inconclusive"])

    def test_equal_count_averages_are_ties_despite_binary_rounding(self):
        left, right = (0.1 + 0.2) / 2, (0.11 + 0.19) / 2
        self.assertNotEqual(left, right)
        result = paired_metrics([left] * 16, [right] * 16, seed=42)
        self.assertEqual((result["wins"], result["losses"], result["ties"], result["sign_test_p"]), (0, 0, 16, 1))
        ordinary = paired_metrics([1, 2], [0, 3], seed=42)
        self.assertEqual((ordinary["wins"], ordinary["losses"], ordinary["ties"]), (1, 1, 0))

    def test_parallel_reproducibility_and_running_checkpoints(self):
        checkpoints = []
        with patch("world.create_population", side_effect=short_population), patch("experiment_speed.ProcessPoolExecutor", ThreadPoolExecutor):
            r = run_study([11, 22], generations=2, repeats=2, workers=2,
                          checkpoint=lambda r: checkpoints.append(deepcopy(r)))
        self.assertEqual(r, self.report)
        self.assertEqual([r["status"] for r in checkpoints], ["running", "running", "running", "complete"])
        with self.assertRaises(ValueError):
            build_speed_figure(checkpoints[-2])

    def test_numeric_model_roundtrip_reuse_and_training_protocol_guard(self):
        with tempfile.TemporaryDirectory() as directory, patch("world.create_population", side_effect=short_population):
            original = run_study([11, 22], generations=2, repeats=1, models_dir=directory)
            with patch("experiment_speed.train_lineage", side_effect=AssertionError("Must not retrain")):
                reused = run_study([11, 22], generations=2, repeats=1, models_dir=directory, reuse=True)
            self.assertEqual(original["trials"], reused["trials"])
            self.assertEqual(original["analysis"], reused["analysis"])
            path = Path(directory) / "seed-11.npz"
            training, starts, bank = load_model(path, 11, 2)
            before = bank_digest(bank)
            bank[1].input_weights[0, 0] += 1
            self.assertNotEqual(bank_digest(bank), before)
            self.assertEqual(bank_digest(load_model(path, 11, 2)[2]), before)
            for seed, generations in ((22, 2), (11, 3)):
                with self.assertRaises(ValueError):
                    load_model(path, seed, generations)
            training["fixed_speed"] = None
            save_checkpoint(path, training, starts, {"evolved": bank})
            with self.assertRaises(ValueError):
                load_model(path, 11, 2)

    def test_plot_has_one_point_per_lineage_and_exports_three_formats(self):
        figure = build_speed_figure(self.report)
        self.assertEqual(len(figure.axes), 9)
        for axis in figure.axes:
            self.assertEqual([len(c.get_offsets()) for c in axis.collections], [2, 1, 2, 1, 2, 1])
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("png", "svg", "pdf"):
                output = Path(directory) / f"plot.{suffix}"
                save_speed_plot(self.report, output)
                self.assertGreater(output.stat().st_size, 1000)

    def test_cli_generates_complete_report_and_reusable_models(self):
        with tempfile.TemporaryDirectory() as directory, patch("world.create_population", side_effect=short_population):
            output = Path(directory) / "report.json"
            args = ["experiment_speed.py", "--seeds", "11", "22", "--generations", "2", "--repeats", "1",
                    "--output", str(output), "--models-dir", directory]
            with patch("sys.argv", args), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            self.assertEqual(json.loads(output.read_text())["status"], "complete")
            self.assertTrue((Path(directory) / "seed-11.npz").exists())

    def test_invalid_budgets_are_rejected_before_training(self):
        for kwargs in ({"seeds": [1]}, {"seeds": [1, 1]}, {"generations": 1}, {"repeats": 0}, {"workers": 0}, {"reuse": True}):
            with self.assertRaises(ValueError):
                run_study(**kwargs)


if __name__ == "__main__":
    unittest.main()
