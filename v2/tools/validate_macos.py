#!/usr/bin/env python3
"""Extract and run the actual Mac ZIP independently of the Godot project directory."""
from pathlib import Path
import hashlib
import json
import plistlib
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT / 'build/Artificial Evolution 2.zip'
OUT = ROOT / 'build/validation'
OUT.mkdir(parents=True, exist_ok=True)
records = []


def run(args, **kwargs):
    result = subprocess.run([str(a) for a in args], text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=120, **kwargs)
    print(result.stdout, end='', flush=True)
    if result.returncode or 'SCRIPT ERROR' in result.stdout or '\nERROR:' in result.stdout:
        raise RuntimeError(f'Validation command failed ({result.returncode}): {args[0]}')
    return result.stdout


with tempfile.TemporaryDirectory(prefix='ae2-packaged-', dir='/private/tmp') as directory:
    stage = Path(directory)
    run(['/usr/bin/ditto', '-x', '-k', ZIP, stage])
    app = next(stage.glob('*.app'))
    run(['/usr/bin/codesign', '--verify', '--deep', '--strict', app])
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    binary = app / 'Contents/MacOS' / info['CFBundleExecutable']
    architectures = run(['/usr/bin/lipo', '-archs', binary]).strip()
    for environment, image in [('uniform', 'world'), ('hazards', 'hazards')]:
        bundle = OUT / f'native-{environment}-{time.time_ns()}'
        screenshot = ROOT / f'docs/screenshots/{image}.png'
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        log = run([binary, '--', '--frames=180', f'--environment={environment}',
                   f'--screenshot={screenshot}', f'--export={bundle}'], cwd=stage)
        assert screenshot.is_file() and screenshot.stat().st_size > 10000
        assert (bundle / 'application.png').is_file()
        replay = run([ROOT / 'Run Artificial Evolution 2.command', '--headless',
                      '--script', 'tools/headless.gd', '--', f'--replay={bundle}'])
        assert '"ok":true' in replay
        manifest = json.loads((bundle / 'manifest.json').read_text())
        for name, expected in manifest['files_sha256'].items():
            assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == expected
        records.append({'environment': environment, 'screenshot': f'../screenshots/{image}.png',
                        'bundle': str(bundle.relative_to(ROOT)), 'export_files': sorted(manifest['files_sha256']),
                        'replayed_exactly': True})
report = {'ok': True, 'archive': str(ZIP.relative_to(ROOT)),
          'archive_sha256': hashlib.sha256(ZIP.read_bytes()).hexdigest(),
          'signature': 'ad-hoc; codesign --verify --deep --strict passed after fresh extraction',
          'architectures': architectures, 'execution_architecture': 'arm64',
          'native_runs': records,
          'limitations': 'Local packaged-app validation, not independent external reproduction. No manual mouse/keyboard QA: computer control was unavailable. x86_64 was not executed.'}
(ROOT / 'docs/validation/packaged-macos.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
