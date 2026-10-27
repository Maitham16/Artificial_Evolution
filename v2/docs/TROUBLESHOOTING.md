# Troubleshooting

[Documentation](README.md) · [Installation](INSTALLATION.md) · [Settings](CONFIGURATION.md) · [Export/replay](EXPORTS_AND_REPLAY.md)

First distinguish an installed-app problem, a source-toolchain problem and an experiment outcome. Record the view, mode, seed and physical-habitat status when reporting a problem.

## Which icon should I open?

Open **Finder → Go → Home → Applications → Artificial Evolution 2.0.app**. This is `~/Applications`, not system `/Applications`. Godot and Blender are authoring tools, not the simulator's normal launch icon.

```bash
open "$HOME/Applications/Artificial Evolution 2.0.app"
```

If it is absent, a fresh clone has no generated desktop ZIP. [Build/install](INSTALLATION.md#build-the-standalone-app) or obtain the actual desktop artifact. V1's release ZIP is a different package.

## macOS will not open the app

The current build is ad-hoc signed, not notarized. For an app you have verified and trust, Apple documents the per-app **System Settings → Privacy & Security → Open Anyway** flow after a blocked launch. Follow [Apple's current instructions](https://support.apple.com/en-gb/102445); a managed Mac may restrict this option. Do not change global security settings to diagnose the simulator.

Verify the installed bundle and reinstall from the checked ZIP if damaged:

```bash
codesign --verify --deep --strict "$HOME/Applications/Artificial Evolution 2.0.app"
python3 v2/tools/install_macos.py
```

Keep it outside Desktop/iCloud-managed folders. The installer checks engine file hashes and signature and rolls back a failed replacement. The arm64 runtime is not an Intel package. macOS 13 is declared by bundle metadata but not established for the full locked dependency stack; see [compatibility](INSTALLATION.md#requirements-and-compatibility).

## Source launch says Godot or Python is missing

Run from the repository root, not from inside `v2/`. The source launcher needs Godot 4 and the original `.venv`; the installed desktop app does not.

```bash
./.venv/bin/python -m pip check
./.venv/bin/python v2/tools/configure_engine.py
```

If `.venv/bin/python` is missing, follow [source installation](INSTALLATION.md#option-b-source-development). If Godot is missing, run the Mac setup after its prerequisites. If the checkout moved, recreate/verify the environment as appropriate and update connection paths; copying a virtual environment between locations is not the documented portability mechanism.

`GODOT_BIN` can select a nonstandard Godot executable. `AE_ENGINE_ROOT` and `AE_PYTHON` are explicit engine/interpreter overrides; remove stale overrides when you want the packaged payload.

## The app is waiting for Python

Packaged launches normally use their embedded engine without Desktop access. A selected Desktop file or external engine can require macOS folder permission. The source bridge continues waiting during delayed startup; check the Connection message instead of repeatedly creating new instances.

Use **Research → Connection** to inspect repository/interpreter paths. **Connect** launches the configured engine; **Reconnect** reuses its still-living owned process. Confirm that your explicit interpreter can import `research_session`, NumPy and the original dependencies. A crashed backend cannot recover its unsaved in-memory population simply by reconnecting.

Temporary endpoints are under `~/Library/Application Support/ArtificialEvolution2/bridge/`. They contain private connection tokens; do not publish them in bug reports. Do not delete a live instance's endpoint as a substitute for reconnecting normally.

## The Ecosystem panel does not click or scroll

The current fix keeps GUI input order above the immersive viewport. Close/reopen the updated app if an older process is still running. The [panel audit](panel-input-validation/README.md) identifies the fix and tests.

Place the pointer **inside the drawer** to scroll its outer content. The event list has a separate scroll region. Use the right-hand outer scrollbar to reach weather/daylight/scenery motion; scroll back up for Close, or press **N**. Over-panel trackpad gestures scroll; gestures over uncovered landscape control the camera.

Opening a new installed launch with arguments uses a new instance. Several identical windows can therefore belong to different versions/sessions; finish normal closure of the old one after exporting its run.

## I cannot move the camera or select an animal

Use right drag/two-finger gesture to orbit, middle drag/Shift-gesture to pan, wheel/pinch to zoom. There is no WASD/first-person controller. A focused text field suppresses keyboard shortcuts; click the landscape or finish text editing first.

Selection uses displayed animal bounds. **F** follows an active selection; panning releases follow. Dead/retired selections cannot be followed indefinitely. **R** returns to overview. Performance mode reduces 3D resolution, but picking is mapped into that viewport automatically.

## Low FPS or slow simulation

Render FPS and Python speed are different. A 60 FPS view can show Python below a requested 20× if the numerical workload is too high; a 1× simulation can render below 60 FPS if graphics are the bottleneck.

Try **Performance** quality, a smaller window, fewer founders and a lower population cap. Lush increases vegetation/particle budgets; continuous populations can approach 1000 only when configured, and the recorded 60 FPS result did not test every such cap. Keep native Metal as the normal Mac renderer.

The OpenGL Compatibility fallback exists but measured around 40 FPS on the local M3. It is a compatibility option, not the fast path. [Settings](CONFIGURATION.md#godot-options-and-installed-launches) shows its engine flags. Never use headless frame timing as evidence of native GPU performance.

## Animals still slide, clip or appear partly underwater

Nearby detailed skeletons use terrain foot IK; far animals use cheaper GPU skeletal motion without per-foot CPU IK. Finite leg reach, rapid boundary turns, speed multipliers and transitions can leave residual slip. Focus/follow for close inspection at 1×.

Python collision bodies are circular and do not match every antler, limb or muzzle. Visual juvenile growth does not shrink the engine's newborn collision radius. The physical extension permits shallow wading and blocks only above its configured depth limit; it has no swimming pose/physics. See [animation limits](ANIMALS_AND_ANIMATION.md#skeletal-performance-and-foot-contact).

## Weather, mountains or rivers do not affect survival

Original-rule mode deliberately keeps scenery separate. Enable **Research → Physical habitat (v2 rules) → Start new population** and check the **PHYSICAL HABITAT** badge for real slope/wading/climate costs. A manual weather/hour override remains cosmetic even then. Outside-arena water, trees and mountains remain scenery.

**Apply JSON configuration** currently starts original rules without forwarding the checkbox. Load the draft, tick Physical habitat, then use **Start new population**, or launch with `--config=… --habitat`. This is documented behavior, not a weather-driven change to the original model.

Physical predator capture paths have a [combined-model limitation](PHYSICAL_HABITAT.md#combined-model-limitations). A reproducible capture in that extension is not proof that a depth barrier was respected by the original swept-contact solver.

## Food, births or predators are missing

Only edible Python ferns are resources; most vegetation is ornamental. Barren normally has zero food. Continuous regrowth is finite. Seasonal scarcity can prevent eligible reproduction.

Wolves appear in **Predator & prey**, not every mode. Its founders include predators in the total count and its replacement birth counts are fixed. Real overlapping births and juvenile visuals belong to **Continuous ecosystem**, not ordinary generational replacement.

Continuous births require maturity, cooldown, adequate parent energy, affordable offspring, space and cap capacity. They are not guaranteed. The [lifecycle preset](../configs/animation_lifecycle.json) improves opportunity through explicit demonstration settings; it does not override biology. Total extinction can be a valid experiment outcome.

## A configuration is rejected or a change does nothing

Edit pending settings, then **Start new population**. Selecting a preset only loads a draft. Read the Python error: mode/controller compatibility, social divisibility, seasonal stock and exact-tick durations are common causes.

Use `null` for default stock; JSON booleans are `true`/`false`, not quoted strings. Do not mix HabitatConfig fields into RunConfig. V2 has no `--algorithm` app flag; use JSON. With `--config`, put mode/layout inside that file rather than relying on extra convenience overrides. [Full reference](CONFIGURATION.md) lists fields and placement rules.

## Export or shutdown fails

Check the destination and available disk space. Exports need a writable output root and publish a unique child directory. Resolve the status error while the old run remains available/paused; do not force replacement to hide an archive failure.

Capture/profile parent directories must exist. A headless run has no native screenshot. Source CLI exports default to root `exports/`; V2 exports use application-support `python-runs/`. `report.html` needs its sibling files.

## Verification or replay fails

Keep the complete bundle. A failed checksum can mean a missing/edited file; a numerical mismatch can mean different source/runtime/settings. Configuration reload creates fresh founders, not a restored run.

Use original `simulator.py` for original-rule replay and `v2/backend/habitat.py` for physical replay. Physical source hashes must match exactly. The root structural verifier alone does not establish the physical numerical model. Follow the [copyable examples](EXPORTS_AND_REPLAY.md) before interpreting a failure.

## A study or advanced brain viewer is unavailable

V2's Research button is not V1's background study catalog. Open the original interface or use `simulator.py --catalog` / `--study`. Saved-model studies need the original research inputs; they are not bundled into the standalone desktop engine. [Research guide](RESEARCH_AND_VALIDATION.md#preserved-study-catalog) lists dependencies and entry points.

## A useful issue report

Include the Git commit or installed archive hash, Mac chip/OS, launch route, mode/controller/environment/seed, original versus physical rules, quality/window size, expected/observed behavior and relevant error output. For a model issue, attach a reproducible configuration and bundle when appropriate. Keep endpoint tokens and private local paths out of public logs.

For visual issues, a screenshot plus 1× reproduction helps distinguish interpolation/animation from Python state. For scientific claims, use source data, matched conditions and independent seeds rather than a screen recording alone.
