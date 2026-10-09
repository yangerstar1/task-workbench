"""Offline negative fixtures only; generated fixture pixels are never native evidence."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
import environment_terrain_probe_evidence as p

TASK=Path(__file__).resolve().parents[1]

def valid():
 mats=[]
 for name in ['Surface-Sand','Surface-Dune']:
  mats.append(dict(name=name,shader='Universal Render Pipeline/Lit',baseMapAsset=p.ART+'sand_03_diff_1k.jpg',normalMapAsset=p.ART+'sand_03_nor_gl_1k.jpg',normalScale=.035,smoothness=.04,metallic=0,baseScale={'x':1,'y':1},baseOffset={'x':0,'y':0},baseColor={'r':1.75,'g':1.52,'b':1.16,'a':1}))
 images=[]
 for variant in p.VARIANTS:
  for view,(fov,at,look) in p.CAMERAS.items():
   images.append(dict(file=f'Scrapyard-{view}-{variant}.png',view=view,variant=variant,sceneHash='a'*32,width=1440,height=900,fieldOfView=fov,minimum=.1,maximum=.8,normalEnabled=not variant.endswith('normal-off'),flatDiffuse=variant.startswith('diffuse-flat'),cameraPosition=at.copy(),cameraTarget=look.copy()))
 return dict(status=p.STATUS,graphicsDeviceType='OpenGLCore',graphicsDeviceName='llvmpipe (LLVM fixture)',savedSceneAndMaterialBytesPreserved=True,captureBuffersReleased=True,terrainRenderers=3,flatDiffuseSrgbBytes=[108,96,79],originalMaterials=mats,images=images)

class ReportTests(unittest.TestCase):
 def test_valid_report(self):self.assertEqual(p.validate_report(valid())['status'],p.STATUS)
 def test_exact_eight_set(self):self.assertEqual(len(p.IMAGES),8)
 def test_each_normal_off_state_disables_normal(self):
  d=valid()
  for r in d['images']:self.assertEqual(r['normalEnabled'],'normal-off' not in r['variant'])
 def test_explicit_diagnostic_not_acceptance(self):self.assertIn('NOT_ART_ACCEPTANCE',p.STATUS)

def add_mutation(name,mutate):
 def test(self):
  value=valid();mutate(value)
  with self.assertRaises((ValueError,TypeError,KeyError)):p.validate_report(value)
 setattr(ReportTests,'test_reject_'+name,test)

for name,func in {
 'extra_report_field':lambda d:d.update(secret='not-exported'),
 'wrong_scope':lambda d:d.update(status='ACCEPTED'),
 'fake_device':lambda d:d.update(graphicsDeviceType='Null'),
 'wrong_gpu':lambda d:d.update(graphicsDeviceName='fake'),
 'lost_material_preservation':lambda d:d.update(savedSceneAndMaterialBytesPreserved=False),
 'lost_buffers':lambda d:d.update(captureBuffersReleased=False),
 'renderer_count':lambda d:d.update(terrainRenderers=4),
 'bool_renderer_count':lambda d:d.update(terrainRenderers=True),
 'wrong_mean':lambda d:d.update(flatDiffuseSrgbBytes=[109,96,79]),
 'float_mean':lambda d:d.update(flatDiffuseSrgbBytes=[108.,96,79]),
 'extra_material':lambda d:d['originalMaterials'].append(d['originalMaterials'][0]),
 'duplicate_material':lambda d:d['originalMaterials'][1].update(name='Surface-Sand'),
 'wrong_shader':lambda d:d['originalMaterials'][0].update(shader='Unlit/Color'),
 'wrong_diffuse':lambda d:d['originalMaterials'][0].update(baseMapAsset='Assets/unverified.jpg'),
 'wrong_normal':lambda d:d['originalMaterials'][0].update(normalMapAsset='Assets/unverified.jpg'),
 'normal_strength':lambda d:d['originalMaterials'][0].update(normalScale=1),
 'smoothness':lambda d:d['originalMaterials'][0].update(smoothness=.5),
 'metallic':lambda d:d['originalMaterials'][0].update(metallic=1),
 'texture_scale':lambda d:d['originalMaterials'][0]['baseScale'].update(x=2),
 'texture_offset':lambda d:d['originalMaterials'][0]['baseOffset'].update(y=1),
 'base_tint':lambda d:d['originalMaterials'][0]['baseColor'].update(r=1),
 'material_extra':lambda d:d['originalMaterials'][0].update(arbitrary='no'),
 'missing_image':lambda d:d['images'].pop(),
 'extra_image':lambda d:d['images'].append(d['images'][0]),
 'duplicate_image':lambda d:d['images'].__setitem__(1,copy.deepcopy(d['images'][0])),
 'unknown_variant':lambda d:d['images'][0].update(variant='arbitrary'),
 'unknown_view':lambda d:d['images'][0].update(view='cabin'),
 'file_traversal':lambda d:d['images'][0].update(file='../other.png'),
 'normal_state':lambda d:d['images'][0].update(normalEnabled=False),
 'flat_state':lambda d:d['images'][0].update(flatDiffuse=True),
 'normal_bool_type':lambda d:d['images'][0].update(normalEnabled=1),
 'wrong_width':lambda d:d['images'][0].update(width=1280),
 'wrong_fov':lambda d:d['images'][0].update(fieldOfView=55),
 'wrong_position':lambda d:d['images'][0]['cameraPosition'].update(y=40),
 'wrong_target':lambda d:d['images'][0]['cameraTarget'].update(z=29),
 'nan_fov':lambda d:d['images'][0].update(fieldOfView=float('nan')),
 'nan_pixel':lambda d:d['images'][0].update(minimum=float('nan')),
 'blank_pixel_range':lambda d:d['images'][0].update(minimum=.8),
 'different_scene_hash':lambda d:d['images'][0].update(sceneHash='b'*32),
 'wrong_scene_hash':lambda d:d['images'][0].update(sceneHash='none'),
 'record_extra':lambda d:d['images'][0].update(command='no'),
}.items():add_mutation(name,func)

class CaptureTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.directory=self.root/p.CAPTURE;self.directory.mkdir(parents=True)
  self.im=Image.new('RGB',(1440,900),(35,50,70));ImageDraw.Draw(self.im).rectangle((200,100,1100,700),fill=(185,160,110))
  for name in p.IMAGES:self.im.save(self.directory/name)
  (self.directory/'probe-report.json').write_text(json.dumps(valid()))
  (self.root/'JourneyEvidence/candidate-layout.json').write_text('{"passed":true}')
  self.clearance=patch.object(p.legacy,'inspect_clearance',return_value=[{'region':1,'passed':True},{'region':2,'passed':True},{'region':3,'passed':True}]);self.clearance.start()
 def tearDown(self):self.clearance.stop();self.temp.cleanup()
 def test_valid_capture(self):self.assertEqual(len(p.inspect_capture(self.root)[0]['images']),8)
 def test_missing_png(self):
  (self.directory/next(iter(p.IMAGES))).unlink()
  with self.assertRaises(ValueError):p.inspect_capture(self.root)
 def test_extra_capture_file(self):
  (self.directory/'raw.log').write_text('no')
  with self.assertRaises(ValueError):p.inspect_capture(self.root)
 def test_bad_png(self):
  (self.directory/next(iter(p.IMAGES))).write_bytes(b'not png')
  with self.assertRaises(Exception):p.inspect_capture(self.root)
 def test_wrong_png_dimensions(self):
  Image.new('RGB',(10,10)).save(self.directory/next(iter(p.IMAGES)))
  with self.assertRaises(ValueError):p.inspect_capture(self.root)
 def test_blank_png(self):
  Image.new('RGB',(1440,900),(0,0,0)).save(self.directory/next(iter(p.IMAGES)))
  with self.assertRaises(ValueError):p.inspect_capture(self.root)
 def test_layout_failed(self):
  (self.root/'JourneyEvidence/candidate-layout.json').write_text('{"passed":false}')
  with self.assertRaises(ValueError):p.inspect_capture(self.root)
 def test_failed_clearance(self):
  self.clearance.stop()
  with self.assertRaises(ValueError):p.inspect_capture(self.root)
  self.clearance.start()

class PackageTests(CaptureTests):
 def test_package_outputs_only_eight_png_and_receipt_hashes(self):
  snapshot=self.root/'before.json';snapshot.write_text('{"tracked":"abc"}');out=self.root/'sanitized'
  identity=dict(repository='yangerstar1/task-workbench',commit='b'*40,runId='1',runAttempt='1',editorVersion='6000.3.19f1',sourceStateSha256='c'*64)
  with patch.object(p,'OUT',out),patch.object(p.source,'TASK',self.root),patch.object(p.source,'PROJECT',self.root),patch.object(p.legacy,'SNAPSHOT',snapshot),patch.object(p.legacy,'tracked_snapshot',return_value={'tracked':'abc'}),patch.object(p,'inspect_native',return_value='d'*64),patch.object(p.source,'identity',return_value=identity):
   p.package()
  self.assertEqual({x.name for x in out.iterdir()},p.IMAGES|{'receipt.json','SHA256SUMS.json'})
  receipt=json.loads((out/'receipt.json').read_text());self.assertEqual(receipt['scope'],p.STATUS);self.assertEqual(receipt['visualAcceptance'],'NOT_ACCEPTED')
  hashes=json.loads((out/'SHA256SUMS.json').read_text());self.assertEqual(len(hashes),9)
  for row in hashes:self.assertEqual(hashlib.sha256((out/row['path']).read_bytes()).hexdigest(),row['sha256'])
 def test_changed_tracked_source_stops_before_output(self):
  snapshot=self.root/'before.json';snapshot.write_text('{"tracked":"abc"}');out=self.root/'sanitized'
  with patch.object(p,'OUT',out),patch.object(p.legacy,'SNAPSHOT',snapshot),patch.object(p.legacy,'tracked_snapshot',return_value={'tracked':'changed'}):
   with self.assertRaises(ValueError):p.package()
  self.assertFalse(out.exists())
 def test_stale_output_rejected(self):
  out=self.root/'sanitized';out.mkdir()
  with patch.object(p,'OUT',out):
   with self.assertRaises(ValueError):p.package()

class NativeTests(unittest.TestCase):
 def check(self,text,passed=False):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'results.xml').write_text(text)
   if passed:self.assertEqual(len(p.inspect_native(root)),64)
   else:
    with self.assertRaises(ValueError):p.inspect_native(root)
 def xml(self,name=p.RENDER_TEST,result='Passed',count=1):return '<test-run result="'+result+'">'+('<test-case fullname="'+name+'" result="'+result+'"/>')*count+'</test-run>'
 def test_native_exact_case(self):self.check(self.xml(),True)
 def test_native_old_twenty_case(self):self.check(self.xml(name=p.legacy.RENDER_TEST))
 def test_native_failed(self):self.check(self.xml(result='Failed'))
 def test_native_extra_case(self):self.check(self.xml(count=2))
 def test_native_no_case(self):self.check(self.xml(count=0))

class ImplementationTests(unittest.TestCase):
 def test_production_camera_and_gate_files_are_byte_exact_r3(self):
  expected={'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.EnvironmentPolishCapture.cs':'fa6cbe1f1252801ec1b0f62b864104d715f781dc01567b50ec82c9a0b30f097e','unity/Assets/DesertRV/Editor/JourneySceneAuthoring.EnvironmentPolish.cs':'b829eda4869721b7956cb279b53e0a6b7e1194ef91880c80e2d712110a8366d9'}
  for path,digest in expected.items():self.assertEqual(hashlib.sha256((TASK/path).read_bytes()).hexdigest(),digest)
 def test_probe_source_is_fixed_two_by_four_and_in_memory_only(self):
  s=(TASK/'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.TerrainProbe.cs').read_text()
  self.assertIn('new[]{"original","normal-off","diffuse-flat","diffuse-flat-normal-off"}',s)
  self.assertIn('new[]{"overview","ground"}',s);self.assertIn('records.Count!=8',s)
  self.assertIn('m.DisableKeyword("_NORMALMAP");m.SetTexture("_BumpMap",null);m.SetFloat("_BumpScale",0)',s)
  self.assertIn('m.IsKeywordEnabled("_NORMALMAP")!=normal',s);self.assertIn('m.GetTexture("_BaseMap")!=(flat?meanDiffuse:original.GetTexture("_BaseMap"))',s)
  self.assertIn('new Material(original)',s);self.assertIn('new Color32(108,96,79,255)',s)
  for forbidden in ['SaveAssets','CreateAsset','SetAtmosphere(','light.intensity','RenderSettings.','SetTextureScale(']:self.assertNotIn(forbidden,s)
 def test_independent_single_case(self):
  root=TASK/'unity/Assets/DesertRV/Tests/EditorTerrainProbe';text=(root/'JourneyTerrainProbeTests.cs').read_text()
  self.assertEqual(text.count('[Test,'),1);self.assertIn('Timeout(600000)',text)
  asm=json.loads((root/'DesertRV.EditorTerrainProbeTests.asmdef').read_text());self.assertEqual(asm['name'],'DesertRV.EditorTerrainProbeTests');self.assertEqual(asm['includePlatforms'],['Editor'])
 def test_flat_rgb_constant_matches_linear_source_mean(self):
  with Image.open(TASK/'unity/Assets/DesertRV/Art/EnvironmentV4/sand_03_diff_1k.jpg') as image:
   hist=image.convert('RGB').histogram();n=image.width*image.height
  result=[]
  for channel in range(3):
   mean=sum(hist[channel*256+i]*(i/255/12.92 if i/255<=.04045 else ((i/255+.055)/1.055)**2.4) for i in range(256))/n
   gamma=12.92*mean if mean<=.0031308 else 1.055*mean**(1/2.4)-.055
   result.append(round(gamma*255))
  self.assertEqual(result,[108,96,79])
 def test_no_external_assets_or_licensing_change(self):
  provenance=json.loads((TASK/'unity/Assets/DesertRV/Art/EnvironmentV4/asset-provenance.json').read_text())
  self.assertEqual(len(provenance['assets']),29)
  for row in provenance['assets']:self.assertEqual(hashlib.sha256((TASK/row['path']).read_bytes()).hexdigest(),row['sha256'])

if __name__=='__main__':unittest.main()
