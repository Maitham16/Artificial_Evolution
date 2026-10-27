extends Node3D
## Actual Skeleton3D bone poses, driven only by received movement and events.
const COAT=preload("res://assets/materials/animal_skin.gdshader")
const MODELS={"doe":preload("res://assets/animals/skeletal/doe/doe.gltf"),"stag":preload("res://assets/animals/skeletal/stag/stag.gltf"),"wolf":preload("res://assets/animals/skeletal/wolf/wolf.gltf")}
const HERBIVORE_COATS=[Color(.90,.83,.73),Color(1.04,.97,.87),Color(.78,.72,.66),Color(.98,.89,.76),Color(1.02,1.0,.95)]
const PREDATOR_COATS=[Color(.84,.88,.92),Color(.87,.81,.71),Color(.66,.67,.65),Color(1.0,.98,.92)]
var shadows_enabled=true
var detailed=false
var detail_initialized=false
var previous_clip="Rest"
var previous_phase=0.0
var meshes: Array=[]
var python_id=""
var lineage_id=""
var model_key=""
var coat_color=Color.WHITE
var appearance_size=1.0
var skin: Node3D
var skeleton: Skeleton3D
var library
var clips={}
var materials: Array=[]
var current_clip="Rest"
var animation_state="Awaiting movement"
var base_clip="Rest"
var gait_phase=0.0
var idle_phase=0.0
var last_position=Vector2.ZERO
var last_heading=0.0
var last_sim_time=-1.0
var last_toward=0.0
var last_away=0.0
var last_visible=0.0
var turn_blend=0.0
var angular_velocity=0.0
var has_position=false
var dead=false
var death_time=0.0
var expired=false
var event_kind=""
var event_time=0.0
var event_duration=0.0
var event_count=0
var growth=1.0
var grow_target=1.0
var phase_elapsed=0.0
var crossfade_elapsed=1.0
var current_pose: Array=[]
var transition_pose: Array=[]
var visual_bounds=AABB(Vector3(-.8,-.15,-.45),Vector3(1.6,1.8,.9))
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
	name="Animal_"+python_id.replace(":","_");set_meta("python_id",python_id);set_meta("python_lineage",lineage_id);set_meta("python_species",actor.get("species"))
	skin=MODELS[model_key].instantiate();add_child(skin)
	for player in skin.find_children("*","AnimationPlayer",true,false):player.free()
	skeleton=skin.find_children("*","Skeleton3D",true,false)[0]
	library=load("res://assets/animals/skeletal/"+model_key+"/poses.res");clips=library.clips
	assert(skeleton.get_bone_count()==library.bone_names.size())
	for bone in skeleton.get_bone_count():assert(skeleton.get_bone_name(bone)==library.bone_names[bone])
	_update_growth(actor,true)
	for node in skin.find_children("*","MeshInstance3D",true,false):
		for surface in node.mesh.get_surface_count():
			var source=node.mesh.surface_get_material(surface)
			if not source is BaseMaterial3D:continue
			var eye="eye" in source.resource_name.to_lower();var material=ShaderMaterial.new();material.shader=COAT
			material.set_shader_parameter("coat_texture",source.albedo_texture);material.set_shader_parameter("coat_tint",Color.WHITE if eye else coat_color)
			material.set_shader_parameter("base_color",source.albedo_color);material.set_shader_parameter("has_texture",source.albedo_texture!=null)
			material.set_shader_parameter("surface_roughness",.18 if eye else .86);material.set_shader_parameter("desaturation",.63 if model_key=="wolf" else 0.0 if eye else .26)
			material.set_shader_parameter("has_normal",source.normal_texture!=null)
			if source.normal_texture:material.set_shader_parameter("coat_normal",source.normal_texture)
			node.set_surface_override_material(surface,material);materials.append(material)
			node.extra_cull_margin=1.5
			node.set_meta("source_skin",node.skin);node.set_meta("source_skeleton",node.skeleton)
			if not node in meshes:meshes.append(node)
			var weights=PackedFloat32Array();weights.resize(64)
			for index in library.upper_weights.size():weights[index]=library.upper_weights[index]
			material.set_shader_parameter("upper_weights",weights)
			material.set_shader_parameter("bone_palette",load("res://assets/animals/skeletal/"+model_key+"/bones.exr"))
			material.set_shader_parameter("palette_size",Vector2(library.gpu_dimensions))
	set_detailed(false)
	_pose("Rest",idle_phase)

func _update_growth(actor: Dictionary,immediate: bool=false) -> void:
	var maturity=float(actor.get("maturity_age",0.0) if actor.get("maturity_age")!=null else 0.0)
	grow_target=1.0
	if maturity>0 and actor.get("parent")!=null:
		var fraction=clampf(float(actor.get("age",0.0))/maturity,0,1)
		grow_target=.65+.35*fraction*fraction*(3-2*fraction)
	if immediate:growth=grow_target;skin.scale=Vector3.ONE*appearance_size*growth

func _sample(clip: String,phase: float,bone: int) -> Transform3D:
	var data=clips[clip];var count=data.poses.size()
	var frame=fposmod(phase,1.0)*count if data.loop else clampf(phase,0,1)*(count-1)
	var first=int(floor(frame));var next=(first+1)%count if data.loop else mini(first+1,count-1)
	return data.poses[first][bone].interpolate_with(data.poses[next][bone],fposmod(frame,1.0))

func set_detailed(value: bool) -> void:
	if detail_initialized and detailed==value:return
	detail_initialized=true;detailed=value;phase_elapsed=1.0
	for mesh in meshes:
		mesh.skin=mesh.get_meta("source_skin") if value else null
		mesh.skeleton=mesh.get_meta("source_skeleton") if value else NodePath("")
	for material in materials:material.set_shader_parameter("gpu_skeleton",not value)
	if not current_pose.is_empty():
		var overlay=_overlay_parameters()
		var phase=idle_phase if base_clip=="Rest" else gait_phase
		var blend=smoothstep(0.0,.22,crossfade_elapsed)
		_gpu_pose(base_clip,phase,blend,overlay.clip,overlay.phase,overlay.amount)
		if value:
			for bone in skeleton.get_bone_count():
				var pose=_sample(base_clip,phase,bone)
				if bone in library.upper_bones and overlay.amount>.001:pose=pose.interpolate_with(_sample(overlay.clip,overlay.phase,bone),overlay.amount)
				if blend<1:pose=_sample(previous_clip,previous_phase,bone).interpolate_with(pose,blend)
				current_pose[bone]=pose;skeleton.set_bone_pose(bone,pose)

func _overlay_parameters() -> Dictionary:
	var result={"clip":"Rest","phase":0.0,"amount":0.0}
	if turn_blend>.001:result={"clip":"TurnLeft" if angular_velocity<0 else "TurnRight","phase":.5,"amount":turn_blend}
	if grow_target<.999:result={"clip":"Grow","phase":idle_phase,"amount":.12}
	if not event_kind.is_empty():result={"clip":event_kind,"phase":event_time/maxf(.1,event_duration),"amount":smoothstep(0.0,.18,event_time)*(1-smoothstep(event_duration-.2,event_duration,event_time))}
	return result

func _gpu_frames(clip: String,phase: float) -> Vector3:
	var data=clips[clip];var count=data.poses.size()
	var frame=fposmod(phase,1.0)*count if data.loop else clampf(phase,0,1)*(count-1)
	var first=floor(frame);var next=fposmod(first+1,count) if data.loop else minf(first+1,count-1)
	return Vector3(float(data.gpu_start)+first,float(data.gpu_start)+next,fposmod(frame,1.0))

func _gpu_pose(clip: String,phase: float,blend: float=1.0,upper: String="Rest",upper_phase: float=0.0,amount: float=0.0) -> void:
	var frames=_gpu_frames(clip,phase);var previous=_gpu_frames(previous_clip,previous_phase);var overlay=_gpu_frames(upper,upper_phase)
	for material in materials:
		material.set_shader_parameter("base_frames",frames);material.set_shader_parameter("previous_frames",previous)
		material.set_shader_parameter("upper_frames",overlay);material.set_shader_parameter("transition",blend);material.set_shader_parameter("upper_blend",amount)

func _pose(clip: String,phase: float) -> void:
	clip="Rest" if clip=="Idle" else clip
	current_clip=clip;current_pose=[]
	for bone in skeleton.get_bone_count():
		var pose=_sample(clip,phase,bone);current_pose.append(pose)
		if detailed:skeleton.set_bone_pose(bone,pose)
	_gpu_pose(clip,phase)

func event(value: Dictionary) -> void:
	event_count+=1
	if value.kind=="death":
		previous_clip=base_clip;previous_phase=idle_phase if base_clip=="Rest" else gait_phase
		dead=true;death_time=0;transition_pose=current_pose.duplicate();crossfade_elapsed=0;animation_state="Dying";return
	if dead:return
	var next="Eat" if value.kind=="meal" else "Reproduce" if value.kind=="reproduce" else "Hunt" if value.kind=="capture" else ""
	if next.is_empty():return
	if event_kind=="Reproduce" and next=="Eat":return
	event_kind=next;event_time=0;event_duration=1.1 if next=="Eat" else 1.2 if next=="Reproduce" else .6

func present(actor: Dictionary,pose: Dictionary,sim_time: float,delta: float,camera_distance: float) -> void:
	if dead:_present_death(delta);return
	var position_xz: Vector2=pose.position;var heading=float(pose.heading)
	if not has_position:
		last_position=position_xz;last_heading=heading;last_sim_time=sim_time;has_position=true
		last_toward=float(pose.get("toward_seconds",0));last_away=float(pose.get("away_seconds",0));last_visible=float(pose.get("opponent_visible_seconds",0))
	var travelled=position_xz.distance_to(last_position);var simulation_delta=maxf(0,sim_time-last_sim_time)
	var observed_speed=travelled/simulation_delta if simulation_delta>.000001 else float(actor.get("speed",0))/20.0
	angular_velocity=angle_difference(last_heading,heading)/simulation_delta if simulation_delta>.000001 else 0.0
	last_position=position_xz;last_heading=heading;last_sim_time=sim_time
	if delta<=0:return
	# Distant bodies retain GPU skeletal motion; only nearby bodies spend shadow passes.
	var cast=camera_distance<34 if shadows_enabled else camera_distance<30
	if cast!=shadows_enabled:
		shadows_enabled=cast
		for mesh in meshes:mesh.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_ON if cast else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var physical_scale=maxf(.1,global_basis.x.length()*appearance_size*growth)
	var next="Rest" if observed_speed<.025 and float(actor.get("speed",0))<.5 else "Run" if observed_speed>(1.35 if base_clip in ["Run","Hunt","Escape"] else 1.65)*physical_scale else "Walk"
	var visible=float(pose.get("opponent_visible_seconds",last_visible));var toward=float(pose.get("toward_seconds",last_toward));var away=float(pose.get("away_seconds",last_away))
	var hunting=actor.get("species")=="predator" and visible>last_visible and toward>last_toward
	var escaping=actor.get("species")=="prey" and visible>last_visible and away>last_away
	last_visible=visible;last_toward=toward;last_away=away
	var display_state="Hunting" if hunting else "Escaping" if escaping else "Resting" if next=="Rest" else "Running" if next=="Run" else "Walking"
	if next=="Run" and (hunting or escaping):next="Hunt" if hunting else "Escape"
	if next!=base_clip:
		previous_clip=base_clip;previous_phase=idle_phase if base_clip=="Rest" else gait_phase
		transition_pose=current_pose.duplicate();crossfade_elapsed=0;base_clip=next
	var stride=float(library.strides["Walk" if base_clip=="Walk" else "Run"])*physical_scale
	gait_phase+=travelled/maxf(.1,stride);idle_phase+=delta/4.0
	_update_growth(actor);growth=lerpf(growth,grow_target,1-exp(-delta*8));skin.scale=Vector3.ONE*appearance_size*growth
	if grow_target<.999:display_state="Growing"
	turn_blend=lerpf(turn_blend,clampf(absf(angular_velocity)*.13,0,.45),1-exp(-delta*10))
	if turn_blend>.10 and not hunting and not escaping:display_state="Turning left" if angular_velocity<0 else "Turning right"
	event_time+=delta
	if event_time>=event_duration:event_kind=""
	if not event_kind.is_empty():display_state="Eating" if event_kind=="Eat" else "Reproducing" if event_kind=="Reproduce" else "Hunting"
	animation_state=display_state
	crossfade_elapsed+=delta;phase_elapsed+=delta
	# Shared skeletal poses avoid per-animal AnimationPlayer track evaluation.
	if phase_elapsed<(1.0/30 if camera_distance<30 else 1.0/20):return
	phase_elapsed=0;current_clip=base_clip
	var blend=smoothstep(0.0,.22,crossfade_elapsed);var phase=idle_phase if base_clip=="Rest" else gait_phase
	if not detailed:
		var upper="Rest";var upper_phase=0.0;var amount=0.0
		if turn_blend>.001:upper="TurnLeft" if angular_velocity<0 else "TurnRight";upper_phase=.5;amount=turn_blend
		if grow_target<.999:upper="Grow";upper_phase=idle_phase;amount=.12
		if not event_kind.is_empty():upper=event_kind;upper_phase=event_time/maxf(.1,event_duration);amount=smoothstep(0.0,.18,event_time)*(1-smoothstep(event_duration-.2,event_duration,event_time))
		_gpu_pose(base_clip,phase,blend,upper,upper_phase,amount);return
	for bone in skeleton.get_bone_count():
		var target=_sample(base_clip,phase,bone)
		if bone in library.upper_bones:
			if turn_blend>.001:target=target.interpolate_with(_sample("TurnLeft" if angular_velocity<0 else "TurnRight",0.5,bone),turn_blend)
			if grow_target<.999:target=target.interpolate_with(_sample("Grow",idle_phase,bone),.12)
			if not event_kind.is_empty():
				var amount=smoothstep(0.0,.18,event_time)*(1-smoothstep(event_duration-.2,event_duration,event_time))
				target=target.interpolate_with(_sample(event_kind,event_time/maxf(.1,event_duration),bone),amount)
		if blend<1 and transition_pose.size()>bone:target=transition_pose[bone].interpolate_with(target,blend)
		current_pose[bone]=target;skeleton.set_bone_pose(bone,target)

func _present_death(delta: float) -> void:
	if delta<=0:return
	death_time+=delta;animation_state="Dying" if death_time<1.3 else "Dead"
	var blend=smoothstep(0.0,.18,death_time)
	if not detailed:_gpu_pose("Die",minf(1,death_time/1.3),blend)
	for bone in (skeleton.get_bone_count() if detailed else 0):
		var target=_sample("Die",minf(1,death_time/1.3),bone)
		if transition_pose.size()>bone:target=transition_pose[bone].interpolate_with(target,blend)
		current_pose[bone]=target;skeleton.set_bone_pose(bone,target)
	var opacity=1-smoothstep(2.3,3.0,death_time)
	for material in materials:material.set_shader_parameter("opacity",opacity)
	expired=death_time>=3.0
