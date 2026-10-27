extends Resource
## Shared, evaluated bone transforms from the Blender-authored skeletal clips.
@export var bone_names: PackedStringArray
@export var clips: Dictionary={}
@export var upper_bones: PackedInt32Array
@export var gpu_dimensions: Vector2i
@export var upper_weights: PackedFloat32Array
@export var strides: Dictionary={"Walk":1.0,"Run":1.15}
