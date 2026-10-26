"""Paired individual/group survival selection and frozen social interventions."""

from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
import argparse
import json
from pathlib import Path
import random
from types import SimpleNamespace

import numpy as np

from body_traits import BodyTraits,WholeGenome,ENERGY_MODEL,genome_bank_digest,shared_layout_digest
from compare_creatures import complete_generation,derived_seed,initial_conditions_digest,positive_integer
from experiment_speed import classify_primary,paired_metrics
from experiment_strategy import file_digest
from social import (SocialWorld,new_social_brain,parent_plan,SENSOR_NAMES,SIGNAL_COST,
                    SHARE_RATE,SHARE_RANGE,SHARE_EFFICIENCY,DONOR_RESERVE)
from simulation import EvolutionSimulation


DEFAULT_SEEDS=tuple(range(2501,2509))
ARMS=('individual','group')
ENVIRONMENTS=('restricted','open')
CONDITIONS=('group','individual','group_no_sharing','founder','founder_no_sharing','group_signals_hidden')
ATTRIBUTES=('input_weights','hidden_bias','output_weights','output_bias')
SHAPES=((17,8),(8,),(8,3),(3,))
CONFIG={'arena_size':[1000,600],'population_size':100,'food_count':150,'fixed_speed':None,
        'controller':'neural','food_distribution':'uniform','food_sensor_mode':'intact',
        'mutation_rate':.1,'mutation_scale':.1}


def current_bank(world):
    return {c.creature_id:WholeGenome(c.brain.copy(),c.body) for c in [*world.creatures,*world.dead_creatures]}


def validate_cohorts(data,*,study=True):
    social=data['social'];rows=social['history'] if study else [r for r in social['history'] if r['complete']]
    population=data['population_size'];groups=social['groups'];size=social['group_size']
    if (len(rows)!=data['completed_generations'] or len(rows)!=len(data['generations']) or groups*size!=population
        or social['sensor_names']!=list(SENSOR_NAMES) or social['body']!=[60.,8.,160.] or social['energy_model']!=ENERGY_MODEL
        or any(social[k]!=v for k,v in {'signal_cost':SIGNAL_COST,'share_rate':SHARE_RATE,'share_range':SHARE_RANGE,
            'share_efficiency':SHARE_EFFICIENCY,'donor_reserve':DONOR_RESERVE}.items())
        or (study and (any(data[k]!=v for k,v in CONFIG.items()) or groups!=10 or size!=10))):
        raise ValueError('Social reports must match the declared fixed-body, equal-resource cohort.')
    for g,row in enumerate(rows,1):
        records=row['creatures'];lookup={c['creature_id']:c for c in records}
        expected_access=population if social['access']=='open' else groups*(size//2)
        if (not row['complete'] or row['generation']!=g or [c['creature_id'] for c in records]!=list(range(1,population+1))
            or not 0<row['duration']<=social['episode_seconds']+1e-7 or len(row['groups'])!=groups
            or [c['creature_id'] for c in records if c['can_feed']]!=row['food_access_ids'] or len(row['food_access_ids'])!=expected_access):
            raise ValueError('Every newborn, feeding role, and censored survivor must be retained.')
        for c in records:
            age=c['age'];spent=[c[k] for k in ('basal_energy','movement_energy','sensing_energy')]
            if (c['group_id']!=(c['creature_id']-1)//size or type(c['can_feed']) is not bool or not 0<=age<=row['duration']+1e-7
                or c['fitness']!=age or type(c['food_eaten']) is not int or c['food_eaten']<0 or (not c['can_feed'] and c['food_eaten'])
                or c['death_cause'] not in (None,'starvation','old_age') or c['alive_at_end']!=(c['death_cause'] is None)
                or (c['removed_at'] is None)!=c['alive_at_end']
                or (not c['alive_at_end'] and not age-1e-7<=c['removed_at']<=min(row['duration'],age+1/60)+1e-7)
                or (c['alive_at_end'] and not np.isclose(age,row['duration']))
                or not 0<=c['final_energy']<=100+1e-7 or c['initial_energy']!=90):
                raise ValueError('Invalid group membership, access, pure-survival fitness, or removal time.')
            ledgers=[c[k] for k in ('signal_energy','signal_integral','received_signal_integral','share_request_integral',
                                   'shared_out','shared_in','assimilated_energy','wasted_food_energy')]
            if (not np.all(np.isfinite(spent+ledgers)) or min(spent+ledgers)<-1e-7
                or not np.allclose(spent,np.array([2.,2.5,.5])*age,atol=1e-7)
                or not np.isclose(c['signal_energy'],SIGNAL_COST*c['signal_integral'],atol=1e-7)
                or max(c['signal_integral'],c['received_signal_integral'],c['share_request_integral'])>age+1e-7
                or not np.isclose(c['assimilated_energy']+c['wasted_food_energy'],20*c['food_eaten'],atol=1e-7)
                or not np.isclose(90+c['assimilated_energy']+c['shared_in']-sum(spent)-c['signal_energy']-c['shared_out'],c['final_energy'],atol=1e-7)
                or (not social['signaling'] and c['signal_energy']!=0)
                or (not social['sharing'] and (c['shared_out']!=0 or c['shared_in']!=0))):
                raise ValueError('Food, transfer, signal, and living-time ledgers must conserve energy.')
        edges=row['transfer_edges'];seen=set()
        for edge in edges:
            donor,recipient=lookup[edge['donor_id']],lookup[edge['recipient_id']];key=(edge['donor_id'],edge['recipient_id'])
            if (key in seen or donor is recipient or donor['group_id']!=recipient['group_id'] or edge['given']<=0
                or not np.isfinite(edge['given']) or not np.isclose(edge['received'],SHARE_EFFICIENCY*edge['given'],atol=1e-7)
                or type(edge['ticks']) is not int or edge['ticks']<1 or not 0<edge['last_time']<=row['duration']+1e-7):
                raise ValueError('Transfers must be positive, lossy, and confined to one group.')
            seen.add(key)
        for c in records:
            if (not np.isclose(c['shared_out'],sum(e['given'] for e in edges if e['donor_id']==c['creature_id']),atol=1e-7)
                or not np.isclose(c['shared_in'],sum(e['received'] for e in edges if e['recipient_id']==c['creature_id']),atol=1e-7)):
                raise ValueError('Actor and edge transfer ledgers disagree.')
        for group,summary in enumerate(row['groups']):
            members=[c for c in records if c['group_id']==group]
            if (summary['group_id']!=group or len(members)!=size or summary['alive_at_end']!=sum(c['alive_at_end'] for c in members)
                or summary['survival_rate']!=summary['alive_at_end']/size
                or not np.isclose(summary['mean_age'],np.mean([c['age'] for c in members]))
                or not np.isclose(summary['shared_out'],sum(c['shared_out'] for c in members),atol=1e-7)
                or not np.isclose(summary['shared_in'],SHARE_EFFICIENCY*summary['shared_out'],atol=1e-7)
                or sum(c['can_feed'] for c in members)!=(size if social['access']=='open' else size//2)):
                raise ValueError('Each complete group needs its own observed survival, roles, and transfer balance.')
        if (not np.isclose(row['mean_age'],np.mean([c['age'] for c in records]))
            or row['survival_rate']!=sum(c['alive_at_end'] for c in records)/population
            or not np.isclose(row['shared_out'],sum(c['shared_out'] for c in records),atol=1e-7)
            or not np.isclose(row['shared_in'],SHARE_EFFICIENCY*row['shared_out'],atol=1e-7)
            or not np.isclose(row['signal_energy'],sum(c['signal_energy'] for c in records),atol=1e-7)):
            raise ValueError('Cohort outcomes must retain all groups and individuals.')
        timeline=row['population']
        if timeline[0]!={'time':0.,'alive':[size]*groups} or timeline[-1]['time']!=row['duration']:
            raise ValueError('Population traces must include birth and evaluation end.')
        if any(not 0<=a['time']<b['time']<=row['duration'] for a,b in zip(timeline,timeline[1:])):
            raise ValueError('Population observations must have increasing times.')
        for point in timeline:
            expected=[size-sum(c['group_id']==group and c['removed_at'] is not None and c['removed_at']<=point['time']+1e-7 for c in records) for group in range(groups)]
            if point['alive']!=expected:raise ValueError('Population counts must use actual removal ticks.')


def validate_training(trial,generations):
    starts=set()
    for arm in ARMS:
        data=trial['training'][arm];validate_cohorts(data);profile=data['social']
        if (data['seed']!=trial['seed'] or not data['evolution_enabled'] or data['completed_generations']!=generations
            or profile['selection_level']!=arm or profile['access']!='restricted' or not profile['signaling'] or not profile['sharing'] or profile['signals_hidden']
            or len(profile['transitions'])!=generations-1 or len(trial['training_starts'][arm])!=generations
            or len(trial['training_physical_starts'][arm])!=generations
            or [r['shared_layout_sha256'] for r in profile['history']]!=trial['training_starts'][arm]
            or profile['history'][0]['genomes_sha256']!=trial['genome_hashes']['founder']
            or profile['history'][-1]['genomes_sha256']!=trial['genome_hashes'][arm]):
            raise ValueError('Both policies must train complete matched cohorts from the same founders.')
        starts.update(trial['training_starts'][arm])
        for g,trace in enumerate(profile['transitions'],1):
            slot_seed=random.Random(f'step25:slots:{trial["seed"]}:generation:{g+1}').getrandbits(128)
            mutation_seed=random.Random(f'step25:brain-mutation:{trial["seed"]}:generation:{g+1}').getrandbits(128)
            records=[SimpleNamespace(**c) for c in profile['history'][g-1]['creatures']]
            plan=parent_plan(records,arm,10,10,slot_seed)
            if (trace['from_generation']!=g or trace['to_generation']!=g+1 or trace['slot_seed']!=slot_seed or trace['mutation_seed']!=mutation_seed
                or any(trace[k]!=v for k,v in plan.items()) or trace['mutation_rng_calls']!=800
                or len(trace['offspring_mutation_counts'])!=100 or len(trace['parent_ids'])!=20
                or any(trace['offspring_parent_ids'].count(k)!=5 for k in trace['parent_ids'])):
                raise ValueError('Selection, team assortment, and balanced offspring must follow the declared policy.')
    if trial['training_starts']['individual']!=trial['training_starts']['group']:
        raise ValueError('Paired policies must share physical training layouts.')
    if ([r['food_access_ids'] for r in trial['training']['individual']['social']['history']]
            !=[r['food_access_ids'] for r in trial['training']['group']['social']['history']]):
        raise ValueError('Access roles must match in every paired training generation.')
    if trial['training']['individual']['social']['history'][0]!=trial['training']['group']['social']['history'][0]:
        raise ValueError('Identical founders must yield identical first cohorts.')
    for a,b in zip(trial['training']['individual']['social']['transitions'],trial['training']['group']['social']['transitions']):
        if any(a[k]!=b[k] for k in ('mutation_seed','mutation_draws_sha256','mutation_rng_calls','offspring_mutation_counts')):
            raise ValueError('Per-child mutation streams and budgets must match across selection policies.')
    return starts


def save_models(path,metadata,banks):
    path=Path(path)
    if path.exists():raise ValueError('Preserve existing social populations.')
    arrays={'ids':np.arange(1,101),'metadata':np.array(json.dumps(metadata,allow_nan=False))}
    for name,bank in banks.items():
        for i,attribute in enumerate(ATTRIBUTES):arrays[f'{name}_{i}']=np.stack([getattr(bank[k].brain,attribute) for k in range(1,101)])
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp.npz');np.savez_compressed(temp,**arrays);temp.replace(path)


def load_models(path,seed,generations):
    with np.load(path,allow_pickle=False) as archive:
        metadata=json.loads(str(archive['metadata'].item()))
        if metadata['seed']!=seed or archive['ids'].tolist()!=list(range(1,101)):raise ValueError('Social model IDs or seed changed.')
        validate_training(metadata,generations);banks={}
        for name in ('founder',*ARMS):
            arrays=[archive[f'{name}_{i}'] for i in range(4)]
            if any(a.shape!=(100,*shape) or not np.all(np.isfinite(a)) for a,shape in zip(arrays,SHAPES)):
                raise ValueError('Social archives require finite 17–8–3 parameters.')
            bank={}
            for i in range(100):
                brain=new_social_brain(np.random.default_rng(0))
                for attribute,array in zip(ATTRIBUTES,arrays):setattr(brain,attribute,array[i].copy())
                bank[i+1]=WholeGenome(brain,BodyTraits())
            if genome_bank_digest(bank)!=metadata['genome_hashes'][name]:raise ValueError('Social model hash changed.')
            banks[name]=bank
    return metadata,banks


def run_lineage(seed,generations,episode_seconds,models_dir,progress=False):
    worlds={a:SocialWorld(seed=seed,selection_level=a,episode_seconds=episode_seconds) for a in ARMS}
    sims={a:EvolutionSimulation(w,generation_limit=generations,auto_advance=False) for a,w in worlds.items()}
    banks={'founder':current_bank(worlds['group'])};starts={a:[] for a in ARMS};physical={a:[] for a in ARMS}
    for g in range(1,generations+1):
        for arm in ARMS:
            starts[arm].append(shared_layout_digest(worlds[arm]));physical[arm].append(initial_conditions_digest(worlds[arm]));complete_generation(sims[arm])
        if starts['individual'][-1]!=starts['group'][-1] or physical['individual'][-1]!=physical['group'][-1]:raise RuntimeError('Training physical starts differ.')
        if progress:print(f'Seed {seed}: both social selection policies completed G{g}/{generations}',flush=True)
        if g<generations:
            for arm in ARMS:
                if not sims[arm].advance_generation():raise RuntimeError('Social reproduction failed.')
    banks.update({a:current_bank(w) for a,w in worlds.items()})
    trial={'seed':seed,'training':{a:s.report() for a,s in sims.items()},'training_starts':starts,'training_physical_starts':physical,
           'genome_hashes':{name:genome_bank_digest(bank) for name,bank in banks.items()}}
    validate_training(trial,generations);path=Path(models_dir)/f'seed-{seed}.npz';save_models(path,trial,banks)
    trial.update(model_file=str(path),model_sha256=file_digest(path),tests={})
    for environment in ENVIRONMENTS:
        test_seed=derived_seed(f'step25:test:{seed}:{environment}');trial['tests'][environment]={}
        for condition in CONDITIONS:
            source='founder' if condition.startswith('founder') else 'individual' if condition=='individual' else 'group'
            w=SocialWorld(seed=test_seed,episode_seconds=episode_seconds,access=environment,evolution_enabled=False,genomes=banks[source],
                sharing=not condition.endswith('no_sharing'),signals_hidden=condition.endswith('signals_hidden'))
            start=shared_layout_digest(w)
            if start in starts['group']:raise RuntimeError('A test layout was used in training.')
            s=EvolutionSimulation(w,generation_limit=1,auto_advance=False);complete_generation(s)
            if genome_bank_digest(current_bank(w))!=genome_bank_digest(banks[source]):raise RuntimeError('Testing changed frozen genes.')
            trial['tests'][environment][condition]={'seed':test_seed,'shared_layout_sha256':start,'genomes_sha256':genome_bank_digest(banks[source]),'report':s.report()}
        if progress:print(f'Seed {seed}: all six frozen {environment} comparisons complete',flush=True)
    return trial


def mean_defined(values):
    available=[v for v in values if v is not None]
    return float(np.mean(available)) if available else None


def observations(row):
    records=row['creatures'];living=sum(c['age'] for c in records)
    received=sum(c['received_signal_integral'] for c in records)
    return {'mean_age':row['mean_age'],'survival_rate':row['survival_rate'],'shared_received_per_birth':row['shared_in']/len(records),
        'signal_power_per_living_second':row['signal_energy']/living,
        'mean_received_signal':received/living,'mean_meals':np.mean([c['food_eaten'] for c in records]).item(),
        'dependent_mean_age':mean_defined([c['age'] for c in records if not c['can_feed']])}


def analyze_results(report):
    p,trials=report['protocol'],report['trials'];seeds=p['seeds'];generations=p['generations']
    if (len(seeds)<2 or len(set(seeds))!=len(seeds) or len(trials)!=len(seeds) or {t['seed'] for t in trials}!=set(seeds)
        or p['configuration']!=CONFIG or p['conditions']!=list(CONDITIONS) or p['environments']!=list(ENVIRONMENTS)):
        raise ValueError('A complete declared social comparison is required.')
    trials=sorted(trials,key=lambda t:seeds.index(t['seed']));training=set();seen=set()
    for t in trials:training.update(validate_training(t,generations))
    for t in trials:
        if set(t['tests'])!=set(ENVIRONMENTS):raise ValueError('Both resource-access environments are required.')
        for environment,cases in t['tests'].items():
            if set(cases)!=set(CONDITIONS):raise ValueError('Missing frozen social intervention.')
            starts=set();access_ids=None
            for condition,record in cases.items():
                data=record['report'];validate_cohorts(data);social=data['social'];source='founder' if condition.startswith('founder') else 'individual' if condition=='individual' else 'group'
                if (record['seed']!=derived_seed(f'step25:test:{t["seed"]}:{environment}') or data['seed']!=record['seed'] or data['evolution_enabled']
                    or data['completed_generations']!=1 or social['transitions'] or social['access']!=environment
                    or social['episode_seconds']!=p['episode_seconds'] or not social['signaling']
                    or social['sharing']!= (not condition.endswith('no_sharing')) or social['signals_hidden']!=condition.endswith('signals_hidden')
                    or record['genomes_sha256']!=t['genome_hashes'][source] or social['history'][0]['genomes_sha256']!=record['genomes_sha256']
                    or social['history'][0]['shared_layout_sha256']!=record['shared_layout_sha256']):
                    raise ValueError('Tests must freeze complete models with declared physical and information interventions.')
                starts.add(record['shared_layout_sha256']);ids=social['history'][0]['food_access_ids']
                if access_ids is not None and ids!=access_ids:raise ValueError('Feeding access must be matched across conditions.')
                access_ids=ids
            if len(starts)!=1 or starts.intersection(training|seen):raise ValueError('Tests need matched unseen scenarios across every condition.')
            seen.update(starts)
    analysis={'independent_seed_groups':len(seeds),'environments':{},'training':[]};primary=[]
    for env in ENVIRONMENTS:
        values={c:[observations(t['tests'][env][c]['report']['social']['history'][0]) for t in trials] for c in CONDITIONS}
        ages={c:[r['mean_age'] for r in rows] for c,rows in values.items()}
        final_benefit=np.array(ages['group'])-ages['group_no_sharing'];founder_benefit=np.array(ages['founder'])-ages['founder_no_sharing']
        comparisons={
            'group_vs_individual':paired_metrics(ages['group'],ages['individual'],seed=derived_seed(f'step25:bootstrap:{env}:selection')),
            'final_sharing_benefit':paired_metrics(ages['group'],ages['group_no_sharing'],seed=derived_seed(f'step25:bootstrap:{env}:sharing')),
            'evolved_sharing_gain':paired_metrics(final_benefit,founder_benefit,seed=derived_seed(f'step25:bootstrap:{env}:evolution'))}
        primary.extend(comparisons.values())
        signaling=paired_metrics(ages['group'],ages['group_signals_hidden'],seed=derived_seed(f'step25:signals:{env}'));signaling.pop('sign_test_p')
        analysis['environments'][env]={'primary':comparisons,'descriptive_signal_information_effect':signaling,
            'seed_values':values,'condition_means':{c:{metric:mean_defined([r[metric] for r in rows]) for metric in rows[0]} for c,rows in values.items()},
            'descriptive_counts':{c:{metric:sum(r[metric] is not None for r in rows) for metric in rows[0]} for c,rows in values.items()}}
    classify_primary(primary)
    for g in range(generations):
        analysis['training'].append({'generation':g+1,**{arm:{metric:mean_defined([observations(t['training'][arm]['social']['history'][g])[metric] for t in trials])
            for metric in observations(trials[0]['training'][arm]['social']['history'][g])} for arm in ARMS}})
    restricted=analysis['environments']['restricted']['primary']
    analysis['verdict']='evolved_beneficial_cooperation_detected' if all(row['conclusion']=='higher' for row in restricted.values()) else 'evolved_beneficial_cooperation_not_established'
    return analysis


def run_study(seeds=DEFAULT_SEEDS,*,generations=8,episode_seconds=60.,workers=1,models_dir='.cache/social-models',progress=False,checkpoint=None,declare=None):
    seeds=list(seeds)
    if len(seeds)<2 or len(set(seeds))!=len(seeds) or any(type(s) is not int for s in seeds) or type(generations) is not int or generations<2 or type(workers) is not int or workers<1:
        raise ValueError('Use independent integer seeds, at least two generations, and positive workers.')
    if not np.isfinite(episode_seconds) or episode_seconds<=0 or not np.isclose(episode_seconds*60,round(episode_seconds*60),rtol=0,atol=1e-8):raise ValueError('Use a positive whole-tick evaluation window.')
    if any((Path(models_dir)/f'seed-{s}.npz').exists() for s in seeds):raise ValueError('Preserve existing social archives.')
    report={'format_version':1,'status':'running','protocol':{'seeds':seeds,'generations':generations,'configuration':CONFIG,'conditions':list(CONDITIONS),
        'environments':list(ENVIRONMENTS),'episode_seconds':episode_seconds,'training_cohorts':len(seeds)*generations*2,'test_cohorts':len(seeds)*12,
        'groups':'Ten isolated groups of ten in equal200x300 cells. Each receives15 maintained food pellets. Fixed reference bodies, cruise60, 17–8–3 networks with171 parameters; output turn, positive signal effort, positive sharing effort. No trained legacy models reused.',
        'access':'Training restricts plant access to five randomly assigned members per group, independently redrawn each generation and matched across arms. All members sense their own access flag. This deliberately creates a need for redistribution; it is not an unrestricted natural ecology. Tests compare restricted and open access.',
        'social_physics':'Nearest local neighbor proximity, signed bearing, visibility, hunger; strongest attenuated prior-tick signal and bearing; density; own food access. All decisions use a common position/energy/signal snapshot. Signal costs.2*effort per living second. Positive sharing offers at most12*effort energy/s to the nearest living same-group neighbor within48px. Reserve10; efficiency.8; cap recipient room, proportionally scale competing gifts. Post-food pre-transfer snapshots prevent forwarding newly received gifts in the same tick. Sharing includes initial stored reserves as well as food-derived energy.',
        'selection':'Individual: top20 actors by actual age, balanced five children each, mixed among teams. Group: top2 group mean ages, clone each complete ten-member team five times with member permutations. Both select20 parent genomes and make100 offspring; neural mutation.1 probability/.1 Gaussian scale. Common per-child mutation stream, separate assignment RNG. Bodies fixed. Group policy changes incentives AND assortment.',
        'demography':'Finite60s windows; censored survivors remain alive. All newborns, including dead genomes, retained for selection. No within-window reproduction or permanent demographic extinction claim. Selection score is age only; no reward for transfers, signals, or meals.',
        'tests':'Freeze full final evaluated birth banks without an extra reproduction and retain original founders. Six cases per access environment: group, individual, group sharing blocked, founder, founder sharing blocked, group received signals hidden. All six match layout, food, heading, lifespan and access roles; every new scenario excluded from all current training starts. No evolution during testing.',
        'primary':'Six paired mean-age tests: group versus individual, final group sharing benefit, and final sharing benefit minus founder sharing benefit, each in restricted/open tests. Exact two-sided sign tests,1e-10 ties, Holm across all six. Direction requires adjusted p<.05 and paired pointwise95% mean-difference interval excluding zero. Evolved beneficial cooperation requires all three restricted contrasts higher.',
        'intervals':'20000 paired percentile bootstrap resamples; source seed is independent unit, never members or descendant teams.',
        'secondary':'Horizon survival, dependent survival, food, emitted/received signal measures, actual transfers, and signal-mask intervals are descriptive. Undefined dependent means in open access remain missing. No confirmatory signal p-value.',
        'limitations':'Stylized access restriction and lossy stored-energy transfer. Group selection is bundled with preserved team assortment. No drift training control. More sharing alone is not evidence of cooperation; final benefit must exceed both blocked sharing and founder benefit. Local neighbor hunger is directly observable, so signals may be redundant. Results do not establish reciprocal intent, language, unrestricted ecological cooperation, or a general evolutionary law.'},'trials':[]}
    if declare:declare(report)
    if checkpoint:checkpoint(report)
    args=[(s,generations,episode_seconds,models_dir,progress) for s in seeds]
    if workers==1:
        for arg in args:
            report['trials'].append(run_lineage(*arg))
            if checkpoint:checkpoint(report)
    else:
        with ProcessPoolExecutor(max_workers=min(workers,len(seeds))) as executor:
            for future in as_completed([executor.submit(run_lineage,*arg) for arg in args]):
                report['trials'].append(future.result())
                if checkpoint:checkpoint(report)
    report['trials'].sort(key=lambda t:seeds.index(t['seed']));report['analysis']=analyze_results(report);report['status']='complete'
    if checkpoint:checkpoint(report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seeds',nargs='+',type=int,default=DEFAULT_SEEDS)
    parser.add_argument('--generations',type=positive_integer,default=8);parser.add_argument('--workers',type=positive_integer,default=1)
    parser.add_argument('--models-dir',type=Path,default=Path('.cache/social-models'));parser.add_argument('--output',type=Path,default=Path('.cache/social.json'))
    parser.add_argument('--protocol-output',type=Path,default=Path('.cache/social-protocol.json'));args=parser.parse_args()
    if args.output.resolve()==args.protocol_output.resolve() or any(p.exists() or p.suffix!='.json' for p in (args.output,args.protocol_output)):parser.error('Use distinct new JSON paths.')
    def write(r):
        args.output.parent.mkdir(parents=True,exist_ok=True);temp=args.output.with_suffix('.tmp.json');temp.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');temp.replace(args.output)
    def declare(r):
        args.protocol_output.parent.mkdir(parents=True,exist_ok=True);args.protocol_output.write_text(json.dumps({'declared_at_utc':datetime.now(timezone.utc).isoformat(),'protocol':r['protocol'],
            'source_sha256':{p.name:file_digest(p) for p in sorted(Path(__file__).resolve().parent.glob('*.py'))}},indent=2)+'\n')
    try:run_study(args.seeds,generations=args.generations,workers=args.workers,models_dir=args.models_dir,progress=True,checkpoint=write,declare=declare)
    except (ValueError,OSError) as error:parser.error(str(error))
    print(f'Social comparison complete: {args.output}');return 0


if __name__=='__main__':raise SystemExit(main())
