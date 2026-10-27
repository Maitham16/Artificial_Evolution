shader_type spatial;
render_mode cull_disabled, diffuse_burley;
uniform sampler2D color_texture : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap;
uniform vec4 base_color : source_color=vec4(1.0);
uniform bool has_normal=false;
uniform float wind_strength=.12;
uniform float crown_height=8.0;
uniform float fade_end=180.0;
varying vec3 world_pos;
varying vec4 variation;
void vertex(){
 vec3 wp=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
 float weight=pow(clamp(VERTEX.y/max(.1,crown_height),0.0,1.0),1.5);
 float breeze=sin(wp.x*.13+wp.z*.10+TIME*.85)+.35*sin(wp.z*.53-TIME*1.7);
 VERTEX.x+=breeze*weight*wind_strength;
 VERTEX.z+=sin(wp.x*.24+TIME*1.15)*weight*wind_strength*.5;
 world_pos=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
 variation=COLOR;
}
void fragment(){
 vec4 color=texture(color_texture,UV)*base_color;
 if(color.a<.42){discard;}
 float fade=1.0-smoothstep(fade_end*.80,fade_end,distance(CAMERA_POSITION_WORLD,world_pos));
 float dither=fract(sin(dot(FRAGCOORD.xy,vec2(12.9898,78.233)))*43758.5453);
 if(dither>fade){discard;}
 ALBEDO=color.rgb*mix(vec3(1),variation.rgb,.6);
 if(has_normal){NORMAL_MAP=texture(normal_texture,UV).rgb;NORMAL_MAP_DEPTH=.6;}
 ROUGHNESS=.87;
 SPECULAR=.16;
 BACKLIGHT=color.rgb*.14;
}
