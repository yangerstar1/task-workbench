import contextlib,hashlib,io,json,os,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import package_technical as p,staged,plan
class TechnicalPackageTests(unittest.TestCase):
 def check_case(self,mutation=None,exit_code=0,expected=0,manifest_mutation=None):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);src=root/'technical';src.mkdir();lock=p.static_prerequisite()
   for n in ['bulwark-candidate.fbx','bulwark-animations.fbx']:(src/n).write_bytes(b'Kaydara FBX Binary fixture')
   (src/'bulwark-candidate.glb').write_bytes(b'glTF fixture');(src/'bulwark-review.blend').write_bytes(b'fixture')
   for n in ['bulwark-basecolor.png','bulwark-orm.png']:(src/n).write_bytes(b'\x89PNG\r\n\x1a\n'+b'\0'*8+struct.pack('>II',1024,1024))
   (src/'evaluated-validation.json').write_text(json.dumps({'status':'technical_checks_passed_visual_review_still_required','failures':[]}))
   (src/'binding-contract.json').write_text(json.dumps({'status':'source_graph_checked_import_unverified','failures':[]}))
   clips=[{'name':n,'duration_seconds':t,'root_motion':False} for n,t in plan.P['clips'].items()];(src/'clip-manifest.json').write_text(json.dumps(clips))
   for n in ['output-sha256.json','ASSET-LICENSE.json']+['numeric-'+c+'.json' for c in plan.REMAINING]:(src/n).write_text('{}')
   if mutation:mutation(src)
   payload={name:p.sha(src/name) for name in staged.technical_payload_names() if (src/name).is_file()}
   (src/'output-sha256.json').write_text(json.dumps(payload))
   if manifest_mutation:manifest_mutation(src)
   receipt={'stage':'technical','status':'COMPLETE_TECHNICAL_EVIDENCE_NOT_VISUAL_APPROVAL','art_source_manifest_sha256':lock['source_manifest_sha256'],'art_source_commit':lock['source_commit'],'execution_manifest_sha256':p.sha(p.HERE/'execution-manifest.json'),'execution_commit':'a'*40,'run_id':'123','run_attempt':'1','files':{f.name:p.sha(f) for f in src.iterdir()}}
   (src/'stage-receipt.json').write_text(json.dumps(receipt))
   with patch.dict(os.environ,GITHUB_SHA='a'*40,GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1'),contextlib.redirect_stdout(io.StringIO()):result=p.package(src,root/'package',exit_code)
   self.assertEqual(result,expected);d=json.loads((root/'package/producer-contract.json').read_text());self.assertFalse(d['visualApproved']);self.assertFalse(d['unityVerified']);self.assertFalse(d['moviesComplete'])
   self.assertEqual(d['scope'],'FULL_CANDIDATE' if expected==0 else 'PARTIAL_DIAGNOSTIC_NOT_FULL')
 def test_complete_source_fixture(self):self.check_case()
 def test_failed_process_retains_partial(self):self.check_case(exit_code=1,expected=1)
 def test_missing_model_rejected(self):self.check_case(lambda s:(s/'bulwark-candidate.fbx').unlink(),expected=1)
 def test_old_512_texture_rejected(self):self.check_case(lambda s:(s/'bulwark-orm.png').write_bytes(b'\x89PNG\r\n\x1a\n'+b'\0'*8+struct.pack('>II',512,512)),expected=1)
 def test_wrong_texture_shape_rejected(self):self.check_case(lambda s:(s/'bulwark-basecolor.png').write_bytes(b'\x89PNG\r\n\x1a\n'+b'\0'*8+struct.pack('>II',960,540)),expected=1)
 def test_failed_numeric_gate_rejected(self):self.check_case(lambda s:(s/'evaluated-validation.json').write_text(json.dumps({'status':'technical_checks_failed','failures':['floor']})),expected=1)
 def test_missing_clip_rejected(self):self.check_case(lambda s:(s/'clip-manifest.json').write_text('[]'),expected=1)
 def test_stale_nested_payload_sha_rejected(self):
  self.check_case(manifest_mutation=lambda s:(s/'bulwark-candidate.fbx').write_bytes(b'Kaydara FBX Binary changed'),expected=1)
 def test_mutable_stage_receipt_excluded(self):
  def mutate(s):
   f=s/'output-sha256.json';d=json.loads(f.read_text());d['stage-receipt.json']='0'*64;f.write_text(json.dumps(d))
  self.check_case(manifest_mutation=mutate,expected=1)
 def test_self_referential_payload_manifest_rejected(self):
  def mutate(s):
   f=s/'output-sha256.json';d=json.loads(f.read_text());d['output-sha256.json']='0'*64;f.write_text(json.dumps(d))
  self.check_case(manifest_mutation=mutate,expected=1)
 def test_payload_manifest_exact_raw_bytes_and_mutable_receipt(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td)
   for name in staged.technical_payload_names():(folder/name).write_bytes(('actual payload '+name).encode())
   (folder/'stage-receipt.json').write_text('initial receipt')
   staged.write_payload_manifest(folder);first=(folder/'output-sha256.json').read_bytes()
   for name,digest in staged.verify_payload_manifest(folder).items():self.assertEqual(digest,hashlib.sha256((folder/name).read_bytes()).hexdigest())
   (folder/'stage-receipt.json').write_text('final receipt')
   self.assertEqual(first,(folder/'output-sha256.json').read_bytes());staged.verify_payload_manifest(folder)
   # The final outer receipt pins the now-stable inner manifest bytes.
   staged.finalize_receipt(folder,{'stage':'technical','status':'COMPLETE_TECHNICAL_EVIDENCE_NOT_VISUAL_APPROVAL'})
   final=json.loads((folder/'stage-receipt.json').read_text())
   self.assertEqual(set(final['files']),set(staged.technical_payload_names())|{'output-sha256.json'})
   for name,digest in final['files'].items():self.assertEqual(digest,p.sha(folder/name))
   self.assertEqual(final['files']['output-sha256.json'],hashlib.sha256(first).hexdigest())
   staged.verify_payload_manifest(folder)
 def test_unbounded_output_refused(self):
  with tempfile.TemporaryDirectory() as td:
   pth=Path(td);(pth/'old').write_text('old')
   with self.assertRaises(Exception):p.package(pth,pth,0)
if __name__=='__main__':unittest.main()
