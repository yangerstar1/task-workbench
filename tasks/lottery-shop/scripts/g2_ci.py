#!/usr/bin/env python3
"""G2 stage adapter around the bounded G0 validators. No credential access/network."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import xml.etree.ElementTree as ET
import zlib

_spec = importlib.util.spec_from_file_location("g2_g0_helpers", Path(__file__).with_name("probe_ci.py"))
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)
TASK = legacy.TASK
BASE = "7211d28a277ae0d7316b293e6d8d8a00e55a9784"
RULES_SHA = "e959108cb2a4ef080862565de5b87814ccdfae14026204227e767d049bbdf668"
MANIFEST_SHA = "95bb5ada418c6d596d622ebd1a2e0f0b6d24422f3e525c622958cb492bae3eb2"
LOCK_SHA = "950e703b31453d45443719e88b1a37025d40d388df07c9c3bed31b507fd2f132"
VECTORS_SHA = "22af609400604776d2801955946dacd35a057edb0563d3a6069848f6be8adcd9"
SCOPE = "G2_TECHNICAL_SLICE_NOT_DEVICE_TESTED"
REQUEST = {"schemaVersion": 1, "requestId": "lottery-g2-20261012-02", "baseCommit": BASE, "purpose": "G2_TECHNICAL_SLICE"}
G0_CASES = set(legacy.EXPECTED_CASES)
SCENE = "Assets/G2/Scenes/G2Slice.unity"
GENERATED = {SCENE, SCENE + ".meta", "Assets/G2/Scenes.meta"}
_ORIGINAL_KIND = legacy.mutation_kind
legacy.BASE, legacy.SCOPE, legacy.REQUEST = BASE, SCOPE, REQUEST
legacy.PACKAGES = dict(legacy.PACKAGES, **{"com.unity.modules.imageconversion": "1.0.0"})
legacy.REQUEST_PATH = TASK + "/ci/g2-request.json"
legacy.mutation_kind = lambda path: "G2_GENERATED_SCENE" if path in GENERATED else _ORIGINAL_KIND(path)
require, digest, bounded_read, write_json = legacy.require, legacy.digest, legacy.bounded_read, legacy.write_json
FRAMES = ("initial", "half", "revealed", "settled")
SAFE_COMMON = ("guard-receipt.json", "font-receipt.json", "source-mutations.json", "manifest-before.json",
               "manifest-after.json", "manifest-diagnostic.json")
SAFE_GENERATED = ("generated-manifest.json", "generated-assets.zip", "packages-lock.json")


_SETTING_KEY = re.compile(r'^\s*(?:-\s*)?["\']?([A-Za-z_][A-Za-z0-9_.-]*)["\']?\s*:\s*(.*?)\s*$')
_CREDENTIAL_KEY = re.compile(r'password|passwd|passcode|secret|token|private.?key|api.?key|credential|license', re.I)


def settings_findings(root):
    """Fail closed on nonempty credential-like fields; never return source values."""
    directory = root / TASK / "unity/ProjectSettings"
    require(directory.is_dir() and not directory.is_symlink(), "Missing/unsafe ProjectSettings directory")
    findings = []
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(root / TASK / "unity").as_posix()
        require(re.fullmatch(r"ProjectSettings/[A-Za-z0-9_./-]+", relative), "Unsafe settings path")
        require(not path.is_symlink(), "Settings symlink refused")
        if path.is_dir(): continue
        raw = bounded_read(path, 2 * 1024 * 1024)
        value = raw.decode("utf-8", errors="strict")
        for line in value.splitlines():
            field = _SETTING_KEY.fullmatch(line)
            if not field or not _CREDENTIAL_KEY.search(field.group(1)): continue
            # Native Unity YAML scalar fields only. A block/list/map is nonempty
            # and refused too. An optional trailing YAML comment contains no value.
            scalar = field.group(2).split(" #", 1)[0].strip()
            if scalar not in {"", '""', "''", "null", "Null", "NULL", "~"}:
                findings.append({"path": relative, "kind": "NONEMPTY_CREDENTIAL_SETTING",
                                 "sha256": hashlib.sha256(raw).hexdigest()})
                break
    return findings


def source_preflight(root):
    require(not settings_findings(root), "Credential-bearing settings refused")


def verify_inputs(root):
    source_preflight(root)
    task = root / TASK
    require(digest(task / "unity/Packages/manifest.json") == MANIFEST_SHA, "Reviewed G2 dependency manifest mismatch")
    require(digest(task / "data/g1-rules.json") == RULES_SHA, "Frozen G1 runtime rules mismatch")
    require(digest(task / "unity/Packages/packages-lock.json") == LOCK_SHA, "Frozen resolved package lock mismatch")
    require(digest(task / "data/g1-number-face-vectors.json") == VECTORS_SHA, "Frozen G1 vector bytes mismatch")
    vectors = json.loads(bounded_read(task / "data/g1-number-face-vectors.json", 128 * 1024))
    require(vectors.get("rulesSha256") == RULES_SHA and len(vectors.get("numberFaces", [])) == 16,
            "Frozen number-face vector binding mismatch")


def load_contract(path):
    data = json.loads(bounded_read(path, 64 * 1024))
    require(isinstance(data, dict) and set(data) == {"schemaVersion", "status", "rulesSha256", "profiles"}
            and data["schemaVersion"] == 1 and data["status"] == "FROZEN_FOR_CI"
            and data["rulesSha256"] == RULES_SHA, "G2 test contract is not frozen")
    profiles = data["profiles"]
    require(isinstance(profiles, dict) and set(profiles) == {"edit", "play"}, "Unexpected G2 profiles")
    for profile, assemblies in profiles.items():
        required = {"Lottery.Probe.Tests.dll", "Lottery.G2.EditMode.Tests.dll"} if profile == "edit" else {"Lottery.G2.PlayMode.Tests.dll"}
        require(isinstance(assemblies, dict) and set(assemblies) == required, "Unexpected assembly contract")
        names = []
        for assembly, cases in assemblies.items():
            require(isinstance(cases, list) and 0 < len(cases) <= 256 and
                    all(isinstance(x, str) and re.fullmatch(r"Lottery\.[A-Za-z0-9_.]+", x) for x in cases),
                    "Invalid exact case identities")
            names.extend(cases)
        require(len(names) == len(set(names)), "Duplicate contracted test identities")
    require(set(profiles["edit"]["Lottery.Probe.Tests.dll"]) == G0_CASES, "G0 six-case regression changed")
    return profiles


def inspect_tests(directory, assemblies):
    path, report = legacy.load_test_report(directory)
    legacy.require_safe_xml(bounded_read(path, 10 * 1024 * 1024))
    expected = {name for cases in assemblies.values() for name in cases}
    cases = list(report.iter("test-case"))
    require(len(cases) == len(expected) and {x.get("fullname") for x in cases} == expected, "Exact G2 cases mismatch")
    require(report.get("result") == "Passed", "G2 NUnit run did not pass")
    for key, n in {"total": len(expected), "passed": len(expected), "failed": 0, "skipped": 0, "inconclusive": 0}.items():
        require(report.get(key) == str(n), "G2 NUnit count mismatch")
    suites = [x for x in report.iter("test-suite") if x.get("type") == "Assembly"]
    require(len(suites) == len(assemblies) and {x.get("name") for x in suites} == set(assemblies), "G2 assembly mismatch")
    owned = []
    for suite in suites:
        children = list(suite.iter("test-case")); wanted = assemblies[suite.get("name")]
        require(len(children) == len(wanted) and {x.get("fullname") for x in children} == set(wanted), "Test case assembly ownership mismatch")
        owned.extend(children)
    require(len(owned) == len(cases) and set(owned) == set(cases), "Orphaned or nested G2 cases")
    require(all(x.get("result") == "Passed" for x in cases + list(report.iter("test-suite"))), "Non-passing G2 case/suite")
    return path, report, {"passed": len(expected), "failed": 0, "skipped": 0, "inconclusive": 0,
                          "assemblies": assemblies, "rawXmlSha256": digest(path)}


def export_tests(task, profile, identity):
    out = task / "evidence/g2" / profile
    out.mkdir(parents=True, exist_ok=True)
    for name in ("raw-test-results.xml", "raw-test-report-receipt.json", "test-results.xml", "test-receipt.json"):
        (out / name).unlink(missing_ok=True)
    assemblies = load_contract(task / "ci/g2-test-contract.json")[profile]
    directory = task / ("artifacts/g2-" + profile)
    # Keep safe original failed XML too; safety screening precedes every export.
    legacy.export_raw_test_report(directory, out)
    path, report, result = inspect_tests(directory, assemblies)
    safe = ET.Element("test-run", {k: report.get(k, "") for k in ("result", "total", "passed", "failed", "skipped", "inconclusive")})
    for suite in [n for n in report.iter("test-suite") if n.get("type") == "Assembly"]:
        target = ET.SubElement(safe, "test-suite", {"type": "Assembly", "name": suite.get("name"), "result": "Passed"})
        for case in suite.iter("test-case"):
            ET.SubElement(target, "test-case", {"fullname": case.get("fullname"), "result": "Passed"})
    ET.indent(safe); ET.ElementTree(safe).write(out / "test-results.xml", encoding="utf-8", xml_declaration=True)
    write_json(out / "test-receipt.json", dict(identity, **result, profile=profile,
               scopeOfPass="EXACT_NATIVE_TEST_CASES_NOT_DEVICE_QA", deviceQa="NOT_RUN", visualReview="PENDING"))
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write(profile + "_passed=true\n")


def audit_stage(root, stage, identity):
    task = root / TASK; common = task / "evidence"; out = common / "g2" / stage
    out.mkdir(parents=True, exist_ok=True)
    for name in SAFE_COMMON + SAFE_GENERATED:
        (out / name).unlink(missing_ok=True)
    (common / "source-mutations.json").unlink(missing_ok=True)
    success = False
    try:
        findings = settings_findings(root)
        if findings:
            write_json(common / "source-mutations.json", dict(identity, status="FAIL",
                       failedStage="SETTINGS_CREDENTIAL_PREFLIGHT", metadataStatus="NO_SOURCE_CONTENT_EXPORTED",
                       changes=findings))
            raise ValueError("Credential-bearing generated settings refused")
        legacy.audit(root, identity, additional_generated_kinds=("G2_GENERATED_SCENE",))
        # Exact restored lock is immutable in G2, not merely six matching package versions.
        if digest(task / "unity/Packages/packages-lock.json") != LOCK_SHA:
            receipt = json.loads(bounded_read(common / "source-mutations.json", 1024 * 1024))
            receipt.update(status="FAIL", failedStage="PINNED_G2_RESOLVED_LOCK")
            write_json(common / "source-mutations.json", receipt)
            raise ValueError("G2 lock changed after import")
        success = True
    except Exception:
        if not (common / "source-mutations.json").is_file():
            write_json(common / "source-mutations.json", dict(identity, status="FAIL",
                       failedStage="G2_SOURCE_AUDIT", metadataStatus="NO_SOURCE_CONTENT_EXPORTED", changes=[]))
        raise
    finally:
        for name in SAFE_COMMON + (SAFE_GENERATED if success else ()):
            source = common / name
            if source.is_file() and not source.is_symlink():
                require(source.stat().st_size <= 32 * 1024 * 1024, "Stage evidence too large")
                shutil.copyfile(source, out / name)


def png_dimensions(raw):
    """Bounded original PNG verification; rejects metadata payloads and broken CRC."""
    require(raw[:8] == b"\x89PNG\r\n\x1a\n" and len(raw) <= 4 * 1024 * 1024, "Invalid/oversize capture PNG")
    offset, chunks, ids = 8, [], []
    while offset < len(raw):
        require(offset + 12 <= len(raw), "Truncated PNG chunk")
        size = struct.unpack(">I", raw[offset:offset + 4])[0]; kind = raw[offset + 4:offset + 8]
        require(size <= 4 * 1024 * 1024 and offset + 12 + size <= len(raw), "PNG chunk exceeds bound")
        value = raw[offset + 8:offset + 8 + size]
        crc = struct.unpack(">I", raw[offset + 8 + size:offset + 12 + size])[0]
        require(zlib.crc32(kind + value) & 0xffffffff == crc, "PNG chunk CRC mismatch")
        require(kind in {b"IHDR", b"IDAT", b"IEND", b"sRGB", b"gAMA", b"cHRM", b"pHYs"}, "Unapproved PNG metadata")
        if kind in {b"sRGB", b"gAMA", b"cHRM", b"pHYs"}:
            require(size == {b"sRGB": 1, b"gAMA": 4, b"cHRM": 32, b"pHYs": 9}[kind], "PNG metadata size mismatch")
        chunks.append((kind, value)); offset += 12 + size
        if kind == b"IDAT": ids.append(value)
        if kind == b"IEND": break
    kinds = [k for k, _ in chunks]
    require(bool(kinds) and offset == len(raw) and kinds[0] == b"IHDR" and kinds[-1] == b"IEND" and
            kinds.count(b"IHDR") == 1 and chunks[-1][1] == b"" and ids, "PNG structure mismatch")
    require(len(chunks[0][1]) == 13, "PNG header mismatch")
    w, h, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
    require((w, h) == (1280, 720) and depth == 8 and color in {2, 6} and
            compression == filtering == interlace == 0, "PNG dimensions/format mismatch")
    bpp = 3 if color == 2 else 4; stride = w * bpp; count = (stride + 1) * h
    dec = zlib.decompressobj(); pixels = dec.decompress(b"".join(ids), count + 1)
    require(len(pixels) == count and dec.eof and not dec.unused_data and not dec.unconsumed_tail, "PNG pixel stream mismatch")
    # Reconstruct filters to distinguish a real varied frame from a flat image.
    previous = bytearray(stride); colors = set()
    for y in range(h):
        start = y * (stride + 1); filter_type = pixels[start]; row = bytearray(pixels[start + 1:start + 1 + stride])
        require(filter_type <= 4, "Unsupported PNG row filter")
        for i in range(stride) if filter_type else ():
            a = row[i - bpp] if i >= bpp else 0; b = previous[i]; c = previous[i - bpp] if i >= bpp else 0
            if filter_type == 1: p = a
            elif filter_type == 2: p = b
            elif filter_type == 3: p = (a + b) // 2
            elif filter_type == 4:
                q = a + b - c; da, db, dc = abs(q - a), abs(q - b), abs(q - c)
                p = a if da <= db and da <= dc else (b if db <= dc else c)
            else: p = 0
            row[i] = (row[i] + p) & 255
        if len(colors) <= 16:
            colors.update(bytes(row[i:i + 3]) for i in range(0, stride, bpp))
        previous = row
    require(len(colors) > 16, "Capture is empty/flat or insufficiently varied")
    return w, h


def inspect_captures(source, identity):
    source = Path(source)
    raw = bounded_read(source / "render-receipt.json", 64 * 1024); data = json.loads(raw)
    keys = {"schemaVersion", "scope", "sourceCommit", "runId", "unityVersion", "rulesSha256", "captureMethod",
            "graphicsDeviceType", "graphicsDeviceName", "width", "height", "sourceViewportWidth", "sourceViewportHeight",
            "inputEvidence", "deviceQa", "visualReview", "frames"}
    require(isinstance(data, dict) and set(data) == keys, "Render receipt schema mismatch")
    fixed = {"schemaVersion": 1, "scope": "G2_CAMERA_RENDER_NOT_DEVICE_TESTED", "sourceCommit": identity["sourceCommit"],
             "runId": identity["runId"], "unityVersion": legacy.VERSION, "rulesSha256": RULES_SHA,
             "captureMethod": "URP_STANDARD_REQUEST_READPIXELS", "width": 1280, "height": 720,
             "inputEvidence": "SIMULATED_INPUT_SYSTEM", "deviceQa": "NOT_RUN", "visualReview": "PENDING"}
    require(all(data.get(k) == v for k, v in fixed.items()), "Render receipt identity/scope mismatch")
    require(type(data["schemaVersion"]) is int and all(type(data[k]) is int and 64 <= data[k] <= 8192
            for k in ("sourceViewportWidth", "sourceViewportHeight")), "Actual viewport metadata missing")
    for key in ("graphicsDeviceType", "graphicsDeviceName"):
        require(isinstance(data[key], str) and re.fullmatch(r"[A-Za-z0-9_., ()/+:-]{1,200}", data[key]) and
                "null" not in data[key].lower(), "Missing/invalid actual graphics device")
    frames = data["frames"]
    require(isinstance(frames, list) and len(frames) == 4 and all(isinstance(x, dict) for x in frames) and [x.get("stage") for x in frames] == list(FRAMES), "Four ordered native frames required")
    for frame in frames:
        require(set(frame) == {"stage", "file", "sha256", "bytes", "stateSha256"} and
                frame["file"] == frame["stage"] + ".png" and
                re.fullmatch(r"[0-9a-f]{64}", frame["stateSha256"] or ""), "Render frame metadata mismatch")
        path = source / frame["file"]; image = bounded_read(path, 4 * 1024 * 1024)
        require(frame["sha256"] == digest(path) and type(frame["bytes"]) is int and frame["bytes"] == len(image), "Frame hash/size mismatch")
        png_dimensions(image)
    require(len({f["sha256"] for f in frames}) == 4 and len({f["stateSha256"] for f in frames}) == 4,
            "Distinct actual frame/state evidence missing")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("source-preflight", "guard", "restore-font", "snapshot", "audit", "tests", "captures", "apk", "diagnostics"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--stage", choices=("edit", "play", "android"), default="edit")
    parser.add_argument("--unity-outcome", default="unknown"); parser.add_argument("--verify-outcome", default="unknown"); parser.add_argument("--audit-outcome", default="unknown")
    args = parser.parse_args(); root = args.root.resolve(); task = root / TASK
    if args.command == "source-preflight":
        source_preflight(root)
        print("G2 source settings preflight PASS; no source values exported.")
        return
    (task / "evidence").mkdir(parents=True, exist_ok=True)
    # Every CI invocation checks event identity. There is no dispatch or write token.
    identity = legacy.guard(root)
    identity.update(rulesSha256=RULES_SHA, g0SourceBase=BASE)
    out = task / "evidence/g2" / args.stage; out.mkdir(parents=True, exist_ok=True)
    write_json(out / "guard-receipt.json", identity)
    if args.command == "guard":
        verify_inputs(root); load_contract(task / "ci/g2-test-contract.json")
    elif args.command == "restore-font": legacy.restore(root)
    elif args.command == "snapshot":
        verify_inputs(root); legacy.snapshot_project(root)
    elif args.command == "audit": audit_stage(root, args.stage, identity)
    elif args.command == "tests":
        require(args.stage in {"edit", "play"}, "Tests require edit/play stage")
        export_tests(task, args.stage, identity)
    elif args.command == "captures":
        for name in [x + ".png" for x in FRAMES] + ["render-receipt.json"]:
            (out / name).unlink(missing_ok=True)
        source = task / "artifacts/g2-play/captures"; data = inspect_captures(source, identity)
        for name in [x + ".png" for x in FRAMES] + ["render-receipt.json"]:
            shutil.copyfile(source / name, out / name)
    elif args.command == "apk":
        directory = task / "build/G2/Android"
        native = json.loads(bounded_read(directory / "build-receipt.json", 64 * 1024))
        require(native.get("rulesSha256") == RULES_SHA and native.get("runtimeScene") == SCENE
                and native.get("fakeAd") == "DEVELOPMENT_FAKE_ONLY", "G2 native scene/rules binding mismatch")
        result = legacy.inspect_apk(directory / "LotteryG2.apk", directory / "build-receipt.json", directory / "resolved-packages.txt", identity)
        write_json(out / "apk-receipt.json", result)
    elif args.command == "diagnostics":
        write_json(out / "diagnostic-receipt.json", legacy.diagnostic_receipt(identity, args.unity_outcome, args.verify_outcome, args.audit_outcome))
    print("G2 " + args.command + " completed; device QA remains NOT_RUN.")


if __name__ == "__main__":
    try: main()
    except Exception:
        # Never echo an arbitrary XML/JSON/path/exception payload from evidence.
        print("G2 verification failed; inspect bounded receipts and failing step.", file=sys.stderr)
        sys.exit(1)
