"""Animation receipts are passive observations of the original numerical engine."""
from test_engine_bridge import config, scientific_state
from engine_bridge import EngineAdapter
from research_session import ResearchSession
import unittest

class AnimationObservationTests(unittest.TestCase):
    def test_meals_are_real_counter_increases_and_acknowledged_once(self):
        adapter=EngineAdapter(config())
        self.assertEqual(adapter.frame()['animation_events'],[])
        c=adapter.session.world.creatures[0];food=adapter.session.world.food[0]
        c.energy=10;c.x,c.y=food.x,food.y
        adapter.session.world._resolve_food_collisions()
        frame=adapter.frame();meal=[e for e in frame['animation_events'] if e['kind']=='meal']
        self.assertTrue(meal);self.assertEqual(meal[0]['id'],adapter.session.key(c))
        self.assertEqual(meal[0]['count'],c.food_eaten)
        self.assertEqual(adapter.frame(seen_animation=frame['animation_sequence'])['animation_events'],[])
        self.assertEqual(adapter.view_sequence,frame['animation_sequence'])

    def test_confirmed_death_is_not_repeated_and_retirement_is_not_death(self):
        adapter=EngineAdapter(config(population=4))
        c=adapter.session.world.creatures[0];c.energy=0;c.update_survival(1/60)
        frame=adapter.frame();deaths=[e for e in frame['animation_events'] if e['kind']=='death']
        self.assertEqual(len(deaths),1);self.assertEqual(deaths[0]['cause'],'starvation')
        self.assertEqual(deaths[0]['radius'],c.radius)
        self.assertEqual(adapter.frame(seen_animation=frame['animation_sequence'])['animation_events'],[])
        adapter=EngineAdapter(config('predator_prey',population=4,predators=1,episode_seconds=.1))
        for index,c in enumerate(adapter.session.world.creatures):c.x=100+index*200;c.y=100
        for _ in range(7):adapter.session.step()
        events=adapter.frame()['animation_events']
        self.assertTrue(any(e['kind']=='retire' for e in events))
        self.assertFalse(any(e['kind']=='death' for e in events))
        self.assertFalse(any(e['kind']=='reproduce' for e in events))

    def test_real_continuous_births_link_reproduction_and_maturity(self):
        adapter=EngineAdapter(config('continuous',maturity_age=.1,birth_cooldown=.1,
                                     body_mutation_rate=0,population_cap=24))
        for _ in range(30):adapter.session.step()
        frame=adapter.frame();births=[e for e in frame['animation_events'] if e['kind']=='birth']
        self.assertTrue(births)
        for event in births:
            self.assertTrue(event['continuous']);self.assertEqual(event['maturity_age'],.1)
            self.assertEqual(event['parent'],adapter.session.births[event['id']]['parent'])
            self.assertTrue(any(e['kind']=='reproduce' and e['child']==event['id']
                                for e in frame['animation_events']))
        child=adapter.session.actors[births[0]['id']]
        child.energy=0;child.update_survival(1/60)
        self.assertTrue(any(e['kind']=='death' and e['id']==births[0]['id']
                            for e in adapter.frame()['animation_events']))

    def test_birth_then_parent_death_between_frames_preserves_both_receipts(self):
        adapter=EngineAdapter(config('continuous',maturity_age=.1,birth_cooldown=.1,
                                     body_mutation_rate=0,population_cap=24))
        for _ in range(30):adapter.session.step()
        birth=next(b for b in adapter.session.births.values() if b['parent'])
        parent=adapter.session.actors[birth['parent']]
        parent.energy=0;adapter.session.step()
        self.assertNotIn(parent,adapter.session.world.creatures)
        events=adapter.frame()['animation_events']
        self.assertTrue(any(e['kind']=='reproduce' and e['child']==birth['key'] for e in events))
        self.assertTrue(any(e['kind']=='death' and e['id']==birth['parent'] for e in events))

    def test_capture_receipts_and_directional_telemetry_come_from_python(self):
        adapter=EngineAdapter(config('predator_prey',population=4,predators=2,food_count=0))
        for c in adapter.session.world.creatures:c.x=c.y=250;c.heading=0
        adapter.session.world.creatures[1].x=800
        adapter.session.step();frame=adapter.frame()
        self.assertTrue(any(e['kind']=='capture' for e in frame['animation_events']))
        self.assertTrue(any(e['kind']=='death' and e['cause']=='predation' for e in frame['animation_events']))
        for row in frame['agents']:
            c=adapter.session.actors[row['id']]
            self.assertEqual(row['toward_seconds'],c.toward_seconds)
            self.assertEqual(row['away_seconds'],c.away_seconds)
            self.assertEqual(row['max_speed'],c.max_speed)

    def test_observing_life_events_never_changes_the_scientific_run(self):
        cfg=config('continuous',maturity_age=.1,birth_cooldown=.1,population_cap=24)
        adapter=EngineAdapter(cfg);reference=ResearchSession(cfg)
        for _ in range(180):
            adapter.session.step();reference.step();adapter.frame()
        self.assertEqual(scientific_state(adapter.session),scientific_state(reference))
        self.assertLessEqual(len(adapter.view_events),4096)

if __name__=='__main__':unittest.main()
