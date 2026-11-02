extends Node3D
## VRM toon runtime proof (see docs/ANIME-TOON-KIT.md). Copy a VRM 1.0 file in as res://model.glb, its spring data as
## res://springs.json (`python scripts/vrm_toon.py springs`, which also carries VRM node constraints and expressions) and its SDF face map as res://face_sdf.png, then run the
## project. Toon light() shader, hull outlines, SpringBoneSimulator3D from the VRM's own springs, a procedural idle with
## one quick body turn so skirt and hair visibly swing, plus a blink and a smile from the VRM's expressions. Material roles follow `vrm_toon.material_role`.

const SHADE := {"skin": Vector3(.93, .76, .74), "face": Vector3(.93, .76, .74), "hair": Vector3(.50, .64, .74), "cloth": Vector3(.62, .62, .78)}

var skel: Skeleton3D
var root: Node3D
var face_mats: Array[ShaderMaterial] = []
var head_rest: Basis
var constraints := []
var expressions := {}
var expr_w := {}                                                             # this frame's requested expression weights
var expr_targets := []                                                       # every [mesh, blend shape] an expression drives
const BLINKS := ["blink", "blinkLeft", "blinkRight"]
const MOUTHS := ["aa", "ih", "ou", "ee", "oh"]
# Rhubarb mouth shapes -> VRM visemes (A closed lips, X rest): optional res://voice.wav + res://cues.json (rhubarb -f json)
const VISEMES := {"A": {}, "B": {"ih": .35}, "C": {"ee": .6, "aa": .2}, "D": {"aa": 1.0}, "E": {"oh": .75},
		"F": {"ou": .85}, "G": {"ih": .3}, "H": {"aa": .45}, "X": {}}
# Resource paths and options, overridable before the node enters the tree, so several actors can share one scene
# (each loads its own model, springs and voice; only a standalone actor makes the camera, lights and environment).
var model_path := "res://model.glb"
var springs_path := "res://springs.json"
var sdf_path := "res://face_sdf.png"
var voice_path := "res://voice.wav"
var cues_path := "res://cues.json"
var voice_start := 0.5
var standalone := true
var cues := []
var action := "idle"                                                         # -- --action=idle|wave|walk
var mouth := {"aa": 0.0, "ih": 0.0, "ou": 0.0, "ee": 0.0, "oh": 0.0}
var t := 0.0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if standalone and a.begins_with("--action="): action = a.trim_prefix("--action=")   # a host sets each actor's own
	root = load(model_path).instantiate()
	add_child(root)
	skel = _find(root, func(n): return n is Skeleton3D)
	for mi in _all(root, func(n): return n is MeshInstance3D):
		_restyle(mi)
	_springs()
	head_rest = skel.get_bone_global_rest(skel.find_bone("J_Bip_C_Head")).basis
	if FileAccess.file_exists(cues_path) and not ResourceLoader.exists(voice_path):
		push_warning("TOON cues.json found but voice.wav is not imported: run godot --headless --import first")
		print("TOON lip sync off: voice.wav not imported")
	if FileAccess.file_exists(cues_path) and ResourceLoader.exists(voice_path):
		cues = JSON.parse_string(FileAccess.get_file_as_string(cues_path)).mouthCues
		var voice := AudioStreamPlayer.new(); voice.stream = load(voice_path); add_child(voice)
		get_tree().create_timer(voice_start).timeout.connect(voice.play)
	if not standalone:
		print("TOON ready: ", model_path); return
	var cam := Camera3D.new(); add_child(cam)
	if action == "walk":                                                    # side-on, so the stride reads
		cam.position = Vector3(2.7, 1.0, 1.2); cam.look_at(Vector3(0, 0.85, 0)); cam.fov = 35
	elif cues.is_empty():
		cam.position = Vector3(0.9, 1.15, 2.6); cam.look_at(Vector3(0, 0.88, 0)); cam.fov = 35
	else:                                                                   # talking portrait
		cam.position = Vector3(0.32, 1.40, 1.05); cam.look_at(Vector3(0, 1.36, 0)); cam.fov = 28
	var key := DirectionalLight3D.new(); add_child(key); key.shadow_enabled = true
	key.rotation_degrees = Vector3(-40, 35, 0); key.light_color = Color(1, .97, .92); key.light_energy = 1.0
	var rim := DirectionalLight3D.new(); add_child(rim); rim.rotation_degrees = Vector3(-20, 200, 0)
	rim.light_color = Color(.75, .85, 1); rim.light_energy = .5
	var env := Environment.new(); env.background_mode = Environment.BG_COLOR; env.background_color = Color(.78, .82, .88)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_DISABLED; env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	var we := WorldEnvironment.new(); we.environment = env; add_child(we)
	print("TOON ready: meshes=", _all(root, func(n): return n is MeshInstance3D).size(), " bones=", skel.get_bone_count())


func _restyle(mi: MeshInstance3D) -> void:
	for s in mi.mesh.get_surface_count():
		var src = mi.get_active_material(s)
		var name: String = src.resource_name if src else ""
		var tex: Texture2D = src.albedo_texture if src is BaseMaterial3D else null
		var m := ShaderMaterial.new()
		var kind := _role(name)
		if kind == "unlit":
			m.shader = load("res://unlit.gdshader")
		else:
			m.shader = load("res://toon.gdshader")
			m.set_shader_parameter("shade_tint", SHADE[kind])
			if kind == "hair": m.set_shader_parameter("spec_amount", .45)
			if kind == "face":
				m.set_shader_parameter("face_sdf", true); m.set_shader_parameter("sdf_tex", load(sdf_path)); face_mats.append(m)
			var o := ShaderMaterial.new(); o.shader = load("res://outline.gdshader"); o.set_shader_parameter("albedo_tex", tex)
			o.set_shader_parameter("width", .0010 if kind == "face" else .0018)
			m.next_pass = o
		m.set_shader_parameter("albedo_tex", tex)
		mi.set_surface_override_material(s, m)


func _role(name: String) -> String:
	var u := name.to_upper()
	if u.ends_with("_EYE") or u.ends_with("_FACE"): return "unlit"
	if u.ends_with("_SKIN"): return "face" if u.begins_with("FACE") else "skin"
	if u.ends_with("_HAIR"): return "hair"
	return "cloth"


func _springs() -> void:
	var data = JSON.parse_string(FileAccess.get_file_as_string(springs_path))
	constraints = _dependency_order(data.get("constraints", []))
	expressions = data.get("expressions", {})
	for p in expressions:                                                     # resolve each bind to [mesh, blend shape] once
		var resolved := []
		for b in expressions[p].binds:
			var mi := root.find_child(b.node, true, false) as MeshInstance3D
			if mi == null: continue
			var i := mi.find_blend_shape_by_name(b.name) if b.name else int(b.index)
			if i < 0: continue
			resolved.append([mi, i, float(b.weight)])
			if not expr_targets.any(func(x): return x[0] == mi and x[1] == i): expr_targets.append([mi, i])
		expressions[p]["resolved"] = resolved
	var sim := SpringBoneSimulator3D.new(); skel.add_child(sim)
	var cols: Array[SpringBoneCollision3D] = []
	for c in data.colliders:
		var col: SpringBoneCollision3D
		var off := Vector3(c.offset[0], c.offset[1], c.offset[2])
		if c.type == "sphere":
			col = SpringBoneCollisionSphere3D.new(); col.radius = c.radius; col.position_offset = off
		else:
			var tail := Vector3(c.tail[0], c.tail[1], c.tail[2]); var axis := tail - off
			col = SpringBoneCollisionCapsule3D.new(); col.radius = c.radius; col.height = axis.length() + 2.0 * c.radius
			col.position_offset = (off + tail) * 0.5
			if axis.length() > 1e-5: col.rotation_offset = Quaternion(Vector3.UP, axis.normalized())
		col.bone_name = c.bone
		sim.add_child(col); cols.append(col)
	sim.set_setting_count(data.chains.size())
	for i in data.chains.size():
		var ch = data.chains[i]
		sim.set_root_bone_name(i, ch.root); sim.set_end_bone_name(i, ch.end)
		sim.set_stiffness(i, ch.stiffness); sim.set_drag(i, ch.drag); sim.set_gravity(i, ch.gravity); sim.set_radius(i, ch.radius)
		sim.set_enable_all_child_collisions(i, false)                 # only the colliders in this spring's VRM groups
		sim.set_collision_count(i, ch.colliders.size())
		for k in ch.colliders.size(): sim.set_collision_path(i, k, sim.get_path_to(cols[int(ch.colliders[k])]))
	print("TOON springs=", sim.get_setting_count(), " colliders=", data.colliders.size(), " constraints=", constraints.size())


func _dependency_order(list: Array) -> Array:
	# A constraint whose source is itself constrained runs after it (VRMC_node_constraint dependency resolution);
	# a cycle falls back to file order.
	var targets := {}
	for c in list: targets[c.bone] = true
	var done := {}; var order := []; var pending := list.duplicate()
	for _pass in list.size():
		var waiting := []
		for c in pending:
			if targets.has(c.source) and not done.has(c.source): waiting.append(c)
			else: order.append(c); done[c.bone] = true
		pending = waiting
		if pending.is_empty(): break
	order.append_array(pending)
	return order


func _apply_constraints() -> void:
	# VRMC_node_constraint, which glTF import ignores: aim turns the bone's rest axis toward the source bone; roll and
	# rotation copy the source's rotation from its rest (roll: only the twist about the axis), each blended by weight.
	for c in constraints:
		var i := skel.find_bone(c.bone); var s := skel.find_bone(c.source)
		if i < 0 or s < 0: continue
		var p := skel.get_bone_parent(i)
		var parent := skel.get_bone_global_pose(p) if p >= 0 else Transform3D()
		var rest := skel.get_bone_rest(i)
		var rest_rot := rest.basis.get_rotation_quaternion()
		if c.type == "aim":
			var at := parent * rest
			var from := (at.basis * Vector3(c.axis[0], c.axis[1], c.axis[2])).normalized()
			var to := skel.get_bone_global_pose(s).origin - at.origin
			if to.length() < 1e-6: continue
			var arc := Quaternion.IDENTITY.slerp(Quaternion(from, to.normalized()), c.weight)
			skel.set_bone_pose_rotation(i, (parent.basis.inverse() * Basis(arc) * at.basis).get_rotation_quaternion())
		else:
			# The source's rotation from its rest (spec reference code). Rotation applies it as is; roll first carries it
			# into the destination's rest frame and keeps only the twist about the axis.
			var src_rest := skel.get_bone_rest(s).basis.get_rotation_quaternion()
			var d := src_rest.inverse() * skel.get_bone_pose_rotation(s)
			if c.type == "roll":
				d = (rest_rot.inverse() * (src_rest * d * src_rest.inverse()) * rest_rot).normalized()
				var ax := Vector3(c.axis[0], c.axis[1], c.axis[2]); var to := d * ax
				var swing := Quaternion(ax.cross(Vector3.UP if absf(ax.y) < .9 else Vector3.RIGHT).normalized(), PI) if ax.dot(to) < -0.9999 else Quaternion(ax, to)
				d = (swing.inverse() * d).normalized()
			skel.set_bone_pose_rotation(i, rest_rot.slerp(rest_rot * d, c.weight))


func _rot_global(bone: String, axis: Vector3, deg: float) -> void:
	# Rotate a bone about a skeleton-space axis relative to its rest, written as a local pose rotation.
	_rot_basis(bone, Basis(axis, deg_to_rad(deg)))


func _rot_basis(bone: String, rot: Basis) -> void:
	var i := skel.find_bone(bone); var p := skel.get_bone_parent(i)
	var want := rot * skel.get_bone_global_rest(i).basis
	skel.set_bone_pose_rotation(i, (skel.get_bone_global_pose(p).basis.inverse() * want).get_rotation_quaternion())


func _walk(t: float) -> void:
	# In-place procedural walk, 1.1 s per cycle: thighs swing 22 deg, knees bend on the passing leg, feet stay level,
	# arms counter-swing, hips bob and sway. Character faces +Z; a negative angle about +X swings a leg forward.
	var ph := TAU * t / 1.1
	for side in [["L", 0.0], ["R", PI]]:
		var s: float = sin(ph + side[1]); var knee := 38.0 * maxf(0.0, -cos(ph + side[1])) + 4.0
		var thigh := -22.0 * s
		_rot_global("J_Bip_%s_UpperLeg" % side[0], Vector3.RIGHT, thigh)
		_rot_global("J_Bip_%s_LowerLeg" % side[0], Vector3.RIGHT, thigh + knee)
		_rot_global("J_Bip_%s_Foot" % side[0], Vector3.RIGHT, -4.0 * s)
		var lower := 68.0 if side[0] == "L" else -68.0
		_rot_basis("J_Bip_%s_UpperArm" % side[0], Basis(Vector3.RIGHT, deg_to_rad(18.0 * s)) * Basis(Vector3.FORWARD, deg_to_rad(lower)))
	skel.set_bone_pose_position(skel.find_bone("J_Bip_C_Hips"), skel.get_bone_rest(skel.find_bone("J_Bip_C_Hips")).origin + Vector3(0, 0.015 * cos(2.0 * ph) - 0.01, 0))
	_rot_global("J_Bip_C_Hips", Vector3.UP, 5.0 * sin(ph))
	_rot_global("J_Bip_C_Spine", Vector3.UP, -6.0 * sin(ph))


func _wave(t: float) -> void:
	# Right arm up, forearm waving side to side in the frontal plane; left arm relaxed.
	var up := smoothstep(0.3, 0.9, t)
	_rot_global("J_Bip_R_UpperArm", Vector3.FORWARD, lerpf(-62.0, 48.0, up))
	_rot_global("J_Bip_R_LowerArm", Vector3.FORWARD, lerpf(-62.0, 95.0 + 22.0 * sin(t * 9.0) * up, up))
	_rot_global("J_Bip_R_Hand", Vector3.FORWARD, lerpf(-62.0, 95.0 + 30.0 * sin(t * 9.0 - 0.6) * up, up))
	_rot_global("J_Bip_L_UpperArm", Vector3.FORWARD, 62.0 + 3.0 * sin(t * 1.3))


func _process(delta: float) -> void:
	t += delta
	var turn := 28.0 * smoothstep(1.6, 2.1, t) * (1.0 - smoothstep(3.2, 3.7, t)) if cues.is_empty() and action == "idle" else 0.0   # one quick turn and back
	root.rotation_degrees.y = turn
	_rot_global("J_Bip_C_Hips", Vector3.UP, 3.0 * sin(t * 1.3))
	_rot_global("J_Bip_C_Spine", Vector3.UP, 3.0 * sin(t * 1.3))
	_rot_global("J_Bip_C_Chest", Vector3.RIGHT, 1.5 * sin(t * 2.4))
	_rot_global("J_Bip_C_Neck", Vector3.UP, 3.0 * sin(t * 1.3))
	_rot_global("J_Bip_C_Head", Vector3.FORWARD, 4.0 * sin(t * 0.9))
	if action == "walk": _walk(t)
	elif action == "wave": _wave(t)
	else:
		_rot_global("J_Bip_L_UpperArm", Vector3.FORWARD, 62.0 + 3.0 * sin(t * 1.3))
		_rot_global("J_Bip_R_UpperArm", Vector3.FORWARD, -62.0 + 3.0 * sin(t * 1.3))
	_apply_constraints()
	var blink := 1.0 - smoothstep(0.0, 0.07, absf(fmod(t, 3.1) - 2.9))      # a 0.14 s blink every 3.1 s
	var joy := (smoothstep(1.4, 1.9, t) * (1.0 - smoothstep(3.6, 4.2, t)) if action == "idle" else smoothstep(0.6, 1.0, t) if action == "wave" else 0.0) if cues.is_empty() else 0.0
	_expr("happy", joy); _expr("blink", blink)
	if not cues.is_empty():
		var shape := "X"
		for c in cues:
			if t - voice_start >= c.start and t - voice_start < c.end: shape = c.value
		for v in mouth:                                                     # ease toward the cue's shape, ~60 ms
			mouth[v] = lerpf(mouth[v], VISEMES[shape].get(v, 0.0), clampf(delta * 16.0, 0.0, 1.0)); _expr(v, mouth[v])
	_apply_expressions()
	_face_dirs()


func _face_dirs() -> void:
	# The SDF face shadow reads the head's current facing: call again after any later change to the head pose.
	var hb := (skel.global_transform.basis * skel.get_bone_global_pose(skel.find_bone("J_Bip_C_Head")).basis * head_rest.inverse()).orthonormalized()
	for m in face_mats:
		m.set_shader_parameter("face_forward", hb * Vector3(0, 0, 1)); m.set_shader_parameter("face_left", hb * Vector3(1, 0, 0))


func _expr(preset: String, w: float) -> void:
	if expressions.has(preset): expr_w[preset] = w


func _apply_expressions() -> void:
	# VRM 1.0 update order: binary expressions snap at 0.5; an active expression's overrideBlink/overrideMouth
	# ("block" zeroes, "blend" scales by 1 - weight) damps the blink and mouth groups; binds sum per blend shape.
	var w := {}
	for p in expr_w: w[p] = (1.0 if expr_w[p] > 0.5 else 0.0) if expressions[p].binary else expr_w[p]
	var damp := {"blink": 1.0, "mouth": 1.0}
	for p in w:
		for g in ["blink", "mouth"]:
			var mode: String = expressions[p].get("override_" + g, "none")
			if mode == "block" and w[p] > 0.0: damp[g] = 0.0
			elif mode == "blend": damp[g] = minf(damp[g], 1.0 - w[p])
	var acc := {}
	for p in w:
		var k: float = damp["blink"] if p in BLINKS else damp["mouth"] if p in MOUTHS else 1.0
		for r in expressions[p].resolved:
			var key := "%d:%d" % [r[0].get_instance_id(), r[1]]
			acc[key] = acc.get(key, 0.0) + w[p] * k * r[2]
	for tg in expr_targets:
		tg[0].set_blend_shape_value(tg[1], clampf(acc.get("%d:%d" % [tg[0].get_instance_id(), tg[1]], 0.0), 0.0, 1.0))


func _find(n: Node, pred: Callable) -> Node:
	if pred.call(n): return n
	for c in n.get_children():
		var r = _find(c, pred)
		if r: return r
	return null


func _all(n: Node, pred: Callable) -> Array:
	var out := []
	if pred.call(n): out.append(n)
	for c in n.get_children(): out.append_array(_all(c, pred))
	return out
