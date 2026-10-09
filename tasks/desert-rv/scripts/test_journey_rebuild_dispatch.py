"""Closed one-shot push identity fixtures; no network or workflow dispatch."""
import copy,hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest import mock
import journey_rebuild_dispatch as d

class PushIdentityTests(unittest.TestCase):
 def setUp(self):
  self.head='a'*40;self.sha='b'*64
  self.env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=d.REPOSITORY,GITHUB_REPOSITORY_VISIBILITY='public',GITHUB_ACTOR=d.OWNER,GITHUB_TRIGGERING_ACTOR=d.OWNER,GITHUB_REF='refs/heads/main',GITHUB_SHA=self.head,GITHUB_RUN_ID='1',GITHUB_RUN_ATTEMPT='1',GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF=d.REPOSITORY+'/.github/workflows/desert-rv-journey-rebuild.yml@refs/heads/main')
  self.event=dict(before=d.BASE,after=self.head,ref='refs/heads/main',created=False,deleted=False,forced=False,repository=dict(full_name=d.REPOSITORY,private=False,fork=False,owner=dict(login=d.OWNER)),sender=dict(login=d.OWNER),head_commit=dict(id=self.head))
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
  self.request['requestId']='desert-rv-rebuild-performance-20261009-once';self.request['baseCommit']='9abf31160845852d6b1eaffcf432522f60258a0a';self.reject('REQUEST_IDENTITY')
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
 def test_other_branch_rejected(self):self.env['GITHUB_REF']='refs/heads/art';self.reject('BRANCH')
 def test_wrong_event_rejected(self):self.env['GITHUB_EVENT_NAME']='pull_request';self.reject('EVENT')
 def test_force_created_deleted_rejected(self):
  for key in ('forced','created','deleted'):
   self.event[key]=True;self.reject('PUSH_KIND');self.event[key]=False
 def test_existing_request_rejected(self):self.present=True;self.reject('REQUEST_GIT')
 def test_request_unchanged_rejected(self):self.changed=[];self.reject('REQUEST_GIT')
 def test_working_request_tamper_rejected(self):self.reject('REQUEST_GIT',tracked=b'other bytes')
 def test_manual_exact_policy_retains_original_replay_behavior(self):
  self.env.update(GITHUB_EVENT_NAME='workflow_dispatch',MANUAL_TRANSITION_SHA=self.sha,GITHUB_RUN_ATTEMPT='2');self.assertEqual(self.sha,self.check(raw=b''))
 def test_manual_wrong_policy_rejected(self):self.env.update(GITHUB_EVENT_NAME='workflow_dispatch',MANUAL_TRANSITION_SHA='c'*64);self.reject('MANUAL_POLICY')
 def test_oversized_request_rejected(self):self.reject('REQUEST_SIZE',raw=b' '*2049)

class RealGitInputTests(unittest.TestCase):
 def test_actual_git_parent_and_tracked_request_bytes(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);git=lambda *args:subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()
   git('init');git('config','user.name','Local Fixture');git('config','user.email','fixture@example.invalid')
   (root/'original').write_text('base');git('add','.');git('commit','-m','fixture base');parent=git('rev-parse','HEAD')
   policy=root/d.POLICY;policy.parent.mkdir(parents=True);policy.write_bytes(b'actual fixture policy');sha=hashlib.sha256(policy.read_bytes()).hexdigest()
   request=root/d.REQUEST;request.parent.mkdir(parents=True);request.write_text(json.dumps(dict(schema=1,requestId=d.REQUEST_ID,baseCommit=parent,policySha256=sha)))
   git('add','.');git('commit','-m','fixture single request');head=git('rev-parse','HEAD')
   event=dict(before=parent,after=head,ref='refs/heads/main',created=False,deleted=False,forced=False,repository=dict(full_name=d.REPOSITORY,private=False,fork=False,owner=dict(login=d.OWNER)),sender=dict(login=d.OWNER),head_commit=dict(id=head))
   event_path=root/'event.json';event_path.write_text(json.dumps(event))
   env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=d.REPOSITORY,GITHUB_REPOSITORY_VISIBILITY='public',GITHUB_ACTOR=d.OWNER,GITHUB_TRIGGERING_ACTOR=d.OWNER,GITHUB_REF='refs/heads/main',GITHUB_SHA=head,GITHUB_RUN_ID='1',GITHUB_RUN_ATTEMPT='1',GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF=d.REPOSITORY+'/.github/workflows/desert-rv-journey-rebuild.yml@refs/heads/main',GITHUB_EVENT_PATH=str(event_path))
   with mock.patch.object(d,'BASE',parent):
    self.assertEqual(sha,d.verify(root,env))
    request.write_bytes(request.read_bytes()+b' ')
    with self.assertRaisesRegex(ValueError,'REQUEST_GIT'):d.verify(root,env)
 def test_symlink_input_rejected(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);(root/'real').write_text('bytes');(root/'linked').symlink_to(root/'real')
   with self.assertRaisesRegex(ValueError,'INPUT_FILE'):d.safe_bytes(root/'linked',100)

if __name__=='__main__':unittest.main()
