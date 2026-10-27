extends RefCounted
const Sim = preload("res://scripts/simulation.gd")

static func _write(path: String, content: String) -> bool:
	var file = FileAccess.open(path,FileAccess.WRITE)
	if file == null:return false
	file.store_string(content)
	file.flush()
	var ok = file.get_error() == OK
	file.close()
	return ok

static func csv_row(values: Array) -> String:
	var fields = PackedStringArray()
	for value in values:
		var text = str(value).replace('"','""')
		fields.append('"' + text + '"')
	return ",".join(fields) + "\n"

static func export_run(sim, destination: String = "", screenshot: Image = null) -> String:
	var root = destination
	if root.is_empty():root = "user://runs/run-%s-%d" % [Time.get_datetime_string_from_system().replace(":","-"),Time.get_ticks_usec()]
	if DirAccess.dir_exists_absolute(root):return ""
	var destination_root = root
	root += ".pending"
	if DirAccess.dir_exists_absolute(root):return ""
	if DirAccess.make_dir_recursive_absolute(root) != OK:return ""
	var report = sim.snapshot()
	var binary = FileAccess.open(root.path_join("state.bin"),FileAccess.WRITE)
	if binary == null:return ""
	binary.store_var(report,false)
	binary.close()
	_write(root.path_join("run.json"),JSON.stringify(report,"\t",true,true)+"\n")
	_write(root.path_join("config.json"),JSON.stringify(sim.config,"\t",true,true)+"\n")
	var people = csv_row(["id","x","z","age","energy","meals","fitness","alive","right_censored","death_cause","parent","root","depth","hazard_seconds","hazard_loss","collisions"])
	var lineage = csv_row(["id","parent","root","depth"])
	for c in report.individuals:
		people += csv_row([c.id,c.x,c.z,c.age,c.energy,c.meals,c.fitness,c.alive,c.right_censored,c.cause,c.parent,c.root,c.depth,c.hazard_seconds,c.hazard_loss,c.collisions])
		lineage += csv_row([c.id,c.parent,c.root,c.depth])
	_write(root.path_join("individuals.csv"),people)
	_write(root.path_join("lineage.csv"),lineage)
	var populations = csv_row(["time","generation","alive","food","families","mean_fitness","mean_meals"])
	for row in report.samples:populations += csv_row([row.time,row.generation,row.alive,row.food,row.families,row.mean_fitness,row.mean_meals])
	_write(root.path_join("population.csv"),populations)
	var generations = csv_row(["generation","mean_fitness","best_fitness","mean_meals","survival_60s","duration"])
	for row in report.generations:generations += csv_row([row.generation,row.mean_fitness,row.best_fitness,row.mean_meals,row.survival_60s,row.duration])
	_write(root.path_join("generations.csv"),generations)
	_write(root.path_join("fitness.svg"),_svg(report))
	_write(root.path_join("report.html"),"<!doctype html><meta charset='utf-8'><title>Artificial Evolution 2.0</title><style>body{font:16px system-ui;background:#102126;color:#e7ece2;max-width:1000px;margin:4rem auto}a{color:#a2dfb5}img{width:100%%}</style><h1>Artificial Evolution 2.0</h1><p>Seed %s · %s · %s · %d ticks</p><p>One seeded demonstration. 3D ground-plane model; not a replication of the Python research studies.</p><img src='fitness.svg'><p><a href='run.json'>Full state and birth genomes</a> · <a href='config.json'>Configuration</a> · <a href='individuals.csv'>Lifetimes</a> · <a href='lineage.csv'>Ancestry</a></p>" % [sim.config.seed,sim.config.environment,sim.config.algorithm,sim.ticks])
	if screenshot != null:screenshot.save_png(root.path_join("application.png"))
	var hashes = {}
	for name in ["run.json","state.bin","config.json","individuals.csv","lineage.csv","population.csv","generations.csv","fitness.svg","report.html"]:
		hashes[name] = FileAccess.get_sha256(root.path_join(name))
	if screenshot != null:hashes["application.png"] = FileAccess.get_sha256(root.path_join("application.png"))
	_write(root.path_join("manifest.json"),JSON.stringify({"schema_version":1,"application_version":Sim.VERSION,"files_sha256":hashes},"\t",true,true)+"\n")
	if not verify_bundle(root,false).ok:return ""
	if DirAccess.rename_absolute(root,destination_root) != OK:return ""
	return ProjectSettings.globalize_path(destination_root)

static func _svg(report: Dictionary) -> String:
	var rows: Array = report.samples
	var points = PackedStringArray()
	var high = 1.0;var low = 0.0;var last_time=1.0
	for row in rows:
		high=maxf(high,row.mean_fitness);low=minf(low,row.mean_fitness);last_time=maxf(last_time,row.time)
	for i in range(rows.size()):
		points.append("%.2f,%.2f" % [50+float(rows[i].time)/last_time*820,300-(float(rows[i].mean_fitness)-low)/(high-low)*230])
	return '<svg xmlns="http://www.w3.org/2000/svg" width="920" height="360" viewBox="0 0 920 360"><rect width="920" height="360" fill="#182f32"/><text x="50" y="35" fill="#ecf1e7" font-family="sans-serif" font-size="20">Cohort mean earned fitness / simulated time</text><path d="M50 70V300H875" fill="none" stroke="#657b78"/><polyline points="%s" fill="none" stroke="#a3deb6" stroke-width="3"/><text x="50" y="335" fill="#b3c3b7" font-family="sans-serif" font-size="13">Fitness resets each generation. One run; descriptive observations only.</text></svg>' % " ".join(points)

static func verify_bundle(root: String, replay: bool = true) -> Dictionary:
	var manifest = JSON.parse_string(FileAccess.get_file_as_string(root.path_join("manifest.json")))
	if not manifest is Dictionary:return {"ok":false,"error":"Invalid manifest"}
	var required = ["run.json","state.bin","config.json","individuals.csv","lineage.csv","population.csv","generations.csv","fitness.svg","report.html"]
	for name in required:
		if not manifest.get("files_sha256",{}).has(name):return {"ok":false,"error":"Incomplete manifest"}
	for name in manifest.files_sha256:
		if name != str(name).get_file():return {"ok":false,"error":"Unsafe manifest path"}
		if FileAccess.get_sha256(root.path_join(name)) != manifest.files_sha256[name]:return {"ok":false,"error":"Checksum mismatch: " + str(name)}
	var readable = JSON.parse_string(FileAccess.get_file_as_string(root.path_join("run.json")))
	var binary = FileAccess.open(root.path_join("state.bin"),FileAccess.READ)
	var report = binary.get_var(false)
	if not report is Dictionary or not Sim.validate(report.get("config",{})).is_empty():return {"ok":false,"error":"Invalid run configuration"}
	if not _json_equivalent(report,readable):return {"ok":false,"error":"Readable JSON differs from lossless state"}
	if not _json_equivalent(report.config,JSON.parse_string(FileAccess.get_file_as_string(root.path_join("config.json")))):return {"ok":false,"error":"Configuration differs from saved state"}
	if report.ticks < 0 or report.ticks > int(report.config.generation_limit)*7201:return {"ok":false,"error":"Invalid tick horizon"}
	if replay:
		var model = Sim.new(report.config)
		for i in range(int(report.ticks)):
			if not model.step():return {"ok":false,"error":"Replay ended early"}
		if not _equal(model.snapshot(),report):return {"ok":false,"error":"Replay state differs: " + first_difference(model.snapshot(),report)}
	return {"ok":true,"ticks":report.ticks,"report":report}

static func _equal(a, b) -> bool:
	if (a is float or a is int) and (b is float or b is int):return a == b
	if a is Dictionary and b is Dictionary:
		if a.size() != b.size():return false
		for k in a:
			if not b.has(k) or not _equal(a[k],b[k]):return false
		return true
	if a is Array and b is Array:
		if a.size()!=b.size():return false
		for i in range(a.size()):
			if not _equal(a[i],b[i]):return false
		return true
	return a == b

static func first_difference(a, b, path: String = "state") -> String:
	if (a is float or a is int) and (b is float or b is int):
		return "" if a == b else path + ": " + str(a) + " versus " + str(b)
	if a is Dictionary and b is Dictionary:
		for k in a:
			if not b.has(k):return path + "." + str(k) + " missing"
			var d = first_difference(a[k],b[k],path + "." + str(k))
			if not d.is_empty():return d
		return "" if a.size()==b.size() else path + " keys differ"
	if a is Array and b is Array:
		if a.size()!=b.size():return path + " lengths differ"
		for i in range(a.size()):
			var d = first_difference(a[i],b[i],path + "[" + str(i) + "]")
			if not d.is_empty():return d
		return ""
	return "" if a==b else path + ": " + str(a) + " versus " + str(b)

static func _json_equivalent(a, b) -> bool:
	if (a is float or a is int) and (b is float or b is int):return abs(float(a)-float(b)) <= 1e-12 + abs(float(a))*1e-14
	if a is Dictionary and b is Dictionary:
		if a.size()!=b.size():return false
		for k in a:
			if not b.has(k) or not _json_equivalent(a[k],b[k]):return false
		return true
	if a is Array and b is Array:
		if a.size()!=b.size():return false
		for i in range(a.size()):
			if not _json_equivalent(a[i],b[i]):return false
		return true
	return a==b
