#!/bin/bash
set -euo pipefail
AE_V2_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# iCloud/Desktop file providers can recreate FinderInfo on .app bundles.
# Export, sign and archive outside those managed directories.
AE_STAGE="$(mktemp -d /private/tmp/artificial-evolution-build.XXXXXX)"
trap 'rm -rf "$AE_STAGE"' EXIT
mkdir -p "$AE_V2_ROOT/build"
touch "$AE_V2_ROOT/build/.gdignore"
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --editor --import
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --export-release macOS "$AE_STAGE/Artificial Evolution 2.zip"
/usr/bin/ditto -x -k "$AE_STAGE/Artificial Evolution 2.zip" "$AE_STAGE"
AE_APP="$(find "$AE_STAGE" -maxdepth 1 -name '*.app' -print -quit)"
if [[ -z "$AE_APP" ]]; then echo "Export produced no .app"; exit 1; fi
"${AE_PYTHON:-$AE_V2_ROOT/../.venv/bin/python}" "$AE_V2_ROOT/tools/prepare_desktop_runtime.py" --app "$AE_APP"
# These attributes belong only to this freshly generated application.
/usr/bin/xattr -dr com.apple.FinderInfo "$AE_APP" 2>/dev/null || true
/usr/bin/xattr -dr com.apple.ResourceFork "$AE_APP" 2>/dev/null || true
python3 - "$AE_APP" <<'PYPLIST'
from pathlib import Path
import plistlib,sys
path=Path(sys.argv[1])/'Contents/Info.plist'
info=plistlib.loads(path.read_bytes())
info['NSDesktopFolderUsageDescription']='Optional: connect to a development Python checkout or import/export files on Desktop. The bundled engine runs without Desktop access.'
path.write_bytes(plistlib.dumps(info))
PYPLIST
/usr/bin/codesign --force --deep --sign - "$AE_APP"
/usr/bin/codesign --verify --deep --strict "$AE_APP"
rm "$AE_STAGE/Artificial Evolution 2.zip"
/usr/bin/ditto -c -k --keepParent "$AE_APP" "$AE_STAGE/Artificial Evolution 2.zip"
cp "$AE_STAGE/Artificial Evolution 2.zip" "$AE_V2_ROOT/build/Artificial Evolution 2.zip"
python3 - "$AE_V2_ROOT" <<'PYMANIFEST'
from pathlib import Path
import hashlib,json,sys
v2=Path(sys.argv[1]);archive=v2/'build/Artificial Evolution 2.zip'
data={'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'architecture':'arm64','self_contained':True,'runtime_lock_sha256':hashlib.sha256((v2/'runtime.lock.json').read_bytes()).hexdigest()}
(v2/'build/desktop-manifest.json').write_text(json.dumps(data,indent=2)+'\n')
PYMANIFEST
echo "Built and ad-hoc signed: $AE_V2_ROOT/build/Artificial Evolution 2.zip"
echo "Extract into ~/Applications, outside iCloud-managed Desktop folders."
