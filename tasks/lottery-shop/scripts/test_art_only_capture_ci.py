#!/usr/bin/env python3
"""Small synthetic profile checks. No Unity, capture, regression, or G3 evidence."""
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import art_only_capture_ci as art
import visual_candidate_ci as v
import safe_project_ci as safe

REVIEW = dict(sourceCommit='2'*40, status='APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY',
              reviewedAtUtc='2026-10-14T00:00:00Z', reviewId='visual-source-20261014-99', reviewer='independent-source-review')
IDENT = dict(scope=v.SCOPE, sourceCommit='1'*40, reviewedCandidateCommit='2'*40, runId='123', runAttempt='1',
             requestId='lottery-visual-20261014-99', sourceReview=REVIEW, g3Gate='NOT_EVALUATED', deviceQa='NOT_RUN',
             executionProfile=v.ART_ONLY, regressionPlan='NOT_REQUESTED_ART_ONLY_DIAGNOSTIC', priorRegressionFailures='UNCHANGED_NOT_SUPERSEDED')


def request(profile=v.ART_ONLY):
    return dict(schemaVersion=2, requestId=IDENT['requestId'], sourceCommit='2'*40,
                purpose=v.SCOPE, sourceReview=copy.deepcopy(REVIEW), executionProfile=profile)


def environment():
    return dict(GITHUB_SHA='1'*40, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1', ART_GUARD_OUTCOME='success',
                ART_EXECUTION_PROFILE=v.ART_ONLY, ART_PREPARE_OUTCOME='success', ART_START_OUTCOME='success', ART_CAPTURE_OUTCOME='failure',
                ART_FINISH_OUTCOME='success', ART_PREPARE_ORIGINAL_OUTCOME='skipped',
                **{key:'skipped' for key in art.REGRESSION_ENV})


class ArtOnlyChecks(unittest.TestCase):
    def fixture(self, root):
        v.write(root/v.REQUEST, request()); v.write(v.outdir(root)/'source-receipt.json', IDENT)
        return patch.object(v, 'git', return_value=(root/v.REQUEST).read_text().strip())

    def test_closed_selector_and_legacy_compatibility(self):
        for profile in (v.ART_ONLY, v.FULL_DIAGNOSTIC, v.EARLY_STOP):
            self.assertEqual(v.request_execution_profile(request(profile)), profile)
        legacy=request(); legacy.pop('executionProfile'); legacy['schemaVersion']=1
        self.assertEqual(v.request_execution_profile(legacy), v.FULL_DIAGNOSTIC)
        for profile in (True, None, 1, 'true', 'art_only_diagnostic', 'G3_PASS'):
            with self.assertRaises(ValueError): v.request_execution_profile(request(profile))
        with self.assertRaises(ValueError): v.request_profile(request())
        for field,value in (('schemaVersion', True), ('requestId', 1), ('sourceCommit', None), ('purpose', False), ('sourceReview', [])):
            with self.assertRaises(ValueError): v.request_execution_profile(dict(request(), **{field:value}))
        for extra in ({'skipTests':True}, {'commands':['echo']}, {'androidBuild':'DEVELOPMENT_CANDIDATE_APK'}):
            with self.assertRaises(ValueError): v.request_execution_profile(dict(request(), **extra))

    def test_prepare_binds_existing_contract_and_rejects_tampered_dependency(self):
        with tempfile.TemporaryDirectory() as d, patch.object(v,'guard',return_value=IDENT), patch.dict(os.environ, GITHUB_WORKFLOW_REF='yangerstar1/task-workbench/.github/workflows/lottery-visual-candidate.yml@refs/heads/lottery-shop-g0-20261011'):
            root=Path(d); rows=[]
            for relative in sorted(art.REQUIRED_CODE):
                path=root/relative; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b'synthetic code\n')
                rows.append(dict(repositoryPath=relative,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size))
            v.write(root/art.CONTRACT,dict(schemaVersion=1,scope='REVIEWED_COUNTER_LIGHT_R2_CODE_CONTRACT_NOT_RUNTIME_PASS',files=rows))
            def git(_root,command,*args):
                relative=args[-1] if command=='hash-object' else args[-1].split(':',1)[1]
                raw=(root/relative).read_bytes()
                return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            with patch.object(v,'git',side_effect=git):
                self.assertEqual(art.prepare(root)['status'],'ART_ONLY_SOURCE_BOUND_NOT_NATIVE_PASS')
                (root/rows[0]['repositoryPath']).write_bytes(b'tampered')
                with self.assertRaises(ValueError): art.prepare(root)

    def test_real_25_row_contract_cold_prepare_and_unknown_ci_rejected(self):
        source = Path(__file__).resolve().parents[3]
        original = v.read_json(source/art.CONTRACT)
        self.assertEqual(len(original['files']), 25)
        names = {row['repositoryPath'] for row in original['files']}
        self.assertEqual(len(names), 25)
        self.assertTrue(art.CI_CONTRACT_PATHS <= names)
        for unknown_ci in (False, True):
            with self.subTest(unknown_ci=unknown_ci), tempfile.TemporaryDirectory(prefix='ART_COLD_SOURCE_NOT_NATIVE_') as d:
                parent=Path(d);root=parent/'checkout';root.mkdir()
                contract=copy.deepcopy(original)
                for relative in sorted(names | {v.WORKFLOW, v.TASK+'/.gitignore'}):
                    destination=root/relative;destination.parent.mkdir(parents=True,exist_ok=True)
                    destination.write_bytes((source/relative).read_bytes())
                if unknown_ci:
                    relative=v.TASK+'/ci/not-allowed.json';raw=b'{"synthetic":true}\n'
                    path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
                    contract['files'].append(dict(repositoryPath=relative,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
                v.write(root/art.CONTRACT,contract)
                env=dict(PATH=os.defpath,HOME=str(parent/'empty-home'),LANG='C.UTF-8',
                         PYTHONDONTWRITEBYTECODE='1',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull)
                Path(env['HOME']).mkdir()
                def git(*args):
                    return subprocess.check_output(['git','-C',str(root),*args],env=env,stderr=subprocess.DEVNULL).decode().strip()
                git('init','-q');git('config','user.name','Synthetic Art Contract');git('config','user.email','synthetic-art@example.invalid')
                git('add','.');git('commit','-qm','Synthetic exact candidate source');reviewed=git('rev-parse','HEAD')
                r=request();r['sourceCommit']=reviewed;r['sourceReview']['sourceCommit']=reviewed
                v.write(root/v.REQUEST,r);git('add','.');git('commit','-qm','Synthetic request-only trigger');trigger=git('rev-parse','HEAD')
                event=parent/'event.json';v.write(event,dict(repository=dict(private=False,fork=False),deleted=False))
                env.update(GITHUB_EVENT_NAME='push',GITHUB_REPOSITORY='yangerstar1/task-workbench',GITHUB_REPOSITORY_OWNER='yangerstar1',
                           GITHUB_ACTOR='yangerstar1',GITHUB_TRIGGERING_ACTOR='yangerstar1',GITHUB_REF='refs/heads/lottery-shop-g0-20261011',
                           GITHUB_SHA=trigger,GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1',GITHUB_EVENT_PATH=str(event),
                           GITHUB_WORKFLOW_REF='yangerstar1/task-workbench/'+v.WORKFLOW+'@refs/heads/lottery-shop-g0-20261011',
                           GITHUB_OUTPUT=str(parent/'output.txt'))
                if unknown_ci:
                    with patch.dict(os.environ,env,clear=True), self.assertRaisesRegex(ValueError,'ART_CODE_PATH_REJECTED'):
                        art.prepare(root)
                    self.assertFalse((v.outdir(root)/art.PREPARED).exists())
                else:
                    result=subprocess.run([sys.executable,'-S',str(root/v.TASK/'scripts/art_only_capture_ci.py'),'prepare'],
                                          cwd=parent,env=env,capture_output=True,text=True,timeout=30)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    proof=v.read_json(v.outdir(root)/art.PREPARED)
                    self.assertEqual(proof['codeFileCount'],25);self.assertEqual(proof['codeContractSha256'],v.sha(root/art.CONTRACT))
                    self.assertEqual(proof['reviewedCandidateCommit'],reviewed);self.assertEqual(proof['executionProfile'],v.ART_ONLY)
                    self.assertEqual(proof['g3Gate'],'NOT_EVALUATED')

    def test_schema3_unchanged_but_art_android_rejected(self):
        r=dict(request(), schemaVersion=3, androidBuild='DEVELOPMENT_CANDIDATE_APK',
               androidReview=dict(REVIEW, status='APPROVED_FOR_DIAGNOSTIC_ANDROID_ONLY', reviewId='android-source-20261014-99'))
        with self.assertRaises(ValueError): v.request_execution_profile(r)
        for profile in (v.FULL_DIAGNOSTIC, v.EARLY_STOP):
            r['executionProfile']=profile; self.assertEqual(v.request_execution_profile(r), profile)
            self.assertEqual(v.request_profile(r), profile)

    def test_real_guard_preserves_source_review_actor_and_parent(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def git(*args): return subprocess.check_output(['git','-C',d,*args], stderr=subprocess.DEVNULL).decode().strip()
            git('init'); git('config','user.name','Synthetic'); git('config','user.email','synthetic@example.invalid')
            (root/'source').write_text('synthetic'); git('add','.'); git('commit','-m','source'); source=git('rev-parse','HEAD')
            r=request(); r['sourceCommit']=source; r['sourceReview']['sourceCommit']=source
            v.write(root/v.REQUEST,r); git('add','.'); git('commit','-m','request')
            event=root/'event.json'; event.write_text(json.dumps(dict(repository=dict(private=False,fork=False),deleted=False)))
            env=dict(environment(), GITHUB_EVENT_NAME='push', GITHUB_REPOSITORY='yangerstar1/task-workbench', GITHUB_REPOSITORY_OWNER='yangerstar1',
                     GITHUB_ACTOR='yangerstar1', GITHUB_TRIGGERING_ACTOR='yangerstar1', GITHUB_REF='refs/heads/lottery-shop-g0-20261011',
                     GITHUB_SHA=git('rev-parse','HEAD'), GITHUB_EVENT_PATH=str(event), GITHUB_OUTPUT=str(root/'outputs'))
            with patch.dict(os.environ,env):
                result=v.guard(root); self.assertEqual(result['executionProfile'],v.ART_ONLY); self.assertEqual(result['g3Gate'],'NOT_EVALUATED')
                self.assertIn('android_requested=false', (root/'outputs').read_text())
                with patch.dict(os.environ,GITHUB_ACTOR='other'), self.assertRaises(ValueError): v.guard(root)
                r['sourceReview']['sourceCommit']='3'*40; v.write(root/v.REQUEST,r)
                with self.assertRaises(ValueError): v.guard(root)

    def test_not_run_is_actual_skip_and_never_pass_even_capture_failure(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,environment()):
            root=Path(d)
            with self.fixture(root): result=art.finalize(root)
            self.assertEqual(result['regressionPlayWorld'],'NOT_RUN'); self.assertEqual(result['g3Gate'],'NOT_EVALUATED')
            self.assertEqual(result['nativeStepOutcomes']['capture'],'failure')
            self.assertFalse(any(value == 'PASSED' for value in result.values()))
            v.write(v.outdir(root)/'source-before.json',dict(IDENT,files=[]))
            with patch.object(v,'git',return_value=''): v.snapshot(root,after=True)
            after=v.read_json(v.outdir(root)/'source-after.json')
            self.assertEqual(after['executionProfile'],v.ART_ONLY); self.assertEqual(after['regressionExecution'],'NOT_RUN')

    def test_failed_or_missing_skip_cleanup_and_wrong_profile_cannot_attest(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,environment()):
            root=Path(d)
            with self.fixture(root):
                for key,value in ((art.REGRESSION_ENV[0],'success'),(art.REGRESSION_ENV[2],'failure'),
                                  ('ART_GUARD_OUTCOME','failure'),('ART_FINISH_OUTCOME','skipped'),
                                  ('ART_EXECUTION_PROFILE',v.FULL_DIAGNOSTIC)):
                    with patch.dict(os.environ,{key:value}), self.assertRaises(ValueError): art.finalize(root)

    def test_existing_world_failure_is_untouched_and_blocks_not_run(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,environment()):
            root=Path(d)
            with self.fixture(root):
                failure=v.outdir(root)/'regression-play-world/raw-test-results.xml'
                failure.parent.mkdir(); failure.write_text('<test-run result="Failed"/>')
                before=failure.read_bytes()
                with self.assertRaises(ValueError): art.finalize(root)
                self.assertEqual(failure.read_bytes(),before); self.assertFalse((v.outdir(root)/art.NAME).exists())

    def test_native_adapter_rejects_art_regressions_and_extra_diagnostics(self):
        with tempfile.TemporaryDirectory() as d, patch.object(safe,'identity',return_value=IDENT), patch.object(safe,'native') as native:
            for phase in ('regression-edit','regression-play-core','regression-play-world'):
                with self.assertRaises(ValueError): safe.test(Path(d),phase)
            with patch.object(safe,'COUNTER_LIGHT_DIAGNOSTIC',True), self.assertRaises(ValueError): safe.test(Path(d),'capture')
            native.assert_not_called()

    def test_failed_capture_still_returns_license_and_cleans_owned_container(self):
        with tempfile.TemporaryDirectory() as d, patch.object(safe,'identity',return_value=IDENT):
            root=Path(d)
            safe.private.write(safe.file(root,'session'),dict(IDENT,status='READY',activationSucceeded=True,stagesStarted=[],cleanup=None))
            def failed(*args): args[3].update(status='NATIVE_FAILED',nativeExitCode=3,dockerExitCode=3,nativeExitMarkerCount=1)
            def returned(*args):
                self.assertIn('-returnlicense',args[1]); args[3].update(status='NATIVE_SUCCEEDED',nativeExitCode=0,dockerExitCode=0,nativeExitMarkerCount=1)
            with patch.object(safe.private,'cleanup',return_value=dict(status='ABSENCE_VERIFIED')) as cleanup:
                with patch.object(safe,'native',side_effect=failed): self.assertEqual(safe.test(root,'capture'),1)
                with patch.object(safe,'native',side_effect=returned): self.assertEqual(safe.finish(root),0)
                cleanup.assert_called_once(); self.assertEqual(safe.session(root,IDENT)['stagesStarted'],['capture'])
                self.assertEqual(v.read_json(safe.file(root,'capture'))['status'],'NATIVE_FAILED')

    def test_workflow_gates_only_new_profile_and_keeps_cleanup_unconditional(self):
        workflow=(Path(__file__).resolve().parents[3]/v.WORKFLOW).read_text()
        for step in ('regressiondecision','regressionedit','prepareoriginal','regressionplaycore','regressionplayworld'):
            section=workflow.split('        id: '+step+'\n',1)[1].split('      - name:',1)[0]
            self.assertIn("steps.guard.outputs.execution_profile != 'ART_ONLY_DIAGNOSTIC'",section)
        finish=workflow.split('        id: nativefinish\n',1)[1].split('      - name:',1)[0]
        self.assertIn("always() && steps.guard.outcome == 'success' && steps.safestart.outcome != 'skipped'",finish)
        self.assertNotIn('execution_profile',finish); self.assertNotIn('continue-on-error:',workflow)
        self.assertEqual(len(v.FRAMES),23); self.assertEqual(safe.PHASES['capture'][3],1800)
        for phase,budget in (('regression-edit',480),('regression-play-core',720),('regression-play-world',480)):
            self.assertEqual(safe.PHASES[phase][3],budget)


if __name__ == '__main__': unittest.main()
