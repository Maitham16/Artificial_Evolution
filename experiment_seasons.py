"""Track seasonal lineages and test their last archived cohorts against founders."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import json
import math
from pathlib import Path
import random

import numpy as np

from analyze_intelligence import PARAMETER_NAMES, PARAMETER_SHAPES, bank_digest
from brain import NeuralNetwork
from compare_creatures import complete_generation, derived_seed, genome_digest, initial_conditions_digest, positive_integer
from experiment_speed import paired_metrics
from experiment_specialization import bodies_digest
from experiment_strategy import file_digest
from inspect_brains import prior_layouts
from seasons import DEFAULT_FOOD, SEASON_NAMES, SeasonalWorld, moving_centers, season_context
from simulation import EvolutionSimulation
from world import World


DEFAULT_SEEDS = tuple(range(2101, 2109))
MAX_GENERATIONS = 8
BANKS = ('last_cohort', 'founder')
CHALLENGES = {'standard': 150, 'scarce': 25}
CONFIG = {'population_size': 100, 'fixed_speed': 60.0, 'controller': 'neural', 'food_sensor_mode': 'intact',
          'mutation_rate': .1, 'mutation_scale': .1, 'food_distribution': 'clustered', 'arena_size': [1000, 600]}


def validate_lineage(trial, generations):
    training = trial['training']
    rows = training['generations']
    env = training['seasonal_environment']
    history, traces = env['history'], env['transitions']
    count = len(rows)
    if (any(training[k] != v for k, v in CONFIG.items()) or not training['evolution_enabled']
            or training['seed'] != trial['seed'] or not 1 <= count <= generations
            or training['completed_generations'] != count or len(history) != count
            or len(traces) != count - 1 or len(trial['training_starts']) != count
            or len(trial['training_genome_hashes']) != count or len(trial['training_body_hashes']) != count
            or env['food_counts'] != list(DEFAULT_FOOD) or env['season_length_generations'] != 1
            or env['cluster_shift_pixels'] != 120.0 or env['reproductive_age_seconds'] != 60.0
            or trial['last_birth_generation'] != count):
        raise ValueError('Lineage history must match the declared physics, seasons, and realized budget.')
    for index, (stats, context) in enumerate(zip(rows, history), 1):
        expected = season_context(index)
        candidates = context['candidates']
        ranked = sorted(candidates, key=lambda r: (-r['fitness'], r['creature_id']))
        eligible = [r['creature_id'] for r in ranked if r['age'] >= 60]
        selected = eligible[:20]
        if (any(context[k] != v for k, v in expected.items()) or not context['complete']
                or context['cluster_centers'] != [list(p) for p in moving_centers(trial['seed'], index, 1000, 600, 120.0)]
                or len(candidates) != 100 or sorted(r['creature_id'] for r in candidates) != list(range(1, 101))
                or not all(np.isfinite(r['fitness']) and np.isfinite(r['age']) and 0 <= r['age'] <= 120
                           and type(r['food_eaten']) is int and r['food_eaten'] >= 0
                           and np.isclose(r['fitness'], r['age'] + 10 * r['food_eaten']) for r in candidates)
                or context['eligible_parent_count'] != len(eligible) or context['selected_ids'] != selected
                or stats['generation'] != index or stats['population_size'] != 100
                or not np.isclose(stats['mean_speed'], 60) or stats['survivors_at_checkpoint'] != len(eligible)
                or stats['survival_rate'] != len(eligible) / 100
                or not np.isclose(stats['mean_fitness'], np.mean([r['fitness'] for r in ranked]))
                or not np.isclose(stats['mean_food_eaten'], np.mean([r['food_eaten'] for r in ranked]))
                or not np.isclose(stats['mean_survival_seconds'], np.mean([r['age'] for r in ranked]))):
            raise ValueError('Season, maturity eligibility, or complete-cohort scores are inconsistent.')
        if index < count:
            t = traces[index - 1]
            mutation_seed = random.Random(f'mutation:{trial["seed"]}:generation:{index + 1}').getrandbits(128)
            if (not selected or t['parent_ids'] != sorted(selected) or t['from_generation'] != index
                    or t['to_generation'] != index + 1 or t['mutation_seed'] != mutation_seed
                    or t['mutation_rng_calls'] != 801 or len(t['offspring_parent_ids']) != 100
                    or len(t['offspring_mutation_counts']) != 100
                    or set(t['offspring_parent_ids']) != set(selected)
                    or max(t['offspring_parent_ids'].count(k) for k in selected)
                    - min(t['offspring_parent_ids'].count(k) for k in selected) > 1):
                raise ValueError('Inheritance must use only mature selected parents with balanced offspring.')
        elif (env['lineage_extinct'] != (not eligible)
                or env['extinction_generation'] != (index if not eligible else None)
                or (eligible and index != generations)):
            raise ValueError('Lineage must stop at extinction or the planned observation horizon.')
    if trial['training_genome_hashes'][0] != trial['genome_hashes']['founder'] or trial['training_genome_hashes'][-1] != trial['genome_hashes']['last_cohort']:
        raise ValueError('Archives must contain the original founders and complete last birth cohort.')


def save_models(path, metadata, banks):
    path = Path(path)
    if path.exists():
        raise ValueError('Preserve existing seasonal model archives.')
    arrays = {'ids': np.arange(1, 101, dtype=np.int64), 'metadata': np.array(json.dumps(metadata, allow_nan=False))}
    for name in BANKS:
        for index, attribute in enumerate(PARAMETER_NAMES):
            arrays[f'{name}_{index}'] = np.stack([getattr(banks[name][key], attribute) for key in range(1, 101)])
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp.npz')
    np.savez_compressed(temp, **arrays)
    temp.replace(path)


def load_models(path, seed, generations):
    with np.load(path, allow_pickle=False) as a:
        metadata = json.loads(str(a['metadata'].item()))
        if metadata['seed'] != seed or a['ids'].dtype.kind not in 'iu' or a['ids'].tolist() != list(range(1, 101)):
            raise ValueError('Wrong seasonal archive seed or cohort IDs.')
        validate_lineage(metadata, generations)
        banks = {}
        for name in BANKS:
            arrays = [a[f'{name}_{index}'] for index in range(4)]
            if any(x.shape != (100, *shape) or not np.all(np.isfinite(x)) for x, shape in zip(arrays, PARAMETER_SHAPES)):
                raise ValueError('Invalid seasonal neural arrays.')
            banks[name] = {}
            for index in range(100):
                brain = object.__new__(NeuralNetwork)
                for attribute, values in zip(PARAMETER_NAMES, arrays):
                    setattr(brain, attribute, values[index].copy())
                banks[name][index + 1] = brain
            if bank_digest(banks[name]) != metadata['genome_hashes'][name]:
                raise ValueError('Frozen archive genome hash mismatch.')
    return metadata, banks


def run_lineage(seed, generations, models_dir, forbidden, progress=False):
    world = SeasonalWorld(seed=seed, fixed_speed=60.0)
    founders = {c.creature_id: c.brain.copy() for c in world.creatures}
    simulation = EvolutionSimulation(world, generation_limit=generations, auto_advance=False)
    starts, hashes, bodies = [], [], []
    for generation in range(1, generations + 1):
        starts.append(initial_conditions_digest(world))
        hashes.append(genome_digest(world.creatures))
        bodies.append(bodies_digest(world))
        complete_generation(simulation)
        if progress:
            row = world.environment_history[-1]
            print(f"Seed {seed}: G{generation} {row['season']}, food {row['food_count']}, eligible {row['eligible_parent_count']}/100"
                  + ('; LINEAGE EXTINCT' if world.lineage_extinct else ''), flush=True)
        if world.lineage_extinct or generation == generations:
            break
        if not simulation.advance_generation():
            raise RuntimeError('A viable seasonal lineage could not reproduce.')
    banks = {'last_cohort': {c.creature_id: c.brain.copy() for c in world.dead_creatures}, 'founder': founders}
    trial = {'seed': seed, 'training': simulation.report(), 'training_starts': starts,
             'training_genome_hashes': hashes, 'training_body_hashes': bodies,
             'last_birth_generation': world.generation, 'genome_hashes': {n: bank_digest(b) for n, b in banks.items()}}
    validate_lineage(trial, generations)
    path = Path(models_dir) / f'seed-{seed}.npz'
    save_models(path, trial, banks)
    trial.update(model_file=str(path), model_sha256=file_digest(path), tests=[])
    for challenge, food_count in CHALLENGES.items():
        test_seed = derived_seed(f'step21:test:{seed}:{challenge}')
        test = {'challenge': challenge, 'seed': test_seed, 'conditions': {}}
        for name, bank in banks.items():
            test_world = World(seed=test_seed, fixed_speed=60.0, food_distribution='clustered',
                               food_count=food_count, evolution_enabled=False)
            for c in test_world.creatures:
                c.brain = bank[c.creature_id].copy()
            initial = initial_conditions_digest(test_world)
            if initial in forbidden or initial in starts:
                raise RuntimeError('Diagnostic test layouts must be new.')
            test_simulation = EvolutionSimulation(test_world, generation_limit=1, auto_advance=False)
            complete_generation(test_simulation)
            if genome_digest(test_world.dead_creatures) != trial['genome_hashes'][name]:
                raise RuntimeError('Diagnostic evaluation changed an archived genome.')
            test['conditions'][name] = {'initial_conditions': initial, 'genomes_sha256': trial['genome_hashes'][name],
                                        'report': test_simulation.report()}
        trial['tests'].append(test)
        if progress:
            print(f'Seed {seed}: frozen {challenge} diagnostic complete (does not revive the lineage)', flush=True)
    return trial


def analyze_results(report):
    protocol, trials = report['protocol'], report['trials']
    seeds, limit = protocol['seeds'], protocol['generation_limit']
    if (len(seeds) < 2 or len(set(seeds)) != len(seeds) or len(trials) != len(seeds)
            or {t['seed'] for t in trials} != set(seeds) or protocol['season_food'] != list(DEFAULT_FOOD)
            or protocol['challenges'] != CHALLENGES or limit < 4 or limit % 4):
        raise ValueError('The complete declared independent-seed study is required.')
    trials = sorted(trials, key=lambda t: seeds.index(t['seed']))
    forbidden = set(protocol['excluded_initial_conditions']) | {p for t in trials for p in t['training_starts']}
    seen = set()
    for trial in trials:
        validate_lineage(trial, limit)
        if len(trial['tests']) != 2 or {t['challenge'] for t in trial['tests']} != set(CHALLENGES):
            raise ValueError('Both fresh standardized diagnostics must be present.')
        for test in trial['tests']:
            if set(test['conditions']) != set(BANKS) or test['seed'] != derived_seed(f"step21:test:{trial['seed']}:{test['challenge']}"):
                raise ValueError('Wrong diagnostic conditions or test namespace.')
            starts = {r['initial_conditions'] for r in test['conditions'].values()}
            if len(starts) != 1 or starts.intersection(forbidden | seen):
                raise ValueError('Diagnostic starts must be matched, new, and distinct.')
            seen.update(starts)
            for name, data in test['conditions'].items():
                r = data['report']
                if (any(r[k] != v for k, v in CONFIG.items()) or r['food_count'] != CHALLENGES[test['challenge']]
                        or r['evolution_enabled'] or r['seed'] != test['seed'] or r['completed_generations'] != 1
                        or len(r['generations']) != 1 or data['genomes_sha256'] != trial['genome_hashes'][name]):
                    raise ValueError('Diagnostics must use complete unchanged archived brain cohorts.')
                row = r['generations'][0]
                if (row['population_size'] != 100 or not np.isclose(row['mean_speed'], 60)
                        or row['survival_rate'] != row['survivors_at_checkpoint'] / 100
                        or not np.isclose(row['mean_fitness'], row['mean_survival_seconds'] + 10 * row['mean_food_eaten'])):
                    raise ValueError('Invalid diagnostic observations.')
    analysis = {'independent_seed_groups': len(seeds), 'actual_training_cohorts': sum(len(t['training']['generations']) for t in trials),
                'complete_diagnostic_cohorts': len(trials) * 4, 'by_generation': [], 'diagnostics': {}}
    for generation in range(1, limit + 1):
        rows = [t['training']['generations'][generation - 1] for t in trials if len(t['training']['generations']) >= generation]
        viable = sum(t['training']['seasonal_environment']['extinction_generation'] is None
                     or t['training']['seasonal_environment']['extinction_generation'] > generation for t in trials)
        analysis['by_generation'].append({**season_context(generation), 'cohorts_reached': len(rows),
            'lineages_eligible_to_continue': viable, 'retention_fraction': viable / len(seeds),
            'mean_fitness_among_reached': float(np.mean([r['mean_fitness'] for r in rows])) if rows else None,
            'mean_food_among_reached': float(np.mean([r['mean_food_eaten'] for r in rows])) if rows else None,
            'mean_survival_rate_among_reached': float(np.mean([r['survival_rate'] for r in rows])) if rows else None})
    extinct = [t for t in trials if t['training']['seasonal_environment']['lineage_extinct']]
    analysis['extinct_lineages'] = len(extinct)
    analysis['viable_at_horizon'] = len(trials) - len(extinct)
    analysis['extinction_generations'] = {str(t['seed']): t['training']['seasonal_environment']['extinction_generation'] for t in trials}
    for challenge in CHALLENGES:
        metrics = {}
        for metric in ('mean_fitness', 'mean_food_eaten', 'survival_rate'):
            values = {name: [next(x for x in t['tests'] if x['challenge'] == challenge)['conditions'][name]['report']['generations'][0][metric] for t in trials] for name in BANKS}
            pair = paired_metrics(values['last_cohort'], values['founder'], seed=derived_seed(f'step21:bootstrap:{challenge}:{metric}'))
            pair.pop('sign_test_p')
            metrics[metric] = pair
        analysis['diagnostics'][challenge] = metrics
    return analysis


def excluded_initial_conditions():
    excluded = set(prior_layouts())
    path = Path(__file__).resolve().parent / 'results/step20-brains.json'
    if path.exists():
        previous = json.loads(path.read_text())
        excluded.update(r['initial_conditions'] for t in previous['trials'] for test in t['tests'] for r in test['conditions'].values())
    return sorted(excluded)


def run_study(seeds=DEFAULT_SEEDS, *, generations=MAX_GENERATIONS, workers=1, models_dir='.cache/seasonal-models',
              progress=False, checkpoint=None, declare=None):
    seeds = list(seeds)
    if (len(seeds) < 2 or len(set(seeds)) != len(seeds) or any(type(s) is not int for s in seeds)
            or type(generations) is not int or generations < 4 or generations % 4
            or type(workers) is not int or workers < 1):
        raise ValueError('Use distinct integer seeds, a full-year generation limit divisible by four, and positive workers.')
    if any((Path(models_dir) / f'seed-{seed}.npz').exists() for seed in seeds):
        raise ValueError('Existing seasonal models are preserved; choose a new directory.')
    report = {'format_version': 1, 'status': 'running', 'protocol': {
        'seeds': seeds, 'generation_limit': generations, 'season_names': list(SEASON_NAMES),
        'season_food': list(DEFAULT_FOOD), 'generations_per_season': 1, 'cluster_shift_pixels': 120.0,
        'reproductive_age_seconds': 60.0, 'configuration': CONFIG, 'challenges': CHALLENGES,
        'maximum_training_cohorts': len(seeds) * generations, 'planned_diagnostic_cohorts': len(seeds) * 4,
        'excluded_initial_conditions': excluded_initial_conditions(),
        'parent_rule': 'Up to 20 highest-fitness individuals reaching age 60; neutral ID order, balanced 100 offspring. No eligible parent permanently ends the lineage.',
        'archive_rule': 'All 100 brains of the last evaluated birth cohort, including failures; maximum G archived, without extra reproduction at the horizon.',
        'diagnostic_rule': 'Paired fresh standard/scarce worlds compare last-cohort archives with exact founders for every seed, including extinct lineages. Shadow tests do not resume lineages.',
        'analysis': 'Exploratory; paired percentile bootstrap 20000, pointwise 95% intervals; source seed is unit, no confirmatory p-values.',
        'limitations': 'Raw seasonal fitness confounds food supply, moving layouts, evolution and survivor selection. Archive tests assess changed inherited performance, not survival of the lineage or causal effects of selection alone. No static-environment control; no claim of optimal seasonal adaptation. Fixed cohort size is not an emergent population model. Viability at horizon is censored, not permanent persistence.',
    }, 'trials': []}
    if declare: declare(report)
    if checkpoint: checkpoint(report)
    args = [(s, generations, models_dir, report['protocol']['excluded_initial_conditions'], progress) for s in seeds]
    if workers == 1:
        for arg in args:
            report['trials'].append(run_lineage(*arg))
            if checkpoint: checkpoint(report)
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(seeds))) as executor:
            futures = [executor.submit(run_lineage, *arg) for arg in args]
            for future in as_completed(futures):
                report['trials'].append(future.result())
                if checkpoint: checkpoint(report)
    report['trials'].sort(key=lambda t: seeds.index(t['seed']))
    report['analysis'] = analyze_results(report)
    report['status'] = 'complete'
    if checkpoint: checkpoint(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', type=int, nargs='+', default=DEFAULT_SEEDS)
    parser.add_argument('--generations', type=positive_integer, default=MAX_GENERATIONS)
    parser.add_argument('--workers', type=positive_integer, default=1)
    parser.add_argument('--models-dir', type=Path, default=Path('.cache/seasonal-models'))
    parser.add_argument('--output', type=Path, default=Path('.cache/seasons.json'))
    parser.add_argument('--protocol-output', type=Path, default=Path('.cache/seasons-protocol.json'))
    args = parser.parse_args()
    paths = [args.output.resolve(), args.protocol_output.resolve()]
    if len(set(paths)) != 2 or any(p.exists() or p.suffix != '.json' for p in paths):
        parser.error('Use distinct new JSON output paths; preserve existing results.')
    def write(report):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix('.tmp.json')
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
        temporary.replace(args.output)
    def declare(report):
        root = Path(__file__).resolve().parent
        args.protocol_output.parent.mkdir(parents=True, exist_ok=True)
        args.protocol_output.write_text(json.dumps({'declared_at_utc': datetime.now(timezone.utc).isoformat(),
            'protocol': report['protocol'], 'source_sha256': {p.name: file_digest(p) for p in sorted(root.glob('*.py'))}}, indent=2) + '\n')
    try:
        run_study(args.seeds, generations=args.generations, workers=args.workers, models_dir=args.models_dir,
                  progress=True, checkpoint=write, declare=declare)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f'Seasonal study complete: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
