"""Launch Step 10: selected brains reproduce with mutations across generations."""

import argparse
import math
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from creature import MAX_ENERGY
from perception import VISION_RANGE
from selection import FitnessEvaluation
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
            if event.key == pygame.K_v:
                world.show_perception = not world.show_perception
            if event.key == pygame.K_f:
                world.show_fitness = not world.show_fitness
            if event.key == pygame.K_r:
                world.regenerate_population()
            if event.key == pygame.K_n:
                world.advance_generation()
            if event.key == pygame.K_SPACE:
                world.paused = not world.paused
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not world.show_fitness:
                world.select_creature((event.pos[0] - PADDING, event.pos[1] - HEADER_HEIGHT))
    return True


def draw_fitness_panel(
    screen: pygame.Surface, world: World, evaluation: FitnessEvaluation,
    fonts: dict[str, pygame.font.Font],
) -> None:
    """Show the leading scores while the world continues or remains paused."""
    panel = pygame.Rect(0, 0, 740, 410)
    panel.center = (PADDING + world.width // 2, HEADER_HEIGHT + world.height // 2)
    pygame.draw.rect(screen, BACKGROUND, panel, border_radius=12)
    pygame.draw.rect(screen, MUTED, panel, width=1, border_radius=12)
    x = panel.left + 28
    screen.blit(fonts["title"].render("Fitness leaderboard", True, TEXT), (x, panel.top + 20))
    state = (
        f"GEN {world.generation} / FINAL / TOP {evaluation.selection_fraction:.0%} SELECTED"
        if evaluation.complete else f"GEN {world.generation} / LIVE / PROVISIONAL SCORES"
    )
    screen.blit(fonts["small"].render(state, True, ACCENT), (x, panel.top + 61))
    rule = "Fitness = seconds alive + 10 x food eaten"
    screen.blit(fonts["small"].render(rule, True, MUTED), (x, panel.top + 86))

    columns = (x, x + 65, x + 175, x + 315, x + 420, x + 540)
    y = panel.top + 124
    for column, label in zip(columns, ("RANK", "CREATURE", "SURVIVAL", "FOOD", "FITNESS", "STATE")):
        screen.blit(fonts["small"].render(label, True, MUTED), (column, y))
    for rank, entry in enumerate(evaluation.ranking[:10], start=1):
        y = panel.top + 151 + (rank - 1) * 21
        selected = entry.creature_id in evaluation.selected_ids
        values = (
            str(rank), f"#{entry.creature_id:03d}", f"{entry.survival_seconds:.2f} s",
            str(entry.food_eaten), f"{entry.fitness:.2f}",
            "SELECTED" if selected else "ALIVE" if entry.alive else "DEAD",
        )
        color = ACCENT if selected else TEXT
        for column, value in zip(columns, values):
            screen.blit(fonts["small"].render(value, True, color), (column, y))

    count = len(evaluation.ranking)
    note = (
        f"Top {min(10, count)} of {count} shown / "
        f"{len(evaluation.selected_ids)} parents selected for reproduction."
        if evaluation.complete else
        f"Top {evaluation.selection_fraction:.0%} selected after the run ends. "
        f"Showing top {min(10, count)} of {count}."
    )
    screen.blit(fonts["small"].render(note, True, MUTED), (x, panel.bottom - 48))
    action = "N  Next generation     /     F  Close leaderboard" if evaluation.complete else "F  Close leaderboard"
    screen.blit(fonts["small"].render(action, True, ACCENT), (x, panel.bottom - 25))


def draw_interface(
    screen: pygame.Surface, world: World, fonts: dict[str, pygame.font.Font]
) -> None:
    screen.fill(BACKGROUND)
    screen.blit(fonts["small"].render("ARTIFICIAL EVOLUTION", True, ACCENT), (40, 25))
    screen.blit(fonts["title"].render("The virtual world", True, TEXT), (38, 48))
    evaluation = world.get_fitness_evaluation()
    best_score = evaluation.best.fitness if evaluation.best is not None else 0.0
    controller_name = "NEURAL" if world.controller == "neural" else "RANDOM"
    controller_label = (
        f"{controller_name} / BEST {best_score:.1f} / MEAN {evaluation.mean_fitness:.1f}"
    )
    if world.controller == "neural":
        brains = "Random brains" if world.generation == 1 else f"Mutate {world.mutation_rate:.0%}"
        controller_note = f"Gen {world.generation} / {brains} / Sight {VISION_RANGE:.0f} px"
    else:
        controller_note = f"Gen {world.generation} / Random movement baseline"
    screen.blit(fonts["small"].render(controller_label, True, ACCENT), (400, 31))
    screen.blit(fonts["small"].render(controller_note, True, MUTED), (400, 55))

    if not world.creatures:
        activity, status_color = "EXTINCT", (238, 115, 127)
    elif world.paused:
        activity, status_color = "PAUSED", MUTED
    else:
        activity, status_color = "RUNNING", ACCENT
    status = fonts["small"].render(
        f"{len(world.creatures)} ALIVE / {activity}", True, status_color
    )
    status_x = screen.get_width() - PADDING - status.get_width()
    pygame.draw.circle(screen, status_color, (status_x - 15, 38), 4)
    screen.blit(status, (status_x, 30))
    stage = fonts["small"].render("STEP 10 / REPRODUCTION", True, MUTED)
    screen.blit(stage, (screen.get_width() - PADDING - stage.get_width(), 57))
    food_label = fonts["small"].render(
        f"FOOD {len(world.food)}  /  EATEN {world.total_food_eaten}",
        True, (166, 220, 100),
    )
    food_x = screen.get_width() - PADDING - food_label.get_width()
    pygame.draw.polygon(
        screen, (166, 220, 100),
        [(food_x - 15, 84), (food_x - 11, 88),
         (food_x - 15, 92), (food_x - 19, 88)],
    )
    screen.blit(food_label, (food_x, 81))
    hungry = sum(creature.hunger >= 0.5 for creature in world.creatures)
    starved = sum(
        creature.death_cause == "starvation" for creature in world.dead_creatures
    )
    aged = len(world.dead_creatures) - starved
    survival_label = fonts["small"].render(
        f"HUNGRY {hungry}  /  DEAD {len(world.dead_creatures)} "
        f"(starved {starved}, aged {aged})", True, MUTED,
    )
    screen.blit(survival_label, (PADDING, 81))
    if world.selected_creature is None:
        perception_text = "Select a creature to view senses"
    else:
        observation = world.perceive_food(world.selected_creature)
        if observation.visible:
            perception_text = (
                f"Food {observation.distance:.1f} px  /  "
                f"Dir {math.degrees(observation.direction):+.0f} deg  /  "
                f"Nearby {observation.nearby_count}"
            )
        else:
            perception_text = f"No food within {VISION_RANGE:.0f} px"
    screen.blit(fonts["small"].render(perception_text, True, MUTED), (400, 81))

    world.draw(screen, (PADDING, HEADER_HEIGHT))
    if world.show_fitness:
        draw_fitness_panel(screen, world, evaluation, fonts)
    elif not world.creatures:
        panel = pygame.Rect(0, 0, 580, 124)
        panel.center = (PADDING + world.width // 2, HEADER_HEIGHT + world.height // 2)
        pygame.draw.rect(screen, BACKGROUND, panel, border_radius=12)
        pygame.draw.rect(screen, MUTED, panel, width=1, border_radius=12)
        title = fonts["title"].render(f"Generation {world.generation} complete", True, TEXT)
        summary = (
            f"Best #{evaluation.best.creature_id:03d}: {evaluation.best.fitness:.1f} points"
            if evaluation.best is not None else "No creatures evaluated"
        )
        summary += f" / {len(evaluation.selected_ids)} selected"
        result = fonts["small"].render(summary, True, TEXT)
        hint = fonts["small"].render("N  Next generation    /    F  Ranking    /    R  Restart", True, ACCENT)
        screen.blit(title, title.get_rect(center=(panel.centerx, panel.centery - 31)))
        screen.blit(result, result.get_rect(center=(panel.centerx, panel.centery + 5)))
        screen.blit(hint, hint.get_rect(center=(panel.centerx, panel.centery + 35)))

    footer_y = HEADER_HEIGHT + world.height + 16
    controls = (
        f"Space  {'Resume' if world.paused else 'Pause'}     /     "
        f"G  Grid {'on' if world.show_grid else 'off'}     /     "
        f"V  Overlay {'on' if world.show_perception else 'off'}     /     "
        "F  Fitness     /     N  Breed     /     "
        "R  Restart     /     Click  Inspect     /     Esc  Quit"
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
        details = "Click a living creature to inspect its survival state."
        traits = "Energy bars: green = sated, amber = hungry, red = starving"
    else:
        details = (
            f"G{creature.generation} #{creature.creature_id:03d}    "
            f"Energy {creature.energy:.1f}/{MAX_ENERGY:.0f}    "
            f"Hunger {creature.hunger:.0%} ({creature.hunger_state})    "
            f"Age {creature.age:.1f}/{creature.lifespan:.1f} s    Eaten {creature.food_eaten}    "
            f"Fitness {creature.fitness:.1f}"
        )
        parent = "Founder" if creature.parent_id is None else f"Parent G{creature.generation - 1} #{creature.parent_id:03d}"
        details += f"    {parent} / Mut {creature.mutation_count}"
        traits = (
            f"Position ({creature.x:.0f}, {creature.y:.0f})    "
            f"Speed {creature.speed:.1f}/{creature.max_speed:.0f} px/s    "
            f"Radius {creature.radius} px    Facing {math.degrees(creature.heading):.0f} deg    "
            f"Turn {math.degrees(creature.turn_rate):+.0f} deg/s"
        )
    screen.blit(fonts["small"].render(details, True, TEXT), (PADDING, footer_y + 24))
    screen.blit(fonts["small"].render(traits, True, MUTED), (PADDING, footer_y + 46))
    seed_label = fonts["small"].render(
        f"{world.elapsed_time:.1f} s  /  Seed {world.seed}", True, MUTED
    )
    screen.blit(
        seed_label,
        (screen.get_width() - PADDING - seed_label.get_width(), footer_y + 46),
    )


def run(
    *,
    headless: bool = False,
    frames: int | None = None,
    screenshot: Path | None = None,
    seed: int | None = None,
    controller: str = "neural",
) -> int:
    if headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"

    try:
        pygame.display.init()
        pygame.font.init()
        world = World(seed=seed, controller=controller)
        screen = pygame.display.set_mode(
            (world.width + 2 * PADDING, HEADER_HEIGHT + world.height + FOOTER_HEIGHT)
        )
        pygame.display.set_caption(f"Artificial Evolution | Reproduction | {controller.title()}")
        fonts = {
            "title": pygame.font.Font(None, 38),
            "small": pygame.font.Font(None, 20),
        }
        clock = pygame.time.Clock()
        rendered_frames = 0
        print(
            f"World ready: {world.width} x {world.height}; "
            f"creatures: {len(world.creatures)}; seed: {world.seed}; "
            f"food: {len(world.food)}; "
            f"controller: {world.controller}; "
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
    parser.add_argument(
        "--controller", choices=("neural", "random"), default="neural",
        help="use NumPy brains (default) or the original random movement baseline",
    )
    args = parser.parse_args()
    if args.headless and args.frames is None:
        parser.error("--headless requires --frames so the run finishes automatically")
    return run(
        headless=args.headless,
        frames=args.frames,
        screenshot=args.screenshot,
        seed=args.seed,
        controller=args.controller,
    )


if __name__ == "__main__":
    raise SystemExit(main())
