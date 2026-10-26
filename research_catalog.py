"""Allowlisted study recipes and isolated, observable background study jobs."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import uuid

from research_session import ROOT, file_hash


@dataclass(frozen=True)
class Study:
    step: int
    title: str
    script: str
    published: str
    plotter: str
    summary: str
    models: str = "new"
    protocol: bool = True

    @property
    def source(self):
        return ROOT / "results" / self.published

    def status(self):
        if not self.source.exists():
            return "Evidence not installed"
        return "Published evidence available"

    def missing_inputs(self):
        needed = {17: ("results/step16-models", "results/step16-speed-comparison.json"),
                  20: ("results/step16-models", "results/step17-unselected-models"),
                  27: ("results/step18-models", "results/step18-selection.json")}
        return [p for p in needed.get(self.step, ()) if not (ROOT / p).exists()]

    def command(self, directory, workers=1):
        if type(workers) is not int or not 1 <= workers <= 8:
            raise ValueError("Use one to eight study workers.")
        directory = Path(directory).resolve()
        command = [sys.executable, str(ROOT / self.script), "--workers", str(workers), "--output", str(directory / "study.json")]
        if self.protocol:
            command += ["--protocol-output", str(directory / "protocol.json")]
        if self.models == "new":
            command += ["--models-dir", str(directory / "models")]
        if self.step == 17:
            command += ["--unselected-models-dir", str(directory / "unselected-models")]
        if self.step == 20:
            command += ["--trace-dir", str(directory / "traces")]
        if self.step in (26, 27):
            command += ["--runs-dir", str(directory / "runs")]
        return command

    def plot_command(self, directory):
        directory = Path(directory).resolve()
        if self.step == 20:
            return [sys.executable, str(ROOT / self.plotter), str(directory / "study.json"),
                    "--plot", str(directory / "study.png"), "--viewer", str(directory / "playback.html")]
        return [sys.executable, str(ROOT / self.plotter), str(directory / "study.json"), "--output", str(directory / "study.png")]


STUDIES = (
    Study(13, "Evolved vs. random", "compare_creatures.py", "step13-comparison.json", "plot_comparison.py", "8 independent training seeds; held-out controls.", "none", False),
    Study(14, "Evolutionary parameters", "experiment_parameters.py", "step14-parameters.json", "plot_parameters.py", "Mutation, population, and food parameter sweep.", "none", False),
    Study(15, "Emergent food seeking", "analyze_intelligence.py", "step15-intelligence.json", "plot_intelligence.py", "Repeated unseen tests and sensor interventions.", "new", False),
    Study(16, "Equal-speed baselines", "experiment_speed.py", "step16-speed-comparison.json", "plot_speed.py", "16 lineages; random and greedy at identical speed."),
    Study(17, "What did they learn?", "experiment_strategy.py", "step17-strategy.json", "plot_strategy.py", "Saved Step 16 brains and unselected neural controls.", "source"),
    Study(18, "Selection vs. drift", "experiment_selection.py", "step18-selection.json", "plot_selection.py", "Matched parents, mutation streams, and training budget."),
    Study(19, "Specialization", "experiment_specialization.py", "step19-specialization.json", "plot_specialization.py", "Uniform, sparse, clustered, and generalist curricula."),
    Study(20, "Inside evolved brains", "inspect_brains.py", "step20-brains.json", "plot_brains.py", "Saved models, activations, traces, and sensory Jacobians.", "source"),
    Study(21, "Changing seasons", "experiment_seasons.py", "step21-seasons.json", "plot_seasons.py", "Seasonal food, moving clusters, and extinction."),
    Study(22, "Obstacles and hazards", "experiment_obstacles.py", "step22-obstacles.json", "plot_obstacles.py", "Matched foraging, collision, and risk-sensor tests."),
    Study(23, "Brains and bodies", "experiment_traits.py", "step23-traits.json", "plot_traits.py", "Heritable traits with explicit energetic costs."),
    Study(24, "Predator–prey", "experiment_predator_prey.py", "step24-coevolution.json", "plot_predator_prey.py", "Separate gene pools and frozen historical opponents."),
    Study(25, "Cooperation", "experiment_social.py", "step25-cooperation.json", "plot_social.py", "Group vs. individual survival, signaling, and sharing."),
    Study(26, "Continuous ecosystems", "experiment_ecosystem.py", "step26-ecosystems.json", "plot_ecosystem.py", "32 ecosystems, paid births, genealogy, and diversity.", "none"),
    Study(27, "Comprehensive evaluation", "experiment_evaluation.py", "step27-evaluation.json", "plot_evaluation.py", "16 saved pairs; 1,056 cohorts; corrected comparisons.", "source"),
)


class StudyJob:
    """One external study at a time; no shell or writes to published results."""
    def __init__(self, study, root, workers=1):
        if study.missing_inputs():
            raise ValueError("Install the research-evidence release asset first; missing " + ", ".join(study.missing_inputs()))
        self.study = study
        self.directory = Path(root).resolve() / f"study-{study.step}-{uuid.uuid4().hex[:10]}"
        self.directory.mkdir(parents=True, exist_ok=False)
        self.command = study.command(self.directory, workers)
        self.plot_command = study.plot_command(self.directory)
        self.phase = "study"
        self.status = "running"
        self.process = None
        self.log = None
        self.metadata = {"schema_version": 1, "step": study.step, "title": study.title,
                         "created_at": datetime.now(timezone.utc).isoformat(), "command": self.command,
                         "plot_command": self.plot_command, "working_directory": str(ROOT), "status": self.status,
                         "source_sha256": {p.name: file_hash(p) for p in sorted(ROOT.glob("*.py"))}}
        self._launch(self.command)

    def _save(self):
        self.metadata.update(status=self.status, phase=self.phase)
        path = self.directory / "job.json"
        temporary = self.directory / ".job.tmp"
        temporary.write_text(json.dumps(self.metadata, indent=2) + "\n")
        temporary.replace(path)

    def _launch(self, command):
        self.log = (self.directory / "progress.log").open("ab")
        self.process = subprocess.Popen(command, cwd=ROOT, stdout=self.log, stderr=subprocess.STDOUT,
                                        start_new_session=os.name != "nt")
        self.metadata["pid"] = self.process.pid
        self._save()

    def poll(self):
        if self.status != "running":
            return self.status
        result = self.process.poll()
        if result is None:
            return self.status
        self.log.close()
        self.metadata[f"{self.phase}_exit_code"] = result
        if result == 0 and self.phase == "study":
            # Existing scripts own their analysis; this launcher never fabricates
            # a complete status from a partial checkpoint.
            report = json.loads((self.directory / "study.json").read_text())
            if report.get("status") != "complete":
                self.status = "failed"
                self._save()
                return self.status
            self.phase = "plot"
            self._launch(self.plot_command)
        else:
            self.status = "complete" if result == 0 else "failed"
            self.metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
            self._save()
        return self.status

    def cancel(self):
        if self.status != "running":
            return
        if self.process.poll() is None:
            if os.name == "nt":
                self.process.terminate()
            else:
                os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    self.process.kill()
                else:
                    os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=5)
        self.log.close()
        self.status = "cancelled"
        self.metadata["finished_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def tail(self, lines=6):
        path = self.directory / "progress.log"
        if not path.exists():
            return []
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 6000))
            text = stream.read().decode(errors="replace")
        return text.splitlines()[-lines:]
