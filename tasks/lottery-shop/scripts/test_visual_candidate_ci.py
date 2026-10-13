#!/usr/bin/env python3
"""Synthetic validator tests, never native rendering or gameplay evidence."""
import copy
import re
import unittest
import json
import os
from pathlib import Path
import subprocess
import tempfile
import hashlib
import shutil
import struct
import zlib
from unittest.mock import patch
import xml.etree.ElementTree as ET
import visual_candidate_ci as candidate


def receipt():
    frames = []
    for name in candidate.FRAMES:
        frames.append(dict(stateOrigin="REAL_SERVICE_TRANSACTIONS",navigationEvidence="SCENARIO_SETUP_NOT_WORLD_INPUT",cameraOrigin=candidate.FRAME_CAMERA_ORIGINS[name],stage=name, file=name + ".png", sha256="a" * 64,
            width=1600 if name.endswith("20x9") else 1280, height=720,
            stateSha256="b" * 64, seedSha256="c" * 64, hudVisible=True, hudFits=True,
            cameraOrthographic=False, hudFrustumRendererCount=20, importedRendererCount=200, inputUpdates=123,
            cameraPosition=dict(x=1, y=2, z=3), cameraEuler=dict(x=60, y=180, z=0), cameraFov=64, dayPhase="NIGHT_BILL" if name == "night-table" else "DAY_OPEN",
            panel="None", hudOpaqueAreaRatio=.18, visibleControlIds=["open-settings", "stand"], moreVisible=False, paperVisible=True, renderedShopRendererCount=32, renderedShopMaterialCount=31, paperPresentationBounds=dict(x=300,y=200,width=600,height=400), toolPresentationBounds=[dict(x=400+i*100,y=510,width=60,height=80) for i in range(3)], currentTools=["small_prize_box", "inspection_lamp", "large_prize_stamp"], revealedCells=3))
    for f in frames:
        name = f["stage"]
        f.update(ticketId="fixed-ticket", ticketPhase="ACTIVE", ticketMaskSha256="d"*64, ticketContentSha256="f"*64,
                 nextTools=["small_prize_box", "inspection_lamp", "large_prize_stamp"],
                 phoneFocused=name in ("phone-contacts", "phone-mom-pending", "phone-mom-claimed"),
                 phoneFrustumRendererCount=10, phoneWorldObjectActive=True, phoneActiveRendererCount=10, phoneInstanceId=42, phoneScreenMinDepth=1, phoneScreenMaxDepth=1.2, phonePlaneCameraAbsCosine=.9, phoneScreenBounds=dict(x=500,y=200,width=150,height=300),
                 cashMinor=30000, motherDebtMinor=0, motherLifetimeMinor=0, loanCount=0, ledgerCount=0, phoneEventCount=0)
        if name == "phone-mom-pending": f.update(stateSha256="d"*64, phoneEventCount=1)
        if name in ("phone-mom-claimed", "phone-table-return"):
            f.update(stateSha256="e"*64, cashMinor=40000, motherDebtMinor=10000, motherLifetimeMinor=10000, loanCount=1, ledgerCount=1, phoneEventCount=2)
    for f in frames:
        if f["stage"] not in candidate.EXTERIOR_FRAMES: continue
        night=f["stage"] in candidate.EXTERIOR_NIGHT_FRAMES
        station=f["stage"].removeprefix("exterior-night-" if night else "exterior-day-")
        position,angles=candidate.EXTERIOR_STATIONS[station]
        f.update(cameraOrigin="FIXTURE_VIEW_NOT_WALKED",cameraPosition=dict(zip(("x","y","z"),position)),cameraEuler=dict(zip(("x","y","z"),angles)),
            dayPhase="NIGHT_BILL" if night else "CLOSING_PREP",fixturePoseRestored=True,fixtureStateBefore=f["stateSha256"],fixtureStateAfter=f["stateSha256"],sha256=("b" if night else "a")*64,
            exterior=dict(basis="MATERIAL_METADATA_NOT_PIXEL_ACCEPTANCE",backdropShader="Lottery/G3/ExteriorBackdrop",textureName="Street-night" if night else "Street-day",
                textureWidth=1882 if night else 1881,textureHeight=836,exposure=.72 if night else 1,backdropRendererCount=1,backdropFrustumRendererCount=1,glassFrustumRendererCount=1,
                transparentGlassMaterialCount=1,glassAlpha=.5,glassSurface=1,glassZWrite=0,glassRenderQueue=3000,nearFieldTriangles=60,nearFieldColliderCount=0,feltNormalScale=.6,linerSmoothness=.08,brassSmoothness=1))
    return dict(schemaVersion=5, candidatePresentation="V31_SCENARIO_STATE_VIEWS_NOT_WORLD_INPUT_PASS", scope=candidate.SCOPE, sourceCommit="1" * 40, runId="12345", runAttempt="1", unityVersion="6000.3.19f1",
                graphicsDeviceType="OpenGLCore", inputEvidence="SIMULATED_UI_INPUT_WITH_DECLARED_SCENARIO_SETUP",
                captureMethod="URP_STANDARD_REQUEST_READPIXELS", hudVisibilityBasis="ENABLED_CAMERA_LAYER_AND_FRUSTUM_TEST_NOT_PIXEL_OCCLUSION", complete=True, frames=frames, actions=[])


def progress_receipt(kind="runtime"):
    value = dict(schemaVersion=1, scope=candidate.SCOPE, kind=kind, sourceCommit="1" * 40, runId="12345", runAttempt="1",
                status="MILESTONES_ONLY_NOT_TEST_PASS", events=[dict(stage="runtime-setup-begin" if kind == "runtime" else "prebuild-begin",
                utc="2026-10-13T03:00:00.0000000Z", elapsedMs=0, inputUpdates=0, frameCount=0, purchased=-1, settled=-1, dayPhase="UNAVAILABLE")])
    if kind=="runtime":value.update(tickFrequency=1000000000,costs=[dict(values=[0]*11)])
    return value


class ProgressReceiptTests(unittest.TestCase):
    def validate(self, value, kind="runtime"):
        return candidate.validate_progress(value, kind, "1" * 40, "12345", "1")

    def test_runtime_and_prebuild_milestones_are_observations_only(self):
        self.validate(progress_receipt()); self.validate(progress_receipt("prebuild"), "prebuild")

    def test_fixed_prebuild_substeps_and_guard_enums_are_bounded(self):
        self.assertEqual(len(candidate.PREBUILD_DETAIL_STAGES), 20)
        self.assertEqual(sum(s.startswith("prebuild-guard-failed-") for s in candidate.PREBUILD_DETAIL_STAGES), 12)
        for stage in candidate.PREBUILD_DETAIL_STAGES:
            value = progress_receipt("prebuild")
            value["events"].append(dict(value["events"][0], stage=stage, elapsedMs=10))
            self.validate(value, "prebuild")
        for stage in ("prebuild-guard-failed-new-arbitrary-code", "prebuild-prepare-failed:raw exception body"):
            value = progress_receipt("prebuild"); value["events"].append(dict(value["events"][0], stage=stage, elapsedMs=10))
            with self.assertRaises(ValueError): self.validate(value, "prebuild")
        value = progress_receipt("prebuild"); value["events"][0]["exception"] = "not an allowed field"
        with self.assertRaises(ValueError): self.validate(value, "prebuild")

    def test_fixed_lifecycle_stages_accept_no_arbitrary_payload(self):
        value = progress_receipt("prebuild"); value["kind"] = "lifecycle"; value["events"][0]["stage"] = "editor-exiting-edit-mode"
        candidate.validate_progress(value, "lifecycle", "1" * 40, "12345", "1")
        value["events"][0]["sceneName"] = "not an allowed field"
        with self.assertRaises(ValueError): candidate.validate_progress(value, "lifecycle", "1" * 40, "12345", "1")

    def test_missing_progress_is_not_fabricated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(candidate, "identity", return_value=dict(sourceCommit="1" * 40, runId="12345", runAttempt="1")):
                candidate.export_progress(root)
            self.assertFalse(candidate.outdir(root).exists())

    def test_progress_export_only_fixed_named_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); folder = root / candidate.TASK / "artifacts/visual-candidate"
            candidate.write(folder / "runtime-progress.json", progress_receipt())
            (folder / "Unity.log").write_text("synthetic unrelated file must not be exported")
            with patch.object(candidate, "identity", return_value=dict(sourceCommit="1" * 40, runId="12345", runAttempt="1")):
                candidate.export_progress(root)
            self.assertEqual([x.name for x in candidate.outdir(root).iterdir()], ["runtime-progress.json"])

    def test_progress_run_attempt_source_and_kind_must_match(self):
        for key, wrong in (("runAttempt", "2"), ("runId", "99999"), ("sourceCommit", "2" * 40), ("kind", "prebuild")):
            value = progress_receipt(); value[key] = wrong
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)

    def test_progress_refuses_arbitrary_text_fields_or_unknown_stages(self):
        for event_key, value in (("exception", "not allowed"), ("stage", "arbitrary log text"), ("dayPhase", "arbitrary phase")):
            receipt = progress_receipt(); receipt["events"][0][event_key] = value
            with self.subTest(key=event_key), self.assertRaises(ValueError): self.validate(receipt)
        value = progress_receipt(); value["rawLog"] = "not allowed"
        with self.assertRaises(ValueError): self.validate(value)

    def test_progress_bounds_and_clock_are_strict(self):
        value = progress_receipt(); value["events"] *= 129
        with self.assertRaises(ValueError): self.validate(value)
        value = progress_receipt(); value["events"].append(dict(value["events"][0], elapsedMs=-1))
        with self.assertRaises(ValueError): self.validate(value)
        for key, wrong in (("elapsedMs", -1), ("inputUpdates", True), ("frameCount", len(candidate.FRAMES)+1), ("purchased", 13), ("settled", -2), ("utc", "not-a-date")):
            value = progress_receipt(); value["events"][0][key] = wrong
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)

    def test_timeout_milestone_never_claims_pass(self):
        value = progress_receipt(); value["events"].append(dict(value["events"][0], stage="runtime-timeout", elapsedMs=900001)); value["costs"].append(dict(values=[0]*11))
        self.validate(value)
        value["status"] = "PASS"
        with self.assertRaises(ValueError): self.validate(value)

    def test_fixture_loop_and_ci_backstop_remain_bounded_static(self):
        root = Path(__file__).resolve().parents[3]
        source = (root / candidate.TASK / "unity/Assets/G3/Tests/VisualCandidate/VisualCandidateCaptureTests.cs").read_text()
        self.assertNotIn("while(State.TicketsPurchasedToday", source)
        self.assertIn("for(int index = 0; index < remaining; index++)", source)
        loop = source.split("for(int index = 0; index < remaining; index++)", 1)[1].split("Assert.That(State.TicketsPurchasedToday", 1)[0]
        self.assertIn("yield return null;", loop)
        self.assertIn('Assert.That(remaining, Is.InRange(0, 12)', source)
        for text in ("State.TicketsPurchasedToday, Is.EqualTo(12)", "State.SettledTicketCount, Is.EqualTo(12)", "State.Phase, Is.EqualTo(DayPhase.CLOSING_PREP)", "frame < 600", "Is.LessThan(UnloadSeconds)"):
            self.assertIn(text, source)
        workflow = (root / candidate.WORKFLOW).read_text()
        self.assertIn("timeout-minutes: 32", workflow)
        self.assertIn("timeout-minutes: 75", workflow)


class PreparationSceneReceiptTests(unittest.TestCase):
    def receipt(self):
        return dict(schemaVersion=1, scope=candidate.SCOPE, sourceCommit="1" * 40, runId="12345", runAttempt="1", status="MILESTONES_ONLY_NOT_TEST_PASS",
                    observations=[dict(stageCode=code, elapsedMs=i * 10, sceneValid=True, isLoaded=True, activeMatches=i % 3 == 1,
                                       activationAttempted=False, activationReturned=False) for i, code in enumerate((10, 11, 12, 20, 21, 22))])
    def validate(self, value): return candidate.validate_preparation_scenes(value, "1" * 40, "12345", "1")

    def test_fixed_complete_and_early_failure_observations_do_not_imply_pass(self):
        value = self.receipt(); self.validate(value)
        value["observations"] = [value["observations"][0], value["observations"][2]]
        value["observations"][0]["sceneValid"] = False; self.validate(value)
        value["status"] = "PASS"
        with self.assertRaises(ValueError): self.validate(value)
        value = self.receipt(); value["schemaVersion"] = True
        with self.assertRaises(ValueError): self.validate(value)

    def test_already_active_observation_is_retained_without_attempt_or_pass(self):
        value = self.receipt(); value["observations"] = value["observations"][:2]
        for observed in value["observations"]:
            observed.update(activeMatches=True, activationAttempted=False, activationReturned=False)
        self.assertEqual(self.validate(value), value)
        value["status"] = "PASS"
        with self.assertRaises(ValueError): self.validate(value)

    def test_false_activation_return_with_true_postcondition_is_observation_only(self):
        value = self.receipt(); value["observations"] = value["observations"][:2]
        value["observations"][1].update(activeMatches=True, activationAttempted=True, activationReturned=False)
        self.assertEqual(self.validate(value), value)
        value["status"] = "PASS"
        with self.assertRaises(ValueError): self.validate(value)

    def test_true_activation_return_with_false_postcondition_is_preserved_failure_data(self):
        value = self.receipt(); value["observations"] = value["observations"][:2]
        value["observations"][1].update(activeMatches=False, activationAttempted=True, activationReturned=True)
        # A failed native postcondition must remain exportable as diagnostic data.
        # Receipt validation never executes Unity or decides the NUnit verdict.
        self.assertEqual(self.validate(value), value)
        value["status"] = "PASS"
        with self.assertRaises(ValueError): self.validate(value)

    def test_wrong_scene_source_run_or_attempt_rejected(self):
        for field, wrong in (("sourceCommit", "2" * 40), ("runId", "987"), ("runAttempt", "2")):
            value = self.receipt(); value[field] = wrong
            with self.subTest(field=field), self.assertRaises(ValueError): self.validate(value)

    def test_scene_observation_unknown_fields_codes_duplicates_and_overflow_rejected(self):
        for field, wrong in (("sceneName", "not permitted"), ("stageCode", 99), ("sceneValid", 1), ("elapsedMs", -1)):
            value = self.receipt(); value["observations"][0][field] = wrong
            with self.subTest(field=field), self.assertRaises(ValueError): self.validate(value)
        value = self.receipt(); value["observations"][1]["stageCode"] = 10
        with self.assertRaises(ValueError): self.validate(value)
        value = self.receipt(); value["observations"][2]["elapsedMs"] = 5
        with self.assertRaises(ValueError): self.validate(value)
        value = self.receipt(); value["observations"].append(value["observations"][-1])
        with self.assertRaises(ValueError): self.validate(value)

    def test_scene_export_exact_filename_and_16kib_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); folder = root / candidate.TASK / "artifacts/visual-candidate"
            candidate.write(folder / "preparation-scenes.json", self.receipt())
            (folder / "other-scenes.json").write_text("unrelated")
            ident = dict(sourceCommit="1" * 40, runId="12345", runAttempt="1")
            with patch.object(candidate, "identity", return_value=ident): candidate.export_progress(root)
            self.assertEqual([x.name for x in candidate.outdir(root).iterdir()], ["preparation-scenes.json"])
            (folder / "preparation-scenes.json").write_text(" " * 16385)
            with patch.object(candidate, "identity", return_value=ident), self.assertRaises(ValueError): candidate.export_progress(root)


class PreparationSourceContractTests(unittest.TestCase):
    """Narrow source-shape checks with negative mutations, not C# execution."""
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[3] / candidate.TASK / "unity/Assets"
        cls.probe = (root / "Editor/ProbeBuild.cs").read_text()
        cls.g3 = (root / "G3/Editor/G3Build.cs").read_text()
        cls.fixture = (root / "G3/Tests/VisualCandidate/VisualCandidateCaptureTests.cs").read_text()

    @staticmethod
    def compact(source):
        return re.sub(r"\s+", "", re.sub(r"//[^\n]*", "", source))

    def require_active_contract(self, source):
        body = self.compact(source.split("public static void RequirePreparedSceneActive", 1)[1].split("public static void RestorePreparedScene", 1)[0])
        self.assertIn("boolattempted=!active,returned=false;", body)
        self.assertEqual(body.count("SceneManager.SetActiveScene(scene)"), 1)
        self.assertIn("if(attempted)returned=SceneManager.SetActiveScene(scene);", body)
        after_call = body.split("SceneManager.SetActiveScene(scene);", 1)[1]
        ordered = ("valid=scene.IsValid();loaded=valid&&scene.isLoaded;",
                   "active=valid&&loaded&&SceneManager.GetActiveScene().handle==scene.handle;",
                   "observe?.Invoke(stageCode+1,valid,loaded,active,attempted,returned);",
                   "if(!active)thrownewInvalidOperationException(")
        previous = -1
        for token in ordered:
            position = after_call.find(token); self.assertGreater(position, previous, token); previous = position
        self.assertNotIn("if(!returned)", body)

    def test_active_postcondition_static_contract_rejects_three_branch_regressions(self):
        self.require_active_contract(self.probe)
        mutations = (("attempted=!active", "attempted=true"),
                     ("if(!active)throw", "if(!returned)throw"),
                     ("active=valid&&loaded&&SceneManager.GetActiveScene().handle==scene.handle;\n            observe?.Invoke(stageCode+1", "active=returned;\n            observe?.Invoke(stageCode+1"))
        for old, new in mutations:
            changed = self.probe.replace(old, new, 1); self.assertNotEqual(changed, self.probe)
            with self.subTest(mutation=old), self.assertRaises(AssertionError): self.require_active_contract(changed)

    def require_exception_contract(self, source):
        helper = self.compact(source.split("public static void RunPreparationWithCleanup", 1)[1].split("public static void BuildAndroid", 1)[0])
        self.assertIn("try{operation();}catch(Exceptionerror){operationFailure=error;}", helper)
        self.assertIn("finally{try{cleanup();}catch(Exceptionerror){cleanupFailure=error;}}", helper)
        self.assertIn('if(operationFailure!=null&&cleanupFailure!=null)thrownewAggregateException("Preparationandcleanupbothfailed",operationFailure,cleanupFailure);', helper)
        for failure in ("operationFailure", "cleanupFailure"):
            self.assertIn("if(" + failure + "!=null)System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(" + failure + ").Throw();", helper)

    def test_body_and_cleanup_failures_static_contract_rejects_overwrite_or_swallow(self):
        self.require_exception_contract(self.probe)
        for old, new in ((",operationFailure,cleanupFailure)", ",cleanupFailure)"),
                         ("cleanupFailure=error;", "cleanupFailure=null;"),
                         ("Capture(operationFailure).Throw();", "Capture(operationFailure);")):
            changed = self.probe.replace(old, new, 1); self.assertNotEqual(changed, self.probe)
            with self.subTest(mutation=old), self.assertRaises(AssertionError): self.require_exception_contract(changed)

    def require_restore_contract(self, source):
        body = self.compact(source.split("public static void RestorePreparedScene", 1)[1].split("public static void RunPreparationWithCleanup", 1)[0])
        self.assertEqual(body.count("RunPreparationWithCleanup("), 2)
        self.assertIn("RunPreparationWithCleanup(()=>RunPreparationWithCleanup(", body)
        self.assertIn("if(ownedScene.IsValid()&&ownedScene.isLoaded)EditorSceneManager.CloseScene(ownedScene,true);}),()=>{", body)
        self.assertIn("boolvalid=priorScene.IsValid(),loaded=valid&&priorScene.isLoaded;boolactive=valid&&loaded&&SceneManager.GetActiveScene().handle==priorScene.handle;", body)
        self.assertIn('observe?.Invoke(stageCode,valid,loaded,active,attempted,returned);if(!active)thrownewInvalidOperationException(', body)

    def test_restore_close_and_final_observation_static_chain_rejects_dropped_cleanup(self):
        self.require_restore_contract(self.probe)
        for old, new in (("() => RunPreparationWithCleanup(", "() => UnprotectedSequence("),
                         ("EditorSceneManager.CloseScene(ownedScene,true)", "EditorSceneManager.CloseScene(priorScene,true)"),
                         ("active=valid&&loaded&&SceneManager.GetActiveScene().handle==priorScene.handle;", "active=returned;")):
            changed = self.probe.replace(old, new, 1); self.assertNotEqual(changed, self.probe)
            with self.subTest(mutation=old), self.assertRaises(AssertionError): self.require_restore_contract(changed)

    def test_both_preparation_bodies_and_outer_scene_guard_keep_cleanup_chain_static(self):
        probe, g3, fixture = map(self.compact, (self.probe, self.g3, self.fixture))
        self.assertIn("RunPreparationWithCleanup(build,()=>RestorePreparedScene(priorScene,scene,12,observe));", probe)
        self.assertIn("RunPreparationWithCleanup(build,()=>Lottery.Probe.Editor.ProbeBuild.RestorePreparedScene(priorScene,scene,22,observe));", g3)
        self.assertIn('finally{DiagnosticMark(progress,"prebuild-guard-verify-begin",errors);try{guard.RequireUnchanged();', fixture)
        self.assertIn('if(errors.Count>1)thrownewAggregateException("Prebuildfailedinmultipleguardedphases",errors);', fixture)


class VisualCandidateEvidenceTests(unittest.TestCase):
    def validate(self, value, complete=True):
        return candidate.validate_capture(value, "1" * 40, "12345", "1", complete)

    def test_synthetic_complete_shape(self):
        self.assertEqual(len(self.validate(receipt())), 23)

    def test_exterior_missing_any_of_six_frames_is_rejected(self):
        self.assertEqual([n for n in candidate.FRAMES if n not in candidate.EXTERIOR_FRAMES], candidate.ORIGINAL_VISUAL_FRAMES)
        self.assertEqual(len(candidate.ORIGINAL_VISUAL_FRAMES),17)
        for name in candidate.EXTERIOR_FRAMES:
            value=receipt();value["frames"]=[f for f in value["frames"] if f["stage"]!=name]
            with self.subTest(name=name),self.assertRaises(ValueError):self.validate(value)

    def test_exterior_wrong_day_fake_restore_or_walk_claim_rejected(self):
        for name in candidate.EXTERIOR_FRAMES:
            for key,bad in (("dayPhase","DAY_OPEN"),("fixturePoseRestored",False),("fixtureStateAfter","f"*64),("cameraOrigin","KEYBOARD_TRAVERSED_PLAYER_VIEW"),("panel","Bill"),("phoneFocused",True)):
                value=receipt();next(f for f in value["frames"] if f["stage"]==name)[key]=bad
                with self.subTest(name=name,key=key),self.assertRaises(ValueError):self.validate(value)

    def test_exterior_opaque_glass_wrong_texture_and_materials_rejected(self):
        for key,bad in (("textureName","Street-day"),("glassAlpha",1),("glassSurface",0),("glassZWrite",1),("glassRenderQueue",2000),("exposure",1),("nearFieldTriangles",0),("nearFieldColliderCount",1),("backdropRendererCount",2),("glassFrustumRendererCount",0),("feltNormalScale",.28),("linerSmoothness",.5),("brassSmoothness",.73),("brassSmoothness",.66),("basis","PIXEL_PASS")):
            value=receipt();next(f for f in value["frames"] if f["stage"]==candidate.EXTERIOR_NIGHT_FRAMES[0])["exterior"][key]=bad
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(value)

    def test_exterior_camera_and_production_state_pairing_rejected(self):
        for key,bad in (("cameraPosition",dict(x=0,y=1.58,z=0)),("cameraFov",90),("sha256","a"*64),("stateSha256","e"*64)):
            value=receipt();next(f for f in value["frames"] if f["stage"]==candidate.EXTERIOR_NIGHT_FRAMES[0])[key]=bad
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(value)

    def test_exterior_fixture_source_and_workflow_do_not_bypass_production(self):
        root=Path(__file__).resolve().parents[3]
        source=(root / candidate.TASK / "unity/Assets/G3/Tests/VisualCandidate/VisualCandidateCaptureTests.cs").read_text()
        body=source.split("IEnumerator ExteriorFixtureViews(bool isNight)",1)[1].split("ExteriorReceipt ExteriorMetadata",1)[0]
        self.assertNotIn("SetNight(",body)
        self.assertIn("Physics.OverlapCapsule",body)
        self.assertIn('"FIXTURE_VIEW_NOT_WALKED"',body)
        self.assertIn("finally",body)
        for text in ("P.Walking, Is.EqualTo(walking)","P.View.Phone.IsFocused, Is.EqualTo(phoneFocused)","P.View.Walk.SavedPosition, Is.EqualTo(walkPosition)","StateCodec.ComputeHash(State), Is.EqualTo(hash)"):
            self.assertIn(text,body)
        self.assertIn('Capture("closing-day-table", "NORMAL_SEATED_PLAYER_VIEW");\n            yield return ExteriorFixtureViews(false);',source)
        self.assertIn('Capture("night-table", "SAME_CAMERA_AS_CLOSING_DAY_WITH_BILL_CLOSED");\n            yield return ExteriorFixtureViews(true);',source)
        workflow=(root / ".github/workflows/lottery-visual-candidate.yml").read_text()
        for name in candidate.EXTERIOR_FRAMES:self.assertEqual(workflow.count('/captures/'+name+'.png'),1)

    def test_missing_six_group_evidence_is_not_complete(self):
        value = receipt(); value["frames"].pop()
        with self.assertRaises(ValueError): self.validate(value)

    def test_valid_partial_is_preserved_but_never_complete(self):
        value = receipt(); value["complete"] = False; value["frames"] = value["frames"][:3]
        self.assertEqual(len(self.validate(value, False)), 3)
        with self.assertRaises(ValueError): self.validate(value)

    def test_old_source_cannot_be_relabelled(self):
        value = receipt(); value["sourceCommit"] = "2" * 40
        with self.assertRaises(ValueError): self.validate(value)

    def test_other_attempt_cannot_be_mixed(self):
        value = receipt(); value["runAttempt"] = "2"
        with self.assertRaises(ValueError): self.validate(value)

    def test_fake_capture_or_null_gpu_is_rejected(self):
        for key, bad in (("captureMethod", "BLENDER"), ("graphicsDeviceType", "Null"), ("scope", "G3_PASS"), ("unityVersion", "6000.0.1f1")):
            value = receipt(); value[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)

    def test_hidden_hud_or_non_native_framing_is_rejected(self):
        for key, bad in (("hudVisible", False), ("hudFits", False), ("cameraOrthographic", True), ("inputUpdates", 0), ("importedRendererCount", 0), ("width", 1920)):
            value = receipt(); value["frames"][0][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)

    def test_shelf_and_return_must_preserve_ticket(self):
        value = receipt(); next(f for f in value["frames"] if f["stage"] == "shelf-after-open")["stateSha256"] = "d" * 64
        with self.assertRaises(ValueError): self.validate(value)

    def test_day_night_must_use_same_camera(self):
        value = receipt(); next(f for f in value["frames"] if f["stage"] == "night-table")["cameraPosition"]["x"] = 8
        with self.assertRaises(ValueError): self.validate(value)

    def test_same_position_different_rotation_or_fov_is_rejected(self):
        for key, bad in (("cameraEuler", dict(x=0, y=0, z=0)), ("cameraFov", 90)):
            value = receipt(); next(f for f in value["frames"] if f["stage"] == "night-table")[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)

    def test_aspect_pair_and_seed_cannot_be_mixed(self):
        for key in ("stateSha256", "seedSha256"):
            value = receipt(); value["frames"][3][key] = "d" * 64
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)

    def test_night_must_be_real_phase_with_closed_bill(self):
        for key, bad in (("dayPhase", "DAY_OPEN"), ("panel", "Bill")):
            value = receipt(); next(f for f in value["frames"] if f["stage"] == "night-table")[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)

    def test_measured_layout_fields_are_required_without_art_pass_threshold(self):
        value = receipt(); value["frames"][0]["hudOpaqueAreaRatio"] = .9
        self.assertEqual(len(self.validate(value)), 23)
        for bad in (None, -1, float("inf"), 1.1):
            value = receipt(); value["frames"][0]["hudOpaqueAreaRatio"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError): self.validate(value)

    def test_missing_or_nonfinite_paper_tool_projections_rejected(self):
        for key, bad in (("paperPresentationBounds", None), ("toolPresentationBounds", [])):
            value = receipt(); value["frames"][0][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)

    def test_no_unlisted_output_paths(self):
        value = receipt(); value["frames"][0]["file"] = "../../../ProjectSettings/ProjectSettings.asset"
        with self.assertRaises(ValueError): self.validate(value)

    def test_duplicate_captures_rejected(self):
        value = receipt(); value["frames"].append(copy.deepcopy(value["frames"][0]))
        with self.assertRaises(ValueError): self.validate(value)


class NativeReportShapeTests(unittest.TestCase):
    def test_v2_contract_has_331_edit_and_37_play_with_phone_coverage(self):
        task = Path(candidate.__file__).resolve().parents[1]
        contracts = [json.loads((task / "ci" / (name + "-test-contract.json")).read_text()) for name in ("g2", "g3")]
        source = (task / "unity/Assets/G3/Tests/EditMode/PhoneLoanTests.cs").read_text()
        ordinary = re.findall(r"\[Test\]\s*public void (\w+)\(", source)
        self.assertEqual(len(ordinary), 8)
        phone_edit = {"Lottery.G3.EditMode.Tests.PhoneLoanTests." + name for name in ordinary}
        phone_edit |= {"Lottery.G3.EditMode.Tests.PhoneLoanTests.PhoneAtomic_" + action + "_" + point + "_" + mode
                       for action in ("Request", "Claim", "Cancel")
                       for point in ("BeforeWrite", "TempHalfWritten", "TempFlushed", "BeforePublish", "AfterPublish", "BeforeResponse")
                       for mode in ("cold", "live")}
        interaction = (task / "unity/Assets/G3/Tests/PlayMode/G3PhoneInteractionTests.cs").read_text()
        phone_play = {"Lottery.G3.PlayMode.Tests.G3PlayTests." + method for method in re.findall(r"\[UnityTest\]\s*public IEnumerator (\w+)\(", interaction)}
        self.assertEqual(len(phone_edit), 44); self.assertEqual(len(phone_play), 3)
        for stage, original_count, additional in (("edit", 287, phone_edit), ("play", 34, phone_play)):
            names = {case for contract in contracts for cases in contract["profiles"][stage].values() for case in cases}
            self.assertTrue(additional <= names)
            self.assertEqual(len(names - additional), original_count, "V2 exact local/world case split plus phone identities is required")
            self.assertEqual(len(names), original_count + len(additional))

    def test_original_candidate_report_is_preserved_and_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output = candidate.outdir(root)
            candidate.write(output / "source-receipt.json", dict(scope=candidate.SCOPE, sourceCommit="1"*40))
            folder = root / candidate.TASK / "artifacts/visual-candidate"; folder.mkdir(parents=True)
            report = ET.Element("test-run", result="Passed", total="1", passed="1", failed="0", skipped="0", inconclusive="0")
            suite = ET.SubElement(report, "test-suite", type="Assembly", name=candidate.ASSEMBLY, result="Passed")
            ET.SubElement(suite, "test-case", fullname=candidate.CASE, result="Passed")
            original = ET.tostring(report); (folder / "results.xml").write_bytes(original)
            with patch.dict(os.environ, GITHUB_SHA="1"*40): candidate.export_tests(root, "capture")
            self.assertEqual((output / "capture/raw-test-results.xml").read_bytes(), original)
            report = json.loads((output / "capture/test-receipt.json").read_text())
            self.assertTrue(report["allExpectedPassed"])
            self.assertEqual(report["scope"], candidate.SCOPE)

    def test_bad_native_report_is_not_passing_but_retains_safe_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output = candidate.outdir(root)
            candidate.write(output / "source-receipt.json", dict(scope=candidate.SCOPE, sourceCommit="1"*40))
            folder = root / candidate.TASK / "artifacts/visual-candidate"; folder.mkdir(parents=True)
            report = ET.Element("test-run", result="Failed", total="1", passed="0", failed="1", skipped="0", inconclusive="0")
            suite = ET.SubElement(report, "test-suite", type="Assembly", name=candidate.ASSEMBLY, result="Failed")
            ET.SubElement(suite, "test-case", fullname=candidate.CASE, result="Failed")
            original = ET.tostring(report); (folder / "results.xml").write_bytes(original)
            with patch.dict(os.environ, GITHUB_SHA="1"*40), self.assertRaises(ValueError): candidate.export_tests(root, "capture")
            self.assertEqual((output / "capture/raw-test-results.xml").read_bytes(), original)

    def test_duplicate_empty_assemblies_or_orphan_case_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output = candidate.outdir(root)
            candidate.write(output / "source-receipt.json", dict(scope=candidate.SCOPE, sourceCommit="1"*40))
            folder = root / candidate.TASK / "artifacts/visual-candidate"; folder.mkdir(parents=True)
            report = ET.Element("test-run", result="Passed", total="777", passed="777", failed="0", skipped="0", inconclusive="0")
            for unused in range(2): ET.SubElement(report, "test-suite", type="Assembly", name=candidate.ASSEMBLY, result="Passed")
            ET.SubElement(report, "test-case", fullname=candidate.CASE, result="Passed")
            (folder / "results.xml").write_bytes(ET.tostring(report))
            with patch.dict(os.environ, GITHUB_SHA="1"*40), self.assertRaises(ValueError): candidate.export_tests(root, "capture")
            self.assertTrue((output / "capture/raw-test-results.xml").exists())

    def test_wrong_root_counts_and_failed_nested_suite_rejected(self):
        for defect in ("counts", "suite"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); output = candidate.outdir(root)
                candidate.write(output / "source-receipt.json", dict(scope=candidate.SCOPE, sourceCommit="1"*40))
                folder = root / candidate.TASK / "artifacts/visual-candidate"; folder.mkdir(parents=True)
                report = ET.Element("test-run", result="Passed", total="777" if defect == "counts" else "1", passed="777" if defect == "counts" else "1", failed="0", skipped="0", inconclusive="0")
                assembly = ET.SubElement(report, "test-suite", type="Assembly", name=candidate.ASSEMBLY, result="Passed")
                fixture = ET.SubElement(assembly, "test-suite", type="TestFixture", result="Failed" if defect == "suite" else "Passed")
                ET.SubElement(fixture, "test-case", fullname=candidate.CASE, result="Passed")
                (folder / "results.xml").write_bytes(ET.tostring(report))
                with patch.dict(os.environ, GITHUB_SHA="1"*40), self.assertRaises(ValueError): candidate.export_tests(root, "capture")

    def test_private_like_output_is_never_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); folder = root / candidate.TASK / "artifacts/visual-candidate"; folder.mkdir(parents=True)
            (folder / "results.xml").write_text('<test-run><output>password=synthetic</output></test-run>')
            with self.assertRaises(ValueError): candidate.export_tests(root, "capture")
            self.assertFalse((candidate.outdir(root) / "capture/raw-test-results.xml").exists())


class PhysicalPhoneEvidenceTests(unittest.TestCase):
    def validate(self, value):
        return candidate.validate_capture(value, "1"*40, "12345", "1")

    @staticmethod
    def frame(value, stage):
        return next(f for f in value["frames"] if f["stage"] == stage)

    def test_original_eleven_and_six_phone_frames_remain_distinct(self):
        self.assertEqual(len(candidate.BASE_FRAMES), 11)
        self.assertEqual(len(candidate.PHONE_FRAMES), 6)
        self.assertEqual(len(set(candidate.FRAMES)), 23)
        self.validate(receipt())
        for name in candidate.PHONE_FRAMES:
            value=receipt();value["frames"]=[f for f in value["frames"] if f["stage"] != name]
            with self.subTest(stage=name), self.assertRaises(ValueError):self.validate(value)

    def test_pending_request_must_not_credit_money_debt_limit_or_loan(self):
        for key in ("cashMinor", "motherDebtMinor", "motherLifetimeMinor", "loanCount", "ledgerCount"):
            value=receipt();self.frame(value,"phone-mom-pending")[key] += 1
            with self.subTest(field=key), self.assertRaises(ValueError):self.validate(value)
        value=receipt();self.frame(value,"phone-mom-pending")["phoneEventCount"]=0
        with self.assertRaises(ValueError):self.validate(value)

    def test_claim_exact_game_coin_units_and_unique_financial_entries(self):
        for key in ("cashMinor", "motherDebtMinor", "motherLifetimeMinor", "loanCount", "ledgerCount", "phoneEventCount"):
            value=receipt();self.frame(value,"phone-mom-claimed")[key] += 1
            with self.subTest(field=key), self.assertRaises(ValueError):self.validate(value)
        value=receipt();self.frame(value,"phone-mom-claimed")["cashMinor"]=31000
        with self.assertRaises(ValueError):self.validate(value)

    def test_phone_return_preserves_ticket_mask_tools_camera_and_saved_state(self):
        for key,bad in (("ticketId","other"),("ticketMaskSha256","a"*64),("ticketContentSha256","a"*64),
                        ("currentTools",[]),("nextTools",[]),("revealedCells",4),("stateSha256","a"*64),
                        ("cameraPosition",dict(x=99,y=0,z=0))):
            value=receipt();self.frame(value,"phone-table-return")[key]=bad
            with self.subTest(field=key), self.assertRaises(ValueError):self.validate(value)

    def test_table_views_may_exclude_active_counter_phone_but_visibility_views_cannot(self):
        value=receipt()
        for name in ("phone-table-before","phone-table-return"):
            self.frame(value,name).update(phoneFrustumRendererCount=0,phoneScreenBounds=dict(x=-1000,y=-200,width=50,height=90),phoneScreenMinDepth=-1,phoneScreenMaxDepth=-.5)
        self.validate(value)
        for name in candidate.PHONE_VISIBLE_FRAMES:
            value=receipt();self.frame(value,name)["phoneFrustumRendererCount"]=0
            with self.subTest(stage=name),self.assertRaises(ValueError):self.validate(value)
        for key,bad in (("phoneWorldObjectActive",False),("phoneActiveRendererCount",0),("phoneInstanceId",43)):
            value=receipt();self.frame(value,"phone-table-return")[key]=bad
            with self.subTest(field=key),self.assertRaises(ValueError):self.validate(value)

    def test_phone_requires_real_focused_geometry_not_zero_or_offscreen(self):
        for key,bad in (("phoneFrustumRendererCount",0),("phoneFocused",False),
                        ("phoneScreenBounds",dict(x=-1,y=1,width=100,height=200)),
                        ("phoneScreenBounds",dict(x=500,y=200,width=0,height=300))):
            value=receipt();self.frame(value,"phone-contacts")[key]=bad
            with self.subTest(field=key), self.assertRaises(ValueError):self.validate(value)

    def test_only_three_phone_closeups_can_hide_normal_hud(self):
        value=receipt()
        for name in ("phone-contacts", "phone-mom-pending", "phone-mom-claimed"):
            self.frame(value,name).update(hudVisible=False,hudFrustumRendererCount=0)
        self.validate(value)
        for name in candidate.BASE_FRAMES + ["phone-room-standing","phone-table-before","phone-table-return"]:
            value=receipt();self.frame(value,name).update(hudVisible=False,hudFrustumRendererCount=0)
            with self.subTest(stage=name),self.assertRaises(ValueError):self.validate(value)
        for key,bad in (("phoneScreenMinDepth",-1),("phonePlaneCameraAbsCosine",0),("phoneScreenMaxDepth",float("inf"))):
            value=receipt();self.frame(value,"phone-contacts")[key]=bad
            with self.subTest(field=key),self.assertRaises(ValueError):self.validate(value)

    def test_phone_interaction_fixture_retains_cancel_scroll_and_real_input_routes(self):
        root=Path(__file__).resolve().parents[3]
        source=(root/candidate.TASK/'unity/Assets/G3/Tests/VisualCandidate/VisualCandidateCaptureTests.cs').read_text()
        body=source.split('IEnumerator PhysicalPhoneBorrowKeepsConfirmedTicket()',1)[1].split('static long MotherDebt',1)[0]
        for forbidden in ('P.Execute(', 'P.Service.Borrow(', 'P.Service.RequestPhoneLoan('):self.assertNotIn(forbidden,body)
        for token in ('MouseEvent(sendPoint, true)', 'Router.NotifyFocus(false); Router.NotifyFocus(true); MouseEvent(sendPoint, false)',
                      'phone-send-focus-cancelled-no-request', 'MouseEvent(packetPoint + Vector2.up * 24, true)',
                      'phone-packet-scroll-no-claim', 'Click("phone-claim")', 'Click("close-phone")'):
            self.assertIn(token,body)

    def test_original_capture_method_identity_and_contract_files_unchanged(self):
        root=Path(__file__).resolve().parents[3]
        fixture=(root/candidate.TASK/'unity/Assets/G3/Tests/VisualCandidate/VisualCandidateCaptureTests.cs').read_text()
        self.assertEqual(fixture.count('[UnityTest]'),1)
        self.assertIn('ScenarioStateCaptureRetainsTwentyThreeViewsFromRealTransactionsV2',fixture)
        for marker in ('Assert.That(State.TicketsPurchasedToday, Is.EqualTo(12))',
                       'Assert.That(State.SettledTicketCount, Is.EqualTo(12))',
                       'PreviewSettlement().RawPrizeMinor, Is.EqualTo(2000)',
                       'CurrentTicket.RevealedCells.Count(x => x), Is.EqualTo(2)'):
            self.assertIn(marker,fixture)
        workflow=(root/candidate.WORKFLOW).read_text()
        for frame in candidate.PHONE_FRAMES:self.assertEqual(workflow.count('/captures/'+frame+'.png'),1)


class OriginalG3FrameExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
        cls.chunk = staticmethod(chunk)
        row = bytes(value for x in range(1280) for value in (x % 256, (x // 8) % 256, (x * 3) % 256))
        cls.pixels = b"".join(b"\x00" + row for unused in range(720))
        cls.pngs = [cls.png(index) for index in range(14)]

    @classmethod
    def png(cls, index, width=1280):
        pixels = bytearray(cls.pixels); pixels[1] = index
        return b"\x89PNG\r\n\x1a\n" + cls.chunk(b"IHDR", struct.pack(">IIBBBBB", width, 720, 8, 2, 0, 0, 0)) + cls.chunk(b"IDAT", zlib.compress(pixels)) + cls.chunk(b"IEND", b"")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, GITHUB_SHA="1" * 40, GITHUB_RUN_ID="12345", GITHUB_RUN_ATTEMPT="1"); self.env.start(); self.addCleanup(self.env.stop)
        candidate.write(candidate.outdir(self.root) / "source-receipt.json", dict(scope=candidate.SCOPE, sourceCommit="1" * 40, runId="12345", runAttempt="1"))
        original = Path(__file__).resolve().parents[3] / candidate.TASK / "ci"
        for name in ("g2-test-contract.json", "g3-test-contract.json"):
            target = self.root / candidate.TASK / "ci" / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(original / name, target)
        candidate.prepare_original_g3_captures(self.root)
        profiles = {}
        for name in ("g2-test-contract.json", "g3-test-contract.json"):
            profiles.update(candidate.read_json(original / name)["profiles"]["play"])
        count = sum(len(names) for names in profiles.values())
        self.xml = ET.Element("test-run", result="Passed", total=str(count), passed=str(count), failed="0", skipped="0", inconclusive="0")
        for assembly, names in profiles.items():
            suite = ET.SubElement(self.xml, "test-suite", type="Assembly", name=assembly, result="Passed")
            for name in names: ET.SubElement(suite, "test-case", fullname=name, result="Passed")
        self.xmlpath = self.root / candidate.TASK / "artifacts/visual-regression-play/results.xml"
        self.xmlpath.parent.mkdir(parents=True); self.xmlpath.write_bytes(ET.tostring(self.xml))
        self.source = candidate.original_g3_source(self.root); self.source.mkdir(parents=True)
        frames = []
        for index, name in enumerate(candidate.ORIGINAL_G3_FRAMES):
            data = self.pngs[index]; (self.source / (name + ".png")).write_bytes(data)
            frames.append(dict(stage=name, file=name + ".png", sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), stateSha256="a" * 64,
                               gameRunId="g3-protected-render-fixture" if name == "challenge-protected" else "g3-day-qafixture-001",
                               fixtureLabel="SYNTHETIC_CONSUMABLE_BOUNDARY_FIXTURE" if name == "challenge-protected" else "G3_DIAGNOSTIC_VECTOR_NOT_NATURAL"))
        import g3_ci
        self.receipt = dict(schemaVersion=2, scope="G3_CAMERA_RENDER_NOT_DEVICE_TESTED", sourceCommit="1" * 40, runId="12345", unityVersion="6000.3.19f1",
                            rulesSha256=g3_ci.RULES_SHA, captureMethod="URP_STANDARD_REQUEST_READPIXELS", graphicsDeviceType="OpenGLCore", graphicsDeviceName="Synthetic validation only",
                            width=1280, height=720, sourceViewportWidth=1280, sourceViewportHeight=720, inputEvidence="SIMULATED_UI_INPUT_WITH_DECLARED_SCENARIO_SETUP", deviceQa="NOT_RUN", visualReview="PENDING", frames=frames)
        self.save_receipt()

    def save_receipt(self): candidate.write(self.source / "render-receipt.json", self.receipt)
    def export(self): candidate.export_original_g3_captures(self.root)
    def assert_no_frames_exported(self): self.assertFalse((candidate.outdir(self.root) / "original-g3-captures/empty.png").exists())

    def test_original_legacy_navigation_provenance_rejected(self):
        self.receipt.update(schemaVersion=1,inputEvidence="SIMULATED_INPUT_SYSTEM");self.save_receipt()
        with self.assertRaises(ValueError):self.export()
    def test_original_wrong_setup_provenance_rejected(self):
        self.receipt["inputEvidence"]="WORLD_INPUT_PASS";self.save_receipt()
        with self.assertRaises(ValueError):self.export()
    def test_complete_originals_export_separately_with_attempt_limitation(self):
        self.export(); folder = candidate.outdir(self.root) / "original-g3-captures"
        self.assertEqual(len(list(folder.glob("*.png"))), 14)
        result = candidate.read_json(folder / "export-receipt.json")
        self.assertEqual(result["exactPlayModeCases"], 37)
        self.assertEqual(result["legacyReceiptRunAttempt"], "NOT_PRESENT_IN_LEGACY_SCHEMA")
        self.assertEqual(result["separateProtectedFixtureFrame"], "challenge-protected")
        self.assertEqual(result["g3Gate"], "NOT_EVALUATED")
        self.assertFalse((candidate.outdir(self.root) / "captures/capture-receipt.json").exists())

    def test_expanded_phone_play_cases_cannot_be_omitted_to_reuse_old_32_pass(self):
        suffixes={"PhysicalPhoneProjectsRealGlassAndRestoresCameraWithoutChangingTicket", "PhoneSendRequiresReleaseAndSavedPendingPacketSurvivesReload", "PhysicalPhoneKeysMeetProjectedReferenceTargetsAndOcclusionBlocksTap"}
        removed=0
        for suite in self.xml.iter("test-suite"):
            for case in list(suite):
                if case.tag=="test-case" and case.get("fullname","").rsplit(".",1)[-1] in suffixes:
                    suite.remove(case);removed+=1
        self.assertEqual(removed,3)
        self.xml.set("total","32");self.xml.set("passed","32");self.xmlpath.write_bytes(ET.tostring(self.xml))
        with self.assertRaises(ValueError):self.export()
        self.assert_no_frames_exported()

    def test_old_frames_upload_requires_successful_export_and_is_separate(self):
        root = Path(__file__).resolve().parents[3]
        workflow = (root / candidate.WORKFLOW).read_text()
        upload = workflow.split("      - name: Upload separately verified existing 14 original G3 frames", 1)[1].split("      - name:", 1)[0]
        self.assertIn("steps.originalcaptures.outcome == 'success'", upload)
        for name in candidate.ORIGINAL_G3_FILES: self.assertIn("original-g3-captures/" + name, upload)
        regression = workflow.split("      - name: Upload bounded regression and source mutation evidence", 1)[1]
        self.assertNotIn("original-g3-captures/", regression)

    def test_wrong_source_receipt_is_rejected(self):
        self.receipt["sourceCommit"] = "2" * 40; self.save_receipt()
        with self.assertRaises(ValueError): self.export()
        self.assert_no_frames_exported()

    def test_old_attempt_preparation_is_rejected(self):
        path = candidate.outdir(self.root) / "original-g3-preparation.json"; value = candidate.read_json(path); value["runAttempt"] = "2"; candidate.write(path, value)
        with self.assertRaises(ValueError): self.export()
        self.assert_no_frames_exported()

    def test_preparation_removes_only_fixed_outputs_and_rejects_leftover_old_files(self):
        keep = self.source / "unrelated.txt"; keep.write_text("keep")
        candidate.prepare_original_g3_captures(self.root)
        self.assertTrue(keep.exists()); self.assertFalse(any((self.source / name).exists() for name in candidate.ORIGINAL_G3_FILES))
        with self.assertRaises(ValueError): self.export()
        self.assert_no_frames_exported()

    def test_stale_png_timestamp_from_before_preparation_is_rejected(self):
        os.utime(self.source / "empty.png", ns=(1, 1))
        with self.assertRaises(ValueError): self.export()
        self.assert_no_frames_exported()

    def test_stale_original_nunit_xml_is_rejected(self):
        os.utime(self.xmlpath, ns=(1, 1))
        with self.assertRaises(ValueError): self.export()
        self.assert_no_frames_exported()

    def test_missing_original_png_is_rejected(self):
        (self.source / "night.png").unlink()
        with self.assertRaises(ValueError): self.export()
        self.assert_no_frames_exported()

    def test_original_png_hash_corruption_is_rejected(self):
        path = self.source / "empty.png"; data = bytearray(path.read_bytes()); data[-1] ^= 1; path.write_bytes(data)
        with self.assertRaises(ValueError): self.export()
        self.assert_no_frames_exported()

    def test_wrong_dimensions_with_matching_hash_are_rejected(self):
        data = self.png(0, width=1279); (self.source / "empty.png").write_bytes(data)
        self.receipt["frames"][0].update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data)); self.save_receipt()
        with self.assertRaises(ValueError): self.export()
        self.assert_no_frames_exported()

    def test_failed_original_nunit_case_is_rejected(self):
        for case in self.xml.iter("test-case"):
            if case.get("fullname") == candidate.ORIGINAL_G3_CASE: case.set("result", "Failed")
        self.xml.set("result", "Failed"); self.xml.set("passed", "31"); self.xml.set("failed", "1"); self.xmlpath.write_bytes(ET.tostring(self.xml))
        with self.assertRaises(ValueError): self.export()
        self.assert_no_frames_exported()

    def test_protected_fixture_cannot_be_relabelled_as_main_day(self):
        self.receipt["frames"][-1]["gameRunId"] = "g3-day-qafixture-001"; self.save_receipt()
        with self.assertRaises(ValueError): self.export()
        self.assert_no_frames_exported()


class SeparateRequestTests(unittest.TestCase):
    def test_only_new_diagnostic_trigger_following_source_is_admitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return subprocess.check_output(["git", "-C", directory, *args], stderr=subprocess.DEVNULL).decode().strip()
            git("init"); git("config", "user.name", "Synthetic Test"); git("config", "user.email", "synthetic@example.invalid")
            (root / "source.txt").write_text("synthetic candidate")
            git("add", "."); git("commit", "-m", "Synthetic source")
            source = git("rev-parse", "HEAD")
            candidate.write(root / candidate.REQUEST, dict(schemaVersion=1, requestId="lottery-visual-20261013-01", sourceCommit=source, purpose=candidate.SCOPE, sourceReview=dict(sourceCommit=source, status="APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY", reviewedAtUtc="2026-10-13T01:00:00Z", reviewId="visual-source-20261013-01", reviewer="independent-source-review")))
            git("add", "."); git("commit", "-m", "Synthetic diagnostic request")
            event = root / "event.json"; event.write_text(json.dumps(dict(repository=dict(private=False, fork=False), deleted=False)))
            env = dict(GITHUB_EVENT_NAME="push", GITHUB_REPOSITORY="yangerstar1/task-workbench", GITHUB_REPOSITORY_OWNER="yangerstar1", GITHUB_ACTOR="yangerstar1", GITHUB_TRIGGERING_ACTOR="yangerstar1", GITHUB_REF="refs/heads/lottery-shop-g0-20261011", GITHUB_SHA=git("rev-parse", "HEAD"), GITHUB_EVENT_PATH=str(event), GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1")
            with patch.dict(os.environ, env):
                observed = candidate.guard(root)
                self.assertEqual(observed["reviewedCandidateCommit"], source)
                self.assertEqual(observed["g3Gate"], "NOT_EVALUATED")
            env["GITHUB_ACTOR"] = "other"
            with patch.dict(os.environ, env), self.assertRaises(ValueError): candidate.guard(root)


class RegressionProgressTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[3]
        self.ident = dict(sourceCommit="1"*40, reviewedCandidateCommit="2"*40, runId="123", runAttempt="1")
        self.allowed = candidate.regression_case_keys(self.root)
        self.case = sorted(self.allowed)[0]

    def value(self, finish=False):
        events = [dict(sequence=1, stage="run-start", caseKey="", result="UNAVAILABLE", utc="2026-10-13T00:00:00Z", elapsedMs=0),
                  dict(sequence=2, stage="case-start", caseKey=self.case, result="UNAVAILABLE", utc="2026-10-13T00:00:01Z", elapsedMs=1000)]
        if finish:
            events += [dict(sequence=3, stage="case-end", caseKey=self.case, result="FAILED", utc="2026-10-13T00:00:02Z", elapsedMs=2000),
                       dict(sequence=4, stage="run-end", caseKey="", result="UNAVAILABLE", utc="2026-10-13T00:00:03Z", elapsedMs=3000)]
        return dict(schemaVersion=1, scope=candidate.SCOPE, status="MILESTONES_ONLY_NOT_TEST_PASS", events=events, **self.ident)

    def check(self, value):
        return candidate.validate_regression_progress(value, self.ident, self.allowed)

    def test_partial_and_failed_case_trails_are_diagnostic_only(self):
        for finish in (False, True):
            value = self.value(finish); self.assertEqual(self.check(value), value)
            self.assertNotIn("allExpectedPassed", value)

    def test_trigger_reviewed_source_run_and_attempt_must_all_match(self):
        for key in self.ident:
            value = self.value(); value[key] = "3"*40 if "Commit" in key else "99"
            with self.subTest(key=key), self.assertRaises(ValueError): self.check(value)

    def test_unknown_fields_case_stage_and_payload_are_rejected(self):
        for level in ("top", "event"):
            value = self.value(); target = value if level == "top" else value["events"][1]
            target["message"] = "SYNTHETIC_PRIVATE_LICENSE_XML"
            with self.assertRaises(ValueError): self.check(value)
        for field, bad in (("caseKey", "a"*64), ("caseKey", "Assets/private.cs"), ("stage", "arbitrary-log"), ("result", "SYNTHETIC_PRIVATE")):
            value = self.value(); value["events"][1][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError): self.check(value)

    def test_sequence_time_event_cap_and_verdict_claim_are_rejected(self):
        for field, bad in (("sequence", 3), ("sequence", True), ("elapsedMs", -1), ("elapsedMs", 86400001), ("elapsedMs", True), ("utc", "2026-10-13T00:00:01+01:00")):
            value = self.value(); value["events"][1][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError): self.check(value)
        value = self.value(); value["events"][1]["utc"] = "SYNTHETIC_PRIVATE_LICENSE_XML"
        with self.assertRaisesRegex(ValueError, "^Invalid regression progress UTC$"): self.check(value)
        value = self.value(); value["events"] *= 65
        with self.assertRaises(ValueError): self.check(value)
        value = self.value(); value["status"] = "ALL_PASSED"
        with self.assertRaises(ValueError): self.check(value)
        value = self.value(True); value["events"][2]["elapsedMs"] = 0
        with self.assertRaises(ValueError): self.check(value)
        value = self.value(True); value["events"][2]["utc"] = "2026-10-12T00:00:00Z"
        with self.assertRaises(ValueError): self.check(value)

    def test_duplicate_start_unpaired_finish_and_early_run_end_rejected(self):
        mutations = [lambda v: v["events"][2].update(stage="case-start", result="UNAVAILABLE"),
                     lambda v: v["events"][1].update(stage="case-end", result="PASSED"),
                     lambda v: v["events"][2].update(stage="run-end", caseKey="", result="UNAVAILABLE")]
        for change in mutations:
            value = self.value(True); change(value)
            with self.assertRaises(ValueError): self.check(value)

    def test_only_fixed_file_exports_and_oversize_never_leaks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root/candidate.TASK/"artifacts/visual-regression-play/test-progress.json"
            source.parent.mkdir(parents=True); destination = candidate.outdir(root)/"regression-play-progress.json"
            source.write_text(json.dumps(self.value()))
            with patch.object(candidate, "identity", return_value=self.ident), patch.object(candidate, "regression_case_keys", return_value=self.allowed):
                candidate.export_regression_progress(root); self.assertEqual(json.loads(destination.read_text()), self.value())
                source.write_text("x"*65537)
                with self.assertRaises(Exception): candidate.export_regression_progress(root)
                self.assertFalse(destination.exists())
                source.unlink(); candidate.export_regression_progress(root); self.assertFalse(destination.exists())

    def test_callback_whitelist_matches_exact_current_contract_and_is_explicitly_gated(self):
        text = (self.root/candidate.TASK/"unity/Assets/G3/Tests/PlayMode/G3RegressionProgress.cs").read_text()
        keys = set(re.findall(r'"([0-9a-f]{64})"', text)); self.assertEqual(keys, self.allowed); self.assertEqual(len(keys), 37)
        for required in ('[assembly: TestRunCallback(', 'ITestRunCallback', 'Arg("-g3RegressionProgress")=="1"', 'Arg("-assemblyNames")==Assemblies', 'Arg("-testPlatform")=="playmode"', 'Arg("-probeReviewedCommit")', 'MaximumBytes=65536, MaximumEvents=128'):
            self.assertIn(required, text)
        for forbidden in ('.Message', '.StackTrace', '.Output', 'ToXml', 'GetEnvironmentVariable', 'test.Name'):
            self.assertNotIn(forbidden, text)
        self.assertIn('if(Enabled&&!test.IsSuite)', text)

    def test_workflow_exports_only_named_validated_progress_after_real_play_attempt(self):
        text = (self.root/candidate.WORKFLOW).read_text()
        begin = text.index('      - name: Preserve exact-contract bounded PlayMode progress even on timeout')
        end = text.index('      - name: Verify existing exact PlayMode', begin)
        block = text[begin:end]
        self.assertIn("steps.regressionplay.outcome != 'skipped'", block)
        self.assertIn("steps.guard.outcome == 'success'", block)
        self.assertIn('visual_candidate_ci.py regression-progress', block)
        self.assertEqual(text.count('            tasks/lottery-shop/evidence/visual-candidate/regression-play-progress.json'), 1)



class FrameCostTests(unittest.TestCase):
    def check(self,v):return candidate.validate_progress(v,"runtime","1"*40,"12345","1")
    def test_fixed_numeric_snapshot_and_overflow_accepted_as_observation(self):
        v=progress_receipt();v['costs'][0]['values']=[2,10,8,5,3,20,9,2,100,60,1];self.check(v)
    def test_unknown_fields_and_free_text_rejected(self):
        for key,value in [('path','private'),('raw','private')]:
            v=progress_receipt();v['costs'][0][key]=value
            with self.assertRaises(ValueError):self.check(v)
        v=progress_receipt();v['costs'][0]['values'][0]='private'
        with self.assertRaises(ValueError):self.check(v)
    def test_shape_count_and_missing_rejected(self):
        for rows in ([],[dict(values=[0]*10)],[dict(values=[0]*12)],[dict(values=[0]*11)]*2):
            v=progress_receipt();v['costs']=rows
            with self.assertRaises(ValueError):self.check(v)
        v=progress_receipt();del v['costs']
        with self.assertRaises(ValueError):self.check(v)
    def test_all_numeric_bounds_and_bool_rejected(self):
        limits=[1000000,10**15,10**15,1000000,1000000,10**15,10**15,1000000,10**15,10**15,1]
        for i,limit in enumerate(limits):
            for bad in (-1,limit+1,True,1.5,float('nan'),float('inf')):
                v=progress_receipt();v['costs'][0]['values'][i]=bad
                with self.assertRaises(ValueError):self.check(v)
    def test_frequency_bounds_rejected(self):
        for bad in (0,-1,10**12+1,True,1.5,'private'):
            v=progress_receipt();v['tickFrequency']=bad
            with self.assertRaises(ValueError):self.check(v)
    def test_monotonic_counts_and_overflow_sticky(self):
        for i in range(11):
            v=progress_receipt();v['events'].append(dict(v['events'][0],elapsedMs=1));v['costs']=[dict(values=[1]*11),dict(values=[1]*11)];v['costs'][1]['values'][i]=0
            with self.assertRaises(ValueError):self.check(v)
    def test_no_impossible_totals(self):
        for count,total,maximum in ((0,1,2),(4,5,6),(7,8,9)):
            v=progress_receipt();v['costs'][0]['values'][maximum]=1
            with self.assertRaises(ValueError):self.check(v)
            v=progress_receipt();v['costs'][0]['values'][total]=1
            with self.assertRaises(ValueError):self.check(v)
    def test_max128_compact_payload_keeps64k(self):
        v=progress_receipt();v['events']*=128;v['costs']=[dict(values=[1000000,10**15,10**15,1000000,1000000,10**15,10**15,1000000,10**15,10**15,1])]*128;self.check(v);self.assertLess(len(json.dumps(v,separators=(',',':')).encode()),65536)
    def test_no_diagnostic_poll_movement_or_material_change(self):
        root=Path(__file__).resolve().parents[3];router=(root/candidate.TASK/'unity/Assets/G3/Interaction/G3InputRouter.cs').read_text();label=(root/candidate.TASK/'unity/Assets/G3/Rendering/BoundedGlyphLabel.cs').read_text()
        self.assertIn('Mathf.Clamp(Time.unscaledTime-lastPoll,0,.05f)',router);self.assertIn('try{PollInputObserved();}finally{PollCostEnd(start);}',router);self.assertIn('if(!dirty||font==null||mesh==null)return;',label);self.assertIn('finally{RebuildCostEnd(costStart);}',label)
    def test_capture_session_reset_stop_and_existing_write_only(self):
        root=Path(__file__).resolve().parents[3];s=(root/candidate.TASK/'unity/Assets/G3/Tests/VisualCandidate/VisualCandidateCaptureTests.cs').read_text();self.assertIn('BoundedGlyphLabel.BeginCostObservation();G3InputRouter.BeginCostObservation();',s);self.assertIn('finally{BoundedGlyphLabel.EndCostObservation();G3InputRouter.EndCostObservation();}',s);self.assertIn('JsonUtility.ToJson(receipt, kind!="runtime")',s)


class ScenarioProvenanceV2Tests(unittest.TestCase):
    def test_every_frame_has_closed_origin_and_setup_scope(self):
        self.assertEqual(set(candidate.FRAME_CAMERA_ORIGINS),set(candidate.FRAMES))
        for index in range(23):
            for key,bad in (("cameraOrigin","KEYBOARD_TRAVERSED_PLAYER_VIEW"),("stateOrigin","UNTRACKED"),("navigationEvidence","WORLD_INPUT_PASS")):
                value=receipt();value["frames"][index][key]=bad
                with self.assertRaises(ValueError):candidate.validate_capture(value,"1"*40,"12345","1")
    def test_removed_global_controls_cannot_return(self):
        for control in ("open-more","open-shop","open-inventory","open-phone","open-tickets","open-drawer","open-bill"):
            value=receipt();value["frames"][0]["visibleControlIds"].append(control)
            with self.assertRaises(ValueError):candidate.validate_capture(value,"1"*40,"12345","1")
    def test_old_v4_receipt_rejected(self):
        value=receipt();value.update(schemaVersion=4,candidatePresentation="V19_EXTERIOR_FIXTURE_VIEWS_NOT_VISUAL_PASS")
        with self.assertRaises(ValueError):candidate.validate_capture(value,"1"*40,"12345","1")
    def test_world_cases_match_compiled_source_list(self):
        root=Path(candidate.__file__).resolve().parents[1]
        contract=json.loads((root/"ci/g3-test-contract.json").read_text())["profiles"]["play"]["Lottery.G3.PlayMode.Tests.dll"]
        methods=[]
        for file in (root/"unity/Assets/G3/Tests/PlayMode").glob("G3*Tests.cs"):
            methods+=re.findall(r"\[UnityTest(?:,Timeout\(180000\))?\]\s*public IEnumerator (\w+)\(",file.read_text())
        self.assertEqual(len(methods),29);self.assertEqual({"Lottery.G3.PlayMode.Tests.G3PlayTests."+name for name in methods},set(contract))
        worlds=[x for x in contract if ".WorldInput" in x];self.assertEqual(len(worlds),3)
        self.assertNotIn("Lottery.G3.PlayMode.Tests.G3PlayTests.WalkingIsOptionalAndPhysicalAndQuickShopShareStockAndReturnPose",contract)

if __name__ == "__main__":
    unittest.main()
