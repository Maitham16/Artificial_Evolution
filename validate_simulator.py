"""Reproduce the final engineering demonstration and audit its exported bundles.

This is a bounded integration check, not a new independent evolution experiment.
Use new output paths; published demonstration records are never overwritten.
"""

from dataclasses import replace
import argparse
import json
import os
from pathlib import Path
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from research_catalog import STUDIES, Study, StudyJob
from research_session import (ALGORITHMS, MODES, ROOT, ResearchSession, RunConfig, export_bundle,
                              file_hash, replay_run, verify_bundle)


class RunnerSmoke(Study):
    def command(self, directory, workers=1):
        return super().command(directory, workers) + ["--seeds", "28001", "28002", "--duration", "1"]


def validate(output, demos, baseline, native):
    output, demos = Path(output), Path(demos)
    if output.exists() or demos.exists():
        raise ValueError("Use new validation output and demonstration paths.")
    demos.mkdir(parents=True)
    records = []
    for mode in MODES:
        config = RunConfig(mode=mode, algorithm=ALGORITHMS[mode][0],
                           environment="seasonal" if mode == "seasons" else "uniform")
        if mode in ("foraging", "traits"):
            config = replace(config, population=20, food_count=0, generations=2)
        elif mode == "seasons":
            config = replace(config, population=20, season_food=(0, 0, 0, 0), generations=2)
        elif mode in ("social", "predator_prey"):
            config = replace(config, episode_seconds=1., generations=2)
        elif mode == "continuous":
            config = replace(config, duration=60.)
        session = ResearchSession(config)
        limit = 3600 if mode == "continuous" else 120 if mode == "obstacles" else 16000
        for _ in range(limit):
            if not session.step(): break
        report, genomes = session.snapshot()
        path = export_bundle(report, genomes, demos / mode)
        verified = verify_bundle(path)
        replay_run(verified)
        records.append({"mode": mode, "bundle": str(path), "manifest_sha256": file_hash(path / "manifest.json"),
                        "ticks": session.ticks, "individuals": len(session.births), "finished": session.finished,
                        "parent_edges": sum(p["parent"] is not None for p in session.births.values()),
                        "complete_bundle_verified": True, "tick_replay_bitwise_equal": True})
        print(f"Verified {mode}: {session.ticks} ticks / {len(session.births)} individuals", flush=True)
    native_records = []
    for path in sorted(Path(native).glob("*")):
        if path.is_dir() and (path / "manifest.json").exists():
            report = verify_bundle(path)
            replay_run(report)
            native_records.append({"bundle": str(path), "mode": report["config"]["mode"],
                                   "environment": report["config"]["environment"], "algorithm": report["config"]["algorithm"],
                                   "ticks": report["execution"]["ticks"], "manifest_sha256": file_hash(path / "manifest.json"),
                                   "verified_and_replayed": True})
    if native_records:
        from research_app import ResearchApp
        import pygame
        focus = next(r for r in native_records if r["mode"] == "continuous")
        report = verify_bundle(focus["bundle"])
        session = replay_run(report)
        app = ResearchApp(session.config, ROOT / ".cache/validation-exports")
        app.session = session
        for tab, suffix in (("Live world", "workbench"), ("Lineages", "lineages"), ("Research", "research")):
            app.tab = tab
            app.draw()
            pygame.image.save(app.canvas, str(output.parent / f"step28-{suffix}.png"))
        app.executor.shutdown()
        pygame.quit()
    smoke = RunnerSmoke(26, "Runner integration smoke / not scientific evidence", "experiment_ecosystem.py",
                        "step26-ecosystems.json", "plot_ecosystem.py", "Two seeds, one simulated second.", "none")
    job = StudyJob(smoke, ROOT / ".cache/step28-job-checks", workers=2)
    deadline = time.monotonic() + 120
    while job.poll() == "running":
        if time.monotonic() > deadline:
            job.cancel()
            raise RuntimeError("Integration study exceeded its test budget.")
        time.sleep(.1)
    if job.status != "complete":
        raise RuntimeError(f"Integration job failed; inspect {job.directory / 'progress.log'}")
    baseline_data = json.loads(Path(baseline).read_text())
    preserved = {p: h for p, h in baseline_data["files_sha256"].items() if p != "README.md"}
    if not all(file_hash(ROOT / p) == h for p, h in preserved.items()):
        raise RuntimeError("A preexisting scientific source or artifact changed.")
    result = {"schema_version": 1, "status": "passed", "app_version": "1.0.0", "purpose": "Bounded engineering validation, not an independent scientific replication.",
              "modes": records, "native_ui_records": native_records,
              "native_checks": ["Pause/resume", "Live ecosystem and ancestry", "Background export", "Research catalog",
                                "Mode switching with automatic archive", "Clustered environment", "Neutral algorithm", "Clean application exit"],
              "runner_smoke": {"directory": str(job.directory), "status": job.status, "seeds": [28001, 28002], "duration_seconds": 1,
                               "job_metadata": job.metadata, "data_sha256": file_hash(job.directory / "study.json"),
                               "plot_sha256": file_hash(job.directory / "study.png")},
              "preserved_earlier_files_except_README": len(preserved),
              "unchanged_prior_result_artifacts": sum(p.startswith("results/") for p in preserved),
              "source_sha256": {p.name: file_hash(p) for p in sorted(ROOT.glob("*.py"))},
              "all_15_study_recipes_available": [s.step for s in STUDIES] == list(range(13, 28))}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--demos", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=ROOT / "results/step28-baseline.json")
    parser.add_argument("--native", type=Path, default=ROOT / "results/step28-native")
    args = parser.parse_args()
    validate(args.output, args.demos, args.baseline, args.native)
    print(f"Simulator integration validation passed: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
