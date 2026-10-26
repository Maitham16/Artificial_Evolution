"""Repeated resource/mutation conditions in a continuously renewing population."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
import argparse
import gzip
import json
from pathlib import Path

import numpy as np

from brain import NeuralNetwork
from body_traits import BodyTraits,WholeGenome,genome_bank_digest
from ecosystem import ContinuousWorld,ContinuousSimulation,diversity_metrics
from experiment_strategy import file_digest
from compare_creatures import positive_integer


DEFAULT_SEEDS=tuple(range(2601,2609))
RESOURCES={'abundant':{'food_count':150,'regrowth_rate':30.},'scarce':{'food_count':50,'regrowth_rate':6.}}
ARMS=('mutating','clonal')
ATTRIBUTES=('input_weights','hidden_bias','output_weights','output_bias')
SHAPES=((8,8),(8,),(8,2),(2,))


def validate_run(report):
    births=report['births'];individuals=report['individuals'];n=report['initial_population'];end=report['elapsed_seconds']
    if (report['mode']!='continuous' or len(births)!=len(individuals) or len(births)<n
        or [r['creature_id'] for r in births]!=list(range(1,len(births)+1))
        or [r['creature_id'] for r in individuals]!=list(range(1,len(births)+1))
        or end>report['duration_limit']+1e-7):raise ValueError('Every founder and descendant must retain one unique lifetime record.')
    by_id={c['creature_id']:c for c in individuals};born={c['creature_id']:c for c in births}
    for birth,c in zip(births,individuals):
        key=birth['creature_id'];body=BodyTraits.from_vector(birth['body']);parent=birth['parent_id']
        if (c['alive']!=(c['removed_at'] is None) or c['alive']!=(c['death_cause'] is None)
            or not 0<=c['age']<=birth['lifespan']+1e-7 or c['age']>end-birth['born_at']+1e-7
            or not -1e-7<=c['energy']<=body.capacity+1e-7
            or (not c['alive'] and not c['age']-1e-7<=c['removed_at']-birth['born_at']<=c['age']+1/60+1e-7)
            or (c['alive'] and not np.isclose(c['age'],end-birth['born_at'],atol=1e-7))
            or c['death_cause'] not in (None,'starvation','old_age')):raise ValueError('Invalid lifetime, censoring, capacity, or removal time.')
        if key<=n:
            if parent is not None or birth['founder_id']!=key or birth['depth']!=0 or birth['born_at']!=0 or birth['initial_energy']!=body.initial_energy:
                raise ValueError('Founders must enter only at time zero.')
        else:
            if (type(parent) is not int or not 1<=parent<key or birth['founder_id']!=born[parent]['founder_id']
                or birth['depth']!=born[parent]['depth']+1 or birth['born_at']<=born[parent]['born_at']
                or birth['born_at']-born[parent]['born_at']+1e-7<report['maturity_age']
                or birth['initial_energy']!=.4*body.capacity):raise ValueError('Descendants must have a mature, earlier parent and funded endowment.')
        costs=[c[k] for k in ('basal_energy','movement_energy','sensing_energy')]
        if (not np.allclose(costs,np.array(body.powers())*c['age'],atol=1e-7)
            or min(costs+[c['assimilated_energy'],c['wasted_food_energy'],c['reproduction_energy']])< -1e-7
            or not np.isclose(c['assimilated_energy']+c['wasted_food_energy'],20*c['food_eaten'],atol=1e-7)
            or not np.isclose(birth['initial_energy']+c['assimilated_energy']-sum(costs)-c['reproduction_energy'],c['energy'],atol=1e-7)):
            raise ValueError('Individual food, maintenance, and reproductive energy must balance.')
    successful=[];attempt_counts={};last={};costs={};children={}
    for index,event in enumerate(report['attempts'],1):
        parent=event['parent_id'];attempt_counts[parent]=attempt_counts.get(parent,0)+1
        if (event['attempt_id']!=index or event['parent_attempt']!=attempt_counts[parent] or parent not in born
            or not born[parent]['born_at']+report['maturity_age']-1e-7<=event['time']<=end+1e-7
            or event['time']-last.get(parent,-1e30)+1e-7<report['birth_cooldown']
            or event['status'] not in ('born','energy','space','capacity')
            or (by_id[parent]['removed_at'] is not None and event['time']>=by_id[parent]['removed_at']-1e-7)):
            raise ValueError('Reproduction attempts require a living mature parent and cooldown.')
        last[parent]=event['time']
        if event['status']!='capacity':
            body=BodyTraits.from_vector(event['candidate_body'])
            if not np.isclose(event['cost'],.55*body.capacity):raise ValueError('Each candidate must include endowment, development, and overhead.')
        if event['status']=='born':
            child=born[event['child_id']];successful.append(event['child_id'])
            if (child['parent_id']!=parent or child['born_at']!=event['time'] or child['body']!=event['candidate_body']
                or child['genome_sha256']!=event['candidate_genome_sha256']
                or not np.isclose(event['parent_energy_before']-event['cost'],event['parent_energy_after'])
                or event['parent_energy_after']+1e-7<.25*BodyTraits.from_vector(born[parent]['body']).capacity):
                raise ValueError('Every birth must debit its parent and preserve the parent reserve.')
            costs[parent]=costs.get(parent,0.)+event['cost'];children[parent]=children.get(parent,0)+1
        elif event['child_id'] is not None:raise ValueError('Failed attempts cannot create descendants.')
    if successful!=list(range(n+1,len(births)+1)):raise ValueError('No unrecorded, duplicate, or immigrant births are allowed.')
    for c in individuals:
        if not np.isclose(c['reproduction_energy'],costs.get(c['creature_id'],0.),atol=1e-7) or c['children']!=children.get(c['creature_id'],0):raise ValueError('Parent reproductive totals disagree with births.')
    timeline=report['snapshots']
    if timeline[0]['time']!=0 or timeline[-1]['time']!=end or any(a['time']>=b['time'] for a,b in zip(timeline,timeline[1:])):raise ValueError('Snapshots require increasing times and both endpoints.')
    for row in timeline:
        active=[b for b in births if b['born_at']<=row['time']+1e-7 and (by_id[b['creature_id']]['removed_at'] is None or by_id[b['creature_id']]['removed_at']>row['time']+1e-7)]
        families={str(k):sum(c['founder_id']==k for c in active) for k in sorted({c['founder_id'] for c in active})}
        if (row['population']!=len(active) or row['population']>report['population_cap'] or row['family_counts']!=families
            or row['births']!=sum(b['parent_id'] is not None and b['born_at']<=row['time']+1e-7 for b in births)
            or row['deaths']!=sum(c['removed_at'] is not None and c['removed_at']<=row['time']+1e-7 for c in individuals)
            or row['population']!=n+row['births']-row['deaths']):raise ValueError('Population and ancestry counts must follow actual event times.')
    if (report['food_remaining']!=report['food_capacity']+report['food_regrown']-report['food_eaten']
        or report['food_eaten']!=sum(c['food_eaten'] for c in individuals)
        or (report['extinct_at'] is not None and (timeline[-1]['population']!=0 or report['extinct_at']!=end))):raise ValueError('Food regeneration or extinction accounting disagrees.')
    founder_energy=sum(b['initial_energy'] for b in births[:n]);food=sum(c['assimilated_energy'] for c in individuals)
    spent=sum(sum(c[k] for k in ('basal_energy','movement_energy','sensing_energy')) for c in individuals)
    birth_losses=sum(.15*BodyTraits.from_vector(b['body']).capacity for b in births[n:])
    remaining=sum(c['energy'] for c in individuals)
    if not np.isclose(founder_energy+food-spent-birth_losses,remaining,atol=1e-6):raise ValueError('Global energy accounting must exclude transferred child endowments from new input.')


def summarize(report):
    validate_run(report);last=report['snapshots'][-1];duration=report['duration_limit']
    late=sum(b['parent_id'] is not None and b['born_at']>=duration-120 for b in report['births'])
    depth=max(b['depth'] for b in report['births'])
    persistent=(report['extinct_at'] is None and report['elapsed_seconds']+1e-7>=duration and duration>=240
                and last['population']>0 and last['living_founders']==0 and late>0 and depth>=3)
    return {'final_population':last['population'],'births':last['births'],'deaths':last['deaths'],'extinct_at':report['extinct_at'],
        'max_depth_ever':depth,'max_living_depth':last['max_living_depth'],'living_families':len(last['family_counts']),
        'effective_families':last['effective_families'],'genetic_rms':last['genetic_rms'],'within_family_rms':last['within_family_rms'],
        'genetic_clusters':last['genetic_clusters'],'within_family_clusters':last['within_family_clusters'],
        'late_births':late,'finite_window_persistence':persistent,'attempts':len(report['attempts']),
        'blocked_attempts':{status:sum(e['status']==status for e in report['attempts']) for status in ('capacity','space','energy')}}


def save_archive(path,world,report_hash):
    path=Path(path)
    if path.exists():raise ValueError('Preserve existing lifetime genomes.')
    bank=world.bank();ids=sorted(bank);arrays={'ids':np.array(ids),
        'metadata':np.array(json.dumps({'seed':world.seed,'report_sha256':report_hash,'genomes_sha256':genome_bank_digest(bank)})),
        'bodies':np.stack([bank[k].body.vector() for k in ids])}
    for i,key in enumerate(ATTRIBUTES):arrays[f'brain_{i}']=np.stack([getattr(bank[k].brain,key) for k in ids])
    path.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(path,**arrays)


def load_archive(path,report):
    with np.load(path,allow_pickle=False) as a:
        metadata=json.loads(str(a['metadata'].item()));ids=a['ids'].tolist();count=len(report['births'])
        if metadata['seed']!=report['seed'] or ids!=list(range(1,count+1)) or a['bodies'].shape!=(count,3):raise ValueError('Lifetime genome IDs, seed, or body dimensions changed.')
        arrays=[a[f'brain_{i}'] for i in range(4)]
        if any(x.shape!=(count,*shape) or not np.all(np.isfinite(x)) for x,shape in zip(arrays,SHAPES)):raise ValueError('Invalid lifetime neural arrays.')
        bank={}
        for i,key in enumerate(ids):
            brain=object.__new__(NeuralNetwork)
            for name,x in zip(ATTRIBUTES,arrays):setattr(brain,name,x[i].copy())
            body=BodyTraits.from_vector(a['bodies'][i]);bank[key]=WholeGenome(brain,body)
            birth=report['births'][i]
            if birth['body']!=body.vector().tolist() or birth['genome_sha256']!=genome_bank_digest({0:bank[key]}):raise ValueError('A birth genotype does not match its numeric archive.')
        if genome_bank_digest(bank)!=metadata['genomes_sha256'] or metadata['genomes_sha256']!=report['all_genomes_sha256']:raise ValueError('Lifetime genome digest changed.')
    return metadata,bank


def load_run(record):
    if file_digest(record['report_file'])!=record['report_sha256']:raise ValueError('Compressed lifetime report checksum changed.')
    with gzip.open(record['report_file'],'rt') as stream:report=json.load(stream)
    validate_run(report)
    if summarize(report)!=record['summary'] or report['snapshots']!=record['snapshots']:raise ValueError('Stored ecological summary disagrees with its full events.')
    return report


def run_seed(seed,duration,output_dir,progress=False):
    trial={'seed':seed,'runs':{}}
    for resource,config in RESOURCES.items():
        trial['runs'][resource]={};paired=None
        for arm in ARMS:
            rates={} if arm=='mutating' else {'mutation_rate':0.,'body_mutation_rate':0.}
            world=ContinuousWorld(seed=seed,**config,**rates)
            start=(world.initial_layout,world.founder_genomes_hash)
            if paired is not None and paired!=start:raise RuntimeError('Mutation controls must share founders and initial habitat.')
            paired=start;s=ContinuousSimulation(world,duration=duration)
            last=0
            while not s.finished:
                s.update(1.)
                if progress and int(world.elapsed_time)//120>last:
                    last=int(world.elapsed_time)//120;print(f'Seed {seed}: {resource}/{arm}, {world.elapsed_time:.0f}/{duration:g}s',flush=True)
            report=s.report();summary=summarize(report)
            prefix=Path(output_dir)/f'seed-{seed}-{resource}-{arm}';raw=prefix.with_suffix('.json.gz');model=prefix.with_suffix('.npz')
            if raw.exists() or model.exists():raise ValueError('Preserve existing ecosystem records.')
            raw.parent.mkdir(parents=True,exist_ok=True)
            with gzip.GzipFile(filename=str(raw),mode='wb',mtime=0) as stream:stream.write(json.dumps(report,separators=(',',':'),allow_nan=False).encode())
            digest=file_digest(raw);save_archive(model,world,digest)
            sensitivity={str(t):diversity_metrics(world.creatures,t)['genetic_clusters'] for t in (.15,.25,.5)}
            trial['runs'][resource][arm]={'report_file':str(raw),'report_sha256':digest,'models_file':str(model),'models_sha256':file_digest(model),
                'initial_layout_sha256':world.initial_layout,'founder_genomes_sha256':world.founder_genomes_hash,
                'summary':summary,'snapshots':report['snapshots'],'cluster_threshold_sensitivity':sensitivity}
            if progress:print(f'Seed {seed}: {resource}/{arm} complete, raw events and genomes saved',flush=True)
    return trial


def analyze_results(report,verify_files=True):
    p=report['protocol'];trials=report['trials'];seeds=p['seeds']
    if len(seeds)<2 or len(set(seeds))!=len(seeds) or len(trials)!=len(seeds) or {t['seed'] for t in trials}!=set(seeds) or p['resources']!=RESOURCES or p['arms']!=list(ARMS):raise ValueError('Use the complete declared ecosystem study.')
    for trial in trials:
        if set(trial['runs'])!=set(RESOURCES):raise ValueError('Missing resource condition.')
        for resource,runs in trial['runs'].items():
            if set(runs)!=set(ARMS):raise ValueError('Missing mutation control.')
            if any(runs['mutating'][k]!=runs['clonal'][k] for k in ('initial_layout_sha256','founder_genomes_sha256')):raise ValueError('Unmatched initial ecosystem controls.')
            for arm,record in runs.items():
                if verify_files:
                    data=load_run(record)
                    if (not data['finished'] or (data['extinct_at'] is None and abs(data['elapsed_seconds']-p['duration'])>1e-7)
                        or data['seed']!=trial['seed'] or data['duration_limit']!=p['duration'] or data['initial_population']!=100 or data['population_cap']!=300
                        or data['food_capacity']!=RESOURCES[resource]['food_count'] or data['regrowth_rate']!=RESOURCES[resource]['regrowth_rate']
                        or data['mutation_rate']!=(.1 if arm=='mutating' else 0.) or data['body_mutation_rate']!=(.25 if arm=='mutating' else 0.)):
                        raise ValueError('A continuous run does not match its declared resource/mutation condition.')
    analysis={'independent_seed_groups':len(seeds),'conditions':{}}
    for resource in RESOURCES:
        analysis['conditions'][resource]={}
        for arm in ARMS:
            rows=[t['runs'][resource][arm]['summary'] for t in trials]
            keys=('final_population','births','deaths','max_depth_ever','living_families','effective_families','genetic_rms','within_family_rms','genetic_clusters','within_family_clusters')
            analysis['conditions'][resource][arm]={'runs':len(rows),'persisting_runs':sum(r['finite_window_persistence'] for r in rows),
                'extinct_runs':sum(r['extinct_at'] is not None for r in rows),
                'means':{k:float(np.mean([r[k] for r in rows if r[k] is not None])) if any(r[k] is not None for r in rows) else None for k in keys},
                'available_counts':{k:sum(r[k] is not None for r in rows) for k in keys}}
    analysis['interpretation']='Descriptive repeated finite-window persistence, not proof of indefinite sustainability, adaptation over drift, reproductive isolation, or species formation. Clusters are threshold-dependent snapshot neighborhoods.'
    return analysis


def run_study(seeds=DEFAULT_SEEDS,*,duration=600.,workers=1,output_dir='.cache/continuous-runs',checkpoint=None,declare=None,progress=False):
    seeds=list(seeds)
    if len(seeds)<2 or len(set(seeds))!=len(seeds) or any(type(s) is not int for s in seeds) or type(workers) is not int or workers<1:raise ValueError('Use independent integer seeds and positive workers.')
    if not np.isfinite(duration) or duration<=0 or not np.isclose(duration*60,round(duration*60),rtol=0,atol=1e-8):raise ValueError('Use a positive whole-tick horizon.')
    if any(Path(output_dir).glob('seed-*.npz')) or any(Path(output_dir).glob('seed-*.json.gz')):raise ValueError('Use a new ecosystem output directory.')
    report={'format_version':1,'status':'running','protocol':{'seeds':seeds,'duration':duration,'resources':RESOURCES,'arms':list(ARMS),'runs':len(seeds)*4,
        'configuration':'100 random reference-body founders, 8–8–2 brains/90 neural parameters plus three linked body traits. 1000x600 arena; living cap300; actual 1/60s ticks. No synchronized cohorts or immigration.',
        'births':'Age>=15s, >=20s since prior attempt, energy>=.8 own capacity. Eligible-parent ordering uses a per-tick seeded lottery. Each child receives .4 of its own capacity; parent also pays .1 development and .05 overhead, retaining >=.25 of its own capacity. No energy charge on failed attempts, but cooldown applies. Failed energy/space proposals and cap blocks are retained. Newborns first act next tick; parents continue living.',
        'mutation':'Independent recorded brain/body seeds per parent and attempt. Neural probability.1/scale.1, body probability.25/log scale.08. Clonal controls set both probabilities to zero; all initial founders/layouts match within resource condition.',
        'resource_model':'Food carries20 energy. Finite regrowth rate and maximum standing food stock; unused growth credit is discarded at full stock. No creatures respawn after extinction. Sustenance is external renewable food input, not a closed energy system.',
        'ancestry':'Every unique birth ID, parent, founder family, depth, time, mutation attempt, failure, and genome is archived. Colors inherit founder family. Depth is ancestry depth, not synchronized generation.',
        'diversity':'Equal-weight neural/body blocks. Neural alleles standardized by initial distribution scales; body speed/range log-normalized to bounds and radius linearly normalized. RMS pairwise distance and within-family RMS; undefined without pairs. Connected components at distance.25 are operational snapshot clusters, with final sensitivity at.15/.5; bridge loss can split clusters and clusters are not species.',
        'persistence':'A run reaches its horizon with living actors, zero living founders, ancestry depth>=3 and births during the final120s; duration must be>=240s. This is finite-window population renewal, not proof of indefinite sustainability.',
        'analysis':'Eight independent source seeds; all four resource/mutation conditions included. Descriptive counts and equal-seed means, with explicit available denominators for diversity after extinction. No confirmatory p-values, selection-versus-drift claim, or post-result tuning.'},'trials':[]}
    if declare:declare(report)
    if checkpoint:checkpoint(report)
    if workers==1:
        for seed in seeds:
            report['trials'].append(run_seed(seed,duration,output_dir,progress))
            if checkpoint:checkpoint(report)
    else:
        with ProcessPoolExecutor(max_workers=min(workers,len(seeds))) as executor:
            for future in as_completed([executor.submit(run_seed,s,duration,output_dir,progress) for s in seeds]):
                report['trials'].append(future.result())
                if checkpoint:checkpoint(report)
    report['trials'].sort(key=lambda t:seeds.index(t['seed']));report['analysis']=analyze_results(report);report['status']='complete'
    if checkpoint:checkpoint(report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--seeds',nargs='+',type=int,default=DEFAULT_SEEDS)
    parser.add_argument('--duration',type=float,default=600.);parser.add_argument('--workers',type=positive_integer,default=1)
    parser.add_argument('--runs-dir',type=Path,default=Path('.cache/continuous-runs'));parser.add_argument('--output',type=Path,default=Path('.cache/ecosystems.json'))
    parser.add_argument('--protocol-output',type=Path,default=Path('.cache/ecosystem-protocol.json'));args=parser.parse_args()
    if args.output.resolve()==args.protocol_output.resolve() or any(p.exists() or p.suffix!='.json' for p in (args.output,args.protocol_output)):parser.error('Use distinct new JSON paths.')
    def write(r):
        args.output.parent.mkdir(parents=True,exist_ok=True);temp=args.output.with_suffix('.tmp.json');temp.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');temp.replace(args.output)
    def declare(r):
        args.protocol_output.parent.mkdir(parents=True,exist_ok=True);args.protocol_output.write_text(json.dumps({'declared_at_utc':datetime.now(timezone.utc).isoformat(),'protocol':r['protocol'],
            'source_sha256':{p.name:file_digest(p) for p in sorted(Path(__file__).resolve().parent.glob('*.py'))}},indent=2)+'\n')
    try:run_study(args.seeds,duration=args.duration,workers=args.workers,output_dir=args.runs_dir,checkpoint=write,declare=declare,progress=True)
    except (ValueError,OSError) as error:parser.error(str(error))
    print(f'Continuous ecosystem study complete: {args.output}');return 0


if __name__=='__main__':raise SystemExit(main())
