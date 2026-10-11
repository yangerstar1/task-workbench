#!/usr/bin/env python3
"""One-use fresh Android Journey candidate. Host checks never claim device acceptance."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
TASK = ROOT / 'tasks/desert-rv'
PROJECT = TASK / 'unity'
sys.path[:0] = [str(TASK/'scripts'), str(TASK/'art/journey-preparation')]
import verify_evidence as source
import verify_tracer_shader as shader
safe=source.safe
sha=source.sha
read_json=source.read_json

def load_build_modules():
    # Identity admission must remain stdlib-only before the hosted dependency install.
    global prepared,linux,recovery,atomic,safe,sha,read_json,mobile_hud,restoration
    import linux_build_input as prepared
    import journey_linux_export as linux
    import player_window_smoke as recovery
    import journey_mobile_hud_native as mobile_hud
    import restore_preparation as restoration
    from capture_game_window import atomic
    from prepare_safe_diagnostic_export import safe,sha,read_json

BASE = '767b37db844cbe27b0940ee3bc9677b1fc8291f7'
BRANCH = 'journey-android-c15'
REF = 'refs/heads/' + BRANCH
REPO = 'yangerstar1/task-workbench'
WORKFLOW = '.github/workflows/desert-rv-journey-android.yml'
REQUEST = '.github/dispatch/desert-rv-journey-android-c15-r2-20261011.json'
REQUEST_ID = 'desert-rv-journey-android-c15-r2-20261011-once'
SOURCE = 'tasks/desert-rv/SOURCE-STATE.json'
SELECTION = 'tasks/desert-rv/art/journey-preparation/three-strict-candidates.json'
IMAGE = 'unityci/editor@sha256:1e98c949ff728e6ff627b5c55ef65975125a6dc47cf27060601b79a141cc8692'
RESTORE_REQUEST_ID = 'desert-rv-journey-android-c15-restored-r2-20261011-once'
RESTORED = os.environ.get('JOURNEY_ANDROID_RESTORATION') == RESTORE_REQUEST_ID
RESTORE_POLICY = 'tasks/desert-rv/art/journey-preparation/android-restoration-transition.json'
if RESTORED:
    BASE = '7e6cdc28339bac076cf86da41b451949bc4d2e3d'
    REQUEST = '.github/dispatch/desert-rv-journey-android-c15-restored-r2-20261011.json'
    REQUEST_ID = RESTORE_REQUEST_ID
STATE = PROJECT/'JourneyEvidence/JourneyPreparation'
INPUT = STATE/'android-build-input.json'
BUILD = TASK/'journey-android-private-build'
STAGED = TASK/'journey-android-staged-export'
PUBLIC = TASK/'journey-android-public-export'
CONTROL = TASK/'journey-android-control.json'
OBSERVATION = TASK/'journey-android-build-observation.json'
GATES = TASK/'journey-android-native-gates.json'
RECOVERY = TASK/'journey-android-recovery-private'
APK = 'DesertRV-Journey.apk'
SURFACE_SHADER = 'Universal Render Pipeline/Lit'
LABEL = 'CANDIDATE_ANDROID_DEVELOPMENT_BUILT_UNREVIEWED'
FAILURE_CODES=frozenset((
    'ANDROID_APK_PIN',
    'ANDROID_CERTIFICATE_DIGEST',
    'ANDROID_COMMAND',
    'ANDROID_CONTROL',
    'ANDROID_CONTROL_FAILED',
    'ANDROID_COPY',
    'ANDROID_DEBUGGABLE',
    'ANDROID_DEBUG_SIGNER',
    'ANDROID_DIRTY_OUTPUT',
    'ANDROID_EVENT',
    'ANDROID_EXIT_CODE',
    'ANDROID_EXPORT_EXISTS',
    'ANDROID_EXPORT_PIN',
    'ANDROID_FRESH_ONLY',
    'ANDROID_RESTORATION_ROUTE',
    'ANDROID_RESTORATION_PROOF',
    'ANDROID_FRESH_REQUEST',
    'ANDROID_GATES_CHANGED',
    'ANDROID_GATES_EXIST',
    'ANDROID_HEAD',
    'ANDROID_INPUT_CHANGED',
    'ANDROID_MANIFEST_IDENTITY',
    'ANDROID_MANIFEST_SCHEMA',
    'ANDROID_NATIVE_BUILD_FAILED',
    'ANDROID_NATIVE_GATE',
    'ANDROID_NATIVE_PINS',
    'ANDROID_OBSERVATION',
    'ANDROID_OBSERVATION_PHASE',
    'ANDROID_OWNER_PUSH',
    'ANDROID_PACKAGE_IDENTITY',
    'ANDROID_PACKAGE_SCHEMA',
    'ANDROID_PACKAGE_TOOL',
    'ANDROID_PARENT',
    'ANDROID_PIN_CHANGED',
    'ANDROID_PUBLIC_HOSTED',
    'ANDROID_RECEIPT_FLAGS',
    'ANDROID_RECEIPT_HASH',
    'ANDROID_RECEIPT_IDENTITY',
    'ANDROID_RECEIPT_SCHEMA',
    'ANDROID_REPOSITORY',
    'ANDROID_REQUEST',
    'ANDROID_REQUEST_EXISTS',
    'ANDROID_SHADER_AMBIGUOUS',
    'ANDROID_SHADER_MISSING',
    'ANDROID_SHADER_PATH',
    'ANDROID_SHADER_REPORT_CHANGED',
    'ANDROID_SHADER_SIZE',
    'ANDROID_SOURCE_RECOVERY',
    'ANDROID_STAGE_CHANGED',
    'ANDROID_STAGE_EXISTS',
    'ANDROID_STAGE_INVENTORY',
    'ANDROID_TRACKED_INPUT',
    'ANDROID_UNREVIEWED',
    'ANDROID_XML_BOUND',
    'ANDROID_XML_COUNT',
))
FAILURE_COMMANDS={'prepare':'INPUT_PREPARATION','before':'PREFLIGHT','verify':'PREFLIGHT_OR_VERIFY','snapshot':'SOURCE_SNAPSHOT','record':'NATIVE_OBSERVATION','restore':'SOURCE_RESTORE','stage':'STAGE','export':'EXPORT','control':'CLEANUP_CONTROL'}
FAILURE_STAGES=frozenset(FAILURE_COMMANDS.values())|{'NATIVE_BUILD','NATIVE_RECEIPT','APK_CONTENTS','APK_IDENTITY','SHADER_REGISTRY','STAGED'}
FAILURE_CLASSES=frozenset(('ValueError','OSError','RuntimeError','KeyError','TypeError','Rejected','OtherError'))
FIELDS = ['scriptingBackend.Android', 'Android.targetArchitectures', 'Android.useCustomKeystore',
          'Android.buildApkPerCpuArchitecture', 'Android.splitApplicationBinary', 'Android.targetSdkVersion',
          'Android.bundleVersionCode', 'buildAppBundle', 'exportAsGoogleAndroidProject',
          'applicationIdentifier.Android', 'bundleVersion', 'productName']

def require(condition, code):
    if not condition:
        raise ValueError(code)

def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'DUPLICATE_JSON_KEY'); value[key] = item
    return value

def sealed(path, limit=4*1024**2):
    path=safe(path);require(0 < path.stat().st_size <= limit, 'JSON_SIZE')
    raw = path.read_bytes(); require(0 < len(raw) <= limit, 'JSON_SIZE')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: require(False, 'JSON_CONSTANT'))

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, stderr=subprocess.DEVNULL)

def validate(env, event, head, parents, request_raw, tracked_raw, request_in_parent,
             changed_paths, source_sha, selection_sha, policy_sha=None):
    """Exact Android admission, also usable with HEAD bytes for read-only diagnostics."""
    require(env.get('GITHUB_ACTIONS') == 'true' and env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and
            env.get('RUNNER_OS') == 'Linux' and env.get('GITHUB_REPOSITORY') == REPO and
            env.get('GITHUB_REPOSITORY_VISIBILITY') == 'public', 'ANDROID_PUBLIC_HOSTED')
    require(env.get('GITHUB_ACTOR') == env.get('GITHUB_TRIGGERING_ACTOR') == 'yangerstar1' and
            env.get('GITHUB_EVENT_NAME') == 'push' and env.get('GITHUB_REF') == REF and
            env.get('GITHUB_WORKFLOW_REF') == REPO+'/'+WORKFLOW+'@'+REF and
            env.get('GITHUB_RUN_ATTEMPT') == '1' and re.fullmatch('[1-9][0-9]*', env.get('GITHUB_RUN_ID','')), 'ANDROID_OWNER_PUSH')
    require(re.fullmatch('[a-f0-9]{40}',head) and env.get('GITHUB_SHA') == head and head != BASE, 'ANDROID_HEAD')
    require(parents == [BASE], 'ANDROID_PARENT')
    require(type(event) is dict and event.get('before') == BASE and event.get('after') == head and event.get('ref') == REF and
            all(event.get(k) is False for k in ('created','deleted','forced')) and
            event.get('sender',{}).get('login') == 'yangerstar1' and event.get('head_commit',{}).get('id') == head, 'ANDROID_EVENT')
    repo = event.get('repository',{})
    require(type(repo) is dict and repo.get('full_name') == REPO and repo.get('private') is False and repo.get('fork') is False and
            repo.get('default_branch') == 'main' and repo.get('owner',{}).get('login') == 'yangerstar1', 'ANDROID_REPOSITORY')
    require(type(request_raw) is bytes and 0 < len(request_raw) <= 4096, 'ANDROID_REQUEST')
    request = json.loads(request_raw, object_pairs_hook=unique, parse_constant=lambda _: require(False, 'JSON_CONSTANT'))
    expected = dict(schema=1, requestId=REQUEST_ID, baseCommit=BASE,
                    sourceStateSha256=source_sha, selection=SELECTION, selectionSha256=selection_sha, image=IMAGE)
    if RESTORED:
        require(env.get('JOURNEY_ANDROID_RESTORATION')==RESTORE_REQUEST_ID and
                isinstance(policy_sha,str) and re.fullmatch('[a-f0-9]{64}',policy_sha),'ANDROID_RESTORATION_ROUTE')
        expected['restorationPolicySha256']=policy_sha
    require(type(request) is dict and type(request.get('schema')) is int and request == expected, 'ANDROID_REQUEST')
    require(request_raw == tracked_raw, 'ANDROID_TRACKED_INPUT')
    require(request_in_parent is False and REQUEST in changed_paths, 'ANDROID_FRESH_REQUEST')
    return request

def dispatch(env=None):
    env = os.environ if env is None else env
    head = git('rev-parse','HEAD').decode().strip()
    parents = [line.split(' ',1)[1] for line in git('cat-file','-p','HEAD').decode().split('\n\n',1)[0].splitlines() if line.startswith('parent ')]
    git('cat-file','-e',BASE+'^{commit}')
    request_path = safe(ROOT/REQUEST)
    require(0 < request_path.stat().st_size <= 4096, 'ANDROID_REQUEST')
    request_raw = request_path.read_bytes()
    request = validate(env, sealed(Path(env['GITHUB_EVENT_PATH'])), head, parents, request_raw,
        git('show','HEAD:'+REQUEST), subprocess.run(['git','cat-file','-e',BASE+':'+REQUEST],cwd=ROOT,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 0,
        git('diff-tree','--no-commit-id','--name-only','-r','HEAD').decode().splitlines(), sha(ROOT/SOURCE), sha(ROOT/SELECTION), sha(ROOT/RESTORE_POLICY) if RESTORED else None)
    for name in (SOURCE, SELECTION, RESTORE_POLICY) if RESTORED else (SOURCE, SELECTION):
        require(safe(ROOT/name).read_bytes() == git('show','HEAD:'+name), 'ANDROID_TRACKED_INPUT')
    return request

def output(**values):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as stream:
            for key,value in values.items(): stream.write(key+'='+str(value)+'\n')

def exact_xml(folder, names):
    names = set(names); paths = list(folder.rglob('*.xml')); require(len(paths)==1, 'ANDROID_XML_COUNT')
    raw = safe(paths[0]).read_bytes(); require(len(raw)<=10*1024**2 and b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper(), 'ANDROID_XML_BOUND')
    root = ET.fromstring(raw); cases=list(root.iter('test-case')); actual=[c.get('fullname') for c in cases]
    require(root.tag=='test-run' and root.get('result')=='Passed' and root.get('total')==root.get('passed')==str(len(names)) and
            all(root.get(k)=='0' for k in ('failed','skipped','inconclusive')) and len(actual)==len(set(actual))==len(names) and
            set(actual)==names and all(c.get('result')=='Passed' for c in cases),'ANDROID_NATIVE_GATE')
    return dict(path=str(paths[0].relative_to(ROOT)),sha256=sha(paths[0]),cases=sorted(names),count=len(names))

def gate_values():
    if RESTORED:
        _, _, proof = restoration.verify()
        return dict(schema=1,scope='RESTORED_CONSUMER_WITH_SEPARATE_IMMUTABLE_PRODUCER_EVIDENCE',
                    sourceCommit=os.environ['GITHUB_SHA'],runId=os.environ['GITHUB_RUN_ID'],runAttempt=os.environ['GITHUB_RUN_ATTEMPT'],
                    assetProducer=dict(**restoration.PRODUCER,apiEvidence=restoration.pin(restoration.PRODUCER_API),
                        generatedReceipt=restoration.pin(restoration.PUBLIC/'generated/receipt.json'),
                        strictReceipts=[restoration.pin(restoration.PUBLIC/k/'receipt.json') for k in ('armored','pouncer','weapon')],
                        mobileHud=restoration.producer_hud_evidence(),nativeHistory=restoration.producer_native_history()),
                    currentConsumer=dict(restorationNativeCases=1,restorationNativeXml=proof['nativeXml'],
                        restorationReport=restoration.pin(restoration.REPORT),boundaryNativeCases=17,
                        boundaryNativeXml=proof['boundaryNativeXml'],worldHud=mobile_hud.verify_world()),
                    deviceExecuted=False,approved=False)
    from journey_pouncer_ground_support_probe import GENERIC_TESTS
    return dict(schema=1,sourceCommit=os.environ['GITHUB_SHA'],runId=os.environ['GITHUB_RUN_ID'],runAttempt=os.environ['GITHUB_RUN_ATTEMPT'],
                playmode=exact_xml(TASK/'artifacts/journey-android-playmode',source.expected_cases('playmode')),
                groundSupport=exact_xml(TASK/'artifacts/journey-android-ground',GENERIC_TESTS),mobileHud=mobile_hud.verify(),deviceExecuted=False,approved=False)

def gates():
    from journey_keyboard_look_native import verify_unchanged
    verify_unchanged(); require(not GATES.exists(), 'ANDROID_GATES_EXIST'); atomic(GATES, gate_values())

def request_expected():
    result = copy.deepcopy(prepared.verify())
    result.update(label='CANDIDATE_ANDROID_DEVELOPMENT_ONLY',target='Android',define='DESERTRV_CANDIDATE_ANDROID')
    native_gates=gate_values()
    require(sealed(GATES)==native_gates, 'ANDROID_GATES_CHANGED')
    for path in (STATE/'linux-build-input.json', GATES):
        result['files'].append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path)))
    if RESTORED:
        for row in [restoration.pin(restoration.PRODUCER_API), *restoration.producer_hud_pins(), *mobile_hud.verify_world()]:
            result['files'].append(dict(path=row['path'],sha256=row['sha256']))
        return result
    for name in ('playmode','groundSupport'):
        row=native_gates[name]; result['files'].append(dict(path=row['path'],sha256=row['sha256']))
    hud=native_gates['mobileHud']
    for row in [hud['report'],hud['nativeXml'],*hud['captures']]:
        result['files'].append(dict(path=row['path'],sha256=row['sha256']))
    for row in mobile_hud.verify_world():result['files'].append(dict(path=row['path'],sha256=row['sha256']))
    return result

def prepare():
    if RESTORED:
        prepared.prepare_restored()
        require(not GATES.exists(),'ANDROID_GATES_EXIST');atomic(GATES,gate_values())
    else:prepared.prepare()
    require(not INPUT.exists(), 'ANDROID_REQUEST_EXISTS')
    value=request_expected(); atomic(INPUT,value); INPUT.with_suffix('.sha256').write_text(sha(INPUT)+'\n'); verify()

def verify():
    require(sealed(INPUT)==request_expected() and safe(INPUT.with_suffix('.sha256')).read_text().strip()==sha(INPUT), 'ANDROID_INPUT_CHANGED')
    for pin in sealed(INPUT)['files']: require(sha(ROOT/pin['path'])==pin['sha256'], 'ANDROID_PIN_CHANGED')
    return sealed(INPUT)

def before():
    from verify_inputs import verify_gameci
    verify_gameci(ROOT/'_ci/gameci-journey-android',read_json(TASK/'scripts/rendered/official-gameci-pins.json'))
    verify()
    for path in (BUILD,STAGED,PUBLIC,CONTROL,OBSERVATION,RECOVERY): require(not path.exists() and not path.is_symlink(), 'ANDROID_DIRTY_OUTPUT')
    atomic(TASK/'player-source-before.json',recovery.tracked())

def native_receipt(value):
    require(type(value) is dict and set(value)==linux.RECEIPT_KEYS and type(value['schema']) is int and value['schema']==1, 'ANDROID_RECEIPT_SCHEMA')
    require(value['label']==LABEL and value['sourceCommit']==os.environ['GITHUB_SHA'] and value['producerRunUrl']==linux.producer_url() and
            value['unityVersion']=='6000.3.19f1' and value['target']=='Android' and value['backend']=='IL2CPP' and
            value['define']=='DESERTRV_CANDIDATE_ANDROID' and value['executable']==APK and value['scenes']==linux.SCENES and
            type(value['boundaryNativeCases']) is int and value['boundaryNativeCases']==17 and
            value['temporarySettingsFiles']==['ProjectSettings/ProjectSettings.asset'] and value['temporarySettingsApiFields']==FIELDS, 'ANDROID_RECEIPT_IDENTITY')
    for key in ('candidateOnly','development','detailedBuildReport','performanceTestResourcesExcluded','settingsRestored','sourceBytesUnchanged'): require(value[key] is True,'ANDROID_RECEIPT_FLAGS')
    for key in ('approved','visualReviewed','gameplayReviewed','audioAuditioned'): require(value[key] is False,'ANDROID_UNREVIEWED')
    for key in ('generatedReceiptSha256','requestSha256','executableSha256','boundaryNativeXmlSha256'): require(re.fullmatch('[a-f0-9]{64}', value[key] or ''),'ANDROID_RECEIPT_HASH')
    if RESTORED:
        expected=verify()
        require(all(value[k]==expected[k] for k in ('restorationProof','assetProducerSourceCommit','assetProducerRunUrl','restorationNativeXmlSha256',
                                                  'generatedReceiptSha256','boundaryNativeXmlSha256')),'ANDROID_RESTORATION_PROOF')
    else:
        require(value['restorationProof'] in (None,{'path':'','sha256':''}) and all(value[k] in ('',None) for k in ('assetProducerSourceCommit','assetProducerRunUrl','restorationNativeXmlSha256')), 'ANDROID_FRESH_ONLY')
    return value

def apk_shader(apk):
    prefix='assets/bin/Data/'
    with zipfile.ZipFile(safe(apk)) as archive:
        infos={i.filename:i for i in archive.infolist()}
        def load(name):
            require(shader.safe_relative(name) and name.startswith(prefix),'ANDROID_SHADER_PATH')
            splits=sorted(n for n in infos if re.fullmatch(re.escape(name)+r'\.split[0-9]+',n))
            if name in infos: require(not splits,'ANDROID_SHADER_AMBIGUOUS'); names=[name]
            else:
                names=[name+'.split'+str(i) for i in range(len(splits))]
                require(0<len(names)<=32 and set(names)==set(splits),'ANDROID_SHADER_MISSING')
            require(48<=sum(infos[n].file_size for n in names)<=shader.MAX_ASSET_BYTES,'ANDROID_SHADER_SIZE')
            return b''.join(archive.read(n) for n in names)
        data=load(prefix+'globalgamemanagers'); meta=shader.serialized(data,target=13)
        entries, registry=shader.registry(data,meta,target=13,prefix=prefix)
        resolved=shader.resolve_shader(load,meta,entries,shader.TARGET,target=13,prefix=prefix)
        surface=shader.resolve_shader(load,meta,entries,SURFACE_SHADER,target=13,prefix=prefix)
        return dict(status='PASSED',targetShader=shader.TARGET,registry=registry,resolvedShader=resolved,
                    surfaceShader=SURFACE_SHADER,resolvedSurfaceShader=surface,playerExecuted=False,renderingVerified=False)

def apk_identity(apk):
    sdk=Path('/opt/unity/Editor/Data/PlaybackEngines/AndroidPlayer/SDK/build-tools/36.0.0')
    def run(*args):
        result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90,check=False)
        require(result.returncode==0 and len(result.stdout)<=2*1024**2 and len(result.stderr)<=65536,'ANDROID_PACKAGE_TOOL')
        return result.stdout.decode('utf-8')
    badging=run(str(sdk/'aapt'),'dump','badging',str(apk))
    require(re.search(r"^package: name='com\.desertrv\.journey\.dev' versionCode='1' versionName='0\.1\.0-dev\."+os.environ['GITHUB_SHA'][:12]+"'",badging,re.M) and
            "targetSdkVersion:'35'" in badging and re.search(r"^native-code: 'arm64-v8a'\s*$",badging,re.M),'ANDROID_PACKAGE_IDENTITY')
    xml=run(str(sdk/'aapt'),'dump','xmltree',str(apk),'AndroidManifest.xml')
    require(re.search(r'android:debuggable\([^\n]+\)=\(type 0x12\)0xffffffff',xml),'ANDROID_DEBUGGABLE')
    certificates=run(str(sdk/'apksigner'),'verify','--verbose','--print-certs',str(apk))
    require(re.findall(r'^Signer #[0-9]+ certificate DN: (.+)$',certificates,re.M)==['CN=Android Debug, O=Android, C=US'],'ANDROID_DEBUG_SIGNER')
    fingerprints=re.findall(r'^Signer #1 certificate SHA-256 digest: ([a-f0-9]{64})$',certificates,re.M)
    require(len(fingerprints)==1,'ANDROID_CERTIFICATE_DIGEST')
    return dict(packageName='com.desertrv.journey.dev',versionName='0.1.0-dev.'+os.environ['GITHUB_SHA'][:12],versionCode=1,
                architecture='ARM64',backend='IL2CPP',targetSdk=35,development=True,debuggable=True,signing='debug-only',certificateSha256=fingerprints[0])

def observe(exit_code=None, phase='NATIVE_BUILD', logs=None):
    require(exit_code is None or type(exit_code) is int and 0<=exit_code<=255,'ANDROID_EXIT_CODE')
    require(phase in ('NATIVE_BUILD','NATIVE_RECEIPT','APK_CONTENTS','APK_IDENTITY','SHADER_REGISTRY','STAGED'),'ANDROID_OBSERVATION_PHASE')
    value=sealed(OBSERVATION,131072) if OBSERVATION.exists() else dict(schema=1,sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=linux.producer_url(),batchExitCode=exit_code,native=None,startup=recovery.startup.empty_report(),phase=phase)
    if exit_code is not None:
        value['batchExitCode']=exit_code
        path=STATE/'android-build-diagnostic.json'
        if path.exists():value['native']=linux.native_diagnostic(sealed(path,131072),platform='ANDROID')
        if logs is not None:value['startup']=recovery.startup.classify(logs,PROJECT,editor=exit_code)
    value['phase']=phase;validate_observation(value);atomic(OBSERVATION,value)

def validate_observation(value):
    require(type(value) is dict and set(value)=={'schema','sourceCommit','producerRunUrl','batchExitCode','native','startup','phase'} and
            type(value['schema']) is int and value['schema']==1 and value['sourceCommit']==os.environ['GITHUB_SHA'] and
            value['producerRunUrl']==linux.producer_url() and type(value['batchExitCode']) is int and 0<=value['batchExitCode']<=255 and
            value['phase'] in ('NATIVE_BUILD','NATIVE_RECEIPT','APK_CONTENTS','APK_IDENTITY','SHADER_REGISTRY','STAGED'),'ANDROID_OBSERVATION')
    if value['native'] is not None:linux.native_diagnostic(value['native'],platform='ANDROID')
    recovery.startup.validate(value['startup'],set(recovery.startup.source_map(PROJECT).values()))
    return value

def stage():
    observe(phase='NATIVE_RECEIPT')
    r=verify(); native=native_receipt(sealed(STATE/'android-build-receipt.json',32768))
    diagnostic=linux.native_diagnostic(sealed(STATE/'android-build-diagnostic.json',131072),platform='ANDROID')
    require(linux.diagnostic_success(diagnostic,target='ANDROID'),'ANDROID_NATIVE_BUILD_FAILED')
    require(native['requestSha256']==sha(INPUT) and native['generatedReceiptSha256']==r['generatedReceiptSha256'] and
            native['boundaryNativeXmlSha256']==r['boundaryNativeXmlSha256'],'ANDROID_NATIVE_PINS')
    observe(phase='APK_CONTENTS')
    apk=safe(BUILD/APK); info=source.inspect_apk_bytes(apk); require(native['executableSha256']==info['apkSha256'],'ANDROID_APK_PIN')
    observe(phase='APK_IDENTITY');identity=apk_identity(apk)
    observe(phase='SHADER_REGISTRY');shader_report=apk_shader(apk)
    shader_report['nativeDependencies']=shader.dependency_proof(TASK/'journey-preparation-export/generated',PROJECT,linux,native,restored_android=RESTORED)
    require(not STAGED.exists(),'ANDROID_STAGE_EXISTS'); temporary=Path(tempfile.mkdtemp(prefix='journey-android-stage-',dir=TASK))
    try:
        shutil.copyfile(apk,temporary/APK); require(sha(temporary/APK)==info['apkSha256'],'ANDROID_COPY')
        manifest=dict(schema=1,label=LABEL,sourceCommit=os.environ['GITHUB_SHA'],baseCommit=BASE,producerRunUrl=linux.producer_url(),runAttempt=os.environ['GITHUB_RUN_ATTEMPT'],
                      sourceStateSha256=sha(TASK/'SOURCE-STATE.json'),image=IMAGE,inputSha256=sha(INPUT),nativeReceiptSha256=sha(STATE/'android-build-receipt.json'),
                      generatedReceiptSha256=r['generatedReceiptSha256'],nativeGates=sealed(GATES),apk=APK,**info,package=identity,
                      shaderRegistry=shader_report,nativeDiagnostic=diagnostic,deviceExecuted=False,approved=False)
        atomic(temporary/'manifest.json',manifest); shutil.copyfile(STATE/'android-build-receipt.json',temporary/'native-build-receipt.json')
        verify(); require(sha(apk)==sha(temporary/APK)==info['apkSha256'],'ANDROID_STAGE_CHANGED'); os.replace(temporary,STAGED);observe(phase='STAGED')
    finally:
        if temporary.exists():shutil.rmtree(temporary)

def control_value(values, first_failure=None):
    return dict(schema=1,sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=linux.producer_url(),
                activation=values[0],build=values[1],licenseReturn=values[2],privateCleanup=values[3],firstFailure=first_failure)

def validate_control(value):
    expected=control_value(['NOT_ATTEMPTED']*4)
    require(type(value) is dict and set(value)==set(expected) and type(value['schema']) is int and value['schema']==1 and
            all(value[k]==expected[k] for k in ('sourceCommit','producerRunUrl')) and
            all(value[k] in ('NOT_ATTEMPTED','SUCCEEDED','FAILED') for k in ('activation','build','licenseReturn','privateCleanup')),'ANDROID_CONTROL')
    failure=value['firstFailure']
    require(failure is None or type(failure) is dict and set(failure)=={'command','stage','code','exceptionClass'} and
            failure['command'] in FAILURE_COMMANDS and failure['stage'] in FAILURE_STAGES and
            (failure['code'] is None or failure['code'] in FAILURE_CODES) and failure['exceptionClass'] in FAILURE_CLASSES,'ANDROID_CONTROL')
    return value

def record_failure(command,error):
    require(command in FAILURE_COMMANDS,'ANDROID_COMMAND')
    value=validate_control(sealed(CONTROL,4096)) if CONTROL.exists() else control_value(['NOT_ATTEMPTED']*4)
    if value['firstFailure'] is not None:return
    stage=FAILURE_COMMANDS[command]
    if command=='stage' and OBSERVATION.exists():
        try:stage=validate_observation(sealed(OBSERVATION,131072))['phase']
        except Exception:pass
    # Match only fixed internal predicates. Exception messages, paths and logs never enter evidence.
    code=error.args[0] if len(error.args)==1 and type(error.args[0]) is str and error.args[0] in FAILURE_CODES else None
    kind=type(error).__name__;kind=kind if kind in FAILURE_CLASSES else 'OSError' if isinstance(error,OSError) else 'OtherError'
    value['firstFailure']=dict(command=command,stage=stage,code=code,exceptionClass=kind)
    validate_control(value);atomic(CONTROL,value);os.chmod(CONTROL,0o644)

def control(values):
    require(len(values)==4 and all(v in ('NOT_ATTEMPTED','SUCCEEDED','FAILED') for v in values),'ANDROID_CONTROL')
    first=validate_control(sealed(CONTROL,4096))['firstFailure'] if CONTROL.exists() else None
    value=control_value(values,first)
    validate_control(value);atomic(CONTROL,value); os.chmod(CONTROL,0o644)
    if OBSERVATION.exists():validate_observation(sealed(OBSERVATION,131072));os.chmod(OBSERVATION,0o644)
    if STAGED.exists():
        require({p.name for p in safe(STAGED,False).iterdir()}=={APK,'manifest.json','native-build-receipt.json'},'ANDROID_STAGE_INVENTORY')
        for path in STAGED.iterdir():os.chmod(safe(path),0o644)
        os.chmod(STAGED,0o755)

def validate_manifest(manifest, native):
    keys={'schema','label','sourceCommit','baseCommit','producerRunUrl','runAttempt','sourceStateSha256','image','inputSha256',
          'nativeReceiptSha256','generatedReceiptSha256','nativeGates','apk','apkSha256','apkBytes','package',
          'shaderRegistry','nativeDiagnostic','deviceExecuted','approved'}
    require(type(manifest) is dict and set(manifest)==keys and type(manifest['schema']) is int and manifest['schema']==1,
            'ANDROID_MANIFEST_SCHEMA')
    require(manifest['label']==LABEL and manifest['baseCommit']==BASE and manifest['sourceCommit']==os.environ['GITHUB_SHA'] and
            manifest['producerRunUrl']==linux.producer_url() and manifest['runAttempt']==os.environ['GITHUB_RUN_ATTEMPT'] and
            manifest['sourceStateSha256']==sha(TASK/'SOURCE-STATE.json') and manifest['image']==IMAGE and manifest['apk']==APK and
            manifest['inputSha256']==sha(INPUT) and manifest['nativeGates']==gate_values() and
            manifest['generatedReceiptSha256']==native['generatedReceiptSha256'] and manifest['deviceExecuted'] is False and
            manifest['approved'] is False,'ANDROID_MANIFEST_IDENTITY')
    require(type(manifest['apkBytes']) is int and manifest['apkBytes']==safe(STAGED/APK).stat().st_size and
            manifest['nativeReceiptSha256']==sha(STAGED/'native-build-receipt.json') and
            manifest['apkSha256']==native['executableSha256']==sha(STAGED/APK),'ANDROID_EXPORT_PIN')
    package=manifest['package']; require(type(package) is dict,'ANDROID_PACKAGE_SCHEMA')
    fingerprint=package.get('certificateSha256'); require(type(fingerprint) is str and re.fullmatch('[a-f0-9]{64}',fingerprint),'ANDROID_CERTIFICATE_DIGEST')
    require(package==dict(packageName='com.desertrv.journey.dev',versionName='0.1.0-dev.'+os.environ['GITHUB_SHA'][:12],versionCode=1,
                         architecture='ARM64',backend='IL2CPP',targetSdk=35,development=True,debuggable=True,
                         signing='debug-only',certificateSha256=fingerprint),'ANDROID_PACKAGE_IDENTITY')
    diagnostic=linux.native_diagnostic(manifest['nativeDiagnostic'],platform='ANDROID')
    require(linux.diagnostic_success(diagnostic,target='ANDROID'),'ANDROID_NATIVE_BUILD_FAILED')
    report=apk_shader(STAGED/APK)
    report['nativeDependencies']=shader.dependency_proof(TASK/'journey-preparation-export/generated',PROJECT,linux,native,restored_android=RESTORED)
    require(manifest['shaderRegistry']==report,'ANDROID_SHADER_REPORT_CHANGED')
    return manifest

def export():
    require(not PUBLIC.exists() and not PUBLIC.is_symlink(),'ANDROID_EXPORT_EXISTS'); PUBLIC.mkdir()
    status=dict(schema=1,status='FAILED_OR_NOT_BUILT',sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=linux.producer_url(),deviceExecuted=False,approved=False)
    if os.environ.get('NATIVE_OUTCOME')=='success' and os.environ.get('UNION_OUTCOME')=='success':
        value=validate_control(sealed(CONTROL,4096))
        require(value==control_value(['SUCCEEDED']*4),'ANDROID_CONTROL_FAILED')
        verify(); manifest=sealed(STAGED/'manifest.json',131072); native=native_receipt(sealed(STAGED/'native-build-receipt.json',32768))
        validate_manifest(manifest,native)
        for name in (APK,'manifest.json','native-build-receipt.json'):shutil.copyfile(safe(STAGED/name),PUBLIC/name)
        shutil.copyfile(CONTROL,PUBLIC/'control.json');status['status']=LABEL
    if CONTROL.exists():atomic(PUBLIC/'control.json',validate_control(sealed(CONTROL,4096)))
    if OBSERVATION.exists():atomic(PUBLIC/'build-observation.json',validate_observation(sealed(OBSERVATION,131072)))
    atomic(PUBLIC/'status.json',status); output(export_ready='true')

def main():
    command=sys.argv[1]; dispatch()
    if command!='dispatch':load_build_modules()
    try:
        if command=='dispatch':
            value=dispatch();output(selection=SELECTION,selection_sha256=value['selectionSha256'],playmode_filter=';'.join(sorted(source.expected_cases('playmode'))))
            if RESTORED:output(transition_sha256=value['restorationPolicySha256'])
        elif command=='gates':gates()
        elif command=='prepare':prepare()
        elif command=='verify':verify()
        elif command=='before':before()
        elif command=='snapshot':recovery.snapshot_recovery(Path(sys.argv[2]))
        elif command=='record':observe(exit_code=int(sys.argv[3]),logs=Path(sys.argv[2]))
        elif command=='restore':
            recovery.EVIDENCE=RECOVERY
            require(recovery.recover_source(Path(sys.argv[2]))==0,'ANDROID_SOURCE_RECOVERY');verify()
        elif command=='stage':stage()
        elif command=='control':control(sys.argv[2:])
        elif command=='export':export()
        elif command=='control-report':validate_control(sealed(CONTROL,4096));output(control_valid='true')
        else:raise ValueError('ANDROID_COMMAND')
    except Exception as error:
        if command in FAILURE_COMMANDS:
            try:record_failure(command,error)
            except Exception:pass
        raise

if __name__=='__main__':
    try:main()
    except Exception:
        print('JOURNEY_ANDROID_CHECK_FAILED');raise SystemExit(1)
