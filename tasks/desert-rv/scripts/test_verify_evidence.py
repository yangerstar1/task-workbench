#!/usr/bin/env python3
"""Local verifier tests; these are NOT Unity gameplay-test evidence."""
import importlib.util
import json
import hashlib
import zipfile
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('evidence', Path(__file__).with_name('verify_evidence.py'))
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


class TestNativeTestGate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.input = self.root / 'input'
        self.input.mkdir()
        self.patches = [patch.object(evidence, 'TASK', self.root),
                        patch.object(evidence, 'identity', return_value={'commit': 'a' * 40}),
                        patch.object(evidence, 'expected_cases', return_value={'Rules.A', 'Rules.B'})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp.cleanup()

    def write(self, body=None, **attrs):
        values = dict(result='Passed', total='2', passed='2', failed='0')
        values.update(attrs)
        if body is None:
            body = '<test-case fullname="Rules.A" result="Passed"/><test-case fullname="Rules.B" result="Passed"/>'
        text = '<test-run ' + ' '.join(k + '="' + str(v) + '"' for k, v in values.items()) + '>' + body + '</test-run>'
        (self.input / 'results.xml').write_text(text)

    def test_pass_and_strip_sensitive_output(self):
        self.write('<test-case fullname="Rules.A" result="Passed"><output>SECRET_SENTINEL</output></test-case><test-case fullname="Rules.B" result="Passed"/>')
        result = evidence.inspect_tests(self.input)
        self.assertEqual(result['passed'], 2)
        self.assertEqual(result['verdict'], 'PASSED')
        self.assertNotIn('SECRET_SENTINEL', (self.root / 'evidence/tests/test-results.json').read_text())

    def test_missing_report(self):
        with self.assertRaises(ValueError):
            evidence.inspect_tests(self.input)

    def test_empty_run(self):
        self.write('', total=0, passed=0)
        with self.assertRaises(ValueError):
            evidence.inspect_tests(self.input)

    def test_skipped(self):
        self.write('<test-case fullname="Rules.A" result="Passed"/><test-case fullname="Rules.B" result="Skipped"/>')
        with self.assertRaises(ValueError):
            evidence.inspect_tests(self.input)
        data = json.loads((self.root / 'evidence/tests/test-results.json').read_text())
        self.assertEqual(data['verdict'], 'COLLECTED_NOT_YET_VERIFIED')

    def test_duplicate_case(self):
        self.write('<test-case fullname="Rules.A" result="Passed"/><test-case fullname="Rules.A" result="Passed"/>')
        with self.assertRaises(ValueError):
            evidence.inspect_tests(self.input)

    def test_foreign_case(self):
        self.write('<test-case fullname="Rules.A" result="Passed"/><test-case fullname="Foreign.B" result="Passed"/>')
        with self.assertRaises(ValueError):
            evidence.inspect_tests(self.input)

    def test_false_root_success(self):
        self.write(result='Failed')
        with self.assertRaises(ValueError):
            evidence.inspect_tests(self.input)

    def test_wrong_count(self):
        self.write(passed=0)
        with self.assertRaises(ValueError):
            evidence.inspect_tests(self.input)

    def test_root_skipped_count_fails(self):
        self.write(skipped=1)
        with self.assertRaises(ValueError): evidence.inspect_tests(self.input)

    def test_root_inconclusive_count_fails(self):
        self.write(inconclusive=1)
        with self.assertRaises(ValueError): evidence.inspect_tests(self.input)

    def test_multiple_reports(self):
        self.write()
        (self.input / 'second.xml').write_bytes((self.input / 'results.xml').read_bytes())
        with self.assertRaises(ValueError):
            evidence.inspect_tests(self.input)

    def test_symlink_report(self):
        self.write()
        (self.input / 'link.xml').symlink_to(self.input / 'results.xml')
        with self.assertRaises(ValueError):
            evidence.inspect_tests(self.input)


    def test_unknown_case_result_fails(self):
        self.write('<test-case fullname="Rules.A" result="Passed"/><test-case fullname="Rules.B" result="Unknown"/>')
        with self.assertRaises(ValueError): evidence.inspect_tests(self.input)

    def test_playmode_has_separate_evidence(self):
        self.write()
        result = evidence.inspect_tests(self.input, 'playmode')
        self.assertEqual(result['testMode'], 'playmode')
        self.assertTrue((self.root / 'evidence/playmode/test-results.json').is_file())
        self.assertFalse((self.root / 'evidence/tests/test-results.json').exists())



class TestCurrentSourceInventory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.task = self.root / 'tasks/desert-rv'
        for directory in evidence.SOURCE_ROOTS:
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        self.files = list(evidence.SOURCE_FILES) + [
            'tasks/desert-rv/unity/Assets/Game.cs',
            'tasks/desert-rv/unity/Assets/Game.cs.meta',
            'tasks/desert-rv/unity/Packages/manifest.json',
            'tasks/desert-rv/unity/ProjectSettings/ProjectSettings.asset',
            'tasks/desert-rv/backup-assets/font.xz',
            'tasks/desert-rv/scripts/backup/restore.py']
        for name in self.files:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('reviewed source')
        (self.task / 'PUBLIC-EXPORT.json').write_text('{}')
        self.baseline_hash = evidence.sha(self.task / 'PUBLIC-EXPORT.json')
        self.patches = [patch.object(evidence, 'ROOT', self.root),
                        patch.object(evidence, 'TASK', self.task),
                        patch.object(evidence, 'BASELINE_EXPORT_SHA', self.baseline_hash)]
        for p in self.patches: p.start()
        self.state = dict(schema='desert-rv-source-state/v1',
            baselineGameCommit=evidence.BASELINE_COMMIT,
            baselineExportManifestSha256=self.baseline_hash,
            coverageRoots=list(evidence.SOURCE_ROOTS), coverageFiles=list(evidence.SOURCE_FILES),
            restoredFiles=[dict(path=evidence.FONT_PATH, sha256=evidence.FONT_SHA, size=16437340)],
            files=[dict(path=name, sha256=evidence.sha(self.root / name),
                        size=(self.root / name).stat().st_size) for name in self.files])
        self.save()

    def tearDown(self):
        for p in self.patches: p.stop()
        self.temp.cleanup()

    def save(self):
        (self.task / 'SOURCE-STATE.json').write_text(json.dumps(self.state))

    def rejected(self):
        with self.assertRaises(ValueError): evidence.verify_source_state()

    def test_current_source_passes_without_rewriting_historical_manifest(self):
        self.assertEqual(evidence.verify_source_state(), self.state)

    def test_changed_source_fails(self):
        (self.root / self.files[2]).write_text('new source')
        self.rejected()

    def test_missing_source_fails(self):
        (self.root / self.files[2]).unlink()
        self.rejected()

    def test_unlisted_unity_source_fails(self):
        (self.task / 'unity/Assets/Injected.cs').write_text('new source')
        self.rejected()

    def test_unlisted_unity_root_response_file_fails(self):
        (self.task / 'unity/csc.rsp').write_text('compiler input')
        self.rejected()

    def test_unlisted_package_fails(self):
        (self.task / 'unity/Packages/local.cs').write_text('package source')
        self.rejected()

    def test_missing_recovery_inventory_fails(self):
        self.state['files'].pop()
        self.save(); self.rejected()

    def test_changed_historical_manifest_fails(self):
        (self.task / 'PUBLIC-EXPORT.json').write_text('{"changed":true}')
        self.rejected()

    def test_rebinding_baseline_hash_is_not_allowed(self):
        (self.task / 'PUBLIC-EXPORT.json').write_text('{"changed":true}')
        self.state['baselineExportManifestSha256'] = evidence.sha(self.task / 'PUBLIC-EXPORT.json')
        self.save(); self.rejected()

    def test_wrong_baseline_commit_fails(self):
        self.state['baselineGameCommit'] = 'a' * 40
        self.save(); self.rejected()

    def test_weakened_coverage_fails(self):
        self.state['coverageRoots'] = []
        self.save(); self.rejected()

    def test_duplicate_entry_fails(self):
        self.state['files'].append(self.state['files'][0])
        self.save(); self.rejected()

    def test_path_escape_fails(self):
        self.state['files'][0]['path'] = '../outside'
        self.save(); self.rejected()

    def test_symlink_source_fails(self):
        (self.task / 'unity/Assets/linked.cs').symlink_to(self.root / self.files[2])
        self.rejected()

    def test_arbitrary_restored_font_fails(self):
        font = self.root / evidence.FONT_PATH
        font.parent.mkdir(parents=True, exist_ok=True)
        font.write_text('wrong font')
        self.rejected()

    def test_python_bytecode_is_not_source(self):
        cache = self.task / 'scripts/__pycache__/verify_evidence.pyc'
        cache.parent.mkdir(); cache.write_bytes(b'cache')
        evidence.verify_source_state()

    def test_art_candidate_outside_unity_does_not_enter_compile_inventory(self):
        art = self.task / 'art/candidates/script.py'
        art.parent.mkdir(parents=True); art.write_text('offline art authoring')
        evidence.verify_source_state()


class TestPresentationBuiltinModules(unittest.TestCase):
    def test_presenter_native_modules_are_declared_and_builtin(self):
        packages = evidence.TASK / 'unity/Packages'
        manifest = json.loads((packages / 'manifest.json').read_text())['dependencies']
        locked = json.loads((packages / 'packages-lock.json').read_text())['dependencies']
        # CoreModule supplies transforms/renderers; these optional modules supply the added native APIs.
        for suffix in ('animation', 'audio', 'physics', 'particlesystem'):
            name = 'com.unity.modules.' + suffix
            self.assertEqual(manifest.get(name), '1.0.0', name)
            self.assertEqual(locked[name]['version'], '1.0.0', name)
            self.assertEqual(locked[name]['source'], 'builtin', name)
            self.assertEqual(locked[name]['depth'], 0, name)
            self.assertNotIn('url', locked[name], name)


class TestResolvedEditorPackages(unittest.TestCase):
    def test_pinned_editor_core_and_platform_dependencies(self):
        manifest=evidence.read_json(evidence.PROJECT/'Packages/manifest.json')['dependencies']
        locked=evidence.read_json(evidence.PROJECT/'Packages/packages-lock.json')['dependencies']
        self.assertEqual(manifest['com.unity.test-framework'],'1.6.0')
        for name,version in [('com.unity.test-framework','1.6.0'),('com.unity.ext.nunit','2.0.5')]:
            self.assertEqual(locked[name]['version'],version)
            self.assertEqual(locked[name]['source'],'builtin')
            self.assertNotIn('url',locked[name])
        for name in ['com.unity.sdk.linux-arm64','com.unity.sdk.linux-x86_64','com.unity.toolchain.linux-x86_64-linux']:
            self.assertEqual(manifest[name],'1.1.0')
            self.assertEqual(locked[name]['version'],'1.1.0')
            self.assertEqual(locked[name]['depth'],0)
            self.assertEqual(locked[name]['url'],'https://packages.unity.com')
        self.assertEqual(locked['com.unity.sysroot.base']['version'],'1.1.0')


class TestDiagnosticCaptureModules(unittest.TestCase):
    def test_official_capture_modules_are_explicit_builtins(self):
        manifest=json.loads((evidence.PROJECT/'Packages/manifest.json').read_text())['dependencies']
        locked=json.loads((evidence.PROJECT/'Packages/packages-lock.json').read_text())['dependencies']
        for name in ('com.unity.modules.imageconversion','com.unity.modules.screencapture'):
            self.assertEqual(manifest[name],'1.0.0')
            self.assertEqual(locked[name]['source'],'builtin')
            self.assertEqual(locked[name]['depth'],0)
        self.assertEqual(locked['com.unity.modules.screencapture']['dependencies'],{'com.unity.modules.imageconversion':'1.0.0'})


class TestSeparateModeInventories(unittest.TestCase):
    def test_separate_reviewed_inventories(self):
        edits = evidence.expected_cases('editmode')
        plays = evidence.expected_cases('playmode')
        self.assertEqual(len(edits), 210)
        self.assertEqual(len(plays), 13)
        self.assertFalse(edits & plays)

    def test_unknown_mode_fails(self):
        with self.assertRaises(ValueError): evidence.expected_cases('combined')



class TestUpstreamRunBinding(unittest.TestCase):
    def setUp(self):
        self.base = dict(commit='a' * 40, runId='12', runAttempt='2', sourceStateSha256='b' * 64)
        self.env = {}
        for mode in ('EDITMODE', 'PLAYMODE'):
            for suffix, key in [('COMMIT', 'commit'), ('RUN_ID', 'runId'),
                                ('RUN_ATTEMPT', 'runAttempt'), ('SOURCE_STATE_SHA256', 'sourceStateSha256')]:
                self.env['EXPECTED_' + mode + '_' + suffix] = self.base[key]

    def test_same_run_attempt_and_source_pass(self):
        with patch.dict(evidence.os.environ, self.env, clear=True):
            evidence.verify_upstream_identity(self.base)

    def test_each_identity_field_missing_or_stale_fails(self):
        for key in self.env:
            for value in ('', 'stale'):
                with self.subTest(key=key, value=value):
                    changed = dict(self.env); changed[key] = value
                    with patch.dict(evidence.os.environ, changed, clear=True):
                        with self.assertRaises(ValueError): evidence.verify_upstream_identity(self.base)

    def test_partial_rerun_cannot_reuse_old_attempt(self):
        self.env['EXPECTED_EDITMODE_RUN_ATTEMPT'] = '1'
        with patch.dict(evidence.os.environ, self.env, clear=True):
            with self.assertRaises(ValueError): evidence.verify_upstream_identity(self.base)



class TestApkAndReceipt(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.apk = self.root / 'test.apk'
        self.base = dict(commit='a' * 40, runId='12', runAttempt='1')
        self.hash = 'a6a530f3e7e7a2c299470c42efff2e109fcc0a5be92686b96d5e84a05f3ecb2b'
        self.result = dict(apkSha256='b' * 64, apkBytes=2000000)
        self.receipt = dict(schemaVersion=1, status='succeeded', stage='complete', scope='traversal-test-only-no-combat-not-complete-game', project='desert-rv/unity', scene='Assets/DesertRV/Scenes/TraversalHarness.unity', unityVersion=evidence.VERSION, version='0.1.0-dev.' + 'a' * 12, **self.base, buildIdentitySha256=hashlib.sha256(('a' * 40 + ':12:1').encode()).hexdigest(), target='Android', architecture='ARM64', backend='IL2CPP', development=True, signing='debug-only', apk='DesertRV.apk', sceneSha256=self.hash, referenceSceneSha256=self.hash, fontSha256=self.hash, **self.result)

    def tearDown(self):
        self.temp.cleanup()

    def verify(self):
        with patch.object(evidence, 'sha', return_value=self.hash):
            return evidence.inspect_receipt(self.receipt, self.base, self.result)

    def zip(self, omit=None, extra=None):
        names = ['AndroidManifest.xml', 'classes.dex', 'lib/arm64-v8a/libil2cpp.so', 'lib/arm64-v8a/libunity.so']
        with zipfile.ZipFile(self.apk, 'w') as z:
            for name in names:
                if name != omit:
                    z.writestr(name, b'placeholder')
            z.writestr('assets/inert-test-padding', b'x' * (1024**2))
            if extra:
                z.writestr(extra, b'placeholder')

    def test_exact_receipt(self):
        self.assertEqual(self.verify(), self.receipt)

    def test_old_commit_rejected(self):
        self.receipt['commit'] = 'c' * 40
        with self.assertRaises(ValueError): self.verify()

    def test_old_attempt_rejected(self):
        self.receipt['runAttempt'] = '2'
        with self.assertRaises(ValueError): self.verify()

    def test_secret_field_rejected(self):
        self.receipt['license'] = 'SENTINEL'
        with self.assertRaises(ValueError): self.verify()

    def test_wrong_apk_hash_rejected(self):
        self.receipt['apkSha256'] = 'c' * 64
        with self.assertRaises(ValueError): self.verify()

    def test_failed_receipt_rejected(self):
        self.receipt['status'] = 'failed'
        with self.assertRaises(ValueError): self.verify()

    def test_integer_is_not_boolean(self):
        self.receipt['development'] = 1
        with self.assertRaises(ValueError): self.verify()

    def test_valid_synthetic_zip_structure(self):
        self.zip()
        self.assertGreater(evidence.inspect_apk_bytes(self.apk)['apkBytes'], 1024**2)

    def test_missing_native_library(self):
        self.zip(omit='lib/arm64-v8a/libil2cpp.so')
        with self.assertRaises(ValueError): evidence.inspect_apk_bytes(self.apk)

    def test_foreign_architecture(self):
        self.zip(extra='lib/x86/libunity.so')
        with self.assertRaises(ValueError): evidence.inspect_apk_bytes(self.apk)

    def test_unsafe_zip_member(self):
        self.zip(extra='../escape')
        with self.assertRaises(ValueError): evidence.inspect_apk_bytes(self.apk)


if __name__ == '__main__':
    unittest.main()
