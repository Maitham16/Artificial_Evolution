# Artificial Evolution 2.0 — Python engine, Godot 3D view

The 3D application now runs the repository's **existing Python simulation engine**. Python owns brains, creature movement, food, energy, survival, selection, reproduction, mutation, seasons, hazards, body traits, predation, cooperation, and continuous ecosystems. Godot renders the state it receives and interpolates movement between snapshots.

![Standalone desktop application](docs/screenshots/desktop-foraging.png)

The new [living landscape](docs/NATURAL_WORLD.md) adds rolling green terrain, scanned trees and plants, wind-blown grass, mountains, water, sunlight and atmospheric lighting. Click **Landscape view** or press **V**, then choose **Valley** or **Ground view**. Three scenery quality profiles adjust rendering cost without changing Python.

The [animal models](docs/ANIMAL_MODELS.md) now use detailed, textured deer for herbivores and wolves for predators, with natural coat/size variations and [event-driven skeletal animation](docs/CREATURE_ANIMATION.md). Walk/run/turn, feeding, pursuit/escape, rest, real continuous births, age-based visual growth and confirmed deaths follow Python observations. Editable Blender files and CC0 source/license records are included.

The [interactive ecosystem observatory](docs/INTERACTIVE_ECOSYSTEM.md) adds edible ferns, source event navigation, recorded movement trails, animated plants, seasonal colors, weather and a day/night cycle. Press **N** or click **Ecosystem**. The panel separates Python events and actual seasonal food from decorative lighting and weather.

All integration changes are under `v2/`. The root Python application, engine, tests, dependencies, configurations, results, and published 1.x releases are unchanged.

## Run both versions on this Mac

**3D desktop application:** double-click **Artificial Evolution 2.0** in `~/Applications`, or double-click [Launch 3D Application.command](Launch%203D%20Application.command). It opens in the landscape view with pause, speed, camera controls and a live creature inspector. The app bundles Python, pinned libraries and an unchanged snapshot of the original engine. It runs offline without this checkout, `.venv`, Godot, Blender or Homebrew.

```bash
open "$HOME/Applications/Artificial Evolution 2.0.app"
```

**Original 2D application:** double-click [Run Original Simulator.command](Run%20Original%20Simulator.command), or run:

```bash
./.venv/bin/python simulator.py
```

The original source, environment, tests, results and interface remain unchanged. **Research → Connection → Open original 2D** can also start the unchanged original interface with the bundled runtime as a separate process; it remains independent when the 3D viewer closes.

For source development, which uses the existing root `.venv` and an installed Godot:

```bash
./"v2/Run Artificial Evolution 2.command"
./"v2/Open Godot Editor.command"
./"v2/Open Blender Models.command"
```

To reinstall the checked desktop ZIP, double-click **Install Desktop App.command** or run `python3 v2/tools/install_macos.py`. The installer verifies the archive when its build checksum is present, checks the app signature and engine hashes, and restores the previous app if final verification fails. It does not install or modify the original Python environment.

The current standalone build targets **Apple Silicon (arm64), macOS 13+**. It is locally ad-hoc signed, not Apple-notarized. Intel execution is not supported by this runtime package.

## Setup and dependencies

The authoring toolchain is Godot 4.7.2 standard, Blender 5.2.3 LTS, and the existing Python 3.13.17 environment with unchanged root dependency pins. The desktop build uses a separate pinned, relocatable CPython 3.13.18 runtime; it never upgrades the original `.venv`. Godot uses its Compatibility renderer. Blender is needed for authoring assets, not during simulation.

If the original environment already works, keep it. To create it on another checkout:

```bash
python3.13 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

With [Homebrew](https://brew.sh) installed:

```bash
./v2/tools/setup_macos.sh
```

Setup installs missing Godot/Blender applications, verifies the original Python environment, records the engine paths, installs verified export templates, imports the project, and runs the bridge tests. It does not upgrade an existing `.venv`. Checked tool downloads are listed in [toolchain.lock.json](toolchain.lock.json).

To update the recorded repository/interpreter paths after moving the checkout:

```bash
./.venv/bin/python v2/tools/configure_engine.py
# Or choose another compatible interpreter:
python3 v2/tools/configure_engine.py --python /absolute/path/to/python
```

Optional development paths are stored in `~/Library/Application Support/ArtificialEvolution2/engine.json`. You can also edit them in the app's **Connection** tab. Source launches discover their own repository; `AE_ENGINE_ROOT` and `AE_PYTHON`, or `-- --engine-root=/path --python=/path`, provide explicit overrides. The packaged app prefers its bundled engine and never replaces saved development paths. Explicit environment/CLI overrides can still select an external checkout.

**Finder launch:** the self-contained app starts its bundled engine without reading the Desktop checkout. macOS may request access if you explicitly select a Desktop file or external development engine. The user data directory holds exports, connection endpoints and caches; the signed app remains unchanged while running.

## Controls

| Action | Control |
| --- | --- |
| Inspect a creature / edible plant | Left-click its displayed body / fern |
| Ecosystem events and scenery | N or **Ecosystem**; click a confirmed event to locate it |
| Orbit / pan | Right drag or two-finger gesture / middle drag or Shift-gesture |
| Zoom | Scroll, pinch, or the − / + buttons |
| Focus a creature | Double-click its body, I, or **Focus** |
| Fullscreen | ⛶ or Ctrl/Cmd + Enter |
| Overview / follow | R / F, or the camera buttons |
| Landscape / workbench | V / Esc |
| Ground camera | C or **Ground view** |
| Scenery quality | Performance / Balanced / Lush menu |
| Pause/resume Python | Space or the top button |
| Simulation rate | 1× / 5× / 20×, matching the Python engine |
| Export the Python run | E or **Export run** |
| Manual reproduction | Disable **Automatic reproduction**, then **Next generation** when a cohort completes |
| Single step | Pause, then **Single physics tick** |

The desktop HUD keeps pause, speed, inspection and cameras visible. **Research** restores the full workbench; **V** switches views. The sidebar scrolls to expose all research controls on smaller windows. Choose a mode, environment, controller, founder count, seed, food stock, and mutation settings, then press **Start new population**. Python validates the configuration and archives the previous run before replacing it. A failed archive leaves the previous run available.

**Run settings** loads presets directly from the original `configs/` folder and exposes the full existing Python JSON schema. **Load configuration** validates an external JSON configuration through Python before populating the controls. Seeds retain the engine's full 63-bit range. Food stock `−1` in the sidebar means use the environment default (`null` in the Python schema).

All seven existing modes are available:

| Python mode | Display and behavior |
| --- | --- |
| `foraging` | Selection, neutral inheritance, random movement, greedy food seeking, frozen founders |
| `seasons` | Original seasonal stock and cluster movement |
| `obstacles` | Original barriers and damaging areas; geometry and damage come from Python |
| `traits` | Original inherited speeds, body sizes, sensor ranges, and energy costs |
| `predator_prey` | Original hunting and escape; predators are wolves and prey are deer |
| `social` | Original group boundaries, signaling and food sharing; recent sharing links are shown |
| `continuous` | Original simultaneous births, deaths, ancestry and finite regrowth |

The right panel shows Python's live energy, capacity, age, meals, fitness, lineage, and mode-specific telemetry. Hidden-neuron activations are calculated by NumPy using the same passive preview as the original interface. **Lineages** uses Python's birth ledger and shows the largest 12 living families across eight ancestry generations. Full ancestry remains in the export.

The existing engine's rules and fitness definitions apply. Fixed-speed foraging comparisons keep their existing constraints; body-trait modes use inherited speeds and costs. Social fitness is survival age, and predator/prey scores retain their original definitions. Live plots describe one run and do not establish an evolutionary advantage.

## Real-time connection and recovery

In source mode Godot starts `v2/backend/engine_bridge.py` with the existing `.venv/bin/python`. The standalone app starts the same adapter from `Contents/Resources/engine/` with its bundled interpreter. All original root Python sources and presets are copied byte-for-byte during packaging and recorded in `engine-manifest.json`. This adapter imports `ResearchSession`, `RunConfig`, and the original export functions directly from the repository root. It contains no replacement physics or evolutionary algorithm. The previous GDScript simulation and brain implementation have been removed.

Python retains its 1/60-second physics step. Up to 30 snapshots per wall-clock second carry current poses, food, geometry, telemetry, and ancestry. Godot interpolates position and shortest-angle heading with a 100 ms display delay. Births, deaths, and new cohorts use their actual Python identities. Energy, age, fitness, and decisions are never calculated by the renderer. World coordinates are displayed at 20 Python pixels per Godot unit.

The view holds the last known pose when updates stop and does not extrapolate new motion. Python pauses when the viewer disconnects. **Reconnect** retains the same session while its Python process is still alive. A crashed or terminated Python process cannot retain an in-memory run: connect a new process, then start a new population or use the original replay workflow on an exported run. The app never falls back to a second simulation engine.

The connection is local to `127.0.0.1`, uses a randomly assigned port and a per-process token, and supports one controlling viewer. Temporary endpoint files are private and removed on shutdown. Normal app closure waits for Python to save the changed run and exit. A save error keeps the application open and Python paused so the error can be resolved. Python also checks its parent process and attempts to save if the viewer exits unexpectedly.

If the target speed exceeds available CPU capacity, the actual displayed speed falls below the target. The engine continues using fixed physics ticks. The renderer can discard superseded presentation snapshots without discarding physics steps.

## Export and replay with the original application

New 3D-view runs are written to:

```text
~/Library/Application Support/ArtificialEvolution2/python-runs/run-.../
```

Use **Open export folder**. Exports are produced by the original `research_session.export_bundle` and include `run.json`, `config.json`, `genomes.npz`, lifetime/lineage/population/telemetry CSVs, PNG/SVG/PDF plots, `report.html`, checksums, and a Godot screenshot for native GUI exports. Living or cohort-censored lifetimes retain the original engine's censoring fields.

From the repository root, use the existing commands:

```bash
./.venv/bin/python simulator.py --verify-bundle /absolute/path/to/run-bundle
./.venv/bin/python simulator.py --replay /absolute/path/to/run-bundle/run.json --headless

# Automated simulation using the same engine:
./.venv/bin/python simulator.py --headless --config configs/obstacles.json \
  --ticks 600 --export-root /tmp/ae-python-experiment
```

Historical exports from the initial independent Godot prototype remain under `ArtificialEvolution2/runs/`. Existing root exports/results are unchanged. Current 3D-view runs use the original Python bundle format; the historical Godot format is not silently converted.

## Test, edit, and build

```bash
# New transport, authority, interpolation and interface tests
./v2/tools/test.sh

# Original tests and preservation checks
./.venv/bin/python -m unittest discover -v
python3 v2/tools/verify_original.py --all-existing

# Edit and regenerate 3D assets
./"v2/Open Godot Editor.command"
./"v2/Open Blender Models.command"
./v2/tools/rebuild_assets.sh

# Build and test the actual Mac app ZIP
./v2/tools/build_macos.sh
./.venv/bin/python v2/tools/validate_macos.py
./.venv/bin/python v2/tools/validate_ecosystem_macos.py
./.venv/bin/python v2/tools/validate_desktop_macos.py
python3 v2/tools/install_macos.py
python3 v2/tools/validate_installed_macos.py
```

On another checkout, omit `--all-existing`; the original Mac's untracked experiment files are not required there. Rebuilding Blender assets deliberately regenerates the editable `.blend` files and optimized `.glb` files, so preserve hand edits before running the generator.

The Mac builder produces `v2/build/Artificial Evolution 2.zip` and `desktop-manifest.json`. It uses checksum-pinned runtime/wheel downloads in a private ignored cache, includes CPython and dependency licenses, signs all nested native binaries, then signs and verifies the outer app. Extract into `~/Applications` or use the installer; iCloud-managed Desktop folders can interfere with Mac bundle signing. No system Python or root dependency changes occur. See [Desktop application](docs/DESKTOP_APP.md), [runtime lock](runtime.lock.json) and [current desktop validation](docs/desktop-validation/README.md).

For bounded native validation, the app accepts `-- --frames=180 --mode=obstacles --screenshot=/absolute/world.png --export=/absolute/new-export-root`. The exported bundle is a unique child of that export root. It pauses Python before capture, saves the authoritative Python bundle, and shuts down the owned backend. `--no-auto-save` is intended for disposable automated test sessions.

See the [connection architecture](docs/PYTHON_BRIDGE.md), [current validation](docs/bridge-validation/README.md), and [original repository inspection](docs/INSPECTION.md). The original [README](../README.md) and [user guide](../docs/USER_GUIDE.md) remain the reference for the established research workflows.

## Licenses

The desktop runtime bundles the CPython/license texts and wheel dependency licenses; see [runtime provenance](docs/BUNDLED_RUNTIME.md). Project code and original generated art use the copied [MIT license](LICENSE). [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) contains bundled engine notices. Godot is [MIT licensed](https://godotengine.org/license/); Blender is an external [GPL authoring tool](https://www.blender.org/about/license/). The landscape includes [CC0 Poly Haven scans and textures](assets/nature/LICENSE.md), bundled locally with [source attribution and checksums](assets/nature/ASSET_SOURCES.json). The [animal models](assets/animals/LICENSE.md) are also CC0, with editable Blender rigs, [source credits and checksums](assets/animals/ASSET_SOURCES.json). No runtime art downloads are required.
