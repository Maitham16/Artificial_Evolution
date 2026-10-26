"""Frozen matched tests of foraging, avoidance, and added-risk-sensor usefulness."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import random

import numpy as np

from analyze_intelligence import bank_digest
from brain import NeuralNetwork
from compare_creatures import complete_generation, derived_seed, genome_digest, initial_conditions_digest, positive_integer
from experiment_speed import classify_primary, paired_metrics
from experiment_specialization import bodies_digest
from experiment_seasons import excluded_initial_conditions
from experiment_strategy import file_digest
from obstacles import (COLLISION_ENERGY, COLLISION_FITNESS, HAZARD_ENERGY_PER_SECOND,
                       HAZARD_FITNESS_PER_SECOND, INPUT_SIZE, SENSORS, ObstacleWorld, geometry_digest, layout)
from simulation import EvolutionSimulation


DEFAULT_SEEDS = tuple(range(2201, 2213))
CONDITIONS = ('evolved', 'risk_hidden', 'founder')
CONFIG = {'population_size': 100, 'food_count': 150, 'fixed_speed': 60.0, 'arena_size': [1000, 600],
          'food_distribution': 'uniform', 'controller': 'neural', 'food_sensor_mode': 'intact',
          'mutation_rate': .1, 'mutation_scale': .1}
SHAPES = ((16, 8), (8,), (8, 2), (2,))
ATTRIBUTES = ('input_weights', 'hidden_bias', 'output_weights', 'output_bias')
METRICS = ('mean_fitness', 'mean_food_eaten', 'survival_rate', 'collision_rate', 'hazard_fraction')


def validate_cohorts(data, *, study=True):
    environment = data['obstacle_environment']
    rows, history = data['generations'], environment['history']
    population = data['population_size']
    if ((study and any(data[k] != v for k, v in CONFIG.items())) or environment['input_size'] != INPUT_SIZE
            or environment['sensors'] != list(SENSORS) or len(rows) != len(history)
            or data['completed_generations'] != len(rows)
            or environment['collision_energy'] != COLLISION_ENERGY
            or environment['collision_fitness'] != COLLISION_FITNESS
            or environment['hazard_energy_per_second'] != HAZARD_ENERGY_PER_SECOND
            or environment['hazard_fitness_per_second'] != HAZARD_FITNESS_PER_SECOND):
        raise ValueError('Obstacle reports must match the declared architecture, physics, and costs.')
    for index, (row, context) in enumerate(zip(rows, history), 1):
        barriers, dangers = layout(data['seed'], index, *data['arena_size'])
        records = context['creatures']
        if (not context['complete'] or row['generation'] != index or context['generation'] != index
                or context['geometry_sha256'] != geometry_digest(barriers, dangers)
                or context['barriers'] != [list(b.__dict__.values()) for b in barriers]
                or context['dangers'] != [list(h.__dict__.values()) for h in dangers]
                or row['population_size'] != population or [r['creature_id'] for r in records] != list(range(1, population + 1))
                or (data['fixed_speed'] is not None and not np.isclose(row['mean_speed'], data['fixed_speed']))):
            raise ValueError('Every cohort requires complete IDs, canonical geometry, and matched fixed speed.')
        for r in records:
            expected = r['age'] + 10 * r['food_eaten'] - 2 * r['collisions'] - 5 * r['hazard_seconds']
            if (not all(np.isfinite(r[k]) for k in ('age', 'fitness', 'hazard_seconds'))
                    or not 0 <= r['hazard_seconds'] <= r['age'] <= 120
                    or type(r['collisions']) is not int or r['collisions'] < 0
                    or type(r['food_eaten']) is not int or r['food_eaten'] < 0
                    or not np.isclose(r['fitness'], expected)):
                raise ValueError('Invalid risk exposure, collisions, or penalized fitness.')
        living = sum(r['age'] for r in records)
        if living <= 0: raise ValueError('Risk rates require positive observed living time.')
        if (not np.isclose(row['mean_fitness'], np.mean([r['fitness'] for r in records]))
                or not np.isclose(row['mean_food_eaten'], np.mean([r['food_eaten'] for r in records]))
                or not np.isclose(row['mean_survival_seconds'], living / population)
                or row['survivors_at_checkpoint'] != sum(r['age'] >= 60 for r in records)
                or row['survival_rate'] != row['survivors_at_checkpoint'] / population
                or row['duration_seconds'] + 1e-8 < max(r['age'] for r in records)
                or not np.isclose(context['collision_rate'], 60 * sum(r['collisions'] for r in records) / living)
                or not np.isclose(context['hazard_fraction'], sum(r['hazard_seconds'] for r in records) / living)):
            raise ValueError('Cohort summaries or living-time denominators do not match individual records.')


def validate_training(trial, generations):
    data = trial['training'];validate_cohorts(data)
    traces = data['obstacle_environment']['transitions']
    if (data['seed'] != trial['seed'] or data['completed_generations'] != generations or not data['evolution_enabled']
            or data['obstacle_environment']['risk_sensor_mode'] != 'intact' or len(traces) != generations - 1
            or len(trial['training_starts']) != generations or len(trial['training_genome_hashes']) != generations
            or len(trial['training_body_hashes']) != generations
            or trial['training_genome_hashes'][0] != trial['genome_hashes']['founder']
            or trial['training_genome_hashes'][-1] != trial['genome_hashes']['evolved']):
        raise ValueError('Training must preserve complete founders, histories, and last evaluated cohorts.')
    for index, trace in enumerate(traces, 1):
        records = data['obstacle_environment']['history'][index - 1]['creatures']
        expected = sorted(r['creature_id'] for r in sorted(records, key=lambda r: (-r['fitness'], r['creature_id']))[:20])
        mutation_seed = random.Random(f'mutation:{trial["seed"]}:generation:{index + 1}').getrandbits(128)
        if (trace['parent_ids'] != expected or trace['from_generation'] != index or trace['to_generation'] != index + 1
                or trace['mutation_seed'] != mutation_seed or trace['mutation_rng_calls'] != 801
                or len(trace['offspring_parent_ids']) != 100 or len(trace['offspring_mutation_counts']) != 100
                or any(trace['offspring_parent_ids'].count(k) != 5 for k in expected)
                or set(trace['offspring_parent_ids']) != set(expected)):
            raise ValueError('Inheritance must follow the declared penalized-fitness selection and mutation stream.')


def save_models(path, metadata, banks):
    path = Path(path)
    if path.exists(): raise ValueError('Preserve existing obstacle model archives.')
    arrays = {'ids': np.arange(1, 101, dtype=np.int64), 'metadata': np.array(json.dumps(metadata, allow_nan=False))}
    for name, bank in banks.items():
        for index, attribute in enumerate(ATTRIBUTES):
            arrays[f'{name}_{index}'] = np.stack([getattr(bank[k], attribute) for k in range(1, 101)])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp.npz');np.savez_compressed(temporary, **arrays);temporary.replace(path)


def load_models(path, seed, generations):
    with np.load(path, allow_pickle=False) as a:
        metadata = json.loads(str(a['metadata'].item()))
        if metadata['seed'] != seed or a['ids'].dtype.kind not in 'iu' or a['ids'].tolist() != list(range(1, 101)):
            raise ValueError('Invalid obstacle archive seed or IDs.')
        validate_training(metadata, generations)
        banks = {}
        for name in ('evolved', 'founder'):
            arrays = [a[f'{name}_{i}'] for i in range(4)]
            if any(x.shape != (100, *shape) or not np.all(np.isfinite(x)) for x, shape in zip(arrays, SHAPES)):
                raise ValueError('Invalid 16-input obstacle brain parameters.')
            banks[name] = {}
            for index in range(100):
                brain = object.__new__(NeuralNetwork)
                for attribute, values in zip(ATTRIBUTES, arrays):setattr(brain, attribute, values[index].copy())
                banks[name][index + 1] = brain
            if bank_digest(banks[name]) != metadata['genome_hashes'][name]: raise ValueError('Frozen brain hash mismatch.')
    return metadata, banks


def observations(data):
    return {**{k: data['generations'][0][k] for k in METRICS[:3]},
            **{k: data['obstacle_environment']['history'][0][k] for k in METRICS[3:]}}


def run_lineage(seed, generations, repeats, models_dir, forbidden, progress=False):
    world = ObstacleWorld(seed=seed, fixed_speed=60.0)
    founders = {c.creature_id: c.brain.copy() for c in world.creatures}
    simulation = EvolutionSimulation(world, generation_limit=generations, auto_advance=False)
    starts, hashes, bodies = [], [], []
    for g in range(1, generations + 1):
        starts.append(initial_conditions_digest(world));hashes.append(genome_digest(world.creatures));bodies.append(bodies_digest(world))
        complete_generation(simulation)
        if progress and g in (1, generations // 2, generations):
            print(f'Seed {seed}: obstacle training G{g}/{generations} complete', flush=True)
        if g < generations and not simulation.advance_generation():raise RuntimeError('Could not advance obstacle training.')
    banks = {'evolved': {c.creature_id: c.brain.copy() for c in world.dead_creatures}, 'founder': founders}
    trial = {'seed': seed, 'training': simulation.report(), 'training_starts': starts,
        'training_genome_hashes': hashes, 'training_body_hashes': bodies,
        'genome_hashes': {name: bank_digest(bank) for name, bank in banks.items()}}
    validate_training(trial, generations)
    path = Path(models_dir) / f'seed-{seed}.npz';save_models(path, trial, banks)
    trial.update(model_file=str(path), model_sha256=file_digest(path), tests=[])
    for repeat in range(1, repeats + 1):
        test_seed = derived_seed(f'step22:test:{seed}:{repeat}')
        test = {'repeat': repeat, 'seed': test_seed, 'conditions': {}}
        for condition in CONDITIONS:
            name = 'founder' if condition == 'founder' else 'evolved'
            test_world = ObstacleWorld(seed=test_seed, fixed_speed=60.0, evolution_enabled=False,
                                       risk_sensor_mode='hidden' if condition == 'risk_hidden' else 'intact')
            for c in test_world.creatures:c.brain = banks[name][c.creature_id].copy()
            initial = initial_conditions_digest(test_world)
            if initial in forbidden or initial in starts:raise RuntimeError('Held-out physical layouts must be new.')
            test_simulation = EvolutionSimulation(test_world, generation_limit=1, auto_advance=False)
            complete_generation(test_simulation)
            if genome_digest(test_world.dead_creatures) != trial['genome_hashes'][name]:raise RuntimeError('Frozen evaluation changed a brain.')
            test['conditions'][condition] = {'initial_conditions': initial, 'genomes_sha256': trial['genome_hashes'][name], 'report': test_simulation.report()}
        trial['tests'].append(test)
        if progress:print(f'Seed {seed}: held-out layout {repeat}/{repeats}, all three conditions complete', flush=True)
    return trial


def analyze_results(report):
    p, trials = report['protocol'], report['trials'];seeds=p['seeds'];repeats=p['repeats']
    if (len(seeds) < 2 or len(set(seeds)) != len(seeds) or len(trials) != len(seeds) or {t['seed'] for t in trials} != set(seeds)
            or p['configuration'] != CONFIG or p['conditions'] != list(CONDITIONS) or type(repeats) is not int or repeats < 1):
        raise ValueError('A complete planned matched study is required.')
    trials = sorted(trials, key=lambda t: seeds.index(t['seed']))
    forbidden = set(p['excluded_initial_conditions']) | {s for t in trials for s in t['training_starts']};seen=set()
    for t in trials:
        validate_training(t, p['generations'])
        if len(t['tests']) != repeats or {x['repeat'] for x in t['tests']} != set(range(1, repeats + 1)):
            raise ValueError('Every repeat must be present once.')
        for test in t['tests']:
            if set(test['conditions']) != set(CONDITIONS) or test['seed'] != derived_seed(f'step22:test:{t["seed"]}:{test["repeat"]}'):
                raise ValueError('Missing control or wrong test seed namespace.')
            starts={r['initial_conditions'] for r in test['conditions'].values()}
            if len(starts) != 1 or starts.intersection(forbidden | seen):raise ValueError('Tests must be physically matched, distinct, and new.')
            seen.update(starts);geometry=set()
            for condition,r in test['conditions'].items():
                data=r['report'];validate_cohorts(data)
                name='founder' if condition=='founder' else 'evolved'
                if (data['evolution_enabled'] or data['seed'] != test['seed'] or data['completed_generations'] != 1
                        or data['obstacle_environment']['risk_sensor_mode'] != ('hidden' if condition=='risk_hidden' else 'intact')
                        or r['genomes_sha256'] != t['genome_hashes'][name]):raise ValueError('Evaluation must freeze the declared genomes and sensor intervention.')
                geometry.add(data['obstacle_environment']['history'][0]['geometry_sha256'])
            if len(geometry) != 1:raise ValueError('Obstacles and hazards must match across conditions.')
    values={c:{metric:[float(np.mean([observations(test['conditions'][c]['report'])[metric] for test in t['tests']])) for t in trials] for metric in METRICS} for c in CONDITIONS}
    def pair(metric,left,right,label):return paired_metrics(values[left][metric],values[right][metric],seed=derived_seed(f'step22:bootstrap:{label}'))
    primary={
        'fitness_gain':pair('mean_fitness','evolved','founder','fitness_gain'),
        'food_gain':pair('mean_food_eaten','evolved','founder','food_gain'),
        'collision_change':pair('collision_rate','evolved','founder','collision_change'),
        'hazard_change':pair('hazard_fraction','evolved','founder','hazard_change'),
        'risk_sensor_benefit':pair('mean_fitness','evolved','risk_hidden','risk_sensor_benefit'),
    }
    classify_primary(list(primary.values()))
    avoidance=(primary['fitness_gain']['conclusion']=='higher' and primary['food_gain']['conclusion']=='higher'
               and any(primary[name]['conclusion']=='lower' for name in ('collision_change','hazard_change')))
    return {'independent_seed_groups':len(seeds),'seed_values':values,
            'condition_means':{c:{m:float(np.mean(v)) for m,v in metrics.items()} for c,metrics in values.items()},
            'primary':primary,'avoidance_with_improved_foraging_supported':avoidance,
            'added_risk_sensor_benefit_supported':primary['risk_sensor_benefit']['conclusion']=='higher'}


def prior_layouts():
    forbidden=set(excluded_initial_conditions())
    path=Path(__file__).resolve().parent/'results/step21-seasons.json'
    if path.exists():
        old=json.loads(path.read_text())
        forbidden.update(s for t in old['trials'] for s in t['training_starts'])
        forbidden.update(r['initial_conditions'] for t in old['trials'] for test in t['tests'] for r in test['conditions'].values())
    return sorted(forbidden)


def run_study(seeds=DEFAULT_SEEDS,*,generations=8,repeats=2,workers=1,models_dir='.cache/obstacle-models',progress=False,checkpoint=None,declare=None):
    seeds=list(seeds)
    if (len(seeds)<2 or len(set(seeds))!=len(seeds) or any(type(s)is not int for s in seeds)
            or type(generations)is not int or generations<2 or type(repeats)is not int or repeats<1 or type(workers)is not int or workers<1):
        raise ValueError('Use distinct integer seeds, at least two generations, and positive repeats/workers.')
    if any((Path(models_dir)/f'seed-{s}.npz').exists() for s in seeds):raise ValueError('Preserve existing obstacle archives; choose a new directory.')
    report={'format_version':1,'status':'running','protocol':{
        'seeds':seeds,'generations':generations,'repeats':repeats,'configuration':CONFIG,'conditions':list(CONDITIONS),
        'input_size':INPUT_SIZE,'hidden_size':8,'parameter_count':154,'sensors':list(SENSORS),
        'training_cohorts':len(seeds)*generations,'test_cohorts':len(seeds)*repeats*3,
        'excluded_initial_conditions':prior_layouts(),
        'primary_family':'Five two-sided exact paired sign tests with Holm correction: evolved vs founder fitness, meals, collision rate, hazard fraction; evolved intact vs risk-hidden fitness.',
        'decision':'Adjusted p < .05 and paired mean-difference interval excluding zero in the same direction. Avoidance with foraging requires fitness_gain higher AND food_gain higher AND (collision_change lower OR hazard_change lower).',
        'analysis_unit':'Independent source seed; held-out repeats averaged within seed before inference.',
        'intervals':'Paired percentile bootstrap, 20000 resamples, pointwise 95%. Sign ties <=1e-10.',
        'fitness':'age + 10*meals - 2*barrier_collisions - 5*hazard_seconds',
        'physical_costs':{'collision_energy':2.,'hazard_energy_per_second':12.},
        'sensing':'Five radius-expanded barrier rays at -90,-45,0,45,90 degrees, range160; nearest hazard proximity,bearing,inside. Hidden risk inputs replace rays with1 and hazard inputs with0; original8 remain intact.',
        'limitations':'Fresh layouts from the same geometry family, not arbitrary mazes. Food sensing is non-occluded. Bodies use conservative radius-expanded rectangular barrier envelopes. Danger is charged at fixed-tick starting positions; default motion is1 pixel/tick. Penalized fitness mixes reward and costs; avoidance also requires improved meals and reduced living-time-normalized risk. No seasonal gate or static-training/drift control. No navigation/planning claim.',
    },'trials':[]}
    if declare:declare(report)
    if checkpoint:checkpoint(report)
    args=[(s,generations,repeats,models_dir,report['protocol']['excluded_initial_conditions'],progress) for s in seeds]
    if workers==1:
        for arg in args:
            report['trials'].append(run_lineage(*arg))
            if checkpoint:checkpoint(report)
    else:
        with ProcessPoolExecutor(max_workers=min(workers,len(seeds))) as executor:
            futures=[executor.submit(run_lineage,*arg) for arg in args]
            for future in as_completed(futures):
                report['trials'].append(future.result())
                if checkpoint:checkpoint(report)
    report['trials'].sort(key=lambda t:seeds.index(t['seed']))
    report['analysis']=analyze_results(report);report['status']='complete'
    if checkpoint:checkpoint(report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds',nargs='+',type=int,default=DEFAULT_SEEDS)
    parser.add_argument('--generations',type=positive_integer,default=8)
    parser.add_argument('--repeats',type=positive_integer,default=2)
    parser.add_argument('--workers',type=positive_integer,default=1)
    parser.add_argument('--models-dir',type=Path,default=Path('.cache/obstacle-models'))
    parser.add_argument('--output',type=Path,default=Path('.cache/obstacles.json'))
    parser.add_argument('--protocol-output',type=Path,default=Path('.cache/obstacle-protocol.json'))
    args=parser.parse_args();paths=[args.output.resolve(),args.protocol_output.resolve()]
    if len(set(paths))!=2 or any(p.exists() or p.suffix!='.json' for p in paths):parser.error('Use distinct new JSON output paths.')
    def write(report):
        args.output.parent.mkdir(parents=True,exist_ok=True);temporary=args.output.with_suffix('.tmp.json')
        temporary.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');temporary.replace(args.output)
    def declare(report):
        root=Path(__file__).resolve().parent;args.protocol_output.parent.mkdir(parents=True,exist_ok=True)
        args.protocol_output.write_text(json.dumps({'declared_at_utc':datetime.now(timezone.utc).isoformat(),'protocol':report['protocol'],
            'source_sha256':{p.name:file_digest(p) for p in sorted(root.glob('*.py'))}},indent=2)+'\n')
    try:run_study(args.seeds,generations=args.generations,repeats=args.repeats,workers=args.workers,models_dir=args.models_dir,progress=True,checkpoint=write,declare=declare)
    except (ValueError,OSError) as error:parser.error(str(error))
    print(f'Obstacle study complete: {args.output}');return 0


if __name__=='__main__':raise SystemExit(main())
