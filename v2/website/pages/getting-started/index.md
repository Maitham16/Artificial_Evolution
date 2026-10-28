---
title: Install Artificial Evolution — choose V1 or V2
description: A practical installation tutorial for the original Python 2D simulator and Godot 3D Living World, with separate launch commands and Mac desktop instructions.
---

# Install and launch

Choose **V2** for the immersive 3D application or **V1** for the original scientific workbench. Both use the existing Python models. The website itself runs neither simulator in your browser.

## Download the Mac app

Download the [V2.0.0 Apple Silicon desktop ZIP](https://github.com/Maitham16/Artificial_Evolution/releases/tag/v2.0.0), verify its checksums, extract it and move the app to your home **Applications** folder. It requires macOS 14 or later; see [installation and macOS opening instructions](../v2/installation.md#install-a-desktop-zip).

## If the Mac app is already installed

On the prepared Mac, open **Finder → Go → Home → Applications → Artificial Evolution 2.0.app**, or run:

```bash
open "$HOME/Applications/Artificial Evolution 2.0.app"
```

That standalone bundle contains Python, its dependencies and runtime art. Godot and Blender are not needed to open it. A fresh clone does not contain this local build.

## Prepare a source checkout

The commands below use macOS shell paths and the project's Python 3.13 environment. Keep an existing working `.venv` instead of recreating it.

```bash
git clone https://github.com/Maitham16/Artificial_Evolution.git
cd Artificial_Evolution
python3.13 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pip check
```

=== "V2 · 3D Living World"

    Prepare the Mac source toolchain and launch the ground view:

    ```bash
    ./v2/tools/setup_macos.sh
    ./"v2/Run Artificial Evolution 2.command" -- --immersive --ground-view
    ```

    Setup uses Homebrew for missing Godot/Blender installations. Current recorded tools are Godot **4.7.2** and Blender **5.2.3**. Runtime art is already committed; ordinary launches do not require rebuilding animal models.

    [Complete V2 installation and compatibility](../v2/installation.md)

=== "V1 · Original 2D simulator"

    Launch the original Pygame workbench:

    ```bash
    ./.venv/bin/python simulator.py
    ```

    V1 works independently of the 3D application. Its study recipes, controls, datasets and command-line tools remain in the original documentation.

    [Complete V1 user guide](../v1/user-guide.md)

## Build a standalone V2 Mac app

With the source toolchain prepared:

```bash
./v2/tools/build_macos.sh
python3 v2/tools/install_macos.py
open "$HOME/Applications/Artificial Evolution 2.0.app"
```

The current pipeline builds an Apple Silicon application. The package is locally ad-hoc signed, not Apple notarized. Its NumPy wheel requires macOS 14 or later, with complete recorded native validation on the project's macOS 27 / M3 machine. Read [compatibility details](../v2/installation.md#requirements-and-compatibility) before building elsewhere. Intel, Windows and Linux V2 desktop packages are not provided by this pipeline.

!!! info "Which download should I choose?"
    Choose the **V2.0.0 macOS arm64 ZIP** for the standalone 3D app, or the separate **V1.0.1** source/research archives for the original simulator. See [downloads](../downloads.md) for the actual release links and checksums.

## Check your first launch

In V2, wait for **PYTHON ENGINE** and a living population. Choose **Ground**, select an animal, then **Focus** and **Follow**. Open **Research** to inspect settings and **Ecosystem** to read confirmed events.

In V1, the live workbench should show creatures, food, configuration controls and plots. The applications use different shortcuts; follow the guide for the version you opened.

[Your first experiment →](first-experiment.md){ .md-button .md-button--primary }
[Startup help](../v2/troubleshooting.md){ .md-button }
