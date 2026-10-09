"""Restore one verified public Journey producer; old scopes never authorize a new build."""
import argparse,base64,hashlib,json,os,re,shutil,stat,subprocess,sys,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[4];TASK=ROOT/'tasks/desert-rv';PROJECT=TASK/'unity'
PRIVATE=PROJECT/'JourneyEvidence/JourneyPreparation';PUBLIC=TASK/'journey-preparation-export'
POLICY='tasks/desert-rv/art/journey-preparation/restoration-transition.json'
STATE=PRIVATE/'restoration-state.json';SOURCE_PROOF=PRIVATE/'restoration-source-proof.json'
INPUT=PRIVATE/'restoration-input.json';REPORT=PRIVATE/'restoration-revalidated.json';VERIFIED=PRIVATE/'restoration-native-verified.json'
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
RUN_URL='https://github.com/yangerstar1/task-workbench/actions/runs/'+str(PRODUCER['runId'])
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

def pin(path):return dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
def write_fresh(path,value):
 require(not path.exists(),'RESTORE_OUTPUT_EXISTS');path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
def source_transition(policy,before,after,policy_sha):
 require(set(policy)=={'schema','status','producer','changes'} and type(policy['schema']) is int and policy['schema']==1 and policy['status']=='REVIEWED_DIAGNOSTIC_RESTORATION_SOURCE_ONLY' and policy['producer']==PRODUCER,'RESTORE_POLICY_IDENTITY')
 require(digest(policy_sha) and isinstance(policy['changes'],list),'RESTORE_POLICY_HASH')
 require(before['restoredFiles']==after['restoredFiles'] and before['coverageRoots']==after['coverageRoots'],'RESTORE_SOURCE_DOMAIN_CHANGED')
 expected_coverage=before['coverageFiles']+['.github/workflows/desert-rv-journey-rebuild.yml']
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
         run.get('status')=='completed' and run.get('head_branch')=='main' and run.get('event')=='workflow_dispatch' and
         run.get('path')=='.github/workflows/desert-rv-journey-prepare.yml','RESTORE_PRODUCER_RUN')
 require(artifact.get('id')==PRODUCER['artifactId'] and artifact.get('name')==PRODUCER['artifactName'] and artifact.get('expired') is False and
         artifact.get('size_in_bytes')==PRODUCER['artifactBytes'] and artifact.get('digest')=='sha256:'+PRODUCER['artifactSha256'] and
         artifact.get('workflow_run',{}).get('id')==PRODUCER['runId'] and artifact['workflow_run'].get('head_sha')==PRODUCER['sourceCommit'],'RESTORE_PRODUCER_ARTIFACT')
 candidates=[j for j in jobs.get('jobs',[]) if j.get('name')=='prepare' and j.get('run_id')==PRODUCER['runId'] and j.get('status')=='completed']
 require(len(candidates)==1,'RESTORE_PRODUCER_JOB')
 steps={s['number']:s for s in candidates[0]['steps']}
 required={7:'Native strict armored import and actual capture',8:'Reuse exact strict quality gate and preserve armored reports',10:'Native strict pouncer import and actual capture',11:'Reuse exact strict quality gate and preserve pouncer reports',13:'Native strict weapon import and actual capture',14:'Reuse exact strict quality gate and preserve weapon reports',15:'Require exact three-candidate union and freeze real selections',16:'Native exact candidate Linux boundary tests',17:'Require exact seventeen passing candidate boundary cases',18:'Native original FX, four scenes, integration and diagnostic scope',19:'Verify actual preparation test, saved outputs and final scope pins'}
 require(all(steps.get(n,{}).get('name')==name and steps[n].get('conclusion')=='success' for n,name in required.items()),'RESTORE_PRODUCER_AUTHORING_NOT_PASSED')
 # A later Linux failure does not rewrite the actual successful producer stages.

def extract_original(zip_path,destination):
 require(sha(zip_path)==PRODUCER['artifactSha256'] and zip_path.stat().st_size==PRODUCER['artifactBytes'] and not destination.exists(),'RESTORE_ZIP_IDENTITY')
 with zipfile.ZipFile(zip_path) as archive:
  rows=archive.infolist();require(len(rows)==len({x.filename for x in rows}) and sum(x.file_size for x in rows)<=256*1024**2,'RESTORE_ZIP_BOUNDS')
  for row in rows:
   p=PurePosixPath(row.filename);require(not p.is_absolute() and p.parts and '..' not in p.parts and p.as_posix()==row.filename.rstrip('/') and '\\' not in row.filename and not stat.S_ISLNK(row.external_attr>>16) and (stat.S_IFMT(row.external_attr>>16) in (0,stat.S_IFREG,stat.S_IFDIR)),'RESTORE_ZIP_PATH')
  archive.extractall(destination)

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
 return dict(schema=1,label=INPUT_LABEL,sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),assetProducerSourceCommit=PRODUCER['sourceCommit'],assetProducerRunUrl=RUN_URL,
  generatedReceiptSha256=PRODUCER['generatedReceiptSha256'],sourceTransitionProof=pin(SOURCE_PROOF),selection=pin(ROOT/SELECTION),
  originalGeneratedReceipt=pin(PUBLIC/'generated/receipt.json'),originalNativeManifest=pin(PUBLIC/'generated/native-authored-assets.json'),originalGrounding=pin(PUBLIC/'generated'/generated.GROUND_EXPORT),
  files=[records[n] for n in sorted(records)],integration=integration,expectedDependencies=bundle['native']['dependencies'],
  directories=sorted(name+'/'+d for name in ('Assets','Packages','ProjectSettings') for d in directories(PROJECT/name)))

def restore_assets(bundle):
 # Exact new Assets only. Never copy Library, private snapshots, old scope, packages or Settings.
 for name,path in sorted(bundle['paths'].items()):
  target=PROJECT/name;require(rel(name) and name.startswith('Assets/') and not target.exists() and not target.is_symlink(),'RESTORE_ASSET_COLLISION')
  require(not any(p.is_symlink() for p in target.parents),'RESTORE_ASSET_PARENT_SYMLINK')
  target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
  require(sha(target)==bundle['assets'][name],'RESTORE_ASSET_COPY_CHANGED')

def stage(policy_sha):
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
 write_fresh(STATE,dict(schema=1,sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),initialIdentity=identity,initialSourceDirectories=initial_dirs,addedAssets=bundle['assets'],publicFiles=public_pins,policySha256=policy_sha,sourceProof=pin(SOURCE_PROOF),input=pin(INPUT),producerSource=pin(PRODUCER_SOURCE)))
 verify_assets();print('JOURNEY_RESTORED_BYTES_AWAIT_FRESH_NATIVE_REVALIDATION')

def verify_assets():
 s=read(STATE);require(s['schema']==1 and s['sourceCommit']==os.environ['GITHUB_SHA'] and s['producerRunUrl']==current_run(),'RESTORE_CONSUMER_IDENTITY')
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
 require(set(report)==REPORT_KEYS and type(report['schema']) is int and report['schema']==1 and report['label']==REPORT_LABEL and report['sourceCommit']==os.environ['GITHUB_SHA'] and report['producerRunUrl']==current_run() and report['assetProducerSourceCommit']==PRODUCER['sourceCommit'] and report['assetProducerRunUrl']==RUN_URL and report['generatedReceiptSha256']==PRODUCER['generatedReceiptSha256'] and report['sourceTransitionProof']==pin(SOURCE_PROOF) and report['requestSha256']==sha(INPUT) and report['unityVersion']==generated.UNITY,'RESTORE_NATIVE_REPORT_IDENTITY')
 require(all(report[k] is True for k in ('sourceBytesUnchanged','originalAssetsUnchanged','structureValidated','productionApprovalRejected')) and report['approved'] is False and report['scopeReused'] is False,'RESTORE_NATIVE_REPORT_NOT_READY')
 original_outputs={r['path']:r for r in bundle['receipt']['integrationOutputs']};scenes=report['scenes']
 require(len(scenes)==5 and len({r['path'] for r in scenes})==5 and {r['path'] for r in scenes}==set(original_outputs),'RESTORE_NATIVE_SCENE_SET')
 for row in scenes:require(set(row)=={'path','sha256','dependencyHash','dependencySha256'} and row['sha256']==original_outputs[row['path']]['sha256']==sha(PROJECT/row['path']) and digest(row['dependencyHash'],32) and digest(row['dependencySha256']),'RESTORE_NATIVE_SCENE_PIN')
 # Approved changes are Editor/entry diagnostics only. Actual dependency byte closure stays exact.
 require(report['dependencies']==bundle['native']['dependencies'],'RESTORE_NATIVE_DEPENDENCY_BYTES_CHANGED')
 check_grounding(report['grounding'],read(ROOT/SELECTION),os.environ['GITHUB_SHA'],sha(ROOT/SELECTION),sha(INPUT))
 require(len(report['grounding']['rows'])==len(bundle['ground']['rows']),'RESTORE_NATIVE_GROUNDING_CHANGED')
 oldrows={x['id']:x for x in bundle['ground']['rows']}
 for row in report['grounding']['rows']:
  old=oldrows[row['id']];vectors={'declaredPosition','resolvedPosition','hitPoint','hitNormal'}
  require(all(row[k]==old[k] for k in set(row)-vectors) and all(sum((row[k][a]-old[k][a])**2 for a in ('x','y','z'))<1e-10 for k in vectors),'RESTORE_NATIVE_GROUNDING_CHANGED')
 return report

def verify():
 import linux_build_input as linux
 s,bundle=verify_assets();linux.bound_boundary();actual=native_evidence();proof=read(VERIFIED)
 require(proof==dict(schema=1,label='CURRENT_RESTORATION_NATIVE_PASSED',sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),nativeXml=actual,nativeReport=pin(REPORT),sourceProof=pin(SOURCE_PROOF),input=pin(INPUT),boundaryNativeXml=linux.boundary_evidence()['nativeXml']),'RESTORE_NATIVE_PROOF_CHANGED')
 validate_native_report(read(REPORT),bundle)
 return s,bundle,proof

def finish(native):
 import linux_build_input as linux
 require(native=='success','RESTORE_NATIVE_STEP_FAILED');s,bundle=verify_assets();boundary=linux.bound_boundary();xml=native_evidence();report=validate_native_report(read(REPORT),bundle)
 write_fresh(VERIFIED,dict(schema=1,label='CURRENT_RESTORATION_NATIVE_PASSED',sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),nativeXml=xml,nativeReport=pin(REPORT),sourceProof=pin(SOURCE_PROOF),input=pin(INPUT),boundaryNativeXml=boundary['nativeXml']))
 verify();require(not EXPORT.exists(),'RESTORE_PUBLIC_DESTINATION_EXISTS');EXPORT.mkdir()
 evidence=[]
 for path,name in ((REPORT,'native-restoration.json'),(SOURCE_PROOF,'source-transition.json'),(INPUT,'native-input.json')):
  shutil.copyfile(path,EXPORT/name);evidence.append(generated.record(EXPORT/name,name));require(sha(EXPORT/name)==sha(path),'RESTORE_PUBLIC_COPY_CHANGED')
 receipt=dict(schema=1,status=REPORT_LABEL,sourceCommit=os.environ['GITHUB_SHA'],producerRunUrl=current_run(),assetProducer=PRODUCER,generatedReceiptSha256=PRODUCER['generatedReceiptSha256'],nativeXmlSha256=xml['sha256'],boundaryNativeXmlSha256=boundary['nativeXml']['sha256'],nativeCases=1,boundaryNativeCases=17,approved=False,scopeReusable=False,files=evidence)
 write_fresh(EXPORT/'receipt.json',receipt);verify_staged_inventory(EXPORT,evidence,sha(EXPORT/'receipt.json'))
 if os.environ.get('GITHUB_OUTPUT'):
  with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('export_ready=true\n')
 print('JOURNEY_RESTORATION_EXACT_NATIVE_PASSED_UNREVIEWED')

DIAGNOSTIC=PRIVATE/'restoration-diagnostic.json'
HOST_STATUS=TASK/'journey-restoration-status.json'
DIAGNOSTIC_STAGES={'INPUT','INVENTORY','SOURCE_PROOF','STRICT_BUNDLES','DEPENDENCIES','GENERATED_BYTES','SELECTION','POSES','GROUNDING','IMPORTER_IDENTITIES','SAVED_BINDINGS','FINAL_PROTECTION','PROOF','COMPLETED'}
DIAGNOSTIC_ERRORS={'RUN_ID_ARGUMENT','NONE','IMPORTER_IDENTITY','DEPENDENCY_BYTES','VALIDATION','IO','UNAUTHORIZED','OTHER'}
def bounded_native_diagnostic(value):
 keys={'schema','label','sourceCommit','producerRunUrl','stage','completed','importerIdentities','dependencyDifferences','errorClass','dependencyExpectedCount','dependencyActualCount','dependencyAddedCount','dependencyMissingCount','runIdentity','consumerIdentityMatched'}
 require(set(value)==keys and type(value['schema']) is int and value['schema']==1 and value['label']=='RESTORATION_NATIVE_DIAGNOSTIC_ONLY' and value['stage'] in DIAGNOSTIC_STAGES and type(value['completed']) is bool and value['errorClass'] in DIAGNOSTIC_ERRORS,'RESTORE_DIAGNOSTIC_SCHEMA')
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
 return value

def diagnose():
 # A failure has no reusable proof. Export fixed status and strictly projected public identities only.
 if EXPORT.exists():
  receipt=read(EXPORT/'receipt.json');require(receipt.get('status')==REPORT_LABEL,'RESTORE_EXISTING_PUBLIC_STATUS')
  verify_staged_inventory(EXPORT,receipt['files'],sha(EXPORT/'receipt.json'))
 else:
  status=dict(command='none',errorCode='NATIVE_OR_PREFLIGHT_NOT_READY')
  if HOST_STATUS.exists():
   candidate=read(HOST_STATUS)
   if set(candidate)=={'command','errorCode'} and candidate['command'] in {'stage','verify-assets','verify-boundary','finish','verify'} and re.fullmatch('[A-Z][A-Z0-9_]{0,100}',candidate['errorCode']):status=candidate
  files=[];diagnostic=None
  if DIAGNOSTIC.exists():
   try:
    require(DIAGNOSTIC.stat().st_size<=128*1024,'RESTORE_DIAGNOSTIC_SIZE');diagnostic=bounded_native_diagnostic(read(DIAGNOSTIC))
   except Exception:status=dict(command='finish',errorCode='DIAGNOSTIC_SCHEMA_REJECTED')
  EXPORT.mkdir()
  if diagnostic is not None:
   write_fresh(EXPORT/'native-diagnostic.json',diagnostic);files.append(generated.record(EXPORT/'native-diagnostic.json','native-diagnostic.json'))
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
