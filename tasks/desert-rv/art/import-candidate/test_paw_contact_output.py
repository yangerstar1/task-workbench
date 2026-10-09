"""Host-only closed-schema and source-wiring tests. These are not Unity evidence."""
import copy
import json
from pathlib import Path
import re
import tempfile
import unittest
import paw_contact_output as paw
import strict_output as strict

ROOT=Path(__file__).parents[2]
class PawContactExportTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.project=Path(self.tmp.name)
  self.prefix='Assets/DesertRV/CandidateArtImports/test'
  for path,guid in ((paw.SCRIPT,paw.GUID),(paw.SOLVER,paw.SOLVER_GUID)):
   target=self.project/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/'unity'/path).read_bytes())
   Path(str(target)+'.meta').write_text('fileFormatVersion: 2\nguid: '+guid+'\n')
  target=self.project/self.prefix/'Candidate.prefab';target.parent.mkdir(parents=True);target.write_text('m_Script: {guid: '+paw.GUID+'}\n')
  self.frame=dict(meshPoseSha256='a'*64,worldMinY=.001,groundReferenceY=0)
  self.legs=[]
  for id in paw.IDS:
   self.legs.append(dict(id=id,reason=None,sourceState='Walk',destinationState='Death',corrected=True,valid=True,
    lowestRendererPath='pouncer-candidate/Claw',lowestSourceVertex=4950,selectedVertices=32,excludedMixedVertices=2,groundSceneHandle=42,
    preMinDistance=-.024082288,postMinDistance=.001,attemptedPostMinDistance=.001,correctionMeters=.025082288,targetClearance=.001,
    prePawWorld=dict(x=1,y=.1,z=2),postPawWorld=dict(x=1,y=.125082288,z=2),groundPoint=dict(x=1,y=0,z=2),groundNormal=dict(x=0,y=1,z=0)))
  solve=dict(valid=True,paused=False,fullMeshValidated=False,slipValidated=False,swingArcValidated=False,frame=1,actorSceneHandle=42,physicsSceneHash=99,reason=None,
   transitionNormalizedTime=.333333,currentNormalizedTime=.54,nextNormalizedTime=.00888889,currentLength=.4,nextLength=1.8,animatorSpeed=1,legs=self.legs)
  self.row=dict(label='Walk-0.5-Death-0.016',preMeshPoseSha256='b'*64,postMeshPoseSha256='a'*64,preWorldMinY=-.024082288,postWorldMinY=.001,solve=solve)
  self.report=dict(status='captured-unreviewed',scope='same-runtime-ApplyPawContact-real-Animator-not-locomotion-QA',gameplayAccepted=False,slipAccepted=False,groundLayer=0,groundObject='CandidatePawContactGround',samples=[self.row])
 def tearDown(self):self.tmp.cleanup()
 def validate(self):return paw.validate(self.project,self.prefix,{'dependencies':[paw.SCRIPT]},{self.row['label']:self.frame},self.report)
 def reject(self,code):
  with self.assertRaisesRegex(strict.StrictError,code):self.validate()
 def test_measured_violation_closes_exact_runtime_payload(self):
  self.assertEqual({str(dest) for _,dest in self.validate()},{'OriginalRuntime/PouncerPawContactConstraint.cs','OriginalRuntime/PouncerPawContactConstraint.cs.meta','OriginalRuntime/TwoBoneArmSolver.cs','OriginalRuntime/TwoBoneArmSolver.cs.meta'})
 def test_full_mesh_acceptance_cannot_be_forged(self):self.row['solve']['fullMeshValidated']=True;self.reject('PAW_SOLVE_STATUS')
 def test_wrong_scene_rejected(self):self.legs[0]['groundSceneHandle']=43;self.reject('PAW_GROUND_WRONG_SCENE')
 def test_tangent_drift_rejected(self):self.legs[0]['postPawWorld']['x']+=.001;self.reject('PAW_TANGENT_POSITION_CHANGED')
 def test_gate_cannot_be_relaxed(self):self.legs[0]['postMinDistance']=-.004001;self.row['postWorldMinY']=self.frame['worldMinY']=-.004001;self.reject('PAW_ACTUAL_SOLE_GATE')
 def test_unnecessary_correction_rejected(self):self.legs[0]['preMinDistance']=-.003;self.reject('PAW_BOUNDED_CORRECTION')
 def test_corrected_geometry_must_match_frame(self):self.row['postMeshPoseSha256']='c'*64;self.reject('PAW_PRE_POST_IDENTITY')
 def test_mixed_vertex_count_must_be_explicit(self):del self.legs[0]['excludedMixedVertices'];self.reject('STRICT_SCHEMA')
 def test_extra_report_fields_rejected(self):self.row['unknown']='no';self.reject('STRICT_SCHEMA')
 def test_missing_component_guid_rejected(self):(self.project/self.prefix/'Candidate.prefab').write_text('no component');self.reject('PAW_PERSISTED_COMPONENT_GUID')
 def test_failed_report_has_no_narrative_or_acceptance(self):
  self.report['status']='not-complete';self.row['solve']['valid']=False;self.row['solve']['reason']='private failure text'
  self.legs[0]['reason']='private detail';out=paw.sanitize_failed(self.report)
  self.assertFalse(out['accepted']);self.assertNotIn('private',json.dumps(out));self.assertEqual(out['samples'][0]['solve']['legs'][0]['lowestSourceVertex'],4950)
 def test_exact_contract_and_native_names(self):
  contract=json.loads((ROOT/'art/import-candidate/contracts/pouncer-full-strict-37856618820.json').read_text());paw.contract(contract['bindings'])
  source=(ROOT/'unity/Assets/DesertRV/Tests/CandidateArt/PouncerPawContactConstraintTests.cs').read_text()
  names={'DesertRV.Tests.PouncerPawContactConstraintTests.'+x for x in re.findall(r'\[Test\]\s+public void (\w+)\(',source)}
  self.assertEqual(names,paw.NATIVE_NAMES);self.assertEqual(len(names),9)
 def test_runtime_uses_cached_complete_weights_and_same_strict_entry(self):
  source=(ROOT/'unity'/paw.SCRIPT).read_text();apply=source[source.index('public bool ApplyPawContact'):]
  self.assertIn('GetAllBoneWeights()',source);self.assertNotIn('GetAllBoneWeights',apply);self.assertNotIn('mesh.vertices',apply)
  self.assertIn('GetPhysicsScene().Raycast',source);self.assertNotIn('Physics.Raycast(',source)
  self.assertNotIn('BakeMesh(',source);self.assertNotRegex(apply,r'\.localPosition\s*=(?!=)');self.assertNotRegex(apply,r'\.localScale\s*=(?!=)')
  capture=(ROOT/'unity/Assets/DesertRV/Editor/JourneyCandidateArtCapture.cs').read_text()
  self.assertIn('pawContact.ApplyPawContact(out var pawReport)',capture);self.assertIn('frame.worldMinY<frame.groundReferenceY-.004f',capture)
  self.assertIn('MoveGameObjectToScene(groundObject,scene)',capture)

if __name__=='__main__':unittest.main()
