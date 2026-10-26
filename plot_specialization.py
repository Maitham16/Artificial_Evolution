"""Cross-environment performance matrices and corrected home-advantage contrasts."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".cache" / "matplotlib"))

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
import numpy as np

from experiment_specialization import HABITATS, REGIMES, analyze_results
from plot_intelligence import draw_effect


def build_specialization_figure(report):
    if report.get("status") != "complete":
        raise ValueError("Plot only a complete specialization study.")
    analysis = analyze_results(report)
    figure = Figure(figsize=(15, 11), facecolor="#f8fafc")
    FigureCanvasAgg(figure)
    grid = figure.add_gridspec(2, 6, left=0.13, right=0.97, bottom=0.20, top=0.81, hspace=0.65, wspace=1.0)
    raw_axis, relative_axis = figure.add_subplot(grid[0, :3]), figure.add_subplot(grid[0, 3:])
    matrix = np.array(analysis["performance_matrices"]["mean_fitness"])
    relative = matrix - matrix[-1]
    n = analysis["independent_seed_groups"]
    figure.suptitle("Specialization or generalization?", fontsize=21, fontweight="bold", color="#172b3a", y=0.97)
    figure.text(0.5, 0.925, f"{n} matched seed groups  |  three specialists + a domain-cycling generalist  |  frozen matched tests",
                ha="center", fontsize=11, color="#526575")
    figure.text(0.5, 0.885, "Same population, speed, mutation draws, and training budget. Generalists receive equal habitat exposures.",
                ha="center", fontsize=10, color="#526575")
    vmax = max(float(np.max(np.abs(relative))), 1.0)
    for axis, data, title, cmap, low, high in (
        (raw_axis, matrix, "Mean fitness: training regime × test habitat", "YlGnBu", 0, float(matrix.max()) * 1.05),
        (relative_axis, relative, "Fitness difference from generalist in each column", "RdBu", -vmax, vmax),
    ):
        shown = axis.imshow(data, cmap=cmap, vmin=low, vmax=high, aspect="auto")
        axis.set_xticks(range(3), [h.title() for h in HABITATS], fontsize=10)
        axis.set_yticks(range(4), ["Uniform specialist", "Clustered specialist", "Sparse specialist", "Generalist"], fontsize=9)
        axis.tick_params(axis="y", labelleft=axis is raw_axis)
        axis.set_xlabel("Unseen test habitat", fontsize=10)
        axis.set_title(title, fontsize=11, pad=10)
        for row in range(4):
            for column in range(3):
                rgba = shown.cmap(shown.norm(data[row, column]))
                luminance = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
                value = f"{data[row, column]:+.1f}" if axis is relative_axis else f"{data[row, column]:.1f}"
                axis.text(column, row, value, ha="center", va="center", fontsize=11,
                          color="white" if luminance < 0.5 else "#172b3a")
                if row == column:
                    axis.add_patch(Rectangle((column - 0.48, row - 0.48), 0.96, 0.96,
                                             fill=False, linewidth=2, edgecolor="#e6b445"))
        figure.colorbar(shown, ax=axis, fraction=0.04, pad=0.025).ax.tick_params(labelsize=8)
    effect_axes, limits = [], [0.0]
    for column, habitat in enumerate(HABITATS):
        axis = figure.add_subplot(grid[1, column * 2:column * 2 + 2])
        effect_axes.append(axis)
        data = analysis["habitats"][habitat]
        values = data["seed_values"]
        ticks = []
        others = ["generalist", *[h for h in HABITATS if h != habitat]]
        for position, other in enumerate(others):
            effect = data["home_contrasts"][other]["mean_fitness"]
            raw = np.asarray(values[habitat]["mean_fitness"]) - values[other]["mean_fitness"]
            draw_effect(axis, effect, raw, position, ("#13856b", "#7a58a0", "#c28a1a")[position])
            limits.extend([*raw, *effect["difference_ci95"]])
            ticks.append(f"Home − {other.title()}\np={effect['holm_adjusted_p']:.4g}; {effect['conclusion']}")
        axis.set_yticks(range(3), ticks, fontsize=8)
        axis.set_ylim(2.5, -0.5)
        axis.axvline(0, color="#8b9aa7", linestyle="--", linewidth=1)
        axis.set_title(f"{habitat.title()}: home specialist advantage", fontsize=10)
        axis.set_xlabel("Fitness difference within the same test habitat", fontsize=9)
        axis.grid(axis="x", color="#dce5ec", linewidth=0.8)
        axis.set_facecolor("white")
        axis.set_axisbelow(True)
        axis.tick_params(colors="#526575", labelsize=8)
        for spine in axis.spines.values():
            spine.set_color("#d3dee6")
    low, high = min(limits), max(limits)
    pad = max(1.0, (high - low) * 0.06)
    for axis in effect_axes:
        axis.set_xlim(low - pad, high + pad)
    figure.text(0.075, 0.125, "Gold borders mark matching training/test habitats; they do not mark significant wins. Raw fitness differs with task difficulty.",
                fontsize=9, color="#526575")
    figure.text(0.075, 0.085, "Points: independent seed-group differences. Intervals: pointwise 95% paired bootstrap. Holm correction covers all nine primary tests.",
                fontsize=9, color="#526575")
    figure.text(0.075, 0.045, "Reciprocal specialization requires both specialists winning at home. Generalist results are conditional on the balanced cycling curriculum.",
                fontsize=9, color="#526575")
    return figure


def save_specialization_plot(report, output):
    output = Path(output)
    if output.suffix.lower() not in (".png", ".svg", ".pdf"):
        raise ValueError("Use PNG, SVG, or PDF.")
    figure = build_specialization_figure(report)
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
        save_specialization_plot(json.loads(args.report.read_text()), args.output or args.report.with_suffix(".png"))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
