"""Render four stills from the exact passing artifact. Never author/export/save assets."""
import argparse, hashlib, json, math, sys
from pathlib import Path
import bpy
from mathutils import Vector
PIN = {
 'technical-gate.json':'33cde1c855c27a954b72051b188fd7b92b4b9378219c972e244ace6419dcf962',
 'pouncer-candidate.blend':'f2fd43af20d8cc82ae4eb9e5ea4fc35284fffcb50223c7b9e99bb1d1650ad73d',
 'pouncer-candidate.glb':'b14fc5279f529db06ae6c7075aaa670058970d3d1490453371c0c9c10170e104',
 'pouncer-candidate.fbx':'7a00a875d8d5d8bd6f14d39aee736a9e705f95f304e754d8653d3f1150ef223f'}
COMMIT='ec7a88493dcba5c1d0394218efc740926cd95ce1'
a=argparse.ArgumentParser();a.add_argument('--input',required=True);a.add_argument('--output',required=True)
args=a.parse_args(sys.argv[sys.argv.index('--')+1:]);src=Path(args.input).resolve();out=Path(args.output).resolve()
if src==out:raise RuntimeError('Render evidence must have a separate output directory')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,digest in PIN.items():
 if sha(src/name)!=digest:raise RuntimeError('Pinned source mismatch: '+name)
if (src/'source-commit.txt').read_text().strip()!=COMMIT:raise RuntimeError('Source commit mismatch')
gate=json.loads((src/'technical-gate.json').read_text())
if gate['status']!='DEATH_TECHNICAL_PASS_NOT_FULL' or gate['errors'] or not gate['source_native_pass']:raise RuntimeError('Source native gate failed')
if not all(gate['serialized_native_checks'][f]['passed'] for f in ('glb','fbx')):raise RuntimeError('Serialized gate failed')
if tuple(bpy.app.version)!=(4,2,3):raise RuntimeError('Official Blender4.2.3 required')
bpy.ops.wm.open_mainfile(filepath=str(src/'pouncer-candidate.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['Pouncer_Rig'];assets=sorted([o for o in scene.objects if o.type=='MESH'],key=lambda o:o.name)
if len(assets)!=27 or scene.render.fps!=100:raise RuntimeError('Mesh/fps contract mismatch')
expected={'Idle':2.,'Walk':.4,'Windup':.78,'Attack':.8,'Recover':1.3,'Hit':.28,'Death':1.8}
if set(a.name for a in bpy.data.actions)!=set(expected):raise RuntimeError('Seven-clip contract mismatch')
def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def fingerprints():
 geometry={o.name:{'vertices':[list(v.co) for v in o.data.vertices],'faces':[list(p.vertices) for p in o.data.polygons],'uv':[[list(d.uv) for d in l.data] for l in o.data.uv_layers],'materials':[m.name for m in o.data.materials]} for o in assets}
 weights={o.name:{'groups':[(g.index,g.name) for g in o.vertex_groups],'weights':[[(g.group,g.weight) for g in v.groups] for v in o.data.vertices]} for o in assets}
 bones={b.name:{'parent':b.parent.name if b.parent else None,'matrix':[list(r) for r in b.matrix_local]} for b in rig.data.bones}
 actions={a.name:digest([(f.data_path,f.array_index,[(list(k.co),list(k.handle_left),list(k.handle_right),k.interpolation) for k in f.keyframe_points]) for f in a.fcurves]) for a in bpy.data.actions}
 return {'geometry':digest(geometry),'weights':digest(weights),'rig':digest(bones),'actions':actions}
before=fingerprints()
for track in rig.animation_data.nla_tracks:track.mute=True
rig.animation_data.action=bpy.data.actions['Death']
scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
scene.render.resolution_x=960;scene.render.resolution_y=540;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.world.color=(.16,.16,.16);scene.view_settings.view_transform='AgX'
bpy.ops.mesh.primitive_plane_add(size=200);ground=bpy.context.object
m=bpy.data.materials.new('ReviewNeutral');m.diffuse_color=(.16,.16,.16,1);ground.data.materials.append(m)
lights=[]
for loc,power in [((-3,-4,5),600),((4,-1,3),280),((0,4,4),400)]:
 bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.size=4
 o.rotation_euler=(Vector((0,0,.4))-o.location).to_track_quat('-Z','Y').to_euler()
 lights.append({'location':list(o.location),'rotation_xyz_radians':list(o.rotation_euler),'power':power,'size':4})
bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=3.6;scene.camera=cam
out.mkdir(parents=True,exist_ok=True);images=[]
for label,seconds,index in [('rest03',1.8,3),('rest07',1.8,7),('mid102',1.02,2),('mid135',1.35,2)]:
 scene.frame_set(1+round(seconds*100));angle=index*math.tau/8
 cam.location=(6*math.sin(angle),-6*math.cos(angle),2.4)
 cam.rotation_euler=(Vector((0,-.12,.4))-cam.location).to_track_quat('-Z','Y').to_euler()
 target=out/('opaque-'+label+'.png');scene.render.filepath=str(target);bpy.ops.render.render(write_still=True)
 images.append({'file':target.name,'sha256':sha(target),'seconds':seconds,'frame':scene.frame_current,'azimuth_degrees':math.degrees(angle),'camera_world_xyz':list(cam.location),'camera_rotation_xyz_radians':list(cam.rotation_euler),'camera_world_matrix':[list(r) for r in cam.matrix_world],'look_at':[0,-.12,.4],'orthographic_scale':3.6})
after=fingerprints()
if before!=after:raise RuntimeError('Rendering changed protected asset data')
for name,h in PIN.items():
 if sha(src/name)!=h:raise RuntimeError('Rendering modified source file')
receipt={'scope':'FOUR_OPAQUE_STILLS_FROM_PINNED_TECHNICAL_ARTIFACT_NOT_FULL','visual_approval':False,'run_id':37854056191,'artifact_id':11582903139,'source_commit':COMMIT,'source_sha256':PIN,'fingerprints_before':before,'fingerprints_after':after,'asset_data_unchanged':True,'lights':lights,'images':images,'resolution':[960,540],'render_engine':'CYCLES','samples':16,'view_transform':'AgX'}
(out/'opaque-receipt.json').write_text(json.dumps(receipt,indent=2))
(out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
