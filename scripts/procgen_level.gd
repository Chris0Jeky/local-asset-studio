extends Node3D
## Procgen level loader (written by procgen_level.py assemble): instantiates each piece's LOD0 GLB from res://level.json
## at its Blender placement, converted to Godot (x, y, z) -> (x, z, -y), with the Blender yaw as the Godot Y rotation.
## Parts the factory leaves to the engine (open ground with no factory collision) get a trimesh collision here.
## Each placement becomes a Marker3D "spawn_<name>" under "Placements" (a spot and facing for a character).
## Headless check: prints one "LEVEL_REPORT {json}" line and quits when run with -- --report.


func _ready() -> void:
	var level = JSON.parse_string(FileAccess.get_file_as_string("res://level.json"))
	var engine_trimesh := 0
	var pieces := 0
	for piece in level.pieces:
		var scene: Node3D = load("res://" + piece.glb).instantiate()
		add_child(scene)
		var p = piece.position
		scene.position = Vector3(p[0], p[2], -p[1])
		scene.rotation_degrees.y = piece.yaw_deg
		scene.name = piece.name
		pieces += 1
		for mi in _meshes(scene):
			if String(mi.name) in piece.trimesh_parts:
				mi.create_trimesh_collision()
				engine_trimesh += 1
	var spots := Node3D.new(); spots.name = "Placements"; add_child(spots)
	for spot in level.get("placements", []):
		var m := Marker3D.new(); m.name = "spawn_" + spot.name; spots.add_child(m)
		var q = spot.position
		m.position = Vector3(q[0], q[2], -q[1])
		m.rotation_degrees.y = spot.yaw_deg
	if "--report" in OS.get_cmdline_user_args():
		var shapes := _count(self, func(n): return n is CollisionShape3D)
		print("LEVEL_REPORT " + JSON.stringify({"pieces": pieces, "collision_shapes": shapes, "engine_trimesh": engine_trimesh,
			"meshes": _meshes(self).size(), "placements": spots.get_child_count()}))
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
