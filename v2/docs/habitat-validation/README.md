# Metal, foot IK and physical habitat validation — 27 October 2026

All original 2D files, source rules and published results remain unchanged. Original research is still the default v2 mode. Actual terrain/wading/climate effects require the explicit physical-habitat option and its separate replay.

| Check | Result | Evidence |
| --- | --- | --- |
| Original Python suite | **431 tests passed**, 114.171 s | [Original tests](original-tests.log) |
| Python adapter / transport / observations / packaging / habitat | **49 tests passed** | [v2 tests](v2-tests.log) |
| Existing Godot state/interface/animation/lifecycle/ecosystem/desktop checks | **18 + 40 + 28 + 8 + 33 + 37 passed** | [v2 tests](v2-tests.log) |
| Terrain animation and batching | **38 checks passed**, three animal rigs | [v2 tests](v2-tests.log) |
| Physical habitat UI and source/display separation | **16 checks passed** | [v2 tests](v2-tests.log) |
| Repeated 60 FPS target | **Passed across three seeds**, 100 founders, Balanced, 1520 × 960 | [Signed-package audit](packaged-habitat.json) |
| Native experiment connection | **13 signed-package runs**, exact declared replay; all seven original modes and three physical modes | [Signed-package audit](packaged-habitat.json) |
| Self-contained physical replay | Bundled helper verified/replayed a physical bundle without checkout access | [Bundled CLI](bundled-habitat-replay.log) |
| Original preservation | **1,241 original files / 591 tracked unchanged** | [Preservation](preservation.json) |
| Installed app and one-click launch | Signature, bundled-engine launch and **49 bundled-Python tests** passed | [Install](install.log), [LaunchServices](installed-launch.json), [Bundled tests](installed-python-tests.log) |

The v2 total is **267 Python tests and Godot checks**, separately from the original 431. Physical replay tests cover all seven modes, unchanged legacy sessions, passive observation/RNG equivalence, seeded geometry, actual wading slowdown and energy, blocked deep-water travel, simulation-time climate costs, dry food, safe founders, social food allocation, declared exports, source hashes and replay mismatch detection. TCP tests confirm that invalid habitat settings preserve the previous run. UI checks confirm that decorative overrides and IK cannot change the physical Python report.

## Native frame timing

![Physical arena](../screenshots/habitat-physical-foraging.png)

| Case | Mean FPS | p95 frame ms | Frames over 25 ms | Replay |
| --- | ---: | ---: | ---: | --- |
| metal-seed-2801 | 60.00 | 17.17 | 0.00% | original |
| metal-seed-2802 | 60.00 | 17.18 | 0.00% | original |
| metal-seed-2803 | 60.00 | 17.20 | 0.00% | original |
| legacy-seasons | 59.60 | 17.13 | 0.67% | original |
| legacy-obstacles | 60.00 | 17.09 | 0.00% | original |
| legacy-traits | 59.99 | 17.14 | 0.00% | original |
| legacy-predator_prey | 60.00 | 17.09 | 0.00% | original |
| legacy-social | 60.01 | 17.16 | 0.00% | original |
| legacy-continuous | 60.00 | 17.07 | 0.00% | original |
| physical-foraging | 60.00 | 17.17 | 0.00% | v2 habitat |
| physical-predator_prey | 60.00 | 17.11 | 0.00% | v2 habitat |
| physical-continuous | 60.00 | 17.10 | 0.00% | v2 habitat |
| compatibility-fallback | 40.28 | 29.31 | 48.15% | original |

The previous Compatibility desktop audit measured **41.8 FPS** on this Mac. The current Metal trials used three seeds, 1,200 displayed frames each and **1,110 measured frames** after warmup. Every frame interval comes from monotonic `Time.get_ticks_usec()` wall time, not the engine's smoothed delta. Capture, pause, Python plotting and export are excluded. The recorded target is mean FPS ≥59, p95 ≤19 ms and fewer than 1% of frames over 25 ms. Raw intervals, p99, maximum frame time and renderer diagnostics remain in the JSON.

This target passed in all three repeated Metal trials. Physical foraging, predator–prey and continuous cases also met it. The Compatibility/OpenGL fallback remains a documented failure case at about 40 FPS. One short original seasonal run had a 0.67% late-frame fraction; it is retained rather than hidden. These are local Apple M3 observations, not a guarantee for every computer, population size, quality profile or background workload, and not a statistical finding about evolutionary fitness.

The validator extracted the actual ad-hoc signed ZIP outside the checkout, denied reads from the checkout, `/opt/homebrew` and `/usr/local`, removed development overrides and set invalid Python environment paths. All **96** packaged original-source/preset/helper hashes matched. Each exported bundle passed manifest/genome checks and its declared numerical replay. The app remained correctly signed after all runs and saved development paths remained unchanged. No texture-leak warnings occurred in the final native suite.

## Foot contact and limitations

The reachable-slope unit fixture measured a worst IK target residual of **0.014425 m** across deer, stag and wolf poses. It checks unchanged source transforms, pause behavior, detailed/batched transitions and confirmed-death restoration. Native endpoint samples showed constrained residuals up to approximately **0.0433 m**. These metrics describe the joint/IK target, not a universal hoof-volume collision guarantee. Finite reach, sharp reflections and accelerated motion remain limitations; distant animals do not run CPU foot IK.

The [before](../screenshots/habitat-feet-before.png) / [after](../screenshots/habitat-feet-after.png) gallery is a synthetic geometry fixture using the same rigs and terrain-alignment convention. It is not presented as a Python simulation event. [Fixture log](feet-gallery.log).

Physical mode uses the existing Python decision/survival/movement/interaction framework, with a v2 mixin and recorded deterministic surface/climate. It changes biological outcomes and is **not equivalent to the original 2D model**. Original published results stay frozen. No new learned avoidance strategy, full rigid-body dynamics, swimming, water currents, tree collisions or measured biological energetics are claimed. Physical social groups may experience different terrain and require matched experimental controls.

The committed `*-run.json` files are numerical reports copied from verified temporary bundles, not full standalone export directories. Re-running the validator regenerates the complete temporary datasets. Habitat replay requires the corresponding source hash. Only arm64 execution was tested; no Apple notarization, independent replication or manual operating-system input QA is claimed.

## Reproduce

```bash
./.venv/bin/python -B -m unittest discover -v
./v2/tools/test.sh
python3 v2/tools/verify_original.py --all-existing
./v2/tools/build_macos.sh
./.venv/bin/python v2/tools/validate_habitat_macos.py
python3 v2/tools/install_macos.py
python3 v2/tools/validate_installed_macos.py
./"v2/Run Artificial Evolution 2.command" --script tools/foot_ik_gallery.gd
```

Omit `--all-existing` on another checkout. [Rules, controls, bounds and physical replay](../PHYSICAL_HABITAT.md).
