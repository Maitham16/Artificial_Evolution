# Artificial Evolution 1.0.1

This patch release repairs archive packaging and makes existing hazard damage
visible in the research workbench. The v1.0.0 tag and assets are preserved.

## Packaging

- Both ZIPs include the committed MIT `LICENSE` and its SHA-256 in their separate
  internal manifests. A regression test checks license contents in both archives,
  including when the working-tree license differs from the committed version.
- The source archive includes `.python-version`, `.gitattributes`, and the
  GitHub Actions test workflow. The missing runtime-version file caused the
  v1.0.0 ZIP-based provenance validator to fail.
- Archives are rebuilt from the tagged Git commit, with fresh `BUILD-INFO.json`
  and `SHA256SUMS.txt` files.

## Hazard feedback

Red zones show their extra 12 energy/second cost and live exposure count. Click
a zone to inspect its rules. Exposed creatures receive warning rings and red
energy bars; their inspector shows current drain, accumulated hazard damage,
and exposure time. Damage and evolutionary physics are unchanged.

## Install

Extract the source ZIP and install its pinned dependencies in a new environment:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python simulator.py
```

Merge the research ZIP into the same extraction directory for historical datasets,
trained populations, and the complete test/provenance suite. Both archives use
the `Artificial_Evolution-v1.0.1/` prefix and contain identical license bytes.

`RELEASE-VERIFICATION.json` is attached after testing the actual public downloads
in a fresh environment. It records download checksums, license/manifest checks,
dependency installation, application launch, export/replay, and engineering
validation. This is author-run release verification, not independent external
scientific review or new training evidence.
