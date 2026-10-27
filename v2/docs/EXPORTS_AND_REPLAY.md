# Export, datasets and replay

[Documentation](README.md) · [Settings](CONFIGURATION.md) · [Research](RESEARCH_AND_VALIDATION.md)

An export is an immutable observation of an actual Python run. It is not a screenshot-based reconstruction or a generic population savegame. Original-rule and physical-habitat exports have different numerical replay entry points.

## Save an interactive run

Press **E** or choose **Research → Export run**. Python snapshots the session and copied birth genomes; a worker writes the bundle while the session can continue. **Open export folder** opens:

```text
~/Library/Application Support/ArtificialEvolution2/python-runs/
  run-<run-id>-<unique-suffix>/
```

Normal changed-run replacement and shutdown also archive the previous run. Invalid configuration is rejected before replacement. Failed automatic export retains the old run; shutdown-save failure leaves the window open and Python paused. A successful explicit export does not guarantee later unsaved ticks are preserved after a crash.

Source `simulator.py` defaults to root `exports/` instead. Neither workflow overwrites the published `results/`. Historical independent-Godot prototype exports under `ArtificialEvolution2/runs/` use a superseded format and are not silently converted.

## Bundle contents

| File | Meaning |
| --- | --- |
| `config.json` | Complete normalized original RunConfig |
| `run.json` | Run ID, configuration, tick/control history, metrics, lifetimes, telemetry, canonical mode report, runtime and original source hashes |
| `population.csv` | Sampled time, living count, earned fitness, meals, food, families, diversity and role-specific score fields |
| `individuals.csv` | Every observed lifetime, birth identity/parent/root, starting state/genome hash, last state and cohort censoring |
| `telemetry.csv` | Available body-energy, hazard, collision, capture, social and reproduction observations |
| `lineage.csv` | Complete key/parent/founder/generation/depth/birth/cohort-end table |
| `generations.csv` | Completed canonical generation statistics; may be empty in an incomplete/continuous run |
| `genomes.npz` | Numeric birth weights, body vectors/presence flags and identity metadata |
| `population.png`, `.svg`, `.pdf` | Four-panel scientific figure: population, fitness, families, meals |
| `application.png` | Optional native GUI capture; absent from a display-free export |
| `report.html` | Local report, interpretation and relative artifact links |
| `manifest.json` | Run identity/schema and SHA-256 of bundle files |

The engine's `app_version`/HTML version remains **1.0.1**, identifying the unchanged Python research application contract. The Godot viewer's application version is **2.0.0**. Seeing 1.0.1 inside a research bundle does not mean the 3D app failed to update.

Keep the entire folder together. Moving only the HTML or CSV prevents relative links and integrity verification from covering the original bundle.

## Verify versus replay

| Operation | Establishes | Does not establish |
| --- | --- | --- |
| Verify bundle | Manifest file hashes, identities/config and numeric birth-genome correspondence | That physics reproduces, or that a scientific treatment works |
| Original replay | Reconstruct config, fixed ticks and semantic controls; compare metrics/lifetimes/samples/canonical reports/available telemetry | Independent replication, cross-runtime equivalence or arbitrary checkpoint import |
| Physical replay | Same scientific checks plus extension source hash, options, climate and complete habitat telemetry | Fully realistic 3D physics or externally validated model fidelity |

Original replay records source hashes for provenance but does not enforce every current source hash before execution; it detects disagreement through numerical comparisons. Physical replay additionally requires the **exact physical module source hash**. Preserve the appropriate source and runtime, not just the JSON.

### Copyable original-rule example

From the repository root, this creates a unique temporary output directory, runs two simulated seconds, verifies the generated bundle and replays it:

```bash
AE2_DOC_ROOT="$(mktemp -d /tmp/ae2-original.XXXXXX)"
./.venv/bin/python simulator.py --headless \
  --config v2/docs/examples/foraging.json --ticks 120 --export-root "$AE2_DOC_ROOT"
AE2_DOC_BUNDLE="$(find "$AE2_DOC_ROOT" -maxdepth 1 -type d -name 'run-*' -print -quit)"
./.venv/bin/python simulator.py --verify-bundle "$AE2_DOC_BUNDLE"
./.venv/bin/python simulator.py --replay "$AE2_DOC_BUNDLE/run.json" --headless
```

Expected output includes **Bundle verified** and **Replay verified: 120 ticks**. This is an incomplete live demonstration, not three finished generations or a full scientific study. Omit `--headless` from the replay command to open the reconstructed original 2D state paused; it can continue if its budget remains.

To replay an existing original-rule bundle, substitute its absolute path for `AE2_DOC_BUNDLE`. Replay uses saved controls/ticks: do not add seed, mode, config or tick overrides.

## Physical-habitat exports

Physical exports additionally contain:

| Record | Meaning |
| --- | --- |
| `run.json:habitat` | Extension version/source SHA, config, surface SHA, climate and actor ledger |
| `habitat.json` | Separate extension record and configuration |
| `habitat_telemetry.csv` | Uphill/water/weather energy, water seconds, blocked moves and actual metres |
| `manifest.json:engine_extension` | Explicit `physical_habitat_v1` marker |

The HTML includes the physical notes/configuration and V2 helper command. Ordinary Python structural verification can read its files, but ordinary `simulator.py --replay` is **not** its numerical model.

### Copyable fixed-tick physical example

The habitat helper has verification/replay options, not a general `--ticks` training CLI. This small source example uses its existing session API directly:

```bash
AE2_PHYSICAL_ROOT="$(mktemp -d /tmp/ae2-physical.XXXXXX)"
./.venv/bin/python - "$AE2_PHYSICAL_ROOT" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, str(Path("v2/backend").resolve()))
from habitat import HabitatSession, export_habitat
from research_session import RunConfig
session = HabitatSession(RunConfig(population=20, seed=2801), {"enabled": True})
for _ in range(120):
    session.step()
report, genomes = session.snapshot()
print(export_habitat(report, genomes, Path(sys.argv[1])))
PY
AE2_PHYSICAL_BUNDLE="$(find "$AE2_PHYSICAL_ROOT" -maxdepth 1 -type d -name 'run-*' -print -quit)"
./.venv/bin/python v2/backend/habitat.py --verify-bundle "$AE2_PHYSICAL_BUNDLE"
./.venv/bin/python v2/backend/habitat.py --replay "$AE2_PHYSICAL_BUNDLE/run.json"
```

Both commands should report an exact V2 habitat replay. To create a visual physical run, use the interface or `--habitat` with bounded Godot capture/export flags; see [CLI](CONFIGURATION.md#application-command-line).

### Verify without a checkout

Set `AE2_SAVED_BUNDLE` to an existing absolute bundle path. For an original-rule bundle:

```bash
AE2_APP="$HOME/Applications/Artificial Evolution 2.0.app"
AE2_SAVED_BUNDLE="/absolute/path/to/run-bundle"
"$AE2_APP/Contents/Resources/python/bin/python3" -E -s -B \
  "$AE2_APP/Contents/Resources/engine/simulator.py" --verify-bundle "$AE2_SAVED_BUNDLE"
"$AE2_APP/Contents/Resources/python/bin/python3" -E -s -B \
  "$AE2_APP/Contents/Resources/engine/simulator.py" --replay "$AE2_SAVED_BUNDLE/run.json" --headless
```

For a physical bundle, use the bundled helper from the app whose habitat source hash matches:

```bash
"$AE2_APP/Contents/Resources/python/bin/python3" -E -s -B \
  "$AE2_APP/Contents/Resources/engine/v2/backend/habitat.py" \
  --verify-bundle "$AE2_SAVED_BUNDLE"
```

## Read numeric genomes safely

The archive represents **birth** parameters for every observed actor, including those later dead or retired. It is not a single selected adult population or mutable runtime object dump. Parameter keys map to input weights, hidden bias, output weights and output bias.

```python
from pathlib import Path
import numpy as np

bundle = Path("/absolute/path/to/run-bundle")
with np.load(bundle / "genomes.npz", allow_pickle=False) as data:
    print(data["keys"])
    print(data["parameter_0"].shape)
    print(data["body_traits_present"])
```

Different modes have different neural shapes. Use the accompanying config/metadata rather than assuming every archive is 8–8–2. The manifest verifier compares each birth genome with its recorded hash and body vector.

## Censoring, time and presentation

`individuals.csv:censored` marks an alive actor whose cohort ended. `telemetry.csv:right_censored` marks living observations, including a continuous horizon stop. Missing mode-specific values are empty; they are not measured zeros.

`run.json:execution.controls` records pause, speed, automatic reproduction and manual transitions at physics ticks. Wall-clock FPS, camera movement, visual overrides and foot IK are not scientific controls. A screenshot and the delayed display may show a different presentation moment from the latest authoritative state.

V2 has no GUI button that loads a bundle back into its 3D view or imports arbitrary saved weights. Configuration reload starts a new seeded experiment; numerical replay reconstructs the saved experiment. Rich historical brain playback remains in the V1 tools.

## Integrity and preservation

Exports stage files privately and publish a new directory when complete. A checksum mismatch should be investigated or the original bundle restored; do not edit hashes to disguise a failed replay. A physically inconsistent model can still replay exactly, so read [model limits](PHYSICAL_HABITAT.md#combined-model-limitations) separately from integrity claims.

Keep old application/source snapshots when preserving physical runs, because the helper enforces its source hash. Keep the original research `results/` and released V1 ZIPs unchanged. See [Research and validation](RESEARCH_AND_VALIDATION.md) for the difference between a replayed demonstration and independent scientific evidence.
