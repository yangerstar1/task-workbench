"""Executed within generate.py after asset export; hard checks are not visual approval."""
import collections
import json
import math
import struct

errors = []
checks = {}
meshes = [body] + details
triangles = sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
checks['triangles_all_render_meshes'] = triangles
checks['bone_count'] = len(rig.data.bones)
if not 8000 <= triangles <= 12000: errors.append('Total render triangle budget is outside 8k–12k')
if not 35 <= checks['bone_count'] <= 55: errors.append('Bone budget outside 35–55')
adj = collections.defaultdict(set)
for e in body.data.edges:
    u,v=e.vertices
    adj[u].add(v); adj[v].add(u)
left=set(range(len(body.data.vertices))); components=[]
while left:
    stack=[left.pop()]; size=0
    while stack:
        v=stack.pop(); size+=1
        new=adj[v]&left; left-=new; stack.extend(new)
    components.append(size)
checks['skin_connected_components']=len(components)
if len(components)!=1: errors.append('Main sculpt skin is disconnected')
weights_ok=True
for obj in meshes:
    for v in obj.data.vertices:
        w=[g.weight for g in v.groups if g.weight>0]
        if not w or len(w)>4 or abs(sum(w)-1)>1e-5: weights_ok=False
        if not all(math.isfinite(c) for c in v.co): errors.append('Nonfinite vertex'); break
checks['normalized_max_four_weights']=weights_ok
if not weights_ok: errors.append('Weights invalid')
checks['clips']=list(clips)
checks['root_motion']=False
root_static=True
for action in bpy.data.actions:
    for fc in action.fcurves:
        if fc.data_path=='pose.bones["root"].location':
            root_static &= all(abs(k.co.y)<1e-8 for k in fc.keyframe_points)
if not root_static: errors.append('Root has translation')
checks['root_translation_zero']=root_static
# Count serialized GLB animations and skin, instead of trusting export operator success.
b=(OUT/'pouncer-candidate.glb').read_bytes()
magic,version,length=struct.unpack_from('<4sII',b,0)
if magic!=b'glTF' or version!=2 or length!=len(b): errors.append('Invalid GLB container')
chunk_len,chunk_type=struct.unpack_from('<II',b,12)
gltf=json.loads(b[20:20+chunk_len].decode('utf8'))
exported={x.get('name') for x in gltf.get('animations',[])}
checks['glb_animation_names']=sorted(exported)
if exported!=set(clips): errors.append('Serialized GLB action names differ from required clips')
if not gltf.get('skins'): errors.append('No serialized GLB skin')
# Sample evaluated skinned world bounds for floor penetration/airborne whole asset.
# Small paw movement requires visual inspection and future foot-lock refinement.
motion={}
for name,meta in clips.items():
    rig.animation_data.action=bpy.data.actions[name]
    bounds=[]
    for f in range(1,meta['frame_end']+1):
        scene.frame_set(f)
        deps=bpy.context.evaluated_depsgraph_get()
        ev=body.evaluated_get(deps)
        me=ev.to_mesh()
        z=[(ev.matrix_world@v.co).z for v in me.vertices]
        bounds.append((min(z),max(z)))
        ev.to_mesh_clear()
    motion[name]={'minimum_z':min(z[0] for z in bounds),'maximum_floor_gap':max(z[0] for z in bounds)}
checks['motion_bounds_m']=motion
# Flight is allowed. First and last samples must return to contact.
endpoint_contacts={}
for name in ('Attack','Recover','Walk'):
    rig.animation_data.action=bpy.data.actions[name]
    heights=[]
    for frame in (1,clips[name]['frame_end']):
        scene.frame_set(frame)
        ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get()); me=ev.to_mesh()
        heights.append(min((ev.matrix_world@v.co).z for v in me.vertices)); ev.to_mesh_clear()
    endpoint_contacts[name]=heights
    if any(abs(z)>.04 for z in heights): errors.append(name+' start/end lost floor contact')
checks['clip_endpoint_floor_heights_m']=endpoint_contacts
rig.animation_data.action=bpy.data.actions['Attack']; scene.frame_set(1+round((clips['Attack']['frame_end']-1)*.5))
checks['attack_apex_visual_offset_m']=list(rig.pose.bones['visual_body'].location)
if checks['attack_apex_visual_offset_m'][1]>-.2: errors.append('Attack fails forward -Y lunge direction')
checks['attack_flight_height_m']=motion['Attack']['maximum_floor_gap']
if motion['Attack']['maximum_floor_gap']<.07: errors.append('Attack has no visible flight phase')
# Side-lying Death must remain down and unchanged over its final hold.
rig.animation_data.action=bpy.data.actions['Death']
death_end=clips['Death']['frame_end']
scene.frame_set(death_end)
checks['death_end_roll_rad']=rig.pose.bones['visual_body'].rotation_euler.y
if abs(checks['death_end_roll_rad'])<1.2: errors.append('Death is not a complete side collapse')
def capture():
    return {pb.name:(pb.location.copy(),pb.rotation_euler.copy()) for pb in rig.pose.bones}
end_pose=capture(); scene.frame_set(death_end-4); hold_pose=capture()
checks['death_final_hold_stable']=all((end_pose[n][0]-hold_pose[n][0]).length<1e-5 and (Vector(end_pose[n][1])-Vector(hold_pose[n][1])).length<1e-5 for n in end_pose)
if not checks['death_final_hold_stable']: errors.append('Death final hold moves')
# Synthetic interrupted blends, AFTER export: evidence clips never enter production GLB.
preview_clips={}; interrupt_checks={}
for fraction in (.25,.50,.75):
    rig.animation_data.action=bpy.data.actions['Attack']
    scene.frame_set(round(1+fraction*(clips['Attack']['frame_end']-1)))
    start_pose=capture()
    rig.animation_data.action=bpy.data.actions['Recover']; scene.frame_set(1)
    landing_pose=capture()
    label='InterruptAttack'+str(round(fraction*100))+'ToRecover'
    action=bpy.data.actions.new(label); rig.animation_data.action=action
    transition_frames=6  # 0.1667 seconds; inside <=0.18 second contract.
    end=transition_frames+clips['Recover']['frame_end']-1
    for frame in range(1,end+1):
        if frame<=transition_frames:
            w=(frame-1)/(transition_frames-1)
            pose={n:(start_pose[n][0].lerp(landing_pose[n][0],w),Vector(start_pose[n][1]).lerp(Vector(landing_pose[n][1]),w)) for n in start_pose}
        else:
            rig.animation_data.action=bpy.data.actions['Recover']; scene.frame_set(frame-transition_frames+1)
            pose=capture(); rig.animation_data.action=action
        for n,(loc,rot) in pose.items():
            pb=rig.pose.bones[n]; pb.location=loc; pb.rotation_euler=rot
            pb.keyframe_insert('location',frame=frame,group=n); pb.keyframe_insert('rotation_euler',frame=frame,group=n)
    for fc in action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation='LINEAR'
    scene.frame_set(transition_frames)
    ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get()); me=ev.to_mesh()
    landed=min((ev.matrix_world@v.co).z for v in me.vertices); ev.to_mesh_clear()
    interrupt_checks[label]={'landing_floor_height_m':landed,'transition_seconds':(transition_frames-1)/P['fps'],'engine_runtime_verified':False}
    if abs(landed)>.04: errors.append(label+' does not settle to floor')
    preview_clips[label]={'frame_start':1,'frame_end':end}
checks['synthetic_interrupt_recovery']=interrupt_checks
(OUT/'interrupt-manifest.json').write_text(json.dumps(interrupt_checks,indent=2))
rig.animation_data.action=bpy.data.actions['Idle']; scene.frame_set(1)
report={'status':'technical_pass' if not errors else 'technical_fail','visual_approval':False,'checks':checks,'errors':errors,'review_required':['silhouette from eight views','skin stretching at shoulder and hip','paw sliding / penetration during Walk','Windup and bite weight','full Death collapse contact and final hold','in-engine Attack interrupt blending and Unity materials not tested']}
(OUT/'validation.json').write_text(json.dumps(report,indent=2))
validation_errors=list(errors)  # Generator renders evidence even if a technical gate fails.
