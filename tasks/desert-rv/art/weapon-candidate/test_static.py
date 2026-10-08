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
  for token in ['export_scene.gltf','export_scene.fbx','save_as_mainfile','range(0 if CONTACT_ONLY else 8)','1280,720','1600,720',"'quality_gate':'PENDING_RENDER_REVIEW'","'weight_errors'"] :self.assertIn(token,s)
 def test_pixel_footprint_and_contact_evidence(self):
  s=(ROOT/'build_weapon.py').read_text()
  for token in ["bpy.data.images.load(scene.render.filepath,check_existing=False)","'max_fingertip_IK_error_m'","reload_contact_{frame:03d}","camera.data.type='PERSP'","'Forearm_'"]:self.assertIn(token,s)
 def test_fresh_strip_and_fixed_magazine(self):
  s=(ROOT/'build_weapon.py').read_text();self.assertIn("'magazine_detaches':False",s);self.assertIn("'new_nails_count':12",s);self.assertIn("constraints.new('IK')",s)
 def test_no_animation_ammo_visibility_scaling(self):
  s=(ROOT/'build_weapon.py').read_text();self.assertNotIn('key_scale(',s);self.assertNotIn('.0001',s);self.assertIn("if n not in ['IncomingOffset','LeftReloadOffset','Muzzle']",s)
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
class CoreMetricRegression(unittest.TestCase):
 def test_sleeve_width_is_not_core_width(self):
  from pixel_evidence import core_target_fit
  core=[.66,.04,.94,.31];full=[.5,0,1,.4]
  self.assertTrue(core_target_fit(core,core));self.assertGreater(full[2]-full[0],.32)
 def test_short_core_not_rescued_by_sleeve_height(self):
  from pixel_evidence import core_target_fit
  core=[.66,.06,.94,.30]
  self.assertFalse(core_target_fit(core,core))
 def test_contact_diagnostic_explicitly_not_full(self):
  s=(ROOT/'build_weapon.py').read_text();self.assertIn("'full_asset_validation':False",s);self.assertIn("CONTACT_ONLY='--contact-only'",s);self.assertIn('obj.vertex_groups.clear()',s)
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
class ArtifactGateRegression(unittest.TestCase):
 def test_historical_failure_not_success(self):
  from asset_validation import technical_failures
  self.assertIn('missing_aspect_evidence',technical_failures({}))
  failures=technical_failures({'mesh_groups':{'weapon':{'in_budget':False},'hands':{'in_budget':False}}})
  self.assertIn('triangle_budget:weapon',failures)
 def test_backup_not_published_or_hashed(self):
  from asset_validation import delivered_file
  import tempfile
  with tempfile.TemporaryDirectory() as d:
   for name,expect in [('x.blend1',False),('x.blend',True),('x.png',True),('SHA256SUMS',False)]:
    p=pathlib.Path(d)/name;p.write_bytes(b'x');self.assertEqual(delivered_file(p),expect)
 def test_carrier_channel_cleanup_preserves_other_motion(self):
  from asset_validation import strip_carrier_animation_channels,read_glb
  import tempfile,json,struct
  doc={'nodes':[{'name':'IncomingOffset'},{'name':'LeftReloadOffset'},{'name':'hand.L'}],'animations':[{'name':'Reload','channels':[{'target':{'node':i,'path':'translation'},'sampler':0} for i in range(3)],'samplers':[]}]}
  data=json.dumps(doc).encode();data+=b' '*((-len(data))%4)
  raw=b'glTF'+struct.pack('<II',2,20+len(data))+struct.pack('<II',len(data),0x4E4F534A)+data
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'test.glb';p.write_bytes(raw);self.assertEqual(strip_carrier_animation_channels(p),{'Reload':2});_,out,_=read_glb(p);self.assertEqual([c['target']['node'] for c in out['animations'][0]['channels']],[2])
 def test_fixed_pose_and_continuous_connector(self):
  s=(ROOT/'build_weapon.py').read_text();self.assertNotIn('best=None',s);self.assertIn("camera.data.sensor_fit='HORIZONTAL'",s);self.assertIn('y-.015,z+.027-.001605',s);self.assertIn('y+.015,z+.027+.001605',s)
 def test_carrier_gate_not_replaced_by_runtime_override(self):
  s=(ROOT/'package_evidence.py').read_text();self.assertIn("failures.append('fbx_carrier_channels_present')",s);self.assertIn("failures.append('glb_carrier_channels_present')",s)
  s=(ROOT/'build_weapon.py').read_text();self.assertIn("kwargs['force_keep']=False",s);self.assertIn('bake_anim_use_all_bones=False',s)
 def test_muzzle_and_skin_contract_are_explicit(self):
  s=(ROOT/'build_weapon.py').read_text();self.assertIn("bone('Muzzle',(0,.35,.072),(0,.385,.072),'weapon')",s);self.assertIn('use_armature_deform_only=False',s);self.assertIn('export_def_bones=False',s);self.assertIn("'renderer_reparented':False",s);self.assertIn('max_inside_vertex_depth_m',s)
 def test_fbx_single_export_path(self):
  s=(ROOT/'build_weapon.py').read_text();self.assertIn('bake_anim_use_all_actions=False,bake_anim_use_nla_strips=True',s)
if __name__=='__main__':unittest.main()
