"""Synthetic schema/security fixtures only; never substitutes for native rendering."""
import copy,hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
import strict_output as s
from verify_output import export,EvidenceError

class StrictExportTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'desert-rv';self.project=self.root/'unity';self.out=self.root/'safe-export'
  self.c=json.loads((Path(__file__).parent/'contracts/armored-full-strict-37850840062.json').read_text());self.c['id']='armored-test-fixture'
  self.prefix='Assets/DesertRV/CandidateArtImports/'+self.c['id'];self.folder=self.project/self.prefix;self.ev=self.project/'JourneyEvidence/CandidateArt';self.ev.mkdir(parents=True)
  self.guid=0
  def write(rel,data):
   p=self.project/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data if isinstance(data,bytes) else data.encode());return p
  self.write=write
  for f in self.c['files']:
   p=self.folder/'Source'/f['file'];p.parent.mkdir(parents=True,exist_ok=True)
   if p.suffix=='.png':
    im=Image.new('RGBA',(2,2));im.putdata([(11,40,90,255),(23,71,133,255),(48,121,177,255),(82,198,229,255)]);im.save(p)
   else:p.write_bytes(b'synthetic-fbx-fixture')
   f['sha256']=s.sha(p);self.meta(p)
  cp=write('CandidateImportInput/contract.json',json.dumps(self.c));write(self.prefix+'/contract.json',cp.read_bytes())
  for n in ['contract.json','Candidate.prefab','Candidate.controller']:
   if n!='contract.json':write(self.prefix+'/'+n,'%YAML 1.1\n--- !u!1 &1\nCandidate: {}\n')
   self.meta(self.folder/n)
  self.meta(self.folder);self.meta(self.folder.parent);self.meta(self.folder/'Source');self.meta(self.folder/'Materials')
  for n in ['Material_00','Material_01','Core_Open']:
   p=write(self.prefix+'/Materials/'+n+'.mat','%YAML 1.1\nMaterial: {}\n');self.meta(p)
  self.meta(self.folder/'Derived');derived=write(self.prefix+'/Derived/ORM_00.png',b'')
  im=Image.new('RGBA',(2,2));im.putdata([(90,11,0,215),(133,23,0,184),(177,48,0,134),(229,82,0,57)]);im.save(derived);self.meta(derived,texture=True)
  self.imp=dict(mode='STRICT_BINDING',scope='FULL_CANDIDATE',kind='armored',status='candidate-structure-imported-unreviewed',contractSha256=s.sha(cp),prefab=self.prefix+'/Candidate.prefab',dependencyHash='a'*32,dependencies=[self.prefix+'/Candidate.prefab'],runUrl=self.c['runUrl'],sourceCommit=self.c['sourceCommit'],artifactName=self.c['artifactName'],artifactSha256=self.c['artifactSha256'],candidateOnly=True,visualReviewed=False,gameplayReviewed=False,failures=[],importedAnimatorPaths=['Bulwark_Rig'],muzzle=None,stillRequired=['Actual Unity camera rendering and human visual review','Interrupted/repeated runtime flows','Full three-region playthrough','Android device acceptance','Explicit production review and unchanged production gate'])
  self.imp['dependencies']=[self.prefix+'/'+n for n in ['Candidate.prefab','Candidate.controller','Materials/Material_00.mat','Materials/Material_01.mat','Materials/Core_Open.mat','Derived/ORM_00.png','Source/bulwark-candidate.fbx','Source/bulwark-animations.fbx','Source/bulwark-basecolor.png']]
  self.imp['dependencySha256']=s.dependency_digest(self.project,self.imp['dependencies'])
  self.imp['clips']=[dict(x,frameRate=60,floatBindings=160,objectBindings=0) for x in self.c['clips']]
  # Exact own script fixture, not a broad Runtime wildcard.
  from foot_contact_output import SCRIPT,GUID
  write(SCRIPT,'// synthetic foot component fixture')
  write(SCRIPT+'.meta','fileFormatVersion: 2\nguid: '+GUID+'\n')
  write(self.prefix+'/Candidate.prefab','%YAML 1.1\n--- !u!1 &1\nCandidate: {script: {guid: '+GUID+'}}\n')
  self.imp['dependencies'].append(SCRIPT)
  self.imp['dependencySha256']=s.dependency_digest(self.project,self.imp['dependencies'])
  self.imp['rootCurves']=[dict(state=st,property=p,keys=2,minimum=0,maximum=0,constant=True,tangentsSafe=True) for st in s.STATES for p in sorted(s.ROOT_PROPERTIES)]
  for row in self.imp['rootCurves']:
   group,axis=row['property'].split('.');key={'m_LocalPosition':'position','m_LocalRotation':'rotation','m_LocalScale':'scale'}[group];row['minimum']=row['maximum']=self.c['bindings']['neutralBaseline'][key][axis]
  self.imp['derivedTextures']=[dict(source=self.prefix+'/Source/bulwark-orm.png',sourceSha256=next(x['sha256'] for x in self.c['files'] if x['file']=='bulwark-orm.png'),derived=self.prefix+'/Derived/ORM_00.png',derivedSha256=s.sha(derived),decodedPixelSha256=hashlib.sha256(bytes((177,48,0,134,229,82,0,57,90,11,0,215,133,23,0,184))).hexdigest(),mapping='R=source.B; G=source.R; B=0; A=255-source.G',width=2,height=2,sRGB=False,sourceModified=False)]
  image=Image.new('RGB',(960,540),(30,40,50));ImageDraw.Draw(image).rectangle((150,100,600,400),fill=(180,90,50));image.save(self.ev/'seed.png');png=(self.ev/'seed.png').read_bytes();(self.ev/'seed.png').unlink()
  frames=[]
  for i,label in enumerate(sorted(s.expected_labels())):
   name=f'frame-{i:04}.png';(self.ev/name).write_bytes(png)
   frames.append(dict(image=name,requestedState=label,imageSha256=hashlib.sha256(png).hexdigest(),meshPoseSha256=hashlib.sha256(label.encode()).hexdigest(),advanceSeconds=0,normalizedTime=0,worldMinY=0,groundReferenceY=0,rootLocalPositionDelta=0,rootLocalAngleDelta=0,rootLocalScaleDelta=0,stateHash=1,sampledVertices=100,outsideViewportVertices=0,behindCameraVertices=0,belowReferenceVertices=0,transitioning=False,groundDiagnosticApplicable=True))
  self.cap=dict(graphicsDeviceType='OpenGLCore',graphicsDeviceName='llvmpipe (LLVM 15.0.7, 256 bits)',status='captured-unreviewed',scope='real-Animator-pose-diagnostics-only',prefab=self.imp['prefab'],dependencySha256=self.imp['dependencySha256'],visualAccepted=False,gameplayAccepted=False,armoredAttackLoopIntent='Only source-authored Armored Attack loops to cover attackClock>1.2 and normalized CrossFade overrun. Gameplay clock/movement/damage unchanged.',notCovered=['Authoritative combat/weakpoint event state','Gameplay interruption and reload counts','Whole-session restart','Three-region walkthrough','Android device'],frames=frames)
  self.cap.update(neutralRoot=copy.deepcopy(self.c['bindings']['neutralBaseline']),neutralMeshWorldMin=dict(x=0,y=0,z=0),neutralMeshWorldMax=dict(x=1,y=2,z=3),neutralMeshWorldSize=dict(x=1,y=2,z=3))
  for f in frames:f.update(rootLocalPosition=copy.deepcopy(self.cap['neutralRoot']['position']),rootLocalRotation=copy.deepcopy(self.cap['neutralRoot']['rotation']),rootLocalScale=copy.deepcopy(self.cap['neutralRoot']['scale']),meshWorldMin=dict(x=0,y=0,z=0),meshWorldMax=dict(x=1,y=2,z=3),meshWorldSize=dict(x=1,y=2,z=3),meshSizeRatioToNeutral=dict(x=1,y=1,z=1))
  self.weak=dict(status='editor-fixture-captured-unreviewed',scope='explicit-Editor-fixture-real-presenter-not-full-gameplay',calibratedForScene=False,visualAccepted=False,limitation='Fixture assigns actor combat references/phase using reflection, then uses real BeastCombatState window and actor.WeakPointExposed. Not a world encounter, collision test or end-to-end playthrough. Whole body is vulnerable during Recover; no directional damage rule.',samples=[])
  for state in ('closed-before','open','closed-after'):
   for view in ('front','side','rear'):
    q=dict(x=0,y=1 if state=='open' else 0,z=0,w=0 if state=='open' else 1)
    self.weak['samples'].append(dict(state=state,view=view,coreMaterial=self.prefix+'/Materials/'+('Core_Open' if state=='open' else 'Material_01')+'.mat',imageLabel='weakpoint-'+state+'-'+view,fieldOfView=60,distance=3,weakPointExposed=state=='open',bodyUnchanged=True,localPlateRotations=([s.unity_euler(v) for v in self.c['bindings']['openEuler']] if state=='open' else [q,q.copy()]),cameraPosition=dict(x=0,y=1.65,z=3)))
  native=self.root/'artifacts/candidate-art/results.xml';native.parent.mkdir(parents=True)
  names=sorted(__import__('candidate_native_cases').NATIVE_NAMES)
  native.write_text('<test-run result="Passed">'+''.join('<test-case fullname="'+n+'" result="Passed"/>' for n in names)+'</test-run>')
  self.flush()
 def meta(self,p,texture=False):
  self.guid+=1;Path(str(p)+'.meta').parent.mkdir(parents=True,exist_ok=True);Path(str(p)+'.meta').write_text('fileFormatVersion: 2\nguid: '+f'{self.guid:032x}'+'\n'+('TextureImporter:\n  sRGBTexture: 0\n  isReadable: 1\n  textureType: 0\n' if texture else 'DefaultImporter: {}\n'))
 def foot_report(self):
  from foot_contact_output import IDS
  zero=dict(x=0.,y=0.,z=0.);up=dict(x=0.,y=1.,z=0.)
  rows=[]
  for f in self.cap['frames']:
   legs=[dict(id=id,reason=None,sourceState='Idle',destinationState='Idle',corrected=False,valid=True,sourceAirborne=False,destinationAirborne=False,lowestSourceVertex=1,groundSceneHandle=1,preMinDistance=.005,postMinDistance=.005,attemptedPostMinDistance=.005,correctionMeters=0.,targetClearance=0.,preFootWorld=zero.copy(),postFootWorld=zero.copy(),groundPoint=zero.copy(),groundNormal=up.copy()) for id in IDS]
   solve=dict(valid=True,paused=False,fullMeshValidated=False,slipValidated=False,swingArcValidated=False,frame=1,actorSceneHandle=1,physicsSceneHash=1,reason=None,transitionNormalizedTime=0.,currentNormalizedTime=0.,nextNormalizedTime=0.,currentLength=2.,nextLength=2.,animatorSpeed=1.,legs=legs)
   rows.append(dict(label=f['requestedState'],preMeshPoseSha256=f['meshPoseSha256'],postMeshPoseSha256=f['meshPoseSha256'],preWorldMinY=f['worldMinY'],postWorldMinY=f['worldMinY'],solve=solve))
  return dict(status='captured-unreviewed',scope='same-runtime-ApplyFootContact-real-Animator-not-locomotion-QA',gameplayAccepted=False,slipAccepted=False,groundLayer=0,groundObject='CandidateFootContactGround',samples=rows)
 def flush(self):
  (self.ev/'foot-contact-report.json').write_text(json.dumps(self.foot_report()))
  for n,obj in [('import-report.json',self.imp),('capture-report.json',self.cap),('weakpoint-fixture-report.json',self.weak)]:(self.ev/n).write_text(json.dumps(obj))
 def test_foot_report_rejects_invented_acceptance(self):
  from foot_contact_output import validate
  report=self.foot_report();report['slipAccepted']=True
  with self.assertRaisesRegex(s.StrictError,'FOOT_SCOPE'):validate(self.project,self.prefix,self.imp,{f['requestedState']:f for f in self.cap['frames']},report)
 def test_foot_report_requires_persisted_component_dependency(self):
  from foot_contact_output import validate,SCRIPT
  self.imp['dependencies'].remove(SCRIPT)
  with self.assertRaisesRegex(s.StrictError,'FOOT_PERSISTED_DEPENDENCY'):validate(self.project,self.prefix,self.imp,{f['requestedState']:f for f in self.cap['frames']},self.foot_report())
 def test_foot_report_rejects_false_healthy_sole(self):
  from foot_contact_output import validate
  report=self.foot_report();report['samples'][0]['solve']['legs'][0]['postMinDistance']=-.04159
  with self.assertRaises(s.StrictError):validate(self.project,self.prefix,self.imp,{f['requestedState']:f for f in self.cap['frames']},report)
 def test_foot_report_rejects_hidden_tangent_translation(self):
  from foot_contact_output import validate
  report=self.foot_report();row=report['samples'][0];row['preWorldMinY']=-.0415903
  leg=row['solve']['legs'][0];leg.update(corrected=True,preMinDistance=-.0415903,postMinDistance=.005,attemptedPostMinDistance=.005,targetClearance=.005,correctionMeters=.0465903,postFootWorld=dict(x=.1,y=.0465903,z=0))
  with self.assertRaisesRegex(s.StrictError,'FOOT_TANGENT_POSITION_CHANGED'):validate(self.project,self.prefix,self.imp,{f['requestedState']:f for f in self.cap['frames']},report)
 def tearDown(self):self.tmp.cleanup()
 def run_export(self,**kwargs):
  self.flush()
  with patch.dict(os.environ,{'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'123'}):return export(self.root,self.out,**kwargs)
 def rejected(self,code=None,**kwargs):
  with self.assertRaises((s.StrictError,EvidenceError)):self.run_export(**kwargs)
  receipt=json.loads((self.out/'receipt.json').read_text());self.assertEqual(receipt['status'],'FAILED_NOT_ACCEPTED');self.assertFalse(receipt['approved']);self.assertEqual(list(self.out.iterdir()),[self.out/'receipt.json'])
  if code:self.assertEqual(receipt['errorCode'],code)
 def test_neutral_is_locked_before_first_animator_update(self):
  source=(Path(__file__).parents[2]/'unity/Assets/DesertRV/Editor/JourneyCandidateArtCapture.cs').read_text()
  self.assertLess(source.index('RequireNeutral(contract.bindings.neutralBaseline'),source.index('animator.Rebind();animator.Update(0);'))
  self.assertIn('RequireRootUnchanged();',source)
  self.assertIn('meshSizeRatioToNeutral=new Vector3',source)
 def test_native_clip_pose_expectation_is_reported(self):
  source=(Path(__file__).parents[2]/'unity/Assets/DesertRV/Editor/JourneyCandidateArtImport.cs').read_text()
  self.assertIn('take=spec.take,poseExpectation=spec.poseExpectation,seconds=clip.length',source)
  self.assertIn('if(c.kind=="armored")RequireNeutralRootCurves',source)
  self.assertIn('Quaternion.Angle(rotation.normalized,root.localRotation.normalized)<=.001f',source)
 def test_valid_unreviewed_bounded_export(self):
  r=self.run_export();self.assertEqual(r['images'],202);self.assertEqual(r['weakpointImages'],9);self.assertEqual(r['nativeCases'],__import__('candidate_native_cases').NATIVE_COUNT);self.assertFalse(r['approved']);self.assertNotIn('muzzle',json.loads((self.out/'import-report.json').read_text()))
  for f in r['files']:self.assertEqual(s.sha(self.out/f['path']),f['sha256'])
 def test_optional_dependency_trace_failure_does_not_mask_original_gate(self):
  import io
  from contextlib import redirect_stdout
  from unittest.mock import patch
  output=io.StringIO()
  with patch.object(s,'dependency_digest',side_effect=ValueError('PRIVATE ERROR CONTENT')),redirect_stdout(output):
   s.observe_dependency_mismatch(self.project,[],None,'',None)
  self.assertIn('CANDIDATE_DEPENDENCY_OBSERVATION_FAILED',output.getvalue())
  self.assertNotIn('PRIVATE ERROR CONTENT',output.getvalue())
  self.assertIn('"storedSha256Valid": false',output.getvalue())

 def test_failed_native_only_safe_identity(self):self.rejected('STRICT_NATIVE_FAILED',native='failure')
 def test_failed_protected_only_safe_identity(self):self.rejected('STRICT_PROTECTED_SOURCE_FAILED',protected='failure')
 def test_missing_policy_case(self):
  p=self.root/'artifacts/candidate-art/results.xml';p.write_text('<test-run result="Passed"><test-case fullname="'+s.NATIVE+'" result="Passed"/></test-run>');self.rejected('STRICT_NATIVE_FAILED')
 def test_partial_scope_refused(self):
  p=self.project/'CandidateImportInput/contract.json';c=copy.deepcopy(self.c);c['scope']='PARTIAL_DIAGNOSTIC_NOT_FULL';p.write_text(json.dumps(c));self.rejected('STRICT_ARMORED_FULL_ONLY')
 def test_boolean_schema_does_not_impersonate_version_one(self):
  c=copy.deepcopy(self.c);c['schema']=True
  with self.assertRaises(s.StrictError):s.contract_shape(c)
 def test_other_kind_refused(self):
  c=copy.deepcopy(self.c);c['kind']='weapon'
  with self.assertRaises(s.StrictError):s.contract_shape(c)
 def test_nonattack_loop_refused(self):
  c=copy.deepcopy(self.c);next(x for x in c['clips'] if x['state']=='Death')['loop']=True
  with self.assertRaises(s.StrictError):s.contract_shape(c)
 def test_import_identity_refused(self):self.imp['sourceCommit']='b'*40;self.rejected('STRICT_IMPORT_SOURCE_MISMATCH')
 def test_constant_wrong_root_curve_refused(self):
  row=next(x for x in self.imp['rootCurves'] if x['property']=='m_LocalScale.x');row['minimum']=row['maximum']=1;self.rejected('STRICT_ROOT_CURVE_NEUTRAL_MISMATCH')
 def test_root_tangent_refused(self):self.imp['rootCurves'][0]['tangentsSafe']=False;self.rejected('STRICT_ROOT_CURVE_MOTION')
 def test_root_value_refused(self):self.imp['rootCurves'][0]['maximum']=.01;self.rejected('STRICT_ROOT_CURVE_MOTION')
 def test_omitted_dependency_refused(self):
  self.imp['dependencies']=['Assets/DesertRV/absent.asset'];self.imp['dependencySha256']=hashlib.sha256(b'').hexdigest();self.cap['dependencySha256']=self.imp['dependencySha256'];self.rejected('STRICT_REQUIRED_DEPENDENCIES')
 def test_missing_assets_dependency_refused(self):
  with self.assertRaises(s.StrictError):s.dependency_digest(self.project,['Assets/DesertRV/absent.asset'])
 def test_dependency_mutation_refused(self):(self.folder/'Candidate.prefab').write_text('%YAML 1.1\nChanged: true\n');self.rejected('STRICT_DEPENDENCY_HASH')
 def test_neutral_root_unit_change_refused(self):self.cap['neutralRoot']['scale']=dict(x=1,y=1,z=1);self.rejected('STRICT_NEUTRAL_ROOT_MISMATCH')
 def test_neutral_world_bounds_refused(self):self.cap['neutralRoot']['renderers'][0]['worldExtents']['x']*=.01;self.rejected('STRICT_NEUTRAL_BOUNDS_MISMATCH')
 def test_frame_hidden_unit_change_refused(self):self.cap['frames'][0]['rootLocalScale']=dict(x=1,y=1,z=1);self.rejected('STRICT_ROOT_VECTOR_DRIFT')
 def test_frame_size_ratio_refused(self):self.cap['frames'][0]['meshSizeRatioToNeutral']['y']=.01;self.rejected('STRICT_MESH_RATIO')
 def test_frame_mesh_size_refused(self):self.cap['frames'][0]['meshWorldSize']['z']=2;self.rejected('STRICT_MESH_DIMENSIONS')
 def test_missing_frame_refused(self):self.cap['frames'].pop();self.rejected('STRICT_FRAME_COUNT')
 def test_enemy_ground_below_four_mm_refused(self):self.cap['frames'][0]['worldMinY']=-.00401;self.rejected('STRICT_GROUND_PENETRATION')
 def test_enemy_ground_four_mm_boundary_is_allowed(self):
  f=self.cap['frames'][0];f['worldMinY']=-.004;f['meshWorldMin']['y']=-.004;f['meshWorldSize']['y']=2.004;f['meshSizeRatioToNeutral']['y']=1.002
  self.assertEqual(self.run_export()['status'],'STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED')
 def test_frame_drift_refused(self):self.cap['frames'][0]['rootLocalPositionDelta']=.001;self.rejected('STRICT_ROOT_SAMPLE_DRIFT')
 def test_null_graphics_refused(self):self.cap['graphicsDeviceType']='Null';self.rejected('STRICT_REAL_SOFTWARE_GRAPHICS_REQUIRED')
 def test_approval_refused(self):self.cap['visualAccepted']=True;self.rejected('STRICT_CAPTURE_STATUS')
 def test_bad_image_refused(self):(self.ev/'frame-0000.png').write_bytes(b'not-png');self.rejected('STRICT_FRAME_IDENTITY')
 def test_black_image_refused(self):
  p=self.ev/'frame-0000.png';Image.new('RGB',(960,540)).save(p);self.cap['frames'][0]['imageSha256']=s.sha(p);self.rejected('STRICT_BLANK_IMAGE')
 def test_weakpoint_image_link_refused(self):self.weak['samples'][0]['imageLabel']='wrong';self.rejected('STRICT_WEAKPOINT_IMAGE_LINK')
 def test_weakpoint_window_refused(self):self.weak['samples'][3]['weakPointExposed']=False;self.rejected('STRICT_WEAKPOINT_STATE')
 def test_weakpoint_not_restored_refused(self):self.weak['samples'][6]['localPlateRotations'][0]=dict(x=0,y=1,z=0,w=0);self.rejected('STRICT_PLATE_NOT_CHANGED_OR_RESTORED')
 def test_extra_generated_file_refused(self):(self.folder/'secret.log').write_text('fixture-secret');self.rejected('STRICT_GENERATED_ALLOWLIST')
 def test_extra_report_field_refused(self):self.imp['rawLogs']='fixture-secret';self.rejected('STRICT_SCHEMA_MISMATCH')
 def test_symlink_refused(self):(self.folder/'escape').symlink_to('/tmp');self.rejected('STRICT_SYMLINK_FORBIDDEN')
 def test_source_hash_refused(self):(self.folder/'Source/bulwark-candidate.fbx').write_bytes(b'changed');self.rejected('STRICT_DEPENDENCY_HASH')
 def test_orm_gamma_refused(self):
  p=self.folder/'Derived/ORM_00.png.meta';p.write_text(p.read_text().replace('sRGBTexture: 0','sRGBTexture: 1'));self.imp['dependencySha256']=s.dependency_digest(self.project,self.imp['dependencies']);self.cap['dependencySha256']=self.imp['dependencySha256'];self.rejected('STRICT_ORM_IMPORT_SETTINGS')
 def test_orm_row_order_hash_refused(self):
  self.imp['derivedTextures'][0]['decodedPixelSha256']=hashlib.sha256(Image.open(self.folder/'Derived/ORM_00.png').convert('RGBA').tobytes()).hexdigest();self.rejected('STRICT_ORM_IMPORTED_PIXEL_HASH')
 def test_orm_wrong_mapping_refused(self):
  p=self.folder/'Derived/ORM_00.png';Image.new('RGBA',(2,2),(90,12,0,215)).save(p);self.imp['derivedTextures'][0]['derivedSha256']=s.sha(p);self.imp['dependencySha256']=s.dependency_digest(self.project,self.imp['dependencies']);self.cap['dependencySha256']=self.imp['dependencySha256'];self.rejected('STRICT_ORM_PIXEL_MAPPING')
 def test_atomic_commit_failure_has_no_payload(self):
  original=Path.replace
  def fail(p,target):
   if p.name.startswith('.strict-safe-'):raise OSError('synthetic commit failure')
   return original(p,target)
  with patch.object(Path,'replace',fail):self.rejected('INVALID_EVIDENCE')
 def test_late_report_read_failure_has_no_payload(self):
  original=s.sha;counts={}
  def fail(p):
   if Path(p)==self.ev/'import-report.json':raise OSError('synthetic late read failure')
   return original(p)
  with patch.object(s,'sha',fail):self.rejected('INVALID_EVIDENCE')
 def test_staging_unlisted_file_is_not_uploaded(self):
  original=s.shutil.copyfile
  def inject(src,dest,*args,**kwargs):
   result=original(src,dest,*args,**kwargs)
   for parent in Path(dest).parents:
    if parent.name.startswith('.strict-safe-'):(parent/'unlisted.log').write_text('SECRET');break
   return result
  with patch.object(s.shutil,'copyfile',inject):self.rejected('STRICT_STAGING_ALLOWLIST')
 def test_staging_receipt_cannot_be_replaced(self):
  original=Path.write_bytes
  def inject(path,data):
   result=original(path,data)
   if path.name=='receipt.json' and path.parent.name.startswith('.strict-safe-'):original(path,b'{"approved":true}')
   return result
  with patch.object(Path,'write_bytes',inject):self.rejected('STRICT_STAGING_RECEIPT')
 def test_extra_file_created_during_final_receipt_hash_is_rejected(self):
  original=s.sha
  def inject(path):
   result=original(path)
   if Path(path).name=='receipt.json' and Path(path).parent.name.startswith('.strict-safe-'):(Path(path).parent/'unlisted.log').write_text('SECRET')
   return result
  with patch.object(s,'sha',inject):self.rejected('STRICT_STAGING_ALLOWLIST')
 def test_duplicate_json_refused(self):
  p=self.project/'CandidateImportInput/contract.json';p.write_text('{"mode":"STRICT_BINDING","mode":"DISCOVERY_ONLY"}');self.rejected('STRICT_DUPLICATE_JSON_KEY')
 def test_path_and_private_url_rejected(self):
  for name in ('../secret','https://private.example/token','Assets/Other/key','Packages/com.other/a'):
   with self.assertRaises(s.StrictError):s.dependency_digest(self.project,[name])

if __name__=='__main__':unittest.main()
