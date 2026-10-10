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
                            sourceStateSha256='b' * 64, selection=d.SELECTION, selectionSha256='c' * 64)

    def check(self, **changes):
        raw = json.dumps(self.request).encode()
        inputs = dict(env=self.env, event=self.event, head=self.head, parents=[d.BASE], request_raw=raw,
                      tracked_raw=raw, request_in_parent=False, changed_paths=[d.REQUEST],
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
            (root/'base').write_text('fixture'); git('add', '.'); git('commit', '-m', 'base'); parent=git('rev-parse','HEAD')
            # A real current-source inventory, with no mocked successful validator.
            for directory in source.SOURCE_ROOTS: (root/directory).mkdir(parents=True, exist_ok=True)
            for name in source.SOURCE_FILES:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((d.ROOT/name).read_bytes())
            version=root/'tasks/desert-rv/unity/ProjectSettings/ProjectVersion.txt';version.parent.mkdir(parents=True);version.write_text('m_EditorVersion: '+source.VERSION+'\n')
            export=root/'tasks/desert-rv/PUBLIC-EXPORT.json';export.write_bytes((d.ROOT/'tasks/desert-rv/PUBLIC-EXPORT.json').read_bytes())
            select=root/d.SELECTION;select.write_bytes((d.ROOT/d.SELECTION).read_bytes())
            helper=root/'tasks/desert-rv/scripts/journey_tracer_dispatch.py'
            helper.write_text((d.ROOT/'tasks/desert-rv/scripts/journey_tracer_dispatch.py').read_text().replace(d.BASE,parent))
            old_helper=root/'tasks/desert-rv/scripts/journey_rebuild_dispatch.py'
            old_helper.write_bytes((d.ROOT/'tasks/desert-rv/scripts/journey_rebuild_dispatch.py').read_bytes())
            runner=root/'tasks/desert-rv/scripts/prepare-prefix.sh'
            runner.write_text((d.ROOT/'tasks/desert-rv/scripts/prepare_runner.sh').read_text().split('test -n "${UNITY_LICENSE:-}"',1)[0])
            with mock.patch.multiple(source,ROOT=root,TASK=root/'tasks/desert-rv',PROJECT=root/'tasks/desert-rv/unity'):
                names=sorted(source.source_inventory())
                state=dict(schema='desert-rv-source-state/v1',baselineGameCommit=source.BASELINE_COMMIT,
                    baselineExportManifestSha256=source.BASELINE_EXPORT_SHA,coverageRoots=list(source.SOURCE_ROOTS),coverageFiles=list(source.SOURCE_FILES),
                    restoredFiles=[dict(path=source.FONT_PATH,sha256=source.FONT_SHA,size=16437340)],
                    files=[dict(path=name,sha256=source.sha(root/name),size=(root/name).stat().st_size) for name in names])
                (root/d.SOURCE).write_text(json.dumps(state))
                source_sha=source.sha(root/d.SOURCE);selection_sha=source.sha(select)
                request=root/d.REQUEST;request.parent.mkdir(parents=True)
                request.write_text(json.dumps(dict(schema=1,requestId=d.REQUEST_ID,baseCommit=parent,sourceStateSha256=source_sha,selection=d.SELECTION,selectionSha256=selection_sha)))
                git('add','.');git('commit','-m','single request');head=git('rev-parse','HEAD')
                event=root/'event.json';event.write_text(json.dumps(fixture_event(head,parent)));env=fixture_env(head,str(event))
                workflow=(d.ROOT/d.WORKFLOW).read_text()
                self.assertIn('bash tasks/desert-rv/scripts/prepare_runner.sh',workflow)
                self.assertIn('journey_linux_container.sh',workflow)
                forwarded=dict(env)
                with mock.patch.object(d,'BASE',parent),mock.patch.dict(os.environ,forwarded,clear=True),mock.patch.object(pipeline,'REPO',root):
                    self.assertEqual(source_sha,d.verify(root,forwarded)['sourceStateSha256'])
                    pipeline.guard();source.guard()
                    def shell(environment):return subprocess.run(['bash',str(runner)],cwd=root,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                    self.assertEqual(shell(forwarded).returncode,0)
                    for branch in ('refs/heads/main','refs/heads/unknown','refs/heads/journey-linux-export-recovery-938'):
                        with self.subTest(prefix_branch=branch):self.assertNotEqual(shell(dict(forwarded,GITHUB_REF=branch)).returncode,0)
                    # Actual source mutation cannot pass even with a still-valid request.
                    version.write_text(version.read_text()+'tampered\n')
                    with self.assertRaisesRegex(ValueError,'Current source bytes differ'):source.guard()
                    version.write_text('m_EditorVersion: '+source.VERSION+'\n')
                    for key in forwarded:
                        missing=dict(forwarded);missing.pop(key)
                        with self.subTest(missing=key),self.assertRaises(Exception):d.verify(root,missing)
                    with mock.patch.dict(os.environ,dict(forwarded,GITHUB_REF='refs/heads/unknown'),clear=True):
                        with self.assertRaises(Exception):pipeline.guard()
                        with self.assertRaises(Exception):source.guard()
                    request.write_bytes(request.read_bytes()+b' ')
                    with self.assertRaisesRegex(ValueError,'REQUEST_GIT'):d.verify(root,forwarded)
                    request.write_bytes(d.git(root,'show','HEAD:'+d.REQUEST))
                    (root/d.SOURCE).write_bytes((root/d.SOURCE).read_bytes()+b' ')
                    with self.assertRaisesRegex(ValueError,'TRACKED_INPUT'):d.verify(root,forwarded)

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


if __name__=='__main__':unittest.main()
