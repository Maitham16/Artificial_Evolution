extends Control
## Display/control surface only. Simulation changes go through the existing Python bridge.
var app
var camera_dock: PanelContainer
var gesture_hint: Label
var pause_button: Button
var speed_menu: OptionButton
var follow_button: Button
var metrics: Label
var status: Label
var identity: Label
var activity: Label
var details: Label
var energy: ProgressBar
var energy_text: Label
var inspector: PanelContainer
var engine_status: Label
var previous_selection=""
var inspection_visible=true

func bind(owner_app) -> void:
	app=owner_app;set_anchors_and_offsets_preset(PRESET_FULL_RECT);mouse_filter=MOUSE_FILTER_IGNORE
	var header=_card(PRESET_TOP_WIDE,Vector4(20,16,-20,94));header.name="DesktopHeader"
	var row=HBoxContainer.new();row.add_theme_constant_override("separation",12);header.add_child(row)
	var brand=VBoxContainer.new();brand.add_theme_constant_override("separation",2);row.add_child(brand)
	app._label("Artificial Evolution",brand,23,app.INK)
	app._label("2.0   /   LIVING WORLD",brand,10,app.MINT)
	metrics=app._label("CONNECTING…",row,12,app.MUTED);metrics.size_flags_horizontal=SIZE_EXPAND_FILL;metrics.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;metrics.vertical_alignment=VERTICAL_ALIGNMENT_CENTER
	pause_button=app._button("Pause",row,app._toggle_pause);pause_button.name="DesktopPause";pause_button.custom_minimum_size.x=83
	speed_menu=OptionButton.new();speed_menu.name="DesktopSpeed"
	for title in ["1× speed","5× speed","20× speed"]:speed_menu.add_item(title)
	speed_menu.item_selected.connect(func(index):app._control("speed",[1,5,20][index]));row.add_child(speed_menu)
	app._button("Research",row,app._toggle_immersive).tooltip_text="Full research workbench · V / Esc"
	app._button("Ecosystem",row,app._toggle_ecosystem).tooltip_text="Confirmed events and decorative scenery · N"
	app._quality_menu(row)
	app._button("⛶",row,app._toggle_fullscreen).tooltip_text="Fullscreen · Ctrl/Cmd + Enter"
	app._button("?",row,app._help).tooltip_text="Controls and source/decoration guide"
	var badge=_card(PRESET_TOP_LEFT,Vector4(20,104,550,140));badge.mouse_filter=MOUSE_FILTER_IGNORE
	status=app._label("Starting the Python engine…",badge,12,app.INK);status.mouse_filter=MOUSE_FILTER_IGNORE;status.text_overrun_behavior=TextServer.OVERRUN_TRIM_ELLIPSIS
	var dock=_card(PRESET_CENTER_BOTTOM,Vector4(-285,-80,285,-24));dock.name="CameraDock";camera_dock=dock
	var cameras=HBoxContainer.new();cameras.alignment=BoxContainer.ALIGNMENT_CENTER;cameras.add_theme_constant_override("separation",6);dock.add_child(cameras)
	app._button("Overview",cameras,func():app.world_view.reset_camera(false);app.following=false)
	app._button("Valley",cameras,func():app.world_view.valley_view();app.following=false)
	app._button("Ground",cameras,func():app.world_view.ground_view();app.following=false)
	app._button("Focus",cameras,app._focus_selected).tooltip_text="Frame the inspected creature · double click / I"
	app._button("−",cameras,func():app.world_view.zoom(1)).tooltip_text="Zoom out"
	app._button("+",cameras,func():app.world_view.zoom(-1)).tooltip_text="Zoom in"
	follow_button=app._button("Follow",cameras,app._toggle_follow);follow_button.name="DesktopFollow";follow_button.tooltip_text="Follow the inspected living creature · F"
	var hint=app._label("Right drag / two fingers: orbit   ·   Pinch / scroll: zoom   ·   Shift-gesture: pan",self,11,app.INK)
	hint.set_anchors_and_offsets_preset(PRESET_CENTER_BOTTOM);hint.offset_left=-285;hint.offset_right=285;hint.offset_top=-105;hint.offset_bottom=-86;hint.mouse_filter=MOUSE_FILTER_IGNORE;hint.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;gesture_hint=hint
	inspector=_card(PRESET_BOTTOM_LEFT,Vector4(20,-300,316,-24));inspector.name="DesktopInspector"
	var box=VBoxContainer.new();box.add_theme_constant_override("separation",9);inspector.add_child(box)
	var specimen_row=HBoxContainer.new();box.add_child(specimen_row)
	var caption=app._label("CREATURE INSPECTOR",specimen_row,10,app.MINT);caption.size_flags_horizontal=SIZE_EXPAND_FILL
	app._button("×",specimen_row,func():inspection_visible=false;inspector.hide()).tooltip_text="Hide inspector; click an animal to reopen"
	identity=app._label("Select an animal",box,19)
	activity=app._label("",box,12,app.GOLD)
	energy_text=app._label("",box,12)
	energy=ProgressBar.new();energy.step=0;energy.show_percentage=false;energy.custom_minimum_size.y=5;box.add_child(energy)
	details=app._wrap("Click a creature to see its real Python state.",box,12,app.MUTED)
	engine_status=app._label("",self,10,app.MUTED);engine_status.set_anchors_and_offsets_preset(PRESET_BOTTOM_RIGHT);engine_status.offset_left=-280;engine_status.offset_right=-24;engine_status.offset_top=-40;engine_status.offset_bottom=-20;engine_status.horizontal_alignment=HORIZONTAL_ALIGNMENT_RIGHT;engine_status.mouse_filter=MOUSE_FILTER_IGNORE

	resized.connect(_layout);_layout()

func _layout() -> void:
	if camera_dock==null:return
	var center=.6 if size.x<1280 else .5
	camera_dock.anchor_left=center;camera_dock.anchor_right=center
	gesture_hint.anchor_left=center;gesture_hint.anchor_right=center

func _card(preset: int,offsets: Vector4) -> PanelContainer:
	var card=PanelContainer.new();add_child(card);card.set_anchors_and_offsets_preset(preset)
	card.offset_left=offsets.x;card.offset_top=offsets.y;card.offset_right=offsets.z;card.offset_bottom=offsets.w
	card.add_theme_stylebox_override("panel",app._style(Color(.043,.085,.085,.95),Color(.26,.38,.31,.7),12))
	return card

func inspect() -> void:inspection_visible=true

func refresh() -> void:
	var model=app.model;var connected=model.connected and app.bridge.authenticated
	pause_button.disabled=not connected;pause_button.text="Resume" if model.paused else "Pause"
	speed_menu.disabled=not connected;speed_menu.select(maxi(0,[1,5,20].find(model.speed)))
	var state="Disconnected" if not connected else "Extinct" if model.extinct else "Complete" if model.finished else "Paused" if model.paused else "Live"
	metrics.text="%s   ·   G%02d   ·   %d LIVING" % [state,model.generation,int(model.metrics.get("population",0))]
	status.text="%s   ·   %d edible plants   ·   Python %.1f×" % [str(app.ENV_LABELS.get(model.config.get("environment",""),"Living ecosystem")),model.food_objects.size(),app.measured]
	if model.habitat.get("enabled",false):status.text+="  ·  PHYSICAL HABITAT / "+str(model.habitat.climate.weather)
	if not connected:status.text=app.bridge.detail
	var actor=model.actor(app.selected_id)
	follow_button.disabled=actor==null or not actor.active
	follow_button.text="Following" if app.following else "Follow"
	if previous_selection!=app.selected_id:inspection_visible=true;previous_selection=app.selected_id
	inspector.visible=actor!=null and inspection_visible
	if actor:
		identity.text="%s  /  %s" % [str(actor.get("species","herbivore") if actor.get("species")!=null else "herbivore").capitalize(),str(actor.id)]
		var body=app.world_view.bodies.get(app.selected_id,app.world_view.remnants.get(app.selected_id))
		activity.text=body.animation_state if body and is_instance_valid(body) else "Confirmed death · "+str(actor.cause) if not actor.alive else "Cohort complete" if not actor.active else "Observing movement"
		energy.max_value=float(actor.capacity);energy.value=float(actor.energy);energy_text.text="Energy  %.1f / %.1f" % [actor.energy,actor.capacity]
		details.text="Age %.1fs   ·   Meals %d   ·   Fitness %.1f\nLineage %s   ·   Depth %d\nParent %s" % [actor.age,actor.meals,actor.fitness,actor.root,actor.depth,str(actor.parent) if actor.parent!=null else "founder"]
	engine_status.text="PYTHON ENGINE   ·   %d FPS   ·   %s" % [int(Engine.get_frames_per_second()),["PERFORMANCE","BALANCED","LUSH"][app.quality_index]]
