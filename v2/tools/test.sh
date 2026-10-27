#!/bin/bash
set -euo pipefail
AE_V2_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AE_ROOT="$(cd "$AE_V2_ROOT/.." && pwd)"
AE_TEST_PYTHON="${AE_PYTHON:-$AE_ROOT/.venv/bin/python}"
"$AE_TEST_PYTHON" -m unittest discover -s "$AE_V2_ROOT/tests" -p 'test_*.py' -v
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --script tests/run_tests.gd
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --script tests/ui_smoke.gd -- --no-auto-save
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --script tests/animation_states.gd
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --script tests/lifecycle_smoke.gd -- --no-auto-save
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --script tests/ecosystem_smoke.gd -- --no-auto-save
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --script tests/desktop_smoke.gd -- --no-auto-save
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --script tests/terrain_animation.gd
"$AE_V2_ROOT/Run Artificial Evolution 2.command" --headless --script tests/habitat_smoke.gd -- --no-auto-save
