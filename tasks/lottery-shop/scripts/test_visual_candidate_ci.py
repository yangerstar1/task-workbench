#!/usr/bin/env python3
"""Synthetic validator tests, never native rendering or gameplay evidence."""
import copy
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
        frames.append(dict(stage=name, file=name + ".png", sha256="a" * 64,
            width=1600 if name.endswith("20x9") else 1280, height=720,
            stateSha256="b" * 64, seedSha256="c" * 64, hudVisible=True, hudFits=True,
            cameraOrthographic=False, hudFrustumRendererCount=20, importedRendererCount=200, inputUpdates=123,
            cameraPosition=dict(x=1, y=2, z=3), cameraEuler=dict(x=60, y=180, z=0), cameraFov=64, dayPhase="NIGHT_BILL" if name == "night-table" else "DAY_OPEN",
            panel="None", hudOpaqueAreaRatio=.18, visibleControlIds=["open-shop", "open-inventory", "open-phone", "stand", "open-more"], moreVisible=False, paperVisible=True, renderedShopRendererCount=32, renderedShopMaterialCount=31, paperPresentationBounds=dict(x=300,y=200,width=600,height=400), toolPresentationBounds=[dict(x=400+i*100,y=510,width=60,height=80) for i in range(3)], currentTools=["small_prize_box", "inspection_lamp", "large_prize_stamp"], revealedCells=3))
    return dict(schemaVersion=2, candidatePresentation="V13_MORE_NAVIGATION_MEASURED_GEOMETRY_NOT_VISUAL_PASS", scope=candidate.SCOPE, sourceCommit="1" * 40, runId="12345", runAttempt="1", unityVersion="6000.3.19f1",
                graphicsDeviceType="OpenGLCore", inputEvidence="SIMULATED_INPUT_SYSTEM",
                captureMethod="URP_STANDARD_REQUEST_READPIXELS", hudVisibilityBasis="ENABLED_CAMERA_LAYER_AND_FRUSTUM_TEST_NOT_PIXEL_OCCLUSION", complete=True, frames=frames, actions=[])


def progress_receipt(kind="runtime"):
    return dict(schemaVersion=1, scope=candidate.SCOPE, kind=kind, sourceCommit="1" * 40, runId="12345", runAttempt="1",
                status="MILESTONES_ONLY_NOT_TEST_PASS", events=[dict(stage="runtime-setup-begin" if kind == "runtime" else "prebuild-begin",
                utc="2026-10-13T03:00:00.0000000Z", elapsedMs=0, inputUpdates=0, frameCount=0, purchased=-1, settled=-1, dayPhase="UNAVAILABLE")])


class ProgressReceiptTests(unittest.TestCase):
    def validate(self, value, kind="runtime"):
        return candidate.validate_progress(value, kind, "1" * 40, "12345", "1")

    def test_runtime_and_prebuild_milestones_are_observations_only(self):
        self.validate(progress_receipt()); self.validate(progress_receipt("prebuild"), "prebuild")

    def test_fixed_lifecycle_stages_accept_no_arbitrary_payload(self):
        value = progress_receipt(); value["kind"] = "lifecycle"; value["events"][0]["stage"] = "editor-exiting-edit-mode"
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
        for key, wrong in (("elapsedMs", -1), ("inputUpdates", True), ("frameCount", 12), ("purchased", 13), ("settled", -2), ("utc", "not-a-date")):
            value = progress_receipt(); value["events"][0][key] = wrong
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)

    def test_timeout_milestone_never_claims_pass(self):
        value = progress_receipt(); value["events"].append(dict(value["events"][0], stage="runtime-timeout", elapsedMs=900001))
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
        for text in ("State.TicketsPurchasedToday, Is.EqualTo(12)", "State.SettledTicketCount, Is.EqualTo(12)", "State.Phase, Is.EqualTo(DayPhase.CLOSING_PREP)", "frame < 600", "i < 1200", "Is.LessThan(UnloadSeconds)"):
            self.assertIn(text, source)
        workflow = (root / candidate.WORKFLOW).read_text()
        self.assertIn("id: capture\n        timeout-minutes: 30", workflow)
        self.assertIn("timeout-minutes: 60", workflow)


class VisualCandidateEvidenceTests(unittest.TestCase):
    def validate(self, value, complete=True):
        return candidate.validate_capture(value, "1" * 40, "12345", "1", complete)

    def test_synthetic_complete_shape(self):
        self.assertEqual(len(self.validate(receipt())), 11)

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
        value = receipt(); value["frames"][6]["stateSha256"] = "d" * 64
        with self.assertRaises(ValueError): self.validate(value)

    def test_day_night_must_use_same_camera(self):
        value = receipt(); value["frames"][9]["cameraPosition"]["x"] = 8
        with self.assertRaises(ValueError): self.validate(value)

    def test_same_position_different_rotation_or_fov_is_rejected(self):
        for key, bad in (("cameraEuler", dict(x=0, y=0, z=0)), ("cameraFov", 90)):
            value = receipt(); value["frames"][9][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)

    def test_aspect_pair_and_seed_cannot_be_mixed(self):
        for key in ("stateSha256", "seedSha256"):
            value = receipt(); value["frames"][3][key] = "d" * 64
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)

    def test_night_must_be_real_phase_with_closed_bill(self):
        for key, bad in (("dayPhase", "DAY_OPEN"), ("panel", "Bill")):
            value = receipt(); value["frames"][9][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError): self.validate(value)

    def test_measured_layout_fields_are_required_without_art_pass_threshold(self):
        value = receipt(); value["frames"][0]["hudOpaqueAreaRatio"] = .9
        self.assertEqual(len(self.validate(value)), 11)
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
    def test_existing_contract_union_has_287_edit_and_32_play_cases(self):
        task = Path(candidate.__file__).resolve().parents[1]
        contracts = [json.loads((task / "ci" / (name + "-test-contract.json")).read_text()) for name in ("g2", "g3")]
        for stage, expected in (("edit", 287), ("play", 32)):
            names = {case for contract in contracts for cases in contract["profiles"][stage].values() for case in cases}
            self.assertEqual(len(names), expected)

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
        self.receipt = dict(schemaVersion=1, scope="G3_CAMERA_RENDER_NOT_DEVICE_TESTED", sourceCommit="1" * 40, runId="12345", unityVersion="6000.3.19f1",
                            rulesSha256=g3_ci.RULES_SHA, captureMethod="URP_STANDARD_REQUEST_READPIXELS", graphicsDeviceType="OpenGLCore", graphicsDeviceName="Synthetic validation only",
                            width=1280, height=720, sourceViewportWidth=1280, sourceViewportHeight=720, inputEvidence="SIMULATED_INPUT_SYSTEM", deviceQa="NOT_RUN", visualReview="PENDING", frames=frames)
        self.save_receipt()

    def save_receipt(self): candidate.write(self.source / "render-receipt.json", self.receipt)
    def export(self): candidate.export_original_g3_captures(self.root)
    def assert_no_frames_exported(self): self.assertFalse((candidate.outdir(self.root) / "original-g3-captures/empty.png").exists())

    def test_complete_originals_export_separately_with_attempt_limitation(self):
        self.export(); folder = candidate.outdir(self.root) / "original-g3-captures"
        self.assertEqual(len(list(folder.glob("*.png"))), 14)
        result = candidate.read_json(folder / "export-receipt.json")
        self.assertEqual(result["legacyReceiptRunAttempt"], "NOT_PRESENT_IN_LEGACY_SCHEMA")
        self.assertEqual(result["separateProtectedFixtureFrame"], "challenge-protected")
        self.assertEqual(result["g3Gate"], "NOT_EVALUATED")
        self.assertFalse((candidate.outdir(self.root) / "captures/capture-receipt.json").exists())

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


if __name__ == "__main__":
    unittest.main()
