"""Opt-in v2 2.5D habitat extension. Original Python modules remain unmodified.

Terrain changes movement/metabolic cost inside the original survival/move calls,
before food/capture resolution. A separate replay identifies these changed rules.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import argparse
import hashlib
import csv
import html
import json
import math
import random
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from research_session import ResearchSession, RunConfig, export_bundle, verify_bundle
from food import Food

VERSION='physical_habitat_v1'
SOURCE_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
UNITS=20.

@dataclass(frozen=True)
class HabitatConfig:
    enabled: bool=False
    version: str=VERSION
    grid_spacing: float=1.
    water_level: float=-.2
    max_water_depth: float=.75
    max_slope: float=.9
    uphill_cost: float=2.
    wading_cost: float=2.5
    weather_period: float=40.
    day_seconds: float=240.

    @classmethod
    def from_dict(cls,data=None):
        data={} if data is None else data
        if not isinstance(data,dict) or set(data)-set(cls.__dataclass_fields__):raise ValueError('Unknown physical habitat setting')
        config=cls(**data)
        if type(config.enabled) is not bool or config.version!=VERSION:raise ValueError('Invalid physical habitat version or enabled flag')
        for name in ('grid_spacing','max_water_depth','max_slope','uphill_cost','wading_cost','weather_period','day_seconds'):
            value=getattr(config,name)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError('Habitat values must be finite and positive: '+name)
        if config.grid_spacing!=1. or config.water_level!=-.2:raise ValueError('Version 1 fixes grid spacing and water level for reproducible geometry')
        if config.max_water_depth>2 or config.max_slope>2 or config.uphill_cost>20 or config.wading_cost>20 or config.weather_period<1 or config.day_seconds<1:raise ValueError('Habitat parameters exceed supported bounds')
        return config

class Surface:
    def __init__(self,width,height,seed,config):
        self.width,self.height=width/UNITS,height/UNITS;self.config=config
        self.nx=math.ceil(self.width)+1;self.nz=math.ceil(self.height)+1
        phase=random.Random(f'{VERSION}:{seed}').random()*math.tau
        self.values=[]
        for iz in range(self.nz):
            z=iz*self.height/(self.nz-1)-self.height/2
            for ix in range(self.nx):
                x=ix*self.width/(self.nx-1)-self.width/2
                meadow=.65+.32*math.sin(x*.22+phase)*math.cos(z*.18)+.18*math.sin(z*.43+x*.08)
                hill=2.8*math.exp(-((x-.23*self.width)/max(3.,self.width*.17))**2-((z+self.height*.17)/max(3.,self.height*.25))**2)
                center=self.width*.10*math.sin(z*.13)+self.width*.03
                river=(1.5-.9*math.exp(-(z/2.2)**2))*math.exp(-((x-center)/1.8)**2)
                self.values.append(meadow+hill-river)
        self.digest=hashlib.sha256(json.dumps(self.values,separators=(',',':')).encode()).hexdigest()
    def height_at(self,x,z):
        fx=min(self.nx-1,max(0,(x/self.width+.5)*(self.nx-1)))
        fz=min(self.nz-1,max(0,(z/self.height+.5)*(self.nz-1)))
        ix=min(self.nx-2,int(fx));iz=min(self.nz-2,int(fz));tx=fx-ix;tz=fz-iz
        offset=iz*self.nx+ix;a=self.values[offset];b=self.values[offset+1];c=self.values[offset+self.nx];d=self.values[offset+self.nx+1]
        return a+(b-a)*tx+(c-a)*tz if tx+tz<=1 else d+(c-d)*(1-tx)+(b-d)*(1-tz)
    def at_pixel(self,x,y):return self.height_at((x/UNITS)-self.width/2,(y/UNITS)-self.height/2)
    def depth(self,x,y):return max(0,self.config.water_level-self.at_pixel(x,y))
    def gradient(self,x,y):
        epsilon=5.
        return ((self.at_pixel(x+epsilon,y)-self.at_pixel(x-epsilon,y))/.5,
                (self.at_pixel(x,y+epsilon)-self.at_pixel(x,y-epsilon))/.5)
    def describe(self):
        return dict(width=self.width,height=self.height,nx=self.nx,nz=self.nz,heights=self.values,sha256=self.digest,water_level=self.config.water_level)

_CLASSES={}
class HabitatMotion:
    @property
    def energy_cost_per_second(self):return super().energy_cost_per_second+sum(self._habitat.costs(self))
    def update_survival(self,dt):
        before=self.age;costs=self._habitat.costs(self);super().update_survival(dt);lived=self.age-before
        for name,value in zip(('uphill_energy','water_energy','weather_energy'),costs):self.habitat_ledger[name]+=value*lived
        if self._habitat.surface.depth(self.x,self.y)>.03:self.habitat_ledger['water_seconds']+=lived
    def move(self,dt,width,height):
        if dt==0 or not self.alive:return super().move(dt,width,height)
        before=(self.x,self.y);command=self.speed;habitat=self._habitat
        gx,gz=habitat.surface.gradient(self.x,self.y);depth=habitat.surface.depth(self.x,self.y)
        traction={'clear':1.,'rain':.9,'snow':.78}[habitat.climate['weather']]
        self.speed=command*traction/(math.sqrt(1+gx*gx+gz*gz)*(1+depth*2.5))
        try:super().move(dt,width,height)
        finally:self.speed=command
        nx,nz=habitat.surface.gradient(self.x,self.y)
        if habitat.surface.depth(self.x,self.y)>habitat.config.max_water_depth or math.hypot(nx,nz)>habitat.config.max_slope:
            self.x,self.y=before;self.habitat_ledger['blocked']+=1
            length=math.hypot(nx,nz)
            if length>1e-8:
                vx,vy=math.cos(self.heading),math.sin(self.heading);nx/=length;nz/=length;dot=vx*nx+vy*nz
                self.heading=math.atan2(vy-2*dot*nz,vx-2*dot*nx)%math.tau
            else:self.heading=(self.heading+math.pi)%math.tau
        self.habitat_ledger['metres']+=math.dist(before,(self.x,self.y))/UNITS

class HabitatSession(ResearchSession):
    def __init__(self,config,habitat):
        self.habitat_config=HabitatConfig.from_dict(habitat)
        if not self.habitat_config.enabled:raise ValueError('Use the original ResearchSession for disabled habitat')
        width,height,_,_=config.habitat
        self.surface=Surface(width,height,config.seed,self.habitat_config)
        self.habitat_owner=_HabitatOwner(self.surface,self.habitat_config)
        super().__init__(config)
        spawn=self.world._spawn_food
        def dry_food(*args,**kwargs):
            for _ in range(256):
                candidate=spawn(*args,**kwargs)
                if self.surface.depth(candidate.x,candidate.y)<=.02:return candidate
            raise ValueError('Cannot place dry food in this habitat; reduce food/population density')
        self.world._spawn_food=dry_food
        foods=[]
        for food in self.world.food:
            if self.surface.depth(food.x,food.y)<=.02:foods.append(food);continue
            if hasattr(self.world,'food_group'):
                previous=self.world._replacement_group;self.world._replacement_group=self.world.food_group(food)
                try:foods.append(dry_food())
                finally:self.world._replacement_group=previous
            else:foods.append(dry_food())
        self.world.food=foods
    def _observe_births(self):
        super()._observe_births()
        for c in self.world.creatures:
            if getattr(c,'_habitat',None) is self.habitat_owner:continue
            base=type(c)
            if base not in _CLASSES:_CLASSES[base]=type('Habitat'+base.__name__,(HabitatMotion,base),{})
            self.habitat_owner.safe_spawn(c,self.world.width,self.world.height)
            c.__class__=_CLASSES[base];c._habitat=self.habitat_owner
            c.habitat_ledger=dict(uphill_energy=0.,water_energy=0.,weather_energy=0.,water_seconds=0.,blocked=0,metres=0.)
    def _sync_climate(self):
        self.habitat_owner.set_time(self.elapsed)
        history=getattr(self.world,'environment_history',())
        if history:
            climate=self.habitat_owner.climate;climate['season']=history[-1]['season']
            if climate['weather'] in ('rain','snow'):climate['weather']='snow' if climate['season']=='winter' else 'rain'
    def advance(self,record=True):
        result=super().advance(record);self._sync_climate();return result
    def step(self):
        self._sync_climate();result=super().step();self._sync_climate();return result
    def snapshot(self):
        report,genomes=super().snapshot()
        report['habitat']=dict(version=VERSION,source_sha256=SOURCE_SHA,config=asdict(self.habitat_config),surface_sha256=self.surface.digest,
                               climate=self.habitat_owner.climate.copy(),telemetry={key:c.habitat_ledger.copy() for key,c in self.actors.items()},
                               replay='python v2/backend/habitat.py --replay PATH/run.json')
        report['notes'].append('Commanded speed retains the original telemetry meaning; habitat telemetry metres records actual travel.')
        report['notes'].append('V2 PHYSICAL HABITAT: changed movement/metabolism/food placement. Use v2 habitat replay, not the original simulator replay. Not comparable to legacy runs without matched habitat settings.')
        return report,genomes

class _HabitatOwner:
    def __init__(self,surface,config):self.surface=surface;self.config=config;self.set_time(0)
    def set_time(self,seconds):
        self._cost_cache={}
        season=('spring','summer','autumn','winter')[int(seconds/(self.config.weather_period*3))%4]
        weather='clear' if int(seconds/self.config.weather_period)%2==0 else 'snow' if season=='winter' else 'rain'
        hour=(10.5+seconds*24/self.config.day_seconds)%24
        self.climate=dict(time=seconds,weather=weather,hour=hour,season=season,source='Python physical habitat')
    def safe_spawn(self,c,width,height):
        if self.surface.depth(c.x,c.y)<=self.config.max_water_depth and math.hypot(*self.surface.gradient(c.x,c.y))<=self.config.max_slope:return
        ox,oy=getattr(c,'cell_origin',(0,0));cw,ch=getattr(c,'cell_size',(width,height))
        for distance in (10,20,40,80,160,320):
            for index in range(32):
                angle=index*math.tau/32;x=min(ox+cw-c.radius,max(ox+c.radius,c.x+math.cos(angle)*distance));y=min(oy+ch-c.radius,max(oy+c.radius,c.y+math.sin(angle)*distance))
                if self.surface.depth(x,y)<=.03 and math.hypot(*self.surface.gradient(x,y))<=self.config.max_slope:c.x,c.y=x,y;return
        raise ValueError('No safe physical habitat birth location')
    def costs(self,c):
        key=(id(c),c.x,c.y,c.heading,c.speed)
        if key in self._cost_cache:return self._cost_cache[key]
        gx,gz=self.surface.gradient(c.x,c.y);speed=abs(c.speed)/UNITS
        uphill=max(0,gx*math.cos(c.heading)+gz*math.sin(c.heading))*speed*self.config.uphill_cost
        water=self.surface.depth(c.x,c.y)*self.config.wading_cost
        night=max(0,-math.sin((self.climate['hour']-6)/24*math.tau))
        weather={'clear':0.,'rain':.35,'snow':.8}[self.climate['weather']]+night*.25
        result=(uphill,water,weather);self._cost_cache[key]=result
        return result

def replay_habitat(report):
    if report.get('habitat',{}).get('version')!=VERSION:raise ValueError('Not a supported physical habitat report')
    if report['habitat'].get('source_sha256')!=SOURCE_SHA:raise ValueError('Physical habitat source version differs from this report')
    session=HabitatSession(RunConfig.from_dict(report['config']),report['habitat']['config'])
    events=report['execution']['controls'];index=0
    for tick in range(report['execution']['ticks']+1):
        while index<len(events) and events[index]['tick']==tick:
            event=events[index]
            if event['action']=='advance':
                if not session.advance():raise ValueError('Habitat manual transition mismatch')
            else:session.set_control(event['action'],event['value'])
            index+=1
        if tick<report['execution']['ticks'] and not session.step():raise ValueError('Habitat replay ended early')
    actual,_=session.snapshot()
    for name in ('individuals','metrics','samples','simulation','telemetry','habitat'):
        if actual[name]!=report[name]:raise ValueError('Habitat replay mismatch: '+name)
    if index!=len(events):raise ValueError('Control events extend beyond horizon')
    return session

def export_habitat(report,genomes,root,screenshot=None):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.habitat-export-',dir=root) as directory:
        bundle=export_bundle(report,genomes,directory,screenshot)
        (bundle/'habitat.json').write_text(json.dumps(report['habitat'],indent=2)+'\n')
        with (bundle/'habitat_telemetry.csv').open('w',newline='') as stream:
            rows=[dict(key=key,**values) for key,values in report['habitat']['telemetry'].items()]
            if rows:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        page=bundle/'report.html'
        text=page.read_text().replace('python simulator.py --replay','python v2/backend/habitat.py --replay')
        text=text.replace('<h1>Artificial Evolution research run</h1>','<h1>V2 physical habitat research run</h1>')
        text=text.replace('</body>', '<section><h2>Physical habitat configuration</h2><pre>'+html.escape(json.dumps(report['habitat']['config'],indent=2))+'</pre><p><a href="habitat.json">Habitat source record</a> · <a href="habitat_telemetry.csv">Physical costs and contacts</a></p></section></body>')
        page.write_text(text)
        manifest=json.loads((bundle/'manifest.json').read_text());manifest['engine_extension']=VERSION
        manifest['files_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(bundle.iterdir()) if p.name!='manifest.json'}
        (bundle/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        destination=root/bundle.name;bundle.rename(destination)
    return destination

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--replay',type=Path);parser.add_argument('--verify-bundle',type=Path)
    args=parser.parse_args()
    if args.verify_bundle:
        report=verify_bundle(args.verify_bundle)
        if json.loads((args.verify_bundle/'manifest.json').read_text()).get('engine_extension')!=VERSION:raise ValueError('Bundle does not declare physical habitat')
        replay_habitat(report);print('V2 habitat bundle verified and replayed exactly.')
    elif args.replay:replay_habitat(json.loads(args.replay.read_text()));print('V2 habitat replay matched exactly.')
    else:parser.error('Choose --replay or --verify-bundle')
