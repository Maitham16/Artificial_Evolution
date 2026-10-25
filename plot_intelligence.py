"""Visualize repeated unseen-environment tests and counterfactual steering evidence."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".cache" / "matplotlib"))

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np

from analyze_intelligence import CONDITIONS, ENVIRONMENTS, analyze_results


def draw_effect(axis, row: dict, raw, y: int, color: str):
    low, high = row["difference_ci95"]
    axis.scatter(raw, y + np.linspace(-0.12, 0.12, len(raw)), color="#b7c3cd", s=18, zorder=1)
    axis.hlines(y, low, high, color=color, linewidth=3)
    axis.vlines([low, high], y - 0.07, y + 0.07, color=color, linewidth=1.5)
    axis.scatter(row["mean_difference"], y, color=color, marker="D", s=45, zorder=3)


def build_intelligence_figure(report: dict) -> Figure:
    if report.get("status") != "complete":
        raise ValueError("Plot only a complete intelligence analysis.")
    analysis = analyze_results(report)
    trials = sorted(report["trials"], key=lambda trial: report["protocol"]["seeds"].index(trial["seed"]))
    figure = Figure(figsize=(14, 8.6), facecolor="#f8fafc")
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 3)
    figure.subplots_adjust(left=0.075, right=0.98, bottom=0.18, top=0.82,
                           wspace=0.45, hspace=0.78)
    figure.suptitle("Does food information guide behavior?", fontsize=20, fontweight="bold", color="#172b3a", y=0.97)
    repeats = report["protocol"]["repeats_per_environment"]
    figure.text(0.5, 0.915,
                f"{len(trials)} independent lineages  |  {repeats} unseen layouts per environment  |  frozen original-setting brains",
                ha="center", fontsize=11, color="#526575")
    colors = ("#13856b", "#bd514b", "#8870a7", "#3779ba", "#c28a1a")
    for axis in axes.flat:
        axis.set_facecolor("white")
        axis.tick_params(colors="#526575", labelsize=9)
        for spine in axis.spines.values():
            spine.set_color("#d3dee6")
        axis.set_axisbelow(True)
    meal_limit = 1.0
    for column, environment in enumerate(ENVIRONMENTS):
        values = analysis["environments"][environment]["seed_values"]
        matrix = np.array([values[condition]["mean_food_eaten"] for condition in CONDITIONS]).T
        upper, lower = axes[:, column]
        for row in matrix:
            upper.plot(range(5), row, color="#c1cbd2", linewidth=0.8, alpha=0.7, zorder=1)
        for index, color in enumerate(colors):
            upper.scatter([index] * len(trials), matrix[:, index], color=color, s=18, zorder=2)
            upper.scatter(index, matrix[:, index].mean(), color=color, marker="D", s=65,
                          edgecolors="#172b3a", linewidths=0.8, zorder=3)
        meal_limit = max(meal_limit, float(matrix.max()) * 1.15)
        upper.set_xticks(range(5), ["Intact", "Mirror", "Hidden", "Founder", "Random"], fontsize=8)
        upper.set_xlim(-0.35, 4.35)
        upper.set_title(f"{environment.title()} arena", fontsize=13)
        upper.set_ylabel("Mean meals / creature", fontsize=10)
        upper.grid(axis="y", color="#dce5ec", linewidth=0.8)
        primary = analysis["primary_tests"][f"food_direction_{environment}"]
        raw = np.array(values["intact"]["mean_food_eaten"]) - values["mirrored"]["mean_food_eaten"]
        draw_effect(lower, primary, raw, 0, colors[1])
        lower.axvline(0, color="#8b9aa7", linestyle="--", linewidth=1)
        lower.set_yticks([])
        lower.set_ylim(-0.5, 0.5)
        lower.set_title(f"Intact minus mirrored food intake\nHolm p={primary['holm_adjusted_p']:.3f}; {primary['conclusion']}", fontsize=10)
        lower.set_xlabel("Meals per creature", fontsize=10)
        lower.grid(axis="x", color="#dce5ec", linewidth=0.8)
    for column in (0, 1):
        axes[0, column].set_ylim(0, meal_limit)
    evolved = np.array([trial["probes"]["evolved"]["mean_steering_gain"] for trial in trials])
    founders = np.array([trial["probes"]["founder"]["mean_steering_gain"] for trial in trials])
    upper, lower = axes[:, 2]
    for left, right in zip(evolved, founders):
        upper.plot([0, 1], [left, right], color="#c1cbd2", linewidth=0.8, zorder=1)
    for index, (values, color) in enumerate(((evolved, colors[0]), (founders, colors[3]))):
        upper.scatter([index] * len(trials), values, color=color, s=22, zorder=2)
        upper.scatter(index, values.mean(), color=color, marker="D", s=65,
                      edgecolors="#172b3a", linewidths=0.8, zorder=3)
    upper.axhline(0, color="#8b9aa7", linestyle="--", linewidth=1)
    upper.set_xticks([0, 1], ["Evolved", "Founder"])
    upper.set_xlim(-0.3, 1.3)
    upper.set_title("Controlled left/right probe", fontsize=13)
    upper.set_ylabel("Signed steering gain", fontsize=10)
    upper.grid(axis="y", color="#dce5ec", linewidth=0.8)
    labels = []
    for index, (name, title, raw) in enumerate((
        ("directional_response", "Response > 0", evolved),
        ("response_emergence", "Above founders", evolved - founders),
    )):
        row = analysis["primary_tests"][name]
        draw_effect(lower, row, raw, index, colors[0] if index == 0 else colors[3])
        labels.append(f"{title}\nHolm p={row['holm_adjusted_p']:.3f}")
    lower.axvline(0, color="#8b9aa7", linestyle="--", linewidth=1)
    lower.set_yticks([0, 1], labels, fontsize=8)
    lower.set_ylim(1.5, -0.5)
    lower.set_title("Directional-response evidence", fontsize=11)
    lower.set_xlabel("Signed gain difference", fontsize=10)
    lower.grid(axis="x", color="#dce5ec", linewidth=0.8)
    decision = "all met" if analysis["generalized_food_seeking_demonstrated"] else "not all met"
    figure.text(0.075, 0.09,
                f"Operational criteria: {decision}. Points represent independent lineages; repeats are averaged within each lineage and environment.",
                fontsize=9, color="#526575")
    figure.text(0.075, 0.045,
                "Intervals: 95% paired percentile bootstrap. Four primary sign tests use Holm correction. This assesses reactive food guidance, not human-like cognition.",
                fontsize=9, color="#526575")
    return figure


def save_intelligence_plot(report: dict, output: Path) -> None:
    output = Path(output)
    if output.suffix.lower() not in (".png", ".svg", ".pdf"):
        raise ValueError("Intelligence plot output must use .png, .svg, or .pdf.")
    figure = build_intelligence_figure(report)
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
            raise ValueError("An intelligence report must be a JSON object.")
        output = args.output if args.output is not None else args.report.with_suffix(".png")
        save_intelligence_plot(report, output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Intelligence plot saved: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
