extends "res://toon_proof.gd"
## One actor in a shared scene: toon_proof with its own paths (set by duo.gd) plus a head-yaw schedule, so the speaker and
## listener can look at each other. look: [[time_s, yaw_deg], ...], eased between keys; the neck takes 40 %, the head ends at the full yaw.

var look := []


func _process(delta: float) -> void:
	super(delta)
	if look.is_empty(): return
	var y: float = look[0][1]
	for i in range(look.size() - 1):
		var a = look[i]; var b = look[i + 1]
		if t >= a[0] and t < b[0]: y = lerpf(a[1], b[1], smoothstep(0.0, 1.0, (t - a[0]) / maxf(b[0] - a[0], 1e-3)))
		elif t >= b[0]: y = b[1]
	_rot_global("J_Bip_C_Neck", Vector3.UP, y * 0.4 + 3.0 * sin(t * 1.3))
	_rot_global("J_Bip_C_Head", Vector3.UP, y)                             # skeleton space: the full angle, not neck + 60 %
	_apply_constraints(); _face_dirs()
