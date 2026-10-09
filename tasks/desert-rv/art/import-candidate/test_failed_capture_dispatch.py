"""End-to-end dispatcher failure identity; synthetic fixtures are never native proof."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import test_failed_capture_output as fixtures
import verify_output
from strict_output import StrictError

class FailureDispatchTests(unittest.TestCase):
    def fixture(self):
        f=fixtures.FailedCaptureTests('test_failed_native_exports_only_bounded_safe_diagnostics')
        f.setUp();self.addCleanup(f.doCleanups);f.flush();f.out.rmdir()
        return f
    def environment(self,f):
        return patch.dict(os.environ,{'GITHUB_SHA':f.summary['importCommit'],'GITHUB_RUN_ID':f.summary['importRunUrl'].rsplit('/',1)[1]})
    def test_committed_diagnostics_still_raise_original_and_receipt_is_not_rewritten(self):
        f=self.fixture();original=StrictError('STRICT_NATIVE_FAILED');writes=[];write=Path.write_text;write_bytes=Path.write_bytes
        def observe(path,*args,**kwargs):
            if path.name=='receipt.json':writes.append(path)
            return write(path,*args,**kwargs)
        def observe_bytes(path,*args,**kwargs):
            if path.name=='receipt.json':writes.append(path)
            return write_bytes(path,*args,**kwargs)
        with self.environment(f),patch.object(verify_output,'export_strict',side_effect=original),patch.object(Path,'write_text',observe),patch.object(Path,'write_bytes',observe_bytes):
            with self.assertRaises(StrictError) as caught:verify_output.export(f.root,f.out,'failure','success')
        self.assertIs(caught.exception,original)
        receipt=json.loads((f.out/'receipt.json').read_text())
        self.assertEqual(receipt['status'],'FAILED_DIAGNOSTICS');self.assertFalse(receipt['approved']);self.assertLessEqual(receipt['images'],8)
        self.assertEqual(len(writes),1);self.assertTrue(writes[0].parent.name.startswith('.failed-diagnostics-'))
        self.assertFalse(any(p.suffix in ('.fbx','.prefab','.mat','.xml','.log') for p in f.out.rglob('*')))
    def test_unverified_schema_failure_keeps_receipt_only(self):
        f=self.fixture();original=StrictError('STRICT_SCHEMA_MISMATCH')
        with self.environment(f),patch.object(verify_output,'export_strict',side_effect=original):
            with self.assertRaises(StrictError) as caught:verify_output.export(f.root,f.out,'failure','success')
        self.assertIs(caught.exception,original);self.assertEqual([p.name for p in f.out.iterdir()],['receipt.json'])
        self.assertEqual(json.loads((f.out/'receipt.json').read_text())['status'],'FAILED_NOT_ACCEPTED')
    def test_diagnostic_collector_error_cannot_mask_original_or_leak_text(self):
        f=self.fixture();original=StrictError('STRICT_NATIVE_FAILED')
        with self.environment(f),patch.object(verify_output,'export_strict',side_effect=original),patch('failed_capture_output.try_export_failed',side_effect=RuntimeError('SECRET STACK')):
            with self.assertRaises(StrictError) as caught:verify_output.export(f.root,f.out,'failure','success')
        self.assertIs(caught.exception,original);self.assertEqual([p.name for p in f.out.iterdir()],['receipt.json'])
        self.assertNotIn('SECRET',(f.out/'receipt.json').read_text())

if __name__=='__main__':unittest.main()
