"""Display food-sensor interventions, ancestral controls, and attribution contrasts."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".cache" / "matplotlib"))

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np

from experiment_strategy import CONDITIONS, ENVIRONMENTS, analyze_results
from plot_intelligence import draw_effect


def build_strategy_figure(report):
    if report.get("status") != "complete":
        raise ValueError("Plot only a complete strategy analysis.")
    analysis = analyze_results(report)
    figure = Figure(figsize=(15, 12), facecolor="#f8fafc")
    FigureCanvasAgg(figure)
    axes = figure.subplots(3, 3)
    figure.subplots_adjust(left=0.13, right=0.98, top=0.80, bottom=0.17, hspace=0.7, wspace=0.7)
    figure.suptitle("What did the fixed-speed creatures learn?", fontsize=20, fontweight="bold", color="#172b3a", y=0.97)
    figure.text(0.5, 0.925,
                f"{analysis['independent_lineages']} saved lineages  |  evolved × unselected founders × three sensor modes  |  60 pixels/s",
                ha="center", fontsize=11, color="#526575")
    figure.text(0.5, 0.89, "New matched layouts. Frozen weights. Food and observations stay truthful; only brain inputs change.",
                ha="center", fontsize=10, color="#526575")
    colors = ("#13856b", "#4e9c88", "#88b6a9", "#7a58a0", "#9a7aba", "#b9a3cc", "#c28a1a")
    labels = ("E", "E↔", "EØ", "U", "U↔", "UØ", "R")
    meal_limit = 1.0
    limits = {1: [0.0], 2: [0.0]}
    for column, environment in enumerate(ENVIRONMENTS):
        data = analysis["environments"][environment]
        values = data["seed_values"]
        meals = np.array([values[c]["mean_food_eaten"] for c in CONDITIONS]).T
        axis = axes[0, column]
        for row in meals:
            axis.plot(range(7), row, color="#c1cbd2", linewidth=0.7, alpha=0.65, zorder=1)
        for index, color in enumerate(colors):
            axis.scatter([index] * len(meals), meals[:, index], color=color, s=16, zorder=2)
            axis.scatter(index, meals[:, index].mean(), color=color, marker="D", s=50,
                         edgecolors="#172b3a", linewidths=0.7, zorder=3)
        meal_limit = max(meal_limit, float(meals.max()) * 1.12)
        axis.set_xticks(range(7), labels, fontsize=9)
        axis.set_xlim(-0.4, 6.4)
        axis.set_ylabel("Meals per creature", fontsize=10)
        axis.set_title(environment.replace("_", " ").title(), fontsize=13)
        axis.grid(axis="y", color="#dce5ec", linewidth=0.8)
        food = {c: np.asarray(v["mean_food_eaten"]) for c, v in values.items()}
        fitness = {c: np.asarray(v["mean_fitness"]) for c, v in values.items()}
        rows = (
            (1, "Direct food-bearing benefit", "Meals per creature", (
                ("useful_bearing", "E bearing use", food["evolved_intact"] - food["evolved_mirrored"], "#13856b"),
                ("evolved_bearing_benefit", "Benefit above U", (food["evolved_intact"] - food["evolved_mirrored"]) -
                 (food["unselected_intact"] - food["unselected_mirrored"]), "#7a58a0"))),
            (2, "Evolutionary-history fitness gains", "Fitness difference", (
                ("evolution_advantage", "Intact E − U", fitness["evolved_intact"] - fitness["unselected_intact"], "#3779ba"),
                ("residual_advantage", "Hidden E − U", fitness["evolved_hidden"] - fitness["unselected_hidden"], "#c28a1a"))),
        )
        for row_index, title, xlabel, effects in rows:
            axis = axes[row_index, column]
            ticks = []
            for position, (name, label, raw, color) in enumerate(effects):
                effect = data["primary_tests"][name]
                draw_effect(axis, effect, raw, position, color)
                limits[row_index].extend([*raw, *effect["difference_ci95"]])
                ticks.append(f"{label}\np={effect['holm_adjusted_p']:.4g}\n{effect['conclusion']}")
            axis.axvline(0, color="#8b9aa7", linestyle="--", linewidth=1)
            axis.set_yticks([0, 1], ticks, fontsize=8)
            axis.set_ylim(1.5, -0.5)
            axis.set_title(title, fontsize=10)
            axis.set_xlabel(xlabel, fontsize=10)
            axis.grid(axis="x", color="#dce5ec", linewidth=0.8)
    for column in range(3):
        axes[0, column].set_ylim(0, meal_limit)
        for row_index in (1, 2):
            low, high = min(limits[row_index]), max(limits[row_index])
            pad = max(1.0, (high - low) * 0.06)
            axes[row_index, column].set_xlim(low - pad, high + pad)
    for axis in axes.flat:
        axis.set_facecolor("white")
        axis.set_axisbelow(True)
        axis.tick_params(colors="#526575", labelsize=8)
        for spine in axis.spines.values():
            spine.set_color("#d3dee6")
    figure.text(0.075, 0.105, "E: evolved. U: unselected founders. ↔: mirrored bearing. Ø: direct food inputs hidden. R: random steering.",
                fontsize=10, color="#526575")
    figure.text(0.075, 0.07, "Points: lineage means; diamonds: means. Intervals: pointwise 95% paired bootstrap. All p-values use Holm correction over 12 tests.",
                fontsize=9, color="#526575")
    figure.text(0.075, 0.035, "Hidden inputs change the input distribution; hunger retains indirect eating feedback. Residual gains do not identify an exclusive movement strategy.",
                fontsize=9, color="#526575")
    return figure


def save_strategy_plot(report, output):
    output = Path(output)
    if output.suffix.lower() not in (".png", ".svg", ".pdf"):
        raise ValueError("Plot output must use .png, .svg, or .pdf.")
    figure = build_strategy_figure(report)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=160, facecolor=figure.get_facecolor())
    finally:
        figure.clear()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text())
        save_strategy_plot(report, args.output or args.report.with_suffix(".png"))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
