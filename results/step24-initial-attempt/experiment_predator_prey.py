"""Matched historical-opponent tests of simultaneous predator/prey evolution."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import random

import numpy as np

from brain import NeuralNetwork
from body_traits import BodyTraits, WholeGenome, genome_bank_digest, shared_layout_digest
from compare_creatures import complete_generation, derived_seed, initial_conditions_digest, positive_integer
from experiment_speed import classify_primary, paired_metrics
from experiment_strategy import file_digest
from predator_prey import PredatorPreyWorld, SPECIES, CAPTURE_ENERGY, CAPTURE_REWARD, SENSOR_NAMES
from simulation import EvolutionSimulation


DEFAULT_SEEDS = tuple(range(2401, 2409))
ATTRIBUTES = ('input_weights', 'hidden_bias', 'output_weights', 'output_bias')
SHAPES = ((11, 8), (8,), (8, 2), (2,))
CONFIG = {'arena_size': [1000, 600], 'population_size': 100, 'food_count': 150, 'fixed_speed': None,
          'controller': 'neural', 'food_distribution': 'uniform', 'food_sensor_mode': 'intact',
          'mutation_rate': .1, 'mutation_scale': .1}


def checkpoint_generations(generations):
    if type(generations) is not int or generations < 3: raise ValueError('Use at least three training generations.')
    return [1, (generations + 1) // 2, generations]


def current_bank(world):
    return {c.creature_id: WholeGenome(c.brain.copy(), c.body) for c in [*world.creatures, *world.dead_creatures]}


def opponent_bank(predators, prey):
    return {k: (prey[k] if k <= 80 else predators[k]).copy() for k in range(1, 101)}


def case_name(predator_generation, prey_generation):
    return f'predator-{predator_generation}_prey-{prey_generation}'


def validate_cohorts(data, *, study=True):
    eco = data['ecosystem']
    history = eco['history'] if study else [h for h in eco['history'] if h['complete']]
    counts = eco['birth_counts']
    if (len(history) != data['completed_generations'] or len(history) != len(data['generations'])
            or eco['capture_energy'] != CAPTURE_ENERGY or eco['capture_reward'] != CAPTURE_REWARD
            or eco['sensor_names'] != list(SENSOR_NAMES)
            or (study and (any(data[k] != v for k, v in CONFIG.items()) or counts != {'prey': 80, 'predator': 20}
                or eco['body_mutation_rate'] != .25 or eco['body_mutation_scale'] != .08))):
        raise ValueError('Cohorts must match the declared shared arena and complete evaluation windows.')
    for index, row in enumerate(history, 1):
        records = row['creatures']
        if (not row['complete'] or row['generation'] != index or len(row['birth_bodies']) != data['population_size']
                or [c['creature_id'] for c in records] != list(range(1, data['population_size'] + 1))
                or row['duration'] > eco['episode_seconds'] + 1e-7 or row['duration'] <= 0):
            raise ValueError('Every evaluated birth cohort needs all individuals, including deaths and censored survivors.')
        for c, born in zip(records, row['birth_bodies']):
            body = BodyTraits.from_vector(c['body'])
            expected_species = 'prey' if c['creature_id'] <= counts['prey'] else 'predator'
            if (c['species'] != expected_species or born != c['body'] or not 0 <= c['age'] <= row['duration'] + 1e-7
                    or type(c['food_eaten']) is not int or type(c['captures']) is not int or min(c['food_eaten'], c['captures']) < 0
                    or (expected_species == 'prey' and c['captures'] != 0) or (expected_species == 'predator' and c['food_eaten'] != 0)
                    or not np.isclose(c['fitness'], c['age'] + (10 * c['food_eaten'] if expected_species == 'prey' else 30 * c['captures']))
                    or c['death_cause'] not in (None, 'predation', 'starvation', 'old_age')
                    or c['alive_at_end'] != (c['death_cause'] is None)
                    or (c['alive_at_end'] and not np.isclose(c['age'], row['duration']))
                    or (expected_species == 'predator' and c['death_cause'] == 'predation')
                    or not -1e-7 <= c['final_energy'] <= body.capacity + 1e-7):
                raise ValueError('Invalid species, score, death cause, or finite-window censoring.')
            spent = [c[k] for k in ('basal_energy', 'movement_energy', 'sensing_energy')]
            if (not np.all(np.isfinite(spent)) or any(x < 0 for x in spent)
                    or not np.allclose(spent, np.array(body.powers()) * c['age'], atol=1e-7)
                    or not np.isclose(c['initial_energy'], body.initial_energy)
                    or not np.isclose(c['assimilated_energy'] + c['wasted_food_energy'], 20 * c['food_eaten'], atol=1e-7)
                    or not np.isclose(c['capture_assimilated_energy'] + c['wasted_capture_energy'], 60 * c['captures'], atol=1e-7)
                    or min(c['assimilated_energy'], c['wasted_food_energy'], c['capture_assimilated_energy'], c['wasted_capture_energy']) < -1e-7
                    or not np.isclose(c['initial_energy'] + c['assimilated_energy'] + c['capture_assimilated_energy'] - sum(spent), c['final_energy'], atol=1e-7)
                    or not 0 <= c['away_seconds'] + c['toward_seconds'] <= c['opponent_visible_seconds'] + 1e-7
                    or c['opponent_visible_seconds'] > c['age'] + 1e-7):
                raise ValueError('Individual living-time costs, food/capture energy, or defensive denominators disagree.')
        events = row['capture_events']
        victims = [e['prey_id'] for e in events]
        record_by_id = {c['creature_id']: c for c in records}
        if (len(victims) != len(set(victims)) or len(events) != sum(c['captures'] for c in records)
                or set(victims) != {c['creature_id'] for c in records if c['death_cause'] == 'predation'}
                or row['capture_fraction'] != len(events) / counts['prey']):
            raise ValueError('Every captured prey must have exactly one hunter and one recorded removal.')
        for event in events:
            hunter, victim = record_by_id[event['predator_id']], record_by_id[event['prey_id']]
            if (hunter['species'] != 'predator' or victim['species'] != 'prey'
                    or not event['removed_at'] - 1 / 60 - 1e-7 <= event['contact_time'] <= event['removed_at'] + 1e-7
                    or not np.isclose(victim['age'], event['removed_at']) or hunter['age'] + 1e-7 < event['removed_at']):
                raise ValueError('Capture ownership and tick timing must match actual histories.')
        if any(c['captures'] != sum(e['predator_id']==c['creature_id'] for e in events) for c in records):
            raise ValueError('Each hunter must receive exactly its own capture events.')
        for species in SPECIES:
            members = [c for c in records if c['species'] == species]
            summary = row['species'][species]
            visible = sum(c['opponent_visible_seconds'] for c in members)
            for key in ('away', 'toward'):
                expected = sum(c[f'{key}_seconds'] for c in members) / visible if visible else None
                if summary[f'{key}_fraction'] != expected: raise ValueError('Behavior requires truthful visible-opponent time.')
            expected_ids = [c['creature_id'] for c in sorted(members, key=lambda c: (-c['fitness'], c['creature_id']))[:int(np.ceil(len(members) * .2))]]
            if (summary['births'] != counts[species] or summary['alive_at_end'] != sum(c['alive_at_end'] for c in members)
                    or summary['survival_rate'] != summary['alive_at_end'] / len(members)
                    or not np.isclose(summary['mean_fitness'], np.mean([c['fitness'] for c in members]))
                    or not np.isclose(summary['mean_age'], np.mean([c['age'] for c in members]))
                    or not np.isclose(summary['mean_meals'], np.mean([c['food_eaten'] for c in members]))
                    or summary['opponent_visible_seconds'] != visible
                    or summary['selected_ids'] != expected_ids or summary['captures'] != sum(c['captures'] for c in members)
                    or summary['deaths'] != {cause: sum(c['death_cause'] == cause for c in members) for cause in ('predation', 'starvation', 'old_age')}):
                raise ValueError('Each role requires its own complete fitness ranking and demographic denominator.')
        timeline = row['population']
        if timeline[0] != {'time': 0., **counts} or timeline[-1]['time'] != row['duration']:
            raise ValueError('Population traces must include birth and evaluation end.')
        if any(not 0 <= a['time'] < b['time'] <= row['duration'] for a,b in zip(timeline,timeline[1:])):
            raise ValueError('Population observations must have increasing finite times.')
        for point in timeline:
            for species in SPECIES:
                expected = counts[species] - sum(c['species'] == species and not c['alive_at_end'] and c['age'] <= point['time'] + 1e-7 for c in records)
                if point[species] != expected: raise ValueError('Live population counts must agree with individual deaths.')


def save_models(path, metadata, checkpoints):
    path = Path(path)
    if path.exists(): raise ValueError('Preserve existing historical populations.')
    arrays = {'ids': np.arange(1, 101), 'metadata': np.array(json.dumps(metadata, allow_nan=False))}
    for generation, bank in checkpoints.items():
        arrays[f'g{generation}_bodies'] = np.stack([bank[k].body.vector() for k in range(1, 101)])
        for index, attribute in enumerate(ATTRIBUTES): arrays[f'g{generation}_{index}'] = np.stack([getattr(bank[k].brain, attribute) for k in range(1, 101)])
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp.npz'); np.savez_compressed(temp, **arrays); temp.replace(path)


def load_models(path, seed, generations):
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(str(archive['metadata'].item()))
        if metadata['seed'] != seed or archive['ids'].tolist() != list(range(1, 101)):
            raise ValueError('Historical archive IDs or seed disagree.')
        validate_cohorts(metadata['training'])
        checkpoints = {}
        for g in checkpoint_generations(generations):
            bodies = archive[f'g{g}_bodies']
            arrays = [archive[f'g{g}_{i}'] for i in range(4)]
            if bodies.shape != (100, 3) or any(a.shape != (100, *s) or not np.all(np.isfinite(a)) for a, s in zip(arrays, SHAPES)):
                raise ValueError('Historical archives require finite 11–8–2 brains and three body traits.')
            bank = {}
            for i in range(100):
                brain = object.__new__(NeuralNetwork)
                for attribute, array in zip(ATTRIBUTES, arrays): setattr(brain, attribute, array[i].copy())
                bank[i + 1] = WholeGenome(brain, BodyTraits.from_vector(bodies[i]))
            if genome_bank_digest(bank) != metadata['checkpoint_hashes'][str(g)]: raise ValueError('Historical genome checksum changed.')
            checkpoints[g] = bank
        expected = {case_name(a,b):genome_bank_digest(opponent_bank(checkpoints[a],checkpoints[b])) for a in checkpoints for b in checkpoints}
        expected.update(prey_hidden=metadata['checkpoint_hashes'][str(generations)],predator_hidden=metadata['checkpoint_hashes'][str(generations)])
        if expected != metadata['test_genome_hashes']: raise ValueError('Historical cross-pairings do not match the archived gene pools.')
    return metadata, checkpoints


def run_lineage(seed, generations, episode_seconds, models_dir, progress=False):
    checkpoints, starts, physical = {}, [], []
    world = PredatorPreyWorld(seed=seed, episode_seconds=episode_seconds)
    simulation = EvolutionSimulation(world, generation_limit=generations, auto_advance=False)
    for g in range(1, generations + 1):
        starts.append(shared_layout_digest(world)); physical.append(initial_conditions_digest(world))
        complete_generation(simulation)
        if g in checkpoint_generations(generations): checkpoints[g] = current_bank(world)
        if progress: print(f'Seed {seed}: both populations completed G{g}/{generations}', flush=True)
        if g < generations and not simulation.advance_generation(): raise RuntimeError('Simultaneous reproduction failed.')
    trial = {'seed': seed, 'training': simulation.report(), 'training_starts': starts, 'training_physical_starts': physical,
             'checkpoint_hashes': {str(g): genome_bank_digest(bank) for g, bank in checkpoints.items()}}
    trial['test_genome_hashes'] = {case_name(a,b):genome_bank_digest(opponent_bank(checkpoints[a],checkpoints[b])) for a in checkpoints for b in checkpoints}
    trial['test_genome_hashes'].update(prey_hidden=trial['checkpoint_hashes'][str(generations)],predator_hidden=trial['checkpoint_hashes'][str(generations)])
    validate_cohorts(trial['training'])
    path = Path(models_dir) / f'seed-{seed}.npz'; save_models(path, trial, checkpoints)
    trial.update(model_file=str(path), model_sha256=file_digest(path), tests={})
    test_seed = derived_seed(f'step24:test:{seed}')
    cases = [(case_name(p, q), p, q, 'intact', 'intact') for p in checkpoints for q in checkpoints]
    cases.extend([('prey_hidden', generations, generations, 'hidden', 'intact'),
                  ('predator_hidden', generations, generations, 'intact', 'hidden')])
    for name, p, q, prey_sensors, predator_sensors in cases:
        bank = opponent_bank(checkpoints[p], checkpoints[q])
        w = PredatorPreyWorld(seed=test_seed, episode_seconds=episode_seconds, evolution_enabled=False, genomes=bank,
                             prey_sensors=prey_sensors, predator_sensors=predator_sensors)
        start = shared_layout_digest(w)
        if start in starts: raise RuntimeError('Held-out opponent tests reused a training layout.')
        s = EvolutionSimulation(w, generation_limit=1, auto_advance=False); complete_generation(s)
        if genome_bank_digest(current_bank(w)) != genome_bank_digest(bank): raise RuntimeError('Frozen opponent test modified its genomes.')
        trial['tests'][name] = {'predator_generation': p, 'prey_generation': q, 'seed': test_seed,
            'shared_layout_sha256': start, 'genomes_sha256': genome_bank_digest(bank), 'report': s.report()}
        if progress: print(f'Seed {seed}: frozen {name} complete', flush=True)
    return trial


def mean_defined(values):
    defined = [v for v in values if v is not None]
    return float(np.mean(defined)) if defined else None


def analyze_results(report):
    p, trials = report['protocol'], report['trials']
    seeds, generations = p['seeds'], p['generations']
    checkpoints = checkpoint_generations(generations)
    cases = {case_name(a, b): (a, b) for a in checkpoints for b in checkpoints}
    cases.update(prey_hidden=(generations, generations), predator_hidden=(generations, generations))
    if (len(seeds) < 2 or len(set(seeds)) != len(seeds) or len(trials) != len(seeds)
            or {t['seed'] for t in trials} != set(seeds) or p['configuration'] != CONFIG
            or p['checkpoints'] != checkpoints): raise ValueError('A complete declared coevolution study is required.')
    trials = sorted(trials, key=lambda t: seeds.index(t['seed']))
    training_starts = {start for t in trials for start in t['training_starts']}; test_starts = set()
    for trial in trials:
        data = trial['training']; validate_cohorts(data)
        eco = data['ecosystem']
        if (not data['evolution_enabled'] or data['seed'] != trial['seed'] or data['completed_generations'] != generations
                or eco['episode_seconds'] != p['episode_seconds'] or eco['opponent_sensors'] != {'prey': 'intact', 'predator': 'intact'}
                or len(eco['transitions']) != generations - 1 or len(trial['training_starts']) != generations
                or len(trial['training_physical_starts']) != generations
                or [h['shared_layout_sha256'] for h in eco['history']] != trial['training_starts']
                or {str(g): eco['history'][g-1]['genomes_sha256'] for g in checkpoints} != trial['checkpoint_hashes']
                or set(trial['test_genome_hashes']) != set(cases)
                or set(trial['tests']) != set(cases)):
            raise ValueError('Training and historical snapshots must retain both complete gene pools.')
        for i, trace in enumerate(eco['transitions'], 1):
            if trace['from_generation'] != i or trace['to_generation'] != i + 1 or set(trace['species']) != set(SPECIES): raise ValueError('Missing simultaneous transition.')
            for species, ids in (('prey', range(1,81)), ('predator', range(81,101))):
                transition = trace['species'][species]
                expected = sorted(eco['history'][i-1]['species'][species]['selected_ids'])
                expected_seeds = {kind:random.Random(f'step24:{kind}:{trial["seed"]}:{species}:generation:{i+1}').getrandbits(128) for kind in ('brain','body')}
                if (transition['parent_ids'] != expected or not set(expected).issubset(ids)
                        or transition['seeds'] != expected_seeds
                        or len(transition['offspring_parent_ids']) != len(ids)
                        or len(transition['brain_mutation_counts']) != len(ids) or len(transition['body_mutation_counts']) != len(ids)
                        or any(not 0<=n<=3 for n in transition['body_mutation_counts'])
                        or set(transition['offspring_parent_ids']) != set(expected)
                        or any(transition['offspring_parent_ids'].count(k) != 5 for k in expected)
                        or transition['brain_rng_calls'] != 1 + 8 * len(ids) or transition['body_rng_calls'] != 2 * len(ids)):
                    raise ValueError('Selection must stay within species with balanced linked inheritance.')
        starts = set()
        for name, (a, b) in cases.items():
            record = trial['tests'][name]; data = record['report']; validate_cohorts(data)
            eco = data['ecosystem']
            expected_modes = {'prey': 'hidden' if name == 'prey_hidden' else 'intact',
                              'predator': 'hidden' if name == 'predator_hidden' else 'intact'}
            if (record['predator_generation'] != a or record['prey_generation'] != b
                    or record['seed'] != derived_seed(f'step24:test:{trial["seed"]}') or data['seed'] != record['seed']
                    or data['evolution_enabled'] or data['completed_generations'] != 1 or eco['transitions']
                    or eco['episode_seconds'] != p['episode_seconds'] or eco['opponent_sensors'] != expected_modes
                    or eco['history'][0]['shared_layout_sha256'] != record['shared_layout_sha256']
                    or eco['history'][0]['genomes_sha256'] != record['genomes_sha256']
                    or record['genomes_sha256'] != trial['test_genome_hashes'][name]
                    or (a == b and record['genomes_sha256'] != trial['checkpoint_hashes'][str(a)])):
                raise ValueError('Historical tests require unchanged complete banks, matched worlds, and declared sensor modes.')
            starts.add(record['shared_layout_sha256'])
        if len(starts) != 1 or starts.intersection(training_starts | test_starts): raise ValueError('All eleven tests need a matched unseen scenario.')
        test_starts.update(starts)
    def cohort(t, a, b): return t['tests'][case_name(a,b)]['report']['ecosystem']['history'][0]
    def values(a,b,metric):
        return [cohort(t,a,b)['capture_fraction'] if metric == 'capture' else cohort(t,a,b)['species']['prey']['survival_rate'] for t in trials]
    last = generations
    definitions = {
        'predator_vs_founder_prey': (values(last,1,'capture'), values(1,1,'capture')),
        'prey_vs_founder_predators': (values(1,last,'survival'), values(1,1,'survival')),
        'predator_vs_final_prey': (values(last,last,'capture'), values(1,last,'capture')),
        'prey_vs_final_predators': (values(last,last,'survival'), values(last,1,'survival'))}
    primary = {name: paired_metrics(left,right,seed=derived_seed(f'step24:bootstrap:{name}')) for name,(left,right) in definitions.items()}
    classify_primary(list(primary.values()))
    descriptive = {}
    joint = [cohort(t,last,last) for t in trials]
    for role, metric in (('prey','survival_rate'), ('predator','capture_fraction')):
        masked = [t['tests'][f'{role}_hidden']['report']['ecosystem']['history'][0] for t in trials]
        intact = [c['species']['prey'][metric] if role == 'prey' else c[metric] for c in joint]
        hidden = [c['species']['prey'][metric] if role == 'prey' else c[metric] for c in masked]
        row = paired_metrics(intact,hidden,seed=derived_seed(f'step24:sensors:{role}')); row.pop('sign_test_p')
        descriptive[f'{role}_opponent_sensor_effect'] = row
    matrix = {metric: [[float(np.mean(values(a,b,metric))) for b in checkpoints] for a in checkpoints] for metric in ('capture','survival')}
    curve = []
    for i in range(generations):
        rows = [t['training']['ecosystem']['history'][i] for t in trials]
        curve.append({'generation': i + 1, 'capture_fraction': float(np.mean([c['capture_fraction'] for c in rows])),
            **{s: {metric: mean_defined([c['species'][s][metric] for c in rows]) for metric in (
                'survival_rate','mean_fitness','mean_age','mean_meals','away_fraction','toward_fraction')} for s in SPECIES},
            'birth_body_means': {s: np.mean([np.mean([c['body'] for c in row['creatures'] if c['species']==s],axis=0) for row in rows],axis=0).tolist() for s in SPECIES}})
    return {'independent_seed_groups': len(seeds), 'checkpoint_generations': checkpoints,
        'capture_fraction_matrix': matrix['capture'], 'prey_survival_matrix': matrix['survival'],
        'primary': primary, 'descriptive_sensor_interventions': descriptive, 'training': curve,
        'verdict': 'reciprocal_improvement_detected' if all(x['conclusion']=='higher' for x in primary.values()) else 'reciprocal_improvement_not_established',
        'interpretation': 'Historical-opponent gains can be consistent with reciprocal improvement. No frozen-opponent training control: they do not prove opponent-driven adaptation or a sustained evolutionary arms race.'}


def run_study(seeds=DEFAULT_SEEDS, *, generations=8, episode_seconds=60., workers=1, models_dir='.cache/predator-models', checkpoint=None, declare=None, progress=False):
    seeds = list(seeds); checkpoints = checkpoint_generations(generations)
    if len(seeds)<2 or len(set(seeds))!=len(seeds) or any(type(s) is not int for s in seeds) or type(workers) is not int or workers<1:
        raise ValueError('Use independent integer seeds and positive workers.')
    if any((Path(models_dir)/f'seed-{s}.npz').exists() for s in seeds): raise ValueError('Preserve existing archives.')
    # Validate the window even before protocol publication or expensive workers.
    if not np.isfinite(episode_seconds) or episode_seconds<=0 or not np.isclose(episode_seconds*60,round(episode_seconds*60),rtol=0,atol=1e-8): raise ValueError('Use a positive whole-tick evaluation window.')
    report={'format_version':1,'status':'running','protocol':{'seeds':seeds,'generations':generations,'checkpoints':checkpoints,
        'configuration':CONFIG,'episode_seconds':episode_seconds,'birth_counts':{'prey':80,'predator':20},
        'training_cohorts':len(seeds)*generations,'test_cohorts':len(seeds)*11,
        'brains':'11–8–2, 114 parameters plus three inherited body genes. Original eight inputs plus nearest opponent proximity, signed direction, visibility. Predators cannot sense or eat pellets. No chase/flee policy is programmed.',
        'physics':'Snapshot all inputs before any movement. Pay Step23 body costs first; fatal actors cannot hunt/eat. Reflective piecewise paths give earliest swept contact; each prey captured once, ties by prey then hunter ID. Captures resolve before prey meals. Removal, energy reward and age accounting occur at tick end; contact time also recorded. Each kill offers60 energy, capped by inherited storage.',
        'selection':'Separate top20% pools: prey age+10*meals; predators age+30*captures. Both offspring banks are formed from the same completed arena before either is installed. Linked brain/body inheritance, canonical independent species/brain/body RNG streams. Neural rate.1 scale.1; body rate.25 log scale.08.',
        'demography':'Fixed80 prey and20 predator births each generation. Live counts sampled every5s and at end; no within-window births. Censored survivors at horizon stay alive in reports. Dead genomes remain eligible. No reproductive resource budget, demographic extinction, or continuous population growth claim.',
        'tests':'Freeze entire evaluated birth banks at G1, midpoint, final. All nine historical predator/prey pairings plus final prey-opponent-hidden and final predator-opponent-hidden. Every case uses the same unseen anchors/food/heading/lifespan scenario per source seed, excluding all current training starts; actual treated genes/reserves differ. No selection during testing.',
        'primary':'Four directional improvements: final predators versus founders holding founder or final prey fixed (capture fraction); final prey versus founders holding founder or final predators fixed (alive-at-horizon fraction). Four exact paired two-sided sign tests with1e-10 ties and Holm. Directional verdict needs adjusted p<.05 and paired pointwise95% mean-difference interval excluding zero. Reciprocal improvement requires all four higher.',
        'intervals':'20000 paired percentile bootstrap resamples; independent source seed is the unit, never individual creatures.',
        'secondary':'Training fitness, 3x3 matrices, traits, population trajectories, away/toward movement, deaths, and two sensor interventions are descriptive. Sensor intervals have no confirmatory p-values. Away movement is relative to the nearest visible opponent and need not be deliberate escape.',
        'limitations':'Stylized energetic/capture assumptions. No frozen-opponent training or drift control. Reciprocal historical gains alone cannot establish that changing opponents caused adaptation, a sustained arms race, or ecological cycles. Lower capture rates alone can reflect prey starvation; primary prey success uses alive-at-horizon survival instead.'},'trials':[]}
    if declare:declare(report)
    if checkpoint:checkpoint(report)
    args=[(s,generations,episode_seconds,models_dir,progress) for s in seeds]
    if workers==1:
        for arg in args:
            report['trials'].append(run_lineage(*arg))
            if checkpoint:checkpoint(report)
    else:
        with ProcessPoolExecutor(max_workers=min(workers,len(seeds))) as executor:
            for future in as_completed([executor.submit(run_lineage,*a) for a in args]):
                report['trials'].append(future.result())
                if checkpoint:checkpoint(report)
    report['trials'].sort(key=lambda t:seeds.index(t['seed']));report['analysis']=analyze_results(report);report['status']='complete'
    if checkpoint:checkpoint(report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds',nargs='+',type=int,default=DEFAULT_SEEDS)
    parser.add_argument('--generations',type=positive_integer,default=8)
    parser.add_argument('--workers',type=positive_integer,default=1)
    parser.add_argument('--models-dir',type=Path,default=Path('.cache/predator-models'))
    parser.add_argument('--output',type=Path,default=Path('.cache/predators.json'))
    parser.add_argument('--protocol-output',type=Path,default=Path('.cache/predator-protocol.json'))
    args=parser.parse_args()
    if args.output.resolve()==args.protocol_output.resolve() or any(p.exists() or p.suffix!='.json' for p in (args.output,args.protocol_output)):parser.error('Use distinct new JSON output paths.')
    def write(r):
        args.output.parent.mkdir(parents=True,exist_ok=True);temp=args.output.with_suffix('.tmp.json');temp.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');temp.replace(args.output)
    def declare(r):
        args.protocol_output.parent.mkdir(parents=True,exist_ok=True)
        args.protocol_output.write_text(json.dumps({'declared_at_utc':datetime.now(timezone.utc).isoformat(),'protocol':r['protocol'],
            'source_sha256':{p.name:file_digest(p) for p in sorted(Path(__file__).resolve().parent.glob('*.py'))}},indent=2)+'\n')
    try:run_study(args.seeds,generations=args.generations,workers=args.workers,models_dir=args.models_dir,checkpoint=write,declare=declare,progress=True)
    except (ValueError,OSError) as error:parser.error(str(error))
    print(f'Predator–prey study complete: {args.output}');return 0


if __name__=='__main__':raise SystemExit(main())
