# Headless policy probe: production guard, GLB-imported materials, no render or Blender invocation.
extends SceneTree

const Renderer = preload("res://render.gd")


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 2:
		push_error("expected GLB path and receipt path")
		quit(2)
		return
	var failures: Array[String] = []
	var rows: Array = []
	var imported := {}
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var import_error := doc.append_from_file(args[0], state)
	if import_error != OK:
		failures.append("fixture GLB import failed: " + str(import_error))
		finish(args[1], rows, failures, imported)
		return
	var scene := doc.generate_scene(state)
	if scene == null:
		failures.append("fixture GLB did not produce a scene")
		finish(args[1], rows, failures, imported)
		return
	var meshes := scene.find_children("*", "MeshInstance3D", true, false)
	if meshes.is_empty():
		failures.append("fixture GLB did not produce a mesh")
		scene.free()
		finish(args[1], rows, failures, imported)
		return
	var template := meshes[0] as MeshInstance3D
	if template.mesh == null or template.mesh.get_surface_count() < 1 or template.get_active_material(0) == null:
		failures.append("fixture GLB did not produce an imported surface material")
		scene.free()
		finish(args[1], rows, failures, imported)
		return
	imported = {"mesh_count": meshes.size(), "surface_count": template.mesh.get_surface_count(),
		"material_name": template.get_active_material(0).resource_name,
		"material_class": template.get_active_material(0).get_class()}
	var entries := [
		{"name": "ok", "record": {"status": "ok", "file": "ready.gdshader"}, "apply": true},
		{"name": "partial", "record": {"status": "partial", "file": "inspect.gdshader", "unsupported": ["Transmission Light"]}},
		{"name": "unsupported", "record": {"status": "unsupported", "file": "stale.gdshader"}},
		{"name": "unknown", "record": {"status": "future-status", "file": "stale.gdshader"}},
		{"name": "missing-status", "record": {"file": "stale.gdshader"}},
		{"name": "missing-record", "record": null},
		{"name": "missing-file", "record": {"status": "ok"}},
		{"name": "empty-file", "record": {"status": "ok", "file": ""}},
		{"name": "invalid-file", "record": {"status": "ok", "file": 7}},
		{"name": "partial-with-override", "record": {"status": "partial", "file": "inspect.gdshader"}, "prior_override": true},
		{"name": "ok-with-override", "record": {"status": "ok", "file": "ready.gdshader"}, "prior_override": true, "apply": true},
		{"name": "unavailable-material", "record": {"status": "ok", "file": "ready.gdshader"}, "unavailable": true, "loads": 1},
		{"name": "absent-shader", "record": {"status": "ok", "file": "absent.gdshader"}, "loads": 1},
		{"name": "empty-shader", "record": {"status": "ok", "file": "empty.gdshader"}, "loads": 1},
		{"name": "blank-shader", "record": {"status": "ok", "file": "blank.gdshader"}, "loads": 1}
	]
	for entry in entries:
		var node := template.duplicate() as MeshInstance3D
		var base: Material = node.mesh.surface_get_material(0)
		var original: Material = node.get_active_material(0)
		if entry.get("prior_override", false):
			original = StandardMaterial3D.new()
			node.set_surface_override_material(0, original)
		var replacement := ShaderMaterial.new()
		var loads := [0]
		var make_material := func() -> Material:
			loads[0] += 1
			if entry.get("unavailable", false):
				return null
			var shader: Shader = Renderer.load_compiled_shader("res://" + entry["record"]["file"])
			if shader == null:
				return null
			replacement.shader = shader
			return replacement
		var result: Dictionary = Renderer.apply_compiled_material(node, 0, entry["record"], make_material)
		var applied: bool = entry.get("apply", false)
		var expected_loads: int = entry.get("loads", 1 if applied else 0)
		var expected: Material = replacement if applied else original
		var base_unchanged: bool = node.mesh.surface_get_material(0) == base
		var active_correct: bool = node.get_active_material(0) == expected
		if result.get("applied") != applied or loads[0] != expected_loads or not base_unchanged or not active_correct:
			failures.append(entry["name"] + ": wrong selection, load count or retained material")
		if not applied and str(result.get("reason", "")).is_empty():
			failures.append(entry["name"] + ": missing kept-imported diagnostic")
		if entry["name"] == "partial" and result.get("unsupported", []) != ["Transmission Light"]:
			failures.append("partial: unsupported feature was not retained")
		rows.append({"name": entry["name"], "result": result, "loads": loads[0],
			"base_material_unchanged": base_unchanged, "active_material_correct": active_correct})
		node.free()
	scene.free()
	finish(args[1], rows, failures, imported)


func finish(path: String, rows: Array, failures: Array[String], imported: Dictionary) -> void:
	var receipt := {"schema": "las.toon-material-policy-test.v1", "godot": Engine.get_version_info(),
		"imported": imported, "cases": rows, "failures": failures}
	var out := FileAccess.open(path, FileAccess.WRITE)
	if out == null:
		push_error("could not retain toon material policy receipt")
		quit(2)
		return
	out.store_string(JSON.stringify(receipt, "\t"))
	out.close()
	print("TOON_POLICY_RESULT ", JSON.stringify(receipt))
	quit(0 if failures.is_empty() else 1)
