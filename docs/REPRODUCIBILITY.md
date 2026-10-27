# Reproducing the simulator and its evidence

The version 1.0 release combines a research interface with the existing numerical
models. Earlier experiments retain their original methods, trained arrays, raw
histories, source hashes, and audit records.

Version 1.0.1 repairs packaging: both source and research ZIPs contain the same
committed MIT `LICENSE`, recorded in each archive manifest. The source ZIP also
includes `.python-version`, `.gitattributes`, and the CI workflow. This fixes the
missing runtime-version file that prevented the v1.0.0 ZIP installation from
completing the preserved-file check. The original v1.0.0 assets and tag remain
unchanged. Hazard feedback in 1.0.1 is observational; damage and fitness rules
retain their original numerical implementation.

## Validated runtime

The release was checked on macOS with Python 3.13.17, NumPy 2.5.4, Pygame 2.6.1,
and Matplotlib 3.11.2. `requirements.txt` pins the direct and transitive packages.
Both native-window interactions and SDL dummy-display checks were performed.
Numerical replay checks refer to this recorded runtime; source hashes identify
the implementation used for each export.

## Distinguish three kinds of evidence

1. **Interactive demonstration:** one seeded run with provisional live metrics.
   Exporting and replaying establish what that run did.
2. **Engineering integration checks:** bounded tests exercise every mode,
   transitions, exports, job execution, and source preservation. Their results
   do not estimate an evolutionary treatment effect.
3. **Independent-seed research studies:** the original Step 13–27 scripts use
   their declared conditions, budgets, and analysis units. Their reports support
   the statistical conclusions, with the stated uncertainty and limitations.

Step 27 reused all 16 Step 18 training pairs and tested new matched worlds.
Its 1,056 cohorts are not 1,056 independent training replicates. Its inference
averages test repeats within training seed and applies Holm correction to 45
primary and 21 exploratory tests separately. Inspect its protocol and failure
cases when interpreting the observed improvements over random or neutral control.

## Repeat a live run

Load an exported configuration to start a fresh run with the same parameters:

```sh
python simulator.py --config PATH/TO/config.json
```

For the recorded run itself, preserve its tick/control history:

```sh
python simulator.py --verify-bundle PATH/TO/bundle
python simulator.py --replay PATH/TO/bundle/run.json --headless
```

Pause and speed affect playback. Reproduction toggles and manual transitions
are recorded at physics ticks. Environment/algorithm changes start separate runs
and archive the previous run, avoiding an undocumented mixed-condition history.
Observation and exporting do not draw from the model's random streams. Endpoint
sampling in continuous reports is isolated so mid-run exports do not change
later replay results.

## Repeat the engineering validation

From the project root, choose new output paths:

Install the research-evidence asset for the full repository suite and historical
validation inputs.

```sh
python -m unittest discover -v
python validate_simulator.py --output .cache/new-integration.json --demos .cache/new-demos
```

The validator exercises all seven modes, verifies every file/genome manifest,
replays each run, and reconstructs the saved native interaction records. It also
runs a **two-seed, one-second** version of the ecosystem pipeline through the
real background-study launcher and plotter. That short job validates integration;
the full Step 26 persistence study remains the separate 600-second protocol.

Published Step 28 demonstration bundles live under `results/step28-demos/`.
The native records under `results/step28-native/` document actual pause, export,
mode/environment/algorithm switching, and automatic archiving. They were collected
during pre-release UI verification; final tick replay checks verify their model
outcomes against the released observer. New release bundles include additional
mode-specific telemetry while those early native records retain their original
fields and checksums.

`results/step28-baseline.json` records the preceding commit and all 427 tracked
file hashes. The final integration audit checks all **426 earlier files other
than README**, including the original launcher and ignore rules. The model
kernels and 347 prior research-result artifacts retain their original versions.

## Repeat a published research study

Install the research-evidence asset for saved-population studies. The workbench
catalog delegates to the existing scripts, using fresh output folders. For example:

```sh
python simulator.py --study 27 --workers 8 --export-root exports/new-evaluation
```

Study folders retain commands, working directory, source hashes, logs, canonical
protocols/results, and plots. Source scripts remain directly callable with their
own documented options. The earlier README sections describe each experiment's
training and testing details. Do not pool scores across different model modes:
food fitness, hazard penalties, predator capture scores, group survival, and
continuous renewal address different questions.

## Rebuild release assets

From a Git checkout of the release tag:

```sh
python build_release.py --ref v1.0.1 --version v1.0.1 --output .cache/rebuilt-release
```

The builder reads committed Git blobs, assigns fixed ZIP timestamps/permissions,
and emits source/research archives, separate `release-source-manifest.json` and
`release-research-manifest.json` file manifests, archive SHA-256 checksums,
and `BUILD-INFO.json` identifying the exact commit. Untracked files and working-tree
changes do not enter the package. A unit test builds twice from the same commit
and checks identical archive hashes. The release upload is separately checked
against the final commit and asset digests.
