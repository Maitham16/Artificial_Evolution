extends SceneTree
const Library=preload("res://scripts/skeletal_pose_library.gd")
func _initialize() -> void:call_deferred("_bake")
func _bake() -> void:
	for model in ["doe","stag","wolf"]:
		var scene=load("res://assets/animals/skeletal/"+model+"/"+model+".gltf").instantiate();root.add_child(scene)
		var player: AnimationPlayer=scene.find_children("*","AnimationPlayer",true,false)[0]
		var skeleton: Skeleton3D=scene.find_children("*","Skeleton3D",true,false)[0]
		player.process_mode=Node.PROCESS_MODE_DISABLED
		var library=Library.new()
		for index in skeleton.get_bone_count():
			var name=skeleton.get_bone_name(index);library.bone_names.append(name)
			if "Head" in name or "Neck" in name or "Jaw" in name or name=="Backbone.002":library.upper_bones.append(index)
		for clip in player.get_animation_list():
			if clip=="RESET":continue
			var title=str(clip).get_file();var animation=player.get_animation(clip)
			var looping=not title in ["Die","Eat","Reproduce"]
			var count=32 if title in ["Run","Walk","Hunt","Escape"] else 24
			var poses=[]
			player.play(clip);player.pause()
			for frame in range(count):
				player.seek(animation.length*float(frame)/(count if looping else count-1),true)
				skeleton.force_update_all_bone_transforms()
				var pose=[]
				for index in skeleton.get_bone_count():pose.append(skeleton.get_bone_pose(index))
				poses.append(pose)
			library.clips[title]={"duration":animation.length,"loop":looping,"poses":poses}
		var meshes=scene.find_children("*","MeshInstance3D",true,false)
		var bind: Skin=meshes[0].skin
		var bone_indices=[]
		for index in bind.get_bind_count():
			var bone=skeleton.find_bone(bind.get_bind_name(index)) if not str(bind.get_bind_name(index)).is_empty() else bind.get_bind_bone(index)
			bone_indices.append(bone)
			var upper=bone in library.upper_bones;var parent=skeleton.get_bone_parent(bone)
			while parent>=0:
				if parent in library.upper_bones:upper=true
				parent=skeleton.get_bone_parent(parent)
			library.upper_weights.append(1.0 if upper else 0.0)
		var pixels=PackedFloat32Array();var rows=0;var width=128
		for title in library.clips:
			var clip=library.clips[title];clip.gpu_start=rows
			for pose in clip.poses:
				var globals=[]
				for bone in skeleton.get_bone_count():
					var parent=skeleton.get_bone_parent(bone)
					globals.append(globals[parent]*pose[bone] if parent>=0 else pose[bone])
				var line=PackedFloat32Array();line.resize(width*4)
				for index in bind.get_bind_count():
					var transform: Transform3D=globals[bone_indices[index]]*bind.get_bind_pose(index)
					for axis in range(3):
						var offset=index*12+axis*4
						line[offset]=transform.basis.x[axis];line[offset+1]=transform.basis.y[axis];line[offset+2]=transform.basis.z[axis];line[offset+3]=transform.origin[axis]
				pixels.append_array(line);rows+=1
		for title in ["Walk","Run"]:
			var foot_indices=[]
			for bone in skeleton.get_bone_count():
				var name=skeleton.get_bone_name(bone)
				if name.ends_with("leg_L.002") or name.ends_with("leg_R.002") or name.ends_with("Hand03") or name.ends_with("Foot03"):foot_indices.append(bone)
			var trajectories={}
			for bone in foot_indices:trajectories[bone]=[]
			var frames=library.clips[title].poses
			for pose in frames:
				var globals=[]
				for bone in skeleton.get_bone_count():
					var parent=skeleton.get_bone_parent(bone)
					globals.append(globals[parent]*pose[bone] if parent>=0 else pose[bone])
				for bone in foot_indices:trajectories[bone].append((skeleton.global_transform*globals[bone]).origin)
			var estimates=[]
			for bone in foot_indices:
				var points=trajectories[bone];var low=INF
				for point in points:low=minf(low,point.y)
				for frame in points.size():
					var a=points[frame];var b=points[(frame+1)%points.size()]
					var estimate=-(b.x-a.x)*points.size()
					if a.y<low+.035 and b.y<low+.035 and estimate>.25 and estimate<3.0:estimates.append(estimate)
			if not estimates.is_empty():estimates.sort();library.strides[title]=estimates[estimates.size()/2]
		print("CONTACT_STRIDES ",model," ",library.strides)
		library.gpu_dimensions=Vector2i(width,rows)
		var image=Image.create_from_data(width,rows,false,Image.FORMAT_RGBAF,pixels.to_byte_array())
		assert(image.save_exr("res://assets/animals/skeletal/"+model+"/bones.exr")==OK)
		print("BONE_PALETTE ",model," binds=",bind.get_bind_count()," dims=",library.gpu_dimensions)
		var path="res://assets/animals/skeletal/"+model+"/poses.res"
		assert(ResourceSaver.save(library,path,ResourceSaver.FLAG_COMPRESS)==OK)
		print("SKELETAL_POSES ",model," bones=",library.bone_names.size()," clips=",library.clips.keys())
		scene.free()
	quit()
