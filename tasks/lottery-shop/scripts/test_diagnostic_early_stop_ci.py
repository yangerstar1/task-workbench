#!/usr/bin/env python3
"""Synthetic scheduling/ownership models only, never native or skipped-test passes."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import diagnostic_early_stop_ci as decision

v = decision.visual
s = decision.safe
IDENT = dict(scope=v.SCOPE,sourceCommit='1'*40,reviewedCandidateCommit='2'*40,runId='123',runAttempt='1',requestId='lottery-visual-20261013-99',g3Gate='NOT_EVALUATED',deviceQa='NOT_RUN',sourceReview=dict(sourceCommit='2'*40,status='APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY',reviewer='independent-source-review',reviewId='visual-source-20261013-99',reviewedAtUtc='2026-10-13T01:00:00Z'))


def request(profile=v.EARLY_STOP):
    return dict(schemaVersion=2,requestId=IDENT['requestId'],sourceCommit=IDENT['reviewedCandidateCommit'],purpose=v.SCOPE,sourceReview=IDENT['sourceReview'],executionProfile=profile)


def evidence():
    capture=s.process_receipt(IDENT,'capture');capture.update(status='NATIVE_FAILED',nativeExitCode=3,dockerExitCode=3,nativeExitMarkerCount=1,elapsedMs=250000,recordedAtUtc='2026-10-13T02:00:00Z')
    session=dict(IDENT,status='READY',activationSucceeded=True,stagesStarted=['capture'],cleanup=None)
    events=[dict(stage=stage,utc='2026-10-13T02:00:00Z',elapsedMs=i,inputUpdates=0,frameCount=0,purchased=-1,settled=-1,dayPhase='UNAVAILABLE') for i,stage in enumerate(decision.FAILED_PREBUILD)]
    progress=dict(schemaVersion=1,scope=v.SCOPE,kind='prebuild',sourceCommit=IDENT['sourceCommit'],runId='123',runAttempt='1',status='MILESTONES_ONLY_NOT_TEST_PASS',events=events)
    events=[]
    for i,stage in enumerate(['ARMED','ERROR_LOG','QUITTING']):
        events.append(dict(stage=stage,origin='PREBUILD_SETUP' if i==1 else 'NONE',code='PREBUILD_SETUP' if i==1 else 'NONE',exceptionKind='NONE',elapsedMs=i,errorCount=0 if i==0 else 1,assertCount=0,exceptionCount=0,utfErrorCount=0,isPlaying=False,isPlayingOrWillChangePlaymode=False,isCompiling=False,isUpdating=False))
    started=dict(schemaVersion=1,scope=decision.startup.SCOPE,status=decision.startup.STATUS,sourceCommit=IDENT['sourceCommit'],runId='123',runAttempt='1',startedUtc='2026-10-13T02:00:00Z',diagnosticWriteFailed=False,eventLimitReached=False,errorCount=1,assertCount=0,exceptionCount=0,utfErrorCount=0,events=events)
    return [capture,session,progress,started]


class RequestTests(unittest.TestCase):
    def test_legacy_is_full_and_v2_both_explicit_profiles(self):
        a=request();a.pop('executionProfile');a['schemaVersion']=1
        self.assertEqual(v.request_profile(a),v.FULL_DIAGNOSTIC)
        for profile in (v.EARLY_STOP,v.FULL_DIAGNOSTIC):self.assertEqual(v.request_profile(request(profile)),profile)

    def test_closed_schema_no_implicit_truthy_selector(self):
        values=[dict(request(),extra=True),dict(request(),schemaVersion=True),dict(request(),schemaVersion=3)]
        for value in ('true',True,1,None,'early_stop_on_prebuild_failure','G3_PASS'):
            values.append(request(value))
        a=request();a.pop('executionProfile');values.append(a)
        a=request();a['schemaVersion']=1;values.append(a)
        for value in values:
            with self.subTest(value=value),self.assertRaises(ValueError):v.request_profile(value)

    def test_request_reader_rejects_duplicate_keys_and_oversize(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'request.json';raw=json.dumps(request())
            for bad in (raw.replace('"schemaVersion": 2','"schemaVersion": 2, "schemaVersion": 2'),raw.replace('"executionProfile":','"executionProfile": "FULL_DIAGNOSTIC", "executionProfile":'),' '*8193):
                path.write_text(bad)
                with self.assertRaises(ValueError):v.read_diagnostic_request(path)

    def test_v2_guard_retains_actor_review_and_direct_parent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def git(*args):return subprocess.check_output(['git','-C',d,*args],stderr=subprocess.DEVNULL).decode().strip()
            git('init');git('config','user.name','Synthetic');git('config','user.email','synthetic@example.invalid')
            (root/'source').write_text('synthetic');git('add','.');git('commit','-m','source');source=git('rev-parse','HEAD')
            r=request();r['sourceCommit']=source;r['sourceReview']=dict(r['sourceReview'],sourceCommit=source)
            v.write(root/v.REQUEST,r);git('add','.');git('commit','-m','request')
            event=root/'event.json';event.write_text(json.dumps(dict(repository=dict(private=False,fork=False),deleted=False)))
            env=dict(GITHUB_EVENT_NAME='push',GITHUB_REPOSITORY='yangerstar1/task-workbench',GITHUB_REPOSITORY_OWNER='yangerstar1',GITHUB_ACTOR='yangerstar1',GITHUB_TRIGGERING_ACTOR='yangerstar1',GITHUB_REF='refs/heads/lottery-shop-g0-20261011',GITHUB_SHA=git('rev-parse','HEAD'),GITHUB_EVENT_PATH=str(event),GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1')
            with patch.dict(os.environ,env):
                self.assertEqual(v.guard(root)['reviewedCandidateCommit'],source)
                r['executionProfile']='G3_PASS';v.write(root/v.REQUEST,r)
                with self.assertRaises(ValueError):v.guard(root)


class ProofTests(unittest.TestCase):
    def test_exact_proven_failed_prebuild(self):self.assertTrue(decision.eligible(IDENT,*evidence(),False))

    def test_source_run_attempt_mismatch_in_every_proof(self):
        for index in range(4):
            for key,value in [('sourceCommit','3'*40),('runId','456'),('runAttempt','2')]:
                inputs=evidence();inputs[index][key]=value
                with self.subTest(index=index,key=key),self.assertRaises(ValueError):decision.eligible(IDENT,*inputs,False)

    def test_capture_success_timeout_bad_exit_license_compiler_and_unknown_fields(self):
        changes=[('status','NATIVE_SUCCEEDED'),('status','PROCESS_TIMEOUT'),('nativeExitCode',0),('nativeExitCode',True),('dockerExitCode',2),('nativeExitMarkerCount',2),('compilerErrors',[{}]),('cleanup',{}),('unknown','SECRET'),('image','other')]
        for key,value in changes:
            inputs=evidence();inputs[0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):decision.eligible(IDENT,*inputs,False)
        for key in ('invalidLicenseXml400','nativeActivationAborted'):
            inputs=evidence();inputs[0]['observations'][key]=1
            with self.assertRaises(ValueError):decision.eligible(IDENT,*inputs,False)

    def test_session_not_ready_not_activated_repeated_or_other_phase(self):
        for key,value in [('status','BLOCKED'),('status','CLOSED'),('activationSucceeded',False),('activationSucceeded',1),('stagesStarted',[]),('stagesStarted',['capture','regression-edit']),('cleanup',{})]:
            inputs=evidence();inputs[1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):decision.eligible(IDENT,*inputs,False)

    def test_missing_duplicate_reordered_success_or_runtime_prebuild_milestones(self):
        mutations=[lambda e:e.pop(),lambda e:e.append(e[-1]),lambda e:e.reverse(),lambda e:e[5].update(stage='prebuild-prepare-passed'),lambda e:e[-1].update(stage='prebuild-end'),lambda e:e[0].update(frameCount=1),lambda e:e[0].update(inputUpdates=1)]
        for mutate in mutations:
            inputs=evidence();mutate(inputs[2]['events'])
            with self.assertRaises(ValueError):decision.eligible(IDENT,*inputs,False)

    def test_startup_incomplete_or_entered_play_cannot_skip(self):
        for key in ('diagnosticWriteFailed','eventLimitReached'):
            inputs=evidence();inputs[3][key]=True
            with self.assertRaises(ValueError):decision.eligible(IDENT,*inputs,False)
        for stage in ('PREBUILD_RETURNED','UTF_RUN_STARTED','BEFORE_RELOAD','DOMAIN_RESTORED','EXITING_EDIT_MODE','ENTERED_PLAY_MODE'):
            inputs=evidence();inputs[3]['events'][1]['stage']=stage
            with self.subTest(stage=stage),self.assertRaises(ValueError):decision.eligible(IDENT,*inputs,False)
        for flag in ('isPlaying','isPlayingOrWillChangePlaymode'):
            inputs=evidence();inputs[3]['events'][1][flag]=True
            with self.assertRaises(ValueError):decision.eligible(IDENT,*inputs,False)
        inputs=evidence();inputs[3]['events'].pop()
        with self.assertRaises(ValueError):decision.eligible(IDENT,*inputs,False)
        with self.assertRaises(ValueError):decision.eligible(IDENT,*evidence(),True)


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.folder=self.root/v.TASK/'artifacts/visual-candidate';self.output=self.root/'outputs'
        self.env=patch.dict(os.environ,dict(GITHUB_SHA=IDENT['sourceCommit'],GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1',GITHUB_OUTPUT=str(self.output)));self.env.start();self.addCleanup(self.env.stop)
        self.ident=patch.object(v,'identity',return_value=IDENT);self.ident.start();self.addCleanup(self.ident.stop)
        self.req=request();v.write(self.root/v.REQUEST,self.req)
        self.git=patch.object(v,'git',side_effect=lambda *args:json.dumps(self.req,indent=2,sort_keys=True));self.git.start();self.addCleanup(self.git.stop)
        for name,value in zip(['safe-capture.json','safe-session.json','prebuild-progress.json','startup-progress.json'],evidence()):
            v.write((v.outdir(self.root) if name.startswith('safe-') else self.folder)/name,value)

    def decide(self):return decision.decide(self.root)
    def required(self):
        receipt=self.decide();self.assertEqual(receipt['status'],'REGRESSIONS_REQUIRED');self.assertEqual(self.output.read_text().splitlines()[-1],'skip_regressions=false');return receipt

    def test_skip_receipt_is_not_run_never_fake_safe_or_test_results(self):
        result=self.decide();self.assertEqual(result['status'],'SKIP_REQUESTED');self.assertEqual(result['regressionEdit'],'SKIP_REQUESTED');self.assertEqual(result['regressionPlay'],'SKIP_REQUESTED');self.assertEqual(self.output.read_text(),'skip_regressions=true\n')
        self.assertEqual(set(result),{'schemaVersion','scope','status','reason','sourceCommit','reviewedCandidateCommit','runId','runAttempt','requestId','regressionEdit','regressionPlay','g3Gate','captureVerdict','evidenceSha256'})
        self.assertFalse(list(self.root.rglob('*regression*xml')));self.assertFalse((v.outdir(self.root)/'safe-regression-edit.json').exists());self.assertFalse((v.outdir(self.root)/'safe-regression-play.json').exists())

    def test_not_run_requires_both_actual_skips_and_successful_decision(self):
        self.decide()
        env=dict(DECISION_OUTCOME='success',DECISION_SKIP='true',REGRESSION_EDIT_OUTCOME='skipped',REGRESSION_PLAY_OUTCOME='skipped')
        with patch.dict(os.environ,env):
            final=decision.finalize_not_run(self.root)
            self.assertEqual(final['status'],'REGRESSIONS_NOT_RUN');self.assertEqual(final['regressionEdit'],'NOT_RUN');self.assertEqual(final['regressionPlay'],'NOT_RUN')
            for key in env:
                for bad in ('', 'failure', 'success' if key.startswith('REGRESSION_') else 'skipped'):
                    with patch.dict(os.environ,{key:bad}),self.assertRaises(ValueError):decision.finalize_not_run(self.root)
        self.assertNotIn('expectedCases',final)

    def test_not_run_cannot_use_full_profile_or_wrong_run_decision(self):
        env=dict(DECISION_OUTCOME='success',DECISION_SKIP='true',REGRESSION_EDIT_OUTCOME='skipped',REGRESSION_PLAY_OUTCOME='skipped')
        with patch.dict(os.environ,env):
            self.req['executionProfile']=v.FULL_DIAGNOSTIC;v.write(self.root/v.REQUEST,self.req);self.decide()
            with self.assertRaises(ValueError):decision.finalize_not_run(self.root)
            self.req=request();v.write(self.root/v.REQUEST,self.req);self.decide()
            path=v.outdir(self.root)/decision.NAME;value=json.loads(path.read_text());value['runId']='456';v.write(path,value)
            with self.assertRaises(ValueError):decision.finalize_not_run(self.root)

    def test_both_full_profiles_default_to_run(self):
        self.req['executionProfile']=v.FULL_DIAGNOSTIC;v.write(self.root/v.REQUEST,self.req);self.required()
        self.req.pop('executionProfile');self.req['schemaVersion']=1;v.write(self.root/v.REQUEST,self.req);self.required()

    def test_selector_tampering_unknown_or_no_source_binding_runs(self):
        for key,value in [('executionProfile','UNKNOWN'),('sourceCommit','4'*40),('purpose','FORMAL_G3'),('requestId','different')]:
            self.req=request();self.req[key]=value;v.write(self.root/v.REQUEST,self.req);self.required()
        self.req=request();v.write(self.root/v.REQUEST,self.req)
        with patch.object(v,'git',return_value='different committed bytes'):self.required()

    def test_each_missing_proof_defaults_to_run(self):
        for path in [v.outdir(self.root)/'safe-capture.json',v.outdir(self.root)/'safe-session.json',self.folder/'prebuild-progress.json',self.folder/'startup-progress.json']:
            data=path.read_bytes();path.unlink();self.required();path.write_bytes(data)

    def test_bad_json_duplicate_keys_over_bound_or_secret_not_exported(self):
        path=self.folder/'prebuild-progress.json';original=path.read_bytes()
        for raw in [b'not json SECRET',original.replace(b'"schemaVersion": 1',b'"schemaVersion": 1, "schemaVersion": 1'),b' '*65537]:
            path.write_bytes(raw);receipt=self.required();self.assertNotIn('SECRET',json.dumps(receipt))

    def test_each_runtime_file_presence_or_symlink_disallows_skip(self):
        for path in [self.folder/'runtime-progress.json',self.folder/'lifecycle-progress.json',self.folder/'captures/capture-receipt.json']:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}');self.required();path.unlink()
            path.symlink_to(self.root/'nonexistent');self.required();path.unlink()

    def test_proof_symlink_disallows_skip(self):
        path=self.folder/'prebuild-progress.json';target=self.root/'same-content';target.write_bytes(path.read_bytes());path.unlink();path.symlink_to(target);self.required()

    def test_receipt_write_failure_cannot_publish_skip(self):
        with patch.object(v,'write',side_effect=OSError('SYNTHETIC_WRITE_FAILURE')),self.assertRaises(OSError):self.decide()
        self.assertFalse(self.output.exists())

    def test_output_write_failure_is_step_failure(self):
        self.output.mkdir()
        with self.assertRaises(OSError):self.decide()
        self.assertEqual(json.loads((v.outdir(self.root)/decision.NAME).read_text())['status'],'SKIP_REQUESTED')
        # Workflow additionally requires successful step outcome, so this intent
        # receipt cannot cause an actual skip or claim tests ran.


class LifecycleWorkflowTests(unittest.TestCase):
    def test_capture_failure_can_finish_directly_without_regression_and_remains_failed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);s.private.write(s.file(root,'session'),dict(IDENT,status='READY',activationSucceeded=True,stagesStarted=[],cleanup=None))
            def failed(*args):args[3].update(status='NATIVE_FAILED',nativeExitCode=3,dockerExitCode=3,nativeExitMarkerCount=1)
            def returned(*args):self.assertIn('-returnlicense',args[1]);args[3].update(status='NATIVE_SUCCEEDED',nativeExitCode=0,dockerExitCode=0,nativeExitMarkerCount=1)
            with patch.object(s,'identity',return_value=IDENT),patch.object(s.private,'cleanup',return_value=dict(status='ABSENCE_VERIFIED')) as clean:
                with patch.object(s,'native',side_effect=failed):self.assertEqual(s.test(root,'capture'),1)
                clean.assert_not_called()
                with patch.object(s,'native',side_effect=returned) as native:self.assertEqual(s.finish(root),0);native.assert_called_once()
                clean.assert_called_once();self.assertEqual(s.session(root,IDENT)['stagesStarted'],['capture']);self.assertEqual(s.session(root,IDENT)['status'],'CLOSED');self.assertEqual(json.loads(s.file(root,'capture').read_text())['status'],'NATIVE_FAILED')

    def test_truth_table_missing_failed_cancelled_decision_never_skips(self):
        for outcome in ('success','failure','skipped','cancelled',''):
            for output in ('true','false',''):
                run=not(outcome=='success' and output=='true')
                self.assertEqual(run,(outcome,output)!=('success','true'))

    def test_workflow_keeps_finish_independent_and_original_timeouts(self):
        root=Path(__file__).resolve().parents[3];workflow=(root/v.WORKFLOW).read_text()
        condition="&& !(steps.regressiondecision.outcome == 'success' && steps.regressiondecision.outputs.skip_regressions == 'true')"
        self.assertEqual(workflow.count(condition),3)
        for step in ('regressionedit','prepareoriginal','regressionplay'):
            section=workflow.split('        id: '+step+'\n',1)[1].split('      - name:',1)[0];self.assertIn(condition,section);self.assertIn('always()',section)
        finish=workflow.split('      - name: Return only this temporary session',1)[1].split('      - name:',1)[0]
        self.assertIn("always() && steps.guard.outcome == 'success' && steps.safestart.outcome != 'skipped'",finish);self.assertNotIn('regressiondecision',finish);self.assertIn('safe_project_ci.py finish',finish)
        self.assertNotIn('continue-on-error:',workflow);self.assertEqual(len(v.FRAMES),23);self.assertEqual(s.PHASES['regression-edit'][3],480);self.assertEqual(s.PHASES['regression-play'][3],480);self.assertEqual(s.PHASES['capture'][3],1800)


if __name__=='__main__':unittest.main()
