extends Control
const Sim=preload("res://scripts/simulation.gd")
const WorldView=preload("res://scripts/world_view.gd")
const Visuals=preload("res://scripts/visuals.gd")
const Exporter=preload("res://scripts/exporter.gd")
const Benchmark=preload("res://scripts/benchmark.gd")
const BG=Color("0d1d20")
const PANEL=Color("172b2d")
const INK=Color("e4ebe0")
const MUTED=Color("98afa1")
const MINT=Color("a4dbac")
const GOLD=Color("dfbd87")
const ENV_NAMES=["Meadow","Food clusters","Scarcity","Hazards & barriers","Changing seasons","Barren"]
const POLICY_NAMES=["Selected neural","Neutral neural","Random movement","Greedy forager","Frozen founders"]
var model
var world_view
var viewport_container: SubViewportContainer
var viewport: SubViewport
var model_controls={}
var plots: Array=[]
var selected_id: String=""
var paused=false
var speed=1
var accumulator=0.0
var measured=0.0
var last_time=0
var last_ticks=0
var ui_clock=0.0
var pause_button: Button
var status_label: Label
var generation_label: Label
var biome_label: Label
var rate_label: Label
var specimen_label: Label
var energy_label: Label
var energy_bar: ProgressBar
var specimen_details: Label
var neural_plot
var alive_label: Label
var meals_label: Label
var family_label: Label
var score_label: Label
var world_panel: Control
var lineage_panel: Control
var transfer_panel: Control
var lineage_view
var transfer_button: Button
var cancel_button: Button
var open_check_button: Button
var transfer_progress: ProgressBar
var transfer_status: Label
var transfer_values={}
var job
var job_restored=false
var was_paused=false
var following=false
var drag_moved=false
var last_export=""
var last_export_ticks: int=-1
var cli_screenshot=""
var cli_export=""
var cli_quit_frames=0
var frame_count=0

func _ready() -> void:
	_install_theme()
	_build_ui()
	_new_run(false)
	last_time=Time.get_ticks_msec()
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--screenshot="):cli_screenshot=argument.trim_prefix("--screenshot=")
		elif argument.begins_with("--export="):cli_export=argument.trim_prefix("--export=")
		elif argument.begins_with("--frames="):cli_quit_frames=int(argument.trim_prefix("--frames="))
		elif argument.begins_with("--environment="):
			var key=argument.trim_prefix("--environment=")
			if key in Sim.ENVIRONMENTS:model_controls.environment.select(Sim.ENVIRONMENTS.find(key));_new_run(false)
	get_tree().root.close_requested.connect(_on_close)
	get_tree().auto_accept_quit=false

func _style(color: Color,border: Color=Color("304743"),radius: int=10) -> StyleBoxFlat:
	var box=StyleBoxFlat.new();box.bg_color=color
	box.set_corner_radius_all(radius);box.set_border_width_all(1);box.border_color=border
	box.content_margin_left=12;box.content_margin_right=12;box.content_margin_top=8;box.content_margin_bottom=8
	return box

func _install_theme() -> void:
	var t=Theme.new();t.default_font_size=14
	t.set_color("font_color","Label",INK)
	t.set_color("font_color","Button",INK);t.set_color("font_hover_color","Button",Color.WHITE)
	for kind in ["Button","OptionButton"]:
		t.set_stylebox("normal",kind,_style(Color("243c39")))
		t.set_stylebox("hover",kind,_style(Color("354f44"),MINT))
		t.set_stylebox("pressed",kind,_style(Color("456044"),MINT))
		t.set_stylebox("focus",kind,_style(Color(0,0,0,0),GOLD))
		t.set_stylebox("disabled",kind,_style(Color("1c2e2e")))
		t.set_color("font_color",kind,INK)
	t.set_stylebox("panel","PanelContainer",_style(PANEL))
	t.set_stylebox("normal","LineEdit",_style(Color("203734")))
	t.set_color("font_color","LineEdit",INK)
	t.set_stylebox("background","ProgressBar",_style(Color("30443d"),Color("30443d"),4))
	t.set_stylebox("fill","ProgressBar",_style(MINT,MINT,4))
	t.set_constant("separation","VBoxContainer",10);t.set_constant("separation","HBoxContainer",10)
	t.set_constant("h_separation","GridContainer",20);t.set_constant("v_separation","GridContainer",12)
	theme=t

func _label(text: String,parent: Node,size_px: int=14,color: Color=INK) -> Label:
	var label=Label.new();label.text=text;label.add_theme_font_size_override("font_size",size_px);label.add_theme_color_override("font_color",color);parent.add_child(label);return label

func _wrap(text: String,parent: Node,size_px: int=13,color: Color=MUTED) -> Label:
	var label=_label(text,parent,size_px,color);label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;label.size_flags_horizontal=SIZE_EXPAND_FILL;return label

func _button(text: String,parent: Node,callback: Callable,accent: bool=false) -> Button:
	var button=Button.new();button.text=text;button.custom_minimum_size.y=36;button.pressed.connect(callback);parent.add_child(button)
	if accent:
		button.add_theme_stylebox_override("normal",_style(MINT,MINT));button.add_theme_color_override("font_color",BG)
	return button

func _panel(parent: Node,min_width: float=0) -> VBoxContainer:
	var card=PanelContainer.new();card.custom_minimum_size.x=min_width;parent.add_child(card)
	var content=VBoxContainer.new();card.add_child(content);return content

func _build_ui() -> void:
	var background=ColorRect.new();background.color=BG;background.set_anchors_and_offsets_preset(PRESET_FULL_RECT);background.mouse_filter=MOUSE_FILTER_IGNORE;add_child(background)
	var margin=MarginContainer.new();margin.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	for side in ["left","right","top","bottom"]:margin.add_theme_constant_override("margin_"+side,16)
	add_child(margin)
	var root=VBoxContainer.new();root.add_theme_constant_override("separation",12);margin.add_child(root)
	var header=HBoxContainer.new();root.add_child(header)
	var brand=VBoxContainer.new();brand.add_theme_constant_override("separation",0);brand.size_flags_horizontal=SIZE_EXPAND_FILL;header.add_child(brand)
	_label("ARTIFICIAL EVOLUTION",brand,27)
	_label("02   /   THREE-DIMENSIONAL VIVARIUM",brand,11,MINT)
	generation_label=_label("GENERATION 01",header,13,MUTED);generation_label.vertical_alignment=VERTICAL_ALIGNMENT_CENTER
	pause_button=_button("Pause",header,_toggle_pause)
	var speed_select=OptionButton.new();for value in ["1× speed","4× speed","12× speed"]:speed_select.add_item(value)
	speed_select.item_selected.connect(func(index):speed=[1,4,12][index]);header.add_child(speed_select)
	_button("Export run",header,_export,true)
	_button("Controls",header,_help)
	var body=HBoxContainer.new();body.size_flags_vertical=SIZE_EXPAND_FILL;body.add_theme_constant_override("separation",12);root.add_child(body)
	_build_sidebar(body)
	var center=VBoxContainer.new();center.size_flags_horizontal=SIZE_EXPAND_FILL;center.size_flags_vertical=SIZE_EXPAND_FILL;body.add_child(center)
	var tabs=TabBar.new();tabs.add_tab("3D world");tabs.add_tab("Lineages");tabs.add_tab("Transfer check");tabs.tab_changed.connect(_tab_changed);center.add_child(tabs)
	world_panel=PanelContainer.new();world_panel.size_flags_vertical=SIZE_EXPAND_FILL;center.add_child(world_panel)
	var stack=Control.new();stack.custom_minimum_size=Vector2(320,300);stack.size_flags_vertical=SIZE_EXPAND_FILL;world_panel.add_child(stack)
	viewport_container=SubViewportContainer.new();viewport_container.set_anchors_and_offsets_preset(PRESET_FULL_RECT);viewport_container.stretch=true;viewport_container.mouse_filter=MOUSE_FILTER_STOP;stack.add_child(viewport_container)
	viewport=SubViewport.new();viewport.size=Vector2i(1000,650);viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS;viewport.own_world_3d=true;viewport_container.add_child(viewport)
	world_view=WorldView.new();viewport.add_child(world_view)
	viewport_container.gui_input.connect(_view_input)
	var overlay=VBoxContainer.new();overlay.position=Vector2(15,15);overlay.mouse_filter=MOUSE_FILTER_IGNORE;stack.add_child(overlay)
	biome_label=_label("MEADOW",overlay,12,Color("e9f2d6"));biome_label.mouse_filter=MOUSE_FILTER_IGNORE
	var instruction=_label("Inspect: left click   ·   Orbit: right drag   ·   Zoom: scroll   ·   Pan: middle drag",center,11,MUTED)
	instruction.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	var camera_row=HBoxContainer.new();center.add_child(camera_row)
	_button("Reset camera",camera_row,func():world_view.reset_camera();following=false)
	_button("Follow specimen",camera_row,func():following=not following)
	rate_label=_label("LIVE / 1.0×",camera_row,12,MUTED);rate_label.size_flags_horizontal=SIZE_EXPAND_FILL;rate_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_RIGHT
	lineage_panel=PanelContainer.new();lineage_panel.size_flags_vertical=SIZE_EXPAND_FILL;lineage_panel.visible=false;center.add_child(lineage_panel)
	lineage_view=Visuals.new();lineage_view.mode="lineages";lineage_view.title="FOUNDER FAMILIES / BIRTH COHORTS";lineage_view.custom_minimum_size=Vector2(300,360);lineage_panel.add_child(lineage_view)
	_build_transfer(center)
	_build_inspector(body)
	var footer=HBoxContainer.new();footer.custom_minimum_size.y=140;root.add_child(footer)
	for definition in [["LIVING POPULATION","population",MINT],["COMPLETED GENERATION FITNESS","fitness",GOLD],["MEALS PER CREATURE","meals",Color("91c6d9")]]:
		var card=PanelContainer.new();card.size_flags_horizontal=SIZE_EXPAND_FILL;footer.add_child(card)
		var plot=Visuals.new();plot.title=definition[0];plot.mode=definition[1];plot.accent=definition[2];plot.custom_minimum_size.y=135;card.add_child(plot);plots.append(plot)
	status_label=_label("100 untrained founders. Observe, select, and evolve.",root,12,MUTED)

func _build_sidebar(parent: Node) -> void:
	var card=PanelContainer.new();card.custom_minimum_size.x=224;parent.add_child(card)
	var scroll=ScrollContainer.new();scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;card.add_child(scroll)
	var box=VBoxContainer.new();box.size_flags_horizontal=SIZE_EXPAND_FILL;box.custom_minimum_size.x=198;scroll.add_child(box)
	_label("EXPERIMENT",box,12,MINT)
	_label("Environment",box,12,MUTED)
	var env=OptionButton.new();for text in ENV_NAMES:env.add_item(text)
	box.add_child(env);model_controls.environment=env;env.item_selected.connect(func(_i):_pending())
	_label("Controller",box,12,MUTED)
	var policy=OptionButton.new();for text in POLICY_NAMES:policy.add_item(text)
	box.add_child(policy);model_controls.algorithm=policy;policy.item_selected.connect(func(_i):_pending())
	_spin("population","Founders",2,200,100,box)
	_spin("seed","Random seed",0,2147483647,2801,box)
	_spin("food_count","Base food stock",0,300,150,box)
	_spin("generation_limit","Generations",1,100,10,box)
	_label("Mutation probability",box,12,MUTED)
	var mutation=HSlider.new();mutation.min_value=0;mutation.max_value=1;mutation.step=.01;mutation.value=.1;box.add_child(mutation);model_controls.mutation_rate=mutation
	var mutation_label=_label("10% of inherited weights",box,12,GOLD)
	mutation.value_changed.connect(func(value):mutation_label.text="%d%% of inherited weights" % roundi(value*100);_pending())
	_spin("mutation_scale","Mutation scale",0,2,.1,box,.01)
	_button("Start new population",box,func():_new_run(true),true)
	_button("Load configuration",box,_load_config)
	_button("Open export folder",box,_open_exports)
	_wrap("SPEED CONTROLLED\nAll policies: 3 m/s.\nNeural weights steer; food is sensed locally within 8 m.",box,12,MUTED)
	var divider=HSeparator.new();box.add_child(divider)
	_wrap("New settings start a separate run. Existing run data is archived before replacement.",box,12,MUTED)

func _spin(key: String,title: String,minimum: float,maximum: float,value: float,parent: Node,step: float=1.0) -> void:
	_label(title,parent,12,MUTED)
	var control=SpinBox.new();control.min_value=minimum;control.max_value=maximum;control.step=step;control.value=value;control.size_flags_horizontal=SIZE_EXPAND_FILL
	parent.add_child(control);model_controls[key]=control;control.value_changed.connect(func(_value):_pending())

func _build_inspector(parent: Node) -> void:
	var card=PanelContainer.new();card.custom_minimum_size.x=250;parent.add_child(card)
	var scroll=ScrollContainer.new();scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;card.add_child(scroll)
	var box=VBoxContainer.new();box.size_flags_horizontal=SIZE_EXPAND_FILL;box.custom_minimum_size.x=224;scroll.add_child(box)
	_label("LIVE OBSERVATIONS",box,12,MINT)
	var grid=GridContainer.new();grid.columns=2;box.add_child(grid)
	alive_label=_metric("ALIVE",grid);family_label=_metric("FAMILIES",grid);score_label=_metric("MEAN FITNESS",grid);meals_label=_metric("MEAN MEALS",grid)
	box.add_child(HSeparator.new())
	_label("SELECTED SPECIMEN",box,12,MUTED)
	specimen_label=_label("Click a creature",box,23,INK)
	energy_label=_label("Energy 100 / 100",box,12,MUTED)
	energy_bar=ProgressBar.new();energy_bar.max_value=100;energy_bar.show_percentage=false;energy_bar.custom_minimum_size.y=8;box.add_child(energy_bar)
	specimen_details=_label("",box,13,MUTED);specimen_details.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	neural_plot=Visuals.new();neural_plot.mode="neurons";neural_plot.title="HIDDEN NEURONS";neural_plot.custom_minimum_size.y=202;box.add_child(neural_plot)
	_wrap("Colors identify founder families. Neural activity is a current-state preview.",box,11,MUTED)

func _metric(title: String,parent: Node) -> Label:
	var box=VBoxContainer.new();box.add_theme_constant_override("separation",2);parent.add_child(box)
	_label(title,box,10,MUTED);return _label("0",box,24,INK)

func _build_transfer(parent: Node) -> void:
	transfer_panel=PanelContainer.new();transfer_panel.visible=false;transfer_panel.size_flags_vertical=SIZE_EXPAND_FILL;parent.add_child(transfer_panel)
	var content=VBoxContainer.new();content.add_theme_constant_override("separation",18);transfer_panel.add_child(content)
	_label("A MATCHED TRANSFER CHECK",content,20,INK)
	_wrap("Copy the entire current birth cohort into three unseen layouts. Compare its frozen brains with random movement, greedy food seeking, and the original founder brains. All policies share speed, energy costs, and physical starts.",content,14)
	_wrap("30 seconds per layout · no test training · 3 layout repeats are descriptive, not independent training replications.",content,12,GOLD)
	var row=HBoxContainer.new();content.add_child(row)
	transfer_button=_button("Run matched check",row,_start_check,true)
	cancel_button=_button("Cancel",row,_cancel_check);cancel_button.disabled=true
	open_check_button=_button("Open results",row,func():
		if job and not job.output_path.is_empty():OS.shell_open(job.output_path))
	open_check_button.disabled=true
	transfer_progress=ProgressBar.new();transfer_progress.show_percentage=true;transfer_progress.custom_minimum_size.y=18;content.add_child(transfer_progress)
	transfer_status=_label("Ready. The live run will pause during the check.",content,12,MUTED)
	var table=GridContainer.new();table.columns=5;table.add_theme_constant_override("v_separation",18);content.add_child(table)
	for title in ["POLICY","FITNESS","MEALS","ALIVE AT 30s","LAYOUTS"]:_label(title,table,11,MUTED)
	for key in Benchmark.POLICIES:
		_label({"current":"Current bank","random":"Random","greedy":"Greedy","founder":"Founder bank"}[key],table,14,INK)
		var values=[]
		for i in range(4):values.append(_label("—",table,14,MINT))
		transfer_values[key]=values
	_wrap("Fitness = survival seconds + 10 × meals, with collision/hazard penalties where applicable. Living test actors are right-censored at 30 seconds. The full rows and protocol are saved as JSON and CSV.",content,12,MUTED)

func _read_config() -> Dictionary:
	var data=Sim.defaults()
	for key in ["population","seed","food_count","generation_limit"]:data[key]=int(model_controls[key].value)
	data.environment=Sim.ENVIRONMENTS[model_controls.environment.selected]
	data.algorithm=Sim.ALGORITHMS[model_controls.algorithm.selected]
	data.mutation_rate=model_controls.mutation_rate.value
	data.mutation_scale=model_controls.mutation_scale.value
	return data

func _pending() -> void:
	if status_label:status_label.text="Settings pending. Start a new population to apply them."

func _new_run(archive: bool) -> void:
	var data=_read_config();var error=Sim.validate(data)
	if not error.is_empty():status_label.text=error;return
	if job and not job.complete and not job.cancelled:_cancel_check()
	if archive and model and model.ticks>0:
		var previous=Exporter.export_run(model)
		if previous.is_empty():status_label.text="Cannot archive the previous run; new run was not started.";return
	model=Sim.new(data);last_export_ticks=-1;accumulator=0;paused=false;selected_id=model.agents[0].id
	world_view.set_model(model);world_view.selected_id=selected_id
	for plot in plots:plot.model=model
	lineage_view.model=model;neural_plot.model=model
	last_ticks=0;last_time=Time.get_ticks_msec()
	_refresh()
	status_label.text="New untrained population · %d founders · seed %d" % [data.population,data.seed]

func _toggle_pause() -> void:
	if job and not job.complete and not job.cancelled:return
	paused=not paused
	pause_button.text="Resume" if paused else "Pause"

func _process(delta: float) -> void:
	if model==null:return
	if job and not job.complete and not job.cancelled:
		job.work(7000);_refresh_transfer()
	elif job and not job_restored:
		job_restored=true;paused=was_paused;_refresh_transfer()
	if not paused and not model.finished:
		accumulator+=delta*speed
		var start=Time.get_ticks_usec();var processed=0
		while accumulator>=Sim.STEP and processed<32 and Time.get_ticks_usec()-start<10000:
			if not model.step():accumulator=0;break
			accumulator-=Sim.STEP;processed+=1
	world_view.selected_id=selected_id
	world_view.update_view(delta if not paused else 0.0)
	if following:
		for c in model.agents:
			if c.id==selected_id and c.alive:
				world_view.target=world_view.target.lerp(Vector3(c.position.x,0,c.position.y),.08);world_view._update_camera()
	ui_clock+=delta
	if ui_clock>=.12:
		ui_clock=0;_refresh()
	if Time.get_ticks_msec()-last_time>=1000:
		measured=float(model.ticks-last_ticks)/60.0/(float(Time.get_ticks_msec()-last_time)/1000.0);last_ticks=model.ticks;last_time=Time.get_ticks_msec()
	frame_count+=1
	if cli_quit_frames>0 and frame_count>=cli_quit_frames:
		cli_quit_frames=0;paused=true
		if not cli_screenshot.is_empty() or not cli_export.is_empty():
			await RenderingServer.frame_post_draw
			if not cli_screenshot.is_empty():get_viewport().get_texture().get_image().save_png(cli_screenshot)
			if not cli_export.is_empty():
				_export(cli_export)
				print("AE2_NATIVE_EXPORT ",last_export)
				if last_export.is_empty():get_tree().quit(1);return
		get_tree().quit()

func _refresh() -> void:
	var m=model.metrics()
	alive_label.text=str(m.alive);family_label.text=str(m.families);score_label.text="%.1f" % m.mean_fitness;meals_label.text="%.2f" % m.mean_meals
	generation_label.text="G%02d  /  SEED %d" % [model.generation,model.config.seed]
	biome_label.text=ENV_NAMES[Sim.ENVIRONMENTS.find(model.config.environment)].to_upper()+"  ·  %d PELLETS" % model.food.size()
	rate_label.text=("COMPLETE" if model.finished else "PAUSED" if paused else "LIVE")+" / target %d× · actual %.1f×" % [speed,measured]
	pause_button.text="Resume" if paused else "Pause"
	var selected=null
	for c in model.agents:
		if c.id==selected_id:selected=c
	if selected:
		specimen_label.text=selected.id.to_upper();specimen_label.add_theme_color_override("font_color",WorldView.family_color(selected.root))
		energy_label.text="Energy %.1f / 100 · %s" % [selected.energy,"living" if selected.alive else selected.cause]
		energy_bar.value=selected.energy
		var danger=model.in_hazard(selected) and selected.alive
		energy_bar.add_theme_stylebox_override("fill",_style(Color("e59c89") if danger else MINT,Color("e59c89") if danger else MINT,4))
		specimen_details.text="Age %.1fs    Meals %d\nFitness %.1f\nParent %s\nRoot %s · depth %d\n%s" % [selected.age,selected.meals,selected.fitness,selected.parent if not selected.parent.is_empty() else "founder",selected.root,selected.depth,"HAZARD: −17 energy/s" if danger else "Movement: 3 m/s · drain 5/s" if selected.alive else "Lifetime complete"]
		if not selected.alive:
			neural_plot.title="LIFETIME COMPLETE";neural_plot.activation=PackedFloat64Array()
		elif model.config.algorithm in ["random","greedy"]:
			neural_plot.title="BRAIN UNUSED / STEERING RULE";neural_plot.activation=PackedFloat64Array()
		else:
			neural_plot.title="HIDDEN NEURONS";neural_plot.activation=selected.brain.hidden(model.sensors(selected))
	else:
		specimen_label.text="Select a creature";specimen_details.text="Click a living creature in the 3D world.\n\nOrbit, zoom, or pan to explore the habitat.";energy_bar.value=0;neural_plot.activation=PackedFloat64Array()
	for plot in plots:plot.queue_redraw()
	neural_plot.queue_redraw();lineage_view.queue_redraw()

func _tab_changed(index: int) -> void:
	if world_panel:world_panel.visible=index==0
	if lineage_panel:lineage_panel.visible=index==1
	if transfer_panel:transfer_panel.visible=index==2

func _view_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index==MOUSE_BUTTON_LEFT and event.pressed:selected_id=world_view.pick(event.position);_refresh()
		if event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_UP:world_view.zoom(-1)
		if event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_DOWN:world_view.zoom(1)
	elif event is InputEventMouseMotion:
		if event.button_mask & MOUSE_BUTTON_MASK_RIGHT:world_view.orbit(event.relative)
		elif event.button_mask & MOUSE_BUTTON_MASK_MIDDLE:following=false;world_view.pan(event.relative)

func _unhandled_key_input(event: InputEvent) -> void:
	if get_viewport().gui_get_focus_owner() is LineEdit:return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode==KEY_SPACE:_toggle_pause();accept_event()
		elif event.keycode==KEY_R:world_view.reset_camera();following=false
		elif event.keycode==KEY_E:_export()
		elif event.keycode==KEY_F:following=not following

func _export(destination: String="") -> void:
	if model==null:return
	last_export=Exporter.export_run(model,destination,get_viewport().get_texture().get_image())
	if not last_export.is_empty():last_export_ticks=model.ticks
	status_label.text="Export saved: "+last_export if not last_export.is_empty() else "Export could not be created. Existing exports are never overwritten."

func _open_exports() -> void:
	DirAccess.make_dir_recursive_absolute("user://runs")
	OS.shell_open(ProjectSettings.globalize_path("user://runs"))

func _load_config() -> void:
	var dialog=FileDialog.new();dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.filters=PackedStringArray(["*.json ; Run configuration"]);dialog.use_native_dialog=true
	add_child(dialog)
	dialog.file_selected.connect(func(path):
		var data=JSON.parse_string(FileAccess.get_file_as_string(path))
		if not data is Dictionary:status_label.text="Invalid configuration JSON.";dialog.queue_free();return
		var error=Sim.validate(data)
		if not error.is_empty():status_label.text=error;dialog.queue_free();return
		for key in ["population","seed","food_count","generation_limit","mutation_scale"]:model_controls[key].value=data[key]
		model_controls.environment.select(Sim.ENVIRONMENTS.find(data.environment));model_controls.algorithm.select(Sim.ALGORITHMS.find(data.algorithm));model_controls.mutation_rate.value=data.mutation_rate
		status_label.text="Configuration loaded. Start a new population to apply it.";dialog.queue_free())
	dialog.canceled.connect(dialog.queue_free);dialog.popup_centered_ratio(.6)

func _start_check() -> void:
	if job and not job.complete and not job.cancelled:return
	was_paused=paused;paused=true;job_restored=false;job=Benchmark.new(model)
	transfer_button.disabled=true;cancel_button.disabled=false;open_check_button.disabled=true;_refresh_transfer()

func _cancel_check() -> void:
	if job and not job.complete and not job.cancelled:job.cancel()

func _refresh_transfer() -> void:
	transfer_progress.value=job.progress()*100
	transfer_status.text="%d / 12 matched tests · live run paused" % job.phase
	for policy in Benchmark.POLICIES:
		var total_fitness=0.0;var total_meals=0.0;var survival=0.0;var n=0
		for row in job.rows:
			if row.policy==policy:total_fitness+=row.mean_fitness;total_meals+=row.mean_meals;survival+=row.survival_at_30s;n+=1
		if n>0:
			transfer_values[policy][0].text="%.1f" % (total_fitness/n);transfer_values[policy][1].text="%.2f" % (total_meals/n);transfer_values[policy][2].text="%.1f%%" % (survival/n*100);transfer_values[policy][3].text="%d / 3" % n
	if job.complete or job.cancelled:
		transfer_button.disabled=false;cancel_button.disabled=true;open_check_button.disabled=false
		transfer_status.text=("Cancelled; partial rows retained. " if job.cancelled else "Complete; descriptive results saved. ")+job.output_path

func _help() -> void:
	var dialog=AcceptDialog.new();dialog.title="Vivarium controls"
	dialog.dialog_text="SPACE — pause / resume\nLeft click — inspect a creature\nRight drag — orbit the camera\nMiddle drag — pan\nScroll — zoom\nR — reset camera   F — follow specimen\nE — export this run\n\nAll policies move at the same speed. Neural controllers only choose steering.\nSettings apply to a new population; the prior run is archived.\n\nThis is a new Godot ground-foraging model rendered in 3D.\nThe original Python application and its research records are separate."
	add_child(dialog);dialog.confirmed.connect(dialog.queue_free);dialog.popup_centered()

func _on_close() -> void:
	if model and model.ticks>0 and last_export_ticks!=model.ticks:_export()
	if job and not job.complete and not job.cancelled:job.cancel()
	get_tree().quit()
