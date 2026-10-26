"""Artificial Evolution 1.0: interactive research workbench and tick replay CLI."""

import argparse
import io
import json
import os
from pathlib import Path
import time

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from research_session import MODES, ROOT, VERSION, ResearchSession, RunConfig, export_bundle, replay_run, verify_bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--config", type=Path, help="load an exported config or configs/*.json preset")
    parser.add_argument("--mode", choices=MODES)
    parser.add_argument("--environment", help="uniform, clustered, sparse, wide_clustered, barren, or seasonal")
    parser.add_argument("--algorithm", help="choose an algorithm supported by the mode; see the user guide")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--population", type=int)
    parser.add_argument("--food-count", type=int)
    parser.add_argument("--mutation-rate", type=float)
    parser.add_argument("--generations", type=int)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--speed", type=int, choices=(1, 5, 20), default=1)
    parser.add_argument("--headless", action="store_true", help="run fixed ticks without an interactive window")
    parser.add_argument("--ticks", type=int, help="positive fixed-tick budget for a headless run")
    parser.add_argument("--frames", type=int, help="stop the interactive application after this many rendered frames")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--export-root", type=Path, default=ROOT / "exports")
    parser.add_argument("--replay", type=Path, help="verify an exported run.json by reconstructing its physics and controls")
    parser.add_argument("--verify-bundle", type=Path, help="verify all manifest checksums and numeric birth genomes")
    parser.add_argument("--catalog", action="store_true", help="list integrated study recipes")
    parser.add_argument("--study", type=int, help="run a complete research study (13–27) in an isolated folder")
    parser.add_argument("--workers", type=int, default=1, choices=(1, 2, 4, 8))
    args = parser.parse_args(argv)
    if args.verify_bundle:
        try:
            data = verify_bundle(args.verify_bundle)
            print(f"Bundle verified: {data['run_id']}, {len(data['individuals'])} lifetimes.")
            return 0
        except (OSError, ValueError, KeyError, TypeError) as error:
            parser.error(str(error))
    from research_catalog import STUDIES, StudyJob
    if args.catalog:
        print(json.dumps([{"step": s.step, "title": s.title, "script": s.script, "evidence": s.status(),
                           "summary": s.summary} for s in STUDIES], indent=2))
        return 0
    if args.study:
        study = next((s for s in STUDIES if s.step == args.study), None)
        if study is None: parser.error("Choose a study from 13 to 27.")
        try:
            job = StudyJob(study, args.export_root, args.workers)
        except (ValueError, OSError) as error:
            parser.error(str(error))
        print(f"Study folder: {job.directory}", flush=True)
        previous = None
        try:
            while job.poll() == "running":
                tail = job.tail(1)
                if tail and tail[-1] != previous:
                    previous = tail[-1]
                    print(previous, flush=True)
                time.sleep(.2)
        except KeyboardInterrupt:
            job.cancel()
        except (ValueError, OSError) as error:
            job.cancel()
            parser.error(str(error))
        print(f"Study {job.status}: {job.directory}")
        return 0 if job.status == "complete" else 1
    if args.ticks is not None and args.ticks < 1 or args.frames is not None and args.frames < 1:
        parser.error("Tick and frame budgets must be positive.")
    if args.headless and not args.replay and args.ticks is None:
        parser.error("A headless run requires --ticks or --replay.")
    if args.replay and (args.config or args.mode or args.environment or args.algorithm or args.seed is not None or args.ticks is not None
                        or any(getattr(args, key) is not None for key in ("population", "food_count", "mutation_rate", "generations", "duration"))):
        parser.error("Replay uses the saved configuration, controls, and tick horizon; omit overrides.")
    try:
        if args.replay:
            report = verify_bundle(args.replay.parent) if (args.replay.parent / "manifest.json").exists() else json.loads(args.replay.read_text())
            session = replay_run(report)
            print(f"Replay verified: {session.ticks} ticks, {len(session.births)} lifetimes.")
            if args.headless: return 0
        else:
            config = (RunConfig.load(args.config) if args.config else RunConfig()).to_dict()
            if args.mode:
                from research_session import ALGORITHMS
                config.update(mode=args.mode, algorithm=ALGORITHMS[args.mode][0],
                              environment="seasonal" if args.mode == "seasons" else "uniform", food_count=None)
            for key in ("environment", "algorithm", "seed", "population", "food_count", "mutation_rate", "generations", "duration"):
                if getattr(args, key) is not None: config[key] = getattr(args, key)
            session = ResearchSession(RunConfig.from_dict(config))
        if args.headless:
            session.set_control("speed", args.speed)
            for _ in range(args.ticks):
                if not session.step(): break
            screenshot = None
            if args.screenshot:
                os.environ["SDL_VIDEODRIVER"] = "dummy"
                from research_app import ResearchApp
                import pygame
                app = ResearchApp(session.config, args.export_root)
                app.session = session
                app.draw()
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(app.canvas, str(args.screenshot))
                buffer = io.BytesIO()
                pygame.image.save(app.canvas, buffer, "application.png")
                screenshot = buffer.getvalue()
                app.executor.shutdown()
                pygame.quit()
            data, bank = session.snapshot()
            path = export_bundle(data, bank, args.export_root, screenshot)
            print(f"Exported run: {path}")
            return 0
        from research_app import ResearchApp
        app = ResearchApp(session.config, args.export_root)
        app.session = session
        app.session.set_control("speed", args.speed)
        if args.replay: app.session.set_control("paused", True)
        return app.run(frames=args.frames, screenshot=args.screenshot)
    except (ValueError, TypeError, OSError, RuntimeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
