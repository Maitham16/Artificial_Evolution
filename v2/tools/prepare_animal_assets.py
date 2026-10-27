"""Convert pinned CC0 animal sources using Blender 5.2; no simulation imports."""
from pathlib import Path
import json
import math
import bpy
from mathutils import Vector, Quaternion

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / '.cache/animals'
OUTPUT = ROOT / 'v2/assets/animals'
EDITABLE = ROOT / 'v2/art_source/animals'
OUTPUT.mkdir(parents=True, exist_ok=True)
EDITABLE.mkdir(parents=True, exist_ok=True)


def material(name, color_image=None, normal_image=None, eye=False):
    mat = bpy.data.materials.new(name + '_PBR')
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    principled = nodes.get('Principled BSDF')
    principled.inputs['Roughness'].default_value = .18 if eye else .86
    principled.inputs['Base Color'].default_value = (.065, .037, .018, 1) if eye else (.7, .7, .7, 1)
    if color_image:
        texture = nodes.new('ShaderNodeTexImage'); texture.image = color_image
        links.new(texture.outputs['Color'], principled.inputs['Base Color'])
    if normal_image:
        normal_image.colorspace_settings.name = 'Non-Color'
        texture = nodes.new('ShaderNodeTexImage'); texture.image = normal_image
        normal = nodes.new('ShaderNodeNormalMap'); normal.inputs['Strength'].default_value = .5
        links.new(texture.outputs['Color'], normal.inputs['Color'])
        links.new(normal.outputs['Normal'], principled.inputs['Normal'])
    return mat


def wolf_actions(rig):
    """Author in-place quadruped cycles on the licensed source skeleton."""
    for name, frames in [('Idle', 72), ('Run', 24)]:
        rig.animation_data_create(); rig.animation_data.action = None
        for frame in range(frames + 1):
            phase = frame / frames * math.tau
            for bone in rig.pose.bones:
                bone.rotation_mode = 'QUATERNION'; bone.rotation_quaternion = Quaternion()
                angle = 0.0; axis = Vector((1, 0, 0))
                if name == 'Run':
                    for side, offset in [('Left', 0), ('Right', math.pi)]:
                        wave = math.sin(phase + offset)
                        if bone.name == f'b_{side}UpperArm': angle = wave * .38
                        elif bone.name == f'b_{side}ForeArm': angle = max(0, -wave) * .42
                        elif bone.name == f'b_{side}Hand01': angle = -wave * .12
                        elif bone.name == f'b_{side}Leg01': angle = -wave * .44
                        elif bone.name == f'b_{side}Leg02': angle = max(0, wave) * -.42
                        elif bone.name == f'b_{side}Foot01': angle = wave * .18
                if 'Tail' in bone.name:
                    axis = Vector((0, 1, 0)); angle = math.sin(phase + .4) * .035
                if bone.name == 'b_Head': angle = math.sin(phase) * (.025 if name == 'Idle' else .04)
                local_axis = bone.bone.matrix_local.to_3x3().inverted() @ axis
                bone.rotation_quaternion = Quaternion(local_axis.normalized(), angle)
                bone.keyframe_insert('rotation_quaternion', frame=frame, group=bone.name)
        rig.animation_data.action.name = name
        rig.animation_data.action.use_fake_user = True
    rig.animation_data.action = bpy.data.actions['Idle']


def bake_vertex_cycles(rig, meshes, folder):
    """Sample Blender's evaluated rig into GPU-readable position/normal textures."""
    width = 1024
    total = sum(len(obj.data.vertices) for obj in meshes)
    rows = math.ceil(total / width)
    samples, normals, clips = [], [], {}
    for name, count in [('Idle', 32), ('Run', 24)]:
        action = bpy.data.actions[name]
        rig.animation_data.action = action
        if action.slots: rig.animation_data.action_slot = action.slots[0]
        start, end = action.frame_range
        clips[name] = {'start': len(samples), 'count': count, 'duration': (end-start)/24}
        for index in range(count):
            frame = start+(end-start)*index/count
            bpy.context.scene.frame_set(int(frame), subframe=frame-int(frame))
            graph = bpy.context.evaluated_depsgraph_get()
            positions, directions = [], []
            for obj in meshes:
                evaluated = obj.evaluated_get(graph)
                mesh = evaluated.to_mesh()
                assert len(mesh.vertices) == len(obj.data.vertices), 'Animation changed topology'
                positions.extend((v.co.x,v.co.z,-v.co.y) for v in mesh.vertices)
                directions.extend((v.normal.x,v.normal.z,-v.normal.y) for v in mesh.vertices)
                evaluated.to_mesh_clear()
            samples.append(positions); normals.append(directions)
    low = [min(p[a] for frame in samples for p in frame) for a in range(3)]
    span = [max(p[a] for frame in samples for p in frame)-low[a] for a in range(3)]
    texture_height = rows*len(samples)
    for kind, source in [('positions', samples), ('normals', normals)]:
        pixels = []
        for frame in source:
            for p in frame:
                pixels.extend([(p[a]-low[a])/max(.001, span[a]) if kind == 'positions'
                               else p[a]*.5+.5 for a in range(3)] + [1.0])
            pixels.extend([0.0, 0.0, 0.0, 1.0]*(width*rows-total))
        image = bpy.data.images.new('Gait_'+kind, width=width, height=texture_height, float_buffer=True)
        image.colorspace_settings.name = 'Non-Color'
        image.pixels.foreach_set(pixels)
        image.filepath_raw = str(folder/(kind+'.exr')); image.file_format = 'OPEN_EXR'; image.save()
        bpy.data.images.remove(image)
    offset = 0
    for obj in meshes:
        while len(obj.data.uv_layers)>1: obj.data.uv_layers.remove(obj.data.uv_layers[-1])
        lookup = obj.data.uv_layers.new(name='AnimationLookup')
        for loop in obj.data.loops:
            vertex = offset+loop.vertex_index
            lookup.data[loop.index].uv = ((vertex%width+.5)/width, (vertex//width+.5)/texture_height)
        obj.data.uv_layers.active_index = 0; obj.data.uv_layers[0].active_render = True
        offset += len(obj.data.vertices)
    return {'vertices': total, 'rows_per_frame': rows, 'texture_size': [width, texture_height],
            'position_min': low, 'position_span': span, 'clips': clips}


records = []
for key, source, height in [('doe', SOURCE/'doe.blend', 1.10),
                            ('stag', SOURCE/'stag.blend', 1.43),
                            ('wolf', SOURCE/'wolf-source/dog2.blend', .85)]:
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    rig = next(obj for obj in bpy.data.objects if obj.type == 'ARMATURE')
    bpy.context.view_layer.objects.active = rig
    if bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    for obj in list(bpy.data.objects):
        if obj.type not in {'ARMATURE', 'MESH'} or obj.name.startswith('Plane'):
            bpy.data.objects.remove(obj, do_unlink=True)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if key == 'wolf':
        color = bpy.data.images.load(str(SOURCE/'wolf-source/dog2Color.png'), check_existing=True)
        normal = bpy.data.images.load(str(SOURCE/'wolf-source/dog2Normal.png'), check_existing=True)
        for obj in meshes:
            obj.data.materials.clear(); obj.data.materials.append(material('WolfCoat', color, normal))
        wolf_actions(rig)
    else:
        keep = {bpy.data.actions['Run'], bpy.data.actions['Idle.000']}
        rig.animation_data.action = None
        for action in list(bpy.data.actions):
            if action not in keep: bpy.data.actions.remove(action)
        for action in keep:
            action.name = 'Run' if action.name == 'Run' else 'Idle'; action.use_fake_user = True
        rig.animation_data.action = bpy.data.actions['Idle']
        mappings = {}
        for obj in meshes:
            obj.data.uv_layers.active_index = 0
            for index, old in enumerate(list(obj.data.materials)):
                name = old.name.lower()
                if name not in mappings:
                    image = None; normal = None
                    if name in ['body', 'head']:
                        image = bpy.data.images.get(('doe-' if key == 'doe' else '') + name)
                        normal = bpy.data.images.get('deer-' + name + '-normal.png')
                    elif name == 'antlers':
                        image = bpy.data.images.get('deer-antlers.png')
                        normal = bpy.data.images.get('deer-antlers-normal.png')
                    mappings[name] = material(name, image, normal, eye=name == 'eye')
                obj.data.materials[index] = mappings[name]
    # Keep every original vertex weight and the IK rig. A parent transform
    # normalizes units and heading without changing skin bind matrices.
    rig.data.pose_position = 'REST'; bpy.context.view_layer.update()
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    low = Vector([min(p[a] for p in points) for a in range(3)])
    high = Vector([max(p[a] for p in points) for a in range(3)])
    center = Vector((0, (high.y+low.y)*.5, low.z))
    scale = height / (high.z-low.z)
    wrapper = bpy.data.objects.new('Animal', None); bpy.context.collection.objects.link(wrapper)
    for obj in [o for o in bpy.context.scene.objects if o != wrapper and o.parent is None]:
        matrix = obj.matrix_world.copy(); obj.parent = wrapper; obj.matrix_world = matrix
    wrapper.rotation_euler.z = math.pi/2  # Source -Y forward -> Godot +X.
    wrapper.scale = Vector((scale,)*3)
    wrapper.location = -(wrapper.rotation_euler.to_matrix() @ center) * scale
    rig.data.pose_position = 'POSE'; bpy.context.scene.frame_set(0)
    for obj in meshes:
        for polygon in obj.data.polygons: polygon.use_smooth = True
    scene = bpy.context.scene; scene.render.fps = 24; scene.frame_start = 0; scene.frame_end = 72
    # Pack textures so the editable model is self-contained on another Mac.
    for image in bpy.data.images:
        if image.size[0] and image.source == 'FILE':
            try: image.pack()
            except RuntimeError: pass
    bpy.ops.wm.save_as_mainfile(filepath=str(EDITABLE/(key+'.blend')))
    folder = OUTPUT/key; folder.mkdir(parents=True, exist_ok=True)
    vat = bake_vertex_cycles(rig, meshes, folder)
    rig.data.pose_position = 'REST'; bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(filepath=str(folder/(key+'.gltf')), export_format='GLTF_SEPARATE',
        use_selection=True, export_yup=True, export_animations=False, export_skins=False)
    document = json.loads((folder/(key+'.gltf')).read_text())
    # Runtime geometry uses GPU poses; discard unreferenced static bone nodes.
    parents = {child: index for index, node in enumerate(document['nodes']) for child in node.get('children', [])}
    needed = {index for index, node in enumerate(document['nodes']) if 'mesh' in node}
    for index in list(needed):
        while index in parents:
            index = parents[index]; needed.add(index)
    remap = {old: new for new, old in enumerate(sorted(needed))}
    nodes = []
    for index in sorted(needed):
        node = document['nodes'][index]
        if 'children' in node: node['children'] = [remap[c] for c in node['children'] if c in needed]
        nodes.append(node)
    document['nodes'] = nodes
    for scene_data in document['scenes']: scene_data['nodes'] = [remap[i] for i in scene_data['nodes'] if i in needed]
    (folder/(key+'.gltf')).write_text(json.dumps(document, separators=(',', ':'))+'\n')
    triangles = sum(len(p.vertices)-2 for obj in meshes for p in obj.data.polygons)
    record = {'model': key, 'source_triangles': triangles, 'height_metres': height,
              'animations': ['Idle', 'Run'], 'animation_storage': 'Blender-baked vertex textures',
              'source_skin_joints': len(rig.data.bones), 'vat': vat}
    records.append(record); print('ANIMAL_BUILT', json.dumps(record), flush=True)
(OUTPUT/'models.json').write_text(json.dumps(records, indent=2)+'\n')
