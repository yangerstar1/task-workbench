"""SOURCE-ONLY candidate. Run Blender 4.2.3 exclusively in an approved public Actions job.
Usage: blender -b --python generate.py -- --output OUTPUT --phase static|motion
No downloads, publishing, Unity mutations, third-party textures, or runtime damage.
"""
import argparse, json, math, sys
from pathlib import Path
import bpy, bmesh
from mathutils import Vector, Matrix
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import motion
import cavity_geometry
from artifact_io import fresh_output
P=json.loads((HERE/'parameters.json').read_text())
p=argparse.ArgumentParser(); p.add_argument('--output',required=True); p.add_argument('--phase',choices=['static','motion'],required=True)
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]); OUT=fresh_output(args.output)
if bpy.app.version[:3]!=(4,2,3): raise RuntimeError('Pinned Blender 4.2.3 required')
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene; scene.render.fps=P['fps']; scene.unit_settings.system='METRIC'
assets=[]
def active(o):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active=o
# Palette: faded cream paint, oxide, dark iron, warm hide, vent amber, horn, slate, soot.
PALETTE=[(.55,.40,.22),(.30,.092,.038),(.072,.063,.045),(.22,.14,.066),(.82,.29,.028),(.46,.34,.18),(.16,.19,.15),(.025,.021,.016)]
tex=bpy.data.images.new('Bulwark_Original_BaseColor',width=512,height=512,alpha=False)
pixels=[]
for y in range(512):
    for x in range(512):
        tile=(y//256)*4+x//128; base=PALETTE[tile]
        u=(x%128)/127; v=(y%256)/255
        # Sparse broad paint loss. No periodic stripe, wood grain or repeated diagonal bands.
        chip=tile in (0,1) and ((u<.22 and .24<v<.43) or (.64<u<.88 and v>.79) or (u>.83 and .13<v<.23))
        tone=.012*(u-.5)+.008*(v-.5)
        color=(.19,.18,.145) if chip else base
        pixels.extend([max(.004,min(1,k+tone)) for k in color]+[1])
tex.pixels=pixels; tex.filepath_raw=str(OUT/'bulwark-basecolor.png'); tex.file_format='PNG'; tex.save(); tex.pack()
mat=bpy.data.materials.new('Bulwark_StandardPBR_Atlas'); mat.use_nodes=True
nodes=mat.node_tree.nodes; bs=nodes.get('Principled BSDF'); bs.inputs['Roughness'].default_value=.77; bs.inputs['Metallic'].default_value=.12
image_node=nodes.new('ShaderNodeTexImage'); image_node.image=tex; mat.node_tree.links.new(image_node.outputs['Color'],bs.inputs['Base Color'])
orm=bpy.data.images.new('Bulwark_Original_ORM',width=512,height=512,alpha=False); orm.colorspace_settings.name='Non-Color'
orm_pixels=[]
for y in range(512):
    for x in range(512):
        tile=(y//256)*4+x//128; u=(x%128)/127; v=(y%256)/255
        chip=tile in (0,1) and ((u<.22 and .24<v<.43) or (.64<u<.88 and v>.79) or (u>.83 and .13<v<.23))
        metal=chip or tile in (2,6); orm_pixels.extend([1,.38 if metal else .78,.72 if metal else 0,1])
orm.pixels=orm_pixels; orm.filepath_raw=str(OUT/'bulwark-orm.png'); orm.file_format='PNG'; orm.save(); orm.pack()
orm_node=nodes.new('ShaderNodeTexImage'); orm_node.image=orm; channels=nodes.new('ShaderNodeSeparateColor')
mat.node_tree.links.new(orm_node.outputs['Color'],channels.inputs['Color']); mat.node_tree.links.new(channels.outputs['Green'],bs.inputs['Roughness']); mat.node_tree.links.new(channels.outputs['Blue'],bs.inputs['Metallic'])

def mesh(name,verts,faces,bone,tile):
    me=bpy.data.meshes.new(name); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); scene.collection.objects.link(o); assets.append(o); o['bone']=bone; o.data.materials.append(mat)
    tag=me.attributes.new(name='weakpoint_face',type='INT',domain='FACE')
    for value in tag.data:value.value=int(name.startswith('WeakpointTissue'))
    bm=bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(me); bm.free()
    active(o); bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=1.15,island_margin=.025); bpy.ops.object.mode_set(mode='OBJECT')
    for uv in o.data.uv_layers.active.data:
        uv.uv.x=(tile%4+(uv.uv.x*.88+.06))/4; uv.uv.y=(tile//4+(uv.uv.y*.88+.06))/2
    return o

def loft(name,sections,bone,tile,sides=12):
    # Ring axis Y. Intentional chamfered section planes, closed manifold caps.
    verts=[]; faces=[]
    for x,y,z,w,h in sections:
        for j in range(sides):
            a=math.tau*j/sides; verts.append((x+w*math.cos(a),y,z+h*math.sin(a)))
    for i in range(len(sections)-1):
        for j in range(sides):
            a=i*sides+j; b=i*sides+(j+1)%sides; faces.append((a,b,b+sides,a+sides))
    faces+=[tuple(reversed(range(sides))),tuple((len(sections)-1)*sides+j for j in range(sides))]
    return mesh(name,verts,faces,bone,tile)

def strut(name,a,b,r1,r2,bone,tile,sides=10):
    a,b=Vector(a),Vector(b); axis=(b-a).normalized(); helper=Vector((0,0,1)) if abs(axis.z)<.95 else Vector((1,0,0)); u=axis.cross(helper).normalized(); v=axis.cross(u)
    verts=[]
    for t,r in ((0,r1),(.12,r1*1.05),(.8,r2),(1,r2*.85)):
        verts += [a.lerp(b,t)+r*(math.cos(j*math.tau/sides)*u+math.sin(j*math.tau/sides)*v) for j in range(sides)]
    faces=[(i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j) for i in range(3) for j in range(sides)]
    faces += [tuple(reversed(range(sides))),tuple(3*sides+j for j in range(sides))]
    return mesh(name,verts,faces,bone,tile)
# A low six-sided thorax supports overlapping salvage plates, unlike the pouncer silhouette.
loft('LivingThorax',[(0,-.94,.66,.29,.17),(0,-.65,.72,.57,.28),(0,-.10,.74,.61,.29),(0,.54,.70,.54,.24),(0,.94,.63,.29,.14)],'body',3,16)
for i,(y,w,z) in enumerate([(-.55,.62,.91),(-.13,.67,1.00),(.29,.62,.97)]):
    loft('DorsalSalvagePlate_%02d'%i,[(0,y-.25,z-.025,w*.70,.045),(0,y-.16,z,w,.125),(0,y+.15,z-.03,w*.92,.11),(0,y+.24,z-.09,w*.68,.035)],'body',0 if i%2==0 else 1,8)
    # Raised longitudinal reinforcing keel provides a distinctive armored silhouette.
    loft('PlateKeel_%02d'%i,[(0,y-.17,z+.10,.06,.016),(0,y,z+.17,.065,.038),(0,y+.15,z+.095,.04,.018)],'body',2,6)
loft('ChiselRam',motion.RAM_SECTIONS,'ram',0,8)
for s in (-1,1):
    loft('RamCuttingRidge',[(s*.37,-1.02,.63,.058,.06),(s*.40,-1.35,.51,.061,.05),(s*.37,-1.55,.45,.022,.022)],'ram',2,6)
    loft('EyeRecess',[(s*.44,-.89,.76,.10,.043),(s*.46,-1.03,.735,.085,.032)],'ram',7,8)
    loft('AmberEye',[(s*.473,-.92,.775,.025,.022),(s*.478,-1.005,.755,.025,.019)],'ram',4,8)
# Fitted posterior cavity: an oval closed rim with a real front wall and bottom.
# No tall rectangular freight box, open front, exposed rods, or fake hit marker.
verts,faces=cavity_geometry.bowl_wall(); mesh('ClosedCavityRim',verts,faces,'body',2)
verts,faces=cavity_geometry.bowl_floor(); mesh('CavityBottom',verts,faces,'body',7)
verts,faces=cavity_geometry.core_disk()
core=mesh('Core_Renderer',verts,faces,'body',4); core['presentation_part']='core'
core_closed=bpy.data.materials.new('Core_Closed'); core_closed.use_nodes=True
core_closed.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.27,.095,.027,1)
core_closed.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.63
core_open=core_closed.copy(); core_open.name='Core_Open'
core_open.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.85,.255,.025,1)
core_open.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value=(.12,.025,.002,1)
core_open.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value=1
core.data.materials.clear(); core.data.materials.append(core_closed)
plate_objects={}
for side,sign in motion.SIDES:
    # Two shallow curved half-shells continue the old overlapping dorsal silhouette.
    verts,faces=cavity_geometry.cover(sign)
    plate=mesh('ArmorPlate_'+side+'_Renderer',verts,faces,'body',1); plate['presentation_part']='plate'; plate_objects[side]=plate
# Four wide load-bearing legs with contrasting recessed linkages and bevel-shaped greaves.
rest={}
for k in motion.LEGS:
    h,f=motion.HIP[k],motion.FOOT[k]; n=motion.knee(h,f,k); rest[k]=(h,n,f)
    strut('UpperArm_'+k,h,n,.12,.10,'upper.'+k,3)
    strut('Greave_'+k,n,f,.13,.085,'lower.'+k,0)
    s=1 if k.endswith('L') else -1
    strut('KneePin_'+k,motion.add(n,(-.10,0,0)),motion.add(n,(.10,0,0)),.09,.09,'lower.'+k,2,12)
    x,y,z=f
    loft('LoadFoot_'+k,[(x,y+.16,.085,.115,.075),(x,y+.06,.08,.155,.075),(x,y-.18,.07,.15,.065),(x,y-.24,.055,.10,.05)],'foot.'+k,2,8)
    for dx in (-.085,.085):
        loft('ToeCleat_'+k,[(x+dx,y-.13,.068,.038,.028),(x+dx,y-.29,.039,.025,.031)],'foot.'+k,5,6)
# Rigidly weighted armor parts are intentional. No automatic weights or cross-limb leakage.
bpy.ops.object.armature_add(enter_editmode=True); rig=bpy.context.object; rig.name='Bulwark_Rig'; rig.data.edit_bones.remove(rig.data.edit_bones[0])
def bone(n,h,t,parent=None):
    b=rig.data.edit_bones.new(n); b.head=h; b.tail=t
    if parent:b.parent=rig.data.edit_bones[parent]
bone('root',(0,0,0),(0,0,.2)); bone('body',(0,0,.69),(0,0,1.0),'root')
bone('ram',(0,-.79,.66),(0,-1.15,.66),'body')
for k,(h,n,f) in rest.items():
    bone('upper.'+k,h,n,'body'); bone('lower.'+k,n,f,'upper.'+k); bone('foot.'+k,f,motion.add(f,(0,-.2,0)),'lower.'+k)
bpy.ops.object.mode_set(mode='OBJECT')
body_assets=[o for o in assets if not o.get('presentation_part')]
for o in body_assets:
    o.parent=rig; g=o.vertex_groups.new(name=o['bone']); g.add(list(range(len(o.data.vertices))),1,'REPLACE'); mod=o.modifiers.new('Deform','ARMATURE'); mod.object=rig
# One skinned renderer and one atlas material, not one draw call per armor fragment.
bpy.ops.object.select_all(action='DESELECT')
for o in body_assets:o.select_set(True)
bpy.context.view_layer.objects.active=body_assets[0]; bpy.ops.object.join()
combined=bpy.context.object; combined.name='Bulwark_Body'; assets=[combined,core]+list(plate_objects.values())
# Joining same-material objects can retain duplicate material slots; remap deterministically.
for poly in combined.data.polygons:poly.material_index=0
while len(combined.data.materials)>1:combined.data.materials.pop(index=len(combined.data.materials)-1)
sole_indices={k:[] for k in motion.LEGS}
for k in motion.LEGS:
    gi=combined.vertex_groups['foot.'+k].index
    sole_indices[k]=[v.index for v in combined.data.vertices if any(g.group==gi and g.weight>.99 for g in v.groups)]
# Dedicated unkeyed presentation branch, carrier body bone may move the whole assembly.
assembly=bpy.data.objects.new('WeakPointAssembly',None); scene.collection.objects.link(assembly)
assembly.parent=rig; assembly.parent_type='BONE'; assembly.parent_bone='body'; bpy.context.view_layer.update(); assembly.matrix_world=Matrix.Identity(4)
core.parent=assembly; core.matrix_world=Matrix.Identity(4)
pivots={}
for side,sign in motion.SIDES:
    pivot=bpy.data.objects.new('ArmorPlate_'+side+'_Pivot',None); scene.collection.objects.link(pivot); pivot.parent=assembly; pivot.location=(sign*.48,.78,.86)
    pivot.rotation_mode='XYZ'; plate=plate_objects[side]; plate.parent=pivot
    plate.matrix_parent_inverse=Matrix.Identity(4); plate.location=-pivot.location
    pivots[side]=pivot
presentation_nodes=[assembly]+list(pivots.values())
def set_presentation(exposed):
    # Review-only emulation of WeakPointExposed. Never insert animation keys here.
    core.data.materials[0]=core_open if exposed else core_closed
    for side,sign in motion.SIDES:pivots[side].rotation_euler=(0,sign*P['gate_open_radians'] if exposed else 0,0)
    bpy.context.view_layer.update()
set_presentation(False)
for pb in rig.pose.bones: pb.rotation_mode='QUATERNION'
rest_matrices={b.name:b.matrix_local.copy() for b in rig.data.bones}
def translate(z): return Matrix.Translation((0,0,z))
def apply_pose(pose):
    rig.pose.bones['root'].matrix=rest_matrices['root']; z=pose['z']
    rig.pose.bones['body'].matrix=translate(z)@rest_matrices['body']; bpy.context.view_layer.update()
    for name,angle,axis in [('ram',pose['ram'],'X')]:
        pivot=rest_matrices[name].translation
        rig.pose.bones[name].matrix=translate(z)@Matrix.Translation(pivot)@Matrix.Rotation(angle,4,axis)@Matrix.Translation(-pivot)@rest_matrices[name]
    for k in motion.LEGS:
        h=Vector(motion.add(motion.HIP[k],(0,0,z))); f=Vector(pose['feet'][k]); n=Vector(motion.knee(h,f,k))
        for name,a,b in [('upper.'+k,h,n),('lower.'+k,n,f)]:
            # Preserve rest roll: shortest rotation from original limb axis.
            rest_axis=rig.data.bones[name].tail_local-rig.data.bones[name].head_local
            rot=rest_axis.rotation_difference(b-a).to_matrix().to_4x4()
            rig.pose.bones[name].matrix=Matrix.Translation(a)@rot@rest_matrices[name].to_3x3().to_4x4()
            bpy.context.view_layer.update()
        m=rest_matrices['foot.'+k].copy(); m.translation=f; rig.pose.bones['foot.'+k].matrix=m
    bpy.context.view_layer.update()
exec(compile((HERE/'binding_contract.py').read_text(),str(HERE/'binding_contract.py'),'exec'))
# Neutral studio only. No private source image enters any generated output.
scene.render.engine='CYCLES'; scene.cycles.samples=24; scene.cycles.use_denoising=True; scene.view_settings.view_transform='AgX'; scene.world.color=(.18,.18,.18)
scene.render.resolution_x=960; scene.render.resolution_y=540; scene.render.resolution_percentage=100
bpy.ops.mesh.primitive_plane_add(size=200); floor=bpy.context.object; floor.name='REVIEW_ONLY_floor'
fmat=bpy.data.materials.new('REVIEW_ONLY_neutral'); fmat.diffuse_color=(.17,.16,.14,1); floor.data.materials.append(fmat)
for loc,power,size in [((-3,-4,5),750,4),((4,-1,3),350,4),((0,4,5),650,3)]:
    bpy.ops.object.light_add(type='AREA',location=loc); l=bpy.context.object; l.data.energy=power; l.data.shape='DISK'; l.data.size=size; l.rotation_euler=(Vector((0,0,.5))-l.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(); cam=bpy.context.object; cam.data.type='ORTHO'; cam.data.ortho_scale=4.8; scene.camera=cam
from bpy_extras.object_utils import world_to_camera_view
review=OUT/'review'; review.mkdir(exist_ok=True)
def camera(angle,center=(0,-.1,.55)):
    target=Vector(center); cam.location=target+Vector((4*math.sin(angle),-4*math.cos(angle),2.6)); cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler(); bpy.context.view_layer.update()
def bounds():
    deps=bpy.context.evaluated_depsgraph_get(); verts=[]
    for obj in assets:
        ob=obj.evaluated_get(deps); me=ob.to_mesh(); verts.extend(ob.matrix_world@v.co for v in me.vertices); ob.to_mesh_clear()
    return verts
def validate_frame(label,require_full_body=True):
    vs=bounds(); min_z=min(v.z for v in vs); clip=[world_to_camera_view(scene,cam,v) for v in vs]
    errors=[]
    if min_z< -P['floor_penetration_limit_m']: errors.append('floor penetration')
    body_clipped=any(v.z<=0 or min(v.x,v.y)<.035 or max(v.x,v.y)>.965 for v in clip)
    if require_full_body and body_clipped: errors.append('camera clipping')
    return {'errors':errors,'whole_body_clipped_diagnostic':body_clipped,'whole_body_required':require_full_body,'label':label,'min_z':min_z,'screen_min':[min(v.x for v in clip),min(v.y for v in clip)],'screen_max':[max(v.x for v in clip),max(v.y for v in clip)]}
def still(path):
    scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(path); bpy.ops.render.render(write_still=True)
apply_pose(motion.sample('Idle',0)); camera(0)
if args.phase=='static':
    # Early views complete without creating/rendering animation.
    checks=[]
    for i in range(8):
        camera(math.tau*i/8); checks.append(validate_frame('static-'+str(i))); still(review/f'static-{i:02}.png')
    apply_pose(motion.sample('Recover',0)); set_presentation(True); camera(math.pi*.68); checks.append(validate_frame('open-weakpoint')); still(review/'static-weakpoint-open.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bulwark-static-review.blend'))
    exec(compile((HERE/'fps_evidence.py').read_text(),str(HERE/'fps_evidence.py'),'exec'))
    (OUT/'static-checks.json').write_text(json.dumps(checks,indent=2)); sys.exit(1 if any(c['errors'] for c in checks) else 0)
exec(compile((HERE/'animate.py').read_text(),str(HERE/'animate.py'),'exec'))
