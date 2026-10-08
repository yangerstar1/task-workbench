"""Executed after R2 sculpt build. IK controls are authoring-only; export is baked."""
import collections
import struct
from death_contact import DeathContactSolver
death_solver=DeathContactSolver(body,details,rig,leg_chains,P['clips']['Death'])

# Calibrate each original limb's pole angle against its known rest elbow/knee.
for key,pts in leg_chains.items():
    pre,side=key.split('.'); con=rig.pose.bones[pre+'_lower.'+side].constraints['AuthoringFootLock']; con.influence=1
    best=(1e9,0)
    for index in range(16):
        angle=index*math.tau/16; con.pole_angle=angle; bpy.context.view_layer.update()
        error=(rig.pose.bones[pre+'_upper.'+side].tail-pts[1]).length
        if error<best[0]:best=(error,angle)
    con.pole_angle=best[1]; con.influence=0


def set_target(key,position):
    pre,side=key.split('.'); pb=rig.pose.bones[pre+'_target.'+side]
    # Targets have +Y local axes matching world, parent root is stationary.
    pb.location=Vector(position)-bones[pb.name][0]


def bounds(meshes=None):
    deps=bpy.context.evaluated_depsgraph_get(); coords=[]
    for obj in meshes or [body]+details:
        ev=obj.evaluated_get(deps); me=ev.to_mesh(); coords.extend(ev.matrix_world@v.co for v in me.vertices); ev.to_mesh_clear()
    return {'min_z':min(v.z for v in coords),'max_z':max(v.z for v in coords),'min_y':min(v.y for v in coords),'max_y':max(v.y for v in coords)}


def author_pose(name,u):
    for pb in rig.pose.bones:
        pb.rotation_mode='XYZ'; pb.rotation_euler=(0,0,0); pb.location=(0,0,0); pb.scale=(1,1,1)
    for key in leg_chains:
        pre,side=key.split('.'); rig.pose.bones[pre+'_lower.'+side].constraints['AuthoringFootLock'].influence=1 if name in ('Idle','Walk','Windup','Recover','Hit','Death') or (name=='Attack' and (u<.12 or u>.82)) else 0
    def rot(n,xyz):rig.pose.bones[n].rotation_euler=xyz
    visual=rig.pose.bones['visual_body']; flight=False
    if name=='Idle':
        rot('chest',(.010*math.sin(math.tau*u),0,0)); rot('head',(0,.018*math.sin(math.tau*u),0))
    elif name=='Walk':
        cycle=P['gait']['cycle_seconds']; speed=2.7; duty=.5; travel=speed*cycle*duty
        visual.location.z=-.02+.012*math.cos(4*math.pi*u)
        rot('spine',(0,.017*math.sin(math.tau*u),0))
        for key,pts in leg_chains.items():
            pre,side=key.split('.'); offset=0 if key in ('fore.L','hind.R') else .5
            phase=(u+offset)%1; center=-.38 if pre=='fore' else .60
            target=pts[2].copy()
            if phase<duty:
                target.y=center-travel/2+speed*phase*cycle
            else:
                t=(phase-duty)/(1-duty); eased=t*t*(3-2*t)
                target.y=center+travel/2-travel*eased; target.z+=.12*math.sin(math.pi*t)
            set_target(key,target)
    elif name=='Windup':
        q=u*u*(3-2*u); visual.location=(0,.105*q,-.14*q)
        rot('neck',(-.15*q,0,0)); rot('head',(.10*q,0,0))
    elif name=='Attack':
        if u<.12:
            q=1-u/.12; visual.location=(0,.105*q,-.14*q); rot('neck',(-.15*q,0,0)); rot('head',(.10*q,0,0))
        elif u<.82:
            t=(u-.12)/.70; hump=math.sin(math.pi*t)
            visual.location=(0,-.18*hump,.27*hump)
            rot('visual_body',(-.12*math.sin(math.tau*t),0,0)); flight=True
            rot('neck',(.14*hump,0,0)); rot('head',(-.16*hump,0,0)); rot('jaw',(.60*math.sin(math.pi*min(1,t*1.5)),0,0))
            for side in ('L','R'):
                rot('fore_upper.'+side,(-.32*hump,0,0)); rot('fore_lower.'+side,(.15*hump,0,0)); rot('hind_upper.'+side,(.35*hump,0,0)); rot('hind_lower.'+side,(-.40*hump,0,0))
        else:
            t=(u-.82)/.18; compression=.07*math.sin(math.pi*t)
            visual.location=(0,0,-compression); rot('neck',(.06*math.sin(math.pi*t),0,0))
    elif name=='Recover':
        # Stronger absorbing compression, restrained head shake, stable finish.
        q=math.sin(math.pi*(u**.65))*(1-.30*u)
        visual.location=(0,.045*q,-.12*q)
        rot('head',(.17*q,0,.12*math.sin(math.tau*u)*q)); rot('neck',(-.10*q,0,0))
    elif name=='Hit':
        q=math.sin(math.pi*u); visual.location=(.055*q,.085*q,-.045*q)
        rot('head',(-.20*q,0,.23*q)); rot('neck',(-.10*q,0,-.10*q))
    elif name=='Death':
        t=min(1,u/.76); q=t*t*(3-2*t)
        visual.location=(.12*q,0,-.24*q); rot('visual_body',(.04*q,1.48*q,0))
        rot('head',(.16*q,0,.09*q)); rot('neck',(.09*q,0,0))
        # Each relaxed leg receives its own reachable grounded endpoint.
        # The upper-side legs tuck closer; lower-side legs extend outward on the floor.
        for key,pts in leg_chains.items():
            pre,side=key.split('.')
            endpoint=pts[2].copy(); endpoint.x=-.18 if side=='L' else .06
            endpoint.y=(-.60 if side=='L' else -.78) if pre=='fore' else (.50 if side=='L' else .35)
            set_target(key,pts[2].lerp(endpoint,q))
            pole=rig.pose.bones[pre+'_pole.'+side]
            rest=bones[pole.name][0]; target=Vector((-.10,-.20 if pre=='fore' else .80,.22))
            pole.location=rest.lerp(target,q)-rest
    for i in range(3):rot('tail'+str(i),(0,0,-.09 if name=='Death' else .02*math.sin(u*math.tau+i*.4)))
    bpy.context.view_layer.update()
    # Keep IK-controlled paws at their rest world orientation, never paddle with the wrist.
    for key in leg_chains:
        pre,side=key.split('.'); con=rig.pose.bones[pre+'_lower.'+side].constraints['AuthoringFootLock']
        if con.influence:
            paw=rig.pose.bones[pre+'_paw.'+side]; world_rest=rig.data.bones[paw.name].matrix_local.to_3x3().to_4x4(); world_rest.translation=paw.head; paw.matrix=world_rest
    bpy.context.view_layer.update()
    if name=='Death':
        death_solver.solve(u)
        return flight
    b=bounds()
    # Explicit collision correction keeps the 4mm rejection threshold unchanged.
    if b['min_z']<-.001:
        correction=-b['min_z']
        if not flight:
            for key in leg_chains:
                pre,side=key.split('.'); rig.pose.bones[pre+'_target.'+side].location.z+=correction
        if name!='Death':visual.location.z+=correction
        else:
            # Relax limb bend upward if needed while the torso remains side-supported.
            for key in leg_chains:
                pre,side=key.split('.'); rig.pose.bones[pre+'_pole.'+side].location.z+=correction*2
        bpy.context.view_layer.update()
    return flight

# Bake evaluated local matrices, NOT raw IK rotation channels.
clips={}; gait_samples=[]; motion_bounds={}; authored_poses={}
for name,seconds in P['clips'].items():
    end=round(seconds*P['fps'])+1
    clips[name]={'frame_start':1,'frame_end':end,'seconds_requested':seconds,'seconds_sampled':(end-1)/P['fps'],'loop':name in ('Idle','Walk'),'hold_last_pose':name=='Death'}
    matrices=[]; pose_bounds=[]
    rig.animation_data_clear()
    for frame in range(1,end+1):
        u=(frame-1)/(end-1); author_pose(name,u)
        matrices.append({pb.name:pb.matrix.copy() for pb in rig.pose.bones})
        pose_bounds.append(bounds())
        if name=='Walk':
            row={'frame':frame,'time':(frame-1)/P['fps'],'feet':{}}
            for key in leg_chains:
                pre,side=key.split('.'); offset=0 if key in ('fore.L','hind.R') else .5; phase=(u+offset)%1
                paw=rig.pose.bones[pre+'_paw.'+side]
                row['feet'][key]={'stance':phase<.5,'ankle':list(paw.head),'paw_tip':list(paw.tail)}
            gait_samples.append(row)
    motion_bounds[name]=pose_bounds; authored_poses[name]=matrices
    for pb in rig.pose.bones:
        for con in pb.constraints:con.influence=0
    action=bpy.data.actions.new(name); action.use_fake_user=True; rig.animation_data_create(); rig.animation_data.action=action
    # Parents first: assigning world matrices computes correct local export rotations.
    for frame,pose in enumerate(matrices,1):
        for pb in rig.pose.bones:
            if pb.parent:
                pb.matrix_basis=pb.bone.matrix_local.inverted() @ pb.parent.bone.matrix_local @ pose[pb.parent.name].inverted() @ pose[pb.name]
            else:
                pb.matrix_basis=pb.bone.matrix_local.inverted() @ pose[pb.name]
            pb.keyframe_insert('location',frame=frame,group=pb.name); pb.keyframe_insert('rotation_euler',frame=frame,group=pb.name); pb.keyframe_insert('scale',frame=frame,group=pb.name)
    for fc in action.fcurves:
        for kp in fc.keyframe_points:kp.interpolation='LINEAR'
(OUT/'death-contact-solver.json').write_text(json.dumps(death_solver.rows,indent=2))
# Remove authoring constraints completely before export, preventing doubled IK evaluation.
for pb in rig.pose.bones:
    for con in list(pb.constraints):pb.constraints.remove(con)
# Probe the actual quaternion crossfade to Recover BEFORE exporting Attack.
# Minimal flight clearance is baked into the source clip, not added to review images.
def local_snapshot():
    return {pb.name:(pb.location.copy(),pb.rotation_euler.to_quaternion(),pb.scale.copy()) for pb in rig.pose.bones}
def apply_mix(start,target,w):
    rig.animation_data.action=None
    for n,(loc,quat,scale) in start.items():
        pb=rig.pose.bones[n]; pb.location=loc.lerp(target[n][0],w); pb.rotation_euler=quat.slerp(target[n][1],w).to_euler('XYZ'); pb.scale=scale.lerp(target[n][2],w)
    bpy.context.view_layer.update()
# Target Recover continues advancing while crossfade is active, as it does in Animator.
probe_targets=[]
for duration in (.12*clips['Attack']['seconds_sampled'],.24):
    for w in (.10,.20,.30,.40,.50,.60,.70,.80,.90,.95,.98):
        target_frame=1+duration*w*P['fps']; rig.animation_data.action=bpy.data.actions['Recover']; scene.frame_set(int(target_frame),subframe=target_frame-int(target_frame))
        probe_targets.append((w,local_snapshot()))
attack_end=clips['Attack']['frame_end']; raw_lifts=[]; clearance_rows=[]
for frame in range(1,attack_end+1):
    rig.animation_data.action=bpy.data.actions['Attack']; scene.frame_set(frame); source=local_snapshot(); required=0; lowest=1
    for w,target in probe_targets:
        apply_mix(source,target,w); z=bounds()['min_z']; lowest=min(lowest,z)
        if z<.001:required=max(required,(.001-z)/(1-w))
    u=(frame-1)/(attack_end-1)
    lift=min(.16,required) if .12<u<.82 else 0
    raw_lifts.append(lift); clearance_rows.append({'frame':frame,'unmodified_crossfade_min_z':lowest,'required_lift_m':required,'added_flight_clearance_m':lift})
# A short upper envelope keeps the necessary lift smooth without reducing its safety margin.
for index,row in enumerate(clearance_rows):
    u=index/(attack_end-1)
    lift=max(raw_lifts[j]*max(0,1-abs(index-j)/3) for j in range(max(0,index-2),min(attack_end,index+3))) if .12<u<.82 else 0
    rig.animation_data.action=bpy.data.actions['Attack']; scene.frame_set(index+1)
    rig.pose.bones['visual_body'].location.z+=lift
    rig.pose.bones['visual_body'].keyframe_insert('location',frame=index+1,group='visual_body')
    row['added_flight_clearance_m']=lift
# Verify the adjusted source clip across every frame and quaternion blend fraction.
for row in clearance_rows:
    rig.animation_data.action=bpy.data.actions['Attack']; scene.frame_set(row['frame']); source=local_snapshot(); minimum=1
    for w,target in probe_targets:
        apply_mix(source,target,w); minimum=min(minimum,bounds()['min_z'])
    row['verified_crossfade_min_z_after_lift']=minimum
(OUT/'transition-clearance.json').write_text(json.dumps({'method':'actual source quaternion crossfade; added clearance baked before export','maximum_added_lift_m':max(r['added_flight_clearance_m'] for r in clearance_rows),'frames':clearance_rows,'Unity_runtime_verified':False},indent=2))
rig.animation_data.action=bpy.data.actions['Idle']; scene.frame_set(1)
for name in clips:
    track=rig.animation_data.nla_tracks.new(); track.name=name; track.strips.new(name,1,bpy.data.actions[name]); track.mute=True
bpy.ops.object.select_all(action='DESELECT')
for obj in [body,rig]+details:obj.select_set(True)
bpy.context.view_layer.objects.active=rig
# Export exactly zero-based ranges. 100fps expresses .78/.28/.8/1.3 exactly.
for name in clips:
    for fc in bpy.data.actions[name].fcurves:
        for key in fc.keyframe_points:key.co.x-=1;key.handle_left.x-=1;key.handle_right.x-=1
for track in rig.animation_data.nla_tracks:
    strip=track.strips[0]; strip.action_frame_start=0; strip.action_frame_end=clips[track.name]['frame_end']-1;strip.frame_start=0;strip.frame_end=clips[track.name]['frame_end']-1
rig.animation_data.action=None
for tr in rig.animation_data.nla_tracks:tr.mute=False
bpy.ops.export_scene.gltf(filepath=str(OUT/'pouncer-candidate.glb'),export_format='GLB',use_selection=True,export_animations=True,export_animation_mode='NLA_TRACKS',export_nla_strips=True,export_yup=True,export_anim_slide_to_zero=True)
for tr in rig.animation_data.nla_tracks:tr.mute=True
bpy.ops.export_scene.fbx(filepath=str(OUT/'pouncer-candidate.fbx'),use_selection=True,add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=True,bake_anim_use_nla_strips=False,axis_forward='-Z',axis_up='Y',apply_unit_scale=True,path_mode='COPY',embed_textures=True)
# Restore authoring frame indices after both serialized exports.
for name in clips:
    for fc in bpy.data.actions[name].fcurves:
        for key in fc.keyframe_points:key.co.x+=1;key.handle_left.x+=1;key.handle_right.x+=1
for track in rig.animation_data.nla_tracks:
    strip=track.strips[0];strip.action_frame_start=1;strip.action_frame_end=clips[track.name]['frame_end'];strip.frame_start=1;strip.frame_end=clips[track.name]['frame_end']
rig.animation_data.action=bpy.data.actions['Idle']; scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'pouncer-candidate.blend'))
(OUT/'clip-manifest.json').write_text(json.dumps(clips,indent=2)); (OUT/'parameters.json').write_text(json.dumps(P,indent=2)); (OUT/'gait-samples.json').write_text(json.dumps(gait_samples,indent=2))
exec(compile((HERE/'validate_asset.py').read_text(),str(HERE/'validate_asset.py'),'exec'))
cam=setup_stage(); camera_at(cam,math.pi/2); cam.data.ortho_scale=4.35
# Landscape 16:9 and 4.35m field fully contain head at maximum forward lunge.
scene.render.resolution_x=960; scene.render.resolution_y=540
review=OUT/'review'; review.mkdir(exist_ok=True); scene.render.image_settings.file_format='PNG'
from bpy_extras.object_utils import world_to_camera_view
render_manifest=[]; framing_failures=[]
render_clips={'Death':clips['Death']} if args.scope=='death-diagnostic' else {**clips,**preview_clips}
render_fps=30 if args.scope=='death-diagnostic' else 15
for name,meta in render_clips.items():
    rig.animation_data.action=bpy.data.actions[name]; folder=review/name; folder.mkdir(exist_ok=True)
    frames=sorted({1+round(i*P['fps']/render_fps) for i in range(math.ceil((meta['frame_end']-1)/P['fps']*render_fps)+1) if 1+round(i*P['fps']/render_fps)<=meta['frame_end']})
    if frames[-1]!=meta['frame_end']:frames.append(meta['frame_end'])
    for index,frame in enumerate(frames):
        scene.frame_set(frame)
        deps=bpy.context.evaluated_depsgraph_get(); screen=[]
        for obj in [body]+details:
            ev=obj.evaluated_get(deps)
            screen.extend(world_to_camera_view(scene,cam,ev.matrix_world@Vector(c)) for c in ev.bound_box)
        framing={'min_x':min(v.x for v in screen),'max_x':max(v.x for v in screen),'min_y':min(v.y for v in screen),'max_y':max(v.y for v in screen)}
        if min(framing['min_x'],framing['min_y'])<.02 or max(framing['max_x'],framing['max_y'])>.98:framing_failures.append({'clip':name,'frame':frame,'bounds':framing})
        render_manifest.append({'clip':name,'png':f'{name}/{index:04}.png','source_frame':frame,'source_time_seconds':(frame-1)/P['fps'],'screen_bounds':framing})
        scene.render.filepath=str(folder/f'{index:04}.png'); bpy.ops.render.render(write_still=True)
if args.scope=='death-diagnostic':
    # Near-ground witness views cover the actual R3 failure interval, not only a rest pose.
    cam.location=(6,-.12,1.2);cam.rotation_euler=(Vector((0,-.12,.22))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=3.2
    rig.animation_data.action=bpy.data.actions['Death']
    for ms in (750,900,950,1000,1070,1150,1200,1300,1600,1800):
        scene.frame_set(1+round(ms/1000*P['fps']));scene.render.filepath=str(review/f'death-near-{ms:04}.png');bpy.ops.render.render(write_still=True)
    cam.data.ortho_scale=4.35
# Two opposing three-quarter death stills expose torso support and relaxed limbs.
rig.animation_data.action=bpy.data.actions['Death']; scene.frame_set(clips['Death']['frame_end'])
for index in (3,7):
    camera_at(cam,index*math.tau/8); scene.render.filepath=str(review/f'death-rest-{index:02}.png'); bpy.ops.render.render(write_still=True)
(OUT/'render-manifest.json').write_text(json.dumps(render_manifest,indent=2))
report=json.loads((OUT/'validation.json').read_text()); report['checks']['motion_framing_failures']=framing_failures
if framing_failures:
    validation_errors.append('Motion camera clips asset or has <2% margin'); report['status']='technical_fail'; report['errors']=validation_errors
(OUT/'validation.json').write_text(json.dumps(report,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'review-stage.blend'))
if validation_errors:raise RuntimeError('; '.join(validation_errors))
