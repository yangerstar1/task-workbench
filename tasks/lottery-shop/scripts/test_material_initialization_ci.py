#!/usr/bin/env python3
import struct,copy,hashlib,itertools,json,os,re,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import material_initialization_ci as ci
IDENT=dict(sourceCommit='1'*40,reviewedCandidateCommit='2'*40,runId='123',runAttempt='1')
ENV=dict(GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1')
def receipt():return dict(smoothnessObserved=True,smoothnessMaterialId=34,actualSmoothnessBits=0x3f35c290,expectedSmoothnessBits=0x3f35c290,schemaVersion=1,scope=ci.SCOPE,status='COMPLETE',sourceCommit='1'*40,runId='123',runAttempt='1',stageCode=40,materialId=-1,materialsCompleted=35,firstFailureStage=-1,firstFailureMaterial=-1,predicateCode=0,slotIndex=-1,exceptionKind='NONE',diagnosticWriteFailed=False,elapsedMs=100,completedBits=(1<<35)-1)
def failure(code=15,slot=-1):
 v=receipt();v.update(status='FAILED',stageCode=35 if code>=46 else 20 if code<=18 else 22,materialId=0,materialsCompleted=0,completedBits=0,firstFailureStage=35 if code>=46 else 20 if code<=18 else 22,firstFailureMaterial=0,predicateCode=code,slotIndex=slot,exceptionKind='INVALID_OPERATION');v.update(smoothnessMaterialId=0);
 if code==8:v['actualSmoothnessBits']+=1
 return v
class Tests(unittest.TestCase):
 def export(self,v):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(t.name);src=root/ci.visual.TASK/'artifacts/visual-candidate'/ci.NAME;src.parent.mkdir(parents=True);raw=v if isinstance(v,bytes) else json.dumps(v).encode();src.write_bytes(raw);dest=ci.visual.outdir(root)/ci.NAME
  with patch.dict(os.environ,ENV),patch.object(ci.visual,'identity',return_value=IDENT):
   try:ci.export(root);ok=True
   except ValueError:ok=False
  return dest,raw,ok
 def test_complete_receipt_exact_export(self):
  v=receipt();ci.validate(v,IDENT);p,raw,ok=self.export(v);self.assertTrue(ok);self.assertEqual(p.read_bytes(),raw)
 def test_all45_predicates_and_slots_preserved_failed(self):
  for code in ci.PREDICATES:
   slots=range(4) if code in (22,23,24) else range(7) if code in (25,26,47) else [-1]
   for slot in slots:ci.validate(failure(code,slot),IDENT)
  p,raw,ok=self.export(failure());self.assertFalse(ok);self.assertEqual(p.read_bytes(),raw)
 def test_running_and_write_failure_never_pass(self):
  for v in [dict(receipt(),status='RUNNING'),dict(receipt(),diagnosticWriteFailed=True)]:
   p,raw,ok=self.export(v);self.assertFalse(ok);self.assertEqual(p.read_bytes(),raw)
 def test_unclassified_native_exception_has_no_invented_predicate(self):
  v=failure();v.update(predicateCode=0,slotIndex=-1,exceptionKind='UNITY');ci.validate(v,IDENT)
 def test_unknown_extra_fields_and_text_rejected(self):
  for k,x in [('rawLog','PRIVATE'),('materialId','PrivateAsset'),('predicateCode','PRIVATE'),('exceptionKind','PRIVATE'),('scope','PRIVATE')]:
   v=failure();v[k]=x;p,_,ok=self.export(v);self.assertFalse(ok);self.assertFalse(p.exists())
 def test_wrong_source_run_attempt_rejected(self):
  for k in ['sourceCommit','runId','runAttempt']:
   v=receipt();v[k]='wrong'
   with self.assertRaises(ValueError):ci.validate(v,IDENT)
 def test_wrong_live_run_rejected(self):
  with patch.dict(os.environ,dict(ENV,GITHUB_RUN_ID='999')),patch.object(ci.visual,'identity',return_value=IDENT),tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):ci.export(Path(d))
 def test_duplicate_keys_no_export(self):
  raw=json.dumps(receipt()).replace('"predicateCode": 0','"predicateCode": "PRIVATE", "predicateCode": 0');p,_,ok=self.export(raw.encode());self.assertFalse(ok);self.assertFalse(p.exists())
 def test_empty_oversized_invalid_utf8_rejected(self):
  for raw in [b'',b' '*8193,b'\xff',b'{}']:
   p,_,ok=self.export(raw);self.assertFalse(ok);self.assertFalse(p.exists())
 def test_numeric_bounds_and_bool_rejected(self):
  for k,x in [('stageCode',True),('stageCode',999),('materialId',35),('materialId',-2),('materialsCompleted',36),('elapsedMs',3600001),('elapsedMs',-1),('completedBits',1<<35),('predicateCode',48),('predicateCode',True),('slotIndex',7),('slotIndex',True),('diagnosticWriteFailed',0)]:
   v=receipt();v[k]=x
   with self.subTest(k=k,x=x),self.assertRaises(ValueError):ci.validate(v,IDENT)
 def test_predicate_context_and_slot_constraints(self):
  for updates in [dict(firstFailureStage=22,stageCode=22),dict(firstFailureMaterial=-1,materialId=-1),dict(exceptionKind='IO'),dict(slotIndex=0),dict(firstFailureMaterial=1),dict(firstFailureStage=1)]:
   v=failure();v.update(updates)
   with self.assertRaises(ValueError):ci.validate(v,IDENT)
  for code,slot in [(22,-1),(22,4),(25,-1),(25,7)]:
   with self.assertRaises(ValueError):ci.validate(failure(code,slot),IDENT)
 def test_completion_requires_all35_exact_bits(self):
  for changes in [dict(materialsCompleted=33,completedBits=(1<<33)-1),dict(materialId=0),dict(stageCode=34),dict(completedBits=1),dict(firstFailureStage=20)]:
   v=receipt();v.update(changes)
   with self.assertRaises(ValueError):ci.validate(v,IDENT)
 def test_failure_none_and_nonfailure_error_rejected(self):
  for v in [dict(failure(),exceptionKind='NONE'),dict(receipt(),exceptionKind='UNITY'),dict(receipt(),predicateCode=1)]:
   with self.assertRaises(ValueError):ci.validate(v,IDENT)
 def test_source_symlink_and_stale_dest(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV),patch.object(ci.visual,'identity',return_value=IDENT):
   root=Path(d);src=root/ci.visual.TASK/'artifacts/visual-candidate'/ci.NAME;src.parent.mkdir(parents=True);other=root/'other';other.write_text(json.dumps(receipt()));src.symlink_to(other);dest=ci.visual.outdir(root)/ci.NAME;dest.parent.mkdir(parents=True);dest.write_text('stale')
   with self.assertRaises(ValueError):ci.export(root)
   self.assertFalse(dest.exists())
 def test_cli_fixed_failure_only(self):
  r=subprocess.run([sys.executable,ci.__file__],capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'));self.assertEqual((r.returncode,r.stdout,r.stderr),(1,'MATERIAL_INITIALIZATION_DIAGNOSTIC_REJECTED\n',''))
 def source(self):return (Path(__file__).resolve().parents[3]/ci.visual.TASK/'unity/Assets/G3/Editor/G3ShopArtImporter.cs').read_text()
 def test_enum_predicates_match_producer(self):
  s=self.source();enum=s.split('enum MaterialPredicate {',1)[1].split('}',1)[0];pairs={int(i):n for n,i in re.findall(r'(\w+)=(\d+)',enum)};self.assertEqual(pairs,{0:'NONE',**ci.PREDICATES})
 def test_every_original_predicate_expression_unchanged(self):
  found=re.findall(r'RequireMaterial\((.*?),MaterialPredicate\.(\w+),(i|-1)\);',self.source());found=[x for x in found if x[1] not in ('OWNED_MATERIAL_IDENTITY','OWNED_MATERIAL_STATE')];self.assertEqual(len(found),45);found=[(expr,name,slot) for expr,name,slot in found if name!='AUTHOR_SMOOTHNESS'];found.insert(7,('material.GetFloat("_Smoothness")== (packed?1:1-Mathf.Clamp01(item.roughness))','AUTHOR_SMOOTHNESS','-1'))
  reverse={n:c for c,n in ci.PREDICATES.items()};normalized=[(reverse[name],re.sub(r'\s+','',expr),name,slot) for expr,name,slot in found]
  self.assertEqual(hashlib.sha256(json.dumps(normalized,separators=(',',':')).encode()).hexdigest(),'687cbc15af3a16199ee000a364cf4ad60147c54d9300099e5f1ea738210f00aa')
 def test_shortcircuit_equivalence_exhaustive(self):
  for size in (1,2,3,4):
   for values in itertools.product((False,True),repeat=size):
    original=all(values);visited=[]
    for i,x in enumerate(values):
     visited.append(i)
     if not x:break
    self.assertEqual(original,all(values[i] for i in visited));self.assertEqual(len(visited),size if original else values.index(False)+1)
 def test_original_exception_rethrow_and_trace_no_material_mutation(self):
  s=self.source();self.assertIn('catch(Exception error){trace?.Failure(error);throw;}',s);self.assertIn('finally{trace?.Finish();}',s);self.assertIn('MaterialContractFailure:InvalidOperationException',s)
  body=s.split('sealed class MaterialTrace',1)[1].split('static void RequireMaterial',1)[0]
  for forbidden in ['LoadAsset','SaveAssets','Refresh(','SetFloat(','SetTexture(','SetColor(','Debug.Log','error.Message','error.StackTrace']:self.assertNotIn(forbidden,body)
  self.assertIn('catch{receipt.diagnosticWriteFailed=true;}',body);self.assertIn('>8192',body)
 def test_fixed_material_table_and_capture_scope(self):
  s=self.source();names=re.findall(r'"([A-Za-z0-9_]+)"',s.split('static readonly string[] Names={',1)[1].split('};',1)[0]);self.assertEqual(len(names),35);self.assertEqual(names[-3:],['Tool_Dock_Liner','Nearfield_Tea','Plant_Stem_Green']);self.assertIn('args[i+1]!="Lottery.G3.VisualCandidate.Tests"',s)
 def test_no_detail_explicit_initialization_before_original_assertions(self):
  s=self.source();start=s.index('material.SetTexture("_DetailAlbedoMap",null)');end=s.index('MaterialPredicate.DETAIL_ALBEDO_ABSENT');self.assertLess(start,end)
  block=s[start:end]
  for x in ['material.SetTexture("_DetailNormalMap",null)','material.DisableKeyword("_DETAIL_MULX2")','material.DisableKeyword("_DETAIL_SCALED")']:self.assertIn(x,block)
  self.assertNotIn('SetFloat(',block);self.assertNotIn('_DetailMask',block)
 def test_workflow_only_fixed_export_path_and_test(self):
  w=(Path(__file__).resolve().parents[3]/ci.visual.WORKFLOW).read_text();self.assertEqual(w.count('scripts/material_initialization_ci.py'),1);self.assertEqual(w.count('/evidence/visual-candidate/'+ci.NAME),1);self.assertIn('scripts/test_material_initialization_ci.py -v',w);self.assertNotIn('*.json',w)
 def test_payload_stays_small_with_max_fields(self):
  v=dict(receipt(),elapsedMs=3600000,runId='9'*20,runAttempt='9'*20);self.assertLess(len(json.dumps(v).encode()),8192)
 def test_receipt_fields_exact_producer(self):
  body=self.source().split('sealed class MaterialProgress',1)[1].split('sealed class MaterialTrace',1)[0];fields=set()
  for group in re.findall(r'public (?:int|long|bool|string) ([^;]+);',body):fields.update(x.split('=')[0].strip() for x in group.split(','))
  self.assertEqual(fields,ci.FIELDS)
 def test_unknown_predicate_slot_cannot_disclose_arbitrary_data(self):
  for update in [dict(predicateCode=0,slotIndex=1),dict(slotIndex='PRIVATE'),dict(firstFailureStage=True),dict(firstFailureMaterial=True),dict(completedBits=True),dict(status='PRIVATE')]:
   v=failure();v.update(update)
   with self.assertRaises(ValueError):ci.validate(v,IDENT)
 def test_smoothness_midpoint_exact_binary32_model(self):
  f=lambda x:struct.unpack('<f',struct.pack('<f',x))[0]
  bits=lambda x:struct.unpack('<I',struct.pack('<f',x))[0]
  rough=f(.28999999165534973);extended=1-rough;stored=f(extended)
  self.assertNotEqual(extended,stored);self.assertEqual(stored-extended,2**-25);self.assertEqual(bits(rough),0x3e947ae1);self.assertEqual(bits(extended),0x3f35c290);self.assertEqual(bits(stored),bits(extended))
 def test_smoothness_one_ulp_and_nonfinite_not_success(self):
  for actual in (0x3f35c28f,0x3f35c291,0x7f800000,0xff800000,0x7fc00000):
   v=receipt();v['actualSmoothnessBits']=actual
   with self.assertRaises(ValueError):ci.validate(v,IDENT)
   v=failure(8);v['actualSmoothnessBits']=actual;ci.validate(v,IDENT)
  for bits in (0x7f800000,0xff800000,0x7fc00000):
   v=receipt();v.update(actualSmoothnessBits=bits,expectedSmoothnessBits=bits)
   with self.assertRaises(ValueError):ci.validate(v,IDENT)
 def test_smoothness_observation_closed_numeric_context(self):
  for updates in [dict(smoothnessObserved=1),dict(smoothnessMaterialId=35),dict(actualSmoothnessBits=True),dict(expectedSmoothnessBits=-1),dict(actualSmoothnessBits=4294967296),dict(actualSmoothnessBits='private'),dict(smoothnessObserved=False),dict(smoothnessMaterialId=-1)]:
   v=receipt();v.update(updates)
   with self.assertRaises(ValueError):ci.validate(v,IDENT)
  v=failure(8);v['actualSmoothnessBits']=v['expectedSmoothnessBits']
  with self.assertRaises(ValueError):ci.validate(v,IDENT)
 def test_smoothness_unobserved_early_failure_valid(self):
  v=failure(1);v.update(smoothnessObserved=False,smoothnessMaterialId=-1,actualSmoothnessBits=0,expectedSmoothnessBits=0);ci.validate(v,IDENT)
 def test_all35_roughness_float32_and_clamp_boundaries(self):
  root=Path(__file__).resolve().parents[3];items=json.loads((root/ci.visual.TASK/'unity/Assets/G3/Shop/Resources/G3/Shop/materials.json').read_text())['materials'];self.assertEqual(len(items),35)
  f=lambda x:struct.unpack('<f',struct.pack('<f',x))[0]
  bits=lambda x:struct.unpack('<I',struct.pack('<f',x))[0]
  for item in items:
   r=f(item['roughness']);expected=item.get('packedSmoothnessScale',1) if item.get('roughnessTexture') else 1-max(0,min(1,r));self.assertEqual(bits(f(expected)),bits(expected));self.assertTrue(0<=f(expected)<=1)
  for r in (-100,-0.0,0,2**-149,.5,1,100):self.assertEqual(bits(f(1-max(0,min(1,f(r))))),bits(1-max(0,min(1,f(r)))))
 def test_smoothness_source_zero_tolerance_and_no_setter_change(self):
  s=self.source();self.assertIn('material.SetFloat("_Smoothness",1-Mathf.Clamp01(item.roughness))',s);self.assertIn('return BitConverter.ToUInt32(BitConverter.GetBytes(value),0)',s)
  body=s.split('static void RequireSmoothness(',1)[1].split('static void RequireMaterial',1)[0]
  self.assertIn('packed?PackedSmoothness(item):1-Mathf.Clamp01(item.roughness)',body);self.assertIn('FiniteSingleBits(actual)&&FiniteSingleBits(expected)&&actual==expected',body);self.assertIn('trace?.ObserveSmoothness(actual,expected)',body)
  for forbidden in ('Approximately','Abs(','SetFloat','epsilon','tolerance'):self.assertNotIn(forbidden,body)
 def test_stem_id34_failure_preserved(self):
  v=failure();v.update(materialId=34,firstFailureMaterial=34,smoothnessMaterialId=34);ci.validate(v,IDENT);p,raw,ok=self.export(v);self.assertFalse(ok);self.assertEqual(p.read_bytes(),raw)
 def test_old34_complete_no_longer_complete(self):
  v=receipt();v.update(materialsCompleted=34,completedBits=(1<<34)-1)
  with self.assertRaises(ValueError):ci.validate(v,IDENT)
 def test_unknown_id35_and_high_bit_rejected(self):
  for values in [dict(materialId=35,firstFailureMaterial=35),dict(materialId='Plant_Stem_Green'),dict(completedBits=1<<35,materialsCompleted=1)]:
   v=failure();v.update(values)
   with self.assertRaises(ValueError):ci.validate(v,IDENT)
 def test_initializer_ids_equal_reflection_and_external_manifest(self):
  import reflection_progress_ci as progress
  names=re.findall(r'"([A-Za-z0-9_]+)"',self.source().split('static readonly string[] Names={',1)[1].split('};',1)[0]);self.assertEqual(tuple(names),tuple(progress.MATERIAL_IDS))
 def test_stem_smoothness_bits_and_unknown_id_bounds(self):
  v=failure(8);v.update(materialId=34,firstFailureMaterial=34,smoothnessMaterialId=34);ci.validate(v,IDENT)
  v['smoothnessMaterialId']=35
  with self.assertRaises(ValueError):ci.validate(v,IDENT)
  v=receipt();self.assertEqual(v['smoothnessMaterialId'],34);ci.validate(v,IDENT)

 def test_postimport_failure_stages_and_state_slots_are_bounded(self):
  for stage in (35,36,37,38,39):
   for code,slots in ((46,[-1]),(47,range(7))):
    for slot in slots:
     v=failure(code,slot);v.update(stageCode=stage,firstFailureStage=stage);ci.validate(v,IDENT)
     p,raw,ok=self.export(v);self.assertFalse(ok);self.assertEqual(p.read_bytes(),raw)
  for changes in [dict(stageCode=22,firstFailureStage=22),dict(slotIndex=7),dict(slotIndex=-1),dict(materialId=-1,firstFailureMaterial=-1),dict(predicateCode=48)]:
   v=failure(47,3);v.update(changes)
   with self.subTest(changes=changes),self.assertRaises(ValueError):ci.validate(v,IDENT)
 def test_unknown_renderer_material_identity_is_bounded_without_name(self):
  v=failure(46);v.update(materialId=-1,firstFailureMaterial=-1);ci.validate(v,IDENT)
  for key in ('actualPath','actualGuid','materialName','rawLog'):
   bad=dict(v);bad[key]='UNTRUSTED';p,_,ok=self.export(bad);self.assertFalse(ok);self.assertFalse(p.exists())
 def require_remap_contract(self,s):
  setup=s.split('static void PrepareObserved',1)[1].split('enum MaterialPredicate',1)[0]
  self.assertNotIn('AssetImporter.GetAtPath',setup);self.assertNotIn('AddRemap(',setup)
  self.assertLess(setup.index('owned.Add(item.name,new OwnedMaterialState'),setup.index('RemapModel(model,true,owned)'))
  for token in ('RequireOwnedMaterials(owned,trace,35)','RequireOwnedMaterials(owned,trace,36);RequireModelBindings(model,owned,trace,36)',
                'RemapModel(toolFile,false,owned);RequireOwnedMaterials(owned,trace,37);RequireModelBindings(toolFile,owned,trace,37)',
                'RequireOwnedMaterials(owned,trace,39)'):self.assertIn(token,setup)
  remap=s.split('static void RemapModel(',1)[1].split('static void RequireModelBindings(',1)[0]
  self.assertLess(remap.index('AssetImporter.GetAtPath'),remap.index('importer.AddRemap'))
  self.assertLess(remap.index('importer.AddRemap'),remap.index('importer.SaveAndReimport'))
  self.assertEqual(remap.count('SaveAndReimport'),1)
  for token in ('Texture(', 'PackRoughness(', 'ImportAsset(', 'Refresh('):self.assertNotIn(token,remap)
 def test_remap_occurs_after_all_dependency_imports_source_negative_mutations(self):
  s=self.source();self.require_remap_contract(s)
  for before,after in [('owned.Add(item.name,new OwnedMaterialState','importer.AddRemap(item.name,new OwnedMaterialState'),
                       ('RequireModelBindings(toolFile,owned,trace,37)','SkipToolBindings(toolFile,owned,trace,37)'),
                       ('importer.SaveAndReimport();','Texture("late.png",false);importer.SaveAndReimport();')]:
   changed=s.replace(before,after);self.assertNotEqual(s,changed)
   with self.assertRaises(AssertionError):self.require_remap_contract(changed)
 def require_identity_contract(self,s):
  body=s.split('public void RequireIdentity(Material actual)',1)[1].split('public void RequireState()',1)[0]
  for token in ('actual==Material','LoadAssetAtPath<Material>(Path)==actual','IsMainAsset(actual)','GetAssetPath(actual)==Path',
                'AssetPathToGUID(Path)==Guid','GUIDToAssetPath(Guid)==Path','TryGetGUIDAndLocalFileIdentifier(actual',
                'guid==Guid&&id==localId'):self.assertIn(token,body)
  checks=s.split('static void RequireModelBindings(',1)[1].split('static void BuildRuntimePrefab(',1)[0]
  for token in ('importer.GetExternalObjectMap()','mapped==state.Material','state.RequireIdentity(mapped as Material)',
                'GetComponentsInChildren<Renderer>(true)','renderer.sharedMaterials','owned[name].RequireIdentity(material)'):self.assertIn(token,checks)
  build=s.split('static void BuildRuntimePrefab(',1)[1].split('static Color SourceLinearBaseColor',1)[0]
  self.assertIn('RequireRendererMaterial(material,owned,trace,38);',build)
  self.assertIn('RequireRendererBindings(AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath),owned,trace,38);',build)
 def test_identity_checks_reject_name_shader_only_and_wrong_guid_source_mutations(self):
  s=self.source();self.require_identity_contract(s)
  for token in ('actual==Material','GetAssetPath(actual)==Path','guid==Guid&&id==localId','mapped==state.Material','owned[name].RequireIdentity(material)'):
   with self.subTest(token=token),self.assertRaises(AssertionError):self.require_identity_contract(s.replace(token,'true'))
 def test_snapshot_validation_is_read_only_and_covers_all_authored_state(self):
  s=self.source();body=s.split('sealed class OwnedMaterialState',1)[1].split('static void RemapModel',1)[0]
  for forbidden in ('SetFloat(','SetColor(','SetTexture(','SaveAsset','ImportAsset(','Refresh(','SetMaterialKeywords','EnableKeyword','DisableKeyword'):self.assertNotIn(forbidden,body)
  for token in ('AuthoredTextureSlots.Concat','AuthoredFloatSlots.Concat','"_MainTex"','"_Color"','"_DetailAlbedoMap"','"_DetailNormalMap"',
                '"_Blend"','"_SrcBlend"','"_DstBlend"','"_ZWrite"','SingleBits','shaderKeywords.OrderBy','globalIlluminationFlags','doubleSidedGI','enableInstancing'):self.assertIn(token,body)
  self.assertEqual(set(map(int,re.findall(r'MaterialPredicate.OWNED_MATERIAL_STATE,(\d)',body))),set(range(7)))
 def test_manifest_felt_liner_brass_contracts_are_not_relaxed(self):
  base=Path(__file__).resolve().parents[1]/'unity/Assets/G3'
  manifest=json.loads((base/'Shop/Resources/G3/Shop/materials.json').read_text())['materials'];items={x['name']:x for x in manifest}
  self.assertEqual(items['Dark_Green_Felt']['normalStrength'],.6);self.assertEqual(items['Tool_Dock_Liner']['normalStrength'],.45)
  self.assertEqual(items['Tool_Dock_Liner']['roughness'],.92);self.assertFalse(items['Tool_Dock_Liner'].get('roughnessTexture'))
  self.assertEqual({k:items[k]['packedSmoothnessScale'] for k in ('Warm_Oak','Brass_Worn','Dark_Green_Felt')},{'Warm_Oak':.78,'Brass_Worn':.72,'Dark_Green_Felt':.40});self.assertEqual(items['Brass_Worn']['normalStrength'],.18);self.assertTrue(items['Brass_Worn']['roughnessTexture'])
  fixture=(base/'Tests/VisualCandidate/VisualCandidateCaptureTests.cs').read_text()
  for token in ('felt.GetFloat("_BumpScale"), Is.EqualTo(.60f).Within(.0001f)','liner.GetFloat("_Smoothness"), Is.EqualTo(.08f).Within(.0001f)',
                'brass.GetFloat("_BumpScale"), Is.EqualTo(.18f).Within(.0001f)','brass.GetFloat("_Smoothness"), Is.EqualTo(.72f).Within(.0001f)',
                'RequireOwnedRuntimeMaterial(felt,"Dark_Green_Felt")','RequireOwnedRuntimeMaterial(liner,"Tool_Dock_Liner")','RequireOwnedRuntimeMaterial(brass,"Brass_Worn")'):
   self.assertIn(token,fixture)

if __name__=='__main__':unittest.main()
