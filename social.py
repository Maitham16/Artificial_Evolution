"""Optional costly communication and conservative, local stored-food sharing."""

from dataclasses import dataclass, fields
import copy
import math
import os
import random

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')

import numpy as np
import pygame

from brain import NeuralNetwork
from body_traits import BodyTraits, TraitCreature, TraitWorld, WholeOffspring, ENERGY_MODEL, shared_layout_digest
from experiment_selection import RecordedMutationRNG
from food import Food, FOOD_RADIUS
from generation_stats import GenerationStats
from perception import sense_food
from selection import FitnessEntry, FitnessEvaluation
from world import SIMULATION_STEP


INPUTS, OUTPUTS = 17, 3
SIGNAL_COST = .2
SHARE_RATE, SHARE_RANGE, SHARE_EFFICIENCY, DONOR_RESERVE = 12., 48., .8, 10.
SENSOR_NAMES = ('food_proximity','food_direction','food_visible','hunger',
                'wall_forward','wall_right','wall_back','wall_left',
                'neighbor_proximity','neighbor_direction','neighbor_visible','neighbor_hunger',
                'received_signal','signal_direction','signal_visible','neighbor_density','food_access')
PALETTE = ((101,219,181),(105,194,237),(187,155,236),(239,167,120),(232,137,168),
           (224,205,117),(115,199,192),(161,185,242),(196,198,154),(218,164,224))


def new_social_brain(rng):
    brain=object.__new__(NeuralNetwork)
    brain.input_weights=rng.normal(0.,1/math.sqrt(INPUTS),(INPUTS,8))
    brain.hidden_bias=rng.normal(0.,.1,8)
    brain.output_weights=rng.normal(0.,1/math.sqrt(8),(8,OUTPUTS))
    brain.output_bias=rng.normal(0.,.1,OUTPUTS)
    return brain


def parent_plan(records, level, groups, group_size, seed):
    """Separate selection/assortment from the common per-child mutation stream."""
    rng=random.Random(seed)
    if level=='individual':
        selected=sorted(c.creature_id for c in sorted(records,key=lambda c:(-c.age,c.creature_id))[:math.ceil(len(records)*.2)])
        assignments=[selected[i%len(selected)] for i in range(len(records))]
        rng.shuffle(assignments)
        return {'selected_groups':[],'parent_ids':selected,'offspring_parent_ids':assignments}
    means={g:sum(c.age for c in records if c.group_id==g)/group_size for g in range(groups)}
    chosen=sorted(sorted(means,key=lambda g:(-means[g],g))[:math.ceil(groups*.2)])
    slots=[chosen[g%len(chosen)] for g in range(groups)];rng.shuffle(slots)
    assignments=[]
    for source in slots:
        members=sorted(c.creature_id for c in records if c.group_id==source);rng.shuffle(members);assignments.extend(members)
    return {'selected_groups':chosen,'parent_ids':sorted(set(assignments)),'offspring_parent_ids':assignments}


@dataclass
class SocialCreature(TraitCreature):
    group_id: int = 0
    can_feed: bool = True
    cell_origin: tuple = (0.,0.)
    cell_size: tuple = (1000.,600.)
    signal: float = 0.
    share_effort: float = 0.
    signal_energy: float = 0.
    signal_integral: float = 0.
    received_signal_integral: float = 0.
    share_request_integral: float = 0.
    shared_out: float = 0.
    shared_in: float = 0.
    removed_at: float | None = None

    @property
    def fitness(self):return self.age

    @property
    def energy_cost_per_second(self):return super().energy_cost_per_second+SIGNAL_COST*self.signal

    def update_survival(self,dt):
        before=self.age;super().update_survival(dt);lived=self.age-before
        self.signal_integral+=self.signal*lived
        self.signal_energy+=SIGNAL_COST*self.signal*lived
        self.share_request_integral+=self.share_effort*lived

    def move(self,dt,width,height):
        ox,oy=self.cell_origin;self.x-=ox;self.y-=oy
        try:super().move(dt,*self.cell_size)
        finally:self.x+=ox;self.y+=oy

    def draw(self,surface,*,selected=False):
        super().draw(surface,selected=selected)
        if not self.alive:return
        center=(round(self.x),round(self.y))
        if self.can_feed:pygame.draw.circle(surface,(245,208,115),center,2)
        if self.signal>.05:pygame.draw.circle(surface,(102,167,198),center,self.radius+5+round(8*self.signal),1)


class SocialWorld(TraitWorld):
    """Independent demes, optional signals/transfers, and survival-only selection.

    Groups are physically isolated for a cohort. Group breeding preserves teams;
    individual breeding mixes selected actors. This compares both incentives and
    assortment, without a direct reward for sending signals or sharing energy.
    """
    def __init__(self,width=1000,height=600,*,groups=10,selection_level='group',
                 access='restricted',signaling=True,sharing=True,signals_hidden=False,
                 episode_seconds=60.,**kwargs):
        population=kwargs.get('population_size',100);food=kwargs.get('food_count',150)
        if type(groups) is not int or groups<2 or population%groups or population//groups<2:
            raise ValueError('Use at least two groups, equally sized with at least two members.')
        if food%groups:raise ValueError('Food count must divide equally among groups.')
        if selection_level not in ('individual','group') or access not in ('restricted','open'):
            raise ValueError('Choose individual/group selection and restricted/open food access.')
        if any(type(v) is not bool for v in (signaling,sharing,signals_hidden)):raise ValueError('Social switches must be boolean.')
        if (isinstance(episode_seconds,bool) or not math.isfinite(episode_seconds) or episode_seconds<=0
                or not math.isclose(episode_seconds*60,round(episode_seconds*60),rel_tol=0,abs_tol=1e-8)):
            raise ValueError('Episode length must be a positive whole number of fixed ticks.')
        if (kwargs.get('controller','neural')!='neural' or kwargs.get('food_distribution','uniform')!='uniform'
                or kwargs.get('food_sensor_mode','intact')!='intact'):
            raise ValueError('Social cohorts use neural controllers and uniform food inside each group.')
        if kwargs.get('body_mutation_rate',0)!=0 or kwargs.get('body_mutation_scale',0)!=0:
            raise ValueError('Social experiments hold body traits fixed to isolate social behavior.')
        self.groups,self.group_size=groups,population//groups
        self.columns=min((n for n in range(1,groups+1) if groups%n==0),key=lambda n:abs(math.log((n/(groups/n))/(width/height))))
        self.rows=groups//self.columns
        self.cell_size=(width/self.columns,height/self.rows)
        if min(self.cell_size)<80:raise ValueError('Group arenas must be at least 80 pixels wide and tall.')
        self.selection_level,self.access=selection_level,access
        self.signaling,self.sharing,self.signals_hidden=signaling,sharing,signals_hidden
        self.episode_seconds=episode_seconds;self.episode_ticks=round(episode_seconds*60)
        kwargs.update(body_mutation_rate=0,body_mutation_scale=0)
        super().__init__(width,height,**kwargs)

    def regenerate_population(self,seed=None):
        self.social_history=[]
        super().regenerate_population(seed)

    def origin(self,group):return ((group%self.columns)*self.cell_size[0],(group//self.columns)*self.cell_size[1])

    def food_group(self,food):
        return min(self.columns-1,int(food.x/self.cell_size[0]))+self.columns*min(self.rows-1,int(food.y/self.cell_size[1]))

    def _create_population(self,rng):
        originals=super()._create_population(rng);population=[]
        anchors=random.Random(f'step25:anchors:{self.seed}:generation:{self._body_generation}')
        roles=random.Random(f'step25:access:{self.seed}:generation:{self._body_generation}')
        accessible={g:set(roles.sample(range(self.group_size),self.group_size//2)) for g in range(self.groups)}
        for old in originals:
            g=(old.creature_id-1)//self.group_size;slot=(old.creature_id-1)%self.group_size
            if old.body!=BodyTraits():raise ValueError('Social actors require reference bodies.')
            c=SocialCreature(**{f.name:getattr(old,f.name) for f in fields(TraitCreature) if f.init},
                group_id=g,can_feed=self.access=='open' or slot in accessible[g],cell_origin=self.origin(g),cell_size=self.cell_size)
            c.color=PALETTE[g%len(PALETTE)]
            if self._birth_genomes is None and self.initial_genomes is None:
                c.brain=new_social_brain(np.random.default_rng(random.Random(f'step25:founder:{self.seed}:{c.creature_id}').getrandbits(128)))
            if c.brain.input_weights.shape!=(INPUTS,8) or c.brain.output_weights.shape!=(8,OUTPUTS):raise ValueError('Social brains require 17–8–3 parameters.')
            ox,oy=c.cell_origin;cw,ch=c.cell_size
            for _ in range(2000):
                c.x,c.y=ox+anchors.uniform(20,cw-20),oy+anchors.uniform(20,ch-20)
                if all(other.group_id!=g or math.hypot(c.x-other.x,c.y-other.y)>=32 for other in population):break
            else:raise ValueError('A social group is too crowded for matched placement.')
            population.append(c)
        return population

    def _start_generation(self,generation,inherited=None):
        self._replacement_group=None
        super()._start_generation(generation,inherited)
        self._episode_ticks=0;self.transfer_edges={}
        self.social_history.append({'generation':generation,'complete':False,'shared_layout_sha256':shared_layout_digest(self),
            'genomes_sha256':self.trait_history[-1]['genomes_sha256'],
            'food_access_ids':[c.creature_id for c in self.creatures if c.can_feed],
            'population':[self.population_snapshot()]})

    def _spawn_food(self):
        group=self._replacement_group if self._replacement_group is not None else len(self.food)%self.groups
        ox,oy=self.origin(group);cw,ch=self.cell_size;margin=FOOD_RADIUS+3
        for _ in range(1000):
            food=Food(ox+self._food_rng.uniform(margin,cw-margin),oy+self._food_rng.uniform(margin,ch-margin))
            if any(c.group_id==group and food.overlaps_circle(c.x,c.y,14) for c in self.creatures):continue
            if any(food.overlaps_circle(f.x,f.y,f.radius+2) for f in self.food if self.food_group(f)==group):continue
            return food
        raise ValueError('A social arena is too crowded to place food.')

    def _resolve_food_collisions(self):
        remaining=[]
        members={g:[] for g in range(self.groups)}
        for c in self.creatures:
            if c.can_feed and c.alive and c.energy<c.energy_capacity:members[c.group_id].append(c)
        for food in self.food:
            group=self.food_group(food)
            eater=min((c for c in members[group] if c.energy<c.energy_capacity
                       and food.overlaps_circle(c.x,c.y,c.radius)),key=lambda c:((c.x-food.x)**2+(c.y-food.y)**2,c.creature_id),default=None)
            if eater is None or not eater.eat(food):remaining.append(food)
            else:self.total_food_eaten+=1
        self.food=remaining
        counts={g:0 for g in range(self.groups)}
        for food in self.food:counts[self.food_group(food)]+=1
        try:
            for group in range(self.groups):
                self._replacement_group=group
                missing=self.food_count//self.groups-counts[group]
                for _ in range(missing):self.food.append(self._spawn_food())
        finally:self._replacement_group=None

    def _wall_clearance(self,c,dx,dy):
        ox,oy=c.cell_origin;cw,ch=c.cell_size;x,y=c.x-ox,c.y-oy;r=c.body.sensory_range
        distances=[r]
        if dx>1e-12:distances.append((cw-c.radius-x)/dx)
        elif dx< -1e-12:distances.append((c.radius-x)/dx)
        if dy>1e-12:distances.append((ch-c.radius-y)/dy)
        elif dy< -1e-12:distances.append((c.radius-y)/dy)
        return max(0.,min(distances))/r

    def perceive_food(self,c,food_positions=None):
        positions=np.array([(f.x,f.y) for f in self.food if self.food_group(f)==c.group_id]).reshape(-1,2) if food_positions is None else food_positions
        return sense_food(c.x,c.y,c.heading,positions,vision_range=c.body.sensory_range)

    def neighbor_snapshot(self):
        rows={g:[] for g in range(self.groups)}
        for c in self.creatures:rows[c.group_id].append((c.creature_id,c.x,c.y,c.hunger,c.signal))
        return {g:np.array(row).reshape(-1,5) for g,row in rows.items()}

    def perceive_neighbors(self,c,snapshot=None):
        rows=self.neighbor_snapshot()[c.group_id] if snapshot is None else snapshot
        rows=rows[rows[:,0]!=c.creature_id]
        signals=np.zeros(9);signals[-1]=float(c.can_feed)
        truth={'nearest_id':None,'nearest_position':None,'signal_id':None,'signal_strength':0.,'nearby':0}
        if not len(rows):return signals,truth
        offsets=rows[:,1:3]-(c.x,c.y);dist=np.hypot(offsets[:,0],offsets[:,1]);visible=dist<=c.body.sensory_range
        if not np.any(visible):return signals,truth
        rows,offsets,dist=rows[visible],offsets[visible],dist[visible];i=int(np.argmin(dist))
        bearing=lambda j:0. if dist[j]==0 else ((math.atan2(offsets[j,1],offsets[j,0])-c.heading+math.pi)%math.tau-math.pi)/math.pi
        signals[:4]=[1-dist[i]/c.body.sensory_range,bearing(i),1.,rows[i,3]]
        signals[7]=len(rows)/(self.group_size-1)
        strength=rows[:,4]*(1-dist/c.body.sensory_range);j=int(np.argmax(strength))
        if strength[j]>0:signals[4:7]=[strength[j],bearing(j),1.];truth.update(signal_id=int(rows[j,0]),signal_strength=float(strength[j]))
        truth.update(nearest_id=int(rows[i,0]),nearest_position=rows[i,1:3].tolist(),nearby=len(rows))
        return signals,truth

    def get_sensory_inputs(self,c,food_positions=None,neighbors=None):
        base=super().get_sensory_inputs(c,food_positions);social,_=self.perceive_neighbors(c,neighbors)
        if not self.signaling or self.signals_hidden:social[4:7]=0
        return np.concatenate((base,social))

    def _share_food(self):
        if not self.sharing:return
        stock={c.creature_id:c.energy for c in self.creatures};proposals=[];incoming={}
        groups={g:[] for g in range(self.groups)}
        for c in self.creatures:groups[c.group_id].append(c)
        for donor in self.creatures:
            if donor.share_effort<=0 or stock[donor.creature_id]<=DONOR_RESERVE:continue
            recipient=min((c for c in groups[donor.group_id] if c is not donor
                and math.hypot(c.x-donor.x,c.y-donor.y)<=SHARE_RANGE),key=lambda c:((c.x-donor.x)**2+(c.y-donor.y)**2,c.creature_id),default=None)
            if recipient is None:continue
            amount=min(SHARE_RATE*donor.share_effort*SIMULATION_STEP,stock[donor.creature_id]-DONOR_RESERVE,
                       (recipient.energy_capacity-stock[recipient.creature_id])/SHARE_EFFICIENCY)
            if amount<=1e-12:continue
            proposals.append((donor,recipient,amount));incoming[recipient.creature_id]=incoming.get(recipient.creature_id,0.)+amount
        outgoing={};received={}
        for donor,recipient,amount in proposals:
            room=recipient.energy_capacity-stock[recipient.creature_id]
            amount*=min(1.,room/(SHARE_EFFICIENCY*incoming[recipient.creature_id]))
            if amount<=1e-12:continue
            gain=SHARE_EFFICIENCY*amount
            outgoing[donor.creature_id]=outgoing.get(donor.creature_id,0.)+amount
            received[recipient.creature_id]=received.get(recipient.creature_id,0.)+gain
            donor.shared_out+=amount;recipient.shared_in+=gain
            key=(donor.creature_id,recipient.creature_id)
            edge=self.transfer_edges.setdefault(key,{'donor_id':key[0],'recipient_id':key[1],'given':0.,'received':0.,'ticks':0,'last_time':0.})
            edge['given']+=amount;edge['received']+=gain;edge['ticks']+=1;edge['last_time']=self.elapsed_time+SIMULATION_STEP
        for c in self.creatures:c.energy=stock[c.creature_id]-outgoing.get(c.creature_id,0.)+received.get(c.creature_id,0.)

    def population_snapshot(self):
        return {'time':self.elapsed_time,'alive':[sum(c.group_id==g for c in self.creatures) for g in range(self.groups)]}

    def update(self,dt):
        if not math.isfinite(dt) or dt<0:raise ValueError('Simulation time must be finite and nonnegative.')
        if self.paused or self.final_evaluation is not None or dt==0:return
        self._accumulator+=dt
        while self._accumulator+1e-12>=SIMULATION_STEP and self.final_evaluation is None:
            neighbors=self.neighbor_snapshot()
            food={g:[] for g in range(self.groups)}
            for f in self.food:food[self.food_group(f)].append((f.x,f.y))
            food={g:np.array(points).reshape(-1,2) for g,points in food.items()}
            survivors=[]
            for c in self.creatures:
                local,truth=self.perceive_neighbors(c,neighbors[c.group_id])
                if not self.signaling or self.signals_hidden:local[4:7]=0
                base=super().get_sensory_inputs(c,food[c.group_id])
                controls=c.brain.forward(np.concatenate((base,local)))
                c.apply_controls(float(controls[0]),1.)
                c.signal=max(0.,float(controls[1])) if self.signaling else 0.
                c.share_effort=max(0.,float(controls[2]))
                before=c.age;c.update_survival(SIMULATION_STEP);lived=c.age-before
                c.received_signal_integral+=truth['signal_strength']*lived
                self._alive_time+=lived;self._speed_time+=c.speed*lived
                if not c.alive:c.removed_at=self.elapsed_time+SIMULATION_STEP;self.dead_creatures.append(c);continue
                c.rotate(c.turn_rate*SIMULATION_STEP);c.move(SIMULATION_STEP,self.width,self.height);survivors.append(c)
            self.creatures=survivors
            self._resolve_food_collisions();self._share_food()
            if self.selected_creature not in self.creatures:self.selected_creature=None
            self._episode_ticks+=1;self.elapsed_time=self._episode_ticks*SIMULATION_STEP
            self._accumulator=max(0.,self._accumulator-SIMULATION_STEP)
            if self._episode_ticks%300==0 or not self.creatures or self._episode_ticks>=self.episode_ticks:
                self.social_history[-1]['population'].append(self.population_snapshot())
            if not self.creatures or self._episode_ticks>=self.episode_ticks:self._finish_generation()

    def _finish_generation(self):
        members=sorted([*self.creatures,*self.dead_creatures],key=lambda c:c.creature_id)
        groups=[]
        for g in range(self.groups):
            rows=[c for c in members if c.group_id==g]
            groups.append({'group_id':g,'mean_age':sum(c.age for c in rows)/len(rows),
                'alive_at_end':sum(c.alive for c in rows),'survival_rate':sum(c.alive for c in rows)/len(rows),
                'shared_out':sum(c.shared_out for c in rows),'shared_in':sum(c.shared_in for c in rows)})
        entries=tuple(sorted((FitnessEntry(c.creature_id,c.age,c.food_eaten,c.age,c.alive) for c in members),key=lambda e:(-e.fitness,e.creature_id)))
        plan=parent_plan(members,self.selection_level,self.groups,self.group_size,0)
        self.final_evaluation=FitnessEvaluation(entries,tuple(plan['parent_ids']),True,.2);self.generation_history.append(self.final_evaluation)
        mean_age=sum(c.age for c in members)/len(members)
        self.generation_stats.append(GenerationStats(self.generation,len(members),self.elapsed_time,mean_age,max(c.age for c in members),
            sum(c.food_eaten for c in members)/len(members),mean_age,self._speed_time/self._alive_time if self._alive_time else 0.,0.,0.,
            survivors_at_checkpoint=sum(c.age>=60 for c in members)))
        records=[]
        for c in members:
            records.append({'creature_id':c.creature_id,'group_id':c.group_id,'can_feed':c.can_feed,'age':c.age,'fitness':c.age,
                'food_eaten':c.food_eaten,'alive_at_end':c.alive,'death_cause':c.death_cause,'removed_at':c.removed_at,
                'initial_energy':c.body.initial_energy,'final_energy':c.energy,
                **{k:getattr(c,k) for k in ('basal_energy','movement_energy','sensing_energy','assimilated_energy','wasted_food_energy',
                    'signal_energy','signal_integral','received_signal_integral','share_request_integral','shared_out','shared_in')}})
        self.social_history[-1].update(complete=True,duration=self.elapsed_time,mean_age=mean_age,
            survival_rate=sum(c.alive for c in members)/len(members),groups=groups,creatures=records,
            transfer_edges=[self.transfer_edges[k].copy() for k in sorted(self.transfer_edges)],
            shared_out=sum(c.shared_out for c in members),shared_in=sum(c.shared_in for c in members),signal_energy=sum(c.signal_energy for c in members))

    def advance_generation(self):
        if self.final_evaluation is None or not self.evolution_enabled:return False
        members=[*self.creatures,*self.dead_creatures];records={c.creature_id:c for c in members};following=self.generation+1
        slot_seed=random.Random(f'step25:slots:{self.seed}:generation:{following}').getrandbits(128)
        mutation_seed=random.Random(f'step25:brain-mutation:{self.seed}:generation:{following}').getrandbits(128)
        plan=parent_plan(members,self.selection_level,self.groups,self.group_size,slot_seed)
        rng=RecordedMutationRNG(mutation_seed);children=[]
        for key in plan['offspring_parent_ids']:
            parent=records[key];brain=parent.brain.mutated_copy(rng,mutation_rate=self.mutation_rate,mutation_scale=self.mutation_scale)
            changes=sum(int(np.count_nonzero(a!=b)) for a,b in zip(parent.brain.parameters,brain.parameters))
            children.append(WholeOffspring(key,brain,changes,BodyTraits(),0))
        self.transitions.append({'from_generation':self.generation,'to_generation':following,**plan,'slot_seed':slot_seed,
            'mutation_seed':mutation_seed,'mutation_draws_sha256':rng.digest.hexdigest(),'mutation_rng_calls':rng.calls,
            'offspring_mutation_counts':[c.mutations for c in children]})
        self._start_generation(following,children);return True

    def social_report(self):
        return copy.deepcopy({'groups':self.groups,'group_size':self.group_size,'selection_level':self.selection_level,
            'access':self.access,'signaling':self.signaling,'sharing':self.sharing,'signals_hidden':self.signals_hidden,
            'episode_seconds':self.episode_seconds,'sensor_names':list(SENSOR_NAMES),'body':BodyTraits().vector().tolist(),
            'signal_cost':SIGNAL_COST,'share_rate':SHARE_RATE,'share_range':SHARE_RANGE,'share_efficiency':SHARE_EFFICIENCY,
            'donor_reserve':DONOR_RESERVE,'energy_model':ENERGY_MODEL,'cell_size':list(self.cell_size),
            'history':self.social_history,'transitions':self.transitions})

    def _draw_environment(self,surface):
        font=pygame.font.Font(None,17) if pygame.font.get_init() else None
        for g in range(self.groups):
            ox,oy=self.origin(g);pygame.draw.rect(surface,(63,86,96),pygame.Rect(ox,oy,*self.cell_size),1)
            if font:surface.blit(font.render(f'Group {g+1}: {sum(c.group_id==g for c in self.creatures)}/{self.group_size}',True,PALETTE[g%10]),(ox+7,oy+6))
        records={c.creature_id:c for c in self.creatures}
        for edge in self.transfer_edges.values():
            if self.elapsed_time-edge['last_time']<=.2 and edge['donor_id'] in records and edge['recipient_id'] in records:
                a,b=records[edge['donor_id']],records[edge['recipient_id']]
                pygame.draw.line(surface,(220,182,93),(round(a.x),round(a.y)),(round(b.x),round(b.y)),1)
        c=self.selected_creature
        if c is not None and self.show_perception:
            _,truth=self.perceive_neighbors(c)
            if truth['nearest_position'] is not None:
                pygame.draw.line(surface,(111,184,218),(round(c.x),round(c.y)),tuple(round(x) for x in truth['nearest_position']),1)


def draw_social_interface(screen,world,fonts,simulation):
    from main import BACKGROUND,TEXT,MUTED,PADDING,HEADER_HEIGHT,draw_trend
    screen.fill(BACKGROUND);font=fonts['small']
    def label(text,x,y,color=TEXT):screen.blit(font.render(text,True,color),(x,y))
    label('ARTIFICIAL EVOLUTION / STEP 25',40,22,PALETTE[0])
    screen.blit(fonts['title'].render('Cooperation and social behavior',True,TEXT),(40,43))
    label(f"{world.selection_level.upper()} SELECTION  /  {len(world.creatures)}/{world.population_size} ALIVE",630,25)
    label(f"Gen {world.generation}/{simulation.generation_limit or 'unlimited'}   {simulation.speed}x   {world.elapsed_time:.1f}/{world.episode_seconds:g}s",630,49,MUTED)
    label(f"Access {world.access}  /  Signal {'on' if world.signaling else 'off'}  /  Sharing {'on' if world.sharing else 'off'}  /  Shared {sum(e['given'] for e in world.transfer_edges.values()):.1f} energy",40,82,MUTED)
    world.draw(screen,(PADDING,HEADER_HEIGHT));y=HEADER_HEIGHT+world.height+15
    label('Space Pause  /  A Auto  /  S Speed  /  N Next  /  R Restart  /  F Scores  /  T History  /  V Senses  /  Esc Quit',40,y,MUTED)
    c=world.selected_creature
    if c is not None:
        label(f"#{c.creature_id} / Group {c.group_id+1} / {'Plant access' if c.can_feed else 'Sharing-dependent'} / Energy {c.energy:.1f} / Age {c.age:.1f}s / Meals {c.food_eaten}",40,y+24,c.color)
        label(f"Signal {c.signal:.2f} / Share action {c.share_effort:.2f} / Given {c.shared_out:.1f} / Received {c.shared_in:.1f} / Gold lines: food transfers",40,y+46,MUTED)
    else:label('Click an individual. Gold center: plant access. Blue halo: emitted signal. Blue line: nearest neighbor.',40,y+28,MUTED)
    if not (world.show_history or world.show_fitness):return
    panel=pygame.Rect(90,170,900,475);pygame.draw.rect(screen,BACKGROUND,panel,border_radius=12);pygame.draw.rect(screen,MUTED,panel,1,border_radius=12)
    if world.show_fitness:
        members=[*world.creatures,*world.dead_creatures]
        label('Selection uses survival only; signaling and donating have no direct score reward.',120,195)
        for i,c in enumerate(sorted(members,key=lambda c:(-c.age,c.creature_id))[:12]):
            label(f"#{c.creature_id:03d} / Group {c.group_id+1:2d} / Age {c.age:5.1f} / Given {c.shared_out:6.1f} / Received {c.shared_in:6.1f}",120,235+i*28,c.color)
    else:
        rows=[h for h in world.social_history if h['complete']];label('Completed cohorts / fixed birth groups / survival and actual transfers',120,195)
        if not rows:label('Complete a cohort to see history.',120,245,MUTED);return
        g=[h['generation'] for h in rows]
        draw_trend(screen,pygame.Rect(120,270,390,235),'Mean survival (seconds)',[([r['mean_age'] for r in rows],PALETTE[0])],g,font,ceiling=world.episode_seconds)
        draw_trend(screen,pygame.Rect(560,270,390,235),'Energy shared per newborn',[([r['shared_in']/world.population_size for r in rows],PALETTE[5])],g,font)
