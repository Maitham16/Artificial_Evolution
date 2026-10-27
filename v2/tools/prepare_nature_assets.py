"""Blender asset optimization. Source files are downloaded with fetch_nature_assets.py."""
import bpy,math,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'.cache/nature/source'
OUT=ROOT/'v2/assets/nature/models';OUT.mkdir(parents=True,exist_ok=True)
# Material-preserving decimation and distinct medium/near meshes keep source
# silhouettes while removing geometry too small to resolve in the simulator.
ASSETS={'fir_sapling':150000,'jacaranda_tree':380000,'fern_02':1400,'flower_empodium':900,'rock_07':3500}
records=[]
for name,budget in ASSETS.items():
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 bpy.ops.import_scene.gltf(filepath=str(SOURCE/name/(name+'.gltf')))
 objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
 # Fir, fern and flower downloads contain multiple variations positioned side
 # by side. Keep one authored variation, not the entire presentation group.
 if len(objects)>1:
  largest=max(objects,key=lambda o:len(o.data.polygons))
  keep=[o for o in objects if o.parent is largest.parent] if name=='jacaranda_tree' else [largest]
  for obj in objects:
   if obj not in keep:bpy.data.objects.remove(obj,do_unlink=True)
  objects=keep
 bpy.context.view_layer.update()
 points=[o.matrix_world@Vector(corner) for o in objects for corner in o.bound_box]
 lo=Vector([min(p[a] for p in points) for a in range(3)]);hi=Vector([max(p[a] for p in points) for a in range(3)])
 center=Vector(((lo.x+hi.x)/2,(lo.y+hi.y)/2,lo.z))
 for o in objects:
  o.location-=center
  bpy.context.view_layer.objects.active=o;o.select_set(True)
  bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
 for o in objects:
  bpy.context.view_layer.objects.active=o
  mod=o.modifiers.new('Runtime triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=mod.name)
 total=sum(len(o.data.polygons) for o in objects)
 for o in objects:
  bpy.context.view_layer.objects.active=o
  if total>budget:
   mod=o.modifiers.new('Runtime silhouette budget','DECIMATE');mod.ratio=max(.002,budget/total);mod.use_collapse_triangulate=True
   bpy.ops.object.modifier_apply(modifier=mod.name)
  for poly in o.data.polygons:poly.use_smooth=True
 # Bake all remaining transforms. Keep surface/material partitions in one mesh
 # so Godot can instance every surface in one MultiMesh draw per material.
 bpy.ops.object.select_all(action='DESELECT')
 for o in objects:o.select_set(True)
 bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.join()
 obj=bpy.context.object;obj.name=name
 bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
 # glTF alpha blend is unnecessary for cutout leaves. It causes poor sorting and
 # excess overdraw. The foliage shader uses cutouts where source textures have alpha.
 for mat in obj.data.materials:
  if mat:mat.surface_render_method='DITHERED'
 folder=OUT/name;folder.mkdir(exist_ok=True)
 bpy.ops.export_scene.gltf(filepath=str(folder/(name+'.gltf')),export_format='GLTF_SEPARATE',use_selection=True,export_yup=True,export_materials='EXPORT')
 triangles=sum(len(p.vertices)-2 for p in obj.data.polygons)
 record={'asset':name,'triangles':triangles,'bounds_metres':[float(v) for v in hi-lo],'file_bytes':sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())}
 records.append(record);print('NATURE_ASSET',json.dumps(record),flush=True)
(OUT/'budgets.json').write_text(json.dumps(records,indent=2)+'\n')
