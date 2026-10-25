"""Disentangle useful food sensing from residual movement in saved evolved brains."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from analyze_intelligence import PARAMETER_NAMES, PARAMETER_SHAPES, bank_digest, steering_probe
from brain import MAX_TURN_RATE, NeuralNetwork
from compare_creatures import complete_generation, derived_seed, genome_digest, initial_conditions_digest, positive_integer
from experiment_speed import (DEFAULT_SEEDS, ENVIRONMENTS, FIXED_SPEED, TRAINING_CONFIG,
                              classify_primary, load_model, paired_metrics)
from simulation import EvolutionSimulation
from world import CLUSTER_COUNT, World


CONDITIONS = ("evolved_intact", "evolved_mirrored", "evolved_hidden",
              "unselected_intact", "unselected_mirrored", "unselected_hidden", "random")
METRICS = ("mean_fitness", "mean_food_eaten", "survival_rate")
PRIMARY_NAMES = ("useful_bearing", "evolved_bearing_benefit", "evolution_advantage", "residual_advantage")


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def movement_probe(bank):
    """Analytic open-space motion at constant hunger, without direct food inputs."""
    records = []
    for key, brain in sorted(bank.items()):
        turns = [float(brain.forward(np.array([0, 0, 0, hunger, 1, 1, 1, 1]))[0])
                 for hunger in (0.25, 0.75)]
        # Constant inputs to this feed-forward network imply constant angular speed.
        # Displacement / arc length after T=12s is |sinc(omega*T/(2*pi))|.
        straightness = np.abs(np.sinc(np.array(turns) * MAX_TURN_RATE * 12 / (2 * np.pi)))
        records.append({"creature_id": key, "mean_abs_turn": float(np.mean(np.abs(turns))),
                        "straightness_12s": float(np.mean(straightness))})
    if not records:
        raise ValueError("Movement probes require a nonempty brain cohort.")
    return {"hunger_states": [0.25, 0.75], "duration_seconds": 12, "brains": records,
            "mean_abs_turn": float(np.mean([r["mean_abs_turn"] for r in records])),
            "mean_straightness_12s": float(np.mean([r["straightness_12s"] for r in records]))}


def save_unselected(path, seed, initial, bank):
    """Persist the exact ancestral random weights, with no selection or training."""
    path = Path(path)
    if path.exists():
        metadata, saved = load_unselected(path, seed)
        if metadata["initial_conditions"] != initial or bank_digest(saved) != bank_digest(bank):
            raise ValueError("Existing unselected archive differs; preserve it and choose a new output directory.")
        return
    arrays = {"ids": np.array(sorted(bank), dtype=np.int64),
              "metadata": np.array(json.dumps({"format_version": 1, "kind": "unselected_founders",
                  "seed": seed, "initial_conditions": initial, "genomes_sha256": bank_digest(bank),
                  "fixed_speed": FIXED_SPEED}, allow_nan=False))}
    for index, attribute in enumerate(PARAMETER_NAMES):
        arrays[f"parameters_{index}"] = np.stack([getattr(bank[key], attribute) for key in sorted(bank)])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    temporary.replace(path)


def load_unselected(path, seed):
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata"].item()))
        ids = archive["ids"]
        if (metadata["format_version"] != 1 or metadata["kind"] != "unselected_founders"
                or metadata["seed"] != seed or metadata["fixed_speed"] != FIXED_SPEED
                or ids.dtype.kind not in "iu" or ids.tolist() != list(range(1, 101))):
            raise ValueError("Invalid unselected founder archive.")
        arrays = [archive[f"parameters_{index}"] for index in range(4)]
        if any(a.shape != (100, *shape) or not np.all(np.isfinite(a)) for a, shape in zip(arrays, PARAMETER_SHAPES)):
            raise ValueError("Invalid unselected parameter arrays.")
        bank = {}
        for index, key in enumerate(ids):
            brain = object.__new__(NeuralNetwork)
            for attribute, array in zip(PARAMETER_NAMES, arrays):
                setattr(brain, attribute, array[index].copy())
            bank[int(key)] = brain
        if bank_digest(bank) != metadata["genomes_sha256"]:
            raise ValueError("Unselected model hash mismatch.")
    return metadata, bank


def prepare_lineage(seed, generations, models_dir, unselected_dir=None):
    path = Path(models_dir) / f"seed-{seed}.npz"
    training, starts, evolved = load_model(path, seed, generations)
    founders = World(seed=seed, fixed_speed=FIXED_SPEED)
    initial = initial_conditions_digest(founders)
    if initial != starts[0]:
        raise ValueError("Reconstructed founders must match the saved Step 16 starting conditions.")
    unselected = {c.creature_id: c.brain.copy() for c in founders.creatures}
    path_unselected = Path(unselected_dir) / f"seed-{seed}.npz" if unselected_dir is not None else None
    if path_unselected is not None:
        if path_unselected.resolve() == path.resolve():
            raise ValueError("Unselected archives must never overwrite Step 16 models.")
        save_unselected(path_unselected, seed, initial, unselected)
    return training, starts, {"evolved": evolved, "unselected": unselected}, path_unselected


def run_lineage(seed, generations, repeats, models_dir, unselected_dir, forbidden, progress=False):
    training, starts, banks, unselected_file = prepare_lineage(seed, generations, models_dir, unselected_dir)
    hashes = {name: bank_digest(bank) for name, bank in banks.items()}
    probes = {name: {"steering": steering_probe(bank), "movement": movement_probe(bank)} for name, bank in banks.items()}
    tests = []
    for environment, settings in ENVIRONMENTS.items():
        for repeat in range(1, repeats + 1):
            test_seed = derived_seed(f"step17:test:{seed}:{environment}:{repeat}")
            test = {"environment": environment, "repeat": repeat, "seed": test_seed, "conditions": {}}
            reference = None
            for condition in CONDITIONS:
                bank_name, mode = ("evolved", "intact") if condition == "random" else condition.split("_", 1)
                world = World(*settings["arena_size"], seed=test_seed, fixed_speed=FIXED_SPEED,
                              food_distribution=settings["food_distribution"], food_sensor_mode=mode,
                              controller="random" if condition == "random" else "neural", evolution_enabled=False)
                for creature in world.creatures:
                    creature.brain = banks[bank_name][creature.creature_id].copy()
                    if creature.speed != FIXED_SPEED or creature.energy_cost_per_second != 5.0:
                        raise RuntimeError("All conditions require identical speed and per-second energy cost.")
                initial = initial_conditions_digest(world)
                if initial in forbidden or initial in starts or (reference is not None and initial != reference):
                    raise RuntimeError("Test layouts must be unseen and physically matched.")
                reference = initial
                simulation = EvolutionSimulation(world, generation_limit=1, auto_advance=False)
                complete_generation(simulation)
                if genome_digest(world.dead_creatures) != hashes[bank_name]:
                    raise RuntimeError("Testing changed a frozen brain.")
                test["conditions"][condition] = {"initial_conditions": initial,
                    "genomes_sha256": hashes[bank_name], "report": simulation.report()}
            tests.append(test)
            if progress:
                print(f"Seed {seed}: {environment}, repeat {repeat}/{repeats}, all seven conditions complete", flush=True)
    if any(bank_digest(bank) != hashes[name] for name, bank in banks.items()):
        raise RuntimeError("Probes or tests changed source weights.")
    path = Path(models_dir) / f"seed-{seed}.npz"
    return {"seed": seed, "source_model_file": str(path), "source_model_sha256": file_digest(path),
            "source_training": training, "source_training_initial_conditions": starts,
            "unselected_model_file": str(unselected_file) if unselected_file is not None else None,
            "genome_hashes": hashes, "probes": probes, "tests": tests}


def primary_effects(values, environment):
    def effect(left, right, name):
        return paired_metrics(left, right, seed=derived_seed(f"step17:bootstrap:{environment}:{name}"))
    food = {c: np.asarray(v["mean_food_eaten"]) for c, v in values.items()}
    fitness = {c: v["mean_fitness"] for c, v in values.items()}
    return {
        "useful_bearing": effect(food["evolved_intact"], food["evolved_mirrored"], "useful_bearing"),
        "evolved_bearing_benefit": effect(food["evolved_intact"] - food["evolved_mirrored"],
            food["unselected_intact"] - food["unselected_mirrored"], "evolved_bearing_benefit"),
        "evolution_advantage": effect(fitness["evolved_intact"], fitness["unselected_intact"], "evolution_advantage"),
        "residual_advantage": effect(fitness["evolved_hidden"], fitness["unselected_hidden"], "residual_advantage"),
    }


def validate_probe(probe):
    steering, movement = probe["steering"], probe["movement"]
    if (steering["pose_pairs_per_brain"] != 12 or movement["duration_seconds"] != 12
            or movement["hunger_states"] != [0.25, 0.75]):
        raise ValueError("Incorrect probe design.")
    for data, metrics in ((steering, (("steering_gain", "mean_steering_gain", -1, 1),
                                     ("both_sides_correct_fraction", "mean_both_sides_correct_fraction", 0, 1))),
                          (movement, (("mean_abs_turn", "mean_abs_turn", 0, 1),
                                      ("straightness_12s", "mean_straightness_12s", 0, 1)))):
        if len(data["brains"]) != 100 or sorted(r["creature_id"] for r in data["brains"]) != list(range(1, 101)):
            raise ValueError("Probes require the complete 100-brain cohort.")
        for metric, summary, low, high in metrics:
            if (any(not low <= r[metric] <= high for r in data["brains"])
                    or not np.isclose(data[summary], np.mean([r[metric] for r in data["brains"]]))):
                raise ValueError("Probe summary does not match finite per-brain responses.")


def analyze_results(report):
    protocol, trials = report["protocol"], report["trials"]
    seeds, repeats = protocol["seeds"], protocol["repeats_per_environment"]
    if (len(seeds) < 2 or len(set(seeds)) != len(seeds) or len(trials) != len(seeds)
            or {t["seed"] for t in trials} != set(seeds) or protocol["environments"] != ENVIRONMENTS
            or protocol["conditions"] != list(CONDITIONS) or type(repeats) is not int or repeats < 1):
        raise ValueError("Analysis requires the complete planned matched study.")
    trials = sorted(trials, key=lambda t: seeds.index(t["seed"]))
    expected = {(env, repeat) for env in ENVIRONMENTS for repeat in range(1, repeats + 1)}
    seen = set()
    forbidden = set(protocol["excluded_initial_conditions"])
    for trial in trials:
        source = protocol["source_models"][str(trial["seed"])]
        training = trial["source_training"]
        if (trial["source_model_sha256"] != source["file_sha256"]
                or trial["genome_hashes"]["evolved"] != source["genomes_sha256"]
                or training["seed"] != trial["seed"]
                or training["completed_generations"] != protocol["source_generations"]
                or len(training["generations"]) != protocol["source_generations"]
                or any(training[k] != v for k, v in TRAINING_CONFIG.items())
                or trial["source_training_initial_conditions"] != source["training_initial_conditions"]):
            raise ValueError("Evolved brains must come from the declared unchanged fixed-speed source models.")
        for name in ("evolved", "unselected"):
            validate_probe(trial["probes"][name])
        if len(trial["tests"]) != len(expected) or {(t["environment"], t["repeat"]) for t in trial["tests"]} != expected:
            raise ValueError("Every environment and repeat must be present exactly once.")
        for test in trial["tests"]:
            if (test["seed"] != derived_seed(f"step17:test:{trial['seed']}:{test['environment']}:{test['repeat']}")
                    or set(test["conditions"]) != set(CONDITIONS)):
                raise ValueError("Incorrect test namespace or missing intervention/control.")
            starts = {r["initial_conditions"] for r in test["conditions"].values()}
            if len(starts) != 1 or starts.intersection(forbidden) or starts.intersection(seen):
                raise ValueError("Test starts must be matched, unseen, and distinct.")
            seen.update(starts)
            centers = None
            for condition, record in test["conditions"].items():
                bank, mode = ("evolved", "intact") if condition == "random" else condition.split("_", 1)
                data = record["report"]
                settings = ENVIRONMENTS[test["environment"]]
                if (data["completed_generations"] != 1 or len(data["generations"]) != 1
                        or data["population_size"] != 100 or data["food_count"] != 150
                        or data["seed"] != test["seed"] or data["evolution_enabled"]
                        or data["fixed_speed"] != FIXED_SPEED or data["food_sensor_mode"] != mode
                        or data["food_distribution"] != settings["food_distribution"]
                        or data["arena_size"] != settings["arena_size"]
                        or data["controller"] != ("random" if condition == "random" else "neural")
                        or record["genomes_sha256"] != trial["genome_hashes"][bank]):
                    raise ValueError("Reports must match the frozen bank, sensor mode, speed, controller, and environment.")
                if centers is not None and centers != data["food_cluster_centers"]:
                    raise ValueError("Cluster centers must match across interventions.")
                centers = data["food_cluster_centers"]
                if len(centers) != (CLUSTER_COUNT if settings["food_distribution"] == "clustered" else 0):
                    raise ValueError("Incorrect food cluster configuration.")
                stats = data["generations"][0]
                if (stats["population_size"] != 100 or not np.isclose(stats["mean_speed"], FIXED_SPEED)
                        or not all(np.isfinite(stats[m]) for m in METRICS)
                        or stats["survival_rate"] != stats["survivors_at_checkpoint"] / 100
                        or not 0 <= stats["survival_rate"] <= 1 or stats["mean_food_eaten"] < 0
                        or not np.isclose(stats["mean_fitness"], stats["mean_survival_seconds"] + 10 * stats["mean_food_eaten"])):
                    raise ValueError("Invalid speed, score, denominator, or non-finite metric.")
    environments, primary = {}, []
    for environment in ENVIRONMENTS:
        values = {c: {m: [] for m in METRICS} for c in CONDITIONS}
        for trial in trials:
            tests = [t for t in trial["tests"] if t["environment"] == environment]
            for c in CONDITIONS:
                for metric in METRICS:
                    values[c][metric].append(float(np.mean([t["conditions"][c]["report"]["generations"][0][metric] for t in tests])))
        effects = primary_effects(values, environment)
        primary.extend(effects.values())
        secondary = {}
        for label, left, right in (("evolved_hidden_vs_random", "evolved_hidden", "random"),
                                   ("unselected_hidden_vs_random", "unselected_hidden", "random"),
                                   ("evolved_intact_vs_hidden", "evolved_intact", "evolved_hidden"),
                                   ("evolved_intact_vs_random", "evolved_intact", "random")):
            secondary[label] = {}
            for metric in METRICS:
                result = paired_metrics(values[left][metric], values[right][metric],
                                        seed=derived_seed(f"step17:secondary:{environment}:{label}:{metric}"))
                result.pop("sign_test_p")
                secondary[label][metric] = result
        environments[environment] = {"seed_values": values, "primary_tests": effects, "secondary": secondary,
            "condition_means": {c: {m: float(np.mean(v)) for m, v in metrics.items()} for c, metrics in values.items()}}
    classify_primary(primary)
    for data in environments.values():
        effects = data["primary_tests"]
        data["evidence"] = {
            "evolved_food_guidance_supported": all(effects[name]["conclusion"] == "higher" for name in PRIMARY_NAMES[:3]),
            "residual_evolved_advantage_with_direct_food_inputs_hidden": effects["residual_advantage"]["conclusion"],
            "interpretation_limit": "Hidden inputs are a distribution shift; hunger retains indirect eating feedback. Residual benefit does not identify an exclusive movement strategy or exclude food-guided behavior.",
        }
    probes = {name: {"steering_gain": float(np.mean([t["probes"][name]["steering"]["mean_steering_gain"] for t in trials])),
                    "both_sides_correct_fraction": float(np.mean([t["probes"][name]["steering"]["mean_both_sides_correct_fraction"] for t in trials])),
                    "abs_no_food_turn": float(np.mean([t["probes"][name]["movement"]["mean_abs_turn"] for t in trials])),
                    "open_space_straightness_12s": float(np.mean([t["probes"][name]["movement"]["mean_straightness_12s"] for t in trials]))}
              for name in ("evolved", "unselected")}
    return {"independent_lineages": len(seeds), "environments": environments, "probe_means": probes}


def run_study(seeds=DEFAULT_SEEDS, *, models_dir=Path("results/step16-models"), prior_report=Path("results/step16-speed-comparison.json"),
              unselected_dir=None, generations=10, repeats=1, workers=1, progress=False, checkpoint=None):
    seeds = list(seeds)
    if (len(seeds) < 2 or any(type(s) is not int for s in seeds) or len(set(seeds)) != len(seeds)
            or type(generations) is not int or generations < 2 or type(repeats) is not int or repeats < 1
            or type(workers) is not int or workers < 1):
        raise ValueError("Use distinct integer seeds, at least two source generations, and positive repeats/workers.")
    if unselected_dir is not None and Path(unselected_dir).resolve() == Path(models_dir).resolve():
        raise ValueError("Save unselected models separately from the original evolved models.")
    prior = json.loads(Path(prior_report).read_text())
    if prior.get("status") != "complete":
        raise ValueError("The source Step 16 report must be complete.")
    source_trials = {t["seed"]: t for t in prior["trials"]}
    forbidden = {start for t in prior["trials"] for start in t["training_initial_conditions"]}
    forbidden.update(row["initial_conditions"] for t in prior["trials"] for test in t["tests"] for row in test["conditions"].values())
    sources = {}
    for seed in seeds:
        path = Path(models_dir) / f"seed-{seed}.npz"
        training, starts, bank = load_model(path, seed, generations)
        if seed not in source_trials or source_trials[seed]["genomes_sha256"] != bank_digest(bank):
            raise ValueError("Each source model must match its published Step 16 lineage.")
        forbidden.update(starts)
        sources[str(seed)] = {"file": str(path), "file_sha256": file_digest(path),
                              "genomes_sha256": bank_digest(bank), "training_initial_conditions": starts}
    report = {"format_version": 1, "status": "running", "protocol": {
        "seeds": seeds, "source_generations": generations, "repeats_per_environment": repeats,
        "environments": json.loads(json.dumps(ENVIRONMENTS)), "conditions": list(CONDITIONS),
        "source_models": sources, "prior_report_file": str(prior_report), "prior_report_sha256": file_digest(prior_report),
        "excluded_initial_conditions": sorted(forbidden), "training_cohorts": 0,
        "planned_test_cohorts": len(seeds) * len(ENVIRONMENTS) * repeats * len(CONDITIONS),
        "unselected_baseline": "Original random founders reconstructed from the same training seed, before selection/mutation; starting physical hash checked against Step 16. No training or selection performed.",
        "speed_pixels_per_second": FIXED_SPEED, "energy_cost_per_living_second": 5.0,
        "primary_family": "12 two-sided exact paired sign tests: four contrasts in each of three environments; Holm correction across all 12",
        "primary_contrasts": {
            "useful_bearing": "evolved intact minus mirrored meals",
            "evolved_bearing_benefit": "(evolved intact minus mirrored meals) minus (unselected intact minus mirrored meals)",
            "evolution_advantage": "evolved intact minus unselected intact fitness",
            "residual_advantage": "evolved hidden minus unselected hidden fitness"},
        "sign_tie_tolerance_abs": 1e-10, "intervals": "95% paired percentile bootstrap, 20000 resamples, pointwise",
        "analysis_unit": "one source training lineage; test repeats averaged within environment before inference",
        "decision": "Higher/lower requires Holm p < 0.05 and mean-difference interval excluding zero in the same direction. Food-guidance attribution requires useful_bearing, evolved_bearing_benefit, and evolution_advantage all higher within an environment.",
        "secondary": "Other contrasts and steering/movement probes are descriptive, without confirmatory p-values.",
        "diagnostic_probes": {
            "steering": "12 left/right target pairs per brain: +/-45 and +/-90 degrees, distances 40/80/120, hunger .25/.75, open walls; report gain and correct turn commands on both sides",
            "movement": "No direct food inputs, open walls, hunger clamped at .25/.75; constant feed-forward turn response; analytic displacement/arc length after 12 seconds. Not a natural trajectory or planning test."},
        "limitations": "Mirroring changes bearing use; hidden food channels can cause input distribution shift and hunger retains indirect eating feedback. Residual benefits cannot establish an exclusive strategy. Founder comparison measures evolutionary history, without a neutral-mutation control. No planning or human-like intelligence claim.",
    }, "trials": []}
    if checkpoint:
        checkpoint(report)
    if workers == 1:
        for seed in seeds:
            report["trials"].append(run_lineage(seed, generations, repeats, models_dir, unselected_dir, forbidden, progress))
            if checkpoint:
                checkpoint(report)
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(seeds))) as executor:
            futures = [executor.submit(run_lineage, seed, generations, repeats, models_dir, unselected_dir, forbidden, progress) for seed in seeds]
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
    parser.add_argument("--models-dir", type=Path, default=Path("results/step16-models"))
    parser.add_argument("--prior-report", type=Path, default=Path("results/step16-speed-comparison.json"))
    parser.add_argument("--unselected-models-dir", type=Path, default=Path("results/step17-unselected-models"))
    parser.add_argument("--source-generations", type=positive_integer, default=10)
    parser.add_argument("--repeats", type=positive_integer, default=1)
    parser.add_argument("--workers", type=positive_integer, default=1)
    parser.add_argument("--output", type=Path, default=Path("results/strategy.json"))
    parser.add_argument("--protocol-output", type=Path)
    parser.add_argument("--plot", type=Path)
    args = parser.parse_args()
    outputs = [path.resolve() for path in (args.output, args.protocol_output, args.plot) if path is not None]
    protected = {args.prior_report.resolve(), *[p.resolve() for p in args.models_dir.glob("*.npz")]}
    if len(set(outputs)) != len(outputs) or any(path in protected for path in outputs):
        parser.error("Output paths must be distinct and must preserve the source report and models.")
    def save(report):
        if args.protocol_output is not None and not report["trials"]:
            source = Path(__file__).resolve().parent
            declaration = {"declared_at_utc": datetime.now(timezone.utc).isoformat(), "protocol": report["protocol"],
                           "source_sha256": {p.name: file_digest(p) for p in sorted(source.glob("*.py"))}}
            args.protocol_output.parent.mkdir(parents=True, exist_ok=True)
            args.protocol_output.write_text(json.dumps(declaration, indent=2, allow_nan=False) + "\n")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(".tmp.json")
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        temporary.replace(args.output)
    try:
        report = run_study(args.seeds, models_dir=args.models_dir, prior_report=args.prior_report,
                           unselected_dir=args.unselected_models_dir, generations=args.source_generations,
                           repeats=args.repeats, workers=args.workers, progress=True, checkpoint=save)
        if args.plot:
            from plot_strategy import save_strategy_plot
            save_strategy_plot(report, args.plot)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for environment, data in report["analysis"]["environments"].items():
        for name, result in data["primary_tests"].items():
            print(f"{environment}/{name}: {result['mean_difference']:+.4f}; Holm p={result['holm_adjusted_p']:.5f}; {result['conclusion']}")
    print(f"Strategy analysis saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
