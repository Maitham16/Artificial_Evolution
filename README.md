# Artificial Evolution

An experiment to investigate whether food-seeking behavior evolves in creatures
controlled by tiny neural networks, with random movement as a comparison.

Current step: **2 — Create the virtual world**. The Pygame application displays an
empty 1,000 × 600 pixel habitat. Creatures, food, survival mechanics, neural
networks, and evolution will be implemented in later steps.

## Run the world

From this project folder:

```sh
source .venv/bin/activate
python main.py
```

- Press **G** to hide or show the grid.
- Press **Esc**, or close the window, to quit.

The window runs at up to 60 frames per second. The arena has a visible border and
a 40-pixel grid, with a stronger line every 200 pixels. Its coordinates start at
`(0, 0)` in the top-left corner, with x increasing right and y increasing down.
The surrounding header and footer are outside the arena. The border and grid are
visual guides at this stage.

To render a few frames without opening a window, optionally saving a preview:

```sh
python main.py --headless --frames 5 --screenshot .cache/world-preview.png
```

Headless mode requires `--frames` so it exits automatically. This verifies the
rendering loop; it does not exercise the desktop window backend.

Verified: a five-frame headless run, visual inspection of the saved preview, grid
rendering and toggling, Escape, and window-close event handling. Native macOS
display initialization aborted during sandboxed execution, so opening the actual
desktop window still needs verification from a normal terminal.

## Project structure

```text
main.py               Window, event loop, interface, and launch options
world.py              Arena dimensions, background, border, and grid
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
