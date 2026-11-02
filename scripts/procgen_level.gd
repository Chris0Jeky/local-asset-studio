extends Node3D
## Procgen level loader (written by procgen_level.py assemble): instantiates each piece's LOD0 GLB from res://level.json
## at its Blender placement, converted to Godot (x, y, z) -> (x, z, -y), with the Blender yaw as the Godot Y rotation.
## Parts the factory leaves to the engine (open ground with no factory collision) get a trimesh collision here.
## Headless check: prints one "LEVEL_REPORT {json}" line and quits when run with -- --report.


func _ready() -> void:
	var level = JSON.parse_string(FileAccess.get_file_as_string("res://level.json"))
	var engine_trimesh := 0
	for piece in level.pieces:
		var scene: Node3D = load("res://" + piece.glb).instantiate()
		add_child(scene)
		var p = piece.position
		scene.position = Vector3(p[0], p[2], -p[1])
		scene.rotation_degrees.y = piece.yaw_deg
		scene.name = piece.name
		for mi in _meshes(scene):
			if String(mi.name) in piece.trimesh_parts:
				mi.create_trimesh_collision()
				engine_trimesh += 1
	if "--report" in OS.get_cmdline_user_args():
		var shapes := _count(self, func(n): return n is CollisionShape3D)
		print("LEVEL_REPORT " + JSON.stringify({"pieces": get_child_count(), "collision_shapes": shapes, "engine_trimesh": engine_trimesh,
			"meshes": _meshes(self).size()}))
		get_tree().quit()


func _meshes(n: Node) -> Array:
	var out := []
	if n is MeshInstance3D: out.append(n)
	for c in n.get_children(): out.append_array(_meshes(c))
	return out


func _count(n: Node, pred: Callable) -> int:
	var total := 1 if pred.call(n) else 0
	for c in n.get_children(): total += _count(c, pred)
	return total
