"""The unified Pygame research workbench. UI changes never mutate experiments."""

from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from dataclasses import replace
import colorsys
import hashlib
import io
import json
from pathlib import Path
import shlex
import time
import webbrowser

import numpy as np
import pygame

from obstacles import HAZARD_ENERGY_PER_SECOND, HAZARD_FITNESS_PER_SECOND
from research_catalog import STUDIES, StudyJob
from research_session import (ALGORITHMS, ENVIRONMENTS, FITNESS_LABELS, MODES, MODE_NAMES, ROOT,
                              VERSION, ResearchSession, RunConfig, export_bundle)


SIZE = (1440, 900)
BG = (10, 19, 25)
PANEL = (18, 32, 41)
INSET = (24, 42, 51)
LINE = (43, 65, 75)
INK = (228, 240, 242)
MUTED = (145, 169, 179)
MINT = (105, 224, 182)
GOLD = (240, 196, 113)
RED = (245, 134, 145)
ALGORITHM_NAMES = {"selection": "Fitness selection", "neutral": "Neutral inheritance", "random": "Random movement",
                   "greedy": "Greedy food seeking", "founder": "Frozen founders", "coevolution": "Two-species selection",
                   "group": "Group survival", "individual": "Individual survival", "funded": "Funded reproduction", "clonal": "Clonal reproduction"}
ENV_NAMES = {"uniform": "Uniform food", "clustered": "Clustered food", "sparse": "Sparse food",
             "wide_clustered": "Wide clustered arena", "barren": "No food", "seasonal": "Seasonal food & clusters"}
INTEGER_FIELDS = {"seed", "population", "generations", "population_cap", "season_length", "predators", "groups", "food_count"}
ENUM_FIELDS = {"food_access": ("restricted", "open"), "risk_sensors": ("intact", "hidden"),
               "prey_sensors": ("intact", "hidden"), "predator_sensors": ("intact", "hidden")}
BOOL_FIELDS = {"signaling", "sharing", "signals_hidden"}


def family_color(key):
    hue = int(hashlib.sha256(key.encode()).hexdigest()[:6], 16) / 0xffffff
    return tuple(round(v * 255) for v in colorsys.hsv_to_rgb(hue, .55, .95))


class ResearchApp:
    def __init__(self, config=None, output_root=None, size=SIZE):
        pygame.display.init()
        pygame.font.init()
        self.window = pygame.display.set_mode(size, pygame.RESIZABLE)
        pygame.display.set_caption(f"Artificial Evolution {VERSION} | Research workbench")
        self.canvas = pygame.Surface(SIZE)
        self.fonts = {"title": pygame.font.Font(None, 38), "large": pygame.font.Font(None, 32),
                      "body": pygame.font.Font(None, 23), "small": pygame.font.Font(None, 19), "tiny": pygame.font.Font(None, 17)}
        self.session = ResearchSession(config or RunConfig())
        self.output_root = Path(output_root or ROOT / "exports")
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="run-export")
        self.exports = []
        self.last_export = None
        self.last_export_ticks = None
        self.job = None
        self.study_index = len(STUDIES) - 1
        self.workers = 1
        self.tab = "Live world"
        self.modal = None
        self.popup = None
        self.edit = None
        self.selection_all = False
        self.import_path = ""
        self.notice = "Choose an environment and algorithm, then Apply to start a new run."
        self.error = False
        self.running = True
        self.hits = []
        self.arena = pygame.Rect(288, 161, 850, 510)
        self.viewport = pygame.Rect(0, 0, *size)
        self.clock = pygame.time.Clock()
        self.last_rate_time = time.monotonic()
        self.last_rate_ticks = 0
        self.actual_rate = 0.
        self.lineage_rings = True
        self.figure_preview = None
        self.hazard_selection = None
        self.draft = self.session.config.to_dict()
        self.text_values = {}
        self.sync_inputs()

    def sync_inputs(self):
        self.text_values = {k: ",".join(map(str, v)) if isinstance(v, list) else "" if v is None else str(v)
                            for k, v in self.draft.items()}

    def message(self, text, error=False):
        self.notice, self.error = text, error

    def select_hazard(self, index):
        world = self.session.world
        if 0 <= index < len(getattr(world, "dangers", ())):
            self.hazard_selection = (self.session.run_id, world.generation, index)
            world.selected_creature = None
            self.message("Hazards drain extra energy while a creature overlaps them. Click a creature to watch its energy.")

    def selected_hazard(self):
        if self.hazard_selection is not None:
            run, generation, index = self.hazard_selection
            world = self.session.world
            if (run == self.session.run_id and generation == world.generation
                    and index < len(getattr(world, "dangers", ()))):
                return index, world.dangers[index]
        self.hazard_selection = None
        return None

    def text(self, value, x, y, kind="body", color=INK):
        self.canvas.blit(self.fonts[kind].render(str(value), True, color), (x, y))

    def wrapped(self, value, rect, color=MUTED, kind="small", max_lines=6):
        words = str(value).split()
        rows, line = [], ""
        for word in words:
            candidate = (line + " " + word).strip()
            if self.fonts[kind].size(candidate)[0] > rect.width and line:
                rows.append(line)
                line = word
            else:
                line = candidate
        rows.append(line)
        for index, row in enumerate(rows[:max_lines]):
            self.text(row, rect.x, rect.y + index * 21, kind, color)

    def card(self, rect, color=PANEL):
        pygame.draw.rect(self.canvas, color, rect, border_radius=12)
        pygame.draw.rect(self.canvas, LINE, rect, 1, border_radius=12)

    def button(self, label, rect, action, *, accent=False, enabled=True):
        rect = pygame.Rect(rect)
        pygame.draw.rect(self.canvas, MINT if accent and enabled else INSET if enabled else PANEL, rect, border_radius=7)
        pygame.draw.rect(self.canvas, LINE, rect, 1, border_radius=7)
        image = self.fonts["body"].render(label, True, BG if accent and enabled else INK if enabled else MUTED)
        self.canvas.blit(image, image.get_rect(center=rect.center))
        if enabled:
            self.hits.append((rect, action))

    def selector(self, field, label, y, choices, names):
        self.text(label.upper(), 36, y, "tiny", MUTED)
        rect = pygame.Rect(34, y + 21, 222, 36)
        self.button(names[self.draft[field]] + "  >", rect, ("popup", field, choices, names))

    def input(self, field, label, rect):
        rect = pygame.Rect(rect)
        self.text(label, rect.x, rect.y - 21, "small", MUTED)
        pygame.draw.rect(self.canvas, INSET, rect, border_radius=6)
        pygame.draw.rect(self.canvas, MINT if self.edit == field else LINE, rect, 1, border_radius=6)
        value = self.import_path if field == "import_path" else self.text_values[field]
        if field in BOOL_FIELDS:
            value = "ON" if self.draft[field] else "OFF"
        image = self.fonts["body"].render(value or ("Environment default" if field == "food_count" else ""), True, INK)
        clip = self.canvas.get_clip()
        self.canvas.set_clip(rect.inflate(-12, -6))
        self.canvas.blit(image, (rect.x + 10, rect.y + 8))
        self.canvas.set_clip(clip)
        self.hits.append((rect, ("edit", field)))

    def read_draft(self):
        data = dict(self.draft)
        for key, text in self.text_values.items():
            if key in ("mode", "environment", "algorithm", "schema_version") or key in ENUM_FIELDS or key in BOOL_FIELDS:
                continue
            if key == "season_food":
                data[key] = [int(n.strip()) for n in text.split(",")]
            elif key == "food_count" and not text.strip():
                data[key] = None
            elif key in INTEGER_FIELDS:
                data[key] = int(text)
            else:
                data[key] = float(text)
        return RunConfig.from_dict(data)

    def choose(self, field, value):
        pending_text = dict(self.text_values)
        self.draft[field] = value
        if field == "mode":
            self.draft["algorithm"] = ALGORITHMS[value][0]
            self.draft["environment"] = "seasonal" if value == "seasons" else "uniform"
            self.draft["food_count"] = None
        if field == "environment":
            self.draft["food_count"] = None
        if field == "algorithm" and value == "clonal":
            self.draft["mutation_rate"] = self.draft["body_mutation_rate"] = 0.
            pending_text["mutation_rate"] = pending_text["body_mutation_rate"] = "0.0"
        self.sync_inputs()
        for key, text in pending_text.items():
            if key not in ("mode", "environment", "algorithm", "food_count"):
                self.text_values[key] = text
        self.popup = None
        self.message("Changes pending. Apply starts a new seeded run and archives this one.")

    def queue_export(self):
        report, genomes = self.session.snapshot()
        buffer = io.BytesIO()
        pygame.image.save(self.canvas, buffer, "application.png")
        future = self.executor.submit(export_bundle, report, genomes, self.output_root, buffer.getvalue())
        self.exports.append(future)
        self.last_export_ticks = (self.session.run_id, self.session.ticks)
        self.message("Exporting datasets, configuration, genomes, plots, and report…")

    def apply(self):
        try:
            config = self.read_draft()
            candidate = ResearchSession(config)  # Construct successfully before retiring the old run.
            self.queue_export()
            self.session = candidate
            self.draft = candidate.config.to_dict()
            self.sync_inputs()
            self.last_rate_time, self.last_rate_ticks = time.monotonic(), 0
            self.modal = self.popup = self.edit = None
            self.message("New seeded run started. The previous run is exporting in the background.")
        except (ValueError, TypeError, OSError, RuntimeError) as error:
            self.message(str(error), True)

    def open_path(self, path):
        path = Path(path).resolve()
        if path.exists():
            webbrowser.open(path.as_uri())
        else:
            self.message("That artifact is not installed. Download the research-evidence release asset.", True)

    def action(self, action):
        key, *args = action
        if key == "popup": self.popup = tuple(args)
        elif key == "choose": self.choose(*args)
        elif key == "edit":
            field = args[0]
            if field in BOOL_FIELDS:
                self.draft[field] = not self.draft[field]
            elif field in ENUM_FIELDS:
                options = ENUM_FIELDS[field]
                self.draft[field] = options[(options.index(self.draft[field]) + 1) % len(options)]
            else:
                self.edit, self.selection_all = field, True
                pygame.key.start_text_input()
        elif key == "apply": self.apply()
        elif key == "pause": self.session.set_control("paused", not self.session.paused)
        elif key == "speed": self.session.set_control("speed", (1, 5, 20)[((1, 5, 20).index(self.session.speed) + 1) % 3])
        elif key == "automatic": self.session.set_control("automatic", not self.session.automatic)
        elif key == "advance":
            if not self.session.advance(): self.message("A completed cohort is required; continuous births have no generation button.")
        elif key == "export": self.queue_export()
        elif key == "tab": self.tab = args[0]
        elif key == "modal": self.modal, self.edit = args[0], None
        elif key == "close": self.modal = self.popup = self.edit = None
        elif key == "restart":
            self.draft = self.session.config.to_dict()
            self.sync_inputs()
            self.apply()
        elif key == "import":
            try:
                self.draft = RunConfig.load(Path(self.import_path).expanduser()).to_dict()
                self.sync_inputs()
                self.message("Configuration loaded into the editor. Apply to start it.")
            except (ValueError, TypeError, OSError) as error: self.message(str(error), True)
        elif key == "open_export":
            if self.last_export: self.open_path(self.last_export / "report.html")
        elif key == "hazard": self.select_hazard(args[0])
        elif key == "study": self.study_index = (self.study_index + args[0]) % len(STUDIES)
        elif key == "workers": self.workers = (1, 2, 4, 8)[((1, 2, 4, 8).index(self.workers) + 1) % 4]
        elif key == "published": self.open_path(STUDIES[self.study_index].source)
        elif key == "published_plot":
            path = STUDIES[self.study_index].source.with_suffix(".png")
            if path.exists():
                self.figure_preview = pygame.image.load(str(path)).convert()
                self.modal = "figure"
            else: self.open_path(path)
        elif key == "start_study":
            if self.job and self.job.status == "running": return
            try:
                self.job = StudyJob(STUDIES[self.study_index], self.output_root, self.workers)
                self.message("Full study running in its own folder. Use Cancel study to stop; partial records are retained.")
            except (ValueError, OSError) as error: self.message(str(error), True)
        elif key == "cancel_study" and self.job: self.job.cancel()
        elif key == "open_job" and self.job: self.open_path(self.job.directory / ("study.png" if self.job.status == "complete" else "progress.log"))

    def logical_position(self, pos):
        return ((pos[0] - self.viewport.x) * SIZE[0] / self.viewport.width,
                (pos[1] - self.viewport.y) * SIZE[1] / self.viewport.height)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.VIDEORESIZE:
            self.window = pygame.display.set_mode(event.size, pygame.RESIZABLE)
        if event.type == pygame.TEXTINPUT and self.edit:
            text = "" if self.selection_all else (self.import_path if self.edit == "import_path" else self.text_values[self.edit])
            text = (text + event.text)[:500]
            if self.edit == "import_path": self.import_path = text
            else: self.text_values[self.edit] = text
            self.selection_all = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.modal or self.popup or self.edit: self.modal = self.popup = self.edit = None
                else: self.running = False
                return
            if self.edit:
                if event.key == pygame.K_BACKSPACE:
                    text = "" if self.selection_all else (self.import_path if self.edit == "import_path" else self.text_values[self.edit])[:-1]
                    if self.edit == "import_path": self.import_path = text
                    else: self.text_values[self.edit] = text
                    self.selection_all = False
                elif event.key == pygame.K_a and event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META): self.selection_all = True
                elif event.key in (pygame.K_RETURN, pygame.K_TAB): self.edit = None
                return
            shortcuts = {pygame.K_SPACE: ("pause",), pygame.K_s: ("speed",), pygame.K_a: ("automatic",),
                         pygame.K_n: ("advance",), pygame.K_r: ("restart",), pygame.K_e: ("export",),
                         pygame.K_l: ("tab", "Lineages"), pygame.K_b: ("tab", "Research"), pygame.K_h: ("modal", "help")}
            if event.key in shortcuts:
                self.action(shortcuts[event.key])
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            point = self.logical_position(event.pos)
            for rect, action in reversed(self.hits):
                if rect.collidepoint(point):
                    self.action(action)
                    return
            self.edit = None
            if self.popup:
                self.popup = None
                return
            if not self.modal and self.tab == "Live world" and self.arena.collidepoint(point):
                w = self.session.world
                position = ((point[0] - self.arena.x) * w.width / self.arena.width,
                            (point[1] - self.arena.y) * w.height / self.arena.height)
                self.hazard_selection = None
                w.select_creature(position)
                if w.selected_creature is None:
                    for index, hazard in enumerate(getattr(w, "dangers", ())):
                        if hazard.overlaps(*position):
                            self.select_hazard(index)
                            break

    def spark(self, title, rect, key, color=MINT):
        self.card(rect)
        self.text(title, rect.x + 14, rect.y + 10, "small", MUTED)
        values = [(r["time"], r[key]) for r in self.session.samples if r[key] is not None]
        if not values: return
        if len(values) > 240: values = values[::max(1, len(values) // 240)] + values[-1:]
        low, high = min(0., min(v for _, v in values)), max(1., max(v for _, v in values))
        area = pygame.Rect(rect.x + 14, rect.y + 39, rect.width - 28, rect.height - 57)
        points = [(area.x + (t - values[0][0]) / max(.01, values[-1][0] - values[0][0]) * area.width,
                   area.bottom - (v - low) / (high - low) * area.height) for t, v in values]
        pygame.draw.line(self.canvas, LINE, area.bottomleft, area.bottomright)
        if len(points) > 1: pygame.draw.lines(self.canvas, color, False, points, 2)
        pygame.draw.circle(self.canvas, color, points[-1], 3)
        self.text(f"{values[-1][1]:.1f}", rect.right - 65, rect.y + 10, "small", color)

    def draw_sidebar(self):
        self.card(pygame.Rect(20, 106, 250, 766))
        self.selector("mode", "World mode", 126, MODES, MODE_NAMES)
        mode = self.draft["mode"]
        envs = ("seasonal",) if mode == "seasons" else tuple(e for e in ENVIRONMENTS if e != "seasonal" and not (mode == "social" and e in ("clustered", "wide_clustered")))
        self.selector("environment", "Environment", 196, envs, ENV_NAMES)
        self.selector("algorithm", "Algorithm", 266, ALGORITHMS[mode], ALGORITHM_NAMES)
        self.input("seed", "Random seed", (34, 360, 222, 37))
        self.input("population", "Initial population", (34, 421, 222, 37))
        self.input("mutation_rate", "Neural mutation probability", (34, 482, 222, 37))
        horizon = "duration" if mode == "continuous" else "generations"
        self.input(horizon, "Duration (seconds)" if mode == "continuous" else "Generation limit", (34, 543, 222, 37))
        self.button("Apply / new run", (34, 598, 222, 40), ("apply",), accent=True)
        self.button("Resume" if self.session.paused else "Pause", (34, 651, 106, 36), ("pause",))
        self.button(f"Speed {self.session.speed}x", (150, 651, 106, 36), ("speed",))
        self.button("Export run", (34, 700, 222, 38), ("export",))
        self.button("All settings / import", (34, 750, 222, 36), ("modal", "settings"))
        self.button("Help", (34, 803, 106, 34), ("modal", "help"))
        self.button("Restart", (150, 803, 106, 34), ("restart",))

    def draw_inspector(self):
        s, w = self.session, self.session.world
        self.card(pygame.Rect(1154, 106, 266, 766))
        m = s.metrics()
        for i, (label, value) in enumerate((("ALIVE", m["population"]), ("FOOD", m["food"]),
                                           ("ROOT FAMILIES", m["families"]), ("SEEN", m["births"]))):
            x, y = 1170 + (i % 2) * 122, 126 + (i // 2) * 75
            self.text(label, x, y, "tiny", MUTED)
            self.text(str(value), x, y + 24, "large", MINT)
        self.text(FITNESS_LABELS.get(s.config.mode, "Mean earned fitness"), 1170, 291, "small", MUTED)
        self.text(f"{m['mean_fitness']:.2f}", 1170, 314, "large")
        if s.config.mode == "predator_prey":
            self.text(f"Predator fitness {m['predator_mean_fitness']:.1f}", 1170, 349, "small", GOLD)
        else:
            self.text(f"Mean meals {m['mean_meals']:.2f}", 1170, 349, "small", GOLD)
        selected_hazard = self.selected_hazard()
        self.text("SELECTED HAZARD" if selected_hazard else "SELECTED CREATURE", 1170, 391, "tiny", MUTED)
        c = w.selected_creature
        if selected_hazard:
            index, hazard = selected_hazard
            exposed = sum(hazard.overlaps(c.x, c.y, c.radius) for c in w.creatures)
            self.text(f"Zone {index + 1}", 1170, 420, "large", RED)
            self.text(f"Currently exposed: {exposed}", 1170, 456, "small", RED if exposed else MUTED)
            self.text(f"Extra energy loss: {HAZARD_ENERGY_PER_SECOND:g}/s", 1170, 495, "small", RED)
            self.text(f"Fitness penalty: {HAZARD_FITNESS_PER_SECOND:g}/s", 1170, 522, "small", MUTED)
            self.wrapped("Creatures can pass through this area. Damage applies for the time their body overlaps the red zone.",
                         pygame.Rect(1170, 568, 228, 110))
            self.wrapped("Click an exposed creature to see its energy drain, accumulated hazard damage, and exposure time.",
                         pygame.Rect(1170, 700, 228, 110))
        elif c is None:
            self.wrapped("Click a living creature to inspect its ancestry, energy, and current-state neural activations.", pygame.Rect(1170, 423, 230, 130))
        else:
            key = s.key(c)
            birth = s.births[key]
            self.text(key, 1170, 420, "large", family_color(birth["founder"]))
            self.text(f"Age {c.age:.1f}s / energy {c.energy:.1f}", 1170, 456, "small")
            pygame.draw.rect(self.canvas, LINE, (1170, 484, 228, 7), border_radius=3)
            in_danger = getattr(c, "in_danger", False)
            pygame.draw.rect(self.canvas, RED if in_danger else MINT, (1170, 484, round(228 * c.energy / c.energy_capacity), 7), border_radius=3)
            self.text(f"Parent {birth['parent'] or 'founder'}", 1170, 509, "small", MUTED)
            self.text(f"Root {birth['founder']} / depth {birth['depth']}", 1170, 535, "small", MUTED)
            self.text(f"Speed {c.speed:.1f} / size {c.radius}", 1170, 561, "small", MUTED)
            hazard_details = hasattr(c, "hazard_energy_lost")
            if hazard_details:
                self.text(f"{'IN HAZARD' if in_danger else 'Energy drain'}: {c.energy_cost_per_second:.1f}/s",
                          1170, 582, "small", RED if in_danger else MUTED)
                self.text(f"Hazard loss {c.hazard_energy_lost:.1f} / {c.hazard_seconds:.1f}s", 1170, 602, "tiny", RED)
            if s.config.algorithm in ("random", "greedy"):
                self.wrapped("Hand-coded steering. Stored placeholder weights do not control this creature.", pygame.Rect(1170, 632 if hazard_details else 612, 226, 100))
            else:
                inputs = w.get_sensory_inputs(c)
                hidden = np.tanh(inputs @ c.brain.input_weights + c.brain.hidden_bias)
                offset = 20 if hazard_details else 0
                self.text("CURRENT-STATE ACTIVATION", 1170, 612 + offset, "tiny", MUTED)
                for i, value in enumerate(hidden):
                    y = 641 + offset + i * 18
                    self.text(str(i + 1), 1170, y - 3, "tiny", MUTED)
                    pygame.draw.line(self.canvas, LINE, (1200, y + 3), (1394, y + 3), 5)
                    pygame.draw.line(self.canvas, MINT if value >= 0 else GOLD, (1297, y + 3), (1297 + round(value * 96), y + 3), 6)
                self.text("Preview at the current state", 1170, 810 if hazard_details else 800, "tiny", MUTED)
        self.button("Open last report", (1170, 828, 232, 30), ("open_export",), enabled=self.last_export is not None)

    def draw_world(self):
        s, w = self.session, self.session.world
        state = "EXTINCT" if getattr(w, "lineage_extinct", False) else "LIMIT REACHED" if s.finished else "PAUSED" if s.paused else "AWAITING BREEDING" if w.final_evaluation and not s.automatic else "RUNNING"
        self.text(MODE_NAMES[s.config.mode], 290, 111, "large")
        self.text(f"{state}  /  t {s.elapsed:.1f}s  /  {'continuous births' if s.config.mode == 'continuous' else 'cohort G' + str(w.generation)}", 290, 143, "tiny", MINT)
        surface = pygame.Surface((w.width, w.height))
        w.draw(surface, (0, 0))
        if self.lineage_rings:
            for c in w.creatures:
                root = s.births[s.key(c)]["founder"]
                pygame.draw.circle(surface, family_color(root), (round(c.x), round(c.y)), c.radius + 4, 1)
        for c in w.creatures:
            if getattr(c, "in_danger", False):
                pygame.draw.circle(surface, RED, (round(c.x), round(c.y)), c.radius + 7, 2)
        scale = min(850 / w.width, 510 / w.height)
        self.arena = pygame.Rect(288 + (850 - round(w.width * scale)) // 2, 161 + (510 - round(w.height * scale)) // 2,
                                 round(w.width * scale), round(w.height * scale))
        self.canvas.blit(pygame.transform.smoothscale(surface, self.arena.size), self.arena)
        pygame.draw.rect(self.canvas, LINE, self.arena, 1)
        selected_hazard = self.selected_hazard()
        for index, hazard in enumerate(getattr(w, "dangers", ())):
            center = (self.arena.x + round(hazard.x * self.arena.width / w.width),
                      self.arena.y + round(hazard.y * self.arena.height / w.height))
            radius = round(hazard.radius * self.arena.width / w.width)
            exposed = sum(hazard.overlaps(c.x, c.y, c.radius) for c in w.creatures)
            if selected_hazard and selected_hazard[0] == index:
                pygame.draw.circle(self.canvas, RED, center, radius, 3)
            label = f"HAZARD -{HAZARD_ENERGY_PER_SECOND:g} energy/s"
            width = max(104, self.fonts["tiny"].size(label)[0] + 12)
            badge = pygame.Rect(center[0] - width // 2, max(self.arena.top + 3, center[1] - radius - 38), width, 35)
            badge.clamp_ip(self.arena.inflate(-6, -6))
            pygame.draw.rect(self.canvas, (57, 29, 38), badge, border_radius=5)
            pygame.draw.rect(self.canvas, RED if exposed else LINE, badge, 1, border_radius=5)
            self.text(label, badge.x + 6, badge.y + 3, "tiny", RED)
            self.text(f"{exposed} exposed", badge.x + 6, badge.y + 18, "tiny", INK)
            self.hits.append((badge, ("hazard", index)))
        self.button("Auto births ON" if s.config.mode == "continuous" and s.automatic else "Auto births OFF" if s.config.mode == "continuous" else "Auto breed ON" if s.automatic else "Auto breed OFF",
                    (288, 685, 190, 31), ("automatic",))
        self.button("Next generation", (490, 685, 178, 31), ("advance",), enabled=s.config.mode != "continuous" and w.final_evaluation is not None and not s.finished)
        self.text(f"Target {s.speed}x / measured {self.actual_rate:.1f}x", 740, 692, "small", MUTED)

    def draw_lineages(self):
        s = self.session
        self.card(pygame.Rect(288, 109, 850, 606))
        self.text("Ancestry through time", 310, 130, "large")
        self.text("Every observed birth and parent edge / colors are founder families, not species", 310, 167, "small", MUTED)
        plot = pygame.Rect(320, 220, 790, 290)
        births = list(s.births.values())
        observed_depth = max(b["depth"] for b in births)
        maximum = max(1, observed_depth)
        def position(b):
            return (plot.x + b["born_at"] / max(1., s.elapsed) * plot.width,
                    plot.bottom - b["depth"] / maximum * plot.height)
        for b in births:
            if b["parent"]:
                pygame.draw.line(self.canvas, LINE, position(s.births[b["parent"]]), position(b))
            pygame.draw.circle(self.canvas, family_color(b["founder"]), position(b), 3)
        self.text(f"0s -> {s.elapsed:.1f}s / maximum depth {observed_depth}", 320, 526, "small", MUTED)
        counts = Counter(s.births[s.key(c)]["founder"] for c in s.world.creatures)
        for index, (root, count) in enumerate(counts.most_common(8)):
            x, y = 320 + (index % 2) * 400, 573 + (index // 2) * 30
            self.text(f"{root}: {count} living", x, y, "small", family_color(root))

    def draw_research(self):
        study = STUDIES[self.study_index]
        self.card(pygame.Rect(288, 109, 850, 606))
        self.text("Published experiments & new studies", 310, 130, "large")
        self.button("<", (310, 187, 45, 35), ("study", -1))
        self.button(">", (1067, 187, 45, 35), ("study", 1))
        self.text(f"STEP {study.step} / {study.title}", 373, 193, "body", MINT)
        self.wrapped(study.summary, pygame.Rect(310, 245, 790, 45))
        self.text(study.status(), 310, 293, "small", GOLD)
        self.button("Open published data", (310, 329, 240, 37), ("published",), enabled=study.source.exists())
        self.button("Open published figure", (565, 329, 240, 37), ("published_plot",), enabled=study.source.with_suffix(".png").exists())
        self.text("FULL PROTOCOL / uses the study's declared seed and training budgets", 310, 395, "small", MUTED)
        self.wrapped("These studies can take minutes or longer. Each runs in a new folder with its command, source hashes, protocol, data, and progress log. Published files are read-only inputs.", pygame.Rect(310, 425, 790, 70), max_lines=3)
        active = self.job is not None and self.job.status == "running"
        self.button("Run full study", (310, 511, 220, 38), ("start_study",), accent=True, enabled=not active and not study.missing_inputs())
        self.button(f"Workers: {self.workers}", (544, 511, 145, 38), ("workers",), enabled=not active)
        self.button("Cancel study", (704, 511, 176, 38), ("cancel_study",), enabled=active)
        self.button("Open output", (895, 511, 216, 38), ("open_job",), enabled=self.job is not None)
        if self.job:
            self.text(f"Step {self.job.study.step}: {self.job.status} / {self.job.phase}", 310, 571, "small", MINT)
            for index, line in enumerate(self.job.tail(4)):
                self.text(line[:106], 310, 600 + index * 23, "tiny", MUTED)
        else:
            self.text("Choose a study with the arrows. New studies do not change the live world.", 310, 590, "small", MUTED)

    def advanced_fields(self):
        mode = self.draft["mode"]
        common = ["food_count", "mutation_scale", "sample_interval"]
        if mode == "seasons": common.remove("food_count")
        if mode in ("foraging", "seasons", "obstacles"): common += ["fixed_speed"]
        extra = {"foraging": [], "obstacles": ["risk_sensors"],
                 "seasons": ["season_length", "season_food", "cluster_shift", "reproductive_age"],
                 "traits": ["body_mutation_rate", "body_mutation_scale"],
                 "predator_prey": ["predators", "episode_seconds", "prey_sensors", "predator_sensors", "body_mutation_rate", "body_mutation_scale"],
                 "social": ["episode_seconds", "groups", "food_access", "signaling", "sharing", "signals_hidden"],
                 "continuous": ["duration", "population_cap", "regrowth_rate", "maturity_age", "birth_cooldown", "body_mutation_rate", "body_mutation_scale"]}
        return common + extra[mode]

    def draw_modal(self):
        shade = pygame.Surface(SIZE, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 180))
        self.canvas.blit(shade, (0, 0))
        self.hits = []
        self.card(pygame.Rect(295, 104, 850, 744))
        self.text("Run settings" if self.modal == "settings" else "Published research figure" if self.modal == "figure" else "Using the research workbench", 321, 128, "large")
        self.button("Close", (1013, 123, 107, 34), ("close",))
        if self.modal == "figure" and self.figure_preview:
            scale = min(800 / self.figure_preview.get_width(), 625 / self.figure_preview.get_height())
            size = (round(self.figure_preview.get_width() * scale), round(self.figure_preview.get_height() * scale))
            self.canvas.blit(pygame.transform.smoothscale(self.figure_preview, size), (322 + (800 - size[0]) // 2, 187 + (625 - size[1]) // 2))
            return
        if self.modal == "help":
            messages = ["Space: pause/resume   S: target speed   A: automatic breeding/births", "N: next completed generation   R: restart the same seed   E: export",
                        "L: ancestry   B: research studies   H: help   Esc: close panel / quit",
                        "Choose a world, environment, and supported algorithm in the left panel.",
                        "Apply starts a new seeded run and exports the previous run automatically.",
                        "All settings / import exposes mode-specific controls and accepts config JSON paths.",
                        "Click a creature for its family, energy, and current-state neural activation preview.",
                        "Live scores are provisional. Cohort scores reset; continuous scores use all lifetimes.",
                        "Predator fitness stays separate from prey fitness; social fitness is survival age.",
                        "Export creates CSV/JSON datasets, lineage, numeric genomes, PNG/SVG/PDF plots,",
                        "a browser-readable report, configuration, screenshot, and SHA-256 manifest.",
                        "Replay: python simulator.py --replay PATH/TO/run.json --headless",
                        "One live demonstration is not statistical evidence. Research launches the original",
                        "independent-seed studies into isolated folders. Closing the app cancels active jobs."]
            for i, line in enumerate(messages): self.text(line, 322, 203 + i * 37, "small", MUTED)
            return
        self.text("These edits apply to a new run. Empty food stock uses the environment default.", 322, 178, "small", MUTED)
        for i, field in enumerate(self.advanced_fields()):
            x, y = 322 + (i % 2) * 400, 245 + (i // 2) * 70
            self.input(field, field.replace("_", " ").title(), (x, y, 370, 35))
        self.input("import_path", "Import an exported or preset config JSON path", (322, 677, 590, 36))
        self.button("Load", (930, 677, 190, 36), ("import",))
        self.button("Apply / new run", (322, 775, 240, 40), ("apply",), accent=True)
        self.wrapped(self.notice, pygame.Rect(581, 767, 528, 60), RED if self.error else MUTED, max_lines=2)

    def draw(self):
        self.hits = []
        self.canvas.fill(BG)
        self.text("ARTIFICIAL EVOLUTION", 24, 20, "title")
        self.text(f"RESEARCH WORKBENCH / {VERSION}", 26, 63, "small", MINT)
        for i, name in enumerate(("Live world", "Lineages", "Research")):
            self.button(name, (572 + i * 173, 31, 159, 38), ("tab", name), accent=self.tab == name)
        self.text(f"SEED {self.session.config.seed}", 1180, 34, "body", MUTED)
        self.draw_sidebar()
        if self.tab == "Live world": self.draw_world()
        elif self.tab == "Lineages": self.draw_lineages()
        else: self.draw_research()
        self.draw_inspector()
        for i, (title, key, color) in enumerate((("Population / time", "population", MINT),
                                                ("Provisional fitness / time", "mean_fitness", GOLD),
                                                ("Living families / time", "families", (168, 154, 242)))):
            self.spark(title, pygame.Rect(288 + i * 288, 733, 274, 139), key, color)
        self.text(self.notice[:150], 24, 881, "tiny", RED if self.error else MUTED)
        if self.modal: self.draw_modal()
        if self.popup:
            field, choices, names = self.popup
            # Block the underlying interface while choosing a dropdown value.
            self.hits = []
            top = {"mode": 179, "environment": 249, "algorithm": 319}[field]
            popup = pygame.Rect(33, top, 239, len(choices) * 35 + 8)
            self.card(popup, INSET)
            for i, value in enumerate(choices):
                self.button(names[value], (38, top + 4 + i * 35, 229, 32), ("choose", field, value), accent=self.draft[field] == value)
        width, height = self.window.get_size()
        scale = min(width / SIZE[0], height / SIZE[1])
        self.viewport = pygame.Rect((width - round(SIZE[0] * scale)) // 2, (height - round(SIZE[1] * scale)) // 2,
                                    round(SIZE[0] * scale), round(SIZE[1] * scale))
        self.window.fill(BG)
        self.window.blit(pygame.transform.smoothscale(self.canvas, self.viewport.size), self.viewport)
        pygame.display.flip()

    def poll_background(self):
        for future in self.exports[:]:
            if future.done():
                self.exports.remove(future)
                try:
                    self.last_export = future.result()
                    self.message(f"Export complete: {self.last_export.name}")
                except Exception as error:
                    self.message(f"Export failed: {error}", True)
        if self.job:
            try: self.job.poll()
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.job.cancel()
                self.message(f"Study job failed: {error}", True)

    def run(self, frames=None, screenshot=None):
        count = 0
        self.draw()
        try:
            while self.running and (frames is None or count < frames):
                dt = self.clock.tick(60) / 1000.
                for event in pygame.event.get(): self.handle_event(event)
                try: self.session.update(dt, max_ticks=12)
                except (ValueError, RuntimeError) as error:
                    self.session.paused = True
                    self.message(f"Run paused: {error}", True)
                self.poll_background()
                now = time.monotonic()
                if now - self.last_rate_time >= 1:
                    self.actual_rate = (self.session.ticks - self.last_rate_ticks) / 60 / (now - self.last_rate_time)
                    self.last_rate_time, self.last_rate_ticks = now, self.session.ticks
                self.draw()
                count += 1
            if screenshot:
                Path(screenshot).parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(self.canvas, str(screenshot))
        finally:
            if self.session.ticks and self.last_export_ticks != (self.session.run_id, self.session.ticks): self.queue_export()
            if self.job: self.job.cancel()
            self.executor.shutdown(wait=True)
            self.poll_background()
            pygame.quit()
        return 0
