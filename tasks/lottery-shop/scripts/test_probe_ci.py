"""Synthetic validator fixtures only. Not Unity execution or device evidence."""
import copy
import hashlib
import json
import lzma
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import probe_ci as ci


class GuardSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.env = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push",
                    "GITHUB_REPOSITORY": ci.REPOSITORY, "GITHUB_REPOSITORY_OWNER": ci.OWNER,
                    "GITHUB_ACTOR": ci.OWNER, "GITHUB_TRIGGERING_ACTOR": ci.OWNER,
                    "GITHUB_REF": "refs/heads/" + ci.BRANCH, "RUNNER_ENVIRONMENT": "github-hosted",
                    "RUNNER_OS": "Linux", "GITHUB_SHA": self.sha,
                    "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}
        self.event = {"ref": self.env["GITHUB_REF"], "after": self.sha, "deleted": False,
                      "sender": {"login": ci.OWNER}, "repository": {"full_name": ci.REPOSITORY,
                      "private": False, "fork": False, "owner": {"login": ci.OWNER}}}
        self.request = copy.deepcopy(ci.REQUEST)
        self.changed = [ci.REQUEST_PATH]

    def verify(self):
        return ci.validate_guard(self.env, self.event, self.request, self.sha, self.changed)

    def test_synthetic_authorized_context(self):
        self.assertEqual(self.verify()["sourceCommit"], self.sha)
        self.assertEqual(self.verify()["deviceQa"], "NOT_RUN")

    def test_reject_each_untrusted_environment_field(self):
        for key in self.env:
            with self.subTest(key=key):
                original = self.env[key]
                self.env[key] = "unexpected"
                with self.assertRaises(ValueError):
                    self.verify()
                self.env[key] = original

    def test_reject_fork_private_missing_flags(self):
        for key in ("private", "fork"):
            for value in (True, None, 0, "false"):
                with self.subTest(key=key, value=value):
                    self.event["repository"][key] = value
                    with self.assertRaises(ValueError):
                        self.verify()
            self.event["repository"][key] = False

    def test_reject_wrong_sender_or_owner(self):
        self.event["sender"]["login"] = "someone-else"
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_missing_request_change(self):
        self.changed = ["tasks/lottery-shop/README.md"]
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_request_extra_field(self):
        self.request["command"] = "other-action"
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_boolean_schema_version(self):
        self.request["schemaVersion"] = True
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_wrong_request_id(self):
        self.request["requestId"] = "other-run"
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_deleted_push(self):
        self.event["deleted"] = True
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_event_commit_mismatch(self):
        self.event["after"] = "b" * 40
        with self.assertRaises(ValueError):
            self.verify()


class NUnitSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.path = self.directory / "synthetic-NOT-UNITY-EVIDENCE.xml"
        self.report = ET.Element("test-run", {"result": "Passed", "total": "6", "passed": "6",
                                "failed": "0", "skipped": "0", "inconclusive": "0"})
        self.suite = ET.SubElement(self.report, "test-suite", {"type": "Assembly",
                                  "name": "Lottery.Probe.Tests.dll", "result": "Passed"})
        for name in sorted(ci.EXPECTED_CASES):
            ET.SubElement(self.suite, "test-case", {"fullname": name, "result": "Passed"})

    def verify(self):
        ET.ElementTree(self.report).write(self.path, encoding="utf-8")
        return ci.inspect_tests(self.directory)

    def test_synthetic_six_pass(self):
        result = self.verify()[2]
        self.assertEqual(result["passed"], 6)
        self.assertEqual(result["renderedFrameQa"], "NOT_RUN")
        self.assertEqual(result["touchEventInjectionQa"], "NOT_RUN")

    def test_reject_empty_directory(self):
        with self.assertRaises(ValueError):
            ci.inspect_tests(self.directory)

    def test_reject_duplicate_report(self):
        self.verify()
        (self.directory / "duplicate.xml").write_bytes(self.path.read_bytes())
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_duplicate_case(self):
        self.suite[1].set("fullname", self.suite[0].get("fullname"))
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_missing_case(self):
        self.suite.remove(self.suite[0])
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_extra_case(self):
        ET.SubElement(self.suite, "test-case", {"fullname": "Unexpected.Test", "result": "Passed"})
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_skipped_failed_or_inconclusive_case(self):
        for status in ("Skipped", "Failed", "Inconclusive", "Ignored"):
            with self.subTest(status=status):
                self.suite[0].set("result", status)
                with self.assertRaises(ValueError):
                    self.verify()

    def test_reject_inconsistent_summary(self):
        for key in ("total", "passed", "failed", "skipped", "inconclusive"):
            with self.subTest(key=key):
                original = self.report.get(key)
                self.report.set(key, "99")
                with self.assertRaises(ValueError):
                    self.verify()
                self.report.set(key, original)

    def test_reject_wrong_assembly(self):
        self.suite.set("name", "Other.dll")
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_failed_suite_despite_passed_cases(self):
        self.suite.set("result", "Failed")
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_xml_entities(self):
        self.path.write_text('<!DOCTYPE test-run [<!ENTITY fixture "SYNTHETIC">]><test-run/>')
        with self.assertRaises(ValueError):
            ci.inspect_tests(self.directory)

    def test_published_xml_excludes_properties_logs_and_command_lines(self):
        self.report.set("command-line", "SYNTHETIC-DO-NOT-PUBLISH")
        ET.SubElement(self.suite[0], "output").text = "SYNTHETIC-DO-NOT-PUBLISH"
        safe = self.directory / "safe-result.txt"
        ci.save_safe_test_xml(self.report, safe)
        self.assertNotIn("SYNTHETIC-DO-NOT-PUBLISH", safe.read_text())
        self.assertEqual(len(ET.parse(safe).getroot().findall("test-case")), 6)

    def test_original_xml_preserved_byte_for_byte(self):
        self.verify()
        out = self.directory / "evidence"
        out.mkdir()
        ci.export_raw_test_report(self.directory, out)
        self.assertEqual((out / "raw-test-results.xml").read_bytes(), self.path.read_bytes())

    def test_original_xml_refused_if_credential_like_content(self):
        for value in ("UNITY_PASSWORD=synthetic", "synthetic@example.invalid", "Bearer synthetic",
                      "ghp_" + "z" * 30):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ci.require_safe_xml(("<test-run><output>" + value + "</output></test-run>").encode())

    def test_reject_three_encoded_credential_shapes_in_text_attributes_and_tails(self):
        for value in ("synthetic&#64;example.invalid", "pass&#119;ord=synthetic", "ghp&#95;" + "z" * 30):
            for xml in ("<test-run><output>" + value + "</output></test-run>",
                        '<test-run><property value="' + value + '"/></test-run>',
                        "<test-run><output/>" + value + "</test-run>"):
                with self.subTest(xml=xml), self.assertRaises(ValueError):
                    ci.require_safe_xml(xml.encode())

    def test_rejected_encoded_xml_is_not_exported(self):
        self.verify()
        raw = self.path.read_bytes().replace(b"</test-run>", b"<output>pass&#119;ord=synthetic</output></test-run>")
        self.path.write_bytes(raw)
        out = self.directory / "evidence"
        out.mkdir()
        with self.assertRaises(ValueError):
            ci.export_raw_test_report(self.directory, out)
        self.assertFalse((out / "raw-test-results.xml").exists())
        self.assertFalse((out / "raw-test-report-receipt.json").exists())

    def test_reject_all_cases_outside_expected_assembly(self):
        for case in list(self.suite):
            self.suite.remove(case)
            self.report.append(case)
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_one_case_outside_expected_assembly(self):
        case = self.suite[0]
        self.suite.remove(case)
        self.report.append(case)
        with self.assertRaises(ValueError):
            self.verify()


class ApkSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.apk = self.path / "SYNTHETIC-NOT-AN-ANDROID-APP.apk"
        self.receipt = self.path / "synthetic-receipt.json"
        self.packages = self.path / "synthetic-packages.txt"
        self.identity = {"sourceCommit": "a" * 40, "runId": "123", "runAttempt": "1"}
        self.header = bytearray(64)
        self.header[:6] = b"\x7fELF\x02\x01"
        self.header[18:20] = (183).to_bytes(2, "little")
        self.entries = {"AndroidManifest.xml": b"synthetic", "classes.dex": b"synthetic",
                        "lib/arm64-v8a/libil2cpp.so": bytes(self.header),
                        "lib/arm64-v8a/libunity.so": bytes(self.header),
                        "assets/SYNTHETIC-PADDING": b"x" * (1024 * 1024 + 1)}
        self.data = {"sourceCommit": self.identity["sourceCommit"], "runId": "123", "unityVersion": ci.VERSION,
                     "scope": ci.SCOPE, "deviceQa": "NOT_RUN", "renderedFrameQa": "NOT_RUN", "gameplayQa": "NOT_RUN",
                     "signing": "development-debug", "buildResult": "Succeeded", "buildTarget": "Android",
                     "scriptingBackend": "IL2CPP", "architecture": "ARM64", "minSdk": 26, "targetSdk": 35,
                     "graphicsApis": "OpenGLES3", "editorRevision": "6000.3.19f1 (7689f4515d75)"}
        self.packages.write_text("\n".join(name + "@" + version for name, version in ci.PACKAGES.items()))

    def verify(self):
        with zipfile.ZipFile(self.apk, "w", zipfile.ZIP_STORED) as archive:
            for name, data in self.entries.items():
                archive.writestr(name, data)
        self.data.update(apkBytes=self.apk.stat().st_size, apkSha256=ci.digest(self.apk))
        ci.write_json(self.receipt, self.data)
        return ci.inspect_apk(self.apk, self.receipt, self.packages, self.identity)

    def test_synthetic_byte_structure_only_not_device_evidence(self):
        result = self.verify()
        self.assertEqual(result["deviceQa"], "NOT_RUN")
        self.assertEqual(result["renderedFrameQa"], "NOT_RUN")

    def test_reject_mismatched_source_identity(self):
        self.data["sourceCommit"] = "b" * 40
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_native_receipt_claiming_device_pass(self):
        self.data["deviceQa"] = "PASS"
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_wrong_backend(self):
        self.data["scriptingBackend"] = "Mono2x"
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_non_aarch64_elf(self):
        self.entries["lib/arm64-v8a/libil2cpp.so"] = b"not-elf" * 20
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_other_abi(self):
        self.entries["lib/x86/libunity.so"] = b"synthetic"
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_missing_native_il2cpp(self):
        del self.entries["lib/arm64-v8a/libil2cpp.so"]
        with self.assertRaises(ValueError):
            self.verify()

    def test_reject_unexpected_resolved_package_version(self):
        self.packages.write_text(self.packages.read_text().replace("1.20.1", "1.0.0"))
        with self.assertRaises(ValueError):
            self.verify()


class FontSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "SYNTHETIC-NOT-A-FONT.xz"
        self.dest = Path(self.tmp.name) / "restored-synthetic.txt"
        self.raw = b"SYNTHETIC FONT RESTORE VALIDATOR TEST; NOT REAL FONT BYTES\n"
        self.source.write_bytes(lzma.compress(self.raw))
        self.comp_sha = ci.digest(self.source)
        self.raw_sha = hashlib.sha256(self.raw).hexdigest()

    def restore(self):
        return ci.restore_font(self.source, self.dest, self.comp_sha, self.raw_sha, len(self.raw))

    def test_synthetic_restore_and_idempotency(self):
        self.restore()
        self.restore()
        self.assertEqual(self.dest.read_bytes(), self.raw)

    def test_reject_corrupt_compressed_bytes(self):
        self.source.write_bytes(self.source.read_bytes() + b"bad")
        with self.assertRaises(ValueError):
            self.restore()
        self.assertFalse(self.dest.exists())

    def test_reject_wrong_restored_hash(self):
        self.raw_sha = "0" * 64
        with self.assertRaises(ValueError):
            self.restore()
        self.assertFalse(self.dest.exists())

    def test_reject_wrong_existing_font_without_overwrite(self):
        self.dest.write_bytes(b"keep-existing")
        with self.assertRaises(ValueError):
            self.restore()
        self.assertEqual(self.dest.read_bytes(), b"keep-existing")

    def test_reject_concatenated_xz_streams(self):
        self.source.write_bytes(self.source.read_bytes() + lzma.compress(b"extra"))
        self.comp_sha = ci.digest(self.source)
        with self.assertRaises(ValueError):
            self.restore()

    def test_reject_decompressed_length_overrun(self):
        with self.assertRaises(ValueError):
            ci.restore_font(self.source, self.dest, self.comp_sha, self.raw_sha, 2)

    def test_reject_destination_symlink(self):
        other = Path(self.tmp.name) / "other.txt"
        other.write_bytes(b"must-remain")
        self.dest.symlink_to(other)
        with self.assertRaises(ValueError):
            self.restore()
        self.assertEqual(other.read_bytes(), b"must-remain")


class SourceMutationSyntheticTests(unittest.TestCase):
    def test_each_pinned_linux_toolchain_dependency_is_required_in_resolved_lock(self):
        names = ("com.unity.sdk.linux-arm64", "com.unity.sdk.linux-x86_64", "com.unity.toolchain.linux-x86_64-linux")
        for name in names:
            for mode in ("missing", "wrong-version"):
                with self.subTest(name=name, mode=mode):
                    lock = {"dependencies": {key: {"version": version} for key, version in ci.PACKAGES.items()}}
                    if mode == "missing":
                        del lock["dependencies"][name]
                    else:
                        lock["dependencies"][name]["version"] = "1.1.1"
                    with self.assertRaises(ValueError):
                        ci.validate_resolved_lock(lock)

    def test_unreviewed_toolchain_dependency_mutation_still_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task = root / ci.TASK
            manifest = task / "unity/Packages/manifest.json"
            ci.write_json(manifest, {"dependencies": ci.PACKAGES})
            ci.snapshot_project(root)
            altered = dict(ci.PACKAGES)
            altered["com.unity.toolchain.linux-x86_64-linux"] = "1.1.1"
            ci.write_json(manifest, {"dependencies": altered})
            with self.assertRaises(ValueError):
                ci.audit(root, {"sourceCommit": "a" * 40})
            self.assertEqual(json.loads((task / "evidence/source-mutations.json").read_text())["status"], "FAIL")

    def test_lock_arrays_produce_fail_receipt_instead_of_attribute_error(self):
        bad_locks = [[], {"dependencies": []}, {"dependencies": {name: [] for name in ci.PACKAGES}},
                     {"dependencies": {name: {"version": version, "dependencies": []} for name, version in ci.PACKAGES.items()}}]
        for lock in bad_locks:
            with self.subTest(lock=lock), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                task = root / ci.TASK
                ci.write_json(task / "evidence/pre-unity-source.json", {})
                ci.write_json(task / "unity/Packages/packages-lock.json", lock)
                with self.assertRaisesRegex(ValueError, "bounded diagnostic receipt saved"):
                    ci.audit(root, {"sourceCommit": "a" * 40})
                receipt = json.loads((task / "evidence/source-mutations.json").read_text())
                self.assertEqual(receipt["status"], "FAIL")
                self.assertEqual(receipt["failedStage"], "VALIDATE_RESOLVED_LOCK")
                self.assertFalse((task / "evidence/generated-assets.zip").exists())

    def test_manifest_format_only_requires_actual_baseline_and_preserves_both_byte_sequences(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task = root / ci.TASK
            manifest = task / "unity/Packages/manifest.json"
            ci.write_json(manifest, {"dependencies": ci.PACKAGES})
            original = manifest.read_bytes()
            ci.snapshot_project(root)
            changed = json.dumps({"dependencies": ci.PACKAGES}, separators=(",", ":")).encode()
            manifest.write_bytes(changed)
            ci.write_json(task / "unity/Packages/packages-lock.json", {
                "dependencies": {name: {"version": version} for name, version in ci.PACKAGES.items()}})
            ci.audit(root, {"sourceCommit": "a" * 40})
            receipt = json.loads((task / "evidence/source-mutations.json").read_text())
            self.assertEqual(receipt["status"], "PASS")
            row = next(row for row in receipt["changes"] if row["path"] == "Packages/manifest.json")
            self.assertEqual(row["kind"], "MANIFEST_FORMAT_ONLY")
            self.assertEqual((task / "evidence/manifest-before.json").read_bytes(), original)
            self.assertEqual((task / "evidence/manifest-after.json").read_bytes(), changed)

    def test_manifest_semantic_change_is_diagnosed_but_still_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task = root / ci.TASK
            manifest = task / "unity/Packages/manifest.json"
            ci.write_json(manifest, {"dependencies": ci.PACKAGES})
            ci.snapshot_project(root)
            altered = dict(ci.PACKAGES, **{"com.unity.inputsystem": "1.20.0"})
            ci.write_json(manifest, {"dependencies": altered})
            with self.assertRaises(ValueError):
                ci.audit(root, {"sourceCommit": "a" * 40})
            receipt = json.loads((task / "evidence/source-mutations.json").read_text())
            diagnostic = json.loads((task / "evidence/manifest-diagnostic.json").read_text())
            self.assertEqual(receipt["status"], "FAIL")
            self.assertEqual(diagnostic["semanticComparison"], "DIFFERENT")
            self.assertEqual(diagnostic["changedPackages"], [{"name": "com.unity.inputsystem", "before": "1.20.1", "after": "1.20.0"}])
            self.assertTrue((task / "evidence/manifest-after.json").is_file())
            self.assertFalse((task / "evidence/generated-assets.zip").exists())

    def test_manifest_without_matching_baseline_is_never_format_only(self):
        with tempfile.TemporaryDirectory() as temp:
            task = Path(temp)
            (task / "evidence").mkdir()
            path = task / "unity/Packages/manifest.json"
            ci.write_json(path, {"dependencies": ci.PACKAGES})
            self.assertFalse(ci.capture_manifest_change(task, "a" * 64, ci.digest(path)))
            (task / "evidence/manifest-baseline.internal.json").write_bytes(path.read_bytes())
            self.assertFalse(ci.capture_manifest_change(task, "a" * 64, ci.digest(path)))

    def test_refused_before_baseline_cannot_remain_in_public_artifact_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task = root / ci.TASK
            manifest = task / "unity/Packages/manifest.json"
            ci.write_json(manifest, {"dependencies": ci.PACKAGES})
            ci.snapshot_project(root)
            internal = task / "evidence/manifest-baseline.internal.json"
            public_before = task / "evidence/manifest-before.json"
            self.assertTrue(internal.is_file())
            self.assertFalse(public_before.exists())
            marker = b"SYNTHETIC-UNSAFE-BASELINE-MUST-NOT-BE-UPLOADED"
            internal.write_bytes(marker)
            # An old or tampered export must also be removed before revalidation.
            public_before.write_bytes(marker)
            manifest.write_bytes(json.dumps({"dependencies": ci.PACKAGES}, separators=(",", ":")).encode())
            with self.assertRaises(ValueError):
                ci.audit(root, {"sourceCommit": "a" * 40})
            diagnostic = json.loads((task / "evidence/manifest-diagnostic.json").read_text())
            self.assertEqual(diagnostic["beforeExport"], "REFUSED_OR_UNAVAILABLE")
            self.assertFalse(public_before.exists())
            self.assertNotIn(marker, (task / "evidence/manifest-diagnostic.json").read_bytes())
            self.assertEqual(json.loads((task / "evidence/source-mutations.json").read_text())["status"], "FAIL")
            workflow = Path(ci.__file__).resolve().parents[3] / ".github/workflows/lottery-g0.yml"
            self.assertNotIn("evidence/manifest-baseline.internal.json", workflow.read_text())

    def test_manifest_diagnostic_rejects_arbitrary_content_urls_arrays_and_duplicate_keys(self):
        bad = [[], {"dependencies": []}, {"dependencies": {"com.unity.inputsystem": "https://private.invalid/token"}},
               {"dependencies": ci.PACKAGES, "credentials": "synthetic"}, {"dependencies": {"other.organization.package": "1.0.0"}}]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(ValueError):
                ci.parse_diagnostic_manifest(json.dumps(data).encode())
        with self.assertRaises(ValueError):
            ci.parse_diagnostic_manifest(b'{"dependencies":{"com.unity.inputsystem":"synthetic-secret","com.unity.inputsystem":"1.20.1"}}')

    def test_unsafe_manifest_bytes_are_not_exported(self):
        with tempfile.TemporaryDirectory() as temp:
            task = Path(temp)
            (task / "evidence").mkdir()
            path = task / "unity/Packages/manifest.json"
            ci.write_json(path, {"dependencies": {"com.unity.inputsystem": "synthetic-private-string"}})
            self.assertFalse(ci.capture_manifest_change(task, None, ci.digest(path)))
            self.assertFalse((task / "evidence/manifest-after.json").exists())
            self.assertNotIn("synthetic-private-string", (task / "evidence/manifest-diagnostic.json").read_text())

    def test_failed_audit_records_path_classification_and_hash_without_source_contents(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task = root / ci.TASK
            source = task / "unity/Assets/Unexpected.asset"
            source.parent.mkdir(parents=True)
            source.write_text("SYNTHETIC-CONTENT-MUST-NOT-ENTER-DIAGNOSTIC")
            ci.write_json(task / "evidence/pre-unity-source.json", {})
            with self.assertRaises(ValueError):
                ci.audit(root, {"sourceCommit": "a" * 40})
            receipt_path = task / "evidence/source-mutations.json"
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(receipt["status"], "FAIL")
            self.assertEqual(receipt["failedStage"], "VALIDATE_SOURCE_MUTATIONS")
            self.assertEqual(receipt["changes"], [{"path": "Assets/Unexpected.asset", "kind": "UNEXPECTED_SOURCE_CHANGE",
                            "beforeSha256": None, "afterSha256": ci.digest(source)}])
            self.assertNotIn("SYNTHETIC-CONTENT-MUST-NOT-ENTER-DIAGNOSTIC", receipt_path.read_text())
            self.assertFalse((task / "evidence/generated-assets.zip").exists())

    def test_failed_lock_audit_also_records_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task = root / ci.TASK
            ci.write_json(task / "evidence/pre-unity-source.json", {})
            with self.assertRaises(ValueError):
                ci.audit(root, {"sourceCommit": "a" * 40})
            receipt = json.loads((task / "evidence/source-mutations.json").read_text())
            self.assertEqual(receipt["status"], "FAIL")
            self.assertEqual(receipt["failedStage"], "VALIDATE_RESOLVED_LOCK")

    def test_diagnostic_metadata_rejects_noncanonical_paths_and_nonhash_payload(self):
        for path in ("/absolute/file", "Assets/../outside", "Assets//double", "Assets/new\nline.asset", "Assets/x@private.invalid"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                ci.diagnostic_changes([{"path": path, "kind": "ignored", "beforeSha256": None, "afterSha256": "a" * 64}])
        with self.assertRaises(ValueError):
            ci.diagnostic_changes([{"path": "Assets/Ok.asset", "beforeSha256": None, "afterSha256": "arbitrary-content"}])

    def test_fixed_diagnostic_receipt_does_not_claim_candidate_or_persistence(self):
        receipt = ci.diagnostic_receipt({"sourceCommit": "a" * 40}, "failure", "skipped", "failure")
        self.assertEqual(receipt["status"], "DIAGNOSTIC_ONLY_NOT_APK_CANDIDATE")
        self.assertEqual(receipt["evidencePersistence"], "EVIDENCE_PERSISTENCE_PENDING")
        with self.assertRaises(ValueError):
            ci.diagnostic_receipt({}, "arbitrary log contents", "success", "success")

    def test_accept_exact_four_urp_initialization_outputs(self):
        changes = ci.inspect_mutations({}, {name: "synthetic-sha" for name in ci.URP_GENERATED_GLOBAL_ASSETS})
        self.assertEqual(len(changes), 4)
        self.assertEqual({item["kind"] for item in changes}, {"URP_GENERATED_GLOBAL_SETTING"})

    def test_reject_adjacent_unknown_urp_assets(self):
        for name in ("Assets/Unknown.asset", "Assets/Unknown.asset.meta",
                     "Assets/DefaultVolumeProfileExtra.asset", "Assets/DefaultVolumeProfileExtra.asset.meta",
                     "Assets/UniversalRenderPipelineGlobalSettings2.asset",
                     "Assets/UniversalRenderPipelineGlobalSettings2.asset.meta",
                     "Assets/Subfolder/DefaultVolumeProfile.asset"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                ci.inspect_mutations({}, {name: "synthetic-sha"})

    def test_archive_retains_all_four_urp_assets_with_separate_classification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task = root / ci.TASK
            for name in ci.URP_GENERATED_GLOBAL_ASSETS:
                path = task / "unity" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("SYNTHETIC UNIT FIXTURE, NOT A UNITY ASSET\n")
            ci.write_json(task / "unity/Packages/packages-lock.json", {
                "dependencies": {name: {"version": version} for name, version in ci.PACKAGES.items()}})
            ci.write_json(task / "evidence/pre-unity-source.json", {})
            ci.audit(root, {"sourceCommit": "a" * 40})
            with zipfile.ZipFile(task / "evidence/generated-assets.zip") as archive:
                self.assertTrue(ci.URP_GENERATED_GLOBAL_ASSETS <= set(archive.namelist()))
            manifest = json.loads((task / "evidence/generated-manifest.json").read_text())
            selected = [item for item in manifest["files"] if item["path"] in ci.URP_GENERATED_GLOBAL_ASSETS]
            self.assertEqual(len(selected), 4)
            self.assertTrue(all(item["kind"] == "URP_GENERATED_GLOBAL_SETTING" for item in selected))

    def test_accept_named_generated_assets(self):
        result = ci.inspect_mutations({}, {"Assets/GeneratedProbe/Probe.unity": "a"})
        self.assertEqual(result[0]["kind"], "GENERATED_PROBE_ASSET")

    def test_reject_runtime_or_editor_code_change(self):
        for name in ("Assets/Runtime/ProbeRuntime.cs", "Assets/Editor/ProbeBuild.cs",
                     "Assets/GeneratedProbe/Unreviewed.cs", "Packages/manifest.json",
                     "ProjectSettings/ProjectVersion.txt"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                ci.inspect_mutations({name: "a"}, {name: "b"})

    def test_reject_deleted_settings(self):
        with self.assertRaises(ValueError):
            ci.inspect_mutations({"ProjectSettings/ProjectSettings.asset": "a"}, {})

    def test_classify_lock_settings_and_font_meta_separately(self):
        changes = ci.inspect_mutations({}, {"Packages/packages-lock.json": "a",
                    "ProjectSettings/GraphicsSettings.asset": "b", "Assets/Resources/ProbeChinese.otf.meta": "c"})
        self.assertEqual({item["kind"] for item in changes},
                         {"RESOLVED_PACKAGE_LOCK", "UNITY_PROJECT_SETTING", "FONT_IMPORT_METADATA"})


if __name__ == "__main__":
    unittest.main()
