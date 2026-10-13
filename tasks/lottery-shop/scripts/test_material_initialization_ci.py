#!/usr/bin/env python3
import copy,hashlib,itertools,json,os,re,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import material_initialization_ci as ci
IDENT=dict(sourceCommit='1'*40,reviewedCandidateCommit='2'*40,runId='123',runAttempt='1')
ENV=dict(GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1')
def receipt():return dict(schemaVersion=1,scope=ci.SCOPE,status='COMPLETE',sourceCommit='1'*40,runId='123',runAttempt='1',stageCode=40,materialId=-1,materialsCompleted=34,firstFailureStage=-1,firstFailureMaterial=-1,predicateCode=0,slotIndex=-1,exceptionKind='NONE',diagnosticWriteFailed=False,elapsedMs=100,completedBits=(1<<34)-1)
def failure(code=15,slot=-1):
 v=receipt();v.update(status='FAILED',stageCode=20 if code<=18 else 22,materialId=0,materialsCompleted=0,completedBits=0,firstFailureStage=20 if code<=18 else 22,firstFailureMaterial=0,predicateCode=code,slotIndex=slot,exceptionKind='INVALID_OPERATION');return v
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
   slots=range(4) if code in (22,23,24) else range(7) if code in (25,26) else [-1]
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
  for k,x in [('stageCode',True),('stageCode',999),('materialId',34),('materialId',-2),('materialsCompleted',35),('elapsedMs',3600001),('elapsedMs',-1),('completedBits',1<<34),('predicateCode',46),('predicateCode',True),('slotIndex',7),('slotIndex',True),('diagnosticWriteFailed',0)]:
   v=receipt();v[k]=x
   with self.subTest(k=k,x=x),self.assertRaises(ValueError):ci.validate(v,IDENT)
 def test_predicate_context_and_slot_constraints(self):
  for updates in [dict(firstFailureStage=22,stageCode=22),dict(firstFailureMaterial=-1,materialId=-1),dict(exceptionKind='IO'),dict(slotIndex=0),dict(firstFailureMaterial=1),dict(firstFailureStage=1)]:
   v=failure();v.update(updates)
   with self.assertRaises(ValueError):ci.validate(v,IDENT)
  for code,slot in [(22,-1),(22,4),(25,-1),(25,7)]:
   with self.assertRaises(ValueError):ci.validate(failure(code,slot),IDENT)
 def test_completion_requires_all34_exact_bits(self):
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
  found=re.findall(r'RequireMaterial\((.*?),MaterialPredicate\.(\w+),(i|-1)\);',self.source());self.assertEqual(len(found),45)
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
  s=self.source();names=re.findall(r'"([A-Za-z0-9_]+)"',s.split('static readonly string[] Names={',1)[1].split('};',1)[0]);self.assertEqual(len(names),34);self.assertEqual(names[-2:],['Tool_Dock_Liner','Nearfield_Tea']);self.assertIn('args[i+1]!="Lottery.G3.VisualCandidate.Tests"',s)
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
if __name__=='__main__':unittest.main()
