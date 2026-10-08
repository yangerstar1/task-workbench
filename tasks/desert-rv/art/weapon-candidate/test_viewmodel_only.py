import ast,json,pathlib,unittest
ROOT=pathlib.Path(__file__).parent
class Scope(unittest.TestCase):
 def test_scripts_parse(self):
  for name in ['viewmodel_only.py','prepare_viewmodel_source.py']:ast.parse((ROOT/name).read_text())
 def test_no_asset_generation_export_or_blend_save(self):
  s=(ROOT/'viewmodel_only.py').read_text()
  for text in ['bpy.ops.mesh','export_scene','save_as_mainfile','frames_Reload','frames_Idle','frames_Fire']:self.assertNotIn(text,s)
  self.assertIn('open_mainfile',s);self.assertIn('before==after',s)
 def test_exact_baseline_pinned(self):
  d=json.loads((ROOT/'viewmodel-baseline.json').read_text());self.assertEqual(d['artifact_id'],11579827076);self.assertEqual(d['run_id'],37841477090);self.assertFalse(d['new_full_run']);self.assertEqual(len(d['zip_sha256']),64)
 def test_rig_offset_not_camera_projection_change(self):
  s=(ROOT/'viewmodel_only.py').read_text();self.assertIn('camera_right*.015',s);self.assertFalse(any(ast.unparse(t)=='camera.data.shift_x' for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Assign) for t in n.targets));self.assertIn('camera_projection_unchanged',s)
 def test_explicit_not_full_or_unity_approval(self):
  s=(ROOT/'viewmodel_only.py').read_text();self.assertIn("'new_full_run':False",s);self.assertIn("'unity_muzzle_alignment_verified':False",s);self.assertIn("'source_original_result':'failure'",s)
 def test_owner_only_no_billing_runners(self):
  s=(ROOT.parents[3]/'.github/workflows/desert-rv-weapon-viewmodel.yml').read_text();self.assertIn('github.actor == github.repository_owner',s);self.assertIn('runs-on: ubuntu-24.04',s);self.assertNotIn('workflow_run:',s)
if __name__=='__main__':unittest.main()
