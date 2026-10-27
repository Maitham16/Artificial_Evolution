---
title: Your first Living World experiment
description: Start a small, inspectable Artificial Evolution experiment, follow real Python creatures, compare models and export a reproducible run.
---

# Your first experiment

This short walkthrough uses V2's original Python foraging rules. It is a live demonstration; a single session is not an independent-seed scientific comparison.

## 1. Start with known conditions

Open **Research**, choose **Food seeking → Meadow → Selected neural**, and keep **100 founders** with seed **2801**. Choose **Start new population**. Configuration changes start fresh founders; they do not import a saved evolved population.

## 2. Meet an individual

Choose **Landscape view** or press **V**. Click an animal, choose **Focus**, then **Follow**. Read its source ID, energy, age, meals, fitness and ancestry in the inspector.

[![An actual deer selected and followed in the 3D application](../assets/gallery/animal-follow-thumb.jpg)](../gallery/index.md#animals-in-motion)

The model represents a Python agent. Coat, antlers and artistic anatomy do not imply simulated sex or additional genes.

## 3. Control the observation

Use **Space** to pause/resume Python and the speed menu for **1× / 5× / 20×**. A higher requested simulation rate does not guarantee the machine will achieve it. Camera motion and decorative scenery are separate from source ticks.

Open **Ecosystem** with **N**. Scroll inside the drawer to see its lower controls. Meals, births, deaths and captures come from observed Python events; manual weather and seasonal colors are cosmetic under original rules.

## 4. Return to the workbench

Open **Research** to see live plots and current-state hidden-neuron activity for a selected neural creature. The **Lineages** tab shows a bounded ancestry view; exported records retain the full genealogy.

For another session, try **Predator & prey** or **Continuous ecosystem**. Changing models normally archives the previous run before replacement. [Read each mode's actual rules](../v2/simulation-modes.md) before comparing scores across modes.

## 5. Export the record

Press **E** or choose **Export run**. The original engine writes configurations, datasets, numeric genomes, plots and reports. Original-rule and physical-habitat exports have different replay helpers; use the [export and replay guide](../v2/exports-and-replay.md).

For a scientific result, use [matched baselines and repeated independent seeds](../research/index.md), with training and test environments separated. The preserved V1 study tools already provide those protocols.
