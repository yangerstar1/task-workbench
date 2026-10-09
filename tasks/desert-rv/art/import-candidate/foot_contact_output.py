"""Exact own-component and real pre/post foot evidence closure. No acceptance upgrades."""
import re
from pathlib import Path
SCRIPT='Assets/DesertRV/Runtime/ArmoredFootContactConstraint.cs'
GUID='a97352c38e4f540e895d203fb9028cad'
IDS=('fore.L','fore.R','hind.L','hind.R')
NATIVE_NAMES={'DesertRV.Tests.ArmoredFootContactConstraintTests.'+n for n in (
 'CorrectsMeasuredFortyOneMillimeterViolationByRotation','FailedPostSolveRestoresWholeLegRotations',
 'RepeatedSamePoseDoesNotAccumulateCorrection','PauseDoesNotWriteAndAnimatorRewriteCanBeCorrectedAgain',
 'FailureRemainsLatchedUntilExplicitReset','RejectsMoreThanFourFootInfluences','UsesActorPhysicsSceneAndRejectsOtherSceneGround')}

def contract(bindings):
 import strict_output as s
 s.require(bindings.get('footGroundLayer')==0 and type(bindings['footGroundLayer']) is int,'FOOT_GROUND_LAYER')
 rows=bindings.get('footChains');s.require(isinstance(rows,list) and len(rows)==4,'FOOT_CHAIN_COUNT')
 for row,id in zip(rows,IDS):
  s.keys(row,('id','upper','lower','foot'));upper='Bulwark_Rig/root/body/upper.'+id;lower=upper+'/lower.'+id
  s.require(row==dict(id=id,upper=upper,lower=lower,foot=lower+'/foot.'+id),'FOOT_EXACT_CHAIN_PATH')

def validate(project,prefix,imported,frames,report):
 import strict_output as s
 s.require(SCRIPT in imported['dependencies'],'FOOT_PERSISTED_DEPENDENCY')
 script=s.safe(project/SCRIPT);meta=s.safe(project/(SCRIPT+'.meta'))
 s.require(re.findall(r'^guid: ([a-f0-9]{32})$',meta.read_text(),re.M)==[GUID],'FOOT_COMPONENT_META_GUID')
 prefab=s.safe(project/(prefix+'/Candidate.prefab')).read_text()
 s.require(len(re.findall(r'\bguid: '+GUID+r'\b',prefab))==1,'FOOT_PERSISTED_COMPONENT_GUID')
 s.keys(report,('status','scope','gameplayAccepted','slipAccepted','groundLayer','groundObject','samples'))
 s.require(report['status']=='captured-unreviewed' and report['scope']=='same-runtime-ApplyFootContact-real-Animator-not-locomotion-QA' and report['gameplayAccepted'] is False and report['slipAccepted'] is False,'FOOT_SCOPE')
 s.require(report['groundLayer']==0 and report['groundObject']=='CandidateFootContactGround','FOOT_REAL_GROUND_FIXTURE')
 rows=report['samples'];s.require(isinstance(rows,list) and len(rows)==len(frames) and {x['label'] for x in rows}==set(frames),'FOOT_SAMPLE_INVENTORY')
 for row in rows:
  s.keys(row,('label','preMeshPoseSha256','postMeshPoseSha256','preWorldMinY','postWorldMinY','solve'));frame=frames[row['label']]
  s.require(s.digest(row['preMeshPoseSha256']) and row['postMeshPoseSha256']==frame['meshPoseSha256'],'FOOT_PRE_POST_IDENTITY')
  s.require(s.finite(row['preWorldMinY']) and s.finite(row['postWorldMinY']) and abs(row['postWorldMinY']-frame['worldMinY'])<=1e-5,'FOOT_PRE_POST_WORLD_MIN')
  solve=row['solve'];s.keys(solve,('valid','paused','fullMeshValidated','slipValidated','swingArcValidated','frame','actorSceneHandle','physicsSceneHash','reason','transitionNormalizedTime','currentNormalizedTime','nextNormalizedTime','currentLength','nextLength','animatorSpeed','legs'))
  s.require(solve['valid'] is True and all(solve[x] is False for x in ('paused','fullMeshValidated','slipValidated','swingArcValidated')) and solve['reason'] in (None,''),'FOOT_SOLVE_STATUS')
  for k in ('actorSceneHandle','physicsSceneHash'):s.require(type(solve[k]) is int,'FOOT_PHYSICS_SCENE_ID')
  for k in ('transitionNormalizedTime','currentNormalizedTime','nextNormalizedTime','currentLength','nextLength','animatorSpeed'):s.require(s.finite(solve[k]),'FOOT_STATE_NUMBER')
  s.require(type(solve['frame']) is int and solve['frame']>=0 and isinstance(solve['legs'],list) and [x['id'] for x in solve['legs']]==list(IDS),'FOOT_LEG_INVENTORY')
  for leg in solve['legs']:
   s.keys(leg,('id','reason','sourceState','destinationState','corrected','valid','sourceAirborne','destinationAirborne','lowestSourceVertex','groundSceneHandle','preMinDistance','postMinDistance','attemptedPostMinDistance','correctionMeters','targetClearance','preFootWorld','postFootWorld','groundPoint','groundNormal'))
   s.require(type(leg['groundSceneHandle']) is int and leg['groundSceneHandle']==solve['actorSceneHandle'],'FOOT_GROUND_WRONG_SCENE')
   s.require(leg['valid'] is True and leg['reason'] in (None,'') and leg['sourceState'] in s.STATES and leg['destinationState'] in s.STATES,'FOOT_LEG_STATUS')
   for k in ('corrected','sourceAirborne','destinationAirborne'):s.require(type(leg[k]) is bool,'FOOT_LEG_BOOL')
   for k in ('preMinDistance','postMinDistance','attemptedPostMinDistance','correctionMeters','targetClearance'):s.require(s.finite(leg[k]),'FOOT_LEG_NUMBER')
   for k in ('preFootWorld','postFootWorld','groundPoint','groundNormal'):s.vec(leg[k])
   s.require(abs(sum(v*v for v in leg['groundNormal'].values())-1)<.001,'FOOT_GROUND_NORMAL')
   s.require(leg['groundNormal']['y']>.9999 and abs(leg['groundPoint']['y']-frame['groundReferenceY'])<=.00001,'FOOT_FIXTURE_PLANE')
   s.require(row['preWorldMinY']<=leg['preMinDistance']+leg['groundPoint']['y']+.00001 and row['postWorldMinY']<=leg['postMinDistance']+leg['groundPoint']['y']+.00001,'FOOT_WHOLE_MESH_BOUND_CONSISTENCY')
   s.require(type(leg['lowestSourceVertex']) is int and leg['lowestSourceVertex']>=0 and leg['postMinDistance']>=-.004,'FOOT_ACTUAL_SOLE_GATE')
   if leg['corrected']:
    target=.001 if leg['sourceAirborne'] or leg['destinationAirborne'] else .005
    s.require(leg['preMinDistance']<-.004 and abs(leg['targetClearance']-target)<1e-6 and 0<leg['correctionMeters']<=.20 and abs(leg['correctionMeters']-(target-leg['preMinDistance']))<1e-5 and abs(leg['postMinDistance']-target)<=.0002,'FOOT_BOUNDED_CORRECTION')
    expected={a:leg['preFootWorld'][a]+leg['groundNormal'][a]*leg['correctionMeters'] for a in ('x','y','z')}
    s.require(s.distance(expected,leg['postFootWorld'])<=.0001,'FOOT_TANGENT_POSITION_CHANGED')
   else:s.require(leg['preMinDistance']>=-.004 and abs(leg['postMinDistance']-leg['preMinDistance'])<1e-6 and s.distance(leg['preFootWorld'],leg['postFootWorld'])<1e-6,'FOOT_NO_UNNECESSARY_CORRECTION')
 return [(script,Path('OriginalRuntime/ArmoredFootContactConstraint.cs')),(meta,Path('OriginalRuntime/ArmoredFootContactConstraint.cs.meta'))]

def sanitize_failed(report):
 """Preserve bounded measurements only; failure narratives are discarded, never promoted."""
 import strict_output as s
 s.keys(report,('status','scope','gameplayAccepted','slipAccepted','groundLayer','groundObject','samples'))
 s.require(report['status'] in ('not-complete','captured-unreviewed') and report['scope']=='same-runtime-ApplyFootContact-real-Animator-not-locomotion-QA' and report['gameplayAccepted'] is False and report['slipAccepted'] is False,'FOOT_FAILED_SCOPE')
 s.require(report['groundLayer']==0 and report['groundObject']=='CandidateFootContactGround' and isinstance(report['samples'],list) and len(report['samples'])<=202,'FOOT_FAILED_BOUNDS')
 result=[]
 for row in report['samples']:
  s.keys(row,('label','preMeshPoseSha256','postMeshPoseSha256','preWorldMinY','postWorldMinY','solve'))
  s.require(row['label'] in s.expected_labels() and s.digest(row['preMeshPoseSha256']) and (s.digest(row['postMeshPoseSha256']) or row['postMeshPoseSha256'] in (None,'')),'FOOT_FAILED_IDENTITY')
  for k in ('preWorldMinY','postWorldMinY'):s.require(s.finite(row[k]),'FOOT_FAILED_NUMBER')
  solve=row['solve'];s.keys(solve,('valid','paused','fullMeshValidated','slipValidated','swingArcValidated','frame','actorSceneHandle','physicsSceneHash','reason','transitionNormalizedTime','currentNormalizedTime','nextNormalizedTime','currentLength','nextLength','animatorSpeed','legs'))
  s.require(all(type(solve[k]) is bool for k in ('valid','paused','fullMeshValidated','slipValidated','swingArcValidated')) and all(solve[k] is False for k in ('fullMeshValidated','slipValidated','swingArcValidated')),'FOOT_FAILED_ACCEPTANCE')
  s.require(solve['reason'] is None or isinstance(solve['reason'],str) and len(solve['reason'])<=4096,'FOOT_FAILED_REASON_SHAPE')
  for k in ('transitionNormalizedTime','currentNormalizedTime','nextNormalizedTime','currentLength','nextLength','animatorSpeed'):s.require(s.finite(solve[k]),'FOOT_FAILED_STATE')
  for k in ('frame','actorSceneHandle','physicsSceneHash'):s.require(type(solve[k]) is int,'FOOT_FAILED_SCENE')
  s.require(isinstance(solve['legs'],list) and len(solve['legs'])<=4,'FOOT_FAILED_LEG_COUNT');legs=[]
  for leg in solve['legs']:
   s.keys(leg,('id','reason','sourceState','destinationState','corrected','valid','sourceAirborne','destinationAirborne','lowestSourceVertex','groundSceneHandle','preMinDistance','postMinDistance','attemptedPostMinDistance','correctionMeters','targetClearance','preFootWorld','postFootWorld','groundPoint','groundNormal'))
   s.require(leg['id'] in IDS and leg['sourceState'] in set(s.STATES)|{'Unknown'} and leg['destinationState'] in set(s.STATES)|{'Unknown'},'FOOT_FAILED_LEG_ID')
   s.require(leg['reason'] is None or isinstance(leg['reason'],str) and len(leg['reason'])<=4096,'FOOT_FAILED_REASON_SHAPE')
   for k in ('corrected','valid','sourceAirborne','destinationAirborne'):s.require(type(leg[k]) is bool,'FOOT_FAILED_LEG_BOOL')
   for k in ('lowestSourceVertex','groundSceneHandle'):s.require(type(leg[k]) is int,'FOOT_FAILED_LEG_INTEGER')
   for k in ('preMinDistance','postMinDistance','attemptedPostMinDistance','correctionMeters','targetClearance'):s.require(s.finite(leg[k]),'FOOT_FAILED_LEG_NUMBER')
   for k in ('preFootWorld','postFootWorld','groundPoint','groundNormal'):s.vec(leg[k])
   legs.append({k:v for k,v in leg.items() if k!='reason'})
  clean={k:v for k,v in solve.items() if k not in ('reason','legs')};clean['legs']=legs
  result.append({**{k:v for k,v in row.items() if k!='solve'},'solve':clean})
 return {'scope':'failed-foot-contact-measurements-not-accepted','accepted':False,'samples':result}
