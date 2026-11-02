extends "res://toon_proof.gd"
## Talking companion on the toon proof (docs/COMPANION-LOOP.md): a chat box over loopback TCP to
## scripts/companion_loop.py (NDJSON). Each finished sentence arrives with its Kokoro WAV, mouth cues and a mood;
## sentences play back to back with the mouth driven from the audio clock, the mood eased onto VRM expressions, a wave
## on greetings, a nod, and gaze at the camera (up and away while the reply is being written).
## Optional res://set.glb (toon-dressed around the character) and res://companion.json:
## {"name": "Suzu", "home": [x, y, z], "yaw": deg, "camera": {"pos": [x, y, z], "look": [x, y, z], "fov": 30}}.
## Args after `--`: --demo=lines.txt (types each line, waits for the reply), --log=turns.jsonl, --port=8095.

const MOODS := {"happy": {"happy": .6}, "curious": {"surprised": .4}, "thinking": {"relaxed": .45}, "apologetic": {"sad": .6}}
const GREETING := ["hi", "hello", "hey", "morning", "evening", "bye", "goodbye", "see you", "good night"]

var tcp := StreamPeerTCP.new()
var rx := PackedByteArray()
var port := 8095
var log_path := "user://companion-turns.jsonl"
var cfg := {"name": "Suzu", "home": [0.0, 0.0, 0.0], "yaw": 0.0, "camera": {"pos": [0.45, 1.45, 1.6], "look": [0.0, 1.3, 0.0], "fov": 30.0}}
var pending := []                      # sentence events waiting for the speaker
var player: AudioStreamPlayer
var speaking := {}                     # the sentence now playing
var mood := "happy"
var mood_w := {}                       # eased expression weights
var waiting := false                   # enter pressed, no audio yet (thinking pose)
var busy := false                      # a turn is in flight: until its done event has arrived and its audio has played
var wave_from := -100.0                # gesture clock
var nod_from := -100.0
var turn := {}                         # timing record for the current turn
var log_box: RichTextLabel
var input: LineEdit
var bubble := ""
var demo := []
var demo_state := "idle"; var demo_at := 0.0; var demo_typed := 0
var movie := false; var wall0 := 0
var cam: Camera3D
var eye_rest := {}
var props := {}                        # set node name -> world-space centre, for "look" (scene awareness)
var look_w := 0.0                      # eased weight of the look toward a named prop
var look_at_prop := Vector3.ZERO
var mouth_log := PackedStringArray(["t,talking,open"])     # Movie Maker runs: frame n is audio time n / fps


func _ready() -> void:
	super()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--demo="): demo = Array(FileAccess.get_file_as_string(a.trim_prefix("--demo=")).strip_edges().split("\n"))
		elif a.begins_with("--log="): log_path = a.trim_prefix("--log=")
		elif a.begins_with("--port="): port = int(a.trim_prefix("--port="))
	movie = Engine.get_write_movie_path() != ""; wall0 = Time.get_ticks_usec()
	if FileAccess.file_exists("res://companion.json"): cfg.merge(JSON.parse_string(FileAccess.get_file_as_string("res://companion.json")), true)
	if ResourceLoader.exists("res://set.glb"): _dress_set()
	cam = _find(self, func(n): return n is Camera3D)
	var c: Dictionary = cfg.camera
	cam.fov = c.fov; cam.position = _v(c.pos); cam.look_at(_v(c.look))
	for e in ["J_Adj_L_FaceEye", "J_Adj_R_FaceEye"]: eye_rest[e] = skel.get_bone_rest(skel.find_bone(e)).basis.get_rotation_quaternion()
	player = AudioStreamPlayer.new(); add_child(player); player.finished.connect(_next_sentence)
	_build_ui()
	tcp.connect_to_host("127.0.0.1", port)
	_say_system("Connecting to %s…" % cfg.name)


func _dress_set() -> void:
	var set: Node3D = load("res://set.glb").instantiate(); add_child(set)
	for mi in _all(set, func(n): return n is MeshInstance3D):
		var box: AABB = mi.global_transform * mi.get_aabb(); var up: Node = mi      # every named node up to the set root
		while up != set.get_parent():                                                   # gets the merged bounds of its meshes
			props[String(up.name)] = props[String(up.name)].merge(box) if props.has(String(up.name)) else box; up = up.get_parent()
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		for s in mi.mesh.get_surface_count():
			var src = mi.get_active_material(s)
			if not (src is BaseMaterial3D): continue
			var m: StandardMaterial3D = src.duplicate()
			m.diffuse_mode = BaseMaterial3D.DIFFUSE_TOON; m.specular_mode = BaseMaterial3D.SPECULAR_TOON; m.roughness = 1.0
			m.emission_enabled = true; m.emission = m.albedo_color; m.emission_energy_multiplier = 0.35
			if m.albedo_texture: m.emission_texture = m.albedo_texture
			var n := String(mi.name).to_lower()
			if not (n.contains("glass") or n.contains("rug")):
				var o := ShaderMaterial.new(); o.shader = load("res://outline.gdshader"); o.set_shader_parameter("width", 0.008)
				m.next_pass = o
			mi.set_surface_override_material(s, m)


func _build_ui() -> void:
	var ui := CanvasLayer.new(); add_child(ui)
	var panel := PanelContainer.new(); ui.add_child(panel)
	panel.anchor_left = 0.60; panel.anchor_right = 0.98; panel.anchor_top = 0.04; panel.anchor_bottom = 0.96
	var sb := StyleBoxFlat.new(); sb.bg_color = Color(0.08, 0.10, 0.16, 0.72); sb.set_corner_radius_all(10); sb.set_content_margin_all(12)
	panel.add_theme_stylebox_override("panel", sb)
	var box := VBoxContainer.new(); panel.add_child(box)
	var title := Label.new(); title.text = "Talk to " + cfg.name; title.add_theme_font_size_override("font_size", 22); box.add_child(title)
	log_box = RichTextLabel.new(); log_box.bbcode_enabled = true; log_box.scroll_following = true
	log_box.size_flags_vertical = Control.SIZE_EXPAND_FILL; log_box.add_theme_font_size_override("normal_font_size", 17); box.add_child(log_box)
	input = LineEdit.new(); input.placeholder_text = _prompt(); input.add_theme_font_size_override("font_size", 17)
	input.text_submitted.connect(_submit); box.add_child(input)
	if demo.is_empty(): input.grab_focus()


func _say_system(s: String) -> void: log_box.append_text("[color=#8a93a6][i]%s[/i][/color]\n" % s)


func _submit(text: String) -> void:
	text = text.strip_edges()
	if text.is_empty() or busy or tcp.get_status() != StreamPeerTCP.STATUS_CONNECTED: return
	input.clear()
	log_box.append_text("[color=#9fd3ff][b]You:[/b] %s[/color]\n" % text.replace("[", "[lb]"))
	turn = {"user": text, "enter_us": Time.get_ticks_usec(), "movie": movie}
	waiting = true; busy = true; bubble = ""
	var low := text.to_lower()
	if GREETING.any(func(g): return low.begins_with(g) or low.contains(" " + g)): turn["wave"] = true
	tcp.put_data((JSON.stringify({"type": "say", "text": text}) + "\n").to_utf8_buffer())


func _poll() -> void:
	tcp.poll()
	var st := tcp.get_status()
	if st == StreamPeerTCP.STATUS_ERROR or st == StreamPeerTCP.STATUS_NONE:
		if busy:                                                             # the sidecar went away mid-turn: end it here
			_say_system("Lost the connection; reconnecting."); turn["done"] = true; rx.clear()
			if speaking.is_empty(): _finish_turn()
		tcp = StreamPeerTCP.new(); tcp.connect_to_host("127.0.0.1", port); return
	if st != StreamPeerTCP.STATUS_CONNECTED: return
	var n := tcp.get_available_bytes()
	if n > 0: rx.append_array(tcp.get_data(n)[1])
	while true:
		var nl := rx.find(10)
		if nl < 0: break
		var line := rx.slice(0, nl).get_string_from_utf8(); rx = rx.slice(nl + 1)
		var ev = JSON.parse_string(line)
		if ev is Dictionary: _on_event(ev)


func _on_event(ev: Dictionary) -> void:
	match ev.type:
		"hello": _say_system("%s is here. Type below and press Enter." % cfg.name)
		"token": bubble += ev.text
		"sentence":
			if not turn.has("first_sentence_us"): turn["first_sentence_us"] = Time.get_ticks_usec(); turn["sidecar_ms"] = ev.ms; turn["lead_s"] = ev.lead_s
			pending.append(ev)
			if speaking.is_empty(): _next_sentence()
		"done":
			turn["done_us"] = Time.get_ticks_usec(); turn["reply"] = ev.reply; turn["sidecar"] = ev.ms; turn["sentences"] = ev.sentences.size()
			var shown := " ".join(ev.sentences.map(func(s): return s.text))
			log_box.append_text("[color=#ffd9a8][b]%s[/b] [i](%s)[/i]: %s[/color]\n" % [cfg.name, ev.emotion, shown.replace("[", "[lb]")])
			if ev.sentences.is_empty(): _say_system("No spoken reply (%s)." % ev.ms.get("error", "empty"))
			for f in ev.facts: _say_system("%s will remember: %s" % [cfg.name, f])
			turn["done"] = true
			if speaking.is_empty() and pending.is_empty(): _finish_turn()


func _next_sentence() -> void:
	if pending.is_empty():
		speaking = {}
		if turn.get("done", false): _finish_turn()
		return
	speaking = pending.pop_front()
	var stream := AudioStreamWAV.load_from_file(speaking.wav)
	player.stream = stream; player.play()
	if speaking.i == 0:
		waiting = false
		turn["play_us"] = Time.get_ticks_usec(); turn["output_latency_s"] = AudioServer.get_output_latency()
		if turn.get("wave", false): wave_from = t
		elif speaking.emotion in ["happy", "apologetic"]: nod_from = t
	if speaking.emotion != mood and speaking.emotion in MOODS: mood = speaking.emotion


func _finish_turn() -> void:
	waiting = false; busy = false
	if not turn.has("enter_us") or turn.has("logged"): return
	turn["logged"] = true
	var e: int = turn.enter_us
	var rec := {"user": turn.user, "reply": turn.get("reply", ""), "movie": movie, "sentences": turn.get("sentences", 0),
		"enter_to_first_sentence_ms": (turn.get("first_sentence_us", e) - e) / 1000.0,
		"enter_to_play_ms": (turn.get("play_us", e) - e) / 1000.0,
		"enter_to_first_audible_ms": (turn.get("play_us", e) - e) / 1000.0 + 1000.0 * (turn.get("lead_s", 0.0) + turn.get("output_latency_s", 0.0)),
		"output_latency_s": turn.get("output_latency_s", 0.0), "sidecar_first": turn.get("sidecar_ms", {}), "sidecar": turn.get("sidecar", {}),
		"enter_to_audio_end_ms": (Time.get_ticks_usec() - e) / 1000.0}
	var f := FileAccess.open(log_path, FileAccess.READ_WRITE if FileAccess.file_exists(log_path) else FileAccess.WRITE)
	f.seek_end(); f.store_line(JSON.stringify(rec)); f.close()
	print("TURN ", JSON.stringify(rec))
	if demo_state == "reply": demo_state = "pause"; demo_at = t


func _demo(delta: float) -> void:
	if demo_state == "off" or tcp.get_status() != StreamPeerTCP.STATUS_CONNECTED: return
	match demo_state:
		"idle":
			if demo.is_empty(): demo_state = "off"
			elif t > 2.0: demo_state = "type"; demo_at = t; demo_typed = 0
		"type":
			var line: String = demo[0]
			var want := int((t - demo_at) / 0.045)
			if want > demo_typed: demo_typed = mini(want, line.length()); input.text = line.substr(0, demo_typed); input.caret_column = demo_typed
			if demo_typed >= line.length() and t - demo_at > line.length() * 0.045 + 0.4:
				demo.pop_front(); _submit(line); demo_state = "reply"
		"pause":
			if t - demo_at > 1.4:
				if demo.is_empty(): demo_state = "end"; demo_at = t
				else: demo_state = "type"; demo_at = t; demo_typed = 0
		"end":
			if t - demo_at > 1.5: _quit()


func _mouth_pos() -> float:
	return player.get_playback_position() + AudioServer.get_time_since_last_mix() - AudioServer.get_output_latency()


func _process(delta: float) -> void:
	if movie:                                                                # Movie Maker: keep game time on the wall clock so
		while Time.get_ticks_usec() < wall0 + int((t + delta) * 1e6): OS.delay_usec(500)   # waits look real
	t += delta
	_poll(); _demo(delta)
	root.position = _v(cfg.home); root.rotation_degrees.y = cfg.yaw
	var think := 1.0 if waiting else 0.0
	_rot_global("J_Bip_C_Hips", Vector3.UP, 3.0 * sin(t * 1.3))
	_rot_global("J_Bip_C_Spine", Vector3.UP, 3.0 * sin(t * 1.3))
	_rot_global("J_Bip_C_Chest", Vector3.RIGHT, 1.5 * sin(t * 2.4))
	# arms: idle, or the toon kit's wave on a greeting (up 0.6 s, wave, down after 2.6 s)
	var w := t - wave_from; var up := smoothstep(0.0, 0.6, w) * (1.0 - smoothstep(2.6, 3.2, w))
	_rot_global("J_Bip_R_UpperArm", Vector3.FORWARD, lerpf(-62.0 + 3.0 * sin(t * 1.3), 48.0, up))
	_rot_global("J_Bip_R_LowerArm", Vector3.FORWARD, lerpf(-62.0, 95.0 + 22.0 * sin(t * 9.0), up))
	_rot_global("J_Bip_R_Hand", Vector3.FORWARD, lerpf(-62.0, 95.0 + 30.0 * sin(t * 9.0 - 0.6), up))
	_rot_global("J_Bip_L_UpperArm", Vector3.FORWARD, 62.0 + 3.0 * sin(t * 1.3))
	# head: gaze at the camera, tilt per mood, look up and away while thinking, a nod on happy/apologetic replies
	var nod := sin(clampf((t - nod_from) / 0.5, 0.0, 1.0) * PI) * 8.0
	var tilt: float = {"curious": 10.0, "thinking": -6.0, "apologetic": 4.0}.get(mood, 0.0) * (0.0 if waiting else 1.0) + 9.0 * think
	var bow: float = {"apologetic": 8.0}.get(mood, 0.0) + nod - 7.0 * think
	# a sentence that names a set prop turns the head (up to 35 deg) and eyes toward it while it plays
	var prop = props[speaking.look].get_center() if talking_now() and props.has(str(speaking.get("look", ""))) else null
	look_w = lerpf(look_w, 1.0 if prop != null else 0.0, clampf(delta * 4.0, 0.0, 1.0))
	if prop != null: look_at_prop = prop
	var d := (skel.global_transform.basis.inverse() * (look_at_prop - skel.global_transform * skel.get_bone_global_pose(skel.find_bone("J_Bip_C_Head")).origin)).normalized()
	var full := rad_to_deg(atan2(d.x, d.z))
	if absf(full) > 100.0:                                                     # behind her: glance to the side it shows on screen
		var head_x := (cam.global_transform.affine_inverse() * (skel.global_transform * skel.get_bone_global_pose(skel.find_bone("J_Bip_C_Head")).origin)).x
		full = 35.0 if (cam.global_transform.affine_inverse() * look_at_prop).x > head_x else -35.0
	var yaw := clampf(full, -35.0, 35.0) * look_w; var pitch := clampf(rad_to_deg(asin(d.y)), -20.0, 20.0) * look_w
	_rot_basis("J_Bip_C_Head", Basis(Vector3.UP, deg_to_rad(yaw)) * Basis(Vector3.RIGHT, deg_to_rad(-pitch + bow)) * Basis(Vector3.FORWARD, deg_to_rad(tilt + 3.0 * sin(t * 0.9))))
	_gaze(think)
	_apply_constraints()
	# face: blink, mood, mouth from the sentence cues on the audio clock
	var blink := 1.0 - smoothstep(0.0, 0.07, absf(fmod(t, 3.7) - 3.5))
	_expr("blink", blink * (1.0 - 0.6 * think))
	var talking := not speaking.is_empty() and player.playing
	var target_mood := "thinking" if waiting else mood
	for m in MOODS:
		for p in MOODS[m]:
			var want: float = MOODS[m][p] * (0.55 if talking else 1.0) if m == target_mood else 0.0
			mood_w[p] = lerpf(mood_w.get(p, 0.0), want, clampf(delta * 5.0, 0.0, 1.0)); _expr(p, mood_w[p])
	var shape := "X"
	if talking:
		var pos := _mouth_pos()
		for c in speaking.cues:
			if pos >= c.start and pos < c.end: shape = c.value
	for v in mouth:
		mouth[v] = lerpf(mouth[v], VISEMES[shape].get(v, 0.0), clampf(delta * 18.0, 0.0, 1.0)); _expr(v, mouth[v])
	_apply_expressions()
	if movie: mouth_log.append("%.4f,%d,%.4f" % [t, int(talking), mouth.aa + 0.8 * mouth.oh + 0.6 * (mouth.ou + mouth.ee) + 0.4 * mouth.ih])
	var hb := (skel.global_transform.basis * skel.get_bone_global_pose(skel.find_bone("J_Bip_C_Head")).basis * head_rest.inverse()).orthonormalized()
	for m in face_mats:
		m.set_shader_parameter("face_forward", hb * Vector3(0, 0, 1)); m.set_shader_parameter("face_left", hb * Vector3(1, 0, 0))
	if waiting and not bubble.is_empty(): input.placeholder_text = cfg.name + ": " + _strip_tags(bubble)
	elif not waiting: input.placeholder_text = _prompt()


func _gaze(think: float) -> void:
	# VRM bone lookAt: eyes turn toward the target by up to 10 degrees (the model's range map: 90 in -> 10 out).
	var head := skel.global_transform * skel.get_bone_global_pose(skel.find_bone("J_Bip_C_Head"))
	var target := cam.global_position.lerp(head.origin + head.basis * Vector3(0.6, 0.5, 1.0), think).lerp(look_at_prop, look_w)
	var local := (head.basis.inverse() * (target - head.origin)).normalized()
	var yaw := clampf(rad_to_deg(atan2(local.x, local.z)) / 9.0, -10.0, 10.0)
	var pitch := clampf(rad_to_deg(asin(local.y)) / 9.0, -10.0, 10.0)
	for e in eye_rest:
		var i := skel.find_bone(e)
		skel.set_bone_pose_rotation(i, eye_rest[e] * Quaternion(Vector3.UP, deg_to_rad(yaw)) * Quaternion(Vector3.RIGHT, deg_to_rad(-pitch)))


func _strip_tags(s: String) -> String:
	var r := RegEx.new(); r.compile("\\[[^\\]]*\\]?"); return r.sub(s, "", true).strip_edges()


func _prompt() -> String: return "Say something to %s, then press Enter" % cfg.name


func _v(a: Array) -> Vector3: return Vector3(a[0], a[1], a[2])


func _quit() -> void:
	if movie:
		var f := FileAccess.open(log_path.get_basename() + "-mouth.csv", FileAccess.WRITE); f.store_string("\n".join(mouth_log) + "\n"); f.close()
	get_tree().quit()


func talking_now() -> bool: return not speaking.is_empty() and player.playing
