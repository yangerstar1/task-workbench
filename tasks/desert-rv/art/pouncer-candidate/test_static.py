"""Static source checks only: no Blender execution or image-quality assertion."""
import ast
import json
import unittest
from pathlib import Path
H=Path(__file__).resolve().parent
class CandidateContract(unittest.TestCase):
    def test_python_parses(self):
        for p in H.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    def test_pipeline_is_split(self):
        text=(H.parents[3]/'.github/workflows/desert-rv-pouncer-art.yml').read_text()
        self.assertIn('--phase static',text); self.assertIn('--phase motion',text)
        self.assertLess(text.index('Upload early static'),text.index('--phase motion'))
        self.assertIn("github.actor == github.repository_owner",text); self.assertIn('contents: read',text)
        self.assertNotRegex(text,r'(?m)^  (push|pull_request|schedule):')
    def test_motion_contract(self):
        p=json.loads((H/'parameters.json').read_text()); self.assertEqual(p['fps'],60)
        self.assertEqual(set(p['clips']),{'Idle','Walk','Windup','Attack','Recover','Hit','Death'})
        self.assertAlmostEqual(p['gait']['cycle_seconds']*p['gait']['stance_fraction']*2.7,p['gait']['stance_travel_m'])
        self.assertFalse(p['integration']['root_motion'])
    def test_substantive_r2_rebuild(self):
        text=(H/'generate.py').read_text(); self.assertIn('def loft(',text); self.assertNotIn("ellipsoid('Thorax'",text)
        self.assertIn("bpy.ops.object.bake(type='EMIT'",text); self.assertIn("constraints.new('IK')",text)
        text=(H/'validate_asset.py').read_text(); self.assertIn('skin_euler_characteristic',text); self.assertIn('stance_max_speed_error_mps',text); self.assertIn('<-.004',text)
if __name__=='__main__':unittest.main()
