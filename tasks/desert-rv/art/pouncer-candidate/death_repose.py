"""Actions-only technical-first reauthoring from the exact examined native baseline.
No mesh/weight edits. No render is possible until the generated technical gate passes.
"""
import argparse,hashlib,json,math,struct,sys
from pathlib import Path
import bpy
from mathutils import Vector,Matrix,Quaternion
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from death_anatomy import AnatomicalSupport
from export_timing import inspect_glb,inspect_fbx
P=json.loads((HERE/'parameters.json').read_text());BASE=json.loads((HERE/'death-baseline.json').read_text())
a=argparse.ArgumentParser();a.add_argument('--phase',choices=['technical','opaque'],required=True);a.add_argument('--input',required=True);a.add_argument('--output',required=True)
args=a.parse_args(sys.argv[sys.argv.index('--')+1:]);OUT=Path(args.output).resolve();OUT.mkdir(parents=True,exist_ok=True)
source=Path(args.input).resolve();digest=hashlib.sha256(source.read_bytes()).hexdigest()
if args.phase=='technical' and digest!=BASE['blend_sha256']:raise RuntimeError('Pinned native baseline hash mismatch')
if args.phase=='opaque':
    gate=json.loads((OUT/'technical-gate.json').read_text())
    if gate['status']!='DEATH_TECHNICAL_PASS_NOT_FULL' or digest!=gate['candidate_blend_sha256']:raise RuntimeError('Opaque render requires exact passing technical candidate')
bpy.ops.wm.open_mainfile(filepath=str(source))
scene=bpy.context.scene;rig=bpy.data.objects['Pouncer_Rig'];body=bpy.data.objects['Pouncer_Skin_LOD0'];meshes=[o for o in scene.objects if o.type=='MESH']
for track in rig.animation_data.nla_tracks:track.mute=True
if tuple(bpy.app.version)!=(4,2,3):raise RuntimeError('Expected official Blender 4.2.3')
if scene.render.fps!=100 or set(a.name for a in bpy.data.actions)!=set(P['clips']):raise RuntimeError('Baseline clip/fps contract changed')
if any(pb.constraints for pb in rig.pose.bones):raise RuntimeError('Baseline must contain baked, unconstrained actions')
anatomy=AnatomicalSupport(body,rig)

def geometry_hash():
    h=hashlib.sha256()
    for obj in sorted(meshes,key=lambda o:o.name):
        h.update(obj.name.encode())
        for v in obj.data.vertices:
            h.update(struct.pack('<3f',*v.co))
            for g in v.groups:h.update(struct.pack('<If',g.group,g.weight))
        for face in obj.data.polygons:h.update(json.dumps(list(face.vertices)).encode())
        for material in obj.data.materials:h.update(material.name.encode())
    for bone in rig.data.bones:h.update(json.dumps([bone.name,list(bone.head_local),list(bone.tail_local)]).encode())
    return h.hexdigest()

def action_hash(action):
    return hashlib.sha256(json.dumps([(f.data_path,f.array_index,[(list(k.co),k.interpolation) for k in f.keyframe_points]) for f in action.fcurves],sort_keys=True).encode()).hexdigest()

def evaluated():
    deps=bpy.context.evaluated_depsgraph_get();low=None;body_coords=None
    for obj in meshes:
        ev=obj.evaluated_get(deps);me=ev.to_mesh();coords=[ev.matrix_world@v.co for v in me.vertices];index=min(range(len(coords)),key=lambda i:coords[i].z)
        if low is None or coords[index].z<low['z']:
            names={g.index:g.name for g in obj.vertex_groups};low={'z':coords[index].z,'mesh':obj.name,'vertex':index,'world_xyz_m':list(coords[index]),'weights':{names[g.group]:g.weight for g in obj.data.vertices[index].groups}}
        if obj==body:body_coords=coords
        ev.to_mesh_clear()
    return low,body_coords

def write_pose_key(action,frame,basis):
    rig.animation_data.action=action
    for pb in rig.pose.bones:
        pb.rotation_mode='XYZ';pb.matrix_basis=basis[pb.name]
        for path in ('location','rotation_euler','scale'):pb.keyframe_insert(path,frame=frame,group=pb.name)

if args.phase=='technical':
    geometry_before=geometry_hash();other_before={n:action_hash(bpy.data.actions[n]) for n in P['clips'] if n!='Death'}
    original=bpy.data.actions['Death'];poses=[];placement=[];end=181
    for frame in range(1,end+1):
        rig.animation_data.action=original;scene.frame_set(frame);basis={pb.name:pb.matrix_basis.copy() for pb in rig.pose.bones};rig.animation_data.action=None
        for pb in rig.pose.bones:pb.matrix_basis=basis[pb.name]
        u=(frame-1)/(end-1);t=max(0,min(1,(u-.10)/.70));q=t*t*(3-2*t)
        neck=rig.pose.bones['neck'];nq=neck.rotation_euler.to_quaternion() @ Quaternion((1,0,0),BASE['neck_local_delta_x_radians']*q) @ Quaternion((0,0,1),BASE['neck_local_delta_z_radians']*q);neck.rotation_euler=nq.to_euler('XYZ')
        bpy.context.view_layer.update()
        # Rigid-body placement about a documented world pivot. It changes visual_body,
        # not mesh vertices, limb roots, gameplay root or the already-baked joint lengths.
        origin=Vector((.1,0,.25));R=Matrix.Rotation(math.radians(BASE['extra_global_pitch_degrees'])*q,4,'X');T=Matrix.Translation(origin) @ R @ Matrix.Translation(-origin)
        pb=rig.pose.bones['visual_body'];desired=T@pb.matrix
        pb.matrix_basis=pb.bone.matrix_local.inverted()@pb.parent.bone.matrix_local@pb.parent.matrix.inverted()@desired
        bpy.context.view_layer.update();low,_=evaluated()
        # Gravity placement uses the real all-mesh support envelope. Unlike the former
        # inner-trunk rule, it never requires exterior shoulder/hip meat to enter the floor.
        dz=.001-low['z'];desired=Matrix.Translation((0,0,dz))@pb.matrix
        pb.matrix_basis=pb.bone.matrix_local.inverted()@pb.parent.bone.matrix_local@pb.parent.matrix.inverted()@desired
        bpy.context.view_layer.update();poses.append({bone.name:bone.matrix_basis.copy() for bone in rig.pose.bones});placement.append({'seconds':(frame-1)/100,'extra_pitch_degrees':BASE['extra_global_pitch_degrees']*q,'physical_support_translation_z':dz,'visual_world_origin':list(pb.matrix.translation)})
    original.name='RetiredBaselineDeath';new=bpy.data.actions.new('Death');new.use_fake_user=True
    for frame,basis in enumerate(poses,1):write_pose_key(new,frame,basis)
    for fc in new.fcurves:
        for k in fc.keyframe_points:k.interpolation='LINEAR'
    for track in rig.animation_data.nla_tracks:
        if track.name=='Death':
            for strip in list(track.strips):track.strips.remove(strip)
            track.strips.new('Death',1,new);track.mute=True
    rig.animation_data.action=new;bpy.data.actions.remove(original)
    rows=[];roots=[]
    # Re-evaluate baked poses at 200 Hz, including mid-keyframe samples.
    for sample in range(361):
        frame=1+sample*.5;scene.frame_set(int(frame),subframe=frame-int(frame));low,_=evaluated();rows.append({'seconds':sample/200,**low});root=rig.pose.bones['root'];roots.append(max(root.location.length,root.rotation_euler.to_quaternion().angle))
    scene.frame_set(181);low,coords=evaluated();patches=anatomy.inspect(coords)
    from death_support import TrunkSupport
    former_filter_report=TrunkSupport(body).inspect(coords)
    errors=[];worst=min(rows,key=lambda r:r['z'])
    if worst['z']<-.004:errors.append('All-mesh Death penetration exceeds unchanged 4mm')
    if max(roots)>1e-6:errors.append('Gameplay root moved')
    for name in ('shoulder','pelvis'):
        region=patches[name]
        if abs(region['minimum_z'])>.012 or region['q05_z']>.040 or region['vertices_within_30mm']<max(3,math.ceil(region['vertices']*.02)):errors.append(name+' anatomical support patch is insufficient')
    if patches['face']['minimum_z']>.030 or patches['face']['vertices_within_35mm']<4:errors.append('Face remains suspended rather than relaxed near support')
    max_step=max((Vector(b['visual_world_origin'])-Vector(a['visual_world_origin'])).length for a,b in zip(placement,placement[1:]))
    if max_step>.03:errors.append('Rigid placement jumps more than30mm in10ms; continuity not accepted')
    final_basis={pb.name:pb.matrix_basis.copy() for pb in rig.pose.bones};scene.frame_set(176)
    hold=max(max(abs(final_basis[pb.name][i][j]-pb.matrix_basis[i][j]) for i in range(4) for j in range(4)) for pb in rig.pose.bones)
    if hold>1e-5:errors.append('Death final hold moves')
    if geometry_before!=geometry_hash():errors.append('Geometry/weights/rig changed')
    if other_before!={n:action_hash(bpy.data.actions[n]) for n in other_before}:errors.append('A non-Death action changed')
    # Export all seven exact clips, with zero-based serialized timing as before.
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes+[rig]:obj.select_set(True)
    bpy.context.view_layer.objects.active=rig
    for name in P['clips']:
        for fc in bpy.data.actions[name].fcurves:
            for k in fc.keyframe_points:k.co.x-=1;k.handle_left.x-=1;k.handle_right.x-=1
    for track in rig.animation_data.nla_tracks:
        strip=track.strips[0];strip.action_frame_start=0;strip.action_frame_end=P['clips'][track.name]*100;strip.frame_start=0;strip.frame_end=P['clips'][track.name]*100;track.mute=False
    rig.animation_data.action=None
    bpy.ops.export_scene.gltf(filepath=str(OUT/'pouncer-candidate.glb'),export_format='GLB',use_selection=True,export_animation_mode='NLA_TRACKS',export_nla_strips=True,export_anim_slide_to_zero=True,export_yup=True)
    for track in rig.animation_data.nla_tracks:track.mute=True
    bpy.ops.export_scene.fbx(filepath=str(OUT/'pouncer-candidate.fbx'),use_selection=True,add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=True,bake_anim_use_nla_strips=False,axis_forward='-Z',axis_up='Y',path_mode='COPY',embed_textures=True)
    for name in P['clips']:
        for fc in bpy.data.actions[name].fcurves:
            for k in fc.keyframe_points:k.co.x+=1;k.handle_left.x+=1;k.handle_right.x+=1
    for track in rig.animation_data.nla_tracks:
        strip=track.strips[0];strip.action_frame_start=1;strip.action_frame_end=1+P['clips'][track.name]*100;strip.frame_start=1;strip.frame_end=1+P['clips'][track.name]*100
    serialized={format:reader(OUT/('pouncer-candidate.'+format)) for format,reader in [('glb',inspect_glb),('fbx',inspect_fbx)]}
    for format,times in serialized.items():
        if set(times)!=set(P['clips']):errors.append(format+' exported clip set changed')
        for name,duration in P['clips'].items():
            if name not in times or abs(times[name]['start'])>1e-6 or abs(times[name]['end']-duration)>1e-6:errors.append(format+' '+name+' timing mismatch')
    rig.animation_data.action=new;scene.frame_set(181)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'pouncer-candidate.blend'))
    report={'scope':'DEATH_TECHNICAL_FIRST_NOT_FULL','status':'DEATH_TECHNICAL_PASS_NOT_FULL' if not errors else 'DEATH_TECHNICAL_FAIL','errors':errors,'visual_review':'NOT_RUN','visual_approval':False,'definition_change':BASE['definition_change'],'baseline':BASE,'geometry_weights_rig_unchanged':geometry_before==geometry_hash(),'non_death_actions_unchanged':other_before=={n:action_hash(bpy.data.actions[n]) for n in other_before},'maximum_penetration_m':max(0,-worst['z']),'worst_sample':worst,'end_minimum_z':rows[-1]['z'],'support_regions':patches,'former_trunk_only_filter_reported_not_used':former_filter_report,'max_visual_translation_per10ms':max_step,'final_hold_error':hold,'serialized_times':serialized,'candidate_blend_sha256':hashlib.sha256((OUT/'pouncer-candidate.blend').read_bytes()).hexdigest()}
    (OUT/'technical-gate.json').write_text(json.dumps(report,indent=2));(OUT/'death-200hz-samples.json').write_text(json.dumps(rows,indent=2));(OUT/'death-placement.json').write_text(json.dumps(placement,indent=2))
    print(json.dumps({'status':report['status'],'maximum_penetration_m':report['maximum_penetration_m'],'worst_seconds':worst['seconds'],'errors':errors}),flush=True)
    if errors:raise RuntimeError('; '.join(errors))
else:
    # Exactly four opaque stills, only after the prior technical pass. No full video.
    scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True;scene.render.resolution_x=960;scene.render.resolution_y=540;scene.render.resolution_percentage=100;scene.world.color=(.16,.16,.16);scene.view_settings.view_transform='AgX'
    bpy.ops.mesh.primitive_plane_add(size=200);ground=bpy.context.object;m=bpy.data.materials.new('ReviewNeutral');m.diffuse_color=(.16,.16,.16,1);ground.data.materials.append(m)
    for loc,power in [((-3,-4,5),600),((4,-1,3),280),((0,4,4),400)]:
        bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.size=4;o.rotation_euler=(Vector((0,0,.4))-o.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=3.6;scene.camera=cam
    for label,seconds,index in [('rest03',1.8,3),('rest07',1.8,7),('mid102',1.02,2),('mid135',1.35,2)]:
        rig.animation_data.action=bpy.data.actions['Death'];scene.frame_set(1+round(seconds*100));angle=index*math.tau/8;cam.location=(6*math.sin(angle),-6*math.cos(angle),2.4);cam.rotation_euler=(Vector((0,-.12,.4))-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(OUT/f'opaque-{label}.png');bpy.ops.render.render(write_still=True)
    (OUT/'opaque-scope.json').write_text(json.dumps({'scope':'FOUR_OPAQUE_STILLS_AFTER_TECHNICAL_PASS_NOT_FULL','visual_approval':False},indent=2))
