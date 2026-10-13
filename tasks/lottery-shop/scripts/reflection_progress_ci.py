#!/usr/bin/env python3
"""Fixed reflection preparation observations; no native logs or error text."""
import os
import math
from pathlib import Path
import visual_candidate_ci as visual
import reflection_bake_ci as baked

SCOPE = 'REFLECTION_PREPARATION_DIAGNOSTIC_NOT_VISUAL_PASS'
NAME = 'reflection-progress.json'
LIMIT = 65536
MAX_EVENTS = 64
require = visual.require


def integer(value, low, high):
    return type(value) is int and low <= value <= high


STAGES = frozenset({10, 400, 20, 21, 30, 40, 300, 301, 302, 303, 304, 305, 50, 51, 306, 310, 311, 60, 61, 190, 320, 321, 322, 323, 70, 71, 200, 201, 202, 203, 204, 205, 206, 207, 80, 81, 208, 209, 210, 211, 212, 90, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 499})
ERRORS = frozenset({'UNCLASSIFIED_NATIVE_EXCEPTION', 'SOURCE_INPUT_MISSING', 'BAKE_RETURNED_FALSE', 'EXR_DIMENSIONS', 'FIXED_FILE_MISSING_OR_SIZE', 'IN_PLAY_MODE', 'NONE', 'FINAL_TEXTURE_CONTRACT', 'HDR_NONFINITE', 'IMPORTER_EXTERNAL_REMAP', 'IMPORTER_MISSING', 'SOURCE_DEPENDENCY_MISSING', 'STATIC_FLAG_MISSING', 'RECEIPT_SIZE', 'HDR_FLAT_OR_RANGE', 'CACHE_ARTIFACT_MISMATCH', 'CLEANUP_PIPELINE_OR_SCENE', 'STATIC_MESH_MISSING', 'CLEANUP_LIGHTING', 'PROBE_CONFIG', 'GEOMETRY_BOUNDS', 'ISOLATION_CONFLICT', 'DIAGNOSTIC_WRITE_FAILURE', 'GUID_OWNERSHIP', 'CUBEMAP_LAYOUT', 'BUILD_IDENTITY_INVALID', 'STATIC_LAYER_MISMATCH', 'SOURCE_DIGEST_CHANGED', 'GUID_MISMATCH'})
KINDS = frozenset({'UNITY', 'ACCESS', 'NONE', 'NULL_REFERENCE', 'ARGUMENT', 'AGGREGATE', 'REQUIRE', 'IO', 'OTHER', 'NOT_SUPPORTED', 'INVALID_OPERATION'})
ROOT_FIELDS = frozenset({'elapsedMs', 'diagnosticWriteFailed', 'schemaVersion', 'events', 'scope', 'cacheHit', 'runId', 'runAttempt', 'sourceCommit', 'firstFailureCode', 'firstExceptionKind', 'failureCount', 'status', 'firstFailureStage'})
EVENT_FIELDS = frozenset({'stageCode', 'bakeAttempted', 'captureRenderers', 'textureExists', 'maxChannelRange', 'foreignProbes', 'sourceHeight', 'sceneObserved', 'sceneValid', 'errorCode', 'changedInputCount', 'elapsedMs', 'metaBytes', 'guidMatches', 'bakeReturned', 'rangeFinite', 'digestCompared', 'fileExists', 'width', 'activeMatches', 'foreignLights', 'guidObserved', 'guidPresent', 'sceneLoaded', 'fileObserved', 'exceptionKind', 'rangeObserved', 'textureObserved', 'mipCount', 'formatCode', 'foreignRenderers', 'sourceWidth', 'digestSame', 'pixelSampleCount', 'metaObserved', 'height', 'fileBytes', 'changedInputKinds', 'captureTriangles', 'metaExists', 'bakeIndex'})
BOOL_FIELDS = frozenset({'bakeAttempted', 'textureExists', 'sceneObserved', 'sceneValid', 'guidMatches', 'bakeReturned', 'rangeFinite', 'digestCompared', 'fileExists', 'activeMatches', 'guidObserved', 'guidPresent', 'sceneLoaded', 'fileObserved', 'rangeObserved', 'textureObserved', 'digestSame', 'metaObserved', 'metaExists'})
INT_FIELDS = frozenset({'stageCode', 'pixelSampleCount', 'height', 'captureRenderers', 'changedInputCount', 'changedInputKinds', 'mipCount', 'formatCode', 'foreignRenderers', 'foreignProbes', 'sourceWidth', 'width', 'sourceHeight', 'foreignLights', 'bakeIndex'})
LONG_FIELDS = frozenset({'fileBytes', 'metaBytes', 'captureTriangles'})


def validate_progress(receipt, ident):
    require(isinstance(receipt,dict) and set(receipt)==ROOT_FIELDS, 'REFLECTION_PROGRESS_FIELDS_REJECTED')
    require(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1 and receipt['scope']==SCOPE, 'REFLECTION_PROGRESS_SCHEMA_REJECTED')
    for key in ('sourceCommit','runId','runAttempt'):
        require(receipt[key]==ident[key], 'REFLECTION_PROGRESS_IDENTITY_REJECTED')
    require(receipt['status'] in ('RUNNING','COMPLETE','FAILED') and type(receipt['cacheHit']) is bool and type(receipt['diagnosticWriteFailed']) is bool and integer(receipt['elapsedMs'],0,3600000), 'REFLECTION_PROGRESS_STATUS_REJECTED')
    require(integer(receipt['failureCount'],0,MAX_EVENTS) and type(receipt['firstFailureStage']) is int and receipt['firstFailureStage'] in STAGES|{-1} and receipt['firstFailureCode'] in ERRORS and receipt['firstExceptionKind'] in KINDS, 'REFLECTION_PROGRESS_FIRST_FAILURE_REJECTED')
    events=receipt['events'];require(isinstance(events,list) and 1<=len(events)<=MAX_EVENTS, 'REFLECTION_PROGRESS_EVENT_COUNT_REJECTED')
    last_ms=0;last_stage=0; failures=[]
    for event in events:
        require(isinstance(event,dict) and set(event)==EVENT_FIELDS, 'REFLECTION_PROGRESS_EVENT_FIELDS_REJECTED')
        require(all(type(event[key]) is bool for key in BOOL_FIELDS), 'REFLECTION_PROGRESS_BOOL_REJECTED')
        require(all(integer(event[key],-1,2147483647) for key in INT_FIELDS) and all(integer(event[key],-1,9007199254740991) for key in LONG_FIELDS), 'REFLECTION_PROGRESS_NUMBER_REJECTED')
        require(event['stageCode'] in STAGES and event['stageCode']>=last_stage and event['bakeIndex'] in (-1,0,1) and 0<=event['changedInputKinds']<=127 and integer(event['elapsedMs'],last_ms,receipt['elapsedMs']), 'REFLECTION_PROGRESS_STAGE_CLOCK_REJECTED');last_ms=event['elapsedMs'];last_stage=event['stageCode']
        require(event['errorCode'] in ERRORS and event['exceptionKind'] in KINDS and (event['errorCode']=='NONE')==(event['exceptionKind']=='NONE'), 'REFLECTION_PROGRESS_ERROR_REJECTED')
        require(type(event['maxChannelRange']) in (int,float) and math.isfinite(event['maxChannelRange']) and -1<=event['maxChannelRange']<=131008, 'REFLECTION_PROGRESS_RANGE_REJECTED')
        if event['errorCode']!='NONE':failures.append(event)
        # Absence stays unknown, rather than becoming a fabricated zero or pass.
        require(event['sceneObserved'] or not(event['sceneValid'] or event['sceneLoaded'] or event['activeMatches']), 'REFLECTION_PROGRESS_SCENE_OBSERVATION_REJECTED')
        require(not event['sceneLoaded'] or event['sceneValid'], 'REFLECTION_PROGRESS_SCENE_REJECTED')
        require(not event['activeMatches'] or event['sceneLoaded'], 'REFLECTION_PROGRESS_ACTIVE_REJECTED')
        for prefix,size in (('file','fileBytes'),('meta','metaBytes')):
            require(not event[prefix+'Exists'] or event[prefix+'Observed'], 'REFLECTION_PROGRESS_FILE_OBSERVATION_REJECTED')
            require(event[size]>=0 if event[prefix+'Exists'] else event[size]==-1, 'REFLECTION_PROGRESS_FILE_SIZE_REJECTED')
        require(not event['textureExists'] or event['textureObserved'], 'REFLECTION_PROGRESS_TEXTURE_OBSERVATION_REJECTED')
        if not event['textureExists']:
            require(all(event[key]==-1 for key in ('width','height','mipCount','formatCode')), 'REFLECTION_PROGRESS_UNKNOWN_TEXTURE_REJECTED')
        else:require(all(event[key]>=0 for key in ('width','height','mipCount','formatCode')), 'REFLECTION_PROGRESS_TEXTURE_SIZE_REJECTED')
        require(not event['bakeReturned'] or event['bakeAttempted'], 'REFLECTION_PROGRESS_BAKE_RETURN_REJECTED')
        require(not event['rangeFinite'] or event['rangeObserved'], 'REFLECTION_PROGRESS_RANGE_OBSERVATION_REJECTED')
        require(event['maxChannelRange']>=0 if event['rangeFinite'] else event['maxChannelRange']==-1, 'REFLECTION_PROGRESS_UNKNOWN_RANGE_REJECTED')
        require(not event['guidPresent'] or event['guidObserved'], 'REFLECTION_PROGRESS_GUID_OBSERVATION_REJECTED')
        require(not event['guidMatches'] or event['guidPresent'], 'REFLECTION_PROGRESS_GUID_MATCH_REJECTED')
        if not event['digestCompared']:
            require(not event['digestSame'] and event['changedInputCount']==-1 and event['changedInputKinds']==0, 'REFLECTION_PROGRESS_UNKNOWN_DIGEST_REJECTED')
        else:
            require(event['changedInputCount']>=0 and (not event['digestSame'] or (event['changedInputCount']==0 and event['changedInputKinds']==0)), 'REFLECTION_PROGRESS_DIGEST_REJECTED')
    require(events[0]['stageCode']==10 and events[0]['errorCode']=='NONE', 'REFLECTION_PROGRESS_BEGIN_REJECTED')
    require(receipt['failureCount']==len(failures), 'REFLECTION_PROGRESS_FAILURE_COUNT_REJECTED')
    if failures:
        first=failures[0]
        require((receipt['firstFailureStage'],receipt['firstFailureCode'],receipt['firstExceptionKind'])==(first['stageCode'],first['errorCode'],first['exceptionKind']), 'REFLECTION_PROGRESS_FIRST_FAILURE_CHANGED')
    else:
        require((receipt['firstFailureStage'],receipt['firstFailureCode'],receipt['firstExceptionKind'])==(-1,'NONE','NONE'), 'REFLECTION_PROGRESS_INVENTED_FAILURE')
    if receipt['status']=='COMPLETE':
        require(not failures and events[-1]['stageCode']==400 and events[-1]['errorCode']=='NONE', 'REFLECTION_PROGRESS_COMPLETION_REJECTED')
        observed={event['stageCode'] for event in events}
        common={10,20,21,30,320,321,322,323,400}
        needed=common if receipt['cacheHit'] else STAGES-{499}
        require(needed<=observed and (not receipt['cacheHit'] or not observed.intersection(set(range(100,113))|set(range(200,213)))), 'REFLECTION_PROGRESS_COMPLETENESS_REJECTED')
        if not receipt['cacheHit']:
            by_stage={event['stageCode']:event for event in events}
            require(1<=by_stage[81]['captureRenderers']<=4096 and 1<=by_stage[81]['captureTriangles']<=2000000, 'REFLECTION_PROGRESS_COMPLETE_GEOMETRY_REJECTED')
            for stage in (112,212):
                e=by_stage[stage]
                require(all(e[k] for k in ('bakeAttempted','bakeReturned','fileObserved','fileExists','textureObserved','textureExists','rangeObserved','rangeFinite','guidObserved','guidPresent','guidMatches','metaObserved','metaExists')), 'REFLECTION_PROGRESS_COMPLETE_CUBE_OBSERVATION_REJECTED')
                require(e['width']==e['height']==128 and e['mipCount']==8 and e['formatCode']==17 and e['pixelSampleCount']==98304 and .01<e['maxChannelRange']<=65504 and 128<=e['sourceWidth']<=2048 and 128<=e['sourceHeight']<=2048 and 0<e['fileBytes']<=8388608 and 0<e['metaBytes']<=16384, 'REFLECTION_PROGRESS_COMPLETE_CUBE_REJECTED')
            require(by_stage[306]['sceneObserved'] and by_stage[306]['activeMatches'] and by_stage[311]['digestCompared'] and by_stage[311]['digestSame'], 'REFLECTION_PROGRESS_COMPLETE_RESTORE_OR_DIGEST_REJECTED')
    return receipt


def export_progress(root):
    source = root / visual.TASK / 'artifacts/visual-candidate' / NAME
    dest = visual.outdir(root) / NAME
    require(dest.parent.resolve() == dest.parent.absolute(), 'REFLECTION_PROGRESS_PATH_REJECTED')
    if dest.exists() or dest.is_symlink():
        require(dest.is_file() or dest.is_symlink(), 'REFLECTION_PROGRESS_STALE_REJECTED');dest.unlink()
    require(source.resolve() == source.absolute(), 'REFLECTION_PROGRESS_PATH_REJECTED')
    ident = visual.identity(root)
    require(ident['runId'] == os.environ.get('GITHUB_RUN_ID') and ident['runAttempt'] == os.environ.get('GITHUB_RUN_ATTEMPT'), 'REFLECTION_PROGRESS_RUN_REJECTED')
    raw = visual.bounded.bounded_read(source,LIMIT)
    receipt = validate_progress(baked.load_receipt(raw),ident)
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    print('REFLECTION_PREPARATION_OBSERVATIONS_PRESERVED_NOT_TEST_PASS')
    require(receipt['status'] == 'COMPLETE' and not receipt['diagnosticWriteFailed'], 'REFLECTION_PREPARATION_INCOMPLETE')


def main():
    try:
        export_progress(Path(__file__).resolve().parents[3]);return 0
    except BaseException:
        print('REFLECTION_PREPARATION_DIAGNOSTIC_REJECTED');return 1


if __name__ == '__main__':raise SystemExit(main())
