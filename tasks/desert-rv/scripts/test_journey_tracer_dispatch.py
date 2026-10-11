"""Host boundary regressions; synthetic Git repos are never native evidence."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import journey_tracer_dispatch as d


def fixture_env(head, event_path=''):
    return dict(RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Linux', GITHUB_ACTIONS='true',
                GITHUB_REPOSITORY=d.REPOSITORY, GITHUB_REPOSITORY_VISIBILITY='public',
                GITHUB_ACTOR=d.OWNER, GITHUB_TRIGGERING_ACTOR=d.OWNER, GITHUB_REF=d.REF,
                GITHUB_SHA=head, GITHUB_RUN_ID='9876', GITHUB_RUN_ATTEMPT='1', GITHUB_EVENT_NAME='push',
                GITHUB_WORKFLOW_REF=d.REPOSITORY + '/' + d.WORKFLOW + '@' + d.REF, GITHUB_EVENT_PATH=event_path)


def fixture_event(head, base):
    return dict(before=base, after=head, ref=d.REF, created=False, deleted=False, forced=False,
                repository=dict(full_name=d.REPOSITORY, private=False, fork=False, default_branch='main', owner=dict(login=d.OWNER)),
                sender=dict(login=d.OWNER), head_commit=dict(id=head))


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.head = 'a' * 40
        self.env = fixture_env(self.head)
        self.event = fixture_event(self.head, d.BASE)
        self.request = dict(schema=1, requestId=d.REQUEST_ID, baseCommit=d.BASE,
                            sourceStateSha256='b' * 64, selection=d.SELECTION, selectionSha256='c' * 64, shortEvidence=d.SHORT)

    def check(self, **changes):
        raw = json.dumps(self.request).encode()
        inputs = dict(env=self.env, event=self.event, head=self.head, parents=[d.BASE], request_raw=raw,
                      tracked_raw=raw, request_in_parent=False, changed_paths=list(d.CHANGED_FILES),
                      source_sha='b' * 64, selection_sha='c' * 64)
        inputs.update(changes)
        return d.validate(**inputs)

    def test_exact_identity_and_closed_environment(self):
        self.assertEqual(self.check(), self.request)
        for key in self.env:
            if key == 'GITHUB_EVENT_PATH':
                continue  # File existence is exercised through real Git below.
            with self.subTest(missing=key), self.assertRaises(ValueError):
                changed = dict(self.env); changed.pop(key); self.check(env=changed)
        for branch in ('main', 'journey-linux-export-recovery-938', 'journey-tracer-shader-fix-6648-other'):
            with self.subTest(branch=branch), self.assertRaises(ValueError):
                self.check(env=dict(self.env, GITHUB_REF='refs/heads/' + branch))
        for key, value in [('GITHUB_EVENT_NAME', 'workflow_dispatch'), ('GITHUB_RUN_ATTEMPT', '2'),
                           ('GITHUB_ACTOR', 'outsider'), ('GITHUB_TRIGGERING_ACTOR', 'outsider'),
                           ('GITHUB_WORKFLOW_REF', d.REPOSITORY + '/.github/workflows/desert-rv-journey-prepare.yml@' + d.REF)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(env=dict(self.env, **{key: value}))

    def test_event_parent_original_request_and_current_inputs_are_bound(self):
        for changes in (dict(parents=['e' * 40]), dict(parents=[d.BASE, 'e' * 40]), dict(request_in_parent=True),
                        dict(changed_paths=[]), dict(tracked_raw=b'other'), dict(source_sha='e' * 64),
                        dict(selection_sha='e' * 64)):
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.check(**changes)
        for key, value in [('before', 'e' * 40), ('after', 'e' * 40), ('ref', 'refs/heads/main'),
                           ('created', True), ('forced', True), ('deleted', True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(event=dict(self.event, **{key: value}))
        for key, value in [('private', True), ('fork', True), ('default_branch', 'other'), ('full_name', 'other/repo')]:
            event = copy.deepcopy(self.event); event['repository'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.check(event=event)
        for key in ('sender', 'head_commit'):
            event = copy.deepcopy(self.event); event[key] = {}
            with self.subTest(key=key), self.assertRaises(ValueError): self.check(event=event)

    def test_request_schema_is_closed_and_token_bytes_are_not_echoed(self):
        for raw in (b'{', b'[]', b'{"schema":1,"schema":1}', b'{"schema":NaN}', b' ' * 2049):
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError): d.parse_request(raw)
        for key, value in [('schema', True), ('requestId', 'wrong'), ('baseCommit', 'e' * 40),
                           ('shortEvidence', dict(d.SHORT,runAttempt=True)), ('shortEvidence', dict(d.SHORT,artifactBytes=950762.0)),
                           ('selection', '../outside'), ('selectionSha256', 'NEVER_PUBLIC_TOKEN'), ('extra', 'NEVER_PUBLIC_TOKEN')]:
            raw = json.dumps(dict(self.request, **{key: value})).encode()
            with self.subTest(key=key), self.assertRaises(ValueError) as error: d.parse_request(raw)
            self.assertNotIn('NEVER_PUBLIC_TOKEN', str(error.exception))


class RealGitAndWorkflowTests(unittest.TestCase):
    def test_real_git_and_host_runner_prefix_reach_both_guards(self):
        import sys
        import verify_evidence as source
        sys.path.insert(0, str(d.ROOT / 'tasks/desert-rv/art/journey-preparation'))
        import pipeline
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            git = lambda *args: subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()
            git('init'); git('config', 'user.name', 'Local fixture'); git('config', 'user.email', 'fixture@example.invalid')
            # Real complete Unity source map; the sealed evidence bytes below are explicitly synthetic.
            for name in source.source_inventory() | {d.SOURCE, 'tasks/desert-rv/PUBLIC-EXPORT.json'}:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((d.ROOT/name).read_bytes())
            git('add','.');git('commit','-m','synthetic parent');parent=git('rev-parse','HEAD')
            archive=b'SYNTHETIC_SEAL_FIXTURE_NOT_NATIVE_EVIDENCE'
            short=dict(d.SHORT,artifactBytes=len(archive),artifactSha256=d.sha(archive))
            helper=root/'tasks/desert-rv/scripts/journey_tracer_dispatch.py'
            helper.write_text(helper.read_text().replace("BASE = '"+d.BASE+"'", "BASE = '"+parent+"'")
                .replace('artifactBytes='+str(d.SHORT['artifactBytes']), 'artifactBytes='+str(len(archive)))
                .replace(d.SHORT['artifactSha256'],d.sha(archive)))
            for name in d.CHANGED_FILES - {d.REQUEST,d.SOURCE,'tasks/desert-rv/scripts/journey_tracer_dispatch.py'}:
                path=root/name;path.write_bytes(path.read_bytes()+b'\n')
            with mock.patch.multiple(source,ROOT=root,TASK=root/'tasks/desert-rv',PROJECT=root/'tasks/desert-rv/unity'):
                state=json.loads((root/d.SOURCE).read_bytes())
                state['files']=[dict(path=n,sha256=source.sha(root/n),size=(root/n).stat().st_size) for n in sorted(source.source_inventory())]
                (root/d.SOURCE).write_text(json.dumps(state))
                source_sha=source.sha(root/d.SOURCE);selection_sha=source.sha(root/d.SELECTION)
                request=dict(schema=1,requestId=d.REQUEST_ID,baseCommit=parent,sourceStateSha256=source_sha,
                    selection=d.SELECTION,selectionSha256=selection_sha,shortEvidence=short)
                path=root/d.REQUEST;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(request))
                git('add','.');git('commit','-m','exact eight fixture changes');head=git('rev-parse','HEAD')
                event=root/'event.json';event.write_text(json.dumps(fixture_event(head,parent)));env=fixture_env(head,str(event))
                prefix=root/'prepare-prefix.sh';prefix.write_text((root/'tasks/desert-rv/scripts/prepare_runner.sh').read_text()
                    .split('test -n "${UNITY_LICENSE:-}"',1)[0].replace('$(dirname "${BASH_SOURCE[0]}")',str(root/'tasks/desert-rv/scripts')))
                with mock.patch.object(d,'BASE',parent),mock.patch.object(d,'SHORT',short),mock.patch.dict(os.environ,env,clear=True),mock.patch.object(pipeline,'REPO',root):
                    self.assertEqual(d.verify_identity(root,env),request)
                    with self.assertRaisesRegex(ValueError,'ADMISSION_FILES'):d.verify(root,env)
                    values=api_fixture();evidence={n+'.json':json.dumps(v).encode() for n,v in zip(('run','artifact','jobs'),values)}
                    evidence['original.zip']=archive;folder=root/d.ADMISSION;folder.mkdir()
                    for n,b in evidence.items():(folder/n).write_bytes(b)
                    (folder/'seal.json').write_text(json.dumps(d.seal_value(env,request,evidence)))
                    with mock.patch.object(d,'api',side_effect=AssertionError('Later guards must not fetch')):
                        self.assertEqual(d.verify(root,env),request);pipeline.guard();source.guard()
                    def shell(environment):return subprocess.run(['bash',str(prefix)],cwd=root,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                    self.assertEqual(shell(env).returncode,0)
                    for branch in ('refs/heads/main','refs/heads/unknown','refs/heads/journey-pouncer-ground-support-2915'):
                        with self.subTest(branch=branch):self.assertNotEqual(shell(dict(env,GITHUB_REF=branch)).returncode,0)
                    seal=(folder/'seal.json').read_bytes();(folder/'seal.json').write_bytes(seal+b'changed')
                    self.assertNotEqual(shell(env).returncode,0);(folder/'seal.json').write_bytes(seal)
                    (folder/'unexpected').write_text('x')
                    with self.assertRaisesRegex(ValueError,'ADMISSION_FILES'):d.verify(root,env)
                    (folder/'unexpected').unlink()
                    version=root/'tasks/desert-rv/unity/ProjectSettings/ProjectVersion.txt';original=version.read_bytes();version.write_bytes(original+b'tampered\n')
                    with self.assertRaisesRegex(ValueError,'Current source bytes differ'):source.guard()
                    version.write_bytes(original)
                    for key in env:
                        missing=dict(env);missing.pop(key)
                        with self.subTest(missing=key),self.assertRaises(Exception):d.verify(root,missing)
                    path.write_bytes(path.read_bytes()+b' ')
                    with self.assertRaisesRegex(ValueError,'REQUEST_GIT'):d.verify(root,env)
                    path.write_bytes(d.git(root,'show','HEAD:'+d.REQUEST))
                    (root/d.SOURCE).write_bytes((root/d.SOURCE).read_bytes()+b' ')
                    with self.assertRaisesRegex(ValueError,'TRACKED_INPUT'):d.verify(root,env)

    def test_workflow_order_image_copy_and_unchanged_native_authorities(self):
        workflow=(d.ROOT/d.WORKFLOW).read_text()
        old=(d.ROOT/'.github/workflows/desert-rv-journey-rebuild.yml').read_text()
        start='      - name: Verify fixed-image readiness with at most one bounded fallback pull'
        self.assertEqual(workflow.split(start,1)[1].split('      - name: Prepare official validators',1)[0],
                         old.split(start,1)[1].split('      - name: Verify fresh source',1)[0])
        order=['id: dispatch_identity','Verify current source before fixed-image readiness','id: image_precheck',
               'pipeline.py init','JOURNEY_HOSTED_ROOT_CACHE_TEST:','UNITY_LICENSE:',
               'id: tracer_native','id: tracer_source','id: tracer_verify','id: keyboard_copy','id: keyboard_native','id: cabin_native','id: keyboard_isolation',
               'id: keyboard_source','id: keyboard_verify','id: cabin_report','id: keyboard_cleanup',
               'id: stage_armored','id: stage_pouncer','id: stage_weapon','id: ready',
               'id: linux_boundary','id: boundary_verify','id: author','id: finish',
               'id: linux_input','id: linux_native','id: linux_verify','id: linux_public','id: shader_registry',
               'Prove tracked original source was not edited']
        positions=[workflow.index(text) for text in order];self.assertEqual(positions,sorted(positions))
        for forbidden in ('workflow_dispatch:', 'restore_preparation.py', 'prepare-restored',
                          'restoration-transition', 'continue-on-error:', 'workflow_run:'):
            self.assertNotIn(forbidden,workflow)
        self.assertEqual(workflow.count('uses: game-ci/unity-test-runner@'),10)
        self.assertIn('DesertRV.Tests.JourneyCabinEntryPhysicsTests.RealRV_StandardExitToCabin_AllTimesteps',workflow)
        runner=(d.ROOT/'tasks/desert-rv/scripts/prepare_runner.sh').read_text()
        self.assertLess(runner.index('journey_tracer_dispatch.py'),runner.index('UNITY_LICENSE'))
        self.assertIn('else\n    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/journey_rebuild_dispatch.py" --verify-only',runner)


def api_fixture():
    x=d.SHORT
    run=dict(id=x['runId'],run_attempt=1,head_sha=x['commit'],head_branch=x['branch'],path=x['workflow'],
        event='push',status='completed',conclusion='success',actor=dict(login=d.OWNER),triggering_actor=dict(login=d.OWNER),
        repository=dict(full_name=d.REPOSITORY,private=False,fork=False,owner=dict(login=d.OWNER)))
    artifact=dict(id=x['artifactId'],name=x['artifactName'],expired=False,size_in_bytes=x['artifactBytes'],digest='sha256:'+x['artifactSha256'],
        workflow_run=dict(id=x['runId'],head_sha=x['commit'],head_branch=x['branch']))
    jobs=dict(jobs=[dict(id=x['jobId'],name='diagnose',run_id=x['runId'],status='completed',conclusion='success',
        steps=[dict(name=n,status='completed',conclusion='success') for n in d.SHORT_STEPS])])
    return run,artifact,jobs


class ShortAdmissionTests(unittest.TestCase):
    def test_fixed_successful_run_artifact_and_all_steps_required(self):
        original=api_fixture();d.validate_short_api(*original)
        for index,key,value in [(0,'id',1),(0,'head_sha','a'*40),(0,'run_attempt',2),(0,'conclusion','failure'),
            (0,'head_branch','main'),(0,'event','workflow_dispatch'),(1,'expired',True),(1,'id',1),(1,'digest','sha256:'+'f'*64),
            (1,'size_in_bytes',1)]:
            values=copy.deepcopy(original);values[index][key]=value
            with self.subTest(index=index,key=key),self.assertRaises(ValueError):d.validate_short_api(*values)
        values=copy.deepcopy(original);values[2]['jobs'][0]['steps'][0]['conclusion']='skipped'
        with self.assertRaisesRegex(ValueError,'SHORT_STEPS'):d.validate_short_api(*values)
        values=copy.deepcopy(original);values[2]['jobs'].append(values[2]['jobs'][0])
        with self.assertRaisesRegex(ValueError,'SHORT_JOB'):d.validate_short_api(*values)

    def test_partial_failed_redacted_or_mutated_source_is_never_admitted(self):
        import journey_pouncer_ground_support_probe as probe
        report=dict(schema=1,status='DIAGNOSTIC_COMPLETED_NOT_GAMEPLAY_ACCEPTANCE',consumerCommit=d.SHORT['commit'],
            currentProductionCommit=d.SHORT['commit'],consumerParentCommit=probe.BASE,runId=str(d.SHORT['runId']),runAttempt='1',
            producer=probe.PRODUCER,authorOutcome='success',nativeOutcome='success',checks=[],nativeReportRejection=None,nativeRedactedReport=None)
        report.update({k:True for k in ('sourceUnchanged','isolatedInputsVerified','inputUnchanged','authorReportComplete','focusedReportComplete','derivedScenesSealed')})
        report.update({k:False for k in ('approved','gameplayReviewed','scopeReusable')})
        d.validate_short_report(report,probe)
        for key,value in [('status','FAILED_OR_PARTIAL_DIAGNOSTIC_NOT_GAMEPLAY_ACCEPTANCE'),('nativeOutcome','failure'),
            ('authorOutcome','failure'),('focusedReportComplete',False),('sourceUnchanged',False),('nativeReportRejection',{}),
            ('nativeRedactedReport',{}),('checks',['failure']),('approved',True)]:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'SHORT_SUCCESS'):d.validate_short_report(dict(report,**{key:value}),probe)
        state=json.loads((d.ROOT/d.SOURCE).read_bytes());d.unity_map(state)
        row=next(x for x in state['files'] if x['path'].startswith(d.PREFIX));row['sha256']='e'*64
        with self.assertRaisesRegex(ValueError,'UNITY_EQUIVALENCE'):d.unity_map(state)

    def test_exact_archive_pin_precedes_all_parsing(self):
        for raw in (b'',b'not a zip',b'x'*950762):
            with self.assertRaisesRegex(ValueError,'SHORT_ZIP_PIN'):d.short_members(raw)

    def test_initial_source_rejection_performs_no_network_or_seal_write(self):
        import verify_evidence as source
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with mock.patch.object(source,'ROOT',root),mock.patch.object(source,'verify_source_state',side_effect=ValueError('source failed')),mock.patch.object(d,'api') as fetch:
                with self.assertRaisesRegex(ValueError,'source failed'):d.admit(root,{}, {})
                fetch.assert_not_called();self.assertFalse((root/d.ADMISSION).exists())

    def test_only_fixed_owned_error_codes_are_exposed(self):
        self.assertEqual(d.failure_code(ValueError('TRACER_DISPATCH_SHORT_RUN')),'TRACER_DISPATCH_SHORT_RUN')
        self.assertEqual(d.failure_code(ValueError('TRACER_DISPATCH_BAD_JSON')),'TRACER_DISPATCH_BAD_JSON')
        for error in (ValueError('TRACER_DISPATCH_TOKEN_NEVER_PUBLIC'),ValueError('https://private.invalid/token'),RuntimeError('TRACER_DISPATCH_SHORT_RUN')):
            self.assertEqual(d.failure_code(error),'TRACER_PRODUCER_IDENTITY_OR_SHORT_ADMISSION_REJECTED')

    def test_single_explicit_admission_precedes_all_native_calls(self):
        workflow=(d.ROOT/d.WORKFLOW).read_text()
        self.assertEqual(workflow.count('journey_tracer_dispatch.py --admit'),1)
        self.assertLess(workflow.index('journey_tracer_dispatch.py --admit'),workflow.index('verify_evidence.py guard'))
        self.assertLess(workflow.index('verify_evidence.py guard'),workflow.index('id: image_precheck'))
        self.assertEqual(workflow.count('uses: game-ci/unity-test-runner@'),10)
        self.assertNotIn('actions/download-artifact',workflow)
        self.assertNotIn('ignoreFailingMessages',workflow)


if __name__=='__main__':unittest.main()
