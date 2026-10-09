"""Closed R4 twenty-view production terrain push fixtures, including actual Git parent/blob/mode checks. No network or dispatch."""
import copy,hashlib,json,os,re,subprocess,tempfile,unittest
from pathlib import Path
from unittest import mock
import environment_v4_r4_dispatch as d

class IdentityTests(unittest.TestCase):
 def setUp(self):
  self.head='a'*40;self.candidate=(d.ROOT/d.CANDIDATE).read_bytes();self.state=b'fixture source state'
  self.env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=d.REPOSITORY,GITHUB_REPOSITORY_VISIBILITY='public',GITHUB_ACTOR=d.OWNER,GITHUB_TRIGGERING_ACTOR=d.OWNER,GITHUB_REF='refs/heads/main',GITHUB_SHA=self.head,GITHUB_RUN_ID='1',GITHUB_RUN_ATTEMPT='1',GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF=d.REPOSITORY+'/'+d.WORKFLOW+'@refs/heads/main')
  self.event=dict(before=d.BASE,after=self.head,ref='refs/heads/main',created=False,deleted=False,forced=False,repository=dict(full_name=d.REPOSITORY,visibility='public',private=False,fork=False,default_branch='main',owner=dict(login=d.OWNER)),sender=dict(login=d.OWNER),head_commit=dict(id=self.head))
  self.manifest=dict(schema=1,requestId=d.REQUEST_ID,baseCommit=d.BASE,candidateManifestSha256=d.CANDIDATE_SHA,files=[dict(path=p,sha256='b'*64,size=12,mode='100644') for p in d.PAYLOAD_PATHS])
  self.request=dict(schema=1,requestId=d.REQUEST_ID,baseCommit=d.BASE,candidateManifestSha256=d.CANDIDATE_SHA,filesManifestSha256=d.sha(json.dumps(self.manifest).encode()),sourceStateSha256=d.sha(self.state))
  self.parents=[d.BASE];self.present=False;self.changed=[i['path'] for i in self.manifest['files']]+[d.REQUEST,d.MANIFEST,d.SOURCE_STATE]
 def check(self,raw=None,tracked=None,manifest=None,candidate=None):
  raw=json.dumps(self.request).encode() if raw is None else raw;manifest=json.dumps(self.manifest).encode() if manifest is None else manifest
  return d.validate_identity(self.env,self.event,self.head,self.parents,raw,raw if tracked is None else tracked,self.present,self.changed,manifest,self.state,self.candidate if candidate is None else candidate)
 def reject(self,code,**kwargs):
  with self.assertRaisesRegex(ValueError,'ENVIRONMENT_V4_R4_DISPATCH_'+code):self.check(**kwargs)
 def test_exact_fixed_push_passes(self):self.assertEqual(self.manifest,self.check())
 def test_manual_event_rejected_not_impersonated(self):self.env['GITHUB_EVENT_NAME']='workflow_dispatch';self.reject('EVENT')
 def test_pull_request_rejected(self):self.env['GITHUB_EVENT_NAME']='pull_request';self.reject('EVENT')
 def test_wrong_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/desert-rv-journey-rebuild.yml@refs/heads/main';self.reject('WORKFLOW')
 def test_rebuild_nonce_rejected(self):self.request['requestId']='desert-rv-rebuild-performance-20261009-once';self.reject('REQUEST_IDENTITY')
 def test_previous_v4_nonce_rejected(self):self.request['requestId']='desert-rv-environment-v4-20261009-once-7f3c2b68';self.reject('REQUEST_IDENTITY')
 def test_previous_v4_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/desert-rv-environment-v4.yml@refs/heads/main';self.reject('WORKFLOW')
 def test_previous_r2_nonce_rejected(self):self.request['requestId']='desert-rv-environment-v4-r2-20261009-once-b871ce26';self.reject('REQUEST_IDENTITY')
 def test_previous_r2_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/desert-rv-environment-v4-r2.yml@refs/heads/main';self.reject('WORKFLOW')
 def test_discovery_nonce_rejected(self):self.request['requestId']='armored-v004-r1-discovery-20261009-once-69a502dd';self.reject('REQUEST_IDENTITY')
 def test_discovery_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/desert-rv-armored-v004-r1-discovery.yml@refs/heads/main';self.reject('WORKFLOW')
 def test_previous_r3_nonce_rejected(self):self.request['requestId']='desert-rv-environment-v4-r3-20261009-once-58ad490e';self.reject('REQUEST_IDENTITY')
 def test_previous_r3_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/desert-rv-environment-v4-r3.yml@refs/heads/main';self.reject('WORKFLOW')
 def test_previous_comparison_nonce_rejected(self):self.request['requestId']='desert-rv-environment-diffuse-comparison-20261009-once-a643e92d';self.reject('REQUEST_IDENTITY')
 def test_previous_comparison_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/desert-rv-environment-diffuse-comparison.yml@refs/heads/main';self.reject('WORKFLOW')
 def test_previous_probe_nonce_rejected(self):self.request['requestId']='desert-rv-environment-terrain-probe-20261009-once-68d50a31';self.reject('REQUEST_IDENTITY')
 def test_previous_probe_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/desert-rv-environment-terrain-probe.yml@refs/heads/main';self.reject('WORKFLOW')
 def test_strict_nonce_rejected(self):self.request['requestId']='armored-v004-r1-strict-20261009-once-c8521e4b';self.reject('REQUEST_IDENTITY')
 def test_strict_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/desert-rv-armored-v004-r1-strict.yml@refs/heads/main';self.reject('WORKFLOW')
 def test_previous_comparison_r1_nonce_rejected(self):self.request['requestId']='desert-rv-environment-diffuse-comparison-r1-20261009-once-c91b7f42';self.reject('REQUEST_IDENTITY')
 def test_previous_comparison_r1_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main';self.reject('WORKFLOW')
 def test_wrong_parent_rejected(self):self.parents=['c'*40];self.reject('PARENT')
 def test_merge_parent_rejected(self):self.parents.append('c'*40);self.reject('PARENT')
 def test_wrong_before_rejected(self):self.event['before']='c'*40;self.reject('PUSH_IDENTITY')
 def test_wrong_after_rejected(self):self.event['after']='c'*40;self.reject('PUSH_IDENTITY')
 def test_wrong_head_rejected(self):self.env['GITHUB_SHA']='c'*40;self.reject('HEAD')
 def test_wrong_head_commit_rejected(self):self.event['head_commit']['id']='c'*40;self.reject('PUSH_AUTHOR')
 def test_wrong_sender_rejected(self):self.event['sender']['login']='other';self.reject('PUSH_AUTHOR')
 def test_wrong_actor_rejected(self):self.env['GITHUB_ACTOR']='other';self.reject('ACTOR')
 def test_wrong_triggering_actor_rejected(self):self.env['GITHUB_TRIGGERING_ACTOR']='other';self.reject('ACTOR')
 def test_wrong_branch_rejected(self):self.env['GITHUB_REF']='refs/heads/art';self.reject('BRANCH')
 def test_wrong_repo_rejected(self):self.env['GITHUB_REPOSITORY']='x/y';self.reject('REPOSITORY')
 def test_missing_environment_visibility_rejected(self):self.env.pop('GITHUB_REPOSITORY_VISIBILITY');self.reject('REPOSITORY')
 def test_private_environment_visibility_rejected(self):self.env['GITHUB_REPOSITORY_VISIBILITY']='private';self.reject('REPOSITORY')
 def test_private_payload_visibility_with_public_environment_rejected(self):self.event['repository']['visibility']='private';self.reject('PUSH_REPOSITORY')
 def test_absent_payload_visibility_with_public_environment_rejected(self):self.event['repository'].pop('visibility');self.reject('PUSH_REPOSITORY')
 def test_private_repo_rejected(self):self.event['repository']['private']=True;self.reject('PUSH_REPOSITORY')
 def test_fork_repo_rejected(self):self.event['repository']['fork']=True;self.reject('PUSH_REPOSITORY')
 def test_wrong_default_branch_rejected(self):self.event['repository']['default_branch']='dev';self.reject('PUSH_REPOSITORY')
 def test_attempt_two_rejected(self):self.env['GITHUB_RUN_ATTEMPT']='2';self.reject('REPLAY')
 def test_created_deleted_forced_rejected(self):
  for key in ['created','deleted','forced']:
   self.event[key]=True;self.reject('PUSH_KIND');self.event[key]=False
 def test_prior_request_rejected(self):self.present=True;self.reject('REQUEST_GIT')
 def test_request_bytes_tamper_rejected(self):self.reject('REQUEST_GIT',tracked=b'other')
 def test_candidate_pin_rejected(self):self.reject('CANDIDATE_PIN',candidate=b'other')
 def test_manifest_pin_rejected(self):self.request['filesManifestSha256']='c'*64;self.reject('REQUEST_PIN')
 def test_source_state_pin_rejected(self):self.request['sourceStateSha256']='c'*64;self.reject('REQUEST_PIN')
 def test_extra_changed_path_rejected(self):self.changed.append('arbitrary.py');self.reject('CHANGED_SET')
 def test_missing_changed_path_rejected(self):self.changed.remove(d.SOURCE_STATE);self.reject('CHANGED_SET')
 def test_duplicate_changed_path_rejected(self):self.changed.append(d.REQUEST);self.reject('CHANGED_SET')
 def test_extra_request_command_rejected(self):self.request['command']='build anything';self.reject('REQUEST_KEYS')
 def test_wrong_request_base_rejected(self):self.request['baseCommit']='c'*40;self.reject('REQUEST_IDENTITY')
 def test_bool_schema_rejected(self):self.request['schema']=True;self.reject('REQUEST_IDENTITY')
 def test_duplicate_json_key_rejected(self):self.reject('DUPLICATE_KEY',raw=b'{"schema":1,"schema":1}')
 def test_bad_json_rejected(self):self.reject('BAD_JSON',raw=b'{')
 def test_nonfinite_json_rejected(self):self.reject('JSON_CONSTANT',raw=b'{"schema":NaN}')
 def test_oversized_request_rejected(self):self.reject('JSON_SIZE',raw=b' '*4097)
 def test_extra_manifest_command_rejected(self):self.manifest['command']='x';self.reject('MANIFEST_KEYS')
 def test_manifest_symlink_mode_rejected(self):self.manifest['files'][0]['mode']='120000';self.reject('FILE_IDENTITY')
 def test_manifest_submodule_mode_rejected(self):self.manifest['files'][0]['mode']='160000';self.reject('FILE_IDENTITY')
 def test_manifest_absolute_path_rejected(self):self.manifest['files'][0]['path']='/tmp/a';self.reject('FILE_PATH')
 def test_manifest_traversal_rejected(self):self.manifest['files'][0]['path']='tasks/../secret';self.reject('FILE_PATH')
 def test_manifest_duplicate_file_rejected(self):self.manifest['files'].append(self.manifest['files'][0]);self.reject('FILE_PATH')
 def test_manifest_circular_control_file_rejected(self):self.manifest['files'][0]['path']=d.SOURCE_STATE;self.reject('FILE_PATH')
 def test_manifest_oversized_file_rejected(self):self.manifest['files'][0]['size']=40*1024*1024+1;self.reject('FILE_IDENTITY')
 def test_wrong_manifest_identity_rejected(self):self.manifest['requestId']='rebuild';self.reject('MANIFEST_IDENTITY')

 def test_manifest_extra_valid_path_rejected(self):self.manifest['files'].append(dict(path='tasks/arbitrary.py',sha256='b'*64,size=1,mode='100644'));self.reject('PAYLOAD_SET')
 def test_manifest_missing_candidate_path_rejected(self):self.manifest['files']=[r for r in self.manifest['files'] if r['path']!=d.CANDIDATE];self.reject('PAYLOAD_SET')
 def test_manifest_substituted_valid_path_rejected(self):
  next(r for r in self.manifest['files'] if r['path']==d.CANDIDATE)['path']='tasks/substitute.json';self.reject('PAYLOAD_SET')
 def test_manifest_request_hash_cycle_rejected(self):self.manifest['files'][0]['path']=d.REQUEST;self.reject('FILE_PATH')
 def test_manifest_self_hash_cycle_rejected(self):self.manifest['files'][0]['path']=d.MANIFEST;self.reject('FILE_PATH')

class WorkflowEnvironmentTests(unittest.TestCase):
 """Read the real workflow job-env bridge; do not invent it inside the helper fixture."""
 def setUp(self):
  self.fixture=IdentityTests();self.fixture.setUp()
  self.workflow=(d.ROOT/d.WORKFLOW).read_text()
 def environment(self,text=None,event=None):
  text=self.workflow if text is None else text;event=self.fixture.event if event is None else event
  match=re.search(r'^    env:\n((?:      .*\n)+)',text,re.M)
  if not match:raise ValueError('WORKFLOW_JOB_ENV_MISSING')
  values=dict(re.findall(r'^      ([A-Z_]+): (.+)$',match.group(1),re.M))
  if values!={'GITHUB_REPOSITORY_VISIBILITY':'${{ github.event.repository.visibility }}'}:raise ValueError('WORKFLOW_JOB_ENV_CONTEXT')
  defaults={k:v for k,v in self.fixture.env.items() if k!='GITHUB_REPOSITORY_VISIBILITY'}
  defaults.update(GITHUB_EVENT_PATH='event.json',GITHUB_OUTPUT='step-output')
  defaults['GITHUB_REPOSITORY_VISIBILITY']=event.get('repository',{}).get('visibility','')
  return defaults
 def test_real_workflow_context_supplies_helper_visibility(self):
  self.fixture.event['repository']['visibility']='public';self.fixture.env=self.environment();self.assertEqual(self.fixture.manifest,self.fixture.check())
 def test_missing_real_workflow_bridge_is_not_assumed(self):
  removed=self.workflow.replace('    env:\n      GITHUB_REPOSITORY_VISIBILITY: ${{ github.event.repository.visibility }}\n','')
  with self.assertRaisesRegex(ValueError,'WORKFLOW_JOB_ENV_MISSING'):self.environment(removed)
 def test_wrong_context_expression_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'WORKFLOW_JOB_ENV_CONTEXT'):self.environment(self.workflow.replace('github.event.repository.visibility','github.repository.visibility'))
 def test_private_actual_payload_bridge_fails_identity(self):
  self.fixture.event['repository']['visibility']='private';self.fixture.env=self.environment();self.fixture.reject('REPOSITORY')
 def test_absent_payload_visibility_does_not_default_public(self):
  self.fixture.event['repository'].pop('visibility',None);self.fixture.env=self.environment();self.fixture.reject('REPOSITORY')
 def test_every_helper_variable_has_verified_provider(self):
  # GitHub official default-variable reference checked 2026-10-09:
  # https://docs.github.com/en/actions/reference/workflows-and-actions/variables
  documented_defaults={'GITHUB_ACTIONS','GITHUB_ACTOR','GITHUB_EVENT_NAME','GITHUB_EVENT_PATH','GITHUB_OUTPUT','GITHUB_REF','GITHUB_REPOSITORY','GITHUB_RUN_ATTEMPT','GITHUB_RUN_ID','GITHUB_SHA','GITHUB_TRIGGERING_ACTOR','GITHUB_WORKFLOW_REF'}
  helper=Path(d.__file__).read_text()
  actual=set(re.findall(r"(?:env.get\(|os.environ\[)'([A-Z_]+)'",helper))
  self.assertEqual(actual,documented_defaults|{'GITHUB_REPOSITORY_VISIBILITY'})
  self.fixture.event['repository']['visibility']='public';provided=self.environment()
  self.assertTrue(actual<=set(provided))

class RealGitTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.git('init');self.git('config','user.name','Local Fixture');self.git('config','user.email','fixture@example.invalid')
  (self.root/'baseline').write_text('immutable base');self.git('add','.');self.git('commit','-m','fixture base');self.base=self.git('rev-parse','HEAD')
  self.payloads={p:((d.ROOT/d.CANDIDATE).read_bytes() if p==d.CANDIDATE else ('fixture '+p).encode()) for p in d.PAYLOAD_PATHS}
  for path,raw in self.payloads.items():p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
  manifest=dict(schema=1,requestId=d.REQUEST_ID,baseCommit=self.base,candidateManifestSha256=d.CANDIDATE_SHA,files=[dict(path=p,sha256=d.sha(raw),size=len(raw),mode='100644') for p,raw in sorted(self.payloads.items())])
  manifest_raw=(json.dumps(manifest,indent=2)+'\n').encode();self.manifest_sha=d.sha(manifest_raw)
  self.write(d.MANIFEST,manifest_raw);self.write(d.SOURCE_STATE,b'fixture state')
  request=dict(schema=1,requestId=d.REQUEST_ID,baseCommit=self.base,candidateManifestSha256=d.CANDIDATE_SHA,filesManifestSha256=self.manifest_sha,sourceStateSha256=d.sha(b'fixture state'))
  self.write(d.REQUEST,(json.dumps(request,indent=2)+'\n').encode());self.git('add','.');self.git('commit','-m','fixture V4 exact publication')
  self.env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=d.REPOSITORY,GITHUB_REPOSITORY_VISIBILITY='public',GITHUB_ACTOR=d.OWNER,GITHUB_TRIGGERING_ACTOR=d.OWNER,GITHUB_REF='refs/heads/main',GITHUB_RUN_ID='1',GITHUB_RUN_ATTEMPT='1',GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF=d.REPOSITORY+'/'+d.WORKFLOW+'@refs/heads/main')
  self.update_event()
 def tearDown(self):
  self.event.unlink(missing_ok=True);self.temp.cleanup()
 def git(self,*args):return subprocess.check_output(['git',*args],cwd=self.root,stderr=subprocess.DEVNULL).decode().strip()
 def write(self,path,raw):p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
 def update_event(self):
  head=self.git('rev-parse','HEAD');self.env['GITHUB_SHA']=head
  event=dict(before=self.base,after=head,ref='refs/heads/main',created=False,deleted=False,forced=False,repository=dict(full_name=d.REPOSITORY,visibility='public',private=False,fork=False,default_branch='main',owner=dict(login=d.OWNER)),sender=dict(login=d.OWNER),head_commit=dict(id=head))
  self.event=Path(self.temp.name).parent/(self.root.name+'-event.json');self.event.write_text(json.dumps(event));self.env['GITHUB_EVENT_PATH']=str(self.event)
 def verify(self):
  with mock.patch.object(d,'BASE',self.base):return d.verify(self.root,self.env)
 def test_actual_git_verification_from_real_workflow_bridge(self):
  workflow=(d.ROOT/d.WORKFLOW).read_text()
  expression=re.search(r'^      GITHUB_REPOSITORY_VISIBILITY: (.+)$',workflow,re.M).group(1)
  self.assertEqual(expression,'${{ github.event.repository.visibility }}')
  payload=json.loads(self.event.read_text());payload['repository']['visibility']='public';self.event.write_text(json.dumps(payload))
  self.env.pop('GITHUB_REPOSITORY_VISIBILITY');self.env['GITHUB_REPOSITORY_VISIBILITY']=payload['repository']['visibility']
  self.assertEqual(self.manifest_sha,self.verify())
 def test_actual_git_without_workflow_bridge_reproduces_original_block(self):
  self.env.pop('GITHUB_REPOSITORY_VISIBILITY')
  with self.assertRaisesRegex(ValueError,'REPOSITORY'):self.verify()
 def test_actual_git_with_private_context_bridge_is_rejected(self):
  payload=json.loads(self.event.read_text());payload['repository']['visibility']='private';self.event.write_text(json.dumps(payload))
  self.env['GITHUB_REPOSITORY_VISIBILITY']=payload['repository']['visibility']
  with self.assertRaisesRegex(ValueError,'REPOSITORY'):self.verify()
 def test_actual_parent_blob_modes_and_closed_set_pass(self):self.assertEqual(self.manifest_sha,self.verify())
 def test_actual_payload_working_tamper_rejected(self):
  (self.root/d.WORKFLOW).write_text('changed')
  with self.assertRaisesRegex(ValueError,'PAYLOAD_BYTES'):self.verify()
 def test_actual_control_working_tamper_rejected(self):
  self.write(d.REQUEST,(self.root/d.REQUEST).read_bytes()+b' ')
  with self.assertRaisesRegex(ValueError,'TRACKED_CONTROL'):self.verify()
 def test_actual_extra_committed_path_rejected(self):
  (self.root/'extra.py').write_text('not approved');self.git('add','extra.py');self.git('commit','--amend','--no-edit');self.update_event()
  with self.assertRaisesRegex(ValueError,'CHANGED_SET'):self.verify()
 def test_actual_file_mode_change_rejected(self):
  self.git('update-index','--chmod=+x',d.WORKFLOW);self.git('commit','--amend','--no-edit');self.update_event()
  with self.assertRaisesRegex(ValueError,'PAYLOAD_BYTES'):self.verify()
 def test_actual_second_commit_rejected(self):
  (self.root/'later').write_text('second publication');self.git('add','later');self.git('commit','-m','replay');self.update_event()
  with self.assertRaisesRegex(ValueError,'PARENT'):self.verify()
 def test_actual_symlink_working_input_rejected(self):
  p=self.root/d.WORKFLOW;p.unlink();p.symlink_to(self.root/'baseline')
  with self.assertRaisesRegex(ValueError,'INPUT_FILE'):self.verify()

# Historical R4 publication bytes are distinct from this independent audit's current source.
PUBLISHED_R4_COMMIT='d1a5749787d81845433899455c47925a3ca40f0e'
PUBLISHED_R4_REQUEST_SHA='6fde28a7973a484947726abaf3e89bc418eb0f8d00582d9a506bc1ef7f09b5e6'
PUBLISHED_R4_SOURCE_SHA='bb56c1c5a845651154203a2bde36a337776825df9665896cc0ed17ca79e1a620'
PUBLISHED_R4_FIXTURE='tasks/desert-rv/scripts/fixtures/environment-v4-r4-published-d1a57497.json'
PUBLISHED_R4_PREIMAGE_PATHS={'tasks/desert-rv/scripts/test_environment_diffuse_comparison_dispatch.py', 'tasks/desert-rv/SOURCE-STATE.json', 'tasks/desert-rv/scripts/test_environment_v4_r4_dispatch.py', 'tasks/desert-rv/scripts/prepare_runner.sh', 'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneySceneAuthoring.CorrectedTerrain.cs', 'tasks/desert-rv/scripts/test_environment_diffuse_comparison_r1_dispatch.py', 'tasks/desert-rv/scripts/verify_evidence.py'}

def published_r4_preimages(raw=None):
 import base64,zlib
 request_raw=d.safe_bytes(d.ROOT/d.REQUEST,4096)
 d.require(d.sha(request_raw)==PUBLISHED_R4_REQUEST_SHA,'HISTORICAL_REQUEST')
 request=d.parse_request(request_raw)
 manifest_raw=d.safe_bytes(d.ROOT/d.MANIFEST,2*1024*1024)
 d.require(d.sha(manifest_raw)==request['filesManifestSha256'],'HISTORICAL_MANIFEST')
 d.parse_manifest(manifest_raw)
 d.require(d.sha(d.safe_bytes(d.ROOT/d.CANDIDATE,2*1024*1024))==request['candidateManifestSha256']==d.CANDIDATE_SHA,'HISTORICAL_CANDIDATE')
 d.require(request['sourceStateSha256']==PUBLISHED_R4_SOURCE_SHA,'HISTORICAL_SOURCE_PIN')
 raw=d.safe_bytes(d.ROOT/PUBLISHED_R4_FIXTURE,1024*1024) if raw is None else raw
 packet=d.decode(raw,1024*1024)
 d.require(isinstance(packet,dict) and set(packet)=={'schema','label','sourceCommit','files'} and type(packet['schema']) is int and packet['schema']==1,'HISTORICAL_SCHEMA')
 d.require(packet['label']=='HISTORICAL_PUBLIC_R4_PREIMAGE_NOT_PRODUCER_EVIDENCE' and packet['sourceCommit']==PUBLISHED_R4_COMMIT,'HISTORICAL_IDENTITY')
 rows=packet['files'];d.require(isinstance(rows,list) and len(rows)==len(PUBLISHED_R4_PREIMAGE_PATHS),'HISTORICAL_COUNT')
 result={}
 for row in rows:
  d.require(isinstance(row,dict) and set(row)=={'path','bytes','sha256','encoding','data'},'HISTORICAL_FILE_KEYS')
  name=row['path'];d.require(name in PUBLISHED_R4_PREIMAGE_PATHS and name not in result,'HISTORICAL_PATH')
  d.require(type(row['bytes']) is int and 0<row['bytes']<=512*1024 and d.digest(row['sha256']) and row['encoding']=='zlib-base64' and isinstance(row['data'],str),'HISTORICAL_FILE_IDENTITY')
  packed=base64.b64decode(row['data'],validate=True);decoder=zlib.decompressobj()
  original=decoder.decompress(packed,row['bytes']+1)
  d.require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and len(original)==row['bytes'] and d.sha(original)==row['sha256'],'HISTORICAL_FILE_BYTES')
  result[name]=original
 d.require(set(result)==PUBLISHED_R4_PREIMAGE_PATHS,'HISTORICAL_SET')
 d.require(d.sha(result[d.SOURCE_STATE])==PUBLISHED_R4_SOURCE_SHA,'HISTORICAL_SOURCE_BYTES')
 source=d.decode(result[d.SOURCE_STATE],512*1024);d.require(isinstance(source,dict) and isinstance(source.get('files'),list),'HISTORICAL_SOURCE_SCHEMA')
 declared={row['path']:row for row in source['files']}
 d.require(len(declared)==len(source['files']),'HISTORICAL_SOURCE_DUPLICATE')
 for name,original in result.items():
  if name==d.SOURCE_STATE:continue
  d.require(name in declared and d.sha(original)==declared[name]['sha256'] and len(original)==declared[name]['size'],'HISTORICAL_SOURCE_CLOSURE')
 return result

def published_r4_bytes(name,preimages):
 # Only the explicitly listed changed historical paths use pinned public preimages.
 return preimages[name] if name in PUBLISHED_R4_PREIMAGE_PATHS else d.safe_bytes(d.ROOT/name,4*1024*1024)

class PublishedR4PreimageTests(unittest.TestCase):
 def packet(self):return json.loads((d.ROOT/PUBLISHED_R4_FIXTURE).read_text())
 def check(self,packet):return published_r4_preimages(json.dumps(packet).encode())
 def test_exact_published_preimages_anchor_old_source(self):
  values=self.check(self.packet());self.assertEqual(set(values),PUBLISHED_R4_PREIMAGE_PATHS);self.assertEqual(d.sha(values[d.SOURCE_STATE]),PUBLISHED_R4_SOURCE_SHA)
 def test_missing_duplicate_and_unknown_preimage_rejected(self):
  original=self.packet()
  for mode in ('missing','duplicate','unknown','extra'):
   value=copy.deepcopy(original)
   if mode=='missing':value['files'].pop()
   if mode=='duplicate':value['files'][-1]=value['files'][0]
   if mode=='extra':value['files'].append(copy.deepcopy(value['files'][0]))
   if mode=='unknown':value['files'][0]['path']='tasks/desert-rv/private.log'
   with self.subTest(mode=mode),self.assertRaises(ValueError):self.check(value)
 def test_rehashed_preimage_tamper_is_rejected_by_original_source(self):
  import base64,zlib
  for name in sorted(PUBLISHED_R4_PREIMAGE_PATHS-{d.SOURCE_STATE}):
   value=self.packet();row=next(r for r in value['files'] if r['path']==name)
   raw=zlib.decompress(base64.b64decode(row['data']))+b'\n# UNREVIEWED\n';row.update(bytes=len(raw),sha256=d.sha(raw),data=base64.b64encode(zlib.compress(raw)).decode())
   with self.subTest(path=name),self.assertRaisesRegex(ValueError,'HISTORICAL_SOURCE_CLOSURE'):self.check(value)
 def test_rehashed_old_source_tamper_is_rejected_by_original_request(self):
  import base64,zlib
  value=self.packet();row=next(r for r in value['files'] if r['path']==d.SOURCE_STATE)
  raw=zlib.decompress(base64.b64decode(row['data']))+b' ';row.update(bytes=len(raw),sha256=d.sha(raw),data=base64.b64encode(zlib.compress(raw)).decode())
  with self.assertRaisesRegex(ValueError,'HISTORICAL_SOURCE_BYTES'):self.check(value)
 def test_old_request_tamper_cannot_rebind_snapshot(self):
  original=d.safe_bytes
  def changed(path,limit):
   raw=original(path,limit)
   return raw+b' ' if path==d.ROOT/d.REQUEST else raw
  with mock.patch.object(d,'safe_bytes',side_effect=changed),self.assertRaisesRegex(ValueError,'HISTORICAL_REQUEST'):published_r4_preimages()
 def test_old_manifest_and_candidate_byte_anchors_reject_changes(self):
  original=d.safe_bytes
  for name,code in ((d.MANIFEST,'HISTORICAL_MANIFEST'),(d.CANDIDATE,'HISTORICAL_CANDIDATE')):
   def changed(path,limit):
    raw=original(path,limit)
    return raw+b' ' if path==d.ROOT/name else raw
   with self.subTest(path=name),mock.patch.object(d,'safe_bytes',side_effect=changed),self.assertRaisesRegex(ValueError,code):published_r4_preimages()
 def test_current_source_gate_does_not_use_historical_preimages(self):
  import verify_evidence as evidence
  original=evidence.sha;target=d.ROOT/'tasks/desert-rv/scripts/verify_evidence.py'
  def changed(path):return '0'*64 if Path(path)==target else original(path)
  with mock.patch.object(evidence,'sha',side_effect=changed),self.assertRaisesRegex(ValueError,'Current source bytes differ'):evidence.verify_source_state()
  self.assertEqual(d.sha(published_r4_preimages()[d.SOURCE_STATE]),PUBLISHED_R4_SOURCE_SHA)
 def test_unknown_fields_bad_declared_size_and_trailing_stream_rejected(self):
  import base64
  original=self.packet()
  for mode in ('unknown','size','trailing'):
   value=copy.deepcopy(original);row=value['files'][0]
   if mode=='unknown':row['extra']='UNREVIEWED'
   if mode=='size':row['bytes']=1
   if mode=='trailing':row['data']=base64.b64encode(base64.b64decode(row['data'])+b'JUNK').decode()
   with self.subTest(mode=mode),self.assertRaises(ValueError):self.check(value)


class NarrowR4IntegrationTests(unittest.TestCase):
 def test_only_exact_guard_insertions(self):
  text=(Path(d.__file__).parent/'verify_evidence.py').read_text()
  self.assertEqual(text.count(", '.github/workflows/desert-rv-environment-emission-lifecycle.yml', '.github/dispatch/desert-rv-environment-emission-lifecycle-20261009-files.json'"),1);text=text.replace(", '.github/workflows/desert-rv-environment-emission-lifecycle.yml', '.github/dispatch/desert-rv-environment-emission-lifecycle-20261009-files.json'",'')
  self.assertEqual(text.count("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-emission-lifecycle.yml@refs/heads/main':\n            import environment_emission_lifecycle_dispatch\n            environment_emission_lifecycle_dispatch.verify(ROOT, os.environ)  # Independent fixed author-time emission lifecycle; strict package unchanged.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main':"),1);text=text.replace("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-emission-lifecycle.yml@refs/heads/main':\n            import environment_emission_lifecycle_dispatch\n            environment_emission_lifecycle_dispatch.verify(ROOT, os.environ)  # Independent fixed author-time emission lifecycle; strict package unchanged.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main':","        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main':")
  self.assertEqual(text.count(", '.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml', '.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json'"),1);text=text.replace(", '.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml', '.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json'",'')
  self.assertEqual(text.count("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main':\n            import environment_v4_r4_audit_r2_dispatch\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main':"),1);text=text.replace("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main':\n            import environment_v4_r4_audit_r2_dispatch\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main':","        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main':")
  self.assertEqual(text.count(", '.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml', '.github/dispatch/desert-rv-environment-v4-r4-audit-r1-20261009-files.json'"),1);text=text.replace(", '.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml', '.github/dispatch/desert-rv-environment-v4-r4-audit-r1-20261009-files.json'",'')
  self.assertEqual(text.count("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main':\n            import environment_v4_r4_audit_r1_dispatch\n            environment_v4_r4_audit_r1_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R1 host snapshot; strict package unchanged.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main':"),1);text=text.replace("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main':\n            import environment_v4_r4_audit_r1_dispatch\n            environment_v4_r4_audit_r1_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R1 host snapshot; strict package unchanged.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main':","        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main':")
  self.assertEqual(text.count(", '.github/workflows/desert-rv-environment-v4-r4-audit.yml', '.github/dispatch/desert-rv-environment-v4-r4-audit-20261009-files.json'"),1);text=text.replace(", '.github/workflows/desert-rv-environment-v4-r4-audit.yml', '.github/dispatch/desert-rv-environment-v4-r4-audit-20261009-files.json'",'')
  self.assertEqual(text.count("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main':\n            import environment_v4_r4_audit_dispatch\n            environment_v4_r4_audit_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 phase audit; strict package unchanged.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main':"),1);text=text.replace("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main':\n            import environment_v4_r4_audit_dispatch\n            environment_v4_r4_audit_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 phase audit; strict package unchanged.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main':","        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main':")
  self.assertEqual(text.count(", '.github/workflows/desert-rv-environment-v4-r4.yml', '.github/dispatch/desert-rv-environment-v4-r4-20261009-files.json'"),1);text=text.replace(", '.github/workflows/desert-rv-environment-v4-r4.yml', '.github/dispatch/desert-rv-environment-v4-r4-20261009-files.json'",'')
  self.assertEqual(text.count("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main':\n            import environment_v4_r4_dispatch\n            environment_v4_r4_dispatch.verify(ROOT, os.environ)  # Exact separate R4 corrected terrain twenty-view verification.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main':"),1);text=text.replace("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main':\n            import environment_v4_r4_dispatch\n            environment_v4_r4_dispatch.verify(ROOT, os.environ)  # Exact separate R4 corrected terrain twenty-view verification.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main':","        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main':")
  self.assertEqual(d.sha(text.encode()),'0d0e9cade546caa24ec5c433c0403186c5792ff44f2f8dfea2276cbb7d230d9e')
 def test_only_exact_runner_insertions(self):
  text=(Path(d.__file__).parent/'prepare_runner.sh').read_text()
  self.assertEqual(text.count('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-emission-lifecycle.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_emission_lifecycle_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\' ]]; then'),1);text=text.replace('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-emission-lifecycle.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_emission_lifecycle_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\' ]]; then','  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\' ]]; then')
  self.assertEqual(text.count('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\' ]]; then'),1);text=text.replace('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\' ]]; then','  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\' ]]; then')
  self.assertEqual(text.count('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r1_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main\' ]]; then'),1);text=text.replace('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r1_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main\' ]]; then','  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main\' ]]; then')
  self.assertEqual(text.count('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\' ]]; then'),1);text=text.replace('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\' ]]; then','  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\' ]]; then')
  self.assertEqual(text.count('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\' ]]; then'),1);text=text.replace('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\' ]]; then','  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\' ]]; then')
  self.assertEqual(d.sha(text.encode()),'77626e29656dde81e2ed5c16374888d25d5f0c6bd5dd20eebcfa81ac58ba70e6')

class WorkflowScopeTests(unittest.TestCase):
 def setUp(self):self.workflow=(d.ROOT/d.WORKFLOW).read_text()
 def test_original_native_execution_and_failure_gates_are_exact(self):
  prior=(d.ROOT/'.github/workflows/desert-rv-environment-v4-r3.yml').read_text()
  expected=prior.replace('environment-v4-r3','environment-v4-r4').replace('environment_v4_r3_dispatch','environment_v4_r4_dispatch').replace('V4 R3','V4 R4').replace('e0bd572526df46b6997e70a338d4a36db4f8568f',d.BASE)
  expected=expected.replace('name: Author V4 regions and capture twenty actual Unity views','name: Apply corrected terrain diffuse and capture twenty original Unity views')
  expected=expected.replace('scripts/environment_v4_evidence.py','scripts/environment_v4_r4_evidence.py').replace('path: tasks/desert-rv/evidence/environment-v4/','path: tasks/desert-rv/evidence/environment-v4-r4/').replace('path: tasks/desert-rv/evidence/environment-v4-unaccepted/','path: tasks/desert-rv/evidence/environment-v4-r4-unaccepted/').replace('python3-pil\n','python3-pil python3-numpy\n')
  def without_validation(text):
   first,rest=text.split('      - name: Validate guards and safety contracts\n',1)
   validation,last=rest.split('      - name: Restore exact checkpoint font',1)
   return first+'      - name: Restore exact checkpoint font'+last
  self.assertEqual(without_validation(self.workflow),without_validation(expected))
 def test_one_native_twenty_view_assembly_only(self):
  self.assertEqual(self.workflow.count('customParameters:'),1)
  self.assertIn('customParameters: -assemblyNames DesertRV.EditorRenderTests -force-glcore -job-worker-count 2',self.workflow)
  for token in ('EditorDiffuseComparisonTests','EditorTerrainProbeTests','continue-on-error:','if: always()','download-artifact','contents: write','-nographics'):self.assertNotIn(token,self.workflow)
  for token in ('timeout-minutes: 55','dockerCpuLimit: 2','dockerMemoryLimit: 12g','unityVersion: 6000.3.19f1'):self.assertIn(token,self.workflow)
 def test_twenty_view_wrapper_and_separate_packaging_paths(self):
  for command in ('before','package','partial'):self.assertIn('scripts/environment_v4_r4_evidence.py '+command,self.workflow)
  self.assertIn('path: tasks/desert-rv/evidence/environment-v4-r4/',self.workflow)
  self.assertIn('path: tasks/desert-rv/evidence/environment-v4-r4-unaccepted/',self.workflow)
  self.assertIn('artifactsPath: tasks/desert-rv/artifacts/environment',self.workflow)
  self.assertNotIn('evidence/diffuse-comparison/',self.workflow)
  import environment_v4_r4_evidence as evidence
  self.assertEqual(evidence.OUT,d.ROOT/'tasks/desert-rv/evidence/environment-v4-r4')
  self.assertEqual(evidence.PARTIAL,d.ROOT/'tasks/desert-rv/evidence/environment-v4-r4-unaccepted')
 def test_fixed_request_push_only(self):
  self.assertNotIn('workflow_dispatch:',self.workflow);self.assertNotIn('repository_dispatch:',self.workflow)
  self.assertIn('    branches: [main]',self.workflow);self.assertIn('      - '+d.REQUEST,self.workflow)
  self.assertIn("github.event.before == '"+d.BASE+"'",self.workflow)
  self.assertIn('permissions:\n  contents: read\n',self.workflow)
 def test_full_prior_validation_block_retained(self):
  old=(d.ROOT/'.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml').read_text()
  def commands(text):
   return text.split('      - name: Validate guards and safety contracts\n',1)[1].split('      - name: Restore exact checkpoint font',1)[0].splitlines()[1:]
  extra=['          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_r4_dispatch.py','          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_r4_runner_prefix.py','          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_r4_evidence.py','          /usr/bin/python3 tasks/desert-rv/art/environment-v4/test_candidate_r4.py']
  self.assertEqual(commands(self.workflow),commands(old)+extra)
 def test_official_packages_and_no_new_yaml_dependency(self):
  self.assertIn('apt-get install -y --no-install-recommends python3-pil python3-numpy',self.workflow)
  self.assertNotIn('python3-yaml',self.workflow);self.assertNotIn('pip install',self.workflow)
 def test_contract_still_exact_121_plus_122(self):
  contract=json.loads((d.ROOT/'tasks/desert-rv/art/environment-v4/generated-contract.json').read_text())
  self.assertEqual(len(contract['files']),121);self.assertEqual(len(contract['metadata_files']),122)
  self.assertEqual({k:len(v) for k,v in contract['region_mesh_keys'].items()},{'1':37,'2':45,'3':23});self.assertEqual(len(contract['material_names']),16)
 def test_every_old_workflow_request_and_helper_is_byte_identical(self):
  pins={'.github/dispatch/armored-v004-r1-discovery-20261009-once-69a502dd-files.json': 'f44f8c24ea4ae4656a60dd90f9a82f50d7a666c9e438973a211448e17173e242', '.github/dispatch/armored-v004-r1-discovery-20261009-once-69a502dd.json': 'f410c5744988ab33ce0d39cc9e5f438d3254250976cc3d885123f573f8b57bae', '.github/dispatch/armored-v004-r1-strict-20261009-once-c8521e4b-files.json': '7107fa05cbc12706b4545595deaeab6ced546e46cd474d1f9e2e8355ee315043', '.github/dispatch/armored-v004-r1-strict-20261009-once-c8521e4b.json': 'a8b01a16c0e06719720aa198ecdfe915ffb246e0a47d926ad08b078df2130440', '.github/dispatch/desert-rv-armored-v004-r1-static-20261009.json': 'dff22bd4d1dacc76f5c379d11614b74fca6940ff236e06de1074e63a6df353ac', '.github/dispatch/desert-rv-armored-v004-r1-technical-20261009.json': 'b2835cb6038b7d41f30c9fcd4c042cd7517f54afbd9a49185c7fd4088599a7d1', '.github/dispatch/desert-rv-armored-v004-static-20261009.json': '6ccb20b76a191feab4bc16ab3f5911dfb237d88582059c4b3744b824b76fe4b7', '.github/dispatch/desert-rv-environment-diffuse-comparison-20261009-files.json': 'a571d25aa79a85f50488be98b5bfb1c14815375753ed4ad224bb41ac7f437093', '.github/dispatch/desert-rv-environment-diffuse-comparison-20261009.json': '1386a3b6dfb746cc76542ae9172ab9afa79f5e54c8910ebfbaff18a7012bfb69', '.github/dispatch/desert-rv-environment-diffuse-comparison-r1-20261009-files.json': 'e26ec76f89d79506c248b92ddaba3fce190db8084d71c04466d3f11051627570', '.github/dispatch/desert-rv-environment-diffuse-comparison-r1-20261009.json': 'ccae6bbcaa49b2acb358f9455dfb4f476c1e75445cfad6f2c4f6ff036920fe34', '.github/dispatch/desert-rv-environment-terrain-probe-20261009-files.json': '4e7484ee6d3624acc5c964fd542d4050779b7129236353f1381bc10ef57fe9e8', '.github/dispatch/desert-rv-environment-terrain-probe-20261009.json': 'bca0375e55b6da13c94907d351f3754620b3dcfe15ccd27776200d5384c2e52e', '.github/dispatch/desert-rv-environment-v4-20261009-files.json': 'fc0a8a0670126e742c8540ebabe44352b42c132656c5887df2f71e42734c23cb', '.github/dispatch/desert-rv-environment-v4-20261009.json': '442a5bf8ce36bf69dc54c02e4a4f57c0d4b4ba2528df4090da67e8fc7088e991', '.github/dispatch/desert-rv-environment-v4-r2-20261009-files.json': '21012aab599a5282554e78eba4d4c649ffe884d683e7741296669f70c1f73ec3', '.github/dispatch/desert-rv-environment-v4-r2-20261009.json': 'd6344772a648b6228199bee74a781ef8d36925c73d9793182a76f13f02fb4db1', '.github/dispatch/desert-rv-environment-v4-r3-20261009-files.json': '375f75e87efe7c6db0b3be09a73c396ca66da94d2c434d81f8d353f9c2cd0628', '.github/dispatch/desert-rv-environment-v4-r3-20261009.json': 'fd9ed1fc78cce60e660f6bef41c67a6e0d7db7e9ffbb4e6004ee570776fec476', '.github/dispatch/desert-rv-rebuild-performance-20261009.json': 'beea0fdb80eff9506e2dd0ddff0e6099670d155397d42f01e751ef9044e469b0', '.github/dispatch/desert-rv-rebuild-performance350-20261009.json': '9c1c9e02704e360275c87e67813d23f43dacea1faf86e6f307569a075d48fad1', '.github/workflows/desert-rv-android.yml': 'a921a22d3bafd4b736575ceb48a44e302a4c31104b77fc8d341ec83162b0d4cd', '.github/workflows/desert-rv-armored-refined-static.yml': '19680a698ef93945b19d2911bfb83a670b1ab31b24a3fc196a5ad79d95398b53', '.github/workflows/desert-rv-armored-refined-technical.yml': '23d5cea0ebd344aaaa9a7d096dd909f4d90ef9f21eb9b0a099e28be7df209676', '.github/workflows/desert-rv-armored-v004-r1-discovery.yml': 'e9d002447ffda6e559df2bce20fb7eae684285f7937d0e3e16e847f7ba8031e6', '.github/workflows/desert-rv-armored-v004-r1-strict.yml': 'cca09e27c17e0d5a84637169f8a0ee0b520d77f43513a05293a2933ccf3ac6ba', '.github/workflows/desert-rv-candidate-art-import.yml': '631d3e8d75d6a67b424d82b0a902c2261f444b86fc9a9690a7336613d430621c', '.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml': 'eb439295f8b9d1bd1a720f7dd487266d2806f222f84ff5a941aae6910ac0db93', '.github/workflows/desert-rv-environment-diffuse-comparison.yml': '44019cdb559597c222d28fb6de5bae84f68d9a973de7fe7b30d23e100710ebcd', '.github/workflows/desert-rv-environment-terrain-probe.yml': 'bcae3cc5aa89f9f8794dc210c90009738ccc5a819aae4862019fdef27deeeaac', '.github/workflows/desert-rv-environment-v4-r2.yml': '886ef6b433bdaf8e8aba3b426641ac8182c84c57655a6b42b25ac4e5e0d4c1bd', '.github/workflows/desert-rv-environment-v4-r3.yml': '8929745c359c96f1a6fc7ddf90850e77f71e75d1884de8f2e33165a1c35631a7', '.github/workflows/desert-rv-environment-v4.yml': '891c1822353a9bde0966fe290a97a09e5282591fccff3962658a8c1789816e05', '.github/workflows/desert-rv-environment.yml': '172633338212febf86e7044d516b5db77b35718e461c7f51113879ef97f1a4aa', '.github/workflows/desert-rv-journey-prepare.yml': '367eec8a8c17bcaaa00dedd117e119b48bd24fa3b0df85d75f798895581c37d8', '.github/workflows/desert-rv-journey-rebuild.yml': '1cb6397c58fcbfb1d8ba8ba52b64915074594ab5b84fc68151cdd00902f0210d', '.github/workflows/desert-rv-player-observe.yml': '92dd8519f828b291ae638e88431d376d358ba7bca89abc2f4df0251b7ace944b', '.github/workflows/desert-rv-player-smoke.yml': '016374404d7410e7465137e608fde56691e0583f315ee5cb606a50b24e740072', '.github/workflows/desert-rv-rendered-smoke.yml': '78343b783fe955d751df7340388d7eb6fd21b7144fa12f5770cfca5a17d57870', '.github/workflows/desert-rv-supplies.yml': '96e34b71e0e981cde3488063333b6acdf9f8db18e181031ba6e5b60b1da59332', 'tasks/desert-rv/scripts/armored_v004_discovery_dispatch.py': '23b62943578e29b948202d1a4f67444b9ab10111d50c9d3140534c9fcf256174', 'tasks/desert-rv/scripts/armored_v004_strict_dispatch.py': '7248d35f9abb6cd03de768f673d58b97cce7efef883bc1b37447d5aa397300b8', 'tasks/desert-rv/scripts/environment_diffuse_comparison_dispatch.py': '1c3c6cf43ae8af47a8df2d9c56f5264d99d8ec11035df4bfc9ea983c0bec9cbd', 'tasks/desert-rv/scripts/environment_diffuse_comparison_r1_dispatch.py': 'b1ba84217ec8173343fa23eff321fc3522736c20c0a24dec5976172736e9a479', 'tasks/desert-rv/scripts/environment_terrain_probe_dispatch.py': '6c0e883271251f0e9a9b02e00ed241aaeb31f1a884ea53f0c3715a275bf7b83d', 'tasks/desert-rv/scripts/environment_v4_dispatch.py': '5aaf1d2c006246a9a17aeca2103be09bcadf57e08f13b3820ef5054030fbac5b', 'tasks/desert-rv/scripts/environment_v4_r2_dispatch.py': '8a8b926e249941a80f3aa846ecffea065ec5af18f42601c94f8443568391c4ec', 'tasks/desert-rv/scripts/environment_v4_r3_dispatch.py': '0427d2d8db05bbb94acd45bada987c44b4211b4dec4f2113968edf0a7ffeed62', 'tasks/desert-rv/scripts/journey_rebuild_dispatch.py': '9f906ef9ce1b4664ec5dc5c5b756afc78f78a90fd834b54a87cce565eba33101'}
  for name,expected in pins.items():self.assertEqual(d.sha((d.ROOT/name).read_bytes()),expected,name)

class FinalControlTests(unittest.TestCase):
 def test_published_r4_request_source_and_payload_preimages_are_exact(self):
  preimages=published_r4_preimages()
  request=d.parse_request((d.ROOT/d.REQUEST).read_bytes());raw=(d.ROOT/d.MANIFEST).read_bytes();manifest=d.parse_manifest(raw)
  self.assertEqual(d.sha(raw),request['filesManifestSha256']);self.assertEqual(d.sha(preimages[d.SOURCE_STATE]),request['sourceStateSha256'])
  self.assertEqual(d.sha((d.ROOT/d.CANDIDATE).read_bytes()),d.CANDIDATE_SHA)
  for row in manifest['files']:
   path=d.ROOT/row['path'];self.assertTrue(path.is_file());self.assertFalse(path.is_symlink())
   original=published_r4_bytes(row['path'],preimages)
   self.assertEqual(d.sha(original),row['sha256'],row['path']);self.assertEqual(len(original),row['size'],row['path'])
 def test_no_control_file_hash_cycle(self):
  manifest=d.parse_manifest((d.ROOT/d.MANIFEST).read_bytes());payload={row['path'] for row in manifest['files']}
  state=json.loads((d.ROOT/d.SOURCE_STATE).read_text());covered={row['path'] for row in state['files']}
  self.assertFalse(payload & {d.REQUEST,d.MANIFEST,d.SOURCE_STATE})
  self.assertTrue({d.MANIFEST,d.WORKFLOW,d.CANDIDATE}<=covered);self.assertFalse(covered & {d.REQUEST,d.SOURCE_STATE})
  self.assertTrue(payload<=covered)
 def test_source_closed_set_matches_final_disk(self):
  import verify_evidence as evidence
  evidence.verify_source_state()

class OldTestIntegrityTests(unittest.TestCase):
 def test_r3_test_only_updates_exact_render_entry_expectation(self):
  text=(Path(d.__file__).parent/'test_environment_v4_r3_dispatch.py').read_text()
  current="self.assertIn('AuthorAndCaptureCorrectedTerrainCandidates',source)";original="self.assertIn('AuthorAndCaptureEnvironmentCandidates',source)"
  self.assertEqual(text.count(current),1);text=text.replace(current,original)
  self.assertEqual(d.sha(text.encode()),'4af06c0d5c7a184c12c6bba3f0610d6510d61692351553d907b940673599bfe2')
 def test_published_old_tests_have_only_explicit_r4_changes(self):
  preimages=published_r4_preimages()
  candidate=json.loads((d.ROOT/d.CANDIDATE).read_text())
  name='tasks/desert-rv/unity/Assets/DesertRV/Tests/EditorRender/JourneyEnvironmentRenderTests.cs'
  corrected_sha=next(row['sha256'] for row in candidate['files'] if row['path']==name)
  original_sha='f5b8d102ce5debf111805742fa300bf3ded062b02f4d53856e429e057e0097f2'
  self.assertNotEqual(corrected_sha,original_sha)
  pins={'test_environment_terrain_probe_dispatch.py': '015e38d89be08b97fc18369b2f33ba0c21afe10acd2090a583715c3ec710a731', 'test_environment_diffuse_comparison_dispatch.py': 'c67aa6bbe418148b535258da2c9cf05033a5873a7593e610c83ae0859e9f77dc', 'test_environment_diffuse_comparison_r1_dispatch.py': 'fbe7c6f9728e3108f233488374bde397157477b7ffe6b8314daa24d603420ecd'}
  normalizations={'test_environment_terrain_probe_dispatch.py': [], 'test_environment_diffuse_comparison_dispatch.py': ['  self.assertEqual(text.count(", \'.github/workflows/desert-rv-environment-v4-r4.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-20261009-files.json\'"),1);text=text.replace(", \'.github/workflows/desert-rv-environment-v4-r4.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-20261009-files.json\'",\'\')\n  self.assertEqual(text.count("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\':\\n            import environment_v4_r4_dispatch\\n            environment_v4_r4_dispatch.verify(ROOT, os.environ)  # Exact separate R4 corrected terrain twenty-view verification.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\':"),1);text=text.replace("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\':\\n            import environment_v4_r4_dispatch\\n            environment_v4_r4_dispatch.verify(ROOT, os.environ)  # Exact separate R4 corrected terrain twenty-view verification.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\':","        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\':")\n', '  self.assertEqual(text.count(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\\\' ]]; then\'),1);text=text.replace(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\\\' ]]; then\',\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\\\' ]]; then\')\n'], 'test_environment_diffuse_comparison_r1_dispatch.py': ['  self.assertEqual(text.count(", \'.github/workflows/desert-rv-environment-v4-r4.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-20261009-files.json\'"),1);text=text.replace(", \'.github/workflows/desert-rv-environment-v4-r4.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-20261009-files.json\'",\'\')\n  self.assertEqual(text.count("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\':\\n            import environment_v4_r4_dispatch\\n            environment_v4_r4_dispatch.verify(ROOT, os.environ)  # Exact separate R4 corrected terrain twenty-view verification.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\':"),1);text=text.replace("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\':\\n            import environment_v4_r4_dispatch\\n            environment_v4_r4_dispatch.verify(ROOT, os.environ)  # Exact separate R4 corrected terrain twenty-view verification.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\':","        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\':")\n', '  self.assertEqual(text.count(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\\\' ]]; then\'),1);text=text.replace(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\\\' ]]; then\',\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml@refs/heads/main\\\' ]]; then\')\n']}
  for filename,expected in pins.items():
   text=published_r4_bytes('tasks/desert-rv/scripts/'+filename,preimages).decode()
   old="'"+name+"': '"+original_sha+"'";new="'"+name+"': '"+corrected_sha+"'"
   self.assertEqual(text.count(new),1,filename);text=text.replace(new,old)
   label='def test_original_production_sources_and_explicit_r4_render_entry(self):'
   self.assertEqual(text.count(label),1);text=text.replace(label,'def test_original_twenty_view_and_production_material_sources_unchanged(self):')
   comment='  # R4 explicitly changes only the EditorRender entry pin; original SHA: '+original_sha+'\n'
   self.assertEqual(text.count(comment),1);text=text.replace(comment,'')
   for exact in normalizations[filename]:
    self.assertEqual(text.count(exact),1,filename);text=text.replace(exact,'')
   self.assertEqual(d.sha(text.encode()),expected,filename)

if __name__=='__main__':unittest.main()
