#!/usr/bin/env python3
"""Bounded G0 CI validation. No credentials, network calls, or gameplay claims.

Local unit fixtures exercise the validator only. They are never Unity evidence.
"""
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

REPOSITORY = "yangerstar1/task-workbench"
OWNER = "yangerstar1"
BRANCH = "lottery-shop-g0-20261011"
BASE = "22525198f7865d055af937f5e828243023d6ad31"
TASK = "tasks/lottery-shop"
REQUEST_PATH = TASK + "/ci/g0-request.json"
REQUEST = {"schemaVersion": 1, "requestId": "lottery-g0-20261012-02",
           "baseCommit": BASE, "purpose": "G0_TECHNICAL_PROBE"}
VERSION = "6000.3.19f1"
SCOPE = "G0_TECHNICAL_PROBE_NOT_GAME_NOT_DEVICE_TESTED"
FONT_COMPRESSED_SHA = "e8affaf0b8f8e8fccecf5476bf05999c891f94ef66ef9b55474fda32ce1ec786"
FONT_SHA = "a6a530f3e7e7a2c299470c42efff2e109fcc0a5be92686b96d5e84a05f3ecb2b"
FONT_SIZE = 16437340
OFL_SHA = "0e22ba35da45f9dfc194dd2f5dd7cbc2169c19d01aa42597ce1e7c01c2b88a13"
EXPECTED_CASES = {"Lottery.Probe.Tests.ProbeTests." + name for name in (
    "EditorPatchPinned", "RequiredPackagesResolved", "UrpAssetsSurviveReimport",
    "ChineseFontContainsRequiredGlyphs", "InputBackendAndLifecycle", "SceneReferencesFontAndUrpMaterial")}
PACKAGES = {"com.unity.render-pipelines.universal": "17.3.0",
            "com.unity.inputsystem": "1.20.1", "com.unity.test-framework": "1.6.0"}
# Exact URP 17.3 initialization outputs, not a general Assets/*.asset exemption.
# Unity-Technologies/Graphics@2d2e78cc9d6254bc6e7c9c5552cea053508e86cb
# Runtime/UniversalRenderPipelineGlobalSettings.cs defines both asset paths.
URP_GENERATED_GLOBAL_ASSETS = {
    "Assets/UniversalRenderPipelineGlobalSettings.asset",
    "Assets/UniversalRenderPipelineGlobalSettings.asset.meta",
    "Assets/DefaultVolumeProfile.asset",
    "Assets/DefaultVolumeProfile.asset.meta",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bounded_read(path, limit):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "Required regular evidence file missing")
    require(path.stat().st_size <= limit, "Evidence exceeds size limit")
    return path.read_bytes()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def validate_guard(env, event, request, head, changed):
    """Pure guard; tests supply synthetic metadata, production loads GitHub's file."""
    expected = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push",
                "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REPOSITORY_OWNER": OWNER,
                "GITHUB_ACTOR": OWNER, "GITHUB_TRIGGERING_ACTOR": OWNER,
                "GITHUB_REF": "refs/heads/" + BRANCH,
                "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux"}
    for key, value in expected.items():
        require(env.get(key) == value, "Untrusted execution context: " + key)
    require(re.fullmatch(r"[0-9a-f]{40}", head) is not None, "Invalid source commit")
    require(env.get("GITHUB_SHA") == head and event.get("after") == head,
            "Event/checkout source commit mismatch")
    require(event.get("ref") == "refs/heads/" + BRANCH, "Event ref mismatch")
    require(event.get("deleted") is False, "Deleted or malformed push")
    repo = event.get("repository", {})
    require(repo.get("full_name") == REPOSITORY and repo.get("private") is False
            and repo.get("fork") is False, "Only the original public repository is permitted")
    require(repo.get("owner", {}).get("login") == OWNER, "Repository owner mismatch")
    require(event.get("sender", {}).get("login") == OWNER, "Push sender mismatch")
    require(request == REQUEST and type(request.get("schemaVersion")) is int,
            "Request document does not match the single approved probe")
    require(REQUEST_PATH in changed, "The unique request file must change in the triggering commit")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(re.fullmatch(r"[1-9][0-9]*", env.get(key, "")) is not None, "Invalid run identity")
    return {"sourceCommit": head, "runId": env["GITHUB_RUN_ID"],
            "runAttempt": env["GITHUB_RUN_ATTEMPT"], "requestId": request["requestId"],
            "scope": SCOPE, "deviceQa": "NOT_RUN", "renderedFrameQa": "NOT_RUN"}


def guard(root):
    event = json.loads(bounded_read(os.environ["GITHUB_EVENT_PATH"], 4 * 1024 * 1024))
    request = json.loads(bounded_read(root / REQUEST_PATH, 4096))
    head = git(root, "rev-parse", "HEAD")
    changed = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()
    data = validate_guard(os.environ, event, request, head, changed)
    # Checkout includes history, so the pinned original base must be an ancestor.
    subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", BASE, head], check=True)
    write_json(root / TASK / "evidence/guard-receipt.json", data)
    return data


def restore_font(source, destination, compressed_sha=FONT_COMPRESSED_SHA,
                 font_sha=FONT_SHA, font_size=FONT_SIZE):
    """Arguments are exposed for synthetic unit fixtures, never CLI overrides."""
    source, destination = Path(source), Path(destination)
    require(not source.is_symlink(), "Font source must not be a symlink")
    require(source.is_file() and source.stat().st_size <= 12 * 1024 * 1024, "Font archive missing or oversized")
    require(digest(source) == compressed_sha, "Compressed font SHA-256 mismatch")
    # Stream with a hard decompressed bound; reject concatenated/trailing payloads.
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=128 * 1024 * 1024)
    raw = decoder.decompress(source.read_bytes(), max_length=font_size + 1)
    require(decoder.eof and not decoder.unused_data, "Invalid or oversized compressed font stream")
    require(len(raw) == font_size, "Restored font byte length mismatch")
    require(hashlib.sha256(raw).hexdigest() == font_sha, "Restored font SHA-256 mismatch")
    require(not destination.is_symlink(), "Font destination must not be a symlink")
    if destination.exists():
        require(digest(destination) == font_sha, "Refusing to overwrite a different font")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_name(destination.name + ".restoring")
        require(not temp.exists() and not temp.is_symlink(), "Temporary font path already exists")
        with temp.open("xb") as stream:
            stream.write(raw)
        temp.replace(destination)
    return {"compressedSha256": compressed_sha, "fontSha256": font_sha,
            "fontBytes": font_size, "status": "BYTE_HASH_VERIFIED_NOT_GLYPH_OR_DEVICE_QA"}


def restore(root):
    task = root / TASK
    receipt = restore_font(task / "fonts/NotoSansCJKsc-Regular.otf.xz",
                           task / "unity/Assets/Resources/ProbeChinese.otf")
    license_text = bounded_read(task / "fonts/OFL.txt", 20000).decode("utf-8")
    require(digest(task / "fonts/OFL.txt") == OFL_SHA, "Complete OFL license hash mismatch")
    attribution = bounded_read(task / "fonts/ATTRIBUTION.txt", 10000).decode("utf-8")
    require("SIL OPEN FONT LICENSE Version 1.1" in license_text and "DISCLAIMER" in license_text,
            "Complete font license missing")
    require("2014–2021 Adobe" in attribution, "Font copyright notice missing")
    license_path = task / "unity/Assets/Resources/ProbeFontLicense.txt"
    require(not license_path.is_symlink(), "License destination must not be a symlink")
    license_path.write_text(attribution + "\n\n" + license_text, encoding="utf-8")
    receipt["embeddedLicenseSha256"] = digest(license_path)
    write_json(task / "evidence/font-receipt.json", receipt)


def load_test_report(directory):
    candidates = []
    for path in sorted(Path(directory).rglob("*.xml")):
        raw = bounded_read(path, 10 * 1024 * 1024)
        require(b"<!DOCTYPE" not in raw and b"<!ENTITY" not in raw, "DTD/entity test XML is rejected")
        parsed = ET.fromstring(raw)
        if parsed.tag == "test-run":
            candidates.append((path, parsed))
    require(len(candidates) == 1, "Expected exactly one real NUnit test-run report")
    return candidates[0]


def require_safe_xml(raw):
    """Conservative content checks without loading any actual credential values.

    This intentionally fails closed on credential-like content; it is not a
    general data-loss-prevention guarantee. No report is exported on rejection.
    """
    require(len(raw) <= 10 * 1024 * 1024, "Test XML exceeds size limit")
    require(b"<!DOCTYPE" not in raw and b"<!ENTITY" not in raw, "DTD/entity test XML is rejected")
    text = raw.decode("utf-8-sig")
    report = ET.fromstring(raw)
    patterns = (r"(?i)\b(?:password|passwd|unity_license|unity_email|unity_password|access[_-]?token|api[_-]?key|client[_-]?secret|authorization|bearer)\b",
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
                r"\bAKIA[0-9A-Z]{16}\b", r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
    values = [text]
    for node in report.iter():
        values.extend(node.attrib.keys())
        values.extend(node.attrib.values())
        values.extend(value for value in (node.text, node.tail) if value is not None)
    require(not any(re.search(pattern, value) for pattern in patterns for value in values),
            "Raw NUnit XML export refused: potential credential or private identifier content")


def export_raw_test_report(directory, evidence):
    path, report = load_test_report(directory)
    raw = bounded_read(path, 10 * 1024 * 1024)
    require_safe_xml(raw)
    target = Path(evidence) / "raw-test-results.xml"
    target.write_bytes(raw)
    write_json(Path(evidence) / "raw-test-report-receipt.json", {
        "rawXmlSha256": digest(target), "bytes": len(raw),
        "status": "PRESERVED_ORIGINAL_NOT_A_PASS_VERDICT",
        "screening": "BOUNDED_XML_AND_CREDENTIAL_PATTERN_CHECK_NO_SECRET_VALUE_ACCESS"})
    return report


def inspect_tests(directory):
    path, report = load_test_report(directory)
    cases = list(report.iter("test-case"))
    names = [case.get("fullname") for case in cases]
    require(len(cases) == 6 and set(names) == EXPECTED_CASES,
            "All six exact named tests are required, without duplicates or extras")
    require(report.get("result") == "Passed", "NUnit run is not Passed")
    for key, expected in {"total": 6, "passed": 6, "failed": 0, "skipped": 0, "inconclusive": 0}.items():
        require(report.get(key) == str(expected), "NUnit count mismatch: " + key)
    require(all(case.get("result") == "Passed" for case in cases), "A test failed, was skipped, or is inconclusive")
    assemblies = [node for node in report.iter("test-suite") if node.get("type") == "Assembly"]
    require(len(assemblies) == 1 and assemblies[0].get("name") == "Lottery.Probe.Tests.dll"
            and assemblies[0].get("result") == "Passed", "Unexpected or missing test assembly")
    assembly_cases = list(assemblies[0].iter("test-case"))
    require(len(assembly_cases) == 6 and set(assembly_cases) == set(cases),
            "Every test case must belong to the unique expected Assembly")
    require(all(node.get("result") == "Passed" for node in report.iter("test-suite")), "A test suite did not pass")
    return path, report, {"passed": 6, "failed": 0, "skipped": 0, "inconclusive": 0,
                          "cases": sorted(names), "rawXmlSha256": digest(path),
                          "testScope": "EDITOR_STATIC_ASSET_AND_API_CHECKS",
                          "renderedFrameQa": "NOT_RUN", "touchEventInjectionQa": "NOT_RUN",
                          "deviceQa": "NOT_RUN", "gameplayQa": "NOT_RUN"}


def save_safe_test_xml(report, target):
    """Avoid logs, command lines, arbitrary properties, output and stack traces."""
    safe = ET.Element("test-run", {key: report.get(key, "") for key in
                      ("result", "total", "passed", "failed", "skipped", "inconclusive")})
    for case in report.iter("test-case"):
        name = case.get("fullname", "")
        require(name in EXPECTED_CASES, "Unexpected test identity cannot be published")
        ET.SubElement(safe, "test-case", {"fullname": name, "result": case.get("result", "")})
    ET.indent(safe)
    ET.ElementTree(safe).write(target, encoding="utf-8", xml_declaration=True)


def snapshot_files(root):
    project = root / TASK / "unity"
    files = {}
    for dirname in ("Assets", "Packages", "ProjectSettings"):
        for path in sorted((project / dirname).rglob("*")):
            require(not path.is_symlink(), "Symlink in Unity source tree")
            if path.is_file():
                require(path.stat().st_size <= 32 * 1024 * 1024, "Unexpectedly large Unity source asset")
                files[path.relative_to(project).as_posix()] = digest(path)
                require(len(files) <= 1024, "Unexpectedly many Unity source files")
    return files


def parse_diagnostic_manifest(raw):
    """Only small official-registry package/version maps may become artifacts."""
    require(len(raw) <= 64 * 1024, "Manifest diagnostic exceeds size limit")
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate manifest key rejected")
            result[key] = value
        return result
    data = json.loads(raw, object_pairs_hook=unique_keys)
    require(isinstance(data, dict) and set(data) == {"dependencies"}, "Manifest diagnostic schema rejected")
    dependencies = data["dependencies"]
    require(isinstance(dependencies, dict) and len(dependencies) <= 128, "Manifest dependency map rejected")
    for name, version in dependencies.items():
        require(isinstance(name, str) and re.fullmatch(r"com\.unity\.[a-z0-9][a-z0-9._-]{0,99}", name),
                "Manifest package identity rejected")
        require(isinstance(version, str) and re.fullmatch(r"[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:-[a-z0-9.]{1,32})?", version),
                "Manifest non-pinned or non-registry version rejected")
    return data


def snapshot_project(root):
    task = root / TASK
    (task / "evidence").mkdir(parents=True, exist_ok=True)
    (task / "evidence/manifest-before.json").unlink(missing_ok=True)
    (task / "evidence/manifest-after.json").unlink(missing_ok=True)
    files = snapshot_files(root)
    raw = bounded_read(task / "unity/Packages/manifest.json", 64 * 1024)
    parse_diagnostic_manifest(raw)
    require(hashlib.sha256(raw).hexdigest() == files.get("Packages/manifest.json"), "Manifest changed during snapshot")
    # Baseline is private to the validator and is never an artifact input.
    (task / "evidence/manifest-baseline.internal.json").write_bytes(raw)
    write_json(task / "evidence/pre-unity-source.json", files)


def capture_manifest_change(task, before_hash, after_hash):
    """Preserve reviewed-shaped actual bytes; never treat a semantic change as OK."""
    receipt = {"path": "Packages/manifest.json", "beforeSha256": before_hash, "afterSha256": after_hash,
               "status": "DIAGNOSTIC_ONLY_NOT_A_MUTATION_APPROVAL", "semanticComparison": "UNAVAILABLE",
               "beforeExport": "UNAVAILABLE", "afterExport": "UNAVAILABLE"}
    decoded = {}
    (task / "evidence/manifest-before.json").unlink(missing_ok=True)
    (task / "evidence/manifest-after.json").unlink(missing_ok=True)
    for label, path, expected_hash in (
        ("before", task / "evidence/manifest-baseline.internal.json", before_hash),
        ("after", task / "unity/Packages/manifest.json", after_hash)):
        try:
            raw = bounded_read(path, 64 * 1024)
            require(hashlib.sha256(raw).hexdigest() == expected_hash, "Manifest snapshot identity mismatch")
            data = parse_diagnostic_manifest(raw)
            (task / ("evidence/manifest-" + label + ".json")).write_bytes(raw)
            decoded[label] = data
            receipt[label + "Export"] = "SAFE_SCHEMA_ACTUAL_BYTES"
        except (ValueError, OSError, TypeError):
            receipt[label + "Export"] = "REFUSED_OR_UNAVAILABLE"
    if set(decoded) == {"before", "after"}:
        before = decoded["before"]["dependencies"]
        after = decoded["after"]["dependencies"]
        identical = before == after
        receipt["semanticComparison"] = "IDENTICAL" if identical else "DIFFERENT"
        receipt["addedPackages"] = [{"name": name, "version": after[name]} for name in sorted(after.keys() - before.keys())]
        receipt["removedPackages"] = [{"name": name, "version": before[name]} for name in sorted(before.keys() - after.keys())]
        receipt["changedPackages"] = [{"name": name, "before": before[name], "after": after[name]}
                                      for name in sorted(before.keys() & after.keys()) if before[name] != after[name]]
    write_json(task / "evidence/manifest-diagnostic.json", receipt)
    return receipt["semanticComparison"] == "IDENTICAL"


def validate_resolved_lock(data):
    require(isinstance(data, dict), "Resolved lock root must be an object")
    dependencies = data.get("dependencies")
    require(isinstance(dependencies, dict) and len(dependencies) <= 256, "Resolved lock dependencies must be a bounded object")
    require(all(isinstance(name, str) and isinstance(entry, dict) for name, entry in dependencies.items()),
            "Resolved lock package entries must be objects")
    for entry in dependencies.values():
        require(isinstance(entry.get("version"), str), "Resolved lock versions must be strings")
        if "dependencies" in entry:
            require(isinstance(entry["dependencies"], dict)
                    and all(isinstance(name, str) and isinstance(version, str) for name, version in entry["dependencies"].items()),
                    "Resolved lock transitive dependencies must be a string map")
    for name, version in PACKAGES.items():
        require(dependencies.get(name, {}).get("version") == version, "Resolved lock mismatch: " + name)


def mutation_kind(path):
    if path in URP_GENERATED_GLOBAL_ASSETS:
        return "URP_GENERATED_GLOBAL_SETTING"
    if (path.startswith("Assets/GeneratedProbe/") or path == "Assets/GeneratedProbe.meta") and Path(path).suffix in {".asset", ".meta", ".mat", ".unity"}:
        return "GENERATED_PROBE_ASSET"
    if path.startswith("ProjectSettings/") and "/" not in path[len("ProjectSettings/"):] and Path(path).suffix in {".asset", ".txt"} and path != "ProjectSettings/ProjectVersion.txt":
        return "UNITY_PROJECT_SETTING"
    if path in {"ProjectSettings/SceneTemplateSettings.json", "ProjectSettings/boot.config"}:
        return "UNITY_PROJECT_SETTING"
    if path == "Packages/packages-lock.json":
        return "RESOLVED_PACKAGE_LOCK"
    if path in {"Assets/Resources/ProbeChinese.otf.meta", "Assets/Resources/ProbeFontLicense.txt.meta"}:
        return "FONT_IMPORT_METADATA"
    return "UNEXPECTED_SOURCE_CHANGE"


def collect_mutations(before, after, manifest_format_only=False):
    return [{"path": path, "beforeSha256": before.get(path), "afterSha256": after.get(path),
                "kind": "MANIFEST_FORMAT_ONLY" if manifest_format_only and path == "Packages/manifest.json"
                        and before.get(path) is not None and after.get(path) is not None else mutation_kind(path)}
               for path in sorted(before.keys() | after.keys())
               if before.get(path) != after.get(path)]


def inspect_mutations(before, after, manifest_format_only=False):
    changes = collect_mutations(before, after, manifest_format_only)
    require(all(item["kind"] != "UNEXPECTED_SOURCE_CHANGE" and item["afterSha256"] is not None
                for item in changes), "Unexpected source mutation or deletion during Unity execution")
    return changes


def diagnostic_changes(changes):
    """Bounded path/class/hash metadata only; never copy source or error text."""
    require(len(changes) <= 1024, "Too many source changes for diagnostic receipt")
    result = []
    for item in changes:
        path = item["path"]
        require(isinstance(path, str) and len(path) <= 240
                and re.fullmatch(r"(?:Assets|Packages|ProjectSettings)/[A-Za-z0-9_. /-]+", path)
                and all(part not in {"", ".", ".."} for part in path.split("/")),
                "Noncanonical source path cannot be exported")
        for key in ("beforeSha256", "afterSha256"):
            value = item[key]
            require(value is None or (isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)),
                    "Malformed source hash cannot be exported")
        kind = "MANIFEST_FORMAT_ONLY" if path == "Packages/manifest.json" and item.get("kind") == "MANIFEST_FORMAT_ONLY" else mutation_kind(path)
        result.append({"path": path, "kind": kind,
                       "beforeSha256": item["beforeSha256"], "afterSha256": item["afterSha256"]})
    return result


def audit(root, identity):
    task = root / TASK
    changes = []
    stage = "READ_SOURCE_BASELINE"
    try:
        before = json.loads(bounded_read(task / "evidence/pre-unity-source.json", 1024 * 1024))
        require(isinstance(before, dict) and len(before) <= 1024, "Malformed source baseline")
        require(all(isinstance(key, str) and isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                    for key, value in before.items()), "Malformed source baseline hash map")
        stage = "SNAPSHOT_SOURCE"
        after = snapshot_files(root)
        manifest_format_only = False
        if before.get("Packages/manifest.json") != after.get("Packages/manifest.json"):
            stage = "CAPTURE_MANIFEST_DIAGNOSTIC"
            manifest_format_only = capture_manifest_change(task, before.get("Packages/manifest.json"), after.get("Packages/manifest.json"))
        stage = "VALIDATE_SOURCE_MUTATIONS"
        changes = collect_mutations(before, after, manifest_format_only)
        safe_changes = diagnostic_changes(changes)
        inspect_mutations(before, after, manifest_format_only)
        # Validate the resolved lock before exposing any generated archive.
        stage = "VALIDATE_RESOLVED_LOCK"
        lock = task / "unity/Packages/packages-lock.json"
        require(lock.is_file(), "Unity did not produce its resolved package lock")
        lock_data = json.loads(bounded_read(lock, 1024 * 1024))
        validate_resolved_lock(lock_data)
        stage = "ARCHIVE_GENERATED_EVIDENCE"
        selected = sorted(path for path in after if mutation_kind(path) in
                          {"GENERATED_PROBE_ASSET", "URP_GENERATED_GLOBAL_SETTING", "UNITY_PROJECT_SETTING",
                           "FONT_IMPORT_METADATA", "RESOLVED_PACKAGE_LOCK"})
        total = 0
        manifest = []
        archive_temp = task / "evidence/generated-assets.zip.tmp"
        with zipfile.ZipFile(archive_temp, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in selected:
                path = task / "unity" / name
                size = path.stat().st_size
                total += size
                require(size <= 8 * 1024 * 1024 and total <= 32 * 1024 * 1024, "Generated evidence too large")
                archive.write(path, name)
                manifest.append({"path": name, "sha256": after[name], "bytes": size, "kind": mutation_kind(name)})
        archive_temp.replace(task / "evidence/generated-assets.zip")
        write_json(task / "evidence/generated-manifest.json", {"files": manifest, "sourceCommit": identity["sourceCommit"]})
        shutil.copyfile(lock, task / "evidence/packages-lock.json")
        write_json(task / "evidence/source-mutations.json", dict(identity, status="PASS",
                   scopeOfPass="SOURCE_MUTATIONS_EXPLICITLY_ACCOUNTED_NOT_CLEAN_SOURCE",
                   changes=safe_changes, generatedArtifactsRebuiltInEachJob=True))
    except (ValueError, OSError, KeyError, TypeError) as error:
        try:
            safe_changes = diagnostic_changes(changes)
            metadata_status = "CANONICAL_PATH_KIND_HASH_ONLY"
        except (ValueError, KeyError, TypeError):
            safe_changes = []
            metadata_status = "REJECTED_NONCANONICAL_METADATA"
        write_json(task / "evidence/source-mutations.json", dict(identity, status="FAIL",
                   failedStage=stage, metadataStatus=metadata_status, changes=safe_changes))
        raise ValueError("Source audit failed; bounded diagnostic receipt saved") from error


def diagnostic_receipt(identity, unity_outcome, verify_outcome, audit_outcome):
    allowed = {"success", "failure", "cancelled", "skipped", "unknown"}
    require(all(value in allowed for value in (unity_outcome, verify_outcome, audit_outcome)),
            "Unexpected workflow outcome cannot be exported")
    return dict(identity, status="DIAGNOSTIC_ONLY_NOT_APK_CANDIDATE",
                unityStep=unity_outcome, apkVerificationStep=verify_outcome, sourceAuditStep=audit_outcome,
                deviceQa="NOT_RUN", renderedFrameQa="NOT_RUN", evidencePersistence="EVIDENCE_PERSISTENCE_PENDING")


def inspect_apk(apk, native_receipt, packages_path, identity):
    apk = Path(apk)
    receipt = json.loads(bounded_read(native_receipt, 64 * 1024))
    for key, expected in {"sourceCommit": identity["sourceCommit"], "runId": identity["runId"],
                          "unityVersion": VERSION, "scope": SCOPE, "deviceQa": "NOT_RUN",
                          "renderedFrameQa": "NOT_RUN", "gameplayQa": "NOT_RUN",
                          "signing": "development-debug", "buildResult": "Succeeded",
                          "buildTarget": "Android", "scriptingBackend": "IL2CPP", "architecture": "ARM64",
                          "minSdk": 26, "targetSdk": 35, "graphicsApis": "OpenGLES3"}.items():
        require(receipt.get(key) == expected, "Native build receipt mismatch: " + key)
    require(VERSION in receipt.get("editorRevision", "") and "7689f4515d75" in receipt.get("editorRevision", ""),
            "Editor revision mismatch")
    require(apk.is_file() and not apk.is_symlink() and 1024 * 1024 < apk.stat().st_size < 512 * 1024 * 1024,
            "APK missing or implausible byte size")
    require(receipt.get("apkBytes") == apk.stat().st_size and receipt.get("apkSha256") == digest(apk),
            "APK hash or size mismatch")
    with zipfile.ZipFile(apk) as archive:
        entries = archive.infolist()
        names = {entry.filename for entry in entries}
        require(len(names) == len(entries) and len(entries) < 100000, "Duplicate or excessive APK entries")
        required = {"AndroidManifest.xml", "classes.dex", "lib/arm64-v8a/libil2cpp.so", "lib/arm64-v8a/libunity.so"}
        require(required <= names, "APK lacks Android ARM64 IL2CPP content")
        require(all(not name.startswith("lib/") or name.startswith("lib/arm64-v8a/") for name in names),
                "APK contains an unexpected native ABI")
        require(sum(entry.file_size for entry in entries) <= 1024 * 1024 * 1024, "APK expanded size too large")
        for name in ("lib/arm64-v8a/libil2cpp.so", "lib/arm64-v8a/libunity.so"):
            with archive.open(name) as stream:
                header = stream.read(64)
            require(len(header) >= 20 and header[:6] == b"\x7fELF\x02\x01"
                    and int.from_bytes(header[18:20], "little") == 183,
                    "Native binary is not little-endian ELF64 AArch64")
        require(archive.testzip() is None, "APK ZIP integrity failure")
    lines = bounded_read(packages_path, 64 * 1024).decode("utf-8").splitlines()
    require(len(lines) < 256 and all(re.fullmatch(r"[a-z0-9][a-z0-9._-]*@[a-zA-Z0-9.+_-]+", line) for line in lines),
            "Malformed resolved-package list")
    require(len(lines) == len(set(lines)), "Duplicate resolved-package rows")
    packages = dict(line.split("@", 1) for line in lines)
    for name, version in PACKAGES.items():
        require(packages.get(name) == version, "Registered package mismatch: " + name)
    return dict(identity, apkSha256=digest(apk), apkBytes=apk.stat().st_size,
                verification="APK_SHA256_ZIP_CRC_AND_AARCH64_ELF64_IL2CPP_ENTRIES",
                nativeReceiptSha256=digest(native_receipt), resolvedPackagesSha256=digest(packages_path),
                signingVerification="NATIVE_RECEIPT_DECLARATION_ONLY_NOT_CERTIFICATE_VERIFIED",
                deviceQa="NOT_RUN", renderedFrameQa="NOT_RUN", touchEventInjectionQa="NOT_RUN", gameplayQa="NOT_RUN")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("guard", "restore-font", "snapshot", "audit", "tests", "apk", "diagnostics"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--unity-outcome", default="unknown")
    parser.add_argument("--verify-outcome", default="unknown")
    parser.add_argument("--audit-outcome", default="unknown")
    args = parser.parse_args()
    root = args.root.resolve()
    task = root / TASK
    evidence = task / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    if args.command == "restore-font":
        restore(root)
    elif args.command == "snapshot":
        snapshot_project(root)
    else:
        identity = guard(root)
        if args.command == "audit":
            audit(root, identity)
        elif args.command == "diagnostics":
            write_json(evidence / "diagnostic-receipt.json", diagnostic_receipt(identity, args.unity_outcome,
                       args.verify_outcome, args.audit_outcome))
        elif args.command == "tests":
            report = export_raw_test_report(task / "artifacts/tests", evidence)
            save_safe_test_xml(report, evidence / "test-results.xml")
            _, report, result = inspect_tests(task / "artifacts/tests")
            write_json(evidence / "test-receipt.json", dict(result, **identity))
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                output.write("test_count=6\n")
        elif args.command == "apk":
            result = inspect_apk(task / "build/Android/LotteryG0.apk", task / "build/Android/build-receipt.json",
                                 task / "build/Android/resolved-packages.txt", identity)
            write_json(evidence / "apk-receipt.json", result)
    print("G0 " + args.command + " verification complete; device and rendered-frame QA remain NOT_RUN.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError, ET.ParseError, lzma.LZMAError, subprocess.CalledProcessError) as error:
        # Only our bounded messages, never complete logs or environment dumps.
        print("G0 verification failed: " + str(error), file=sys.stderr)
        sys.exit(1)
