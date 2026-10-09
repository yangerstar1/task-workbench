"""Closed R4 twenty-view production terrain push fixtures, including actual Git parent/blob/mode checks. No network or dispatch."""
import copy,hashlib,json,os,re,subprocess,tempfile,unittest
from pathlib import Path
from unittest import mock
import environment_v4_r4_audit_dispatch as d

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
  with self.assertRaisesRegex(ValueError,'ENVIRONMENT_V4_R4_AUDIT_DISPATCH_'+code):self.check(**kwargs)
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

class NarrowAuditIntegrationTests(unittest.TestCase):
 def test_only_exact_guard_insertions(self):
  text=(Path(d.__file__).parent/'verify_evidence.py').read_text()
  self.assertEqual(text.count(", '.github/workflows/desert-rv-environment-v4-r4-audit.yml', '.github/dispatch/desert-rv-environment-v4-r4-audit-20261009-files.json'"),1);text=text.replace(", '.github/workflows/desert-rv-environment-v4-r4-audit.yml', '.github/dispatch/desert-rv-environment-v4-r4-audit-20261009-files.json'",'')
  self.assertEqual(text.count("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main':\n            import environment_v4_r4_audit_dispatch\n            environment_v4_r4_audit_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 phase audit; strict package unchanged.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main':"),1);text=text.replace("        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main':\n            import environment_v4_r4_audit_dispatch\n            environment_v4_r4_audit_dispatch.verify(ROOT, os.environ)  # Independent fixed R4 phase audit; strict package unchanged.\n        elif os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main':","        if os.environ.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main':")
  self.assertEqual(d.sha(text.encode()),'ff6b8936a154ed215c1ab24dd719df867f806118eefcd209b112d2294615905e')
 def test_only_exact_runner_insertions(self):
  text=(Path(d.__file__).parent/'prepare_runner.sh').read_text()
  self.assertEqual(text.count('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\' ]]; then'),1);text=text.replace('  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4-audit.yml@refs/heads/main\' ]]; then\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/environment_v4_r4_audit_dispatch.py" --verify-only\n  elif [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\' ]]; then','  if [[ "${GITHUB_WORKFLOW_REF:-}" == \'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main\' ]]; then')
  self.assertEqual(d.sha(text.encode()),'575db6430f48e29b8ff98a49bb1c2565889d6f29695b2222203bcaab4dae4f17')

class AuditWorkflowTests(unittest.TestCase):
 def setUp(self):self.workflow=(d.ROOT/d.WORKFLOW).read_text()
 def test_prior_twenty_camera_native_entry_and_resources_are_exact(self):
  original=(d.ROOT/'.github/workflows/desert-rv-environment-v4-r4.yml').read_text()
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
 def test_all_old_tests_and_three_audit_suites_are_retained(self):
  original=(d.ROOT/'.github/workflows/desert-rv-environment-v4-r4.yml').read_text()
  def commands(text):return text.split('      - name: Validate guards and safety contracts\n',1)[1].split('      - name: Restore exact checkpoint font',1)[0].splitlines()[1:]
  additions=['          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_r4_audit_dispatch.py','          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_r4_audit_runner_prefix.py','          /usr/bin/python3 tasks/desert-rv/scripts/test_environment_v4_r4_audit.py']
  self.assertEqual(commands(self.workflow),commands(original)+additions)
 def test_only_exact_artifact_paths_and_upload_count(self):
  paths=re.findall(r'^          path: (.+)$',self.workflow,re.M)
  self.assertEqual(paths,['tasks/desert-rv/evidence/environment-v4-r4/','tasks/desert-rv/evidence/environment-v4-r4-audit/','tasks/desert-rv/evidence/environment-source-diagnostic/protected-source-failure.json','tasks/desert-rv/evidence/environment-package-diagnostic/unity-package-resolution.json'])
  self.assertEqual(self.workflow.count('uses: actions/upload-artifact@'),4)
  self.assertIn('name: desert-rv-environment-v4-r4-audit-LIFECYCLE-DIAGNOSTIC-',self.workflow)
  import environment_v4_r4_audit as audit
  self.assertEqual(audit.OUT,d.ROOT/'tasks/desert-rv/evidence/environment-v4-r4-audit')
  for forbidden in ('Unity.log','artifacts/environment/','JourneyEvidence/','generated/'):
   self.assertFalse(any(forbidden in path for path in paths))
 def test_every_prior_authorization_file_is_byte_identical(self):
  pins={'.github/dispatch/armored-v004-r1-discovery-20261009-once-69a502dd-files.json': 'f44f8c24ea4ae4656a60dd90f9a82f50d7a666c9e438973a211448e17173e242', '.github/dispatch/armored-v004-r1-discovery-20261009-once-69a502dd.json': 'f410c5744988ab33ce0d39cc9e5f438d3254250976cc3d885123f573f8b57bae', '.github/dispatch/armored-v004-r1-strict-20261009-once-c8521e4b-files.json': '7107fa05cbc12706b4545595deaeab6ced546e46cd474d1f9e2e8355ee315043', '.github/dispatch/armored-v004-r1-strict-20261009-once-c8521e4b.json': 'a8b01a16c0e06719720aa198ecdfe915ffb246e0a47d926ad08b078df2130440', '.github/dispatch/desert-rv-armored-v004-r1-static-20261009.json': 'dff22bd4d1dacc76f5c379d11614b74fca6940ff236e06de1074e63a6df353ac', '.github/dispatch/desert-rv-armored-v004-r1-technical-20261009.json': 'b2835cb6038b7d41f30c9fcd4c042cd7517f54afbd9a49185c7fd4088599a7d1', '.github/dispatch/desert-rv-armored-v004-static-20261009.json': '6ccb20b76a191feab4bc16ab3f5911dfb237d88582059c4b3744b824b76fe4b7', '.github/dispatch/desert-rv-environment-diffuse-comparison-20261009-files.json': 'a571d25aa79a85f50488be98b5bfb1c14815375753ed4ad224bb41ac7f437093', '.github/dispatch/desert-rv-environment-diffuse-comparison-20261009.json': '1386a3b6dfb746cc76542ae9172ab9afa79f5e54c8910ebfbaff18a7012bfb69', '.github/dispatch/desert-rv-environment-diffuse-comparison-r1-20261009-files.json': 'e26ec76f89d79506c248b92ddaba3fce190db8084d71c04466d3f11051627570', '.github/dispatch/desert-rv-environment-diffuse-comparison-r1-20261009.json': 'ccae6bbcaa49b2acb358f9455dfb4f476c1e75445cfad6f2c4f6ff036920fe34', '.github/dispatch/desert-rv-environment-terrain-probe-20261009-files.json': '4e7484ee6d3624acc5c964fd542d4050779b7129236353f1381bc10ef57fe9e8', '.github/dispatch/desert-rv-environment-terrain-probe-20261009.json': 'bca0375e55b6da13c94907d351f3754620b3dcfe15ccd27776200d5384c2e52e', '.github/dispatch/desert-rv-environment-v4-20261009-files.json': 'fc0a8a0670126e742c8540ebabe44352b42c132656c5887df2f71e42734c23cb', '.github/dispatch/desert-rv-environment-v4-20261009.json': '442a5bf8ce36bf69dc54c02e4a4f57c0d4b4ba2528df4090da67e8fc7088e991', '.github/dispatch/desert-rv-environment-v4-r2-20261009-files.json': '21012aab599a5282554e78eba4d4c649ffe884d683e7741296669f70c1f73ec3', '.github/dispatch/desert-rv-environment-v4-r2-20261009.json': 'd6344772a648b6228199bee74a781ef8d36925c73d9793182a76f13f02fb4db1', '.github/dispatch/desert-rv-environment-v4-r3-20261009-files.json': '375f75e87efe7c6db0b3be09a73c396ca66da94d2c434d81f8d353f9c2cd0628', '.github/dispatch/desert-rv-environment-v4-r3-20261009.json': 'fd9ed1fc78cce60e660f6bef41c67a6e0d7db7e9ffbb4e6004ee570776fec476', '.github/dispatch/desert-rv-environment-v4-r4-20261009-files.json': '12738e82388b4f3ff6fc84dfd82651f57e9937b0153ef8b05c312dbd9728c16c', '.github/dispatch/desert-rv-environment-v4-r4-20261009.json': '6fde28a7973a484947726abaf3e89bc418eb0f8d00582d9a506bc1ef7f09b5e6', '.github/dispatch/desert-rv-rebuild-performance-20261009.json': 'beea0fdb80eff9506e2dd0ddff0e6099670d155397d42f01e751ef9044e469b0', '.github/dispatch/desert-rv-rebuild-performance350-20261009.json': '9c1c9e02704e360275c87e67813d23f43dacea1faf86e6f307569a075d48fad1', '.github/workflows/desert-rv-android.yml': 'a921a22d3bafd4b736575ceb48a44e302a4c31104b77fc8d341ec83162b0d4cd', '.github/workflows/desert-rv-armored-refined-static.yml': '19680a698ef93945b19d2911bfb83a670b1ab31b24a3fc196a5ad79d95398b53', '.github/workflows/desert-rv-armored-refined-technical.yml': '23d5cea0ebd344aaaa9a7d096dd909f4d90ef9f21eb9b0a099e28be7df209676', '.github/workflows/desert-rv-armored-v004-r1-discovery.yml': 'e9d002447ffda6e559df2bce20fb7eae684285f7937d0e3e16e847f7ba8031e6', '.github/workflows/desert-rv-armored-v004-r1-strict.yml': 'cca09e27c17e0d5a84637169f8a0ee0b520d77f43513a05293a2933ccf3ac6ba', '.github/workflows/desert-rv-candidate-art-import.yml': '631d3e8d75d6a67b424d82b0a902c2261f444b86fc9a9690a7336613d430621c', '.github/workflows/desert-rv-environment-diffuse-comparison-r1.yml': 'eb439295f8b9d1bd1a720f7dd487266d2806f222f84ff5a941aae6910ac0db93', '.github/workflows/desert-rv-environment-diffuse-comparison.yml': '44019cdb559597c222d28fb6de5bae84f68d9a973de7fe7b30d23e100710ebcd', '.github/workflows/desert-rv-environment-terrain-probe.yml': 'bcae3cc5aa89f9f8794dc210c90009738ccc5a819aae4862019fdef27deeeaac', '.github/workflows/desert-rv-environment-v4-r2.yml': '886ef6b433bdaf8e8aba3b426641ac8182c84c57655a6b42b25ac4e5e0d4c1bd', '.github/workflows/desert-rv-environment-v4-r3.yml': '8929745c359c96f1a6fc7ddf90850e77f71e75d1884de8f2e33165a1c35631a7', '.github/workflows/desert-rv-environment-v4-r4.yml': '10712c9cfbbe230d801743bf320407947b6933b1d80931be2e26c7c847501535', '.github/workflows/desert-rv-environment-v4.yml': '891c1822353a9bde0966fe290a97a09e5282591fccff3962658a8c1789816e05', '.github/workflows/desert-rv-environment.yml': '172633338212febf86e7044d516b5db77b35718e461c7f51113879ef97f1a4aa', '.github/workflows/desert-rv-journey-prepare.yml': '367eec8a8c17bcaaa00dedd117e119b48bd24fa3b0df85d75f798895581c37d8', '.github/workflows/desert-rv-journey-rebuild.yml': '1cb6397c58fcbfb1d8ba8ba52b64915074594ab5b84fc68151cdd00902f0210d', '.github/workflows/desert-rv-player-observe.yml': '92dd8519f828b291ae638e88431d376d358ba7bca89abc2f4df0251b7ace944b', '.github/workflows/desert-rv-player-smoke.yml': '016374404d7410e7465137e608fde56691e0583f315ee5cb606a50b24e740072', '.github/workflows/desert-rv-rendered-smoke.yml': '78343b783fe955d751df7340388d7eb6fd21b7144fa12f5770cfca5a17d57870', '.github/workflows/desert-rv-supplies.yml': '96e34b71e0e981cde3488063333b6acdf9f8db18e181031ba6e5b60b1da59332', 'tasks/desert-rv/scripts/armored_v004_discovery_dispatch.py': '23b62943578e29b948202d1a4f67444b9ab10111d50c9d3140534c9fcf256174', 'tasks/desert-rv/scripts/armored_v004_strict_dispatch.py': '7248d35f9abb6cd03de768f673d58b97cce7efef883bc1b37447d5aa397300b8', 'tasks/desert-rv/scripts/environment_diffuse_comparison_dispatch.py': '1c3c6cf43ae8af47a8df2d9c56f5264d99d8ec11035df4bfc9ea983c0bec9cbd', 'tasks/desert-rv/scripts/environment_diffuse_comparison_r1_dispatch.py': 'b1ba84217ec8173343fa23eff321fc3522736c20c0a24dec5976172736e9a479', 'tasks/desert-rv/scripts/environment_terrain_probe_dispatch.py': '6c0e883271251f0e9a9b02e00ed241aaeb31f1a884ea53f0c3715a275bf7b83d', 'tasks/desert-rv/scripts/environment_v4_dispatch.py': '5aaf1d2c006246a9a17aeca2103be09bcadf57e08f13b3820ef5054030fbac5b', 'tasks/desert-rv/scripts/environment_v4_r2_dispatch.py': '8a8b926e249941a80f3aa846ecffea065ec5af18f42601c94f8443568391c4ec', 'tasks/desert-rv/scripts/environment_v4_r3_dispatch.py': '0427d2d8db05bbb94acd45bada987c44b4211b4dec4f2113968edf0a7ffeed62', 'tasks/desert-rv/scripts/environment_v4_r4_dispatch.py': 'd4817fd852a6abcfbd112d5ba437fbfc7d26732e3e133fa3a67361e292317d6c', 'tasks/desert-rv/scripts/journey_rebuild_dispatch.py': '9f906ef9ce1b4664ec5dc5c5b756afc78f78a90fd834b54a87cce565eba33101'}
  for name,expected in pins.items():self.assertEqual(d.sha((d.ROOT/name).read_bytes()),expected,name)
 def test_original_strict_wrapper_is_byte_identical(self):
  self.assertEqual(d.sha((d.ROOT/'tasks/desert-rv/scripts/environment_v4_r4_evidence.py').read_bytes()),'958739e1d1b38bc8916e0e730d43c9f1abf52ba9ba524ffb72848f102cfa8f2f')
  self.assertEqual(d.sha((d.ROOT/'tasks/desert-rv/scripts/environment_v4_evidence.py').read_bytes()),'7f8bd56d466260bbf57653a76f3845deea81d9f96d03a093366376dcfeba6548')
  self.assertEqual(d.sha((d.ROOT/'tasks/desert-rv/unity/Assets/DesertRV/Tests/EditorRender/JourneyEnvironmentRenderTests.cs').read_bytes()),'4a16e5d04dabc2a0ed78dd0be8eb6b4730e2edc9a2a40ac3b0acd20382246858')

class AuditFinalControlTests(unittest.TestCase):
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
  import test_environment_v4_r4_dispatch as historical
  preimages=historical.published_r4_preimages()
  self.assertEqual(d.sha(preimages[d.SOURCE_STATE]),historical.PUBLISHED_R4_SOURCE_SHA)
  self.assertNotEqual(d.sha((d.ROOT/d.SOURCE_STATE).read_bytes()),historical.PUBLISHED_R4_SOURCE_SHA)
 def test_current_source_closed_set_is_not_historical(self):
  import verify_evidence as evidence
  evidence.verify_source_state()

if __name__=='__main__':unittest.main()
