#!/usr/bin/env python3
"""Run the actual Mac ZIP against the original Python engine in all seven modes."""
from pathlib import Path
import hashlib
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import time

V2=Path(__file__).resolve().parents[1]
ROOT=V2.parent
sys.path.insert(0,str(ROOT))
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
from research_session import MODES,verify_bundle,replay_run
ZIP=V2/'build/Artificial Evolution 2.zip'
OUT=V2/'build/bridge-validation'
OUT.mkdir(parents=True,exist_ok=True)
records=[]


def run(args,**kwargs):
    result=subprocess.run([str(a) for a in args],text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,timeout=120,**kwargs)
    print(result.stdout,end='',flush=True)
    if result.returncode or 'SCRIPT ERROR' in result.stdout or '\nERROR:' in result.stdout:
        raise RuntimeError(f'Validation command failed ({result.returncode}): {args[0]}')
    return result.stdout


with tempfile.TemporaryDirectory(prefix='ae2-python-package-',dir='/private/tmp') as directory:
    stage=Path(directory)
    run(['/usr/bin/ditto','-x','-k',ZIP,stage])
    app=next(stage.glob('*.app'))
    run(['/usr/bin/codesign','--verify','--deep','--strict',app])
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    binary=app/'Contents/MacOS'/info['CFBundleExecutable']
    architectures=run(['/usr/bin/lipo','-archs',binary]).strip()
    for mode in MODES:
        destination=OUT/f'{mode}-{time.time_ns()}'
        image='world' if mode=='foraging' else 'hazards' if mode=='obstacles' else mode
        screenshot=V2/f'docs/screenshots/{image}.png'
        environment={**os.environ,'AE_ENGINE_ROOT':str(ROOT),'AE_PYTHON':sys.executable}
        log=run([binary,'--','--frames=180',f'--mode={mode}',
                 f'--screenshot={screenshot}',f'--export={destination}'],cwd=stage,env=environment)
        assert 'AE2_PYTHON_VIEW' in log and 'AE2_PYTHON_EXPORT' in log
        bundles=list(destination.glob('run-*'));assert len(bundles)==1
        bundle=bundles[0]
        assert screenshot.stat().st_size>10000
        assert (bundle/'application.png').exists()
        report=verify_bundle(bundle)
        assert report['config']['mode']==mode
        assert report['execution']['ticks']>=30
        replay=replay_run(report)
        assert replay.ticks==report['execution']['ticks']
        for name,expected in json.loads((bundle/'manifest.json').read_text())['files_sha256'].items():
            assert hashlib.sha256((bundle/name).read_bytes()).hexdigest()==expected
        # Test the user's original CLI contract as well as the direct engine API.
        if mode=='foraging':
            run([sys.executable,ROOT/'simulator.py','--verify-bundle',bundle],cwd=stage)
            run([sys.executable,ROOT/'simulator.py','--replay',bundle/'run.json','--headless'],cwd=stage)
        records.append({'mode':mode,'screenshot':f'../screenshots/{image}.png',
                        'bundle':str(bundle.relative_to(V2)),
                        'ticks':report['execution']['ticks'],'births':report['metrics']['births'],
                        'replayed_exactly_with_original_engine':True,'python_engine_version':report['app_version']})
report={'ok':True,'archive':str(ZIP.relative_to(V2)),
        'archive_sha256':hashlib.sha256(ZIP.read_bytes()).hexdigest(),
        'signature':'ad-hoc; fresh extraction passed codesign --verify --deep --strict',
        'architectures':architectures,'executed_architecture':'arm64',
        'native_runs':records,
        'limitations':'Local packaged-app validation; no manual mouse/keyboard QA. x86_64 and Apple notarization were not tested.'}
(V2/'docs/bridge-validation/packaged-macos.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
