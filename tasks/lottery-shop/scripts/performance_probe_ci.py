#!/usr/bin/env python3
"""Independent bounded A/B/A diagnostic; no visual/gameplay/device approval."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import probe_ci as bounded
import visual_candidate_ci as original

TASK = "tasks/lottery-shop"
SCOPE = "PERFORMANCE_DIAGNOSTIC_NOT_G3_PASS"
REQUEST = TASK + "/ci/performance-probe-request.json"
WORKFLOW = ".github/workflows/lottery-performance-probe.yml"
ASSEMBLY = "Lottery.G3.PerformanceDiagnostic.Tests.dll"
CASE = "Lottery.G3.PerformanceDiagnostic.Tests.AdditionalShadowPerformanceTests.AdditionalShadowCostAbaKeepsSceneAndRestoresLights"
require, read_json, write, git, sha = original.require, original.read_json, original.write, original.git, original.sha
HEX40 = original.HEX40


def outdir(root):
    return root / TASK / "evidence/performance-probe"


def guard(root):
    env = os.environ
    require(env.get("GITHUB_RUN_ATTEMPT") == "1", "Independent performance diagnostic requires first attempt")
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
    require(request["schemaVersion"] == 1 and request["purpose"] == SCOPE, "Request is not a independent performance diagnostic")
    require(re.fullmatch(r"lottery-performance-[0-9]{8}-[0-9]{2,3}", request["requestId"]), "Invalid request identity")
    require(HEX40.fullmatch(request["sourceCommit"]) and request["sourceCommit"] == git(root, "rev-parse", "HEAD^"), "Trigger must directly follow the separately reviewed candidate source")
    review = request["sourceReview"]
    require(isinstance(review, dict) and set(review) == {"sourceCommit", "status", "reviewedAtUtc", "reviewId", "reviewer"}, "Bounded independent source-review receipt required")
    require(review["sourceCommit"] == request["sourceCommit"] and review["status"] == "APPROVED_FOR_PERFORMANCE_DIAGNOSTIC_ONLY" and review["reviewer"] == "independent-source-review", "Source review does not cover this candidate")
    require(re.fullmatch(r"performance-source-[0-9]{8}-[0-9]{2,3}", review["reviewId"]), "Invalid independent review identity")
    reviewed_at = datetime.fromisoformat(review["reviewedAtUtc"].replace("Z", "+00:00"))
    require(reviewed_at.tzinfo is not None and reviewed_at.utcoffset().total_seconds() == 0 and reviewed_at <= datetime.now(timezone.utc), "Invalid review UTC timestamp")
    changed = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()
    require(changed == [REQUEST], "Trigger commit must change only performance-probe-request.json")
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


def export_tests(root):
    ident = identity(root)
    source = root / TASK / 'artifacts/performance-probe'
    target = outdir(root) / 'tests'; target.mkdir(parents=True, exist_ok=True)
    tree = bounded.export_raw_test_report(source, target)
    assemblies = [s for s in tree.iter('test-suite') if s.get('type') == 'Assembly']
    cases = list(tree.iter('test-case'))
    exact = (tree.tag == 'test-run' and len(assemblies) == 1 and assemblies[0].get('name') == ASSEMBLY
             and len(cases) == 1 and cases[0].get('fullname') == CASE
             and list(assemblies[0].iter('test-case')) == cases)
    passed = (exact and all(tree.get(k) == '1' for k in ('total', 'passed'))
              and all(tree.get(k) == '0' for k in ('failed', 'skipped', 'inconclusive'))
              and all(node.get('result') == 'Passed' for node in [tree, *tree.iter('test-suite'), *cases]))
    write(target / 'test-receipt.json', dict(ident, exactSingleCase=exact, allExpectedPassed=passed,
          expectedAssembly=ASSEMBLY, expectedCase=CASE, status='PERFORMANCE_TEST_ONLY_NOT_G3_PASS'))
    require(passed, 'Independent performance NUnit case did not exactly pass')


# The numeric measurement schema is agreed with the fixture owner below.
METRICS = {'mainThread': 'NANOSECONDS', 'renderThread': 'NANOSECONDS', 'drawCalls': 'COUNT',
           'batches': 'COUNT', 'setPass': 'COUNT', 'triangles': 'COUNT', 'vertices': 'COUNT',
           'mainShadowCpu': 'NANOSECONDS', 'additionalShadowCpu': 'NANOSECONDS', 'presentWaitCpu': 'NANOSECONDS'}
UNAVAILABLE_REASONS = {'NOT_EXPOSED', 'AMBIGUOUS_MARKER', 'UNIT_MISMATCH', 'TYPE_MISMATCH',
                       'NO_NEW_SAMPLE', 'INVALID_RECORDER', 'RECORDER_UNAVAILABLE', 'NOT_RUNNING', 'NEGATIVE_VALUE'}


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def number(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def validate_measurements(value, ident):
    flags = {'setupComplete', 'a2Restored', 'finallyRestored', 'teardownRestored', 'stateUnchanged',
             'renderingUnchanged', 'measurementsComplete', 'cleanupComplete', 'softwareRendererDetected'}
    fields = {'schemaVersion', 'scope', 'testIdentity', 'sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt',
              'unityVersion', 'graphicsDeviceType', 'status', 'stage', 'gpuTiming', 'visualReview', 'deviceQa',
              'width', 'height', 'warmupFrames', 'sampleFrames', 'measuredAndWarmupFrames', 'shopRenderers',
              'shopMaterials', 'sceneRenderers', 'cameraPosition', 'cameraEuler', 'cameraFov', 'cameraOrigin', 'stateSha256', 'elapsedMs', 'setupElapsedMs', 'measurementElapsedMs', 'phases'} | flags
    require(isinstance(value, dict) and set(value) == fields, 'Unexpected performance receipt fields')
    require(type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and value['scope'] == SCOPE and value['testIdentity'] == CASE, 'Performance schema/scope/case mismatch')
    require(all(value[k] == ident[k] for k in ('sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt')), 'Performance source/run/attempt mismatch')
    require(value['unityVersion'] == '6000.3.19f1' and value['graphicsDeviceType'] in {'OpenGLCore', 'Vulkan', 'Null'}, 'Unknown performance native version/backend')
    require(value['status'] in {'PARTIAL_MEASUREMENTS_ONLY', 'COMPLETE_MEASUREMENTS_ONLY'} and value['stage'] in {'SETUP', 'READY', 'A1', 'B', 'A2', 'RESTORED', 'TEARDOWN'}, 'Invalid performance status/stage')
    require(value['gpuTiming'] == 'NOT_COLLECTED_CPU_COUNTERS_ONLY' and value['visualReview'] == 'NOT_EVALUATED' and value['deviceQa'] == 'NOT_RUN', 'Performance observations cannot claim quality/device/GPU results')
    require(all(type(value[k]) is bool for k in flags), 'Performance flags must be booleans')
    require(all(type(value[k]) is int and value[k] == v for k, v in {'width':1280, 'height':720, 'warmupFrames':2, 'sampleFrames':6}.items()), 'Performance fixed camera/sample design mismatch')
    require(integer(value['measuredAndWarmupFrames'], 0, 24) and integer(value['shopRenderers'], 0, 10000) and integer(value['shopMaterials'], 0, 10000), 'Performance count out of bounds')
    require(integer(value['sceneRenderers'], 0, 10000) and number(value['cameraFov'], 0, 179), 'Performance scene/camera bounds invalid')
    require(value['cameraOrigin'] == 'FIXTURE_POSITIONED_NORMAL_ENTRY', 'Performance camera origin mismatch')
    for field in ('cameraPosition', 'cameraEuler'):
        vector = value[field]
        require(isinstance(vector, dict) and set(vector) == {'x', 'y', 'z'} and all(number(v, -1000, 1000) for v in vector.values()), 'Invalid bounded performance camera vector')
    require(isinstance(value['stateSha256'], str) and (original.HEX64.fullmatch(value['stateSha256']) is not None or (not value['setupComplete'] and value['stateSha256'] == 'UNAVAILABLE')), 'Performance state hash invalid')
    require(integer(value['elapsedMs'], 0, 600000) and integer(value['setupElapsedMs'], 0, value['elapsedMs']) and integer(value['measurementElapsedMs'], 0, value['elapsedMs']), 'Performance wall clock out of bounds')
    phases = value['phases']; require(isinstance(phases, list) and len(phases) <= 3, 'Performance phase count out of bounds')
    completed_frames = 0
    for index, phase in enumerate(phases):
        require(isinstance(phase, dict) and set(phase) == {'phase', 'shadowedAdditionalLights', 'warmupCompleted', 'elapsedMs', 'complete', 'samples'}, 'Unexpected performance phase fields')
        require(phase['phase'] == ('A1', 'B', 'A2')[index] and type(phase['shadowedAdditionalLights']) is int and phase['shadowedAdditionalLights'] == (0 if index == 1 else 2), 'Performance A-B-A shadow sequence mismatch')
        require(type(phase['complete']) is bool and integer(phase['warmupCompleted'], 0, 2) and integer(phase['elapsedMs'], 0, 60000), 'Performance phase bound mismatch')
        samples = phase['samples']; require(isinstance(samples, list) and len(samples) <= 6 and (not samples or phase['warmupCompleted'] == 2), 'Performance warmup/sample count mismatch')
        if index < len(phases)-1 or phase['complete']:
            require(phase['complete'] and phase['warmupCompleted'] == 2 and len(samples) == 6, 'Incomplete earlier performance phase')
        completed_frames += phase['warmupCompleted'] + len(samples)
        if phase['complete']:
            require(sum(s.get('wallMs', 0) for s in samples if isinstance(s, dict) and number(s.get('wallMs'), 0, 60000)) <= phase['elapsedMs'] + 2, 'Performance sample walls exceed phase wall')
        for n, sample in enumerate(samples):
            require(isinstance(sample, dict) and set(sample) == {'index', 'frameDelta', 'cameraRenderDelta', 'wallMs', 'metrics'}, 'Unexpected performance frame fields')
            require(type(sample['index']) is int and sample['index'] == n and integer(sample['frameDelta'], 1, 10000) and integer(sample['cameraRenderDelta'], 1, 16) and number(sample['wallMs'], 0, 60000), 'Performance sample index/frame/camera/wall mismatch')
            metrics = sample['metrics']; require(isinstance(metrics, list) and len(metrics) == len(METRICS), 'Performance metric count mismatch')
            require([m.get('code') for m in metrics if isinstance(m, dict)] == list(METRICS), 'Unknown/duplicate/out-of-order performance metric')
            for metric in metrics:
                require(set(metric) == {'code', 'unit', 'reason', 'available', 'isRunning', 'sampleCount', 'value', 'milliseconds'}, 'Unexpected performance metric fields')
                require(metric['unit'] == METRICS[metric['code']] and type(metric['available']) is bool and type(metric['isRunning']) is bool and integer(metric['sampleCount'], 0, 16), 'Performance metric unit/status/count mismatch')
                if metric['available']:
                    require(metric['reason'] == 'OBSERVED' and metric['isRunning'] and metric['sampleCount'] > 0 and integer(metric['value'], 0, 10**15), 'Invalid observed performance metric')
                    expected = metric['value']/1000000 if metric['unit'] == 'NANOSECONDS' else -1
                    require(number(metric['milliseconds'], -1, 10**9) and abs(metric['milliseconds']-expected) <= 0.000001, 'Performance metric unit conversion mismatch')
                else:
                    require(metric['reason'] in UNAVAILABLE_REASONS and type(metric['value']) is int and metric['value'] == -1 and number(metric['milliseconds'], -1, -1), 'Unavailable performance metric must not fabricate zero')
    require(completed_frames == value['measuredAndWarmupFrames'], 'Performance rendered-frame accounting mismatch')
    if value['status'] == 'COMPLETE_MEASUREMENTS_ONLY':
        require(value['stage'] == 'TEARDOWN' and value['graphicsDeviceType'] != 'Null' and all(value[k] for k in flags-{'softwareRendererDetected'}), 'Complete performance record lacks verified restoration/cleanup')
        require(value['shopRenderers'] > 0 and value['shopMaterials'] > 0 and len(phases) == 3 and all(p['complete'] for p in phases) and completed_frames == 24, 'Complete performance record lacks all 24 actual frames')
        require(value['setupElapsedMs'] <= value['measurementElapsedMs'] <= 180000, 'Performance case measurement budget exceeded')
        require(value['sceneRenderers'] >= value['shopRenderers'] and abs(value['cameraFov'] - 64) < 0.001, 'Complete performance scene/camera invariant mismatch')
        require(value['measurementElapsedMs'] + 3 >= value['setupElapsedMs'] + sum(p['elapsedMs'] for p in phases), 'Performance wall accounting mismatch')
    return value


def export_measurements(root):
    ident = identity(root)
    source = root / TASK / 'artifacts/performance-probe/performance-receipt.json'
    destination = outdir(root) / 'performance-receipt.json'
    if destination.exists(): destination.unlink()
    value = validate_measurements(read_json(source, 131072), ident)
    write(destination, value)
    require(value['status'] == 'COMPLETE_MEASUREMENTS_ONLY', 'Performance diagnostic incomplete or restoration unverified')


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('command', choices=('guard','prepare','tests','measurements','snapshot-after'))
    args = parser.parse_args(); root = Path(__file__).resolve().parents[3]
    if args.command == 'guard': guard(root)
    elif args.command == 'prepare':
        identity(root); bounded.restore(root)
        shutil.copyfile(root / TASK / 'evidence/font-receipt.json', outdir(root) / 'font-receipt.json')
        snapshot(root)
    elif args.command == 'snapshot-after': snapshot(root, after=True)
    elif args.command == 'tests': export_tests(root)
    elif args.command == 'measurements': export_measurements(root)


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        # Never interpolate arbitrary exception/receipt text into Actions output.
        print('PERFORMANCE_DIAGNOSTIC_REJECTED', file=sys.stderr)
        sys.exit(1)
