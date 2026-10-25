"""Survival checkpoint accounting and exported evolution charts."""

from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError
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
from PIL import Image

from creature import Creature, create_population
from main import run
from plot_evolution import build_figure, main, save_evolution_plot
from simulation import EvolutionSimulation
from world import SIMULATION_STEP, World


def sample_report() -> dict:
    return {
        "format_version": 2, "seed": 42, "controller": "neural",
        "generations": [
            {"generation": 1, "population_size": 100, "mean_fitness": 10,
             "best_fitness": 30, "mean_food_eaten": 2,
             "survival_checkpoint_seconds": 60, "survivors_at_checkpoint": 25,
             "survival_rate": 0.25},
            {"generation": 3, "population_size": 40, "mean_fitness": 40,
             "best_fitness": 60, "mean_food_eaten": 4,
             "survival_checkpoint_seconds": 60, "survivors_at_checkpoint": 30,
             "survival_rate": 0.75},
        ],
    }


def short_population(*args):
    population = create_population(*args)
    for creature in population:
        creature.lifespan = 0.005
    return population


class SurvivalRateTests(unittest.TestCase):
    def test_checkpoint_includes_exact_age_and_uses_whole_population(self) -> None:
        world = World(seed=42, food_count=0)
        world.creatures = [
            Creature(index, 100 * index, 100, 6, (101, 219, 181), 0, 0,
                     age=age, lifespan=lifespan)
            for index, (age, lifespan) in enumerate(
                ((59.99, 60), (0, 0.005), (75, 75.005), (59.98, 59.985)), start=1
            )
        ]
        world.update(SIMULATION_STEP)
        stats = world.generation_stats[0]
        self.assertEqual(stats.population_size, 4)
        self.assertEqual(len(world.final_evaluation.selected_ids), 1)
        self.assertEqual(stats.survival_checkpoint_seconds, 60)
        self.assertEqual(stats.survivors_at_checkpoint, 2)
        self.assertEqual(stats.survival_rate, 0.5)
        with self.assertRaises(FrozenInstanceError):
            stats.survivors_at_checkpoint = 4
        report = EvolutionSimulation(world).report()
        self.assertEqual(report["format_version"], 2)
        self.assertEqual(report["generations"][0]["survival_rate"], 0.5)
        self.assertEqual(report["generations"][0]["survivors_at_checkpoint"], 2)

    def test_partial_generations_are_not_reported_as_zero_survival(self) -> None:
        world = World(seed=42, food_count=0)
        world.update(SIMULATION_STEP)
        self.assertEqual(world.generation_stats, [])
        self.assertEqual(EvolutionSimulation(world).report()["generations"], [])

    def test_zero_survival_is_recorded_and_reset_clears_it(self) -> None:
        world = World(seed=42, food_count=0)
        for creature in world.creatures:
            creature.lifespan = 0.005
        world.update(SIMULATION_STEP)
        self.assertEqual(world.generation_stats[0].survival_rate, 0)
        world.regenerate_population(42)
        self.assertEqual(world.generation_stats, [])


class FigureTests(unittest.TestCase):
    def figure(self, report):
        figure = build_figure(report)
        self.addCleanup(figure.clear)
        return figure

    def test_curves_use_recorded_values_and_actual_generation_numbers(self) -> None:
        report = sample_report()
        before = deepcopy(report)
        fitness, survival, food = self.figure(report).axes
        np.testing.assert_array_equal(fitness.lines[0].get_xdata(), [1, 3])
        np.testing.assert_array_equal(fitness.lines[0].get_ydata(), [10, 40])
        np.testing.assert_array_equal(fitness.lines[1].get_ydata(), [30, 60])
        np.testing.assert_array_equal(survival.lines[0].get_ydata(), [25, 75])
        np.testing.assert_array_equal(food.lines[0].get_ydata(), [2, 4])
        self.assertEqual(survival.get_ylim(), (0, 100))
        self.assertIn("60 seconds", survival.get_title())
        self.assertIn("Mean pellets", food.get_ylabel())
        self.assertEqual(report, before)

    def test_zero_and_full_survival_are_visible_on_fixed_percentage_axis(self) -> None:
        report = sample_report()
        for row, count in zip(report["generations"], (0, 40)):
            row["survivors_at_checkpoint"] = count
            row["survival_rate"] = count / row["population_size"]
        survival = self.figure(report).axes[1]
        np.testing.assert_array_equal(survival.lines[0].get_ydata(), [0, 100])
        self.assertEqual(survival.get_ylim(), (0, 100))

    def test_old_reports_show_missing_survival_without_inferring_it_from_mean_age(self) -> None:
        report = sample_report()
        report["format_version"] = 1
        for row in report["generations"]:
            for key in ("survivors_at_checkpoint", "survival_checkpoint_seconds", "survival_rate"):
                row.pop(key)
            row["mean_survival_seconds"] = 80
        survival = self.figure(report).axes[1]
        self.assertTrue(np.all(np.isnan(survival.lines[0].get_ydata())))
        self.assertIn("not recorded", survival.texts[0].get_text())

    def test_missing_generation_measurement_creates_gap_in_survival_curve(self) -> None:
        report = sample_report()
        report["generations"][1]["survivors_at_checkpoint"] = None
        survival = self.figure(report).axes[1].lines[0].get_ydata()
        self.assertEqual(survival[0], 25)
        self.assertTrue(math.isnan(survival[1]))

    def test_one_generation_and_zero_food_are_valid(self) -> None:
        report = sample_report()
        report["generations"] = report["generations"][:1]
        report["generations"][0]["mean_food_eaten"] = 0
        figure = self.figure(report)
        self.assertEqual(len(figure.axes), 3)
        self.assertEqual(list(figure.axes[2].lines[0].get_ydata()), [0])
        figure.canvas.draw()

    def test_invalid_observations_are_rejected_before_rendering(self) -> None:
        cases = [
            ("generation", 0), ("generation", 3),
            ("mean_fitness", math.nan), ("best_fitness", math.inf),
            ("mean_food_eaten", -1), ("mean_food_eaten", None),
            ("population_size", 0), ("population_size", 1.5),
            ("survivors_at_checkpoint", -1), ("survivors_at_checkpoint", 101),
            ("survivors_at_checkpoint", 25.5), ("survival_checkpoint_seconds", 0),
            ("survival_checkpoint_seconds", 30), ("survival_rate", 0.99),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                report = sample_report()
                report["generations"][0][key] = value
                with self.assertRaises(ValueError):
                    build_figure(report)
        with self.assertRaisesRegex(ValueError, "at least one generation"):
            build_figure({"generations": []})

    def test_png_svg_and_pdf_exports_are_headless_and_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for extension, signature in (("png", b"\x89PNG"), ("svg", b"<?xml"), ("pdf", b"%PDF")):
                output = Path(directory) / "plots" / f"evolution.{extension}"
                save_evolution_plot(sample_report(), output)
                self.assertTrue(output.read_bytes().startswith(signature))
            with Image.open(Path(directory) / "plots" / "evolution.png") as image:
                self.assertEqual(image.size, (2240, 768))
                image.verify()
            with self.assertRaises(ValueError):
                save_evolution_plot(sample_report(), Path(directory) / "bad.txt")

    def test_plotting_does_not_change_world_or_future_offspring(self) -> None:
        first, second = World(seed=42), World(seed=42)
        for world in (first, second):
            for creature in world.creatures:
                creature.lifespan = 0.005
            world.update(SIMULATION_STEP)
        self.figure(EvolutionSimulation(first).report()).canvas.draw()
        for world in (first, second):
            self.assertTrue(world.advance_generation())
            world.update(SIMULATION_STEP)
        self.assertEqual([asdict(c) for c in first.creatures], [asdict(c) for c in second.creatures])
        self.assertEqual(first.food, second.food)
        self.assertEqual(first.generation_stats, second.generation_stats)


class PlotCommandTests(unittest.TestCase):
    def test_existing_report_cli_creates_default_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "run.json"
            report.write_text(json.dumps(sample_report()))
            with patch("sys.argv", ["plot_evolution.py", str(report)]), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            self.assertTrue(report.with_suffix(".png").is_file())

    def test_bad_report_exits_with_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "run.json"
            for content in ("not json", "[]", '{"generations": []}'):
                report.write_text(content)
                with patch("sys.argv", ["plot_evolution.py", str(report)]), patch("sys.stderr", new_callable=io.StringIO):
                    with self.assertRaises(SystemExit) as error:
                        main()
                    self.assertEqual(error.exception.code, 2)
            self.assertFalse(report.with_suffix(".png").exists())

    def test_simulation_exports_matching_report_and_chart_on_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report, plot = Path(directory) / "run.json", Path(directory) / "run.png"
            with patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy"}), patch("world.create_population", side_effect=short_population), redirect_stdout(io.StringIO()):
                self.assertEqual(run(headless=True, generations=2, speed=20,
                                     seed=42, report=report, plot=plot), 0)
            data = json.loads(report.read_text())
            self.assertEqual(data["completed_generations"], 2)
            self.assertTrue(all(row["survival_rate"] == 0 for row in data["generations"]))
            self.assertTrue(plot.is_file())

    def test_no_completed_generation_skips_plot_with_explanation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plot = Path(directory) / "run.png"
            with patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy"}), redirect_stdout(io.StringIO()) as output:
                run(headless=True, frames=1, seed=42, plot=plot)
            self.assertIn("no completed generations", output.getvalue())
            self.assertFalse(plot.exists())


if __name__ == "__main__":
    unittest.main()
