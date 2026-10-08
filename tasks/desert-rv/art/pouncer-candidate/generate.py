"""R3 original controlled-section creature. Blender execution is Actions-only.
Blender Z up / forward -Y. Static review is a separate early artifact.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path
import bpy
from mathutils import Vector, Matrix
HERE=Path(__file__).resolve().parent
P=json.loads((HERE/'parameters.json').read_text())
sys.path.insert(0,str(HERE))
from geometry_frames import transport_frames
from topology_report import inspect_mesh
p=argparse.ArgumentParser(); p.add_argument('--output',required=True); p.add_argument('--phase',choices=['static','motion'],required=True); p.add_argument('--scope',choices=['full','death-diagnostic'],default='full')
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]); OUT=Path(args.output).resolve(); OUT.mkdir(parents=True,exist_ok=True)
SCOPE='DEATH_DIAGNOSTIC_NOT_FULL' if args.scope=='death-diagnostic' else 'FULL_CANDIDATE_REVIEW_NOT_APPROVED'
(OUT/'review-scope.json').write_text(json.dumps({'scope':SCOPE,'full_motion_visual_review':'NOT_RUN' if args.scope=='death-diagnostic' else 'REQUIRED','render_fps':30 if args.scope=='death-diagnostic' else 15},indent=2))
print('SCOPE='+SCOPE,flush=True)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
random.seed(P['seed']); scene=bpy.context.scene
scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1; scene.render.fps=P['fps']

def active(o):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active=o

def mesh_object(name,verts,faces):
    me=bpy.data.meshes.new(name); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); scene.collection.objects.link(o); return o

def loft(name, sections, sides=16, power=1):
    """Cross sections (x,y,z,width,height), always ordered along an anatomical chain.
    Frames follow each centerline segment; a single swept tube cannot self-bridge a hock.
    """
    verts=[]; faces=[]
    frames=transport_frames([section[:3] for section in sections])
    for i,(x,y,z,w,h) in enumerate(sections):
        right,up,tangent=(Vector(v) for v in frames[i])
        for j in range(sides):
            a=j*math.tau/sides
            co=math.cos(a); si=math.sin(a)
            sx=math.copysign(abs(co)**power,co); sz=math.copysign(abs(si)**power,si)
            verts.append(Vector((x,y,z))+right*w*sx+up*h*sz)
    for i in range(len(sections)-1):
        for j in range(sides):
            a=i*sides+j; b=i*sides+(j+1)%sides
            faces.append((a,b,b+sides,a+sides))
    faces.append(tuple(reversed(range(sides))))
    faces.append(tuple((len(sections)-1)*sides+j for j in range(sides)))
    o=mesh_object(name,verts,faces)
    active(o); bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT')
    return o

parts=[]
# Deliberately discontinuous slope changes form a shoulder blade, lumbar tuck and flank.
parts.append(loft('Torso',[(0,-.71,.65,.20,.17),(0,-.53,.65,.31,.22),(0,-.32,.65,.355,.235),(0,-.10,.64,.30,.20),(0,.12,.67,.205,.135),(0,.37,.65,.19,.14),(0,.56,.61,.265,.19),(0,.74,.60,.235,.165),(0,.81,.60,.13,.11)],20,.88))
# Broad flat brow -> cheek planes -> narrowed squared muzzle. No animal ear appendages.
parts.append(loft('WedgeCranium',[(0,-.60,.635,.19,.15),(0,-.78,.625,.235,.175),(0,-.91,.625,.285,.155),(0,-1.07,.59,.25,.125),(0,-1.28,.535,.185,.072),(0,-1.36,.53,.135,.055)],16,.65))
# Narrow tapered short tail replaces the old bloated cone.
parts.append(loft('Tail',[(0,.73,.62,.13,.11),(0,.91,.59,.105,.086),(0,1.08,.55,.075,.055),(0,1.24,.50,.027,.024)],12,.9))
leg_chains={}
for side,s in [('L',1),('R',-1)]:
    # Hocks are narrow enough that upper/lower segments cannot fuse into a torus.
    for pre,points,radii in [
        ('fore',[(s*.27,-.38,.69),(s*.335,-.24,.36),(s*.345,-.48,.12),(s*.345,-.60,.075)],[(.14,.17),(.085,.095),(.060,.067),(.095,.045)]),
        ('hind',[(s*.245,.61,.61),(s*.30,.38,.34),(s*.315,.69,.18),(s*.315,.55,.065)],[(.16,.18),(.078,.085),(.045,.050),(.069,.035)])]:
        leg_chains[pre+'.'+side]=[Vector(v) for v in points]
        if pre=='fore':
            sections=[(s*.17,-.38,.73,.115,.135),(s*.27,-.38,.69,.14,.17),(s*.29,-.365,.63,.14,.16),(s*.315,-.32,.55,.13,.14),(s*.33,-.275,.45,.115,.12),(s*.335,-.24,.36,.095,.103),(s*.34,-.34,.265,.086,.091),(s*.345,-.48,.12,.066,.070),(s*.345,-.60,.075,.095,.045)]
        else:
            sections=[(s*.15,.65,.66,.105,.115),(s*.245,.61,.61,.145,.165),(s*.275,.55,.50,.137,.145),(s*.295,.43,.38,.102,.112),(s*.30,.38,.34,.083,.089),(s*.307,.52,.26,.068,.075),(s*.315,.69,.18,.047,.052),(s*.315,.62,.11,.052,.042),(s*.315,.55,.065,.069,.035)]
        parts.append(loft(pre+side,sections,16,.85))
        x,y,z=points[-1]
        parts.append(loft(pre+'Paw'+side,[(x,y+.055,.052,.072,.041),(x,y-.03,.047,.115 if pre=='fore' else .09,.043),(x,y-.13,.037,.11 if pre=='fore' else .085,.037),(x,y-.16,.032,.073,.028)],12,.65))
# Fused upper orbital ledges shade partially inset eyes without separate eyebrow plates.
for side,s in [('L',1),('R',-1)]:
    parts.append(loft('OrbitalLedge'+side,[(s*.19,-1.065,.687,.05,.022),(s*.25,-1.005,.702,.047,.026),(s*.245,-.94,.704,.045,.026),(s*.19,-.895,.688,.048,.022)],12,1))
# The union only closes branch junctions. Much finer voxels and one gentle relax retain planes.
bpy.ops.object.select_all(action='DESELECT')
for o in parts:o.select_set(True)
bpy.context.view_layer.objects.active=parts[0]; bpy.ops.object.join(); body=bpy.context.object; body.name='Pouncer_Skin_LOD0'
rem=body.modifiers.new('BranchJunctionUnion','REMESH'); rem.mode='VOXEL'; rem.voxel_size=.010; rem.use_smooth_shade=True
bpy.ops.object.modifier_apply(modifier=rem.name)
topology_stages={'voxel_union':inspect_mesh(body.data)}
sm=body.modifiers.new('SingleSurfaceRelax','SMOOTH'); sm.factor=.28; sm.iterations=1; bpy.ops.object.modifier_apply(modifier=sm.name)
tri=body.modifiers.new('Triangles','TRIANGULATE'); bpy.ops.object.modifier_apply(modifier=tri.name)
dec=body.modifiers.new('LODBudget','DECIMATE'); dec.ratio=min(1,7900/len(body.data.polygons)); bpy.ops.object.modifier_apply(modifier=dec.name)
topology_stages['decimated_skin']=inspect_mesh(body.data)
(OUT/'topology-stages.json').write_text(json.dumps(topology_stages,indent=2))
for face in body.data.polygons:face.use_smooth=True

def mat(name,color,rough=.8):
    m=bpy.data.materials.new(name); m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF'); bs.inputs['Base Color'].default_value=(*color,1); bs.inputs['Roughness'].default_value=rough; bs.inputs['Specular IOR Level'].default_value=.22
    return m
skin=mat('Sandstone_BaseColorTexture',(.28,.13,.052),.86)
body.data.materials.append(skin)
colors=body.data.color_attributes.new(name='BakedPigment',type='FLOAT_COLOR',domain='POINT')
for v,c in zip(body.data.vertices,colors.data):
    x,y,z=v.co
    # Strong readable leg/ventral and sandstone-dorsal partitions, not pale noisy mud.
    leg=abs(x)>.20 and z<.48
    ventral=(abs(x)<.27 and z<.57 and -.65<y<.7) or (y<-.7 and z<.52)
    base=Vector((.066,.036,.018)) if leg or ventral else Vector((.29,.145,.060))
    if z>.70:base=Vector((.36,.205,.093))
    stripe=math.sin(y*28+z*16+abs(x)*7)
    # Broad irregular stratification with restrained fine grain survives downsampling.
    band=(-.025 if stripe>.55 else .008)+random.uniform(-.007,.007)
    c.color=(*(max(.005,k+band) for k in base),1)
# Bake a real UV base-color image, so GLB and FBX are not dependent on vertex-color shaders.
active(body); bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.smart_project(angle_limit=1.15192,island_margin=.02); bpy.ops.object.mode_set(mode='OBJECT')
image=bpy.data.images.new('Pouncer_BaseColor',width=1024,height=1024,alpha=False)
image.filepath_raw=str(OUT/'pouncer-basecolor.png'); image.file_format='PNG'
nodes=skin.node_tree.nodes; links=skin.node_tree.links
vcol=nodes.new('ShaderNodeVertexColor'); vcol.layer_name='BakedPigment'
emit=nodes.new('ShaderNodeEmission'); links.new(vcol.outputs['Color'],emit.inputs['Color'])
output=nodes.get('Material Output'); links.new(emit.outputs[0],output.inputs['Surface'])
tex=nodes.new('ShaderNodeTexImage'); tex.image=image; nodes.active=tex
scene.render.engine='CYCLES'; scene.cycles.samples=1
bpy.ops.object.bake(type='EMIT',margin=8)
image.save(); image.pack()
links.new(nodes['Principled BSDF'].outputs[0],output.inputs['Surface']); links.new(tex.outputs['Color'],nodes['Principled BSDF'].inputs['Base Color'])
nodes.remove(vcol); nodes.remove(emit)
# Jaw is anatomically separate and truly moves, unlike a painted seam over fused geometry.
jaw=loft('ArticulatedLowerJaw',[(0,-.80,.447,.18,.039),(0,-.98,.426,.212,.045),(0,-1.20,.414,.165,.037),(0,-1.31,.422,.105,.026)],12,.65)
jaw.data.materials.append(mat('VentralJaw',(.10,.052,.025)))
details=[jaw]; jaw['bind_bone']='jaw'
clawmat=mat('Keratin',(.045,.026,.014),.50); eye_mat=mat('AmberEye',(.72,.31,.035),.25); black=mat('MouthAndPupil',(.009,.007,.005),.7)

def ball(name,loc,scale,material,bone,segments=12,rings=8):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=loc)
    o=bpy.context.object; o.name=name; o.scale=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(material); o['bind_bone']=bone; details.append(o); return o
for side,s in [('L',1),('R',-1)]:
    ball('DeepEyeSocket',(s*.259,-.965,.669),(.013,.067,.032),black,'head')
    ball('AmberEye',(s*.271,-.985,.668),(.012,.036,.018),eye_mat,'head')
    ball('SlitPupil',(s*.280,-.99,.668),(.006,.008,.014),black,'head')
    ball('Nostril',(s*.125,-1.329,.56),(.030,.018,.012),black,'head')
    for pre in ('fore','hind'):
        x,y,z=leg_chains[pre+'.'+side][-1]
        for k in (-1,0,1):
            # Actual pointed claw, tapered swept sections rather than rounded toe beads.
            cx=x+k*(.065 if pre=='fore' else .049)
            claw=loft('Claw',[(cx,y-.105,.075,.026,.021),(cx,y-.17,.055,.022,.018),(cx,y-.23,.027,.003,.003)],8,.85)
            claw.data.materials.append(clawmat); claw['bind_bone']=pre+'_paw.'+side; details.append(claw)
    # Upper exposed fangs frame a genuinely openable dark mouth line.
    for fy in (-1.08,-1.23):
        fang=loft('Fang',[(s*.16,fy,.505,.018,.015),(s*.16,fy-.015,.464,.007,.007),(s*.16,fy-.025,.448,.001,.001)],8,1)
        fang.data.materials.append(mat('Tooth'+side+str(fy),(.47,.39,.25),.6)); fang['bind_bone']='head'; details.append(fang)
ball('MouthCavity',(0,-1.08,.463),(.19,.20,.017),black,'head',16,8)
# 47 bones including explicit IK controls, below 55. Deform skeleton remains original.
bpy.ops.object.armature_add(enter_editmode=True); rig=bpy.context.object; rig.name='Pouncer_Rig'; rig.data.edit_bones.remove(rig.data.edit_bones[0]); bones={}
def bone(n,h,t,parent=None,deform=True):
    b=rig.data.edit_bones.new(n); b.head=h; b.tail=t; b.use_deform=deform
    if parent:b.parent=rig.data.edit_bones[parent]
    bones[n]=(Vector(h),Vector(t),deform)
bone('root',(0,0,0),(0,0,.15),deform=False)
bone('visual_body',(0,0,.48),(0,1,.48),'root',False)
bone('pelvis',(0,.58,.61),(0,.3,.65),'visual_body')
bone('spine',(0,.3,.65),(0,-.13,.67),'pelvis')
bone('chest',(0,-.13,.67),(0,-.48,.67),'spine')
bone('neck',(0,-.48,.67),(0,-.80,.625),'chest')
bone('head',(0,-.80,.625),(0,-1.27,.54),'neck')
bone('jaw',(0,-.80,.475),(0,-1.27,.445),'head')
for i in range(3):bone('tail'+str(i),(0,.74+i*.16,.61-i*.045),(0,.90+i*.16,.565-i*.045),'pelvis' if i==0 else 'tail'+str(i-1))
for key,pts in leg_chains.items():
    pre,side=key.split('.'); parent='chest' if pre=='fore' else 'pelvis'
    for j,part in enumerate(('upper','lower','paw')):
        n=pre+'_'+part+'.'+side; bone(n,pts[j],pts[j+1],parent); parent=n
    bone(pre+'_digits.'+side,pts[-1],pts[-1]+Vector((0,-.19,0)),parent)
    for k in (-1,0,1):
        h=pts[-1]+Vector((k*.05,-.08,0)); bone(pre+'_toe'+str(k)+'.'+side,h,h+Vector((0,-.12,0)),pre+'_paw.'+side)
    # Target is at ankle/wrist; articulated paw retains horizontal contact.
    h=pts[2]; bone(pre+'_target.'+side,h,h+Vector((0,.10,0)),'root',False)
    pole=pts[1]+Vector((0,(-1 if pre=='hind' else 1)*.5,0))
    bone(pre+'_pole.'+side,pole,pole+Vector((0,.10,0)),'root',False)
bpy.ops.object.mode_set(mode='OBJECT'); rig.show_in_front=True
# Anatomical region weighting prevents shoulders/head borrowing nearby lower-leg bones.
def distance(p,h,t):
    d=t-h; u=max(0,min(1,(p-h).dot(d)/d.length_squared)); return (p-h-u*d).length
for obj in [body]+details:
    obj.parent=rig; mod=obj.modifiers.new('Skin','ARMATURE'); mod.object=rig
    if obj is not body:
        vg=obj.vertex_groups.new(name=obj['bind_bone']); vg.add(list(range(len(obj.data.vertices))),1,'REPLACE'); continue
    candidates=[(n,h,t) for n,(h,t,d) in bones.items() if d and 'toe' not in n and n!='jaw']
    for n,h,t in candidates:obj.vertex_groups.new(name=n)
    for v in obj.data.vertices:
        x,y,z=v.co; side='L' if x>0 else 'R'
        if abs(x)>.19 and z<.11:
            pre='fore' if y<.05 else 'hind'
            obj.vertex_groups[pre+'_paw.'+side].add([v.index],1.0,'REPLACE')
            continue
        if abs(x)>.19 and z<.48:
            pre='fore' if y<.05 else 'hind'
            eligible=[(n,h,t) for n,h,t in candidates if n.startswith(pre+'_') and n.endswith('.'+side)]
        elif y<-.76:eligible=[(n,h,t) for n,h,t in candidates if n in ('head','neck')]
        elif y>.82:eligible=[(n,h,t) for n,h,t in candidates if n.startswith('tail') or n=='pelvis']
        else:eligible=[(n,h,t) for n,h,t in candidates if n in ('pelvis','spine','chest','neck') or (n.endswith('.'+side) and '_upper' in n)]
        best=sorted((distance(v.co,h,t),n) for n,h,t in eligible)[:4]; ws=[math.exp(-d*32) for d,n in best]; total=sum(ws)
        for (_,n),w in zip(best,ws):obj.vertex_groups[n].add([v.index],w/total,'REPLACE')
# IK only used while authoring; baked evaluated poses become export actions.
for key,pts in leg_chains.items():
    pre,side=key.split('.')
    pb=rig.pose.bones[pre+'_lower.'+side]; con=pb.constraints.new('IK'); con.name='AuthoringFootLock'; con.target=rig; con.subtarget=pre+'_target.'+side; con.pole_target=rig; con.pole_subtarget=pre+'_pole.'+side; con.chain_count=2; con.use_stretch=False; con.influence=0
    # Pole angle is calibrated in Actions from resulting joint orientation below.
    con.pole_angle=0
rig['candidate_status']='R3_unreviewed'; rig['root_motion']=False
rig['attack_interrupt_contract']='Current BeastActor uses CrossFade normalized 0.12, about 0.096s from 0.8s Attack. Current-duration and proposed 0.24s fixed-time comparison clips are evidence only. Actual Unity collision/transition integration remains unverified.'

def setup_stage():
    scene.render.engine='CYCLES'; scene.cycles.samples=16; scene.cycles.use_denoising=True
    scene.render.resolution_x=scene.render.resolution_y=720; scene.render.resolution_percentage=100
    scene.world.color=(.16,.16,.16); scene.view_settings.view_transform='AgX'
    bpy.ops.mesh.primitive_plane_add(size=200); floor=bpy.context.object; floor.name='ReviewFloor'; floor.data.materials.append(mat('NeutralFloor',(.16,.16,.16)))
    for name,loc,power,size in [('Key',(-3,-4,5),600,4),('Fill',(4,-1,3),280,4),('Rim',(0,4,4),400,3)]:
        bpy.ops.object.light_add(type='AREA',location=loc); l=bpy.context.object; l.name=name; l.data.energy=power; l.data.shape='DISK'; l.data.size=size; l.rotation_euler=(Vector((0,0,.45))-l.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add(); cam=bpy.context.object; cam.data.type='ORTHO'; cam.data.ortho_scale=3.75; scene.camera=cam
    return cam

def camera_at(cam,angle):
    cam.location=(6*math.sin(angle),-6*math.cos(angle),2.4); cam.rotation_euler=(Vector((0,-.12,.40))-cam.location).to_track_quat('-Z','Y').to_euler()

if args.phase=='static':
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'pouncer-static-source.blend'))
    cam=setup_stage(); review=OUT/'review'; review.mkdir(exist_ok=True); scene.render.image_settings.file_format='PNG'
    for i in range(8):
        camera_at(cam,i*math.tau/8); scene.render.filepath=str(review/f'turntable-{i:02}.png'); bpy.ops.render.render(write_still=True)
    (OUT/'static-review.json').write_text(json.dumps({'candidate':P['candidate'],'visual_approval':False,'source':'original controlled cross sections','material':'UV PNG BaseColor standard Principled PBR','private_references_uploaded':False,'topology':topology_stages['decimated_skin'],'render_triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in [body]+details),'rig_bones':len(rig.data.bones)},indent=2))
    sys.exit(0)

# Actions and motion evidence live in a second script to make the staging split explicit.
exec(compile((HERE/'animate.py').read_text(),str(HERE/'animate.py'),'exec'))
