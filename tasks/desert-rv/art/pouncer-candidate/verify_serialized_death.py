"""Actions-only independent reimport/sample of actual GLB or FBX at 200Hz.
A GLB quaternion pass cannot replace native Euler or FBX-import curve validation.
"""
import argparse,hashlib,json,re,struct,sys
from pathlib import Path
import bpy
p=argparse.ArgumentParser();p.add_argument('--format',choices=['glb','fbx'],required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=Path(a.output);gate_path=out/'technical-gate.json';gate=json.loads(gate_path.read_text())
if not gate.get('source_native_pass'):raise RuntimeError('Native source gate did not pass')
errors=[];rows=[];report={'format':a.format,'scope':'SERIALIZED_DEATH_REIMPORT_NOT_FULL','passed':False}
try:
    bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.render.fps=100;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    path=out/('pouncer-candidate.'+a.format)
    if a.format=='glb':
        # Establish provenance from the actual serialized asset, not object-name guesses.
        raw=path.read_bytes();length,kind=struct.unpack_from('<II',raw,12)
        if kind!=0x4e4f534a:raise RuntimeError('Missing GLB JSON chunk')
        document=json.loads(raw[20:20+length]);source_nodes=[{'node_index':i,'name':n.get('name'),'mesh':n['mesh'],'skin':n.get('skin')} for i,n in enumerate(document['nodes']) if 'mesh' in n]
        if len(source_nodes)!=27 or any(n['skin']!=0 for n in source_nodes):raise RuntimeError('Pinned candidate must retain all27 serialized skin0 mesh nodes')
        expected={n['name'] for n in source_nodes}
        if None in expected or len(expected)!=len(source_nodes):raise RuntimeError('Source mesh-node names are not unique; explicit mapping required')
        # First collect the old import behavior as evidence. This scene is never sampled.
        bpy.ops.import_scene.gltf(filepath=str(path),import_pack_images=True,merge_vertices=False,bone_heuristic='BLENDER')
        custom_users={}
        for arm in [o for o in scene.objects if o.type=='ARMATURE']:
            for pb in arm.pose.bones:
                if pb.custom_shape:custom_users.setdefault(pb.custom_shape.name,[]).append(arm.name+'/'+pb.name)
        provenance=[];unknown=[]
        for obj in [o for o in scene.objects if o.type=='MESH']:
            collections=[{'name':c.name,'hide_render':c.hide_render,'hide_viewport':c.hide_viewport} for c in obj.users_collection]
            row={'object':obj.name,'mesh_datablock':obj.data.name,'in_source_mesh_nodes':obj.name in expected,'object_hide_render':obj.hide_render,'collections':collections,'custom_shape_users':custom_users.get(obj.name,[]),'armature_modifier_count':sum(m.type=='ARMATURE' for m in obj.modifiers)}
            row['confirmed_importer_only_display_shape']=not row['in_source_mesh_nodes'] and bool(row['custom_shape_users']) and bool(collections) and all(c['hide_render'] for c in collections) and row['armature_modifier_count']==0
            if not row['in_source_mesh_nodes'] and not row['confirmed_importer_only_display_shape']:unknown.append(row)
            provenance.append(row)
        report['import_provenance']={'source_meshes':len(document['meshes']),'source_mesh_nodes':source_nodes,'default_import_objects':provenance,'confirmed_helper_count':sum(r['confirmed_importer_only_display_shape'] for r in provenance)}
        (out/'glb-import-provenance.json').write_text(json.dumps(report['import_provenance'],indent=2))
        if unknown:raise RuntimeError('Unexpected imported meshes are not proven display helpers: '+str([r['object'] for r in unknown]))
        # Prevent helper creation using the official importer switch. No mesh is filtered
        # out of the final scene or the floor test, by name, visibility or otherwise.
        bpy.ops.wm.read_factory_settings(use_empty=True);scene=bpy.context.scene;scene.render.fps=100;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
        bpy.ops.import_scene.gltf(filepath=str(path),import_pack_images=True,merge_vertices=False,bone_heuristic='BLENDER',disable_bone_shape=True)
        actual=[o for o in scene.objects if o.type=='MESH']
        if len(actual)!=len(source_nodes) or {o.name for o in actual}!=expected:raise RuntimeError('Final imported mesh set does not exactly match serialized source nodes')
        links=[]
        for obj in actual:
            skinned=next(n for n in source_nodes if n['name']==obj.name)['skin'] is not None
            linked=[m.object.name for m in obj.modifiers if m.type=='ARMATURE' and m.object]
            if skinned and not linked and not (obj.parent and obj.parent.type=='ARMATURE' and obj.parent_type=='BONE'):raise RuntimeError('Source skin has lost its armature link: '+obj.name)
            links.append({'object':obj.name,'armature_targets':linked,'bone_parent':obj.parent_bone if obj.parent_type=='BONE' else None})
        report['import_provenance']['final_mesh_links']=links;report['import_provenance']['final_mesh_count']=len(actual)
        (out/'glb-import-provenance.json').write_text(json.dumps(report['import_provenance'],indent=2))
    else:bpy.ops.import_scene.fbx(filepath=str(path),use_anim=True,anim_offset=1.0,automatic_bone_orientation=False,use_prepost_rot=True)
    arms=[o for o in scene.objects if o.type=='ARMATURE'];meshes=[o for o in scene.objects if o.type=='MESH']
    if len(arms)!=1 or not meshes:raise RuntimeError('Expected one imported armature and actual meshes')
    rig=arms[0];candidates=set()
    for tr in rig.animation_data.nla_tracks:
        if 'Death' in re.split(r'[^A-Za-z0-9]+',tr.name):candidates.update(s.action for s in tr.strips if s.action)
        tr.mute=True
    for action in bpy.data.actions:
        if 'Death' in re.split(r'[^A-Za-z0-9]+',action.name) and any(f.data_path.startswith('pose.bones[') for f in action.fcurves):candidates.add(action)
    if len(candidates)!=1:raise RuntimeError('Cannot uniquely resolve imported Death: '+str([x.name for x in candidates]))
    action=next(iter(candidates));rig.animation_data.action=action;start,end=action.frame_range;duration=(end-start)/scene.render.fps
    if abs(duration-1.8)>1e-5:errors.append('Imported Death duration is not1.8s')
    root=rig.pose.bones.get('root')
    if root is None:raise RuntimeError('Imported gameplay root missing')
    root_reference=None;max_root_delta=0
    for i in range(361):
        frame=start+i*scene.render.fps/200;scene.frame_set(int(frame),subframe=frame-int(frame));deps=bpy.context.evaluated_depsgraph_get();low=None;high=-1e9
        for obj in meshes:
            ev=obj.evaluated_get(deps);me=ev.to_mesh();positions=[ev.matrix_world@v.co for v in me.vertices];index=min(range(len(positions)),key=lambda n:positions[n].z);high=max(high,max(v.z for v in positions))
            if low is None or positions[index].z<low['minimum_z']:low={'mesh':obj.name,'vertex':index,'minimum_z':positions[index].z,'world_xyz_m':list(positions[index])}
            ev.to_mesh_clear()
        current=rig.matrix_world@root.matrix
        if root_reference is None:root_reference=current.copy()
        max_root_delta=max(max_root_delta,max(abs(current[r][c]-root_reference[r][c]) for r in range(4) for c in range(4)))
        rows.append({'seconds':i/200,'maximum_z':high,**low})
    worst=min(rows,key=lambda r:r['minimum_z'])
    if worst['minimum_z']<-.004:errors.append('Imported all-mesh penetration exceeds4mm')
    if any(abs(rows[i]['minimum_z'])>.02 for i in (0,-1)):errors.append('Imported endpoint loses floor contact')
    if not .3<max(r['maximum_z'] for r in rows)<2:errors.append('Imported metric scale/orientation is wrong')
    if max_root_delta>1e-5:errors.append('Imported gameplay root moves')
    report.update({'passed':not errors,'action':action.name,'frame_range':[start,end],'duration_seconds':duration,'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'maximum_penetration_m':max(0,-worst['minimum_z']),'worst_sample':worst,'root_matrix_max_delta':max_root_delta})
except Exception as exc:errors.append(str(exc))
report['errors']=errors;(out/(a.format+'-native-reimport.json')).write_text(json.dumps(report,indent=2));(out/(a.format+'-native-200hz.json')).write_text(json.dumps(rows,indent=2))
gate.setdefault('serialized_native_checks',{})[a.format]=report
for error in errors:gate['errors'].append(a.format+' native reimport: '+error)
if gate['errors']:gate['status']='DEATH_TECHNICAL_FAIL'
elif set(gate['serialized_native_checks'])=={'glb','fbx'} and all(r['passed'] for r in gate['serialized_native_checks'].values()):gate['status']='DEATH_TECHNICAL_PASS_NOT_FULL'
else:gate['status']='DEATH_NATIVE_SOURCE_PASS_PENDING_IMPORTS'
gate_path.write_text(json.dumps(gate,indent=2));print(json.dumps(report),flush=True)
if errors:raise RuntimeError('; '.join(errors))
