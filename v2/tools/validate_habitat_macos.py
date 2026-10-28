#!/usr/bin/env python3
"""Repeated wall-clock FPS trials, real foot IK, and declared physical-habitat replay."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile

V2=Path(__file__).resolve().parents[1];ROOT=V2.parent
OUT=V2/'docs/habitat-validation';ZIP=V2/'build/Artificial Evolution 2.zip'
sys.path[:0]=[str(ROOT),str(V2/'backend')]
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1');os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from research_session import MODES, RunConfig, verify_bundle, replay_run
from habitat import replay_habitat


def run(args,**kwargs):
    result=subprocess.run([str(a) for a in args],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,**kwargs)
    if result.returncode or 'SCRIPT ERROR' in result.stdout or '\nERROR:' in result.stdout or 'were leaked' in result.stdout:raise RuntimeError(result.stdout)
    return result.stdout


def main():
    global OUT, ZIP
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=ZIP)
    parser.add_argument('--output',type=Path,help='Write fresh evidence here instead of replacing historical documentation records.')
    cli=parser.parse_args()
    ZIP=cli.archive.resolve()
    if cli.output:
        OUT=cli.output.resolve()
    screenshots=OUT/'screenshots' if cli.output else V2/'docs/screenshots'
    screenshots.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    registry=Path.home()/'Library/Application Support/ArtificialEvolution2/engine.json'
    remembered=registry.read_bytes() if registry.exists() else None
    with tempfile.TemporaryDirectory(prefix='ae2-habitat-',dir='/private/tmp') as directory:
        stage=Path(directory);run(['/usr/bin/ditto','-x','-k',ZIP,stage]);app=next(stage.glob('*.app'))
        run(['/usr/bin/codesign','--verify','--deep','--strict',app]);resources=app/'Contents/Resources'
        payload=json.loads((resources/'engine-manifest.json').read_text())
        for name,expected in payload['engine_files_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected
        info=plistlib.loads((app/'Contents/Info.plist').read_bytes());binary=app/'Contents/MacOS'/info['CFBundleExecutable']
        env={k:v for k,v in os.environ.items() if not k.startswith(('AE_','PYTHON','VIRTUAL_ENV'))}
        env.update(PATH='/usr/bin:/bin:/usr/sbin:/sbin',PYTHONHOME='/missing-python',PYTHONPATH='/missing-packages')
        policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(ROOT))+'))(deny file-read* (subpath "/opt/homebrew"))(deny file-read* (subpath "/usr/local"))'
        sandbox=['/usr/bin/sandbox-exec','-p',policy]
        cases=[('metal-seed-'+str(seed),'foraging',1200,seed,False,False) for seed in (2801,2802,2803)]
        cases += [('legacy-'+mode,mode,240,2801,False,False) for mode in MODES if mode!='foraging']
        cases += [('physical-'+mode,mode,720,2801,True,False) for mode in ('foraging','predator_prey','continuous')]
        cases += [('compatibility-fallback','foraging',360,2801,False,True)]
        for label,mode,frames,seed,physical,compat in cases:
            data=RunConfig(seed=seed).to_dict();data['mode']=mode
            from engine_bridge import catalog
            data['algorithm']=catalog()['algorithms'][mode][0]
            if mode=='seasons':data['environment']='seasonal';data['food_count']=None
            if mode=='continuous':data=json.loads((V2/'configs/animation_lifecycle.json').read_text())
            config=stage/(label+'-config.json');config.write_text(json.dumps(data))
            profile=stage/(label+'-profile.json');image=stage/(label+'.png');exports=stage/(label+'-exports')
            args=[*sandbox,binary]
            if compat:args+=['--rendering-method','gl_compatibility','--rendering-driver','opengl3']
            args+=['--',f'--frames={frames}',f'--config={config}','--immersive','--ground-view','--quality=1',f'--profile={profile}',f'--screenshot={image}',f'--export={exports}','--no-auto-save']
            if physical:
                options=stage/(label+'-habitat.json');options.write_text(json.dumps({'enabled':True,'weather_period':1.}))
                args.append(f'--habitat-config={options}')
            else:args+=['--visual-hour=11','--visual-cycle=off','--visual-weather=clear']
            log=run(args,cwd=stage,env=env);(OUT/(label+'.log')).write_text(log)
            result=json.loads(profile.read_text());assert result['frames']==frames-90
            assert result['timing_source'].startswith('monotonic wall-clock')
            assert result['animation']['event_gaps']==0
            assert result['renderer']==('gl_compatibility' if compat else 'mobile')
            assert result['animation']['foot_ik']['solves']>0
            bundle=next(exports.glob('run-*'));report=verify_bundle(bundle)
            if physical:
                replay_habitat(report)
                assert report['habitat']['climate']['source']=='Python physical habitat'
                assert any(v['weather_energy']>0 for v in report['habitat']['telemetry'].values())
                if mode=='foraging':
                    assert any(v['water_seconds']>0 for v in report['habitat']['telemetry'].values())
                    assert any(v['blocked']>0 for v in report['habitat']['telemetry'].values())
                    check=run([*sandbox,resources/'python/bin/python3','-E','-s','-B',resources/'engine/v2/backend/habitat.py','--verify-bundle',bundle],cwd=stage,env=env)
                    (OUT/'bundled-habitat-replay.log').write_text(check)
            else:assert replay_run(report).ticks==report['execution']['ticks']
            if mode=='continuous':assert result['animation']['events'].get('birth',0)>0
            shutil.copyfile(bundle/'run.json',OUT/(label+'-run.json'))
            screenshot=screenshots/('habitat-'+label+'.png');shutil.copyfile(image,screenshot)
            late=sum(t>25 for t in result['frame_ms'])/len(result['frame_ms'])
            result.update(case=label,mode=mode,seed=seed,physical_habitat=physical,mean_fps=1000/result['mean_ms'],late_frame_fraction_over_25ms=late,python_ticks=report['execution']['ticks'],replayed_exactly=True,render_pixels=list(struct.unpack('>II',image.read_bytes()[16:24])),screenshot=('screenshots/' if cli.output else '../screenshots/')+screenshot.name)
            result['target_60fps_met']=result['mean_fps']>=59 and result['p95_ms']<=19 and late<.01
            records.append(result);print(label,round(result['mean_fps'],2),'FPS; p95',round(result['p95_ms'],2),'ms;',round(late*100,2),'% late',flush=True)
        run(['/usr/bin/codesign','--verify','--deep','--strict',app])
        assert (registry.read_bytes() if registry.exists() else None)==remembered
        trials=[r for r in records if r['case'].startswith('metal-seed-')]
        report={'ok':True,'archive_sha256':hashlib.sha256(ZIP.read_bytes()).hexdigest(),'platform':platform.platform(),'architecture':platform.machine(),'legacy_sources_unchanged':True,'standalone_checkout_and_homebrew_reads_denied':True,'signature_valid_after_runs':True,'development_settings_unchanged':True,'target':'100 founders, Balanced, 1520x960; 59+ mean FPS, p95 <=19ms, <1% frames over25ms, across three seeds; 90 warmup frames and exports excluded.','repeated_metal_target_met':all(r['target_60fps_met'] for r in trials),'profiles':records,'limitations':'Local Apple M3; no universal FPS guarantee, independent replication, Apple notarization or manual OS input QA. Physical habitat is an explicitly different 2.5D rule extension, not full 3D rigid-body physics.'}
        (OUT/'packaged-habitat.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
