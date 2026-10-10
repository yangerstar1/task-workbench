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
        self.assertEqual(native['with']['projectPath'], n.COPY_REL)
        self.assertNotIn('chownFilesTo', native['with'])
        self.assertEqual(native['with']['customParameters'], '-assemblyNames DesertRV.PlayModeTests -testFilter ' + ';'.join(n.EXPECTED) + ' -force-glcore -job-worker-count 2')
        # Pinned GameCI run_tests.sh expands CUSTOM_PARAMETERS directly, without eval.
        actual = subprocess.check_output(['bash', '-c', 'set -- $CUSTOM_PARAMETERS; printf "%s\\n" "$@"'],
                                        env=dict(os.environ, CUSTOM_PARAMETERS=native['with']['customParameters'])).decode().splitlines()
        self.assertEqual(actual, ['-assemblyNames', 'DesertRV.PlayModeTests', '-testFilter', ';'.join(n.EXPECTED), '-force-glcore', '-job-worker-count', '2'])
        order = [s.get('id', '') for s in steps]
        self.assertLess(order.index('keyboard_copy'), order.index('keyboard_native'))
        self.assertLess(order.index('keyboard_native'), order.index('keyboard_source'))
        self.assertLess(order.index('keyboard_source'), order.index('keyboard_verify'))
        self.assertLess(order.index('keyboard_verify'), order.index('keyboard_cleanup'))
        for ident in ('keyboard_source', 'keyboard_verify'):
            step = next(s for s in steps if s.get('id') == ident)
            self.assertEqual(step['if'], "always() && steps.keyboard_copy.outputs.copy_created == 'true'" if ident == 'keyboard_source' else "always() && steps.keyboard_native.outcome != 'skipped'")
        self.assertLess(order.index('keyboard_cleanup'), order.index('stage_armored'))
        self.assertIn('cabin_native', order)
        self.assertIn('cabin_report', order)

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
                self.assertEqual(value['nativeCases'], 4 if outcome == 'success' else 0)
                self.assertNotIn('PRIVATE_TOKEN', report.read_text())
                self.assertNotIn('native_verified', Path(self.env['GITHUB_OUTPUT']).read_text())
                before = report.read_bytes()
                with self.assertRaisesRegex(ValueError, 'REPORT_PATH'): n.run(self.env)
                self.assertEqual(report.read_bytes(), before)
                report.unlink()
        for change in ({'schema': True}, {'expectedNativeCases': 10}, {'nativeCases': 3}, {'status': 'PASS'}, {'secret': 'PRIVATE_TOKEN'}):
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
        isolation = self.root / 'isolation.json'; isolation.write_text(json.dumps(dict(n.owner_identity(self.env), status='PASS')))
        with mock.patch.multiple(n, ROOT=self.root, TASK=self.root, TEST_SOURCE='test.cs', REPORT=report, ARTIFACTS=self.root, ISOLATION_REPORT=isolation), mock.patch.object(n, 'verify_unchanged'), mock.patch.object(n, 'validate_isolation', return_value=True):
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
                isolation = fixture.task / 'isolation.json'; isolation.write_text(json.dumps(n.isolation_blank(fixture.env)))
                with mock.patch.object(n, 'REPORT', native_report), mock.patch.object(n, 'ISOLATION_REPORT', isolation), mock.patch.object(n, 'PREPARATION_REPORTS', prepared / 'keyboard-look'):
                    self.assertEqual(n.preserve(fixture.env), 0)
                    self.assertEqual((prepared / 'keyboard-look/native-report.json').read_bytes(), native_report.read_bytes())
                    self.assertEqual((prepared / 'keyboard-look/source-report.json').read_bytes(), output.read_bytes())
                    self.assertEqual((prepared / 'keyboard-look/isolation-report.json').read_bytes(), isolation.read_bytes())
                    with self.assertRaises(Exception): n.preserve(fixture.env)
        finally:
            fixture.tearDown()


class IsolatedProjectLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.task = self.root / 'tasks/desert-rv'; self.project = self.task / 'unity'
        for name in ('Assets/Empty', 'Packages', 'ProjectSettings'): (self.project / name).mkdir(parents=True)
        self.settings = b'%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!129 &1\nPlayerSettings:\n  productName: Desert RV - Technical Preflight\n  runInBackground: 0\n  scriptingDefineSymbols: {}\n  secretSetting: \n'
        (self.project / n.SETTINGS).write_bytes(self.settings)
        (self.project / 'Assets/font.otf').write_bytes(b'restored pinned font')
        (self.project / 'Packages/manifest.json').write_bytes(b'{}\n')
        self.rows, self.dirs = n.protected_inventory(self.project)
        self.copy = self.root / n.COPY_REL
        self.owner = self.task / 'journey-keyboard-look-copy-owner.json'
        self.report = self.task / 'journey-keyboard-look-isolation-report.json'
        self.env = dict(GITHUB_SHA='a'*40, GITHUB_RUN_ID='9876', GITHUB_RUN_ATTEMPT='1', GITHUB_OUTPUT=str(self.root/'output'))
        self.patches = [mock.patch.multiple(n, ROOT=self.root, TASK=self.task, PROJECT=self.project, COPY=self.copy, OWNER=self.owner, ISOLATION_REPORT=self.report),
                        mock.patch.object(n, 'copy_baseline', return_value=(self.rows, 'b'*64)), mock.patch.object(n, 'verify_unchanged')]
        for patch in self.patches: patch.start()
    def tearDown(self):
        for patch in reversed(self.patches): patch.stop()
        self.temp.cleanup()
    def create(self):
        self.assertEqual(n.create_copy(self.env), 0)
        self.assertIn('copy_ready=true', Path(self.env['GITHUB_OUTPUT']).read_text())
    def inspect(self, expected):
        self.assertEqual(n.inspect_copy(self.env), expected)
        report=json.loads(self.report.read_text()); self.assertTrue(n.validate_isolation(report))
        self.assertLessEqual(self.report.stat().st_size, n.MAX_ISOLATION_REPORT)
        return report
    def test_real_posix_copy_exact_bytes_distinct_inode_empty_dirs_and_owned_cleanup(self):
        self.create(); self.assertEqual(n.protected_inventory(self.copy),(self.rows,self.dirs))
        for name in self.rows:
            self.assertNotEqual((self.project/name).stat().st_ino,(self.copy/name).stat().st_ino)
            self.assertEqual((self.copy/name).stat().st_nlink,1)
        report=self.inspect(0); self.assertEqual(report['settingsStatus'],'UNCHANGED')
        (self.copy/'Library').mkdir(); (self.copy/'Library/cache').write_text('private cache')
        self.assertEqual(n.cleanup_copy(self.env),0); self.assertFalse(self.copy.exists())
        self.assertEqual(n.protected_inventory(self.project),(self.rows,self.dirs))
    def test_complete_settings_diff_is_exact_reconstructable_and_never_copied_back(self):
        self.create(); changed=self.settings.replace(b'runInBackground: 0',b'runInBackground: 1').replace(b'  scriptingDefineSymbols: {}',b'  scriptingDefineSymbols:\n    Standalone: UNITY_INCLUDE_TESTS')
        (self.copy/n.SETTINGS).write_bytes(changed)
        report=self.inspect(0); self.assertEqual(report['settingsStatus'],'COMPLETE_DIFF')
        self.assertEqual(n.apply_settings_diff(self.settings,report['settingsDiff']),changed)
        self.assertIn('+  runInBackground: 1', report['settingsDiff'])
        self.assertEqual(n.cleanup_copy(self.env),0)
        self.assertEqual((self.project/n.SETTINGS).read_bytes(),self.settings)
    def test_non_settings_edit_added_file_deleted_file_and_empty_directory_reject(self):
        for kind in ('edit','add','delete','directory'):
            with self.subTest(kind=kind):
                self.create()
                if kind=='edit': (self.copy/'Assets/font.otf').write_bytes(b'modified')
                elif kind=='add': (self.copy/'Assets/private-name-TOKEN.txt').write_bytes(b'PRIVATE_TOKEN')
                elif kind=='delete': (self.copy/'Assets/font.otf').unlink()
                else: (self.copy/'Assets/AddedEmpty').mkdir()
                report=self.inspect(2); self.assertFalse(report['otherSourceUnchanged']); self.assertEqual(report['changedPathCount'],1)
                self.assertNotIn('private-name',self.report.read_text()); self.assertNotIn('PRIVATE_TOKEN',self.report.read_text())
                n.cleanup_copy(self.env); self.owner.unlink(); self.report.unlink()
    def test_sensitive_unknown_string_added_credential_and_oversize_settings_fail_without_raw(self):
        for extra in (b'  secretSetting: PRIVATE_TOKEN\n',b'  productName: PRIVATE_TOKEN\n',b'  password: PRIVATE_TOKEN\n',b'  harmless: ghp_PRIVATE_TOKEN\n',b'  harmless: '+b'x'*65536+b'\n'):
            with self.subTest(length=len(extra)):
                self.create(); base=b'\n'.join(line for line in self.settings.split(b'\n') if not line.startswith(extra.split(b':')[0]+b':'))
                (self.copy/n.SETTINGS).write_bytes(base+extra)
                report=self.inspect(2); self.assertNotEqual(report['settingsStatus'],'COMPLETE_DIFF')
                self.assertNotIn('PRIVATE_TOKEN',self.report.read_text()); self.assertEqual(report['settingsDiff'],'')
                n.cleanup_copy(self.env); self.owner.unlink(); self.report.unlink()
    def test_symlink_or_hardlink_initial_source_is_rejected_before_copy_creation(self):
        path=self.project/'Assets/font.otf'; raw=path.read_bytes(); path.unlink()
        other=self.root/'outside'; other.write_bytes(raw)
        path.symlink_to(other)
        with self.assertRaises(ValueError): n.create_copy(self.env)
        self.assertFalse(self.copy.exists()); path.unlink(); os.link(other,path)
        with self.assertRaises(ValueError): n.create_copy(self.env)
        self.assertFalse(self.copy.exists())
    def test_existing_copy_symlink_parent_and_wrong_fixed_path_reject(self):
        self.copy.symlink_to(self.project, target_is_directory=True)
        with self.assertRaises(ValueError): n.create_copy(self.env)
        self.copy.unlink()
        with mock.patch.object(n,'COPY',self.project),self.assertRaisesRegex(ValueError,'COPY_PATH'): n.create_copy(self.env)
        self.copy.mkdir()
        with self.assertRaisesRegex(ValueError,'COPY_EXISTS'): n.create_copy(self.env)
    def test_swapped_root_inode_wrong_owner_identity_and_marker_prevent_cleanup(self):
        self.create(); self.inspect(0)
        original=self.copy.with_name('retained-original'); self.copy.rename(original); self.copy.mkdir()
        with self.assertRaises(ValueError): n.cleanup_copy(self.env)
        self.copy.rmdir(); original.rename(self.copy)
        with self.assertRaisesRegex(ValueError,'OWNER_IDENTITY'): n.cleanup_copy(dict(self.env,GITHUB_RUN_ID='9877'))
        marker=self.copy/n.COPY_MARKER; marker.write_text('{}')
        with self.assertRaisesRegex(ValueError,'OWNER_MARKER'): n.cleanup_copy(self.env)
        self.assertTrue(self.copy.exists()); self.assertEqual(n.protected_inventory(self.project),(self.rows,self.dirs))
    def test_native_symlink_or_hardlink_rejected_and_cleanup_never_follows_operational_link(self):
        self.create(); target=self.copy/'Assets/font.otf'; target.unlink(); target.symlink_to(self.project/'Assets/font.otf')
        self.inspect(2); n.cleanup_copy(self.env); self.owner.unlink(); self.report.unlink()
        self.create(); target=self.copy/'Assets/font.otf'; target.unlink(); os.link(self.project/'Assets/font.otf',target)
        self.inspect(2); n.cleanup_copy(self.env); self.owner.unlink(); self.report.unlink()
        self.create(); self.inspect(0); (self.copy/'Library').symlink_to(self.project,target_is_directory=True)
        n.cleanup_copy(self.env); self.assertEqual(n.protected_inventory(self.project),(self.rows,self.dirs))
    def test_copy_interrupted_does_not_become_ready_and_can_record_and_cleanup(self):
        original=n.file_bytes; count=0
        def interrupt(path,limit=128*1024**2):
            nonlocal count
            if path.is_relative_to(self.copy) and path.name!=n.COPY_MARKER:
                count+=1
                if count==1: raise OSError('PRIVATE_TOKEN')
            return original(path,limit)
        with mock.patch.object(n,'file_bytes',side_effect=interrupt),self.assertRaises(OSError): n.create_copy(self.env)
        self.assertNotIn('copy_ready',Path(self.env['GITHUB_OUTPUT']).read_text())
        self.inspect(2); n.cleanup_copy(self.env)
        self.assertEqual(n.protected_inventory(self.project),(self.rows,self.dirs))
    def test_cleanup_requires_saved_valid_report_and_does_not_overwrite_first_failure(self):
        self.create()
        with self.assertRaises(FileNotFoundError): n.cleanup_copy(self.env)
        (self.copy/'Assets/font.otf').write_bytes(b'bad'); self.inspect(2); before=self.report.read_bytes()
        with mock.patch.object(n.shutil,'rmtree',side_effect=PermissionError('PRIVATE_TOKEN')),self.assertRaises(PermissionError): n.cleanup_copy(self.env)
        self.assertEqual(self.report.read_bytes(),before); self.assertTrue(self.copy.exists())
    def test_diff_validator_rejects_injected_credentials_incorrect_hashes_and_counts(self):
        self.create(); (self.copy/n.SETTINGS).write_bytes(self.settings.replace(b'runInBackground: 0',b'runInBackground: 1'))
        value=self.inspect(0)
        for changed in (dict(settingsDiff=value['settingsDiff'].replace('+  runInBackground: 1','+  password: PRIVATE_TOKEN')),
                        dict(changedPathCount=1),dict(settingsAfter=dict(sha256='f'*64,bytes=1)),dict(settingsStatus='UNCHANGED'),
                        dict(projectPath='tasks/desert-rv/unity'),dict(copyVerified=False),dict(protectedFiles=True)):
            self.assertFalse(n.validate_isolation(dict(value,**changed)))
    def test_actual_isolated_cleanup_cli_ignores_shadow_stdlib_and_local_native_modules(self):
        import sys
        self.create(); self.inspect(0)
        scripts=self.task/'scripts'; scripts.mkdir()
        helper=scripts/'journey_keyboard_look_native.py'; helper.write_bytes(Path(n.__file__).read_bytes())
        marker=self.root/'shadow-import-ran'
        for name in ('json.py','shutil.py','journey_tracer_native.py','yaml.py'):
            (scripts/name).write_text("from pathlib import Path\nPath("+repr(str(marker))+").write_text('BAD')\nraise RuntimeError('shadow')\n")
        result=subprocess.run([sys.executable,'-I','-B',str(helper),'cleanup'],env=dict(self.env),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertFalse(marker.exists()); self.assertFalse(self.copy.exists())
        self.assertEqual(n.protected_inventory(self.project),(self.rows,self.dirs))
    def test_actual_public_settings_baseline_and_nested_changes_round_trip(self):
        real=Path(n.__file__).resolve().parents[3]/'tasks/desert-rv/unity'/n.SETTINGS
        before=real.read_bytes(); self.assertEqual(len(before),22342)
        self.assertEqual(n.settings_diff(before,before),'')
        for after in (before.replace(b'runInBackground: 0',b'runInBackground: 1'),
                      before.replace(b'b: 0.1254902',b'b: 0.14',1),
                      before.replace(b'productName: Desert RV - Technical Preflight',b'productName: Desert RV - Technical Preflight PlayMode')):
            with self.subTest(bytes=len(after)):
                diff=n.settings_diff(before,after); self.assertTrue(diff)
                self.assertEqual(n.apply_settings_diff(before,diff),after)
        duplicate=self.settings+b'  nested:\n    value: hidden\n    value: safe\n'
        with self.assertRaises(n.SettingsRejected) as caught: n.settings_diff(self.settings,duplicate)
        self.assertEqual(caught.exception.reason,'YAML_DUPLICATE')
    def test_normal_public_yaml_strings_guids_enums_and_numeric_structures_are_preserved(self):
        changed=self.settings.replace(b'  runInBackground: 0', b'  runInBackground: 1')+b'  graphicsApi: Vulkan\n  newGuid: abcdef0123456789abcdef0123456789\n  newColor: {r: 0.1, g: 0.2, b: 0.3, a: 1}\n  identifier: com.example.unity.tests\n'
        diff=n.settings_diff(self.settings,changed)
        self.assertEqual(n.apply_settings_diff(self.settings,diff),changed)
        for payload, reason in [(b'  localFolder: /home/runner/private\n','ABSOLUTE_PATH'),(b'  apiToken: value\n','SENSITIVE_FIELD'),(b'  normal: ghp_PRIVATE_TOKEN\n','SENSITIVE_VALUE')]:
            with self.subTest(reason=reason), self.assertRaises(n.SettingsRejected) as caught: n.settings_diff(self.settings,self.settings+payload)
            self.assertEqual(caught.exception.reason,reason)
    def test_actual_after_hash_reconstruction_replays_full_isolation_diff_and_validator(self):
        # Actual runner after SHA/size; bytes reconstructed solely by adding one
        # trailing space to the nine public single-line empty fields. No raw log.
        real=Path(n.__file__).resolve().parents[3]/'tasks/desert-rv/unity'/n.SETTINGS
        before=real.read_bytes(); self.assertEqual(hashlib.sha256(before).hexdigest(),'4508539ef0d76b843206ef4d05d4f0700c6eb0dc2d6a36d14174fc9072411577')
        lines=before.splitlines(keepends=True)
        starts=[i for i,line in enumerate(lines) if re.match(rb'^  [A-Za-z0-9_][A-Za-z0-9_ ]*:',line)]
        indices=[i for j,i in enumerate(starts) if (starts[j+1] if j+1<len(starts) else len(lines))==i+1 and re.fullmatch(rb'  [A-Za-z0-9_][A-Za-z0-9_ ]*:\n',lines[i])]
        self.assertEqual(len(indices),9)
        after=b''.join(line[:-1]+b' \n' if i in indices else line for i,line in enumerate(lines))
        self.assertEqual(len(after),22351); self.assertEqual(hashlib.sha256(after).hexdigest(),'5dfc460eab7c3d48818bad6069e9458130ae742a152b41d98a3b61943d2446f0')
        (self.project/n.SETTINGS).write_bytes(before); self.rows.clear(); self.rows.update(n.protected_inventory(self.project)[0])
        self.create(); (self.copy/n.SETTINGS).write_bytes(after)
        value=self.inspect(0); self.assertEqual(value['settingsStatus'],'COMPLETE_DIFF');self.assertEqual(value['settingsRejectedFields'],[])
        self.assertEqual(value['allowedEmptySensitiveFields'],[dict(field=field,beforeValueKind='EMPTY_NULL',afterValueKind='EMPTY_NULL') for field in ('AndroidKeystoreName','metroCertificatePassword','ps4NPTitleSecret')])
        changed=copy.deepcopy(value);changed['allowedEmptySensitiveFields']=[];self.assertFalse(n.validate_isolation(changed))
        changed=copy.deepcopy(value);changed['allowedEmptySensitiveFields'][0]['afterValueKind']='EMPTY_STRING';self.assertFalse(n.validate_isolation(changed))
        self.assertEqual(n.apply_settings_diff(before,value['settingsDiff']),after)
        self.assertEqual(n.cleanup_copy(self.env),0); self.assertEqual((self.project/n.SETTINGS).read_bytes(),before)
    def test_sensitive_field_only_existing_explicit_single_line_empty_literals_are_allowed(self):
        original=b'  secretSetting: \n'
        for literal in (b'',b' ',b'null',b'Null',b'NULL',b'~',b"''",b'""'):
            after=self.settings.replace(original,b'  secretSetting: '+literal+b'\n')
            with self.subTest(literal=literal):
                diff=n.settings_diff(self.settings,after)
                if diff:self.assertEqual(n.apply_settings_diff(self.settings,diff),after)
        variants=[(self.settings,self.settings.replace(original,b'  secretSetting: PRIVATE_TOKEN\n'),'EMPTY_NULL','NONEMPTY_OR_UNSAFE'),
                  (self.settings,self.settings.replace(original,b'  secretSetting: # hidden\n'),'EMPTY_NULL','NONEMPTY_OR_UNSAFE'),
                  (self.settings,self.settings.replace(original,b'  secretSetting: " "\n'),'EMPTY_NULL','NONEMPTY_OR_UNSAFE'),
                  (self.settings,self.settings.replace(original,b'  secretSetting: |\n    \n'),'EMPTY_NULL','NONEMPTY_OR_UNSAFE'),
                  (self.settings,self.settings+b'  newPassword: \n','ABSENT','EMPTY_NULL'),
                  (self.settings,self.settings.replace(original,b''),'EMPTY_NULL','ABSENT'),
                  (self.settings.replace(original,b'  secretSetting: PRIVATE_TOKEN\n'),self.settings,'NONEMPTY_OR_UNSAFE','EMPTY_NULL')]
        for before,after,old_kind,new_kind in variants:
            with self.subTest(beforeKind=old_kind,afterKind=new_kind),self.assertRaises(n.SettingsRejected) as caught:n.settings_diff(before,after)
            self.assertEqual(caught.exception.reason,'SENSITIVE_FIELD');self.assertEqual(caught.exception.before_kind,old_kind);self.assertEqual(caught.exception.after_kind,new_kind)
        self.create(); (self.copy/n.SETTINGS).write_bytes(self.settings.replace(original,b'  secretSetting: PRIVATE_TOKEN\n'))
        report=self.inspect(2)
        self.assertEqual(report['settingsRejectedFields'],[dict(field='secretSetting',reason='SENSITIVE_FIELD',beforeValueKind='EMPTY_NULL',afterValueKind='NONEMPTY_OR_UNSAFE')])
        self.assertNotIn('PRIVATE_TOKEN',self.report.read_text());self.assertEqual(report['settingsDiff'],'')
        rejected=copy.deepcopy(report);rejected['settingsRejectedFields'][0]['afterValueKind']='PRIVATE_TOKEN';self.assertFalse(n.validate_isolation(rejected))
    def test_workflow_preserves_diagnostics_before_fixed_cleanup_and_expensive_stages(self):
        import yaml
        real=Path(__file__).resolve().parents[3]
        steps=yaml.load((real/'.github/workflows/desert-rv-tracer-shader-prepare.yml').read_text(),Loader=yaml.BaseLoader)['jobs']['prepare']['steps']
        order=[step.get('id') for step in steps]
        for before,after in [('keyboard_copy','keyboard_native'),('keyboard_native','cabin_native'),('cabin_native','keyboard_isolation'),('keyboard_isolation','keyboard_verify'),('keyboard_verify','cabin_report'),('cabin_report','keyboard_cleanup')]:
            self.assertLess(order.index(before),order.index(after))
        cleanup=next(step for step in steps if step.get('id')=='keyboard_cleanup')
        self.assertIn('sudo --preserve-env=GITHUB_SHA,GITHUB_RUN_ID,GITHUB_RUN_ATTEMPT /usr/bin/python3 -I -B tasks/desert-rv/scripts/journey_keyboard_look_native.py cleanup',cleanup['run'])
        self.assertNotIn('rm -rf',cleanup['run']); self.assertNotIn('chmod',cleanup['run']); self.assertNotIn('chown',cleanup['run'])
        self.assertLess(order.index('keyboard_cleanup'),order.index('stage_armored'))
        self.assertLess(order.index('stage_armored'),order.index('linux_native'))
        stage=next(step for step in steps if step.get('id')=='stage_armored')
        for gate in ("steps.keyboard_source.outputs.source_unchanged == 'true'",
                     "steps.keyboard_verify.outputs.native_verified == 'true'",
                     "steps.keyboard_isolation.outputs.copy_verified == 'true'",
                     "steps.keyboard_cleanup.outcome == 'success'"):
            self.assertIn(gate,stage['if'])



if __name__ == '__main__':
    unittest.main()
