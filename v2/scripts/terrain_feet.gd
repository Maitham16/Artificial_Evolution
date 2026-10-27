extends RefCounted
## Visual two-bone IK: samples the displayed surface, never changes Python XZ or energy.
static var references={}
var animal
var chains=[]
var anchors={}
var revision=-1
var statistics={"contacts":0,"max_error_m":0.0,"solves":0}
func setup(body) -> void:
	animal=body
	var sk=animal.skeleton
	var names=[]
	if animal.model_key=="wolf":
		for side in ["Left","Right"]:
			names.append(["b_"+side+"Leg01","b_"+side+"Leg02","b_"+side+"Foot01","b_"+side+"Foot03"])
			names.append(["b_"+side+"UpperArm","b_"+side+"ForeArm","b_"+side+"Hand01","b_"+side+"Hand03"])
	else:
		for name in ["Frontleg_L","Frontleg_R","Backleg_L","Backleg_R"]:names.append([name,name+".001",name+".002",name+".002"])
	for group in names:
		var indices=[]
		for name in group:indices.append(sk.find_bone(name))
		assert(not -1 in indices,"Missing terrain IK chain")
		chains.append(indices)
	if not references.has(animal.model_key):
		var data={};var to_body=animal.global_transform.affine_inverse()*sk.global_transform
		var scale=animal.appearance_size*animal.growth
		for clip in ["Rest","Walk","Run"]:
			var low=[INF,INF,INF,INF]
			for pose in animal.clips[clip].poses:
				var globals=[]
				for bone in sk.get_bone_count():
					var parent=sk.get_bone_parent(bone);globals.append(globals[parent]*pose[bone] if parent>=0 else pose[bone])
				for index in chains.size():low[index]=minf(low[index],(to_body*globals[chains[index][3]].origin).y/scale)
			data[clip]=low
		references[animal.model_key]=data
func reset() -> void:anchors.clear();revision=-1
func apply(terrain,delta: float) -> void:
	if not animal.detailed or animal.dead or delta<=0 or revision==animal.pose_revision:return
	revision=animal.pose_revision
	var sk=animal.skeleton;var scale=animal.global_basis.x.length()*animal.appearance_size*animal.growth
	var visual_scale=animal.appearance_size*animal.growth
	var clip="Run" if animal.base_clip in ["Run","Hunt","Escape"] else "Walk" if animal.base_clip=="Walk" else "Rest"
	var low=references[animal.model_key][clip]
	var contacts=0;var error=0.0;var solves=int(statistics.solves)
	for index in chains.size():
		var chain=chains[index];var toe=sk.global_transform*sk.get_bone_global_pose(chain[3]).origin
		var local=animal.global_transform.affine_inverse()*toe
		var lift=local.y-low[index]*visual_scale
		var strength=1.0-smoothstep(.025*visual_scale,.13*visual_scale,lift)
		var sole=maxf(.015,float(low[index]))*scale
		if strength<.25:anchors.erase(index)
		elif strength>.65 and (not anchors.has(index) or Vector2(toe.x,toe.z).distance_to(anchors[index])>.32*scale):anchors[index]=Vector2(toe.x,toe.z)
		var point: Vector2=anchors.get(index,Vector2(toe.x,toe.z))
		var ground=terrain.contact_height_at(point)+sole+.005
		var goal=Vector3(point.x,ground,point.y)
		if toe.y<ground:strength=maxf(strength,.8)
		if strength<.01:continue
		goal=toe.lerp(goal,strength)
		var inverse=sk.global_transform.affine_inverse()
		var ankle_pose=sk.get_bone_global_pose(chain[2]);var toe_pose=sk.get_bone_global_pose(chain[3])
		var ankle_goal=inverse*goal-(toe_pose.origin-ankle_pose.origin)
		_solve(sk,chain,ankle_goal);solves+=1
		# Preserve the animated paw/hoof orientation after positioning its ankle.
		var placed=sk.get_bone_global_pose(chain[2]);placed.basis=ankle_pose.basis;sk.set_bone_global_pose(chain[2],placed)
		if strength>.8:
			contacts+=1
			var result=sk.global_transform*sk.get_bone_global_pose(chain[3]).origin
			error=maxf(error,result.distance_to(goal))
	statistics={"contacts":contacts,"max_error_m":error,"solves":solves}
static func _solve(sk: Skeleton3D,chain: Array,target: Vector3) -> void:
	var hip=sk.get_bone_global_pose(chain[0]);var knee=sk.get_bone_global_pose(chain[1]);var foot=sk.get_bone_global_pose(chain[2])
	var a=hip.origin;var b=knee.origin;var c=foot.origin
	var upper=a.distance_to(b);var lower=b.distance_to(c);var direction=target-a
	var distance=clampf(direction.length(),absf(upper-lower)+.0001,upper+lower-.0001);direction=direction.normalized()
	var bend=(b-a)-direction*(b-a).dot(direction)
	if bend.length_squared()<.000001:bend=direction.cross(Vector3.RIGHT if absf(direction.x)<.8 else Vector3.UP)
	bend=bend.normalized()
	var along=(upper*upper-lower*lower+distance*distance)/(2*distance)
	var new_knee=a+direction*along+bend*sqrt(maxf(0,upper*upper-along*along))
	hip.basis=Basis(Quaternion((b-a).normalized(),(new_knee-a).normalized()))*hip.basis;sk.set_bone_global_pose(chain[0],hip)
	knee=sk.get_bone_global_pose(chain[1]);foot=sk.get_bone_global_pose(chain[2])
	var desired=a+direction*distance
	knee.basis=Basis(Quaternion((foot.origin-knee.origin).normalized(),(desired-knee.origin).normalized()))*knee.basis;sk.set_bone_global_pose(chain[1],knee)
