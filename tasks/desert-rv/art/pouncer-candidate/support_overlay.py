"""Render explicitly diagnostic translucent witness overlays AFTER asset exports.
The original opaque death-rest images remain unchanged and are delivered alongside them.
"""
import bpy
from mathutils import Vector
from death_support import TrunkSupport

def render_support_overlays(scene,cam,body,details,rig,clips,review,camera_at):
    rig.animation_data.action=bpy.data.actions['Death'];scene.frame_set(clips['Death']['frame_end'])
    patches=TrunkSupport(body).inspect();created=[];saved=[];copies={}
    for obj in [body]+details:
        saved.append((obj,list(obj.data.materials)))
        for index,material in enumerate(obj.data.materials):
            if material.name not in copies:
                cp=material.copy();cp.name='DIAGNOSTIC_TRANSPARENT_'+material.name
                nodes=cp.node_tree.nodes;links=cp.node_tree.links;out=nodes.get('Material Output')
                original=out.inputs['Surface'].links[0].from_socket
                transparent=nodes.new('ShaderNodeBsdfTransparent');mix=nodes.new('ShaderNodeMixShader');mix.inputs[0].default_value=.24
                links.new(transparent.outputs[0],mix.inputs[1]);links.new(original,mix.inputs[2]);links.new(mix.outputs[0],out.inputs['Surface']);copies[material.name]=cp
            obj.data.materials[index]=copies[material.name]
    def color_material(name,color):
        m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes;e=n.new('ShaderNodeEmission');e.inputs['Color'].default_value=(*color,1);e.inputs['Strength'].default_value=1.5;m.node_tree.links.new(e.outputs[0],n['Material Output'].inputs['Surface']);return m
    mats={'shoulder':color_material('DIAGNOSTIC_Shoulder',(1,.12,.025)),'pelvis':color_material('DIAGNOSTIC_Pelvis',(.025,.75,1))}
    for name,patch in patches.items():
        for witness in patch['witnesses']:
            point=Vector(witness['world_xyz_m']);bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=.011,location=point)
            o=bpy.context.object;o.name='DIAGNOSTIC_'+name+'_vertex_'+str(witness['vertex']);o.data.materials.append(mats[name]);created.append(o)
        point=Vector(patch['lowest_world_xyz_m'])
        bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=.003,depth=.40,location=point+Vector((0,0,.20)))
        o=bpy.context.object;o.name='DIAGNOSTIC_'+name+'_contact_vertical';o.data.materials.append(mats[name]);created.append(o)
    texts=[]
    for line,(name,patch) in enumerate(patches.items()):
        bpy.ops.object.text_add();o=bpy.context.object;o.name='DIAGNOSTIC_'+name+'_label';o.data.size=.060
        witness=patch['witnesses'][0];x,y,z=witness['world_xyz_m']
        weights=', '.join(f'{bone}={weight:.2f}' for bone,weight in sorted(witness['weights'].items(),key=lambda item:-item[1]))
        o.data.body=f"{name} xyz=({x:.3f},{y:.3f},{z:.3f})m | trunk={100*witness['trunk_weight']:.1f}%\n{weights}"
        o.data.materials.append(mats[name]);created.append(o);texts.append((o,line))
    for index in (3,7):
        camera_at(cam,index*6.283185307179586/8);bpy.context.view_layer.update()
        for obj,line in texts:
            obj.location=cam.matrix_world@Vector((-1.92,.94-line*.22,-4));obj.rotation_euler=cam.rotation_euler
        scene.render.filepath=str(review/f'death-support-overlay-{index:02}.png');bpy.ops.render.render(write_still=True)
    for obj,materials in saved:
        for index,material in enumerate(materials):obj.data.materials[index]=material
    for obj in created:bpy.data.objects.remove(obj,do_unlink=True)
