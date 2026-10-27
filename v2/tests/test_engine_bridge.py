"""Authority, transport and compatibility checks against the real Python engine."""
from dataclasses import replace
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'v2/backend'))
from engine_bridge import EngineAdapter,RunConfig,catalog,encode,decode
from research_session import ResearchSession,replay_run,verify_bundle
import numpy as np


def config(mode='foraging',**changes):
    data=RunConfig(mode=mode,algorithm=catalog()['algorithms'][mode][0],population=12,groups=3,
                   predators=3,food_count=None if mode=='seasons' else 30,
                   environment='seasonal' if mode=='seasons' else 'uniform',generations=3)
    return replace(data,**changes)


def scientific_state(session):
    report,_=session.snapshot()
    return {k:report[k] for k in ('config','execution','metrics','samples','individuals','telemetry','simulation')}


class ObservationTests(unittest.TestCase):
    def test_all_seven_modes_match_direct_python_even_with_repeated_observation(self):
        for mode in catalog()['modes']:
            with self.subTest(mode=mode):
                adapter=EngineAdapter(config(mode));reference=ResearchSession(config(mode))
                for tick in range(180):
                    adapter.session.step();reference.step()
                    if tick%5==0:adapter.frame(full=tick==0)
                self.assertEqual(scientific_state(adapter.session),scientific_state(reference))
                for key in reference.genomes:
                    for a,b in zip(adapter.session.genomes[key],reference.genomes[key]):
                        np.testing.assert_array_equal(a,b)
                frame=adapter.frame(full=True)
                self.assertEqual(frame['food'],[[f.x,f.y,f.radius] for f in reference.world.food])
                self.assertEqual(frame['metrics'],reference.metrics())

    def test_all_foraging_policies_reuse_original_reproduction_across_cohorts(self):
        for policy in catalog()['algorithms']['foraging']:
            with self.subTest(policy=policy):
                cfg=config(algorithm=policy,food_count=0,environment='barren',population=4)
                adapter=EngineAdapter(cfg);reference=ResearchSession(cfg)
                for tick in range(2600):
                    adapter.session.step();reference.step()
                    if tick%60==0:adapter.frame()
                self.assertGreater(adapter.session.world.generation,1)
                self.assertEqual(scientific_state(adapter.session),scientific_state(reference))

    def test_frame_exposes_original_hazard_cost_geometry_and_contact_damage(self):
        adapter=EngineAdapter(config('obstacles'))
        s=adapter.session;c=s.world.creatures[0];hazard=s.world.dangers[0]
        c.x,c.y=hazard.x,hazard.y
        s.step();frame=adapter.frame()
        row=next(a for a in frame['agents'] if a['id']==s.key(c))
        self.assertTrue(row['in_hazard']);self.assertGreater(row['hazard_loss'],0)
        self.assertEqual(row['energy'],c.energy)
        self.assertEqual(frame['hazards'],[[h.x,h.y,h.radius] for h in s.world.dangers])
        self.assertEqual(row['energy_cost'],c.energy_cost_per_second)

    def test_continuous_births_and_ancestry_are_observed_from_original_registry(self):
        adapter=EngineAdapter(config('continuous',maturity_age=.1,birth_cooldown=.1,body_mutation_rate=0,population_cap=24))
        for _ in range(30):adapter.session.step()
        frame=adapter.frame(full=True)
        self.assertGreater(frame['birth_count'],12)
        self.assertEqual(frame['birth_count'],len(adapter.session.world.registry))
        children=[b for b in frame['birth_delta'] if b['parent']]
        self.assertTrue(children)
        for child in children:self.assertIn(child['parent'],adapter.session.births)
        self.assertEqual({a['id'] for a in frame['agents'] if a['active']},
                         {adapter.session.key(c) for c in adapter.session.world.creatures})

    def test_social_sharing_is_read_from_existing_interaction(self):
        adapter=EngineAdapter(config('social'))
        s=adapter.session;group=[c for c in s.world.creatures if c.group_id==0]
        a,b=group[:2];a.x=a.y=100;b.x=110;b.y=100;a.energy=100;b.energy=20;a.share_effort=1
        s.world._share_food()
        frame=adapter.frame()
        row=next(c for c in frame['agents'] if c['id']==s.key(b))
        self.assertGreater(row['shared_in'],0);self.assertEqual(row['energy'],b.energy)
        self.assertEqual(frame['sharing'],[[s.key(a),s.key(b)]])

    def test_predation_deaths_and_captures_are_observed_from_existing_physics(self):
        adapter=EngineAdapter(config('predator_prey',population=4,predators=2,food_count=0))
        s=adapter.session
        for c in s.world.creatures:c.x=c.y=250;c.heading=0
        s.world.creatures[1].x=800
        s.step();frame=adapter.frame()
        self.assertGreater(sum(c['captures'] for c in frame['agents']),0)
        self.assertTrue(any(c.death_cause=='predation' for c in s.actors.values()))
        self.assertLess(frame['metrics']['population'],4)

    def test_protocol_rejects_nonfinite_or_nonobject_json(self):
        for raw in [b'[]',b'{"value":NaN}',b'{"value":Infinity}']:
            with self.assertRaises(ValueError):decode(raw)


class Client:
    def __init__(self,endpoint):
        self.sock=socket.create_connection(('127.0.0.1',endpoint['port']),timeout=10)
        self.buffer=bytearray();self.index=0;self.last_ping=time.monotonic();self.sock.settimeout(.5)
        self.request('hello',protocol=1,token=endpoint['token'])

    def request(self,cmd,**data):
        self.index+=1;self.sock.sendall(encode(dict(id=self.index,cmd=cmd,**data)))
        return self.response(self.index)

    def response(self,ident):
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            if time.monotonic()-self.last_ping>2:
                self.sock.sendall(encode(dict(id=0,cmd='ping')));self.last_ping=time.monotonic()
            end=self.buffer.find(b'\n')
            if end<0:
                try:raw=self.sock.recv(65536)
                except socket.timeout:continue
                if not raw:raise ConnectionError('Backend disconnected')
                self.buffer.extend(raw);continue
            raw=bytes(self.buffer[:end]);del self.buffer[:end+1]
            message=json.loads(raw)
            if message.get('type')=='response' and message.get('id')==ident:return message
        raise TimeoutError('No matching bridge response')

    def close(self):self.sock.close()


class TransportFixture(unittest.TestCase):
    AUTO_SAVE=False
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(prefix='ae2-bridge-test-')
        self.directory=Path(self.folder.name)
        self.endpoint=self.directory/'endpoint.json'
        self.log=(self.directory/'server.log').open('w')
        command=[sys.executable,str(ROOT/'v2/backend/engine_bridge.py'),
            '--ready-file',str(self.endpoint),'--export-root',str(self.directory/'exports')]
        if not self.AUTO_SAVE:command.append('--no-auto-save')
        self.process=subprocess.Popen(command,stdout=self.log,stderr=subprocess.STDOUT)
        deadline=time.monotonic()+10
        while not self.endpoint.exists() and time.monotonic()<deadline and self.process.poll() is None:time.sleep(.01)
        self.assertTrue(self.endpoint.exists(),(self.directory/'server.log').read_text())
        self.metadata=json.loads(self.endpoint.read_text())
        self.client=Client(self.metadata)

    def tearDown(self):
        if self.client:
            try:
                if self.process.poll() is None:self.client.request('shutdown',save=False)
            except (OSError,ConnectionError):pass
            self.client.close()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=5)
        self.log.close();self.folder.cleanup()

    def start(self,cfg=None):
        reply=self.client.request('configure',config=(cfg or config()).to_dict(),paused=True)
        self.assertTrue(reply['ok'],reply)
        self.assertEqual(reply['frame']['ticks'],0)
        return reply


class TransportTests(TransportFixture):
    def test_paused_steps_over_socket_match_direct_python_and_reject_pose_writes(self):
        cfg=config();self.start(cfg)
        reply=self.client.request('step',ticks=120)
        self.assertEqual(reply['frame']['ticks'],120)
        direct=ResearchSession(cfg);direct.set_control('paused',True)
        for _ in range(120):direct.step()
        report=self.client.request('state')['report']
        self.assertEqual({k:report[k] for k in scientific_state(direct)},scientific_state(direct))
        rejected=self.client.request('set_position',x=0,y=0)
        self.assertFalse(rejected['ok'])
        self.assertEqual(self.client.request('state')['report']['individuals'],report['individuals'])

    def test_wire_supports_every_existing_mode(self):
        for mode in catalog()['modes']:
            with self.subTest(mode=mode):
                self.start(config(mode))
                reply=self.client.request('step',ticks=60)
                self.assertTrue(reply['ok'],reply)
                self.assertEqual(reply['frame']['config']['mode'],mode)
                self.assertEqual(reply['frame']['ticks'],60)

    def test_bad_configuration_cannot_replace_live_session(self):
        initial=self.start()['frame']['run_id']
        bad=config().to_dict();bad['population']=-1
        self.assertFalse(self.client.request('configure',config=bad)['ok'])
        self.assertEqual(self.client.request('state')['report']['run_id'],initial)

    def test_full_precision_seed_survives_configuration_text(self):
        seed=2**63-1;data=config().to_dict();data['seed']=seed
        reply=self.client.request('configure',config_json=json.dumps(data),paused=True)
        self.assertTrue(reply['ok']);self.assertEqual(reply['frame']['seed_text'],str(seed))
        self.assertEqual(self.client.request('state')['report']['config']['seed'],seed)

    def test_fragmented_utf8_and_many_coalesced_commands(self):
        self.start()
        self.client.index+=1;ident=self.client.index
        payload=encode(dict(id=ident,cmd='ping',note='creature 🍃'))
        for chunk in [payload[:3],payload[3:-3],payload[-3:-1],payload[-1:]]:self.client.sock.sendall(chunk)
        self.assertTrue(self.client.response(ident)['ok'])
        start=self.client.index+1
        self.client.sock.sendall(b''.join(encode(dict(id=i,cmd='ping')) for i in range(start,start+70)))
        for ident in range(start,start+70):self.assertTrue(self.client.response(ident)['ok'])
        self.client.index=start+69

    def test_second_client_cannot_take_control(self):
        sock=socket.create_connection(('127.0.0.1',self.metadata['port']),timeout=2)
        sock.sendall(encode(dict(id=1,cmd='hello',protocol=1,token=self.metadata['token'])))
        self.assertEqual(sock.recv(1024),b'');sock.close()
        self.assertTrue(self.client.request('ping')['ok'])

    def test_invalid_token_is_rejected(self):
        sock=socket.create_connection(('127.0.0.1',self.metadata['port']),timeout=2)
        sock.sendall(encode(dict(id=1,cmd='hello',protocol=1,token='wrong')))
        self.assertEqual(sock.recv(1024),b'');sock.close()

    def test_disconnect_pauses_and_reconnect_retains_same_run(self):
        initial=self.start()['frame']['run_id']
        self.client.request('control',name='paused',value=False)
        time.sleep(.12);self.client.close();self.client=None;time.sleep(.1)
        self.client=Client(self.metadata)
        report=self.client.request('state')['report'];ticks=report['execution']['ticks']
        self.assertEqual(report['run_id'],initial);self.assertTrue(report['execution']['paused'])
        time.sleep(.08)
        self.assertEqual(self.client.request('state')['report']['execution']['ticks'],ticks)

    def test_export_is_the_original_verifiable_and_replayable_bundle(self):
        self.start();self.client.request('step',ticks=180)
        result=self.client.request('export',root=str(self.directory/'export-check'))
        self.assertTrue(result['ok'],result)
        report=verify_bundle(result['bundle'])
        self.assertEqual(report['execution']['ticks'],180)
        replay=replay_run(report)
        self.assertEqual(replay.ticks,180)
        self.assertEqual(report['individuals'],self.client.request('state')['report']['individuals'])
        self.assertTrue((Path(result['bundle'])/'genomes.npz').exists())
        self.assertEqual(self.endpoint.stat().st_mode & 0o777,0o600)


class ArchivingTests(TransportFixture):
    AUTO_SAVE=True

    def test_replacement_archives_original_python_run_before_switching(self):
        old=self.start()['frame']['run_id'];self.client.request('step',ticks=60)
        reply=self.client.request('configure',config=config(seed=42).to_dict(),paused=True)
        self.assertTrue(reply['ok'],reply);self.assertNotEqual(reply['frame']['run_id'],old)
        bundles=list((self.directory/'exports').glob('run-*'));self.assertEqual(len(bundles),1)
        report=verify_bundle(bundles[0]);self.assertEqual(report['run_id'],old)
        self.assertEqual(replay_run(report).ticks,60)
        self.assertEqual(self.client.request('state')['report']['config']['seed'],42)

    def test_failed_archive_keeps_previous_run_and_reports_shutdown_failure(self):
        old=self.start()['frame']['run_id'];self.client.request('step',ticks=60)
        (self.directory/'exports').write_text('Blocked test output path')
        reply=self.client.request('configure',config=config(seed=42).to_dict(),paused=True)
        self.assertFalse(reply['ok']);self.assertIn('retained',reply['error'])
        self.assertEqual(self.client.request('state')['report']['run_id'],old)
        failed=self.client.request('shutdown')
        self.assertFalse(failed['ok']);self.assertIn('remains paused',failed['error'])
        self.assertIsNone(self.process.poll())

    def test_reconnect_during_archive_does_not_lose_new_run_ancestry(self):
        old=self.start()['frame']['run_id'];self.client.request('step',ticks=60)
        self.client.index+=1
        self.client.sock.sendall(encode(dict(id=self.client.index,cmd='configure',config=config(population=4).to_dict(),paused=True)))
        # A later ping acknowledgement proves the configure command was read.
        # Closing with unread TCP data before that can legitimately cancel it.
        self.assertTrue(self.client.request('ping')['ok'])
        self.client.close();self.client=None
        time.sleep(.03)
        self.client=Client(self.metadata)
        # An old-run acknowledgement must not suppress the new run's ledger.
        self.client.sock.sendall(encode(dict(cmd='seen',count=12,run_id=old)))
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            report=self.client.request('state')['report']
            if report['run_id']!=old:break
            time.sleep(.02)
        self.assertNotEqual(report['run_id'],old)
        reply=self.client.request('control',name='paused',value=True)
        self.assertEqual(reply['frame']['birth_count'],4)
        self.assertEqual(len(reply['frame']['birth_delta']),4)

    def test_shutdown_saves_a_replayable_python_bundle(self):
        self.start();self.client.request('step',ticks=90)
        reply=self.client.request('shutdown')
        self.assertTrue(reply['ok'],reply)
        self.process.wait(timeout=5)
        report=verify_bundle(reply['bundle']);self.assertEqual(replay_run(report).ticks,90)


if __name__=='__main__':unittest.main()
