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
from types import SimpleNamespace
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

DISK_IDENT=dict(IDENT,requestId='lottery-phone-return-20261015-03')


class RunnerDiskTests(unittest.TestCase):
    def exercise(self, before=1, after=phone.DISK_REQUIRED_BYTES, cleanup_code=0,
                 guard_error=None, cleanup_error=None, measurements=None):
        snapshots=[];order=[]
        def guarded(root):
            order.append('guard')
            if guard_error:raise guard_error
        def measured(root):
            order.append('measure')
            value=next(values)
            if isinstance(value,BaseException):raise value
            return SimpleNamespace(free=value)
        def cleanup(*args,**kwargs):
            order.append('cleanup')
            if cleanup_error:raise cleanup_error
            return SimpleNamespace(returncode=cleanup_code)
        values=iter(measurements if measurements is not None else [before,after])
        with patch.object(phone,'disk_identity',return_value=DISK_IDENT),patch.object(phone,'guard',side_effect=guarded),patch.object(phone,'read_disk_receipt'), \
             patch.object(phone,'shutil') as usage,patch.object(phone.subprocess,'run',side_effect=cleanup) as run, \
             patch.object(phone,'write_disk_receipt',side_effect=lambda root,value:snapshots.append(copy.deepcopy(value))):
            usage.disk_usage.side_effect=measured
            code=phone.prepare_runner_disk(Path('/unused'))
        for value in snapshots:phone.validate_disk_receipt(value,DISK_IDENT)
        return code,snapshots,order,run

    def test_disk_exact_command_guard_order_and_unchanged_threshold(self):
        code,snapshots,order,run=self.exercise()
        self.assertEqual(code,0);self.assertEqual(order,['guard','measure','cleanup','measure'])
        run.assert_called_once_with(['sudo','rm','-rf','/usr/share/dotnet','/opt/ghc','/usr/local/.ghcup',
                                     '/usr/local/lib/android','/opt/hostedtoolcache/CodeQL'],cwd=Path('/unused'),
                                    stdin=phone.subprocess.DEVNULL,stdout=phone.subprocess.DEVNULL,
                                    stderr=phone.subprocess.DEVNULL,check=False)
        last=snapshots[-1]
        self.assertEqual(last['status'],'DISK_PREPARATION_SUCCEEDED')
        self.assertEqual(last['requiredFreeBytes'],32212254720)
        self.assertEqual(last['freeBeforeBytes'],1);self.assertEqual(last['freeAfterBytes'],32212254720)
        self.assertEqual(last['helperReturnMarkerCount'],1);self.assertEqual(last['helperReturnCode'],0)
        self.assertTrue(all(snapshot['helperReturnMarkerCount']==0 for snapshot in snapshots[:-1]))

    def test_disk_one_byte_below_threshold_fails_without_retry(self):
        code,snapshots,_,run=self.exercise(after=phone.DISK_REQUIRED_BYTES-1)
        self.assertEqual(code,1);self.assertEqual(run.call_count,1)
        self.assertEqual(snapshots[-1]['status'],'INSUFFICIENT_IMAGE_DISK_SPACE')
        self.assertEqual(snapshots[-1]['thresholdExitCode'],1)

    def test_disk_guard_failure_prevents_cleanup_and_measurement(self):
        code,snapshots,order,run=self.exercise(guard_error=ValueError('RAW_ERROR_MUST_NOT_ESCAPE'))
        self.assertEqual(code,1);self.assertEqual(order,['guard']);run.assert_not_called()
        self.assertEqual(snapshots[-1]['status'],'GUARD_OR_IDENTITY_REJECTED')
        self.assertEqual(snapshots[-1]['guardExitCode'],1)
        self.assertEqual(snapshots[-1]['freeBeforeBytes'],-1)
        self.assertNotIn('RAW_ERROR',json.dumps(snapshots))

    def test_disk_cleanup_nonzero_preserves_exit_and_after_measurement(self):
        code,snapshots,_,run=self.exercise(cleanup_code=7)
        self.assertEqual(code,1);self.assertEqual(run.call_count,1)
        last=snapshots[-1];self.assertEqual(last['status'],'CLEANUP_FAILED')
        self.assertEqual(last['cleanupExitCode'],7);self.assertIsNone(last['thresholdExitCode'])
        self.assertEqual(last['freeAfterBytes'],phone.DISK_REQUIRED_BYTES)

    def test_disk_cleanup_launch_failure_exports_no_exception(self):
        code,snapshots,order,_=self.exercise(cleanup_error=OSError('RAW_ERROR_MUST_NOT_ESCAPE'))
        self.assertEqual(code,1);self.assertEqual(order,['guard','measure','cleanup'])
        self.assertEqual(snapshots[-1]['status'],'CLEANUP_LAUNCH_OR_EXIT_REJECTED')
        self.assertIsNone(snapshots[-1]['cleanupExitCode']);self.assertNotIn('RAW_ERROR',json.dumps(snapshots))

    def test_disk_measurements_fail_closed_and_never_export_raw_values(self):
        for bad in (True,-1,2**63,float('nan'),'RAW_ERROR_MUST_NOT_ESCAPE',OSError('RAW_ERROR_MUST_NOT_ESCAPE')):
            for values,stage,count in (([bad],'BEFORE_MEASUREMENT_FAILED',0),([1,bad],'AFTER_MEASUREMENT_FAILED',1)):
                with self.subTest(bad=type(bad).__name__,stage=stage):
                    code,snapshots,_,run=self.exercise(measurements=values)
                    self.assertEqual(code,1);self.assertEqual(snapshots[-1]['status'],stage)
                    self.assertEqual(run.call_count,count);self.assertNotIn('RAW_ERROR',json.dumps(snapshots))

    def test_disk_interruption_does_not_claim_timeout_or_success(self):
        code,snapshots,_,_=self.exercise(cleanup_error=KeyboardInterrupt())
        self.assertEqual(code,1);self.assertEqual(snapshots[-1]['status'],'INTERRUPTED')
        self.assertEqual(snapshots[-1]['stage'],'CLEANUP');self.assertIsNone(snapshots[-1]['cleanupExitCode'])

    def test_disk_initial_receipt_write_failure_prevents_cleanup(self):
        with patch.object(phone,'disk_identity',return_value=DISK_IDENT),patch.object(phone,'write_disk_receipt',side_effect=OSError('write')), \
             patch.object(phone,'guard') as guard,patch.object(phone.subprocess,'run') as run:
            with self.assertRaises(OSError):phone.prepare_runner_disk(Path('/unused'))
            guard.assert_not_called();run.assert_not_called()

    def test_disk_identity_is_tightly_bound_and_never_copies_extra_fields(self):
        env=dict(GITHUB_SHA=IDENT['sourceCommit'],GITHUB_RUN_ID=IDENT['runId'],GITHUB_RUN_ATTEMPT='1')
        with patch.dict(os.environ,env),patch.object(phone,'read_json',return_value=dict(DISK_IDENT,scope=phone.SCOPE,raw='RAW_ERROR')):
            self.assertEqual(phone.disk_identity(Path('/unused')),DISK_IDENT)
        for key,value in [('sourceCommit','bad'),('reviewedCandidateCommit','bad'),('runId','456'),('runId','1'*21),('runAttempt','2'),('requestId','bad')]:
            bad=dict(DISK_IDENT,scope=phone.SCOPE);bad[key]=value
            with self.subTest(key=key,value=value),patch.dict(os.environ,env),patch.object(phone,'read_json',return_value=bad):
                with self.assertRaises(ValueError):phone.disk_identity(Path('/unused'))

    def test_disk_receipt_atomic_fixed_schema_and_size(self):
        _,snapshots,_,_=self.exercise()
        expected={'schemaVersion','scope','phase','status','stage','cleanupPaths','requiredFreeBytes',
                  'freeBeforeBytes','freeAfterBytes','guardExitCode','cleanupExitCode','thresholdExitCode',
                  'helperReturnCode','helperReturnMarkerCount',*phone.DISK_IDENTITY_KEYS}
        self.assertTrue(all(set(value)==expected for value in snapshots))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);phone.write_disk_receipt(root,snapshots[-1])
            path=phone.outdir(root)/'runner-disk-preparation-state.json'
            self.assertEqual(json.loads(path.read_text()),snapshots[-1]);self.assertLessEqual(path.stat().st_size,4096)
            self.assertFalse(path.with_suffix('.tmp').exists())

    def test_disk_export_validator_rejects_extra_fields_wrong_identity_and_forged_states(self):
        _,snapshots,_,_=self.exercise();good=snapshots[-1]
        bad=copy.deepcopy(good);bad['rawText']='RAW_ERROR'
        with self.assertRaises(ValueError):phone.validate_disk_receipt(bad,DISK_IDENT)
        changes=[('schemaVersion',True),('requiredFreeBytes',1),('cleanupPaths',['/extra']),
                 ('freeAfterBytes',True),('freeAfterBytes',float('nan')),('freeAfterBytes',phone.DISK_REQUIRED_BYTES-1),
                 ('helperReturnMarkerCount',True),('helperReturnMarkerCount',0),('helperReturnCode',1),
                 ('guardExitCode',1),('cleanupExitCode',7),('thresholdExitCode',1),('stage','CLEANUP'),
                 ('status','IN_PROGRESS'),('status','RAW_ERROR'),('requestId','lottery-phone-return-20261015-99'),
                 ('sourceCommit','3'*40),('reviewedCandidateCommit','4'*40),('runId','999'),('runAttempt','2')]
        for key,value in changes:
            with self.subTest(key=key,value=value):
                bad=copy.deepcopy(good);bad[key]=value
                with self.assertRaises(ValueError):phone.validate_disk_receipt(bad,DISK_IDENT)

    def test_disk_incomplete_snapshot_remains_incomplete_and_never_proves_timeout(self):
        _,snapshots,_,_=self.exercise()
        partial=next(v for v in snapshots if v['stage']=='CLEANUP')
        self.assertEqual(partial['status'],'IN_PROGRESS');self.assertEqual(partial['helperReturnMarkerCount'],0)
        self.assertIsNone(partial['helperReturnCode']);self.assertIsNone(partial['cleanupExitCode'])
        phone.validate_disk_receipt(partial,DISK_IDENT)
        with tempfile.TemporaryDirectory() as folder,patch.object(phone,'disk_identity',return_value=DISK_IDENT):
            root=Path(folder);phone.write_disk_receipt(root,partial)
            value=phone.export_disk_receipt(root,'failure')
            self.assertEqual(value['status'],'IN_PROGRESS');self.assertNotIn('TIMEOUT',json.dumps(value))
            with self.assertRaises(ValueError):phone.export_disk_receipt(root,'success')
            self.assertFalse((phone.outdir(root)/'runner-disk-preparation.json').exists())

    def test_disk_safe_export_requires_actual_success_and_rejects_duplicate_or_extra_keys(self):
        _,snapshots,_,_=self.exercise();good=snapshots[-1]
        with tempfile.TemporaryDirectory() as folder,patch.object(phone,'disk_identity',return_value=DISK_IDENT):
            root=Path(folder);phone.write_disk_receipt(root,good)
            state=phone.outdir(root)/'runner-disk-preparation-state.json'
            target=phone.outdir(root)/'runner-disk-preparation.json'
            self.assertFalse(target.exists());self.assertEqual(phone.export_disk_receipt(root,'success'),good)
            self.assertEqual(json.loads(target.read_text()),good)
            for outcome in ('failure','cancelled','skipped','unexpected'):
                with self.assertRaises(ValueError):phone.export_disk_receipt(root,outcome)
                self.assertFalse(target.exists())
            for text in (state.read_text().rstrip()[:-1]+',"status":"DISK_PREPARATION_SUCCEEDED"}',
                         json.dumps(dict(good,rawText='RAW_ERROR')),'{}'+' '*4096,'{'):
                state.write_text(text);target.write_text(json.dumps(good))
                with self.assertRaises((ValueError,AssertionError)):phone.export_disk_receipt(root,'success')
                self.assertFalse(target.exists())

    def test_disk_export_preserves_phone_outcome_condition_and_never_bypasses_validation(self):
        for outcome in ('skipped','success','failure','cancelled'):
            with self.subTest(outcome=outcome),patch.dict(os.environ,dict(RUNNER_DISK_STEP_OUTCOME='success',PHONE_RETURN_STEP_OUTCOME=outcome)), \
                 patch.object(phone,'export_disk_receipt') as disk,patch.object(phone,'export') as export:
                phone.export_diagnostics(Path('/unused'))
                disk.assert_called_once_with(Path('/unused'),'success')
                self.assertEqual(export.call_count,int(outcome!='skipped'))
        with patch.dict(os.environ,dict(RUNNER_DISK_STEP_OUTCOME='success',PHONE_RETURN_STEP_OUTCOME='success')), \
             patch.object(phone,'export_disk_receipt',side_effect=ValueError('rejected')),patch.object(phone,'export') as export:
            with self.assertRaises(ValueError):phone.export_diagnostics(Path('/unused'))
            export.assert_not_called()

    def test_disk_preparation_checks_persisted_snapshot_before_successful_return(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(phone,'disk_identity',return_value=DISK_IDENT), \
             patch.object(phone,'guard'),patch.object(phone.shutil,'disk_usage',return_value=SimpleNamespace(free=phone.DISK_REQUIRED_BYTES)), \
             patch.object(phone.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as run:
            root=Path(folder);self.assertEqual(phone.prepare_runner_disk(root),0);self.assertEqual(run.call_count,1)
            self.assertFalse((phone.outdir(root)/'runner-disk-preparation.json').exists())
            self.assertEqual(phone.read_disk_receipt(root)['status'],'DISK_PREPARATION_SUCCEEDED')
            with patch.object(phone,'read_disk_receipt',side_effect=ValueError('rejected')):
                with self.assertRaises(ValueError):phone.prepare_runner_disk(root)

if __name__=='__main__':unittest.main()
