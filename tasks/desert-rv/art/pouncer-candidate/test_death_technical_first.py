"""Static contracts only; no Blender invocation or model generation."""
import ast,hashlib,json,re,unittest
from pathlib import Path
H=Path(__file__).resolve().parent
class TechnicalFirst(unittest.TestCase):
    def test_all_sources_parse(self):
        for p in H.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    def test_exact_input_baseline(self):
        b=json.loads((H/'death-baseline.json').read_text())
        self.assertEqual(b['repository'],'yangerstar1/task-workbench');self.assertEqual(b['run_id'],37844163484)
        self.assertRegex(b['blend_sha256'],r'^[0-9a-f]{64}$')
    def test_geometry_and_nondeath_boundary(self):
        b=json.loads((H/'death-change-boundary.json').read_text())
        for r in b['unchanged_regions'].values():
            text=(H/r['file']).read_text().split(r['start_marker'],1)[1].split(r['end_marker'],1)[0]
            self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),r['sha256'])
        self.assertEqual(hashlib.sha256((H/'parameters.json').read_bytes()).hexdigest(),b['parameters_sha256'])
    def test_anatomical_definition_is_explicit(self):
        source=(H/'death_anatomy.py').read_text()
        for marker in ('segment_fraction','distance_from_joint_m','weights','-.50<=t<=.45','p.length<=.34'):
            self.assertIn(marker,source)
        self.assertIn('former >=60% trunk-only', (H/'death-baseline.json').read_text())
    def test_technical_branch_never_renders(self):
        tree=ast.parse((H/'death_repose.py').read_text())
        blocks=[n for n in tree.body if isinstance(n,ast.If) and ast.unparse(n.test)=="args.phase == 'technical'"]
        self.assertEqual(len(blocks),1)
        calls=[ast.unparse(n.func) for child in blocks[0].body for n in ast.walk(child) if isinstance(n,ast.Call)]
        self.assertNotIn('bpy.ops.render.render',calls)
    def test_four_stills_gate_and_readonly_workflow(self):
        w=(H.parents[3]/'.github/workflows/desert-rv-pouncer-art.yml').read_text()
        self.assertIn("steps.technical.outcome == 'success'",w);self.assertIn('contents: read',w);self.assertIn('actions: read',w)
        self.assertIn("github.triggering_actor == github.repository_owner",w);self.assertIn('death-technical-first',w)
        s=(H/'death_repose.py').read_text();self.assertIn("digest!=gate['candidate_blend_sha256']",s);self.assertIn('if errors:raise RuntimeError',s)
    def test_original_collision_duration_and_root_contract(self):
        s=(H/'death_repose.py').read_text();p=json.loads((H/'parameters.json').read_text())
        self.assertEqual(p['clips']['Death'],1.8);self.assertEqual(p['fps'],100)
        self.assertIn("worst['z']<-.004",s);self.assertIn('range(361)',s);self.assertIn('if max(roots)>1e-6',s)
    def test_continuous_joint_path_precedes_contact(self):
        b=json.loads((H/'death-baseline.json').read_text());times=b['continuous_control_times']
        self.assertEqual(times,sorted(set(times)));self.assertEqual(times[0],0);self.assertEqual(times[-1],1.8)
        source=(H/'death_repose.py').read_text()
        self.assertLess(source.index('controls.append'),source.index('physical_support_translation_z'))
        self.assertIn("quat.to_euler('XYZ',old_euler)",source);self.assertIn('q1.make_compatible(q0)',source)
    def test_native_and_both_serialized_gates_are_required(self):
        source=(H/'death_repose.py').read_text();verify=(H/'verify_serialized_death.py').read_text()
        self.assertIn('DEATH_NATIVE_SOURCE_PASS_PENDING_IMPORTS',source)
        self.assertIn("bpy.ops.import_scene.gltf",verify);self.assertIn('bpy.ops.import_scene.fbx',verify)
        self.assertIn("=={'glb','fbx'}",verify);self.assertIn('range(361)',verify)
        workflow=(H.parents[3]/'.github/workflows/desert-rv-pouncer-art.yml').read_text()
        self.assertIn("steps.glb_import.outcome == 'success'",workflow);self.assertIn("steps.fbx_import.outcome == 'success'",workflow)
    def test_importer_helper_handling_is_provenance_based(self):
        source=(H/'verify_serialized_death.py').read_text()
        self.assertIn('disable_bone_shape=True',source);self.assertIn('len(source_nodes)!=27',source)
        self.assertIn('confirmed_importer_only_display_shape',source)
        self.assertIn("{o.name for o in actual}!=expected",source)
        self.assertIn('custom_shape_users',source);self.assertIn('Final imported mesh set',source)
        self.assertNotIn("obj.name=='Icosphere'",source);self.assertNotIn("obj.name != 'Icosphere'",source)
        self.assertIn("meshes=[o for o in scene.objects if o.type=='MESH']",source)
if __name__=='__main__':unittest.main()
