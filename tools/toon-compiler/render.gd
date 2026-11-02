# Render a GLB in Godot 4.7 with shaders from scripts/toon_compile.py, under the compiler's lights and cameras:
#   godot --path tools/toon-compiler --script res://render.gd -- <config.json>
# config: {"glb", "compiled" (a toon_compile output dir), "out", "background" (linear RGB), "shadow_max_distance",
# "msaa"}. Writes <out>/<camera>.png per camera in <compiled>/cameras.json. Surfaces without a compiled shader keep
# their imported material and are listed on stdout.
extends SceneTree

var cfg: Dictionary
var cams: Array
var index := -1
var settle := 0
var view: SubViewport
var cam: Camera3D
var textures := {}


func xform(t: Array) -> Transform3D:
	var c := func(v): return Vector3(v[0], v[1], v[2])
	return Transform3D(Basis(c.call(t[0]), c.call(t[1]), c.call(t[2])), c.call(t[3]))


func read_json(path: String):
	return JSON.parse_string(FileAccess.get_file_as_string(path))


func texture(path: String) -> Texture2D:
	if not textures.has(path):
		var img := Image.load_from_file(path)
		img.generate_mipmaps()
		textures[path] = ImageTexture.create_from_image(img)
	return textures[path]


func _initialize() -> void:
	cfg = read_json(OS.get_cmdline_user_args()[0])
	var dir: String = cfg["compiled"]
	var report: Dictionary = read_json(dir + "/report.json")
	if not FileAccess.file_exists(dir + "/cameras.json"):
		push_error("no cameras.json: compile with views (toon_compile_bpy.py --cameras)")
		quit(2)
		return
	cams = read_json(dir + "/cameras.json")
	view = SubViewport.new()
	view.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	view.msaa_3d = int(cfg.get("msaa", Viewport.MSAA_4X))
	view.positional_shadow_atlas_size = 4096
	get_root().add_child(view)
	var world := Node3D.new()
	view.add_child(world)
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	if doc.append_from_file(cfg["glb"], state) != OK:
		push_error("GLB load failed")
		quit(2)
		return
	world.add_child(doc.generate_scene(state))
	var shaders := {}
	var missing := {}
	for node in world.find_children("*", "MeshInstance3D", true, false):
		for i in node.mesh.get_surface_count():
			var src: Material = node.mesh.surface_get_material(i)
			var mname := src.resource_name if src else ""
			var r = report["materials"].get(mname)
			if r == null or not r.has("file"):
				missing[mname] = true
				continue
			if not shaders.has(mname):
				var sh := Shader.new()
				sh.code = FileAccess.get_file_as_string(dir + "/" + r["file"])
				var m := ShaderMaterial.new()
				m.shader = sh
				for uni in r["uniforms"]:
					m.set_shader_parameter(uni, texture(dir + "/" + report["images"][r["uniforms"][uni]]["file"]))
				shaders[mname] = m
			node.set_surface_override_material(i, shaders[mname])
	print("TOONC godot: ", shaders.size(), " compiled materials, kept imported: ", missing.keys())
	for L in read_json(dir + "/lights.json"):
		if L.has("skipped"):
			print("TOONC godot: light skipped: ", L["name"], " (", L["skipped"], ")")
			continue
		var l: Light3D
		if L["type"] == "directional":
			l = DirectionalLight3D.new()
			l.directional_shadow_max_distance = float(cfg.get("shadow_max_distance", 10.0))
			l.light_angular_distance = float(L["angular_distance"])
		else:
			l = OmniLight3D.new()
			l.omni_range = 100.0
		l.light_color = Color(L["color"][0], L["color"][1], L["color"][2])
		l.light_energy = float(L["energy"])
		l.shadow_enabled = bool(L["shadow"])
		world.add_child(l)
		l.transform = xform(L["transform"])
	var env := Environment.new()
	var bg: Array = cfg.get("background", [0.0, 0.0, 0.0])
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(bg[0], bg[1], bg[2]).linear_to_srgb()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_DISABLED
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we := WorldEnvironment.new()
	we.environment = env
	world.add_child(we)
	cam = Camera3D.new()
	world.add_child(cam)
	cam.current = true


func _process(_delta: float) -> bool:
	if settle > 0:
		settle -= 1
		return false
	if index >= 0:
		view.get_texture().get_image().save_png(cfg["out"] + "/" + cams[index]["name"] + ".png")
	index += 1
	if index >= cams.size():
		print("TOONC godot rendered ", cams.size())
		return true
	var c: Dictionary = cams[index]
	view.size = Vector2i(int(c["res"][0]), int(c["res"][1]))
	cam.transform = xform(c["transform"])
	cam.near = float(c["near"])
	cam.far = float(c["far"])
	if c.has("ortho"):
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = float(c["godot_size"])
	else:
		cam.projection = Camera3D.PROJECTION_PERSPECTIVE
		cam.fov = float(c["godot_fov"])
	settle = 8
	return false
