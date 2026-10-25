# Artificial Evolution

An experiment to investigate whether food-seeking behavior evolves in creatures
controlled by tiny neural networks, with random movement as a comparison.

Current step: **5 — Introduce food**. The Pygame application displays 100 moving
creatures and 150 food pellets in a 1,000 × 600 pixel habitat. Creatures eat on
contact, gaining energy. Energy consumption, death, neural networks, and evolution
will be implemented in later steps.

## Run the world

From this project folder:

```sh
source .venv/bin/activate
python main.py
```

- Press **G** to hide or show the grid.
- Press **Space** to pause or resume movement and eating.
- Press **R** to reset creatures, food, energy, counters, and simulation time.
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
| Speed | Random value from 40 to 80 pixels per second |
| Energy | 100 initially; each eaten pellet adds 20 |
| Food eaten | 0 initially; incremented once per consumed pellet |

The selected creature has a white ring, and its properties appear below the arena.
The first creature is selected initially. Pause with **Space** to inspect a
creature while it holds still. Its energy and food counter update as it eats.

## Food and eating

The arena starts with 150 green diamond-shaped pellets, each with a collision
radius of 3 pixels and an energy value of 20. Food spawns fully inside the arena,
clear of creatures and other pellets.

Each simulation step checks circle contact using both the creature's and the
pellet's radius. On contact, the creature gains the pellet's energy, its food
counter increases, and the pellet is removed. If multiple creatures touch one
pellet in the same step, the nearest center wins; an exact distance tie uses the
lower creature ID. Each pellet awards energy only once.

After all contacts are resolved, eaten pellets are replaced at random free
positions, maintaining 150 available meals. Replacements start clear of creatures
and are eligible for eating on subsequent steps. The header shows available food
and total meals eaten; selecting a creature shows its individual meal count.

Creatures keep their random steering and eat food they encounter along the way.
Food affects their energy and counters. Energy can rise above the starting value
of 100; energy costs and capacity rules belong to later survival steps.

## Movement

Each creature travels forward at its own speed. Its facing direction rotates
gradually, with a random turn rate between -90 and +90 degrees per second. It
chooses a new turn rate approximately every 0.75 to 2 seconds. This is temporary
random steering for the movement stage, separate from future neural decisions.

Creatures bounce off all four walls. Wall contact reflects their direction and
keeps their full body inside the arena, accounting for body radius and any travel
remaining after the impact. Corner hits reflect both direction components.
Creatures move independently and may pass through one another after spawning.

Movement advances in fixed 1/60-second simulation steps, independently of display
frame rate. The footer shows elapsed simulation time. Long desktop frame stalls
are capped at 0.25 seconds of catch-up to avoid a large jump. Pausing freezes
movement, eating, and simulation time. **R** resets time and generates a fresh
population and food supply, preserving the current pause state.

Use a seed to reproduce a population and its movement at the same simulation time:

```sh
python main.py --seed 42
```

Without `--seed`, startup chooses a random seed. The active seed is displayed in
the footer. **R** chooses a new seed and resets the population to 100 creatures.
Population generation, motion, and food use separate random-number generators,
so changing food availability does not change creature trajectories.

To render a few frames without opening a window, optionally saving a preview:

```sh
python main.py --headless --frames 120 --seed 42 --screenshot .cache/food-preview.png
```

Headless mode requires `--frames` so it exits automatically and advances exactly
one 1/60-second simulation step per frame, without waiting for real time. The
command above therefore captures the world after 2 seconds of simulated motion.

Run the movement and food checks with the standard Python test runner:

```sh
python -m unittest -v test_movement.py test_food.py
```

Verified: all 23 movement and food checks, pause/reset and inspection controls,
and 120-frame headless and native macOS Cocoa runs. Food checks cover collision
geometry, single meal ownership, energy accounting, spawning, and seeded results
at 30, 60, and 144 display updates per second.

## Project structure

```text
main.py               Window, controls, simulation timing, and launch options
world.py              Simulation, random steering, food spawning, eating, and selection
creature.py           Creature properties, motion, wall reflection, drawing, and spawning
food.py               Food properties, circle collision checks, and drawing
test_movement.py      Movement, boundary, timing, pause, and reproducibility checks
test_food.py          Food generation, contact, meal accounting, and reproducibility
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
