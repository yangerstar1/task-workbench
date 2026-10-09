"""Exact own-component and real pre/post paw evidence closure. No acceptance upgrades."""
import re
from pathlib import Path
SCRIPT='Assets/DesertRV/Runtime/PouncerPawContactConstraint.cs'
GUID='91bc621dee2e4fd39c36b41412fed003'
IDS=('fore.L','fore.R','hind.L','hind.R')
NATIVE_NAMES={'DesertRV.Tests.PouncerPawContactConstraintTests.'+n for n in ('CorrectsMeasuredTwentyFourMillimeterViolationAcrossSkinAndClaws', 'PreservesAnimatedDigitsWithMoreThanFourInfluences', 'ExcludesCrossSubtreeMixedVertices', 'FailedPostSolveRestoresWholePoseRotations', 'RepeatedSamePoseDoesNotAccumulateCorrection', 'PauseDoesNotWriteAndAnimatorRewriteCanBeCorrectedAgain', 'FailureRemainsLatchedUntilExplicitReset', 'UsesActorPhysicsSceneAndRejectsOtherSceneGround', 'RejectsIncompleteRendererInventory')}
CHAINS=[{'id': 'fore.L', 'upper': 'Pouncer_Rig/root/visual_body/pelvis/spine/chest/fore_upper.L', 'lower': 'Pouncer_Rig/root/visual_body/pelvis/spine/chest/fore_upper.L/fore_lower.L', 'paw': 'Pouncer_Rig/root/visual_body/pelvis/spine/chest/fore_upper.L/fore_lower.L/fore_paw.L'}, {'id': 'fore.R', 'upper': 'Pouncer_Rig/root/visual_body/pelvis/spine/chest/fore_upper.R', 'lower': 'Pouncer_Rig/root/visual_body/pelvis/spine/chest/fore_upper.R/fore_lower.R', 'paw': 'Pouncer_Rig/root/visual_body/pelvis/spine/chest/fore_upper.R/fore_lower.R/fore_paw.R'}, {'id': 'hind.L', 'upper': 'Pouncer_Rig/root/visual_body/pelvis/hind_upper.L', 'lower': 'Pouncer_Rig/root/visual_body/pelvis/hind_upper.L/hind_lower.L', 'paw': 'Pouncer_Rig/root/visual_body/pelvis/hind_upper.L/hind_lower.L/hind_paw.L'}, {'id': 'hind.R', 'upper': 'Pouncer_Rig/root/visual_body/pelvis/hind_upper.R', 'lower': 'Pouncer_Rig/root/visual_body/pelvis/hind_upper.R/hind_lower.R', 'paw': 'Pouncer_Rig/root/visual_body/pelvis/hind_upper.R/hind_lower.R/hind_paw.R'}]
RENDERERS=['AmberEye', 'AmberEye.001', 'ArticulatedLowerJaw', 'Claw', 'Claw.001', 'Claw.002', 'Claw.003', 'Claw.004', 'Claw.005', 'Claw.006', 'Claw.007', 'Claw.008', 'Claw.009', 'Claw.010', 'Claw.011', 'DeepEyeSocket', 'DeepEyeSocket.001', 'Fang', 'Fang.001', 'Fang.002', 'Fang.003', 'MouthCavity', 'Nostril', 'Nostril.001', 'Pouncer_Skin_LOD0', 'SlitPupil', 'SlitPupil.001']
SOLVER='Assets/DesertRV/Runtime/TwoBoneArmSolver.cs'
SOLVER_GUID='17ed0b5762b35543b60100e36f9279a1'

def contract(bindings):
 import strict_output as s
 s.require(type(bindings.get('pawGroundLayer')) is int and bindings['pawGroundLayer']==0,'PAW_GROUND_LAYER')
 s.require(bindings.get('pawChains')==CHAINS,'PAW_EXACT_CHAIN_PATHS')
 s.require(bindings.get('pawRenderers')==RENDERERS,'PAW_COMPLETE_RENDERER_PATHS')

def validate(project,prefix,imported,frames,report):
 import strict_output as s
 s.require(SCRIPT in imported['dependencies'],'PAW_PERSISTED_DEPENDENCY')
 script=s.safe(project/SCRIPT);meta=s.safe(project/(SCRIPT+'.meta'))
 s.require(re.findall(r'^guid: ([a-f0-9]{32})$',meta.read_text(),re.M)==[GUID],'PAW_COMPONENT_META_GUID')
 prefab=s.safe(project/(prefix+'/Candidate.prefab')).read_text()
 s.require(len(re.findall(r'\bguid: '+GUID+r'\b',prefab))==1,'PAW_PERSISTED_COMPONENT_GUID')
 s.keys(report,('status','scope','gameplayAccepted','slipAccepted','groundLayer','groundObject','samples'))
 s.require(report['status']=='captured-unreviewed' and report['scope']=='same-runtime-ApplyPawContact-real-Animator-not-locomotion-QA' and report['gameplayAccepted'] is False and report['slipAccepted'] is False,'PAW_SCOPE')
 s.require(report['groundLayer']==0 and report['groundObject']=='CandidatePawContactGround','PAW_REAL_GROUND_FIXTURE')
 rows=report['samples'];s.require(isinstance(rows,list) and len(rows)==len(frames) and {x['label'] for x in rows}==set(frames),'PAW_SAMPLE_INVENTORY')
 for row in rows:
  s.keys(row,('label','preMeshPoseSha256','postMeshPoseSha256','preWorldMinY','postWorldMinY','solve'));frame=frames[row['label']]
  s.require(s.digest(row['preMeshPoseSha256']) and row['postMeshPoseSha256']==frame['meshPoseSha256'],'PAW_PRE_POST_IDENTITY')
  s.require(s.finite(row['preWorldMinY']) and s.finite(row['postWorldMinY']) and abs(row['postWorldMinY']-frame['worldMinY'])<=1e-5,'PAW_PRE_POST_WORLD_MIN')
  solve=row['solve'];s.keys(solve,('valid','paused','fullMeshValidated','slipValidated','swingArcValidated','frame','actorSceneHandle','physicsSceneHash','reason','transitionNormalizedTime','currentNormalizedTime','nextNormalizedTime','currentLength','nextLength','animatorSpeed','legs'))
  s.require(solve['valid'] is True and all(solve[x] is False for x in ('paused','fullMeshValidated','slipValidated','swingArcValidated')) and solve['reason'] in (None,''),'PAW_SOLVE_STATUS')
  for k in ('actorSceneHandle','physicsSceneHash'):s.require(type(solve[k]) is int,'PAW_PHYSICS_SCENE_ID')
  for k in ('transitionNormalizedTime','currentNormalizedTime','nextNormalizedTime','currentLength','nextLength','animatorSpeed'):s.require(s.finite(solve[k]),'PAW_STATE_NUMBER')
  s.require(type(solve['frame']) is int and solve['frame']>=0 and isinstance(solve['legs'],list) and [x['id'] for x in solve['legs']]==list(IDS),'PAW_LEG_INVENTORY')
  for leg in solve['legs']:
   s.keys(leg,('id','reason','sourceState','destinationState','corrected','valid','lowestRendererPath','lowestSourceVertex','selectedVertices','excludedMixedVertices','groundSceneHandle','preMinDistance','postMinDistance','attemptedPostMinDistance','correctionMeters','targetClearance','prePawWorld','postPawWorld','groundPoint','groundNormal'))
   s.require(type(leg['groundSceneHandle']) is int and leg['groundSceneHandle']==solve['actorSceneHandle'],'PAW_GROUND_WRONG_SCENE')
   s.require(leg['valid'] is True and leg['reason'] in (None,'') and leg['sourceState'] in s.STATES and leg['destinationState'] in s.STATES,'PAW_LEG_STATUS')
   for k in ('corrected',):s.require(type(leg[k]) is bool,'PAW_LEG_BOOL')
   for k in ('preMinDistance','postMinDistance','attemptedPostMinDistance','correctionMeters','targetClearance'):s.require(s.finite(leg[k]),'PAW_LEG_NUMBER')
   for k in ('prePawWorld','postPawWorld','groundPoint','groundNormal'):s.vec(leg[k])
   s.require(abs(sum(v*v for v in leg['groundNormal'].values())-1)<.001,'PAW_GROUND_NORMAL')
   s.require(leg['groundNormal']['y']>.9999 and abs(leg['groundPoint']['y']-frame['groundReferenceY'])<=.00001,'PAW_FIXTURE_PLANE')
   s.require(row['preWorldMinY']<=leg['preMinDistance']+leg['groundPoint']['y']+.00001 and row['postWorldMinY']<=leg['postMinDistance']+leg['groundPoint']['y']+.00001,'PAW_WHOLE_MESH_BOUND_CONSISTENCY')
   s.require(isinstance(leg['lowestRendererPath'],str) and leg['lowestRendererPath'] in {'pouncer-candidate/'+r for r in RENDERERS},'PAW_LOWEST_RENDERER_PATH')
   s.require(type(leg['selectedVertices']) is int and leg['selectedVertices']>=4 and type(leg['excludedMixedVertices']) is int and leg['excludedMixedVertices']>=0,'PAW_VERTEX_MEMBERSHIP')
   s.require(type(leg['lowestSourceVertex']) is int and leg['lowestSourceVertex']>=0 and leg['postMinDistance']>=-.004,'PAW_ACTUAL_SOLE_GATE')
   if leg['corrected']:
    target=.001
    s.require(leg['preMinDistance']<-.004 and abs(leg['targetClearance']-target)<1e-6 and 0<leg['correctionMeters']<=.10 and abs(leg['correctionMeters']-(target-leg['preMinDistance']))<1e-5 and abs(leg['postMinDistance']-target)<=.0002,'PAW_BOUNDED_CORRECTION')
    expected={a:leg['prePawWorld'][a]+leg['groundNormal'][a]*leg['correctionMeters'] for a in ('x','y','z')}
    s.require(s.distance(expected,leg['postPawWorld'])<=.0001,'PAW_TANGENT_POSITION_CHANGED')
   else:s.require(leg['preMinDistance']>=-.004 and abs(leg['postMinDistance']-leg['preMinDistance'])<1e-6 and s.distance(leg['prePawWorld'],leg['postPawWorld'])<1e-6,'PAW_NO_UNNECESSARY_CORRECTION')
 solver=s.safe(project/SOLVER);solver_meta=s.safe(project/(SOLVER+'.meta'))
 s.require(re.findall(r'^guid: ([a-f0-9]{32})$',solver_meta.read_text(),re.M)==[SOLVER_GUID],'PAW_SOLVER_META_GUID')
 return [(script,Path('OriginalRuntime/PouncerPawContactConstraint.cs')),(meta,Path('OriginalRuntime/PouncerPawContactConstraint.cs.meta')),(solver,Path('OriginalRuntime/TwoBoneArmSolver.cs')),(solver_meta,Path('OriginalRuntime/TwoBoneArmSolver.cs.meta'))]

def sanitize_failed(report):
 """Preserve bounded measurements only; failure narratives are discarded, never promoted."""
 import strict_output as s
 s.keys(report,('status','scope','gameplayAccepted','slipAccepted','groundLayer','groundObject','samples'))
 s.require(report['status'] in ('not-complete','captured-unreviewed') and report['scope']=='same-runtime-ApplyPawContact-real-Animator-not-locomotion-QA' and report['gameplayAccepted'] is False and report['slipAccepted'] is False,'PAW_FAILED_SCOPE')
 s.require(report['groundLayer']==0 and report['groundObject']=='CandidatePawContactGround' and isinstance(report['samples'],list) and len(report['samples'])<=184,'PAW_FAILED_BOUNDS')
 result=[]
 for row in report['samples']:
  s.keys(row,('label','preMeshPoseSha256','postMeshPoseSha256','preWorldMinY','postWorldMinY','solve'))
  s.require(row['label'] in __import__('pouncer_output').expected_labels() and s.digest(row['preMeshPoseSha256']) and (s.digest(row['postMeshPoseSha256']) or row['postMeshPoseSha256'] in (None,'')),'PAW_FAILED_IDENTITY')
  for k in ('preWorldMinY','postWorldMinY'):s.require(s.finite(row[k]),'PAW_FAILED_NUMBER')
  solve=row['solve'];s.keys(solve,('valid','paused','fullMeshValidated','slipValidated','swingArcValidated','frame','actorSceneHandle','physicsSceneHash','reason','transitionNormalizedTime','currentNormalizedTime','nextNormalizedTime','currentLength','nextLength','animatorSpeed','legs'))
  s.require(all(type(solve[k]) is bool for k in ('valid','paused','fullMeshValidated','slipValidated','swingArcValidated')) and all(solve[k] is False for k in ('fullMeshValidated','slipValidated','swingArcValidated')),'PAW_FAILED_ACCEPTANCE')
  s.require(solve['reason'] is None or isinstance(solve['reason'],str) and len(solve['reason'])<=4096,'PAW_FAILED_REASON_SHAPE')
  for k in ('transitionNormalizedTime','currentNormalizedTime','nextNormalizedTime','currentLength','nextLength','animatorSpeed'):s.require(s.finite(solve[k]),'PAW_FAILED_STATE')
  for k in ('frame','actorSceneHandle','physicsSceneHash'):s.require(type(solve[k]) is int,'PAW_FAILED_SCENE')
  s.require(isinstance(solve['legs'],list) and len(solve['legs'])<=4,'PAW_FAILED_LEG_COUNT');legs=[]
  for leg in solve['legs']:
   s.keys(leg,('id','reason','sourceState','destinationState','corrected','valid','lowestRendererPath','lowestSourceVertex','selectedVertices','excludedMixedVertices','groundSceneHandle','preMinDistance','postMinDistance','attemptedPostMinDistance','correctionMeters','targetClearance','prePawWorld','postPawWorld','groundPoint','groundNormal'))
   s.require(leg['id'] in IDS and leg['sourceState'] in set(s.STATES)|{'Unknown'} and leg['destinationState'] in set(s.STATES)|{'Unknown'},'PAW_FAILED_LEG_ID')
   s.require(leg['reason'] is None or isinstance(leg['reason'],str) and len(leg['reason'])<=4096,'PAW_FAILED_REASON_SHAPE')
   for k in ('corrected','valid'):s.require(type(leg[k]) is bool,'PAW_FAILED_LEG_BOOL')
   for k in ('lowestSourceVertex','selectedVertices','excludedMixedVertices','groundSceneHandle'):s.require(type(leg[k]) is int,'PAW_FAILED_LEG_INTEGER')
   for k in ('preMinDistance','postMinDistance','attemptedPostMinDistance','correctionMeters','targetClearance'):s.require(s.finite(leg[k]),'PAW_FAILED_LEG_NUMBER')
   for k in ('prePawWorld','postPawWorld','groundPoint','groundNormal'):s.vec(leg[k])
   s.require(leg['lowestRendererPath'] in (None,'') or isinstance(leg['lowestRendererPath'],str) and leg['lowestRendererPath'] in {'pouncer-candidate/'+r for r in RENDERERS},'PAW_FAILED_RENDERER_PATH')
   legs.append({k:v for k,v in leg.items() if k!='reason'})
  clean={k:v for k,v in solve.items() if k not in ('reason','legs')};clean['legs']=legs
  result.append({**{k:v for k,v in row.items() if k!='solve'},'solve':clean})
 return {'scope':'failed-paw-contact-measurements-not-accepted','accepted':False,'samples':result}
