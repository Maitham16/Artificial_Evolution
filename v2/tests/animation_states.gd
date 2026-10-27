extends SceneTree
const Animal=preload("res://scripts/animal_view.gd")
const State=preload("res://scripts/python_state.gd")
const Fixtures=preload("res://tests/run_tests.gd")
var checks=0
var failures=0
func _initialize() -> void:call_deferred("_run")
func check(value: bool,message: String) -> void:
	checks+=1
	if not value:failures+=1;printerr("FAIL: "+message)
func actor(species=null,parent=null,age=0.0,maturity=0.0) -> Dictionary:
	return {"id":"fixture:"+str(species),"root":"family0","species":species,"parent":parent,"age":age,"maturity_age":maturity,"speed":0.0}
func specimen(data: Dictionary):
	var body=Animal.new();root.add_child(body);body.configure(data);return body
func move(body,data,pos: Vector2,time: float,heading=0.0,toward=0.0,away=0.0,visible=0.0):
	body.present(data,{"position":pos,"heading":heading,"toward_seconds":toward,"away_seconds":away,"opponent_visible_seconds":visible},time,.1,3)
func _run() -> void:
	var data=actor();var body=specimen(data);body.set_detailed(true)
	move(body,data,Vector2.ZERO,0);check(body.animation_state=="Resting","Only observed stationary actors rest")
	data.speed=20;move(body,data,Vector2(1,0),1);check(body.current_clip=="Walk","Observed slow movement walks")
	check(body.crossfade_elapsed<.22,"Locomotion transitions use a finite crossfade")
	data.speed=60;move(body,data,Vector2(4,0),2);check(body.current_clip=="Run","Observed fast movement runs")
	move(body,data,Vector2(4.6,0),2.2,-.6);check(body.animation_state=="Turning left","Heading changes drive a turning layer")
	body.event({"kind":"meal"});move(body,data,Vector2(5.2,0),2.4,-.6)
	check(body.animation_state=="Eating" and body.base_clip!="Rest","Confirmed meals feed without stopping real movement")
	var bones=body.current_pose.duplicate();body.present(data,{"position":Vector2(5.2,0),"heading":-.6},2.4,0,3)
	check(body.current_pose==bones,"Pausing freezes skeletal transitions")
	body.event({"kind":"reproduce"});move(body,data,Vector2(5.8,0),2.6,-.6)
	check(body.animation_state=="Reproducing","A confirmed offspring event plays the reproduction layer")
	var hunter_data=actor("predator");hunter_data.speed=60;var hunter=specimen(hunter_data)
	move(hunter,hunter_data,Vector2.ZERO,0)
	move(hunter,hunter_data,Vector2(3,0),1,0,1,0,1)
	check(hunter.animation_state=="Hunting","Recorded approach to a visible opponent drives pursuit")
	move(hunter,hunter_data,Vector2(6,0),2,0,1,0,1)
	check(hunter.animation_state!="Hunting","Nearby opponents alone do not invent pursuit")
	var prey_data=actor("prey");prey_data.speed=60;var prey=specimen(prey_data)
	move(prey,prey_data,Vector2.ZERO,0)
	move(prey,prey_data,Vector2(3,0),1,0,0,1,1)
	check(prey.animation_state=="Escaping","Recorded retreat from a visible opponent drives escape")
	var newborn=actor(null,"parent",0,15);var child=specimen(newborn)
	check(is_equal_approx(child.growth,.65),"Actual continuous newborns begin with a juvenile visual size")
	newborn.age=15;move(child,newborn,Vector2.ZERO,15)
	check(is_equal_approx(child.grow_target,1.0),"Recorded age and maturity determine the growth target")
	var founder=specimen(actor(null,null,0,15));check(founder.growth==1.0,"Founders are not invented newborns")
	body.event({"kind":"death"});body._present_death(.5)
	check(body.dead and body.animation_state=="Dying","Confirmed death plays a skeletal collapse")
	var frozen=body.death_time;body._present_death(0);check(body.death_time==frozen,"Paused corpses do not advance")
	body._present_death(3);check(body.expired,"Dead presentation remnants expire without resurrection")
	check(body.find_children("*","CollisionObject3D",true,false).is_empty(),"Animation adds no scientific collisions")
	hunter.set_detailed(false);hunter._pose("Walk",.25)
	check(hunter.materials[0].get_shader_parameter("gpu_skeleton"),"Distant animals use actual bone-palette skinning")
	check(hunter.materials[0].get_shader_parameter("base_frames").x>=hunter.clips.Walk.gpu_start,"GPU and skeletal paths share clip frames")
	# A paused selection/detail change must preserve the current gait/feeding layer.
	prey.base_clip="Run";prey.gait_phase=.25;prey.crossfade_elapsed=1;prey.event_kind="Eat";prey.event_time=.5;prey.event_duration=1.1
	prey.set_detailed(true);var selected_pose=prey.current_pose.duplicate()
	prey.set_detailed(false);var gpu_frames=prey.materials[0].get_shader_parameter("base_frames")
	prey.set_detailed(true)
	check(prey.current_pose==selected_pose,"Paused detail changes preserve the current skeletal pose")
	check(gpu_frames==prey._gpu_frames("Run",.25),"Paused demotion preserves the same GPU gait phase")
	# Compare a sampled GPU skin matrix against the actual Skeleton3D path.
	hunter.set_detailed(true);hunter._pose("Run",.25);hunter.skeleton.force_update_all_bone_transforms()
	var bind: Skin=hunter.meshes[0].get_meta("source_skin")
	var image=load("res://assets/animals/skeletal/wolf/bones.exr").get_image()
	var row=int(hunter.clips.Run.gpu_start)+8;var error=0.0
	for index in bind.get_bind_count():
		var bone=hunter.skeleton.find_bone(bind.get_bind_name(index))
		var expected=hunter.skeleton.get_bone_global_pose(bone)*bind.get_bind_pose(index)
		var a=image.get_pixel(index*3,row);var b=image.get_pixel(index*3+1,row);var c=image.get_pixel(index*3+2,row)
		var actual=Transform3D(Basis(Vector3(a.r,b.r,c.r),Vector3(a.g,b.g,c.g),Vector3(a.b,b.b,c.b)),Vector3(a.a,b.a,c.a))
		error=maxf(error,actual.origin.distance_to(expected.origin))
		for axis in range(3):error=maxf(error,actual.basis[axis].distance_to(expected.basis[axis]))
	check(error<.03,"GPU bone matrices match the real Skeleton3D transforms")
	# Buffer/receipt tests use the same snapshots as the interpolation suite.
	var state=State.new();var first=Fixtures.frame(0,500);first.animation_sequence=5;first.animation_events=[{"seq":5,"kind":"meal"}]
	state.accept(first,100);check(state.animation_events.is_empty(),"Initial connection never replays historical actions")
	var second=Fixtures.frame(.1,520);second.animation_sequence=6;second.animation_floor=1;second.animation_events=[{"seq":6,"kind":"meal"}]
	state.accept(second,100.1);state.accept(second,100.1)
	state.sample_display(100.15);check(state.take_animation_events().is_empty(),"Events wait for the matching delayed display time")
	state.sample_display(100.25);check(state.take_animation_events().size()==1,"Repeated snapshots deliver each event once")
	check(state.take_animation_events().is_empty(),"Consumed receipts cannot replay")
	state.accept(Fixtures.frame(.2,600,0,"another"),100.3);check(state.animation_events.is_empty(),"A new run clears all old animation receipts")
	for node in [body,hunter,prey,child,founder]:node.free()
	print("AE2_ANIMATION_TEST_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
	quit(0 if failures==0 else 1)
