# Configuration and command-line reference

[Documentation](README.md) · [User guide](USER_GUIDE.md) · [Modes](SIMULATION_MODES.md) · [Examples](examples/README.md)

Three independent settings layers exist: original Python **RunConfig**, optional V2 **HabitatConfig**, and Godot **presentation/connection** options. Do not insert visual weather fields or habitat fields into RunConfig: Python rejects unknown keys.

## Apply settings in the interface

| Action | Effect |
| --- | --- |
| Change sidebar values | Updates a draft; does not mutate the live model |
| Select a preset in Run settings | Loads that original Python configuration into the draft |
| **Load configuration** | Python validates a JSON file, then loads its draft |
| **Start new population** | Applies draft plus **Physical habitat** checkbox; normally archives the previous run |
| **Apply JSON configuration** | Immediately configures the edited original RunConfig; currently does not forward habitat options |
| Pause, speed, automatic reproduction | Live semantic controls recorded at physics ticks |
| Weather, camera, quality, scenery motion | Presentation changes, not RunConfig |

For physical JSON experiments, load/validate the draft, enable the checkbox, then **Start new population**. Alternatively use `--config=… --habitat` or `--habitat-config=…`. The direct JSON button starts an original-rule run even if a physical checkbox was previously checked.

## RunConfig schema

The authoritative schema is [`research_session.RunConfig`](../../research_session.py). Missing fields take the defaults below; unknown fields fail validation. Use valid mode/algorithm combinations rather than changing `mode` alone in a partial JSON file.

### Identity, layout and budget

| Field | Default | Meaning and constraint |
| --- | --- | --- |
| `schema_version` | `1` | Integer exactly 1 |
| `mode` | `"foraging"` | One of seven [mode IDs](SIMULATION_MODES.md#mode-and-controller-matrix) |
| `environment` | `"uniform"` | Allowed layout for that mode |
| `algorithm` | `"selection"` | Allowed controller/reproduction policy for that mode |
| `seed` | `2801` | Integer `0 <= seed < 2^63`; transmitted without float rounding |
| `population` | `100` | Positive integer, at most 300 founders; includes predators when applicable |
| `food_count` | `null` | Default layout stock; explicit integer 0–500; must stay null for Seasons |
| `generations` | `5` | Positive synchronized-generation limit; not the continuous horizon |
| `duration` | `600.0` | Positive continuous horizon in simulated seconds |
| `sample_interval` | `1.0` | Positive simulated seconds between samples |

`duration`, `episode_seconds` and `sample_interval` must be exact whole numbers of `1/60 s` ticks. The engine validates this with finite-number checks and tick tolerance. The sidebar caps its generation widget at 1000; the Python schema requires positivity rather than that UI maximum.

### Neural and physical inheritance

| Field | Default | Applies to |
| --- | --- | --- |
| `mutation_rate` | `0.1` | Neural scalar mutation probability, finite [0, 1] |
| `mutation_scale` | `0.1` | Neural Gaussian scale, finite ≥0 |
| `fixed_speed` | `60.0` | Positive px/s for fixed-speed foraging/seasons/obstacles |
| `body_mutation_rate` | `0.25` | Body-trait probability, finite [0, 1] |
| `body_mutation_scale` | `0.08` | Body-trait log-space scale, finite ≥0 |

Trait, predator and continuous models use inherited cruise speed rather than `fixed_speed`. Social sessions force body mutation rate/scale to zero. Continuous clonal sessions force neural/body mutation probabilities to zero. Unused fields can remain in a complete exported config but do not create extra features in an incompatible mode.

The sidebar mutation-scale widget tops out at 10; raw Python JSON permits finite nonnegative scales. Keep values within the intended experiment's protocol. Large mutation is not an optimization guarantee.

### Continuous ecosystem

| Field | Default | Constraint / meaning |
| --- | --- | --- |
| `population_cap` | `300` | Positive integer ≤1000, at least founder count |
| `regrowth_rate` | `30.0` | Finite nonnegative food units/s up to stock capacity |
| `maturity_age` | `15.0` | Positive minimum birth age in seconds |
| `birth_cooldown` | `20.0` | Positive seconds between eligible attempts |

Births also require parent energy, reserve, affordable candidate size and free placement. Setting a large cap does not make an ecosystem sustainable. [Continuous rules](SIMULATION_MODES.md#continuous-ecosystem) explain funded versus clonal reproduction.

### Seasons

| Field | Default | Constraint / meaning |
| --- | --- | --- |
| `season_length` | `1` | Positive integer generations per season |
| `season_food` | `[150, 200, 75, 25]` | Four integer stocks 0–500, spring through winter |
| `cluster_shift` | `120.0` | Finite nonnegative cluster-shift scale in px |
| `reproductive_age` | `60.0` | Positive eligibility age for seasonal parents |

Use `environment="seasonal"` and `food_count=null`. No eligible parent is a valid extinction result.

### Predator and social episodes

| Field | Default | Constraint / meaning |
| --- | --- | --- |
| `predators` | `20` | Positive integer; smaller than total population in predator–prey |
| `episode_seconds` | `60.0` | Positive exact-tick episode length for predator/social cohorts |
| `groups` | `10` | Positive integer; social needs ≥2 equal groups, ≥2 agents per group |
| `food_access` | `"restricted"` | Social `"restricted"` or `"open"` |
| `signaling` | `true` | Strict JSON boolean: social production/cost switch |
| `sharing` | `true` | Strict JSON boolean: social energy-transfer switch |
| `signals_hidden` | `false` | Hide received-signal inputs while retaining source behavior |
| `risk_sensors` | `"intact"` | Obstacles `"intact"` or `"hidden"` |
| `prey_sensors` | `"intact"` | Prey opponent channels intact/hidden |
| `predator_sensors` | `"intact"` | Predator opponent channels intact/hidden |

Social founders and food stock must divide evenly by groups. Clustered/wide-clustered food is unavailable there, and group cells must meet the original minimum dimensions. Python world construction performs further mode-specific validity/placement checks before replacement.

## Presets and small examples

The Run settings preset menu reads original [`configs/`](../../configs): `foraging`, `neutral`, `greedy_sparse`, `seasons`, `obstacles`, `traits`, `predator_prey`, `social`, `continuous`. These files remain unchanged.

V2 also includes the explicit [lifecycle demonstration](../configs/animation_lifecycle.json), separate [physical options](../configs/physical_habitat.json), and [documentation examples](examples/README.md). Documentation JSON files are source examples; they are not added to the original preset menu or packaged engine presets.

```json
{
  "schema_version": 1,
  "mode": "foraging",
  "environment": "uniform",
  "algorithm": "selection",
  "seed": 2801,
  "population": 30,
  "food_count": 90,
  "generations": 3,
  "fixed_speed": 60.0,
  "mutation_rate": 0.1,
  "mutation_scale": 0.1
}
```

This is [examples/foraging.json](examples/foraging.json). `config.json` reloads settings with fresh founders. It is not a savegame or imported neural population.

## Physical HabitatConfig

This separate dictionary is passed as `habitat` to bridge configuration, or loaded with `--habitat-config=`. The authoritative schema is [`v2/backend/habitat.py`](../backend/habitat.py).

| Field | Default | Supported validation |
| --- | --- | --- |
| `enabled` | `false` | Strict boolean; `--habitat` sends true |
| `version` | `"physical_habitat_v1"` | Exact version string |
| `grid_spacing` | `1.0` | Fixed at 1 for this version |
| `water_level` | `-0.2` | Fixed at −0.2 |
| `max_water_depth` | `0.75` | Finite positive, ≤2 |
| `max_slope` | `0.9` | Finite positive grade, ≤2 |
| `uphill_cost` | `2.0` | Finite positive, ≤20 |
| `wading_cost` | `2.5` | Finite positive, ≤20 |
| `weather_period` | `40.0` | Finite seconds, ≥1 |
| `day_seconds` | `240.0` | Finite seconds, ≥1 |

The supplied physical preset explicitly enables the extension. An exported `habitat.json` wrapper is accepted by the launcher: it extracts its `config` dictionary. A malformed file or unknown field fails configuration; it does not silently downgrade to the original engine.

Use [physical rules and limits](PHYSICAL_HABITAT.md), including the difference between source climate and decorative overrides. Food rejection/safe spawn can change random draws and outcomes; use separate physical comparisons.

## Application command line

The source launcher passes Godot arguments before `--` and app flags after it. Prefer `--name=value` for the application fields below.

| Flag | Behavior |
| --- | --- |
| `--config=/absolute/config.json` | Load original RunConfig; can combine with habitat flags |
| `--mode=ID` | Select one of seven modes and its first valid policy |
| `--environment=ID` | Select a valid food layout; `hazards`/`seasons` are also legacy mode shortcuts |
| `--habitat` | Enable default physical rules |
| `--habitat-config=/absolute/file.json` | Enable physical option loading; file controls actual `enabled` value |
| `--immersive` | Landscape HUD |
| `--workbench` | Start in research workbench |
| `--ground-view` | Initial low camera after configuration |
| `--valley-view` | Initial valley framing |
| `--quality=0`, `1`, `2` | Performance, Balanced, Lush; value clamped to this range |
| `--ecosystem-panel` | Show Ecosystem drawer on launch |
| `--visual-weather=VALUE` | `auto`, `clear`, `cloudy`, `rain`, `fog`, `snow` |
| `--visual-season=VALUE` | `auto`, `spring`, `summer`, `autumn`, `winter` |
| `--visual-hour=NUMBER` | Decorative hour, wrapped over 24 hours |
| `--visual-cycle=off` | Disable automatic visual/Python-follow hour selection |
| `--frames=N` | Bounded display-frame run; not a fixed scientific tick budget |
| `--screenshot=/absolute/image.png` | Save at bounded-run completion; native rendering required |
| `--export=/absolute/output-root` | Export at bounded-run completion |
| `--profile=/absolute/profile.json` | Frame diagnostics for bounded runs after 90 warmup frames |
| `--no-auto-save` | Disposable testing: bypass automatic replacement/shutdown archives; explicit export still works |
| `--engine-root=/absolute/root` | Explicit development engine path |
| `--python=/absolute/python` | Explicit interpreter path |

With `--config`, mode/environment convenience overrides are not additionally applied by the current startup branch. Put the desired model in the JSON. There are no V2 `--population`, `--algorithm`, `--seed`, `--ticks`, `--replay`, `--workers` or `--study` app flags: use RunConfig, the fixed-tick Python examples, or V1's separate CLI as appropriate. Unknown app flags are not a schema-validated experiment API.

Create capture/profile directories first. The output root receives a uniquely named `run-*` child, not files directly at its top level:

```bash
mkdir -p /tmp/ae2-documentation-capture
./"v2/Run Artificial Evolution 2.command" -- --immersive --mode=obstacles \
  --frames=180 --screenshot=/tmp/ae2-documentation-capture/world.png \
  --profile=/tmp/ae2-documentation-capture/profile.json \
  --export=/tmp/ae2-documentation-capture/runs --no-auto-save
```

Frame timings from `--headless` are not GPU performance evidence. Use native rendering for the 60 FPS target. A bounded frame run simulates a wall-time-dependent number of ticks; exported replay records its actual tick horizon.

## Godot options and installed launches

```bash
# Source: Godot arguments, delimiter, application arguments:
./"v2/Run Artificial Evolution 2.command" --resolution 1160x760 -- \
  --immersive --mode=traits

# Finder/installed helper adds the delimiter itself:
./"v2/Launch 3D Application.command" --mode=traits --quality=0

# Direct installed binary: explicit delimiter for app options:
"$HOME/Applications/Artificial Evolution 2.0.app/Contents/MacOS/Artificial Evolution 2.0" \
  -- --mode=traits --quality=0
```

Compatibility fallback engine options must precede the delimiter:

```bash
"$HOME/Applications/Artificial Evolution 2.0.app/Contents/MacOS/Artificial Evolution 2.0" \
  --rendering-method gl_compatibility --rendering-driver opengl3 -- --quality=0
```

Release templates do not expose the editor's `--script`; use the source Godot executable for tool/test scripts. [Development](DEVELOPMENT.md) explains how native UI-pack tests instrument the exported resources.

## Environment variables and persistence

| Variable / file | Purpose |
| --- | --- |
| `GODOT_BIN` | Source-launcher Godot executable override |
| `BLENDER_BIN` | Supported shell authoring launcher/generator override |
| `AE_ENGINE_ROOT` | Explicit root containing `research_session.py` and presets |
| `AE_PYTHON` | Source/test interpreter and explicit bridge override |
| `user://engine.json` | Remembered development connection paths |

Explicit CLI connection paths override discovered/settings paths. Packaged discovery normally prefers its embedded engine, and packaged launches do not replace saved development paths. Cosmetic choices and camera state are not a documented persistent preferences store. Save a RunConfig plus exported run rather than assuming the next launch restores the current population.
