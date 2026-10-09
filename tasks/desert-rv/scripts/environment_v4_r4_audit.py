#!/usr/bin/env python3
"""Read-only R4 save-lifecycle audit. Never relax/rewrite a frozen hash or package gate.
Internal phase copies are never exported. Only bounded typed material fields can leave them.
"""
import argparse
import hashlib
import json
import math
import re
import shutil
import tempfile
from pathlib import Path
import environment_v4_r4_evidence as r4

source=r4.source
v4=r4.v4
legacy=v4.legacy
require=source.require
CAPTURE='JourneyEvidence/environment-v4-r4-audit'
PROJECT_REPO_PATH='tasks/desert-rv/unity'
OUT=source.TASK/'evidence/environment-v4-r4-audit'
POLICY='ENUMERATE_ALREADY_LOADED_NO_LOAD_ALL_ASSETS_NO_SAVE'
SHA=re.compile('[0-9a-f]{64}')
GUID=re.compile('[0-9a-f]{32}')
# Fixed shader properties, never field names inferred from untrusted/unknown serialized text.
TEXTURES={'_BaseMap','_MainTex','_BumpMap','_DetailAlbedoMap','_DetailMask','_DetailNormalMap','_EmissionMap',
          '_MetallicGlossMap','_OcclusionMap','_ParallaxMap','_SpecGlossMap','unity_Lightmaps','unity_LightmapsInd','unity_ShadowMasks'}
FLOATS={'_AddPrecomputedVelocity','_AlphaClip','_AlphaToMask','_Blend','_BlendModePreserveSpecular','_BumpScale',
        '_ClearCoatMask','_ClearCoatSmoothness','_Cull','_Cutoff','_DetailAlbedoMapScale','_DetailNormalMapScale',
        '_DstBlend','_DstBlendAlpha','_EnvironmentReflections','_GlossMapScale','_Glossiness','_GlossyReflections',
        '_Metallic','_OcclusionStrength','_Parallax','_QueueOffset','_ReceiveShadows','_Smoothness','_SmoothnessTextureChannel',
        '_SpecularHighlights','_SrcBlend','_SrcBlendAlpha','_Surface','_WorkflowMode','_XRMotionVectorsPass','_ZWrite',
        '_DetailContrast','_DetailStart','_DetailEnd'}
COLORS={'_BaseColor','_Color','_EmissionColor','_SpecColor'}
KEYWORDS={'_NORMALMAP','_EMISSION','_ALPHATEST_ON','_SURFACE_TYPE_TRANSPARENT','_ALPHAPREMULTIPLY_ON',
          '_ALPHAMODULATE_ON','_RECEIVE_SHADOWS_OFF','_SPECULARHIGHLIGHTS_OFF','_ENVIRONMENTREFLECTIONS_OFF',
          '_METALLICSPECGLOSSMAP','_SPECULAR_SETUP','_DETAIL_MULX2','_DETAIL_SCALED','_OCCLUSIONMAP','_PARALLAXMAP',
          '_SMOOTHNESS_TEXTURE_ALBEDO_CHANNEL_A'}
NUM=r'-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'


def fingerprint(path):
    path=source.safe(path);size=path.stat().st_size
    require(0<size<=40*1024**2,'Audit generated file exceeds byte bound')
    return dict(sha256=source.sha(path),size=size)


def frozen_report(project):
    report=source.read_json(project/r4.CAPTURE/r4.REPORT)
    require(isinstance(report,dict) and set(report)==r4.REPORT_KEYS,'Audit requires exact native R4 report schema')
    require(type(report['schema']) is int and report['schema']==1 and report['status']==r4.STATUS and report['postCaptureVerified'] is True and
            type(report['postCaptureImageCount']) is int and report['postCaptureImageCount']==20 and
            report['allOtherGeneratedBytesPreserved'] is True,'Audit requires completed native saved-asset verification')
    rows=report['generatedFiles'];require(isinstance(rows,list) and 243<len(rows)<400,'Audit native generated count')
    result={};contract=v4.load_contract();allowed=set(contract['files'])|set(contract['metadata_files'])
    for row in rows:
        require(isinstance(row,dict) and set(row)=={'path','beforeSha256','afterSha256'},'Audit frozen row fields')
        path=row['path'];require(isinstance(path,str) and (path in allowed or legacy.valid_generated_name(path)) and path not in result,'Audit unapproved/duplicate frozen path')
        require(all(isinstance(row[k],str) and SHA.fullmatch(row[k]) for k in ('beforeSha256','afterSha256')),'Audit frozen digest')
        require((row['beforeSha256']!=row['afterSha256'])==(path in r4.MATERIALS),'Audit frozen delta differs from original two-material contract')
        result[path]=row['afterSha256']
    require(allowed<=set(result),'Audit missing finite V4 frozen membership')
    return result


def native_phase(project,phase,frozen):
    require(phase in ('freeze','postcapture'),'Unknown native audit phase')
    root=project/CAPTURE
    record=source.read_json(root/(phase+'.json'))
    require(isinstance(record,dict) and set(record)=={'schema','phase','observationPolicy','files','loadedObjects'} and
            type(record['schema']) is int and record['schema']==1 and record['phase']==phase and record['observationPolicy']==POLICY,'Audit phase schema/policy')
    copies=root/'internal'/phase
    require(set(v4.collect_generated(copies,v4.load_contract()))==set(frozen),'Audit internal copy membership differs')
    require({p.relative_to(copies).as_posix() for p in copies.rglob('*') if p.is_file()}==set(frozen),'Audit copy outside authorized generated closure')
    rows=record['files'];require(isinstance(rows,list) and len(rows)==len(frozen),'Audit phase count')
    seen=set();total=0
    for row in rows:
        require(isinstance(row,dict) and set(row)=={'path','sha256','size'},'Audit phase file fields')
        path=row['path'];require(path in frozen and path not in seen,'Audit phase unknown/duplicate path');seen.add(path)
        actual=fingerprint(copies/path);total+=actual['size']
        require(type(row['size']) is int and actual==dict(sha256=row['sha256'],size=row['size']) and row['sha256']==frozen[path],'Audit phase copy or frozen hash differs')
    require(total<=100*1024**2,'Audit phase total byte bound')
    objects=record['loadedObjects'];require(isinstance(objects,list) and len(objects)<20000,'Audit loaded object bound')
    for row in objects:
        require(isinstance(row,dict) and set(row)=={'path','objectType','localFileId','hasLocalFileId','isDirty'},'Audit loaded object fields')
        require(row['path'] in frozen and isinstance(row['objectType'],str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.+`]{0,191}',row['objectType']) and
                type(row['localFileId']) is int and -(2**63)<=row['localFileId']<2**63 and type(row['hasLocalFileId']) is bool and
                (row['hasLocalFileId'] or row['localFileId']==0) and type(row['isDirty']) is bool,'Audit loaded object identity')
    return record


def capture_postexit(project):
    root=project/CAPTURE;target=root/'postexit.json'
    require(not target.exists() and not (root/'internal/postexit').exists(),'Refuse overwriting earliest postexit observation')
    frozen=frozen_report(project)
    native_phase(project,'freeze',frozen);last=native_phase(project,'postcapture',frozen)
    actual_names={p.relative_to(project).as_posix() for p in (project/legacy.GENERATED).rglob('*') if p.is_file() or p.is_symlink()}
    if (project/(legacy.GENERATED+'.meta')).exists():actual_names.add(legacy.GENERATED+'.meta')
    # New non-frozen names are counted, never echoed or copied. Only the original closed set is read.
    records=[];total=0;copies=root/'internal/postexit'
    for name in sorted(frozen):
        path=project/name
        if not path.exists():records.append(dict(path=name,present=False,sha256=None,size=None));continue
        row=fingerprint(path);total+=row['size'];require(total<=100*1024**2,'Audit postexit total bound')
        destination=copies/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
        require(fingerprint(destination)==row and fingerprint(path)==row,'Postexit observation changed while copying')
        records.append(dict(path=name,present=True,**row))
    record=dict(schema=1,phase='postexit',loadedObjectsAvailable=False,unapprovedGeneratedEntryCount=len(actual_names-set(frozen)),files=records)
    target.write_text(json.dumps(record,indent=2)+'\n');require(source.read_json(target)==record,'Postexit observation readback failed')
    earlier={row['path']:row for row in last['files']}
    changed=[dict(path=row['path'],repoPath=PROJECT_REPO_PATH+'/'+row['path'],postcapture=earlier[row['path']],postexit=row) for row in records if not row['present'] or row['sha256']!=frozen[row['path']]]
    print('R4_POSTEXIT_GENERATED_DIFF '+json.dumps(dict(changed=changed,unapprovedGeneratedEntryCount=record['unapprovedGeneratedEntryCount']),sort_keys=True))
    return record


def read_postexit(project,frozen):
    root=project/CAPTURE;record=source.read_json(root/'postexit.json')
    require(isinstance(record,dict) and set(record)=={'schema','phase','loadedObjectsAvailable','unapprovedGeneratedEntryCount','files'} and
            type(record['schema']) is int and record['schema']==1 and record['phase']=='postexit' and record['loadedObjectsAvailable'] is False,'Postexit schema')
    count=record['unapprovedGeneratedEntryCount'];require(type(count) is int and 0<=count<1000,'Postexit unknown count')
    rows=record['files'];require(isinstance(rows,list) and len(rows)==len(frozen),'Postexit file count');seen=set();present=set();total=0
    for row in rows:
        require(isinstance(row,dict) and set(row)=={'path','present','sha256','size'},'Postexit fields')
        name=row['path'];require(name in frozen and name not in seen and type(row['present']) is bool,'Postexit path identity');seen.add(name)
        if row['present']:
            require(type(row['size']) is int and fingerprint(root/'internal/postexit'/name)==dict(sha256=row['sha256'],size=row['size']),'Postexit preserved copy differs');present.add(name)
            total+=row['size'];require(total<=100*1024**2,'Postexit saved total byte bound')
        else:require(row['sha256'] is None and row['size'] is None,'Missing postexit file carries fabricated bytes')
    copies=root/'internal/postexit'
    require({p.relative_to(copies).as_posix() for p in copies.rglob('*') if p.is_file()}==present,'Postexit internal copy outside closed set')
    return record


def material_semantics(data):
    """Return typed whitelisted fields and a hash of everything not recognized; never raw lines."""
    if len(data)>128*1024 or not data.startswith(b'%YAML 1.1\n'):return dict(supported=False,reason='NOT_BOUNDED_UNITY_MATERIAL')
    try:text=data.decode('utf-8')
    except UnicodeError:return dict(supported=False,reason='NON_UTF8_SERIALIZATION')
    docs=re.findall(r'^--- !u!(\d+) &(-?\d+)\n(.*?)(?=^--- !u!|\Z)',text,re.M|re.S)
    if not docs or sum(kind=='21' for kind,_,_ in docs)!=1 or any(kind not in ('21','114') for kind,_,_ in docs):
        return dict(supported=False,reason='UNSUPPORTED_DOCUMENT_CLASSES')
    values={};remainders=[]
    def number(value):
        result=float(value);require(math.isfinite(result) and abs(result)<=1e12,'Unsafe numeric semantic field');return result
    try:
        for kind,identity,body in docs:
            prefix=kind+':'+identity+':';spans=[]
            def accept(pattern,key,convert):
                matches=list(re.finditer(pattern,body,re.M))
                require(len(matches)<=1,'Duplicate allowed semantic field')
                if matches:
                    match=matches[0];value=convert(match)
                    if value is not None:values[prefix+key]=value;spans.append(match.span())
            for key in ('m_ObjectHideFlags','serializedVersion','m_LightmapFlags','m_EnableInstancingVariants','m_DoubleSidedGI','m_CustomRenderQueue','m_ModifiedSerializedProperties','m_AllowLocking','m_Enabled','m_EditorHideFlags','version'):
                accept(r'^  '+key+r': ('+NUM+r')$',key,lambda m:number(m[1]))
            for key in ('m_Shader','m_Script','m_Parent'):
                accept(r'^  '+key+r': \{fileID: (-?\d+)(?:, guid: ([0-9a-f]{32}), type: ([0-3]))?\}$',key,
                       lambda m:dict(fileID=int(m[1]),guid=m[2],type=int(m[3]) if m[3] else None))
            for key in ('m_ValidKeywords','m_InvalidKeywords'):
                accept(r'^  '+key+r':(?: \[\]|\n(?:  - [A-Z0-9_]+\n?)+)$',key,
                       lambda m:sorted(re.findall(r'^  - ([A-Z0-9_]+)$',m[0],re.M)) if set(re.findall(r'^  - ([A-Z0-9_]+)$',m[0],re.M))<=KEYWORDS else None)
            for key in FLOATS:
                accept(r'^    - '+key+r': ('+NUM+r')$',key,lambda m:number(m[1]))
            for key in COLORS:
                accept(r'^    - '+key+r': \{r: ('+NUM+r'), g: ('+NUM+r'), b: ('+NUM+r'), a: ('+NUM+r')\}$',key,
                       lambda m:dict(zip(('r','g','b','a'),[number(m[i]) for i in range(1,5)])))
            for key in TEXTURES:
                pattern=r'^    - '+key+r':\n        m_Texture: \{fileID: (-?\d+)(?:, guid: ([0-9a-f]{32}), type: ([0-3]))?\}\n        m_Scale: \{x: ('+NUM+r'), y: ('+NUM+r')\}\n        m_Offset: \{x: ('+NUM+r'), y: ('+NUM+r')\}$'
                accept(pattern,key,lambda m:dict(fileID=int(m[1]),guid=m[2],type=int(m[3]) if m[3] else None,
                        scale=dict(x=number(m[4]),y=number(m[5])),offset=dict(x=number(m[6]),y=number(m[7]))))
            for start,end in sorted(spans,reverse=True):body=body[:start]+body[end:]
            remainders.append((kind,identity,body))
        return dict(supported=True,fields=values,unrecognizedBytesSha256=hashlib.sha256(json.dumps(dict(preamble=text.split('--- !u!',1)[0],documents=remainders),separators=(',',':')).encode()).hexdigest())
    except (ValueError,OverflowError):return dict(supported=False,reason='UNSAFE_OR_DUPLICATE_ALLOWED_FIELD')


def semantics_diff(name,before,after):
    if not name.endswith('.mat') or before is None or after is None:return dict(status='HASH_AND_SIZE_ONLY')
    first,last=material_semantics(before),material_semantics(after)
    if not first['supported'] or not last['supported']:return dict(status='UNRECOGNIZED_CONTENT_HASH_AND_SIZE_ONLY')
    a,b=first['fields'],last['fields']
    changes=[dict(field=key,before=a.get(key),after=b.get(key)) for key in sorted(set(a)|set(b)) if a.get(key)!=b.get(key)]
    require(len(changes)<=256,'Material semantic difference bound')
    return dict(status='WHITELISTED_TYPED_MATERIAL_FIELDS_ONLY',fields=changes,
                unrecognizedBytesChanged=first['unrecognizedBytesSha256']!=last['unrecognizedBytesSha256'])


def sanitized_audit(project,outcome):
    require(outcome in ('success','failure'),'Package outcome must be success or failure')
    frozen=frozen_report(project);first=native_phase(project,'freeze',frozen);last=native_phase(project,'postcapture',frozen);post=read_postexit(project,frozen)
    phases={phase['phase']:[dict(row,present=True,repoPath=PROJECT_REPO_PATH+'/'+row['path']) for row in phase['files']] for phase in (first,last)}
    phases['postexit']=[dict(row,repoPath=PROJECT_REPO_PATH+'/'+row['path']) for row in post['files']]
    maps={phase:{row['path']:row for row in rows} for phase,rows in phases.items()};changes=[]
    for name in sorted(frozen):
        stages={phase:maps[phase][name] for phase in phases}
        if len({(row['present'],row['sha256'],row['size']) for row in stages.values()})>1:
            transitions=[]
            for earlier,later in (('freeze','postcapture'),('postcapture','postexit')):
                a,b=stages[earlier],stages[later]
                if (a['present'],a['sha256'],a['size'])==(b['present'],b['sha256'],b['size']):continue
                root=project/CAPTURE/'internal'
                before=source.safe(root/earlier/name).read_bytes() if a['present'] else None
                after=source.safe(root/later/name).read_bytes() if b['present'] else None
                transitions.append(dict(beforePhase=earlier,afterPhase=later,semantic=semantics_diff(name,before,after)))
            changes.append(dict(path=name,repoPath=PROJECT_REPO_PATH+'/'+name,stages=stages,transitions=transitions))
    if outcome=='success':require(not changes and post['unapprovedGeneratedEntryCount']==0,'Successful package cannot have lifecycle byte differences')
    else:require(changes or post['unapprovedGeneratedEntryCount']>0,'Failure audit requires an actual lifecycle byte/membership difference')
    return dict(schema='desert-rv-environment-v4-r4-lifecycle-audit/v1',scope='READ_ONLY_GENERATED_SAVE_LIFECYCLE_AUDIT',packageOutcome=outcome,
                status='PACKAGE_VALIDATED_LIFECYCLE_AUDIT' if outcome=='success' else 'NATIVE_RENDERED_NOT_PACKAGE_VALIDATED',
                frozenHashesReplaced=False,observationPolicy=POLICY,unityProjectRepoPath=PROJECT_REPO_PATH,phases=phases,differences=changes,
                loadedObjects=dict(freeze=[dict(row,repoPath=PROJECT_REPO_PATH+'/'+row['path']) for row in first['loadedObjects']],
                                   postcapture=[dict(row,repoPath=PROJECT_REPO_PATH+'/'+row['path']) for row in last['loadedObjects']],postexit=None),
                postexitLoadedObjectsObservable=False,unapprovedGeneratedEntryCount=post['unapprovedGeneratedEntryCount'])


def package():
    capture_postexit(source.PROJECT)
    # No catch, normalization, replacement snapshot, or weakened condition. Original failure propagates.
    r4.package()


def diagnose(outcome):
    require(outcome in ('success','failure'),'Package outcome must be success or failure')
    require(not OUT.exists() and not OUT.is_symlink(),'Refuse stale lifecycle audit output')
    native=legacy.inspect_native_report(source.TASK/'artifacts/environment')
    saved=source.read_json(legacy.SNAPSHOT);legacy.assert_preserved(saved,legacy.tracked_snapshot(source.ROOT))
    r4.inspect_input(source.PROJECT)
    report=sanitized_audit(source.PROJECT,outcome)
    identity=source.identity();require(identity['runAttempt']=='1','Lifecycle audit replay')
    if outcome=='success':
        r4.verify_manifest(r4.OUT);accepted=source.read_json(r4.OUT/'receipt.json')
        require(accepted.get('schema')==r4.SCHEMA and accepted.get('nativeRenderXmlSha256')==native and
                all(accepted.get(key)==identity[key] for key in ('commit','runId','runAttempt')) and
                accepted.get('protectedTrackedFilesUnchanged') is True,'No matching strict successful R4 package')
    else:require(not r4.OUT.exists(),'Failure audit conflicts with an existing strict R4 package')
    report.update(identity=identity,nativeRenderTest=legacy.RENDER_TEST,nativeRenderXmlSha256=native,
                  protectedTrackedFilesUnchanged=True,visualAcceptance='NOT_ACCEPTED',gameplayIntegration='NOT_RUN')
    images={}
    if outcome=='failure':
        legacy.inspect_capture(source.PROJECT);v4.inspect_extra(source.PROJECT,v4.load_contract())
        images={name:source.PROJECT/'JourneyEvidence/environment'/name for name in legacy.IMAGES}
        images.update({name:source.PROJECT/v4.EXTRA/name for name in v4.EXTRA_IMAGES})
        require(len(images)==20,'Audit exactly twenty original PNG names required')
        for path in images.values():legacy.inspect_png(path)
    require(not any(p.is_symlink() for p in OUT.parents),'Linked audit output ancestor');OUT.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.r4-lifecycle-audit-',dir=OUT.parent) as temporary:
        stage=Path(temporary)/'bundle';stage.mkdir()
        image_rows=[]
        for name,path in sorted(images.items()):
            shutil.copyfile(path,stage/name);legacy.inspect_png(stage/name)
            require(source.sha(stage/name)==source.sha(path),'Audit PNG copy readback failed')
            image_rows.append(dict(file=name,sha256=source.sha(path),size=path.stat().st_size,width=1440,height=900))
        report['images']=image_rows;(stage/'lifecycle-audit.json').write_text(json.dumps(report,indent=2)+'\n')
        require(source.read_json(stage/'lifecycle-audit.json')==report,'Audit report readback failed')
        v4.write_manifest(stage);r4.verify_manifest(stage)
        require({p.name for p in stage.iterdir()}==set(images)|{'lifecycle-audit.json','SHA256SUMS.json'},'Audit sanitized export closed set')
        require(not OUT.exists() and not OUT.is_symlink(),'Audit output appeared during packaging');stage.rename(OUT)
    print('Read-only lifecycle audit exported: '+report['status']+'; changed authorized paths='+str(len(report['differences'])))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('package','diagnose'));parser.add_argument('--package-outcome',choices=('success','failure'))
    args=parser.parse_args()
    if args.mode=='diagnose':
        parser.error('--package-outcome is required for diagnose') if args.package_outcome is None else diagnose(args.package_outcome)
    else:
        parser.error('--package-outcome is only valid with diagnose') if args.package_outcome is not None else package()
