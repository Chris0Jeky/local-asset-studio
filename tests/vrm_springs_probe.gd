extends SceneTree

const Config = preload("res://vrm_spring_config.gd")
const ToonProof = preload("res://toon_proof.gd")
var failures: Array[String] = []
var cases := {}
var measurements := {}
var fixture: Dictionary
var data: Dictionary


func _initialize() -> void:
	call_deferred("run")


func check_case(label: String, passed: bool) -> void:
	cases[label] = passed
	if not passed: failures.append(label)


func make_scene() -> Dictionary:
	var model := Node3D.new(); model.name = "Model"
	var skeleton := Skeleton3D.new(); skeleton.name = "Armature"; model.add_child(skeleton)
	for node in fixture.nodes: skeleton.add_bone(node.name)
	for i in fixture.nodes.size():
		var node: Dictionary = fixture.nodes[i]
		for child in node.get("children", []): skeleton.set_bone_parent(int(child), i)
		var p: Array = node.translation
		skeleton.set_bone_rest(i, Transform3D(Basis.IDENTITY, Vector3(p[0], p[1], p[2])))
	skeleton.reset_bone_poses(); root.add_child(model)
	return {"model": model, "skeleton": skeleton}


func apply(scene: Dictionary, sidecar: Dictionary) -> Dictionary:
	var config := Config.new(); scene.skeleton.add_child(config)
	var result: Dictionary = config.configure(scene.model, sidecar)
	return {"config": config, "result": result}


func settings_match(config: Config, original: Dictionary) -> bool:
	var sim := config.simulator
	if sim == null or sim.get_setting_count() != 1 or not sim.is_config_individual(0): return false
	if sim.get_joint_count(0) != 3 or sim.is_end_bone_extended(0) or sim.get_collision_count(0) != 2: return false
	for j in original.chains[0].joint_settings.size():
		var joint: Dictionary = original.chains[0].joint_settings[j]
		if sim.get_joint_bone_name(0, j) != joint.bone: return false
		for pair in [[sim.get_joint_stiffness(0, j), joint.stiffness], [sim.get_joint_drag(0, j), joint.drag],
				[sim.get_joint_radius(0, j), joint.radius]]:
			if not is_equal_approx(float(pair[0]), float(pair[1])): return false
		var actual := sim.get_joint_gravity_direction(0, j) * sim.get_joint_gravity(0, j)
		var center: Node3D = config.bindings[0].center
		if center != null: actual = center.global_basis * actual
		var direction: Array = joint.gravity_direction
		var expected := Vector3(direction[0], direction[1], direction[2]) * float(joint.gravity)
		if not actual.is_equal_approx(expected): return false
	return true


func run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 3: push_error("expected sidecar, skeleton fixture and result paths"); quit(2); return
	data = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	fixture = JSON.parse_string(FileAccess.get_file_as_string(args[1]))
	var scene := make_scene()
	# Call the actual toon host entry without entering its unrelated camera/animation _ready path.
	var host := ToonProof.new(); host.root = scene.model; host.skel = scene.skeleton; host.springs_path = args[0]
	host._springs()
	var config: Config = host.spring_config
	check_case("production-binding", config != null and config.simulator != null and config.get_index() < config.simulator.get_index())
	if config == null or config.simulator == null:
		host.free(); scene.model.free(); finish(args[2]); return
	check_case("individual-settings", settings_match(config, data))
	await process_frame; await process_frame
	check_case("deferred-settings", settings_match(config, data))
	scene.model.rotation = Vector3(.2, .4, -.3)
	scene.skeleton.set_bone_pose_rotation(0, Quaternion(Vector3.FORWARD, .9))
	await process_frame; await process_frame
	check_case("rotated-world-gravity", settings_match(config, data))
	host.free(); scene.model.free()
	var zero := data.duplicate(true); zero.chains[0].joint_settings[0].gravity_direction = [0, 0, 0]
	scene = make_scene(); var configured := apply(scene, zero)
	check_case("zero-gravity", configured.result.ok and is_zero_approx(configured.config.simulator.get_joint_gravity(0, 0)))
	scene.model.free()
	for mode in ["bone", "node", "world"]: await center_motion(mode)
	for label in ["legacy-sidecar", "missing-bone", "missing-center", "ambiguous-center", "sparse-chain", "reordered-chain", "missing-collider", "descendant-center"]:
		var bad := data.duplicate(true); scene = make_scene()
		match label:
			"legacy-sidecar": bad.chains[0].erase("joint_settings")
			"missing-bone": bad.chains[0].joint_settings[1].bone = "Absent"
			"missing-center": bad.chains[0].center.name = "Absent"
			"ambiguous-center":
				var duplicate := Node3D.new(); duplicate.name = "J_Bip_C_Hips"; scene.model.add_child(duplicate)
			"sparse-chain": bad.chains[0].joint_settings.remove_at(1); bad.chains[0].joints = 2
			"reordered-chain": bad.chains[0].joint_settings.reverse()
			"missing-collider": bad.colliders[0].bone = "Absent"
			"descendant-center": bad.chains[0].center.name = "Skirt0_2"
		configured = apply(scene, bad)
		check_case(label, not configured.result.ok and configured.config.simulator == null and not str(configured.result.get("error", "")).is_empty())
		scene.model.free()
	finish(args[2])


func center_motion(mode: String) -> void:
	var isolated := data.duplicate(true); isolated.colliders = []; isolated.chains[0].colliders = []
	for joint in isolated.chains[0].joint_settings:
		joint.stiffness = 0.0; joint.drag = 1.0; joint.gravity = 0.0; joint.radius = 0.0
	if mode == "world": isolated.chains[0].center = null
	if mode == "node": isolated.chains[0].center = {"name": "Model", "node": 99}
	var scene := make_scene(); var configured := apply(scene, isolated)
	if not configured.result.ok:
		check_case(mode + "-center-motion", false); scene.model.free(); return
	var rotations: Array = []
	var skeleton: Skeleton3D = scene.skeleton
	configured.config.simulator.modification_processed.connect(func(): rotations.append(Quaternion.IDENTITY.angle_to(skeleton.get_bone_pose_rotation(1))))
	await process_frame; await process_frame
	rotations.clear()
	if mode == "node":
		scene.model.position = Vector3(1.3, .8, -.2); scene.model.rotation.z = .8
	else:
		skeleton.set_bone_pose_position(0, Vector3(1.3, 1.6, -.2))
		skeleton.set_bone_pose_rotation(0, Quaternion(Vector3.BACK, .8))
	await process_frame; await process_frame
	var angle: float = rotations[-1] if not rotations.is_empty() else -1.0
	measurements[mode + "-center-motion"] = {"observed_steps": rotations.size(), "joint_angle_rad": angle}
	check_case(mode + "-center-motion", not rotations.is_empty() and (angle > .1 if mode == "world" else angle < .001))
	scene.model.free()


func finish(path: String) -> void:
	var receipt := {"schema": "las.vrm-spring-test.v1", "godot": Engine.get_version_info(), "cases": cases,
		"measurements": measurements, "failures": failures}
	var out := FileAccess.open(path, FileAccess.WRITE)
	if out == null: push_error("could not retain VRM spring receipt"); quit(2); return
	out.store_string(JSON.stringify(receipt, "\t")); out.close()
	print("VRM_SPRING_RESULT ", JSON.stringify(receipt)); quit(0 if failures.is_empty() else 1)
