#!/bin/bash
set -euo pipefail
AE_LAUNCH_ROOT="$(cd "$(dirname "$0")" && pwd)"
AE_DESKTOP_APP="$HOME/Applications/Artificial Evolution 2.0.app"
if [[ ! -d "$AE_DESKTOP_APP" ]]; then
  python3 "$AE_LAUNCH_ROOT/tools/install_macos.py"
fi
if [[ $# -gt 0 ]]; then
  exec /usr/bin/open -n "$AE_DESKTOP_APP" --args -- "$@"
fi
exec /usr/bin/open "$AE_DESKTOP_APP"
