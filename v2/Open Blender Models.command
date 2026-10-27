#!/bin/bash
set -euo pipefail
AE_V2_ROOT="$(cd "$(dirname "$0")" && pwd)"
AE_BLENDER="${BLENDER_BIN:-/Applications/Blender.app/Contents/MacOS/Blender}"
if [[ ! -x "$AE_BLENDER" ]]; then
  AE_BLENDER="$(command -v blender || true)"
fi
if [[ ! -x "$AE_BLENDER" ]]; then echo "Run v2/tools/setup_macos.sh to install Blender."; exit 1; fi
exec "$AE_BLENDER" "$AE_V2_ROOT/art_source/creature.blend" "$@"
