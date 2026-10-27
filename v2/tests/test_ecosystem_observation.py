"""Visual ecosystem observations must retain source identity and numerical authority."""
from dataclasses import asdict, replace
import unittest
from test_engine_bridge import config, scientific_state
from engine_bridge import EngineAdapter, encode, decode
from research_session import ResearchSession


class EcosystemObservationTests(unittest.TestCase):
    def test_food_identity_and_fields_are_stable_without_mutating_food(self):
        a=EngineAdapter(config())
        before=[asdict(f) for f in a.session.world.food]
        first=a.frame()['food_objects']
        self.assertEqual(first,a.frame()['food_objects'])
        self.assertEqual([{k: row[k] for k in before[0]} for row in first],before)
        self.assertEqual([asdict(f) for f in a.session.world.food],before)
        self.assertEqual(len({r['id'] for r in first}),len(before))

    def test_new_food_at_same_coordinates_gets_new_observer_identity(self):
        a=EngineAdapter(config());w=a.session.world
        first=a.frame()['food_objects'];original=w.food[0]
        w.food[0]=replace(original)
        changed=a.frame()['food_objects']
        self.assertNotEqual(changed[0]['id'],first[0]['id'])
        self.assertEqual(changed[1:],first[1:])
        w.food=[];self.assertEqual(a.frame()['food_objects'],[])
        self.assertEqual(a.food_observations,{})
        w.food=[original]
        self.assertNotEqual(a.frame()['food_objects'][0]['id'],first[0]['id'])

    def test_source_season_is_exact_and_does_not_alias_engine_history(self):
        a=EngineAdapter(config('seasons'));w=a.session.world
        frame=a.frame();context=frame['environment_context']
        for k,v in context['season'].items():self.assertEqual(v,w.environment_history[-1][k])
        self.assertEqual(context['food_target'],w.food_count)
        self.assertFalse(context['weather_simulated']);self.assertFalse(context['daylight_simulated'])
        context['season']['cluster_centers'][0][0]=-999
        self.assertNotEqual(w.environment_history[-1]['cluster_centers'][0][0],-999)

    def test_season_journal_follows_real_engine_transition_and_is_not_repeated(self):
        a=EngineAdapter(config('seasons'));a.frame()
        a.session.world._start_generation(2)
        a.session._observe_births()
        frame=a.frame();events=[e for e in frame['animation_events'] if e['kind']=='season']
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['context']['season'],'summer')
        self.assertEqual(events[0]['context']['generation'],2)
        self.assertFalse(a.frame(seen_animation=frame['animation_sequence'])['animation_events'])

    def test_nonseasonal_modes_do_not_claim_simulated_seasons(self):
        for mode in ('foraging','predator_prey','continuous'):
            frame=EngineAdapter(config(mode)).frame()
            self.assertIsNone(frame['environment_context']['season'])

    def test_capture_targets_are_exact_source_ledger_identities(self):
        a=EngineAdapter(config('predator_prey',population=4,predators=2,food_count=0))
        for c in a.session.world.creatures:c.x=c.y=250;c.heading=0
        a.session.world.creatures[1].x=800
        a.session.step();frame=a.frame()
        events=[e for e in frame['animation_events'] if e['kind']=='capture']
        self.assertTrue(events)
        for event in events:
            c=a.session.actors[event['id']]
            expected=[f"g{c.generation}:c{item['prey_id']}" for item in a.session.world.captures if item['predator_id']==c.creature_id]
            self.assertEqual(event['targets'],expected)
            self.assertTrue(expected)

    def test_opponents_are_only_original_sensor_visible_nearest_individuals(self):
        a=EngineAdapter(config('predator_prey',population=4,predators=2,food_count=0))
        for i,c in enumerate(a.session.world.creatures):c.x=250+i*10;c.y=250
        frame=a.frame();found=0
        for row in frame['agents']:
            c=a.session.actors[row['id']];perception=a.session.world.perceive_opponents(c)
            self.assertEqual('observed_opponent' in row,perception.visible)
            if perception.visible:
                found+=1;observed=row['observed_opponent'];other=a.session.actors[observed['id']]
                self.assertEqual((observed['x'],observed['y']),perception.target_position)
                self.assertNotEqual(c.species,other.species)
                self.assertEqual(observed['source'],'nearest visible opponent')
        self.assertGreater(found,0)
        self.assertEqual(decode(encode(frame))['food_objects'],frame['food_objects'])

    def test_extended_observations_leave_predator_rng_genomes_and_science_identical(self):
        cfg=config('predator_prey');a=EngineAdapter(cfg);reference=ResearchSession(cfg)
        for _ in range(180):
            a.session.step();reference.step();a.frame()
        self.assertEqual(scientific_state(a.session),scientific_state(reference))
        self.assertEqual(a.session.world._food_rng.getstate(),reference.world._food_rng.getstate())

if __name__=='__main__':unittest.main()
