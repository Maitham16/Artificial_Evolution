"""Plot exploratory parameter effects and paired evolved-minus-random fitness."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".cache" / "matplotlib"))

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import numpy as np

from experiment_parameters import STANDARD, Setting, analyze_sweep


def build_parameter_figure(report: dict) -> Figure:
    if report.get("status") != "complete":
        raise ValueError("Plot only a complete parameter sweep.")
    summary = analyze_sweep(report)
    settings = [Setting(**values) for values in report["protocol"]["settings"]]
    figure = Figure(figsize=(14, 8.5), facecolor="#f8fafc")
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 3, sharey="row", sharex="col")
    figure.subplots_adjust(left=0.075, right=0.98, bottom=0.17, top=0.81,
                           wspace=0.25, hspace=0.55)
    figure.suptitle("Evolutionary parameter sweep", fontsize=20, fontweight="bold", color="#172b3a", y=0.97)
    protocol = report["protocol"]
    figure.text(0.5, 0.917,
                f"{len(report['runs'])} independent seeds  |  {protocol['generations']} training generations  |  one factor at a time  |  fresh validation arenas",
                ha="center", fontsize=11, color="#526575")
    colors = ("#13856b", "#c28a1a", "#3779ba")
    figure.legend(handles=[
        Line2D([0], [0], color=colors[0], marker="o", label="Evolved mean"),
        Line2D([0], [0], color=colors[1], marker="o", label="Random mean"),
        Line2D([0], [0], color="#8b9aa7", linestyle="--", label="Standard parameter value"),
    ], loc="upper center", bbox_to_anchor=(0.5, 0.89), ncol=3, frameon=False, fontsize=10)
    definitions = (
        ("mutation_rate", "Mutation rate", "Probability per weight / bias"),
        ("population_size", "Population size", "Creatures per generation"),
        ("food_count", "Environmental difficulty", "Maintained food pellets (more = easier)"),
    )
    all_fitness, all_limits = [], [0.0]
    for axis in axes.flat:
        axis.set_facecolor("white")
        axis.tick_params(colors="#526575", labelsize=9)
        axis.grid(axis="y", color="#dce5ec", linewidth=0.8)
        axis.set_axisbelow(True)
        for spine in axis.spines.values():
            spine.set_color("#d3dee6")
    for column, (factor, title, xlabel) in enumerate(definitions):
        cases = sorted((s for s in settings if all(
            getattr(s, other) == getattr(STANDARD, other)
            for other in ("mutation_rate", "population_size", "food_count") if other != factor
        )), key=lambda setting: getattr(setting, factor))
        x = [getattr(case, factor) for case in cases]
        upper, lower = axes[:, column]
        summaries = [summary[case.key]["metrics"]["mean_fitness"]["evolved_vs_random"] for case in cases]
        for index, field in enumerate(("left_mean", "right_mean")):
            means = [row[field] for row in summaries]
            upper.plot(x, means, color=colors[index], marker="o", linewidth=2, zorder=3)
            for case, value in zip(cases, x):
                raw = [
                    (run["settings"][case.key]["validation"] if index == 0 else
                     run["random_controls"][case.ecology_key]["validation"])["generations"][0]["mean_fitness"]
                    for run in report["runs"]
                ]
                upper.scatter([value] * len(raw), raw, color=colors[index], s=18, alpha=0.4, zorder=2)
                all_fitness.extend(raw)
        width = (max(x) - min(x) or 1) * 0.025
        for value, row in zip(x, summaries):
            low, high = row["difference_ci95"]
            lower.vlines(value, low, high, color=colors[2], linewidth=2)
            lower.hlines([low, high], value - width, value + width, color=colors[2], linewidth=1.5)
            all_limits.extend((low, high, row["mean_difference"]))
        lower.plot(x, [row["mean_difference"] for row in summaries], color=colors[2], marker="o", linewidth=1.5)
        lower.axhline(0, color="#697c8d", linewidth=1)
        for axis in (upper, lower):
            axis.axvline(getattr(STANDARD, factor), color="#8b9aa7", linestyle="--", linewidth=1)
            labels = [f"{value * 100:g}%" if factor == "mutation_rate" else str(value) for value in x]
            axis.set_xticks(x, labels)
            axis.margins(x=0.13)
        upper.set_title(title, fontsize=13)
        upper.tick_params(labelbottom=True)
        lower.set_xlabel(xlabel, fontsize=10)
    axes[0, 0].set_ylabel("Validation mean fitness (points)", fontsize=11)
    axes[1, 0].set_ylabel("Evolved minus random (points)", fontsize=11)
    axes[0, 0].set_ylim(0, max(1, max(all_fitness) * 1.15))
    span = max(1, max(all_limits) - min(all_limits))
    axes[1, 0].set_ylim(min(all_limits) - 0.1 * span, max(all_limits) + 0.1 * span)
    figure.text(0.075, 0.085,
                "Top: points are seed outcomes; lines join means. Bottom: paired mean fitness gaps with 95% pointwise percentile bootstrap intervals.",
                fontsize=9, color="#526575")
    figure.text(0.075, 0.04,
                "Exploratory validation, not a confirmed optimum. Population changes also change density and training lives; interactions are not estimated.",
                fontsize=9, color="#526575")
    return figure


def save_parameter_plot(report: dict, output: Path) -> None:
    output = Path(output)
    if output.suffix.lower() not in (".png", ".svg", ".pdf"):
        raise ValueError("Parameter plot output must use .png, .svg, or .pdf.")
    figure = build_parameter_figure(report)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(output, dpi=160, facecolor=figure.get_facecolor())
    finally:
        figure.clear()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text())
        if not isinstance(report, dict):
            raise ValueError("A sweep report must be a JSON object.")
        output = args.output if args.output is not None else args.report.with_suffix(".png")
        save_parameter_plot(report, output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Parameter plot saved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
