# Artificial Evolution

An experiment to investigate whether food-seeking behavior evolves in creatures
controlled by tiny neural networks, with random movement as a comparison.

Current step: **12 — Visualize evolution**. Plot mean/best fitness, survival to
60 seconds, and food consumption across completed generations. Charts appear in
the world and can be exported with Matplotlib. Comparing evolution against random
movement across independent experiments remains later work.

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
single seeded trajectory can show changes, but independent runs and the random
movement comparison are needed to evaluate whether evolution reliably helps.

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

Each of the usual **20 selected parents produces five offspring**, rebuilding the
population to **100**. Birth slots are shuffled to avoid associating parent rank
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
independent runs remain later work.

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
founders. Each new population has 100 living creatures with zero scores and
deaths. Pause freezes the full simulation,
including hunger, lifespan, and earned fitness.

## Food and eating

The arena starts with 150 green diamond-shaped pellets, each with a collision
radius of 3 pixels and an energy value of 20. Food spawns fully inside the arena,
clear of creatures and other pellets.

Each simulation step checks circle contact using both the creature's and the
pellet's radius. A living creature with room for energy gains up to 20 on contact.
Its food counter increases, and the pellet is removed. If multiple creatures touch one
pellet and can eat, the nearest center wins; an exact distance tie uses the lower
creature ID. Each pellet awards energy only once. A full or dead creature leaves
the food available.

After all contacts are resolved, eaten pellets are replaced at random free
positions, maintaining 150 available meals. Replacements start clear of creatures
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
the footer. **R** chooses a new seed and resets the population to 100 creatures.
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

Verified: **139 checks**, a ten-generation seeded run with checkpoint survival
counts, inspection of the exported figure and in-world charts, and a native
macOS Cocoa rendering check with three short test generations. Every previously
recorded fitness, feeding, and behavior observation matches Step 11 exactly.
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
results/step11-seed42.json  Observations from one seeded ten-generation run
results/step12-seed42.json  Repeated seed-42 trajectory with checkpoint survival rates
results/step12-evolution.png  Exported fitness, survival, and food-consumption figure
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
