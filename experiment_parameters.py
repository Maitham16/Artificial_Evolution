"""Explore mutation, population, and food scarcity using paired validation runs."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import argparse
import json
import math
from pathlib import Path
from typing import Callable

from brain import DEFAULT_MUTATION_SCALE
from compare_creatures import complete_generation, derived_seed, genome_digest, initial_conditions_digest, paired_summary
from main import mutation_probability, nonnegative_integer, positive_integer
from selection import SELECTION_FRACTION
from simulation import EvolutionSimulation
from world import World


DEFAULT_SEEDS = (901, 902, 903, 904)
METRICS = ("mean_fitness", "survival_rate", "mean_food_eaten", "mean_survival_seconds")


@dataclass(frozen=True)
class Setting:
    mutation_rate: float = 0.1
    population_size: int = 100
    food_count: int = 150

    def __post_init__(self):
        if not math.isfinite(self.mutation_rate) or not 0 <= self.mutation_rate <= 1:
            raise ValueError("Mutation probability must be finite and between 0 and 1.")
        object.__setattr__(self, "mutation_rate", float(self.mutation_rate) if self.mutation_rate else 0.0)
        if type(self.population_size) is not int or self.population_size < 1:
            raise ValueError("Population size must be a positive integer.")
        if type(self.food_count) is not int or self.food_count < 0:
            raise ValueError("Food count must be a non-negative integer.")

    @property
    def key(self) -> str:
        return f"m{self.mutation_rate}-n{self.population_size}-f{self.food_count}"

    @property
    def ecology_key(self) -> str:
        return f"n{self.population_size}-f{self.food_count}"


STANDARD = Setting()


def make_settings(rates=(0.0, 0.1, 0.3), populations=(50, 100, 150), food_counts=(75, 150, 225)):
    """Keep the standard fixed while varying one factor, without sequential tuning."""
    settings = [STANDARD]
    settings.extend(Setting(rate) for rate in rates)
    settings.extend(Setting(population_size=size) for size in populations)
    settings.extend(Setting(food_count=count) for count in food_counts)
    return list(dict.fromkeys(settings))


def world_for(setting: Setting, seed: int, *, controller="neural", evolution=True) -> World:
    return World(1000, 600, seed=seed, population_size=setting.population_size,
                 food_count=setting.food_count, mutation_rate=setting.mutation_rate,
                 mutation_scale=DEFAULT_MUTATION_SCALE,
                 controller=controller, evolution_enabled=evolution)


def run_seed(seed: int, settings: list[Setting], generations: int, progress=False) -> dict:
    validation_seed = derived_seed(f"step14:validation:{seed}")
    result = {"seed": seed, "validation_seed": validation_seed, "settings": {}, "random_controls": {}}
    for setting in settings:
        world = world_for(setting, seed)
        simulation = EvolutionSimulation(world, generation_limit=generations, auto_advance=False)
        initial, founder_genomes = [], genome_digest(world.creatures)
        for generation in range(1, generations + 1):
            initial.append(initial_conditions_digest(world))
            complete_generation(simulation)
            if progress and generation in (1, generations // 2, generations):
                print(f"Seed {seed} / {setting.key} / generation {generation}/{generations}", flush=True)
            if generation < generations and not simulation.advance_generation():
                raise RuntimeError("Parameter-study generation could not advance.")
        frozen = genome_digest(world.dead_creatures)
        validation = world_for(setting, validation_seed, evolution=False)
        sources = {creature.creature_id: creature for creature in world.dead_creatures}
        for creature in validation.creatures:
            creature.brain = sources[creature.creature_id].brain.copy()
        validation_initial = initial_conditions_digest(validation)
        validation_simulation = EvolutionSimulation(validation, generation_limit=1, auto_advance=False)
        complete_generation(validation_simulation)
        if genome_digest(validation.dead_creatures) != frozen or genome_digest(world.dead_creatures) != frozen:
            raise RuntimeError("Validation changed frozen training weights.")
        if setting.ecology_key not in result["random_controls"]:
            # Mutation has no effect on this non-learning controller; reuse its exact outcome.
            control_setting = Setting(population_size=setting.population_size, food_count=setting.food_count)
            control = world_for(control_setting, validation_seed, controller="random", evolution=False)
            control_initial = initial_conditions_digest(control)
            control_simulation = EvolutionSimulation(control, generation_limit=1, auto_advance=False)
            complete_generation(control_simulation)
            result["random_controls"][setting.ecology_key] = {
                "initial_conditions": control_initial, "validation": control_simulation.report(),
            }
        control = result["random_controls"][setting.ecology_key]
        if control["initial_conditions"] != validation_initial or validation_initial in initial:
            raise RuntimeError("Validation must be fresh and matched to the random control.")
        result["settings"][setting.key] = {
            "training": simulation.report(), "training_initial_conditions": initial,
            "founder_genomes_sha256": founder_genomes, "frozen_genomes_sha256": frozen,
            "validation": validation_simulation.report(), "validation_initial_conditions": validation_initial,
            "random_control": setting.ecology_key,
        }
        if progress:
            print(f"Seed {seed} / {setting.key} / training and validation complete", flush=True)
    for left in settings:
        for right in settings:
            if left.ecology_key == right.ecology_key:
                if result["settings"][left.key]["training_initial_conditions"] != result["settings"][right.key]["training_initial_conditions"]:
                    raise RuntimeError("Mutation variants must have matched training starts.")
            if left.population_size == right.population_size:
                if result["settings"][left.key]["founder_genomes_sha256"] != result["settings"][right.key]["founder_genomes_sha256"]:
                    raise RuntimeError("Food and mutation variants must share founder brains.")
    return result


def describe_pairs(left, right, label: str) -> dict:
    summary = paired_summary(left, right, seed=derived_seed(f"step14:bootstrap:{label}"))
    return {"n_seeds": summary["n_pairs"], "left_mean": summary["evolved_mean"],
            "right_mean": summary["control_mean"], "mean_difference": summary["mean_difference"],
            "difference_ci95": summary["difference_ci95"]}


def analyze_sweep(report: dict) -> dict:
    protocol, runs = report["protocol"], report["runs"]
    seeds = protocol["seeds"]
    if len(seeds) < 2 or len(set(seeds)) != len(seeds) or len(runs) != len(seeds) or {run["seed"] for run in runs} != set(seeds):
        raise ValueError("Analysis requires every planned independent seed.")
    runs = sorted(runs, key=lambda run: seeds.index(run["seed"]))
    settings = [Setting(**values) for values in protocol["settings"]]
    if STANDARD not in settings or len(set(settings)) != len(settings):
        raise ValueError("The sweep must contain the standard setting and unique variants.")
    if any(sum((s.mutation_rate != STANDARD.mutation_rate, s.population_size != STANDARD.population_size,
                s.food_count != STANDARD.food_count)) > 1 for s in settings):
        raise ValueError("The report must change only one factor per setting.")
    rows = {}
    for run in runs:
        if set(run["settings"]) != {setting.key for setting in settings}:
            raise ValueError("Each seed must complete every planned setting.")
        for setting in settings:
            record = run["settings"][setting.key]
            control = run["random_controls"][setting.ecology_key]
            for phase, count in (("training", protocol["generations"]), ("validation", 1)):
                if record[phase]["completed_generations"] != count or len(record[phase]["generations"]) != count:
                    raise ValueError("A sweep includes an incomplete training or validation run.")
                if (record[phase]["population_size"] != setting.population_size
                        or record[phase]["food_count"] != setting.food_count
                        or record[phase]["mutation_rate"] != setting.mutation_rate
                        or any(row["population_size"] != setting.population_size for row in record[phase]["generations"])):
                    raise ValueError("Recorded population, food, and mutation must match the planned setting.")
            if control["validation"]["completed_generations"] != 1 or len(control["validation"]["generations"]) != 1:
                raise ValueError("Random validation must be complete.")
            if (control["validation"]["population_size"] != setting.population_size
                    or control["validation"]["food_count"] != setting.food_count
                    or control["validation"]["controller"] != "random"
                    or control["validation"]["generations"][0]["population_size"] != setting.population_size):
                raise ValueError("Random validation must match the planned ecology.")
            if record["validation_initial_conditions"] != control["initial_conditions"]:
                raise ValueError("Validation groups must start with matched bodies and food.")
    for setting in settings:
        metrics = {}
        for metric in METRICS:
            evolved, random, standard, standard_random = [], [], [], []
            for run in runs:
                evolved.append(run["settings"][setting.key]["validation"]["generations"][0][metric])
                random.append(run["random_controls"][setting.ecology_key]["validation"]["generations"][0][metric])
                standard.append(run["settings"][STANDARD.key]["validation"]["generations"][0][metric])
                standard_random.append(run["random_controls"][STANDARD.ecology_key]["validation"]["generations"][0][metric])
            gaps = [left - right for left, right in zip(evolved, random)]
            standard_gaps = [left - right for left, right in zip(standard, standard_random)]
            metrics[metric] = {
                "evolved_vs_random": describe_pairs(evolved, random, f"{setting.key}:{metric}:random"),
                "change_from_standard": describe_pairs(evolved, standard, f"{setting.key}:{metric}:standard"),
                "advantage_change_from_standard": describe_pairs(gaps, standard_gaps, f"{setting.key}:{metric}:gap"),
            }
        rows[setting.key] = {"setting": asdict(setting), "metrics": metrics}
    return rows


def run_sweep(seeds=DEFAULT_SEEDS, *, settings=None, generations=5, workers=1,
              progress=False, checkpoint: Callable[[dict], None] | None = None) -> dict:
    seeds, settings = list(seeds), list(make_settings() if settings is None else settings)
    if len(seeds) < 2 or any(type(seed) is not int for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError("Use at least two distinct integer seeds.")
    if type(generations) is not int or generations < 2 or type(workers) is not int or workers < 1:
        raise ValueError("Use at least two generations and a positive worker count.")
    if not all(isinstance(setting, Setting) for setting in settings) or STANDARD not in settings or len(set(settings)) != len(settings):
        raise ValueError("Use unique settings including the standard world.")
    if any(sum((s.mutation_rate != STANDARD.mutation_rate, s.population_size != STANDARD.population_size,
                s.food_count != STANDARD.food_count)) > 1 for s in settings):
        raise ValueError("Change at most one factor from the standard setting.")
    report = {"format_version": 1, "status": "running", "protocol": {
        "seeds": seeds, "generations": generations, "settings": [asdict(setting) for setting in settings],
        "design": "one factor at a time around a fixed standard; no interaction estimates",
        "mutation_scale": DEFAULT_MUTATION_SCALE, "selection_fraction": SELECTION_FRACTION, "arena": [1000, 600],
        "validation_seed_namespace": "step14:validation", "validation_arenas_per_seed": 1,
        "analysis_unit": "independent training seed", "confidence_interval": "95% paired percentile bootstrap, 20000 resamples, pointwise",
        "inference": "exploratory only; no significance decisions or confirmed optimum",
        "population_interpretation": "fixed arena and food supply; includes density, competition, and different training-life budgets",
        "difficulty": "maintained pellet count; other survival rules fixed",
        "random_control_reuse": "one non-learning validation run per seed/population/food combination; no repeated training",
        "planned_unique_cohorts": len(seeds) * (len(settings) * (generations + 1) + len({s.ecology_key for s in settings})),
    }, "runs": []}
    if checkpoint:
        checkpoint(report)
    if workers == 1:
        for seed in seeds:
            report["runs"].append(run_seed(seed, settings, generations, progress))
            if checkpoint:
                checkpoint(report)
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(seeds))) as executor:
            futures = [executor.submit(run_seed, seed, settings, generations, progress) for seed in seeds]
            for future in as_completed(futures):
                report["runs"].append(future.result())
                if checkpoint:
                    checkpoint(report)
    report["runs"].sort(key=lambda run: seeds.index(run["seed"]))
    report["summary"] = analyze_sweep(report)
    report["status"] = "complete"
    if checkpoint:
        checkpoint(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--generations", type=positive_integer, default=5)
    parser.add_argument("--workers", type=positive_integer, default=1)
    parser.add_argument("--mutation-rates", type=mutation_probability, nargs="+", default=[0, 0.1, 0.3])
    parser.add_argument("--populations", type=positive_integer, nargs="+", default=[50, 100, 150])
    parser.add_argument("--food-counts", type=nonnegative_integer, nargs="+", default=[75, 150, 225])
    parser.add_argument("--output", type=Path, default=Path("results/parameter-sweep.json"))
    parser.add_argument("--plot", type=Path)
    args = parser.parse_args()
    def save(report):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    try:
        report = run_sweep(args.seeds, settings=make_settings(args.mutation_rates, args.populations, args.food_counts),
                           generations=args.generations, workers=args.workers, progress=True, checkpoint=save)
        if args.plot:
            from plot_parameters import save_parameter_plot
            save_parameter_plot(report, args.plot)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for key, summary in report["summary"].items():
        fitness = summary["metrics"]["mean_fitness"]["evolved_vs_random"]
        print(f"{key}: evolved fitness {fitness['left_mean']:.2f}; random {fitness['right_mean']:.2f}; "
              f"gap {fitness['mean_difference']:+.2f}; 95% paired interval {fitness['difference_ci95']}")
    print(f"Exploratory parameter report saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
