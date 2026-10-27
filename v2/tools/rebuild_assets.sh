#!/bin/bash
set -euo pipefail
AE_V2_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AE_BLENDER="${BLENDER_BIN:-/Applications/Blender.app/Contents/MacOS/Blender}"
"$AE_BLENDER" --background --factory-startup --threads 2 --python "$AE_V2_ROOT/tools/build_assets.py"
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --editor --import
