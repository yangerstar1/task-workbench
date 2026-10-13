#!/usr/bin/env python3
"""Synthetic stage/enum/privacy tests, not Unity preparation evidence."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import reflection_progress_ci as progress

IDENT=dict(scope=progress.visual.SCOPE,sourceCommit='1'*40,reviewedCandidateCommit='2'*40,runId='123',runAttempt='1')
ENV=dict(GITHUB_SHA=IDENT['sourceCommit'],GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1')


def event(stage,elapsed=0,**extra):
    value={key:False for key in progress.BOOL_FIELDS}
    value.update({key:-1 for key in progress.INT_FIELDS|progress.LONG_FIELDS})
    value.update(stageCode=stage,elapsedMs=elapsed,pixelSampleCount=0,changedInputKinds=0,errorCode='NONE',exceptionKind='NONE',maxChannelRange=-1)
    value.update(extra);return value


def receipt(status='COMPLETE',cold=False):
    stages=sorted(progress.STAGES-{499}) if cold else [10,20,21,30,320,321,322,323,324,325,400]
    value=dict(schemaVersion=1,scope=progress.SCOPE,sourceCommit=IDENT['sourceCommit'],runId='123',runAttempt='1',status=status,cacheHit=not cold,diagnosticWriteFailed=False,firstFailureStage=-1,firstFailureCode='NONE',firstExceptionKind='NONE',failureCount=0,elapsedMs=100,events=[event(stage,n) for n,stage in enumerate(stages)])
    if cold:
        by_stage={e['stageCode']:e for e in value['events']};by_stage[81].update(captureRenderers=39,captureTriangles=70000)
        for stage,index in ((112,0),(212,1)):
            by_stage[stage].update(bakeIndex=index,bakeAttempted=True,bakeReturned=True,fileObserved=True,fileExists=True,fileBytes=102400,textureObserved=True,textureExists=True,width=128,height=128,mipCount=8,formatCode=17,sourceWidth=128,sourceHeight=768,rangeObserved=True,rangeFinite=True,pixelSampleCount=98304,maxChannelRange=.5,guidObserved=True,guidPresent=True,guidMatches=True,metaObserved=True,metaExists=True,metaBytes=3000)
        by_stage[306].update(sceneObserved=True,sceneValid=True,sceneLoaded=True,activeMatches=True)
        by_stage[311].update(digestCompared=True,digestSame=True,changedInputCount=0,changedInputKinds=0)
    next(e for e in value['events'] if e['stageCode']==325).update(digestCompared=True,digestSame=True,changedInputCount=0,changedInputKinds=0)
    return value


def failed():
    value=receipt('FAILED');value.update(cacheHit=False,firstFailureStage=102,firstFailureCode='BAKE_RETURNED_FALSE',firstExceptionKind='REQUIRE',failureCount=2)
    value['events']=[event(10,0),event(101,1,bakeIndex=0,bakeAttempted=True),event(102,2,bakeIndex=0,bakeAttempted=True,fileObserved=True),event(102,3,bakeIndex=0,bakeAttempted=True,fileObserved=True,errorCode='BAKE_RETURNED_FALSE',exceptionKind='REQUIRE'),event(304,4),event(304,5,errorCode='UNCLASSIFIED_NATIVE_EXCEPTION',exceptionKind='UNITY'),event(499,6)]
    return value


class ReflectionProgressTests(unittest.TestCase):
    def validate(self,value):return progress.validate_progress(value,IDENT)
    def export(self,value):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        path=root/progress.visual.TASK/'artifacts/visual-candidate'/progress.NAME;path.parent.mkdir(parents=True);raw=value if isinstance(value,bytes) else json.dumps(value).encode();path.write_bytes(raw)
        dest=progress.visual.outdir(root)/progress.NAME
        with patch.dict(os.environ,ENV),patch.object(progress.visual,'identity',return_value=IDENT):
            try:progress.export_progress(root)
            except ValueError:return dest,raw,False
        return dest,raw,True
    def test_cache_and_cold_completion_validated_with_actual_observation_fields(self):
        for cold in (False,True):
            value=receipt(cold=cold);self.assertEqual(self.validate(value),value)
            dest,raw,ok=self.export(value);self.assertTrue(ok);self.assertEqual(dest.read_bytes(),raw)
    def test_failed_and_running_preserved_but_cannot_pass_gate(self):
        for value in (failed(),dict(receipt(),status='RUNNING')):
            dest,raw,ok=self.export(value);self.assertFalse(ok);self.assertEqual(dest.read_bytes(),raw)
    def test_diagnostic_write_failure_never_becomes_native_success_claim(self):
        value=receipt();value['diagnosticWriteFailed']=True
        dest,raw,ok=self.export(value);self.assertFalse(ok);self.assertEqual(dest.read_bytes(),raw)
        value=failed();value['diagnosticWriteFailed']=True;self.validate(value)
    def test_first_failure_survives_later_cleanup_error(self):
        value=failed();self.validate(value)
        for key,bad in [('firstFailureStage',304),('firstFailureCode','UNCLASSIFIED_NATIVE_EXCEPTION'),('firstExceptionKind','UNITY'),('failureCount',1)]:
            changed=copy.deepcopy(value);changed[key]=bad
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(changed)
    def test_wrong_source_run_attempt_scope_rejected(self):
        for key in ('sourceCommit','runId','runAttempt','scope'):
            value=receipt();value[key]='wrong'
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(value)
    def test_unknown_fields_and_free_text_never_export(self):
        for change in [lambda v:v.update(rawLog='SYNTHETIC_PRIVATE'),lambda v:v['events'][0].update(message='SYNTHETIC_PRIVATE'),lambda v:v['events'][0].update(errorCode='SYNTHETIC_PRIVATE'),lambda v:v['events'][0].update(exceptionKind='SYNTHETIC_PRIVATE')]:
            value=receipt();change(value);dest,raw,ok=self.export(value);self.assertFalse(ok);self.assertFalse(dest.exists())
    def test_duplicate_json_keys_rejected_in_root_and_event(self):
        raw=json.dumps(receipt())
        for changed in [raw.replace('"schemaVersion": 1','"schemaVersion": "SYNTHETIC_PRIVATE", "schemaVersion": 1',1),raw.replace('"stageCode": 10','"stageCode": "SYNTHETIC_PRIVATE", "stageCode": 10',1)]:
            dest,_,ok=self.export(changed.encode());self.assertFalse(ok);self.assertFalse(dest.exists())
    def test_unknown_stage_enum_count_and_size_rejected(self):
        for change in [lambda v:v['events'][0].update(stageCode=999),lambda v:v.update(events=[]),lambda v:v.update(events=[event(10)]*65),lambda v:v['events'][0].update(changedInputKinds=128)]:
            value=receipt();change(value)
            with self.assertRaises(ValueError):self.validate(value)
        dest,_,ok=self.export(b' '*65537);self.assertFalse(ok);self.assertFalse(dest.exists())
    def test_numeric_types_and_monotonic_time_and_stage_required(self):
        changes=[lambda v:v.update(elapsedMs=-1),lambda v:v.update(elapsedMs=3600001),lambda v:v.update(cacheHit=1),lambda v:v.update(diagnosticWriteFailed=0),lambda v:v['events'][0].update(width=True),lambda v:v['events'][0].update(sceneObserved=1),lambda v:v['events'][0].update(maxChannelRange=float('nan')),lambda v:v['events'][0].update(maxChannelRange=float('inf')),lambda v:v['events'][0].update(fileBytes=9007199254740992),lambda v:v['events'][1].update(elapsedMs=-1),lambda v:v['events'][3].update(stageCode=20)]
        for change in changes:
            value=receipt();change(value)
            with self.assertRaises(ValueError):self.validate(value)
    def test_unknown_observations_cannot_be_fabricated_zero_or_true(self):
        for change in [dict(width=0),dict(fileBytes=0),dict(metaBytes=0),dict(sceneValid=True),dict(activeMatches=True),dict(fileExists=True),dict(textureExists=True),dict(bakeReturned=True),dict(rangeFinite=True),dict(maxChannelRange=0),dict(guidMatches=True),dict(digestSame=True),dict(changedInputCount=0)]:
            value=receipt();value['events'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate(value)
    def test_complete_cannot_hide_failure_missing_stage_wrong_cube_or_restore(self):
        values=[]
        value=failed();value['status']='COMPLETE';values.append(value)
        value=receipt(cold=True);value['events']=[e for e in value['events'] if e['stageCode']!=112];values.append(value)
        for stage,changes in [(112,dict(width=64)),(212,dict(formatCode=1)),(306,dict(activeMatches=False)),(311,dict(digestSame=False))]:
            value=receipt(cold=True);next(e for e in value['events'] if e['stageCode']==stage).update(changes);values.append(value)
        for value in values:
            with self.assertRaises(ValueError):self.validate(value)
    def test_stale_export_removed_and_source_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV),patch.object(progress.visual,'identity',return_value=IDENT):
            root=Path(d);dest=progress.visual.outdir(root)/progress.NAME;dest.parent.mkdir(parents=True);dest.write_text('STALE')
            source=root/progress.visual.TASK/'artifacts/visual-candidate'/progress.NAME;source.parent.mkdir(parents=True);other=root/'other';other.write_text(json.dumps(receipt()));source.symlink_to(other)
            with self.assertRaises(ValueError):progress.export_progress(root)
            self.assertFalse(dest.exists())
            source.unlink();source.write_text('{}')
            with self.assertRaises(ValueError):progress.export_progress(root)
            self.assertFalse(dest.exists())
    def test_cli_prints_only_fixed_failure_no_traceback(self):
        result=subprocess.run([sys.executable,progress.__file__],capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(result.returncode,1);self.assertEqual(result.stdout,'REFLECTION_PREPARATION_DIAGNOSTIC_REJECTED\n');self.assertEqual(result.stderr,'')
    def test_workflow_single_fixed_sidecar_and_existing_gates_kept(self):
        root=Path(__file__).resolve().parents[3];workflow=(root/progress.visual.WORKFLOW).read_text()
        self.assertEqual(workflow.count('scripts/reflection_progress_ci.py'),1);self.assertEqual(workflow.count('/evidence/visual-candidate/reflection-progress.json'),1)
        self.assertIn('scripts/test_reflection_progress_ci.py -v',workflow)
        self.assertIn('scripts/reflection_bake_ci.py',workflow);self.assertIn('scripts/visual_candidate_ci.py captures',workflow)
        self.assertNotIn('*.json',workflow);self.assertEqual(workflow.count('secrets.'),3)
        self.assertEqual(len(progress.visual.FRAMES),23)
    def test_producer_enum_fields_gate_and_best_effort_match(self):
        root=Path(__file__).resolve().parents[3];source=(root/progress.visual.TASK/'unity/Assets/G3/Editor/G3ShopReflectionBaker.cs').read_text()
        enum=source[source.index('enum FailureCode'):source.index('sealed class BakeFailure')]
        codes=set(re.findall(r'\b[A-Z][A-Z_]+\b',enum));self.assertEqual(codes,progress.ERRORS)
        classes={}
        for name in ('TraceReceipt','TraceEvent'):
            text=source.split('sealed class '+name,1)[1].split('\n        }',1)[0]
            fields=set()
            for group in re.findall(r'public (?:int|long|float|bool|string) ([^;]+);',text):
                for field in group.split(','):fields.add(field.split('=')[0].strip())
            if name=='TraceReceipt':fields.add('events')
            classes[name]=fields
        self.assertEqual(classes['TraceReceipt'],progress.ROOT_FIELDS);self.assertEqual(classes['TraceEvent'],progress.EVENT_FIELDS)
        self.assertIn('args[assembly+1]!="Lottery.G3.VisualCandidate.Tests"',source)
        self.assertIn('JsonUtility.ToJson(receipt,false)',source);self.assertIn('>65536',source);self.assertIn('events.Count>=64',source)
        finish=source.split('public void Finish()',1)[1].split('[Serializable] sealed class TraceReceipt',1)[0]
        self.assertNotIn('throw ',finish);self.assertIn('diagnosticWriteFailed',source)
        self.assertIn('trace?.ClearSceneObservation();trace?.Mark(304)',source)

    def test_postsave_stage_required_for_cold_and_cache(self):
        for cold in (False,True):
            for stage in (324,325):
                value=receipt(cold=cold);value['events']=[e for e in value['events'] if e['stageCode']!=stage]
                with self.subTest(cold=cold,stage=stage),self.assertRaises(ValueError):self.validate(value)
    def test_postsave_digest_false_or_unknown_cannot_complete(self):
        for cold in (False,True):
            for patch_event in [dict(digestSame=False,changedInputCount=1,changedInputKinds=1),dict(digestCompared=False,digestSame=False,changedInputCount=-1,changedInputKinds=0)]:
                value=receipt(cold=cold);next(e for e in value['events'] if e['stageCode']==325).update(patch_event)
                with self.assertRaises(ValueError):self.validate(value)
    def test_postsave_changed_inputs_preserved_as_failure_not_success(self):
        value=receipt('FAILED',cold=True);value['events']=[e for e in value['events'] if e['stageCode']<325]
        value['events'].append(event(325,70,digestCompared=True,digestSame=False,changedInputCount=1,changedInputKinds=64,errorCode='SOURCE_DIGEST_CHANGED',exceptionKind='REQUIRE'))
        value.update(firstFailureStage=325,firstFailureCode='SOURCE_DIGEST_CHANGED',firstExceptionKind='REQUIRE',failureCount=1)
        self.validate(value);dest,raw,ok=self.export(value);self.assertFalse(ok);self.assertEqual(dest.read_bytes(),raw)
    def test_postsave_read_failure_preserves_unknown_measurement_and_original_error(self):
        value=receipt('FAILED');value['events']=[e for e in value['events'] if e['stageCode']<324]
        value['events'].append(event(324,70,errorCode='UNCLASSIFIED_NATIVE_EXCEPTION',exceptionKind='IO'))
        value.update(firstFailureStage=324,firstFailureCode='UNCLASSIFIED_NATIVE_EXCEPTION',firstExceptionKind='IO',failureCount=1)
        self.validate(value);dest,raw,ok=self.export(value);self.assertFalse(ok);self.assertEqual(dest.read_bytes(),raw)
    def test_source_receipt_hashes_share_snapshot_and_final_check_follows_save(self):
        root=Path(__file__).resolve().parents[3];source=(root/progress.visual.TASK/'unity/Assets/G3/Editor/G3ShopReflectionBaker.cs').read_text()
        body=source.split('static void PrepareObserved',1)[1].split('static void CleanupBake',1)[0]
        self.assertIn('receipt.runtimeDependencyHash=beforeInputs["DEPENDENCY|"+DependencyRoots[0]]',body)
        self.assertIn('receipt.pipelineDependencyHash=beforeInputs["DEPENDENCY|"+DependencyRoots[1]]',body)
        self.assertNotIn('GetAssetDependencyHash',body)
        self.assertLess(body.index('AssetDatabase.SaveAssets();trace?.Mark(323)'),body.index('trace?.Mark(324)'))
        self.assertIn('ComputeDigest(out var finalInputs)==digest',body);self.assertIn('ObserveInputChanges(beforeInputs,finalInputs)',body)
        self.assertNotIn('sourceDigest=ComputeDigest',body);self.assertEqual(body.count('sourceDigest=digest'),1)
    def test_source_invalidates_complete_receipt_on_any_final_verification_failure(self):
        root=Path(__file__).resolve().parents[3];source=(root/progress.visual.TASK/'unity/Assets/G3/Editor/G3ShopReflectionBaker.cs').read_text()
        final=source.split('bool finalValidated=false;',1)[1].split('static void CleanupBake',1)[0]
        self.assertIn('RunPreparationWithCleanup',final);self.assertIn('()=>Observed(trace,()=>{',final)
        self.assertIn('AssetDatabase.SaveAssets();trace?.Mark(323)',final)
        self.assertEqual(final.count('AssetDatabase.ImportAsset(ReceiptPath,ImportAssetOptions.ForceUpdate)'),2)
        self.assertIn('if(!finalSame)throw new BakeFailure(FailureCode.SOURCE_DIGEST_CHANGED);',final)
        self.assertLess(final.index('if(!finalSame)throw'),final.index('finalValidated=true;'))
        self.assertIn('if(!finalValidated){File.WriteAllText(ReceiptPath,',final);self.assertIn('BAKE_INPUT_CHANGED',final)
        self.assertNotIn('File.Delete',final);self.assertNotIn('while(',final);self.assertNotIn('sourceDigest=',final)
    def test_extended_cold_path_stays_within_existing_event_and_byte_limits(self):
        value=receipt(cold=True);self.validate(value);self.assertEqual(len(value['events']),57)
        self.assertLessEqual(len(json.dumps(value).encode()),65536);self.assertLessEqual(len(value['events']),64)


if __name__=='__main__':unittest.main()
