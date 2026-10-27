# Graph Report - corpus  (2026-10-27)

## Corpus Check
- 97 files · ~132,783 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1742 nodes · 6699 edges · 55 communities (44 shown, 11 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 671 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- test evaluation / experiment evaluation
- test specialization / test parent selection
- test social / social
-  / predator prey
- test simulation / simulation
- brain / test reproduction
-  / compare creatures
- test predator prey / experiment predator prey
- test predator prey / predator prey
- test ecosystem / experiment ecosystem
- research app / test research app
- test obstacles / experiment obstacles
- predator prey / test perception
- test speed / experiment speed
- test comparison / compare creatures
- research session / test research session
- test body traits / experiment traits
- obstacles / test obstacles
- test strategy / experiment strategy
- inspect brains / test brain inspection
- README.md / research catalog
- research session /
- main / plot ecosystem
- body traits / test body traits
- ecosystem / body traits
- creature / social
- USER GUIDE.md / REPRODUCIBILITY.md
- test plot evolution / plot evolution
- test seasons / plot seasons
- test intelligence / analyze intelligence
- test research app / build release
- test speed / test parameters
- test food / food
- test parameters / experiment parameters
- experiment evaluation / experiment strategy
- test selection / selection
- world / perception
- audit evaluation / step27-audit-declared
- test movement / test selection
- test survival / world
- experiment predator prey / body traits
- test brain / test intelligence
- plot selection / plot intelligence
- test evaluation / collision-equivalence-probe
- research session / world
- test reproduction / world
- generation stats / selection
- research catalog / test research app
- test reproduction / reproduction
- test movement
- inspect brains / test brain inspection
- research catalog / validate simulator
- experiment evaluation

## God Nodes (most connected - your core abstractions)
1. `World` - 209 edges
2. `EvolutionSimulation` - 135 edges
3. `NeuralNetwork` - 102 edges
4. `Food` - 85 edges
5. `file_digest()` - 71 edges
6. `initial_conditions_digest()` - 69 edges
7. `PredatorPreyWorld` - 69 edges
8. `bank_digest()` - 67 edges
9. `derived_seed()` - 66 edges
10. `complete_generation()` - 64 edges

## Surprising Connections (you probably didn't know these)
- `load_models()` --uses--> `BodyTraits`  [INFERRED]
  results/step24-initial-attempt/experiment_predator_prey.py → body_traits.py
- `validate_cohorts()` --uses--> `BodyTraits`  [INFERRED]
  results/step24-initial-attempt/experiment_predator_prey.py → body_traits.py
- `PredatorPhysicsTests` --uses--> `BodyTraits`  [INFERRED]
  results/step24-initial-attempt/test_predator_prey.py → body_traits.py
- `PredatorPhysicsTests` --uses--> `WholeGenome`  [INFERRED]
  results/step24-initial-attempt/test_predator_prey.py → body_traits.py
- `PredatorPreyWorld` --uses--> `TraitCreature`  [INFERRED]
  results/step24-initial-attempt/predator_prey.py → body_traits.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Demonstration, engineering and independent-seed evidence** — docs_reproducibility_evidence_boundaries, docs_reproducibility_engineering_validation, docs_reproducibility_published_study_protocols, docs_release_v1_0_0_scientific_record [EXTRACTED 1.00]
- **Configure, export and verify a recorded run** — docs_user_guide_validated_configuration, docs_user_guide_export_bundle, docs_user_guide_verified_replay, docs_reproducibility_deterministic_replay [EXTRACTED 1.00]
- **Reused archived lineages connect diagnostics without adding independent training replications** — readme_study16_speed, readme_study17_strategy, readme_study20_brain_inspection, readme_provenance [EXTRACTED 1.00]
- **Matched parent-choice comparison separates fitness selection from neutral inheritance** — readme_study18_selection, readme_fitness_selection, readme_neutral_inheritance, readme_frozen_evaluation, readme_seed_inference [EXTRACTED 1.00]
- **Seven worlds integrated through validated research session** — research_session, readme_food_seeking, readme_changing_seasons, readme_obstacles_hazards, readme_brains_bodies, readme_predator_prey, readme_social_behavior, readme_continuous_ecosystem [EXTRACTED 1.00]

## Communities (55 total, 11 thin omitted)

### Community 0 - "test evaluation / experiment evaluation"
Cohesion: 0.06
Nodes (37): holm_adjust(), analyze_results(), conditions_for(), effect(), genetic_diversity(), load_raw(), main(), declare() (+29 more)

### Community 1 - "test specialization / test parent selection"
Cohesion: 0.05
Nodes (21): main(), ParentPolicyWorld, RecordedMutationRNG, run_study(), analyze_results(), curriculum(), HabitatWorld, load_models() (+13 more)

### Community 2 - "test social / social"
Cohesion: 0.06
Nodes (23): WholeOffspring, analyze_results(), load_models(), main(), declare(), mean_defined(), observations(), run_study() (+15 more)

### Community 3 - " / predator prey"
Cohesion: 0.09
Nodes (8): validate_mutation_parameters(), create_population(), _reflect_axis(), draw_ecosystem_interface(), first_contact(), reflected_path(), moving_centers(), short_population()

### Community 4 - "test simulation / simulation"
Cohesion: 0.08
Nodes (12): train_lineage(), run_lineage(), save_models(), season_context(), SeasonalWorld, EvolutionSimulation, LineageExtinctionTests, SeasonalHabitatTests (+4 more)

### Community 5 - "brain / test reproduction"
Cohesion: 0.07
Nodes (12): steering_probe(), NeuralNetwork, movement_probe(), decision_effects(), network_details(), NetworkMechanismTests, NeuralNetworkTests, zero_brain() (+4 more)

### Community 6 - " / compare creatures"
Cohesion: 0.14
Nodes (24): run_lineage(), complete_generation(), derived_seed(), genome_digest(), initial_conditions_digest(), positive_integer(), run_seed(), world_for() (+16 more)

### Community 7 - "test predator prey / experiment predator prey"
Cohesion: 0.11
Nodes (24): genome_bank_digest(), shared_layout_digest(), analyze_results(), cohort(), values(), case_name(), checkpoint_generations(), load_models() (+16 more)

### Community 8 - "test predator prey / predator prey"
Cohesion: 0.08
Nodes (10): EcologicalCreature, first_contact(), PredatorPreyWorld, reflected_path(), actor(), PredatorPhysicsTests, stopped_brain(), actor() (+2 more)

### Community 9 - "test ecosystem / experiment ecosystem"
Cohesion: 0.10
Nodes (13): ContinuousSimulation, analyze_results(), load_archive(), load_run(), main(), declare(), run_seed(), run_study() (+5 more)

### Community 10 - "research app / test research app"
Cohesion: 0.13
Nodes (4): args(), family_color(), ResearchApp, WorkbenchTests

### Community 11 - "test obstacles / experiment obstacles"
Cohesion: 0.11
Nodes (24): analyze_results(), load_models(), main(), declare(), observations(), prior_layouts(), run_lineage(), run_study() (+16 more)

### Community 12 - "predator prey / test perception"
Cohesion: 0.07
Nodes (4): sense_food(), EcologicalCreature, PredatorPreyWorld, FoodPerceptionTests

### Community 13 - "test speed / experiment speed"
Cohesion: 0.12
Nodes (16): bank_digest(), load_checkpoint(), save_checkpoint(), analyze_results(), classify_primary(), load_model(), main(), run_lineage() (+8 more)

### Community 14 - "test comparison / compare creatures"
Cohesion: 0.10
Nodes (14): analyze_trials(), main(), paired_summary(), run_experiment(), run_trial(), build_comparison_figure(), main(), save_comparison_plot() (+6 more)

### Community 15 - "research session / test research session"
Cohesion: 0.18
Nodes (5): replay_run(), ResearchSession, RunConfig, ConfigurationTests, ResearchSessionTests

### Community 16 - "test body traits / experiment traits"
Cohesion: 0.13
Nodes (21): analyze_results(), descriptive_mean(), load_models(), main(), declare(), observations(), run_study(), test_bank() (+13 more)

### Community 17 - "obstacles / test obstacles"
Cohesion: 0.10
Nodes (8): Barrier, Danger, layout(), ObstacleCreature, ObstacleWorld, ray_box(), creature(), ObstaclePhysicsTests

### Community 18 - "test strategy / experiment strategy"
Cohesion: 0.11
Nodes (16): pair(), paired_metrics(), analyze_results(), main(), save(), prepare_lineage(), primary_effects(), effect() (+8 more)

### Community 19 - "inspect brains / test brain inspection"
Cohesion: 0.13
Nodes (19): load_unselected(), analyze_results(), descriptive_pair(), load_trace(), main(), declare(), mean_brains(), prior_layouts() (+11 more)

### Community 20 - "README.md / research catalog"
Cohesion: 0.09
Nodes (28): Ancestry and genetic diversity, Brains and bodies world, Changing seasons world, Continuous ecosystem world, Food seeking world, Greedy controller, NeuralNetwork, Obstacles and hazards world (+20 more)

### Community 21 - "research session / "
Cohesion: 0.11
Nodes (14): Research records and export bundles, Artificial Evolution 1.0.1, Automated checks and deterministic replay, build_run_figure(), create_world(), export_bundle(), file_hash(), ForagingWorld (+6 more)

### Community 22 - "main / plot ecosystem"
Cohesion: 0.12
Nodes (19): main(), draw_fitness_panel(), draw_history_panel(), draw_interface(), draw_trend(), main(), mutation_probability(), mutation_scale() (+11 more)

### Community 23 - "body traits / test body traits"
Cohesion: 0.12
Nodes (8): BodyTraits, mutate_body(), reproduce_genomes(), TraitWorld, bank_for(), BodyGeneTests, make_creature(), TraitPhysicsTests

### Community 24 - "ecosystem / body traits"
Cohesion: 0.11
Nodes (8): TraitCreature, WholeGenome, ContinuousCreature, ContinuousWorld, diversity_metrics(), genetic_features(), seed_for(), current_bank()

### Community 26 - "USER GUIDE.md / REPRODUCIBILITY.md"
Cohesion: 0.10
Nodes (22): Steps 13–27 research catalog, Artificial Evolution research workbench, Seven simulation worlds, Version 1.0.1 packaging repair, Observational hazard feedback, Author-run public-download verification, Deterministic Git-based release builder, Recorded-run reproduction (+14 more)

### Community 27 - "test plot evolution / plot evolution"
Cohesion: 0.13
Nodes (8): build_figure(), main(), plot_data(), save_evolution_plot(), FigureTests, PlotCommandTests, sample_report(), short_population()

### Community 28 - "test seasons / plot seasons"
Cohesion: 0.15
Nodes (16): analyze_results(), load_models(), main(), declare(), run_study(), validate_lineage(), build_study_figure(), finish_figure() (+8 more)

### Community 29 - "test intelligence / analyze intelligence"
Cohesion: 0.11
Nodes (11): analyze_results(), effect(), main(), primary_decisions(), run_study(), build_intelligence_figure(), save_intelligence_plot(), FrozenArchiveTests (+3 more)

### Community 30 - "test research app / build release"
Cohesion: 0.11
Nodes (7): build_release(), git(), main(), source_member(), main(), main(), ReleaseAndCliTests

### Community 31 - "test speed / test parameters"
Cohesion: 0.12
Nodes (4): NeuralControlTests, PopulationParameterTests, FixedSpeedTests, World

### Community 32 - "test food / food"
Cohesion: 0.13
Nodes (6): Food, FoodTests, still_creature(), world_state(), ObservationTests, ProbeTests

### Community 33 - "test parameters / experiment parameters"
Cohesion: 0.14
Nodes (9): analyze_sweep(), describe_pairs(), make_settings(), run_sweep(), Setting, build_parameter_figure(), save_parameter_plot(), ParameterStudyTests (+1 more)

### Community 34 - "experiment evaluation / experiment strategy"
Cohesion: 0.17
Nodes (18): file_digest(), analyze_results(), conditions_for(), effect(), genetic_diversity(), individual_records(), load_raw(), main() (+10 more)

### Community 35 - "test selection / selection"
Cohesion: 0.16
Nodes (5): evaluate_population(), fitness_score(), FitnessTests, make_creature(), PopulationEvaluationTests

### Community 37 - "audit evaluation / step27-audit-declared"
Cohesion: 0.21
Nodes (13): audit(), check_family(), independent_sign(), main(), individual_records(), audit(), check_family(), independent_sign() (+5 more)

### Community 38 - "test movement / test selection"
Cohesion: 0.18
Nodes (4): population_state(), WorldMovementTests, SurvivalRateTests, WorldSelectionTests

### Community 39 - "test survival / world"
Cohesion: 0.16
Nodes (3): CreatureSurvivalTests, make_creature(), WorldSurvivalTests

### Community 40 - "experiment predator prey / body traits"
Cohesion: 0.23
Nodes (15): analyze_results(), cohort(), values(), case_name(), checkpoint_generations(), current_bank(), load_models(), main() (+7 more)

### Community 41 - "test brain / test intelligence"
Cohesion: 0.15
Nodes (3): food_inputs_for_control(), SensoryInputTests, FoodInterventionTests

### Community 42 - "plot selection / plot intelligence"
Cohesion: 0.19
Nodes (6): draw_effect(), main(), main(), build_selection_figure(), main(), save_selection_plot()

### Community 43 - "test evaluation / collision-equivalence-probe"
Cohesion: 0.22
Nodes (3): EvaluationWorld, FastWorld, CollisionExecutionTests

### Community 46 - "generation stats / selection"
Cohesion: 0.21
Nodes (3): GenerationStats, FitnessEntry, FitnessEvaluation

### Community 48 - "test reproduction / reproduction"
Cohesion: 0.29
Nodes (3): OffspringBrain, reproduce_brains(), BreedingTests

## Knowledge Gaps
- **6 isolated node(s):** `Random movement controller`, `Greedy controller`, `Step 14: experiment_parameters.py`, `Version 1.0.1 packaging repair`, `Observational hazard feedback` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 314 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `World` connect `test speed / test parameters` to `test evaluation / experiment evaluation`, `test specialization / test parent selection`, ` / predator prey`, `test simulation / simulation`, ` / compare creatures`, `test predator prey / experiment predator prey`, `test speed / experiment speed`, `test comparison / compare creatures`, `obstacles / test obstacles`, `test strategy / experiment strategy`, `inspect brains / test brain inspection`, `research session / `, `main / plot ecosystem`, `body traits / test body traits`, `creature / social`, `test plot evolution / plot evolution`, `test seasons / plot seasons`, `test food / food`, `experiment evaluation / experiment strategy`, `test selection / selection`, `world / perception`, `audit evaluation / step27-audit-declared`, `test movement / test selection`, `test survival / world`, `test brain / test intelligence`, `test evaluation / collision-equivalence-probe`, `research session / world`, `test reproduction / world`, `generation stats / selection`, `test reproduction / reproduction`, `inspect brains / test brain inspection`?**
  _High betweenness centrality (0.161) - this node is a cross-community bridge._
- **Are the 40 inferred relationships involving `World` (e.g. with `initial_conditions_digest()` and `draw_fitness_panel()`) actually correct?**
  _`World` has 40 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Random movement controller`, `Greedy controller`, `Step 14: experiment_parameters.py` to the rest of the system?**
  _6 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test evaluation / experiment evaluation` be split into smaller, more focused modules?**
  _Cohesion score 0.05956112852664577 - nodes in this community are weakly interconnected._
- **Why does `NeuralNetwork` connect `brain / test reproduction` to `test evaluation / experiment evaluation`, `test specialization / test parent selection`, `test social / social`, ` / predator prey`, ` / compare creatures`, `test predator prey / experiment predator prey`, `test predator prey / predator prey`, `test ecosystem / experiment ecosystem`, `test obstacles / experiment obstacles`, `predator prey / test perception`, `test speed / experiment speed`, `test body traits / experiment traits`, `obstacles / test obstacles`, `test strategy / experiment strategy`, `inspect brains / test brain inspection`, `body traits / test body traits`, `ecosystem / body traits`, `creature / social`, `test seasons / plot seasons`, `test speed / test parameters`, `test food / food`, `test parameters / experiment parameters`, `world / perception`, `experiment predator prey / body traits`, `test reproduction / reproduction`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `EvolutionSimulation` (e.g. with `complete_generation()` and `draw_fitness_panel()`) actually correct?**
  _`EvolutionSimulation` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Should `test specialization / test parent selection` be split into smaller, more focused modules?**
  _Cohesion score 0.05225225225225225 - nodes in this community are weakly interconnected._

Inspection scope: all tracked Python source and Markdown documentation. Generated datasets were inventoried separately. Host did not expose agent token usage; zero token counters are placeholders, not measured usage. The scan used read-only copies to preserve original files.
