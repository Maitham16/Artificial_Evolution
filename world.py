"""The 2D habitat. Coordinates are local to the arena, in pixels."""

import math
import random

import numpy as np
import pygame

from brain import DEFAULT_MUTATION_RATE, DEFAULT_MUTATION_SCALE, validate_mutation_parameters
from creature import MAX_ENERGY, POPULATION_SIZE, Creature, create_population
from food import FOOD_COUNT, FOOD_RADIUS, Food
from generation_stats import SURVIVAL_CHECKPOINT_SECONDS, GenerationStats
from perception import VISION_RANGE, FoodPerception, sense_food
from selection import FitnessEvaluation, evaluate_population
from reproduction import OffspringBrain, reproduce_brains


SIMULATION_STEP = 1.0 / 60.0


class World:
    """A rectangular arena where creatures move, feed, age, and survive."""

    BACKGROUND = (17, 29, 35)
    GRID = (24, 39, 46)
    MAJOR_GRID = (31, 49, 56)
    BORDER = (64, 91, 100)

    def __init__(
        self,
        width: int = 1000,
        height: int = 600,
        *,
        seed: int | None = None,
        food_count: int = FOOD_COUNT,
        controller: str = "neural",
        mutation_rate: float = DEFAULT_MUTATION_RATE,
        mutation_scale: float = DEFAULT_MUTATION_SCALE,
        evolution_enabled: bool = True,
    ) -> None:
        if food_count < 0:
            raise ValueError("Food count must be non-negative.")
        if controller not in ("neural", "random"):
            raise ValueError("Controller must be 'neural' or 'random'.")
        validate_mutation_parameters(mutation_rate, mutation_scale)
        self.width = width
        self.height = height
        self.food_count = food_count
        self.controller = controller
        self.mutation_rate = mutation_rate
        self.mutation_scale = mutation_scale
        self.evolution_enabled = evolution_enabled
        self.grid_spacing = 40
        self.show_grid = True
        self.show_perception = True
        self.show_fitness = False
        self.show_history = False
        self.paused = False
        self.surface = pygame.Surface((width, height))
        self.regenerate_population(seed)

    def regenerate_population(self, seed: int | None = None) -> None:
        """Restart the experiment with random founders and an empty history."""
        seed = seed if seed is not None else random.SystemRandom().randrange(2**32)
        self.seed = seed
        self.generation_history: list[FitnessEvaluation] = []
        self.generation_stats: list[GenerationStats] = []
        self._start_generation(1)

    def _start_generation(
        self, generation: int, inherited: list[OffspringBrain] | None = None
    ) -> None:
        """Create newborn bodies and a fresh environment for one generation."""
        suffix = "" if generation == 1 else f":generation:{generation}"
        population_seed = self.seed if generation == 1 else f"population:{self.seed}{suffix}"
        creatures = create_population(self.width, self.height, random.Random(population_seed))
        if inherited is not None and len(inherited) != len(creatures):
            raise ValueError("Every newborn must receive one inherited brain.")
        for index, creature in enumerate(creatures):
            creature.generation = generation
            if inherited is not None:
                inheritance = inherited[index]
                creature.brain = inheritance.brain
                creature.parent_id = inheritance.parent_id
                creature.mutation_count = inheritance.mutations
        self.generation = generation
        self.creatures = creatures
        self.dead_creatures: list[Creature] = []
        self.final_evaluation: FitnessEvaluation | None = None
        self.selected_creature: Creature | None = creatures[0]
        self._motion_rng = random.Random(f"motion:{self.seed}{suffix}")
        self._food_rng = random.Random(f"food:{self.seed}{suffix}")
        self.food: list[Food] = []
        self.total_food_eaten = 0
        for _ in range(self.food_count):
            self.food.append(self._spawn_food())
        self._accumulator = 0.0
        self.elapsed_time = 0.0
        self._alive_time = 0.0
        self._speed_time = 0.0
        self._food_visible_time = 0.0
        self._food_facing_time = 0.0

    def advance_generation(self) -> bool:
        """Advance a completed generation, breeding or resampling its brains."""
        evaluation = self.final_evaluation
        if self.creatures or evaluation is None or not evaluation.complete or not evaluation.selected_ids:
            return False
        if not self.evolution_enabled:
            self._start_generation(self.generation + 1)
            return True
        records = {creature.creature_id: creature for creature in self.dead_creatures}
        if any(parent_id not in records for parent_id in evaluation.selected_ids):
            raise ValueError("Selected parent records are missing.")
        parents = [records[parent_id] for parent_id in evaluation.selected_ids]
        next_generation = self.generation + 1
        mutation_seed = random.Random(
            f"mutation:{self.seed}:generation:{next_generation}"
        ).getrandbits(128)
        offspring = reproduce_brains(
            parents, np.random.default_rng(mutation_seed), offspring_count=POPULATION_SIZE,
            mutation_rate=self.mutation_rate, mutation_scale=self.mutation_scale,
        )
        self._start_generation(next_generation, offspring)
        return True

    def get_fitness_evaluation(self) -> FitnessEvaluation:
        """Return live scores or the frozen final ranking, without altering the run."""
        if self.final_evaluation is not None:
            return self.final_evaluation
        return evaluate_population([*self.creatures, *self.dead_creatures])

    def _spawn_food(self) -> Food:
        """Place a pellet in free space, clear of creatures and existing food."""
        margin = FOOD_RADIUS + 3
        for _ in range(1000):
            candidate = Food(
                self._food_rng.uniform(margin, self.width - margin),
                self._food_rng.uniform(margin, self.height - margin),
            )
            if any(
                candidate.overlaps_circle(creature.x, creature.y, creature.radius + 2)
                for creature in self.creatures
            ):
                continue
            if any(
                candidate.overlaps_circle(food.x, food.y, food.radius + 2)
                for food in self.food
            ):
                continue
            return candidate
        raise ValueError("The arena is too crowded to place food in free space.")

    def _resolve_food_collisions(self) -> None:
        """Award each touched pellet once, then replenish after all meals."""
        remaining = []
        for food in self.food:
            eater = min(
                (
                    creature for creature in self.creatures
                    if creature.alive and creature.energy < MAX_ENERGY
                    and food.overlaps_circle(creature.x, creature.y, creature.radius)
                ),
                key=lambda creature: (
                    (creature.x - food.x) ** 2 + (creature.y - food.y) ** 2,
                    creature.creature_id,
                ),
                default=None,
            )
            if eater is None:
                remaining.append(food)
            else:
                if eater.eat(food):
                    self.total_food_eaten += 1
                else:
                    remaining.append(food)

        self.food = remaining
        for _ in range(self.food_count - len(self.food)):
            self.food.append(self._spawn_food())

    def perceive_food(
        self, creature: Creature, food_positions: np.ndarray | None = None
    ) -> FoodPerception:
        """Observe nearby food from the creature's current position and heading."""
        if food_positions is None:
            food_positions = np.array([(food.x, food.y) for food in self.food],
                                      dtype=np.float64).reshape(-1, 2)
        return sense_food(creature.x, creature.y, creature.heading, food_positions)

    def get_sensory_inputs(
        self, creature: Creature, food_positions: np.ndarray | None = None
    ) -> np.ndarray:
        """Encode food distance/direction, hunger, and body-relative wall clearance."""
        food = self.perceive_food(creature, food_positions)
        cosine, sine = math.cos(creature.heading), math.sin(creature.heading)
        directions = ((cosine, sine), (-sine, cosine),
                      (-cosine, -sine), (sine, -cosine))
        walls = [self._wall_clearance(creature, dx, dy) for dx, dy in directions]
        return np.array([*food.neural_signals, creature.hunger, *walls],
                        dtype=np.float64)

    def _wall_clearance(self, creature: Creature, dx: float, dy: float) -> float:
        """Return a normalized ray distance to the nearest center-position limit."""
        distances = [VISION_RANGE]
        if dx > 1e-12:
            distances.append((self.width - creature.radius - creature.x) / dx)
        elif dx < -1e-12:
            distances.append((creature.radius - creature.x) / dx)
        if dy > 1e-12:
            distances.append((self.height - creature.radius - creature.y) / dy)
        elif dy < -1e-12:
            distances.append((creature.radius - creature.y) / dy)
        return max(0.0, min(distances)) / VISION_RANGE

    def update(self, dt: float) -> None:
        """Advance survival, living creatures' motion, and eating in fixed steps."""
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Simulation time must be finite and non-negative.")
        if self.paused or dt == 0:
            return

        self._accumulator += dt
        while self._accumulator + 1e-12 >= SIMULATION_STEP:
            food_positions = np.array([(food.x, food.y) for food in self.food],
                                      dtype=np.float64).reshape(-1, 2)
            survivors = []
            for creature in self.creatures:
                uses_brain = self.controller == "neural" and creature.brain is not None
                food_visible, food_direction = False, 0.0
                if creature.alive:
                    if uses_brain:
                        sensors = self.get_sensory_inputs(creature, food_positions)
                        food_visible, food_direction = bool(sensors[2]), sensors[1] * math.pi
                        turn, throttle = creature.brain.forward(sensors)
                        creature.apply_controls(float(turn), (float(throttle) + 1.0) / 2.0)
                    else:
                        observation = self.perceive_food(creature, food_positions)
                        food_visible = observation.visible
                        food_direction = observation.direction if food_visible else 0.0
                        if creature.turn_time_remaining <= 0:
                            creature.turn_rate = self._motion_rng.uniform(
                                -math.pi / 2, math.pi / 2
                            )
                            creature.turn_time_remaining = self._motion_rng.uniform(0.75, 2.0)
                previous_age = creature.age
                creature.update_survival(SIMULATION_STEP)
                lived = creature.age - previous_age
                self._alive_time += lived
                self._speed_time += abs(creature.speed) * lived
                if food_visible:
                    self._food_visible_time += lived
                    if abs(food_direction) <= math.pi / 4:
                        self._food_facing_time += lived
                if not creature.alive:
                    self.dead_creatures.append(creature)
                    continue
                survivors.append(creature)
                creature.rotate(creature.turn_rate * SIMULATION_STEP)
                creature.move(SIMULATION_STEP, self.width, self.height)
                if not uses_brain:
                    creature.turn_time_remaining -= SIMULATION_STEP
            self.creatures = survivors
            if self.selected_creature not in self.creatures:
                self.selected_creature = None
            self._resolve_food_collisions()
            if not self.creatures and self.final_evaluation is None:
                self.final_evaluation = evaluate_population(self.dead_creatures)
                self.generation_history.append(self.final_evaluation)
                entries = self.final_evaluation.ranking
                count = len(entries)
                if count:
                    self.generation_stats.append(GenerationStats(
                        generation=self.generation,
                        population_size=count,
                        duration_seconds=self.elapsed_time + SIMULATION_STEP,
                        mean_fitness=self.final_evaluation.mean_fitness,
                        best_fitness=self.final_evaluation.best.fitness,
                        mean_food_eaten=sum(entry.food_eaten for entry in entries) / count,
                        mean_survival_seconds=sum(entry.survival_seconds for entry in entries) / count,
                        mean_speed=self._speed_time / self._alive_time if self._alive_time else 0.0,
                        food_visible_seconds=self._food_visible_time,
                        food_facing_seconds=self._food_facing_time,
                        survivors_at_checkpoint=sum(
                            entry.survival_seconds >= SURVIVAL_CHECKPOINT_SECONDS
                            for entry in entries
                        ),
                    ))
            self.elapsed_time += SIMULATION_STEP
            self._accumulator = max(0.0, self._accumulator - SIMULATION_STEP)

    def select_creature(self, position: tuple[int, int]) -> None:
        """Select the nearest creature under a click in arena coordinates."""
        x, y = position
        nearest = min(
            self.creatures,
            key=lambda creature: math.hypot(x - creature.x, y - creature.y),
            default=None,
        )
        if nearest is None:
            self.selected_creature = None
            return
        distance = math.hypot(x - nearest.x, y - nearest.y)
        self.selected_creature = nearest if distance <= nearest.radius + 6 else None

    def draw(self, screen: pygame.Surface, origin: tuple[int, int]) -> None:
        """Draw the arena at an offset without changing its coordinates."""
        self.surface.fill(self.BACKGROUND)

        if self.show_grid:
            for x in range(0, self.width, self.grid_spacing):
                color = self.MAJOR_GRID if x % 200 == 0 else self.GRID
                pygame.draw.line(self.surface, color, (x, 0), (x, self.height - 1))
            for y in range(0, self.height, self.grid_spacing):
                color = self.MAJOR_GRID if y % 200 == 0 else self.GRID
                pygame.draw.line(self.surface, color, (0, y), (self.width - 1, y))

        observation = None
        if (
            self.show_perception and self.selected_creature is not None
            and self.selected_creature.alive
        ):
            selected = self.selected_creature
            observation = self.perceive_food(selected)
            center = (round(selected.x), round(selected.y))
            pygame.draw.circle(self.surface, (46, 83, 97), center, round(VISION_RANGE), width=1)
            forward = (
                round(selected.x + math.cos(selected.heading) * 28),
                round(selected.y + math.sin(selected.heading) * 28),
            )
            pygame.draw.line(self.surface, (105, 143, 159), center, forward, width=1)
            if observation.visible:
                target = tuple(round(value) for value in observation.target_position)
                pygame.draw.line(self.surface, (115, 158, 82), center, target, width=1)

        for food in self.food:
            food.draw(self.surface)

        if observation is not None and observation.visible:
            target = tuple(round(value) for value in observation.target_position)
            pygame.draw.circle(self.surface, (192, 235, 137), target, FOOD_RADIUS + 4, width=1)

        for creature in self.creatures:
            if creature is not self.selected_creature:
                creature.draw(self.surface)
        if self.selected_creature is not None:
            self.selected_creature.draw(self.surface, selected=True)

        pygame.draw.rect(self.surface, self.BORDER, self.surface.get_rect(), width=2)
        screen.blit(self.surface, origin)
