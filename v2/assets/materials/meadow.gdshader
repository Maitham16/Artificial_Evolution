shader_type spatial;
render_mode diffuse_burley;
uniform sampler2D grass_color : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D earth_color : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D stone_color : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D stone_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 meadow_tint : source_color = vec4(.58,.82,.61,1.0);
varying vec3 world_pos;
varying vec3 world_normal;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1)),f.x),f.y);}
void vertex(){world_pos=(MODEL_MATRIX*vec4(VERTEX,1.0)).xyz;world_normal=normalize(MODEL_NORMAL_MATRIX*NORMAL);}
void fragment(){
 vec2 p=world_pos.xz;
 vec3 grass=texture(grass_color,p*.16).rgb;
 vec3 fine=texture(grass_color,p*.69+vec2(.34,.61)).rgb;
 float patches=noise(p*.045)*.65+noise(p*.13)*.35;
 vec3 soil=texture(earth_color,p*.24).rgb;
 float mountain=smoothstep(7.0,32.0,world_pos.y);
 float steep=smoothstep(.24,.66,1.0-world_normal.y);
 float rocky=max(steep,mountain*.85);
 vec3 rock=texture(stone_color,p*.085+world_pos.yy*.04).rgb;
 vec3 ground=mix(grass,fine,.22)*meadow_tint.rgb;
 ground=mix(ground,soil,smoothstep(.62,.90,patches)*.45);
 ground*=.86+.26*noise(p*.027);
 ALBEDO=mix(ground,rock,rocky);
 vec3 normal_a=texture(grass_normal,p*.42).rgb;
 vec3 normal_b=texture(stone_normal,p*.10).rgb;
 NORMAL_MAP=mix(normal_a,normal_b,rocky);
 NORMAL_MAP_DEPTH=mix(.25,.65,rocky);
 ROUGHNESS=.94;
 SPECULAR=.12;
}
