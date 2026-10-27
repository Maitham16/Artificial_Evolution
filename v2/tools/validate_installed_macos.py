#!/usr/bin/env python3
"""Exercise the real one-click launcher and verify the installed app stays signed."""
from pathlib import Path
import json
import subprocess
import tempfile
import time

V2=Path(__file__).resolve().parents[1]
APP=Path.home()/'Applications/Artificial Evolution 2.0.app'


def main():
    if not APP.is_dir():raise RuntimeError('Install the checked desktop ZIP first.')
    with tempfile.TemporaryDirectory(prefix='ae2-launchservices-',dir='/private/tmp') as folder:
        folder=Path(folder);profile=folder/'profile.json';image=folder/'application.png'
        subprocess.run([str(V2/'Launch 3D Application.command'),'--frames=180','--no-auto-save',
                        f'--profile={profile}',f'--screenshot={image}'],check=True)
        deadline=time.monotonic()+60
        while not profile.exists() and time.monotonic()<deadline:time.sleep(.2)
        if not profile.exists():raise RuntimeError('LaunchServices did not produce the bounded validation profile.')
        result=json.loads(profile.read_text())
        assert result['immersive'] and result['animation']['active_models']>0
        assert image.is_file() and image.stat().st_size>10000
        time.sleep(2)  # Allow the acknowledged backend shutdown to finish.
        subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(APP)],check=True)
        output=V2/'docs/desktop-validation';output.mkdir(parents=True,exist_ok=True)
        record={'ok':True,'launcher':'v2/Launch 3D Application.command via macOS LaunchServices',
                'application':str(APP),'bundled_engine_connected':True,
                'signature_valid_after_launch':True,'manual_os_input_tested':False,'profile':result}
        (output/'installed-launch.json').write_text(json.dumps(record,indent=2)+'\n')
        print('One-click launch passed; bundled engine connected and installed signature remains valid.')


if __name__=='__main__':main()
