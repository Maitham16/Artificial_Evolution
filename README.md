# Artificial Evolution

An experiment to investigate whether food-seeking behavior evolves in creatures
controlled by tiny neural networks, with random movement as a comparison.

Current step: **9 — Implement natural selection**. Creatures earn fitness from
survival time and food eaten. Rankings include all 100 original creatures, and the
top 20% are selected as future breeding candidates once the run ends. Reproduction,
mutation, training, and evolving new generations remain later steps.

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
- Press **Space** to pause or resume movement, eating, energy use, and aging.
- Press **R** to reset creatures, food, energy, ages, deaths, and simulation time.
- **Click a creature** to inspect its properties. Click empty space to deselect.
- Press **Esc**, or close the window, to quit.

The window runs at up to 60 frames per second. The arena has a visible border and
a 40-pixel grid, with a stronger line every 200 pixels. Its coordinates start at
`(0, 0)` in the top-left corner, with x increasing right and y increasing down.
The surrounding header and footer are outside the arena. The border marks the
reflective walls; the grid is a visual guide.

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

The selected creature has a white ring, and its properties appear below the arena.
The first creature is selected initially. Pause with **Space** to inspect a
creature while it holds still. Its inspector shows energy, hunger, age/lifespan,
food count, fitness, position, current/maximum speed, size, facing direction, and turn rate.
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
usual 100. These are candidate IDs associated with the retained creature/brain
records. Reproduction and mutation will use them in later steps.

The header shows best and mean fitness across the entire original population.
Clicking a living creature shows its individual score. **F** opens the top-ten
leaderboard with survival time, meals, score, and live/dead or selected status.
The world continues while the leaderboard is open; use **Space** to pause. Close
the leaderboard before selecting creatures in the arena.

Completed runs show their best result and selection count. **R** clears the final
results and begins a new population with zero scores. Ranking and drawing the
leaderboard do not change movement, randomness, food, or brain parameters.

The code exposes live or final immutable snapshots through
`World.get_fitness_evaluation()`. Its `ranking` contains every evaluated creature,
and its `selected_ids` is populated only for completed runs.
`World.final_evaluation` retains the final snapshot until reset. The default rule
and selection fraction are defined in `selection.py`.

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
The network has **90 parameters**, including biases. Parameters are randomly
initialized from a seed and remain fixed during a run.

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
network's parameters, which may produce useful or unhelpful actions while
untrained. The brain label and the selected creature's current speed and turn rate
make the active controller visible.

The random mode retains the earlier gradual random steering and cruising speed.
Both modes start with the same physical traits, food, and seeded network
parameters for a given seed. Both use the same fitness rule. Comparisons across
independent runs and evolving generations remain later work.

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
population. Final creature states remain in `World.dead_creatures` until reset.

The header shows living creatures, hungry creatures, total deaths, and the
starvation/old-age breakdown. An extinct population shows final fitness and
selection results and keeps the controls usable. **R** starts again with 100 living
creatures, zero scores, and zero deaths. Pause freezes the full simulation,
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
python main.py --headless --frames 120 --seed 42 --screenshot .cache/selection-preview.png
```

Headless mode requires `--frames` so it exits automatically and advances exactly
one 1/60-second simulation step per frame, without waiting for real time. The
command above therefore captures the world after 2 seconds of simulated life.

Run all checks with the standard Python test runner:

```sh
python -m unittest discover -v
```

Verified: all 90 checks, a 125-second headless run through final selection,
leaderboard/pause/reset controls, and a 120-frame native macOS Cocoa run.
Selection tests cover both score components, dead-creature scores, deterministic
ranking, frozen results, top-20% selection, reset, observation without simulation
changes, and matching final results across frame rates. Existing perception,
neural, movement, food, and survival checks remain included.

## Project structure

```text
main.py               Window, controls, simulation timing, and launch options
world.py              Simulation, perception, survival, food, and final fitness results
creature.py           Creature state, motor controls, survival, drawing, and spawning
brain.py              NumPy network, seeded parameters, and forward inference
perception.py         Read-only food distance, direction, visibility, and neural signals
selection.py          Fitness formula, immutable rankings, and final candidate selection
food.py               Food properties, circle collision checks, and drawing
test_movement.py      Movement, boundary, timing, pause, and reproducibility checks
test_food.py          Food generation, contact, meal accounting, and reproducibility
test_survival.py      Energy, hunger, aging, death, extinction, and reset checks
test_brain.py         Network math, sensors, motor commands, and seeded brain checks
test_perception.py    Perception geometry, edge cases, brain inputs, and overlay checks
test_selection.py     Scores, ranking, final selection, immutability, and reset checks
check_environment.py  Numerical and graphics dependency check
requirements.txt      Pinned Python dependencies
.python-version       Python version selection
.gitignore            Local environment and cache exclusions
```

## Environment

Use Python 3.13 and a local virtual environment. The project uses:

- NumPy for neural networks and sensory calculations.
- Pygame for the 2D world display.
- Matplotlib for later experiment charts.

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
