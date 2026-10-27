shader_type spatial;
global uniform float eco_time;
global uniform float eco_wind;
global uniform vec4 eco_tint;
global uniform float eco_snow;
global uniform float eco_daylight;
render_mode cull_disabled, depth_prepass_alpha, diffuse_burley;
uniform vec4 deep_color : source_color=vec4(.025,.16,.14,1);
uniform vec4 shallow_color : source_color=vec4(.13,.32,.25,1);
varying vec3 world_pos;
void vertex(){
 world_pos=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
 VERTEX.y+=sin(world_pos.x*1.7+world_pos.z*.6+eco_time*1.3)*.008+sin(world_pos.z*2.9-eco_time*.7)*.004;
}
void fragment(){
 float a=sin(world_pos.x*11.2+world_pos.z*7.7+eco_time*1.3);
 float b=cos(world_pos.z*17.8-world_pos.x*3.3-eco_time*.86);
 NORMAL_MAP=normalize(vec3(a*.035,b*.025,1.0))*.5+.5;
 NORMAL_MAP_DEPTH=.35;
 float fresnel=pow(1.0-clamp(dot(normalize(NORMAL),normalize(VIEW)),0.0,1.0),4.0);
 ALBEDO=mix(deep_color.rgb,shallow_color.rgb,.18)+vec3(.08,.12,.13)*fresnel;
 ROUGHNESS=.18;SPECULAR=.9;METALLIC=.12;
 ALPHA=.93;
}
