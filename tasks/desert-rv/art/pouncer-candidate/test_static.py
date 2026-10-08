"""No Blender import/execution: audit reproducible candidate's source contract."""
import ast
import json
import re
import unittest
from pathlib import Path
H=Path(__file__).resolve().parent
class CandidateContract(unittest.TestCase):
    def test_all_python_parses(self):
        for p in H.glob('*.py'): ast.parse(p.read_text(),filename=str(p))
    def test_required_clips(self):
        p=json.loads((H/'parameters.json').read_text())
        self.assertEqual(set(p['clips']),{'Idle','Walk','Windup','Attack','Recover','Hit','Death'})
        self.assertFalse(p['integration']['root_motion'])
        self.assertLessEqual(p['clips']['Attack'],.8)
        self.assertEqual(p['blender'],'4.2.3')
    def test_no_external_model_inputs(self):
        tree=ast.parse((H/'generate.py').read_text())
        imports=[a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
        self.assertFalse(set(imports)&{'requests','urllib','subprocess'})
        text=(H/'generate.py').read_text()
        self.assertNotIn('bpy.ops.import_scene',text)
        self.assertIn("rem.mode = 'VOXEL'",text)
        self.assertIn("export_animation_mode='NLA_TRACKS'",text)
    def test_complete_motion_contract(self):
        text=(H/'generate.py').read_text()
        self.assertIn("bone('visual_body'",text)
        self.assertIn('1.48*q',text)
        validate=(H/'validate_asset.py').read_text()
        self.assertIn('synthetic_interrupt_recovery',validate)
        self.assertIn('death_final_hold_stable',validate)
        self.assertIn('clip_endpoint_floor_heights_m',validate)
        self.assertNotIn('Attack leaves entire skin above floor',validate)
    def test_manual_owner_only(self):
        workflow=H.parents[3]/'.github/workflows/desert-rv-pouncer-art.yml'
        text=workflow.read_text()
        self.assertIn('workflow_dispatch:',text)
        self.assertIn('if: github.actor == github.repository_owner',text)
        self.assertNotRegex(text,r'(?m)^  (push|pull_request|schedule):')
        self.assertIn('contents: read',text)
        self.assertIn('sha256sum --check',text)
        self.assertNotIn('self-hosted',text)
if __name__=='__main__': unittest.main()
