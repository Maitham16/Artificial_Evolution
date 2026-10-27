# Artificial Evolution 2.0 documentation

[V2 overview](../README.md) · [Original V1 README](../../README.md) · [Original V1 user guide](../../docs/USER_GUIDE.md)

These guides describe the Python-backed Godot application in `v2/`. Commands assume the **repository root**, unless a guide describes the installed app. Paths containing spaces are quoted. V1 documentation, scientific results and numerical code remain independently available.

## Start here

| Your task | Guide |
| --- | --- |
| Install, find the icon and launch either version | [Installation](INSTALLATION.md) |
| Learn cameras, inspection, panels and experiment controls | [User guide](USER_GUIDE.md) |
| Choose a model, controller or reproduction regime | [Simulation modes](SIMULATION_MODES.md) |
| Understand senses, neural decisions, selection and mutation | [Evolution and brains](EVOLUTION_AND_BRAINS.md) |
| Understand deer, wolves, animation and foot contact | [Animals and animation](ANIMALS_AND_ANIMATION.md) |
| Choose food layouts, scenery, seasons and weather | [Environments](ENVIRONMENTS.md) |
| Enable actual terrain, river and climate costs | [Physical habitat](PHYSICAL_HABITAT.md) |
| Find configuration fields and application CLI flags | [Configuration](CONFIGURATION.md) |
| Export, verify, replay and interpret datasets | [Export and replay](EXPORTS_AND_REPLAY.md) |
| Interpret fitness, ancestry and research evidence | [Research and validation](RESEARCH_AND_VALIDATION.md) |
| Understand source ownership and process boundaries | [Architecture](ARCHITECTURE.md) |
| Edit assets, test, build and install | [Development](DEVELOPMENT.md) |
| Diagnose startup, input, rendering or replay | [Troubleshooting](TROUBLESHOOTING.md) |
| Inspect review scope and implementation findings | [Repository review](REPOSITORY_REVIEW.md) |

For a first session: **Installation → User guide → Simulation modes → Export and replay**. For contributions: **Architecture → Configuration → Development**. For research: **Evolution and brains → Research and validation → V1 protocols**.

## Detailed implementation references

| Topic | Reference | Scope |
| --- | --- | --- |
| Desktop packaging/cameras | [Desktop application](DESKTOP_APP.md) | Current desktop implementation |
| Runtime provenance | [Bundled runtime](BUNDLED_RUNTIME.md) | Embedded Python, locks, signatures and caches |
| TCP/interpolation | [Python bridge](PYTHON_BRIDGE.md) | Local protocol and recovery |
| Meshes and source assets | [Animal models](ANIMAL_MODELS.md) | Runtime models and earlier art pipeline |
| Actions and event evidence | [Creature animation](CREATURE_ANIMATION.md) | Eleven clips, layers and receipt semantics |
| Landscape assets/budgets | [Natural world](NATURAL_WORLD.md) | Scenery; physical rules are separate |
| Event drawer and food identities | [Interactive ecosystem](INTERACTIVE_ECOSYSTEM.md) | Confirmed observations and cosmetic controls |

The user guides describe current use; these references retain implementation detail. Historical audits identify the build they measured. A new audit does not retroactively update an old archive's hash or benchmark.

## Engineering record

| Record | What it establishes |
| --- | --- |
| [Panel input](panel-input-validation/README.md) | Pointer routing, 284 V2 tests/checks, native UI-pack and installed launch |
| [Metal, foot IK and habitat](habitat-validation/README.md) | Repeated local timing, 13 native cases, original preservation, physical replay |
| [Standalone desktop](desktop-validation/README.md) | Embedded runtime, 2D independence, hashes/signatures and earlier timings |
| [Interactive ecosystem](ecosystem-validation/README.md) | Food/event observation and scenery integration |
| [Skeletal animation](animation-validation/README.md) | Rig/pose and lifecycle integration |
| [Animals](animal-validation/README.md) | Earlier animal renderer, art and licenses |
| [Nature](nature-validation/README.md) | Earlier landscape measurements and assets |
| [Python bridge](bridge-validation/README.md) | Engine parity, transport and source preservation |
| [Initial prototype](validation/README.md) | Historical independent Godot prototype, superseded by Python integration |
| [Initial inspection](INSPECTION.md) | Historical inventory and initial isolation design |

## Relationship to V1

V2 uses V1's `ResearchSession` and seven ecological models. It does not replace the root application, rewrite its numerical engine in Godot or change published protocols. Physical habitat is an explicitly different extension under `v2/`.

The V2 **Research** button opens its workbench. V1's background study catalog, full Step 13–27 jobs and historical brain-analysis tools remain in the [original interface](../../docs/USER_GUIDE.md#run-the-research-studies) and CLI. V2 has no generic saved-genome import or V2 replay viewer. Original-rule exports can be numerically replayed and opened paused in V1; physical exports use the V2 helper.

The scientific conclusion remains bounded: evolved adaptive behavior under specified conditions, with documented baselines and failures. Realistic animal art and persistent lineages do not establish general intelligence.
