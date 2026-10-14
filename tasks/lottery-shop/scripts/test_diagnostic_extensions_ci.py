#!/usr/bin/env python3
"""Combined diagnostic wiring checks. Source-only; never runs Unity or Docker."""
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
        names=['id: guard','visual_candidate_ci.py restore-font','id: counterlightprepare','id: inventorybefore','id: safestart','id: capture']
        positions=[text.index(x) for x in names]
        self.assertEqual(positions,sorted(positions))
        for n in ('counterlightprepare','inventorybefore'):
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
        for n in ('guard','counterlightprepare','capture','regressionedit','regressionplaycore','regressionplayworld'):
            self.assertIn('steps.'+n+".outcome == 'success'",f)
        self.assertIn('always()',f)
        self.assertIn('compose_evidence.py finalize --repo-root "$GITHUB_WORKSPACE"',f)

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

    def test_counter_contract_matches_every_exact_file(self):
        folder=SCRIPTS/'counter_light_diagnostics';data=json.loads((folder/'code-contract.json').read_bytes())
        names=[]
        for row in data['files']:
            names.append(row['repositoryPath']);raw=(ROOT/row['repositoryPath']).read_bytes()
            self.assertEqual(len(raw),row['bytes']);self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        self.assertEqual(len(names),len(set(names)));self.assertEqual(len(names),22)
        pins=json.loads((folder/'dependency-pins.json').read_bytes())
        for name,digest in pins.items():self.assertEqual(hashlib.sha256((folder/'pinned_dependencies'/name).read_bytes()).hexdigest(),digest)

    def test_new_wiring_test_is_executed_before_activation(self):
        text=WORKFLOW.read_text();cmd='python3 tasks/lottery-shop/scripts/test_diagnostic_extensions_ci.py -v'
        self.assertEqual(text.count(cmd),1);self.assertLess(text.index(cmd),text.index('id: safestart'))


if __name__=='__main__':unittest.main()
