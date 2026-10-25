"""Test food-guided behavior with frozen brains, sensor controls, and unseen arenas."""

from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import numpy as np

from brain import HIDDEN_SIZE, INPUT_SIZE, OUTPUT_SIZE, NeuralNetwork
from compare_creatures import complete_generation, derived_seed, genome_digest, holm_adjust, paired_summary
from compare_creatures import initial_conditions_digest, positive_integer
from perception import VISION_RANGE
from simulation import EvolutionSimulation
from world import World


DEFAULT_SEEDS = tuple(range(1501, 1509))
ENVIRONMENTS = {"standard": (1000, 600), "wide": (1200, 500)}
CONDITIONS = ("intact", "mirrored", "hidden", "founder", "random")
METRICS = ("mean_food_eaten", "mean_fitness", "survival_rate", "mean_survival_seconds", "mean_speed")
PARAMETER_NAMES = ("input_weights", "hidden_bias", "output_weights", "output_bias")
PARAMETER_SHAPES = ((INPUT_SIZE, HIDDEN_SIZE), (HIDDEN_SIZE,), (HIDDEN_SIZE, OUTPUT_SIZE), (OUTPUT_SIZE,))
TRAINING_CONFIG = {"population_size": 100, "food_count": 150, "mutation_rate": 0.1,
                   "mutation_scale": 0.1, "controller": "neural", "evolution_enabled": True,
                   "food_sensor_mode": "intact", "arena_size": [1000, 600]}


def bank_digest(bank: dict) -> str:
    return genome_digest(SimpleNamespace(creature_id=key, brain=brain) for key, brain in bank.items())


def train_lineage(seed: int, generations: int, progress=False):
    world = World(1000, 600, seed=seed, population_size=100, food_count=150,
                  mutation_rate=0.1, mutation_scale=0.1)
    founders = {c.creature_id: c.brain.copy() for c in world.creatures}
    simulation = EvolutionSimulation(world, generation_limit=generations, auto_advance=False)
    initial = []
    for generation in range(1, generations + 1):
        initial.append(initial_conditions_digest(world))
        complete_generation(simulation)
        if progress and generation in (1, generations // 2, generations):
            print(f"Seed {seed} / training {generation}/{generations}", flush=True)
        if generation < generations and not simulation.advance_generation():
            raise RuntimeError("Training could not advance.")
    evolved = {c.creature_id: c.brain.copy() for c in world.dead_creatures}
    return simulation.report(), initial, {"evolved": evolved, "founder": founders}


def save_checkpoint(path: Path, training: dict, initial: list, banks: dict) -> None:
    """Archive numeric arrays only; no Python objects or pickle payloads."""
    ids = sorted(banks["evolved"])
    arrays = {"ids": np.array(ids, dtype=np.int64)}
    metadata = {"format_version": 1, "training": training, "training_initial_conditions": initial,
                "genome_hashes": {name: bank_digest(bank) for name, bank in banks.items()}}
    arrays["metadata"] = np.array(json.dumps(metadata, allow_nan=False))
    for name, bank in banks.items():
        for parameter, attribute in enumerate(PARAMETER_NAMES):
            arrays[f"{name}_{parameter}"] = np.stack([getattr(bank[key], attribute) for key in ids])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    temporary.replace(path)


def load_checkpoint(path: Path, seed: int, generations: int):
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata"].item()))
        training = metadata["training"]
        if (metadata["format_version"] != 1 or training["seed"] != seed
                or training["completed_generations"] != generations
                or len(training["generations"]) != generations
                or any(training[key] != value for key, value in TRAINING_CONFIG.items())):
            raise ValueError("Checkpoint must match the declared seed, generation count, and original training settings.")
        ids = archive["ids"]
        if ids.dtype.kind not in "iu" or ids.tolist() != list(range(1, 101)):
            raise ValueError("Checkpoint must contain every brain in the 100-creature cohort.")
        banks = {}
        for name in ("evolved", "founder"):
            arrays = [archive[f"{name}_{index}"] for index in range(4)]
            if any(array.shape != (100, *shape) or not np.all(np.isfinite(array))
                   for array, shape in zip(arrays, PARAMETER_SHAPES)):
                raise ValueError("Checkpoint arrays have invalid shapes or non-finite parameters.")
            bank = {}
            for index, key in enumerate(ids):
                brain = object.__new__(NeuralNetwork)
                for attribute, array in zip(PARAMETER_NAMES, arrays):
                    setattr(brain, attribute, array[index].copy())
                bank[int(key)] = brain
            if bank_digest(bank) != metadata["genome_hashes"][name]:
                raise ValueError("Checkpoint genome hash does not match its numeric arrays.")
            banks[name] = bank
    return training, metadata["training_initial_conditions"], banks


def steering_probe(bank: dict) -> dict:
    """Flip only target side in plausible open-field sensory states."""
    records = []
    for key, brain in sorted(bank.items()):
        gains, correct = [], []
        for distance in (40.0, 80.0, 120.0):
            for hunger in (0.25, 0.75):
                for bearing in (0.25, 0.5):  # bearing / pi: 45 and 90 degrees
                    right = np.array([1 - distance / VISION_RANGE, bearing, 1, hunger, 1, 1, 1, 1])
                    left = right.copy()
                    left[1] = -bearing
                    turn_right, turn_left = float(brain.forward(right)[0]), float(brain.forward(left)[0])
                    gains.append((turn_right - turn_left) / 2)
                    correct.append(turn_right > 0 and turn_left < 0)
        records.append({"creature_id": key, "steering_gain": float(np.mean(gains)),
                        "both_sides_correct_fraction": float(np.mean(correct))})
    if not records:
        raise ValueError("Steering probes require at least one brain.")
    return {"pose_pairs_per_brain": 12, "brains": records,
            "mean_steering_gain": float(np.mean([row["steering_gain"] for row in records])),
            "mean_both_sides_correct_fraction": float(np.mean([row["both_sides_correct_fraction"] for row in records]))}


def run_lineage(seed: int, generations: int, repeats: int, models_dir=None, reuse=False, progress=False):
    path = Path(models_dir) / f"seed-{seed}.npz" if models_dir is not None else None
    if reuse:
        training, initial, banks = load_checkpoint(path, seed, generations)
    else:
        training, initial, banks = train_lineage(seed, generations, progress)
        if path is not None:
            save_checkpoint(path, training, initial, banks)
    hashes = {name: bank_digest(bank) for name, bank in banks.items()}
    probes = {name: steering_probe(bank) for name, bank in banks.items()}
    tests = []
    for environment, (width, height) in ENVIRONMENTS.items():
        for repeat in range(1, repeats + 1):
            test_seed = derived_seed(f"step15:test:{seed}:{environment}:{repeat}")
            test = {"environment": environment, "repeat": repeat, "seed": test_seed, "conditions": {}}
            reference = None
            for condition in CONDITIONS:
                mode = condition if condition in ("mirrored", "hidden") else "intact"
                world = World(width, height, seed=test_seed, population_size=100, food_count=150,
                              controller="random" if condition == "random" else "neural",
                              evolution_enabled=False, food_sensor_mode=mode)
                bank_name = "founder" if condition == "founder" else "evolved"
                if condition != "random":
                    for creature in world.creatures:
                        creature.brain = banks[bank_name][creature.creature_id].copy()
                start = initial_conditions_digest(world)
                if start in initial or (reference is not None and start != reference):
                    raise RuntimeError("Test arenas must be unseen and matched across conditions.")
                reference = start
                assigned_genomes = genome_digest(world.creatures)
                simulation = EvolutionSimulation(world, generation_limit=1, auto_advance=False)
                complete_generation(simulation)
                if genome_digest(world.dead_creatures) != assigned_genomes:
                    raise RuntimeError("Testing changed a frozen brain.")
                test["conditions"][condition] = {
                    "initial_conditions": start, "genomes_sha256": assigned_genomes,
                    "report": simulation.report(),
                }
            tests.append(test)
            if progress:
                print(f"Seed {seed} / {environment} / repeat {repeat}/{repeats} / all five conditions complete", flush=True)
    if any(bank_digest(bank) != hashes[name] for name, bank in banks.items()):
        raise RuntimeError("Probes or tests changed source genomes.")
    return {"seed": seed, "training": training, "training_initial_conditions": initial,
            "model_file": str(path) if path is not None else None,
            "genome_hashes": hashes, "probes": probes, "tests": tests}


def effect(left, right, label: str, *, primary=False) -> dict:
    result = paired_summary(left, right, seed=derived_seed(f"step15:bootstrap:{label}"))
    if not primary:
        result.pop("sign_test_p")
    return result


def primary_decisions(primary: dict) -> bool:
    """Require consistent benefits in all four predeclared operational tests."""
    adjusted = holm_adjust([row["sign_test_p"] for row in primary.values()])
    for row, p_value in zip(primary.values(), adjusted):
        row["holm_adjusted_p"] = p_value
        low, high = row["difference_ci95"]
        row["conclusion"] = "higher" if p_value < 0.05 and low > 0 else "lower" if p_value < 0.05 and high < 0 else "inconclusive"
    return len(primary) == 4 and all(row["conclusion"] == "higher" for row in primary.values())


def analyze_results(report: dict) -> dict:
    protocol, trials = report["protocol"], report["trials"]
    seeds, repeats = protocol["seeds"], protocol["repeats_per_environment"]
    if len(seeds) < 2 or len(set(seeds)) != len(seeds) or len(trials) != len(seeds) or {t["seed"] for t in trials} != set(seeds):
        raise ValueError("Analysis needs every planned independent training seed.")
    trials = sorted(trials, key=lambda trial: seeds.index(trial["seed"]))
    expected = {(name, repeat) for name in ENVIRONMENTS for repeat in range(1, repeats + 1)}
    if protocol["environments"] != {name: list(size) for name, size in ENVIRONMENTS.items()}:
        raise ValueError("The protocol must specify both planned arena geometries.")
    for trial in trials:
        if len(trial["tests"]) != len(expected) or {(test["environment"], test["repeat"]) for test in trial["tests"]} != expected:
            raise ValueError("Every environment and repeat must be present exactly once.")
        if (trial["training"]["completed_generations"] != protocol["generations"]
                or len(trial["training"]["generations"]) != protocol["generations"]
                or any(trial["training"][key] != value for key, value in TRAINING_CONFIG.items())):
            raise ValueError("Training must be complete before testing.")
        if len({test["seed"] for test in trial["tests"]}) != len(expected):
            raise ValueError("Repeated arenas must have distinct test seeds.")
        for test in trial["tests"]:
            if test["seed"] != derived_seed(f"step15:test:{trial['seed']}:{test['environment']}:{test['repeat']}"):
                raise ValueError("Test seeds must use the independent planned namespace.")
            if set(test["conditions"]) != set(CONDITIONS):
                raise ValueError("All five matched test conditions are required.")
            starts = {record["initial_conditions"] for record in test["conditions"].values()}
            if len(starts) != 1 or starts.intersection(trial["training_initial_conditions"]):
                raise ValueError("Test starts must be matched and separate from training.")
            for name, record in test["conditions"].items():
                data = record["report"]
                expected_mode = name if name in ("mirrored", "hidden") else "intact"
                if (data["completed_generations"] != 1 or len(data["generations"]) != 1
                        or data["population_size"] != 100 or data["food_count"] != 150
                        or data["seed"] != test["seed"] or data["evolution_enabled"]
                        or data["arena_size"] != list(ENVIRONMENTS[test["environment"]])
                        or data["food_sensor_mode"] != expected_mode
                        or data["controller"] != ("random" if name == "random" else "neural")
                        or data["generations"][0]["population_size"] != 100):
                    raise ValueError("Test reports must match the fixed cohort, environment, and sensor intervention.")
                if name != "random" and record["genomes_sha256"] != trial["genome_hashes"]["founder" if name == "founder" else "evolved"]:
                    raise ValueError("All neural tests must use their frozen source genomes.")
        for name in ("evolved", "founder"):
            probe = trial["probes"][name]
            if (probe["pose_pairs_per_brain"] != 12 or len(probe["brains"]) != 100
                    or sorted(row["creature_id"] for row in probe["brains"]) != list(range(1, 101))
                    or any(not -1 <= row["steering_gain"] <= 1 or not 0 <= row["both_sides_correct_fraction"] <= 1 for row in probe["brains"])
                    or not np.isclose(probe["mean_steering_gain"], np.mean([row["steering_gain"] for row in probe["brains"]]))
                    or not np.isclose(probe["mean_both_sides_correct_fraction"], np.mean([row["both_sides_correct_fraction"] for row in probe["brains"]]))):
                raise ValueError("Probe summaries must describe every frozen brain and match their recorded responses.")
    environments, primary = {}, {}
    for environment in ENVIRONMENTS:
        values = {condition: {metric: [] for metric in METRICS} for condition in CONDITIONS}
        for trial in trials:
            tests = [test for test in trial["tests"] if test["environment"] == environment]
            for condition in CONDITIONS:
                for metric in METRICS:
                    # Repeats reduce within-lineage noise, not the number of independent units.
                    values[condition][metric].append(float(np.mean([
                        test["conditions"][condition]["report"]["generations"][0][metric] for test in tests
                    ])))
        contrasts = {}
        for control in CONDITIONS[1:]:
            contrasts[control] = {metric: effect(values["intact"][metric], values[control][metric],
                f"{environment}:{control}:{metric}", primary=control == "mirrored" and metric == "mean_food_eaten") for metric in METRICS}
        environments[environment] = {
            "condition_means": {condition: {metric: float(np.mean(rows)) for metric, rows in metrics.items()}
                                for condition, metrics in values.items()},
            "seed_values": values, "contrasts": contrasts,
        }
        primary[f"food_direction_{environment}"] = dict(contrasts["mirrored"]["mean_food_eaten"])
    evolved_gains = [trial["probes"]["evolved"]["mean_steering_gain"] for trial in trials]
    founder_gains = [trial["probes"]["founder"]["mean_steering_gain"] for trial in trials]
    primary["directional_response"] = effect(evolved_gains, np.zeros(len(trials)), "probe:positive", primary=True)
    primary["response_emergence"] = effect(evolved_gains, founder_gains, "probe:emergence", primary=True)
    supported = primary_decisions(primary)
    return {"environments": environments, "primary_tests": primary,
            "probe_means": {name: {metric: float(np.mean([trial["probes"][name][metric] for trial in trials]))
                for metric in ("mean_steering_gain", "mean_both_sides_correct_fraction")} for name in ("evolved", "founder")},
            "generalized_food_seeking_demonstrated": supported,
            "interpretation": "All four operational criteria met." if supported else "Generalized food seeking was not demonstrated by all four operational criteria; this does not establish absence of every food-dependent strategy."}


def run_study(seeds=DEFAULT_SEEDS, *, generations=10, repeats=2, workers=1,
              models_dir=None, reuse=False, progress=False, checkpoint: Callable[[dict], None] | None = None):
    seeds = list(seeds)
    if len(seeds) < 2 or any(type(seed) is not int for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("Use at least two distinct integer training seeds.")
    if type(generations) is not int or generations < 2 or type(repeats) is not int or repeats < 1 or type(workers) is not int or workers < 1:
        raise ValueError("Use at least two generations, positive repeats, and a positive worker count.")
    if reuse and models_dir is None:
        raise ValueError("Reusing brains requires --models-dir.")
    report = {"format_version": 1, "status": "running", "protocol": {
        "seeds": seeds, "generations": generations,
        "training_configuration": {**TRAINING_CONFIG, "arena_size": list(TRAINING_CONFIG["arena_size"])},
        "environments": {name: list(size) for name, size in ENVIRONMENTS.items()},
        "repeats_per_environment": repeats, "conditions": list(CONDITIONS),
        "test_seed_namespace": "step15:test", "training_reused": reuse,
        "planned_training_cohorts": 0 if reuse else len(seeds) * generations,
        "planned_test_cohorts": len(seeds) * len(ENVIRONMENTS) * repeats * len(CONDITIONS),
        "analysis_unit": "independent training seed; repeats averaged within environment and lineage",
        "primary_outcomes": "intact-minus-mirrored mean meals in each environment; positive steering gain; steering gain above founders",
        "primary_family": "four two-sided exact paired sign tests with Holm correction",
        "intervals": "95% paired percentile bootstrap, 20000 resamples, pointwise",
        "decision": "all four tests must have Holm p < 0.05 and a positive mean-difference interval",
        "probe": {"distances": [40, 80, 120], "bearings_degrees": [45, 90], "hungers": [0.25, 0.75],
                  "wall_inputs": [1, 1, 1, 1], "gain": "(turn at +bearing minus turn at -bearing) / 2"},
        "limitations": "operational food-guidance evidence, not human-like cognition; hidden inputs can cause distribution shift; secondary contrasts descriptive",
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
    report["trials"].sort(key=lambda trial: seeds.index(trial["seed"]))
    report["analysis"] = analyze_results(report)
    report["status"] = "complete"
    if checkpoint:
        checkpoint(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--generations", type=positive_integer, default=10)
    parser.add_argument("--repeats", type=positive_integer, default=2)
    parser.add_argument("--workers", type=positive_integer, default=1)
    parser.add_argument("--models-dir", type=Path, help="save frozen founder and evolved brain archives")
    parser.add_argument("--reuse-models", action="store_true", help="load verified archives and repeat testing without retraining")
    parser.add_argument("--output", type=Path, default=Path("results/intelligence.json"))
    parser.add_argument("--plot", type=Path)
    args = parser.parse_args()
    def save(report):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    try:
        report = run_study(args.seeds, generations=args.generations, repeats=args.repeats, workers=args.workers,
                           models_dir=args.models_dir, reuse=args.reuse_models, progress=True, checkpoint=save)
        if args.plot:
            from plot_intelligence import save_intelligence_plot
            save_intelligence_plot(report, args.plot)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for name, row in report["analysis"]["primary_tests"].items():
        print(f"{name}: difference {row['mean_difference']:+.4f}; interval {row['difference_ci95']}; "
              f"Holm p={row['holm_adjusted_p']:.4f}; {row['conclusion']}")
    print(report["analysis"]["interpretation"])
    print(f"Intelligence-analysis report saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
