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
    value.update({k:0 for k in progress.CHANGE_BITS});value.update(changedOther=extra.get("changedInputCount",0) if extra.get("changedInputCount",0)>0 else 0)
    value.update(extra);return value


def audit_for(value):
    observed={e['stageCode'] for e in value['events']}
    ready=20 in observed
    value['materialAudit']=dict(ready=ready,error=not ready,missingBits=0,stages=sum(1<<i for i,s in enumerate(progress.MATERIAL_STAGES) if s in observed) if ready else 0,changedBits=0,overflow=0,records=[])
    if not ready:value['diagnosticWriteFailed']=True
    return value


def receipt(status='COMPLETE',cold=False):
    stages=sorted(progress.STAGES-{499}) if cold else [10,20,21,30,320,321,322,323,324,325,400]
    value=dict(startedUtc="2026-10-13T17:30:00.1234567Z",schemaVersion=1,scope=progress.SCOPE,sourceCommit=IDENT['sourceCommit'],runId='123',runAttempt='1',status=status,cacheHit=not cold,diagnosticWriteFailed=False,firstFailureStage=-1,firstFailureCode='NONE',firstExceptionKind='NONE',failureCount=0,elapsedMs=100,events=[event(stage,n) for n,stage in enumerate(stages)])
    if cold:
        by_stage={e['stageCode']:e for e in value['events']};by_stage[81].update(captureRenderers=39,captureTriangles=70000)
        for stage,index in ((112,0),(212,1)):
            by_stage[stage].update(bakeIndex=index,bakeAttempted=True,bakeReturned=True,fileObserved=True,fileExists=True,fileBytes=102400,textureObserved=True,textureExists=True,width=128,height=128,mipCount=8,formatCode=17,sourceWidth=128,sourceHeight=768,rangeObserved=True,rangeFinite=True,pixelSampleCount=98304,maxChannelRange=.5,guidObserved=True,guidPresent=True,guidMatches=True,metaObserved=True,metaExists=True,metaBytes=3000)
        by_stage[306].update(sceneObserved=True,sceneValid=True,sceneLoaded=True,activeMatches=True)
        by_stage[311].update(digestCompared=True,digestSame=True,changedInputCount=0,changedInputKinds=0)
    next(e for e in value['events'] if e['stageCode']==325).update(digestCompared=True,digestSame=True,changedInputCount=0,changedInputKinds=0)
    return audit_for(value)


def failed():
    value=receipt('FAILED');value.update(cacheHit=False,firstFailureStage=102,firstFailureCode='BAKE_RETURNED_FALSE',firstExceptionKind='REQUIRE',failureCount=2)
    value['events']=[event(10,0),event(101,1,bakeIndex=0,bakeAttempted=True),event(102,2,bakeIndex=0,bakeAttempted=True,fileObserved=True),event(102,3,bakeIndex=0,bakeAttempted=True,fileObserved=True,errorCode='BAKE_RETURNED_FALSE',exceptionKind='REQUIRE'),event(304,4),event(304,5,errorCode='UNCLASSIFIED_NATIVE_EXCEPTION',exceptionKind='UNITY'),event(499,6)]
    return audit_for(value)


def material_state():
    value={k:0 for k in progress.STATE_FIELDS};value.update(queue=2000,version=-1,instancing=False,doubleSided=False,serialized='0'*64,sub='0'*64,disk='0'*64)
    return value


def changed_receipt(ids=(32,33)):
    value=receipt(cold=True);audit=value['materialAudit']
    for id in ids:
        a=material_state();b=copy.deepcopy(a);b['gi']=4
        audit['records'].append(dict(id=id,firstStage=102,lastStage=325,changeBits=1,lastBits=1,before=a,first=b,last=copy.deepcopy(b)));audit['changedBits']|=1<<id
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
            if name=='TraceReceipt':fields.update(('events','materialAudit'))
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
        audit_for(value);self.validate(value);dest,raw,ok=self.export(value);self.assertFalse(ok);self.assertEqual(dest.read_bytes(),raw)
    def test_postsave_read_failure_preserves_unknown_measurement_and_original_error(self):
        value=receipt('FAILED');value['events']=[e for e in value['events'] if e['stageCode']<324]
        value['events'].append(event(324,70,errorCode='UNCLASSIFIED_NATIVE_EXCEPTION',exceptionKind='IO'))
        value.update(firstFailureStage=324,firstFailureCode='UNCLASSIFIED_NATIVE_EXCEPTION',firstExceptionKind='IO',failureCount=1)
        audit_for(value);self.validate(value);dest,raw,ok=self.export(value);self.assertFalse(ok);self.assertEqual(dest.read_bytes(),raw)
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

    def test_material_ids_exact_frozen_source_table(self):
        root=Path(__file__).resolve().parents[3];shop=root/progress.visual.TASK/'unity/Assets/G3/Shop/Resources/G3/Shop'
        names=tuple(x['name'] for x in json.loads((shop/'materials.json').read_text())['materials'])
        self.assertTrue(set(progress.MATERIAL_IDS)<=set(names));self.assertEqual(len(progress.MATERIAL_IDS),34);self.assertEqual(len(set(progress.MATERIAL_IDS)),34)
        source=(root/progress.visual.TASK/'unity/Assets/G3/Editor/G3ShopReflectionBaker.cs').read_text()
        table=source.split('DiagnosticMaterials={',1)[1].split('};',1)[0]
        self.assertEqual(tuple(re.findall(r'"([A-Za-z0-9_]+)"',table)),progress.MATERIAL_IDS)
    def test_all_fixed_material_roles_and_high_bit_export(self):
        for key in progress.CHANGE_BITS:
            for idx in (0,32,33):
                value=receipt('FAILED');value['events']=[event(10),event(325,70,digestCompared=True,digestSame=False,changedInputCount=1,changedInputKinds=2,changedOther=0,**{key:1<<idx},errorCode='SOURCE_DIGEST_CHANGED',exceptionKind='REQUIRE')]
                value.update(firstFailureStage=325,firstFailureCode='SOURCE_DIGEST_CHANGED',firstExceptionKind='REQUIRE',failureCount=1)
                audit_for(value);self.validate(value);dest,raw,ok=self.export(value);self.assertFalse(ok);self.assertEqual(dest.read_bytes(),raw)
    def test_input_id_bounds_and_count_rejected(self):
        for patch_event in [dict(matBits=-1),dict(matBits=True),dict(matBits=1<<34),dict(packBits=1),dict(changedOther=1),dict(changedOther='RAW_PRIVATE_PATH')]:
            value=receipt();value['events'][0].update(patch_event)
            with self.assertRaises(ValueError):self.validate(value)
    def test_material_bit_requires_material_category(self):
        value=receipt('FAILED');value['events']=[event(10),event(325,70,digestCompared=True,changedInputCount=1,changedInputKinds=1,matBits=1,changedOther=0)]
        with self.assertRaises(ValueError):self.validate(value)
    def test_dirty_unknown_bounds_stage_and_bool_rejected(self):
        for patch_event in [dict(dirtyMatBits=0),dict(dirtyStage=325,dirtyMatBits=0,dirtyPackBits=0),dict(dirtyStage=30,dirtyMatBits=0,dirtyPackBits=0),dict(dirtyStage=21,dirtyMatBits=1<<34,dirtyPackBits=0),dict(dirtyStage=21,dirtyMatBits=True,dirtyPackBits=0)]:
            value=receipt();value['events'][1].update(patch_event)
            with self.assertRaises(ValueError):self.validate(value)
    def test_dirty_observation_is_not_success_or_changed_bytes(self):
        value=receipt();e=next(x for x in value['events'] if x['stageCode']==325);e.update(dirtyStage=325,dirtyMatBits=1<<32,dirtyPackBits=1)
        self.validate(value) # Dirty flags alone are observations, not a changed-file verdict.
        e.update(digestSame=False,changedInputCount=1,changedOther=1,changedInputKinds=32)
        with self.assertRaises(ValueError):self.validate(value)
    def test_dirty_source_is_loaded_only_and_does_not_save_or_load(self):
        root=Path(__file__).resolve().parents[3];source=(root/progress.visual.TASK/'unity/Assets/G3/Editor/G3ShopReflectionBaker.cs').read_text()
        body=source.split('void ObserveLoadedDirty',1)[1].split('public void Mark',1)[0]
        self.assertIn('Resources.FindObjectsOfTypeAll<Material>()',body);self.assertIn('EditorUtility.IsDirty(asset)',body)
        for forbidden in ('LoadAsset','SaveAssets','SetDirty','Refresh(','Debug.Log','error.Message','GetPixels'):self.assertNotIn(forbidden,body)
        self.assertIn('writeFailed=true',body)
    def test_expanded_normal_cold_receipt_with_dirty_highbits_within_cap(self):
        value=receipt(cold=True)
        for e in value['events']:
            if e['stageCode']>=21:e.update(dirtyStage=21,dirtyMatBits=progress.BIT_LIMIT,dirtyPackBits=progress.BIT_LIMIT)
        self.validate(value);self.assertEqual(len(value['events']),57)
        self.assertLess(len(json.dumps(value,separators=(',',':')).encode()),progress.LIMIT)

    def test_started_utc_strict_format_calendar_and_range(self):
        for utc in [None,1,'RAW_TEXT','2026-10-13T17:30:00Z','2026-10-13T17:30:00.1234567+00:00','2026-02-30T17:30:00.1234567Z','2019-12-31T17:30:00.1234567Z','2100-01-01T00:00:00.1234567Z','2026-10-13T25:30:00.1234567Z','2026-10-13T17:30:00.1234567Z\n']:
            value=receipt();value['startedUtc']=utc
            with self.subTest(utc=utc),self.assertRaises(ValueError):self.validate(value)
    def test_started_utc_end_range_and_valid_leap_date(self):
        value=receipt();value['startedUtc']='2099-12-31T23:59:59.9999999Z';value['elapsedMs']=3600000
        with self.assertRaises(ValueError):self.validate(value)
        value=receipt();value['startedUtc']='2028-02-29T00:00:00.0000000Z';self.validate(value)
    def test_source_utc_is_fixed_invariant_root_only(self):
        root=Path(__file__).resolve().parents[3];source=(root/progress.visual.TASK/'unity/Assets/G3/Editor/G3ShopReflectionBaker.cs').read_text()
        self.assertEqual(source.count('DateTime.UtcNow.ToString("O",System.Globalization.CultureInfo.InvariantCulture)'),1)
        event=source.split('[Serializable] sealed class TraceEvent',1)[1]
        self.assertNotIn('startedUtc',event)

    def test_material_fixed_ids_34_and_appended_tea(self):
        self.assertEqual(progress.MATERIAL_IDS[32:],('Tool_Dock_Liner','Nearfield_Tea'))
        self.assertEqual(len(set(progress.MATERIAL_IDS)),34)
    def test_material_two_changed_ids_gi_diagnostic_not_gate_repair(self):
        value=changed_receipt();self.validate(value)
        self.assertEqual(value['materialAudit']['changedBits'],(1<<32)|(1<<33))
        # State changes are observations; strict source-digest verdict remains independent.
        e=next(e for e in value['events'] if e['stageCode']==325);e.update(digestSame=False,changedInputCount=2,changedOther=0,matBits=(1<<32)|(1<<33),changedInputKinds=2)
        with self.assertRaises(ValueError):self.validate(value)
    def test_material_all_nine_difference_categories(self):
        patches=[dict(gi=4),dict(instancing=True),dict(queue=2001),dict(keywords=1),dict(saved=1,present=1),dict(tags=1,present=64),dict(serialized='1'*64),dict(sub='1'*64),dict(disk='1'*64)]
        for i,patch_state in enumerate(patches):
            value=changed_receipt((32,));row=value['materialAudit']['records'][0];row['first']=dict(row['before'],**patch_state);row['last']=copy.deepcopy(row['first']);row['changeBits']=row['lastBits']=progress.material_difference(row['before'],row['first']);self.assertTrue(row['lastBits']&(1<<i));self.validate(value)
    def test_material_internal_unknown_serialization_and_restored_latest(self):
        value=changed_receipt((33,));r=value['materialAudit']['records'][0];r['first']=dict(r['before'],serialized='a'*64);r.update(changeBits=64,lastBits=0,last=copy.deepcopy(r['before']));self.validate(value)
    def test_material_unknown_fields_or_strings_not_exported(self):
        for mutate in [lambda v:v['materialAudit'].update(rawPath='PRIVATE'),lambda v:v['materialAudit']['records'][0].update(name='PRIVATE'),lambda v:v['materialAudit']['records'][0]['before'].update(yaml='PRIVATE'),lambda v:v['materialAudit']['records'][0]['before'].update(serialized='PRIVATE')]:
            v=changed_receipt();mutate(v);dest,raw,ok=self.export(v);self.assertFalse(ok);self.assertFalse(dest.exists())
    def test_material_ids_duplicates_count_and_masks_rejected(self):
        for mutate in [lambda a:a['records'][0].update(id=34),lambda a:a['records'][0].update(id=True),lambda a:a['records'][1].update(id=32),lambda a:a.update(changedBits=0),lambda a:a.update(records=a['records']*3),lambda a:a.update(overflow=1),lambda a:a.update(changedBits=1<<34)]:
            v=changed_receipt();mutate(v['materialAudit'])
            with self.assertRaises(ValueError):self.validate(v)
    def test_material_numeric_state_and_hash_bounds_rejected(self):
        for change in [dict(gi=8),dict(gi=True),dict(queue=5001),dict(keywords=65536),dict(unknownKeywords=257),dict(present=256),dict(instancing=1),dict(saved=-1),dict(saved=4294967296),dict(saved=True),dict(saved=1),dict(version=1025),dict(subCount=9),dict(versionCount=1),dict(serialized='a'*63),dict(disk='A'*64),dict(sub='a'*64+'\n')]:
            v=changed_receipt();v['materialAudit']['records'][0]['before'].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):self.validate(v)
    def test_material_known_subasset_version_and_unknown_count(self):
        v=changed_receipt((32,));r=v['materialAudit']['records'][0];r['first']=dict(r['before'],subCount=2,versionCount=1,otherSubCount=1,version=10,sub='b'*64);r['last']=copy.deepcopy(r['first']);r['changeBits']=r['lastBits']=128;self.validate(v)
    def test_material_record_difference_integrity(self):
        for mutate in [lambda r:r.update(changeBits=0),lambda r:r.update(lastBits=2),lambda r:r.update(first=copy.deepcopy(r['before'])),lambda r:r.update(changeBits=512),lambda r:r.update(firstStage=20),lambda r:r.update(firstStage=325,lastStage=102)]:
            v=changed_receipt();mutate(v['materialAudit']['records'][0])
            with self.assertRaises(ValueError):self.validate(v)
    def test_material_observation_missing_and_future_stages(self):
        for mutate in [lambda a:a.update(stages=0),lambda a:a.update(ready=False),lambda a:a.update(stages=1<<12),lambda a:a.update(missingBits=1),lambda a:a.update(error=True)]:
            v=receipt();mutate(v['materialAudit'])
            with self.assertRaises(ValueError):self.validate(v)
    def test_material_overflow_failure_flag_and_total(self):
        v=changed_receipt((0,1,32,33));v['materialAudit'].update(changedBits=v['materialAudit']['changedBits']|4,overflow=1);v['diagnosticWriteFailed']=True
        self.validate(v);dest,raw,ok=self.export(v);self.assertFalse(ok);self.assertEqual(dest.read_bytes(),raw)
        v['diagnosticWriteFailed']=False
        with self.assertRaises(ValueError):self.validate(v)
    def test_material_missing_loaded_refs_preserved_as_incomplete(self):
        v=receipt();v.update(diagnosticWriteFailed=True,status='RUNNING');v['materialAudit'].update(ready=False,error=True,missingBits=1<<33,stages=0);self.validate(v)
    def test_material_four_rows_cold_byte_budget(self):
        v=changed_receipt((0,1,32,33));self.validate(v)
        for e in v['events']:
            if e['stageCode']>=21:e.update(dirtyStage=21,dirtyMatBits=progress.BIT_LIMIT,dirtyPackBits=progress.BIT_LIMIT)
        raw=json.dumps(v,separators=(',',':')).encode();self.assertLess(len(raw),65536);self.assertEqual(len(v['events']),57)
    def test_material_producer_observer_has_no_load_save_or_validation(self):
        root=Path(__file__).resolve().parents[3];s=(root/progress.visual.TASK/'unity/Assets/G3/Editor/G3ShopReflectionBaker.cs').read_text()
        bodies=[s.split('void ObserveMaterialState',1)[1].split('void ObserveLoadedDirty',1)[0],s.split('static MaterialState ReadMaterialState',1)[1].split('static int MaterialDifference',1)[0]]
        for body in bodies:
            for forbidden in ('LoadAsset','SaveAssets','SaveAndReimport','ImportAsset','SetDirty','Refresh(','ValidateMaterial(','ApplyModifiedProperties','Debug.Log','error.Message'):self.assertNotIn(forbidden,body)
        self.assertIn('Resources.FindObjectsOfTypeAll<Material>()',bodies[0]);self.assertIn('snapshots[id]=ReadMaterialState',bodies[0]);self.assertIn('audit.records.Count<4',bodies[0]);self.assertIn('audit.overflow>0)writeFailed=true',bodies[0])
        self.assertIn('ObserveMaterialState(stage)',s);self.assertIn('p.contentHash',s);self.assertIn('EditorJsonUtility.ToJson(material,false)',s)
    def test_material_schema_producer_fields_and_stages_match(self):
        root=Path(__file__).resolve().parents[3];s=(root/progress.visual.TASK/'unity/Assets/G3/Editor/G3ShopReflectionBaker.cs').read_text()
        for name,expected,extra in [('MaterialState',progress.STATE_FIELDS,set()),('MaterialChange',progress.RECORD_FIELDS,{'before','first','last'}),('MaterialAudit',progress.AUDIT_FIELDS,{'records'})]:
            body=s.split('sealed class '+name,1)[1].split('\n        }',1)[0];fields=set(extra)
            for group in re.findall(r'public (?:int|long|bool|string) ([^;]+);',body):
                fields.update(field.split('=')[0].strip() for field in group.split(','))
            self.assertEqual(fields,expected)
        stages=s.split('MaterialStages={',1)[1].split('};',1)[0];self.assertEqual(tuple(map(int,stages.split(','))),progress.MATERIAL_STAGES)
    def test_material_duplicate_nested_key_rejected(self):
        raw=json.dumps(changed_receipt());raw=raw.replace('"gi": 0','"gi": "PRIVATE", "gi": 0',1)
        dest,_,ok=self.export(raw.encode());self.assertFalse(ok);self.assertFalse(dest.exists())


if __name__=='__main__':unittest.main()
