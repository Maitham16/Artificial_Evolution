#!/bin/bash
set -euo pipefail
AE_ORIGINAL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ ! -x "$AE_ORIGINAL_ROOT/.venv/bin/python" ]]; then
  echo "The original Python environment is missing. See v2/README.md for the original installation commands."
  exit 1
fi
cd "$AE_ORIGINAL_ROOT"
exec "$AE_ORIGINAL_ROOT/.venv/bin/python" "$AE_ORIGINAL_ROOT/simulator.py" "$@"
