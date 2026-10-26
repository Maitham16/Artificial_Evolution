"""Scientific overview and self-contained playback of recorded neural decisions."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parent / '.cache/matplotlib'))
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np

from inspect_brains import BANKS, BEARINGS, ENVIRONMENTS, TRACE_COLUMNS, TRACE_IDS, analyze_results, load_trace, source_banks
from brain import SENSOR_NAMES
from experiment_strategy import file_digest

COLORS = {'evolved': '#087f8c', 'unselected': '#b76b27'}


def focus_recording(report):
    if report.get('status') != 'complete':
        raise ValueError('Visualize only a complete study.')
    analysis = analyze_results(report)
    seed = report['protocol']['focus_seed']
    if seed != report['protocol']['seeds'][0] or report['protocol']['focus_creature_id'] != 1:
        raise ValueError('Focus must be the first declared seed and ID 1, not a test winner.')
    trial = next(t for t in report['trials'] if t['seed'] == seed)
    if file_digest(trial['trace_file']) != trial['trace_sha256']:
        raise ValueError('Trace hash mismatch.')
    metadata, arrays = load_trace(trial['trace_file'])
    if metadata['seed'] != seed or metadata['sources'] != trial['sources']:
        raise ValueError('Recording provenance differs from the report.')
    return analysis, trial, arrays


def build_brain_figure(report):
    analysis, trial, arrays = focus_recording(report)
    figure = Figure(figsize=(17, 11), facecolor='#f8fafc')
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 3)
    figure.subplots_adjust(left=.075, right=.97, top=.84, bottom=.16, wspace=.38, hspace=.60)
    figure.suptitle('Inside evolved controllers', fontsize=23, fontweight='bold', y=.97, color='#183241')
    figure.text(.5, .925, f"{analysis['independent_seed_groups']} saved training seeds · all 100 brains per cohort · new matched uniform and clustered worlds", ha='center', fontsize=12, color='#536876')
    figure.text(.5, .887, 'Exploratory mechanism diagnostics. Local command effects do not establish fitness effects.', ha='center', fontsize=11, color='#536876')
    axis = axes[0, 0]
    for bank in BANKS:
        axis.plot(BEARINGS * 180, analysis['common_probes']['turn_curves'][bank], color=COLORS[bank], label=bank.title(), linewidth=2)
    axis.axhline(0, color='#bbc8d0', linewidth=.8)
    axis.axvline(0, color='#bbc8d0', linewidth=.8)
    axis.set(title='Turn response to food bearing', xlabel='Food bearing (degrees; positive = right)', ylabel='Mean signed turn command')
    axis.legend(frameon=False, fontsize=9)
    for column, metric, labels, title, xlabel in (
        (1, 'mean_abs_input_jacobian', ['Food near', 'Bearing', 'Visible', 'Hunger', 'Wall F', 'Wall R', 'Wall B', 'Wall L'], 'Local sensitivity on common probe states', 'Mean |∂turn / ∂encoded input|'),
        (2, 'mean_abs_intervention_effect', ['Hide food', 'Mirror bearing', 'Hunger → 0.5', 'Walls → open'], 'Finite changes on observed uniform states', 'Mean absolute change in turn command'),
    ):
        axis = axes[0, column]
        for offset, bank in zip((-.18, .18), BANKS):
            data = analysis['common_probes'] if column == 1 else analysis['environments']['uniform']
            axis.barh(np.arange(len(labels)) + offset, data[metric][bank], height=.32, color=COLORS[bank])
        axis.set_yticks(range(len(labels)), labels, fontsize=9)
        axis.invert_yaxis()
        axis.set(title=title, xlabel=xlabel)
    for column, environment in enumerate(ENVIRONMENTS):
        axis = axes[1, column]
        food = arrays[f'{environment}_evolved_initial_food']
        axis.scatter(food[:, 0], food[:, 1], s=5, color='#cad4db', label='Initial food', zorder=1)
        for bank in BANKS:
            frames = arrays[f'{environment}_{bank}_1']
            meals = arrays[f'{environment}_{bank}_1_meals']
            axis.plot(frames[:, 1], frames[:, 2], color=COLORS[bank], linewidth=1.2, label=bank.title())
            axis.scatter(frames[0, 1], frames[0, 2], color=COLORS[bank], marker='s', s=28)
            if len(meals):
                axis.scatter(meals[:, 1], meals[:, 2], facecolors='none', edgecolors=COLORS[bank], s=18)
        axis.set(xlim=(0, 1000), ylim=(600, 0), xlabel='x (pixels)', ylabel='y (pixels)', title=f"{environment.title()} trajectories: seed {trial['seed']}, ID 1")
        axis.set_aspect('equal', adjustable='box')
        axis.legend(fontsize=8, frameon=False, loc='upper right')
    frames = arrays['clustered_evolved_1']
    axis = axes[1, 2]
    image = axis.imshow(frames[:, 16:24].T, cmap='RdBu', vmin=-1, vmax=1, aspect='auto', extent=(0, max(.2, frames[-1, 0]), 8.5, .5), interpolation='nearest')
    axis.set_yticks(range(1, 9), [f'h{i}' for i in range(8)])
    axis.set(title=f"Hidden activations: evolved seed {trial['seed']}, ID 1", xlabel='Recorded decision time (seconds)', ylabel='Network-specific hidden unit')
    figure.colorbar(image, ax=axis, fraction=.04, pad=.025).ax.tick_params(labelsize=8)
    for axis in axes.flat:
        axis.set_facecolor('white')
        axis.title.set_fontsize(10)
        for spine in axis.spines.values():
            spine.set_color('#d4dfe5')
        axis.tick_params(labelsize=8, colors='#536876')
    figure.text(.075, .095, 'Common probes: visible food, 37 bearings × 3 proximities × 2 hunger levels, open walls. Each brain and seed has equal weight.', fontsize=10, color='#536876')
    figure.text(.075, .060, 'Examples fixed before outcomes. Squares: starts; rings: meals; grey dots: initial food only (pellets replenish).', fontsize=10, color='#536876')
    figure.text(.075, .025, 'Throttle is ignored at fixed speed. Partial derivatives are per encoded unit; clamp sizes differ. Neuron activity is not a semantic label.', fontsize=10, color='#536876')
    return figure


def save_brain_plot(report, path):
    path = Path(path)
    if path.suffix.lower() not in ('.png', '.svg', '.pdf'):
        raise ValueError('Use PNG, SVG, or PDF.')
    figure = build_brain_figure(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        figure.savefig(path, dpi=160, facecolor=figure.get_facecolor())
    finally:
        figure.clear()


def save_brain_viewer(report, path):
    _, trial, arrays = focus_recording(report)
    sources = trial['sources']
    banks, metadata = source_banks(trial['seed'], Path(sources['evolved']['file']).parent, Path(sources['unselected']['file']).parent)
    if metadata != sources:
        raise ValueError('Source hashes changed since recording.')
    payload = {'seed': trial['seed'], 'columns': TRACE_COLUMNS, 'sensors': SENSOR_NAMES, 'conditions': {}}
    for environment in ENVIRONMENTS:
        for bank in BANKS:
            for key in TRACE_IDS:
                label = f'{environment} / {bank} / ID {key}'
                payload['conditions'][label] = {
                    'frames': arrays[f'{environment}_{bank}_{key}'].tolist(),
                    'meals': arrays[f'{environment}_{bank}_{key}_meals'].tolist(),
                    'initialFood': arrays[f'{environment}_{bank}_initial_food'].tolist(),
                    'weights': [p.tolist() for p in banks[bank][key].parameters],
                    'final': next(r for t in trial['tests'] if t['environment'] == environment for r in t['conditions'][bank]['brains'] if r['creature_id'] == key),
                }
    template = Path(__file__).with_name('brain_viewer.html').read_text()
    encoded = json.dumps(payload, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    if template.count('/*BRAIN_DATA*/null') != 1:
        raise ValueError('Invalid viewer template.')
    output = template.replace('/*BRAIN_DATA*/null', encoded)
    path = Path(path)
    if path.suffix.lower() != '.html':
        raise ValueError('Use an HTML viewer path.')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--plot', type=Path, required=True)
    parser.add_argument('--viewer', type=Path, required=True)
    args = parser.parse_args()
    if args.plot.resolve() == args.report.resolve() or args.viewer.resolve() == args.report.resolve():
        parser.error('Preserve the report; choose separate visualization paths.')
    try:
        report = json.loads(args.report.read_text())
        save_brain_plot(report, args.plot)
        save_brain_viewer(report, args.viewer)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
