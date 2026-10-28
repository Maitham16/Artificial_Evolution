# Installation and launch

[Documentation](README.md) · [User guide](USER_GUIDE.md) · [Troubleshooting](TROUBLESHOOTING.md)

Run the standalone V2 desktop app for normal 3D exploration, V2 from source for development, or the original Python/Pygame application independently. Commands below assume the repository root unless stated otherwise.

## Requirements and compatibility

| Component | Desktop runtime | Source development / authoring |
| --- | --- | --- |
| Computer | Apple Silicon / arm64 package | Checked setup/native tools target macOS |
| OS | Tested macOS 27.0.1, Apple M3 | Same recorded validation machine |
| Godot | Included executable | **4.7.2 standard**, matching export templates |
| Python | Included relocatable **3.13.18** | Original `.venv`, recorded **3.13.17** |
| Python libraries | Bundled, locked wheels | Unchanged root `requirements.txt` |
| Blender | Not needed | **5.2.3** recorded authoring version |
| Internet | Not needed after installation | Initial tools/runtime/asset downloads |
| Homebrew | Not needed | Setup uses it for missing Godot/Blender |

The release requires **macOS 14 or later**, matching the minimum tag of its locked NumPy wheel. End-to-end validation is limited to the recorded macOS 27 / M3 machine. Intel, Windows and Linux desktop packages are not provided or verified by this Mac pipeline.

The app is ad-hoc signed locally, not Apple notarized. Signature verification checks bundle integrity; it is not Apple distribution approval. See [runtime provenance](BUNDLED_RUNTIME.md) and [package evidence](panel-input-validation/packaged-panel-input.json).

## Option A: desktop app

On the prepared Mac:

1. In Finder choose **Go → Home**.
2. Open **Applications** in your home folder.
3. Double-click **Artificial Evolution 2.0.app**.

`~/Applications` is separate from system `/Applications`, where Godot and Blender are installed. Keep the app outside Desktop/iCloud-managed folders to avoid bundle metadata/signing interference.

```bash
open "$HOME/Applications/Artificial Evolution 2.0.app"
```

The app opens in the landscape. **Research** exposes settings, plots, lineages and connection information. Normal closure asks Python to archive a changed run; an export error leaves the app open and Python paused.

### Install a desktop ZIP

Download [Artificial Evolution 2.0.0 for Apple Silicon](https://github.com/Maitham16/Artificial_Evolution/releases/download/v2.0.0/Artificial_Evolution-v2.0.0-macos-arm64.zip) and the [SHA-256 checksums](https://github.com/Maitham16/Artificial_Evolution/releases/download/v2.0.0/SHA256SUMS.txt). Verify the ZIP, double-click it and move the extracted app to `~/Applications`. Manual installation requires no Python, Godot or Blender.

```bash
shasum -a 256 -c SHA256SUMS.txt
```

The app is ad-hoc signed rather than notarized. If macOS blocks the downloaded app, attempt opening it once, then use **System Settings → Privacy & Security → Open Anyway** for this app. Do not disable Gatekeeper globally. The local source builder still creates `v2/build/Artificial Evolution 2.zip`.

From a prepared checkout, use the checked installer:

```bash
python3 v2/tools/install_macos.py
```

Or double-click `v2/Install Desktop App.command`. It verifies the archive checksum when its sidecar is available, the app signature and embedded engine hashes. It restores the old app if final validation fails, and does not modify the original `.venv`.

A fresh clone does not contain ignored `v2/build/`; build the package first. V1 release ZIPs remain separate from the [V2 desktop release](https://github.com/Maitham16/Artificial_Evolution/releases/tag/v2.0.0).

### Installed launcher arguments

The repository's installed-app launcher accepts application flags directly:

```bash
./"v2/Launch 3D Application.command" --ecosystem-panel
./"v2/Launch 3D Application.command" --habitat
```

Arguments open a **new instance**. Existing instances retain separate Python sessions; close them normally when finished. The launcher inserts the Godot/application delimiter for you.

## Option B: source development

```bash
git clone https://github.com/Maitham16/Artificial_Evolution.git
cd Artificial_Evolution
```

Keep an existing working environment. Otherwise install Python 3.13 through your normal distribution and create it:

```bash
python3.13 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pip check
```

The root requirements pin NumPy 2.5.4, Pygame 2.6.1, Matplotlib 3.11.2 and transitive dependencies. Source V2 reuses those requirements; it has no second unpinned requirements file.

Prepare the authoring toolchain:

```bash
./v2/tools/setup_macos.sh
```

Setup checks macOS, installs missing Godot/Blender through Homebrew, selects/downloads the pinned Godot if needed, records tool locations, verifies the existing Python engine, installs matching export templates, imports resources and runs V2 tests. It prints the Blender version rather than forcing an existing Blender to match the recorded version. [toolchain.lock.json](../toolchain.lock.json) records checked downloads/hashes.

Setup does not create a missing `.venv` or upgrade an existing one. Follow printed missing-tool/interpreter messages before retrying.

```bash
./"v2/Run Artificial Evolution 2.command" -- --immersive --ground-view
./"v2/Open Godot Editor.command"
```

Without `--immersive`, a source run through the standard Godot editor binary normally opens the workbench. The source launcher searches `GODOT_BIN`, `v2/.tools/Godot.app`, `godot` on PATH, then `/Applications/Godot.app`. It requires Godot 4. Current runtime assets are committed; ordinary launches need no asset regeneration.

### Argument placement

Godot options go **before** `--`; application options go **after** it:

```bash
./"v2/Run Artificial Evolution 2.command" --resolution 1160x760 -- \
  --immersive --mode=predator_prey --quality=0
```

See [CLI options](CONFIGURATION.md#application-command-line). V2 has no `--algorithm` flag; select the controller through RunConfig JSON or the interface.

## Option C: original 2D application

```bash
./.venv/bin/python simulator.py
# Equivalent source launcher:
./"v2/Run Original Simulator.command"
```

In the standalone app, **Research → Connection → Open original 2D** uses its included Python and unchanged engine snapshot, without the checkout or `.venv`. Each interface has its own process.

The original `main.py` and historical experiment entry points retain their options. [V1's README](../../README.md) documents them. V1 and V2 keyboard shortcuts differ.

## Build the standalone app

From the prepared source toolchain:

```bash
./v2/tools/build_macos.sh
python3 v2/tools/install_macos.py
open "$HOME/Applications/Artificial Evolution 2.0.app"
```

Outputs are `v2/build/Artificial Evolution 2.zip` and `desktop-manifest.json`. The builder exports Godot, assembles fresh locked CPython outside Desktop, copies unchanged original Python sources/presets, includes helpers/licenses, signs native binaries and verifies the app. It reuses verified downloads but never copies or upgrades the original `.venv`.

See [native validation](DEVELOPMENT.md#native-package-validation) for release execution versus instrumented UI-pack tests.

## Data locations and moving a checkout

| Location | Purpose |
| --- | --- |
| `~/Applications/Artificial Evolution 2.0.app` | Installed standalone app |
| `~/Library/Application Support/ArtificialEvolution2/engine.json` | Optional development repository/interpreter |
| `~/Library/Application Support/ArtificialEvolution2/bridge/` | Private temporary TCP endpoints |
| `~/Library/Application Support/ArtificialEvolution2/python-runs/` | 3D exports and automatic archives |
| `~/Library/Application Support/ArtificialEvolution2/cache/` | Runtime caches |
| `~/Library/Caches/ArtificialEvolution2/desktop-runtime/` | Verified build downloads |
| `exports/` in the checkout | Original source CLI's default exports |
| `results/` in the checkout | Preserved published evidence |

After moving a source checkout:

```bash
./.venv/bin/python v2/tools/configure_engine.py
# Or select an already prepared interpreter:
python3 v2/tools/configure_engine.py --python /absolute/path/to/python
```

The Connection tab supports these paths. Packaged launches prefer their bundled payload and do not overwrite remembered source paths. Explicit `AE_ENGINE_ROOT`, `AE_PYTHON`, `--engine-root=` and `--python=` overrides select external code; record the engine/config/report together for replay.

Next: [User guide](USER_GUIDE.md).
