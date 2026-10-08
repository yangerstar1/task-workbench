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
        p=json.loads((H/'parameters.json').read_text()); self.assertEqual(p['fps'],100)
        self.assertEqual(set(p['clips']),{'Idle','Walk','Windup','Attack','Recover','Hit','Death'})
        self.assertAlmostEqual(p['gait']['cycle_seconds']*p['gait']['stance_fraction']*2.7,p['gait']['stance_travel_m'])
        self.assertFalse(p['integration']['root_motion'])
    def test_substantive_r2_rebuild(self):
        text=(H/'generate.py').read_text(); self.assertIn('def loft(',text); self.assertNotIn("ellipsoid('Thorax'",text)
        self.assertIn("bpy.ops.object.bake(type='EMIT'",text); self.assertIn("constraints.new('IK')",text)
        text=(H/'validate_asset.py').read_text(); self.assertIn('skin_topology',text); self.assertIn('stance_max_speed_error_mps',text); self.assertIn('<-.004',text)
    def test_transport_frames_are_continuous_and_orthogonal(self):
        import math
        from geometry_frames import transport_frames,dot,cross
        chains=[[(.17,-.38,.73),(.27,-.38,.69),(.29,-.365,.63),(.315,-.32,.55),(.33,-.275,.45),(.335,-.24,.36),(.34,-.34,.265),(.345,-.48,.12),(.345,-.60,.075)],[(.15,.65,.66),(.245,.61,.61),(.275,.55,.50),(.295,.43,.38),(.30,.38,.34),(.307,.52,.26),(.315,.69,.18),(.315,.62,.11),(.315,.55,.065)]]
        for centers in chains:
            frames=transport_frames(centers)
            for right,up,tangent in frames:
                for vector in (right,up,tangent):self.assertAlmostEqual(dot(vector,vector),1)
                self.assertAlmostEqual(dot(right,up),0);self.assertAlmostEqual(dot(right,tangent),0)
                self.assertAlmostEqual(dot(cross(right,tangent),up),1)
            for a,b in zip(frames,frames[1:]):self.assertGreater(dot(a[1],b[1]),math.cos(math.radians(65)))
    def test_topology_does_not_confuse_boundary_with_genus(self):
        from types import SimpleNamespace as NS
        from topology_report import inspect_mesh
        def mesh(faces):
            edges={tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1])}
            return NS(vertices=[NS(co=(0,0,0)) for _ in range(4)],edges=[NS(vertices=e) for e in edges],polygons=[NS(vertices=f,index=i) for i,f in enumerate(faces)])
        tetra=[(0,1,2),(0,3,1),(1,3,2),(2,3,0)]
        closed=inspect_mesh(mesh(tetra)); opened=inspect_mesh(mesh(tetra[:-1]))
        self.assertEqual(closed['orientable_genus_if_closed'],0);self.assertEqual(closed['boundary_edge_count'],0)
        self.assertEqual(opened['boundary_edge_count'],3);self.assertIsNone(opened['orientable_genus_if_closed'])
    def test_death_requires_torso_and_relaxed_legs(self):
        source=(H/'animate.py').read_text(); validate=(H/'validate_asset.py').read_text()
        self.assertIn('Solve contact against the side of the actual torso',source)
        self.assertIn('death_torso_contact_z',validate);self.assertIn('death_relaxed_paw_heights',validate)
        self.assertIn("topology['nonmanifold_vertex_count']",validate)
    def test_transition_probes_precede_asset_export(self):
        source=(H/'animate.py').read_text();validate=(H/'validate_asset.py').read_text()
        self.assertLess(source.index("transition-clearance.json"),source.index('bpy.ops.export_scene.gltf'))
        self.assertIn('verified_crossfade_min_z_after_lift',source)
        self.assertIn('to_quaternion().slerp',validate)
        self.assertIn('current_runtime',validate);self.assertIn('proposed_fixed_time',validate)
    def test_export_timing_is_zero_based_and_read_back(self):
        source=(H/'animate.py').read_text();validate=(H/'validate_asset.py').read_text()
        self.assertIn('export_anim_slide_to_zero=True',source);self.assertIn('key.co.x-=1',source)
        self.assertIn("strip.action_frame_start=0",source)
        self.assertIn('inspect_glb,inspect_fbx',validate);self.assertIn('serialized_animation_times',validate)
if __name__=='__main__':unittest.main()
