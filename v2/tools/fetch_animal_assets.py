#!/usr/bin/env python3
"""Fetch pinned CC0 animal authoring files or verify the committed derived assets."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def matches(path, record):
    return (path.is_file() and path.stat().st_size == record['bytes']
            and hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-runtime', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT/'v2/assets/animals/ASSET_SOURCES.json').read_text())
    if args.verify_runtime:
        records = manifest['runtime_files'] + manifest['editable_files']
        bad = [r['path'] for r in records if not matches(ROOT/r['path'], r)]
        if bad: raise SystemExit('Asset checksum mismatch: ' + ', '.join(bad))
        for path in (ROOT/'v2/assets/animals').rglob('*.exr.import'):
            settings = path.read_text()
            assert 'compress/mode=0' in settings and 'mipmaps/generate=false' in settings, path
            assert 'detect_3d/compress_to=0' in settings, path
        for path in (ROOT/'v2/assets/animals').rglob('*.gltf.import'):
            settings = path.read_text()
            assert 'meshes/generate_lods=false' in settings and 'meshes/create_shadow_meshes=false' in settings, path
        print(f'Verified {len(records)} runtime and editable animal files, plus GPU data import settings.')
        return
    for asset in manifest['assets']:
        path = ROOT/asset['path']
        if not matches(path, asset):
            path.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(asset['url'], headers={'User-Agent': 'ArtificialEvolution/2.0'})
            temporary = path.with_name(path.name+'.part')
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    temporary.write_bytes(response.read())
                if not matches(temporary, asset): raise ValueError('Source checksum mismatch: '+asset['id'])
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        if asset['id'] == 'wolf':
            destination = ROOT/'.cache/animals/wolf-source'
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    target = (destination/member.filename).resolve()
                    if not target.is_relative_to(destination.resolve()) or stat.S_ISLNK(member.external_attr >> 16):
                        raise ValueError('Unsafe authoring archive member')
                archive.extractall(destination)
    print('Verified three pinned CC0 animal sources.')


if __name__ == '__main__':
    main()
