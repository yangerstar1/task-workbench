#!/usr/bin/env python3
"""Combined diagnostic wiring checks. Source-only; never runs Unity or Docker."""
import ast
import hashlib
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch
import safe_project_ci as safe

ROOT=Path(__file__).resolve().parents[3]
TASK=ROOT/'tasks/lottery-shop'
WORKFLOW=ROOT/'.github/workflows/lottery-visual-candidate.yml'
SCRIPTS=TASK/'scripts'


def blocks(text):
    return ['      - '+x for x in text.split('      - ')[1:]]


def with_id(text, name):
    found=[b for b in blocks(text) if re.search(r'^        id: '+re.escape(name)+r'$',b,re.M)]
    if len(found)!=1:raise ValueError('EXPECTED_EXACT_STEP')
    return found[0]


class CombinedDiagnosticTests(unittest.TestCase):
    def test_job_disables_bytecode_before_any_python_guard(self):
        text=WORKFLOW.read_text()
        self.assertEqual(text.count("    env:\n      PYTHONDONTWRITEBYTECODE: '1'\n    steps:\n"),1)
        self.assertLess(text.index("      PYTHONDONTWRITEBYTECODE: '1'"),text.index('id: guard'))

    def test_cold_prepare_order_before_native(self):
        text=WORKFLOW.read_text()
        names=['id: guard','visual_candidate_ci.py restore-font','id: counterlightprepare','id: counterlightdeps','id: inventorybefore','id: safestart','id: capture']
        positions=[text.index(x) for x in names]
        self.assertEqual(positions,sorted(positions))
        for n in ('counterlightprepare','counterlightdeps','inventorybefore'):
            self.assertNotIn('always()',with_id(text,n))
        self.assertNotIn('continue-on-error',text)

    def test_exact_opt_in_only_capture(self):
        text=WORKFLOW.read_text()
        self.assertIn('safe_project_ci.py capture --counter-light-diagnostic',with_id(text,'capture'))
        self.assertEqual(text.count(' --counter-light-diagnostic'),1)
        self.assertNotIn('--counter-light-diagnostic-fault',text)
        for n in ('regressionedit','regressionplaycore','regressionplayworld'):
            self.assertNotIn('--counter-light-diagnostic',with_id(text,n))

    def test_safe_default_and_opt_in_leave_other_phases_unchanged(self):
        ident=dict(sourceCommit='1'*40,reviewedCandidateCommit='2'*40,runId='123',runAttempt='1')
        with patch.object(safe,'COUNTER_LIGHT_DIAGNOSTIC',False),patch.object(safe,'COUNTER_LIGHT_DIAGNOSTIC_FAULT',''):
            baseline={p:safe.project_argv(p,ident) for p in safe.PHASES}
        with patch.object(safe,'COUNTER_LIGHT_DIAGNOSTIC',True),patch.object(safe,'COUNTER_LIGHT_DIAGNOSTIC_FAULT',''):
            for phase in safe.PHASES:
                got=safe.project_argv(phase,ident)
                self.assertEqual(got,baseline[phase]+(['-counterLightDiagnostic','1'] if phase=='capture' else []))

    def test_original_budgets_and_workflow_limits_remain(self):
        self.assertEqual(safe.PHASES['capture'][3],1800)
        self.assertEqual({safe.PHASES[k][3] for k in ('regression-edit','regression-play-core','regression-play-world')},{480})
        text=WORKFLOW.read_text();self.assertIn('timeout-minutes: 75',text)
        fixture=(TASK/'unity/Assets/G3/Tests/VisualCandidate/VisualCandidateCaptureTests.cs').read_text()
        self.assertIn('900',fixture)

    def test_finalize_follows_original_cleanup_and_export(self):
        text=WORKFLOW.read_text();f=with_id(text,'counterlightfinalize')
        pos=text.index('id: counterlightfinalize')
        for earlier in ('safe_project_ci.py finish','visual_candidate_ci.py snapshot-after','name: Upload bounded regression and source mutation evidence'):
            self.assertLess(text.index(earlier),pos)
        for n in ('guard','counterlightprepare','counterlightdeps','capture','regressionedit','regressionplaycore','regressionplayworld'):
            self.assertIn('steps.'+n+".outcome == 'success'",f)
        self.assertIn('always()',f)
        self.assertIn('compose_evidence.py finalize --repo-root "$GITHUB_WORKSPACE"',f)

    def test_image_dependency_setup_fails_closed_before_native(self):
        text=WORKFLOW.read_text();setup=with_id(text,'counterlightdeps')
        for required in ('set -euo pipefail', 'COUNTER_LIGHT_DEPENDENCY_SETUP_FAILED_BEFORE_NATIVE',
                         'test ! -e "$LIGHT_ENV"', 'python3 -m venv "$LIGHT_ENV"',
                         '--isolated install --index-url https://pypi.org/simple --only-binary=:all:',
                         "'numpy==2.3.5' 'Pillow==12.3.0'", '--dependencies-only -v'):
            self.assertIn(required,setup)
        self.assertNotIn('always()',setup);self.assertNotIn('secrets.',setup)
        python='"$RUNNER_TEMP/lottery-counter-light-python-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT/bin/python"'
        self.assertIn(python+' tasks/lottery-shop/scripts/counter_light_diagnostics/compose_evidence.py finalize',with_id(text,'counterlightfinalize'))
        command='python3 -S tasks/lottery-shop/scripts/test_counter_light_prepare_ci.py -v'
        self.assertEqual(text.count(command),1);self.assertLess(text.index(command),text.index('id: safestart'))

    def test_inventory_does_not_depend_on_light_finalize_result(self):
        text=WORKFLOW.read_text()
        for n in ('inventoryafter','inventorypublish'):
            b=with_id(text,n);self.assertIn('always()',b);self.assertNotIn('counterlight',b)
        self.assertGreater(text.index('id: inventoryafter'),text.index('safe_project_ci.py finish'))
        self.assertIn("steps.inventorypublish.outcome != 'success'",text)
        self.assertIn("echo 'STAGE_A_INVENTORY_BLOCKED_NOT_SOURCE_WAIVER_NOT_G3_PASS'\n          exit 1",text)

    def test_exact_new_artifact_boundaries(self):
        text=WORKFLOW.read_text()
        light=[b for b in blocks(text) if 'name: lottery-counter-light-diagnostic-' in b]
        inv=[b for b in blocks(text) if 'name: lottery-shop-inventory-not-' in b]
        self.assertEqual(len(light),1);self.assertEqual(len(inv),1)
        self.assertIn("steps.counterlightfinalize.outcome == 'success'",light[0])
        self.assertIn('path: tasks/lottery-shop/artifacts/counter-light-package\n',light[0])
        self.assertIn("steps.inventorypublish.outputs.publishable == 'true'",inv[0])
        self.assertIn('path: tasks/lottery-shop/evidence/visual-candidate/shop-inventory-not-source-waiver-not-g3-pass.json',inv[0])
        for b in light+inv:
            self.assertIn('actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02',b)
            self.assertNotIn('*',b);self.assertNotIn('.log',b);self.assertNotIn('ProjectSettings',b)

    def test_safe_observation_and_status_upload_are_independent(self):
        text=WORKFLOW.read_text();block=with_id(text,'counterlightobservation')
        self.assertIn('always()',block);self.assertNotIn('counterlightfinalize',block)
        self.assertLess(text.index('safe_project_ci.py finish'),text.index('id: counterlightobservation'))
        self.assertLess(text.index('id: counterlightobservation'),text.index('id: counterlightfinalize'))
        partial=[b for b in blocks(text) if 'name: lottery-counter-light-unvalidated-' in b]
        statuses=[b for b in blocks(text) if 'name: lottery-post-step-fixed-status-' in b]
        self.assertEqual(len(partial),1);self.assertEqual(len(statuses),1)
        self.assertIn("steps.counterlightobservation.outputs.safe_observation == 'true'",partial[0])
        for b in partial+statuses:
            self.assertNotIn('*',b);self.assertNotIn('.log',b);self.assertNotIn('ProjectSettings',b)
        self.assertIn("steps.poststatuscollect.outcome == 'success'",statuses[0]);self.assertIn("steps.poststatuscollect.outputs.safe_statuses == 'true'",statuses[0])
        self.assertIn('path: tasks/lottery-shop/artifacts/post-capture-screened-status',statuses[0]);self.assertNotIn('evidence/visual-candidate',statuses[0])
        collector=with_id(text,'poststatuscollect');self.assertIn('always()',collector);self.assertIn('post_capture_safety.py collect-statuses',collector)

    def test_counter_contract_matches_every_exact_file(self):
        folder=SCRIPTS/'counter_light_diagnostics';data=json.loads((folder/'code-contract.json').read_bytes())
        names=[]
        for row in data['files']:
            names.append(row['repositoryPath']);raw=(ROOT/row['repositoryPath']).read_bytes()
            self.assertEqual(len(raw),row['bytes']);self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        self.assertEqual(len(names),len(set(names)));self.assertEqual(len(names),24)
        for new in ('tasks/lottery-shop/scripts/post_capture_safety.py','tasks/lottery-shop/scripts/counter_light_diagnostics/export_observation.py'):self.assertIn(new,names)
        pins=json.loads((folder/'dependency-pins.json').read_bytes())
        for name,digest in pins.items():self.assertEqual(hashlib.sha256((folder/'pinned_dependencies'/name).read_bytes()).hexdigest(),digest)

    def test_new_wiring_test_is_executed_before_activation(self):
        text=WORKFLOW.read_text();cmd='python3 tasks/lottery-shop/scripts/test_diagnostic_extensions_ci.py -v'
        self.assertEqual(text.count(cmd),1);self.assertLess(text.index(cmd),text.index('id: safestart'))




# Capture runner budget binding: source-only, not a device-performance target.
FIXTURE=TASK/'unity/Assets/G3/Tests/VisualCandidate/VisualCandidateCaptureTests.cs'
DIAGNOSTIC=TASK/'unity/Assets/G3/Tests/VisualCandidate/CounterLightDiagnosticCapture.cs'
METHOD='ScenarioStateCaptureRetainsTwentyThreeViewsFromRealTransactionsV2'

def capture_budget(source):
    """Reject missing, literal, detached, or unbounded watchdog declarations."""
    runtime=re.findall(r'const double RuntimeSeconds = (\d+), FaceSeconds = (\d+), WalkSeconds = (\d+), UnloadSeconds = (\d+);',source)
    if runtime!=[('900','120','180','10')]:raise ValueError('CAPTURE_DECLARED_BUDGET_DRIFT')
    header=r'\[UnityTest\]\s*\[Timeout\(\(int\)\(RuntimeSeconds \* 1000\)\)\]\s*public IEnumerator '+METHOD+r'\(\)'
    if len(re.findall(header,source))!=1 or len(re.findall(r'\[Timeout\s*\(',source))!=1:
        raise ValueError('CAPTURE_RUNNER_BUDGET_UNBOUND')
    if 'runtimeProgress.ElapsedSeconds >= RuntimeSeconds' not in source or 'Assert.Fail("Visual fixture runtime exceeded 900 seconds; this is a diagnostic failure, never a skip or pass")' not in source:
        raise ValueError('CAPTURE_COOPERATIVE_GATE_DRIFT')
    return int(runtime[0][0])*1000

class CaptureTimeoutBudgetTests(unittest.TestCase):
    def test_declared_runtime_and_method_attribute_share_one_budget(self):
        self.assertEqual(capture_budget(FIXTURE.read_text()),900000)

    def test_bound_attribute_is_on_exact_capture_case_only(self):
        s=FIXTURE.read_text()
        self.assertEqual(s.count('[UnityTest]'),1)
        self.assertEqual(s.count('public IEnumerator '+METHOD+'()'),1)
        self.assertNotIn('[assembly: Timeout',s)
        self.assertNotIn('[TestFixture, Timeout',s)
        self.assertLess(s.index('public sealed class VisualCandidateCaptureTests'),s.index('[Timeout('))

    def test_cooperative_runtime_timeout_remains_failure(self):
        s=FIXTURE.read_text();body=s.split('void CheckRuntimeBudget()',1)[1].split('void Milestone(',1)[0]
        self.assertIn('>= RuntimeSeconds',body);self.assertIn('Milestone("runtime-timeout")',body)
        self.assertIn('Assert.Fail(',body);self.assertNotIn('Assert.Ignore',body);self.assertNotIn('Assert.Pass',body)

    def test_nested_diagnostic_budget_still180seconds(self):
        s=DIAGNOSTIC.read_text();self.assertIn('const long BudgetMs = 180000;',s)
        self.assertIn('timer.ElapsedMilliseconds < BudgetMs',s)
        self.assertIn('"DIAGNOSTIC_TIME_BUDGET"',s)
        self.assertIn('ThrowIfAny(errors); // Never let a diagnostic failure proceed to a normal frame.',s)

    def test_diagnostic17cases_restore_checks_and_schema_remain(self):
        p=TASK/'scripts/counter_light_diagnostics/diagnostic_plan.json';plan=json.loads(p.read_text())
        self.assertEqual(len(plan['cases']),17);self.assertIn('ambient-sh-zero',plan['cases'])
        s=DIAGNOSTIC.read_text();self.assertIn('PER_CASE_RESTORED_PIXEL_MISMATCH',s)
        self.assertIn('FINAL_RESTORED_PIXEL_MISMATCH',s);self.assertIn('public int schemaVersion = 3;',s)

    def test_capture_process_remains1800_other_process_budgets480(self):
        tree=ast.parse((TASK/'scripts/safe_project_ci.py').read_text())
        node=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PHASES' for t in n.targets))
        # Other tuple members include imported assembly selectors; inspect only fixed budgets.
        budgets={ast.literal_eval(k):ast.literal_eval(v.elts[3]) for k,v in zip(node.keys,node.values)}
        self.assertEqual(budgets['capture'],1800)
        for p in ('regression-edit','regression-play-core','regression-play-world'):self.assertEqual(budgets[p],480)
        self.assertLess(capture_budget(FIXTURE.read_text()),budgets['capture']*1000)

    def test_workflow_capture_and_job_budgets_unchanged(self):
        text=(ROOT/'.github/workflows/lottery-visual-candidate.yml').read_text()
        block=text.split('        id: capture\n',1)[1].split('      - name:',1)[0]
        self.assertIn('timeout-minutes: 32',block);self.assertIn('timeout-minutes: 75',text)
        self.assertIn('safe_project_ci.py capture --counter-light-diagnostic',block)

    def test_normal23_frames_and_completion_gate_remain(self):
        s=FIXTURE.read_text();self.assertIn('Assert.That(frames.Count, Is.EqualTo(23));',s)
        self.assertIn('yield return ExteriorFixtureViews(true);',s)
        self.assertIn('Capture("night-bill", "NORMAL_BILL_INFORMATION_HIERARCHY");',s)
        self.assertIn('WriteReceipt(true);\n            Milestone("scenario-complete");',s)

    def test_fixture_bound_in_code_contract(self):
        contract=json.loads((TASK/'scripts/counter_light_diagnostics/code-contract.json').read_text())
        rel=FIXTURE.relative_to(ROOT).as_posix();rows=[r for r in contract['files'] if r['repositoryPath']==rel]
        self.assertEqual(len(rows),1);raw=FIXTURE.read_bytes()
        self.assertEqual((rows[0]['bytes'],rows[0]['sha256']),(len(raw),hashlib.sha256(raw).hexdigest()))

    def test_framework_manifest_and_lock_pin1_6_builtin(self):
        p=TASK/'unity/Packages';manifest=json.loads((p/'manifest.json').read_text());lock=json.loads((p/'packages-lock.json').read_text())
        self.assertEqual(manifest['dependencies']['com.unity.test-framework'],'1.6.0')
        self.assertEqual(lock['dependencies']['com.unity.test-framework']['version'],'1.6.0')
        self.assertEqual(lock['dependencies']['com.unity.test-framework']['source'],'builtin')

    def test_missing_or_literal_runner_timeout_is_rejected(self):
        s=FIXTURE.read_text();attribute='[Timeout((int)(RuntimeSeconds * 1000))]'
        for replacement in ('','[Timeout(900000)]','[Timeout(180000)]','[Timeout(0)]','[Timeout((int)(RuntimeSeconds * 100))]'):
            with self.subTest(replacement=replacement),self.assertRaisesRegex(ValueError,'CAPTURE_RUNNER_BUDGET_UNBOUND'):
                capture_budget(s.replace(attribute,replacement,1))

    def test_detached_declaration_or_cooperative_failure_is_rejected(self):
        s=FIXTURE.read_text()
        for old,new in [('RuntimeSeconds = 900','RuntimeSeconds = 901'),('runtimeProgress.ElapsedSeconds >= RuntimeSeconds','runtimeProgress.ElapsedSeconds >= 1800'),('Assert.Fail("Visual fixture runtime exceeded 900 seconds','Assert.Pass("Visual fixture runtime exceeded 900 seconds')]:
            with self.subTest(replacement=new),self.assertRaises(ValueError):capture_budget(s.replace(old,new,1))

    def test_budget_guard_is_in_executed_pre_native_entrypoint(self):
        command='python3 tasks/lottery-shop/scripts/test_diagnostic_extensions_ci.py -v'
        workflow=(ROOT/'.github/workflows/lottery-visual-candidate.yml').read_text()
        self.assertEqual(workflow.count(command),1)
        self.assertLess(workflow.index(command),workflow.index('id: safestart'))
        source=(TASK/'scripts/test_diagnostic_extensions_ci.py').read_text()
        self.assertLess(source.index('class CaptureTimeoutBudgetTests'),source.index("if __name__=='__main__'"))

if __name__=='__main__':unittest.main()
