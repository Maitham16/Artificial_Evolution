# Simulation modes

[Documentation](README.md) · [User guide](USER_GUIDE.md) · [Evolution](EVOLUTION_AND_BRAINS.md) · [Configuration](CONFIGURATION.md)

All seven modes come from the original Python engine. The Godot viewer changes their presentation. Optional physical habitat adds explicitly separate costs/motion rules; it does not create an eighth mode or a new evolutionary algorithm.

## Mode and controller matrix

| Display name | `mode` | Supported `algorithm` values | Episode / reproduction |
| --- | --- | --- | --- |
| Food seeking | `foraging` | `selection`, `neutral`, `random`, `greedy`, `founder` | Complete lifetimes; synchronized replacement |
| Changing seasons | `seasons` | `selection` | Seasonal cohorts; maturity-eligible parents or lineage extinction |
| Obstacles & hazards | `obstacles` | `selection`, `random`, `greedy` | Complete lifetimes with collision/risk costs |
| Brains & bodies | `traits` | `selection` | Joint neural/body inheritance |
| Predator & prey | `predator_prey` | `coevolution` | Fixed-duration cohorts; two separate parent pools |
| Social behavior | `social` | `group`, `individual` | Fixed-duration isolated groups; survival selection |
| Continuous ecosystem | `continuous` | `funded`, `clonal` | Overlapping lifetimes and paid births until duration/extinction |

The interface filters invalid combinations. JSON is validated again by Python before the current run is replaced.

## Food seeking

This is the default model: 100 founders, uniform food, selected neural steering, fixed speed 60 Python pixels/s, five generations. Brains begin as random weights. They receive local food signals, hunger and wall clearances. They are not programmed to move toward food.

Each meal adds up to 20 energy, capped by capacity. Ordinary energy use is `2 + 0.05 × abs(speed)` per simulated second: 5/s at the default fixed speed. Ordinary capacity is 100, with founder lifespans drawn between 60 and 120 simulated seconds. Death ends biological updates. Base fitness is `age + 10 × meals`.

At cohort completion, ordinary selection chooses the top 20% (rounded up), breaking exact ties by ID. Offspring receive copied/mutated brains and fresh physical starting conditions. Live survivors are not simply carried into the next cohort.

| Controller | Meaning |
| --- | --- |
| Selected neural | Fitness-based parent eligibility and inherited mutated brains |
| Neutral neural | Uniform random-parent subset from the complete cohort, retaining parent bottleneck and mutation mechanism |
| Random movement | Existing random-steering controller; no food-directed policy |
| Greedy forager | Explicitly turns toward nearest detected food; a programmed positive baseline |
| Frozen founders | Reuses each original founder brain in fresh cohorts, without selection or brain mutation |

Fixed-speed comparisons constrain neural, random and greedy motor speed equally. Throttle is not a hidden advantage for the neural controller in these runs. Physical habitat can slow actual ground movement separately; record that extension when comparing runs.

Food is replenished after consumption in this mode, so random exploration can earn meals. Compare matched conditions and repeated training seeds rather than interpreting a single increase as proof of learning.

```bash
./"v2/Run Artificial Evolution 2.command" -- --immersive \
  --config="$(pwd)/v2/docs/examples/foraging.json"
```

## Changing seasons

Seasonal mode uses the `seasonal` environment and selected neural brains. Default stock is spring 150, summer 200, autumn 75, winter 25. `season_length=1` changes season every generation; `cluster_shift=120` controls food-cluster movement in original Python coordinates.

Season changes occur **between generations**, not because the decorative clock reaches midnight. Set `food_count` to `null`; `season_food` controls the four stocks.

Parents must reach `reproductive_age` (default 60 s). The engine chooses eligible high-fitness parents up to its ordinary selection count. A cohort can finish with no eligible parents, causing genuine seasonal lineage extinction. It does not restart a random population and label that lineage continuous.

Watch the Ecosystem Python season summary, food target, cluster relocation and generation history. Auto scenery colors follow the actual Python season; manual colors do not change food or eligibility.

```bash
./"v2/Run Artificial Evolution 2.command" -- --mode=seasons --immersive
```

## Obstacles and hazards

The Python model generates three rectangular barriers and two circular dangerous regions per generation, with seeded layouts. Godot depicts barriers as stone walls and hazards as terrain-conforming red areas. Their planar Python extents are authoritative; decorative rocks elsewhere do not block agents.

- Barrier impacts cost **2 energy** and **2 fitness** each.
- Hazard exposure adds **12 energy/s** and a **5 fitness/s** penalty.
- Arena-edge reflections retain the original unpenalized boundary rule.
- Radius-aware obstacle sensing adds five directional rays and three hazard signals to the usual eight inputs.

The model's 16-input neural controller can be compared with random and greedy steering. `risk_sensors="hidden"` removes risk information for an intervention; it does not remove barriers or their costs. Eating can offset some damage while exposure continues.

Inspect cumulative hazard energy/time in Research. These costs exist only in this mode; a red visual effect or ornamental stone elsewhere is not an extra ecological rule.

```bash
./"v2/Run Artificial Evolution 2.command" -- --mode=obstacles --immersive
```

## Brains and bodies

Neural weights and three physical traits are inherited together: cruise speed, body radius and sensory range. Founder bodies use reference traits; offspring body mutation is multiplicative, bounded and separately controlled from neural mutation.

| Trait | Allowed range | Trade-off |
| --- | --- | --- |
| Cruise speed | 25–100 px/s | Travel opportunity versus quadratic movement cost |
| Radius | Integer 4–12 px | Capacity and mass versus development and metabolism |
| Sensory range | 60–280 px | Perception reach versus quadratic sensing cost |

These are stylized model units, not calibrated animal biology. Godot scales models from the authoritative radius, while coats and a small cosmetic size factor remain artwork. See [energetics](EVOLUTION_AND_BRAINS.md#body-traits-and-energy) for formulas.

```bash
./"v2/Run Artificial Evolution 2.command" -- --mode=traits --immersive
```

## Predator and prey

The founder count includes both populations; default 100 total with 20 predators leaves 80 prey. Predators are wolves, prey are deer. Both use 11-input neural networks with the normal eight channels plus nearest-opponent distance/direction/visibility. Hunting/escape is not hard-coded steering.

Prey eat ordinary food. Predators gain up to **60 energy per capture**. Prey fitness is `age + 10 × meals`; predator fitness is `age + 30 × captures`. Selection and inheritance operate separately in the two gene pools, maintaining configured birth counts each replacement cohort.

`episode_seconds=60` bounds each episode. Living animals at its end are censored, not dead. All evaluated genomes remain eligible for their role's selection, including animals that died. This is not continuous demographic predator–prey reproduction and does not by itself establish a self-sustaining arms race.

Source directional counters support **Hunting** and **Escaping** animation labels; nearest-opponent lines are observations rather than the neural controller's chosen target. Hiding opponent sensors with `prey_sensors` or `predator_sensors` changes information, not opponent presence.

```bash
./"v2/Run Artificial Evolution 2.command" -- --immersive \
  --config="$(pwd)/v2/docs/examples/predator_prey.json"
```

**Combined physical-habitat limitation:** the original capture solver builds swept reflected paths before calling the habitat-wrapped movement method. Its contact paths therefore retain commanded-speed planar motion while habitat can slow/block the final move. Exact replay reproduces this implementation; it does not establish terrain-consistent capture geometry. Keep this distinction in any physical predator–prey analysis; see [physical limits](PHYSICAL_HABITAT.md#combined-model-limitations).

## Social behavior

Social mode divides the arena into physically isolated, equal groups. Default 100 founders in 10 groups gives 10 members per group. Supported layouts are uniform, sparse and barren; stock must divide evenly among groups. Each group needs at least two agents and the group arena must be large enough.

The 17-input, eight-hidden, three-output network controls turning, costly signaling and sharing effort. Bodies are held at reference traits. Optional signaling costs `0.2 × signal` energy/s. Local transfers can request up to 12 energy/s within 48 px, retain a 10-energy donor reserve and deliver 80% of donated energy. Losses are explicit; sharing does not create food.

With restricted food access, designated members can eat while others depend on stored energy or transfers. Open access lets all members feed. Hiding received signals preserves their cost/production while removing that sensory information. Sharing/signaling switches expose controlled comparisons.

Fitness is survival age, with no direct cooperation bonus. **Group survival** selects groups by average age and preserves team assortment; **Individual survival** selects high-survival individuals and remixes them. Thus the contrast changes both incentives and assortment, not one isolated variable.

Watch real sharing links and inspector totals. A visible group is not evidence that cooperation evolved; use the preserved Step 25 protocol for repeated inference.

```bash
./"v2/Run Artificial Evolution 2.command" -- --immersive \
  --config="$(pwd)/v2/docs/examples/social.json"
```

## Continuous ecosystem

This model removes synchronized replacement. Real births and deaths overlap in one persistent habitat. It uses inherited brains/bodies, food capacity, finite `regrowth_rate`, maturity, birth cooldown and a population cap. It ends at `duration` or total lineage extinction. Its displayed generation represents ancestry depth rather than a global replacement round.

Birth eligibility requires maturity, cooldown and at least 80% of parent energy capacity. A candidate child carries inherited/mutated genes and must fit available space. The parent funds 40% of the child's capacity as endowment plus development/overhead, retaining a parent reserve. Failed capacity, placement or energy attempts are recorded in the canonical report. Food and births are not unlimited.

**Funded reproduction** uses configured mutations. **Clonal reproduction** forces neural and body mutation probabilities to zero, retaining resource-funded births and selection through differential reproductive success. Disable **Automatic reproduction** to stop new birth attempts while existing animals continue living/dying. **Next generation** does not apply.

Defaults are 100 founders, cap 300, 30 regrowth units/s, 15-second maturity, 20-second cooldown and 600-second horizon. For a more readily visible lifecycle demonstration:

```bash
./"v2/Run Artificial Evolution 2.command" -- --immersive --ground-view \
  --config="$(pwd)/v2/configs/animation_lifecycle.json"
```

That explicit preset uses 24 founders, food capacity 120, cap 60, maturity 2 s, cooldown 4 s and duration 180 s. It illustrates actual lifecycle events under favorable conditions; it is not the published persistence protocol or a promise of indefinite survival.

## End states and interpretation

Completed budgets, biological deaths, retired survivors and extinction have different meanings. Generational mean fitness resets with each cohort; completed-generation curves retain historical scores. Continuous mean fitness covers all recorded lifetimes. The primary predator–prey score is prey-only; inspect role-specific records for predators. Social scores are survival age.

Do not pool these scores into a single ranking of intelligence. [Research and validation](RESEARCH_AND_VALIDATION.md) explains matched baselines and uncertainty. [Configuration](CONFIGURATION.md) lists every applicable parameter and validation rule.
