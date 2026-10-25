# Artificial Evolution

An experiment to investigate whether food-seeking behavior evolves in creatures
controlled by tiny neural networks, with random movement as a comparison.

Current step: **17 — Investigate what the creatures learned**. Reuse the sixteen
fixed-speed evolved populations, compare against unselected ancestral brains,
and intervene on food inputs in new matched environments. Preserve Step 16's
code, models, results, and conclusions.

## Run the world

From this project folder:

```sh
source .venv/bin/activate
python main.py
```

Neural control is the default. The existing random movement controller is also
available as a baseline:

```sh
python main.py --controller random --seed 42
```

- Press **G** to hide or show the grid.
- Press **V** to hide or show the selected creature's perception overlay.
- Press **F** to open or close the fitness leaderboard.
- Press **T** to open or close generation history and trend charts.
- Press **S** to cycle between **1x**, **5x**, and **20x** simulation speed.
- Press **A** to switch automatic generation cycling on or off.
- Press **N** after a generation ends to breed manually, within the generation limit.
- Press **Space** to pause or resume movement, eating, energy use, and aging.
- Press **R** to restart with random founders, clearing generations and results.
- **Click a creature** to inspect its properties. Click empty space to deselect.
- Press **Esc**, or close the window, to quit.

The window runs at up to 60 frames per second. The arena has a visible border and
a 40-pixel grid, with a stronger line every 200 pixels. Its coordinates start at
`(0, 0)` in the top-left corner, with x increasing right and y increasing down.
The surrounding header and footer are outside the arena. The border marks the
reflective walls; the grid is a visual guide.

## Investigate learned food guidance and movement

Step 17 adds a new analysis; **Step 16 is preserved**. It reuses every brain in
the sixteen saved final birth cohorts from seeds 1601–1616, without retraining,
selection, mutation, tuning, or choosing test winners. Before this step, all
**212 existing tests passed**. `results/step17-baseline.json` records the preceding
commit and hashes of all 79 tracked files, including all 41 prior result
artifacts; `results/step17-baseline-tests.txt` saves that test transcript.

Run the fixed-protocol study:

```sh
python experiment_strategy.py --workers 6 --output .cache/strategy.json \
  --unselected-models-dir .cache/unselected-models \
  --protocol-output .cache/strategy-protocol.json --plot .cache/strategy.png
```

The source defaults are `results/step16-models` and the published
`results/step16-speed-comparison.json`. Model-file hashes and complete-cohort
genome hashes link the new experiment to the original records. All evolved
weights stay frozen throughout testing.

The **unselected neural baseline** consists of the original random founder
brains, reconstructed deterministically from each Step 16 training seed using
unchanged initialization code. The founder world's physical hash must match
the archived first training layout. This check verifies the starting bodies,
lifespans, and food; founder weights are regenerated from the deterministic
initialization, then saved in numeric archives for this study. These brains
undergo no training, selection, or mutation. The comparison measures the effects
of the evolved history relative to its initial policy distribution; it does
not separate selection from mutation or provide a neutral-drift control.

Each lineage faces **one new layout in each of the three Step 16 environment
families**: uniform food in 1000 × 600, clustered food in 1000 × 600, and clustered
food in 1200 × 500. The new `step17:test` seed namespace includes lineage,
environment, and repeat. Every layout must differ from **every** Step 16 training
and test layout, including those from other lineages. There are **48 unseen
layouts**, repeated independently across sixteen source lineages per environment.
The default uses one layout per lineage/environment, rather than the two used
in Step 16; `--repeats` can specify a different budget for a future declared study.

Each layout runs all seven conditions in separate matched 100-creature worlds:

| Condition | Weights | Direct food inputs |
| --- | --- | --- |
| Evolved intact | Saved evolved cohort | Truthful |
| Evolved mirrored | Same evolved cohort | Food bearing reflected left/right |
| Evolved hidden | Same evolved cohort | Proximity, bearing, and visibility set to zero |
| Unselected intact | Original random founders | Truthful |
| Unselected mirrored | Same founder cohort | Food bearing reflected left/right |
| Unselected hidden | Same founder cohort | All three food inputs set to zero |
| Random | Existing random steering | Unused by controller |

All conditions share **60 pixels/second**, **5 energy units per living second**,
150 maintained pellets, body traits, lifespan limits, initial food, cluster
centers, and initial random streams within a layout. The same existing turning,
food replenishment, energy, and death rules apply. The sensor interventions are
the existing Step 15 implementation: they alter inputs only at the brain-control
boundary. Food, hunger, walls, collision detection, and recorded observations
remain physical truth. Later replenishment and random-stream consumption can
diverge as behavior diverges. Complete cohorts are evaluated, including early
deaths. The study has **336 test cohorts and zero training cohorts**.

The independent statistical unit is **one source training lineage (n = 16)**.
Repeats, if requested, are averaged within lineage and environment before
inference. The **twelve predeclared primary tests** comprise four contrasts in
each of the three environments:

| Contrast | Outcome | Question |
| --- | --- | --- |
| Evolved intact − evolved mirrored | Meals per creature | Does truthful food bearing help the evolved population? |
| (Evolved intact − mirrored) − (unselected intact − mirrored) | Meals per creature | Did the useful bearing benefit increase beyond the founders' benefit? |
| Evolved intact − unselected intact | Fitness | Do evolved brains outperform the original neural population? |
| Evolved hidden − unselected hidden | Fitness | Is an evolved advantage retained when direct food inputs are hidden? |

The second contrast is calculated **within lineage** before paired analysis;
it is not a difference between two separately pooled significance tests. All
twelve use two-sided exact paired sign tests with the Step 16 numerical-tie
tolerance of `1e-10`, and Holm correction across the full family. Intervals use
20,000 paired percentile bootstrap resamples, with approximate pointwise 95%
coverage. A higher/lower decision requires adjusted p < 0.05 and an interval
excluding zero in the same direction. The declared food-guidance attribution
requires the first three contrasts all higher within an environment. Individual
test results remain visible when that joint criterion is not met; failure does
not establish absence or equivalence.

Other performance contrasts, including evolved hidden versus random and
unselected hidden versus random, are descriptive with pointwise intervals and
no confirmatory p-values. Fitness, meals, and 60-second survival are saved for
every condition. These contrasts are not an additive decomposition of the
previous Step 16 gain.

Two **descriptive diagnostic probes** characterize all frozen evolved and
founder brains:

- The existing steering probe flips only target side at ±45°/±90°, distances
  40/80/120, and hunger 25%/75%, with all wall inputs at 1. Its signed gain is
  `(turn_right − turn_left) / 2`. The separate fraction commanding the correct
  turn on both sides distinguishes an appropriate shift from a persistent bias.
- The movement probe supplies no direct food input, open-space wall values,
  and hunger clamped at 25% or 75%. A feed-forward brain then has a constant
  turn output. It reports mean absolute turn and the analytic displacement/arc
  length ratio after 12 seconds: `abs(sinc(angular_speed × 12 / (2π)))` with
  NumPy's normalized sinc. A straight path has ratio 1; a complete circular
  orbit has ratio 0. This is a controlled probe, not a natural trajectory,
  navigation test, or evidence of planning.

Food-channel removal creates an input distribution shift, and hidden creatures
still receive **indirect feedback from eating through hunger/energy**. A residual
advantage can reflect turning biases, wall/hunger responses, or other aspects
of control. It does not identify an exclusive general-movement strategy, and a
drop does not rule out such strategies. Mirroring also changes closed-loop
trajectories; its useful-bearing effect demonstrates the value of truthful
directional information, rather than human-like understanding. Food guidance
and residual movement benefits can coexist.

`results/step17-protocol.json` records the protocol, UTC declaration time, all
source hashes, source model hashes, and excluded layouts before testing. This
is a local declaration, not an externally registered study. Partial reports
remain `running` and cannot produce a final plot. Unselected archives use
`allow_pickle=False`; existing matching archives are preserved, and conflicting
archives or attempts to overwrite source inputs are rejected.

Regenerate the figure:

```sh
python plot_strategy.py results/step17-strategy.json --output .cache/strategy.png
```

Re-running the same source models and deterministic test seeds checks
reproducibility and does not increase the independent sample size. Keep replay
outputs in a new directory to preserve the published reports.

### Recorded Step 17 results

The complete study evaluated **336 cohorts on 48 new matched layouts**, reusing
all sixteen evolved populations and evaluating their sixteen unselected founder
cohorts. No population was retrained. The audit verified all frozen weights,
founder reconstruction, model archives, probes, source hashes, and stored
statistics. All **41 previous result artifacts and all previous code files remain
unchanged**. Only this README is extended among the pre-existing tracked files.

Mean fitness under the seven conditions:

| Condition | Uniform | Clustered | Wide clustered |
| --- | ---: | ---: | ---: |
| Evolved intact | 354.12 | 353.24 | 350.80 |
| Evolved mirrored | 277.65 | 137.83 | 135.37 |
| Evolved hidden | 258.99 | 222.61 | 237.99 |
| Unselected intact | 291.21 | 206.14 | 211.04 |
| Unselected mirrored | 291.26 | 218.01 | 221.72 |
| Unselected hidden | 293.25 | 207.76 | 213.68 |
| Random | 323.44 | 211.90 | 196.64 |

The twelve primary tests produced these mean paired differences:

| Environment | Contrast and unit | Difference | 95% paired interval | Holm p | Decision |
| --- | --- | ---: | --- | ---: | --- |
| Uniform | Evolved intact − mirrored meals | +6.71 | [4.86, 8.60] | 0.002075 | Higher |
| Uniform | Bearing benefit above founders, meals | +6.75 | [4.90, 8.71] | 0.0003662 | Higher |
| Uniform | Intact evolved − founders, fitness | +62.91 | [52.37, 73.27] | 0.0003662 | Higher |
| Uniform | Hidden evolved − founders, fitness | −34.27 | [−64.54, −6.16] | 0.6303 | Inconclusive |
| Clustered | Evolved intact − mirrored meals | +19.24 | [14.47, 24.32] | 0.0003662 | Higher |
| Clustered | Bearing benefit above founders, meals | +20.37 | [15.97, 24.82] | 0.0003662 | Higher |
| Clustered | Intact evolved − founders, fitness | +147.09 | [103.08, 194.83] | 0.0003662 | Higher |
| Clustered | Hidden evolved − founders, fitness | +14.85 | [−12.19, 47.42] | 1.0000 | Inconclusive |
| Wide clustered | Evolved intact − mirrored meals | +19.36 | [14.64, 24.63] | 0.0003662 | Higher |
| Wide clustered | Bearing benefit above founders, meals | +20.35 | [15.84, 25.48] | 0.0003662 | Higher |
| Wide clustered | Intact evolved − founders, fitness | +139.77 | [97.15, 187.87] | 0.0003662 | Higher |
| Wide clustered | Hidden evolved − founders, fitness | +24.31 | [−10.07, 66.96] | 1.0000 | Inconclusive |

**All three food-guidance attribution criteria passed in every environment.**
Truthful bearing improved evolved feeding in 15 of 16 uniform lineages and all
16 lineages in each clustered environment. The bearing benefit exceeded the
founders' benefit in all 16 lineages in every environment. Intact evolved brains
also exceeded intact founders' fitness in all 16 lineages in every environment.
These findings support **evolved functional food-directed control** beyond the
initial neural-policy distribution, under the tested conditions.

The three residual hidden-input comparisons were **inconclusive**. The uniform
mean interval was negative, but did not meet the predeclared sign-test threshold;
neither a lower nor a higher effect is confirmed there. Hidden evolved versus
random and hidden founders versus random remain descriptive comparisons. For
example, wide-arena hidden evolved fitness exceeded random by +41.35 on average
with interval [4.10, 85.38], while hidden founders also exceeded random by +17.04
[4.43, 29.97]. Those secondary intervals do not establish an evolved residual
advantage over founders or identify its mechanism.

Descriptive probe averages:

| Population | Steering gain | Both-side correct probe pairs | Absolute no-food turn, fraction of limit | Open-space straightness after 12s |
| --- | ---: | ---: | ---: | ---: |
| Evolved | 0.13355 | 34.36% | 0.35677 | 0.34451 |
| Unselected founders | −0.00264 | 4.61% | 0.36846 | 0.35435 |

The steering probes show a larger food-directed response in evolved brains,
while the simple no-food movement averages are close. Only about one third of
evolved probe pairs commanded correct turns on both sides, so this is not
perfect pursuit by every creature. These controlled averages do not exclude
differences in real hunger- or wall-dependent motion. Hidden-input distribution
shift and indirect feeding feedback limit any exclusive causal explanation.

The result supports useful evolved food guidance; it does **not demonstrate an
additional general-movement advantage when direct food channels are hidden**.
That is not evidence of equivalence or proof that every part of the Step 16 gain
comes from food guidance. The new uniform primary tests concern sensory benefit
and the founder comparison; they do not change Step 16's inconclusive uniform
evolved-versus-random result. The same sixteen source populations are reused,
so the two studies must not be pooled as 32 independent training lineages.

![Step 17 food-guidance and residual movement analysis](results/step17-strategy.png)

The figure was visually inspected. `results/step17-audit.json` records the
completeness, preservation, model/probe reproduction, and statistical audits,
with runtime versions and artifact hashes. `results/step17-tests.txt` saves the
passing **227-test** transcript. Fitness, meals, and 60-second survival for every
condition, all secondary intervals, and per-brain probes remain in the JSON report.

## Compare steering at identical movement speed

The earlier comparison allowed random creatures to cruise at full speed while
neural creatures chose throttle. It therefore measured a combination of steering,
speed, and energy cost. Step 16 controls this by retraining from random founders
with **every creature moving at 60 pixels/second**, overriding neural throttle
before energy use and movement, including the first tick. Every body also has
the same 60-pixel/second maximum speed. The original behavior remains the default
when `--fixed-speed` is omitted.

Try the controls directly:

```sh
python main.py --seed 42 --controller neural --fixed-speed 60
python main.py --seed 42 --controller random --fixed-speed 60
python main.py --seed 42 --controller greedy --fixed-speed 60 --food-distribution clustered
```

All controllers share the original body generation, sensing radius (160 pixels),
turning limit (90°/second), boundary reflection, energy formula, and survival
rules. **Per living second**, energy cost is now exactly `2 + 0.05 × 60 = 5`
units for every creature. This equalizes commanded speed and per-second movement
cost, not total lifetime expenditure or lifetime distance: survivors move and
consume energy for longer. Motion still follows the existing fixed timestep and
wall reflection rules.

The **greedy reference** turns toward the nearest detected pellet using the
shortest signed bearing, bounded by the same turning limit. It limits the last
turn to avoid overshooting the target angle. When no food is detected, it uses
the existing random steering policy. It has no access to unseen food, future
pellets, test outcomes, or extra sensory range. The evolved network architecture
remains 8–8–2; its throttle output is ignored under the speed constraint.

Before modification, all **193 existing tests passed**. The full test transcript
is saved in `results/step16-baseline-tests.txt`. The baseline manifest
`results/step16-baseline.json` records the preceding commit and SHA-256 hashes of
its tracked source and result files. Earlier experiment reports, plots, and model
archives remain unchanged in place and in Git history. The source changes for
this step are relative to that preserved commit.

Run the full study:

```sh
python experiment_speed.py --workers 6 --models-dir .cache/speed-models \
  --output .cache/speed-comparison.json --protocol-output .cache/speed-protocol.json \
  --plot .cache/speed-comparison.png
```

The fixed protocol uses **16 new independent training seeds (1601–1616)**,
**10 generations**, population 100, food supply 150, mutation probability 0.1,
mutation scale 0.1, and the existing fitness and selection rules. Training uses
uniform food in a 1000 × 600 arena throughout. It does not reuse variable-speed
Step 15 models or tune parameters against test results. All 100 brains from each
final birth cohort are frozen, without selecting a test winner or generation.

Each lineage faces **two new layouts per environment**:

| Test environment | Geometry | Food distribution | Relationship to training |
| --- | --- | --- | --- |
| Uniform | 1000 × 600 | Uniform | New layouts at the trained distribution |
| Clustered | 1000 × 600 | Four seeded clusters | Unseen food distribution |
| Wide clustered | 1200 × 500 | Four seeded clusters | Unseen distribution and aspect ratio |

All arenas have equal area and the same maintained food count. For clustered
food, four centers are drawn independently within the middle 60% of each axis.
Each spawn chooses a center uniformly and proposes a Gaussian offset with
55-pixel standard deviation on each axis. Out-of-bounds or overlapping proposals
are rejected; there is no uniform fallback. Centers remain fixed during a
cohort and are resampled for the next layout. These parameters are declared in
the protocol. Clusters can overlap; they are not enforced as four separate
non-overlapping patches.

Food remains continuously replenished in every condition. Clustered spawning
changes where replenishment occurs and may reward staying near food patches;
it does not remove the existing benefit of random exploration in uniform arenas.
Step 16 does not test depleted finite food supplies or every possible environment.

Test seeds use a separate `step16:test` namespace. For each layout, evolved,
random, and greedy conditions start in separate worlds with identical bodies,
food, lifespans, cluster centers, and random streams. Body IDs receive matched
physical traits across conditions. Initial physical hashes verify matching and
separation from training. Later food replenishment and random-stream consumption
can diverge as behavior diverges. This is a comparison of complete populations,
with within-population competition, rather than isolated creature trials.

No selection, reproduction, mutation, or weight updates occur during testing.
Genome hashes verify that the complete evolved cohort remains frozen. The same
brain arrays are also recorded for baseline bodies, whose steering policies do
not consult them. Numeric model archives use `allow_pickle=False` and validate
configuration, IDs, array shapes, finite values, and hashes on loading.

There are **160 training cohorts** and **288 test cohorts**, totaling **448**,
with **96 distinct unseen test layouts**. Repeats are averaged within each
lineage and environment before inference, keeping the independent sample size
at **16**, not 96 layouts or 1,600 creatures. Training trajectories and every
test condition are saved. Progress stays `running` until all planned trials
finish, and incomplete studies cannot be plotted.

The primary family contains **nine evolved-minus-random contrasts**: fitness,
meals per creature, and survival to 60 seconds in each of the three environments.
Two-sided exact paired sign tests exclude ties and use Holm correction across
all nine. Absolute paired differences within `1e-10` are treated as numerical
ties for sign-test counts only; raw effect sizes and intervals are retained.
Difference intervals use 20,000 paired percentile bootstrap resamples,
with approximate pointwise 95% coverage. A higher/lower decision requires both
adjusted p < 0.05 and an interval excluding zero in the corresponding direction.
Fitness wins are reported separately by environment; a claim of beating random
fitness across all three requires all three fitness contrasts to pass. Greedy
contrasts are secondary descriptive estimates with pointwise intervals and no
confirmatory p-values. A nonsignificant difference does not establish equivalence.

`results/step16-protocol.json` records the protocol, UTC declaration time, and
source hashes before the actual trials started. This is a local record of the
declared analysis, not an externally registered study. Primary conditions, the
trial budget, and significance/interval decision thresholds are fixed before
test analysis.

`results/step16-numerical-ties.json` records one numerical correction during the
run, before any full lineage finished testing: synthetic equal-count averages
could differ by about `1e-16` in binary arithmetic. The `1e-10` sign-test tie
tolerance prevents counting that noise as a win. The note preserves the original
declaration hash, time, and changed analysis/test source hashes. Training,
physics, conditions, seeds, primary family, budget, and decision thresholds stay
unchanged. The final complete raw report is reanalyzed with this correction;
the running parent had already loaded the earlier analyzer.

Reproduce tests from the saved fixed-speed models:

```sh
python experiment_speed.py --workers 6 --reuse-models \
  --models-dir results/step16-models --output .cache/replayed-speed.json
python plot_speed.py results/step16-speed-comparison.json --output .cache/speed.png
```

Replaying the same deterministic test seeds checks reproducibility; it does not
create new independent evidence. `--seeds`, `--generations`, and `--repeats` allow
other studies, whose settings should be chosen before looking at their outcomes.
Conclusions concern this fixed speed, training budget, mutation setting, and
environment family, rather than evolution in general.

### Recorded Step 16 results

All **16 lineages, 448 cohorts, and 96 distinct unseen layouts** completed.
The final audit verified all 16 model archives, matched/frozen test conditions,
and separation from every training layout. All 17 earlier result artifacts
remain unchanged. Stored statistics match fresh recomputation. The documented
numerical-tie correction changed no sign count, p-value, decision, effect size,
or confidence interval in these data.

Mean fitness, averaging test repeats within each lineage first:

| Environment | Evolved | Random | Greedy | Evolved − random, 95% CI | Holm p | Decision |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| Uniform | 354.97 | 321.69 | 637.40 | +33.28 [20.31, 47.06] | 0.06381 | Inconclusive |
| Clustered | 340.25 | 197.63 | 1193.75 | +142.62 [109.86, 178.54] | 0.0002747 | Higher |
| Wide clustered | 361.78 | 202.70 | 1156.48 | +159.08 [115.28, 206.86] | 0.0002747 | Higher |

Feeding and survival means under the same fixed-speed constraint:

| Environment | Evolved meals | Random meals | Greedy meals | Evolved survival | Random survival | Greedy survival |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Uniform | 27.35 | 24.32 | 55.01 | 87.1% | 82.0% | 96.3% |
| Clustered | 28.36 | 15.47 | 110.57 | 47.6% | 25.0% | 97.2% |
| Wide clustered | 30.34 | 15.97 | 107.05 | 49.6% | 25.6% | 94.2% |

Meals are per creature; survival means reaching 60 simulated seconds. Fitness
uses the existing `survival_seconds + 10 × meals` definition. Greedy comparisons
are descriptive secondary benchmarks.

**The evolved populations beat the existing random controller in both clustered
environments.** All 16 lineages favored evolution on fitness, meals, and survival
in each clustered environment. All six contrasts passed the nine-test Holm
correction, with positive difference intervals. Fitness was approximately
**72.2% higher** with standard clustered food and **78.5% higher** in the wider
clustered arena. These are gains over random under the declared conditions.

Uniform-food averages also favored evolution, with fitness and meals higher in
13 of 16 lineages and survival higher in 12. However, none of the three uniform
contrasts passed the corrected sign tests. Their positive mean intervals alone
do not satisfy the declared decision rule. A fitness advantage across all three
environments is therefore **not demonstrated**.

The greedy controller had substantially higher observed mean fitness, meals,
and survival in every environment. Evolution has room to improve under this
budget. The findings benchmark final evolved populations against the specified
random controller; this step does not add an unselected-neural training arm to
isolate selection's contribution from the initial policy distribution. Performance
advantages also do not by themselves establish food understanding or planning.

![Step 16 fixed-speed fitness, meals, and survival comparisons](results/step16-speed-comparison.png)

The exported figure was visually inspected. `results/step16-audit.json` records
the completeness, model, source, speed, score, denominator, and data-integrity
checks, along with runtime versions and artifact hashes. The largest difference
between recorded cohort mean speed and 60 was `3.6e-10` pixels/second, from
floating-point accumulation. `results/step16-tests.txt` saves the passing
212-test transcript.

## Analyze emergent food-guided behavior

Run the full, fixed-protocol analysis:

```sh
python analyze_intelligence.py --workers 4 --models-dir .cache/intelligence-models \
  --output .cache/intelligence.json --plot .cache/intelligence.png
```

The study uses **eight new training seeds (1501–1508)** and **ten generations**
under the original settings: population 100, food 150, mutation probability 10%,
Gaussian mutation scale 0.1, and the existing fitness/selection rules. No setting
is chosen from the Step 14 validation results. Founder brains are copied before
training, and all 100 final-cohort brains are frozen after training. No test
result selects a model, creature, generation, or hyperparameter.

Each lineage is tested on **two new layouts in each of two environments**:

| Environment | Dimensions | Food | Relationship to training |
| --- | --- | ---: | --- |
| Standard | 1000 × 600 | 150 | New bodies and food layouts at the trained geometry |
| Wide | 1200 × 500 | 150 | New layouts and an unseen aspect ratio, with equal area/density |

Test seeds use a separate `step15:test` namespace containing lineage, environment,
and repeat. The design has **32 distinct unseen layouts**. Separate training/test
environments are central to evaluating generalization, as illustrated by
[Cobbe et al.'s generalization study](https://proceedings.mlr.press/v97/cobbe19a/cobbe19a.pdf).
This project uses evolutionary selection, with its own operational criteria.

Every layout has five matched conditions:

| Condition | Brain and food information |
| --- | --- |
| Intact | Frozen evolved brains with truthful sensors |
| Mirrored | The same brains with food bearing reflected left/right; distance, visibility, hunger, and walls stay accurate |
| Hidden | The same brains with all three food inputs set to zero |
| Founder | Frozen original founder brains with truthful sensors |
| Random | The existing random movement controller |

Bodies, food, lifespan limits, and random streams start identically within each
layout. Replenishment then follows each condition's behavior. No selection,
reproduction, mutation, or weight updates occur during testing. Genome hashes
verify source and test weights. All creatures are evaluated, including those
that die early. The fresh study runs **80 training and 160 test cohorts**, totaling
**240 cohorts**.

Food interventions happen only at the brain-control boundary. Physical food
and observations remain truthful: `World.get_sensory_inputs()` still reports the
real sensory state, and the simulation's food-facing statistics use real food.
Reports record `food_sensor_mode` and `arena_size`. The hidden-input condition is
a secondary stress test: feature removal can itself change the input distribution,
so its performance drop alone cannot establish feature understanding. This
limitation is discussed by [Hooker et al.](https://papers.nips.cc/paper/2019/file/fe4b8556000d0f0cae99daa5c5c5a410-Paper.pdf).

The separate **counterfactual steering probe** presents each frozen brain with
food at ±45° and ±90°, distances 40/80/120 pixels, and hunger 25%/75%. All wall
inputs are 1, representing open space. Each pair changes only target side.
Its signed response is:

```text
steering gain = (turn output with food on the right - output with food on the left) / 2
```

Positive gain indicates a shift in steering toward target side. A separate
descriptive fraction counts pairs where the brain actually commands right for
the right target and left for the left target; a fixed turning bias cannot satisfy
that fraction. Zero turn counts as neither direction. The probe has 12 pairs per
brain, but these are not independent experimental samples.

The independent unit remains **one trained lineage (n = 8)**. The two test layouts
are averaged within each environment and lineage before inference. Predeclared
primary tests ask whether:

1. Truthful bearing improves mean meals over mirrored bearing in standard arenas.
2. The same benefit appears in wide arenas.
3. Evolved steering gain is positive.
4. Evolved steering gain exceeds the founders' gain.

All four use the existing two-sided exact paired sign test, with Holm correction
across the four tests. Mean-difference intervals use 20,000 paired bootstrap
resamples at 95% confidence and remain approximate/pointwise. The full operational
criterion requires all four adjusted p-values below 0.05 and positive intervals.
Secondary contrasts are descriptive. A positive interval with an insufficient
directional-consistency p-value does not pass the declared rule.

These criteria assess useful **reactive food guidance**, not human-like
intelligence, memory, or planning. Failure does not exclude all food-dependent
behavior, including strategies involving speed or contexts outside the probe.
Effects are reported in meals and steering units so their practical size remains
visible.

Frozen founder/evolved brains are saved as numeric `.npz` archives with seed,
training configuration, complete-cohort IDs, and genome hashes. Loading uses
`allow_pickle=False` and checks shapes, finite values, hashes, and configuration.
You can reproduce testing without repeating training:

```sh
python analyze_intelligence.py --workers 4 --reuse-models \
  --models-dir results/step15-models --output .cache/replayed-intelligence.json
```

The repeated test seeds are deterministic, so this is a reproducibility check,
not new independent evidence. For a new study, choose new training seeds before
examining outcomes. `--seeds`, `--generations`, and `--repeats` set the budget.
Progress reports stay `running` until every planned lineage, environment,
repeat, and condition has finished; incomplete studies cannot be plotted.

Regenerate a figure from a complete report:

```sh
python plot_intelligence.py results/step15-intelligence.json \
  --output .cache/intelligence.png
```

### Recorded Step 15 results

The completed study includes all **240 planned cohorts**, **eight independent
lineages**, and **32 unseen layouts**. Mean meals per creature, averaged within
lineage before averaging across lineages:

| Condition | Standard arena | Wide arena |
| --- | ---: | ---: |
| Intact evolved | 21.88 | 21.97 |
| Mirrored bearing | 17.73 | 17.68 |
| Hidden food inputs | 15.25 | 14.52 |
| Founder brains | 8.43 | 8.25 |
| Random movement | 23.97 | 23.76 |

The four predeclared primary tests produced:

| Test | Mean effect | 95% paired bootstrap interval | Holm-adjusted p | Decision |
| --- | ---: | --- | ---: | --- |
| Intact − mirrored meals, standard | +4.158 | [2.423, 6.171] | 0.03125 | Higher |
| Intact − mirrored meals, wide | +4.293 | [2.362, 6.671] | 0.07031 | Inconclusive |
| Evolved steering gain above zero | +0.07367 | [0.04121, 0.11111] | 0.03125 | Higher |
| Evolved gain above founders | +0.07351 | [0.03985, 0.11410] | 0.03125 | Higher |

**Three of four criteria pass: there is evidence of useful reactive food
guidance, while robust generalization remains unconfirmed.** Truthful bearing
improved feeding in all eight standard-arena lineages. The wide arena had a
similar positive average effect, with seven of eight lineages benefiting, but
did not meet the declared directional-consistency threshold. This uncertainty
does not establish an absence of food guidance in wide arenas.

Evolved mean steering gain was 0.07367, versus 0.00016 for founders. Correct
commands on both sides appeared in **22.0%** of evolved probe pairs versus
**5.47%** for founders; many responses therefore still had turning biases or
failed to turn correctly on both sides. Intact evolved creatures also remained
below random movement in mean food intake and fitness in both environments.
Useful sensory behavior has emerged without establishing superior overall
performance, planning, or human-like intelligence.

![Step 15 food-guidance and generalization results](results/step15-intelligence.png)

## Experiment with parameters

Choose a world configuration directly:

```sh
python main.py --seed 42 --population 50 --mutation-rate 0.3 --food-count 75
```

- `--population`: positive integer; the same number of newborns is created at
  every generation and restart. Default **100**.
- `--mutation-rate`: independent probability from 0 to 1 for each weight or bias.
  Default **0.1**. A rate of zero still uses fitness selection and inheritance;
  it explores the founders' existing genomes without adding mutations.
- `--mutation-scale`: finite non-negative standard deviation of Gaussian noise.
  Default **0.1**. The recorded sweep holds this fixed.
- `--food-count`: non-negative maintained pellet supply. Default **150**.
  The study uses **75 scarce**, **150 standard**, and **225 rich** pellets to
  change environmental difficulty while keeping other survival rules fixed.

The header shows the configured birth population and mutation probability.
Selection retains the top 20%, rounding up, and reproduction creates exactly the
configured population. Scores and survival rates use the actual cohort size.
Space, N, R, generation limits, reports, and plot exports work with custom settings.

Run the exploratory parameter study:

```sh
python experiment_parameters.py --workers 4 \
  --output .cache/parameters.json --plot .cache/parameters.png
```

The fixed standard is mutation **10%**, population **100**, and food **150**.
The default **seven-setting** design changes one factor from this standard:

| Factor | Tested values | Other factors |
| --- | --- | --- |
| Mutation probability | 0%, 10%, 30% | Population 100, food 150 |
| Population | 50, 100, 150 | Mutation 10%, food 150 |
| Food supply | 75, 150, 225 | Mutation 10%, population 100 |

The standard is shared across the three comparisons. Four new seeds
(**901–904**) each train for **five generations**, including the founders and
four reproduction cycles, at every setting. All final-cohort brains are copied
into fresh bodies in a separate `step14:validation` seed namespace. No weights
change during validation. Within each setting, evolved and random-moving
creatures start with identical bodies and food. Mutation and food variants at
the same population size share their founder brains. Mutation variants also
share all generation-start layouts.

The random controller does not learn, so it needs one validation episode per
seed/population/food combination. These exact baseline outcomes are reused across
mutation settings, without increasing the independent sample count. The default
study therefore runs **188 unique cohorts**: 140 training, 28 evolved validation,
and 20 random validation cohorts. CPU workers change execution speed; physics
always advances in fixed 1/60-second ticks.

Population experiments keep the **arena and maintained pellet count fixed**.
Food is replenished as before. Changing population changes density, food per creature, the founder sample,
and the number of training lives. At five generations, a population of 50 uses
250 training lives per seed, while 150 uses 750. These results describe the total
effect of changing population in this world, rather than isolating a pure benefit
from genetic diversity or equal computation budgets. Matched random controls
provide ecological context for the evolved results.

The report contains fitness, survival to age 60 seconds, food consumption, and
mean survival age. Each setting has seed-paired summaries for:

- Evolved minus its matched random controller.
- Evolved performance minus evolved performance at the standard setting.
- The change in the evolved-minus-random gap relative to the standard.

Intervals are **95% pointwise percentile bootstrap intervals**, resampling four
independent seed pairs, with 20,000 resamples. They are approximate and are not
corrected across settings or metrics. There are **no significance decisions or
confirmed winners** in this exploratory sweep. Using validation results to choose
parameters would require new independent confirmation runs before making a
general improvement claim. Step 14 uses its own seeds, five-generation budget,
standard, and baselines; the earlier Step 13 benchmark remains a separate study.

This one-factor-at-a-time design measures effects conditional on the standard.
It cannot estimate interactions or identify a global optimum; see
[NIST's explanation of the OFAT limitation](https://www.itl.nist.gov/div898/handbook/pri/section2/pri212.htm).
The interactive world accepts combined changes, while the sweep keeps each
variation to one factor so the reported design remains explicit.

You can supply other levels and seeds before running, for example:

```sh
python experiment_parameters.py --seeds 11 22 33 44 --generations 5 \
  --mutation-rates 0 0.05 0.1 0.3 --populations 50 100 150 \
  --food-counts 75 150 225 --workers 4 --output .cache/custom-sweep.json
```

The standard is always included. Reports save the planned protocol and raw
training/validation summaries, matching and genome hashes, cached controls, and
paired estimates. Progress reports remain `running` until all planned settings
and seeds are complete. Incomplete studies cannot be plotted.

Regenerate a figure from the saved data:

```sh
python plot_parameters.py results/step14-parameters.json \
  --output .cache/parameters.png
```

Top panels show evolved and random validation fitness, with individual seed
outcomes and mean curves. Bottom panels show evolved-minus-random fitness with
paired intervals. PNG, SVG, and PDF exports are supported.

The [recorded four-seed pilot](results/step14-parameters.json) completed all
**188 unique cohorts**. Its validation fitness means were:

| Variation from standard | Evolved | Random | Evolved minus random |
| --- | ---: | ---: | ---: |
| Standard: 10% mutation, population 100, food 150 | 273.06 | 317.37 | -44.31 |
| Mutation 0% (selection and inheritance only) | 286.01 | 317.37 | -31.36 |
| Mutation 30% | 278.50 | 317.37 | -38.88 |
| Population 50 | 260.16 | 330.86 | -70.70 |
| Population 150 | 267.79 | 313.51 | -45.72 |
| Food 75 (scarce) | 99.94 | 105.73 | -5.78 |
| Food 225 (rich) | 431.82 | 479.54 | -47.72 |

Zero mutation had the highest observed fitness among the three mutation rates,
12.95 points above standard; the pointwise paired interval was [1.46, 24.43].
The 30% rate was 5.44 points above standard with interval [-15.35, 25.53]. This
short pilot does not establish an optimal rate. Population changes to 50 and 150
had intervals crossing zero for their evolved-fitness changes from standard.

Food supply produced the largest observed fitness shifts in these tested ranges.
Moving from 75 to 225 pellets increased evolved survival to age 60 seconds from
**17.5% to 96.5%**, and mean meals from **5.32 to 34.55**. Random movement also
benefited from richer food. Every tested setting still had a negative average
evolved-minus-random fitness gap, so this sweep did not find a setting with a
positive mean advantage over that baseline.

![Mutation, population, and food-scarcity effects with paired uncertainty](results/step14-parameters.png)

## Compare evolved and random creatures

Run the default comparison with four CPU processes:

```sh
python compare_creatures.py --workers 4 \
  --output .cache/comparison.json --plot .cache/comparison.png
```

The default protocol uses **eight independent training seeds** (101, 202, 303,
404, 505, 606, 707, 808), **ten training generations**, and **100 creatures per
cohort**. All seeds, generation counts, metrics, and decision rules are fixed
before running. There are three conditions:

| Condition | Behavior and reproduction |
| --- | --- |
| Evolved | Neural control; top-20% selection, inheritance, and the existing mutations |
| Random | The original random steering and cruising speed; brains are ignored |
| Unselected NN | The same neural architecture as evolved creatures, with fresh random weights each generation and no inheritance |

`World(evolution_enabled=False)` samples fresh brains when advancing generations;
the `evolution_enabled` report field records this policy.

Each condition occupies its own 100-creature arena. All conditions start each
training generation with identical physical traits, positions, and food. Their
seed streams are matched. Eating and replenishment
subsequently follow each condition's own behavior, so later food layouts can
diverge. The two neural conditions begin with identical founder brains. Only
brains are inherited; body traits are freshly sampled as before.

Each condition runs the same number of complete cohorts under the same lifespan
bound, arena, food supply, energy costs, and fitness rule. Random steering uses
the existing fixed cruising speed; neural controllers can also choose throttle.
The unselected neural control helps separate the effect of evolution from this
difference in movement capabilities.

After training, **all 100 brains from the final birth cohort** are copied into
new bodies in a fresh test arena. Its seed is derived from the training seed in
a separate `step13:held-out` namespace. The test arena has matched starting
conditions across all three groups. Evaluation uses no selection, reproduction,
mutation, or weight updates. Genome hashes verify that training and test weights
stay frozen. No best creature, generation, or seed is chosen using test results.

The default experiment runs **240 training cohorts and 24 test cohorts**. It can
take several minutes. `--workers` controls parallel CPU processes; the default is
one. Results are reproducible across worker counts. Explicit seeds and budgets
can also be supplied, for example:

```sh
python compare_creatures.py --seeds 11 22 33 44 55 66 77 88 \
  --generations 10 --workers 4 --output .cache/another-comparison.json
```

Use at least two distinct seeds and two generations. Choose the budget before
examining outcomes. Reports include the planned protocol, every training/test
summary, initial-condition hashes, frozen-genome hashes, and statistical results.
A progress file is updated after each seed finishes all conditions. Its status
stays `running` until **all planned seeds** complete; partial experiments are not
analyzed or plotted.

The independent experimental unit is **one training seed**, yielding eight
paired observations per contrast in the default experiment. Creatures within a
cohort share ancestry and competition and are not treated as independent trials.
The primary outcome is **held-out mean fitness**. Secondary outcomes are survival
to age 60 seconds, meals per creature, and mean survival age.

For each contrast (evolved minus random, evolved minus unselected NN), the report
estimates the mean paired difference and a **95% percentile bootstrap interval**
from 20,000 resamples of whole seed pairs. Pairing follows the method described in
the [SciPy bootstrap documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html).
These intervals are pointwise and approximate, especially with eight pairs.

The two fitness contrasts also use an **exact two-sided paired sign test**,
excluding ties, following [NIST's sign-test description](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/signtest.htm).
It tests directional consistency across runs; the bootstrap interval separately
describes the average effect. **Holm correction** adjusts the two fitness p-values
as one family, using the method documented by [R stats](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/p.adjust.html).
The declared decision is `higher` or `lower` only when the adjusted p-value is
below 0.05 and the mean-difference interval lies entirely on that side of zero.
Otherwise it is `inconclusive`. Secondary metrics remain descriptive and their
intervals are not corrected for multiple comparisons. The implementation uses
NumPy and Python's standard library; SciPy is not an additional dependency.

This is a small pilot with one held-out arena per training seed. An inconclusive
result does not establish equivalence, and a positive result would apply to this
world, controller, and training budget. Broader layout coverage and larger
independent samples would be needed for stronger general claims.

Export a figure from a completed report without repeating the simulation:

```sh
python plot_comparison.py results/step13-comparison.json \
  --output .cache/comparison.png
```

The top panels show each seed's paired held-out fitness, survival, and meals;
diamonds show means. The bottom panels show paired differences and bootstrap
intervals. Survival differences use **percentage points**. Positive differences
favor evolved creatures. PNG, SVG, and PDF exports are supported.

The [recorded pilot report](results/step13-comparison.json) completed all eight
planned seed trials and all 264 cohorts. Held-out outcomes averaged across seeds:

| Condition | Mean fitness | Reached age 60s | Meals / creature | Mean survival |
| --- | ---: | ---: | ---: | ---: |
| Evolved | 297.36 | 78.75% | 22.01 | 77.29 s |
| Random | 327.18 | 83.00% | 24.72 | 79.97 s |
| Unselected NN | 138.63 | 44.25% | 7.92 | 59.48 s |

| Held-out fitness contrast | Mean difference | 95% paired bootstrap interval | Holm p | Decision |
| --- | ---: | --- | ---: | --- |
| Evolved minus random | -29.83 | [-57.89, -2.03] | 0.2891 | Inconclusive |
| Evolved minus unselected NN | +158.73 | [130.68, 183.83] | 0.0156 | Higher |

Evolved brains beat the unselected neural control in **8/8** seed pairs, showing
a measurable improvement for this neural architecture. They beat random movement
in **2/8** pairs and had lower observed mean fitness. The mean-difference interval
for that contrast is below zero, but the directional sign test did not meet the
declared threshold, so its formal decision remains inconclusive. This pilot
does **not demonstrate an advantage over random movement**.

![Paired held-out outcomes and uncertainty across eight independent seeds](results/step13-comparison.png)

## Visualize evolution

Press **T** to see all three generation plots and the latest eight completed
generations in a table. Fitness shows **mean and best scores**. Food consumption
shows **mean pellets eaten per creature**, counting the whole starting population.
Survival shows the **percentage of the starting population that reaches age 60
simulated seconds**, including creatures that die exactly at that age:

```text
survival rate = creatures reaching age 60 seconds / starting population
```

This checkpoint stays fixed across generations. The percentage axis spans
0–100%; the rate is distinct from mean survival age and the final living count.
All generations eventually become extinct, but their checkpoint survival rates
can differ. Survival is measured from actual creature ages and adds no fitness
bonus or change to selection.

The saved ten-generation seed-42 example includes a standalone figure:

![Fitness, survival rates, and food consumption across generations](results/step12-evolution.png)

Regenerate this figure from its saved observations without running the simulation:

```sh
python plot_evolution.py results/step12-seed42.json --output .cache/evolution.png
```

Or collect observations and export a figure from a new run:

```sh
python main.py --headless --seed 42 --generations 10 --speed 20 \
  --report .cache/evolution.json --plot .cache/evolution.png
```

`--plot PATH` exports on exit. PNG, SVG, and PDF are supported, using a headless
Matplotlib canvas that opens no additional window. The standalone command accepts
`--output PATH`; without it, output uses the report's name with a `.png` extension.
Only completed generations are plotted. A run ending before any generation
completes reports that its plot was skipped; the standalone command rejects an
empty report.

New JSON reports use **format version 2**, adding `survival_checkpoint_seconds`,
`survivors_at_checkpoint`, and `survival_rate` to every generation. Existing
version-1 reports remain plottable for fitness and food consumption; their
unrecorded survival data is shown as unavailable. Rates are never inferred from
mean age or replaced with zero. Exported charts use actual generation numbers,
so gaps in recorded generations retain their spacing.

Each figure describes one run. Lines join recorded observations; they are not
smoothed fits or averages across independent runs, and contain no uncertainty
bands.

## Multiple generations

Automatic cycling is on by default. When a population becomes extinct, its final
results are recorded and its selected parents produce the next generation.
Use **A** or `--manual` to wait between generations and review results before
pressing **N**. **Space** freezes survival and automatic generation transitions. Increasing
speed runs more fixed 1/60-second ticks per frame; the physics step stays the same.

Run a fixed number of generations while watching the world:

```sh
python main.py --seed 42 --generations 10 --speed 20
```

After generation 10 completes, the simulation stops advancing and opens history.
The window remains open for inspection; **R** starts a new run with the same
generation limit and speed. With no generation limit, automatic cycling continues
until you close the window. **N** cannot advance beyond a configured limit.

To complete the same run without opening a window and save its observations:

```sh
python main.py --headless --seed 42 --generations 10 --speed 20 \
  --report .cache/generations.json --screenshot .cache/generations-preview.png
```

Headless mode exits when the generation target is complete. If `--frames` is also
given, whichever limit is reached first ends the run. Headless manual mode needs
`--frames`, because keyboard input cannot advance its generations.

The **T** history panel plots mean/best fitness, survival to 60 seconds, and mean
meals over all completed generations, with a table of the latest eight.
Incomplete generations are excluded.
The table also shows mean survival age, mean commanded speed weighted by actual
time alive, and the fraction of visible-food time spent facing the nearest pellet
within **±45 degrees**. This last measure samples heading before movement at each
tick, weighted by actual creature-time alive, including partial final ticks.
It displays **N/A** when no food was visible. These observations add no fitness
reward and do not change movement decisions or random streams.

The history and fitness panels keep the simulation running behind them; pause
to inspect at leisure. They are mutually exclusive and block arena clicks while
open. Restart clears both histories and total simulation time while preserving
pause, speed, auto/manual mode, generation limit, and display preferences.

`--report PATH` writes JSON on exit, containing the seed, controller, mutation
settings, fixed timestep, target, completed count, total simulated time, and one
statistics record per completed generation. Reports also include raw visible-food
and facing-food creature-seconds. An interrupted run can contain a partial current
generation in total time, but only completed generations have statistics records.
`World.generation_stats` holds immutable records; `EvolutionSimulation` in
`simulation.py` handles timing, automatic cycles, limits, and reports.

Facing food is a descriptive orientation measure, not proof of food seeking.
Food layout, body traits, competition, and chance vary between generations. A
single seeded trajectory can show changes. The independent comparison above
tests whether improvements extend to held-out arenas and control conditions.

The recorded [seed-42 example](results/step12-seed42.json) completed ten
generations with the default neural controller and mutation settings:

| Observation | Generation 1 | Generation 10 |
| --- | ---: | ---: |
| Mean fitness | 148.36 | 297.50 |
| Mean meals per creature | 8.65 | 21.92 |
| Mean survival | 61.86 s | 78.30 s |
| Reached age 60 seconds | 44% | 82% |
| Mean commanded speed | 30.82 px/s | 52.76 px/s |
| Facing visible food | 28.30% | 28.06% |

Feeding and survival increased in this run, while food-facing time stayed close
to its starting level. Results fluctuated between generations rather than
improving on every cycle. These observations do not yet establish reliable
food-seeking behavior or an advantage over random movement.

## Creatures

Each creature has a unique ID within its population and these initial properties:

| Property | Initial value |
| --- | --- |
| Position | Random, fully inside the arena, with space between creatures |
| Body radius | Random integer from 6 to 9 pixels |
| Color | Random choice of six pastel colors; appearance only |
| Facing direction | Random angle around the full circle, shown by the white eye |
| Maximum speed | Random value from 40 to 80 pixels per second |
| Current speed | Neural throttle selects 0–100% of maximum speed |
| Energy | 100 initially, capped at 100; food restores up to 20 per pellet |
| Hunger | Energy deficit from 0% full to 100% empty |
| Age | 0 simulated seconds initially |
| Lifespan | Seeded random value from 60 to 120 simulated seconds |
| Food eaten | 0 initially; incremented once per consumed pellet |
| Fitness | 0 initially; survival seconds plus 10 points per eaten pellet |
| Generation | 1 for random founders; increases when selected parents reproduce |
| Parent | None for founders; previous generation's selected parent ID for offspring |
| Mutations | Number of parameters actually changed during birth; 0 for founders |

The selected creature has a white ring, and its properties appear below the arena.
The first creature is selected initially. Pause with **Space** to inspect a
creature while it holds still. Its inspector shows energy, hunger, age/lifespan,
food count, fitness, generation, parent, mutation count, position, current/maximum
speed, size, facing direction, and turn rate.
Small energy bars below creatures change from green to amber to red as hunger
increases.

## Fitness and natural selection

The starting scoring rule is:

```text
fitness = 1 * simulated seconds alive + 10 * food pellets eaten
```

For example, a creature that survives 40 seconds and eats 3 pellets earns 70
points. Survival uses each creature's actual age, including partial final steps.
Food rewards count consumed pellets, including meals that restore only part of
their energy because of capacity. Remaining energy adds no separate bonus.

Scores update as living creatures age and eat. A dead creature keeps its earned
score; continued world time does not increase it. Rankings include both living
and dead creatures, ordered by descending fitness. Exact score ties use the lower
creature ID, keeping results reproducible.

During a run, rankings are **provisional** and candidate selection is pending.
When the population becomes extinct, the world freezes the final ranking and
selects the top **20%**, rounding up for small populations: 20 candidates from the
usual 100. These IDs identify the retained creature/brain records used for reproduction.

The header shows best and mean fitness across the entire original population.
Clicking a living creature shows its individual score. **F** opens the top-ten
leaderboard with survival time, meals, score, and live/dead or selected status.
The world continues while the leaderboard is open; use **Space** to pause. Close
the leaderboard before selecting creatures in the arena.

Completed generations retain their best result and selection count in history.
Automatic mode breeds the next generation; **N** does so in manual mode.
**R** restarts with random founders. Ranking and drawing the
leaderboard do not change movement, randomness, food, or brain parameters.

The code exposes live or final immutable snapshots through
`World.get_fitness_evaluation()`. Its `ranking` contains every evaluated creature,
and its `selected_ids` is populated only for completed runs.
`World.final_evaluation` retains the final snapshot until breeding or reset.
`World.generation_history` keeps one immutable final evaluation per completed
generation until restart. The default rule and selection fraction are defined in
`selection.py`.

## Reproduction and mutation

Generations run separately. Once all creatures die, final results are recorded
before the next population is born. Automatic cycling breeds on the next tick;
manual mode waits for **N**, which also works while viewing the leaderboard.
Pressing **N** during a living generation has no effect.

With the default population, **20 selected parents produce five offspring each**,
rebuilding the population to **100**. Other sizes use the same rounded-up 20%
selection rule and balance offspring across parents. Birth slots are shuffled to avoid associating parent rank
with particular body positions. Each offspring receives an independent copy of
one parent's complete network: all **90 weights and biases**. Reproduction is
asexual, without crossover or gradient training.

Every parameter independently has a **10% mutation probability**. A mutation
adds Gaussian noise with **mean 0 and standard deviation 0.1**. About nine
parameters per offspring change on average; the actual count varies, and an
offspring can receive no mutations. Parents and siblings never share parameter
arrays. Parameters remain fixed throughout each creature's lifetime.

Only the brain is inherited. New bodies receive fresh positions, colors, sizes,
headings, speed limits, and lifespans. Energy starts at 100, and age, meals, and
fitness start at zero. Food and per-generation counters also restart. The
inspector shows the creature's generation, its parent's generation and ID, and
the number of changed parameters. IDs are local to each generation.

The founding seed and generation number determine separate random streams for
bodies, food, steering, and mutations. Repeating the same seed, controller, and
generation sequence reproduces the same results; waiting longer on the final
results screen does not change offspring. **R** chooses a new founding seed and
returns to generation 1. Pause and display settings survive both controls.

Programmatically, `World.advance_generation()` returns `True` when reproduction
succeeds and `False` while the generation is incomplete. `World` accepts
`mutation_rate` (0–1) and `mutation_scale` (finite, non-negative) for controlled
checks. Setting either to zero creates exact, independent brain copies.
`reproduction.py` handles parent allocation and birth records, while
`NeuralNetwork.mutated_copy()` implements inheritance and mutation.

The random movement controller can also advance generations, but it continues to
ignore inherited brains when choosing movement. Evolutionary improvement is a
question for repeated experiments; reproduction alone does not establish it.

## Sensory perception

Each creature senses food centers within a **160-pixel radius in all directions**.
It observes the nearest visible pellet, including its position, Euclidean distance,
relative bearing, and the total number of nearby pellets. Direction is measured
from the creature's current heading: 0 degrees is ahead, positive angles are to
the right, and negative angles are to the left. Bearings wrap into [-180, 180)
degrees, with directly behind represented as -180 degrees.

Distance becomes a proximity signal, `1 - distance / 160`, so closer food gives a
stronger signal. Direction becomes `bearing / pi`, in [-1, 1]. A visibility flag
distinguishes food at the range boundary from an absence of food. With no visible
food, distance and bearing are absent and all three food signals are zero. Food
at the creature's center has distance 0 and neutral bearing 0. Equal-distance
pellets retain their list order when choosing the nearest.

Click a creature to inspect its current reading in the header. The overlay shows
its sensing radius, a short forward-facing line, and a line to the nearest food,
which is marked with a ring. **V** controls this visualization; sensing and brain
decisions continue when it is hidden. The overlay is clipped to the arena.

`World.perceive_food()` returns a read-only observation of the current world.
Readings are recomputed after food changes, so removed pellets do not remain as
stale targets. The brain uses the same perception function at the beginning of
each simulation step; the display shows the current view after movement/eating.

## Artificial brains

Every creature owns an independent **8-input, 8-hidden, 2-output** feed-forward
network. NumPy matrix multiplication and `tanh` activations compute each decision.
The network has **90 parameters**, including biases. Founders receive random
parameters; descendants inherit mutated copies from selected parents. Parameters
remain fixed during each creature's lifetime.

The eight inputs, in order, are:

| Input | Meaning and range |
| --- | --- |
| Food proximity | `1 - distance / 160`, from 0 at range limit to 1 at the creature's center |
| Food direction | Relative bearing divided by pi, from -1 to 1 |
| Food visible | 1 when food is within 160 pixels, otherwise 0; absent food signals are also 0 |
| Hunger | Energy deficit, from 0 full to 1 empty |
| Wall forward | Radius-aware forward wall distance, clipped to 160 pixels and divided by 160 |
| Wall right | The same normalized distance to the right |
| Wall back | The same normalized distance behind the creature |
| Wall left | The same normalized distance to the left |

The first two channels now encode explicit proximity and bearing, replacing the
earlier forward/right offsets while retaining the 8–8–2 network. A wall input of 0
means the body is touching that wall; 1 means at least 160 pixels of clearance in
that direction. Sensors update in the creature's current orientation.

```text
hidden = tanh(inputs @ input_weights + hidden_bias)
outputs = tanh(hidden @ output_weights + output_bias)
turn_rate = outputs[0] * 90 degrees/second
throttle = (outputs[1] + 1) / 2
speed = throttle * maximum_speed
```

The first output chooses left/right turning; the second chooses forward speed.
Zero outputs mean straight movement at half maximum speed. Neural decisions run
once per fixed simulation step. Food information reaches movement through the
network's parameters, which may produce useful or unhelpful actions. The brain
label and the selected creature's current speed and turn rate
make the active controller visible.

The random mode retains the earlier gradual random steering and cruising speed.
Both modes start with the same physical traits, food, and seeded network
parameters for a given seed. Both use the same fitness rule. Comparisons across
independent runs are available through `compare_creatures.py`.

## Survival

Energy use is charged per simulated second:

```text
energy cost = 2 + 0.05 * movement speed
```

With neural speeds of 0–80 pixels per second, creatures spend 2–6 energy units
per second. A stationary creature still spends 2 units per second. Food restores
energy up to a capacity of 100. Hunger is `1 - energy / 100`: creatures are hungry
at 50% deficit and starving at 80% deficit. Hunger is also a neural sensory input.

Age advances with simulated time. Each creature has a seeded lifespan of 60–120
seconds. Energy exhaustion causes starvation death; reaching lifespan causes
old-age death, even with energy remaining. If both limits fall inside a step,
the earlier one determines the cause. Age stops at the moment of death.

Every fixed step chooses motor commands, charges energy for the newly chosen
speed, advances age, removes fatal creatures, then moves and feeds survivors.
A creature with positive energy can recover by eating; one that has already died
cannot move, eat, or revive. Death reduces the
population. Final creature states remain in `World.dead_creatures` until breeding
or reset; final fitness snapshots remain in generation history until reset.

The header shows living creatures, hungry creatures, total deaths, and the
starvation/old-age breakdown. An extinct population shows final fitness and
selection results in manual mode or after reaching a generation target. Automatic
cycling breeds offspring; **N** does so manually. **R** starts again with random
founders. Each new population has its configured number of living creatures with zero scores and
deaths. Pause freezes the full simulation,
including hunger, lifespan, and earned fitness.

## Food and eating

By default, the arena starts with 150 green diamond-shaped pellets, each with a collision
radius of 3 pixels and an energy value of 20. Food spawns fully inside the arena,
clear of creatures and other pellets.

Each simulation step checks circle contact using both the creature's and the
pellet's radius. A living creature with room for energy gains up to 20 on contact.
Its food counter increases, and the pellet is removed. If multiple creatures touch one
pellet and can eat, the nearest center wins; an exact distance tie uses the lower
creature ID. Each pellet awards energy only once. A full or dead creature leaves
the food available.

After all contacts are resolved, eaten pellets are replaced at random free
positions, maintaining the configured supply (150 by default). Replacements start clear of creatures
and are eligible for eating on subsequent steps. The header shows available food
and total meals eaten; selecting a creature shows its individual meal count.

Creatures eat food they encounter while following the active controller.
Meals eaten by creatures that later die remain included in the total meal count.

## Movement

Each creature travels forward at its commanded speed and rotates at its commanded
turn rate, bounded to -90 through +90 degrees per second. In neural mode, its
network chooses both commands. In random mode, the creature cruises at its
initial speed and chooses a new random turn rate approximately every 0.75 to 2
seconds.

Creatures bounce off all four walls. Wall contact reflects their direction and
keeps their full body inside the arena, accounting for body radius and any travel
remaining after the impact. Corner hits reflect both direction components.
Creatures move independently and may pass through one another after spawning.

Movement advances in fixed 1/60-second simulation steps, independently of display
frame rate. The footer shows elapsed simulation time. Long desktop frame stalls
are capped at 0.25 seconds of catch-up to avoid a large jump. Pausing freezes
movement, eating, energy use, aging, and simulation time. **R** resets time and
generates a fresh population and food supply, preserving the current pause state.

Use a seed to reproduce a population and its movement at the same simulation time:

```sh
python main.py --seed 42
```

Without `--seed`, startup chooses a random seed. The active seed is displayed in
the footer. **R** chooses a new seed and resets the configured birth population.
Initial physical traits, food, and random steering keep separate seed streams.
Brains are sampled with a NumPy generator after physical traits are created.
The seed recreates their parameters as well as the initial world. Food availability
can now affect both neural decisions and survival.

To render a few frames without opening a window, optionally saving a preview:

```sh
python main.py --headless --frames 120 --seed 42 --screenshot .cache/reproduction-preview.png
```

Headless mode requires `--frames` or automatic `--generations` so it exits on its
own. At the default 1x speed it advances one 1/60-second simulation tick per frame,
without waiting for real time. At 5x or 20x it advances five or twenty ticks per
frame, stopping early if its generation target is reached. The command above
captures the world after 2 seconds of simulated life at 1x.

Run all checks with the standard Python test runner:

```sh
python -m unittest discover -v
```

Verified: **227 checks**, including source-model reuse, deterministic founder
reconstruction, paired sensor interactions, complete factorial conditions,
cross-lineage layout exclusion, numerical probes, twelve-test correction,
archive/input preservation, incomplete-report rejection, reproducible parallel
results, and PNG/SVG/PDF exports. The pre-Step-17 212-test transcript is saved.

The checks also include fixed speed and per-second energy fairness,
greedy target selection and bounded turns, successful greedy feeding, clustered
spawning and replenishment, unchanged default throttle, retraining and model
reuse, repeated matched held-out worlds, lineage-level inference, Holm correction
across nine primary comparisons, numerical ties, and plot exports. The 193-test baseline was
recorded before Step 16 changes. The checks also include frozen-model round trips, repeated unseen
arenas, truthful observations during sensor interventions, matched conditions,
lineage-level inference, all four decision gates, reproducible model reuse, and
PNG/SVG/PDF exports. A controlled food-seeking brain verifies that the movement
and sensor intervention can distinguish successful guidance from mirrored
guidance; this hand-built brain is used only in tests, never in the study.

The Step 15 report passed a completeness audit, and its stored analysis matches
fresh recomputation exactly. All eight saved model archives reproduce their
genome hashes and steering probes. The exported figure was visually inspected.

The checks also include population sizes 1, 7, 50, and 150 across
generation changes and restart; configured survival denominators; parameter CLI
validation; matched/frozen validation; random-control reuse; reproducible sweeps;
and exploratory paired summaries and exports. A native macOS run verified custom
parameters, and a full default seed-42 generation exactly reproduced every
recorded Step 12 observation.

The Step 14 dataset contains all 188 planned unique cohorts; population counts,
survival denominators, frozen validation, cached controls, score components,
and completeness were audited. Its stored summaries match fresh recomputation
exactly, and its exported parameter plots were visually inspected.

Step 13 also recorded a complete eight-seed, 264-cohort benchmark. The
saved dataset passed fairness and completeness audits, and its stored analysis
matches recomputation exactly. Comparison checks cover matched cohorts and fresh test
arenas, all-population frozen-genome evaluation, reproducible serial/parallel
results, complete-run requirements, paired resampling, ties, exact sign-test
probabilities, Holm adjustment, positive/negative/inconclusive decisions, and
PNG/SVG/PDF exports. The earlier ten-generation visualization and native macOS
Cocoa checks remain covered by the preceding steps. Every previously recorded
fitness, feeding, and behavior observation matched Step 11 exactly in Step 12.
Plot checks cover checkpoint boundaries and the full-population denominator,
curve values, generation spacing, 0–100% survival limits, missing legacy data,
empty reports, PNG/SVG/PDF output, and plotting without changing future offspring.

Cycle checks cover exact limits,
time carried across generation boundaries, matching results across frame rates
and speed settings, pause/manual/restart behavior, actual-time-weighted behavioral
measurements, keyboard controls, and bounded headless reports.

Reproduction checks cover independent copies of every weight and bias, mutation
settings, deterministic offspring, balanced parent allocation, selected-parent
inheritance, newborn survival resets, repeated generation transitions, history,
restart, and preservation of pause/display settings and random movement mode.
Existing fitness, perception, neural, movement, food, and survival checks remain
included.

## Project structure

```text
main.py               Window, controls, simulation timing, and launch options
world.py              One-generation physics, observation, survival, food, and fitness
simulation.py         Automatic cycles, speed, generation limits, restart, and reports
generation_stats.py   Immutable completed-generation behavioral observations
plot_evolution.py     Matplotlib fitness, checkpoint survival, and food plot exports
compare_creatures.py  Paired training/test experiments and seed-level statistical analysis
plot_comparison.py    Held-out comparisons and paired-difference uncertainty plots
experiment_parameters.py  Paired mutation/population/food exploration and summaries
plot_parameters.py    Parameter-response curves and paired validation fitness gaps
analyze_intelligence.py  Frozen models, repeated unseen tests, sensor controls, and steering probes
plot_intelligence.py  Food-direction benefits and corrected operational evidence
experiment_speed.py   Fixed-speed retraining, greedy/random controls, and 16-seed held-out study
plot_speed.py         Paired fitness, meals, and survival comparisons at equal speed
experiment_strategy.py  Saved-brain sensor interventions, ancestral controls, and attribution tests
plot_strategy.py      Food-bearing benefits and residual evolutionary-history comparisons
creature.py           Creature state, motor controls, survival, drawing, and spawning
brain.py              NumPy network, inference, independent copies, and mutation
reproduction.py       Balanced selected-parent reproduction and offspring records
perception.py         Read-only food distance, direction, visibility, and neural signals
selection.py          Fitness formula, immutable rankings, and final candidate selection
food.py               Food properties, circle collision checks, and drawing
test_movement.py      Movement, boundary, timing, pause, and reproducibility checks
test_food.py          Food generation, contact, meal accounting, and reproducibility
test_survival.py      Energy, hunger, aging, death, extinction, and reset checks
test_brain.py         Network math, sensors, motor commands, and seeded brain checks
test_perception.py    Perception geometry, edge cases, brain inputs, and overlay checks
test_selection.py     Scores, ranking, final selection, immutability, and reset checks
test_reproduction.py  Brain inheritance, mutation, lineage, and generation transitions
test_simulation.py    Automatic cycles, timing, behavioral metrics, controls, and reports
test_plot_evolution.py  Checkpoint accounting, plotted values, missing data, and export
test_comparison.py    Matched controls, frozen evaluation, independent pairs, and inference
test_parameters.py    Configurable populations, controlled sweeps, caching, and validation
test_intelligence.py  Sensor truth, positive controls, archives, repeated trials, and criteria
test_speed.py         Speed/energy fairness, greedy guidance, clustered food, and study inference
test_strategy.py      Source preservation, factorial controls, paired interactions, and probes
results/step11-seed42.json  Observations from one seeded ten-generation run
results/step12-seed42.json  Repeated seed-42 trajectory with checkpoint survival rates
results/step12-evolution.png  Exported fitness, survival, and food-consumption figure
results/step13-comparison.json  Protocol, training/test data, and paired inference
results/step13-comparison.png  Held-out outcomes and paired difference intervals
results/step14-parameters.json  Exploratory protocol, raw data, and paired estimates
results/step14-parameters.png  Parameter effects on evolved and random fitness
results/step15-intelligence.json  Full emergent-behavior protocol, trials, probes, and inference
results/step15-intelligence.png  Food-guidance effects and generalization evidence
results/step15-models/  Eight verified frozen founder/evolved model archives
results/step16-baseline.json  Pre-change commit and source/result hashes
results/step16-baseline-tests.txt  Original 193-test baseline transcript
results/step16-tests.txt  Full 212-test verification transcript
results/step16-audit.json  Completeness, source/model/data hashes, runtime, and recomputation audit
results/step16-protocol.json  Protocol and source hashes recorded before trials
results/step16-numerical-ties.json  Pre-result numerical sign-test tie correction
results/step16-speed-comparison.json  Fixed-speed training, held-out trials, and paired inference
results/step16-speed-comparison.png  Fitness, meals, and survival in three environments
results/step16-models/  Sixteen frozen populations retrained at identical speed
results/step17-baseline.json  Hashes of every pre-Step-17 tracked file
results/step17-baseline-tests.txt  Passing 212-test baseline transcript
results/step17-tests.txt  Full 227-test verification transcript
results/step17-audit.json  Prior-file preservation, model/probe reproduction, and analysis audit
results/step17-protocol.json  Pre-trial source/model hashes, contrasts, and layout exclusions
results/step17-strategy.json  Complete sensor-intervention trials, probes, and paired analysis
results/step17-strategy.png  Food-bearing and residual fitness evidence
results/step17-unselected-models/  Sixteen exact reconstructed ancestral cohorts
check_environment.py  Numerical and graphics dependency check
requirements.txt      Pinned Python dependencies
.python-version       Python version selection
.gitignore            Local environment and cache exclusions
```

## Environment

Use Python 3.13 and a local virtual environment. The project uses:

- NumPy for neural networks and sensory calculations.
- Pygame for the 2D world display.
- Matplotlib for generation charts exported as PNG, SVG, or PDF.

The installed package versions, including their dependencies, are pinned in
`requirements.txt`. No external AI service or GPU is needed.

## Setup

Run these commands from this project folder on macOS or Linux:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python check_environment.py
```

The virtual environment is already prepared on this machine. To use it in a new
terminal session:

```sh
source .venv/bin/activate
python check_environment.py
```

In an editor, select `.venv/bin/python` as the Python interpreter.

The check exercises NumPy calculations, Pygame's headless display, and Matplotlib
PNG rendering. It opens no window and runs no simulation. A successful run ends
with `Environment ready.`

Official installation references: [NumPy](https://numpy.org/install/),
[Pygame](https://www.pygame.org/wiki/GettingStarted), and
[Matplotlib](https://matplotlib.org/stable/install/).
Pygame's [display documentation](https://www.pygame.org/docs/ref/display.html)
describes the window and coordinate system used here.
