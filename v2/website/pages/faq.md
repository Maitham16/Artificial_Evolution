---
title: FAQ — launching, simulation rules, animals and research
description: Answers about V1 and V2, the Mac app icon, Python ownership, animation, weather, physical habitat, performance, exports and the project's scientific claims.
---

# Frequently asked questions

## Which version should I start with?

Choose **V2** to explore a 3D world, follow animals and inspect live source events. Choose **V1** for the original research workbench, background study catalog and preserved experiment protocols. Both remain available. [Compare the actual interfaces](gallery/index.md#one-engine-two-views).

## Which icon opens V2?

On the prepared Mac, open **Finder → Go → Home → Applications → Artificial Evolution 2.0.app**. This is the installed application, separate from Godot and Blender. A fresh clone needs source setup or a local package build first. [Installation tutorial](getting-started/index.md).

## Does the website run the simulation?

No. This is a static documentation website. The applications run on your computer; the gallery contains actual captured runs and recordings.

## Does Godot control the creatures?

Python controls brains, movement, food, survival, reproduction and interactions. Godot receives snapshots, interpolates movement and displays the scene. Animation and foot IK do not move the authoritative Python agent. [Architecture](architecture/index.md).

## Do rain, rivers and snow affect survival?

Under original rules, the landscape and weather are decorative. The optional **Physical habitat (v2 rules)** adds recorded Python slope, wading, deep-water contact and climate costs. Manual visual overrides remain cosmetic. This is a 2.5D extension, not full rigid-body ecology. [Physical habitat](v2/physical-habitat.md).

## Are the animals' appearances inherited biological traits?

Python body size affects scale in modes with body genes. Deer/wolf anatomy, coats and antlers are visual choices; antlers do not imply simulated sex. Continuous growth is an age-based visual treatment, while the Python collision radius is already present at birth. [Animals and animation](v2/animals-and-animation.md).

## Why can feet still slip or clip the ground?

Nearby animals use terrain foot IK with finite reach and detailed animation budgets. Residual slipping or imperfect contact remains possible, especially on difficult terrain or with mismatched source movement. The gallery retains what the application actually rendered. [Animation limits](v2/animals-and-animation.md).

## Is 60 FPS guaranteed?

No. Recorded local Metal trials on the M3 reached approximately 60 FPS under their tested conditions. Machine, quality, population, renderer and capture overhead affect performance. Render FPS and achieved Python simulation rate are different measurements. [Performance troubleshooting](v2/troubleshooting.md).

## Can I reload a saved evolved population in V2?

V2 has no generic saved-genome import or replay viewer. Loading configuration starts fresh founders. The original tools own saved-population studies; original-rule exports can be numerically replayed and opened paused in V1, while physical exports use the V2 helper. [Export and replay](v2/exports-and-replay.md).

## Do the screenshots prove intelligence or cooperation?

They show the application and observed events. Scientific claims require controlled conditions, appropriate baselines and independent training seeds. Realistic animals, group boundaries and persistent lineages alone do not establish general intelligence, cooperation or speciation. [Research methods](research/index.md).

## Why does continuous mode still show G01 after births?

It has overlapping lifetimes instead of synchronized replacement. Individual ancestry depth can increase while the world header remains `G01`. Follow the selected creature's parent identity and the exported genealogy. [Continuous ecosystem](v2/simulation-modes.md#continuous-ecosystem).

## Where can I get help or report a problem?

Start with [troubleshooting](v2/troubleshooting.md). For an issue, include the version, operating system, renderer, configuration/seed, exact reproduction steps and relevant logs or export. Use the repository's [issue tracker](https://github.com/Maitham16/Artificial_Evolution/issues).
