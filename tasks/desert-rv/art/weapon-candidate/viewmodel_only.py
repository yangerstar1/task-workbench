"""Actions-only bounded rendering from the exact R9 blend. Never regenerate/export assets."""
import bpy,sys,pathlib,json,hashlib
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from pixel_evidence import alpha_bounds,is_core_asset,core_fully_visible,core_target_fit
from asset_validation import technical_failures
args=sys.argv[sys.argv.index('--')+1:];source=pathlib.Path(args[0]);out=pathlib.Path(args[1]);out.mkdir(parents=True,exist_ok=True)
locked=json.loads((ROOT/'viewmodel-baseline.json').read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for name,expected in locked['files'].items():
 if digest(source/name)!=expected:raise RuntimeError('Baseline identity mismatch: '+name)
original=json.loads((source/'validation.json').read_text());original_package=json.loads((source/'package-validation.json').read_text())
allowed={'1280x720:core_fully_visible','1280x720:target_fit','1600x720:core_fully_visible','1600x720:target_fit'}
if set(original_package['technical_failures'])!=allowed:raise RuntimeError('Baseline failure scope differs from reviewed framing-only defects')
bpy.ops.wm.open_mainfile(filepath=str(source/'weapon_hands.blend'))
scene=bpy.context.scene;rig=bpy.data.objects['DesertRV_WeaponHands_Rig'];camera=scene.camera
assets=sorted((o for o in scene.objects if o.type=='MESH'),key=lambda o:o.name)
def encode_hash(value):return hashlib.sha256(json.dumps(value,separators=(',',':'),sort_keys=True).encode()).hexdigest()
def asset_fingerprints():
 meshes={}
 for obj in assets:
  meshes[obj.name]=encode_hash({'vertices':[list(v.co) for v in obj.data.vertices],'polygons':[list(p.vertices) for p in obj.data.polygons],'weights':[[(g.group,g.weight) for g in v.groups] for v in obj.data.vertices],'groups':[g.name for g in obj.vertex_groups],'materials':[m.name if m else None for m in obj.data.materials],'parent':obj.parent.name if obj.parent else None,'parent_bone':obj.parent_bone,'modifiers':[(m.type,getattr(getattr(m,'object',None),'name',None)) for m in obj.modifiers]})
 bones=encode_hash([(b.name,b.parent.name if b.parent else None,[list(row) for row in b.matrix_local],b.use_deform) for b in rig.data.bones])
 actions={a.name:encode_hash([(f.data_path,f.array_index,[(list(k.co),list(k.handle_left),list(k.handle_right),k.interpolation) for k in f.keyframe_points]) for f in a.fcurves]) for a in bpy.data.actions}
 materials={}
 for m in bpy.data.materials:
  nodes=[]
  if m.use_nodes:
   for n in m.node_tree.nodes:
    inputs=[]
    for v in n.inputs:
     if hasattr(v,'default_value'):
      value=v.default_value;value=value if isinstance(value,(str,int,float,bool)) else list(value)
      inputs.append((v.name,value,v.is_linked))
    nodes.append((n.name,n.type,inputs))
  materials[m.name]=encode_hash({'diffuse':list(m.diffuse_color),'metallic':m.metallic,'roughness':m.roughness,'nodes':nodes})
 return {'meshes_and_skin_weights':meshes,'bone_rest_hierarchy':bones,'actions':actions,'materials':materials}
before=asset_fingerprints()
if abs(camera.data.shift_x)>1e-8 or abs(camera.data.lens-37.75)>1e-6:raise RuntimeError('Baseline camera differs from reviewed pose')
pose=original['viewmodels']['1280x720']
other=original['viewmodels']['1600x720']
if pose['rig_location']!=other['rig_location'] or pose['rig_euler']!=other['rig_euler']:raise RuntimeError('Baseline pose not aspect-stable')
camera_right=(camera.matrix_world.to_3x3()@Vector((1,0,0))).normalized()
rig.location=Vector(pose['rig_location'])-camera_right*.015;rig.rotation_euler=pose['rig_euler'];rig.animation_data.action=bpy.data.actions['Idle']
for t in rig.animation_data.nla_tracks:t.mute=True
scene.frame_set(1)
if rig.parent is not None:raise RuntimeError('Expected baseline armature at scene root')
scene.render.film_transparent=True;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
views={}
def raw_core_bounds():
 bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get();points=[world_to_camera_view(scene,camera,o.evaluated_get(deps).matrix_world@Vector(v))for o in assets if is_core_asset(o.name) for v in o.evaluated_get(deps).bound_box]
 return [min(p.x for p in points),min(p.y for p in points),max(p.x for p in points),max(p.y for p in points)]
def render_bounds(name,w,h):
 scene.render.filepath=str(out/name);bpy.ops.render.render(write_still=True);im=bpy.data.images.load(scene.render.filepath,check_existing=False)
 try:return alpha_bounds(im.pixels[:],w,h,im.channels)
 finally:bpy.data.images.remove(im)
for w,h in [(1280,720),(1600,720)]:
 key=f'{w}x{h}';scene.render.resolution_x=w;scene.render.resolution_y=h;camera.data.shift_y=original['viewmodels'][key]['camera_shift_y']
 bounds=raw_core_bounds();full=render_bounds(f'viewmodel_{key}.png',w,h)
 sleeves=[o for o in assets if not is_core_asset(o.name)];saved=[o.hide_render for o in sleeves]
 for o in sleeves:o.hide_render=True
 core=render_bounds(f'viewmodel_core_{key}.png',w,h)
 for o,state in zip(sleeves,saved):o.hide_render=state
 item=dict(original['viewmodels'][key]);item.update({'normalized_bounds':core,'core_alpha_bounds':core,'full_alpha_bounds':full,'unclipped_core_bounds':bounds,'width_fraction':core[2]-core[0],'height_fraction':core[3]-core[1],'core_fully_visible':core_fully_visible(bounds),'target_fit':core_target_fit(core,bounds),'center_clear':not(core[0]<=.5<=core[2] and core[1]<=.5<=core[3]),'sleeves_reach_lower_edge':full[1]<=1/h,'camera_shift_x':camera.data.shift_x,'rig_location':list(rig.location),'rig_camera_plane_offset_m':[-.015,0,0],'stable_pose_id':'R10_R9_plus15mm_camera_left'})
 views[key]=item
 if not(bounds[0]<original['viewmodels'][key]['unclipped_core_bounds'][0] and bounds[2]<original['viewmodels'][key]['unclipped_core_bounds'][2]):raise RuntimeError('Expected leftward rig shift was not observed')
after=asset_fingerprints();unchanged=before==after
files_after={name:digest(source/name) for name in locked['files']};files_unchanged=files_after==locked['files']
merged=dict(original);merged['viewmodels']=views
failures=technical_failures(merged)
if not unchanged:failures.append('asset_semantics_changed')
if not files_unchanged:failures.append('source_file_bytes_changed')
(out/'viewmodel-validation.json').write_text(json.dumps({'scope':'viewmodel-only','new_full_run':False,'viewmodels':views,'technical_failures':failures},indent=2))
(out/'asset-equivalence.json').write_text(json.dumps({'baseline':locked,'asset_fingerprints_before':before,'asset_fingerprints_after':after,'identical_mesh_skin_bone_animation':unchanged,'source_files_after':files_after,'all_source_files_byte_identical':files_unchanged,'model_reexported':False,'only_presentation_change':{'rig_camera_plane_offset_m':[-.015,0,0]},'camera_projection_unchanged':camera.data.shift_x==0 and abs(camera.data.lens-37.75)<1e-6,'original_display_location':pose['rig_location'],'new_display_location':list(rig.location),'unity_equivalence':'Must apply and measure actual camera-relative weapon instance offset after import; no gameplay-camera projection changes authorized'},indent=2))
(out/'combined-technical-evidence.json').write_text(json.dumps({'scope':'R9 unchanged-asset evidence plus bounded framing replacement','source_run':locked['run_id'],'source_original_result':'failure','source_original_failed_gates':original_package['technical_failures'],'replaced_evidence':['viewmodels.1280x720','viewmodels.1600x720'],'reused_evidence_identity':'asset-equivalence.json','new_full_run':False,'visual_approved':False,'unity_muzzle_alignment_verified':False,'combined_technical_evidence_pass':not failures,'remaining_failures':failures},indent=2))
if failures:raise RuntimeError('Bounded framing rejected: '+', '.join(failures))
