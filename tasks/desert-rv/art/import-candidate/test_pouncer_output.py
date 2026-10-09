"""Synthetic native-report/security fixtures, using the genuine pinned source bytes.

These tests never execute Unity and cannot establish native or visual acceptance.
Set POUNCER_CONTRACT and POUNCER_SOURCE_DIR when the real fixtures live elsewhere.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
import yaml
import pouncer_output as p

LOCAL_CONTRACT = Path(__file__).parent/'contracts/pouncer-full-strict-37856618820.json'
LOCAL_SOURCE = Path(__file__).parents[2]/'unity/CandidateImportInput/payload'


class PouncerExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidate = Path(__file__).parent/'contracts/pouncer-full-strict-37856618820.json'
        cls.contract_path = Path(os.environ.get('POUNCER_CONTRACT', str(candidate if candidate.exists() else LOCAL_CONTRACT)))
        cls.source_dir = Path(os.environ.get('POUNCER_SOURCE_DIR', str(LOCAL_SOURCE)))
        if not cls.contract_path.is_file() or not cls.source_dir.is_dir():
            raise RuntimeError('Provide the reviewed POUNCER_CONTRACT and genuine POUNCER_SOURCE_DIR fixtures; do not substitute fake hashes.')
        cls.contract_bytes = cls.contract_path.read_bytes()
        assert hashlib.sha256(cls.contract_bytes).hexdigest() == p.CONTRACT_SHA
        c = json.loads(cls.contract_bytes)
        cls.source_bytes = {r['file']: (cls.source_dir/r['file']).read_bytes() for r in c['files']}
        assert all(hashlib.sha256(cls.source_bytes[r['file']]).hexdigest() == r['sha256'] for r in c['files'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'fixture.png'
            image = Image.new('RGB', (960, 540), (30, 40, 50))
            ImageDraw.Draw(image).rectangle((150, 100, 600, 400), fill=(180, 90, 50)); image.save(path)
            cls.png = path.read_bytes()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)/'desert-rv'
        self.project = self.root/'unity'; self.out = self.root/'safe-export'
        self.c = json.loads(self.contract_bytes)
        self.prefix = 'Assets/DesertRV/CandidateArtImports/'+self.c['id']
        self.folder = self.project/self.prefix; self.ev = self.project/'JourneyEvidence/CandidateArt'
        self.ev.mkdir(parents=True); self.guid = 0
        self.write('CandidateImportInput/contract.json', self.contract_bytes)
        self.write(self.prefix+'/contract.json', self.contract_bytes)
        for name, data in self.source_bytes.items():
            path = self.write(self.prefix+'/Source/'+name, data); self.meta(path)
        for name in ('Candidate.prefab', 'Candidate.controller'):
            path = self.write(self.prefix+'/'+name, '%YAML 1.1\n--- !u!1 &1\nCandidate: {}\n'); self.meta(path)
        for path in (self.folder/'contract.json', self.folder, self.folder.parent,
                     self.folder/'Source', self.folder/'Materials'):
            self.meta(path)
        script = self.write(p.ACTOR_SCRIPT, '// Synthetic protected-script fixture, not native evidence.\n')
        self.meta(script)
        for i, spec in enumerate(self.c['materials']):
            texture = {'fileID': 0}
            if spec['baseColorFile']:
                texture = dict(fileID=2800000, guid=p._meta_guid(self.folder/'Source'/spec['baseColorFile']), type=3)
            asset = dict(m_Name=spec['sourceName']+'_Candidate', m_Shader=dict(fileID=4800000, guid=p.URP_LIT_GUID, type=3),
                m_ValidKeywords=[], m_SavedProperties=dict(m_Floats=[{'_Metallic': spec['metallic']},
                {'_Smoothness': spec['smoothness']}, {'_Cull': 2}], m_Colors=[{'_BaseColor': spec['baseColor']},
                {'_EmissionColor': dict(r=0, g=0, b=0, a=1)}], m_TexEnvs=[{'_BaseMap': {'m_Texture': texture}}]))
            path = self.write(self.prefix+f'/Materials/Material_{i:02}.mat', '%YAML 1.1\n--- !u!21 &2100000\n'+yaml.safe_dump({'Material': asset}, sort_keys=False))
            self.meta(path)
        self.imp = dict(mode='STRICT_BINDING', scope='FULL_CANDIDATE', kind='pouncer',
            status='candidate-structure-imported-unreviewed', contractSha256=p.CONTRACT_SHA,
            prefab=self.prefix+'/Candidate.prefab', dependencyHash='a'*32,
            dependencies=sorted(p.required_dependencies(self.c, self.prefix)),
            runUrl=self.c['runUrl'], sourceCommit=self.c['sourceCommit'], artifactName=self.c['artifactName'],
            artifactSha256=self.c['artifactSha256'], candidateOnly=True, visualReviewed=False, gameplayReviewed=False,
            failures=[], importedAnimatorPaths=[], muzzle=None, weaponCalibration=None,
            stillRequired=p.IMPORT_LIMITS.copy(), derivedTextures=[])
        self.imp['clips'] = [dict(spec, frameRate=100, floatBindings=480, objectBindings=0) for spec in self.c['clips']]
        self.imp['rootCurves'] = []
        anchor = self.c['bindings']['rigCurveBaseline']
        for state in p.STATES:
            for prop in sorted(p.ROOT_PROPERTIES):
                group, axis = prop.split('.'); field = {'m_LocalPosition': 'position', 'm_LocalRotation': 'rotation', 'm_LocalScale': 'scale'}[group]
                value = anchor[field][axis]
                self.imp['rootCurves'].append(dict(state=state, property=prop, keys=2, minimum=value, maximum=value, constant=True, tangentsSafe=True))
        frames = []
        state_hashes = {state: i+1 for i, state in enumerate(p.STATES)}
        for i, (label, step) in enumerate(p.sample_schedule()):
            name = f'frame-{i:04}.png'; (self.ev/name).write_bytes(self.png)
            state = (label.split('-')[0] if i < 35 else label.rsplit('-',2)[1] if i < 182 else 'Idle')
            normalized = float(label.rsplit('-',1)[1]) if i < 35 else 0
            frames.append(dict(image=name, requestedState=label, imageSha256=hashlib.sha256(self.png).hexdigest(),
                meshPoseSha256=hashlib.sha256(label.encode()).hexdigest(), advanceSeconds=step, normalizedTime=normalized,
                worldMinY=0, groundReferenceY=0, rootLocalPositionDelta=0, rootLocalAngleDelta=0, rootLocalScaleDelta=0,
                stateHash=state_hashes[state], sampledVertices=100, outsideViewportVertices=0, behindCameraVertices=0,
                belowReferenceVertices=0, transitioning=False, groundDiagnosticApplicable=True,
                rootLocalPosition=dict(x=0, y=0, z=0), rootLocalRotation=dict(x=0, y=0, z=0, w=1),
                rootLocalScale=dict(x=1, y=1, z=1), meshWorldMin=dict(x=0, y=0, z=0),
                meshWorldMax=dict(x=1, y=2, z=3), meshWorldSize=dict(x=1, y=2, z=3),
                meshSizeRatioToNeutral=dict(x=1, y=1, z=1)))
        self.cap = dict(graphicsDeviceType='OpenGLCore', graphicsDeviceName='llvmpipe (LLVM 15.0.7, 256 bits)',
            status='captured-unreviewed', scope='real-Animator-pose-diagnostics-only', prefab=self.imp['prefab'],
            visualAccepted=False, gameplayAccepted=False, armoredAttackLoopIntent=p.LOOP_INTENT,
            notCovered=p.CAPTURE_LIMITS.copy(), frames=frames, weapon=None,
            neutralRoot=copy.deepcopy(self.c['bindings']['neutralBaseline']), neutralMeshWorldMin=dict(x=0,y=0,z=0),
            neutralMeshWorldMax=dict(x=1,y=2,z=3), neutralMeshWorldSize=dict(x=1,y=2,z=3))
        self.native = self.root/'artifacts/candidate-art/results.xml'; self.native.parent.mkdir(parents=True)
        self.native.write_text('<test-run result="Passed">'+''.join('<test-case fullname="'+name+'" result="Passed"/>'
            for name in sorted(p.NATIVE_NAMES))+'</test-run>')
        self.rehash(); self.flush()

    def tearDown(self): self.tmp.cleanup()

    def write(self, relative, data):
        path = self.project/relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode()); return path

    def meta(self, path):
        self.guid += 1; target = Path(str(path)+'.meta'); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('fileFormatVersion: 2\nguid: '+f'{self.guid:032x}'+'\nDefaultImporter: {}\n')

    def rehash(self):
        self.imp['dependencySha256'] = p.dependency_digest(self.project, self.imp['dependencies'])
        self.cap['dependencySha256'] = self.imp['dependencySha256']

    def flush(self):
        for name, value in [('import-report.json', self.imp), ('capture-report.json', self.cap)]:
            (self.ev/name).write_text(json.dumps(value))

    def run_export(self, **kwargs):
        self.flush()
        with patch.dict(os.environ, {'GITHUB_SHA': 'a'*40, 'GITHUB_RUN_ID': '123'}):
            return p.export(self.root, self.out, **kwargs)

    def rejected(self, code=None, **kwargs):
        with self.assertRaises(p.StrictError): self.run_export(**kwargs)
        receipt = json.loads((self.out/'receipt.json').read_text())
        self.assertEqual(receipt['status'], 'FAILED_NOT_ACCEPTED'); self.assertFalse(receipt['approved'])
        self.assertEqual(list(self.out.iterdir()), [self.out/'receipt.json'])
        self.assertNotIn('fixture-secret', json.dumps(receipt)); self.assertNotIn('files', receipt)
        self.assertEqual(list(self.out.parent.glob('.pouncer-safe-*')), [])
        if code: self.assertEqual(receipt['errorCode'], code)

    def change_material(self, index, edit):
        path = self.folder/f'Materials/Material_{index:02}.mat'
        value = p._unity_yaml(path)[0]; edit(value['Material'])
        path.write_text('%YAML 1.1\n--- !u!21 &2100000\n'+yaml.safe_dump(value, sort_keys=False)); self.rehash()

    def test_valid_unreviewed_export_rehashes_every_file(self):
        result = self.run_export()
        self.assertEqual((result['images'], result['nativeCases'], result['weakpointImages']), (184, 7, 0))
        self.assertEqual([result[k] for k in ('directImages','attackRecoverImages','deathTransitionImages','resetImages')], [35,21,126,2])
        self.assertTrue(all(result[k] is False for k in ('approved','calibratedForScene','visualApproved','gameplayAccepted')))
        self.assertEqual(len(list((self.out/'frames').glob('*.png'))), 184)
        self.assertNotIn('muzzle', json.loads((self.out/'import-report.json').read_text()))
        for row in result['files']: self.assertEqual(p.sha(self.out/row['path']), row['sha256'])
        self.assertEqual(result['rawReportSha256']['capture-report.json'], p.sha(self.ev/'capture-report.json'))

    def test_actual_pinned_contract_has_27_renderers_and_two_distinct_scales(self):
        p.contract_shape(self.c)
        b = self.c['bindings']; self.assertEqual(b['animatorPath'], '')
        self.assertEqual(len(b['neutralBaseline']['renderers']), 27)
        self.assertEqual(b['neutralBaseline']['scale'], dict(x=1,y=1,z=1))
        self.assertEqual(b['rigCurveBaseline']['scale'], dict(x=100,y=100,z=100))

    def test_exact_schedule_excludes_armored_extras(self):
        labels = p.expected_labels(); self.assertEqual(len(labels), 184)
        self.assertFalse(any('weakpoint' in x or 'overrun' in x or '1.1-Recover' in x for x in labels))
        self.assertIn('Hit-0.75-Death-0.986', labels); self.assertIn('Attack-0.25-Recover-0.016', labels)

    def test_partial_scope_rejected(self):
        self.c['scope']='PARTIAL_DIAGNOSTIC_NOT_FULL'
        with self.assertRaisesRegex(p.StrictError,'POUNCER_FULL_ONLY'): p.contract_shape(self.c)

    def test_armored_and_weapon_contracts_rejected(self):
        for kind in ('armored','weapon'):
            c=copy.deepcopy(self.c); c['kind']=kind
            with self.assertRaisesRegex(p.StrictError,'POUNCER_FULL_ONLY'): p.contract_shape(c)

    def test_reviewed_contract_rejects_new_source_binding_material_and_loop(self):
        for edit in (lambda c:c.update(sourceCommit='b'*40), lambda c:c['bindings'].update(animatorPath='Pouncer_Rig'),
                     lambda c:c['materials'][0].update(metallic=1), lambda c:c['clips'][3].update(loop=True),
                     lambda c:c['bindings']['neutralBaseline']['renderers'][0]['worldExtents'].update(x=1)):
            c=copy.deepcopy(self.c); edit(c)
            with self.assertRaisesRegex(p.StrictError,'POUNCER_REVIEWED_CONTRACT_MISMATCH'): p.contract_shape(c)

    def test_contract_duplicate_key_rejected(self):
        (self.project/'CandidateImportInput/contract.json').write_text('{"mode":"STRICT_BINDING","mode":"fixture-secret"}')
        self.rejected('STRICT_DUPLICATE_JSON_KEY')

    def test_contract_raw_byte_pin_rejected(self):
        (self.project/'CandidateImportInput/contract.json').write_bytes(self.contract_bytes+b'\n')
        self.rejected('POUNCER_REVIEWED_CONTRACT_MISMATCH')

    def test_native_failure_receipt_only(self): self.rejected('STRICT_NATIVE_FAILED',native='failure')
    def test_protected_failure_receipt_only(self): self.rejected('STRICT_PROTECTED_SOURCE_FAILED',protected='failure')
    def test_native_missing_cleanup_case_rejected(self):
        import xml.etree.ElementTree as ET
        tree=ET.parse(self.native); root=tree.getroot()
        root.remove(next(c for c in root if c.get('fullname','').endswith('RenderTargetCleanupDetachesCameraBeforeDestroy')))
        tree.write(self.native); self.rejected('STRICT_NATIVE_FAILED')
    def test_native_duplicate_case_rejected(self):
        text=self.native.read_text(); self.native.write_text(text.replace('</test-run>','<test-case fullname="fixture-secret" result="Passed"/></test-run>'))
        self.rejected('STRICT_NATIVE_FAILED')
    def test_native_failed_case_rejected(self):
        self.native.write_text(self.native.read_text().replace('result="Passed"','result="Failed"',1)); self.rejected('STRICT_NATIVE_FAILED')

    def test_import_source_mismatch(self): self.imp['sourceCommit']='b'*40; self.rejected('POUNCER_IMPORT_SOURCE_MISMATCH')
    def test_import_approval_forbidden(self): self.imp['visualReviewed']=True; self.rejected('POUNCER_APPROVAL_FORBIDDEN')
    def test_unknown_report_field_rejected(self): self.imp['rawLogs']='fixture-secret'; self.rejected('STRICT_SCHEMA_MISMATCH')
    def test_unknown_nested_field_rejected(self): self.imp['clips'][0]['rawLogs']='fixture-secret'; self.rejected('STRICT_SCHEMA_MISMATCH')
    def test_inapplicable_weapon_fields_normalized_without_export(self):
        self.imp['muzzle']={'gate':'fixture-secret','calibratedForScene':True}
        self.imp['weaponCalibration']={'visualApproved':True,'rawLogs':'fixture-secret'}
        self.cap['weapon']={'gameplayAccepted':True,'rawLogs':'fixture-secret'}
        result=self.run_export()
        self.assertEqual(len(result['normalizedAwayFields']),3)
        for name in ('import-report.json','capture-report.json','receipt.json'):
            self.assertNotIn('fixture-secret',(self.out/name).read_text())
        self.assertNotIn('weapon',json.loads((self.out/'capture-report.json').read_text()))
        self.assertFalse(result['gameplayAccepted'])
    def test_derived_textures_forbidden(self): self.imp['derivedTextures']=[{}]; self.rejected('POUNCER_DERIVED_FORBIDDEN')
    def test_imported_animator_child_rejected(self): self.imp['importedAnimatorPaths']=['Pouncer_Rig']; self.rejected('POUNCER_ANIMATOR_ROOT')
    def test_100_hz_required(self): self.imp['clips'][0]['frameRate']=60; self.rejected('POUNCER_IMPORTED_CLIP_MISMATCH')
    def test_float_binding_count_locked(self): self.imp['clips'][0]['floatBindings']=470; self.rejected('POUNCER_IMPORTED_CLIP_MISMATCH')
    def test_attack_must_not_loop(self): self.imp['clips'][3]['loop']=True; self.rejected('POUNCER_IMPORTED_CLIP_MISMATCH')
    def test_held_death_cannot_replace_varying_clip(self): self.imp['clips'][6]['poseExpectation']='held'; self.rejected('POUNCER_IMPORTED_CLIP_MISMATCH')
    def test_object_curves_rejected(self): self.imp['clips'][0]['objectBindings']=1; self.rejected('POUNCER_IMPORTED_CLIP_MISMATCH')
    def test_rig_scale_100_cannot_be_normalized_to_one(self):
        row=next(r for r in self.imp['rootCurves'] if r['property']=='m_LocalScale.x'); row['minimum']=row['maximum']=1
        self.rejected('POUNCER_RIG_CURVE_BASELINE')
    def test_rig_tangents_required(self): self.imp['rootCurves'][0]['tangentsSafe']=False; self.rejected('POUNCER_RIG_CURVE_MOTION')
    def test_rig_curve_motion_rejected(self): self.imp['rootCurves'][0]['maximum']+=.01; self.rejected('POUNCER_RIG_CURVE_MOTION')
    def test_rig_curve_duplicate_rejected(self): self.imp['rootCurves'][0]=self.imp['rootCurves'][1].copy(); self.rejected('POUNCER_RIG_CURVE_INVENTORY')

    def test_dependency_missing_controller(self): self.imp['dependencies'].remove(self.prefix+'/Candidate.controller'); self.rejected('POUNCER_DEPENDENCY_INVENTORY')
    def test_dependency_outside_exact_pouncer_inventory(self): self.imp['dependencies'].append('Assets/DesertRV/Runtime/WeaponPresentation.cs'); self.rejected('POUNCER_DEPENDENCY_INVENTORY')
    def test_dependency_traversal_rejected(self): self.imp['dependencies'].append('../fixture-secret'); self.rejected('POUNCER_DEPENDENCY_INVENTORY')
    def test_dependency_bytes_changed(self): (self.folder/'Candidate.prefab').write_text('%YAML 1.1\nChanged: true\n'); self.rejected('POUNCER_DEPENDENCY_HASH')
    def test_missing_source_guid_rejected(self): Path(str(self.folder/'Source/pouncer-candidate.fbx')+'.meta').unlink(); self.rejected('STRICT_UNSAFE_FILE')
    def test_unknown_prefab_guid_rejected(self):
        (self.folder/'Candidate.prefab').write_text('%YAML 1.1\nPrefab: {m_Source: {fileID: 1, guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa}}\n')
        self.rehash(); self.rejected('POUNCER_DEPENDENCY_GUID_CLOSURE')
    def test_duplicate_meta_guid_rejected(self):
        a=self.folder/'Candidate.prefab.meta'; b=self.folder/'Candidate.controller.meta'; a.write_bytes(b.read_bytes())
        self.rehash(); self.rejected('POUNCER_DEPENDENCY_GUID_DUPLICATE')
    def test_material_original_source_color_required(self):
        self.change_material(0, lambda m:m['m_SavedProperties']['m_Colors'][0]['_BaseColor'].update(r=0))
        self.rejected('POUNCER_MATERIAL_VALUES')
    def test_material_cull_is_original_single_sided(self):
        self.change_material(0, lambda m:m['m_SavedProperties']['m_Floats'][2].update(_Cull=0))
        self.rejected('POUNCER_MATERIAL_VALUES')
    def test_material_source_name_required(self):
        self.change_material(0,lambda m:m.update(m_Name='Armored_Candidate')); self.rejected('POUNCER_MATERIAL_ASSET')
    def test_material_atlas_texture_must_reference_real_source_guid(self):
        self.change_material(3,lambda m:m['m_SavedProperties']['m_TexEnvs'][0]['_BaseMap'].update(m_Texture={'fileID':0}))
        self.rejected('POUNCER_MATERIAL_TEXTURE_BINDING')
    def test_material_unlisted_texture_role_rejected(self):
        self.change_material(0,lambda m:m['m_SavedProperties']['m_TexEnvs'].append({'_UnexpectedMap':{'m_Texture':{'fileID':2800000,'guid':p._meta_guid(self.folder/'Source/pouncer-basecolor.png')}}}))
        self.rejected('POUNCER_UNDECLARED_TEXTURE')
    def test_material_emission_forbidden(self):
        self.change_material(0,lambda m:m['m_SavedProperties']['m_Colors'][1]['_EmissionColor'].update(r=1))
        self.rejected('POUNCER_UNDECLARED_EMISSION')
    def test_duplicate_yaml_key_rejected(self):
        path=self.folder/'Candidate.prefab'; path.write_text('%YAML 1.1\nCandidate: {}\nCandidate: {}\n')
        self.rehash(); self.rejected('POUNCER_DUPLICATE_YAML_KEY')
    def test_model_importer_external_object_unknown_guid_rejected(self):
        path=self.folder/'Source/pouncer-candidate.fbx.meta'
        path.write_text(path.read_text()+'ModelImporter:\n  externalObjects:\n  - first: {type: UnityEngine.Material, name: AmberEye}\n    second: {fileID: 2100000, guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, type: 2}\n')
        self.rehash(); self.rejected('POUNCER_DEPENDENCY_GUID_CLOSURE')
    def test_folder_meta_nested_unknown_guid_rejected(self):
        path=self.folder/'Materials.meta'
        path.write_text(path.read_text()+'CustomImporter:\n  nested:\n  - target: {fileID: 1, guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa}\n')
        self.rejected('POUNCER_DEPENDENCY_GUID_CLOSURE')
    def test_export_root_meta_nested_unknown_guid_rejected(self):
        path=Path(str(self.folder.parent)+'.meta')
        path.write_text(path.read_text()+'DefaultReferences:\n  deep: {guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa}\n')
        self.rejected('POUNCER_DEPENDENCY_GUID_CLOSURE')
    def test_meta_duplicate_importer_key_rejected(self):
        path=self.folder/'Source/pouncer-candidate.fbx.meta'
        path.write_text(path.read_text()+'ModelImporter:\n  externalObjects: []\n  externalObjects: []\n')
        self.rehash(); self.rejected('POUNCER_DUPLICATE_YAML_KEY')
    def test_meta_unknown_guid_length_rejected(self):
        path=self.folder/'contract.json.meta'
        path.write_text(path.read_text()+'Nested: {guid: malformed}\n')
        self.rejected('POUNCER_DEPENDENCY_GUID_CLOSURE')
    def test_model_importer_known_external_material_guid_allowed(self):
        path=self.folder/'Source/pouncer-candidate.fbx.meta'
        guid=p._meta_guid(self.folder/'Materials/Material_00.mat')
        path.write_text(path.read_text()+'ModelImporter:\n  externalObjects:\n  - second: {fileID: 2100000, guid: '+guid+', type: 2}\n')
        self.rehash()
        payload=p.generated_files(self.project,self.c,self.prefix,self.imp,p.contract_shape(self.c))
        self.assertIn(path,{src for src,_ in payload})

    def test_model_root_scale_one_not_internal_rig_scale(self): self.cap['neutralRoot']['scale']=dict(x=100,y=100,z=100); self.rejected('POUNCER_NEUTRAL_ROOT_MISMATCH')
    def test_exact_27_renderer_inventory(self): self.cap['neutralRoot']['renderers'].pop(); self.rejected('POUNCER_NEUTRAL_RENDERER_INVENTORY')
    def test_actual_renderer_bounds_locked(self): self.cap['neutralRoot']['renderers'][0]['worldExtents']['x']*=.01; self.rejected('POUNCER_NEUTRAL_BOUNDS_MISMATCH')
    def test_hidden_frame_root_scale_change(self): self.cap['frames'][0]['rootLocalScale']=dict(x=100,y=100,z=100); self.rejected('POUNCER_ROOT_VECTOR_DRIFT')
    def test_mesh_size_ratio_cannot_hide_scale_change(self): self.cap['frames'][0]['meshSizeRatioToNeutral']['x']=.01; self.rejected('POUNCER_MESH_RATIO')
    def test_mesh_bounds_and_size_must_agree(self): self.cap['frames'][0]['meshWorldSize']['x']=.01; self.rejected('STRICT_MESH_DIMENSIONS')
    def test_missing_frame_rejected(self): self.cap['frames'].pop(); self.rejected('POUNCER_FRAME_COUNT')
    def test_armored_overrun_label_rejected(self): self.cap['frames'][0]['requestedState']='Attack-overrun-1.1'; self.rejected('POUNCER_FRAME_INVENTORY')
    def test_duplicate_label_rejected(self): self.cap['frames'][1]['requestedState']=self.cap['frames'][0]['requestedState']; self.rejected('POUNCER_FRAME_INVENTORY')
    def test_wrong_actual_update_step_rejected(self): self.cap['frames'][0]['advanceSeconds']=.016; self.rejected('POUNCER_FRAME_STATE')
    def test_ground_4mm_boundary_allowed(self):
        f=self.cap['frames'][0]; f['worldMinY']=f['meshWorldMin']['y']=-.004; f['meshWorldSize']['y']=2.004; f['meshSizeRatioToNeutral']['y']=1.002
        self.assertEqual(self.run_export()['images'],184)
    def test_ground_beyond_4mm_rejected(self): self.cap['frames'][0]['worldMinY']=-.00401; self.rejected('POUNCER_GROUND_PENETRATION')
    def test_ground_gate_cannot_be_disabled(self): self.cap['frames'][0]['groundDiagnosticApplicable']=False; self.rejected('POUNCER_FRAME_STATE')
    def test_ground_reference_cannot_be_lowered(self): self.cap['frames'][0]['groundReferenceY']=-1; self.rejected('POUNCER_GROUND_REFERENCE')
    def test_direct_pose_actual_time_required(self): self.cap['frames'][1]['normalizedTime']=0; self.rejected('POUNCER_DIRECT_STATE')
    def test_actual_direct_state_hash_consistency(self): self.cap['frames'][1]['stateHash']=999; self.rejected('POUNCER_DIRECT_STATE')
    def test_final_crossfade_reaches_target_state(self): self.cap['frames'][41]['stateHash']=999; self.rejected('POUNCER_TRANSITION_INCOMPLETE')
    def test_final_crossfade_is_no_longer_transitioning(self): self.cap['frames'][41]['transitioning']=True; self.rejected('POUNCER_TRANSITION_INCOMPLETE')
    def test_reset_reaches_idle(self): self.cap['frames'][-1]['stateHash']=999; self.rejected('POUNCER_RESET_INCOMPLETE')
    def test_capture_approval_rejected(self): self.cap['gameplayAccepted']=True; self.rejected('POUNCER_CAPTURE_STATUS')
    def test_nonfinite_json_rejected(self): self.cap['frames'][0]['worldMinY']=float('nan'); self.rejected('STRICT_NONFINITE_JSON')
    def test_boolean_masquerading_as_number_rejected(self): self.cap['frames'][0]['sampledVertices']=True; self.rejected('POUNCER_MESH_COUNT')
    def test_null_renderer_rejected(self): self.cap['graphicsDeviceType']='Null'; self.rejected('POUNCER_REAL_SOFTWARE_GRAPHICS_REQUIRED')
    def test_secret_graphics_device_text_rejected(self): self.cap['graphicsDeviceName']='llvmpipe\nfixture-secret'; self.rejected('POUNCER_REAL_SOFTWARE_GRAPHICS_REQUIRED')
    def test_image_hash_mismatch_rejected(self): (self.ev/'frame-0000.png').write_bytes(b'broken'); self.rejected('POUNCER_FRAME_IDENTITY')
    def test_black_image_rejected(self):
        path=self.ev/'frame-0000.png'; Image.new('RGB',(960,540)).save(path); self.cap['frames'][0]['imageSha256']=p.sha(path)
        self.rejected('STRICT_BLANK_IMAGE')
    def test_wrong_image_dimensions_rejected(self):
        path=self.ev/'frame-0000.png'; Image.new('RGB',(960,539),(80,80,80)).save(path); self.cap['frames'][0]['imageSha256']=p.sha(path)
        self.rejected('STRICT_IMAGE_DIMENSIONS')
    def test_pose_variation_required_for_all_seven_clips(self):
        for f in self.cap['frames'][:5]: f['meshPoseSha256']='a'*64
        self.rejected('POUNCER_POSE_NOT_VARYING')

    def test_extra_weakpoint_report_rejected(self): (self.ev/'weakpoint-fixture-report.json').write_text('{"raw":"fixture-secret"}'); self.rejected('POUNCER_EVIDENCE_ALLOWLIST')
    def test_extra_raw_log_rejected(self): (self.ev/'Unity.log').write_text('fixture-secret'); self.rejected('POUNCER_EVIDENCE_ALLOWLIST')
    def test_extra_core_open_material_rejected(self): (self.folder/'Materials/Core_Open.mat').write_text('%YAML 1.1\nMaterial: {}\n'); self.rejected('POUNCER_GENERATED_ALLOWLIST')
    def test_derived_directory_rejected(self): (self.folder/'Derived').mkdir(); self.rejected('POUNCER_GENERATED_DIRECTORY')
    def test_symlink_source_rejected(self):
        path=self.folder/'Source/pouncer-candidate.fbx'; path.unlink(); path.symlink_to(self.source_dir/'pouncer-candidate.fbx'); self.rejected('POUNCER_SYMLINK_FORBIDDEN')
    def test_real_fbx_hash_required_even_after_dependency_rehash(self):
        (self.folder/'Source/pouncer-candidate.fbx').write_bytes(b'fixture-secret'); self.rehash(); self.rejected('POUNCER_GENERATED_SOURCE')

    def test_mutation_after_validation_is_rejected(self):
        original=p.validate_capture
        def change(*args):
            result=original(*args); (self.folder/'Candidate.prefab').write_text('fixture-secret'); return result
        with patch.object(p,'validate_capture',change): self.rejected()
    def test_new_evidence_file_after_validation_is_rejected(self):
        original=p.verify_snapshot; calls=0
        def change(*args):
            nonlocal calls
            calls+=1
            if calls==2: (self.ev/'new.log').write_text('fixture-secret')
            return original(*args)
        with patch.object(p,'verify_snapshot',change): self.rejected('POUNCER_INPUT_CHANGED_DURING_VALIDATION')
    def test_native_changes_after_validation_are_rejected(self):
        original=p.validate_capture
        def change(*args):
            result=original(*args); self.native.write_text('<test-run result="Failed"/>'); return result
        with patch.object(p,'validate_capture',change): self.rejected('POUNCER_INPUT_CHANGED_DURING_VALIDATION')
    def test_copy_mutation_is_rejected_before_commit(self):
        original=shutil.copyfile
        def change(source,target,*args,**kwargs):
            result=original(source,target,*args,**kwargs)
            if str(target).endswith('Candidate.prefab'): Path(target).write_text('fixture-secret')
            return result
        with patch.object(p.shutil,'copyfile',change): self.rejected('POUNCER_SOURCE_CHANGED_DURING_EXPORT')
    def inject_staging_node(self, create, code):
        original=shutil.copyfile
        def change(source,target,*args,**kwargs):
            result=original(source,target,*args,**kwargs)
            if Path(target).name=='frame-0183.png':
                staged=next(parent for parent in Path(target).parents if parent.name.startswith('.pouncer-safe-'))
                create(staged)
            return result
        with patch.object(p.shutil,'copyfile',change): self.rejected(code)
    def test_unlisted_log_added_after_copy_cannot_be_committed(self):
        self.inject_staging_node(lambda staged:(staged/'unlisted.log').write_text('fixture-secret'),'POUNCER_STAGING_INVENTORY')
    def test_unlisted_empty_staging_directory_rejected(self):
        self.inject_staging_node(lambda staged:(staged/'unlisted').mkdir(),'POUNCER_STAGING_INVENTORY')
    def test_unlisted_staging_symlink_rejected(self):
        self.inject_staging_node(lambda staged:(staged/'unlisted.log').symlink_to(self.native),'POUNCER_STAGING_UNSAFE_NODE')
    def test_unknown_staging_node_rejected(self):
        self.inject_staging_node(lambda staged:os.mkfifo(staged/'unlisted.pipe'),'POUNCER_STAGING_UNSAFE_NODE')
    def test_staging_receipt_bytes_are_verified(self):
        original=p._verify_staging
        def change(staged,records,receipt_hash):
            (staged/'receipt.json').write_text('{"approved":true,"raw":"fixture-secret"}')
            return original(staged,records,receipt_hash)
        with patch.object(p,'_verify_staging',change): self.rejected('POUNCER_STAGING_CHANGED')
    def test_unlisted_node_added_during_final_hash_reads_is_rejected(self):
        original=p.sha
        def change(path):
            result=original(path); path=Path(path)
            if path.name=='receipt.json' and path.parent.name.startswith('.pouncer-safe-'):
                (path.parent/'unlisted.log').write_text('fixture-secret')
            return result
        with patch.object(p,'sha',change): self.rejected('POUNCER_STAGING_INVENTORY')
    def test_atomic_commit_failure_has_receipt_only(self):
        original=Path.replace
        def fail(path,target):
            if path.name.startswith('.pouncer-safe-'): raise OSError('fixture-secret')
            return original(path,target)
        with patch.object(Path,'replace',fail): self.rejected('INVALID_EVIDENCE')
    def test_existing_output_never_overwritten(self):
        self.out.mkdir(); (self.out/'existing.txt').write_text('keep')
        with self.assertRaisesRegex(p.StrictError,'POUNCER_EXPORT_EXISTS_OR_UNSAFE'): self.run_export()
        self.assertEqual((self.out/'existing.txt').read_text(),'keep')
    def test_summary_private_fields_scrubbed_at_dispatcher_entry(self):
        self.out.mkdir(); summary={'status':'approved','rawLogs':'fixture-secret','importCommit':'a'*40,
            'importRunUrl':'https://github.com/yangerstar1/task-workbench/actions/runs/123'}
        with self.assertRaisesRegex(p.StrictError,'STRICT_NATIVE_FAILED'):
            p.export_pouncer(self.root,self.out,self.c,summary,'failure','success')
        self.assertNotIn('rawLogs',summary); self.assertEqual(summary['status'],'FAILED_NOT_ACCEPTED'); self.assertFalse(summary['approved'])


if __name__ == '__main__': unittest.main()
