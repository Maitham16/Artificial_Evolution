"""Matched replay and physical mechanisms for the explicit v2 rule extension."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from test_engine_bridge import config, scientific_state, TransportFixture
from engine_bridge import EngineAdapter
from habitat import HabitatConfig, HabitatSession, Surface, replay_habitat, export_habitat
from research_session import ResearchSession, verify_bundle, replay_run


class PhysicalHabitatTests(unittest.TestCase):
    def test_legacy_disabled_is_the_original_session_and_identical_science(self):
        cfg=config();adapter=EngineAdapter(cfg,{'enabled':False});reference=ResearchSession(cfg)
        self.assertIs(type(adapter.session),ResearchSession)
        for _ in range(180):adapter.session.step();reference.step();adapter.frame()
        self.assertEqual(scientific_state(adapter.session),scientific_state(reference))
        self.assertNotIn('habitat',adapter.session.snapshot()[0])

    def test_all_seven_physical_modes_replay_exactly_with_their_own_extension(self):
        for mode in ('foraging','seasons','obstacles','traits','predator_prey','social','continuous'):
            with self.subTest(mode=mode):
                session=HabitatSession(config(mode),{'enabled':True,'weather_period':1.})
                for tick in range(150):session.step()
                report,_=session.snapshot();replayed=replay_habitat(report)
                self.assertEqual(scientific_state(session),scientific_state(replayed))
                self.assertEqual(report['habitat'],replayed.snapshot()[0]['habitat'])

    def test_observing_physical_sessions_does_not_change_model_or_rng(self):
        cfg=config('continuous',maturity_age=.1,birth_cooldown=.1,population_cap=24)
        adapter=EngineAdapter(cfg,{'enabled':True});reference=HabitatSession(cfg,{'enabled':True})
        for _ in range(180):adapter.session.step();reference.step();adapter.frame()
        self.assertEqual(scientific_state(adapter.session),scientific_state(reference))
        self.assertEqual(adapter.session.snapshot()[0]['habitat'],reference.snapshot()[0]['habitat'])
        self.assertEqual(adapter.session.world._food_rng.getstate(),reference.world._food_rng.getstate())

    def test_heightfield_is_seeded_and_source_geometry_is_explicit(self):
        options=HabitatConfig.from_dict({'enabled':True});a=Surface(1000,600,1,options);b=Surface(1000,600,1,options);c=Surface(1000,600,2,options)
        self.assertEqual(a.describe(),b.describe());self.assertNotEqual(a.digest,c.digest)
        self.assertEqual((a.nx,a.nz),(51,31))
        self.assertEqual(a.height_at(-25,-15),a.values[0])
        self.assertTrue(any(h<options.water_level for h in a.values))

    def test_wading_slows_actual_motion_and_consumes_real_energy(self):
        session=HabitatSession(config(food_count=0),{'enabled':True});c=session.world.creatures[0]
        found=False
        for x in range(80,920,2):
            for y in range(80,520,10):
                depth=session.surface.depth(x,y)
                if .15<depth<.5 and sum(v*v for v in session.surface.gradient(x,y))<.7:
                    c.x,c.y=x,y;found=True;break
            if found:break
        self.assertTrue(found);c.heading=1.57079632679;c.speed=60
        before=(c.x,c.y);energy=c.energy;c.update_survival(1/60);c.move(1/60,session.world.width,session.world.height)
        distance=((c.x-before[0])**2+(c.y-before[1])**2)**.5
        self.assertLess(distance,1.);self.assertGreater(c.habitat_ledger['water_energy'],0)
        self.assertLess(c.energy,energy);self.assertGreater(c.habitat_ledger['water_seconds'],0)

    def test_deep_water_contact_blocks_and_reflects_before_interactions(self):
        session=HabitatSession(config(food_count=0),{'enabled':True});c=session.world.creatures[0];c.speed=60
        found=False
        import math
        for x in range(200,800):
            for y in range(100,500,10):
                if session.surface.depth(x,y)<=.75 and session.surface.depth(x+1,y)>.75:
                    for sub in range(20):
                        px=x+sub*.05
                        if session.surface.depth(px,y)<=.75 and session.surface.depth(px+.2,y)>.75:
                            c.x,c.y=px,y;c.heading=0.;found=True;break
                    if found:break
            if found:break
        self.assertTrue(found);before=(c.x,c.y);c.move(1/60,1000,600)
        self.assertEqual((c.x,c.y),before);self.assertEqual(c.habitat_ledger['blocked'],1);self.assertNotEqual(c.heading,0)

    def test_weather_is_simulation_time_and_raises_metabolic_cost(self):
        session=HabitatSession(config(food_count=0),{'enabled':True,'weather_period':1.});owner=session.habitat_owner;c=session.world.creatures[0]
        owner.set_time(0);clear=owner.costs(c)[2];owner.set_time(1);rain=owner.costs(c)[2];owner.set_time(9);snow=owner.costs(c)[2]
        self.assertEqual(owner.climate['weather'],'snow');self.assertGreater(rain,clear);self.assertGreater(snow,rain)
        self.assertGreater(c.energy_cost_per_second,sum(c.body.powers()) if hasattr(c,'body') else 2+.05*c.speed)

    def test_food_and_founders_do_not_spawn_in_inaccessible_water(self):
        for mode in ('foraging','social','continuous'):
            session=HabitatSession(config(mode),{'enabled':True})
            self.assertTrue(all(session.surface.depth(f.x,f.y)<=.02 for f in session.world.food))
            self.assertTrue(all(session.surface.depth(c.x,c.y)<=.75 for c in session.world.creatures))
            if mode=='social':
                counts={g:sum(session.world.food_group(f)==g for f in session.world.food) for g in range(session.world.groups)}
                self.assertEqual(len(set(counts.values())),1)

    def test_physical_export_declares_rules_and_replay_detects_tampering(self):
        session=HabitatSession(config(population=4,food_count=0),{'enabled':True})
        for _ in range(30):session.step()
        report,genomes=session.snapshot()
        with tempfile.TemporaryDirectory() as directory:
            bundle=export_habitat(report,genomes,directory)
            checked=verify_bundle(bundle);replay_habitat(checked)
            manifest=json.loads((bundle/'manifest.json').read_text())
            self.assertEqual(manifest['engine_extension'],'physical_habitat_v1')
            self.assertIn('habitat.json',manifest['files_sha256'])
            self.assertIn('v2/backend/habitat.py --replay',(bundle/'report.html').read_text())
            with self.assertRaises(ValueError):replay_run(checked)
        broken=json.loads(json.dumps(report));broken['habitat']['telemetry'][next(iter(broken['habitat']['telemetry']))]['blocked']+=1
        with self.assertRaisesRegex(ValueError,'mismatch'):replay_habitat(broken)
        broken=json.loads(json.dumps(report));broken['habitat']['source_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'source version'):replay_habitat(broken)

    def test_invalid_settings_are_rejected_and_surface_receipts_are_explicit(self):
        for bad in ({'enabled':'yes'},{'max_slope':0},{'grid_spacing':2},{'weather_period':float('nan')},{'unknown':1}):
            with self.assertRaises(ValueError):EngineAdapter(config(),bad)
        adapter=EngineAdapter(config(),{'enabled':True});first=adapter.frame(full=True);later=adapter.frame()
        self.assertIn('habitat_surface',first);self.assertNotIn('habitat_surface',later)
        self.assertEqual(first['habitat_surface']['sha256'],first['habitat']['surface_sha256'])
        self.assertEqual(first['habitat']['climate']['source'],'Python physical habitat')
        self.assertTrue(first['environment_context']['weather_simulated']);self.assertTrue(first['environment_context']['daylight_simulated'])

class PhysicalTransportTests(TransportFixture):
    def test_tcp_configure_export_replay_and_rejection_keep_the_declared_rules(self):
        reply=self.client.request('configure',config=config().to_dict(),habitat={'enabled':True,'weather_period':1.},paused=True)
        self.assertTrue(reply['ok']);run=reply['frame']['run_id']
        self.assertTrue(reply['frame']['habitat']['enabled']);self.assertIn('habitat_surface',reply['frame'])
        rejected=self.client.request('configure',config=config().to_dict(),habitat={'enabled':True,'max_slope':-1})
        self.assertFalse(rejected['ok'])
        self.client.request('step',ticks=120)
        state=self.client.request('state')['report'];self.assertEqual(state['run_id'],run)
        exported=self.client.request('export',root=str(self.directory/'physical'))
        self.assertTrue(exported['ok']);replay_habitat(verify_bundle(exported['bundle']))

if __name__=='__main__':unittest.main()
