#!/usr/bin/env python3
"""Focused synthetic checks: no Unity, Docker, secrets or external requests."""
import copy
import tempfile
import json
import reflection_bake_ci as reflection
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
            safe.configure_phone_return();self.assertEqual(set(safe.PHASES),{'phone-return-prepare','phone-return-probe'});self.assertEqual(safe.PHASES['phone-return-probe'][3],480)
            argv=safe.project_argv('phone-return-probe',IDENT)
            self.assertEqual(argv[argv.index('-testFilter')+1],phone.FILTER);self.assertEqual(argv[argv.index('-assemblyNames')+1],'Lottery.G3.PlayMode.Tests')
            self.assertNotIn('-g3RegressionProgress',argv);self.assertNotIn('-g3PerformanceProbe',argv)
    def test_selector_requires_explicit_capability_and_rejects_mixing(self):
        for args in [('phone-return-prepare',),('phone-return-probe',),('regression-play-world','--phone-return-only'),('start','--phone-return-only','--performance-only'),('start','--phone-return-only','--counter-light-diagnostic')]:
            with self.subTest(args=args),patch.object(sys,'argv',['safe_project_ci.py',*args]):self.assertEqual(safe.main(),1)
    def test_preparation_argv_is_fixed_and_never_runs_tests(self):
        with patch.object(safe,'PHASES',dict(safe.PHASES)),patch.object(safe,'visual',safe.visual):
            safe.configure_phone_return();self.assertEqual(safe.PHASES['phone-return-prepare'][3],1800)
            argv=safe.project_argv('phone-return-prepare',IDENT)
            self.assertEqual(argv[argv.index('-executeMethod')+1],'Lottery.G3.Editor.G3Build.Prepare')
            for flag in ('-runTests','-testFilter','-assemblyNames'):self.assertNotIn(flag,argv)
            self.assertIn('-quit',argv);self.assertEqual(argv[argv.index('-probeRunAttempt')+1],'1')
    def test_failed_or_foreign_preparation_never_qualifies(self):
        base=dict(IDENT,phase='phone-return-prepare',processBudgetSeconds=1800,status='NATIVE_SUCCEEDED',nativeExitCode=0,dockerExitCode=0,nativeExitMarkerCount=1,nativeStartedAtNs=123)
        for field,value in [('status','NATIVE_FAILED'),('status','PROCESS_TIMEOUT'),('sourceCommit','3'*40),('runId','999'),('nativeExitCode',1),('nativeExitMarkerCount',0),('processBudgetSeconds',1801),('nativeStartedAtNs',None)]:
            bad=dict(base);bad[field]=value
            with self.subTest(field=field,value=value),patch.object(phone,'identity',return_value=IDENT),patch.object(phone,'read_json',return_value=bad),patch.object(phone,'read_regular') as read:
                with self.assertRaises((ValueError,AssertionError)):phone.verify_preparation(Path('/unused'))
                read.assert_not_called()
    def test_preparation_rejects_missing_stale_and_wrong_source_reflections(self):
        native=dict(IDENT,phase='phone-return-prepare',processBudgetSeconds=1800,status='NATIVE_SUCCEEDED',nativeExitCode=0,dockerExitCode=0,nativeExitMarkerCount=1,nativeStartedAtNs=123)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/phone.TASK/'unity/Assets/G3/Shop/Resources/G3/Shop/Reflections/reflection-receipt.json'
            with patch.object(phone,'identity',return_value=IDENT),patch.object(phone,'read_json',return_value=native):
                with self.assertRaises((ValueError,AssertionError)):phone.verify_preparation(root)
                path.parent.mkdir(parents=True);path.write_text('{}');os.utime(path,ns=(1,1))
                with self.assertRaises((ValueError,AssertionError)):phone.verify_preparation(root)
                receipt=dict(schemaVersion=1,status='COMPLETE_BAKED_STATIC_REFLECTIONS',recipe=reflection.RECIPE,sourceDigest='a'*64,
                             sourceCommit='9'*40,runId=IDENT['runId'],runAttempt='1',unityVersion='6000.3.19f1',day={},night={},
                             colorSpace='Gamma',runtimeDependencyHash='b'*32,pipelineDependencyHash='c'*32,captureRenderers=1,captureTriangles=1)
                path.write_text(json.dumps(receipt))
                with self.assertRaises((ValueError,AssertionError)):phone.verify_preparation(root)
    def test_export_requires_preparation_even_if_probe_result_claims_success(self):
        with patch.object(phone,'identity',return_value=IDENT),patch.object(phone,'verify_preparation',side_effect=ValueError('blocked')),patch.object(Path,'unlink'),patch.object(phone,'write') as write:
            with self.assertRaises((ValueError,AssertionError)):phone.export(Path('/unused'))
            self.assertEqual(write.call_args.args[1]['status'],'INCONCLUSIVE')
            self.assertIsNone(write.call_args.args[1]['observation'])
    def test_capture_filter_is_exact_under_normal_and_counterlight_profiles(self):
        case='Lottery.G3.VisualCandidate.Tests.VisualCandidateCaptureTests.ScenarioStateCaptureRetainsTwentyThreeViewsFromRealTransactionsV2'
        for enabled in (False,True):
            with patch.object(safe,'COUNTER_LIGHT_DIAGNOSTIC',enabled):
                argv=safe.project_argv('capture',IDENT);selection=argv[argv.index('-testFilter')+1]
                self.assertTrue(re.fullmatch(selection,case));self.assertFalse(re.fullmatch(selection,case+'Extra'))
                self.assertFalse(re.fullmatch(selection,'Lottery.G3.VisualCandidate.Tests.LoanLabelTests.EmptyLoanHasNoDueDate'))
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
