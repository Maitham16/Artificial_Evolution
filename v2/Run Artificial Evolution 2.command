#!/bin/bash
set -euo pipefail
AE_V2_ROOT="$(cd "$(dirname "$0")" && pwd)"
AE_GODOT="${GODOT_BIN:-}"
if [[ -z "$AE_GODOT" ]]; then
  if [[ -x "$AE_V2_ROOT/.tools/Godot.app/Contents/MacOS/Godot" ]]; then
    AE_GODOT="$AE_V2_ROOT/.tools/Godot.app/Contents/MacOS/Godot"
  elif command -v godot >/dev/null 2>&1; then
    AE_GODOT="$(command -v godot)"
  else
    AE_GODOT="/Applications/Godot.app/Contents/MacOS/Godot"
  fi
fi
if [[ ! -x "$AE_GODOT" ]]; then
  echo "Godot 4 is missing. Run v2/tools/setup_macos.sh first."
  exit 1
fi
AE_GODOT_VERSION="$("$AE_GODOT" --version)"
if [[ "$AE_GODOT_VERSION" != 4.* ]]; then
  echo "Artificial Evolution 2 requires Godot 4; found $AE_GODOT_VERSION"
  exit 1
fi
exec "$AE_GODOT" --path "$AE_V2_ROOT" "$@"
