"""Interactive controls, study isolation, release reproducibility, and CLI entry."""

from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from build_release import build_release
from research_app import ResearchApp
from research_catalog import STUDIES, StudyJob
from research_session import ALGORITHMS, MODES, ROOT, ResearchSession, RunConfig, verify_bundle
from simulator import main


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = ResearchApp(RunConfig(population=20), self.temp.name, size=(1200, 750))

    def tearDown(self):
        if self.app.job: self.app.job.cancel()
        self.app.executor.shutdown(wait=True)
        pygame.quit()
        self.temp.cleanup()

    def test_actual_button_hitboxes_and_letterboxed_selection(self):
        self.app.draw()
        rect = next(rect for rect, action in self.app.hits if action == ("pause",))
        point = (self.app.viewport.x + rect.centerx * self.app.viewport.width / 1440,
                 self.app.viewport.y + rect.centery * self.app.viewport.height / 900)
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))
        self.assertTrue(self.app.session.paused)
        self.app.action(("speed",))
        self.assertEqual(self.app.session.speed, 5)
        self.assertEqual(self.app.session.events[-1]["action"], "speed")

    def test_mode_change_is_transactional_and_keeps_previous_run_on_failure(self):
        original = self.app.session
        self.app.text_values["population"] = "0"
        with patch.object(self.app, "queue_export") as export:
            self.app.apply()
            self.assertIs(self.app.session, original)
            export.assert_not_called()
            self.app.text_values["population"] = "20"
            self.app.text_values["seed"] = "456"
            self.app.choose("mode", "continuous")
            self.assertEqual(self.app.text_values["seed"], "456")
            self.app.apply()
            export.assert_called_once()
            self.assertEqual(self.app.session.config.mode, "continuous")
            self.assertEqual(self.app.session.config.seed, 456)

    def test_every_mode_tabs_settings_and_current_state_preview_render(self):
        for mode in MODES:
            config = replace(RunConfig(), mode=mode, environment="seasonal" if mode == "seasons" else "uniform",
                             algorithm=ALGORITHMS[mode][0], population=20, predators=4, groups=2)
            self.app.session = ResearchSession(config)
            self.app.draft = self.app.session.config.to_dict()
            self.app.sync_inputs()
            for tab in ("Live world", "Lineages", "Research"):
                self.app.tab = tab
                self.app.draw()
            self.app.modal = "settings"
            self.app.draw()
            self.app.modal = None
        self.assertEqual(self.app.canvas.get_size(), (1440, 900))

    def test_text_input_shortcuts_do_not_pause_or_export_while_editing(self):
        self.app.action(("edit", "seed"))
        self.app.handle_event(pygame.event.Event(pygame.TEXTINPUT, text="7801"))
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, mod=0))
        self.assertEqual(self.app.session.speed, 1)
        self.assertEqual(self.app.text_values["seed"], "7801")
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
        self.assertIsNone(self.app.edit)

    def test_published_figure_opens_inside_the_application(self):
        self.app.action(("published_plot",))
        self.assertEqual(self.app.modal, "figure")
        self.app.draw()
        self.assertIsNotNone(self.app.figure_preview)

    def test_background_export_uses_immutable_snapshot_and_verifies(self):
        self.app.draw()
        for _ in range(6): self.app.session.step()
        self.app.queue_export()
        future = self.app.exports[0]
        for _ in range(6): self.app.session.step()
        path = future.result(timeout=30)
        self.assertEqual(verify_bundle(path)["execution"]["ticks"], 6)
        self.assertTrue((path / "application.png").exists())
        self.app.poll_background()
        self.assertEqual(self.app.last_export, path)


class StudyLauncherTests(unittest.TestCase):
    def test_all_15_study_and_plot_recipes_use_supported_cli_flags(self):
        self.assertEqual([s.step for s in STUDIES], list(range(13, 28)))
        for study in STUDIES:
            for script, command in ((study.script, study.command(".cache/study-fixture")),
                                    (study.plotter, study.plot_command(".cache/study-fixture"))):
                tree = ast.parse((ROOT / script).read_text())
                flags = {a.value for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                         and n.func.attr == "add_argument" for a in n.args if isinstance(a, ast.Constant) and isinstance(a.value, str)}
                self.assertTrue({x for x in command[2:] if x.startswith("--")} <= flags, (script, command))
            self.assertNotIn("--reuse-models", study.command(".cache/study-fixture"))
            self.assertNotIn(str(study.source), study.command(".cache/study-fixture"))

    def test_successful_study_then_plot_has_explicit_complete_status(self):
        processes = [MagicMock(pid=123456), MagicMock(pid=123457)]
        for process in processes: process.poll.return_value = 0
        with tempfile.TemporaryDirectory() as temp, patch("research_catalog.subprocess.Popen", side_effect=processes) as popen:
            job = StudyJob(STUDIES[-2], temp)
            (job.directory / "study.json").write_text(json.dumps({"status": "complete"}))
            self.assertEqual(job.poll(), "running")
            self.assertEqual(job.phase, "plot")
            self.assertEqual(job.poll(), "complete")
            metadata = json.loads((job.directory / "job.json").read_text())
            self.assertEqual(metadata["plot_exit_code"], 0)
            self.assertEqual(metadata["study_exit_code"], 0)
            self.assertFalse(popen.call_args.kwargs.get("shell", False))

    def test_failed_or_cancelled_jobs_keep_logs_and_never_claim_complete(self):
        process = MagicMock(pid=123456)
        process.poll.return_value = None
        with tempfile.TemporaryDirectory() as temp, patch("research_catalog.subprocess.Popen", return_value=process), patch("research_catalog.os.killpg") as kill:
            job = StudyJob(STUDIES[-2], temp)
            job.cancel()
            self.assertEqual(job.status, "cancelled")
            kill.assert_called_once()
            self.assertTrue((job.directory / "progress.log").exists())
        process.poll.return_value = 2
        with tempfile.TemporaryDirectory() as temp, patch("research_catalog.subprocess.Popen", return_value=process):
            job = StudyJob(STUDIES[-2], temp)
            self.assertEqual(job.poll(), "failed")

    def test_partial_success_exit_is_not_treated_as_complete(self):
        process = MagicMock(pid=123456)
        process.poll.return_value = 0
        with tempfile.TemporaryDirectory() as temp, patch("research_catalog.subprocess.Popen", return_value=process):
            job = StudyJob(STUDIES[-2], temp)
            (job.directory / "study.json").write_text('{"status":"running"}')
            self.assertEqual(job.poll(), "failed")


class ReleaseAndCliTests(unittest.TestCase):
    def test_release_uses_only_committed_blobs_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            for name, data in {"app.py": "print('committed')\n", "README.md": "release", "requirements.txt": "numpy\n",
                               "results/evidence.json": "{}", "results/step28-summary.json": "{}",
                               "results/step28-demos/sample/run.json": "{}", ".venv/secret.py": "exclude"}.items():
                path = repo / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(data)
            def git(*args):
                return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.STDOUT)
            git("init", "--quiet")
            git("add", ".")
            git("-c", "user.name=Release Test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "fixture")
            (repo / "app.py").write_text("uncommitted")
            (repo / "private.txt").write_text("never package")
            first = build_release(repo, root / "one")
            second = build_release(repo, root / "two")
            self.assertEqual(first, second)
            for kind in ("source", "research"):
                path = root / "one" / f"Artificial_Evolution-v1.0.0-{kind}.zip"
                with zipfile.ZipFile(path) as archive:
                    names = archive.namelist()
                    self.assertIn(f"Artificial_Evolution-v1.0.0/release-{kind}-manifest.json", names)
                    self.assertFalse(any(".venv" in n or "private.txt" in n for n in names))
                    self.assertTrue(all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in archive.infolist()))
                    if kind == "source":
                        self.assertEqual(archive.read("Artificial_Evolution-v1.0.0/app.py"), b"print('committed')\n")
                        self.assertIn("Artificial_Evolution-v1.0.0/results/step28-summary.json", names)
                        self.assertFalse(any("step28-demos/" in n for n in names))
                    else: self.assertIn("Artificial_Evolution-v1.0.0/results/evidence.json", names)
            with self.assertRaises(ValueError): build_release(repo, root / "one")
            with self.assertRaises(ValueError): build_release(repo, root / "bad", version="../unsafe")

    def test_headless_cli_exports_and_verifies_then_replays(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--headless", "--ticks", "5", "--population", "4", "--export-root", temp]), 0)
            path = next(Path(temp).glob("run-*"))
            self.assertEqual(main(["--verify-bundle", str(path)]), 0)
            self.assertEqual(main(["--replay", str(path / "run.json"), "--headless"]), 0)

    def test_default_simulator_entry_opens_the_workbench(self):
        with patch("research_app.ResearchApp") as app:
            app.return_value.run.return_value = 0
            self.assertEqual(main([]), 0)
            app.return_value.run.assert_called_once_with(frames=None, screenshot=None)

    def test_bad_cli_budgets_and_config_overrides_are_rejected(self):
        for argv in (["--headless"], ["--headless", "--ticks", "0"], ["--population", "0", "--headless", "--ticks", "1"],
                     ["--replay", "file.json", "--seed", "12", "--headless"]):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit): main(argv)


if __name__ == "__main__":
    unittest.main()
