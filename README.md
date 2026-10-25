# Artificial Evolution

An experiment to investigate whether food-seeking behavior evolves in creatures
controlled by tiny neural networks, with random movement as a comparison.

Current step: **6 — Implement survival mechanics**. The Pygame application starts
with 100 creatures and 150 food pellets in a 1,000 × 600 pixel habitat. Creatures
spend energy, become hungry, age, and die from starvation or old age. Neural
networks, reproduction, and evolution will be implemented in later steps.

## Run the world

From this project folder:

```sh
source .venv/bin/activate
python main.py
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
| Speed | Random value from 40 to 80 pixels per second |
| Energy | 100 initially, capped at 100; food restores up to 20 per pellet |
| Hunger | Energy deficit from 0% full to 100% empty |
| Age | 0 simulated seconds initially |
| Lifespan | Seeded random value from 60 to 120 simulated seconds |
| Food eaten | 0 initially; incremented once per consumed pellet |

The selected creature has a white ring, and its properties appear below the arena.
The first creature is selected initially. Pause with **Space** to inspect a
creature while it holds still. Its inspector shows energy, hunger, age/lifespan,
food count, position, speed, size, and facing direction. Small energy bars below
creatures change from green to amber to red as hunger increases.

## Survival

Energy use is charged per simulated second:

```text
energy cost = 2 + 0.05 * movement speed
```

With initial speeds of 40–80 pixels per second, creatures spend 4–6 energy units
per second. A stationary creature still spends 2 units per second. Food restores
energy up to a capacity of 100. Hunger is `1 - energy / 100`: creatures are hungry
at 50% deficit and starving at 80% deficit. These states describe their reserves;
steering stays random.

Age advances with simulated time. Each creature has a seeded lifespan of 60–120
seconds. Energy exhaustion causes starvation death; reaching lifespan causes
old-age death, even with energy remaining. If both limits fall inside a step,
the earlier one determines the cause. Age stops at the moment of death.

Every fixed step applies energy use and aging first, removes fatal creatures,
then moves and feeds survivors. A creature with positive energy can recover by
eating; one that has already died cannot move, eat, or revive. Death reduces the
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

Creatures keep their random steering and eat food they encounter along the way.
Meals eaten by creatures that later die remain included in the total meal count.

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
movement, eating, energy use, aging, and simulation time. **R** resets time and
generates a fresh population and food supply, preserving the current pause state.

Use a seed to reproduce a population and its movement at the same simulation time:

```sh
python main.py --seed 42
```

Without `--seed`, startup chooses a random seed. The active seed is displayed in
the footer. **R** chooses a new seed and resets the population to 100 creatures.
Population generation, motion, and food use separate random-number generators.
Food availability affects survival, while steering stays random at this step.

To render a few frames without opening a window, optionally saving a preview:

```sh
python main.py --headless --frames 5400 --seed 42 --screenshot .cache/survival-preview.png
```

Headless mode requires `--frames` so it exits automatically and advances exactly
one 1/60-second simulation step per frame, without waiting for real time. The
command above therefore captures the world after 90 seconds of simulated life.

Run the movement, food, and survival checks with the standard Python test runner:

```sh
python -m unittest -v test_movement.py test_food.py test_survival.py
```

Verified: all 39 checks, a 125-second headless lifespan run through extinction,
and a 120-frame native macOS Cocoa run. Tests cover energy use, hunger, capacity,
starvation, old age, death removal, food rescue, extinction, reset, and seeded
results at 30, 60, and 144 display updates per second.

## Project structure

```text
main.py               Window, controls, simulation timing, and launch options
world.py              Survival, death removal, motion, food, eating, and selection
creature.py           Creature state, energy, hunger, age, motion, drawing, and spawning
food.py               Food properties, circle collision checks, and drawing
test_movement.py      Movement, boundary, timing, pause, and reproducibility checks
test_food.py          Food generation, contact, meal accounting, and reproducibility
test_survival.py      Energy, hunger, aging, death, extinction, and reset checks
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
