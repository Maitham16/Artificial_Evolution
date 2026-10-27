# Repository inspection and isolation design

[Documentation](README.md) · [User guide](USER_GUIDE.md) · [Development](DEVELOPMENT.md)

**Historical report:** the prototype-specific model, file tree and feature limits below describe the initial implementation, not the current app. Use [Architecture](ARCHITECTURE.md) and [the current review](REPOSITORY_REVIEW.md) for present behavior.

This report records the initial repository inspection and standalone prototype. The active application now uses the existing Python engine through the [Python bridge](PYTHON_BRIDGE.md); the later connection replaces the GDScript model described below.

Inspection date: 27 October 2026. Original baseline: `f890b4f481a6659714dfae70e11f5b34f19a86f3` (v1.0.1 maintenance commit). The inspection preceded v2 implementation.

## Coverage

The repository was clean before work. A file inventory recorded SHA-256 hashes and sizes for **591 tracked files** and **1,241 total pre-existing project/data/export files**. Generated environments, Git internals, caches, bytecode, operating-system files, and the new `v2/` folder were excluded. The inventory preserves both tracked and local experiment outputs, not just source code.

- All 91 tracked Python files were inspected through AST analysis and their definitions/imports mapped. Central simulation, perception, network, selection, reproduction, session/export, and UI modules were also read directly.
- The complete 4,097-line original README and all five other Markdown documents were read: AGENTS, the two release notes, reproducibility documentation, and the user guide.
- Structured data inspection covered 102 JSON files (types, keys, schema/status), 182 NumPy archives (all member names, shapes, and dtypes, with pickle disabled), 48 compressed JSON records, and 47 CSV datasets (headers and row counts). Large numerical arrays were profiled, not manually read element by element. This survey is not an independent rerun of the published scientific studies.
- Requirements, CI, configuration presets, release packaging rules, manifests, license, and Git metadata were inspected. Existing MIT licensing and GitHub Actions already exist at this baseline; neither needed changing for the requested isolated v2 app.
- Before implementation, the original test suite passed **431 tests in 113.245 seconds**. After implementation, it passed **431 tests in 116.300 seconds**.

Raw records: [baseline hashes](inspection/baseline.json), [source/data inventory](inspection/data-and-source-inventory.json), [before-test log](inspection/original-tests-before.log), [after-test log](validation/original-tests-after.log), and [preservation report](validation/preservation.json).

## Original architecture

| Area | Responsibilities and coupling |
| --- | --- |
| `world.py`, `creature.py`, `food.py` | Movement, survival, consumption, environmental state |
| `brain.py`, `perception.py` | NumPy network decisions and local sensory inputs |
| `selection.py`, `reproduction.py`, `simulation.py` | Fitness ranking, mutation, cohort evolution, generation records |
| Experiment and plot modules | Independent training runs, interventions, controls, aggregation, statistical evaluation |
| `ecosystem.py`, `predator_prey.py`, `social.py`, trait/obstacle/season modules | Additional ecological models and their scientific protocols |
| `research_session.py`, `research_catalog.py` | Configurations, application-independent sessions, research catalog, export and replay |
| `research_app.py`, `simulator.py` | Pygame research interface and command-line entry point |
| Root `test_*.py`, `results/`, `docs/`, release tooling | Regression evidence, saved studies, provenance, releases |

The important boundary is numerical model → session observation/export → presentation. It lets the original interface and scientific datasets remain untouched while the new renderer uses its own implementation.

The existing models have distinct sensor dimensions and study protocols. Copying saved neural weights into a new controller would silently change their meaning. V2 therefore identifies its own model as `godot_ground_foraging_v1`, has a separate schema and output directory, and does not claim compatibility with original saved populations or experiment results.

## Graph-assisted inspection

The Graphify skill mapped a read-only corpus of all 91 Python sources and six Markdown documents. The combined map contains **1,742 nodes, 6,699 edges, and 55 communities**. High-degree concepts include World (209 edges), EvolutionSimulation (135), and NeuralNetwork (102). These connections guided direct source reading and the isolation boundary; they are navigation aids rather than proof of execution behavior.

Artifacts: [interactive graph](inspection/graph.html), [graph JSON](inspection/graph.json), [generated report](inspection/GRAPH_REPORT.md), and [health audit](inspection/health.json).

The extractor reported **894 dangling endpoint edges**, four self-loops, and 223 endpoint collapses when converting candidates into an undirected graph. AST calls to external or unresolved symbols and graph normalization limit graph accuracy. The report's zero token counters are generator placeholders because the host did not expose delegated token usage; they do not mean the analysis had zero cost. Neither inferred relationships nor topology replace the test results or file hashes.

## New application boundaries

Everything added to the repository is under `v2/`:

```text
v2/
  project.godot, scenes/         Godot entry point and native desktop window
  scripts/brain.gd               Independent tiny neural network
  scripts/simulation.gd          Fixed-step ground-plane numerical model
  scripts/world_view.gd          3D meshes, camera, picking, cosmetic animation
  scripts/main.gd, visuals.gd    Controls, inspection, charts, family overview
  scripts/benchmark.gd           Matched frozen-bank transfer checks
  scripts/exporter.gd            Immutable bundles, hashes, deterministic replay
  assets/                       Optimized GLBs, procedural shaders, icon
  art_source/                   Editable Blender models, ignored by Godot
  presets/                      Complete validated model configurations
  tools/                        Setup, asset generation, build, CLI, preservation
  tests/                        Godot model and UI integration checks
  docs/                         Inspection, validation, and screenshots
```

Model randomness is split into body, food, initial-brain, steering, parent, and mutation streams. Rendering and UI observation do not draw model randomness. All controllers share 3 m/s speed and the same energy costs. Neutral reproduction changes parent eligibility while preserving mutation rules and draws. The transfer checker uses fresh layout seeds, freezes both brain banks, includes dead birth slots, checks physical-start hashes, and labels its results as descriptive rather than independent training replications.

The full original scientific catalog is not ported. This v2 delivers a separate functioning 3D neuroevolution desktop application with synchronized foraging cohorts, six habitats, five policies, family visualization, local neural inspection, and reproducible exports. Continuous ecosystem, predator–prey, social behavior, body-trait evolution, and original multi-seed research workflows remain available through the unmodified Python application.

## Preservation

No original source, interface, test, result, root README, requirements, CI workflow, license, release, or Git history was edited. Setup added external Mac applications and Godot templates; v2 uses its own application-support directory and ignored local build/import outputs. The existing Python virtual environment was used for regression testing, not rebuilt or upgraded.

`tools/verify_original.py` compares the original tracked hashes on any checkout. `--all-existing` additionally verifies the original Mac's pre-existing untracked research/export files. The final local check confirms all **1,241 originals unchanged**, including every one of the **591 tracked files**. All committed additions are confined to `v2/`.
