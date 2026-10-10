"""Focused four-case evidence and post-PlayMode source preservation regressions."""
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import journey_keyboard_look_native as n


def xml_bytes(names=None):
    root = ET.Element('test-run', dict(result='Passed', total='4', passed='4', failed='0', skipped='0', inconclusive='0'))
    for name in n.EXPECTED if names is None else names:
        ET.SubElement(root, 'test-case', dict(fullname=name, result='Passed'))
    return ET.tostring(root)


class KeyboardNativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.xml = self.root / 'native.xml'
        self.xml.write_bytes(xml_bytes())
        self.env = dict(GITHUB_SHA='a' * 40, GITHUB_RUN_ID='9876', GITHUB_RUN_ATTEMPT='1',
                        NATIVE_OUTCOME='success', GITHUB_OUTPUT=str(self.root / 'output'))

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_four_native_methods_and_supported_workflow_filter(self):
        import yaml
        xml_sha, results = n.inspect_xml(self.root)
        self.assertEqual(xml_sha, hashlib.sha256(self.xml.read_bytes()).hexdigest())
        self.assertEqual(results, [dict(fullname=name, result='Passed') for name in sorted(n.EXPECTED)])
        source = (n.ROOT / n.TEST_SOURCE).read_text()
        self.assertEqual(len(n.EXPECTED), 4)
        original_playmode = ['DesertRV.Tests.JourneyLoaderPlayModeTests.MissingRegion_RemainsLoadingAndSameTicketCanRetry', 'DesertRV.Tests.JourneyReplayInputTests.ContextCancellation_HeldReplayRequiresLiftBeforeRepress', 'DesertRV.Tests.JourneyReplayInputTests.HeldFire_SurvivesAdapterSampleWithoutNewPressedEdge', 'DesertRV.Tests.JourneyReplayInputTests.ScopeRequestHashChange_InvalidatesAndCloseClearsCapability', 'DesertRV.Tests.RegionLoaderActiveSceneTests.LoadedRegion_IsActiveWithItsRenderSettingsBeforeReady', 'DesertRV.Tests.RegionLoaderActiveSceneTests.ReadyException_RestoresActiveReleasesBusyAndKeepsTicket', 'DesertRV.Tests.RegionLoaderActiveSceneTests.RejectedSameNameReload_RestoresPreviousActiveAndAllowsSameTicketRetry', 'DesertRV.Tests.RegionLoaderActiveSceneTests.StaleGenerationLoad_DoesNotStealNewerActiveScene', 'DesertRV.Tests.RegionLoaderActiveSceneTests.UnloadedScene_ActivationFailsWithoutChangingActiveScene']
        actual_playmode = json.loads((n.TASK / 'scripts/expected_playmode_test_cases.json').read_text())
        self.assertEqual(actual_playmode, sorted(original_playmode + list(n.EXPECTED)))
        for name in n.EXPECTED:
            self.assertRegex(source, r'\[Test\]\s+public\s+void\s+' + re.escape(name[len(n.PREFIX):]) + r'\(')
        steps = yaml.load((n.ROOT / '.github/workflows/desert-rv-tracer-shader-prepare.yml').read_text(), Loader=yaml.BaseLoader)['jobs']['prepare']['steps']
        native = next(s for s in steps if s.get('id') == 'keyboard_native')
        self.assertEqual(native['uses'], 'game-ci/unity-test-runner@0ff419b913a3630032cbe0de48a0099b5a9f0ed9')
        self.assertEqual(native['with']['testMode'], 'playmode')
        self.assertEqual(native['with']['customParameters'], '-assemblyNames DesertRV.PlayModeTests -testFilter ' + ';'.join(n.EXPECTED) + ' -force-glcore -job-worker-count 2')
        # Pinned GameCI run_tests.sh expands CUSTOM_PARAMETERS directly, without eval.
        actual = subprocess.check_output(['bash', '-c', 'set -- $CUSTOM_PARAMETERS; printf "%s\\n" "$@"'],
                                        env=dict(os.environ, CUSTOM_PARAMETERS=native['with']['customParameters'])).decode().splitlines()
        self.assertEqual(actual, ['-assemblyNames', 'DesertRV.PlayModeTests', '-testFilter', ';'.join(n.EXPECTED), '-force-glcore', '-job-worker-count', '2'])
        order = [s.get('id', '') for s in steps]
        self.assertLess(order.index('tracer_verify'), order.index('keyboard_native'))
        self.assertLess(order.index('keyboard_native'), order.index('keyboard_source'))
        self.assertLess(order.index('keyboard_source'), order.index('keyboard_verify'))
        self.assertLess(order.index('keyboard_verify'), order.index('stage_armored'))
        for ident in ('keyboard_source', 'keyboard_verify'):
            step = next(s for s in steps if s.get('id') == ident)
            self.assertEqual(step['if'], "always() && steps.keyboard_native.outcome != 'skipped'")
        stage = next(s for s in steps if s.get('id') == 'stage_armored')
        for expression in ("steps.keyboard_source.outcome == 'success'", "steps.keyboard_source.outputs.source_unchanged == 'true'",
                           "steps.keyboard_verify.outcome == 'success'", "steps.keyboard_verify.outputs.native_verified == 'true'"):
            self.assertIn(expression, stage['if'])

    def test_omitted_duplicate_extra_failed_skipped_and_wrong_counts_reject(self):
        names = list(n.EXPECTED)
        for changed in ([], names[:-1], names + [names[0]], names[:-1] + [names[0]], names[:-1] + ['Unrelated.Test']):
            self.xml.write_bytes(xml_bytes(changed))
            with self.subTest(names=changed), self.assertRaises(ValueError):
                n.inspect_xml(self.root)
        for key, value in [('result', 'Failed'), ('total', '10'), ('passed', '3'), ('failed', '1'), ('skipped', '1'), ('inconclusive', '1')]:
            root = ET.fromstring(xml_bytes()); root.set(key, value); self.xml.write_bytes(ET.tostring(root))
            with self.subTest(key=key), self.assertRaises(ValueError):
                n.inspect_xml(self.root)
        for value in ('Failed', 'Skipped', 'Inconclusive', 'Unknown'):
            root = ET.fromstring(xml_bytes()); root.find('test-case').set('result', value); self.xml.write_bytes(ET.tostring(root))
            with self.subTest(result=value), self.assertRaises(ValueError):
                n.inspect_xml(self.root)

    def test_xml_size_entity_duplicate_file_and_link_reject(self):
        second = self.root / 'second.xml'; second.write_bytes(xml_bytes())
        with self.assertRaisesRegex(ValueError, 'XML_COUNT'): n.inspect_xml(self.root)
        second.unlink(); self.xml.write_bytes(b' ' * (1024 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, 'XML_SIZE'): n.inspect_xml(self.root)
        self.xml.write_bytes(b'<!DOCTYPE test-run [<!ENTITY secret "PRIVATE_TOKEN">]>' + xml_bytes())
        with self.assertRaisesRegex(ValueError, 'XML_DECLARATION'): n.inspect_xml(self.root)
        self.xml.unlink(); target = self.root / 'payload'; target.write_bytes(xml_bytes()); self.xml.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'UNSAFE_INPUT'): n.inspect_xml(self.root)

    def test_native_report_closes_on_outcome_and_source_failures_without_raw_errors(self):
        report = self.root / 'report.json'
        def reject_source(context):
            context['phase'] = 'INITIAL_SOURCE'
            raise ValueError('PRIVATE_TOKEN')
        for outcome, phase in [('failure', 'NATIVE_OUTCOME'), ('cancelled', 'NATIVE_OUTCOME'), ('success', 'INITIAL_SOURCE')]:
            with mock.patch.object(n, 'REPORT', report), mock.patch.object(n, 'ARTIFACTS', self.root), mock.patch.object(n, 'verify_unchanged', side_effect=reject_source):
                self.assertEqual(n.run(dict(self.env, NATIVE_OUTCOME=outcome)), 2)
                value = json.loads(report.read_text()); self.assertTrue(n.validate_report(value))
                self.assertEqual(value['failurePhase'], phase)
                self.assertNotIn('PRIVATE_TOKEN', report.read_text())
                self.assertNotIn('native_verified', Path(self.env['GITHUB_OUTPUT']).read_text())
                before = report.read_bytes()
                with self.assertRaisesRegex(ValueError, 'REPORT_PATH'): n.run(self.env)
                self.assertEqual(report.read_bytes(), before)
                report.unlink()
        for change in ({'schema': True}, {'expectedNativeCases': 10}, {'nativeCases': 4}, {'status': 'PASS'}, {'secret': 'PRIVATE_TOKEN'}):
            self.assertFalse(n.validate_report(dict(value, **change)))
        self.assertEqual(n.main([]), 2)
        self.assertEqual(n.main(['source', 'arbitrary-output']), 2)

    def test_pass_result_excerpt_allows_only_fixed_names_and_finite_native_durations(self):
        root = ET.fromstring(xml_bytes())
        root.find('test-case').set('duration', '0.125')
        root.find('test-case').set('private-extra', 'PRIVATE_TOKEN')
        ET.SubElement(root, 'environment', dict(secret='PRIVATE_TOKEN'))
        self.xml.write_bytes(ET.tostring(root))
        state = self.root / 'SOURCE-STATE.json'; state.write_text('{}')
        source = self.root / 'test.cs'; source.write_text('fixture')
        report = self.root / 'report.json'
        with mock.patch.multiple(n, ROOT=self.root, TASK=self.root, TEST_SOURCE='test.cs', REPORT=report, ARTIFACTS=self.root), mock.patch.object(n, 'verify_unchanged'):
            self.assertEqual(n.run(self.env), 0)
        value = json.loads(report.read_text())
        self.assertTrue(n.validate_report(value))
        self.assertEqual(value['testPlatform'], 'PlayMode')
        self.assertEqual(value['assembly'], 'DesertRV.PlayModeTests')
        self.assertEqual(value['resultScope'], 'DERIVED_EXACT_RESULTS')
        self.assertNotIn('PRIVATE_TOKEN', report.read_text())
        self.assertTrue(any(row.get('durationSeconds') == .125 for row in value['nativeResults']))
        self.assertIn('native_verified=true', Path(self.env['GITHUB_OUTPUT']).read_text())
        for duration in ('NaN', 'Infinity', '-1', '86401', 'private'):
            root.find('test-case').set('duration', duration); self.xml.write_bytes(ET.tostring(root))
            with self.subTest(duration=duration), self.assertRaises(ValueError): n.inspect_xml(self.root)
        for key, item in [('durationSeconds', float('nan')), ('durationSeconds', True), ('rawLog', 'PRIVATE_TOKEN'), ('fullname', 'Other.Case')]:
            changed = copy.deepcopy(value); changed['nativeResults'][0][key] = item
            self.assertFalse(n.validate_report(changed))

    def test_failed_native_source_scan_keeps_old_report_and_exact_drift_without_rebaseline(self):
        import journey_tracer_source_diagnostic as d
        from test_journey_tracer_source_diagnostic import DiagnosticTests
        fixture = DiagnosticTests(); fixture.setUp()
        try:
            name = d.PREFIX + 'Assets/owned.cs'; path = fixture.file(name, b'initial source')
            fixture.baseline(); path.write_bytes(b'native changed source')
            old_report = d.REPORT; old_report.write_bytes(b'prior tracer evidence')
            output = fixture.task / 'keyboard-source.json'
            gates = {key: dict(status='PASS', errorClass='NONE') for key in d.CHECKS}
            baseline = (fixture.source, copy.deepcopy(fixture.expected), 'b' * 64)
            with mock.patch.object(n, 'SOURCE_REPORT', output), mock.patch.object(d, 'pinned_baseline', return_value=baseline), mock.patch.object(d, 'check_original_gates', return_value=gates):
                self.assertEqual(n.run_source(fixture.env), 2)
                self.assertEqual(d.REPORT, old_report)
                self.assertEqual(old_report.read_bytes(), b'prior tracer evidence')
                value = json.loads(output.read_text())
                self.assertEqual(value['nativeOutcome'], 'failure')
                self.assertEqual(value['status'], 'SOURCE_CHANGED')
                self.assertEqual(value['observedChanges'], dict(declaredSource=1, fixtureResidue=0, undeclared=0))
                row = value['records'][0]
                self.assertEqual(row['path'], name)
                self.assertEqual(row['before']['sha256'], d.sha(b'initial source'))
                self.assertEqual(row['after']['sha256'], d.sha(b'native changed source'))
                self.assertEqual(path.read_bytes(), b'native changed source')
                self.assertLessEqual(output.stat().st_size, d.MAX_REPORT)
                with self.assertRaises(Exception): n.run_source(fixture.env)
                self.assertEqual(d.REPORT, old_report)
                native_report = fixture.task / 'keyboard-native.json'
                native_report.write_text(json.dumps(n.blank_report(fixture.env)))
                prepared = fixture.task / 'journey-preparation-export'; prepared.mkdir()
                with mock.patch.object(n, 'REPORT', native_report), mock.patch.object(n, 'PREPARATION_REPORTS', prepared / 'keyboard-look'):
                    self.assertEqual(n.preserve(fixture.env), 0)
                    self.assertEqual((prepared / 'keyboard-look/native-report.json').read_bytes(), native_report.read_bytes())
                    self.assertEqual((prepared / 'keyboard-look/source-report.json').read_bytes(), output.read_bytes())
                    with self.assertRaises(Exception): n.preserve(fixture.env)
        finally:
            fixture.tearDown()


if __name__ == '__main__':
    unittest.main()
