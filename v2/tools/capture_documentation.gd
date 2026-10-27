extends SceneTree
## Native app viewport capture. Uses the actual Main scene and Python session.
## Only camera, selection, normal controls and declared configurations are changed.
const Main=preload("res://scenes/main.tscn")
var app
var output=""
var plan={}
var frames=[]
var capture_started=0.0
func _initialize():call_deferred("_run")
func now() -> float:return Time.get_ticks_usec()/1000000.0
func wait_until(predicate: Callable,seconds: float=40.0) -> bool:
	var deadline=now()+seconds
	while not predicate.call() and now()<deadline:await create_timer(.03).timeout
	return predicate.call()
func fail(message: String):
	printerr("DOCUMENTATION_CAPTURE_ERROR: "+message)
	if app and app.bridge.authenticated:await app._shutdown(1)
	else:quit(1)
func selected_actor(role: String):
	var candidates=[]
	for actor in app.model.agents:
		if not actor.active:continue
		if role=="predator" and actor.get("species")!="predator":continue
		if role=="offspring" and actor.parent==null:continue
		if role=="hazard" and not actor.in_hazard:continue
		candidates.append(actor)
	if candidates.is_empty():return null
	candidates.sort_custom(func(a,b):return float(a.age)<float(b.age) if role=="offspring" else a.position.length_squared()<b.position.length_squared())
	return candidates[0]
func capture(file: String) -> Dictionary:
	await RenderingServer.frame_post_draw
	var before=now()
	var picture=root.get_texture().get_image()
	var result=OK
	if file.ends_with(".rgba"):
		# Lossless raw readback avoids PNG compression stalling live animation.
		picture.convert(Image.FORMAT_RGBA8)
		var raw=FileAccess.open(output.path_join(file),FileAccess.WRITE)
		if raw:raw.store_buffer(picture.get_data());raw.close()
		else:result=ERR_CANT_CREATE
	else:result=picture.save_png(output.path_join(file))
	if result!=OK:await fail("Cannot save "+file);return {}
	var actor=app.model.actor(app.selected_id)
	var body=app.world_view.bodies.get(app.selected_id)
	return {"file":file,"wall_seconds":before-capture_started,"ticks":app.model.ticks,"simulation_seconds":app.model.ticks/60.0,
		"generation":app.model.generation,"population":app.model.metrics.population,"paused":app.model.paused,
		"selected":app.selected_id,"selected_age":actor.age if actor else null,"activity":body.animation_state if body else null,
		"visual_growth":body.growth if body else null,"pixels":[picture.get_width(),picture.get_height()],"storage_format":"RGBA8" if file.ends_with(".rgba") else "PNG"}
func record() -> void:
	var length=float(plan.get("record_seconds",5.0));var kind=str(plan.get("record",""));var stage=0
	capture_started=now();var next=0.0
	while now()-capture_started<length:
		var elapsed=now()-capture_started
		if kind=="controls":
			if stage==0 and elapsed>=1:app._toggle_ecosystem();stage=1
			elif stage==1 and elapsed>=2:await app._control("paused",true);stage=2
			elif stage==2 and elapsed>=3:
				var scroll=app.ecosystem_panel.get_child(0);scroll.scroll_vertical=int(scroll.get_v_scroll_bar().max_value);stage=3
			elif stage==3 and elapsed>=4:app._toggle_ecosystem();await app._control("paused",false);stage=4
		if elapsed>=next:
			frames.append(await capture("frame-%04d.rgba" % frames.size()));next+=1.0/12.0
		else:await process_frame
	await app._control("paused",true)
	await create_timer(.25).timeout
func _run():
	if DisplayServer.get_name()=="headless":await fail("Native rendering is required; headless images are not screenshots.");return
	var path=""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--capture-plan="):path=arg.trim_prefix("--capture-plan=")
	if path.is_empty():await fail("Supply --capture-plan=/absolute/plan.json");return
	plan=JSON.parse_string(FileAccess.get_file_as_string(path))
	output=str(plan.output);DirAccess.make_dir_recursive_absolute(output)
	app=Main.instantiate();root.add_child(app)
	if not await wait_until(func():return not app.model.run_id.is_empty()):await fail("Python did not connect");return
	var configured=await app._call("configure",{"config_json":FileAccess.get_file_as_string(str(plan.config_path)),"habitat":plan.get("habitat",{}),"paused":true})
	if not configured.get("ok",false):await fail(str(configured));return
	app._apply_quality(int(plan.get("quality",1)))
	app._apply_visual_options(plan.get("visuals",{"weather":"clear","hour":11.3,"cycle":false}))
	var immersive=bool(plan.get("immersive",true))
	if app.immersive!=immersive:app._toggle_immersive()
	await app._control("speed",int(plan.get("warmup_speed",1)))
	await app._control("paused",false)
	await create_timer(float(plan.get("warmup_seconds",3.0))).timeout
	if int(plan.get("generation",1))>1:
		if not await wait_until(func():return app.model.generation>=int(plan.generation) or app.model.finished):await fail("Generation wait timed out");return
		if app.model.generation<int(plan.generation):await fail("Requested generation was not reached naturally");return
	var role=str(plan.get("select","any"))
	if role=="offspring":
		if not await wait_until(func():return selected_actor("offspring")!=null):await fail("No real offspring was born");return
	await app._control("speed",1)
	var actor=selected_actor(role)
	if actor==null:actor=selected_actor("any")
	if actor==null:await fail("No living actor remains");return
	app.selected_id=actor.id;await app._call("select",{"key":actor.id})
	app.world_view.update_view(.016)
	var camera=str(plan.get("camera","ground"))
	if camera=="valley":app.world_view.valley_view()
	elif camera=="overview":app.world_view.reset_camera(false)
	elif camera=="follow":
		app._focus_selected();app.following=true
		app.world_view.distance=5.5;app.world_view.pitch=.24;app.world_view.yaw=PI/4-float(actor.heading)
	else:
		app.world_view.ground_view()
		app.world_view.target=Vector3(0,app.world_view.surface_height(Vector2.ZERO)+.65,0)
		app.world_view.pitch=.23;app.world_view.distance=26
	if plan.get("ecosystem",false):app._toggle_ecosystem()
	await create_timer(.6).timeout
	var start=await app._call("state")
	var before=FileAccess.open(output.path_join("before.json"),FileAccess.WRITE);before.store_string(JSON.stringify(start.report,"\t")+"\n");before.close()
	if not str(plan.get("record","")).is_empty():
		if not app.immersive:app._toggle_immersive()
		await record()
	else:
		await app._control("paused",true);await create_timer(.25).timeout
		capture_started=now()
	var still=await capture("application.png")
	var exported=await app._export(output.path_join("exports"))
	if not exported.get("ok",false):await fail(str(exported));return
	var summary={"case":plan.name,"source":"Native Godot Main scene, real Python engine; viewport readback", "headless":false,
		"plan":plan,"still":still,"frames":frames,"bundle":exported.bundle,
		"event_gaps":app.model.animation_gaps,"animation":app.world_view.animation_summary(),"ecosystem":app.world_view.ecosystem_summary(),
		"renderer":RenderingServer.get_current_rendering_method(),"device":RenderingServer.get_video_adapter_name()}
	var file=FileAccess.open(output.path_join("capture.json"),FileAccess.WRITE);file.store_string(JSON.stringify(summary,"\t")+"\n");file.close()
	print("AE2_DOCUMENTATION_CAPTURE ",plan.name," ",frames.size()," real frames; ",app.model.ticks," Python ticks")
	await app._shutdown(0)
