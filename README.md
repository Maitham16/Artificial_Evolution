# Artificial Evolution

An experiment to investigate whether food-seeking behavior evolves in creatures
controlled by tiny neural networks, with random movement as a comparison.

Current step: **4 — Implement movement**. The Pygame application displays 100
creatures moving and turning in a 1,000 × 600 pixel habitat, with reflective wall
boundaries. Food, survival mechanics, neural networks, and evolution will be
implemented in later steps.

## Run the world

From this project folder:

```sh
source .venv/bin/activate
python main.py
```

- Press **G** to hide or show the grid.
- Press **Space** to pause or resume movement.
- Press **R** to generate a new random population.
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
| Energy | 100 for every creature; constant at this step |

The selected creature has a white ring, and its properties appear below the arena.
The first creature is selected initially. Pause with **Space** to inspect a
creature while it holds still. Energy remains constant at this step.

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
are capped at 0.25 seconds of catch-up to avoid a large jump. Pausing freezes both
movement and simulation time. **R** resets time and generates a fresh population,
preserving the current pause state.

Use a seed to reproduce a population and its movement at the same simulation time:

```sh
python main.py --seed 42
```

Without `--seed`, startup chooses a random seed. The active seed is displayed in
the footer. **R** chooses a new seed and resets the population to 100 creatures.
Population generation and motion use separate random-number generators.

To render a few frames without opening a window, optionally saving a preview:

```sh
python main.py --headless --frames 120 --seed 42 --screenshot .cache/movement-preview.png
```

Headless mode requires `--frames` so it exits automatically and advances exactly
one 1/60-second simulation step per frame, without waiting for real time. The
command above therefore captures the world after 2 seconds of simulated motion.

Run the movement checks with the standard Python test runner:

```sh
python -m unittest -v test_movement.py
```

Verified: all 11 movement checks, pause/resume and inspection controls, and
120-frame headless and native macOS Cocoa runs. The movement checks include wall
and corner reflections, large travel distances, seeded motion, and matching
simulation results at 30, 60, and 144 display updates per second.

## Project structure

```text
main.py               Window, controls, simulation timing, and launch options
world.py              Fixed simulation steps, random steering, arena, and selection
creature.py           Creature properties, motion, wall reflection, drawing, and spawning
test_movement.py      Movement, boundary, timing, pause, and reproducibility checks
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
