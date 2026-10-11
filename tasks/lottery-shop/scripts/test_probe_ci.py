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
                ci.require_safe_xml(value.encode())


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
