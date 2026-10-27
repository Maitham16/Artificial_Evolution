extends RefCounted
const Sim=preload("res://scripts/simulation.gd")
const Exporter=preload("res://scripts/exporter.gd")
const POLICIES=["current","random","greedy","founder"]
var settings: Dictionary
var current_bank: Array
var founder_bank: Array
var phase: int = 0
var model
var rows: Array=[]
var starts: Dictionary={}
var complete: bool=false
var cancelled: bool=false
var output_path: String=""
var output_root: String="user://transfer-checks"

func _init(live, destination: String="user://transfer-checks") -> void:
	output_root=destination
	settings=live.config.duplicate(true)
	current_bank=live.brain_bank()
	founder_bank=[]
	for brain in live.founders:founder_bank.append(brain.copy())
	_begin()

func _begin() -> void:
	if phase>=12:complete=true;_save();return
	var config=settings.duplicate(true)
	config.seed=(str(settings.seed)+":transfer:"+str(phase/4)).hash() & 0x7fffffff
	config.generation_limit=1
	var policy=POLICIES[phase%4]
	config.algorithm=policy if policy in ["random","greedy"] else "selection"
	model=Sim.new(config)
	var bank=founder_bank if policy in ["founder","random","greedy"] else current_bank
	for i in range(model.agents.size()):model.agents[i].brain=bank[i].copy()
	var physical=[]
	for c in model.agents:physical.append([c.position,c.heading,c.lifespan])
	physical.append(model.food.duplicate())
	var digest=var_to_bytes(physical).hex_encode().sha256_text()
	var repeat=phase/4
	if starts.has(repeat):assert(starts[repeat]==digest,"Transfer worlds must share physical starts")
	else:starts[repeat]=digest

func work(budget_usec: int=5000) -> void:
	if complete or cancelled:return
	var start=Time.get_ticks_usec()
	while Time.get_ticks_usec()-start<budget_usec and not complete and not cancelled:
		if model.ticks<1800 and not model.finished:model.step()
		else:
			var m=model.metrics()
			rows.append({"repeat":phase/4+1,"seed":model.config.seed,"policy":POLICIES[phase%4],
				"mean_fitness":m.mean_fitness,"mean_meals":m.mean_meals,"survival_at_30s":float(m.alive)/model.agents.size(),
				"observed_ticks":model.ticks,"declared_horizon_seconds":30,"population":model.agents.size(),"physical_start_sha256":starts[phase/4]})
			phase+=1;_begin()

func cancel() -> void:
	cancelled=true;_save()

func progress() -> float:
	return minf(1.0,(phase+float(model.ticks)/1800.0)/12.0)

func _save() -> void:
	var root=output_root.path_join("check-%s-%d") % [Time.get_datetime_string_from_system().replace(":","-"),Time.get_ticks_usec()]
	DirAccess.make_dir_recursive_absolute(root)
	var data={"schema_version":1,"status":"cancelled" if cancelled else "complete","application_version":Sim.VERSION,
		"live_config":settings,"matched_layout_repeats":3,"test_horizon_seconds":30,"rows":rows,
		"interpretation":"Descriptive frozen-population transfer check. Current and founder genomes are copied, including every birth slot. Layout repeats are not independent training replications. No within-test training; all policies have identical speed and initial physical conditions. Lifetimes alive at 30 seconds are censored. All-dead cohorts stop earlier with survival at 30 seconds equal to zero."}
	Exporter._write(root.path_join("check.json"),JSON.stringify(data,"\t",true,true)+"\n")
	var csv=Exporter.csv_row(["repeat","seed","policy","mean_fitness","mean_meals","survival_at_30s","observed_ticks"])
	for row in rows:csv+=Exporter.csv_row([row.repeat,row.seed,row.policy,row.mean_fitness,row.mean_meals,row.survival_at_30s,row.observed_ticks])
	Exporter._write(root.path_join("check.csv"),csv)
	output_path=ProjectSettings.globalize_path(root)
