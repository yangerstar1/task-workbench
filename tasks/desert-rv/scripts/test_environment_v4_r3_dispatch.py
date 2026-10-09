"""Closed V4 push fixtures, including actual Git parent/blob/mode checks. No network or dispatch."""
import copy,hashlib,json,os,re,subprocess,tempfile,unittest
from pathlib import Path
from unittest import mock
import environment_v4_r3_dispatch as d

class IdentityTests(unittest.TestCase):
 def setUp(self):
  self.head='a'*40;self.candidate=(d.ROOT/d.CANDIDATE).read_bytes();self.state=b'fixture source state'
  self.env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=d.REPOSITORY,GITHUB_REPOSITORY_VISIBILITY='public',GITHUB_ACTOR=d.OWNER,GITHUB_TRIGGERING_ACTOR=d.OWNER,GITHUB_REF='refs/heads/main',GITHUB_SHA=self.head,GITHUB_RUN_ID='1',GITHUB_RUN_ATTEMPT='1',GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF=d.REPOSITORY+'/'+d.WORKFLOW+'@refs/heads/main')
  self.event=dict(before=d.BASE,after=self.head,ref='refs/heads/main',created=False,deleted=False,forced=False,repository=dict(full_name=d.REPOSITORY,private=False,fork=False,default_branch='main',owner=dict(login=d.OWNER)),sender=dict(login=d.OWNER),head_commit=dict(id=self.head))
  self.manifest=dict(schema=1,requestId=d.REQUEST_ID,baseCommit=d.BASE,candidateManifestSha256=d.CANDIDATE_SHA,files=[dict(path=p,sha256='b'*64,size=12,mode='100644') for p in [d.WORKFLOW,'tasks/desert-rv/scripts/environment_v4_r3_dispatch.py']])
  self.request=dict(schema=1,requestId=d.REQUEST_ID,baseCommit=d.BASE,candidateManifestSha256=d.CANDIDATE_SHA,filesManifestSha256=d.sha(json.dumps(self.manifest).encode()),sourceStateSha256=d.sha(self.state))
  self.parents=[d.BASE];self.present=False;self.changed=[i['path'] for i in self.manifest['files']]+[d.REQUEST,d.MANIFEST,d.SOURCE_STATE]
 def check(self,raw=None,tracked=None,manifest=None,candidate=None):
  raw=json.dumps(self.request).encode() if raw is None else raw;manifest=json.dumps(self.manifest).encode() if manifest is None else manifest
  return d.validate_identity(self.env,self.event,self.head,self.parents,raw,raw if tracked is None else tracked,self.present,self.changed,manifest,self.state,self.candidate if candidate is None else candidate)
 def reject(self,code,**kwargs):
  with self.assertRaisesRegex(ValueError,'ENVIRONMENT_V4_R3_DISPATCH_'+code):self.check(**kwargs)
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
  self.fixture.env=self.environment();self.fixture.reject('REPOSITORY')
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
  self.payloads={d.WORKFLOW:b'fixture workflow','tasks/desert-rv/scripts/environment_v4_r3_dispatch.py':b'fixture helper',d.CANDIDATE:(d.ROOT/d.CANDIDATE).read_bytes()}
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
  event=dict(before=self.base,after=head,ref='refs/heads/main',created=False,deleted=False,forced=False,repository=dict(full_name=d.REPOSITORY,private=False,fork=False,default_branch='main',owner=dict(login=d.OWNER)),sender=dict(login=d.OWNER),head_commit=dict(id=head))
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

class RendererScopeTests(unittest.TestCase):
 def test_workflow_preserves_r2_native_and_packaging_steps(self):
  prior=(d.ROOT/'.github/workflows/desert-rv-environment-v4-r2.yml').read_text()
  expected=prior.replace('environment-v4-r2','environment-v4-r3').replace('V4 R2','V4 R3').replace('environment_v4_r2','environment_v4_r3').replace('10d52332b0808017a3f7d39e6920d008b113ba6f',d.BASE)
  expected=expected.replace('          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_dispatch.py\n','          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_dispatch.py\n          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_runner_prefix.py\n          /usr/bin/python3 tasks/desert-rv/scripts/test_journey_rebuild_dispatch.py\n')
  expected=expected.replace('          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_r3_dispatch.py\n','          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_r2_dispatch.py\n          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_r2_runner_prefix.py\n          /usr/bin/python3 tasks/desert-rv/scripts/test_armored_v004_discovery_dispatch.py\n          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_r3_dispatch.py\n')
  self.assertEqual((d.ROOT/d.WORKFLOW).read_text(),expected)
 def test_single_native_case_and_timeout_retained(self):
  source=(d.ROOT/'tasks/desert-rv/unity/Assets/DesertRV/Tests/EditorRender/JourneyEnvironmentRenderTests.cs').read_text()
  self.assertEqual(source.count('[Test,'),1);self.assertIn('[Test, Timeout(600000)]',source)
  self.assertIn('AuthorAndCaptureCorrectedTerrainCandidates',source);self.assertIn('CaptureEnvironmentPolishCloseups',source)
  workflow=(d.ROOT/d.WORKFLOW).read_text();self.assertIn('timeout-minutes: 55',workflow)
  self.assertIn('customParameters: -assemblyNames DesertRV.EditorRenderTests -force-glcore -job-worker-count 2',workflow)
 def test_exact_generated_asset_membership_retained(self):
  contract=json.loads((d.ROOT/'tasks/desert-rv/art/environment-v4/generated-contract.json').read_text())
  self.assertEqual(len(contract['files']),121);self.assertEqual(len(contract['metadata_files']),122)
  self.assertEqual({k:len(v) for k,v in contract['region_mesh_keys'].items()},{'1':37,'2':45,'3':23})
  self.assertEqual(len(contract['material_names']),16)
 def test_official_container_wrapper_is_byte_exact(self):
  self.assertEqual(d.sha((d.ROOT/'tasks/desert-rv/scripts/Environment.Dockerfile').read_bytes()),'f0d83398543119a22f73cd922257c88ee00894f41d6c5f302f1f525438ad73ab')
 def test_ci_does_not_add_yaml_dependency(self):
  workflow=(d.ROOT/d.WORKFLOW).read_text();self.assertIn('apt-get install -y --no-install-recommends python3-pil',workflow)
  self.assertNotIn('python3-yaml',workflow);self.assertNotIn('pip install',workflow)
  for name in ('environment_v4_r3_dispatch.py','test_environment_v4_r3_dispatch.py','test_environment_v4_r3_runner_prefix.py'):
   import ast
   tree=ast.parse((Path(d.__file__).parent/name).read_text())
   imported={a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}|{n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
   self.assertNotIn('yaml',imported)

if __name__=='__main__':unittest.main()
