extends SceneTree
# Procgen factory import check: load the imported GLB, count collision, measure mesh AABB, print one JSON line.

func _walk(node):
	var result = [node]
	for child in node.get_children():
		result += _walk(child)
	return result

func _to_root(node, top):
	# global_transform is not resolved inside _initialize, so compose local transforms explicitly.
	var xf = Transform3D.IDENTITY
	while node != top:
		xf = node.transform * xf
		node = node.get_parent()
	return xf

func _initialize():
	var out = {"state": "failed"}
	var scene = load("res://asset.glb")
	if scene == null:
		out["error"] = "load returned null"
	else:
		var inst = scene.instantiate()
		root.add_child(inst)
		var meshes = 0
		var bodies = 0
		var shapes = 0
		var aabb = AABB()
		for node in _walk(inst):
			if node is MeshInstance3D:
				var box = _to_root(node, inst) * node.get_aabb()
				aabb = box if meshes == 0 else aabb.merge(box)
				meshes += 1
			elif node is StaticBody3D:
				bodies += 1
			elif node is CollisionShape3D and node.shape != null:
				shapes += 1
		out = {"state": "loaded", "meshes": meshes, "static_bodies": bodies, "collision_shapes": shapes,
			"mesh_aabb_size": [aabb.size.x, aabb.size.y, aabb.size.z],
			"mesh_aabb_position": [aabb.position.x, aabb.position.y, aabb.position.z]}
	print("PROCGEN_REPORT " + JSON.stringify(out))
	quit()
