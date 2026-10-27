"""Validated configurations, passive observation, and reproducible run bundles."""

from collections import Counter
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timezone
import copy
import csv
import hashlib
import html
import json
import math
import os
from pathlib import Path
import platform
import shutil
import tempfile
import uuid

import numpy as np

from evaluation_world import EvaluationWorld
from experiment_selection import ParentPolicyWorld
from simulation import EvolutionSimulation
from world import SIMULATION_STEP, World


VERSION = "1.0.1"
ROOT = Path(__file__).resolve().parent
MODES = ("foraging", "seasons", "obstacles", "traits", "predator_prey", "social", "continuous")
ENVIRONMENTS = {
    "uniform": (1000, 600, "uniform", 150), "clustered": (1000, 600, "clustered", 150),
    "sparse": (1000, 600, "uniform", 50), "wide_clustered": (1200, 500, "clustered", 150),
    "barren": (1000, 600, "uniform", 0), "seasonal": (1000, 600, "clustered", 150),
}
ALGORITHMS = {
    "foraging": ("selection", "neutral", "random", "greedy", "founder"),
    "seasons": ("selection",), "obstacles": ("selection", "random", "greedy"),
    "traits": ("selection",), "predator_prey": ("coevolution",),
    "social": ("group", "individual"), "continuous": ("funded", "clonal"),
}
MODE_NAMES = {"foraging": "Food seeking", "seasons": "Changing seasons", "obstacles": "Obstacles & hazards",
              "traits": "Brains & bodies", "predator_prey": "Predator & prey", "social": "Social behavior",
              "continuous": "Continuous ecosystem"}
FITNESS_LABELS = {"social": "Mean survival age", "predator_prey": "Prey mean fitness"}


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parameter_hash(parameters):
    digest = hashlib.sha256()
    for value in parameters:
        digest.update(value.astype("<f8").tobytes())
    return digest.hexdigest()


@dataclass(frozen=True)
class RunConfig:
    schema_version: int = 1
    mode: str = "foraging"
    environment: str = "uniform"
    algorithm: str = "selection"
    seed: int = 2801
    population: int = 100
    food_count: int | None = None
    mutation_rate: float = .1
    mutation_scale: float = .1
    generations: int = 5
    duration: float = 600.
    fixed_speed: float = 60.
    body_mutation_rate: float = .25
    body_mutation_scale: float = .08
    population_cap: int = 300
    regrowth_rate: float = 30.
    maturity_age: float = 15.
    birth_cooldown: float = 20.
    season_length: int = 1
    season_food: tuple = (150, 200, 75, 25)
    cluster_shift: float = 120.
    reproductive_age: float = 60.
    predators: int = 20
    episode_seconds: float = 60.
    groups: int = 10
    food_access: str = "restricted"
    signaling: bool = True
    sharing: bool = True
    signals_hidden: bool = False
    risk_sensors: str = "intact"
    prey_sensors: str = "intact"
    predator_sensors: str = "intact"
    sample_interval: float = 1.

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) - {f.name for f in fields(cls)}:
            raise ValueError("Use a versioned simulator configuration with known fields.")
        data = dict(data)
        if "season_food" in data:
            data["season_food"] = tuple(data["season_food"])
        config = cls(**data)
        config.validate()
        return config

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text()))

    def to_dict(self):
        return json.loads(json.dumps(asdict(self), allow_nan=False))

    @property
    def habitat(self):
        width, height, distribution, food = ENVIRONMENTS[self.environment]
        return width, height, distribution, food if self.food_count is None else self.food_count

    def validate(self):
        if type(self.schema_version) is not int or self.schema_version != 1 or self.mode not in MODES or self.algorithm not in ALGORITHMS[self.mode]:
            raise ValueError("Choose a supported mode and its corresponding algorithm.")
        allowed = ("seasonal",) if self.mode == "seasons" else tuple(e for e in ENVIRONMENTS if e != "seasonal")
        if self.environment not in allowed or (self.mode == "social" and self.environment in ("clustered", "wide_clustered")):
            raise ValueError("This environment is not supported by the selected mode.")
        if self.mode == "seasons" and self.food_count is not None:
            raise ValueError("Seasonal stock is controlled by season_food; leave food_count empty.")
        if type(self.seed) is not int or not 0 <= self.seed < 2 ** 63:
            raise ValueError("Seed must be an integer from 0 to 2^63−1.")
        for name in ("population", "generations", "population_cap", "season_length", "predators", "groups"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer.")
        if self.population > 300 or self.population_cap > 1000:
            raise ValueError("The interactive application supports at most 300 founders and a cap of 1000.")
        if self.food_count is not None and (type(self.food_count) is not int or not 0 <= self.food_count <= 500):
            raise ValueError("Food stock must be an integer from 0 to 500.")
        for name in ("mutation_rate", "body_mutation_rate"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be a finite probability.")
        for name in ("mutation_scale", "body_mutation_scale", "regrowth_rate", "cluster_shift"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative.")
        for name in ("duration", "fixed_speed", "maturity_age", "birth_cooldown", "reproductive_age", "episode_seconds", "sample_interval"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive.")
        for name in ("duration", "episode_seconds", "sample_interval"):
            if not math.isclose(getattr(self, name) * 60, round(getattr(self, name) * 60), rel_tol=0, abs_tol=1e-8):
                raise ValueError(f"{name} must be a whole number of fixed ticks.")
        if self.population_cap < self.population or (self.mode == "predator_prey" and self.predators >= self.population):
            raise ValueError("Population cap must include founders; predator count must leave at least one prey.")
        if self.food_access not in ("restricted", "open") or self.risk_sensors not in ("intact", "hidden"):
            raise ValueError("Invalid access or risk-sensor setting.")
        if self.prey_sensors not in ("intact", "hidden") or self.predator_sensors not in ("intact", "hidden"):
            raise ValueError("Invalid opponent-sensor setting.")
        if any(type(getattr(self, k)) is not bool for k in ("signaling", "sharing", "signals_hidden")):
            raise ValueError("Social switches must be boolean.")
        if (len(self.season_food) != 4 or any(type(n) is not int or not 0 <= n <= 500 for n in self.season_food)):
            raise ValueError("Provide four seasonal food counts from 0 to 500.")
        if self.mode == "social" and (self.groups < 2 or self.population % self.groups or self.population // self.groups < 2
                                      or self.habitat[3] % self.groups):
            raise ValueError("Social mode needs equal groups of at least two, with food divisible by groups.")
        return self


class ForagingWorld(ParentPolicyWorld, EvaluationWorld):
    """The verified Step 27 broad phase with the existing parent-choice policy."""


class FounderWorld(EvaluationWorld):
    """Replay original neural controllers in each new cohort, without selection."""
    def regenerate_population(self, seed=None):
        super().regenerate_population(seed)
        self.founders = {c.creature_id: c.brain.copy() for c in self.creatures}

    def advance_generation(self):
        if self.final_evaluation is None:
            return False
        self._start_generation(self.generation + 1)
        for c in self.creatures:
            c.brain = self.founders[c.creature_id].copy()
            c.parent_id = c.creature_id
        return True


def create_world(config):
    config.validate()
    width, height, distribution, food = config.habitat
    common = dict(seed=config.seed, population_size=config.population, food_count=food,
                  food_distribution=distribution, mutation_rate=config.mutation_rate, mutation_scale=config.mutation_scale)
    fixed = dict(fixed_speed=float(config.fixed_speed))
    body = dict(body_mutation_rate=config.body_mutation_rate, body_mutation_scale=config.body_mutation_scale)
    if config.mode == "foraging":
        if config.algorithm in ("selection", "neutral"):
            return ForagingWorld(width, height, **common, **fixed,
                                     parent_policy="selection" if config.algorithm == "selection" else "random_parent")
        kind = FounderWorld if config.algorithm == "founder" else EvaluationWorld
        return kind(width, height, **common, **fixed, evolution_enabled=False,
                    controller=config.algorithm if config.algorithm in ("random", "greedy") else "neural")
    if config.mode == "seasons":
        from seasons import SeasonalWorld
        return SeasonalWorld(width, height, **common, **fixed, season_length=config.season_length,
                             season_food=config.season_food, cluster_shift=config.cluster_shift, reproductive_age=config.reproductive_age)
    if config.mode == "obstacles":
        from obstacles import ObstacleWorld
        return ObstacleWorld(width, height, **common, **fixed, risk_sensor_mode=config.risk_sensors,
                             evolution_enabled=config.algorithm == "selection",
                             controller="neural" if config.algorithm == "selection" else config.algorithm)
    if config.mode == "traits":
        from body_traits import TraitWorld
        return TraitWorld(width, height, **common, **body)
    if config.mode == "predator_prey":
        from predator_prey import PredatorPreyWorld
        return PredatorPreyWorld(width, height, **common, **body, predators=config.predators,
                                 episode_seconds=config.episode_seconds, prey_sensors=config.prey_sensors, predator_sensors=config.predator_sensors)
    if config.mode == "social":
        from social import SocialWorld
        return SocialWorld(width, height, **common, groups=config.groups, selection_level=config.algorithm,
                           access=config.food_access, signaling=config.signaling, sharing=config.sharing,
                           signals_hidden=config.signals_hidden, episode_seconds=config.episode_seconds)
    from ecosystem import ContinuousWorld
    if config.algorithm == "clonal":
        common["mutation_rate"] = 0.
        body["body_mutation_rate"] = 0.
    return ContinuousWorld(width, height, **common, **body, population_cap=config.population_cap,
                           regrowth_rate=config.regrowth_rate, maturity_age=config.maturity_age,
                           birth_cooldown=config.birth_cooldown, sample_interval=config.sample_interval)


class ResearchSession:
    """Observe every birth before its first tick; never touch model RNG streams."""
    def __init__(self, config):
        if config.mode == "continuous" and config.algorithm == "clonal":
            config = replace(config, mutation_rate=0., body_mutation_rate=0.)
        if config.mode == "social":
            config = replace(config, body_mutation_rate=0., body_mutation_scale=0.)
        self.config = config.validate()
        self.world = create_world(config)
        if config.mode == "continuous":
            from ecosystem import ContinuousSimulation
            self.simulation = ContinuousSimulation(self.world, duration=config.duration)
        else:
            self.simulation = EvolutionSimulation(self.world, generation_limit=config.generations, auto_advance=False)
        self.run_id = uuid.uuid4().hex[:12]
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.ticks = 0
        self.speed = 1
        self.paused = False
        self.automatic = True
        self.accumulator = 0.
        self.events = []
        self.births, self.actors, self.genomes, self.ends = {}, {}, {}, {}
        self.samples = []
        self._observe_births()
        self.sample()

    @property
    def elapsed(self):
        return self.ticks * SIMULATION_STEP

    @property
    def finished(self):
        return self.simulation.finished

    def key(self, c):
        return f"c{c.creature_id}" if self.config.mode == "continuous" else f"g{c.generation}:c{c.creature_id}"

    def _observe_births(self):
        world = self.world
        members = list(world.registry.values()) if self.config.mode == "continuous" else [*world.creatures, *world.dead_creatures]
        for c in members:
            key = self.key(c)
            if key in self.births:
                continue
            parent = None if c.parent_id is None else (f"c{c.parent_id}" if self.config.mode == "continuous" else f"g{c.generation - 1}:c{c.parent_id}")
            if parent is not None and parent not in self.births:
                raise RuntimeError("An observed child has no earlier parent record.")
            founder = self.births[parent]["founder"] if parent else key
            born = c.born_at if self.config.mode == "continuous" else self.elapsed
            body = c.body.vector().tolist() if hasattr(c, "body") else None
            self.births[key] = dict(key=key, creature_id=c.creature_id, generation=c.generation,
                                    parent=parent, founder=founder, born_at=born,
                                    depth=self.births[parent]["depth"] + 1 if parent else 0,
                                    initial_energy=c.energy, lifespan=c.lifespan, body=body,
                                    neural_sha256=parameter_hash(c.brain.parameters),
                                    species=getattr(c, "species", None), group=getattr(c, "group_id", None))
            self.actors[key] = c
            self.genomes[key] = tuple(p.copy() for p in c.brain.parameters)

    def _end_cohort(self):
        if self.config.mode != "continuous" and self.world.final_evaluation is not None:
            for c in [*self.world.creatures, *self.world.dead_creatures]:
                self.ends.setdefault(self.key(c), self.elapsed)

    def set_control(self, action, value):
        if action == "paused" and type(value) is bool:
            self.paused = value
        elif action == "speed" and type(value) is int and value in (1, 5, 20):
            self.speed = value
            self.accumulator = 0.
        elif action == "automatic" and type(value) is bool:
            self.automatic = value
            if self.config.mode == "continuous":
                self.world.set_reproduction(value)
        else:
            raise ValueError("Invalid simulator control.")
        self.events.append({"tick": self.ticks, "action": action, "value": value})

    def advance(self, record=True):
        if self.config.mode == "continuous" or self.finished or self.world.final_evaluation is None:
            return False
        self._end_cohort()
        if not self.simulation.advance_generation():
            return False
        self._observe_births()
        if record:
            self.events.append({"tick": self.ticks, "action": "advance", "value": True})
        return True

    def step(self):
        if self.finished:
            return False
        if self.config.mode != "continuous" and self.world.final_evaluation is not None:
            if not self.automatic or not self.advance(record=False):
                return False
        self.simulation.update(SIMULATION_STEP)
        self.ticks += 1
        self._observe_births()
        self._end_cohort()
        interval = round(self.config.sample_interval / SIMULATION_STEP)
        if self.ticks % interval == 0 or self.finished:
            self.sample()
        return True

    def update(self, dt, max_ticks=None):
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("Elapsed time must be finite and nonnegative.")
        if max_ticks is not None and (type(max_ticks) is not int or max_ticks < 1):
            raise ValueError("A UI tick budget must be a positive integer.")
        if self.paused or self.finished:
            return
        self.accumulator += min(dt, .25) * self.speed
        count = 0
        while self.accumulator + 1e-12 >= SIMULATION_STEP:
            if max_ticks is not None and count >= max_ticks:
                break
            if not self.step():
                self.accumulator = 0.
                break
            self.accumulator = max(0., self.accumulator - SIMULATION_STEP)
            count += 1

    def metrics(self):
        w = self.world
        members = list(w.registry.values()) if self.config.mode == "continuous" else [*w.creatures, *w.dead_creatures]
        scored = [c for c in members if getattr(c, "species", "prey") == "prey"]
        fitness = [c.age if self.config.mode == "social" else c.fitness for c in scored]
        live = w.creatures
        counts = Counter(self.births[self.key(c)]["founder"] for c in live)
        probabilities = np.array(list(counts.values()), dtype=float) / len(live) if live else np.array([])
        rms = None
        if len(live) > 1 and self.config.algorithm not in ("random", "greedy"):
            x = np.stack([np.concatenate([p.ravel() for p in c.brain.parameters]) for c in live])
            rms = float(np.sqrt(2 * len(x) / (len(x) - 1) * np.var(x, axis=0).mean()))
        return dict(time=self.elapsed, generation=w.generation, population=len(live),
                    mean_fitness=float(np.mean(fitness)) if fitness else 0., best_fitness=max(fitness, default=0.),
                    living_mean_fitness=float(np.mean([c.age if self.config.mode == "social" else c.fitness for c in live
                                                      if getattr(c, "species", "prey") == "prey"])) if any(getattr(c, "species", "prey") == "prey" for c in live) else 0.,
                    mean_meals=float(np.mean([c.food_eaten for c in scored])) if scored else 0.,
                    food=len(w.food), births=len(self.births), deaths=sum(not c.alive for c in self.actors.values()),
                    families=len(counts), effective_families=float(np.exp(-np.sum(probabilities * np.log(probabilities)))) if len(probabilities) else 0.,
                    neural_rms=rms, predators=sum(getattr(c, "species", None) == "predator" for c in live),
                    prey=sum(getattr(c, "species", None) == "prey" for c in live),
                    predator_mean_fitness=float(np.mean([c.fitness for c in members if getattr(c, "species", None) == "predator"])) if self.config.mode == "predator_prey" else None)

    def sample(self):
        if self.samples and self.samples[-1]["time"] == self.elapsed:
            return
        self.samples.append(self.metrics())

    def snapshot(self):
        people = []
        for key, c in self.actors.items():
            people.append({**self.births[key], "age": c.age, "energy": c.energy, "food_eaten": c.food_eaten,
                           "fitness": c.age if self.config.mode == "social" else c.fitness,
                           "alive": c.alive, "death_cause": c.death_cause,
                           "cohort_ended_at": self.ends.get(key), "censored": key in self.ends and c.alive,
                           "x": c.x, "y": c.y, "heading": c.heading,
                           "captures": getattr(c, "captures", None), "children": getattr(c, "children", None)})
        samples = copy.deepcopy(self.samples)
        if samples[-1]["time"] != self.elapsed:
            samples.append(self.metrics())
        # ContinuousSimulation.report adds an endpoint sample. Keep observation
        # pure so exporting mid-run does not alter a later tick replay.
        previous_samples = len(self.world.snapshots) if self.config.mode == "continuous" else None
        simulation_report = self.simulation.report()
        if previous_samples is not None:
            del self.world.snapshots[previous_samples:]
        telemetry_names = ("basal_energy", "movement_energy", "sensing_energy", "assimilated_energy", "wasted_food_energy",
                           "collisions", "hazard_seconds", "collision_energy_lost", "hazard_energy_lost",
                           "captures", "capture_assimilated_energy", "wasted_capture_energy", "opponent_visible_seconds", "away_seconds", "toward_seconds",
                           "can_feed", "shared_in", "shared_out", "signal", "signal_energy", "share_effort",
                           "signal_integral", "received_signal_integral", "share_request_integral", "reproduction_energy", "children")
        telemetry = [{"key": key, "right_censored": c.alive,
                      **{name: getattr(c, name, None) for name in telemetry_names}} for key, c in self.actors.items()]
        return {"schema_version": 1, "app_version": VERSION, "run_id": self.run_id, "created_at": self.created_at,
                "config": self.config.to_dict(), "execution": {"ticks": self.ticks, "finished": self.finished,
                    "controls": copy.deepcopy(self.events), "automatic": self.automatic, "paused": self.paused, "speed": self.speed},
                "metrics": self.metrics(), "samples": samples, "individuals": people,
                "telemetry": telemetry,
                "simulation": simulation_report,
                "runtime": {"python": platform.python_version(), "numpy": np.__version__},
                "sources_sha256": {p.name: file_hash(p) for p in sorted(ROOT.glob("*.py"))},
                "notes": ["Live curves are descriptive, not independent scientific replications.",
                    "Generational scores reset each cohort; continuous scores average all recorded lifetimes.",
                    "Predator/prey scores remain separate; social fitness is survival age.",
                    "Founder labels are genealogy, not species. Random/greedy placeholder weights have no diversity score.",
                    "Genomes are birth parameters; configuration plus tick/control replay reproduces this run, not an arbitrary resume checkpoint."]}, {k: tuple(p.copy() for p in v) for k, v in self.genomes.items()}


def replay_run(report):
    """Replay physics ticks and semantic controls, independent of wall-clock/UI."""
    session = ResearchSession(RunConfig.from_dict(report["config"]))
    execution = report["execution"]
    events = execution["controls"]
    index = 0
    for tick in range(execution["ticks"] + 1):
        while index < len(events) and events[index]["tick"] == tick:
            event = events[index]
            if event["action"] == "advance":
                if not session.advance():
                    raise ValueError("A recorded manual transition could not be replayed.")
            else:
                session.set_control(event["action"], event["value"])
            index += 1
        if tick < execution["ticks"] and not session.step():
            raise ValueError("Replay ended before the recorded tick horizon.")
    if index != len(events):
        raise ValueError("Control events extend beyond the replay horizon.")
    snapshot, bank = session.snapshot()
    for key in ("samples", "individuals", "simulation", "metrics"):
        if snapshot[key] != report[key]:
            raise ValueError(f"Replay mismatch in {key}.")
    if "telemetry" in report and snapshot["telemetry"] != report["telemetry"]:
        raise ValueError("Replay mismatch in mode-specific telemetry.")
    return session


def verify_bundle(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text())
    required = {"config.json", "run.json", "population.csv", "individuals.csv", "lineage.csv", "generations.csv",
                "genomes.npz", "population.png", "population.svg", "population.pdf", "report.html"}
    if manifest.get("schema_version") != 1 or not required <= set(manifest.get("files_sha256", {})):
        raise ValueError("Incomplete run-bundle manifest.")
    for name, expected in manifest["files_sha256"].items():
        path = directory / name
        if Path(name).name != name or path.is_symlink() or not path.is_file() or file_hash(path) != expected:
            raise ValueError(f"Bundle file is missing, unsafe, or changed: {name}")
    report = json.loads((directory / "run.json").read_text())
    if report["config"] != json.loads((directory / "config.json").read_text()) or report["run_id"] != manifest["run_id"]:
        raise ValueError("Run identity or configuration differs from its manifest.")
    with np.load(directory / "genomes.npz", allow_pickle=False) as archive:
        keys = archive["keys"].tolist()
        if keys != [p["key"] for p in report["individuals"]]:
            raise ValueError("Genomes do not cover the complete birth ledger.")
        arrays = [archive[f"parameter_{i}"] for i in range(4)]
        if any(len(a) != len(keys) or not np.all(np.isfinite(a)) for a in arrays):
            raise ValueError("Invalid numeric genome arrays.")
        for i, person in enumerate(report["individuals"]):
            if parameter_hash([a[i] for a in arrays]) != person["neural_sha256"]:
                raise ValueError("A numeric genome differs from its birth record.")
            if archive["bodies"][i].tolist() != (person["body"] or [0., 0., 0.]):
                raise ValueError("Body traits differ from the birth record.")
    return report


def write_csv(path, rows):
    if not rows:
        path.write_text("")
        return
    keys = list(rows[0])
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def build_run_figure(report):
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    figure = Figure(figsize=(13, 9), facecolor="#f5f8fa")
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 2)
    figure.subplots_adjust(left=.09, right=.96, top=.83, bottom=.15, hspace=.4, wspace=.3)
    c = report["config"]
    figure.suptitle(f"Artificial Evolution / {MODE_NAMES[c['mode']]}", fontsize=22, fontweight="bold")
    figure.text(.5, .89, f"Seed {c['seed']} · {c['environment']} · {c['algorithm']} · {report['execution']['ticks']} fixed ticks", ha="center", fontsize=11)
    series = (("population", "Living population"), ("mean_fitness", FITNESS_LABELS.get(c["mode"], "Mean earned fitness")),
              ("families", "Living founder families"), ("mean_meals", "Mean meals / scored cohort"))
    for axis, (key, title) in zip(axes.flat, series):
        axis.plot([r["time"] for r in report["samples"]], [r[key] for r in report["samples"]], color="#14866e", linewidth=2)
        axis.set(title=title, xlabel="Global simulated seconds")
        axis.grid(alpha=.2)
    figure.text(.07, .065, "One demonstration run. Provisional scores reset between cohorts; this plot does not establish an evolutionary advantage.", fontsize=10)
    figure.text(.07, .03, "Founder families are genealogical labels. Predator fitness is reported separately; social fitness measures survival age.", fontsize=10)
    return figure


def export_bundle(report, genomes, root, screenshot=None):
    """Write to a private staging directory, then atomically publish a new bundle."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"run-{report['run_id']}-{uuid.uuid4().hex[:6]}"
    staging = Path(tempfile.mkdtemp(prefix=".export-", dir=root))
    try:
        (staging / "config.json").write_text(json.dumps(report["config"], indent=2, allow_nan=False) + "\n")
        (staging / "run.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        write_csv(staging / "population.csv", report["samples"])
        write_csv(staging / "individuals.csv", report["individuals"])
        write_csv(staging / "telemetry.csv", report.get("telemetry", []))
        write_csv(staging / "lineage.csv", [{k: p[k] for k in ("key", "parent", "founder", "generation", "depth", "born_at", "cohort_ended_at", "censored")} for p in report["individuals"]])
        write_csv(staging / "generations.csv", report["simulation"].get("generations", []))
        keys = list(genomes)
        arrays = {"keys": np.array(keys), "metadata": np.array(json.dumps({"format_version": 1, "run_id": report["run_id"],
                  "config": report["config"], "parameter_names": ["input_weights", "hidden_bias", "output_weights", "output_bias"]}))}
        for index in range(4):
            arrays[f"parameter_{index}"] = np.stack([genomes[key][index] for key in keys])
        arrays["body_traits_present"] = np.array([p["body"] is not None for p in report["individuals"]])
        arrays["bodies"] = np.array([p["body"] or [0., 0., 0.] for p in report["individuals"]])
        np.savez_compressed(staging / "genomes.npz", **arrays)
        for suffix in ("png", "svg", "pdf"):
            figure = build_run_figure(report)
            figure.savefig(staging / f"population.{suffix}", dpi=140, facecolor=figure.get_facecolor())
            figure.clear()
        if screenshot:
            (staging / "application.png").write_bytes(screenshot)
        config_text = html.escape(json.dumps(report["config"], indent=2))
        metrics_text = html.escape(json.dumps(report["metrics"], indent=2))
        notes = "".join(f"<li>{html.escape(n)}</li>" for n in report["notes"])
        (staging / "report.html").write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Artificial Evolution research run</title>
<style>body{{font:16px system-ui;margin:40px auto;max-width:1050px;padding:0 24px;color:#173344;background:#f5f8fa}}pre{{background:white;padding:20px;overflow:auto;border-radius:12px}}img{{width:100%}}a{{color:#087f76}}section{{margin:28px 0}}</style>
<h1>Artificial Evolution / research run</h1><p>Version {VERSION} · Run {html.escape(report['run_id'])} · {html.escape(report['created_at'])}</p>
<img src="population.svg" alt="Population, fitness, founder families, and food history"><section><h2>Interpretation</h2><ul>{notes}</ul></section>
<section><h2>Observed metrics</h2><pre>{metrics_text}</pre></section><section><h2>Reproducible configuration</h2><pre>{config_text}</pre></section>
<p><a href="run.json">Complete run and controls</a> · <a href="population.csv">Population dataset</a> · <a href="individuals.csv">Lifetimes</a> · <a href="lineage.csv">Ancestry</a> · <a href="genomes.npz">Numeric genomes</a> · <a href="population.pdf">PDF figure</a></p>
<p>Replay from the project: <code>python simulator.py --replay PATH/TO/run.json --headless</code></p></html>''')
        manifest = {"schema_version": 1, "app_version": VERSION, "run_id": report["run_id"],
                    "files_sha256": {p.name: file_hash(p) for p in sorted(staging.iterdir())}}
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging)
        raise
    return destination
