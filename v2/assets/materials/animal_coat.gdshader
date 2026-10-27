shader_type spatial;
render_mode diffuse_burley;
uniform sampler2D coat_texture : source_color, filter_linear_mipmap_anisotropic;
uniform sampler2D coat_normal : hint_normal, filter_linear_mipmap_anisotropic;
uniform sampler2D gait_positions : filter_nearest, repeat_disable;
uniform sampler2D gait_normals : filter_nearest, repeat_disable;
uniform vec3 position_min;
uniform vec3 position_span;
uniform float frame_uv_step;
uniform vec3 pose_frames=vec3(0,0,0);
uniform bool has_texture=true;
uniform bool has_normal=false;
uniform vec4 base_color : source_color=vec4(1.0);
uniform vec4 coat_tint : source_color=vec4(1.0);
uniform float desaturation=0.0;
uniform float surface_roughness=.86;
void vertex(){
 vec2 a=UV2-vec2(0.0,pose_frames.x*frame_uv_step);
 vec2 b=UV2-vec2(0.0,pose_frames.y*frame_uv_step);
 VERTEX=position_min+mix(texture(gait_positions,a).rgb,texture(gait_positions,b).rgb,pose_frames.z)*position_span;
 NORMAL=normalize(mix(texture(gait_normals,a).rgb,texture(gait_normals,b).rgb,pose_frames.z)*2.0-1.0);
}
void fragment(){
 vec3 coat=base_color.rgb;
 if(has_texture){coat*=texture(coat_texture,UV).rgb;}
 float luminance=dot(coat,vec3(.2126,.7152,.0722));
 ALBEDO=mix(coat,vec3(luminance),desaturation)*coat_tint.rgb;
 if(has_normal){NORMAL_MAP=texture(coat_normal,UV).rgb;NORMAL_MAP_DEPTH=.45;}
 ROUGHNESS=surface_roughness;
 SPECULAR=.24;
 BACKLIGHT=ALBEDO*.07;
}
