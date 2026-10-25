"""Launch Step 2: the Pygame virtual world."""

import argparse
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from world import World


PADDING = 40
HEADER_HEIGHT = 108
FOOTER_HEIGHT = 72
TARGET_FPS = 60
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
    return True


def draw_interface(
    screen: pygame.Surface, world: World, fonts: dict[str, pygame.font.Font]
) -> None:
    screen.fill(BACKGROUND)
    screen.blit(fonts["small"].render("ARTIFICIAL EVOLUTION", True, ACCENT), (40, 25))
    screen.blit(fonts["title"].render("The virtual world", True, TEXT), (38, 48))

    status = fonts["small"].render("WORLD READY", True, ACCENT)
    status_x = screen.get_width() - PADDING - status.get_width()
    pygame.draw.circle(screen, ACCENT, (status_x - 15, 38), 4)
    screen.blit(status, (status_x, 30))
    stage = fonts["small"].render("STEP 02 / ENVIRONMENT", True, MUTED)
    screen.blit(stage, (screen.get_width() - PADDING - stage.get_width(), 57))

    world.draw(screen, (PADDING, HEADER_HEIGHT))

    label = fonts["body"].render("An empty habitat", True, MUTED)
    center = (PADDING + world.width // 2, HEADER_HEIGHT + world.height // 2)
    screen.blit(label, label.get_rect(center=center))

    footer_y = HEADER_HEIGHT + world.height + 26
    controls = f"G  Grid {'on' if world.show_grid else 'off'}     /     Esc  Quit"
    screen.blit(fonts["small"].render(controls, True, MUTED), (PADDING, footer_y))
    dimensions = fonts["small"].render(
        f"{world.width:,} x {world.height:,} pixels", True, MUTED
    )
    screen.blit(
        dimensions,
        (screen.get_width() - PADDING - dimensions.get_width(), footer_y),
    )


def run(
    *, headless: bool = False, frames: int | None = None, screenshot: Path | None = None
) -> int:
    if headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"

    try:
        pygame.display.init()
        pygame.font.init()
        world = World()
        screen = pygame.display.set_mode(
            (world.width + 2 * PADDING, HEADER_HEIGHT + world.height + FOOTER_HEIGHT)
        )
        pygame.display.set_caption("Artificial Evolution | Virtual World")
        fonts = {
            "title": pygame.font.Font(None, 38),
            "body": pygame.font.Font(None, 25),
            "small": pygame.font.Font(None, 20),
        }
        clock = pygame.time.Clock()
        rendered_frames = 0
        print(
            f"World ready: {world.width} x {world.height}; "
            f"display driver: {pygame.display.get_driver()}",
            flush=True,
        )

        while frames is None or rendered_frames < frames:
            if not handle_events(world):
                break
            draw_interface(screen, world, fonts)
            pygame.display.flip()
            rendered_frames += 1
            clock.tick(TARGET_FPS)

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
    args = parser.parse_args()
    if args.headless and args.frames is None:
        parser.error("--headless requires --frames so the run finishes automatically")
    return run(headless=args.headless, frames=args.frames, screenshot=args.screenshot)


if __name__ == "__main__":
    raise SystemExit(main())
