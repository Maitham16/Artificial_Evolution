# Standalone desktop validation — 27 October 2026

The app is a self-contained Apple Silicon build. All changes are under `v2/`; the original simulator, interface, tests, presets and results are unchanged.

| Check | Result | Evidence |
| --- | --- | --- |
| Original Python environment | **431 tests passed**, 119.453 s | [Original tests](original-tests.log) |
| Installed bundled interpreter | **431 original tests passed**, 111.114 s | [Installed-runtime original tests](installed-runtime-original.log) |
| v2 Python adapter, transport, observation and packaging | **38 tests passed** | [v2 test log](v2-tests.log) |
| Same v2 Python suite using the installed app's interpreter | **38 tests passed** | [Installed-runtime v2 log](installed-runtime-v2.log) |
| Existing Godot state / interface / skeletal animation / lifecycle / ecosystem | **18 + 40 + 28 + 8 + 33 checks passed** | [v2 test log](v2-tests.log) |
| New desktop controls / inspection / rendering budgets | **37 checks passed** | [v2 test log](v2-tests.log) |
| Original preservation | **1,241 original files / 591 tracked unchanged** | [Preservation](preservation.json) |
| Signed ZIP, cold extraction | **Nine native cases passed** with original export verification and exact replay | [Package report](packaged-desktop.json) |
| No checkout or Homebrew dependency | All native cases denied reads from the repository, `/opt/homebrew` and `/usr/local` | [Package report](packaged-desktop.json) |
| Independent original 2D CLI | Bundled original entry point ran, exported, verified and replayed 60 ticks | [2D CLI log](original-2d.log) |
| Signature and development settings | Signature still valid after all 3D/2D runs; saved external paths unchanged | [Package report](packaged-desktop.json) |
| Installed app / easy launcher | Installed from the checked ZIP; `.command` → macOS LaunchServices → bundled engine connected; signature valid after shutdown | [Install](install.log), [launcher record](installed-launch.json) |

The v2 total is **202 Python tests and Godot checks**, separately from the original 431 tests. Both original and new suites also ran with the installed bundled interpreter. The desktop checks exercise actual pause/speed acknowledgements, trackpad pinch and pan gestures, camera bounds and easing, follow/release, scaled picking, accurate energy/identity inspection, distant shadow budgets, static pose/food reuse and presentation-only state preservation. High-speed follow tracks the received interpolated pose directly and increases camera responsiveness with simulation speed, avoiding a second target delay. The observed settings truncation bug has a regression check; saves are now atomic and bundled launches cannot replace development paths. Installer tests cover corrupt archive rejection and restoration after a failed final check. Runtime assembly uses a fresh temporary interpreter outside Desktop/iCloud, avoiding conflicting package files in the former Desktop cache.

## Native profiles

![Desktop](../screenshots/desktop-foraging.png)

| Case | Python ticks | Mean FPS | Actual screenshot pixels |
| --- | ---: | ---: | --- |
| foraging | 839 | 41.8 | 1520 × 960 |
| seasons | 453 | 47.1 | 1520 × 960 |
| obstacles | 462 | 44.8 | 1520 × 960 |
| traits | 459 | 44.5 | 1520 × 960 |
| predator_prey | 435 | 48.7 | 1520 × 960 |
| social | 489 | 43.9 | 1520 × 960 |
| continuous | 742 | 49.2 | 1520 × 960 |
| foraging-performance | 722 | 48.8 | 1520 × 960 |
| foraging-small | 462 | 44.3 | 1160 × 732 |

The foraging performance profile renders the world at half resolution while keeping the HUD at full resolution. Balanced uses full resolution. These are single local rendering measurements, not matched scientific experiments or broad performance guarantees. Conditions and populations evolve during wall-clock rendering; compare reproduction and fitness only with the established matched experiment procedures. The small-window capture uses the actual macOS content area, excluding its title bar.

The validator freshly extracted the actual signed ZIP outside the checkout, used a system-only PATH, removed all `AE_` development overrides, and supplied invalid `PYTHONHOME`/`PYTHONPATH` to test interpreter isolation. macOS `sandbox-exec` denied file reads from the checkout and Homebrew locations for both Godot and its Python child. It checked all **95** bundled source/preset/helper hashes against the checkout. All seven modes exported bundles accepted and exactly replayed by the original engine. Continuous-mode validation used the explicit existing lifecycle demo configuration. No live source events were forced. Zero journal gaps were observed.

The `*-run.json` files are authoritative reports copied from those verified temporary bundles, suitable for original replay; they are not complete archived bundles. Re-running the validator regenerates full temporary exports. Screenshots and profiles record the final HUD, not manual OS interaction.

The first post-run signature check caught the independent original 2D plotting path writing a cache into its signed engine folder. A runtime-only cache policy now sets a user cache before importing that unchanged code; the final 3D/2D sequence passed signature verification. Numerical engine code was not changed. Existing CC0 art manifests also verified: 50 animal/runtime/editable files and 41 nature assets.

This is local Apple M3 engineering validation, not independent replication. No Intel execution, Apple notarization or manual operating-system mouse/keyboard QA is claimed. The current standalone artifact is arm64/macOS 13+.

## Reproduce

```bash
./.venv/bin/python -B -m unittest discover -v
./v2/tools/test.sh
python3 v2/tools/verify_original.py --all-existing
./v2/tools/build_macos.sh
./.venv/bin/python v2/tools/validate_desktop_macos.py
python3 v2/tools/install_macos.py
python3 v2/tools/validate_installed_macos.py
./"v2/Launch 3D Application.command"
```

On another checkout omit `--all-existing`, which includes this Mac's local historical experiment files. No root files or original published releases are modified. [Usage](../DESKTOP_APP.md), [runtime provenance](../BUNDLED_RUNTIME.md), [interactive ecosystem](../INTERACTIVE_ECOSYSTEM.md).
