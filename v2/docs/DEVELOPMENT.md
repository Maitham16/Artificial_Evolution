# Development and builds

[Documentation](README.md) · [Architecture](ARCHITECTURE.md) · [Installation](INSTALLATION.md) · [Validation](RESEARCH_AND_VALIDATION.md)

V2 changes belong under `v2/`. Original root code, tests, presets, results, README, V1 guides and released assets stay frozen for the current isolation contract. Do not refactor numerical modules into Godot to implement a visual feature.

## Project layout

```text
Artificial_Evolution/
  README.md, docs/            Original V1 documentation
  *.py, configs/             Original Python engine, CLI, UI, tests and presets
  results/                   Preserved research datasets/models/figures
  .github/workflows/          Existing original Python CI
  v2/
    README.md, docs/          V2 guides, examples, historical audits/screenshots
    project.godot            Entry scene, window, shader globals, Metal renderer
    scenes/main.tscn          Main application
    scripts/                 View, UI, transport, interpolation and animation
    backend/                 Python adapter, optional habitat, runtime cache helper
    configs/                 V2 lifecycle demo and separate physical options
    assets/                  Runtime meshes, textures, pose libraries and licenses
    art_source/              Editable Blender source; excluded from Godot imports
    tools/                   Setup, asset authoring, tests, packaging and validators
    tests/                   Python and GDScript integration/regression checks
    toolchain.lock.json      Authoring/export-tool downloads and hashes
    runtime.lock.json        Standalone Python/wheel/license lock
    export_presets.cfg       macOS arm64 export configuration
    build/, .godot/, .cache/  Generated/ignored local artifacts
```

See [Architecture](ARCHITECTURE.md#source-map) for individual file responsibilities. Do not commit `.venv`, `.godot`, caches, bytecode, build products or operating-system files. Texture/model `.import` settings and `.gd.uid` files are source metadata; preserve intentional existing settings.

## Source setup and editing

Follow [Installation](INSTALLATION.md#option-b-source-development), then:

```bash
./"v2/Open Godot Editor.command"
./"v2/Run Artificial Evolution 2.command" -- --immersive
```

Use the pinned standard Godot 4.7.2 rather than requiring the .NET build. Blender is needed for asset authoring, not simulation. The bridge imports NumPy/Pygame/Matplotlib through the existing original Python environment.

Presentation code must consume real source IDs, positions and events. New decorative effects need clear UI/source labels. A numerical extension needs an explicit option, separately recorded rules/configuration and declared replay; it must not masquerade as an unchanged V1 experiment.

## Tests

```bash
# Complete V2 Python + headless Godot checks:
./v2/tools/test.sh

# Complete original Python regression suite:
./.venv/bin/python -B -m unittest discover -v

# Original tracked-file preservation on any matching checkout:
python3 v2/tools/verify_original.py

# Also require original local untracked datasets/exports (author's Mac only):
python3 v2/tools/verify_original.py --all-existing
```

The latest complete V2 record is 58 Python tests plus Godot suites of 18, 40, 28, 8, 33, 37, 17, 38 and 16 checks: **293 total**, separately from 431 original tests. Counts describe that recorded revision; inspect current output after adding tests.

| Suite | Main coverage |
| --- | --- |
| Python `test_engine_bridge.py` | Authority/parity, transport, validation, archives, shutdown and replay |
| Python animation/ecosystem tests | Passive observations, receipts, food/season/opponent semantics |
| Python desktop packaging tests | Runtime locks, source payloads, installer verification/rollback |
| Python physical tests | Geometry/costs, all-mode replay, disabled equivalence, exports and TCP rejection |
| `run_tests.gd`, `ui_smoke.gd` | Received state, interpolation, interface and acknowledged configuration |
| `animation_states.gd`, `lifecycle_smoke.gd` | Skeletal pose/event/lifecycle behavior |
| `ecosystem_smoke.gd`, `desktop_smoke.gd` | Observation/scenery, HUD, camera and rendering budgets |
| `panel_input.gd` | Actual viewport-dispatched clicks, wheel/pan, drag and view switching |
| `terrain_animation.gd`, `habitat_smoke.gd` | Foot IK/batching and physical source/display separation |

Targeted commands:

```bash
./.venv/bin/python -m unittest discover -s v2/tests -p 'test_*.py' -v
./"v2/Run Artificial Evolution 2.command" --headless \
  --script tests/panel_input.gd -- --no-auto-save
```

The existing GitHub Actions workflow runs original root Python tests and original seven-world export/replay checks on Linux/macOS. It does **not** install Godot or run `v2/tools/test.sh`. Native graphics, packaging and V2 GDScript coverage require the separate commands above; do not infer them from a green V1 CI badge.

## Asset authoring

Current runtime art is committed. Generators are deliberate authoring tools and can overwrite editable `.blend` and derived resources. Preserve hand edits, then review manifests and intended changes.

### Current animal pipeline

Open a current rig explicitly:

```bash
/Applications/Blender.app/Contents/MacOS/Blender v2/art_source/animation/wolf.blend
```

`Open Blender Models.command` opens prototype `art_source/creature.blend`; it is not a chooser for current deer/wolf animation files. `rebuild_assets.sh` runs the prototype-art generator. Earlier `art_source/animals/` files and two-clip vertex-animation assets are not the active skeletal renderer.

To regenerate the current skeletal assets from recorded sources:

```bash
python3 v2/tools/fetch_animal_assets.py
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --python v2/tools/prepare_animation_rigs.py
./"v2/Run Artificial Evolution 2.command" --headless --editor --import
./"v2/Run Artificial Evolution 2.command" --headless --script tools/bake_skeletal_poses.gd
./"v2/Run Artificial Evolution 2.command" --headless --editor --import
python3 v2/tools/fetch_animal_assets.py --verify-runtime
```

The verifier rejects unrecorded derived changes; update `ASSET_SOURCES.json` deliberately after reviewing intentional authoring output. Pose palettes must retain linear/lossless/no-mipmap imports and necessary bone attributes. [Creature animation](CREATURE_ANIMATION.md) describes strides, layers and clip requirements.

### Landscape pipeline

```bash
python3 v2/tools/fetch_nature_assets.py
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --python v2/tools/prepare_nature_assets.py
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --python v2/tools/bake_forest_impostors.py
./"v2/Run Artificial Evolution 2.command" --headless --editor --import
python3 v2/tools/fetch_nature_assets.py --verify-runtime
```

Check [Natural world](NATURAL_WORLD.md) for generator inputs/limits. Asset fetchers use pinned checksums and are authoring-time tools; normal app use is offline.

### Isolated art review

```bash
./"v2/Run Artificial Evolution 2.command" --script tools/animal_gallery.gd \
  -- --clip=Walk --phase=0.25 --screenshot=/tmp/ae2-animal-gallery.png
./"v2/Run Artificial Evolution 2.command" --script tools/foot_ik_gallery.gd
```

These fixtures pose art without Python behavior and must not be reported as observed feeding, hunting or reproduction. The foot gallery writes its documented before/after screenshots; avoid overwriting audit artifacts during unrelated work. Gallery tool scripts need the source/editor executable because release templates lack `--script`.

## Desktop build and runtime lock

```bash
./v2/tools/build_macos.sh
python3 v2/tools/install_macos.py
```

The builder imports resources, exports the official universal macOS template and thins the fresh Godot executable to arm64. It stages outside Desktop/iCloud, assembles a fresh CPython 3.13.18 runtime, installs exactly the locked dependency wheels, includes license texts, copies unchanged original root Python/presets and V2 helpers, signs nested Mach-O files, then signs/verifies/zips the application. It checks the actual executable architecture, minimum OS and category and emits the archive SHA in `desktop-manifest.json`.

`runtime.lock.json` pins archive/wheel/license hashes and the unchanged requirements hash. `engine-manifest.json` inside the app identifies copied source files and base commit; exact file hashes matter when a working-tree build precedes its eventual commit. The original `.venv` is never copied or upgraded.

The package excludes development docs, tools/tests as Godot resources, Blender authoring files and caches. The Python payload still includes original Python sources/tests for source-hash consistency. Do not remove notices to shrink a build. [Bundled runtime](BUNDLED_RUNTIME.md) covers cache relocation and interpreter flags.

## Native package validation

Run the focused current audits after rebuilding:

```bash
./.venv/bin/python v2/tools/validate_habitat_macos.py
python3 v2/tools/validate_panel_input_macos.py
python3 v2/tools/validate_installed_macos.py
```

The habitat validator exercises 13 release cases, including repeated Metal timing, original/physical modes, exact declared replay and slower OpenGL fallback. The panel validator instruments the exact exported UI pack with the native Godot editor executable and an external input fixture, using bundled Python and denied checkout/Homebrew reads; it separately smoke-tests the release executable. This is not manual hardware input or script injection into release templates.

The installed validator exercises the one-click LaunchServices path and signature after closure. Its default output is `docs/desktop-validation/installed-launch.json`; preserve prior audit records when collecting a new campaign. Validators generally write fixed audit/screenshots paths. Copy evidence to a new campaign intentionally instead of silently attributing old records to a new archive.

Older `validate_macos.py`, `validate_animal_macos.py`, `validate_animation_macos.py`, `validate_ecosystem_macos.py`, `validate_desktop_macos.py` and `profile_nature_macos.py` retain focused historical workflows. Read their scope before running them. Headless checks cannot establish native FPS, material correctness, notarization or cross-platform execution.

## Documentation and contribution workflow

Keep guides source-backed. Include actual UI labels, argument delimiters, working relative links, explicit placeholders and the correct original/physical replay entry point. Document limitations rather than adding speculative features. Use existing audit hashes as historical evidence, not a performance claim for every rebuild.

For the repository's requested workflow: implement only the requested step, check the intended changes, preserve unrelated edits, then commit/push to `master`. Build/cache files stay ignored. Verify original-file hashes before completing work. A documentation-only change should not require modifying the original V1 docs or rebuilding its released archives.

The [repository review](REPOSITORY_REVIEW.md) lists current implementation/documentation mismatches and [troubleshooting](TROUBLESHOOTING.md) gives operational remedies without changing the original engine.

## Documentation media

The [visual gallery](GALLERY.md) contains real native application captures. Its [capture and publishing procedure](GALLERY.md#capture-method-and-reproduction) uses `v2/tools/capture_gallery.py`, the real Godot Main scene and the original Pygame application. Exported runs must pass their declared numerical replay before publication. `v2/tools/publish_gallery.py` produces small JPEGs, sampled GIF previews and timestamped H.264 videos using the included Swift/AVFoundation encoder. Keep raw lossless frames and export bundles under ignored `.cache/`; commit only reviewed media and its hash/configuration manifest.
