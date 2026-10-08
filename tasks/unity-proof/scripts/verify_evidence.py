#!/usr/bin/env python3
"""Validate native evidence; never treat a skipped/empty Unity run as a pass."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

EXPECTED_VERSION = "6000.3.19f1"
EXPECTED_CASES = {
    "CIProof.NativeProofTests.EditorVersionIsPinned",
    "CIProof.NativeProofTests.TransformHierarchyPreservesExpectedWorldPosition",
    "CIProof.NativeProofTests.NativeColliderRaycastHitsExpectedSurface",
    "CIProof.NativeProofTests.NativeAnimationSamplesIntermediatePose",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def identity():
    commit = os.environ["GITHUB_SHA"]
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    require(actual == commit, "Checkout differs from requested commit")
    return {"commit": commit, "runId": os.environ["GITHUB_RUN_ID"],
            "runAttempt": os.environ["GITHUB_RUN_ATTEMPT"], "editorVersion": EXPECTED_VERSION}


def inspect_tests(directory):
    candidates = []
    for path in Path(directory).rglob("*.xml"):
        require(path.stat().st_size <= 10 * 1024 * 1024, "Unexpectedly large test XML")
        root = ET.parse(path).getroot()
        if root.tag == "test-run":
            candidates.append((path, root))
    require(len(candidates) == 1, "Expected exactly one NUnit test-run report")
    path, root = candidates[0]
    cases = list(root.iter("test-case"))
    names = [case.attrib.get("fullname") for case in cases]
    require(len(cases) == 4 and set(names) == EXPECTED_CASES,
            "Expected all four named native tests, without duplicates or omissions")
    require(root.attrib.get("result") == "Passed", "NUnit run did not pass")
    require(all(case.attrib.get("result") == "Passed" for case in cases),
            "A native test failed or was skipped")
    require(int(root.attrib.get("total", "-1")) == 4, "NUnit total is not four")
    require(int(root.attrib.get("passed", "-1")) == 4, "NUnit passed count is not four")
    require(int(root.attrib.get("failed", "-1")) == 0, "NUnit contains failures")
    return path, {"passed": 4, "failed": 0, "cases": sorted(names), "xmlSha256": digest(path)}


def preserve_test_reports(directory, evidence):
    """Keep bounded original NUnit XML even when native tests failed."""
    saved = []
    total = 0
    for path in sorted(Path(directory).rglob("*.xml")):
        size = path.stat().st_size
        require(size <= 10 * 1024 * 1024, "Unexpectedly large test XML")
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            continue
        if root.tag != "test-run":
            continue
        total += size
        require(len(saved) < 4 and total <= 20 * 1024 * 1024, "Too much native test evidence")
        target = evidence / ("original-tests-" + str(len(saved) + 1) + ".xml")
        shutil.copyfile(path, target)
        saved.append({"file": target.name, "bytes": size, "sha256": digest(target)})
    (evidence / "test-report-collection.json").write_text(
        json.dumps({"files": saved, "status": "COLLECTED_ONLY_NOT_A_VERDICT"}, indent=2) + "\n")


def inspect_apk(apk, receipt, expected_identity):
    apk, receipt = Path(apk), Path(receipt)
    require(apk.is_file() and receipt.is_file(), "APK or native receipt missing")
    data = json.loads(receipt.read_text())
    for key, expected in {"schema": "desert-rv-ci-proof/v1", "editorVersion": EXPECTED_VERSION,
                          "commit": expected_identity["commit"],
                          "workflowRunId": expected_identity["runId"],
                          "editModeTestsPassed": 4, "buildTarget": "Android",
                          "scriptingBackend": "IL2CPP", "architecture": "ARM64",
                          "buildResult": "Succeeded", "apkRelativePath": "build/Android/Proof.apk"}.items():
        require(data.get(key) == expected, "Native build receipt mismatch: " + key)
    require(apk.stat().st_size > 1024 * 1024, "APK is implausibly small")
    require(data.get("apkBytes") == apk.stat().st_size, "APK size mismatch")
    require(data.get("apkSha256") == digest(apk), "APK hash mismatch")
    with zipfile.ZipFile(apk) as archive:
        names = set(archive.namelist())
        required = {"AndroidManifest.xml", "classes.dex", "lib/arm64-v8a/libil2cpp.so",
                    "lib/arm64-v8a/libunity.so"}
        require(required <= names, "APK lacks required Android/ARM64 IL2CPP content")
        require(archive.testzip() is None, "APK ZIP CRC validation failed")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["tests", "apk"])
    args = parser.parse_args()
    evidence = Path("evidence")
    evidence.mkdir(exist_ok=True)
    base = identity()
    if args.mode == "tests":
        preserve_test_reports("artifacts/tests", evidence)
        path, result = inspect_tests("artifacts/tests")
        shutil.copyfile(path, evidence / "test-results.xml")
        result.update(base)
        result["scope"] = "Four original CI smoke tests, not Desert RV gameplay acceptance"
        (evidence / "test-receipt.json").write_text(json.dumps(result, indent=2) + "\n")
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("test_count=4\n")
        print("Four native EditMode tests passed; XML and commit identity verified.")
    else:
        result = inspect_apk("build/Android/Proof.apk", "build/Android/build-receipt.json", base)
        result.update({"verifier": "independent Python SHA256 and ZIP structure/CRC",
                       "runAttempt": base["runAttempt"], "deviceExecution": "NOT_RUN"})
        (evidence / "apk-receipt.json").write_text(json.dumps(result, indent=2) + "\n")
        with (evidence / "SHA256SUMS").open("w") as f:
            for path in [Path("build/Android/Proof.apk"), Path("build/Android/build-receipt.json")]:
                f.write(digest(path) + "  " + path.as_posix() + "\n")
        print("New ARM64 IL2CPP APK hash and exact commit verified. Device execution remains untested.")


if __name__ == "__main__":
    main()
