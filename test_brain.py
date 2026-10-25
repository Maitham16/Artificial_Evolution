"""Neural inference, local sensory inputs, and control of real creature motion."""

from dataclasses import asdict
import math
import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

from brain import MAX_TURN_RATE, VISION_RANGE, NeuralNetwork
from food import Food
from world import SIMULATION_STEP, World


def zero_brain(brain: NeuralNetwork) -> None:
    for parameter in brain.parameters:
        parameter.fill(0.0)


class NeuralNetworkTests(unittest.TestCase):
    def test_architecture_has_90_parameters_and_independent_arrays(self) -> None:
        rng = np.random.default_rng(42)
        first, second = NeuralNetwork(rng), NeuralNetwork(rng)
        self.assertEqual(first.parameter_count, 90)
        self.assertEqual(first.input_weights.shape, (8, 8))
        self.assertEqual(first.output_weights.shape, (8, 2))
        self.assertNotEqual(first, second)
        for left, right in zip(first.parameters, second.parameters):
            self.assertFalse(np.shares_memory(left, right))

    def test_initialization_is_seeded(self) -> None:
        first = NeuralNetwork(np.random.default_rng(42))
        repeat = NeuralNetwork(np.random.default_rng(42))
        different = NeuralNetwork(np.random.default_rng(43))
        self.assertEqual(first, repeat)
        self.assertNotEqual(first, different)

    def test_zero_parameters_produce_neutral_outputs(self) -> None:
        brain = NeuralNetwork(np.random.default_rng(42))
        zero_brain(brain)
        np.testing.assert_array_equal(brain.forward(np.ones(8)), [0.0, 0.0])

    def test_a_known_signal_passes_through_both_layers(self) -> None:
        brain = NeuralNetwork(np.random.default_rng(42))
        zero_brain(brain)
        brain.input_weights[0, 0] = 1.0
        brain.output_weights[0, 0] = 1.0
        sensors = np.zeros(8)
        sensors[0] = 0.5
        expected = math.tanh(math.tanh(0.5))
        np.testing.assert_allclose(brain.forward(sensors), [expected, 0.0])

    def test_outputs_are_bounded_and_inference_does_not_train_weights(self) -> None:
        rng = np.random.default_rng(42)
        brain = NeuralNetwork(rng)
        before = [parameter.copy() for parameter in brain.parameters]
        for _ in range(100):
            outputs = brain.forward(rng.uniform(-1.0, 1.0, 8))
            self.assertEqual(outputs.shape, (2,))
            self.assertTrue(np.all(np.isfinite(outputs)))
            self.assertTrue(np.all(np.abs(outputs) <= 1.0))
        for old, current in zip(before, brain.parameters):
            np.testing.assert_array_equal(old, current)

    def test_invalid_inputs_and_nonfinite_outputs_are_rejected(self) -> None:
        brain = NeuralNetwork(np.random.default_rng(42))
        for sensors in (np.zeros(7), np.zeros((1, 8)), np.full(8, np.nan), np.full(8, np.inf)):
            with self.subTest(shape=sensors.shape), self.assertRaises(ValueError):
                brain.forward(sensors)
        brain.output_bias[0] = np.nan
        with self.assertRaises(ValueError):
            brain.forward(np.zeros(8))


class SensoryInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World(seed=42, food_count=0)
        self.creature = self.world.creatures[0]
        self.creature.x, self.creature.y, self.creature.heading = 500.0, 300.0, 0.0

    def test_food_offsets_rotate_with_the_creatures_heading(self) -> None:
        self.world.food = [Food(580, 300)]
        np.testing.assert_allclose(self.world.get_sensory_inputs(self.creature)[:3],
                                   [0.5, 0.0, 1.0])
        self.creature.heading = math.pi / 2
        np.testing.assert_allclose(self.world.get_sensory_inputs(self.creature)[:3],
                                   [0.0, -0.5, 1.0], atol=1e-12)

    def test_nearest_food_is_used_and_food_behind_has_a_negative_forward_offset(self) -> None:
        self.world.food = [Food(580, 300), Food(480, 300)]
        np.testing.assert_allclose(self.world.get_sensory_inputs(self.creature)[:3],
                                   [-20 / VISION_RANGE, 0.0, 1.0])

    def test_absent_and_out_of_range_food_are_masked(self) -> None:
        for food in ([], [Food(500 + VISION_RANGE + 1, 300)]):
            self.world.food = food
            np.testing.assert_array_equal(self.world.get_sensory_inputs(self.creature)[:3],
                                          [0.0, 0.0, 0.0])

    def test_wall_rays_account_for_radius_and_body_orientation(self) -> None:
        self.creature.x = self.creature.radius + 16.0
        np.testing.assert_allclose(self.world.get_sensory_inputs(self.creature)[4:],
                                   [1.0, 1.0, 0.1, 1.0])
        self.creature.heading = math.pi / 2
        np.testing.assert_allclose(self.world.get_sensory_inputs(self.creature)[4:],
                                   [1.0, 0.1, 1.0, 1.0])
        self.creature.x = self.creature.radius
        sensors = self.world.get_sensory_inputs(self.creature)
        self.assertEqual(sensors[5], 0.0)
        self.assertTrue(np.all(np.isfinite(sensors)))
        self.assertTrue(np.all(np.abs(sensors) <= 1.0))

    def test_hunger_is_an_input(self) -> None:
        self.creature.energy = 25.0
        self.assertEqual(self.world.get_sensory_inputs(self.creature)[3], 0.75)


class NeuralControlTests(unittest.TestCase):
    def test_both_modes_start_with_the_same_bodies_food_and_individual_brains(self) -> None:
        neural = World(seed=42)
        baseline = World(seed=42, controller="random")
        self.assertEqual([asdict(creature) for creature in neural.creatures],
                         [asdict(creature) for creature in baseline.creatures])
        self.assertEqual(neural.food, baseline.food)
        self.assertTrue(all(creature.brain is not None for creature in neural.creatures))
        self.assertNotEqual(neural.creatures[0].brain, neural.creatures[1].brain)

    def test_neural_throttle_drives_motion_and_the_same_ticks_energy_cost(self) -> None:
        world = World(seed=42, food_count=0)
        creature = world.creatures[0]
        creature.x, creature.y, creature.heading = 500.0, 300.0, 0.0
        creature.max_speed = creature.speed = 60.0
        zero_brain(creature.brain)
        world.creatures = [creature]
        world.update(SIMULATION_STEP)
        self.assertAlmostEqual(creature.speed, 30.0)
        self.assertAlmostEqual(creature.x, 500.5)
        self.assertAlmostEqual(creature.y, 300.0)
        self.assertAlmostEqual(creature.energy, 100 - 3.5 * SIMULATION_STEP)
        self.assertEqual(creature.turn_rate, 0.0)
        self.assertEqual(creature.turn_time_remaining, 0.0)

    def test_opposite_weights_can_turn_away_from_the_same_food(self) -> None:
        headings = []
        for sign in (1.0, -1.0):
            world = World(seed=42, food_count=0)
            creature = world.creatures[0]
            creature.x, creature.y, creature.heading = 500.0, 300.0, 0.0
            zero_brain(creature.brain)
            creature.brain.input_weights[1, 0] = 1.0
            creature.brain.output_weights[0, 0] = sign * 2.0
            world.creatures = [creature]
            world.food = [Food(500, 380)]
            world.update(SIMULATION_STEP)
            headings.append((creature.heading + math.pi) % math.tau - math.pi)
        self.assertGreater(headings[0], 0.0)
        self.assertLess(headings[1], 0.0)
        self.assertAlmostEqual(headings[0], -headings[1])

    def test_motor_commands_are_bounded_by_the_creatures_capacity(self) -> None:
        creature = World(seed=42).creatures[0]
        creature.apply_controls(2.0, 2.0)
        self.assertEqual(creature.turn_rate, MAX_TURN_RATE)
        self.assertEqual(creature.speed, creature.max_speed)
        creature.apply_controls(-2.0, -2.0)
        self.assertEqual(creature.turn_rate, -MAX_TURN_RATE)
        self.assertEqual(creature.speed, 0.0)

    def test_dead_and_paused_creatures_do_not_run_inference(self) -> None:
        world = World(seed=42, food_count=0)
        creature = world.creatures[0]
        creature.brain = Mock(spec=NeuralNetwork)
        world.creatures = [creature]
        world.paused = True
        world.update(1.0)
        creature.brain.forward.assert_not_called()
        world.paused = False
        creature.energy = 0.0
        world.update(SIMULATION_STEP)
        creature.brain.forward.assert_not_called()
        self.assertEqual(world.dead_creatures, [creature])

    def test_reset_recreates_weights_and_supports_negative_seeds(self) -> None:
        world = World(seed=-42, food_count=0)
        before = [parameter.copy() for parameter in world.creatures[0].brain.parameters]
        world.creatures[0].brain.input_weights[0, 0] += 1.0
        world.regenerate_population(-42)
        for expected, actual in zip(before, world.creatures[0].brain.parameters):
            np.testing.assert_array_equal(expected, actual)

    def test_invalid_controller_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            World(controller="invalid")


if __name__ == "__main__":
    unittest.main()
