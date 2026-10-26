"""Frozen-network diagnostics and passive recordings extending Step 17."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from analyze_intelligence import bank_digest
from brain import SENSOR_NAMES
from compare_creatures import complete_generation, derived_seed, genome_digest, initial_conditions_digest, positive_integer
from experiment_speed import DEFAULT_SEEDS, FIXED_SPEED, load_model, paired_metrics
from experiment_strategy import file_digest, load_unselected
from experiment_specialization import excluded_layouts
from simulation import EvolutionSimulation
from world import SIMULATION_STEP, World


BANKS = ("evolved", "unselected")
ENVIRONMENTS = ("uniform", "clustered")
TRACE_IDS = (1, 34, 67)  # Fixed before outcomes, not test winners.
INTERVENTIONS = ("food_hidden", "bearing_mirrored", "hunger_midpoint", "walls_open")
BEARINGS = np.linspace(-0.9, 0.9, 37)
PROBE_INPUTS = np.array([[p, b, 1, h, 1, 1, 1, 1]
                         for b in BEARINGS for p in (0.25, 0.5, 0.75) for h in (0.25, 0.75)])
TRACE_COLUMNS = ("time", "x", "y", "heading", "energy", "food_eaten", "target_x", "target_y",
                 *SENSOR_NAMES, *[f"hidden_{i}" for i in range(8)], "turn", "throttle",
                 *[f"dturn_d_{s}" for s in SENSOR_NAMES], *[f"hidden_{i}_zero_effect" for i in range(8)])


def network_details(brain, inputs):
    """Exact feed-forward activations, input Jacobian, and finite neuron ablations.

    Jacobian is output per encoded input unit (not normalized importance).
    Neuron ablation sets its post-tanh activity to zero in this decision only.
    """
    x = np.asarray(inputs, dtype=np.float64)
    if x.ndim not in (1, 2) or x.shape[-1] != 8 or not np.all(np.isfinite(x)):
        raise ValueError("Use eight finite inputs per decision.")
    hidden = np.tanh(x @ brain.input_weights + brain.hidden_bias)
    logits = hidden @ brain.output_weights + brain.output_bias
    output = np.tanh(logits)
    jacobian = np.einsum("ij,...j,jk,...k->...ik", brain.input_weights,
                         1 - hidden ** 2, brain.output_weights, 1 - output ** 2)
    removed = np.tanh(logits[..., None, :] - hidden[..., :, None] * brain.output_weights)
    return hidden, output, jacobian, output[..., None, :] - removed


def decision_effects(brain, inputs):
    """Finite, simultaneous-state diagnostic clamps; no world is advanced."""
    x = np.atleast_2d(np.asarray(inputs, dtype=float))
    original = network_details(brain, x)[1]
    changed = []
    for name in INTERVENTIONS:
        values = x.copy()
        if name == "food_hidden":
            values[:, :3] = 0
        elif name == "bearing_mirrored":
            visible = values[:, 2] != 0
            values[visible, 1] = (-values[visible, 1] + 1) % 2 - 1
        elif name == "hunger_midpoint":
            values[:, 3] = 0.5
        else:
            values[:, 4:] = 1
        changed.append(original - network_details(brain, values)[1])
    return np.stack(changed, axis=-2)


def probe_bank(bank):
    records, curves = [], []
    for key, brain in sorted(bank.items()):
        hidden, output, jacobian, ablations = network_details(brain, PROBE_INPUTS)
        records.append({"creature_id": key,
            "mean_abs_input_jacobian": np.mean(np.abs(jacobian[:, :, 0]), axis=0).tolist(),
            "mean_abs_intervention_effect": np.mean(np.abs(decision_effects(brain, PROBE_INPUTS)[:, :, 0]), axis=0).tolist(),
            "mean_abs_hidden_zero_effect": np.mean(np.abs(ablations[:, :, 0]), axis=0).tolist(),
            "mean_abs_turn": float(np.mean(np.abs(output[:, 0]))),
            "hidden_saturation_fraction": float(np.mean(np.abs(hidden) > 0.95))})
        curves.append(output[:, 0].reshape(len(BEARINGS), 6).mean(axis=1).tolist())
    return {"brains": records, "turn_curves": curves}


class RecordingWorld(World):
    """Observe the existing controller calls; never replace a physics/control step."""
    def __init__(self, *args, recording=True, **kwargs):
        self.recording = recording
        self.traces = {key: [] for key in TRACE_IDS}
        self.meal_events = {key: [] for key in TRACE_IDS}
        self.samples = {}
        super().__init__(*args, **kwargs)
        self.initial_food = [[f.x, f.y] for f in self.food]

    def get_sensory_inputs(self, creature, food_positions=None):
        inputs = super().get_sensory_inputs(creature, food_positions)
        tick = round(self.elapsed_time / SIMULATION_STEP)
        detailed = creature.creature_id in self.traces and tick % 12 == 0
        sampled = tick % 60 == 0
        if not self.recording or not (detailed or sampled):
            return inputs
        brain = creature.brain
        hidden, output, jacobian, ablations = network_details(brain, inputs)
        if sampled:
            self.samples.setdefault(creature.creature_id, []).append(np.concatenate([
                np.abs(jacobian[:, 0]), np.abs(decision_effects(brain, inputs)[0, :, 0]),
                [abs(output[0]), float(np.min(inputs[4:]) < 0.2), float(inputs[2]),
                 float(bool(inputs[2]) and abs(inputs[1]) > 0.02),
                 float(bool(inputs[2]) and abs(inputs[1]) > 0.02 and output[0] * inputs[1] > 0)],
            ]))
        if detailed:
            observation = self.perceive_food(creature, food_positions)
            target = observation.target_position or (creature.x, creature.y)
            self.traces[creature.creature_id].append(np.concatenate([
                [self.elapsed_time, creature.x, creature.y, creature.heading, creature.energy,
                 creature.food_eaten, *target], inputs, hidden, output, jacobian[:, 0], ablations[:, 0]]))
        return inputs

    def _resolve_food_collisions(self):
        before = {c.creature_id: c.food_eaten for c in self.creatures if c.creature_id in self.meal_events}
        super()._resolve_food_collisions()
        if self.recording:
            for creature in self.creatures:
                if creature.creature_id in before and creature.food_eaten > before[creature.creature_id]:
                    self.meal_events[creature.creature_id].append([
                        self.elapsed_time + SIMULATION_STEP, creature.x, creature.y,
                        creature.food_eaten - before[creature.creature_id]])

    def observations(self):
        records = []
        for creature in sorted(self.dead_creatures, key=lambda c: c.creature_id):
            values = np.array(self.samples[creature.creature_id])
            mean = values.mean(axis=0)
            records.append({"creature_id": creature.creature_id, "samples": len(values),
                "mean_abs_input_jacobian": mean[:8].tolist(),
                "mean_abs_intervention_effect": mean[8:12].tolist(),
                "mean_abs_turn": float(mean[12]), "near_wall_fraction": float(mean[13]),
                "food_visible_fraction": float(mean[14]),
                "off_axis_visible_samples": int(values[:, 15].sum()),
                "turn_toward_food_samples": int(values[:, 16].sum()),
                "food_eaten": creature.food_eaten, "survival_seconds": creature.age,
                "death_cause": creature.death_cause, "final_position": [creature.x, creature.y]})
        return records


def save_trace(path, metadata, arrays):
    path = Path(path)
    if path.exists():
        raise ValueError("Preserve existing recordings; choose a new trace directory.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.npz")
    np.savez_compressed(temporary, metadata=np.array(json.dumps(metadata, allow_nan=False)), **arrays)
    temporary.replace(path)


def load_trace(path):
    with np.load(path, allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata"].item()))
        if metadata.get("trace_columns") != list(TRACE_COLUMNS) or metadata.get("trace_ids") != list(TRACE_IDS):
            raise ValueError("Incorrect trace format.")
        arrays = {key: archive[key].copy() for key in archive.files if key != "metadata"}
    for environment in ENVIRONMENTS:
        for bank in BANKS:
            for key in TRACE_IDS:
                frames = arrays[f"{environment}_{bank}_{key}"]
                if (frames.ndim != 2 or frames.shape[1] != len(TRACE_COLUMNS) or len(frames) < 1
                        or not np.all(np.isfinite(frames)) or frames[0, 0] != 0
                        or np.any(np.diff(frames[:, 0]) <= 0)):
                    raise ValueError("Invalid finite time-ordered decision recording.")
                if not np.all(np.isfinite(arrays[f"{environment}_{bank}_{key}_meals"])):
                    raise ValueError("Invalid meal events.")
    return metadata, arrays


def source_banks(seed, models_dir, unselected_dir):
    source = Path(models_dir) / f"seed-{seed}.npz"
    founder = Path(unselected_dir) / f"seed-{seed}.npz"
    training, starts, evolved = load_model(source, seed, 10)
    metadata, unselected = load_unselected(founder, seed)
    if metadata["initial_conditions"] != starts[0]:
        raise ValueError("Unselected founders must match the evolved lineage's original start.")
    return {"evolved": evolved, "unselected": unselected}, {
        "evolved": {"file": str(source), "file_sha256": file_digest(source), "genomes_sha256": bank_digest(evolved)},
        "unselected": {"file": str(founder), "file_sha256": file_digest(founder), "genomes_sha256": bank_digest(unselected)},
    }


def run_lineage(seed, models_dir, unselected_dir, trace_dir, forbidden, progress=False):
    banks, sources = source_banks(seed, models_dir, unselected_dir)
    probes = {name: probe_bank(bank) for name, bank in banks.items()}
    arrays, tests = {}, []
    for environment in ENVIRONMENTS:
        test_seed = derived_seed(f"step20:test:{seed}:{environment}")
        test = {"environment": environment, "seed": test_seed, "conditions": {}}
        for name, bank in banks.items():
            world = RecordingWorld(seed=test_seed, fixed_speed=FIXED_SPEED, evolution_enabled=False,
                                   food_distribution=environment)
            for creature in world.creatures:
                creature.brain = bank[creature.creature_id].copy()
            initial = initial_conditions_digest(world)
            if initial in forbidden:
                raise RuntimeError("Step 20 test layout was used previously.")
            arrays[f"{environment}_{name}_initial_food"] = np.array(world.initial_food)
            simulation = EvolutionSimulation(world, generation_limit=1, auto_advance=False)
            complete_generation(simulation)
            if genome_digest(world.dead_creatures) != sources[name]["genomes_sha256"]:
                raise RuntimeError("A passive recording changed a frozen genome.")
            test["conditions"][name] = {"initial_conditions": initial, "report": simulation.report(),
                                       "genomes_sha256": genome_digest(world.dead_creatures), "brains": world.observations()}
            for key in TRACE_IDS:
                arrays[f"{environment}_{name}_{key}"] = np.array(world.traces[key])
                arrays[f"{environment}_{name}_{key}_meals"] = np.array(world.meal_events[key]).reshape(-1, 4)
        tests.append(test)
        if progress:
            print(f"Seed {seed}: {environment}, both frozen 100-brain cohorts recorded", flush=True)
    if any(bank_digest(banks[name]) != sources[name]["genomes_sha256"] for name in BANKS):
        raise RuntimeError("Diagnostics changed a source brain.")
    path = Path(trace_dir) / f"seed-{seed}.npz"
    save_trace(path, {"seed": seed, "trace_columns": TRACE_COLUMNS, "trace_ids": TRACE_IDS,
                     "sources": sources, "decision_sample_seconds": 0.2}, arrays)
    return {"seed": seed, "sources": sources, "probes": probes, "tests": tests,
            "trace_file": str(path), "trace_sha256": file_digest(path)}


def mean_brains(records, metric):
    return np.mean([r[metric] for r in records], axis=0)


def descriptive_pair(left, right, label):
    data = paired_metrics(left, right, seed=derived_seed(f"step20:bootstrap:{label}"))
    data.pop("sign_test_p")
    return data  # Deliberately no confirmatory tests or significance decisions.


def analyze_results(report):
    protocol, trials = report["protocol"], report["trials"]
    seeds = protocol["seeds"]
    if (len(seeds) < 2 or len(set(seeds)) != len(seeds) or len(trials) != len(seeds)
            or {t["seed"] for t in trials} != set(seeds) or protocol["environments"] != list(ENVIRONMENTS)
            or protocol["banks"] != list(BANKS) or protocol["trace_ids"] != list(TRACE_IDS)
            or protocol["training_cohorts"] != 0):
        raise ValueError("A complete declared study with distinct independent seed groups is required.")
    trials = sorted(trials, key=lambda t: seeds.index(t["seed"]))
    seen = set(protocol["excluded_initial_conditions"])
    for trial in trials:
        if trial["sources"] != protocol["source_models"][str(trial["seed"])]:
            raise ValueError("Source models differ from the declaration.")
        if len(trial["tests"]) != 2 or {t["environment"] for t in trial["tests"]} != set(ENVIRONMENTS):
            raise ValueError("Every environment must be recorded exactly once.")
        for name in BANKS:
            probe = trial["probes"][name]
            if (len(probe["brains"]) != 100 or [r["creature_id"] for r in probe["brains"]] != list(range(1, 101))
                    or np.asarray(probe["turn_curves"]).shape != (100, len(BEARINGS))):
                raise ValueError("Diagnostic probes require every original cohort brain.")
            if not np.all(np.isfinite(probe['turn_curves'])) or np.any(np.abs(probe['turn_curves']) > 1):
                raise ValueError("Turn curves must be finite bounded commands.")
            for row in probe["brains"]:
                for metric, width in (("mean_abs_input_jacobian", 8), ("mean_abs_intervention_effect", 4),
                                      ("mean_abs_hidden_zero_effect", 8)):
                    a = np.asarray(row[metric])
                    if a.shape != (width,) or not np.all(np.isfinite(a)) or np.any(a < 0):
                        raise ValueError("Invalid neural diagnostic.")
        for test in trial["tests"]:
            if set(test["conditions"]) != set(BANKS) or test["seed"] != derived_seed(f"step20:test:{trial['seed']}:{test['environment']}"):
                raise ValueError("Incorrect test namespace or missing baseline.")
            starts = {r["initial_conditions"] for r in test["conditions"].values()}
            if len(starts) != 1 or starts.intersection(seen):
                raise ValueError("Test bodies/food must be matched, unseen, and distinct.")
            seen.update(starts)
            for name, record in test["conditions"].items():
                data, rows = record["report"], record["brains"]
                if (data["completed_generations"] != 1 or len(data["generations"]) != 1
                        or data["controller"] != "neural" or data["evolution_enabled"]
                        or data["food_sensor_mode"] != "intact" or data["fixed_speed"] != FIXED_SPEED
                        or data["population_size"] != 100 or data["food_count"] != 150
                        or data["arena_size"] != [1000, 600] or data["food_distribution"] != test["environment"]
                        or data["seed"] != test["seed"] or [r["creature_id"] for r in rows] != list(range(1, 101))):
                    raise ValueError("Recording must preserve the fixed-speed complete-cohort protocol.")
                if record['genomes_sha256'] != trial['sources'][name]['genomes_sha256']:
                    raise ValueError("Recorded genomes differ from their frozen sources.")
                for row in rows:
                    if (type(row['samples']) is not int or row['samples'] < 1
                            or not 0 <= row['turn_toward_food_samples'] <= row['off_axis_visible_samples'] <= row['samples']):
                        raise ValueError("Invalid observation denominators.")
                    for metric, width in (("mean_abs_input_jacobian", 8), ("mean_abs_intervention_effect", 4)):
                        values = np.asarray(row[metric])
                        if values.shape != (width,) or not np.all(np.isfinite(values)) or np.any(values < 0):
                            raise ValueError("Invalid observed-state input effects.")
                stats = data["generations"][0]
                if (not np.isclose(stats["mean_speed"], FIXED_SPEED)
                        or not np.isclose(np.mean([r["food_eaten"] for r in rows]), stats["mean_food_eaten"])
                        or not np.isclose(np.mean([r["survival_seconds"] for r in rows]), stats["mean_survival_seconds"])):
                    raise ValueError("Individual records do not reproduce the full-cohort observations.")
    analysis = {"independent_seed_groups": len(seeds), "common_probes": {}, "environments": {}}
    for metric in ("mean_abs_input_jacobian", "mean_abs_intervention_effect", "mean_abs_turn", "hidden_saturation_fraction"):
        values = {name: np.array([mean_brains(t["probes"][name]["brains"], metric) for t in trials]) for name in BANKS}
        analysis["common_probes"][metric] = {name: a.mean(axis=0).tolist() for name, a in values.items()}
        if values['evolved'].ndim == 1:
            paired = descriptive_pair(values['evolved'], values['unselected'], metric)
        else:
            paired = [descriptive_pair(values['evolved'][:, i], values['unselected'][:, i], f'{metric}:{i}')
                      for i in range(values['evolved'].shape[1])]
        analysis['common_probes'][metric]['evolved_minus_unselected'] = paired
    analysis["common_probes"]["turn_curves"] = {name: np.mean([np.mean(t["probes"][name]["turn_curves"], axis=0) for t in trials], axis=0).tolist() for name in BANKS}
    for environment in ENVIRONMENTS:
        records = {name: [next(test for test in t["tests"] if test["environment"] == environment)["conditions"][name] for t in trials] for name in BANKS}
        results = {}
        for metric in ("mean_fitness", "mean_food_eaten", "survival_rate"):
            values = {name: [r["report"]["generations"][0][metric] for r in records[name]] for name in BANKS}
            results[metric] = descriptive_pair(values["evolved"], values["unselected"], f"{environment}:{metric}")
        for metric in ("mean_abs_input_jacobian", "mean_abs_intervention_effect", "mean_abs_turn", "near_wall_fraction", "food_visible_fraction"):
            results[metric] = {name: np.mean([mean_brains(r["brains"], metric) for r in records[name]], axis=0).tolist() for name in BANKS}
        # Equal weight per lineage; within-lineage ratio pools only eligible observed states.
        results["turn_toward_food_fraction"] = {}
        for name in BANKS:
            numerators = [sum(b["turn_toward_food_samples"] for b in r["brains"]) for r in records[name]]
            denominators = [sum(b["off_axis_visible_samples"] for b in r["brains"]) for r in records[name]]
            results["turn_toward_food_fraction"][name] = {"seed_values": [n / d if d else None for n, d in zip(numerators, denominators)], "eligible_sample_counts": denominators}
        analysis["environments"][environment] = results
    return analysis


def prior_layouts():
    forbidden = set(excluded_layouts())
    path = Path(__file__).resolve().parent / "results/step19-specialization.json"
    if path.exists():
        previous = json.loads(path.read_text())
        for trial in previous["trials"]:
            forbidden.update(e["initial_conditions"] for rows in trial["training"].values() for e in rows)
            forbidden.update(r["initial_conditions"] for test in trial["tests"] for r in test["conditions"].values())
    return sorted(forbidden)


def run_study(seeds=DEFAULT_SEEDS, *, models_dir="results/step16-models", unselected_dir="results/step17-unselected-models",
              trace_dir=".cache/brain-traces", workers=1, progress=False, checkpoint=None, declare=None):
    seeds = list(seeds)
    if len(seeds) < 2 or len(set(seeds)) != len(seeds) or any(type(s) is not int for s in seeds) or type(workers) is not int or workers < 1:
        raise ValueError("Use at least two distinct integer seeds and positive workers.")
    if any((Path(trace_dir) / f"seed-{s}.npz").exists() for s in seeds):
        raise ValueError("Preserve existing recordings; choose a new trace directory.")
    sources = {str(seed): source_banks(seed, models_dir, unselected_dir)[1] for seed in seeds}
    previous = json.loads((Path(__file__).resolve().parent / 'results/step17-strategy.json').read_text())
    published = {t['seed']: t for t in previous['trials']}
    for seed in seeds:
        if (sources[str(seed)]['evolved']['file_sha256'] != published[seed]['source_model_sha256']
                or any(sources[str(seed)][b]['genomes_sha256'] != published[seed]['genome_hashes'][b] for b in BANKS)):
            raise ValueError("Sources must match the published Step 17 evolved and unselected banks.")
    report = {"format_version": 1, "status": "running", "protocol": {
        "seeds": seeds, "environments": list(ENVIRONMENTS), "banks": list(BANKS), "source_models": sources,
        "training_cohorts": 0, "planned_test_cohorts": len(seeds) * 4,
        "source_generations": 10, "fixed_speed": FIXED_SPEED, "trace_ids": list(TRACE_IDS),
        "focus_seed": seeds[0], "focus_creature_id": 1,
        "excluded_initial_conditions": prior_layouts(), "test_seed_namespace": "step20:test",
        "common_probe_inputs": PROBE_INPUTS.tolist(), "bearing_grid": BEARINGS.tolist(),
        "trace_columns": list(TRACE_COLUMNS), "trace_sample_seconds": 0.2, "all_brain_sample_seconds": 1.0,
        "interventions": list(INTERVENTIONS), "sensors": list(SENSOR_NAMES),
        "analysis_unit": "independent source training seed; all 100 brains averaged within seed",
        "inference": "Exploratory descriptive analyses only; 20000 paired bootstrap resamples and pointwise 95% intervals, no confirmatory tests.",
        "limitations": "Local derivatives and single-decision clamps do not estimate fitness effects. Some clamps leave naturally observed input support. Observed states differ between policies. Hidden unit identities are network-specific; activation is not semantic understanding. Fixed speed ignores throttle. Nearest-food targets may switch; trajectories and initial food are illustrative, not planning evidence.",
    }, "trials": []}
    if declare:
        declare(report)
    if checkpoint:
        checkpoint(report)
    args = [(s, models_dir, unselected_dir, trace_dir, report["protocol"]["excluded_initial_conditions"], progress) for s in seeds]
    if workers == 1:
        for arg in args:
            report["trials"].append(run_lineage(*arg))
            if checkpoint:
                checkpoint(report)
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(seeds))) as executor:
            futures = [executor.submit(run_lineage, *arg) for arg in args]
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
    parser.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    parser.add_argument("--workers", type=positive_integer, default=1)
    parser.add_argument("--models-dir", type=Path, default=Path("results/step16-models"))
    parser.add_argument("--unselected-dir", type=Path, default=Path("results/step17-unselected-models"))
    parser.add_argument("--trace-dir", type=Path, default=Path(".cache/brain-traces"))
    parser.add_argument("--output", type=Path, default=Path(".cache/brain-analysis.json"))
    parser.add_argument("--protocol-output", type=Path, default=Path(".cache/brain-protocol.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    destinations = [args.output.resolve(), args.protocol_output.resolve()]
    tracked = set(p.resolve() for p in (root / 'results').rglob('*') if p.is_file())
    if (len(set(destinations)) != 2 or any(p in tracked or p.suffix != '.json' for p in destinations)
            or any(p == root / name for p in destinations for name in ('README.md', 'brain.py'))):
        parser.error("Use distinct new JSON output paths; preserve previous results.")
    def write(report):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix('.tmp.json')
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
        temporary.replace(args.output)
    def declare(report):
        args.protocol_output.parent.mkdir(parents=True, exist_ok=True)
        args.protocol_output.write_text(json.dumps({"declared_at_utc": datetime.now(timezone.utc).isoformat(),
            "protocol": report['protocol'], "source_sha256": {p.name: file_digest(p) for p in [*sorted(root.glob('*.py')), root / 'brain_viewer.html']}}, indent=2) + '\n')
    try:
        run_study(args.seeds, models_dir=args.models_dir, unselected_dir=args.unselected_dir,
                  trace_dir=args.trace_dir, workers=args.workers, progress=True, checkpoint=write, declare=declare)
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    print(f"Complete frozen-brain analysis saved: {args.output}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
