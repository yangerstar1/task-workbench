#!/usr/bin/env python3
"""Same-job candidate Linux build bundle. Does not execute the player or grant approval."""
import functools,gzip,hashlib,json,os,pathlib,re,shutil,subprocess,sys,tarfile,tempfile
import player_window_smoke as recovery
from prepare_safe_diagnostic_export import safe,sha,read_json,require
from capture_game_window import atomic
ROOT=recovery.ROOT;TASK=recovery.TASK;PROJECT=TASK/'unity'
STATE=PROJECT/'JourneyEvidence/JourneyPreparation'
BUILD=TASK/'journey-linux-private-build';STAGED=TASK/'journey-linux-staged-export';PUBLIC=TASK/'journey-linux-public-export';CONTROL=TASK/'journey-linux-control.json'
RECOVERY=TASK/'journey-linux-control-private';recovery.EVIDENCE=RECOVERY
sys.path.insert(0,str(TASK/'art/journey-preparation'));import linux_build_input
MODE='CANDIDATE_LINUX_DEVELOPMENT_BUILT_UNREVIEWED'
SCENES=['Assets/DesertRV/Scenes/Journey/'+n+'.unity' for n in ('JourneyBootstrap','FirstStation','Scrapyard','NightBeacon')]
RECEIPT_KEYS={'detailedBuildReport','performanceTestResourcesExcluded','schema','label','sourceCommit','producerRunUrl','generatedReceiptSha256','requestSha256','executableSha256','unityVersion','target','backend','define','executable','scenes','candidateOnly','development','settingsRestored','sourceBytesUnchanged','approved','visualReviewed','gameplayReviewed','audioAuditioned','temporarySettingsFiles','temporarySettingsApiFields','boundaryNativeXmlSha256','boundaryNativeCases','restorationProof','assetProducerSourceCommit','assetProducerRunUrl','restorationNativeXmlSha256'}
DIAG_KEYS={'performanceResources','primaryInventory','verificationInventory','activeTargetAtEntry','activeTargetBeforeBuild','activeTargetAfterBuild','reportTarget','sourceBytesUnchanged', 'primaryCallbackGate', 'settingsRestored', 'buildReportAvailable', 'restorationExceptionKind', 'verificationSceneRole', 'totalErrors', 'leaseClosedReason', 'exceptionKind', 'buildResult', 'primarySceneRole', 'buildMessages', 'verificationFailureCode', 'receiptWritten', 'primaryRootMismatch', 'restorationFailureCode', 'assemblyReloadObserved', 'primaryFailureCode', 'verificationCallbackGate', 'label', 'verificationRootMismatch', 'buildMessagesTruncated', 'stage', 'leaseActiveAtBuildReturn', 'primaryExceptionKind', 'verificationExceptionKind', 'schema', 'buildErrorKinds', 'totalWarnings'}
FAILURE_CODES={'PERFORMANCE_PACKAGE_MISSING','PERFORMANCE_PACKAGE_NAME','PERFORMANCE_PACKAGE_VERSION','PERFORMANCE_PACKAGE_SOURCE','PERFORMANCE_PREFERENCE','PERFORMANCE_LINK','PERFORMANCE_PACKAGE','PERFORMANCE_BASELINE','PERFORMANCE_INVENTORY','PERFORMANCE_PAYLOAD','PERFORMANCE_META','PERFORMANCE_MOVE','PERFORMANCE_PACKED_REPORT','PERFORMANCE_PACKED_CONTENT','PERFORMANCE_PRIVATE','PIN_LINK', 'RESTORATION_XML', 'INVENTORY_NONREGULAR', 'ROOT_BYTES', 'BUILD_OR_SCENE_FAILED', 'INVENTORY_LINK', 'ROOT_IMPORT_HASH', 'PACKAGE_IDENTITY', 'PIN_BYTES', 'DEPENDENCY_PATH', 'INVENTORY_DIRECTORY', 'SAVED_RUNTIME_IDENTITY', 'BOOTSTRAP_OWNER', 'ROOT_DEPENDENCY', 'REQUEST_RECEIPT_HASH', 'BOOTSTRAP_BINDING', 'REGION_BINDING', 'REGION_OWNER', 'SCENE_COMPONENT', 'DEPENDENCY_KIND', 'INVENTORY_SET', 'ROOT_DEPENDENCY_BYTES', 'SCENE_SEQUENCE', 'PIN_MISSING', 'REGION_IDENTITY', 'BUILTIN_DEPENDENCY', 'IMPORT_FINGERPRINT', 'TARGET_OUTPUT', 'REQUEST_IDENTITY', 'PIN_PATH', 'UNCLASSIFIED_EXCEPTION', 'DIRTY_SCENE', 'ENTRY_PROFILE', 'LEASE_PROFILE', 'RESTORATION_PROOF', 'REQUEST_HASH', 'DEPENDENCY_BYTES', 'BUILD_PROFILE'}
EXCEPTIONS={'NONE','BUILD_FAILED','UNAUTHORIZED_ACCESS','IO','OTHER'}
CALLBACKS={'CANDIDATE_PERFORMANCE','NONE','PRODUCTION_PREPROCESS','PRODUCTION_SCENE','CANDIDATE_SCENE'}
ROLES={'NONE','CONTENT','BOOTSTRAP','FIRST_STATION','SCRAPYARD','NIGHT_BEACON'}
BUILD_ERROR_KINDS={'CANDIDATE_GATE','PRODUCTION_GATE','CS_COMPILATION','SHADER_ERROR','UNCLASSIFIED_BUILD_ERROR'}
RUNTIME_FILE_ROOTS={'DesertRV.x86_64','UnityPlayer.so','UnityCrashHandler64','libdecor-0.so.0','libdecor-cairo.so'}
RUNTIME_ROOTS=RUNTIME_FILE_ROOTS|{'DesertRV_Data'}
# Exact native symbols observed in the same pinned official development_mono template.
DEBUG_FILES={'UnityPlayer_s.debug','LinuxPlayer_s.debug'}
MONO_FILES={'DesertRV_Data/MonoBleedingEdge/x86_64/'+n for n in ('libmonobdwgc-2.0.so','libmono-native.so','libMonoPosixHelper.so')}
REQUIRED_FILES={'DesertRV.x86_64','UnityPlayer.so','libdecor-0.so.0','libdecor-cairo.so','DesertRV_Data/Managed/Assembly-CSharp.dll','DesertRV_Data/MonoBleedingEdge/etc/mono/config'}|MONO_FILES
# Burst 1.8.29 FetchOutputPath uses PlayerSettings.productName, not the executable basename.
DEBUG_ROOTS={'DESERTRV_JOURNEY_CANDIDATE_BurstDebugInformation_DoNotShip'}

# Closed post-build observations. Raw exception text and private logs never leave the container.
HOST_PHASES={'NONE','PREFLIGHT','PREFLIGHT_GUARD','RECORD','STAGE','STAGE_REQUEST','PREFLIGHT_MODULES','PREFLIGHT_ENGINE_LAYOUT','PREFLIGHT_UNION','PREFLIGHT_REQUEST','PREFLIGHT_ARCHIVER','RECORD_NATIVE','RESTORE_SOURCE','RESTORE_UNION','POSTBUILD_UNION','STAGE_UNION','STAGE_RECEIPT','STAGE_INVENTORY','STAGE_ARCHIVE','STAGE_REVERIFY','STAGED'}
HOST_SOURCE_PATHS=('tasks/desert-rv/scripts/journey_rebuild_dispatch.py','tasks/desert-rv/scripts/player/journey_linux_export.py','tasks/desert-rv/scripts/player/player_window_smoke.py','tasks/desert-rv/scripts/rendered/prepared_source.py','tasks/desert-rv/art/journey-preparation/linux_build_input.py','tasks/desert-rv/art/journey-preparation/restore_preparation.py','tasks/desert-rv/art/journey-preparation/generated_export.py','tasks/desert-rv/art/journey-preparation/pipeline.py','tasks/desert-rv/art/import-candidate/strict_output.py','tasks/desert-rv/art/import-candidate/pouncer_output.py','tasks/desert-rv/art/import-candidate/weapon_output.py')
HOST_BASE_CODES={'RUNTIME_ROOT_SET','RUNTIME_REQUIRED_FILES','RUNTIME_DEBUG_TYPE','NONE','MISSING_YAML','MISSING_PIL','MISSING_MODULE','PERMISSION_DENIED','FILE_NOT_FOUND','OS_ERROR','VALIDATION_REJECTED','OTHER_ERROR'}

@functools.lru_cache(maxsize=1)
def host_codes():
    import ast
    result=set(HOST_BASE_CODES)
    for name in HOST_SOURCE_PATHS:
        tree=ast.parse((ROOT/name).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                if node.func.id=='require' and len(node.args)>=2 and isinstance(node.args[1],ast.Constant) and isinstance(node.args[1].value,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,100}',node.args[1].value):
                    prefix='JOURNEY_DISPATCH_' if name.endswith('/journey_rebuild_dispatch.py') else '';result.add(prefix+node.args[1].value)
                if name.endswith('/journey_rebuild_dispatch.py') and node.func.id=='ValueError' and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str) and re.fullmatch('JOURNEY_DISPATCH_[A-Z0-9_]{1,80}',node.args[0].value):result.add(node.args[0].value)
    return result

def empty_runtime():return dict(observed=False,totalEntries=0,omittedEntries=0,entries=[])
def empty_engine():return dict(scope='UNITY_6000_3_19F1_LINUX_STANDALONE_MODULE',status='NOT_OBSERVED',runtime=empty_runtime())
def empty_host():return dict(engineLayout=empty_engine(),schema=1,lastPhase='NONE',completedPhases=[],failurePhase='NONE',failureCode='NONE',failureSource='',failureLine=0,nativeReceiptPin=None,runtime=empty_runtime())
def host_path():return RECOVERY/'host-diagnostic.json'
def validate_host(value):
    require(isinstance(value,dict) and set(value)==set(empty_host()) and value['schema']==1)
    require(value['lastPhase'] in HOST_PHASES and value['failurePhase'] in HOST_PHASES and value['failureCode'] in host_codes())
    done=value['completedPhases'];require(isinstance(done,list) and len(done)<=len(HOST_PHASES) and len(done)==len(set(done)) and set(done)<=HOST_PHASES-{'NONE'})
    require((value['failurePhase']=='NONE')==(value['failureCode']=='NONE'))
    require(value['failureSource'] in ('',)+HOST_SOURCE_PATHS and type(value['failureLine']) is int and 0<=value['failureLine']<=100000 and (bool(value['failureSource'])==(value['failureLine']>0)))
    pin=value['nativeReceiptPin'];require(pin is None or isinstance(pin,dict) and set(pin)=={'sha256','bytes'} and re.fullmatch('[a-f0-9]{64}',pin['sha256']) and type(pin['bytes']) is int and 0<pin['bytes']<=32768)
    validate_runtime(value['runtime'])
    engine=value['engineLayout'];require(isinstance(engine,dict) and set(engine)==set(empty_engine()) and engine['scope']==empty_engine()['scope'] and engine['status'] in {'NOT_OBSERVED','MISSING','OBSERVED','IO_UNAVAILABLE'})
    validate_runtime(engine['runtime']);require(engine['runtime']['observed']==(engine['status']=='OBSERVED'))
    return value

def validate_runtime(runtime):
    require(isinstance(runtime,dict) and set(runtime)==set(empty_runtime()) and type(runtime['observed']) is bool)
    require(type(runtime['totalEntries']) is int and type(runtime['omittedEntries']) is int and 0<=runtime['omittedEntries']<=runtime['totalEntries']<=100000)
    rows=runtime['entries'];require(isinstance(rows,list) and len(rows)<=2048 and len(rows)+runtime['omittedEntries']==runtime['totalEntries'])
    if not runtime['observed']:require(runtime['totalEntries']==0)
    previous=''
    for row in rows:
        require(isinstance(row,dict) and set(row)=={'path','kind','mode','bytes','sha256'})
        name=row['path'];require(runtime_name(name) and name>previous);previous=name
        require(row['kind'] in {'FILE','DIRECTORY','SYMLINK','OTHER'} and type(row['mode']) is int and 0<=row['mode']<=0o7777 and type(row['bytes']) is int and 0<=row['bytes']<=2**63-1)
        require(isinstance(row['sha256'],str) and (re.fullmatch('[a-f0-9]{64}',row['sha256']) if row['kind']=='FILE' and row['bytes']<=2*1024**3 else row['sha256']==''))
    return runtime

def runtime_name(name):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_./ @+()\-]{1,512}',name):return False
    parts=pathlib.PurePosixPath(name).parts
    return bool(parts) and not name.startswith('/') and all(p not in ('.','..') and not p.startswith('.') for p in parts) and pathlib.PurePosixPath(name).suffix.lower() not in {'.log','.ulf','.alf','.lic','.key'} and parts[-1].lower() not in {'credentials','credentials.json','activation.log','return.log'}

def observe_runtime(folder,engine_only=False):
    import stat
    result=empty_runtime()
    if not folder.is_dir() or folder.is_symlink():return result
    result['observed']=True;paths=[]
    for current,dirs,files in os.walk(folder,followlinks=False):
        for name in dirs+files:paths.append(pathlib.Path(current)/name)
        dirs[:]=[name for name in dirs if runtime_name((pathlib.Path(current)/name).relative_to(folder).as_posix()) and not (pathlib.Path(current)/name).is_symlink()]
    result['totalEntries']=len(paths)
    for p in sorted(paths):
        name=p.relative_to(folder).as_posix()
        if not runtime_name(name) or len(result['entries'])>=2048:continue
        if engine_only and p.name not in RUNTIME_FILE_ROOTS|DEBUG_FILES|{pathlib.PurePosixPath(n).name for n in MONO_FILES} and not p.name.endswith('_s.debug'):continue
        info=p.lstat();kind='FILE' if stat.S_ISREG(info.st_mode) else 'DIRECTORY' if stat.S_ISDIR(info.st_mode) else 'SYMLINK' if stat.S_ISLNK(info.st_mode) else 'OTHER';digest=''
        if kind=='FILE' and info.st_size<=2*1024**3:
            h=hashlib.sha256()
            with p.open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
            digest=h.hexdigest()
        result['entries'].append(dict(path=name,kind=kind,mode=stat.S_IMODE(info.st_mode),bytes=info.st_size,sha256=digest))
    result['omittedEntries']=result['totalEntries']-len(result['entries']);return result

def observe_engine_layout():
    # Fixed, already version-pinned installed Unity module; no execution or package mutation.
    root=pathlib.Path('/opt/unity/Editor/Data/PlaybackEngines/LinuxStandaloneSupport');entry=empty_engine()
    try:
        if root.is_dir() and not root.is_symlink():entry.update(status='OBSERVED',runtime=observe_runtime(root,engine_only=True))
        else:entry['status']='MISSING'
    except OSError:entry['status']='IO_UNAVAILABLE'
    value=host_state();value['engineLayout']=entry;save_host(value)

def host_state():return validate_host(read_json(host_path())) if host_path().exists() else empty_host()
def save_host(value):RECOVERY.mkdir(exist_ok=True);atomic(host_path(),validate_host(value))
def host_error(error):
    code='MISSING_YAML' if isinstance(error,ModuleNotFoundError) and error.name=='yaml' else 'MISSING_PIL' if isinstance(error,ModuleNotFoundError) and error.name in {'PIL','PIL.Image'} else 'MISSING_MODULE' if isinstance(error,ModuleNotFoundError) else 'PERMISSION_DENIED' if isinstance(error,PermissionError) else 'FILE_NOT_FOUND' if isinstance(error,FileNotFoundError) else 'OS_ERROR' if isinstance(error,OSError) else 'VALIDATION_REJECTED' if isinstance(error,ValueError) else 'OTHER_ERROR'
    if str(error) in (host_codes()-HOST_BASE_CODES)|{'RUNTIME_ROOT_SET','RUNTIME_REQUIRED_FILES','RUNTIME_DEBUG_TYPE'}:code=str(error)
    result=dict(code=code,source='',line=0);tb=error.__traceback__;allowed={str((ROOT/p).resolve()):p for p in HOST_SOURCE_PATHS}
    while tb:
        known=allowed.get(str(pathlib.Path(tb.tb_frame.f_code.co_filename).resolve()))
        if known:result.update(source=known,line=tb.tb_lineno)
        tb=tb.tb_next
    return result

def host_phase(phase,action):
    value=host_state();value['lastPhase']=phase;save_host(value)
    try:
        result=action();value=host_state()
        if phase not in value['completedPhases']:value['completedPhases'].append(phase)
        save_host(value);return result
    except Exception as error:
        value=host_state()
        if value['failurePhase']=='NONE':
            failure=host_error(error);value.update(failurePhase=phase,failureCode=failure['code'],failureSource=failure['source'],failureLine=failure['line'])
            save_host(value)
        raise

def preflight(logs):
    import importlib
    from pipeline import guard
    host_phase('PREFLIGHT_GUARD',guard)
    host_phase('PREFLIGHT_MODULES',lambda:(importlib.import_module('yaml'),importlib.import_module('PIL.Image')))
    host_phase('PREFLIGHT_ENGINE_LAYOUT',observe_engine_layout)
    host_phase('PREFLIGHT_UNION',verify_union);host_phase('PREFLIGHT_REQUEST',request)
    def archiver():
        probe=logs/'archiver-self-test';require(not probe.exists());probe.mkdir()
        try:
            for name in sorted(REQUIRED_FILES):
                p=probe/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'ARCHIVER_SELF_TEST_NOT_AN_EXECUTABLE')
            records=inventory(probe);tar_bundle(probe,records,logs/'archiver-self-test.tar.gz');verify_tar(logs/'archiver-self-test.tar.gz',records)
        finally:shutil.rmtree(probe)
    host_phase('PREFLIGHT_ARCHIVER',archiver)

def save_native_receipt_observation():
    raw,native=sealed_native_receipt(STATE/'linux-build-receipt.json');r=request();require(native['requestSha256']==sha(STATE/'linux-build-input.json'));restoration_matches(native,r)
    require(native['generatedReceiptSha256']==r['generatedReceiptSha256'] and native['boundaryNativeXmlSha256']==r['boundaryNativeXmlSha256'] and native['executableSha256']==sha(BUILD/'DesertRV.x86_64'))
    value=host_state();value['nativeReceiptPin']=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw));save_host(value);value['runtime']=observe_runtime(BUILD);save_host(value)


def producer_url():return 'https://github.com/yangerstar1/task-workbench/actions/runs/'+os.environ['GITHUB_RUN_ID']
def verify_union():
    return linux_build_input.verify()
def request():
    r=read_json(STATE/'linux-build-input.json');require(sha(STATE/'linux-build-input.json')==safe(STATE/'linux-build-input.sha256').read_text().strip())
    require(r['schema']==1 and r['label']=='CANDIDATE_LINUX_DEVELOPMENT_ONLY' and r['sourceCommit']==os.environ['GITHUB_SHA'] and r['producerRunUrl']==producer_url() and r['approved'] is False)
    return r

def sealed_native_receipt(path):
    raw=safe(path).read_bytes();require(len(raw)<=32768)
    def unique(pairs):
        result={}
        for key,value in pairs:require(key not in result);result[key]=value
        return result
    return raw,native_receipt(json.loads(raw,object_pairs_hook=unique))

def native_receipt(value):
    require(isinstance(value,dict) and set(value)==RECEIPT_KEYS)
    require(type(value['schema']) is int and value['schema']==1 and value['label']==MODE)
    require(value['sourceCommit']==os.environ['GITHUB_SHA'] and value['producerRunUrl']==producer_url())
    for key in ('generatedReceiptSha256','requestSha256','executableSha256','boundaryNativeXmlSha256'):require(isinstance(value[key],str) and re.fullmatch('[a-f0-9]{64}',value[key]))
    require(value['unityVersion']=='6000.3.19f1' and value['target']=='StandaloneLinux64' and value['backend']=='Mono2x' and value['define']=='DESERTRV_CANDIDATE_LINUX' and value['executable']=='DesertRV.x86_64' and value['scenes']==SCENES)
    require(type(value['boundaryNativeCases']) is int and value['boundaryNativeCases']==17)
    require(value['temporarySettingsFiles']==['ProjectSettings/ProjectSettings.asset'] and value['temporarySettingsApiFields']==['scriptingBackend.Standalone','fullScreenMode','defaultScreenWidth','defaultScreenHeight','productName','resizableWindow'])
    for key in ('candidateOnly','development','detailedBuildReport','performanceTestResourcesExcluded','settingsRestored','sourceBytesUnchanged'):require(value[key] is True)
    for key in ('approved','visualReviewed','gameplayReviewed','audioAuditioned'):require(value[key] is False)
    pin=value['restorationProof'];restored=isinstance(pin,dict) and bool(pin.get('path'))
    if restored:
        require(set(pin)=={'path','sha256'} and pin['path']=='tasks/desert-rv/unity/JourneyEvidence/JourneyPreparation/restoration-revalidated.json' and re.fullmatch('[a-f0-9]{64}',pin['sha256']))
        require(re.fullmatch('[a-f0-9]{40}',value['assetProducerSourceCommit']) and re.fullmatch(r'https://github\.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]*',value['assetProducerRunUrl']) and re.fullmatch('[a-f0-9]{64}',value['restorationNativeXmlSha256']))
    else:require(pin is None or pin=={'path':'','sha256':''});require(all(value[k] in ('',None) for k in ('assetProducerSourceCommit','assetProducerRunUrl','restorationNativeXmlSha256')))
    return value

def inventory_observation(value):
    require(isinstance(value,dict) and set(value)=={'observed','truncated','totalChanges','addedFiles','removedFiles','addedDirectories','removedDirectories','unsafePathsOmitted','entries'})
    require(type(value['observed']) is bool and type(value['truncated']) is bool)
    for k in ('totalChanges','addedFiles','removedFiles','addedDirectories','removedDirectories','unsafePathsOmitted'):require(type(value[k]) is int and 0<=value[k]<=2147483647)
    require(value['totalChanges']==sum(value[k] for k in ('addedFiles','removedFiles','addedDirectories','removedDirectories')))
    rows=value['entries'];require(isinstance(rows,list) and len(rows)<=32 and len(rows)+value['unsafePathsOmitted']<=value['totalChanges'] and value['truncated']==(value['totalChanges']>len(rows)))
    if not value['observed']:require(value['totalChanges']==0 and value['unsafePathsOmitted']==0 and rows==[])
    previous=None;counts={('ADDED','FILE'):0,('REMOVED','FILE'):0,('ADDED','DIRECTORY'):0,('REMOVED','DIRECTORY'):0}
    for row in rows:
        require(isinstance(row,dict) and set(row)=={'path','change','kind','sha256','measurement','bytes'})
        name=row['path'];require(isinstance(name,str) and re.fullmatch(r'(Assets|Packages|ProjectSettings)/[A-Za-z0-9_./ @+()\-]{1,480}',name) and all(n not in ('','.','..') for n in name.split('/')))
        require(row['change'] in {'ADDED','REMOVED'} and row['kind'] in {'FILE','DIRECTORY'});key=(name,row['kind'],row['change']);require(previous is None or key>previous);previous=key;counts[(row['change'],row['kind'])]+=1
        require(type(row['bytes']) is int and -1<=row['bytes']<=9223372036854775807 and isinstance(row['sha256'],str))
        if row['kind']=='DIRECTORY':require(row['measurement']=='NOT_APPLICABLE' and row['bytes']==0 and row['sha256']=='')
        elif row['change']=='REMOVED':
            require(re.fullmatch('[a-f0-9]{64}',row['sha256']))
            require(row['measurement']=='EXPECTED_PIN_PRIOR_SIZE' and row['bytes']>=0 or row['measurement']=='EXPECTED_PIN_SIZE_UNAVAILABLE' and row['bytes']==-1)
        elif row['measurement']=='ACTUAL_BYTES':require(0<=row['bytes']<=128*1024**2 and re.fullmatch('[a-f0-9]{64}',row['sha256']))
        elif row['measurement']=='SIZE_ONLY_LIMIT':require(row['bytes']>128*1024**2 and row['sha256']=='')
        else:require(row['measurement']=='UNREADABLE' and row['bytes']==-1 and row['sha256']=='')
    for kind,key in [(('ADDED','FILE'),'addedFiles'),(('REMOVED','FILE'),'removedFiles'),(('ADDED','DIRECTORY'),'addedDirectories'),(('REMOVED','DIRECTORY'),'removedDirectories')]:require(counts[kind]<=value[key])
    if not value['truncated']:require(all(counts[kind]==value[key] for kind,key in [(('ADDED','FILE'),'addedFiles'),(('REMOVED','FILE'),'removedFiles'),(('ADDED','DIRECTORY'),'addedDirectories'),(('REMOVED','DIRECTORY'),'removedDirectories')]))

PERFORMANCE_JSON=['Assets/Resources/PerformanceTestRunInfo.json','Assets/Resources/PerformanceTestRunSettings.json']
PERFORMANCE_FILES=['Assets/Resources.meta',PERFORMANCE_JSON[0],PERFORMANCE_JSON[0]+'.meta',PERFORMANCE_JSON[1],PERFORMANCE_JSON[1]+'.meta']
def performance_observation(value):
    require(isinstance(value,dict) and set(value)=={'status','packageIdentity','packageVerified','baselineAbsent','preferenceRestored','synchronousImportCompleted','exactInventoryRestored','packedReportAvailable','packedContainers','packedObjects','packedSourceObjects','packedJsonHits','packedScenePaths','callbackScenePaths','jsonGuids','generated'})
    require(value['packageIdentity'] in {'NOT_OBSERVED','MISSING','NAME_MISMATCH','REGISTERED_3_5_0','REGISTERED_3_0_3','OTHER_VERSION'})
    require(value['status'] in {'NOT_ARMED','ARMED','IMPORTED','QUARANTINED','PACKED_VERIFIED'})
    for k in ('packageVerified','baselineAbsent','preferenceRestored','synchronousImportCompleted','exactInventoryRestored','packedReportAvailable'):require(type(value[k]) is bool)
    for k in ('packedContainers','packedObjects','packedSourceObjects','packedJsonHits'):require(type(value[k]) is int and 0<=value[k]<=2147483647)
    require(value['packedJsonHits']<=value['packedObjects'] and value['packedSourceObjects']<=value['packedObjects'])
    scenes=value['packedScenePaths'];require(isinstance(scenes,list) and scenes==sorted(set(scenes)) and set(scenes)<=set(SCENES))
    callbacks=value['callbackScenePaths'];require(isinstance(callbacks,list) and callbacks==sorted(set(callbacks)) and set(callbacks)<=set(SCENES))
    guids=value['jsonGuids'];require(isinstance(guids,list) and len(guids) in (0,2) and len(set(guids))==len(guids) and all(isinstance(g,str) and re.fullmatch('[a-f0-9]{32}',g) for g in guids))
    inventory_observation(value['generated'])
    if value['packageVerified']:require(value['packageIdentity']=='REGISTERED_3_5_0')
    if value['status']!='NOT_ARMED':require(value['packageVerified'] and value['baselineAbsent'])
    if value['generated']['observed']:
        inventory=value['generated'];require(inventory['totalChanges']==6 and inventory['addedFiles']==5 and inventory['addedDirectories']==1 and inventory['removedFiles']==inventory['removedDirectories']==inventory['unsafePathsOmitted']==0 and not inventory['truncated'])
        require([r['path'] for r in inventory['entries']]==sorted(['Assets/Resources']+PERFORMANCE_FILES))
        for row in inventory['entries']:require(row['change']=='ADDED' and (row['path']=='Assets/Resources' and row['kind']=='DIRECTORY' or row['path'] in PERFORMANCE_FILES and row['kind']=='FILE' and row['measurement']=='ACTUAL_BYTES' and 0<row['bytes']<=65536))
    if value['status'] in {'IMPORTED','QUARANTINED','PACKED_VERIFIED'}:require(value['generated']['observed'] and value['synchronousImportCompleted'] and len(guids)==2)
    if value['status'] in {'QUARANTINED','PACKED_VERIFIED'}:require(value['exactInventoryRestored'])
    if not value['packedReportAvailable']:require(value['packedContainers']==value['packedObjects']==value['packedSourceObjects']==value['packedJsonHits']==0 and scenes==[] and callbacks==[])
    else:require(value['packedContainers']>0 and value['packedObjects']>=len(scenes))
    if value['status']=='PACKED_VERIFIED':require(value['packedReportAvailable'] and value['packedObjects']>0 and value['packedSourceObjects']>0 and value['packedJsonHits']==0 and callbacks==sorted(SCENES))
    return value

def performance_success(value):
    return value['status']=='PACKED_VERIFIED' and value['preferenceRestored'] and value['exactInventoryRestored'] and value['packedReportAvailable'] and value['packedJsonHits']==0 and value['packedSourceObjects']>0 and value['callbackScenePaths']==sorted(SCENES)


def root_observation(value):
    require(isinstance(value,dict) and set(value)=={'observed','rootBytesMatch','rootDependencyBytesMatch','slot','expectedImportHash','observedImportHash'})
    for k in ('observed','rootBytesMatch','rootDependencyBytesMatch'):require(type(value[k]) is bool)
    require(value['slot'] in ROLES)
    if value['observed']:require(value['slot']!='NONE' and all(isinstance(value[k],str) and re.fullmatch('[a-f0-9]{32}',value[k]) for k in ('expectedImportHash','observedImportHash')))
    else:require(value['slot']=='NONE' and value['expectedImportHash']==value['observedImportHash']=='' and not value['rootBytesMatch'] and not value['rootDependencyBytesMatch'])

def safe_build_message(value):
    require(isinstance(value,dict) and set(value)=={'category','code','source','text','line'} and value['category'] in BUILD_ERROR_KINDS)
    category=value['category'];code=value['code'];source=value['source'];line=value['line'];expected=''
    require(type(line) is int and 0<=line<=9999999 and isinstance(source,str))
    if category=='CANDIDATE_GATE':require(code in FAILURE_CODES and source=='' and line==0);expected='Candidate build gate rejected: '+code
    elif category=='PRODUCTION_GATE':require(code=='NONE' and source=='' and line==0);expected='Formal journey scenes require current production content preflight.'
    elif category=='CS_COMPILATION':
        if code=='NONE':require(source=='' and line==0);expected='Error building Player because scripts had compiler errors.'
        else:
            require(code in recovery.startup.CODES);expected='C# compiler diagnostic: '+code
            if source:require(source in recovery.startup.source_map(PROJECT) and line>0);expected+=' at '+source+':'+str(line)
            else:require(line==0)
    elif category=='SHADER_ERROR':require(code=='NONE' and source=='' and line==0);expected='Build report contains a shader error.'
    else:require(code=='NONE' and source=='' and line==0)
    require(value['text']==expected and len(expected)<=512)

def native_diagnostic(value):
    require(isinstance(value,dict) and set(value)==DIAG_KEYS and type(value['schema']) is int and value['schema']==1 and value['label']=='CANDIDATE_LINUX_BUILD_DIAGNOSTIC')
    require(value['stage'] in {'ENTRY','SOURCE_VERIFIED','CONTENT_VERIFIED','BUILD_PLAYER_ENTERED','BUILD_PLAYER_RETURNED','RECEIPT_WRITTEN'})
    require(value['exceptionKind'] in EXCEPTIONS and value['buildResult'] in {'UNAVAILABLE','SUCCEEDED','FAILED','CANCELLED','UNKNOWN'})
    for key in ('settingsRestored','sourceBytesUnchanged','receiptWritten','buildReportAvailable','leaseActiveAtBuildReturn','assemblyReloadObserved','buildMessagesTruncated'):require(type(value[key]) is bool)
    for key in ('totalErrors','totalWarnings'):require(type(value[key]) is int and 0<=value[key]<=4294967295)
    for key in ('activeTargetAtEntry','activeTargetBeforeBuild','activeTargetAfterBuild','reportTarget'):require(value[key] in {'NOT_OBSERVED','LINUX64','ANDROID','OTHER'})
    require(value['buildReportAvailable']==(value['buildResult']!='UNAVAILABLE') and value['buildReportAvailable']==(value['reportTarget']!='NOT_OBSERVED'))
    if not value['buildReportAvailable']:require(value['totalErrors']==value['totalWarnings']==0 and value['buildErrorKinds']==[] and value['buildMessages']==[])
    for prefix in ('primary','restoration','verification'):
        require(value[prefix+'FailureCode'] in FAILURE_CODES|{'NONE'} and value[prefix+'ExceptionKind'] in EXCEPTIONS)
        require((value[prefix+'FailureCode']=='NONE')==(value[prefix+'ExceptionKind']=='NONE'))
    require(value['leaseClosedReason'] in {'NONE','EXPLICIT','ASSEMBLY_RELOAD','EDITOR_QUIT'})
    for prefix in ('primary','verification'):
        require(value[prefix+'CallbackGate'] in CALLBACKS and value[prefix+'SceneRole'] in ROLES);root_observation(value[prefix+'RootMismatch']);inventory_observation(value[prefix+'Inventory'])
    performance_observation(value['performanceResources'])
    kinds=value['buildErrorKinds'];require(isinstance(kinds,list) and kinds==sorted(set(kinds)) and set(kinds)<=BUILD_ERROR_KINDS)
    messages=value['buildMessages'];require(isinstance(messages,list) and len(messages)<=32)
    for message in messages:safe_build_message(message);require(message['category'] in kinds)
    return value

def diagnostic_success(d):
    return d is not None and performance_success(d['performanceResources']) and d['stage']=='RECEIPT_WRITTEN' and d['buildResult']=='SUCCEEDED' and d['exceptionKind']=='NONE' and d['buildReportAvailable'] is True and d['reportTarget']=='LINUX64' and d['totalErrors']==0 and all(d[p+'FailureCode']=='NONE' for p in ('primary','restoration','verification')) and all(d[p+'Inventory']['totalChanges']==0 for p in ('primary','verification')) and all(d[k] is True for k in ('settingsRestored','sourceBytesUnchanged','receiptWritten'))

def runtime_require(condition,code):
    if not condition:raise ValueError(code)

def validate_records(records):
    require(isinstance(records,list) and 0<len(records)<=20000);previous='';total=0;roots=set()
    for row in records:
        require(isinstance(row,dict) and set(row)=={'path','size','sha256','mode'})
        name=row['path'];require(isinstance(name,str) and len(name)<=512 and name>previous and '\\' not in name and '\x00' not in name);previous=name;path=pathlib.PurePosixPath(name)
        require((len(path.parts)==1) == (path.parts[0] in RUNTIME_FILE_ROOTS))
        require(not path.is_absolute() and '..' not in path.parts and path.parts[0] in RUNTIME_ROOTS and not any(part.startswith('.') for part in path.parts));roots.add(path.parts[0])
        require(path.suffix.lower() not in {'.log','.ulf','.alf','.lic','.key','.pdb','.mdb','.debug'} and path.name.lower() not in {'credentials','credentials.json','activation.log','return.log'})
        require(type(row['size']) is int and 0<=row['size']<=2*1024**3 and isinstance(row['sha256'],str) and re.fullmatch('[a-f0-9]{64}',row['sha256']))
        require(type(row['mode']) is int and row['mode']==(0o755 if path.parts[0] in {'DesertRV.x86_64','UnityCrashHandler64'} else 0o644));total+=row['size']
    require(total<=8*1024**3 and {'DesertRV.x86_64','UnityPlayer.so','DesertRV_Data'}<=roots)
    runtime_require(REQUIRED_FILES<={row['path'] for row in records},'RUNTIME_REQUIRED_FILES')
    return records

def inventory(folder):
    folder=safe(folder,False);require(folder.is_dir());names={p.name for p in folder.iterdir()}
    runtime_require({'DesertRV.x86_64','UnityPlayer.so','DesertRV_Data'}<=names<=RUNTIME_ROOTS|DEBUG_ROOTS|DEBUG_FILES,'RUNTIME_ROOT_SET')
    for name in names & DEBUG_FILES:runtime_require((folder/name).is_file(),'RUNTIME_DEBUG_TYPE')
    for name in names & DEBUG_ROOTS:runtime_require((folder/name).is_dir(),'RUNTIME_DEBUG_TYPE')
    for name in names & RUNTIME_ROOTS:require((folder/name).is_file() if name in RUNTIME_FILE_ROOTS else (folder/name).is_dir())
    records=[];total=0
    for p in sorted(folder.rglob('*')):
        safe(p,False);require(p.is_file() or p.is_dir());name=p.relative_to(folder).as_posix();top=p.relative_to(folder).parts[0]
        if top in DEBUG_ROOTS or name in DEBUG_FILES:continue
        if p.is_dir():continue
        require(not any(part.startswith('.') for part in pathlib.PurePosixPath(name).parts))
        require(p.suffix.lower() not in {'.log','.ulf','.alf','.lic','.key'} and p.name.lower() not in {'credentials','credentials.json','activation.log','return.log'})
        if p.suffix.lower() in {'.pdb','.mdb','.debug'}:continue # Optional debugging symbols are not runtime closure.
        size=p.stat().st_size;require(0<=size<=2*1024**3);total+=size;require(total<=8*1024**3)
        records.append(dict(path=name,size=size,sha256=sha(p),mode=0o755 if top in {'DesertRV.x86_64','UnityCrashHandler64'} else 0o644))
    return validate_records(records)

def tar_bundle(folder,records,destination):
    with safe(destination,False).open('wb') as output:
        with gzip.GzipFile(filename='',mode='wb',fileobj=output,mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w') as archive:
                for row in records:
                    p=safe(folder/row['path']);require(sha(p)==row['sha256'] and p.stat().st_size==row['size'])
                    info=tarfile.TarInfo(row['path']);info.size=row['size'];info.mode=row['mode'];info.mtime=0;info.uid=info.gid=0;info.uname=info.gname=''
                    with p.open('rb') as content:archive.addfile(info,content)

def verify_tar(path,records):
    validate_records(records);require(safe(path).stat().st_size<=8*1024**3);expected={r['path']:r for r in records};seen=set()
    with tarfile.open(path,'r:gz') as archive:
        for member in archive:
            require(member.name in expected and member.name not in seen and member.isfile() and not member.issym() and not member.islnk());row=expected[member.name]
            require(member.size==row['size'] and member.mode==row['mode'] and member.uid==member.gid==member.mtime==0 and member.uname==member.gname=='')
            digest=hashlib.sha256()
            with archive.extractfile(member) as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            require(digest.hexdigest()==row['sha256']);seen.add(member.name)
    require(seen==set(expected))

def before():
    from verify_inputs import verify_gameci
    verify_gameci(ROOT/'_ci/gameci-journey-linux',read_json(TASK/'scripts/rendered/official-gameci-pins.json'))
    verify_union();request()
    for p in (BUILD,STAGED,PUBLIC,CONTROL,RECOVERY):require(not p.exists() and not p.is_symlink())
    atomic(TASK/'player-source-before.json',recovery.tracked())

def snapshot(logs):recovery.snapshot_recovery(logs)
def restore(logs):
    def source():require(recovery.recover_source(logs)==0)
    host_phase('RESTORE_SOURCE',source)
    host_phase('RESTORE_UNION',verify_union);return 0

def restoration_matches(native,request):
    for key in ('assetProducerSourceCommit','assetProducerRunUrl','restorationNativeXmlSha256'):require((native.get(key) or '')==(request.get(key) or ''))
    a=native.get('restorationProof');b=request.get('restorationProof')
    if isinstance(a,dict) and a.get('path'):require(a==b)
    else:require(b is None or b=={'path':'','sha256':''})

def stage():return host_phase('STAGE',stage_inner)

def stage_inner():
    host_phase('STAGE_UNION',verify_union);r=host_phase('STAGE_REQUEST',request)
    def receipt():
        _,native=sealed_native_receipt(STATE/'linux-build-receipt.json');diagnostic=native_diagnostic(read_json(STATE/'linux-build-diagnostic.json'));require(diagnostic_success(diagnostic))
        require(native['requestSha256']==sha(STATE/'linux-build-input.json'));restoration_matches(native,r)
        require(native['boundaryNativeXmlSha256']==r['boundaryNativeXmlSha256'] and r['boundaryNativeCases']==17)
        require(native['generatedReceiptSha256']==r['generatedReceiptSha256']==sha(TASK/'journey-preparation-export/generated/receipt.json'))
        require(native['executableSha256']==sha(BUILD/'DesertRV.x86_64'));return native
    native=host_phase('STAGE_RECEIPT',receipt);records=host_phase('STAGE_INVENTORY',lambda:inventory(BUILD))
    require(not STAGED.exists());temp=pathlib.Path(tempfile.mkdtemp(prefix='journey-linux-stage-',dir=TASK));success=False
    try:
        host_phase('STAGE_ARCHIVE',lambda:tar_bundle(BUILD,records,temp/'player.tar.gz'))
        def reverify():
            require(inventory(BUILD)==records);verify_union();verify_tar(temp/'player.tar.gz',records)
        host_phase('STAGE_REVERIFY',reverify)
        manifest=dict(schema=1,label='REUSABLE_CANDIDATE_LINUX_PLAYER_UNREVIEWED',sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=producer_url(),nativeReceiptSha256=sha(STATE/'linux-build-receipt.json'),inputSha256=sha(STATE/'linux-build-input.json'),generatedReceiptSha256=r['generatedReceiptSha256'],sourceStateSha256=sha(TASK/'SOURCE-STATE.json'),bundleSha256=sha(temp/'player.tar.gz'),bundleBytes=(temp/'player.tar.gz').stat().st_size,files=records,nativeReceipt=native,playerExecuted=False,approved=False)
        def commit():atomic(temp/'manifest.json',manifest);os.replace(temp,STAGED)
        host_phase('STAGED',commit);success=True
    finally:
        if not success:shutil.rmtree(temp,ignore_errors=True)

def record(logs,exit_code):
    require(type(exit_code) is int and 0<=exit_code<=255);RECOVERY.mkdir(exist_ok=True)
    diagnostic=None
    if (STATE/'linux-build-diagnostic.json').exists():diagnostic=native_diagnostic(read_json(STATE/'linux-build-diagnostic.json'))
    classified=recovery.startup.classify(logs,PROJECT,editor=exit_code)
    atomic(RECOVERY/'build-diagnostic.json',dict(batchExitCode=exit_code,batchTimedOut=exit_code==124,native=diagnostic,logClassification=classified))
    if exit_code==0 and diagnostic is not None and diagnostic_success(diagnostic):host_phase('RECORD_NATIVE',save_native_receipt_observation)

def control(values):
    require(len(values)==4 and all(v in {'NOT_ATTEMPTED','SUCCEEDED','FAILED'} for v in values))
    result=dict(schema=1,mode='JOURNEY_LINUX_BUILD_CONTROL',activation=values[0],build=values[1],licenseReturn=values[2],privateCleanup=values[3],buildDiagnostic=None,sourceRecovery=recovery.empty_recovery(),hostDiagnostic=host_state())
    if (RECOVERY/'build-diagnostic.json').exists():result['buildDiagnostic']=read_json(RECOVERY/'build-diagnostic.json')
    if (RECOVERY/'source-recovery.json').exists():result['sourceRecovery']=read_json(RECOVERY/'source-recovery.json')
    validate_control(result)
    pin=result['hostDiagnostic']['nativeReceiptPin']
    if pin is not None:
        raw,_=sealed_native_receipt(STATE/'linux-build-receipt.json');require(pin==dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)));os.chmod(safe(STATE/'linux-build-receipt.json'),0o644)
    atomic(CONTROL,result);os.chmod(safe(CONTROL),0o644)
    if values[1]=='SUCCEEDED':
        sealed_native_receipt(STATE/'linux-build-receipt.json');os.chmod(safe(STATE/'linux-build-receipt.json'),0o644)
        require({p.name for p in safe(STAGED,False).iterdir()}=={'manifest.json','player.tar.gz'})
        for p in STAGED.iterdir():os.chmod(safe(p),0o644)
        os.chmod(STAGED,0o755)

def validate_control(c):
    require(isinstance(c,dict) and set(c)=={'schema','mode','activation','build','licenseReturn','privateCleanup','buildDiagnostic','sourceRecovery','hostDiagnostic'} and c['schema']==1 and c['mode']=='JOURNEY_LINUX_BUILD_CONTROL')
    require(all(c[k] in {'NOT_ATTEMPTED','SUCCEEDED','FAILED'} for k in ('activation','build','licenseReturn','privateCleanup')));recovery.validate_recovery(c['sourceRecovery'])
    validate_host(c['hostDiagnostic'])
    if c['buildDiagnostic'] is not None:
        d=c['buildDiagnostic'];require(set(d)=={'batchExitCode','batchTimedOut','native','logClassification'} and type(d['batchExitCode']) is int and 0<=d['batchExitCode']<=255 and type(d['batchTimedOut']) is bool and d['batchTimedOut']==(d['batchExitCode']==124))
        if d['native'] is not None:native_diagnostic(d['native'])
        recovery.startup.validate(d['logClassification'],set(recovery.startup.source_map(PROJECT).values()))
    if c['hostDiagnostic']['nativeReceiptPin'] is not None:require(c['buildDiagnostic'] is not None and c['buildDiagnostic']['batchExitCode']==0 and diagnostic_success(c['buildDiagnostic']['native']))
    return c

def export_attempt(context):
    context['phase']='HOST_EXPORT_CONTROL';require(not PUBLIC.exists());c=validate_control(read_json(CONTROL));context['control']=c;ok=c['hostDiagnostic']['failurePhase']=='NONE' and os.environ.get('NATIVE_OUTCOME')=='success' and os.environ.get('UNION_OUTCOME')=='success' and all(c[k]=='SUCCEEDED' for k in ('activation','build','licenseReturn','privateCleanup')) and c['sourceRecovery']['status']=='SUCCEEDED' and c['buildDiagnostic'] is not None and c['buildDiagnostic']['batchExitCode']==0 and diagnostic_success(c['buildDiagnostic']['native'])
    stage_out=pathlib.Path(tempfile.mkdtemp(prefix='journey-linux-public-',dir=TASK));committed=False
    try:
        if ok:
            context['phase']='HOST_EXPORT_UNION';verify_union();r=request()
            context['phase']='HOST_EXPORT_STAGED_METADATA';m=read_json(STAGED/'manifest.json')
            require(set(m)=={'schema','label','sourceCommit','producerRunUrl','nativeReceiptSha256','inputSha256','generatedReceiptSha256','sourceStateSha256','bundleSha256','bundleBytes','files','nativeReceipt','playerExecuted','approved'})
            require(m['schema']==1 and m['label']=='REUSABLE_CANDIDATE_LINUX_PLAYER_UNREVIEWED' and m['sourceCommit']==os.environ['GITHUB_SHA'] and m['producerRunUrl']==producer_url() and m['playerExecuted'] is False and m['approved'] is False)
            native_receipt(m['nativeReceipt']);restoration_matches(m['nativeReceipt'],r);require(m['nativeReceipt']['requestSha256']==sha(STATE/'linux-build-input.json'));require(m['nativeReceipt']['generatedReceiptSha256']==r['generatedReceiptSha256']==m['generatedReceiptSha256'])
            context['phase']='HOST_EXPORT_NATIVE_RECEIPT'
            native_bytes,sealed=sealed_native_receipt(STATE/'linux-build-receipt.json');require(hashlib.sha256(native_bytes).hexdigest()==m['nativeReceiptSha256'] and sealed==m['nativeReceipt'])
            pin=c['hostDiagnostic']['nativeReceiptPin']
            if pin is not None:require(pin==dict(sha256=hashlib.sha256(native_bytes).hexdigest(),bytes=len(native_bytes)))
            require(m['nativeReceipt']['boundaryNativeXmlSha256']==r['boundaryNativeXmlSha256'] and r['boundaryNativeCases']==17)
            require(m['inputSha256']==sha(STATE/'linux-build-input.json') and m['sourceStateSha256']==sha(TASK/'SOURCE-STATE.json'))
            context['phase']='HOST_EXPORT_TAR'
            require(m['bundleSha256']==sha(STAGED/'player.tar.gz') and m['bundleBytes']==(STAGED/'player.tar.gz').stat().st_size)
            # Metadata originates in the validated closed runtime inventory; tar verification reads bytes without extracting.
            validate_records(m['files'])
            require(next(x['sha256'] for x in m['files'] if x['path']=='DesertRV.x86_64')==m['nativeReceipt']['executableSha256'])
            context['phase']='HOST_EXPORT_TAR';verify_tar(STAGED/'player.tar.gz',m['files'])
            context['phase']='HOST_EXPORT_COPY';atomic(stage_out/'manifest.json',m);shutil.copyfile(safe(STAGED/'player.tar.gz'),stage_out/'player.tar.gz');atomic(stage_out/'control.json',c)
            (stage_out/'native-build-receipt.json').write_bytes(native_bytes)
            require(sha(stage_out/'native-build-receipt.json')==m['nativeReceiptSha256'] and (stage_out/'native-build-receipt.json').stat().st_size==len(native_bytes))
            require(sha(stage_out/'player.tar.gz')==m['bundleSha256'] and (stage_out/'player.tar.gz').stat().st_size==m['bundleBytes'])
        else:
            context['phase']='HOST_EXPORT_FAILURE_RECEIPT'
            pin=c['hostDiagnostic']['nativeReceiptPin']
            if pin is not None:
                raw,_=sealed_native_receipt(STATE/'linux-build-receipt.json');require(pin==dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
                (stage_out/'native-build-receipt.json').write_bytes(raw);require(sha(stage_out/'native-build-receipt.json')==pin['sha256'])
            atomic(stage_out/'status.json',dict(schema=1,status='CANDIDATE_LINUX_BUILD_FAILED_NOT_ACCEPTED',playerExported=False,control=c))
        context['phase']='HOST_EXPORT_COMMIT';os.replace(stage_out,PUBLIC);committed=True;context['createdPublic']=True
    finally:
        if not committed:shutil.rmtree(stage_out)
    context['phase']='HOST_EXPORT_OUTPUT'
    with open(os.environ['GITHUB_OUTPUT'],'a') as output:output.write('export_ready=true\n')

def export():
    context=dict(phase='HOST_EXPORT_CONTROL',control=None,createdPublic=False)
    try:export_attempt(context);return 0
    except Exception as error:
        failure=dict(phase=context['phase'],**host_error(error))
        print('JOURNEY_LINUX_HOST_EXPORT_FAILURE '+json.dumps(failure,sort_keys=True))
        # Only remove this invocation's own published directory. An existing foreign/stale path is never overwritten.
        temp=None
        try:
            if context['createdPublic']:shutil.rmtree(PUBLIC)
            if PUBLIC.exists() or PUBLIC.is_symlink():return 1
            temp=pathlib.Path(tempfile.mkdtemp(prefix='journey-linux-safe-failure-',dir=TASK));c=context['control'];copied=False
            if c is not None and c['hostDiagnostic']['nativeReceiptPin'] is not None:
                pin=c['hostDiagnostic']['nativeReceiptPin'];target=temp/'native-build-receipt.json'
                try:
                    raw,_=sealed_native_receipt(STATE/'linux-build-receipt.json');require(pin==dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
                    target.write_bytes(raw);require(sha(target)==pin['sha256']);copied=True
                except Exception:
                    if target.exists():target.unlink()
            atomic(temp/'status.json',dict(schema=1,status='CANDIDATE_LINUX_EXPORT_FAILED_NOT_ACCEPTED',playerExported=False,nativeReceiptExported=copied,hostExportFailure=failure,control=c))
            os.replace(temp,PUBLIC);temp=None
            with open(os.environ['GITHUB_OUTPUT'],'a') as output:output.write('export_ready=true\n')
        except Exception:
            print('JOURNEY_LINUX_SAFE_FAILURE_EXPORT_UNAVAILABLE')
        finally:
            if temp is not None:shutil.rmtree(temp,ignore_errors=True)
        return 1

def main():
    try:
        command=sys.argv[1]
        if command=='preflight':host_phase('PREFLIGHT',lambda:preflight(pathlib.Path(sys.argv[2])))
        elif command=='verify-union':
            from pipeline import guard
            host_phase('POSTBUILD_UNION',lambda:(guard(),verify_union()))
        elif command=='before':before()
        elif command=='snapshot':snapshot(pathlib.Path(sys.argv[2]))
        elif command=='restore':return restore(pathlib.Path(sys.argv[2]))
        elif command=='record':host_phase('RECORD',lambda:record(pathlib.Path(sys.argv[2]),int(sys.argv[3])))
        elif command=='stage':stage()
        elif command=='control':control(sys.argv[2:])
        elif command=='export':return export()
        else:raise ValueError()
    except Exception:print('JOURNEY_LINUX_FIXED_VALIDATION_FAILED');return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
