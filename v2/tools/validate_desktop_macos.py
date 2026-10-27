#!/usr/bin/env python3
"""Validate the signed standalone ZIP with checkout and Homebrew reads denied."""
from pathlib import Path
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
OUTPUT=V2/'docs/desktop-validation';ARCHIVE=V2/'build/Artificial Evolution 2.zip'
sys.path.insert(0,str(ROOT))
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy');os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
from research_session import MODES,verify_bundle,replay_run


def run(args,**kwargs):
    result=subprocess.run([str(a) for a in args],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=150,**kwargs)
    if result.returncode or 'SCRIPT ERROR' in result.stdout or '\nERROR:' in result.stdout:raise RuntimeError(result.stdout)
    return result.stdout


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True);records=[]
    registry=Path.home()/'Library/Application Support/ArtificialEvolution2/engine.json'
    saved_registry=registry.read_bytes() if registry.exists() else None
    with tempfile.TemporaryDirectory(prefix='ae2-desktop-',dir='/private/tmp') as folder:
        stage=Path(folder);run(['/usr/bin/ditto','-x','-k',ARCHIVE,stage]);app=next(stage.glob('*.app'))
        run(['/usr/bin/codesign','--verify','--deep','--strict',app])
        resources=app/'Contents/Resources';info=plistlib.loads((app/'Contents/Info.plist').read_bytes());binary=app/'Contents/MacOS'/info['CFBundleExecutable']
        payload=json.loads((resources/'engine-manifest.json').read_text())
        for name,expected in payload['engine_files_sha256'].items():
            assert hashlib.sha256((resources/'engine'/name).read_bytes()).hexdigest()==expected
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected
        environment={k:v for k,v in os.environ.items() if not k.startswith(('AE_','PYTHON','VIRTUAL_ENV'))}
        environment.update(PATH='/usr/bin:/bin:/usr/sbin:/sbin',PYTHONHOME='/missing-runtime',PYTHONPATH='/missing-packages')
        # The native process and its Python child cannot read this checkout or Homebrew.
        policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(ROOT))+'))(deny file-read* (subpath "/opt/homebrew"))(deny file-read* (subpath "/usr/local"))'
        sandbox=['/usr/bin/sandbox-exec','-p',policy]
        cases=[(mode,1,480 if mode in ('foraging','continuous') else 240,False) for mode in MODES]
        cases += [('foraging',0,480,False),('foraging',1,240,True)]
        for mode,quality,frames,small in cases:
            label=mode+('-performance' if quality==0 else '-small' if small else '')
            profile=stage/(label+'.json');image=stage/(label+'.png');destination=stage/(label+'-exports')
            args=[*sandbox,binary]
            if small:args+=['--resolution','1160x760']
            args+=['--',f'--frames={frames}',f'--mode={mode}',f'--quality={quality}',f'--profile={profile}',f'--screenshot={image}',f'--export={destination}','--visual-weather=clear','--visual-hour=11','--visual-cycle=off','--no-auto-save']
            if mode=='continuous':
                demo=stage/'lifecycle.json';shutil.copyfile(V2/'configs/animation_lifecycle.json',demo);args.append(f'--config={demo}')
            log=run(args,cwd=stage,env=environment);(OUTPUT/(label+'.log')).write_text(log)
            assert 'AE2_PYTHON_EXPORT' in log and 'AE2_PYTHON_VIEW' in log
            data=json.loads(profile.read_text());assert data['immersive'];assert data['animation']['event_gaps']==0
            bundles=list(destination.glob('run-*'));assert len(bundles)==1
            report=verify_bundle(bundles[0]);assert replay_run(report).ticks==report['execution']['ticks']
            target=OUTPUT/(label+'-run.json');shutil.copyfile(bundles[0]/'run.json',target)
            screenshot=V2/'docs/screenshots'/('desktop-'+label+'.png');shutil.copyfile(image,screenshot)
            data.update(case=label,mode=mode,mean_fps=1000/data['mean_ms'],render_pixels=list(struct.unpack('>II',image.read_bytes()[16:24])),python_ticks=report['execution']['ticks'],verified_and_replayed_exactly=True,checkout_and_homebrew_reads_denied=True,screenshot='../screenshots/'+screenshot.name)
            if mode=='continuous':assert data['animation']['events'].get('birth',0)>0
            records.append(data);print(label,round(data['mean_fps'],1),'FPS',flush=True)
        # The same unchanged 2D entry point works as an independent process using bundled Python.
        two_d=run([*sandbox,resources/'python/bin/python3','-E','-s','-B',resources/'engine/simulator.py','--headless','--config',resources/'engine/configs/foraging.json','--ticks','60','--export-root',stage/'original-2d'],cwd=stage,env=environment)
        (OUTPUT/'original-2d.log').write_text(two_d)
        bundle=next((stage/'original-2d').glob('run-*'));original=verify_bundle(bundle)
        assert replay_run(original).ticks==60
        # No accidental cache/bytecode writes invalidated the signed app.
        run(['/usr/bin/codesign','--verify','--deep','--strict',app])
        assert (registry.read_bytes() if registry.exists() else None)==saved_registry
        report={'ok':True,'archive_sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),'architecture':platform.machine(),'platform':platform.platform(),'self_contained':True,'engine_sources_verified':len(payload['engine_files_sha256']),'development_registry_unchanged':True,'original_2d_independent_replay':True,'signature_valid_after_launches':True,'profiles':records,'method':'Fresh signed ZIP extraction; nine sequential native runs, checkout + /opt/homebrew + /usr/local reads denied by macOS sandbox-exec. No AE path overrides, system-only PATH, invalid PYTHONHOME/PYTHONPATH (ignored by owned interpreter). Each original export verified and replayed exactly. First 90 displayed frames excluded from timing.','limitations':'Local Apple M3 checks; not independent replication, Intel execution, Apple notarization or manual operating-system mouse/keyboard QA.'}
        (OUTPUT/'packaged-desktop.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
