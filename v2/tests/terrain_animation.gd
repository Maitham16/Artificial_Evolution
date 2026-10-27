extends SceneTree
const Animal=preload("res://scripts/animal_view.gd")
const Batches=preload("res://scripts/animal_batches.gd")
var checks=0
var failures=0
class Ground:
	extends RefCounted
	func contact_height_at(point: Vector2) -> float:return .04+.025*point.x+.018*point.y
func _initialize():call_deferred("_run")
func check(value: bool,message: String):
	checks+=1
	if not value:failures+=1;printerr("FAIL: "+message)
func _run():
	var ground=Ground.new();var bodies={};var worst=0.0
	for model in ["doe","stag","wolf"]:
		var data={"id":model,"root":"family0","species":"predator" if model=="wolf" else null,"age":5.0,"speed":0.0}
		var number=0
		while Animal.appearance(data).model!=model:number+=1;data.root="family"+str(number)
		var body=Animal.new();root.add_child(body);body.configure(data);body.set_detailed(true);bodies[model]=body
		check(body.feet.chains.size()==4,model+" has four explicit anatomical leg chains")
		for phase in [.0,.25,.5,.75]:
			body.base_clip="Walk";body._pose("Walk",phase);body.pose_revision+=1
			var transform=body.transform;body.feet.apply(ground,.016)
			worst=maxf(worst,float(body.feet.statistics.max_error_m))
			check(body.transform==transform,model+" foot IK preserves the authoritative body transform")
			check(float(body.feet.statistics.max_error_m)<.035,model+" planted feet converge within 3.5cm on a reachable slope")
		var count=body.feet.statistics.solves;body.feet.apply(ground,0)
		check(body.feet.statistics.solves==count,model+" paused feet never advance")
		body.set_detailed(false);body.feet.apply(ground,.016)
		check(body.feet.statistics.solves==count,model+" distant animals skip CPU IK")
	var batches=Batches.new();root.add_child(batches);batches.update(bodies)
	check(batches.statistics.animals==3,"Distant animals are batched without losing their source nodes")
	check(bodies.values().all(func(body):return body.meshes.all(func(mesh):return not mesh.visible)),"Batched source meshes are hidden to avoid double rendering")
	var selected=bodies.doe;selected.set_detailed(true);batches.update(bodies)
	check(not selected.batched and selected.meshes.all(func(mesh):return mesh.visible),"Selecting an animal restores its real skeleton and meshes")
	check(batches.statistics.animals==2,"A detailed selected animal leaves the GPU batch")
	var death=bodies.wolf;death.event({"kind":"death"});batches.update(bodies)
	check(not death.batched,"Confirmed deaths leave the living batch and restore corpse animation")
	print("AE2_TERRAIN_ANIMATION_TEST_RESULT ",JSON.stringify({"checks":checks,"failures":failures,"worst_foot_error_m":worst}))
	for body in bodies.values():body.free()
	batches.free();quit(0 if failures==0 else 1)
