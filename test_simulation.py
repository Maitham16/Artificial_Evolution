"""Automatic cycles, behavioral observations, controls, and bounded runs."""

from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError, asdict
import io
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from creature import Creature, create_population
from food import Food
from main import handle_events, main, run
from simulation import EvolutionSimulation
from world import SIMULATION_STEP, World


def short_population(*args):
    creatures = create_population(*args)
    for creature in creatures:
        creature.lifespan = 0.05
    return creatures


class SimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spawning = patch("world.create_population", side_effect=short_population)
        self.spawning.start()
        self.addCleanup(self.spawning.stop)

    def test_automatic_cycles_stop_at_exact_limit_with_all_final_records(self) -> None:
        world = World(seed=42, food_count=0)
        simulation = EvolutionSimulation(world, generation_limit=3, speed=20)
        simulation.update(1.0)
        self.assertTrue(simulation.finished)
        self.assertEqual(world.generation, 3)
        self.assertEqual(len(world.generation_history), 3)
        self.assertEqual([row.generation for row in world.generation_stats], [1, 2, 3])
        self.assertTrue(all(len(result.ranking) == 100 for result in world.generation_history))
        self.assertTrue(all(len(result.selected_ids) == 20 for result in world.generation_history))
        self.assertEqual(len(world.dead_creatures), 100)
        self.assertEqual(world.creatures, [])
        self.assertAlmostEqual(simulation.total_simulated_seconds, 0.15)
        final = simulation.report()
        simulation.update(100.0)
        self.assertFalse(simulation.advance_generation())
        self.assertEqual(simulation.report(), final)

    def test_unused_frame_time_continues_into_next_generation(self) -> None:
        world = World(seed=42, food_count=0)
        simulation = EvolutionSimulation(world)
        simulation.update(5 * SIMULATION_STEP)
        self.assertEqual(len(world.generation_history), 1)
        self.assertEqual(world.generation, 2)
        self.assertAlmostEqual(world.elapsed_time, 2 * SIMULATION_STEP)
        self.assertAlmostEqual(simulation.total_simulated_seconds, 5 * SIMULATION_STEP)

    def test_frame_rates_and_speed_settings_produce_identical_evolution(self) -> None:
        states = []
        for fps, speed in ((30, 1), (60, 1), (144, 1), (60, 5), (60, 20)):
            world = World(seed=42, food_count=0)
            simulation = EvolutionSimulation(world, speed=speed)
            for _ in range(fps // 2):
                simulation.update(1 / (fps * speed))
            states.append((simulation.report(), [asdict(c) for c in world.dead_creatures],
                           [asdict(c) for c in world.creatures], world.food))
        for state in states[1:]:
            self.assertEqual(state, states[0])

    def test_manual_mode_waits_without_gaining_time_and_can_resume_automatic_cycles(self) -> None:
        world = World(seed=42, food_count=0)
        simulation = EvolutionSimulation(world, generation_limit=3, auto_advance=False)
        simulation.update(1.0)
        self.assertEqual(len(world.generation_history), 1)
        self.assertEqual(world.generation, 1)
        self.assertAlmostEqual(simulation.total_simulated_seconds, 0.05)
        before = simulation.report()
        simulation.update(1.0)
        self.assertEqual(simulation.report(), before)
        self.assertTrue(simulation.advance_generation())
        self.assertFalse(simulation.advance_generation())
        simulation.auto_advance = True
        simulation.update(1.0)
        self.assertTrue(simulation.finished)
        self.assertEqual(world.generation, 3)

    def test_pause_freezes_history_time_and_generation_transitions(self) -> None:
        world = World(seed=42, food_count=0)
        simulation = EvolutionSimulation(world, speed=20)
        world.paused = True
        before = simulation.report()
        simulation.update(10.0)
        self.assertEqual(simulation.report(), before)
        self.assertEqual(world.generation, 1)
        world.paused = False
        simulation.update(SIMULATION_STEP)
        world.paused = True
        before = simulation.report()
        simulation.update(10.0)
        self.assertEqual(simulation.report(), before)

    def test_restart_clears_history_and_time_while_preserving_settings(self) -> None:
        world = World(seed=42, food_count=0)
        original = [asdict(c) for c in world.creatures]
        simulation = EvolutionSimulation(world, generation_limit=2, speed=20)
        simulation.update(1.0)
        self.assertTrue(simulation.finished)
        world.paused, world.show_history = True, True
        simulation.auto_advance = False
        simulation.restart(42)
        self.assertEqual([asdict(c) for c in world.creatures], original)
        self.assertFalse(simulation.finished)
        self.assertEqual(world.generation_stats, [])
        self.assertEqual(simulation.total_simulated_seconds, 0)
        self.assertEqual(simulation.generation_limit, 2)
        self.assertEqual(simulation.speed, 20)
        self.assertFalse(simulation.auto_advance)
        self.assertTrue(world.paused)
        self.assertTrue(world.show_history)

    def test_invalid_limits_speeds_and_times_are_rejected(self) -> None:
        world = World(seed=42, food_count=0)
        for limit in (0, -1, 1.5, True):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                EvolutionSimulation(world, generation_limit=limit)
        with self.assertRaises(ValueError):
            EvolutionSimulation(world, speed=3)
        simulation = EvolutionSimulation(world, speed=20)
        for dt in (-1, math.inf, math.nan, 1e308):
            with self.subTest(dt=dt), self.assertRaises(ValueError):
                simulation.update(dt)

    def test_reports_exclude_partial_generations_and_are_independent_snapshots(self) -> None:
        simulation = EvolutionSimulation(World(seed=42, food_count=0))
        simulation.update(SIMULATION_STEP)
        self.assertEqual(simulation.report()["generations"], [])
        simulation.update(3 * SIMULATION_STEP)
        report = simulation.report()
        self.assertEqual(report["completed_generations"], 1)
        self.assertEqual(len(report["generations"]), 1)
        self.assertIsNone(report["generations"][0]["food_facing_fraction"])
        json.dumps(report, allow_nan=False)
        report["generations"][0]["mean_fitness"] = -1
        self.assertGreaterEqual(simulation.report()["generations"][0]["mean_fitness"], 0)


class ObservationTests(unittest.TestCase):
    def test_observations_use_actual_lifetime_and_do_not_reward_behavior_measurements(self) -> None:
        world = World(seed=42, food_count=0, controller="random")
        world.creatures = [
            Creature(1, 100, 100, 6, (101, 219, 181), 0, 20,
                     lifespan=0.005, food_eaten=1, turn_time_remaining=10),
            Creature(2, 100, 300, 6, (101, 219, 181), math.pi, 60,
                     lifespan=0.015, food_eaten=3, turn_time_remaining=10),
        ]
        world.food = [Food(150, 100), Food(150, 300)]
        world.update(SIMULATION_STEP)
        stats = world.generation_stats[0]
        self.assertEqual(stats.population_size, 2)
        self.assertAlmostEqual(stats.mean_food_eaten, 2)
        self.assertAlmostEqual(stats.mean_survival_seconds, 0.01)
        self.assertAlmostEqual(stats.mean_fitness, 20.01)
        self.assertAlmostEqual(stats.best_fitness, 30.015)
        self.assertAlmostEqual(stats.duration_seconds, SIMULATION_STEP)
        self.assertAlmostEqual(stats.mean_speed, 50)
        self.assertAlmostEqual(stats.food_visible_seconds, 0.02)
        self.assertAlmostEqual(stats.food_facing_seconds, 0.005)
        self.assertAlmostEqual(stats.food_facing_fraction, 0.25)
        with self.assertRaises(FrozenInstanceError):
            stats.mean_fitness = 1000
        world.update(1.0)
        self.assertEqual(world.generation_stats, [stats])

    def test_heading_measure_includes_boundary_and_distinguishes_missing_food(self) -> None:
        for bearing, expected in ((0, 1), (math.pi / 4, 1), (math.pi / 2, 0), (None, None)):
            with self.subTest(bearing=bearing):
                world = World(seed=42, food_count=0, controller="random")
                world.creatures = [Creature(1, 100, 100, 6, (101, 219, 181), 0, 40,
                                             lifespan=0.005, turn_time_remaining=10)]
                world.food = ([] if bearing is None else
                              [Food(100 + 50 * math.cos(bearing), 100 + 50 * math.sin(bearing))])
                world.update(SIMULATION_STEP)
                self.assertEqual(world.generation_stats[0].food_facing_fraction, expected)


class InterfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        pygame.display.init()
        pygame.display.set_mode((1, 1))
        self.addCleanup(pygame.quit)

    def press(self, key, world, simulation):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
        self.assertTrue(handle_events(world, simulation))

    def test_auto_speed_history_and_manual_controls(self) -> None:
        world = World(seed=42, food_count=0)
        simulation = EvolutionSimulation(world)
        self.press(pygame.K_a, world, simulation)
        self.assertFalse(simulation.auto_advance)
        for speed in (5, 20, 1):
            self.press(pygame.K_s, world, simulation)
            self.assertEqual(simulation.speed, speed)
        self.press(pygame.K_t, world, simulation)
        self.assertTrue(world.show_history)
        self.assertFalse(world.show_fitness)
        self.press(pygame.K_f, world, simulation)
        self.assertTrue(world.show_fitness)
        self.assertFalse(world.show_history)
        self.press(pygame.K_n, world, simulation)
        self.assertEqual(world.generation, 1)
        for c in world.creatures:
            c.lifespan = 0.005
        simulation.update(SIMULATION_STEP)
        self.press(pygame.K_n, world, simulation)
        self.assertEqual(world.generation, 2)
        self.press(pygame.K_r, world, simulation)
        self.assertEqual(world.generation, 1)
        self.assertEqual(world.generation_stats, [])
        self.assertEqual(simulation.total_simulated_seconds, 0)

    def test_history_panel_blocks_arena_selection(self) -> None:
        world = World(seed=42)
        simulation = EvolutionSimulation(world)
        selected = world.selected_creature
        world.show_history = True
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(0, 0)))
        handle_events(world, simulation)
        self.assertIs(world.selected_creature, selected)

    def test_headless_generation_limit_saves_report_and_final_history_view(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report, screenshot = Path(directory) / "run.json", Path(directory) / "run.png"
            with patch("world.create_population", side_effect=short_population), redirect_stdout(io.StringIO()):
                self.assertEqual(run(headless=True, generations=3, speed=20, seed=42,
                                     report=report, screenshot=screenshot), 0)
            data = json.loads(report.read_text())
            self.assertEqual(data["completed_generations"], 3)
            self.assertEqual([row["generation"] for row in data["generations"]], [1, 2, 3])
            self.assertGreater(screenshot.stat().st_size, 100)

    def test_frame_limit_can_stop_before_generation_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "run.json"
            with redirect_stdout(io.StringIO()):
                run(headless=True, frames=1, generations=10, seed=42, report=report)
            data = json.loads(report.read_text())
            self.assertEqual(data["completed_generations"], 0)
            self.assertAlmostEqual(data["total_simulated_seconds"], SIMULATION_STEP)

    def test_unbounded_or_manual_headless_cli_requires_frame_limit(self) -> None:
        for args in (("--headless",), ("--headless", "--manual", "--generations", "2"),
                     ("--headless", "--generations", "0")):
            with self.subTest(args=args), patch("sys.argv", ["main.py", *args]), patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as result:
                    main()
                self.assertEqual(result.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
