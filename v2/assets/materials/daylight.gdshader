shader_type sky;
uniform float daylight=1.0;
uniform float overcast=0.0;
uniform vec2 cloud_shift=vec2(0);
uniform vec3 zenith : source_color=vec3(.24,.43,.65);
uniform vec3 horizon : source_color=vec3(.70,.78,.78);
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1)),f.x),f.y);}
float fbm(vec2 p){float v=0.0;float a=.5;for(int i=0;i<5;i++){v+=noise(p)*a;p=mat2(vec2(.8,.6),vec2(-.6,.8))*p*2.05;a*=.5;}return v;}
void sky(){
 float y=max(0.0,EYEDIR.y);
 vec3 sky_color=mix(horizon,zenith,pow(y,.4));
 float cloud=fbm(EYEDIR.xz/max(.15,EYEDIR.y+.15)*2.6+vec2(2.1,-3.8)+cloud_shift);
 float cover=smoothstep(.51,.73,cloud)*smoothstep(.02,.24,y);
 sky_color=mix(sky_color,vec3(.72,.76,.78),max(cover*.75,overcast*.78));
 sky_color=mix(vec3(.004,.010,.026),sky_color,daylight);
 vec2 star_uv=EYEDIR.xz/max(.05,y+.12)*280.0;
 float star=step(.996,hash(floor(star_uv)))*(1.0-smoothstep(.05,.23,length(fract(star_uv)-.5)));
 sky_color+=vec3(.58,.68,.90)*star*(1.0-daylight)*smoothstep(.02,.2,y)*(1.0-overcast);
 float moon=max(dot(EYEDIR,normalize(vec3(-.4,.6,-.65))),0.0);
 sky_color+=vec3(.65,.75,.95)*smoothstep(.9991,.9997,moon)*(1.0-daylight)*(1.0-overcast*.6);
 if(LIGHT0_ENABLED){
  float sun=max(dot(EYEDIR,LIGHT0_DIRECTION),0.0);
  sky_color+=vec3(1.0,.77,.44)*pow(sun,14.0)*.18*daylight*(1.0-overcast);
  sky_color+=vec3(1.8,1.55,1.13)*smoothstep(.9995,.99985,sun)*daylight*(1.0-overcast);
 }
 COLOR=EYEDIR.y<0.0?mix(vec3(.012,.024,.025),horizon*max(.02,daylight),exp(EYEDIR.y*7.0)):sky_color;
}
