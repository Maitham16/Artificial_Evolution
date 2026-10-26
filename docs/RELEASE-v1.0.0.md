# Artificial Evolution 1.0.0 — research workbench

A unified Python/Pygame application for the artificial-life experiments developed
through Steps 1–28.

## Application

- Seven interactive worlds: food seeking, seasons, obstacles/hazards, inherited
  brains/bodies, predator–prey, social behavior, and continuous ecosystems.
- Mode-appropriate algorithms, including fitness selection, neutral inheritance,
  random/greedy steering, frozen founders, group/individual survival, and funded
  or clonal reproduction.
- Live population/fitness/family curves, ancestry edges, creature inspection,
  and current-state hidden-neuron previews.
- Validated configuration import, automatic run archiving on model changes,
  background exports, and verified fixed-tick replay.
- CSV/JSON datasets, numeric genomes, PNG/SVG/PDF figures, HTML reports,
  configurations, screenshots, and SHA-256 manifests.
- A research catalog covering all 15 studies from Steps 13–27, with published
  figures, isolated full-protocol jobs, progress, cancellation, and plotting.

## Scientific record

Earlier model kernels and results are preserved. The latest controlled evaluation
used 16 archived training pairs, fresh matched environments, confidence intervals,
45 primary tests, and 21 exploratory tests with separate Holm corrections.
Evolved fitness/food gains over random movement coexist with a substantial gap
to greedy steering, environment-dependent neutral comparisons, and severe
scarcity failures. Live demonstrations are descriptive; the published studies
provide the independent-seed evidence.

## Get started

Download the source ZIP, extract it, then run:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python simulator.py
```

The optional research ZIP adds the complete historical datasets and trained
populations. Merge it into the same extraction folder for saved-model studies.
See `docs/USER_GUIDE.md` for controls and exports and
`docs/REPRODUCIBILITY.md` for protocols, replay, validation, and asset rebuilding.

The source and research archives have deterministic Git-based manifests.
`SHA256SUMS.txt` verifies their contents; `BUILD-INFO.json` identifies the release
commit. This release was validated on macOS with the pinned Python 3.13 runtime,
native interactions, the full test suite, seven-mode export/replay checks, and
an actual background-study/plot integration run.

`RELEASE-VERIFICATION.json` records the verified tag/commit and the GitHub asset
digests after upload.
