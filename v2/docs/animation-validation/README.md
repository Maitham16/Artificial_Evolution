# Skeletal animation validation

The original Python engine remains authoritative. Animation observes real counters, birth ledgers, terminal status, movement and directional telemetry.

| Check | Result | Evidence |
| --- | --- | --- |
| Original simulator suite | 431 tests passed | [Log](original-tests.log) |
| Python bridge and event receipts | 26 tests passed | [Log](bridge-tests.log) |
| Snapshot/interpolation | 18 checks passed | [Log](integration-tests.log) |
| Native scene / identity / authority | 40 checks passed | [Log](integration-tests.log) |
| Animation state, receipt timing, paused detail handoff and bone equivalence | 28 checks passed | [Log](integration-tests.log) |
| Real births and deaths through the full application | 8 checks passed | [Log](integration-tests.log) |
| Original project preservation | 591 tracked / 1,241 total pre-existing files unchanged | [Tracked hashes](root-preserved.json), [all originals](original-preserved.json) |
| Source / derived art and data imports | 50 runtime/editable files verified | [Log](assets.log) |
| Signed ZIP, fresh extraction, all seven modes | Launch, export manifests and exact original-engine replay passed | [Report](../bridge-validation/packaged-macos.json), [log](packaged-seven-modes.log) |

The event tests cover actual food collisions, predation, funded births, birth then parent death between display frames, retirement without death, counter acknowledgements and unchanged scientific state versus a direct Python session. GDScript checks cover walk/run/turn, stationary rest, feeding without forcing a stop, approach/retreat evidence, real age/maturity visual growth, founder adulthood, reproduction, death/fade, pause behavior, initial-history suppression, duplicate receipts, delayed delivery, run resets, and no added collisions. GPU skin matrices are compared numerically with the actual Skeleton3D path. The full application lifecycle test confirms that real continuous births reach both the child and parent animations, and real starvation deaths produce correctly scaled remnants that expire.

## Native package measurements

Apple M3, macOS 27.0.1, Godot 4.7.2 Compatibility renderer, Balanced quality. Five sequential runs use the actual signed ZIP extracted outside the checkout, with 480 displayed frames each and the first 90 excluded. Timings include the live Python process, communication and interface. Actual screenshot/render dimensions are reported per run rather than assumed from the nominal window setting.

| Mode | Camera | Final active models | Render pixels | Mean fps | Median | 95th percentile |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| foraging | ground | 100 | 1520 × 960 | 41.4 | 24.07 ms | 29.24 ms |
| foraging | valley | 100 | 1520 × 960 | 43.3 | 22.73 ms | 26.67 ms |
| predator_prey | ground | 52 | 1520 × 960 | 49.4 | 20.37 ms | 23.51 ms |
| traits | ground | 100 | 1520 × 960 | 43.7 | 22.22 ms | 26.63 ms |
| continuous | ground | 42 | 1520 × 960 | 50.9 | 20.51 ms | 25.49 ms |

The two foraging runs retain all 100 animals and measure approximately 41–43 fps. Other modes have changing populations, active events, corpse remnants and potentially different render dimensions; the frame rates are not a controlled comparison between simulation modes.

The predator/prey run recorded 48 confirmed captures and 48 deaths, with both pursuit and retreat states. The shortened continuous demonstration recorded 29 real births, 29 reproduction receipts and 11 deaths; it displayed Growing and Reproducing states. All five runs reported zero event-journal gaps. Rest is exercised with controlled stationary inputs in the state tests, rather than forced into the moving native populations. [Raw profiles](packaged-animation.json) contain clip activity, observed receipts, actual detailed/GPU counts, frame times and the exact archive checksum.

The installed `~/Applications/Artificial Evolution 2.0.app` was updated from the tested archive and passed signature verification. Current screenshots are [herd](../screenshots/meadow.png), [pursuit/death](../screenshots/animation-predators.png), [body traits](../screenshots/animation-traits.png) and [continuous lifecycle](../screenshots/animation-continuous.png).

## Reproduce

```bash
./.venv/bin/python -m unittest discover -v
./v2/tools/test.sh
python3 v2/tools/verify_original.py --all-existing
python3 v2/tools/fetch_animal_assets.py --verify-runtime
./v2/tools/build_macos.sh
./.venv/bin/python v2/tools/validate_macos.py
./.venv/bin/python v2/tools/validate_animation_macos.py
```

Omit `--all-existing` on another checkout; local untracked historical research files are not required there. Rig authoring and demonstration commands are in [CREATURE_ANIMATION.md](../CREATURE_ANIMATION.md). The observation adapter is deliberately extended under v2; the original numerical modules and 2D application are unchanged.

Limitations: local Apple Silicon validation, programmatic UI checks and native captures; no manual OS mouse/keyboard QA, x86_64 execution or Apple notarization. Finder still needs Desktop-folder access when the external Python project lives on Desktop. Growth and pose behavior are visual representations; no physical growth, mating, root-motion physics or terrain foot IK was introduced.
