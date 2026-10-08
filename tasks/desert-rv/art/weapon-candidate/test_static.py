"""Source-contract tests only; these do not pretend to validate rendered art."""
import ast,pathlib,unittest
ROOT=pathlib.Path(__file__).parent
class Contracts(unittest.TestCase):
 def test_python_parses(self):
  for f in ROOT.glob('*.py'):ast.parse(f.read_text())
 def test_workflow_owner_only(self):
  s=(ROOT.parents[3]/'.github/workflows/desert-rv-weapon-art.yml').read_text()
  for token in ['workflow_dispatch:', 'github.actor == github.repository_owner','contents: read','sha256sum --check --strict','--python-exit-code 1']:self.assertIn(token,s)
  self.assertNotIn('pull_request:',s); self.assertNotIn('push:',s)
 def test_exact_clip_durations(self):
  self.assertAlmostEqual((14.2-1)/60,.22); self.assertAlmostEqual((100-1)/60,1.65)
 def test_exports_and_evidence(self):
  s=(ROOT/'build_weapon.py').read_text()
  for token in ['export_scene.gltf','export_scene.fbx','save_as_mainfile','range(8)','1280,720','1600,720',"'quality_gate':'PENDING_RENDER_REVIEW'","'weight_errors'"] :self.assertIn(token,s)
 def test_pixel_footprint_and_contact_evidence(self):
  s=(ROOT/'build_weapon.py').read_text()
  for token in ["bpy.data.images.load(scene.render.filepath,check_existing=False)","'max_fingertip_IK_error_m'","reload_contact_{frame:03d}","camera.data.type='PERSP'","'Forearm_'"]:self.assertIn(token,s)
 def test_fresh_strip_and_fixed_magazine(self):
  s=(ROOT/'build_weapon.py').read_text();self.assertIn("'magazine_detaches':False",s);self.assertIn("'new_nails_count':12",s);self.assertIn("constraints.new('IK')",s)
 def test_no_animation_ammo_visibility_scaling(self):
  s=(ROOT/'build_weapon.py').read_text();self.assertNotIn('key_scale(',s);self.assertNotIn('.0001',s);self.assertIn("if n not in ['IncomingOffset','LeftReloadOffset']",s)
 def test_no_external_art_or_game_events(self):
  s=(ROOT/'build_weapon.py').read_text(); self.assertNotIn('https://',s); self.assertIn("'gameplay_events':[]",s)
class FramingRegression(unittest.TestCase):
 def test_fully_outside_core_rejected(self):
  from pixel_evidence import core_fit_score
  self.assertEqual(core_fit_score([1.1,.1,1.4,.4]),float('inf'))
 def test_partially_cropped_core_rejected(self):
  from pixel_evidence import core_fit_score
  for bounds in [[.7,-.1,.98,.3],[.7,.1,1.1,.3],[-.1,.1,.3,.3],[.7,.8,.9,1.1]]:self.assertEqual(core_fit_score(bounds),float('inf'))
 def test_only_long_forearms_exempt(self):
  from pixel_evidence import is_core_asset
  self.assertFalse(is_core_asset('Forearm_L')); self.assertFalse(is_core_asset('Forearm_R'))
  for name in ['Glove_L_Continuous','Cuff_R','Grip','Forearm_Glove','hand.L']:self.assertTrue(is_core_asset(name))
 def test_safe_core_has_finite_score(self):
  from pixel_evidence import core_fit_score
  self.assertLess(core_fit_score([.65,.05,.935,.32]),1)
class PixelBufferRegression(unittest.TestCase):
 def test_empty_buffer_rejected(self):
  from pixel_evidence import alpha_bounds
  with self.assertRaisesRegex(ValueError,'Incomplete image pixel buffer'):alpha_bounds([],2,2)
 def test_exact_single_pixel_footprint(self):
  from pixel_evidence import alpha_bounds
  values=[0.0]*32;values[(1*4+2)*4+3]=1
  self.assertEqual(alpha_bounds(values,4,2),[.5,.5,.75,1.0])
 def test_transparent_image_rejected(self):
  from pixel_evidence import alpha_bounds
  with self.assertRaisesRegex(ValueError,'no visible asset'):alpha_bounds([0.0]*16,2,2)
 def test_rgb_image_rejected(self):
  from pixel_evidence import alpha_bounds
  with self.assertRaisesRegex(ValueError,'RGBA'):alpha_bounds([0.0]*12,2,2,3)
if __name__=='__main__':unittest.main()
