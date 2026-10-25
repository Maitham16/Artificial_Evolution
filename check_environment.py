"""Check the numerical and graphics libraries without opening a window."""

import io
import os
import sys
from pathlib import Path


def main() -> None:
    cache_dir = Path(__file__).resolve().parent / ".cache"
    cache_dir.mkdir(exist_ok=True)
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_dir))
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir / "matplotlib"))

    import matplotlib
    import numpy as np
    import pygame
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    print(f"Python {sys.version.split()[0]}")

    vector = np.array([3.0, 4.0])
    if not np.isclose(vector @ vector, 25.0):
        raise RuntimeError("NumPy numerical check failed")
    print(f"NumPy {np.__version__}: numerical operations OK")

    try:
        pygame.display.init()
        surface = pygame.display.set_mode((32, 32))
        surface.fill((20, 40, 60))
        pygame.display.flip()
        if surface.get_at((0, 0))[:3] != (20, 40, 60):
            raise RuntimeError("Pygame drawing check failed")
    finally:
        pygame.display.quit()
    print(f"Pygame {pygame.version.ver}: headless display and drawing OK")

    figure = Figure(figsize=(2, 2))
    axes = figure.subplots()
    axes.plot([0, 1], [0, 1])
    output = io.BytesIO()
    FigureCanvasAgg(figure).print_png(output)
    if not output.getvalue().startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Matplotlib PNG rendering check failed")
    print(f"Matplotlib {matplotlib.__version__}: PNG rendering OK")
    print("Environment ready.")


if __name__ == "__main__":
    main()
