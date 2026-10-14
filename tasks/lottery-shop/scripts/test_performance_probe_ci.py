#!/usr/bin/env python3
"""Independent synthetic guard/schema tests; never invokes Unity or Docker."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import performance_probe_ci as perf
import safe_project_ci as safe

IDENT=dict(scope=perf.SCOPE,sourceCommit='1'*40,reviewedCandidateCommit='2'*40,runId='12345',runAttempt='1')


def measurement():
    phases=[]
    for p,phase in enumerate(('A1','B','A2')):
        samples=[]
        for n in range(6):
            metrics=[dict(code=code,unit=unit,reason='OBSERVED',available=True,isRunning=True,sampleCount=n+1,value=1000000 if unit=='NANOSECONDS' else 42,milliseconds=1 if unit=='NANOSECONDS' else -1) for code,unit in perf.METRICS.items()]
            samples.append(dict(index=n,frameDelta=1,cameraRenderDelta=1,wallMs=2000,metrics=metrics))
        phases.append(dict(phase=phase,shadowedAdditionalLights=0 if p==1 else 2,warmupCompleted=2,elapsedMs=16000,complete=True,samples=samples))
    return dict(schemaVersion=1,scope=perf.SCOPE,testIdentity=perf.CASE,sourceCommit=IDENT['sourceCommit'],reviewedCandidateCommit=IDENT['reviewedCandidateCommit'],runId=IDENT['runId'],runAttempt=IDENT['runAttempt'],unityVersion='6000.3.19f1',graphicsDeviceType='OpenGLCore',softwareRendererDetected=True,status='COMPLETE_MEASUREMENTS_ONLY',stage='TEARDOWN',gpuTiming='NOT_COLLECTED_CPU_COUNTERS_ONLY',visualReview='NOT_EVALUATED',deviceQa='NOT_RUN',width=1280,height=720,warmupFrames=2,sampleFrames=6,measuredAndWarmupFrames=24,shopRenderers=39,shopMaterials=39,sceneRenderers=500,cameraPosition=dict(x=0,y=1.58,z=1.69),cameraEuler=dict(x=8,y=180,z=0),cameraFov=64,cameraOrigin='FIXTURE_POSITIONED_NORMAL_ENTRY',stateSha256='a'*64,elapsedMs=62000,setupElapsedMs=12000,measurementElapsedMs=61000,setupComplete=True,a2Restored=True,finallyRestored=True,teardownRestored=True,stateUnchanged=True,renderingUnchanged=True,measurementsComplete=True,cleanupComplete=True,phases=phases)


class MeasurementTests(unittest.TestCase):
    def check(self,value):return perf.validate_measurements(value,IDENT)
    def test_complete_and_unavailable_are_honest_observations(self):
        value=measurement();self.assertEqual(self.check(value),value)
        m=value['phases'][1]['samples'][2]['metrics'][1];m.update(available=False,isRunning=False,sampleCount=0,reason='NOT_EXPOSED',value=-1,milliseconds=-1)
        self.check(value)
    def test_missing_does_not_become_zero_or_fabricated_gpu_time(self):
        for change in [dict(available=False,reason='NOT_EXPOSED',value=0,milliseconds=-1),dict(unit='MILLISECONDS'),dict(milliseconds=0),dict(available=True,reason='NOT_EXPOSED'),dict(sampleCount=17)]:
            value=measurement();value['phases'][0]['samples'][0]['metrics'][0].update(change)
            with self.assertRaises(ValueError):self.check(value)
        value=measurement();value['gpuTiming']='MEASURED'
        with self.assertRaises(ValueError):self.check(value)
    def test_wrong_sources_run_attempt_scope_or_case_rejected(self):
        for field in ['sourceCommit','reviewedCandidateCommit','runId','runAttempt','scope','testIdentity']:
            value=measurement();value[field]='wrong'
            with self.subTest(field=field),self.assertRaises(ValueError):self.check(value)
    def test_unknown_fields_and_metric_codes_rejected_at_every_level(self):
        for level in range(5):
            value=measurement();targets=[value,value['phases'][0],value['phases'][0]['samples'][0],value['phases'][0]['samples'][0]['metrics'][0]]
            if level<4:targets[level]['rawLog']='SYNTHETIC_PRIVATE'
            else:targets[3]['code']='arbitrary-marker'
            with self.assertRaises(ValueError):self.check(value)
    def test_nan_infinity_bool_and_out_of_bounds_rejected(self):
        for bad in [float('nan'),float('inf'),-1,60001,True]:
            value=measurement();value['phases'][0]['samples'][0]['wallMs']=bad
            with self.assertRaises(ValueError):self.check(value)
        for field,bad in [('elapsedMs',600001),('measurementElapsedMs',180001),('warmupFrames',3),('sampleFrames',5),('width',1600),('measuredAndWarmupFrames',25),('shopRenderers',10001)]:
            value=measurement();value[field]=bad
            with self.assertRaises(ValueError):self.check(value)
    def test_aba_order_sample_count_real_frame_and_restoration_required(self):
        mutations=[lambda v:v['phases'].reverse(),lambda v:v['phases'][1].update(shadowedAdditionalLights=2),lambda v:v['phases'][0]['samples'].pop(),lambda v:v['phases'][0]['samples'][0].update(frameDelta=0),lambda v:v.update(finallyRestored=False),lambda v:v.update(teardownRestored=False),lambda v:v.update(a2Restored=False),lambda v:v.update(cleanupComplete=False),lambda v:v.update(renderingUnchanged=False)]
        for change in mutations:
            value=measurement();change(value)
            with self.assertRaises(ValueError):self.check(value)
    def test_actual_camera_render_required_with_bounded_integer_count(self):
        for bad in [None,0,-1,17,True,1.0,'1']:
            value=measurement();sample=value['phases'][0]['samples'][0]
            if bad is None:sample.pop('cameraRenderDelta')
            else:sample['cameraRenderDelta']=bad
            with self.subTest(bad=bad),self.assertRaises(ValueError):self.check(value)
        value=measurement();value['phases'][0]['samples'][0]['cameraRenderDelta']=16
        self.check(value)
    def test_scene_camera_and_wall_accounting_are_fixed(self):
        for field, bad in [('cameraFov',63),('cameraOrigin','ARBITRARY'),('stateSha256','UNAVAILABLE'),('sceneRenderers',1),('measurementElapsedMs',50000)]:
            value=measurement();value[field]=bad
            with self.assertRaises(ValueError):self.check(value)
        value=measurement();value['cameraPosition']['x']=float('nan')
        with self.assertRaises(ValueError):self.check(value)
        value=measurement();value['phases'][0]['elapsedMs']=1
        with self.assertRaises(ValueError):self.check(value)
    def test_fixture_schema_source_uses_no_free_device_name_and_restores_before_receipt(self):
        root=Path(__file__).resolve().parents[3]
        text=(root/perf.TASK/'unity/Assets/G3/Tests/PerformanceDiagnostic/AdditionalShadowPerformanceTests.cs').read_text()
        tail=text[text.index('[Serializable] sealed class Receipt'):]
        self.assertNotIn('graphicsDeviceName',tail);self.assertIn('softwareRendererDetected',tail)
        self.assertIn('Timeout(180000)',text);self.assertIn('Is.LessThan(60)',text)
        self.assertIn('"'+perf.SCOPE+'"',text)
        self.assertLess(text.index('receipt.finallyRestored=TryRestoreLights()'),text.index('receipt.stage="RESTORED"'))
        for key in perf.METRICS:self.assertIn('new MetricSpec("'+key+'"',text)

    def test_partial_saved_but_cannot_pass_completeness_gate(self):
        value=measurement();value.update(status='PARTIAL_MEASUREMENTS_ONLY',measurementsComplete=False,finallyRestored=False,phases=value['phases'][:1],measuredAndWarmupFrames=8)
        self.check(value)
        with tempfile.TemporaryDirectory() as d,patch.object(perf,'identity',return_value=IDENT):
            root=Path(d);source=root/perf.TASK/'artifacts/performance-probe/performance-receipt.json';source.parent.mkdir(parents=True);source.write_text(json.dumps(value))
            with self.assertRaises(ValueError):perf.export_measurements(root)
            self.assertEqual(json.loads((perf.outdir(root)/'performance-receipt.json').read_text()),value)
    def test_oversize_and_unknown_data_never_export_or_leave_stale_output(self):
        with tempfile.TemporaryDirectory() as d,patch.object(perf,'identity',return_value=IDENT):
            root=Path(d);source=root/perf.TASK/'artifacts/performance-probe/performance-receipt.json';source.parent.mkdir(parents=True)
            dest=perf.outdir(root)/'performance-receipt.json';dest.parent.mkdir(parents=True);dest.write_text('STALE')
            source.write_text('x'*131073)
            with self.assertRaises(Exception):perf.export_measurements(root)
            self.assertFalse(dest.exists())
    def test_all_missing_counters_remain_missing_but_frame_wall_is_usable(self):
        value=measurement()
        for p in value['phases']:
            for f in p['samples']:
                for m in f['metrics']:m.update(available=False,isRunning=False,sampleCount=0,reason='NOT_EXPOSED',value=-1,milliseconds=-1)
        self.check(value)


class NativeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.old_visual=safe.visual;self.old_phases=safe.PHASES;safe.configure_performance()
    def tearDown(self):safe.visual=self.old_visual;safe.PHASES=self.old_phases
    def test_only_one_independent_phase_and_original_limits_unchanged(self):
        self.assertEqual(set(safe.PHASES),{'performance-probe'});self.assertEqual(safe.PHASES['performance-probe'][3],600)
        self.assertEqual(self.old_phases['regression-play-core'][3],480);self.assertEqual(self.old_phases['regression-play-world'][3],480);self.assertEqual(self.old_phases['capture'][3],1800)
        argv=safe.project_argv('performance-probe',IDENT)
        self.assertEqual(argv[argv.index('-assemblyNames')+1],'Lottery.G3.PerformanceDiagnostic.Tests')
        self.assertEqual(argv[argv.index('-probeReviewedCommit')+1],'2'*40);self.assertEqual(argv[argv.index('-probeRunAttempt')+1],'1')
        self.assertIn('-g3PerformanceProbe',argv)
        for bad in ['-quit','-nographics','-g3RegressionProgress']:self.assertNotIn(bad,argv)
        self.assertIn('/github/workspace/tasks/lottery-shop/artifacts/performance-probe/playmode-results.xml',argv)
    def test_wrong_profile_cannot_start_other_project_or_bypass_performance_flag(self):
        script=str(Path(__file__).with_name('safe_project_ci.py'))
        for args in [('capture','--performance-only'),('regression-play-core','--performance-only'),('regression-play-world','--performance-only'),('performance-probe',)]:
            p=subprocess.run([sys.executable,script,*args],capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            self.assertEqual(p.returncode,1);self.assertEqual(p.stdout.strip(),'SAFE_PROJECT_PROFILE_REJECTED');self.assertEqual(p.stderr,'')
    def test_new_workflow_one_native_case_same_pins_secret_scope_and_exact_exports(self):
        root=Path(__file__).resolve().parents[3];text=(root/perf.WORKFLOW).read_text()
        for fixed in ['group: unity-personal-proof','cancel-in-progress: false','contents: read','timeout-minutes: 35','timeout-minutes: 12','persist-credentials: false','0ff419b913a3630032cbe0de48a0099b5a9f0ed9','paths: [tasks/lottery-shop/ci/performance-probe-request.json]']:
            self.assertIn(fixed,text)
        self.assertEqual(text.count('secrets.'),3);self.assertEqual(text.count('safe_project_ci.py performance-probe --performance-only'),1)
        for bad in ['.png','*.json','*.xml','.log','uses: game-ci/unity-test-runner','continue-on-error','safe_project_ci.py capture','safe_project_ci.py regression-play']:self.assertNotIn(bad,text)
        self.assertIn('safe_project_ci.py finish --performance-only',text)


class NUnitTests(unittest.TestCase):
    def report(self):
        tree=ET.Element('test-run',result='Passed',total='1',passed='1',failed='0',skipped='0',inconclusive='0')
        suite=ET.SubElement(tree,'test-suite',type='Assembly',name=perf.ASSEMBLY,result='Passed')
        ET.SubElement(suite,'test-case',fullname=perf.CASE,result='Passed');return tree
    def run_report(self,tree):
        with tempfile.TemporaryDirectory() as d,patch.object(perf,'identity',return_value=IDENT):
            root=Path(d);path=root/perf.TASK/'artifacts/performance-probe/playmode-results.xml';path.parent.mkdir(parents=True);ET.ElementTree(tree).write(path,encoding='utf-8');perf.export_tests(root)
    def test_single_exact_pass(self):self.run_report(self.report())
    def test_failed_wrong_case_duplicate_empty_assembly_counts_rejected(self):
        for change in [lambda r:r.set('passed','777'),lambda r:r.find('test-suite').set('name','Other.dll'),lambda r:r.find('.//test-case').set('fullname','Other.Case'),lambda r:r.find('.//test-case').set('result','Failed'),lambda r:ET.SubElement(r,'test-suite',type='Assembly',name=perf.ASSEMBLY,result='Passed')]:
            tree=self.report();change(tree)
            with self.assertRaises(ValueError):self.run_report(tree)


class GuardTests(unittest.TestCase):
    def test_real_git_request_only_reviewed_parent_and_first_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True,stderr=subprocess.PIPE).strip()
            git('init','-q');git('config','user.name','Synthetic');git('config','user.email','synthetic@example.invalid')
            (root/'candidate.txt').write_text('safe');git('add','.');git('commit','-qm','candidate');source=git('rev-parse','HEAD')
            request=dict(schemaVersion=1,requestId='lottery-performance-20261013-01',sourceCommit=source,purpose=perf.SCOPE,sourceReview=dict(sourceCommit=source,status='APPROVED_FOR_PERFORMANCE_DIAGNOSTIC_ONLY',reviewedAtUtc='2026-10-13T00:00:00Z',reviewId='performance-source-20261013-01',reviewer='independent-source-review'))
            path=root/perf.REQUEST;path.parent.mkdir(parents=True);path.write_text(json.dumps(request));git('add','.');git('commit','-qm','request');head=git('rev-parse','HEAD')
            event=root/'event.json';event.write_text(json.dumps(dict(repository=dict(private=False,fork=False),deleted=False)))
            env=dict(GITHUB_EVENT_NAME='push',GITHUB_REPOSITORY='yangerstar1/task-workbench',GITHUB_REPOSITORY_OWNER='yangerstar1',GITHUB_ACTOR='yangerstar1',GITHUB_TRIGGERING_ACTOR='yangerstar1',GITHUB_REF='refs/heads/lottery-shop-g0-20261011',GITHUB_SHA=head,GITHUB_EVENT_PATH=str(event),GITHUB_RUN_ID='12345',GITHUB_RUN_ATTEMPT='1')
            with patch.dict(os.environ,env):
                value=perf.guard(root);self.assertEqual(value['reviewedCandidateCommit'],source);self.assertEqual(value['scope'],perf.SCOPE)
            for key,bad in [('GITHUB_ACTOR','other'),('GITHUB_SHA','a'*40),('GITHUB_RUN_ATTEMPT','2')]:
                with patch.dict(os.environ,dict(env,**{key:bad})),self.assertRaises(ValueError):perf.guard(root)
            request['purpose']='DIAGNOSTIC_VISUAL_CANDIDATE_NOT_G3_PASS';path.write_text(json.dumps(request))
            with patch.dict(os.environ,env),self.assertRaises(ValueError):perf.guard(root)


if __name__=='__main__':unittest.main()
