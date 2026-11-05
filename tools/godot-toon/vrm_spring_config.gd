extends SkeletonModifier3D
## Binds a regenerated VRM sidecar before SpringBoneSimulator3D runs. Both modifiers are children of the same
## skeleton, in this order, so actor/mocap/constraint pose changes are already visible when centers are read.

var simulator: SpringBoneSimulator3D
var bindings: Array = []
var failure := ""


func configure(model: Node3D, data: Dictionary) -> Dictionary:
	if simulator != null: return _refuse("Spring settings are already configured")
	failure = ""
	var skeleton := get_skeleton()
	if skeleton == null or not skeleton.is_inside_tree(): return _refuse("Spring configuration needs an attached Skeleton3D")
	if not data.get("chains") is Array or not data.get("colliders") is Array: return _refuse("Invalid spring sidecar")
	var plans: Array = []
	for chain in data.chains:
		if not chain is Dictionary or not chain.get("joint_settings") is Array or not chain.has("center"):
			return _refuse("Regenerate springs.json with vrm_toon.py springs; this sidecar has no per-joint settings")
		var joints: Array = chain.joint_settings
		if joints.size() < 2 or not _index(chain.get("joints"), joints.size() + 1) or int(chain.joints) != joints.size():
			return _refuse("Spring joint count does not match its settings")
		var bones: Array[int] = []
		for joint in joints:
			if not joint is Dictionary or not joint.get("bone") is String: return _refuse("Invalid spring joint name")
			var bone := skeleton.find_bone(joint.bone)
			if bone < 0: return _refuse("Missing imported spring bone: " + joint.bone)
			if not bones.is_empty() and skeleton.get_bone_parent(bone) != bones[-1]:
				return _refuse("Spring joints must be consecutive imported bones; sparse or reordered chains are unsupported")
			for key in ["stiffness", "drag", "gravity", "radius"]:
				if not _number(joint.get(key)) or float(joint[key]) < 0.0: return _refuse("Invalid spring " + key)
			if float(joint.drag) > 1.0 or not _vector(joint.get("gravity_direction")): return _refuse("Invalid spring drag or gravity direction")
			bones.append(bone)
		if chain.get("root") != joints[0].bone or chain.get("end") != joints[-1].bone:
			return _refuse("Spring endpoints do not match the authored joints")
		if not chain.get("colliders") is Array: return _refuse("Invalid spring collider list")
		for index in chain.colliders:
			if not _index(index, data.colliders.size()): return _refuse("Missing spring collider index")
		var center_bone := -1
		var center_node: Node3D = null
		if chain.center != null:
			if not chain.center is Dictionary or not chain.center.get("name") is String: return _refuse("Invalid spring center")
			var center_name: String = chain.center.name
			center_bone = skeleton.find_bone(center_name)
			var nodes := _named_nodes(model, center_name)
			if nodes.size() + int(center_bone >= 0) != 1: return _refuse("Missing or ambiguous imported spring center: " + center_name)
			if center_bone >= 0:
				if not _bone_ancestor(skeleton, center_bone, bones[0]): return _refuse("Spring center must be its root or an ancestor")
			else:
				center_node = nodes[0] as Node3D
				if center_node != skeleton and not center_node.is_ancestor_of(skeleton): return _refuse("Spring center node must contain the skeleton")
		plans.append({"chain": chain, "bones": bones, "center_bone": center_bone, "center_node": center_node})
	for i in plans.size():
		if int(plans[i].center_bone) < 0: continue
		for k in plans.size():
			if i != k:
				for bone in plans[k].bones:
					if _bone_ancestor(skeleton, int(bone), int(plans[i].center_bone)):
						return _refuse("Spring center cannot depend on another simulated chain")
	for collider in data.colliders:
		if not collider is Dictionary or not collider.get("bone") is String or skeleton.find_bone(collider.bone) < 0:
			return _refuse("Missing imported collider bone")
		if collider.get("type") not in ["sphere", "capsule"] or not _vector(collider.get("offset")):
			return _refuse("Invalid spring collider shape")
		if not _number(collider.get("radius")) or float(collider.radius) < 0.0: return _refuse("Invalid spring collider radius")
		if collider.type == "capsule" and not _vector(collider.get("tail")): return _refuse("Invalid spring collider tail")

	simulator = SpringBoneSimulator3D.new(); simulator.name = "VrmSpringSimulator"; simulator.active = false
	skeleton.add_child(simulator)
	var colliders: Array[SpringBoneCollision3D] = []
	for collider in data.colliders:
		var node: SpringBoneCollision3D
		var offset := _v(collider.offset)
		if collider.type == "sphere":
			node = SpringBoneCollisionSphere3D.new(); node.radius = collider.radius; node.position_offset = offset
		else:
			var tail := _v(collider.tail); var axis := tail - offset
			node = SpringBoneCollisionCapsule3D.new(); node.radius = collider.radius; node.height = axis.length() + 2.0 * collider.radius
			node.position_offset = (offset + tail) * .5
			if axis.length() > 1e-5: node.rotation_offset = Quaternion(Vector3.UP, axis.normalized())
		node.bone_name = collider.bone; simulator.add_child(node); colliders.append(node)
	simulator.set_setting_count(plans.size())
	for i in plans.size():
		var plan: Dictionary = plans[i]; var chain: Dictionary = plan.chain
		simulator.set_root_bone(i, plan.bones[0]); simulator.set_end_bone(i, plan.bones[-1])
		simulator.set_extend_end_bone(i, false)                         # the final VRM joint is a tail, not another segment
		if simulator.get_joint_count(i) != plan.bones.size(): return _discard("Godot expanded the authored spring chain")
		for j in plan.bones.size():
			if simulator.get_joint_bone(i, j) != int(plan.bones[j]): return _discard("Godot changed the authored spring joint order")
		simulator.set_individual_config(i, true)
		var center: Node3D = plan.center_node
		if int(plan.center_bone) >= 0:
			center = Node3D.new(); center.name = "Center_%d" % i; add_child(center)
		if center == null:
			simulator.set_center_from(i, SpringBoneSimulator3D.CENTER_FROM_WORLD_ORIGIN)
		else:
			simulator.set_center_from(i, SpringBoneSimulator3D.CENTER_FROM_NODE)
			simulator.set_center_node(i, simulator.get_path_to(center))
		bindings.append({"center": center, "bone": plan.center_bone, "joints": chain.joint_settings})
		for j in chain.joint_settings.size():
			var joint: Dictionary = chain.joint_settings[j]
			simulator.set_joint_stiffness(i, j, joint.stiffness); simulator.set_joint_drag(i, j, joint.drag)
			simulator.set_joint_radius(i, j, joint.radius)
		simulator.set_enable_all_child_collisions(i, false)
		simulator.set_collision_count(i, chain.colliders.size())
		for k in chain.colliders.size(): simulator.set_collision_path(i, k, simulator.get_path_to(colliders[int(chain.colliders[k])]))
	_process_modification(0.0)
	if not failure.is_empty(): return _discard(failure)
	simulator.active = true; simulator.reset()
	return {"ok": true, "chains": plans.size(), "colliders": colliders.size()}


func _process_modification(_delta: float) -> void:
	if not is_instance_valid(simulator): return
	var skeleton := get_skeleton()
	for i in bindings.size():
		var binding: Dictionary = bindings[i]
		if binding.center != null and not is_instance_valid(binding.center):
			failure = "Spring center was removed"; simulator.active = false; active = false
			push_error(failure); return
		var center: Node3D = binding.center
		var world_to_center := Basis.IDENTITY
		if int(binding.bone) >= 0: center.transform = skeleton.get_bone_global_pose(int(binding.bone))
		if center != null:
			if is_zero_approx(center.global_basis.determinant()):
				failure = "Spring center has a singular transform"; simulator.active = false; active = false
				push_error(failure); return
			world_to_center = center.global_basis.inverse()
		for j in binding.joints.size():
			var joint: Dictionary = binding.joints[j]
			# The engine integrates in center coordinates. VRM gravity remains world-space when that center rotates.
			var direction := world_to_center * _v(joint.gravity_direction)
			var magnitude := direction.length()
			simulator.set_joint_gravity_direction(i, j, direction / magnitude if magnitude > 0.0 else Vector3.DOWN)
			simulator.set_joint_gravity(i, j, float(joint.gravity) * magnitude)


func _discard(message: String) -> Dictionary:
	if simulator != null: simulator.free(); simulator = null
	for binding in bindings:
		if int(binding.bone) >= 0: binding.center.free()
	bindings.clear()
	return _refuse(message)


func _refuse(message: String) -> Dictionary:
	failure = message
	return {"ok": false, "error": message}


static func _number(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value))


static func _index(value: Variant, count: int) -> bool:
	return _number(value) and float(value) == floor(float(value)) and float(value) >= 0 and float(value) < count


static func _vector(value: Variant) -> bool:
	return value is Array and value.size() == 3 and _number(value[0]) and _number(value[1]) and _number(value[2])


static func _v(value: Array) -> Vector3:
	return Vector3(value[0], value[1], value[2])


static func _named_nodes(model: Node3D, wanted: String) -> Array[Node3D]:
	var found: Array[Node3D] = []
	if model.name == wanted: found.append(model)
	for node in model.find_children("*", "Node3D", true, false):
		if node.name == wanted: found.append(node as Node3D)
	return found


static func _bone_ancestor(skeleton: Skeleton3D, ancestor: int, bone: int) -> bool:
	while bone >= 0:
		if bone == ancestor: return true
		bone = skeleton.get_bone_parent(bone)
	return false
