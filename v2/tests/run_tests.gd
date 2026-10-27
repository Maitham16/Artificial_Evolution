extends SceneTree
const State=preload("res://scripts/python_state.gd")
var checks=0
var failures=0
func check(value: bool,message: String) -> void:
	checks+=1
	if not value:failures+=1;printerr("FAIL: "+message)
func frame(time: float,x: float,heading: float=0.0,run_id: String="a",generation: int=1) -> Dictionary:
	return {"stream_id":"fixture","run_id":run_id,"wall_time":time,"ticks":int(time*60),"generation":generation,
		"config":{"mode":"foraging","environment":"uniform","algorithm":"selection"},"seed_text":"9223372036854775807",
		"width":1000,"height":600,"paused":false,"speed":1,"automatic":true,"finished":false,"extinct":false,"awaiting_generation":false,
		"metrics":{"population":1,"families":1,"mean_fitness":42,"mean_meals":0,"neural_rms":0},
		"selected":"g1:c1","hazard_energy_per_second":12,"activation":[0,0,0,0,0,0,0,0],
		"birth_count":1,"birth_delta":[{"id":"g1:c1","root":"g1:c1","parent":null,"generation":generation}],
		"agents":[{"id":"g1:c1","x":x,"y":300,"heading":heading,"radius":8,"vision":160,"active":true,"alive":true,"energy":71,"age":42}],
		"food":[[520,300,3]],"barriers":[[400,280,20,40]],"hazards":[[300,200,50]]}
func _initialize():call_deferred("_run")
func _run() -> void:
	var state=State.new()
	check(state.accept(frame(0,500,TAU-.1),100),"First Python snapshot is accepted")
	check(state.agents[0].position==Vector2.ZERO,"Python coordinates map to centered 3D ground")
	check(state.food[0]==Vector2(1,0),"Food uses the same coordinate transform")
	check(state.barriers[0].size==Vector2(1,2),"Barrier dimensions come from Python")
	check(state.hazards[0].radius==2.5,"Hazard radius comes from Python")
	check(state.agents[0].radius==.4 and state.agents[0].vision==8,"Body and sensor sizes preserve Python units")
	state.accept(frame(.1,520,.1),100.1)
	var view=state.sample_display(100.15)
	check(view["g1:c1"].position.distance_to(Vector2(.5,0))<.00001,"Movement interpolates between snapshots")
	check(abs(angle_difference(view["g1:c1"].heading,0))<.00001,"Heading interpolates across the angle wrap via the shortest path")
	check(state.agents[0].position==Vector2(1,0) and state.agents[0].energy==71 and state.agents[0].age==42,"Display interpolation never changes authoritative fields")
	check(state.sample_display(1000)["g1:c1"].position==Vector2(1,0),"Missing snapshots never cause extrapolated movement")
	check(not state.has_method("step"),"Godot state cannot execute physics ticks")
	check(state.seed_text=="9223372036854775807","Large seeds remain exact decimal text")
	check(not state.accept(frame(.05,800),101) and state.agents[0].position==Vector2(1,0),"Old snapshots cannot rewind physics")
	state.accept(frame(.2,700,0,"b",2),100.2)
	check(state.frames.size()==1 and state.sample_display(100.2)["g1:c1"].position==Vector2(10,0),"New runs snap rather than interpolate unrelated lifetimes")
	check(not state.accept(frame(.15,500,0,"a"),100.3) and state.run_id=="b","A queued old-run frame cannot replace a newer run")
	var dead=frame(.3,700,0,"b",2);dead.agents[0].active=false;dead.agents[0].alive=false
	state.accept(dead,100.3)
	check(state.sample_display(100.3).is_empty(),"Deaths remove visible actors without simulated ghost motion")
	for i in range(1,100):state.accept(frame(.3+i*.01,700,0,"b",2),100.3+i*.01)
	check(state.frames.size()<=16,"Interpolation buffer remains bounded")
	var restarted=frame(0,600,0,"new");restarted.stream_id="new-process"
	check(state.accept(restarted,200),"A new Python process establishes a new stream clock")
	print("AE2_VIEW_TEST_RESULT ",JSON.stringify({"checks":checks,"failures":failures}))
	quit(0 if failures==0 else 1)
