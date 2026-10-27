# Repository and documentation review

[Documentation](README.md) · [Architecture](ARCHITECTURE.md) · [Research evidence](RESEARCH_AND_VALIDATION.md)

This review documents the implemented Python-backed V2 application at base commit `342438f6ea5e1beb99c245dbe4f0d49309e63389`. It is a documentation change, not a new simulation step, numerical repair, release publication or independent repetition of the research studies.

## Scope and method

The base inventory contains **1,154 tracked files**: 591 outside V2 and 563 inside it. Outside V2 are 90 root files, nine presets, four V1 guides, one CI workflow, one export placeholder and 486 result artifacts. The prior [initial inspection](INSPECTION.md) and its immutable inventory remain available.

The review indexed all tracked paths and examined original README/V1 guide organization, current source boundaries, settings and model factories, Godot UI/actions/CLI, session/export/replay, physical extension, art/runtime manifests, launch/build/install tools, tests and audit records. It used the existing Graphify map as navigation and checked claims against current source. The map describes earlier Python sources and is not treated as an up-to-date V2 execution trace.

The structural scan parsed **120 Python files**, indexed **25 GDScript files**, decoded **184 JSON files and 48 compressed JSON records**, read **47 CSV headers**, and indexed **182 numeric archive containers**. It indexed the 28 tracked Markdown files present at the base revision. It did not manually inspect every numeric array element, inspect binary artwork as source text, or rerun the full historical training protocols.

The [machine-readable inventory](documentation-validation/review-inventory.json) records those counts and no scan errors. Animal/nature manifests independently verified 50 and 41 runtime/authoring files. Original tracked hashes and pre-existing unrelated import edits were preserved during this documentation work.

## Findings incorporated into the guides

| Source-backed finding | Documentation treatment |
| --- | --- |
| V2 now uses the original Python engine; the initial independent Godot model was removed | Current [architecture](ARCHITECTURE.md); initial report labeled historical |
| All seven modes are exposed, but the V1 study-job catalog is not a V2 panel | Distinguish workbench **Research** from the [original study launcher](RESEARCH_AND_VALIDATION.md#preserved-study-catalog) |
| Physical habitat changes biological outcomes and has separate source-hash replay | [Rules](PHYSICAL_HABITAT.md), [settings](CONFIGURATION.md) and [replay](EXPORTS_AND_REPLAY.md) explicitly separate it |
| `_apply_json` does not forward habitat options | Use draft loading plus **Start new population**, or CLI `--config` with habitat options |
| `Open Blender Models.command` / `rebuild_assets.sh` target prototype art | [Current authoring](DEVELOPMENT.md#asset-authoring) uses explicit `art_source/animation/` rigs |
| App metadata declares macOS 13; pinned NumPy wheel targets macOS 14 | [Compatibility](INSTALLATION.md#requirements-and-compatibility) distinguishes declaration, dependency floor and tested OS |
| Original report `app_version` remains 1.0.1 while Godot app metadata is 2.0.0 | Explain engine/viewer versions in [exports](EXPORTS_AND_REPLAY.md#bundle-contents) |
| Native Metal uses sky water reflections; the older static probe is Compatibility-only | Update [nature](NATURAL_WORLD.md) and [environment](ENVIRONMENTS.md) references |
| Physical predator capture paths are computed before habitat-adjusted movement | Record the [combined-model limitation](PHYSICAL_HABITAT.md#combined-model-limitations), without asserting a new measured failure rate |
| Existing GitHub Actions checks the original Python application, not Godot V2 | [Development](DEVELOPMENT.md#tests) identifies manual V2/native checks |
| No V2 GitHub release exists in the checked release list | Separate local standalone artifacts from published V1 releases |
| Bundle verification, numerical replay and independent research have distinct evidential meanings | [Export](EXPORTS_AND_REPLAY.md#verify-versus-replay) and [research](RESEARCH_AND_VALIDATION.md) guides |

These findings describe the present implementation. The documentation does not silently repair runtime behavior, claim new sensors, invent genome import/resume, or extend statistical claims to physical habitats.

## Documentation structure

The new [index](README.md) provides task-oriented navigation. [V2's README](../README.md) offers an overview and launch path, while separate guides cover installation, operation, seven modes, brains/evolution, animals/animation, environments, every configuration field/CLI flag, exports/replay, measurements, architecture, development and troubleshooting. Existing V2 implementation notes remain linked and receive current scope/navigation corrections. Historical audits retain their own records and hashes.

The style follows the useful parts of V1's depth: exact model rules, source ownership, controlled baselines, honest interpretation, complete data/replay contracts, operational commands and explicit limits. It avoids duplicating thousands of lines of V1 results into a misleading new V2 research claim.

## Validation and preservation

[Documentation validation](documentation-validation/README.md) records internal link/anchor and code-block checks, original/physical example execution and preservation checks. The included JSON examples are valid original RunConfig files and do not modify the original preset directory.

All V1 README/docs, source, tests, requirements, CI, original presets, numerical results and release assets remain unchanged. No runtime/source implementation change is required by these guides. Earlier engineering tests retain their original status; this documentation campaign does not relabel them as a fresh independent reproduction.
