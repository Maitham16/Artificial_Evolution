extends RefCounted
## Local feed-forward controller. No services, Python or runtime learning.

var input_size: int = 8
var weights := PackedFloat64Array()

static func create(rng: RandomNumberGenerator, inputs: int = 8):
	var brain = load("res://scripts/brain.gd").new()
	brain.input_size = inputs
	brain.weights.resize(inputs * 8 + 26)
	for i in range(brain.weights.size()):
		var scale = 0.1 if (i >= inputs * 8 and i < inputs * 8 + 8) or i >= inputs * 8 + 24 else 1.0 / sqrt(8.0 if i >= inputs * 8 + 8 else float(inputs))
		brain.weights[i] = rng.randfn(0.0, scale)
	return brain

func hidden(inputs: PackedFloat64Array) -> PackedFloat64Array:
	assert(inputs.size() == input_size)
	var values := PackedFloat64Array()
	values.resize(8)
	for j in range(8):
		var total = weights[input_size * 8 + j]
		for i in range(input_size):
			total += inputs[i] * weights[i * 8 + j]
		values[j] = tanh(total)
	return values

func forward(inputs: PackedFloat64Array) -> PackedFloat64Array:
	var activation = hidden(inputs)
	var outputs := PackedFloat64Array([0.0, 0.0])
	for k in range(2):
		var total = weights[input_size * 8 + 24 + k]
		for j in range(8):
			total += activation[j] * weights[input_size * 8 + 8 + j * 2 + k]
		outputs[k] = tanh(total)
	return outputs

func copy():
	var result = get_script().new()
	result.input_size = input_size
	result.weights = weights.duplicate()
	return result

func mutated(rng: RandomNumberGenerator, probability: float, sigma: float):
	var child = copy()
	for i in range(weights.size()):
		if rng.randf() < probability:
			child.weights[i] += rng.randfn(0.0, sigma)
	return child

func serialize() -> Dictionary:
	return {"input_size": input_size, "weights": Array(weights)}

static func deserialize(data: Dictionary):
	var result = load("res://scripts/brain.gd").new()
	result.input_size = int(data.input_size)
	result.weights = PackedFloat64Array(data.weights)
	assert(result.weights.size() == result.input_size * 8 + 26)
	return result
