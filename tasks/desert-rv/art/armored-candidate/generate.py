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
        wear=.045*math.sin(x*.063+y*.031)+.014*math.sin(x*1.9+y*.81)
        # Painted broad edge wear, not random high-frequency camouflage.
        edge=min(x%128,127-x%128,y%256,255-y%256)<6
        pixels.extend([max(.004,min(1,v+wear+(.065 if edge else 0))) for v in base]+[1])
tex.pixels=pixels; tex.filepath_raw=str(OUT/'bulwark-basecolor.png'); tex.file_format='PNG'; tex.save(); tex.pack()
mat=bpy.data.materials.new('Bulwark_StandardPBR_Atlas'); mat.use_nodes=True
nodes=mat.node_tree.nodes; bs=nodes.get('Principled BSDF'); bs.inputs['Roughness'].default_value=.77; bs.inputs['Metallic'].default_value=.12
image_node=nodes.new('ShaderNodeTexImage'); image_node.image=tex; mat.node_tree.links.new(image_node.outputs['Color'],bs.inputs['Base Color'])
def mesh(name,verts,faces,bone,tile):
    me=bpy.data.meshes.new(name); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); scene.collection.objects.link(o); assets.append(o); o['bone']=bone; o.data.materials.append(mat)
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
for i,(y,w,z) in enumerate([(-.55,.62,.91),(-.13,.67,1.00),(.29,.62,.97),(.67,.48,.85)]):
    loft('DorsalSalvagePlate_%02d'%i,[(0,y-.25,z-.025,w*.70,.045),(0,y-.16,z,w,.125),(0,y+.15,z-.03,w*.92,.11),(0,y+.24,z-.09,w*.68,.035)],'body',0 if i%2==0 else 1,8)
    # Raised longitudinal reinforcing keel provides a distinctive armored silhouette.
    loft('PlateKeel_%02d'%i,[(0,y-.17,z+.10,.06,.016),(0,y,z+.17,.065,.038),(0,y+.15,z+.095,.04,.018)],'body',2,6)
loft('ChiselRam',motion.RAM_SECTIONS,'ram',0,8)
for s in (-1,1):
    loft('RamCuttingRidge',[(s*.37,-1.02,.63,.058,.06),(s*.40,-1.35,.51,.061,.05),(s*.37,-1.55,.45,.022,.022)],'ram',2,6)
    loft('EyeRecess',[(s*.44,-.89,.76,.10,.043),(s*.46,-1.03,.735,.085,.032)],'ram',7,8)
    loft('AmberEye',[(s*.473,-.92,.775,.025,.022),(s*.478,-1.005,.755,.025,.019)],'ram',4,8)
for side,s in motion.SIDES:
    # Real separate hinged cover; side/rear weak tissue is concealed at rest.
    loft('ExposedVentTissue_'+side,[(s*.51,.05,.70,.065,.12),(s*.52,.39,.71,.09,.16),(s*.43,.75,.63,.055,.10)],'body',4,12)
    for j in range(4):
        y=.10+j*.16
        strut('VentRib_'+side+str(j),(s*.555,y,.59),(s*.58,y,.84),.018,.018,'body',2,8)
    loft('HingedFlankShield_'+side,[(s*.60,-.10,.77,.105,.18),(s*.65,.18,.76,.13,.25),(s*.60,.53,.73,.12,.23),(s*.48,.88,.66,.075,.13)],'gate.'+side,1,8)
    for y in (.06,.30,.54):
        strut('ShieldRivet_'+side+str(y),(s*.74,y,.83),(s*.765,y,.83),.026,.026,'gate.'+side,5,8)
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
for side,s in motion.SIDES: bone('gate.'+side,(s*.43,.35,.95),(s*.43,.65,.95),'body')
for k,(h,n,f) in rest.items():
    bone('upper.'+k,h,n,'body'); bone('lower.'+k,n,f,'upper.'+k); bone('foot.'+k,f,motion.add(f,(0,-.2,0)),'lower.'+k)
bpy.ops.object.mode_set(mode='OBJECT')
for o in assets:
    o.parent=rig; g=o.vertex_groups.new(name=o['bone']); g.add(list(range(len(o.data.vertices))),1,'REPLACE'); mod=o.modifiers.new('Deform','ARMATURE'); mod.object=rig
# One skinned renderer and one atlas material, not one draw call per armor fragment.
bpy.ops.object.select_all(action='DESELECT')
for o in assets:o.select_set(True)
bpy.context.view_layer.objects.active=assets[0]; bpy.ops.object.join()
combined=bpy.context.object; combined.name='Bulwark_OneAtlas_SkinnedMesh'; assets=[combined]
# Joining same-material objects can retain duplicate material slots; remap deterministically.
for poly in combined.data.polygons:poly.material_index=0
while len(combined.data.materials)>1:combined.data.materials.pop(index=len(combined.data.materials)-1)
sole_indices={k:[] for k in motion.LEGS}
for k in motion.LEGS:
    gi=combined.vertex_groups['foot.'+k].index
    sole_indices[k]=[v.index for v in combined.data.vertices if any(g.group==gi and g.weight>.99 for g in v.groups)]
for pb in rig.pose.bones: pb.rotation_mode='QUATERNION'
rest_matrices={b.name:b.matrix_local.copy() for b in rig.data.bones}
def translate(z): return Matrix.Translation((0,0,z))
def apply_pose(pose):
    rig.pose.bones['root'].matrix=rest_matrices['root']; z=pose['z']
    rig.pose.bones['body'].matrix=translate(z)@rest_matrices['body']; bpy.context.view_layer.update()
    for name,angle,axis in [('ram',pose['ram'],'X')]+[('gate.'+side,-s*pose['gate'],'Y') for side,s in motion.SIDES]:
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
def validate_frame(label):
    vs=bounds(); min_z=min(v.z for v in vs); clip=[world_to_camera_view(scene,cam,v) for v in vs]
    errors=[]
    if min_z< -P['floor_penetration_limit_m']: errors.append('floor penetration')
    if any(v.z<=0 or min(v.x,v.y)<.035 or max(v.x,v.y)>.965 for v in clip): errors.append('camera clipping')
    return {'errors':errors,'label':label,'min_z':min_z,'screen_min':[min(v.x for v in clip),min(v.y for v in clip)],'screen_max':[max(v.x for v in clip),max(v.y for v in clip)]}
def still(path):
    scene.render.image_settings.file_format='PNG'; scene.render.filepath=str(path); bpy.ops.render.render(write_still=True)
apply_pose(motion.sample('Idle',0)); camera(0)
if args.phase=='static':
    # Early views complete without creating/rendering animation.
    checks=[]
    for i in range(8):
        camera(math.tau*i/8); checks.append(validate_frame('static-'+str(i))); still(review/f'static-{i:02}.png')
    apply_pose(motion.sample('Recover',0)); camera(math.pi*.68); checks.append(validate_frame('open-weakpoint')); still(review/'static-weakpoint-open.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bulwark-static-review.blend'))
    (OUT/'static-checks.json').write_text(json.dumps(checks,indent=2)); sys.exit(1 if any(c['errors'] for c in checks) else 0)
exec(compile((HERE/'animate.py').read_text(),str(HERE/'animate.py'),'exec'))
