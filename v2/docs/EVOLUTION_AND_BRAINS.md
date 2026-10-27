# Evolution and artificial brains

[Documentation](README.md) · [Modes](SIMULATION_MODES.md) · [Measurements](RESEARCH_AND_VALIDATION.md)

The experiment asks whether inherited variation and differential reproduction produce useful behavior. Founders have random neural weights, local observations and no explicitly programmed food-seeking policy. Their brains do not train by backpropagation during a lifetime. Adaptation occurs through inheritance, selection and mutation across births or replacement cohorts.

## Perception and decisions

The ordinary network is a feed-forward **8 → 8 → 2** NumPy network with 90 scalar weights/biases. Hidden and output activations use `tanh`:

```text
hidden  = tanh(inputs @ input_weights + hidden_bias)
outputs = tanh(hidden @ output_weights + output_bias)
```

| Ordinary input | Meaning |
| --- | --- |
| `food_proximity` | `1 − distance / sensory_range`, bounded to [0, 1] |
| `food_direction` | Relative bearing / π, in the wrapped left/right interval |
| `food_visible` | Whether nearest food is within sensing range |
| `hunger` | Capacity-normalized energy deficit |
| `wall_forward` | Body-relative forward boundary clearance / sensory range |
| `wall_right` | Right boundary clearance |
| `wall_back` | Rear boundary clearance |
| `wall_left` | Left boundary clearance |

Food sensing covers the full circle; it is not a rendered camera or image-recognition model. The engine chooses the nearest center within range, with stable tie behavior. Ordinary range is 160 px; trait modes use inherited range. Forest meshes, mountains and graphical shadows do not occlude these channels.

Outputs ordinarily represent signed turn and throttle. Turning is bounded by the original maximum rate, π/2 radians/s. Fixed-speed models override variable throttle to maintain matched motor speed across controllers. Trait-based actors use their inherited cruise speed. The default original 2D viewer can expose earlier variable-speed behavior through its own options; V2's RunConfig modes retain the session's existing constraints.

## Mode-specific networks

| Model | Inputs / hidden / outputs | Additional information |
| --- | --- | --- |
| Foraging, seasons, traits, continuous | 8 / 8 / 2 | Ordinary channels |
| Obstacles | 16 / 8 / 2 | Five obstacle rays; hazard proximity, bearing and overlap |
| Predator–prey | 11 / 8 / 2 | Nearest opponent proximity, bearing and visibility |
| Social | 17 / 8 / 3 | Neighbor state, signals, density, food access; outputs turn, signal and sharing effort |

Different input dimensions mean saved arrays are not interchangeable between modes. A visual wolf is not a distinct brain architecture by itself: Python's predator/prey model determines the actual controller and diet. Physical habitat retains these dimensions and does **not** supply dedicated slope, depth or weather channels.

## Fitness and selection

Ordinary earned fitness is:

```text
fitness = simulated survival age + 10 × meals
```

The score stops accumulating after biological death. Ordinary selection evaluates the complete cohort, orders by fitness and ID, and selects `ceil(population × 0.2)` parents. Offspring slots are balanced across selected parents and shuffled. This is asexual inheritance, not mating, crossover or sexual selection.

Model-specific definitions remain separate:

| Mode | Selection / score difference |
| --- | --- |
| Seasons | Only actors reaching `reproductive_age` can become parents; none eligible means extinction |
| Obstacles | Subtract 2 per collision and 5 per hazard-exposure second |
| Predator–prey | Prey use age + meals; predators use age + 30 × captures; separate parent pools |
| Social | Survival age only; individual selection versus selected groups with team assortment |
| Continuous | No global top-20% replacement; funded local births create differential reproductive success |

An animal that dies before the end of a fixed-window predator/social cohort can still contribute an archived genome to the appropriate selection process. Conversely, a living survivor at the episode horizon is right-censored, not a demonstrated lifelong survivor.

## Neural mutation

An offspring receives independent copies of all four parameter arrays. Each scalar is selected independently with `mutation_rate` (default 0.1); selected values receive zero-mean Gaussian noise with standard deviation `mutation_scale` (default 0.1). Zero probability or zero scale produces no changed weights. Mutation is not an improvement guarantee.

Seeded body placement, food, steering, parent choice and mutation use the engine's established streams. Godot observation, rendering, cameras and export previews do not consume those model streams. Original-rule exports retain their original replay contract.

**Neutral neural** changes parent eligibility to a uniformly sampled subset of all evaluated lifetimes while keeping the same bottleneck size and mutation machinery. It is a genetic-drift control, not random movement. **Frozen founders** retain initial brains without selecting new ones. **Random** and **greedy** use programmed steering and carry unused placeholder arrays; their placeholder arrays are excluded from live neural diversity.

## Body traits and energy

Trait-based modes link brain inheritance to speed, radius and sensory range. With radius `r`, speed `v` and range `s`, the reference model uses:

```text
mass proxy       m = (r / 8)²
capacity           = 100 × m
development cost   = 10 × m
initial energy     = min(capacity, 100 − development cost)
basal power        = 2 × m
movement power     = 2.5 × m × (v / 60)²
sensing power      = 0.5 × (s / 160)²
```

At reference traits (60 px/s, radius 8, range 160), these powers total 5/s. Larger bodies store more energy but cost more to develop and maintain; longer-range sensing and speed have explicit costs. Food assimilation is capped and wasted food energy is recorded.

Body mutation independently selects each trait with `body_mutation_rate` and applies log-space noise of `body_mutation_scale`, clamping to speed 25–100, integer radius 4–12 and range 60–280. Social mode forces body mutation off and uses reference bodies. Continuous clonal mode forces both neural/body mutation probabilities to zero. These are stylized 2D energetics, not measured deer/wolf physiology.

Physical habitat adds its separately recorded slope/water/climate power and ground-speed factors. The baseline motor-cost and speed telemetry meanings are retained; actual travel is recorded in habitat metres. Do not compare a physical run to an original-rule run as though only parent choice changed.

## Continuous reproduction

Continuous actors must meet age, cooldown, energy, space and population-cap constraints. A child receives 40% of its capacity as funded initial endowment; the parent pays that amount plus development and overhead while keeping a reserve. Candidate mutations and failed attempts are recorded. With zero mutation, reproduction still requires resources and can differentially amplify founders.

The genealogical founder label is inherited. The engine also reports genetic summaries/clusters for continuous populations, but thresholds and ancestry do not establish biological species. See [metrics](RESEARCH_AND_VALIDATION.md#metrics-and-their-limits).

## Inspecting a brain

Select an active neural creature and open Research. The eight hidden bars are calculated in Python from the selected actor's current sensory vector and weights. This preview does not issue an extra movement command or consume RNG. Random/greedy controllers do not have a meaningful neural preview.

V2 does not provide a weight editor, training-loss dashboard, memory/recurrent network, or automatic saliency viewer. The preserved Step 20 tools produce richer trajectories, activations and sensory Jacobians from saved populations. [Research](RESEARCH_AND_VALIDATION.md#preserved-study-catalog) links that workflow.

## What would support a learned-strategy claim?

Useful evidence includes improvements over random movement **and** an unselected neural baseline, a contrast with neutral-parent reproduction, matched food/energy/speed budgets, unseen environments, independent training seeds, and sensor interventions. Greedy steering is a positive control for the task, not evolved intelligence.

The existing studies provide such tests under their declared conditions; visual plausibility alone does not. Performance can fail in scarcity, transfer poorly, or reflect general movement rather than food-directed steering. [V1's complete research record](../../README.md) remains the source for numerical findings.
