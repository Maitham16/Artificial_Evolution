"""Two coevolving, fixed birth cohorts in a shared, finite-window arena."""

from dataclasses import dataclass, fields
import copy
import math
import os
import random

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')

import numpy as np
import pygame

from brain import NeuralNetwork
from body_traits import (TraitCreature, TraitWorld, WholeGenome, ENERGY_MODEL,
                         genome_bank_digest, reproduce_genomes, shared_layout_digest)
from experiment_selection import RecordedMutationRNG
from generation_stats import GenerationStats
from perception import FoodPerception, sense_food
from selection import FitnessEntry, FitnessEvaluation
from world import SIMULATION_STEP


SPECIES = ('prey', 'predator')
INPUT_SIZE = 11
CAPTURE_ENERGY = 60.
CAPTURE_REWARD = 30.
COLORS = {'prey': (101, 219, 181), 'predator': (239, 117, 130)}
SENSOR_NAMES = ('food_proximity', 'food_direction', 'food_visible', 'hunger',
                'wall_forward', 'wall_right', 'wall_back', 'wall_left',
                'opponent_proximity', 'opponent_direction', 'opponent_visible')


def reflected_path(c, dt, width, height):
    """Exact straight segments of a radius-aware reflective move, in tick time."""
    x, y = c.x, c.y
    vx, vy = c.speed * math.cos(c.heading), c.speed * math.sin(c.heading)
    time, segments = 0., []
    while time < dt - 1e-12:
        tx = ((width - c.radius - x) / vx if vx > 1e-12 else
              (c.radius - x) / vx if vx < -1e-12 else math.inf)
        ty = ((height - c.radius - y) / vy if vy > 1e-12 else
              (c.radius - y) / vy if vy < -1e-12 else math.inf)
        travel = min(dt - time, max(0., tx), max(0., ty))
        if travel > 1e-12:
            segments.append((time, time + travel, x, y, vx, vy))
            x, y = x + vx * travel, y + vy * travel
            time += travel
        if tx <= travel + 1e-12: vx = -vx
        if ty <= travel + 1e-12: vy = -vy
        if len(segments) > 16:
            raise ValueError('A fixed movement tick cannot have more than 16 wall segments.')
    return segments


def first_contact(left, right, radius):
    """First disk contact along two piecewise reflected paths, or None."""
    earliest = None
    for a in left:
        for b in right:
            start, end = max(a[0], b[0]), min(a[1], b[1])
            if end < start: continue
            dx = a[2] + a[4] * (start - a[0]) - b[2] - b[4] * (start - b[0])
            dy = a[3] + a[5] * (start - a[0]) - b[3] - b[5] * (start - b[0])
            vx, vy = a[4] - b[4], a[5] - b[5]
            offset = dx * dx + dy * dy - radius * radius
            if offset <= 1e-10:
                hit = start
            else:
                speed2 = vx * vx + vy * vy
                projection = dx * vx + dy * vy
                discriminant = projection * projection - speed2 * offset
                if speed2 <= 1e-16 or projection >= 0 or discriminant < -1e-10: continue
                hit = start + (-projection - math.sqrt(max(0., discriminant))) / speed2
                if hit > end + 1e-12: continue
            earliest = hit if earliest is None else min(earliest, hit)
    return earliest


@dataclass
class EcologicalCreature(TraitCreature):
    species: str = 'prey'
    captures: int = 0
    capture_assimilated_energy: float = 0.
    wasted_capture_energy: float = 0.
    opponent_visible_seconds: float = 0.
    away_seconds: float = 0.
    toward_seconds: float = 0.

    @property
    def fitness(self):
        return self.age + (10 * self.food_eaten if self.species == 'prey' else CAPTURE_REWARD * self.captures)


class PredatorPreyWorld(TraitWorld):
    """Simultaneous decisions/selection, separate gene pools, and no scripted pursuit.

    Birth numbers are experimental controls. Counts change within each cohort;
    genomes from the complete evaluated cohort may breed even after death.
    This is not a continuously reproducing ecosystem or a lineage-extinction model.
    """

    def __init__(self, *args, predators=20, episode_seconds=60., prey_sensors='intact',
                 predator_sensors='intact', **kwargs):
        total = kwargs.get('population_size', 100)
        if type(predators) is not int or not 0 < predators < total:
            raise ValueError('Predators must be a positive integer smaller than the total population.')
        if (isinstance(episode_seconds, bool) or not math.isfinite(episode_seconds) or episode_seconds <= 0
                or not math.isclose(episode_seconds / SIMULATION_STEP, round(episode_seconds / SIMULATION_STEP), abs_tol=1e-8)):
            raise ValueError('Episode length must be positive and an exact number of fixed ticks.')
        if prey_sensors not in ('intact', 'hidden') or predator_sensors not in ('intact', 'hidden'):
            raise ValueError('Opponent sensors must be intact or hidden.')
        if kwargs.get('controller', 'neural') != 'neural' or kwargs.get('food_sensor_mode', 'intact') != 'intact':
            raise ValueError('Predator–prey mode uses neural controllers and intact food inputs.')
        self.predator_count, self.prey_count = predators, total - predators
        self.episode_seconds = episode_seconds
        self.episode_ticks = round(episode_seconds / SIMULATION_STEP)
        self.opponent_sensors = {'prey': prey_sensors, 'predator': predator_sensors}
        super().__init__(*args, **kwargs)

    def regenerate_population(self, seed=None):
        self.ecosystem_history = []
        super().regenerate_population(seed)

    def species_ids(self, species):
        return list(range(1, self.prey_count + 1)) if species == 'prey' else list(range(self.prey_count + 1, self.population_size + 1))

    def _create_population(self, rng):
        originals = super()._create_population(rng)
        creatures = []
        for old in originals:
            species = 'prey' if old.creature_id <= self.prey_count else 'predator'
            c = EcologicalCreature(**{f.name: getattr(old, f.name) for f in fields(TraitCreature) if f.init}, species=species)
            c.color = COLORS[species]
            if self._birth_genomes is None and self.initial_genomes is None:
                c.brain = NeuralNetwork(np.random.default_rng(random.Random(
                    f'step24:founder:{self.seed}:{c.creature_id}').getrandbits(128)), input_size=INPUT_SIZE)
            if c.brain.input_weights.shape != (INPUT_SIZE, 8):
                raise ValueError('Predator–prey brains require exactly eleven inputs.')
            creatures.append(c)
        return creatures

    def _start_generation(self, generation, inherited=None):
        super()._start_generation(generation, inherited)
        self._episode_ticks = 0
        self.captures = []
        self.role_evaluations = {}
        self.ecosystem_history.append({'generation': generation, 'complete': False,
            'shared_layout_sha256': shared_layout_digest(self),
            'genomes_sha256': self.trait_history[-1]['genomes_sha256'],
            'birth_bodies': self.trait_history[-1]['birth_bodies'],
            'population': [self.population_snapshot()]})

    def population_snapshot(self):
        return {'time': self.elapsed_time, **{s: sum(c.species == s for c in self.creatures) for s in SPECIES}}

    def perceive_food(self, creature, food_positions=None):
        if creature.species == 'predator': return FoodPerception(vision_range=creature.body.sensory_range)
        return super().perceive_food(creature, food_positions)

    def perceive_opponents(self, creature, positions=None):
        if positions is None:
            positions = np.array([(c.x, c.y) for c in self.creatures if c.species != creature.species]).reshape(-1, 2)
        return sense_food(creature.x, creature.y, creature.heading, positions, vision_range=creature.body.sensory_range)

    def get_sensory_inputs(self, creature, food_positions=None, opponent_positions=None):
        base = super().get_sensory_inputs(creature, food_positions)
        other = self.perceive_opponents(creature, opponent_positions)
        signal = other.neural_signals if self.opponent_sensors[creature.species] == 'intact' else (0., 0., 0.)
        return np.concatenate((base, signal))

    def _resolve_food_collisions(self):
        remaining = []
        prey = [c for c in self.creatures if c.species == 'prey' and c.alive and c.energy < c.energy_capacity]
        for food in self.food:
            eater = min((c for c in prey if c.energy < c.energy_capacity and food.overlaps_circle(c.x, c.y, c.radius)),
                        key=lambda c: ((c.x - food.x) ** 2 + (c.y - food.y) ** 2, c.creature_id), default=None)
            if eater is None: remaining.append(food)
            elif eater.eat(food): self.total_food_eaten += 1
        self.food = remaining
        while len(self.food) < self.food_count: self.food.append(self._spawn_food())

    def _resolve_captures(self, paths):
        prey = [c for c in self.creatures if c.species == 'prey']
        predators = [c for c in self.creatures if c.species == 'predator']
        events = []
        if not prey or not predators: return
        offsets = np.array([(c.x, c.y) for c in predators])[:, None, :] - np.array([(c.x, c.y) for c in prey])[None, :, :]
        # A contact cannot end farther apart than radii plus both full path lengths.
        reach = (np.array([c.radius + c.speed * SIMULATION_STEP for c in predators])[:, None]
                 + np.array([c.radius + c.speed * SIMULATION_STEP for c in prey])[None, :])
        for i, j in zip(*np.nonzero(np.sum(offsets * offsets, axis=2) <= reach * reach + 1e-9)):
            hunter, victim = predators[i], prey[j]
            hit = first_contact(paths[hunter.creature_id], paths[victim.creature_id], hunter.radius + victim.radius)
            if hit is not None: events.append((hit, victim.creature_id, hunter.creature_id, victim, hunter))
        # Earliest contact wins; exact simultaneous contacts break ties by neutral IDs.
        for time, _, _, victim, hunter in sorted(events, key=lambda e: e[:3]):
            if not victim.alive: continue
            victim.death_cause = 'predation'
            hunter.captures += 1
            gained = min(CAPTURE_ENERGY, hunter.energy_capacity - hunter.energy)
            hunter.energy += gained
            hunter.capture_assimilated_energy += gained
            hunter.wasted_capture_energy += CAPTURE_ENERGY - gained
            self.captures.append({'predator_id': hunter.creature_id, 'prey_id': victim.creature_id,
                                  'contact_time': self.elapsed_time + time,
                                  'removed_at': self.elapsed_time + SIMULATION_STEP})
        caught = [c for c in self.creatures if not c.alive]
        self.dead_creatures.extend(caught)
        self.creatures = [c for c in self.creatures if c.alive]

    def update(self, dt):
        if not math.isfinite(dt) or dt < 0: raise ValueError('Simulation time must be finite and nonnegative.')
        if self.paused or self.final_evaluation is not None or dt == 0: return
        self._accumulator += dt
        while self._accumulator + 1e-12 >= SIMULATION_STEP and self.final_evaluation is None:
            food = np.array([(f.x, f.y) for f in self.food]).reshape(-1, 2)
            positions = {s: np.array([(c.x, c.y) for c in self.creatures if c.species == s]).reshape(-1, 2) for s in SPECIES}
            survivors, paths = [], {}
            for c in self.creatures:
                other = positions['predator' if c.species == 'prey' else 'prey']
                observation = self.perceive_opponents(c, other)
                sensors = self.get_sensory_inputs(c, food, other)
                turn, throttle = c.brain.forward(sensors)
                c.apply_controls(float(turn), float(throttle))
                before, x, y = c.age, c.x, c.y
                c.update_survival(SIMULATION_STEP)
                lived = c.age - before
                self._alive_time += lived
                self._speed_time += c.speed * lived
                if observation.visible: c.opponent_visible_seconds += lived
                if not c.alive:
                    self.dead_creatures.append(c)
                    continue
                c.rotate(c.turn_rate * SIMULATION_STEP)
                paths[c.creature_id] = reflected_path(c, SIMULATION_STEP, self.width, self.height)
                c.move(SIMULATION_STEP, self.width, self.height)
                if observation.visible:
                    tx, ty = observation.target_position
                    dot = (c.x - x) * (tx - x) + (c.y - y) * (ty - y)
                    if dot < -1e-12: c.away_seconds += lived
                    elif dot > 1e-12: c.toward_seconds += lived
                survivors.append(c)
            self.creatures = survivors
            self._resolve_captures(paths)
            # Captured/starved prey cannot consume food in this tick.
            self._resolve_food_collisions()
            if self.selected_creature not in self.creatures: self.selected_creature = None
            self._episode_ticks += 1
            self.elapsed_time = self._episode_ticks * SIMULATION_STEP
            self._accumulator = max(0., self._accumulator - SIMULATION_STEP)
            if self._episode_ticks % 300 == 0 or not self.creatures or self._episode_ticks >= self.episode_ticks:
                self.ecosystem_history[-1]['population'].append(self.population_snapshot())
            if not self.creatures or self._episode_ticks >= self.episode_ticks: self._finish_generation()

    def _finish_generation(self):
        records = sorted([*self.creatures, *self.dead_creatures], key=lambda c: c.creature_id)
        summaries = {}
        for species in SPECIES:
            members = [c for c in records if c.species == species]
            entries = tuple(sorted((FitnessEntry(c.creature_id, c.age, c.food_eaten, c.fitness, c.alive) for c in members),
                                   key=lambda e: (-e.fitness, e.creature_id)))
            selected = tuple(e.creature_id for e in entries[:math.ceil(len(entries) * .2)])
            evaluation = FitnessEvaluation(entries, selected, True, .2)
            self.role_evaluations[species] = evaluation
            visible = sum(c.opponent_visible_seconds for c in members)
            summaries[species] = {'births': len(members), 'alive_at_end': sum(c.alive for c in members),
                'survival_rate': sum(c.alive for c in members) / len(members),
                'mean_fitness': sum(c.fitness for c in members) / len(members),
                'mean_age': sum(c.age for c in members) / len(members),
                'mean_meals': sum(c.food_eaten for c in members) / len(members),
                'captures': sum(c.captures for c in members),
                'deaths': {cause: sum(c.death_cause == cause for c in members) for cause in ('predation', 'starvation', 'old_age')},
                'opponent_visible_seconds': visible,
                'away_fraction': sum(c.away_seconds for c in members) / visible if visible else None,
                'toward_fraction': sum(c.toward_seconds for c in members) / visible if visible else None,
                'selected_ids': list(selected)}
        self.final_evaluation = self.role_evaluations['prey']
        self.generation_history.append(self.final_evaluation)
        prey = summaries['prey']
        # Legacy summary rows refer only to prey; predator scores are never mixed in.
        self.generation_stats.append(GenerationStats(self.generation, self.prey_count, self.elapsed_time,
            prey['mean_fitness'], self.final_evaluation.best.fitness, prey['mean_meals'], prey['mean_age'],
            self._speed_time / self._alive_time if self._alive_time else 0., 0., 0.,
            survivors_at_checkpoint=sum(c.species == 'prey' and c.age >= 60 for c in records)))
        individual = []
        for c in records:
            individual.append({'creature_id': c.creature_id, 'species': c.species, 'body': c.body.vector().tolist(),
                'age': c.age, 'food_eaten': c.food_eaten, 'captures': c.captures, 'fitness': c.fitness,
                'alive_at_end': c.alive, 'death_cause': c.death_cause, 'initial_energy': c.body.initial_energy,
                'final_energy': c.energy, **{name: getattr(c, name) for name in (
                    'basal_energy', 'movement_energy', 'sensing_energy', 'assimilated_energy', 'wasted_food_energy',
                    'capture_assimilated_energy', 'wasted_capture_energy', 'opponent_visible_seconds', 'away_seconds', 'toward_seconds')}})
        self.ecosystem_history[-1].update(complete=True, duration=self.elapsed_time, species=summaries,
            capture_fraction=len(self.captures) / self.prey_count, capture_events=copy.deepcopy(self.captures), creatures=individual)

    def advance_generation(self):
        if self.final_evaluation is None or not self.evolution_enabled: return False
        records = {c.creature_id: c for c in [*self.creatures, *self.dead_creatures]}
        offspring, traces = [], {}
        for species in SPECIES:
            parent_ids = sorted(self.role_evaluations[species].selected_ids)
            following = self.generation + 1
            seeds = {kind: random.Random(f'step24:{kind}:{self.seed}:{species}:generation:{following}').getrandbits(128)
                     for kind in ('brain', 'body')}
            brain_rng, body_rng = RecordedMutationRNG(seeds['brain']), RecordedMutationRNG(seeds['body'])
            children = reproduce_genomes([records[k] for k in parent_ids], brain_rng, body_rng,
                offspring_count=len(self.species_ids(species)), mutation_rate=self.mutation_rate, mutation_scale=self.mutation_scale,
                body_mutation_rate=self.body_mutation_rate, body_mutation_scale=self.body_mutation_scale)
            offspring.extend(children)
            traces[species] = {'parent_ids': parent_ids, 'seeds': seeds, 'brain_draws_sha256': brain_rng.digest.hexdigest(),
                'body_draws_sha256': body_rng.digest.hexdigest(), 'brain_rng_calls': brain_rng.calls, 'body_rng_calls': body_rng.calls,
                'offspring_parent_ids': [c.parent_id for c in children], 'brain_mutation_counts': [c.mutations for c in children],
                'body_mutation_counts': [c.body_mutations for c in children]}
        self.transitions.append({'from_generation': self.generation, 'to_generation': self.generation + 1, 'species': traces})
        self._start_generation(self.generation + 1, offspring)
        return True

    def ecosystem_report(self):
        return copy.deepcopy({'birth_counts': {'prey': self.prey_count, 'predator': self.predator_count},
            'episode_seconds': self.episode_seconds, 'opponent_sensors': self.opponent_sensors,
            'sensor_names': list(SENSOR_NAMES), 'capture_energy': CAPTURE_ENERGY, 'capture_reward': CAPTURE_REWARD,
            'energy_model': ENERGY_MODEL, 'body_mutation_rate': self.body_mutation_rate, 'body_mutation_scale': self.body_mutation_scale,
            'history': self.ecosystem_history, 'transitions': self.transitions,
            'summary_rows': 'Prey fitness only. All predator metrics are in ecosystem.history[].species.predator.',
            'demography': 'Fixed birth cohorts; within-cohort losses, finite-window censoring, archival genome reproduction. No demographic growth or lineage extinction claim.'})

    def _draw_environment(self, surface):
        c = self.selected_creature
        if c is None or not self.show_perception: return
        observation = self.perceive_opponents(c)
        if observation.visible:
            target = tuple(round(x) for x in observation.target_position)
            pygame.draw.line(surface, (235, 146, 95), (round(c.x), round(c.y)), target, width=2)
            pygame.draw.circle(surface, (235, 146, 95), target, 15, width=1)


def draw_ecosystem_interface(screen, world, fonts, simulation):
    """Role-specific counts and scores without mixing predator/prey fitness."""
    from main import PADDING, HEADER_HEIGHT, TEXT, MUTED, BACKGROUND, draw_trend
    screen.fill(BACKGROUND)
    font = fonts['small']
    def label(text, x, y, color=TEXT): screen.blit(font.render(text, True, color), (x, y))
    label('ARTIFICIAL EVOLUTION / STEP 24', 40, 22, COLORS['prey'])
    screen.blit(fonts['title'].render('Predator–prey evolution', True, TEXT), (40, 43))
    counts = world.population_snapshot()
    label(f"PREY {counts['prey']}/{world.prey_count}   PREDATORS {counts['predator']}/{world.predator_count}", 490, 25)
    label(f"Generation {world.generation} / {simulation.generation_limit or 'unlimited'}    {simulation.speed}x    {'PAUSED' if world.paused else 'COMPLETE' if world.final_evaluation else 'RUNNING'}", 490, 49, MUTED)
    label(f"Time {world.elapsed_time:.1f}/{world.episode_seconds:g}s    Captures {len(world.captures)}    Prey meals {world.total_food_eaten}    Food {len(world.food)}", 40, 82, MUTED)
    world.draw(screen, (PADDING, HEADER_HEIGHT))
    y = HEADER_HEIGHT + world.height + 15
    label('Space Pause  /  A Auto  /  S Speed  /  N Next  /  R Restart  /  F Roles  /  T History  /  V Senses  /  Esc Quit', 40, y, MUTED)
    c = world.selected_creature
    if c is not None:
        label(f"{c.species.upper()} #{c.creature_id}   Energy {c.energy:.1f}/{c.energy_capacity:.1f}   Age {c.age:.1f}s   Meals {c.food_eaten}   Captures {c.captures}   Fitness {c.fitness:.1f}", 40, y + 24, c.color)
        label(f"Genes: speed {c.body.cruise_speed:.1f} / radius {c.radius} / sight {c.body.sensory_range:.0f}    Opponent inputs {world.opponent_sensors[c.species]}    Orange line: actual nearest opponent", 40, y + 46, MUTED)
    else: label('Click a living creature to inspect its inherited traits and opponent senses.', 40, y + 28, MUTED)
    if not (world.show_history or world.show_fitness): return
    panel = pygame.Rect(90, 170, 900, 475)
    pygame.draw.rect(screen, BACKGROUND, panel, border_radius=12)
    pygame.draw.rect(screen, MUTED, panel, 1, border_radius=12)
    if world.show_fitness:
        label('Separate selection pools', 120, 192)
        members = [*world.creatures, *world.dead_creatures]
        for col, species in enumerate(SPECIES):
            x = 120 + col * 430
            label(f"{species.upper()} / {'age + 10 x meals' if species == 'prey' else 'age + 30 x captures'}", x, 230, COLORS[species])
            for row, c in enumerate(sorted((c for c in members if c.species == species), key=lambda c: (-c.fitness, c.creature_id))[:12]):
                label(f"#{c.creature_id:03d}   score {c.fitness:6.1f}   age {c.age:4.1f}   {'alive' if c.alive else c.death_cause}", x, 266 + row * 26)
    else:
        rows = [h for h in world.ecosystem_history if h['complete']]
        label('Completed cohorts / live counts change within each cohort; births reset to controlled sizes', 120, 192)
        if not rows:
            label('Complete a cohort to see history.', 120, 245, MUTED)
            return
        generations = [r['generation'] for r in rows]
        draw_trend(screen, pygame.Rect(120, 265, 390, 235), 'Alive at cohort end / prey mint, predator rose',
            [([r['species'][s]['survival_rate'] for r in rows], COLORS[s]) for s in SPECIES], generations, font, ceiling=1.)
        draw_trend(screen, pygame.Rect(560, 265, 390, 235), 'Capture fraction of initial prey',
            [([r['capture_fraction'] for r in rows], COLORS['predator'])], generations, font, ceiling=1.)
