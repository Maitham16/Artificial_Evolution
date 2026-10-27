extends Node3D
## Display-only skin, coat and gait for one authoritative Python lifetime.
const COAT=preload("res://assets/materials/animal_coat.gdshader")
const MODELS={"doe":preload("res://assets/animals/doe/doe.gltf"),"stag":preload("res://assets/animals/stag/stag.gltf"),"wolf":preload("res://assets/animals/wolf/wolf.gltf")}
const HERBIVORE_COATS=[Color(.90,.83,.73),Color(1.04,.97,.87),Color(.78,.72,.66),Color(.98,.89,.76),Color(1.02,1.0,.95)]
const PREDATOR_COATS=[Color(.84,.88,.92),Color(.87,.81,.71),Color(.66,.67,.65),Color(1.0,.98,.92)]
var python_id=""
var lineage_id=""
var model_key=""
var coat_color=Color.WHITE
var appearance_size=1.0
var skin: Node3D
var materials: Array=[]
var model_data: Dictionary
static var model_catalog: Dictionary={}
var clips={}
var current_clip=""
var gait_phase=0.0
var idle_phase=0.0
var last_position=Vector2.ZERO
var has_position=false
var stationary_time=0.0
var animation_elapsed=0.0
var pending_distance=0.0
var visual_bounds=AABB(Vector3(-.7,0,-.3),Vector3(1.4,1.5,.6))

static func appearance(actor: Dictionary) -> Dictionary:
	var family=str(actor.root).sha256_text().substr(0,7).hex_to_int()
	var individual=str(actor.id).sha256_text().substr(0,7).hex_to_int()
	var predator=actor.get("species")=="predator"
	return {"model":"wolf" if predator else "stag" if family%3==0 else "doe",
		"coat":PREDATOR_COATS[family%PREDATOR_COATS.size()] if predator else HERBIVORE_COATS[family%HERBIVORE_COATS.size()],
		"size":.94+float(individual%121)/1000.0,"phase":float(individual%1000)/1000.0}

func configure(actor: Dictionary) -> void:
	python_id=str(actor.id);lineage_id=str(actor.root)
	var style=appearance(actor);model_key=style.model;coat_color=style.coat;appearance_size=style.size;gait_phase=style.phase;idle_phase=style.phase
	name="Animal_"+python_id.replace(":","_")
	set_meta("python_id",python_id);set_meta("python_lineage",lineage_id);set_meta("python_species",actor.get("species"))
	skin=MODELS[model_key].instantiate();add_child(skin);skin.scale*=appearance_size
	if model_catalog.is_empty():
		for record in JSON.parse_string(FileAccess.get_file_as_string("res://assets/animals/models.json")):model_catalog[record.model]=record
	model_data=model_catalog[model_key].vat;clips=model_data.clips
	var pose_bounds=AABB(Vector3(model_data.position_min[0],model_data.position_min[1],model_data.position_min[2]),Vector3(model_data.position_span[0],model_data.position_span[1],model_data.position_span[2]))
	var bounds_ready=false
	for node in skin.find_children("*","MeshInstance3D",true,false):
		for surface in range(node.mesh.get_surface_count()):
			var source=node.mesh.surface_get_material(surface)
			if not source is BaseMaterial3D:continue
			var eye="eye" in source.resource_name.to_lower()
			var material=ShaderMaterial.new();material.shader=COAT
			material.set_shader_parameter("coat_texture",source.albedo_texture)
			material.set_shader_parameter("coat_tint",Color.WHITE if eye else coat_color)
			material.set_shader_parameter("base_color",source.albedo_color)
			material.set_shader_parameter("has_texture",source.albedo_texture!=null)
			material.set_shader_parameter("surface_roughness",.18 if eye else .86)
			material.set_shader_parameter("desaturation",.63 if model_key=="wolf" else .0 if eye else .26)
			material.set_shader_parameter("has_normal",source.normal_texture!=null)
			if source.normal_texture:material.set_shader_parameter("coat_normal",source.normal_texture)
			material.set_shader_parameter("gait_positions",load("res://assets/animals/"+model_key+"/positions.exr"))
			material.set_shader_parameter("gait_normals",load("res://assets/animals/"+model_key+"/normals.exr"))
			material.set_shader_parameter("position_min",Vector3(model_data.position_min[0],model_data.position_min[1],model_data.position_min[2]))
			material.set_shader_parameter("position_span",Vector3(model_data.position_span[0],model_data.position_span[1],model_data.position_span[2]))
			material.set_shader_parameter("frame_uv_step",float(model_data.rows_per_frame)/float(model_data.texture_size[1]))
			node.set_surface_override_material(surface,material);materials.append(material)
			node.custom_aabb=pose_bounds;node.extra_cull_margin=.05
		var relative=global_transform.affine_inverse()*node.global_transform
		var bounds=relative*pose_bounds
		visual_bounds=visual_bounds.merge(bounds) if bounds_ready else bounds;bounds_ready=true
	# Picking and culling cover every baked pose, including raised legs and tails.
	visual_bounds=visual_bounds.grow(.04)
	_pose("Idle",idle_phase)

func _pose(clip: String,phase: float) -> void:
	current_clip=clip
	var data=clips[clip];var frame=fposmod(phase,1.0)*float(data.count)
	var frames=Vector3(float(data.start)+floor(frame),float(data.start)+fposmod(floor(frame)+1,float(data.count)),fposmod(frame,1.0))
	for material in materials:material.set_shader_parameter("pose_frames",frames)

func present(position_xz: Vector2,delta: float,camera_distance: float) -> void:
	if not has_position:last_position=position_xz;has_position=true;return
	var travelled=position_xz.distance_to(last_position);last_position=position_xz
	if delta<=0:return
	pending_distance+=travelled;animation_elapsed+=delta
	stationary_time=stationary_time+delta if travelled<.0001 else 0.0
	var interval=1.0/30 if camera_distance<30 else 1.0/15
	if animation_elapsed<interval:return
	var stride=maxf(.2,1.15*global_basis.x.length()*appearance_size)
	gait_phase+=pending_distance/stride
	idle_phase+=animation_elapsed/6.0
	_pose("Run" if stationary_time<.16 else "Idle",gait_phase if stationary_time<.16 else idle_phase)
	pending_distance=0.0;animation_elapsed=0.0
