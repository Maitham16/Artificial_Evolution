# Animal model validation

The tested package uses the existing Python engine with the new deer and wolf appearances. No scientific algorithm or original Python file changed.

| Check | Result | Evidence |
| --- | --- | --- |
| Original Python tests | 431 passed | [Log](original-tests.log) |
| Python bridge tests | 20 passed | [Log](integration-tests.log) |
| Godot state/interpolation checks | 18 passed | [Log](integration-tests.log) |
| Scene, animal identity and GPU pose checks | 40 passed | [Log](integration-tests.log) |
| Original tracked and local files | 1,241 unchanged | [Report](original-preserved.json) |
| All original non-v2 files and pre-existing Python files | 602 unchanged | [Report](python-preserved.json) |
| Animal art and import settings | 25 runtime/editable hashes and data settings verified | [Log](assets.log) |
| Freshly extracted signed ZIP, all seven modes | Launch, export manifests and exact original-engine replay passed | [Report](../bridge-validation/packaged-macos.json), [log](packaged-seven-modes.log) |

Animal checks verify lifetime/lineage IDs after mode changes, wolf/predator mapping, radius-controlled scale, deterministic appearance choices, movement-driven gait changes, paused poses, absence of runtime CPU skeletons, floating-point position textures, no data mipmaps, and unchanged Python state during rendering. Existing bridge/state tests cover births, deaths and cohort/run boundaries. Native idle and run-pose renders were inspected in addition to the headless checks.

## Native frame times

Apple M3, macOS 27.0.1, Godot 4.7.2 Compatibility renderer, 1520 × 960, Balanced scenery. Four sequential runs used the actual signed ZIP extracted outside the repository, 480 displayed frames each, with the first 90 excluded. Results include the live Python simulation, communication and interface.

| Mode | View | Mean fps | Median frame | 95th percentile frame |
| --- | --- | ---: | ---: | ---: |
| foraging | ground | 51.2 | 19.44 ms | 23.09 ms |
| foraging | valley | 50.3 | 20.00 ms | 23.33 ms |
| predator_prey | ground | 63.6 | 16.14 ms | 18.06 ms |
| traits | ground | 54.4 | 18.06 ms | 21.21 ms |

The two foraging captures show the 100-animal herd. Live populations differ across modes as Python applies survival and predation; these measurements are not a controlled comparison between modes. [Raw records](packaged-animals.json) include the exact ZIP checksum. Model close-ups are [here](../screenshots/animals.png); [predator/prey](../screenshots/animal-predators.png) and [body traits](../screenshots/animal-traits.png) were also captured natively.

The installed `~/Applications/Artificial Evolution 2.0.app` was updated from the tested ZIP and passed signature verification. The root 2D application and all established experimental results remain unchanged.

## Reproduce

```bash
./.venv/bin/python -m unittest discover -v
./v2/tools/test.sh
python3 v2/tools/verify_original.py --all-existing
python3 v2/tools/fetch_animal_assets.py --verify-runtime
./v2/tools/build_macos.sh
./.venv/bin/python v2/tools/validate_macos.py
./.venv/bin/python v2/tools/validate_animal_macos.py
```

On another checkout, omit `--all-existing`: local untracked historical result files are not required there. The model authoring and close-up review commands are in [ANIMAL_MODELS.md](../ANIMAL_MODELS.md).

Limits: local Apple Silicon validation; no x86_64 execution, Apple notarization or manual OS mouse/keyboard QA. Finder needs Desktop-folder permission when launching the external Python project on Desktop; the Terminal launcher is validated. All anatomy, coats and gait poses are presentation only. No attack-animation hit timing or terrain foot IK was added.
