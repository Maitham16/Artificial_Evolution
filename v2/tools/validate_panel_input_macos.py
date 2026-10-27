#!/usr/bin/env python3
"""Test the packaged UI with native Godot input, then smoke-test the release executable."""
from pathlib import Path
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile

V2=Path(__file__).resolve().parents[1]
ROOT=V2.parent
OUT=V2/'docs/panel-input-validation'
ARCHIVE=V2/'build/Artificial Evolution 2.zip'
GODOT=Path(os.environ.get('GODOT_BIN','/Applications/Godot.app/Contents/MacOS/Godot'))


def run(args,**kwargs):
    result=subprocess.run([str(a) for a in args],text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,timeout=150,**kwargs)
    if result.returncode or any(error in result.stdout for error in ('SCRIPT ERROR','\nERROR:','FAIL:','were leaked')):
        raise RuntimeError(result.stdout)
    return result.stdout


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    registry=Path.home()/'Library/Application Support/ArtificialEvolution2/engine.json'
    saved=registry.read_bytes() if registry.exists() else None
    records=[]
    with tempfile.TemporaryDirectory(prefix='ae2-panel-input-',dir='/private/tmp') as directory:
        stage=Path(directory)
        run(['/usr/bin/ditto','-x','-k',ARCHIVE,stage])
        app=next(stage.glob('*.app'));binary=app/'Contents/MacOS/Artificial Evolution 2.0'
        resources=app/'Contents/Resources';pack=resources/'Artificial Evolution 2.0.pck'
        run(['/usr/bin/codesign','--verify','--deep','--strict',app])
        fixture=stage/'panel_input.gd';shutil.copyfile(V2/'tests/panel_input.gd',fixture)
        env={k:v for k,v in os.environ.items() if not k.startswith(('AE_','PYTHON','VIRTUAL_ENV'))}
        env.update(PATH='/usr/bin:/bin:/usr/sbin:/sbin',PYTHONHOME='/missing-python',PYTHONPATH='/missing-packages')
        fixture_env=dict(env,AE_ENGINE_ROOT=str(resources/'engine'),AE_PYTHON=str(resources/'python/bin/python3'))
        policy='(version 1)(allow default)(deny file-read* (subpath '+json.dumps(str(ROOT))+'))(deny file-read* (subpath "/opt/homebrew"))(deny file-read* (subpath "/usr/local"))'
        sandbox=['/usr/bin/sandbox-exec','-p',policy]
        for size in ('1520x960','1160x760'):
            for physical in (False,True):
                label=('physical-' if physical else 'original-')+size
                image=stage/(label+'.png')
                # Release templates do not expose --script. The native editor
                # executable instruments the exact exported UI pack instead.
                args=[*sandbox,GODOT,'--main-pack',pack,'--resolution',size,'--script',fixture,'--',
                      '--no-auto-save',f'--panel-input-screenshot={image}']
                if physical:args.append('--habitat')
                log=run(args,cwd=stage,env=fixture_env)
                (OUT/(label+'.log')).write_text(log)
                marker='AE2_PANEL_INPUT_RESULT '
                result=json.loads(next(line.split(marker,1)[1] for line in log.splitlines() if marker in line))
                assert result==dict(checks=17,failures=0),result
                assert image.is_file() and image.stat().st_size>10000
                target=V2/'docs/screenshots'/('panel-input-'+label+'.png')
                shutil.copyfile(image,target)
                records.append(dict(case=label,**result,screenshot='../screenshots/'+target.name))
                print(label,': 17 routed GUI checks passed',flush=True)
        profile=stage/'release.json';image=stage/'release.png'
        log=run([*sandbox,binary,'--','--frames=180','--no-auto-save','--ecosystem-panel',
                 f'--profile={profile}',f'--screenshot={image}'],cwd=stage,env=env)
        (OUT/'release-smoke.log').write_text(log)
        release=json.loads(profile.read_text())
        assert release['immersive'] and release['animation']['active_models']>0
        assert image.is_file() and image.stat().st_size>10000
        run(['/usr/bin/codesign','--verify','--deep','--strict',app])
        assert (registry.read_bytes() if registry.exists() else None)==saved
    record=dict(ok=True,archive_sha256=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
                fixture_sha256=hashlib.sha256((V2/'tests/panel_input.gd').read_bytes()).hexdigest(),
                platform=platform.platform(),architecture=platform.machine(),cases=records,
                signature_valid_after_runs=True,development_settings_unchanged=True,
                checkout_and_homebrew_reads_denied=True,
                standalone_release_smoke=True,
                method='Fresh signed ZIP. Native Godot editor runs its exported UI pack with an external input fixture and explicit bundled Python paths. Separately, the release executable connects and captures without development overrides. No direct control signal emissions.',
                limitations='GUI event dispatch uses the native editor executable and the exact release UI pack, because release templates lack --script. Not manual macOS hardware input or external script execution in the release executable. Dropdown opening is tested; popup selection remains in the ecosystem functional suite.')
    (OUT/'packaged-panel-input.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__':main()
