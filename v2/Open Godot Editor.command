#!/bin/bash
set -euo pipefail
AE_V2_ROOT="$(cd "$(dirname "$0")" && pwd)"
exec "$AE_V2_ROOT/Run Artificial Evolution 2.command" --editor "$@"
