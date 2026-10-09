#!/usr/bin/env python3
"""Same-job candidate Linux build bundle. Does not execute the player or grant approval."""
import gzip,hashlib,json,os,pathlib,re,shutil,subprocess,sys,tarfile,tempfile
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
FAILURE_CODES={'PERFORMANCE_PREFERENCE','PERFORMANCE_LINK','PERFORMANCE_PACKAGE','PERFORMANCE_BASELINE','PERFORMANCE_INVENTORY','PERFORMANCE_PAYLOAD','PERFORMANCE_META','PERFORMANCE_MOVE','PERFORMANCE_PACKED_REPORT','PERFORMANCE_PACKED_CONTENT','PERFORMANCE_PRIVATE','PIN_LINK', 'RESTORATION_XML', 'INVENTORY_NONREGULAR', 'ROOT_BYTES', 'BUILD_OR_SCENE_FAILED', 'INVENTORY_LINK', 'ROOT_IMPORT_HASH', 'PACKAGE_IDENTITY', 'PIN_BYTES', 'DEPENDENCY_PATH', 'INVENTORY_DIRECTORY', 'SAVED_RUNTIME_IDENTITY', 'BOOTSTRAP_OWNER', 'ROOT_DEPENDENCY', 'REQUEST_RECEIPT_HASH', 'BOOTSTRAP_BINDING', 'REGION_BINDING', 'REGION_OWNER', 'SCENE_COMPONENT', 'DEPENDENCY_KIND', 'INVENTORY_SET', 'ROOT_DEPENDENCY_BYTES', 'SCENE_SEQUENCE', 'PIN_MISSING', 'REGION_IDENTITY', 'BUILTIN_DEPENDENCY', 'IMPORT_FINGERPRINT', 'TARGET_OUTPUT', 'REQUEST_IDENTITY', 'PIN_PATH', 'UNCLASSIFIED_EXCEPTION', 'DIRTY_SCENE', 'ENTRY_PROFILE', 'LEASE_PROFILE', 'RESTORATION_PROOF', 'REQUEST_HASH', 'DEPENDENCY_BYTES', 'BUILD_PROFILE'}
EXCEPTIONS={'NONE','BUILD_FAILED','UNAUTHORIZED_ACCESS','IO','OTHER'}
CALLBACKS={'CANDIDATE_PERFORMANCE','NONE','PRODUCTION_PREPROCESS','PRODUCTION_SCENE','CANDIDATE_SCENE'}
ROLES={'NONE','CONTENT','BOOTSTRAP','FIRST_STATION','SCRAPYARD','NIGHT_BEACON'}
BUILD_ERROR_KINDS={'CANDIDATE_GATE','PRODUCTION_GATE','CS_COMPILATION','SHADER_ERROR','UNCLASSIFIED_BUILD_ERROR'}
RUNTIME_ROOTS={'DesertRV.x86_64','UnityPlayer.so','DesertRV_Data','MonoBleedingEdge','UnityCrashHandler64'}
DEBUG_ROOTS={'DesertRV_BackUpThisFolder_ButDontShipItWithYourGame','DesertRV_BurstDebugInformation_DoNotShip'}

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
    require(isinstance(value,dict) and set(value)=={'status','packageVerified','baselineAbsent','preferenceRestored','synchronousImportCompleted','exactInventoryRestored','packedReportAvailable','packedContainers','packedObjects','packedSourceObjects','packedJsonHits','packedScenePaths','callbackScenePaths','jsonGuids','generated'})
    require(value['status'] in {'NOT_ARMED','ARMED','IMPORTED','QUARANTINED','PACKED_VERIFIED'})
    for k in ('packageVerified','baselineAbsent','preferenceRestored','synchronousImportCompleted','exactInventoryRestored','packedReportAvailable'):require(type(value[k]) is bool)
    for k in ('packedContainers','packedObjects','packedSourceObjects','packedJsonHits'):require(type(value[k]) is int and 0<=value[k]<=2147483647)
    require(value['packedJsonHits']<=value['packedObjects'] and value['packedSourceObjects']<=value['packedObjects'])
    scenes=value['packedScenePaths'];require(isinstance(scenes,list) and scenes==sorted(set(scenes)) and set(scenes)<=set(SCENES))
    callbacks=value['callbackScenePaths'];require(isinstance(callbacks,list) and callbacks==sorted(set(callbacks)) and set(callbacks)<=set(SCENES))
    guids=value['jsonGuids'];require(isinstance(guids,list) and len(guids) in (0,2) and len(set(guids))==len(guids) and all(isinstance(g,str) and re.fullmatch('[a-f0-9]{32}',g) for g in guids))
    inventory_observation(value['generated'])
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

def validate_records(records):
    require(isinstance(records,list) and 0<len(records)<=20000);previous='';total=0;roots=set()
    for row in records:
        require(isinstance(row,dict) and set(row)=={'path','size','sha256','mode'})
        name=row['path'];require(isinstance(name,str) and len(name)<=512 and name>previous and '\\' not in name and '\x00' not in name);previous=name;path=pathlib.PurePosixPath(name)
        require((len(path.parts)==1) == (path.parts[0] in {'DesertRV.x86_64','UnityPlayer.so','UnityCrashHandler64'}))
        require(not path.is_absolute() and '..' not in path.parts and path.parts[0] in RUNTIME_ROOTS and not any(part.startswith('.') for part in path.parts));roots.add(path.parts[0])
        require(path.suffix.lower() not in {'.log','.ulf','.alf','.lic','.key','.pdb','.mdb','.debug'} and path.name.lower() not in {'credentials','credentials.json','activation.log','return.log'})
        require(type(row['size']) is int and 0<=row['size']<=2*1024**3 and isinstance(row['sha256'],str) and re.fullmatch('[a-f0-9]{64}',row['sha256']))
        require(type(row['mode']) is int and row['mode']==(0o755 if path.parts[0] in {'DesertRV.x86_64','UnityCrashHandler64'} else 0o644));total+=row['size']
    require(total<=8*1024**3 and {'DesertRV.x86_64','UnityPlayer.so','DesertRV_Data','MonoBleedingEdge'}<=roots)
    require(any(x['path']=='DesertRV_Data/Managed/Assembly-CSharp.dll' for x in records))
    return records

def inventory(folder):
    folder=safe(folder,False);require(folder.is_dir());names={p.name for p in folder.iterdir()}
    require({'DesertRV.x86_64','UnityPlayer.so','DesertRV_Data','MonoBleedingEdge'}<=names<=RUNTIME_ROOTS|DEBUG_ROOTS)
    for name in names & RUNTIME_ROOTS:require((folder/name).is_file() if name in {'DesertRV.x86_64','UnityPlayer.so','UnityCrashHandler64'} else (folder/name).is_dir())
    records=[];total=0
    for p in sorted(folder.rglob('*')):
        safe(p,False);require(p.is_file() or p.is_dir());name=p.relative_to(folder).as_posix();top=p.relative_to(folder).parts[0]
        if top in DEBUG_ROOTS:continue
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
    if recovery.recover_source(logs)!=0:return 1
    verify_union();return 0

def restoration_matches(native,request):
    for key in ('assetProducerSourceCommit','assetProducerRunUrl','restorationNativeXmlSha256'):require((native.get(key) or '')==(request.get(key) or ''))
    a=native.get('restorationProof');b=request.get('restorationProof')
    if isinstance(a,dict) and a.get('path'):require(a==b)
    else:require(b is None or b=={'path':'','sha256':''})

def stage():
    verify_union();r=request();_,native=sealed_native_receipt(STATE/'linux-build-receipt.json');diagnostic=native_diagnostic(read_json(STATE/'linux-build-diagnostic.json'))
    require(diagnostic_success(diagnostic))
    require(native['requestSha256']==sha(STATE/'linux-build-input.json'));restoration_matches(native,r)
    require(native['boundaryNativeXmlSha256']==r['boundaryNativeXmlSha256'] and r['boundaryNativeCases']==17)
    require(native['generatedReceiptSha256']==r['generatedReceiptSha256']==sha(TASK/'journey-preparation-export/generated/receipt.json'))
    require(native['executableSha256']==sha(BUILD/'DesertRV.x86_64'));records=inventory(BUILD)
    require(not STAGED.exists());temp=pathlib.Path(tempfile.mkdtemp(prefix='journey-linux-stage-',dir=TASK));success=False
    try:
        tar_bundle(BUILD,records,temp/'player.tar.gz');require(inventory(BUILD)==records);verify_union();verify_tar(temp/'player.tar.gz',records)
        manifest=dict(schema=1,label='REUSABLE_CANDIDATE_LINUX_PLAYER_UNREVIEWED',sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=producer_url(),nativeReceiptSha256=sha(STATE/'linux-build-receipt.json'),inputSha256=sha(STATE/'linux-build-input.json'),generatedReceiptSha256=r['generatedReceiptSha256'],sourceStateSha256=sha(TASK/'SOURCE-STATE.json'),bundleSha256=sha(temp/'player.tar.gz'),bundleBytes=(temp/'player.tar.gz').stat().st_size,files=records,nativeReceipt=native,playerExecuted=False,approved=False)
        atomic(temp/'manifest.json',manifest);os.replace(temp,STAGED);success=True
    finally:
        if not success:shutil.rmtree(temp)

def record(logs,exit_code):
    require(type(exit_code) is int and 0<=exit_code<=255);RECOVERY.mkdir(exist_ok=True)
    diagnostic=None
    if (STATE/'linux-build-diagnostic.json').exists():diagnostic=native_diagnostic(read_json(STATE/'linux-build-diagnostic.json'))
    classified=recovery.startup.classify(logs,PROJECT,editor=exit_code)
    atomic(RECOVERY/'build-diagnostic.json',dict(batchExitCode=exit_code,batchTimedOut=exit_code==124,native=diagnostic,logClassification=classified))

def control(values):
    require(len(values)==4 and all(v in {'NOT_ATTEMPTED','SUCCEEDED','FAILED'} for v in values))
    result=dict(schema=1,mode='JOURNEY_LINUX_BUILD_CONTROL',activation=values[0],build=values[1],licenseReturn=values[2],privateCleanup=values[3],buildDiagnostic=None,sourceRecovery=recovery.empty_recovery())
    if (RECOVERY/'build-diagnostic.json').exists():result['buildDiagnostic']=read_json(RECOVERY/'build-diagnostic.json')
    if (RECOVERY/'source-recovery.json').exists():result['sourceRecovery']=read_json(RECOVERY/'source-recovery.json')
    validate_control(result);atomic(CONTROL,result);os.chmod(safe(CONTROL),0o644)
    if values[1]=='SUCCEEDED':
        sealed_native_receipt(STATE/'linux-build-receipt.json');os.chmod(safe(STATE/'linux-build-receipt.json'),0o644)
        require({p.name for p in safe(STAGED,False).iterdir()}=={'manifest.json','player.tar.gz'})
        for p in STAGED.iterdir():os.chmod(safe(p),0o644)
        os.chmod(STAGED,0o755)

def validate_control(c):
    require(isinstance(c,dict) and set(c)=={'schema','mode','activation','build','licenseReturn','privateCleanup','buildDiagnostic','sourceRecovery'} and c['schema']==1 and c['mode']=='JOURNEY_LINUX_BUILD_CONTROL')
    require(all(c[k] in {'NOT_ATTEMPTED','SUCCEEDED','FAILED'} for k in ('activation','build','licenseReturn','privateCleanup')));recovery.validate_recovery(c['sourceRecovery'])
    if c['buildDiagnostic'] is not None:
        d=c['buildDiagnostic'];require(set(d)=={'batchExitCode','batchTimedOut','native','logClassification'} and type(d['batchExitCode']) is int and 0<=d['batchExitCode']<=255 and type(d['batchTimedOut']) is bool and d['batchTimedOut']==(d['batchExitCode']==124))
        if d['native'] is not None:native_diagnostic(d['native'])
        recovery.startup.validate(d['logClassification'],set(recovery.startup.source_map(PROJECT).values()))
    return c

def export():
    require(not PUBLIC.exists());c=validate_control(read_json(CONTROL));ok=os.environ.get('NATIVE_OUTCOME')=='success' and os.environ.get('UNION_OUTCOME')=='success' and all(c[k]=='SUCCEEDED' for k in ('activation','build','licenseReturn','privateCleanup')) and c['sourceRecovery']['status']=='SUCCEEDED' and c['buildDiagnostic'] is not None and c['buildDiagnostic']['batchExitCode']==0 and diagnostic_success(c['buildDiagnostic']['native'])
    stage_out=pathlib.Path(tempfile.mkdtemp(prefix='journey-linux-public-',dir=TASK));committed=False
    try:
        if ok:
            verify_union();r=request();m=read_json(STAGED/'manifest.json')
            require(set(m)=={'schema','label','sourceCommit','producerRunUrl','nativeReceiptSha256','inputSha256','generatedReceiptSha256','sourceStateSha256','bundleSha256','bundleBytes','files','nativeReceipt','playerExecuted','approved'})
            require(m['schema']==1 and m['label']=='REUSABLE_CANDIDATE_LINUX_PLAYER_UNREVIEWED' and m['sourceCommit']==os.environ['GITHUB_SHA'] and m['producerRunUrl']==producer_url() and m['playerExecuted'] is False and m['approved'] is False)
            native_receipt(m['nativeReceipt']);restoration_matches(m['nativeReceipt'],r);require(m['nativeReceipt']['requestSha256']==sha(STATE/'linux-build-input.json'));require(m['nativeReceipt']['generatedReceiptSha256']==r['generatedReceiptSha256']==m['generatedReceiptSha256'])
            native_bytes,sealed=sealed_native_receipt(STATE/'linux-build-receipt.json');require(hashlib.sha256(native_bytes).hexdigest()==m['nativeReceiptSha256'] and sealed==m['nativeReceipt'])
            require(m['nativeReceipt']['boundaryNativeXmlSha256']==r['boundaryNativeXmlSha256'] and r['boundaryNativeCases']==17)
            require(m['inputSha256']==sha(STATE/'linux-build-input.json') and m['sourceStateSha256']==sha(TASK/'SOURCE-STATE.json'))
            require(m['bundleSha256']==sha(STAGED/'player.tar.gz') and m['bundleBytes']==(STAGED/'player.tar.gz').stat().st_size)
            # Metadata originates in the validated closed runtime inventory; tar verification reads bytes without extracting.
            validate_records(m['files'])
            require(next(x['sha256'] for x in m['files'] if x['path']=='DesertRV.x86_64')==m['nativeReceipt']['executableSha256'])
            verify_tar(STAGED/'player.tar.gz',m['files']);atomic(stage_out/'manifest.json',m);shutil.copyfile(safe(STAGED/'player.tar.gz'),stage_out/'player.tar.gz');atomic(stage_out/'control.json',c)
            (stage_out/'native-build-receipt.json').write_bytes(native_bytes)
            require(sha(stage_out/'native-build-receipt.json')==m['nativeReceiptSha256'] and (stage_out/'native-build-receipt.json').stat().st_size==len(native_bytes))
            require(sha(stage_out/'player.tar.gz')==m['bundleSha256'] and (stage_out/'player.tar.gz').stat().st_size==m['bundleBytes'])
        else:atomic(stage_out/'status.json',dict(schema=1,status='CANDIDATE_LINUX_BUILD_FAILED_NOT_ACCEPTED',playerExported=False,control=c))
        os.replace(stage_out,PUBLIC);committed=True
    finally:
        if not committed:shutil.rmtree(stage_out)
    with open(os.environ['GITHUB_OUTPUT'],'a') as output:output.write('export_ready=true\n')

def main():
    try:
        command=sys.argv[1]
        if command=='before':before()
        elif command=='snapshot':snapshot(pathlib.Path(sys.argv[2]))
        elif command=='restore':return restore(pathlib.Path(sys.argv[2]))
        elif command=='record':record(pathlib.Path(sys.argv[2]),int(sys.argv[3]))
        elif command=='stage':stage()
        elif command=='control':control(sys.argv[2:])
        elif command=='export':export()
        else:raise ValueError()
    except Exception:print('JOURNEY_LINUX_FIXED_VALIDATION_FAILED');return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
