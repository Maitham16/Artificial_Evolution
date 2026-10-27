extends SceneTree
const Main=preload("res://scenes/main.tscn")
const Exporter=preload("res://scripts/exporter.gd")
var checks=0
var failures=0
var app
func _initialize():call_deferred("_run")
func check(value: bool,message: String):
	checks+=1
	if not value:failures+=1;printerr("FAIL: "+message)
func button(text: String) -> Button:
	for node in app.find_children("*","Button",true,false):
		if node.text==text:return node
	return null
func _run():
	app=Main.instantiate();root.add_child(app)
	await process_frame
	check(app.model.agents.size()==100,"Native interface creates 100 founders")
	button("Pause").pressed.emit()
	check(app.paused,"Pause button changes simulation state")
	button("Resume").pressed.emit()
	check(not app.paused,"Resume button restores simulation state")
	app.paused=true
	for i in range(120):app.model.step()
	var before=app.model.snapshot()
	# Tabs are tested through their actual signal.
	var tabs=app.find_children("*","TabBar",true,false)[0]
	tabs.current_tab=1
	check(app.lineage_panel.visible and not app.world_panel.visible,"Lineage tab switches content")
	tabs.current_tab=2
	check(app.transfer_panel.visible,"Transfer tab switches content")
	app.model_controls.population.value=4;app.model_controls.food_count.value=8
	app.model_controls.seed.value=42;app.model_controls.mutation_scale.value=.23
	button("Start new population").pressed.emit()
	app.paused=true
	check(app.model.config.population==4 and app.model.config.seed==42,"New-run button applies settings")
	check(is_equal_approx(app.model.config.mutation_scale,.23),"Mutation scale survives interface round trip")
	check(before.config.population==100 and app.model.ticks==0,"New-run replacement starts a fresh cohort")
	tabs.current_tab=0
	var actor=app.model.agents[0]
	var point=app.world_view.camera.unproject_position(Vector3(actor.position.x,.3,actor.position.y))
	var click=InputEventMouseButton.new();click.button_index=MOUSE_BUTTON_LEFT;click.pressed=true;click.position=point
	app._view_input(click)
	check(app.selected_id==actor.id,"Viewport picking selects the projected creature")
	var keyboard=InputEventKey.new();keyboard.pressed=true;keyboard.keycode=KEY_SPACE
	app._unhandled_key_input(keyboard)
	check(not app.paused,"Space keyboard handler resumes the paused model")
	app.paused=true
	app.world_view.orbit(Vector2(20,-10));app.world_view.zoom(-1)
	button("Reset camera").pressed.emit()
	button("Follow specimen").pressed.emit()
	check(app.following,"Follow button enables camera tracking")
	button("Run matched check").pressed.emit()
	check(app.paused and app.job!=null,"Transfer button freezes live training")
	while not app.job.complete:app.job.work(50000)
	app._refresh_transfer()
	check(app.job.rows.size()==12 and app.cancel_button.disabled,"Transfer interface displays complete matched results")
	check(not app.open_check_button.disabled,"Saved transfer results become available")
	button("Run matched check").pressed.emit();button("Cancel").pressed.emit()
	check(app.job.cancelled,"Cancel button retains a cancelled transfer record")
	tabs.current_tab=0
	app.paused=true
	print("AE2_UI_TEST_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
	app.queue_free()
	await process_frame
	quit(0 if failures==0 else 1)
