# Terrain contact, 60 FPS and physical habitats

The Apple Silicon desktop build now uses Godot's native Metal Mobile renderer, batches distant animated animals and applies terrain foot IK to nearby detailed skeletons. An **opt-in Python physical habitat** adds traversable terrain, a river inside the arena, wading, bank collisions and climate costs. The original Python files and original 2D application remain unchanged.

![Physical habitat](screenshots/habitat-physical-foraging.png)

## Use it

Open **Artificial Evolution 2.0** in `~/Applications`. Its default research rules are still the original engine's rules. To run the new physics, choose **Research → Physical habitat (v2 rules) → Start new population**. This creates a fresh, explicitly different experiment; normal archive-before-replacement behavior still applies.

From the repository:

```bash
# Installed standalone app, new physical habitat run:
./"v2/Launch 3D Application.command" --habitat

# Source application:
./"v2/Run Artificial Evolution 2.command" -- --habitat --immersive --ground-view

# Original 2D application, independently:
./"v2/Run Original Simulator.command"
```

The HUD identifies **PHYSICAL HABITAT** and the source weather. The inspector in **Research** shows wading depth, additional habitat energy and terrain contacts. **Ecosystem** identifies the Python climate separately from decorative overrides. Auto weather and daylight follow simulated time, including pause and speed changes. Manual weather, hour and color overrides remain visual and do not alter that source climate or its costs.

To customize a physical run, use `--habitat-config=/absolute/file.json`, with the separate schema shown in [physical_habitat.json](../configs/physical_habitat.json). The original RunConfig JSON stays unchanged. Exported `habitat.json` is also accepted as a source of these settings. Invalid settings are rejected before replacing the current run.

## Performance

The previous desktop audit measured about **41.8 FPS** at Balanced quality on this Apple M3 using Compatibility/OpenGL. The current signed-package audit measured **60 FPS** across three 100-founder seeds, using full-resolution Balanced rendering at 1520 × 960. Its measured 95th-percentile wall-clock frame times were about **17.2 ms**. Physical foraging, predator–prey and continuous runs also met the measured target. See the [complete audit](habitat-validation/README.md).

The app uses the [Mobile renderer with native Metal](https://docs.godotengine.org/en/stable/tutorials/rendering/renderers.html) on this Mac. Godot supports this renderer on [macOS 13+ with Metal 3](https://docs.godotengine.org/en/stable/about/system_requirements.html); this build is arm64. Timings are local measurements, not a guarantee for every device, quality profile, population cap or background workload.

Distant living animals share per-model/anatomical-part draw batches and a small floating-point pose-state texture. They retain their original bone weights, animation phases, blends, coats and source identities. Selected/nearby animals leave those batches for individual Skeleton3D poses and foot IK. Confirmed deaths leave living batches before the original collapse/fade animation. Stationary pose/food caching, distance-based shadows and existing vegetation budgets remain in use.

Metal water uses sky reflections. The old static reflection probe is retained only by the Compatibility fallback; removing its unused Metal capture also eliminated its shutdown texture-allocation warnings. FPS profiles now use **monotonic wall-clock intervals**, exclude the first 90 warmup frames, and stop recording before pause/capture/export. Raw intervals, p95/p99, late-frame fraction and draw-call diagnostics are retained; smoothed engine delta is not used to claim 60 FPS.

The OpenGL fallback is available, but measured about **40 FPS**, below the target:

```bash
"$HOME/Applications/Artificial Evolution 2.0.app/Contents/MacOS/Artificial Evolution 2.0" \
  --rendering-method gl_compatibility --rendering-driver opengl3
```

## Foot contact

Nearby deer, stags and wolves use explicit four-leg, two-bone IK chains. The solver starts from the existing skeletal clip pose, samples the displayed triangle surface, plants low stance feet, releases swing feet and limits reach to the original anatomical lengths. Wolf ankle/foot offsets and animated hoof/paw orientation are preserved. Stance anchors reduce sliding; sharp motion can release an unreachable anchor instead of stretching the anatomy.

Terrain contact queries use the rendered triangles rather than a different procedural height approximation. The physical heightfield is shared with Python and rendered on an aligned half-metre mesh; Python and Godot use the same piecewise-linear interpolation. Nearby detailed poses update at up to 60 Hz. Distant animals keep the cheaper shared skeletal deformation without per-foot CPU IK.

The solver changes **visual bone poses**, not Python XZ positions, movement, fitness, food or decisions. Three-rig reachable-slope tests measured a worst target residual of **1.45 cm**. Native endpoint samples included residuals up to about **4.4 cm** where reach is constrained. This is not a guarantee of perfect contact on every slope: abrupt reflections, accelerated simulation, swing transitions and finite leg reach can still leave residual slip or separation. No root-motion locomotion, whole-body rigid-body simulation or anatomical stretching is introduced.

The [before](screenshots/habitat-feet-before.png) / [after](screenshots/habitat-feet-after.png) pictures are an explicitly synthetic geometry fixture, not a scientific simulation run. Reproduce with `./"v2/Run Artificial Evolution 2.command" --script tools/foot_ik_gallery.gd`.

## What becomes physical?

| Feature | Original research mode | Opt-in physical habitat |
| --- | --- | --- |
| Terrain height | Display surface only | Seeded heightfield affects movement, uphill work and steep-bank collisions |
| Arena river | Decorative river outside the arena | Additional river/ford inside the arena; shallow wading slows motion and costs energy; excessive depth blocks travel |
| Food | Original placement and regrowth | Original distribution/regrowth with wet placement rejected; current food is still the original Food objects |
| Weather/daylight | Decorative | Deterministic simulated climate affects traction and metabolic cost; auto visuals follow it |
| Decisions/evolution | Existing Python controllers and reproduction | Same controllers, sensory dimensions, selection and mutation, operating under explicitly changed movement/cost rules |
| Export/replay | Original simulator replay | Versioned habitat sidecar, physical telemetry and separate v2 replay |

This is a **2.5D ecological extension**, not unrestricted 3D rigid-body physics. Animals retain horizontal trajectories in the original engine. Height and water affect those trajectories and energy through a v2 mixin inside the original survival/move calls, before original food/capture resolution. Godot never sends corrected creature poses back to Python. Ornamental trees, distant mountains and outside-arena water remain scenery; no tree collisions, currents, swimming controller, dynamic water levels or weather-driven plant growth are claimed.

The original neural-input dimensions are retained. No new terrain-specific sensory channels or learned avoidance strategy is asserted. Different behavior must be evaluated through matched training and repeated trials; changed physics alone is not evidence of intelligence.

## Recorded rules

The deterministic surface uses a one-metre grid, seed-specific meadow/hill relief and a river with a crossing. Water level is −0.2 m. Default blocked limits are water depth above 0.75 m or grade above 0.9. Contact restores the preceding valid horizontal position and reflects heading against the local surface gradient. Inaccessible birth positions are moved to a deterministic nearby safe location within the original arena/group bounds.

For depth `d`, grade vector `g`, and commanded speed `v` in metres per simulated second:

- Movement factor: `traction / (sqrt(1 + |g|²) * (1 + 2.5*d))`.
- Traction: clear `1`, rain `0.9`, snow `0.78`.
- Additional uphill power: `2 * max(0, dot(g, heading)) * abs(v)`.
- Additional wading power: `2.5 * d`.
- Precipitation power: clear `0`, rain `0.35`, snow `0.8`; night adds up to `0.25`.

These are explicit stylized energy units, not measured animal physiology. The original metabolic costs remain in force. Uphill power represents commanded work; `habitat.telemetry.metres` records actual travel, while the original speed telemetry retains its commanded-speed meaning. Water exposure, added energy and blocked contacts are recorded per individual.

Defaults use a 240-simulated-second day and 40-second weather stages. Clear/wet stages alternate; precipitation is snow in winter and rain otherwise. Habitat seasons advance every three stages; the original seasonal mode instead supplies its own generation-based season and food schedule. These virtual time scales are experimental controls, not an Earth-climate model.

## Export and replay

Physical exports contain the original numerical datasets plus `habitat.json`, `habitat_telemetry.csv`, an explicit `engine_extension` manifest marker and a source-code hash. Their HTML report identifies the physical rules and correct replay command. They do **not** use the unchanged original replay as an equivalent numerical model.

```bash
# Original exports:
./.venv/bin/python simulator.py --verify-bundle /path/to/original-bundle
./.venv/bin/python simulator.py --replay /path/to/original-bundle/run.json --headless

# Physical exports, using the corresponding v2 source version:
./.venv/bin/python v2/backend/habitat.py --verify-bundle /path/to/physical-bundle
./.venv/bin/python v2/backend/habitat.py --replay /path/to/physical-bundle/run.json
```

Without the checkout, use the same helper bundled in the app:

```bash
AE2_APP="$HOME/Applications/Artificial Evolution 2.0.app"
"$AE2_APP/Contents/Resources/python/bin/python3" -E -s -B \
  "$AE2_APP/Contents/Resources/engine/v2/backend/habitat.py" \
  --verify-bundle /path/to/physical-bundle
```

Replay checks source version, physical configuration, climate, complete individual telemetry and original scientific outputs. Camera/IK changes and decorative overrides are not scientific events. Published original results remain unchanged; compare new physical results only under matched habitat, seeds, controller budgets and training/test conditions. In particular, physical social demes can have different terrain and require appropriate experimental controls.
