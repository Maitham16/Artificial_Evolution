"""Mechanistic ground truths, passive-physics equivalence, and complete-data checks."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from brain import NeuralNetwork
from compare_creatures import complete_generation, genome_digest, initial_conditions_digest
from inspect_brains import (BANKS, TRACE_COLUMNS, TRACE_IDS, RecordingWorld, analyze_results, decision_effects,
                           load_trace, network_details, run_study, save_trace)
from plot_brains import build_brain_figure, save_brain_plot, save_brain_viewer
from simulation import EvolutionSimulation
from world import World


class NetworkMechanismTests(unittest.TestCase):
    def setUp(self):
        self.brain = NeuralNetwork(np.random.default_rng(2001))
        self.inputs = np.array([.6, .3, 1, .4, .8, .9, 1, .5])

    def test_forward_matches_existing_controller_without_mutation(self):
        original = self.brain.copy()
        states = np.array([self.inputs, self.inputs * .5])
        h, y, j, a = network_details(self.brain, states)
        np.testing.assert_allclose(y, np.array([self.brain.forward(x) for x in states]), rtol=0, atol=1e-15)
        np.testing.assert_array_equal(network_details(self.brain, self.inputs)[1], self.brain.forward(self.inputs))
        self.assertEqual(h.shape, (2, 8))
        self.assertEqual(j.shape, (2, 8, 2))
        self.assertEqual(a.shape, (2, 8, 2))
        self.assertEqual(original, self.brain)

    def test_exact_jacobian_matches_central_numerical_perturbations(self):
        _, _, jacobian, _ = network_details(self.brain, self.inputs)
        for i in range(8):
            step = np.eye(8)[i] * 1e-6
            expected = (self.brain.forward(self.inputs + step) - self.brain.forward(self.inputs - step)) / 2e-6
            np.testing.assert_allclose(jacobian[i], expected, atol=2e-10, rtol=1e-7)

    def test_known_one_path_identifies_the_only_influential_input_and_unit(self):
        for p in self.brain.parameters:
            p[:] = 0
        self.brain.input_weights[1, 3] = 2
        self.brain.output_weights[3, 0] = 1.5
        h, y, j, ablations = network_details(self.brain, self.inputs)
        self.assertAlmostEqual(y[0], np.tanh(1.5 * np.tanh(.6)))
        self.assertEqual(np.flatnonzero(j[:, 0]).tolist(), [1])
        self.assertEqual(np.flatnonzero(ablations[:, 0]).tolist(), [3])
        self.assertAlmostEqual(ablations[3, 0], y[0])

    def test_bearing_mirror_reverses_a_known_food_seeking_policy(self):
        for p in self.brain.parameters:
            p[:] = 0
        self.brain.input_weights[1, 0] = 1
        self.brain.output_weights[0, 0] = 1
        effects = decision_effects(self.brain, self.inputs)[0, :, 0]
        turn = self.brain.forward(self.inputs)[0]
        np.testing.assert_allclose(effects, [turn, 2 * turn, 0, 0])

    def test_invalid_inputs_are_rejected(self):
        for x in (np.zeros(7), np.full(8, np.nan), np.zeros((1, 1, 8))):
            with self.assertRaises(ValueError):
                network_details(self.brain, x)

    def test_saturated_unit_has_small_local_derivative_but_large_finite_effect(self):
        for p in self.brain.parameters:
            p[:] = 0
        self.brain.hidden_bias[0] = 10
        self.brain.input_weights[3, 0] = 1
        self.brain.output_weights[0, 0] = 2
        _, _, j, ablations = network_details(self.brain, self.inputs)
        self.assertLess(abs(j[3, 0]), 1e-7)
        self.assertGreater(abs(ablations[0, 0]), .9)


class PassiveRecordingTests(unittest.TestCase):
    def test_recording_does_not_change_physics_rng_or_frozen_brains(self):
        plain = World(seed=2020, fixed_speed=60, evolution_enabled=False)
        recorded = RecordingWorld(seed=2020, fixed_speed=60, evolution_enabled=False)
        self.assertEqual(initial_conditions_digest(plain), initial_conditions_digest(recorded))
        digest = genome_digest(plain.creatures)
        # Includes control, meal ownership/replenishment, energy, headings, and walls.
        for _ in range(240):
            plain.update(1 / 60)
            recorded.update(1 / 60)
        self.assertEqual(initial_conditions_digest(plain), initial_conditions_digest(recorded))
        self.assertEqual(genome_digest(recorded.creatures), digest)
        for a, b in zip(plain.creatures, recorded.creatures):
            self.assertEqual((a.age, a.food_eaten, a.turn_rate, a.energy, a.x, a.y),
                             (b.age, b.food_eaten, b.turn_rate, b.energy, b.x, b.y))
        for key in TRACE_IDS:
            frames = np.array(recorded.traces[key])
            self.assertEqual(frames.shape, (20, len(TRACE_COLUMNS)))
            np.testing.assert_allclose(np.diff(frames[:, 0]), .2)
        self.assertEqual(len(recorded.samples), 100)
        self.assertTrue(all(len(v) == 4 for v in recorded.samples.values()))


class InspectionStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        original = RecordingWorld._start_generation
        def short_fixture(world, *args, **kwargs):
            original(world, *args, **kwargs)
            for creature in world.creatures:
                creature.lifespan = .04
        cls.checkpoints = []
        with patch.object(RecordingWorld, '_start_generation', short_fixture):
            cls.report = run_study([1601, 1602], trace_dir=cls.root / 'traces',
                                   checkpoint=lambda r: cls.checkpoints.append((r['status'], len(r['trials']))))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_complete_study_freezes_cohorts_and_uses_independent_seed_denominator(self):
        self.assertEqual(self.report['status'], 'complete')
        self.assertEqual(self.report['protocol']['training_cohorts'], 0)
        self.assertEqual(self.report['protocol']['planned_test_cohorts'], 8)
        self.assertEqual(self.report['analysis']['independent_seed_groups'], 2)
        self.assertEqual(self.checkpoints[0], ('running', 0))
        self.assertEqual(self.checkpoints[-1], ('complete', 2))
        for environment in ('uniform', 'clustered'):
            row = self.report['analysis']['environments'][environment]['mean_fitness']
            self.assertEqual(row['n_pairs'], 2)
            self.assertNotIn('sign_test_p', row)
            self.assertNotIn('conclusion', row)

    def test_missing_or_duplicate_data_and_unmatched_layouts_are_rejected(self):
        for edit in ('missing_seed', 'missing_brain', 'duplicate_env', 'layout', 'genome', 'denominator'):
            r = copy.deepcopy(self.report)
            c = r['trials'][0]['tests'][0]['conditions']['evolved']
            if edit == 'missing_seed': r['trials'].pop()
            elif edit == 'missing_brain': c['brains'].pop()
            elif edit == 'duplicate_env': r['trials'][0]['tests'][1]['environment'] = 'uniform'
            elif edit == 'layout': c['initial_conditions'] = 'changed'
            elif edit == 'genome': c['genomes_sha256'] = 'changed'
            else: c['brains'][0]['off_axis_visible_samples'] = 99999
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                analyze_results(r)

    def test_trace_numeric_roundtrip_and_overwrite_protection(self):
        path = self.report['trials'][0]['trace_file']
        metadata, arrays = load_trace(path)
        self.assertEqual(metadata['trace_ids'], list(TRACE_IDS))
        self.assertTrue(all(a.dtype.kind == 'f' for a in arrays.values()))
        with self.assertRaises(ValueError): save_trace(path, metadata, arrays)
        arrays['uniform_evolved_1'][0, 1] = np.nan
        invalid = self.root / 'invalid.npz'
        save_trace(invalid, metadata, arrays)
        with self.assertRaises(ValueError): load_trace(invalid)

    def test_plot_and_viewer_export_actual_traces_and_all_twelve_examples(self):
        for suffix in ('png', 'svg', 'pdf'):
            output = self.root / f'overview.{suffix}'
            save_brain_plot(self.report, output)
            self.assertGreater(output.stat().st_size, 1000)
        path = self.root / 'viewer.html'
        save_brain_viewer(self.report, path)
        text = path.read_text()
        payload = json.loads(text.split('const DATA=', 1)[1].split(';\nconst $=', 1)[0])
        self.assertEqual(len(payload['conditions']), 12)
        self.assertEqual(payload['seed'], 1601)
        self.assertEqual(len(payload['columns']), 42)
        self.assertNotIn('/*BRAIN_DATA*/null', text)
        self.assertNotIn('<script src=', text)

    def test_plot_rejects_running_report_changed_focus_and_corrupted_trace(self):
        for case in ('running', 'focus', 'hash'):
            r = copy.deepcopy(self.report)
            if case == 'running': r['status'] = 'running'
            elif case == 'focus': r['protocol']['focus_creature_id'] = 34
            else: r['trials'][0]['trace_sha256'] = 'changed'
            with self.subTest(case=case), self.assertRaises(ValueError):
                build_brain_figure(r)

    def test_existing_recordings_are_preserved_before_any_new_work(self):
        with self.assertRaises(ValueError):
            run_study([1601, 1602], trace_dir=self.root / 'traces')
        with self.assertRaises(ValueError):
            run_study([1601, 1601], trace_dir=self.root / 'new')


if __name__ == '__main__':
    unittest.main()
