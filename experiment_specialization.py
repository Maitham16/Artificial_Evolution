"""Matched specialists and a domain-cycling generalist, crossed with three habitats."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import hashlib
from itertools import combinations, permutations
import json
from pathlib import Path
import random

import numpy as np

from analyze_intelligence import PARAMETER_NAMES, PARAMETER_SHAPES, bank_digest
from brain import NeuralNetwork
from compare_creatures import complete_generation, derived_seed, genome_digest, initial_conditions_digest, positive_integer
from experiment_selection import ParentPolicyWorld, previous_layouts
from experiment_speed import FIXED_SPEED, classify_primary, paired_metrics
from simulation import EvolutionSimulation
from world import CLUSTER_COUNT, World


DEFAULT_SEEDS = tuple(range(1901, 1919))
HABITATS = {
    "uniform": {"food_distribution": "uniform", "food_count": 150},
    "clustered": {"food_distribution": "clustered", "food_count": 150},
    "sparse": {"food_distribution": "uniform", "food_count": 50},
}
REGIMES = (*HABITATS, "generalist")
BANKS = (*REGIMES, "founder")
METRICS = ("mean_fitness", "mean_food_eaten", "survival_rate")
COMMON = {"arena_size": [1000, 600], "population_size": 100, "fixed_speed": FIXED_SPEED,
          "mutation_rate": 0.1, "mutation_scale": 0.1, "controller": "neural", "food_sensor_mode": "intact"}


def curriculum(seed, regime, rounds):
    if regime not in REGIMES or type(rounds) is not int or rounds < 3 or rounds % 3:
        raise ValueError("Use a known regime and training rounds divisible by three.")
    if regime != "generalist":
        return [regime] * rounds
    orders = list(permutations(HABITATS))
    schedule = []
    for block in range(rounds // 3):
        offset = derived_seed(f"step19:curriculum-block:{block}") % 6
        schedule.extend(orders[(seed - 1901 + offset) % 6])
    return schedule


def bodies_digest(world):
    bodies = [(c.creature_id, c.x, c.y, c.radius, c.color, c.heading, c.max_speed, c.lifespan, c.energy)
              for c in world.creatures]
    return hashlib.sha256(json.dumps(bodies).encode()).hexdigest()


class HabitatWorld(ParentPolicyWorld):
    """Choose the scheduled food context before each existing generation starts."""
    def __init__(self, seed, regime, rounds):
        self.schedule = curriculum(seed, regime, rounds)
        self.regime = regime
        super().__init__(seed=seed, fixed_speed=FIXED_SPEED, parent_policy="selection")

    def _start_generation(self, generation, inherited=None):
        # Round R selects parents for the frozen, unscored birth cohort R+1.
        habitat = self.schedule[min(generation - 1, len(self.schedule) - 1)]
        self.food_count = HABITATS[habitat]["food_count"]
        self.food_distribution = HABITATS[habitat]["food_distribution"]
        super()._start_generation(generation, inherited)


def train_group(seed, rounds, progress=False):
    worlds = {r: HabitatWorld(seed, r, rounds) for r in REGIMES}
    simulations = {r: EvolutionSimulation(w, auto_advance=False) for r, w in worlds.items()}
    founders = {c.creature_id: c.brain.copy() for c in worlds["uniform"].creatures}
    founder_hash = bank_digest(founders)
    episodes = {r: [] for r in REGIMES}
    for generation in range(1, rounds + 1):
        body_hashes = set()
        for regime, world in worlds.items():
            initial, bodies = initial_conditions_digest(world), bodies_digest(world)
            body_hashes.add(bodies)
            if generation == 1 and genome_digest(world.creatures) != founder_hash:
                raise RuntimeError("Every regime must have the same original genomes.")
            complete_generation(simulations[regime])
            observations = simulations[regime].report()
            episodes[regime].append({"round": generation, "habitat": world.schedule[generation - 1],
                "food_count": world.food_count, "food_distribution": world.food_distribution,
                "common_configuration": {key: observations[key] for key in COMMON},
                "initial_conditions": initial, "bodies_sha256": bodies,
                "stats": observations["generations"][-1]})
        if len(body_hashes) != 1:
            raise RuntimeError("Training bodies must match across all regimes each round.")
        # Every scored habitat, including the final one, contributes to reproduction.
        for world in worlds.values():
            if not world.advance_generation():
                raise RuntimeError("Training selection could not advance.")
        traces = [world.transitions[-1] for world in worlds.values()]
        for key in ("mutation_seed", "mutation_draws_sha256", "mutation_rng_calls", "offspring_mutation_counts"):
            if any(t[key] != traces[0][key] for t in traces[1:]):
                raise RuntimeError("Mutation schedules must be shared across all training regimes.")
        if progress and generation in (1, rounds // 2, rounds):
            print(f"Seed {seed}: all four regimes complete evaluation/selection round {generation}/{rounds}", flush=True)
    banks = {r: {c.creature_id: c.brain.copy() for c in w.creatures} for r, w in worlds.items()}
    if any(w.generation != rounds + 1 or len(w.creatures) != 100 or any(c.age != 0 for c in w.creatures) for w in worlds.values()):
        raise RuntimeError("Freeze the complete unscored offspring cohort after the last selection.")
    banks["founder"] = founders
    return episodes, {r: w.transitions for r, w in worlds.items()}, banks


def validate_training(seed, rounds, training, transitions):
    for regime in REGIMES:
        if len(training[regime]) != rounds or len(transitions[regime]) != rounds:
            raise ValueError("Every regime requires equal evaluation and reproduction budgets.")
        schedule = curriculum(seed, regime, rounds)
        for index, (episode, trace) in enumerate(zip(training[regime], transitions[regime]), 1):
            habitat = schedule[index - 1]
            stats, settings = episode["stats"], HABITATS[habitat]
            scores = trace["candidate_fitness"]
            parents = sorted(sorted(range(1, 101), key=lambda key: (-scores[str(key)], key))[:20])
            mutation_seed = random.Random(f"mutation:{seed}:generation:{index + 1}").getrandbits(128)
            if (episode["round"] != index or episode["habitat"] != habitat
                    or any(episode[k] != v for k, v in settings.items())
                    or episode["common_configuration"] != COMMON
                    or stats["generation"] != index or stats["population_size"] != 100
                    or not np.isclose(stats["mean_speed"], FIXED_SPEED)
                    or not all(np.isfinite(stats[m]) for m in METRICS)
                    or stats["survival_rate"] != stats["survivors_at_checkpoint"] / 100
                    or not np.isclose(stats["mean_fitness"], stats["mean_survival_seconds"] + 10 * stats["mean_food_eaten"])):
                raise ValueError("Training episode does not match its declared habitat, budget, or physics.")
            if (trace["candidate_ids"] != list(range(1, 101)) or set(scores) != {str(k) for k in range(1, 101)}
                    or not all(np.isfinite(v) for v in scores.values()) or trace["parent_policy"] != "selection"
                    or trace["parent_ids"] != parents or trace["from_generation"] != index or trace["to_generation"] != index + 1
                    or trace["mutation_seed"] != mutation_seed or trace["mutation_rng_calls"] != 801
                    or trace["offspring_count"] != 100 or len(trace["offspring_parent_ids"]) != 100
                    or set(trace["offspring_parent_ids"]) != set(parents)
                    or any(trace["offspring_parent_ids"].count(k) != 5 for k in parents)
                    or not np.isclose(np.mean(list(scores.values())), stats["mean_fitness"])):
                raise ValueError("Parent choice or inheritance does not match the shared selection rule.")
    for index in range(rounds):
        if len({training[r][index]["bodies_sha256"] for r in REGIMES}) != 1:
            raise ValueError("Bodies must be shared across regimes within each scored round.")
        for habitat in HABITATS:
            starts = {training[r][index]["initial_conditions"] for r in REGIMES if training[r][index]["habitat"] == habitat}
            if len(starts) != 1:
                raise ValueError("Identical habitat exposures must have identical food starts in the same round.")
        traces = [transitions[r][index] for r in REGIMES]
        for key in ("mutation_seed", "mutation_draws_sha256", "mutation_rng_calls", "offspring_mutation_counts"):
            if any(t[key] != traces[0][key] for t in traces[1:]):
                raise ValueError("Mutation schedules must match across regimes.")


def save_models(path, seed, rounds, training, transitions, banks):
    path = Path(path)
    if path.exists():
        raise ValueError("Preserve existing models; use reuse or a new directory.")
    metadata = {"format_version": 1, "seed": seed, "rounds": rounds, "common_configuration": COMMON,
                "training": training, "transitions": transitions, "frozen_birth_generation": rounds + 1,
                "genome_hashes": {r: bank_digest(b) for r, b in banks.items()}}
    arrays = {"ids": np.arange(1, 101, dtype=np.int64), "metadata": np.array(json.dumps(metadata, allow_nan=False))}
    for name in BANKS:
        for index, attribute in enumerate(PARAMETER_NAMES):
            arrays[f"{name}_{index}"] = np.stack([getattr(banks[name][key], attribute) for key in range(1, 101)])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    temporary.replace(path)


def load_models(path, seed, rounds):
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata"].item()))
        ids = archive["ids"]
        if (metadata["format_version"] != 1 or metadata["seed"] != seed or metadata["rounds"] != rounds
                or metadata["common_configuration"] != COMMON or metadata["frozen_birth_generation"] != rounds + 1
                or ids.dtype.kind not in "iu" or ids.tolist() != list(range(1, 101))):
            raise ValueError("Invalid specialization model archive.")
        validate_training(seed, rounds, metadata["training"], metadata["transitions"])
        banks = {}
        for name in BANKS:
            arrays = [archive[f"{name}_{index}"] for index in range(4)]
            if any(a.shape != (100, *shape) or not np.all(np.isfinite(a)) for a, shape in zip(arrays, PARAMETER_SHAPES)):
                raise ValueError("Invalid specialization parameter arrays.")
            bank = {}
            for index, key in enumerate(ids):
                brain = object.__new__(NeuralNetwork)
                for attribute, array in zip(PARAMETER_NAMES, arrays):
                    setattr(brain, attribute, array[index].copy())
                bank[int(key)] = brain
            if bank_digest(bank) != metadata["genome_hashes"][name]:
                raise ValueError("Specialization model hash mismatch.")
            banks[name] = bank
    return metadata["training"], metadata["transitions"], banks


def run_lineage(seed, rounds, repeats, models_dir, reuse, forbidden, progress=False):
    path = Path(models_dir) / f"seed-{seed}.npz" if models_dir is not None else None
    if reuse:
        training, transitions, banks = load_models(path, seed, rounds)
    else:
        training, transitions, banks = train_group(seed, rounds, progress)
        validate_training(seed, rounds, training, transitions)
        if path is not None:
            save_models(path, seed, rounds, training, transitions, banks)
    hashes = {r: bank_digest(b) for r, b in banks.items()}
    forbidden = set(forbidden) | {e["initial_conditions"] for episodes in training.values() for e in episodes}
    tests = []
    for habitat, settings in HABITATS.items():
        for repeat in range(1, repeats + 1):
            test_seed = derived_seed(f"step19:test:{seed}:{habitat}:{repeat}")
            test = {"habitat": habitat, "repeat": repeat, "seed": test_seed, "conditions": {}}
            reference = None
            for regime in REGIMES:
                world = World(seed=test_seed, fixed_speed=FIXED_SPEED, evolution_enabled=False, **settings)
                for c in world.creatures:
                    c.brain = banks[regime][c.creature_id].copy()
                initial = initial_conditions_digest(world)
                if initial in forbidden or (reference is not None and initial != reference):
                    raise RuntimeError("Test layouts must be matched and unseen.")
                reference = initial
                simulation = EvolutionSimulation(world, generation_limit=1, auto_advance=False)
                complete_generation(simulation)
                if genome_digest(world.dead_creatures) != hashes[regime]:
                    raise RuntimeError("Testing changed frozen weights.")
                test["conditions"][regime] = {"initial_conditions": initial, "genomes_sha256": hashes[regime], "report": simulation.report()}
            tests.append(test)
            if progress:
                print(f"Seed {seed}: {habitat}, repeat {repeat}/{repeats}, all four frozen regimes complete", flush=True)
    if any(bank_digest(bank) != hashes[r] for r, bank in banks.items()):
        raise RuntimeError("Source weights changed.")
    return {"seed": seed, "model_file": str(path) if path is not None else None, "training": training,
            "transitions": transitions, "frozen_birth_generation": rounds + 1,
            "genome_hashes": hashes, "tests": tests}


def analyze_results(report):
    p, trials = report["protocol"], report["trials"]
    seeds, rounds, repeats = p["seeds"], p["rounds"], p["repeats_per_habitat"]
    if (len(seeds) < 2 or len(set(seeds)) != len(seeds) or len(trials) != len(seeds)
            or {t["seed"] for t in trials} != set(seeds) or p["habitats"] != HABITATS or p["regimes"] != list(REGIMES)
            or p["common_configuration"] != COMMON or rounds < 3 or rounds % 3 or type(repeats) is not int or repeats < 1):
        raise ValueError("Analyze only the complete declared specialization study.")
    if p["curricula"] != {str(seed): {r: curriculum(seed, r, rounds) for r in REGIMES} for seed in seeds}:
        raise ValueError("The recorded curricula must match the predeclared counterbalancing rule.")
    trials = sorted(trials, key=lambda t: seeds.index(t["seed"]))
    forbidden = set(p["excluded_initial_conditions"]) | {e["initial_conditions"] for t in trials for episodes in t["training"].values() for e in episodes}
    seen = set()
    expected = {(h, repeat) for h in HABITATS for repeat in range(1, repeats + 1)}
    for trial in trials:
        validate_training(trial["seed"], rounds, trial["training"], trial["transitions"])
        if trial["frozen_birth_generation"] != rounds + 1:
            raise ValueError("Every scored round, including the final one, must contribute to the frozen offspring.")
        if len(trial["tests"]) != len(expected) or {(t["habitat"], t["repeat"]) for t in trial["tests"]} != expected:
            raise ValueError("The full training-regime by test-habitat matrix is required.")
        for test in trial["tests"]:
            if (test["seed"] != derived_seed(f"step19:test:{trial['seed']}:{test['habitat']}:{test['repeat']}")
                    or set(test["conditions"]) != set(REGIMES)):
                raise ValueError("Incorrect held-out namespace or missing regime.")
            starts = {r["initial_conditions"] for r in test["conditions"].values()}
            if len(starts) != 1 or starts.intersection(forbidden) or starts.intersection(seen):
                raise ValueError("Test layouts must be matched, new, and distinct.")
            seen.update(starts)
            centers = None
            for regime, record in test["conditions"].items():
                data, settings = record["report"], HABITATS[test["habitat"]]
                if (data["completed_generations"] != 1 or len(data["generations"]) != 1 or data["evolution_enabled"]
                        or any(data[k] != v for k, v in COMMON.items())
                        or any(data[k] != v for k, v in settings.items()) or data["seed"] != test["seed"]
                        or record["genomes_sha256"] != trial["genome_hashes"][regime]):
                    raise ValueError("Test reports must retain matched physics, habitat, and frozen source weights.")
                if centers is not None and centers != data["food_cluster_centers"]:
                    raise ValueError("Test cluster centers must match across regimes.")
                centers = data["food_cluster_centers"]
                if len(centers) != (CLUSTER_COUNT if settings["food_distribution"] == "clustered" else 0):
                    raise ValueError("Incorrect cluster geometry.")
                stats = data["generations"][0]
                if (stats["population_size"] != 100 or not np.isclose(stats["mean_speed"], FIXED_SPEED)
                        or not all(np.isfinite(stats[m]) for m in METRICS)
                        or stats["survival_rate"] != stats["survivors_at_checkpoint"] / 100
                        or not 0 <= stats["survival_rate"] <= 1 or stats["mean_food_eaten"] < 0
                        or not np.isclose(stats["mean_fitness"], stats["mean_survival_seconds"] + 10 * stats["mean_food_eaten"])):
                    raise ValueError("Invalid test score, population denominator, or speed.")
    habitats, primary = {}, []
    for habitat in HABITATS:
        values = {r: {m: [] for m in METRICS} for r in REGIMES}
        for trial in trials:
            tests = [t for t in trial["tests"] if t["habitat"] == habitat]
            for regime in REGIMES:
                for metric in METRICS:
                    values[regime][metric].append(float(np.mean([t["conditions"][regime]["report"]["generations"][0][metric] for t in tests])))
        contrasts = {}
        for other in REGIMES:
            if other == habitat:
                continue
            contrasts[other] = {}
            for metric in METRICS:
                row = paired_metrics(values[habitat][metric], values[other][metric],
                                     seed=derived_seed(f"step19:bootstrap:{habitat}:{other}:{metric}"))
                if metric == "mean_fitness":
                    primary.append(row)
                else:
                    row.pop("sign_test_p")
                contrasts[other][metric] = row
        habitats[habitat] = {"seed_values": values, "home_contrasts": contrasts,
            "condition_means": {r: {m: float(np.mean(v)) for m, v in metrics.items()} for r, metrics in values.items()}}
    classify_primary(primary)
    reciprocal = {}
    for a, b in combinations(HABITATS, 2):
        a_home = habitats[a]["home_contrasts"][b]["mean_fitness"]
        b_home = habitats[b]["home_contrasts"][a]["mean_fitness"]
        reciprocal[f"{a}:{b}"] = {"supported": a_home["conclusion"] == b_home["conclusion"] == "higher",
                                 "a_home_conclusion": a_home["conclusion"], "b_home_conclusion": b_home["conclusion"]}
    overall = {r: np.mean([habitats[h]["seed_values"][r]["mean_fitness"] for h in HABITATS], axis=0) for r in REGIMES}
    generalization = {}
    for specialist in HABITATS:
        row = paired_metrics(overall["generalist"], overall[specialist], seed=derived_seed(f"step19:overall:{specialist}"))
        row.pop("sign_test_p")
        generalization[specialist] = row
    matrix = {metric: [[habitats[h]["condition_means"][r][metric] for h in HABITATS] for r in REGIMES] for metric in METRICS}
    return {"independent_seed_groups": len(seeds), "matrix_rows": list(REGIMES), "matrix_columns": list(HABITATS),
            "performance_matrices": matrix, "habitats": habitats, "reciprocal_specialization": reciprocal,
            "all_home_specialists_beat_generalist": all(habitats[h]["home_contrasts"]["generalist"]["mean_fitness"]["conclusion"] == "higher" for h in HABITATS),
            "descriptive_generalist_minus_specialist_over_equal_habitat_mix": generalization}


def excluded_layouts():
    excluded = set(previous_layouts())
    path = Path(__file__).resolve().parent / "results/step18-selection.json"
    if path.exists():
        prior = json.loads(path.read_text())
        for trial in prior["trials"]:
            excluded.update(trial["training_initial_conditions"]["selection"])
            excluded.update(r["initial_conditions"] for test in trial["tests"] for r in test["conditions"].values())
    return sorted(excluded)


def run_study(seeds=DEFAULT_SEEDS, *, rounds=9, repeats=1, workers=1, models_dir=None,
              reuse=False, progress=False, checkpoint=None):
    seeds = list(seeds)
    if (len(seeds) < 2 or any(type(s) is not int for s in seeds) or len(set(seeds)) != len(seeds)
            or type(rounds) is not int or rounds < 3 or rounds % 3 or type(repeats) is not int or repeats < 1
            or type(workers) is not int or workers < 1 or (reuse and models_dir is None)):
        raise ValueError("Use distinct integer seeds, rounds divisible by three, positive repeats/workers, and models for reuse.")
    if models_dir is not None:
        paths = [Path(models_dir) / f"seed-{seed}.npz" for seed in seeds]
        if not reuse and any(p.exists() for p in paths):
            raise ValueError("Preserve existing models; use --reuse-models or a new directory.")
        if reuse:
            for seed, path in zip(seeds, paths):
                load_models(path, seed, rounds)
    report = {"format_version": 1, "status": "running", "protocol": {
        "seeds": seeds, "rounds": rounds, "repeats_per_habitat": repeats, "regimes": list(REGIMES),
        "habitats": json.loads(json.dumps(HABITATS)), "common_configuration": json.loads(json.dumps(COMMON)),
        "curricula": {str(seed): {r: curriculum(seed, r, rounds) for r in REGIMES} for seed in seeds},
        "excluded_initial_conditions": excluded_layouts(), "training_reused": reuse,
        "planned_new_training_cohorts": 0 if reuse else len(seeds) * rounds * len(REGIMES),
        "planned_test_cohorts": len(seeds) * len(HABITATS) * repeats * len(REGIMES),
        "selection": "top 20 by existing fitness, ties lower ID, parent IDs sorted, five mutated offspring each",
        "matched_randomness": "same founders and round-specific bodies; common mutation masks, Gaussian draws, and slot shuffles, with recorded draw hashes",
        "generalist": "one habitat per scored round, equal exposure in every three-round block; six curriculum permutations counterbalanced by seed phase; not simultaneous joint-fitness optimization",
        "freeze": "reproduce after every scored round, including the last; freeze all 100 unscored offspring at generation rounds+1",
        "primary_family": "nine fitness contrasts: each home specialist minus generalist and each of the other two specialists in that same test habitat; two-sided paired exact sign tests with Holm over nine",
        "intervals": "pointwise approximate 95% paired percentile bootstrap, 20000 resamples", "sign_tie_tolerance_abs": 1e-10,
        "decision": "higher/lower requires Holm p<0.05 and a mean-difference interval excluding zero in the same direction; reciprocal specialization requires both specialists significantly winning in their own habitat",
        "analysis_unit": "one matched source seed group; repeats averaged within habitat before inference",
        "secondary": "meals, survival to 60s, and generalist-minus-specialist average fitness across equally weighted habitats descriptive, without confirmatory p-values",
        "limitations": "food supply changes absolute task difficulty; compare regimes within the same column, not raw home-vs-away scores. Curriculum and final-context effects remain possible despite order counterbalancing. One architecture, budget, speed, and environment family.",
    }, "trials": []}
    if checkpoint:
        checkpoint(report)
    args = (rounds, repeats, models_dir, reuse, report["protocol"]["excluded_initial_conditions"], progress)
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
    parser.add_argument("--rounds", type=positive_integer, default=9)
    parser.add_argument("--repeats", type=positive_integer, default=1)
    parser.add_argument("--workers", type=positive_integer, default=1)
    parser.add_argument("--models-dir", type=Path)
    parser.add_argument("--reuse-models", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("results/specialization.json"))
    parser.add_argument("--protocol-output", type=Path)
    parser.add_argument("--plot", type=Path)
    args = parser.parse_args()
    outputs = [p.resolve() for p in (args.output, args.protocol_output, args.plot) if p is not None]
    protected = {p.resolve() for p in Path("results").glob("step1[1-8]*") if p.is_file()}
    protected.update(p.resolve() for p in Path("results").rglob("*.npz"))
    if args.models_dir is not None:
        protected.update((args.models_dir / f"seed-{seed}.npz").resolve() for seed in args.seeds)
    if len(set(outputs)) != len(outputs) or any(p in protected for p in outputs):
        parser.error("Use distinct output paths and preserve previous source/result files.")
    def save(report):
        if args.protocol_output is not None and not report["trials"]:
            root = Path(__file__).resolve().parent
            declaration = {"declared_at_utc": datetime.now(timezone.utc).isoformat(), "protocol": report["protocol"],
                           "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob("*.py"))}}
            args.protocol_output.parent.mkdir(parents=True, exist_ok=True)
            args.protocol_output.write_text(json.dumps(declaration, indent=2, allow_nan=False) + "\n")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(".tmp.json")
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        temporary.replace(args.output)
    try:
        report = run_study(args.seeds, rounds=args.rounds, repeats=args.repeats, workers=args.workers,
                           models_dir=args.models_dir, reuse=args.reuse_models, progress=True, checkpoint=save)
        if args.plot:
            from plot_specialization import save_specialization_plot
            save_specialization_plot(report, args.plot)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for habitat, data in report["analysis"]["habitats"].items():
        row = data["home_contrasts"]["generalist"]["mean_fitness"]
        print(f"{habitat}/home-minus-generalist: {row['mean_difference']:+.4f}; Holm p={row['holm_adjusted_p']:.5f}; {row['conclusion']}")
    print(f"Specialization study saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
