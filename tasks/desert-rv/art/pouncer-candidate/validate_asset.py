"""Hard technical rejection rules; never a visual-art approval."""
errors=[]; checks={}; preview_clips={}
meshes=[body]+details
checks['triangles_all_render_meshes']=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
checks['bone_count']=len(rig.data.bones)
if not 8000<=checks['triangles_all_render_meshes']<=12000:errors.append('Total triangle budget outside 8k–12k')
if not 35<=checks['bone_count']<=55:errors.append('Bone count outside35–55')
adj=collections.defaultdict(set)
for e in body.data.edges:
    u,v=e.vertices; adj[u].add(v); adj[v].add(u)
left=set(range(len(body.data.vertices))); components=0
while left:
    components+=1; stack=[left.pop()]
    while stack:
        v=stack.pop(); new=adj[v]&left; left-=new; stack.extend(new)
checks['skin_components']=components
checks['skin_topology']=inspect_mesh(body.data)
topology=checks['skin_topology']
if components!=1:errors.append('Skin disconnected')
if topology['boundary_edge_count'] or topology['nonmanifold_edge_count'] or topology['loose_edge_count'] or topology['nonmanifold_vertex_count']:errors.append('Skin boundary/nonmanifold/loose edges found; see topology coordinates')
if topology['closed_connected_edge_manifold'] and topology['orientable_genus_if_closed']!=0:errors.append('Closed skin has nonzero genus: unintended handle, not an inferred open boundary')
weights_ok=all(0<len(v.groups)<=4 and abs(sum(g.weight for g in v.groups)-1)<1e-5 for o in meshes for v in o.data.vertices)
checks['max_four_normalized_weights']=weights_ok
if not weights_ok:errors.append('Bad weights')
checks['basecolor_texture_png']=(OUT/'pouncer-basecolor.png').exists()
checks['uv_layers']=len(body.data.uv_layers)
if not checks['basecolor_texture_png'] or not checks['uv_layers']:errors.append('Missing Unity-compatible UV base-color image')
b=(OUT/'pouncer-candidate.glb').read_bytes(); magic,version,length=struct.unpack_from('<4sII',b,0); chunk_len,chunk_type=struct.unpack_from('<II',b,12); gltf=json.loads(b[20:20+chunk_len].decode())
checks['glb_animation_names']=sorted(a.get('name') for a in gltf.get('animations',[])); checks['glb_images']=len(gltf.get('images',[]))
if set(checks['glb_animation_names'])!=set(clips):errors.append('Serialized GLB clip names differ')
if not checks['glb_images']:errors.append('GLB has no embedded texture image')
checks['root_translation_zero']=all(all(abs(k.co.y)<1e-7 for k in fc.keyframe_points) for n in clips for fc in bpy.data.actions[n].fcurves if fc.data_path=='pose.bones["root"].location')
if not checks['root_translation_zero']:errors.append('Root motion present')
from export_timing import inspect_glb,inspect_fbx
checks['serialized_animation_times']={}
for format,reader in [('glb',inspect_glb),('fbx',inspect_fbx)]:
    try:
        times=reader(OUT/('pouncer-candidate.'+format)); checks['serialized_animation_times'][format]=times
        if set(times)!=set(P['clips']):errors.append(format+' serialized animation names/ranges missing')
        for name,seconds in P['clips'].items():
            if name in times and (abs(times[name]['start'])>1e-6 or abs(times[name]['end']-seconds)>1e-6):errors.append(format+' '+name+' actual exported timing differs from game contract')
    except Exception as exc:errors.append(format+' timing verification failed: '+str(exc))
# Evaluate exported-source BAKED poses, never pass based only on authoring targets.
sampled={}; baked_gait=[]
for name,meta in clips.items():
    rig.animation_data.action=bpy.data.actions[name]; rows=[]
    for frame in range(1,meta['frame_end']+1):
        scene.frame_set(frame); row=bounds(); rows.append(row)
        if name=='Walk':
            u=(frame-1)/(meta['frame_end']-1); feet={}
            for key in leg_chains:
                pre,side=key.split('.'); phase=(u+(0 if key in ('fore.L','hind.R') else .5))%1
                pb=rig.pose.bones[pre+'_paw.'+side]; feet[key]={'stance':phase<.5,'ankle':list(pb.head),'tip':list(pb.tail)}
            baked_gait.append({'frame':frame,'time':(frame-1)/P['fps'],'feet':feet})
    sampled[name]=rows
    if min(r['min_z'] for r in rows)<-.004:errors.append(name+' penetrates floor >4mm')
(OUT/'death-baked-bounds.json').write_text(json.dumps([{'source_frame':i+1,'seconds':i/P['fps'],**row} for i,row in enumerate(sampled['Death'])],indent=2))
checks['motion_bounds_m']={n:{'minimum_z':min(r['min_z'] for r in rows),'max_floor_gap':max(r['min_z'] for r in rows),'start_z':rows[0]['min_z'],'end_z':rows[-1]['min_z']} for n,rows in sampled.items()}
for name in ('Idle','Walk','Windup','Attack','Recover','Hit','Death'):
    if any(abs(sampled[name][i]['min_z'])>.02 for i in (0,-1)):errors.append(name+' endpoint lacks ground contact')
if checks['motion_bounds_m']['Attack']['max_floor_gap']<.07:errors.append('Attack has no visible leap')
# World-foot lock: root travels -2.7m/s, so each supporting foot moves +2.7 locally.
stance_speeds={}; stance_errors={}
for key in leg_chains:
    speeds=[]; errors_y=[]
    for a,b in zip(baked_gait,baked_gait[1:]):
        if a['feet'][key]['stance'] and b['feet'][key]['stance']:
            pa=Vector(a['feet'][key]['ankle']); pb=Vector(b['feet'][key]['ankle']); dt=b['time']-a['time']
            speed=(pb.y-pa.y)/dt; speeds.append(speed); errors_y.append(abs(speed-2.7))
    stance_speeds[key]=speeds; stance_errors[key]=max(errors_y,default=999)
    if stance_errors[key]>.08:errors.append(key+' planted phase does not match 2.7m/s')
checks['stance_max_speed_error_mps']=stance_errors; checks['stance_speed_samples_mps']=stance_speeds
(OUT/'gait-baked-verification.json').write_text(json.dumps(baked_gait,indent=2))
rig.animation_data.action=bpy.data.actions['Death']; scene.frame_set(clips['Death']['frame_end'])
def capture():return {pb.name:(pb.location.copy(),pb.rotation_euler.copy(),pb.scale.copy()) for pb in rig.pose.bones}
last=capture(); scene.frame_set(clips['Death']['frame_end']-5); before=capture()
checks['death_final_hold_stable']=all((last[n][0]-before[n][0]).length<1e-5 and (Vector(last[n][1])-Vector(before[n][1])).length<1e-5 for n in last)
if not checks['death_final_hold_stable']:errors.append('Death final hold not stable')
checks['death_end_max_height']=sampled['Death'][-1]['max_z']
rig.animation_data.action=bpy.data.actions['Death']; scene.frame_set(clips['Death']['frame_end'])
ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get()); me=ev.to_mesh()
torso=[i for i,v in enumerate(body.data.vertices) if -.65<v.co.y<.77 and v.co.z>.50]
checks['death_torso_contact_z']=min((ev.matrix_world@me.vertices[i].co).z for i in torso); ev.to_mesh_clear()
checks['death_relaxed_paw_heights']={key:rig.pose.bones[key.split('.')[0]+'_paw.'+key.split('.')[1]].tail.z for key in leg_chains}
rest_width=max(body.data.vertices[i].co.x for i in torso)-min(body.data.vertices[i].co.x for i in torso)
checks['death_height_limit_from_torso_width']=rest_width+.035
if abs(checks['death_torso_contact_z'])>.012:errors.append('Death torso is not resting on the floor')
if max(checks['death_relaxed_paw_heights'].values())>.28:errors.append('Death legs remain rigidly raised')
if sampled['Death'][-1]['max_z']>rest_width+.035:errors.append('Death exceeds anatomical side-lying height')
# Synthetic default crossfade + a visible supported compression after landing.
# These clips disclose the real visual jump/gap for review; they are not Unity verification.
interrupts={}
for fraction,mode in [(f,'current_runtime') for f in (.25,.50,.75)]+[(.50,'proposed_fixed_time')]:
    rig.animation_data.action=bpy.data.actions['Attack']; scene.frame_set(round(1+fraction*(clips['Attack']['frame_end']-1))); start=capture()
    rig.animation_data.action=bpy.data.actions['Recover']; scene.frame_set(1); target=capture()
    label=('InterruptAttack' if mode=='current_runtime' else 'ProposedFixedInterruptAttack')+str(round(fraction*100))+'ToRecover'; action=bpy.data.actions.new(label); rig.animation_data.action=action
    requested=.12*clips['Attack']['seconds_sampled'] if mode=='current_runtime' else .24
    transition=round(requested*P['fps'])+1; end=clips['Recover']['frame_end']
    interrupt_frame=round(1+fraction*(clips['Attack']['frame_end']-1))
    for frame in range(1,end+1):
        if frame<=transition:
            w=(frame-1)/(transition-1)
            rig.animation_data.action=bpy.data.actions['Attack']; scene.frame_set(min(clips['Attack']['frame_end'],interrupt_frame+frame-1)); start=capture()
            rig.animation_data.action=bpy.data.actions['Recover']; scene.frame_set(frame); target=capture(); rig.animation_data.action=action
            pose={n:(start[n][0].lerp(target[n][0],w),start[n][1].to_quaternion().slerp(target[n][1].to_quaternion(),w).to_euler('XYZ'),start[n][2].lerp(target[n][2],w)) for n in start}
        else:
            rig.animation_data.action=bpy.data.actions['Recover']; scene.frame_set(frame); pose=capture(); rig.animation_data.action=action
        for n,(loc,rot,scale) in pose.items():
            pb=rig.pose.bones[n]; pb.location=loc; pb.rotation_euler=rot; pb.scale=scale
            pb.keyframe_insert('location',frame=frame,group=n); pb.keyframe_insert('rotation_euler',frame=frame,group=n); pb.keyframe_insert('scale',frame=frame,group=n)
    for fc in action.fcurves:
        for kp in fc.keyframe_points:kp.interpolation='LINEAR'
    zs=[]
    for frame in range(1,end+1):scene.frame_set(frame); zs.append(bounds()['min_z'])
    interrupts[label]={'mode':mode,'source_and_target_advance':True,'blend_weight_assumption':'linear quaternion slerp; Unity not measured','requested_seconds':requested,'transition_seconds':(transition-1)/P['fps'],'landing_z':zs[transition-1],'minimum_z':min(zs),'Unity_runtime_verified':False}
    if abs(zs[transition-1])>.02 or min(zs)<-.004:errors.append(label+' failed contact during crossfade')
    preview_clips[label]={'frame_start':1,'frame_end':end}
checks['synthetic_interrupts']=interrupts
clearance=json.loads((OUT/'transition-clearance.json').read_text())
checks['all_attack_frames_quaternion_crossfade_min_z']=min(r['verified_crossfade_min_z_after_lift'] for r in clearance['frames'])
checks['attack_maximum_added_clearance_m']=clearance['maximum_added_lift_m']
if checks['all_attack_frames_quaternion_crossfade_min_z']<-.004:errors.append('An actual source Attack quaternion crossfade still penetrates the ground >4mm')
(OUT/'interrupt-manifest.json').write_text(json.dumps(interrupts,indent=2))
rig.animation_data.action=bpy.data.actions['Idle']; scene.frame_set(1)
report={'scope':SCOPE,'full_motion_visual_review':'NOT_RUN' if args.scope=='death-diagnostic' else 'REQUIRED','status':('death_diagnostic_technical_pass' if args.scope=='death-diagnostic' else 'technical_pass') if not errors else 'technical_fail','visual_approval':False,'revision':3,'checks':checks,'errors':errors,'review_required':['all eight silhouette views','brow, jaw separation, shoulder and narrow waist','no hock tunnel','UV base-color parity in Unity','diagonal support and contact load in Walk','Windup compresses rather than rises','all-frame Attack framing and bite clarity','real Unity interrupted transitions before adopting asset']}
(OUT/'validation.json').write_text(json.dumps(report,indent=2)); validation_errors=errors
