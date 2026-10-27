extends SceneTree
const Main=preload("res://scenes/main.tscn")
var app
var checks=0
var failures=0
func _initialize():call_deferred("_run")
func check(value: bool,message: String):
	checks+=1
	if not value:failures+=1;printerr("FAIL: "+message)
func wait_until(predicate: Callable) -> bool:
	var deadline=Time.get_ticks_msec()+15000
	while not predicate.call() and Time.get_ticks_msec()<deadline:await process_frame
	return predicate.call()
func _run():
	app=Main.instantiate();root.add_child(app)
	check(await wait_until(func():return not app.model.run_id.is_empty()),"Desktop connects to the real Python engine")
	if app.model.run_id.is_empty():await app._shutdown(1);return
	var saved_path=ProjectSettings.globalize_path("user://engine.json")
	var saved=FileAccess.get_file_as_string(saved_path);var development_root=app.bridge.engine_root
	app.bridge.engine_root="/private/tmp/Example.app/Contents/Resources/engine";app.bridge.remember();app.bridge.engine_root=development_root
	check(FileAccess.get_file_as_string(saved_path)==saved,"Bundled launch cannot truncate or replace development settings")
	app._toggle_immersive();var hud=app.desktop_hud
	check(app.immersive and hud!=null,"Landscape has a dedicated desktop HUD")
	hud.pause_button.pressed.emit()
	check(await wait_until(func():return app.model.paused),"HUD pause button pauses Python")
	hud.refresh();check(hud.pause_button.text=="Resume","Paused state is acknowledged in the HUD")
	hud.speed_menu.item_selected.emit(1)
	check(await wait_until(func():return app.model.speed==5),"HUD speed menu commands the real engine")
	hud.speed_menu.item_selected.emit(0)
	check(await wait_until(func():return app.model.speed==1),"HUD restores normal speed")
	await app._call("step",{"ticks":60});await create_timer(.25).timeout
	var before=await app._call("state");var world=app.world_view
	world.update_view(0)
	var transforms=world.terrain_pose_updates;var uploads=world.food_uploads
	for i in range(10):world.update_view(0)
	check(world.terrain_pose_updates==transforms,"Stationary poses reuse terrain alignment")
	check(world.food_uploads==uploads,"Unchanged paused food avoids repeated GPU uploads")
	var actor=app.model.agents[0];app.selected_id=actor.id;world.selected_id=actor.id
	app._focus_selected();var camera_before=world.camera.transform
	check(world.distance<=10 and world.distance>=5,"Focus chooses a useful close viewing distance")
	check(world.camera.transform==camera_before,"Focus does not snap the camera")
	world._process(.2)
	hud.follow_button.pressed.emit();check(app.following,"HUD starts following an actual living creature")
	await app._control("speed",20);app._process(.016)
	var followed: Vector2=app.model.displayed[actor.id].position
	check(Vector2(world.target.x,world.target.z).distance_to(followed)<.001,"Follow tracks the actual interpolated pose without a second target delay")
	check(world.camera_smoothing>40,"Fast simulation uses responsive camera easing instead of losing the subject")
	await app._control("speed",1)
	before=await app._call("state")
	var drag=InputEventMouseMotion.new();drag.button_mask=MOUSE_BUTTON_MASK_MIDDLE;drag.relative=Vector2(30,0);app._view_input(drag)
	check(not app.following,"Panning disengages follow")
	var zoom=InputEventMagnifyGesture.new();zoom.factor=1.3;var distance=world.distance;app._view_input(zoom)
	check(world.distance<distance,"Mac pinch gesture zooms toward the selection")
	zoom.factor=0;distance=world.distance;app._view_input(zoom)
	check(world.distance==distance,"Invalid pinch factors cannot corrupt the camera")
	var gesture=InputEventPanGesture.new();gesture.delta=Vector2(2,1);var yaw=world.yaw;app._view_input(gesture)
	check(world.yaw!=yaw,"Two-finger gesture orbits the camera")
	gesture.shift_pressed=true;var target=world.target;app._view_input(gesture)
	check(world.target!=target,"Shift-gesture pans without changing the simulation")
	world.orbit(Vector2(0,10000));check(world.pitch<=1.35,"Orbit pitch is clamped")
	world.zoom(10000);check(world.distance==180,"Zoom-out limit remains finite")
	world.zoom(-10000);check(world.distance==3.5,"Zoom-in limit prevents ground penetration")
	camera_before=world.camera.transform;world.reset_camera(false)
	check(world.camera.transform==camera_before,"Overview can frame the arena without an immediate camera jump")
	world._process(.05)
	check(world.camera.transform!=camera_before,"Camera eases toward its new framing")
	check(world.camera.position.y>=world.surface_height(Vector2(world.camera.position.x,world.camera.position.z))+.39,"Camera remains above the landscape")
	app._apply_quality(0);await process_frame;await process_frame
	check(app.viewport_container.stretch_shrink==2,"Performance mode reduces only 3D resolution")
	var mapped=app._view_point(app.viewport_container.size/2)
	check(mapped.distance_to(Vector2(app.viewport.size)/2)<.01,"Picking scales correctly at reduced render resolution")
	app._apply_quality(1);await process_frame
	check(app.viewport_container.stretch_shrink==1,"Balanced restores full 3D resolution")
	world.reset_camera();await process_frame;world.update_view(0)
	var projected=Vector2.ZERO
	for candidate in app.model.agents:
		var candidate_pos: Vector2=app.model.sample_display().get(candidate.id,{"position":candidate.position}).position
		var screen=world.camera.unproject_position(Vector3(candidate_pos.x,world.surface_height(candidate_pos)+.3,candidate_pos.y))
		if world.pick(screen)==candidate.id:actor=candidate;projected=screen;break
	var pos: Vector2=app.model.sample_display().get(actor.id,{"position":actor.position}).position
	var click=InputEventMouseButton.new();click.button_index=MOUSE_BUTTON_LEFT;click.pressed=true;click.position=projected*app.viewport_container.size/Vector2(app.viewport.size)
	app._view_input(click)
	check(app.selected_id==actor.id,"Desktop click selects the visible Python creature")
	hud.refresh();check(hud.identity.text.contains(actor.id) and hud.inspector.visible,"Desktop inspector shows its real identity")
	check(hud.energy.value==float(actor.energy),"Desktop energy is read from Python")
	var body=world.bodies[actor.id];var pose={"position":pos,"heading":actor.heading}
	body.present(actor,pose,app.model.display_sim_time,.016,100)
	check(body.meshes.all(func(mesh):return mesh.cast_shadow==GeometryInstance3D.SHADOW_CASTING_SETTING_OFF),"Distant animals stop spending shadow passes")
	body.present(actor,pose,app.model.display_sim_time,.016,10)
	check(body.meshes.all(func(mesh):return mesh.cast_shadow==GeometryInstance3D.SHADOW_CASTING_SETTING_ON),"Near animals restore shadows")
	app.selected_id="absent";app._toggle_follow();check(not app.following,"Follow cannot invent an absent creature")
	var after=await app._call("state")
	check(before.report.individuals==after.report.individuals and before.report.simulation==after.report.simulation,"Camera, HUD, quality and animation budgets preserve scientific state")
	check(before.report.execution==after.report.execution,"Presentation controls do not advance paused Python time")
	app._toggle_immersive();check(not app.immersive and app.desktop_hud==null,"Research mode restores the independent workbench controls")
	print("AE2_DESKTOP_TEST_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
	await app._shutdown(0 if failures==0 else 1)
