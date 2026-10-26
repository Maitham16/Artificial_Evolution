"""Season timing, bounded habitats, maturity gates, extinction, and archive diagnostics."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from analyze_intelligence import bank_digest
from compare_creatures import complete_generation, genome_digest
from creature import create_population
from experiment_seasons import analyze_results, load_models, run_study
from main import run
from plot_seasons import build_study_figure, save_cluster_paths, save_lineage_plot, save_season_plot
from seasons import DEFAULT_FOOD, SeasonalWorld, moving_centers, season_context
from simulation import EvolutionSimulation
from world import SIMULATION_STEP, World


def short_population(*args):
    population = create_population(*args)
    for c in population:
        c.lifespan = .005
    return population


class SeasonalHabitatTests(unittest.TestCase):
    def test_food_schedule_repeats_and_season_duration_is_in_generations(self):
        rows = [season_context(g, season_length=2) for g in range(1, 17)]
        self.assertEqual([r['food_count'] for r in rows], [n for n in DEFAULT_FOOD for _ in range(2)] * 2)
        self.assertEqual(rows[0]['cycle'], 1)
        self.assertEqual(rows[8]['cycle'], 2)
        self.assertEqual(season_context(4, food_counts=(0, 1, 2, 3))['food_count'], 3)

    def test_cluster_motion_is_bounded_reproducible_and_can_be_disabled(self):
        original = moving_centers(42, 1, 1000, 600, 120)
        self.assertEqual(original, moving_centers(42, 8, 1000, 600, 0))
        previous = original
        for g in range(2, 30):
            centers = moving_centers(42, g, 1000, 600, 120)
            self.assertEqual(centers, moving_centers(42, g, 1000, 600, 120))
            self.assertNotEqual(centers, previous)
            self.assertTrue(all(200 <= x <= 800 and 120 <= y <= 480 for x, y in centers))
            self.assertTrue(all(np.linalg.norm(np.subtract(a, b)) <= 120 + 1e-9 for a, b in zip(centers, previous)))
            previous = centers

    def test_actual_food_is_placed_using_seasonal_centers_before_first_spawn(self):
        world = SeasonalWorld(seed=42, fixed_speed=60.0)
        plain = World(seed=42, fixed_speed=60.0, food_distribution='clustered')
        self.assertEqual(genome_digest(world.creatures), genome_digest(plain.creatures))
        plain.food_cluster_centers = list(world.food_cluster_centers)
        plain.food = []
        plain._food_rng = random.Random('food:42')
        for _ in range(world.food_count):
            plain.food.append(plain._spawn_food())
        self.assertEqual(plain.food, world.food)
        self.assertEqual(len(world.food), 150)
        pellet = world.food[0]
        world.creatures[0].x, world.creatures[0].y, world.creatures[0].energy = pellet.x, pellet.y, 50
        world._resolve_food_collisions()
        self.assertGreater(world.total_food_eaten, 0)
        self.assertEqual(len(world.food), 150)
        self.assertEqual(world.food_cluster_centers, moving_centers(42, 1, 1000, 600, 120))

    def test_actual_births_apply_new_food_and_cluster_context_each_generation(self):
        def brief(*args):
            population = create_population(*args)
            for c in population: c.lifespan = .03
            return population
        with patch('world.create_population', side_effect=brief):
            world = SeasonalWorld(seed=42, fixed_speed=60.0, reproductive_age=.02)
            simulation = EvolutionSimulation(world, generation_limit=5, auto_advance=False)
            for g in range(1, 6):
                self.assertEqual(len(world.food), season_context(g)['food_count'])
                self.assertEqual(world.food_cluster_centers, moving_centers(42, g, 1000, 600, 120))
                complete_generation(simulation)
                self.assertFalse(world.lineage_extinct)
                if g < 5: self.assertTrue(simulation.advance_generation())
        self.assertEqual(len(world.environment_history), 5)
        self.assertEqual(len(world.transitions), 4)

    def test_bad_schedule_and_extinction_parameters_are_rejected(self):
        for kwargs in ({'season_length':0}, {'season_food':(1, 2)}, {'season_food':(1, 2, -1, 4)},
                       {'cluster_shift':float('nan')}, {'reproductive_age':0}, {'evolution_enabled':False}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                SeasonalWorld(seed=42, **kwargs)


class LineageExtinctionTests(unittest.TestCase):
    def test_zero_food_causes_permanent_lineage_extinction_and_restart_resets_it(self):
        world = SeasonalWorld(seed=42, fixed_speed=60.0, season_food=(0, 0, 0, 0))
        simulation = EvolutionSimulation(world, generation_limit=8, auto_advance=True)
        complete_generation(simulation)
        self.assertTrue(world.lineage_extinct)
        self.assertTrue(simulation.finished)
        self.assertEqual(world.extinction_generation, 1)
        self.assertEqual(world.final_evaluation.selected_ids, ())
        self.assertFalse(simulation.advance_generation())
        frozen = simulation.report()
        simulation.update(500)
        self.assertEqual(simulation.report(), frozen)
        simulation.restart(42)
        self.assertFalse(world.lineage_extinct)
        self.assertFalse(simulation.finished)
        self.assertEqual(len(world.environment_history), 1)
        self.assertEqual(len(world.creatures), 100)

    def test_immature_high_fitness_cannot_displace_mature_parent(self):
        world = SeasonalWorld(seed=42, population_size=6, fixed_speed=60.0, mutation_rate=0)
        parent = world.creatures[0].brain.copy()
        for c in world.creatures:
            c.age = 61 if c.creature_id == 1 else 10
            c.food_eaten = 0 if c.creature_id == 1 else 100
            c.energy, c.death_cause = 0, 'starvation'
        world.dead_creatures, world.creatures = world.creatures, []
        world.update(SIMULATION_STEP)
        self.assertEqual(world.final_evaluation.selected_ids, (1,))
        self.assertEqual(world.environment_history[-1]['eligible_parent_count'], 1)
        self.assertTrue(world.advance_generation())
        self.assertTrue(all(c.parent_id == 1 and c.brain == parent for c in world.creatures))
        self.assertEqual(len(world.creatures), 6)

    def test_cohort_death_with_mature_candidates_is_not_lineage_extinction(self):
        world = SeasonalWorld(seed=42, population_size=4, fixed_speed=60.0)
        for c in world.creatures:
            c.age, c.energy, c.death_cause = 70, 0, 'old_age'
        world.dead_creatures, world.creatures = world.creatures, []
        world.update(SIMULATION_STEP)
        self.assertFalse(world.lineage_extinct)
        self.assertEqual(len(world.final_evaluation.selected_ids), 1)
        self.assertTrue(world.advance_generation())

    def test_environment_reports_are_snapshots_and_preserve_partial_context(self):
        world = SeasonalWorld(seed=42)
        s = EvolutionSimulation(world)
        report = s.report()
        self.assertEqual(report['generations'], [])
        self.assertFalse(report['seasonal_environment']['history'][0]['complete'])
        report['seasonal_environment']['history'][0]['food_count'] = -1
        self.assertEqual(world.food_count, 150)
        self.assertEqual(s.report()['seasonal_environment']['history'][0]['food_count'], 150)


class SeasonalStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        with patch('world.create_population', side_effect=short_population):
            cls.report = run_study([11, 22], generations=4, models_dir=cls.root / 'models')

    @classmethod
    def tearDownClass(cls): cls.directory.cleanup()

    def test_extinction_is_retained_without_imputing_unborn_cohorts(self):
        a = self.report['analysis']
        self.assertEqual(a['extinct_lineages'], 2)
        self.assertEqual(a['actual_training_cohorts'], 2)
        self.assertEqual(a['complete_diagnostic_cohorts'], 8)
        self.assertEqual(a['by_generation'][1]['cohorts_reached'], 0)
        self.assertIsNone(a['by_generation'][1]['mean_fitness_among_reached'])
        self.assertTrue(all(row['retention_fraction'] == 0 for row in a['by_generation']))
        for result in a['diagnostics'].values():
            self.assertEqual(result['mean_fitness']['n_pairs'], 2)
            self.assertNotIn('sign_test_p', result['mean_fitness'])
        for trial in self.report['trials']:
            self.assertEqual(trial['genome_hashes']['founder'], trial['genome_hashes']['last_cohort'])
            self.assertTrue(trial['training']['seasonal_environment']['lineage_extinct'])

    def test_models_load_finite_numeric_arrays_and_existing_archives_are_preserved(self):
        trial = self.report['trials'][0]
        metadata, banks = load_models(trial['model_file'], 11, 4)
        self.assertEqual(metadata['last_birth_generation'], 1)
        self.assertEqual(bank_digest(banks['founder']), trial['genome_hashes']['founder'])
        with self.assertRaises(ValueError): load_models(trial['model_file'], 22, 4)
        with self.assertRaises(ValueError): run_study([11, 22], generations=4, models_dir=self.root / 'models')

    def test_missing_and_inconsistent_history_diagnostics_and_parent_eligibility_fail(self):
        for case in ('missing_seed', 'season', 'maturity', 'extinction', 'diagnostic', 'layout'):
            r = copy.deepcopy(self.report);trial = r['trials'][0];env=trial['training']['seasonal_environment']
            if case == 'missing_seed': r['trials'].pop()
            elif case == 'season': env['history'][0]['food_count'] = 999
            elif case == 'maturity': env['history'][0]['selected_ids'] = [1]
            elif case == 'extinction': env['lineage_extinct'] = False
            elif case == 'diagnostic': trial['tests'].pop()
            else: trial['tests'][0]['conditions']['founder']['initial_conditions'] = 'changed'
            with self.subTest(case=case), self.assertRaises(ValueError): analyze_results(r)

    def test_parallel_results_are_deterministic_and_checkpoints_remain_running(self):
        states = []
        with patch('world.create_population', side_effect=short_population), patch('experiment_seasons.ProcessPoolExecutor', ThreadPoolExecutor):
            r = run_study([11, 22], generations=4, workers=2, models_dir=self.root / 'parallel',
                          checkpoint=lambda x: states.append(x['status']))
        self.assertEqual(r['analysis'], self.report['analysis'])
        self.assertEqual(states, ['running', 'running', 'running', 'complete'])

    def test_plots_export_study_and_individual_lineage_and_reject_partial_studies(self):
        for suffix in ('png', 'svg', 'pdf'):
            p = self.root / f'study.{suffix}';save_season_plot(self.report, p)
            self.assertGreater(p.stat().st_size, 1000)
        save_lineage_plot(self.report['trials'][0]['training'], self.root / 'lineage.png')
        save_cluster_paths(self.report, self.root / 'clusters.png')
        r = copy.deepcopy(self.report);r['status']='running'
        with self.assertRaises(ValueError): build_study_figure(r)

    def test_headless_seasonal_mode_stops_at_extinction_and_exports_context(self):
        report, plot, screenshot = self.root / 'cli.json', self.root / 'cli.png', self.root / 'world.png'
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run(headless=True, seasons=True, generations=8, speed=20, seed=42,
                                 season_food=(0, 0, 0, 0), report=report, plot=plot, screenshot=screenshot), 0)
        data = json.loads(report.read_text())
        self.assertTrue(data['seasonal_environment']['lineage_extinct'])
        self.assertEqual(data['completed_generations'], 1)
        self.assertGreater(plot.stat().st_size, 1000)
        self.assertGreater(screenshot.stat().st_size, 1000)


if __name__ == '__main__': unittest.main()
