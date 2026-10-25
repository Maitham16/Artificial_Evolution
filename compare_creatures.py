"""Compare evolved brains, random movement, and unselected brains on held-out worlds."""

from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Callable

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import numpy as np

from creature import POPULATION_SIZE
from simulation import EvolutionSimulation
from world import World


DEFAULT_SEEDS = (101, 202, 303, 404, 505, 606, 707, 808)
CONDITIONS = ("evolved", "random", "unselected")
METRICS = ("mean_fitness", "survival_rate", "mean_food_eaten", "mean_survival_seconds")
BOOTSTRAP_RESAMPLES = 20000
ANALYSIS_SEED = 130013


def derived_seed(label: str) -> int:
    return int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big")


def initial_conditions_digest(world: World) -> str:
    """Hash matched bodies and initial food, excluding inherited brains."""
    bodies = [(c.creature_id, c.x, c.y, c.radius, c.color, c.heading,
               c.max_speed, c.lifespan, c.energy) for c in world.creatures]
    food = [(pellet.x, pellet.y) for pellet in world.food]
    return hashlib.sha256(json.dumps([bodies, food]).encode()).hexdigest()


def genome_digest(creatures) -> str:
    digest = hashlib.sha256()
    for creature in sorted(creatures, key=lambda c: c.creature_id):
        if creature.brain is None:
            raise ValueError("Every creature must have a recorded brain.")
        for parameter in creature.brain.parameters:
            digest.update(parameter.astype("<f8").tobytes())
    return digest.hexdigest()


def complete_generation(simulation: EvolutionSimulation) -> None:
    # Lifespans guarantee extinction. The guard also catches stalled/paused runs.
    budget = math.ceil(max(c.lifespan for c in simulation.world.creatures)) + 1
    for _ in range(budget):
        simulation.update(1.0)
        if simulation.world.final_evaluation is not None:
            return
    raise RuntimeError("Generation did not complete within its lifespan budget.")


def run_trial(seed: int, generations: int, *, progress: bool = False) -> dict:
    """One independent training lineage per condition, followed by one test arena."""
    if type(seed) is not int or type(generations) is not int or generations < 2:
        raise ValueError("A trial needs an integer seed and at least two generations.")
    test_seed = derived_seed(f"step13:held-out:{seed}")
    trial = {"seed": seed, "evaluation_seed": test_seed, "conditions": {}}
    for condition in CONDITIONS:
        controller = "random" if condition == "random" else "neural"
        world = World(seed=seed, controller=controller, evolution_enabled=condition == "evolved")
        simulation = EvolutionSimulation(world, generation_limit=generations, auto_advance=False)
        initial = []
        for generation in range(1, generations + 1):
            initial.append(initial_conditions_digest(world))
            complete_generation(simulation)
            if progress and generation in (1, generations // 2, generations):
                print(f"Seed {seed} / {condition} / generation {generation}/{generations}", flush=True)
            if generation < generations:
                if not simulation.advance_generation():
                    raise RuntimeError("Training generation could not advance.")
        training = simulation.report()
        genomes = genome_digest(world.dead_creatures)

        # Test every brain from the final birth cohort, without selecting test winners.
        test = World(seed=test_seed, controller=controller, evolution_enabled=False)
        source = {c.creature_id: c for c in world.dead_creatures}
        for creature in test.creatures:
            creature.brain = source[creature.creature_id].brain.copy()
        evaluation_initial = initial_conditions_digest(test)
        evaluation = EvolutionSimulation(test, generation_limit=1, auto_advance=False)
        complete_generation(evaluation)
        if genome_digest(test.dead_creatures) != genomes or genome_digest(world.dead_creatures) != genomes:
            raise RuntimeError("Evaluation changed a frozen training genome.")
        trial["conditions"][condition] = {
            "training": training, "training_initial_conditions": initial,
            "evaluation": evaluation.report(), "evaluation_initial_conditions": evaluation_initial,
            "frozen_genomes_sha256": genomes,
        }
    conditions = trial["conditions"]
    if any(conditions[c]["training_initial_conditions"] != conditions["evolved"]["training_initial_conditions"]
           or conditions[c]["evaluation_initial_conditions"] != conditions["evolved"]["evaluation_initial_conditions"]
           for c in CONDITIONS):
        raise RuntimeError("Conditions did not start with matched bodies and food.")
    if conditions["evolved"]["training"]["generations"][0] != conditions["unselected"]["training"]["generations"][0]:
        raise RuntimeError("Neural conditions did not start with identical founders.")
    return trial


def paired_summary(left, right, *, seed: int = ANALYSIS_SEED) -> dict:
    """Resample independent seed pairs, never individual creatures."""
    left, right = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if left.ndim != 1 or left.shape != right.shape or left.size < 2:
        raise ValueError("Paired analysis needs at least two equally sized seed samples.")
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        raise ValueError("Paired observations must be finite.")
    delta = left - right
    rng = np.random.default_rng(seed)
    indices = rng.integers(left.size, size=(BOOTSTRAP_RESAMPLES, left.size))
    means = delta[indices].mean(axis=1)
    low, high = np.quantile(means, [0.025, 0.975])
    wins, losses = int(np.count_nonzero(delta > 0)), int(np.count_nonzero(delta < 0))
    non_ties = wins + losses
    p_value = min(1.0, 2 * sum(math.comb(non_ties, k) for k in range(min(wins, losses) + 1)) / 2**non_ties)
    return {
        "n_pairs": int(left.size), "evolved_mean": float(left.mean()),
        "control_mean": float(right.mean()), "mean_difference": float(delta.mean()),
        "difference_ci95": [float(low), float(high)],
        "wins": wins, "losses": losses, "ties": int(left.size) - non_ties,
        "sign_test_p": p_value,
    }


def holm_adjust(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=p_values.__getitem__)
    adjusted = [0.0] * len(p_values)
    previous = 0.0
    for rank, index in enumerate(order):
        previous = max(previous, min(1.0, p_values[index] * (len(p_values) - rank)))
        adjusted[index] = previous
    return adjusted


def analyze_trials(trials: list[dict]) -> dict:
    if len(trials) < 2 or len({trial["seed"] for trial in trials}) != len(trials):
        raise ValueError("Analysis needs at least two distinct training seeds.")
    for trial in trials:
        for condition in CONDITIONS:
            evaluation = trial["conditions"][condition]["evaluation"]
            if evaluation.get("completed_generations") != 1 or len(evaluation.get("generations", [])) != 1:
                raise ValueError("Each condition needs exactly one complete held-out generation per seed.")
    comparisons = {}
    for control in ("random", "unselected"):
        metrics = {}
        for metric in METRICS:
            observations = [
                (trial["conditions"]["evolved"]["evaluation"]["generations"][0][metric],
                 trial["conditions"][control]["evaluation"]["generations"][0][metric])
                for trial in trials
            ]
            left, right = zip(*observations)
            metrics[metric] = paired_summary(left, right, seed=derived_seed(f"{ANALYSIS_SEED}:{control}:{metric}"))
        comparisons[f"evolved_vs_{control}"] = metrics
    fitness = [metrics["mean_fitness"] for metrics in comparisons.values()]
    for result, p_value in zip(fitness, holm_adjust([result["sign_test_p"] for result in fitness])):
        result["holm_adjusted_p"] = p_value
        low, high = result["difference_ci95"]
        result["conclusion"] = (
            "higher" if p_value < 0.05 and low > 0 else
            "lower" if p_value < 0.05 and high < 0 else "inconclusive"
        )
    return comparisons


def run_experiment(
    seeds=DEFAULT_SEEDS, *, generations: int = 10, workers: int = 1,
    progress: bool = False, checkpoint: Callable[[dict], None] | None = None,
) -> dict:
    seeds = list(seeds)
    if len(seeds) < 2 or any(type(seed) is not int for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("Use at least two distinct integer training seeds.")
    if type(generations) is not int or generations < 2 or type(workers) is not int or workers < 1:
        raise ValueError("Use at least two generations and a positive worker count.")
    report = {
        "format_version": 1, "status": "running",
        "protocol": {
            "training_seeds": seeds, "training_generations": generations,
            "conditions": list(CONDITIONS), "population_size": POPULATION_SIZE,
            "evaluation_arenas_per_seed": 1, "evaluation_seed_namespace": "step13:held-out",
            "primary_metric": "mean_fitness", "analysis_unit": "independent training seed",
            "confidence_interval": "paired percentile bootstrap, 95%, pointwise",
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES, "analysis_seed": ANALYSIS_SEED,
            "fitness_test": "two-sided exact paired sign test; ties excluded; Holm over two fitness contrasts",
            "decision": "Holm p < 0.05 and the paired mean-difference interval excludes zero in the same direction",
            "secondary_metrics": "descriptive; not adjusted for multiple comparisons",
        },
        "trials": [],
    }
    if checkpoint:
        checkpoint(report)
    if workers == 1:
        results = (run_trial(seed, generations, progress=progress) for seed in seeds)
        for trial in results:
            report["trials"].append(trial)
            if checkpoint:
                checkpoint(report)
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(seeds))) as executor:
            futures = [executor.submit(run_trial, seed, generations, progress=progress) for seed in seeds]
            for future in as_completed(futures):
                report["trials"].append(future.result())
                if checkpoint:
                    checkpoint(report)
    report["trials"].sort(key=lambda trial: seeds.index(trial["seed"]))
    report["comparisons"] = analyze_trials(report["trials"])
    report["status"] = "complete"
    if checkpoint:
        checkpoint(report)
    return report


def positive_integer(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--generations", type=positive_integer, default=10)
    parser.add_argument("--workers", type=positive_integer, default=1, help="parallel CPU processes")
    parser.add_argument("--output", type=Path, default=Path("results/comparison.json"))
    parser.add_argument("--plot", type=Path, help="also export the paired comparison figure")
    args = parser.parse_args()
    def save(report):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    try:
        report = run_experiment(args.seeds, generations=args.generations, workers=args.workers,
                                progress=True, checkpoint=save)
        if args.plot is not None:
            from plot_comparison import save_comparison_plot
            save_comparison_plot(report, args.plot)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for name, metrics in report["comparisons"].items():
        fitness = metrics["mean_fitness"]
        print(f"{name}: fitness difference {fitness['mean_difference']:+.2f}; "
              f"95% paired bootstrap interval {fitness['difference_ci95']}; "
              f"Holm p={fitness['holm_adjusted_p']:.4f}; {fitness['conclusion']}")
    print(f"Comparison report saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
