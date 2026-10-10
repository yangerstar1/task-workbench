"""Host-only checks of fresh same-job feedback evidence; synthetic XML is not native evidence."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import journey_combat_feedback_native as n


def xml_bytes(names=None):
    root = ET.Element('test-run', dict(result='Passed', total='7', passed='7', failed='0', skipped='0', inconclusive='0'))
    for name in n.EXPECTED if names is None else names:
        ET.SubElement(root, 'test-case', dict(fullname=name, result='Passed', duration='0.125'))
    return ET.tostring(root)


class FeedbackEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.artifacts = self.root / 'artifacts'; self.artifacts.mkdir()
        self.xml = self.artifacts / 'results.xml'; self.xml.write_bytes(xml_bytes())
        self.report = self.root / 'report.json'
        self.isolation = self.root / 'isolation.json'
        self.env = dict(GITHUB_SHA='a' * 40, GITHUB_RUN_ID='9876', GITHUB_RUN_ATTEMPT='1',
                        NATIVE_OUTCOME='success', GITHUB_OUTPUT=str(self.root / 'outputs'))
        state = self.root / 'SOURCE-STATE.json'; state.write_text('{}')
        (self.root / 'test.cs').write_text('synthetic test source')
        self.identity = n.isolated.owner_identity(self.env)
        self.isolation.write_text(json.dumps(dict(self.identity, status='PASS', sourceStateSha256=n.sha(state.read_bytes()))))

    def tearDown(self):
        self.temp.cleanup()

    def run_fixture(self, env=None, source_check=None):
        with mock.patch.multiple(n, ROOT=self.root, TASK=self.root, REPORT=self.report,
                                 ARTIFACTS=self.artifacts, TEST_SOURCE='test.cs'), \
             mock.patch.object(n.isolated, 'ISOLATION_REPORT', self.isolation), \
             mock.patch.object(n.isolated, 'verify_unchanged', side_effect=source_check), \
             mock.patch.object(n.isolated, 'validate_isolation', return_value=True):
            return n.run(self.env if env is None else env)

    def test_exact_seven_and_safe_excerpt(self):
        root = ET.fromstring(xml_bytes())
        root.find('test-case').set('secret', 'PRIVATE_NATIVE_DATA')
        ET.SubElement(root, 'environment').text = 'PRIVATE_NATIVE_DATA'
        self.xml.write_bytes(ET.tostring(root))
        self.assertEqual(self.run_fixture(), 0)
        report = json.loads(self.report.read_bytes())
        self.assertTrue(n.validate_report(report))
        self.assertEqual(report['nativeCases'], 7)
        self.assertEqual(report['nativeResults'], [dict(fullname=name, result='Passed', durationSeconds=.125) for name in n.EXPECTED])
        self.assertEqual(report['nativeXmlSha256'], hashlib.sha256(self.xml.read_bytes()).hexdigest())
        self.assertNotIn('PRIVATE_NATIVE_DATA', self.report.read_text())
        self.assertIn('native_verified=true', Path(self.env['GITHUB_OUTPUT']).read_text())

    def test_old_keyboard_or_unrelated_omitted_duplicate_cases_reject(self):
        for names in ([], list(n.isolated.EXPECTED), [n.isolated.EXPECTED[0]], [n.EXPECTED[0]] * 7, ['Other.Case']):
            with self.subTest(names=names):
                self.xml.write_bytes(xml_bytes(names))
                with self.assertRaisesRegex(ValueError, 'EXACT_SEVEN'):
                    n.inspect_xml(self.artifacts)

    def test_failed_skipped_inconclusive_totals_and_case_outcome_reject(self):
        for key, value in [('result', 'Failed'), ('total', '2'), ('passed', '0'), ('failed', '1'), ('skipped', '1'), ('inconclusive', '1')]:
            with self.subTest(key=key):
                root = ET.fromstring(xml_bytes()); root.set(key, value); self.xml.write_bytes(ET.tostring(root))
                with self.assertRaises(ValueError): n.inspect_xml(self.artifacts)
        for value in ('Failed', 'Skipped', 'Inconclusive'):
            root = ET.fromstring(xml_bytes()); root.find('test-case').set('result', value); self.xml.write_bytes(ET.tostring(root))
            with self.assertRaises(ValueError): n.inspect_xml(self.artifacts)

    def test_nonfinite_negative_and_unbounded_native_duration_reject(self):
        for duration in ('nan', 'inf', '-1', '86401'):
            root = ET.fromstring(xml_bytes()); root.find('test-case').set('duration', duration); self.xml.write_bytes(ET.tostring(root))
            with self.assertRaises(ValueError): n.inspect_xml(self.artifacts)

    def test_entity_symlink_hardlink_extra_xml_and_oversize_reject(self):
        other = self.artifacts / 'extra.xml'; other.write_bytes(xml_bytes())
        with self.assertRaisesRegex(ValueError, 'XML_COUNT'): n.inspect_xml(self.artifacts)
        other.unlink()
        self.xml.write_bytes(b'<!DOCTYPE test-run [<!ENTITY x "PRIVATE">]>' + xml_bytes())
        with self.assertRaisesRegex(ValueError, 'XML_DECLARATION'): n.inspect_xml(self.artifacts)
        self.xml.write_bytes(b' ' * (1024 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, 'UNSAFE_FILE'): n.inspect_xml(self.artifacts)
        self.xml.unlink(); outside = self.root / 'payload'; outside.write_bytes(xml_bytes()); self.xml.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'UNSAFE_PATH'): n.inspect_xml(self.artifacts)
        self.xml.unlink(); os.link(outside, self.xml)
        with self.assertRaisesRegex(ValueError, 'UNSAFE_FILE'): n.inspect_xml(self.artifacts)

    def test_native_failure_cannot_export_pass_or_raw_error(self):
        for outcome in ('failure', 'cancelled', 'skipped', 'unknown'):
            with self.subTest(outcome=outcome):
                self.assertEqual(self.run_fixture(dict(self.env, NATIVE_OUTCOME=outcome)), 2)
                report = json.loads(self.report.read_bytes()); self.assertTrue(n.validate_report(report))
                self.assertEqual(report['nativeCases'], 0)
                self.assertNotIn('native_verified', Path(self.env['GITHUB_OUTPUT']).read_text())
                self.report.unlink()
        def fail_source(context):
            context['phase'] = 'INITIAL_SOURCE'; raise ValueError('PRIVATE_SOURCE_PATH')
        self.assertEqual(self.run_fixture(source_check=fail_source), 2)
        report = json.loads(self.report.read_bytes()); self.assertTrue(n.validate_report(report))
        self.assertEqual(report['nativeCases'], 7)
        self.assertEqual(report['failurePhase'], 'INITIAL_SOURCE')
        self.assertNotIn('PRIVATE_SOURCE_PATH', self.report.read_text())

    def test_cross_run_commit_attempt_or_source_state_isolation_rejected(self):
        original = json.loads(self.isolation.read_bytes())
        for change in ({'sourceCommit': 'b' * 40}, {'runId': '9875'}, {'runAttempt': '2'}, {'sourceStateSha256': 'c' * 64}, {'status': 'FAIL'}):
            self.isolation.write_text(json.dumps(dict(original, **change)))
            self.assertEqual(self.run_fixture(), 2)
            report = json.loads(self.report.read_bytes()); self.assertTrue(n.validate_report(report))
            self.assertEqual(report['failurePhase'], 'ISOLATED_COPY')
            self.assertFalse(report['originalSourceUnchanged'])
            self.report.unlink()

    def test_report_no_overwrite_and_strict_schema(self):
        self.assertEqual(self.run_fixture(), 0)
        before = self.report.read_bytes(); value = json.loads(before)
        with self.assertRaisesRegex(ValueError, 'REPORT_PATH'): self.run_fixture()
        self.assertEqual(self.report.read_bytes(), before)
        for change in ({'schema': True}, {'expectedNativeCases': 4}, {'nativeCases': True},
                       {'nativeCases': 4}, {'resultScope': 'PLAYER_PASSED'}, {'testSourceSha256': ''},
                       {'sourceCommit': 'bad'}, {'runAttempt': '2'}, {'originalSourceUnchanged': 1},
                       {'importUnionUnchanged': 1}, {'secret': 'PRIVATE'}):
            self.assertFalse(n.validate_report(dict(value, **change)))
        changed = copy.deepcopy(value); changed['nativeResults'][0]['fullname'] = n.isolated.EXPECTED[0]
        self.assertFalse(n.validate_report(changed))
        self.assertEqual(n.main([]), 2)
        self.assertEqual(n.main(['native', '/tmp/unreviewed']), 2)

    def test_preserve_bounded_report_checks_current_job_identity(self):
        self.assertEqual(self.run_fixture(), 0)
        destination = self.root / 'preparation' / 'combat-feedback'; destination.parent.mkdir()
        with mock.patch.multiple(n, REPORT=self.report, PREPARATION_REPORTS=destination):
            with self.assertRaisesRegex(ValueError, 'REPORT_IDENTITY'):
                n.preserve(dict(self.env, GITHUB_RUN_ID='9877'))
            self.assertFalse(destination.exists())
            self.assertEqual(n.preserve(self.env), 0)
            self.assertEqual((destination / 'native-report.json').read_bytes(), self.report.read_bytes())
            with self.assertRaisesRegex(ValueError, 'REPORT_PATH'): n.preserve(self.env)

    def test_workflow_keeps_exact_seven_before_all_strict_build_gates(self):
        import yaml
        path = n.ROOT / '.github/workflows/desert-rv-tracer-shader-prepare.yml'
        steps = yaml.load(path.read_text(), Loader=yaml.BaseLoader)['jobs']['prepare']['steps']
        by_id = {step['id']: step for step in steps if 'id' in step}
        order = [step.get('id', '') for step in steps]
        native = by_id['combat_feedback_native']
        self.assertEqual(native['with']['customParameters'], '-assemblyNames DesertRV.EditModeTests -testFilter DesertRV.Tests.JourneyCombatFeedbackTests -force-glcore -job-worker-count 2')
        self.assertEqual(native['with']['projectPath'], n.isolated.COPY_REL)
        self.assertEqual(native['with']['testMode'], 'editmode')
        self.assertEqual(native['with']['artifactsPath'], str(n.ARTIFACTS.relative_to(n.ROOT)))
        self.assertIn("steps.keyboard_copy.outputs.copy_ready == 'true'", native['if'])
        for before, after in [('region_hud_native', 'combat_feedback_native'),
                              ('combat_feedback_native', 'keyboard_isolation'),
                              ('keyboard_isolation', 'combat_feedback_verify'),
                              ('combat_feedback_verify', 'keyboard_cleanup'),
                              ('keyboard_cleanup', 'stage_armored')]:
            self.assertLess(order.index(before), order.index(after))
        gate = by_id['stage_armored']['if']
        for requirement in ("steps.combat_feedback_native.outcome == 'success'",
                            "steps.combat_feedback_verify.outcome == 'success'",
                            "steps.combat_feedback_verify.outputs.native_verified == 'true'"):
            self.assertIn(requirement, gate)
        self.assertEqual(sum('game-ci/unity-test-runner@' in step.get('uses', '') for step in steps), 10)
        self.assertEqual(sum(step.get('id') == 'linux_native' for step in steps), 1)
        source = (n.ROOT / n.TEST_SOURCE).read_text()
        for name in n.EXPECTED:
            self.assertIn(name.split('.')[-1] + '()', source)
        self.assertNotIn('journey_combat_feedback_probe.py finish', path.read_text())
        for step in steps:
            if 'run' in step:
                checked = subprocess.run(['bash', '-n'], input=step['run'], text=True, capture_output=True)
                self.assertEqual(checked.returncode, 0, step['name'] + checked.stderr)


if __name__ == '__main__':
    unittest.main()
