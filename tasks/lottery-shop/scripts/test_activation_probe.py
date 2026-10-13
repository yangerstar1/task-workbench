#!/usr/bin/env python3
"""Synthetic/local processes only. No Docker, Unity, real secret or activation."""
import base64
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import activation_probe as probe


class OutputTests(unittest.TestCase):
    def test_arbitrary_license_xml_both_streams_and_invalid_utf8_are_not_echoed(self):
        sentinel = 'SYNTHETIC_PRIVATE_PAYLOAD_DO_NOT_OUTPUT'
        child = "import os; os.write(1,b'[Licensing::Client] Error: Code 400 while processing request (status: license_xml is invalid.<License>" + sentinel + "</License>\\xff\\n'); os.write(2,b'" + sentinel + "\\n'); print('ACTIVATION_NATIVE_EXIT_CODE=1'); raise SystemExit(1)"
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code, scan = probe.captured([sys.executable, '-c', child], 5)
        self.assertEqual(out.getvalue(), '')
        self.assertEqual(code, 1); self.assertEqual(scan.native_exit, 1)
        self.assertEqual(scan.counts['invalidLicenseXml400'], 1)
        self.assertEqual(scan.carry, b'')
        self.assertNotIn(sentinel, json.dumps(scan.counts))

    def test_fixed_messages_across_chunks_count_once(self):
        data = probe.TOKENS['invalidLicenseXml400'] + b'<License>synthetic</License>\nACTIVATION_NATIVE_EXIT_CODE=0\n'
        for width in (1, 17, 1000):
            scan = probe.Scan()
            for i in range(0, len(data), width): scan.feed(data[i:i+width])
            self.assertEqual(scan.counts['invalidLicenseXml400'], 1)
            self.assertEqual(scan.native_exit, 0); self.assertEqual(scan.exit_markers, 1)

    def test_no_native_marker_is_unknown_even_for_docker_exit_125(self):
        code, scan = probe.captured([sys.executable, '-c', 'raise SystemExit(125)'], 5)
        self.assertEqual(code, 125); self.assertIsNone(scan.native_exit); self.assertEqual(scan.exit_markers, 0)

    def test_output_bound_and_timeout_never_dump_child_output(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            with patch.object(probe, 'MAX_OUTPUT', 32), self.assertRaises(ValueError):
                probe.captured([sys.executable, '-c', "print('synthetic-private'*100)"], 5)
            with self.assertRaises(TimeoutError):
                probe.captured([sys.executable, '-c', "import time; print('synthetic-private',flush=True); time.sleep(3)"], .1)
        self.assertEqual(out.getvalue(), '')

    def test_missing_executable_exception_is_never_interpreted_as_native_exit(self):
        with self.assertRaises(FileNotFoundError): probe.captured(['/nonexistent-synthetic-executable'], 1)

    def test_serial_conversion_matches_pinned_mechanism_without_real_credentials(self):
        serial = 'F0-0000-0000-0000-0000-0000'
        encoded = base64.b64encode(('xxxx' + serial).encode()).decode()
        self.assertEqual(probe.derive_serial('<DeveloperData Value="' + encoded + '"/>'), serial)
        for bad in ('', '<License>synthetic-private</License>', '<DeveloperData Value="bm90LWEta2V5"/>'):
            with self.assertRaises(ValueError) as error: probe.derive_serial(bad)
            self.assertNotIn(bad, str(error.exception)) if bad else None

    def test_static_workflow_scope_no_project_run_or_raw_upload(self):
        root = Path(__file__).resolve().parents[3]
        workflow = (root / probe.WORKFLOW).read_text()
        self.assertIn('group: unity-personal-proof', workflow)
        self.assertIn('paths: [tasks/lottery-shop/ci/activation-probe-request.json]', workflow)
        self.assertIn(probe.PIN, workflow)
        self.assertEqual(workflow.count('secrets.'), 3)
        self.assertNotIn('uses: game-ci/', workflow)
        self.assertNotIn('workflow_dispatch', workflow)
        upload = workflow.split('name: Preserve only fixed', 1)[1]
        self.assertNotIn('.log', upload); self.assertNotIn('.activation-upstream', upload)
        self.assertNotIn('run_tests', probe.SHELL); self.assertNotIn('return_license', probe.SHELL)
        self.assertEqual(probe.SHELL.count('unity-editor '), 1)
        self.assertNotIn('while ', probe.SHELL)
        self.assertIn('exit "$code"', probe.SHELL)


class DiagnosticTests(unittest.TestCase):
    def scenario(self, docker_code=0, native_code=0, error=None, cleanup_status="ABSENCE_VERIFIED", contradiction=None, observed_before_error=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); upstream=root/'.activation-upstream/dist/platforms/ubuntu';upstream.mkdir(parents=True)
            (upstream/'activate.sh').write_text(probe.NATIVE_COMMAND)
            ident=dict(scope=probe.SCOPE,sourceCommit='1'*40,reviewedCandidateCommit='2'*40,runId='12345',runAttempt='1')
            scan=probe.Scan();scan.counts['entitlementActivated']=1;scan.native_exit=native_code;scan.exit_markers=0 if native_code is None else 1
            if contradiction: scan.counts[contradiction]=1
            serial='F0-0000-0000-0000-0000-0000';encoded=base64.b64encode(('xxxx'+serial).encode()).decode()
            env=dict(UNITY_LICENSE='<DeveloperData Value="'+encoded+'"/>',UNITY_EMAIL='synthetic@example.invalid',UNITY_PASSWORD='synthetic-private-password')
            calls=[]
            def captured(command, timeout, env=None, scan=None):
                calls.append(command)
                if len(calls)==1:return (0,probe.Scan())
                self.assertNotIn(serial,' '.join(command));self.assertNotIn('synthetic-private-password',' '.join(command))
                self.assertNotIn('UNITY_LICENSE',env)
                if error is not None:
                    if observed_before_error:
                        scan.native_exit=native_code;scan.exit_markers=1;scan.counts["nativeActivationAborted"]=1
                    raise error
                return docker_code, result_scan
            result_scan=scan;output=io.StringIO()
            with patch.object(probe,'guard',return_value=ident),patch.object(probe,'git',return_value=probe.PIN),patch.object(probe,'captured',side_effect=captured),patch.object(probe,'cleanup',return_value=dict(status=cleanup_status,removalExitCode=0)) as clean,patch.dict(os.environ,env),contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
                code=probe.diagnose(root)
            clean.assert_called_once_with('lottery-activation-12345-1')
            receipt=json.loads((probe.evidence(root)/'activation-receipt.json').read_text())
            self.assertEqual(len(calls),2);self.assertIn('--log-driver=none',calls[1]);self.assertEqual(output.getvalue(),'ACTIVATION_DIAGNOSTIC_RECEIPT_WRITTEN\n')
            self.assertNotIn('synthetic-private',json.dumps(receipt))
            return code,receipt

    def test_real_nonzero_exit_overrides_entitlement_success_text(self):
        code,r=self.scenario(1,1);self.assertEqual(code,1);self.assertEqual(r['status'],'ACTIVATION_FAILED');self.assertEqual(r['nativeExitCode'],1)
    def test_native_marker_missing_never_grants_success_or_invents_native_exit(self):
        for code in (0,125):
            result,r=self.scenario(code,None);self.assertEqual(result,1);self.assertIsNone(r['nativeExitCode']);self.assertEqual(r['dockerExitCode'],code)
    def test_zero_native_and_process_exit_only_grants_activation_not_game_pass(self):
        code,r=self.scenario();self.assertEqual(code,0);self.assertEqual(r['status'],'ACTIVATION_SUCCEEDED_ONLY');self.assertEqual(r['gameTests'],'NOT_RUN')
    def test_zero_exit_with_explicit_native_failure_is_inconsistent_not_success(self):
        for observation in ('invalidLicenseXml400','nativeActivationAborted'):
            code,r=self.scenario(contradiction=observation);self.assertEqual(code,1);self.assertEqual(r['status'],'INCONSISTENT_NATIVE_RESULT')
    def test_cleanup_not_verified_cannot_pass_even_if_activation_succeeded(self):
        for status in ('ABSENCE_CHECK_FAILED','CONTAINER_STILL_PRESENT','CLEANUP_TIMEOUT','CLEANUP_FAILED'):
            code,r=self.scenario(cleanup_status=status);self.assertEqual(code,1);self.assertEqual(r['status'],'CLEANUP_NOT_VERIFIED');self.assertEqual(r['activationStatus'],'ACTIVATION_SUCCEEDED_ONLY')
    def test_later_timeout_retains_observed_native_marker_but_unknown_process_exit(self):
        code,r=self.scenario(native_code=1,error=TimeoutError('synthetic-private'),observed_before_error=True)
        self.assertEqual(code,1);self.assertEqual(r['status'],'PROCESS_TIMEOUT');self.assertEqual(r['nativeExitCode'],1);self.assertEqual(r['nativeExitMarkerCount'],1);self.assertIsNone(r['dockerExitCode']);self.assertEqual(r['observations']['nativeActivationAborted'],1)
    def test_timeout_cancel_and_arbitrary_exception_still_cleanup_without_dump(self):
        for error,status in ((TimeoutError('synthetic-private'),'PROCESS_TIMEOUT'),(InterruptedError('synthetic-private'),'CANCELLED'),(RuntimeError('synthetic-private'),'ADAPTER_FAILED')):
            code,r=self.scenario(error=error);self.assertEqual(code,1);self.assertEqual(r['status'],status);self.assertIsNone(r['nativeExitCode'])


class CleanupTests(unittest.TestCase):
    def test_already_removed_is_success_only_when_absence_query_succeeds(self):
        commands=[]
        def run(command,**kwargs):
            commands.append(command);self.assertEqual(kwargs['stderr'],subprocess.DEVNULL)
            return subprocess.CompletedProcess(command,1 if len(commands)==1 else 0,stdout=b'')
        with patch.object(probe.subprocess,'run',side_effect=run): result=probe.cleanup('lottery-activation-12345-1')
        self.assertEqual(result,dict(status='ABSENCE_VERIFIED',removalExitCode=1))
        self.assertIn('name=^/lottery-activation-12345-1$',commands[1]);self.assertEqual(commands[0],['docker','rm','--force','lottery-activation-12345-1'])
    def test_present_unknown_and_exception_cleanup_results_fail_closed(self):
        for query,status in ((subprocess.CompletedProcess([],0,stdout=b'lottery-activation-12345-1\n'),'CONTAINER_STILL_PRESENT'),(subprocess.CompletedProcess([],1,stdout=b'synthetic-private'),'ABSENCE_CHECK_FAILED'),(RuntimeError('synthetic-private'),'CLEANUP_FAILED'),(subprocess.TimeoutExpired('synthetic-private',20),'CLEANUP_TIMEOUT')):
            with patch.object(probe.subprocess,'run',side_effect=[subprocess.CompletedProcess([],0),query]): result=probe.cleanup('lottery-activation-12345-1')
            self.assertEqual(result['status'],status);self.assertNotIn('synthetic-private',json.dumps(result))


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        def git(*args): subprocess.run(['git', '-C', str(self.root), *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.git = git; git('init'); git('config', 'user.email', 'fixture@example.invalid'); git('config', 'user.name', 'synthetic fixture')
        (self.root/'base').write_text('source'); git('add', '.'); git('commit', '-m', 'reviewed source')
        self.source = probe.git(self.root,'rev-parse','HEAD')
        self.request = dict(schemaVersion=1, requestId='lottery-activation-20261013-01', sourceCommit=self.source, purpose=probe.SCOPE,
            sourceReview=dict(sourceCommit=self.source,status='APPROVED_FOR_ACTIVATION_DIAGNOSTIC_ONLY',reviewer='independent-source-review',reviewId='activation-source-20261013-01',reviewedAtUtc='2026-10-13T00:00:00Z'))
        probe.write(self.root/probe.REQUEST,self.request); git('add','.'); git('commit','-m','request only')
        self.head=probe.git(self.root,'rev-parse','HEAD'); event=self.root/'event.json';probe.write(event,dict(repository=dict(private=False,fork=False),deleted=False))
        self.env=dict(GITHUB_EVENT_NAME='push',GITHUB_REPOSITORY='yangerstar1/task-workbench',GITHUB_REPOSITORY_OWNER='yangerstar1',GITHUB_ACTOR='yangerstar1',GITHUB_TRIGGERING_ACTOR='yangerstar1',GITHUB_REF='refs/heads/lottery-shop-g0-20261011',GITHUB_SHA=self.head,GITHUB_EVENT_PATH=str(event),GITHUB_RUN_ID='12345',GITHUB_RUN_ATTEMPT='1')
    def tearDown(self): self.temp.cleanup()
    def test_exact_reviewed_request_only_child(self):
        with patch.dict(os.environ,self.env): result=probe.guard(self.root)
        self.assertEqual(result['sourceCommit'],self.head);self.assertEqual(result['reviewedCandidateCommit'],self.source)
    def test_actor_source_and_rerun_rejected(self):
        for key,value in [('GITHUB_ACTOR','other'),('GITHUB_SHA','f'*40),('GITHUB_RUN_ATTEMPT','2')]:
            with self.subTest(key=key),patch.dict(os.environ,dict(self.env,**{key:value})),self.assertRaises(ValueError):probe.guard(self.root)
    def test_wrong_review_and_unreviewed_source_rejected(self):
        for key,value in [('status','APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY'),('sourceCommit','f'*40)]:
            request=json.loads(json.dumps(self.request));request['sourceReview'][key]=value;probe.write(self.root/probe.REQUEST,request)
            with self.subTest(key=key),patch.dict(os.environ,self.env),self.assertRaises(ValueError):probe.guard(self.root)
    def test_changed_additional_source_file_rejected(self):
        (self.root/'other').write_text('unreviewed');self.git('add','.');self.git('commit','--amend','--no-edit')
        self.env['GITHUB_SHA']=probe.git(self.root,'rev-parse','HEAD')
        with patch.dict(os.environ,self.env),self.assertRaises(ValueError):probe.guard(self.root)


if __name__=='__main__':unittest.main()
