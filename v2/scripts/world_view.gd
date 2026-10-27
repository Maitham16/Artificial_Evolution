extends Node3D
const State = preload("res://scripts/python_state.gd")
const Nature = preload("res://scripts/nature_scene.gd")
var nature
var camera_focus=Vector3.ZERO
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
var research_guides=true
var selected_id: String = ""
var visual_time: float = 0.0
var body_scene = preload("res://assets/models/creature.glb")
var food_scene = preload("res://assets/models/nutrient.glb")
var rock_scene = preload("res://assets/models/basalt.glb")
var ground_material: ShaderMaterial

static func family_color(root: String) -> Color:
	return Color.from_hsv(float(root.sha256_text().substr(0,6).hex_to_int())/16777215.0,.30,.88)

func _ready() -> void:
	nature=Nature.new();nature.name="LivingLandscape";add_child(nature)
	ground_material=nature.ground_material
	arena=Node3D.new();add_child(arena)
	camera=Camera3D.new();camera.fov=48;camera.near=.1;camera.far=1800;add_child(camera);camera.make_current()
	selection=_ring(.58,.64,Color("f8e2af"));selection.position.y=.08;selection.visible=false
	sensing=_ring(7.96,8.0,Color(.65,.82,.74,.28));sensing.position.y=.035;sensing.visible=false
	decor=Node3D.new();add_child(decor)
	transfers=MeshInstance3D.new();transfers.mesh=ImmediateMesh.new();add_child(transfers)
	var transfer_material=StandardMaterial3D.new();transfer_material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;transfer_material.albedo_color=Color("e3d49e");transfers.material_override=transfer_material
	_update_camera(true)

func _ring(inner: float, outer: float, color: Color) -> MeshInstance3D:
	var node=MeshInstance3D.new();var mesh=TorusMesh.new();mesh.inner_radius=inner;mesh.outer_radius=outer;mesh.rings=48;mesh.ring_segments=6;node.mesh=mesh
	var mat=StandardMaterial3D.new();mat.albedo_color=color;mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
	if color.a<1:mat.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA
	node.material_override=mat;add_child(node);return node

func set_model(value) -> void:
	model=value;geometry_signature="";selected_id="";target=Vector3.ZERO

func surface_height(point: Vector2) -> float:return nature.height_at(point) if nature!=null else 0.0

func _rebuild_arena() -> void:
	for child in decor.get_children():child.queue_free()
	var width=float(model.width)/State.UNITS;var height=float(model.height)/State.UNITS
	nature.configure(width,height)
	if not model.groups.is_empty():
		var lines=ImmediateMesh.new();lines.surface_begin(Mesh.PRIMITIVE_LINES)
		for region in model.groups:
			var corners=[region.position,region.position+Vector2(region.size.x,0),region.end,region.position+Vector2(0,region.size.y)]
			for edge in range(4):
				var a: Vector2=corners[edge];var b: Vector2=corners[(edge+1)%4]
				var pieces=maxi(1,ceili(a.distance_to(b)))
				for piece in range(pieces):
					for t in [float(piece)/pieces,float(piece+1)/pieces]:
						var p=a.lerp(b,t);lines.surface_add_vertex(Vector3(p.x,surface_height(p)+.065,p.y))
		lines.surface_end()
		var boundaries=MeshInstance3D.new();boundaries.name="GroupBoundaries";boundaries.mesh=lines
		var ink=StandardMaterial3D.new();ink.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;ink.albedo_color=Color("c6c9a1");boundaries.material_override=ink;decor.add_child(boundaries)
	for box in model.barriers:
		_stone_wall(box)
	for hazard in model.hazards:
		var area=MeshInstance3D.new();area.mesh=_surface_patch(hazard.position,hazard.radius)
		var material=ShaderMaterial.new();material.shader=load("res://assets/materials/hazard.gdshader");area.material_override=material;decor.add_child(area)
		var label=Label3D.new();label.text="−%.0f energy/s" % model.hazard_cost;label.font_size=42;label.pixel_size=.025;label.outline_size=3;label.no_depth_test=true;label.position=Vector3(hazard.position.x,surface_height(hazard.position)+.8,hazard.position.y);label.billboard=BaseMaterial3D.BILLBOARD_ENABLED;label.modulate=Color("ffa7a0");decor.add_child(label)
	if food_meshes==null:
		food_meshes=MultiMeshInstance3D.new()
		var multi=MultiMesh.new();multi.transform_format=MultiMesh.TRANSFORM_3D;multi.mesh=_first_mesh(food_scene.instantiate());food_meshes.multimesh=multi
		var material=StandardMaterial3D.new();material.albedo_color=Color("9fdb78");material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;material.roughness=.4;food_meshes.material_override=material;add_child(food_meshes)

func _surface_patch(center: Vector2,radius: float) -> Mesh:
	# Project scientific hazard overlays onto display terrain; retain Python XZ extents.
	var tool=SurfaceTool.new();tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	var count=maxi(8,ceili(radius*4))
	for z in range(count):
		for x in range(count):
			for corner in [Vector2(0,0),Vector2(1,0),Vector2(0,1),Vector2(1,0),Vector2(1,1),Vector2(0,1)]:
				var uv=(Vector2(x,z)+corner)/count
				var p=center+(uv*2-Vector2.ONE)*radius
				tool.set_uv(uv);tool.set_normal(nature.normal_at(p));tool.add_vertex(Vector3(p.x,surface_height(p)+.06,p.y))
	return tool.commit()

func _stone_wall(box: Rect2) -> void:
	var mesh=nature._asset("rock_07")
	var horizontal=box.size.x>box.size.y;var length=maxf(box.size.x,box.size.y)
	var count=maxi(2,ceili(length/.55));var multi=MultiMesh.new();multi.transform_format=MultiMesh.TRANSFORM_3D;multi.mesh=mesh;multi.instance_count=count*2
	for i in range(count):
		var p=box.position+box.size/2
		if horizontal:p.x=box.position.x+float(i+.5)/count*box.size.x
		else:p.y=box.position.y+float(i+.5)/count*box.size.y
		for row in range(2):
			var basis=Basis(Vector3.UP,i*2.39+row).scaled(Vector3(4.2,3.8,4.2))
			multi.set_instance_transform(i*2+row,Transform3D(basis,Vector3(p.x,surface_height(p)+row*.43,p.y)))
	var wall=MultiMeshInstance3D.new();wall.multimesh=multi;decor.add_child(wall)


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
		var body=bodies[id];body.position=Vector3(position.x,surface_height(position)+.025+sin(visual_time*11+actor.slot)*.018,position.y)
		var normal: Vector3=nature.normal_at(position)
		var direction=Vector3(cos(float(pose.heading)),0,sin(float(pose.heading)))
		var forward=direction.slide(normal).normalized();var side=forward.cross(normal).normalized()
		body.basis=Basis(forward,side.cross(forward).normalized(),side).scaled(Vector3.ONE*float(actor.radius)/.35)
		if id==selected_id:selected=actor
	for id in bodies.keys():
		if not living.has(id):bodies[id].queue_free();bodies.erase(id)
	if food_meshes.multimesh.instance_count!=model.food.size():food_meshes.multimesh.instance_count=model.food.size()
	for i in range(model.food.size()):
		var position: Vector2=model.food[i]
		food_meshes.multimesh.set_instance_transform(i,Transform3D(Basis().scaled(Vector3.ONE*.65),Vector3(position.x,surface_height(position)+.10,position.y)))
	transfers.mesh.clear_surfaces()
	var vertices=PackedVector3Array()
	for edge in model.sharing:
		if poses.has(str(edge[0])) and poses.has(str(edge[1])):
			var a: Vector2=poses[str(edge[0])].position;var b: Vector2=poses[str(edge[1])].position
			vertices.append(Vector3(a.x,surface_height(a)+.32,a.y));vertices.append(Vector3(b.x,surface_height(b)+.32,b.y))
	if not vertices.is_empty():
		transfers.mesh.surface_begin(Mesh.PRIMITIVE_LINES)
		for vertex in vertices:transfers.mesh.surface_add_vertex(vertex)
		transfers.mesh.surface_end()
	var groups=decor.get_node_or_null("GroupBoundaries")
	if groups:groups.visible=research_guides
	selection.visible=selected!=null and research_guides;sensing.visible=selected!=null and research_guides
	if selected:
		var position: Vector2=poses.get(str(selected.id),{"position":selected.position}).position
		selection.position=Vector3(position.x,surface_height(position)+.1,position.y);selection.scale=Vector3.ONE*maxf(.5,float(selected.radius)/.35)
		sensing.position=Vector3(position.x,surface_height(position)+.10,position.y);sensing.scale=Vector3.ONE*float(selected.vision)/8

func _update_camera(immediate: bool=false) -> void:
	if camera==null:return
	if immediate:
		camera_focus=target
		camera.position=target+Vector3(sin(yaw)*cos(pitch),sin(pitch),cos(yaw)*cos(pitch))*distance
		camera.look_at(target)

func _process(delta: float) -> void:
	if camera==null:return
	var desired=target+Vector3(sin(yaw)*cos(pitch),sin(pitch),cos(yaw)*cos(pitch))*distance
	desired.y=maxf(desired.y,surface_height(Vector2(desired.x,desired.z))+.65)
	var weight=1-exp(-delta*8)
	camera.position=camera.position.lerp(desired,weight);camera.position.y=maxf(camera.position.y,surface_height(Vector2(camera.position.x,camera.position.z))+.4);camera_focus=camera_focus.lerp(target,weight)
	if camera.position.distance_squared_to(camera_focus)>.01:camera.look_at(camera_focus)

func ground_view() -> void:
	yaw=.86;pitch=.12;distance=26
	var p=Vector2.ZERO
	if model!=null and model.displayed.has(selected_id):p=model.displayed[selected_id].position
	target=Vector3(p.x,surface_height(p)+.65,p.y)

func valley_view() -> void:
	yaw=.90;pitch=.30;distance=88
	var p=Vector2(-12,-6)
	target=Vector3(p.x,surface_height(p)+1.0,p.y)

func set_quality(index: int) -> void:nature.set_quality(index)

func orbit(motion: Vector2) -> void:
	yaw-=motion.x*.007;pitch=clampf(pitch+motion.y*.006,.08,1.35);_update_camera()

func zoom(direction: float) -> void:
	distance=clampf(distance*pow(1.1,direction),3.5,180);_update_camera()

func pan(motion: Vector2) -> void:
	var right=camera.global_basis.x;var forward=Vector3(camera.global_basis.z.x,0,camera.global_basis.z.z).normalized()
	target-=right*motion.x*distance*.001;target-=forward*motion.y*distance*.001;target.y=surface_height(Vector2(target.x,target.z))+.4;_update_camera()

func reset_camera() -> void:
	yaw=.65;pitch=.70;target=Vector3(0,surface_height(Vector2.ZERO)+.35,0)
	distance=maxf(36,maxf(float(model.width),float(model.height))/State.UNITS*1.02) if model!=null else 51
	var half=Vector2(float(model.width),float(model.height))/State.UNITS/2 if model!=null else Vector2(25,15)
	for attempt in range(20):
		_update_camera(true)
		var size=camera.get_viewport().get_visible_rect().size
		if size.x<2 or size.y<2:break
		var safe=Rect2(size*.06,size*.88);var fits=true
		for x in [-half.x,half.x]:
			for z in [-half.y,half.y]:
				if not safe.has_point(camera.unproject_position(Vector3(x,surface_height(Vector2(x,z)),z))):fits=false
		if fits:break
		distance*=1.07

func pick(point: Vector2) -> String:
	if model==null:return ""
	var origin=camera.project_ray_origin(point);var direction=camera.project_ray_normal(point)
	if abs(direction.y)<.00001:return ""
	var time=(surface_height(Vector2(origin.x,origin.z))+.3-origin.y)/direction.y
	for iteration in range(9):
		var sample_point=origin+direction*time
		time=(surface_height(Vector2(sample_point.x,sample_point.z))+.3-origin.y)/direction.y
	var hit=origin+direction*time
	var best=INF;var result=""
	for actor in model.agents:
		if not actor.active:continue
		var position: Vector2=model.displayed.get(str(actor.id),{"position":actor.position}).position
		var d=Vector2(hit.x,hit.z).distance_squared_to(position)
		if d<pow(maxf(.5,float(actor.radius)*1.6),2) and d<best:best=d;result=str(actor.id)
	selected_id=result;return result
