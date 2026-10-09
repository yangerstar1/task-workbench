"""Closed one-shot push identity fixtures; no network or workflow dispatch."""
import copy,hashlib,json,os,re,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
import journey_rebuild_dispatch as d

class PushIdentityTests(unittest.TestCase):
 def setUp(self):
  self.head='a'*40;self.sha='b'*64
  self.env=dict(RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',GITHUB_ACTIONS='true',GITHUB_REPOSITORY=d.REPOSITORY,GITHUB_REPOSITORY_VISIBILITY='public',GITHUB_ACTOR=d.OWNER,GITHUB_TRIGGERING_ACTOR=d.OWNER,GITHUB_REF=d.REF,GITHUB_SHA=self.head,GITHUB_RUN_ID='1',GITHUB_RUN_ATTEMPT='1',GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF=d.REPOSITORY+'/.github/workflows/desert-rv-journey-rebuild.yml@'+d.REF)
  self.event=dict(before=d.BASE,after=self.head,ref=d.REF,created=False,deleted=False,forced=False,repository=dict(full_name=d.REPOSITORY,private=False,fork=False,default_branch='main',owner=dict(login=d.OWNER)),sender=dict(login=d.OWNER),head_commit=dict(id=self.head))
  self.request=dict(schema=1,requestId=d.REQUEST_ID,baseCommit=d.BASE,policySha256=self.sha)
  self.parents=[d.BASE];self.present=False;self.changed=[d.REQUEST]
 def check(self,raw=None,tracked=None):
  raw=json.dumps(self.request).encode() if raw is None else raw
  return d.validate(self.env,self.event,self.head,self.parents,raw,raw if tracked is None else tracked,self.present,self.changed,self.sha)
 def reject(self,code,**kwargs):
  with self.assertRaisesRegex(ValueError,'JOURNEY_DISPATCH_'+code):self.check(**kwargs)
 def test_exact_push_accepted(self):self.assertEqual(self.sha,self.check())
 def test_malformed_json_rejected(self):self.reject('BAD_JSON',raw=b'{')
 def test_extra_json_key_rejected(self):self.request['command']='anything';self.reject('REQUEST_KEYS')
 def test_missing_json_key_rejected(self):del self.request['baseCommit'];self.reject('REQUEST_KEYS')
 def test_duplicate_json_key_rejected(self):self.reject('DUPLICATE_KEY',raw=b'{"schema":1,"schema":1}')
 def test_array_json_rejected(self):self.reject('REQUEST_KEYS',raw=b'[]')
 def test_nonfinite_json_rejected(self):self.reject('JSON_CONSTANT',raw=b'{"schema":NaN}')
 def test_boolean_schema_rejected(self):self.request['schema']=True;self.reject('REQUEST_IDENTITY')
 def test_consumed_first_request_cannot_authorize_new_run(self):
  for nonce,parent in [('desert-rv-rebuild-performance-20261009-once','9abf31160845852d6b1eaffcf432522f60258a0a'),('desert-rv-rebuild-performance350-20261009-once','be129aef52363202d7d3cbb51c28281075bef0b5'),('desert-rv-rebuild-export-recovery938-20261009-once','93886445d69597efa0dbf190340b61a6f9ea447c'),('desert-rv-linux-template-probe-20261009-once','dac4109a2a643f25760b9761ea71454e23981e8f'),('desert-rv-rebuild-linux-layout-20261009-once','4ac351190f97783a9b99621a1a8e6bed954f0f9e'),('desert-rv-rebuild-linux-symbol-20261009-once','4bcc86731f7a030ee31b78017ad9ad27f1997383'),('desert-rv-rebuild-python-cache-20261009-once','af1f7e2f77e22a2983995d78406921b35e52706f'),('desert-rv-rebuild-image-readiness-r2-20261009-once','5342c507985d5f97dfcb843e06e149f0ce269d41'),('desert-rv-rebuild-rate-diagnostic-r3-20261009-once','82313a0bd2966c81c5c8bc0fa7f9a9826d861c85')]:
   self.request['requestId']=nonce;self.request['baseCommit']=parent;self.reject('REQUEST_IDENTITY')
 def test_wrong_nonce_rejected(self):self.request['requestId']='other';self.reject('REQUEST_IDENTITY')
 def test_wrong_request_base_rejected(self):self.request['baseCommit']='c'*40;self.reject('REQUEST_IDENTITY')
 def test_wrong_policy_rejected(self):self.request['policySha256']='c'*64;self.reject('REQUEST_POLICY')
 def test_policy_command_injection_rejected(self):self.request['policySha256']='b'*64+'\ncommand';self.reject('REQUEST_POLICY_FORMAT')
 def test_wrong_before_rejected(self):self.event['before']='c'*40;self.reject('PUSH_IDENTITY')
 def test_wrong_after_rejected(self):self.event['after']='c'*40;self.reject('PUSH_IDENTITY')
 def test_wrong_head_rejected(self):self.env['GITHUB_SHA']='c'*40;self.reject('HEAD')
 def test_wrong_parent_rejected(self):self.parents=['c'*40];self.reject('PARENT')
 def test_merge_parent_rejected(self):self.parents.append('c'*40);self.reject('PARENT')
 def test_other_workflow_rejected(self):self.env['GITHUB_WORKFLOW_REF']=d.REPOSITORY+'/.github/workflows/other.yml@refs/heads/main';self.reject('WORKFLOW')
 def test_attempt_two_rejected(self):self.env['GITHUB_RUN_ATTEMPT']='2';self.reject('REPLAY')
 def test_other_repository_rejected(self):self.env['GITHUB_REPOSITORY']='other/repo';self.reject('REPOSITORY')
 def test_private_repository_rejected(self):self.event['repository']['private']=True;self.reject('PUSH_REPOSITORY')
 def test_fork_rejected(self):self.event['repository']['fork']=True;self.reject('PUSH_REPOSITORY')
 def test_other_actor_rejected(self):self.env['GITHUB_ACTOR']='other';self.reject('ACTOR')
 def test_other_triggering_actor_rejected(self):self.env['GITHUB_TRIGGERING_ACTOR']='other';self.reject('ACTOR')
 def test_other_sender_rejected(self):self.event['sender']['login']='other';self.reject('PUSH_AUTHOR')
 def test_main_push_cannot_use_recovery_request(self):self.env['GITHUB_REF']='refs/heads/main';self.reject('BRANCH')
 def test_recovery_branch_manual_cannot_bypass_push_identity(self):self.env.update(GITHUB_EVENT_NAME='workflow_dispatch',MANUAL_TRANSITION_SHA=self.sha);self.reject('BRANCH')
 def test_other_branch_rejected(self):self.env['GITHUB_REF']='refs/heads/art';self.reject('BRANCH')
 def test_wrong_event_rejected(self):self.env['GITHUB_EVENT_NAME']='pull_request';self.reject('EVENT')
 def test_force_created_deleted_rejected(self):
  for key in ('forced','created','deleted'):
   self.event[key]=True;self.reject('PUSH_KIND');self.event[key]=False
 def test_existing_request_rejected(self):self.present=True;self.reject('REQUEST_GIT')
 def test_request_unchanged_rejected(self):self.changed=[];self.reject('REQUEST_GIT')
 def test_working_request_tamper_rejected(self):self.reject('REQUEST_GIT',tracked=b'other bytes')
 def test_manual_exact_policy_retains_original_replay_behavior(self):
  self.env.update(GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REF='refs/heads/main',MANUAL_TRANSITION_SHA=self.sha,GITHUB_RUN_ATTEMPT='2');self.assertEqual(self.sha,self.check(raw=b''))
 def test_manual_wrong_policy_rejected(self):self.env.update(GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REF='refs/heads/main',MANUAL_TRANSITION_SHA='c'*64);self.reject('MANUAL_POLICY')
 def test_oversized_request_rejected(self):self.reject('REQUEST_SIZE',raw=b' '*2049)

class WorkflowEarlyBoundaryTests(unittest.TestCase):
 def test_fixed_image_and_root_cache_checks_precede_first_pull_or_license(self):
  workflow=(Path(__file__).resolve().parents[3]/'.github/workflows/desert-rv-journey-rebuild.yml').read_text()
  identity=workflow.index('id: dispatch_identity');source=workflow.index('      - name: Verify current source before fixed-image readiness');image=workflow.index('id: image_precheck')
  root=workflow.index('JOURNEY_HOSTED_ROOT_CACHE_TEST:');license=workflow.index('UNITY_LICENSE:')
  pull=workflow.index('docker build');native=workflow.index('game-ci/unity-test-runner@')
  self.assertTrue(identity<source<image<root<license<pull<native)
  self.assertIn("JOURNEY_HOSTED_ROOT_CACHE_TEST: '1'",workflow)
  block=workflow.split('      - name: Verify non-root host union across real root-owned bytecode caches',1)[1].split('      - name:',1)[0]
  self.assertIn('MANUAL_TRANSITION_SHA: ${{ inputs.transition_sha256 }}',block)
  self.assertIn('/usr/bin/python3 tasks/desert-rv/scripts/rendered/test_prepared_source.py',block)
  import environment_image_precheck as check
  self.assertIn('--build-arg BASE_IMAGE='+check.IMAGE,workflow)
  self.assertIn("if: always() && steps.image_precheck.outputs.report_written == 'true' && steps.image_report.outputs.export_ready == 'true'",workflow)
 def test_actual_image_report_shell_fragments_reject_status_outcome_or_schema_drift(self):
  import textwrap,shutil
  import environment_image_precheck as check
  source=Path(__file__).resolve().parents[3]
  workflow=(source/'.github/workflows/desert-rv-journey-rebuild.yml').read_text()
  pre=workflow.split('        id: image_precheck',1)[1].split('      - name:',1)[0]
  post=workflow.split('        id: image_report',1)[1].split('      - name:',1)[0]
  fragments=[textwrap.dedent(part.split("<<'PYCODE'\n",1)[1].split('          PYCODE',1)[0]) for part in (pre,post)]
  good=check.blank_result();good.update(status='PASS',reason='CACHE_HIT',cacheHit=True)
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);scripts=root/'tasks/desert-rv/scripts';scripts.mkdir(parents=True)
   shutil.copyfile(source/'tasks/desert-rv/scripts/environment_image_precheck.py',scripts/'environment_image_precheck.py')
   report=root/'tasks/desert-rv/journey-image-precheck.json';output=root/'output'
   env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',GITHUB_OUTPUT=str(output),PRECHECK_EXIT='0',PRECHECK_OUTCOME='success')
   def run(fragment):return subprocess.run(['/usr/bin/python3','-c',fragment],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode
   report.write_text(json.dumps(good));self.assertEqual(run(fragments[0]),0);self.assertEqual(run(fragments[1]),0)
   env['PRECHECK_OUTCOME']='failure';self.assertNotEqual(run(fragments[1]),0)
   env['PRECHECK_EXIT']='2';self.assertNotEqual(run(fragments[0]),0)
   unknown=check.blank_result();report.write_text(json.dumps(unknown));self.assertEqual(run(fragments[0]),0);self.assertEqual(run(fragments[1]),0)
   report.write_text(json.dumps(dict(unknown,privateLog='NEVER_PUBLIC')));self.assertNotEqual(run(fragments[1]),0)
   for version in (1,2,3):
    report.write_text(json.dumps(dict(unknown,schemaVersion=version)));self.assertNotEqual(run(fragments[1]),0)
   bounded=json.dumps(unknown).encode()
   report.write_bytes(bounded+b' '*(8192-len(bounded)));self.assertEqual(run(fragments[1]),0)
   report.write_bytes(bounded+b' '*(8193-len(bounded)));self.assertNotEqual(run(fragments[0]),0);self.assertNotEqual(run(fragments[1]),0)
   report.unlink();target=root/'outside';target.write_text(json.dumps(good));report.symlink_to(target);self.assertNotEqual(run(fragments[0]),0)
   # Execute the actual first shell block with a fixture-only helper CLI. The
   # validation functions remain exact; the fixture never contacts a registry.
   report.unlink();output.unlink(missing_ok=True)
   code=(source/'tasks/desert-rv/scripts/environment_image_precheck.py').read_text().rsplit('if __name__ == "__main__":',1)[0]
   code+='if __name__ == "__main__":\n    print(os.environ["FIXTURE_REPORT"])\n    sys.exit(int(os.environ["FIXTURE_EXIT"]))\n'
   (scripts/'environment_image_precheck.py').write_text(code)
   (scripts/'test_environment_image_precheck.py').write_text('# fixture test command; full helper suite runs separately\n')
   shell=textwrap.dedent(pre.split('        run: |\n',1)[1]);env.update(FIXTURE_REPORT=json.dumps(unknown),FIXTURE_EXIT='2')
   def shell_run():return subprocess.run(['bash','-e','-c',shell],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode
   self.assertEqual(shell_run(),2);self.assertEqual(json.loads(report.read_text()),unknown)
   self.assertIn('report_written=true',output.read_text());self.assertIn('report_valid=true',output.read_text())
   for old in (good,unknown):
    report.write_text(json.dumps(old));output.unlink(missing_ok=True);before=report.read_bytes()
    self.assertNotEqual(shell_run(),0);self.assertEqual(report.read_bytes(),before);self.assertFalse(output.exists())
   report.unlink();report.symlink_to(target);self.assertNotEqual(shell_run(),0);self.assertTrue(report.is_symlink());self.assertFalse(output.exists())
   self.assertEqual(json.loads(target.read_text()),good)


class RealGitInputTests(unittest.TestCase):
 def test_actual_git_parent_and_tracked_request_bytes(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);git=lambda *args:subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()
   git('init');git('config','user.name','Local Fixture');git('config','user.email','fixture@example.invalid')
   (root/'original').write_text('base');git('add','.');git('commit','-m','fixture base');parent=git('rev-parse','HEAD')
   policy=root/d.POLICY;policy.parent.mkdir(parents=True);policy.write_bytes(b'actual fixture policy');sha=hashlib.sha256(policy.read_bytes()).hexdigest()
   request=root/d.REQUEST;request.parent.mkdir(parents=True);request.write_text(json.dumps(dict(schema=1,requestId=d.REQUEST_ID,baseCommit=parent,policySha256=sha)))
   git('add','.');git('commit','-m','fixture single request');head=git('rev-parse','HEAD')
   event=dict(before=parent,after=head,ref=d.REF,created=False,deleted=False,forced=False,repository=dict(full_name=d.REPOSITORY,private=False,fork=False,default_branch='main',owner=dict(login=d.OWNER)),sender=dict(login=d.OWNER),head_commit=dict(id=head))
   event_path=root/'event.json';event_path.write_text(json.dumps(event))
   env=dict(RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',GITHUB_ACTIONS='true',GITHUB_REPOSITORY=d.REPOSITORY,GITHUB_REPOSITORY_VISIBILITY='public',GITHUB_ACTOR=d.OWNER,GITHUB_TRIGGERING_ACTOR=d.OWNER,GITHUB_REF=d.REF,GITHUB_SHA=head,GITHUB_RUN_ID='1',GITHUB_RUN_ATTEMPT='1',GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF=d.REPOSITORY+'/.github/workflows/desert-rv-journey-rebuild.yml@'+d.REF,GITHUB_EVENT_PATH=str(event_path))
   with mock.patch.object(d,'BASE',parent):
    self.assertEqual(sha,d.verify(root,env))
    workflow=(Path(__file__).resolve().parents[3]/'.github/workflows/desert-rv-journey-rebuild.yml').read_text()
    block=workflow.split('      - name: Build candidate Linux player without launching it\n',1)[1].split('      - name:',1)[0]
    declared=re.findall(r'--env ([A-Z_]+)(?:=([^\s]+))?',block)
    forwarded={key:(value or env.get(key,'')) for key,value in declared if key in env or key=='GITHUB_EVENT_PATH'}
    self.assertEqual('/github/workflow/event.json',forwarded['GITHUB_EVENT_PATH'])
    self.assertIn('--volume "$GITHUB_EVENT_PATH:/github/workflow/event.json:ro"',block)
    required={'GITHUB_ACTIONS','GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_REPOSITORY','GITHUB_REF','GITHUB_ACTOR','GITHUB_TRIGGERING_ACTOR','GITHUB_EVENT_NAME','GITHUB_WORKFLOW_REF','GITHUB_EVENT_PATH','RUNNER_ENVIRONMENT','RUNNER_OS','GITHUB_REPOSITORY_VISIBILITY'}
    self.assertEqual(required,set(forwarded))
    # Map only the parsed read-only volume target into a local fixture mount. Every value comes from the real workflow's env declarations.
    mounted=root/'container/github/workflow/event.json';mounted.parent.mkdir(parents=True);mounted.write_bytes(event_path.read_bytes());mounted.chmod(0o444)
    forwarded['GITHUB_EVENT_PATH']=str(mounted);self.assertEqual(sha,d.verify(root,forwarded))
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'art/journey-preparation'))
    import pipeline
    with mock.patch.object(pipeline,'REPO',root),mock.patch.dict(os.environ,forwarded,clear=True):pipeline.guard()
    import verify_evidence
    with mock.patch.object(verify_evidence,'ROOT',root),mock.patch.object(verify_evidence,'identity',return_value={}),mock.patch.object(verify_evidence,'verify_source_state',return_value={}),mock.patch.dict(os.environ,forwarded,clear=True):verify_evidence.guard()
    with mock.patch.object(pipeline,'REPO',root),mock.patch.dict(os.environ,dict(forwarded,GITHUB_REF='refs/heads/unknown'),clear=True):
     with self.assertRaisesRegex(ValueError,'BRANCH'):pipeline.guard()
    for key in required:
     missing=dict(forwarded);missing.pop(key)
     with self.assertRaises(Exception,msg=key):d.verify(root,missing)
    request.write_bytes(request.read_bytes()+b' ')
    with self.assertRaisesRegex(ValueError,'REQUEST_GIT'):d.verify(root,env)
 def test_symlink_input_rejected(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);(root/'real').write_text('bytes');(root/'linked').symlink_to(root/'real')
   with self.assertRaisesRegex(ValueError,'INPUT_FILE'):d.safe_bytes(root/'linked',100)

if __name__=='__main__':unittest.main()
