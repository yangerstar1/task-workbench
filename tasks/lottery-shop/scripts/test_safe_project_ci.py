#!/usr/bin/env python3
"""Synthetic boundary checks only; never invokes Docker or Unity."""
import contextlib
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import safe_project_ci as safe

IDENT = dict(scope=safe.visual.SCOPE, sourceCommit='1'*40, reviewedCandidateCommit='2'*40, runId='12345', runAttempt='1')


class BoundaryTests(unittest.TestCase):
    def test_three_exact_pinned_project_argument_sets(self):
        sets = [('capture','playmode','visual-candidate','Lottery.G3.VisualCandidate.Tests'),
                ('regression-edit','editmode','visual-regression-edit','Lottery.Probe.Tests;Lottery.G2.EditMode.Tests;Lottery.G3.EditMode.Tests'),
                ('regression-play','playmode','visual-regression-play','Lottery.G2.PlayMode.Tests;Lottery.G3.PlayMode.Tests')]
        for phase,platform,folder,assemblies in sets:
            expected=['unity-editor','-batchmode','-logFile','/dev/stdout','-projectPath','/github/workspace/tasks/lottery-shop/unity',
                '-coverageResultsPath','/github/workspace/CodeCoverage','-runTests','-testPlatform',platform,'-testResults',
                '/github/workspace/tasks/lottery-shop/artifacts/'+folder+'/'+platform+'-results.xml','-enableCodeCoverage','-debugCodeOptimization',
                '-coverageOptions','generateAdditionalMetrics;generateHtmlReport;generateBadgeReport;dontClear','-assemblyNames',assemblies]
            if phase!='regression-edit':expected+=['-force-glcore','-screen-width','1280','-screen-height','720']
            expected+=['-job-worker-count','2','-probeCommit','1'*40,'-probeRunId','12345']
            if phase=='capture':expected+=['-probeRunAttempt','1']
            self.assertEqual(safe.project_argv(phase,IDENT),expected)
            for forbidden in ('-quit','-nographics','-executeMethod'):self.assertNotIn(forbidden,expected)

    def test_native_both_streams_xml_and_secret_sentinels_never_echo(self):
        command="import os; os.write(1,b'<License>SYNTHETIC_PRIVATE</License>\\xff\\n');os.write(2,b'SYNTHETIC_PRIVATE\\n');print('SAFE_PROJECT_NATIVE_EXIT_CODE=2');raise SystemExit(2)"
        output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            code,scan=safe.private.captured([sys.executable,'-c',command],5,scan=safe.ProcessScan())
        self.assertEqual(code,2);self.assertEqual(scan.native_exit,2);self.assertEqual(scan.exit_markers,1);self.assertEqual(output.getvalue(),'');self.assertEqual(scan.carry,b'')

    def test_scanner_chunk_boundaries(self):
        data=safe.private.TOKENS['invalidLicenseXml400']+b'<License>SYNTHETIC_PRIVATE</License>\nSAFE_PROJECT_NATIVE_EXIT_CODE=1\n'
        scan=safe.ProcessScan()
        for byte in data:scan.feed(bytes([byte]))
        self.assertEqual(scan.native_exit,1);self.assertEqual(scan.exit_markers,1);self.assertEqual(scan.counts['invalidLicenseXml400'],1)

    def test_native_zero_with_abort_and_missing_marker_never_succeeds(self):
        for marker,aborted in [(None,False),(0,True)]:
            record=safe.process_receipt(IDENT,'capture')
            def captured(*args,**kwargs):
                scan=kwargs['scan'];scan.native_exit=marker;scan.exit_markers=0 if marker is None else 1;scan.counts['nativeActivationAborted']=int(aborted);return 0,scan
            with patch.object(safe.private,'captured',side_effect=captured):safe.native(IDENT,'synthetic',1,record)
            self.assertEqual(record['status'],'INCONSISTENT_NATIVE_RESULT')

    def test_later_timeout_preserves_native_observation_and_unknown_docker_exit(self):
        record=safe.process_receipt(IDENT,'capture')
        def captured(*args,**kwargs):
            scan=kwargs['scan'];scan.native_exit=1;scan.exit_markers=1;raise TimeoutError('SYNTHETIC_PRIVATE')
        with patch.object(safe.private,'captured',side_effect=captured):safe.native(IDENT,'synthetic',1,record)
        self.assertEqual(record['nativeExitCode'],1);self.assertIsNone(record['dockerExitCode']);self.assertEqual(record['status'],'PROCESS_TIMEOUT')
        self.assertNotIn('SYNTHETIC_PRIVATE',json.dumps(record))

    def test_workflow_exact_exports_and_no_raw_logging_actions(self):
        root=Path(__file__).resolve().parents[3];text=(root/safe.visual.WORKFLOW).read_text()
        self.assertNotIn('uses: game-ci/unity-test-runner@',text);self.assertEqual(text.count('secrets.'),3)
        self.assertIn('group: unity-personal-proof',text);self.assertIn('timeout-minutes: 75',text)
        self.assertIn('safe_project_ci.py finish',text);self.assertIn('safe_project_ci.py capture',text)
        self.assertNotIn('continue-on-error',text)
        self.assertIn('visual_candidate_ci.py tests --stage regression-edit',text);self.assertIn('visual_candidate_ci.py tests --stage regression-play',text)
        self.assertIn('visual_candidate_ci.py captures',text);self.assertIn('visual_candidate_ci.py snapshot-after',text)
        self.assertNotIn('*.log',text);self.assertNotIn('cat ',text);self.assertNotIn('*.xml',text)


class StartTests(unittest.TestCase):
    def test_one_private_container_and_one_activation_no_host_license_mount(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);upstream=root/'.visual-safe-upstream/dist/platforms/ubuntu';upstream.mkdir(parents=True)
            (upstream/'activate.sh').write_text(safe.private.NATIVE_COMMAND);(upstream/'return_license.sh').write_text(safe.RETURN_COMMAND)
            encoded=base64.b64encode(b'xxxxF0-0000-0000-0000-0000-0000').decode()
            calls=[]
            def captured(command,*args,**kwargs):
                calls.append(command)
                if 'run' in command:
                    self.assertIn('--log-driver=none',command);self.assertIn('--detach',command)
                    self.assertNotIn('UNITY_LICENSE',kwargs['env']);self.assertNotIn('synthetic-private',' '.join(command))
                    self.assertNotIn(':/root',' '.join(command));self.assertNotIn('/var/run/docker.sock',' '.join(command))
                return 0,safe.ProcessScan()
            def native(_ident,command,_seconds,record):
                self.assertEqual(command.count('unity-editor '),1);self.assertNotIn('-runTests',command)
                record.update(status='NATIVE_SUCCEEDED',nativeExitCode=0,dockerExitCode=0,nativeExitMarkerCount=1)
            with patch.object(safe.visual,'guard'),patch.object(safe,'identity',return_value=IDENT),patch.object(safe.private,'git',return_value=safe.private.PIN),patch.object(safe.private,'captured',side_effect=captured),patch.object(safe,'native',side_effect=native) as run,patch.dict(os.environ,dict(UNITY_LICENSE='<DeveloperData Value="'+encoded+'"/>',UNITY_EMAIL='synthetic@example.invalid',UNITY_PASSWORD='synthetic-private')),patch.object(safe.private,'cleanup') as cleanup:
                self.assertEqual(safe.start(root),0);run.assert_called_once();cleanup.assert_not_called()
                with self.assertRaises(ValueError):safe.start(root)
                self.assertEqual(run.call_count,1)
            self.assertEqual(len(calls),2);self.assertEqual(safe.session(root,IDENT)['status'],'READY')
            self.assertNotIn('synthetic-private',safe.file(root,'start').read_text())
    def test_first_activation_failure_blocks_and_cleans_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);upstream=root/'.visual-safe-upstream/dist/platforms/ubuntu';upstream.mkdir(parents=True)
            (upstream/'activate.sh').write_text(safe.private.NATIVE_COMMAND);(upstream/'return_license.sh').write_text(safe.RETURN_COMMAND)
            def failed(_ident,_command,_seconds,record):record.update(status='NATIVE_FAILED',nativeExitCode=1,dockerExitCode=1,nativeExitMarkerCount=1)
            with patch.object(safe.visual,'guard'),patch.object(safe,'identity',return_value=IDENT),patch.object(safe.private,'git',return_value=safe.private.PIN),patch.object(safe.private,'derive_serial',return_value='F0-0000-0000-0000-0000-0000'),patch.object(safe.private,'captured',return_value=(0,safe.ProcessScan())),patch.object(safe,'native',side_effect=failed) as run,patch.dict(os.environ,dict(UNITY_EMAIL='synthetic@example.invalid',UNITY_PASSWORD='synthetic-private')),patch.object(safe.private,'cleanup',return_value=dict(status='ABSENCE_VERIFIED',removalExitCode=0)) as cleanup:
                self.assertEqual(safe.start(root),1);run.assert_called_once();cleanup.assert_called_once_with('lottery-visual-safe-12345-1')
            self.assertEqual(safe.session(root,IDENT)['status'],'BLOCKED')


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.value=dict(IDENT,status='READY',activationSucceeded=True,stagesStarted=[],cleanup=None)
        safe.private.write(safe.file(self.root,'session'),self.value)
        self.ident=patch.object(safe,'identity',return_value=IDENT);self.ident.start()
        self.clean=patch.object(safe.private,'cleanup',return_value=dict(status='ABSENCE_VERIFIED',removalExitCode=0));self.cleanup=self.clean.start()
    def tearDown(self):self.ident.stop();self.clean.stop();self.temp.cleanup()
    @staticmethod
    def successful(_ident,_command,_seconds,record):record.update(status='NATIVE_SUCCEEDED',nativeExitCode=0,dockerExitCode=0,nativeExitMarkerCount=1)
    def test_failed_capture_keeps_regressions_runnable_but_capture_exit_is_failure(self):
        def failure(*args):args[3].update(status='NATIVE_FAILED',nativeExitCode=2,dockerExitCode=2,nativeExitMarkerCount=1)
        with patch.object(safe,'native',side_effect=failure):self.assertEqual(safe.test(self.root,'capture'),1)
        self.assertEqual(safe.session(self.root,IDENT)['status'],'READY');self.cleanup.assert_not_called()
        with patch.object(safe,'native',side_effect=self.successful):self.assertEqual(safe.test(self.root,'regression-edit'),0)
        self.assertEqual(json.loads(safe.file(self.root,'capture').read_text())['nativeExitCode'],2)
    def test_timeout_blocks_later_native_calls_and_cleans_owned_container(self):
        with patch.object(safe,'native',side_effect=lambda *a:a[3].update(status='PROCESS_TIMEOUT')):self.assertEqual(safe.test(self.root,'capture'),1)
        self.cleanup.assert_called_once_with('lottery-visual-safe-12345-1')
        with patch.object(safe,'native') as native:self.assertEqual(safe.test(self.root,'regression-edit'),1);native.assert_not_called()
    def test_phase_cannot_repeat_or_reactivate(self):
        with patch.object(safe,'native',side_effect=self.successful):self.assertEqual(safe.test(self.root,'capture'),0)
        with patch.object(safe,'native') as native:self.assertEqual(safe.test(self.root,'capture'),1);native.assert_not_called()
    def test_return_only_recorded_activated_session_and_separate_return_exit(self):
        def returned(*args):
            self.assertIn('-returnlicense',args[1]);args[3].update(status='NATIVE_FAILED',nativeExitCode=1,dockerExitCode=1,nativeExitMarkerCount=1)
        with patch.object(safe,'native',side_effect=returned):self.assertEqual(safe.finish(self.root),1)
        receipt=json.loads(safe.file(self.root,'finish').read_text());self.assertEqual(receipt['nativeExitCode'],1);self.assertEqual(receipt['returnStatus'],'NATIVE_FAILED');self.assertEqual(receipt['cleanup']['status'],'ABSENCE_VERIFIED')
    def test_unverified_or_blocked_session_never_returns_other_license(self):
        self.value['status']='BLOCKED';safe.private.write(safe.file(self.root,'session'),self.value)
        with patch.object(safe,'native') as native:self.assertEqual(safe.finish(self.root),1);native.assert_not_called()
        self.cleanup.assert_called_once_with('lottery-visual-safe-12345-1')
    def test_cleanup_failure_cannot_grant_success(self):
        self.cleanup.return_value=dict(status='ABSENCE_CHECK_FAILED',removalExitCode=1)
        with patch.object(safe,'native',side_effect=self.successful):self.assertEqual(safe.finish(self.root),1)
        self.assertEqual(json.loads(safe.file(self.root,'finish').read_text())['status'],'CLEANUP_NOT_VERIFIED')
    def test_wrong_attempt_session_rejected_before_native_action(self):
        self.value['runAttempt']='2';safe.private.write(safe.file(self.root,'session'),self.value)
        with patch.object(safe,'native') as native,self.assertRaises(ValueError):safe.test(self.root,'capture')
        native.assert_not_called()


if __name__=='__main__':unittest.main()
