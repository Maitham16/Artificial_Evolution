extends Node3D
## Decorative clock/weather. Has no Python control or model mutation capability.
const WEATHER=["auto","clear","cloudy","rain","fog","snow"]
const SEASONS=["auto","spring","summer","autumn","winter"]
var nature
var camera: Camera3D
var hour=10.5
var day_length=240.0
var cycle_enabled=true
var motion_enabled=true
var weather_choice="auto"
var season_choice="auto"
var visual_seconds=0.0
var weather_seconds=0.0
var source_context={}
var season="summer"
var season_source="decorative"
var weather="clear"
var daylight=1.0
var rain=0.0
var snow=0.0
var wetness=0.0
var cloud=0.0
var snow_cover=0.0
var wind=1.0
var lighting_clock=1.0
var rain_particles: CPUParticles3D
var snow_particles: CPUParticles3D
var motes: CPUParticles3D
var moon: DirectionalLight3D
var last_quality=-1

func bind(landscape,view_camera: Camera3D) -> void:
	nature=landscape;camera=view_camera
	moon=DirectionalLight3D.new();moon.name="DecorativeMoonlight";moon.light_color=Color("9bb5e5");moon.shadow_enabled=false;add_child(moon)
	rain_particles=_particles("DecorativeRain",650,Vector2(.012,.35),Color(.65,.79,.86,.4),Vector3(1,-20,.4),.95)
	snow_particles=_particles("DecorativeSnow",320,Vector2(.045,.045),Color(.85,.91,.96,.8),Vector3(.3,-1.6,.1),4.0)
	motes=_particles("DecorativePollen",100,Vector2(.018,.018),Color(.80,.78,.52,.42),Vector3(.02,.03,.01),5.0)
	nature.environment.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
	nature.environment.sky.process_mode=Sky.PROCESS_MODE_INCREMENTAL
	nature.environment.sky.radiance_size=Sky.RADIANCE_SIZE_64
	step(0,true)

func _particles(title: String,count: int,size: Vector2,color: Color,gravity: Vector3,lifetime: float) -> CPUParticles3D:
	var p=CPUParticles3D.new();p.name=title;p.amount=count;p.lifetime=lifetime;p.preprocess=lifetime*.5;p.fixed_fps=30
	p.emission_shape=CPUParticles3D.EMISSION_SHAPE_BOX;p.emission_box_extents=Vector3(18,5,18);p.direction=Vector3.DOWN;p.spread=12;p.gravity=gravity
	p.initial_velocity_min=.3;p.initial_velocity_max=1.0;p.scale_amount_min=.7;p.scale_amount_max=1.4;p.local_coords=false
	var mesh=QuadMesh.new();mesh.size=size;p.mesh=mesh
	var material=StandardMaterial3D.new();material.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED;material.transparency=BaseMaterial3D.TRANSPARENCY_ALPHA;material.albedo_color=color;material.billboard_mode=BaseMaterial3D.BILLBOARD_ENABLED
	material.cull_mode=BaseMaterial3D.CULL_DISABLED;mesh.material=material;p.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF;p.emitting=false;add_child(p)
	return p

func set_source(context: Dictionary) -> void:source_context=context.duplicate(true)

func choose_weather(value: String) -> void:
	if value in WEATHER:weather_choice=value;lighting_clock=1.0
func choose_season(value: String) -> void:
	if value in SEASONS:season_choice=value;lighting_clock=1.0
func set_hour(value: float) -> void:hour=fposmod(value,24);lighting_clock=1.0

func step(delta: float,immediate: bool=false) -> void:
	if nature==null:return
	if motion_enabled:
		visual_seconds+=delta;weather_seconds+=delta
		if cycle_enabled:hour=fposmod(hour+delta*24/day_length,24)
	var physical=source_context.get("physical_climate",{})
	if not physical.is_empty() and cycle_enabled:hour=float(physical.hour)
	var source_season=source_context.get("season")
	season=str(source_season.season) if season_choice=="auto" and source_season is Dictionary else "summer" if season_choice=="auto" else season_choice
	season_source="Python" if season_choice=="auto" and source_season is Dictionary else "decorative"
	if season_choice=="auto" and not physical.is_empty():season=str(physical.season);season_source="Python habitat"
	weather=weather_choice
	if weather=="auto":
		var pattern=["clear","cloudy","snow" if season=="winter" else "rain","fog","clear"]
		weather=str(physical.weather) if not physical.is_empty() else pattern[int(weather_seconds/55.0)%pattern.size()]
	var weight=1.0 if immediate else 1-exp(-delta*.8)
	rain=lerpf(rain,1.0 if weather=="rain" else 0.0,weight)
	snow=lerpf(snow,1.0 if weather=="snow" else 0.0,weight)
	wetness=lerpf(wetness,rain,weight*.5 if not immediate else 1.0)
	cloud=lerpf(cloud,1.0 if weather in ["rain","snow"] else .65 if weather=="cloudy" else .3 if weather=="fog" else .05,weight)
	snow_cover=lerpf(snow_cover,.72 if season=="winter" else .35 if weather=="snow" else 0.0,weight)
	wind=1.0+rain*.9+sin(visual_seconds*.21)*.22
	var solar=sin((hour-6)/24*TAU);daylight=smoothstep(-.12,.25,solar)
	RenderingServer.global_shader_parameter_set("eco_time",visual_seconds)
	RenderingServer.global_shader_parameter_set("eco_wind",wind)
	RenderingServer.global_shader_parameter_set("eco_wetness",wetness)
	RenderingServer.global_shader_parameter_set("eco_snow",snow_cover)
	RenderingServer.global_shader_parameter_set("eco_daylight",daylight)
	var tint={"spring":Color(1.02,1.07,.90),"summer":Color.WHITE,"autumn":Color(1.25,.82,.47),"winter":Color(.85,.92,.93)}[season]
	RenderingServer.global_shader_parameter_set("eco_tint",tint)
	if last_quality!=nature.quality:
		last_quality=nature.quality;rain_particles.amount=[280,650,1000][last_quality];snow_particles.amount=[140,320,500][last_quality];motes.amount=[40,90,140][last_quality]
	var forward=-camera.global_basis.z;var anchor=camera.global_position+forward*7
	rain_particles.global_position=anchor+Vector3(0,6,0);snow_particles.global_position=anchor+Vector3(0,4,0)
	motes.global_position=Vector3(anchor.x,nature.height_at(Vector2(anchor.x,anchor.z))+1.4,anchor.z)
	motes.emission_box_extents=Vector3(12,1.0,12)
	for pair in [[rain_particles,rain],[snow_particles,snow],[motes,(1-cloud)*(1-snow_cover)*.6]]:
		pair[0].emitting=float(pair[1])>.02;pair[0].speed_scale=1.0 if motion_enabled else 0.0
		var material=pair[0].mesh.material;var color=material.albedo_color;color.a=float(pair[1])*.55;material.albedo_color=color
	lighting_clock+=delta
	if lighting_clock<.2 and not immediate:return
	lighting_clock=0
	nature.sun.rotation_degrees=Vector3(-solar*(48 if season=="winter" else 62),-32+(hour-10.5)*8,0)
	nature.sun.light_energy=(.08+daylight*.95)*(1-cloud*.6);nature.sun.shadow_enabled=daylight>.12
	nature.sun.light_color=Color("ffcc93").lerp(Color("fff1da"),smoothstep(.05,.8,solar))
	moon.rotation_degrees=Vector3(-maxf(.15,-solar)*50,120,0);moon.light_energy=(1-daylight)*.28
	nature.environment.ambient_light_color=Color("5b76a3").lerp(Color("c4d3cd"),daylight)
	nature.environment.ambient_light_energy=.14+daylight*.26
	nature.environment.fog_density=.0017+(1-daylight)*.0008+cloud*.0015+(.008 if weather=="fog" else 0.0)
	nature.environment.fog_light_color=Color("263854").lerp(Color("acbec1"),daylight)
	var sky=nature.environment.sky.sky_material
	sky.set_shader_parameter("daylight",daylight);sky.set_shader_parameter("overcast",cloud);sky.set_shader_parameter("cloud_shift",Vector2(visual_seconds*.0008,visual_seconds*.0003))
	for probe in nature.content.find_children("RiverReflection","ReflectionProbe",false,false):probe.intensity=.03+.77*daylight

func summary() -> Dictionary:
	return {"hour":hour,"weather":weather,"season":season,"season_source":season_source,"source_context":source_context,"weather_source":"Python habitat" if source_context.has("physical_climate") and weather_choice=="auto" else "decorative","daylight_source":"Python habitat" if source_context.has("physical_climate") and cycle_enabled else "decorative","cycle_enabled":cycle_enabled,"motion_enabled":motion_enabled,"rain":rain,"snow":snow,"wind":wind}
