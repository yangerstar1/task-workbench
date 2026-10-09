"""Persist only the exact native Journey additions. Never exports private package bytes or a live scope."""
import hashlib, json, math, os, re, shutil, tempfile
from pathlib import Path
from strict_output import read, sha, require, safe, digest, rel, verify_staged_inventory

SCHEMA='desert-rv-generated-journey/v1'
KINDS=('armored','pouncer','weapon')
BUILTINS={'Resources/unity_builtin_extra','Library/unity default resources'}
NATIVE_KEYS={'schema','status','sourceCommit','unityVersion','importRunUrl','approved','files','dependencies','spawnGrounding'}
DEPENDENCY_KEYS={'path','sha256','bytes','kind','packageName','packageVersion'}
UNITY='6000.3.19f1'
GROUND_PATH='JourneyEvidence/JourneyPreparation/spawn-grounding.json'
GROUND_EXPORT='spawn-grounding-evidence.json'
GROUND_SOURCE='scene-physical-floor'
GROUND_KEYS={'schema','status','sourceCommit','source','selectionSha256','readyInputSha256','approved','rows'}
GROUND_ROW_KEYS={'id','kind','region','scene','floor','layer','declaredPosition','resolvedPosition','hitPoint','hitNormal','yaw'}
REGION_SCENES={i:'Assets/DesertRV/Scenes/Journey/'+name+'.unity' for i,name in enumerate(('FirstStation','Scrapyard','NightBeacon'),1)}

def record(path, name):
    path=safe(path)
    return dict(path=name,sha256=sha(path),bytes=path.stat().st_size)

def sealed_json(path, proof, root):
    name=str(path.relative_to(root));pins=[row for row in proof['dataPins'] if row['path']==name]
    require(len(pins)==1 and digest(pins[0]['sha256']),'GENERATED_SEALED_JSON_PIN')
    raw=safe(path).read_bytes();expected=pins[0]['sha256']
    require(len(raw)<=8*1024**2 and hashlib.sha256(raw).hexdigest()==expected,'GENERATED_SEALED_JSON_CHANGED')
    def unique(items):
        result={}
        for key,value in items:
            require(key not in result,'GENERATED_DUPLICATE_JSON_KEY');result[key]=value
        return result
    def finite(_):raise ValueError('GENERATED_NONFINITE_JSON')
    return json.loads(raw,object_pairs_hook=unique,parse_constant=finite),expected

def grounding_pin(native):
    pin=native.get('spawnGrounding')
    require(type(native.get('schema')) is int and native['schema']==3 and isinstance(pin,dict) and set(pin)=={'path','sha256'} and
            pin['path']==GROUND_PATH and digest(pin['sha256']),'GENERATED_GROUNDING_NATIVE_PIN')
    return pin

def validate_spawn_grounding(value,native,state,project,commit,actual_sha):
    pin=grounding_pin(native);require(pin['sha256']==actual_sha,'GENERATED_GROUNDING_NATIVE_HASH')
    require(isinstance(value,dict) and set(value)==GROUND_KEYS and type(value['schema']) is int and value['schema']==1 and
            value['status']=='ACTUAL_NATIVE_ROOT_GROUNDING_UNREVIEWED' and value['sourceCommit']==commit and
            value['source']==GROUND_SOURCE and value['approved'] is False,'GENERATED_GROUNDING_IDENTITY')
    root=project.parents[2];selection_name=state['selection']
    require(isinstance(selection_name,str) and re.fullmatch(r'tasks/desert-rv/art/journey-preparation/[a-z0-9-]+\.json',selection_name) and
            digest(state['selectionSha256']) and sha(root/selection_name)==state['selectionSha256']==value['selectionSha256'],'GENERATED_GROUNDING_SELECTION_PIN')
    selection=read(root/selection_name);ready_path=project/'JourneyEvidence/JourneyPreparation/ready-input.json'
    require(digest(state['readyInputSha256']) and sha(ready_path)==state['readyInputSha256']==value['readyInputSha256'],'GENERATED_GROUNDING_READY_PIN')
    ready=read(ready_path)
    require(selection.get('spawnRootHeightSource')==state['plan'].get('spawnRootHeightSource')==ready.get('spawnRootHeightSource')==GROUND_SOURCE and
            ready.get('selectionSha256')==state['selectionSha256'] and ready.get('sourceCommit')==commit,'GENERATED_GROUNDING_INPUT_IDENTITY')
    regions=state['plan']['integration']['regions']
    require(regions==selection['integration']['regions']==ready['integration']['regions'],'GENERATED_GROUNDING_DECLARATION_CHANGED')
    require(isinstance(regions,list) and len(regions)==3 and {r['region'] for r in regions}==set(REGION_SCENES),'GENERATED_GROUNDING_REGIONS')
    expected={}
    for region in regions:
        require(type(region['region']) is int,'GENERATED_GROUNDING_REGIONS')
        for row in region['guards']+region['roadBeasts']+[enemy for wave in region['waves'] for enemy in wave['enemies']]:
            require(isinstance(row['id'],str) and row['id'] not in expected and row['kind'] in ('armored','pouncer'),'GENERATED_GROUNDING_DECLARATIONS')
            expected[row['id']]=(region['region'],row)
    rows=value['rows'];require(len(expected)==9 and isinstance(rows,list) and len(rows)==9,'GENERATED_GROUNDING_ROW_COUNT')
    seen=set()
    def number(n):return type(n) in (int,float) and math.isfinite(n)
    def vector(v):return isinstance(v,dict) and set(v)=={'x','y','z'} and all(number(n) for n in v.values())
    for row in rows:
        require(isinstance(row,dict) and set(row)==GROUND_ROW_KEYS,'GENERATED_GROUNDING_ROW_SCHEMA')
        name=row['id'];require(isinstance(name,str) and name in expected and name not in seen,'GENERATED_GROUNDING_ROW_ID');seen.add(name)
        region,declared=expected[name]
        require(type(row['region']) is int and row['region']==region and row['scene']==REGION_SCENES[region] and row['kind']==declared['kind'],'GENERATED_GROUNDING_ROW_IDENTITY')
        require(row['floor'] in ('Route foundation','Road surface') and type(row['layer']) is int and row['layer']==0,'GENERATED_GROUNDING_FLOOR')
        require(all(vector(row[k]) for k in ('declaredPosition','resolvedPosition','hitPoint','hitNormal')) and number(row['yaw']) and number(declared['yaw']),'GENERATED_GROUNDING_FINITE')
        a,b,hit,normal=(row[k] for k in ('declaredPosition','resolvedPosition','hitPoint','hitNormal'))
        require(a==declared['position'] and a['y']==0 and row['yaw']==declared['yaw'],'GENERATED_GROUNDING_DECLARED_POSITION')
        require(all(b[axis]==a[axis] and abs(hit[axis]-a[axis])<=.0001 for axis in ('x','z')) and b['y']==hit['y'],'GENERATED_GROUNDING_RESOLVED_POSITION')
        require(normal['y']>=.9,'GENERATED_GROUNDING_NORMAL')
    require(seen==set(expected),'GENERATED_GROUNDING_ROW_INVENTORY')

def native_closure(native, generated, source, strict, project, commit, run):
    require(set(native)==NATIVE_KEYS and type(native['schema']) is int and native['schema']==3 and native['status']=='ACTUAL_NATIVE_JOURNEY_ASSETS_UNREVIEWED' and
            native['sourceCommit']==commit and native['unityVersion']==UNITY and native['importRunUrl']==run and native['approved'] is False,'GENERATED_NATIVE_IDENTITY')
    rows=native['files'];require(isinstance(rows,list) and rows and all(set(r)=={'path','sha256'} for r in rows),'GENERATED_NATIVE_FILES')
    require(len(rows)==len(generated) and {r['path']:r['sha256'] for r in rows}==generated,'GENERATED_NATIVE_FILES_CHANGED')
    dependencies=native['dependencies'];require(isinstance(dependencies,list) and 0<len(dependencies)<=8192,'GENERATED_DEPENDENCY_COUNT')
    lock=read(project/'Packages/packages-lock.json')['dependencies'];seen=set();result=[]
    for row in dependencies:
        require(isinstance(row,dict) and set(row)==DEPENDENCY_KEYS,'GENERATED_DEPENDENCY_SCHEMA')
        name=row['path'];require(rel(name) and name not in seen,'GENERATED_DEPENDENCY_PATH');seen.add(name)
        require(type(row['bytes']) is int and 0<=row['bytes']<=128*1024**2,'GENERATED_DEPENDENCY_SIZE')
        if row['kind']=='builtin':
            require(name in BUILTINS and row['sha256']=='' and row['bytes']==0 and row['packageName']==row['packageVersion']=='','GENERATED_BUILTIN_IDENTITY')
            owner='unity-builtin'
        elif row['kind']=='package':
            package=row['packageName'];require(isinstance(package,str) and re.fullmatch(r'com\.unity\.[a-z0-9.-]+',package) and package in lock,'GENERATED_PACKAGE_IDENTITY')
            expected=lock[package]
            require(row['packageVersion']==expected['version'] and (expected['source']=='builtin' or expected['source']=='registry' and expected.get('url')=='https://packages.unity.com'),'GENERATED_PACKAGE_VERSION')
            require(name.startswith('Packages/'+package+'/') and re.fullmatch(r'Packages/[A-Za-z0-9_./ -]+',name) and digest(row['sha256']) and row['bytes']>0,'GENERATED_PACKAGE_PATH')
            owner='official-package' # Reinstall pinned official packages; only logical identity and native digest are public.
        else:
            require(row['kind']=='asset' and name.startswith('Assets/') and row['packageName']==row['packageVersion']=='' and digest(row['sha256']),'GENERATED_ASSET_IDENTITY')
            owners=[(label,files) for label,files in [('source',source),('strict',strict),('generated',generated)] if name in files]
            require(len(owners)==1,'GENERATED_UNKNOWN_OR_AMBIGUOUS_DEPENDENCY')
            owner,files=owners[0];require(files[name]==row['sha256'],'GENERATED_DEPENDENCY_PIN_CHANGED')
            actual=record(project/name,name);require(actual['sha256']==row['sha256'] and actual['bytes']==row['bytes'],'GENERATED_DEPENDENCY_BYTES_CHANGED')
        result.append(dict(row,owner=owner))
    # Unity must include every generated non-meta root and the metadata for each real dependency.
    unreferenced={n for n in generated if not n.endswith('.meta')} - seen
    require(all(re.fullmatch(r'Assets/DesertRV/Scenes/Journey/Layout-[0-9A-F]{6}\.mat',n) for n in unreferenced),'GENERATED_ROOT_DEPENDENCY_MISSING')
    require(all(n+'.meta' in seen for n in seen if n not in BUILTINS and not n.endswith('.meta')),'GENERATED_DEPENDENCY_META_MISSING')
    require(all(n[:-5] in seen for n in seen if n.endswith('.meta')),'GENERATED_ORPHAN_DEPENDENCY_META')
    return sorted(result,key=lambda r:r['path'])

def strict_sources(task,state,project,commit,run):
    require([r['kind'] for r in state['completed']]==list(KINDS),'GENERATED_THREE_STRICT_REQUIRED')
    assets={};refs=[]
    for stage in state['completed']:
        kind=stage['kind'];folder=task/'journey-preparation-export'/kind;receipt=read(folder/'receipt.json')
        require(sha(folder/'receipt.json')==stage['exportReceiptSha256'],'GENERATED_STRICT_RECEIPT_CHANGED')
        require(receipt['status']=='STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED' and receipt['approved'] is False and receipt['kind']==kind and receipt['importCommit']==commit and receipt['importRunUrl']==run,'GENERATED_STRICT_IDENTITY')
        verify_staged_inventory(folder,receipt['files'],stage['exportReceiptSha256'])
        for item in receipt['files']:
            name=item['path']
            if name=='CandidateArtImports.meta' or name.startswith('CandidateArtImports/'):
                path='Assets/DesertRV/'+name
                require(path not in assets or assets[path]==item['sha256'],'GENERATED_STRICT_COLLISION')
                require(sha(project/path)==item['sha256'],'GENERATED_STRICT_ASSET_CHANGED');assets[path]=item['sha256']
        refs.append(dict(kind=kind,path=kind+'/receipt.json',sha256=stage['exportReceiptSha256'],nativeXmlSha256=receipt['nativeXmlSha256'],nativeCases=receipt['nativeCases']))
    require(assets==state['assetFiles'],'GENERATED_STRICT_UNION')
    return assets,refs

def export_generated(prepared, native_xml_sha):
    require(digest(native_xml_sha),'GENERATED_NATIVE_TEST_PIN')
    proof=prepared.verify();state=read(prepared.STATE);project=prepared.PROJECT;task=prepared.TASK
    commit=os.environ['GITHUB_SHA'];attempt=os.environ['GITHUB_RUN_ATTEMPT'];run='https://github.com/yangerstar1/task-workbench/actions/runs/'+os.environ['GITHUB_RUN_ID']
    require(re.fullmatch(r'[1-9][0-9]*',attempt) and digest(commit,40) and re.fullmatch(r'https://github\.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]*',run),'GENERATED_JOB_IDENTITY')
    source_state=read(task/'SOURCE-STATE.json');prefix='tasks/desert-rv/unity/'
    source={row['path'][len(prefix):]:row['sha256'] for row in source_state['files']+source_state['restoredFiles'] if row['path'].startswith(prefix)}
    fx=read(project/'JourneyEvidence/journey-candidate-fx.json');generated=prepared.journey_files(fx)
    native_path=project/'JourneyEvidence/JourneyPreparation/authored-assets.json';native,native_sha=sealed_json(native_path,proof,task.parent.parent)
    ground_path=project/GROUND_PATH;ground,ground_sha=sealed_json(ground_path,proof,task.parent.parent)
    validate_spawn_grounding(ground,native,state,project,commit,ground_sha)
    strict,refs=strict_sources(task,state,project,commit,run)
    dependencies=native_closure(native,generated,source,strict,project,commit,run)
    referenced={r['path'] for r in dependencies}
    omitted={n:generated[n] for n in generated if re.fullmatch(r'Assets/DesertRV/Scenes/Journey/Layout-[0-9A-F]{6}\.mat(?:\.meta)?',n) and (n[:-5] if n.endswith('.meta') else n) not in referenced}
    exported={n:h for n,h in generated.items() if n not in omitted}
    require(proof['addedAssets']=={**strict,**generated},'GENERATED_PROOF_UNION')
    require(len(generated)<=512 and sum(safe(project/name).stat().st_size for name in generated)<=128*1024**2,'GENERATED_EXPORT_SIZE')
    integrated_path=project/'JourneyEvidence/journey-candidate-integration.json';integrated=read(integrated_path)
    require(integrated['status']=='STRICT_CANDIDATES_BOUND_UNREVIEWED' and integrated['sourceCommit']==commit and integrated['candidateOnly'] is True and
            integrated['protectedSourcesUnchanged'] is True and integrated['rolledBack'] is False and integrated['failures']==[] and
            all(integrated[k] is False for k in ('visualReviewed','gameplayReviewed','audioAuditioned')),'GENERATED_INTEGRATION_IDENTITY')
    outputs=integrated['outputs'];require(isinstance(outputs,list) and len(outputs)==5,'GENERATED_SCENE_OUTPUTS')
    for row in outputs:
        require(set(row)=={'path','sha256','dependencyHash','dependencySha256'} and generated.get(row['path'])==row['sha256'] and digest(row['dependencySha256']) and digest(row['dependencyHash'],32),'GENERATED_SCENE_PIN')
    scope_path=project/'JourneyEvidence/journey-diagnostic-scope.json';scope,scope_sha=sealed_json(scope_path,proof,task.parent.parent)
    require(set(scope)=={'label','sourceCommit','files'} and scope['label']=='EDITOR_DIAGNOSTIC_UNAPPROVED_CONTENT' and scope['sourceCommit']==commit,'GENERATED_SCOPE_IDENTITY')
    for row in scope['files']:
        require(set(row)=={'path','sha256','dependencyHash','kind'} and rel(row['path']) and row['path'].startswith(('Assets/DesertRV/','JourneyEvidence/CandidateArt/')) and digest(row['sha256']) and row['kind'] in {'source','scene','import-report','import-contract','imported-model'} and (row['dependencyHash'] in ('',None) or digest(row['dependencyHash'],32)),'GENERATED_SCOPE_PIN')
        require(sha(project/row['path'])==row['sha256'],'GENERATED_SCOPE_BYTES_CHANGED')
    target=task/'journey-preparation-export/generated';require(not target.exists(),'GENERATED_DESTINATION_EXISTS')
    staging=Path(tempfile.mkdtemp(prefix='generated-safe-',dir=prepared.STATE.parent))
    try:
        files=[]
        for name,h in sorted(exported.items()):
            dest=staging/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(safe(project/name),dest)
            item=record(dest,name);require(item['sha256']==h,'GENERATED_COPY_CHANGED');files.append(item)
        for original,name,expected in ((native_path,'native-authored-assets.json',native_sha),(scope_path,'diagnostic-scope-evidence.json',scope_sha),(ground_path,GROUND_EXPORT,ground_sha)):
            shutil.copyfile(safe(original),staging/name);item=record(staging/name,name)
            require(item['sha256']==expected,'GENERATED_EVIDENCE_COPY_CHANGED');files.append(item)
        controls=[record(project/name,name) for name in ('Packages/manifest.json','Packages/packages-lock.json','ProjectSettings/ProjectVersion.txt')]
        manifest=dict(schema=SCHEMA,status='GENERATED_JOURNEY_SAVED_UNREVIEWED',approved=False,sourceCommit=commit,importRunUrl=run,unityVersion=UNITY,
            runAttempt=int(attempt),sourceStateSha256=sha(task/'SOURCE-STATE.json'),strictReceipts=refs,files=files,dependencies=dependencies,packageControls=controls,
            nativeManifestPath='native-authored-assets.json',nativeManifestSha256=native_sha,diagnosticScopeEvidencePath='diagnostic-scope-evidence.json',
            spawnGroundingPath=GROUND_EXPORT,spawnGroundingSha256=ground_sha,
            omittedUnreferencedLayout=[dict(path=n,sha256=h) for n,h in sorted(omitted.items())],
            nativeAuthoringXmlSha256=native_xml_sha,preparedProofSha256=sha(prepared.PROOF),integrationReportSha256=sha(integrated_path),
            integrationOutputs=outputs,fxParametersSha256=fx['parametersSha256'],diagnosticScopeSha256=scope_sha,
            visualReviewed=False,gameplayReviewed=False,audioAuditioned=False,
            restoration='EXACT_SOURCE_CHECKOUT_PLUS_SAME_RUN_STRICT_AND_REFERENCED_GENERATED_ASSETS',scopeReusable=False)
        require(digest(manifest['fxParametersSha256']),'GENERATED_FX_PARAMETERS_PIN')
        (staging/'receipt.json').write_text(json.dumps(manifest,indent=2)+'\n')
        manifest_sha=sha(staging/'receipt.json');verify_staged_inventory(staging,files,manifest_sha)
        prepared.verify() # Revalidate original/native hashes after copying; a host snapshot cannot replace the pre-exit native snapshot.
        staging.replace(target)
        return dict(path='generated/receipt.json',sha256=manifest_sha,files=len(files))
    finally:
        if staging.exists():shutil.rmtree(staging)
