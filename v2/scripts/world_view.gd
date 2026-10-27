extends Node3D
const State = preload("res://scripts/python_state.gd")
const Nature = preload("res://scripts/nature_scene.gd")
var nature
var atmosphere
var recent_events: Array=[]
var food_ages={}
var food_render_revision=-1
var food_growth_until=0.0
var body_poses={}
var terrain_pose_updates=0
var food_uploads=0
var selected_food=""
var trails={}
var trail_clock=0.0
var effects: Node3D
var observation_lines: MeshInstance3D
var camera_smoothing=8.0
var camera_focus=Vector3.ZERO
var camera: Camera3D
var model
var bodies: Dictionary = {}
var activity_counts={}
var event_counts={}
var detail_clock=0.0
var detailed_ids: Array=[]
var remnants: Dictionary = {}
var missing_since: Dictionary = {}
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
const Animal=preload("res://scripts/animal_view.gd")
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
	atmosphere=preload("res://scripts/environment_director.gd").new();add_child(atmosphere);atmosphere.bind(nature,camera)
	effects=Node3D.new();effects.name="ConfirmedEventEffects";add_child(effects)
	observation_lines=MeshInstance3D.new();observation_lines.mesh=ImmediateMesh.new();add_child(observation_lines)
	var trail_material=StandardMaterial3D.new();trail_material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;trail_material.albedo_color=Color("d7cda4");trail_material.vertex_color_use_as_albedo=true;observation_lines.material_override=trail_material
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
		var multi=MultiMesh.new();multi.transform_format=MultiMesh.TRANSFORM_3D;multi.mesh=nature._asset("fern_02");food_meshes.multimesh=multi
		food_meshes.name="PythonEdiblePlants";add_child(food_meshes)


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

func update_view(delta: float) -> void:
	if model==null or model.run_id.is_empty() or camera==null:return
	visual_time+=delta
	atmosphere.set_source(model.environment_context)
	var signature=model.run_id+str(model.generation)+str(model.width)+str(model.height)+str(model.barriers)+str(model.hazards)+str(model.groups)
	if signature!=geometry_signature:
		_rebuild_arena();geometry_signature=signature
	if source_run!=model.run_id:
		for body in bodies.values():body.queue_free()
		bodies.clear()
		for body in remnants.values():body.queue_free()
		remnants.clear();missing_since.clear();activity_counts.clear();event_counts.clear();recent_events.clear();food_ages.clear();body_poses.clear();food_render_revision=-1;trails.clear();selected_food=""
		for effect in effects.get_children():effect.queue_free()
		reset_camera();source_run=model.run_id
	var poses=model.sample_display()
	var living={};var selected=null
	for actor in model.agents:
		if not actor.active:continue
		var id=str(actor.id);living[id]=true
		if not bodies.has(id):
			var body=Animal.new();add_child(body);body.configure(actor);bodies[id]=body
		var pose=poses.get(id,{"position":actor.position,"heading":actor.heading});var position: Vector2=pose.position
		var body=bodies[id]
		var pose_key=[position,float(pose.heading),float(actor.radius)]
		if body_poses.get(id)!=pose_key:
			body_poses[id]=pose_key;terrain_pose_updates+=1
			body.position=Vector3(position.x,surface_height(position)+.015,position.y)
			var normal: Vector3=nature.normal_at(position)
			var direction=Vector3(cos(float(pose.heading)),0,sin(float(pose.heading)))
			var forward=direction.slide(normal).normalized();var side=forward.cross(normal).normalized()
			body.basis=Basis(forward,side.cross(forward).normalized(),side).scaled(Vector3.ONE*float(actor.radius)/.45)
		body.set_detailed(id==selected_id or id in detailed_ids)
		body.present(actor,pose,model.display_sim_time,delta,camera.global_position.distance_to(body.global_position))
		activity_counts[body.animation_state]=int(activity_counts.get(body.animation_state,0))+1
		if id==selected_id:selected=actor
	detail_clock+=delta
	if detail_clock>.4:
		detail_clock=0;detailed_ids.clear()
		var candidates=bodies.keys()
		candidates.sort_custom(func(a,b):return camera.global_position.distance_squared_to(bodies[a].global_position)<camera.global_position.distance_squared_to(bodies[b].global_position))
		for id in candidates.slice(0,[2,4,6][nature.quality]):
			if camera.global_position.distance_to(bodies[id].global_position)<22:detailed_ids.append(id)
	for event in model.take_animation_events():
		_record_event(event)
		event_counts[event.kind]=int(event_counts.get(event.kind,0))+int(event.get("count",1))
		var id=str(event.id)
		if event.kind=="death":
			var body=bodies.get(id)
			if body==null:
				body=Animal.new();add_child(body);body.configure(event)
			var point=model.point(float(event.x),float(event.y))
			body.position=Vector3(point.x,surface_height(point)+.015,point.y)
			body.rotation.y=-float(event.heading);body.scale=Vector3.ONE*float(event.radius)/State.UNITS/.45
			body.set_detailed(false);body.event(event);remnants[id]=body;bodies.erase(id);body_poses.erase(id);missing_since.erase(id)
		elif event.kind=="retire":
			if bodies.has(id):bodies[id].queue_free();bodies.erase(id);body_poses.erase(id)
			missing_since.erase(id)
		elif bodies.has(id):bodies[id].event(event)
	for id in bodies.keys():
		if living.has(id):missing_since.erase(id)
		else:
			if not missing_since.has(id):missing_since[id]=0.0
			missing_since[id]+=delta
			# Unknown removals (e.g. a journal gap) never invent a death.
			if missing_since[id]>.35:bodies[id].queue_free();bodies.erase(id);body_poses.erase(id);missing_since.erase(id)
	for id in remnants.keys():
		remnants[id]._present_death(delta)
		activity_counts[remnants[id].animation_state]=int(activity_counts.get(remnants[id].animation_state,0))+1
		if remnants[id].expired:remnants[id].queue_free();remnants.erase(id)
	var food_changed=food_render_revision!=model.food_revision
	if food_changed:
		food_growth_until=visual_time+.35;food_render_revision=model.food_revision
	if food_changed or (delta>0 and visual_time<=food_growth_until) or food_meshes.multimesh.instance_count!=model.food_objects.size():
		if food_meshes.multimesh.instance_count!=model.food_objects.size():food_meshes.multimesh.instance_count=model.food_objects.size()
		var plant_index=0;var living_food={}
		food_uploads+=1
		for id in model.food_objects:
			var plant=model.food_objects[id];var position: Vector2=plant.position;living_food[id]=true
			food_ages[id]=float(food_ages.get(id,.35 if food_ages.is_empty() else 0.0))+delta
			var scale=(.65+.12*sin(float(str(id).hash()%100)))*smoothstep(0,.35,float(food_ages[id]))
			var basis=Basis(Vector3.UP,float(str(id).hash()%628)*.01).scaled(Vector3.ONE*maxf(.01,scale))
			food_meshes.multimesh.set_instance_transform(plant_index,Transform3D(basis,Vector3(position.x,surface_height(position)-.025,position.y)))
			plant_index+=1
		for id in food_ages.keys():
			if not living_food.has(id):food_ages.erase(id)
	_update_observation_trails(delta)
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
	selection.visible=selected!=null;sensing.visible=selected!=null and research_guides
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
	if atmosphere:atmosphere.step(delta)
	var desired=target+Vector3(sin(yaw)*cos(pitch),sin(pitch),cos(yaw)*cos(pitch))*distance
	desired.y=maxf(desired.y,surface_height(Vector2(desired.x,desired.z))+.65)
	var weight=1-exp(-delta*camera_smoothing)
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

func reset_camera(immediate: bool=true) -> void:
	var previous_transform=camera.transform;var previous_focus=camera_focus
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

	if not immediate:camera.transform=previous_transform;camera_focus=previous_focus

func pick(point: Vector2) -> String:
	if model==null:return ""
	var origin=camera.project_ray_origin(point);var direction=camera.project_ray_normal(point)
	var best=INF;var result=""
	for id in bodies:
		var body=bodies[id];var inverse=body.global_transform.affine_inverse()
		var hit=body.visual_bounds.intersects_ray(inverse*origin,inverse.basis*direction)
		if hit!=null:
			var distance_to_hit=origin.distance_squared_to(body.global_transform*hit)
			if distance_to_hit<best:best=distance_to_hit;result=id
	selected_id=result;return result

func animation_summary() -> Dictionary:
	var detailed=0
	for body in bodies.values():
		if body.detailed:detailed+=1
	return {"terrain_pose_updates":terrain_pose_updates,"food_uploads":food_uploads,"active_models":bodies.size(),"detailed_skeletons":detailed,"gpu_bone_models":bodies.size()-detailed,"death_remnants":remnants.size(),"events":event_counts.duplicate(),"observed_visual_states":activity_counts.keys(),"event_gaps":model.animation_gaps if model else 0}

func _record_event(event: Dictionary) -> void:
	# Only confirmed journal receipts create effects. No inferred plant contact or kills.
	if event.kind=="retire":return
	recent_events.push_front(event.duplicate(true))
	if recent_events.size()>256:recent_events.resize(256)
	if event.kind not in ["meal","birth"] or not event.has("x"):return
	if effects.get_child_count()>=20:return
	var point=model.point(float(event.x),float(event.y))
	var p=CPUParticles3D.new();p.amount=8 if event.kind=="meal" else 18;p.lifetime=.9;p.one_shot=true;p.explosiveness=.95;p.local_coords=false
	p.direction=Vector3.UP;p.spread=60;p.initial_velocity_min=.2;p.initial_velocity_max=.6;p.gravity=Vector3(0,-.5,0)
	var leaf=QuadMesh.new();leaf.size=Vector2(.035,.018);var mat=StandardMaterial3D.new();mat.albedo_color=Color("91a75e") if event.kind=="meal" else Color("dfd3a0");mat.billboard_mode=BaseMaterial3D.BILLBOARD_ENABLED;mat.cull_mode=BaseMaterial3D.CULL_DISABLED;leaf.material=mat;p.mesh=leaf
	p.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;p.position=Vector3(point.x,surface_height(point)+.25,point.y);effects.add_child(p)
	p.finished.connect(p.queue_free)

func _update_observation_trails(delta: float) -> void:
	if not research_guides:
		observation_lines.mesh.clear_surfaces();return
	trail_clock+=delta
	var actor=model.actor(selected_id);var ids=[selected_id]
	if actor and actor.get("observed_opponent") is Dictionary:ids.append(str(actor.observed_opponent.id))
	if trail_clock>.12:
		trail_clock=0
		for id in trails.keys():
			if id not in ids:trails.erase(id)
		for id in ids:
			var source=model.actor(id)
			if source and source.active:
				if not trails.has(id):trails[id]=[]
				if trails[id].is_empty() or trails[id][-1].distance_squared_to(source.position)>.002:
					trails[id].append(source.position)
					if trails[id].size()>100:trails[id].pop_front()
	observation_lines.mesh.clear_surfaces()
	if not research_guides or not actor:return
	var vertices=[];var colors=[]
	for id in trails:
		var samples=trails[id]
		for i in range(1,samples.size()):
			for point in [samples[i-1],samples[i]]:
				vertices.append(Vector3(point.x,surface_height(point)+.09,point.y));colors.append(Color("b4d7a7") if id==selected_id else Color("dfac88"))
	var opponent=actor.get("observed_opponent")
	if opponent is Dictionary:
		var a: Vector2=actor.position;var b=model.point(float(opponent.x),float(opponent.y))
		for point in [a,b]:vertices.append(Vector3(point.x,surface_height(point)+.48,point.y));colors.append(Color("e8b578"))
	if not vertices.is_empty():
		observation_lines.mesh.surface_begin(Mesh.PRIMITIVE_LINES)
		for i in range(vertices.size()):observation_lines.mesh.surface_set_color(colors[i]);observation_lines.mesh.surface_add_vertex(vertices[i])
		observation_lines.mesh.surface_end()

func pick_food(point: Vector2) -> String:
	if model==null:return ""
	var origin=camera.project_ray_origin(point);var direction=camera.project_ray_normal(point)
	var best=INF;var result=""
	for id in model.food_objects:
		var plant=model.food_objects[id];var p: Vector2=plant.position
		var center=Vector3(p.x,surface_height(p)+.18,p.y);var along=(center-origin).dot(direction)
		if along>0 and center.distance_to(origin+direction*along)<.36 and along<best:result=id;best=along
	selected_food=result;return result

func focus_event(event: Dictionary) -> String:
	var id=str(event.get("id",""));var actor=model.actor(id)
	if actor and actor.active:
		target=Vector3(actor.position.x,surface_height(actor.position)+.4,actor.position.y);selected_id=id;return id
	if event.has("x"):
		var point=model.point(float(event.x),float(event.y));target=Vector3(point.x,surface_height(point)+.3,point.y)
	return ""

func ecosystem_summary() -> Dictionary:
	return {"scenery":atmosphere.summary(),"python_food_plants":model.food_objects.size(),"recent_confirmed_events":recent_events.size(),"bounded_event_effects":effects.get_child_count(),"selected_food":selected_food,"source":"Python journal and snapshots; weather/daylight are decorative"}
