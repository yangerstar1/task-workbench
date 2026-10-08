"""Static regression guards only; never substitute for Unity compilation/runtime tests."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]/'unity/Assets/DesertRV/Editor'
CAPTURE=(ROOT/'JourneyCandidateArtCapture.cs').read_text()
IMPORT=(ROOT/'JourneyCandidateArtImport.cs').read_text()
class CaptureSourceTests(unittest.TestCase):
    def test_urp_request_not_legacy_render(self):
        self.assertNotIn('camera.Render()',CAPTURE)
        for text in ['UniversalRenderPipeline.SingleCameraRequest','RenderPipeline.SupportsRenderRequest','RenderPipeline.SubmitRenderRequest']: self.assertIn(text,CAPTURE)
    def test_explicit_pose_expectations(self):
        self.assertIn('s.poseExpectation=="held" || s.poseExpectation=="varying"',IMPORT)
        self.assertIn('poseExpectation=="varying"',CAPTURE)
        self.assertNotIn('Select(f=>f.imageSha256).Distinct()',CAPTURE)
    def test_deformed_mesh_diagnostics(self):
        for text in ['skin.BakeMesh(temporary,false)','mesh.vertices','WorldToViewportPoint','worldMinY','belowReferenceVertices','groundDiagnosticApplicable=contract.kind!="weapon"']: self.assertIn(text,CAPTURE)
    def test_cleanup_after_report_write(self):
        tail=CAPTURE[CAPTURE.index('try { File.WriteAllText("JourneyEvidence/CandidateArt/capture-report.json"'):]
        self.assertGreaterEqual(tail.count('finally'),5)
        self.assertIn('EditorSceneManager.ClosePreviewScene(scene)',tail)
    def test_real_shared_contract(self):
        for text in ['NailRigOwnership.ValidateLoaded','NailRigOwnership.Validate(','WeakPointContractChecks.Validate']: self.assertIn(text,IMPORT)
    def test_muzzle_gate_never_guesses_forward_or_creates_flash(self):
        self.assertIn('sourceBoneLocalForwardAxis = "+Y"',IMPORT)
        self.assertIn('calibratedForScene = false',IMPORT)
        self.assertIn('p.muzzleFlash=null',IMPORT)
        self.assertNotIn('AddComponent<ParticleSystem>',IMPORT)
    def test_stable_new_source_folder_meta(self):
        path=ROOT.parent/'Tests/CandidateArt.meta'
        self.assertIn('folderAsset: yes',path.read_text())
    def test_discovery_is_not_prefab_binding(self):
        discovery=(ROOT/'JourneyCandidateArtDiscovery.cs').read_text()
        for forbidden in ['SaveAsPrefabAsset','AnimatorController.Create','AddComponent<','accepted=true']:
            self.assertNotIn(forbidden,discovery)
        for required in ['DISCOVERY_ONLY','CandidateArtDiscovery/','defaultClipAnimations','mesh.bindposes','DEATH_DIAGNOSTIC_NOT_FULL']:
            self.assertIn(required,discovery)
        self.assertIn('c.scope=="FULL_CANDIDATE"',IMPORT)
    def test_missing_native_animator_uses_unity_object_boolean(self):
        self.assertNotIn('GetComponent<Animator>() ??',IMPORT)
        self.assertIn('if(!animator)animator=root.gameObject.AddComponent<Animator>();',IMPORT)
        self.assertIn('var animator=EnsureNativeAnimator(animatorRoot); animator.applyRootMotion=false;',IMPORT)
    def test_open_emission_is_persisted_with_urp_gi_flags(self):
        self.assertIn('MaterialGlobalIlluminationFlags.BakedEmissive',IMPORT)
        self.assertIn('MaterialEditor.FixupEmissiveFlag(open)',IMPORT)
        self.assertIn('ForceUpdate|ImportAssetOptions.ForceSynchronousImport',IMPORT)
        self.assertIn('persisted.IsKeywordEnabled("_EMISSION")',IMPORT)
    def test_no_approval_or_production_scene_write(self):
        for source in [CAPTURE,IMPORT]:
            self.assertNotIn('accepted=true',source)
            self.assertNotIn('SaveScene(',source)
            self.assertNotIn('BuildPipeline.BuildPlayer',source)
if __name__=='__main__':unittest.main()
