#!/usr/bin/env python3
"""Synthetic media/identity tests; never claims native PNG acquisition."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import independent_g3_frames_ci as frames
import test_visual_candidate_ci as fixtures


class IndependentFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.OriginalG3FrameExportTests.setUpClass.__func__(cls)
    png=classmethod(fixtures.OriginalG3FrameExportTests.png.__func__)
    save_receipt=fixtures.OriginalG3FrameExportTests.save_receipt
    def setUp(self):
        fixtures.OriginalG3FrameExportTests.setUp(self)
        self.xmlpath=self.xmlpath.rename(self.xmlpath.with_name('playmode-results.xml'))
        ident=frames.visual.read_json(frames.visual.outdir(self.root)/'source-receipt.json');ident['reviewedCandidateCommit']='2'*40
        frames.visual.write(frames.visual.outdir(self.root)/'source-receipt.json',ident)
        self.native=dict(ident,phase='regression-play',status='NATIVE_SUCCEEDED',nativeExitCode=0,dockerExitCode=0,nativeExitMarkerCount=1,observations=dict(invalidLicenseXml400=0,nativeActivationAborted=0))
        self.save_native()
    def save_native(self):frames.visual.write(frames.visual.outdir(self.root)/'safe-regression-play.json',self.native)
    def save_xml(self):self.xmlpath.write_bytes(ET.tostring(self.xml))
    def export(self):frames.export(self.root)
    def output(self):return frames.destination(self.root)
    def proof(self):return json.loads((self.output()/frames.EXPORT).read_text())
    def reject(self):
        with self.assertRaises(Exception):self.export()
        self.assertFalse(any((self.output()/name).exists() for name in (*frames.FILES,frames.EXPORT)))
    def fail_other(self):
        other=next(c for c in self.xml.iter('test-case') if c.get('fullname')!=frames.visual.ORIGINAL_G3_CASE);other.set('result','Failed')
        self.xml.set('result','Failed(Child)');self.xml.set('passed','34');self.xml.set('failed','1');self.save_xml()
        self.native.update(status='NATIVE_FAILED',nativeExitCode=2,dockerExitCode=2);self.save_native()
    def test_full_suite_success_exports_exact_originals(self):
        self.export();self.assertTrue(self.proof()['suiteAllPassed']);self.assertEqual({p.name for p in self.output().iterdir()},set(frames.FILES)|{frames.EXPORT})
        for name in frames.FILES:self.assertEqual((self.output()/name).read_bytes(),(self.source/name).read_bytes())
    def test_other_failure_allows_only_target_evidence_and_discloses_counts(self):
        self.fail_other();self.export();p=self.proof();self.assertFalse(p['suiteAllPassed']);self.assertEqual(p['suiteCounts'],dict(total=35,passed=34,failed=1,skipped=0));self.assertEqual(p['visual23FrameGate'],'NOT_EVALUATED_BY_THIS_EXPORT');self.assertEqual(p['g3Gate'],'NOT_EVALUATED')
        self.assertFalse((frames.visual.outdir(self.root)/'captures/capture-receipt.json').exists())
    def test_two_other_failures_disclosed_as_run12_shape(self):
        self.fail_other();other=next(c for c in self.xml.iter('test-case') if c.get('fullname')!=frames.visual.ORIGINAL_G3_CASE and c.get('result')=='Passed');other.set('result','Failed');self.xml.set('passed','33');self.xml.set('failed','2');self.save_xml();self.export();self.assertEqual(self.proof()['suiteCounts'],dict(total=35,passed=33,failed=2,skipped=0))
    def test_png_text_payload_rejected_even_with_matching_receipt_hash(self):
        p=self.source/'empty.png';raw=p.read_bytes();raw=raw[:33]+self.chunk(b'tEXt',b'PRIVATE_SENTINEL')+raw[33:];p.write_bytes(raw);self.receipt['frames'][0].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());self.save_receipt();self.reject()
    def test_target_failure_never_exports(self):
        target=next(c for c in self.xml.iter('test-case') if c.get('fullname')==frames.visual.ORIGINAL_G3_CASE);target.set('result','Failed');self.xml.set('result','Failed(Child)');self.xml.set('passed','34');self.xml.set('failed','1');self.save_xml();self.native.update(status='NATIVE_FAILED',nativeExitCode=2,dockerExitCode=2);self.save_native();self.reject()
    def test_missing_duplicate_wrong_identity_never_exports(self):
        original=ET.tostring(self.xml)
        for mode in ('missing','duplicate','wrong'):
            self.xml=ET.fromstring(original);a=self.xml.find('test-suite');case=a.find('test-case')
            if mode=='missing':a.remove(case)
            elif mode=='duplicate':a.append(copy.deepcopy(case))
            else:case.set('fullname','Arbitrary.Case')
            self.save_xml();self.reject()
    def test_wrong_assembly_and_orphan_rejected(self):
        a=self.xml.find('test-suite');a.set('name','Wrong.dll');self.save_xml();self.reject()
    def test_skip_or_count_fabrication_rejected(self):
        self.xml.set('passed','999');self.save_xml();self.reject()
    def test_timeout_missing_exit_and_mismatch_rejected(self):
        original=copy.deepcopy(self.native)
        for change in [dict(status='PROCESS_TIMEOUT'),dict(nativeExitMarkerCount=0),dict(nativeExitCode=None),dict(dockerExitCode=2),dict(nativeExitCode=True),dict(nativeExitMarkerCount=True)]:
            self.native=dict(original,**change);self.save_native();self.reject()
    def test_licensing_error_rejected(self):
        self.native['observations']['nativeActivationAborted']=1;self.save_native();self.reject()
    def test_wrong_native_source_review_run_attempt_rejected(self):
        original=copy.deepcopy(self.native)
        for key in ('sourceCommit','reviewedCandidateCommit','runId','runAttempt'):
            self.native=dict(original,**{key:'wrong'});self.save_native();self.reject()
    def test_current_attempt_and_preparation_required(self):
        with patch.dict(os.environ,GITHUB_RUN_ATTEMPT='2'):self.reject()
        (frames.visual.outdir(self.root)/'original-g3-preparation.json').unlink();self.reject()
    def test_stale_xml_or_frame_rejected(self):
        os.utime(self.xmlpath,ns=(1,1));self.reject();self.save_xml();os.utime(self.source/'empty.png',ns=(1,1));self.reject()
    def test_missing_corrupt_or_late_frame_no_partial_export(self):
        p=self.source/'challenge-protected.png';p.write_bytes(b'broken');self.reject()
    def test_corrupt_png_receipt_rehashed_still_rejected(self):
        p=self.source/'empty.png';raw=p.read_bytes()[:-1];p.write_bytes(raw);self.receipt['frames'][0].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());self.save_receipt();self.reject()
    def test_wrong_dimensions_and_metadata_payload_rejected(self):
        p=self.source/'empty.png';raw=self.png(0,width=640);p.write_bytes(raw);self.receipt['frames'][0].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());self.save_receipt();self.reject()
    def test_arbitrary_stage_path_label_rejected(self):
        original=copy.deepcopy(self.receipt)
        for changes in [dict(stage='../private'),dict(file='../private.png'),dict(fixtureLabel='SYNTHETIC_PRIVATE'),dict(gameRunId='private-run')]:
            self.receipt=copy.deepcopy(original);self.receipt['frames'][0].update(changes);self.save_receipt();self.reject()
    def test_raw_receipt_duplicate_key_and_secret_bait_rejected(self):
        p=self.source/'render-receipt.json';raw=p.read_text();p.write_text(raw.replace('"schemaVersion": 1','"schemaVersion": "PRIVATE_SENTINEL", "schemaVersion": 1'));self.reject()
        self.receipt['graphicsDeviceName']='UNITY_PASSWORD PRIVATE_SENTINEL';self.save_receipt();self.reject()
    def test_raw_xml_secret_and_dtd_rejected(self):
        self.xmlpath.write_text('<!DOCTYPE test-run><test-run/>');self.reject()
        self.save_xml();e=ET.SubElement(self.xml,'output');e.text='UNITY_PASSWORD PRIVATE_SENTINEL';self.save_xml();self.reject()
    def test_utf16_utf32_and_bom_dtd_entities_rejected(self):
        document='<!DOCTYPE test-run [<!ENTITY harmless "x">]>'+ET.tostring(self.xml,encoding='unicode')
        for encoding in ('utf-16-le','utf-16-be','utf-16','utf-32-le','utf-32-be','utf-32','utf-8-sig'):
            with self.subTest(encoding=encoding):self.xmlpath.write_bytes(document.encode(encoding));self.reject()
    def test_non_utf8_nul_xml_rejected_without_dtd(self):
        document=ET.tostring(self.xml,encoding='unicode')
        for encoding in ('utf-16-le','utf-16-be','utf-32-le','utf-32-be'):
            with self.subTest(encoding=encoding):self.xmlpath.write_bytes(document.encode(encoding));self.reject()
    def test_valid_native_utf8_bom_xml_is_accepted(self):
        self.xmlpath.write_bytes(ET.tostring(self.xml,encoding='unicode').encode('utf-8-sig'));self.export();self.assertTrue(self.proof()['suiteAllPassed'])
    def test_symlink_source_or_parent_rejected(self):
        p=self.source/'empty.png';target=self.root/'real.png';p.rename(target);p.symlink_to(target);self.reject()
    def test_stale_destination_cleared_before_failure(self):
        self.export();self.xmlpath.unlink();self.reject()
    def test_copy_failure_cleans_owned_outputs_without_touching_siblings(self):
        self.output().mkdir(parents=True);keep=self.output()/'unrelated.txt';keep.write_text('KEEP');original=Path.write_bytes
        def fail(p,data):
            if p==self.output()/'night.png':raise OSError('PRIVATE_SENTINEL')
            return original(p,data)
        with patch.object(Path,'write_bytes',fail):self.reject()
        self.assertEqual(keep.read_text(),'KEEP')
    def test_reuses_mature_media_validator(self):
        original=frames.g3_ci.inspect_captures
        with patch.object(frames.g3_ci,'inspect_captures',wraps=original) as check:self.export();check.assert_called_once()
    def test_old_full_suite_exporter_still_rejects_other_failure(self):
        self.fail_other()
        with self.assertRaises(ValueError):frames.visual.export_original_g3_captures(self.root)
        self.assertFalse((frames.visual.outdir(self.root)/'original-g3-captures/empty.png').exists())


if __name__=='__main__':unittest.main()
