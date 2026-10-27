shader_type spatial;
render_mode diffuse_burley;
uniform vec4 soil_color : source_color = vec4(0.19,0.28,0.23,1.0);
varying vec3 world_position;
void vertex(){ world_position=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz; }
void fragment(){
 vec2 p=world_position.xz;
 float grain=fract(sin(dot(floor(p*12.0),vec2(12.9898,78.233)))*43758.5453);
 vec2 grid=abs(fract(p/2.0-0.5)-0.5)/max(fwidth(p/2.0),vec2(0.001));
 float line=1.0-min(min(grid.x,grid.y),1.0);
 ALBEDO=soil_color.rgb*(0.97+grain*0.04)+vec3(0.09,0.12,0.09)*line*0.25;
 ROUGHNESS=0.95;
}
