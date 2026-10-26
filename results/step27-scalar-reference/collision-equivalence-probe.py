import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from world import World
from simulation import EvolutionSimulation

class FastWorld(World):
 def _resolve_food_collisions(self):
  eaten=set()
  if self.creatures and self.food:
   food=np.array([(f.x,f.y,f.radius) for f in self.food])
   bodies=np.array([(c.x,c.y,c.radius) for c in self.creatures])
   dx=food[:,0,None]-bodies[None,:,0];dy=food[:,1,None]-bodies[None,:,1]
   near=dx*dx+dy*dy<=(food[:,2,None]+bodies[None,:,2])**2+1e-9
   candidates={}
   for fi,ci in zip(*np.nonzero(near)):candidates.setdefault(int(fi),[]).append(self.creatures[int(ci)])
   for i,actors in candidates.items():
    f=self.food[i]
    eater=min((c for c in actors if c.alive and c.energy<c.energy_capacity and f.overlaps_circle(c.x,c.y,c.radius)),
     key=lambda c:((c.x-f.x)**2+(c.y-f.y)**2,c.creature_id),default=None)
    if eater is not None and eater.eat(f):eaten.add(i);self.total_food_eaten+=1
  self.food=[f for i,f in enumerate(self.food) if i not in eaten]
  for _ in range(self.food_count-len(self.food)):self.food.append(self._spawn_food())

for controller in ('random','greedy','neural'):
 for distribution in ('uniform','clustered'):
  a=World(seed=270027,controller=controller,food_distribution=distribution,fixed_speed=60,evolution_enabled=False)
  b=FastWorld(seed=270027,controller=controller,food_distribution=distribution,fixed_speed=60,evolution_enabled=False)
  times=[]
  for w in (a,b):
   t=time.process_time()
   for _ in range(10):w.update(1.)
   times.append(time.process_time()-t)
  assert a.creatures==b.creatures and a.dead_creatures==b.dead_creatures
  assert a.food==b.food and a._food_rng.getstate()==b._food_rng.getstate() and a._motion_rng.getstate()==b._motion_rng.getstate()
  assert EvolutionSimulation(a).report()==EvolutionSimulation(b).report()
  assert a._alive_time==b._alive_time and a._food_visible_time==b._food_visible_time and a._food_facing_time==b._food_facing_time
  print(controller,distribution,'CPU times',times,'speedup',times[0]/times[1],flush=True)
