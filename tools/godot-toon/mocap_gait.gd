extends RefCounted
## Distance-driven mocap gait + foot IK for a host that extends toon_proof.gd and moves itself (CharacterBody3D, path
## follower...). The cycle advances by distance travelled / clip stride, so feet match any speed; idle < 0.05 m/s, walk,
## run above ~2 m/s with a positional blend between. Feet plant on ray-cast ground with a stance lock (TwoBoneIK3D).
##   var gait = preload("res://mocap_gait.gd").new()
##   func _ready(): super(); gait.setup(self, [body])          # [body]: the host's own CharacterBody3D, if any
##   func _process(delta): super(delta); gait.drive(self, delta, Vector3(body.velocity.x, 0, body.velocity.z))
## Ray casts read the physics space directly: fine with the default single-threaded physics; with
## physics/common/run_on_separate_thread enabled, call drive() from _physics_process instead.
## Needs res://mocap/walk.json and run.json (`python scripts/bvh_joints.py IN.bvh OUT.json`; not in Git). Tested with Bandai Namco Research
## Motiondataset 1 clips (CC BY-NC 4.0: attribution, non-commercial; record the licence of whatever mocap you use).

const MAP := {
	"J_Bip_C_Spine": ["Spine", "Chest"], "J_Bip_C_Chest": ["Spine", "Chest"], "J_Bip_C_UpperChest": ["Chest", "Neck"],
	"J_Bip_C_Neck": ["Neck", "Head"],
	"J_Bip_L_UpperArm": ["UpperArm_L", "LowerArm_L"], "J_Bip_L_LowerArm": ["LowerArm_L", "Hand_L"],
	"J_Bip_R_UpperArm": ["UpperArm_R", "LowerArm_R"], "J_Bip_R_LowerArm": ["LowerArm_R", "Hand_R"],
	"J_Bip_L_UpperLeg": ["UpperLeg_L", "LowerLeg_L"], "J_Bip_L_LowerLeg": ["LowerLeg_L", "Foot_L"], "J_Bip_L_Foot": ["Foot_L", "Toes_L"],
	"J_Bip_R_UpperLeg": ["UpperLeg_R", "LowerLeg_R"], "J_Bip_R_LowerLeg": ["LowerLeg_R", "Foot_R"], "J_Bip_R_Foot": ["Foot_R", "Toes_R"]}
const CHILD := {"J_Bip_C_Spine": "J_Bip_C_Chest", "J_Bip_C_Chest": "J_Bip_C_UpperChest", "J_Bip_C_UpperChest": "J_Bip_C_Neck",
	"J_Bip_C_Neck": "J_Bip_C_Head", "J_Bip_L_UpperArm": "J_Bip_L_LowerArm", "J_Bip_L_LowerArm": "J_Bip_L_Hand",
	"J_Bip_R_UpperArm": "J_Bip_R_LowerArm", "J_Bip_R_LowerArm": "J_Bip_R_Hand", "J_Bip_L_UpperLeg": "J_Bip_L_LowerLeg",
	"J_Bip_L_LowerLeg": "J_Bip_L_Foot", "J_Bip_L_Foot": "J_Bip_L_ToeBase", "J_Bip_R_UpperLeg": "J_Bip_R_LowerLeg",
	"J_Bip_R_LowerLeg": "J_Bip_R_Foot", "J_Bip_R_Foot": "J_Bip_R_ToeBase"}
const ORDER := ["J_Bip_C_Spine", "J_Bip_C_Chest", "J_Bip_C_UpperChest", "J_Bip_C_Neck", "J_Bip_L_UpperArm", "J_Bip_L_LowerArm",
	"J_Bip_R_UpperArm", "J_Bip_R_LowerArm", "J_Bip_L_UpperLeg", "J_Bip_L_LowerLeg", "J_Bip_L_Foot", "J_Bip_R_UpperLeg",
	"J_Bip_R_LowerLeg", "J_Bip_R_Foot"]
const FEET := {"L": ["J_Bip_L_UpperLeg", "J_Bip_L_LowerLeg", "J_Bip_L_Foot"], "R": ["J_Bip_R_UpperLeg", "J_Bip_R_LowerLeg", "J_Bip_R_Foot"]}
const STANCE := 0.015
const RUN_FROM := 1.7
const RUN_FULL := 2.3

var clips := {}; var stride := {}; var cycle := {}; var rest_dir := {}; var hips_i := -1; var hips_rest: Transform3D; var hips_y := 0.0
var k := 1.0; var ankle_h := 0.1; var phase := 0.0; var run_w := 0.0; var moving := 0.0
var ik: TwoBoneIK3D; var targets := {}; var poles := {}; var lock := {}; var exclude: Array[RID] = []


func setup(h, ignore: Array = []) -> void:
	# ignore: the host's own physics bodies (its CharacterBody3D), so the foot rays don't land on its capsule
	for b in ignore:
		if b is CollisionObject3D: exclude.append(b.get_rid())
	var skel: Skeleton3D = h.skel
	for c in ["walk", "run"]:
		clips[c] = JSON.parse_string(FileAccess.get_file_as_string("res://mocap/%s.json" % c))
		var fr: Array = clips[c].frames; var n := fr.size()
		stride[c] = Vector2(fr[n - 1]["Hips"][0] - fr[0]["Hips"][0], fr[n - 1]["Hips"][2] - fr[0]["Hips"][2]).length()
		cycle[c] = (n - 1) / float(clips[c].fps)
	hips_i = skel.find_bone("J_Bip_C_Hips"); hips_rest = skel.get_bone_rest(hips_i); hips_y = skel.get_bone_global_rest(hips_i).origin.y
	for b in CHILD: rest_dir[b] = (skel.get_bone_global_rest(skel.find_bone(CHILD[b])).origin - skel.get_bone_global_rest(skel.find_bone(b)).origin).normalized()
	var hl := skel.get_bone_global_rest(skel.find_bone("J_Bip_L_UpperLeg")).origin; var hr := skel.get_bone_global_rest(skel.find_bone("J_Bip_R_UpperLeg")).origin
	rest_dir["side"] = (hl - hr).normalized()
	rest_dir["up"] = (skel.get_bone_global_rest(skel.find_bone("J_Bip_C_Spine")).origin - skel.get_bone_global_rest(hips_i).origin).normalized()
	k = hips_y / float(clips["walk"].frames[0]["Hips"][1]); ankle_h = skel.get_bone_global_rest(skel.find_bone("J_Bip_L_Foot")).origin.y
	ik = TwoBoneIK3D.new(); skel.add_child(ik); skel.move_child(ik, 0); ik.set_setting_count(2); var i := 0
	for side in FEET:
		var t := Node3D.new(); h.add_child(t); targets[side] = t; var p := Node3D.new(); h.add_child(p); poles[side] = p
		ik.set_root_bone_name(i, FEET[side][0]); ik.set_middle_bone_name(i, FEET[side][1]); ik.set_end_bone_name(i, FEET[side][2])
		ik.set_target_node(i, ik.get_path_to(t)); ik.set_pole_node(i, ik.get_path_to(p)); i += 1


func _sample(c: String, ph: float) -> Dictionary:
	# Positions at normalised cycle phase ph (0..1), hips' horizontal travel removed (the host moves the body).
	var fr: Array = clips[c].frames; var n := fr.size()
	var u := fposmod(ph, 1.0) * (n - 1); var i := int(u); var w := u - i
	var a: Dictionary = fr[i]; var b: Dictionary = fr[min(i + 1, n - 1)]; var out := {}
	var hips := Vector3(a["Hips"][0], 0, a["Hips"][2]).lerp(Vector3(b["Hips"][0], 0, b["Hips"][2]), w)
	for j in a: out[j] = Vector3(a[j][0], a[j][1], a[j][2]).lerp(Vector3(b[j][0], b[j][1], b[j][2]), w) - hips
	return out


func drive(h, delta: float, velocity_xz: Vector3) -> void:
	var skel: Skeleton3D = h.skel; var speed := velocity_xz.length()
	moving = move_toward(moving, 1.0 if speed > 0.05 else 0.0, delta * 4.0)            # ease in and out of idle
	run_w = clampf((speed - RUN_FROM) / (RUN_FULL - RUN_FROM), 0.0, 1.0)
	phase = fposmod(phase + speed * delta / (lerpf(stride["walk"], stride["run"], run_w) * k), 1.0)   # one phase, blended stride
	if moving > 0.0:
		var idle := {}                                                    # host's pose (e.g. lowered idle arms) as world deltas,
		for bone in ["J_Bip_C_Hips"] + ORDER:                               # captured before any write: the blend starts from it
			var bi := skel.find_bone(bone)
			idle[bone] = (skel.get_bone_global_pose(bi).basis * skel.get_bone_global_rest(bi).basis.inverse()).get_rotation_quaternion()
		var pw := _sample("walk", phase); var pr := _sample("run", phase) if run_w > 0.0 else pw
		var P := {}
		for j in pw: P[j] = pw[j].lerp(pr[j], run_w)
		skel.set_bone_pose_position(hips_i, hips_rest.origin + Vector3(0, (P["Hips"].y * k - hips_y) * moving, 0))
		var up: Vector3 = (P["Spine"] - P["Hips"]).normalized(); var side: Vector3 = (P["UpperLeg_L"] - P["UpperLeg_R"]).normalized()
		var bs := Basis(side, up, side.cross(up).normalized()).orthonormalized()
		var br := Basis(rest_dir["side"], rest_dir["up"], rest_dir["side"].cross(rest_dir["up"]).normalized()).orthonormalized()
		h._rot_basis("J_Bip_C_Hips", Basis(idle["J_Bip_C_Hips"].slerp((bs * br.inverse()).get_rotation_quaternion(), moving)))
		for bone in ORDER:
			var m: Array = MAP[bone]; var d: Vector3 = (P[m[1]] - P[m[0]]).normalized()
			h._rot_basis(bone, Basis(idle[bone].slerp(Quaternion(rest_dir[bone], d), moving)))
		h._apply_constraints()
	_feet(h)


func _feet(h) -> void:
	var skel: Skeleton3D = h.skel; var space: PhysicsDirectSpaceState3D = h.get_world_3d().direct_space_state
	for side in FEET:
		var p: Vector3 = skel.global_transform * skel.get_bone_global_pose(skel.find_bone(FEET[side][2])).origin
		var lift: float = p.y - h.root.global_position.y
		if lift < ankle_h + STANCE:
			if not lock.has(side): lock[side] = Vector3(p.x, 0, p.z)
		else: lock.erase(side)
		var at: Vector3 = Vector3(lock[side].x, p.y, lock[side].z) if lock.has(side) else p    # ground under the planted spot
		var q := PhysicsRayQueryParameters3D.create(at + Vector3(0, 0.8, 0), at + Vector3(0, -1.2, 0)); q.exclude = exclude
		var hit := space.intersect_ray(q)
		var g: float = hit.position.y if hit else h.root.global_position.y
		var want := Vector3(at.x, g + (maxf(lift, ankle_h) if lock.has(side) else lift), at.z)
		targets[side].global_position = want
		var knee: Vector3 = skel.global_transform * skel.get_bone_global_pose(skel.find_bone(FEET[side][1])).origin
		poles[side].global_position = knee + h.root.global_transform.basis.z * 0.6
