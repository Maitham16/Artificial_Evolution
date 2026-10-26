"""Local perception, conservative transfers, team inheritance, and causal controls."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from body_traits import WholeGenome,BodyTraits,genome_bank_digest
from experiment_social import run_study,analyze_results,validate_cohorts,load_models,current_bank
from food import Food
from main import run
from plot_social import build_study_figure,save_outcome_plot,save_world_image,save_lineage_plot
from plot_traits import export
from social import SocialWorld,new_social_brain,SIGNAL_COST,SHARE_EFFICIENCY,DONOR_RESERVE
from simulation import EvolutionSimulation
from world import SIMULATION_STEP


def constant_brain(signal=0.,share=0.):
    b=new_social_brain(np.random.default_rng(1))
    for p in b.parameters:p[:]=0
    b.output_bias[1:]=[signal,share]
    return b


class SocialPhysicsTests(unittest.TestCase):
    def make_world(self,**kwargs):return SocialWorld(seed=1,population_size=6,groups=2,food_count=0,episode_seconds=.1,**kwargs)

    def test_nearest_neighbors_signals_density_and_access_have_separate_inputs(self):
        w=self.make_world();a,b,c=w.creatures[:3]
        a.x=a.y=100;a.heading=0;b.x=130;b.y=100;b.energy=25;b.signal=.5;c.x=140;c.y=100;c.signal=1.
        sensors=w.get_sensory_inputs(a);self.assertEqual(sensors.shape,(17,));self.assertEqual(a.brain.parameter_count,171)
        self.assertAlmostEqual(sensors[8],1-30/160);self.assertEqual(sensors[9],0);self.assertEqual(sensors[10],1)
        self.assertEqual(sensors[11],.75);self.assertAlmostEqual(sensors[12],.75);self.assertEqual(sensors[14],1)
        self.assertEqual(sensors[15],1);self.assertEqual(sensors[16],float(a.can_feed))

    def test_groups_cannot_sense_or_share_across_borders_and_never_sense_themselves(self):
        w=self.make_world();a=w.creatures[0]
        for c in w.creatures:c.x=900;c.y=500;c.signal=1
        a.x=a.y=100;w.creatures[3].x=101;w.creatures[3].y=100
        sensors=w.get_sensory_inputs(a);np.testing.assert_array_equal(sensors[8:16],0)
        a.share_effort=1;w._share_food();self.assertEqual(a.shared_out,0)

    def test_hidden_signals_preserve_nearest_neighbor_information_truth_and_cost(self):
        w=self.make_world();a,b=w.creatures[:2];a.x=a.y=100;b.x=110;b.y=100;b.signal=1
        before=w.get_sensory_inputs(a);w.signals_hidden=True;after=w.get_sensory_inputs(a)
        np.testing.assert_array_equal(before[:12],after[:12]);np.testing.assert_array_equal(before[15:],after[15:]);np.testing.assert_array_equal(after[12:15],0)
        _,truth=w.perceive_neighbors(a);self.assertGreater(truth['signal_strength'],0)
        a.signal=.5;self.assertAlmostEqual(a.energy_cost_per_second,5+SIGNAL_COST*.5)

    def test_transfers_are_lossy_local_and_have_no_automatic_donation(self):
        w=self.make_world();a,b,c=w.creatures[:3]
        a.x=a.y=100;b.x=120;b.y=100;c.x=400;c.y=400;a.energy=90;b.energy=20
        w._share_food();self.assertEqual(b.energy,20)
        a.share_effort=1;w._share_food()
        self.assertAlmostEqual(a.shared_out,.2);self.assertAlmostEqual(b.shared_in,.16)
        self.assertAlmostEqual(a.energy+b.energy,110-.04)
        self.assertEqual(len(w.transfer_edges),1)

    def test_recipient_capacity_and_donor_reserve_are_never_exceeded(self):
        w=self.make_world();a,b,c=w.creatures[:3];a.x=a.y=100;b.x=120;b.y=100;c.x=400;c.y=400
        a.energy=DONOR_RESERVE+.1;b.energy=99.99;a.share_effort=1;w._share_food()
        self.assertGreaterEqual(a.energy,DONOR_RESERVE);self.assertLessEqual(b.energy,100+1e-12)
        self.assertAlmostEqual(b.energy,100)

    def test_multiple_donors_are_scaled_proportionally_without_list_order_bias(self):
        def setup():
            w=self.make_world();a,b,c=w.creatures[:3]
            a.x=90;a.y=100;b.x=100;b.y=100;c.x=110;c.y=100
            a.share_effort=c.share_effort=1;b.energy=99.9
            return w,a,b,c
        w,a,b,c=setup();w._share_food();self.assertAlmostEqual(a.shared_out,c.shared_out)
        self.assertAlmostEqual(b.energy,100);expected={x.creature_id:x.energy for x in w.creatures}
        q,_,_,_=setup();q.creatures.reverse();q._share_food()
        self.assertEqual({x.creature_id:x.energy for x in q.creatures},expected)

    def test_received_energy_cannot_be_forwarded_in_the_same_tick(self):
        w=self.make_world();a,b,c=w.creatures[:3];a.x=90;a.y=100;b.x=100;b.y=100;c.x=110;c.y=100
        a.share_effort=b.share_effort=1;b.energy=DONOR_RESERVE;c.energy=20
        w._share_food();self.assertGreater(b.shared_in,0);self.assertEqual(b.shared_out,0)

    def test_plant_access_is_enforced_and_food_quota_is_equal(self):
        w=SocialWorld(seed=1,population_size=12,groups=3,food_count=30,episode_seconds=.1)
        self.assertEqual([sum(w.food_group(f)==g for f in w.food) for g in range(3)],[10]*3)
        for g in range(3):self.assertEqual(sum(c.can_feed and c.group_id==g for c in w.creatures),2)
        dependent=next(c for c in w.creatures if not c.can_feed);w.food=[Food(dependent.x,dependent.y)]
        for c in w.creatures:
            if c.can_feed:c.x+=100
        w._resolve_food_collisions();self.assertEqual(dependent.food_eaten,0)

    def test_censoring_removal_times_and_signal_energy_conserve_full_ledger(self):
        w=self.make_world()
        for c in w.creatures:c.brain=constant_brain(signal=1,share=1)
        s=EvolutionSimulation(w,generation_limit=1);s.update(.1);report=s.report();validate_cohorts(report,study=False)
        self.assertTrue(any(c['alive_at_end'] for c in report['social']['history'][0]['creatures']))
        self.assertTrue(all(c['removed_at'] is None for c in report['social']['history'][0]['creatures'] if c['alive_at_end']))
        self.assertGreater(report['social']['history'][0]['signal_energy'],0)

    def test_all_decisions_use_prior_tick_signal_and_energy_snapshot(self):
        w=self.make_world();a,b=w.creatures[:2];a.x=a.y=100;b.x=120;b.y=100
        a.signal=.8;a.brain=constant_brain(signal=-10);expected=w.get_sensory_inputs(b).copy();seen=[]
        class Recorder:
            def forward(self,sensors):seen.append(sensors.copy());return np.zeros(3)
        b.brain=Recorder();w.update(SIMULATION_STEP);np.testing.assert_array_equal(seen[0],expected)

    def test_body_speed_and_local_walls_are_fixed_and_frame_rate_independent(self):
        a=self.make_world();b=self.make_world();a.update(.1)
        for _ in range(6):b.update(SIMULATION_STEP)
        self.assertEqual(a.social_report(),b.social_report())
        for c in a.creatures:
            self.assertEqual(c.speed,60);ox,oy=c.cell_origin;cw,ch=c.cell_size
            self.assertTrue(ox+8<=c.x<=ox+cw-8 and oy+8<=c.y<=oy+ch-8)

    def test_known_donor_can_improve_recipient_and_group_survival_without_score_bonus(self):
        def simulate(sharing):
            w=SocialWorld(seed=1,population_size=4,groups=2,food_count=0,episode_seconds=18.15,sharing=False)
            donor=next(c for c in w.creatures if c.group_id==0 and c.can_feed)
            recipient=next(c for c in w.creatures if c.group_id==0 and not c.can_feed)
            for c in w.creatures:c.brain=constant_brain(share=-10)
            donor.brain=constant_brain(share=10);donor.x=100;recipient.x=120;donor.y=recipient.y=200;donor.heading=recipient.heading=0
            w.update(17.95);donor.eat(Food(donor.x,donor.y));w.sharing=sharing;w.update(.2)
            return w,recipient
        enabled,recipient=simulate(True);blocked,other=simulate(False)
        self.assertGreater(recipient.age,other.age)
        self.assertGreater(enabled.social_history[0]['groups'][0]['mean_age'],blocked.social_history[0]['groups'][0]['mean_age'])
        self.assertEqual(recipient.fitness,recipient.age)

    def test_group_breeding_preserves_teams_individual_breeding_mixes_them(self):
        worlds={a:SocialWorld(seed=42,selection_level=a,episode_seconds=.05,mutation_rate=0) for a in ('individual','group')}
        for w in worlds.values():w.update(.05);w.advance_generation()
        grouped=worlds['group'];mixed=worlds['individual']
        for g in range(10):self.assertEqual(len({(c.parent_id-1)//10 for c in grouped.creatures if c.group_id==g}),1)
        self.assertTrue(any(len({(c.parent_id-1)//10 for c in mixed.creatures if c.group_id==g})>1 for g in range(10)))

    def test_action_switches_and_constructor_validation(self):
        w=self.make_world(signaling=False,sharing=False)
        for c in w.creatures:c.brain=constant_brain(signal=10,share=10)
        w.update(.1);self.assertEqual(w.social_history[0]['signal_energy'],0);self.assertEqual(w.social_history[0]['shared_out'],0)
        for options in ({'groups':1},{'groups':7},{'food_count':151},{'episode_seconds':0},{'episode_seconds':.001},
                        {'access':'invented'},{'controller':'random'},{'food_sensor_mode':'hidden'},{'fixed_speed':60},{'body_mutation_rate':.1}):
            with self.subTest(options=options),self.assertRaises(ValueError):SocialWorld(**options)


class SocialStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.report=run_study(range(2501,2509),generations=2,episode_seconds=.05,models_dir=cls.root/'models')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_complete_paired_study_uses_seed_units_and_matched_mutations(self):
        r=self.report;a=analyze_results(r);self.assertEqual(r['status'],'complete')
        self.assertEqual(a['independent_seed_groups'],8)
        for t in r['trials']:
            self.assertEqual(t['training_starts']['individual'],t['training_starts']['group'])
            x,y=[t['training'][arm]['social']['transitions'][0] for arm in ('individual','group')]
            self.assertEqual(x['mutation_draws_sha256'],y['mutation_draws_sha256']);self.assertEqual(x['mutation_rng_calls'],800)
        self.assertTrue(all(v['n_pairs']==8 for env in a['environments'].values() for v in env['primary'].values()))

    def test_frozen_models_preserve_three_complete_banks_and_no_sharing_interventions(self):
        t=self.report['trials'][0];metadata,banks=load_models(t['model_file'],t['seed'],2)
        self.assertEqual(metadata,{k:v for k,v in t.items() if k not in ('model_file','model_sha256','tests')})
        for cases in t['tests'].values():
            for name,case in cases.items():
                source='founder' if name.startswith('founder') else 'individual' if name=='individual' else 'group'
                self.assertEqual(case['genomes_sha256'],genome_bank_digest(banks[source]))
        self.assertIsNone(self.report['analysis']['environments']['open']['condition_means']['group']['dependent_mean_age'])

    def test_evolved_cooperation_requires_founder_adjusted_benefit_not_random_sharing(self):
        r=copy.deepcopy(self.report)
        ages={'group':40.,'individual':25.,'group_no_sharing':30.,'founder':20.,'founder_no_sharing':18.,'group_signals_hidden':39.}
        for t in r['trials']:
            for cases in t['tests'].values():
                for name,record in cases.items():record['report']['social']['history'][0]['mean_age']=ages[name]
        with patch('experiment_social.validate_cohorts'):
            self.assertEqual(analyze_results(r)['verdict'],'evolved_beneficial_cooperation_detected')
            for t in r['trials']:
                for cases in t['tests'].values():
                    cases['founder']['report']['social']['history'][0]['mean_age']=40.
                    cases['founder_no_sharing']['report']['social']['history'][0]['mean_age']=30.
            self.assertEqual(analyze_results(r)['verdict'],'evolved_beneficial_cooperation_not_established')

    def test_corrupt_energy_groups_roles_mutation_and_interventions_are_rejected(self):
        for case in ('missing','energy','role','group','parent','mutation','mask','layout','model'):
            r=copy.deepcopy(self.report);t=r['trials'][0];record=t['tests']['restricted']['group'];row=record['report']['social']['history'][0]
            if case=='missing':t['tests']['restricted'].pop('founder_no_sharing')
            elif case=='energy':row['creatures'][0]['shared_in']+=1
            elif case=='role':row['creatures'][0]['can_feed']=not row['creatures'][0]['can_feed']
            elif case=='group':row['creatures'][0]['group_id']=9
            elif case=='parent':t['training']['group']['social']['transitions'][0]['parent_ids']=[100]
            elif case=='mutation':t['training']['group']['social']['transitions'][0]['mutation_seed']=0
            elif case=='mask':record['report']['social']['sharing']=False
            elif case=='layout':record['shared_layout_sha256']='wrong'
            else:record['genomes_sha256']='wrong'
            with self.subTest(case=case),self.assertRaises(ValueError):analyze_results(r)

    def test_archives_reject_changed_numeric_parameters_and_existing_paths(self):
        t=self.report['trials'][0]
        with np.load(t['model_file'],allow_pickle=False) as archive:arrays={k:archive[k] for k in archive.files}
        arrays['group_0'][0,0,0]+=1;p=self.root/'changed.npz';np.savez_compressed(p,**arrays)
        with self.assertRaises(ValueError):load_models(p,t['seed'],2)
        with self.assertRaises(ValueError):run_study(range(2501,2509),generations=2,models_dir=self.root/'models')

    def test_png_svg_pdf_world_and_partial_lineage_exports(self):
        for suffix in ('png','svg','pdf'):
            path=self.root/f'plot.{suffix}';export(build_study_figure(self.report),path);self.assertGreater(path.stat().st_size,1000)
        save_outcome_plot(self.report,self.root/'outcomes.png');save_world_image(self.report,self.root/'world.png')
        r=copy.deepcopy(self.report['trials'][0]['training']['group']);r['social']['history'].append({'generation':3,'complete':False})
        save_lineage_plot(r,self.root/'lineage.png')
        r=copy.deepcopy(self.report);r['status']='running'
        with self.assertRaises(ValueError):build_study_figure(r)

    def test_headless_cli_social_modes_and_restart(self):
        p=self.root/'cli.json';plot=self.root/'cli.png'
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run(headless=True,social=True,population_size=12,groups=3,episode_seconds=.1,generations=2,seed=42,speed=20,report=p,plot=plot),0)
        r=json.loads(p.read_text());validate_cohorts(r,study=False);self.assertNotIn('physical_traits',r);self.assertEqual(r['completed_generations'],2)
        for options in ({'traits':True},{'predator_prey':True},{'obstacles':True},{'seasons':True},{'fixed_speed':60}):
            with self.assertRaises(ValueError):run(headless=True,frames=1,social=True,**options)
        w=SocialWorld(seed=42,episode_seconds=.05);s=EvolutionSimulation(w,generation_limit=2);s.update(.2);s.restart(42)
        self.assertEqual(len(w.social_history),1);self.assertEqual(len(w.transitions),0);self.assertEqual(s.total_simulated_seconds,0)


if __name__=='__main__':unittest.main()
