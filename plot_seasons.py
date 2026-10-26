"""Season-aware observations, true lineage retention, and frozen diagnostic effects."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parent / '.cache/matplotlib'))
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np

from experiment_seasons import analyze_results
from seasons import SEASON_NAMES


SEASON_COLORS = ('#bce3cc', '#ffe2a7', '#edc2a5', '#bfd5ea')


def finish_figure(figure, path):
    path = Path(path)
    if path.suffix.lower() not in ('.png', '.svg', '.pdf'):
        raise ValueError('Use a PNG, SVG, or PDF destination.')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        figure.savefig(path, dpi=160, facecolor=figure.get_facecolor())
    finally:
        figure.clear()


def style(axes):
    for axis in axes:
        axis.set_facecolor('white')
        axis.grid(axis='y', color='#e1e8ee', linewidth=.7)
        axis.set_axisbelow(True)
        axis.tick_params(labelsize=9, colors='#536876')
        axis.title.set_fontsize(11)
        for spine in axis.spines.values():
            spine.set_color('#cddae3')


def shade_seasons(axis, rows):
    for row in rows:
        g = row['generation']
        axis.axvspan(g - .5, g + .5, facecolor=SEASON_COLORS[row['season_index']], alpha=.5, zorder=0)
    axis.set_xlim(.5, rows[-1]['generation'] + .5)
    axis.set_xticks([r['generation'] for r in rows])


def build_study_figure(report):
    if report.get('status') != 'complete':
        raise ValueError('Visualize only a complete seasonal study.')
    a = analyze_results(report)
    rows = a['by_generation']
    generations = [r['generation'] for r in rows]
    n = a['independent_seed_groups']
    figure = Figure(figsize=(15, 11), facecolor='#f8fafc')
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 2)
    figure.subplots_adjust(left=.085, right=.965, bottom=.18, top=.82, wspace=.28, hspace=.5)
    figure.suptitle('Evolution through changing seasons', fontsize=22, fontweight='bold', y=.97, color='#173344')
    figure.text(.5, .924, f"{n} independent founder seeds · {a['actual_training_cohorts']} realized seasonal cohorts · {a['extinct_lineages']} extinct by the horizon",
                ha='center', fontsize=12, color='#536876')
    figure.text(.5, .878, 'Spring 150 · Summer 200 · Autumn 75 · Winter 25 maintained pellets; clusters move each generation.', ha='center', fontsize=11, color='#536876')
    axis = axes[0, 0]
    axis.plot(generations, [r['food_count'] for r in rows], color='#477551', marker='s', linewidth=2)
    axis.set(title='Declared seasonal food availability', xlabel='Generation', ylabel='Maintained pellets')
    shade_seasons(axis, rows)
    axis = axes[0, 1]
    axis.step([0, *generations], [n, *[r['lineages_eligible_to_continue'] for r in rows]], where='post', color='#b44355', linewidth=2)
    axis.set(title='Lineages able to produce a next cohort', xlabel='After generation', ylabel='Lineages (original seed denominator)', ylim=(-.1, n + .5), xlim=(0, generations[-1]))
    axis.set_xticks([0, *generations])
    axis = axes[1, 0]
    for trial in report['trials']:
        data = trial['training']['generations']
        axis.plot([r['generation'] for r in data], [r['mean_fitness'] for r in data], color='#839ca8', alpha=.5, linewidth=1)
    means = [np.nan if r['mean_fitness_among_reached'] is None else r['mean_fitness_among_reached'] for r in rows]
    axis.plot(generations, means, color='#087f8c', linewidth=2.5, marker='o', label='Mean of reached cohorts')
    for r in rows:
        if r['mean_fitness_among_reached'] is not None:
            axis.annotate(f"n={r['cohorts_reached']}", (r['generation'], r['mean_fitness_among_reached']), xytext=(0, 8), textcoords='offset points', ha='center', fontsize=8)
    axis.set(title='Raw training fitness changes with both habitat and ancestry', xlabel='Generation (no imputed post-extinction cohorts)', ylabel='Fitness among cohorts reached')
    shade_seasons(axis, rows)
    axis.legend(frameon=False, fontsize=8)
    axis = axes[1, 1]
    for index, (name, result) in enumerate(a['diagnostics'].items()):
        value = result['mean_fitness'];low, high = value['difference_ci95'];mean = value['mean_difference']
        axis.errorbar(mean, index, xerr=[[mean - low], [high - mean]], fmt='D', color=('#087f8c', '#b46c2c')[index], capsize=5, linewidth=2)
        axis.text(.98, .78 - index * .48, f"Δ {mean:+.1f}; 95% [{low:+.1f}, {high:+.1f}]", transform=axis.transAxes, ha='right', fontsize=9, color='#536876')
    axis.axvline(0, color='#98aab6', linestyle='--', linewidth=1)
    axis.set_yticks([0, 1], ['Standard: 150 food', 'Scarce: 25 food'])
    axis.set_ylim(1.6, -.6)
    axis.set(title='Fresh matched archive tests: last birth cohort − founders', xlabel='Mean fitness difference; paired pointwise 95% interval')
    style(axes.flat)
    figure.text(.075, .115, 'Raw seasonal trends cannot isolate adaptation: food, locations, ancestry, and which lineages remain all change.', fontsize=10, color='#536876')
    figure.text(.075, .075, 'Archive diagnostics include every source seed, even extinct lineages. They do not revive populations or demonstrate persistence.', fontsize=10, color='#536876')
    figure.text(.075, .035, 'Extinction: no individual reaches reproductive age 60 s. Fixed 100 births per viable generation; no claim of natural population dynamics.', fontsize=10, color='#536876')
    return figure


def save_season_plot(report, path):
    finish_figure(build_study_figure(report), path)


def save_cluster_paths(report, path):
    if report.get('status') != 'complete':
        raise ValueError('Visualize only a complete seasonal study.')
    analyze_results(report)
    trial = next(t for t in report['trials'] if t['seed'] == report['protocol']['seeds'][0])
    history = trial['training']['seasonal_environment']['history']
    centers = np.array([r['cluster_centers'] for r in history])
    figure = Figure(figsize=(11, 7), facecolor='#f8fafc')
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    figure.subplots_adjust(left=.09, right=.96, top=.84, bottom=.17)
    for cluster, color in enumerate(('#087f8c', '#be7a25', '#815ba4', '#b44355')):
        axis.plot(centers[:, cluster, 0], centers[:, cluster, 1], color=color, marker='o', label=f'Cluster {cluster + 1}')
        for g, (x, y) in enumerate(centers[:, cluster], 1):
            axis.annotate(str(g), (x, y), xytext=(5, 5), textcoords='offset points', fontsize=9, color=color)
    axis.set(xlim=(0, 1000), ylim=(600, 0), xlabel='x (pixels)', ylabel='y (pixels)',
             title=f"Realized cluster-center paths · predetermined seed {trial['seed']}")
    axis.set_aspect('equal', adjustable='box')
    axis.legend(frameon=False, fontsize=9, loc='upper right')
    style([axis])
    figure.text(.09, .09, 'Numbers identify generation starts. Centers move at most 120 pixels after bounded reflection; food spread stays 55 pixels.', fontsize=9, color='#536876')
    figure.text(.09, .04, 'Only cohorts actually reached are shown. This is the first declared seed, not a selected survivor or a best-performing example.', fontsize=9, color='#536876')
    finish_figure(figure, path)


def save_lineage_plot(report, path):
    history = [r for r in report['seasonal_environment']['history'] if r['complete']]
    if not history:
        raise ValueError('Complete a seasonal cohort before plotting.')
    rows = report['generations']
    figure = Figure(figsize=(12, 7), facecolor='#f8fafc')
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 2)
    figure.subplots_adjust(left=.09, right=.96, bottom=.17, top=.84, wspace=.28, hspace=.55)
    status = 'lineage extinct' if report['seasonal_environment']['lineage_extinct'] else 'observation stopped'
    figure.suptitle(f"Seasonal lineage · seed {report['seed']} · {status}", fontsize=17)
    g = [r['generation'] for r in rows]
    series = (([r['food_count'] for r in history], 'Food availability', 'Maintained pellets'),
              ([r['mean_fitness'] for r in rows], 'Raw fitness (habitat and ancestry both vary)', 'Mean fitness'),
              ([r['eligible_parent_count'] for r in history], 'Individuals reaching reproductive age', 'Eligible parents'),
              ([r['mean_food_eaten'] for r in rows], 'Food consumption', 'Meals per creature'))
    for axis, (values, title, ylabel) in zip(axes.flat, series):
        shade_seasons(axis, history)
        axis.plot(g, values, marker='o', color='#087f8c')
        axis.set(title=title, xlabel='Generation', ylabel=ylabel)
    style(axes.flat)
    figure.text(.07, .08, 'Seasons change between generations; all cohorts eventually die. Zero eligible parents ends the lineage.', fontsize=10, color='#536876')
    figure.text(.07, .035, 'Raw fitness is descriptive and does not isolate adaptation from environmental difficulty or survivor selection.', fontsize=10, color='#536876')
    finish_figure(figure, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--clusters-output', type=Path, help='also plot realized cluster paths for the first declared seed')
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text())
        if 'seasonal_environment' in report:
            save_lineage_plot(report, args.output)
        else:
            save_season_plot(report, args.output)
            if args.clusters_output:
                save_cluster_paths(report, args.clusters_output)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
