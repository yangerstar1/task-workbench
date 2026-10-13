#!/usr/bin/env python3
"""Diagnostic Unity visual candidate evidence. Never a G3 approval or device gate.

Reuses only the existing bounded font and NUnit XML utilities, not old source
approvals or G3 guard receipts. No credential values, full Unity logs, generated
project settings, caches, or source-file contents are exported.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

import probe_ci as bounded

TASK = "tasks/lottery-shop"
SCOPE = "DIAGNOSTIC_VISUAL_CANDIDATE_NOT_G3_PASS"
REQUEST = TASK + "/ci/visual-candidate-request.json"
WORKFLOW = ".github/workflows/lottery-visual-candidate.yml"
ASSEMBLY = "Lottery.G3.VisualCandidate.Tests.dll"
CASE = "Lottery.G3.VisualCandidate.Tests.VisualCandidateCaptureTests.RealRuntimeSixGroupsRetainHudAndRoutePurchasesScratchShelfAndNight"
FRAMES = ["entry-whole-shop", "table-empty", "number-half", "number-half-20x9",
          "challenge-two-safe-three-tools", "shelf-before-open", "shelf-after-open",
          "challenge-returned-from-shelf", "closing-day-table", "night-table", "night-bill"]
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
STAGES = ("capture", "regression-edit", "regression-play")


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return bounded.digest(path)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    require(len(result.stdout) <= 8 * 1024 * 1024, "Git metadata output exceeds bound")
    return result.stdout.decode("utf-8").strip()


def outdir(root):
    return root / TASK / "evidence/visual-candidate"


def read_json(path, maximum=2 * 1024 * 1024):
    return json.loads(bounded.bounded_read(path, maximum))


def guard(root):
    env = os.environ
    for key, value in {"GITHUB_EVENT_NAME": "push", "GITHUB_REPOSITORY": "yangerstar1/task-workbench",
                       "GITHUB_REPOSITORY_OWNER": "yangerstar1", "GITHUB_ACTOR": "yangerstar1",
                       "GITHUB_TRIGGERING_ACTOR": "yangerstar1", "GITHUB_REF": "refs/heads/lottery-shop-g0-20261011"}.items():
        require(env.get(key) == value, "Unexpected diagnostic execution context: " + key)
    event = read_json(Path(env["GITHUB_EVENT_PATH"]))
    require(event.get("repository", {}).get("private") is False and event["repository"].get("fork") is False and not event.get("deleted"), "Unexpected repository event")
    source = env.get("GITHUB_SHA", "")
    require(HEX40.fullmatch(source) and source == git(root, "rev-parse", "HEAD"), "Source commit mismatch")
    request = read_json(root / REQUEST, 8192)
    require(set(request) == {"schemaVersion", "requestId", "sourceCommit", "purpose", "sourceReview"}, "Diagnostic request keys mismatch")
    require(request["schemaVersion"] == 1 and request["purpose"] == SCOPE, "Request is not a diagnostic visual candidate")
    require(re.fullmatch(r"lottery-visual-[0-9]{8}-[0-9]{2,3}", request["requestId"]), "Invalid request identity")
    require(HEX40.fullmatch(request["sourceCommit"]) and request["sourceCommit"] == git(root, "rev-parse", "HEAD^"), "Trigger must directly follow the separately reviewed candidate source")
    review = request["sourceReview"]
    require(isinstance(review, dict) and set(review) == {"sourceCommit", "status", "reviewedAtUtc", "reviewId", "reviewer"}, "Bounded independent source-review receipt required")
    require(review["sourceCommit"] == request["sourceCommit"] and review["status"] == "APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY" and review["reviewer"] == "independent-source-review", "Source review does not cover this candidate")
    require(re.fullmatch(r"visual-source-[0-9]{8}-[0-9]{2,3}", review["reviewId"]), "Invalid independent review identity")
    reviewed_at = datetime.fromisoformat(review["reviewedAtUtc"].replace("Z", "+00:00"))
    require(reviewed_at.tzinfo is not None and reviewed_at.utcoffset().total_seconds() == 0 and reviewed_at <= datetime.now(timezone.utc), "Invalid review UTC timestamp")
    changed = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()
    require(changed == [REQUEST], "Trigger commit must change only visual-candidate-request.json")
    require(git(root, "diff", "--name-only", "HEAD", "--", TASK, WORKFLOW) == "", "Checkout changed before candidate guard")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(re.fullmatch(r"[1-9][0-9]*", env.get(key, "")), "Invalid run identity")
    identity = {"scope": SCOPE, "sourceCommit": source, "reviewedCandidateCommit": request["sourceCommit"],
                "requestId": request["requestId"], "runId": env["GITHUB_RUN_ID"], "runAttempt": env["GITHUB_RUN_ATTEMPT"],
                "deviceQa": "NOT_RUN", "g3Gate": "NOT_EVALUATED", "sourceApproval": "FIXED_ACTOR_ATTESTED_INDEPENDENT_DIAGNOSTIC_REVIEW_NOT_CRYPTOGRAPHIC_SIGNATURE", "sourceReview": review}
    write(outdir(root) / "source-receipt.json", identity)
    return identity


def identity(root):
    value = read_json(outdir(root) / "source-receipt.json", 8192)
    require(value.get("scope") == SCOPE and value.get("sourceCommit") == os.environ.get("GITHUB_SHA"), "Source receipt mismatch")
    return value


def snapshot(root, after=False):
    # Hash committed project inputs only. No file contents or ProjectSettings
    # content is copied to evidence, and no runtime Library/Logs tree is scanned.
    names = git(root, "ls-files", "--", TASK + "/unity/Assets", TASK + "/unity/Packages",
                TASK + "/unity/ProjectSettings", TASK + "/scripts", WORKFLOW, REQUEST).splitlines()
    records = []
    for name in sorted(names):
        path = root / name
        require(path.is_file() and not path.is_symlink(), "Committed source input is not a regular file")
        records.append({"path": name, "sha256": sha(path), "bytes": path.stat().st_size})
    payload = dict(identity(root), status="SOURCE_HASH_METADATA_ONLY", files=records)
    write(outdir(root) / ("source-after.json" if after else "source-before.json"), payload)
    if after:
        before = read_json(outdir(root) / "source-before.json")
        old = {x["path"]: x for x in before["files"]}
        changes = [x["path"] for x in records if old.get(x["path"]) != x]
        write(outdir(root) / "source-changes.json", dict(identity(root), changedPaths=changes,
              note="DIAGNOSTIC_ONLY_IMPORT_GENERATION_AND_SETTINGS_CHANGES_REQUIRE_REVIEW"))


def export_tests(root, stage):
    source = root / TASK / "artifacts" / ("visual-candidate" if stage == "capture" else "visual-" + stage)
    target = outdir(root) / stage
    target.mkdir(parents=True, exist_ok=True)
    report = bounded.export_raw_test_report(source, target)
    cases = list(report.iter("test-case"))
    assemblies = [x for x in report.iter("test-suite") if x.get("type") == "Assembly"]
    if stage == "capture":
        expected = {ASSEMBLY: [CASE]}
    else:
        g2 = read_json(root / TASK / "ci/g2-test-contract.json")
        g3 = read_json(root / TASK / "ci/g3-test-contract.json")
        profile = "edit" if stage == "regression-edit" else "play"
        expected = dict(g2["profiles"][profile])
        for name, names in g3["profiles"][profile].items():
            require(name not in expected, "Duplicate contract assembly")
            expected[name] = names
    expected_cases = {case for names in expected.values() for case in names}
    require(len(assemblies) == len(expected) and {a.get("name") for a in assemblies} == set(expected), "Unexpected or duplicate native assembly set")
    require(len(cases) == len(expected_cases) and {x.get("fullname") for x in cases} == expected_cases,
            "Exact native cases changed, missing, or duplicated")
    owned = []
    for assembly in assemblies:
        actual = list(assembly.iter("test-case"))
        names = expected[assembly.get("name")]
        require(len(actual) == len(names) and {c.get("fullname") for c in actual} == set(names), "Native case assembly ownership mismatch")
        owned.extend(actual)
    require(len(owned) == len(cases) and set(owned) == set(cases), "Orphaned or multiply owned test case")
    all_suites = list(report.iter("test-suite"))
    passed = report.get("result") == "Passed" and all(x.get("result") == "Passed" for x in cases + all_suites)
    passed = passed and all(report.get(k) == str(v) for k, v in
                            {"total": len(expected_cases), "passed": len(expected_cases), "failed": 0, "skipped": 0, "inconclusive": 0}.items())
    write(target / "test-receipt.json", dict(identity(root), stage=stage, nativeResult=report.get("result"),
          expectedCases=len(cases), allExpectedPassed=passed, rawXmlSha256=sha(target / "raw-test-results.xml"),
          cases=[{"fullname": c.get("fullname"), "result": c.get("result")} for c in cases]))
    require(passed, "Native diagnostic/regression suite did not pass; original bounded XML retained")


def validate_capture(receipt, source, run, attempt, require_complete=True):
    require(receipt.get("schemaVersion") == 2 and receipt.get("candidatePresentation") == "V13_MORE_NAVIGATION_MEASURED_GEOMETRY_NOT_VISUAL_PASS", "V13 measured presentation receipt required")
    require(receipt.get("scope") == SCOPE and receipt.get("sourceCommit") == source and receipt.get("runId") == run and receipt.get("runAttempt") == attempt, "Capture source/run/attempt mismatch")
    require(receipt.get("unityVersion") == "6000.3.19f1" and receipt.get("graphicsDeviceType") not in (None, "Null"), "Pinned native GPU capture required")
    require(receipt.get("hudVisibilityBasis") == "ENABLED_CAMERA_LAYER_AND_FRUSTUM_TEST_NOT_PIXEL_OCCLUSION", "HUD visibility observation basis missing")
    require(receipt.get("inputEvidence") == "SIMULATED_INPUT_SYSTEM" and receipt.get("captureMethod") == "URP_STANDARD_REQUEST_READPIXELS", "Unexpected capture provenance")
    frames = receipt.get("frames", [])
    names = [f.get("stage") for f in frames]
    require(len(names) == len(set(names)) and all(name in FRAMES for name in names), "Unexpected/duplicate capture names")
    require(len(receipt.get("actions", [])) <= 1200, "Action receipt exceeds bounded scenario")
    if require_complete:
        require(receipt.get("complete") is True and names == FRAMES, "Six visual groups are incomplete")
    for f in frames:
        require(f.get("file") == f["stage"] + ".png" and HEX64.fullmatch(f.get("sha256", "")), "Invalid frame identity")
        require((f.get("width"), f.get("height")) == ((1600, 720) if f["stage"].endswith("20x9") else (1280, 720)), "Incorrect capture dimensions")
        require(all(HEX64.fullmatch(f.get(k, "")) for k in ("stateSha256", "seedSha256")), "State/seed hash missing")
        require(f.get("hudVisible") is True and f.get("hudFits") is True and f.get("hudFrustumRendererCount", 0) > 5 and f.get("cameraOrthographic") is False, "Runtime HUD/perspective evidence incomplete")
        require(f.get("importedRendererCount", 0) > 10 and f.get("inputUpdates", 0) > 0, "Real imported model/input evidence missing")
        ratio = f.get("hudOpaqueAreaRatio")
        require(type(ratio) in (int, float) and math.isfinite(ratio) and 0 <= ratio <= 1.00001, "HUD opaque-area observation missing or invalid")
        controls = f.get("visibleControlIds")
        require(isinstance(controls, list) and len(controls) <= 64 and len(controls) == len(set(controls)) and all(isinstance(x, str) for x in controls), "Visible control identity observation invalid")
        require(type(f.get("moreVisible")) is bool and type(f.get("paperVisible")) is bool, "More/paper visibility observation missing")
        require(all(type(f.get(key)) is int and f[key] >= 0 for key in ("renderedShopRendererCount", "renderedShopMaterialCount")), "Rendered shop resource counts missing")
        tool_bounds = f.get("toolPresentationBounds")
        require(isinstance(tool_bounds, list) and len(tool_bounds) == 3, "Three tool projection observations required")
        for rect in [f.get("paperPresentationBounds")] + tool_bounds:
            require(isinstance(rect, dict) and set(rect) == {"x", "y", "width", "height"} and all(type(v) in (int, float) and math.isfinite(v) for v in rect.values()), "Invalid projection observation")
            require(rect["width"] >= 0 and rect["height"] >= 0, "Negative projection size")
        # These observations intentionally do not confer art/layout acceptance.

    if require_complete:
        by_name = {f["stage"]: f for f in frames}
        require(by_name["shelf-before-open"]["stateSha256"] == by_name["shelf-after-open"]["stateSha256"] == by_name["challenge-returned-from-shelf"]["stateSha256"], "Shelf/return mutated the ticket state")
        for a, b in (("shelf-before-open", "shelf-after-open"), ("closing-day-table", "night-table")):
            require(all(by_name[a][key] == by_name[b][key] for key in ("cameraPosition", "cameraEuler", "cameraFov")), "Paired captures differ in camera position/rotation/FOV")
        require(by_name["number-half"]["stateSha256"] == by_name["number-half-20x9"]["stateSha256"], "Alternate aspect changed confirmed state")
        require(len({f["seedSha256"] for f in frames}) == 1, "Fixed diagnostic seed differs across frames")
        require(by_name["night-table"]["dayPhase"] == "NIGHT_BILL" and by_name["night-table"]["panel"] == "None", "Night table hidden by modal or not actually night")
        require(len(by_name["challenge-two-safe-three-tools"]["currentTools"]) == 3, "Three current ticket tools missing")
        require(by_name["number-half"]["revealedCells"] == 3, "Number half state mismatch")
    return frames


def export_captures(root, require_complete=True):
    source = root / TASK / "artifacts/visual-candidate/captures"
    receipt_path = source / "capture-receipt.json"
    receipt = read_json(receipt_path)
    bounded.require_safe_xml(b'<test-run><output>' + json.dumps(receipt).encode().replace(b'&', b'&amp;').replace(b'<', b'&lt;').replace(b'>', b'&gt;') + b'</output></test-run>')
    ident = identity(root)
    frames = validate_capture(receipt, ident["sourceCommit"], ident["runId"], ident["runAttempt"], require_complete)
    destination = outdir(root) / "captures"; destination.mkdir(parents=True, exist_ok=True)
    for f in frames:
        path = source / f["file"]
        data = bounded.bounded_read(path, 8 * 1024 * 1024)
        require(len(data) >= 10000 and data[:8] == b"\x89PNG\r\n\x1a\n", "Invalid or empty original PNG")
        require(struct.unpack(">II", data[16:24]) == (f["width"], f["height"]), "PNG dimensions disagree with native receipt")
        require(len(data) == f["bytes"] and hashlib.sha256(data).hexdigest() == f["sha256"], "Original PNG hash mismatch")
        (destination / f["file"]).write_bytes(data)
    shutil.copyfile(receipt_path, destination / "capture-receipt.json")
    print(SCOPE + ": preserved " + str(len(frames)) + " original Unity runtime PNGs")


PROGRESS_STAGES = {
    "prebuild": {"prebuild-begin", "prebuild-end", "prebuild-failed"},
    "runtime": {"runtime-setup-begin", "runtime-setup-end", "runtime-teardown-begin", "runtime-teardown-end",
                "face-begin", "face-end", "walk-begin", "walk-end", "day-ticket-settled", "scenario-complete", "runtime-timeout"}
               | {prefix + name for prefix in ("capture-begin:", "capture-end:") for name in FRAMES},
}


def validate_progress(value, kind, source, run, attempt):
    require(isinstance(value, dict) and set(value) == {"schemaVersion", "scope", "kind", "sourceCommit", "runId", "runAttempt", "status", "events"}, "Unexpected progress receipt fields")
    require(value["schemaVersion"] == 1 and value["scope"] == SCOPE and value["kind"] == kind and kind in PROGRESS_STAGES, "Invalid progress kind/scope")
    require((value["sourceCommit"], value["runId"], value["runAttempt"]) == (source, run, attempt), "Progress source/run/attempt mismatch")
    require(value["status"] == "MILESTONES_ONLY_NOT_TEST_PASS", "Progress cannot claim a test pass")
    events = value["events"]
    require(isinstance(events, list) and 1 <= len(events) <= 128, "Progress event count exceeds bound")
    last_elapsed = -1
    for event in events:
        require(isinstance(event, dict) and set(event) == {"stage", "utc", "elapsedMs", "inputUpdates", "frameCount", "purchased", "settled", "dayPhase"}, "Unexpected progress event fields")
        require(event["stage"] in PROGRESS_STAGES[kind], "Unrecognized progress stage")
        require(type(event["elapsedMs"]) is int and 0 <= event["elapsedMs"] <= 24 * 60 * 60 * 1000 and last_elapsed <= event["elapsedMs"], "Invalid/non-monotonic progress clock")
        last_elapsed = event["elapsedMs"]
        require(isinstance(event["utc"], str) and len(event["utc"]) <= 40, "Invalid progress timestamp")
        timestamp = datetime.fromisoformat(event["utc"].replace("Z", "+00:00"))
        require(timestamp.tzinfo is not None and timestamp.utcoffset().total_seconds() == 0, "Progress timestamp must be UTC")
        for key, low, high in (("inputUpdates", 0, 100000), ("frameCount", 0, 11), ("purchased", -1, 12), ("settled", -1, 12)):
            require(type(event[key]) is int and low <= event[key] <= high, "Invalid bounded progress counter")
        require(event["dayPhase"] in {"UNAVAILABLE", "DAY_OPEN", "CLOSING_PREP", "NIGHT_BILL", "DAY_COMPLETE", "RUN_FAILED"}, "Invalid progress day phase")
    require(events[0]["stage"] == ("prebuild-begin" if kind == "prebuild" else "runtime-setup-begin"), "Missing initial progress milestone")
    return value


def export_progress(root):
    ident = identity(root)
    # Two explicitly named, fixed-schema files only. Missing files mean no observed
    # milestone, not a successful import/runtime; the real NUnit verdict stays separate.
    for kind in ("prebuild", "runtime"):
        path = root / TASK / ("artifacts/visual-candidate/" + kind + "-progress.json")
        if not path.exists():
            continue
        value = validate_progress(read_json(path, 65536), kind, ident["sourceCommit"], ident["runId"], ident["runAttempt"])
        write(outdir(root) / (kind + "-progress.json"), value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("guard", "restore-font", "snapshot", "snapshot-after", "tests", "captures", "partial-captures", "progress"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--stage", choices=STAGES, default="capture")
    args = parser.parse_args(); root = args.root.resolve()
    if args.command == "guard": guard(root)
    elif args.command == "restore-font":
        identity(root); bounded.restore(root)
        shutil.copyfile(root / TASK / "evidence/font-receipt.json", outdir(root) / "font-receipt.json")
    elif args.command in ("snapshot", "snapshot-after"): snapshot(root, after=args.command == "snapshot-after")
    elif args.command == "progress": export_progress(root)
    elif args.command == "tests": export_tests(root, args.stage)
    else: export_captures(root, require_complete=args.command == "captures")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Fixed error messages and bounded file paths only; never print env/Unity logs.
        print("VISUAL_CANDIDATE_ERROR " + str(exc), file=sys.stderr)
        sys.exit(1)
