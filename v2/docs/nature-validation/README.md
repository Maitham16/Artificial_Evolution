# Landscape validation

Validation on this Mac: Apple M3, macOS 27.0.1, Godot 4.7.2 Compatibility renderer, 1520 × 960 window.

| Check | Result | Evidence |
| --- | --- | --- |
| Original Python suite | 431 tests passed | [Log](original-tests.log) |
| Python bridge suite | 20 tests passed | [Log](integration-tests.log) |
| Snapshot/interpolation | 18 checks passed | [Log](integration-tests.log) |
| Native scene and landscape | 33 checks passed | [Log](integration-tests.log) |
| Pre-existing files | 1,241 unchanged | [Hashes](original-preserved.json) |
| Protected source | 598 original files and existing Python files unchanged | [Report](python-preserved.json) |
| Committed art | 41 runtime asset hashes verified | [Log](assets.log) |
| Actual Mac ZIP | All seven modes launched, exported and replayed exactly with Python | [Report](../bridge-validation/packaged-macos.json), [log](packaged-macos.log) |

The landscape checks cover cache reuse, absence of scenery collision objects, upright tree imports, terrain-aware picking, immersive viewport reparenting/restoration, hidden research guides, smooth camera motion while paused, profile rebuilding, and unchanged Python reports after camera/quality/layout controls.

## Native performance

The actual signed ZIP was extracted into a fresh temporary directory and its binary ran outside the source working directory. Each of six sequential runs displayed a live 100-creature Python session for 480 frames, excluding the first 90 from timings. These are local frame-time samples, including UI and IPC.

| Quality | Camera | Mean fps | Median frame | 95th percentile frame |
| --- | --- | ---: | ---: | ---: |
| Performance | Valley | 58.8 | 16.67 ms | 20.00 ms |
| Performance | Ground | 59.1 | 16.67 ms | 18.75 ms |
| Balanced | Valley | 56.4 | 16.67 ms | 21.21 ms |
| Balanced | Ground | 60.2 | 16.67 ms | 18.29 ms |
| Lush | Valley | 51.0 | 19.61 ms | 21.43 ms |
| Lush | Ground | 56.6 | 16.67 ms | 21.09 ms |

[Raw timing records](profiles.json) contain the exact archive SHA-256 and actual vegetation counts. Logs are named `0-valley.log` through `2-ground.log`. The installed app at `~/Applications/Artificial Evolution 2.0.app` was updated from this ZIP and passed signature verification.

## Reproduce

```bash
./.venv/bin/python -m unittest discover -v
./v2/tools/test.sh
python3 v2/tools/verify_original.py --all-existing
python3 v2/tools/fetch_nature_assets.py --verify-runtime
./v2/tools/build_macos.sh
./.venv/bin/python v2/tools/validate_macos.py
./.venv/bin/python v2/tools/profile_nature_macos.py
```

Omit `--all-existing` on a different checkout: the original local untracked experiment files are not needed there. The asset scripts use only the standard library; Blender is required only to regenerate art. The source viewer and original Python app retain the run commands in [v2/README](../../README.md).

Limitations: native captures and programmatic control checks were completed; manual OS mouse/keyboard input was not tested. No x86_64 execution or Apple notarization was performed. Finder still requires Desktop-folder permission on this Mac because the external Python project lives on Desktop; the Terminal launcher is verified. Scenery is display-only. Background trees use baked, camera-facing crowns with approximate lighting and no dynamic shadows; detailed trees near the clearing cast shadows. Timings do not establish scientific performance or evolutionary advantage.
