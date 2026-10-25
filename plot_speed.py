"""Plot paired fixed-speed steering comparisons across unseen food environments."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".cache" / "matplotlib"))

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np

from experiment_speed import CONDITIONS, ENVIRONMENTS, FIXED_SPEED, METRICS, analyze_results


def build_speed_figure(report):
    if report.get("status") != "complete":
        raise ValueError("Plot only a complete fixed-speed study.")
    analysis = analyze_results(report)
    figure = Figure(figsize=(14, 12), facecolor="#f8fafc")
    FigureCanvasAgg(figure)
    axes = figure.subplots(3, 3)
    figure.subplots_adjust(left=0.07, right=0.98, top=0.82, bottom=0.16, hspace=0.78, wspace=0.32)
    figure.suptitle("Can evolution beat random steering at equal speed?", fontsize=19,
                   fontweight="bold", color="#172b3a", y=0.97)
    n = analysis["independent_lineages"]
    figure.text(0.5, 0.925, f"{n} independent retrained lineages  |  {FIXED_SPEED:g} pixels/s for every controller  |  frozen held-out tests",
                ha="center", fontsize=11, color="#526575")
    figure.text(0.5, 0.89, "Training: uniform food, 1000 × 600. Testing: new uniform and clustered layouts, plus unfamiliar geometry.",
                ha="center", fontsize=10, color="#526575")
    labels = {"mean_fitness": "Mean fitness", "mean_food_eaten": "Meals per creature", "survival_rate": "Surviving to 60 seconds"}
    colors = ("#13856b", "#c28a1a", "#3779ba")
    for column, environment in enumerate(ENVIRONMENTS):
        data = analysis["environments"][environment]
        for row, metric in enumerate(METRICS):
            axis = axes[row, column]
            matrix = np.array([data["seed_values"][condition][metric] for condition in CONDITIONS]).T
            scale = 100 if metric == "survival_rate" else 1
            matrix *= scale
            for observations in matrix:
                axis.plot(range(3), observations, color="#c1cbd2", linewidth=0.7, alpha=0.65, zorder=1)
            for index, color in enumerate(colors):
                axis.scatter([index] * n, matrix[:, index], s=16, color=color, alpha=0.8, zorder=2)
                axis.scatter(index, matrix[:, index].mean(), s=65, marker="D", color=color,
                             edgecolors="#172b3a", linewidths=0.8, zorder=3)
            effect = data["contrasts"]["random"][metric]
            low, high = np.array(effect["difference_ci95"]) * scale
            difference = effect["mean_difference"] * scale
            unit = " pp" if scale == 100 else ""
            axis.set_title(f"{environment.replace('_', ' ').title()}\n"
                           f"E − R: {difference:+.2f}{unit} [{low:+.2f}, {high:+.2f}]\n"
                           f"Holm p={effect['holm_adjusted_p']:.4f}; {effect['conclusion']}", fontsize=10)
            axis.set_ylabel(labels[metric] + (" (%)" if scale == 100 else ""), fontsize=10)
            axis.set_xticks(range(3), ["Evolved", "Random", "Greedy"])
            axis.set_xlim(-0.3, 2.3)
            axis.set_ylim(bottom=0, top=105 if scale == 100 else None)
            axis.set_facecolor("white")
            axis.set_axisbelow(True)
            axis.grid(axis="y", color="#dce5ec", linewidth=0.8)
            axis.tick_params(colors="#526575", labelsize=9)
            for spine in axis.spines.values():
                spine.set_color("#d3dee6")
    figure.text(0.07, 0.095, "Points: independent lineage means; layouts averaged within lineage. Diamonds: means. Lines: matched conditions.",
                fontsize=10, color="#526575")
    figure.text(0.07, 0.06, "E − R intervals: 95% paired percentile bootstrap. Nine primary sign tests use Holm correction. Greedy is a descriptive reference.",
                fontsize=10, color="#526575")
    figure.text(0.07, 0.025, "Fixed speed equalizes per-second movement cost, not total lifetime energy. Conclusions apply to the declared training budget and environments.",
                fontsize=9, color="#526575")
    return figure


def save_speed_plot(report, output):
    output = Path(output)
    if output.suffix.lower() not in (".png", ".svg", ".pdf"):
        raise ValueError("Plot output must use .png, .svg, or .pdf.")
    figure = build_speed_figure(report)
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
        save_speed_plot(report, args.output or args.report.with_suffix(".png"))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
