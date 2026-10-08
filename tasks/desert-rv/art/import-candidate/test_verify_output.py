import unittest,tempfile,json,hashlib
from pathlib import Path
from verify_output import export,EvidenceError,EXPECTED
class ExportTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'task';self.out=Path(self.tmp.name)/'export'
  self.c={'id':'pouncer-test','mode':'DISCOVERY_ONLY','scope':'DEATH_DIAGNOSTIC_NOT_FULL','sourceCommit':'a'*40,'runUrl':'https://github.com/yangerstar1/task-workbench/actions/runs/123','artifactName':'pouncer-test','artifactSha256':'b'*64,'files':[{'file':'model.fbx','sha256':hashlib.sha256(b'model').hexdigest()}]}
  self.write('unity/CandidateImportInput/contract.json',json.dumps(self.c));self.base=self.root/'unity/Assets/DesertRV/CandidateArtDiscovery';self.candidate=self.base/self.c['id']
  for p in ['pouncer-test.meta','pouncer-test/Source.meta','pouncer-test/discovery-contract.json.meta','pouncer-test/Source/model.fbx.meta']:self.write('unity/Assets/DesertRV/CandidateArtDiscovery/'+p,'fileFormatVersion: 2\nguid: '+'c'*32+'\n')
  self.write('unity/Assets/DesertRV/CandidateArtDiscovery/pouncer-test/Source/model.fbx','model');self.write('unity/Assets/DesertRV/CandidateArtDiscovery/pouncer-test/discovery-contract.json',json.dumps(self.c))
  self.report={k:self.c[k] for k in ['mode','scope','sourceCommit','runUrl','artifactName','artifactSha256']};self.report.update(status='discovered-unreviewed-not-bound',failures=[],approved=False,bindingCalibrated=False,contractSha256=hashlib.sha256(json.dumps(self.c).encode()).hexdigest(),models=[{'file':'model.fbx'}]);self.save()
  self.write('artifacts/candidate-art/test.xml','<test-run><test-case fullname="'+EXPECTED+'" result="Passed"/></test-run>')
 def write(self,p,s):
  p=self.root/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
 def save(self):self.write('unity/JourneyEvidence/CandidateArtDiscovery/discovery-report.json',json.dumps(self.report))
 def rejected(self,**kw):
  with self.assertRaises(EvidenceError):export(self.root,self.out,**kw)
  self.assertEqual([p.name for p in self.out.iterdir()],['receipt.json']);self.assertEqual(json.loads((self.out/'receipt.json').read_text())['status'],'FAILED_NOT_ACCEPTED')
 def test_valid(self):
  r=export(self.root,self.out);self.assertFalse(r['approved']);self.assertTrue(r['files'])
  for f in r['files']:self.assertEqual(hashlib.sha256((self.out/f['path']).read_bytes()).hexdigest(),f['sha256'])
 def nested(self,name='technical/model.fbx'):
  for leaf in ['model.fbx','model.fbx.meta']:(self.candidate/'Source'/leaf).unlink()
  self.c['files'][0]['file']=name
  encoded=json.dumps(self.c);self.write('unity/CandidateImportInput/contract.json',encoded);self.write('unity/Assets/DesertRV/CandidateArtDiscovery/pouncer-test/discovery-contract.json',encoded)
  self.report['contractSha256']=hashlib.sha256(encoded.encode()).hexdigest();self.report['models']=[{'file':name}];self.save()
  # Only create files for the valid case; malformed names must fail before output copy.
  if name=='technical/model.fbx':
   self.write('unity/Assets/DesertRV/CandidateArtDiscovery/pouncer-test/Source/'+name,'model')
   for leaf in ['technical.meta',name+'.meta']:self.write('unity/Assets/DesertRV/CandidateArtDiscovery/pouncer-test/Source/'+leaf,'fileFormatVersion: 2\nguid: '+'c'*32+'\n')
 def test_technical_prefix_preserved(self):
  self.nested();r=export(self.root,self.out)
  names={f['path'] for f in r['files']}
  self.assertIn('CandidateArtDiscovery/pouncer-test/Source/technical/model.fbx',names)
  self.assertIn('CandidateArtDiscovery/pouncer-test/Source/technical.meta',names)
 def test_parent_path_rejected(self):self.nested('technical/../model.fbx');self.rejected()
 def test_absolute_path_rejected(self):self.nested('/technical/model.fbx');self.rejected()
 def test_two_level_path_rejected(self):self.nested('technical/sub/model.fbx');self.rejected()
 def test_unknown_prefix_rejected(self):self.nested('other/model.fbx');self.rejected()
 def test_extra_nested_file_rejected(self):
  self.nested();self.write('unity/Assets/DesertRV/CandidateArtDiscovery/pouncer-test/Source/technical/extra.png','bad');self.rejected()
 def test_nested_symlink_rejected(self):
  self.nested();p=self.candidate/'Source/technical/model.fbx';p.unlink();p.symlink_to(self.root/'unity/CandidateImportInput/contract.json');self.rejected()
 def test_missing_technical_meta_rejected(self):
  self.nested();(self.candidate/'Source/technical.meta').unlink();self.rejected()
 def test_extra_script(self):self.write('unity/Assets/DesertRV/CandidateArtDiscovery/pouncer-test/evil.cs','x');self.rejected()
 def test_prefab(self):self.write('unity/Assets/DesertRV/CandidateArtDiscovery/pouncer-test/x.prefab','x');self.rejected()
 def test_extra_report(self):self.report['rawLog']='sensitive';self.save();self.rejected()
 def test_wrong_source(self):self.report['sourceCommit']='d'*40;self.save();self.rejected()
 def test_wrong_contract(self):self.report['contractSha256']='d'*64;self.save();self.rejected()
 def test_approved(self):self.report['approved']=True;self.save();self.rejected()
 def test_raw_failure_not_exported(self):self.report['failures']=['secret path raw exception'];self.save();self.rejected();self.assertNotIn('secret',(self.out/'receipt.json').read_text())
 def test_native_failure(self):self.rejected(native='failure')
 def test_protected_failure(self):self.rejected(protected='failure')
 def test_changed_input(self):self.write('unity/Assets/DesertRV/CandidateArtDiscovery/pouncer-test/Source/model.fbx','bad');self.rejected()
 def test_symlink(self):
  p=self.candidate/'Source/model.fbx';p.unlink();p.symlink_to(self.root/'unity/CandidateImportInput/contract.json');self.rejected()
 def test_missing_native(self):
  (self.root/'artifacts/candidate-art/test.xml').unlink();self.rejected()
if __name__=='__main__':unittest.main()

