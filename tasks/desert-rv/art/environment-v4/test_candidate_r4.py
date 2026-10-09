"""Offline source/serialization contract checks only; never Unity compilation or visual acceptance."""
import hashlib
import json
import re
import unittest
from pathlib import Path

TASK=Path(__file__).resolve().parents[2]
PROJECT=TASK/'unity'
EDITOR=PROJECT/'Assets/DesertRV/Editor'
SOURCE=(EDITOR/'JourneySceneAuthoring.CorrectedTerrain.cs').read_text()
NATIVE=PROJECT/'Assets/DesertRV/Tests/EditorRender/JourneyEnvironmentRenderTests.cs'
PINNED={
 'JourneySceneAuthoring.cs':'ced4da08b8447265c14a26b5b63503bb4a08861e5bc5536d1921a4c7e880ee49',
 'JourneySceneAuthoring.EnvironmentPolish.cs':'b829eda4869721b7956cb279b53e0a6b7e1194ef91880c80e2d712110a8366d9',
 'JourneySceneAuthoring.EnvironmentPolishCapture.cs':'fa6cbe1f1252801ec1b0f62b864104d715f781dc01567b50ec82c9a0b30f097e',
 'JourneySceneAuthoring.DiffuseComparison.cs':'57827dce31e1f5cb864cc3214d9833f0e2f44c3355d7bf7daa17c20454a8a53a',
 'JourneySceneAuthoring.TerrainProbe.cs':'e0c8643bd5a399095aad86e49b9929d04e9737385f373e04a35e8208e81b21d1',
}


def method(name):
    declaration=re.search(r'\b(?:public )?static [^\n]+\b'+re.escape(name)+r'\(',SOURCE)
    if declaration is None:raise AssertionError('Missing method '+name)
    start=SOURCE.index('{',declaration.start());depth=0
    # Current methods have no braces inside ordinary string literals except regex in a separate method.
    for index in range(start,len(SOURCE)):
        if SOURCE[index]=='{':depth+=1
        if SOURCE[index]=='}':
            depth-=1
            if depth==0:return SOURCE[start:index+1]
    raise AssertionError('Unterminated method '+name)


class CorrectedCandidateTests(unittest.TestCase):
    def test_historical_authors_and_camera_capture_remain_byte_exact(self):
        for name,expected in PINNED.items():self.assertEqual(hashlib.sha256((EDITOR/name).read_bytes()).hexdigest(),expected,name)
    def test_existing_native_case_has_exactly_two_narrow_changes(self):
        text=NATIVE.read_text();self.assertEqual(text.count('[Test,'),1);self.assertIn('Timeout(600000)',text)
        reverse=text.replace('GetMethod("AuthorAndCaptureCorrectedTerrainCandidates"','GetMethod("AuthorAndCaptureEnvironmentCandidates"')
        added='            type.GetMethod("VerifyCorrectedTerrainCandidatesAfterCapture", BindingFlags.Static | BindingFlags.Public).Invoke(null, null);\n'
        self.assertEqual(reverse.count(added),1);reverse=reverse.replace(added,'')
        self.assertEqual(hashlib.sha256(reverse.encode()).hexdigest(),'f5b8d102ce5debf111805742fa300bf3ded062b02f4d53856e429e057e0097f2')
        self.assertLess(text.index('ValidateOpaqueTerrain();'),text.index('GetMethod("VerifyCorrectedTerrainCandidatesAfterCapture"'))
    def test_pure_author_and_wrapper_do_not_reauthor_or_capture_indirectly(self):
        pure=method('AuthorCorrectedTerrainCandidateScenes')
        self.assertEqual(pure.count('AuthorCandidateScenes();'),1)
        for value in ('CaptureEnvironmentCandidates','AuthorAndCaptureEnvironmentCandidates','RenderPipeline','RenderTexture','CaptureEnvironmentPolishCloseups'):self.assertNotIn(value,pure)
        wrapper=method('AuthorAndCaptureCorrectedTerrainCandidates')
        self.assertEqual(re.sub(r'\s+',' ',wrapper),'{ AuthorCorrectedTerrainCandidateScenes(); JourneyContentChecks.CheckCandidateLayout(); CaptureEnvironmentCandidates(); }')
        self.assertNotRegex(SOURCE,r'static\s+(?:bool|Material|Texture2D)\s+\w+\s*[;=]')
    def test_original_generation_is_normalized_then_frozen_once(self):
        pure=method('AuthorCorrectedTerrainCandidateScenes')
        freeze=pure.index('var before=SnapshotCorrectedTerrainGenerated();')
        self.assertLess(pure.index('AssetDatabase.ImportAsset('),freeze)
        self.assertLess(pure.index('AssetDatabase.SaveAssets();'),freeze)
        self.assertEqual(pure.count('var before='),1)
        self.assertGreater(pure.index('material.SetTexture("_BaseMap",corrected)'),freeze)
    def test_both_albedo_aliases_are_saved_imported_and_byte_stable(self):
        pure=method('AuthorCorrectedTerrainCandidateScenes')
        for value in ('material.SetTexture("_BaseMap",corrected)','material.SetTexture("_MainTex",corrected)',
                      'ForceUpdate|ImportAssetOptions.ForceSynchronousImport','byte[] firstSaved=File.ReadAllBytes(path)',
                      'firstSaved.SequenceEqual(File.ReadAllBytes(path))','saveImportCycles=2,secondSaveImportBytesStable=true'):
            self.assertIn(value,pure)
        self.assertEqual(SOURCE.count('.SetTexture('),2)
        self.assertNotIn('SaveAndReimport',SOURCE)
    def test_full_shader_property_and_exact_serialized_checks(self):
        for value in ('GetPropertyCount()','ShaderPropertyType.Color','ShaderPropertyType.Vector','ShaderPropertyType.Int',
                      'ShaderPropertyType.Float','ShaderPropertyType.Range','ShaderPropertyType.Texture','GetTextureScale(property)',
                      'GetTextureOffset(property)','GetShaderPassEnabled','globalIlluminationFlags','renderQueue','doubleSidedGI',
                      '_(BaseMap|MainTex):','pattern.Matches(text).Count!=2','GetBytes(expected).SequenceEqual(after)'):
            self.assertIn(value,SOURCE)
        self.assertNotIn('AssertDiffuseComparisonMaterial(',SOURCE)
    def test_lifecycle_load_occurs_after_final_scene_transition(self):
        bindings=method('ReadSavedCorrectedTerrainBindings')
        self.assertLess(bindings.index('OpenScene(RegionPaths[region-1]'),bindings.index('LoadVerifiedCorrectedTerrain('))
        self.assertIn('for(int region=1;region<=3;region++)',bindings)
        self.assertIn('terrain.Length!=3',bindings)
        self.assertIn('renderer.sharedMaterial.GetTexture("_MainTex")!=corrected',bindings)
        self.assertIn('renderer.sharedMaterial!=AssetDatabase.LoadAssetAtPath<Material>(materialPath)',bindings)
    def test_postcapture_verification_reopens_and_protects_generated_bytes(self):
        body=method('VerifyCorrectedTerrainCandidatesAfterCapture')
        self.assertEqual(body.count('RequireCorrectedTerrainSavedBytes(report);'),2)
        self.assertIn('ReadSavedCorrectedTerrainBindings(report)',body)
        self.assertIn('images.Length!=20',body)
        self.assertIn('report.postCaptureImageCount=images.Length;report.postCaptureVerified=true',body)
        self.assertIn('VerifyProtectedFiles(protectedFiles)',body)
    def test_texture_and_importer_bytes_are_pinned(self):
        texture=PROJECT/'Assets/DesertRV/Art/TerrainDiffuseCorrection/sand_03_diff_illumination_corrected_1k.png'
        for path,expected in ((texture,'4fe4e4e5745ce34d4f8eb9668e45a5fab1acf7f6c0baa96de45ae15ff98764a3'),
                              (Path(str(texture)+'.meta'),'c90d8b8ae8da299cdd47af43312699c27861d72effc9a493c7b142526bd87dd3')):
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),expected);self.assertIn(expected,SOURCE)
        for value in ('mipmapCount<2','!importer.sRGBTexture','!importer.streamingMipmaps','importer.isReadable',
                      'importer.maxTextureSize!=1024','TextureImporterCompression.Compressed','TextureImporterAlphaSource.None',
                      'FilterMode.Trilinear','TextureWrapMode.Repeat','texture.anisoLevel!=4'):
            self.assertIn(value,SOURCE)
    def test_new_partial_has_unique_meta_guid(self):
        meta=Path(str(EDITOR/'JourneySceneAuthoring.CorrectedTerrain.cs')+'.meta')
        guid=re.search(r'^guid: ([0-9a-f]{32})$',meta.read_text(),re.M).group(1)
        found=[path for path in (PROJECT/'Assets').rglob('*.meta') if f'guid: {guid}\n' in path.read_text(errors='replace')]
        self.assertEqual(found,[meta])
    def test_fixture_is_explicitly_historical_and_not_r4_render_proof(self):
        fixture=json.loads((Path(__file__).parent/'r4-native-yaml-fixture.json').read_text())
        self.assertEqual(fixture['scope'],'VALIDATOR_UNIT_FIXTURE_ONLY_NOT_R4_RENDER_OR_GAMEPLAY_EVIDENCE')
        self.assertEqual(fixture['sourceRun'],'37961223152');self.assertEqual(len(fixture['sceneSources']),3)
        for value in fixture['files'].values():self.assertNotIn('d29d00d5224659788346ab661919f5ee',value)
    def test_generated_contract_not_expanded(self):
        contract=json.loads((Path(__file__).parent/'generated-contract.json').read_text())
        self.assertEqual(len(contract['files']),121);self.assertEqual(len(contract['metadata_files']),122)
        self.assertIn('changed.SequenceEqual(CorrectedTerrainMaterials.OrderBy',SOURCE)
        for forbidden in ('AssetDatabase.CreateAsset','SaveScene(','File.WriteAllBytes','new Mesh(','new GameObject(','new Light('):self.assertNotIn(forbidden,SOURCE)

if __name__=='__main__':unittest.main()
