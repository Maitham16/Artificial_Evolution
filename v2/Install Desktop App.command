#!/bin/bash
set -euo pipefail
AE_INSTALL_ROOT="$(cd "$(dirname "$0")" && pwd)"
python3 "$AE_INSTALL_ROOT/tools/install_macos.py"
exec /usr/bin/open "$HOME/Applications"
