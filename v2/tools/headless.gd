extends SceneTree
const Sim=preload("res://scripts/simulation.gd")
const Exporter=preload("res://scripts/exporter.gd")
func _initialize():call_deferred("_run")
func _run() -> void:
	var options={}
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--") and "=" in arg:
			var index=arg.find("=");options[arg.substr(2,index-2)]=arg.substr(index+1)
	if options.has("verify") or options.has("replay"):
		var replay=options.has("replay")
		var result=Exporter.verify_bundle(options.get("replay",options.get("verify","")),replay)
		result.erase("report")
		print(JSON.stringify(result));quit(0 if result.ok else 1);return
	var config=Sim.defaults()
	if options.has("config"):
		var loaded=JSON.parse_string(FileAccess.get_file_as_string(options.config))
		if not loaded is Dictionary:printerr("Invalid JSON configuration.");quit(2);return
		config=loaded
	for key in ["seed","population","food_count","generation_limit"]:
		if options.has(key):
			if not str(options[key]).is_valid_int():printerr(key+" must be an integer");quit(2);return
			config[key]=int(options[key])
	for key in ["mutation_rate","mutation_scale"]:
		if options.has(key):
			if not str(options[key]).is_valid_float():printerr(key+" must be numeric");quit(2);return
			config[key]=float(options[key])
	for key in ["algorithm","environment"]:
		if options.has(key):config[key]=options[key]
	var error=Sim.validate(config)
	if not error.is_empty():printerr(error);quit(2);return
	var ticks=int(options.get("ticks","600"))
	if ticks<0 or ticks>720000:printerr("Tick budget must be 0–720000.");quit(2);return
	var model=Sim.new(config)
	for i in range(ticks):
		if not model.step():break
	var destination=Exporter.export_run(model,options.get("out",""))
	if destination.is_empty():printerr("Use a new writable export directory.");quit(2);return
	var check=Exporter.verify_bundle(destination)
	print(JSON.stringify({"ok":check.ok,"version":Sim.VERSION,"ticks":model.ticks,"bundle":destination,"metrics":model.metrics()}))
	quit(0 if check.ok else 1)
