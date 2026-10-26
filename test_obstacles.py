"""Obstacle geometry, costs, backward compatibility, and controlled inference checks."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import copy
import io
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from analyze_intelligence import bank_digest
from brain import NeuralNetwork,food_inputs_for_control
from compare_creatures import genome_digest,initial_conditions_digest
from creature import create_population
from experiment_obstacles import analyze_results,load_models,run_study
from experiment_selection import RecordedMutationRNG
from main import run
from obstacles import Barrier,Danger,ObstacleCreature,ObstacleWorld,ray_box
from plot_obstacles import build_study_figure,save_layout_plot,save_lineage_plot,save_obstacle_plot
from reproduction import reproduce_brains
from world import SIMULATION_STEP


def creature(**changes):
    values=dict(creature_id=1,x=50.,y=100.,radius=6,color=(100,200,100),heading=0.,speed=60.)
    values.update(changes);c=ObstacleCreature(**values);c.barriers=[];c.dangers=[];return c


def short_population(*args):
    population=create_population(*args)
    for c in population:c.lifespan=.005
    return population


class ExpandedBrainTests(unittest.TestCase):
    def test_default_eight_input_draws_are_bitwise_compatible(self):
        brain=NeuralNetwork(np.random.default_rng(42));rng=np.random.default_rng(42)
        expected=[rng.normal(0,1/math.sqrt(8),(8,8)),rng.normal(0,.1,8),rng.normal(0,1/math.sqrt(8),(8,2)),rng.normal(0,.1,2)]
        for actual,reference in zip(brain.parameters,expected):np.testing.assert_array_equal(actual,reference)
        self.assertEqual(brain.parameter_count,90)

    def test_sixteen_input_copy_mutation_and_food_interventions_preserve_extra_inputs(self):
        b=NeuralNetwork(np.random.default_rng(42),input_size=16);self.assertEqual(b.parameter_count,154)
        child=b.mutated_copy(np.random.default_rng(7),mutation_rate=1)
        self.assertEqual(child.input_weights.shape,(16,8));self.assertEqual(child.forward(np.zeros(16)).shape,(2,))
        self.assertFalse(np.shares_memory(b.input_weights,child.input_weights))
        x=np.linspace(0,1,16);x[2]=1
        for mode in ('hidden','mirrored'):
            y=food_inputs_for_control(x,mode);np.testing.assert_array_equal(y[3:],x[3:])
        with self.assertRaises(ValueError):b.forward(np.zeros(8))
        for size in (7,True,8.5):
            with self.assertRaises(ValueError):NeuralNetwork(np.random.default_rng(1),input_size=size)


class ObstaclePhysicsTests(unittest.TestCase):
    def test_slab_geometry_reports_entry_normals_and_ignores_leaving_contacts(self):
        bounds=(100,50,120,150)
        self.assertEqual(ray_box(50,100,1,0,bounds),(50,(-1.,0.)))
        self.assertEqual(ray_box(150,100,-1,0,bounds),(30,(1.,0.)))
        self.assertIsNone(ray_box(50,20,1,0,bounds))
        self.assertIsNone(ray_box(100,100,-1,0,bounds))

    def test_swept_motion_prevents_tunneling_and_charges_one_impact(self):
        c=creature(speed=600);c.barriers=[Barrier(100,50,10,100)]
        c.move(.2,1000,600)
        self.assertAlmostEqual(c.x,18,places=5);self.assertAlmostEqual(c.heading,math.pi)
        self.assertEqual(c.collisions,1);self.assertEqual(c.energy,98)
        self.assertFalse(c.barriers[0].overlaps(c.x,c.y,c.radius))
        c.move(.01,1000,600);self.assertEqual(c.collisions,1)

    def test_outer_boundaries_reflect_without_internal_collision_penalty(self):
        c=creature(x=990,speed=60);c.move(.5,1000,600)
        self.assertAlmostEqual(c.x,968,places=5);self.assertEqual(c.collisions,0);self.assertEqual(c.energy,100)

    def test_hazard_cost_uses_actual_lived_time_and_labels_fatal_damage(self):
        c=creature();c.dangers=[Danger(c.x,c.y,30)]
        c.update_survival(2)
        self.assertAlmostEqual(c.energy,66);self.assertEqual(c.hazard_seconds,2);self.assertEqual(c.fitness,-8)
        c=creature(energy=17);c.dangers=[Danger(c.x,c.y,30)];c.update_survival(2)
        self.assertAlmostEqual(c.age,1);self.assertAlmostEqual(c.hazard_seconds,1)
        self.assertEqual(c.death_cause,'hazard');self.assertEqual(c.energy,0)

    def test_collision_death_is_registered_immediately_and_cannot_eat(self):
        w=ObstacleWorld(seed=42,fixed_speed=60.,food_count=0);c=w.creatures[0]
        c.x,c.y,c.heading,c.energy=50,100,0,1
        c.barriers=[Barrier(56.5,50,10,100)];w.creatures=[c]
        w.update(SIMULATION_STEP)
        self.assertEqual(w.creatures,[]);self.assertEqual(w.dead_creatures,[c])
        self.assertEqual(c.death_cause,'collision');self.assertEqual(c.collisions,1)
        self.assertLess(w.final_evaluation.mean_fitness,0)

    def test_safe_placements_and_sensor_interventions_have_identical_physical_starts(self):
        a=ObstacleWorld(seed=42,fixed_speed=60.);b=ObstacleWorld(seed=42,fixed_speed=60.,risk_sensor_mode='hidden')
        self.assertEqual(initial_conditions_digest(a),initial_conditions_digest(b))
        self.assertEqual(genome_digest(a.creatures),genome_digest(b.creatures))
        self.assertTrue(all(not a.unsafe(c.x,c.y,c.radius+3) for c in a.creatures))
        self.assertTrue(all(not a.unsafe(f.x,f.y,f.radius+2) for f in a.food))
        np.testing.assert_array_equal(a.get_sensory_inputs(a.creatures[0])[:8],b.get_sensory_inputs(b.creatures[0])[:8])
        np.testing.assert_array_equal(b.get_sensory_inputs(b.creatures[0])[8:],[1,1,1,1,1,0,0,0])

    def test_rays_are_radius_and_orientation_aware_and_hazards_have_bearing(self):
        w=ObstacleWorld(seed=42,food_count=0);c=w.creatures[0]
        c.x,c.y,c.heading,c.radius=500.,300.,0.,6
        w.barriers=[Barrier(522,200,10,200)];w.dangers=[Danger(600,300,20)];c.barriers=w.barriers;c.dangers=w.dangers
        x=w.get_sensory_inputs(c)
        np.testing.assert_allclose(x[8:13],[1,math.sqrt(2)*.1,.1,math.sqrt(2)*.1,1],atol=1e-12)
        self.assertAlmostEqual(x[13],1-74/160);self.assertEqual(x[14],0);self.assertEqual(x[15],0)
        c.heading=math.pi/2;x=w.get_sensory_inputs(c)
        self.assertAlmostEqual(x[8],.1);self.assertAlmostEqual(x[14],-.5)
        self.assertTrue(np.all(np.isfinite(x)));self.assertTrue(np.all(np.abs(x)<=1))
        c.x,c.y=600,300
        self.assertEqual(w.get_sensory_inputs(c)[14],0.)

    def test_food_replenishment_stays_clear_of_geometry(self):
        w=ObstacleWorld(seed=42,fixed_speed=60.);c=w.creatures[0]
        pellet=next(f for f in w.food if not w.unsafe(f.x,f.y,c.radius+3))
        c.x,c.y,c.energy=pellet.x,pellet.y,50;w._resolve_food_collisions()
        self.assertGreater(w.total_food_eaten,0);self.assertEqual(len(w.food),150)
        self.assertTrue(all(not w.unsafe(f.x,f.y,f.radius+2) for f in w.food))


def synthetic_outcomes(report, evolved=(80,12,1,1)):
    """Controlled statistical ground truth, never used as experimental evidence."""
    report=copy.deepcopy(report)
    cases={'evolved':evolved,'risk_hidden':(70,8,5,5),'founder':(60,5,10,10)}
    for trial in report['trials']:
        for test in trial['tests']:
            for condition,record in test['conditions'].items():
                age,food,collisions,hazard=cases[condition];data=record['report'];context=data['obstacle_environment']['history'][0]
                fitness=age+10*food-2*collisions-5*hazard
                for r in context['creatures']:r.update(age=age,food_eaten=food,collisions=collisions,hazard_seconds=hazard,fitness=fitness)
                context.update(collision_rate=60*collisions/age,hazard_fraction=hazard/age)
                data['generations'][0].update(mean_fitness=fitness,best_fitness=fitness,mean_food_eaten=food,
                    mean_survival_seconds=age,survivors_at_checkpoint=100 if age>=60 else 0,
                    survival_rate=1. if age>=60 else 0.,duration_seconds=age+SIMULATION_STEP)
                data['total_simulated_seconds']=age+SIMULATION_STEP
    return report


class ObstacleStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=tempfile.TemporaryDirectory();cls.root=Path(cls.directory.name)
        with patch('world.create_population',side_effect=short_population):
            cls.report=run_study(range(2201,2213),generations=2,repeats=2,models_dir=cls.root/'models')

    @classmethod
    def tearDownClass(cls):cls.directory.cleanup()

    def test_repeats_are_averaged_inside_independent_seeds(self):
        a=self.report['analysis'];self.assertEqual(a['independent_seed_groups'],12)
        self.assertEqual(len(a['primary']),5)
        self.assertTrue(all(x['n_pairs']==12 for x in a['primary'].values()))
        self.assertFalse(a['avoidance_with_improved_foraging_supported'])
        self.assertFalse(a['added_risk_sensor_benefit_supported'])

    def test_known_avoidance_and_food_improvements_pass_the_corrected_joint_rule(self):
        a=analyze_results(synthetic_outcomes(self.report))
        self.assertTrue(a['avoidance_with_improved_foraging_supported']);self.assertTrue(a['added_risk_sensor_benefit_supported'])
        self.assertEqual(a['primary']['collision_change']['conclusion'],'lower')
        self.assertEqual(a['primary']['hazard_change']['conclusion'],'lower')

    def test_risk_reduction_without_improved_foraging_does_not_pass(self):
        a=analyze_results(synthetic_outcomes(self.report,evolved=(120,1,0,0)))
        self.assertEqual(a['primary']['fitness_gain']['conclusion'],'higher')
        self.assertEqual(a['primary']['food_gain']['conclusion'],'lower')
        self.assertFalse(a['avoidance_with_improved_foraging_supported'])

    def test_early_death_with_lower_raw_risk_but_higher_rates_does_not_pass(self):
        a=analyze_results(synthetic_outcomes(self.report,evolved=(5,30,1,2)))
        self.assertEqual(a['primary']['collision_change']['conclusion'],'higher')
        self.assertEqual(a['primary']['hazard_change']['conclusion'],'higher')
        self.assertFalse(a['avoidance_with_improved_foraging_supported'])

    def test_inherited_sixteen_input_genomes_reconstruct_from_recorded_mutations(self):
        trial=self.report['trials'][0];metadata,banks=load_models(trial['model_file'],2201,2)
        bank={k:v.copy() for k,v in banks['founder'].items()}
        for trace in metadata['training']['obstacle_environment']['transitions']:
            rng=RecordedMutationRNG(trace['mutation_seed'])
            children=reproduce_brains([SimpleNamespace(creature_id=k,brain=bank[k]) for k in trace['parent_ids']],rng)
            self.assertEqual(rng.digest.hexdigest(),trace['mutation_draws_sha256'])
            self.assertEqual([x.mutations for x in children],trace['offspring_mutation_counts'])
            bank={i:x.brain for i,x in enumerate(children,1)}
        self.assertEqual(bank_digest(bank),bank_digest(banks['evolved']))
        self.assertTrue(all(b.parameter_count==154 for b in bank.values()))
        with self.assertRaises(ValueError):run_study(range(2201,2213),generations=2,models_dir=self.root/'models')

    def test_incomplete_unmatched_or_corrupted_reports_are_rejected(self):
        for case in ('seed','control','layout','mode','fitness','duration','parents'):
            r=copy.deepcopy(self.report);t=r['trials'][0];record=t['tests'][0]['conditions']['evolved'];data=record['report']
            if case=='seed':r['trials'].pop()
            elif case=='control':t['tests'][0]['conditions'].pop('founder')
            elif case=='layout':record['initial_conditions']='changed'
            elif case=='mode':data['obstacle_environment']['risk_sensor_mode']='hidden'
            elif case=='fitness':data['generations'][0]['mean_fitness']=1000
            elif case=='duration':data['generations'][0]['duration_seconds']=0
            else:t['training']['obstacle_environment']['transitions'][0]['parent_ids']=[99]
            with self.subTest(case=case),self.assertRaises(ValueError):analyze_results(r)

    def test_plot_and_layout_export_and_running_studies_are_rejected(self):
        for suffix in ('png','svg','pdf'):
            p=self.root/f'plot.{suffix}';save_obstacle_plot(self.report,p);self.assertGreater(p.stat().st_size,1000)
        with patch('world.create_population',side_effect=short_population):
            save_layout_plot(self.report,self.root/'layout.png')
        save_lineage_plot(self.report['trials'][0]['training'],self.root/'lineage.png')
        partial=copy.deepcopy(self.report['trials'][0]['training'])
        partial['obstacle_environment']['history'].append({'generation':3,'complete':False})
        save_lineage_plot(partial,self.root/'partial-lineage.png')
        r=copy.deepcopy(self.report);r['status']='running'
        with self.assertRaises(ValueError):build_study_figure(r)

    def test_parallel_results_and_checkpoints_are_deterministic(self):
        states=[]
        with patch('world.create_population',side_effect=short_population),patch('experiment_obstacles.ProcessPoolExecutor',ThreadPoolExecutor):
            r=run_study([2201,2202],generations=2,repeats=2,workers=2,models_dir=self.root/'parallel',checkpoint=lambda x:states.append(x['status']))
        subset=copy.deepcopy(self.report);subset['protocol']['seeds']=[2201,2202];subset['trials']=subset['trials'][:2]
        self.assertEqual(r['analysis'],analyze_results(subset));self.assertEqual(states,['running','running','running','complete'])

    def test_headless_cli_exports_sixteen_input_cohorts_and_custom_lineage_plots(self):
        report,plot,screenshot=self.root/'cli.json',self.root/'cli.png',self.root/'cli-world.png'
        with patch('world.create_population',side_effect=short_population),redirect_stdout(io.StringIO()):
            self.assertEqual(run(headless=True,obstacles=True,generations=2,speed=20,seed=42,
                                 population_size=12,food_count=0,report=report,plot=plot,screenshot=screenshot),0)
        data=json.loads(report.read_text());self.assertEqual(data['completed_generations'],2)
        self.assertEqual(data['obstacle_environment']['input_size'],16);self.assertGreater(plot.stat().st_size,1000)
        with self.assertRaises(ValueError):run(headless=True,frames=1,seasons=True,obstacles=True)


if __name__=='__main__':unittest.main()
