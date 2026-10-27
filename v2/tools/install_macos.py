#!/usr/bin/env python3
"""Install the signed, self-contained 3D app without changing the original simulator."""
from pathlib import Path
import argparse
import hashlib
import json
import plistlib
import shutil
import subprocess
import tempfile

V2=Path(__file__).resolve().parents[1]


def validate_app(app):
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    if info.get('CFBundleIdentifier')!='org.maitham.artificialevolution2':
        raise ValueError('Unexpected application bundle identifier')
    subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True)
    resources=app/'Contents/Resources'
    if not (resources/'python/bin/python3').is_file():raise ValueError('Standalone Python runtime is missing')
    manifest=json.loads((resources/'engine-manifest.json').read_text())
    for name,expected in manifest['engine_files_sha256'].items():
        path=resources/'engine'/name
        if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Invalid engine manifest path')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Engine checksum mismatch: '+name)


def install(archive,destination):
    sidecar=archive.parent/'desktop-manifest.json'
    if sidecar.is_file():
        expected=json.loads(sidecar.read_text())['archive_sha256']
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:raise ValueError('Desktop ZIP checksum mismatch')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ae2-install-',dir='/private/tmp') as folder:
        stage=Path(folder)
        subprocess.run(['/usr/bin/ditto','-x','-k',str(archive),str(stage)],check=True)
        apps=list(stage.glob('*.app'))
        if len(apps)!=1:raise ValueError('Expected one application in the archive')
        validate_app(apps[0])
        backup=stage/'previous.app'
        if destination.exists():
            info=plistlib.loads((destination/'Contents/Info.plist').read_bytes())
            if info.get('CFBundleIdentifier')!='org.maitham.artificialevolution2':raise ValueError('Destination contains another application')
            shutil.move(destination,backup)
        try:
            subprocess.run(['/usr/bin/ditto',str(apps[0]),str(destination)],check=True)
            validate_app(destination)
        except BaseException:
            if destination.exists():shutil.rmtree(destination)
            if backup.exists():shutil.move(backup,destination)
            raise
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=V2/'build/Artificial Evolution 2.zip')
    parser.add_argument('--destination',type=Path,default=Path.home()/'Applications/Artificial Evolution 2.0.app')
    args=parser.parse_args()
    if not args.archive.is_file():parser.error('Build the desktop ZIP first: ./v2/tools/build_macos.sh')
    print('Installed:',install(args.archive.resolve(),args.destination.expanduser().absolute()))
    print('Double-click the app in Finder. Python, Godot and Blender are not required to run it.')
