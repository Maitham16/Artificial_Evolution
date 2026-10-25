# Artificial Evolution

An experiment to investigate whether food-seeking behavior evolves in creatures
controlled by tiny neural networks, with random movement as a comparison.

Current step: **7 — Create artificial brains**. Each of the 100 creatures has an
individual, untrained NumPy neural network controlling its turn rate and speed.
The 1,000 × 600 pixel habitat includes food, energy use, hunger, aging, and death.
Reproduction, mutation, training, and evolution will be implemented in later steps.

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

The selected creature has a white ring, and its properties appear below the arena.
The first creature is selected initially. Pause with **Space** to inspect a
creature while it holds still. Its inspector shows energy, hunger, age/lifespan,
food count, position, current/maximum speed, size, facing direction, and turn rate.
Small energy bars below creatures change from green to amber to red as hunger
increases.

## Artificial brains

Every creature owns an independent **8-input, 8-hidden, 2-output** feed-forward
network. NumPy matrix multiplication and `tanh` activations compute each decision.
The network has **90 parameters**, including biases. Parameters are randomly
initialized from a seed and remain fixed during a run.

The eight inputs, in order, are:

| Input | Meaning and range |
| --- | --- |
| Food forward | Nearest visible food's forward offset in the body's frame, divided by 160; -1 to 1 |
| Food right | The same food's rightward offset in the body's frame, divided by 160; -1 to 1 |
| Food visible | 1 when food is within 160 pixels, otherwise 0; absent food offsets are also 0 |
| Hunger | Energy deficit, from 0 full to 1 empty |
| Wall forward | Radius-aware forward wall distance, clipped to 160 pixels and divided by 160 |
| Wall right | The same normalized distance to the right |
| Wall back | The same normalized distance behind the creature |
| Wall left | The same normalized distance to the left |

Food can be sensed all around the creature within 160 pixels. A wall input of 0
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
parameters for a given seed. This step provides the two controllers; fitness
comparison experiments remain later work.

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
starvation/old-age breakdown. An extinct population shows a reset prompt and
keeps the controls usable. **R** starts again with 100 living creatures and zero
deaths. Pause freezes the full simulation, including hunger and lifespan.

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
python main.py --headless --frames 120 --seed 42 --screenshot .cache/brains-preview.png
```

Headless mode requires `--frames` so it exits automatically and advances exactly
one 1/60-second simulation step per frame, without waiting for real time. The
command above therefore captures the world after 2 seconds of simulated life.

Run all checks with the standard Python test runner:

```sh
python -m unittest -v test_movement.py test_food.py test_survival.py test_brain.py
```

Verified: all 57 checks and 120-frame neural and random headless runs, plus a
120-frame native macOS Cocoa run. Neural tests cover the forward pass, sensory
geometry, bounded motor commands, same-step energy costs, independent parameters,
seeded reset, and fixed parameters during inference. The regression tests retain
movement, food, survival, and frame-rate reproducibility coverage. A 125-second
neural lifespan run completed through extinction with unchanged brain parameters.

## Project structure

```text
main.py               Window, controls, simulation timing, and launch options
world.py              Sensory inputs, controller selection, survival, motion, and food
creature.py           Creature state, motor controls, survival, drawing, and spawning
brain.py              NumPy network, seeded parameters, and forward inference
food.py               Food properties, circle collision checks, and drawing
test_movement.py      Movement, boundary, timing, pause, and reproducibility checks
test_food.py          Food generation, contact, meal accounting, and reproducibility
test_survival.py      Energy, hunger, aging, death, extinction, and reset checks
test_brain.py         Network math, sensors, motor commands, and seeded brain checks
check_environment.py  Numerical and graphics dependency check
requirements.txt      Pinned Python dependencies
.python-version       Python version selection
.gitignore            Local environment and cache exclusions
```

## Environment

Use Python 3.13 and a local virtual environment. The project uses:

- NumPy for numerical operations and, later, neural-network weights.
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
