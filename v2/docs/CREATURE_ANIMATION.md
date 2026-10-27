# Event-driven skeletal animation

[Documentation](README.md) · [User guide](USER_GUIDE.md) · [Development](DEVELOPMENT.md)

Godot now displays walking, running, turning, feeding, resting, pursuit, escape, reproduction, juvenile growth and death using the deer/wolf skeletal rigs. Python remains the only source of movement, meals, reproduction, survival and interactions. The original 2D simulator and numerical models are unchanged.

## What drives each animation

| Display | Required Python evidence |
| --- | --- |
| Walk / run | Received XZ displacement per simulated second; gait phase follows travelled distance and displayed body scale. |
| Turn left / right | Shortest-angle changes in received headings; an upper-body turn layer blends over the current gait. |
| Eating | A real increase in `food_eaten`. Nearby food alone never triggers it. Head/neck feeding blends over the gait; Python creatures are not forced to stop. |
| Resting | Observed near-zero movement **and** near-zero Python speed. Pausing a moving animal freezes its current pose instead of inventing rest. |
| Hunting | Predator movement recorded by Python as toward a visible opponent; a successful capture also triggers a brief confirmed-capture response. |
| Escaping | Prey movement recorded by Python as away from a visible opponent. Mere proximity is insufficient. |
| Reproducing | A real continuous-mode birth ledger entry linked to its parent, which was alive at birth. It uses a brief upper-body brace, not a mating or gestation sequence. If the parent also dies between snapshots, death takes priority. |
| Growing | A real continuous-mode offspring's recorded age relative to the configured maturity age. Its visual size eases from 65% to adult size. Founders and synchronized replacement cohorts start at adult visual size. |
| Dying | A confirmed `alive == False` observation, retaining Python's cause, final position and radius. Alive cohort retirement never plays death. |

Pursuit/escape are descriptive movement labels; they do not establish what the neural controller intended or understood. Visual maturation is an age-based artistic representation: the engine creates newborns with their complete collision radius and has no physical growth law. The original radius, costs and sensors remain authoritative. The existing reproduction model is clonal or generational copying, so no sexual behavior was invented.

## Smooth movement and poses

The Blender rigs contain eleven actions: `Rest`, `Walk`, `Run`, `TurnLeft`, `TurnRight`, `Eat`, `Hunt`, `Escape`, `Reproduce`, `Grow` and `Die`. The deer retain source gallop, feeding and collapse actions; additional walking and contextual actions were authored on the existing rigs. All are in place. The animal's world transform continues to come from Python's interpolated pose.

Locomotion changes crossfade over 0.22 seconds. Feeding/reproduction and turning use smooth upper-body layers, preserving the actual leg movement. Death blends from the preceding gait into a full-body collapse. Pausing or losing the connection freezes animation advancement.

Stride lengths were calibrated from the rig's low-foot contact motion, rather than assigning an arbitrary looping playback speed. Distance-driven phases and scale-aware strides reduce foot sliding, including during age-based visual growth. Sharp Python boundary reflections, accelerated simulation, uneven ground and transitions can still show residual foot slip: nearby terrain foot IK is now applied as described in [Physical habitat](PHYSICAL_HABITAT.md). Root-motion locomotion still does not replace Python's trajectory.

Selected and nearby animals use actual `Skeleton3D` poses with transform/quaternion interpolation. Performance/Balanced/Lush evaluate detailed poses for up to 2/4/6 nearby animals plus the selection. Other animals use their mesh's original bone indices and weights with shared GPU bone matrices from the same skeletal clips. They are skeletally skinned, not static meshes sliding along paths. This avoids evaluating a separate full animation track tree for every animal. The distant GPU path blends sampled bone matrices; the nearby path interpolates local bone transforms. Tests compare GPU and `Skeleton3D` skin matrices at matching samples.

Dead models are removed from the active collection immediately after the confirmed event reaches the delayed display. A separate, noninteractive remnant plays collapse and fades after three presentation seconds. It has no food, energy, sensing or collision effects. Surviving cohort replacements simply retire. Unexplained removals never manufacture a death.

## Reliable observations

`v2/backend/engine_bridge.py` reads the original session's birth ledger, creature counters, death status and directional telemetry. It does not run extra decisions, consume random numbers or alter scientific objects. Numbered receipts record births, meals, captures, reproduction, deaths and retirement. A bounded 4,096-event journal and client acknowledgements retain events across superseded display frames. Godot deduplicates them and delays delivery to match its existing interpolation buffer.

Initial connections do not replay historical actions. New runs clear pending events. A journal gap is recorded rather than filled with fabricated events. Counter receipts aggregate increases observed between snapshots; their timestamp and position describe observation, not a newly recorded exact food-contact instant. Source physics and exported research records retain their original timing and meaning.

The specimen panel shows the current display activity. Its label describes the presentation, rather than adding a new brain state to Python.

## Run and observe

```bash
./"v2/Run Artificial Evolution 2.command"
```

Use **V** → **Ground view**, left-click an animal, and press **F** to follow. **Predator & prey** exposes pursuit, retreat and confirmed captures. **Continuous ecosystem** exposes real funded births, juvenile appearances and reproduction. Whether these events occur still depends on the original simulation.

A short continuous-mode demonstration preset is included to make lifecycle events easier to observe:

```bash
./"v2/Run Artificial Evolution 2.command" -- --immersive --ground-view \
  --config="$(pwd)/v2/configs/animation_lifecycle.json"
```

It uses 24 founders, abundant food, a 2-second maturity threshold and a population cap of 60. These are explicit demonstration conditions, not a new scientific result or a change to defaults. Existing research results and presets remain untouched.

## Author, test and reproduce

The editable skeletal rigs are `v2/art_source/animation/{doe,stag,wolf}.blend`. All animal art and derived animations remain [CC0](../assets/animals/LICENSE.md); scripts are MIT licensed.

```bash
# Restore pinned original animal sources if needed:
python3 v2/tools/fetch_animal_assets.py

# Rebuild skeletal actions, import and compile shared bone-pose resources:
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup \
  --python v2/tools/prepare_animation_rigs.py
./"v2/Run Artificial Evolution 2.command" --headless --editor --import
./"v2/Run Artificial Evolution 2.command" --headless --script tools/bake_skeletal_poses.gd
./"v2/Run Artificial Evolution 2.command" --headless --editor --import

# Regressions and actual signed-package validation:
./v2/tools/test.sh
./.venv/bin/python -m unittest discover -v
python3 v2/tools/verify_original.py --all-existing
./v2/tools/build_macos.sh
./.venv/bin/python v2/tools/validate_macos.py
./.venv/bin/python v2/tools/validate_animation_macos.py
```

Preserve hand edits before regenerating rigs. Bone palette `.exr.import` settings must remain linear, lossless and without mipmaps; optimized shadow meshes are disabled so GPU bone attributes are retained. Regeneration intentionally changes asset hashes: review the changes and update `ASSET_SOURCES.json` before using the checksum verifier.

For isolated authoring review, `tools/animal_gallery.gd` accepts `--clip=Walk`, `--clip=Eat`, or `--clip=Die --phase=1`, plus an absolute `--screenshot=` path. This authoring scene is not evidence of simulated behavior. Actual event and authority tests, package records and measured timings are in [animation-validation](animation-validation/README.md).
