"""Export fitness, survival, and food-consumption plots from a saved run report."""

import argparse
import json
import math
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".cache" / "matplotlib"))

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator, PercentFormatter

from generation_stats import SURVIVAL_CHECKPOINT_SECONDS


def plot_data(report: dict) -> tuple[list[dict], float]:
    """Validate observations; survival counts are never inferred from mean age."""
    rows = report.get("generations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Complete at least one generation before plotting.")
    previous_generation = 0
    checkpoints = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each generation must be an observation record.")
        generation = row.get("generation")
        if type(generation) is not int or generation <= previous_generation:
            raise ValueError("Generation numbers must be positive, unique, and increasing.")
        previous_generation = generation
        for name in ("mean_fitness", "best_fitness", "mean_food_eaten"):
            value = row.get(name)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be a finite, non-negative number.")
        population = row.get("population_size")
        if type(population) is not int or population < 1:
            raise ValueError("Each generation needs a positive population size.")
        count = row.get("survivors_at_checkpoint")
        if count is not None:
            if type(count) is not int or not 0 <= count <= population:
                raise ValueError("Survival count must be between zero and population size.")
            checkpoint = row.get("survival_checkpoint_seconds")
            if not isinstance(checkpoint, (int, float)) or not math.isfinite(checkpoint) or checkpoint <= 0:
                raise ValueError("Survival counts need a finite, positive checkpoint age.")
            checkpoints.add(float(checkpoint))
            rate = row.get("survival_rate", count / population)
            if not isinstance(rate, (int, float)) or not math.isclose(rate, count / population):
                raise ValueError("Survival rate must match the recorded count and population.")
    if len(checkpoints) > 1:
        raise ValueError("All generations must use the same survival checkpoint age.")
    return rows, next(iter(checkpoints), SURVIVAL_CHECKPOINT_SECONDS)


def build_figure(report: dict) -> Figure:
    rows, checkpoint = plot_data(report)
    generations = [row["generation"] for row in rows]
    mean = [row["mean_fitness"] for row in rows]
    best = [row["best_fitness"] for row in rows]
    meals = [row["mean_food_eaten"] for row in rows]
    survival = [
        100 * row["survivors_at_checkpoint"] / row["population_size"]
        if row.get("survivors_at_checkpoint") is not None else math.nan
        for row in rows
    ]
    figure = Figure(figsize=(14, 4.8), facecolor="#f8fafc")
    FigureCanvasAgg(figure)
    axes = figure.subplots(1, 3)
    figure.subplots_adjust(left=0.065, right=0.98, bottom=0.22, top=0.76, wspace=0.34)
    figure.suptitle("Evolution across generations", fontsize=20, fontweight="bold", color="#172b3a", y=0.96)
    metadata = f"Seed {report.get('seed', '?')}  |  {report.get('controller', 'unknown')} controller  |  {len(rows)} completed generations"
    figure.text(0.5, 0.85, metadata, ha="center", fontsize=11, color="#526575")
    for axis in axes:
        axis.set_facecolor("white")
        axis.set_xlabel("Generation", color="#172b3a")
        axis.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
        if len(generations) <= 12:
            axis.set_xticks(generations)
        axis.set_xlim(generations[0] - 0.3, generations[-1] + 0.3)
        axis.grid(axis="y", color="#dce5ec", linewidth=0.8)
        axis.set_axisbelow(True)
        axis.tick_params(colors="#526575", labelsize=9)
        for spine in axis.spines.values():
            spine.set_color("#d3dee6")
    line_style = dict(marker="o", markersize=4, linewidth=2)
    axes[0].plot(generations, mean, label="Mean", color="#13856b", **line_style)
    axes[0].plot(generations, best, label="Best", color="#c28a1a", **line_style)
    axes[0].set(title="Fitness", ylabel="Fitness (points)", ylim=(0, max(1, max(best + mean) * 1.15)))
    axes[0].legend(frameon=False, fontsize=9)
    axes[1].plot(generations, survival, color="#3779ba", **line_style)
    axes[1].set(title=f"Survival to {checkpoint:g} seconds", ylabel="Starting population reaching this age", ylim=(0, 100))
    axes[1].set_yticks([0, 25, 50, 75, 100])
    axes[1].yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    if all(math.isnan(value) for value in survival):
        axes[1].text(0.5, 0.5, "Checkpoint counts not recorded\nRe-run to collect survival rates",
                     ha="center", va="center", transform=axes[1].transAxes, color="#526575", fontsize=10)
    axes[2].plot(generations, meals, color="#4e8d36", **line_style)
    axes[2].set(title="Food consumption", ylabel="Mean pellets eaten per creature", ylim=(0, max(1, max(meals) * 1.15)))
    figure.text(0.065, 0.035,
                f"Survival = creatures reaching age {checkpoint:g}s / starting population. Completed generations only; one run, without uncertainty estimates.",
                fontsize=9, color="#526575")
    return figure


def save_evolution_plot(report: dict, output: Path) -> None:
    output = Path(output)
    if output.suffix.lower() not in (".png", ".svg", ".pdf"):
        raise ValueError("Plot output must use .png, .svg, or .pdf.")
    figure = build_figure(report)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=160, facecolor=figure.get_facecolor())
    finally:
        figure.clear()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="JSON report written by main.py --report")
    parser.add_argument("--output", type=Path, help="output PNG, SVG, or PDF; defaults to report name with .png")
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text())
        if not isinstance(report, dict):
            raise ValueError("A run report must be a JSON object.")
        output = args.output if args.output is not None else args.report.with_suffix(".png")
        save_evolution_plot(report, output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Evolution plot saved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
