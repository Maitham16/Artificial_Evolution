# Historical prototype validation — 27 October 2026

This record describes the initial independent Godot prototype at commit `81782f1`. Current Python-engine connection checks are recorded in [bridge-validation](../bridge-validation/README.md).

All checks were performed locally on the user's Apple M3 Mac. This is implementation validation, not independent external scientific reproduction.

| Check | Result | Evidence |
| --- | --- | --- |
| Original baseline tests | 431 passed, 113.245s | [Before log](../inspection/original-tests-before.log) |
| Original tests after v2 implementation | 431 passed, 116.300s | [After log](original-tests-after.log) |
| Original file hashes | All 591 tracked and 1,241 total pre-existing files unchanged | [Preservation JSON](preservation.json) |
| Godot model suite | 87 checks, zero failures | [Model log](godot-model-tests.log) |
| Godot interface integration | 15 checks, zero failures | [UI log](godot-ui-tests.log) |
| Neutral evolution across four cohorts | 4,000 ticks exported and replayed exactly | [Multi-generation log](multigeneration.log) |
| Freshly extracted standalone Mac ZIP | Signature passed; meadow and hazards launched, rendered, exported, and replayed exactly | [Packaged-app JSON](packaged-macos.json), [log](packaged-macos.log) |
| Fresh source copy without `.godot` | Import, 87 model checks, 15 interface checks passed | [Fresh-source log](clean-source.log) |
| Setup rerun | Existing apps/templates recognized; import and model suite passed | [Setup summary](toolchain.json) |
| Utility/launcher checks | Python AST parse and Bash syntax passed; original launcher reports 1.0.1 | [Toolchain summary](toolchain.json) |

The model suite covers independent network copies and mutation, controller-matched physical starts, local food sensors, food consumption/regrowth, boundary reflection, barrier cost, hazard damage, cohort replacement, ancestry, selection versus neutral eligibility, identical mutation draws conditional on identical genomes, configuration rejection, negative fitness summaries, immutable export bundles, tamper rejection, six-habitat replay, complete transfer checks, and cancellation.

The interface suite instantiates the real scene, emits actual control signals, checks tabs and settings, projects a 3D body into viewport coordinates to test selection, exercises the keyboard handler and camera controls, completes the transfer workflow, and tests cancellation. It does not simulate operating-system mouse clicks. Computer control was unavailable for the new application, so manual mouse/keyboard QA was not performed.

The packaged-app validator extracts the actual ZIP into a fresh `/private/tmp` directory, verifies its code signature, runs its own binary with that directory as the working directory, renders native OpenGL frames, exports all data plus a screenshot, checks every manifest hash, and reconstructs both runs with the pinned Godot kernel. It therefore checks the packaged resource paths independently of the source-project working directory. Generated full bundles remain locally under ignored `v2/build/validation/`; representative [world](../screenshots/world.png) and [hazard](../screenshots/hazards.png) screenshots are committed.

The app is a universal arm64/x86_64 build. Only arm64 execution on this Mac was tested. The ad-hoc signature is valid locally; Apple notarization and external-machine validation were not performed. The ZIP SHA in `packaged-macos.json` identifies this local build; a fresh rebuild can have a different ZIP hash because native packaging includes timestamps/signatures.

The initial packaging checks exposed and resolved three problems: required macOS texture import formats, iCloud/Finder metadata interfering with signing, and re-entry into the asynchronous bounded-frame export path. The final extracted bundle checks passed after those fixes. Negative fitness summaries and plots were also checked while reviewing failure conditions.

Re-run from the repository root:

```bash
./.venv/bin/python -m unittest discover -v
python3 v2/tools/verify_original.py --all-existing
./v2/tools/test.sh
./"v2/Run Artificial Evolution 2.command" --headless --script tests/ui_smoke.gd
./v2/tools/build_macos.sh
python3 v2/tools/validate_macos.py
```

The last command regenerates the two validation screenshots and packaged-app records under `v2/docs/`, and creates fresh local export bundles. On another checkout, omit `--all-existing`: the untracked experiment/export files from the original working Mac are intentionally not required there. The original root GitHub Actions workflow is preserved; it continues testing the Python application on macOS and Linux. V2 checks are invoked separately through the commands above.
