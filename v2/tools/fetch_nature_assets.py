#!/usr/bin/env python3
"""Fetch pinned CC0 authoring sources, or verify the committed runtime assets."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'v2/assets/nature/ASSET_SOURCES.json'


def matches(path, record):
    return (path.is_file() and path.stat().st_size == record['bytes']
            and hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'])


def fetch(record):
    path = ROOT / record['path']
    if matches(path, record):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(record['url'], headers={'User-Agent': 'ArtificialEvolution/2.0'})
    temporary = path.with_name(path.name + '.part')
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            temporary.write_bytes(response.read())
        if not matches(temporary, record):
            raise ValueError('Source checksum mismatch: ' + record['path'])
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-runtime', action='store_true',
                        help='Check installed art without fetching authoring sources.')
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    if args.verify_runtime:
        records = manifest['runtime_files']
        bad = [item['path'] for item in records if not matches(ROOT / item['path'], item)]
        if bad:
            raise SystemExit('Changed or missing assets: ' + ', '.join(bad))
        print(f'Verified {len(records)} committed runtime assets.')
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(fetch, manifest['source_downloads']))
        print(f'Verified {len(manifest["source_downloads"])} pinned source downloads.')


if __name__ == '__main__':
    main()
