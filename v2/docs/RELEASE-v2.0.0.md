# Artificial Evolution 2.0.0 — 3D Living World

[Download the Mac app](https://github.com/Maitham16/Artificial_Evolution/releases/tag/v2.0.0) · [Installation](INSTALLATION.md) · [Gallery](GALLERY.md) · [Original V1](../../docs/USER_GUIDE.md)

Artificial Evolution 2.0 brings the existing Python artificial-life engine into a standalone Godot 3D desktop application. Python continues to control neural decisions, food, energy, survival, reproduction and ecological interactions. Godot supplies the landscape, presentation, animation and interactive controls.

## Included

- Detailed deer and wolves with skeletal animation, terrain foot IK and actions driven by observed Python movements/events.
- Forested landscapes, vegetation, water, weather, seasons and daylight; decorative effects remain distinct from simulated rules.
- Orbit, pan, zoom, ground/valley views, animal following and inspection, Research and Ecosystem panels, pause and speed controls.
- Seven original ecological models: food seeking, changing seasons, obstacles/hazards, inherited bodies, predator–prey, social behavior and continuous ecosystems.
- Selected neural, neutral inheritance, random, greedy and frozen-founder controllers where supported by the chosen model.
- Optional, explicitly separate physical-habitat rules for terrain, wading, depth limits and climate energy costs.
- Exported configurations, datasets, genomes, plots and reports, with model-appropriate numerical verification/replay.
- A bundled relocatable Python runtime, locked dependencies, original source snapshot and required licenses; no source checkout or authoring tools needed to run the desktop app.

The original 2D simulator and V1 releases remain independently accessible. This release does not modify the original Python numerical engine, tests, presets, research results or archived V1 documentation.

## Download and launch

Use **Artificial_Evolution-v2.0.0-macos-arm64.zip** from the release assets. Download **SHA256SUMS.txt** beside it and verify the ZIP:

```bash
shasum -a 256 -c SHA256SUMS.txt
```

Extract the ZIP, move **Artificial Evolution 2.0.app** to your home **Applications** folder, then double-click it. The app runs offline. See [installation](INSTALLATION.md#install-a-desktop-zip) for macOS's app-specific opening flow and the source-build alternative.

## Compatibility and limitations

The package targets **Apple Silicon / arm64**, requires **macOS 14+**, and is ad-hoc signed rather than Apple notarized. Complete native validation is on macOS 27.0.1 / Apple M3; this does not certify every compatible OS or Mac. Intel, Windows and Linux desktop assets are not provided.

The 3D world presents the existing Python models. Physical habitat is an optional 2.5D extension, not full rigid-body ecology. V2 has no generic saved-genome importer or interactive replay viewer. Original-rule exports use the original numerical replay; physical exports use the V2 habitat replay helper. Rendering performance depends on hardware, quality and population size.

Scientific conclusions remain limited to adaptive behavior under documented conditions, not general intelligence. See [research methods and limitations](RESEARCH_AND_VALIDATION.md).

## Release verification

Release assets include **BUILD-INFO.json**, **RELEASE-VERIFICATION.json**, **desktop-manifest.json**, **runtime.lock.json** and **SHA256SUMS.txt**. They identify the source revision, ZIP hash, pinned runtime, source-preservation results and executed checks. The standalone validators extract the actual ZIP outside the checkout, deny access to the checkout/Homebrew and verify native runs, numerical exports/replay and signatures.

To generate fresh evidence without replacing historical audit records:

```bash
./.venv/bin/python -B v2/tools/validate_desktop_macos.py \
  --archive /absolute/path/to/Artificial_Evolution-v2.0.0-macos-arm64.zip \
  --output .cache/release-validation/desktop
./.venv/bin/python -B v2/tools/validate_habitat_macos.py \
  --archive /absolute/path/to/Artificial_Evolution-v2.0.0-macos-arm64.zip \
  --output .cache/release-validation/habitat
```

These are local engineering checks, not independent third-party replication or Apple notarization. Code is MIT licensed; bundled art/runtime components retain their recorded licenses.
