"""Food generation, collision geometry, meal accounting, and reproducibility."""

from dataclasses import asdict
import os
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from creature import Creature
from food import FOOD_COUNT, Food
from world import SIMULATION_STEP, World


def still_creature(creature_id: int = 1, **changes: float) -> Creature:
    properties = dict(
        creature_id=creature_id, x=50.0, y=50.0, radius=6,
        color=(101, 219, 181), heading=0.0, speed=0.0,
        turn_time_remaining=10.0, energy=50.0,
    )
    properties.update(changes)
    return Creature(**properties)


def world_state(world: World) -> tuple:
    return (
        [asdict(creature) for creature in world.creatures],
        [asdict(food) for food in world.food],
        world.total_food_eaten,
    )


class FoodTests(unittest.TestCase):
    def test_circle_contact_includes_edges_and_rejects_diagonal_near_misses(self) -> None:
        food = Food(20.0, 20.0)
        self.assertTrue(food.overlaps_circle(29.0, 20.0, 6))
        self.assertFalse(food.overlaps_circle(29.001, 20.0, 6))
        self.assertFalse(food.overlaps_circle(28.0, 28.0, 6))
        self.assertTrue(food.overlaps_circle(26.0, 26.0, 6))

    def test_random_food_starts_inside_arena_and_clear_of_bodies_and_other_food(self) -> None:
        for seed in range(5):
            with self.subTest(seed=seed):
                world = World(seed=seed)
                self.assertEqual(len(world.food), FOOD_COUNT)
                for index, food in enumerate(world.food):
                    self.assertTrue(food.radius <= food.x <= world.width - food.radius)
                    self.assertTrue(food.radius <= food.y <= world.height - food.radius)
                    self.assertEqual(food.energy, 20.0)
                    self.assertFalse(any(
                        food.overlaps_circle(creature.x, creature.y, creature.radius)
                        for creature in world.creatures
                    ))
                    self.assertFalse(any(
                        food.overlaps_circle(other.x, other.y, other.radius)
                        for other in world.food[index + 1:]
                    ))

    def test_moving_into_food_awards_energy_once_and_replaces_the_pellet(self) -> None:
        world = World(seed=42, food_count=1)
        creature = still_creature(x=45.0, speed=80.0)
        pellet = Food(55.0, 50.0)
        world.creatures = [creature]
        world.food = [pellet]
        self.assertFalse(pellet.overlaps_circle(creature.x, creature.y, creature.radius))
        world.update(SIMULATION_STEP)
        expected_energy = 50.0 - 6.0 * SIMULATION_STEP + pellet.energy
        self.assertAlmostEqual(creature.energy, expected_energy)
        self.assertEqual(creature.food_eaten, 1)
        self.assertEqual(world.total_food_eaten, 1)
        self.assertEqual(len(world.food), 1)
        self.assertIsNot(world.food[0], pellet)
        self.assertFalse(world.food[0].overlaps_circle(creature.x, creature.y, creature.radius))
        creature.speed = 0.0
        world.update(SIMULATION_STEP)
        self.assertAlmostEqual(creature.energy, expected_energy - 2.0 * SIMULATION_STEP)
        self.assertEqual(world.total_food_eaten, 1)

    def test_separated_creature_does_not_eat(self) -> None:
        world = World(seed=42, food_count=1)
        creature = still_creature()
        pellet = Food(80.0, 80.0)
        world.creatures = [creature]
        world.food = [pellet]
        world.update(SIMULATION_STEP)
        self.assertAlmostEqual(creature.energy, 50.0 - 2.0 * SIMULATION_STEP)
        self.assertEqual(creature.food_eaten, 0)
        self.assertEqual(world.total_food_eaten, 0)
        self.assertIs(world.food[0], pellet)

    def test_contested_food_goes_to_nearest_creature_once(self) -> None:
        world = World(seed=42, food_count=1)
        farther = still_creature(1, x=57.0)
        nearer = still_creature(2, x=51.0)
        world.creatures = [farther, nearer]
        world.food = [Food(50.0, 50.0)]
        world.update(SIMULATION_STEP)
        self.assertEqual((farther.food_eaten, nearer.food_eaten), (0, 1))
        self.assertAlmostEqual(farther.energy, 50.0 - 2.0 * SIMULATION_STEP)
        self.assertAlmostEqual(nearer.energy, 70.0 - 2.0 * SIMULATION_STEP)
        self.assertEqual(world.total_food_eaten, 1)

    def test_exact_tie_uses_id_independently_of_list_order(self) -> None:
        world = World(seed=42, food_count=1)
        first = still_creature(1, x=49.0)
        second = still_creature(2, x=51.0)
        world.creatures = [second, first]
        world.food = [Food(50.0, 50.0)]
        world.update(SIMULATION_STEP)
        self.assertEqual((first.food_eaten, second.food_eaten), (1, 0))
        self.assertEqual(world.total_food_eaten, 1)

    def test_one_creature_can_consume_two_distinct_pellets(self) -> None:
        world = World(seed=42, food_count=2)
        creature = still_creature()
        world.creatures = [creature]
        world.food = [Food(45.0, 50.0), Food(55.0, 50.0)]
        world.update(SIMULATION_STEP)
        self.assertAlmostEqual(creature.energy, 90.0 - 2.0 * SIMULATION_STEP)
        self.assertEqual(creature.food_eaten, 2)
        self.assertEqual(world.total_food_eaten, 2)
        self.assertEqual(len(world.food), 2)

    def test_pause_freezes_food_and_eating(self) -> None:
        world = World(seed=42, food_count=1)
        world.creatures = [still_creature()]
        world.food = [Food(50.0, 50.0)]
        world.paused = True
        before = world_state(world)
        world.update(1.0)
        self.assertEqual(world_state(world), before)
        world.paused = False
        world.update(SIMULATION_STEP)
        self.assertEqual(world.total_food_eaten, 1)

    def test_same_seed_and_time_reproduce_food_and_meals_across_frame_rates(self) -> None:
        states = []
        for fps in (30, 60, 144):
            world = World(seed=42)
            for _ in range(fps * 2):
                world.update(1.0 / fps)
            states.append(world_state(world))
        self.assertGreater(states[0][2], 0)
        self.assertEqual(states[0], states[1])
        self.assertEqual(states[0], states[2])

    def test_food_does_not_change_early_random_movement(self) -> None:
        with_food = World(seed=42, controller="random")
        without_food = World(seed=42, food_count=0, controller="random")
        for world in (with_food, without_food):
            world.update(2.0)
        self.assertGreater(with_food.total_food_eaten, 0)
        for fed, unfed in zip(with_food.creatures, without_food.creatures):
            self.assertEqual((fed.x, fed.y, fed.heading), (unfed.x, unfed.y, unfed.heading))

    def test_reset_restores_food_energy_and_counters_from_seed(self) -> None:
        world = World(seed=42)
        initial = world_state(world)
        world.update(2.0)
        eaten = world.total_food_eaten
        self.assertGreater(eaten, 0)
        self.assertEqual(sum(creature.food_eaten for creature in world.creatures), eaten)
        self.assertTrue(all(0 < creature.energy <= 100 for creature in world.creatures))
        self.assertTrue(any(creature.energy < 100 for creature in world.creatures))
        self.assertEqual(len(world.food), FOOD_COUNT)
        world.paused = True
        world.regenerate_population(42)
        self.assertEqual(world_state(world), initial)
        self.assertTrue(world.paused)
        self.assertEqual(world.elapsed_time, 0.0)

    def test_zero_and_negative_food_counts(self) -> None:
        self.assertEqual(World(seed=42, food_count=0).food, [])
        with self.assertRaises(ValueError):
            World(seed=42, food_count=-1)


if __name__ == "__main__":
    unittest.main()
