shader_type spatial;
render_mode unshaded, cull_disabled;
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap;
void fragment() { vec4 c = texture(albedo_tex, UV); ALBEDO = c.rgb; ALPHA = c.a; ALPHA_SCISSOR_THRESHOLD = 0.5; }
