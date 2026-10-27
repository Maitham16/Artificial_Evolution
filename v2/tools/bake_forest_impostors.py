"""Bake the original CC0 tree scans into distant forest impostors using Blender."""
import bpy,math,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'v2/assets/nature/impostors';OUT.mkdir(parents=True,exist_ok=True)
records={}
for name in ['fir_sapling','jacaranda_tree']:
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 bpy.ops.import_scene.gltf(filepath=str(ROOT/'.cache/nature/source'/name/(name+'.gltf')))
 objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
 if len(objects)>1:
  biggest=max(objects,key=lambda o:len(o.data.polygons))
  for o in objects:
   if o is not biggest:bpy.data.objects.remove(o,do_unlink=True)
  objects=[biggest]
 bpy.context.view_layer.update()
 points=[o.matrix_world@Vector(p) for o in objects for p in o.bound_box]
 lo=Vector([min(p[a] for p in points) for a in range(3)]);hi=Vector([max(p[a] for p in points) for a in range(3)])
 center=(lo+hi)*.5;size=hi-lo
 scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
 scene.render.resolution_x=768;scene.render.resolution_y=1024;scene.render.resolution_percentage=100
 scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
 scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.5,.62,.74,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.6
 bpy.ops.object.light_add(type='SUN',location=center+Vector((10,-10,20)));light=bpy.context.object;light.rotation_euler=(math.radians(30),math.radians(-25),math.radians(-35));light.data.energy=2.3;light.data.angle=math.radians(7)
 bpy.ops.object.camera_add(location=center+Vector((0,-size.z*3,0)))
 camera=bpy.context.object;camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=max(size.z*1.08,size.x*1.08/(768/1024));scene.camera=camera
 scene.view_settings.view_transform='AgX';scene.render.filepath=str(OUT/(name+'.png'))
 bpy.ops.render.render(write_still=True)
 records[name]={'height':float(camera.data.ortho_scale),'width':float(camera.data.ortho_scale*768/1024),'base_offset':float((camera.data.ortho_scale-size.z)/2),'source':'https://polyhaven.com/a/'+name,'license':'CC0-1.0'}
 print('IMPOSTOR_DONE',name,flush=True)
(OUT/'dimensions.json').write_text(json.dumps(records,indent=2)+'\n')
