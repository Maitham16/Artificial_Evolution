"""Capture ownership, finite-window accounting, genetic isolation, and historical inference."""

from contextlib import redirect_stdout
import copy
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from brain import NeuralNetwork
from body_traits import BodyTraits, WholeGenome, genome_bank_digest, shared_layout_digest
from experiment_predator_prey import (analyze_results, case_name, current_bank, load_models,
                                     opponent_bank, run_study, validate_cohorts)
from food import Food
from main import run
from plot_predator_prey import (build_study_figure, save_lineage_plot, save_population_plot, save_world_image)
from plot_traits import export
from predator_prey import EcologicalCreature, PredatorPreyWorld, first_contact, reflected_path
from simulation import EvolutionSimulation
from world import SIMULATION_STEP


def stopped_brain():
    b=NeuralNetwork(np.random.default_rng(1),input_size=11)
    for p in b.parameters:p[:]=0
    return b


def actor(key,x,y,speed,heading=0,radius=4):
    c=EcologicalCreature(key,x,y,radius,(1,2,3),heading,60,body=BodyTraits(radius=radius))
    c.speed=speed
    return c


class PredatorPhysicsTests(unittest.TestCase):
    def test_opponent_inputs_are_local_and_predators_cannot_see_pellets(self):
        w=PredatorPreyWorld(seed=1,population_size=2,predators=1,food_count=0)
        prey,hunter=w.creatures
        prey.x=200;prey.y=200;prey.heading=0
        hunter.x=250;hunter.y=200;hunter.heading=math.pi
        w.food=[Food(210,200)]
        a=w.get_sensory_inputs(prey);b=w.get_sensory_inputs(hunter)
        self.assertEqual(a.shape,(11,));self.assertGreater(a[0],0);self.assertTrue(np.array_equal(b[:3],np.zeros(3)))
        self.assertEqual(a[10],1);self.assertAlmostEqual(a[9],0)
        hunter.x=500
        self.assertTrue(np.array_equal(w.get_sensory_inputs(prey)[8:],np.zeros(3)))
        self.assertEqual(prey.brain.parameter_count,114)

    def test_hidden_opponents_leave_true_observations_other_inputs_and_costs_intact(self):
        w=PredatorPreyWorld(seed=1,population_size=2,predators=1,food_count=0)
        a,b=w.creatures;a.x=a.y=200;b.x=240;b.y=200
        before=w.get_sensory_inputs(a);cost=a.energy_cost_per_second
        w.opponent_sensors['prey']='hidden';after=w.get_sensory_inputs(a)
        np.testing.assert_array_equal(before[:8],after[:8]);np.testing.assert_array_equal(after[8:],0)
        self.assertTrue(w.perceive_opponents(a).visible);self.assertEqual(cost,a.energy_cost_per_second)

    def test_reflected_paths_match_motion_and_swept_contact_catches_endpoint_misses(self):
        c=actor(1,80,50,200);other=actor(2,94,50,0)
        path=reflected_path(c,.2,100,100)
        hit=first_contact(path,reflected_path(other,.2,100,100),8)
        self.assertAlmostEqual(hit,.03)
        c.move(.2,100,100)
        self.assertAlmostEqual(c.x,72)
        self.assertGreater(abs(c.x-other.x),8)
        last=path[-1]
        self.assertAlmostEqual(last[2]+last[4]*(last[1]-last[0]),c.x)
        self.assertIsNone(first_contact(path,reflected_path(actor(3,10,10,0),.2,100,100),8))

    def test_random_reflective_paths_reproduce_generic_boundary_motion(self):
        rng=np.random.default_rng(240024)
        for i in range(200):
            c=actor(i,float(rng.uniform(4,996)),float(rng.uniform(4,596)),float(rng.uniform(25,100)),float(rng.uniform(0,math.tau)))
            dt=float(rng.uniform(.001,.5));path=reflected_path(c,dt,1000,600);c.move(dt,1000,600)
            end=path[-1];np.testing.assert_allclose([end[2]+end[4]*(end[1]-end[0]),end[3]+end[5]*(end[1]-end[0])],[c.x,c.y],atol=1e-9)

    def test_capture_has_one_owner_and_captured_prey_cannot_eat(self):
        w=PredatorPreyWorld(seed=1,population_size=4,predators=2,food_count=0,episode_seconds=SIMULATION_STEP)
        for c in w.creatures:c.brain=stopped_brain();c.x=c.y=250;c.heading=0
        w.creatures[1].x=800
        w.food=[Food(250,250)]
        w.update(SIMULATION_STEP)
        records={c.creature_id:c for c in [*w.creatures,*w.dead_creatures]}
        self.assertEqual(records[1].death_cause,'predation');self.assertEqual(records[1].food_eaten,0)
        self.assertEqual(records[3].captures,1);self.assertEqual(records[4].captures,0)
        self.assertEqual(len(w.captures),1);self.assertEqual(w.captures[0]['predator_id'],3)
        self.assertAlmostEqual(records[3].capture_assimilated_energy+records[3].wasted_capture_energy,60)
        self.assertEqual(sum(c.food_eaten for c in records.values()),0)

    def test_starved_predator_cannot_capture_or_be_rescued_by_contact(self):
        w=PredatorPreyWorld(seed=1,population_size=2,predators=1,food_count=0,episode_seconds=SIMULATION_STEP)
        for c in w.creatures:c.brain=stopped_brain();c.x=c.y=250
        w.creatures[1].energy=1e-8
        w.update(SIMULATION_STEP)
        self.assertEqual(len(w.captures),0);self.assertEqual(w.dead_creatures[0].death_cause,'starvation')
        self.assertEqual(w.ecosystem_history[0]['species']['prey']['alive_at_end'],1)

    def test_world_swept_capture_keeps_grazing_contacts_rejected_by_endpoints(self):
        w=PredatorPreyWorld(seed=1,population_size=2,predators=1,food_count=0,episode_seconds=SIMULATION_STEP)
        prey,hunter=w.creatures
        for c in w.creatures:c.brain=stopped_brain()
        prey.x=200;prey.y=200;prey.heading=0
        hunter.x=200.5;hunter.y=215.999;hunter.heading=math.pi
        self.assertGreater(math.hypot(prey.x-hunter.x,prey.y-hunter.y),16)
        s=EvolutionSimulation(w,generation_limit=1);s.update(SIMULATION_STEP)
        self.assertEqual(len(w.captures),1)
        self.assertGreater(math.hypot(prey.x-hunter.x,prey.y-hunter.y),16)
        validate_cohorts(s.report(),study=False)

    def test_decisions_use_opponents_at_tick_start(self):
        w=PredatorPreyWorld(seed=1,population_size=2,predators=1,food_count=0,episode_seconds=SIMULATION_STEP)
        prey,pred=w.creatures;prey.x=200;prey.y=200;pred.x=250;pred.y=200
        expected=w.get_sensory_inputs(pred).copy();seen=[]
        class Recorder:
            def forward(self,sensors):seen.append(sensors.copy());return np.zeros(2)
        pred.brain=Recorder();w.update(SIMULATION_STEP)
        np.testing.assert_array_equal(seen[0],expected)

    def test_fixed_step_results_and_pause_are_frame_rate_independent(self):
        a=PredatorPreyWorld(seed=42,population_size=12,predators=3,episode_seconds=1)
        b=PredatorPreyWorld(seed=42,population_size=12,predators=3,episode_seconds=1)
        a.paused=True;a.update(1);self.assertEqual(a.elapsed_time,0);a.paused=False
        a.update(1)
        for _ in range(60):b.update(SIMULATION_STEP)
        self.assertEqual(a.ecosystem_report(),b.ecosystem_report())
        with self.assertRaises(ValueError):a.update(-1)

    def test_horizon_survivors_are_censored_alive_and_can_breed(self):
        w=PredatorPreyWorld(seed=42,population_size=12,predators=3,episode_seconds=.1,food_count=0)
        s=EvolutionSimulation(w,generation_limit=2,auto_advance=False);s.update(.1)
        report=s.report();validate_cohorts(report,study=False)
        row=report['ecosystem']['history'][0]
        self.assertEqual(len(row['creatures']),12)
        self.assertTrue(any(c['alive_at_end'] for c in row['creatures']))
        self.assertTrue(all(c['death_cause'] is None for c in row['creatures'] if c['alive_at_end']))
        self.assertTrue(s.advance_generation());self.assertEqual(w.population_snapshot()['prey'],9)

    def test_linked_inheritance_stays_inside_each_species(self):
        rng=np.random.default_rng(1)
        bank={i:WholeGenome(NeuralNetwork(rng,input_size=11),BodyTraits(35+i,4+i%5,80+10*i)) for i in range(1,11)}
        w=PredatorPreyWorld(seed=42,population_size=10,predators=2,episode_seconds=.05,food_count=0,genomes=bank,mutation_rate=0,body_mutation_rate=0)
        w.update(.05);old=current_bank(w)
        pools={s:set(w.role_evaluations[s].selected_ids) for s in ('prey','predator')}
        self.assertTrue(w.advance_generation())
        for child in w.creatures:
            self.assertIn(child.parent_id,pools[child.species]);self.assertEqual(child.brain,old[child.parent_id].brain)
            self.assertEqual(child.body,old[child.parent_id].body)
            self.assertFalse(np.shares_memory(child.brain.input_weights,old[child.parent_id].brain.input_weights))

    def test_body_mutation_stream_does_not_change_neural_mutation(self):
        a=PredatorPreyWorld(seed=42,episode_seconds=.05,body_mutation_rate=0)
        b=PredatorPreyWorld(seed=42,episode_seconds=.05)
        a.update(.05);b.update(.05);a.advance_generation();b.advance_generation()
        self.assertTrue(all(x.brain==y.brain for x,y in zip(a.creatures,b.creatures)))
        self.assertTrue(any(x.body!=y.body for x,y in zip(a.creatures,b.creatures)))

    def test_parameter_and_controller_combinations_are_validated(self):
        for options in ({'predators':0},{'predators':100},{'episode_seconds':0},{'episode_seconds':.001},
                        {'prey_sensors':'invented'},{'controller':'random'},{'fixed_speed':60}):
            with self.subTest(options=options),self.assertRaises(ValueError):PredatorPreyWorld(**options)


class HistoricalStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.report=run_study(range(2401,2409),generations=3,episode_seconds=.05,models_dir=cls.root/'models')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_full_historical_matrix_masks_and_independent_unit(self):
        r=self.report;a=analyze_results(r)
        self.assertEqual(r['status'],'complete');self.assertEqual(len(r['trials']),8)
        self.assertEqual(len(r['trials'][0]['tests']),11)
        self.assertEqual(np.array(a['capture_fraction_matrix']).shape,(3,3))
        self.assertTrue(all(x['n_pairs']==8 for x in a['primary'].values()))
        self.assertEqual(a['verdict'],'reciprocal_improvement_not_established')
        self.assertNotIn('sign_test_p',a['descriptive_sensor_interventions']['prey_opponent_sensor_effect'])

    def test_all_frozen_pairings_reconstruct_exact_species_components(self):
        t=self.report['trials'][0];metadata,banks=load_models(t['model_file'],t['seed'],3)
        self.assertEqual(metadata,{k:v for k,v in t.items() if k not in ('model_file','model_sha256','tests')})
        for case in t['tests'].values():
            bank=opponent_bank(banks[case['predator_generation']],banks[case['prey_generation']])
            self.assertEqual(genome_bank_digest(bank),case['genomes_sha256'])
        w=PredatorPreyWorld(seed=t['tests']['prey_hidden']['seed'],genomes=banks[3],episode_seconds=.05)
        self.assertEqual(shared_layout_digest(w),t['tests']['prey_hidden']['shared_layout_sha256'])

    def test_reciprocal_verdict_requires_both_species_in_both_opponent_contexts(self):
        # Isolate inference from physics validation; valid physical reports are tested separately.
        r=copy.deepcopy(self.report)
        for t in r['trials']:
            for record in t['tests'].values():
                p=(record['predator_generation']-1)/2;q=(record['prey_generation']-1)/2
                row=record['report']['ecosystem']['history'][0]
                row['capture_fraction']=.4+.2*p-.2*q
                row['species']['prey']['survival_rate']=.3+.2*q-.1*p
        with patch('experiment_predator_prey.validate_cohorts'):
            a=analyze_results(r)
            self.assertEqual(a['verdict'],'reciprocal_improvement_detected')
            self.assertTrue(all(x['holm_adjusted_p']<.05 for x in a['primary'].values()))
            for t in r['trials']:
                for record in t['tests'].values():record['report']['ecosystem']['history'][0]['species']['prey']['survival_rate']=.5
            self.assertEqual(analyze_results(r)['verdict'],'reciprocal_improvement_not_established')

    def test_tampered_energy_masks_layouts_roles_parents_and_components_are_rejected(self):
        for case in ('missing','energy','cause','role','time','layout','mask','parent','seed','genome'):
            r=copy.deepcopy(self.report);t=r['trials'][0];rec=t['tests'][case_name(3,3)];row=rec['report']['ecosystem']['history'][0]
            if case=='missing':t['tests'].pop('prey_hidden')
            elif case=='energy':row['creatures'][0]['sensing_energy']+=10
            elif case=='cause':row['creatures'][0]['death_cause']='predation'
            elif case=='role':row['creatures'][0]['species']='predator'
            elif case=='time':row['population'][-1]['time']+=10
            elif case=='layout':rec['shared_layout_sha256']='wrong'
            elif case=='mask':rec['report']['ecosystem']['opponent_sensors']['prey']='hidden'
            elif case=='parent':t['training']['ecosystem']['transitions'][0]['species']['prey']['parent_ids']=[81]
            elif case=='seed':t['training']['ecosystem']['transitions'][0]['species']['predator']['seeds']['body']=0
            else:rec['genomes_sha256']='wrong'
            with self.subTest(case=case),self.assertRaises(ValueError):analyze_results(r)

    def test_numeric_archive_rejects_changed_genomes_and_preserves_old_outputs(self):
        t=self.report['trials'][0]
        with np.load(t['model_file'],allow_pickle=False) as archive:arrays={k:archive[k] for k in archive.files}
        arrays['g3_0'][0,0,0]+=1
        p=self.root/'corrupt.npz';np.savez_compressed(p,**arrays)
        with self.assertRaises(ValueError):load_models(p,t['seed'],3)
        with self.assertRaises(ValueError):run_study(range(2401,2409),generations=3,episode_seconds=.05,models_dir=self.root/'models')

    def test_exports_and_partial_lineage_exclude_unfinished_cohort(self):
        for suffix in ('png','svg','pdf'):
            p=self.root/f'plot.{suffix}';export(build_study_figure(self.report),p);self.assertGreater(p.stat().st_size,1000)
        save_population_plot(self.report,self.root/'populations.png');save_world_image(self.report,self.root/'world.png')
        r=copy.deepcopy(self.report['trials'][0]['training']);r['ecosystem']['history'].append({'complete':False,'generation':4})
        save_lineage_plot(r,self.root/'lineage.png')
        incomplete=copy.deepcopy(self.report);incomplete['status']='running'
        with self.assertRaises(ValueError):build_study_figure(incomplete)

    def test_headless_cli_exports_both_populations_and_restarts_cleanly(self):
        p=self.root/'cli.json';image=self.root/'cli.png'
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run(headless=True,predator_prey=True,population_size=12,predators=3,episode_seconds=.1,generations=3,seed=42,speed=20,report=p,plot=image),0)
        data=json.loads(p.read_text());validate_cohorts(data,study=False)
        self.assertEqual(data['completed_generations'],3);self.assertNotIn('physical_traits',data)
        self.assertEqual(len(data['ecosystem']['transitions']),2);self.assertGreater(image.stat().st_size,1000)
        for options in ({'traits':True},{'obstacles':True},{'seasons':True},{'fixed_speed':60}):
            with self.assertRaises(ValueError):run(headless=True,frames=1,predator_prey=True,**options)
        w=PredatorPreyWorld(seed=42,episode_seconds=.05);s=EvolutionSimulation(w,generation_limit=3);s.update(.2)
        s.restart(42);self.assertEqual(len(w.ecosystem_history),1);self.assertEqual(len(w.transitions),0);self.assertEqual(s.total_simulated_seconds,0)


if __name__=='__main__':unittest.main()
