shader_type spatial;
render_mode diffuse_burley;
uniform sampler2D coat_texture : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D coat_normal : hint_normal, filter_linear_mipmap_anisotropic;
uniform bool has_texture=true;
uniform bool has_normal=false;
uniform vec4 base_color : source_color=vec4(1.0);
uniform vec4 coat_tint : source_color=vec4(1.0);
uniform float desaturation=0.0;
uniform float surface_roughness=.86;
uniform float opacity=1.0;
uniform bool gpu_skeleton=true;
uniform sampler2D bone_palette : filter_nearest, repeat_disable;
uniform vec2 palette_size=vec2(128,296);
uniform float upper_weights[64];
uniform vec3 base_frames=vec3(0);
uniform vec3 previous_frames=vec3(0);
uniform vec3 upper_frames=vec3(0);
uniform float transition=1.0;
uniform float upper_blend=0.0;
mat4 bone_at(uint bone,float frame){
 float x=float(bone)*3.0;
 vec4 a=texture(bone_palette,vec2((x+.5)/palette_size.x,(frame+.5)/palette_size.y));
 vec4 b=texture(bone_palette,vec2((x+1.5)/palette_size.x,(frame+.5)/palette_size.y));
 vec4 c=texture(bone_palette,vec2((x+2.5)/palette_size.x,(frame+.5)/palette_size.y));
 return mat4(vec4(a.x,b.x,c.x,0),vec4(a.y,b.y,c.y,0),vec4(a.z,b.z,c.z,0),vec4(a.w,b.w,c.w,1));
}
mat4 sampled(uint bone,vec3 frames){return bone_at(bone,frames.x)*(1.0-frames.z)+bone_at(bone,frames.y)*frames.z;}
void vertex(){
 if(gpu_skeleton){
  mat4 skin=mat4(0.0);
  for(int i=0;i<4;i++){
   float weight=BONE_WEIGHTS[i];
   if(weight>.0001){
    uint bone=BONE_INDICES[i];
    mat4 pose=sampled(bone,base_frames);
    if(transition<.999){pose=sampled(bone,previous_frames)*(1.0-transition)+pose*transition;}
    float amount=upper_blend*upper_weights[int(bone)];
    if(amount>.001){pose=pose*(1.0-amount)+sampled(bone,upper_frames)*amount;}
    skin+=pose*weight;
   }
  }
  VERTEX=(skin*vec4(VERTEX,1)).xyz;
  NORMAL=normalize(mat3(skin)*NORMAL);
  TANGENT=normalize(mat3(skin)*TANGENT);BINORMAL=normalize(mat3(skin)*BINORMAL);
 }
}
void fragment(){
 if(opacity<1.0 && fract(sin(dot(FRAGCOORD.xy,vec2(12.9898,78.233)))*43758.5453)>opacity){discard;}
 vec3 coat=base_color.rgb;
 if(has_texture){coat*=texture(coat_texture,UV).rgb;}
 float luminance=dot(coat,vec3(.2126,.7152,.0722));
 ALBEDO=mix(coat,vec3(luminance),desaturation)*coat_tint.rgb;
 if(has_normal){NORMAL_MAP=texture(coat_normal,UV).rgb;NORMAL_MAP_DEPTH=.45;}
 ROUGHNESS=surface_roughness;SPECULAR=.24;BACKLIGHT=ALBEDO*.07;
}
