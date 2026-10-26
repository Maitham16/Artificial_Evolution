"""Heritable body trends, frozen component tests, and analytical energy trade-offs."""

import argparse
import copy
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parent / '.cache/matplotlib'))
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle
import numpy as np

from body_traits import BodyTraits, TraitWorld, shared_layout_digest
from experiment_traits import analyze_results, load_models, test_bank, validate_cohorts
from experiment_strategy import file_digest


COLOR = '#087f8c'


def export(figure, path):
    path = Path(path)
    if path.suffix.lower() not in ('.png', '.svg', '.pdf'):
        raise ValueError('Use PNG, SVG, or PDF.')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        figure.savefig(path, dpi=160, facecolor=figure.get_facecolor())
    finally:
        figure.clear()


def style(axes):
    for axis in axes:
        axis.set_facecolor('white')
        axis.tick_params(labelsize=8, colors='#536876')
        axis.title.set_fontsize(11)
        axis.grid(axis='y', color='#e1e8ee', linewidth=.7)
        axis.set_axisbelow(True)
        for spine in axis.spines.values():
            spine.set_color('#cddae3')


def draw_effect(axis, row, position, color):
    low, high = row['difference_ci95']
    axis.hlines(position, low, high, color=color, linewidth=3)
    axis.vlines([low, high], position - .05, position + .05, color=color)
    axis.scatter(row['mean_difference'], position, color=color, marker='D', s=45)


def build_trait_figure(report):
    if report.get('status') != 'complete':
        raise ValueError('Visualize only a complete joint-evolution study.')
    a = analyze_results(report)
    figure = Figure(figsize=(16, 11), facecolor='#f8fafc')
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 3)
    figure.subplots_adjust(left=.11, right=.96, top=.82, bottom=.17, wspace=.38, hspace=.65)
    figure.suptitle('Evolving brains and bodies together', fontsize=23, fontweight='bold', y=.97, color='#173344')
    figure.text(.5, .925, f"{a['independent_seed_groups']} independent seeds · linked brain/body inheritance · all 100 individuals per birth cohort", ha='center', fontsize=12, color='#536876')
    figure.text(.5, .88, 'Cruise speed, radius, and perception have explicit costs. Frozen factorial tests separate brain and body components.', ha='center', fontsize=11, color='#536876')
    trends = a['birth_trait_means_by_generation']
    g = [r['generation'] for r in trends]
    values = np.array([r['seed_values'] for r in trends])
    labels = [('Cruise speed', 'Pixels per second', 60.), ('Body radius', 'Pixels', 8.), ('Sensory range', 'Pixels', 160.)]
    for index, (title, ylabel, reference) in enumerate(labels):
        axis = axes[0, index]
        for seed in range(values.shape[1]):
            axis.plot(g, values[:, seed, index], color='#9aadb8', alpha=.6, linewidth=1)
        axis.plot(g, values[:, :, index].mean(axis=1), color=COLOR, linewidth=2.5, marker='o')
        axis.axhline(reference, color='#ba7a2c', linestyle='--', linewidth=1)
        axis.set(title=title, ylabel=ylabel, xlabel='Generation (complete birth cohort means)')
        axis.set_xticks(g)
    for column, control, title in ((0, 'founder', 'Joint evolved genome − complete founders'),
                                   (1, 'brain_only', 'Body contribution with evolved brains held fixed')):
        axis = axes[1, column]
        ticks = []
        for position, (environment, data) in enumerate(a['environments'].items()):
            row = data['primary_fitness'][control]
            draw_effect(axis, row, position, (COLOR, '#b97b2d')[position])
            ticks.append(f"{environment.title()}\np={row['holm_adjusted_p']:.4g}; {row['conclusion']}")
        axis.axvline(0, color='#98aab6', linestyle='--')
        axis.set_yticks([0, 1], ticks, fontsize=8)
        axis.set(title=title, xlabel='Fitness difference; paired pointwise 95% interval', ylim=(1.5, -.5))
    axis = axes[1, 2]
    for position, (environment, data) in enumerate(a['environments'].items()):
        draw_effect(axis, data['descriptive_brain_body_interaction'], position, (COLOR, '#b97b2d')[position])
    axis.axvline(0, color='#98aab6', linestyle='--')
    axis.set_yticks([0, 1], ['Standard', 'Scarce'])
    axis.set(title='Brain × body interaction (descriptive)', xlabel='(Joint − brain only) − (body only − founders)', ylim=(1.5, -.5))
    style(axes.flat)
    figure.text(.07, .11, 'Grey lines: source-seed means; teal: equal-seed mean; dashed: founding reference. Trait trends do not establish selection over drift.', fontsize=10, color='#536876')
    figure.text(.07, .07, 'Four primary fitness tests use Holm correction. The interaction has a pointwise interval and no confirmatory p-value.', fontsize=10, color='#536876')
    figure.text(.07, .03, '“Brain only” is the evolved brain in a reference body, not an independently trained population. Costs are a declared 2D model, not calibrated biology.', fontsize=10, color='#536876')
    return figure


def save_trait_plot(report, path):
    export(build_trait_figure(report), path)


def save_cost_plot(path):
    figure = Figure(figsize=(15, 6.5), facecolor='#f8fafc')
    FigureCanvasAgg(figure)
    axes = figure.subplots(1, 3)
    figure.subplots_adjust(left=.065, right=.94, top=.77, bottom=.25, wspace=.5)
    figure.suptitle('The declared energetic trade-offs', fontsize=22, fontweight='bold', y=.96)
    figure.text(.5, .88, 'Analytical model curves: vary one trait, keep the other two at speed 60, radius 8, range 160.', ha='center', fontsize=11, color='#536876')
    for index, (grid, label) in enumerate(((np.linspace(25, 100, 76), 'Cruise speed (pixels/s)'),
                                          (np.arange(4, 13), 'Radius (pixels)'),
                                          (np.linspace(60, 280, 76), 'Sensory range (pixels)'))):
        bodies = []
        for value in grid:
            values = [60., 8, 160.]
            values[index] = int(value) if index == 1 else float(value)
            bodies.append(BodyTraits(*values))
        powers = np.array([b.powers() for b in bodies])
        axis = axes[index]
        axis.stackplot(grid, powers.T, colors=['#c6d8e5', '#80b6bb', '#dfb56d'], labels=['Basal', 'Movement', 'Sensing'], alpha=.9)
        axis.plot(grid, powers.sum(axis=1), color=COLOR, linewidth=2)
        axis.set(xlabel=label, ylabel='Energy per living second', title=('Faster cruise: quadratic movement cost', 'Larger body: storage, reach, and upkeep', 'Longer sensing: quadratic area cost')[index])
        other = axis.twinx()
        other.plot(grid, [b.initial_energy / sum(b.powers()) for b in bodies], color='#b44355', linestyle='--', linewidth=2)
        other.set_ylabel('No-food energy endurance (seconds)', color='#b44355', fontsize=9)
        other.tick_params(labelsize=8, colors='#b44355')
        other.spines['top'].set_visible(False)
        if index == 0: axis.legend(frameon=False, fontsize=8, loc='upper left')
    style(axes)
    figure.text(.06, .14, 'Filled areas: basal / movement / sensing power. Red dashed line: initial usable energy divided by total power, with no meals.', fontsize=10, color='#536876')
    figure.text(.06, .08, 'Capacity = 100 × (radius/8)²; development costs 10 × (radius/8)² from a common 100-unit birth budget; excess allocation is not stored.', fontsize=10, color='#536876')
    figure.text(.06, .025, 'These are specified mechanical costs, not observed fitness curves or empirical biological scaling laws. Food capture and brain/body coupling determine performance.', fontsize=9, color='#536876')
    export(figure, path)


def save_body_map(report, path):
    if report.get('status') != 'complete':
        raise ValueError('Visualize only a complete joint-evolution study.')
    analyze_results(report)
    trial = next(t for t in report['trials'] if t['seed'] == report['protocol']['seeds'][0])
    if file_digest(trial['model_file']) != trial['model_sha256']:
        raise ValueError('Model checksum changed.')
    _, banks = load_models(trial['model_file'], trial['seed'], report['protocol']['generations'])
    test = next(x for x in trial['tests'] if x['environment'] == 'standard')
    figure = Figure(figsize=(14, 6.5), facecolor='#f8fafc')
    FigureCanvasAgg(figure)
    axes = figure.subplots(1, 2)
    figure.subplots_adjust(left=.06, right=.94, top=.82, bottom=.2, wspace=.15)
    figure.suptitle(f"Matched body phenotypes · predetermined source seed {trial['seed']}", fontsize=19, y=.96)
    for axis, condition, title in zip(axes, ('founder', 'joint'), ('Founding reference bodies', 'Evolved bodies and brains')):
        world = TraitWorld(seed=test['seed'], food_count=150, evolution_enabled=False, genomes=test_bank(banks, condition))
        if shared_layout_digest(world) != test['conditions'][condition]['shared_layout_sha256']:
            raise ValueError('Body-map shared scenario differs from the experiment.')
        axis.scatter([f.x for f in world.food], [f.y for f in world.food], color='#8bb264', s=3, alpha=.5)
        for c in world.creatures:
            color = (c.body.cruise_speed - 25) / 75
            from matplotlib import colormaps
            axis.add_patch(Circle((c.x, c.y), c.radius, facecolor=colormaps['viridis'](color), edgecolor='#263e4a', linewidth=.5))
        selected = world.creatures[0]
        axis.add_patch(Circle((selected.x, selected.y), selected.body.sensory_range, fill=False, linestyle='--', edgecolor=COLOR, linewidth=1))
        axis.set(xlim=(0, 1000), ylim=(600, 0), title=title, xlabel='x (pixels)', ylabel='y (pixels)')
        axis.set_aspect('equal', adjustable='box')
    style(axes)
    figure.text(.06, .12, 'Circle size is actual radius; colour encodes cruise speed on a common 25–100 scale (purple → yellow). Dashed circle: sensory range of ID 1.', fontsize=9, color='#536876')
    figure.text(.06, .06, 'All initial positions, headings, lifespans, and food match; physical traits and energy reserves intentionally differ. This is an initial state, not a trajectory.', fontsize=9, color='#536876')
    export(figure, path)


def save_lineage_plot(report, path):
    report = copy.deepcopy(report)
    report['physical_traits']['history'] = [r for r in report['physical_traits']['history'] if r['complete']]
    validate_cohorts(report, study=False)
    history, rows = report['physical_traits']['history'], report['generations']
    if not rows:
        raise ValueError('Complete a trait cohort before plotting.')
    means = np.array([np.mean(r['birth_bodies'], axis=0) for r in history])
    figure = Figure(figsize=(12, 8), facecolor='#f8fafc')
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 2)
    figure.subplots_adjust(left=.09, right=.96, bottom=.13, top=.85, hspace=.5, wspace=.3)
    figure.suptitle(f"Joint brain/body lineage · seed {report['seed']}", fontsize=18)
    for index, (axis, title) in enumerate(zip(axes.flat, ('Cruise speed', 'Radius', 'Sensory range', 'Fitness'))):
        values = means[:, index] if index < 3 else [r['mean_fitness'] for r in rows]
        axis.plot([r['generation'] for r in rows], values, color=COLOR, marker='o')
        axis.set(title=title, xlabel='Completed generation')
    style(axes.flat)
    figure.text(.08, .04, 'Birth-cohort means include every creature. Trait trends and training fitness alone do not establish optimality or separate selection from drift.', fontsize=10, color='#536876')
    export(figure, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--costs-output', type=Path)
    parser.add_argument('--bodies-output', type=Path)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text())
        if 'physical_traits' in report:
            save_lineage_plot(report, args.output)
        else:
            save_trait_plot(report, args.output)
            if args.bodies_output: save_body_map(report, args.bodies_output)
        if args.costs_output: save_cost_plot(args.costs_output)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
