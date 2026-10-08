import json,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import supply_evidence as s
class SupplyEvidenceTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name);self.folder=self.root/'JourneyEvidence/supplies';self.folder.mkdir(parents=True)
  self.report=dict(status=s.STATUS,graphicsDeviceType='OpenGLCore',graphicsDeviceName='llvmpipe test',bufferSceneTransitionsChecked=3,captureBuffersReleased=True,savedScenes=[],fixtures=[],images=[])
  for name in ['JourneyBootstrap',*s.env.REGIONS]:
   for ext in ('','.meta'):
    rel=s.env.GENERATED+'/'+name+'.unity'+ext;p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture');h=hashlib.sha256(p.read_bytes()).hexdigest();self.report['savedScenes'].append(dict(path=rel,beforeSha256=h,afterSha256=h))
  ids=(('apron-ammo','garage-kit'),('container-ammo','canopy-kit'),('tower-ammo','relay-kit'))
  for i,name in enumerate(s.env.REGIONS,1):
   a,b=ids[i-1];self.report['fixtures'].append(dict(region=i,reserveBefore=96,reserveAfter=96+(12 if i==1 else 18),repairBefore=2,repairAfter=2,selectedId=f'region-{i}/optional/{a}',blockedId=f'region-{i}/optional/{b}',otherRejected=True,selectedOfferHidden=True,otherSealed=True,selectedBoxStillPresent=True))
   for view in s.VIEWS:
    file=name+'-'+view+'.png';(self.folder/file).write_bytes(b'fixture');self.report['images'].append(dict(region=i,view=view,file='JourneyEvidence/supplies/'+file,cameraPosition=dict(x=0,y=1,z=0),lookAt=dict(x=0,y=1,z=1)))
  self.save()
 def save(self):(self.folder/'capture-report.json').write_text(json.dumps(self.report))
 def inspect(self):
  self.save()
  with patch.object(s.env,'inspect_png'):return s.inspect_report(self.root)
 def test_valid_fixture(self):self.assertEqual(len(self.inspect()['images']),9)
 def test_missing_image(self):self.report['images'].pop();self.assertRaises(ValueError,self.inspect)
 def test_duplicate_view(self):self.report['images'][1]=self.report['images'][0];self.assertRaises(ValueError,self.inspect)
 def test_traversal(self):self.report['images'][0]['file']='../private.png';self.assertRaises(ValueError,self.inspect)
 def test_scene_mutation(self):self.report['savedScenes'][0]['afterSha256']='0'*64;self.assertRaises(ValueError,self.inspect)
 def test_failed_group_rejection(self):self.report['fixtures'][2]['otherRejected']=False;self.assertRaises(ValueError,self.inspect)
 def test_wrong_reward(self):self.report['fixtures'][0]['reserveAfter']=999;self.assertRaises(ValueError,self.inspect)
 def test_unreleased_buffer(self):self.report['captureBuffersReleased']=False;self.assertRaises(ValueError,self.inspect)
 def test_null_graphics(self):self.report['graphicsDeviceType']='Null';self.assertRaises(ValueError,self.inspect)
 def test_extra_file(self):(self.folder/'raw-log.txt').write_text('never export');self.assertRaises(ValueError,self.inspect)
 def test_extra_report_field(self):self.report['rawException']='never export';self.assertRaises(ValueError,self.inspect)
 def test_nonfinite_camera(self):self.report['images'][0]['lookAt']['x']=float('nan');self.assertRaises(ValueError,self.inspect)
 def test_symlink_report(self):
  self.save();p=self.folder/'capture-report.json';p.rename(self.root/'original.json');p.symlink_to(self.root/'original.json')
  with self.assertRaises(ValueError):s.inspect_report(self.root)
 def test_black_real_png_rejected(self):
  p=self.root/'black.png';Image.new('RGB',(1440,900)).save(p)
  with self.assertRaises(ValueError):s.env.inspect_png(p)
 def test_native_test_identity(self):
  p=self.root/'native';p.mkdir();(p/'results.xml').write_text('<test-run result="Passed"><test-case fullname="wrong" result="Passed"/></test-run>')
  with self.assertRaises(ValueError):s.native(p)
  (p/'results.xml').write_text('<test-run result="Passed"><test-case fullname="'+s.TEST+'" result="Passed"/></test-run>');self.assertEqual(len(s.native(p)),64)
if __name__=='__main__':unittest.main()
