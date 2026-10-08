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
        self.assertIn('death_solver.solve(u)',source)
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
    def test_death_only_change_boundary(self):
        import hashlib
        boundary=json.loads((H/'death-change-boundary.json').read_text())
        for info in boundary['unchanged_regions'].values():
            text=(H/info['file']).read_text().split(info['start_marker'],1)[1].split(info['end_marker'],1)[0]
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),info['sha256'])
        self.assertEqual(hashlib.sha256((H/'parameters.json').read_bytes()).hexdigest(),boundary['parameters_sha256'])
    def test_diagnostic_scope_cannot_look_like_full_review(self):
        source=(H/'generate.py').read_text();animate=(H/'animate.py').read_text();workflow=(H.parents[3]/'.github/workflows/desert-rv-pouncer-art.yml').read_text()
        self.assertIn('DEATH_DIAGNOSTIC_NOT_FULL',source);self.assertIn("'full_motion_visual_review':'NOT_RUN'",source)
        self.assertIn("render_clips={'Death':clips['Death']}",animate)
        self.assertIn('default: death-diagnostic',workflow);self.assertIn("if: inputs.scope == 'full'",workflow)
        self.assertIn('death-near-',animate);self.assertIn('death_diagnostic_technical_pass',(H/'validate_asset.py').read_text())
    def test_corpse_relaxes_paws_instead_of_standing(self):
        pose=json.loads((H/'death-rest-pose.json').read_text())
        for key in ('fore.L','fore.R','hind.L','hind.R'):
            self.assertGreater(pose[key]['paw_roll'],1.2)
        for prefix in ('fore','hind'):
            self.assertGreater(pose[prefix+'.R']['ankle'][2]-pose[prefix+'.L']['ankle'][2],.10)
        self.assertIn("self.relax=t*t*(3-2*t)",(H/'death_contact.py').read_text())
        self.assertIn('death_paw_up_dot_world_up',(H/'validate_asset.py').read_text())
    def test_genuine_two_patch_support_excludes_head_and_hip_root(self):
        from death_support import support_region
        self.assertEqual(support_region(.25,-.3,.65,.8),'shoulder')
        self.assertEqual(support_region(.20,.5,.6,.75),'pelvis')
        self.assertIsNone(support_region(.2,-.95,.65,1.0))
        self.assertIsNone(support_region(.3,.6,.6,.1115))
        self.assertIsNone(support_region(.3,.5,.06,.9))
        text=(H/'validate_asset.py').read_text()
        self.assertIn('death_support_patches',text);self.assertIn("patch['q05_z']",text)
    def test_support_overlay_is_separate_post_export_evidence(self):
        source=(H/'animate.py').read_text()
        self.assertGreater(source.index('render_support_overlays(scene'),source.index('bpy.ops.export_scene.fbx'))
        overlay=(H/'support_overlay.py').read_text()
        self.assertIn('DIAGNOSTIC_TRANSPARENT_',overlay);self.assertIn('for obj,materials in saved:',overlay)
        self.assertIn('death-support-overlay-',(H/'package_review.py').read_text())
    def test_head_correction_uses_measured_axis_search(self):
        text=(H/'death_contact.py').read_text()
        self.assertIn('def relax_head(',text);self.assertIn('best_z=self.head_minimum()',text)
        self.assertNotIn('neck.rotation_euler.z=max(-.12',text)
        self.assertIn('self.pole_baselines',text);self.assertIn("('angle',0,sign)",text)
        self.assertIn('self.initial_roll-.28',text)
    def test_actual_depth_summary_is_mandatory(self):
        text=(H/'validate_asset.py').read_text()
        self.assertIn('death-diagnostic-summary.json',text);self.assertIn('maximum_penetration_m',text)
        self.assertIn('worst_evaluated_vertex',text);self.assertIn('worst_seconds',text)
if __name__=='__main__':unittest.main()
