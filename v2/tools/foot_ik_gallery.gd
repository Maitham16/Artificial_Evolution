extends SceneTree
## Explicit geometry fixture, not a simulation run or invented Python behavior.
const Animal=preload("res://scripts/animal_view.gd")
var bodies=[]
class Floor:
	extends RefCounted
	func contact_height_at(p: Vector2) -> float:return .10*p.x+.065*sin(p.x*3.0)*cos(p.y*2.0)
var ground=Floor.new()
func _initialize():call_deferred("_run")
func _run():
	var environment=WorldEnvironment.new();environment.environment=Environment.new();environment.environment.background_mode=Environment.BG_COLOR;environment.environment.background_color=Color("ced8db");environment.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR;environment.environment.ambient_light_color=Color.WHITE;environment.environment.ambient_light_energy=.5;root.add_child(environment)
	var sun=DirectionalLight3D.new();sun.rotation_degrees=Vector3(-50,-25,0);sun.shadow_enabled=true;root.add_child(sun)
	var tool=SurfaceTool.new();tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	for z in range(40):
		for x in range(100):
			for corner in [Vector2(0,0),Vector2(1,0),Vector2(0,1),Vector2(1,0),Vector2(1,1),Vector2(0,1)]:
				var p=Vector2(x-50,z-20)*.1+corner*.1;var e=.01
				tool.set_normal(Vector3(ground.contact_height_at(p-Vector2(e,0))-ground.contact_height_at(p+Vector2(e,0)),e*2,ground.contact_height_at(p-Vector2(0,e))-ground.contact_height_at(p+Vector2(0,e))).normalized());tool.set_uv(p*.7);tool.add_vertex(Vector3(p.x,ground.contact_height_at(p),p.y))
	var floor_mesh=MeshInstance3D.new();floor_mesh.mesh=tool.commit();var material=StandardMaterial3D.new();material.albedo_color=Color("8b927a");material.roughness=.95;floor_mesh.material_override=material;root.add_child(floor_mesh)
	var index=0
	for model in ["doe","stag","wolf"]:
		var data={"id":model,"root":"family0","species":"predator" if model=="wolf" else null,"age":5.0,"speed":0.0};var n=0
		while Animal.appearance(data).model!=model:n+=1;data.root="family"+str(n)
		var body=Animal.new();root.add_child(body);body.configure(data);body.position=Vector3((index-1)*2.2,ground.contact_height_at(Vector2((index-1)*2.2,0)),0);var p=Vector2(body.position.x,body.position.z);var e=.05;var normal=Vector3(ground.contact_height_at(p-Vector2(e,0))-ground.contact_height_at(p+Vector2(e,0)),e*2,ground.contact_height_at(p-Vector2(0,e))-ground.contact_height_at(p+Vector2(0,e))).normalized();var forward=Vector3(cos(.35),0,sin(.35)).slide(normal).normalized();var side=forward.cross(normal).normalized();body.basis=Basis(forward,side.cross(forward).normalized(),side);body.set_detailed(true);body.base_clip="Walk";body._pose("Walk",.25);body.pose_revision+=1;bodies.append(body);index+=1
	var camera=Camera3D.new();camera.position=Vector3(6,2.5,6);root.add_child(camera);camera.look_at(Vector3(0,.6,0));camera.fov=38
	for frame in 45:await process_frame
	await RenderingServer.frame_post_draw
	var directory="res://docs/screenshots/"
	root.get_texture().get_image().save_png(directory+"habitat-feet-before.png")
	for body in bodies:body.feet.apply(ground,.016)
	for frame in 10:await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(directory+"habitat-feet-after.png")
	print("IK_GEOMETRY_FIXTURE ",bodies.map(func(body):return {"model":body.model_key,"ik":body.feet.statistics}))
	quit()
