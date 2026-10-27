#!/usr/bin/env python3
"""Read-only SHA-256 verification of the original repository before v2 existed."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all-existing', action='store_true',
                        help='Also require the pre-existing untracked local experiment/export files.')
    parser.add_argument('--report', type=Path, help='Write a JSON report to a new file under v2/.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    baseline = json.loads((root / 'v2/docs/inspection/baseline.json').read_text())
    inventory = baseline['original_files']
    tracked = baseline['tracked_files']
    names = sorted(inventory if args.all_existing else tracked)
    problems = []
    for name in names:
        path = root / name
        if not path.is_file():
            problems.append({'path': name, 'error': 'missing'})
        elif hashlib.sha256(path.read_bytes()).hexdigest() != inventory[name]['sha256']:
            problems.append({'path': name, 'error': 'changed'})
    new_tracked = subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    outside = [name for name in new_tracked
               if name and name not in tracked and not name.startswith('v2/')]
    report = {'ok': not problems and not outside,
              'baseline_commit': baseline['commit'],
              'scope': 'all pre-existing local files' if args.all_existing else 'original tracked files',
              'files_checked': len(names), 'original_tracked_files': len(tracked),
              'problems': problems, 'new_tracked_files_outside_v2': outside}
    encoded = json.dumps(report, indent=2) + '\n'
    if args.report:
        path = args.report.resolve()
        if not path.is_relative_to(root / 'v2'):
            parser.error('--report must be under v2/')
        if path.exists():
            parser.error('--report must name a new file')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded)
    print(encoded, end='')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
