"""Paired fitness selection versus random-parent inheritance with matched mutation."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import random

import numpy as np

from analyze_intelligence import PARAMETER_NAMES, PARAMETER_SHAPES, bank_digest
from brain import NeuralNetwork
from compare_creatures import complete_generation, derived_seed, genome_digest, initial_conditions_digest, positive_integer
from experiment_speed import ENVIRONMENTS, FIXED_SPEED, TRAINING_CONFIG, classify_primary, paired_metrics
from reproduction import reproduce_brains
from simulation import EvolutionSimulation
from world import CLUSTER_COUNT, World


DEFAULT_SEEDS = tuple(range(1801, 1817))
ARMS = ("selection", "random_parent")
CONDITIONS = (*ARMS, "founder")
METRICS = ("mean_fitness", "mean_food_eaten", "survival_rate")


class RecordedMutationRNG:
    """Observe the existing reproducer's draws without changing its RNG sequence."""
    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)
        self.digest = hashlib.sha256()
        self.calls = 0

    def record(self, kind, values):
        array = np.asarray(values)
        self.digest.update(json.dumps([kind, array.shape, array.dtype.str]).encode() + b"\0")
        self.digest.update(array.tobytes())
        self.calls += 1

    def shuffle(self, values):
        self.rng.shuffle(values)
        self.record("shuffle", values)

    def random(self, *args, **kwargs):
        values = self.rng.random(*args, **kwargs)
        self.record("random", values)
        return values

    def normal(self, *args, **kwargs):
        values = self.rng.normal(*args, **kwargs)
        self.record("normal", values)
        return values


class ParentPolicyWorld(World):
    """Keep World physics intact; vary only the completed cohort's parent choice."""
    def __init__(self, *args, parent_policy="selection", **kwargs):
        if parent_policy not in ARMS or kwargs.get("evolution_enabled", True) is not True:
            raise ValueError("Use selection or random_parent with inherited evolution enabled.")
        self.parent_policy = parent_policy
        super().__init__(*args, **kwargs)

    def regenerate_population(self, seed=None):
        self.transitions = []
        super().regenerate_population(seed)

    def advance_generation(self):
        evaluation = self.final_evaluation
        if self.creatures or evaluation is None or not evaluation.complete or not evaluation.selected_ids:
            return False
        records = {c.creature_id: c for c in self.dead_creatures}
        candidates = sorted(records)
        count = len(evaluation.selected_ids)
        next_generation = self.generation + 1
        parent_seed = derived_seed(f"step18:random-parents:{self.seed}:generation:{next_generation}")
        # Use the same fitness-independent ordering before shuffled birth slots.
        parent_ids = sorted(evaluation.selected_ids if self.parent_policy == "selection" else
                            random.Random(parent_seed).sample(candidates, count))
        parents = [records[key] for key in parent_ids]
        # The canonical World mutation stream is identical for the two arms.
        mutation_seed = random.Random(f"mutation:{self.seed}:generation:{next_generation}").getrandbits(128)
        rng = RecordedMutationRNG(mutation_seed)
        offspring = reproduce_brains(parents, rng, offspring_count=self.population_size,
                                     mutation_rate=self.mutation_rate, mutation_scale=self.mutation_scale)
        self.transitions.append({
            "from_generation": self.generation, "to_generation": next_generation,
            "parent_policy": self.parent_policy, "candidate_ids": candidates,
            "candidate_fitness": {str(key): records[key].fitness for key in candidates},
            "parent_ids": parent_ids, "parent_draw_seed": parent_seed if self.parent_policy == "random_parent" else None,
            "mutation_seed": mutation_seed, "mutation_draws_sha256": rng.digest.hexdigest(),
            "mutation_rng_calls": rng.calls, "offspring_count": len(offspring),
            "offspring_parent_ids": [child.parent_id for child in offspring],
            "offspring_mutation_counts": [child.mutations for child in offspring],
        })
        self._start_generation(next_generation, offspring)
        return True


def train_pair(seed, generations, progress=False):
    worlds = {arm: ParentPolicyWorld(seed=seed, fixed_speed=FIXED_SPEED, parent_policy=arm) for arm in ARMS}
    simulations = {arm: EvolutionSimulation(w, generation_limit=generations, auto_advance=False) for arm, w in worlds.items()}
    founders = {c.creature_id: c.brain.copy() for c in worlds["selection"].creatures}
    founder_hash = bank_digest(founders)
    starts = {arm: [] for arm in ARMS}
    for generation in range(1, generations + 1):
        for arm in ARMS:
            starts[arm].append(initial_conditions_digest(worlds[arm]))
            if generation == 1 and genome_digest(worlds[arm].creatures) != founder_hash:
                raise RuntimeError("Both arms must begin with identical founder brains.")
            complete_generation(simulations[arm])
        if starts["selection"][-1] != starts["random_parent"][-1]:
            raise RuntimeError("Training bodies and food must be paired in every generation.")
        if generation == 1 and simulations["selection"].report()["generations"] != simulations["random_parent"].report()["generations"]:
            raise RuntimeError("Identical founders must have identical first-generation observations.")
        if progress and generation in (1, generations // 2, generations):
            print(f"Seed {seed}: both training arms complete generation {generation}/{generations}", flush=True)
        if generation < generations:
            for arm in ARMS:
                if not simulations[arm].advance_generation():
                    raise RuntimeError("Paired training could not advance.")
            a, b = [worlds[arm].transitions[-1] for arm in ARMS]
            if any(a[key] != b[key] for key in ("mutation_seed", "mutation_draws_sha256", "mutation_rng_calls", "offspring_mutation_counts")):
                raise RuntimeError("Mutation streams and offspring counts must match across arms.")
    banks = {arm: {c.creature_id: c.brain.copy() for c in w.dead_creatures} for arm, w in worlds.items()}
    banks["founder"] = founders
    training = {arm: simulations[arm].report() for arm in ARMS}
    transitions = {arm: worlds[arm].transitions for arm in ARMS}
    return training, starts, transitions, banks


def save_models(path, seed, training, starts, transitions, banks):
    path = Path(path)
    if path.exists():
        raise ValueError("Preserve existing models; use --reuse-models or a new model directory.")
    metadata = {"format_version": 1, "seed": seed, "training": training, "training_initial_conditions": starts,
                "transitions": transitions, "genome_hashes": {name: bank_digest(bank) for name, bank in banks.items()}}
    arrays = {"ids": np.arange(1, 101, dtype=np.int64), "metadata": np.array(json.dumps(metadata, allow_nan=False))}
    for name in CONDITIONS:
        for index, attribute in enumerate(PARAMETER_NAMES):
            arrays[f"{name}_{index}"] = np.stack([getattr(banks[name][key], attribute) for key in range(1, 101)])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    temporary.replace(path)


def validate_transitions(training, starts, transitions, seed, generations):
    if starts["selection"] != starts["random_parent"] or len(starts["selection"]) != generations:
        raise ValueError("Every training generation must have matched starting bodies and food.")
    if any(not training[arm]["generations"] for arm in ARMS):
        raise ValueError("Both training histories must be present.")
    if training["selection"]["generations"][0] != training["random_parent"]["generations"][0]:
        raise ValueError("First-generation outcomes must be identical.")
    for arm in ARMS:
        data = training[arm]
        if (data["seed"] != seed or data["completed_generations"] != generations or len(data["generations"]) != generations
                or any(data[key] != value for key, value in TRAINING_CONFIG.items())
                or len(transitions[arm]) != generations - 1):
            raise ValueError("Both arms need complete training with identical fixed parameters.")
        for generation, stats in enumerate(data["generations"], 1):
            if (stats["generation"] != generation or stats["population_size"] != 100
                    or not np.isclose(stats["mean_speed"], FIXED_SPEED)
                    or not all(np.isfinite(stats[m]) for m in METRICS)
                    or stats["survival_rate"] != stats["survivors_at_checkpoint"] / 100
                    or not 0 <= stats["survival_rate"] <= 1
                    or not np.isclose(stats["mean_fitness"], stats["mean_survival_seconds"] + 10 * stats["mean_food_eaten"])):
                raise ValueError("Invalid training speed, cohort count, or score.")
        for index, row in enumerate(transitions[arm], 2):
            ids = row["candidate_ids"]
            scores = row["candidate_fitness"]
            expected_seed = derived_seed(f"step18:random-parents:{seed}:generation:{index}")
            expected_parents = sorted(sorted(range(1, 101), key=lambda key: (-scores[str(key)], key))[:20] if arm == "selection"
                                      else random.Random(expected_seed).sample(list(range(1, 101)), 20))
            mutation_seed = random.Random(f"mutation:{seed}:generation:{index}").getrandbits(128)
            if (row["parent_policy"] != arm or row["from_generation"] != index - 1 or row["to_generation"] != index
                    or ids != list(range(1, 101)) or set(scores) != {str(key) for key in ids}
                    or not all(np.isfinite(score) for score in scores.values()) or row["parent_ids"] != expected_parents
                    or row["mutation_seed"] != mutation_seed or row["offspring_count"] != 100
                    or row["parent_draw_seed"] != (expected_seed if arm == "random_parent" else None)
                    or len(row["offspring_parent_ids"]) != 100 or len(row["offspring_mutation_counts"]) != 100
                    or row["mutation_rng_calls"] != 801
                    or any(type(n) is not int or not 0 <= n <= 90 for n in row["offspring_mutation_counts"])
                    or set(row["offspring_parent_ids"]) != set(expected_parents)
                    or any(row["offspring_parent_ids"].count(key) != 5 for key in expected_parents)):
                raise ValueError("Parent choice, eligibility, balanced inheritance, or generation budget is invalid.")
    for a, b in zip(transitions["selection"], transitions["random_parent"]):
        if any(a[key] != b[key] for key in ("mutation_seed", "mutation_draws_sha256", "mutation_rng_calls", "offspring_mutation_counts")):
            raise ValueError("Mutation draws must match across paired arms.")


def load_models(path, seed, generations):
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata"].item()))
        ids = archive["ids"]
        if metadata["format_version"] != 1 or metadata["seed"] != seed or ids.dtype.kind not in "iu" or ids.tolist() != list(range(1, 101)):
            raise ValueError("Invalid paired model archive.")
        validate_transitions(metadata["training"], metadata["training_initial_conditions"], metadata["transitions"], seed, generations)
        banks = {}
        for name in CONDITIONS:
            arrays = [archive[f"{name}_{index}"] for index in range(4)]
            if any(a.shape != (100, *shape) or not np.all(np.isfinite(a)) for a, shape in zip(arrays, PARAMETER_SHAPES)):
                raise ValueError("Invalid paired parameter arrays.")
            bank = {}
            for index, key in enumerate(ids):
                brain = object.__new__(NeuralNetwork)
                for attribute, array in zip(PARAMETER_NAMES, arrays):
                    setattr(brain, attribute, array[index].copy())
                bank[int(key)] = brain
            if bank_digest(bank) != metadata["genome_hashes"][name]:
                raise ValueError("Paired model hash mismatch.")
            banks[name] = bank
    return metadata["training"], metadata["training_initial_conditions"], metadata["transitions"], banks


def run_lineage(seed, generations, repeats, models_dir, reuse, forbidden, progress=False):
    path = Path(models_dir) / f"seed-{seed}.npz" if models_dir is not None else None
    if reuse:
        training, starts, transitions, banks = load_models(path, seed, generations)
    else:
        training, starts, transitions, banks = train_pair(seed, generations, progress)
        validate_transitions(training, starts, transitions, seed, generations)
        if path is not None:
            save_models(path, seed, training, starts, transitions, banks)
    hashes = {name: bank_digest(bank) for name, bank in banks.items()}
    forbidden = set(forbidden) | set(starts["selection"])
    tests = []
    for environment, settings in ENVIRONMENTS.items():
        for repeat in range(1, repeats + 1):
            test_seed = derived_seed(f"step18:test:{seed}:{environment}:{repeat}")
            test = {"environment": environment, "repeat": repeat, "seed": test_seed, "conditions": {}}
            reference = None
            for name in CONDITIONS:
                world = World(*settings["arena_size"], seed=test_seed, fixed_speed=FIXED_SPEED,
                              food_distribution=settings["food_distribution"], evolution_enabled=False)
                for creature in world.creatures:
                    creature.brain = banks[name][creature.creature_id].copy()
                initial = initial_conditions_digest(world)
                if initial in forbidden or (reference is not None and initial != reference):
                    raise RuntimeError("Test arenas must be new and matched.")
                reference = initial
                simulation = EvolutionSimulation(world, generation_limit=1, auto_advance=False)
                complete_generation(simulation)
                if genome_digest(world.dead_creatures) != hashes[name]:
                    raise RuntimeError("Testing changed frozen weights.")
                test["conditions"][name] = {"initial_conditions": initial, "genomes_sha256": hashes[name], "report": simulation.report()}
            tests.append(test)
            if progress:
                print(f"Seed {seed}: {environment}, repeat {repeat}/{repeats}, all three inherited/founder tests complete", flush=True)
    if any(bank_digest(bank) != hashes[name] for name, bank in banks.items()):
        raise RuntimeError("A frozen source bank changed.")
    return {"seed": seed, "model_file": str(path) if path is not None else None, "training": training,
            "training_initial_conditions": starts, "transitions": transitions, "genome_hashes": hashes, "tests": tests}


def training_curves(trials, generations):
    indices = np.random.default_rng(derived_seed("step18:training-bootstrap")).integers(len(trials), size=(20000, len(trials)))
    result = {}
    for arm in ARMS:
        matrix = np.array([[row["mean_fitness"] for row in t["training"][arm]["generations"]] for t in trials])
        low, high = np.quantile(matrix[indices].mean(axis=1), [0.025, 0.975], axis=0)
        result[arm] = {"generations": list(range(1, generations + 1)), "mean_fitness": matrix.mean(axis=0).tolist(),
                       "low": low.tolist(), "high": high.tolist()}
    return result


def analyze_results(report):
    protocol, trials = report["protocol"], report["trials"]
    seeds, generations, repeats = protocol["seeds"], protocol["generations"], protocol["repeats_per_environment"]
    if (len(seeds) < 2 or len(set(seeds)) != len(seeds) or len(trials) != len(seeds)
            or {t["seed"] for t in trials} != set(seeds) or protocol["conditions"] != list(CONDITIONS)
            or protocol["training_configuration"] != TRAINING_CONFIG or protocol["environments"] != ENVIRONMENTS
            or type(repeats) is not int or repeats < 1 or generations < 2):
        raise ValueError("Analysis requires the complete declared paired-selection study.")
    trials = sorted(trials, key=lambda t: seeds.index(t["seed"]))
    all_training = {start for t in trials for start in t["training_initial_conditions"]["selection"]}
    forbidden = set(protocol["excluded_initial_conditions"]) | all_training
    seen = set()
    expected = {(env, repeat) for env in ENVIRONMENTS for repeat in range(1, repeats + 1)}
    for trial in trials:
        validate_transitions(trial["training"], trial["training_initial_conditions"], trial["transitions"], trial["seed"], generations)
        if len(trial["tests"]) != len(expected) or {(t["environment"], t["repeat"]) for t in trial["tests"]} != expected:
            raise ValueError("Every planned test environment and repeat is required.")
        for test in trial["tests"]:
            if (test["seed"] != derived_seed(f"step18:test:{trial['seed']}:{test['environment']}:{test['repeat']}")
                    or set(test["conditions"]) != set(CONDITIONS)):
                raise ValueError("Incorrect held-out namespace or missing control.")
            starts = {r["initial_conditions"] for r in test["conditions"].values()}
            if len(starts) != 1 or starts.intersection(forbidden) or starts.intersection(seen):
                raise ValueError("Test layouts must be matched and unseen across every lineage.")
            seen.update(starts)
            centers = None
            for name, record in test["conditions"].items():
                data, settings = record["report"], ENVIRONMENTS[test["environment"]]
                if (data["completed_generations"] != 1 or len(data["generations"]) != 1 or data["evolution_enabled"]
                        or data["population_size"] != 100 or data["food_count"] != 150 or data["controller"] != "neural"
                        or data["fixed_speed"] != FIXED_SPEED or data["food_sensor_mode"] != "intact"
                        or data["arena_size"] != settings["arena_size"] or data["food_distribution"] != settings["food_distribution"]
                        or data["seed"] != test["seed"] or record["genomes_sha256"] != trial["genome_hashes"][name]):
                    raise ValueError("Test reports must preserve matched physics and frozen source banks.")
                if centers is not None and centers != data["food_cluster_centers"]:
                    raise ValueError("Test cluster centers must match.")
                centers = data["food_cluster_centers"]
                if len(centers) != (CLUSTER_COUNT if settings["food_distribution"] == "clustered" else 0):
                    raise ValueError("Incorrect test cluster configuration.")
                stats = data["generations"][0]
                if (stats["population_size"] != 100 or not np.isclose(stats["mean_speed"], FIXED_SPEED)
                        or not all(np.isfinite(stats[m]) for m in METRICS)
                        or stats["survival_rate"] != stats["survivors_at_checkpoint"] / 100
                        or not 0 <= stats["survival_rate"] <= 1 or stats["mean_food_eaten"] < 0
                        or not np.isclose(stats["mean_fitness"], stats["mean_survival_seconds"] + 10 * stats["mean_food_eaten"])):
                    raise ValueError("Invalid cohort metrics or speed constraint.")
    environments, primary = {}, []
    for environment in ENVIRONMENTS:
        values = {c: {m: [] for m in METRICS} for c in CONDITIONS}
        for trial in trials:
            tests = [t for t in trial["tests"] if t["environment"] == environment]
            for c in CONDITIONS:
                for metric in METRICS:
                    values[c][metric].append(float(np.mean([t["conditions"][c]["report"]["generations"][0][metric] for t in tests])))
        comparisons = {}
        for label, left, right in (("selection_vs_random_parent", "selection", "random_parent"),
                                   ("selection_vs_founder", "selection", "founder"),
                                   ("random_parent_vs_founder", "random_parent", "founder")):
            comparisons[label] = {}
            for metric in METRICS:
                row = paired_metrics(values[left][metric], values[right][metric], seed=derived_seed(f"step18:bootstrap:{environment}:{label}:{metric}"))
                if label != "random_parent_vs_founder" and metric == "mean_fitness":
                    primary.append(row)
                else:
                    row.pop("sign_test_p")
                comparisons[label][metric] = row
        environments[environment] = {"seed_values": values, "comparisons": comparisons,
            "condition_means": {c: {m: float(np.mean(v)) for m, v in metrics.items()} for c, metrics in values.items()}}
    classify_primary(primary)
    for data in environments.values():
        data["evidence"] = {
            "selection_benefit_over_drift": data["comparisons"]["selection_vs_random_parent"]["mean_fitness"]["conclusion"],
            "net_improvement_over_founders": data["comparisons"]["selection_vs_founder"]["mean_fitness"]["conclusion"],
        }
    return {"independent_seed_pairs": len(seeds), "environments": environments,
            "training_curves": training_curves(trials, generations),
            "selection_improvement_supported_in_all_environments": all(
                all(value == "higher" for value in data["evidence"].values()) for data in environments.values())}


def previous_layouts():
    root = Path(__file__).resolve().parent
    excluded = set()
    for filename in ("step16-speed-comparison.json", "step17-strategy.json"):
        path = root / "results" / filename
        if path.exists():
            prior = json.loads(path.read_text())
            for trial in prior["trials"]:
                excluded.update(trial.get("training_initial_conditions", trial.get("source_training_initial_conditions", [])))
                excluded.update(r["initial_conditions"] for test in trial["tests"] for r in test["conditions"].values())
    return sorted(excluded)


def run_study(seeds=DEFAULT_SEEDS, *, generations=10, repeats=1, workers=1, models_dir=None,
              reuse=False, progress=False, checkpoint=None):
    seeds = list(seeds)
    if (len(seeds) < 2 or any(type(s) is not int for s in seeds) or len(set(seeds)) != len(seeds)
            or type(generations) is not int or generations < 2 or type(repeats) is not int or repeats < 1
            or type(workers) is not int or workers < 1 or (reuse and models_dir is None)):
        raise ValueError("Use distinct integer seeds, at least two generations, positive repeats/workers, and models for reuse.")
    if models_dir is not None:
        paths = [Path(models_dir) / f"seed-{seed}.npz" for seed in seeds]
        if not reuse and any(path.exists() for path in paths):
            raise ValueError("Existing models are preserved; use --reuse-models or a new directory.")
        if reuse:
            for seed, path in zip(seeds, paths):
                load_models(path, seed, generations)
    report = {"format_version": 1, "status": "running", "protocol": {
        "seeds": seeds, "generations": generations, "repeats_per_environment": repeats,
        "conditions": list(CONDITIONS), "training_configuration": json.loads(json.dumps(TRAINING_CONFIG)),
        "environments": json.loads(json.dumps(ENVIRONMENTS)), "excluded_initial_conditions": previous_layouts(),
        "training_reused": reuse, "planned_new_training_cohorts": 0 if reuse else len(seeds) * generations * 2,
        "planned_test_cohorts": len(seeds) * len(ENVIRONMENTS) * repeats * len(CONDITIONS),
        "selection_policy": "top 20 of 100 by existing fitness; exact ties favor lower ID",
        "random_parent_policy": "sample 20 of all 100 uniformly without replacement, independent of fitness, including early deaths",
        "matched_reproduction": "same 20-parent bottleneck, parent IDs sorted before reproduction in both arms, five offspring each, shuffled birth slots, inherited mutated weights in both arms; never fresh random-brain replacement",
        "matched_randomness": "identical founder genomes and generation-specific physical starts; common mutation seed, masks, Gaussian perturbations, and slot shuffles verified by recorded-draw SHA-256 hashes",
        "founder_control": "frozen original brains, tested in the same held-out worlds; no extra founder training",
        "primary_family": "six two-sided exact paired sign tests: selection-minus-random-parent fitness and selection-minus-founder fitness in each environment; Holm over all six",
        "sign_tie_tolerance_abs": 1e-10, "intervals": "95% paired percentile bootstrap, 20000 resamples, approximate pointwise intervals",
        "decision": "higher/lower requires Holm p < 0.05 and paired mean interval excluding zero in the same direction. A net selection improvement in an environment requires both primary contrasts higher.",
        "analysis_unit": "one independently initialized seed pair; repeats averaged within environment and pair",
        "secondary": "meals, 60-second survival, drift-minus-founder comparisons, and training trajectories descriptive; no confirmatory p-values",
        "limitations": "causal effect of fitness-dependent parent choice in this virtual-world model and budget, not universal proof; matched evaluation count, not matched lifetime or wall-clock duration; random-parent arm includes both neutral bottleneck drift and mutation",
    }, "trials": []}
    if checkpoint:
        checkpoint(report)
    args = (generations, repeats, models_dir, reuse, report["protocol"]["excluded_initial_conditions"], progress)
    if workers == 1:
        for seed in seeds:
            report["trials"].append(run_lineage(seed, *args))
            if checkpoint:
                checkpoint(report)
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(seeds))) as executor:
            futures = [executor.submit(run_lineage, seed, *args) for seed in seeds]
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
    parser.add_argument("--repeats", type=positive_integer, default=1)
    parser.add_argument("--workers", type=positive_integer, default=1)
    parser.add_argument("--models-dir", type=Path)
    parser.add_argument("--reuse-models", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("results/selection.json"))
    parser.add_argument("--protocol-output", type=Path)
    parser.add_argument("--plot", type=Path)
    args = parser.parse_args()
    outputs = [p.resolve() for p in (args.output, args.protocol_output, args.plot) if p is not None]
    protected = {p.resolve() for p in Path("results").glob("step1[1-7]*") if p.is_file()}
    protected.update(p.resolve() for p in Path("results").rglob("*.npz"))
    if args.models_dir is not None:
        protected.update((args.models_dir / f"seed-{seed}.npz").resolve() for seed in args.seeds)
    if len(set(outputs)) != len(outputs) or any(p in protected for p in outputs):
        parser.error("Use distinct output paths and preserve published earlier results.")
    def save(report):
        if args.protocol_output is not None and not report["trials"]:
            source = Path(__file__).resolve().parent
            declaration = {"declared_at_utc": datetime.now(timezone.utc).isoformat(), "protocol": report["protocol"],
                           "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.glob("*.py"))}}
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
            from plot_selection import save_selection_plot
            save_selection_plot(report, args.plot)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for env, data in report["analysis"]["environments"].items():
        for label in ("selection_vs_random_parent", "selection_vs_founder"):
            row = data["comparisons"][label]["mean_fitness"]
            print(f"{env}/{label}: {row['mean_difference']:+.4f}; Holm p={row['holm_adjusted_p']:.5f}; {row['conclusion']}")
    print(f"Paired selection study saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
