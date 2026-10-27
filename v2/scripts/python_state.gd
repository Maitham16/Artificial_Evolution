extends RefCounted
## Authoritative snapshots plus a display-only interpolation buffer.
## Coordinates, energy, food, fitness, ancestry, sensors and events come from Python.
const UNITS=20.0
var run_id=""
var stream_id=""
var latest_wall_time=-INF
var config={}
var seed_text=""
var agents: Array=[]
var food: Array=[]
var food_objects: Dictionary={}
var food_revision=0
var environment_context: Dictionary={}
var barriers: Array=[]
var hazards: Array=[]
var births={}
var samples: Array=[]
var history: Array=[]
var metrics={}
var activation:=PackedFloat64Array()
var selected=""
var sharing: Array=[]
var groups: Array=[]
var generation=1
var ticks=0
var width=1000.0
var height=600.0
var paused=false
var finished=false
var extinct=false
var automatic=true
var awaiting_generation=false
var speed=1
var hazard_cost=0.0
var received_frames=0
var last_received=0.0
var clock_offset=INF
var interpolation_delay=.10
var frames: Array=[]
var displayed={}
var connected=false
var display_sim_time=0.0
var display_wall_time=0.0
var animation_sequence=0
var animation_events: Array=[]
var animation_gaps=0

func point(x: float,y: float) -> Vector2:return Vector2((x-width/2)/UNITS,(y-height/2)/UNITS)

func accept(data: Dictionary,received_at: float=-1.0) -> bool:
	if received_at<0:received_at=Time.get_ticks_usec()/1000000.0
	var incoming_stream=str(data.get("stream_id","local"))
	if incoming_stream==stream_id and float(data.wall_time)<latest_wall_time:return false
	if incoming_stream!=stream_id:latest_wall_time=-INF;clock_offset=INF;frames.clear()
	stream_id=incoming_stream;latest_wall_time=float(data.wall_time)
	var changed=run_id!=str(data.run_id)
	if changed:
		run_id=str(data.run_id);births.clear();samples.clear();history.clear();frames.clear();displayed.clear();clock_offset=INF;animation_events.clear();animation_sequence=int(data.get("animation_sequence",0))
	if not changed and int(data.ticks)<ticks:return false
	if not changed:
		if int(data.get("animation_floor",animation_sequence+1))>animation_sequence+1:animation_gaps+=1
		for event in data.get("animation_events",[]):
			if int(event.seq)>animation_sequence:
				var receipt=event.duplicate(true);receipt.received_wall=float(data.wall_time);animation_events.append(receipt)
		animation_sequence=maxi(animation_sequence,int(data.get("animation_sequence",0)))
	last_received=received_at;clock_offset=minf(clock_offset,received_at-float(data.wall_time));connected=true
	config=data.config;seed_text=str(data.seed_text);generation=int(data.generation);ticks=int(data.ticks)
	width=float(data.width);height=float(data.height);paused=data.paused;speed=int(data.speed);automatic=data.automatic
	finished=data.finished;extinct=data.extinct;awaiting_generation=data.awaiting_generation
	metrics=data.metrics;selected=str(data.selected);hazard_cost=float(data.hazard_energy_per_second);sharing=data.get("sharing",[])
	activation=PackedFloat64Array(data.get("activation",[]))
	for birth in data.birth_delta:births[str(birth.id)]=birth
	if data.has("charts"):samples=data.charts.samples;history=data.charts.history
	agents=[]
	var poses={}
	for source in data.agents:
		var actor=source.duplicate();actor.position=point(source.x,source.y);actor.radius=float(source.radius)/UNITS;actor.vision=float(source.vision)/UNITS
		actor.slot=agents.size();agents.append(actor)
		if actor.active:
			poses[str(actor.id)]={"position":actor.position,"heading":float(actor.heading),"age":float(actor.age)}
			for field in ["toward_seconds","away_seconds","opponent_visible_seconds"]:poses[str(actor.id)][field]=float(actor.get(field,0))
	environment_context=data.get("environment_context",{})
	var next_food={}
	for plant in data.get("food_objects",[]):
		var record=plant.duplicate();record.position=point(plant.x,plant.y);record.radius=float(plant.radius)/UNITS;next_food[str(plant.id)]=record
	if next_food!=food_objects or changed:food_revision+=1
	food_objects=next_food
	food=[]
	for pellet in data.food:food.append(point(pellet[0],pellet[1]))
	barriers=[]
	for box in data.barriers:barriers.append(Rect2(point(box[0],box[1]),Vector2(box[2],box[3])/UNITS))
	groups=[]
	for group in data.get("group_arenas",[]):groups.append(Rect2(point(group[1],group[2]),Vector2(group[3],group[4])/UNITS))
	hazards=[]
	for hazard in data.hazards:hazards.append({"position":point(hazard[0],hazard[1]),"radius":float(hazard[2])/UNITS})
	var timestamp=float(data.wall_time)
	if frames.is_empty() or timestamp>float(frames[-1].time):frames.append({"time":timestamp,"poses":poses,"generation":generation,"sim_time":float(data.get("time",ticks/60.0))})
	elif timestamp==float(frames[-1].time):frames[-1]={"time":timestamp,"poses":poses,"generation":generation,"sim_time":float(data.get("time",ticks/60.0))}
	while frames.size()>16:frames.pop_front()
	received_frames+=1
	return true

func sample_display(now: float=-1.0) -> Dictionary:
	if frames.is_empty():return {}
	if now<0:now=Time.get_ticks_usec()/1000000.0
	var target=now-clock_offset-interpolation_delay
	while frames.size()>2 and float(frames[1].time)<=target:frames.pop_front()
	var a=frames[0];var b=frames[1] if frames.size()>1 else frames[0]
	if target>=float(frames[-1].time):a=frames[-1];b=a
	var alpha=clampf((target-float(a.time))/maxf(.000001,float(b.time)-float(a.time)),0,1)
	display_sim_time=lerpf(float(a.get("sim_time",0)),float(b.get("sim_time",0)),alpha)
	display_wall_time=target
	displayed={}
	for actor in agents:
		if not actor.active:continue
		var id=str(actor.id)
		var latest={"position":actor.position,"heading":float(actor.heading),"age":float(actor.age)}
		# A new birth/cohort snaps to its authoritative position. Never interpolate
		# a different lifetime into a newborn or extrapolate through a barrier.
		if a.generation==b.generation and a.poses.has(id) and b.poses.has(id):
			displayed[id]={"position":a.poses[id].position.lerp(b.poses[id].position,alpha),"heading":lerp_angle(a.poses[id].heading,b.poses[id].heading,alpha)}
		else:displayed[id]=latest
		for field in ["age","toward_seconds","away_seconds","opponent_visible_seconds"]:
			displayed[id][field]=lerpf(float(a.poses.get(id,{}).get(field,actor.get(field,0))),float(b.poses.get(id,{}).get(field,actor.get(field,0))),alpha)
	return displayed

func actor(id: String):
	for entry in agents:
		if str(entry.id)==id:return entry
	return null

func take_animation_events() -> Array:
	var due=[];var pending=[]
	for event in animation_events:
		if float(event.received_wall)<=display_wall_time:due.append(event)
		else:pending.append(event)
	animation_events=pending
	return due
