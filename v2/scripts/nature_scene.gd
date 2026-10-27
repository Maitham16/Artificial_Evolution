extends Node3D
## Scenery only. Never owns or changes simulation state, RNG, or collision rules.
const FOLIAGE=preload("res://assets/materials/foliage.gdshader")
const GRASS=preload("res://assets/materials/grass.gdshader")
const GROUND=preload("res://assets/materials/meadow.gdshader")
const WATER=preload("res://assets/materials/river.gdshader")
const IMPOSTOR=preload("res://assets/materials/forest_impostor.gdshader")
const SKY=preload("res://assets/materials/daylight.gdshader")
const PROFILES=[{"name":"Performance","trees":200,"broadleaf":22,"grass":14000,"flowers":160,"ferns":45,"rocks":60,"shadow":75.0},
	{"name":"Balanced","trees":360,"broadleaf":38,"grass":30000,"flowers":500,"ferns":100,"rocks":100,"shadow":105.0},
	{"name":"Lush","trees":560,"broadleaf":55,"grass":52000,"flowers":800,"ferns":170,"rocks":150,"shadow":130.0}]
var physical_surface={}
var contact_vertices={}
var quality=1
var half=Vector2(25,15)
var terrain_noise=FastNoiseLite.new()
var ridge_noise=FastNoiseLite.new()
var plant_noise=FastNoiseLite.new()
var content: Node3D
var environment: Environment
var sun: DirectionalLight3D
var ground_material: ShaderMaterial
var assets={}
var generation_count=0
var statistics={}
var dimensions=Vector2.ZERO
var scatter: Array=[]

func _init() -> void:
	terrain_noise.seed=72814;terrain_noise.frequency=1.0;terrain_noise.noise_type=FastNoiseLite.TYPE_SIMPLEX_SMOOTH;terrain_noise.fractal_octaves=3
	ridge_noise.seed=72815;ridge_noise.frequency=1.0;ridge_noise.fractal_octaves=4
	plant_noise.seed=72816;plant_noise.frequency=1.0

func _ready() -> void:
	content=Node3D.new();content.name="LandscapeGeometry";add_child(content)
	var world=WorldEnvironment.new();environment=Environment.new();world.environment=environment;add_child(world)
	var sky=Sky.new();var sky_material=ShaderMaterial.new();sky_material.shader=SKY;sky.sky_material=sky_material;sky.radiance_size=Sky.RADIANCE_SIZE_128;sky.process_mode=Sky.PROCESS_MODE_QUALITY
	environment.background_mode=Environment.BG_SKY;environment.sky=sky
	environment.ambient_light_source=Environment.AMBIENT_SOURCE_SKY;environment.ambient_light_energy=.35
	environment.tonemap_mode=Environment.TONE_MAPPER_FILMIC;environment.tonemap_exposure=.85
	environment.fog_enabled=true;environment.fog_light_color=Color("a4b9bc");environment.fog_density=.0017
	environment.fog_sun_scatter=.35;environment.fog_sky_affect=.18;environment.fog_aerial_perspective=.28
	sun=DirectionalLight3D.new();sun.name="AfternoonSun";sun.rotation_degrees=Vector3(-43,-32,0);sun.light_color=Color("fff0d2");sun.light_energy=1.0
	sun.shadow_enabled=true;sun.directional_shadow_mode=DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS;sun.directional_shadow_max_distance=105;sun.shadow_bias=.035;sun.shadow_normal_bias=.7;sun.light_angular_distance=.65;add_child(sun)
	ground_material=ShaderMaterial.new();ground_material.shader=GROUND
	for pair in [["grass_color","grass_ground_diff"],["grass_normal","grass_ground_normal"],["earth_color","forest_ground_04_diff"],["stone_color","rock_face_diff"],["stone_normal","rock_face_normal"]]:
		ground_material.set_shader_parameter(pair[0],load("res://assets/nature/textures/"+pair[1]+".jpg"))

func river_x(z: float) -> float:return -half.x-15+sin(z*.035)*5+sin(z*.013+1)*3

func height_at(point: Vector2) -> float:
	if not physical_surface.is_empty():
		var edge=maxf(absf(point.x)-float(physical_surface.width)/2,absf(point.y)-float(physical_surface.height)/2)
		if edge<=0:return _physical_height(point)
		if edge<3:return lerpf(_physical_height(point),_scenery_height(point),smoothstep(0,3,edge))
	return _scenery_height(point)

func _scenery_height(point: Vector2) -> float:
	var edge=maxf(absf(point.x)-half.x,absf(point.y)-half.y)
	var meadow=.65+terrain_noise.get_noise_2d(point.x*.064,point.y*.064)*1.35+sin(point.x*.11)*cos(point.y*.13)*.36
	var outside=smoothstep(0.0,34.0,edge)
	var hills=outside*(2.0+5.5*terrain_noise.get_noise_2d(point.x*.023+91,point.y*.023+48))
	var rise=smoothstep(55.0,260.0,edge)
	var ridge=pow(1.0-absf(ridge_noise.get_noise_2d(point.x*.0045+27,point.y*.0045-19)),1.8)
	var mountain=rise*(10+ridge*65+terrain_noise.get_noise_2d(point.x*.014,point.y*.014)*4)
	var stream=exp(-pow((point.x-river_x(point.y))/5.8,2))
	var lake_center=Vector2(-half.x-40,-78)
	var lake=exp(-pow(((point-lake_center)/Vector2(33,26)).length(),4))
	var carve=maxf(stream*5.5,lake*7)*smoothstep(1.0,7.0,edge)
	return meadow+hills+mountain-carve

func normal_at(point: Vector2) -> Vector3:
	var step=.35
	return Vector3(height_at(point-Vector2(step,0))-height_at(point+Vector2(step,0)),step*2,height_at(point-Vector2(0,step))-height_at(point+Vector2(0,step))).normalized()

func configure(width: float,height: float,force: bool=false) -> void:
	if dimensions==Vector2(width,height) and not force:return
	dimensions=Vector2(width,height);half=dimensions/2
	for child in content.get_children():child.free()
	contact_vertices.clear()
	scatter.clear();statistics={"trees":0,"grass_clumps":0,"flowers":0,"ferns":0,"rocks":0,"draw_batches":0}
	generation_count+=1
	var started=Time.get_ticks_usec()
	_terrain_patch(-48,48,.5 if not physical_surface.is_empty() else 1.0,0)
	_terrain_patch(-160,160,2.0,48)
	_terrain_patch(-640,640,4.0,160)
	_water()
	if not physical_surface.is_empty():
		var water=MeshInstance3D.new();var plane=PlaneMesh.new();plane.size=Vector2(physical_surface.width,physical_surface.height);water.mesh=plane;water.position.y=float(physical_surface.water_level);water.layers=4
		var material=ShaderMaterial.new();material.shader=WATER;water.material_override=material;water.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;water.name="PythonHabitatWater";content.add_child(water)
	var rng=RandomNumberGenerator.new();rng.seed=93281+quality
	var profile=PROFILES[quality]
	sun.directional_shadow_max_distance=profile.shadow
	var trees=[];var broadleaf=[]
	for definition in [["fir_sapling",profile.trees,trees],["jacaranda_tree",profile.broadleaf,broadleaf]]:
		var attempts=0
		while definition[2].size()<int(definition[1]) and attempts<8000:
			attempts+=1
			var p=Vector2(rng.randf_range(-105,105),rng.randf_range(-100,90))
			var edge=maxf(absf(p.x)-half.x,absf(p.y)-half.y)
			if edge<6 or height_at(p)<-.2 or normal_at(p).y<.72:continue
			if plant_noise.get_noise_2d(p.x*.045,p.y*.045)<-.25:continue
			var crowded=false
			for existing in trees+broadleaf:
				if p.distance_squared_to(Vector2(existing.origin.x,existing.origin.z))<11: crowded=true;break
			if crowded:continue
			var scale=rng.randf_range(4.2,8.5) if definition[0]=="fir_sapling" else rng.randf_range(.42,.70)
			definition[2].append(_plant_transform(p,scale,rng))
		_forest(definition[0],definition[2])
	statistics.trees=trees.size()+broadleaf.size()
	var rocks=[]
	for i in range(int(profile.rocks)):
		var p=Vector2(rng.randf_range(-105,100),rng.randf_range(-100,95))
		if maxf(absf(p.x)-half.x,absf(p.y)-half.y)<1.8:continue
		if height_at(p)<-1.5:continue
		rocks.append(_plant_transform(p,rng.randf_range(4,17),rng))
	_batch_asset("rock_07",rocks,true,200);statistics.rocks=rocks.size()
	var ferns=[];var flowers=[]
	for i in range(int(profile.ferns)):
		var p=Vector2(rng.randf_range(-half.x-20,half.x+20),rng.randf_range(-half.y-20,half.y+20))
		if height_at(p)<-.35:continue
		if maxf(absf(p.x)-half.x,absf(p.y)-half.y)<1:continue
		ferns.append(_plant_transform(p,rng.randf_range(.65,1.35),rng))
	_batch_asset("fern_02",ferns,false,110);statistics.ferns=ferns.size()
	for i in range(int(profile.flowers)):
		var p=Vector2(rng.randf_range(-half.x-9,half.x+9),rng.randf_range(-half.y-9,half.y+9))
		if height_at(p)<-.3 or plant_noise.get_noise_2d(p.x*.12,p.y*.12)<-.1:continue
		flowers.append(_plant_transform(p,rng.randf_range(.65,1.6),rng))
	_batch_asset("flower_empodium",flowers,false,100);statistics.flowers=flowers.size()
	_grass(rng,int(profile.grass))
	var probe=ReflectionProbe.new();probe.name="RiverReflection";probe.position=Vector3(-half.x-22,4,-24);probe.size=Vector3(160,72,210);probe.cull_mask=2;probe.reflection_mask=4;probe.ambient_mode=ReflectionProbe.AMBIENT_DISABLED;probe.update_mode=ReflectionProbe.UPDATE_ONCE;probe.intensity=.8;probe.blend_distance=22;probe.enable_shadows=false
	if RenderingServer.get_current_rendering_method()=="gl_compatibility":content.add_child(probe)
	else:probe.free()
	statistics.build_ms=(Time.get_ticks_usec()-started)/1000.0

func _terrain_patch(start: float,end: float,step: float,hole: float) -> void:
	var count=roundi((end-start)/step)
	var vertices=PackedVector3Array();var normals=PackedVector3Array();var uvs=PackedVector2Array();var indices=PackedInt32Array();var tangents=PackedFloat32Array()
	for z in range(count+1):
		for x in range(count+1):
			var p=Vector2(start+x*step,start+z*step);var n=normal_at(p)
			var altitude=height_at(p)
			if maxf(absf(p.x),absf(p.y))<=48:contact_vertices[p]=altitude
			vertices.append(Vector3(p.x,altitude,p.y));normals.append(n);uvs.append(p)
			var tangent=Vector3.RIGHT.slide(n).normalized();tangents.append_array(PackedFloat32Array([tangent.x,tangent.y,tangent.z,-1]))
	for z in range(count):
		for x in range(count):
			var cx=start+(x+.5)*step;var cz=start+(z+.5)*step
			if hole>0 and absf(cx)<hole and absf(cz)<hole:continue
			var i=z*(count+1)+x
			indices.append_array(PackedInt32Array([i,i+1,i+count+1,i+1,i+count+2,i+count+1]))
	var arrays=[];arrays.resize(Mesh.ARRAY_MAX);arrays[Mesh.ARRAY_VERTEX]=vertices;arrays[Mesh.ARRAY_NORMAL]=normals;arrays[Mesh.ARRAY_TEX_UV]=uvs;arrays[Mesh.ARRAY_TANGENT]=tangents;arrays[Mesh.ARRAY_INDEX]=indices
	var mesh=ArrayMesh.new();mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES,arrays)
	var node=MeshInstance3D.new();node.name="TerrainLOD";node.mesh=mesh;node.material_override=ground_material;node.layers=2;node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_ON;content.add_child(node)

func _water() -> void:
	var node=MeshInstance3D.new();node.name="RiverAndLake"
	var plane=PlaneMesh.new();plane.size=Vector2(160,300);plane.subdivide_width=80;plane.subdivide_depth=100;node.mesh=plane
	node.position=Vector3(-half.x-65,-.8,-15);node.layers=4
	var mat=ShaderMaterial.new();mat.shader=WATER;node.material_override=mat;node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;content.add_child(node)

func _plant_transform(point: Vector2,scale: float,rng: RandomNumberGenerator) -> Transform3D:
	var basis=Basis(Vector3.UP,rng.randf_range(-PI,PI)).scaled(Vector3(scale*rng.randf_range(.88,1.1),scale,scale*rng.randf_range(.88,1.1)))
	return Transform3D(basis,Vector3(point.x,height_at(point)-.025,point.y))

func _asset(name: String) -> Mesh:
	if assets.has(name):return assets[name]
	var scene=load("res://assets/nature/models/%s/%s.gltf" % [name,name]).instantiate()
	var found: ArrayMesh=_bake_asset(scene,Transform3D.IDENTITY,null)
	assert(found!=null,"Nature asset is missing geometry: "+name)
	var height=maxf(.1,found.get_aabb().size.y)
	for surface in range(found.get_surface_count()):
		var source=found.surface_get_material(surface)
		if source is BaseMaterial3D:
			var material=ShaderMaterial.new();material.shader=FOLIAGE
			material.set_shader_parameter("color_texture",source.albedo_texture);material.set_shader_parameter("base_color",source.albedo_color)
			material.set_shader_parameter("has_normal",source.normal_texture!=null)
			if source.normal_texture:material.set_shader_parameter("normal_texture",source.normal_texture)
			material.set_shader_parameter("crown_height",height)
			material.set_shader_parameter("season_response",0.0 if name=="rock_07" else .2 if name=="fir_sapling" else 1.0)
			material.set_shader_parameter("wind_strength",.024 if name=="fir_sapling" else .13 if name=="jacaranda_tree" else .05 if name!="rock_07" else 0.0)
			material.set_shader_parameter("fade_end",235.0 if name in ["fir_sapling","jacaranda_tree"] else 180.0 if name=="rock_07" else 110.0)
			found.surface_set_material(surface,material)
	scene.free();assets[name]=found;return found

func _bake_asset(node: Node,parent_transform: Transform3D,result: ArrayMesh) -> ArrayMesh:
	var transform=parent_transform*(node.transform if node is Node3D else Transform3D.IDENTITY)
	if node is MeshInstance3D:
		for surface in range(node.mesh.get_surface_count()):
			var tool=SurfaceTool.new();tool.begin(Mesh.PRIMITIVE_TRIANGLES);tool.append_from(node.mesh,surface,transform);tool.set_material(node.mesh.surface_get_material(surface));result=tool.commit(result)
	for child in node.get_children():result=_bake_asset(child,transform,result)
	return result

func _batch_asset(name: String,transforms: Array,shadows: bool,visible_end: float) -> void:
	if transforms.is_empty():return
	var chunks={}
	for transform in transforms:
		var key=Vector2i(floori(transform.origin.x/32),floori(transform.origin.z/32))
		if not chunks.has(key):chunks[key]=[]
		chunks[key].append(transform)
	var mesh=_asset(name)
	for key in chunks:
		var multi=MultiMesh.new();multi.transform_format=MultiMesh.TRANSFORM_3D;multi.use_colors=true;multi.use_custom_data=true;multi.mesh=mesh;multi.instance_count=chunks[key].size()
		for i in range(chunks[key].size()):
			multi.set_instance_transform(i,chunks[key][i]);multi.set_instance_color(i,Color(.90+sin(i*7.3)*.10,.96+sin(i*4.1)*.07,.88+sin(i*5.2)*.10,1));multi.set_instance_custom_data(i,Color(fposmod(i*.618,1),0,0,1))
		var node=MultiMeshInstance3D.new();node.name=name+"Chunk";node.multimesh=multi;node.layers=2;node.visibility_range_end=visible_end;node.visibility_range_end_margin=15;node.extra_cull_margin=2
		node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		content.add_child(node);scatter.append(node);statistics.draw_batches+=1

func _forest(name: String,transforms: Array) -> void:
	# Full geometry at the clearing; full-scan baked crowns for the distant forest.
	var clearing=Vector3(half.x+8,0,half.y+5)
	transforms.sort_custom(func(a,b):return a.origin.distance_squared_to(clearing)<b.origin.distance_squared_to(clearing))
	var near_count=mini(transforms.size(),4 if name=="fir_sapling" else 1)
	_batch_asset(name,transforms.slice(0,near_count),true,160)
	var data=JSON.parse_string(FileAccess.get_file_as_string("res://assets/nature/impostors/dimensions.json"))[name]
	var mesh=QuadMesh.new();mesh.size=Vector2(data.width,data.height)
	var material=ShaderMaterial.new();material.shader=IMPOSTOR
	material.set_shader_parameter("tree_image",load("res://assets/nature/impostors/"+name+".png"))
	mesh.material=material
	var chunks={}
	for source in transforms.slice(near_count):
		var transform: Transform3D=source
		transform.origin.y+=(float(data.height)/2-float(data.base_offset))*source.basis.y.length()
		var key=Vector2i(floori(transform.origin.x/32),floori(transform.origin.z/32))
		if not chunks.has(key):chunks[key]=[]
		chunks[key].append(transform)
	for key in chunks:
		var multi=MultiMesh.new();multi.transform_format=MultiMesh.TRANSFORM_3D;multi.use_colors=true;multi.mesh=mesh;multi.instance_count=chunks[key].size()
		for i in range(chunks[key].size()):
			multi.set_instance_transform(i,chunks[key][i]);multi.set_instance_color(i,Color(.93+sin(i)*.06,1.0,.94,1))
		var node=MultiMeshInstance3D.new();node.name="ForestImpostorChunk";node.multimesh=multi;node.layers=2;node.extra_cull_margin=18;node.visibility_range_end=260;node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		content.add_child(node);scatter.append(node);statistics.draw_batches+=1

func _grass_mesh() -> Mesh:
	var tool=SurfaceTool.new();tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rng=RandomNumberGenerator.new();rng.seed=178
	for blade in range(7):
		var angle=rng.randf_range(0,TAU);var side=Vector3(cos(angle),0,sin(angle));var offset=Vector3(rng.randf_range(-.11,.11),0,rng.randf_range(-.11,.11))
		var height=rng.randf_range(.19,.42);var bend=Vector3(rng.randf_range(-.13,.13),0,rng.randf_range(-.13,.13));var width=rng.randf_range(.008,.019)
		var points=[offset-side*width,offset+side*width,offset+Vector3(0,height*.55,0)+bend*.3-side*width*.6,offset+Vector3(0,height*.55,0)+bend*.3+side*width*.6,offset+Vector3(0,height,0)+bend]
		for tri in [[0,2,1],[1,2,3],[2,4,3]]:
			for index in tri:
				tool.set_normal(Vector3(0,.65,0)+side*.75);tool.set_uv(Vector2(0 if index in [0,2] else 1,.0 if index<2 else .55 if index<4 else 1));tool.add_vertex(points[index])
	return tool.commit()

func _grass(rng: RandomNumberGenerator,count: int) -> void:
	var chunks={};var placed=0
	for i in range(count):
		var p=Vector2(rng.randf_range(-half.x-26,half.x+26),rng.randf_range(-half.y-26,half.y+26))
		if height_at(p)<-.4:continue
		if plant_noise.get_noise_2d(p.x*.23,p.y*.23)<-.45:continue
		var edge=maxf(absf(p.x)-half.x,absf(p.y)-half.y)
		var scale=rng.randf_range(.65,1.1) if edge<0 else rng.randf_range(.8,1.8)
		var transform=_plant_transform(p,scale,rng);var key=Vector2i(floori(p.x/16),floori(p.y/16))
		if not chunks.has(key):chunks[key]=[]
		chunks[key].append(transform);placed+=1
	var mesh=_grass_mesh();var material=ShaderMaterial.new();material.shader=GRASS
	for key in chunks:
		var multi=MultiMesh.new();multi.transform_format=MultiMesh.TRANSFORM_3D;multi.use_colors=true;multi.use_custom_data=true;multi.mesh=mesh;multi.instance_count=chunks[key].size()
		for i in range(chunks[key].size()):
			multi.set_instance_transform(i,chunks[key][i]);multi.set_instance_color(i,Color(rng.randf_range(.8,1.2),rng.randf_range(.85,1.15),rng.randf_range(.75,1.2),1));multi.set_instance_custom_data(i,Color(rng.randf(),0,0,1))
		var node=MultiMeshInstance3D.new();node.name="WindGrassChunk";node.multimesh=multi;node.material_override=material;node.layers=2;node.extra_cull_margin=1;node.visibility_range_end=60;node.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;content.add_child(node);scatter.append(node);statistics.draw_batches+=1
	statistics.grass_clumps=placed

func set_quality(index: int) -> void:
	quality=clampi(index,0,2)
	if dimensions!=Vector2.ZERO:configure(dimensions.x,dimensions.y,true)

func set_physical_surface(value: Dictionary) -> void:
	if str(physical_surface.get("sha256",""))==str(value.get("sha256","")):return
	physical_surface=value;dimensions=Vector2.ZERO

func _physical_height(point: Vector2) -> float:
	var nx=int(physical_surface.nx);var nz=int(physical_surface.nz)
	var fx=clampf((point.x/float(physical_surface.width)+.5)*(nx-1),0,nx-1)
	var fz=clampf((point.y/float(physical_surface.height)+.5)*(nz-1),0,nz-1)
	var ix=mini(nx-2,int(fx));var iz=mini(nz-2,int(fz));var tx=fx-ix;var tz=fz-iz
	var heights=physical_surface.heights;var offset=iz*nx+ix
	var a=float(heights[offset]);var b=float(heights[offset+1]);var c=float(heights[offset+nx]);var d=float(heights[offset+nx+1])
	return a+(b-a)*tx+(c-a)*tz if tx+tz<=1 else d+(c-d)*(1-tx)+(b-d)*(1-tz)

func contact_height_at(point: Vector2) -> float:
	var extent=maxf(absf(point.x),absf(point.y))
	var spacing=(.5 if not physical_surface.is_empty() else 1.0) if extent<48 else 2.0 if extent<160 else 4.0
	var corner=(point/spacing).floor()*spacing;var f=(point-corner)/spacing
	var samples=[]
	for p in [corner,corner+Vector2(spacing,0),corner+Vector2(0,spacing),corner+Vector2(spacing,spacing)]:
		if not contact_vertices.has(p):contact_vertices[p]=height_at(p)
		samples.append(float(contact_vertices[p]))
	return samples[0]+(samples[1]-samples[0])*f.x+(samples[2]-samples[0])*f.y if f.x+f.y<=1 else samples[3]+(samples[2]-samples[3])*(1-f.x)+(samples[1]-samples[3])*(1-f.y)
