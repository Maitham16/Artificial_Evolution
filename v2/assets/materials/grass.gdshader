shader_type spatial;
render_mode cull_disabled, diffuse_burley;
uniform float wind_strength=.20;
uniform float fade_end=55.0;
varying vec3 world_pos;
varying vec3 blade_color;
void vertex(){
 vec3 wp=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
 float phase=INSTANCE_CUSTOM.x*6.283;
 float wave=sin(wp.x*.42+wp.z*.29+TIME*1.4+phase)+.35*sin(wp.z*1.6-TIME*2.2);
 float fade=1.0-smoothstep(28.0,fade_end,distance(CAMERA_POSITION_WORLD,wp));
 VERTEX.y*=fade;
 VERTEX.x+=wave*UV.y*UV.y*wind_strength;
 VERTEX.z+=cos(wp.x*.65+TIME*1.1+phase)*UV.y*UV.y*wind_strength*.45;
 world_pos=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;
 blade_color=COLOR.rgb;
}
void fragment(){
 vec3 green=mix(vec3(.07,.13,.025),vec3(.28,.40,.09),sqrt(UV.y));
 ALBEDO=green*blade_color;
 ROUGHNESS=.94;SPECULAR=.16;
 BACKLIGHT=vec3(.16,.23,.035)*.55;
}
