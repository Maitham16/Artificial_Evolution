"""Plot paired held-out outcomes and uncertainty from a completed comparison."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".cache" / "matplotlib"))

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import PercentFormatter
import numpy as np

from compare_creatures import CONDITIONS, analyze_trials


def build_comparison_figure(report: dict) -> Figure:
    if report.get("status") != "complete":
        raise ValueError("Plot only a complete experiment; partial runs are not analyzed.")
    trials = report.get("trials", [])
    seeds = report.get("protocol", {}).get("training_seeds", [])
    if (not isinstance(trials, list) or not isinstance(seeds, list)
            or any(not isinstance(trial, dict) or "seed" not in trial for trial in trials)
            or len(trials) != len(seeds) or {trial["seed"] for trial in trials} != set(seeds)):
        raise ValueError("Completed trials must match all planned seeds.")
    try:
        comparisons = analyze_trials(trials)
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("Comparison is missing required held-out observations.") from error
    figure = Figure(figsize=(14, 8.4), facecolor="#f8fafc")
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 3)
    figure.subplots_adjust(left=0.12, right=0.98, bottom=0.18, top=0.83,
                           wspace=0.45, hspace=0.75)
    figure.suptitle("Evolved vs random behavior", fontsize=20, fontweight="bold", color="#172b3a", y=0.97)
    generations = report["protocol"]["training_generations"]
    figure.text(0.5, 0.915,
                f"{len(trials)} independent training seeds  |  {generations} generations  |  fresh held-out arenas",
                ha="center", fontsize=11, color="#526575")
    colors = ("#13856b", "#c28a1a", "#3779ba")
    definitions = (
        ("mean_fitness", "Fitness", "Mean fitness (points)", "Fitness difference", 1),
        ("survival_rate", "Survival to 60 seconds", "Starting population reaching age 60s", "Survival difference (percentage points)", 100),
        ("mean_food_eaten", "Food consumption", "Mean pellets eaten per creature", "Food difference (pellets / creature)", 1),
    )
    for axis in axes.flat:
        axis.set_facecolor("white")
        axis.tick_params(colors="#526575", labelsize=9)
        axis.set_axisbelow(True)
        for spine in axis.spines.values():
            spine.set_color("#d3dee6")
    for column, (metric, title, ylabel, difference_label, scale) in enumerate(definitions):
        axis, differences = axes[:, column]
        values = np.array([
            [trial["conditions"][condition]["evaluation"]["generations"][0][metric] * scale
             for condition in CONDITIONS] for trial in trials
        ])
        for row in values:
            axis.plot(range(3), row, color="#c1cbd2", linewidth=0.9, zorder=1)
        for index, color in enumerate(colors):
            axis.scatter(np.full(len(trials), index), values[:, index], color=color, s=22, zorder=2)
            axis.scatter(index, values[:, index].mean(), color=color, marker="D", s=80,
                         edgecolors="#172b3a", linewidths=1, zorder=3)
        axis.set_xticks(range(3), ["Evolved", "Random", "Unselected NN"])
        axis.set_xlim(-0.35, 2.35)
        axis.set_ylim(0, 100 if scale == 100 else max(1, values.max() * 1.15))
        axis.set_title(title, fontsize=13)
        axis.set_ylabel(ylabel, fontsize=10)
        axis.grid(axis="y", color="#dce5ec", linewidth=0.8)
        if scale == 100:
            axis.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
        differences.axvline(0, color="#8b9aa7", linestyle="--", linewidth=1)
        for index, control in enumerate(("random", "unselected")):
            stats = comparisons[f"evolved_vs_{control}"][metric]
            low, high = np.array(stats["difference_ci95"]) * scale
            center = stats["mean_difference"] * scale
            raw = values[:, 0] - values[:, index + 1]
            differences.scatter(raw, index + np.linspace(-0.12, 0.12, len(trials)),
                                s=16, color="#b7c3cd", zorder=1)
            differences.hlines(index, low, high, color=colors[index + 1], linewidth=3)
            differences.vlines([low, high], index - 0.06, index + 0.06,
                               color=colors[index + 1], linewidth=1.5)
            differences.scatter(center, index, marker="D", color=colors[index + 1], s=45, zorder=3)
        labels = ["vs random", "vs unselected NN"]
        if metric == "mean_fitness":
            labels = [
                label + f"\nHolm p={comparisons[f'evolved_vs_{control}'][metric]['holm_adjusted_p']:.3f}"
                for label, control in zip(labels, ("random", "unselected"))
            ]
        differences.set_yticks([0, 1], labels)
        differences.set_ylim(1.5, -0.5)
        differences.set_title(difference_label, fontsize=11)
        differences.set_xlabel("Evolved minus control", fontsize=10)
        differences.grid(axis="x", color="#dce5ec", linewidth=0.8)
    figure.text(0.12, 0.09,
                "Top: connected points are paired seeds; diamonds are means. Bottom: paired mean differences with 95% percentile bootstrap intervals.",
                fontsize=9, color="#526575")
    figure.text(0.12, 0.045,
                f"Positive differences favor evolved. Fitness: exact sign tests, Holm correction for two contrasts. Secondary intervals are descriptive; {len(trials)}-run pilot.",
                fontsize=9, color="#526575")
    return figure


def save_comparison_plot(report: dict, output: Path) -> None:
    output = Path(output)
    if output.suffix.lower() not in (".png", ".svg", ".pdf"):
        raise ValueError("Comparison output must use .png, .svg, or .pdf.")
    figure = build_comparison_figure(report)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=160, facecolor=figure.get_facecolor())
    finally:
        figure.clear()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, help="PNG, SVG, or PDF; defaults to report name with .png")
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text())
        if not isinstance(report, dict):
            raise ValueError("A comparison report must be a JSON object.")
        output = args.output if args.output is not None else args.report.with_suffix(".png")
        save_comparison_plot(report, output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Comparison plot saved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
