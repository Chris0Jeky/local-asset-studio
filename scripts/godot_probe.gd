extends Node
# Authored verifier only. Asset names are data; imported scripts are never copied.
const GLB_PATH := "__GLB_PATH__"
const FIXED_FPS := 240
var result: Dictionary = {}
var elapsed: float = 0.0
var observing: bool = false
var began_usec: int = 0
var frame_events: Array = []

func alpha_region(image: Image, region: Rect2i) -> Dictionary:
	var min_x: int = region.size.x
	var min_y: int = region.size.y
	var max_x: int = -1
	var max_y: int = -1
	var alpha_pixels: int = 0
	for y in range(region.size.y):
		for x in range(region.size.x):
			if image.get_pixel(region.position.x + x, region.position.y + y).a > 0.0:
				alpha_pixels += 1
				min_x = mini(min_x, x)
				min_y = mini(min_y, y)
				max_x = maxi(max_x, x)
				max_y = maxi(max_y, y)
	if max_x < 0:
		return {"alpha_pixels": 0, "bounds": []}
	return {"alpha_pixels": alpha_pixels, "bounds": [min_x, min_y, max_x + 1, max_y + 1]}

func walk(root: Node) -> Array[Node]:
	var all: Array[Node] = []
	var pending: Array[Node] = [root]
	while not pending.is_empty():
		var item: Node = pending.pop_back()
		all.append(item)
		for child in item.get_children():
			pending.append(child)
	return all

func vector(value: Vector3) -> Array:
	return [value.x, value.y, value.z]

func pose(nodes: Array[Node], root: Node) -> Array:
	var values: Array = []
	for item in nodes:
		if item is Node3D:
			var spatial: Node3D = item as Node3D
			var q: Quaternion = spatial.quaternion
			values.append({"path": str(root.get_path_to(item)), "name": str(item.name),
				"position": vector(spatial.position), "rotation_quaternion": [q.x, q.y, q.z, q.w],
				"scale": vector(spatial.scale), "global_position": vector(spatial.global_position)})
	return values

func inventory_glb() -> Dictionary:
	var inventory: Dictionary = {"requested": GLB_PATH, "loaded": false, "nodes": [], "meshes": [],
		"materials": [], "skins": [], "skeletons": [], "animations": [], "animation_samples": [],
		"collision_acceptance": "not_assessed", "root_motion_acceptance": "not_assessed"}
	if GLB_PATH.is_empty():
		inventory["not_requested"] = true
		return inventory
	var packed: Resource = load(GLB_PATH)
	if not (packed is PackedScene):
		inventory["load_error"] = "Godot did not load GLB as PackedScene"
		return inventory
	var root: Node = (packed as PackedScene).instantiate()
	add_child(root)
	var nodes: Array[Node] = walk(root)
	if nodes.size() > 4096:
		inventory["load_error"] = "Imported node budget exceeded"
		root.queue_free()
		return inventory
	inventory["loaded"] = true
	inventory["node_count"] = nodes.size()
	inventory["rest_transforms"] = pose(nodes, root)
	var seen_materials: Dictionary = {}
	for item in nodes:
		inventory["nodes"].append({"path": str(root.get_path_to(item)), "name": str(item.name), "class": item.get_class()})
		if item is MeshInstance3D:
			var mesh_item: MeshInstance3D = item as MeshInstance3D
			var surfaces: int = 0
			if mesh_item.mesh:
				surfaces = mesh_item.mesh.get_surface_count()
				for index in range(surfaces):
					var material: Material = mesh_item.get_active_material(index)
					if material and not seen_materials.has(material.get_instance_id()):
						seen_materials[material.get_instance_id()] = true
						var detail: Dictionary = {"name": material.resource_name, "class": material.get_class()}
						if material is BaseMaterial3D:
							var pbr: BaseMaterial3D = material as BaseMaterial3D
							detail.merge({"metallic": pbr.metallic, "roughness": pbr.roughness,
								"albedo": [pbr.albedo_color.r, pbr.albedo_color.g, pbr.albedo_color.b, pbr.albedo_color.a],
								"albedo_texture": pbr.albedo_texture != null, "normal_enabled": pbr.normal_enabled,
								"normal_texture": pbr.normal_texture != null, "metallic_texture": pbr.metallic_texture != null,
								"roughness_texture": pbr.roughness_texture != null, "ao_enabled": pbr.ao_enabled})
						inventory["materials"].append(detail)
			inventory["meshes"].append({"name": str(item.name), "surfaces": surfaces,
				"skeleton_path": str(mesh_item.skeleton)})
			if mesh_item.skin:
				var bindings: Array = []
				for index in range(mesh_item.skin.get_bind_count()):
					bindings.append({"bone": mesh_item.skin.get_bind_bone(index), "name": str(mesh_item.skin.get_bind_name(index))})
				inventory["skins"].append({"name": mesh_item.skin.resource_name, "mesh": str(item.name), "binds": bindings})
		if item is Skeleton3D:
			var skeleton: Skeleton3D = item as Skeleton3D
			var bones: Array = []
			for index in range(skeleton.get_bone_count()):
				bones.append({"name": skeleton.get_bone_name(index), "parent": skeleton.get_bone_parent(index)})
			inventory["skeletons"].append({"name": str(item.name), "bones": bones})
		if item is AnimationPlayer:
			var player: AnimationPlayer = item as AnimationPlayer
			player.active = true
			for clip_name in player.get_animation_list():
				inventory["animations"].append(str(clip_name))
				if clip_name == "RESET":
					continue
				var animation: Animation = player.get_animation(clip_name)
				var tracks: Array = []
				for track in range(animation.get_track_count()):
					tracks.append({"path": str(animation.track_get_path(track)), "type": animation.track_get_type(track)})
				var samples: Array = []
				player.play(clip_name)
				player.advance(0.0)
				for fraction in [0.0, 0.5, 1.0]:
					var at: float = animation.length * fraction
					player.seek(at, true)
					samples.append({"time": at, "transforms": pose(nodes, root)})
				player.stop()
				inventory["animation_samples"].append({"name": str(clip_name), "length": animation.length,
					"tracks": tracks, "samples": samples, "method": "AnimationPlayer.seek(update=true)"})
	root.queue_free()
	return inventory

func _ready() -> void:
	process_priority = -1000
	var sprite: AnimatedSprite2D = $SpritePlayback
	sprite.stop()
	var frames: SpriteFrames = sprite.sprite_frames
	var clip: StringName = sprite.animation
	var speed: float = frames.get_animation_speed(clip)
	var texture: Texture2D = load("res://assets/atlas.png") as Texture2D
	var image: Image = texture.get_image()
	var anchor: Vector2 = get_meta("asset_anchor")
	var canvas: Vector2 = get_meta("logical_canvas")
	result = {"report_kind": "godot_headless_import_playback", "schema_version": 2,
		"engine": Engine.get_version_info(), "sprite": {"animation": str(clip),
		"frame_count": frames.get_frame_count(clip), "loop": frames.get_animation_loop(clip),
		"speed_fps": speed, "anchor": [anchor.x, anchor.y], "logical_canvas": [canvas.x, canvas.y],
		"filter": get_meta("atlas_filter"), "texture_filter": sprite.texture_filter,
		"anchor_world_error": [sprite.offset.x + anchor.x - canvas.x / 2.0, sprite.offset.y + anchor.y - canvas.y / 2.0],
		"frames": [], "total_duration_ms": 0.0}, "glb": inventory_glb()}
	for index in range(frames.get_frame_count(clip)):
		var atlas: AtlasTexture = frames.get_frame_texture(clip, index) as AtlasTexture
		var region: Rect2i = Rect2i(atlas.region)
		var relative: float = frames.get_frame_duration(clip, index)
		var duration: float = relative / speed * 1000.0
		result["sprite"]["total_duration_ms"] += duration
		result["sprite"]["frames"].append({"index": index,
			"region": [region.position.x, region.position.y, region.size.x, region.size.y],
			"relative_duration": relative, "duration_ms": duration, "alpha": alpha_region(image, region)})
	sprite.frame_changed.connect(_frame_changed)
	sprite.animation_looped.connect(_completed.bind("animation_looped"))
	sprite.animation_finished.connect(_completed.bind("animation_finished"))
	frame_events = [{"frame": 0, "elapsed_ms": 0.0}]
	elapsed = 0.0
	began_usec = Time.get_ticks_usec()
	observing = true
	sprite.speed_scale = 1.0
	sprite.play(clip, 1.0)

func _process(delta: float) -> void:
	if observing:
		elapsed += delta
		if elapsed > 31.0:
			_completed("timeout")

func _frame_changed() -> void:
	if observing:
		var sprite: AnimatedSprite2D = $SpritePlayback
		if frame_events[-1]["frame"] != sprite.frame:
			frame_events.append({"frame": sprite.frame, "elapsed_ms": elapsed * 1000.0})

func _completed(signal_name: String) -> void:
	if not observing:
		return
	observing = false
	var sprite: AnimatedSprite2D = $SpritePlayback
	result["playback"] = {"completed": signal_name != "timeout", "signal": signal_name,
		"timebase": "process-delta", "fixed_fps": FIXED_FPS, "elapsed_ms": elapsed * 1000.0,
		"wall_ms": (Time.get_ticks_usec() - began_usec) / 1000.0,
		"speed_scale": sprite.speed_scale, "frame_events": frame_events}
	sprite.pause()
	_finish.call_deferred()

func _finish() -> void:
	print("GODOT_ADAPTER_REPORT=" + JSON.stringify(result))
	get_tree().quit(0)
