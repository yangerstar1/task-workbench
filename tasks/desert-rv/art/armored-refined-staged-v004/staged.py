"""Actions-only Blender orchestrator. Immutable original art modules are reused byte-for-byte.
Technical checks/export precede any videos. Render chunks contain at most 24 actual frames.
"""
import argparse, ast, copy, hashlib, json, math, os, shutil, struct, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; ART=HERE.parent/'armored-refined-v004'
sys.path.insert(0,str(HERE)); sys.path.insert(0,str(ART))
import plan
from artifact_io import fresh_output

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verify_source():
    lock=json.loads((HERE/'art-lock.json').read_text())
    if sha(ART/'source-manifest.json')!=lock['source_manifest_sha256']:raise ValueError('Pinned revised art manifest changed')
    for name,digest in lock['source_files'].items():
        if sha(ART/name)!=digest:raise ValueError('Pinned revised art changed: '+name)
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    for name,digest in manifest['sha256'].items():
        if sha(HERE/name)!=digest:raise ValueError('Executor changed: '+name)
    proof=json.loads((ART/lock['historical_equivalence_proof']).read_text()) if lock.get('historical_equivalence_proof') else None
    if proof:
        if proof['historical_manifest_sha256']!=lock['reused_manifest_sha256']:raise ValueError('Historical proof identity mismatch')
        for item in proof['clips'].values():
            if item['original_sha256']!=item['current_sha256']:raise ValueError('Historical motion equivalence failed')
    return lock

def technical_payload_names():
    return ['bulwark-candidate.fbx','bulwark-animations.fbx','bulwark-candidate.glb','bulwark-basecolor.png','bulwark-orm.png','bulwark-review.blend','evaluated-validation.json','clip-manifest.json','binding-contract.json','ASSET-LICENSE.json']+['numeric-'+c+'.json' for c in plan.REMAINING]

def write_payload_manifest(output):
    # No self-reference or mutable receipt: final stage receipt pins this immutable layer.
    files={}
    for name in technical_payload_names():
        path=output/name
        if path.is_symlink() or not path.is_file():raise ValueError('Missing technical payload '+name)
        files[name]=sha(path)
    atomic_json(output/'output-sha256.json',files)

def verify_payload_manifest(output):
    files=json.loads((output/'output-sha256.json').read_text())
    if set(files)!=set(technical_payload_names()):raise ValueError('Payload manifest exact keys mismatch')
    for name,digest in files.items():
        path=output/name
        if path.is_symlink() or not path.is_file() or sha(path)!=digest:raise ValueError('Payload manifest bytes mismatch '+name)
    return files

def atomic_json(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)

def base_receipt(stage,lock):
    return {'stage':stage,'status':'PARTIAL_NOT_COMPLETE','art_source_commit':lock['source_commit'] or os.environ.get('GITHUB_SHA'),'art_source_manifest_sha256':lock['source_manifest_sha256'],'execution_commit':os.environ.get('GITHUB_SHA'),'execution_manifest_sha256':sha(HERE/'execution-manifest.json'),'run_id':os.environ.get('GITHUB_RUN_ID'),'run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'blender_version':'4.2.3','quality':{'samples':24,'width':960,'height':540,'engine':'CYCLES','technical_hz':60,'baked_subframe_floor_hz':240,'new_diagnostic_nominal_hz':30,'endpoint_policy':'include exact final original frame; VFR retains original 1/60 final exposure'},'visual_approved':False,'unity_verified':False,'files':{}}

def verify_receipt(folder,stage,lock):
    folder=Path(folder);r=json.loads((folder/'stage-receipt.json').read_text())
    if r['stage']!=stage or r['status']!='COMPLETE_TECHNICAL_EVIDENCE_NOT_VISUAL_APPROVAL' or r['art_source_manifest_sha256']!=lock['source_manifest_sha256']:raise ValueError('Wrong/incomplete prerequisite')
    for name,digest in r['files'].items():
        if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Invalid prerequisite path')
        f=folder/name
        if f.is_symlink() or not f.is_file() or sha(f)!=digest:raise ValueError('Prerequisite checksum mismatch '+name)
    if stage=='technical':
        required={'evaluated-validation.json','clip-manifest.json','binding-contract.json','bulwark-candidate.glb','bulwark-candidate.fbx','bulwark-animations.fbx','bulwark-review.blend'}
        if not required.issubset(r['files']):raise ValueError('Technical receipt missing required outputs')
        validation=json.loads((folder/'evaluated-validation.json').read_text())
        if validation['failures'] or validation['status']!='technical_checks_passed_visual_review_still_required':raise ValueError('Technical checks did not pass')
    return r

def finalize_receipt(output,receipt):
    if receipt['stage']=='technical':
        receipt['files']={str(f.relative_to(output)):sha(f) for f in output.rglob('*') if f.is_file() and f.name!='stage-receipt.json'}
    atomic_json(output/'stage-receipt.json',receipt)

def bootstrap(output):
    # The last statement alone launches old monolithic animate.py. Skip only that
    # dispatch; all geometry, rig, materials, camera and quality code is unchanged.
    tree=ast.parse((ART/'generate.py').read_text())
    if 'animate.py' not in ast.unparse(tree.body[-1]):raise ValueError('Unexpected generator structure')
    env={'__file__':str(ART/'generate.py'),'__name__':'__main__'}
    sys.argv=['blender','--','--output',str(output),'--phase','motion']
    exec(compile(ast.Module(body=tree.body[:-1],type_ignores=[]),str(ART/'generate.py'),'exec'),env)
    motion_tree=ast.parse((ART/'animate.py').read_text())
    create=next(n for n in motion_tree.body if isinstance(n,ast.FunctionDef) and n.name=='create_action')
    review=next(n for n in motion_tree.body if isinstance(n,ast.FunctionDef) and n.name=='review_action')
    # Reuse the entire original first per-frame validation loop without alteration.
    end=next(i for i,n in enumerate(review.body) if isinstance(n,ast.For))
    validate=copy.deepcopy(review);validate.name='validate_action';validate.body=validate.body[:end+1]
    env.update(checks=[],clip_rows=[],actions=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[create,validate],type_ignores=[])),str(ART/'animate.py'),'exec'),env)
    return env,motion_tree

def sampler(env,clip):
    m=env['motion']
    if clip in plan.P['clips']:return plan.P['clips'][clip],lambda t:m.sample(clip,t),lambda t:m.travel(clip,t)
    phase=float(clip.rsplit('_',1)[1]);lead=min(.35,phase)
    return lead+.6,lambda t:m.sample('Attack',phase-lead+t) if t<lead else m.interrupted(phase,t-lead),lambda t:plan.P['charge_speed_mps']*min(t,lead)

def technical(env,tree,output):
    for clip in list(plan.P['clips'])+[c for c in plan.REMAINING if c.startswith('SYNTHETIC')]:
        duration,fn,travel=sampler(env,clip);act,n=env['create_action'](clip,duration,fn)
        start=len(env['checks']);env['validate_action'](clip,act,n,fn,travel)
        # Additional true baked subframe floor test. This evaluates the actual fcurves,
        # not another call to the analytic sampler, and never renders anything.
        for frame in range(1,n):
            for sub in (.25,.5,.75):
                t=(frame-1+sub)/60;env['scene'].frame_set(frame,subframe=sub);env['rig'].location=(0,-travel(t),0)
                env['bpy'].context.view_layer.update();env['camera'](math.pi*.65,(0,-travel(t)-.1,.55))
                env['set_presentation'](clip=='Recover' or (clip.startswith('SYNTHETIC') and fn(t)['gate']>0))
                row=env['validate_frame'](clip+':'+str(frame+sub));row['time']=t;row['baked_subframe']=True;env['checks'].append(row)
        atomic_json(output/('numeric-'+clip+'.json'),{'clip':clip,'integer_hz':60,'baked_subframe_floor_hz':240,'checks':env['checks'][start:]})
        env['rig'].location=(0,0,0)
        if clip in plan.P['clips']:
            env['actions'].append(act);env['clip_rows'].append({'name':clip,'frames':n,'duration_seconds':(n-1)/60,'requested_seconds':duration,'loop':clip in ('Idle','Walk','Attack'),'root_motion':False})
        else:env['rig'].animation_data.action=None;env['bpy'].data.actions.remove(act)
    env['set_presentation'](False);env['validate_binding_contract']()
    env['rig'].animation_data.action=env['actions'][0];env['scene'].frame_set(1)
    for i in range(16):
        env['camera'](i*math.tau/16);env['checks'].append(env['validate_frame']('turntable-'+str(i)))
    # Original report, gates and export tail, no render calls or skipped conditions.
    start=next(i for i,n in enumerate(tree.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='triangles' for t in n.targets))
    tail=ast.Module(body=tree.body[start:],type_ignores=[])
    if 'render(' in ast.unparse(tail) or 'still(' in ast.unparse(tail):raise ValueError('Unexpected render in export tail')
    env['hashlib']=hashlib;exec(compile(tail,str(ART/'animate.py'),'exec'),env)

def render_chunk(env,clip,index,output,receipt,resume=None):
    if clip not in plan.REMAINING:raise ValueError('Completed legacy clips are not in remaining render plan')
    if index is None or not 0<=index<len(plan.chunks(clip)):raise ValueError('Chunk index out of bounds')
    targets=plan.chunks(clip)[index];duration,fn,travel=sampler(env,clip)
    act,n=env['create_action'](clip,duration,fn);env['rig'].animation_data.action=act
    receipt.update(clip=clip,chunk=index,original_frame_indices=targets,frames=[])
    atomic_json(output/'stage-receipt.json',receipt)
    completed={}
    if resume:
        prior=json.loads((Path(resume)/'stage-receipt.json').read_text())
        if prior.get('clip')!=clip or prior.get('chunk')!=index or prior.get('art_source_manifest_sha256')!=receipt['art_source_manifest_sha256'] or prior.get('execution_manifest_sha256')!=receipt['execution_manifest_sha256'] or prior.get('quality')!=receipt['quality']:raise ValueError('Resume identity mismatch')
        for frame in prior.get('frames',[]):
            if frame['file']!=f"frames/{frame['original_frame']:04}.png" or frame.get('original_time_seconds')!=(frame['original_frame']-1)/60:raise ValueError('Invalid resume path')
            source=Path(resume)/frame['file']
            if frame['original_frame'] not in targets or source.is_symlink() or sha(source)!=frame['sha256']:raise ValueError('Resume frame invalid')
            completed[frame['original_frame']]=(source,frame)
    for frame in targets:
        t=(frame-1)/60;target=output/'frames'/f'{frame:04}.png';target.parent.mkdir(exist_ok=True)
        if frame in completed:
            source,row=completed[frame];shutil.copyfile(source,target);row=dict(row);row['reused_from_chunk_run']=prior['run_id']
        else:
            env['scene'].frame_set(frame);env['rig'].location=(0,-travel(t),0);env['bpy'].context.view_layer.update()
            env['camera'](math.pi*.65,(0,-travel(t)-.1,.55));env['set_presentation'](clip=='Recover' or (clip.startswith('SYNTHETIC') and fn(t)['gate']>0))
            check=env['validate_frame'](clip+':'+str(frame))
            if check['errors']:raise ValueError(check)
            env['still'](target)
            raw=target.read_bytes()[:24]
            if raw[:8]!=b'\x89PNG\r\n\x1a\n' or struct.unpack('>II',raw[16:24])!=(960,540):raise ValueError('Incomplete frame')
            row={'original_frame':frame,'original_time_seconds':t,'file':str(target.relative_to(output)),'sha256':sha(target),'check':check}
        receipt['frames'].append(row);receipt['files'][row['file']]=row['sha256'];atomic_json(output/'stage-receipt.json',receipt)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['technical','chunk'],required=True);ap.add_argument('--output',required=True);ap.add_argument('--technical');ap.add_argument('--clip');ap.add_argument('--chunk',type=int);ap.add_argument('--resume')
    a=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);lock=verify_source();output=Path(a.output).resolve()
    # Generator itself owns its fresh-output rejection. Never place receipts there first.
    if output.exists() and any(output.iterdir()):raise ValueError('Refuse nonempty output')
    if a.stage=='chunk':verify_receipt(a.technical,'technical',lock)
    receipt=base_receipt(a.stage,lock)
    try:
        env,tree=bootstrap(output)
        shutil.copyfile(ART/"materials/ASSET-LICENSE.json",output/"ASSET-LICENSE.json")
        atomic_json(output/'stage-receipt.json',receipt)
        if env['scene'].cycles.samples!=24 or (env['scene'].render.resolution_x,env['scene'].render.resolution_y)!=(960,540):raise ValueError('Original render quality changed')
        if a.stage=='technical':
            technical(env,tree,output)
            write_payload_manifest(output)
            verify_payload_manifest(output)
        else:render_chunk(env,a.clip,a.chunk,output,receipt,a.resume)
        receipt['status']='COMPLETE_TECHNICAL_EVIDENCE_NOT_VISUAL_APPROVAL'
    except Exception as exc:
        receipt['error']=str(exc);raise
    finally:
        if output.is_dir():
            finalize_receipt(output,receipt)
if __name__=='__main__':main()
