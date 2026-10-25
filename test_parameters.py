"""Configurable populations and controlled exploratory parameter studies."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict
import io
import json
import math
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from brain import NeuralNetwork
from compare_creatures import complete_generation, initial_conditions_digest
from creature import create_population
from experiment_parameters import STANDARD, Setting, analyze_sweep, describe_pairs, make_settings, main, run_seed, run_sweep
from main import main as world_main
from plot_parameters import build_parameter_figure, save_parameter_plot
from simulation import EvolutionSimulation
from world import SIMULATION_STEP, World


def short_population(*args):
    creatures = create_population(*args)
    for creature in creatures:
        creature.lifespan = 0.005
    return creatures


class PopulationParameterTests(unittest.TestCase):
    def test_population_sizes_have_unique_ids_nonoverlapping_bodies_and_independent_brains(self):
        for size in (1, 7, 50, 150):
            with self.subTest(size=size):
                creatures = create_population(1000, 600, random.Random(42), size)
                self.assertEqual([c.creature_id for c in creatures], list(range(1, size + 1)))
                self.assertEqual(len({id(c.brain) for c in creatures}), size)
                for index, creature in enumerate(creatures):
                    self.assertTrue(creature.radius <= creature.x <= 1000 - creature.radius)
                    self.assertTrue(creature.radius <= creature.y <= 600 - creature.radius)
                    self.assertEqual(creature.brain.parameter_count, 90)
                    for other in creatures[index + 1:]:
                        self.assertGreater(math.hypot(creature.x - other.x, creature.y - other.y),
                                           creature.radius + other.radius)

    def test_default_world_preserves_recorded_step13_start(self):
        report = json.loads((Path(__file__).parent / "results/step13-comparison.json").read_text())
        trial = report["trials"][0]
        expected = trial["conditions"]["evolved"]["training_initial_conditions"][0]
        self.assertEqual(initial_conditions_digest(World(seed=trial["seed"])), expected)

    def test_reproduction_and_restart_preserve_size_and_parameters(self):
        with patch("world.create_population", side_effect=short_population):
            for size in (1, 7, 50, 150):
                with self.subTest(size=size):
                    world = World(seed=42, population_size=size, food_count=75, mutation_rate=0)
                    initial = [asdict(c) for c in world.creatures]
                    complete_generation(EvolutionSimulation(world, auto_advance=False))
                    selected = world.final_evaluation.selected_ids
                    self.assertEqual(len(selected), math.ceil(size * 0.2))
                    self.assertTrue(world.advance_generation())
                    self.assertEqual(len(world.creatures), size)
                    self.assertTrue(all(c.parent_id in selected and c.mutation_count == 0 for c in world.creatures))
                    self.assertTrue(all(c.age == 0 and c.food_eaten == 0 and c.energy == 100 for c in world.creatures))
                    world.regenerate_population(42)
                    self.assertEqual([asdict(c) for c in world.creatures], initial)
                    self.assertEqual(len(world.food), 75)
                    self.assertEqual(world.mutation_rate, 0)

    def test_survival_rate_uses_configured_population_denominator(self):
        world = World(seed=42, population_size=7, food_count=0)
        for index, creature in enumerate(world.creatures):
            creature.age = 60 if index < 3 else 0
            creature.lifespan = creature.age + 0.005
        world.update(SIMULATION_STEP)
        self.assertEqual(world.generation_stats[0].survivors_at_checkpoint, 3)
        self.assertEqual(world.generation_stats[0].survival_rate, 3 / 7)
        self.assertEqual(EvolutionSimulation(world).report()["population_size"], 7)

    def test_invalid_population_and_food_inputs_fail_clearly(self):
        for size in (0, -1, 2.5, True):
            with self.subTest(size=size), self.assertRaises(ValueError):
                World(population_size=size)
            with self.assertRaises(ValueError):
                create_population(1000, 600, random.Random(42), size)
        for food_count in (-1, 1.5, True):
            with self.subTest(food_count=food_count), self.assertRaises(ValueError):
                World(food_count=food_count)
        with self.assertRaisesRegex(ValueError, "too crowded"):
            create_population(35, 35, random.Random(42), 50)

    def test_world_cli_records_custom_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "world.json"
            argv = ["main.py", "--headless", "--frames", "1", "--population", "7",
                    "--food-count", "0", "--mutation-rate", "0.3", "--mutation-scale", "0.2", "--report", str(output)]
            with patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy"}), patch("sys.argv", argv), redirect_stdout(io.StringIO()):
                self.assertEqual(world_main(), 0)
            report = json.loads(output.read_text())
            self.assertEqual((report["population_size"], report["food_count"], report["mutation_rate"], report["mutation_scale"]), (7, 0, 0.3, 0.2))

    def test_world_cli_rejects_invalid_parameter_values(self):
        for option, value in (("--population", "0"), ("--food-count", "-1"),
                              ("--mutation-rate", "1.1"), ("--mutation-rate", "nan"),
                              ("--mutation-scale", "-0.1")):
            with self.subTest(option=option, value=value), patch("sys.argv", ["main.py", option, value]), patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as error:
                    world_main()
                self.assertEqual(error.exception.code, 2)


class ParameterStudyTests(unittest.TestCase):
    def setUp(self):
        spawning = patch("world.create_population", side_effect=short_population)
        spawning.start()
        self.addCleanup(spawning.stop)
        self.settings = [STANDARD, Setting(0), Setting(0.3), Setting(population_size=7), Setting(food_count=0)]

    def test_default_design_changes_one_factor_around_fixed_standard(self):
        settings = make_settings()
        self.assertEqual(len(settings), 7)
        self.assertEqual(settings[0], STANDARD)
        for setting in settings:
            changed = sum(getattr(setting, key) != getattr(STANDARD, key)
                          for key in ("mutation_rate", "population_size", "food_count"))
            self.assertLessEqual(changed, 1)
        self.assertEqual({s.mutation_rate for s in settings}, {0, 0.1, 0.3})
        self.assertEqual({s.population_size for s in settings}, {50, 100, 150})
        self.assertEqual({s.food_count for s in settings}, {75, 150, 225})

    def test_setting_keys_preserve_precision_and_normalize_zero(self):
        self.assertNotEqual(Setting(0.100000001).key, Setting(0.100000002).key)
        self.assertEqual(Setting(0).key, Setting(-0.0).key)
        for changes in ({"mutation_rate": math.nan}, {"mutation_rate": -0.1},
                        {"population_size": 0}, {"food_count": -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Setting(**changes)

    def test_validation_is_fresh_matched_and_random_controls_are_reused(self):
        result = run_seed(11, self.settings, 2)
        self.assertEqual(len(result["settings"]), 5)
        self.assertEqual(len(result["random_controls"]), 3)
        for setting in self.settings:
            record = result["settings"][setting.key]
            control = result["random_controls"][setting.ecology_key]
            self.assertEqual(record["training"]["completed_generations"], 2)
            self.assertEqual(record["validation"]["completed_generations"], 1)
            self.assertEqual(record["validation"]["population_size"], setting.population_size)
            self.assertEqual(record["validation"]["food_count"], setting.food_count)
            self.assertEqual(record["validation_initial_conditions"], control["initial_conditions"])
            self.assertNotIn(record["validation_initial_conditions"], record["training_initial_conditions"])
            self.assertFalse(record["validation"]["evolution_enabled"])
            self.assertEqual(control["validation"]["controller"], "random")
        standard = result["settings"][STANDARD.key]
        for setting in self.settings[:3]:
            record = result["settings"][setting.key]
            self.assertEqual(record["training_initial_conditions"], standard["training_initial_conditions"])
        self.assertEqual(result["settings"][Setting(food_count=0).key]["founder_genomes_sha256"], standard["founder_genomes_sha256"])

    def test_validation_detects_weight_updates_and_never_completes_bad_run(self):
        forward = NeuralNetwork.forward
        def changing_forward(brain, sensors):
            result = forward(brain, sensors)
            brain.output_bias[0] += 0.001
            return result
        snapshots = []
        with patch.object(NeuralNetwork, "forward", changing_forward), self.assertRaisesRegex(RuntimeError, "frozen training weights"):
            run_sweep([11, 22], settings=[STANDARD], generations=2,
                      checkpoint=lambda report: snapshots.append(deepcopy(report)))
        self.assertEqual([report["status"] for report in snapshots], ["running"])

    def test_serial_and_parallel_runs_have_identical_seed_order_and_results(self):
        settings = [STANDARD, Setting(population_size=7)]
        serial = run_sweep([22, 11], settings=settings, generations=2)
        with patch("experiment_parameters.ProcessPoolExecutor", ThreadPoolExecutor):
            parallel = run_sweep([22, 11], settings=settings, generations=2, workers=2)
        self.assertEqual(serial, parallel)
        self.assertEqual([run["seed"] for run in serial["runs"]], [22, 11])
        self.assertEqual(serial["protocol"]["planned_unique_cohorts"], 16)

    def test_analysis_resamples_seed_pairs_and_has_no_significance_or_winner_claim(self):
        summary = describe_pairs([103, 310], [100, 300], "test")
        self.assertEqual(summary["n_seeds"], 2)
        self.assertEqual(summary["mean_difference"], 6.5)
        self.assertEqual(summary["difference_ci95"], [3, 10])
        self.assertNotIn("sign_test_p", summary)
        report = run_sweep([11, 22], settings=self.settings, generations=2)
        self.assertNotIn("best_setting", report)
        baseline = report["summary"][STANDARD.key]["metrics"]["mean_fitness"]
        self.assertEqual(baseline["change_from_standard"]["difference_ci95"], [0, 0])
        self.assertEqual(baseline["advantage_change_from_standard"]["difference_ci95"], [0, 0])
        self.assertEqual(report["summary"], analyze_sweep(report))
        report["runs"][0]["settings"][STANDARD.key]["training"]["completed_generations"] = 0
        with self.assertRaises(ValueError):
            analyze_sweep(report)

    def test_missing_planned_seeds_or_settings_prevent_analysis(self):
        report = run_sweep([11, 22], settings=self.settings, generations=2)
        wrong_size = deepcopy(report)
        wrong_size["runs"][0]["settings"][Setting(population_size=7).key]["validation"]["generations"][0]["population_size"] = 100
        with self.assertRaises(ValueError):
            analyze_sweep(wrong_size)
        missing = deepcopy(report)
        missing["runs"].pop()
        with self.assertRaises(ValueError):
            analyze_sweep(missing)
        report["runs"][0]["settings"].pop(STANDARD.key)
        with self.assertRaises(ValueError):
            analyze_sweep(report)

    def test_invalid_studies_fail_before_starting_workers(self):
        for changes in ({"seeds": [11]}, {"seeds": [11, 11]}, {"generations": 1},
                        {"workers": 0}, {"settings": [Setting(0)]},
                        {"settings": [STANDARD, Setting(0, 50, 75)]}):
            kwargs = dict(seeds=[11, 22], settings=self.settings, generations=2)
            kwargs.update(changes)
            with self.subTest(changes=changes), patch("experiment_parameters.run_seed") as worker:
                with self.assertRaises(ValueError):
                    run_sweep(**kwargs)
                worker.assert_not_called()

    def test_completed_plot_contains_all_three_parameter_axes_and_real_probabilities(self):
        report = run_sweep([11, 22], settings=self.settings, generations=2)
        figure = build_parameter_figure(report)
        self.addCleanup(figure.clear)
        self.assertEqual(len(figure.axes), 6)
        self.assertIn("Mutation", figure.axes[0].get_title())
        self.assertEqual(list(figure.axes[0].lines[0].get_xdata()), [0, 0.1, 0.3])
        self.assertIn("Population", figure.axes[1].get_title())
        self.assertIn("difficulty", figure.axes[2].get_title())
        figure.canvas.draw()
        report["status"] = "running"
        with self.assertRaises(ValueError):
            build_parameter_figure(report)

    def test_plot_exports_and_study_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            output, plot = Path(directory) / "study.json", Path(directory) / "study.png"
            argv = ["experiment_parameters.py", "--seeds", "11", "22", "--generations", "2",
                    "--mutation-rates", "0.1", "--populations", "7", "--food-counts", "150",
                    "--output", str(output), "--plot", str(plot)]
            with patch("sys.argv", argv), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            report = json.loads(output.read_text())
            self.assertEqual(report["status"], "complete")
            self.assertEqual(len(report["protocol"]["settings"]), 2)
            self.assertTrue(plot.read_bytes().startswith(b"\x89PNG"))
            for extension, signature in (("svg", b"<?xml"), ("pdf", b"%PDF")):
                path = Path(directory) / f"study.{extension}"
                save_parameter_plot(report, path)
                self.assertTrue(path.read_bytes().startswith(signature))


if __name__ == "__main__":
    unittest.main()
