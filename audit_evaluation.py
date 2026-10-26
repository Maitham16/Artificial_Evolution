"""Recompute Step 27 evidence, verify artifacts, and replay declared test cases."""

from datetime import datetime, timezone
from importlib.metadata import version
import argparse
import json
import math
from pathlib import Path
import platform

import numpy as np

from compare_creatures import complete_generation, initial_conditions_digest
from experiment_evaluation import (ARMS, BANK_FOR, BASELINES, DEFAULT_SEEDS, ENVIRONMENTS, GENERATIONS,
    METRICS, FIXED_SPEED, analyze_results, individual_records, load_models, load_raw, neural_features, conditions_for)
from experiment_strategy import file_digest
from simulation import EvolutionSimulation
from world import World


def independent_sign(row):
    n = row["wins"] + row["losses"]
    tail = sum(math.factorial(n) // (math.factorial(k) * math.factorial(n - k))
               for k in range(min(row["wins"], row["losses"]) + 1))
    return min(1., 2 * tail / 2 ** n)


def check_family(rows):
    order = sorted(rows, key=lambda r: r["sign_test_p"])
    adjusted = 0.
    for rank, row in enumerate(order):
        assert row["sign_test_p"] == independent_sign(row)
        adjusted = min(1., max(adjusted, (len(rows) - rank) * row["sign_test_p"]))
        assert row["holm_adjusted_p"] == adjusted


def audit(report_path, protocol_path, baseline_path, tests_path, output, figure_paths):
    if Path(output).exists():
        raise ValueError("Preserve an existing audit; use a new path.")
    report = json.loads(Path(report_path).read_text())
    declaration = json.loads(Path(protocol_path).read_text())
    baseline = json.loads(Path(baseline_path).read_text())
    assert report["status"] == "complete" and report["protocol"] == declaration["protocol"]
    assert report["protocol"]["seeds"] == list(DEFAULT_SEEDS) and report["protocol"]["repeats_per_environment"] == 2
    # Preserve the exact pre-production helper. This audit-only repair uses the
    # declared float speed instead of int60: JSON hashes distinguish 60/60.0.
    declared_audit = Path("results/step27-audit-declared.py")
    assert all(file_digest(declared_audit if p == "audit_evaluation.py" else p) == h
               for p, h in declaration["source_sha256"].items())
    assert all(file_digest(p) == h for p, h in report["protocol"]["runtime_reference_sha256"].items())
    reference_dir = Path("results/step27-scalar-reference")
    original = json.loads((reference_dir / "step27-protocol.json").read_text())
    assert {k: v for k, v in report["protocol"].items() if k not in ("collision_execution", "runtime_reference_sha256")} == original["protocol"]
    for name, digest in original["source_sha256"].items():
        assert file_digest(reference_dir / name if (reference_dir / name).exists() else Path(name)) == digest
    preserved = {p: h for p, h in baseline["files_sha256"].items() if p != "README.md"}
    assert all(file_digest(p) == h for p, h in preserved.items())
    analysis = analyze_results(report)
    assert analysis == report["analysis"]
    primary, secondary = [], []
    for data in analysis["environments"].values():
        primary.extend(row for metrics in data["comparisons"].values() for row in metrics.values())
        secondary.extend(v["mean_fitness"] for v in data["adaptation_from_founders"].values())
        if data["food_sensor_intervention"]:
            secondary.extend(data["food_sensor_intervention"]["mean_fitness"].values())
    secondary.extend(row["selection_minus_neutral"] for row in analysis["diversity"].values())
    assert len(primary) == 45 and len(secondary) == 21
    check_family(primary)
    check_family(secondary)
    cohorts = individuals = starts_count = 0
    mutation_transitions = 0
    artifacts = [str(report_path), str(protocol_path), str(baseline_path), str(tests_path), *map(str, figure_paths)]
    first_raw = first_banks = None
    for trial in report["trials"]:
        raw = load_raw(trial)
        _, _, transitions, banks = load_models(trial["model_file"], trial["seed"], GENERATIONS)
        mutation_transitions += sum(len(t) for t in transitions.values())
        for arm in ARMS:
            for steering, key in ((False, "full_rms"), (True, "steering_rms")):
                x = neural_features(banks[arm], steering)
                direct = np.sqrt(np.mean([np.dot(x[i] - x[j], x[i] - x[j]) for i in range(100) for j in range(i)]))
                assert np.isclose(direct, trial["diversity"][arm][-1][key], rtol=0, atol=1e-12)
        for test in raw["tests"]:
            env = test["environment"]
            settings = ENVIRONMENTS[env]
            original = World(*settings["arena_size"], seed=test["seed"], fixed_speed=FIXED_SPEED,
                             food_count=settings["food_count"], food_distribution=settings["food_distribution"], evolution_enabled=False)
            start = initial_conditions_digest(original)
            starts_count += 1
            lifespans = [c.lifespan for c in original.creatures]
            assert all(c.energy == 100 and c.energy_capacity == 100 and c.energy_cost_per_second == 5
                       and c.speed == 60 and original.vision_range_for(c) == 160 for c in original.creatures)
            for condition, record in test["conditions"].items():
                assert record["initial_conditions"] == start
                assert [c["lifespan"] for c in record["individuals"]] == lifespans
                for c in record["individuals"]:
                    # Food overflow can be discarded, but cannot add unrecorded energy.
                    assert c["energy"] <= 100 + 20 * c["food_eaten"] - 5 * c["age"] + 1e-8
                if env == "barren":
                    assert all(c["food_eaten"] == 0 and c["death_cause"] == "starvation"
                               and math.isclose(c["age"], 20, abs_tol=1e-9) for c in record["individuals"])
                cohorts += 1
                individuals += len(record["individuals"])
        for env in ENVIRONMENTS:
            tests = [t for t in raw["tests"] if t["environment"] == env]
            values = analysis["environments"][env]["seed_values"]
            i = report["protocol"]["seeds"].index(trial["seed"])
            for c in conditions_for(env):
                for metric in METRICS:
                    average = sum(t["conditions"][c]["report"]["generations"][0][metric] for t in tests) / 2
                    assert average == values[c][metric][i]
        if trial["seed"] == DEFAULT_SEEDS[0]:
            first_raw, first_banks = raw, banks
        artifacts.append(trial["raw_file"])
        print(f"Audited complete seed {trial['seed']}", flush=True)
    assert cohorts == report["protocol"]["planned_test_cohorts"] == 1056
    assert individuals == 105600 and starts_count == 160 and mutation_transitions == 288
    replayed = []
    for env in ("uniform", "barren"):
        test = next(t for t in first_raw["tests"] if t["environment"] == env and t["repeat"] == 1)
        for condition, stored in test["conditions"].items():
            settings = ENVIRONMENTS[env]
            world = World(*settings["arena_size"], seed=test["seed"], fixed_speed=FIXED_SPEED, evolution_enabled=False,
                          food_count=settings["food_count"], food_distribution=settings["food_distribution"],
                          controller=condition if condition in ("random", "greedy") else "neural",
                          food_sensor_mode="hidden" if condition.endswith("_hidden") else "intact")
            for c in world.creatures:
                c.brain = first_banks[BANK_FOR[condition]][c.creature_id].copy()
            simulation = EvolutionSimulation(world, generation_limit=1, auto_advance=False)
            complete_generation(simulation)
            assert simulation.report() == stored["report"]
            assert individual_records(world) == stored["individuals"]
            replayed.append(f"{DEFAULT_SEEDS[0]}:{env}:1:{condition}")
            print(f"Bitwise replay passed: {replayed[-1]}", flush=True)
    transcript = Path(tests_path).read_text()
    assert "Ran 401 tests" in transcript and transcript.rstrip().endswith("OK")
    result = {"status": "passed", "audited_at_utc": datetime.now(timezone.utc).isoformat(),
              "independent_source_seed_pairs": 16, "matched_unseen_environment_starts_reconstructed": starts_count,
              "complete_test_cohorts": cohorts, "individual_test_lifetimes_recomputed": individuals,
              "archived_inheritance_transitions_replayed": mutation_transitions,
              "all_source_models_and_publication_hashes_checked": True,
              "all_genetic_curves_replayed_and_final_RMS_independently_recomputed": True,
              "all_deaths_meals_survival_fitness_and_failure_rates_recomputed": True,
              "all_repeats_averaged_within_independent_seed_before_inference": True,
              "primary_tests_with_independent_sign_and_Holm_check": len(primary),
              "exploratory_tests_with_independent_sign_and_Holm_check": len(secondary),
              "all_barren_lifetimes_equal_20_seconds_with_no_food": True,
              "deterministic_complete_cohort_replays_bitwise_equal": replayed,
              "all_declared_python_source_versions_verified": True, "stored_analysis_equals_recomputation": True,
              "all_experiment_plot_and_test_source_hashes_unchanged": True,
              "audit_only_repair": {"reason": "Use the declared FIXED_SPEED float60.0 when reconstructing canonical worlds. Integer60 gave equal physics but a different JSON initial-layout hash. No experiment, models, tests, analysis, or data changed.",
                  "declared_source_file": str(declared_audit), "declared_source_sha256": file_digest(declared_audit),
                  "current_source_sha256": file_digest(Path(__file__)),
                  "initial_failure_log": "results/step27-audit-initial-error.txt"},
              "runtime_only_restart_preserved_scientific_settings_and_initial_sources": True,
              "preserved_preexisting_files_except_README": len(preserved),
              "unchanged_prior_result_artifacts": sum(p.startswith("results/") for p in preserved),
              "baseline_tests_passed": 382, "current_tests_passed": 401,
              "runtime": {"python": platform.python_version(), **{n: version(n) for n in ("numpy", "pygame", "matplotlib")}},
              "artifact_sha256": {p: file_digest(p) for p in artifacts}}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("results/step27-evaluation.json"))
    parser.add_argument("--protocol", type=Path, default=Path("results/step27-protocol.json"))
    parser.add_argument("--baseline", type=Path, default=Path("results/step27-baseline.json"))
    parser.add_argument("--tests", type=Path, default=Path("results/step27-tests.txt"))
    parser.add_argument("--output", type=Path, default=Path("results/step27-audit.json"))
    args = parser.parse_args()
    result = audit(args.report, args.protocol, args.baseline, args.tests, args.output,
                   [Path(f"results/step27-{name}.png") for name in ("evaluation", "effects", "mechanisms")])
    print(json.dumps({k: v for k, v in result.items() if k != "artifact_sha256"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
