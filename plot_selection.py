"""Training trajectories and paired held-out effects of fitness-based parent choice."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".cache" / "matplotlib"))

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np

from experiment_selection import ARMS, CONDITIONS, ENVIRONMENTS, analyze_results
from plot_intelligence import draw_effect


def build_selection_figure(report):
    if report.get("status") != "complete":
        raise ValueError("Plot only a complete paired-selection study.")
    analysis = analyze_results(report)
    figure = Figure(figsize=(15, 12), facecolor="#f8fafc")
    FigureCanvasAgg(figure)
    grid = figure.add_gridspec(3, 3, left=0.13, right=0.98, bottom=0.18, top=0.82, hspace=0.75, wspace=0.65)
    training = figure.add_subplot(grid[0, :])
    axes = [training]
    colors = {"selection": "#13856b", "random_parent": "#7a58a0", "founder": "#c28a1a"}
    names = {"selection": "Fitness selection", "random_parent": "Random parents", "founder": "Founders"}
    figure.suptitle("Does choosing successful parents improve evolution?", fontsize=20,
                   fontweight="bold", color="#172b3a", y=0.97)
    figure.text(0.5, 0.925,
                f"{analysis['independent_seed_pairs']} paired lineages  |  identical founders, bodies, mutation draws, and training budget",
                ha="center", fontsize=11, color="#526575")
    figure.text(0.5, 0.89, "Both arms inherit mutated weights through 20 parents, five offspring each. Only parent choice depends on fitness.",
                ha="center", fontsize=10, color="#526575")
    for arm in ARMS:
        curve = analysis["training_curves"][arm]
        training.plot(curve["generations"], curve["mean_fitness"], color=colors[arm], linewidth=2, label=names[arm])
        training.fill_between(curve["generations"], curve["low"], curve["high"], color=colors[arm], alpha=0.15)
    training.set_title("Training: paired uniform-food arenas; first generation identical", fontsize=11)
    training.set_xlabel("Generation", fontsize=10)
    training.set_ylabel("Mean fitness", fontsize=10)
    training.set_xticks(analysis["training_curves"]["selection"]["generations"])
    training.legend(loc="upper left", fontsize=9, frameon=False)
    training.grid(color="#dce5ec", linewidth=0.8)
    mean_axes, effect_axes, limits = [], [], [0.0]
    ymax = 1.0
    for column, environment in enumerate(ENVIRONMENTS):
        data = analysis["environments"][environment]
        values = data["seed_values"]
        upper, lower = figure.add_subplot(grid[1, column]), figure.add_subplot(grid[2, column])
        axes.extend((upper, lower))
        mean_axes.append(upper)
        effect_axes.append(lower)
        matrix = np.array([values[c]["mean_fitness"] for c in CONDITIONS]).T
        for observations in matrix:
            upper.plot(range(3), observations, color="#c1cbd2", linewidth=0.7, alpha=0.6, zorder=1)
        for index, name in enumerate(CONDITIONS):
            upper.scatter([index] * len(matrix), matrix[:, index], color=colors[name], s=18, zorder=2)
            upper.scatter(index, matrix[:, index].mean(), color=colors[name], marker="D", s=60,
                          edgecolors="#172b3a", linewidths=0.7, zorder=3)
        ymax = max(ymax, float(matrix.max()) * 1.12)
        upper.set_xticks(range(3), ["Selection", "Drift", "Founder"], fontsize=9)
        upper.set_xlim(-0.3, 2.3)
        upper.set_title(environment.replace("_", " ").title(), fontsize=13)
        upper.set_ylabel("Held-out mean fitness", fontsize=10)
        upper.grid(axis="y", color="#dce5ec", linewidth=0.8)
        ticks = []
        for position, (label, title, right) in enumerate((
            ("selection_vs_random_parent", "Selection − drift", "random_parent"),
            ("selection_vs_founder", "Selection − founder", "founder"),
        )):
            effect = data["comparisons"][label]["mean_fitness"]
            raw = np.asarray(values["selection"]["mean_fitness"]) - values[right]["mean_fitness"]
            draw_effect(lower, effect, raw, position, colors["selection"] if position == 0 else "#3779ba")
            limits.extend([*raw, *effect["difference_ci95"]])
            ticks.append(f"{title}\np={effect['holm_adjusted_p']:.4g}\n{effect['conclusion']}")
        lower.set_yticks([0, 1], ticks, fontsize=8)
        lower.set_ylim(1.5, -0.5)
        lower.axvline(0, color="#8b9aa7", linestyle="--", linewidth=1)
        lower.set_title("Paired fitness effects", fontsize=11)
        lower.set_xlabel("Fitness difference", fontsize=10)
        lower.grid(axis="x", color="#dce5ec", linewidth=0.8)
    for axis in mean_axes:
        axis.set_ylim(0, ymax)
    low, high = min(limits), max(limits)
    pad = max(1.0, (high - low) * 0.06)
    for axis in effect_axes:
        axis.set_xlim(low - pad, high + pad)
    for axis in axes:
        axis.set_facecolor("white")
        axis.set_axisbelow(True)
        axis.tick_params(colors="#526575", labelsize=8)
        for spine in axis.spines.values():
            spine.set_color("#d3dee6")
    figure.text(0.075, 0.11, "Points: independent seed-pair means; diamonds: means. Training bands and effect intervals: pointwise 95% seed bootstrap.",
                fontsize=9, color="#526575")
    figure.text(0.075, 0.075, "All displayed p-values: six primary exact paired sign tests with Holm correction. Testing freezes all 100 brains from each birth cohort.",
                fontsize=9, color="#526575")
    figure.text(0.075, 0.04, "Drift means random-parent inheritance with matched mutation, not random movement or new random brains. Evidence applies to this model and budget.",
                fontsize=9, color="#526575")
    return figure


def save_selection_plot(report, output):
    output = Path(output)
    if output.suffix.lower() not in (".png", ".svg", ".pdf"):
        raise ValueError("Plot output must use .png, .svg, or .pdf.")
    figure = build_selection_figure(report)
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
        save_selection_plot(json.loads(args.report.read_text()), args.output or args.report.with_suffix(".png"))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
