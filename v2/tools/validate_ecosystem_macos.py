#!/usr/bin/env python3
"""Render the actual signed ZIP in distinct ecosystem states; replay real exports."""
from pathlib import Path
import hashlib
import json
import os
import platform
import plistlib
import struct
import subprocess
import sys
import tempfile

V2=Path(__file__).resolve().parents[1]
ROOT=V2.parent
OUTPUT=V2/'docs/ecosystem-validation'
ARCHIVE=V2/'build/Artificial Evolution 2.zip'
sys.path.insert(0,str(ROOT))
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
from research_session import verify_bundle,replay_run


def run(arguments,**kwargs):
    result=subprocess.run([str(a) for a in arguments],text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,timeout=120,**kwargs)
    if result.returncode or 'SCRIPT ERROR' in result.stdout or '\nERROR:' in result.stdout:
        raise RuntimeError(result.stdout)
    return result.stdout


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    cases=[('meadow-day','foraging','clear','auto',11,False),
           ('autumn-rain','foraging','rain','autumn',16,True),
           ('predators-night','predator_prey','clear','auto',22,True),
           ('winter-snow','foraging','snow','winter',12,False),
           ('python-spring','seasons','fog','auto',8,True),
           ('continuous-births','continuous','clear','auto',11,True)]
    records=[]
    with tempfile.TemporaryDirectory(prefix='ae2-ecosystem-',dir='/private/tmp') as directory:
        stage=Path(directory)
        run(['/usr/bin/ditto','-x','-k',ARCHIVE,stage])
        app=next(stage.glob('*.app'));run(['/usr/bin/codesign','--verify','--deep','--strict',app])
        info=plistlib.loads((app/'Contents/Info.plist').read_bytes());binary=app/'Contents/MacOS'/info['CFBundleExecutable']
        env={**os.environ,'AE_ENGINE_ROOT':str(ROOT),'AE_PYTHON':sys.executable}
        for label,mode,weather,season,hour,panel in cases:
            profile=stage/(label+'.json');destination=stage/(label+'-exports')
            screenshot=V2/'docs/screenshots'/('ecosystem-'+label+'.png')
            args=[binary,'--','--frames=480','--immersive','--ground-view','--quality=1',f'--mode={mode}',
                  f'--visual-weather={weather}',f'--visual-season={season}',f'--visual-hour={hour}',
                  '--visual-cycle=off',f'--profile={profile}',f'--screenshot={screenshot}',f'--export={destination}','--no-auto-save']
            if panel:args.append('--ecosystem-panel')
            if mode=='continuous':args.append(f'--config={V2/"configs/animation_lifecycle.json"}')
            log=run(args,cwd=stage,env=env);(OUTPUT/(label+'.log')).write_text(log)
            assert 'AE2_PYTHON_EXPORT' in log and 'AE2_PYTHON_VIEW' in log
            result=json.loads(profile.read_text());eco=result['ecosystem'];scenery=eco['scenery']
            assert result['frames']>=390 and result['animation']['event_gaps']==0
            assert scenery['weather']==weather and abs(scenery['hour']-hour)<.01
            assert scenery['weather_source']==scenery['daylight_source']=='decorative'
            assert scenery['season_source']==('Python' if mode=='seasons' else 'decorative')
            assert eco['bounded_event_effects']<=20
            assert eco['python_food_plants']==scenery['source_context']['actual_food']
            if mode=='continuous':
                assert result['animation']['events'].get('birth',0)>0
                assert result['animation']['events'].get('reproduce',0)>0
                assert 'Growing' in result['animation']['observed_visual_states']
            if mode=='predator_prey':
                assert result['animation']['events'].get('capture',0)>0
                assert result['animation']['events'].get('death',0)>0
            bundles=list(destination.glob('run-*'));assert len(bundles)==1
            report=verify_bundle(bundles[0]);replay=replay_run(report)
            assert replay.ticks==report['execution']['ticks']
            # Retain authoritative source evidence, not absolute temporary paths.
            for name in ('run.json','config.json','manifest.json'):
                (OUTPUT/(label+'-'+name)).write_bytes((bundles[0]/name).read_bytes())
            result.update(case=label,mode=mode,mean_fps=1000/result['mean_ms'],
                          render_pixels=list(struct.unpack('>II',screenshot.read_bytes()[16:24])),
                          screenshot='../screenshots/'+screenshot.name,python_ticks=report['execution']['ticks'],
                          verified_original_bundle=True,replayed_exactly_with_original_engine=True)
            records.append(result);print(label,round(result['mean_fps'],1),'fps',flush=True)
    report={'ok':True,'archive_sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
            'platform':platform.platform(),'architecture':platform.machine(),
            'method':'Six sequential native signed-ZIP runs, Balanced, 480 frames, first 90 excluded; fresh extraction outside the checkout. Each Python export manifest verified and replayed exactly by the original engine.',
            'profiles':records,'limitations':'Local Apple M3 execution, no independent replication, manual OS input QA, x86_64 execution or Apple notarization. Weather, lighting and seasonal color overrides are decorative. No forced feeding, capture, birth or death in these native runs.'}
    (OUTPUT/'packaged-ecosystem.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
