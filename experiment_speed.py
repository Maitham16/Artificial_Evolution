"""Retrain and test evolution against random and greedy steering at identical speeds."""

from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from analyze_intelligence import PARAMETER_NAMES, PARAMETER_SHAPES, bank_digest, save_checkpoint
from brain import NeuralNetwork, MAX_TURN_RATE
from compare_creatures import (complete_generation, derived_seed, genome_digest,
                               holm_adjust, initial_conditions_digest, paired_summary, positive_integer)
from creature import BASE_ENERGY_COST, MOVEMENT_ENERGY_COST
from simulation import EvolutionSimulation
from world import CLUSTER_COUNT, CLUSTER_SPREAD, World


DEFAULT_SEEDS = tuple(range(1601, 1617))
FIXED_SPEED = 60.0
SIGN_TIE_TOLERANCE = 1e-10
CONDITIONS = ("evolved", "random", "greedy")
METRICS = ("mean_fitness", "mean_food_eaten", "survival_rate")
ENVIRONMENTS = {
    "uniform": {"arena_size": [1000, 600], "food_distribution": "uniform"},
    "clustered": {"arena_size": [1000, 600], "food_distribution": "clustered"},
    "wide_clustered": {"arena_size": [1200, 500], "food_distribution": "clustered"},
}
TRAINING_CONFIG = {
    "arena_size": [1000, 600], "food_distribution": "uniform", "fixed_speed": FIXED_SPEED,
    "population_size": 100, "food_count": 150, "mutation_rate": 0.1, "mutation_scale": 0.1,
    "controller": "neural", "evolution_enabled": True, "food_sensor_mode": "intact",
}


def train_lineage(seed, generations, progress=False):
    world = World(seed=seed, fixed_speed=FIXED_SPEED)
    simulation = EvolutionSimulation(world, generation_limit=generations, auto_advance=False)
    starts = []
    for generation in range(1, generations + 1):
        starts.append(initial_conditions_digest(world))
        complete_generation(simulation)
        if progress and generation in (1, generations // 2, generations):
            print(f"Seed {seed}: training {generation}/{generations}", flush=True)
        if generation < generations and not simulation.advance_generation():
            raise RuntimeError("Training could not advance.")
    bank = {c.creature_id: c.brain.copy() for c in world.dead_creatures}
    return simulation.report(), starts, bank


def load_model(path, seed, generations):
    """Load only numeric arrays, with complete-cohort and configuration checks."""
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata"].item()))
        training = metadata["training"]
        if (metadata["format_version"] != 1 or training["seed"] != seed
                or training["completed_generations"] != generations
                or len(training["generations"]) != generations
                or any(training[key] != value for key, value in TRAINING_CONFIG.items())):
            raise ValueError("Model must match the fixed-speed training protocol, seed, and generation count.")
        ids = archive["ids"]
        if ids.dtype.kind not in "iu" or ids.tolist() != list(range(1, 101)):
            raise ValueError("Model must contain all 100 brains.")
        arrays = [archive[f"evolved_{i}"] for i in range(4)]
        if any(array.shape != (100, *shape) or not np.all(np.isfinite(array))
               for array, shape in zip(arrays, PARAMETER_SHAPES)):
            raise ValueError("Invalid model parameter arrays.")
        bank = {}
        for index, key in enumerate(ids):
            brain = object.__new__(NeuralNetwork)
            for name, array in zip(PARAMETER_NAMES, arrays):
                setattr(brain, name, array[index].copy())
            bank[int(key)] = brain
        if bank_digest(bank) != metadata["genome_hashes"]["evolved"]:
            raise ValueError("Model hash does not match its parameters.")
    return training, metadata["training_initial_conditions"], bank


def run_lineage(seed, generations, repeats, models_dir=None, reuse=False, progress=False):
    path = Path(models_dir) / f"seed-{seed}.npz" if models_dir is not None else None
    if reuse:
        training, starts, bank = load_model(path, seed, generations)
    else:
        training, starts, bank = train_lineage(seed, generations, progress)
        if path is not None:
            save_checkpoint(path, training, starts, {"evolved": bank})
    source_hash = bank_digest(bank)
    tests = []
    for environment, settings in ENVIRONMENTS.items():
        for repeat in range(1, repeats + 1):
            seed_test = derived_seed(f"step16:test:{seed}:{environment}:{repeat}")
            test = {"environment": environment, "repeat": repeat, "seed": seed_test, "conditions": {}}
            matched = None
            for condition in CONDITIONS:
                width, height = settings["arena_size"]
                world = World(width, height, seed=seed_test, fixed_speed=FIXED_SPEED,
                              food_distribution=settings["food_distribution"], evolution_enabled=False,
                              controller="neural" if condition == "evolved" else condition)
                for creature in world.creatures:
                    # Baseline brains are recorded but unused by their steering policies.
                    creature.brain = bank[creature.creature_id].copy()
                    if creature.speed != FIXED_SPEED or creature.energy_cost_per_second != 5.0:
                        raise RuntimeError("Controllers must have identical speed and per-second energy cost.")
                initial = initial_conditions_digest(world)
                if initial in starts or (matched is not None and initial != matched):
                    raise RuntimeError("Tests must be unseen and physically matched.")
                matched = initial
                simulation = EvolutionSimulation(world, generation_limit=1, auto_advance=False)
                complete_generation(simulation)
                if genome_digest(world.dead_creatures) != source_hash:
                    raise RuntimeError("Testing changed frozen weights.")
                test["conditions"][condition] = {"initial_conditions": initial,
                    "genomes_sha256": source_hash, "report": simulation.report()}
            tests.append(test)
            if progress:
                print(f"Seed {seed}: {environment}, repeat {repeat}/{repeats}, all three conditions complete", flush=True)
    if bank_digest(bank) != source_hash:
        raise RuntimeError("Source model changed.")
    return {"seed": seed, "training": training, "training_initial_conditions": starts,
            "model_file": str(path) if path is not None else None,
            "genomes_sha256": source_hash, "tests": tests}


def classify_primary(rows):
    for row, p_value in zip(rows, holm_adjust([row["sign_test_p"] for row in rows])):
        row["holm_adjusted_p"] = p_value
        low, high = row["difference_ci95"]
        row["conclusion"] = ("higher" if p_value < 0.05 and low > 0 else
                             "lower" if p_value < 0.05 and high < 0 else "inconclusive")


def paired_metrics(left, right, *, seed):
    result = paired_summary(left, right, seed=seed)
    # Equal count averages can differ by ~1e-16 due to binary arithmetic.
    # Keep effect sizes/intervals intact, but never count that noise as a sign win.
    delta = np.asarray(left, dtype=float) - np.asarray(right, dtype=float)
    wins = int(np.count_nonzero(delta > SIGN_TIE_TOLERANCE))
    losses = int(np.count_nonzero(delta < -SIGN_TIE_TOLERANCE))
    n = wins + losses
    result.update(wins=wins, losses=losses, ties=len(delta) - n,
                  sign_test_p=min(1.0, 2 * sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2**n),
                  sign_tie_tolerance_abs=SIGN_TIE_TOLERANCE)
    return result


def analyze_results(report):
    protocol, trials = report["protocol"], report["trials"]
    seeds, repeats, generations = protocol["seeds"], protocol["repeats_per_environment"], protocol["generations"]
    if (len(seeds) < 2 or len(set(seeds)) != len(seeds) or len(trials) != len(seeds)
            or {trial["seed"] for trial in trials} != set(seeds)
            or protocol["training_configuration"] != TRAINING_CONFIG
            or protocol["environments"] != ENVIRONMENTS or protocol["conditions"] != list(CONDITIONS)
            or type(repeats) is not int or repeats < 1 or generations < 2):
        raise ValueError("Analysis requires the complete declared fixed-speed study.")
    trials = sorted(trials, key=lambda trial: seeds.index(trial["seed"]))
    expected = {(name, repeat) for name in ENVIRONMENTS for repeat in range(1, repeats + 1)}
    all_starts = set()
    for trial in trials:
        training = trial["training"]
        if (training["seed"] != trial["seed"] or training["completed_generations"] != generations
                or len(training["generations"]) != generations
                or len(trial["training_initial_conditions"]) != generations
                or any(training[key] != value for key, value in TRAINING_CONFIG.items())
                or any(not np.isclose(row["mean_speed"], FIXED_SPEED) for row in training["generations"])):
            raise ValueError("Training must be complete under the declared speed constraint.")
        if (len(trial["tests"]) != len(expected)
                or {(t["environment"], t["repeat"]) for t in trial["tests"]} != expected):
            raise ValueError("Every planned environment and repeat must appear exactly once.")
        for test in trial["tests"]:
            if (test["seed"] != derived_seed(f"step16:test:{trial['seed']}:{test['environment']}:{test['repeat']}")
                    or set(test["conditions"]) != set(CONDITIONS)):
                raise ValueError("Use every matched condition and the independent test namespace.")
            starts = {row["initial_conditions"] for row in test["conditions"].values()}
            if len(starts) != 1 or starts.intersection(trial["training_initial_conditions"]) or starts.intersection(all_starts):
                raise ValueError("Test layouts must be matched, unseen, and distinct.")
            all_starts.update(starts)
            centers = None
            for condition, record in test["conditions"].items():
                data = record["report"]
                settings = ENVIRONMENTS[test["environment"]]
                if (data["completed_generations"] != 1 or len(data["generations"]) != 1
                        or data["population_size"] != 100 or data["food_count"] != 150
                        or data["seed"] != test["seed"] or data["evolution_enabled"]
                        or data["fixed_speed"] != FIXED_SPEED or data["food_sensor_mode"] != "intact"
                        or data["arena_size"] != settings["arena_size"]
                        or data["food_distribution"] != settings["food_distribution"]
                        or data["controller"] != ("neural" if condition == "evolved" else condition)
                        or record["genomes_sha256"] != trial["genomes_sha256"]):
                    raise ValueError("Tests must match the frozen models, controllers, and environmental constraints.")
                if centers is not None and centers != data["food_cluster_centers"]:
                    raise ValueError("Cluster centers must match across conditions.")
                centers = data["food_cluster_centers"]
                if len(centers) != (CLUSTER_COUNT if settings["food_distribution"] == "clustered" else 0):
                    raise ValueError("Incorrect cluster geometry.")
                stats = data["generations"][0]
                if (stats["population_size"] != 100 or not np.isclose(stats["mean_speed"], FIXED_SPEED)
                        or not all(np.isfinite(stats[metric]) for metric in METRICS)
                        or not 0 <= stats["survival_rate"] <= 1
                        or not np.isclose(stats["survival_rate"], stats["survivors_at_checkpoint"] / 100)
                        or not np.isclose(stats["mean_fitness"], stats["mean_survival_seconds"] + 10 * stats["mean_food_eaten"])):
                    raise ValueError("Invalid speed, cohort denominator, score, or metric.")
    environments, primary = {}, []
    for environment in ENVIRONMENTS:
        values = {condition: {metric: [] for metric in METRICS} for condition in CONDITIONS}
        for trial in trials:
            tests = [t for t in trial["tests"] if t["environment"] == environment]
            for condition in CONDITIONS:
                for metric in METRICS:
                    values[condition][metric].append(float(np.mean([
                        t["conditions"][condition]["report"]["generations"][0][metric] for t in tests])))
        contrasts = {}
        for control in ("random", "greedy"):
            contrasts[control] = {}
            for metric in METRICS:
                row = paired_metrics(values["evolved"][metric], values[control][metric],
                                     seed=derived_seed(f"step16:bootstrap:{environment}:{control}:{metric}"))
                if control == "random":
                    primary.append(row)
                else:
                    row.pop("sign_test_p")
                contrasts[control][metric] = row
        environments[environment] = {"seed_values": values, "contrasts": contrasts,
            "condition_means": {c: {m: float(np.mean(v)) for m, v in rows.items()} for c, rows in values.items()}}
    classify_primary(primary)
    fitness_wins = [name for name, result in environments.items()
                    if result["contrasts"]["random"]["mean_fitness"]["conclusion"] == "higher"]
    return {"environments": environments, "fitness_wins_over_random": fitness_wins,
            "beats_random_fitness_in_all_environments": len(fitness_wins) == len(ENVIRONMENTS),
            "independent_lineages": len(seeds)}


def run_study(seeds=DEFAULT_SEEDS, *, generations=10, repeats=2, workers=1,
              models_dir=None, reuse=False, progress=False, checkpoint=None):
    seeds = list(seeds)
    if len(seeds) < 2 or any(type(s) is not int for s in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("Use at least two distinct integer training seeds.")
    if (type(generations) is not int or generations < 2 or type(repeats) is not int or repeats < 1
            or type(workers) is not int or workers < 1 or (reuse and models_dir is None)):
        raise ValueError("Use at least two generations, positive repeats/workers, and a model directory for reuse.")
    report = {"format_version": 1, "status": "running", "protocol": {
        "seeds": seeds, "generations": generations, "repeats_per_environment": repeats,
        "training_configuration": json.loads(json.dumps(TRAINING_CONFIG)),
        "environments": json.loads(json.dumps(ENVIRONMENTS)), "conditions": list(CONDITIONS),
        "food_clusters": {"count": CLUSTER_COUNT, "gaussian_sigma_pixels": CLUSTER_SPREAD,
                          "centers": "seeded independently per layout, middle 60% of each axis; fixed during the cohort"},
        "training_reused": reuse, "planned_training_cohorts": 0 if reuse else len(seeds) * generations,
        "planned_test_cohorts": len(seeds) * repeats * len(ENVIRONMENTS) * len(CONDITIONS),
        "fixed_speed_pixels_per_second": FIXED_SPEED, "max_turn_radians_per_second": MAX_TURN_RATE,
        "energy_cost_per_living_second": BASE_ENERGY_COST + MOVEMENT_ENERGY_COST * FIXED_SPEED,
        "greedy_policy": "turn toward nearest pellet within 160px, limited to 90deg/s without overshoot; random steering when none is detected",
        "analysis_unit": "independent training lineage; test repeats averaged within environment before inference",
        "primary_family": "nine evolved-minus-random contrasts: fitness, meals, and 60-second survival in three environments; two-sided exact paired sign tests with Holm correction",
        "sign_tie_tolerance_abs": SIGN_TIE_TOLERANCE,
        "intervals": "95% paired percentile bootstrap, 20000 resamples, approximate pointwise intervals",
        "decision": "higher/lower requires Holm p < 0.05 and a paired mean interval excluding zero in the same direction; fitness wins reported by environment",
        "greedy_comparisons": "secondary descriptive estimates and pointwise intervals, without confirmatory p-values",
        "limitations": "one fixed speed, population, mutation setting, generation budget, replenishment rule, and training distribution; no claim about all evolutionary algorithms",
    }, "trials": []}
    if checkpoint:
        checkpoint(report)
    if workers == 1:
        for seed in seeds:
            report["trials"].append(run_lineage(seed, generations, repeats, models_dir, reuse, progress))
            if checkpoint:
                checkpoint(report)
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(seeds))) as executor:
            futures = [executor.submit(run_lineage, seed, generations, repeats, models_dir, reuse, progress) for seed in seeds]
            for future in as_completed(futures):
                report["trials"].append(future.result())
                if checkpoint:
                    checkpoint(report)
    report["trials"].sort(key=lambda t: seeds.index(t["seed"]))
    report["analysis"] = analyze_results(report)
    report["status"] = "complete"
    if checkpoint:
        checkpoint(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--generations", type=positive_integer, default=10)
    parser.add_argument("--repeats", type=positive_integer, default=2)
    parser.add_argument("--workers", type=positive_integer, default=1)
    parser.add_argument("--models-dir", type=Path)
    parser.add_argument("--reuse-models", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("results/speed-comparison.json"))
    parser.add_argument("--plot", type=Path)
    parser.add_argument("--protocol-output", type=Path, help="record protocol and source hashes before any trial runs")
    args = parser.parse_args()
    def save(report):
        if args.protocol_output is not None and not report["trials"]:
            source = Path(__file__).resolve().parent
            declaration = {"declared_at_utc": datetime.now(timezone.utc).isoformat(),
                           "protocol": report["protocol"],
                           "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                             for path in sorted(source.glob("*.py"))}}
            args.protocol_output.parent.mkdir(parents=True, exist_ok=True)
            args.protocol_output.write_text(json.dumps(declaration, indent=2, allow_nan=False) + "\n")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(".tmp.json")
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        temporary.replace(args.output)
    try:
        report = run_study(args.seeds, generations=args.generations, repeats=args.repeats, workers=args.workers,
                           models_dir=args.models_dir, reuse=args.reuse_models, progress=True, checkpoint=save)
        if args.plot:
            from plot_speed import save_speed_plot
            save_speed_plot(report, args.plot)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for environment, rows in report["analysis"]["environments"].items():
        for metric, row in rows["contrasts"]["random"].items():
            print(f"{environment} / {metric}: {row['mean_difference']:+.4f}, Holm p={row['holm_adjusted_p']:.5f}, {row['conclusion']}")
    print(f"Fixed-speed study saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
