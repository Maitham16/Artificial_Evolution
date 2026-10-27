extends SceneTree
const Main=preload("res://scenes/main.tscn")
var checks=0
var failures=0
var app
func _initialize():call_deferred("_run")
func check(value: bool,message: String):
	checks+=1
	if not value:failures+=1;printerr("FAIL: "+message)
func _wait_ready() -> bool:
	var deadline=Time.get_ticks_msec()+20000
	while app.model.run_id.is_empty() and Time.get_ticks_msec()<deadline:await process_frame
	return not app.model.run_id.is_empty()
func button(text: String) -> Button:
	for node in app.find_children("*","Button",true,false):
		if node.text==text:return node
	return null
func _run():
	app=Main.instantiate();root.add_child(app)
	check(await _wait_ready(),"Native scene connects to Python")
	if app.model.run_id.is_empty():await app._shutdown(1);return
	check(app.model.metrics.population==100,"Python creates the original 100 founders")
	var paused=await app._call("control",{"name":"paused","value":true})
	check(paused.get("ok",false) and app.model.paused,"Pause command is confirmed by Python")
	var tick=app.model.ticks
	var stepped=await app._call("step",{"ticks":120})
	check(stepped.get("ok",false) and app.model.ticks==tick+120,"Single-step invokes real Python ticks")
	var before=await app._call("state")
	for i in range(4):app.world_view.update_view(.016)
	var after=await app._call("state")
	check(before.report.individuals==after.report.individuals,"Rendering cannot change Python creatures")
	check(before.report.metrics==after.report.metrics,"Rendering cannot change food or fitness")
	var tabs=app.find_children("*","TabBar",true,false)[0]
	tabs.current_tab=1;check(app.lineage_panel.visible,"Lineage tab shows Python birth records")
	tabs.current_tab=2;check(app.settings_panel.visible,"Settings tab exposes the Python configuration")
	tabs.current_tab=3;check(app.connection_panel.visible,"Connection tab exposes the engine paths")
	tabs.current_tab=0
	var id=app.model.agents[0].id
	var actor=app.model.agents[0]
	var position=app.model.sample_display().get(id,{"position":actor.position}).position
	var point=app.world_view.camera.unproject_position(Vector3(position.x,.3,position.y))
	check(app.world_view.pick(point)==id,"Picking selects the displayed Python creature")
	var selected=await app._call("select",{"key":id})
	check(selected.get("ok",false) and app.model.selected==id,"Python supplies the selected specimen preview")
	check(app.model.activation.size()==8,"Hidden-neuron activations arrive from NumPy")
	var snapshot=app.model.ticks;app.bridge.detach()
	var deadline=Time.get_ticks_msec()+100
	while Time.get_ticks_msec()<deadline:await process_frame
	check(not app.model.connected,"Disconnect freezes the display")
	var endpoint_path=app.bridge.endpoint_path
	app.bridge.endpoint={};app.bridge.endpoint_path=endpoint_path+".not-ready"
	app.bridge.started_at=app._now()-21;app.bridge._set_status("starting","Testing a delayed interpreter startup")
	await process_frame
	check(app.bridge.status=="waiting_for_permission","A slow or permission-blocked interpreter stays retryable")
	app.bridge.endpoint_path=endpoint_path
	deadline=Time.get_ticks_msec()+5000
	while not app.bridge.authenticated and Time.get_ticks_msec()<deadline:await process_frame
	var reconnected=await app._call("state")
	check(reconnected.get("ok",false) and reconnected.report.execution.ticks==snapshot,"Reconnect retains the same paused Python run")
	check(app.bridge.authenticated,"Late endpoint availability connects automatically after the wait")
	if not reconnected.get("ok",false):await app._shutdown(1);return
	var validated=await app._call("validate_config",{"config_json":'{"seed":9223372036854775807}'})
	check(validated.get("ok",false) and validated.seed_text=="9223372036854775807","Configuration import preserves 63-bit seeds")
	app._set_draft(validated.config,validated.seed_text)
	check('9223372036854775807' in app.config_edit.text,"Configuration editor preserves exact seed text")
	var draft=app._read_config();draft.population=12;draft.groups=3;draft.food_count=30;draft.mode="obstacles";draft.algorithm="selection";draft.environment="uniform"
	var changed=await app._call("configure",{"config":draft,"seed_text":"42","paused":true})
	check(changed.get("ok",false) and app.model.config.mode=="obstacles","Python switches to the original obstacle engine")
	check(app.model.hazards.size()==2 and app.model.barriers.size()==3,"3D geometry matches Python obstacles")
	app.world_view.update_view(0)
	check(app.world_view.bodies.size()==12,"Renderer follows Python population identities")
	app.world_view.reset_camera()
	var fits=true;var size=app.viewport.get_visible_rect().size
	for x in [-app.model.width/40,app.model.width/40]:
		for z in [-app.model.height/40,app.model.height/40]:
			if not Rect2(Vector2.ZERO,size).has_point(app.world_view.camera.unproject_position(Vector3(x,0,z))):fits=false
	check(fits,"Reset camera fits every world corner in the viewport")
	var predator_config=app._read_config();predator_config.mode="predator_prey";predator_config.algorithm="coevolution";predator_config.predators=3
	var predator_reply=await app._call("configure",{"config":predator_config,"seed_text":"42","paused":true})
	check(predator_reply.get("ok",false),"Hot switching uses the original predator–prey engine")
	app.world_view.update_view(0)
	var red=true
	for specimen in app.model.agents:
		if specimen.species=="predator":
			for mesh in app.world_view.bodies[specimen.id].find_children("*","MeshInstance3D",true,false):
				if str(mesh.name).begins_with("Body") and mesh.material_override.albedo_color!=Color("c96f60"):red=false
	check(red,"New-run body identities rebuild species styling")
	print("AE2_UI_TEST_RESULT ",JSON.stringify({"checks":checks,"failures":failures,"engine_ticks":app.model.ticks}))
	await app._shutdown(0 if failures==0 else 1)
