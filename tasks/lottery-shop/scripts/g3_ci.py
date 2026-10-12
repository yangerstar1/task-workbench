#!/usr/bin/env python3
"""G3 bounded CI adapter. Baseline G0/G2 validators remain byte-for-byte unchanged.
All reported results require actual runner evidence; no Unity/.NET fallback runs here.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
sys.dont_write_bytecode = True
import g2_ci as g2

legacy = g2.legacy
require, digest, bounded_read, write_json = g2.require, g2.digest, g2.bounded_read, g2.write_json
TASK, RULES_SHA = g2.TASK, g2.RULES_SHA
BASE = '06814f520041676a50601f4e70d5ee09eae10078'
SCOPE = 'G3_ONE_DAY_WHITEBOX_NOT_DEVICE_TESTED'
STANDARDS_DIGEST = '1984cc8f225db73485a052942d30637127679a56b0492edf36497911373f30b1'
REQUEST = dict(schemaVersion=1, requestId='lottery-g3-20261012-01', baseCommit=BASE, purpose='G3_ONE_DAY_WHITEBOX')
REQUEST_PATH = TASK + '/ci/g3-request.json'
SCENE = 'Assets/G3/Scenes/G3Day.unity'
GENERATED = {SCENE, SCENE + '.meta', 'Assets/G3/Scenes.meta'}
STAGES = ('regression-edit', 'regression-play', 'edit', 'play', 'android')
G0_GENERATED = {'Assets/GeneratedProbe.meta'} | {'Assets/GeneratedProbe/'+name+suffix for name,suffixes in
    (('Pipeline',('.asset','.asset.meta')),('Renderer',('.asset','.asset.meta')),('Probe',('.unity','.unity.meta')),('ProbeSurface',('.mat','.mat.meta'))) for suffix in suffixes}
ARTWORK = {'number':'aa9cd14c555cb2db4b402508ddee91e65a02b415e9226a0d99270b3d2e823e14',
           'challenge':'4d1bc2a0999439014db391bd1754ef053f8729f699dbc02af05100ddc83a5384'}
BASELINE_CONTRACT_SHA = 'aad7c41d07d4307b4885353e3bc829b1942d58da20363306018b07e64f47f2bb'

@contextlib.contextmanager
def configured():
    """Bind legacy helpers only within this G3 invocation, never mutate baseline files."""
    saved = {k: getattr(legacy, k) for k in ('BASE', 'SCOPE', 'REQUEST', 'REQUEST_PATH', 'mutation_kind')}
    old_binding = g2.normalization_binding
    original_kind = legacy.mutation_kind
    legacy.BASE, legacy.SCOPE, legacy.REQUEST, legacy.REQUEST_PATH = BASE, SCOPE, REQUEST, REQUEST_PATH
    def mutation_kind(path):
        if path in GENERATED:return 'G3_GENERATED_SCENE'
        kind=original_kind(path)
        if kind=='GENERATED_PROBE_ASSET' and path not in G0_GENERATED:return 'UNEXPECTED_SOURCE_CHANGE'
        return kind
    legacy.mutation_kind=mutation_kind
    def binding(identity, stage):
        require(stage in STAGES, 'Unexpected G3 audit stage')
        return dict(stage=stage, **{k: identity[k] for k in ('sourceCommit','runId','runAttempt','requestId')})
    g2.normalization_binding = binding
    try: yield
    finally:
        for key, value in saved.items(): setattr(legacy, key, value)
        g2.normalization_binding = old_binding


def baseline_contract(task):
    require(digest(task / 'ci/g2-test-contract.json') == BASELINE_CONTRACT_SHA, 'G2 baseline contract bytes changed')
    profiles = g2.load_contract(task / 'ci/g2-test-contract.json')
    require(sum(map(len, profiles['edit'].values())) == 45 and sum(map(len, profiles['play'].values())) == 8,
            'G2 exact regression count changed')
    return profiles


def load_contract(task):
    data = json.loads(bounded_read(task / 'ci/g3-test-contract.json', 128*1024))
    require(set(data) == {'schemaVersion','status','rulesSha256','profiles','frames'} and
            type(data['schemaVersion']) is int and data['schemaVersion'] == 1 and
            data['status'] == 'FROZEN_FOR_CI' and data['rulesSha256'] == RULES_SHA, 'G3 contract not frozen')
    profiles = data['profiles']; baseline = baseline_contract(task)
    require(set(profiles) == set(STAGES)-{'android'}, 'G3 native profiles mismatch')
    require(profiles['regression-edit'] == baseline['edit'] and profiles['regression-play'] == baseline['play'], 'G2 regression identities changed')
    for profile in ('edit','play'):
        assemblies = profiles[profile]; wanted = 'Lottery.G3.' + ('EditMode' if profile == 'edit' else 'PlayMode') + '.Tests.dll'
        require(isinstance(assemblies,dict) and set(assemblies)=={wanted}, 'G3 assembly ownership mismatch')
        names = assemblies[wanted]
        require(isinstance(names,list) and 1 <= len(names) <= 512 and len(names)==len(set(names)) and
                all(isinstance(n,str) and re.fullmatch(r'Lottery\.G3\.[A-Za-z0-9_.]+',n) for n in names), 'G3 exact cases missing')
    frames=data['frames']
    require(isinstance(frames,list) and 10 <= len(frames) <= 20 and len(frames)==len(set(frames)) and
            all(isinstance(f,str) and re.fullmatch(r'[a-z][a-z0-9-]{1,40}',f) for f in frames), 'G3 capture contract incomplete')
    return data


REVIEW_PATH = TASK+'/ci/g3-preflight.review.json'
REVIEW_EXCEPTIONS = {REQUEST_PATH, REVIEW_PATH}
WORKFLOWS = {'.github/workflows/lottery-'+x+'.yml' for x in ('g0','g2','g3')}
# These are outputs, not implicit source/import search directories. Exact paths only.
OUTPUT_ROOTS = {TASK+'/'+x for x in ('artifacts','evidence','build','unity/Library','unity/Temp','unity/Obj','unity/Logs','unity/UserSettings')}


def source_path(name):
    # Bind every file in the task, including parent-level MSBuild/NuGet configuration,
    # README and ignore files. No source-extension or child-directory whitelist.
    return name.startswith(TASK+'/') or name in WORKFLOWS


def git_tree(root, ref):
    require(ref=='HEAD' or re.fullmatch(r'[0-9a-f]{40}',ref), 'Invalid tree reference')
    raw=subprocess.check_output(['git','-C',str(root),'ls-tree','-rz',ref])
    require(len(raw)<=8*1024*1024, 'Repository tree exceeds reviewed bound')
    result={}
    for record in raw.split(b'\0'):
        if not record:continue
        meta,name=record.split(b'\t',1);mode,kind,oid=meta.decode('ascii').split(' ');name=name.decode('utf-8')
        require(name not in result and not name.startswith('/') and all(x not in ('','.','..') for x in name.split('/')), 'Invalid Git tree path')
        result[name]=(mode,kind,oid)
    require(0<len(result)<=50000,'Repository tree file bound')
    return result


def verify_review_tree(root, reviewed_commit):
    before=git_tree(root,reviewed_commit);after=git_tree(root,'HEAD')
    # Entire repository equality catches automatic imports, modes, links, deletions
    # and arbitrary new paths, even outside the materialized sparse checkout.
    require({k:v for k,v in before.items() if k not in REVIEW_EXCEPTIONS}==
            {k:v for k,v in after.items() if k not in REVIEW_EXCEPTIONS},
            'Unreviewed repository tree change')
    return after


def reviewed_files(root, committed=False, ref='HEAD'):
    if committed:
        tree=git_tree(root,ref);names=[n for n in tree if source_path(n) and n not in REVIEW_EXCEPTIONS]
        require(0<len(names)<=4096,'Committed input set bound')
        require(all(tree[n][0] in ('100644','100755') and tree[n][1]=='blob' for n in names),'Non-regular execution input refused')
        return {n:hashlib.sha256(subprocess.check_output(['git','-C',str(root),'show',ref+':'+n])).hexdigest() for n in sorted(names)}
    selected=[]
    for path in (root/TASK).rglob('*'):
        relative=path.relative_to(root).as_posix()
        require(not path.is_symlink(),'Review input symlink refused')
        if not path.is_file():continue
        # Authoring output must not silently become an executable source exception.
        require(not any(relative==x or relative.startswith(x+'/') for x in OUTPUT_ROOTS) and '__pycache__' not in path.parts,'Generated output in authoring source')
        if relative not in REVIEW_EXCEPTIONS:selected.append(path)
    selected += [root/n for n in WORKFLOWS if (root/n).is_file()]
    result={p.relative_to(root).as_posix():digest(p) for p in sorted(selected)}
    task=root/TASK
    if (task/'fonts/OFL.txt').is_file():result.setdefault(TASK+'/fonts/NotoSansCJKsc-Regular.otf.xz',legacy.FONT_COMPRESSED_SHA)
    if (task/'ci/g2-request.review.json').is_file():result.setdefault(TASK+'/ci/g2-request.json',digest(task/'ci/g2-request.review.json'))
    return result


def regular_unaliased(path):
    # lstat does not open FIFOs/devices or follow symlinks. A shared regular inode
    # would let an ordinary write mutate a second pathname outside this checkout.
    info=path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'Non-regular or multiply-linked file refused')
    return info


def check_working_inputs(root, expected, tree=None, allow_generated_unity=False, allow_restored_font=False):
    tree=tree or git_tree(root,'HEAD')
    if not allow_generated_unity:
        require(not any(os.path.lexists(root/name) for name in OUTPUT_ROOTS if name.startswith(TASK+'/unity/')),'Initial Unity runtime output/cache must be absent')
    for name,sha in expected.items():
        path=root/name
        info=regular_unaliased(path)
        require(all(not p.is_symlink() for p in path.parents if p!=root.parent),'Symlinked execution input ancestor')
        require(tree[name][0] in ('100644','100755') and tree[name][1]=='blob' and bool(info.st_mode&0o111)==(tree[name][0]=='100755'),'Execution input mode/type drift')
        if allow_generated_unity and name.startswith(TASK+'/unity/'):
            relative=name[len(TASK+'/unity/'):]
            if legacy.mutation_kind(relative)!='UNEXPECTED_SOURCE_CHANGE':continue
        require(digest(path)==sha,'Working execution input bytes drifted')
    # Enumerate every output subtree for path/type/alias safety, while exempting
    # only its regular generated bytes from source hash equality. No Git ignore
    # rule hides untracked input; even Unity cache destinations must be unaliased.
    visited=0
    for directory,dirs,files in os.walk(root,followlinks=False):
        visited+=len(dirs)+len(files);require(visited<=100000,'Checkout/output entry bound exceeded')
        rel=Path(directory).relative_to(root).as_posix()
        require(all(stat.S_ISDIR((Path(directory)/d).lstat().st_mode) for d in dirs),'Checkout directory link/type refused')
        dirs[:]=[d for d in dirs if not (rel=='.' and d=='.git')]
        for name in files:
            path=Path(directory)/name;relative=path.relative_to(root).as_posix()
            regular_unaliased(path)
            if any(relative.startswith(x+'/') for x in OUTPUT_ROOTS):continue
            if relative in REVIEW_EXCEPTIONS:continue
            if relative in expected:continue
            if (allow_generated_unity or allow_restored_font) and relative.startswith(TASK+'/unity/'):
                child=relative[len(TASK+'/unity/'):]
                if child=='Assets/Resources/ProbeChinese.otf':
                    require(not path.is_symlink() and digest(path)==legacy.FONT_SHA,'Restored font mismatch');continue
                if allow_generated_unity and legacy.mutation_kind(child)!='UNEXPECTED_SOURCE_CHANGE':
                    require(not path.is_symlink(),'Generated source symlink refused');continue
            raise ValueError('Unexpected materialized checkout input')


def verify_preflight(root, allow_generated_unity=False):
    task=root/TASK;control=task/'ci/g3-preflight.review.json'
    require(all(not p.is_symlink() for p in control.parents if p!=root.parent),'Review control ancestor link refused')
    regular_unaliased(control)
    review=json.loads(bounded_read(control, 256*1024))
    require(set(review)=={'schemaVersion','status','requestId','reviewedSourceCommit','reviewerId','sourceFiles','deviceQa','finalQuality'}, 'Fresh preflight schema mismatch')
    require(type(review['schemaVersion']) is int and review['schemaVersion']==1 and review['status']=='APPROVED_FOR_TRIGGER' and
            review['requestId']==REQUEST['requestId'] and review['deviceQa']=='NOT_RUN' and review['finalQuality']=='NOT_PASSED', 'Fresh preflight not approved')
    require(isinstance(review['reviewerId'],str) and re.fullmatch(r'[A-Za-z0-9_./:-]{5,200}',review['reviewerId']), 'Fresh reviewer identity missing')
    require(re.fullmatch(r'[0-9a-f]{40}',review.get('reviewedSourceCommit','')), 'Reviewed commit missing')
    tree=verify_review_tree(root,review['reviewedSourceCommit'])
    require(review['sourceFiles']==reviewed_files(root,committed=True), 'Reviewed execution input set drifted')
    # Exceptions avoid circular review hashes, not working-tree authority: both
    # metadata and request must still be regular, mode-correct committed bytes.
    controls={}
    for name in REVIEW_EXCEPTIONS:
        require(name in tree and tree[name][0] in ('100644','100755') and tree[name][1]=='blob','Missing or non-regular trigger/review control')
        controls[name]=hashlib.sha256(subprocess.check_output(['git','-C',str(root),'show','HEAD:'+name])).hexdigest()
    check_working_inputs(root,dict(review['sourceFiles'],**controls),tree,allow_generated_unity=allow_generated_unity)
    subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',review['reviewedSourceCommit'],'HEAD'],check=True)
    return review


def guard(root, allow_generated_unity=False):
    # No receipt write may occur before checkout and output-destination closure.
    changed=legacy.git(root,'diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines()
    require(changed==[REQUEST_PATH], 'G3 trigger commit must change only its unique request')
    verify_preflight(root,allow_generated_unity=allow_generated_unity)
    identity=legacy.guard(root)
    identity.update(rulesSha256=RULES_SHA,g2SourceBase=BASE,standardsDigest=STANDARDS_DIGEST,contractVersion='1.0.1',qualityBarVersion='QB-2',finalQuality='NOT_PASSED')
    return identity


def verify_artwork(root):
    for name,expected in ARTWORK.items():
        path=root/TASK/'unity/Assets/G3/Rendering/Resources/G3'/(name+'-ticket-albedo.png')
        raw=bounded_read(path,8*1024*1024)
        require(hashlib.sha256(raw).hexdigest()==expected and raw[:8]==b'\x89PNG\r\n\x1a\n' and len(raw)>=33 and struct.unpack_from('>II',raw,16)==(1536,1024),'Original approved G3 artwork source changed')


def verify_inputs(root):
    g2.verify_inputs(root);verify_artwork(root);load_contract(root/TASK)


def audit_stage(root,stage,identity):
    task=root/TASK; common=task/'evidence'; out=common/'g3'/stage
    out.mkdir(parents=True,exist_ok=True)
    safe=g2.SAFE_COMMON+g2.SAFE_GENERATED
    for name in safe+("settings-normalization.json",): (out/name).unlink(missing_ok=True)
    success=False
    (common/'source-mutations.json').unlink(missing_ok=True)
    try:
        normalization=g2.normalize_unused_platform(root,stage,identity)
        legacy.audit(root,identity,additional_generated_kinds=('G2_GENERATED_SCENE','G3_GENERATED_SCENE'))
        require(digest(task/'unity/Packages/packages-lock.json')==g2.LOCK_SHA, 'Frozen G3 package lock changed')
        for name in ('source-mutations.json','generated-manifest.json'):
            data=json.loads(bounded_read(common/name,1024*1024))
            data.update(archiveRepresentation=normalization['archiveRepresentation'],settingsNormalizationReceiptSha256=digest(common/'g2'/stage/'settings-normalization.json'))
            write_json(common/name,data)
        success=True
    except Exception:
        if not (common/'source-mutations.json').is_file():write_json(common/'source-mutations.json',dict(identity,status='FAIL',failedStage='G3_SOURCE_AUDIT',changes=[],metadataStatus='NO_SOURCE_CONTENT_EXPORTED'))
        write_json(out/'audit-failure.json',dict(identity,status='FAIL',stage=stage,sourceContentExport='REFUSED'))
        raise
    finally:
        norm=common/'g2'/stage/'settings-normalization.json'
        if norm.is_file(): shutil.copyfile(norm,out/norm.name)
        for name in g2.SAFE_COMMON+(g2.SAFE_GENERATED if success else ()):
            path=common/name
            if path.is_file() and not path.is_symlink():
                require(path.stat().st_size<=32*1024*1024,'Stage artifact exceeds bound')
                shutil.copyfile(path,out/name)


def artifacts_stage(stage):
    return 'g2-'+stage.removeprefix('regression-') if stage.startswith('regression-') else 'g3-'+stage


def export_tests(task,stage,identity):
    out=task/'evidence/g3'/stage; out.mkdir(parents=True,exist_ok=True)
    for name in ('raw-test-results.xml','raw-test-report-receipt.json','test-results.xml','test-receipt.json'): (out/name).unlink(missing_ok=True)
    assemblies=load_contract(task)['profiles'][stage]; directory=task/'artifacts'/artifacts_stage(stage)
    legacy.export_raw_test_report(directory,out)
    _,report,result=g2.inspect_tests(directory,assemblies)
    safe=ET.Element('test-run',{k:report.get(k,'') for k in ('result','total','passed','failed','skipped','inconclusive')})
    for suite in [n for n in report.iter('test-suite') if n.get('type')=='Assembly']:
        target=ET.SubElement(safe,'test-suite',dict(type='Assembly',name=suite.get('name'),result='Passed'))
        for case in suite.iter('test-case'): ET.SubElement(target,'test-case',dict(fullname=case.get('fullname'),result='Passed'))
    ET.indent(safe); ET.ElementTree(safe).write(out/'test-results.xml',encoding='utf-8',xml_declaration=True)
    write_json(out/'test-receipt.json',dict(identity,**result,profile=stage,scopeOfPass='EXACT_NATIVE_CASES_NOT_DEVICE_QA'))
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream: stream.write(stage.replace('-','_')+'_passed=true\n')


def inspect_captures(source,identity,frames):
    data=json.loads(bounded_read(source/'render-receipt.json',128*1024))
    required={'schemaVersion','scope','sourceCommit','runId','unityVersion','rulesSha256','captureMethod','graphicsDeviceType','graphicsDeviceName','width','height','sourceViewportWidth','sourceViewportHeight','inputEvidence','deviceQa','visualReview','frames'}
    require(set(data)==required,'G3 render receipt schema mismatch')
    expected=dict(schemaVersion=1,scope='G3_CAMERA_RENDER_NOT_DEVICE_TESTED',sourceCommit=identity['sourceCommit'],runId=identity['runId'],unityVersion=legacy.VERSION,rulesSha256=RULES_SHA,captureMethod='URP_STANDARD_REQUEST_READPIXELS',width=1280,height=720,inputEvidence='SIMULATED_INPUT_SYSTEM',deviceQa='NOT_RUN',visualReview='PENDING')
    require(all(data.get(k)==v for k,v in expected.items()) and type(data['schemaVersion']) is int,'G3 render identity mismatch')
    require(all(type(data[k]) is int and 64<=data[k]<=8192 for k in ('sourceViewportWidth','sourceViewportHeight')), 'Viewport absent')
    for k in ('graphicsDeviceType','graphicsDeviceName'):
        require(isinstance(data[k],str) and re.fullmatch(r'[A-Za-z0-9_., ()/+:-]{1,200}',data[k]) and 'null' not in data[k].lower(),'Graphics device absent')
    require(isinstance(data['frames'],list) and [f.get('stage') for f in data['frames']]==frames,'Exact G3 original frame set mismatch')
    for f in data['frames']:
        require(set(f)=={'stage','file','sha256','bytes','stateSha256','gameRunId','fixtureLabel'} and f['file']==f['stage']+'.png' and re.fullmatch(r'[0-9a-f]{64}',f.get('stateSha256','')),'G3 frame metadata mismatch')
        require(isinstance(f['gameRunId'],str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',f['gameRunId']) and isinstance(f['fixtureLabel'],str) and (f['fixtureLabel']=='NORMAL_UNINJECTED' or re.fullmatch(r'(?:G3|SYNTHETIC)_[A-Z0-9_]{3,100}',f['fixtureLabel'])),'G3 per-frame fixture provenance missing')
        expected_provenance=('g3-protected-render-fixture','SYNTHETIC_CONSUMABLE_BOUNDARY_FIXTURE') if f['stage']=='challenge-protected' else ('g3-day-qafixture-001','G3_DIAGNOSTIC_VECTOR_NOT_NATURAL')
        require((f['gameRunId'],f['fixtureLabel'])==expected_provenance,'G3 main-day/separate-fixture provenance mismatch')
        p=source/f['file']; raw=bounded_read(p,4*1024*1024)
        require(f['sha256']==digest(p) and type(f['bytes']) is int and f['bytes']==len(raw),'Frame bytes mismatch')
        g2.png_dimensions(raw)
    require(len({f['sha256'] for f in data['frames']})==len(frames),'Original state frames must be distinct')
    return data


def parse_binary_manifest(raw):
    """Bounded Android AXML parser: validates compiled APK package/version identity."""
    require(8<=len(raw)<=2*1024*1024,'Android manifest bounds')
    kind,header,total=struct.unpack_from('<HHI',raw,0)
    require(kind==3 and header==8 and total==len(raw),'Expected binary AXML document')
    strings=[]; result={}; offset=header
    def u32(p): require(p+4<=len(raw),'Truncated AXML'); return struct.unpack_from('<I',raw,p)[0]
    def string(i): require(0<=i<len(strings),'AXML string index'); return strings[i]
    while offset<len(raw):
        require(offset+8<=len(raw),'Truncated AXML chunk')
        typ,hs,size=struct.unpack_from('<HHI',raw,offset)
        require(hs>=8 and size>=hs and offset+size<=len(raw),'Bad AXML chunk length')
        if typ==1:
            require(not strings and hs>=28,'Duplicate/bad string pool')
            count,styles,flags,start,style_start=struct.unpack_from('<IIIII',raw,offset+8)
            require(count<=16384 and hs+4*(count+styles)<=size and start>=hs+4*(count+styles) and start<size,'Bad string pool bounds')
            def length(p,wide):
                n=2 if wide else 1; require(p+n<=offset+size,'Truncated string')
                first=int.from_bytes(raw[p:p+n],'little'); p+=n; mask=0x8000 if wide else 0x80
                if first&mask:
                    require(p+n<=offset+size,'Truncated string length'); first=((first&(mask-1))<<(16 if wide else 8))|int.from_bytes(raw[p:p+n],'little');p+=n
                return first,p
            for i in range(count):
                p=offset+start+u32(offset+hs+4*i); require(p<offset+size,'String offset')
                if flags&0x100:
                    _,p=length(p,False);length_bytes,p=length(p,False);end=p+length_bytes
                    require(end<offset+size and raw[end]==0,'Bad UTF8 terminator');s=raw[p:end].decode('utf-8')
                else:
                    chars,p=length(p,True);end=p+chars*2
                    require(end+2<=offset+size and raw[end:end+2]==b'\0\0','Bad UTF16 terminator');s=raw[p:end].decode('utf-16le')
                strings.append(s)
        elif typ==0x102:
            require(hs==16 and size>=36,'Bad start element')
            name=string(u32(offset+20)); attr_start,attr_size,count=struct.unpack_from('<HHH',raw,offset+24)
            require(attr_size>=20 and count<=1024 and 16+attr_start+count*attr_size<=size,'Bad AXML attributes')
            if name=='manifest':
                require(not result,'Duplicate manifest element')
                for n in range(count):
                    p=offset+16+attr_start+n*attr_size; ns=u32(p);key=string(u32(p+4));rawidx=u32(p+8);typesize,zero,typval=struct.unpack_from('<HBB',raw,p+12);value=u32(p+16)
                    require(typesize==8 and zero==0,'Bad typed attribute')
                    if key in ('package','versionCode','versionName'):
                        require(key not in result,'Duplicate identity attribute')
                        require(ns==(0xffffffff if key=='package' else ns) and (key=='package' or string(ns)=='http://schemas.android.com/apk/res/android'),'Wrong identity namespace')
                        if typval==3: val=string(value)
                        elif typval in (16,17): val=value
                        else: raise ValueError('Unexpected APK identity type')
                        if rawidx!=0xffffffff: require(string(rawidx)==str(val),'AXML raw/typed disagreement')
                        result[key]=val
        offset+=size
    require(set(result)=={'package','versionCode','versionName'},'APK identity missing')
    return result


def inspect_apk(task,identity):
    directory=task/'build/G3/Android'; apk=directory/'LotteryG3.apk'
    cold=json.loads(bounded_read(task/'evidence/g3/android/cold-build-baseline.json',16384))
    require(all(cold.get(k)==v for k,v in identity.items()) and cold.get('status')=='VERIFIED_BEFORE_UNITY' and cold.get('libraryAbsent') is True and cold.get('buildAbsent') is True and cold.get('cacheRestored') is False,'Independent cold build observation missing')
    receipt=json.loads(bounded_read(directory/'build-receipt.json',64*1024))
    expected=dict(rulesSha256=RULES_SHA,standardsDigest=STANDARDS_DIGEST,runtimeScene=SCENE,fakeAd='DEVELOPMENT_FAKE_ONLY',versionCode=3,versionName='0.0.3',applicationIdentifier='com.buyuqi.lotteryprobe',normalRuntimeFixture='NONE',coldBuild=True)
    require(all(type(receipt.get(k)) is type(v) and receipt.get(k)==v for k,v in expected.items()),'G3 build receipt declaration mismatch')
    result=legacy.inspect_apk(apk,directory/'build-receipt.json',directory/'resolved-packages.txt',identity)
    with zipfile.ZipFile(apk) as archive:
        info=archive.getinfo('AndroidManifest.xml');require(info.file_size<=2*1024*1024,'Manifest exceeds limit')
        actual=parse_binary_manifest(archive.read(info))
    require(actual==dict(package='com.buyuqi.lotteryprobe',versionCode=3,versionName='0.0.3'),'Compiled APK version/package mismatch')
    result.update(binaryManifest=actual,versionIdentityVerification='COMPILED_BINARY_AXML',finalQuality='NOT_PASSED')
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('source-preflight','guard','restore-font','snapshot','audit','tests','captures','apk','diagnostics','review-manifest'))
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[3]);p.add_argument('--stage',choices=STAGES,default='edit')
    for name in ('unity','verify','audit'):p.add_argument('--'+name+'-outcome',default='unknown')
    args=p.parse_args();root=args.root.resolve();task=root/TASK
    if args.command=='source-preflight':g2.source_preflight(root);verify_artwork(root);baseline_contract(task);print('G3 static settings/artwork/baseline-contract preflight PASS; native execution NOT_RUN.');return
    if args.command=='review-manifest':
        verify_inputs(root);print(json.dumps(reviewed_files(root),sort_keys=True,indent=2));return
    with configured():
        identity=guard(root,allow_generated_unity=args.command!='guard');out=task/'evidence/g3'/args.stage;out.mkdir(parents=True,exist_ok=True);write_json(out/'guard-receipt.json',identity);write_json(task/'evidence/guard-receipt.json',identity)
        if args.command=='guard':verify_inputs(root)
        elif args.command=='restore-font':legacy.restore(root)
        elif args.command=='snapshot':
            verify_inputs(root)
            check_working_inputs(root,reviewed_files(root,committed=True),allow_generated_unity=args.stage not in ('regression-edit','android'),allow_restored_font=True)
            if args.stage=='android':
                require(not (task/'unity/Library').exists() and not (task/'build/G3').exists(),'Android checkout is not cold')
                write_json(out/'cold-build-baseline.json',dict(identity,status='VERIFIED_BEFORE_UNITY',libraryAbsent=True,buildAbsent=True,cacheRestored=False))
            (task/'evidence/manifest-diagnostic.json').unlink(missing_ok=True)
            legacy.snapshot_project(root);g2.snapshot_settings_baseline(root,args.stage,identity)
        elif args.command=='audit':audit_stage(root,args.stage,identity)
        elif args.command=='tests':require(args.stage!='android','Invalid test stage');export_tests(task,args.stage,identity)
        elif args.command=='captures':
            require(args.stage in ('regression-play','play'),'Invalid capture stage')
            frames=list(g2.FRAMES) if args.stage=='regression-play' else load_contract(task)['frames'];source=task/'artifacts'/artifacts_stage(args.stage)/'captures'
            for name in [f+'.png' for f in frames]+['render-receipt.json']:(out/name).unlink(missing_ok=True)
            (g2.inspect_captures(source,identity) if args.stage=='regression-play' else inspect_captures(source,identity,frames))
            for name in [f+'.png' for f in frames]+['render-receipt.json']:shutil.copyfile(source/name,out/name)
        elif args.command=='apk':write_json(out/'apk-receipt.json',inspect_apk(task,identity))
        elif args.command=='diagnostics':write_json(out/'diagnostic-receipt.json',legacy.diagnostic_receipt(identity,args.unity_outcome,args.verify_outcome,args.audit_outcome))
    print('G3 '+args.command+' completed; physical device QA remains NOT_RUN.')

if __name__=='__main__':
    try:main()
    except Exception:
        print('G3 verification refused; inspect bounded receipts. No raw logs exported.',file=sys.stderr);sys.exit(1)
