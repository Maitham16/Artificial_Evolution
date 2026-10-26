"""Continuous timing, paid births, ancestry, diversity, and ecological records."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from body_traits import WholeGenome,BodyTraits,genome_bank_digest
from ecosystem import ContinuousWorld,ContinuousSimulation,diversity_metrics,genetic_features
from experiment_ecosystem import run_study,validate_run,load_run,load_archive,save_archive,analyze_results,summarize
from main import run
from plot_ecosystem import build_study_figure,save_ancestry_plot,save_run_plot,save_world_image
from plot_traits import export
from world import SIMULATION_STEP


class ContinuousPhysicsTests(unittest.TestCase):
    def ready_parent(self,**kwargs):
        w=ContinuousWorld(seed=2699,population_size=2,population_cap=10,food_count=0,mutation_rate=0,body_mutation_rate=0,**kwargs)
        parent=w.creatures[0];parent.age=15;parent.energy=100;w.creatures[1].energy=20
        return w,parent

    def test_parent_funds_child_without_resetting_age_food_or_other_actors(self):
        w,parent=self.ready_parent();other=w.creatures[1];before=(parent.age,other.age,other.energy)
        w._try_births(15)
        self.assertEqual(len(w.births),3);child=w.creatures[-1]
        self.assertEqual(child.energy,40);self.assertAlmostEqual(parent.energy,45);self.assertAlmostEqual(parent.reproduction_energy,55)
        self.assertEqual(before,(parent.age,other.age,other.energy));self.assertEqual(child.age,0)
        self.assertEqual(child.parent_id,parent.creature_id);self.assertEqual(child.founder_id,parent.founder_id)
        self.assertEqual(child.generation,parent.generation+1)
        self.assertEqual(child.brain,parent.brain);self.assertFalse(np.shares_memory(child.brain.input_weights,parent.brain.input_weights))

    def test_maturity_cooldown_and_parent_reserve_are_enforced(self):
        w,p=self.ready_parent();p.age=14.9;w._try_births(15);self.assertFalse(w.attempts)
        p.age=15;p.energy=79;w._try_births(15);self.assertFalse(w.attempts)
        p.energy=100;w._try_births(15);self.assertEqual(len(w.attempts),1)
        p.energy=100;w._try_births(16);self.assertEqual(len(w.attempts),1)
        p.age=35;w._try_births(35);self.assertEqual(len(w.attempts),2)
        self.assertGreaterEqual(p.energy,25)

    def test_newborns_cannot_reproduce_in_the_same_tick(self):
        w,p=self.ready_parent(maturity_age=.01);p.age=1;w._try_births(1)
        self.assertEqual(len(w.births),3);self.assertEqual(len(w.attempts),1)
        self.assertEqual(w.creatures[-1].attempt_count,0)

    def test_population_cap_blocks_birth_without_charging_parent(self):
        w=ContinuousWorld(seed=1,population_size=2,population_cap=2,food_count=0)
        for c in w.creatures:c.age=15;c.energy=100
        w._try_births(15)
        self.assertEqual(len(w.creatures),2);self.assertTrue(all(e['status']=='capacity' for e in w.attempts))
        self.assertTrue(all(c.energy==100 for c in w.creatures))

    def test_energy_and_space_failures_are_recorded_without_partial_children(self):
        w,p=self.ready_parent();p.energy=80
        # A larger offspring can exceed its parent's available investment budget.
        from unittest.mock import patch
        with patch('ecosystem.mutate_body',return_value=BodyTraits(radius=12)):
            w._try_births(15)
        self.assertEqual(w.attempts[0]['status'],'energy');self.assertEqual(p.energy,80);self.assertEqual(len(w.births),2)
        w,p=self.ready_parent();w.width=w.height=10;w._try_births(15)
        self.assertEqual(w.attempts[0]['status'],'space');self.assertEqual(p.energy,100)

    def test_food_has_finite_regrowth_and_full_stock_cannot_bank_future_growth(self):
        w=ContinuousWorld(seed=1,population_size=2,population_cap=10,food_count=2,regrowth_rate=6)
        for _ in range(60):w._regrow()
        self.assertEqual(w.food_credit,0);w.food.pop();w._regrow();self.assertEqual(len(w.food),1)
        for _ in range(9):w._regrow()
        self.assertEqual(len(w.food),2);self.assertEqual(w.food_regrown,1)

    def test_extinction_is_absorbing_without_hidden_rescue_or_food_reset(self):
        w=ContinuousWorld(seed=1,population_size=4,population_cap=10,food_count=0)
        s=ContinuousSimulation(w,duration=100);s.update(100);self.assertTrue(s.finished)
        self.assertIsNotNone(w.extinct_at);self.assertEqual(len(w.creatures),0)
        report=s.report();s.update(100);self.assertEqual(s.report(),report)
        validate_run(report)

    def test_reproduction_switch_and_no_birth_negative_control(self):
        w=ContinuousWorld(seed=2699,reproduction=False)
        s=ContinuousSimulation(w,duration=130);s.update(130)
        self.assertEqual(len(w.births),100);self.assertEqual(len(w.creatures),0)
        self.assertLessEqual(w.elapsed_time,120+SIMULATION_STEP)
        s.restart(2699);s.auto_advance=True;self.assertTrue(w.reproduction_enabled)
        self.assertEqual(w.reproduction_events[-1],{'time':0.,'enabled':True})

    def test_snapshot_population_counts_follow_actual_births_and_removals(self):
        w=ContinuousWorld(seed=2699);s=ContinuousSimulation(w,duration=60);s.update(60);r=s.report();validate_run(r)
        self.assertGreater(len(r['births']),100);self.assertGreater(len(r['deaths']),0)
        self.assertEqual(len(w.creatures),100+len(w.births)-100-len(w.deaths))
        self.assertFalse(w.advance_generation());self.assertFalse(w.generation_history)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'all-lifetimes.npz';save_archive(path,w,'test-report-hash');_,bank=load_archive(path,r)
            self.assertEqual(len(bank),len(r['births']))
            for birth in r['births'][100:]:self.assertEqual(birth['genome_sha256'],genome_bank_digest({0:bank[birth['creature_id']]}))

    def test_fixed_step_pause_speed_and_restart_are_deterministic(self):
        a=ContinuousWorld(seed=42,population_size=8,population_cap=20,food_count=20)
        b=ContinuousWorld(seed=42,population_size=8,population_cap=20,food_count=20)
        x,y=ContinuousSimulation(a,duration=1),ContinuousSimulation(b,duration=1,speed=20)
        a.paused=True;x.update(1);self.assertEqual(a.elapsed_time,0);a.paused=False
        x.update(1);y.update(.05);self.assertEqual(x.report(),y.report())
        x.restart(42);self.assertEqual(len(a.registry),8);self.assertEqual(a.elapsed_time,0)
        self.assertEqual(len(a.snapshots),1)
        with self.assertRaises(ValueError):x.update(-1)

    def test_diversity_separates_family_labels_mutation_and_threshold_clusters(self):
        w=ContinuousWorld(seed=1,population_size=2,population_cap=10,food_count=0);a,b=w.creatures
        b.founder_id=a.founder_id;b.brain=a.brain.copy();b.body=a.body
        d=diversity_metrics(w.creatures,.25);self.assertEqual(d['within_family_rms'],0);self.assertEqual(d['genetic_clusters'],1)
        b.brain.output_bias[0]+=1
        d=diversity_metrics(w.creatures,.25);self.assertGreater(d['within_family_rms'],0);self.assertEqual(d['genetic_clusters'],2)
        self.assertEqual(len(d['family_counts']),1)
        self.assertIsNone(diversity_metrics([],.25)['genetic_rms'])
        self.assertIsNone(diversity_metrics([a],.25)['within_family_rms'])

    def test_constant_time_horizon_censors_survivors_instead_of_killing_them(self):
        w=ContinuousWorld(seed=2699);s=ContinuousSimulation(w,duration=1);s.update(1)
        r=s.report();self.assertTrue(r['finished']);self.assertEqual(r['elapsed_seconds'],1)
        self.assertTrue(all(c['alive'] for c in r['individuals']));self.assertTrue(all(c['removed_at'] is None for c in r['individuals']))

    def test_invalid_parameters_and_modes_are_rejected(self):
        for options in ({'population_cap':20},{'maturity_age':0},{'birth_cooldown':0},{'sample_interval':0},
                        {'lineage_threshold':0},{'regrowth_rate':-1},{'controller':'random'},{'fixed_speed':60}):
            with self.subTest(options=options),self.assertRaises(ValueError):ContinuousWorld(**options)
        with self.assertRaises(ValueError):ContinuousSimulation(ContinuousWorld(seed=1),duration=.001)


class ContinuousStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.report=run_study([2601,2602],duration=1,output_dir=cls.root/'runs')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_complete_repeated_resource_mutation_controls_and_initial_matching(self):
        r=self.report;a=analyze_results(r);self.assertEqual(r['status'],'complete');self.assertEqual(a['independent_seed_groups'],2)
        for t in r['trials']:
            for resource,runs in t['runs'].items():
                self.assertEqual(runs['mutating']['initial_layout_sha256'],runs['clonal']['initial_layout_sha256'])
                self.assertFalse(runs['mutating']['summary']['finite_window_persistence'])

    def test_full_lifetime_reports_and_numeric_genomes_are_losslessly_archived(self):
        record=self.report['trials'][0]['runs']['abundant']['mutating'];r=load_run(record);metadata,bank=load_archive(record['models_file'],r)
        self.assertEqual(len(bank),100);self.assertEqual(metadata['report_sha256'],record['report_sha256'])
        self.assertEqual(genome_bank_digest(bank),r['all_genomes_sha256'])

    def test_tampered_energy_ancestry_population_and_compressed_data_are_rejected(self):
        record=self.report['trials'][0]['runs']['abundant']['mutating'];source=load_run(record)
        for case in ('energy','root','population','food','birth'):
            r=copy.deepcopy(source)
            if case=='energy':r['individuals'][0]['energy']+=1
            elif case=='root':r['births'][0]['founder_id']=999
            elif case=='population':r['snapshots'][-1]['population']+=1
            elif case=='food':r['food_regrown']+=1
            else:r['births'][0]['parent_id']=2
            with self.subTest(case=case),self.assertRaises(ValueError):validate_run(r)
        bad=copy.deepcopy(record);bad['report_sha256']='wrong'
        with self.assertRaises(ValueError):load_run(bad)

    def test_archives_and_existing_outputs_are_protected(self):
        record=self.report['trials'][0]['runs']['abundant']['mutating'];r=load_run(record)
        with np.load(record['models_file'],allow_pickle=False) as archive:arrays={k:archive[k] for k in archive.files}
        arrays['brain_0'][0,0,0]+=1;p=self.root/'changed.npz';np.savez_compressed(p,**arrays)
        with self.assertRaises(ValueError):load_archive(p,r)
        with self.assertRaises(ValueError):run_study([2601,2602],duration=1,output_dir=self.root/'runs')

    def test_png_svg_pdf_ancestry_and_single_run_exports(self):
        for suffix in ('png','svg','pdf'):
            path=self.root/f'plot.{suffix}';export(build_study_figure(self.report),path);self.assertGreater(path.stat().st_size,1000)
        save_ancestry_plot(self.report,self.root/'ancestry.png')
        save_world_image(self.report,self.root/'world.png')
        record=self.report['trials'][0]['runs']['abundant']['mutating'];save_run_plot(load_run(record),self.root/'single.png')
        bad=copy.deepcopy(self.report);bad['status']='running'
        with self.assertRaises(ValueError):build_study_figure(bad)

    def test_headless_continuous_cli_report_plot_and_mode_conflicts(self):
        path=self.root/'cli.json';plot=self.root/'cli.png'
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run(headless=True,continuous=True,duration=.1,seed=42,population_size=12,population_cap=30,speed=20,report=path,plot=plot),0)
        r=json.loads(path.read_text());validate_run(r);self.assertEqual(r['mode'],'continuous');self.assertTrue(r['finished'])
        for options in ({'generations':2},{'manual':True},{'social':True},{'predator_prey':True},{'fixed_speed':60}):
            with self.assertRaises(ValueError):run(headless=True,frames=1,continuous=True,**options)


if __name__=='__main__':unittest.main()
