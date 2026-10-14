#!/usr/bin/env python3
"""Optional diagnostic scheduling only. Never grants a native/NUnit/G3 pass."""
import argparse
import hashlib
import os
from pathlib import Path
import visual_candidate_ci as visual
import reflection_bake_ci as reflection
import startup_progress_ci as startup
import safe_project_ci as safe

NAME = 'diagnostic-regression-decision.json'
FINAL_NAME = 'diagnostic-regression-not-run.json'
SCOPE = 'DIAGNOSTIC_SCHEDULING_ONLY_NOT_G3_PASS'
FAILED_PREBUILD = (
    'prebuild-begin', 'prebuild-scene-guard-begin', 'prebuild-guard-snapshot-begin',
    'prebuild-guard-snapshot-end', 'prebuild-prepare-begin', 'prebuild-prepare-failed',
    'prebuild-guard-verify-begin', 'prebuild-guard-verify-passed', 'prebuild-failed')
require = visual.require


def read_fixed(path, limit):
    require(path.resolve() == path.absolute() and path.is_file(), 'DECISION_FIXED_PATH_REJECTED')
    raw = visual.bounded.bounded_read(path, limit)
    return reflection.load_receipt(raw), hashlib.sha256(raw).hexdigest()


def eligible(ident, capture, session, progress, started, runtime_present):
    """All inputs are fixed receipts. Unknown/incomplete evidence never permits skipping."""
    capture_fields = set(ident) | {'schemaVersion', 'phase', 'status', 'dockerExitCode', 'nativeExitCode', 'nativeExitMarkerCount', 'observations', 'compilerErrors', 'cleanup', 'image', 'mechanismSourcePin', 'nativeOutput', 'testVerdict', 'elapsedMs', 'recordedAtUtc'}
    require(set(capture) == capture_fields and set(session) == set(ident) | {'status', 'activationSucceeded', 'stagesStarted', 'cleanup'}, 'SAFE_FIELDS_REJECTED')
    require(type(capture['schemaVersion']) is int and capture['schemaVersion'] == 1 and capture['image'] == safe.private.IMAGE and capture['mechanismSourcePin'] == safe.private.PIN, 'SAFE_PIN_REJECTED')
    require(capture.get('phase') == 'capture' and capture.get('status') == 'NATIVE_FAILED', 'CAPTURE_FAILURE_REQUIRED')
    for value in (capture, session):
        for key in ('scope', 'sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt', 'requestId'):
            require(value.get(key) == ident[key], 'DECISION_IDENTITY_REJECTED')
    code = capture.get('nativeExitCode')
    require(type(code) is int and 1 <= code <= 255 and type(capture.get('dockerExitCode')) is int and capture['dockerExitCode'] == code and type(capture.get('nativeExitMarkerCount')) is int and capture['nativeExitMarkerCount'] == 1, 'CAPTURE_EXIT_REJECTED')
    require(capture.get('compilerErrors') == [] and capture.get('cleanup') is None, 'CAPTURE_INCOMPLETE')
    observations = capture.get('observations')
    require(type(observations) is dict and set(observations) == set(safe.private.TOKENS) and all(type(v) is int and v >= 0 for v in observations.values()), 'CAPTURE_OBSERVATIONS_REJECTED')
    require(observations['invalidLicenseXml400'] == 0 and observations['nativeActivationAborted'] == 0, 'CAPTURE_LICENSE_REJECTED')
    require(session.get('status') == 'READY' and session.get('activationSucceeded') is True and session.get('stagesStarted') == ['capture'] and session.get('cleanup') is None, 'SESSION_NOT_READY')
    visual.validate_progress(progress, 'prebuild', ident['sourceCommit'], ident['runId'], ident['runAttempt'])
    require(tuple(e['stage'] for e in progress['events']) == FAILED_PREBUILD, 'PREBUILD_TERMINAL_FAILURE_REQUIRED')
    require(all(e['inputUpdates'] == 0 and e['frameCount'] == 0 and e['purchased'] == -1 and e['settled'] == -1 and e['dayPhase'] == 'UNAVAILABLE' for e in progress['events']), 'PREBUILD_RUNTIME_CONTRADICTION')
    startup.validate_startup(started, ident)
    require(not started['diagnosticWriteFailed'] and not started['eventLimitReached'] and started['events'][-1]['stage'] == 'QUITTING', 'STARTUP_INCOMPLETE')
    require(all(e['stage'] in {'ARMED', 'ERROR_LOG', 'UTF_ERROR', 'QUITTING'} and not e['isPlaying'] and not e['isPlayingOrWillChangePlaymode'] for e in started['events']), 'STARTUP_RUNTIME_CONTRADICTION')
    require(any(e['stage'] == 'ERROR_LOG' and (e['code'] == 'PREBUILD_SETUP' or e['origin'] == 'PREBUILD_SETUP') for e in started['events']), 'STARTUP_PREBUILD_FAILURE_REQUIRED')
    require(not runtime_present, 'RUNTIME_EVIDENCE_PRESENT')
    return True


def decide(root):
    ident = visual.identity(root)
    require(ident.get('scope') == visual.SCOPE and ident.get('g3Gate') == 'NOT_EVALUATED' and ident.get('deviceQa') == 'NOT_RUN', 'DECISION_SCOPE_REJECTED')
    for key, env in (('sourceCommit', 'GITHUB_SHA'), ('runId', 'GITHUB_RUN_ID'), ('runAttempt', 'GITHUB_RUN_ATTEMPT')):
        require(ident.get(key) == os.environ.get(env), 'DECISION_RUN_REJECTED')
    require(visual.HEX40.fullmatch(ident['sourceCommit']) and visual.HEX40.fullmatch(ident['reviewedCandidateCommit']) and ident['runAttempt'] == '1', 'DECISION_IDENTITY_REJECTED')
    stop = False
    reason = 'FULL_DIAGNOSTIC_DEFAULT'
    hashes = {}
    try:
        request, hashes['request'] = read_fixed(root / visual.REQUEST, 8192)
        profile = visual.request_profile(request)
        require(request['purpose'] == visual.SCOPE and request['sourceCommit'] == ident['reviewedCandidateCommit'] and request['requestId'] == ident['requestId'] and request['sourceReview'] == ident['sourceReview'], 'DECISION_REQUEST_REJECTED')
        # The guard has already attested this exact trigger. Reject later edits.
        require(visual.git(root, 'show', 'HEAD:' + visual.REQUEST) == (root / visual.REQUEST).read_text().strip(), 'DECISION_REQUEST_CHANGED')
        if profile == visual.EARLY_STOP:
            reason = 'EVIDENCE_INCOMPLETE_RUN_REGRESSIONS'
            folder = root / visual.TASK / 'artifacts/visual-candidate'
            capture, hashes['capture'] = read_fixed(visual.outdir(root) / 'safe-capture.json', 32768)
            session, hashes['session'] = read_fixed(visual.outdir(root) / 'safe-session.json', 16384)
            progress, hashes['prebuild'] = read_fixed(folder / 'prebuild-progress.json', 65536)
            started, hashes['startup'] = read_fixed(folder / 'startup-progress.json', startup.LIMIT)
            paths = [folder / 'runtime-progress.json', folder / 'lifecycle-progress.json', folder / 'captures/capture-receipt.json']
            runtime_present = any(p.exists() or p.is_symlink() or p.resolve() != p.absolute() for p in paths)
            stop = eligible(ident, capture, session, progress, started, runtime_present)
            reason = 'PREBUILD_FAILURE_CONFIRMED'
    except Exception:
        # A malformed selector or bad/missing proof never turns into a skip.
        # No arbitrary exception text or path is exported.
        reason = 'EVIDENCE_INCOMPLETE_RUN_REGRESSIONS'
        stop = False
    receipt = {k: ident[k] for k in ('sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt', 'requestId')}
    receipt.update(schemaVersion=1, scope=SCOPE, status='SKIP_REQUESTED' if stop else 'REGRESSIONS_REQUIRED',
                   reason=reason, regressionEdit='SKIP_REQUESTED' if stop else 'REQUIRED', regressionPlay='SKIP_REQUESTED' if stop else 'REQUIRED',
                   g3Gate='NOT_EVALUATED', captureVerdict='UNCHANGED_SEPARATE_RECEIPT', evidenceSha256=hashes)
    dest = visual.outdir(root) / NAME
    require(dest.resolve() == dest.absolute(), 'DECISION_DESTINATION_REJECTED')
    visual.write(dest, receipt)
    # Workflow also requires this step outcome == success. A failed receipt/output
    # write cannot authorize skipping, even if a partial output line was written.
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        stream.write('skip_regressions=' + ('true' if stop else 'false') + '\n')
    print('DIAGNOSTIC_SCHEDULING_RECEIPT_WRITTEN_NOT_TEST_PASS')
    return receipt


def finalize_not_run(root):
    # Only observed workflow skips, never the earlier scheduling intention, are
    # allowed to produce NOT_RUN. A failed output write keeps regressions runnable.
    ident = visual.identity(root)
    for key, env in (('sourceCommit', 'GITHUB_SHA'), ('runId', 'GITHUB_RUN_ID'), ('runAttempt', 'GITHUB_RUN_ATTEMPT')):
        require(ident.get(key) == os.environ.get(env), 'FINAL_DECISION_RUN_REJECTED')
    require(os.environ.get('DECISION_OUTCOME') == 'success' and os.environ.get('DECISION_SKIP') == 'true' and os.environ.get('REGRESSION_EDIT_OUTCOME') == 'skipped' and os.environ.get('REGRESSION_PLAY_CORE_OUTCOME') == 'skipped' and os.environ.get('REGRESSION_PLAY_WORLD_OUTCOME') == 'skipped', 'ACTUAL_REGRESSION_SKIP_REQUIRED')
    value, digest = read_fixed(visual.outdir(root) / NAME, 8192)
    fields = {'schemaVersion', 'scope', 'status', 'reason', 'sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt', 'requestId', 'regressionEdit', 'regressionPlay', 'g3Gate', 'captureVerdict', 'evidenceSha256'}
    require(set(value) == fields and type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and value['scope'] == SCOPE and value['status'] == 'SKIP_REQUESTED' and value['reason'] == 'PREBUILD_FAILURE_CONFIRMED', 'FINAL_DECISION_REJECTED')
    for key in ('sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt', 'requestId'):
        require(value[key] == ident[key], 'FINAL_DECISION_IDENTITY_REJECTED')
    require(value['regressionEdit'] == value['regressionPlay'] == 'SKIP_REQUESTED' and value['g3Gate'] == 'NOT_EVALUATED' and value['captureVerdict'] == 'UNCHANGED_SEPARATE_RECEIPT', 'FINAL_DECISION_SCOPE_REJECTED')
    require(type(value['evidenceSha256']) is dict and set(value['evidenceSha256']) == {'request', 'capture', 'session', 'prebuild', 'startup'} and all(type(x) is str and len(x) == 64 and all(c in '0123456789abcdef' for c in x) for x in value['evidenceSha256'].values()), 'FINAL_DECISION_HASHES_REJECTED')
    final = {k: value[k] for k in ('sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt', 'requestId')}
    final.update(schemaVersion=1, scope=SCOPE, status='REGRESSIONS_NOT_RUN', reason='PREBUILD_FAILURE_CONFIRMED', regressionEdit='NOT_RUN', regressionPlay='NOT_RUN', g3Gate='NOT_EVALUATED', captureVerdict='UNCHANGED_SEPARATE_RECEIPT', decisionSha256=digest)
    dest = visual.outdir(root) / FINAL_NAME
    require(dest.resolve() == dest.absolute(), 'FINAL_DECISION_DESTINATION_REJECTED')
    visual.write(dest, final)
    print('DIAGNOSTIC_REGRESSIONS_NOT_RUN_NOT_TEST_PASS')
    return final


def main():
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('action', choices=('decide', 'finalize'))
        args = parser.parse_args()
        root = Path(__file__).resolve().parents[3]
        (decide if args.action == 'decide' else finalize_not_run)(root); return 0
    except Exception:
        print('DIAGNOSTIC_SCHEDULING_REJECTED_RUN_REGRESSIONS'); return 1


if __name__ == '__main__':
    raise SystemExit(main())
