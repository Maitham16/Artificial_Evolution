extends Node3D
## Living GPU-skinned animals share draw calls. Source identities stay in AnimalView.
var groups={}
var texture: ImageTexture
var capacity=128
var members: Array=[]
var statistics={"animals":0,"draw_batches":0}
func _ready():texture=ImageTexture.create_from_image(Image.create(4,capacity,false,Image.FORMAT_RGBAF))
func update(bodies: Dictionary) -> void:
	var animals=[]
	for body in bodies.values():
		if not body.detailed and not body.dead:animals.append(body)
	var included={}
	for body in animals:included[body.get_instance_id()]=true
	for body in members:
		if is_instance_valid(body) and not included.has(body.get_instance_id()):body.set_batched(false)
	members=animals
	var resized=false
	while capacity<animals.size():capacity*=2;resized=true
	var image=Image.create(4,capacity,false,Image.FORMAT_RGBAF)
	var batches={}
	for slot in animals.size():
		var body=animals[slot];body.set_batched(true)
		var pose=body.gpu_parameters
		image.set_pixel(0,slot,Color(pose.base.x,pose.base.y,pose.base.z,pose.blend))
		image.set_pixel(1,slot,Color(pose.previous.x,pose.previous.y,pose.previous.z,pose.amount))
		image.set_pixel(2,slot,Color(pose.upper.x,pose.upper.y,pose.upper.z,1))
		image.set_pixel(3,slot,body.coat_color.srgb_to_linear())
		for index in body.meshes.size():
			var key=body.model_key+":"+str(index)+":"+str(body.shadows_enabled)
			if not groups.has(key):_group(key,body.meshes[index],body.shadows_enabled)
			if not batches.has(key):batches[key]=[]
			batches[key].append([body.meshes[index].global_transform,(slot+.5)/capacity])
	if resized:texture.set_image(image)
	else:texture.update(image)
	for key in groups:
		var node=groups[key];var entries=batches.get(key,[]);node.visible=not entries.is_empty()
		var multi=node.multimesh
		if multi.instance_count!=entries.size():multi.instance_count=entries.size()
		for index in entries.size():
			multi.set_instance_transform(index,entries[index][0]);multi.set_instance_custom_data(index,Color(entries[index][1],0,0,0))
	statistics={"animals":animals.size(),"draw_batches":batches.size(),"pose_texture_capacity":capacity}
func _group(key: String,source: MeshInstance3D,shadows: bool) -> void:
	# Surface overrides differ by anatomical part; coats are now per-instance data.
	var mesh=source.mesh.duplicate()
	for surface in mesh.get_surface_count():
		var material=source.get_active_material(surface).duplicate()
		material.set_shader_parameter("batch_mode",true);material.set_shader_parameter("gpu_skeleton",true)
		material.set_shader_parameter("instance_poses",texture)
		material.set_shader_parameter("batch_tint",material.get_shader_parameter("coat_tint")!=Color.WHITE)
		mesh.surface_set_material(surface,material)
	var multi=MultiMesh.new();multi.transform_format=MultiMesh.TRANSFORM_3D;multi.use_custom_data=true;multi.mesh=mesh
	var node=MultiMeshInstance3D.new();node.multimesh=multi;node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(node);groups[key]=node
