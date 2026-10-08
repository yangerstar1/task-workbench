#!/usr/bin/env python3
"""Pure Python scope contract checks; never Unity execution evidence."""
import itertools
from pathlib import Path
import unittest
from verification_scope import report


class ScopeContracts(unittest.TestCase):
    def test_all_job_state_combinations(self):
        states = ('success', 'failure', 'cancelled', 'skipped')
        for mode in ('checks-only', 'traversal-apk', 'unknown', ''):
            for editmode, playmode, android in itertools.product(states, repeat=3):
                with self.subTest(mode=mode, states=(editmode, playmode, android)):
                    ok, text = report(mode, editmode, playmode, android)
                    expected = editmode == playmode == 'success' and (
                        (mode == 'checks-only' and android == 'skipped') or
                        (mode == 'traversal-apk' and android == 'success'))
                    self.assertEqual(ok, expected)
                    if mode == 'checks-only':
                        self.assertIn('Android APK: NOT_RUN', text)

    def test_workflow_contract(self):
        root = Path(__file__).resolve().parents[3]
        text = (root / '.github/workflows/desert-rv-android.yml').read_text()
        self.assertIn('default: traversal-apk', text)
        self.assertIn("(inputs.mode == 'traversal-apk' || inputs.mode == '')", text)
        self.assertIn('cancel-in-progress: false', text)
        tests = text.split('\n  tests:\n', 1)[1].split('\n  android:\n', 1)[0]
        self.assertNotIn('inputs.mode', tests)
        self.assertIn('testMode: editmode', tests)
        self.assertIn('testMode: playmode', tests)
        self.assertIn('verify_evidence.py tests', tests)
        self.assertIn('verify_evidence.py playmode', tests)
        self.assertIn('verify_evidence.py apk', text)
        self.assertNotIn('actions/cache', text)  # cost guard: proposal is not enabled
        self.assertNotIn('continue-on-error', text)


if __name__ == '__main__':
    unittest.main()
