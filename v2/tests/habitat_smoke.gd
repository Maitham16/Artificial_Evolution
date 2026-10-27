extends SceneTree
const Main=preload("res://scenes/main.tscn")
var app
var checks=0
var failures=0
func _initialize():call_deferred("_run")
func check(value: bool,message: String):
	checks+=1
	if not value:failures+=1;printerr("FAIL: "+message)
func _run():
	app=Main.instantiate();root.add_child(app)
	var deadline=Time.get_ticks_msec()+20000
	while app.model.run_id.is_empty() and Time.get_ticks_msec()<deadline:await process_frame
	check(not app.model.run_id.is_empty(),"Habitat controls connect to the Python engine")
	if app.model.run_id.is_empty():await app._shutdown(1);return
	check(not app.model.habitat.get("enabled",false),"Original research rules remain the default")
	var cfg=app._read_config();cfg.population=12;cfg.groups=3;cfg.food_count=30
	var reply=await app._call("configure",{"config":cfg,"seed_text":"42","paused":true,"habitat":{"enabled":true,"weather_period":1.0}})
	check(reply.get("ok",false) and app.model.habitat.enabled,"The explicit toggle enables a separate Python habitat session")
	app.world_view.update_view(0)
	check(app.habitat_check.button_pressed,"Sidebar reflects acknowledged physical settings")
	check(not app.model.habitat_surface.is_empty(),"Authoritative heightfield arrives with the initial snapshot")
	var surface=app.model.habitat_surface;var point=Vector2(-float(surface.width)/2+5,-float(surface.height)/2+7)
	check(absf(app.world_view.surface_height(point)-float(surface.heights[7*int(surface.nx)+5]))<.0001,"Display contact height agrees with Python terrain nodes")
	check(app.world_view.nature.content.get_node_or_null("PythonHabitatWater")!=null,"Water is rendered inside the actual arena")
	await app._call("step",{"ticks":75});app.world_view.update_view(0)
	var director=app.world_view.atmosphere;director.choose_weather("auto");director.cycle_enabled=true;director.step(0,true)
	check(director.weather=="rain" and director.summary().weather_source=="Python habitat","Automatic rain follows the simulated Python climate")
	check(absf(director.hour-float(app.model.habitat.climate.hour))<.0001,"Automatic daylight follows simulation time")
	app.ecosystem_panel.show();app._refresh_ecosystem()
	check("PHYSICAL HABITAT" in app.scenery_status.text and "v2 habitat replay" in app.scenery_status.text,"Inspector clearly identifies new rules and their replay")
	var before=await app._call("state")
	director.choose_weather("snow");director.step(0,true)
	check(director.summary().weather_source=="decorative" and app.model.habitat.climate.weather=="rain","Manual weather override is explicitly cosmetic")
	for i in range(5):app.world_view.update_view(.016)
	var after=await app._call("state")
	check(before.report==after.report,"IK, rendering and visual weather cannot alter physical Python state")
	check(before.report.habitat.version=="physical_habitat_v1","Reports identify the extended experiment")
	var legacy=await app._call("configure",{"config":cfg,"seed_text":"42","paused":true,"habitat":{"enabled":false}})
	app.world_view.update_view(0)
	check(legacy.get("ok",false) and not app.model.habitat.enabled,"Users can return to original rules in a fresh run")
	check(app.world_view.nature.physical_surface.is_empty(),"Returning to legacy mode removes the physical arena map")
	var original=await app._call("state")
	check(not original.report.has("habitat"),"Legacy reports retain the original export/replay contract")
	print("AE2_HABITAT_TEST_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
	await app._shutdown(0 if failures==0 else 1)
