extends Control
const Bridge=preload("res://scripts/python_bridge.gd")
const State=preload("res://scripts/python_state.gd")
const WorldView=preload("res://scripts/world_view.gd")
const Visuals=preload("res://scripts/visuals.gd")
const BG=Color("0d1d20")
const PANEL=Color("172b2d")
const INK=Color("e4ebe0")
const MUTED=Color("98afa1")
const MINT=Color("a4dbac")
const GOLD=Color("dfbd87")
const MODES=["foraging","seasons","obstacles","traits","predator_prey","social","continuous"]
const MODE_LABELS=["Food seeking","Changing seasons","Obstacles & hazards","Brains & bodies","Predator & prey","Social behavior","Continuous ecosystem"]
const ENV_LABELS={"uniform":"Meadow","clustered":"Food clusters","sparse":"Scarcity","wide_clustered":"Wide clusters","barren":"Barren","seasonal":"Seasonal food"}
const POLICY_LABELS={"selection":"Selected neural","neutral":"Neutral neural","random":"Random movement","greedy":"Greedy forager","founder":"Frozen founders","coevolution":"Co-evolution","group":"Group survival","individual":"Individual survival","funded":"Funded reproduction","clonal":"Clonal reproduction"}
var ecosystem_panel: PanelContainer
var scenery_status: Label
var food_status: Label
var event_list: ItemList
var event_rows: Array=[]
var event_filter=0
var visual_hour: HSlider
var visual_cycle: CheckBox
var visual_motion: CheckBox
var visual_status: Label
var cli_visuals={}
var cli_ecosystem_panel=false
var immersive=false
var immersive_layer: Control
var workbench_root: Control
var view_home: Control
var cinematic_start=false
var valley_start=false
var immersive_start=false
var quality_index=1
var profile_path=""
var frame_samples: Array=[]
var landscape_label: Label
var model=State.new()
var bridge
var world_view
var viewport_container: SubViewportContainer
var viewport: SubViewport
var model_controls={}
var plots: Array=[]
var selected_id=""
var following=false
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
var settings_panel: Control
var connection_panel: Control
var lineage_view
var connection_label: Label
var connection_details: Label
var repository_edit: LineEdit
var python_edit: LineEdit
var config_edit: TextEdit
var preset_select: OptionButton
var automatic_check: CheckBox
var speed_select: OptionButton
var export_button: Button
var draft={}
var seed_text="2801"
var updating_controls=false
var responses={}
var waiting={}
var ui_clock=0.0
var last_rate_at=0.0
var last_rate_ticks=0
var measured=0.0
var last_export=""
var closing=false
var cli_quit_frames=0
var cli_screenshot=""
var cli_export=""
var cli_environment=""
var cli_mode=""
var cli_config=""
var cli_done=false
var frame_count=0
var startup_deadline=0.0

func _ready() -> void:
	_install_theme();_build_ui()
	bridge=Bridge.new();add_child(bridge)
	bridge.frame_received.connect(_on_frame);bridge.response_received.connect(_on_response)
	bridge.catalog_received.connect(_on_catalog);bridge.status_changed.connect(_on_status)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--frames="):cli_quit_frames=int(arg.trim_prefix("--frames="))
		elif arg.begins_with("--screenshot="):cli_screenshot=arg.trim_prefix("--screenshot=")
		elif arg.begins_with("--export="):cli_export=arg.trim_prefix("--export=")
		elif arg.begins_with("--environment="):cli_environment=arg.trim_prefix("--environment=")
		elif arg.begins_with("--mode="):cli_mode=arg.trim_prefix("--mode=")
		elif arg.begins_with("--config="):cli_config=arg.trim_prefix("--config=")
		elif arg=="--immersive":immersive_start=true
		elif arg=="--ground-view":cinematic_start=true
		elif arg=="--valley-view":valley_start=true
		elif arg.begins_with("--quality="):quality_index=clampi(int(arg.trim_prefix("--quality=")),0,2)
		elif arg.begins_with("--visual-weather="):cli_visuals.weather=arg.trim_prefix("--visual-weather=")
		elif arg.begins_with("--visual-season="):cli_visuals.season=arg.trim_prefix("--visual-season=")
		elif arg.begins_with("--visual-hour="):cli_visuals.hour=float(arg.trim_prefix("--visual-hour="))
		elif arg=="--visual-cycle=off":cli_visuals.cycle=false
		elif arg=="--ecosystem-panel":cli_ecosystem_panel=true
		elif arg.begins_with("--profile="):profile_path=arg.trim_prefix("--profile=")
	var settings=bridge.discover()
	repository_edit.text=str(settings.get("repository",""));python_edit.text=str(settings.get("python",""))
	bridge.launch(repository_edit.text,python_edit.text)
	startup_deadline=_now()+60
	world_view.nature.quality=quality_index
	_sync_quality_menus()
	_apply_visual_options(cli_visuals)
	ecosystem_panel.visible=cli_ecosystem_panel
	if immersive_start:_toggle_immersive()
	get_tree().root.close_requested.connect(_on_close);get_tree().auto_accept_quit=false

func _now() -> float:return Time.get_ticks_usec()/1000000.0

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
	add_child(margin);workbench_root=margin
	var root=VBoxContainer.new();root.add_theme_constant_override("separation",12);margin.add_child(root)
	var header=HBoxContainer.new();root.add_child(header)
	var brand=VBoxContainer.new();brand.add_theme_constant_override("separation",0);brand.size_flags_horizontal=SIZE_EXPAND_FILL;header.add_child(brand)
	_label("ARTIFICIAL EVOLUTION",brand,27)
	_label("02   /   PYTHON ENGINE · GODOT 3D VIEW",brand,11,MINT)
	generation_label=_label("CONNECTING TO PYTHON",header,13,MUTED);generation_label.vertical_alignment=VERTICAL_ALIGNMENT_CENTER
	pause_button=_button("Pause",header,_toggle_pause)
	speed_select=OptionButton.new()
	for value in ["1× speed","5× speed","20× speed"]:speed_select.add_item(value)
	speed_select.item_selected.connect(func(index):_control("speed",[1,5,20][index]));header.add_child(speed_select)
	export_button=_button("Export run",header,_export,true)
	_button("Landscape view",header,_toggle_immersive)
	_button("Controls",header,_help)
	var body=HBoxContainer.new();body.size_flags_vertical=SIZE_EXPAND_FILL;body.add_theme_constant_override("separation",12);root.add_child(body)
	_build_sidebar(body)
	var center=VBoxContainer.new();center.size_flags_horizontal=SIZE_EXPAND_FILL;center.size_flags_vertical=SIZE_EXPAND_FILL;body.add_child(center)
	var tabs=TabBar.new()
	for title in ["3D world","Lineages","Run settings","Connection"]:tabs.add_tab(title)
	tabs.tab_changed.connect(_tab_changed);center.add_child(tabs)
	world_panel=PanelContainer.new();world_panel.size_flags_vertical=SIZE_EXPAND_FILL;center.add_child(world_panel)
	var stack=Control.new();stack.custom_minimum_size=Vector2(320,300);stack.size_flags_vertical=SIZE_EXPAND_FILL;world_panel.add_child(stack);view_home=stack
	viewport_container=SubViewportContainer.new();viewport_container.set_anchors_and_offsets_preset(PRESET_FULL_RECT);viewport_container.stretch=true;viewport_container.mouse_filter=MOUSE_FILTER_STOP;stack.add_child(viewport_container)
	viewport=SubViewport.new();viewport.size=Vector2i(1000,650);viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS;viewport.own_world_3d=true;viewport_container.add_child(viewport)
	world_view=WorldView.new();viewport.add_child(world_view);world_view.set_model(model)
	viewport_container.gui_input.connect(_view_input)
	var overlay=VBoxContainer.new();overlay.position=Vector2(15,15);overlay.mouse_filter=MOUSE_FILTER_IGNORE;stack.add_child(overlay)
	biome_label=_label("WAITING FOR PYTHON",overlay,12,INK);biome_label.mouse_filter=MOUSE_FILTER_IGNORE
	var instruction=_label("Inspect: left click   ·   Orbit: right drag   ·   Zoom: scroll   ·   Pan: middle drag",center,11,MUTED);instruction.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	var camera_row=HBoxContainer.new();center.add_child(camera_row)
	_button("Overview",camera_row,func():world_view.reset_camera();following=false)
	_button("Follow",camera_row,func():following=not following)
	_button("Ground view",camera_row,func():world_view.ground_view();following=false)
	_button("Ecosystem",camera_row,_toggle_ecosystem)
	_quality_menu(camera_row)
	rate_label=_label("CONNECTING",camera_row,12,MUTED);rate_label.size_flags_horizontal=SIZE_EXPAND_FILL;rate_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_RIGHT
	lineage_panel=PanelContainer.new();lineage_panel.size_flags_vertical=SIZE_EXPAND_FILL;lineage_panel.visible=false;center.add_child(lineage_panel)
	lineage_view=Visuals.new();lineage_view.mode="lineages";lineage_view.title="PYTHON ANCESTRY / FOUNDER FAMILIES";lineage_view.model=model;lineage_view.custom_minimum_size=Vector2(300,360);lineage_panel.add_child(lineage_view)
	_build_settings(center);_build_connection(center);_build_inspector(body)
	var footer=HBoxContainer.new();footer.custom_minimum_size.y=140;root.add_child(footer)
	for definition in [["LIVING POPULATION","population",MINT],["COMPLETED GENERATION FITNESS","fitness",GOLD],["MEALS PER SCORED CREATURE","meals",Color("91c6d9")]]:
		var card=PanelContainer.new();card.size_flags_horizontal=SIZE_EXPAND_FILL;footer.add_child(card)
		var plot=Visuals.new();plot.title=definition[0];plot.mode=definition[1];plot.accent=definition[2];plot.model=model;card.add_child(plot);plots.append(plot)
	status_label=_label("Starting the existing Python engine…",root,12,MUTED);status_label.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
	_build_ecosystem_panel()

func _build_sidebar(parent: Node) -> void:
	var card=PanelContainer.new();card.custom_minimum_size.x=230;parent.add_child(card)
	var scroll=ScrollContainer.new();scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;card.add_child(scroll)
	var box=VBoxContainer.new();box.size_flags_horizontal=SIZE_EXPAND_FILL;box.custom_minimum_size.x=198;scroll.add_child(box)
	_label("EXPERIMENT",box,12,MINT)
	for definition in [["mode","Simulation mode"],["environment","Environment"],["algorithm","Controller"]]:
		_label(definition[1],box,12,MUTED)
		var option=OptionButton.new();box.add_child(option);model_controls[definition[0]]=option
		option.item_selected.connect(func(_index):_choice_changed(definition[0]))
	for i in range(MODES.size()):model_controls.mode.add_item(MODE_LABELS[i]);model_controls.mode.set_item_metadata(i,MODES[i])
	_spin("population","Founders",1,300,100,box)
	_label("Random seed",box,12,MUTED)
	var seed=LineEdit.new();seed.text="2801";seed.text_changed.connect(func(_text):_pending());box.add_child(seed);model_controls.seed=seed
	_spin("food_count","Food stock (−1 = default)",-1,500,-1,box)
	_spin("generations","Generations",1,1000,5,box)
	_spin("mutation_rate","Mutation probability",0,1,.1,box,.01)
	_spin("mutation_scale","Mutation scale",0,10,.1,box,.01)
	_button("Start new population",box,_new_run,true)
	automatic_check=CheckBox.new();automatic_check.text="Automatic reproduction";automatic_check.button_pressed=true;box.add_child(automatic_check)
	automatic_check.toggled.connect(func(value):
		if not updating_controls:_control("automatic",value))
	_button("Next generation",box,func():_call("advance"))
	_button("Single physics tick",box,func():_call("step",{"ticks":1}))
	_button("Load configuration",box,_load_config)
	_button("Open export folder",box,_open_exports)
	_wrap("Python controls movement, energy, food, brains, interactions and evolution. Godot displays the received state.",box,12,MUTED)

func _spin(key: String,title: String,minimum: float,maximum: float,value: float,parent: Node,step: float=1) -> void:
	_label(title,parent,12,MUTED)
	var control=SpinBox.new();control.min_value=minimum;control.max_value=maximum;control.step=step;control.value=value;control.size_flags_horizontal=SIZE_EXPAND_FILL
	parent.add_child(control);model_controls[key]=control;control.value_changed.connect(func(_value):_pending())

func _build_inspector(parent: Node) -> void:
	var card=PanelContainer.new();card.custom_minimum_size.x=250;parent.add_child(card)
	var scroll=ScrollContainer.new();scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;card.add_child(scroll)
	var box=VBoxContainer.new();box.size_flags_horizontal=SIZE_EXPAND_FILL;box.custom_minimum_size.x=224;scroll.add_child(box)
	_label("PYTHON OBSERVATIONS",box,12,MINT)
	var grid=GridContainer.new();grid.columns=2;box.add_child(grid)
	alive_label=_metric("ALIVE",grid);family_label=_metric("FAMILIES",grid);score_label=_metric("MEAN FITNESS",grid);meals_label=_metric("MEAN MEALS",grid)
	box.add_child(HSeparator.new());_label("SELECTED SPECIMEN",box,12,MUTED)
	specimen_label=_label("Connecting…",box,23,INK)
	energy_label=_label("",box,12,MUTED)
	energy_bar=ProgressBar.new();energy_bar.max_value=100;energy_bar.show_percentage=false;energy_bar.custom_minimum_size.y=8;box.add_child(energy_bar)
	specimen_details=_label("",box,13,MUTED);specimen_details.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
	neural_plot=Visuals.new();neural_plot.model=model;neural_plot.mode="neurons";neural_plot.title="PYTHON NEURAL ACTIVITY";neural_plot.custom_minimum_size.y=202;box.add_child(neural_plot)
	_wrap("Colors identify founder families. Neural activity is a passive preview calculated by Python.",box,11,MUTED)

func _metric(title: String,parent: Node) -> Label:
	var box=VBoxContainer.new();box.add_theme_constant_override("separation",2);parent.add_child(box);_label(title,box,10,MUTED);return _label("0",box,24,INK)

func _build_settings(parent: Node) -> void:
	settings_panel=PanelContainer.new();settings_panel.visible=false;settings_panel.size_flags_vertical=SIZE_EXPAND_FILL;parent.add_child(settings_panel)
	var content=VBoxContainer.new();settings_panel.add_child(content)
	_label("THE EXISTING PYTHON RUN CONFIGURATION",content,19,INK)
	_wrap("Load the repository's presets or edit any engine setting here. Python validates the complete configuration before starting a new run. The previous run is archived.",content,13)
	preset_select=OptionButton.new();content.add_child(preset_select)
	preset_select.item_selected.connect(func(index):
		if not bridge.catalog.is_empty():
			var name=preset_select.get_item_metadata(index);var preset=bridge.catalog.presets[name];_set_draft(preset.config,str(preset.seed_text));status_label.text="Preset loaded. Start a new population to apply it.")
	config_edit=TextEdit.new();config_edit.custom_minimum_size.y=300;config_edit.size_flags_vertical=SIZE_EXPAND_FILL;config_edit.wrap_mode=TextEdit.LINE_WRAPPING_BOUNDARY;content.add_child(config_edit)
	_button("Apply JSON configuration",content,_apply_json,true)
	_wrap("Live observations retain the Python engine's fitness definitions and cohort semantics. Exported bundles work with the original Python verification and replay commands.",content,12,MUTED)

func _build_connection(parent: Node) -> void:
	connection_panel=PanelContainer.new();connection_panel.visible=false;connection_panel.size_flags_vertical=SIZE_EXPAND_FILL;parent.add_child(connection_panel)
	var scroll=ScrollContainer.new();scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;connection_panel.add_child(scroll)
	var content=VBoxContainer.new();content.size_flags_horizontal=SIZE_EXPAND_FILL;scroll.add_child(content)
	_label("LOCAL PYTHON ENGINE",content,21,INK)
	connection_label=_wrap("Starting…",content,15,MINT)
	_label("Repository folder",content,12,MUTED);repository_edit=LineEdit.new();content.add_child(repository_edit)
	_label("Python interpreter",content,12,MUTED);python_edit=LineEdit.new();content.add_child(python_edit)
	var row=HBoxContainer.new();content.add_child(row)
	_button("Connect",row,func():bridge.launch(repository_edit.text,python_edit.text),true)
	_button("Reconnect",row,func():bridge.reconnect())
	connection_details=_wrap("",content,13)
	_wrap("Snapshots arrive at up to 30 Hz. The 3D view interpolates positions and the shortest heading angle with a 100 ms display delay. It never sends poses or calculated decisions back to Python. A lost connection freezes the view and pauses Python.",content,13)
	_wrap("The standalone app requires the repository and its Python environment. Setup records their paths for launches from Finder. The original Pygame application runs independently.",content,13,GOLD)

func _pending() -> void:
	if status_label and not updating_controls:status_label.text="Settings pending. Start a new population to apply them."

func _option_value(option: OptionButton) -> String:
	return str(option.get_item_metadata(option.selected)) if option.selected>=0 else ""

func _select_value(option: OptionButton,value: String) -> void:
	for i in range(option.item_count):
		if str(option.get_item_metadata(i))==value:option.select(i);return

func _fill_options(option: OptionButton,values: Array,labels: Dictionary) -> void:
	option.clear()
	for value in values:option.add_item(str(labels.get(value,value)));option.set_item_metadata(option.item_count-1,value)

func _choice_changed(key: String) -> void:
	if updating_controls or draft.is_empty():return
	draft=_read_config()
	if key=="mode":
		draft.mode=_option_value(model_controls.mode);draft.algorithm=bridge.catalog.algorithms[draft.mode][0]
		draft.environment="seasonal" if draft.mode=="seasons" else "uniform";draft.food_count=null
	elif key=="environment":draft.environment=_option_value(model_controls.environment);draft.food_count=null
	else:draft.algorithm=_option_value(model_controls.algorithm)
	_set_draft(draft,model_controls.seed.text);_pending()

func _set_draft(data: Dictionary,seed_value: String) -> void:
	draft=data.duplicate(true);seed_text=seed_value;updating_controls=true
	_select_value(model_controls.mode,str(draft.mode))
	var environments: Array=[]
	for key in bridge.catalog.environments:
		if (draft.mode=="seasons" and key=="seasonal") or (draft.mode!="seasons" and key!="seasonal" and not (draft.mode=="social" and key in ["clustered","wide_clustered"])):environments.append(key)
	_fill_options(model_controls.environment,environments,ENV_LABELS);_select_value(model_controls.environment,str(draft.environment))
	_fill_options(model_controls.algorithm,bridge.catalog.algorithms[draft.mode],POLICY_LABELS);_select_value(model_controls.algorithm,str(draft.algorithm))
	model_controls.population.value=draft.population;model_controls.generations.value=draft.generations
	model_controls.food_count.value=-1 if draft.food_count==null else draft.food_count
	model_controls.mutation_rate.value=draft.mutation_rate;model_controls.mutation_scale.value=draft.mutation_scale;model_controls.seed.text=seed_value
	# JSON supplied by Python is authoritative for 63-bit seeds; the text editor
	# uses a decimal token rather than a rounded Godot JSON float.
	var editable=draft.duplicate(true);editable.seed=0
	var text=JSON.stringify(editable,"\t")
	var pattern=RegEx.new();pattern.compile('"seed"\\s*:\\s*0')
	config_edit.text=pattern.sub(text,'"seed": '+seed_value)
	updating_controls=false

func _read_config() -> Dictionary:
	var data=draft.duplicate(true)
	for key in ["population","generations"]:data[key]=int(model_controls[key].value)
	for key in ["schema_version","population_cap","season_length","predators","groups"]:data[key]=int(data[key]) if float(data[key])==floor(float(data[key])) else data[key]
	if data.season_food is Array:
		var stocks=[]
		for value in data.season_food:stocks.append(int(value) if float(value)==floor(float(value)) else value)
		data.season_food=stocks
	data.food_count=null if model_controls.food_count.value<0 else int(model_controls.food_count.value)
	data.mode=_option_value(model_controls.mode);data.environment=_option_value(model_controls.environment);data.algorithm=_option_value(model_controls.algorithm)
	data.mutation_rate=model_controls.mutation_rate.value;data.mutation_scale=model_controls.mutation_scale.value
	data.seed=0
	return data

func _on_catalog(_catalog: Dictionary) -> void:
	if model.run_id.is_empty():
		preset_select.clear()
		for key in bridge.catalog.presets:preset_select.add_item(str(key).capitalize());preset_select.set_item_metadata(preset_select.item_count-1,key)
		_set_draft(bridge.catalog.defaults,"2801")
		if not cli_config.is_empty():
			var result=await _call("configure",{"config_json":FileAccess.get_file_as_string(cli_config)})
			if not result.get("ok",false):return
		elif not cli_environment.is_empty() or not cli_mode.is_empty():
			if cli_environment in ["hazards","seasons"]:draft.mode="obstacles" if cli_environment=="hazards" else "seasons"
			elif not cli_environment.is_empty():draft.environment=cli_environment
			if not cli_mode.is_empty():draft.mode=cli_mode
			draft.algorithm=bridge.catalog.algorithms[draft.mode][0]
			if draft.mode=="seasons":draft.environment="seasonal";draft.food_count=null
			_set_draft(draft,"2801");await _new_run()
		else:await _new_run()
	elif bridge.catalog.get("has_session",false):status_label.text="Reconnected. Python retained this run and paused it. Resume when ready."
	else:status_label.text="A new Python process connected. Start a new population; the previous in-memory run ended."

func _on_status(status: String,message: String) -> void:
	connection_label.text=message;status_label.text=message
	if status in ["disconnected","error","stopped","waiting_for_permission"]:model.connected=false

func _on_frame(data: Dictionary) -> void:
	var changed=model.run_id!=str(data.run_id)
	if not model.accept(data):return
	if changed:
		selected_id=model.selected;world_view.set_model(model);last_rate_ticks=model.ticks;last_rate_at=_now()
		if cinematic_start:
			world_view.update_view(0);world_view.ground_view();cinematic_start=false
		if valley_start:
			world_view.update_view(0);world_view.valley_view();valley_start=false
		_set_draft(model.config,model.seed_text)
	if not model.actor(selected_id):selected_id=model.selected
	_refresh()

func _on_response(value: Dictionary) -> void:
	if value.get("id")!=null and waiting.has(int(value.id)):responses[int(value.id)]=value
	if not value.get("ok",false):status_label.text=str(value.get("error","Python command failed."))

func _call(command: String,data: Dictionary={},timeout: float=30.0) -> Dictionary:
	var id=bridge.request(command,data)
	if id<0:status_label.text="Python is not connected. Open Connection to retry.";return {"ok":false,"error":"Disconnected"}
	waiting[id]=true
	var deadline=_now()+timeout
	while not responses.has(id) and _now()<deadline and bridge.authenticated:await get_tree().process_frame
	waiting.erase(id)
	if responses.has(id):
		var value=responses[id];responses.erase(id);return value
	status_label.text="Python command timed out or disconnected: "+command
	return {"ok":false,"error":status_label.text}

func _new_run() -> void:
	if draft.is_empty():return
	var result=await _call("configure",{"config":_read_config(),"seed_text":model_controls.seed.text})
	if result.get("ok",false):status_label.text="Python started "+str(model.config.mode)+" · seed "+model.seed_text

func _apply_json() -> void:
	var result=await _call("configure",{"config_json":config_edit.text})
	if result.get("ok",false):status_label.text="Python validated and started the new run."

func _control(name: String,value) -> void:await _call("control",{"name":name,"value":value})
func _toggle_pause() -> void:
	if model.connected:await _control("paused",not model.paused)

func _process(delta: float) -> void:
	world_view.selected_id=selected_id
	if not model.run_id.is_empty():
		world_view.update_view(delta if model.connected and not model.paused else 0.0)
		if following and model.displayed.has(selected_id):
			var pos=model.displayed[selected_id].position
			world_view.target=world_view.target.lerp(Vector3(pos.x,world_view.surface_height(pos)+.4,pos.y),1-exp(-6*delta));world_view._update_camera()
		ui_clock+=delta
		if ui_clock>.15:ui_clock=0;_refresh();_refresh_ecosystem()
		if _now()-last_rate_at>=1:
			measured=float(model.ticks-last_rate_ticks)/60/(_now()-last_rate_at);last_rate_at=_now();last_rate_ticks=model.ticks
		frame_count+=1
		if not profile_path.is_empty() and cli_quit_frames>0 and frame_count>90:frame_samples.append(delta*1000)
		if landscape_label:landscape_label.text="LIVING MEADOW   /   %d CREATURES   /   G%02d" % [int(model.metrics.population),model.generation]
		if cli_quit_frames>0 and frame_count>=cli_quit_frames and not cli_done:_finish_cli()
	elif cli_quit_frames>0 and _now()>startup_deadline and not cli_done:
		cli_done=true;printerr("Python startup failed: ",bridge.detail);await _shutdown(1)

func _refresh() -> void:
	if model.run_id.is_empty():return
	alive_label.text=str(int(model.metrics.population));family_label.text=str(int(model.metrics.families));score_label.text="%.1f" % model.metrics.mean_fitness;meals_label.text="%.2f" % model.metrics.mean_meals
	generation_label.text="G%02d / PYTHON %d TICKS" % [model.generation,model.ticks]
	biome_label.text=str(ENV_LABELS.get(model.config.environment,model.config.environment)).to_upper()+"  ·  %d FOOD" % model.food.size()
	var state="DISCONNECTED" if not model.connected else "EXTINCT" if model.extinct else "COMPLETE" if model.finished else "PAUSED" if model.paused else "AWAITING BREEDING" if model.awaiting_generation and not model.automatic else "LIVE"
	rate_label.text="%s / Python %.1f× · target %d×" % [state,measured,model.speed]
	pause_button.text="Resume" if model.paused else "Pause";pause_button.disabled=not bridge.authenticated
	updating_controls=true;automatic_check.button_pressed=model.automatic;speed_select.select([1,5,20].find(model.speed));updating_controls=false
	var actor=model.actor(selected_id)
	if actor:
		specimen_label.text=selected_id.to_upper();specimen_label.add_theme_color_override("font_color",WorldView.family_color(str(actor.root)))
		energy_bar.max_value=float(actor.capacity);energy_bar.value=float(actor.energy)
		energy_label.text="Energy %.1f / %.1f · %s" % [actor.energy,actor.capacity,"living" if actor.active else "cohort ended" if actor.alive else str(actor.cause)]
		specimen_details.text="Age %.1fs · Meals %d\nFitness %.1f\nParent %s\nRoot %s · depth %d\nSpeed %.1f px/s · radius %.1f px\nEnergy drain %.2f/s" % [actor.age,actor.meals,actor.fitness,str(actor.parent) if actor.parent!=null else "founder",actor.root,actor.depth,actor.speed,actor.radius*State.UNITS,actor.energy_cost]
		if actor.in_hazard or float(actor.hazard_loss)>0:specimen_details.text+="\nHAZARD LOSS %.1f / %.1fs" % [actor.hazard_loss,actor.hazard_seconds]
		var visual=world_view.bodies.get(selected_id,world_view.remnants.get(selected_id))
		if visual and is_instance_valid(visual):specimen_details.text+="\nActivity: "+visual.animation_state
		if actor.species!=null:specimen_details.text+="\n%s · captures %d" % [str(actor.species).capitalize(),actor.captures]
		if model.config.mode=="continuous":specimen_details.text+="\nChildren %d" % actor.children
		if model.config.mode=="social":specimen_details.text+="\nGroup %d · shared %.1f → %.1f" % [actor.group,actor.shared_out,actor.shared_in]
		neural_plot.activation=model.activation if model.selected==selected_id else PackedFloat64Array()
		neural_plot.title="PYTHON HIDDEN NEURONS" if not model.activation.is_empty() else "NO ACTIVE NEURAL PREVIEW"
	else:specimen_label.text="Click a creature";specimen_details.text="";energy_bar.value=0;neural_plot.activation=PackedFloat64Array()
	connection_details.text="Engine %s\nSimulation: %d fixed ticks / %.2f seconds\nReceived snapshots: %d\nLast update: %.0f ms ago\nDisplay delay: %.0f ms\nLive founder families: %d\nNeural diversity (RMS): %s" % [str(bridge.catalog.get("engine_version","—")),model.ticks,float(model.ticks)/60,model.received_frames,(_now()-model.last_received)*1000,model.interpolation_delay*1000,int(model.metrics.families),str(model.metrics.neural_rms)]
	plots[1].title="MEAN LIFETIME FITNESS" if model.config.mode=="continuous" else "COMPLETED GENERATION FITNESS"
	for plot in plots:plot.queue_redraw()
	neural_plot.queue_redraw();lineage_view.queue_redraw()

func _tab_changed(index: int) -> void:
	if world_panel:world_panel.visible=index==0
	if lineage_panel:lineage_panel.visible=index==1
	if settings_panel:settings_panel.visible=index==2
	if connection_panel:connection_panel.visible=index==3

func _view_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index==MOUSE_BUTTON_LEFT and event.pressed:
			var id=world_view.pick(event.position)
			if not id.is_empty():
				selected_id=id;world_view.selected_food="";bridge.request("select",{"key":id});_refresh()
			else:
				var plant=world_view.pick_food(event.position)
				if not plant.is_empty():ecosystem_panel.show();_refresh_ecosystem()
		if event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_UP:world_view.zoom(-1)
		if event.pressed and event.button_index==MOUSE_BUTTON_WHEEL_DOWN:world_view.zoom(1)
	elif event is InputEventMouseMotion:
		if event.button_mask & MOUSE_BUTTON_MASK_RIGHT:world_view.orbit(event.relative)
		elif event.button_mask & MOUSE_BUTTON_MASK_MIDDLE:following=false;world_view.pan(event.relative)

func _unhandled_key_input(event: InputEvent) -> void:
	var focus=get_viewport().gui_get_focus_owner()
	if focus is LineEdit or focus is TextEdit:return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode==KEY_SPACE:_toggle_pause();accept_event()
		elif event.keycode==KEY_R:world_view.reset_camera();following=false
		elif event.keycode==KEY_F:following=not following
		elif event.keycode==KEY_E:_export()
		elif event.keycode==KEY_V:_toggle_immersive()
		elif event.keycode==KEY_N:_toggle_ecosystem()
		elif event.keycode==KEY_C:world_view.ground_view();following=false
		elif event.keycode==KEY_ESCAPE and immersive:_toggle_immersive()

func _export(root: String="") -> Dictionary:
	export_button.disabled=true
	var data={}
	if not root.is_empty():data.root=root
	if DisplayServer.get_name()!="headless":data.screenshot=Marshalls.raw_to_base64(get_viewport().get_texture().get_image().save_png_to_buffer())
	status_label.text="Python is exporting the authoritative run…"
	var result=await _call("export",data,60)
	export_button.disabled=false
	if result.get("ok",false):last_export=result.bundle;status_label.text="Python export saved: "+last_export
	return result

func _open_exports() -> void:
	var path=ProjectSettings.globalize_path("user://python-runs");DirAccess.make_dir_recursive_absolute(path);OS.shell_open(path)

func _load_config() -> void:
	var dialog=FileDialog.new();dialog.file_mode=FileDialog.FILE_MODE_OPEN_FILE;dialog.access=FileDialog.ACCESS_FILESYSTEM;dialog.filters=PackedStringArray(["*.json ; Python run configuration"]);dialog.use_native_dialog=true;add_child(dialog)
	dialog.file_selected.connect(func(path):
		var result=await _call("validate_config",{"config_json":FileAccess.get_file_as_string(path)})
		if result.get("ok",false):_set_draft(result.config,str(result.seed_text));status_label.text="Python validated the configuration. Start a new population to apply it."
		dialog.queue_free())
	dialog.canceled.connect(dialog.queue_free);dialog.popup_centered_ratio(.6)

func _help() -> void:
	var dialog=AcceptDialog.new();dialog.title="Python-powered vivarium"
	dialog.dialog_text="SPACE — pause/resume Python\nLeft click — inspect a creature or an edible plant\nN — ecosystem / scenery and confirmed event log\nRight drag — orbit; middle drag — pan; scroll — zoom\nR — reset; F — follow; E — export the Python run\n\nPython owns all neural decisions, movement, meals, survival, births, deaths and interactions.\nGodot interpolates received positions and headings for display.\n\nChoose modes and policies in the sidebar. Run settings exposes the existing Python presets and complete configuration.\nUse Connection to set the repository and Python interpreter."
	add_child(dialog);dialog.confirmed.connect(dialog.queue_free);dialog.popup_centered()

func _finish_cli() -> void:
	cli_done=true
	await _control("paused",true)
	await get_tree().process_frame
	if DisplayServer.get_name()!="headless":await RenderingServer.frame_post_draw
	if not cli_screenshot.is_empty():get_viewport().get_texture().get_image().save_png(cli_screenshot)
	if not cli_export.is_empty():
		var result=await _export(cli_export)
		if not result.get("ok",false):await _shutdown(1);return
		print("AE2_PYTHON_EXPORT ",last_export)
	if not profile_path.is_empty() and not frame_samples.is_empty():
		frame_samples.sort()
		var total=0.0
		for value in frame_samples:total+=value
		var profile={"frames":frame_samples.size(),"mean_ms":total/frame_samples.size(),"median_ms":frame_samples[frame_samples.size()/2],"p95_ms":frame_samples[mini(frame_samples.size()-1,int(frame_samples.size()*.95))],"quality":quality_index,"immersive":immersive,"scenery":world_view.nature.statistics,"animation":world_view.animation_summary(),"ecosystem":world_view.ecosystem_summary(),"renderer":RenderingServer.get_current_rendering_method(),"device":RenderingServer.get_video_adapter_name()}
		var file=FileAccess.open(profile_path,FileAccess.WRITE)
		if file:file.store_string(JSON.stringify(profile,"\t")+"\n");file.close()
	print("AE2_PYTHON_VIEW ",JSON.stringify({"ticks":model.ticks,"frames":model.received_frames,"mode":model.config.mode,"engine":"Python ResearchSession"}))
	await _shutdown(0)

func _on_close() -> void:
	if closing:return
	await _shutdown(0)

func _shutdown(code: int=0) -> void:
	closing=true
	if bridge.authenticated:
		status_label.text="Saving the Python run and closing its process…"
		var result=await _call("shutdown",{},60)
		if result.has("bundle") and result.bundle!=null:last_export=result.bundle
		if not result.get("ok",false):
			printerr("Python shutdown: ",result.get("error","Unknown failure"))
			if not cli_done:closing=false;status_label.text=str(result.get("error","Run could not be saved; Python remains paused."));return
			code=1
	bridge.cancel_uninitialized_process()
	bridge.detach()
	get_tree().quit(code)

func _quality_menu(parent: Node) -> void:
	var options=OptionButton.new();options.add_to_group("landscape_quality")
	for title in ["Performance","Balanced","Lush"]:options.add_item(title)
	options.select(quality_index)
	options.item_selected.connect(func(index):quality_index=index;world_view.set_quality(index);_sync_quality_menus())
	parent.add_child(options)

func _sync_quality_menus() -> void:
	for menu in get_tree().get_nodes_in_group("landscape_quality"):menu.select(quality_index)

func _toggle_immersive() -> void:
	immersive=not immersive
	world_view.research_guides=not immersive
	if immersive:
		if immersive_layer==null:
			immersive_layer=Control.new();immersive_layer.set_anchors_and_offsets_preset(PRESET_FULL_RECT);immersive_layer.z_index=50;add_child(immersive_layer)
		viewport_container.reparent(immersive_layer);viewport_container.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
		workbench_root.hide();immersive_layer.show()
		var bar=HBoxContainer.new();bar.name="LandscapeControls";bar.set_anchors_and_offsets_preset(PRESET_TOP_WIDE);bar.offset_left=24;bar.offset_top=20;bar.offset_right=-24;bar.mouse_filter=MOUSE_FILTER_IGNORE;immersive_layer.add_child(bar)
		landscape_label=_label("LIVING MEADOW / PYTHON SIMULATION",bar,14,Color("f0f0dc"));landscape_label.size_flags_horizontal=SIZE_EXPAND_FILL
		_button("Workbench",bar,_toggle_immersive)
		_button("Ecosystem",bar,_toggle_ecosystem)
		_button("Overview",bar,func():world_view.reset_camera();following=false)
		_button("Valley",bar,func():world_view.valley_view();following=false)
		_button("Ground view",bar,func():world_view.ground_view();following=false)
		_quality_menu(bar)
		var hint=_label("Right drag: orbit    Scroll: zoom    Middle drag: pan    C: ground view    F: follow    N: ecosystem    Space: pause    Esc: workbench",immersive_layer,13,Color("e8e8d0"))
		hint.name="LandscapeHint";hint.set_anchors_and_offsets_preset(PRESET_BOTTOM_WIDE);hint.offset_left=24;hint.offset_top=-40;hint.offset_bottom=-16;hint.mouse_filter=MOUSE_FILTER_IGNORE
	else:
		viewport_container.reparent(view_home);viewport_container.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
		workbench_root.show()
		for node in immersive_layer.get_children():node.queue_free()
		immersive_layer.hide();landscape_label=null

func _build_ecosystem_panel() -> void:
	ecosystem_panel=PanelContainer.new();ecosystem_panel.name="EcosystemPanel";ecosystem_panel.z_index=100;add_child(ecosystem_panel)
	ecosystem_panel.set_anchors_and_offsets_preset(PRESET_TOP_RIGHT);ecosystem_panel.offset_left=-405;ecosystem_panel.offset_right=-20;ecosystem_panel.offset_top=86;ecosystem_panel.anchor_bottom=1;ecosystem_panel.offset_bottom=-60
	var scroll=ScrollContainer.new();scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;ecosystem_panel.add_child(scroll)
	var box=VBoxContainer.new();box.size_flags_horizontal=SIZE_EXPAND_FILL;scroll.add_child(box)
	var header=HBoxContainer.new();box.add_child(header);var title=_label("ECOSYSTEM OBSERVATORY",header,15,MINT);title.size_flags_horizontal=SIZE_EXPAND_FILL;_button("Close",header,_toggle_ecosystem)
	_wrap("PYTHON SIMULATION",box,12,MINT)
	scenery_status=_wrap("Waiting for authoritative environment…",box,13,INK)
	food_status=_wrap("Click a fern in the arena to inspect a real Python food object.",box)
	_label("CONFIRMED PYTHON EVENTS · click to locate",box,11,MINT)
	var filter_menu=OptionButton.new();filter_menu.name="EventFilter"
	for label in ["All confirmed events","Births, deaths, captures and seasons","Meals"]:filter_menu.add_item(label)
	filter_menu.item_selected.connect(func(index):event_filter=index;event_rows.clear();_refresh_ecosystem());box.add_child(filter_menu)
	event_list=ItemList.new();event_list.custom_minimum_size.y=170;event_list.size_flags_horizontal=SIZE_EXPAND_FILL;event_list.add_theme_font_size_override("font_size",12);box.add_child(event_list);event_list.item_selected.connect(_locate_event)
	_wrap("Meal effects mark the creature's observed position; the engine does not identify the consumed plant. Lines show recorded paths and the nearest visible opponent, not a chosen target.",box,11)
	box.add_child(HSeparator.new())
	_label("DECORATIVE SCENERY",box,12,GOLD)
	_wrap("Lighting, clouds, rain, snow, wind and seasonal colors affect this 3D view only. They never change food, energy, senses or evolution.",box,12)
	var weather_menu=OptionButton.new();weather_menu.name="VisualWeather"
	for label in ["Weather: automatic","Clear","Cloudy","Rain","Fog","Snow"]:weather_menu.add_item(label)
	weather_menu.item_selected.connect(func(index):world_view.atmosphere.choose_weather(world_view.atmosphere.WEATHER[index]));box.add_child(weather_menu)
	var season_menu=OptionButton.new();season_menu.name="VisualSeason"
	for label in ["Season: Python / summer fallback","Spring colors","Summer colors","Autumn colors","Winter colors"]:season_menu.add_item(label)
	season_menu.item_selected.connect(func(index):world_view.atmosphere.choose_season(world_view.atmosphere.SEASONS[index]));box.add_child(season_menu)
	visual_status=_label("",box,12,GOLD)
	visual_hour=HSlider.new();visual_hour.min_value=0;visual_hour.max_value=23.99;visual_hour.step=.05;visual_hour.value=10.5;visual_hour.value_changed.connect(func(value):world_view.atmosphere.set_hour(value));box.add_child(visual_hour)
	visual_cycle=CheckBox.new();visual_cycle.text="Day / night cycle · 4 minute day";visual_cycle.button_pressed=true;visual_cycle.toggled.connect(func(value):world_view.atmosphere.cycle_enabled=value);box.add_child(visual_cycle)
	visual_motion=CheckBox.new();visual_motion.text="Scenery motion (independent of Python pause)";visual_motion.button_pressed=true;visual_motion.toggled.connect(func(value):world_view.atmosphere.motion_enabled=value);box.add_child(visual_motion)
	ecosystem_panel.hide()

func _toggle_ecosystem() -> void:ecosystem_panel.visible=not ecosystem_panel.visible;_refresh_ecosystem()

func _apply_visual_options(options: Dictionary) -> void:
	var director=world_view.atmosphere
	if options.has("weather"):director.choose_weather(str(options.weather))
	if options.has("season"):director.choose_season(str(options.season))
	if options.has("hour"):director.set_hour(float(options.hour))
	if options.has("cycle"):director.cycle_enabled=bool(options.cycle)
	director.step(0,true)
	visual_cycle.set_pressed_no_signal(director.cycle_enabled)
	visual_motion.set_pressed_no_signal(director.motion_enabled)
	var weather_menu=ecosystem_panel.find_child("VisualWeather",true,false);weather_menu.select(director.WEATHER.find(director.weather_choice))
	var season_menu=ecosystem_panel.find_child("VisualSeason",true,false);season_menu.select(director.SEASONS.find(director.season_choice))

func _refresh_ecosystem() -> void:
	if not ecosystem_panel.visible:return
	var context=model.environment_context;var source_season=context.get("season")
	scenery_status.text="%d living · %d edible plants · generation %d\n" % [int(model.metrics.get("population",0)),model.food_objects.size(),model.generation]
	if source_season is Dictionary:scenery_status.text+="Python season: %s · food target %d" % [str(source_season.season).capitalize(),int(context.get("food_target",0))]
	else:scenery_status.text+="No seasons in this Python mode."
	var plant=model.food_objects.get(world_view.selected_food)
	if plant:
		food_status.text="PYTHON FOOD %s · %.0f energy\nCollision radius %.1f px · source (%.1f, %.1f)\nFern size and wind are decorative." % [plant.id,plant.energy,float(plant.radius)*State.UNITS,plant.x,plant.y]
	elif not world_view.selected_food.is_empty():food_status.text="Food %s was removed by Python. No plant was recreated." % world_view.selected_food
	else:food_status.text="Click an edible fern in the arena to inspect its Python food identity."
	var director=world_view.atmosphere
	visual_status.text="%02d:%02d · %s · %s (%s)" % [int(director.hour),int(fmod(director.hour,1)*60),director.weather,str(director.season).capitalize(),director.season_source]
	visual_hour.set_value_no_signal(director.hour)
	var latest=[]
	for event in world_view.recent_events:
		if event_filter==0 or (event_filter==1 and event.kind!="meal") or (event_filter==2 and event.kind=="meal"):latest.append(event)
		if latest.size()>=64:break
	if latest!=event_rows:
		event_rows=latest.duplicate(true);event_list.clear()
		for event in event_rows:
			var message="%5.1fs  %s  %s" % [float(event.get("time",0)),str(event.kind).to_upper(),str(event.id)]
			if event.kind=="capture":message+=" → "+", ".join(event.get("targets",[]))
			elif event.kind=="season":message+=" "+str(event.context.season)
			elif event.kind=="birth" and event.get("parent")!=null:message+=" ← "+str(event.parent)
			elif event.kind=="death":message+=" · "+str(event.get("cause",""))
			event_list.add_item(message)
			event_list.set_item_tooltip(event_list.item_count-1,message)

func _locate_event(index: int) -> void:
	if index<0 or index>=event_rows.size():return
	var event=event_rows[index];var id=world_view.focus_event(event)
	following=false
	if not id.is_empty():selected_id=id;bridge.request("select",{"key":id});_refresh()
	elif event.has("x"):status_label.text="Recorded %s location · %.1fs · %s" % [event.kind,float(event.get("time",0)),event.id]
