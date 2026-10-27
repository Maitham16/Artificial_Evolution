extends SceneTree
## Native close-up asset review. This scene contains no simulation engine.
const Animal=preload("res://scripts/animal_view.gd")
var animals=[]
var elapsed=0.0
var frames=0
var review_clip="Idle"
var review_phase=.13
var output="res://docs/screenshots/animals.png"
func _initialize() -> void:call_deferred("_build")
func _build() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--screenshot="):output=arg.trim_prefix("--screenshot=")
		elif arg=="--run":review_clip="Run";review_phase=.25
	var stage=Node3D.new();root.add_child(stage)
	var environment=WorldEnvironment.new();var settings=Environment.new();environment.environment=settings
	settings.background_mode=Environment.BG_COLOR;settings.background_color=Color("b6c8c6")
	settings.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;settings.ambient_light_color=Color("cfdbdf");settings.ambient_light_energy=.40
	settings.tonemap_mode=Environment.TONE_MAPPER_FILMIC;settings.tonemap_exposure=.85;stage.add_child(environment)
	var sun=DirectionalLight3D.new();sun.rotation_degrees=Vector3(-48,-30,0);sun.light_energy=.85;sun.light_color=Color("fff0d9");sun.shadow_enabled=true;sun.directional_shadow_max_distance=22;stage.add_child(sun)
	var ground=MeshInstance3D.new();var plane=PlaneMesh.new();plane.size=Vector2(200,200);ground.mesh=plane
	var material=StandardMaterial3D.new();material.albedo_color=Color(.12,.16,.13);material.roughness=1;ground.material_override=material;stage.add_child(ground)
	for i in range(3):
		var key=["doe","stag","wolf"][i];var actor={"id":"preview:"+key,"root":"family0","species":"predator" if key=="wolf" else "prey"}
		for candidate in range(100):
			actor.root="family"+str(candidate)
			if Animal.appearance(actor).model==key:break
		var animal=Animal.new();stage.add_child(animal);animal.configure(actor);animal.position=Vector3((i-1)*1.95,0,0);animal.rotation.y=-.45;animals.append(animal)
		var label=Label3D.new();label.text=["WOODLAND DOE","ANTLERED DEER","GREY-BROWN WOLF"][i];label.position=Vector3((i-1)*1.95,.02,.85);label.font_size=36;label.pixel_size=.0025;label.modulate=Color("c4d8bf");label.outline_size=0;label.billboard=BaseMaterial3D.BILLBOARD_ENABLED;label.no_depth_test=true;stage.add_child(label)
	var camera=Camera3D.new();stage.add_child(camera);camera.fov=34;camera.position=Vector3(.8,2.1,6.4);camera.look_at(Vector3(0,.63,0));camera.make_current()
	var canvas=CanvasLayer.new();root.add_child(canvas)
	var title=Label.new();title.text="ARTIFICIAL EVOLUTION  /  ANIMAL MODELS";title.position=Vector2(32,28);title.add_theme_font_size_override("font_size",24);title.add_theme_color_override("font_color",Color("233a30"));canvas.add_child(title)
	var caption=Label.new();caption.text="Blender asset review · CC0 models by CDmir / TinyWorlds and NewDLC · Natural coat variations · GPU gait animation";caption.position=Vector2(32,70);caption.add_theme_font_size_override("font_size",16);caption.add_theme_color_override("font_color",Color("3b5548"));canvas.add_child(caption)
func _process(delta: float) -> bool:
	if animals.is_empty():return false
	elapsed+=delta;frames+=1
	for animal in animals:animal._pose(review_clip,review_phase)
	if frames==30:call_deferred("_capture")
	return false
func _capture() -> void:
	await RenderingServer.frame_post_draw
	var result=root.get_texture().get_image().save_png(output)
	print("AE2_ANIMAL_GALLERY ",result);quit(0 if result==OK else 1)
