"""Food distance, relative direction, range limits, and sensory integration."""

from dataclasses import FrozenInstanceError, asdict
import math
import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np
import pygame

from brain import NeuralNetwork
from food import Food
from perception import VISION_RANGE, sense_food
from world import SIMULATION_STEP, World


class FoodPerceptionTests(unittest.TestCase):
    def test_distance_and_direction_match_a_three_four_five_triangle(self) -> None:
        reading = sense_food(0, 0, 0, np.array([[3.0, 4.0]]))
        self.assertTrue(reading.visible)
        self.assertEqual(reading.target_position, (3.0, 4.0))
        self.assertEqual(reading.distance, 5.0)
        self.assertAlmostEqual(reading.direction, math.atan2(4.0, 3.0))
        self.assertAlmostEqual(reading.proximity, 1.0 - 5.0 / VISION_RANGE)

    def test_relative_direction_covers_ahead_right_left_and_behind(self) -> None:
        cases = [
            ((80, 0), 0.0), ((0, 80), math.pi / 2),
            ((0, -80), -math.pi / 2), ((-80, 0), -math.pi),
        ]
        for position, expected in cases:
            with self.subTest(position=position):
                reading = sense_food(0, 0, 0, np.array([position]))
                self.assertAlmostEqual(reading.direction, expected)
                self.assertEqual(reading.distance, 80.0)

    def test_heading_rotates_bearing_without_changing_distance(self) -> None:
        positions = np.array([[80.0, 0.0]])
        for heading in (math.pi / 2, 3 * math.tau + math.pi / 2):
            reading = sense_food(0, 0, heading, positions)
            self.assertAlmostEqual(reading.direction, -math.pi / 2)
            self.assertEqual(reading.distance, 80.0)

    def test_bearing_wraps_across_zero_and_the_back_direction(self) -> None:
        reading = sense_food(0, 0, math.tau - 0.1, np.array([[80.0, 0.0]]))
        self.assertAlmostEqual(reading.direction, 0.1)
        for y in (-0.001, 0.001):
            reading = sense_food(0, 0, 0, np.array([[-80.0, y]]))
            self.assertTrue(-math.pi <= reading.direction < math.pi)
            self.assertAlmostEqual(abs(reading.direction), math.pi, places=4)

    def test_range_is_inclusive_and_visibility_distinguishes_its_edge(self) -> None:
        edge = sense_food(0, 0, 0, np.array([[VISION_RANGE, 0.0]]))
        outside = sense_food(0, 0, 0, np.array([[math.nextafter(VISION_RANGE, math.inf), 0.0]]))
        self.assertEqual(edge.neural_signals, (0.0, 0.0, 1.0))
        self.assertEqual(outside.neural_signals, (0.0, 0.0, 0.0))
        self.assertIsNone(outside.distance)
        self.assertIsNone(outside.direction)

    def test_coincident_food_has_finite_neutral_direction(self) -> None:
        reading = sense_food(10, 20, 1.23, np.array([[10.0, 20.0]]))
        self.assertEqual(reading.distance, 0.0)
        self.assertEqual(reading.direction, 0.0)
        self.assertEqual(reading.neural_signals, (1.0, 0.0, 1.0))

    def test_nearest_target_and_visible_count_ignore_distant_food(self) -> None:
        reading = sense_food(0, 0, 0, np.array([[80, 0], [20, 0], [200, 0]]))
        self.assertEqual(reading.target_position, (20.0, 0.0))
        self.assertEqual(reading.nearby_count, 2)

    def test_equal_distance_targets_keep_their_list_order(self) -> None:
        reading = sense_food(0, 0, 0, np.array([[80, 0], [0, 80]]))
        self.assertEqual(reading.target_position, (80.0, 0.0))

    def test_empty_observation_masks_all_food_signals(self) -> None:
        reading = sense_food(0, 0, 0, np.empty((0, 2)))
        self.assertFalse(reading.visible)
        self.assertIsNone(reading.target_position)
        self.assertEqual(reading.nearby_count, 0)
        self.assertEqual(reading.neural_signals, (0.0, 0.0, 0.0))

    def test_closer_food_produces_stronger_proximity(self) -> None:
        near = sense_food(0, 0, 0, np.array([[40.0, 0.0]]))
        far = sense_food(0, 0, 0, np.array([[80.0, 0.0]]))
        self.assertGreater(near.proximity, far.proximity)
        self.assertEqual(near.direction, far.direction)
        short_range = sense_food(0, 0, 0, np.array([[80.0, 0.0]]), vision_range=40)
        self.assertFalse(short_range.visible)

    def test_observations_are_read_only_and_food_positions_are_unchanged(self) -> None:
        positions = np.array([[30.0, 40.0]])
        before = positions.copy()
        reading = sense_food(0, 0, 0, positions)
        np.testing.assert_array_equal(positions, before)
        with self.assertRaises(FrozenInstanceError):
            reading.distance = 10.0

    def test_invalid_ranges_positions_and_poses_are_rejected(self) -> None:
        for vision_range in (0.0, -1.0, math.inf, math.nan):
            with self.subTest(vision_range=vision_range), self.assertRaises(ValueError):
                sense_food(0, 0, 0, np.empty((0, 2)), vision_range=vision_range)
        for positions in (np.ones((2, 3)), np.array([1.0, 2.0]), np.array([[math.nan, 0]])):
            with self.assertRaises(ValueError):
                sense_food(0, 0, 0, positions)
        with self.assertRaises(ValueError):
            sense_food(0, 0, math.nan, np.empty((0, 2)))


class WorldPerceptionTests(unittest.TestCase):
    def test_the_brain_receives_proximity_bearing_and_visibility(self) -> None:
        world = World(seed=42, food_count=0)
        creature = world.creatures[0]
        creature.x, creature.y, creature.heading = 500.0, 300.0, 0.0
        world.creatures = [creature]
        world.food = [Food(500, 380)]
        reading = world.perceive_food(creature)
        creature.brain = Mock(spec=NeuralNetwork)
        creature.brain.forward.return_value = np.zeros(2)
        world.update(SIMULATION_STEP)
        creature.brain.forward.assert_called_once()
        sensors = creature.brain.forward.call_args.args[0]
        np.testing.assert_allclose(sensors[:3], reading.neural_signals)
        np.testing.assert_allclose(sensors[:3], [0.5, 0.5, 1.0])

    def test_removed_food_cannot_remain_a_sensed_target(self) -> None:
        world = World(seed=42, food_count=0)
        creature = world.creatures[0]
        creature.x, creature.y, creature.heading = 500.0, 300.0, 0.0
        world.food = [Food(540, 300), Food(580, 300)]
        self.assertEqual(world.perceive_food(creature).distance, 40.0)
        world.food.pop(0)
        self.assertEqual(world.perceive_food(creature).distance, 80.0)
        world.food.clear()
        self.assertFalse(world.perceive_food(creature).visible)

    def test_vision_overlay_does_not_change_brains_motion_or_food(self) -> None:
        shown = World(seed=42)
        hidden = World(seed=42)
        hidden.show_perception = False
        screen = pygame.Surface((1000, 600))
        for _ in range(60):
            for world in (shown, hidden):
                world.update(SIMULATION_STEP)
                world.draw(screen, (0, 0))
        self.assertEqual([asdict(creature) for creature in shown.creatures],
                         [asdict(creature) for creature in hidden.creatures])
        self.assertEqual(shown.food, hidden.food)
        self.assertEqual(shown.total_food_eaten, hidden.total_food_eaten)

    def test_reset_recreates_perception_and_preserves_overlay_preference(self) -> None:
        world = World(seed=42)
        initial = world.perceive_food(world.creatures[0])
        world.show_perception = False
        world.update(1.0)
        world.regenerate_population(42)
        self.assertEqual(world.perceive_food(world.creatures[0]), initial)
        self.assertFalse(world.show_perception)


if __name__ == "__main__":
    unittest.main()
