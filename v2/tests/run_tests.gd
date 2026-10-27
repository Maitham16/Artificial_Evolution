extends SceneTree
const Brain = preload("res://scripts/brain.gd")
const Benchmark = preload("res://scripts/benchmark.gd")
const Sim = preload("res://scripts/simulation.gd")
const Exporter = preload("res://scripts/exporter.gd")
var checks = 0
var failures = 0

func _initialize():call_deferred("_run")

func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		printerr("FAIL: " + message)

func settings(changes: Dictionary = {}) -> Dictionary:
	var result = Sim.defaults()
	result.population = 6
	result.food_count = 12
	result.merge(changes,true)
	return result

func _run() -> void:
	var rng = RandomNumberGenerator.new();rng.seed = 42
	var brain = Brain.create(rng)
	check(brain.weights.size()==90,"8–8–2 architecture has 90 parameters")
	check(Brain.create(rng,16).weights.size()==154,"Hazard brain includes risk inputs")
	var copy = brain.copy();copy.weights[0] += 1
	check(copy.weights[0]!=brain.weights[0],"Brain clones are independent")
	check(brain.mutated(rng,0,1).weights==brain.weights,"Zero mutation preserves genomes")
	check(brain.mutated(rng,1,.2).weights!=brain.weights,"Mutation changes inherited weights")
	copy.weights.fill(0)
	check(copy.forward(PackedFloat64Array([0,0,0,0,1,1,1,1]))==PackedFloat64Array([0,0]),"Zero weights produce neutral actions")
	var a = Sim.new(settings());var b = Sim.new(settings())
	for i in range(180):a.step();b.step()
	check(a.snapshot()==b.snapshot(),"Seeded physics is deterministic")
	var baseline = Sim.new(settings({"algorithm":"random"}))
	var greedy = Sim.new(settings({"algorithm":"greedy"}))
	var neural = Sim.new(settings())
	check(baseline.food==greedy.food and baseline.food==neural.food,"All controllers share seeded food starts")
	for i in range(neural.agents.size()):
		check(neural.agents[i].position==baseline.agents[i].position and neural.agents[i].lifespan==greedy.agents[i].lifespan,"All controllers share physical starts")
	var c = neural.agents[0]
	c.position=Vector2.ZERO;c.heading=0
	neural.food=[Vector2(3,0)]
	var sensed=neural.sensors(c)
	check(sensed[2]==1 and sensed[1]==0 and is_equal_approx(sensed[0],.625),"Local food sensors encode distance and bearing")
	neural.food=[Vector2(15,0)]
	check(neural.sensors(c)[2]==0,"Food beyond sensory range is invisible")
	var meal=Sim.new(settings({"food_count":1}))
	var eater=meal.agents[0];eater.position=Vector2.ZERO;eater.heading=0;eater.energy=20;eater.brain.weights.fill(0)
	meal.food=[Vector2(Sim.SPEED*Sim.STEP,0)]
	meal.step()
	check(eater.meals==1 and abs(eater.energy-(40.0-5.0*Sim.STEP))<1e-9,"Contact consumes food and restores energy after movement")
	check(meal.food.size()==1,"Consumed food is replenished")
	eater.position=Vector2(Sim.HALF.x-Sim.RADIUS-.01,0);eater.heading=0
	meal.step()
	check(eater.position.x<=Sim.HALF.x-Sim.RADIUS and cos(eater.heading)<0,"Arena boundary reflects heading and preserves body bounds")
	var risk=Sim.new(settings({"environment":"hazards","food_count":0}))
	c=risk.agents[0];c.position=risk.hazards[0].position;c.heading=0;c.brain.weights.fill(0)
	for i in range(30):risk.step()
	check(abs(c.energy-91.5)<.000001 and abs(c.hazard_loss-6)<.000001,"Hazards consume 12 extra energy per lived second")
	var wall=Sim.new(settings({"environment":"hazards","food_count":0}))
	var collider=wall.agents[0];collider.position=Vector2(-10.37,0);collider.heading=0;collider.brain.weights.fill(0)
	wall.step()
	check(collider.collisions==1 and abs(collider.energy-(98.0-5.0*Sim.STEP))<1e-9,"Barrier contact reflects and charges collision energy")
	check(risk.sensors(c).size()==16,"Hazard sensors have the required input size")
	var barren=Sim.new(settings({"food_count":0,"generation_limit":2,"mutation_rate":0}))
	for i in range(1250):barren.step()
	check(barren.generation==2 and barren.archived.size()==6,"Completed cohorts reproduce and retain all lifetimes")
	check(barren.agents[0].parent.begins_with("g1:"),"Offspring carry parent ancestry")
	check(barren.history.size()==1,"History only records completed generations")
	var selected=Sim.new(settings({"population":20,"mutation_rate":0}))
	var neutral=Sim.new(settings({"population":20,"algorithm":"neutral","mutation_rate":0}))
	for model in [selected,neutral]:
		for i in range(model.agents.size()):model.agents[i].fitness=float(i);model.agents[i].alive=false
		model._finish_generation();model.advance_generation()
	var neutral_outside_top=false
	for child in selected.agents:check(int(child.parent.get_slice("c",1))>=17,"Selection samples the top 20 percent")
	for child in neutral.agents:
		if int(child.parent.get_slice("c",1))<17:neutral_outside_top=true
	check(neutral_outside_top,"Neutral reproduction samples all completed lifetimes")
	var treatment=Sim.new(settings({"population":20,"mutation_rate":.2}))
	var drift=Sim.new(settings({"population":20,"algorithm":"neutral","mutation_rate":.2}))
	for experiment in [treatment,drift]:
		for i in range(experiment.agents.size()):
			experiment.agents[i].brain.weights.fill(0);experiment.agents[i].fitness=float(i);experiment.agents[i].alive=false
		experiment._finish_generation();experiment.advance_generation()
	for i in range(20):check(treatment.agents[i].brain.weights==drift.agents[i].brain.weights,"Selection and drift share mutation draws independently of parent sampling")
	var negative=Sim.new(settings())
	for actor in negative.agents:actor.fitness=-3.0;actor.alive=false
	negative._finish_generation()
	check(negative.history[0].best_fitness==-3.0,"Negative fitness is not clipped in generation summaries")
	check(not Sim.validate(settings({"schema_version":"1"})).is_empty(),"Configuration schema must be numeric version one")
	check(not Sim.validate(settings({"schema_version":1.5})).is_empty(),"Fractional schema versions are rejected")
	var bad=settings({"population":-1});check(not Sim.validate(bad).is_empty(),"Invalid populations are rejected")
	bad=settings({"mutation_rate":NAN});check(not Sim.validate(bad).is_empty(),"Nonfinite mutation is rejected")
	var root="user://test-export-%d" % Time.get_ticks_usec()
	var exported=Exporter.export_run(a,root)
	check(not exported.is_empty(),"Export writes a new immutable bundle")
	var verified=Exporter.verify_bundle(root)
	check(verified.ok,"Exported state replays exactly after JSON round trip: " + str(verified.get("error","")))
	check(Exporter.export_run(a,root).is_empty(),"Existing exports are never overwritten")
	var f=FileAccess.open(root.path_join("individuals.csv"),FileAccess.WRITE);f.store_string("tampered");f.close()
	check(not Exporter.verify_bundle(root,false).ok,"Manifest verification rejects tampered datasets")
	for habitat in Sim.ENVIRONMENTS:
		var habitat_model=Sim.new(settings({"population":4,"food_count":8,"environment":habitat}))
		for tick in range(90):habitat_model.step()
		var path="user://test-habitat-%s-%d" % [habitat,Time.get_ticks_usec()]
		Exporter.export_run(habitat_model,path)
		check(Exporter.verify_bundle(path).ok,"Every habitat exports and replays: "+habitat)
	var live=Sim.new(settings({"population":4,"food_count":8}))
	for i in range(120):live.step()
	var before=live.snapshot()
	var job=Benchmark.new(live,"user://tests/transfer-checks")
	while not job.complete:job.work(50000)
	check(job.rows.size()==12,"Transfer check retains every matched condition")
	check(live.snapshot()==before,"Transfer evaluation never mutates the live population")
	for repeat_index in range(3):
		var left=job.rows[repeat_index*4];var right=job.rows[repeat_index*4+3]
		check(left.mean_fitness==right.mean_fitness and left.mean_meals==right.mean_meals,"Identical current/founder brains are a positive-control match")
	var cancelled=Benchmark.new(live,"user://tests/transfer-checks");cancelled.cancel()
	check(cancelled.cancelled and FileAccess.file_exists(cancelled.output_path.path_join("check.json")),"Cancelled comparisons preserve partial records")
	print("AE2_TEST_RESULT ",JSON.stringify({"checks":checks,"failures":failures,"engine":Engine.get_version_info().string}))
	quit(0 if failures==0 else 1)
