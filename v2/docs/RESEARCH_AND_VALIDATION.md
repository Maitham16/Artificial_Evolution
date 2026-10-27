# Research, measurements and validation

[Documentation](README.md) · [Evolution](EVOLUTION_AND_BRAINS.md) · [Export/replay](EXPORTS_AND_REPLAY.md) · [V1 reproducibility](../../docs/REPRODUCIBILITY.md)

Artificial Evolution supports observed adaptation under specified conditions. A realistic 3D presentation does not broaden that conclusion. Separate live demonstrations, engineering verification and independent-seed studies when interpreting a result.

## Three kinds of evidence

| Evidence | Question answered | Example |
| --- | --- | --- |
| Live experiment | What happened in this configured run? | A food-seeking cohort and its verified bundle |
| Engineering audit | Does the implementation preserve its declared behavior and packaging? | Passive observer parity, exact replay, native frame/input checks |
| Repeated scientific study | Does an evolutionary treatment improve a defined endpoint under matched conditions? | Step 18 selection versus drift, Step 27 held-out evaluation |

Repeated rendering frames, multiple screenshots and thousands of animals within one training seed are not independent evolutionary replications. A deterministic replay verifies a record; it does not independently confirm the scientific hypothesis.

## Metrics and their limits

| Metric | Definition / interpretation |
| --- | --- |
| Living population | Currently living active Python actors; cohort replacement is not continuous demographic growth |
| Mean earned fitness | Current live+dead generational cohort; all recorded lifetimes in Continuous |
| Completed-generation fitness | Canonical completed cohort history; absent before a cohort finishes |
| Mean meals | Meals across the scored cohort/lifetime set; main predator–prey set is prey |
| Predator fitness | Separate role-specific age + capture score; not mixed with prey fitness |
| Social fitness | Survival age; no direct sharing reward |
| Family count | Living founder-root count; genealogy, not species count |
| Effective families | Exponential Shannon diversity of current founder proportions |
| Live neural RMS | Raw per-parameter living neural diversity; excludes body genes and random/greedy placeholder arrays |
| Continuous genetic summaries | Model-specific normalized neural/body features and threshold clusters in the canonical report |
| Habitat metres/costs | Actual physical-extension travel and extra power/contact ledger; motor speed fields keep original meaning |
| Achieved Python rate | Simulated seconds per wall second; separate from render FPS |

Do not compare neural RMS across different architectures as a calibrated intelligence measure. Genetic clusters depend on a specified metric/threshold and do not prove speciation. Founder-family chart limits (12 roots/eight ancestry generations) are display limits; full ancestry is exported.

Live curves in the workbench show population, completed-generation fitness and sampled meals. They are descriptive, update with the model's sampling, and can reset or change meaning at cohort boundaries. Read censoring flags and species-specific reports before aggregating.

## Matched comparisons

For a controller comparison, hold constant layout/stock, population and cap, speed/cost rules, duration/generation/training budgets, mutation settings, test environments and physical-habitat options. Include random movement, greedy steering, unselected/frozen brains and neutral-parent reproduction where the model supports them.

Use multiple independent **training seeds**. Average matched test repeats within training seed before treating seed means as replications. Keep training and test worlds separate. Report uncertainty, paired effects, multiple-comparison rules and failures, not only best runs.

The V2 live workbench does not implement a new batch-study runner or statistical dashboard. The preserved scripts already own those protocols. Physical habitat changes movement/food placement and needs newly matched experiments; V1's published estimates are not estimates for the physical extension.

## Preserved study catalog

The original V1 catalog delegates to these scripts, preserving outputs/protocols under `results/`. Read the [original README](../../README.md) for methods and actual tables.

| Step | Question | Existing script |
| ---: | --- | --- |
| 13 | Evolved versus random | [compare_creatures.py](../../compare_creatures.py) |
| 14 | Mutation/population/food sweep | [experiment_parameters.py](../../experiment_parameters.py) |
| 15 | Emergent food seeking and interventions | [analyze_intelligence.py](../../analyze_intelligence.py) |
| 16 | Equal-speed random/greedy baselines | [experiment_speed.py](../../experiment_speed.py) |
| 17 | Food guidance versus unselected neural behavior | [experiment_strategy.py](../../experiment_strategy.py) |
| 18 | Fitness selection versus random-parent drift | [experiment_selection.py](../../experiment_selection.py) |
| 19 | Specialization and generalization | [experiment_specialization.py](../../experiment_specialization.py) |
| 20 | Brain decisions, trajectories and sensory influence | [inspect_brains.py](../../inspect_brains.py) |
| 21 | Seasons, movement of food and extinction | [experiment_seasons.py](../../experiment_seasons.py) |
| 22 | Obstacle/hazard avoidance | [experiment_obstacles.py](../../experiment_obstacles.py) |
| 23 | Neural/body trade-offs | [experiment_traits.py](../../experiment_traits.py) |
| 24 | Coevolution and historical opponents | [experiment_predator_prey.py](../../experiment_predator_prey.py) |
| 25 | Group/individual survival and cooperation | [experiment_social.py](../../experiment_social.py) |
| 26 | Continuous persistence, genealogy and diversity | [experiment_ecosystem.py](../../experiment_ecosystem.py) |
| 27 | Comprehensive matched evaluation | [experiment_evaluation.py](../../experiment_evaluation.py) |

List the catalog without starting a study:

```bash
./.venv/bin/python simulator.py --catalog
```

Run a full study only when its substantial budget is intended:

```bash
./.venv/bin/python simulator.py --study 27 --workers 8 \
  --export-root exports/new-evaluation
```

This uses the original CLI, not a V2 application flag. Workers are 1/2/4/8. The launcher creates a fresh study directory with command, sources, job state, progress log, data and plotter outputs. It does not overwrite published evidence. Steps 17 and 20 need saved Step 16/unselected populations; Step 27 needs Step 18 pairs. Install the original research evidence for those inputs. Missing inputs produce a clear error rather than a substituted population.

## What the published evaluation found

The original Step 27 record reused **16 independent training pairs**, then evaluated **160 matched test worlds, 1,056 cohorts and 105,600 lifetimes**. Those cohort/lifetime counts do not enlarge the independent training sample beyond 16 seed groups.

The published result supports evolved fitness and meal improvements over random movement in four food-containing environments, with greedy steering still stronger. Selection versus neutral fitness met the primary rule in uniform and sparse food; clustered contrasts remained inconclusive after correction. Barren conditions produced no fitness distinction. Sparse-world survival remained poor despite some gains.

For one concrete reference, the preserved uniform evolved-minus-random fitness difference is **+27.72**, paired 95% bootstrap interval **[+16.88, +38.20]**, Holm-adjusted **p=0.011414**. This is a V1 Step 27 result, not a new V2 experiment. The [original table and decision rules](../../README.md#observed-step-27-results) retain all environments, endpoints and uncertainty. Pointwise bootstrap intervals and corrected directional tests answer different questions; do not recategorize an inconclusive contrast from its mean alone.

Food-input interventions support useful food-dependent control under those protocols, but do not identify a unique targeting algorithm or general intelligence. The original study's 45 primary and 21 exploratory tests are corrected separately. New 3D art, habitat dynamics and frame-rate improvements do not retroactively alter that analysis.

## Engineering evidence

| Audit | Recorded scope | Limits |
| --- | --- | --- |
| [Current panel input](panel-input-validation/README.md) | 49 Python + 235 Godot checks; four native exported-UI-pack input runs; release/installed launch | Native fixture uses editor executable with exact UI pack, not injected scripting in release template |
| [Physical habitat](habitat-validation/README.md) | 431 original + 267 then-current V2 tests/checks; 13 packaged native cases; exact declared replay | Local engineering checks, not independent ecological inference |
| [Standalone runtime](desktop-validation/README.md) | 431 original tests in source and bundled interpreter; engine/source hashes, nine native cases, independent original 2D CLI | Earlier Compatibility renderer timings belong to that archive |
| [Bridge](bridge-validation/README.md) | Source authority, passive observations, transport and original preservation | Does not validate every possible experiment/model assumption |

The physical audit's three Metal trials used 100 founders, Balanced quality, 1520 × 960, 1,200 displayed frames each and 1,110 measured frames after warmup. Mean rendering was about 60 FPS, p95 about 17.2 ms, no measured intervals over 25 ms in those three trials. The declared target was mean ≥59 FPS, p95 ≤19 ms and <1% late intervals. Compatibility fallback measured around 40 FPS and failed that target.

Timings use monotonic wall-clock intervals, not smoothed Godot delta; capture/export is excluded. They are local M3 observations, not claims for 1000 animals, Lush, Intel, every macOS version or all background workloads. A reported GPU timing of zero on the tested driver means unavailable diagnostics, not zero GPU work.

Nearby IK tests report joint-target residuals, not a universal no-sliding proof. Physical exports replay their implementation exactly; the [combined-model capture-path limitation](PHYSICAL_HABITAT.md#combined-model-limitations) remains a modeling issue even when replay passes.

## Reproduce and report responsibly

Use [Development](DEVELOPMENT.md) for engineering checks and the unchanged [V1 reproducibility guide](../../docs/REPRODUCIBILITY.md) for protocols. Preserve configuration, extension/source hashes, seed lists, budgets, test conditions, runtime, raw data and failures. Re-run into fresh output paths, leaving historical records intact.

No independent external clean-install replication, Intel execution or Apple notarization is claimed by the committed local audits. A future physical-habitat study must declare its own matched protocol rather than reuse an original-rule conclusion.
