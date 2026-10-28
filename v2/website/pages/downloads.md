---
title: Downloads — V2 Mac app and V1 research simulator
description: Download Artificial Evolution 2.0.0 for Apple Silicon with its bundled Python engine, or get the separate V1 source and research archives with SHA-256 checksums.
---

# Downloads

## V2 · 3D Living World 2.0.0

[Download for Apple Silicon · macOS 14+](https://github.com/Maitham16/Artificial_Evolution/releases/download/v2.0.0/Artificial_Evolution-v2.0.0-macos-arm64.zip){ .md-button .md-button--primary }
[Release notes and all assets](https://github.com/Maitham16/Artificial_Evolution/releases/tag/v2.0.0){ .md-button }
[SHA-256 checksums](https://github.com/Maitham16/Artificial_Evolution/releases/download/v2.0.0/SHA256SUMS.txt){ .md-button }

The standalone app includes Godot, Python, the original engine, dependencies, animals and landscapes. No developer tools or internet connection are required to run it after installation.

1. Download the ZIP and checksum file into the same folder; verify the archive with the command below.
2. Double-click the ZIP and move **Artificial Evolution 2.0.app** to your home **Applications** folder.
3. Open the app. If macOS blocks this unnotarized build, follow the app-specific [opening instructions](v2/installation.md#install-a-desktop-zip).

```bash
shasum -a 256 -c SHA256SUMS.txt
```

This package is ad-hoc signed, not Apple notarized. It requires Apple Silicon and macOS 14 or later; native validation was performed on macOS 27 / Apple M3. Intel, Windows and Linux desktop builds are not included. [Compatibility and source installation](v2/installation.md).

The release includes build information, the runtime lock, validation evidence and checksums. [Build V2 yourself](v2/installation.md#build-the-standalone-app) from the tagged source if preferred.

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

## Licenses

Project code is MIT licensed. Animal/landscape sources have recorded CC0 licenses; runtime dependencies carry their own notices. See [license and credits](about.md).
