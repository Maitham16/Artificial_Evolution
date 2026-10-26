"""Scientific-kernel parity, ancestry, observation purity, and portable exports."""

from dataclasses import replace
import csv
import json
import tempfile
from pathlib import Path
import unittest

import numpy as np

from compare_creatures import initial_conditions_digest
from experiment_selection import ParentPolicyWorld
from research_session import (ALGORITHMS, MODES, ResearchSession, RunConfig, export_bundle,
                              file_hash, replay_run, verify_bundle)
from simulation import EvolutionSimulation


class ConfigurationTests(unittest.TestCase):
    def test_presets_roundtrip_and_create_every_existing_mode(self):
        for mode in MODES:
            config = RunConfig.load(Path(__file__).parent / "configs" / f"{mode}.json")
            self.assertEqual(RunConfig.from_dict(config.to_dict()), config)
            session = ResearchSession(config)
            for _ in range(4): self.assertTrue(session.step())
            report, genomes = session.snapshot()
            self.assertEqual(len(genomes), 100)
            self.assertEqual(replay_run(report).snapshot()[0]["individuals"], report["individuals"])

    def test_invalid_settings_rejected_before_world_construction(self):
        cases = [{"mode": "unknown"}, {"schema_version": True}, {"seed": True}, {"seed": -1},
                 {"mutation_rate": float("nan")}, {"mutation_rate": 2}, {"duration": .001},
                 {"population": 0}, {"population": 301}, {"food_count": -1}, {"unknown": 1},
                 {"mode": "social", "algorithm": "group", "population": 21},
                 {"mode": "continuous", "algorithm": "neutral"},
                 {"mode": "seasons", "environment": "uniform"}, {"groups": 0},
                 {"season_food": [1, 2]}, {"sample_interval": 0}, {"signaling": 1},
                 {"mode": "predator_prey", "algorithm": "coevolution", "predators": 100}]
        for values in cases:
            with self.subTest(values=values), self.assertRaises((ValueError, TypeError)):
                RunConfig.from_dict({**RunConfig().to_dict(), **values})

    def test_clonal_and_social_effective_configuration_matches_physics(self):
        clonal = ResearchSession(replace(RunConfig(), mode="continuous", algorithm="clonal"))
        self.assertEqual(clonal.config.mutation_rate, 0)
        self.assertEqual(clonal.config.body_mutation_rate, 0)
        self.assertEqual(clonal.world.mutation_rate, 0)
        social = ResearchSession(replace(RunConfig(), mode="social", algorithm="group"))
        self.assertEqual(social.config.body_mutation_rate, social.world.body_mutation_rate)


class ResearchSessionTests(unittest.TestCase):
    def test_monitor_and_fast_broad_phase_preserve_canonical_parent_policy(self):
        for algorithm, policy in (("selection", "selection"), ("neutral", "random_parent")):
            config = replace(RunConfig(), population=8, food_count=0, generations=2, algorithm=algorithm)
            session = ResearchSession(config)
            world = ParentPolicyWorld(seed=config.seed, population_size=8, food_count=0,
                                      fixed_speed=60., parent_policy=policy)
            reference = EvolutionSimulation(world, auto_advance=False, generation_limit=2)
            self.assertEqual(initial_conditions_digest(session.world), initial_conditions_digest(world))
            while not session.finished:
                if world.final_evaluation and not reference.finished:
                    self.assertTrue(reference.advance_generation())
                self.assertTrue(session.step())
                reference.update(1 / 60)
            self.assertEqual(session.simulation.report(), reference.report())
            self.assertEqual(session.world.transitions, world.transitions)
            for a, b in zip(session.world.dead_creatures, world.dead_creatures):
                self.assertEqual(a, b)
                self.assertEqual(a.brain, b.brain)
            report, _ = session.snapshot()
            self.assertEqual(len(report["individuals"]), 16)
            self.assertTrue(all(r["parent"] in session.births for r in report["individuals"] if r["generation"] == 2))
            replay_run(report)

    def test_frozen_founder_weights_and_fresh_baseline_roots_are_distinct(self):
        for algorithm in ("founder", "random", "greedy"):
            session = ResearchSession(replace(RunConfig(), population=4, food_count=0, generations=2, algorithm=algorithm))
            original = {c.creature_id: c.brain.copy() for c in session.world.creatures}
            while session.world.generation == 1: session.step()
            if algorithm == "founder":
                for c in session.world.creatures:
                    self.assertEqual(c.brain, original[c.creature_id])
                    self.assertEqual(session.births[session.key(c)]["founder"], f"g1:c{c.creature_id}")
            else:
                self.assertTrue(all(session.births[session.key(c)]["parent"] is None for c in session.world.creatures))
                self.assertIsNone(session.metrics()["neural_rms"])

    def test_snapshots_do_not_change_continuous_physics_or_model_history(self):
        config = replace(RunConfig(), mode="continuous", algorithm="funded", population=8, population_cap=20)
        observed, reference = ResearchSession(config), ResearchSession(config)
        for tick in range(80):
            observed.step()
            reference.step()
            if tick % 7 == 0:
                before = list(observed.world.snapshots)
                observed.snapshot()
                self.assertEqual(observed.world.snapshots, before)
        a, _ = observed.snapshot()
        b, _ = reference.snapshot()
        for key in ("metrics", "samples", "individuals", "simulation"):
            self.assertEqual(a[key], b[key])
        replay_run(a)

    def test_continuous_paid_births_keep_complete_parent_and_genome_records(self):
        config = replace(RunConfig(), mode="continuous", algorithm="funded", population=4, population_cap=20,
                         food_count=0, maturity_age=.5, birth_cooldown=.5, mutation_rate=0, body_mutation_rate=0)
        session = ResearchSession(config)
        for _ in range(60): session.step()
        report, genomes = session.snapshot()
        self.assertGreater(len(genomes), 4)
        for person in report["individuals"]:
            if person["parent"]:
                self.assertEqual(person["initial_energy"], 40)
                self.assertEqual(person["founder"], session.births[person["parent"]]["founder"])
                self.assertEqual(person["depth"], 1)
        replay_run(report)

    def test_censored_social_survivors_and_mode_specific_fitness_are_preserved(self):
        for mode, algorithm in (("social", "group"), ("predator_prey", "coevolution")):
            config = replace(RunConfig(), mode=mode, algorithm=algorithm, population=20, predators=4,
                             groups=2, food_count=20, episode_seconds=.1, generations=2)
            session = ResearchSession(config)
            for _ in range(7): session.step()
            report, _ = session.snapshot()
            self.assertTrue(any(p["censored"] for p in report["individuals"] if p["generation"] == 1))
            self.assertTrue(all(p["parent"] in session.births for p in report["individuals"] if p["generation"] == 2))
            members = [*session.world.creatures, *session.world.dead_creatures]
            expected = np.mean([c.age if mode == "social" else c.fitness for c in members if getattr(c, "species", "prey") == "prey"])
            self.assertAlmostEqual(report["metrics"]["mean_fitness"], expected)
            replay_run(report)

    def test_pause_manual_transitions_and_recorded_controls_replay(self):
        session = ResearchSession(replace(RunConfig(), population=4, food_count=0, generations=2))
        session.set_control("paused", True)
        session.update(.1)
        self.assertEqual(session.ticks, 0)
        session.set_control("paused", False)
        session.set_control("speed", 20)
        session.set_control("automatic", False)
        while session.world.final_evaluation is None: session.step()
        self.assertFalse(session.step())
        self.assertTrue(session.advance())
        for _ in range(5): session.step()
        replay_run(session.snapshot()[0])
        with self.assertRaises(ValueError): session.set_control("speed", True)
        with self.assertRaises(ValueError): session.set_control("unknown", 1)

    def test_render_tick_budget_never_skips_physics(self):
        a, b = ResearchSession(RunConfig(population=4)), ResearchSession(RunConfig(population=4))
        a.set_control("speed", 20)
        a.update(.1, max_ticks=3)
        self.assertEqual(a.ticks, 3)
        for _ in range(3): b.step()
        self.assertEqual(a.snapshot()[0]["individuals"], b.snapshot()[0]["individuals"])
        with self.assertRaises(ValueError): a.update(.1, max_ticks=0)

    def test_corrupted_replay_data_and_future_controls_are_rejected(self):
        session = ResearchSession(RunConfig(population=4))
        for _ in range(3): session.step()
        report, _ = session.snapshot()
        report["individuals"][0]["energy"] += 1
        with self.assertRaises(ValueError): replay_run(report)
        report, _ = session.snapshot()
        report["execution"]["controls"] = [{"tick": 20, "action": "paused", "value": True}]
        with self.assertRaises(ValueError): replay_run(report)

    def test_complete_bundle_formats_hashes_genomes_and_replay(self):
        session = ResearchSession(RunConfig(population=4))
        for _ in range(6): session.step()
        report, bank = session.snapshot()
        with tempfile.TemporaryDirectory() as temp:
            path = export_bundle(report, bank, temp)
            self.assertEqual(verify_bundle(path), report)
            replay_run(verify_bundle(path))
            for ext in ("png", "svg", "pdf"):
                self.assertGreater((path / f"population.{ext}").stat().st_size, 1000)
            with (path / "individuals.csv").open() as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 4)
            with np.load(path / "genomes.npz", allow_pickle=False) as a:
                self.assertEqual(a["parameter_0"].shape, (4, 8, 8))
            second = export_bundle(report, bank, temp)
            self.assertNotEqual(path, second)
            (path / "population.csv").write_text("corrupt")
            with self.assertRaises(ValueError): verify_bundle(path)

    def test_unsafe_manifests_and_changed_numeric_genomes_are_rejected(self):
        session = ResearchSession(RunConfig(population=4))
        report, bank = session.snapshot()
        with tempfile.TemporaryDirectory() as temp:
            path = export_bundle(report, bank, temp)
            manifest = json.loads((path / "manifest.json").read_text())
            manifest["files_sha256"]["../escape"] = "anything"
            (path / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): verify_bundle(path)
            del manifest["files_sha256"]["../escape"]
            with np.load(path / "genomes.npz", allow_pickle=False) as a:
                values = {k: a[k].copy() for k in a.files}
            values["parameter_0"][0, 0, 0] += 1
            np.savez_compressed(path / "genomes.npz", **values)
            manifest["files_sha256"]["genomes.npz"] = file_hash(path / "genomes.npz")
            (path / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): verify_bundle(path)


if __name__ == "__main__":
    unittest.main()
