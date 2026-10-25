"""Energy use, hunger, aging, death, and integration with eating and the world."""

from dataclasses import asdict
import math
import os
import random
import unittest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from creature import MAX_ENERGY, Creature, create_population
from food import Food
from world import SIMULATION_STEP, World


def make_creature(creature_id: int = 1, **changes: float) -> Creature:
    properties = dict(
        creature_id=creature_id, x=50.0, y=50.0, radius=6,
        color=(101, 219, 181), heading=0.0, speed=0.0,
        turn_time_remaining=10.0,
    )
    properties.update(changes)
    return Creature(**properties)


class CreatureSurvivalTests(unittest.TestCase):
    def test_basal_energy_use_even_when_stationary(self) -> None:
        creature = make_creature()
        creature.update_survival(2.0)
        self.assertAlmostEqual(creature.energy, 96.0)
        self.assertAlmostEqual(creature.age, 2.0)
        self.assertTrue(creature.alive)

    def test_faster_movement_uses_more_energy_per_second(self) -> None:
        slower = make_creature(speed=40.0)
        faster = make_creature(speed=80.0)
        slower.update_survival(2.0)
        faster.update_survival(2.0)
        self.assertAlmostEqual(slower.energy, 92.0)
        self.assertAlmostEqual(faster.energy, 88.0)

    def test_hunger_increases_with_energy_deficit_and_decreases_after_food(self) -> None:
        creature = make_creature()
        self.assertEqual(creature.hunger, 0.0)
        self.assertEqual(creature.hunger_state, "Sated")
        creature.energy = 50.0
        self.assertEqual(creature.hunger, 0.5)
        self.assertEqual(creature.hunger_state, "Hungry")
        self.assertTrue(creature.eat(Food(50, 50)))
        self.assertAlmostEqual(creature.hunger, 0.3)
        self.assertEqual(creature.hunger_state, "Sated")
        creature.energy = 20.0
        self.assertEqual(creature.hunger_state, "Starving")

    def test_food_is_capped_and_full_creatures_do_not_take_meals(self) -> None:
        creature = make_creature(energy=95.0)
        self.assertTrue(creature.eat(Food(50, 50)))
        self.assertEqual(creature.energy, MAX_ENERGY)
        self.assertEqual(creature.food_eaten, 1)
        self.assertFalse(creature.eat(Food(50, 50)))
        self.assertEqual(creature.food_eaten, 1)

    def test_starvation_stops_age_at_death_and_prevents_all_actions(self) -> None:
        creature = make_creature(energy=1.0)
        creature.update_survival(2.0)
        self.assertFalse(creature.alive)
        self.assertEqual(creature.energy, 0.0)
        self.assertAlmostEqual(creature.age, 0.5)
        self.assertEqual(creature.death_cause, "starvation")
        self.assertEqual(creature.hunger_state, "Dead")
        before = asdict(creature)
        self.assertFalse(creature.eat(Food(50, 50)))
        creature.rotate(1.0)
        creature.move(1.0, 100, 100)
        creature.update_survival(10.0)
        self.assertEqual(asdict(creature), before)

    def test_old_age_death_occurs_with_energy_still_available(self) -> None:
        creature = make_creature(age=1.0, lifespan=2.0)
        creature.update_survival(3.0)
        self.assertFalse(creature.alive)
        self.assertEqual(creature.death_cause, "old_age")
        self.assertEqual(creature.age, 2.0)
        self.assertAlmostEqual(creature.energy, 98.0)
        self.assertFalse(creature.eat(Food(50, 50)))

    def test_first_fatal_limit_determines_death_cause(self) -> None:
        starves_first = make_creature(energy=1.0, lifespan=0.75)
        ages_first = make_creature(energy=2.0, lifespan=0.75)
        starves_first.update_survival(1.0)
        ages_first.update_survival(1.0)
        self.assertEqual(starves_first.death_cause, "starvation")
        self.assertEqual(ages_first.death_cause, "old_age")
        self.assertAlmostEqual(starves_first.age, 0.5)
        self.assertAlmostEqual(ages_first.age, 0.75)

    def test_rounded_lifespan_arrival_still_records_a_death_cause(self) -> None:
        creature = make_creature(age=math.nextafter(1.0, 0.0), lifespan=1.0)
        creature.update_survival(2.0 ** -54)
        self.assertFalse(creature.alive)
        self.assertEqual(creature.death_cause, "old_age")

    def test_zero_and_invalid_survival_time(self) -> None:
        creature = make_creature()
        before = asdict(creature)
        creature.update_survival(0.0)
        self.assertEqual(asdict(creature), before)
        for dt in (-1.0, math.inf, math.nan):
            with self.subTest(dt=dt), self.assertRaises(ValueError):
                creature.update_survival(dt)

    def test_initial_lifespans_are_bounded_and_seeded(self) -> None:
        first = create_population(1000, 600, random.Random(42))
        repeat = create_population(1000, 600, random.Random(42))
        self.assertTrue(all(60.0 <= creature.lifespan <= 120.0 for creature in first))
        self.assertEqual([asdict(creature) for creature in first],
                         [asdict(creature) for creature in repeat])


class WorldSurvivalTests(unittest.TestCase):
    def test_starved_creature_is_removed_before_food_contact_and_recorded_once(self) -> None:
        world = World(seed=42, food_count=1)
        creature = make_creature(energy=0.01)
        pellet = Food(50, 50)
        world.creatures = [creature]
        world.selected_creature = creature
        world.food = [pellet]
        world.update(SIMULATION_STEP)
        self.assertEqual(world.creatures, [])
        self.assertEqual(world.dead_creatures, [creature])
        self.assertIsNone(world.selected_creature)
        self.assertEqual(world.total_food_eaten, 0)
        self.assertIs(world.food[0], pellet)
        world.update(SIMULATION_STEP)
        self.assertEqual(len(world.dead_creatures), 1)
        self.assertFalse(creature.alive)

    def test_food_can_rescue_a_creature_that_survives_the_energy_charge(self) -> None:
        world = World(seed=42, food_count=1)
        creature = make_creature(energy=0.05)
        world.creatures = [creature]
        world.food = [Food(50, 50)]
        world.update(SIMULATION_STEP)
        self.assertTrue(creature.alive)
        self.assertEqual(world.dead_creatures, [])
        self.assertAlmostEqual(creature.energy, 20.05 - 2.0 * SIMULATION_STEP)
        self.assertEqual(creature.food_eaten, 1)

    def test_multiple_deaths_leave_only_living_creatures(self) -> None:
        world = World(seed=42, food_count=0)
        starving = make_creature(1, energy=0.01)
        elderly = make_creature(2, lifespan=0.001)
        survivor = make_creature(3)
        world.creatures = [starving, elderly, survivor]
        world.update(SIMULATION_STEP)
        self.assertEqual(world.creatures, [survivor])
        self.assertEqual([creature.death_cause for creature in world.dead_creatures],
                         ["starvation", "old_age"])

    def test_extinction_keeps_drawing_and_selection_safe(self) -> None:
        world = World(seed=42, food_count=0)
        creature = make_creature(energy=0.01)
        world.creatures = [creature]
        world.selected_creature = creature
        world.update(1.0)
        world.select_creature((50, 50))
        world.draw(pygame.Surface((1000, 600)), (0, 0))
        world.update(1.0)
        self.assertEqual(world.creatures, [])
        self.assertIsNone(world.selected_creature)
        self.assertEqual(len(world.dead_creatures), 1)

    def test_survival_and_deaths_match_at_different_frame_rates(self) -> None:
        states = []
        for fps in (30, 60, 144):
            world = World(seed=42, food_count=0)
            for index, creature in enumerate(world.creatures):
                creature.lifespan = 0.5 + index / 300.0
                if index % 10 == 0:
                    creature.energy = 0.01
            for _ in range(fps):
                world.update(1.0 / fps)
            self.assertEqual(world.creatures, [])
            self.assertEqual(len(world.dead_creatures), 100)
            states.append([asdict(creature) for creature in world.dead_creatures])
        self.assertEqual(states[0], states[1])
        self.assertEqual(states[0], states[2])

    def test_reset_restores_life_after_extinction(self) -> None:
        world = World(seed=42, food_count=2)
        initial = [asdict(creature) for creature in world.creatures]
        initial_food = list(world.food)
        for creature in world.creatures:
            creature.energy = 0.0
        world.update(SIMULATION_STEP)
        self.assertEqual(len(world.dead_creatures), 100)
        world.paused = True
        world.regenerate_population(42)
        self.assertTrue(world.paused)
        self.assertEqual([asdict(creature) for creature in world.creatures], initial)
        self.assertEqual(world.food, initial_food)
        self.assertEqual(world.dead_creatures, [])
        self.assertEqual(world.elapsed_time, 0.0)
        self.assertEqual(world.total_food_eaten, 0)


if __name__ == "__main__":
    unittest.main()
