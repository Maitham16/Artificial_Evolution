shader_type spatial;
render_mode unshaded,cull_disabled,depth_draw_never;
void fragment(){
 float r=length(UV-vec2(0.5))*2.0;
 float edge=smoothstep(0.94,0.98,r)*(1.0-smoothstep(0.98,1.0,r));
 float body=1.0-smoothstep(0.95,1.0,r);
 ALBEDO=vec3(0.95,0.32,0.31);
 ALPHA=body*0.12+edge*(0.7+sin(TIME*2.0)*0.15);
}
