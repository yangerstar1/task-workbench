#!/usr/bin/env python3
"""Focused synthetic checks: no Unity, Docker, secrets or external requests."""
import copy
import os
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch
import phone_return_probe_ci as phone
import safe_project_ci as safe

IDENT=dict(sourceCommit='1'*40,reviewedCandidateCommit='2'*40,runId='123',runAttempt='1')

def fixture():
    v=dict(schemaVersion=1,scope=phone.SCOPE,testIdentity=phone.CASE,**IDENT,renderer='llvmpipe',status='FUNCTIONAL_ROUTE_AND_STATE_OBSERVED',stage='TEARDOWN',timing='TIMING_FAIL',elapsedMs=150000,mode=0,initialPaidMinor=1000,paidMinor=1000,initialScratch=.3,scratch=.3)
    v.update({k:True for k in phone.FLAGS});v.update(phoneFocused=False,deadlineExceeded=False)
    v.update({k:'a'*64 for k in phone.HASHES});v.update({k:[0]*n for k,n in phone.VECTORS.items()})
    v['routes']=[dict(segment=i,frames=100,outcome='REACHED',elapsedMs=50000 if i==2 else 10000,pathMeters=1.2,maxFrameWall=45 if i==2 else .1,remaining=.08,position=[0,0,0]) for i in range(4)]
    return v

class PhoneTests(unittest.TestCase):
    def reject(self,v):
        with self.assertRaises((ValueError,AssertionError)):phone.validate_observation(v,IDENT)
    def test_functional_completion_preserves_timing_failure(self):
        v=phone.validate_observation(fixture(),IDENT);self.assertEqual(v['timing'],'TIMING_FAIL')
    def test_false_success_rejections(self):
        for field,value in [('cleanupComplete',False),('routeComplete',False),('deadlineExceeded',True),('elapsedMs',180000),('phoneOpened',False),('cameraRestored',False),('finalSeated',False),('phoneFocused',True),('stateHash','b'*64),('ticketHash','b'*64),('paidMinor',999),('scratch',.4),('timing','NO_OVERRUN_OBSERVED')]:
            with self.subTest(field=field):v=fixture();v[field]=value;self.reject(v)
    def test_unknown_fields_and_raw_renderer_rejected(self):
        v=fixture();v['rawLog']='secret';self.reject(v)
        v=fixture();v['renderer']='llvmpipe version raw device text';self.reject(v)
    def test_nan_overflow_and_bool_number_rejected(self):
        for value in (float('nan'),float('inf'),-1,480001,True):
            v=fixture();v['elapsedMs']=value;self.reject(v)
    def test_missing_and_aborted_routes_never_complete(self):
        v=fixture();v['routes'].pop();self.reject(v)
        v=fixture();v['routes'][2]['outcome']='ABORTED';self.reject(v)
        v=fixture();v['routes'][3]['remaining']=1;self.reject(v)
    def test_partial_observation_is_inconclusive(self):
        v=fixture();v.update(status='INCONCLUSIVE',routeComplete=False,cleanupComplete=False,stage='WALK');v['routes']=v['routes'][:3];v['routes'][-1]['outcome']='MOVING'
        self.assertEqual(phone.validate_observation(v,IDENT)['status'],'INCONCLUSIVE')
    def test_exact_anchored_filter_excludes_all_legacy_37(self):
        self.assertTrue(re.fullmatch(phone.FILTER,phone.CASE));self.assertFalse(re.fullmatch(phone.FILTER,phone.CASE+'Extra'))
        legacy=safe.split.names('core')+safe.split.names('world');self.assertEqual(len(legacy),37)
        for name in legacy:self.assertFalse(re.fullmatch(phone.FILTER,name))
        for shard in ('core','world'):
            for selection in safe.split.selection(shard).split(';'):self.assertFalse(re.fullmatch(selection,phone.CASE))
    def test_fixed_native_selection_and_budget(self):
        with patch.object(safe,'PHASES',dict(safe.PHASES)),patch.object(safe,'visual',safe.visual):
            safe.configure_phone_return();self.assertEqual(set(safe.PHASES),{'phone-return-probe'});self.assertEqual(safe.PHASES['phone-return-probe'][3],480)
            argv=safe.project_argv('phone-return-probe',IDENT)
            self.assertEqual(argv[argv.index('-testFilter')+1],phone.FILTER);self.assertEqual(argv[argv.index('-assemblyNames')+1],'Lottery.G3.PlayMode.Tests')
            self.assertNotIn('-g3RegressionProgress',argv);self.assertNotIn('-g3PerformanceProbe',argv)
    def test_selector_requires_explicit_capability_and_rejects_mixing(self):
        for args in [('phone-return-probe',),('regression-play-world','--phone-return-only'),('start','--phone-return-only','--performance-only'),('start','--phone-return-only','--counter-light-diagnostic')]:
            with self.subTest(args=args),patch.object(sys,'argv',['safe_project_ci.py',*args]):self.assertEqual(safe.main(),1)
    def test_xml_exact_identity_and_no_raw_export(self):
        xml=f'<test-run result="Passed" total="1" passed="1" failed="0" skipped="0" inconclusive="0"><test-suite type="Assembly" name="{phone.ASSEMBLY}" result="Passed"><test-case fullname="{phone.CASE}" result="Passed"><output>DO_NOT_EXPORT_RAW_TEXT</output></test-case></test-suite></test-run>'.encode()
        self.assertEqual(phone.test_summary(xml),'EXACT_CASE_PASSED')
        for bad in (xml.replace(phone.CASE.encode(),b'wrong'),xml.replace(b'total="1"',b'total="2"'),b'<!DOCTYPE x>'+xml):
            if b'total="2"' in bad:self.assertEqual(phone.test_summary(bad),'EXACT_CASE_NOT_PASSED')
            else:
                with self.assertRaises((ValueError,AssertionError)):phone.test_summary(bad)
    def test_missing_source_or_wrong_run_is_rejected(self):
        v=fixture();v['runId']='456';self.reject(v)
    def test_source_has_no_pose_or_internal_navigation_shortcut(self):
        root=Path(__file__).resolve().parents[1];source=(root/'unity/Assets/G3/Tests/PlayMode/G3PhoneReturnDiagnostic.cs').read_text()
        for forbidden in ('SetPose(', 'DeclareWorldSpawn(', 'P.Execute(', 'SetupLocalPanel(', 'shaderRecorder'):
            self.assertNotIn(forbidden,source)
        self.assertIn('Timeout(180000)',source);self.assertIn('phoneClock.Elapsed.TotalSeconds>=180',source)
        self.assertIn('Explicit(',source);self.assertIn('PhoneBounded(PhoneReturnBody())',source)
        self.assertIn('Assert.That(StateCodec.ComputeHash(State),Is.EqualTo(hash))',source)

if __name__=='__main__':unittest.main()
