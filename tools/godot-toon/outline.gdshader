// Inverted hull: grow along the normal, draw back faces only, respect the albedo's alpha cut.
shader_type spatial;
render_mode unshaded, cull_front;
uniform float width = 0.0018;
uniform vec4 color : source_color = vec4(0.07, 0.05, 0.09, 1.0);
uniform sampler2D albedo_tex : source_color, hint_default_white;
void vertex() { VERTEX += NORMAL * width; }
void fragment() { ALBEDO = color.rgb; ALPHA = texture(albedo_tex, UV).a; ALPHA_SCISSOR_THRESHOLD = 0.5; }
