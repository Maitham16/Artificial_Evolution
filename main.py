"""Launch Step 4: 100 creatures moving and turning inside a Pygame world."""

import argparse
import math
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from world import SIMULATION_STEP, World


PADDING = 40
HEADER_HEIGHT = 108
FOOTER_HEIGHT = 92
TARGET_FPS = 60
MAX_FRAME_SECONDS = 0.25
BACKGROUND = (10, 18, 24)
TEXT = (225, 235, 237)
MUTED = (135, 158, 167)
ACCENT = (100, 219, 181)


def positive_integer(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def handle_events(world: World) -> bool:
    """Return False when the user closes the window or presses Escape."""
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            if event.key == pygame.K_g:
                world.show_grid = not world.show_grid
            if event.key == pygame.K_r:
                world.regenerate_population()
            if event.key == pygame.K_SPACE:
                world.paused = not world.paused
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            world.select_creature((event.pos[0] - PADDING, event.pos[1] - HEADER_HEIGHT))
    return True


def draw_interface(
    screen: pygame.Surface, world: World, fonts: dict[str, pygame.font.Font]
) -> None:
    screen.fill(BACKGROUND)
    screen.blit(fonts["small"].render("ARTIFICIAL EVOLUTION", True, ACCENT), (40, 25))
    screen.blit(fonts["title"].render("The virtual world", True, TEXT), (38, 48))

    activity = "PAUSED" if world.paused else "MOVING"
    status_color = MUTED if world.paused else ACCENT
    status = fonts["small"].render(
        f"{len(world.creatures)} CREATURES / {activity}", True, status_color
    )
    status_x = screen.get_width() - PADDING - status.get_width()
    pygame.draw.circle(screen, status_color, (status_x - 15, 38), 4)
    screen.blit(status, (status_x, 30))
    stage = fonts["small"].render("STEP 04 / MOVEMENT", True, MUTED)
    screen.blit(stage, (screen.get_width() - PADDING - stage.get_width(), 57))

    world.draw(screen, (PADDING, HEADER_HEIGHT))

    footer_y = HEADER_HEIGHT + world.height + 22
    controls = (
        f"Space  {'Resume' if world.paused else 'Pause'}     /     "
        f"G  Grid {'on' if world.show_grid else 'off'}     /     "
        "R  New population     /     Click  Inspect     /     Esc  Quit"
    )
    screen.blit(fonts["small"].render(controls, True, MUTED), (PADDING, footer_y))
    dimensions = fonts["small"].render(
        f"{world.width:,} x {world.height:,} pixels", True, MUTED
    )
    screen.blit(
        dimensions,
        (screen.get_width() - PADDING - dimensions.get_width(), footer_y),
    )

    creature = world.selected_creature
    if creature is None:
        details = "Click a creature to inspect its properties."
    else:
        details = (
            f"#{creature.creature_id:03d}    "
            f"Position ({creature.x:.0f}, {creature.y:.0f})    "
            f"Energy {creature.energy:.0f}    Speed {creature.speed:.1f} px/s    "
            f"Radius {creature.radius} px    Facing {math.degrees(creature.heading):.0f} deg"
        )
    screen.blit(fonts["small"].render(details, True, TEXT), (PADDING, footer_y + 27))
    seed_label = fonts["small"].render(
        f"{world.elapsed_time:.1f} s  /  Seed {world.seed}", True, MUTED
    )
    screen.blit(
        seed_label,
        (screen.get_width() - PADDING - seed_label.get_width(), footer_y + 27),
    )


def run(
    *,
    headless: bool = False,
    frames: int | None = None,
    screenshot: Path | None = None,
    seed: int | None = None,
) -> int:
    if headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"

    try:
        pygame.display.init()
        pygame.font.init()
        world = World(seed=seed)
        screen = pygame.display.set_mode(
            (world.width + 2 * PADDING, HEADER_HEIGHT + world.height + FOOTER_HEIGHT)
        )
        pygame.display.set_caption("Artificial Evolution | 100 Creatures")
        fonts = {
            "title": pygame.font.Font(None, 38),
            "small": pygame.font.Font(None, 20),
        }
        clock = pygame.time.Clock()
        rendered_frames = 0
        print(
            f"World ready: {world.width} x {world.height}; "
            f"creatures: {len(world.creatures)}; seed: {world.seed}; "
            f"display driver: {pygame.display.get_driver()}",
            flush=True,
        )

        while frames is None or rendered_frames < frames:
            frame_dt = clock.tick(0 if headless else TARGET_FPS) / 1000.0
            if not handle_events(world):
                break
            # Headless runs advance exactly one simulation tick per saved frame.
            dt = SIMULATION_STEP if headless else min(frame_dt, MAX_FRAME_SECONDS)
            world.update(dt)
            draw_interface(screen, world, fonts)
            pygame.display.flip()
            rendered_frames += 1

        if screenshot is not None and rendered_frames:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(screen, str(screenshot))
            print(f"Screenshot saved: {screenshot}")
    finally:
        pygame.quit()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--headless", action="store_true", help="render without opening a window"
    )
    parser.add_argument(
        "--frames", type=positive_integer, help="exit after this many rendered frames"
    )
    parser.add_argument(
        "--screenshot", type=Path, help="save the final frame as an image on exit"
    )
    parser.add_argument("--seed", type=int, help="recreate a particular initial population")
    args = parser.parse_args()
    if args.headless and args.frames is None:
        parser.error("--headless requires --frames so the run finishes automatically")
    return run(
        headless=args.headless,
        frames=args.frames,
        screenshot=args.screenshot,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
