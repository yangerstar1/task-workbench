#!/usr/bin/env python3
"""Fixed material-initialization predicate receipt. Never native logs or asset values."""
import os,re
from pathlib import Path
import visual_candidate_ci as visual
import reflection_bake_ci as reflection
NAME='material-initialization-progress.json'
LIMIT=8192
SCOPE='MATERIAL_INITIALIZATION_DIAGNOSTIC_NOT_TEST_PASS'
STAGES=frozenset((1,2,10,11,12,20,21,22,23,24,30,31,32,33,34,35,36,37,38,39,40))
KINDS=frozenset(('NONE','INVALID_OPERATION','ARGUMENT','IO','ACCESS','UNITY','NULL_REFERENCE','AGGREGATE','OTHER'))
FIELDS=frozenset(('smoothnessObserved','smoothnessMaterialId','actualSmoothnessBits','expectedSmoothnessBits','schemaVersion','scope','status','sourceCommit','runId','runAttempt','stageCode','materialId','materialsCompleted','firstFailureStage','firstFailureMaterial','predicateCode','slotIndex','exceptionKind','diagnosticWriteFailed','elapsedMs','completedBits'))
PREDICATES={1: 'AUTHOR_SHADER', 2: 'AUTHOR_BASE_COLOR', 3: 'AUTHOR_BASE_MAP', 4: 'AUTHOR_NORMAL_MAP', 5: 'AUTHOR_PACKED_MAP', 6: 'AUTHOR_EMISSION_MAP', 7: 'AUTHOR_METALLIC', 8: 'AUTHOR_SMOOTHNESS', 9: 'AUTHOR_SMOOTHNESS_CHANNEL', 10: 'AUTHOR_NORMAL_STRENGTH', 11: 'AUTHOR_BASE_SCALE', 12: 'AUTHOR_SURFACE', 13: 'AUTHOR_EMISSION_COLOR', 14: 'AUTHOR_CULL', 15: 'DETAIL_ALBEDO_ABSENT', 16: 'DETAIL_NORMAL_ABSENT', 17: 'DETAIL_MULX2_OFF', 18: 'DETAIL_SCALED_OFF', 19: 'FINAL_SHADER', 20: 'FINAL_BASE_COLOR', 21: 'FINAL_EMISSION_COLOR', 22: 'FINAL_TEXTURE_REFERENCE', 23: 'FINAL_TEXTURE_SCALE', 24: 'FINAL_TEXTURE_OFFSET', 25: 'FINAL_FLOAT_PRESENCE', 26: 'FINAL_FLOAT_VALUE', 27: 'ALIAS_TEXTURE', 28: 'ALIAS_SCALE', 29: 'ALIAS_OFFSET', 30: 'ALIAS_COLOR', 31: 'NORMAL_KEYWORD', 32: 'PACKED_KEYWORD', 33: 'EMISSION_KEYWORD', 34: 'TRANSPARENT_KEYWORD', 35: 'ALPHA_TEST_OFF', 36: 'ALPHA_PREMULTIPLY_OFF', 37: 'ALPHA_MODULATE_OFF', 38: 'ALBEDO_SMOOTHNESS_OFF', 39: 'SOURCE_BLEND', 40: 'DEST_BLEND', 41: 'DEPTH_WRITE', 42: 'RENDER_QUEUE', 43: 'RENDER_TAG', 44: 'GI_FLAGS', 45: 'DOUBLE_SIDED_GI', 46: 'OWNED_MATERIAL_IDENTITY', 47: 'OWNED_MATERIAL_STATE'}
require=visual.require

def integer(x,lo,hi):return type(x) is int and lo<=x<=hi

def validate(value,ident):
    require(type(value) is dict and set(value)==FIELDS,'MATERIAL_INITIALIZATION_FIELDS_REJECTED')
    require(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['scope']==SCOPE,'MATERIAL_INITIALIZATION_SCHEMA_REJECTED')
    for k in ('sourceCommit','runId','runAttempt'):require(value[k]==ident[k],'MATERIAL_INITIALIZATION_IDENTITY_REJECTED')
    require(value['status'] in ('RUNNING','COMPLETE','FAILED') and type(value['diagnosticWriteFailed']) is bool,'MATERIAL_INITIALIZATION_STATUS_REJECTED')
    require(type(value['stageCode']) is int and value['stageCode'] in STAGES and type(value['exceptionKind']) is str and value['exceptionKind'] in KINDS,'MATERIAL_INITIALIZATION_ENUM_REJECTED')
    require(integer(value['materialId'],-1,34) and integer(value['firstFailureMaterial'],-1,34) and integer(value['materialsCompleted'],0,35) and integer(value['elapsedMs'],0,3600000) and integer(value['completedBits'],0,(1<<35)-1),'MATERIAL_INITIALIZATION_NUMBER_REJECTED')
    require(value['materialsCompleted']==value['completedBits'].bit_count(),'MATERIAL_INITIALIZATION_COUNT_REJECTED')
    code=value['predicateCode'];slot=value['slotIndex'];require(integer(code,0,47) and integer(slot,-1,6),'MATERIAL_INITIALIZATION_PREDICATE_REJECTED')
    require(type(value['firstFailureStage']) is int and value['firstFailureStage'] in STAGES|{-1},'MATERIAL_INITIALIZATION_FAILURE_STAGE_REJECTED')
    if value['status']=='FAILED':
        require(value['firstFailureStage']==value['stageCode'] and value['firstFailureMaterial']==value['materialId'] and value['exceptionKind']!='NONE','MATERIAL_INITIALIZATION_FAILURE_REJECTED')
    else:
        require((value['firstFailureStage'],value['firstFailureMaterial'],code,slot,value['exceptionKind'])==(-1,-1,0,-1,'NONE'),'MATERIAL_INITIALIZATION_INVENTED_FAILURE')
    if code:
        require(value['status']=='FAILED' and value['exceptionKind']=='INVALID_OPERATION' and (value['firstFailureMaterial']>=0 or code==46) and (value['firstFailureStage'] in (35,36,37,38,39) if code>=46 else value['firstFailureStage']==(20 if code<=18 else 22)),'MATERIAL_INITIALIZATION_CONTRACT_CONTEXT_REJECTED')
        require(0<=slot<=3 if code in (22,23,24) else 0<=slot<=6 if code in (25,26,47) else slot==-1,'MATERIAL_INITIALIZATION_SLOT_REJECTED')
    else:require(slot==-1,'MATERIAL_INITIALIZATION_UNKNOWN_SLOT_REJECTED')
    if value['status']=='COMPLETE':
        require(value['stageCode']==40 and value['materialId']==-1 and value['materialsCompleted']==35 and value['completedBits']==(1<<35)-1,'MATERIAL_INITIALIZATION_COMPLETENESS_REJECTED')
    require(type(value['smoothnessObserved']) is bool and integer(value['smoothnessMaterialId'],-1,34) and all(integer(value[k],0,4294967295) for k in ('actualSmoothnessBits','expectedSmoothnessBits')),'MATERIAL_INITIALIZATION_FLOAT_BITS_REJECTED')
    observed=value['smoothnessObserved'];actual=value['actualSmoothnessBits'];expected=value['expectedSmoothnessBits'];mid=value['smoothnessMaterialId']
    if observed:
        require(mid>=0,'MATERIAL_INITIALIZATION_FLOAT_CONTEXT_REJECTED')
        equal=(actual&0x7f800000)!=0x7f800000 and (expected&0x7f800000)!=0x7f800000 and actual==expected
        if code==8:require(mid==value['materialId'] and not equal,'MATERIAL_INITIALIZATION_FLOAT_FAILURE_REJECTED')
        else:require(equal,'MATERIAL_INITIALIZATION_FLOAT_SUCCESS_REJECTED')
    else:
        require((mid,actual,expected)==(-1,0,0) and code!=8 and value['status']!='COMPLETE','MATERIAL_INITIALIZATION_FLOAT_MISSING_REJECTED')
    return value

def export(root):
    dest=visual.outdir(root)/NAME
    require(dest.parent.resolve()==dest.parent.absolute(),'MATERIAL_INITIALIZATION_PATH_REJECTED')
    if dest.exists() or dest.is_symlink():
        require(dest.is_file() or dest.is_symlink(),'MATERIAL_INITIALIZATION_STALE_REJECTED');dest.unlink()
    source=root/visual.TASK/'artifacts/visual-candidate'/NAME
    require(source.resolve()==source.absolute(),'MATERIAL_INITIALIZATION_PATH_REJECTED')
    ident=visual.identity(root)
    require(visual.HEX40.fullmatch(ident.get('sourceCommit','')) and visual.HEX40.fullmatch(ident.get('reviewedCandidateCommit','')) and all(type(ident.get(k)) is str and re.fullmatch(r'[1-9][0-9]{0,19}',ident[k]) for k in ('runId','runAttempt')),'MATERIAL_INITIALIZATION_IDENTITY_REJECTED')
    require(ident['runId']==os.environ.get('GITHUB_RUN_ID') and ident['runAttempt']==os.environ.get('GITHUB_RUN_ATTEMPT'),'MATERIAL_INITIALIZATION_RUN_REJECTED')
    raw=visual.bounded.bounded_read(source,LIMIT);v=validate(reflection.load_receipt(raw),ident)
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    print('MATERIAL_INITIALIZATION_OBSERVATIONS_PRESERVED_NOT_TEST_PASS')
    require(v['status']=='COMPLETE' and not v['diagnosticWriteFailed'],'MATERIAL_INITIALIZATION_INCOMPLETE')

def main():
    try:export(Path(__file__).resolve().parents[3]);return 0
    except BaseException:print('MATERIAL_INITIALIZATION_DIAGNOSTIC_REJECTED');return 1
if __name__=='__main__':raise SystemExit(main())
