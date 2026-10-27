shader_type spatial;
render_mode unshaded, cull_disabled;
uniform sampler2D tree_image : source_color, filter_linear_mipmap_anisotropic;
uniform float canvas_height=1.0;
varying vec3 tint;
void vertex(){
 vec3 right=normalize(vec3(INV_VIEW_MATRIX[0].x,0.0,INV_VIEW_MATRIX[0].z));
 vec3 up=vec3(0,1,0);
 float sx=length(MODEL_MATRIX[0].xyz),sy=length(MODEL_MATRIX[1].xyz);
 vec3 world=MODEL_MATRIX[3].xyz+right*VERTEX.x*sx+up*VERTEX.y*sy;
 world.x+=sin(TIME*1.1+world.z*.3)*pow(1.0-UV.y,2.0)*.045;
 POSITION=PROJECTION_MATRIX*VIEW_MATRIX*vec4(world,1.0);
 tint=COLOR.rgb;
}
void fragment(){
 vec4 tree=texture(tree_image,UV);
 if(tree.a<.38){discard;}
 ALBEDO=tree.rgb*tint*1.2;
}
