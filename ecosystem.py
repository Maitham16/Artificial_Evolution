"""Resource-funded births and deaths in one persistent, unsynchronized habitat."""
from dataclasses import dataclass,fields
import copy
import colorsys
import hashlib
import math
import random

import numpy as np

from brain import NeuralNetwork
from body_traits import (BodyTraits,TraitCreature,TraitWorld,WholeGenome,mutate_body,
                         genome_bank_digest,shared_layout_digest,ENERGY_MODEL)
from experiment_selection import RecordedMutationRNG
from world import SIMULATION_STEP


CHILD_ENDOWMENT=.4
DEVELOPMENT=.1
BIRTH_OVERHEAD=.05
PARENT_RESERVE=.25
PARAMETERS=('input_weights','hidden_bias','output_weights','output_bias')
NEURAL_SCALES=np.concatenate((np.full(64,1/math.sqrt(8)),np.full(8,.1),np.full(16,1/math.sqrt(8)),np.full(2,.1)))


def seed_for(tag):return random.Random(tag).getrandbits(128)


def genetic_features(genome):
    neural=np.concatenate([p.ravel() for p in genome.brain.parameters])/NEURAL_SCALES/math.sqrt(180)
    b=genome.body
    body=np.array([math.log(b.cruise_speed/25)/math.log(4),(b.radius-4)/8,
                   math.log(b.sensory_range/60)/math.log(280/60)])/math.sqrt(6)
    return np.concatenate((neural,body))


def diversity_metrics(actors,threshold):
    actors=sorted(actors,key=lambda c:c.creature_id);n=len(actors)
    if not n:return {'genetic_rms':None,'within_family_rms':None,'genetic_clusters':0,'within_family_clusters':0,'unique_genomes':0,'family_counts':{},'effective_families':0.}
    x=np.stack([genetic_features(WholeGenome(c.brain,c.body)) for c in actors])
    distances=np.maximum(0.,np.sum(x*x,axis=1)[:,None]+np.sum(x*x,axis=1)[None,:]-2*x@x.T)
    roots=list(range(n));within=list(range(n))
    def find(tree,k):
        while tree[k]!=k:tree[k]=tree[tree[k]];k=tree[k]
        return k
    for i,j in zip(*np.nonzero(np.triu(distances<=threshold*threshold+1e-12,1))):
        roots[find(roots,int(j))]=find(roots,int(i))
        if actors[i].founder_id==actors[j].founder_id:within[find(within,int(j))]=find(within,int(i))
    counts={str(k):sum(c.founder_id==k for c in actors) for k in sorted({c.founder_id for c in actors})}
    probabilities=np.array(list(counts.values()),dtype=float)/n
    pair_sum=0.;pair_count=0
    for root in counts:
        subset=x[[i for i,c in enumerate(actors) if c.founder_id==int(root)]];m=len(subset)
        if m>1:pair_sum+=m*m*np.var(subset,axis=0).sum();pair_count+=m*(m-1)//2
    within_rms=float(math.sqrt(max(0.,pair_sum/pair_count))) if pair_count else None
    if within_rms is not None and within_rms<1e-12:within_rms=0.
    return {'genetic_rms':float(math.sqrt(max(0.,2*n/(n-1)*np.var(x,axis=0).sum()))) if n>1 else None,
        'within_family_rms':within_rms,
        'genetic_clusters':len({find(roots,i) for i in range(n)}),'within_family_clusters':len({find(within,i) for i in range(n)}),
        'unique_genomes':len({genome_bank_digest({0:WholeGenome(c.brain,c.body)}) for c in actors}),
        'family_counts':counts,'effective_families':float(np.exp(-np.sum(probabilities*np.log(probabilities))))}


@dataclass
class ContinuousCreature(TraitCreature):
    founder_id:int=0
    born_at:float=0.
    born_energy:float=90.
    removed_at:float|None=None
    last_attempt:float=-1e30
    attempt_count:int=0
    reproduction_energy:float=0.
    children:int=0


class ContinuousWorld(TraitWorld):
    """No cohort resets, rankings, immigration, or extinction rescue."""
    def __init__(self,*args,regrowth_rate=30.,population_cap=300,reproduction=True,
                 maturity_age=15.,birth_cooldown=20.,sample_interval=10.,lineage_threshold=.25,**kwargs):
        initial=kwargs.get('population_size',100)
        if type(population_cap) is not int or population_cap<initial:raise ValueError('Population cap must include every founder.')
        for name,value,allow_zero in (('regrowth',regrowth_rate,True),('maturity',maturity_age,False),('cooldown',birth_cooldown,False),('sampling',sample_interval,False),('threshold',lineage_threshold,False)):
            if isinstance(value,bool) or not math.isfinite(value) or value<0 or (not allow_zero and value==0):raise ValueError(f'Invalid {name}.')
        if type(reproduction) is not bool:raise ValueError('Reproduction switch must be boolean.')
        if kwargs.get('controller','neural')!='neural' or kwargs.get('food_sensor_mode','intact')!='intact':raise ValueError('Continuous ecosystems use intact neural control.')
        self.regrowth_rate,self.population_cap=regrowth_rate,population_cap
        self.reproduction_enabled=reproduction;self.maturity_age=maturity_age;self.birth_cooldown=birth_cooldown
        self.sample_interval=sample_interval;self.lineage_threshold=lineage_threshold
        super().__init__(*args,**kwargs)

    def _create_population(self,rng):
        population=[]
        for old in super()._create_population(rng):
            c=ContinuousCreature(**{f.name:getattr(old,f.name) for f in fields(TraitCreature) if f.init},founder_id=old.creature_id)
            c.color=tuple(round(v*255) for v in colorsys.hsv_to_rgb((c.creature_id*.61803398875)%1,.5,.9))
            c.born_energy=c.energy;population.append(c)
        return population

    def regenerate_population(self,seed=None):
        super().regenerate_population(seed)
        self.registry={c.creature_id:c for c in self.creatures};self.next_id=self.population_size+1
        self.attempts=[];self.snapshots=[];self.deaths=[];self.births=[]
        self._clock_ticks=0;self.food_credit=0.;self.food_regrown=0;self.regrowth_blocked=0
        self.extinct_at=None;self._next_sample=self.sample_interval
        self.reproduction_events=[{'time':0.,'enabled':self.reproduction_enabled}]
        for c in self.creatures:self.births.append(self.birth_record(c))
        self.initial_layout=shared_layout_digest(self)
        self.founder_genomes_hash=genome_bank_digest(self.bank())
        self.sample()

    @property
    def lineage_extinct(self):return self.extinct_at is not None

    def bank(self):return {k:WholeGenome(c.brain,c.body) for k,c in self.registry.items()}

    def birth_record(self,c):
        return {'creature_id':c.creature_id,'parent_id':c.parent_id,'founder_id':c.founder_id,'depth':c.generation-1,
            'born_at':c.born_at,'body':c.body.vector().tolist(),'initial_energy':c.born_energy,
            'genome_sha256':genome_bank_digest({0:WholeGenome(c.brain,c.body)}),'lifespan':c.lifespan,
            'x':c.x,'y':c.y,'heading':c.heading}

    def _resolve_food_collisions(self):
        remaining=[];eligible=[c for c in self.creatures if c.energy<c.energy_capacity]
        for food in self.food:
            eater=min((c for c in eligible if c.energy<c.energy_capacity and food.overlaps_circle(c.x,c.y,c.radius)),
                key=lambda c:((c.x-food.x)**2+(c.y-food.y)**2,c.creature_id),default=None)
            if eater is None or not eater.eat(food):remaining.append(food)
            else:self.total_food_eaten+=1
        self.food=remaining

    def _regrow(self):
        if len(self.food)>=self.food_count:self.food_credit=0.;return
        self.food_credit+=self.regrowth_rate*SIMULATION_STEP
        while self.food_credit+1e-12>=1 and len(self.food)<self.food_count:
            try:food=self._spawn_food()
            except ValueError:self.regrowth_blocked+=1;self.food_credit=min(self.food_credit,1.);break
            self.food.append(food);self.food_credit=max(0.,self.food_credit-1);self.food_regrown+=1
        if len(self.food)>=self.food_count:self.food_credit=0.

    def _try_births(self,time):
        if not self.reproduction_enabled:return
        eligible=[c for c in self.creatures if c.age+1e-9>=self.maturity_age and time-c.last_attempt+1e-9>=self.birth_cooldown
                  and c.energy+1e-9>=.8*c.energy_capacity]
        random.Random(f'step26:lottery:{self.seed}:tick:{self._clock_ticks+1}').shuffle(eligible)
        for parent in eligible:
            parent.last_attempt=time;parent.attempt_count+=1
            event={'attempt_id':len(self.attempts)+1,'parent_id':parent.creature_id,'parent_attempt':parent.attempt_count,
                'time':time,'parent_energy_before':parent.energy,'status':'capacity','child_id':None}
            self.attempts.append(event)
            if len(self.creatures)>=self.population_cap:continue
            tag=f'{self.seed}:parent:{parent.creature_id}:attempt:{parent.attempt_count}'
            bs,ps=seed_for('step26:brain:'+tag),seed_for('step26:body:'+tag)
            br,pr=RecordedMutationRNG(bs),RecordedMutationRNG(ps)
            brain=parent.brain.mutated_copy(br,mutation_rate=self.mutation_rate,mutation_scale=self.mutation_scale)
            body=mutate_body(parent.body,pr,self.body_mutation_rate,self.body_mutation_scale)
            cost=(CHILD_ENDOWMENT+DEVELOPMENT+BIRTH_OVERHEAD)*body.capacity
            event.update(brain_seed=bs,body_seed=ps,brain_draws_sha256=br.digest.hexdigest(),body_draws_sha256=pr.digest.hexdigest(),
                brain_rng_calls=br.calls,body_rng_calls=pr.calls,candidate_body=body.vector().tolist(),cost=cost,
                brain_mutations=sum(int(np.count_nonzero(a!=b)) for a,b in zip(parent.brain.parameters,brain.parameters)),
                body_mutations=int(np.count_nonzero(parent.body.vector()!=body.vector())),
                candidate_genome_sha256=genome_bank_digest({0:WholeGenome(brain,body)}))
            if parent.energy+1e-9<cost+PARENT_RESERVE*parent.energy_capacity:event['status']='energy';continue
            rng=random.Random('step26:placement:'+tag);position=None
            for _ in range(32):
                angle=rng.uniform(0,math.tau);distance=rng.uniform(20,60)
                x,y=parent.x+distance*math.cos(angle),parent.y+distance*math.sin(angle)
                if not body.radius+2<=x<=self.width-body.radius-2 or not body.radius+2<=y<=self.height-body.radius-2:continue
                if any(math.hypot(x-c.x,y-c.y)<body.radius+c.radius+2 for c in self.creatures):continue
                if any(f.overlaps_circle(x,y,body.radius+2) for f in self.food):continue
                position=(x,y);break
            if position is None:event['status']='space';continue
            c=ContinuousCreature(self.next_id,*position,body.radius,parent.color,rng.uniform(0,math.tau),body.cruise_speed,
                brain=brain,body=body,lifespan=rng.uniform(60,120),generation=parent.generation+1,parent_id=parent.creature_id,
                mutation_count=event['brain_mutations'],body_mutation_count=event['body_mutations'],founder_id=parent.founder_id,born_at=time)
            c.energy=c.born_energy=CHILD_ENDOWMENT*body.capacity
            parent.energy-=cost;parent.reproduction_energy+=cost;parent.children+=1
            self.creatures.append(c);self.registry[c.creature_id]=c;self.next_id+=1
            self.births.append(self.birth_record(c));event.update(status='born',child_id=c.creature_id,parent_energy_after=parent.energy)

    def update(self,dt):
        if not math.isfinite(dt) or dt<0:raise ValueError('Time must be finite and nonnegative.')
        if self.paused or self.lineage_extinct or dt==0:return
        self._accumulator+=dt
        while self._accumulator+1e-12>=SIMULATION_STEP and not self.lineage_extinct:
            food=np.array([(f.x,f.y) for f in self.food]).reshape(-1,2);survivors=[]
            time=(self._clock_ticks+1)*SIMULATION_STEP
            for c in self.creatures:
                turn,throttle=c.brain.forward(self.get_sensory_inputs(c,food));c.apply_controls(float(turn),float(throttle))
                c.update_survival(SIMULATION_STEP)
                if not c.alive:
                    c.removed_at=time;self.dead_creatures.append(c);self.deaths.append({'creature_id':c.creature_id,'time':time,'cause':c.death_cause});continue
                c.rotate(c.turn_rate*SIMULATION_STEP);c.move(SIMULATION_STEP,self.width,self.height);survivors.append(c)
            self.creatures=survivors;self._resolve_food_collisions();self._try_births(time);self._regrow()
            self._clock_ticks+=1;self.elapsed_time=self._clock_ticks*SIMULATION_STEP;self._accumulator=max(0.,self._accumulator-SIMULATION_STEP)
            if self.selected_creature not in self.creatures:self.selected_creature=None
            if not self.creatures:self.extinct_at=self.elapsed_time
            if self.elapsed_time+1e-9>=self._next_sample or self.lineage_extinct:
                self.sample();self._next_sample+=self.sample_interval

    def sample(self):
        if self.snapshots and self.snapshots[-1]['time']==self.elapsed_time:return
        diversity=diversity_metrics(self.creatures,self.lineage_threshold)
        self.snapshots.append({'time':self.elapsed_time,'population':len(self.creatures),'food':len(self.food),
            'births':len(self.births)-self.population_size,'deaths':len(self.deaths),
            'living_founders':sum(c.parent_id is None for c in self.creatures),
            'max_living_depth':max((c.generation-1 for c in self.creatures),default=0),
            'living_energy':sum(c.energy for c in self.creatures),**diversity})

    def advance_generation(self):return False

    def set_reproduction(self,enabled):
        if type(enabled) is not bool:raise ValueError('Reproduction switch must be boolean.')
        if enabled!=self.reproduction_enabled:
            self.reproduction_enabled=enabled;self.reproduction_events.append({'time':self.elapsed_time,'enabled':enabled})

    def continuous_report(self):
        self.sample()
        records=[]
        for c in sorted(self.registry.values(),key=lambda c:c.creature_id):
            records.append({'creature_id':c.creature_id,'age':c.age,'alive':c.alive,'removed_at':c.removed_at,'death_cause':c.death_cause,
                'energy':c.energy,'food_eaten':c.food_eaten,'reproduction_energy':c.reproduction_energy,'children':c.children,
                **{k:getattr(c,k) for k in ('basal_energy','movement_energy','sensing_energy','assimilated_energy','wasted_food_energy')}})
        return copy.deepcopy({'format_version':1,'mode':'continuous','seed':self.seed,'arena_size':[self.width,self.height],
            'initial_population':self.population_size,'population_cap':self.population_cap,'food_capacity':self.food_count,
            'food_distribution':self.food_distribution,'regrowth_rate':self.regrowth_rate,'food_regrown':self.food_regrown,
            'food_eaten':self.total_food_eaten,'food_remaining':len(self.food),'regrowth_blocked':self.regrowth_blocked,
            'reproduction_enabled':self.reproduction_enabled,'reproduction_events':self.reproduction_events,'maturity_age':self.maturity_age,'birth_cooldown':self.birth_cooldown,
            'sample_interval':self.sample_interval,'lineage_threshold':self.lineage_threshold,
            'mutation_rate':self.mutation_rate,'mutation_scale':self.mutation_scale,'body_mutation_rate':self.body_mutation_rate,'body_mutation_scale':self.body_mutation_scale,
            'energy_model':ENERGY_MODEL,'reproduction_model':{'endowment':CHILD_ENDOWMENT,'development':DEVELOPMENT,'overhead':BIRTH_OVERHEAD,'parent_reserve':PARENT_RESERVE},
            'elapsed_seconds':self.elapsed_time,'extinct_at':self.extinct_at,'initial_layout_sha256':self.initial_layout,'founder_genomes_sha256':self.founder_genomes_hash,
            'all_genomes_sha256':genome_bank_digest(self.bank()),'births':self.births,'attempts':self.attempts,'deaths':self.deaths,'individuals':records,'snapshots':self.snapshots})


class ContinuousSimulation:
    def __init__(self,world,*,duration=600.,speed=1):
        if isinstance(duration,bool) or not math.isfinite(duration) or duration<=0 or not math.isclose(duration*60,round(duration*60),rel_tol=0,abs_tol=1e-8):raise ValueError('Duration must be a positive whole-tick time.')
        if speed not in (1,5,20):raise ValueError('Invalid simulation speed.')
        self.world=world;self.duration=duration;self.limit_ticks=round(duration*60);self.speed=speed;self._accumulator=0.;self._ticks=0;self.generation_limit=None

    @property
    def finished(self):return self.world.lineage_extinct or self._ticks>=self.limit_ticks
    @property
    def auto_advance(self):return self.world.reproduction_enabled
    @auto_advance.setter
    def auto_advance(self,value):self.world.set_reproduction(value)
    @property
    def total_simulated_seconds(self):return self._ticks*SIMULATION_STEP
    def cycle_speed(self):self.speed=(1,5,20)[((1,5,20).index(self.speed)+1)%3]
    def advance_generation(self):return False
    def restart(self,seed=None):self.world.regenerate_population(seed);self._ticks=0;self._accumulator=0.
    def update(self,dt):
        if not math.isfinite(dt) or dt<0 or not math.isfinite(dt*self.speed):raise ValueError('Invalid elapsed time.')
        if self.finished or self.world.paused:return
        self._accumulator+=dt*self.speed
        while self._accumulator+1e-12>=SIMULATION_STEP and not self.finished:
            self.world.update(SIMULATION_STEP);self._ticks+=1;self._accumulator=max(0.,self._accumulator-SIMULATION_STEP)
    def report(self):
        report=self.world.continuous_report();report.update(duration_limit=self.duration,finished=self.finished)
        return report
