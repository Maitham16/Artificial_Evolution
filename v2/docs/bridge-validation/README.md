# Python-engine connection validation — 27 October 2026

The 3D application uses the existing Python `ResearchSession` and numerical models. These checks validate the connection and preservation of behavior, not a new scientific finding.

| Check | Result | Evidence |
| --- | --- | --- |
| Original Python regression suite | **431 tests passed in 114.165s** | [Original tests](original-tests.log) |
| Original file preservation | **591 tracked / 1,241 total original files unchanged** | [Hash report](preservation.json) |
| Python adapter and TCP transport | **20 tests passed** | [Tests](tests.log) |
| Godot snapshot/interpolation | **18 checks passed** | [Tests](tests.log) |
| Native-scene integration with Python | **22 checks passed** | [UI checks](ui-tests.log) |
| Fresh source copy, no Godot/import/bytecode caches | Python tests, Godot checks, and interface connection passed | [Clean-source log](clean-source.log) |
| Actual standalone Mac ZIP | All **seven Python modes** rendered, exported, verified, and replayed exactly | [Packaged-app record](packaged-macos.json), [native log](native-macos.log) |
| Installed app without terminal path overrides | Saved repository/interpreter paths connected successfully | [Installed-app log](installed-app.log) |
| Existing user CLI compatibility | Original `simulator.py --verify-bundle` and `--replay … --headless` passed on a native Godot export | [Native log](native-macos.log) |

The adapter tests compare direct Python sessions against bridge-observed sessions at identical ticks in all seven modes. They compare complete scientific state and birth genomes, and repeat observation during execution to detect accidental RNG or state mutation. All five foraging policies are also compared through actual cohort transitions. Tests observe original hazard damage, continuous births, original predator captures, and original social energy transfers.

Transport tests cover paused stepping, rejection of pose-write commands, invalid configurations retaining the current run, exact 63-bit seeds, fragmented UTF-8, more than one buffer's worth of coalesced requests, token rejection, one controlling viewer, disconnect/reconnect retention, private endpoint permissions, original export verification and replay, archive-before-replacement, failed archives retaining the previous run, failed saves keeping Python paused, automatic save on normal shutdown, and reconnection during an asynchronous archive without losing the new ancestry ledger.

Godot checks cover coordinate/radius/range/geometry conversion, position and shortest-angle interpolation, unchanged authoritative energy/age/poses, no extrapolated motion, birth/death/run boundaries, stale-frame rejection, bounded display buffers, and process clock resets. Interface checks instantiate the real scene with a real Python process, exercise controls, stepping, tabs, picking, neural previews, reconnection, configuration import, world switching, full-world camera framing, and species styling after a mode change.

The packaged-app validator extracts the actual ZIP into a fresh temporary directory, verifies its signature, runs its binary outside the source working directory, captures native OpenGL screenshots, and exports through Python. It verifies every original bundle manifest and replays each mode with the original engine. Native mode runs cover about two simulated seconds; longer generational/birth/interaction behavior is exercised in the adapter tests and existing original suite. Source and native tests are local implementation checks, not external independent reproduction.

The Mac archive is universal arm64/x86_64; only Apple Silicon was executed. It is ad-hoc signed, not notarized. Computer control for the app was unavailable, so no manual operating-system mouse/keyboard QA is claimed. Interface automation uses actual Godot control signals and input handlers plus native rendered output.

Issues found and fixed include retaining authoritative state during asynchronous exports, pausing/reconnecting without resetting the run, old queued frames arriving after new-run acknowledgements, float rounding of large seeds, failed archives/save handling, stale body styling after identities are reused in a new run, and camera framing. Export clients keep sending heartbeats while waiting for the original plotting/export worker. The cold-install test waits for an acknowledged archive rather than assuming the first plotting/font-cache startup finishes within a fixed short delay.

Reproduce from the repository root:

```bash
./v2/tools/test.sh
./.venv/bin/python -m unittest discover -v
python3 v2/tools/verify_original.py --all-existing
./v2/tools/build_macos.sh
./.venv/bin/python v2/tools/validate_macos.py
```

Use the default preservation check without `--all-existing` on another checkout. Generated full native bundles remain under ignored `v2/build/bridge-validation/`. Committed screenshots are under [screenshots](../screenshots/). Historical initial-prototype records remain in [validation](../validation/README.md).
