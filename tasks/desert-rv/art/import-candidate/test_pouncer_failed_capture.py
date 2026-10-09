"""Pinned-source synthetic Pouncer failure fixtures, never native evidence."""
import json,os,unittest
from unittest.mock import patch
import test_pouncer_output as fixtures
from test_failed_capture_output import native_xml
from strict_output import StrictError
import verify_output

class PouncerFailureDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.PouncerExportTests.setUpClass()
    def setUp(self):
        self.f=fixtures.PouncerExportTests('test_valid_unreviewed_export_rehashes_every_file');self.f.setUp();self.addCleanup(self.f.tearDown)
        self.f.native.write_text(native_xml(True));self.f.cap['status']='not-complete'
    def call(self):
        self.f.flush()
        with patch.dict(os.environ,{'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'123'}):
            with self.assertRaisesRegex(StrictError,'STRICT_NATIVE_FAILED'):verify_output.export(self.f.root,self.f.out,'failure','success')
        return json.loads((self.f.out/'receipt.json').read_text())
    def test_failed_pouncer_keeps_bounded_worst_ground_and_no_assets(self):
        f=self.f.cap['frames'][5];f['worldMinY']=-.08;f['meshWorldMin']['y']=-.08;f['meshWorldSize']['y']=2.08;f['meshSizeRatioToNeutral']['y']=1.04
        r=self.call();self.assertEqual(r['status'],'FAILED_DIAGNOSTICS');self.assertFalse(r['approved']);self.assertLessEqual(r['images'],8)
        d=json.loads((self.f.out/'failed-diagnostics.json').read_text());bad=d['frames'][5]
        self.assertFalse(bad['groundWithinFourMillimeters']);self.assertTrue(bad['exportedImage']);self.assertEqual(d['frameCount'],184)
        self.assertFalse(any(p.suffix in ('.fbx','.prefab','.mat','.xml','.log') for p in self.f.out.rglob('*')))
    def test_pouncer_false_public_approval_is_not_sanitized_into_success(self):
        self.f.imp['visualReviewed']=True;r=self.call();self.assertEqual(r['status'],'FAILED_NOT_ACCEPTED');self.assertEqual([p.name for p in self.f.out.iterdir()],['receipt.json'])
    def test_pouncer_unrelated_weapon_text_is_dropped(self):
        self.f.imp['weaponCalibration']={'private':'SECRET','approved':True};self.f.cap['weapon']={'private':'SECRET','visualApproved':True}
        r=self.call();self.assertEqual(r['status'],'FAILED_DIAGNOSTICS')
        for p in self.f.out.rglob('*.json'):self.assertNotIn('SECRET',p.read_text())

if __name__=='__main__':unittest.main()
