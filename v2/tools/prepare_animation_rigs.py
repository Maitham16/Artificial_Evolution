"""Blender skeletal clips for event-driven presentation; no simulation imports."""
from pathlib import Path
import bpy, math, json
from mathutils import Vector, Quaternion, Matrix
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'v2/assets/animals/skeletal'
EDIT=ROOT/'v2/art_source/animation'
OUT.mkdir(parents=True,exist_ok=True);EDIT.mkdir(parents=True,exist_ok=True)
NAMES=['Rest','Walk','Run','TurnLeft','TurnRight','Eat','Hunt','Escape','Reproduce','Grow','Die']
records=[]
for model in ['doe','stag','wolf']:
 bpy.ops.wm.open_mainfile(filepath=str(ROOT/'v2/art_source/animals'/(model+'.blend')),load_ui=False,use_scripts=False)
 rig=next(o for o in bpy.data.objects if o.type=='ARMATURE')
 bpy.context.view_layer.objects.active=rig
 if rig.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
 rig.data.pose_position='POSE'
 wolf=model=='wolf'
 originals={n:bpy.data.actions[n] for n in ['Idle','Run']}
 if not wolf:
  raw=ROOT/'.cache/animals'/('doe.blend' if model=='doe' else 'stag.blend')
  with bpy.data.libraries.load(str(raw),link=False) as (source,target):target.actions=[n for n in ['Eat.001','Die.000'] if n in source.actions]
  originals.update(Eat=bpy.data.actions.get('Eat.001'),Die=bpy.data.actions.get('Die.000'))
 originals['Idle'].name='Rest'
 # Keep source gallop, feeding and death actions when available.
 for name in ['Eat','Die']:
  if originals.get(name):originals[name].name=name
 for name in NAMES:
  if name in bpy.data.actions:continue
  source=originals['Run'] if name in ['Hunt','Escape'] else None
  if source:
   action=source.copy();action.name=name;action.use_fake_user=True
   # Preserve the gait while adding a restrained alert posture, with no
   # root translation. The viewer only selects these clips from telemetry.
   rig.animation_data.action=action
   if action.slots:rig.animation_data.action_slot=action.slots[0]
   end=int(action.frame_range[1])
   samples=[]
   for frame in range(end+1):
    bpy.context.scene.frame_set(frame)
    samples.append((frame,{n:(rig.pose.bones[n].rotation_quaternion.copy(),rig.pose.bones[n].location.copy()) for n in (['b_Neck','b_Head','b_Jaw'] if wolf else ['IK-Head'])}))
   for frame,values in samples:
    if wolf and name=='Hunt':
     for bone_name,angle in [('b_Neck',.05),('b_Head',.06),('b_Jaw',.04)]:
      bone=rig.pose.bones[bone_name];bone.rotation_mode='QUATERNION'
      axis=bone.bone.matrix_local.to_3x3().inverted()@Vector((1,0,0))
      bone.rotation_quaternion=values[bone_name][0]@Quaternion(axis.normalized(),angle)
      bone.keyframe_insert('rotation_quaternion',frame=frame,group=bone_name)
    elif not wolf and name=='Escape':
     bone=rig.pose.bones['IK-Head'];axis=bone.bone.matrix_local.to_3x3().inverted()@Vector((0,0,.12))
     bone.location=values['IK-Head'][1]+axis;bone.keyframe_insert('location',frame=frame,group=bone.name)
   continue
  rig.animation_data.action=None
  frames=24 if name in ['Walk','Die'] else 48
  for frame in range(frames+1):
   t=frame/frames;phase=t*math.tau
   for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4);bone.rotation_mode='QUATERNION'
   def rotate(name,axis,angle):
    bone=rig.pose.bones.get(name)
    if bone:
     local=bone.bone.matrix_local.to_3x3().inverted()@Vector(axis)
     bone.rotation_quaternion=Quaternion(local.normalized(),angle)
   def offset(name,value):
    bone=rig.pose.bones.get(name)
    if bone:bone.location=bone.bone.matrix_local.to_3x3().inverted()@Vector(value)
   vertical=(0,1,0) if wolf else (0,0,1)
   side=(1,0,0)
   head='b_Head' if wolf else 'Head'
   neck='b_Neck' if wolf else 'Backbone.002'
   if name=='Walk':
    if wolf:
     for side_name,front_phase,back_phase in [('Left',0,.75),('Right',.5,.25)]:
      for part,shift,amplitude in [('UpperArm',front_phase,.27),('Leg01',back_phase,.32)]:
       cycle=(t+shift)%1;wave=math.cos(cycle*math.tau)
       rotate('b_'+side_name+part,side,wave*amplitude)
       if part=='UpperArm':rotate('b_'+side_name+'ForeArm',side,max(0,-math.sin(cycle*math.tau))*.32)
       else:rotate('b_'+side_name+'Leg02',side,-max(0,-math.sin(cycle*math.tau))*.3)
    else:
     for leg,shift in [('Frontleg_L',0),('Backleg_R',.25),('Frontleg_R',.5),('Backleg_L',.75)]:
      cycle=(t+shift)%1
      if cycle<.6:y=-1.5+3*cycle/.6;z=0
      else:swing=(cycle-.6)/.4;y=1.5-3*swing;z=math.sin(math.pi*swing)*.55
      offset('IK-'+leg,(0,y,z))
   elif name in ['TurnLeft','TurnRight']:
    sign=1 if name=='TurnLeft' else -1
    rotate(neck,vertical,sign*.24);rotate(head,vertical,sign*.12)
   elif name=='Eat':
    envelope=math.sin(math.pi*t)**2
    rotate(neck,side,.48*envelope);rotate(head,side,.35*envelope)
    rotate('b_Jaw',side,.12*abs(math.sin(phase*3))*envelope)
   elif name=='Die':
    progress=t*t*(3-2*t)
    rotate('b_Root',(0,0,1),progress*1.48)
    offset('b_Root',(0,17*progress,0))
    for sn in ['Left','Right']:
     rotate('b_'+sn+'UpperArm',side,.8*progress);rotate('b_'+sn+'ForeArm',side,-1.0*progress)
     rotate('b_'+sn+'Leg01',side,-.65*progress);rotate('b_'+sn+'Leg02',side,-.9*progress)
    rotate(head,side,.23*progress)
   elif name in ['Reproduce','Grow']:
    envelope=math.sin(math.pi*t)**2
    rotate(neck,side,(.12 if name=='Reproduce' else -.09)*envelope)
    rotate(head,side,.12*envelope)
   else:
    rotate(head,side,math.sin(phase)*.018)
   for bone in rig.pose.bones:
    bone.keyframe_insert('location',frame=frame,group=bone.name)
    bone.keyframe_insert('rotation_quaternion',frame=frame,group=bone.name)
    bone.keyframe_insert('scale',frame=frame,group=bone.name)
  rig.animation_data.action.name=name;rig.animation_data.action.use_fake_user=True
 for action in list(bpy.data.actions):
  if action.name not in NAMES:bpy.data.actions.remove(action)
 rig.animation_data.action=bpy.data.actions['Rest']
 if rig.animation_data.action.slots:rig.animation_data.action_slot=rig.animation_data.action.slots[0]
 bpy.context.scene.frame_set(0);bpy.context.scene.render.fps=24
 bpy.ops.wm.save_as_mainfile(filepath=str(EDIT/(model+'.blend')))
 folder=OUT/model;folder.mkdir(exist_ok=True)
 bpy.ops.object.select_all(action='SELECT')
 bpy.ops.export_scene.gltf(filepath=str(folder/(model+'.gltf')),export_format='GLTF_SEPARATE',use_selection=True,
  export_yup=True,export_skins=True,export_animations=True,export_animation_mode='ACTIONS',
  export_force_sampling=True,export_bake_animation=True,export_frame_range=False)
 records.append({'model':model,'animations':NAMES,'walk_stride':.65 if not wolf else .72,'run_stride':1.15,
  'clip_durations':{'Rest':4.,'Walk':1.,'Run':.55,'TurnLeft':1.,'TurnRight':1.,'Eat':1.1,'Hunt':.55,'Escape':.55,'Reproduce':1.2,'Grow':2.,'Die':1.3}})
 print('ANIMATION_RIG',model,flush=True)
(OUT/'models.json').write_text(json.dumps(records,indent=2)+'\n')
