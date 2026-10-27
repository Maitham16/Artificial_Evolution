#!/bin/bash
set -euo pipefail
AE_V2_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# iCloud/Desktop file providers can recreate FinderInfo on .app bundles.
# Export, sign and archive outside those managed directories.
AE_STAGE="$(mktemp -d /private/tmp/artificial-evolution-build.XXXXXX)"
trap 'rm -rf "$AE_STAGE"' EXIT
mkdir -p "$AE_V2_ROOT/build"
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --editor --import
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --export-release macOS "$AE_STAGE/Artificial Evolution 2.zip"
/usr/bin/ditto -x -k "$AE_STAGE/Artificial Evolution 2.zip" "$AE_STAGE"
AE_APP="$(find "$AE_STAGE" -maxdepth 1 -name '*.app' -print -quit)"
if [[ -z "$AE_APP" ]]; then echo "Export produced no .app"; exit 1; fi
# These attributes belong only to this freshly generated application.
/usr/bin/xattr -dr com.apple.FinderInfo "$AE_APP" 2>/dev/null || true
/usr/bin/xattr -dr com.apple.ResourceFork "$AE_APP" 2>/dev/null || true
/usr/bin/codesign --force --deep --sign - "$AE_APP"
/usr/bin/codesign --verify --deep --strict "$AE_APP"
rm "$AE_STAGE/Artificial Evolution 2.zip"
/usr/bin/ditto -c -k --keepParent "$AE_APP" "$AE_STAGE/Artificial Evolution 2.zip"
cp "$AE_STAGE/Artificial Evolution 2.zip" "$AE_V2_ROOT/build/Artificial Evolution 2.zip"
echo "Built and ad-hoc signed: $AE_V2_ROOT/build/Artificial Evolution 2.zip"
echo "Extract into ~/Applications, outside iCloud-managed Desktop folders."
