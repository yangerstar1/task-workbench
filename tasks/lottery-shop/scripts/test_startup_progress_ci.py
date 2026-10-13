#!/usr/bin/env python3
"""Synthetic startup evidence validation; no Unity execution."""
import copy,json,os,sys,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
import startup_progress_ci as startup

IDENT=dict(scope=startup.visual.SCOPE,sourceCommit='1'*40,reviewedCandidateCommit='2'*40,runId='123',runAttempt='1')
ENV=dict(GITHUB_SHA=IDENT['sourceCommit'],GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1')

def event(stage='ARMED',ms=0):
    return dict(stage=stage,origin='NONE',code='NONE',exceptionKind='NONE',elapsedMs=ms,errorCount=0,assertCount=0,exceptionCount=0,utfErrorCount=0,isPlaying=False,isPlayingOrWillChangePlaymode=False,isCompiling=False,isUpdating=False)
def receipt():
    return dict(schemaVersion=1,scope=startup.SCOPE,status=startup.STATUS,sourceCommit=IDENT['sourceCommit'],runId='123',runAttempt='1',startedUtc='2026-10-13T16:00:00.0000000Z',diagnosticWriteFailed=False,eventLimitReached=False,errorCount=0,assertCount=0,exceptionCount=0,utfErrorCount=0,events=[event(),event('PREBUILD_RETURNED',10)])

class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.source=self.root/startup.visual.TASK/'artifacts/visual-candidate'/startup.NAME;self.source.parent.mkdir(parents=True)
        self.dest=startup.visual.outdir(self.root)/startup.NAME;startup.visual.write(self.dest.parent/'source-receipt.json',IDENT)
        self.value=receipt();self.save();self.env=patch.dict(os.environ,ENV);self.env.start();self.addCleanup(self.env.stop)
    def save(self):self.source.write_text(json.dumps(self.value))
    def validate(self,v):return startup.validate_startup(v,IDENT)
    def export(self):startup.export_startup(self.root)
    def test_valid_observations_preserved_byte_exact_without_test_verdict(self):
        self.export();self.assertEqual(self.dest.read_bytes(),self.source.read_bytes());self.assertEqual(json.loads(self.dest.read_bytes())['status'],'OBSERVATIONS_ONLY_NOT_TEST_PASS')
    def test_unknown_root_and_event_text_fields_rejected(self):
        for v in [dict(self.value,rawLog='SECRET'),dict(self.value,path='/tmp/private')]:
            with self.assertRaises(ValueError):self.validate(v)
        v=copy.deepcopy(self.value);v['events'][0]['message']='SECRET'
        with self.assertRaises(ValueError):self.validate(v)
    def test_duplicate_json_keys_rejected_at_both_levels(self):
        original=json.dumps(self.value)
        for raw in [original.replace('"schemaVersion": 1','"schemaVersion":"SECRET","schemaVersion":1'),original.replace('"stage": "ARMED"','"stage":"SECRET","stage":"ARMED"')]:
            self.source.write_text(raw)
            with self.assertRaises(ValueError):self.export()
            self.assertFalse(self.dest.exists())
    def test_enum_fields_reject_arbitrary_text_paths_types(self):
        for key in ('stage','code','exceptionKind','origin'):
            for bad in ('SECRET','/tmp/private',True,123,None,[]):
                v=copy.deepcopy(self.value);v['events'][0][key]=bad
                with self.subTest(key=key,bad=bad),self.assertRaises(ValueError):self.validate(v)
    def test_integer_bounds_bool_and_nonfinite_rejected(self):
        for key in startup.COUNTERS:
            for bad in (True,-1,1000001,1.5,float('nan'),float('inf')):
                v=copy.deepcopy(self.value);v[key]=bad
                with self.assertRaises(ValueError):self.validate(v)
        for bad in (True,-1,3600001,float('nan'),float('inf')):
            v=copy.deepcopy(self.value);v['events'][0]['elapsedMs']=bad
            with self.assertRaises(ValueError):self.validate(v)
    def test_boolean_flags_are_strict(self):
        for key in ('diagnosticWriteFailed','eventLimitReached'):
            v=copy.deepcopy(self.value);v[key]=1
            with self.assertRaises(ValueError):self.validate(v)
        for key in startup.FLAGS:
            v=copy.deepcopy(self.value);v['events'][0][key]=1
            with self.assertRaises(ValueError):self.validate(v)
    def test_time_counter_monotonicity_and_final_agreement(self):
        for mutate in (lambda v:v['events'][1].update(elapsedMs=-1),lambda v:v['events'][0].update(errorCount=1),lambda v:(v.update(errorCount=1),v['events'][0].update(errorCount=1))):
            v=copy.deepcopy(self.value);mutate(v)
            with self.assertRaises(ValueError):self.validate(v)
    def test_armed_first_and_count_limits(self):
        for events in ([],[event('QUITTING')],[event() for _ in range(65)]):
            v=copy.deepcopy(self.value);v['events']=events
            with self.assertRaises(ValueError):self.validate(v)
        v=copy.deepcopy(self.value);v['events']=[event() for _ in range(64)];self.validate(v)
    def test_repeated_domain_and_error_stages_are_allowed_not_fabricated_unique(self):
        self.value['events'] += [event('BEFORE_RELOAD',11),event('DOMAIN_RESTORED',12),event('BEFORE_RELOAD',13),event('DOMAIN_RESTORED',14)];self.save();self.export()
    def test_error_observation_is_preserved_without_new_native_pass_claim(self):
        e=event('ERROR_LOG',11);e.update(errorCount=1,code='UNCLASSIFIED',exceptionKind='OTHER');self.value['events'].append(e);self.value['errorCount']=1;self.save();self.export();self.assertEqual(self.dest.read_bytes(),self.source.read_bytes())
    def test_truncated_observations_preserved_but_fail_completion(self):
        for key in ('diagnosticWriteFailed','eventLimitReached'):
            self.value=receipt();self.value[key]=True;self.save()
            with self.assertRaises(ValueError):self.export()
            self.assertEqual(self.dest.read_bytes(),self.source.read_bytes())
    def test_identity_source_run_attempt_and_review_binding_rejected(self):
        for key in ('sourceCommit','runId','runAttempt'):
            v=copy.deepcopy(self.value);v[key]='WRONG'
            with self.assertRaises(ValueError):self.validate(v)
        with patch.dict(os.environ,GITHUB_RUN_ATTEMPT='2'),self.assertRaises(ValueError):self.export()
        bad=dict(IDENT,reviewedCandidateCommit='FREE_TEXT');startup.visual.write(self.dest.parent/'source-receipt.json',bad)
        with self.assertRaises(ValueError):self.export()
    def test_utc_strict_format_and_calendar_validity(self):
        for bad in ('SECRET','2026-13-13T00:00:00Z','2026-10-13T00:00:00+08:00','2026-10-13',True,'2026-10-13T00:00:00.12345678Z'):
            v=copy.deepcopy(self.value);v['startedUtc']=bad
            with self.assertRaises(ValueError):self.validate(v)
    def test_missing_oversize_and_stale_output_rejected(self):
        self.export();self.source.unlink()
        with self.assertRaises(ValueError):self.export()
        self.assertFalse(self.dest.exists());self.source.write_bytes(b'x'*32769)
        with self.assertRaises(ValueError):self.export()
        self.assertFalse(self.dest.exists())
    def test_source_and_parent_symlink_rejected(self):
        target=self.root/'secret';target.write_bytes(self.source.read_bytes());self.source.unlink();self.source.symlink_to(target)
        with self.assertRaises(ValueError):self.export()
        self.assertFalse(self.dest.exists())
    def test_destination_symlink_is_removed_without_writing_target(self):
        target=self.root/'secret';target.write_text('UNCHANGED');self.dest.symlink_to(target);self.export();self.assertEqual(target.read_text(),'UNCHANGED');self.assertFalse(self.dest.is_symlink())
    def test_cli_failure_output_never_contains_exception_payload(self):
        import io,contextlib
        out=io.StringIO()
        with patch.object(startup,'export_startup',side_effect=RuntimeError('SECRET_STACK_PATH')),contextlib.redirect_stdout(out):self.assertEqual(startup.main(),1)
        self.assertEqual(out.getvalue(),'CAPTURE_STARTUP_DIAGNOSTIC_REJECTED\n')
    def test_fixed_workflow_literal_output_and_suite(self):
        w=(Path(__file__).resolve().parents[3]/'.github/workflows/lottery-visual-candidate.yml').read_text()
        self.assertEqual(w.count('tasks/lottery-shop/evidence/visual-candidate/startup-progress.json'),1)
        self.assertEqual(w.count('python3 tasks/lottery-shop/scripts/test_startup_progress_ci.py -v'),1)
        self.assertNotIn('startup-*.json',w)

    def test_root_count_can_exceed_latest_event_for_deduplicated_category(self):
        self.value['errorCount']=3;self.save();self.export();self.assertEqual(self.dest.read_bytes(),self.source.read_bytes())

if __name__=='__main__':unittest.main()
