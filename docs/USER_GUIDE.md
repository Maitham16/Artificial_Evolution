# Artificial Evolution 1.0.1 — user guide

The research workbench brings the seven simulation modes and the studies from
Steps 13–27 into one Pygame application. Its live displays describe one run;
the Research panel provides the independent-seed experiments used for inference.

## Install and launch

Use Python 3.13. From a Git checkout or the extracted source release:

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python simulator.py
```

An existing prepared checkout only needs the last two commands appropriate to
its installed environment: activate `.venv`, then run `python simulator.py`.
The original `main.py` viewer and all earlier experiment interfaces retain their
published source versions and commands.

The release has two ZIP assets with the same `Artificial_Evolution-v1.0.1/`
prefix. The **source** asset contains the application, presets, guides, current
demonstration figures, and Step 27's published summary/figures. The optional
**research** asset adds all earlier datasets, trained populations, and raw
histories. Extract both into the same parent directory to combine them:

```sh
unzip Artificial_Evolution-v1.0.1-source.zip
unzip -n Artificial_Evolution-v1.0.1-research.zip
cd Artificial_Evolution-v1.0.1
```

Steps 17, 20, and 27 use previously trained populations. Their Run button becomes
available when those inputs are installed. Other studies can train new models.
Each ZIP contains a Git-commit and file-hash manifest; `SHA256SUMS.txt` contains
the archive checksums. With both assets downloaded, verify them using:

```sh
shasum -a 256 -c SHA256SUMS.txt
```

## Choose a world and algorithm

| World | Available algorithms | Environment controls |
| --- | --- | --- |
| Food seeking | Fitness selection, neutral inheritance, random, greedy, frozen founders | Uniform, clustered, sparse, wide clustered, or barren |
| Changing seasons | Fitness selection with maturity eligibility | Seasonal stock and cluster movement |
| Obstacles & hazards | Fitness selection, random, greedy | Five food environments, with barriers and dangerous regions |
| Brains & bodies | Joint neural/body selection | Five food environments; inherited speed, size, and sensory range |
| Predator & prey | Simultaneous selection in two gene pools | Five food environments, opponent sensors, predator count |
| Social behavior | Group or individual survival | Uniform, sparse, or barren stock; groups, access, signaling, sharing |
| Continuous ecosystem | Funded or clonal reproduction | Five environments, finite regrowth, energy-funded births, population cap |

Edit the left panel, then press **Apply / new run**. A new world is constructed
and validated before replacing the current run. The previous run exports in the
background. Invalid settings leave the current simulation available for use.

**All settings / import** exposes mode-specific parameters. Type a preset or
exported `config.json` path in the import field and select **Load**, then Apply.
An empty food-stock field uses the environment default. Seasons use the four
seasonal counts. Clonal reproduction forces both mutation probabilities to zero;
social studies hold body traits fixed. Population/group divisibility is checked.

Neutral inheritance samples parents uniformly from every completed lifetime,
including early deaths. It retains the selection arm's mutation and parent
bottleneck. Frozen founders replay the original controllers in fresh cohorts.
Random/greedy controllers carry unused placeholder neural arrays, which are
excluded from the live neural-diversity metric.

## Observe and control the run

| Control | Action |
| --- | --- |
| Space | Pause or resume |
| S | Cycle the target speed through 1×, 5×, 20× |
| A | Toggle automatic cohort breeding, or continuous births |
| N | Advance a completed generational cohort manually |
| R | Restart the current configuration and seed, archiving the old run |
| E | Export the current run |
| L | Open the ancestry view |
| B | Open the Research panel |
| H | Open help |
| Escape | Close a panel or exit the application |

Typing in a field takes priority over shortcuts. Enter finishes editing; Apply
starts the configured run. Ctrl/Cmd+A selects the field's current text.

The world view shows live population, food, founder-family rings, earned fitness,
and sampled time curves. Click a creature for its parent, root family, energy,
inherited dimensions, and eight hidden-neuron activations. Activations are a
**preview at the current state**, rather than a recording of the preceding tick.

In **Obstacles & hazards**, the red circles are dangerous areas creatures can
cross. Overlapping a zone costs an additional **12 energy per second** and
**5 fitness per second**. Labels show the current exposed population, and exposed
creatures have red warning rings. Click a zone or its label to inspect its rules;
click a creature to see its total energy drain, hazard energy loss, and exposure
time. A red energy bar marks active exposure. Eating can replenish energy while
hazard costs continue to apply. These displays observe the existing damage rules.

Lineages shows every observed birth/parent edge, including extinct branches,
and the largest living families. Generation and creature ID jointly identify
generational actors; continuous actors have globally unique birth IDs. Founder
families are genealogical labels, not inferred species.

Target speed is a playback request. The measured rate reports actual simulated
seconds per wall-clock second. Rendering has a bounded tick workload so controls
remain responsive. Every completed physics step still uses 1/60 second; no
movement or survival ticks are skipped to meet a target rate.

## Interpret the measurements

- In generational modes, the displayed mean includes the current cohort's live
  and dead actors and resets at a cohort boundary. Finished-generation statistics
  are retained separately in the exported canonical report.
- In continuous mode, mean earned fitness averages every recorded lifetime;
  living-only fitness is also exported. Reproduction pays for offspring energy.
- Predator fitness and prey fitness remain separate. The main fitness curve
  refers to prey. Social fitness is survival age, with group/individual selection
  following the underlying social model.
- `individuals.csv` records biological `alive`/death state and cohort retirement.
  Its `censored` flag marks a cohort ending with a living survivor.
  `telemetry.csv:right_censored` identifies all living observations, including a
  continuous run stopped at its horizon. Missing mode-specific values are empty.
- Neural RMS is a raw per-parameter pair-distance summary of the living neural
  controllers. It excludes body genes and is neither functional intelligence
  nor a standardized comparison between different brain architectures.

The status distinguishes a completed budget from a lineage extinction. A finished
predator/social episode may retain living, censored actors. Generational
replacement introduces a new cohort; its counts do not represent continuous
demographic births. Use Continuous ecosystem to study overlapping lifetimes.

## Export and replay

Exports and automatic archives appear in a fresh subfolder under `exports/`.
The export worker receives an immutable snapshot while the live run continues.
**Open last report** opens the local HTML report once the bundle is ready.

| File | Contents |
| --- | --- |
| `config.json` | Versioned, complete experiment configuration |
| `run.json` | Configuration, controls by tick, canonical mode report, metrics, ancestry, runtime, source hashes |
| `population.csv` | Sampled live population, cohort fitness, food, family counts, neural RMS, and separate predator fitness |
| `individuals.csv` | Every observed lifetime, parent/root, initial state, genotype hash, last state, and cohort censoring |
| `telemetry.csv` | Body energy accounts, collisions/hazards, captures, social signals/transfers, reproduction, censoring |
| `lineage.csv` | Complete parent/root/depth and birth/cohort-end table |
| `generations.csv` | Completed canonical generation statistics |
| `genomes.npz` | Numeric parameters for every observed birth, body vectors and presence flags; load with `allow_pickle=False` |
| `population.png/.svg/.pdf` | Four-panel scientific figure |
| `application.png` | Current application view, when exported by the GUI |
| `report.html` | Local browser report with relative artifact links |
| `manifest.json` | SHA-256 hashes of the bundle files |

Example commands, using new output directories:

```sh
python simulator.py --config configs/continuous.json
python simulator.py --headless --config configs/neutral.json --ticks 1200 --export-root exports/headless
python simulator.py --verify-bundle exports/PATH/TO/run-folder
python simulator.py --replay exports/PATH/TO/run-folder/run.json --headless
```

Replay reconstructs the configuration, every physics tick, and semantic controls,
then compares the metrics, lifetimes, canonical report, and available telemetry.
The numeric archive records birth genomes. Omit `--headless` from replay to open
the verified state paused, then use Space to continue when its budget remains.
Keep the bundle together to use its HTML links and verify its hashes.

## Run the research studies

Select **Research**, choose a step with the arrows, and browse its published
figure inside the application or open its data. **Run full study** launches the
original script with its full seed/training budget. Workers are independently
selectable. Live-world settings do not override a published scientific protocol.

The new study folder contains `job.json`, the exact command, source hashes,
progress log, output data, and generated figure. A successful study is followed
by its plotter; both must succeed before the job reports completion. Cancel
stops the owned process group and retains partial records. Closing the workbench
cancels an active study and waits for pending run exports.

```sh
python simulator.py --catalog
python simulator.py --study 27 --workers 8 --export-root exports/research
```

Full studies can take substantial time. The independent-seed confidence intervals
and corrected tests belong to those studies; a live demonstration alone does not
establish an evolutionary advantage. See [reproducibility](REPRODUCIBILITY.md) and
the Step 27 results in the main README for the measured successes and failures.
