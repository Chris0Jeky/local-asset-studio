extends Node3D
## VRM toon runtime proof (see docs/ANIME-TOON-KIT.md). Copy a VRM 1.0 file in as res://model.glb, its spring data as
## res://springs.json (`python scripts/vrm_toon.py springs`) and its SDF face map as res://face_sdf.png, then run the
## project. Toon light() shader, hull outlines, SpringBoneSimulator3D from the VRM's own springs, a procedural idle with
## one quick body turn so skirt and hair visibly swing. Material roles follow `vrm_toon.material_role`.

const SHADE := {"skin": Vector3(.93, .76, .74), "face": Vector3(.93, .76, .74), "hair": Vector3(.50, .64, .74), "cloth": Vector3(.62, .62, .78)}

var skel: Skeleton3D
var root: Node3D
var face_mats: Array[ShaderMaterial] = []
var head_rest: Basis
var t := 0.0


func _ready() -> void:
	root = load("res://model.glb").instantiate()
	add_child(root)
	skel = _find(root, func(n): return n is Skeleton3D)
	for mi in _all(root, func(n): return n is MeshInstance3D):
		_restyle(mi)
	_springs()
	head_rest = skel.get_bone_global_rest(skel.find_bone("J_Bip_C_Head")).basis
	var cam := Camera3D.new(); add_child(cam)
	cam.position = Vector3(0.9, 1.15, 2.6); cam.look_at(Vector3(0, 0.88, 0)); cam.fov = 35
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
				m.set_shader_parameter("face_sdf", true); m.set_shader_parameter("sdf_tex", load("res://face_sdf.png")); face_mats.append(m)
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
	var data = JSON.parse_string(FileAccess.get_file_as_string("res://springs.json"))
	var sim := SpringBoneSimulator3D.new(); skel.add_child(sim)
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
		sim.add_child(col)
	sim.set_setting_count(data.chains.size())
	for i in data.chains.size():
		var ch = data.chains[i]
		sim.set_root_bone_name(i, ch.root); sim.set_end_bone_name(i, ch.end)
		sim.set_stiffness(i, ch.stiffness); sim.set_drag(i, ch.drag); sim.set_gravity(i, ch.gravity); sim.set_radius(i, ch.radius)
		sim.set_enable_all_child_collisions(i, true)
	print("TOON springs=", sim.get_setting_count(), " colliders=", data.colliders.size())


func _rot_global(bone: String, axis: Vector3, deg: float) -> void:
	# Rotate a bone about a skeleton-space axis relative to its rest, written as a local pose rotation.
	var i := skel.find_bone(bone); var p := skel.get_bone_parent(i)
	var want := Basis(axis, deg_to_rad(deg)) * skel.get_bone_global_rest(i).basis
	skel.set_bone_pose_rotation(i, (skel.get_bone_global_pose(p).basis.inverse() * want).get_rotation_quaternion())


func _process(delta: float) -> void:
	t += delta
	var turn := 28.0 * smoothstep(1.6, 2.1, t) * (1.0 - smoothstep(3.2, 3.7, t))   # one quick turn and back
	root.rotation_degrees.y = turn
	_rot_global("J_Bip_C_Hips", Vector3.UP, 3.0 * sin(t * 1.3))
	_rot_global("J_Bip_C_Spine", Vector3.UP, 3.0 * sin(t * 1.3))
	_rot_global("J_Bip_C_Chest", Vector3.RIGHT, 1.5 * sin(t * 2.4))
	_rot_global("J_Bip_C_Neck", Vector3.UP, 3.0 * sin(t * 1.3))
	_rot_global("J_Bip_C_Head", Vector3.FORWARD, 4.0 * sin(t * 0.9))
	_rot_global("J_Bip_L_UpperArm", Vector3.FORWARD, 62.0 + 3.0 * sin(t * 1.3))
	_rot_global("J_Bip_R_UpperArm", Vector3.FORWARD, -62.0 + 3.0 * sin(t * 1.3))
	var hb := (skel.global_transform.basis * skel.get_bone_global_pose(skel.find_bone("J_Bip_C_Head")).basis * head_rest.inverse()).orthonormalized()
	for m in face_mats:
		m.set_shader_parameter("face_forward", hb * Vector3(0, 0, 1)); m.set_shader_parameter("face_left", hb * Vector3(1, 0, 0))


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
