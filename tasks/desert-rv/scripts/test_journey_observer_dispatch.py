"""Offline synthetic identity fixtures. No artifact download, native run, or workflow dispatch."""
import ast
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import types
import unittest
from unittest import mock
import journey_observer_dispatch as d

# Explicit synthetic test-only values, patched only inside fixtures. Never request finalization data.
FIXTURE_PINS = dict(PRODUCER_RUN_ID='123', PRODUCER_COMMIT='a'*40,
                    PRODUCER_ARTIFACT_ID='456', PRODUCER_ZIP_SHA256='b'*64)


def environment(head):
    return dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=d.REPOSITORY,
                GITHUB_REPOSITORY_VISIBILITY='public', GITHUB_ACTOR=d.OWNER,
                GITHUB_TRIGGERING_ACTOR=d.OWNER, GITHUB_REF=d.PUSH_REF,
                GITHUB_SHA=head, GITHUB_RUN_ID='789', GITHUB_RUN_ATTEMPT='1',
                GITHUB_EVENT_NAME='push', GITHUB_WORKFLOW_REF=d.REPOSITORY+'/'+d.WORKFLOW+'@'+d.PUSH_REF,
                RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Linux')


def event_payload(base, head):
    return dict(before=base, after=head, ref=d.PUSH_REF, created=False, deleted=False, forced=False,
                repository=dict(full_name=d.REPOSITORY, private=False, fork=False, visibility='public',
                                default_branch='main', owner=dict(login=d.OWNER)),
                sender=dict(login=d.OWNER), head_commit=dict(id=head))


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.base='c'*40; self.head='d'*40; self.policy=b'EXPLICIT_SYNTHETIC_POLICY'; self.state=b'EXPLICIT_SYNTHETIC_STATE'
        self.env=environment(self.head); self.event=event_payload(self.base,self.head)
        self.request=dict(schema=1,requestId=d.REQUEST_ID,baseCommit=self.base,
                          policySha256=d.sha(self.policy),sourceStateSha256=d.sha(self.state),
                          **{field:FIXTURE_PINS[key] for key,field in d.PIN_FIELDS.items()})
        self.parents=[self.base]; self.present=False; self.changed=sorted(d.CHANGED_PATHS)
        for key,value in dict(BASE=self.base,EXPECTED_PRODUCER=FIXTURE_PINS,POLICY_SHA256=d.sha(self.policy)).items():
            patcher=mock.patch.object(d,key,value);patcher.start();self.addCleanup(patcher.stop)

    def check(self,raw=None,tracked=None):
        d.validate_context(self.env,self.event,self.head)
        raw=json.dumps(self.request).encode() if raw is None else raw
        return d.validate_push(self.env,self.event,self.head,self.parents,raw,raw if tracked is None else tracked,
                               self.present,self.changed,self.policy,self.state)

    def reject(self,code,**kwargs):
        with self.assertRaisesRegex(ValueError,'OBSERVER_DISPATCH_'+code):self.check(**kwargs)

    def test_exact_push_accepts_only_fixture_pins(self):self.assertEqual(FIXTURE_PINS,self.check())
    def test_context_fields_fail_closed(self):
        cases={'GITHUB_ACTIONS':'false','GITHUB_REPOSITORY':'other/repo','GITHUB_REPOSITORY_VISIBILITY':'private',
               'GITHUB_ACTOR':'other','GITHUB_TRIGGERING_ACTOR':'other','GITHUB_REF':'refs/heads/other',
               'GITHUB_EVENT_NAME':'pull_request','GITHUB_WORKFLOW_REF':d.REPOSITORY+'/.github/workflows/desert-rv-journey-rebuild.yml@refs/heads/main',
               'GITHUB_SHA':'e'*40,'GITHUB_RUN_ID':'0','GITHUB_RUN_ATTEMPT':'0','RUNNER_ENVIRONMENT':'self-hosted','RUNNER_OS':'Windows'}
        for key,value in cases.items():
            with self.subTest(key=key),mock.patch.dict(self.env,{key:value}):
                with self.assertRaises(ValueError):self.check()
    def test_missing_context_fields_fail_closed(self):
        for key in self.env:
            with self.subTest(key=key):
                env=dict(self.env);env.pop(key)
                with self.assertRaises(ValueError):d.validate_context(env,self.event,self.head)
    def test_wrong_event_repository_fields(self):
        for key,value in dict(full_name='other/repo',private=True,fork=True,visibility='private',default_branch='dev',owner=None).items():
            with self.subTest(key=key),mock.patch.dict(self.event['repository'],{key:value}):self.reject('EVENT_REPOSITORY')
    def test_attempt_two_rejected(self):self.env['GITHUB_RUN_ATTEMPT']='2';self.reject('REPLAY')
    def test_wrong_event_before_after_branch(self):
        for key,value in dict(before='e'*40,after='e'*40,ref='refs/heads/dev').items():
            with self.subTest(key=key),mock.patch.dict(self.event,{key:value}):self.reject('PUSH_IDENTITY')
    def test_force_create_delete_rejected(self):
        for key in ('forced','created','deleted'):
            for value in (True,0,None):
                with self.subTest(key=key,value=value),mock.patch.dict(self.event,{key:value}):self.reject('PUSH_KIND')
    def test_wrong_sender_or_head_commit(self):
        for key,value in dict(sender={'login':'other'},head_commit={'id':'e'*40}).items():
            with mock.patch.dict(self.event,{key:value}):self.reject('PUSH_AUTHOR')
    def test_wrong_and_merge_parents_rejected(self):
        for parents in ([],['e'*40],[self.base,'e'*40]):
            self.parents=parents;self.reject('PARENT')
    def test_request_present_in_parent_rejected(self):self.present=True;self.reject('REQUEST_GIT')
    def test_worktree_request_tamper_rejected(self):self.reject('REQUEST_GIT',tracked=b'changed')
    def test_extra_missing_and_duplicate_changed_path_rejected(self):
        for changed in (self.changed+['unexpected'],self.changed[1:],self.changed+[d.REQUEST]):
            self.changed=changed;self.reject('CHANGED_SET')
    def test_unknown_or_missing_request_fields(self):
        for field in ('command','producerBranch','producerWorkflow','allowFailedProducer'):
            with mock.patch.dict(self.request,{field:'UNAUTHORIZED'}):self.reject('REQUEST_KEYS')
        for field in list(self.request):
            value=self.request.pop(field);self.reject('REQUEST_KEYS');self.request[field]=value
    def test_duplicate_nonfinite_and_bad_json(self):
        for raw,code in ((b'{"schema":1,"schema":1}','DUPLICATE_KEY'),(b'{"schema":NaN}','JSON_CONSTANT'),
                         (b'{','BAD_JSON'),(b'[]','REQUEST_KEYS'),(b' '*4097,'JSON_SIZE')):
            self.reject(code,raw=raw)
    def test_request_identity(self):
        for key,value in dict(schema=True,requestId='desert-rv-rebuild-performance350-20261009-once',baseCommit='e'*40).items():
            with mock.patch.dict(self.request,{key:value}):self.reject('REQUEST_IDENTITY')
    def test_wrong_well_formed_producer_pins_rejected(self):
        for key,value in dict(producerRunId='124',producerCommit='e'*40,producerArtifactId='457',producerZipSha256='f'*64).items():
            with mock.patch.dict(self.request,{key:value}):self.reject('REQUEST_PRODUCER')
    def test_blank_and_placeholder_pins_rejected(self):
        for field in d.PIN_FIELDS.values():
            for value in ('','__UNFINALIZED__',None,False,123,'a\ncommand'):
                with self.subTest(field=field,value=value),mock.patch.dict(self.request,{field:value}):
                    with self.assertRaises(ValueError):self.check()
    def test_placeholder_policy_source_pins_rejected(self):
        for field in ('policySha256','sourceStateSha256'):
            for value in ('','__UNFINALIZED__',None):
                with mock.patch.dict(self.request,{field:value}):self.reject('REQUEST_DIGEST')
    def test_wrong_policy_or_state_rejected(self):
        for field,code in (('policySha256','POLICY'),('sourceStateSha256','SOURCE_STATE')):
            with mock.patch.dict(self.request,{field:'f'*64}):self.reject(code)
    def test_unfinalized_helper_constants_rejected(self):
        for value in ('','__FINALIZE_OBSERVER_PARENT_COMMIT__'):
            with mock.patch.object(d,'BASE',value):self.reject('UNFINALIZED_PARENT')
        for key in FIXTURE_PINS:
            for value in ('','__UNFINALIZED__'):
                with mock.patch.object(d,'EXPECTED_PRODUCER',dict(FIXTURE_PINS,**{key:value})):
                    with self.assertRaises(ValueError):self.check()
    def test_unknown_pin_dictionary_key_rejected(self):
        with self.assertRaisesRegex(ValueError,'PIN_KEYS'):d.producer_pins(dict(FIXTURE_PINS,PRODUCER_EXTRA='x'))


class WorkflowBridge:
    """Evaluate only the narrow real workflow input/output/env syntax this job uses."""
    def __init__(self,text):
        self.text=text
        match=re.search(r'^    env:\n((?:      .*\n)+)',text,re.M)
        if not match:raise ValueError('WORKFLOW_JOB_ENV_MISSING')
        self.job=dict(re.findall(r'^      ([A-Z0-9_]+): (.+)$',match.group(1),re.M))
        self.steps=re.split(r'^      - ',text,flags=re.M)[1:]
    def step(self,needle):
        matches=[step for step in self.steps if needle in step]
        if len(matches)!=1:raise ValueError('WORKFLOW_STEP')
        return matches[0]
    def resolve(self,value,inputs,outputs,event):
        paths={'github.event.repository.visibility':event.get('repository',{}).get('visibility','')}
        paths.update({'inputs.'+k:v for k,v in inputs.items()})
        paths.update({'steps.observer_request.outputs.'+k:v for k,v in outputs.items()})
        match=re.fullmatch(r'\$\{\{ (.+) \}\}',value)
        if not match or match[1] not in paths:raise ValueError('WORKFLOW_CONTEXT')
        return paths[match[1]]
    def host(self,defaults,inputs,outputs,event,step=None):
        env=dict(defaults)
        for key,value in self.job.items():env[key]=self.resolve(value,inputs,outputs,event)
        if step is not None:
            block=self.step(step)
            for key,value in re.findall(r'^          ([A-Z0-9_]+): (.+)$',block,re.M):
                if key in set(d.PIN_FIELDS)|{'OBSERVER_EVENT_SHA256'}:
                    env[key]=self.resolve(value,inputs,outputs,event)
        return env
    def container(self,host,event_path):
        block=self.step('id: native\n');tokens=shlex.split(block[block.index('docker run'):].replace('\\\n',''))
        env={};volumes=[]
        for index,token in enumerate(tokens):
            if token=='--env':
                key,sep,value=tokens[index+1].partition('=');env[key]=value if sep else host.get(key,'')
            if token=='--volume':volumes.append(tokens[index+1])
        if '$GITHUB_EVENT_PATH:/github/observer-event.json:ro' not in volumes:raise ValueError('WORKFLOW_EVENT_MOUNT')
        if env.get('GITHUB_EVENT_PATH')!='/github/observer-event.json':raise ValueError('WORKFLOW_EVENT_PATH')
        # Emulate only the exact verified read-only bind, preserving source bytes in tests.
        env['GITHUB_EVENT_PATH']=str(event_path)
        return env


class RealGitTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.git('init');self.git('config','user.name','Synthetic Offline Fixture');self.git('config','user.email','fixture@example.invalid')
        self.policy=b'EXPLICIT_SYNTHETIC_POLICY';self.state=b'EXPLICIT_SYNTHETIC_STATE'
        self.write(d.POLICY,self.policy)
        self.git('add','.');self.git('commit','-m','synthetic baseline');self.base=self.git('rev-parse','HEAD')
        for name in d.CHANGED_PATHS:self.write(name,b'EXPLICIT_SYNTHETIC_SOURCE')
        self.write(d.SOURCE_STATE,self.state)
        self.request=dict(schema=1,requestId=d.REQUEST_ID,baseCommit=self.base,policySha256=d.sha(self.policy),
                          sourceStateSha256=d.sha(self.state),**{field:FIXTURE_PINS[key] for key,field in d.PIN_FIELDS.items()})
        self.write(d.REQUEST,json.dumps(self.request).encode());self.git('add','.');self.git('commit','-m','synthetic one-shot publication')
        self.env=environment(self.git('rev-parse','HEAD'));self.event_path=self.root/'event.json';self.update_event()
        for key,value in dict(BASE=self.base,EXPECTED_PRODUCER=FIXTURE_PINS,POLICY_SHA256=d.sha(self.policy)).items():
            p=mock.patch.object(d,key,value);p.start();self.addCleanup(p.stop)
        self.workflow=(d.ROOT/d.WORKFLOW).read_text();self.bridge=WorkflowBridge(self.workflow)
        self.defaults={k:v for k,v in self.env.items() if k!='GITHUB_REPOSITORY_VISIBILITY'}
        self.inputs={key.lower():value for key,value in FIXTURE_PINS.items()}
        self.outputs={key.lower():value for key,value in FIXTURE_PINS.items()}
        self.outputs['observer_event_sha256']=d.sha(self.event_path.read_bytes())
    def git(self,*args):return subprocess.check_output(['git',*args],cwd=self.root,stderr=subprocess.DEVNULL).decode().strip()
    def write(self,name,raw):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    def update_event(self):
        self.env['GITHUB_SHA']=self.git('rev-parse','HEAD');self.event=event_payload(self.base,self.env['GITHUB_SHA'])
        self.event_path.write_text(json.dumps(self.event));self.env['GITHUB_EVENT_PATH']=str(self.event_path)
    def verify(self):return d.verify(self.root,self.env)
    def reject(self,code):
        with self.assertRaisesRegex(ValueError,code):self.verify()
    def host(self,step):return self.bridge.host(self.defaults,self.inputs,self.outputs,self.event,step)
    def test_actual_git_commit_parent_and_tracked_bytes(self):self.assertEqual(FIXTURE_PINS,self.verify())
    def test_actual_head_mismatch(self):self.env['GITHUB_SHA']='e'*40;self.reject('HEAD')
    def test_actual_push_rejects_main_other_branch_and_wrong_workflow_ref(self):
        for key,value in [('GITHUB_REF',d.MANUAL_REF),('GITHUB_REF','refs/heads/unapproved'),
                          ('GITHUB_WORKFLOW_REF',d.REPOSITORY+'/'+d.WORKFLOW+'@'+d.MANUAL_REF),
                          ('GITHUB_WORKFLOW_REF',d.REPOSITORY+'/.github/workflows/unapproved.yml@'+d.PUSH_REF)]:
            with self.subTest(key=key,value=value),mock.patch.dict(self.env,{key:value}):
                with self.assertRaisesRegex(ValueError,'BRANCH|WORKFLOW'):self.verify()
    def test_actual_manual_rejects_observer_and_unknown_branch(self):
        self.env.update(GITHUB_EVENT_NAME='workflow_dispatch',**{'MANUAL_'+k:v for k,v in FIXTURE_PINS.items()})
        for ref in (d.PUSH_REF,'refs/heads/unapproved'):
            self.env.update(GITHUB_REF=ref,GITHUB_WORKFLOW_REF=d.REPOSITORY+'/'+d.WORKFLOW+'@'+ref)
            self.reject('BRANCH')
    def test_complete_guard_runs_actual_git_helper_then_current_source_gate(self):
        import verify_evidence as v
        with mock.patch.dict(os.environ,self.env,clear=True),mock.patch.object(v,'ROOT',self.root), \
             mock.patch.object(v,'identity'),mock.patch.object(v,'verify_source_state',side_effect=ValueError('CURRENT_SOURCE_REQUIRED')) as source:
            with self.assertRaisesRegex(ValueError,'CURRENT_SOURCE_REQUIRED'):v.guard()
            source.assert_called_once()
    def test_complete_guard_rejects_replay_or_request_tamper_before_source(self):
        import verify_evidence as v
        for kind in ('replay','request'):
            original=(self.root/d.REQUEST).read_bytes()
            env=dict(self.env,GITHUB_RUN_ATTEMPT='2') if kind=='replay' else self.env
            if kind=='request':self.write(d.REQUEST,original+b' ')
            try:
                with self.subTest(kind=kind),mock.patch.dict(os.environ,env,clear=True),mock.patch.object(v,'ROOT',self.root),mock.patch.object(v,'verify_source_state') as source:
                    with self.assertRaisesRegex(ValueError,'REPLAY|TRACKED_BYTES'):v.guard()
                    source.assert_not_called()
            finally:self.write(d.REQUEST,original)
    def test_actual_request_worktree_tamper(self):self.write(d.REQUEST,(self.root/d.REQUEST).read_bytes()+b' ');self.reject('TRACKED_BYTES')
    def test_every_actual_changed_path_and_policy_worktree_tamper(self):
        for name in sorted(d.CHANGED_PATHS|{d.POLICY}):
            original=(self.root/name).read_bytes();self.write(name,original+b'changed');self.reject('TRACKED_BYTES');self.write(name,original)
    def test_actual_committed_unknown_pin(self):
        self.request['producerArtifactId']='457';self.write(d.REQUEST,json.dumps(self.request).encode())
        self.git('add','.github');self.git('commit','--amend','--no-edit');self.update_event();self.reject('REQUEST_PRODUCER')
    def test_actual_extra_committed_path(self):
        self.write('extra',b'not allowed');self.git('add','extra');self.git('commit','--amend','--no-edit');self.update_event();self.reject('CHANGED_SET')
    def test_actual_mode_change(self):
        self.git('update-index','--chmod=+x',d.REQUEST);self.git('commit','--amend','--no-edit');self.update_event();self.reject('GIT_MODE')
    def test_actual_symlink(self):
        path=self.root/d.REQUEST;path.unlink();path.symlink_to(self.root/d.POLICY);self.reject('INPUT_FILE')
    def test_actual_later_commit_replay(self):
        self.write('later',b'replay');self.git('add','later');self.git('commit','-m','replay');self.update_event();self.reject('PARENT')
    def test_actual_merge_commit_rejected(self):
        tree=self.git('rev-parse','HEAD^{tree}');other=self.git('commit-tree',tree,'-p',self.base,'-m','other branch')
        merge=self.git('commit-tree',tree,'-p',self.base,'-p',other,'-m','merge fixture');self.git('reset','--hard',merge)
        self.update_event();self.reject('PARENT')
    def test_actual_request_in_parent_rejected(self):
        # Manufacture a parent already containing this request, then a one-parent child changing it.
        old_head=self.git('rev-parse','HEAD');self.git('checkout','--detach',self.base)
        self.write(d.REQUEST,b'previous request');self.git('add','.');self.git('commit','-m','already consumed parent')
        consumed=self.git('rev-parse','HEAD');self.git('read-tree',old_head);self.git('checkout-index','-a','-f')
        child=self.git('commit-tree',self.git('write-tree'),'-p',consumed,'-m','attempt reuse');self.git('reset','--hard',child)
        self.base=consumed;self.update_event()
        with mock.patch.object(d,'BASE',consumed):self.reject('REQUEST_GIT')
    def test_actual_missing_parent_object(self):
        with mock.patch.object(d,'BASE','f'*40):self.reject('PARENT')
    def test_manual_route_does_not_require_finalized_push(self):
        self.env.update(GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REF=d.MANUAL_REF,GITHUB_WORKFLOW_REF=d.REPOSITORY+'/'+d.WORKFLOW+'@'+d.MANUAL_REF,GITHUB_RUN_ATTEMPT='2',**{'MANUAL_'+k:v for k,v in FIXTURE_PINS.items()})
        with mock.patch.object(d,'BASE','__UNFINALIZED__'),mock.patch.object(d,'EXPECTED_PRODUCER',{}):
            self.assertEqual(FIXTURE_PINS,self.verify())
    def test_manual_missing_and_invalid_input(self):
        self.env.update(GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REF=d.MANUAL_REF,GITHUB_WORKFLOW_REF=d.REPOSITORY+'/'+d.WORKFLOW+'@'+d.MANUAL_REF,**{'MANUAL_'+k:v for k,v in FIXTURE_PINS.items()})
        for key in FIXTURE_PINS:
            value=self.env.pop('MANUAL_'+key);self.reject('PIN_');self.env['MANUAL_'+key]=value
    def test_real_workflow_manual_inputs(self):
        env=self.host('observe_journey_player.py stage');env.update(GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REF=d.MANUAL_REF,GITHUB_WORKFLOW_REF=d.REPOSITORY+'/'+d.WORKFLOW+'@'+d.MANUAL_REF)
        self.assertEqual(FIXTURE_PINS,d.verify_runtime(self.root,env))
    def test_missing_real_workflow_manual_input_mapping_rejected(self):
        for key in d.PIN_FIELDS:
            line='      MANUAL_'+key+': ${{ inputs.'+key.lower()+' }}\n'
            self.bridge=WorkflowBridge(self.workflow.replace(line,''))
            env=self.host('observe_journey_player.py stage');env.update(GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REF=d.MANUAL_REF,GITHUB_WORKFLOW_REF=d.REPOSITORY+'/'+d.WORKFLOW+'@'+d.MANUAL_REF)
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'PIN_'):d.verify_runtime(self.root,env)
    def test_manual_container_context_uses_explicit_manual_inputs(self):
        host=self.host('id: native\n');host.update(GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REF=d.MANUAL_REF,GITHUB_WORKFLOW_REF=d.REPOSITORY+'/'+d.WORKFLOW+'@'+d.MANUAL_REF)
        env=self.bridge.container(host,self.event_path)
        self.assertEqual(FIXTURE_PINS,d.verify_runtime(self.root,env))
    def test_real_workflow_stage_and_export_outputs(self):
        for step in ('observe_journey_player.py stage','observe_journey_player.py export'):
            with self.subTest(step=step):self.assertEqual(FIXTURE_PINS,d.verify_runtime(self.root,self.host(step)))
    def test_real_workflow_container_complete_context_and_same_event_bytes(self):
        env=self.bridge.container(self.host('id: native\n'),self.event_path)
        self.assertEqual('push',env['GITHUB_EVENT_NAME']);self.assertEqual(FIXTURE_PINS,d.verify_runtime(self.root,env))
        self.assertNotIn('GH_TOKEN',env);self.assertNotIn('GITHUB_TOKEN',env)
        self.assertFalse(any(key.startswith('UNITY_') for key in env))
    def test_missing_actual_job_visibility_mapping_rejected(self):
        self.bridge=WorkflowBridge(self.workflow.replace('      GITHUB_REPOSITORY_VISIBILITY: ${{ github.event.repository.visibility }}\n',''))
        with self.assertRaisesRegex(ValueError,'REPOSITORY'):d.verify_runtime(self.root,self.host('observe_journey_player.py stage'))
    def test_wrong_actual_job_visibility_expression_rejected(self):
        self.bridge=WorkflowBridge(self.workflow.replace('GITHUB_REPOSITORY_VISIBILITY: ${{ github.event.repository.visibility }}','GITHUB_REPOSITORY_VISIBILITY: ${{ github.repository.visibility }}'))
        with self.assertRaisesRegex(ValueError,'WORKFLOW_CONTEXT'):self.host('observe_journey_player.py stage')
    def test_missing_actual_stage_output_mapping_rejected(self):
        for key in set(d.PIN_FIELDS)|{'OBSERVER_EVENT_SHA256'}:
            line='          '+key+': ${{ steps.observer_request.outputs.'+key.lower()+' }}\n'
            self.bridge=WorkflowBridge(self.workflow.replace(line,'',1))
            with self.subTest(key=key),self.assertRaises(ValueError):d.verify_runtime(self.root,self.host('observe_journey_player.py stage'))
    def test_runtime_pin_substitution_rejected(self):
        env=self.host('observe_journey_player.py stage');env['PRODUCER_ARTIFACT_ID']='457'
        with self.assertRaisesRegex(ValueError,'RUNTIME_PINS'):d.verify_runtime(self.root,env)
    def test_missing_every_container_mapping_is_rejected(self):
        good=self.bridge.container(self.host('id: native\n'),self.event_path)
        required=set(self.env)|set(d.PIN_FIELDS)|{'OBSERVER_EVENT_SHA256'}
        for key in required:
            env=dict(good);env.pop(key)
            with self.subTest(key=key),self.assertRaises((ValueError,KeyError)):d.verify_runtime(self.root,env)
    def test_missing_actual_container_env_forwarding_rejected(self):
        self.bridge=WorkflowBridge(self.workflow.replace('--env GITHUB_EVENT_NAME ',''))
        env=self.bridge.container(self.host('id: native\n'),self.event_path)
        with self.assertRaisesRegex(ValueError,'EVENT'):d.verify_runtime(self.root,env)
    def test_missing_or_wrong_container_event_bind_rejected(self):
        for old,new,code in (('$GITHUB_EVENT_PATH:/github/observer-event.json:ro','$GITHUB_EVENT_PATH:/github/observer-event.json:rw','WORKFLOW_EVENT_MOUNT'),
                             ('--env GITHUB_EVENT_PATH=/github/observer-event.json','--env GITHUB_EVENT_PATH','WORKFLOW_EVENT_PATH')):
            self.bridge=WorkflowBridge(self.workflow.replace(old,new))
            with self.assertRaisesRegex(ValueError,code):self.bridge.container(self.host('id: native\n'),self.event_path)
    def test_event_rewritten_with_same_semantics_rejected(self):
        env=self.host('observe_journey_player.py export');self.event_path.write_bytes(self.event_path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'EVENT_BYTES'):d.verify_runtime(self.root,env)
    def test_cli_outputs_are_exact_and_reused_by_workflow(self):
        path=self.root/'outputs';env=dict(self.env,GITHUB_OUTPUT=str(path))
        with mock.patch.object(d,'ROOT',self.root),mock.patch.dict(os.environ,env,clear=True),mock.patch.object(d.sys,'argv',['helper']),contextlib.redirect_stdout(io.StringIO()):d.main()
        output=dict(line.split('=',1) for line in path.read_text().splitlines());self.assertEqual(self.outputs,output)
        self.outputs=output;self.assertEqual(FIXTURE_PINS,d.verify_runtime(self.root,self.host('observe_journey_player.py stage')))
    def test_cli_rejection_writes_no_outputs(self):
        path=self.root/'outputs';env=dict(self.env,GITHUB_OUTPUT=str(path),GITHUB_RUN_ATTEMPT='2')
        with mock.patch.object(d,'ROOT',self.root),mock.patch.dict(os.environ,env,clear=True),mock.patch.object(d.sys,'argv',['helper']):
            with self.assertRaisesRegex(ValueError,'REPLAY'):d.main()
        self.assertFalse(path.exists())
    def test_exact_safe_directory_override_no_global_setting(self):
        original=subprocess.check_output;seen=[]
        def record(args,**kwargs):seen.append(args);return original(args,**kwargs)
        with mock.patch.object(d.subprocess,'check_output',side_effect=record):self.assertEqual(FIXTURE_PINS,self.verify())
        self.assertTrue(seen)
        for args in seen:self.assertEqual(['git','-c','safe.directory='+str(self.root.resolve())],args[:3])


class EntrypointAndRoutingTests(unittest.TestCase):
    def test_all_actual_observer_entrypoints_verify_before_any_action(self):
        path=d.ROOT/'tasks/desert-rv/scripts/player/observe_journey_player.py'
        node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='main')
        for command in ('stage','capture','export'):
            with tempfile.TemporaryDirectory() as temp:
                invoked=[];namespace=dict(sys=types.SimpleNamespace(argv=['observer',command]),os=os,ROOT=d.ROOT,
                    WORK=Path(temp)/'work',RESULT=Path(temp)/'result',OBSERVED={'stage':'START','failureCode':'INTERNAL_VALIDATION'},
                    require=lambda condition:d.require(condition,'ARGUMENTS'),
                    atomic=lambda *args:None,sha=lambda *args:'',
                    stage=lambda:invoked.append('stage'),capture=lambda:invoked.append('capture'),export=lambda:invoked.append('export'))
                exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
                with mock.patch.object(d,'verify_runtime',side_effect=ValueError('rejected')) as gate,contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(1,namespace['main']());gate.assert_called_once();self.assertEqual([],invoked)
    def test_real_guard_routes_observer_without_rebuild_or_environment_nonce(self):
        import verify_evidence as v
        env=environment('d'*40)
        with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(d,'verify',side_effect=ValueError('OBSERVER_ONLY')) as gate:
            with self.assertRaisesRegex(ValueError,'OBSERVER_ONLY'):v.guard()
            gate.assert_called_once()
    def test_manual_guard_keeps_manual_route(self):
        import verify_evidence as v
        env=dict(environment('d'*40),GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REF=d.MANUAL_REF,GITHUB_WORKFLOW_REF=d.REPOSITORY+'/'+d.WORKFLOW+'@'+d.MANUAL_REF,GITHUB_EVENT_PATH='synthetic.json')
        with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(d,'verify') as observer, \
             mock.patch.object(v,'read_json',side_effect=ValueError('MANUAL_CONTINUES')):
            with self.assertRaisesRegex(ValueError,'MANUAL_CONTINUES'):v.guard()
            observer.assert_not_called()
    def test_manual_guard_rejects_nonmain_before_source(self):
        import verify_evidence as v
        env=dict(environment('d'*40),GITHUB_EVENT_NAME='workflow_dispatch')
        with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(d,'verify') as observer,mock.patch.object(v,'verify_source_state') as source:
            with self.assertRaisesRegex(ValueError,'Trusted repository/main'):v.guard()
            observer.assert_not_called();source.assert_not_called()
    def test_unknown_workflow_or_observer_workflow_on_unknown_branch_cannot_route_observer(self):
        import verify_evidence as v
        import journey_rebuild_dispatch as rebuild
        for ref in (d.REPOSITORY+'/'+d.WORKFLOW+'@refs/heads/unapproved',d.REPOSITORY+'/.github/workflows/unapproved.yml@'+d.PUSH_REF,d.REPOSITORY+'/'+d.WORKFLOW+'@'+d.MANUAL_REF):
            env=dict(environment('d'*40),GITHUB_WORKFLOW_REF=ref)
            with self.subTest(ref=ref),mock.patch.dict(os.environ,env,clear=True),mock.patch.object(d,'verify') as observer,mock.patch.object(rebuild,'verify',side_effect=ValueError('CLOSED_ORIGINAL_FALLBACK')):
                with self.assertRaisesRegex(ValueError,'CLOSED_ORIGINAL_FALLBACK'):v.guard()
                observer.assert_not_called()
    def test_other_guards_keep_their_existing_verifiers(self):
        import importlib
        import verify_evidence as v
        routes=(('environment_v4_r4_audit_dispatch','desert-rv-environment-v4-r4-audit.yml'),
                ('environment_v4_r4_dispatch','desert-rv-environment-v4-r4.yml'),
                ('environment_diffuse_comparison_r1_dispatch','desert-rv-environment-diffuse-comparison-r1.yml'),
                ('environment_diffuse_comparison_dispatch','desert-rv-environment-diffuse-comparison.yml'),
                ('environment_terrain_probe_dispatch','desert-rv-environment-terrain-probe.yml'),
                ('environment_v4_r3_dispatch','desert-rv-environment-v4-r3.yml'),
                ('environment_v4_r2_dispatch','desert-rv-environment-v4-r2.yml'),
                ('environment_v4_dispatch','desert-rv-environment-v4.yml'),
                ('armored_v004_strict_dispatch','desert-rv-armored-v004-r1-strict.yml'),
                ('armored_v004_discovery_dispatch','desert-rv-armored-v004-r1-discovery.yml'),
                ('journey_rebuild_dispatch','desert-rv-journey-rebuild.yml'))
        for name,workflow in routes:
            module=importlib.import_module(name)
            env=dict(environment('d'*40),GITHUB_REF=d.MANUAL_REF,GITHUB_WORKFLOW_REF=d.REPOSITORY+'/.github/workflows/'+workflow+'@refs/heads/main')
            with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(d,'verify') as observer, \
                 mock.patch.object(module,'verify',side_effect=ValueError('ORIGINAL_ROUTE')) as original:
                with self.assertRaisesRegex(ValueError,'ORIGINAL_ROUTE'):v.guard()
                original.assert_called_once();observer.assert_not_called()
    def test_original_native_observation_body_unchanged_by_dispatch(self):
        text=(d.ROOT/'tasks/desert-rv/scripts/player/observe_journey_player.py').read_text()
        main=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='main')
        calls=[n for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='verify_runtime']
        self.assertEqual(1,len(calls));self.assertIn("['stage'], ['capture'], ['export']",text)
        workflow=(d.ROOT/d.WORKFLOW).read_text();self.assertNotIn('prepare_runner',workflow)
        self.assertIn('fetch-depth: 2',workflow);self.assertIn('paths: ['+d.REQUEST+']',workflow)


class ActualWorkflowBranchBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.workflow=(d.ROOT/d.WORKFLOW).read_text()
        self.context={'github.repository':d.REPOSITORY,'github.actor':d.OWNER,'github.triggering_actor':d.OWNER,
                      'github.event.repository.visibility':'public','github.event_name':'push','github.ref':d.PUSH_REF,
                      'github.workflow_ref':d.REPOSITORY+'/'+d.WORKFLOW+'@'+d.PUSH_REF,
                      'github.run_attempt':1,'github.event.before':'fa18f21620028e04145be9026ab3c333fa9cadd4'}
    def accepts(self,updates=None):
        context=dict(self.context,**(updates or {}))
        found=re.search(r'^    if: >-\n((?:      .*\n)+)',self.workflow,re.M);self.assertIsNotNone(found)
        expression=' '.join(found[1].splitlines()).strip()
        expression=re.sub(r'github(?:\.[a-z_]+)+',lambda m:repr(context.get(m[0],'')),expression)
        node=ast.parse(expression.replace('&&',' and ').replace('||',' or '),mode='eval')
        for item in ast.walk(node):self.assertIsInstance(item,(ast.Expression,ast.BoolOp,ast.And,ast.Or,ast.Compare,ast.Eq,ast.Constant))
        return eval(compile(node,'actual workflow job condition','eval'),{'__builtins__':{}},{})
    def test_real_workflow_allows_only_exact_fixed_push_and_original_main_manual(self):
        self.assertTrue(self.accepts())
        self.assertTrue(self.accepts({'github.event_name':'workflow_dispatch','github.ref':d.MANUAL_REF,'github.workflow_ref':d.REPOSITORY+'/'+d.WORKFLOW+'@'+d.MANUAL_REF,'github.run_attempt':2}))
        self.assertIn('    branches: [journey-player-observer-fa18]\n',self.workflow)
        self.assertNotIn('    branches: [main]',self.workflow)
    def test_real_workflow_rejects_wrong_event_branch_owner_workflow_attempt_and_parent(self):
        cases=[{'github.event_name':'pull_request'},{'github.event_name':'workflow_dispatch'},
               {'github.ref':d.MANUAL_REF},{'github.ref':'refs/heads/unapproved'},
               {'github.workflow_ref':d.REPOSITORY+'/'+d.WORKFLOW+'@'+d.MANUAL_REF},
               {'github.workflow_ref':d.REPOSITORY+'/.github/workflows/unapproved.yml@'+d.PUSH_REF},
               {'github.run_attempt':2},{'github.event.before':'f'*40},{'github.repository':'other/repo'},
               {'github.actor':'other'},{'github.triggering_actor':'other'},{'github.event.repository.visibility':'private'}]
        for case in cases:
            with self.subTest(case=case):self.assertFalse(self.accepts(case))
    def test_real_workflow_missing_required_push_context_fails_closed(self):
        for key in self.context:
            with self.subTest(key=key):self.assertFalse(self.accepts({key:''}))


class ImageReadinessWorkflowTests(unittest.TestCase):
    def setUp(self):
        import environment_image_precheck as readiness
        import textwrap
        self.readiness=readiness;self.workflow=(d.ROOT/d.WORKFLOW).read_text();self.bridge=WorkflowBridge(self.workflow)
        self.step=self.bridge.step('id: image_precheck\n')
        self.code=textwrap.dedent(self.step.split("python3 - <<'PY'\n",1)[1].split('\n          PY',1)[0])
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.directory=Path(self.temp.name)
        self.reportpath=self.directory/'desert-rv-player-image-readiness.json';self.outputs=self.directory/'outputs'
    def current_report(self,mode):
        p=self.readiness
        if mode=='UNKNOWN':return p.blank_result()
        if mode=='CACHE_HIT':return dict(p.blank_result(),status='PASS',reason='CACHE_HIT',cacheHit=True)
        class Client:
            def head(self,route,token=None):
                if route is p.Route.TARGET:
                    headers=(('Docker-Content-Digest',p.DIGEST),)
                    if mode=='DECLARED_WINDOWS':headers+=(('RateLimit-Limit','100;w=3600'),('RateLimit-Remaining','100;w=3600'))
                    return p.Response(200,headers)
                if mode=='RATE_LIMITED':return p.Response(429,())
                if mode=='RATE_DIAGNOSTIC':return p.Response(200,(('RateLimit-Limit','100;w=7200,200;w=21600'),('RateLimit-Remaining','99;w=7200,199;w=21600'),('X-Unrelated','UNRELATED_SECRET_MUST_NOT_ESCAPE')))
                if mode in ('PULL_SUCCEEDED','PULL_FAILED'):return p.Response(200,())
                if mode=='DECLARED_WINDOWS':return p.Response(200,(('RateLimit-Limit','100;w=7200'),('RateLimit-Remaining','20;w=7200')))
                if mode=='CHANNEL_CONFLICT':return p.Response(200,(('RateLimit-Limit','100;w=3600'),('RateLimit-Remaining','20;w=7200')))
                return p.Response(200,(('RateLimit-Limit','100;w=21600'),('RateLimit-Remaining','20;w=21600')))
        pull=('SUCCESS',0,'NONE') if mode=='PULL_SUCCEEDED' else ('NONZERO_EXIT',1,'UNKNOWN_CLI_FAILURE')
        with mock.patch.dict(os.environ,{key:'' for key in p.BLOCKED_ENV}),mock.patch.object(p,'RegistryClient',Client), \
             mock.patch.object(p,'daemon_ready',return_value=True),mock.patch.object(p,'cache_hit',side_effect=[False,mode=='PULL_SUCCEEDED']), \
             mock.patch.object(p,'run_fixed_pull',return_value=pull),mock.patch.object(p.subprocess,'Popen',side_effect=AssertionError('REAL_DOCKER_FORBIDDEN')):
            report=p.probe()
        self.assertTrue(p.validate_report(report));return report
    def run_wrapper(self,report,code,raw=None,directory=None,expected_calls=1):
        def fake(_argv):
            self.assertEqual(_argv,[])
            print(json.dumps(report) if raw is None else raw,end='\n' if raw is None else '')
            return code
        env=dict(RUNNER_TEMP=str(directory or self.directory),GITHUB_OUTPUT=str(self.outputs))
        with mock.patch.dict(os.environ,env,clear=True),mock.patch.object(self.readiness,'main',side_effect=fake) as main:
            with self.assertRaises(SystemExit) as stopped:exec(compile(self.code,'actual readiness workflow step','exec'),{})
            self.assertEqual(main.call_count,expected_calls)
            if expected_calls:main.assert_called_once_with([])
        return stopped.exception.code
    def condition(self,step,*,success=True,image_ready='true',report_ready='true',report_written='true',identity='success',cancelled=False):
        block=self.bridge.step(step);match=re.search(r'^        if: \$\{\{ (.+) \}\}$',block,re.M);self.assertIsNotNone(match)
        expression=match[1]
        replacements={'success()':repr(success),'always()':'True','!cancelled()':repr(not cancelled),
                      'steps.image_precheck.outputs.image_ready':repr(image_ready),'steps.image_precheck.outputs.report_ready':repr(report_ready),
                      'steps.image_precheck.outputs.report_written':repr(report_written),
                      'steps.observer_request.outcome':repr(identity)}
        for key,value in replacements.items():expression=expression.replace(key,value)
        tree=ast.parse(expression.replace('&&',' and ').replace('||',' or '),mode='eval')
        for node in ast.walk(tree):self.assertIsInstance(node,(ast.Expression,ast.BoolOp,ast.And,ast.Or,ast.Compare,ast.Eq,ast.Constant))
        return eval(compile(tree,'actual readiness downstream condition','eval'),{'__builtins__':{}},{})
    def test_reviewed_helper_and_tests_are_exact_frozen_bytes(self):
        import hashlib
        pins={'environment_image_precheck.py':'c561c6ae5347cd94e64ec5917ee1d4964b46fd5929939c969680f33123cfa1cc',
              'test_environment_image_precheck.py':'14056956f91bf12de0dec949f9e6ec96b146a353e6a596e922196b2e479c96c1'}
        for name,expected in pins.items():self.assertEqual(hashlib.sha256((d.ROOT/'tasks/desert-rv/scripts'/name).read_bytes()).hexdigest(),expected)
    def test_actual_identity_then_readiness_precedes_all_original_work(self):
        identity=self.bridge.step('id: observer_request\n')
        self.assertIn('python3 tasks/desert-rv/scripts/journey_observer_dispatch.py',identity)
        self.assertIn('python3 tasks/desert-rv/scripts/verify_evidence.py guard',identity)
        self.assertLess(identity.index('journey_observer_dispatch.py'),identity.index('verify_evidence.py guard'))
        self.assertEqual(self.workflow.count('python3 tasks/desert-rv/scripts/verify_evidence.py guard'),1)
        self.assertNotIn('test_',identity)
        steps=self.bridge.steps
        self.assertIn('uses: actions/checkout@',steps[0]);self.assertEqual(steps[1],identity);self.assertEqual(steps[2],self.step)
        for token in ('sudo apt-get','docker build','observe_journey_player.py stage','test_journey_observer_dispatch.py','test_environment_image_precheck.py','test_observe_journey_player.py'):
            self.assertGreater(self.workflow.index(token),self.workflow.index('id: image_precheck'))
        self.assertNotIn('continue-on-error',self.workflow)
        self.assertIn('BASE_IMAGE='+self.readiness.IMAGE,self.workflow)
        self.assertNotIn('docker login',self.workflow)
        self.assertIn('bounded pull',self.step);self.assertIn('timeout-minutes: 12',self.step)
    def test_actual_identity_and_fresh_source_failure_stop_before_readiness(self):
        import textwrap
        identity=self.bridge.step('id: observer_request\n')
        commands=textwrap.dedent(identity.split('        run: |\n',1)[1])
        self.assertEqual(commands.splitlines(),['python3 tasks/desert-rv/scripts/journey_observer_dispatch.py','python3 tasks/desert-rv/scripts/verify_evidence.py guard'])
        stub='''python3() {
case "$1" in
*/journey_observer_dispatch.py) printf 'IDENTITY\\n'; return "$IDENTITY_CODE" ;;
*/verify_evidence.py) printf 'SOURCE\\n'; return "$SOURCE_CODE" ;;
*) return 99 ;;
esac
}
'''
        for identity_code,source_code,expected in [(0,0,'IDENTITY\nSOURCE\nNEXT\n'),(17,0,'IDENTITY\n'),(0,23,'IDENTITY\nSOURCE\n')]:
            result=subprocess.run(['bash','-e','-c',stub+commands+"printf 'NEXT\\n'\n"],env={'PATH':'/usr/bin:/bin','IDENTITY_CODE':str(identity_code),'SOURCE_CODE':str(source_code)},text=True,capture_output=True)
            self.assertEqual(result.stdout,expected);self.assertEqual(result.returncode,identity_code or source_code)
        self.assertTrue(self.condition('id: image_precheck\n'))
        self.assertFalse(self.condition('id: image_precheck\n',success=False,identity='failure'))
        self.assertFalse(self.condition('id: image_precheck\n',identity='failure'))
    def test_pass_persists_only_validated_report_with_owner_only_mode(self):
        report=dict(self.readiness.blank_result(),status='PASS',reason='CACHE_HIT',cacheHit=True)
        self.assertEqual(self.run_wrapper(report,0),0)
        self.assertEqual(json.loads(self.reportpath.read_text()),report)
        self.assertEqual(self.reportpath.stat().st_mode&0o777,0o600)
        self.assertEqual(self.outputs.read_text(),'report_written=true\nreport_ready=true\nimage_ready=true\n')
    def test_unknown_and_rate_limited_preserve_safe_diagnostic_and_fail(self):
        for status in ('UNKNOWN','RATE_LIMITED'):
            with self.subTest(status=status):
                report=self.current_report(status)
                self.assertEqual(self.run_wrapper(report,2),2)
                self.assertEqual(json.loads(self.reportpath.read_text()),report)
                self.assertEqual(self.outputs.read_text(),'report_written=true\nreport_ready=true\nimage_ready=false\n')
                self.reportpath.unlink();self.outputs.unlink()
    def test_v4_cache_quota_and_pull_pass_preserve_separate_phase_records(self):
        for mode in ('CACHE_HIT','READY','PULL_SUCCEEDED'):
            report=self.current_report(mode)
            self.assertEqual(self.run_wrapper(report,0),0)
            saved=json.loads(self.reportpath.read_text());self.assertEqual(saved,report)
            self.assertEqual(saved['schemaVersion'],4);self.assertNotIn('httpStatus',saved)
            self.assertEqual(saved['reason'],mode);self.assertEqual(set(saved)&{'target','quota','pull'},{'target','quota','pull'})
            if mode=='PULL_SUCCEEDED':
                self.assertIsNone(saved['remaining']);self.assertTrue(saved['pull']['cacheVerified']);self.assertEqual(saved['pull']['exitCode'],0)
            self.reportpath.unlink();self.outputs.unlink()
    def test_v4_failed_pull_retains_observations_and_cannot_enter_original_route(self):
        report=self.current_report('PULL_FAILED');self.assertEqual(report['target']['httpStatus'],200);self.assertEqual(report['quota']['httpStatus'],200)
        self.assertEqual(self.run_wrapper(report,2),2)
        self.assertEqual(json.loads(self.reportpath.read_text()),report)
        self.assertIn('image_ready=false\n',self.outputs.read_text())
        self.assertFalse(self.condition('id: native\n',success=False,image_ready='false'))
    def test_v4_actual_declared_windows_remain_distinct_through_wrapper(self):
        report=self.current_report('DECLARED_WINDOWS');self.assertEqual(report['status'],'PASS')
        self.assertEqual(self.run_wrapper(report,0),0)
        saved=json.loads(self.reportpath.read_text());self.assertEqual(saved['schemaVersion'],4)
        self.assertEqual(saved['windowSeconds'],7200);self.assertFalse(saved['pull']['attempted'])
        for channel,window in (('target',3600),('quota',7200)):
            for field in ('limit','remaining'):
                self.assertEqual(saved[channel]['rateDiagnostics'][field]['policies'][0]['windowSeconds'],window)
    def test_v4_same_channel_window_conflict_stays_nonpass_after_wrapper(self):
        report=self.current_report('CHANNEL_CONFLICT');self.assertEqual(report['status'],'UNKNOWN')
        self.assertEqual(report['quota']['rateDiagnostics']['firstFailedPredicate'],'CHANNEL_WINDOWS_MATCH')
        self.assertEqual(self.run_wrapper(report,2),2);self.assertFalse(report['pull']['attempted'])
        self.assertIn('image_ready=false\n',self.outputs.read_text())
    def test_old_schemas_flat_status_or_unverified_pull_cannot_create_ready_report(self):
        good=self.current_report('PULL_SUCCEEDED')
        cases=[dict(good,schemaVersion=1),dict(good,schemaVersion=2),dict(good,schemaVersion=3),dict(good,httpStatus=200),dict(good,pull=dict(good['pull'],cacheVerified=False)),
               dict(good,pull=dict(good['pull'],exitCode=1)),dict(good,quota=dict(good['quota'],reason='SECRET'))]
        for report in cases:
            self.assertEqual(self.run_wrapper(report,0),'IMAGE_PRECHECK_REPORT_REJECTED')
            self.assertFalse(self.reportpath.exists());self.assertFalse(self.outputs.exists())
    def test_v4_rate_diagnostic_survives_wrapper_without_promoting_failure(self):
        report=self.current_report('RATE_DIAGNOSTIC');self.assertEqual(report['status'],'UNKNOWN')
        self.assertEqual(self.run_wrapper(report,2),2)
        saved=json.loads(self.reportpath.read_text());self.assertEqual(saved,report)
        diagnostic=saved['quota']['rateDiagnostics']
        self.assertEqual(diagnostic['firstFailedPredicate'],'LIMIT_STRICT_REGEX')
        self.assertEqual(diagnostic['limit']['boundedRaw'],'100;w=7200,200;w=21600')
        self.assertEqual(diagnostic['remaining']['gateCompatibility'],'MULTIPLE_POLICIES')
        self.assertNotIn('UNRELATED_SECRET_MUST_NOT_ESCAPE',self.reportpath.read_text())
        self.assertIn('image_ready=false\n',self.outputs.read_text())
    def test_legal_json_at_8192_bytes_including_lf_is_canonicalized_and_accepted(self):
        self.assertEqual(self.readiness.MAX_SERIALIZED_REPORT_BYTES,8192)
        self.assertIn("len(raw.encode('utf-8')) <= 8192",self.code)
        self.assertNotIn("len(raw.encode('utf-8')) <= 4096",self.code)
        # Synthetic whitespace reaches the transport boundary without inventing diagnostic fields.
        for mode,code in (('CACHE_HIT',0),('UNKNOWN',2)):
            report=self.current_report(mode)
            canonical=json.dumps(report,sort_keys=True,separators=(',',':'))+'\n'
            raw=' '*(8192-len(canonical.encode('utf-8')))+canonical
            self.assertEqual(len(raw.encode('utf-8')),8192);self.assertEqual(raw.count('\n'),1)
            self.assertEqual(json.loads(raw),report)
            self.assertEqual(self.run_wrapper(report,code,raw),code)
            self.assertEqual(self.reportpath.read_text(),canonical)
            self.reportpath.unlink();self.outputs.unlink()
    def test_same_legal_json_at_8193_bytes_including_lf_is_rejected(self):
        report=self.current_report('CACHE_HIT');canonical=json.dumps(report,sort_keys=True,separators=(',',':'))+'\n'
        raw=' '*(8193-len(canonical.encode('utf-8')))+canonical
        self.assertEqual(len(raw.encode('utf-8')),8193);self.assertEqual(json.loads(raw),report)
        self.assertEqual(self.run_wrapper(report,0,raw),'IMAGE_PRECHECK_REPORT_REJECTED')
        self.assertFalse(self.reportpath.exists());self.assertFalse(self.outputs.exists())
    def test_invalid_or_raw_extra_output_never_becomes_uploadable(self):
        good=dict(self.readiness.blank_result(),status='PASS',reason='CACHE_HIT',cacheHit=True)
        cases=[(dict(good,raw='SECRET'),0,None),(good,2,None),(good,False,None),(good,0,json.dumps(good)+'\nSECRET\n'),
               (good,0,'SECRET'),(good,0,'x'*8192+'\n'),(good,0,'{"status":"PASS","status":"PASS"}\n')]
        for report,code,raw in cases:
            with self.subTest(raw=bool(raw),code=code):
                self.assertEqual(self.run_wrapper(report,code,raw),'IMAGE_PRECHECK_REPORT_REJECTED')
                self.assertFalse(self.reportpath.exists());self.assertFalse(self.outputs.exists())
    def test_existing_report_or_symlink_is_never_overwritten_or_marked_ready(self):
        report=dict(self.readiness.blank_result(),status='PASS',reason='CACHE_HIT',cacheHit=True)
        old=json.dumps(self.readiness.blank_result())+'\n';self.assertTrue(self.readiness.validate_report(json.loads(old)))
        self.reportpath.write_text(old)
        self.assertEqual(self.run_wrapper(report,0,expected_calls=0),'IMAGE_PRECHECK_REPORT_REJECTED');self.assertEqual(self.reportpath.read_text(),old);self.assertFalse(self.outputs.exists())
        self.reportpath.unlink();target=self.directory/'other';target.write_text('TARGET');self.reportpath.symlink_to(target)
        self.assertEqual(self.run_wrapper(report,0,expected_calls=0),'IMAGE_PRECHECK_REPORT_REJECTED');self.assertEqual(target.read_text(),'TARGET');self.assertFalse(self.outputs.exists())
    def test_symlinked_report_directory_rejected(self):
        real=self.directory/'real';real.mkdir();link=self.directory/'link';link.symlink_to(real,target_is_directory=True)
        report=dict(self.readiness.blank_result(),status='PASS',reason='CACHE_HIT',cacheHit=True)
        self.assertEqual(self.run_wrapper(report,0,directory=link,expected_calls=0),'IMAGE_PRECHECK_REPORT_REJECTED')
        self.assertFalse((real/self.reportpath.name).exists());self.assertFalse(self.outputs.exists())
    def test_actual_original_steps_require_success_and_pass_output(self):
        for step in ('Validate observer source and offline byte fixtures','Obtain only the pinned successful producer package',
                     'Prepare existing fixed rendering image without Editor activation','id: native\n'):
            self.assertTrue(self.condition(step))
            for success,ready in ((False,'false'),(False,'true'),(True,'false'),(True,'')):
                with self.subTest(step=step,success=success,ready=ready):self.assertFalse(self.condition(step,success=success,image_ready=ready))
    def test_original_failure_export_stays_available_only_after_readiness_pass(self):
        self.assertTrue(self.condition('id: public\n',success=False,image_ready='true'))
        for ready in ('false',''):
            self.assertFalse(self.condition('id: public\n',success=False,image_ready=ready))
    def test_safe_diagnostic_upload_is_separate_and_survives_nonpass(self):
        name='Save only the validated image readiness JSON';block=self.bridge.step(name)
        self.assertTrue(self.condition(name,success=False,image_ready='false'))
        for updates in ({'report_written':''},{'report_written':'false'},{'report_ready':''},{'identity':'failure'},{'cancelled':True}):self.assertFalse(self.condition(name,**updates))
        self.assertIn('path: ${{ runner.temp }}/desert-rv-player-image-readiness.json',block)
        self.assertIn('name: journey-player-image-readiness-',block)
        self.assertIn('if-no-files-found: error',block)
        self.assertNotIn('player-observer-work',block);self.assertNotIn('**',block)


if __name__=='__main__':unittest.main()
