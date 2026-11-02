// Cel toon with a custom light(): ramp per light (shadowed), lit-side rim, step specular for hair, SDF face shadow.
// Final colour = albedo * shade_tint (emission) + albedo * lit * (1 - shade_tint): exactly albedo where fully lit.
shader_type spatial;
render_mode diffuse_lambert, specular_disabled, cull_disabled;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap, repeat_enable;
uniform vec3 shade_tint = vec3(0.62, 0.62, 0.78);
uniform float threshold = 0.18;
uniform float softness = 0.03;
uniform float rim_amount = 0.35;
uniform float spec_amount = 0.0;
uniform bool face_sdf = false;
uniform sampler2D sdf_tex : hint_default_white, filter_linear;
uniform vec3 face_forward = vec3(0.0, 0.0, 1.0);
uniform vec3 face_left = vec3(1.0, 0.0, 0.0);

void fragment() {
	vec4 c = texture(albedo_tex, UV);
	ALBEDO = c.rgb;
	ALPHA = c.a;
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	EMISSION = c.rgb * shade_tint;
}

void light() {
	float lit;
	if (face_sdf) {
		vec3 lw = (INV_VIEW_MATRIX * vec4(LIGHT, 0.0)).xyz;
		float lx = dot(lw, face_left);
		float lz = dot(lw, face_forward);
		float ang = acos(clamp(lz / max(length(vec2(lx, lz)), 1e-4), -1.0, 1.0)) / PI;
		vec4 s = texture(sdf_tex, UV);
		float facing = smoothstep(0.0, 0.02, dot(NORMAL, LIGHT));   // no light through the back of the head
		lit = smoothstep(-softness, softness, (lx > 0.0 ? s.r : s.g) - ang) * facing * mix(0.5, 1.0, ATTENUATION);
	} else {
		lit = smoothstep(threshold - softness, threshold + softness, dot(NORMAL, LIGHT) * ATTENUATION);
	}
	float rim = smoothstep(0.62, 0.70, 1.0 - abs(dot(NORMAL, VIEW))) * rim_amount;
	vec3 lc = LIGHT_COLOR / PI;
	DIFFUSE_LIGHT += lc * lit * ((vec3(1.0) - shade_tint) + rim);
	if (spec_amount > 0.0) {
		SPECULAR_LIGHT += lc * smoothstep(0.93, 0.95, dot(NORMAL, normalize(LIGHT + VIEW))) * lit * spec_amount;
	}
}
