"""Closed R4 twenty-view production terrain push fixtures, including actual Git parent/blob/mode checks. No network or dispatch."""
import copy,hashlib,json,os,re,subprocess,tempfile,unittest
from pathlib import Path
from unittest import mock
import environment_v4_r4_audit_r2_dispatch as d

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
  with self.assertRaisesRegex(ValueError,'ENVIRONMENT_V4_R4_AUDIT_R2_DISPATCH_'+code):self.check(**kwargs)
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
 def test_previous_r4_nonce_rejected(self):self.request['requestId']='desert-rv-environment-v4-r4-20261009-once-d28e54a9';self.reject('REQUEST_IDENTITY')
 def test_previous_r4_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main';self.reject('WORKFLOW')
 def test_previous_audit_nonce_rejected(self):self.request['requestId']='desert-rv-environment-v4-r4-audit-20261009-once-9f732c61';self.reject('REQUEST_IDENTITY')
 def test_previous_audit_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main';self.reject('WORKFLOW')
 def test_previous_audit_r1_nonce_rejected(self):self.request['requestId']='desert-rv-environment-v4-r4-audit-r1-20261009-once-6b40e912';self.reject('REQUEST_IDENTITY')
 def test_previous_audit_r1_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main';self.reject('WORKFLOW')
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

class NarrowAuditR2IntegrationTests(unittest.TestCase):
 def test_only_exact_guard_insertions(self):
  text=(Path(d.__file__).parent/'verify_evidence.py').read_text()
  self.assertEqual(text.count(", '.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml', '.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json'"),1);text=text.replace(", '.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml', '.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json'",'')
  self.assertEqual(text.count("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main':\n            import environment_v4_r4_audit_r2_dispatch\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main':"),1);text=text.replace("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main':\n            import environment_v4_r4_audit_r2_dispatch\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main':","        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main':")
  self.assertEqual(d.sha(text.encode()),'0f35eff674c3087ac4add221e9464f6f81306b5394fa372e8aa201a8a0a4ebae')
 def test_only_exact_runner_insertions(self):
  text=(Path(d.__file__).parent/'prepare_runner.sh').read_text()
  self.assertEqual(text.count('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\' ]]; then'),1);text=text.replace('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\' ]]; then','  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\' ]]; then')
  self.assertEqual(d.sha(text.encode()),'b10537d9a5a70e77b0746fc0797572bcf0c2c65bed22997b0650a5b1b9e69746')
class AuditR2WorkflowTests(unittest.TestCase):
 def setUp(self):self.workflow=(d.ROOT/d.WORKFLOW).read_text()
 def test_prior_twenty_camera_native_entry_and_resources_are_exact(self):
  original=(d.ROOT/'.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml').read_text()
  def native(text):return text.split('      - name: Execute separate native EditorRender author and capture entry',1)[1].split('      - name: Reject altered originals',1)[0]
  self.assertEqual(native(self.workflow),native(original))
  self.assertEqual(self.workflow.count('customParameters:'),1)
  self.assertIn('customParameters: -assemblyNames DesertRV.EditorRenderTests -force-glcore -job-worker-count 2',self.workflow)
  self.assertIn('timeout-minutes: 55',self.workflow)
  self.assertIn('scripts/environment_v4_r4_evidence.py before',self.workflow)
  for item in ('continue-on-error:','if: always()','contents: write','-nographics','EditorDiffuseComparisonTests','EditorTerrainProbeTests'):self.assertNotIn(item,self.workflow)
 def test_diagnostics_runs_on_strict_success_or_failure_only_after_native_success(self):
  self.assertIn("if: ${{ !cancelled() && steps.native.outcome == 'success' }}",self.workflow)
  self.assertIn("if: ${{ !cancelled() && steps.audit_diag.outcome == 'success' }}",self.workflow)
  self.assertIn("environment_v4_r4_audit.py diagnose --package-outcome '${{ steps.package.outcome }}'",self.workflow)
  self.assertIn('environment_v4_r4_audit.py package',self.workflow)
  self.assertNotIn('environment_v4_r4_evidence.py partial',self.workflow)
  self.assertNotIn('id: partial',self.workflow)
  self.assertNotIn('--package-outcome success',self.workflow)
  self.assertNotIn('--package-outcome failure',self.workflow)
 def test_fixed_request_public_owner_first_attempt_scope(self):
  self.assertNotIn('workflow_dispatch:',self.workflow);self.assertNotIn('repository_dispatch:',self.workflow)
  self.assertIn('    branches: [main]',self.workflow);self.assertIn('      - '+d.REQUEST,self.workflow)
  self.assertIn("github.event.before == '"+d.BASE+"'",self.workflow)
  self.assertIn('permissions:\n  contents: read\n',self.workflow)
 def test_all_old_tests_and_two_new_protocol_suites_are_retained(self):
  original=(d.ROOT/'.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml').read_text()
  def commands(text):return text.split('      - name: Validate guards and safety contracts\n',1)[1].split('      - name: Restore exact checkpoint font',1)[0].splitlines()[1:]
  additions=['          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_r4_audit_r2_dispatch.py', '          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_r4_audit_r2_runner_prefix.py', '          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_image_precheck.py']
  self.assertEqual(commands(self.workflow),commands(original)+additions)
 def test_only_exact_artifact_paths_and_upload_count(self):
  paths=re.findall(r'^          path: (.+)$',self.workflow,re.M)
  self.assertEqual(paths,['tasks/desert-rv/image-readiness.json','tasks/desert-rv/evidence/environment-v4-r4/','tasks/desert-rv/evidence/environment-v4-r4-audit/','tasks/desert-rv/evidence/environment-source-diagnostic/protected-source-failure.json','tasks/desert-rv/evidence/environment-package-diagnostic/unity-package-resolution.json'])
  self.assertEqual(self.workflow.count('uses: actions/upload-artifact@'),5)
  self.assertIn('name: desert-rv-environment-v4-r4-audit-r2-LIFECYCLE-DIAGNOSTIC-',self.workflow)
  import environment_v4_r4_audit as audit
  self.assertEqual(audit.OUT,d.ROOT/'tasks/desert-rv/evidence/environment-v4-r4-audit')
  for forbidden in ('Unity.log','artifacts/environment/','JourneyEvidence/','generated/'):
   self.assertFalse(any(forbidden in path for path in paths))
 def test_every_prior_authorization_file_is_byte_identical(self):
  pins={'.github/dispatch/armored-v004-r1-discovery-20261009-once-69a502dd-files.json': 'f44f8c24ea4ae4656a60dd90f9a82f50d7a666c9e438973a211448e17173e242', '.github/dispatch/armored-v004-r1-discovery-20261009-once-69a502dd.json': 'f410c5744988ab33ce0d39cc9e5f438d3254250976cc3d885123f573f8b57bae', '.github/dispatch/armored-v004-r1-strict-20261009-once-c8521e4b-files.json': '7107fa05cbc12706b4545595deaeab6ced546e46cd474d1f9e2e8355ee315043', '.github/dispatch/armored-v004-r1-strict-20261009-once-c8521e4b.json': 'a8b01a16c0e06719720aa198ecdfe915ffb246e0a47d926ad08b078df2130440', '.github/dispatch/desert-rv-armored-v004-r1-static-20261009.json': 'dff22bd4d1dacc76f5c379d11614b74fca6940ff236e06de1074e63a6df353ac', '.github/dispatch/desert-rv-armored-v004-r1-technical-20261009.json': 'b2835cb6038b7d41f30c9fcd4c042cd7517f54afbd9a49185c7fd4088599a7d1', '.github/dispatch/desert-rv-armored-v004-static-20261009.json': '6ccb20b76a191feab4bc16ab3f5911dfb237d88582059c4b3744b824b76fe4b7', '.github/dispatch/desert-rv-environment-diffuse-comparison-20261009-files.json': 'a571d25aa79a85f50488be98b5bfb1c14815375753ed4ad224bb41ac7f437093', '.github/dispatch/desert-rv-environment-diffuse-comparison-20261009.json': '1386a3b6dfb746cc76542ae9172ab9afa79f5e54c8910ebfbaff18a7012bfb69', '.github/dispatch/desert-rv-environment-diffuse-comparison-r1-20261009-files.json': 'e26ec76f89d79506c248b92ddaba3fce190db8084d71c04466d3f11051627570', '.github/dispatch/desert-rv-environment-diffuse-comparison-r1-20261009.json': 'ccae6bbcaa49b2acb358f9455dfb4f476c1e75445cfad6f2c4f6ff036920fe34', '.github/dispatch/desert-rv-environment-terrain-probe-20261009-files.json': '4e7484ee6d3624acc5c964fd542d4050779b7129236353f1381bc10ef57fe9e8', '.github/dispatch/desert-rv-environment-terrain-probe-20261009.json': 'bca0375e55b6da13c94907d351f3754620b3dcfe15ccd27776200d5384c2e52e', '.github/dispatch/desert-rv-environment-v4-20261009-files.json': 'fc0a8a0670126e742c8540ebabe44352b42c132656c5887df2f71e42734c23cb', '.github/dispatch/desert-rv-environment-v4-20261009.json': '442a5bf8ce36bf69dc54c02e4a4f57c0d4b4ba2528df4090da67e8fc7088e991', '.github/dispatch/desert-rv-environment-v4-r2-20261009-files.json': '21012aab599a5282554e78eba4d4c649ffe884d683e7741296669f70c1f73ec3', '.github/dispatch/desert-rv-environment-v4-r2-20261009.json': 'd6344772a648b6228199bee74a781ef8d36925c73d9793182a76f13f02fb4db1', '.github/dispatch/desert-rv-environment-v4-r3-20261009-files.json': '375f75e87efe7c6db0b3be09a73c396ca66da94d2c434d81f8d353f9c2cd0628', '.github/dispatch/desert-rv-environment-v4-r3-20261009.json': 'fd9ed1fc78cce60e660f6bef41c67a6e0d7db7e9ffbb4e6004ee570776fec476', '.github/dispatch/desert-rv-environment-v4-r4-20261009-files.json': '12738e82388b4f3ff6fc84dfd82651f57e9937b0153ef8b05c312dbd9728c16c', '.github/dispatch/desert-rv-environment-v4-r4-20261009.json': '6fde28a7973a484947726abaf3e89bc418eb0f8d00582d9a506bc1ef7f09b5e6', '.github/dispatch/desert-rv-environment-v4-r4-audit-20261009-files.json': '0b9b5c2d102b326fccc7dd10994fc49b9a1ed69bf14e70de26b94410007587a5', '.github/dispatch/desert-rv-environment-v4-r4-audit-20261009.json': '91eac8b353919bc9a875ebe6aaa2df6f652111e77184c6ca8e73d61587f09968', '.github/dispatch/desert-rv-environment-v4-r4-audit-r1-20261009-files.json': '21fb31623f0390909e653eadd21abc2f24b3d3964499a23a948721def5e3aac8', '.github/dispatch/desert-rv-environment-v4-r4-audit-r1-20261009.json': 'ab6fd7ca5b7658c29d89bbd8046958d31229afffa6aad3689006d2a66de589e7', '.github/dispatch/desert-rv-rebuild-performance-20261009.json': 'beea0fdb80eff9506e2dd0ddff0e6099670d155397d42f01e751ef9044e469b0', '.github/dispatch/desert-rv-rebuild-performance350-20261009.json': '9c1c9e02704e360275c87e67813d23f43dacea1faf86e6f307569a075d48fad1', '.github/workflows/desert-rv-android.yml': 'a921a22d3bafd4b736575ceb48a44e302a4c31104b77fc8d341ec83162b0d4cd', '.github/workflows/desert-rv-armored-refined-static.yml': '19680a698ef93945b19d2911bfb83a670b1ab31b24a3fc196a5ad79d95398b53', '.github/workflows/desert-rv-armored-refined-technical.yml': '23d5cea0ebd344aaaa9a7d096dd909f4d90ef9f21eb9b0a099e28be7df209676', '.github/workflows/desert-rv-armored-v004-r1-discovery.yml': 'e9d002447ffda6e559df2bce20fb7eae684285f7937d0e3e16e847f7ba8031e6', '.github/workflows/desert-rv-armored-v004-r1-strict.yml': 'cca09e27c17e0d5a84637169f8a0ee0b520d77f43513a05293a2933ccf3ac6ba', '.github/workflows/desert-rv-candidate-art-import.yml': '631d3e8d75d6a67b424d82b0a902c2261f444b86fc9a9690a7336613d430621c', '.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml': 'eb439295f8b9d1bd1a720f7dd487266d2806f222f84ff5a941aae6910ac0db93', '.github/workflows/desert-rv-environment-diffuse-comparison.yml': '44019cdb559597c222d28fb6de5bae84f68d9a973de7fe7b30d23e100710ebcd', '.github/workflows/desert-rv-environment-terrain-probe.yml': 'bcae3cc5aa89f9f8794dc210c90009738ccc5a819aae4862019fdef27deeeaac', '.github/workflows/desert-rv-environment-v4-r2.yml': '886ef6b433bdaf8e8aba3b426641ac8182c84c57655a6b42b25ac4e5e0d4c1bd', '.github/workflows/desert-rv-environment-v4-r3.yml': '8929745c359c96f1a6fc7ddf90850e77f71e75d1884de8f2e33165a1c35631a7', '.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml': '7a7cc9cac385ddb9741106c929e9459f99bdc2b34b6bcf7f353c4f2578adcd5c', '.github/workflows/desert-rv-environment-v4-r4-audit.yml': '2309d08b545d20b78291c9c7c72ec73654d6c60830a56c441e69c3fc556ca21c', '.github/workflows/desert-rv-environment-v4-r4.yml': '10712c9cfbbe230d801743bf320407947b6933b1d80931be2e26c7c847501535', '.github/workflows/desert-rv-environment-v4.yml': '891c1822353a9bde0966fe290a97a09e5282591fccff3962658a8c1789816e05', '.github/workflows/desert-rv-environment.yml': '172633338212febf86e7044d516b5db77b35718e461c7f51113879ef97f1a4aa', '.github/workflows/desert-rv-journey-prepare.yml': '367eec8a8c17bcaaa00dedd117e119b48bd24fa3b0df85d75f798895581c37d8', '.github/workflows/desert-rv-journey-rebuild.yml': '1cb6397c58fcbfb1d8ba8ba52b64915074594ab5b84fc68151cdd00902f0210d', '.github/workflows/desert-rv-player-observe.yml': '92dd8519f828b291ae638e88431d376d358ba7bca89abc2f4df0251b7ace944b', '.github/workflows/desert-rv-player-smoke.yml': '016374404d7410e7465137e608fde56691e0583f315ee5cb606a50b24e740072', '.github/workflows/desert-rv-rendered-smoke.yml': '78343b783fe955d751df7340388d7eb6fd21b7144fa12f5770cfca5a17d57870', '.github/workflows/desert-rv-supplies.yml': '96e34b71e0e981cde3488063333b6acdf9f8db18e181031ba6e5b60b1da59332', 'tasks/desert-rv/scripts/armored_v004_discovery_dispatch.py': '23b62943578e29b948202d1a4f67444b9ab10111d50c9d3140534c9fcf256174', 'tasks/desert-rv/scripts/armored_v004_strict_dispatch.py': '7248d35f9abb6cd03de768f673d58b97cce7efef883bc1b37447d5aa397300b8', 'tasks/desert-rv/scripts/environment_diffuse_comparison_dispatch.py': '1c3c6cf43ae8af47a8df2d9c56f5264d99d8ec11035df4bfc9ea983c0bec9cbd', 'tasks/desert-rv/scripts/environment_diffuse_comparison_r1_dispatch.py': 'b1ba84217ec8173343fa23eff321fc3522736c20c0a24dec5976172736e9a479', 'tasks/desert-rv/scripts/environment_terrain_probe_dispatch.py': '6c0e883271251f0e9a9b02e00ed241aaeb31f1a884ea53f0c3715a275bf7b83d', 'tasks/desert-rv/scripts/environment_v4_dispatch.py': '5aaf1d2c006246a9a17aeca2103be09bcadf57e08f13b3820ef5054030fbac5b', 'tasks/desert-rv/scripts/environment_v4_r2_dispatch.py': '8a8b926e249941a80f3aa846ecffea065ec5af18f42601c94f8443568391c4ec', 'tasks/desert-rv/scripts/environment_v4_r3_dispatch.py': '0427d2d8db05bbb94acd45bada987c44b4211b4dec4f2113968edf0a7ffeed62', 'tasks/desert-rv/scripts/environment_v4_r4_audit_dispatch.py': 'a17e366099ad760d4c6220ea74ecfb7c126c31c4b163f1be6918725b3bfc5c2f', 'tasks/desert-rv/scripts/environment_v4_r4_audit_r1_dispatch.py': 'd766479454bae0f058222042a220134f516c437caf40e84ea18cef68671daf8e', 'tasks/desert-rv/scripts/environment_v4_r4_dispatch.py': 'd4817fd852a6abcfbd112d5ba437fbfc7d26732e3e133fa3a67361e292317d6c', 'tasks/desert-rv/scripts/journey_rebuild_dispatch.py': '9f906ef9ce1b4664ec5dc5c5b756afc78f78a90fd834b54a87cce565eba33101'}
  for name,expected in pins.items():self.assertEqual(d.sha((d.ROOT/name).read_bytes()),expected,name)
 def test_original_strict_wrapper_is_byte_identical(self):
  self.assertEqual(d.sha((d.ROOT/'tasks/desert-rv/scripts/environment_v4_r4_evidence.py').read_bytes()),'958739e1d1b38bc8916e0e730d43c9f1abf52ba9ba524ffb72848f102cfa8f2f')
  self.assertEqual(d.sha((d.ROOT/'tasks/desert-rv/scripts/environment_v4_evidence.py').read_bytes()),'7f8bd56d466260bbf57653a76f3845deea81d9f96d03a093366376dcfeba6548')
  self.assertEqual(d.sha((d.ROOT/'tasks/desert-rv/unity/Assets/DesertRV/Tests/EditorRender/JourneyEnvironmentRenderTests.cs').read_bytes()),'4a16e5d04dabc2a0ed78dd0be8eb6b4730e2edc9a2a40ac3b0acd20382246858')

class OldTestIntegrityTests(unittest.TestCase):
 def test_previous_test_bodies_reverse_exactly_to_published_bytes(self):
  pins={'test_environment_diffuse_comparison_dispatch.py': '1b4696aeb8286607caa61a6397ff049705c51a32630ab8c838c6490fb4530e3f', 'test_environment_diffuse_comparison_r1_dispatch.py': '532745602509cd2980423b792020f3343879b3cbb96916a5c1e0e65099ab055c', 'test_environment_v4_r4_dispatch.py': '436647846efe711e03b641910c4d669ce0fbaac5553824a709cd68986ec080d4', 'test_environment_v4_r4_audit_dispatch.py': '22cad8231c8ffcd9b8ad75db55335927832b485e40a459aab7d974c451bc8133', 'test_environment_v4_r4_audit_r1_dispatch.py': '5f9961099fa52b1b64ff60b0c822b4f39454892b2653280bb734edbda01c0a00'}
  changes={'test_environment_diffuse_comparison_dispatch.py': [("  text=(Path(d.__file__).parent/'verify_evidence.py').read_text()\n", '  text=(Path(d.__file__).parent/\'verify_evidence.py\').read_text()\n  self.assertEqual(text.count(", \'.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json\'"),1);text=text.replace(", \'.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json\'",\'\')\n  self.assertEqual(text.count("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\':\\n            import environment_v4_r4_audit_r2_dispatch\\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':"),1);text=text.replace("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\':\\n            import environment_v4_r4_audit_r2_dispatch\\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':","        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':")\n'), ("  text=(Path(d.__file__).parent/'prepare_runner.sh').read_text()\n", '  text=(Path(d.__file__).parent/\'prepare_runner.sh\').read_text()\n  self.assertEqual(text.count(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\'),1);text=text.replace(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\',\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\')\n')], 'test_environment_diffuse_comparison_r1_dispatch.py': [("  text=(Path(d.__file__).parent/'verify_evidence.py').read_text()\n", '  text=(Path(d.__file__).parent/\'verify_evidence.py\').read_text()\n  self.assertEqual(text.count(", \'.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json\'"),1);text=text.replace(", \'.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json\'",\'\')\n  self.assertEqual(text.count("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\':\\n            import environment_v4_r4_audit_r2_dispatch\\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':"),1);text=text.replace("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\':\\n            import environment_v4_r4_audit_r2_dispatch\\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':","        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':")\n'), ("  text=(Path(d.__file__).parent/'prepare_runner.sh').read_text()\n", '  text=(Path(d.__file__).parent/\'prepare_runner.sh\').read_text()\n  self.assertEqual(text.count(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\'),1);text=text.replace(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\',\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\')\n')], 'test_environment_v4_r4_dispatch.py': [("  text=(Path(d.__file__).parent/'verify_evidence.py').read_text()\n", '  text=(Path(d.__file__).parent/\'verify_evidence.py\').read_text()\n  self.assertEqual(text.count(", \'.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json\'"),1);text=text.replace(", \'.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json\'",\'\')\n  self.assertEqual(text.count("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\':\\n            import environment_v4_r4_audit_r2_dispatch\\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':"),1);text=text.replace("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\':\\n            import environment_v4_r4_audit_r2_dispatch\\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':","        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':")\n'), ("  text=(Path(d.__file__).parent/'prepare_runner.sh').read_text()\n", '  text=(Path(d.__file__).parent/\'prepare_runner.sh\').read_text()\n  self.assertEqual(text.count(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\'),1);text=text.replace(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\',\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\')\n')], 'test_environment_v4_r4_audit_dispatch.py': [("  text=(Path(d.__file__).parent/'verify_evidence.py').read_text()\n", '  text=(Path(d.__file__).parent/\'verify_evidence.py\').read_text()\n  self.assertEqual(text.count(", \'.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json\'"),1);text=text.replace(", \'.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json\'",\'\')\n  self.assertEqual(text.count("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\':\\n            import environment_v4_r4_audit_r2_dispatch\\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':"),1);text=text.replace("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\':\\n            import environment_v4_r4_audit_r2_dispatch\\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':","        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':")\n'), ("  text=(Path(d.__file__).parent/'prepare_runner.sh').read_text()\n", '  text=(Path(d.__file__).parent/\'prepare_runner.sh\').read_text()\n  self.assertEqual(text.count(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\'),1);text=text.replace(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\',\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\')\n')], 'test_environment_v4_r4_audit_r1_dispatch.py': [("  text=(Path(d.__file__).parent/'verify_evidence.py').read_text()\n", '  text=(Path(d.__file__).parent/\'verify_evidence.py\').read_text()\n  self.assertEqual(text.count(", \'.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json\'"),1);text=text.replace(", \'.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml\', \'.github/dispatch/desert-rv-environment-v4-r4-audit-r2-20261009-files.json\'",\'\')\n  self.assertEqual(text.count("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\':\\n            import environment_v4_r4_audit_r2_dispatch\\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':"),1);text=text.replace("        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\':\\n            import environment_v4_r4_audit_r2_dispatch\\n            environment_v4_r4_audit_r2_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 audit R2 image-readiness gate; strict package unchanged.\\n        elif os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':","        if os.environ.get(\'GITHUB_WORKFLOW_REF\') == REPOSITORY + \'/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\':")\n'), ("  text=(Path(d.__file__).parent/'prepare_runner.sh').read_text()\n", '  text=(Path(d.__file__).parent/\'prepare_runner.sh\').read_text()\n  self.assertEqual(text.count(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\'),1);text=text.replace(\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r2.yml@refs/heads/main\\\' ]]; then\\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_r2_dispatch.py" --verify-only\\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\',\'  if [[ "${GITHUB_WORKFLOW_REF:-}" == \\\'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml@refs/heads/main\\\' ]]; then\')\n'), ('class NarrowAuditR1IntegrationTests', "# AUDIT_R2_52B883_PREIMAGES_BEGIN\n# Historical R4 publication bytes are distinct from this independent audit's current source.\nPUBLISHED_AUDIT_R1_COMMIT='52b8839343b60a5992c45be17e131bb7caf2cc89'\nPUBLISHED_AUDIT_R1_REQUEST_SHA='ab6fd7ca5b7658c29d89bbd8046958d31229afffa6aad3689006d2a66de589e7'\nPUBLISHED_AUDIT_R1_SOURCE_SHA='51b9927eafea3ce1071566d502d30b6ef758523b73fbb086e12a7455d0b4190e'\nPUBLISHED_AUDIT_R1_FIXTURE='tasks/desert-rv/scripts/fixtures/environment-v4-r4-audit-r1-published-52b88393.json'\nPUBLISHED_AUDIT_R1_PREIMAGE_PATHS=set(['tasks/desert-rv/SOURCE-STATE.json', 'tasks/desert-rv/scripts/prepare_runner.sh', 'tasks/desert-rv/scripts/test_environment_diffuse_comparison_dispatch.py', 'tasks/desert-rv/scripts/test_environment_diffuse_comparison_r1_dispatch.py', 'tasks/desert-rv/scripts/test_environment_v4_r4_audit_dispatch.py', 'tasks/desert-rv/scripts/test_environment_v4_r4_audit_r1_dispatch.py', 'tasks/desert-rv/scripts/test_environment_v4_r4_dispatch.py', 'tasks/desert-rv/scripts/verify_evidence.py'])\n\ndef published_audit_r1_preimages(raw=None):\n import base64,zlib\n request_raw=d.safe_bytes(d.ROOT/d.REQUEST,4096)\n d.require(d.sha(request_raw)==PUBLISHED_AUDIT_R1_REQUEST_SHA,'HISTORICAL_REQUEST')\n request=d.parse_request(request_raw)\n manifest_raw=d.safe_bytes(d.ROOT/d.MANIFEST,2*1024*1024)\n d.require(d.sha(manifest_raw)==request['filesManifestSha256'],'HISTORICAL_MANIFEST')\n d.parse_manifest(manifest_raw)\n d.require(d.sha(d.safe_bytes(d.ROOT/d.CANDIDATE,2*1024*1024))==request['candidateManifestSha256']==d.CANDIDATE_SHA,'HISTORICAL_CANDIDATE')\n d.require(request['sourceStateSha256']==PUBLISHED_AUDIT_R1_SOURCE_SHA,'HISTORICAL_SOURCE_PIN')\n raw=d.safe_bytes(d.ROOT/PUBLISHED_AUDIT_R1_FIXTURE,1024*1024) if raw is None else raw\n packet=d.decode(raw,1024*1024)\n d.require(isinstance(packet,dict) and set(packet)=={'schema','label','sourceCommit','files'} and type(packet['schema']) is int and packet['schema']==1,'HISTORICAL_SCHEMA')\n d.require(packet['label']=='HISTORICAL_PUBLIC_AUDIT_R1_PREIMAGE_NOT_PRODUCER_EVIDENCE' and packet['sourceCommit']==PUBLISHED_AUDIT_R1_COMMIT,'HISTORICAL_IDENTITY')\n rows=packet['files'];d.require(isinstance(rows,list) and len(rows)==len(PUBLISHED_AUDIT_R1_PREIMAGE_PATHS),'HISTORICAL_COUNT')\n result={}\n for row in rows:\n  d.require(isinstance(row,dict) and set(row)=={'path','bytes','sha256','encoding','data'},'HISTORICAL_FILE_KEYS')\n  name=row['path'];d.require(name in PUBLISHED_AUDIT_R1_PREIMAGE_PATHS and name not in result,'HISTORICAL_PATH')\n  d.require(type(row['bytes']) is int and 0<row['bytes']<=512*1024 and d.digest(row['sha256']) and row['encoding']=='zlib-base64' and isinstance(row['data'],str),'HISTORICAL_FILE_IDENTITY')\n  packed=base64.b64decode(row['data'],validate=True);decoder=zlib.decompressobj()\n  original=decoder.decompress(packed,row['bytes']+1)\n  d.require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail and len(original)==row['bytes'] and d.sha(original)==row['sha256'],'HISTORICAL_FILE_BYTES')\n  result[name]=original\n d.require(set(result)==PUBLISHED_AUDIT_R1_PREIMAGE_PATHS,'HISTORICAL_SET')\n d.require(d.sha(result[d.SOURCE_STATE])==PUBLISHED_AUDIT_R1_SOURCE_SHA,'HISTORICAL_SOURCE_BYTES')\n source=d.decode(result[d.SOURCE_STATE],512*1024);d.require(isinstance(source,dict) and isinstance(source.get('files'),list),'HISTORICAL_SOURCE_SCHEMA')\n declared={row['path']:row for row in source['files']}\n d.require(len(declared)==len(source['files']),'HISTORICAL_SOURCE_DUPLICATE')\n for name,original in result.items():\n  if name==d.SOURCE_STATE:continue\n  d.require(name in declared and d.sha(original)==declared[name]['sha256'] and len(original)==declared[name]['size'],'HISTORICAL_SOURCE_CLOSURE')\n for name,row in declared.items():\n  d.require(isinstance(name,str) and not name.startswith('/') and '..' not in Path(name).parts and Path(name).as_posix()==name and set(row)=={'path','sha256','size'} and d.digest(row['sha256']) and type(row['size']) is int and 0<=row['size']<=40*1024*1024,'HISTORICAL_SOURCE_ROW')\n  original=result[name] if name in PUBLISHED_AUDIT_R1_PREIMAGE_PATHS else d.safe_bytes(d.ROOT/name,40*1024*1024)\n  d.require(d.sha(original)==row['sha256'] and len(original)==row['size'],'HISTORICAL_SOURCE_FULL_CLOSURE')\n return result\n\ndef published_audit_r1_bytes(name,preimages):\n # Only the explicitly listed changed historical paths use pinned public preimages.\n return preimages[name] if name in PUBLISHED_AUDIT_R1_PREIMAGE_PATHS else d.safe_bytes(d.ROOT/name,4*1024*1024)\n\nclass PublishedAuditR1PreimageTests(unittest.TestCase):\n def packet(self):return json.loads((d.ROOT/PUBLISHED_AUDIT_R1_FIXTURE).read_text())\n def check(self,packet):return published_audit_r1_preimages(json.dumps(packet).encode())\n def test_exact_published_preimages_anchor_old_source(self):\n  values=self.check(self.packet());self.assertEqual(set(values),PUBLISHED_AUDIT_R1_PREIMAGE_PATHS);self.assertEqual(d.sha(values[d.SOURCE_STATE]),PUBLISHED_AUDIT_R1_SOURCE_SHA)\n def test_missing_duplicate_and_unknown_preimage_rejected(self):\n  original=self.packet()\n  for mode in ('missing','duplicate','unknown','extra'):\n   value=copy.deepcopy(original)\n   if mode=='missing':value['files'].pop()\n   if mode=='duplicate':value['files'][-1]=value['files'][0]\n   if mode=='extra':value['files'].append(copy.deepcopy(value['files'][0]))\n   if mode=='unknown':value['files'][0]['path']='tasks/desert-rv/private.log'\n   with self.subTest(mode=mode),self.assertRaises(ValueError):self.check(value)\n def test_rehashed_preimage_tamper_is_rejected_by_original_source(self):\n  import base64,zlib\n  for name in sorted(PUBLISHED_AUDIT_R1_PREIMAGE_PATHS-{d.SOURCE_STATE}):\n   value=self.packet();row=next(r for r in value['files'] if r['path']==name)\n   raw=zlib.decompress(base64.b64decode(row['data']))+b'\\n# UNREVIEWED\\n';row.update(bytes=len(raw),sha256=d.sha(raw),data=base64.b64encode(zlib.compress(raw)).decode())\n   with self.subTest(path=name),self.assertRaisesRegex(ValueError,'HISTORICAL_SOURCE_CLOSURE'):self.check(value)\n def test_rehashed_old_source_tamper_is_rejected_by_original_request(self):\n  import base64,zlib\n  value=self.packet();row=next(r for r in value['files'] if r['path']==d.SOURCE_STATE)\n  raw=zlib.decompress(base64.b64decode(row['data']))+b' ';row.update(bytes=len(raw),sha256=d.sha(raw),data=base64.b64encode(zlib.compress(raw)).decode())\n  with self.assertRaisesRegex(ValueError,'HISTORICAL_SOURCE_BYTES'):self.check(value)\n def test_old_request_tamper_cannot_rebind_snapshot(self):\n  original=d.safe_bytes\n  def changed(path,limit):\n   raw=original(path,limit)\n   return raw+b' ' if path==d.ROOT/d.REQUEST else raw\n  with mock.patch.object(d,'safe_bytes',side_effect=changed),self.assertRaisesRegex(ValueError,'HISTORICAL_REQUEST'):published_audit_r1_preimages()\n def test_old_manifest_and_candidate_byte_anchors_reject_changes(self):\n  original=d.safe_bytes\n  for name,code in ((d.MANIFEST,'HISTORICAL_MANIFEST'),(d.CANDIDATE,'HISTORICAL_CANDIDATE')):\n   def changed(path,limit):\n    raw=original(path,limit)\n    return raw+b' ' if path==d.ROOT/name else raw\n   with self.subTest(path=name),mock.patch.object(d,'safe_bytes',side_effect=changed),self.assertRaisesRegex(ValueError,code):published_audit_r1_preimages()\n def test_current_source_gate_does_not_use_historical_preimages(self):\n  import verify_evidence as evidence\n  original=evidence.sha;target=d.ROOT/'tasks/desert-rv/scripts/verify_evidence.py'\n  def changed(path):return '0'*64 if Path(path)==target else original(path)\n  with mock.patch.object(evidence,'sha',side_effect=changed),self.assertRaisesRegex(ValueError,'Current source bytes differ'):evidence.verify_source_state()\n  self.assertEqual(d.sha(published_audit_r1_preimages()[d.SOURCE_STATE]),PUBLISHED_AUDIT_R1_SOURCE_SHA)\n def test_unknown_fields_bad_declared_size_and_trailing_stream_rejected(self):\n  import base64\n  original=self.packet()\n  for mode in ('unknown','size','trailing'):\n   value=copy.deepcopy(original);row=value['files'][0]\n   if mode=='unknown':row['extra']='UNREVIEWED'\n   if mode=='size':row['bytes']=1\n   if mode=='trailing':row['data']=base64.b64encode(base64.b64decode(row['data'])+b'JUNK').decode()\n   with self.subTest(mode=mode),self.assertRaises(ValueError):self.check(value)\n\n\n def test_unchanged_old_source_member_tamper_rejected(self):\n  original=d.safe_bytes;name='tasks/desert-rv/scripts/environment_v4_r4_evidence.py'\n  self.assertNotIn(name,PUBLISHED_AUDIT_R1_PREIMAGE_PATHS)\n  def changed(path,limit):\n   raw=original(path,limit)\n   return raw+b' ' if path==d.ROOT/name else raw\n  with mock.patch.object(d,'safe_bytes',side_effect=changed),self.assertRaisesRegex(ValueError,'HISTORICAL_SOURCE_FULL_CLOSURE'):published_audit_r1_preimages()\n\n# AUDIT_R2_52B883_PREIMAGES_END\n\nclass NarrowAuditR1IntegrationTests"), (' def test_current_request_manifest_and_payload_are_exact(self):\n', ' def test_published_audit_r1_request_source_and_payload_preimages_are_exact(self):\n  preimages=published_audit_r1_preimages()\n'), ("\n  self.assertEqual(d.sha(raw),request['filesManifestSha256']);self.assertEqual(d.sha((d.ROOT/d.SOURCE_STATE).read_bytes()),request['sourceStateSha256'])", "\n  self.assertEqual(d.sha(raw),request['filesManifestSha256']);self.assertEqual(d.sha(preimages[d.SOURCE_STATE]),request['sourceStateSha256'])"), ("\n   self.assertEqual(d.sha(path.read_bytes()),row['sha256'],row['path']);self.assertEqual(path.stat().st_size,row['size'],row['path'])", "\n   original=published_audit_r1_bytes(row['path'],preimages)\n   self.assertEqual(d.sha(original),row['sha256'],row['path']);self.assertEqual(len(original),row['size'],row['path'])"), ('\n   text=(Path(d.__file__).parent/name).read_text()', "\n   text=published_audit_r1_bytes('tasks/desert-rv/scripts/'+name,published_audit_r1_preimages()).decode()")]}
  for name,expected in pins.items():
   text=(Path(d.__file__).parent/name).read_text()
   for before,after in reversed(changes[name]):
    self.assertEqual(text.count(after),1,(name,after[:80]));text=text.replace(after,before)
   self.assertEqual(d.sha(text.encode()),expected,name)
 def test_prior_fixtures_are_byte_identical(self):
  self.assertEqual(d.sha((d.ROOT/'tasks/desert-rv/scripts/fixtures/environment-v4-r4-published-d1a57497.json').read_bytes()),'aff273fbe5201322bc523fd7eb7061ec8633977a352579563d0cba4824690094')
  self.assertEqual(d.sha((d.ROOT/'tasks/desert-rv/scripts/fixtures/environment-v4-r4-audit-published-fa18f216.json').read_bytes()),'2b92cd3a940a81892d3b342371e5c875248265f8c7e9925e0a9030f90b4ce359')
class AuditR2FinalControlTests(unittest.TestCase):
 def test_current_request_manifest_and_payload_are_exact(self):
  request=d.parse_request((d.ROOT/d.REQUEST).read_bytes());raw=(d.ROOT/d.MANIFEST).read_bytes();manifest=d.parse_manifest(raw)
  self.assertEqual(d.sha(raw),request['filesManifestSha256']);self.assertEqual(d.sha((d.ROOT/d.SOURCE_STATE).read_bytes()),request['sourceStateSha256'])
  self.assertEqual(d.sha((d.ROOT/d.CANDIDATE).read_bytes()),d.CANDIDATE_SHA)
  for row in manifest['files']:
   path=d.ROOT/row['path'];self.assertTrue(path.is_file());self.assertFalse(path.is_symlink())
   self.assertEqual(d.sha(path.read_bytes()),row['sha256'],row['path']);self.assertEqual(path.stat().st_size,row['size'],row['path'])
 def test_no_current_or_historical_control_cycle(self):
  manifest=d.parse_manifest((d.ROOT/d.MANIFEST).read_bytes());payload={row['path'] for row in manifest['files']}
  state=json.loads((d.ROOT/d.SOURCE_STATE).read_text());covered={row['path'] for row in state['files']}
  self.assertFalse(payload & {d.REQUEST,d.MANIFEST,d.SOURCE_STATE})
  self.assertTrue({d.MANIFEST,d.WORKFLOW,d.CANDIDATE}<=covered);self.assertFalse(covered & {d.REQUEST,d.SOURCE_STATE})
  self.assertTrue(payload<=covered)
  import test_environment_v4_r4_audit_r1_dispatch as historical
  preimages=historical.published_audit_r1_preimages()
  self.assertEqual(d.sha(preimages[d.SOURCE_STATE]),historical.PUBLISHED_AUDIT_R1_SOURCE_SHA)
  self.assertNotEqual(d.sha((d.ROOT/d.SOURCE_STATE).read_bytes()),historical.PUBLISHED_AUDIT_R1_SOURCE_SHA)
 def test_52b883_fixture_has_only_changed_old_payload_overlap_plus_source(self):
  import test_environment_v4_r4_audit_r1_dispatch as historical
  old=historical.d.parse_manifest((d.ROOT/historical.d.MANIFEST).read_bytes())
  old_payload={row['path'] for row in old['files']}
  self.assertEqual(historical.PUBLISHED_AUDIT_R1_PREIMAGE_PATHS,(set(d.PAYLOAD_PATHS)&old_payload)|{d.SOURCE_STATE})
 def test_current_source_closed_set_is_not_historical(self):
  import verify_evidence as evidence
  evidence.verify_source_state()
 def test_every_csharp_and_native_strict_source_retains_published_hash(self):
  import test_environment_v4_r4_audit_r1_dispatch as historical
  original=json.loads(historical.published_audit_r1_preimages()[d.SOURCE_STATE])
  names={row['path']:row for row in original['files'] if row['path'].endswith('.cs') or row['path'].endswith('/environment_v4_r4_evidence.py') or row['path'].endswith('/environment_v4_evidence.py')}
  self.assertTrue(names)
  for name,row in names.items():self.assertEqual(d.sha((d.ROOT/name).read_bytes()),row['sha256'],name)

class ReadinessWorkflowTests(unittest.TestCase):
 def setUp(self):self.workflow=(d.ROOT/d.WORKFLOW).read_text()
 def section(self,start,end):return self.workflow.split('      - name: '+start+'\n',1)[1].split('      - name: '+end+'\n',1)[0]
 def test_gate_is_immediately_after_checkout_and_fixed_identity(self):
  names=re.findall(r'^      - (?:name: (.+)|uses: (.+))$',self.workflow,re.M)
  names=[a or b for a,b in names]
  self.assertTrue(names[0].startswith('actions/checkout@'))
  self.assertEqual(names[1:6],['Verify this exact independent R4 audit R2 fixed-push request','Observe fixed image HEAD and conditionally pull once on this runner','Validate the single sanitized readiness report before upload','Upload only the schema-validated readiness report','Install bounded image validator from official Ubuntu packages'])
 def test_full_source_and_clean_output_guard_runs_before_readiness(self):
  prefix=self.workflow.split('      - name: Observe fixed image HEAD and conditionally pull once on this runner\n',1)[0]
  self.assertIn('        run: |\n          /usr/bin/python3 tasks/desert-rv/scripts/environment_v4_r4_audit_r2_dispatch.py\n          /usr/bin/python3 tasks/desert-rv/scripts/verify_evidence.py guard\n',prefix)
  self.assertEqual(self.workflow.count('/usr/bin/python3 tasks/desert-rv/scripts/verify_evidence.py guard'),2)
  import ast,sys
  parsed=ast.parse((d.ROOT/'tasks/desert-rv/scripts/verify_evidence.py').read_text())
  imports=[name.name.split('.')[0] for node in parsed.body if isinstance(node,ast.Import) for name in node.names]
  imports += [node.module.split('.')[0] for node in parsed.body if isinstance(node,ast.ImportFrom)]
  self.assertTrue(set(imports)<=sys.stdlib_module_names)
 def test_readiness_has_no_early_secret_or_installs_or_alternate_image(self):
  prefix=self.workflow.split('      - name: Install bounded image validator',1)[0]
  for forbidden in ('secrets.','apt-get','docker build','docker pull','UNITY_','continue-on-error:','sudo ','/evidence/'):
   self.assertNotIn(forbidden,prefix)
  block=self.section('Observe fixed image HEAD and conditionally pull once on this runner','Validate the single sanitized readiness report before upload')
  self.assertEqual(block,"        id: image_readiness\n        run: |\n          test ! -e tasks/desert-rv/image-readiness.json\n          test ! -L tasks/desert-rv/image-readiness.json\n          status=0\n          /usr/bin/python3 tasks/desert-rv/scripts/environment_image_precheck.py > tasks/desert-rv/image-readiness.json || status=$?\n          echo 'report_written=true' >> \"$GITHUB_OUTPUT\"\n          exit \"$status\"\n")
 def test_schema_upload_require_actual_step_and_no_cancel(self):
  self.assertIn("if: ${{ !cancelled() && steps.image_readiness.outputs.report_written == 'true' && (steps.image_readiness.outcome == 'success' || steps.image_readiness.outcome == 'failure') }}",self.workflow)
  self.assertIn("if: ${{ !cancelled() && steps.image_readiness.outputs.report_written == 'true' && (steps.image_readiness.outcome == 'success' || steps.image_readiness.outcome == 'failure') && steps.image_readiness_schema.outcome == 'success' }}",self.workflow)
  schema=self.section('Validate the single sanitized readiness report before upload','Upload only the schema-validated readiness report')
  self.assertIn('from environment_image_precheck import validate_report',schema)
  self.assertIn('if validate_report(report) is not True:',schema)
  self.assertIn("(report['status'] == 'PASS') != (outcome == 'success')",schema)
  self.assertIn('object_pairs_hook=unique, parse_constant=reject_constant',schema)
  self.assertIn('info.st_size <= 8192',schema)
  self.assertIn('is_symlink()',schema)
  self.assertNotIn('print(report',schema);self.assertNotIn('print(raw',schema)
 def test_old_post_gate_steps_reverse_to_exact_workflow_suffix(self):
  original=(d.ROOT/'.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml').read_text()
  anchor='      - name: Install bounded image validator from official Ubuntu packages\n'
  suffix=self.workflow.split(anchor,1)[1]
  for name in ('test_environment_v4_r4_audit_r2_dispatch.py','test_environment_v4_r4_audit_r2_runner_prefix.py','test_environment_image_precheck.py'):
   line='          /usr/bin/python3 tasks/desert-rv/scripts/'+name+'\n'
   self.assertEqual(suffix.count(line),1);suffix=suffix.replace(line,'')
  suffix=suffix.replace('name: desert-rv-environment-v4-r4-audit-r2-STRICT-','name: desert-rv-environment-v4-r4-audit-r1-STRICT-').replace('name: desert-rv-environment-v4-r4-audit-r2-LIFECYCLE-DIAGNOSTIC-','name: desert-rv-environment-v4-r4-audit-r1-LIFECYCLE-DIAGNOSTIC-')
  self.assertEqual(suffix,original.split(anchor,1)[1])
 def test_docker_build_remains_original_exact_pinned_bytes(self):
  original=(d.ROOT/'.github/workflows/desert-rv-environment-v4-r4-audit-r1.yml').read_text()
  start='      - name: Prepare software OpenGL on pinned official GameCI editor\n';end='      - name: Execute separate native EditorRender author and capture entry\n'
  self.assertEqual(self.workflow.split(start,1)[1].split(end,1)[0],original.split(start,1)[1].split(end,1)[0])
  self.assertEqual(self.workflow.count('docker build'),1)
  self.assertNotIn('docker pull',self.workflow)

class ReadinessReportUploadValidationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  target=self.root/'tasks/desert-rv/scripts';target.mkdir(parents=True)
  target.joinpath('environment_image_precheck.py').write_bytes((d.ROOT/'tasks/desert-rv/scripts/environment_image_precheck.py').read_bytes())
  self.path=self.root/'tasks/desert-rv/image-readiness.json'
  workflow=(d.ROOT/d.WORKFLOW).read_text()
  section=workflow.split('      - name: Validate the single sanitized readiness report before upload\n',1)[1].split('      - name: Upload only the schema-validated readiness report\n',1)[0]
  self.code=section.split("          /usr/bin/python3 - <<'PY'\n",1)[1].rsplit('          PY\n',1)[0]
  self.code='\n'.join(line[10:] for line in self.code.splitlines())+'\n'
  self.report=dict(schemaVersion=4,status='PASS',reason='CACHE_HIT',image='unityci/editor@sha256:17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264',digest='sha256:17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264',cacheHit=True,limit=None,remaining=None,windowSeconds=None,retryAfter=None,checkedAt='2026-10-09T21:00:00Z',target=self.channel(False),quota=self.channel(True),pull=dict(attempted=False,currentStage='NOT_STARTED',outcome='NOT_ATTEMPTED',exitCode=None,cacheVerified=False,failureClass='NOT_CHECKED'))
 def channel(self,quota):
  return dict(complete=False,currentStage='NOT_STARTED',httpStatus=None,reason='NOT_STARTED',headers=dict(safety='NOT_CHECKED',digest='NOT_APPLICABLE' if quota else 'NOT_CHECKED',limit='NOT_CHECKED',remaining='NOT_CHECKED',challenge='NOT_CHECKED'),rateDiagnostics=self.diagnostics())
 def target_verified(self):
  return dict(complete=True,currentStage='AUTHENTICATED_HEAD',httpStatus=200,reason='TARGET_VERIFIED',headers=dict(safety='VALID',digest='VALID',limit='MISSING',remaining='MISSING',challenge='MISSING'),rateDiagnostics=self.diagnostics('NONE',observed=True))
 def preview_positive(self):
  return dict(complete=True,currentStage='AUTHENTICATED_HEAD',httpStatus=200,reason='QUOTA_AVAILABLE',headers=dict(safety='VALID',digest='NOT_APPLICABLE',limit='VALID',remaining='VALID',challenge='MISSING'),rateDiagnostics=self.diagnostics('NONE','100;w=21600','1;w=21600',True))
 def pull_report(self,success=True):
  self.report.update(status='PASS' if success else 'RATE_LIMITED',reason='PULL_SUCCEEDED' if success else 'PULL_RATE_LIMITED',cacheHit=False,target=self.target_verified(),quota=dict(complete=False,currentStage='AUTHENTICATED_HEAD',httpStatus=200,reason='QUOTA_HEADERS_ABSENT',headers=dict(safety='VALID',digest='NOT_APPLICABLE',limit='MISSING',remaining='MISSING',challenge='MISSING'),rateDiagnostics=self.diagnostics('QUOTA_BOTH_HEADERS_MISSING',observed=True)),pull=dict(attempted=True,currentStage='COMPLETE' if success else 'PULL',outcome='SUCCESS' if success else 'NONZERO_EXIT',exitCode=0 if success else 1,cacheVerified=success,failureClass='NONE' if success else 'DOCKER_RATE_LIMITED'))
 def diagnostics(self,predicate='NOT_EVALUATED',limit=None,remaining=None,observed=False):
  def diagnostic(raw):
   blank=dict(occurrenceCount=None,lengthBytes=None,sha256=None,format='NOT_OBSERVED',gateCompatibility='NOT_EVALUATED',boundedRaw=None,policies=[])
   if not observed:return blank
   if raw is None:return dict(blank,occurrenceCount=0,lengthBytes=0,format='MISSING',gateCompatibility='MISSING')
   numeric=re.fullmatch(r'(?:0|[1-9][0-9]{0,8});w=21600',raw)
   return dict(occurrenceCount=1,lengthBytes=len(raw.encode()),sha256=hashlib.sha256(raw.encode()).hexdigest(),format='NUMERIC_SINGLE' if numeric else 'UNKNOWN_SYNTAX',gateCompatibility='STRICT_FORMAT_MATCH' if numeric else 'UNKNOWN_SYNTAX',boundedRaw=raw,policies=[dict(value=int(raw.split(';')[0]),windowSeconds=21600)] if numeric else [])
  return dict(firstFailedPredicate=predicate,limit=diagnostic(limit),remaining=diagnostic(remaining))
 def run_validator(self,outcome='success',raw=None,write=True):
  import sys
  if write:self.path.write_bytes(raw if raw is not None else (json.dumps(self.report,separators=(',',':'))+'\n').encode())
  env={k:v for k,v in os.environ.items() if not k.startswith(('GITHUB_','RUNNER_','UNITY_'))};env['READINESS_OUTCOME']=outcome
  return subprocess.run([sys.executable,'-c',self.code],cwd=self.root,env=env,capture_output=True,text=True)
 def rejected(self,**kw):
  result=self.run_validator(**kw);self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,'');self.assertEqual(result.stderr,'IMAGE_READINESS_REPORT_REJECTED\n')
 def test_exact_cache_pass_upload_validation(self):
  result=self.run_validator();self.assertEqual(result.returncode,0);self.assertEqual(result.stdout+result.stderr,'')
 def test_exact_remote_pass_upload_validation(self):
  self.report.update(reason='READY',cacheHit=False,limit=100,remaining=1,windowSeconds=21600,target=self.target_verified(),quota=self.preview_positive())
  self.assertEqual(self.run_validator().returncode,0)
 def test_safe_unknown_failure_report_can_be_uploaded(self):
  self.report.update(status='UNKNOWN',reason='NOT_STARTED',cacheHit=False)
  self.assertEqual(self.run_validator(outcome='failure').returncode,0)
 def test_safe_429_failure_report_can_be_uploaded(self):
  self.report.update(status='RATE_LIMITED',reason='TARGET_RATE_LIMITED',cacheHit=False,target=dict(complete=False,currentStage='INITIAL_HEAD',httpStatus=429,reason='HTTP_RATE_LIMITED',headers=dict(safety='VALID',digest='MISSING',limit='MISSING',remaining='MISSING',challenge='MISSING'),rateDiagnostics=self.diagnostics('HTTP_STATUS_429',observed=True)))
  self.assertEqual(self.run_validator(outcome='failure').returncode,0)
 def test_deleted_report_prevents_upload(self):self.rejected(write=False)
 def test_empty_report_prevents_upload(self):self.rejected(raw=b'')
 def test_non_json_prevents_upload_without_echoing_input(self):self.rejected(raw=b'SECRET_RAW_HEADER\n')
 def test_unknown_field_prevents_upload(self):self.report['authorization']='SECRET';self.rejected()
 def test_unknown_status_prevents_upload(self):self.report['status']='SECRET';self.rejected()
 def test_extra_newline_prevents_upload(self):self.rejected(raw=(json.dumps(self.report)+'\n\n').encode())
 def test_missing_newline_prevents_upload(self):self.rejected(raw=json.dumps(self.report).encode())
 def test_duplicate_json_key_prevents_upload(self):
  self.rejected(raw=(json.dumps(self.report)[:-1]+',"status":"PASS"}\n').encode())
 def test_nonfinite_json_prevents_upload(self):
  self.rejected(raw=(json.dumps(self.report).replace('"limit": null','"limit": NaN')+'\n').encode())
 def test_oversized_json_prevents_upload(self):self.rejected(raw=b' '*8192+b'\n')
 def test_file_symlink_prevents_upload(self):
  target=self.root/'other.json';target.write_text(json.dumps(self.report)+'\n');self.path.symlink_to(target);self.rejected(write=False)
 def test_parent_symlink_prevents_upload(self):
  import shutil
  original=self.root/'tasks/desert-rv';target=self.root/'target';shutil.move(str(original),str(target));original.symlink_to(target,target_is_directory=True);self.rejected()
 def test_directory_instead_of_file_prevents_upload(self):self.path.mkdir();self.rejected(write=False)
 def test_bool_schema_prevents_upload(self):self.report['schemaVersion']=True;self.rejected()
 def test_mismatched_image_prevents_upload(self):self.report['image']='attacker/image:latest';self.rejected()
 def test_mismatched_digest_prevents_upload(self):self.report['digest']='sha256:'+'0'*64;self.rejected()
 def test_raw_retry_after_prevents_upload(self):self.report['retryAfter']='SECRET_HEADER';self.rejected()
 def test_failure_outcome_cannot_upload_pass_report(self):self.rejected(outcome='failure')
 def test_success_outcome_cannot_upload_failure_report(self):self.report.update(status='UNKNOWN',reason='NOT_STARTED',cacheHit=False);self.rejected()
 def test_skipped_outcome_cannot_upload_preexisting_report(self):self.rejected(outcome='skipped')
 def test_cancelled_outcome_cannot_upload_preexisting_report(self):self.rejected(outcome='cancelled')
 def test_empty_outcome_cannot_upload_preexisting_report(self):self.rejected(outcome='')
 def test_invalid_utc_time_prevents_upload(self):self.report['checkedAt']='SECRET';self.rejected()

 def run_readiness_shell(self,exit_code,raw=None):
  workflow=(d.ROOT/d.WORKFLOW).read_text()
  section=workflow.split('      - name: Observe fixed image HEAD and conditionally pull once on this runner\n',1)[1].split('      - name: Validate the single sanitized readiness report before upload\n',1)[0]
  script='\n'.join(line[10:] for line in section.split('        run: |\n',1)[1].splitlines())+'\n'
  helper=self.root/'tasks/desert-rv/scripts/environment_image_precheck.py';original=helper.read_bytes()
  if raw is None:raw=(json.dumps(self.report,separators=(',',':'))+'\n').encode()
  helper.write_text("from pathlib import Path\nimport sys\nPath('helper-called').write_text('yes')\nsys.stdout.buffer.write("+repr(raw)+")\nraise SystemExit("+repr(exit_code)+")\n")
  output=self.root/'step-output';output.write_text('')
  env={k:v for k,v in os.environ.items() if not k.startswith(('GITHUB_','RUNNER_','UNITY_'))};env['GITHUB_OUTPUT']=str(output)
  try:result=subprocess.run(['bash','--noprofile','--norc','-e','-o','pipefail','-c',script],cwd=self.root,env=env,capture_output=True,text=True)
  finally:helper.write_bytes(original)
  written='report_written=true' in output.read_text().splitlines()
  return result,written,(self.root/'helper-called').exists()
 def test_existing_unknown_report_has_no_written_marker_or_upload_eligibility(self):
  self.report.update(status='UNKNOWN',reason='NOT_STARTED',cacheHit=False)
  self.path.write_text(json.dumps(self.report)+'\n');old=self.path.read_bytes()
  result,written,called=self.run_readiness_shell(2)
  self.assertNotEqual(result.returncode,0);self.assertFalse(written);self.assertFalse(called);self.assertEqual(self.path.read_bytes(),old)
  # Even a schema-valid old failure report cannot meet either workflow's written-output gate.
  self.assertEqual(self.run_validator(outcome='failure',write=False).returncode,0)
 def test_existing_pass_report_has_no_written_marker_or_upload_eligibility(self):
  self.path.write_text(json.dumps(self.report)+'\n');old=self.path.read_bytes()
  result,written,called=self.run_readiness_shell(0)
  self.assertNotEqual(result.returncode,0);self.assertFalse(written);self.assertFalse(called);self.assertEqual(self.path.read_bytes(),old)
 def test_new_unknown_report_has_written_marker_and_safe_export_but_failed_status(self):
  self.report.update(status='UNKNOWN',reason='NOT_STARTED',cacheHit=False)
  result,written,called=self.run_readiness_shell(2)
  self.assertEqual(result.returncode,2);self.assertTrue(written);self.assertTrue(called);self.assertEqual(result.stdout+result.stderr,'')
  self.assertEqual(self.run_validator(outcome='failure',write=False).returncode,0)
 def test_new_pass_report_has_written_marker_and_safe_export(self):
  result,written,called=self.run_readiness_shell(0)
  self.assertEqual(result.returncode,0);self.assertTrue(written);self.assertTrue(called)
  self.assertEqual(self.run_validator(outcome='success',write=False).returncode,0)
 def test_new_empty_report_has_written_marker_but_cannot_upload(self):
  result,written,called=self.run_readiness_shell(2,raw=b'')
  self.assertEqual(result.returncode,2);self.assertTrue(written);self.assertTrue(called);self.rejected(outcome='failure',write=False)
 def test_helper_failure_status_is_preserved_without_continue_on_error(self):
  self.report.update(status='UNKNOWN',reason='NOT_STARTED',cacheHit=False)
  result,written,called=self.run_readiness_shell(91)
  self.assertEqual(result.returncode,91);self.assertTrue(written);self.assertTrue(called)
  self.assertEqual(self.run_validator(outcome='failure',write=False).returncode,0)

 def test_schema_v1_prevents_upload(self):self.report['schemaVersion']=1;self.rejected()
 def test_legacy_top_level_http_status_prevents_upload(self):self.report['httpStatus']=200;self.rejected()
 def test_unknown_channel_field_prevents_upload(self):self.report['target']['rawHeaders']='SECRET';self.rejected()
 def test_unknown_pull_field_prevents_upload(self):self.report['pull']['stderr']='SECRET';self.rejected()
 def test_pull_success_schema_and_real_shell_outcome_match(self):
  self.pull_report()
  result,written,called=self.run_readiness_shell(0)
  self.assertEqual(result.returncode,0);self.assertTrue(written);self.assertTrue(called)
  self.assertEqual(self.run_validator(outcome='success',write=False).returncode,0)
 def test_pull_rate_limit_schema_and_real_shell_outcome_match(self):
  self.pull_report(False)
  result,written,called=self.run_readiness_shell(2)
  self.assertEqual(result.returncode,2);self.assertTrue(written);self.assertTrue(called)
  self.assertEqual(self.run_validator(outcome='failure',write=False).returncode,0)
 def test_pull_success_cannot_match_failure_outcome(self):self.pull_report();self.rejected(outcome='failure')
 def test_pull_rate_limit_cannot_match_success_outcome(self):self.pull_report(False);self.rejected(outcome='success')
 def test_pull_success_without_verified_cache_prevents_upload(self):self.pull_report();self.report['pull']['cacheVerified']=False;self.rejected()
 def test_pull_success_with_nonzero_exit_prevents_upload(self):self.pull_report();self.report['pull']['exitCode']=1;self.rejected()

 def test_schema_v2_prevents_upload(self):
  self.report['schemaVersion']=2
  result,written,called=self.run_readiness_shell(0)
  self.assertEqual(result.returncode,0);self.assertTrue(written);self.assertTrue(called)
  self.rejected(outcome='success',write=False)
 def test_absent_rate_diagnostics_prevents_upload(self):del self.report['target']['rateDiagnostics'];self.rejected()
 def test_diagnostic_unknown_field_prevents_upload(self):self.report['target']['rateDiagnostics']['rawHeaders']='SECRET';self.rejected()
 def test_diagnostic_unknown_predicate_prevents_upload(self):self.report['target']['rateDiagnostics']['firstFailedPredicate']='SECRET';self.rejected()
 def test_real_large_safe_diagnostic_survives_shell_and_schema_gate(self):
  import environment_image_precheck as precheck
  import socket
  raw_value='\\'*256
  responses={precheck.Route.TARGET:precheck.Response(200,(('Docker-Content-Digest',precheck.DIGEST),('RateLimit-Limit','999999999;w=21600'),('RateLimit-Remaining','999999999;w=21600'))),precheck.Route.QUOTA:precheck.Response(200,(('RateLimit-Limit',raw_value),('RateLimit-Remaining',raw_value)))}
  client=mock.Mock();client.head.side_effect=lambda route,token=None:responses[route]
  with mock.patch.object(socket,'create_connection',side_effect=AssertionError('NETWORK_FORBIDDEN')),mock.patch.object(precheck.subprocess,'Popen',side_effect=AssertionError('DOCKER_FORBIDDEN')),mock.patch.object(precheck,'daemon_ready',return_value=True),mock.patch.object(precheck,'cache_hit',return_value=False),mock.patch.object(precheck,'RegistryClient',return_value=client),mock.patch.dict(os.environ,{name:'' for name in precheck.BLOCKED_ENV}):
   self.report=precheck.probe()
  self.assertEqual(client.head.call_count,2);self.assertEqual(self.report['status'],'UNKNOWN')
  self.assertEqual(self.report['quota']['rateDiagnostics']['firstFailedPredicate'],'LIMIT_STRICT_REGEX')
  self.assertFalse(self.report['pull']['attempted'])
  raw=(json.dumps(self.report,sort_keys=True,separators=(',',':'))+'\n').encode()
  self.assertGreater(len(raw),2048);self.assertLessEqual(len(raw),8192)
  result,written,called=self.run_readiness_shell(2,raw=raw)
  self.assertEqual(result.returncode,2);self.assertTrue(written);self.assertTrue(called)
  self.assertEqual(self.run_validator(outcome='failure',write=False).returncode,0)
 def test_exact_8192_byte_safe_json_including_lf_is_allowed(self):
  raw=json.dumps(self.report,sort_keys=True,separators=(',',':')).encode()
  raw+=b' '*(8191-len(raw))+b'\n';self.assertEqual(len(raw),8192)
  self.assertEqual(self.run_validator(raw=raw).returncode,0)
 def test_8193_byte_json_including_lf_prevents_upload(self):
  raw=json.dumps(self.report,sort_keys=True,separators=(',',':')).encode()
  raw+=b' '*(8192-len(raw))+b'\n';self.assertEqual(len(raw),8193)
  result,written,called=self.run_readiness_shell(0,raw=raw)
  self.assertEqual(result.returncode,0);self.assertTrue(written);self.assertTrue(called)
  self.rejected(outcome='success',write=False)

 def test_schema_v3_prevents_upload(self):
  self.report['schemaVersion']=3
  result,written,called=self.run_readiness_shell(0)
  self.assertEqual(result.returncode,0);self.assertTrue(written);self.assertTrue(called)
  self.rejected(outcome='success',write=False)
 def actual_positive_window_report(self,target_window,preview_window):
  import environment_image_precheck as precheck
  import socket
  target_headers=(('Docker-Content-Digest',precheck.DIGEST),('RateLimit-Limit','100;w='+str(target_window)),('RateLimit-Remaining','100;w='+str(target_window)))
  preview_headers=(('RateLimit-Limit','100;w='+str(preview_window)),('RateLimit-Remaining','20;w='+str(preview_window)))
  responses={precheck.Route.TARGET:precheck.Response(200,target_headers),precheck.Route.QUOTA:precheck.Response(200,preview_headers)}
  client=mock.Mock();client.head.side_effect=lambda route,token=None:responses[route]
  with mock.patch.object(socket,'create_connection',side_effect=AssertionError('NETWORK_FORBIDDEN')),mock.patch.object(precheck.subprocess,'Popen',side_effect=AssertionError('DOCKER_FORBIDDEN')),mock.patch.object(precheck,'daemon_ready',return_value=True),mock.patch.object(precheck,'cache_hit',return_value=False),mock.patch.object(precheck,'RegistryClient',return_value=client),mock.patch.dict(os.environ,{name:'' for name in precheck.BLOCKED_ENV}):
   self.report=precheck.probe()
  self.assertEqual(client.head.call_count,2);self.assertEqual(self.report['status'],'PASS');self.assertEqual(self.report['reason'],'READY')
  self.assertEqual(self.report['windowSeconds'],preview_window);self.assertFalse(self.report['pull']['attempted'])
  self.assertEqual(self.report['target']['rateDiagnostics']['limit']['boundedRaw'],'100;w='+str(target_window))
  self.assertEqual(self.report['quota']['rateDiagnostics']['remaining']['boundedRaw'],'20;w='+str(preview_window))
  result,written,called=self.run_readiness_shell(0)
  self.assertEqual(result.returncode,0);self.assertTrue(written);self.assertTrue(called)
  self.assertEqual(self.run_validator(outcome='success',write=False).returncode,0)
 def test_actual_3600_target_and_21600_preview_pass_real_shell_gate(self):self.actual_positive_window_report(3600,21600)
 def test_actual_21600_target_and_3600_preview_report_actual_window(self):self.actual_positive_window_report(21600,3600)

class CurrentReadinessSourceTests(unittest.TestCase):
 def test_each_new_readiness_file_is_in_actual_source_inventory(self):
  import verify_evidence as evidence
  state=evidence.verify_source_state();rows={row['path']:row for row in state['files']}
  names=['tasks/desert-rv/scripts/environment_image_precheck.py','tasks/desert-rv/scripts/test_environment_image_precheck.py','tasks/desert-rv/art/environment-v4/image-readiness/README.md']
  for name in names:
   raw=(d.ROOT/name).read_bytes();self.assertIn(name,rows);self.assertEqual(d.sha(raw),rows[name]['sha256']);self.assertEqual(len(raw),rows[name]['size'])
 def test_each_new_readiness_member_tamper_is_rejected_without_historical_fallback(self):
  import verify_evidence as evidence
  original=evidence.sha
  names=['tasks/desert-rv/scripts/environment_image_precheck.py','tasks/desert-rv/scripts/test_environment_image_precheck.py','tasks/desert-rv/art/environment-v4/image-readiness/README.md']
  for name in names:
   target=d.ROOT/name
   def changed(path):return '0'*64 if Path(path)==target else original(path)
   with self.subTest(path=name),mock.patch.object(evidence,'sha',side_effect=changed),self.assertRaisesRegex(ValueError,'Current source bytes differ'):evidence.verify_source_state()

if __name__=='__main__':unittest.main()
