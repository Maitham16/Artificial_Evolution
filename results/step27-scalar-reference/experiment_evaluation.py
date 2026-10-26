"""Step 27: matched held-out evaluation of selection, drift, and steering rules.

Reuses every declared Step 18 seed pair; never selects models using these tests.
Run from the project root so recorded relative artifact paths remain portable.
"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from types import SimpleNamespace
import argparse
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from analyze_intelligence import bank_digest
from compare_creatures import complete_generation, derived_seed, genome_digest, initial_conditions_digest, positive_integer
from experiment_selection import ARMS, RecordedMutationRNG, load_models
from experiment_speed import FIXED_SPEED, TRAINING_CONFIG, classify_primary, paired_metrics
from experiment_strategy import file_digest
from reproduction import reproduce_brains
from simulation import EvolutionSimulation
from world import CLUSTER_COUNT, World


DEFAULT_SEEDS = tuple(range(1801, 1817))
SOURCE_REPORT = Path("results/step18-selection.json")
MODELS_DIR = Path("results/step18-models")
GENERATIONS = 10
BASELINES = ("random", "greedy", "evolved", "neutral")
DIAGNOSTICS = ("founder", "evolved_hidden", "neutral_hidden")
METRICS = ("mean_fitness", "mean_food_eaten", "survival_rate")
EXTRA_METRICS = ("mean_survival_seconds", "starvation_rate", "zero_meal_rate")
ENVIRONMENTS = {
    "uniform": {"arena_size": [1000, 600], "food_distribution": "uniform", "food_count": 150},
    "clustered": {"arena_size": [1000, 600], "food_distribution": "clustered", "food_count": 150},
    "sparse": {"arena_size": [1000, 600], "food_distribution": "uniform", "food_count": 50},
    "wide_clustered": {"arena_size": [1200, 500], "food_distribution": "clustered", "food_count": 150},
    "barren": {"arena_size": [1000, 600], "food_distribution": "uniform", "food_count": 0},
}
BANK_FOR = {"random": "founder", "greedy": "founder", "evolved": "selection", "neutral": "random_parent",
            "founder": "founder", "evolved_hidden": "selection", "neutral_hidden": "random_parent"}
DIVERSITY_METRICS = ("full_rms", "steering_rms", "effective_founder_families")
BOOTSTRAPS = 20000


def conditions_for(environment):
    # With no food, a food-input intervention is identical by construction.
    return (*BASELINES, "founder") if environment == "barren" else (*BASELINES, *DIAGNOSTICS)


def neural_features(bank, steering_only=False):
    rows = []
    for key in sorted(bank):
        brain = bank[key]
        if steering_only:
            arrays = (brain.input_weights.ravel(), brain.hidden_bias, brain.output_weights[:, 0], brain.output_bias[:1])
        else:
            arrays = tuple(p.ravel() for p in brain.parameters)
        scales = (1 / math.sqrt(8), .1, 1 / math.sqrt(8), .1)
        row = np.concatenate([p / scale for p, scale in zip(arrays, scales)])
        rows.append(row / math.sqrt(len(row)))
    return np.stack(rows)


def genetic_diversity(bank, origins):
    """RMS unordered-pair distance, standardized by initialization scales."""
    if set(bank) != set(origins) or len(bank) < 2:
        raise ValueError("Diversity requires matching genomes and founder labels, with at least two actors.")
    result = {}
    for name, steering in (("full_rms", False), ("steering_rms", True)):
        x = neural_features(bank, steering)
        result[name] = float(np.sqrt(2 * len(x) / (len(x) - 1) * np.var(x, axis=0).sum()))
    counts = Counter(origins.values())
    p = np.array(list(counts.values())) / len(bank)
    result.update(effective_founder_families=float(np.exp(-np.sum(p * np.log(p)))),
                  founder_families=len(counts), unique_genomes=len({bank_digest({0: b}) for b in bank.values()}),
                  founder_counts={str(k): v for k, v in sorted(counts.items())})
    return result


def replay_diversity(seed, transitions, banks):
    """Replay every inherited genome from founders and recorded mutation draws."""
    output = {}
    for arm in ARMS:
        bank = {k: b.copy() for k, b in banks["founder"].items()}
        origins = {k: k for k in bank}
        rows = [{"generation": 1, **genetic_diversity(bank, origins)}]
        for trace in transitions[arm]:
            parents = [SimpleNamespace(creature_id=k, brain=bank[k]) for k in trace["parent_ids"]]
            rng = RecordedMutationRNG(trace["mutation_seed"])
            children = reproduce_brains(parents, rng, mutation_rate=.1, mutation_scale=.1)
            if (rng.digest.hexdigest() != trace["mutation_draws_sha256"] or rng.calls != trace["mutation_rng_calls"]
                    or [c.parent_id for c in children] != trace["offspring_parent_ids"]
                    or [c.mutations for c in children] != trace["offspring_mutation_counts"]):
                raise ValueError("Recorded mutation or parent assignment cannot be reproduced.")
            origins = {i: origins[c.parent_id] for i, c in enumerate(children, 1)}
            bank = {i: c.brain for i, c in enumerate(children, 1)}
            rows.append({"generation": trace["to_generation"], **genetic_diversity(bank, origins)})
        if bank_digest(bank) != bank_digest(banks[arm]):
            raise ValueError("Replayed inheritance does not equal the frozen final population.")
        output[arm] = rows
    return output


def individual_records(world):
    return [{"id": c.creature_id, "age": c.age, "lifespan": c.lifespan, "food_eaten": c.food_eaten,
             "fitness": c.fitness, "energy": c.energy, "death_cause": c.death_cause}
            for c in sorted(world.dead_creatures, key=lambda c: c.creature_id)]


def validate_individuals(record):
    people = record["individuals"]
    stats = record["report"]["generations"][0]
    if len(people) != 100 or [c["id"] for c in people] != list(range(1, 101)):
        raise ValueError("Retain all 100 test lifetimes, including early deaths.")
    for c in people:
        if (not all(np.isfinite(c[k]) for k in ("age", "lifespan", "fitness", "energy"))
                or not 0 <= c["age"] <= c["lifespan"] or not 60 <= c["lifespan"] <= 120
                or not 0 <= c["energy"] <= 100 or type(c["food_eaten"]) is not int or c["food_eaten"] < 0
                or c["death_cause"] not in ("starvation", "old_age")
                or not np.isclose(c["fitness"], c["age"] + 10 * c["food_eaten"], rtol=0, atol=1e-8)
                or (c["death_cause"] == "starvation" and c["energy"] != 0)
                or (c["death_cause"] == "old_age" and c["age"] != c["lifespan"])):
            raise ValueError("Invalid completed individual lifetime or fitness.")
    expected = {
        "mean_fitness": np.mean([c["fitness"] for c in people]),
        "best_fitness": max(c["fitness"] for c in people),
        "mean_food_eaten": np.mean([c["food_eaten"] for c in people]),
        "mean_survival_seconds": np.mean([c["age"] for c in people]),
        "survival_rate": sum(c["age"] >= 60 for c in people) / 100,
    }
    if any(not np.isclose(stats[k], v, rtol=0, atol=1e-8) for k, v in expected.items()):
        raise ValueError("Cohort metrics disagree with retained individual lifetimes.")
    rates = {"starvation_rate": sum(c["death_cause"] == "starvation" for c in people) / 100,
             "zero_meal_rate": sum(c["food_eaten"] == 0 for c in people) / 100}
    if record["failure_rates"] != rates:
        raise ValueError("Failure rates must count the complete cohort.")
    return expected


def run_lineage(seed, model_file, model_sha256, repeats, runs_dir, forbidden, progress=False):
    if file_digest(model_file) != model_sha256:
        raise ValueError("Source model archive changed since declaration.")
    training, starts, transitions, banks = load_models(model_file, seed, GENERATIONS)
    diversity = replay_diversity(seed, transitions, banks)
    hashes = {name: bank_digest(bank) for name, bank in banks.items()}
    trial = {"seed": seed, "model_file": str(model_file), "model_sha256": model_sha256,
             "training": training, "training_initial_conditions": starts, "genome_hashes": hashes,
             "diversity": diversity, "tests": []}
    for environment, settings in ENVIRONMENTS.items():
        for repeat in range(1, repeats + 1):
            test_seed = derived_seed(f"step27:test:{seed}:{environment}:{repeat}")
            test = {"environment": environment, "repeat": repeat, "seed": test_seed, "conditions": {}}
            reference = None
            for condition in conditions_for(environment):
                bank = banks[BANK_FOR[condition]]
                world = World(*settings["arena_size"], seed=test_seed, fixed_speed=FIXED_SPEED,
                              food_count=settings["food_count"], food_distribution=settings["food_distribution"],
                              evolution_enabled=False, controller=condition if condition in ("random", "greedy") else "neural",
                              food_sensor_mode="hidden" if condition.endswith("_hidden") else "intact")
                for c in world.creatures:
                    c.brain = bank[c.creature_id].copy()
                    if c.speed != 60 or c.energy_cost_per_second != 5:
                        raise RuntimeError("All policies need identical cruise speed and energy costs.")
                initial = initial_conditions_digest(world)
                if initial in forbidden or (reference is not None and initial != reference):
                    raise RuntimeError("Use matched physical starts and previously unseen test worlds.")
                reference = initial
                simulation = EvolutionSimulation(world, generation_limit=1, auto_advance=False)
                complete_generation(simulation)
                if genome_digest(world.dead_creatures) != hashes[BANK_FOR[condition]]:
                    raise RuntimeError("A frozen test population changed its weights.")
                people = individual_records(world)
                record = {"initial_conditions": initial, "genomes_sha256": hashes[BANK_FOR[condition]],
                          "report": simulation.report(), "individuals": people,
                          "failure_rates": {"starvation_rate": sum(c["death_cause"] == "starvation" for c in people) / 100,
                                            "zero_meal_rate": sum(c["food_eaten"] == 0 for c in people) / 100}}
                validate_individuals(record)
                test["conditions"][condition] = record
            trial["tests"].append(test)
            if progress:
                print(f"Seed {seed}: {environment} repeat {repeat}/{repeats} complete ({len(test['conditions'])} controllers)", flush=True)
    if any(bank_digest(bank) != hashes[name] for name, bank in banks.items()):
        raise RuntimeError("Source weights changed during evaluation.")
    path = Path(runs_dir) / f"seed-{seed}.json.gz"
    if path.exists():
        raise ValueError("Preserve existing test records; use a new run directory.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as stream:
        stream.write(json.dumps(trial, separators=(",", ":"), allow_nan=False).encode())
    compact = copy.deepcopy(trial)
    for test in compact["tests"]:
        for record in test["conditions"].values():
            del record["individuals"]
    compact.update(raw_file=str(path), raw_sha256=file_digest(path))
    return compact


def load_raw(trial):
    if file_digest(trial["raw_file"]) != trial["raw_sha256"]:
        raise ValueError("Raw individual lifetime checksum changed.")
    with gzip.open(trial["raw_file"], "rt") as stream:
        raw = json.load(stream)
    compact = copy.deepcopy(raw)
    for test in compact["tests"]:
        for record in test["conditions"].values():
            validate_individuals(record)
            del record["individuals"]
    compact.update(raw_file=trial["raw_file"], raw_sha256=trial["raw_sha256"])
    if compact != trial:
        raise ValueError("Published summaries disagree with the full raw test archive.")
    return raw


def mean_interval(values, label):
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) < 2 or not np.all(np.isfinite(values)):
        raise ValueError("Confidence intervals require finite independent seed means.")
    indices = np.random.default_rng(derived_seed(f"step27:mean:{label}")).integers(len(values), size=(BOOTSTRAPS, len(values)))
    low, high = np.quantile(values[indices].mean(axis=1), [.025, .975])
    return {"n_seeds": len(values), "mean": float(values.mean()), "ci95": [float(low), float(high)]}


def effect(left, right, label, tested=False):
    row = paired_metrics(left, right, seed=derived_seed(f"step27:paired:{label}"))
    row["left_mean"] = row.pop("evolved_mean")
    row["right_mean"] = row.pop("control_mean")
    if not tested:
        row.pop("sign_test_p")
    return row


def validate_study(report, verify_files=True):
    p, trials = report["protocol"], report["trials"]
    seeds, repeats = p["seeds"], p["repeats_per_environment"]
    if (len(seeds) < 2 or len(seeds) != len(set(seeds)) or any(type(s) is not int for s in seeds)
            or len(trials) != len(seeds) or [t["seed"] for t in trials] != seeds
            or p["environments"] != ENVIRONMENTS or p["baselines"] != list(BASELINES)
            or p["conditions_by_environment"] != {e: list(conditions_for(e)) for e in ENVIRONMENTS}
            or p["training_generations"] != GENERATIONS or p["inherited_transitions"] != GENERATIONS - 1
            or p["training_configuration"] != TRAINING_CONFIG
            or type(repeats) is not int or repeats < 1):
        raise ValueError("Analyze the complete declared matched evaluation.")
    if (p["planned_new_training_cohorts"] != 0
            or p["planned_test_cohorts"] != len(seeds) * repeats * sum(len(conditions_for(e)) for e in ENVIRONMENTS)):
        raise ValueError("The declared evaluation budget changed.")
    if verify_files and file_digest(p["source_report"]) != p["source_report_sha256"]:
        raise ValueError("The published source study changed.")
    forbidden = set(p["excluded_initial_conditions"])
    forbidden.update(s for t in trials for s in t["training_initial_conditions"]["selection"])
    seen = set()
    expected = {(e, r) for e in ENVIRONMENTS for r in range(1, repeats + 1)}
    for trial in trials:
        declared = p["source_models"][str(trial["seed"])]
        if (trial["model_file"] != declared["path"] or trial["model_sha256"] != declared["sha256"]
                or trial["genome_hashes"] != declared["genome_hashes"]):
            raise ValueError("Every seed must use its declared source populations.")
        if verify_files:
            load_raw(trial)
            if file_digest(trial["model_file"]) != trial["model_sha256"]:
                raise ValueError("A source archive changed.")
            training, starts, transitions, banks = load_models(trial["model_file"], trial["seed"], GENERATIONS)
            if (training != trial["training"] or starts != trial["training_initial_conditions"]
                    or replay_diversity(trial["seed"], transitions, banks) != trial["diversity"]):
                raise ValueError("Training provenance or genetic-diversity replay changed.")
        if len(trial["tests"]) != len(expected) or {(t["environment"], t["repeat"]) for t in trial["tests"]} != expected:
            raise ValueError("Missing or duplicated environment/repeat cells.")
        for test in trial["tests"]:
            env = test["environment"]
            if (test["seed"] != derived_seed(f"step27:test:{trial['seed']}:{env}:{test['repeat']}")
                    or set(test["conditions"]) != set(conditions_for(env))):
                raise ValueError("Incorrect test seed or missing controller.")
            starts = {r["initial_conditions"] for r in test["conditions"].values()}
            if len(starts) != 1 or starts & (forbidden | seen):
                raise ValueError("Test starts must match and be new across all seeds and prior experiments.")
            seen.update(starts)
            centers = None
            for condition, record in test["conditions"].items():
                data, settings = record["report"], ENVIRONMENTS[env]
                if (data["seed"] != test["seed"] or data["completed_generations"] != 1 or len(data["generations"]) != 1
                        or data["generation_limit"] != 1 or data["evolution_enabled"] or data["population_size"] != 100
                        or data["fixed_speed"] != 60 or data["simulation_step_seconds"] != 1 / 60
                        or any(data[k] != v for k, v in settings.items())
                        or data["controller"] != (condition if condition in ("random", "greedy") else "neural")
                        or data["food_sensor_mode"] != ("hidden" if condition.endswith("_hidden") else "intact")
                        or record["genomes_sha256"] != trial["genome_hashes"][BANK_FOR[condition]]):
                    raise ValueError("Test conditions changed physics, policy, or frozen genomes.")
                if centers is not None and centers != data["food_cluster_centers"]:
                    raise ValueError("Cluster centers must match across controllers.")
                centers = data["food_cluster_centers"]
                if len(centers) != (CLUSTER_COUNT if settings["food_distribution"] == "clustered" else 0):
                    raise ValueError("Incorrect food geometry.")
                stats = data["generations"][0]
                if (stats["population_size"] != 100 or not np.isclose(stats["mean_speed"], 60)
                        or not all(np.isfinite(stats[k]) for k in (*METRICS, "mean_survival_seconds"))
                        or stats["survival_rate"] != stats["survivors_at_checkpoint"] / 100
                        or not 0 <= stats["survival_rate"] <= 1 or stats["mean_food_eaten"] < 0
                        or not np.isclose(stats["mean_fitness"], stats["mean_survival_seconds"] + 10 * stats["mean_food_eaten"])):
                    raise ValueError("Invalid completed-cohort scores or common speed.")


def analyze_results(report, verify_files=True):
    validate_study(report, verify_files)
    trials, p = report["trials"], report["protocol"]
    primary, secondary = [], []
    analysis = {"independent_seed_pairs": len(trials), "environments": {}, "diversity": {}, "training_curves": {}}
    for env in ENVIRONMENTS:
        values = {c: {m: [] for m in (*METRICS, *EXTRA_METRICS)} for c in conditions_for(env)}
        for trial in trials:
            tests = [t for t in trial["tests"] if t["environment"] == env]
            for condition in values:
                for metric in values[condition]:
                    values[condition][metric].append(float(np.mean([
                        (t["conditions"][condition]["failure_rates"][metric] if metric in ("starvation_rate", "zero_meal_rate")
                         else t["conditions"][condition]["report"]["generations"][0][metric]) for t in tests])))
        estimates = {c: {m: mean_interval(v, f"{env}:{c}:{m}") for m, v in row.items()} for c, row in values.items()}
        comparisons = {}
        for control in ("random", "greedy", "neutral"):
            label = f"evolved_minus_{control}"
            comparisons[label] = {}
            for metric in METRICS:
                row = effect(values["evolved"][metric], values[control][metric], f"{env}:{label}:{metric}", True)
                primary.append(row)
                comparisons[label][metric] = row
        adaptation = {}
        for condition in ("evolved", "neutral"):
            adaptation[condition] = {}
            for metric in METRICS:
                row = effect(values[condition][metric], values["founder"][metric], f"{env}:{condition}:adaptation:{metric}", metric == "mean_fitness")
                adaptation[condition][metric] = row
                if metric == "mean_fitness":
                    secondary.append(row)
        sensor = {}
        if env != "barren":
            for metric in METRICS:
                selected_loss = np.array(values["evolved"][metric]) - values["evolved_hidden"][metric]
                neutral_loss = np.array(values["neutral"][metric]) - values["neutral_hidden"][metric]
                loss = effect(values["evolved"][metric], values["evolved_hidden"][metric], f"{env}:food_loss:{metric}", metric == "mean_fitness")
                interaction = effect(selected_loss, neutral_loss, f"{env}:food_interaction:{metric}", metric == "mean_fitness")
                sensor[metric] = {"evolved_sensor_loss": loss, "selection_minus_neutral_sensor_loss": interaction}
                if metric == "mean_fitness":
                    secondary.extend((loss, interaction))
        failures = {}
        for control in ("random", "greedy", "neutral"):
            delta = np.array(values["evolved"]["mean_fitness"]) - values[control]["mean_fitness"]
            failures[control] = [{"seed": t["seed"], "fitness_difference": float(d)} for t, d in zip(trials, delta) if d <= 1e-10]
        analysis["environments"][env] = {"seed_values": values, "estimates": estimates, "comparisons": comparisons,
                                         "adaptation_from_founders": adaptation, "food_sensor_intervention": sensor,
                                         "nonpositive_fitness_seed_cases": failures}
    for metric in DIVERSITY_METRICS:
        values = {arm: [t["diversity"][arm][-1][metric] for t in trials] for arm in ARMS}
        row = effect(values["selection"], values["random_parent"], f"diversity:{metric}", True)
        secondary.append(row)
        analysis["diversity"][metric] = {"seed_values": values, "estimates": {a: mean_interval(v, f"diversity:{a}:{metric}") for a, v in values.items()},
                                          "selection_minus_neutral": row}
    for arm in ARMS:
        curves = {"mean_fitness": [], "steering_rms": [], "effective_founder_families": []}
        for generation in range(GENERATIONS):
            for key in curves:
                values = [(t["training"][arm]["generations"][generation][key] if key == "mean_fitness" else t["diversity"][arm][generation][key]) for t in trials]
                curves[key].append(mean_interval(values, f"curve:{arm}:{key}:{generation}"))
        analysis["training_curves"][arm] = curves
    classify_primary(primary)
    classify_primary(secondary)
    analysis["primary_test_count"] = len(primary)
    analysis["exploratory_test_count"] = len(secondary)
    # Environment changes are descriptive within-seed contrasts, not online learning.
    analysis["transfer_from_uniform"] = {}
    for env in ENVIRONMENTS:
        if env == "uniform":
            continue
        analysis["transfer_from_uniform"][env] = {c: effect(analysis["environments"][env]["seed_values"][c]["mean_fitness"],
            analysis["environments"]["uniform"]["seed_values"][c]["mean_fitness"], f"transfer:{env}:{c}") for c in BASELINES}
    analysis["limitations"] = ("Conditional on 16 reused training seed pairs and one fixed training budget, speed, mutation setting, "
        "and replenished-food model. This is fresh testing of existing lineages, not an independent replication of their training. "
        "Sign tests concern paired directions; bootstrap intervals estimate mean differences and are pointwise, not simultaneous. "
        "Fitness equals survival seconds + 10 meals, so endpoints are dependent. Genetic distance does not measure functional intelligence. "
        "Hidden food inputs are an intervention outside the original input distribution, not a proof of a particular algorithm. "
        "All cohorts eventually die by the lifespan limit; this evaluation does not test ecosystem persistence.")
    return analysis


def previous_initial_conditions():
    """Collect hashes from every earlier top-level result without altering files."""
    excluded = set()
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("initial_conditions", "initial_layout_sha256") and isinstance(item, str):
                    excluded.add(item)
                elif key in ("training_initial_conditions", "source_training_initial_conditions", "excluded_initial_conditions"):
                    def strings(x):
                        if isinstance(x, str):
                            excluded.add(x)
                        elif isinstance(x, dict):
                            for v in x.values(): strings(v)
                        elif isinstance(x, list):
                            for v in x: strings(v)
                    strings(item)
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value: visit(item)
    for path in sorted(Path("results").glob("step*.json")):
        if not path.name.startswith("step27-"):
            visit(json.loads(path.read_text()))
    return sorted(excluded)


def prepare_protocol(seeds, repeats, models_dir, source_report):
    source = json.loads(Path(source_report).read_text())
    if (source["status"] != "complete" or source["protocol"]["generations"] != GENERATIONS
            or source["protocol"]["training_configuration"] != TRAINING_CONFIG
            or not set(seeds) <= set(source["protocol"]["seeds"])):
        raise ValueError("Use complete declared Step 18 source populations.")
    models = {}
    for seed in seeds:
        path = Path(models_dir) / f"seed-{seed}.npz"
        training, starts, transitions, banks = load_models(path, seed, GENERATIONS)
        old = next(t for t in source["trials"] if t["seed"] == seed)
        hashes = {a: bank_digest(b) for a, b in banks.items()}
        if (training != old["training"] or starts != old["training_initial_conditions"]
                or transitions != old["transitions"] or hashes != old["genome_hashes"]):
            raise ValueError("Source models must agree with the published Step 18 records.")
        replay_diversity(seed, transitions, banks)
        models[str(seed)] = {"path": str(path), "sha256": file_digest(path), "genome_hashes": hashes}
    return {"seeds": seeds, "training_generations": GENERATIONS, "inherited_transitions": GENERATIONS - 1,
            "training_configuration": copy.deepcopy(TRAINING_CONFIG), "source_report": str(source_report),
            "source_report_sha256": file_digest(source_report), "source_models": models,
            "repeats_per_environment": repeats, "environments": copy.deepcopy(ENVIRONMENTS), "baselines": list(BASELINES),
            "conditions_by_environment": {e: list(conditions_for(e)) for e in ENVIRONMENTS},
            "excluded_initial_conditions": previous_initial_conditions(),
            "planned_new_training_cohorts": 0,
            "planned_test_cohorts": len(seeds) * repeats * sum(len(conditions_for(e)) for e in ENVIRONMENTS),
            "reuse": "Declared independent Step18 pairs (default all16); 10 scored generations, nine inherited transitions, entire frozen generation10 birth cohort. No test-selected champions, retraining, or outcome-based seed removal. This extends rather than independently replicates Step18 training.",
            "neutral": "20 uniformly random parents from all100 completed lifetimes, including early deaths, five children each; same mutation masks, Gaussian draws, slot shuffles, bodies, food, and training evaluations as fitness selection. No survival-dependent eligibility in this counterfactual baseline.",
            "physical_controls": "All100 actors, 60pixels/s, 5energy/s, capacity100, initialenergy100, food20, turn<=90degrees/s, sight160, identical body/lifespan/food starts. Random/greedy use frozen founder arrays only as unused placeholders; genetic diversity is not attributed to these policies.",
            "random": "Uniform turn rates[-90,90]degrees/s held for random .75–2s intervals; ignores food. Greedy uses the same random fallback when no food is detected, otherwise turns toward nearest detected pellet with the same turn limit and no overshoot.",
            "food": "Existing World immediate replenishment to standing stock, with deterministic seeded proposals and rejection around current actors. Starts and rules match; subsequent pellet placements may differ as paths/eating diverge. No hazards, seasons, physical-trait evolution, social interactions, or continuous reproduction in these tests.",
            "diagnostics": "Ancestral brains measure net adaptation on matched unseen layouts. Hidden conditions zero only the three food inputs in frozen evolved/neutral brains; never train/test-select with hidden inputs. Barren omits redundant hidden conditions because all truthful food signals are already zero.",
            "analysis_unit": "Independent training seed pair. Average repeats within seed/environment/condition before inference; never treat descendants, lifetimes, repeats, or environments as independent training replicates.",
            "primary_family": "45 two-sided exact paired sign tests: evolved-minus-random/greedy/neutral for fitness, meals, and 60-second survival in all five environments; Holm correction over all45. Sign ties abs<=1e-10.",
            "secondary_family": "21 exploratory two-sided sign tests with separate Holm correction: evolved/neutral-minus-founder fitness (10); evolved food-sensor fitness loss and evolved-minus-neutral sensor-loss interaction in four food environments (8); final full/steering genetic RMS and effective founder-family selection-minus-neutral differences (3). Other diagnostic endpoints and transfer effects descriptive.",
            "intervals": f"95% percentile bootstrap of independent seed means/pairs,20000 resamples, fixed namespace-derived seeds; approximate pointwise intervals, not simultaneous familywise intervals. {repeats} repeats average test-environment randomness; uncertainty conditional on original training sample.",
            "decision": "Higher/lower requires Holm p<.05 plus paired mean CI excluding zero in the same direction. Inconclusive is not equivalence. Sign test evaluates equal win/loss probability among non-ties, not mean equality; CIs estimate mean effect separately.",
            "adaptation": "Held-out evolved/neutral minus frozen original founder brains; genetic change during nine inherited transitions plus training trajectories. No within-test adaptation or new training in shifted environments.",
            "diversity": "All100 genomes each training generation reconstructed from recorded inheritance/mutation. Standardized RMS unordered-pair distance: full90 parameters and steering81 (exclude unused throttle column/bias). Weights scaled by1/sqrt8 and biases by.1, divide by sqrt(parametercount). Effective genealogical founder families=exp Shannon; distinct genomes by exact hash. Genetic distance is coordinate-dependent, not a functional/speciation measure.",
            "failure_reporting": "All nonpositive evolved-minus-control seed-mean fitness cases for each baseline/environment, plus complete starvation/zero-meal rates. All scheduled trials retained, including barren ties; no post-result tuning or early stopping."}


def run_study(seeds=DEFAULT_SEEDS, *, repeats=2, workers=1, models_dir=MODELS_DIR, source_report=SOURCE_REPORT,
              runs_dir=Path(".cache/evaluation-runs"), checkpoint=None, declare=None, progress=False):
    seeds = list(seeds)
    if (len(seeds) < 2 or any(type(s) is not int for s in seeds) or len(set(seeds)) != len(seeds)
            or type(repeats) is not int or repeats < 1 or type(workers) is not int or workers < 1):
        raise ValueError("Use distinct integer source seeds and positive repeats/workers.")
    if any(Path(runs_dir).glob("seed-*.json.gz")):
        raise ValueError("Use a new raw-record directory.")
    protocol = prepare_protocol(seeds, repeats, models_dir, source_report)
    report = {"format_version": 1, "status": "running", "protocol": protocol, "trials": []}
    if declare: declare(report)
    if checkpoint: checkpoint(report)
    def args(seed):
        model = protocol["source_models"][str(seed)]
        return (seed, model["path"], model["sha256"], repeats, runs_dir, protocol["excluded_initial_conditions"], progress)
    if workers == 1:
        for seed in seeds:
            report["trials"].append(run_lineage(*args(seed)))
            if checkpoint: checkpoint(report)
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(seeds))) as executor:
            for future in as_completed([executor.submit(run_lineage, *args(s)) for s in seeds]):
                report["trials"].append(future.result())
                if checkpoint: checkpoint(report)
    report["trials"].sort(key=lambda t: seeds.index(t["seed"]))
    report["analysis"] = analyze_results(report)
    report["status"] = "complete"
    if checkpoint: checkpoint(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=DEFAULT_SEEDS)
    parser.add_argument("--repeats", type=positive_integer, default=2)
    parser.add_argument("--workers", type=positive_integer, default=1)
    parser.add_argument("--models-dir", type=Path, default=MODELS_DIR)
    parser.add_argument("--source-report", type=Path, default=SOURCE_REPORT)
    parser.add_argument("--runs-dir", type=Path, default=Path(".cache/evaluation-runs"))
    parser.add_argument("--output", type=Path, default=Path(".cache/evaluation.json"))
    parser.add_argument("--protocol-output", type=Path, default=Path(".cache/evaluation-protocol.json"))
    args = parser.parse_args()
    if args.output.resolve() == args.protocol_output.resolve() or any(p.exists() or p.suffix != ".json" for p in (args.output, args.protocol_output)):
        parser.error("Use distinct new JSON output/protocol paths.")
    def write(report):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temp = args.output.with_suffix(".tmp.json")
        temp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        temp.replace(args.output)
    def declare(report):
        args.protocol_output.parent.mkdir(parents=True, exist_ok=True)
        args.protocol_output.write_text(json.dumps({"declared_at_utc": datetime.now(timezone.utc).isoformat(),
            "protocol": report["protocol"], "source_sha256": {p.name: file_digest(p) for p in sorted(Path(__file__).resolve().parent.glob("*.py"))}}, indent=2) + "\n")
    try:
        run_study(args.seeds, repeats=args.repeats, workers=args.workers, models_dir=args.models_dir,
                  source_report=args.source_report, runs_dir=args.runs_dir, checkpoint=write, declare=declare, progress=True)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"Comprehensive evaluation complete: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
