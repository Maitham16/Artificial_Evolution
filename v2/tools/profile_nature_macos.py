#!/usr/bin/env python3
"""Measure the actual Mac ZIP in two camera views and three scenery profiles."""
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
ARCHIVE = V2 / 'build/Artificial Evolution 2.zip'
OUTPUT = V2 / 'docs/nature-validation'


def run(args, **kwargs):
    process = subprocess.run([str(arg) for arg in args], text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             timeout=120, **kwargs)
    if process.returncode or 'SCRIPT ERROR' in process.stdout or '\nERROR:' in process.stdout:
        raise RuntimeError(process.stdout)
    return process.stdout


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix='ae2-nature-', dir='/private/tmp') as folder:
        stage = Path(folder)
        run(['/usr/bin/ditto', '-x', '-k', ARCHIVE, stage])
        app = next(stage.glob('*.app'))
        run(['/usr/bin/codesign', '--verify', '--deep', '--strict', app])
        info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
        executable = app / 'Contents/MacOS' / info['CFBundleExecutable']
        environment = {**os.environ, 'AE_ENGINE_ROOT': str(ROOT), 'AE_PYTHON': sys.executable}
        for quality in range(3):
            for view in ['valley', 'ground']:
                label = f'{quality}-{view}'
                profile = stage / (label + '.json')
                arguments = [executable, '--', '--frames=480', '--immersive',
                             f'--quality={quality}', f'--{view}-view',
                             f'--profile={profile}', '--no-auto-save']
                if quality == 1:
                    image = 'valley' if view == 'valley' else 'meadow'
                    arguments.append(f'--screenshot={V2 / "docs/screenshots" / (image + ".png")}')
                log = run(arguments, cwd=stage, env=environment)
                (OUTPUT / (label + '.log')).write_text(log)
                record = json.loads(profile.read_text())
                assert record['quality'] == quality and record['frames'] >= 390
                assert record['scenery']['trees'] >= 200
                record.update(view=view, mean_fps=1000 / record['mean_ms'])
                records.append(record)
                print(label, round(record['mean_fps'], 1), 'fps', flush=True)
    result = {'archive': 'build/Artificial Evolution 2.zip',
              'archive_sha256': hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
              'platform': platform.platform(), 'architecture': platform.machine(),
              'window_pixels': [1520, 960],
              'method': 'Six sequential native app runs, 480 displayed frames each, first 90 excluded; live 100-creature Python foraging session; no auto-save. No concurrent benchmark processes.',
              'limitations': 'Local Apple M3 measurements; timings include IPC and UI. No x86_64, manual GUI input or cross-hardware validation.',
              'profiles': records}
    (OUTPUT / 'profiles.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
