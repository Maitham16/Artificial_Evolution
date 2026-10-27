extends SceneTree
const Main=preload("res://scenes/main.tscn")
var checks=0
var failures=0
var app
func _initialize() -> void:call_deferred("_run")
func check(value: bool,message: String) -> void:
	checks+=1
	if not value:failures+=1;printerr("FAIL: "+message)
func settle() -> void:
	await create_timer(.23).timeout
	app.world_view.update_view(0)
func _run() -> void:
	app=Main.instantiate();root.add_child(app)
	var deadline=Time.get_ticks_msec()+20000
	while app.model.run_id.is_empty() and Time.get_ticks_msec()<deadline:await process_frame
	if app.model.run_id.is_empty():check(false,"Python connects");await app._shutdown(1);return
	var config=app._read_config()
	config.mode="continuous";config.algorithm="funded";config.population=12;config.groups=3;config.food_count=30;config.maturity_age=.25;config.birth_cooldown=.1;config.population_cap=24
	var reply=await app._call("configure",{"config":config,"seed_text":"42","paused":true})
	check(reply.get("ok",false),"Real continuous engine configured: "+str(reply.get("error","")))
	app.world_view.update_view(0)
	await app._call("step",{"ticks":18});await settle()
	var juveniles=0;var reproduced=0
	for body in app.world_view.bodies.values():
		if body.growth<.999:juveniles+=1
		if body.event_kind=="Reproduce":reproduced+=1
	check(juveniles>0,"Real births create age-driven juvenile appearances")
	check(reproduced>0,"Real offspring receipts reach the parent's animation controller")
	await app._control("paused",false);await create_timer(.15).timeout
	await app._control("paused",true)
	var before=await app._call("state")
	for i in range(8):app.world_view.update_view(0)
	var after=await app._call("state")
	check(before.report.individuals==after.report.individuals and before.report.metrics==after.report.metrics,"Rendering lifecycle animations cannot change Python")
	config.mode="foraging";config.algorithm="selection";config.environment="barren";config.food_count=0;config.population=4;config.generations=1
	reply=await app._call("configure",{"config":config,"seed_text":"42","paused":true})
	check(reply.get("ok",false),"Real survival engine configured: "+str(reply.get("error","")))
	app.world_view.update_view(0);await app._call("step",{"ticks":3600});await settle()
	check(app.world_view.bodies.is_empty() and app.world_view.remnants.size()==4,"Confirmed starvation deaths become four finite visual remnants")
	var correct=true
	for corpse in app.world_view.remnants.values():
		if not corpse.dead or corpse.scale.x>3:correct=false
	check(correct,"Death poses retain correct Python radius units")
	await app._control("paused",false);await create_timer(3.2).timeout
	check(app.world_view.remnants.is_empty(),"Real death remnants finish and disappear")
	print("AE2_LIFECYCLE_TEST_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
	await app._shutdown(0 if failures==0 else 1)
