extends RefCounted
## Independent Godot model: ground-plane foraging shown in a 3D vivarium.
const Brain = preload("res://scripts/brain.gd")
const STEP: float = 1.0 / 60.0
const VERSION: String = "2.0.0"
const ENVIRONMENTS = ["uniform", "clustered", "sparse", "hazards", "seasons", "barren"]
const ALGORITHMS = ["selection", "neutral", "random", "greedy", "founder"]
const HALF := Vector2(25.0, 15.0)
const RADIUS: float = 0.35
const VISION: float = 8.0
const SPEED: float = 3.0

var config: Dictionary
var agents: Array = []
var food: Array = []
var hazards: Array = []
var barriers: Array = []
var history: Array = []
var archived: Array = []
var samples: Array = []
var founders: Array = []
var generation: int = 1
var ticks: int = 0
var generation_ticks: int = 0
var complete: bool = false
var finished: bool = false
var body_rng := RandomNumberGenerator.new()
var food_rng := RandomNumberGenerator.new()
var brain_rng := RandomNumberGenerator.new()
var steering_rng := RandomNumberGenerator.new()
var mutation_rng := RandomNumberGenerator.new()
var parent_rng := RandomNumberGenerator.new()

static func defaults() -> Dictionary:
	return {"schema_version": 1, "seed": 2801, "population": 100, "food_count": 150,
		"environment": "uniform", "algorithm": "selection", "mutation_rate": 0.1,
		"mutation_scale": 0.1, "generation_limit": 10}

static func validate(data: Dictionary) -> String:
	var keys = defaults()
	for key in data:
		if not keys.has(key): return "Unknown configuration field: " + str(key)
	for key in keys:
		if not data.has(key): return "Missing configuration field: " + key
	if not (data.schema_version is int or data.schema_version is float) or data.schema_version != 1: return "Unsupported configuration schema."
	if not data.environment in ENVIRONMENTS or not data.algorithm in ALGORITHMS: return "Choose a supported environment and controller."
	for key in ["seed", "population", "food_count", "generation_limit"]:
		if not (data[key] is int or data[key] is float) or not is_finite(float(data[key])) or float(data[key]) != floor(float(data[key])):
			return key + " must be an integer."
	if data.seed < 0 or data.seed > 2147483647: return "Seed must be between 0 and 2147483647."
	if data.population < 2 or data.population > 200: return "Population must be 2–200."
	if data.food_count < 0 or data.food_count > 300: return "Food stock must be 0–300."
	if data.generation_limit < 1 or data.generation_limit > 100: return "Generations must be 1–100."
	for key in ["mutation_rate", "mutation_scale"]:
		if not (data[key] is int or data[key] is float) or not is_finite(float(data[key])): return key + " must be finite."
	if data.mutation_rate < 0 or data.mutation_rate > 1: return "Mutation probability must be 0–1."
	if data.mutation_scale < 0 or data.mutation_scale > 2: return "Mutation scale must be 0–2."
	return ""

func _init(settings: Dictionary = {}) -> void:
	config = defaults() if settings.is_empty() else settings.duplicate(true)
	assert(validate(config).is_empty(), validate(config))
	for key in ["schema_version", "seed", "population", "food_count", "generation_limit"]:config[key] = int(config[key])
	for key in ["mutation_rate", "mutation_scale"]:config[key] = float(config[key])
	_start([])

func _seed_stream(label: String) -> int:
	return (str(config.seed) + ":" + label + ":" + str(generation)).hash()

func _start(inherited: Array) -> void:
	body_rng.seed = _seed_stream("body")
	food_rng.seed = _seed_stream("food")
	brain_rng.seed = _seed_stream("brain")
	steering_rng.seed = _seed_stream("steering")
	mutation_rng.seed = _seed_stream("mutation")
	parent_rng.seed = _seed_stream("parent")
	agents.clear()
	food.clear()
	hazards.clear()
	barriers.clear()
	generation_ticks = 0
	complete = false
	if config.environment == "hazards":
		hazards = [{"position": Vector2(-6.0, -7.0), "radius": 2.6}, {"position": Vector2(7.0, 7.0), "radius": 2.6}]
		barriers = [Rect2(-10.0, -2.0, 0.8, 9.0), Rect2(9.0, -8.0, 0.8, 9.0), Rect2(-3.0, 0.0, 6.0, 0.8)]
	var inputs = 16 if config.environment == "hazards" else 8
	for i in range(int(config.population)):
		var pos = _random_position(body_rng)
		var attempt = 0
		while _unsafe(pos, RADIUS + 0.1) and attempt < 2000:
			pos = _random_position(body_rng)
			attempt += 1
		var brain = Brain.create(brain_rng, inputs) if inherited.is_empty() else inherited[i].brain
		var id = "g%d:c%d" % [generation, i + 1]
		var root = id if inherited.is_empty() else inherited[i].root
		agents.append({"id": id, "slot": i, "position": pos, "heading": body_rng.randf_range(-PI, PI),
			"energy": 100.0, "age": 0.0, "lifespan": body_rng.randf_range(60.0, 120.0), "meals": 0,
			"fitness": 0.0, "alive": true, "cause": "", "brain": brain, "root": root,
			"parent": "" if inherited.is_empty() else inherited[i].parent,
			"depth": 0 if inherited.is_empty() else inherited[i].depth,
			"hazard_seconds": 0.0, "hazard_loss": 0.0, "collisions": 0,
			"turn": steering_rng.randf_range(-1.0, 1.0), "turn_left": steering_rng.randf_range(0.75, 2.0)})
	if founders.is_empty():
		for c in agents: founders.append(c.brain.copy())
	while food.size() < food_target(): food.append(_spawn_food())
	_sample()

func _random_position(rng: RandomNumberGenerator) -> Vector2:
	return Vector2(rng.randf_range(-HALF.x + 0.7, HALF.x - 0.7), rng.randf_range(-HALF.y + 0.7, HALF.y - 0.7))

func food_target() -> int:
	if config.environment == "barren": return 0
	if config.environment == "sparse": return mini(int(config.food_count), 50)
	if config.environment == "seasons": return int(round(float(config.food_count) * [1.0, 1.3, 0.5, 0.17][(generation - 1) % 4]))
	return int(config.food_count)

func _spawn_food() -> Vector2:
	for attempt in range(2000):
		var p = _random_position(food_rng)
		if config.environment in ["clustered", "seasons"]:
			var centers = [Vector2(-14,-7),Vector2(13,-6),Vector2(-10,8),Vector2(12,8)]
			var center = centers[food_rng.randi_range(0, 3)]
			if config.environment == "seasons": center = center.rotated(generation * 0.7)
			p = center + Vector2(food_rng.randfn(0,2.2), food_rng.randfn(0,2.2))
			p = p.clamp(-HALF + Vector2.ONE * 0.7, HALF - Vector2.ONE * 0.7)
		if not _unsafe(p, 0.3): return p
	return Vector2(-20,-10)

func _unsafe(p: Vector2, radius: float) -> bool:
	for b in barriers:
		if b.grow(radius).has_point(p): return true
	for h in hazards:
		if p.distance_squared_to(h.position) <= pow(h.radius + radius, 2): return true
	return false

func in_hazard(c: Dictionary) -> bool:
	for h in hazards:
		if c.position.distance_squared_to(h.position) <= pow(h.radius + RADIUS, 2): return true
	return false

func perception(c: Dictionary) -> Dictionary:
	var nearest = -1
	var distance_squared = VISION * VISION
	for i in range(food.size()):
		var d = c.position.distance_squared_to(food[i])
		if d <= distance_squared and (nearest < 0 or d < distance_squared):
			nearest = i
			distance_squared = d
	var bearing = 0.0
	if nearest >= 0:
		var delta = food[nearest] - c.position
		bearing = wrapf(delta.angle() - c.heading, -PI, PI) if delta.length_squared() > 0 else 0.0
	return {"index": nearest, "distance": sqrt(distance_squared), "bearing": bearing}

func _clearance(p: Vector2, direction: Vector2) -> float:
	var result = VISION
	for axis in range(2):
		if abs(direction[axis]) > 0.000001:
			var bound = HALF[axis] - RADIUS if direction[axis] > 0 else -HALF[axis] + RADIUS
			result = minf(result, maxf(0, (bound - p[axis]) / direction[axis]))
	for box in barriers:
		var b: Rect2 = box.grow(RADIUS)
		var near = -INF
		var far = INF
		for axis in range(2):
			if abs(direction[axis]) < 0.000001:
				if p[axis] < b.position[axis] or p[axis] > b.end[axis]: far = -INF
			else:
				var first = (b.position[axis] - p[axis]) / direction[axis]
				var last = (b.end[axis] - p[axis]) / direction[axis]
				near = maxf(near, minf(first,last))
				far = minf(far, maxf(first,last))
		if near >= 0 and near <= far: result = minf(result, near)
	return clampf(result / VISION, 0.0, 1.0)

func sensors(c: Dictionary, seen: Dictionary = {}) -> PackedFloat64Array:
	if seen.is_empty(): seen = perception(c)
	var visible = seen.index >= 0
	var values := PackedFloat64Array([1.0 - seen.distance / VISION if visible else 0.0,
		seen.bearing / PI if visible else 0.0, float(visible), 1.0 - c.energy / 100.0])
	for offset in [0.0, PI/2, PI, -PI/2]:
		values.append(_clearance(c.position, Vector2.from_angle(c.heading + offset)))
	if config.environment == "hazards":
		for offset in [-PI/2, -PI/4, 0.0, PI/4, PI/2]:
			values.append(_clearance(c.position, Vector2.from_angle(c.heading + offset)))
		var proximity = 0.0
		var bearing = 0.0
		for h in hazards:
			var edge = maxf(0.0, c.position.distance_to(h.position) - h.radius - RADIUS)
			if edge <= VISION and 1.0 - edge / VISION >= proximity:
				proximity = 1.0 - edge / VISION
				bearing = wrapf((h.position - c.position).angle() - c.heading, -PI, PI) / PI
		values.append_array(PackedFloat64Array([proximity,bearing,float(in_hazard(c))]))
	return values

func step() -> bool:
	if finished: return false
	if complete:
		if not advance_generation(): return false
	for c in agents:
		if not c.alive: continue
		var seen = perception(c)
		var turn = 0.0
		if config.algorithm in ["random", "greedy"]:
			c.turn_left -= STEP
			if c.turn_left <= 0.0:
				c.turn = steering_rng.randf_range(-1,1)
				c.turn_left = steering_rng.randf_range(0.75,2.0)
			turn = c.turn
			if config.algorithm == "greedy" and seen.index >= 0:
				turn = clampf(seen.bearing / (PI / 2.0 * STEP), -1, 1)
		else: turn = c.brain.forward(sensors(c,seen))[0]
		var hazard = in_hazard(c)
		var cost = 5.0 + (12.0 if hazard else 0.0)
		var lived = minf(STEP, minf(c.lifespan - c.age, c.energy / cost))
		c.age += lived
		c.energy = maxf(0.0, c.energy - lived * cost)
		if hazard:
			c.hazard_seconds += lived
			c.hazard_loss += lived * 12.0
		if c.energy <= 0.00000001 or c.age >= c.lifespan - 0.00000001:
			c.alive = false
			c.cause = "old_age" if c.age >= c.lifespan - 0.00000001 else "hazard" if hazard else "starvation"
		else:
			c.heading = wrapf(c.heading + turn * PI / 2.0 * STEP, -PI, PI)
			_move(c)
			if c.alive and c.energy < 100.0:
				for i in range(food.size()):
					if c.position.distance_squared_to(food[i]) <= pow(RADIUS + 0.22, 2):
						c.energy = minf(100.0,c.energy + 20.0)
						c.meals += 1
						food[i] = _spawn_food()
						break
		c.fitness = c.age + c.meals * 10.0 - c.hazard_seconds * 5.0 - c.collisions * 2.0
	ticks += 1
	generation_ticks += 1
	if ticks % 60 == 0: _sample()
	var living = 0
	for c in agents: living += int(c.alive)
	if living == 0: _finish_generation()
	return true

func _move(c: Dictionary) -> void:
	var old: Vector2 = c.position
	var next = old + Vector2.from_angle(c.heading) * SPEED * STEP
	for axis in range(2):
		var limit = HALF[axis] - RADIUS
		if next[axis] > limit:
			next[axis] = 2.0 * limit - next[axis]
			c.heading = PI - c.heading if axis == 0 else -c.heading
		elif next[axis] < -limit:
			next[axis] = -2.0 * limit - next[axis]
			c.heading = PI - c.heading if axis == 0 else -c.heading
	for box in barriers:
		var b: Rect2 = box.grow(RADIUS)
		if b.has_point(next):
			c.heading = PI - c.heading if old.x <= b.position.x or old.x >= b.end.x else -c.heading
			next = old
			c.collisions += 1
			c.energy = maxf(0.0,c.energy-2.0)
			if c.energy == 0:
				c.alive = false
				c.cause = "collision"
			break
	c.position = next
	c.heading = wrapf(c.heading, -PI, PI)

func _finish_generation() -> void:
	complete = true
	var m = metrics()
	var best = -INF
	var survivors = 0
	for c in agents:
		best = maxf(best,c.fitness)
		survivors += int(c.age >= 60.0)
	history.append({"generation":generation,"mean_fitness":m.mean_fitness,"best_fitness":best,
		"mean_meals":m.mean_meals,"survival_60s":float(survivors)/agents.size(),"duration":generation_ticks*STEP})
	if generation >= int(config.generation_limit): finished = true

func advance_generation() -> bool:
	if not complete or finished: return false
	var parents = agents.duplicate()
	if config.algorithm == "neutral":
		for i in range(parents.size()-1,0,-1):
			var j = parent_rng.randi_range(0,i)
			var c = parents[i];parents[i] = parents[j];parents[j] = c
	else:
		parents.sort_custom(func(a,b): return a.fitness > b.fitness if a.fitness != b.fitness else a.slot < b.slot)
	var count = maxi(1,int(ceil(agents.size() * 0.2)))
	parents = parents.slice(0,count)
	var slots = []
	for i in range(agents.size()):slots.append(i % count)
	for i in range(slots.size()-1,0,-1):
		var j = mutation_rng.randi_range(0,i)
		var value = slots[i];slots[i] = slots[j];slots[j] = value
	var inherited = []
	for i in range(agents.size()):
		var parent = parents[slots[i]]
		var brain = parent.brain.mutated(mutation_rng,config.mutation_rate,config.mutation_scale)
		var root = parent.root
		var depth = parent.depth + 1
		var parent_id = parent.id
		if config.algorithm in ["founder","random","greedy"]:
			brain = founders[i].copy()
			root = agents[i].root
			depth = agents[i].depth + 1
			parent_id = agents[i].id
		inherited.append({"brain":brain,"parent":parent_id,"root":root,"depth":depth})
	for c in agents:archived.append(agent_record(c))
	generation += 1
	_start(inherited)
	return true

func metrics() -> Dictionary:
	var living = 0
	var fitness = 0.0
	var meals = 0.0
	var families = {}
	for c in agents:
		living += int(c.alive)
		fitness += c.fitness
		meals += c.meals
		if c.alive:families[c.root] = true
	return {"alive":living,"population":agents.size(),"food":food.size(),"families":families.size(),
		"mean_fitness":fitness/maxi(1,agents.size()),"mean_meals":meals/maxi(1,agents.size())}

func _sample() -> void:
	var m = metrics()
	m["time"] = ticks * STEP
	m["generation"] = generation
	samples.append(m)

func agent_record(c: Dictionary) -> Dictionary:
	return {"id":c.id,"x":c.position.x,"z":c.position.y,"heading":c.heading,"energy":c.energy,
		"age":c.age,"lifespan":c.lifespan,"meals":c.meals,"fitness":c.fitness,"alive":c.alive,
		"cause":c.cause,"right_censored":c.alive,"parent":c.parent,"root":c.root,"depth":c.depth,
		"hazard_seconds":c.hazard_seconds,"hazard_loss":c.hazard_loss,"collisions":c.collisions,
		"brain":c.brain.serialize()}

func brain_bank() -> Array:
	var result = []
	for c in agents:result.append(c.brain.copy())
	return result

func snapshot() -> Dictionary:
	var records = archived.duplicate(true)
	for c in agents:records.append(agent_record(c))
	return {"schema_version":1,"application_version":VERSION,"model":"godot_ground_foraging_v1",
		"godot_version":Engine.get_version_info().string,"config":config.duplicate(true),"ticks":ticks,
		"generation":generation,"metrics":metrics(),"generations":history.duplicate(true),
		"samples":samples.duplicate(true),"individuals":records,
		"physical_rules":{"step_seconds":STEP,"arena_metres":[50,30],"speed_m_per_s":SPEED,
			"base_energy_per_s":5,"meal_energy":20,"hazard_extra_energy_per_s":12,"vision_metres":VISION},
		"limitations":"Ground-plane agents rendered in 3D. Independent Godot implementation, not bitwise compatible with Python. Single-run observations do not establish treatment effects."}
