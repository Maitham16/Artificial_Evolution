"""Transport/observation adapter for the unchanged root Python research engine.

No simulation rules live here. ResearchSession owns every physics tick, neural
choice, birth, meal, interaction, generation, and scientific export.
"""
from __future__ import annotations

import argparse
import base64
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import selectors
import signal
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('MPLBACKEND', 'Agg')
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'v2/.cache/matplotlib'))

import numpy as np
from research_session import (ALGORITHMS, ENVIRONMENTS, MODES, MODE_NAMES, VERSION,
                              ResearchSession, RunConfig, export_bundle)
from world import SIMULATION_STEP
from obstacles import HAZARD_ENERGY_PER_SECOND

PROTOCOL = 1
MAX_MESSAGE = 8 * 1024 * 1024


def encode(value):
    return (json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def decode(raw):
    def reject(value):
        raise ValueError('Nonfinite JSON values are not supported.')
    value = json.loads(raw, parse_constant=reject)
    if not isinstance(value, dict):
        raise ValueError('A request must be a JSON object.')
    return value


def configuration(request):
    # Preserve 63-bit seeds when a Godot JSON parser would otherwise round them.
    data = json.loads(request['config_json']) if 'config_json' in request else dict(request.get('config', {}))
    if not isinstance(data, dict):
        raise ValueError('Configuration must be an object.')
    if 'seed_text' in request:
        text = request['seed_text']
        if not isinstance(text, str) or not text.isascii() or not text.isdecimal():
            raise ValueError('Seed must contain decimal digits.')
        data['seed'] = int(text)
    return RunConfig.from_dict(data)


def catalog():
    presets = {}
    for path in sorted((ROOT / 'configs').glob('*.json')):
        data = RunConfig.load(path).to_dict()
        presets[path.stem] = dict(config=data, seed_text=str(data['seed']))
    return dict(protocol=PROTOCOL, engine_version=VERSION, engine_root=str(ROOT),
                modes=list(MODES), mode_names=MODE_NAMES,
                algorithms={k: list(v) for k, v in ALGORITHMS.items()},
                environments={k: dict(width=v[0], height=v[1], food=v[3]) for k, v in ENVIRONMENTS.items()},
                defaults=RunConfig().to_dict(), presets=presets,
                physics_step=SIMULATION_STEP, speeds=[1, 5, 20])


class EngineAdapter:
    """Passive view of real engine objects, plus calls to the public session API."""
    def __init__(self, config=None):
        self.session = ResearchSession(config or RunConfig())
        self.selected = self.session.key(self.session.world.creatures[0])
        self.sequence = 0
        self.chart_stamp = None
        self.food_serial = 0
        self.food_observations = {}
        self.capture_generation = self.session.world.generation
        self.capture_cursor = 0
        self.season_signature = None
        self.view_sequence = 0
        self.view_events = deque(maxlen=4096)
        self.view_seen_births = len(self.session.births)
        self.view_watch = {key: (c, c.food_eaten, getattr(c, 'captures', 0))
                           for key, c in self.session.actors.items()}

    def update(self, seconds):
        self.session.update(seconds, max_ticks=32)

    def observe_animation_events(self):
        """Read actual counters/ledgers. Never alter creatures or run extra decisions."""
        s = self.session
        living = {s.key(c) for c in s.world.creatures}
        births = list(s.births.values())
        new_births = births[self.view_seen_births:]
        self.view_seen_births = len(births)

        def event(kind, key, **extra):
            c = s.actors[key]
            self.view_sequence += 1
            birth = s.births[key]
            self.view_events.append(dict(seq=self.view_sequence, kind=kind, id=key,
                time=s.elapsed, x=c.x, y=c.y, heading=c.heading, radius=float(c.radius),
                age=c.age, root=birth['founder'], parent=birth['parent'],
                species=getattr(c, 'species', None), cause=c.death_cause,
                maturity_age=getattr(s.world, 'maturity_age', None), **extra))

        for birth in new_births:
            key = birth['key']; c = s.actors[key]
            self.view_watch[key] = (c, 0, 0)
            event('birth', key, born_at=birth['born_at'], continuous=s.config.mode == 'continuous')
            # Continuous births are funded clonal reproduction. Cohort replacement
            # is selection/copying, not physical mating and not a death.
            if s.config.mode == 'continuous' and birth['parent'] in s.actors:
                event('reproduce', birth['parent'], child=key)
        source_captures = getattr(s.world, 'captures', ())
        if self.capture_generation != s.world.generation:
            self.capture_generation, self.capture_cursor = s.world.generation, 0
        new_captures = source_captures[self.capture_cursor:]
        self.capture_cursor = len(source_captures)
        for key, (c, meals, captures) in list(self.view_watch.items()):
            if c.food_eaten > meals: event('meal', key, count=c.food_eaten-meals)
            if getattr(c, 'captures', 0) > captures:
                targets = [f"g{c.generation}:c{item['prey_id']}" for item in new_captures
                           if item['predator_id'] == c.creature_id and c.generation == s.world.generation]
                event('capture', key, count=c.captures-captures, targets=targets)
            if not c.alive:
                event('death', key)
                del self.view_watch[key]
            elif key not in living:
                event('retire', key)
                del self.view_watch[key]
            else:
                self.view_watch[key] = (c, c.food_eaten, getattr(c, 'captures', 0))

    def environment_context(self):
        w = self.session.world
        history = getattr(w, 'environment_history', ())
        season = None
        if self.session.config.mode == 'seasons' and history:
            row = history[-1]
            season = {key: row[key] for key in ('generation', 'season', 'season_index', 'cycle', 'food_count')}
            season['cluster_centers'] = [list(p) for p in w.food_cluster_centers]
        return dict(season=season, food_target=w.food_count, actual_food=len(w.food),
                    source='Python simulation', weather_simulated=False, daylight_simulated=False)

    def observe_food(self):
        current = {}
        records = []
        for food in self.session.world.food:
            identity = id(food)
            record = self.food_observations.get(identity)
            if record is None or record[0] is not food:
                self.food_serial += 1
                record = (food, f'f{self.food_serial}')
            current[identity] = record
            records.append(dict(id=record[1], x=food.x, y=food.y,
                                radius=food.radius, energy=food.energy))
        self.food_observations = current
        return records

    def frame(self, seen_births=0, full=False, seen_animation=0):
        s, w = self.session, self.session.world
        self.observe_animation_events()
        context = self.environment_context()
        if context['season'] is not None:
            signature = (context['season']['season'], context['season']['cycle'])
            if self.season_signature is not None and signature != self.season_signature:
                self.view_sequence += 1
                self.view_events.append(dict(seq=self.view_sequence, kind='season', id='environment',
                                             time=s.elapsed, context=context['season']))
            self.season_signature = signature
        living_keys = {s.key(c) for c in w.creatures}
        # Current bodies only. Historical ancestry is sent separately and is never
        # reconstructed from display interpolation.
        members = list(w.creatures)
        if self.selected in s.actors and self.selected not in {s.key(c) for c in members}:
            members.append(s.actors[self.selected])
        agents = []
        for c in members:
            key = s.key(c)
            birth = s.births[key]
            agents.append(dict(id=key, x=c.x, y=c.y, heading=c.heading, radius=float(c.radius),
                               alive=c.alive, active=c.alive and key in living_keys, age=c.age, energy=c.energy,
                               capacity=c.energy_capacity, lifespan=c.lifespan, meals=c.food_eaten,
                               fitness=c.age if s.config.mode == 'social' else c.fitness,
                               root=birth['founder'], parent=birth['parent'], depth=birth['depth'],
                               generation=c.generation, species=getattr(c, 'species', None),
                               group=getattr(c, 'group_id', None), cause=c.death_cause,
                               speed=c.speed, max_speed=c.max_speed, turn_rate=c.turn_rate,
                               toward_seconds=getattr(c, 'toward_seconds', 0.),
                               away_seconds=getattr(c, 'away_seconds', 0.),
                               opponent_visible_seconds=getattr(c, 'opponent_visible_seconds', 0.),
                               born_at=birth['born_at'],
                               maturity_age=getattr(w, 'maturity_age', None),
                               vision=w.vision_range_for(c),
                               energy_cost=c.energy_cost_per_second,
                               in_hazard=getattr(c, 'in_danger', False),
                               hazard_loss=getattr(c, 'hazard_energy_lost', 0.),
                               hazard_seconds=getattr(c, 'hazard_seconds', 0.),
                               collisions=getattr(c, 'collisions', 0),
                               captures=getattr(c, 'captures', 0), children=getattr(c, 'children', 0),
                               signal=getattr(c, 'signal', 0.), shared_in=getattr(c, 'shared_in', 0.),
                               shared_out=getattr(c, 'shared_out', 0.)))
        if hasattr(w, 'perceive_opponents'):
            by_species = {role: [c for c in w.creatures if c.species == role] for role in ('prey', 'predator')}
            for row in agents:
                if not row['active']: continue
                c = s.actors[row['id']]
                others = by_species['prey' if c.species == 'predator' else 'predator']
                positions = np.array([(other.x, other.y) for other in others]).reshape(-1, 2)
                perception = w.perceive_opponents(c, positions)
                if perception.visible:
                    target = next(other for other in others if (other.x, other.y) == tuple(perception.target_position))
                    row['observed_opponent'] = dict(id=s.key(target), x=target.x, y=target.y,
                                                    distance=math.hypot(c.x-target.x, c.y-target.y), source='nearest visible opponent')
        activation, inputs = [], []
        selected = s.actors.get(self.selected)
        if selected and selected.alive and self.selected in living_keys and s.config.algorithm not in ('random', 'greedy'):
            values = w.get_sensory_inputs(selected)
            inputs = values.tolist()
            # Same passive current-state preview as ResearchApp; not an extra
            # decision and never applied back to the creature.
            activation = np.tanh(values @ selected.brain.input_weights + selected.brain.hidden_bias).tolist()
        births = list(s.births.values())
        delta = [dict(id=b['key'], root=b['founder'], parent=b['parent'], generation=b['generation'],
                      depth=b['depth'], born_at=b['born_at'], species=b['species'], group=b['group'])
                 for b in births[max(0, seen_births):]]
        by_id = {c.creature_id: s.key(c) for c in w.creatures}
        self.sequence += 1
        frame = dict(type='frame', protocol=PROTOCOL, seq=self.sequence, run_id=s.run_id,
                     ticks=s.ticks, time=s.elapsed, generation=w.generation,
                     animation_events=[e for e in self.view_events if e["seq"] > seen_animation], animation_sequence=self.view_sequence,
                     animation_floor=self.view_events[0]['seq'] if self.view_events else self.view_sequence+1,
                     config=s.config.to_dict(), seed_text=str(s.config.seed),
                     paused=s.paused, speed=s.speed, automatic=s.automatic, finished=s.finished,
                     extinct=getattr(w, 'lineage_extinct', False),
                     awaiting_generation=w.final_evaluation is not None and not s.finished,
                     width=w.width, height=w.height, agents=agents, environment_context=context, food_objects=self.observe_food(),
                     food=[[f.x, f.y, f.radius] for f in w.food],
                     barriers=[[b.x, b.y, b.width, b.height] for b in getattr(w, 'barriers', ())],
                     hazards=[[h.x, h.y, h.radius] for h in getattr(w, 'dangers', ())],
                     group_arenas=[[g, *w.origin(g), *w.cell_size] for g in range(w.groups)] if hasattr(w, 'cell_size') else [],
                     hazard_energy_per_second=HAZARD_ENERGY_PER_SECOND if hasattr(w, 'dangers') else 0.,
                     metrics=s.metrics(), selected=self.selected,
                     activation=activation, inputs=inputs, birth_count=len(births), birth_delta=delta,
                     sharing=[[by_id[edge['donor_id']], by_id[edge['recipient_id']]]
                              for edge in getattr(w, 'transfer_edges', {}).values()
                              if w.elapsed_time-edge['last_time'] <= .5
                              and edge['donor_id'] in by_id and edge['recipient_id'] in by_id])
        stamp = (s.ticks // 60, w.generation, len(s.samples))
        if full or stamp != self.chart_stamp:
            frame['charts'] = dict(samples=s.samples[-720:],
                                   history=[asdict(row) for row in w.generation_stats[-100:]])
            self.chart_stamp = stamp
        return frame


class Peer:
    def __init__(self, sock):
        self.sock = sock
        self.buffer = bytearray()
        self.responses = deque()
        self.latest = None
        self.current = b''
        self.authenticated = False
        self.seen_births = 0
        self.seen_animation = 0
        self.seen_run = None
        self.last_seen = time.monotonic()

    def response(self, value):
        self.responses.append(encode(value))
        if sum(map(len, self.responses)) > 16 * 1024 * 1024:
            raise ValueError('Client is not reading command responses.')

    def frame(self, value):
        # Drop only superseded presentation frames, never commands or physics
        # ticks. Preserve a chart update if its frame has not yet been sent.
        if self.latest and 'charts' in self.latest and 'charts' not in value:
            value['charts'] = self.latest['charts']
        self.latest = value

    def flush(self):
        if not self.current:
            if self.responses:
                self.current = self.responses.popleft()
            elif self.latest:
                self.current = encode(self.latest)
                self.latest = None
        if self.current:
            try:
                sent = self.sock.send(self.current)
                if not sent:
                    raise ConnectionError('Socket closed.')
                self.current = self.current[sent:]
            except BlockingIOError:
                pass


class BridgeServer:
    def __init__(self, ready_file, export_root, owner_pid=0, auto_save=True, fps=30):
        self.ready_file = Path(ready_file)
        self.export_root = Path(export_root).resolve()
        self.owner_pid, self.auto_save, self.fps = owner_pid, auto_save, fps
        self.token = secrets.token_urlsafe(32)
        self.stream_id = secrets.token_hex(12)
        self.frame_sequence = 0
        self.adapter = None
        self.selector = selectors.DefaultSelector()
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(4)
        self.listener.setblocking(False)
        self.selector.register(self.listener, selectors.EVENT_READ)
        self.peers = {}
        self.active = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='python-engine-export')
        self.pending = None
        self.last_export = None
        self.running = True
        self.shutdown_request = None
        self.shutdown_save = auto_save
        self.replacement = None
        self.start = time.monotonic()
        self.last = self.start
        self.last_frame = 0.
        self.last_owner_check = 0.

    def publish(self):
        self.ready_file.parent.mkdir(parents=True, exist_ok=True)
        data = dict(protocol=PROTOCOL, port=self.listener.getsockname()[1], token=self.token,
                    pid=os.getpid(), engine_root=str(ROOT), engine_version=VERSION)
        if self.ready_file.exists():
            raise FileExistsError('Use a new endpoint filename.')
        temporary = self.ready_file.with_suffix('.pending')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream)
        temporary.replace(self.ready_file)

    def drop(self, peer):
        try:
            self.selector.unregister(peer.sock)
        except (KeyError, ValueError):
            pass
        self.peers.pop(peer.sock, None)
        peer.sock.close()
        if self.active is peer:
            self.active = None
            if self.adapter and not self.adapter.session.paused:
                self.adapter.session.set_control('paused', True)

    def frame(self, full=False):
        if self.active.seen_run != self.adapter.session.run_id:
            self.active.seen_run = self.adapter.session.run_id
            self.active.seen_births = 0
            self.active.seen_animation = 0
        frame = self.adapter.frame(self.active.seen_births, full=full, seen_animation=self.active.seen_animation)
        frame['wall_time'] = time.monotonic() - self.start
        frame['stream_id'] = self.stream_id
        self.frame_sequence += 1
        frame['seq'] = self.frame_sequence
        return frame

    def start_export(self, peer, request_id, root=None, screenshot=None):
        if self.pending:
            raise ValueError('An export is already running; wait for completion.')
        report, genomes = self.adapter.session.snapshot()
        root = self.export_root if root is None else Path(root).expanduser().resolve()
        future = self.executor.submit(export_bundle, report, genomes, root, screenshot)
        self.pending = (future, peer, request_id, report['run_id'], report['execution']['ticks'])

    def command(self, peer, request):
        request_id = request.get('id')
        command = request.get('cmd')
        if not peer.authenticated:
            if command != 'hello' or request.get('protocol') != PROTOCOL or not isinstance(request.get('token'), str) or not hmac.compare_digest(request['token'], self.token):
                raise PermissionError('Invalid bridge handshake.')
            if self.active is not None:
                raise PermissionError('The simulation already has a controlling viewer.')
            peer.authenticated = True
            self.active = peer
            peer.response(dict(type='response', id=request_id, ok=True, catalog={**catalog(), 'has_session': self.adapter is not None}))
            if self.adapter:
                peer.frame(self.frame(full=True))
            return
        if command == 'ping':
            peer.response(dict(type='response', id=request_id, ok=True))
            return
        if command == 'seen':
            count = request.get('count')
            if self.adapter and request.get('run_id') == self.adapter.session.run_id and type(count) is int and 0 <= count <= len(self.adapter.session.births):
                peer.seen_births = max(peer.seen_births, count)
                sequence = request.get('animation_sequence')
                if type(sequence) is int and 0 <= sequence <= self.adapter.view_sequence:
                    peer.seen_animation = max(peer.seen_animation, sequence)
            return
        if command == 'validate_config':
            config = configuration(request)
            peer.response(dict(type='response', id=request_id, ok=True,
                               config=config.to_dict(), seed_text=str(config.seed)))
            return
        if command == 'configure':
            config = configuration(request)
            if self.pending:
                raise ValueError('Wait for the current export before starting a new run.')
            candidate = EngineAdapter(config)  # Validate and construct before replacing a live run.
            if 'paused' in request and type(request['paused']) is not bool:
                raise ValueError('Paused must be boolean.')
            if request.get('paused', False):
                candidate.session.set_control('paused', True)
            if self.adapter and self.adapter.session.ticks and self.auto_save:
                was_paused = self.adapter.session.paused
                self.adapter.session.set_control('paused', True)
                self.start_export(None, None)
                self.replacement = (candidate, peer, request_id, was_paused)
                return
            self.adapter = candidate
            peer.seen_births = 0
            peer.seen_animation = 0
            self.last_export = None
            self.last = time.monotonic()
            peer.latest = None
            peer.response(dict(type='response', id=request_id, ok=True, frame=self.frame(full=True)))
            return
        if command == 'shutdown':
            if type(request.get('save', True)) is not bool:
                raise ValueError('Save-on-shutdown must be boolean.')
            self.shutdown_save = self.auto_save and request.get('save', True)
            if self.adapter and not self.adapter.session.paused:
                self.adapter.session.set_control('paused', True)
            self.shutdown_request = (peer, request_id)
            return
        if not self.adapter:
            raise ValueError('Configure a Python session first.')
        s = self.adapter.session
        if command == 'control':
            s.set_control(request.get('name'), request.get('value'))
        elif command == 'advance':
            if not s.advance():
                raise ValueError('There is no completed cohort ready to advance.')
        elif command == 'step':
            count = request.get('ticks')
            if not s.paused or type(count) is not int or not 1 <= count <= 3600:
                raise ValueError('Single-step requires a paused session and 1–3600 ticks.')
            for _ in range(count):
                if not s.step():
                    break
        elif command == 'select':
            key = request.get('key')
            if key not in s.actors:
                raise ValueError('Unknown creature identity.')
            self.adapter.selected = key
        elif command == 'state':
            report, _ = s.snapshot()
            peer.response(dict(type='response', id=request_id, ok=True, report=report))
            return
        elif command == 'export':
            screenshot = None
            if request.get('screenshot'):
                screenshot = base64.b64decode(request['screenshot'], validate=True)
                if len(screenshot) > 4*1024*1024 or not screenshot.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('Provide a PNG screenshot no larger than 4 MiB.')
            self.start_export(peer, request_id, request.get('root'), screenshot)
            return
        else:
            raise ValueError('Unknown bridge command.')
        peer.response(dict(type='response', id=request_id, ok=True, frame=self.frame(full=True)))

    def read(self, peer, receive=True):
        if receive:
            data = peer.sock.recv(65536)
            if not data:
                self.drop(peer)
                return
            peer.buffer.extend(data)
        if len(peer.buffer) > MAX_MESSAGE:
            raise ValueError('Bridge request exceeds 8 MiB.')
        for _ in range(64):
            end = peer.buffer.find(b'\n')
            if end < 0:
                break
            raw = bytes(peer.buffer[:end])
            del peer.buffer[:end+1]
            request_id = None
            try:
                request = decode(raw)
                request_id = request.get('id')
                peer.last_seen = time.monotonic()
                self.command(peer, request)
            except PermissionError:
                self.drop(peer)
                return
            except (ValueError, TypeError, KeyError, OverflowError) as error:
                peer.response(dict(type='response', id=request_id, ok=False, error=str(error)))

    def maintenance(self):
        if self.pending and self.pending[0].done():
            future, peer, request_id, run_id, ticks = self.pending
            self.pending = None
            try:
                path = future.result()
                self.last_export = (run_id, ticks, str(path))
                if self.replacement:
                    candidate, owner, rid, _ = self.replacement
                    self.replacement = None
                    self.adapter = candidate
                    self.last_export = None
                    if owner.sock in self.peers:
                        owner.seen_births = 0
                        owner.seen_animation = 0
                        owner.latest = None
                        owner.response(dict(type='response', id=rid, ok=True, frame=self.frame(full=True)))
                    else:
                        candidate.session.set_control('paused', True)
                if peer and peer.sock in self.peers:
                    peer.response(dict(type='response', id=request_id, ok=True, bundle=str(path), ticks=ticks))
            except Exception as error:
                if peer and peer.sock in self.peers:
                    peer.response(dict(type='response', id=request_id, ok=False, error='Export failed: '+str(error)))
                print('Export failed:', error, file=sys.stderr, flush=True)
                if self.replacement:
                    _, owner, rid, was_paused = self.replacement
                    self.replacement = None
                    self.adapter.session.set_control('paused', was_paused)
                    if owner.sock in self.peers:
                        owner.response(dict(type='response', id=rid, ok=False, error='Previous run could not be archived; current run retained: '+str(error)))
                if self.shutdown_request:
                    target, rid = self.shutdown_request
                    if target and target.sock in self.peers:
                        target.response(dict(type='response', id=rid, ok=False, error='Run could not be saved; Python remains paused: '+str(error)))
                    else:
                        self.running = False
                self.shutdown_request = None
        if self.shutdown_request and self.pending is None:
            s = self.adapter.session if self.adapter else None
            peer, request_id = self.shutdown_request
            if self.shutdown_save and s and s.ticks and (not self.last_export or self.last_export[:2] != (s.run_id, s.ticks)):
                self.start_export(None, None)
            else:
                if peer and peer.sock in self.peers:
                    peer.response(dict(type='response', id=request_id, ok=True,
                                       bundle=self.last_export[2] if self.last_export else None))
                    # Flush the final small acknowledgement before closing sockets.
                    deadline = time.monotonic()+1
                    while (peer.responses or peer.current) and time.monotonic()<deadline:
                        peer.flush()
                        time.sleep(.001)
                self.running = False

    def serve(self):
        self.publish()
        try:
            while self.running:
                now = time.monotonic()
                dt, self.last = now-self.last, now
                if self.adapter and not self.shutdown_request and not self.replacement:
                    self.adapter.update(dt)
                if now-self.last_owner_check >= 1:
                    self.last_owner_check = now
                    if self.owner_pid:
                        try:
                            os.kill(self.owner_pid, 0)
                        except ProcessLookupError:
                            self.shutdown_request = (None, None)
                            if self.adapter and not self.adapter.session.paused:
                                self.adapter.session.set_control('paused', True)
                    for peer in list(self.peers.values()):
                        if now-peer.last_seen > (10 if peer.authenticated else 5):
                            self.drop(peer)
                if self.active and self.adapter and now-self.last_frame >= 1/self.fps:
                    self.active.frame(self.frame())
                    self.last_frame = now
                self.maintenance()
                for peer in list(self.peers.values()):
                    if b'\n' in peer.buffer:
                        self.read(peer, receive=False)
                    if peer.sock not in self.peers:
                        continue
                    events = selectors.EVENT_READ
                    if peer.current or peer.responses or peer.latest:
                        events |= selectors.EVENT_WRITE
                    self.selector.modify(peer.sock, events)
                for key, events in self.selector.select(.004):
                    if key.fileobj is self.listener:
                        sock, _ = self.listener.accept()
                        sock.setblocking(False)
                        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        if len(self.peers) >= 4:
                            sock.close()
                            continue
                        peer = Peer(sock)
                        self.peers[sock] = peer
                        self.selector.register(sock, selectors.EVENT_READ)
                    else:
                        peer = self.peers.get(key.fileobj)
                        if peer is None:
                            continue
                        try:
                            if events & selectors.EVENT_READ:
                                self.read(peer)
                            if peer.sock in self.peers and events & selectors.EVENT_WRITE:
                                peer.flush()
                        except (ConnectionError, OSError, ValueError):
                            self.drop(peer)
        finally:
            for peer in list(self.peers.values()):
                self.drop(peer)
            self.listener.close()
            self.selector.close()
            self.executor.shutdown(wait=True)
            self.ready_file.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready-file', required=True, type=Path)
    parser.add_argument('--export-root', required=True, type=Path)
    parser.add_argument('--owner-pid', type=int, default=0)
    parser.add_argument('--no-auto-save', action='store_true')
    args = parser.parse_args()
    server = BridgeServer(args.ready_file, args.export_root, args.owner_pid, not args.no_auto_save)
    def stop(signum, frame):
        server.shutdown_request = (None, None)
        if server.adapter and not server.adapter.session.paused:
            server.adapter.session.set_control('paused', True)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    server.serve()


if __name__ == '__main__':
    main()
