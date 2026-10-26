"""Launch the world, with optional Step 21 seasons and lineage extinction."""

import argparse
import json
import math
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from brain import DEFAULT_MUTATION_RATE, DEFAULT_MUTATION_SCALE
from creature import MAX_ENERGY, POPULATION_SIZE
from food import FOOD_COUNT
from generation_stats import SURVIVAL_CHECKPOINT_SECONDS
from perception import VISION_RANGE
from selection import FitnessEvaluation
from simulation import SPEEDS, EvolutionSimulation
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


def nonnegative_integer(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return number


def mutation_probability(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise argparse.ArgumentTypeError("must be a finite probability from 0 to 1")
    return number


def mutation_scale(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be finite and non-negative")
    return number


def handle_events(world: World, simulation: EvolutionSimulation | None = None) -> bool:
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
                world.show_history = False
            if event.key == pygame.K_t:
                world.show_history = not world.show_history
                world.show_fitness = False
            if event.key == pygame.K_a and simulation is not None:
                simulation.auto_advance = not simulation.auto_advance
            if event.key == pygame.K_s and simulation is not None:
                simulation.cycle_speed()
            if event.key == pygame.K_r:
                if simulation is not None:
                    simulation.restart()
                else:
                    world.regenerate_population()
            if event.key == pygame.K_n:
                if simulation is not None:
                    simulation.advance_generation()
                else:
                    world.advance_generation()
            if event.key == pygame.K_SPACE:
                world.paused = not world.paused
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not world.show_fitness and not world.show_history:
                world.select_creature((event.pos[0] - PADDING, event.pos[1] - HEADER_HEIGHT))
    return True


def draw_trend(
    screen: pygame.Surface, rect: pygame.Rect, title: str,
    series: list[tuple[list[float | None], tuple[int, int, int]]],
    generations: list[int], font: pygame.font.Font,
    ceiling: float | None = None,
) -> None:
    screen.blit(font.render(title, True, MUTED), (rect.left, rect.top - 22))
    available = [value for values, _ in series for value in values if value is not None]
    maximum = ceiling if ceiling is not None else max(1.0, max(available, default=0))
    plot = pygame.Rect(rect.left + 36, rect.top + 5, rect.width - 42, rect.height - 10)
    for fraction in (0.0, 0.5, 1.0):
        y = round(plot.bottom - fraction * plot.height)
        pygame.draw.line(screen, (31, 49, 56), (plot.left, y), (plot.right, y))
    for value, y in ((maximum, plot.top), (0, plot.bottom - 12)):
        screen.blit(font.render(f"{value:.0f}", True, MUTED), (rect.left, y))
    span = max(1, generations[-1] - generations[0])
    for values, color in series:
        segment = []
        for generation, value in zip(generations, values):
            if value is None:
                if len(segment) > 1:
                    pygame.draw.lines(screen, color, False, segment, 2)
                segment = []
                continue
            point = (round(plot.left + (generation - generations[0]) / span * plot.width),
                     round(plot.bottom - value / maximum * plot.height))
            segment.append(point)
            if len(generations) <= 50:
                pygame.draw.circle(screen, color, point, 3)
        if len(segment) > 1:
            pygame.draw.lines(screen, color, False, segment, 2)
    if not available:
        label = font.render("N/A", True, MUTED)
        screen.blit(label, label.get_rect(center=plot.center))
    screen.blit(font.render(f"G{generations[0]}", True, MUTED), (plot.left, rect.bottom + 5))
    if len(generations) > 1:
        label = font.render(f"G{generations[-1]}", True, MUTED)
        screen.blit(label, (plot.right - label.get_width(), rect.bottom + 5))


def draw_history_panel(
    screen: pygame.Surface, world: World, fonts: dict[str, pygame.font.Font],
) -> None:
    panel = pygame.Rect(0, 0, 900, 520)
    panel.center = (PADDING + world.width // 2, HEADER_HEIGHT + world.height // 2)
    pygame.draw.rect(screen, BACKGROUND, panel, border_radius=12)
    pygame.draw.rect(screen, MUTED, panel, width=1, border_radius=12)
    x, y = panel.left + 28, panel.top
    screen.blit(fonts["title"].render("Evolution across generations", True, TEXT), (x, y + 20))
    note = f"{len(world.generation_stats)} completed / fitness: mean (mint), best (gold)"
    if hasattr(world, "season_food"):
        note = f"{len(world.generation_stats)} completed / food and locations change; raw fitness is habitat-dependent"
    screen.blit(fonts["small"].render(note, True, ACCENT), (x, y + 61))
    stats = world.generation_stats
    if stats:
        generations = [row.generation for row in stats]
        draw_trend(screen, pygame.Rect(x, y + 110, 266, 140), "Fitness", [
            ([row.mean_fitness for row in stats], ACCENT),
            ([row.best_fitness for row in stats], (224, 205, 117)),
        ], generations, fonts["small"])
        checkpoint = SURVIVAL_CHECKPOINT_SECONDS
        draw_trend(screen, pygame.Rect(x + 288, y + 110, 266, 140), f"Reached {checkpoint:g}s (%)", [
            ([None if row.survival_rate is None else row.survival_rate * 100 for row in stats], (105, 194, 237)),
        ], generations, fonts["small"], ceiling=100)
        draw_trend(screen, pygame.Rect(x + 576, y + 110, 268, 140), "Meals per creature", [
            ([row.mean_food_eaten for row in stats], (166, 220, 100)),
        ], generations, fonts["small"])
        columns = (x, x + 50, x + 155, x + 255, x + 350, x + 450, x + 540, x + 675)
        headings = ("GEN", "MEAN FIT", "BEST FIT", "MEALS", "SURV 60s", "AGE (s)", "SPEED (px/s)", "FACING FOOD")
        for column, heading in zip(columns, headings):
            screen.blit(fonts["small"].render(heading, True, MUTED), (column, y + 284))
        for index, row in enumerate(stats[-8:]):
            facing = row.food_facing_fraction
            survival = row.survival_rate
            values = (str(row.generation), f"{row.mean_fitness:.1f}", f"{row.best_fitness:.1f}",
                      f"{row.mean_food_eaten:.2f}", "N/A" if survival is None else f"{survival:.0%}",
                      f"{row.mean_survival_seconds:.1f}",
                      f"{row.mean_speed:.1f}", "N/A" if facing is None else f"{facing:.1%}")
            for column, value in zip(columns, values):
                screen.blit(fonts["small"].render(value, True, TEXT), (column, y + 310 + index * 20))
    else:
        message = "Complete a generation to see its history. The world keeps running behind this panel."
        screen.blit(fonts["small"].render(message, True, TEXT), (x, y + 160))
    explanation = f"Survival = share reaching age {SURVIVAL_CHECKPOINT_SECONDS:g}s. Completed generations only; T closes."
    screen.blit(fonts["small"].render(explanation, True, MUTED), (x, panel.bottom - 29))


def draw_fitness_panel(
    screen: pygame.Surface, world: World, evaluation: FitnessEvaluation,
    fonts: dict[str, pygame.font.Font],
    simulation: EvolutionSimulation | None = None,
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
    action = "F  Close leaderboard"
    if evaluation.complete:
        if simulation is not None and simulation.finished:
            action = "Run complete     /     T  History     /     F  Close leaderboard"
        elif simulation is not None and simulation.auto_advance:
            action = "Auto cycling     /     T  History     /     F  Close leaderboard"
        else:
            action = "N  Next generation     /     F  Close leaderboard"
    screen.blit(fonts["small"].render(action, True, ACCENT), (x, panel.bottom - 25))


def draw_interface(
    screen: pygame.Surface, world: World, fonts: dict[str, pygame.font.Font],
    simulation: EvolutionSimulation | None = None,
) -> None:
    screen.fill(BACKGROUND)
    screen.blit(fonts["small"].render("ARTIFICIAL EVOLUTION", True, ACCENT), (40, 25))
    screen.blit(fonts["title"].render("The evolving world", True, TEXT), (38, 48))
    evaluation = world.get_fitness_evaluation()
    best_score = evaluation.best.fitness if evaluation.best is not None else 0.0
    controller_name = world.controller.upper()
    controller_label = (
        f"{controller_name} / BEST {best_score:.1f} / MEAN {evaluation.mean_fitness:.1f}"
    )
    if world.controller == "neural":
        brains = "Random brains" if world.generation == 1 else f"Mutate {world.mutation_rate:.0%}"
        controller_note = f"Gen {world.generation} / {brains} / Sight {VISION_RANGE:.0f} px"
    else:
        controller_note = f"Gen {world.generation} / {world.controller.title()} movement baseline"
    if simulation is not None:
        generation = str(world.generation)
        if simulation.generation_limit is not None:
            generation += f"/{simulation.generation_limit}"
        mode = "Done" if simulation.finished else "Auto" if simulation.auto_advance else "Manual"
        controller_note = f"Gen {generation} / {mode} / {simulation.speed}x / N {world.population_size} / Mut {world.mutation_rate * 100:g}%"
    screen.blit(fonts["small"].render(controller_label, True, ACCENT), (400, 31))
    screen.blit(fonts["small"].render(controller_note, True, MUTED), (400, 55))

    if getattr(world, "lineage_extinct", False):
        activity, status_color = "LINEAGE EXTINCT", (238, 115, 127)
    elif not world.creatures:
        activity, status_color = "COHORT COMPLETE", MUTED
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
    stage_text = "STEP 14 / PARAMETERS"
    if hasattr(world, "season_food"):
        context = world.environment_history[-1]
        stage_text = f"{context['season'].upper()} / FOOD {world.food_count}"
    stage = fonts["small"].render(stage_text, True, MUTED)
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
    if world.show_history:
        draw_history_panel(screen, world, fonts)
    elif world.show_fitness:
        draw_fitness_panel(screen, world, evaluation, fonts, simulation)
    elif not world.creatures:
        panel = pygame.Rect(0, 0, 580, 124)
        panel.center = (PADDING + world.width // 2, HEADER_HEIGHT + world.height // 2)
        pygame.draw.rect(screen, BACKGROUND, panel, border_radius=12)
        pygame.draw.rect(screen, MUTED, panel, width=1, border_radius=12)
        title_text = "Lineage extinct" if getattr(world, "lineage_extinct", False) else f"Generation {world.generation} complete"
        title = fonts["title"].render(title_text, True, TEXT)
        summary = (
            f"Best #{evaluation.best.creature_id:03d}: {evaluation.best.fitness:.1f} points"
            if evaluation.best is not None else "No creatures evaluated"
        )
        summary += f" / {len(evaluation.selected_ids)} selected"
        result = fonts["small"].render(summary, True, TEXT)
        hint_text = "N  Next generation    /    T  History    /    R  Restart"
        if getattr(world, "lineage_extinct", False):
            hint_text = "No eligible parents    /    T  History    /    R  Restart"
        elif simulation is not None and simulation.finished:
            hint_text = "Run complete    /    T  History    /    R  Restart"
        elif simulation is not None and simulation.auto_advance:
            hint_text = "Next generation starts automatically    /    T  History"
        hint = fonts["small"].render(hint_text, True, ACCENT)
        screen.blit(title, title.get_rect(center=(panel.centerx, panel.centery - 31)))
        screen.blit(result, result.get_rect(center=(panel.centerx, panel.centery + 5)))
        screen.blit(hint, hint.get_rect(center=(panel.centerx, panel.centery + 35)))

    footer_y = HEADER_HEIGHT + world.height + 16
    auto = "on" if simulation is None or simulation.auto_advance else "off"
    speed = simulation.speed if simulation is not None else 1
    controls = (
        f"Space {'Resume' if world.paused else 'Pause'}  /  A Auto {auto}  /  S {speed}x  /  "
        "T History  /  F Fitness  /  N Next  /  R Restart  /  G Grid  /  V Senses  /  Esc Quit"
    )
    screen.blit(fonts["small"].render(controls, True, MUTED), (PADDING, footer_y))

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
    generations: int | None = None,
    speed: int = 1,
    manual: bool = False,
    report: Path | None = None,
    plot: Path | None = None,
    population_size: int = POPULATION_SIZE,
    mutation_rate: float = DEFAULT_MUTATION_RATE,
    mutation_scale: float = DEFAULT_MUTATION_SCALE,
    food_count: int = FOOD_COUNT,
    fixed_speed: float | None = None,
    food_distribution: str = "uniform",
    seasons: bool = False,
    season_length: int = 1,
    season_food: tuple = (150, 200, 75, 25),
    cluster_shift: float = 120.0,
    reproductive_age: float = 60.0,
) -> int:
    if headless and frames is None and (generations is None or manual):
        raise ValueError("Headless mode needs frames or an automatic generation limit.")
    if headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"

    try:
        pygame.display.init()
        pygame.font.init()
        world_type, seasonal_options = World, {}
        if seasons:
            from seasons import SeasonalWorld
            world_type = SeasonalWorld
            seasonal_options = dict(season_length=season_length, season_food=season_food,
                                    cluster_shift=cluster_shift, reproductive_age=reproductive_age)
            fixed_speed = 60.0 if fixed_speed is None else fixed_speed
        world = world_type(seed=seed, controller=controller, population_size=population_size,
                      mutation_rate=mutation_rate, mutation_scale=mutation_scale, food_count=food_count,
                      fixed_speed=fixed_speed, food_distribution=food_distribution, **seasonal_options)
        simulation = EvolutionSimulation(world, generation_limit=generations,
                                         speed=speed, auto_advance=not manual)
        screen = pygame.display.set_mode(
            (world.width + 2 * PADDING, HEADER_HEIGHT + world.height + FOOTER_HEIGHT)
        )
        pygame.display.set_caption(f"Artificial Evolution | Fixed-speed study | {controller.title()}")
        fonts = {
            "title": pygame.font.Font(None, 38),
            "small": pygame.font.Font(None, 20),
        }
        clock = pygame.time.Clock()
        rendered_frames = 0
        reported_generations = 0
        print(
            f"World ready: {world.width} x {world.height}; "
            f"creatures: {len(world.creatures)}; seed: {world.seed}; "
            f"food: {len(world.food)}; "
            f"controller: {world.controller}; "
            f"mutation: {world.mutation_rate:g}; "
            f"speed: {simulation.speed}x; generations: {generations or 'unlimited'}; "
            f"display driver: {pygame.display.get_driver()}",
            flush=True,
        )

        while frames is None or rendered_frames < frames:
            frame_dt = clock.tick(0 if headless else TARGET_FPS) / 1000.0
            if not handle_events(world, simulation):
                break
            if len(world.generation_stats) < reported_generations:
                reported_generations = 0
            # Speed changes tick count per frame, never the physics timestep.
            dt = SIMULATION_STEP if headless else min(frame_dt, MAX_FRAME_SECONDS)
            simulation.update(dt)
            for stats in world.generation_stats[reported_generations:]:
                facing = stats.food_facing_fraction
                facing_label = "N/A" if facing is None else f"{facing:.1%}"
                seasonal_note = ""
                if seasons:
                    context = world.environment_history[stats.generation - 1]
                    seasonal_note = (f"; {context['season']}, food {context['food_count']}, "
                                     f"eligible parents {context['eligible_parent_count']}"
                                     + ("; LINEAGE EXTINCT" if world.lineage_extinct else ""))
                print(
                    f"Generation {stats.generation}: mean fitness {stats.mean_fitness:.2f}; "
                    f"best {stats.best_fitness:.2f}; meals/creature {stats.mean_food_eaten:.2f}; "
                    f"mean age {stats.mean_survival_seconds:.2f}s; facing food {facing_label}{seasonal_note}",
                    flush=True,
                )
                if simulation.finished:
                    world.show_history = True
                    world.show_fitness = False
            reported_generations = len(world.generation_stats)
            draw_interface(screen, world, fonts, simulation)
            pygame.display.flip()
            rendered_frames += 1
            if headless and simulation.finished:
                break

        if screenshot is not None and rendered_frames:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(screen, str(screenshot))
            print(f"Screenshot saved: {screenshot}")
        if report is not None:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(simulation.report(), indent=2, allow_nan=False) + "\n")
            print(f"Report saved: {report}")
        if plot is not None:
            if world.generation_stats:
                if seasons:
                    from plot_seasons import save_lineage_plot
                    save_lineage_plot(simulation.report(), plot)
                else:
                    from plot_evolution import save_evolution_plot
                    save_evolution_plot(simulation.report(), plot)
                print(f"Evolution plot saved: {plot}")
            else:
                print("Plot not saved: no completed generations.")
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
    parser.add_argument("--population", type=positive_integer, default=POPULATION_SIZE,
                        help="creatures born in each generation")
    parser.add_argument("--mutation-rate", type=mutation_probability, default=DEFAULT_MUTATION_RATE,
                        help="independent mutation probability per weight or bias")
    parser.add_argument("--mutation-scale", type=mutation_scale, default=DEFAULT_MUTATION_SCALE,
                        help="standard deviation of Gaussian mutation noise")
    parser.add_argument("--food-count", type=nonnegative_integer, default=FOOD_COUNT,
                        help="maintained food supply; fewer pellets increase scarcity")
    parser.add_argument("--fixed-speed", type=mutation_scale,
                        help="positive pixels/second shared by all bodies; overrides neural throttle")
    parser.add_argument("--food-distribution", choices=("uniform", "clustered"), default="uniform")
    parser.add_argument("--generations", type=positive_integer, help="stop after N complete generations")
    parser.add_argument("--seasons", action="store_true", help="enable seasonal clustered food and maturity-gated reproduction")
    parser.add_argument("--season-length", type=positive_integer, default=1, help="generations per season")
    parser.add_argument("--season-food", type=nonnegative_integer, nargs=4, default=(150, 200, 75, 25),
                        metavar=("SPRING", "SUMMER", "AUTUMN", "WINTER"), help="maintained pellets by season")
    parser.add_argument("--cluster-shift", type=mutation_scale, default=120.0, help="cluster displacement before bounded reflection")
    parser.add_argument("--reproductive-age", type=mutation_scale, default=60.0, help="minimum age for seasonal parent eligibility")
    parser.add_argument("--speed", type=int, choices=SPEEDS, default=1, help="simulation speed multiplier")
    parser.add_argument("--manual", action="store_true", help="wait for N between generations")
    parser.add_argument("--report", type=Path, help="save completed-generation observations as JSON")
    parser.add_argument("--plot", type=Path, help="export evolution charts as PNG, SVG, or PDF on exit")
    parser.add_argument(
        "--controller", choices=("neural", "random", "greedy"), default="neural",
        help="use NumPy brains, random steering, or greedy nearest-detected-food steering",
    )
    args = parser.parse_args()
    if args.fixed_speed is not None and args.fixed_speed <= 0:
        parser.error("--fixed-speed must be positive")
    if args.seasons and args.reproductive_age <= 0:
        parser.error("--reproductive-age must be positive")
    if args.headless and args.frames is None and (args.generations is None or args.manual):
        parser.error("--headless requires --frames or automatic --generations")
    return run(
        headless=args.headless,
        frames=args.frames,
        screenshot=args.screenshot,
        seed=args.seed,
        controller=args.controller,
        generations=args.generations,
        speed=args.speed,
        manual=args.manual,
        report=args.report,
        plot=args.plot,
        population_size=args.population,
        mutation_rate=args.mutation_rate,
        mutation_scale=args.mutation_scale,
        food_count=args.food_count,
        fixed_speed=args.fixed_speed,
        food_distribution=args.food_distribution,
        seasons=args.seasons,
        season_length=args.season_length,
        season_food=args.season_food,
        cluster_shift=args.cluster_shift,
        reproductive_age=args.reproductive_age,
    )


if __name__ == "__main__":
    raise SystemExit(main())
