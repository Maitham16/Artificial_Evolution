---
title: Downloads — V1 releases and V2 source builds
description: Download the published Artificial Evolution V1.0.1 source and research archives, verify SHA-256 checksums, or build the V2 3D Mac application from source.
---

# Downloads

## V1 · Published release 1.0.1

| Archive | Contents | Approximate size |
| --- | --- | ---: |
| [Source ZIP](https://github.com/Maitham16/Artificial_Evolution/releases/download/v1.0.1/Artificial_Evolution-v1.0.1-source.zip) | Original Python source, tests, documentation and license | 2.3 MB |
| [Research ZIP](https://github.com/Maitham16/Artificial_Evolution/releases/download/v1.0.1/Artificial_Evolution-v1.0.1-research.zip) | Preserved research results and license | 90 MB |

[Release notes and all assets](https://github.com/Maitham16/Artificial_Evolution/releases/tag/v1.0.1){ .md-button .md-button--primary }
[SHA-256 checksums](https://github.com/Maitham16/Artificial_Evolution/releases/download/v1.0.1/SHA256SUMS.txt){ .md-button }

After downloading the archives and checksum file into the same directory, verify them on macOS:

```bash
shasum -a 256 -c SHA256SUMS.txt
```

The [verification record](https://github.com/Maitham16/Artificial_Evolution/releases/download/v1.0.1/RELEASE-VERIFICATION.json) and [build information](https://github.com/Maitham16/Artificial_Evolution/releases/download/v1.0.1/BUILD-INFO.json) accompany the release. Version [1.0.0](https://github.com/Maitham16/Artificial_Evolution/releases/tag/v1.0.0) remains a separate historical release.

## V2 · 3D Living World

**A public V2 desktop release asset has not been published.** The current Godot application is available in the repository; the Mac packaging pipeline creates a local Apple Silicon desktop ZIP.

[Get the current repository source](https://github.com/Maitham16/Artificial_Evolution/archive/refs/heads/master.zip){ .md-button }
[V2 source installation](v2/installation.md#option-b-source-development){ .md-button }

From a prepared source checkout:

```bash
./v2/tools/build_macos.sh
python3 v2/tools/install_macos.py
open "$HOME/Applications/Artificial Evolution 2.0.app"
```

The local build is `v2/build/Artificial Evolution 2.zip`; ignored build artifacts do not arrive in a fresh clone. Read the [runtime compatibility and signing details](v2/installation.md#requirements-and-compatibility) before distributing a package.

## Licenses

Project code is MIT licensed. Animal/landscape sources have recorded CC0 licenses; runtime dependencies carry their own notices. See [license and credits](about.md).
