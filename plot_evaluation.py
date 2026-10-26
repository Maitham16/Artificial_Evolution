"""Publish Step 27 performance, paired effects, and mechanistic diagnostics."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / ".cache/matplotlib"))

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np

from experiment_evaluation import BASELINES, ENVIRONMENTS, METRICS, analyze_results
from plot_traits import export, style


COLORS = {"random": "#738496", "greedy": "#c28a1a", "evolved": "#13856b", "neutral": "#9262b5", "founder": "#3779ba"}
NAMES = {"random": "Random", "greedy": "Greedy", "evolved": "Evolved", "neutral": "Neutral", "founder": "Founder"}
TITLES = {"uniform": "Uniform", "clustered": "Clustered", "sparse": "Sparse", "wide_clustered": "Wide clustered", "barren": "Barren"}
LABELS = {"mean_fitness": "Fitness (seconds + 10 × meals)", "mean_food_eaten": "Meals per creature", "survival_rate": "Survival to 60 seconds"}


def setup(title, subtitle, *, size=(17, 11)):
    figure = Figure(figsize=size, facecolor="#f8fafc")
    FigureCanvasAgg(figure)
    figure.suptitle(title, fontsize=23, fontweight="bold", color="#173344", y=.97)
    figure.text(.5, .923, subtitle, ha="center", fontsize=11, color="#536876")
    return figure


def build_performance_figure(analysis):
    figure = setup("When does evolution outperform simple steering?",
                   f"{analysis['independent_seed_pairs']} independent archived training pairs · fresh matched test worlds · fixed speed and energy costs")
    axes = figure.subplots(3, 5)
    figure.subplots_adjust(left=.065, right=.98, top=.85, bottom=.14, wspace=.33, hspace=.43)
    for col, env in enumerate(ENVIRONMENTS):
        data = analysis["environments"][env]
        for row, metric in enumerate(METRICS):
            axis = axes[row, col]
            for x, condition in enumerate((*BASELINES, "founder")):
                values = data["seed_values"][condition][metric]
                axis.scatter([x] * len(values), values, s=9, alpha=.25, color=COLORS[condition])
                estimate = data["estimates"][condition][metric]
                mean, (low, high) = estimate["mean"], estimate["ci95"]
                axis.plot([x, x], [low, high], color=COLORS[condition], lw=2.5)
                axis.scatter(x, mean, s=35, color=COLORS[condition], marker="D", edgecolors="white", linewidths=.5)
            axis.set_xticks(range(5), [NAMES[c] for c in (*BASELINES, "founder")], rotation=40, ha="right", fontsize=8)
            if row == 0:
                axis.set_title(TITLES[env], fontsize=13)
            if col == 0:
                axis.set_ylabel(LABELS[metric], fontsize=10)
            axis.set_ylim(bottom=-.015 if metric == "survival_rate" else 0)
            if metric == "survival_rate":
                axis.set_ylim(-.015, 1.015)
    style(axes.flat)
    figure.text(.06, .072, "Faint points: seed means, averaging two test worlds. Diamonds and bars: mean and pointwise 95% seed-bootstrap interval.", fontsize=10, color="#536876")
    figure.text(.06, .035, "Neutral = inherited neural weights with random parents and matched mutation. Founder = original unselected brains. All scheduled cohorts are retained.", fontsize=10, color="#536876")
    return figure


def build_effects_figure(analysis):
    figure = setup("Paired effects of evolved control",
                   "Evolved minus each baseline · 45 primary exact sign tests, jointly Holm corrected · pointwise 95% paired bootstrap intervals")
    axes = figure.subplots(3, 5)
    figure.subplots_adjust(left=.09, right=.98, top=.85, bottom=.14, wspace=.45, hspace=.48)
    for row, metric in enumerate(METRICS):
        limits = [0.]
        for col, env in enumerate(ENVIRONMENTS):
            axis = axes[row, col]
            data = analysis["environments"][env]
            labels = []
            for y, control in enumerate(("random", "greedy", "neutral")):
                effect = data["comparisons"][f"evolved_minus_{control}"][metric]
                delta = np.array(data["seed_values"]["evolved"][metric]) - data["seed_values"][control][metric]
                low, high = effect["difference_ci95"]
                axis.scatter(delta, [y] * len(delta), color=COLORS[control], s=10, alpha=.25)
                axis.plot([low, high], [y, y], color=COLORS[control], linewidth=2.5)
                axis.scatter(effect["mean_difference"], y, color=COLORS[control], marker="D", s=35)
                labels.append(f"{NAMES[control]}\np={effect['holm_adjusted_p']:.3g}")
                limits.extend([low, high, *delta])
            axis.set_yticks(range(3), labels, fontsize=8)
            axis.set_ylim(2.55, -.55)
            axis.axvline(0, color="#536876", linestyle="--", linewidth=.8)
            axis.set_xlabel(LABELS[metric], fontsize=9)
            if row == 0:
                axis.set_title(TITLES[env], fontsize=13)
        low, high = min(limits), max(limits)
        padding = max((high - low) * .06, .005)
        for axis in axes[row]:
            axis.set_xlim(low - padding, high + padding)
    style(axes.flat)
    figure.text(.06, .072, "Positive favors evolution. Sign tests assess paired win/loss probability; the intervals estimate mean differences. These are different estimands.", fontsize=10, color="#536876")
    figure.text(.06, .035, "A reported advantage requires adjusted p < .05 and a mean interval above zero. Inconclusive results do not establish equivalence.", fontsize=10, color="#536876")
    return figure


def build_mechanisms_figure(analysis):
    figure = setup("Adaptation, sensory dependence, and genetic change",
                   "Diagnostic evidence · existing Step 18 training histories plus fresh matched frozen-controller tests", size=(16, 11))
    axes = figure.subplots(2, 3)
    figure.subplots_adjust(left=.08, right=.98, top=.85, bottom=.16, wspace=.35, hspace=.55)
    generations = range(1, 11)
    for col, (key, title) in enumerate((("mean_fitness", "Training fitness"), ("steering_rms", "Steering-genome RMS distance"),
                                        ("effective_founder_families", "Effective founder families"))):
        axis = axes[0, col]
        for arm, condition in (("selection", "evolved"), ("random_parent", "neutral")):
            rows = analysis["training_curves"][arm][key]
            axis.plot(generations, [r["mean"] for r in rows], color=COLORS[condition], label=NAMES[condition])
            axis.fill_between(generations, [r["ci95"][0] for r in rows], [r["ci95"][1] for r in rows], color=COLORS[condition], alpha=.15)
        axis.set(title=title, xlabel="Scored training generation", xticks=list(generations))
        axis.legend(fontsize=9, frameon=False)
    axis = axes[1, 0]
    for offset, condition in ((-.1, "evolved"), (.1, "neutral")):
        for i, env in enumerate(ENVIRONMENTS):
            row = analysis["environments"][env]["adaptation_from_founders"][condition]["mean_fitness"]
            axis.plot([i + offset] * 2, row["difference_ci95"], color=COLORS[condition], linewidth=2)
            axis.scatter(i + offset, row["mean_difference"], color=COLORS[condition], s=25)
    axis.axhline(0, color="#536876", linestyle="--", linewidth=.8)
    axis.set(title="Held-out fitness gain over founders", ylabel="Fitness difference", xticks=range(5))
    axis.set_xticklabels([TITLES[e] for e in ENVIRONMENTS], rotation=30, ha="right")
    axis = axes[1, 1]
    food_envs = [e for e in ENVIRONMENTS if e != "barren"]
    for i, env in enumerate(food_envs):
        row = analysis["environments"][env]["food_sensor_intervention"]["mean_fitness"]
        for offset, name, color in ((-.1, "evolved_sensor_loss", COLORS["evolved"]), (.1, "selection_minus_neutral_sensor_loss", COLORS["neutral"])):
            result = row[name]
            axis.plot([i + offset] * 2, result["difference_ci95"], color=color, linewidth=2)
            axis.scatter(i + offset, result["mean_difference"], color=color, s=25)
    axis.axhline(0, color="#536876", linestyle="--", linewidth=.8)
    axis.set(title="Food-input intervention: fitness loss", ylabel="Intact minus hidden; interaction", xticks=range(4))
    axis.set_xticklabels([TITLES[e] for e in food_envs], rotation=30, ha="right")
    axis = axes[1, 2]
    for condition in BASELINES:
        rows = [analysis["environments"][e]["estimates"][condition]["starvation_rate"] for e in ENVIRONMENTS]
        axis.plot(range(5), [r["mean"] for r in rows], color=COLORS[condition], marker="o", label=NAMES[condition])
    axis.set(title="Failure: fraction dying from starvation", ylim=(-.02, 1.02), xticks=range(5))
    axis.set_xticklabels([TITLES[e] for e in ENVIRONMENTS], rotation=30, ha="right")
    axis.legend(fontsize=8, frameon=False)
    style(axes.flat)
    figure.text(.065, .075, "Bottom middle: green = evolved sensor loss; purple = evolved loss minus neutral loss. Bars and training bands are pointwise 95% seed bootstrap.", fontsize=10, color="#536876")
    figure.text(.065, .038, "Genetic distance is not functional intelligence; hidden inputs can cause distribution shift. Diagnostics are exploratory, with 21 tests corrected separately.", fontsize=10, color="#536876")
    return figure


def save_plots(report, output, effects_output=None, mechanisms_output=None):
    if report.get("status") != "complete":
        raise ValueError("Plot only a complete evaluation.")
    analysis = analyze_results(report)
    if analysis != report["analysis"]:
        raise ValueError("Stored analysis differs from recomputation.")
    export(build_performance_figure(analysis), output)
    if effects_output:
        export(build_effects_figure(analysis), effects_output)
    if mechanisms_output:
        export(build_mechanisms_figure(analysis), mechanisms_output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--effects-output", type=Path)
    parser.add_argument("--mechanisms-output", type=Path)
    args = parser.parse_args()
    try:
        save_plots(json.loads(args.report.read_text()), args.output, args.effects_output, args.mechanisms_output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
