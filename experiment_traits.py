"""Joint brain/body evolution and matched, frozen factorial body interventions."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import random

import numpy as np

from brain import NeuralNetwork
from body_traits import (BODY_MUTATION_RATE, BODY_MUTATION_SCALE, ENERGY_MODEL, BodyTraits,
                         TraitWorld, WholeGenome, genome_bank_digest, shared_layout_digest)
from compare_creatures import complete_generation, derived_seed, initial_conditions_digest, positive_integer
from experiment_speed import classify_primary, paired_metrics
from experiment_strategy import file_digest
from simulation import EvolutionSimulation


DEFAULT_SEEDS = tuple(range(2301, 2313))
CONDITIONS = ('joint', 'brain_only', 'body_only', 'founder')
ENVIRONMENTS = {'standard': 150, 'scarce': 50}
ATTRIBUTES = ('input_weights', 'hidden_bias', 'output_weights', 'output_bias')
SHAPES = ((8, 8), (8,), (8, 2), (2,))
CONFIG = {'arena_size': [1000, 600], 'population_size': 100, 'fixed_speed': None,
          'controller': 'neural', 'food_distribution': 'uniform', 'food_sensor_mode': 'intact',
          'mutation_rate': .1, 'mutation_scale': .1}
METRICS = ('mean_fitness', 'mean_food_eaten', 'survival_rate', 'mean_speed',
           'energy_per_living_second', 'sensing_share_of_energy', 'food_visible_fraction', 'food_energy_efficiency')


def validate_cohorts(data, *, study=True, food_count=150):
    profile = data['physical_traits']
    rows = data['generations']
    history = profile['history'] if study else [r for r in profile['history'] if r['complete']]
    population = data['population_size']
    if (profile['energy_model'] != ENERGY_MODEL or data['fixed_speed'] is not None
            or len(rows) != len(history) or data['completed_generations'] != len(rows)
            or (study and (any(data[k] != v for k, v in CONFIG.items()) or data['food_count'] != food_count
                or profile['body_mutation_rate'] != BODY_MUTATION_RATE or profile['body_mutation_scale'] != BODY_MUTATION_SCALE))):
        raise ValueError('Trait reports must match the declared energy model, genetic costs, and complete cohorts.')
    for index, (row, context) in enumerate(zip(rows, history), 1):
        records = context['creatures']
        if (not context['complete'] or context['generation'] != index or row['generation'] != index
                or row['population_size'] != population or len(context['birth_bodies']) != population
                or [r['creature_id'] for r in records] != list(range(1, population + 1))):
            raise ValueError('Every birth cohort must retain all individuals and its inherited body genes.')
        for record, birth_body in zip(records, context['birth_bodies']):
            body = BodyTraits.from_vector(record['body'])
            age = record['age']
            if (record['body'] != birth_body or not np.isfinite(age) or not 0 <= age <= 120
                    or type(record['food_eaten']) is not int or record['food_eaten'] < 0
                    or not np.isclose(record['fitness'], age + 10 * record['food_eaten'])
                    or not np.isclose(record['initial_energy'], body.initial_energy)
                    or not -1e-8 <= record['final_energy'] <= body.capacity + 1e-8):
                raise ValueError('Invalid inherited body, life history, or fitness.')
            powers = body.powers()
            spent = []
            for name, power in zip(('basal_energy', 'movement_energy', 'sensing_energy'), powers):
                value = record[name]
                if not np.isfinite(value) or value < 0 or not np.isclose(value, power * age, atol=1e-7):
                    raise ValueError('Integrated trait costs must follow actual living time.')
                spent.append(value)
            assimilated, wasted = record['assimilated_energy'], record['wasted_food_energy']
            if (not np.isfinite(assimilated) or not np.isfinite(wasted) or min(assimilated, wasted) < -1e-7
                    or not np.isclose(assimilated + wasted, 20 * record['food_eaten'], atol=1e-7)
                    or not np.isclose(body.initial_energy + assimilated - sum(spent), record['final_energy'], atol=1e-7)):
                raise ValueError('The food and expenditure ledger must conserve energy.')
        living = sum(r['age'] for r in records)
        speed_time = sum(r['age'] * r['body'][0] for r in records)
        if (living <= 0 or not np.isclose(row['mean_speed'], speed_time / living)
                or not np.isclose(row['mean_fitness'], np.mean([r['fitness'] for r in records]))
                or not np.isclose(row['mean_food_eaten'], np.mean([r['food_eaten'] for r in records]))
                or not np.isclose(row['mean_survival_seconds'], living / population)
                or row['survivors_at_checkpoint'] != sum(r['age'] >= 60 for r in records)
                or row['survival_rate'] != row['survivors_at_checkpoint'] / population
                or row['duration_seconds'] + 1e-8 < max(r['age'] for r in records)):
            raise ValueError('Cohort observations must include every creature and its actual gene-derived speed.')


def validate_training(trial, generations):
    data = trial['training']
    validate_cohorts(data)
    profile = data['physical_traits']
    if (data['seed'] != trial['seed'] or data['completed_generations'] != generations or not data['evolution_enabled']
            or len(profile['transitions']) != generations - 1
            or len(trial['training_starts']) != generations
            or len(trial['training_physical_starts']) != generations
            or [r['shared_layout_sha256'] for r in profile['history']] != trial['training_starts']
            or profile['history'][0]['genomes_sha256'] != trial['genome_hashes']['founder']
            or profile['history'][-1]['genomes_sha256'] != trial['genome_hashes']['evolved']
            or set(trial['intervention_hashes']) != set(CONDITIONS)
            or trial['intervention_hashes']['joint'] != trial['genome_hashes']['evolved']
            or trial['intervention_hashes']['founder'] != trial['genome_hashes']['founder']
            or any(r != [60., 8., 160.] for r in profile['history'][0]['birth_bodies'])):
        raise ValueError('Training must begin with reference-body founders and freeze the entire final evaluated birth cohort.')
    for index, trace in enumerate(profile['transitions'], 1):
        records = profile['history'][index - 1]['creatures']
        expected = sorted(r['creature_id'] for r in sorted(records, key=lambda r: (-r['fitness'], r['creature_id']))[:20])
        brain_seed = random.Random(f'mutation:{trial["seed"]}:generation:{index + 1}').getrandbits(128)
        body_seed = random.Random(f'step23:body-mutation:{trial["seed"]}:generation:{index + 1}').getrandbits(128)
        if (trace['parent_ids'] != expected or trace['from_generation'] != index or trace['to_generation'] != index + 1
                or trace['brain_mutation_seed'] != brain_seed or trace['body_mutation_seed'] != body_seed
                or trace['brain_rng_calls'] != 801 or trace['body_rng_calls'] != 200
                or len(trace['offspring_parent_ids']) != 100
                or len(trace['brain_mutation_counts']) != 100 or len(trace['body_mutation_counts']) != 100
                or any(not 0 <= n <= 3 for n in trace['body_mutation_counts'])
                or set(trace['offspring_parent_ids']) != set(expected)
                or any(trace['offspring_parent_ids'].count(k) != 5 for k in expected)):
            raise ValueError('Linked inheritance must use the selected parents and declared independent mutation streams.')


def save_models(path, metadata, banks):
    path = Path(path)
    if path.exists():
        raise ValueError('Preserve existing brain/body archives.')
    arrays = {'ids': np.arange(1, 101, dtype=np.int64), 'metadata': np.array(json.dumps(metadata, allow_nan=False))}
    for name, bank in banks.items():
        arrays[f'{name}_bodies'] = np.stack([bank[k].body.vector() for k in range(1, 101)])
        for index, attribute in enumerate(ATTRIBUTES):
            arrays[f'{name}_{index}'] = np.stack([getattr(bank[k].brain, attribute) for k in range(1, 101)])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp.npz')
    np.savez_compressed(temporary, **arrays)
    temporary.replace(path)


def load_models(path, seed, generations):
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(str(archive['metadata'].item()))
        if metadata['seed'] != seed or archive['ids'].dtype.kind not in 'iu' or archive['ids'].tolist() != list(range(1, 101)):
            raise ValueError('Invalid brain/body archive seed or IDs.')
        validate_training(metadata, generations)
        banks = {}
        for name in ('evolved', 'founder'):
            arrays = [archive[f'{name}_{i}'] for i in range(4)]
            bodies = archive[f'{name}_bodies']
            if (bodies.shape != (100, 3) or not np.all(np.isfinite(bodies))
                    or any(a.shape != (100, *shape) or not np.all(np.isfinite(a)) for a, shape in zip(arrays, SHAPES))):
                raise ValueError('Invalid brain or body arrays.')
            bank = {}
            for index in range(100):
                brain = object.__new__(NeuralNetwork)
                for attribute, values in zip(ATTRIBUTES, arrays):
                    setattr(brain, attribute, values[index].copy())
                bank[index + 1] = WholeGenome(brain, BodyTraits.from_vector(bodies[index]))
            if genome_bank_digest(bank) != metadata['genome_hashes'][name]:
                raise ValueError('The linked genome hash does not match its numeric arrays.')
            banks[name] = bank
        if {c: genome_bank_digest(test_bank(banks, c)) for c in CONDITIONS} != metadata['intervention_hashes']:
            raise ValueError('Frozen brain/body intervention hashes do not match the archived components.')
    return metadata, banks


def test_bank(banks, condition):
    if condition not in CONDITIONS:
        raise ValueError('Unknown brain/body intervention.')
    brain_source = banks['evolved' if condition in ('joint', 'brain_only') else 'founder']
    body_source = banks['evolved' if condition in ('joint', 'body_only') else 'founder']
    return {k: WholeGenome(brain_source[k].brain.copy(), body_source[k].body) for k in range(1, 101)}


def observations(data):
    row = data['generations'][0]
    records = data['physical_traits']['history'][0]['creatures']
    living = sum(r['age'] for r in records)
    basal = sum(r['basal_energy'] for r in records)
    movement = sum(r['movement_energy'] for r in records)
    sensing = sum(r['sensing_energy'] for r in records)
    offered = 20 * sum(r['food_eaten'] for r in records)
    return {**{key: row[key] for key in METRICS[:4]},
        'energy_per_living_second': (basal + movement + sensing) / living,
        'sensing_share_of_energy': sensing / (basal + movement + sensing),
        'food_visible_fraction': row['food_visible_seconds'] / living,
        'food_energy_efficiency': sum(r['assimilated_energy'] for r in records) / offered if offered else None}


def descriptive_mean(values):
    available = [value for value in values if value is not None]
    return float(np.mean(available)) if available else None


def run_lineage(seed, generations, models_dir, progress=False):
    world = TraitWorld(seed=seed)
    founders = {c.creature_id: WholeGenome(c.brain.copy(), c.body) for c in world.creatures}
    simulation = EvolutionSimulation(world, generation_limit=generations, auto_advance=False)
    starts, physical = [], []
    for g in range(1, generations + 1):
        starts.append(shared_layout_digest(world))
        physical.append(initial_conditions_digest(world))
        complete_generation(simulation)
        if progress and g in (1, generations // 2, generations):
            print(f'Seed {seed}: joint brain/body training G{g}/{generations} complete', flush=True)
        if g < generations and not simulation.advance_generation():
            raise RuntimeError('Joint brain/body reproduction failed.')
    banks = {'evolved': {c.creature_id: WholeGenome(c.brain.copy(), c.body) for c in world.dead_creatures}, 'founder': founders}
    trial = {'seed': seed, 'training': simulation.report(), 'training_starts': starts,
             'training_physical_starts': physical, 'genome_hashes': {n: genome_bank_digest(b) for n, b in banks.items()},
             'intervention_hashes': {c: genome_bank_digest(test_bank(banks, c)) for c in CONDITIONS}}
    validate_training(trial, generations)
    path = Path(models_dir) / f'seed-{seed}.npz'
    save_models(path, trial, banks)
    trial.update(model_file=str(path), model_sha256=file_digest(path), tests=[])
    for environment, food_count in ENVIRONMENTS.items():
        test_seed = derived_seed(f'step23:test:{seed}:{environment}')
        test = {'environment': environment, 'seed': test_seed, 'conditions': {}}
        for condition in CONDITIONS:
            bank = test_bank(banks, condition)
            w = TraitWorld(seed=test_seed, food_count=food_count, evolution_enabled=False, genomes=bank)
            start = shared_layout_digest(w)
            if start in starts:
                raise RuntimeError('A held-out shared scenario was used in training.')
            s = EvolutionSimulation(w, generation_limit=1, auto_advance=False)
            complete_generation(s)
            frozen = {c.creature_id: WholeGenome(c.brain, c.body) for c in w.dead_creatures}
            if genome_bank_digest(frozen) != genome_bank_digest(bank):
                raise RuntimeError('Evaluation changed a frozen brain or body genome.')
            test['conditions'][condition] = {'shared_layout_sha256': start, 'genomes_sha256': genome_bank_digest(bank), 'report': s.report()}
        trial['tests'].append(test)
        if progress:
            print(f'Seed {seed}: {environment}, all four frozen brain/body combinations complete', flush=True)
    return trial


def analyze_results(report):
    p, trials = report['protocol'], report['trials']
    seeds = p['seeds']
    if (len(seeds) < 2 or len(set(seeds)) != len(seeds) or len(trials) != len(seeds)
            or {t['seed'] for t in trials} != set(seeds) or p['configuration'] != CONFIG
            or p['conditions'] != list(CONDITIONS) or p['environments'] != ENVIRONMENTS):
        raise ValueError('A complete declared joint-evolution study is required.')
    trials = sorted(trials, key=lambda t: seeds.index(t['seed']))
    training_starts = {s for t in trials for s in t['training_starts']}
    seen = set()
    for trial in trials:
        validate_training(trial, p['generations'])
        if len(trial['tests']) != 2 or {x['environment'] for x in trial['tests']} != set(ENVIRONMENTS):
            raise ValueError('Both held-out resource environments must be present.')
        for test in trial['tests']:
            if (set(test['conditions']) != set(CONDITIONS)
                    or test['seed'] != derived_seed(f'step23:test:{trial["seed"]}:{test["environment"]}')):
                raise ValueError('Missing factorial condition or wrong test namespace.')
            starts = {x['shared_layout_sha256'] for x in test['conditions'].values()}
            if len(starts) != 1 or starts.intersection(seen | training_starts):
                raise ValueError('Counterfactuals need matched, distinct, unseen anchor/food scenarios.')
            seen.update(starts)
            for condition, record in test['conditions'].items():
                data = record['report']
                validate_cohorts(data, food_count=ENVIRONMENTS[test['environment']])
                profile = data['physical_traits']
                if (data['evolution_enabled'] or data['seed'] != test['seed'] or data['completed_generations'] != 1
                        or profile['transitions'] or profile['history'][0]['shared_layout_sha256'] != record['shared_layout_sha256']
                        or profile['history'][0]['genomes_sha256'] != record['genomes_sha256']
                        or record['genomes_sha256'] != trial['intervention_hashes'][condition]):
                    raise ValueError('Tests must freeze complete counterfactual brain/body cohorts.')
                if condition in ('founder', 'brain_only') and any(r != [60., 8., 160.] for r in profile['history'][0]['birth_bodies']):
                    raise ValueError('The reference-body intervention must use the exact founding phenotype.')
            if test['conditions']['joint']['genomes_sha256'] != trial['genome_hashes']['evolved'] or test['conditions']['founder']['genomes_sha256'] != trial['genome_hashes']['founder']:
                raise ValueError('Full-genome tests must use the archived founders and final birth cohort.')
    analysis = {'independent_seed_groups': len(seeds), 'environments': {}, 'birth_trait_means_by_generation': []}
    primary = []
    for environment in ENVIRONMENTS:
        values = {c: {m: [observations(next(x for x in t['tests'] if x['environment'] == environment)['conditions'][c]['report'])[m] for t in trials] for m in METRICS} for c in CONDITIONS}
        contrasts = {}
        for control in ('founder', 'brain_only'):
            result = paired_metrics(values['joint']['mean_fitness'], values[control]['mean_fitness'], seed=derived_seed(f'step23:bootstrap:{environment}:{control}'))
            contrasts[control] = result
            primary.append(result)
        body_with_evolved_brain = np.asarray(values['joint']['mean_fitness']) - values['brain_only']['mean_fitness']
        body_with_founder_brain = np.asarray(values['body_only']['mean_fitness']) - values['founder']['mean_fitness']
        interaction = paired_metrics(body_with_evolved_brain, body_with_founder_brain, seed=derived_seed(f'step23:interaction:{environment}'))
        interaction.pop('sign_test_p')
        analysis['environments'][environment] = {'seed_values': values, 'primary_fitness': contrasts,
            'descriptive_brain_body_interaction': interaction,
            'condition_means': {c: {m: descriptive_mean(x) for m, x in metrics.items()} for c, metrics in values.items()},
            'descriptive_counts': {c: {m: sum(v is not None for v in x) for m, x in metrics.items()} for c, metrics in values.items()}}
    classify_primary(primary)
    for index in range(p['generations']):
        means = [np.mean(t['training']['physical_traits']['history'][index]['birth_bodies'], axis=0) for t in trials]
        analysis['birth_trait_means_by_generation'].append({'generation': index + 1,
            'seed_values': [m.tolist() for m in means], 'mean': np.mean(means, axis=0).tolist()})
    return analysis


def run_study(seeds=DEFAULT_SEEDS, *, generations=8, workers=1, models_dir='.cache/trait-models', progress=False, checkpoint=None, declare=None):
    seeds = list(seeds)
    if (len(seeds) < 2 or len(set(seeds)) != len(seeds) or any(type(s) is not int for s in seeds)
            or type(generations) is not int or generations < 2 or type(workers) is not int or workers < 1):
        raise ValueError('Use independent integer seeds, at least two generations, and positive workers.')
    if any((Path(models_dir) / f'seed-{s}.npz').exists() for s in seeds):
        raise ValueError('Preserve existing brain/body model archives.')
    report = {'format_version': 1, 'status': 'running', 'protocol': {
        'seeds': seeds, 'generations': generations, 'configuration': CONFIG, 'conditions': list(CONDITIONS),
        'environments': ENVIRONMENTS, 'energy_model': ENERGY_MODEL,
        'body_mutation_rate': BODY_MUTATION_RATE, 'body_mutation_scale': BODY_MUTATION_SCALE,
        'training_cohorts': len(seeds) * generations, 'test_cohorts': len(seeds) * 8,
        'genome': '90 neural parameters plus three linked body traits. Every founder has speed60, radius8, range160. All traits inherit from the same parent as the brain.',
        'mutation': 'Brain .1 probability and .1 Gaussian additive noise. Body .25 probability per allele and .08 Gaussian log noise; clip to bounds, round radius. Independent RNG streams; actual changed alleles recorded.',
        'matched_scenarios': 'All treatments share maximum-radius anchors, heading/color/lifespan draws, and initial food. Actual size, speed, vision, capacity, initial energy and costs differ intentionally. Shared-layout hashes exclude these treated physical traits.',
        'primary': 'Four fitness contrasts: joint minus founder and joint minus same evolved brain/reference body, separately in standard and scarce tests; exact two-sided paired sign tests, Holm over four.',
        'decision': 'Adjusted p < .05 and paired mean-difference interval excluding zero in the same direction; ties <=1e-10. Independent source seed is unit, n=len(seeds).',
        'intervals': '20000 paired percentile bootstrap resamples; pointwise 95%.',
        'secondary': 'Meals, survival, speed, energy costs, useful food energy, visibility, trait trends and brain/body interaction are descriptive without confirmatory p-values.',
        'limitations': 'Stylized 2D energetics, not calibrated biology. All bodies receive the same100-unit birth budget, pay10*area development, then capacity clips initial reserves. No reproductive resource accounting or continuous growth. Cruise speed is genetically fixed within life, with neural throttle ignored. Lifespan and colors are not inherited. Fitness still rewards meals including partially wasted ones; energy assimilation and waste are reported. The reference-body brain condition is a frozen intervention, not a separately trained brain-only population. No static-body training or drift control, no global biological optimum claim.',
    }, 'trials': []}
    if declare: declare(report)
    if checkpoint: checkpoint(report)
    args = [(s, generations, models_dir, progress) for s in seeds]
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
    parser.add_argument('--seeds', nargs='+', type=int, default=DEFAULT_SEEDS)
    parser.add_argument('--generations', type=positive_integer, default=8)
    parser.add_argument('--workers', type=positive_integer, default=1)
    parser.add_argument('--models-dir', type=Path, default=Path('.cache/trait-models'))
    parser.add_argument('--output', type=Path, default=Path('.cache/traits.json'))
    parser.add_argument('--protocol-output', type=Path, default=Path('.cache/traits-protocol.json'))
    args = parser.parse_args()
    paths = [args.output.resolve(), args.protocol_output.resolve()]
    if len(set(paths)) != 2 or any(p.exists() or p.suffix != '.json' for p in paths):
        parser.error('Use distinct new JSON output paths.')
    def write(report):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temp = args.output.with_suffix('.tmp.json')
        temp.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
        temp.replace(args.output)
    def declare(report):
        root = Path(__file__).resolve().parent
        args.protocol_output.parent.mkdir(parents=True, exist_ok=True)
        args.protocol_output.write_text(json.dumps({'declared_at_utc': datetime.now(timezone.utc).isoformat(), 'protocol': report['protocol'],
            'source_sha256': {p.name: file_digest(p) for p in sorted(root.glob('*.py'))}}, indent=2) + '\n')
    try:
        run_study(args.seeds, generations=args.generations, workers=args.workers, models_dir=args.models_dir, progress=True, checkpoint=write, declare=declare)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f'Joint brain/body study complete: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
