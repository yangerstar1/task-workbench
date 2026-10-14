#!/usr/bin/env python3
"""Current safe-writer/Stage-A contracts. Synthetic only; never Docker/Unity."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import safe_project_ci as safe
import stage_a_inventory_ci as adapter


ROOT = Path(__file__).resolve().parents[3]
IDENT = dict(scope=safe.visual.SCOPE, sourceCommit='1'*40,
             reviewedCandidateCommit='2'*40, runId='123', runAttempt='1',
             requestId='lottery-visual-20261013-99', g3Gate='NOT_EVALUATED',
             deviceQa='NOT_RUN', sourceReview=dict(sourceCommit='2'*40,
             status='APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY',
             reviewer='independent-source-review', reviewId='visual-source-20261013-99',
             reviewedAtUtc='2026-10-13T01:00:00Z'))
CAPTURE_FIELDS = ('counterLightDiagnostic', 'counterLightDiagnosticFault',
                  'nativeStartedAtNs', 'processBudgetSeconds')


def receipts(code=0, enabled=False):
    with patch.object(safe, 'COUNTER_LIGHT_DIAGNOSTIC', enabled), \
         patch.object(safe, 'COUNTER_LIGHT_DIAGNOSTIC_FAULT', ''):
        capture = safe.process_receipt(IDENT, 'capture')
    capture.update(status='NATIVE_SUCCEEDED' if code == 0 else 'NATIVE_FAILED',
                   nativeExitCode=code, dockerExitCode=code, nativeExitMarkerCount=1,
                   nativeStartedAtNs=1791856550000000000, processBudgetSeconds=1800,
                   elapsedMs=250000, recordedAtUtc='2026-10-13T02:00:00Z')
    cleanup = dict(status='ABSENCE_VERIFIED', removalExitCode=0)
    finish = safe.process_receipt(IDENT, 'finish')
    finish.update(status='NATIVE_SUCCEEDED', returnStatus='NATIVE_SUCCEEDED',
                  nativeExitCode=0, dockerExitCode=0, nativeExitMarkerCount=1,
                  cleanup=copy.deepcopy(cleanup), elapsedMs=200,
                  recordedAtUtc='2026-10-13T02:00:01Z')
    session = dict(IDENT, status='CLOSED', activationSucceeded=True,
                   stagesStarted=['capture'], cleanup=copy.deepcopy(cleanup))
    return [capture, finish, session]


class CombinedReceiptTests(unittest.TestCase):
    def summary(self, values):
        return adapter.receipt_summary(*values, IDENT, safe.private)

    def test_current_safe_writer_to_summary_both_selectors_and_exit_137(self):
        for enabled in (False, True):
            for code in (0, 3, 137):
                with self.subTest(enabled=enabled, code=code), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    safe.private.write(safe.file(root, 'session'), dict(IDENT, status='READY',
                                       activationSucceeded=True, stagesStarted=[], cleanup=None))

                    def completed(_ident, _command, _seconds, record, _files=()):
                        exit_code = code if record['phase'] == 'capture' else 0
                        record.update(status='NATIVE_SUCCEEDED' if exit_code == 0 else 'NATIVE_FAILED',
                                      nativeExitCode=exit_code, dockerExitCode=exit_code, nativeExitMarkerCount=1)

                    with patch.object(safe, 'identity', return_value=IDENT), \
                         patch.object(safe, 'compiler_assets', return_value=frozenset()), \
                         patch.object(safe, 'COUNTER_LIGHT_DIAGNOSTIC', enabled), \
                         patch.object(safe, 'COUNTER_LIGHT_DIAGNOSTIC_FAULT', ''), \
                         patch.object(safe, 'native', side_effect=completed) as native, \
                         patch.object(safe.private, 'cleanup', return_value=dict(status='ABSENCE_VERIFIED', removalExitCode=0)):
                        self.assertEqual(safe.test(root, 'capture'), 0 if code == 0 else 1)
                        self.assertEqual(safe.finish(root), 0)
                        self.assertEqual(native.call_count, 2)
                    paths = [safe.file(root, phase) for phase in ('capture', 'finish', 'session')]
                    original = [path.read_bytes() for path in paths]
                    values = [json.loads(raw) for raw in original]
                    self.assertEqual(set(values[0]), set(receipts()[0]))
                    self.assertEqual(set(values[1]), set(receipts()[1]))
                    self.assertFalse(set(CAPTURE_FIELDS) & set(values[1]))
                    result = self.summary(values)
                    self.assertEqual(result['captureNativeExit'], code)
                    self.assertEqual(result['captureStatus'], 'NATIVE_SUCCEEDED' if code == 0 else 'NATIVE_FAILED')
                    self.assertEqual(result['regressionVerdicts'], 'ORIGINAL_UNCHANGED_SEPARATE_RECEIPTS')
                    self.assertEqual([path.read_bytes() for path in paths], original)

    def test_each_capture_field_and_all_legacy_fields_missing_rejected(self):
        for key in CAPTURE_FIELDS:
            values = receipts(); values[0].pop(key)
            with self.subTest(key=key), self.assertRaisesRegex(adapter.Blocked, 'NATIVE_RECEIPT_SCHEMA'):
                self.summary(values)
        values = receipts()
        for key in CAPTURE_FIELDS: values[0].pop(key)
        with self.assertRaisesRegex(adapter.Blocked, 'NATIVE_RECEIPT_SCHEMA'): self.summary(values)

    def test_opt_in_requires_exact_bool(self):
        for value in (None, 0, 1, 'true', 'false', [], {}):
            values = receipts(); values[0]['counterLightDiagnostic'] = value
            with self.subTest(value=value), self.assertRaisesRegex(adapter.Blocked, 'CAPTURE_DIAGNOSTIC_SELECTOR'):
                self.summary(values)

    def test_any_fault_or_wrong_fault_type_blocks_both_selector_states(self):
        for enabled in (False, True):
            for value in ('pendant-zero:before-capture', 'negative:camera-target', 'UNKNOWN', None, False, 0, [], {}):
                values = receipts(enabled=enabled); values[0]['counterLightDiagnosticFault'] = value
                with self.subTest(enabled=enabled, value=value), self.assertRaisesRegex(adapter.Blocked, 'CAPTURE_DIAGNOSTIC_SELECTOR'):
                    self.summary(values)

    def test_native_start_requires_positive_nonfuture_exact_int(self):
        for value in (None, False, True, 0, -1, 1791856550000000000.0, '1791856550000000000', [], {}, adapter.time.time_ns()+10**12):
            values = receipts(); values[0]['nativeStartedAtNs'] = value
            with self.subTest(value=value), self.assertRaisesRegex(adapter.Blocked, 'CAPTURE_NATIVE_START'):
                self.summary(values)

    def test_capture_budget_requires_original_exact_int(self):
        for value in (None, False, True, 0, 480, 1799, 1801, 1800.0, '1800', [], {}):
            values = receipts(); values[0]['processBudgetSeconds'] = value
            with self.subTest(value=value), self.assertRaisesRegex(adapter.Blocked, 'CAPTURE_NATIVE_BUDGET'):
                self.summary(values)

    def test_unknown_capture_and_return_fields_rejected(self):
        for index in (0, 1):
            for key, value in [('unknown', True), ('nativeStartedAt', '2026-10-13T02:00:00Z'), ('shard', 'core')]:
                values = receipts(); values[index][key] = value
                with self.subTest(index=index, key=key), self.assertRaisesRegex(adapter.Blocked, 'NATIVE_RECEIPT_SCHEMA'):
                    self.summary(values)

    def test_return_keeps_its_own_schema_without_capture_fields(self):
        self.summary(receipts())
        for key in CAPTURE_FIELDS:
            values = receipts(); values[1][key] = values[0][key]
            with self.subTest(key=key), self.assertRaisesRegex(adapter.Blocked, 'NATIVE_RECEIPT_SCHEMA'):
                self.summary(values)
        values = receipts(); values[1].pop('returnStatus')
        with self.assertRaisesRegex(adapter.Blocked, 'NATIVE_RECEIPT_SCHEMA'): self.summary(values)

    def test_original_native_oracle_and_session_blocking_relationships(self):
        # Execute safe.native's actual decision on synthetic scan results, then
        # require the observer to retain exactly its permitted completed cases.
        # No docker command is executed because captured is mocked throughout.
        for docker in (0, 2, 137):
            for native_code in (0, 2, 137):
                for markers in (0, 1, 2):
                    for license_xml in (0, 1):
                        for activation_aborted in (0, 1):
                            values = receipts(enabled=True)

                            def captured(_argv, _seconds, scan):
                                scan.native_exit = native_code; scan.exit_markers = markers
                                scan.counts['invalidLicenseXml400'] = license_xml
                                scan.counts['nativeActivationAborted'] = activation_aborted
                                return docker, scan

                            with patch.object(safe.private, 'captured', side_effect=captured):
                                safe.native(IDENT, 'SYNTHETIC_NO_EXECUTION', 1800, values[0])
                            healthy = markers == 1 and docker == native_code and not (license_xml or activation_aborted)
                            with self.subTest(docker=docker, native=native_code, markers=markers, license=license_xml, aborted=activation_aborted):
                                if healthy:
                                    result = self.summary(values)
                                    self.assertEqual(result['captureNativeExit'], native_code)
                                    self.assertEqual(result['captureStatus'], values[0]['status'])
                                else:
                                    with self.assertRaisesRegex(adapter.Blocked, 'CAPTURE_SESSION_WOULD_BE_BLOCKED'):
                                        self.summary(values)

    def test_forged_capture_status_and_boolean_exits_still_rejected(self):
        for code in (0, 2, 137):
            expected = 'NATIVE_SUCCEEDED' if code == 0 else 'NATIVE_FAILED'
            for status in adapter.STATES - {expected}:
                values = receipts(code=code); values[0]['status'] = status
                with self.subTest(code=code, status=status), self.assertRaisesRegex(adapter.Blocked, 'CAPTURE_NATIVE_STATUS'):
                    self.summary(values)
        for key in ('dockerExitCode', 'nativeExitCode', 'nativeExitMarkerCount'):
            values = receipts(); values[0][key] = True
            with self.subTest(key=key), self.assertRaisesRegex(adapter.Blocked, 'NATIVE_RESULT_FIELDS'):
                self.summary(values)

    def test_fault_cannot_reach_publication_or_emit_publishable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); home = root/'private'
            values = receipts(enabled=True); values[0]['counterLightDiagnosticFault'] = 'pendant-zero:before-capture'
            for phase, value in zip(('capture', 'finish', 'session'), values):
                safe.private.write(safe.file(root, phase), value)
            parts = (None, None, safe.private, None, {'guard': IDENT}, None, {})
            with patch.object(adapter, 'context', return_value=parts), \
                 patch.object(adapter, 'stopped') as stopped, \
                 patch.object(adapter, 'write_new') as write_new, \
                 self.assertRaisesRegex(adapter.Blocked, 'CAPTURE_DIAGNOSTIC_SELECTOR'):
                adapter.publish(root, home)
            stopped.assert_not_called(); write_new.assert_not_called()
            self.assertFalse((root/adapter.TASK/'evidence/visual-candidate'/adapter.PUBLIC_NAME).exists())

    def test_dependency_lock_matches_all_current_files_and_adapter_self(self):
        lock = json.loads((ROOT/adapter.PACKAGE/'dependency-lock.json').read_bytes())
        self.assertEqual(lock['files']['stage_a_inventory_ci.py']['path'], adapter.SCRIPT)
        for name, row in lock['files'].items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest(), row['sha256'])


if __name__ == '__main__': unittest.main()
