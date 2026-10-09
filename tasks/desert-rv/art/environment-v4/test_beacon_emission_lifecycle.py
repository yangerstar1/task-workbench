"""Offline source and typed-byte contract tests; not Unity compilation/render evidence."""
import hashlib
import re
import unittest
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
PROJECT = TASK / 'unity'
EDITOR = PROJECT / 'Assets/DesertRV/Editor'
SOURCE = (EDITOR / 'JourneySceneAuthoring.CorrectedTerrain.cs').read_text()
BEGIN = '        // CORRECTED_BEACON_EMISSION_BEGIN\n'
END = '        // CORRECTED_BEACON_EMISSION_END\n\n'
AUTHOR_CALL = '                FinalizeCorrectedBeaconEmission();\n'
BINDING_CALL = '                if(region==3)RecordCorrectedBeaconEmissionBinding(binding);\n'
BASE_SHA = '5d5cb18ced5011eac6fa5e8a5a8f602509d165662d7150c4acc136b2c035ba33'


def method(name):
    declaration = re.search(r'\b(?:public )?static [^\n]+\b' + re.escape(name) + r'\(', SOURCE)
    if declaration is None:
        raise AssertionError('Missing method ' + name)
    start = SOURCE.index('{', declaration.start())
    depth = 0
    # The selected methods contain no braces inside ordinary string literals.
    for pos in range(start, len(SOURCE)):
        if SOURCE[pos] == '{': depth += 1
        if SOURCE[pos] == '}':
            depth -= 1
            if depth == 0: return SOURCE[start:pos + 1]
    raise AssertionError('Unterminated method ' + name)


def canonical_material(data):
    """Exercise the two actual C# regexes, not a more permissive substitute."""
    if not data or len(data) > 65536:
        raise ValueError('size')
    text = data.decode('utf-8', errors='strict')
    body = method('CorrectedBeaconNonEmissionBytes')
    for field in ('flags', 'keyword'):
        pattern = re.search(r'var ' + field + r'=new Regex\(@"([^"]+)"', body).group(1)
        if len(re.findall(pattern, text)) != 1:
            raise ValueError('ambiguous ' + field)
        text = re.sub(pattern, '  ' + ('m_LightmapFlags' if field == 'flags' else 'm_ValidKeywords') + ': <authored-emission>', text)
    return text


# Synthetic minimal serialized record solely for exact field-delta rejection tests.
# Not claimed to be the missing raw material from run 38000418463.
FIXTURE = b'''%YAML 1.1
--- !u!21 &2100000
Material:
  m_Shader: {fileID: 4800000, guid: fixture-only, type: 3}
  m_ValidKeywords:
  - _EMISSION
  m_InvalidKeywords: []
  m_LightmapFlags: 4
  m_EnableInstancingVariants: 0
  m_CustomRenderQueue: -1
  m_SavedProperties:
    m_Floats:
    - _Smoothness: 0.12
    m_Colors:
    - _BaseColor: {r: 1, g: 0.76, b: 0.38, a: 1}
    - _EmissionColor: {r: 2.5, g: 1.9, b: 0.95, a: 2.5}
--- !u!114 &123
MonoBehaviour:
  version: 10
'''


class BeaconEmissionLifecycleTests(unittest.TestCase):
    def test_only_three_explicit_extensions_to_current_base(self):
        for value in (BEGIN, END, AUTHOR_CALL, BINDING_CALL):
            self.assertEqual(SOURCE.count(value), 1)
        start = SOURCE.index(BEGIN); end = SOURCE.index(END, start) + len(END)
        reversed_source = (SOURCE[:start] + SOURCE[end:]).replace(AUTHOR_CALL, '').replace(BINDING_CALL, '')
        self.assertEqual(hashlib.sha256(reversed_source.encode()).hexdigest(), BASE_SHA)

    def test_correction_runs_once_before_the_original_freeze(self):
        author = method('AuthorCorrectedTerrainCandidateScenes')
        self.assertEqual(author.count('FinalizeCorrectedBeaconEmission();'), 1)
        self.assertLess(author.index('AuthorCandidateScenes();'), author.index('FinalizeCorrectedBeaconEmission();'))
        self.assertLess(author.index('FinalizeCorrectedBeaconEmission();'), author.index('var before=SnapshotCorrectedTerrainGenerated();'))
        self.assertEqual(SOURCE.count('FinalizeCorrectedBeaconEmission();'), 1)
        bindings = method('ReadSavedCorrectedTerrainBindings')
        self.assertLess(bindings.index('OpenScene(RegionPaths[region-1]'), bindings.index('RecordCorrectedBeaconEmissionBinding(binding)'))
        after = method('VerifyCorrectedTerrainCandidatesAfterCapture')
        self.assertIn('ReadSavedCorrectedTerrainBindings(report)', after)
        self.assertNotIn('FinalizeCorrectedBeaconEmission', after)

    def test_only_one_generated_material_is_authored(self):
        extension = SOURCE.split(BEGIN)[1].split(END)[0]
        self.assertIn('const string CorrectedBeaconMaterial=Folder+"/Layout-FFC261.mat";', extension)
        self.assertEqual(len(re.findall(r'globalIlluminationFlags=(?!=)', extension)), 1)
        self.assertIn('material.globalIlluminationFlags=MaterialGlobalIlluminationFlags.BakedEmissive;', extension)
        for forbidden in ('.SetColor(', '.SetTexture(', '.EnableKeyword(', '.DisableKeyword(', 'SaveAssets(',
                          'FindAssets(', 'ForceReserializeAssets(', 'Refresh(', 'Lightmapping.Bake', 'RenderTexture',
                          'EditorSceneManager.', 'File.Write', 'AssetDatabase.CreateAsset('):
            self.assertNotIn(forbidden, extension)

    def test_uses_complete_installed_lit_validator_and_disposes_editor(self):
        body = method('ValidateCorrectedBeaconWithInstalledLit')
        self.assertIn('global::UnityEditor.Editor.CreateEditor(material) as MaterialEditor', body)
        self.assertIn('editor.customShaderGUI.GetType().FullName!="UnityEditor.Rendering.Universal.ShaderGUI.LitShader"', body)
        self.assertIn('editor.customShaderGUI.ValidateMaterial(material);', body)
        self.assertIn('return editor.customShaderGUI.GetType().FullName;', body)
        self.assertIn('finally{if(editor)Object.DestroyImmediate(editor);}', body)

    def test_guid_save_import_save_then_all_native_objects_clean(self):
        cycle = method('SettleCorrectedBeaconEmissionCycle')
        save = 'AssetDatabase.SaveAssetIfDirty(AssetDatabase.GUIDFromAssetPath(CorrectedBeaconMaterial));'
        self.assertEqual(cycle.count(save), 2)
        self.assertLess(cycle.index(save), cycle.index('AssetDatabase.ImportAsset('))
        self.assertLess(cycle.index('AssetDatabase.ImportAsset('), cycle.rindex(save))
        self.assertIn('ForceUpdate|ImportAssetOptions.ForceSynchronousImport', cycle)
        self.assertIn('AssetDatabase.LoadAllAssetsAtPath(CorrectedBeaconMaterial)', cycle)
        self.assertIn('objects.Any(item=>!item||!EditorUtility.IsPersistent(item)||EditorUtility.IsDirty(item))', cycle)
        self.assertNotIn('globalIlluminationFlags=', cycle)
        finalize = method('FinalizeCorrectedBeaconEmission')
        self.assertEqual(finalize.count('SettleCorrectedBeaconEmissionCycle()'), 2)
        for required in ('stable.SequenceEqual(File.ReadAllBytes(CorrectedBeaconMaterial))',
                         'HashFile(CorrectedBeaconMaterial+".meta")!=meta',
                         'authored.Any(row=>row.Key!=CorrectedBeaconMaterial&&settled[row.Key]!=row.Value)',
                         'CorrectedBeaconNonEmissionBytes(original)!=CorrectedBeaconNonEmissionBytes(stable)'):
            self.assertIn(required, finalize)

    def test_material_assertion_preserves_nonzero_original_hdr_and_keyword(self):
        body = method('RequireCorrectedBeaconMaterial')
        for required in ('new Color(1,.76f,.38f)*2.5f', 'material.IsKeywordEnabled("_EMISSION")',
                         'material.globalIlluminationFlags!=MaterialGlobalIlluminationFlags.BakedEmissive',
                         'EditorUtility.IsDirty(material)', 'material.shaderKeywords.Any(k=>k!="_EMISSION")',
                         'material.GetFloat("_Smoothness")!=.12f', 'material.GetFloat("_Surface")!=0'):
            self.assertIn(required, body)

    def test_capture_binding_check_is_read_only(self):
        body = method('RecordCorrectedBeaconEmissionBinding')
        self.assertIn('r.name=="Beacon warm lamp diffuser"', body)
        self.assertIn('row.expectedGI=material.globalIlluminationFlags==MaterialGlobalIlluminationFlags.BakedEmissive', body)
        self.assertIn('Resources.FindObjectsOfTypeAll<Object>()', body)
        self.assertIn('EditorUtility.IsDirty(item)', body)
        for forbidden in ('LoadAsset', 'LoadAllAssets', 'ImportAsset', 'SaveAsset', 'SetDirty',
                          'ValidateCorrectedBeacon', 'SettleCorrectedBeacon', 'throw ', 'RequireCorrectedBeaconMaterial(', '.SetColor(', '.EnableKeyword('):
            self.assertNotIn(forbidden, body)

    def test_unexpected_postcapture_state_is_observed_without_aborting_three_phases(self):
        body = method('RecordCorrectedBeaconEmissionBinding')
        for required in ('CORRECTED_BEACON_EMISSION_OBSERVATION',
                         'phase=File.Exists(CorrectedTerrainReceipt)?"postcapture":"author-reload"',
                         'row.materialDirty=EditorUtility.IsDirty(material)',
                         'if(EditorUtility.IsDirty(item))row.dirtyLoadedObjectCount++',
                         'row.expectedEmissionColor=row.emissionColor.Equals(new Color(1,.76f,.38f)*2.5f)'):
            self.assertIn(required, body)
        self.assertNotIn('throw ', body)
        self.assertNotIn('RequireCorrectedBeaconMaterial(', body)
        self.assertNotIn('SetDirty(', body)
        after = method('VerifyCorrectedTerrainCandidatesAfterCapture')
        self.assertLess(after.index('ReadSavedCorrectedTerrainBindings(report)'), after.index('WriteCorrectedTerrainAuditPhase("postcapture",report)'))
        self.assertEqual(SOURCE.count('WriteCorrectedTerrainAuditPhase("freeze",report);'), 1)
        self.assertEqual(SOURCE.count('WriteCorrectedTerrainAuditPhase("postcapture",report);'), 1)

    def test_evidence_logs_actual_before_after_values_without_changing_report_schema(self):
        finalizer = method('FinalizeCorrectedBeaconEmission')
        for required in ('CORRECTED_BEACON_EMISSION_LIFECYCLE', 'beforeGIFlags=oldFlags',
                         'afterGIFlags=(int)material.globalIlluminationFlags', 'beforeEmissionKeyword=oldKeyword',
                         'afterEmissionKeyword=material.IsKeywordEnabled("_EMISSION")', 'validator=validator',
                         'beforeEmissionColor=oldEmission', 'afterEmissionColor=material.GetColor("_EmissionColor")'):
            self.assertIn(required, finalizer)
        self.assertNotIn('File.Write', SOURCE.split(BEGIN)[1].split(END)[0])

    def test_only_flag_and_emission_keyword_delta_is_permitted(self):
        steady = FIXTURE.replace(b'm_LightmapFlags: 4', b'm_LightmapFlags: 2')
        self.assertEqual(canonical_material(FIXTURE), canonical_material(steady))
        missing = FIXTURE.replace(b'm_ValidKeywords:\n  - _EMISSION', b'm_ValidKeywords: []')
        self.assertEqual(canonical_material(missing), canonical_material(steady))
        for replacement in (b'm_LightmapFlags: 0', b'm_LightmapFlags: 6'):
            self.assertEqual(canonical_material(FIXTURE.replace(b'm_LightmapFlags: 4', replacement)), canonical_material(steady))

    def test_color_alias_shader_queue_version_and_unrecognized_mutations_are_rejected(self):
        for before, after in ((b'r: 2.5', b'r: 0'), (b'_BaseColor:', b'_Color:'),
                              (b'_Smoothness: 0.12', b'_Smoothness: 0.4'),
                              (b'm_CustomRenderQueue: -1', b'm_CustomRenderQueue: 2000'),
                              (b'fixture-only', b'different-shader'), (b'version: 10', b'version: 11'),
                              (b'a: 2.5', b'a: 1'), (b'm_InvalidKeywords: []', b'm_InvalidKeywords: [_OTHER]')):
            with self.subTest(after=after):
                self.assertNotEqual(canonical_material(FIXTURE), canonical_material(FIXTURE.replace(before, after)))
        self.assertNotEqual(canonical_material(FIXTURE), canonical_material(FIXTURE+b'  unknown: 1\n'))

    def test_ambiguous_missing_and_invalid_field_encodings_are_rejected(self):
        for data in (b'', b'x'*65537, FIXTURE+b'  m_LightmapFlags: 4\n',
                     FIXTURE.replace(b'm_LightmapFlags: 4', b'm_LightmapFlags: 8'),
                     FIXTURE.replace(b'm_LightmapFlags: 4', b'badFlags: 4'),
                     FIXTURE.replace(b'  - _EMISSION', b'  - _NORMALMAP'),
                     FIXTURE+b'  m_ValidKeywords: []\n', FIXTURE+b'\xff'):
            with self.subTest(data=data[-50:]), self.assertRaises((ValueError, UnicodeDecodeError)):
                canonical_material(data)

    def test_cameras_and_strict_host_are_unchanged(self):
        expected = {
            'unity/Assets/DesertRV/Tests/EditorRender/JourneyEnvironmentRenderTests.cs':'4a16e5d04dabc2a0ed78dd0be8eb6b4730e2edc9a2a40ac3b0acd20382246858',
            'scripts/environment_v4_r4_evidence.py':'958739e1d1b38bc8916e0e730d43c9f1abf52ba9ba524ffb72848f102cfa8f2f',
            'scripts/environment_v4_r4_audit.py':'80423e814c8dc03d19e875effde1887a5ff4de134c27bb99a3f228c478002923',
            'scripts/environment_image_precheck.py':'c561c6ae5347cd94e64ec5917ee1d4964b46fd5929939c969680f33123cfa1cc',
        }
        for relative, expected_sha in expected.items():
            self.assertEqual(hashlib.sha256((TASK / relative).read_bytes()).hexdigest(), expected_sha, relative)


if __name__ == '__main__':
    unittest.main()
