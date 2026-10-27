extends SceneTree
## Exercise public observatory controls against a paused, live Python process.
const Main=preload("res://scenes/main.tscn")
var checks=0
var failures=0
var app
func _initialize():call_deferred("_run")
func check(value: bool,message: String):
	checks+=1
	if not value:failures+=1;printerr("FAIL: "+message)
func _run():
	app=Main.instantiate();root.add_child(app)
	var deadline=Time.get_ticks_msec()+20000
	while app.model.run_id.is_empty() and Time.get_ticks_msec()<deadline:await process_frame
	check(not app.model.run_id.is_empty(),"Observatory connects to the unchanged Python engine")
	if app.model.run_id.is_empty():await app._shutdown(1);return
	await app._call("control",{"name":"paused","value":true})
	await app._call("step",{"ticks":180});app.world_view.update_view(0)
	var before=await app._call("state");var director=app.world_view.atmosphere
	deadline=Time.get_ticks_msec()+1000
	while app.world_view.recent_events.is_empty() and Time.get_ticks_msec()<deadline:await process_frame
	check(not app.world_view.recent_events.is_empty(),"Actual Python meals arrive in the source journal")
	app._toggle_ecosystem();check(app.ecosystem_panel.visible,"Observatory drawer opens")
	var filter_menu=app.ecosystem_panel.find_child("EventFilter",true,false);filter_menu.item_selected.emit(2)
	check(not app.event_rows.is_empty() and app.event_rows.all(func(event):return event.kind=="meal"),"Meal filter shows confirmed receipts only")
	if not app.event_rows.is_empty():
		var event=app.event_rows[0];app._locate_event(0)
		check(app.selected_id==event.id,"Clicking the source event list focuses its actual participant")
	filter_menu.item_selected.emit(1)
	check(app.event_rows.all(func(event):return event.kind!="meal"),"Life-event filter excludes frequent meals")
	filter_menu.item_selected.emit(0)
	check(app.model.food_objects.size()==app.model.food.size(),"Every edible plant has a Python food identity")
	var plant=app.model.food_objects.values()[0];var p: Vector2=plant.position
	var projected=app.world_view.camera.unproject_position(Vector3(p.x,app.world_view.surface_height(p)+.18,p.y))
	check(not app.world_view.pick_food(projected).is_empty(),"Ray picking identifies a real edible plant")
	app._refresh_ecosystem();check("PYTHON FOOD" in app.food_status.text,"Plant inspector reports source energy and radius")
	app._apply_visual_options({"weather":"rain","season":"autumn","hour":22,"cycle":false})
	check(director.rain==1 and director.daylight==0,"Rain and night render without advancing Python")
	check(director.season=="autumn" and director.season_source=="decorative","Manual colors are explicitly decorative")
	check(director.rain_particles.emitting and not director.snow_particles.emitting,"Only the selected weather emitter runs")
	check(director.moon.light_energy>0 and not app.world_view.nature.sun.shadow_enabled,"Night uses moonlight and disables sun shadows")
	var weather_menu=app.ecosystem_panel.find_child("VisualWeather",true,false)
	weather_menu.item_selected.emit(5);director.step(10,true)
	check(director.weather=="snow" and director.snow_particles.emitting,"Weather menu signals drive snow rendering")
	var season_menu=app.ecosystem_panel.find_child("VisualSeason",true,false)
	season_menu.item_selected.emit(4);director.step(0,true)
	check(director.season=="winter" and director.snow_cover>.7,"Winter affects scenery frost")
	app.visual_cycle.button_pressed=true;app.visual_motion.button_pressed=false
	var clock=director.visual_seconds;var hour=director.hour
	director.step(30)
	check(director.visual_seconds==clock and director.hour==hour,"Scenery motion toggle freezes its independent clock")
	app.visual_motion.button_pressed=true;director.step(1)
	check(director.visual_seconds>clock and director.hour>hour,"Scenery resumes its own day cycle")
	app._apply_visual_options({"weather":"clear","hour":12,"cycle":false})
	check(director.daylight==1 and app.world_view.nature.sun.shadow_enabled,"Daylight restores sun and shadows")
	app.world_view.update_view(0)
	check(app.world_view.food_meshes.multimesh.instance_count==app.model.food_objects.size(),"Fern instances match actual food count")
	check(app.world_view.effects.get_child_count()<=20,"Confirmed event effects are bounded")
	var after=await app._call("state")
	check(before.report.individuals==after.report.individuals,"Weather, clock and picking preserve every Python creature")
	check(before.report.metrics==after.report.metrics and before.report.execution==after.report.execution,"Scenery controls leave Python time and fitness unchanged")
	check(before.report.simulation==after.report.simulation,"Scenery controls preserve complete scientific simulation state")
	var id=app.model.agents[0].id;var count=app.world_view.bodies.size()
	check(app.world_view.focus_event({"kind":"meal","id":id,"x":100,"y":100})==id,"A confirmed receipt can focus its real living identity")
	check(app.world_view.focus_event({"kind":"death","id":"missing","x":100,"y":100}).is_empty(),"Historical event locations never invent living creatures")
	check(app.world_view.bodies.size()==count,"Event navigation cannot spawn animals")
	var cfg=app._read_config();cfg.mode="seasons";cfg.environment="seasonal";cfg.algorithm="selection";cfg.food_count=null
	var reply=await app._call("configure",{"config":cfg,"seed_text":"42","paused":true})
	check(reply.get("ok",false),"Seasonal view uses the original Python seasonal configuration")
	if not reply.get("ok",false):printerr(reply);await app._shutdown(1);return
	app.world_view.update_view(0);director.choose_season("auto");director.step(0,true)
	check(director.season==app.model.environment_context.season.season and director.season_source=="Python","Auto season reads the actual Python generation history")
	check(app.model.food_objects.size()==150 and app.model.environment_context.food_target==150,"Spring food availability is controlled by Python")
	app._refresh_ecosystem();check("Python season: Spring" in app.scenery_status.text,"Inspector distinguishes the authoritative seasonal context")
	app._toggle_immersive();check(app.ecosystem_panel.visible and app.immersive,"Observatory remains available in landscape mode")
	app._toggle_immersive();check(not app.immersive and app.ecosystem_panel.visible,"Returning to the workbench retains the drawer")
	app._toggle_ecosystem();check(not app.ecosystem_panel.visible,"Drawer closes without changing the run")
	print("AE2_ECOSYSTEM_TEST_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
	await app._shutdown(0 if failures==0 else 1)
