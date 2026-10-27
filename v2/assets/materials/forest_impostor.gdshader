shader_type spatial;
global uniform float eco_time;
global uniform float eco_wind;
global uniform vec4 eco_tint;
global uniform float eco_snow;
global uniform float eco_daylight;
render_mode unshaded, cull_disabled;
uniform sampler2D tree_image : source_color, filter_linear_mipmap_anisotropic;
uniform float canvas_height=1.0;
varying vec3 tint;
void vertex(){
 vec3 right=normalize(vec3(INV_VIEW_MATRIX[0].x,0.0,INV_VIEW_MATRIX[0].z));
 vec3 up=vec3(0,1,0);
 float sx=length(MODEL_MATRIX[0].xyz),sy=length(MODEL_MATRIX[1].xyz);
 vec3 world=MODEL_MATRIX[3].xyz+right*VERTEX.x*sx+up*VERTEX.y*sy;
 world.x+=sin(eco_time*1.1+world.z*.3)*pow(1.0-UV.y,2.0)*.045*eco_wind;
 POSITION=PROJECTION_MATRIX*VIEW_MATRIX*vec4(world,1.0);
 tint=COLOR.rgb;
}
void fragment(){
 vec4 tree=texture(tree_image,UV);
 if(tree.a<.38){discard;}
 ALBEDO=mix(tree.rgb*tint*eco_tint.rgb*1.2,vec3(.62,.70,.73),eco_snow*.25)*(.18+.82*eco_daylight);
}
