"""Opt-in generation seasons, bounded moving clusters, and a reproductive gate."""

from dataclasses import replace
import copy
import math
import random

from creature import _reflect_axis
from experiment_selection import RecordedMutationRNG
from reproduction import reproduce_brains
from selection import SELECTION_FRACTION
from world import CLUSTER_COUNT, World


SEASON_NAMES = ("spring", "summer", "autumn", "winter")
DEFAULT_FOOD = (150, 200, 75, 25)


def season_context(generation, *, season_length=1, food_counts=DEFAULT_FOOD):
    if (type(generation) is not int or generation < 1 or type(season_length) is not int or season_length < 1
            or len(food_counts) != 4 or any(type(n) is not int or n < 0 for n in food_counts)):
        raise ValueError('Use a positive generation and season length, and four nonnegative integer food counts.')
    index = (generation - 1) // season_length
    return {'generation': generation, 'season': SEASON_NAMES[index % 4], 'season_index': index % 4,
            'cycle': index // 4 + 1, 'food_count': food_counts[index % 4]}


def moving_centers(seed, generation, width, height, shift):
    if type(generation) is not int or generation < 1 or not math.isfinite(shift) or shift < 0:
        raise ValueError('Use a positive generation and finite nonnegative cluster shift.')
    rng = random.Random(f'step21:cluster-origins:{seed}')
    centers = [(rng.uniform(.2 * width, .8 * width), rng.uniform(.2 * height, .8 * height)) for _ in range(CLUSTER_COUNT)]
    for index in range(2, generation + 1):
        rng = random.Random(f'step21:cluster-shift:{seed}:generation:{index}')
        moved = []
        for x, y in centers:
            angle = rng.uniform(0, math.tau)
            dx, dy = shift * math.cos(angle), shift * math.sin(angle)
            x, _ = _reflect_axis(x + dx, dx, .2 * width, .8 * width)
            y, _ = _reflect_axis(y + dy, dy, .2 * height, .8 * height)
            moved.append((x, y))
        centers = moved
    return centers


class SeasonalWorld(World):
    """Existing physics, with seasonal starts and maturity-gated inheritance.

    Parents' archived weights may reproduce only if they reached reproductive_age.
    Birth cohort size is fixed; zero eligible parents ends the lineage permanently.
    This is a generational breeding experiment, not continuous demographic ecology.
    """
    def __init__(self, *args, season_length=1, season_food=DEFAULT_FOOD, cluster_shift=120.0,
                 reproductive_age=60.0, **kwargs):
        season_context(1, season_length=season_length, food_counts=season_food)
        if isinstance(cluster_shift, bool) or not math.isfinite(cluster_shift) or cluster_shift < 0:
            raise ValueError('Cluster shift must be finite and nonnegative.')
        if isinstance(reproductive_age, bool) or not math.isfinite(reproductive_age) or reproductive_age <= 0:
            raise ValueError('Reproductive age must be finite and positive.')
        if kwargs.get('evolution_enabled', True) is not True:
            raise ValueError('Seasonal lineages require inherited reproduction.')
        self.season_length, self.season_food = season_length, tuple(season_food)
        self.cluster_shift, self.reproductive_age = cluster_shift, reproductive_age
        kwargs['food_distribution'] = 'clustered'
        super().__init__(*args, **kwargs)

    def regenerate_population(self, seed=None):
        self.environment_history, self.transitions = [], []
        self.extinction_generation = None
        super().regenerate_population(seed)

    def _start_generation(self, generation, inherited=None):
        context = season_context(generation, season_length=self.season_length, food_counts=self.season_food)
        self.food_count = context['food_count']
        self._desired_centers = moving_centers(self.seed, generation, self.width, self.height, self.cluster_shift)
        super()._start_generation(generation, inherited)
        # The zero-food case never calls _spawn_food, but still has a defined habitat.
        self.food_cluster_centers = list(self._desired_centers)
        self.environment_history.append({**context, 'cluster_centers': [list(p) for p in self.food_cluster_centers],
                                         'complete': False})

    def _spawn_food(self):
        # Install the seasonal centers before World places the first pellet.
        self.food_cluster_centers = list(self._desired_centers)
        return super()._spawn_food()

    @property
    def lineage_extinct(self):
        return self.extinction_generation is not None

    def update(self, dt):
        if self.lineage_extinct:
            return
        super().update(dt)
        if self.final_evaluation is not None and not self.environment_history[-1]['complete']:
            candidates = [r for r in self.final_evaluation.ranking if r.survival_seconds >= self.reproductive_age]
            count = min(len(candidates), math.ceil(self.population_size * SELECTION_FRACTION))
            chosen = tuple(row.creature_id for row in candidates[:count])
            self.final_evaluation = replace(self.final_evaluation, selected_ids=chosen)
            self.generation_history[-1] = self.final_evaluation
            self.environment_history[-1].update(complete=True, eligible_parent_count=len(candidates),
                selected_ids=list(chosen), candidates=[{'creature_id': r.creature_id, 'age': r.survival_seconds,
                    'food_eaten': r.food_eaten, 'fitness': r.fitness} for r in self.final_evaluation.ranking])
            if not candidates:
                self.extinction_generation = self.generation

    def advance_generation(self):
        if self.lineage_extinct or self.final_evaluation is None or self.creatures:
            return False
        parent_ids = sorted(self.final_evaluation.selected_ids)
        if not parent_ids:
            return False
        records = {c.creature_id: c for c in self.dead_creatures}
        following = self.generation + 1
        mutation_seed = random.Random(f'mutation:{self.seed}:generation:{following}').getrandbits(128)
        rng = RecordedMutationRNG(mutation_seed)
        offspring = reproduce_brains([records[key] for key in parent_ids], rng, offspring_count=self.population_size,
                                     mutation_rate=self.mutation_rate, mutation_scale=self.mutation_scale)
        self.transitions.append({'from_generation': self.generation, 'to_generation': following,
            'parent_ids': parent_ids, 'mutation_seed': mutation_seed,
            'mutation_draws_sha256': rng.digest.hexdigest(), 'mutation_rng_calls': rng.calls,
            'offspring_parent_ids': [c.parent_id for c in offspring],
            'offspring_mutation_counts': [c.mutations for c in offspring]})
        self._start_generation(following, offspring)
        return True

    def environment_report(self):
        return copy.deepcopy({'season_length_generations': self.season_length,
            'food_counts': list(self.season_food), 'cluster_shift_pixels': self.cluster_shift,
            'reproductive_age_seconds': self.reproductive_age, 'lineage_extinct': self.lineage_extinct,
            'extinction_generation': self.extinction_generation,
            'history': self.environment_history, 'transitions': self.transitions})
