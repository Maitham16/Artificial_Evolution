"""Run with Blender --background --factory-startup --python this_file."""
from pathlib import Path
import math,random
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/models';OUT.mkdir(parents=True,exist_ok=True)
SOURCE=ROOT/'art_source';SOURCE.mkdir(exist_ok=True)

def material(name,color,metal=0,rough=.55,emission=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1)
 p.inputs['Metallic'].default_value=metal;p.inputs['Roughness'].default_value=rough
 p.inputs['Emission Color'].default_value=(*color,1);p.inputs['Emission Strength'].default_value=emission
 return m

def sphere(name,location,scale,mat,segments=16,rings=8):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=location)
 o=bpy.context.object;o.name=name;o.scale=scale;o.data.materials.append(mat)
 for p in o.data.polygons:p.use_smooth=True
 return o

def limb(name,a,b,radius,mat):
 delta=Vector(b)-Vector(a)
 bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=radius,depth=delta.length,location=(Vector(a)+Vector(b))*.5)
 o=bpy.context.object;o.name=name;o.rotation_euler=delta.to_track_quat('Z','Y').to_euler();o.data.materials.append(mat)
 return o

def clean():
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)

def save(name):
 bpy.ops.object.select_all(action='SELECT')
 bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE/(name+'.blend')))
 groups={}
 for o in list(bpy.context.scene.objects):
  if o.type=='MESH':
   key=o.data.materials[0].name if name=='creature' and o.data.materials else name
   groups.setdefault(key,[]).append(o)
 for key,objects in groups.items():
  bpy.ops.object.select_all(action='DESELECT')
  for o in objects:o.select_set(True)
  bpy.context.view_layer.objects.active=objects[0]
  bpy.ops.object.join();bpy.context.object.name=key
 bpy.ops.object.select_all(action='SELECT')
 bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')),export_format='GLB',use_selection=True,export_yup=True)

clean()
body=material('Body',(.68,.86,.7),rough=.38)
feet=material('Legs',(.09,.19,.18),rough=.6)
white=material('Eye',(.91,.97,.9),rough=.2)
pupil=material('Pupil',(.018,.04,.04),rough=.2)
sphere('Body',(0,0,.34),(.47,.31,.26),body)
sphere('Head',(.35,0,.34),(.25,.26,.23),body)
for sign in (-1,1):
 sphere('Eye',(.49,sign*.15,.46),(.1,.085,.1),white)
 sphere('Pupil',(.565,sign*.15,.47),(.034,.05,.052),pupil,12,6)
 for index,x in enumerate((-.28,-.02,.24)):
  knee=(x-.07,sign*.40,.19);tip=(x+.04,sign*.51,.045)
  limb('Leg', (x,sign*.19,.27),knee,.035,feet);limb('Foot',knee,tip,.027,feet)
 limb('Antenna',(.34,sign*.13,.51),(.48,sign*.25,.68),.015,feet)
 sphere('Tip',(.48,sign*.25,.68),(.035,.035,.035),body,8,4)
save('creature')
clean()
stem=material('Stem',(.13,.28,.19),rough=.75)
fruit=material('Nutrient',(.48,.94,.52),rough=.35,emission=.3)
limb('Stem',(0,0,0),(0,0,.25),.045,stem)
for angle,height in ((0,.26),(2.2,.18),(4.1,.19)):
 p=(math.cos(angle)*.105,math.sin(angle)*.105,height)
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.16,location=p)
 bpy.context.object.name='Nutrient';bpy.context.object.scale=(.8,.8,1.25);bpy.context.object.data.materials.append(fruit)
save('nutrient')
clean()
rock=material('Basalt',(.20,.28,.28),metal=.1,rough=.9)
rng=random.Random(20)
for i in range(3):
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=1,location=(rng.uniform(-.5,.5),rng.uniform(-.25,.25),.24))
 o=bpy.context.object;o.name='Basalt';o.scale=(rng.uniform(.6,1),rng.uniform(.5,.8),rng.uniform(.35,.65));o.data.materials.append(rock)
save('basalt')
print('AE2_ASSETS_BUILT',OUT)
