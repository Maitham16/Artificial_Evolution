#!/bin/bash
set -euo pipefail
AE_V2_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$(uname -s)" != Darwin ]]; then echo "This setup script is for macOS."; exit 1; fi
if [[ ! -x /Applications/Godot.app/Contents/MacOS/Godot ]] || [[ ! -x /Applications/Blender.app/Contents/MacOS/Blender ]]; then
  if ! command -v brew >/dev/null 2>&1; then echo "Install Homebrew from https://brew.sh, then run this script again."; exit 1; fi
  brew install --cask godot blender
fi
AE_GODOT="${GODOT_BIN:-/Applications/Godot.app/Contents/MacOS/Godot}"
AE_BLENDER="${BLENDER_BIN:-/Applications/Blender.app/Contents/MacOS/Blender}"
AE_PYTHON="$(command -v python3.13 || command -v python3)"
"$AE_PYTHON" - "$AE_V2_ROOT" "$AE_GODOT" "$AE_BLENDER" <<'PY'
import json,pathlib,subprocess,sys,hashlib,urllib.request,zipfile
root=pathlib.Path(sys.argv[1]);lock=json.loads((root/'toolchain.lock.json').read_text())
godot=pathlib.Path(sys.argv[2]);blender=pathlib.Path(sys.argv[3])
version=subprocess.check_output([str(godot),'--version'],text=True).strip()
if not version.startswith(lock['godot']['version']+'.'):
 print('Installing the pinned Godot locally in v2/.tools; the installed app is preserved.')
 tools=root/'.tools';tools.mkdir(exist_ok=True)
 archive=tools/'godot.zip';urllib.request.urlretrieve(lock['godot']['url'],archive)
 assert hashlib.sha256(archive.read_bytes()).hexdigest()==lock['godot']['sha256'],'Godot checksum mismatch'
 with zipfile.ZipFile(archive) as z:
  assert all(not pathlib.Path(n).is_absolute() and '..' not in pathlib.Path(n).parts for n in z.namelist())
  z.extractall(tools)
 godot=tools/'Godot.app/Contents/MacOS/Godot';godot.chmod(0o755)
 version=subprocess.check_output([str(godot),'--version'],text=True).strip()
assert version.startswith('4.'),'Use Godot 4'
blender_version=subprocess.check_output([str(blender),'--version'],text=True).splitlines()[0]
print('Godot:',version);print('Blender:',blender_version)
(root/'.tools').mkdir(exist_ok=True)
(root/'.tools/installation.json').write_text(json.dumps({'godot':str(godot),'godot_version':version,'blender':str(blender),'blender_version':blender_version},indent=2)+'\n')
PY
"$AE_PYTHON" "$AE_V2_ROOT/tools/install_templates.py"
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --editor --import
"$AE_V2_ROOT/tools/test.sh"
echo "Ready. Double-click v2/Run Artificial Evolution 2.command to run."
