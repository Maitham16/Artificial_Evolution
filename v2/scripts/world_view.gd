extends Node3D
const Sim = preload("res://scripts/simulation.gd")
var camera: Camera3D
var model
var bodies: Array = []
var food_meshes: MultiMeshInstance3D
var decor: Node3D
var selection: MeshInstance3D
var sensing: MeshInstance3D
var yaw: float = 0.65
var pitch: float = 0.84
var distance: float = 51.0
var target := Vector3.ZERO
var tracked_generation: int = -1
var selected_id: String = ""
var visual_time: float = 0.0
var body_scene = preload("res://assets/models/creature.glb")
var food_scene = preload("res://assets/models/nutrient.glb")
var rock_scene = preload("res://assets/models/basalt.glb")
var ground_material: ShaderMaterial

static func family_color(root: String) -> Color:
	return Color.from_hsv(float(root.sha256_text().substr(0,6).hex_to_int())/16777215.0,.30,.88)

func _ready() -> void:
	var environment=WorldEnvironment.new()
	var env=Environment.new()
	env.background_mode=Environment.BG_COLOR;env.background_color=Color("15272a")
	env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;env.ambient_light_color=Color("a8b9ab");env.ambient_light_energy=.28
	env.tonemap_mode=Environment.TONE_MAPPER_FILMIC
	environment.environment=env;add_child(environment)
	var sun=DirectionalLight3D.new();sun.rotation_degrees=Vector3(-58,-35,0);sun.light_color=Color("fff1ce");sun.light_energy=.85
	sun.shadow_enabled=true;sun.directional_shadow_max_distance=100;add_child(sun)
	var fill=DirectionalLight3D.new();fill.rotation_degrees=Vector3(-35,130,0);fill.light_color=Color("acc9dc");fill.light_energy=.16;add_child(fill)
	ground_material=ShaderMaterial.new();ground_material.shader=load("res://assets/materials/ground.gdshader")
	var plane=MeshInstance3D.new();var mesh=PlaneMesh.new();mesh.size=Vector2(50,30);plane.mesh=mesh;plane.material_override=ground_material;add_child(plane)
	_box(Vector3(0,-.8,0),Vector3(52,1.55,32),Color("273d3c"),self)
	for side in [-1,1]:
		_box(Vector3(side*25.2,.12,0),Vector3(.15,.28,30.7),Color("a6af8d"),self)
		_box(Vector3(0,.12,side*15.2),Vector3(50.7,.28,.15),Color("a6af8d"),self)
	for i in range(12):
		var rock=rock_scene.instantiate();rock.position=Vector3(-24+i*4.4,-.05,-15.8 if i%2==0 else 15.8);rock.scale=Vector3.ONE*.5;add_child(rock)
	camera=Camera3D.new();camera.fov=48;camera.near=.1;camera.far=200;add_child(camera);camera.make_current()
	selection=_ring(.58,.64,Color("f8e2af"));selection.position.y=.08;selection.visible=false
	sensing=_ring(7.96,8.0,Color(.65,.82,.74,.28));sensing.position.y=.035;sensing.visible=false
	decor=Node3D.new();add_child(decor)
	_update_camera()

func _box(pos: Vector3, dimensions: Vector3, color: Color, parent: Node3D) -> MeshInstance3D:
	var node=MeshInstance3D.new();var mesh=BoxMesh.new();mesh.size=dimensions;node.mesh=mesh;node.position=pos
	var mat=StandardMaterial3D.new();mat.albedo_color=color;mat.roughness=.8;node.material_override=mat;parent.add_child(node);return node

func _ring(inner: float, outer: float, color: Color) -> MeshInstance3D:
	var node=MeshInstance3D.new();var mesh=TorusMesh.new();mesh.inner_radius=inner;mesh.outer_radius=outer;mesh.rings=48;mesh.ring_segments=6;node.mesh=mesh
	var mat=StandardMaterial3D.new();mat.albedo_color=color;mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	if color.a<1:mat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	node.material_override=mat;add_child(node);return node

func set_model(value) -> void:
	model=value;tracked_generation=-1;selected_id="";target=Vector3.ZERO

func _rebuild() -> void:
	for body in bodies:body.queue_free()
	bodies.clear()
	for child in decor.get_children():child.queue_free()
	for c in model.agents:
		var body=body_scene.instantiate();add_child(body)
		var material=StandardMaterial3D.new();material.albedo_color=family_color(c.root).darkened(.20);material.roughness=.7
		_tint(body,material)
		bodies.append(body)
	for box in model.barriers:
		_box(Vector3(box.get_center().x,.6,box.get_center().y),Vector3(box.size.x,1.2,box.size.y),Color("556865"),decor)
	for h in model.hazards:
		var area=MeshInstance3D.new();var mesh=PlaneMesh.new();mesh.size=Vector2.ONE*h.radius*2;area.mesh=mesh;area.position=Vector3(h.position.x,.025,h.position.y)
		var mat=ShaderMaterial.new();mat.shader=load("res://assets/materials/hazard.gdshader");area.material_override=mat;decor.add_child(area)
		var label=Label3D.new();label.text="−12 energy/s";label.font_size=42;label.pixel_size=.025;label.outline_size=3;label.no_depth_test=true;label.position=area.position+Vector3(0,.8,0);label.billboard=BaseMaterial3D.BILLBOARD_ENABLED;label.modulate=Color("ffa7a0");decor.add_child(label)
	if food_meshes:food_meshes.queue_free()
	food_meshes=MultiMeshInstance3D.new()
	# MultiMesh represents pellets; detailed Blender nutrient mesh is shared.
	var source_mesh=_first_mesh(food_scene.instantiate())
	var multi=MultiMesh.new();multi.transform_format=MultiMesh.TRANSFORM_3D;multi.mesh=source_mesh;multi.instance_count=model.food.size();food_meshes.multimesh=multi
	var material=StandardMaterial3D.new();material.albedo_color=Color("9fdb78");material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;material.emission_enabled=true;material.emission=Color("78a548");material.emission_energy_multiplier=.35;material.roughness=.4;food_meshes.material_override=material;add_child(food_meshes)
	tracked_generation=model.generation
	var colors={"uniform":Color("334937"),"clustered":Color("2f473a"),"sparse":Color("625d41"),"hazards":Color("40534c"),"seasons":Color("52634c"),"barren":Color("655c4c")}
	ground_material.set_shader_parameter("soil_color",colors.get(model.config.environment,Color("334937")))

func _first_mesh(node: Node) -> Mesh:
	var result: Mesh
	if node is MeshInstance3D:result=node.mesh
	else:
		for child in node.get_children():
			if result==null:result=_find_mesh(child)
	node.free();return result

func _find_mesh(node: Node) -> Mesh:
	if node is MeshInstance3D:return node.mesh
	for child in node.get_children():
		var found=_find_mesh(child)
		if found:return found
	return null

func _tint(node: Node, mat: Material) -> void:
	if node is MeshInstance3D and (str(node.name).begins_with("Body") or str(node.name).begins_with("Head") or str(node.name).begins_with("Tip")):node.material_override=mat
	for child in node.get_children():_tint(child,mat)

func update_view(delta: float) -> void:
	if model==null or camera==null:return
	visual_time+=delta
	if tracked_generation!=model.generation:_rebuild()
	var selected=null
	for i in range(model.agents.size()):
		var c=model.agents[i];var body=bodies[i]
		body.visible=c.alive
		body.position=Vector3(c.position.x,.025+sin(visual_time*11+c.slot)*.025,c.position.y)
		body.rotation.y=-c.heading
		body.rotation.z=sin(visual_time*9+c.slot)*.035
		if c.id==selected_id and c.alive:selected=c
	for i in range(model.food.size()):
		var p: Vector2=model.food[i]
		var transform=Transform3D(Basis().scaled(Vector3.ONE*.8),Vector3(p.x,.12+sin(visual_time*2+i)*.04,p.y))
		food_meshes.multimesh.set_instance_transform(i,transform)
	selection.visible=selected!=null;sensing.visible=selected!=null
	if selected:
		selection.position=Vector3(selected.position.x,.08,selected.position.y);sensing.position=Vector3(selected.position.x,.035,selected.position.y)

func _update_camera() -> void:
	if camera==null:return
	camera.position=target+Vector3(sin(yaw)*cos(pitch),sin(pitch),cos(yaw)*cos(pitch))*distance
	camera.look_at(target)

func orbit(motion: Vector2) -> void:
	yaw-=motion.x*.007;pitch=clampf(pitch+motion.y*.006,.25,1.35);_update_camera()

func zoom(direction: float) -> void:
	distance=clampf(distance*pow(1.1,direction),15,90);_update_camera()

func pan(motion: Vector2) -> void:
	var right=camera.global_basis.x;var forward=Vector3(camera.global_basis.z.x,0,camera.global_basis.z.z).normalized()
	target-=right*motion.x*distance*.001;target-=forward*motion.y*distance*.001;target.y=0;_update_camera()

func reset_camera() -> void:
	yaw=.65;pitch=.84;distance=51;target=Vector3.ZERO;_update_camera()

func pick(point: Vector2) -> String:
	if model==null:return ""
	var origin=camera.project_ray_origin(point);var direction=camera.project_ray_normal(point)
	if abs(direction.y)<.00001:return ""
	var hit=origin+direction*((.3-origin.y)/direction.y)
	var best=.9*.9;var result=""
	for c in model.agents:
		if not c.alive:continue
		var d=Vector2(hit.x,hit.z).distance_squared_to(c.position)
		if d<best:best=d;result=c.id
	selected_id=result;return result
