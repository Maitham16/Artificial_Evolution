#!/usr/bin/env python3
"""Build a relocatable, checksum-pinned Python payload; never modify the root venv."""
from pathlib import Path
import argparse
from contextlib import contextmanager
import tempfile
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import urllib.request

V2=Path(__file__).resolve().parents[1]
ROOT=V2.parent
CACHE=Path.home()/'Library/Caches/ArtificialEvolution2/desktop-runtime'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def prepare():
    lock=json.loads((V2/'runtime.lock.json').read_text())
    if digest(ROOT/'requirements.txt')!=lock['requirements_sha256']:
        raise RuntimeError('Root dependencies differ from the reviewed runtime lock; update its wheels deliberately.')
    CACHE.mkdir(parents=True,exist_ok=True)
    archive=CACHE/'python.tar.gz'
    if not archive.exists():urllib.request.urlretrieve(lock['python']['url'],archive)
    if digest(archive)!=lock['python']['sha256']:raise RuntimeError('Python archive checksum mismatch')
    # Each assembly gets a pristine interpreter; never reinstall into a synced or shared tree.
    with tempfile.TemporaryDirectory(prefix='assembly-',dir=CACHE) as stage:
        with tarfile.open(archive) as tf:tf.extractall(stage,filter='data')
        python=Path(stage)/'python/bin/python3'
        wheels=CACHE/'wheels';wheels.mkdir(exist_ok=True)
        environment={**os.environ,'PYTHONNOUSERSITE':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1','PYGAME_HIDE_SUPPORT_PROMPT':'1'}
        missing=[name for name in lock['wheels'] if not (wheels/name).exists()]
        if missing:
            subprocess.run([python,'-I','-m','pip','--isolated','download','--only-binary=:all:','--dest',wheels,'-r',ROOT/'requirements.txt'],check=True,env=environment)
        for name,expected in lock['wheels'].items():
            if digest(wheels/name)!=expected:raise RuntimeError('Dependency wheel checksum mismatch: '+name)
        unexpected={p.name for p in wheels.glob("*.whl")}-set(lock["wheels"])
        if unexpected:raise RuntimeError("Unreviewed wheels in private cache: "+", ".join(sorted(unexpected)))
        # A private cache only. All accepted wheel bytes were checked above.
        subprocess.run([python,'-I','-m','pip','--isolated','install','--no-deps','--no-compile','--no-index','--find-links',wheels,'-r',ROOT/'requirements.txt'],check=True,env=environment)
        subprocess.run([python,'-E','-s','-B','-c','import numpy, pygame, matplotlib; print("Bundled dependencies import successfully")'],check=True,env=environment)
        yield Path(stage)/'python'


def bundle(app):
    resources=app/'Contents/Resources';destination=resources/'python'
    with prepare() as runtime:
        if destination.exists():shutil.rmtree(destination)
        shutil.copytree(runtime,destination,symlinks=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store'))
    shutil.copyfile(V2/'backend/runtime_sitecustomize.py',destination/'lib/python3.13/site-packages/sitecustomize.py')
    engine=resources/'engine';engine.mkdir(exist_ok=True)
    # Include every original Python source byte, including tests: exports record this full source set.
    paths=[*sorted(ROOT.glob('*.py')),ROOT/'LICENSE',ROOT/'requirements.txt',*sorted((ROOT/'configs').glob('*.json')),
           V2/'backend/engine_bridge.py',V2/'backend/runtime_sitecustomize.py',V2/'backend/habitat.py']
    files={}
    for source in paths:
        relative=source.relative_to(ROOT);target=engine/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target);files[str(relative)]=digest(target)
    payload={'python':json.loads((V2/'runtime.lock.json').read_text()),'engine_files_sha256':files,
             'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
             'architecture':'arm64','original_engine_unmodified':True}
    (resources/'engine-manifest.json').write_text(json.dumps(payload,indent=2)+'\n')
    shutil.copyfile(V2/'runtime.lock.json',resources/'runtime.lock.json')
    # Keep CPython/third-party license texts and wheel dist-info licenses in the runtime.
    shutil.copyfile(ROOT/'LICENSE',resources/'LICENSE')
    license_dir=resources/'python/licenses';license_dir.mkdir(exist_ok=True)
    for name,expected in payload['python']['license_files'].items():
        license_file=V2/'assets/runtime-licenses'/name
        if digest(license_file)!=expected:raise RuntimeError('Runtime license checksum mismatch: '+name)
        shutil.copyfile(license_file,license_dir/name)
    # Every nested Mach-O must be signed before the outer bundle; do not rely only on --deep.
    macho=[]
    for path in destination.rglob('*'):
        if path.is_symlink() or not path.is_file():continue
        with path.open('rb') as f:magic=f.read(4)
        if magic in (b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca'):macho.append(path)
    for path in macho:subprocess.run(['/usr/bin/codesign','--force','--sign','-',str(path)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print('Bundled original engine files:',len(files),'· signed runtime binaries:',len(macho))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--app',type=Path)
    args=parser.parse_args()
    if args.app:bundle(args.app)
    else:
        with prepare() as runtime:print("Verified fresh runtime assembly:",runtime)
