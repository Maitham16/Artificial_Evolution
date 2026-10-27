#!/usr/bin/env python3
"""Capture native application documentation; raw frames stay in ignored storage.

This drives the actual Godot Main scene and original ResearchApp. It never
positions creatures, scripts their behavior, or substitutes an art-stage scene.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
from research_session import RunConfig,verify_bundle,replay_run

CASES={
    'living-world':dict(camera='ground',quality=2,warmup_seconds=3),
    'valley':dict(camera='valley',quality=2,warmup_seconds=2),
    'animal-follow':dict(camera='follow',record='locomotion',record_seconds=5,warmup_seconds=2),
    'predator-prey':dict(mode='predator_prey',camera='follow',select='predator',record='locomotion',record_seconds=5),
    'controls':dict(camera='ground',record='controls',record_seconds=6),
    'workbench':dict(camera='overview',immersive=False,warmup_seconds=3),
    'seasons':dict(mode='seasons',camera='overview',ecosystem=True,generation=2,warmup_speed=20,warmup_seconds=1,config_overrides=dict(population=40)),
    'obstacles':dict(mode='obstacles',camera='overview',select='hazard',warmup_seconds=6),
    'traits':dict(mode='traits',camera='overview',immersive=False,generation=2,warmup_speed=20,warmup_seconds=1,config_overrides=dict(population=40)),
    'social':dict(mode='social',camera='overview',immersive=False,warmup_seconds=5),
    'continuous':dict(mode='continuous',camera='follow',select='offspring',record='growth',record_seconds=6,warmup_seconds=1),
    'physical-habitat':dict(camera='ground',habitat=dict(enabled=True,weather_period=2),visuals=dict(weather='auto',season='auto',cycle=True),warmup_seconds=2.5),
    'winter-weather':dict(camera='valley',visuals=dict(weather='snow',season='winter',hour=13,cycle=False),warmup_seconds=2),
}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capture_v1(output):
    """Observe original draws in a real Cocoa window without editing V1 files."""
    os.environ.update(SDL_VIDEODRIVER='cocoa',SDL_AUDIODRIVER='dummy')
    import pygame
    from research_app import ResearchApp
    output.mkdir(parents=True,exist_ok=True)
    app=ResearchApp(RunConfig(),output/'exports')
    if pygame.display.get_driver()=='dummy':raise RuntimeError('V1 capture must use a native display')
    app.session.world.selected_creature=app.session.world.creatures[0]
    original_draw=app.draw
    frames=[];started=time.monotonic();next_frame=1.
    def draw():
        nonlocal next_frame
        original_draw()
        elapsed=time.monotonic()-started
        if elapsed>=next_frame and elapsed<6:
            file=f'frame-{len(frames):04d}.png';pygame.image.save(app.canvas,str(output/file))
            frames.append(dict(file=file,wall_seconds=elapsed-1,ticks=app.session.ticks,
                               simulation_seconds=app.session.elapsed,generation=app.session.world.generation,
                               population=len(app.session.world.creatures),paused=app.session.paused,
                               pixels=list(app.canvas.get_size())))
            next_frame+=1/12
        if elapsed>=6:app.running=False
    app.draw=draw
    app.run(frames=1800,screenshot=output/'application.png')
    bundle=app.last_export
    if bundle is None:raise RuntimeError('Original application did not export its run')
    report=verify_bundle(bundle)
    if replay_run(report).ticks!=report['execution']['ticks']:raise RuntimeError('Original replay mismatch')
    record=dict(case='v1-original',source='Original native Pygame ResearchApp canvas readback',
                headless=False,frames=frames,bundle=str(bundle),config=report['config'],
                verified_and_replayed=True,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                capture_tool_sha256=digest(__file__),platform=platform.platform(),
                still=dict(file='application.png',ticks=report['execution']['ticks'],pixels=frames[-1]['pixels']),
                renderer='Pygame / Cocoa')
    (output/'capture.json').write_text(json.dumps(record,indent=2)+'\n')
    print('V1: captured',len(frames),'real frames and replayed',report['execution']['ticks'],'ticks.',flush=True)


def capture_case(name,raw):
    options=CASES[name].copy();mode=options.pop('mode','foraging')
    if mode=='continuous':
        data=json.loads((ROOT/'v2/configs/animation_lifecycle.json').read_text())
        data['maturity_age']=6. # Explicit six-second visual maturation demonstration.
    else:
        algorithms={'predator_prey':'coevolution','social':'group'}
        data=RunConfig(mode=mode,algorithm=algorithms.get(mode,'selection'),
                       environment='seasonal' if mode=='seasons' else 'uniform').to_dict()
    data.update(options.pop('config_overrides',{}))
    config=RunConfig.from_dict(data)
    output=raw/name;output.mkdir(parents=True,exist_ok=True)
    config_path=output/'configuration.json';config_path.write_text(json.dumps(config.to_dict(),indent=2)+'\n')
    plan=dict(name=name,output=str(output),config_path=str(config_path),**options)
    plan_path=output/'plan.json';plan_path.write_text(json.dumps(plan,indent=2)+'\n')
    command=[str(ROOT/'v2/Run Artificial Evolution 2.command'),'--resolution','1520x960',
             '--script','tools/capture_documentation.gd','--','--no-auto-save',f'--capture-plan={plan_path}']
    with (output/'capture.log').open('w') as log:
        result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180)
    text=(output/'capture.log').read_text()
    if result.returncode or any(marker in text for marker in ('SCRIPT ERROR','\nERROR:','DOCUMENTATION_CAPTURE_ERROR')):
        raise RuntimeError(name+': '+text)
    record=json.loads((output/'capture.json').read_text())
    report=verify_bundle(record['bundle'])
    if 'habitat' in report:
        sys.path.insert(0,str(ROOT/'v2/backend'));from habitat import replay_habitat
        replay_habitat(report)
    else:replay_run(report)
    if record['event_gaps']:raise RuntimeError(name+': source event gap')
    if name=='continuous' and not any(p['parent'] is not None for p in report['individuals']):raise RuntimeError('No actual offspring')
    if name=='traits' and len({tuple(p['body']) for p in report['individuals'] if p['generation']==2})<2:raise RuntimeError('No inherited body variation')
    record.update(verified_and_replayed=True,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  capture_tool_sha256=digest(ROOT/'v2/tools/capture_documentation.gd'),platform=platform.platform())
    (output/'capture.json').write_text(json.dumps(record,indent=2)+'\n')
    print(name,': native image,',len(record['frames']),'frames;',report['execution']['ticks'],'ticks; declared replay passed.',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',nargs='+',choices=[*CASES,'v1-original'],default=[*CASES,'v1-original'])
    parser.add_argument('--raw',type=Path,default=ROOT/'.cache/documentation-media/raw')
    args=parser.parse_args();raw=args.raw.resolve();raw.mkdir(parents=True,exist_ok=True)
    for name in args.cases:
        if name=='v1-original':capture_v1(raw/name)
        else:capture_case(name,raw)


if __name__=='__main__':main()
