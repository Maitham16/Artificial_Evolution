#!/usr/bin/env python3
"""Measure and capture the signed Mac package with the event-driven skeletal animations."""
from pathlib import Path
import hashlib
import json
import os
import platform
import plistlib
import subprocess
import struct
import sys
import tempfile

V2 = Path(__file__).resolve().parents[1]
ROOT = V2.parent
ARCHIVE = V2/'build/Artificial Evolution 2.zip'
OUTPUT = V2/'docs/animation-validation'


def run(arguments, **kwargs):
    result = subprocess.run([str(a) for a in arguments], text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=120, **kwargs)
    if result.returncode or 'SCRIPT ERROR' in result.stdout or '\nERROR:' in result.stdout:
        raise RuntimeError(result.stdout)
    return result.stdout


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix='ae2-animals-', dir='/private/tmp') as directory:
        stage = Path(directory)
        run(['/usr/bin/ditto', '-x', '-k', ARCHIVE, stage])
        app = next(stage.glob('*.app'))
        run(['/usr/bin/codesign', '--verify', '--deep', '--strict', app])
        info = plistlib.loads((app/'Contents/Info.plist').read_bytes())
        binary = app/'Contents/MacOS'/info['CFBundleExecutable']
        environment = {**os.environ, 'AE_ENGINE_ROOT': str(ROOT), 'AE_PYTHON': sys.executable}
        for mode, view in [('foraging', 'ground'), ('foraging', 'valley'),
                           ('predator_prey', 'ground'), ('traits', 'ground'), ('continuous', 'ground')]:
            label = mode+'-'+view
            profile = stage/(label+'.json')
            image = {'foraging-ground':'meadow', 'foraging-valley':'valley',
                     'predator_prey-ground':'animation-predators', 'traits-ground':'animation-traits', 'continuous-ground':'animation-continuous'}[label]
            args = [binary, '--', '--frames=480', '--immersive', f'--{view}-view',
                       '--quality=1', f'--mode={mode}', f'--profile={profile}',
                       f'--screenshot={V2/"docs/screenshots"/(image+".png")}', '--no-auto-save']
            if mode == 'continuous': args.append(f'--config={V2/"configs/animation_lifecycle.json"}')
            log = run(args, cwd=stage, env=environment)
            assert 'AE2_PYTHON_VIEW' in log
            (OUTPUT/(label+'.log')).write_text(log)
            result = json.loads(profile.read_text())
            assert result['frames'] >= 390
            assert result['animation']['event_gaps'] == 0
            assert result['animation']['gpu_bone_models'] > 0
            if mode == 'continuous':
                assert result['animation']['events'].get('birth', 0) > 0
                assert result['animation']['events'].get('reproduce', 0) > 0
                assert 'Growing' in result['animation']['observed_visual_states']
            result.update(mode=mode, view=view, mean_fps=1000/result['mean_ms'], render_pixels=list(struct.unpack('>II',(V2/'docs/screenshots'/(image+'.png')).read_bytes()[16:24])))
            records.append(result)
            print(label, round(result['mean_fps'], 1), 'fps', flush=True)
    report = {'ok': True, 'archive_sha256': hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
              'platform': platform.platform(), 'architecture': platform.machine(),
              'nominal_window_pixels': [1520, 960],
              'method': 'Five sequential signed-package runs at Balanced quality, 480 frames each, first 90 excluded; live Python simulation. Fresh extraction outside the checkout.',
              'animation': 'Actual Skeleton3D near the camera and shared GPU bone matrices farther away, with event-driven blended states.',
              'profiles': records,
              'limitations': 'Local Apple M3 tests; no manual OS mouse/keyboard QA, x86_64 execution, or Apple notarization. Anatomy, coat morphs and gait are presentation only.'}
    (OUTPUT/'packaged-animation.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
