"""Restore one verified public Journey producer; old scopes never authorize a new build."""
import argparse,base64,hashlib,json,os,re,shutil,stat,subprocess,sys,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[4];TASK=ROOT/'tasks/desert-rv';PROJECT=TASK/'unity'
PRIVATE=PROJECT/'JourneyEvidence/JourneyPreparation';PUBLIC=TASK/'journey-preparation-export'
POLICY='tasks/desert-rv/art/journey-preparation/restoration-transition.json'
STATE=PRIVATE/'restoration-state.json';SOURCE_PROOF=PRIVATE/'restoration-source-proof.json'
INPUT=PRIVATE/'restoration-input.json';REPORT=PRIVATE/'restoration-revalidated.json';VERIFIED=PRIVATE/'restoration-native-verified.json'
DERIVATION_FOLDER=PRIVATE/'MaterialDerivation'
DERIVATION_RECORD=DERIVATION_FOLDER/'native-material-derivation.json'
DERIVED_EXPORT=TASK/'journey-derived-preparation-export'
DERIVED_RECEIPT=DERIVED_EXPORT/'receipt.json'
MATERIAL='Assets/DesertRV/Scenes/Journey/Layout-FFC261.mat'
MATERIAL_BEFORE_SHA='ef01bab64fa8fe3f2ebe42a59ed43ddf426e1e8f0c3a5a3401a7dd0fe5202395'
DERIVATION_OPERATION='PINNED_WARM_LIT_BAKED_EMISSION_V1'
DERIVED_LABEL='DERIVED_JOURNEY_NATIVE_REVALIDATED_UNREVIEWED'
sys.path[:0]=[str(TASK/'art/import-candidate'),str(TASK/'scripts/rendered'),str(TASK/'scripts')]
from strict_output import read,sha,require,digest,rel,verify_staged_inventory
from prepare_input import api
from pipeline import guard,directories
import generated_export as generated
import prepared_source
import verify_evidence as original
PRODUCER=dict(repository='yangerstar1/task-workbench',runId=37923953772,runAttempt=1,sourceCommit='7e134d4bbc4a349e5c71b27980dea90d85ff538e',artifactId=11613499060,
 artifactName='journey-preparation-UNREVIEWED-37923953772-1',artifactSha256='81998b540f4b8e51260d5aaffdafec885bbd45215ebb978ed6a60e2dc53bfead',artifactBytes=15840786,
 generatedReceiptSha256='2b5e06b3b5dfcfb5a53afc3ff750b4eb8f460b222dc1abdca5974fc6c4702526',sourceStateSha256='c33b884bd4caaf3fb8d310cebbc0b8de62b52c61cd483cd39a846e245425205b')
# This is the sole additional consumer: one reviewed Android request and producer.
# The historical Linux profile remains byte-for-byte pinned below this selection.
ANDROID_REQUEST_ID = 'desert-rv-journey-android-c15-restored-r6-20261011-once'
ANDROID = os.environ.get('JOURNEY_ANDROID_RESTORATION') == ANDROID_REQUEST_ID
if ANDROID:
 POLICY='tasks/desert-rv/art/journey-preparation/android-restoration-transition.json'
 PRODUCER=dict(repository='yangerstar1/task-workbench',runId=38135035401,runAttempt=1,sourceCommit='9c95f1009a597cf4573e286d0098b7bc47a62321',artifactId=11702226815,
  artifactName='journey-preparation-UNREVIEWED-38135035401-1',artifactSha256='e79829bca28ad709b22822c86d5106ff2710d3356ee20b2fb462ca03c699d91f',artifactBytes=21350895,
  generatedReceiptSha256='742af42d6c4a5f7d366a562f9afbbd9e560c744863c866123565c2cd38ee1f58',sourceStateSha256='2e90d5f2ca98fdcc8c09eb9040d3b314d65d256e0c73d37c63dcf10735fc5e21')
RUN_URL='https://github.com/yangerstar1/task-workbench/actions/runs/'+str(PRODUCER['runId'])
PRODUCER_API=PRIVATE/'producer-api-evidence.json'
PRODUCER_NATIVE=ROOT/'tasks/desert-rv/art/journey-preparation/android-producer-native-history.json'
PRODUCER_NATIVE_SHA='ffce6a5f9873d3619f242a5fb5be4df674be21d6b3c04ee269920670df900d90'
PRODUCER_HUD=TASK/'journey-producer-mobile-hud'
HUD=dict(artifactId=11701099423,artifactName='journey-mobile-hud-native-38135035401-1',artifactBytes=2393601,
 artifactSha256='c4be4ee89b87b0733319fa95319f0c89e5bb3ff8d12384d8d50314c9b96bf3fa',
 reportSha256='0cb1e60c7c03fee43e21731e6ebc6cc455a3908af8dec0b6576abf3fe225ba15')

NATIVE_NAME='DesertRV.Tests.JourneyRestorationTests.RevalidatePinnedRestoredJourney'
# Exact reviewed entry/diagnostic paths only. No runtime, original asset, import contract, package or selector prefix exception.
_ALLOWED=(
 '.github/workflows/desert-rv-journey-rebuild.yml','tasks/desert-rv/scripts/verify_evidence.py',
 'tasks/desert-rv/art/journey-preparation/restore_preparation.py','tasks/desert-rv/art/journey-preparation/test_restore_preparation.py',
 'tasks/desert-rv/art/journey-preparation/linux_build_input.py','tasks/desert-rv/art/journey-preparation/test_linux_build_input.py',
 'tasks/desert-rv/scripts/player/journey_linux_export.py','tasks/desert-rv/scripts/player/test_journey_linux_export.py',
 'tasks/desert-rv/scripts/player/journey_linux_container.sh',
 'tasks/desert-rv/scripts/journey_rebuild_dispatch.py','tasks/desert-rv/scripts/test_journey_rebuild_dispatch.py',
 'tasks/desert-rv/scripts/prepare_runner.sh',
 'tasks/desert-rv/scripts/rendered/prepared_source.py','tasks/desert-rv/scripts/rendered/test_prepared_source.py',
 'tasks/desert-rv/scripts/environment_image_precheck.py','tasks/desert-rv/scripts/test_environment_image_precheck.py',
 'tasks/desert-rv/art/journey-preparation/pipeline.py','tasks/desert-rv/scripts/rendered/Rendered.Dockerfile',
 'tasks/desert-rv/scripts/player/TemplateProbe.Dockerfile','tasks/desert-rv/scripts/player/journey_linux_template_probe.py',
 'tasks/desert-rv/scripts/player/test_journey_linux_template_probe.py',
 'tasks/desert-rv/scripts/player/observe_journey_player.py','tasks/desert-rv/scripts/player/test_observe_journey_player.py',
 'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneyCandidateLinuxBuild.cs',
 'tasks/desert-rv/unity/Assets/DesertRV/Tests/CandidateLinux/CandidateLinuxBoundaryTests.cs',
 'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneyCandidateAssetIntegration.cs',
 'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneyCandidatePreparation.cs',
 'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneyCandidateRestoration.cs',
 'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneyCandidateRestoration.cs.meta',
 'tasks/desert-rv/unity/Assets/DesertRV/Tests/JourneyRestoration.meta',
 'tasks/desert-rv/unity/Assets/DesertRV/Tests/JourneyRestoration/DesertRV.JourneyRestorationTests.asmdef',
 'tasks/desert-rv/unity/Assets/DesertRV/Tests/JourneyRestoration/DesertRV.JourneyRestorationTests.asmdef.meta',
 'tasks/desert-rv/unity/Assets/DesertRV/Tests/JourneyRestoration/JourneyRestorationTests.cs',
 'tasks/desert-rv/unity/Assets/DesertRV/Tests/JourneyRestoration/JourneyRestorationTests.cs.meta')
ALLOWED_SOURCE_CHANGES=frozenset(_ALLOWED)
if ANDROID:
 ALLOWED_SOURCE_CHANGES=frozenset(('tasks/desert-rv/art/journey-preparation/linux_build_input.py','tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneyCandidateLinuxBuild.cs','tasks/desert-rv/unity/Assets/DesertRV/Tests/JourneyRestoration/JourneyRestorationTests.cs','tasks/desert-rv/scripts/player/verify_tracer_shader.py','tasks/desert-rv/scripts/player/test_verify_tracer_shader.py','tasks/desert-rv/art/journey-preparation/android-producer-native-history.json',)+('.github/workflows/desert-rv-journey-android.yml', 'tasks/desert-rv/art/journey-preparation/restore_preparation.py', 'tasks/desert-rv/art/journey-preparation/test_restore_preparation.py', 'tasks/desert-rv/scripts/player/journey_android.py', 'tasks/desert-rv/scripts/player/test_journey_android.py', 'tasks/desert-rv/scripts/player/journey_android_container.sh', 'tasks/desert-rv/scripts/journey_mobile_hud_native.py', 'tasks/desert-rv/scripts/test_journey_mobile_hud_native.py', 'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneyCandidateRestoration.cs', 'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneySceneAuthoring.cs', 'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneyHudCapture.cs'))

def pin(path):return dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
def write_fresh(path,value):
 require(not path.exists(),'RESTORE_OUTPUT_EXISTS');path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')

def material_semantics(raw):
 # Only this owned, bounded Unity Material is decoded. No YAML object constructors.
 import yaml
 require(type(raw) is bytes and 0<len(raw)<=65536,'DERIVE_MATERIAL_SIZE')
 text=raw.decode('utf-8');require('\x00' not in text,'DERIVE_MATERIAL_YAML')
 class UniqueLoader(yaml.SafeLoader):pass
 def mapping(loader,node,deep=False):
  value={}
  for key_node,value_node in node.value:
   key=loader.construct_object(key_node,deep=deep)
   require(isinstance(key,str) and key not in value,'DERIVE_MATERIAL_DUPLICATE_KEY')
   value[key]=loader.construct_object(value_node,deep=deep)
  return value
 UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)
 # Unity's per-document !u! tags are type IDs, never executable YAML constructors.
 headers=re.findall(r'^--- !u!(\d+) &(\d+)\s*$',text,re.M)
 require(headers==[('21','2100000'),('114','2086780894777222751')],'DERIVE_MATERIAL_DOCUMENTS')
 plain=re.sub(r'^%TAG !u! tag:unity3d.com,2011:\s*\n','',text,flags=re.M)
 plain=re.sub(r'^--- !u!\d+ &\d+\s*$', '---',plain,flags=re.M)
 value=list(yaml.load_all(plain,Loader=UniqueLoader))
 require(len(value)==2 and set(value[0])=={'Material'} and set(value[1])=={'MonoBehaviour'},'DERIVE_MATERIAL_DOCUMENTS')
 return value

def validate_material_delta(before_raw,after_raw):
 import copy
 require(hashlib.sha256(before_raw).hexdigest()==MATERIAL_BEFORE_SHA and len(before_raw)==3845,'DERIVE_PARENT_MATERIAL')
 require(before_raw!=after_raw,'DERIVE_MATERIAL_UNCHANGED')
 before=material_semantics(before_raw);after=material_semantics(after_raw);expected=copy.deepcopy(before)
 original=before[0]['Material'];current=after[0]['Material'];wanted=expected[0]['Material']
 require(original['m_LightmapFlags']==4 and current['m_LightmapFlags']==2,'DERIVE_MATERIAL_GI')
 require(original['m_Shader']=={'fileID':4800000,'guid':'933532a4fcc9baf4fa0491de14d08ed7','type':3} and original['m_ValidKeywords']==['_EMISSION'],'DERIVE_MATERIAL_LIT')
 colors=original['m_SavedProperties']['m_Colors']
 require(isinstance(colors,list) and all(isinstance(row,dict) and len(row)==1 for row in colors) and len({next(iter(row)) for row in colors})==len(colors),'DERIVE_MATERIAL_COLORS')
 table={k:v for row in colors for k,v in row.items()}
 require(set(table['_BaseColor'])=={'r','g','b','a'} and table['_BaseColor']=={'r':1,'g':.76,'b':.38,'a':1} and table['_EmissionColor']=={'r':2.5,'g':1.9,'b':.95,'a':2.5},'DERIVE_MATERIAL_COLOR_PIN')
 wanted['m_LightmapFlags']=2
 normalized=copy.deepcopy(expected)
 for row in normalized[0]['Material']['m_SavedProperties']['m_Colors']:
  if '_Color' in row:row['_Color']=copy.deepcopy(table['_BaseColor'])
 require(after==expected or after==normalized,'DERIVE_MATERIAL_UNAUTHORIZED_PROPERTY')
 alias=after!=expected
 return dict(changedProperties=['m_LightmapFlags']+(['m_SavedProperties.m_Colors._Color'] if alias else []),beforeGi=4,afterGi=2,
             baseColor=table['_BaseColor'],emissionColor=table['_EmissionColor'],beforeLegacyColor=table['_Color'],afterLegacyColor=table['_BaseColor'] if alias else table['_Color'])

def material_derivation():
 from strict_output import safe
 value=read(DERIVATION_RECORD)
 require(ANDROID and set(value)=={'schema','label','sourceCommit','producerRunUrl','assetProducerSourceCommit','assetProducerRunUrl','parentGeneratedReceipt','requestSha256','originalBeforeAuthoringVerified','material'} and
         value['schema']==1 and value['label']=='EXACT_WARM_MATERIAL_DERIVATION_NATIVE' and value['sourceCommit']==os.environ['GITHUB_SHA'] and value['producerRunUrl']==current_run() and
         value['assetProducerSourceCommit']==PRODUCER['sourceCommit'] and value['assetProducerRunUrl']==RUN_URL and value['parentGeneratedReceipt']==pin(PUBLIC/'generated/receipt.json') and
         value['requestSha256']==sha(INPUT) and value['originalBeforeAuthoringVerified'] is True,'DERIVE_NATIVE_IDENTITY')
 material=value['material'];require(type(material) is dict,'DERIVE_NATIVE_MATERIAL')
 keys={'schema','status','path','guid','localId','beforeSha256','beforeBytes','afterSha256','afterBytes','metaSha256','metaBytes','source','loaded','authored','reloaded','loadedDirtyBeforeAuthoring','unloadVerified','reloadedClean','bytesStableAfterReload','semanticChanges'}
 require(set(material)==keys and type(material['schema']) is int and material['schema']==1 and material['status']=='DERIVED_WARM_LAMP_MATERIAL_UNREVIEWED' and
         material['path']==MATERIAL and material['guid']=='7807e70b78cd80b04b21bf136de97aaf' and type(material['localId']) is int and material['localId']==2100000,'DERIVE_NATIVE_MATERIAL')
 before_path=safe(DERIVATION_FOLDER/'before.mat');after_path=safe(DERIVATION_FOLDER/'after.mat')
 require(before_path.stat().st_size<=65536 and after_path.stat().st_size<=65536,'DERIVE_MATERIAL_SIZE')
 before=before_path.read_bytes();after=after_path.read_bytes()
 semantic=validate_material_delta(before,after)
 require(before==safe(PUBLIC/'generated'/MATERIAL).read_bytes() and after==safe(PROJECT/MATERIAL).read_bytes(),'DERIVE_MATERIAL_COPY_CHANGED')
 for label,data in [('before',before),('after',after)]:
  require(material[label+'Sha256']==hashlib.sha256(data).hexdigest() and type(material[label+'Bytes']) is int and material[label+'Bytes']==len(data),'DERIVE_MATERIAL_PIN')
 meta=safe(PROJECT/(MATERIAL+'.meta'));require(meta.read_bytes()==safe(PUBLIC/'generated'/(MATERIAL+'.meta')).read_bytes() and material['metaSha256']==sha(meta) and material['metaBytes']==meta.stat().st_size,'DERIVE_META_CHANGED')
 require(material['loadedDirtyBeforeAuthoring'] is False and all(material[k] is True for k in ('unloadVerified','reloadedClean','bytesStableAfterReload')),'DERIVE_RELOAD_NOT_VERIFIED')
 expected_colors={'baseColor':semantic['baseColor'],'emissionColor':semantic['emissionColor']}
 for name in ('source','loaded','authored','reloaded'):
  state=material[name]
  require(type(state) is dict and set(state)=={'giFlags','emissionKeyword','baseColor','emissionColor','legacyColor'} and type(state['giFlags']) is int and type(state['emissionKeyword']) is bool and (name=='loaded' or state['emissionKeyword'] is True),'DERIVE_NATIVE_STATE')
  require(all(set(state[k])=={'r','g','b','a'} and all(type(x) in (float,int) and __import__('math').isfinite(x) for x in state[k].values()) for k in ('baseColor','emissionColor','legacyColor')),'DERIVE_NATIVE_COLOR')
  require(all(all(abs(state[k][c]-v[c])<=0.000001 for c in v) for k,v in expected_colors.items()),'DERIVE_NATIVE_STATE')
  expected_gi=4 if name in ('source','loaded') else 2
  require(state['giFlags']==expected_gi and state['giFlags'] in (2,4),'DERIVE_NATIVE_STATE')
  color=semantic['beforeLegacyColor'] if name in ('source','loaded') else semantic['afterLegacyColor']
  require(all(abs(state['legacyColor'][c]-color[c])<=0.000001 for c in color),'DERIVE_NATIVE_STATE')
 require(material['authored']==material['reloaded'],'DERIVE_RELOAD_CHANGED')
 require(material['semanticChanges']==['GLOBAL_ILLUMINATION_FLAGS_4_TO_2']+(['LEGACY_COLOR_SYNCHRONIZED_TO_BASE_COLOR'] if len(semantic['changedProperties'])==2 else []),'DERIVE_SEMANTIC_CHANGES')
 return value

def derived_dependencies(bundle,material):
 rows=__import__('copy').deepcopy(bundle['native']['dependencies']);matches=[row for row in rows if row['path']==MATERIAL]
 require(len(rows)==1040 and len(matches)==1 and matches[0]['sha256']==MATERIAL_BEFORE_SHA and matches[0]['bytes']==3845 and matches[0]['kind']=='asset','DERIVE_PARENT_DEPENDENCY')
 matches[0].update(sha256=material['afterSha256'],bytes=material['afterBytes'])
 return rows

def derived_receipt_value(xml,boundary,files):
 material=material_derivation()['material']
 return dict(schema=1,status='DERIVED_JOURNEY_PREPARED_UNREVIEWED',sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),
  assetProducerSourceCommit=PRODUCER['sourceCommit'],assetProducerRunUrl=RUN_URL,parentGeneratedReceipt=pin(PUBLIC/'generated/receipt.json'),
  nativeDerivation=pin(DERIVATION_RECORD),nativeRestoration=pin(REPORT),restorationNativeXml=xml,boundaryNativeXml=boundary,
  sourceState=pin(TASK/'SOURCE-STATE.json'),sourceTransition=pin(SOURCE_PROOF),originalBeforeAuthoringVerified=True,exactMaterialDelta=True,editorExited=True,
  changes=[{k:material[k] for k in ('path','guid','localId','beforeSha256','beforeBytes','afterSha256','afterBytes','metaSha256','metaBytes')}],
  inheritedEvidenceScope='PARENT_155_ONLY_NOT_CURRENT_DERIVED_ASSET_VALIDATION',approved=False,scopeReusable=False,files=files)

def verify_derived_export():
 import linux_build_input as linux
 value=read(DERIVED_RECEIPT);verify_staged_inventory(DERIVED_EXPORT,value['files'],sha(DERIVED_RECEIPT))
 expected_files=[]
 for source,name in ((DERIVATION_FOLDER/'before.mat','parent-material.mat'),(PROJECT/MATERIAL,MATERIAL),(DERIVATION_RECORD,'native-material-derivation.json'),(REPORT,'native-restoration.json')):
  target=DERIVED_EXPORT/name;require(target.read_bytes()==source.read_bytes(),'DERIVE_EXPORT_COPY_CHANGED');expected_files.append(generated.record(target,name))
 require(value==derived_receipt_value(native_evidence(),linux.boundary_evidence()['nativeXml'],expected_files),'DERIVE_RECEIPT_CHANGED')
 return value

def export_derived(xml,boundary):
 require(not DERIVED_EXPORT.exists(),'DERIVE_EXPORT_EXISTS');DERIVED_EXPORT.mkdir()
 files=[]
 for source,name in ((DERIVATION_FOLDER/'before.mat','parent-material.mat'),(PROJECT/MATERIAL,MATERIAL),(DERIVATION_RECORD,'native-material-derivation.json'),(REPORT,'native-restoration.json')):
  target=DERIVED_EXPORT/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target);require(target.read_bytes()==source.read_bytes(),'DERIVE_EXPORT_COPY_CHANGED');files.append(generated.record(target,name))
 write_fresh(DERIVED_RECEIPT,derived_receipt_value(xml,boundary,files));verify_derived_export()

def export_material_diagnostic():
 from strict_output import safe
 if not ANDROID or not (DERIVATION_FOLDER/'before.mat').exists():return []
 request=read(INPUT)
 require(request['sourceCommit']==os.environ['GITHUB_SHA'] and request['producerRunUrl']==current_run() and request.get('materialDerivation')==DERIVATION_OPERATION,'DERIVE_DIAGNOSTIC_IDENTITY')
 before_path=safe(DERIVATION_FOLDER/'before.mat');require(before_path.stat().st_size==3845,'DERIVE_PARENT_MATERIAL');before=before_path.read_bytes()
 require(len(before)==3845 and hashlib.sha256(before).hexdigest()==MATERIAL_BEFORE_SHA,'DERIVE_PARENT_MATERIAL')
 rows=[];pending=[]
 def copy(data,name):
  pending.append((data,name))
 copy(before,'material-before.mat')
 value=dict(schema=1,status='MATERIAL_CONTENT_DIAGNOSTIC_ONLY',sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),path=MATERIAL,
            beforeSha256=MATERIAL_BEFORE_SHA,beforeBytes=len(before),afterSha256='',afterBytes=0,afterState='MISSING',semanticChanges=[],buildReady=False,approved=False)
 if (DERIVATION_FOLDER/'after.mat').exists():
  path=safe(DERIVATION_FOLDER/'after.mat');require(path.stat().st_size<=65536,'DERIVE_MATERIAL_SIZE');after=path.read_bytes()
  value.update(afterSha256=hashlib.sha256(after).hexdigest(),afterBytes=len(after),afterState='UNAUTHORIZED_SEMANTIC_DELTA')
  if after==before:value['afterState']='UNCHANGED_PARENT';copy(after,'material-after.mat')
  else:
   try:semantic=validate_material_delta(before,after)
   except Exception:pass
   else:
    value.update(afterState='EXACT_AUTHORIZED_SEMANTIC_DELTA',semanticChanges=semantic['changedProperties']);copy(after,'material-after.mat')
 for data,name in pending:
  path=EXPORT/name
  with path.open('xb') as stream:stream.write(data)
  require(path.read_bytes()==data,'DERIVE_DIAGNOSTIC_COPY_CHANGED');rows.append(generated.record(path,name))
 write_fresh(EXPORT/'material-diagnostic.json',value);rows.append(generated.record(EXPORT/'material-diagnostic.json','material-diagnostic.json'))
 return rows
def source_transition(policy,before,after,policy_sha):
 require(set(policy)=={'schema','status','producer','changes'} and type(policy['schema']) is int and policy['schema']==1 and policy['status']==('REVIEWED_EXACT_MATERIAL_DERIVATION_SOURCE' if ANDROID else 'REVIEWED_DIAGNOSTIC_RESTORATION_SOURCE_ONLY') and policy['producer']==PRODUCER,'RESTORE_POLICY_IDENTITY')
 require(digest(policy_sha) and isinstance(policy['changes'],list),'RESTORE_POLICY_HASH')
 require(before['restoredFiles']==after['restoredFiles'] and before['coverageRoots']==after['coverageRoots'],'RESTORE_SOURCE_DOMAIN_CHANGED')
 expected_coverage=before['coverageFiles'] if ANDROID else before['coverageFiles']+['.github/workflows/desert-rv-journey-rebuild.yml']
 require(after['coverageFiles']==expected_coverage,'RESTORE_SOURCE_COVERAGE_CHANGED')
 require({k:v for k,v in before.items() if k not in ('files','coverageFiles')}=={k:v for k,v in after.items() if k not in ('files','coverageFiles')},'RESTORE_SOURCE_METADATA_CHANGED')
 old={x['path']:x for x in before['files']};new={x['path']:x for x in after['files']}
 require(len(old)==len(before['files']) and len(new)==len(after['files']) and POLICY not in old and new.get(POLICY,{}).get('sha256')==policy_sha,'RESTORE_POLICY_SOURCE_PIN')
 actual=[]
 for name in sorted(set(old)|set(new)):
  if name==POLICY:continue # This one nonexecutable policy is rooted in dispatch SHA plus the unchanged current source guard.
  a,b=old.get(name),new.get(name)
  if a==b:continue
  require(name in ALLOWED_SOURCE_CHANGES and b is not None,'RESTORE_UNREVIEWED_SOURCE_CHANGE')
  actual.append(dict(path=name,beforeSha256=a['sha256'] if a else '',beforeBytes=a['size'] if a else 0,afterSha256=b['sha256'],afterBytes=b['size']))
 require(actual and policy['changes']==actual,'RESTORE_EXACT_SOURCE_DIFF')
 for row in actual:
  require(set(row)=={'path','beforeSha256','beforeBytes','afterSha256','afterBytes'} and digest(row['afterSha256']) and
          (digest(row['beforeSha256']) or row['beforeSha256']=='' and row['beforeBytes']==0) and type(row['afterBytes']) is int and row['afterBytes']>0,'RESTORE_SOURCE_DIFF_SCHEMA')
 return actual

def validate_producer_api(run,artifact,jobs):
 require(run.get('id')==PRODUCER['runId'] and run.get('run_attempt')==1 and run.get('head_sha')==PRODUCER['sourceCommit'] and
         run.get('status')=='completed' and run.get('head_branch')==('journey-android-c15' if ANDROID else 'main') and run.get('event')==('push' if ANDROID else 'workflow_dispatch') and
         run.get('path')==('.github/workflows/desert-rv-journey-android.yml' if ANDROID else '.github/workflows/desert-rv-journey-prepare.yml'),'RESTORE_PRODUCER_RUN')
 require(artifact.get('id')==PRODUCER['artifactId'] and artifact.get('name')==PRODUCER['artifactName'] and artifact.get('expired') is False and
         artifact.get('size_in_bytes')==PRODUCER['artifactBytes'] and artifact.get('digest')=='sha256:'+PRODUCER['artifactSha256'] and
         artifact.get('workflow_run',{}).get('id')==PRODUCER['runId'] and artifact['workflow_run'].get('head_sha')==PRODUCER['sourceCommit'],'RESTORE_PRODUCER_ARTIFACT')
 candidates=[j for j in jobs.get('jobs',[]) if j.get('name')=='prepare' and j.get('run_id')==PRODUCER['runId'] and j.get('status')=='completed']
 require(len(candidates)==1,'RESTORE_PRODUCER_JOB')
 steps={s['number']:s for s in candidates[0]['steps']}
 required={7:'Native strict armored import and actual capture',8:'Reuse exact strict quality gate and preserve armored reports',10:'Native strict pouncer import and actual capture',11:'Reuse exact strict quality gate and preserve pouncer reports',13:'Native strict weapon import and actual capture',14:'Reuse exact strict quality gate and preserve weapon reports',15:'Require exact three-candidate union and freeze real selections',16:'Native exact candidate Linux boundary tests',17:'Require exact seventeen passing candidate boundary cases',18:'Native original FX, four scenes, integration and diagnostic scope',19:'Verify actual preparation test, saved outputs and final scope pins'}
 if ANDROID:required={3: 'Verify one-use Android candidate source identity', 4: 'Verify current source before fixed Android-image readiness', 5: 'Verify fixed Android-image readiness with at most one bounded fallback pull', 6: 'Validate bounded image observation and actual step outcome', 7: 'Upload only validated fixed Android image availability observation', 8: 'Prepare official validators and source before snapshot', 9: 'Validate ordered selection and snapshot protected source', 10: 'Verify non-root host union across real root-owned bytecode caches', 11: 'Prepare existing licensed runner after input validation', 12: 'Native exact ten tracer material cases before strict imports', 13: 'Diagnose original source and import union even after failed native tests', 14: 'Upload bounded original source and fixture residue diagnostics', 15: 'Require exact ten passes and unchanged initial source and import union', 16: 'Upload bounded validated tracer native status', 17: 'Create exact same-commit isolated keyboard look project', 18: 'Native exact four keyboard look PlayMode cases before strict imports', 19: 'Diagnose actual RV entry across five timesteps independently', 20: 'Native exact one region HUD lifecycle PlayMode case in the isolated project', 21: 'Native exact ten production mobile HUD layout and render cases', 22: 'Native exact seven combat feedback EditMode cases in the isolated project', 23: 'Native current thirteen baseline PlayMode cases', 24: 'Native thirteen current Pouncer ground support regressions', 25: 'Preserve isolated project source and complete safe settings diff', 26: 'Upload bounded isolated keyboard look project diagnostics', 27: 'Diagnose source and union independently after keyboard look native tests', 28: 'Upload bounded keyboard look source diagnostics', 29: 'Require exact four keyboard look passes and unchanged initial source', 30: 'Upload bounded keyboard look native result evidence', 31: 'Preserve separate keyboard look reports in preparation evidence', 32: 'Preserve complete safe cabin physics observations even on native failure', 33: 'Upload bounded validated cabin physics diagnosis', 34: 'Require the separate exact HUD pass with same-job source and isolation evidence', 35: 'Upload bounded validated region HUD native status', 36: 'Preserve separate bounded region HUD evidence in the fresh preparation', 37: 'Require fresh exact-seven feedback passes and same-job source and isolation evidence', 38: 'Upload bounded validated combat feedback native status', 39: 'Preserve bounded combat feedback evidence in the fresh preparation', 40: 'Require exact mobile HUD cases and preserve bounded production render fixtures', 41: 'Upload only verified thirteen HUD captures and native fit evidence', 42: 'Pin exact baseline ground support and mobile HUD evidence before authoring or building', 43: 'Remove only the owned isolated keyboard look project', 44: 'Stage verified armored source archive', 45: 'Native strict armored import and actual capture', 46: 'Reuse exact strict quality gate and preserve armored reports', 47: 'Stage verified pouncer source archive', 48: 'Native strict pouncer import and actual capture', 49: 'Reuse exact strict quality gate and preserve pouncer reports', 50: 'Stage verified weapon source archive', 51: 'Native strict weapon import and actual capture', 52: 'Reuse exact strict quality gate and preserve weapon reports', 53: 'Require exact three-candidate union and freeze real selections', 54: 'Native exact candidate Linux boundary tests', 55: 'Require exact seventeen passing candidate boundary cases', 56: 'Native original FX, four scenes, integration and diagnostic scope', 57: 'Verify actual preparation test, saved outputs and final scope pins', 69: 'Prove tracked original source was not edited', 70: 'Upload only existing strict-safe exports and bounded preparation status'}
 require(all(steps.get(n,{}).get('name')==name and steps[n].get('conclusion')=='success' for n,name in required.items()),'RESTORE_PRODUCER_AUTHORING_NOT_PASSED')
 # A later Linux failure does not rewrite the actual successful producer stages.

def extract_original(zip_path,destination,artifact=None):
 artifact=PRODUCER if artifact is None else artifact
 require(sha(zip_path)==artifact['artifactSha256'] and zip_path.stat().st_size==artifact['artifactBytes'] and not destination.exists(),'RESTORE_ZIP_IDENTITY')
 with zipfile.ZipFile(zip_path) as archive:
  rows=archive.infolist();require(len(rows)==len({x.filename for x in rows}) and sum(x.file_size for x in rows)<=256*1024**2,'RESTORE_ZIP_BOUNDS')
  for row in rows:
   p=PurePosixPath(row.filename);require(not p.is_absolute() and p.parts and '..' not in p.parts and p.as_posix()==row.filename.rstrip('/') and '\\' not in row.filename and not stat.S_ISLNK(row.external_attr>>16) and (stat.S_IFMT(row.external_attr>>16) in (0,stat.S_IFREG,stat.S_IFDIR)),'RESTORE_ZIP_PATH')
  archive.extractall(destination)

def producer_native_history():
 require(ANDROID and sha(PRODUCER_NATIVE)==PRODUCER_NATIVE_SHA,'RESTORE_PRODUCER_NATIVE_HISTORY_PIN')
 value=read(PRODUCER_NATIVE)
 require(value['sourceCommit']==PRODUCER['sourceCommit'] and value['runId']==PRODUCER['runId'] and value['runAttempt']==1 and
         value['sourceStateSha256']==PRODUCER['sourceStateSha256'],'RESTORE_PRODUCER_NATIVE_HISTORY_IDENTITY')
 from journey_pouncer_ground_support_probe import GENERIC_TESTS
 expected={'playmode':original.expected_cases('playmode'),'groundSupport':GENERIC_TESTS}
 require([row['kind'] for row in value['tests']]==['playmode','groundSupport'],'RESTORE_PRODUCER_NATIVE_HISTORY_SET')
 for row in value['tests']:
  names=[case['fullname'] for case in row['cases']]
  require(row['result']=='Passed' and row['counts']==dict(total=13,passed=13,failed=0,skipped=0,inconclusive=0) and
          len(names)==len(set(names))==13 and set(names)==set(expected[row['kind']]) and all(c['result']=='Passed' for c in row['cases']) and
          row['independentExportedNativeHashAvailable'] is False,'RESTORE_PRODUCER_NATIVE_HISTORY_CASES')
 return dict(sourceCommit=PRODUCER['sourceCommit'],runId=PRODUCER['runId'],runAttempt=1,scope=value['scope'],
             evidence=pin(PRODUCER_NATIVE),tests=value['tests'],executedInConsumer=False)

def producer_hud_evidence():
 require(ANDROID,'RESTORE_ANDROID_ONLY')
 sys.path.insert(0,str(TASK/'scripts'));import journey_mobile_hud_native as hud
 report=read(PRODUCER_HUD/'native-report.json')
 require(sha(PRIVATE/'producer-hud.zip')==HUD['artifactSha256'] and (PRIVATE/'producer-hud.zip').stat().st_size==HUD['artifactBytes'] and
         sha(PRODUCER_HUD/'native-report.json')==HUD['reportSha256'],'RESTORE_PRODUCER_HUD_PIN')
 require({p.name for p in PRODUCER_HUD.iterdir()}=={'native-report.json','captures'} and report['sourceCommit']==PRODUCER['sourceCommit'] and
         report['runId']==str(PRODUCER['runId']) and report['runAttempt']=='1' and report['sourceStateSha256']==PRODUCER['sourceStateSha256'] and
         report['status']=='EXACT_TEN_AND_13_RENDER_FIXTURES_VERIFIED' and report['scope']==hud.SCOPE and
         all(report[k] is False for k in ('deviceExecuted','gameplayAccepted','approved')),'RESTORE_PRODUCER_HUD_IDENTITY')
 actual=hud.capture_inventory(PRODUCER_HUD/'captures')
 def rows(values):return sorted((Path(r['path']).name,r['sha256'],r['bytes']) for r in values)
 require(rows(actual)==rows(report['captures']),'RESTORE_PRODUCER_HUD_CAPTURE_PINS')
 return dict(sourceCommit=PRODUCER['sourceCommit'],runId=str(PRODUCER['runId']),runAttempt='1',
             artifact=HUD,report=pin(PRODUCER_HUD/'native-report.json'),scope=report['scope'],originalNativeXml=report['nativeXml'],
             captures=actual,executedInConsumer=False)

def producer_hud_pins():
 value=producer_hud_evidence();return [value['report'],*value['captures']]

def validate_bundles(folder,producer_source):
 public_tree(folder)
 require(sha(folder/'generated/receipt.json')==PRODUCER['generatedReceiptSha256'],'RESTORE_GENERATED_RECEIPT')
 assets={};paths={};refs=[]
 for kind in generated.KINDS:
  part=folder/kind;r=read(part/'receipt.json');h=sha(part/'receipt.json')
  require(r['status']=='STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED' and r['approved'] is False and r['kind']==kind and r['importCommit']==PRODUCER['sourceCommit'] and r['importRunUrl']==RUN_URL and r['nativeCases']==26,'RESTORE_STRICT_IDENTITY')
  verify_staged_inventory(part,r['files'],h)
  for item in r['files']:
   name=item['path']
   if name=='CandidateArtImports.meta' or name.startswith('CandidateArtImports/'):
    name='Assets/DesertRV/'+name;require(name not in assets or assets[name]==item['sha256'],'RESTORE_STRICT_COLLISION');assets[name]=item['sha256'];paths[name]=part/item['path']
  refs.append(dict(kind=kind,path=kind+'/receipt.json',sha256=h,nativeXmlSha256=r['nativeXmlSha256'],nativeCases=26))
 r=read(folder/'generated/receipt.json');verify_staged_inventory(folder/'generated',r['files'],PRODUCER['generatedReceiptSha256'])
 require(r['schema']==generated.SCHEMA and r['status']=='GENERATED_JOURNEY_SAVED_UNREVIEWED' and r['sourceCommit']==PRODUCER['sourceCommit'] and r['importRunUrl']==RUN_URL and r['runAttempt']==1 and r['unityVersion']==generated.UNITY and
         all(r[k] is False for k in ('approved','visualReviewed','gameplayReviewed','audioAuditioned','scopeReusable')) and r['strictReceipts']==refs and r['sourceStateSha256']==PRODUCER['sourceStateSha256'],'RESTORE_GENERATED_IDENTITY')
 require(r['nativeManifestPath']=='native-authored-assets.json' and r['diagnosticScopeEvidencePath']=='diagnostic-scope-evidence.json' and r['spawnGroundingPath']==generated.GROUND_EXPORT,'RESTORE_EVIDENCE_PATHS')
 for pathkey,hashkey in [('nativeManifestPath','nativeManifestSha256'),('diagnosticScopeEvidencePath','diagnosticScopeSha256'),('spawnGroundingPath','spawnGroundingSha256')]:require(sha(folder/'generated'/r[pathkey])==r[hashkey],'RESTORE_ORIGINAL_EVIDENCE_BYTES')
 native=read(folder/'generated'/r['nativeManifestPath']);ground=read(folder/'generated'/r['spawnGroundingPath'])
 require(generated.grounding_pin(native)['sha256']==r['spawnGroundingSha256'],'RESTORE_GROUNDING_PIN')
 exported={x['path']:x['sha256'] for x in r['files'] if x['path'].startswith('Assets/')};omitted={x['path']:x['sha256'] for x in r['omittedUnreferencedLayout']}
 require(not set(exported)&set(omitted) and all(re.fullmatch(r'Assets/DesertRV/Scenes/Journey/Layout-[0-9A-F]{6}\.mat(?:\.meta)?',n) for n in omitted),'RESTORE_OMITTED_LAYOUT')
 require({x['path']:x['sha256'] for x in native['files']}=={**exported,**omitted} and not set(assets)&set(exported),'RESTORE_NATIVE_ASSET_SET')
 for name,h in exported.items():assets[name]=h;paths[name]=folder/'generated'/name
 known={kind+'/'+x.relative_to(folder/kind).as_posix() for kind in generated.KINDS for x in (folder/kind).rglob('*') if x.is_file()}
 known.update('generated/'+x.relative_to(folder/'generated').as_posix() for x in (folder/'generated').rglob('*') if x.is_file());known.add('preparation.json')
 if ANDROID:
  extra={'keyboard-look/native-report.json': '24ab29ca896483996c474e2a41cc3ba837084c09cc95ec5a2525cc34f344bf5a', 'keyboard-look/source-report.json': '34a42f77f3bcd759b2b2cf58b7e1eb6cb739c9990512bae7a0faab828622f8ab', 'keyboard-look/isolation-report.json': 'a5fa0b8d4dd4cddee3463918283c3fb01f559b508cd352dc06199f32b9978e07', 'combat-feedback/native-report.json': '74f4cf99affbec0d746e54f7a87c08de57f7ba76f9065ba17ca1192f169b6ef0', 'region-hud/native-report.json': 'e06c18721be98fcec8dcec8b88e6bb84ad541eacfb03a462bc5d75a7b0e50f97'}
  require(all(sha(folder/name)==h for name,h in extra.items()),'RESTORE_PRODUCER_DIAGNOSTIC_PIN');known.update(extra)
 require({x.relative_to(folder).as_posix() for x in folder.rglob('*') if x.is_file()}==known and all(not x.is_symlink() for x in folder.rglob('*')),'RESTORE_TOPLEVEL_ALLOWLIST')
 summary=read(folder/'preparation.json');require(summary['sourceCommit']==PRODUCER['sourceCommit'] and summary['status']=='PREPARED_EDITOR_SCOPE_UNREVIEWED' and summary['generatedExport']['sha256']==PRODUCER['generatedReceiptSha256'] and summary['nativeXmlSha256']==r['nativeAuthoringXmlSha256'],'RESTORE_PRODUCER_SUMMARY')
 prefix='tasks/desert-rv/unity/';source={x['path'][len(prefix):]:x['sha256'] for x in producer_source['files']+producer_source['restoredFiles'] if x['path'].startswith(prefix)}
 return dict(assets=assets,paths=paths,source=source,native=native,receipt=r,ground=ground,exported=exported,omitted=omitted,strict={n:h for n,h in assets.items() if n.startswith('Assets/DesertRV/CandidateArtImports')})

SELECTION='tasks/desert-rv/art/journey-preparation/three-strict-candidates.json'
PRODUCER_SOURCE=PRIVATE/'producer-SOURCE-STATE.json'
EXPORT=TASK/'journey-restoration-public-export'
SOURCE_LABEL='REVIEWED_RESTORATION_SOURCE_TRANSITION'
REPORT_LABEL='RESTORED_JOURNEY_NATIVE_REVALIDATED_UNREVIEWED'
INPUT_LABEL='RESTORE_PINNED_JOURNEY_FOR_NATIVE_REVALIDATION'

def current_run():return 'https://github.com/yangerstar1/task-workbench/actions/runs/'+os.environ['GITHUB_RUN_ID']
def public_tree(folder):
 files,dirs=prepared_source.walk(folder)
 wanted={p.as_posix() for name in files for p in Path(name).parents if p!=Path('.')}
 require(dirs==wanted,'RESTORE_UNDECLARED_BUNDLE_DIRECTORY')
 return files

def check_grounding(ground,selection,commit,selection_sha,ready_sha=None):
 require(set(ground)==generated.GROUND_KEYS and type(ground['schema']) is int and ground['schema']==1 and ground['status']=='ACTUAL_NATIVE_ROOT_GROUNDING_UNREVIEWED' and ground['sourceCommit']==commit and ground['source']==generated.GROUND_SOURCE and ground['approved'] is False and ground['selectionSha256']==selection_sha and digest(ground['readyInputSha256']),'RESTORE_GROUNDING_IDENTITY')
 if ready_sha is not None:require(ground['readyInputSha256']==ready_sha,'RESTORE_GROUNDING_INPUT')
 expected={}
 for region in selection['integration']['regions']:
  for row in region['guards']+region['roadBeasts']+[e for wave in region['waves'] for e in wave['enemies']]:
   require(row['id'] not in expected,'RESTORE_GROUNDING_DUPLICATE');expected[row['id']]=(region['region'],row)
 require(len(expected)==9 and len(ground['rows'])==9,'RESTORE_GROUNDING_COUNT');seen=set()
 for row in ground['rows']:
  require(set(row)==generated.GROUND_ROW_KEYS and row['id'] in expected and row['id'] not in seen,'RESTORE_GROUNDING_ROW');seen.add(row['id'])
  region,declared=expected[row['id']]
  require(row['region']==region and row['scene']==generated.REGION_SCENES[region] and row['kind']==declared['kind'] and row['yaw']==declared['yaw'] and row['declaredPosition']==declared['position'] and declared['position']['y']==0,'RESTORE_GROUNDING_DECLARATION')
  vectors=[row[k] for k in ('declaredPosition','resolvedPosition','hitPoint','hitNormal')]
  require(all(isinstance(v,dict) and set(v)=={'x','y','z'} and all(type(n) in (float,int) and __import__('math').isfinite(n) for n in v.values()) for v in vectors),'RESTORE_GROUNDING_FINITE')
  require(row['floor'] in ('Route foundation','Road surface') and type(row['layer']) is int and row['layer']==0 and row['hitNormal']['y']>=.9,'RESTORE_GROUNDING_SURFACE')
  require(all(row['resolvedPosition'][a]==declared['position'][a] and abs(row['hitPoint'][a]-declared['position'][a])<=.0001 for a in ('x','z')) and row['resolvedPosition']['y']==row['hitPoint']['y'],'RESTORE_GROUNDING_POSITION')

def check_bundle_closure(bundle,source):
 prefix='tasks/desert-rv/unity/'
 current={x['path'][len(prefix):]:x['sha256'] for x in source['files']+source['restoredFiles'] if x['path'].startswith(prefix)}
 deps=generated.native_closure(bundle['native'],{**bundle['exported'],**bundle['omitted']},current,bundle['strict'],PROJECT,PRODUCER['sourceCommit'],RUN_URL)
 require(deps==bundle['receipt']['dependencies'],'RESTORE_ORIGINAL_CLOSURE_CHANGED')
 for row in bundle['receipt']['packageControls']:
  require(set(row)=={'path','sha256','bytes'} and row['path'] in ('Packages/manifest.json','Packages/packages-lock.json','ProjectSettings/ProjectVersion.txt') and generated.record(PROJECT/row['path'],row['path'])==row,'RESTORE_PACKAGE_CONTROLS')
 require(len(bundle['receipt']['packageControls'])==3,'RESTORE_PACKAGE_CONTROL_COUNT')
 selection=read(ROOT/SELECTION);check_grounding(bundle['ground'],selection,PRODUCER['sourceCommit'],sha(ROOT/SELECTION))
 return deps

def request_payload(bundle,source,source_proof):
 from pipeline import validate_selection
 selected=read(ROOT/SELECTION);validate_selection(selected)
 integration=json.loads(json.dumps(selected['integration']));integration['sourceCommit']=os.environ['GITHUB_SHA'];integration['candidates']=[]
 for item in selected['sources']:
  kind=item['kind'];report_path=PROJECT/'JourneyEvidence/CandidateArt'/kind/'import-report.json';report=read(report_path)
  prefab=report['prefab'];contract=str(Path(prefab).parent/'contract.json');c=read(PROJECT/contract)
  require(sha(PROJECT/contract)==item['sha256']==report['contractSha256'],'RESTORE_CONTRACT_CHANGED')
  integration['candidates'].append(dict(kind=kind,sourceModelPath=str(Path(contract).parent/'Source'/c['modelFile']),
    prefab=dict(path=prefab,sha256=sha(PROJECT/prefab),dependencyHash=report['dependencyHash'],dependencySha256=report['dependencySha256']),
    contract=dict(path=contract,sha256=sha(PROJECT/contract)),importReport=dict(path=str(report_path.relative_to(PROJECT)),sha256=sha(report_path))))
 integration['savedInputs']=bundle['receipt']['integrationOutputs']
 for key,filename in [('muzzleFlashPrefab','MuzzleFlash.prefab'),('arcPresentationPrefab','ArcPresentation.prefab')]:
  matches=[name for name in bundle['exported'] if name.endswith('/'+filename)];require(len(matches)==1,'RESTORE_EXACT_FX')
  integration[key]=dict(path=matches[0],sha256=bundle['exported'][matches[0]],dependencyHash='',dependencySha256='')
 for row in integration['sounds']:row['clip']['sha256']=sha(PROJECT/row['clip']['path'])
 records={row['path']:dict(path=row['path'],sha256=row['sha256']) for row in source['files']+source['restoredFiles']}
 for name,h in bundle['assets'].items():records['tasks/desert-rv/unity/'+name]=dict(path='tasks/desert-rv/unity/'+name,sha256=h)
 extras=[TASK/'SOURCE-STATE.json',SOURCE_PROOF,PRODUCER_SOURCE,PUBLIC/'generated/native-authored-assets.json',PUBLIC/'generated'/generated.GROUND_EXPORT]
 extras += [PUBLIC/k/'receipt.json' for k in (*generated.KINDS,'generated')]
 extras += [PROJECT/'JourneyEvidence/CandidateArt'/k/'import-report.json' for k in generated.KINDS]
 for path in extras:records[str(path.relative_to(ROOT))]=pin(path)
 result=dict(schema=1,label=INPUT_LABEL,sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),assetProducerSourceCommit=PRODUCER['sourceCommit'],assetProducerRunUrl=RUN_URL,
  generatedReceiptSha256=PRODUCER['generatedReceiptSha256'],sourceTransitionProof=pin(SOURCE_PROOF),selection=pin(ROOT/SELECTION),
  originalGeneratedReceipt=pin(PUBLIC/'generated/receipt.json'),originalNativeManifest=pin(PUBLIC/'generated/native-authored-assets.json'),originalGrounding=pin(PUBLIC/'generated'/generated.GROUND_EXPORT),
  files=[records[n] for n in sorted(records)],integration=integration,expectedDependencies=bundle['native']['dependencies'],
  directories=sorted(name+'/'+d for name in ('Assets','Packages','ProjectSettings') for d in directories(PROJECT/name)))
 if ANDROID:result.update(schema=2,label='RESTORE_AND_DERIVE_PINNED_WARM_MATERIAL',materialDerivation=DERIVATION_OPERATION)
 return result

def restore_assets(bundle):
 # Exact new Assets only. Never copy Library, private snapshots, old scope, packages or Settings.
 for name,path in sorted(bundle['paths'].items()):
  target=PROJECT/name;require(rel(name) and name.startswith('Assets/') and not target.exists() and not target.is_symlink(),'RESTORE_ASSET_COLLISION')
  require(not any(p.is_symlink() for p in target.parents),'RESTORE_ASSET_PARENT_SYMLINK')
  target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
  require(sha(target)==bundle['assets'][name],'RESTORE_ASSET_COPY_CHANGED')

def stage(policy_sha):
 if ANDROID:
  sys.path.insert(0,str(TASK/'scripts/player'));import journey_android
  journey_android.dispatch()
 guard();require(digest(policy_sha) and sha(ROOT/POLICY)==policy_sha,'RESTORE_DISPATCH_POLICY_PIN')
 subprocess.run(['git','ls-files','--error-unmatch',POLICY],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
 require(not PRIVATE.exists() and not PUBLIC.exists() and not EXPORT.exists() and not (PROJECT/'JourneyEvidence/CandidateArt').exists() and not (PROJECT/'Assets/DesertRV/Scenes/Journey').exists() and not (PROJECT/'Assets/DesertRV/CandidateArtImports').exists() and not (PROJECT/'CandidatePackageSnapshot').exists(),'RESTORE_FRESH_WORKSPACE')
 original.guard();identity=original.identity();source=prepared_source.verify_original(identity)
 initial_dirs={name:sorted(directories(PROJECT/name)) for name in ('Assets','Packages','ProjectSettings')}
 policy=read(ROOT/POLICY)
 repo=api('/repos/'+PRODUCER['repository']);require(repo.get('private') is False and repo.get('fork') is False,'RESTORE_PUBLIC_ORIGINAL_REPOSITORY')
 run=api('/repos/'+PRODUCER['repository']+'/actions/runs/'+str(PRODUCER['runId']))
 artifact=api('/repos/'+PRODUCER['repository']+'/actions/artifacts/'+str(PRODUCER['artifactId']))
 jobs=api('/repos/'+PRODUCER['repository']+'/actions/runs/'+str(PRODUCER['runId'])+'/attempts/1/jobs?per_page=100');validate_producer_api(run,artifact,jobs)
 fetched=api('/repos/'+PRODUCER['repository']+'/contents/tasks/desert-rv/SOURCE-STATE.json?ref='+PRODUCER['sourceCommit'])
 require(fetched.get('type')=='file' and fetched.get('encoding')=='base64','RESTORE_PRODUCER_SOURCE_RESPONSE')
 data=base64.b64decode(fetched['content'],validate=False);require(hashlib.sha256(data).hexdigest()==PRODUCER['sourceStateSha256'],'RESTORE_PRODUCER_SOURCE_PIN')
 before=json.loads(data);changes=source_transition(policy,before,source,policy_sha)
 PRIVATE.mkdir(parents=True);PRODUCER_SOURCE.write_bytes(data)
 if ANDROID:
  evidence=dict(schema=1,sourceCommit=PRODUCER['sourceCommit'],runId=PRODUCER['runId'],runAttempt=1,
                scope='ORIGINAL_PRODUCER_API_OBSERVATION_NOT_CURRENT_NATIVE_EXECUTION',run=run,artifact=artifact,jobs=jobs)
  write_fresh(PRODUCER_API,evidence)
  hud=api('/repos/'+PRODUCER['repository']+'/actions/artifacts/'+str(HUD['artifactId']))
  require(hud.get('id')==HUD['artifactId'] and hud.get('name')==HUD['artifactName'] and hud.get('size_in_bytes')==HUD['artifactBytes'] and
          hud.get('digest')=='sha256:'+HUD['artifactSha256'] and hud.get('expired') is False and hud.get('workflow_run',{}).get('id')==PRODUCER['runId'] and
          hud['workflow_run'].get('head_sha')==PRODUCER['sourceCommit'],'RESTORE_PRODUCER_HUD_ARTIFACT')
  with (PRIVATE/'producer-hud.zip').open('xb') as stream:
   subprocess.run(['gh','api','/repos/'+PRODUCER['repository']+'/actions/artifacts/'+str(HUD['artifactId'])+'/zip'],stdout=stream,check=True)
  extract_original(PRIVATE/'producer-hud.zip',PRODUCER_HUD,HUD);producer_hud_evidence()

 zip_path=PRIVATE/'producer-artifact.zip'
 with zip_path.open('xb') as stream:subprocess.run(['gh','api','/repos/'+PRODUCER['repository']+'/actions/artifacts/'+str(PRODUCER['artifactId'])+'/zip'],stdout=stream,check=True)
 extract_original(zip_path,PUBLIC);public_pins=public_tree(PUBLIC);bundle=validate_bundles(PUBLIC,before)
 restore_assets(bundle);check_bundle_closure(bundle,source)
 for kind in generated.KINDS:
  target=PROJECT/'JourneyEvidence/CandidateArt'/kind/'import-report.json';target.parent.mkdir(parents=True);shutil.copyfile(PUBLIC/kind/'import-report.json',target)
  require(sha(target)==sha(PUBLIC/kind/'import-report.json'),'RESTORE_REPORT_COPY_CHANGED')
 prepared_source.verify_original(identity);prepared_source.verify_asset_union(source,initial_dirs,bundle['assets'])
 proof=dict(schema=1,label=SOURCE_LABEL,sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),assetProducerSourceCommit=PRODUCER['sourceCommit'],assetProducerRunUrl=RUN_URL,
  producer=PRODUCER,policy=pin(ROOT/POLICY),producerSource=pin(PRODUCER_SOURCE),consumerSource=pin(TASK/'SOURCE-STATE.json'),changes=changes,originalAssetsUnchanged=True,scopeReused=False)
 write_fresh(SOURCE_PROOF,proof);payload=request_payload(bundle,source,proof);write_fresh(INPUT,payload);INPUT.with_suffix('.sha256').write_text(sha(INPUT)+'\n')
 state=dict(schema=1,sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),initialIdentity=identity,initialSourceDirectories=initial_dirs,addedAssets=bundle['assets'],publicFiles=public_pins,policySha256=policy_sha,sourceProof=pin(SOURCE_PROOF),input=pin(INPUT),producerSource=pin(PRODUCER_SOURCE))
 if ANDROID:state['producerApi']=pin(PRODUCER_API)
 write_fresh(STATE,state)
 verify_assets();print('JOURNEY_RESTORED_BYTES_AWAIT_FRESH_NATIVE_REVALIDATION')

def verify_assets(derived=False):
 require(not derived or ANDROID,'DERIVE_ANDROID_ONLY')
 s=read(STATE);require(s['schema']==1 and s['sourceCommit']==os.environ['GITHUB_SHA'] and s['producerRunUrl']==current_run(),'RESTORE_CONSUMER_IDENTITY')
 if ANDROID:
  require(s['producerApi']==pin(PRODUCER_API),'RESTORE_PRODUCER_API_CHANGED')
  evidence=read(PRODUCER_API);validate_producer_api(evidence['run'],evidence['artifact'],evidence['jobs']);producer_hud_evidence();producer_native_history()

 for name in ('sourceProof','input','producerSource'):
  expected={'sourceProof':SOURCE_PROOF,'input':INPUT,'producerSource':PRODUCER_SOURCE}[name]
  require(s[name]==pin(expected),'RESTORE_PRIVATE_PROOF_CHANGED')
 require(sha(PRIVATE/'producer-artifact.zip')==PRODUCER['artifactSha256'] and (PRIVATE/'producer-artifact.zip').stat().st_size==PRODUCER['artifactBytes'],'RESTORE_ORIGINAL_ZIP_CHANGED')
 require(public_tree(PUBLIC)==s['publicFiles'],'RESTORE_PUBLIC_BUNDLE_CHANGED')
 before=read(PRODUCER_SOURCE);require(sha(PRODUCER_SOURCE)==PRODUCER['sourceStateSha256'],'RESTORE_PRODUCER_SOURCE_CHANGED')
 source=prepared_source.verify_original(s['initialIdentity']);require(sha(ROOT/POLICY)==s['policySha256'],'RESTORE_POLICY_CHANGED')
 changes=source_transition(read(ROOT/POLICY),before,source,s['policySha256']);proof=read(SOURCE_PROOF)
 expected=dict(schema=1,label=SOURCE_LABEL,sourceCommit=s['sourceCommit'],producerRunUrl=s['producerRunUrl'],assetProducerSourceCommit=PRODUCER['sourceCommit'],assetProducerRunUrl=RUN_URL,
  producer=PRODUCER,policy=pin(ROOT/POLICY),producerSource=pin(PRODUCER_SOURCE),consumerSource=pin(TASK/'SOURCE-STATE.json'),changes=changes,originalAssetsUnchanged=True,scopeReused=False)
 require(proof==expected,'RESTORE_SOURCE_TRANSITION_CHANGED')
 bundle=validate_bundles(PUBLIC,before);require(bundle['assets']==s['addedAssets'],'RESTORE_ASSET_INVENTORY_CHANGED')
 if derived:
  material=material_derivation()['material'];effective=dict(s['addedAssets']);effective[MATERIAL]=material['afterSha256']
  prepared_source.verify_asset_union(source,s['initialSourceDirectories'],effective)
  # Parent ZIP/native manifest remain immutable. The effective closure differs in exactly one declared asset row.
  expected=derived_dependencies(bundle,material)
  for row in expected:
   if row['kind']=='asset':require(generated.record(PROJECT/row['path'],row['path'])=={k:row[k] for k in ('path','sha256','bytes')},'DERIVE_DEPENDENCY_BYTES')
  for row in bundle['receipt']['packageControls']:require(generated.record(PROJECT/row['path'],row['path'])==row,'RESTORE_PACKAGE_CONTROLS')
 else:
  prepared_source.verify_asset_union(source,s['initialSourceDirectories'],s['addedAssets']);check_bundle_closure(bundle,source)
 require(not (PROJECT/'JourneyEvidence/journey-diagnostic-scope.json').exists(),'RESTORE_OLD_SCOPE_FORBIDDEN')
 for kind in generated.KINDS:require(sha(PROJECT/'JourneyEvidence/CandidateArt'/kind/'import-report.json')==sha(PUBLIC/kind/'import-report.json'),'RESTORE_SAFE_REPORT_CHANGED')
 require(INPUT.with_suffix('.sha256').read_text().strip()==sha(INPUT) and read(INPUT)==request_payload(bundle,source,proof),'RESTORE_NATIVE_INPUT_CHANGED')
 return s,bundle

def verify_boundary():
 import linux_build_input as linux
 verify_assets();value=linux.boundary_evidence();write_fresh(PRIVATE/'linux-boundary-verified.json',value);return value

def native_evidence():
 import xml.etree.ElementTree as ET
 from strict_output import safe
 matches=list((TASK/'artifacts/journey-restoration').rglob('*.xml'));require(len(matches)==1,'RESTORE_NATIVE_XML_COUNT')
 path=safe(matches[0]);require(path.stat().st_size<=10*1024**2,'RESTORE_NATIVE_XML_SIZE');xml=ET.parse(path).getroot();cases=list(xml.iter('test-case'))
 require(xml.tag=='test-run' and xml.get('result')=='Passed' and xml.get('total')==xml.get('passed')=='1' and all(xml.get(k)=='0' for k in ('failed','skipped','inconclusive')) and len(cases)==1 and cases[0].get('fullname')==NATIVE_NAME and cases[0].get('result')=='Passed','RESTORE_NATIVE_NOT_PASSED')
 return pin(path)

REPORT_KEYS={'schema','label','sourceCommit','producerRunUrl','assetProducerSourceCommit','assetProducerRunUrl','generatedReceiptSha256','sourceTransitionProof','requestSha256','unityVersion','sourceBytesUnchanged','originalAssetsUnchanged','structureValidated','productionApprovalRejected','approved','scopeReused','scenes','dependencies','grounding'}
def validate_native_report(report,bundle):
 keys=REPORT_KEYS|({'derivation','originalBeforeAuthoringVerified','exactMaterialDelta','derivedBindingsValidated'} if ANDROID else set())
 require(set(report)==keys and type(report['schema']) is int and report['schema']==(2 if ANDROID else 1) and report['label']==(DERIVED_LABEL if ANDROID else REPORT_LABEL) and report['sourceCommit']==os.environ['GITHUB_SHA'] and report['producerRunUrl']==current_run() and report['assetProducerSourceCommit']==PRODUCER['sourceCommit'] and report['assetProducerRunUrl']==RUN_URL and report['generatedReceiptSha256']==PRODUCER['generatedReceiptSha256'] and report['sourceTransitionProof']==pin(SOURCE_PROOF) and report['requestSha256']==sha(INPUT) and report['unityVersion']==generated.UNITY,'RESTORE_NATIVE_REPORT_IDENTITY')
 require(all(report[k] is True for k in ('sourceBytesUnchanged','structureValidated','productionApprovalRejected')) and report['originalAssetsUnchanged'] is (not ANDROID) and report['approved'] is False and report['scopeReused'] is False,'RESTORE_NATIVE_REPORT_NOT_READY')
 if ANDROID:require(report['derivation']==pin(DERIVATION_RECORD) and report['originalBeforeAuthoringVerified'] is True and report['exactMaterialDelta'] is True and report['derivedBindingsValidated'] is True,'DERIVE_NATIVE_PROOF')
 original_outputs={r['path']:r for r in bundle['receipt']['integrationOutputs']};scenes=report['scenes']
 require(len(scenes)==5 and len({r['path'] for r in scenes})==5 and {r['path'] for r in scenes}==set(original_outputs),'RESTORE_NATIVE_SCENE_SET')
 for row in scenes:require(set(row)=={'path','sha256','dependencyHash','dependencySha256'} and row['sha256']==original_outputs[row['path']]['sha256']==sha(PROJECT/row['path']) and digest(row['dependencyHash'],32) and digest(row['dependencySha256']),'RESTORE_NATIVE_SCENE_PIN')
 # Approved changes are Editor/entry diagnostics only. Actual dependency byte closure stays exact.
 expected=derived_dependencies(bundle,material_derivation()['material']) if ANDROID else bundle['native']['dependencies']
 require(report['dependencies']==expected,'RESTORE_NATIVE_DEPENDENCY_BYTES_CHANGED')
 check_grounding(report['grounding'],read(ROOT/SELECTION),os.environ['GITHUB_SHA'],sha(ROOT/SELECTION),sha(INPUT))
 require(len(report['grounding']['rows'])==len(bundle['ground']['rows']),'RESTORE_NATIVE_GROUNDING_CHANGED')
 oldrows={x['id']:x for x in bundle['ground']['rows']}
 for row in report['grounding']['rows']:
  old=oldrows[row['id']];vectors={'declaredPosition','resolvedPosition','hitPoint','hitNormal'}
  require(all(row[k]==old[k] for k in set(row)-vectors) and all(sum((row[k][a]-old[k][a])**2 for a in ('x','y','z'))<1e-10 for k in vectors),'RESTORE_NATIVE_GROUNDING_CHANGED')
 return report

def verify():
 import linux_build_input as linux
 s,bundle=verify_assets(derived=ANDROID);linux.bound_boundary();actual=native_evidence();proof=read(VERIFIED)
 expected=dict(schema=1,label='CURRENT_DERIVED_RESTORATION_NATIVE_PASSED' if ANDROID else 'CURRENT_RESTORATION_NATIVE_PASSED',sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),nativeXml=actual,nativeReport=pin(REPORT),sourceProof=pin(SOURCE_PROOF),input=pin(INPUT),boundaryNativeXml=linux.boundary_evidence()['nativeXml'])
 if ANDROID:verify_derived_export();expected['derivedReceipt']=pin(DERIVED_RECEIPT)
 require(proof==expected,'RESTORE_NATIVE_PROOF_CHANGED')
 validate_native_report(read(REPORT),bundle)
 return s,bundle,proof

def finish(native):
 import linux_build_input as linux
 require(native=='success','RESTORE_NATIVE_STEP_FAILED');s,bundle=verify_assets(derived=ANDROID);boundary=linux.bound_boundary();xml=native_evidence();report=validate_native_report(read(REPORT),bundle)
 proof=dict(schema=1,label='CURRENT_DERIVED_RESTORATION_NATIVE_PASSED' if ANDROID else 'CURRENT_RESTORATION_NATIVE_PASSED',sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),nativeXml=xml,nativeReport=pin(REPORT),sourceProof=pin(SOURCE_PROOF),input=pin(INPUT),boundaryNativeXml=boundary['nativeXml'])
 if ANDROID:export_derived(xml,boundary['nativeXml']);proof['derivedReceipt']=pin(DERIVED_RECEIPT)
 write_fresh(VERIFIED,proof)
 verify();require(not EXPORT.exists(),'RESTORE_PUBLIC_DESTINATION_EXISTS');EXPORT.mkdir()
 evidence=[]
 for path,name in ((REPORT,'native-restoration.json'),(SOURCE_PROOF,'source-transition.json'),(INPUT,'native-input.json')):
  shutil.copyfile(path,EXPORT/name);evidence.append(generated.record(EXPORT/name,name));require(sha(EXPORT/name)==sha(path),'RESTORE_PUBLIC_COPY_CHANGED')
 receipt=dict(schema=1,status=REPORT_LABEL,sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),assetProducer=PRODUCER,generatedReceiptSha256=PRODUCER['generatedReceiptSha256'],nativeXmlSha256=xml['sha256'],boundaryNativeXmlSha256=boundary['nativeXml']['sha256'],nativeCases=1,boundaryNativeCases=17,approved=False,scopeReusable=False,files=evidence)
 if ANDROID:receipt.update(status=DERIVED_LABEL,derivedReceipt=pin(DERIVED_RECEIPT),inheritedEvidenceScope='PARENT_155_ONLY_NOT_CURRENT_DERIVED_ASSET_VALIDATION')
 write_fresh(EXPORT/'receipt.json',receipt);verify_staged_inventory(EXPORT,evidence,sha(EXPORT/'receipt.json'))
 if os.environ.get('GITHUB_OUTPUT'):
  with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('export_ready=true\n')
 print('JOURNEY_DERIVED_RESTORATION_EXACT_NATIVE_PASSED_UNREVIEWED' if ANDROID else 'JOURNEY_RESTORATION_EXACT_NATIVE_PASSED_UNREVIEWED')

DIAGNOSTIC=PRIVATE/'restoration-diagnostic.json'
HOST_STATUS=TASK/'journey-restoration-status.json'
DIAGNOSTIC_STAGES={'INPUT','INVENTORY','SOURCE_PROOF','STRICT_BUNDLES','DEPENDENCIES','GENERATED_BYTES','SELECTION','POSES','GROUNDING','IMPORTER_IDENTITIES','SAVED_BINDINGS','MATERIAL_DERIVATION','DERIVED_BINDINGS','WORLD_HUD_CAPTURE','FINAL_PROTECTION','PROOF','COMPLETED'}
DIAGNOSTIC_ERRORS={'WARM_LAMP_CONTEXT','WARM_LAMP_SOURCE_PIN','WARM_LAMP_META_PIN','WARM_LAMP_SOURCE_FORMAT','WARM_LAMP_SOURCE_SEMANTICS','WARM_LAMP_IDENTITY','WARM_LAMP_SUBASSET_IDENTITY','WARM_LAMP_SUBASSET_DIRTY','WARM_LAMP_SUBASSET_CHANGED','WARM_LAMP_LOADED_DIRTY','WARM_LAMP_LOADED_SOURCE','WARM_LAMP_SERIALIZED_LAYOUT','WARM_LAMP_GI','WARM_LAMP_KEYWORD','WARM_LAMP_ALIAS','WARM_LAMP_RUNTIME_VALUES','WARM_LAMP_UNDECLARED_RUNTIME_CHANGE','WARM_LAMP_UNDECLARED_SERIALIZED_CHANGE','WARM_LAMP_SCENE_CHANGED','WARM_LAMP_OTHER_ASSET_DIRTY','WARM_LAMP_PROTECTION','WARM_LAMP_IMPORT_BYTES','WARM_LAMP_UNLOAD','WARM_LAMP_RELOAD_DIRTY','WARM_LAMP_RELOAD_BYTES','WARM_LAMP_NATIVE_INPUT','WARM_LAMP_NATIVE_LOAD','WARM_LAMP_NATIVE_AUTHOR','WARM_LAMP_NATIVE_SAVE','WARM_LAMP_NATIVE_IMPORT','WARM_LAMP_NATIVE_UNLOAD','WARM_LAMP_NATIVE_RELOAD','DERIVE_PARENT_IDENTITY','DERIVE_MATERIAL_EVIDENCE','DERIVE_MATERIAL_RECORD','DERIVE_BINDINGS','CACHE_PACKAGE_IDENTITY','CACHE_ASSET_BYTES','CACHE_META_BYTES','CACHE_SUBASSET_RELATION','CACHE_FONT_NOT_LOADED','CACHE_FONT_IDENTITY','CACHE_FONT_NOT_DYNAMIC','CACHE_FONT_ATLAS_LINK','DIAGNOSTIC_ARGUMENT','RUN_ID_ARGUMENT','NONE','IMPORTER_IDENTITY','DEPENDENCY_BYTES','DIRTY_DEPENDENCY','ASSET_LIFECYCLE','VALIDATION','IO','UNAUTHORIZED','OTHER'}
ASSET_LIFECYCLE_ORDER=('RESTORATION_ENTRY','DEPENDENCIES_BEFORE','DEPENDENCIES_AFTER','POSES_BEFORE','POSES_AFTER','GROUNDING_BEFORE','GROUNDING_AFTER','IMPORTER_IDENTITIES_BEFORE','IMPORTER_IDENTITIES_AFTER','SAVED_ROOT_IDENTITIES_BEFORE','SAVED_ROOT_IDENTITIES_AFTER','SAVED_BINDINGS_BEFORE','SAVED_BINDINGS_AFTER','MATERIAL_DERIVATION_BEFORE','MATERIAL_DERIVATION_AFTER','CAPTURE_ENTRY','CAPTURE_GATE_BEFORE','CAPTURE_GATE_AFTER','CAPTURE_REGION_1_BEFORE','CAPTURE_REGION_1_AFTER','CAPTURE_REGION_3_BEFORE','CAPTURE_REGION_3_AFTER','CAPTURE_SCENE_RESTORE_BEFORE','CAPTURE_SCENE_RESTORE_AFTER','RESTORATION_SCENE_RESTORE_BEFORE','RESTORATION_SCENE_RESTORE_AFTER','FINAL_PROTECTION_BEFORE','FINAL_PROTECTION_AFTER')
ASSET_LIFECYCLE_STAGES=frozenset(ASSET_LIFECYCLE_ORDER)
BUILTIN_DEPENDENCIES=frozenset(('Resources/unity_builtin_extra','Library/unity default resources'))
def diagnostic_dependencies():
 receipt=read(PUBLIC/'generated/receipt.json');require(sha(PUBLIC/'generated/receipt.json')==PRODUCER['generatedReceiptSha256'],'RESTORE_DIAGNOSTIC_ORIGINAL_RECEIPT')
 native_path=PUBLIC/'generated/native-authored-assets.json';require(sha(native_path)==receipt['nativeManifestSha256'],'RESTORE_DIAGNOSTIC_ORIGINAL_MANIFEST')
 rows=read(native_path)['dependencies'];expected={x['path']:x for x in rows}
 require(len(expected)==len(rows) and all(rel(p) and (p.startswith(('Assets/','Packages/')) or p in BUILTIN_DEPENDENCIES) for p in expected),'RESTORE_DIAGNOSTIC_DEPENDENCY_DOMAIN')
 return expected

def bounded_asset_lifecycle(value):
 snapshots=value['assetLifecycle']
 require(type(snapshots) is list and len(snapshots)<=len(ASSET_LIFECYCLE_STAGES),'RESTORE_DIAGNOSTIC_LIFECYCLE_SCHEMA')
 if not snapshots:
  require(value['stage']=='INPUT' and not value['completed'],'RESTORE_DIAGNOSTIC_LIFECYCLE_MISSING');return
 require(value['consumerIdentityMatched'],'RESTORE_DIAGNOSTIC_LIFECYCLE_IDENTITY')
 expected=diagnostic_dependencies()
 original={p:('BUILTIN','',0) if p in BUILTIN_DEPENDENCIES else ('AVAILABLE',r['sha256'],r['bytes']) for p,r in expected.items()}
 disk=dict(original);previous={};stages=set();observed=set();has_baseline=False;gate_bound=False;gate_membership={};identity_context={};stage_index=-1
 counts=('captureGateObjectCount','observedPathCount','objectCount','distinctPathCount','enteredDirtyCount','retainedDirtyCount','clearedCount','unobservedCount','diskMismatchCount','diskUnavailableCount')
 keys={'sequence','stage','status','errorCode','preexistingBaseline','captureGateBound','declaredDependencyCount',*counts,'dirtyDependencies','clearedDependencies','unobservedDependencies','diskChanges'}
 row_keys={'path','type','captureGateMembership','identityState','guid','localId','dirty','transition','diskState','sha256','bytes'}
 def state(kind,h,size):
  require(kind in {'AVAILABLE','MISSING','UNREADABLE','UNSAFE','BUILTIN','ERROR'} and type(size) is int and 0<=size<=512*1024**2 and
          (digest(h) if kind=='AVAILABLE' else h=='' and size==0),'RESTORE_DIAGNOSTIC_LIFECYCLE_DISK')
  return kind,h,size
 def identity(row):return row['guid'],row['localId']
 for sequence,snapshot in enumerate(snapshots):
  require(type(snapshot) is dict and set(snapshot)==keys and type(snapshot['sequence']) is int and snapshot['sequence']==sequence and snapshot['stage'] in ASSET_LIFECYCLE_STAGES and snapshot['stage'] not in stages and ASSET_LIFECYCLE_ORDER.index(snapshot['stage'])>stage_index and
          (sequence!=0 or snapshot['stage']=='RESTORATION_ENTRY') and type(snapshot['preexistingBaseline']) is bool and snapshot['preexistingBaseline']==(not has_baseline), 'RESTORE_DIAGNOSTIC_LIFECYCLE_SEQUENCE')
  stages.add(snapshot['stage']);stage_index=ASSET_LIFECYCLE_ORDER.index(snapshot['stage'])
  require(type(snapshot['captureGateBound']) is bool and (snapshot['captureGateBound'] or not gate_bound) and
          (snapshot['captureGateBound']==gate_bound or snapshot['stage']=='CAPTURE_GATE_BEFORE'),'RESTORE_DIAGNOSTIC_LIFECYCLE_GATE_BINDING')
  gate_bound=snapshot['captureGateBound']
  require(type(snapshot['declaredDependencyCount']) is int and snapshot['declaredDependencyCount']==len(expected) and all(type(snapshot[k]) is int and 0<=snapshot[k]<=8192 for k in counts),'RESTORE_DIAGNOSTIC_LIFECYCLE_COUNTS')
  arrays=('dirtyDependencies','clearedDependencies','unobservedDependencies','diskChanges')
  require(all(type(snapshot[k]) is list and len(snapshot[k])<=8192 for k in arrays),'RESTORE_DIAGNOSTIC_LIFECYCLE_ROWS')
  require(snapshot['status'] in {'CAPTURED','FAILED'} and snapshot['errorCode'] in {'NONE','IO','UNAUTHORIZED','VALIDATION','OTHER'} and
          (snapshot['errorCode']=='NONE')==(snapshot['status']=='CAPTURED'),'RESTORE_DIAGNOSTIC_LIFECYCLE_STATUS')
  if snapshot['status']=='FAILED':
   require(all(snapshot[k]==0 for k in counts) and all(snapshot[k]==[] for k in arrays),'RESTORE_DIAGNOSTIC_LIFECYCLE_FAILED');continue
  for name in ('dirtyDependencies','clearedDependencies','unobservedDependencies'):
   require(all(type(row) is dict and row.get('path') in expected for row in snapshot[name]),'RESTORE_DIAGNOSTIC_LIFECYCLE_OBJECT_PATH')
   for row in snapshot[name]:
    observed.add(row['path'])
    if row['path']+'.meta' in expected:observed.add(row['path']+'.meta')
  require(snapshot['observedPathCount']==len(observed),'RESTORE_DIAGNOSTIC_LIFECYCLE_COVERAGE')
  seen_disk=set()
  for row in snapshot['diskChanges']:
   require(type(row) is dict and set(row)=={'path','beforeState','beforeSha256','beforeBytes','afterState','afterSha256','afterBytes'} and row['path'] in observed and row['path'] not in seen_disk,'RESTORE_DIAGNOSTIC_LIFECYCLE_DISK_PATH')
   name=row['path'];seen_disk.add(name)
   before=state(row['beforeState'],row['beforeSha256'],row['beforeBytes']);after=state(row['afterState'],row['afterSha256'],row['afterBytes'])
   require(before==disk[name] and before!=after and ((after[0]=='BUILTIN')==(name in BUILTIN_DEPENDENCIES)),'RESTORE_DIAGNOSTIC_LIFECYCLE_DISK_CHAIN');disk[name]=after
  require(snapshot['diskMismatchCount']==sum(disk[p]!=original[p] for p in observed) and snapshot['diskUnavailableCount']==sum(disk[p][0] not in {'AVAILABLE','BUILTIN'} for p in observed),'RESTORE_DIAGNOSTIC_LIFECYCLE_DISK_COUNTS')
  current={};removed=set()
  for array,dirty,transitions in [('dirtyDependencies','DIRTY',{'PREEXISTING'} if not has_baseline else {'ENTERED','RETAINED'}),('clearedDependencies','CLEAN',{'CLEARED'}),('unobservedDependencies','NOT_OBSERVED',{'UNOBSERVED'})]:
   for row in snapshot[array]:
    require(type(row) is dict and set(row)==row_keys and row['path'] in expected and not row['path'].endswith('.meta') and isinstance(row['type'],str) and len(row['type'])<=256 and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.+`]*',row['type']) and
            row['identityState'] in {'RESOLVED','UNAVAILABLE'} and type(row['localId']) is int and -(2**63)<=row['localId']<2**63 and
            (digest(row['guid'],32) if row['identityState']=='RESOLVED' else row['guid']=='' and row['localId']==0) and row['dirty']==dirty and row['transition'] in transitions,'RESTORE_DIAGNOSTIC_LIFECYCLE_OBJECT')
    require(row['captureGateMembership'] in ({'INCLUDED','EXCLUDED'} if gate_bound else {'UNKNOWN'}),'RESTORE_DIAGNOSTIC_LIFECYCLE_GATE_MEMBERSHIP')
    if gate_bound:
     require(gate_membership.get(row['path'],row['captureGateMembership'])==row['captureGateMembership'],'RESTORE_DIAGNOSTIC_LIFECYCLE_GATE_MEMBERSHIP');gate_membership[row['path']]=row['captureGateMembership']
    require(state(row['diskState'],row['sha256'],row['bytes'])==disk[row['path']],'RESTORE_DIAGNOSTIC_LIFECYCLE_OBJECT_DISK')
    key=identity(row)
    # Unavailable Unity identities remain visible, including duplicate path/type objects; never invent a stable key.
    if row['identityState']=='RESOLVED':
     context=(row['path'],row['type']);require(identity_context.get(key,context)==context,'RESTORE_DIAGNOSTIC_LIFECYCLE_IDENTITY_CHANGED');identity_context[key]=context
     require(key not in current and key not in removed,'RESTORE_DIAGNOSTIC_LIFECYCLE_DUPLICATE')
     if dirty=='DIRTY':
      require(row['transition']==('PREEXISTING' if not has_baseline else 'RETAINED' if key in previous else 'ENTERED'),'RESTORE_DIAGNOSTIC_LIFECYCLE_TRANSITION');current[key]=row
     else:
      require(key in previous,'RESTORE_DIAGNOSTIC_LIFECYCLE_TRANSITION');removed.add(key)
  require(set(previous)-set(current)==removed,'RESTORE_DIAGNOSTIC_LIFECYCLE_LOST_OBJECT')
  rows=snapshot['dirtyDependencies']
  require(snapshot['captureGateObjectCount']==sum(row['captureGateMembership']=='INCLUDED' and row['identityState']=='RESOLVED' for row in rows) and snapshot['objectCount']==len(rows) and snapshot['distinctPathCount']==len({r['path'] for r in rows}) and
          snapshot['enteredDirtyCount']==sum(r['transition']=='ENTERED' for r in rows) and snapshot['retainedDirtyCount']==sum(r['transition']=='RETAINED' for r in rows) and
          snapshot['clearedCount']==len(snapshot['clearedDependencies']) and snapshot['unobservedCount']==len(snapshot['unobservedDependencies']),'RESTORE_DIAGNOSTIC_LIFECYCLE_COUNTS')
  previous=current;has_baseline=True

def bounded_native_diagnostic(value):
 keys={'schema','label','sourceCommit','producerRunUrl','stage','completed','importerIdentities','dependencyDifferences','errorClass','dependencyExpectedCount','dependencyActualCount','dependencyAddedCount','dependencyMissingCount','runIdentity','consumerIdentityMatched'}
 require(type(value) is dict and type(value.get('schema')) is int and value['schema'] in {1,2},'RESTORE_DIAGNOSTIC_SCHEMA')
 if value['schema']==2:keys.add('assetLifecycle')
 require(set(value)==keys and value['label']=='RESTORATION_NATIVE_DIAGNOSTIC_ONLY' and value['stage'] in DIAGNOSTIC_STAGES and type(value['completed']) is bool and value['errorClass'] in DIAGNOSTIC_ERRORS,'RESTORE_DIAGNOSTIC_SCHEMA')
 require(type(value['consumerIdentityMatched']) is bool and value['runIdentity'] in {'UNVALIDATED','MISSING','DUPLICATE','MALFORMED','MISMATCH','MATCHED'},'RESTORE_DIAGNOSTIC_IDENTITY_STATE')
 if value['consumerIdentityMatched']:
  require(value['sourceCommit']==os.environ['GITHUB_SHA'] and value['producerRunUrl']==current_run() and value['runIdentity']=='MATCHED','RESTORE_DIAGNOSTIC_CONSUMER')
 else:
  # An identity failure remains visibly unauthenticated native evidence, inside the separately host-bound failure receipt.
  # It cannot supply a successful proof, URL fallback, assets or a build capability.
  require(value['sourceCommit'] in ('',os.environ['GITHUB_SHA']) and value['producerRunUrl']=='' and value['completed'] is False and value['stage']=='INPUT' and
          value['importerIdentities']==[] and value['dependencyDifferences']==[] and all(value[k]==0 for k in ('dependencyExpectedCount','dependencyActualCount','dependencyAddedCount','dependencyMissingCount')),'RESTORE_DIAGNOSTIC_UNBOUND_IDENTITY')
  require(value['errorClass']!='NONE' and (value['runIdentity'] not in {'MISSING','DUPLICATE','MALFORMED','MISMATCH'} or value['errorClass']=='RUN_ID_ARGUMENT'),'RESTORE_DIAGNOSTIC_IDENTITY_ERROR')
 require(all(type(value[k]) is int and 0<=value[k]<=8192 for k in ('dependencyExpectedCount','dependencyActualCount','dependencyAddedCount','dependencyMissingCount')) and value['dependencyActualCount']-value['dependencyExpectedCount']==value['dependencyAddedCount']-value['dependencyMissingCount'],'RESTORE_DIAGNOSTIC_COUNTS')
 require(isinstance(value['importerIdentities'],list) and len(value['importerIdentities'])<=3 and len({x['kind'] for x in value['importerIdentities']})==len(value['importerIdentities']),'RESTORE_DIAGNOSTIC_IMPORTERS')
 selected=read(ROOT/SELECTION)['sources'];paths={x['kind']:'Assets/DesertRV/CandidateArtImports/'+read(ROOT/x['contract'])['id']+'/Candidate.prefab' for x in selected}
 for row in value['importerIdentities']:
  require(set(row)=={'kind','path','producerDependencyHash','currentDependencyHash','producerDependencySha256','currentDependencySha256'} and row['kind'] in paths and row['path']==paths[row['kind']] and all(digest(row[k],32 if k.endswith('Hash') else 64) for k in ('producerDependencyHash','currentDependencyHash','producerDependencySha256','currentDependencySha256')),'RESTORE_DIAGNOSTIC_IMPORTER_PIN')
 rows=value['dependencyDifferences'];require(isinstance(rows,list) and len(rows)<=32 and len({x['path'] for x in rows})==len(rows),'RESTORE_DIAGNOSTIC_DIFFS')
 if rows:
  receipt=read(PUBLIC/'generated/receipt.json');require(sha(PUBLIC/'generated/receipt.json')==PRODUCER['generatedReceiptSha256'],'RESTORE_DIAGNOSTIC_ORIGINAL_RECEIPT')
  native_path=PUBLIC/'generated/native-authored-assets.json';require(sha(native_path)==receipt['nativeManifestSha256'],'RESTORE_DIAGNOSTIC_ORIGINAL_MANIFEST')
  expected={x['path']:x for x in read(native_path)['dependencies']}
  for row in rows:
   require(set(row)=={'path','producerSha256','currentSha256','producerBytes','currentBytes'} and row['path'] in expected,'RESTORE_DIAGNOSTIC_DIFF_PATH')
   old=expected[row['path']]
   require(row['producerSha256']==old['sha256'] and row['producerBytes']==old['bytes'] and (digest(row['currentSha256']) or row['currentSha256']=='' and row['currentBytes']==0) and type(row['currentBytes']) is int and 0<=row['currentBytes']<=128*1024**2,'RESTORE_DIAGNOSTIC_DIFF_PIN')
 if value['schema']==2:bounded_asset_lifecycle(value)
 return value

def diagnose():
 # A failure has no reusable proof. Export fixed status and strictly projected public identities only.
 if EXPORT.exists():
  receipt=read(EXPORT/'receipt.json');require(receipt.get('status')==(DERIVED_LABEL if ANDROID else REPORT_LABEL),'RESTORE_EXISTING_PUBLIC_STATUS')
  verify_staged_inventory(EXPORT,receipt['files'],sha(EXPORT/'receipt.json'))
 else:
  status=dict(command='none',errorCode='NATIVE_OR_PREFLIGHT_NOT_READY')
  if HOST_STATUS.exists():
   candidate=read(HOST_STATUS)
   if set(candidate)=={'command','errorCode'} and candidate['command'] in {'stage','verify-assets','verify-boundary','finish','verify'} and re.fullmatch('[A-Z][A-Z0-9_]{0,100}',candidate['errorCode']):status=candidate
  files=[];diagnostic=None
  if DIAGNOSTIC.exists():
   try:
    require(DIAGNOSTIC.stat().st_size<=512*1024,'RESTORE_DIAGNOSTIC_SIZE');candidate=read(DIAGNOSTIC)
    require(DIAGNOSTIC.stat().st_size<=(512 if candidate.get('schema')==2 else 128)*1024,'RESTORE_DIAGNOSTIC_SIZE')
    require(candidate.get('schema')==(2 if ANDROID else 1),'RESTORE_DIAGNOSTIC_CURRENT_SCHEMA')
    validated=bounded_native_diagnostic(candidate)
    require(len((json.dumps(validated,indent=2)+'\n').encode('utf-8'))<=(512 if validated['schema']==2 else 128)*1024,'RESTORE_DIAGNOSTIC_SIZE')
    diagnostic=validated
   except Exception as error:status=dict(command='finish',errorCode='RESTORE_DIAGNOSTIC_SIZE' if str(error)=='RESTORE_DIAGNOSTIC_SIZE' else 'DIAGNOSTIC_SCHEMA_REJECTED')
  EXPORT.mkdir()
  if diagnostic is not None:
   write_fresh(EXPORT/'native-diagnostic.json',diagnostic);files.append(generated.record(EXPORT/'native-diagnostic.json','native-diagnostic.json'))
  if ANDROID:
   try:files.extend(export_material_diagnostic())
   except Exception as error:status=dict(command='finish',errorCode=str(error) if re.fullmatch('[A-Z][A-Z0-9_]{0,100}',str(error)) else 'DERIVE_MATERIAL_DIAGNOSTIC_REJECTED')
  receipt=dict(schema=1,status='RESTORATION_NOT_READY',sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),assetProducer=PRODUCER,approved=False,scopeReusable=False,buildReady=False,failure=status,files=files)
  write_fresh(EXPORT/'receipt.json',receipt);verify_staged_inventory(EXPORT,files,sha(EXPORT/'receipt.json'))
 if os.environ.get('GITHUB_OUTPUT'):
  with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('export_ready=true\n')
 return receipt

def main():
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['stage','verify-assets','verify-boundary','finish','verify','diagnose']);parser.add_argument('--policy-sha256');parser.add_argument('--native',choices=['success','failure','cancelled','skipped']);args=parser.parse_args()
 try:
  guard()
  if args.command=='stage':stage(args.policy_sha256)
  elif args.command=='verify-assets':verify_assets()
  elif args.command=='verify-boundary':verify_boundary()
  elif args.command=='finish':finish(args.native)
  elif args.command=='diagnose':diagnose()
  else:verify()
 except Exception as error:
  code=str(error) if re.fullmatch('[A-Z][A-Z0-9_]{0,100}',str(error)) else ('IO_ERROR' if isinstance(error,OSError) else 'VALIDATION_ERROR')
  print('JOURNEY_RESTORATION_NOT_READY: '+code)
  if args.command!='diagnose':HOST_STATUS.write_text(json.dumps(dict(command=args.command,errorCode=code))+'\n')
  return 1
 return 0
if __name__=='__main__':raise SystemExit(main())
