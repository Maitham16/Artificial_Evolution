extends Node3D
const State = preload("res://scripts/python_state.gd")
var camera: Camera3D
var model
var bodies: Dictionary = {}
var food_meshes: MultiMeshInstance3D
var decor: Node3D
var selection: MeshInstance3D
var sensing: MeshInstance3D
var yaw: float = 0.65
var pitch: float = 0.84
var distance: float = 51.0
var target := Vector3.ZERO
var arena: Node3D
var transfers: MeshInstance3D
var geometry_signature=""
var source_run=""
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
	arena=Node3D.new();add_child(arena)
	camera=Camera3D.new();camera.fov=48;camera.near=.1;camera.far=200;add_child(camera);camera.make_current()
	selection=_ring(.58,.64,Color("f8e2af"));selection.position.y=.08;selection.visible=false
	sensing=_ring(7.96,8.0,Color(.65,.82,.74,.28));sensing.position.y=.035;sensing.visible=false
	decor=Node3D.new();add_child(decor)
	transfers=MeshInstance3D.new();transfers.mesh=ImmediateMesh.new();add_child(transfers)
	var transfer_material=StandardMaterial3D.new();transfer_material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;transfer_material.albedo_color=Color("e3d49e");transfers.material_override=transfer_material
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
	model=value;geometry_signature="";selected_id="";target=Vector3.ZERO

func _rebuild_arena() -> void:
	for child in arena.get_children():child.queue_free()
	for child in decor.get_children():child.queue_free()
	var width=float(model.width)/State.UNITS;var height=float(model.height)/State.UNITS
	var plane=MeshInstance3D.new();var mesh=PlaneMesh.new();mesh.size=Vector2(width,height);plane.mesh=mesh;plane.material_override=ground_material;arena.add_child(plane)
	_box(Vector3(0,-.8,0),Vector3(width+2,1.55,height+2),Color("273d3c"),arena)
	for side in [-1,1]:
		_box(Vector3(side*(width/2+.2),.12,0),Vector3(.15,.28,height+.7),Color("a6af8d"),arena)
		_box(Vector3(0,.12,side*(height/2+.2)),Vector3(width+.7,.28,.15),Color("a6af8d"),arena)
	for i in range(12):
		var rock=rock_scene.instantiate();rock.position=Vector3(-width/2+1+i*(width-2)/11,-.05,-height/2-.8 if i%2==0 else height/2+.8);rock.scale=Vector3.ONE*.5;arena.add_child(rock)
	for region in model.groups:
		for side in [-1,1]:
			_box(Vector3(region.get_center().x+side*region.size.x/2,.045,region.get_center().y),Vector3(.06,.06,region.size.y),Color("718779"),decor)
			_box(Vector3(region.get_center().x,.045,region.get_center().y+side*region.size.y/2),Vector3(region.size.x,.06,.06),Color("718779"),decor)
	for box in model.barriers:
		_box(Vector3(box.get_center().x,.6,box.get_center().y),Vector3(box.size.x,1.2,box.size.y),Color("556865"),decor)
	for hazard in model.hazards:
		var area=MeshInstance3D.new();var disc=PlaneMesh.new();disc.size=Vector2.ONE*hazard.radius*2;area.mesh=disc;area.position=Vector3(hazard.position.x,.025,hazard.position.y)
		var material=ShaderMaterial.new();material.shader=load("res://assets/materials/hazard.gdshader");area.material_override=material;decor.add_child(area)
		var label=Label3D.new();label.text="−%.0f energy/s" % model.hazard_cost;label.font_size=42;label.pixel_size=.025;label.outline_size=3;label.no_depth_test=true;label.position=area.position+Vector3(0,.8,0);label.billboard=BaseMaterial3D.BILLBOARD_ENABLED;label.modulate=Color("ffa7a0");decor.add_child(label)
	if food_meshes==null:
		food_meshes=MultiMeshInstance3D.new()
		var multi=MultiMesh.new();multi.transform_format=MultiMesh.TRANSFORM_3D;multi.mesh=_first_mesh(food_scene.instantiate());food_meshes.multimesh=multi
		var material=StandardMaterial3D.new();material.albedo_color=Color("9fdb78");material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;material.roughness=.4;food_meshes.material_override=material;add_child(food_meshes)
	var colors={"uniform":Color("334937"),"clustered":Color("2f473a"),"sparse":Color("625d41"),"barren":Color("655c4c"),"seasonal":Color("52634c")}
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
	if model==null or model.run_id.is_empty() or camera==null:return
	visual_time+=delta
	var signature=model.run_id+str(model.generation)+str(model.width)+str(model.height)+str(model.barriers)+str(model.hazards)+str(model.groups)
	if signature!=geometry_signature:
		_rebuild_arena();geometry_signature=signature
	if source_run!=model.run_id:
		for body in bodies.values():body.queue_free()
		bodies.clear();reset_camera();source_run=model.run_id
	var poses=model.sample_display()
	var living={};var selected=null
	for actor in model.agents:
		if not actor.active:continue
		var id=str(actor.id);living[id]=true
		if not bodies.has(id):
			var body=body_scene.instantiate();add_child(body)
			var material=StandardMaterial3D.new();material.albedo_color=Color("c96f60") if actor.species=="predator" else family_color(str(actor.root)).darkened(.20);material.roughness=.7
			_tint(body,material);bodies[id]=body
		var pose=poses.get(id,{"position":actor.position,"heading":actor.heading});var position: Vector2=pose.position
		var body=bodies[id];body.position=Vector3(position.x,.025+sin(visual_time*11+actor.slot)*.025,position.y)
		body.scale=Vector3.ONE*float(actor.radius)/.35;body.rotation.y=-float(pose.heading);body.rotation.z=sin(visual_time*9+actor.slot)*.035
		if id==selected_id:selected=actor
	for id in bodies.keys():
		if not living.has(id):bodies[id].queue_free();bodies.erase(id)
	if food_meshes.multimesh.instance_count!=model.food.size():food_meshes.multimesh.instance_count=model.food.size()
	for i in range(model.food.size()):
		var position: Vector2=model.food[i]
		food_meshes.multimesh.set_instance_transform(i,Transform3D(Basis().scaled(Vector3.ONE*.65),Vector3(position.x,.1,position.y)))
	transfers.mesh.clear_surfaces()
	var vertices=PackedVector3Array()
	for edge in model.sharing:
		if poses.has(str(edge[0])) and poses.has(str(edge[1])):
			var a: Vector2=poses[str(edge[0])].position;var b: Vector2=poses[str(edge[1])].position
			vertices.append(Vector3(a.x,.32,a.y));vertices.append(Vector3(b.x,.32,b.y))
	if not vertices.is_empty():
		transfers.mesh.surface_begin(Mesh.PRIMITIVE_LINES)
		for vertex in vertices:transfers.mesh.surface_add_vertex(vertex)
		transfers.mesh.surface_end()
	selection.visible=selected!=null;sensing.visible=selected!=null
	if selected:
		var position: Vector2=poses.get(str(selected.id),{"position":selected.position}).position
		selection.position=Vector3(position.x,.08,position.y);selection.scale=Vector3.ONE*maxf(.5,float(selected.radius)/.35)
		sensing.position=Vector3(position.x,.035,position.y);sensing.scale=Vector3.ONE*float(selected.vision)/8

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
	yaw=.65;pitch=.84;target=Vector3.ZERO
	distance=maxf(36,maxf(float(model.width),float(model.height))/State.UNITS*1.02) if model!=null else 51
	var half=Vector2(float(model.width),float(model.height))/State.UNITS/2 if model!=null else Vector2(25,15)
	for attempt in range(20):
		_update_camera()
		var size=camera.get_viewport().get_visible_rect().size
		if size.x<2 or size.y<2:break
		var safe=Rect2(size*.06,size*.88);var fits=true
		for x in [-half.x,half.x]:
			for z in [-half.y,half.y]:
				if not safe.has_point(camera.unproject_position(Vector3(x,0,z))):fits=false
		if fits:break
		distance*=1.07

func pick(point: Vector2) -> String:
	if model==null:return ""
	var origin=camera.project_ray_origin(point);var direction=camera.project_ray_normal(point)
	if abs(direction.y)<.00001:return ""
	var hit=origin+direction*((.3-origin.y)/direction.y)
	var best=INF;var result=""
	for actor in model.agents:
		if not actor.active:continue
		var position: Vector2=model.displayed.get(str(actor.id),{"position":actor.position}).position
		var d=Vector2(hit.x,hit.z).distance_squared_to(position)
		if d<pow(maxf(.5,float(actor.radius)*1.6),2) and d<best:best=d;result=str(actor.id)
	selected_id=result;return result
