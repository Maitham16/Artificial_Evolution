# Documentation validation

[Documentation](../README.md) · [Repository review](../REPOSITORY_REVIEW.md) · [Development](../DEVELOPMENT.md)

This campaign checks the V2 documentation against the implementation at base commit `342438f6ea5e1beb99c245dbe4f0d49309e63389`. It changes guides/examples only. It does not rebuild the desktop app, alter numerical rules, rerun historical training studies or publish a release.

## Checks

| Check | Evidence |
| --- | --- |
| Repository inventory, Python/JSON/data-container scan | [Inventory](review-inventory.json) |
| V2 relative links, Markdown anchors, shell/Python/JSON fences and schema-field coverage | [Documentation checks](links-and-examples.json) |
| Copyable original-rule 120-tick export/verify/replay | [Log](original-example.log) |
| Same original bundle through the installed interpreter/helper | [Bundled verification/replay](original-bundled-replay.log) |
| Copyable physical 120-tick export/verify/replay | [Log](physical-example.log) |
| Same physical bundle through its installed habitat helper | [Bundled verification/replay](physical-bundled-replay.log) |
| Three small JSON configs construct, advance 120 ticks and replay | [Executed example record](executed-examples.json) |
| Godot CLI loads example JSON plus habitat flags and exports | [Log](godot-example.log), [verified report summary](godot-example.json) |
| Original files remain unchanged | [Preservation](preservation.json) |

The link check covers all Markdown under `v2/docs/` and the V2 README, including historical audit navigation. It resolves local targets and heading fragments, parses JSON examples through the actual schemas, checks every RunConfig/HabitatConfig field and supported application flag appears in the reference, compiles Python fences and runs `bash -n` on shell fences and launchers. External sites are source references rather than a recursively crawled mirror; Apple's startup guidance was checked against its support page.

The copied code blocks are identified by SHA-256 in the execution record. The temporary bundles were structurally verified and numerically replayed; they are not committed as new research datasets. The Godot example was headless and is **not a native FPS or graphics benchmark**.

Original tracked files and all 1,241 pre-existing local original files are hash-verified. Pre-existing V2 texture-import edits are preserved and excluded from the documentation commit. Existing original and V2 regression results are linked as historical evidence in [Research and validation](../RESEARCH_AND_VALIDATION.md#engineering-evidence); this documentation campaign does not claim a fresh full-suite run.

## Repeat the examples

Use [Export and replay](../EXPORTS_AND_REPLAY.md#copyable-original-rule-example) for the exact original/physical shell blocks. These are short correctness demonstrations, not complete generational or multi-seed studies.

To validate the JSON files without opening a window:

```bash
./.venv/bin/python - <<'PY'
from pathlib import Path
from research_session import RunConfig
for path in sorted(Path("v2/docs/examples").glob("*.json")):
    config = RunConfig.load(path)
    print(path, config.mode, config.algorithm)
PY
```

Keep generated outputs under fresh temporary or ignored directories. For complete numerical/native regression work, use [Development](../DEVELOPMENT.md#tests); rebuilding or regenerating art is not required to validate Markdown.
