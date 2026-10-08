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
