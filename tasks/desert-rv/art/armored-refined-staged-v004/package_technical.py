"""Bounded technical FULL source package; never asserts Unity, movies or visual approval."""
import argparse,hashlib,json,os,shutil,struct
from pathlib import Path
import staged,plan
from artifact_io import fresh_output
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,why):
    if not ok:raise ValueError(why)
def static_prerequisite():
    lock=staged.verify_source();p=HERE/'static-prerequisite'
    status=json.loads((p/'STATUS.json').read_text());prov=json.loads((p/'provenance.json').read_text());checks=json.loads((p/'static-checks.json').read_text())
    require(status['status']=='COMPLETE_TECHNICAL_EVIDENCE_NOT_VISUAL_APPROVAL' and not status['errors'],'static prerequisite failed')
    require(status['run_id']==lock['prerequisite_static']['run_id'] and prov['source_commit']==lock['source_commit'],'static run identity')
    require(prov['source_manifest_sha256']==lock['source_manifest_sha256'],'static source identity')
    require(len(checks)==56 and all(not x['errors'] for x in checks),'all static checks required')
    require(all(x['min_z']>=-.004 for x in checks),'static floor threshold')
    return lock
def package(source,destination,exit_code):
    lock=static_prerequisite();source=Path(source);dst=fresh_output(Path(destination));errors=[]
    required=['bulwark-candidate.fbx','bulwark-animations.fbx','bulwark-candidate.glb','bulwark-basecolor.png','bulwark-orm.png','bulwark-review.blend','evaluated-validation.json','clip-manifest.json','binding-contract.json','output-sha256.json','stage-receipt.json','ASSET-LICENSE.json']+['numeric-'+c+'.json' for c in plan.REMAINING]
    total=0
    for name in required:
        p=source/name
        if not p.is_file() or p.is_symlink():errors.append('missing/invalid '+name);continue
        total+=p.stat().st_size
        if total>512*1024**2 or p.stat().st_size>256*1024**2:errors.append('bounded size '+name);continue
        shutil.copyfile(p,dst/name)
    try:
        require(exit_code==0,'technical process failed')
        receipt=staged.verify_receipt(source,'technical',lock)
        staged.verify_payload_manifest(source)
        require(receipt['art_source_commit']==lock['source_commit'] and receipt['execution_manifest_sha256']==sha(HERE/'execution-manifest.json'),'frozen art/executor identity')
        require(receipt['execution_commit']==os.environ['GITHUB_SHA'] and str(receipt['run_id'])==os.environ['GITHUB_RUN_ID'] and str(receipt['run_attempt'])==os.environ['GITHUB_RUN_ATTEMPT'],'same run receipt required')
        clips=json.loads((source/'clip-manifest.json').read_text());require(len(clips)==7 and {c['name'] for c in clips}==set(plan.P['clips']),'seven clips required')
        for c in clips:require(not c['root_motion'] and abs(c['duration_seconds']-plan.P['clips'][c['name']])<=1/120,'clip duration/root contract')
        for name in ['bulwark-basecolor.png','bulwark-orm.png']:
            raw=(source/name).read_bytes();require(raw[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',raw[16:24])==(1024,1024),'exact1024 atlas '+name)
        for name in ['bulwark-candidate.fbx','bulwark-animations.fbx']:require((source/name).read_bytes().startswith(b'Kaydara FBX Binary'),'binary FBX '+name)
        require((source/'bulwark-candidate.glb').read_bytes()[:4]==b'glTF','GLB header')
        binding=json.loads((source/'binding-contract.json').read_text());require(binding['status']=='source_graph_checked_import_unverified' and not binding['failures'],'binding gate')
    except (ValueError,KeyError,OSError,TypeError,struct.error) as exc:errors.append(str(exc))
    declaration={'scope':'FULL_CANDIDATE' if not errors else 'PARTIAL_DIAGNOSTIC_NOT_FULL','status':'FULL_SOURCE_ASSETS_NOT_UNITY_APPROVAL' if not errors else 'PARTIAL_FAILED_NOT_A_SUCCESS','errors':errors,'artSourceCommit':lock['source_commit'],'executionCommit':os.environ['GITHUB_SHA'],'runId':os.environ['GITHUB_RUN_ID'],'sourceManifestSha256':lock['source_manifest_sha256'],'executionManifestSha256':sha(HERE/'execution-manifest.json'),'textureContract':{'bulwark-basecolor.png':{'width':1024,'height':1024,'colorSpace':'sRGB'},'bulwark-orm.png':{'width':1024,'height':1024,'colorSpace':'linear','channels':'R=occlusion,G=roughness,B=metallic'}},'capsuleContract':plan.P['capsule_contract'],'visualApproved':False,'unityVerified':False,'moviesComplete':False,'movieReview':'NOT_RUN','unityVisualReview':'NOT_RUN','staticPrerequisite':lock['prerequisite_static']}
    (dst/'producer-contract.json').write_text(json.dumps(declaration,indent=2)+'\n')
    shutil.copyfile(staged.ART/'source-manifest.json',dst/'source-manifest.json');shutil.copyfile(HERE/'execution-manifest.json',dst/'execution-manifest.json')
    (dst/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in sorted(dst.iterdir()) if p.is_file()))
    print(json.dumps(declaration,indent=2));return 1 if errors else 0
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--verify-static',action='store_true');p.add_argument('--source');p.add_argument('--output');p.add_argument('--exit-code',type=int);a=p.parse_args()
    if a.verify_static:static_prerequisite();print('FROZEN_STATIC_PREREQUISITE_VERIFIED')
    else:raise SystemExit(package(a.source,a.output,a.exit_code))
