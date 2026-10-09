"""Offline safeguards only. These tests do NOT certify Unity compilation, native collision, or beauty."""
import hashlib,json,math,re,unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'unity/Assets/DesertRV/Art/EnvironmentV4'
CODE=(ROOT/'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.EnvironmentPolish.cs').read_text()
CAPTURE=(ROOT/'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.EnvironmentPolishCapture.cs').read_text()
CONTRACT=json.loads((Path(__file__).parent/'generated-contract.json').read_text())
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def normal(a,b,c):return cross(sub(b,a),sub(c,a))
class CandidateTests(unittest.TestCase):
 def test_provenance_bytes_and_licenses(self):
  data=json.loads((ART/'asset-provenance.json').read_text())
  self.assertEqual(len(data['assets']),29)
  for row in data['assets']:
   p=ROOT/row['path'];self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),row['sha256']);self.assertEqual(p.stat().st_size,row['bytes']);self.assertEqual(row['license'],'CC0-1.0')
   self.assertTrue(row['source_url'].startswith(('https://polyhaven.com/a/','https://kenney.nl/assets/factory-kit')))
 def test_texture_budget_dimensions_and_importers(self):
  files=list(ART.rglob('*.jpg'))+list(ART.rglob('*.png'))
  self.assertEqual(len(files),22)
  for p in files:
   with Image.open(p) as image:w,h=image.size
   self.assertLessEqual(max(w,h),1024)
   meta=p.with_suffix(p.suffix+'.meta').read_text();self.assertIn('enableMipMap: 1',meta);self.assertIn('aniso: 4',meta)
   if '_nor_gl_' in p.name:self.assertIn('textureType: 1',meta);self.assertIn('sRGBTexture: 0',meta);self.assertIn('flipGreenChannel: 0',meta)
   elif '_metallic_smoothness_' in p.name:self.assertIn('sRGBTexture: 0',meta);self.assertIn('alphaUsage: 1',meta)
   else:self.assertIn('sRGBTexture: 1',meta)
  self.assertLess(sum(p.stat().st_size for p in files),14*1024*1024)
 def test_no_unverified_model_or_texture_load(self):
  models=re.findall(r'PlaceFactory\(b,"([a-z-]+)"',CODE)
  self.assertEqual(set(models),{'pipe-large-valve','machine-bed','hopper-square','crane-magnet','catwalk-stairs','catwalk-straight','pipe-large-bend'})
  for name in models:self.assertTrue((ART/'Factory'/f'{name}.fbx').is_file())
  for tile in set(re.findall(r'tile = "([a-z_0-9]+)"',CODE)):
   for suffix in ('diff_1k.jpg','nor_gl_1k.jpg','metallic_smoothness_1k.png'):self.assertTrue((ART/f'{tile}_{suffix}').is_file())
 def test_finite_generated_contract(self):
  self.assertEqual(len(CONTRACT['files']),97);self.assertEqual(len(CONTRACT['metadata_files']),98)
  self.assertEqual(len(set(CONTRACT['files'])),97)
  self.assertTrue(all(p.endswith(('.mat','.asset')) and '*' not in p and '..' not in p for p in CONTRACT['files']))
  for region,keys in CONTRACT['region_mesh_keys'].items():
   block=re.search(r'case '+region+r': return new\[\]\{([^}]+)\};',CODE).group(1)
   self.assertEqual(re.findall('"([^"]+)"',block),keys)
  self.assertIn('meshes.Keys.SequenceEqual(PolishExpectedMeshNames(region.region))',CODE)
 def test_physical_texture_scale(self):
  self.assertIn('material == "TrackSand" ? 15',CODE)
  self.assertIn('material == "Sand" || material == "Plaster" || material == "Sheet" ? 2',CODE)
  self.assertIn('material == "Asphalt" || material == "Concrete" ? 3 : 1',CODE)
  self.assertIn('Project(p,normal.normalized)/TextureMetres(material)',CODE)
  self.assertIn('p.SourceMesh("StationWallLeft", "Plaster", r)',CODE)
  # Photographed tire tracks must not texture the open desert itself.
  self.assertIn('case "Sand": tile = "sand_03"',CODE);self.assertIn('case "TrackSand": tile = "aerial_sand"',CODE)
 def test_shared_material_budget_and_importer_safety(self):
  self.assertEqual(len(CONTRACT['material_names']),14)
  self.assertNotIn('SaveAndReimport',CODE);self.assertNotIn('AssetImporter.GetAtPath',CODE)
  self.assertIn('enableInstancing = true',CODE)
  self.assertIn('if(own.Length>80||triangles>90000||lights>3)',CODE)
 def test_road_and_region_contract_untouched(self):
  main=(ROOT/'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.cs').read_text()
  self.assertEqual(main.count('AuthorEnvironmentPolish(source,b,motor);'),1)
  self.assertIn('new Vector3(8.6f,3.8f,78)',main);self.assertIn('new Vector3(0,0,64)',main)
  self.assertNotIn('motor.vehicle.',CODE);self.assertNotIn('b.salvage =',CODE);self.assertNotIn('b.powerPoint =',CODE)
 def test_existing_camera_set_unchanged(self):
  main=(ROOT/'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.cs').read_text()
  self.assertIn('new[]{"overview","ground","landmark","cabin","motor-driving-editor","motor-walking-editor"}',main)
  self.assertIn('fieldOfView=66',CAPTURE);self.assertIn('forecourt-eye-height',CAPTURE);self.assertIn('garage-eye-height',CAPTURE)
  self.assertIn('savedSceneBytesPreserved=true',CAPTURE)
 def test_cylinder_winding_points_outward(self):
  self.assertIn('m.Quad(from+p,from+q,to+q,to+p)',CODE)
  angle=.25;p=(1,0,0);q=(math.cos(angle),0,-math.sin(angle));tq=(q[0],1,q[2])
  self.assertGreater(normal(p,q,tq)[0],0)
 def test_berm_winding_and_smooth_normals(self):
  self.assertIn('m.Quad(point(r,i+1),point(r+1,i+1),point(r+1,i),point(r,i))',CODE)
  self.assertIn('m.smoothNormals=true',CODE)
  self.assertGreater(normal((0,1,0),(math.cos(.2),.9,math.sin(.2)),(1,.9,0))[1],0)
 def test_ground_winding_points_upward(self):
  self.assertGreater(normal((-1,0,-1),(-1,0,1),(1,0,1))[1],0)
 def test_coarse_envelopes_do_not_invade_road(self):
  # Math preflight only; authoring still runs the real renderer/collider/supply checks in Unity.
  road_half=4.3
  self.assertGreater(39-13*1.12,road_half)
  self.assertGreater(9.55-.835,road_half)
  self.assertGreater(11-4.3,road_half)
  self.assertGreater(12-4.5,road_half)
 def test_all_new_source_assets_have_unique_meta_guids(self):
  guids=[]
  for p in ART.rglob('*'):
   if p.name.endswith('.meta'):continue
   meta=p.with_name(p.name+'.meta');self.assertTrue(meta.is_file(),str(p))
   guid=re.search(r'^guid: ([a-f0-9]{32})$',meta.read_text(),re.M).group(1);guids.append(guid)
  self.assertEqual(len(guids),len(set(guids)))
if __name__=='__main__':unittest.main()
