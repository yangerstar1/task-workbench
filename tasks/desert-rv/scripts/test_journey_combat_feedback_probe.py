"""Host contract tests only. These fixtures are not native Unity execution."""
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import journey_combat_feedback_probe as probe


class FeedbackProbeTests(unittest.TestCase):
    def identity_fixture(self):
        head = 'a' * 40
        env = dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=probe.admission.REPOSITORY,
                   GITHUB_REPOSITORY_VISIBILITY='public', RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Linux',
                   GITHUB_ACTOR=probe.admission.OWNER, GITHUB_TRIGGERING_ACTOR=probe.admission.OWNER,
                   GITHUB_EVENT_NAME='push', GITHUB_REF=probe.REF,
                   GITHUB_WORKFLOW_REF=probe.admission.REPOSITORY + '/' + probe.WORKFLOW + '@' + probe.REF,
                   GITHUB_SHA=head, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1')
        event = dict(before=probe.BASE, after=head, ref=probe.REF, created=False, deleted=False, forced=False,
                     repository=dict(full_name=probe.admission.REPOSITORY, private=False, fork=False, default_branch='main', owner=dict(login=probe.admission.OWNER)),
                     sender=dict(login=probe.admission.OWNER), head_commit=dict(id=head))
        raw = json.dumps(dict(schema=1, requestId=probe.REQUEST_ID, baseCommit=probe.BASE, sourceStateSha256='b' * 64)).encode()
        return dict(env=env, event=event, head=head, parents=[probe.BASE], request_raw=raw, tracked_raw=raw,
                    present=False, changed=sorted(probe.CHANGED), source_sha='b' * 64)

    def test_exact_identity_accepted(self):
        self.assertEqual(probe.validate_identity(**self.identity_fixture())['baseCommit'], probe.BASE)

    def test_runner_actor_attempt_and_ref_fail_closed(self):
        for key, value in dict(GITHUB_ACTIONS='false', GITHUB_REPOSITORY_VISIBILITY='private', RUNNER_ENVIRONMENT='self-hosted',
                               RUNNER_OS='Windows', GITHUB_ACTOR='other', GITHUB_TRIGGERING_ACTOR='other',
                               GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_REF='refs/heads/main',
                               GITHUB_WORKFLOW_REF='wrong', GITHUB_SHA='c' * 40, GITHUB_RUN_ID='0', GITHUB_RUN_ATTEMPT='2').items():
            with self.subTest(key=key):
                fixture = self.identity_fixture(); fixture['env'][key] = value
                with self.assertRaises(ValueError): probe.validate_identity(**fixture)

    def test_event_and_exact_parent_fail_closed(self):
        for key, value in dict(before='c' * 40, after='c' * 40, ref='refs/heads/main', created=True, deleted=True, forced=True).items():
            with self.subTest(key=key):
                fixture = self.identity_fixture(); fixture['event'][key] = value
                with self.assertRaises(ValueError): probe.validate_identity(**fixture)
        for key, value in dict(parents=[probe.BASE, 'd' * 40], present=True, changed=sorted(probe.CHANGED) + ['tasks/desert-rv/unity/Assets/Injected.cs'], source_sha='c' * 64, tracked_raw=b'changed').items():
            with self.subTest(key=key):
                fixture = self.identity_fixture(); fixture[key] = value
                with self.assertRaises(ValueError): probe.validate_identity(**fixture)

    def test_repository_fork_and_sender_rejected(self):
        for mutate in (lambda e: e['repository'].update(private=True), lambda e: e['repository'].update(fork=True),
                       lambda e: e['repository'].update(default_branch='elsewhere'), lambda e: e['sender'].update(login='other')):
            fixture = self.identity_fixture(); mutate(fixture['event'])
            with self.assertRaises(ValueError): probe.validate_identity(**fixture)

    def test_real_git_parent_request_and_source_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL).decode().strip()
            git('init', '-q')
            git('config', 'user.name', 'Host Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            original = root / 'tasks/desert-rv/unity/Assets/fixture.cs'
            original.parent.mkdir(parents=True); original.write_text('unchanged fixture source\n')
            fixture_after = (probe.ROOT / probe.TEST_SOURCE).read_bytes()
            driving = b'            Production.Call(state, "SetControl", Production.Enum("ControlMode", "Driving"));\n'
            advance = b'            Production.Advance(state, "RamPart", "test-ram");\n'
            fixture_before = fixture_after.replace(driving + advance, advance, 1)
            fixture_source = root / probe.TEST_SOURCE
            fixture_source.parent.mkdir(parents=True); fixture_source.write_bytes(fixture_before)
            runner = root / 'tasks/desert-rv/scripts/prepare_runner.sh'
            runner.parent.mkdir(parents=True); runner.write_text('unchanged runner fixture\n')
            git('add', '.'); git('commit', '-qm', 'Synthetic parent')
            base = git('rev-parse', 'HEAD')
            state = b'{}\n'
            for name in probe.CHANGED:
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(fixture_after if name == probe.TEST_SOURCE else state)
            request = dict(schema=1, requestId=probe.REQUEST_ID, baseCommit=base, sourceStateSha256=probe.pin(state))
            (root / probe.REQUEST).write_text(json.dumps(request))
            git('add', '.'); git('commit', '-qm', 'Synthetic gate')
            fixture = self.identity_fixture(); head = git('rev-parse', 'HEAD')
            fixture['env']['GITHUB_SHA'] = head
            fixture['event'].update(before=base, after=head, head_commit=dict(id=head))
            event = root / 'event.json'; event.write_text(json.dumps(fixture['event']))
            fixture['env']['GITHUB_EVENT_PATH'] = str(event)
            with patch.object(probe, 'ROOT', root), patch.object(probe, 'BASE', base):
                self.assertEqual(probe.verify_dispatch(fixture['env']), request)
                (root / probe.WORKFLOW).write_text('untracked workflow modification')
                with self.assertRaises(ValueError): probe.verify_dispatch(fixture['env'])

    def test_only_missing_driving_fixture_transition_is_allowed(self):
        after = (probe.ROOT / probe.TEST_SOURCE).read_bytes()
        driving = b'            Production.Call(state, "SetControl", Production.Enum("ControlMode", "Driving"));\n'
        advance = b'            Production.Advance(state, "RamPart", "test-ram");\n'
        before = after.replace(driving + advance, advance, 1)
        probe.verify_fixture_change(before, after)
        for other in (before, after + b'// extra change\n', after.replace(b'Is.EqualTo(85)', b'Is.EqualTo(86)', 1),
                      after.replace(driving + advance, advance + driving, 1)):
            with self.assertRaises(ValueError): probe.verify_fixture_change(before, other)
        with self.assertRaises(ValueError): probe.verify_fixture_change(before + b' ', after)

    def test_r2_request_leaves_original_request_unchanged(self):
        old = probe.ROOT / '.github/dispatch/desert-rv-combat-feedback-r1-20261010.json'
        self.assertEqual(probe.pin(old.read_bytes()), 'c4d3a104c7160f1d349393d8d60696168fe021f466a8319158ed340f1ad8655f')
        self.assertNotIn(old.relative_to(probe.ROOT).as_posix(), probe.CHANGED)
        self.assertEqual(probe.BASE, 'ec4d6329d9ef372d3d4518b9fcc113c1c5e0c877')
        self.assertEqual(probe.REQUEST_ID, 'desert-rv-combat-feedback-r2-20261010-once')

    def test_request_shape_duplicates_and_replay_rejected(self):
        original = self.identity_fixture()['request_raw']
        for raw in (original.replace(b'"schema": 1', b'"schema": true'), original.replace(probe.REQUEST_ID.encode(), b'old-request'),
                    original[:-1] + b', "extra": 1}', original[:-1] + b', "schema": 1}', b'{}', b'x' * 2049):
            with self.assertRaises(ValueError): probe.parse_request(raw)

    def xml_fixture(self, failed=False):
        rows = [dict(fullname=name, result='Failed' if failed and index == 0 else 'Passed', durationSeconds=.01)
                for index, name in enumerate(probe.EXPECTED)]
        return probe.derived_xml(rows)

    def parse_xml(self, raw):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); (folder / 'results.xml').write_bytes(raw)
            return probe.inspect_xml(folder)

    def test_exact_seven_pass_and_failure_retained(self):
        for failed in (False, True):
            raw = self.xml_fixture(failed); digest, rows = self.parse_xml(raw)
            self.assertEqual(digest, hashlib.sha256(raw).hexdigest())
            self.assertEqual([row['fullname'] for row in rows], list(probe.EXPECTED))
            self.assertEqual(sum(row['result'] == 'Passed' for row in rows), 6 if failed else 7)

    def test_missing_duplicate_wrong_and_skipped_cases_rejected(self):
        for mutate in (lambda r: r.remove(r[-1]), lambda r: r[-1].set('fullname', probe.EXPECTED[0]),
                       lambda r: r[-1].set('fullname', 'Unrelated.Case'), lambda r: r[-1].set('result', 'Skipped'),
                       lambda r: r.set('passed', '6'), lambda r: r.set('result', 'Failed'),
                       lambda r: r[-1].set('duration', 'nan'), lambda r: r[-1].set('duration', '-1')):
            root = ET.fromstring(self.xml_fixture()); mutate(root)
            with self.assertRaises(ValueError): self.parse_xml(ET.tostring(root))

    def test_entity_and_multiple_xml_rejected(self):
        with self.assertRaises(ValueError): self.parse_xml(b'<!DOCTYPE test-run>' + self.xml_fixture())
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'one.xml').write_bytes(self.xml_fixture()); (folder / 'two.xml').write_bytes(self.xml_fixture())
            with self.assertRaises(ValueError): probe.inspect_xml(folder)

    def test_symlink_xml_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); (folder / 'raw').write_bytes(self.xml_fixture()); (folder / 'result.xml').symlink_to('raw')
            with self.assertRaises(ValueError): probe.inspect_xml(folder)

    def test_export_omits_raw_xml_messages_and_attributes(self):
        root = ET.fromstring(self.xml_fixture(True))
        root.set('command-line', 'PRIVATE_SENTINEL')
        ET.SubElement(root[0], 'output').text = 'PRIVATE_SENTINEL'
        ET.SubElement(ET.SubElement(root[0], 'failure'), 'message').text = 'PRIVATE_SENTINEL'
        _, rows = self.parse_xml(ET.tostring(root))
        self.assertNotIn(b'PRIVATE_SENTINEL', probe.derived_xml(rows))

    def test_finish_success_failure_and_incomplete_outcomes(self):
        for native_outcome, failed, corrupt_source, expected_status in (
                ('success', False, False, 'PASS'), ('failure', True, False, 'NATIVE_FAILED'),
                ('success', True, False, 'INCOMPLETE'), ('failure', False, False, 'INCOMPLETE'),
                ('success', False, True, 'INCOMPLETE')):
            with self.subTest(native_outcome=native_outcome, failed=failed, corrupt_source=corrupt_source), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); export = root / 'export'; artifacts = root / 'artifacts'; artifacts.mkdir()
                (artifacts / 'results.xml').write_bytes(self.xml_fixture(failed))
                env = dict(GITHUB_SHA='a' * 40, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1', NATIVE_OUTCOME=native_outcome, GITHUB_OUTPUT=str(root / 'output'))
                # Only identity/source/isolation are fixtures. XML parsing and all
                # public writes use the real implementation, including failures.
                with patch.object(probe, 'EXPORT', export), patch.object(probe, 'ARTIFACTS', artifacts), \
                     patch.object(probe, 'verify_dispatch'), patch.object(probe, 'configure_copy'), \
                     patch.object(probe, 'verify_unchanged', side_effect=ValueError('PRIVATE_SENTINEL') if corrupt_source else None), \
                     patch.object(probe.isolated, 'inspect_copy', return_value=0):
                    result = probe.finish(env)
                report = json.loads((export / 'report.json').read_bytes())
                self.assertEqual(report['status'], expected_status)
                self.assertEqual(result, 0 if expected_status == 'PASS' else 2)
                self.assertNotIn(b'PRIVATE_SENTINEL', (export / 'report.json').read_bytes())
                if report['nativeCases']:
                    self.assertEqual(probe.pin((export / 'derived-exact-seven.xml').read_bytes()), report['derivedXmlSha256'])
                self.assertLess((export / 'report.json').stat().st_size, 8192)

    def test_workflow_is_bounded_and_native_only(self):
        workflow = (probe.ROOT / probe.WORKFLOW).read_text()
        self.assertIn('timeout-minutes: 60', workflow)
        self.assertIn('testMode: editmode', workflow)
        self.assertIn('-testFilter DesertRV.Tests.JourneyCombatFeedbackTests ', workflow)
        self.assertEqual(workflow.count('uses: game-ci/unity-test-runner@'), 1)
        self.assertNotIn('BuildPlayer', workflow)
        self.assertNotIn('unity-builder', workflow)
        self.assertNotIn('workflow_dispatch:', workflow)
        self.assertNotIn('actions: write', workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertIn('sha256:17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264', workflow)
        self.assertIn('python3 tasks/desert-rv/scripts/journey_combat_feedback_probe.py guard', workflow)
        self.assertIn('sudo --preserve-env=GITHUB_SHA,GITHUB_RUN_ID,GITHUB_RUN_ATTEMPT /usr/bin/python3 -I -B', workflow)

    def test_seven_source_cases_and_210_inventory_match(self):
        import re
        text = (probe.ROOT / probe.TEST_SOURCE).read_text()
        names = {probe.PREFIX + name for name in re.findall(r'\[Test\] public void (\w+)\(', text)}
        self.assertEqual(names, set(probe.EXPECTED))
        inventory = json.loads((probe.TASK / 'scripts/expected_test_cases.json').read_text())
        self.assertEqual(len(inventory), 210)
        self.assertTrue(names <= set(inventory))
        self.assertFalse(any(token in text for token in ('AssetDatabase', 'LoadScene', 'ReadAllText', 'ReadAllBytes')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
