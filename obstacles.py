"""Opt-in solid barriers, dangerous regions, radius-aware rays, and 16-input brains."""

from dataclasses import dataclass, field, fields
import copy
import hashlib
import json
import math
import random

import numpy as np
import pygame

from brain import NeuralNetwork, SENSOR_NAMES
from creature import Creature
from experiment_selection import RecordedMutationRNG
from reproduction import reproduce_brains
from world import World


INPUT_SIZE = 16
RAY_ANGLES = (-math.pi / 2, -math.pi / 4, 0.0, math.pi / 4, math.pi / 2)
RISK_RANGE = 160.0
COLLISION_ENERGY = 2.0
HAZARD_ENERGY_PER_SECOND = 12.0
COLLISION_FITNESS = 2.0
HAZARD_FITNESS_PER_SECOND = 5.0
SENSORS = (*SENSOR_NAMES, 'obstacle_left', 'obstacle_front_left', 'obstacle_forward',
           'obstacle_front_right', 'obstacle_right', 'hazard_proximity', 'hazard_direction', 'hazard_inside')


@dataclass(frozen=True)
class Barrier:
    x: float
    y: float
    width: float
    height: float

    def expanded(self, radius=0.0):
        return (self.x - radius, self.y - radius, self.x + self.width + radius, self.y + self.height + radius)

    def overlaps(self, x, y, radius=0.0):
        # Conservative square envelope, identical for sensing, spawning and movement.
        left, top, right, bottom = self.expanded(radius)
        return left <= x <= right and top <= y <= bottom


@dataclass(frozen=True)
class Danger:
    x: float
    y: float
    radius: float

    def overlaps(self, x, y, radius=0.0):
        return (x - self.x) ** 2 + (y - self.y) ** 2 <= (self.radius + radius) ** 2


def ray_box(x, y, dx, dy, bounds):
    """Distance and outward normal on entry; no hit when leaving/tangent at contact."""
    near, far, normal = -math.inf, math.inf, (0.0, 0.0)
    for position, direction, lower, upper, low_normal, high_normal in (
        (x, dx, bounds[0], bounds[2], (-1.0, 0.0), (1.0, 0.0)),
        (y, dy, bounds[1], bounds[3], (0.0, -1.0), (0.0, 1.0)),
    ):
        if abs(direction) < 1e-12:
            if position < lower or position > upper:
                return None
            continue
        a, b = (lower - position) / direction, (upper - position) / direction
        entry_normal = low_normal if direction > 0 else high_normal
        if a > b: a, b = b, a
        if a > near: near, normal = a, entry_normal
        far = min(far, b)
    if near > far + 1e-10 or far < 0 or near < -1e-9:
        return None
    return max(0.0, near), normal


def layout(seed, generation, width=1000, height=600):
    rng = random.Random(f'step22:layout:{seed}:generation:{generation}')
    # Two partial walls plus a cross-bar; generous passages remain around all ends.
    barriers = [Barrier(.30 * width, rng.uniform(.12, .25) * height, .022 * width, .37 * height),
                Barrier(.65 * width, rng.uniform(.38, .48) * height, .022 * width, .37 * height),
                Barrier(rng.uniform(.39, .43) * width, .48 * height, .15 * width, .027 * height)]
    dangers = [Danger(rng.uniform(.43, .53) * width, rng.uniform(.18, .27) * height, .085 * height),
               Danger(rng.uniform(.45, .55) * width, rng.uniform(.74, .83) * height, .085 * height)]
    return barriers, dangers


def geometry_digest(barriers, dangers):
    return hashlib.sha256(json.dumps([[list(b.__dict__.values()) for b in barriers],
                                     [list(h.__dict__.values()) for h in dangers]]).encode()).hexdigest()


@dataclass
class ObstacleCreature(Creature):
    collisions: int = 0
    hazard_seconds: float = 0.0
    collision_energy_lost: float = 0.0
    hazard_energy_lost: float = 0.0
    barriers: list = field(default_factory=list, repr=False, compare=False)
    dangers: list = field(default_factory=list, repr=False, compare=False)

    @property
    def in_danger(self):
        return any(h.overlaps(self.x, self.y, self.radius) for h in self.dangers)

    @property
    def energy_cost_per_second(self):
        return super().energy_cost_per_second + (HAZARD_ENERGY_PER_SECOND if self.in_danger else 0)

    @property
    def fitness(self):
        return super().fitness - COLLISION_FITNESS * self.collisions - HAZARD_FITNESS_PER_SECOND * self.hazard_seconds

    def update_survival(self, dt):
        inside, previous_age = self.in_danger, self.age
        super().update_survival(dt)
        lived = self.age - previous_age
        if inside:
            self.hazard_seconds += lived
            self.hazard_energy_lost += HAZARD_ENERGY_PER_SECOND * lived
            if self.death_cause == 'starvation': self.death_cause = 'hazard'

    def move(self, dt, width, height):
        if not math.isfinite(dt) or dt < 0:
            raise ValueError('Movement time must be finite and nonnegative.')
        if dt == 0 or not self.alive: return
        if min(width, height) <= 2 * self.radius:
            raise ValueError('Arena must be wider than the creature.')
        remaining = abs(self.speed) * dt
        dx, dy = math.cos(self.heading), math.sin(self.heading)
        for _ in range(16):
            if remaining <= 1e-9 or not self.alive: break
            hit, normal, internal = remaining + 1, (0.0, 0.0), False
            for barrier in self.barriers:
                result = ray_box(self.x, self.y, dx, dy, barrier.expanded(self.radius))
                if result is not None and result[0] < hit:
                    hit, normal, internal = result[0], result[1], True
            # World boundary reflections stay unpenalized, as in the original arena.
            for distance, n in (
                (((width - self.radius - self.x) / dx) if dx > 1e-12 else math.inf, (-1., 0.)),
                (((self.radius - self.x) / dx) if dx < -1e-12 else math.inf, (1., 0.)),
                (((height - self.radius - self.y) / dy) if dy > 1e-12 else math.inf, (0., -1.)),
                (((self.radius - self.y) / dy) if dy < -1e-12 else math.inf, (0., 1.)),
            ):
                if -1e-9 <= distance < hit: hit, normal, internal = max(0., distance), n, False
            travel = min(remaining, hit)
            self.x += dx * travel
            self.y += dy * travel
            remaining -= travel
            if hit > travel + 1e-9: break
            if internal:
                self.collisions += 1
                lost = min(self.energy, COLLISION_ENERGY)
                self.energy -= lost
                self.collision_energy_lost += lost
                if self.energy <= 0: self.death_cause = 'collision'
            dot = dx * normal[0] + dy * normal[1]
            dx, dy = dx - 2 * dot * normal[0], dy - 2 * dot * normal[1]
            # Tiny separation prevents a reflected contact from registering repeatedly.
            self.x += normal[0] * 1e-7
            self.y += normal[1] * 1e-7
        self.heading = math.atan2(dy, dx) % math.tau
        # If an extreme dt exceeds 16 impacts, stop at the last safe contact.


class ObstacleWorld(World):
    def __init__(self, *args, risk_sensor_mode='intact', **kwargs):
        if risk_sensor_mode not in ('intact', 'hidden'):
            raise ValueError('Risk sensors must be intact or hidden.')
        self.risk_sensor_mode = risk_sensor_mode
        super().__init__(*args, **kwargs)

    def regenerate_population(self, seed=None):
        self.obstacle_history, self.transitions = [], []
        super().regenerate_population(seed)

    def _start_generation(self, generation, inherited=None):
        self._layout_generation = generation
        self.barriers, self.dangers = layout(self.seed, generation, self.width, self.height)
        super()._start_generation(generation, inherited)
        self.obstacle_history.append({'generation': generation, 'geometry_sha256': geometry_digest(self.barriers, self.dangers),
            'barriers': [list(b.__dict__.values()) for b in self.barriers],
            'dangers': [list(h.__dict__.values()) for h in self.dangers], 'complete': False})

    def _create_population(self, rng):
        originals = super()._create_population(rng)
        positions_rng = random.Random(f'step22:placement:{self.seed}:generation:{self._layout_generation}')
        brain_rng = np.random.default_rng(random.Random(f'step22:brains:{self.seed}:generation:{self._layout_generation}').getrandbits(128))
        population = []
        for original in originals:
            creature = ObstacleCreature(**{f.name: getattr(original, f.name) for f in fields(Creature) if f.init})
            creature.barriers, creature.dangers = self.barriers, self.dangers
            for _ in range(2000):
                if (not self.unsafe(creature.x, creature.y, creature.radius + 3)
                        and all(math.hypot(creature.x - c.x, creature.y - c.y) >= creature.radius + c.radius + 8 for c in population)):
                    break
                margin = creature.radius + 8
                creature.x = positions_rng.uniform(margin, self.width - margin)
                creature.y = positions_rng.uniform(margin, self.height - margin)
            else: raise ValueError('Could not place safe obstacle-world bodies.')
            creature.brain = NeuralNetwork(brain_rng, input_size=INPUT_SIZE)
            population.append(creature)
        return population

    def unsafe(self, x, y, radius):
        return any(b.overlaps(x, y, radius) for b in self.barriers) or any(h.overlaps(x, y, radius) for h in self.dangers)

    def _spawn_food(self):
        for _ in range(1000):
            candidate = super()._spawn_food()
            if not self.unsafe(candidate.x, candidate.y, candidate.radius + 2): return candidate
        raise ValueError('Could not place safe accessible food.')

    def get_sensory_inputs(self, creature, food_positions=None):
        original = super().get_sensory_inputs(creature, food_positions)
        clearances = []
        for angle in RAY_ANGLES:
            dx, dy = math.cos(creature.heading + angle), math.sin(creature.heading + angle)
            distances = [RISK_RANGE]
            for b in self.barriers:
                result = ray_box(creature.x, creature.y, dx, dy, b.expanded(creature.radius))
                if result is not None: distances.append(result[0])
            clearances.append(min(distances) / RISK_RANGE)
        nearest = min(self.dangers, key=lambda h: math.hypot(h.x - creature.x, h.y - creature.y) - h.radius, default=None)
        risk = [0., 0., 0.]
        if nearest is not None:
            center_distance = math.hypot(nearest.x - creature.x, nearest.y - creature.y)
            distance = max(0., center_distance - nearest.radius - creature.radius)
            if distance <= RISK_RANGE:
                bearing = 0. if center_distance == 0 else (math.atan2(nearest.y - creature.y, nearest.x - creature.x) - creature.heading + math.pi) % math.tau - math.pi
                risk = [1 - distance / RISK_RANGE, bearing / math.pi, float(creature.in_danger)]
        extra = [*clearances, *risk] if self.risk_sensor_mode == 'intact' else [1., 1., 1., 1., 1., 0., 0., 0.]
        return np.concatenate([original, extra])

    def update(self, dt):
        super().update(dt)
        if self.final_evaluation is not None and not self.obstacle_history[-1]['complete']:
            records = [{'creature_id': c.creature_id, 'age': c.age, 'food_eaten': c.food_eaten,
                        'collisions': c.collisions, 'hazard_seconds': c.hazard_seconds,
                        'fitness': c.fitness, 'death_cause': c.death_cause} for c in sorted(self.dead_creatures, key=lambda c: c.creature_id)]
            living = sum(c.age for c in self.dead_creatures)
            self.obstacle_history[-1].update(complete=True, creatures=records,
                collision_rate=60 * sum(c.collisions for c in self.dead_creatures) / living if living else 0.,
                hazard_fraction=sum(c.hazard_seconds for c in self.dead_creatures) / living if living else 0.)

    def advance_generation(self):
        if not self.evolution_enabled: return super().advance_generation()
        if self.creatures or self.final_evaluation is None or not self.final_evaluation.selected_ids: return False
        records = {c.creature_id: c for c in self.dead_creatures}
        parent_ids = sorted(self.final_evaluation.selected_ids)
        mutation_seed = random.Random(f'mutation:{self.seed}:generation:{self.generation + 1}').getrandbits(128)
        rng = RecordedMutationRNG(mutation_seed)
        children = reproduce_brains([records[k] for k in parent_ids], rng, offspring_count=self.population_size,
                                    mutation_rate=self.mutation_rate, mutation_scale=self.mutation_scale)
        self.transitions.append({'from_generation': self.generation, 'to_generation': self.generation + 1,
            'parent_ids': parent_ids, 'mutation_seed': mutation_seed, 'mutation_draws_sha256': rng.digest.hexdigest(),
            'mutation_rng_calls': rng.calls, 'offspring_parent_ids': [c.parent_id for c in children],
            'offspring_mutation_counts': [c.mutations for c in children]})
        self._start_generation(self.generation + 1, children)
        return True

    def hazard_report(self):
        return copy.deepcopy({'input_size': INPUT_SIZE, 'sensors': list(SENSORS), 'risk_sensor_mode': self.risk_sensor_mode,
            'collision_energy': COLLISION_ENERGY, 'hazard_energy_per_second': HAZARD_ENERGY_PER_SECOND,
            'collision_fitness': COLLISION_FITNESS, 'hazard_fitness_per_second': HAZARD_FITNESS_PER_SECOND,
            'history': self.obstacle_history, 'transitions': self.transitions})

    def _draw_environment(self, surface):
        for h in self.dangers:
            pygame.draw.circle(surface, (65, 30, 42), (round(h.x), round(h.y)), round(h.radius))
            pygame.draw.circle(surface, (177, 66, 85), (round(h.x), round(h.y)), round(h.radius), width=2)
        for b in self.barriers:
            rect = pygame.Rect(round(b.x), round(b.y), round(b.width), round(b.height))
            pygame.draw.rect(surface, (85, 105, 117), rect)
            pygame.draw.rect(surface, (153, 175, 184), rect, width=2)
        c = self.selected_creature
        if self.show_perception and c is not None and c.alive:
            inputs = self.get_sensory_inputs(c)
            for angle, value in zip(RAY_ANGLES, inputs[8:13]):
                end = (round(c.x + RISK_RANGE * value * math.cos(c.heading + angle)),
                       round(c.y + RISK_RANGE * value * math.sin(c.heading + angle)))
                pygame.draw.line(surface, (193, 161, 93), (round(c.x), round(c.y)), end, width=1)
