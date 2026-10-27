#!/usr/bin/env python3
"""Measure and capture the signed Mac package with the new animal models."""
from pathlib import Path
import hashlib
import json
import os
import platform
import plistlib
import subprocess
import sys
import tempfile

V2 = Path(__file__).resolve().parents[1]
ROOT = V2.parent
ARCHIVE = V2/'build/Artificial Evolution 2.zip'
OUTPUT = V2/'docs/animal-validation'


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
                           ('predator_prey', 'ground'), ('traits', 'ground')]:
            label = mode+'-'+view
            profile = stage/(label+'.json')
            image = {'foraging-ground':'meadow', 'foraging-valley':'valley',
                     'predator_prey-ground':'animal-predators', 'traits-ground':'animal-traits'}[label]
            log = run([binary, '--', '--frames=480', '--immersive', f'--{view}-view',
                       '--quality=1', f'--mode={mode}', f'--profile={profile}',
                       f'--screenshot={V2/"docs/screenshots"/(image+".png")}', '--no-auto-save'],
                      cwd=stage, env=environment)
            assert 'AE2_PYTHON_VIEW' in log
            (OUTPUT/(label+'.log')).write_text(log)
            result = json.loads(profile.read_text())
            assert result['frames'] >= 390
            result.update(mode=mode, view=view, mean_fps=1000/result['mean_ms'])
            records.append(result)
            print(label, round(result['mean_fps'], 1), 'fps', flush=True)
    report = {'ok': True, 'archive_sha256': hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
              'platform': platform.platform(), 'architecture': platform.machine(),
              'window_pixels': [1520, 960],
              'method': 'Four sequential signed-package runs at Balanced quality, 480 frames each, first 90 excluded; live Python simulation. Fresh extraction outside the checkout.',
              'animation': 'Shared floating-point vertex pose textures baked from Blender rigs; no runtime CPU skinning.',
              'profiles': records,
              'limitations': 'Local Apple M3 tests; no manual OS mouse/keyboard QA, x86_64 execution, or Apple notarization. Anatomy, coat morphs and gait are presentation only.'}
    (OUTPUT/'packaged-animals.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
