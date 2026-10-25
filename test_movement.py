"""Checks for movement distances, reflections, and simulation timing."""

from dataclasses import asdict
import math
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from creature import Creature
from world import SIMULATION_STEP, World


def make_creature(**changes: float) -> Creature:
    properties = dict(
        creature_id=1, x=50.0, y=40.0, radius=6,
        color=(101, 219, 181), heading=0.0, speed=40.0,
    )
    properties.update(changes)
    return Creature(**properties)


def population_state(world: World) -> list[dict]:
    return [asdict(creature) for creature in world.creatures]


class CreatureMovementTests(unittest.TestCase):
    def assert_heading(self, creature: Creature, expected: float) -> None:
        difference = (creature.heading - expected + math.pi) % math.tau - math.pi
        self.assertAlmostEqual(difference, 0.0)

    def test_distance_uses_speed_and_elapsed_seconds(self) -> None:
        creature = make_creature()
        creature.move(0.25, 100, 80)
        self.assertAlmostEqual(creature.x, 60.0)
        self.assertAlmostEqual(creature.y, 40.0)

    def test_rotation_changes_direction_and_wraps(self) -> None:
        creature = make_creature()
        creature.rotate(math.pi / 2)
        creature.move(0.25, 100, 80)
        self.assertAlmostEqual(creature.x, 50.0)
        self.assertAlmostEqual(creature.y, 50.0)
        creature.rotate(3 * math.tau)
        self.assert_heading(creature, math.pi / 2)
        creature.rotate(-math.pi)
        self.assert_heading(creature, 3 * math.pi / 2)

    def test_all_four_walls_preserve_excess_travel(self) -> None:
        cases = [
            (7.0, 40.0, math.pi, 9.0, 40.0, 0.0),
            (93.0, 40.0, 0.0, 91.0, 40.0, math.pi),
            (50.0, 7.0, 3 * math.pi / 2, 50.0, 9.0, math.pi / 2),
            (50.0, 73.0, math.pi / 2, 50.0, 71.0, 3 * math.pi / 2),
        ]
        for x, y, heading, expected_x, expected_y, expected_heading in cases:
            with self.subTest(heading=heading):
                creature = make_creature(x=x, y=y, heading=heading)
                creature.move(0.1, 100, 80)
                self.assertAlmostEqual(creature.x, expected_x)
                self.assertAlmostEqual(creature.y, expected_y)
                self.assert_heading(creature, expected_heading)

    def test_corner_reflects_both_components(self) -> None:
        creature = make_creature(x=93.0, y=73.0, heading=math.pi / 4, speed=40 * math.sqrt(2))
        creature.move(0.1, 100, 80)
        self.assertAlmostEqual(creature.x, 91.0)
        self.assertAlmostEqual(creature.y, 71.0)
        self.assert_heading(creature, 5 * math.pi / 4)

    def test_multiple_wall_crossings_in_one_move(self) -> None:
        creature = make_creature()
        creature.move(50.0, 100, 80)
        self.assertAlmostEqual(creature.x, 74.0)
        self.assertAlmostEqual(creature.y, 40.0)
        self.assert_heading(creature, math.pi)

    def test_exact_wall_arrival_faces_inward(self) -> None:
        creature = make_creature(x=90.0)
        creature.move(0.1, 100, 80)
        self.assertAlmostEqual(creature.x, 94.0)
        self.assert_heading(creature, math.pi)
        creature.move(0.1, 100, 80)
        self.assertAlmostEqual(creature.x, 90.0)

    def test_zero_and_invalid_time(self) -> None:
        creature = make_creature()
        before = asdict(creature)
        creature.move(0.0, 100, 80)
        self.assertEqual(asdict(creature), before)
        for dt in (-1.0, math.inf, math.nan):
            with self.subTest(dt=dt), self.assertRaises(ValueError):
                creature.move(dt, 100, 80)


class WorldMovementTests(unittest.TestCase):
    def test_same_seed_and_simulation_time_match_at_different_frame_rates(self) -> None:
        states = []
        for fps in (30, 60, 144):
            world = World(seed=42, food_count=0)
            for _ in range(fps * 2):
                world.update(1.0 / fps)
            self.assertAlmostEqual(world.elapsed_time, 2.0)
            states.append(population_state(world))
        self.assertEqual(states[0], states[1])
        self.assertEqual(states[0], states[2])

    def test_pause_freezes_motion_and_simulation_clock(self) -> None:
        world = World(seed=42, food_count=0)
        world.update(0.5)
        before = population_state(world)
        before_time = world.elapsed_time
        world.paused = True
        world.update(10.0)
        self.assertEqual(population_state(world), before)
        self.assertEqual(world.elapsed_time, before_time)
        world.paused = False
        world.update(SIMULATION_STEP)
        self.assertNotEqual(population_state(world), before)

    def test_long_run_stays_inside_walls_as_energy_depletes(self) -> None:
        world = World(seed=42, food_count=0)
        initial = population_state(world)
        for _ in range(1200):
            world.update(SIMULATION_STEP)
            for creature in world.creatures:
                self.assertTrue(creature.radius <= creature.x <= world.width - creature.radius)
                self.assertTrue(creature.radius <= creature.y <= world.height - creature.radius)
                self.assertTrue(0 <= creature.heading < math.tau)
        self.assertNotEqual(population_state(world), initial)
        self.assertEqual(len(world.creatures) + len(world.dead_creatures), 100)
        self.assertGreater(len(world.dead_creatures), 0)
        self.assertTrue(all(0 < creature.energy < 100.0 for creature in world.creatures))
        self.assertTrue(all(creature.death_cause == "starvation" for creature in world.dead_creatures))

    def test_regeneration_resets_clock_and_reproduces_steering(self) -> None:
        world = World(seed=42, food_count=0)
        world.update(1.0)
        first_run = population_state(world)
        world.paused = True
        world.regenerate_population(42)
        self.assertTrue(world.paused)
        self.assertEqual(world.elapsed_time, 0.0)
        world.paused = False
        world.update(1.0)
        self.assertEqual(population_state(world), first_run)


if __name__ == "__main__":
    unittest.main()
