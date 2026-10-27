shader_type sky;
uniform vec3 zenith : source_color=vec3(.24,.43,.65);
uniform vec3 horizon : source_color=vec3(.70,.78,.78);
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1)),f.x),f.y);}
float fbm(vec2 p){float v=0.0;float a=.5;for(int i=0;i<5;i++){v+=noise(p)*a;p=mat2(vec2(.8,.6),vec2(-.6,.8))*p*2.05;a*=.5;}return v;}
void sky(){
 float y=max(0.0,EYEDIR.y);
 vec3 sky_color=mix(horizon,zenith,pow(y,.4));
 float cloud=fbm(EYEDIR.xz/max(.15,EYEDIR.y+.15)*2.6+vec2(2.1,-3.8));
 float cover=smoothstep(.51,.73,cloud)*smoothstep(.02,.24,y);
 sky_color=mix(sky_color,vec3(.89,.91,.88),cover*.75);
 if(LIGHT0_ENABLED){
  float sun=max(dot(EYEDIR,LIGHT0_DIRECTION),0.0);
  sky_color+=vec3(1.0,.77,.44)*pow(sun,14.0)*.18;
  sky_color+=vec3(1.8,1.55,1.13)*smoothstep(.9995,.99985,sun);
 }
 COLOR=EYEDIR.y<0.0?mix(vec3(.12,.19,.12),horizon,exp(EYEDIR.y*7.0)):sky_color;
}
