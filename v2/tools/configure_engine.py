#!/usr/bin/env python3
"""Locate and verify the existing Python environment, then configure Godot."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--python', type=Path, default=root/'.venv/bin/python')
args = parser.parse_args()
python = args.python.absolute()
if not python.is_file():
    raise SystemExit('Create the original Python environment first:\npython3.13 -m venv .venv\n.venv/bin/python -m pip install -r requirements.txt')
result = subprocess.run([str(python), '-c', 'from research_session import ResearchSession, RunConfig; s=ResearchSession(RunConfig(population=2)); s.step(); print("Python engine ready")'], cwd=root, text=True, capture_output=True,
                        env={**os.environ, 'PYGAME_HIDE_SUPPORT_PROMPT':'1', 'SDL_VIDEODRIVER':'dummy', 'SDL_AUDIODRIVER':'dummy'})
if result.returncode:
    raise SystemExit('The existing Python engine could not start:\n'+result.stderr)
print(result.stdout.strip())
settings = Path.home()/'Library/Application Support/ArtificialEvolution2/engine.json'
settings.parent.mkdir(parents=True, exist_ok=True)
settings.write_text(json.dumps({'repository':str(root),'python':str(python)}, indent=2)+'\n')
print('Godot engine paths saved to', settings)
