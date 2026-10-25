"""Control fitness dependence while retaining identical mutation and inheritance."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from analyze_intelligence import bank_digest
from compare_creatures import complete_generation, derived_seed, genome_digest, initial_conditions_digest
from creature import create_population
from experiment_selection import (ARMS, CONDITIONS, ParentPolicyWorld, RecordedMutationRNG,
    analyze_results, load_models, main, run_study, train_pair, validate_transitions)
from reproduction import reproduce_brains
from simulation import EvolutionSimulation
from plot_selection import build_selection_figure, save_selection_plot
from world import World


def short_population(*args):
    creatures = create_population(*args)
    for c in creatures:
        c.lifespan = 0.005
    return creatures


class ParentChoiceTests(unittest.TestCase):
    def test_recording_draws_does_not_change_the_canonical_reproducer(self):
        parents = create_population(1000, 600, random.Random(42), 20)
        recorded = RecordedMutationRNG(42)
        children = reproduce_brains(parents, recorded)
        ordinary = reproduce_brains(parents, np.random.default_rng(42))
        self.assertEqual([c.parent_id for c in children], [c.parent_id for c in ordinary])
        self.assertEqual([c.mutations for c in children], [c.mutations for c in ordinary])
        for a, b in zip(children, ordinary):
            self.assertEqual(a.brain, b.brain)
        self.assertEqual(recorded.calls, 801)

    def test_selection_uses_the_same_physics_and_reproducer_with_common_parent_order(self):
        with patch("world.create_population", side_effect=short_population):
            canonical = World(seed=42, fixed_speed=60.0)
            selected = ParentPolicyWorld(seed=42, fixed_speed=60.0)
            for generation in range(1, 4):
                self.assertEqual(initial_conditions_digest(canonical), initial_conditions_digest(selected))
                self.assertEqual(genome_digest(canonical.creatures), genome_digest(selected.creatures))
                complete_generation(EvolutionSimulation(canonical, auto_advance=False))
                complete_generation(EvolutionSimulation(selected, auto_advance=False))
                self.assertEqual(canonical.generation_stats, selected.generation_stats)
                if generation < 3:
                    # Apply the experiment's neutral ID order to the canonical reproducer.
                    records = {c.creature_id: c for c in canonical.dead_creatures}
                    parents = [records[key] for key in sorted(canonical.final_evaluation.selected_ids)]
                    seed = random.Random(f"mutation:42:generation:{generation + 1}").getrandbits(128)
                    children = reproduce_brains(parents, np.random.default_rng(seed))
                    canonical._start_generation(generation + 1, children)
                    self.assertTrue(selected.advance_generation())

    def test_random_parent_pool_includes_all_early_deaths_and_ignores_fitness(self):
        with patch("world.create_population", side_effect=short_population):
            world = ParentPolicyWorld(seed=42, fixed_speed=60.0, parent_policy="random_parent")
            complete_generation(EvolutionSimulation(world, auto_advance=False))
            # Make IDs 1..20 the top-ranked cohort, without excluding others from reproduction.
            for c in world.dead_creatures:
                c.food_eaten = 1000 - c.creature_id
            from selection import evaluate_population
            world.final_evaluation = evaluate_population(world.dead_creatures)
            self.assertEqual(world.final_evaluation.selected_ids, tuple(range(1, 21)))
            self.assertTrue(world.advance_generation())
            record = world.transitions[0]
            expected = sorted(random.Random(derived_seed("step18:random-parents:42:generation:2")).sample(list(range(1, 101)), 20))
            self.assertEqual(record["parent_ids"], expected)
            self.assertTrue(any(key > 20 for key in expected))
            self.assertEqual(record["candidate_ids"], list(range(1, 101)))
            self.assertEqual(Counter(c.parent_id for c in world.creatures), Counter({key: 5 for key in expected}))

    def test_both_policies_inherit_and_mutate_instead_of_resampling_brains(self):
        with patch("world.create_population", side_effect=short_population):
            for policy in ARMS:
                world = ParentPolicyWorld(seed=42, fixed_speed=60.0, parent_policy=policy, mutation_rate=0)
                old = {c.creature_id: c.brain.copy() for c in world.creatures}
                complete_generation(EvolutionSimulation(world, auto_advance=False))
                self.assertTrue(world.advance_generation())
                for c in world.creatures:
                    self.assertEqual(c.brain, old[c.parent_id])
                    self.assertEqual(c.mutation_count, 0)
                    self.assertFalse(np.shares_memory(c.brain.input_weights, old[c.parent_id].input_weights))

    def test_only_selection_changes_parent_choice_when_fitness_is_reversed(self):
        from selection import evaluate_population
        with patch("world.create_population", side_effect=short_population):
            for policy in ARMS:
                worlds = [ParentPolicyWorld(seed=42, fixed_speed=60.0, parent_policy=policy) for _ in range(2)]
                for index, world in enumerate(worlds):
                    complete_generation(EvolutionSimulation(world, auto_advance=False))
                    for c in world.dead_creatures:
                        c.food_eaten = c.creature_id if index else 101 - c.creature_id
                    world.final_evaluation = evaluate_population(world.dead_creatures)
                    world.advance_generation()
                parents = [w.transitions[0]["parent_ids"] for w in worlds]
                if policy == "random_parent":
                    self.assertEqual(parents[0], parents[1])
                    self.assertEqual(genome_digest(worlds[0].creatures), genome_digest(worlds[1].creatures))
                else:
                    self.assertNotEqual(parents[0], parents[1])
                    self.assertEqual(set(parents[0]), set(range(1, 21)))
                    self.assertEqual(set(parents[1]), set(range(81, 101)))

    def test_pair_has_identical_mutation_draws_bottlenecks_founders_and_training_starts(self):
        with patch("world.create_population", side_effect=short_population):
            training, starts, transitions, banks = train_pair(42, 3)
        self.assertEqual(starts["selection"], starts["random_parent"])
        self.assertEqual(training["selection"]["generations"][0], training["random_parent"]["generations"][0])
        for a, b in zip(transitions["selection"], transitions["random_parent"]):
            self.assertEqual(a["mutation_draws_sha256"], b["mutation_draws_sha256"])
            self.assertEqual(a["mutation_rng_calls"], b["mutation_rng_calls"])
            self.assertEqual(a["offspring_mutation_counts"], b["offspring_mutation_counts"])
            self.assertEqual(len(a["parent_ids"]), len(b["parent_ids"]))
            self.assertTrue(any(n > 0 for n in a["offspring_mutation_counts"]))
        self.assertEqual(set(banks), set(CONDITIONS))
        self.assertNotEqual(bank_digest(banks["selection"]), bank_digest(banks["random_parent"]))

    def test_incomplete_generations_invalid_policies_and_restart_are_safe(self):
        for policy in ("unknown", None):
            with self.assertRaises(ValueError):
                ParentPolicyWorld(parent_policy=policy)
        with self.assertRaises(ValueError):
            ParentPolicyWorld(evolution_enabled=False)
        with patch("world.create_population", side_effect=short_population):
            w = ParentPolicyWorld(seed=42, fixed_speed=60.0, parent_policy="random_parent")
            self.assertFalse(w.advance_generation())
            self.assertEqual(w.transitions, [])
            initial = genome_digest(w.creatures)
            complete_generation(EvolutionSimulation(w, auto_advance=False))
            w.advance_generation()
            w.regenerate_population(42)
            self.assertEqual(w.transitions, [])
            self.assertEqual(w.parent_policy, "random_parent")
            self.assertEqual(genome_digest(w.creatures), initial)


class SelectionStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("world.create_population", side_effect=short_population):
            cls.report = run_study([11, 22], generations=2, repeats=2)

    def test_all_controls_are_matched_frozen_and_held_out(self):
        r = self.report
        self.assertEqual(r["protocol"]["planned_new_training_cohorts"], 8)
        self.assertEqual(r["protocol"]["planned_test_cohorts"], 36)
        for trial in r["trials"]:
            self.assertEqual(len(trial["tests"]), 6)
            for test in trial["tests"]:
                self.assertEqual(set(test["conditions"]), set(CONDITIONS))
                self.assertEqual(len({v["initial_conditions"] for v in test["conditions"].values()}), 1)
                for name, value in test["conditions"].items():
                    self.assertEqual(value["genomes_sha256"], trial["genome_hashes"][name])
                    self.assertNotIn(value["initial_conditions"], trial["training_initial_conditions"]["selection"])
                    self.assertFalse(value["report"]["evolution_enabled"])
                    self.assertEqual(value["report"]["controller"], "neural")

    def test_repeats_keep_seed_pairs_as_the_unit_and_primary_family_has_six_tests(self):
        r = deepcopy(self.report)
        for trial, outcomes in zip(r["trials"], ((2, 4), (6, 8))):
            for test, value in zip([t for t in trial["tests"] if t["environment"] == "uniform"], outcomes):
                stats = test["conditions"]["selection"]["report"]["generations"][0]
                stats.update(mean_food_eaten=value, mean_fitness=stats["mean_survival_seconds"] + 10 * value)
        result = analyze_results(r)
        self.assertEqual(result["environments"]["uniform"]["seed_values"]["selection"]["mean_food_eaten"], [3, 7])
        count = 0
        for data in result["environments"].values():
            for label, metrics in data["comparisons"].items():
                for metric, row in metrics.items():
                    self.assertEqual(row["n_pairs"], 2)
                    if "holm_adjusted_p" in row:
                        count += 1
                        self.assertEqual(metric, "mean_fitness")
                        self.assertNotEqual(label, "random_parent_vs_founder")
        self.assertEqual(count, 6)
        self.assertFalse(result["selection_improvement_supported_in_all_environments"])

    def test_tampered_parent_choice_mutation_and_incomplete_reports_are_rejected(self):
        def transition(r, arm="random_parent"):
            return r["trials"][0]["transitions"][arm][0]
        changes = [
            lambda r: r["trials"].pop(),
            lambda r: r["trials"][0]["tests"].pop(),
            lambda r: transition(r).update(parent_ids=list(range(1, 21))),
            lambda r: transition(r).update(candidate_ids=list(range(1, 21))),
            lambda r: transition(r).update(mutation_draws_sha256="bad"),
            lambda r: transition(r).update(offspring_parent_ids=[1] * 100),
            lambda r: r["trials"][0]["training"]["random_parent"].update(evolution_enabled=False),
            lambda r: r["trials"][0]["tests"][0]["conditions"]["selection"].update(genomes_sha256="bad"),
            lambda r: r["trials"][0]["tests"][0].update(seed=0),
        ]
        for change in changes:
            r = deepcopy(self.report)
            change(r)
            with self.assertRaises(ValueError):
                analyze_results(r)

    def test_serial_parallel_and_incomplete_checkpoints(self):
        checkpoints = []
        with patch("world.create_population", side_effect=short_population), patch("experiment_selection.ProcessPoolExecutor", ThreadPoolExecutor):
            r = run_study([11, 22], generations=2, repeats=2, workers=2,
                          checkpoint=lambda r: checkpoints.append(deepcopy(r)))
        self.assertEqual(r, self.report)
        self.assertEqual([r["status"] for r in checkpoints], ["running", "running", "running", "complete"])
        with self.assertRaises(ValueError):
            build_selection_figure(checkpoints[-2])

    def test_model_roundtrip_reuse_preserves_both_inherited_histories(self):
        with tempfile.TemporaryDirectory() as directory, patch("world.create_population", side_effect=short_population):
            original = run_study([11, 22], generations=2, models_dir=directory)
            with patch("experiment_selection.train_pair", side_effect=AssertionError("Must not retrain")):
                replay = run_study([11, 22], generations=2, models_dir=directory, reuse=True)
            self.assertEqual(original["trials"], replay["trials"])
            self.assertEqual(original["analysis"], replay["analysis"])
            self.assertEqual(replay["protocol"]["planned_new_training_cohorts"], 0)
            path = Path(directory) / "seed-11.npz"
            training, starts, transitions, banks = load_models(path, 11, 2)
            validate_transitions(training, starts, transitions, 11, 2)
            self.assertEqual(bank_digest(banks["founder"]), original["trials"][0]["genome_hashes"]["founder"])
            banks["founder"][1].input_weights[0, 0] += 1
            self.assertNotEqual(bank_digest(banks["founder"]), bank_digest(load_models(path, 11, 2)[3]["founder"]))
            with self.assertRaises(ValueError):
                load_models(path, 22, 2)
            with self.assertRaises(ValueError):
                run_study([11, 22], generations=2, models_dir=directory)

    def test_training_curves_start_identically_and_plot_exports(self):
        analysis = self.report["analysis"]
        a, b = [analysis["training_curves"][arm] for arm in ARMS]
        for field in ("mean_fitness", "low", "high"):
            self.assertEqual(a[field][0], b[field][0])
        figure = build_selection_figure(self.report)
        self.assertEqual(len(figure.axes), 7)
        self.assertEqual(len(figure.axes[0].lines), 2)
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("png", "svg", "pdf"):
                output = Path(directory) / f"figure.{suffix}"
                save_selection_plot(self.report, output)
                self.assertGreater(output.stat().st_size, 1000)

    def test_cli_saves_protocol_models_and_complete_report(self):
        with tempfile.TemporaryDirectory() as directory, patch("world.create_population", side_effect=short_population):
            output, protocol = Path(directory) / "study.json", Path(directory) / "protocol.json"
            args = ["experiment_selection.py", "--seeds", "11", "22", "--generations", "2", "--workers", "1",
                    "--models-dir", str(Path(directory) / "models"), "--output", str(output), "--protocol-output", str(protocol)]
            with patch("sys.argv", args), redirect_stdout(io.StringIO()):
                self.assertEqual(main(), 0)
            report = json.loads(output.read_text())
            self.assertEqual(report["status"], "complete")
            self.assertEqual(report["protocol"], json.loads(protocol.read_text())["protocol"])
            self.assertTrue((Path(directory) / "models/seed-11.npz").exists())
            args[args.index("--output") + 1] = "results/step17-strategy.json"
            with patch("sys.argv", args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main()

    def test_invalid_budgets_fail_before_work(self):
        for kwargs in ({"seeds": [1]}, {"seeds": [1, 1]}, {"generations": 1}, {"workers": 0}, {"repeats": 0}, {"reuse": True}):
            with self.assertRaises(ValueError):
                run_study(**kwargs)


if __name__ == "__main__":
    unittest.main()
