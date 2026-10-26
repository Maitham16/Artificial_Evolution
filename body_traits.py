"""Linked brain/body inheritance and an explicit, uncalibrated 2D energy model."""

from dataclasses import dataclass, field, fields
import copy
from functools import cached_property
import hashlib
import json
import math
import os
import random

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

import numpy as np

from brain import NeuralNetwork, validate_mutation_parameters
from creature import Creature
from experiment_selection import RecordedMutationRNG
from food import Food, FOOD_RADIUS
from reproduction import reproduce_brains
from world import CLUSTER_SPREAD, World


TRAIT_NAMES = ('cruise_speed', 'radius', 'sensory_range')
LOWER = np.array([25., 4., 60.])
UPPER = np.array([100., 12., 280.])
REFERENCE_VALUES = (60., 8, 160.)
BODY_MUTATION_RATE = .25
BODY_MUTATION_SCALE = .08
ENERGY_MODEL = {'birth_budget': 100., 'reference_radius': 8., 'reference_speed': 60.,
                'reference_range': 160., 'capacity_per_reference_mass': 100.,
                'development_per_reference_mass': 10., 'basal_per_reference_mass': 2.,
                'movement_at_reference': 2.5, 'sensing_at_reference': .5}


@dataclass(frozen=True)
class BodyTraits:
    cruise_speed: float = 60.
    radius: int = 8
    sensory_range: float = 160.

    def __post_init__(self):
        if (type(self.radius) is not int or not 4 <= self.radius <= 12
                or isinstance(self.cruise_speed, bool) or not math.isfinite(self.cruise_speed)
                or not 25 <= self.cruise_speed <= 100
                or isinstance(self.sensory_range, bool) or not math.isfinite(self.sensory_range)
                or not 60 <= self.sensory_range <= 280):
            raise ValueError('Use speed 25–100, integer radius 4–12, and sensory range 60–280.')
        object.__setattr__(self, 'cruise_speed', float(self.cruise_speed))
        object.__setattr__(self, 'sensory_range', float(self.sensory_range))

    def vector(self):
        return np.array([self.cruise_speed, self.radius, self.sensory_range], dtype=np.float64)

    @classmethod
    def from_vector(cls, values):
        values = np.asarray(values, dtype=float)
        if values.shape != (3,) or not np.all(np.isfinite(values)) or not float(values[1]).is_integer():
            raise ValueError('A body genome requires three finite values and an integer radius.')
        return cls(float(values[0]), int(values[1]), float(values[2]))

    @cached_property
    def mass(self):
        return (self.radius / 8.) ** 2

    @cached_property
    def capacity(self):
        return 100. * self.mass

    @cached_property
    def development(self):
        return 10. * self.mass

    @cached_property
    def initial_energy(self):
        return min(self.capacity, 100. - self.development)

    @cached_property
    def energy_powers(self):
        return (2. * self.mass, 2.5 * self.mass * (self.cruise_speed / 60.) ** 2,
                .5 * (self.sensory_range / 160.) ** 2)

    def powers(self):
        return self.energy_powers


@dataclass(frozen=True)
class WholeGenome:
    brain: NeuralNetwork
    body: BodyTraits

    def copy(self):
        return WholeGenome(self.brain.copy(), self.body)


@dataclass(frozen=True)
class WholeOffspring:
    parent_id: int
    brain: NeuralNetwork
    mutations: int
    body: BodyTraits
    body_mutations: int


def mutate_body(parent, rng, rate=BODY_MUTATION_RATE, scale=BODY_MUTATION_SCALE):
    validate_mutation_parameters(rate, scale)
    if rate == 0 or scale == 0:
        return parent
    mask = rng.random(3) < rate
    noise = rng.normal(0., scale, 3)
    values = parent.vector()
    # Clamp in log space before exponentiation, so large finite scales cannot overflow.
    for index in np.flatnonzero(mask):
        value = np.clip(np.exp(np.clip(np.log(values[index]) + noise[index],
                                      np.log(LOWER[index]), np.log(UPPER[index]))), LOWER[index], UPPER[index])
        values[index] = int(round(value)) if index == 1 else value
    return BodyTraits.from_vector(values)


def reproduce_genomes(parents, brain_rng, body_rng, *, offspring_count=100,
                      mutation_rate=.1, mutation_scale=.1,
                      body_mutation_rate=BODY_MUTATION_RATE, body_mutation_scale=BODY_MUTATION_SCALE):
    parents = list(parents)
    records = {c.creature_id: c for c in parents}
    brains = reproduce_brains(parents, brain_rng, offspring_count=offspring_count,
                              mutation_rate=mutation_rate, mutation_scale=mutation_scale)
    children = []
    for child in brains:
        parent_body = records[child.parent_id].body
        body = mutate_body(parent_body, body_rng, body_mutation_rate, body_mutation_scale)
        changes = int(np.count_nonzero(body.vector() != parent_body.vector()))
        children.append(WholeOffspring(child.parent_id, child.brain, child.mutations, body, changes))
    return children


def genome_bank_digest(bank):
    digest = hashlib.sha256()
    for key in sorted(bank):
        genome = bank[key]
        for p in genome.brain.parameters:
            digest.update(p.astype('<f8').tobytes())
        digest.update(genome.body.vector().astype('<f8').tobytes())
    return digest.hexdigest()


def shared_layout_digest(world):
    anchors = [(c.creature_id, c.x, c.y, c.heading, c.color, c.lifespan) for c in world.creatures]
    return hashlib.sha256(json.dumps([anchors, [(f.x, f.y) for f in world.food]]).encode()).hexdigest()


@dataclass
class TraitCreature(Creature):
    body: BodyTraits = field(default_factory=BodyTraits)
    body_mutation_count: int = 0
    basal_energy: float = 0.
    movement_energy: float = 0.
    sensing_energy: float = 0.
    assimilated_energy: float = 0.
    wasted_food_energy: float = 0.

    def __post_init__(self):
        super().__post_init__()
        self.radius = self.body.radius
        self.speed = self.max_speed = self.body.cruise_speed
        self.energy = self.body.initial_energy

    @property
    def energy_capacity(self):
        return self.body.capacity

    @property
    def energy_cost_per_second(self):
        return sum(self.body.powers())

    def apply_controls(self, turn, throttle):
        super().apply_controls(turn, throttle)
        if self.alive:
            self.speed = self.max_speed = self.body.cruise_speed

    def update_survival(self, dt):
        before = self.age
        super().update_survival(dt)
        lived = self.age - before
        basal, movement, sensing = self.body.powers()
        self.basal_energy += basal * lived
        self.movement_energy += movement * lived
        self.sensing_energy += sensing * lived

    def eat(self, food):
        before = self.energy
        result = super().eat(food)
        if result:
            gained = self.energy - before
            self.assimilated_energy += gained
            self.wasted_food_energy += food.energy - gained
        return result


class TraitWorld(World):
    def __init__(self, *args, genomes=None, body_mutation_rate=BODY_MUTATION_RATE,
                 body_mutation_scale=BODY_MUTATION_SCALE, **kwargs):
        if kwargs.get('fixed_speed') is not None:
            raise ValueError('Trait-world cruise speed comes from each inherited body, not --fixed-speed.')
        validate_mutation_parameters(body_mutation_rate, body_mutation_scale)
        self.initial_genomes = genomes
        self.body_mutation_rate, self.body_mutation_scale = body_mutation_rate, body_mutation_scale
        super().__init__(*args, **kwargs)

    def regenerate_population(self, seed=None):
        self.trait_history, self.transitions = [], []
        super().regenerate_population(seed)

    def _start_generation(self, generation, inherited=None):
        self._birth_genomes = inherited
        self._body_generation = generation
        super()._start_generation(generation, inherited)
        bank = {c.creature_id: WholeGenome(c.brain, c.body) for c in self.creatures}
        self.trait_history.append({'generation': generation, 'complete': False,
            'genomes_sha256': genome_bank_digest(bank), 'shared_layout_sha256': shared_layout_digest(self),
            'birth_bodies': [c.body.vector().tolist() for c in self.creatures]})

    def _create_population(self, rng):
        originals = super()._create_population(rng)
        anchors_rng = random.Random(f'step23:anchors:{self.seed}:generation:{self._body_generation}')
        population = []
        for index, original in enumerate(originals):
            source = self._birth_genomes[index] if self._birth_genomes is not None else (
                self.initial_genomes[original.creature_id] if self.initial_genomes is not None else None)
            body = source.body if source is not None else BodyTraits()
            c = TraitCreature(**{f.name: getattr(original, f.name) for f in fields(Creature) if f.init}, body=body)
            if source is not None:
                c.brain = source.brain.copy()
                c.body_mutation_count = getattr(source, 'body_mutations', 0)
            # Use the maximum possible envelope in every treatment, independent of actual body genes.
            for _ in range(2000):
                c.x, c.y = anchors_rng.uniform(20, self.width - 20), anchors_rng.uniform(20, self.height - 20)
                if all(math.hypot(c.x - other.x, c.y - other.y) >= 32 for other in population): break
            else: raise ValueError('Arena is too crowded for shared maximum-body anchors.')
            population.append(c)
        return population

    def _spawn_food(self):
        margin = FOOD_RADIUS + 3
        for _ in range(1000):
            if self.food_distribution == 'clustered':
                cx, cy = self._food_rng.choice(self.food_cluster_centers)
                x, y = self._food_rng.gauss(cx, CLUSTER_SPREAD), self._food_rng.gauss(cy, CLUSTER_SPREAD)
                if not (margin <= x <= self.width - margin and margin <= y <= self.height - margin): continue
                candidate = Food(x, y)
            else:
                candidate = Food(self._food_rng.uniform(margin, self.width - margin), self._food_rng.uniform(margin, self.height - margin))
            if any(candidate.overlaps_circle(c.x, c.y, 14) for c in self.creatures): continue
            if any(candidate.overlaps_circle(f.x, f.y, f.radius + 2) for f in self.food): continue
            return candidate
        raise ValueError('Arena is too crowded for shared food placement.')

    def vision_range_for(self, creature):
        return creature.body.sensory_range

    def update(self, dt):
        super().update(dt)
        if self.final_evaluation is not None and not self.trait_history[-1]['complete']:
            records = []
            for c in sorted(self.dead_creatures, key=lambda c: c.creature_id):
                records.append({'creature_id': c.creature_id, 'body': c.body.vector().tolist(), 'age': c.age,
                    'food_eaten': c.food_eaten, 'fitness': c.fitness, 'death_cause': c.death_cause,
                    'initial_energy': c.body.initial_energy, 'final_energy': c.energy,
                    'basal_energy': c.basal_energy, 'movement_energy': c.movement_energy,
                    'sensing_energy': c.sensing_energy, 'assimilated_energy': c.assimilated_energy,
                    'wasted_food_energy': c.wasted_food_energy})
            self.trait_history[-1].update(complete=True, creatures=records)

    def advance_generation(self):
        if not self.evolution_enabled: return super().advance_generation()
        if self.creatures or self.final_evaluation is None or not self.final_evaluation.selected_ids: return False
        records = {c.creature_id: c for c in self.dead_creatures}
        parent_ids = sorted(self.final_evaluation.selected_ids)
        following = self.generation + 1
        brain_seed = random.Random(f'mutation:{self.seed}:generation:{following}').getrandbits(128)
        body_seed = random.Random(f'step23:body-mutation:{self.seed}:generation:{following}').getrandbits(128)
        brain_rng, body_rng = RecordedMutationRNG(brain_seed), RecordedMutationRNG(body_seed)
        offspring = reproduce_genomes([records[k] for k in parent_ids], brain_rng, body_rng,
            offspring_count=self.population_size, mutation_rate=self.mutation_rate, mutation_scale=self.mutation_scale,
            body_mutation_rate=self.body_mutation_rate, body_mutation_scale=self.body_mutation_scale)
        self.transitions.append({'from_generation': self.generation, 'to_generation': following, 'parent_ids': parent_ids,
            'brain_mutation_seed': brain_seed, 'body_mutation_seed': body_seed,
            'brain_draws_sha256': brain_rng.digest.hexdigest(), 'body_draws_sha256': body_rng.digest.hexdigest(),
            'brain_rng_calls': brain_rng.calls, 'body_rng_calls': body_rng.calls,
            'offspring_parent_ids': [c.parent_id for c in offspring],
            'brain_mutation_counts': [c.mutations for c in offspring], 'body_mutation_counts': [c.body_mutations for c in offspring]})
        self._start_generation(following, offspring)
        return True

    def traits_report(self):
        return copy.deepcopy({'trait_names': list(TRAIT_NAMES), 'bounds': [LOWER.tolist(), UPPER.tolist()],
            'reference': list(REFERENCE_VALUES), 'energy_model': ENERGY_MODEL,
            'body_mutation_rate': self.body_mutation_rate, 'body_mutation_scale': self.body_mutation_scale,
            'history': self.trait_history, 'transitions': self.transitions})
