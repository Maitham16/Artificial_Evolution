extends SceneTree
## Route pointer events through the viewport, rather than emitting UI signals.
const Main=preload("res://scenes/main.tscn")
var app
var checks=0
var failures=0
func check(value: bool,message: String):
	checks+=1
	if not value:failures+=1;printerr("FAIL: "+message)
func _initialize():call_deferred("_run")
func wait_until(predicate: Callable) -> bool:
	var deadline=Time.get_ticks_msec()+15000
	while not predicate.call() and Time.get_ticks_msec()<deadline:await process_frame
	return predicate.call()
func motion(point: Vector2,mask: int=0,relative: Vector2=Vector2.ZERO):
	var event=InputEventMouseMotion.new();event.position=point;event.global_position=point;event.button_mask=mask;event.relative=relative;root.push_input(event,true)
func button(point: Vector2,index: int,pressed: bool):
	var event=InputEventMouseButton.new();event.position=point;event.global_position=point;event.button_index=index;event.pressed=pressed;root.push_input(event,true)
func click(point: Vector2):
	motion(point);button(point,MOUSE_BUTTON_LEFT,true);button(point,MOUSE_BUTTON_LEFT,false);await process_frame
func wheel(point: Vector2,count: int):
	motion(point)
	for i in count:button(point,MOUSE_BUTTON_WHEEL_DOWN,true);button(point,MOUSE_BUTTON_WHEEL_DOWN,false)
	await process_frame;await process_frame
func _run():
	app=Main.instantiate();root.add_child(app)
	check(await wait_until(func():return not app.model.run_id.is_empty()),"Real Python session connects")
	if app.model.run_id.is_empty():await app._shutdown(1);return
	await app._control("paused",true)
	var before=await app._call("state")
	if not app.immersive:app._toggle_immersive()
	app._toggle_ecosystem();await process_frame;await process_frame
	var panel=app.ecosystem_panel;var scroll=panel.get_child(0);var box=scroll.get_child(0)
	var close=box.get_child(0).get_child(1)
	await click(close.get_global_rect().get_center())
	check(not panel.visible,"Visible Close button receives a routed mouse click in immersive mode")
	if not panel.visible:app._toggle_ecosystem()
	await process_frame;await process_frame
	var world=app.world_view;var yaw=world.yaw;var distance=world.distance;var target=world.target
	var point=app.scenery_status.get_global_rect().get_center()
	await wheel(point,8)
	check(scroll.scroll_vertical>0,"Wheel over panel text scrolls its outer container")
	check(world.distance==distance and world.yaw==yaw and world.target==target,"Panel wheel does not zoom or orbit the world behind it")
	scroll.scroll_vertical=0;await process_frame;await process_frame
	var gesture=InputEventPanGesture.new();gesture.position=point;gesture.delta=Vector2(0,8);root.push_input(gesture,true)
	await process_frame;await process_frame
	check(scroll.scroll_vertical>0,"Mac two-finger pan scrolls panel content")
	check(world.yaw==yaw and world.target==target,"Panel trackpad scrolling does not orbit or pan the camera")
	var bar=scroll.get_v_scroll_bar();var rect=bar.get_global_rect()
	scroll.scroll_vertical=0;await process_frame;await process_frame
	var start=Vector2(rect.get_center().x,rect.position.y+12);var end=Vector2(start.x,rect.end.y-12)
	motion(start);button(start,MOUSE_BUTTON_LEFT,true);motion(end,MOUSE_BUTTON_MASK_LEFT,end-start);button(end,MOUSE_BUTTON_LEFT,false)
	await process_frame;await process_frame
	check(scroll.scroll_vertical>0,"Scrollbar thumb accepts a routed drag")
	await wheel(panel.get_global_rect().get_center(),30)
	check(scroll.scroll_vertical>0 and panel.get_global_rect().intersects(app.visual_motion.get_global_rect()),"Bottom scenery controls become reachable")
	var enabled=app.world_view.atmosphere.motion_enabled
	await click(app.visual_motion.get_global_rect().get_center())
	check(app.world_view.atmosphere.motion_enabled!=enabled,"Scrolled scenery checkbox receives a routed click")
	var weather=panel.find_child("VisualWeather",true,false)
	await click(weather.get_global_rect().get_center())
	check(weather.get_popup().visible,"Scrolled weather dropdown opens from a routed mouse click")
	weather.get_popup().hide();await process_frame
	var hour=app.visual_hour.value;var slider=app.visual_hour.get_global_rect()
	await click(Vector2(slider.position.x+slider.size.x*.2,slider.get_center().y))
	check(absf(app.visual_hour.value-hour)>1,"Scrolled hour slider accepts a routed mouse click")
	# Toggling workbench/immersive must retain the panel's pointer priority.
	for immersive in [false,true,false,true]:
		if app.immersive!=immersive:app._toggle_immersive()
		scroll.scroll_vertical=0;await process_frame;await process_frame
		await click(close.get_global_rect().get_center())
		check(not panel.visible,"Panel Close remains clickable after view switch: "+str(immersive))
		if not panel.visible:app._toggle_ecosystem()
	distance=world.distance
	await wheel(Vector2(40,root.get_visible_rect().size.y*.5),1)
	check(world.distance>distance,"Uncovered landscape still receives camera wheel input")
	var after=await app._call("state")
	check(before.report.individuals==after.report.individuals and before.report.execution==after.report.execution,"Panel interactions preserve paused Python creatures and time")
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--panel-input-screenshot=") and DisplayServer.get_name()!="headless":
			scroll.scroll_vertical=int(bar.max_value);await process_frame;await process_frame;await RenderingServer.frame_post_draw
			root.get_texture().get_image().save_png(arg.trim_prefix("--panel-input-screenshot="))
	print("AE2_PANEL_INPUT_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
	await app._shutdown(0 if failures==0 else 1)
