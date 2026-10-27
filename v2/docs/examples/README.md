# Checked documentation examples

[Documentation](../README.md) · [Settings](../CONFIGURATION.md) · [Export and replay](../EXPORTS_AND_REPLAY.md)

These small RunConfig files use the existing Python schema. Omitted values use its defaults. They are examples for source runs, not changes to the original `configs/` presets or full research protocols.

| File | Purpose |
| --- | --- |
| [foraging.json](foraging.json) | 30 founders, 90 food, three selected-neural cohorts |
| [predator_prey.json](predator_prey.json) | 60 total founders including 12 predators, three 60-second episodes |
| [social.json](social.json) | 40 founders in four equal groups, restricted access and optional social actions enabled |
| [Lifecycle demonstration](../../configs/animation_lifecycle.json) | Existing V2 continuous-birth preset |
| [Physical options](../../configs/physical_habitat.json) | Existing separate HabitatConfig, not RunConfig |

From the repository root:

```bash
./"v2/Run Artificial Evolution 2.command" -- --immersive \
  --config="$(pwd)/v2/docs/examples/foraging.json"
```

For a bounded numerical example without a graphics window:

```bash
./.venv/bin/python simulator.py --headless \
  --config v2/docs/examples/foraging.json --ticks 120 \
  --export-root /tmp/ae2-doc-example
```

This executes only two simulated seconds and exports an incomplete demonstration. It does not finish three generations or estimate an evolutionary effect. The [export guide](../EXPORTS_AND_REPLAY.md#copyable-original-rule-example) provides complete copyable verification/replay commands and a fixed-tick physical example.
