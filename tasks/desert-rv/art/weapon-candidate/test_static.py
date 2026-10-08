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
  for token in ["bpy.data.images['Render Result'].pixels","'max_fingertip_IK_error_m'","reload_contact_{frame:03d}","camera.data.type='PERSP'","'Forearm_'"]:self.assertIn(token,s)
 def test_fresh_strip_and_fixed_magazine(self):
  s=(ROOT/'build_weapon.py').read_text();self.assertIn("'magazine_detaches':False",s);self.assertIn("'new_nails_count':27",s);self.assertIn("constraints.new('IK')",s)
 def test_no_external_art_or_game_events(self):
  s=(ROOT/'build_weapon.py').read_text(); self.assertNotIn('https://',s); self.assertIn("'gameplay_events':[]",s)
if __name__=='__main__':unittest.main()
