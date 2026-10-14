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
                ('regression-play-core','playmode','visual-regression-play-core','Lottery.G2.PlayMode.Tests;Lottery.G3.PlayMode.Tests'),
                ('regression-play-world','playmode','visual-regression-world','Lottery.G2.PlayMode.Tests;Lottery.G3.PlayMode.Tests')]
        for phase,platform,folder,assemblies in sets:
            expected=['unity-editor','-batchmode','-logFile','/dev/stdout','-projectPath','/github/workspace/tasks/lottery-shop/unity',
                '-coverageResultsPath','/github/workspace/CodeCoverage','-runTests','-testPlatform',platform,'-testResults',
                '/github/workspace/tasks/lottery-shop/artifacts/'+folder+'/'+platform+'-results.xml','-enableCodeCoverage','-debugCodeOptimization',
                '-coverageOptions','generateAdditionalMetrics;generateHtmlReport;generateBadgeReport;dontClear','-assemblyNames',assemblies]
            if phase!='regression-edit':expected+=['-force-glcore','-screen-width','1280','-screen-height','720']
            expected+=['-job-worker-count','2','-probeCommit','1'*40,'-probeRunId','12345']
            if phase == 'capture' or phase in safe.split.PHASES.values():expected+=['-probeRunAttempt','1']
            if phase in safe.split.PHASES.values():
                shard=phase.removeprefix('regression-play-')
                expected+=['-g3RegressionProgress','1','-probeReviewedCommit','2'*40,'-g3RegressionShard',shard,'-testFilter',safe.split.selection(shard)]
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
        self.assertNotIn('uses: game-ci/unity-test-runner@',text);self.assertEqual(text.count('secrets.'),6)
        for key in ('UNITY_LICENSE','UNITY_EMAIL','UNITY_PASSWORD'):
            self.assertEqual(text.count('secrets.'+key),2)
        self.assertEqual(text.split('\n  android-diagnostic-candidate:',1)[0].count('secrets.'),3)
        self.assertIn('group: unity-personal-proof',text);self.assertIn('timeout-minutes: 75',text)
        self.assertIn('safe_project_ci.py finish',text);self.assertIn('safe_project_ci.py capture',text)
        self.assertNotIn('continue-on-error',text)
        self.assertIn('visual_candidate_ci.py tests --stage regression-edit',text);self.assertIn('visual_candidate_ci.py tests --stage regression-play-core',text);self.assertIn('visual_candidate_ci.py tests --stage regression-play-world',text)
        self.assertIn('visual_candidate_ci.py captures',text);self.assertIn('visual_candidate_ci.py snapshot-after',text)
        self.assertNotIn('*.log',text);self.assertNotIn('cat ',text);self.assertNotIn('*.xml',text)



class QuiescenceBoundaryTests(unittest.TestCase):
    def expected(self, ident=IDENT):
        return ('/lottery-visual-safe-'+ident['runId']+'-1|'+safe.private.IMAGE+'||false|true|true|'+'|'.join(ident[k] for k in safe.OWNER_FIELDS)+'\n').encode()
    def test_exact_metadata_then_bounded_stopper_no_secret_reads(self):
        calls=[]
        def captured(command,seconds,scan):
            calls.append((command,seconds))
            data=self.expected() if len(calls)==1 else safe.QUIESCENT_MARKER
            for byte in data:scan.feed(bytes([byte]))
            return 0,scan
        with patch.object(safe.private,'captured',side_effect=captured):self.assertTrue(safe.quiesce_owned(IDENT))
        self.assertEqual(calls[0],(['docker','inspect','--format',safe.OWNER_FORMAT,'lottery-visual-safe-12345-1'],10))
        self.assertEqual(calls[1],(['docker','exec','lottery-visual-safe-12345-1','/bin/bash','-c',safe.QUIESCE_COMMAND],15))
        for forbidden in ('.Env','cmdline','environ','UNITY_PASSWORD','returnlicense','docker run'):
            self.assertNotIn(forbidden,safe.OWNER_FORMAT+safe.QUIESCE_COMMAND)
        self.assertIn('count <= 4096',safe.QUIESCE_COMMAND);self.assertIn('attempt<20',safe.QUIESCE_COMMAND)
        self.assertIn('"$pid" == 1 || "$pid" == "$$"',safe.QUIESCE_COMMAND)
    def test_foreign_identity_image_pid_namespace_privilege_or_missing_container_never_executes(self):
        good=self.expected()
        bad=[good.replace(b'12345',b'54321'),good.replace(b'2'*40,b'3'*40),good.replace(b'||false|',b'|host|false|'),good.replace(b'|false|',b'|true|'),good.replace(b'|true|true|',b'|false|true|'),good.replace(b'|true|true|',b'|true|false|'),good.replace(safe.private.IMAGE.encode(),b'unknown'),good+b'EXTRA',good[:-1],b'']
        for data in bad:
            with self.subTest(data=data):
                def captured(command,seconds,scan):scan.feed(data);return 0,scan
                with patch.object(safe.private,'captured',side_effect=captured) as run:
                    self.assertFalse(safe.quiesce_owned(IDENT));run.assert_called_once()
        with patch.object(safe.private,'captured',side_effect=TimeoutError('PRIVATE')) as run:
            self.assertFalse(safe.quiesce_owned(IDENT));run.assert_called_once()
    def test_stop_requires_exact_marker_zero_exit_and_no_duplicate_or_raw_output(self):
        for data,code in [(b'',0),(safe.QUIESCENT_MARKER,1),(safe.QUIESCENT_MARKER*2,0),(safe.QUIESCENT_MARKER+b'PRIVATE',0)]:
            calls=[]
            def captured(command,seconds,scan):
                calls.append(command);scan.feed(self.expected() if len(calls)==1 else data);return (0 if len(calls)==1 else code),scan
            with patch.object(safe.private,'captured',side_effect=captured):self.assertFalse(safe.quiesce_owned(IDENT))
        for ident in (dict(IDENT,runId='12345;false'),dict(IDENT,runAttempt='2'),dict(IDENT,sourceCommit='HEAD')):
            with patch.object(safe.private,'captured') as run:self.assertFalse(safe.quiesce_owned(ident));run.assert_not_called()
    def test_stopper_control_flow_on_fake_proc_only_with_non_signalling_kill_stub(self):
        for mode in ('term','kill','stuck','malformed','foreign-init'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as d:
                root=Path(d);proc=root/'fakeproc';(proc/'1').mkdir(parents=True);(proc/'100').mkdir()
                (proc/'1/comm').write_text('other\n' if mode=='foreign-init' else 'sleep\n')
                (proc/'1/stat').write_text('1 (sleep) S 0 1\n')
                (proc/'100/stat').write_text('MALFORMED\n' if mode=='malformed' else '100 (owned worker) S 1 100\n')
                command=safe.QUIESCE_COMMAND.replace('/proc/',str(proc)+'/')
                self.assertNotIn('/proc/',command)
                # Every signal call is a function writing only fake stat data.
                stub='kill() { printf "%s:%s\\n" "$2" "$3" >> "$FAKE/signals"; if [[ "$MODE" == term || ( "$MODE" == kill && "$2" == KILL ) ]]; then printf "100 (owned worker) Z 1 100\\n" > "$FAKE/fakeproc/100/stat"; fi; }; sleep() { :; };\n'
                result=subprocess.run(['bash','--noprofile','--norc','-c',stub+command],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5,env={'PATH':'/usr/bin:/bin','FAKE':d,'MODE':mode})
                signals=(root/'signals').read_text() if (root/'signals').exists() else ''
                if mode in ('term','kill'):
                    self.assertEqual(result.returncode,0);self.assertEqual(result.stdout,safe.QUIESCENT_MARKER)
                    self.assertIn('TERM:100',signals)
                    if mode=='kill':self.assertIn('KILL:100',signals)
                else:self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,b'')
                self.assertNotIn(':1\n',signals)

    def test_stopper_shell_syntax_only_never_executes_on_host(self):
        result=subprocess.run(['bash','-n'],input=safe.QUIESCE_COMMAND.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
        self.assertEqual(result.returncode,0);self.assertEqual(result.stdout,b'')

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
            for key, field in zip(safe.OWNER_LABELS,safe.OWNER_FIELDS):self.assertIn(key+'='+IDENT[field],calls[1])
            self.assertNotIn('--pid',calls[1]);self.assertNotIn('--privileged',calls[1])
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
        self.stop=patch.object(safe,'quiesce_owned',return_value=True);self.quiesce=self.stop.start()
    def tearDown(self):self.ident.stop();self.clean.stop();self.stop.stop();self.temp.cleanup()
    @staticmethod
    def successful(_ident,_command,_seconds,record,_compiler_files=()):record.update(status='NATIVE_SUCCEEDED',nativeExitCode=0,dockerExitCode=0,nativeExitMarkerCount=1)
    def test_failed_capture_keeps_regressions_runnable_but_capture_exit_is_failure(self):
        def failure(*args):args[3].update(status='NATIVE_FAILED',nativeExitCode=2,dockerExitCode=2,nativeExitMarkerCount=1)
        with patch.object(safe,'native',side_effect=failure):self.assertEqual(safe.test(self.root,'capture'),1)
        self.assertEqual(safe.session(self.root,IDENT)['status'],'READY');self.cleanup.assert_not_called()
        with patch.object(safe,'native',side_effect=self.successful):self.assertEqual(safe.test(self.root,'regression-edit'),0)
        self.assertEqual(json.loads(safe.file(self.root,'capture').read_text())['nativeExitCode'],2)
    def test_timeout_stops_owned_processes_keeps_blocked_then_returns_once_and_cleans(self):
        with patch.object(safe,'native',side_effect=lambda *a:a[3].update(status='PROCESS_TIMEOUT')):self.assertEqual(safe.test(self.root,'capture'),1)
        self.cleanup.assert_not_called();self.quiesce.assert_called_once_with(IDENT)
        self.assertEqual(safe.session(self.root,IDENT)['status'],'BLOCKED')
        with patch.object(safe,'native') as native:self.assertEqual(safe.test(self.root,'regression-edit'),1);native.assert_not_called()
        def returned(*args):
            self.assertEqual(args[1],safe.shell(safe.RETURN_COMMAND));self.assertEqual(args[2],180)
            self.successful(*args)
        with patch.object(safe,'native',side_effect=returned) as native:
            self.assertEqual(safe.finish(self.root),0);native.assert_called_once()
        self.cleanup.assert_called_once_with('lottery-visual-safe-12345-1')
        self.assertEqual(safe.session(self.root,IDENT)['status'],'CLOSED')
        self.assertEqual(json.loads(safe.file(self.root,'capture').read_text())['status'],'PROCESS_TIMEOUT')
        with patch.object(safe,'native') as native:self.assertEqual(safe.finish(self.root),1);native.assert_not_called()

    def test_timeout_unproven_stop_removes_container_and_never_returns(self):
        self.quiesce.return_value=False
        with patch.object(safe,'native',side_effect=lambda *a:a[3].update(status='PROCESS_TIMEOUT')):self.assertEqual(safe.test(self.root,'capture'),1)
        self.cleanup.assert_called_once_with('lottery-visual-safe-12345-1')
        with patch.object(safe,'native') as native:self.assertEqual(safe.finish(self.root),1);native.assert_not_called()
        self.assertEqual(json.loads(safe.file(self.root,'finish').read_text())['returnStatus'],'RETURN_NOT_RUN_SESSION_BLOCKED')

    def test_blocked_return_failure_keeps_original_timeout_and_always_cleans(self):
        with patch.object(safe,'native',side_effect=lambda *a:a[3].update(status='PROCESS_TIMEOUT')):self.assertEqual(safe.test(self.root,'capture'),1)
        with patch.object(safe,'native',side_effect=lambda *a:a[3].update(status='PROCESS_TIMEOUT')):self.assertEqual(safe.finish(self.root),1)
        self.cleanup.assert_called_once();self.assertEqual(safe.session(self.root,IDENT)['status'],'CLOSED')
        self.assertEqual(json.loads(safe.file(self.root,'finish').read_text())['returnStatus'],'PROCESS_TIMEOUT')
        self.assertEqual(json.loads(safe.file(self.root,'capture').read_text())['status'],'PROCESS_TIMEOUT')

    def test_blocked_without_recorded_activation_never_returns(self):
        self.value.update(status='BLOCKED',activationSucceeded=False);safe.private.write(safe.file(self.root,'session'),self.value)
        with patch.object(safe,'native') as native:self.assertEqual(safe.finish(self.root),1);native.assert_not_called()
        self.cleanup.assert_called_once()
    def test_play_clears_only_fixed_old_progress_before_native_call(self):
        artifacts = self.root/safe.private.TASK/'artifacts/visual-regression-play-core'; artifacts.mkdir(parents=True)
        evidence = safe.visual.outdir(self.root); evidence.mkdir(parents=True, exist_ok=True)
        fixed = [artifacts/'test-progress.json', evidence/'regression-play-core-progress.json']
        for p in fixed: p.write_text('SYNTHETIC_OLD_ATTEMPT')
        sibling = artifacts/'unrelated.txt'; sibling.write_text('KEEP')
        def native(*args):
            self.assertTrue(all(not p.exists() for p in fixed)); self.assertEqual(sibling.read_text(), 'KEEP')
            self.assertEqual(args[2], 720); self.assertIn('-g3RegressionProgress 1', args[1])
            self.successful(*args)
        with patch.object(safe, 'native', side_effect=native), patch.object(safe.split, 'contract'): self.assertEqual(safe.test(self.root, 'regression-play-core'), 0)

    def test_world_clears_its_sidecar_but_preserves_core_evidence(self):
        artifacts=self.root/safe.private.TASK/'artifacts/visual-regression-world';artifacts.mkdir(parents=True)
        evidence=safe.visual.outdir(self.root);evidence.mkdir(parents=True,exist_ok=True)
        fixed=[artifacts/'world-progress.jsonl',evidence/'world-progress.json',artifacts/'test-progress.json',evidence/'regression-play-world-progress.json']
        for path in fixed:path.write_text('STALE')
        keep=evidence/'regression-play-core-progress.json';keep.write_text('CORE')
        def native(*args):
            self.assertTrue(all(not p.exists() for p in fixed));self.assertEqual(keep.read_text(),'CORE')
            self.assertIn('-g3RegressionShard world',args[1]);self.assertEqual(args[2],480);self.successful(*args)
        with patch.object(safe,'native',side_effect=native),patch.object(safe.split,'contract'):
            self.assertEqual(safe.test(self.root,'regression-play-world'),0)

    def test_phase_cannot_repeat_or_reactivate(self):
        with patch.object(safe,'native',side_effect=self.successful):self.assertEqual(safe.test(self.root,'capture'),0)
        with patch.object(safe,'native') as native:self.assertEqual(safe.test(self.root,'capture'),1);native.assert_not_called()
    def test_return_only_recorded_activated_session_and_separate_return_exit(self):
        def returned(*args):
            self.assertIn('-returnlicense',args[1]);args[3].update(status='NATIVE_FAILED',nativeExitCode=1,dockerExitCode=1,nativeExitMarkerCount=1)
        with patch.object(safe,'native',side_effect=returned):self.assertEqual(safe.finish(self.root),1)
        receipt=json.loads(safe.file(self.root,'finish').read_text());self.assertEqual(receipt['nativeExitCode'],1);self.assertEqual(receipt['returnStatus'],'NATIVE_FAILED');self.assertEqual(receipt['cleanup']['status'],'ABSENCE_VERIFIED')
    def test_unverified_blocked_session_never_returns_other_license(self):
        self.quiesce.return_value=False
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



class CompilerLocatorTests(unittest.TestCase):
    ASSET = 'Assets/G3/Runtime/G3SceneView.cs'
    EXPECTED = dict(code='CS1002', path=ASSET, line=12, column=7)
    LINE = ASSET.encode() + b'(12,7): error CS1002: SYNTHETIC_PRIVATE <License account="hidden"/>\n'

    def test_reviewed_tree_only_and_no_generated_unknown_paths(self):
        prefix = safe.private.TASK + '/unity/'
        paths = [prefix + self.ASSET, prefix + 'Assets/../private.cs', prefix + 'Assets/./private.cs',
                 prefix + 'Assets//private.cs', prefix + 'Assets/secret@example.cs', prefix + 'Assets/Other.txt',
                 'elsewhere/Assets/Hidden.cs', prefix + 'Assets/' + 'x'*250 + '.cs']
        with patch.object(safe.private, 'git', return_value='\n'.join(paths)) as git:
            self.assertEqual(safe.compiler_assets(Path('/synthetic'), IDENT), {self.ASSET})
        git.assert_called_once_with(Path('/synthetic'), 'ls-tree', '-r', '--name-only', '2'*40, '--', prefix + 'Assets')
        with patch.object(safe.private, 'git', side_effect=ValueError('SYNTHETIC_PRIVATE')):
            self.assertEqual(safe.compiler_assets(Path('/synthetic'), IDENT), set())

    def test_invalid_review_source_disables_locations_without_reading_other_commits(self):
        for commit in ('HEAD', '../private', 'secret@example.invalid', 'f'*41):
            with patch.object(safe.private, 'git') as git:
                self.assertEqual(safe.compiler_assets(Path('/synthetic'), dict(IDENT, reviewedCandidateCommit=commit)), set())
                git.assert_not_called()

    def test_metadata_cancel_does_not_start_native_and_retains_cancelled_cleanup(self):
        for error in (KeyboardInterrupt(), InterruptedError('SYNTHETIC_PRIVATE')):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                value = dict(IDENT, status='READY', activationSucceeded=True, stagesStarted=[], cleanup=None)
                safe.private.write(safe.file(root, 'session'), value)
                with patch.object(safe, 'identity', return_value=IDENT), patch.object(safe.private, 'git', side_effect=error), \
                     patch.object(safe, 'native') as native, patch.object(safe, 'quiesce_owned', return_value=False), \
                     patch.object(safe.private, 'cleanup', return_value=dict(status='ABSENCE_VERIFIED', removalExitCode=0)) as cleanup:
                    self.assertEqual(safe.test(root, 'capture'), 1)
                    native.assert_not_called(); cleanup.assert_called_once_with('lottery-visual-safe-12345-1')
                record = json.loads(safe.file(root, 'capture').read_text())
                self.assertEqual(record['status'], 'CANCELLED')
                self.assertEqual(record['cleanup']['status'], 'ABSENCE_VERIFIED')
                self.assertEqual(safe.session(root, IDENT)['status'], 'BLOCKED')
                self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(record))

    def test_output_limit_or_cancel_preserves_safe_prior_locations_without_raw_details(self):
        for error, status in [(ValueError('SYNTHETIC_PRIVATE'), 'OUTPUT_LIMIT_OR_INPUT_REJECTED'),
                              (InterruptedError('SYNTHETIC_PRIVATE'), 'CANCELLED')]:
            record = safe.process_receipt(IDENT, 'capture')
            def captured(*args, **kwargs):
                kwargs['scan'].feed(self.LINE)
                raise error
            with patch.object(safe.private, 'captured', side_effect=captured):
                safe.native(IDENT, 'synthetic', 1, record, [self.ASSET])
            self.assertEqual(record['compilerErrors'], [self.EXPECTED])
            self.assertEqual(record['status'], status); self.assertIsNone(record['dockerExitCode'])
            self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(record))

    def test_every_chunk_boundary_and_absolute_prefix(self):
        for data in (self.LINE, b'/github/workspace/tasks/lottery-shop/unity/' + self.LINE):
            for split in range(len(data)+1):
                scan = safe.ProcessScan([self.ASSET]); scan.feed(data[:split]); scan.feed(data[split:])
                self.assertEqual(scan.compiler_errors, [self.EXPECTED])
        scan = safe.ProcessScan([self.ASSET])
        for byte in self.LINE: scan.feed(bytes([byte]))
        self.assertEqual(scan.compiler_errors, [self.EXPECTED])

    def test_unknown_traversal_encoded_control_and_sensitive_path_baits_rejected(self):
        paths = [b'Assets/Unknown.cs', b'Assets/../G3/Runtime/G3SceneView.cs', b'Assets//G3/Runtime/G3SceneView.cs',
                 b'Assets/./G3/Runtime/G3SceneView.cs', b'Assets/%2e%2e/private.cs', b'Assets/G3/Runtime/secret@example.cs',
                 b'/root/.local/private.cs', b'C:\\private\\Assets\\G3SceneView.cs', b'Assets/G3/Runtime/\xff.cs',
                 b'Assets/G3/Runtime/G3SceneView.cs\x00', b'prefix Assets/G3/Runtime/G3SceneView.cs',
                 b'<license_xml>Assets/G3/Runtime/G3SceneView.cs']
        scan = safe.ProcessScan([self.ASSET])
        for path in paths: scan.feed(path + b'(12,7): error CS1002: SYNTHETIC_PRIVATE\n')
        self.assertEqual(scan.compiler_errors, [])

    def test_code_and_integer_fields_are_fixed_and_bounded(self):
        scan = safe.ProcessScan([self.ASSET])
        for suffix in (b'(0,7): error CS1002:', b'(-1,7): error CS1002:', b'(10000000,7): error CS1002:',
                       b'(12,7): error CS99999:', b'(12,7): error CSsecret:', b'(12,7): warning CS1002:',
                       b'(12,secret): error CS1002:'):
            scan.feed(self.ASSET.encode() + suffix + b' SYNTHETIC_PRIVATE\n')
        self.assertEqual(scan.compiler_errors, [])

    def test_overlong_prefix_and_forged_midline_header_rejected_and_resync(self):
        scan = safe.ProcessScan([self.ASSET])
        scan.feed(b'SYNTHETIC_PRIVATE' * 1000 + self.LINE)
        self.assertEqual(scan.compiler_errors, [])
        self.assertLessEqual(len(scan.compiler_prefix), safe.COMPILER_PREFIX_LIMIT)
        scan.feed(self.LINE); self.assertEqual(scan.compiler_errors, [self.EXPECTED])
        long_path = b'Assets/' + b'x'*600 + b'.cs(12,7): error CS1002:\n'
        scan.feed(long_path); self.assertEqual(scan.compiler_errors, [self.EXPECTED])

    def test_long_message_suffix_discarded_with_maximum_24_locations(self):
        scan = safe.ProcessScan([self.ASSET])
        scan.feed(self.LINE.rstrip(b'\n') + b'SYNTHETIC_PRIVATE'*1000)
        self.assertEqual(scan.compiler_errors, [self.EXPECTED]); self.assertEqual(scan.compiler_prefix, b'')
        scan.feed(b'\n' + self.LINE*40)
        self.assertEqual(len(scan.compiler_errors), 24)
        self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(scan.compiler_errors))
        self.assertEqual(set(scan.compiler_errors[0]), {'code','path','line','column'})

    def test_native_failure_and_timeout_preserve_only_locations_and_real_exit(self):
        for timeout in (False, True):
            record = safe.process_receipt(IDENT, 'capture')
            def captured(*args, **kwargs):
                scan = kwargs['scan']; scan.feed(self.LINE + b'SAFE_PROJECT_NATIVE_EXIT_CODE=1\n')
                if timeout: raise TimeoutError('SYNTHETIC_PRIVATE')
                return 1, scan
            with patch.object(safe.private, 'captured', side_effect=captured):
                safe.native(IDENT, 'synthetic', 1, record, [self.ASSET])
            self.assertEqual(record['compilerErrors'], [self.EXPECTED]); self.assertEqual(record['nativeExitCode'], 1)
            self.assertEqual(record['status'], 'PROCESS_TIMEOUT' if timeout else 'NATIVE_FAILED')
            self.assertEqual(record['dockerExitCode'], None if timeout else 1)
            self.assertNotIn('SYNTHETIC_PRIVATE', json.dumps(record))

    def test_compiler_signature_does_not_override_existing_exit_verdict_or_license_counts(self):
        record = safe.process_receipt(IDENT, 'capture')
        def captured(*args, **kwargs):
            scan = kwargs['scan']; scan.feed(self.LINE + b'SAFE_PROJECT_NATIVE_EXIT_CODE=0\n'); return 0, scan
        with patch.object(safe.private, 'captured', side_effect=captured):safe.native(IDENT, 'synthetic', 1, record, [self.ASSET])
        self.assertEqual(record['status'], 'NATIVE_SUCCEEDED')
        self.assertEqual(record['observations'], {k:0 for k in safe.private.TOKENS})
        self.assertEqual(record['compilerErrors'], [self.EXPECTED])
        scan = safe.ProcessScan([self.ASSET]); data = safe.private.TOKENS['invalidLicenseXml400'] + b'\n' + self.LINE
        for byte in data:scan.feed(bytes([byte]))
        self.assertEqual(scan.counts['invalidLicenseXml400'], 1);self.assertEqual(scan.compiler_errors, [self.EXPECTED])

    def test_both_process_streams_are_captured_without_raw_echo(self):
        command = 'import os;os.write(2,' + repr(self.LINE) + ');os.write(1,b"<license_xml>SYNTHETIC_PRIVATE</license_xml>\\n")'
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code, scan = safe.private.captured([sys.executable, '-c', command], 5, scan=safe.ProcessScan([self.ASSET]))
        self.assertEqual(code, 0);self.assertEqual(scan.compiler_errors, [self.EXPECTED]);self.assertEqual(output.getvalue(), '')

if __name__=='__main__':unittest.main()
