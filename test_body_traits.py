"""Genetic linkage, model energy budgets, personalized senses, and frozen factorial tests."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import copy
from dataclasses import FrozenInstanceError
import io
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from brain import NeuralNetwork
from body_traits import (BodyTraits, TraitCreature, TraitWorld, WholeGenome, genome_bank_digest,
                         mutate_body, reproduce_genomes, shared_layout_digest)
from compare_creatures import initial_conditions_digest
from creature import create_population
from experiment_selection import RecordedMutationRNG
from experiment_traits import analyze_results, load_models, run_study, test_bank
from food import Food
from main import run
from plot_traits import build_trait_figure, save_body_map, save_cost_plot, save_lineage_plot, save_trait_plot
from world import SIMULATION_STEP


def short_population(*args):
    population = create_population(*args)
    for c in population: c.lifespan = .005
    return population


def make_creature(body=BodyTraits()):
    return TraitCreature(1, 200, 200, 8, (100, 200, 100), 0, 60, body=body)


def bank_for(body, count=100):
    rng = np.random.default_rng(2300)
    return {k: WholeGenome(NeuralNetwork(rng), body) for k in range(1, count + 1)}


class BodyGeneTests(unittest.TestCase):
    def test_reference_budget_and_trait_costs_are_dimensioned_and_bounded(self):
        b = BodyTraits()
        self.assertEqual(b.powers(), (2., 2.5, .5))
        self.assertEqual(b.capacity, 100)
        self.assertEqual(b.initial_energy, 90)
        self.assertEqual(BodyTraits(radius=4).capacity, 25)
        self.assertEqual(BodyTraits(radius=12).initial_energy, 77.5)
        self.assertGreater(sum(BodyTraits(cruise_speed=100).powers()), sum(b.powers()))
        self.assertGreater(sum(BodyTraits(radius=12).powers()), sum(b.powers()))
        self.assertGreater(sum(BodyTraits(sensory_range=280).powers()), sum(b.powers()))
        self.assertLess(BodyTraits(radius=12).initial_energy, b.initial_energy)
        for args in ((0, 8, 160), (60, 8.5, 160), (60, 13, 160), (60, 8, math.nan), (60, 8, 300)):
            with self.assertRaises(ValueError): BodyTraits(*args)
        with self.assertRaises(FrozenInstanceError): b.radius = 12

    def test_body_mutations_are_seeded_bounded_and_do_not_change_unselected_alleles(self):
        a = mutate_body(BodyTraits(), np.random.default_rng(42), rate=1)
        self.assertEqual(a, mutate_body(BodyTraits(), np.random.default_rng(42), rate=1))
        self.assertEqual(mutate_body(BodyTraits(), np.random.default_rng(42), rate=0), BodyTraits())
        for index in range(100):
            child = mutate_body(BodyTraits(), np.random.default_rng(index), rate=1, scale=1000)
            self.assertTrue(25 <= child.cruise_speed <= 100)
            self.assertTrue(4 <= child.radius <= 12)
            self.assertTrue(60 <= child.sensory_range <= 280)
        class ControlledRNG:
            def random(self, n): return np.array([1., 0., 1.])
            def normal(self, *args): return np.array([.2, .2, .2])
        changed = mutate_body(BodyTraits(), ControlledRNG(), rate=.5)
        self.assertEqual(changed.cruise_speed, 60)
        self.assertEqual(changed.sensory_range, 160)
        self.assertGreater(changed.radius, 8)

    def test_brain_and_body_come_from_the_same_parent_without_aliasing(self):
        rng = np.random.default_rng(1)
        parents = [SimpleNamespace(creature_id=1, brain=NeuralNetwork(rng), body=BodyTraits(30, 4, 80)),
                   SimpleNamespace(creature_id=2, brain=NeuralNetwork(rng), body=BodyTraits(90, 12, 260))]
        children = reproduce_genomes(parents, np.random.default_rng(2), np.random.default_rng(3), offspring_count=8,
                                    mutation_rate=0, body_mutation_rate=0)
        self.assertEqual([c.parent_id for c in children].count(1), 4)
        for child in children:
            parent = parents[child.parent_id - 1]
            self.assertEqual(child.body, parent.body)
            self.assertEqual(child.brain, parent.brain)
            self.assertFalse(np.shares_memory(child.brain.input_weights, parent.brain.input_weights))
            self.assertEqual((child.mutations, child.body_mutations), (0, 0))

    def test_body_rng_does_not_perturb_neural_mutation_draws(self):
        p = [SimpleNamespace(creature_id=1, brain=NeuralNetwork(np.random.default_rng(1)), body=BodyTraits())]
        a = reproduce_genomes(p, np.random.default_rng(2), np.random.default_rng(3), offspring_count=8)
        b = reproduce_genomes(p, np.random.default_rng(2), np.random.default_rng(4), offspring_count=8)
        self.assertTrue(all(x.brain == y.brain for x, y in zip(a, b)))
        self.assertTrue(any(x.body != y.body for x, y in zip(a, b)))


class TraitPhysicsTests(unittest.TestCase):
    def test_clipped_survival_and_component_ledger_conserve_energy(self):
        for body in (BodyTraits(), BodyTraits(100, 12, 280), BodyTraits(25, 4, 60)):
            c = make_creature(body)
            c.update_survival(90)
            self.assertEqual(c.death_cause, 'starvation')
            self.assertAlmostEqual(c.age, body.initial_energy / sum(body.powers()))
            self.assertAlmostEqual(c.basal_energy + c.movement_energy + c.sensing_energy, body.initial_energy)
            self.assertEqual(c.energy, 0)

    def test_meals_above_legacy_100_capacity_and_waste_accounting_work(self):
        body = BodyTraits(radius=12)
        w = TraitWorld(seed=42, population_size=1, food_count=0, genomes=bank_for(body, 1))
        c = w.creatures[0]
        self.assertTrue(c.eat(Food(c.x, c.y)))
        self.assertTrue(c.eat(Food(c.x, c.y)))
        self.assertGreater(c.energy, 100)
        w.food = [Food(c.x, c.y)]
        w._resolve_food_collisions()
        self.assertEqual(c.food_eaten, 3)
        self.assertAlmostEqual(c.energy, body.initial_energy + 60)
        c.energy = c.energy_capacity - 1
        before = c.wasted_food_energy
        self.assertTrue(c.eat(Food(c.x, c.y)))
        self.assertAlmostEqual(c.wasted_food_energy - before, 19)
        self.assertEqual(c.hunger, 0)
        self.assertFalse(c.eat(Food(c.x, c.y)))

    def test_personal_sensory_range_applies_to_food_and_wall_encoding(self):
        small = TraitWorld(seed=42, population_size=1, food_count=0, genomes=bank_for(BodyTraits(sensory_range=60), 1))
        large = TraitWorld(seed=42, population_size=1, food_count=0, genomes=bank_for(BodyTraits(sensory_range=200), 1))
        for w in (small, large):
            c = w.creatures[0];c.x, c.y, c.heading = 500, 300, 0
            w.food = [Food(600, 300)]
        self.assertFalse(small.perceive_food(small.creatures[0]).visible)
        self.assertTrue(large.perceive_food(large.creatures[0]).visible)
        self.assertAlmostEqual(large.get_sensory_inputs(large.creatures[0])[0], .5)
        for w in (small, large): w.creatures[0].x = 24
        self.assertAlmostEqual(small.get_sensory_inputs(small.creatures[0])[6], 16 / 60)
        self.assertAlmostEqual(large.get_sensory_inputs(large.creatures[0])[6], 16 / 200)

    def test_speed_is_gene_controlled_and_cannot_be_disabled_by_throttle(self):
        c = make_creature(BodyTraits(cruise_speed=90))
        c.apply_controls(0, 0)
        self.assertEqual(c.speed, 90)
        before = c.x
        c.move(1, 1000, 600)
        self.assertAlmostEqual(c.x - before, 90)
        self.assertGreater(c.energy_cost_per_second, 5)
        with self.assertRaises(ValueError): TraitWorld(seed=42, fixed_speed=60.)

    def test_shared_anchors_and_food_match_while_treated_physical_bodies_differ(self):
        a = TraitWorld(seed=42, genomes=bank_for(BodyTraits(25, 4, 60)))
        b = TraitWorld(seed=42, genomes=bank_for(BodyTraits(100, 12, 280)))
        self.assertEqual(shared_layout_digest(a), shared_layout_digest(b))
        self.assertNotEqual(initial_conditions_digest(a), initial_conditions_digest(b))
        self.assertEqual(a.food, b.food)
        self.assertTrue(all(math.hypot(c.x - d.x, c.y - d.y) >= 32 for i, c in enumerate(b.creatures) for d in b.creatures[i + 1:]))

    def test_natural_selection_transmits_the_winning_linked_genome(self):
        genomes = bank_for(BodyTraits(), 4)
        genomes[2] = WholeGenome(NeuralNetwork(np.random.default_rng(9)), BodyTraits(90, 11, 240))
        w = TraitWorld(seed=42, population_size=4, food_count=0, genomes=genomes, mutation_rate=0, body_mutation_rate=0)
        for c in w.creatures:
            c.age, c.food_eaten, c.energy, c.death_cause = 20, (10 if c.creature_id == 2 else 0), 0, 'starvation'
        w.dead_creatures, w.creatures = w.creatures, []
        w.update(SIMULATION_STEP)
        self.assertEqual(w.final_evaluation.selected_ids, (2,))
        self.assertTrue(w.advance_generation())
        self.assertTrue(all(c.parent_id == 2 and c.body == genomes[2].body and c.brain == genomes[2].brain for c in w.creatures))


def synthetic_outcomes(report, joint_case=(80, 50)):
    """Consistent mathematical outcomes for inference checks, never experimental evidence."""
    report = copy.deepcopy(report)
    cases = {'joint': joint_case, 'brain_only': (70, 35), 'body_only': (65, 30), 'founder': (60, 20)}
    for trial in report['trials']:
        for test in trial['tests']:
            for condition, record in test['conditions'].items():
                age, meals = cases[condition]
                data = record['report']
                rows = data['physical_traits']['history'][0]['creatures']
                for r in rows:
                    body = BodyTraits.from_vector(r['body'])
                    basal, movement, sensing = [p * age for p in body.powers()]
                    assimilated = basal + movement + sensing - body.initial_energy
                    assert 0 <= assimilated <= 20 * meals
                    r.update(age=age, food_eaten=meals, fitness=age + 10 * meals, final_energy=0., death_cause='starvation',
                             basal_energy=basal, movement_energy=movement, sensing_energy=sensing,
                             assimilated_energy=assimilated, wasted_food_energy=20 * meals - assimilated)
                data['generations'][0].update(mean_fitness=age + 10 * meals, best_fitness=age + 10 * meals,
                    mean_food_eaten=meals, mean_survival_seconds=age, mean_speed=float(np.mean([r['body'][0] for r in rows])),
                    duration_seconds=age + SIMULATION_STEP, survivors_at_checkpoint=100, survival_rate=1.)
    return report


class TraitStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory();cls.root = Path(cls.directory.name)
        with patch('world.create_population', side_effect=short_population):
            cls.report = run_study(range(2301, 2313), generations=2, models_dir=cls.root / 'models')

    @classmethod
    def tearDownClass(cls): cls.directory.cleanup()

    def test_complete_factorial_study_uses_independent_seed_denominator(self):
        r = self.report
        self.assertEqual(r['analysis']['independent_seed_groups'], 12)
        self.assertEqual(r['protocol']['test_cohorts'], 96)
        for data in r['analysis']['environments'].values():
            self.assertTrue(all(x['n_pairs'] == 12 for x in data['primary_fitness'].values()))
            self.assertNotIn('sign_test_p', data['descriptive_brain_body_interaction'])
            self.assertIsNone(data['condition_means']['founder']['food_energy_efficiency'])

    def test_controlled_body_benefit_passes_and_brain_gains_alone_do_not_imply_body_benefit(self):
        positive = analyze_results(synthetic_outcomes(self.report))
        neutral_body = analyze_results(synthetic_outcomes(self.report, joint_case=(70, 35)))
        for environment in positive['environments']:
            self.assertEqual(positive['environments'][environment]['primary_fitness']['brain_only']['conclusion'], 'higher')
            self.assertEqual(neutral_body['environments'][environment]['primary_fitness']['brain_only']['conclusion'], 'inconclusive')
            self.assertEqual(neutral_body['environments'][environment]['primary_fitness']['founder']['conclusion'], 'higher')

    def test_frozen_interventions_use_exact_brain_and_body_components(self):
        t = self.report['trials'][0]
        _, banks = load_models(t['model_file'], 2301, 2)
        for name in ('joint', 'brain_only', 'body_only', 'founder'):
            bank = test_bank(banks, name)
            brain_source = banks['evolved' if name in ('joint', 'brain_only') else 'founder']
            body_source = banks['evolved' if name in ('joint', 'body_only') else 'founder']
            self.assertEqual(genome_bank_digest(bank), t['intervention_hashes'][name])
            self.assertTrue(all(bank[k].brain == brain_source[k].brain and bank[k].body == body_source[k].body for k in bank))

    def test_linked_genome_replay_reproduces_neural_and_physical_mutations(self):
        t = self.report['trials'][0]
        metadata, banks = load_models(t['model_file'], 2301, 2)
        bank = {k: g.copy() for k, g in banks['founder'].items()}
        for trace in metadata['training']['physical_traits']['transitions']:
            a, b = RecordedMutationRNG(trace['brain_mutation_seed']), RecordedMutationRNG(trace['body_mutation_seed'])
            children = reproduce_genomes([SimpleNamespace(creature_id=k, brain=bank[k].brain, body=bank[k].body) for k in trace['parent_ids']], a, b)
            self.assertEqual(a.digest.hexdigest(), trace['brain_draws_sha256'])
            self.assertEqual(b.digest.hexdigest(), trace['body_draws_sha256'])
            self.assertEqual([c.body_mutations for c in children], trace['body_mutation_counts'])
            bank = {i: WholeGenome(c.brain, c.body) for i, c in enumerate(children, 1)}
        self.assertEqual(genome_bank_digest(bank), genome_bank_digest(banks['evolved']))
        with self.assertRaises(ValueError): run_study(range(2301, 2313), generations=2, models_dir=self.root / 'models')

    def test_mismatched_scenarios_tampered_energy_and_inheritance_are_rejected(self):
        for case in ('seed', 'condition', 'layout', 'energy', 'body', 'parent', 'hash'):
            r = copy.deepcopy(self.report);t = r['trials'][0];c = t['tests'][0]['conditions']['joint']
            row = c['report']['physical_traits']['history'][0]['creatures'][0]
            if case == 'seed': r['trials'].pop()
            elif case == 'condition': t['tests'][0]['conditions'].pop('brain_only')
            elif case == 'layout': c['shared_layout_sha256'] = 'changed'
            elif case == 'energy': row['movement_energy'] += 10
            elif case == 'body': row['body'][1] = 4.5
            elif case == 'parent': t['training']['physical_traits']['transitions'][0]['parent_ids'] = [99]
            else: c['genomes_sha256'] = 'changed'
            with self.subTest(case=case), self.assertRaises(ValueError): analyze_results(r)

    def test_figures_export_and_partial_lineages_plot_only_completed_cohorts(self):
        for suffix in ('png', 'svg', 'pdf'):
            p = self.root / f'study.{suffix}';save_trait_plot(self.report, p)
            self.assertGreater(p.stat().st_size, 1000)
        save_cost_plot(self.root / 'costs.png')
        with patch('world.create_population', side_effect=short_population):
            save_body_map(self.report, self.root / 'bodies.png')
        partial = copy.deepcopy(self.report['trials'][0]['training'])
        partial['physical_traits']['history'].append({'generation': 3, 'complete': False})
        save_lineage_plot(partial, self.root / 'lineage.png')
        r = copy.deepcopy(self.report);r['status'] = 'running'
        with self.assertRaises(ValueError): build_trait_figure(r)

    def test_parallel_results_and_running_checkpoints_are_deterministic(self):
        states = []
        with patch('world.create_population', side_effect=short_population), patch('experiment_traits.ProcessPoolExecutor', ThreadPoolExecutor):
            r = run_study([2301, 2302], generations=2, workers=2, models_dir=self.root / 'parallel', checkpoint=lambda x: states.append(x['status']))
        subset = copy.deepcopy(self.report);subset['protocol']['seeds'] = [2301, 2302];subset['trials'] = subset['trials'][:2]
        self.assertEqual(r['analysis'], analyze_results(subset))
        self.assertEqual(states, ['running', 'running', 'running', 'complete'])

    def test_headless_mode_exports_heritable_traits_with_custom_settings(self):
        import json
        p, figure = self.root / 'cli.json', self.root / 'cli.png'
        with patch('world.create_population', side_effect=short_population), redirect_stdout(io.StringIO()):
            self.assertEqual(run(headless=True, traits=True, seed=42, generations=2, speed=20, population_size=12,
                                 food_count=0, report=p, plot=figure), 0)
        data = json.loads(p.read_text())
        self.assertEqual(data['completed_generations'], 2)
        self.assertTrue(any(r != [60., 8., 160.] for r in data['physical_traits']['history'][1]['birth_bodies']))
        self.assertGreater(figure.stat().st_size, 1000)
        for options in ({'fixed_speed': 60.}, {'seasons': True}, {'obstacles': True}):
            with self.assertRaises(ValueError): run(headless=True, frames=1, traits=True, **options)


if __name__ == '__main__': unittest.main()
