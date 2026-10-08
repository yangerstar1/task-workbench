"""Original sculpt/rig candidate. Run only using pinned Blender on Actions.
Axes: Blender Z up, face -Y. No source model, texture or private reference inputs.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
P = json.loads((HERE / 'parameters.json').read_text())
a = argparse.ArgumentParser()
a.add_argument('--output', required=True)
a.add_argument('--renders', action='store_true')
args = a.parse_args(sys.argv[sys.argv.index('--') + 1:])
OUT = Path(args.output).resolve()
OUT.mkdir(parents=True, exist_ok=True)
random.seed(P['seed'])
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1
scene.render.fps = P['fps']


def active(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def ellipsoid(name, loc, scale, collection, seg=24, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    collection.append(o)
    return o


# Intersecting volumes are just sculpt input; voxel union produces ONE continuous skin.
parts = []
ellipsoid('Thorax', (0, -.24, .67), (.39, .49, .32), parts)
ellipsoid('Withers', (0, -.32, .84), (.29, .31, .15), parts)
ellipsoid('TuckedWaist', (0, .28, .65), (.245, .42, .205), parts)
ellipsoid('Pelvis', (0, .62, .64), (.31, .28, .255), parts)
ellipsoid('Neck', (0, -.65, .68), (.27, .30, .245), parts)
# Flattened wedge head, inset broad muzzle, no canine ears or long wolf snout.
ellipsoid('Cranium', (0, -.91, .65), (.295, .32, .205), parts)
ellipsoid('Muzzle', (0, -1.14, .575), (.24, .24, .125), parts)
ellipsoid('Jaw', (0, -1.055, .485), (.225, .255, .085), parts)
for side in (-1, 1):
    x = side * .285
    ellipsoid('Cheek', (side * .225, -.89, .60), (.14, .22, .17), parts)
    ellipsoid('Brow', (side * .20, -1.02, .755), (.13, .22, .07), parts)
    # Forelimbs: shoulder girdle, heavy triceps, narrower wrist, wide splayed paw.
    ellipsoid('Deltoid', (x, -.37, .63), (.195, .24, .27), parts)
    ellipsoid('UpperFore', (x * 1.1, -.33, .40), (.135, .17, .245), parts)
    ellipsoid('Forearm', (x * 1.16, -.47, .23), (.105, .135, .19), parts)
    ellipsoid('ForePaw', (x * 1.18, -.60, .105), (.155, .205, .105), parts)
    # Rear limb silhouette has a forward stifle and backward hock.
    ellipsoid('Haunch', (x * .94, .60, .48), (.19, .235, .275), parts)
    ellipsoid('Stifle', (x * 1.06, .38, .32), (.13, .15, .16), parts)
    ellipsoid('Hock', (x * 1.09, .69, .19), (.075, .11, .15), parts)
    ellipsoid('RearPaw', (x * 1.1, .55, .08), (.12, .17, .08), parts)
    for toe in (-1, 0, 1):
        ellipsoid('ForeToe', (x * 1.18 + toe * .078, -.745, .073), (.051, .11, .064), parts)
        ellipsoid('RearToe', (x * 1.1 + toe * .060, .43, .060), (.040, .085, .052), parts)
for i in range(6):
    t = i / 5
    ellipsoid('TailVolume', (0, .80 + .48 * t, .63 - .15 * t), (.145 * (1-t) + .035, .15, .13 * (1-t) + .035), parts)
# Subtle fused ridges, not separate armor cubes.
for i in range(6):
    y = -.47 + i * .205
    ellipsoid('DorsalRidge', (0, y, .875 - .16 * i / 5), (.10, .14, .075), parts)
bpy.ops.object.select_all(action='DESELECT')
for o in parts:
    o.select_set(True)
bpy.context.view_layer.objects.active = parts[0]
bpy.ops.object.join()
body = bpy.context.object
body.name = 'Pouncer_Skin_LOD0'
active(body)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
rem = body.modifiers.new('ContinuousSculptUnion', 'REMESH')
rem.mode = 'VOXEL'
rem.voxel_size = P['voxel_size']
rem.use_smooth_shade = True
bpy.ops.object.modifier_apply(modifier=rem.name)
smooth = body.modifiers.new('RelaxSculpt', 'SMOOTH')
smooth.factor = .8
smooth.iterations = 4
bpy.ops.object.modifier_apply(modifier=smooth.name)
tri = body.modifiers.new('Triangulate', 'TRIANGULATE')
bpy.ops.object.modifier_apply(modifier=tri.name)
if len(body.data.polygons) > P['target_triangles']:
    dec = body.modifiers.new('LODBudget', 'DECIMATE')
    dec.ratio = P['target_triangles'] / len(body.data.polygons)
    bpy.ops.object.modifier_apply(modifier=dec.name)
for face in body.data.polygons:
    face.use_smooth = True


def simple_material(name, color, roughness=.7, metallic=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Roughness'].default_value = roughness
    bs.inputs['Metallic'].default_value = metallic
    return mat


skin = simple_material('SandstoneSkin_VertexColor', (.47, .29, .135))
attr = skin.node_tree.nodes.new('ShaderNodeVertexColor')
attr.layer_name = 'SandstoneColor'
skin.node_tree.links.new(attr.outputs['Color'], skin.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
body.data.materials.append(skin)
colors = body.data.color_attributes.new(name='SandstoneColor', type='FLOAT_COLOR', domain='POINT')
for v, c in zip(body.data.vertices, colors.data):
    x, y, z = v.co
    # Large sediment bands follow anatomy; dark ventral countershade, restrained variation.
    belly = max(0, min(1, (z - .35) / .30))
    band = .025 * math.sin(z * 49 + y * 3 + math.sin(x * 14))
    grain = random.uniform(-.017, .017)
    base = Vector((.14, .092, .052)).lerp(Vector((.51, .335, .175)), belly)
    c.color = (*(max(.01, n + band + grain) for n in base), 1)
clawmat = simple_material('WornObsidianKeratin', (.067, .047, .033), .42)
eye_mat = simple_material('AmberIris', (.65, .265, .035), .23)
black = simple_material('ObsidianPupil', (.009, .008, .006), .22)
details = []
for s in (-1, 1):
    for material, scale, offset, label in [(black, (.055, .076, .037), 0, 'EyeSocket'), (eye_mat, (.037, .045, .024), .017, 'Eye'), (black, (.013, .031, .019), .040, 'Pupil')]:
        o = ellipsoid(label, (s * (.255 + offset), -1.055, .705), scale, details, 12, 8)
        o.data.materials.append(material)
        o['bind_bone'] = 'head'
    for front in (True, False):
        for t in (-1, 0, 1):
            x = s * (.336 if front else .314) + t * (.078 if front else .06)
            y = -.845 if front else .355
            o = ellipsoid('Claw', (x, y, .06), (.029, .070 if front else .048, .028), details, 10, 6)
            o.data.materials.append(clawmat)
            o['bind_bone'] = ('fore' if front else 'hind') + '_paw.' + ('L' if s > 0 else 'R')
    for j in range(4):
        o = ellipsoid('MouthSeam', (s * (.17 - j * .015), -1.02 - j * .075, .497), (.012, .045, .011), details, 8, 6)
        o.data.materials.append(black)
        o['bind_bone'] = 'head'

# 43 bones, skinned source mesh; explicit deterministic <=4 segment-distance weights.
bpy.ops.object.armature_add(enter_editmode=True)
rig = bpy.context.object
rig.name = 'Pouncer_Rig'
rig.data.edit_bones.remove(rig.data.edit_bones[0])
bones = {}

def bone(name, head, tail, parent=None, deform=True):
    b = rig.data.edit_bones.new(name)
    b.head, b.tail = head, tail
    b.use_deform = deform
    if parent:
        b.parent = rig.data.edit_bones[parent]
    bones[name] = (Vector(head), Vector(tail), deform)

bone('root', (0, 0, 0), (0, 0, .15), deform=False)
bone('visual_body', (0, 0, .48), (0, 1, .48), 'root', deform=False)
bone('pelvis', (0, .58, .61), (0, .3, .65), 'visual_body')
bone('spine', (0, .3, .65), (0, -.13, .70), 'pelvis')
bone('chest', (0, -.13, .70), (0, -.48, .70), 'spine')
bone('neck', (0, -.48, .70), (0, -.80, .67), 'chest')
bone('head', (0, -.80, .67), (0, -1.22, .60), 'neck')
bone('jaw', (0, -.87, .50), (0, -1.23, .49), 'head')
for i in range(3):
    bone('tail' + str(i), (0, .74 + .18*i, .63 - .045*i), (0, .92 + .18*i, .585-.045*i), 'pelvis' if i == 0 else 'tail'+str(i-1))
for s, suffix in [(1, 'L'), (-1, 'R')]:
    for front in (True, False):
        pre = ('fore' if front else 'hind')
        pts = [(s*.27,-.34,.72),(s*.315,-.28,.43),(s*.33,-.51,.15),(s*.336,-.69,.08),(s*.336,-.84,.065)] if front else [(s*.27,.63,.63),(s*.30,.37,.34),(s*.31,.68,.18),(s*.314,.51,.075),(s*.314,.36,.06)]
        parent = 'chest' if front else 'pelvis'
        for j, part in enumerate(['upper', 'lower', 'paw', 'digits']):
            name = pre+'_'+part+'.'+suffix
            bone(name, pts[j], pts[j+1], parent)
            parent = name
        for t in (-1,0,1):
            h = Vector(pts[3]); h.x += t*.065
            end = h + Vector((0,-.115,0))
            bone(pre+'_toe'+str(t)+'.'+suffix, h, end, pre+'_paw.'+suffix)
    bone('scapula.'+suffix, (s*.14,-.18,.79), (s*.29,-.38,.70), 'chest')
    bone('brow.'+suffix, (s*.16,-.91,.74), (s*.23,-1.11,.72), 'head')
bpy.ops.object.mode_set(mode='OBJECT')
rig.show_in_front = True


def segment_distance(p, h, t):
    d = t-h
    u = max(0, min(1, (p-h).dot(d)/d.length_squared))
    return (p-(h+u*d)).length


for obj in [body] + details:
    obj.parent = rig
    mod = obj.modifiers.new('Skin', 'ARMATURE')
    mod.object = rig
    if obj is not body:
        vg = obj.vertex_groups.new(name=obj['bind_bone'])
        vg.add(list(range(len(obj.data.vertices))), 1.0, 'REPLACE')
        continue
    candidates = [(n, h, t) for n,(h,t,d) in bones.items() if d and not ('toe' in n or n.startswith('brow') )]
    for n,h,t in candidates:
        obj.vertex_groups.new(name=n)
    for v in obj.data.vertices:
        eligible = [(n,h,t) for n,h,t in candidates if n != 'jaw' or (v.co.y < -.87 and v.co.z < .535)]
        distances = sorted((segment_distance(v.co,h,t),n) for n,h,t in eligible)[:4]
        weights = [math.exp(-d*24) for d,n in distances]
        total = sum(weights)
        for (_,n),w in zip(distances, weights):
            obj.vertex_groups[n].add([v.index], w/total, 'REPLACE')

rig['candidate_status'] = 'unreviewed_not_in_game'
rig['root_motion'] = False
rig['attack_interrupt_contract'] = 'Root remains stationary. visual_body owns leap. Blend interrupted Attack to Recover over <=0.18s; Recover begins with visual_body at rest, so blend settles within transition. Collision remains runtime-owned. Synthetic transition evidence is not in-engine proof.'
# Every bone gets a key every sample, avoiding accidental pose leakage across actions.
clips = {}
for name, seconds in P['clips'].items():
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = action
    end = round(seconds * P['fps']) + 1
    clips[name] = {'seconds_requested':seconds, 'frame_start':1, 'frame_end':end, 'seconds_sampled':(end-1)/P['fps'], 'loop':name in ('Idle','Walk'), 'hold_last_pose':name=='Death'}
    for f in range(1, end+1):
        u = (f-1)/(end-1)
        for pb in rig.pose.bones:
            pb.rotation_mode = 'XYZ'
            pb.rotation_euler = (0,0,0)
            pb.location = (0,0,0)
        def rot(n, xyz): rig.pose.bones[n].rotation_euler = xyz
        if name == 'Idle':
            rot('chest', (.012*math.sin(u*math.tau),0,0))
            rot('head', (0,.025*math.sin(u*math.tau),0))
        elif name == 'Walk':
            for s,phase in [('L',0),('R',math.pi)]:
                for pre,extra in [('fore',0),('hind',math.pi)]:
                    swing = math.sin(u*math.tau+phase+extra)
                    rot(pre+'_upper.'+s,(swing*.25,0,0))
                    rot(pre+'_lower.'+s,(-max(0,swing)*.36,0,0))
                    rot(pre+'_paw.'+s,(-swing*.12,0,0))
            rot('spine',(0,.025*math.sin(u*math.tau),0))
        elif name == 'Windup':
            q = math.sin(math.pi*u)
            # Whole-body loaded crouch, resolving to launch-ready neutral at clip boundary.
            rig.pose.bones['visual_body'].location=(0,.06*q,-.07*q)
            rot('neck',(-.20*q,0,0)); rot('head',(.13*q,0,0))
            for side in ('L','R'):
                rot('hind_upper.'+side,(-.22*q,0,0))
                rot('hind_lower.'+side,(.32*q,0,0))
                rot('fore_upper.'+side,(.10*q,0,0))
        elif name == 'Attack':
            # Anticipation -> spring -> forward bite apex -> landing -> settle.
            q = math.sin(math.pi*u)**2
            flight = max(0, math.sin(math.pi*max(0,min(1,(u-.10)/.72))))
            rig.pose.bones['visual_body'].location=(0,-.38*q,.25*flight)
            rot('visual_body',(-.12*math.sin(math.tau*u),0,0))
            rot('neck',(.20*q,0,0)); rot('head',(-.22*q,0,0)); rot('jaw',(.46*q,0,0))
            for side in ('L','R'):
                rot('fore_upper.'+side,(-.40*q,0,0))
                rot('fore_lower.'+side,(.13*q,0,0))
                rot('hind_upper.'+side,(.50*q,0,0))
                rot('hind_lower.'+side,(-.50*q,0,0))
        elif name == 'Recover':
            # First pose is grounded rest: interrupted visual_body lift blends to zero.
            q = math.sin(math.pi*u)*(1-u)
            rig.pose.bones['visual_body'].location=(0,.035*q,-.025*q)
            rot('head',(.15*q,0,.09*q)); rot('neck',(-.08*q,0,0))
            for side in ('L','R'):
                rot('fore_lower.'+side,(.08*q,0,0))
        elif name == 'Hit':
            q = math.sin(math.pi*u)
            rig.pose.bones['visual_body'].location=(.035*q,.05*q,0)
            rot('head',(-.12*q,0,.16*q)); rot('neck',(-.07*q,0,-.07*q))
        elif name == 'Death':
            # Collapse rightward, fold limbs, then hold the final side-lying pose.
            t = min(1,u/.78)
            q = t*t*(3-2*t)
            rig.pose.bones['visual_body'].location=(.14*q,0,-.30*q)
            rot('visual_body',(.05*q,1.48*q,0))
            rot('head',(.31*q,0,.18*q)); rot('neck',(.18*q,0,0))
            for side in ('L','R'):
                rot('fore_upper.'+side,(.50*q,0,.15*q))
                rot('fore_lower.'+side,(-.72*q,0,0))
                rot('hind_upper.'+side,(-.48*q,0,0))
                rot('hind_lower.'+side,(.65*q,0,0))
        for i in range(3):
            rot('tail'+str(i),(0,0,(-.11 if name=='Death' else .025*math.sin(u*math.tau+i*.5))))
        # Ground collision for grounded phases and death; preserve genuine flight.
        if name != 'Attack' or u < .10 or u > .90:
            bpy.context.view_layer.update()
            evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh=evaluated.to_mesh()
            lowest=min((evaluated.matrix_world@v.co).z for v in mesh.vertices)
            evaluated.to_mesh_clear()
            rig.pose.bones['visual_body'].location.z -= lowest
        for pb in rig.pose.bones:
            pb.keyframe_insert('rotation_euler', frame=f, group=pb.name)
            pb.keyframe_insert('location', frame=f, group=pb.name)
    for fc in action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = 'LINEAR'
    track = rig.animation_data.nla_tracks.new()
    track.name = name
    track.strips.new(name, 1, action)
    track.mute = True
rig.animation_data.action = bpy.data.actions['Idle']
scene.frame_set(1)
# Export only asset; stage is created AFTER exports, so no camera/ground contaminants.
bpy.ops.object.select_all(action='DESELECT')
for obj in [body, rig] + details: obj.select_set(True)
bpy.context.view_layer.objects.active = rig
# Export all NLA tracks separately, mute off for exporter discovery.
rig.animation_data.action = None
for tr in rig.animation_data.nla_tracks: tr.mute = False
bpy.ops.export_scene.gltf(filepath=str(OUT/'pouncer-candidate.glb'), export_format='GLB', use_selection=True, export_animations=True, export_animation_mode='NLA_TRACKS', export_nla_strips=True, export_yup=True)
bpy.ops.export_scene.fbx(filepath=str(OUT/'pouncer-candidate.fbx'), use_selection=True, add_leaf_bones=False, bake_anim=True, bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False, axis_forward='-Z', axis_up='Y', apply_unit_scale=True)
for tr in rig.animation_data.nla_tracks: tr.mute = True
rig.animation_data.action = bpy.data.actions['Idle']
scene.frame_set(1)
(OUT/'clip-manifest.json').write_text(json.dumps(clips,indent=2))
(OUT/'parameters.json').write_text(json.dumps(P,indent=2))
# Save clean asset, then render review evidence from a separate stage file.
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'pouncer-candidate.blend'))
exec(compile((HERE/'validate_asset.py').read_text(), str(HERE/'validate_asset.py'), 'exec'))
if not args.renders:
    if validation_errors: raise RuntimeError('; '.join(validation_errors))
    sys.exit(0)
scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.cycles.use_denoising = True
scene.render.resolution_x = scene.render.resolution_y = P['render_size']
scene.render.resolution_percentage = 100
scene.world.color = (.23,.23,.23)
scene.view_settings.view_transform = 'AgX'
ground = simple_material('ReviewNeutralGray',(.18,.18,.18),.9)
bpy.ops.mesh.primitive_plane_add(size=200)
bpy.context.object.data.materials.append(ground)
bpy.context.object.name='ReviewFloor'
for name,loc,power,size in [('Key',(-3,-4,5),600,4),('Fill',(4,-1,3),350,4),('Rim',(0,4,4),500,3)]:
    bpy.ops.object.light_add(type='AREA', location=loc)
    l = bpy.context.object; l.name=name; l.data.energy=power; l.data.shape='DISK'; l.data.size=size
    l.rotation_euler=(Vector((0,0,.5))-l.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add()
cam=bpy.context.object
cam.data.type='ORTHO'; cam.data.ortho_scale=3.25
scene.camera=cam

def camera_at(angle):
    cam.location=(4*math.sin(angle),-4*math.cos(angle),1.9)
    cam.rotation_euler=(Vector((0,-.04,.45))-cam.location).to_track_quat('-Z','Y').to_euler()

review=OUT/'review'; review.mkdir(exist_ok=True)
scene.render.image_settings.file_format='PNG'
for i in range(8):
    camera_at(i*math.tau/8)
    scene.render.filepath=str(review/f'turntable-{i:02}.png')
    bpy.ops.render.render(write_still=True)
camera_at(math.pi/2)
# Side-on motion evidence: 15 fps subsampling keeps CPU-only review bounded.
scene.render.resolution_x=640; scene.render.resolution_y=480
for name,meta in {**clips, **preview_clips}.items():
    rig.animation_data.action=bpy.data.actions[name]
    folder=review/name; folder.mkdir(exist_ok=True)
    frames=list(range(1,meta['frame_end']+1,2))
    if frames[-1]!=meta['frame_end']: frames.append(meta['frame_end'])
    for index,frame in enumerate(frames):
        scene.frame_set(frame)
        scene.render.filepath=str(folder/f'{index:04}.png')
        bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'review-stage.blend'))

if validation_errors: raise RuntimeError('; '.join(validation_errors))
