"""Executed within generate.py. Export clips are in-place; review root travel is synthetic."""
import hashlib
checks=[]; clip_rows=[]; actions=[]
def create_action(name,duration,sampler):
    rig.animation_data_create(); act=bpy.data.actions.new(name); rig.animation_data.action=act
    count=round(duration*P['fps'])+1
    for frame in range(1,count+1):
        scene.frame_set(frame); pose=sampler((frame-1)/P['fps']); apply_pose(pose)
        for pb in rig.pose.bones:
            pb.keyframe_insert('location',frame=frame,group=pb.name)
            pb.keyframe_insert('rotation_quaternion',frame=frame,group=pb.name)
            pb.keyframe_insert('scale',frame=frame,group=pb.name)
    for fc in act.fcurves:
        for key in fc.keyframe_points: key.interpolation='LINEAR'
    act.use_fake_user=True
    return act,count

def review_action(name,act,count,sampler,root_travel):
    rig.animation_data.action=act; scene.frame_start=1; scene.frame_end=count
    previous=None
    for frame in range(1,count+1):
        t=(frame-1)/P['fps']; scene.frame_set(frame); rig.location=(0,-root_travel(t),0)
        bpy.context.view_layer.update(); camera(math.pi*.65,(0,-root_travel(t)-.1,.55))
        row=validate_frame(name+':'+str(frame)); row['time']=t; p=sampler(t)
        feet={k:rig.matrix_world@rig.pose.bones['foot.'+k].head for k in motion.LEGS}
        evaluated=combined.evaluated_get(bpy.context.evaluated_depsgraph_get()); emesh=evaluated.to_mesh()
        for k,v in feet.items():
            if p['contact'][k]:
                sole_z=min((evaluated.matrix_world@emesh.vertices[i].co).z for i in sole_indices[k])
                if sole_z>P['contact_gap_limit_m']: row['errors'].append('sole hovering '+k)
            for part,expected in [('upper',motion.UPPER),('lower',motion.LOWER)]:
                pb=rig.pose.bones[part+'.'+k]
                if abs((pb.tail-pb.head).length-expected)>.001: row['errors'].append('link stretch '+k)
            target=rig.matrix_world@Vector(p['feet'][k])
            if (v-target).length>.001: row['errors'].append('baked ankle target mismatch '+k)
            if p['contact'][k] and abs(v.z-motion.FOOT[k][2])>.001: row['errors'].append('contact height '+k)
            if previous and p['contact'][k] and previous['contact'][k]:
                # Endpoint stance switches are excluded; uninterrupted support must not skate.
                if (v-previous['feet'][k]).length>.025: row['errors'].append('support slip '+k)
        evaluated.to_mesh_clear()
        previous={'feet':feet,'contact':p['contact']}; checks.append(row)
    # Camera follows world translation each frame using keyed location and orientation.
    for frame in range(1,count+1):
        t=(frame-1)/P['fps']; scene.frame_set(frame); rig.location=(0,-root_travel(t),0); rig.keyframe_insert('location',frame=frame)
        camera(math.pi*.65,(0,-root_travel(t)-.1,.55)); cam.keyframe_insert('location',frame=frame); cam.keyframe_insert('rotation_euler',frame=frame)
    for ob in (rig,cam):
        if ob.animation_data and ob.animation_data.action:
            for fc in ob.animation_data.action.fcurves:
                if fc.data_path in ('location','rotation_euler'):
                    for point in fc.keyframe_points: point.interpolation='LINEAR'
    scene.render.image_settings.file_format='FFMPEG'; scene.render.ffmpeg.format='MPEG4'; scene.render.ffmpeg.codec='H264'; scene.render.ffmpeg.constant_rate_factor='MEDIUM'
    scene.render.filepath=str(review/(name+'.mp4')); bpy.ops.render.render(animation=True)
    # Strip all preview-only object curves; exported root motion remains identically zero.
    for fc in list(act.fcurves):
        if fc.data_path=='location': act.fcurves.remove(fc)
    rig.location=(0,0,0)
    camera_action=cam.animation_data.action if cam.animation_data else None
    cam.animation_data_clear()
    if camera_action: bpy.data.actions.remove(camera_action)
    # Representative contact/weak-point frames remain individually inspectable.
    for fraction in (0,.25,.5,.75,1):
        frame=1+round((count-1)*fraction); scene.frame_set(frame); camera(math.pi*.65); still(review/f'{name}-{fraction:.2f}.png')

for name,duration in P['clips'].items():
    sampler=lambda t,n=name:motion.sample(n,t)
    act,count=create_action(name,duration,sampler); actions.append(act)
    review_action(name,act,count,sampler,lambda t,n=name:motion.travel(n,t))
    clip_rows.append({'name':name,'frames':count,'duration_seconds':(count-1)/P['fps'],'loop':name in ('Idle','Walk','Attack'),'root_motion':False})
for phase in (.07,.42,.91):
    name='SYNTHETIC_Interrupt_'+str(phase); lead=min(.35,phase)
    sampler=lambda t,p=phase,l=lead:motion.sample('Attack',p-l+t) if t<l else motion.interrupted(p,t-l)
    act,count=create_action(name,lead+.6,sampler); review_action(name,act,count,sampler,lambda t,l=lead:P['charge_speed_mps']*min(t,l))
    rig.animation_data.action=None; bpy.data.actions.remove(act)
# Orbit the rest pose: independent of seven action footage.
rig.animation_data.action=actions[0]; scene.frame_set(1); rig.location=(0,0,0)
for i in range(16):
    camera(i*math.tau/16); checks.append(validate_frame('turntable-'+str(i))); still(review/f'turntable-{i:02}.png')
triangles=sum(sum(len(face.vertices)-2 for face in o.data.polygons) for o in assets)
errors=[r for r in checks if r['errors']]
if triangles>P['triangle_budget']: errors.append({'errors':['triangle budget'],'actual':triangles})
if len(rig.data.bones)>P['bone_budget']: errors.append({'errors':['bone budget']})
report={'status':'technical_checks_failed' if errors else 'technical_checks_passed_visual_review_still_required','triangles':triangles,'bones':len(rig.data.bones),'frame_checks':checks,'failures':errors,'unity_tested':False,'visual_approved':False}
(OUT/'evaluated-validation.json').write_text(json.dumps(report,indent=2))
(OUT/'clip-manifest.json').write_text(json.dumps(clip_rows,indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bulwark-review.blend'))
if errors: raise RuntimeError('Evidence retained. Export blocked by evaluated technical failures; inspect evaluated-validation.json')
# Select only the rig and asset meshes, never the review stage/camera/lights.
bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True)
for o in assets:o.select_set(True)
bpy.context.view_layer.objects.active=rig
bpy.ops.export_scene.gltf(filepath=str(OUT/'bulwark-candidate.glb'),use_selection=True,export_format='GLB',export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_frame_range=False)
bpy.ops.export_scene.fbx(filepath=str(OUT/'bulwark-candidate.fbx'),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,axis_forward='-Z',axis_up='Y',bake_anim=True,bake_anim_use_all_actions=True,bake_anim_use_nla_strips=False,bake_anim_force_startend_keying=True,bake_anim_simplify_factor=0.0,path_mode='COPY',embed_textures=True)
files={str(f.relative_to(OUT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in OUT.rglob('*') if f.is_file()}
(OUT/'output-sha256.json').write_text(json.dumps(files,indent=2))
