#!/usr/bin/env python3
"""Closed art-only scheduling receipt. No command, skip list, or test-pass capability."""
import argparse
import hashlib
import os
from pathlib import Path
import visual_candidate_ci as visual

NAME = 'art-only-execution.json'
PREPARED = 'art-only-preparation.json'
CONTRACT = visual.TASK + '/scripts/counter_light_diagnostics/code-contract.json'
REQUIRED_CODE = {visual.TASK + '/scripts/' + name for name in (
    'art_only_capture_ci.py', 'visual_candidate_ci.py', 'safe_project_ci.py',
    'activation_probe.py', 'probe_ci.py', 'reflection_bake_ci.py', 'play_split_ci.py')}
REQUIRED_CODE.add(visual.TASK + '/unity/Assets/G3/Tests/VisualCandidate/VisualCandidateCaptureTests.cs')
CI_CONTRACT_PATHS = {visual.TASK + '/ci/g2-test-contract.json', visual.TASK + '/ci/g3-test-contract.json'}
REQUIRED_CODE.update(CI_CONTRACT_PATHS)
SCOPE = 'ART_ONLY_DIAGNOSTIC_NOT_REGRESSION_NOT_G3_PASS'
OUTCOMES = {'success', 'failure', 'cancelled', 'skipped'}
REGRESSION_ENV = ('REGRESSION_EDIT_OUTCOME', 'REGRESSION_PLAY_CORE_OUTCOME', 'REGRESSION_PLAY_WORLD_OUTCOME')
IDENTITY_FIELDS = ('sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt', 'requestId')
require = visual.require



def prepare(root):
    # Keep the existing reviewed code-contract binding before activation without
    # importing pixel-analysis packages or executing counter-light variants.
    ident = visual.guard(root)
    require(ident.get('executionProfile') == visual.ART_ONLY, 'ART_PREPARE_PROFILE_REJECTED')
    require(os.environ.get('GITHUB_WORKFLOW_REF', '').split('@')[0] ==
            'yangerstar1/task-workbench/.github/workflows/lottery-visual-candidate.yml' and
            ident.get('runAttempt') == '1', 'ART_WORKFLOW_CONTEXT_REJECTED')
    contract_path = root / CONTRACT
    require(contract_path.resolve() == contract_path.absolute() and contract_path.is_file(), 'ART_CONTRACT_PATH_REJECTED')
    require(visual.git(root, 'hash-object', '--', CONTRACT) ==
            visual.git(root, 'rev-parse', ident['reviewedCandidateCommit'] + ':' + CONTRACT), 'ART_CONTRACT_NOT_REVIEWED')
    contract = visual.read_json(contract_path, 65536)
    require(type(contract) is dict and set(contract) == {'schemaVersion', 'scope', 'files'} and
            type(contract['schemaVersion']) is int and contract['schemaVersion'] == 1 and
            contract['scope'] == 'REVIEWED_COUNTER_LIGHT_R2_CODE_CONTRACT_NOT_RUNTIME_PASS', 'ART_CONTRACT_SCHEMA_REJECTED')
    rows = contract['files']
    require(type(rows) is list and 1 <= len(rows) <= 64, 'ART_CONTRACT_COUNT_REJECTED')
    seen = set()
    for row in rows:
        require(type(row) is dict and set(row) == {'repositoryPath', 'sha256', 'bytes'}, 'ART_CODE_RECORD_REJECTED')
        relative = row['repositoryPath']
        require(type(relative) is str and len(relative) <= 240 and
                (relative in CI_CONTRACT_PATHS or
                 relative.startswith((visual.TASK + '/scripts/', visual.TASK + '/unity/Assets/G3/'))) and
                all(part not in ('', '.', '..') for part in relative.split('/')) and
                '\\' not in relative and relative not in seen, 'ART_CODE_PATH_REJECTED')
        seen.add(relative)
        path = root / relative
        require(path.resolve() == path.absolute() and path.is_file(), 'ART_CODE_LINK_REJECTED')
        raw = visual.bounded.bounded_read(path, 2 * 1024 * 1024)
        require(type(row['bytes']) is int and row['bytes'] == len(raw) and
                type(row['sha256']) is str and visual.HEX64.fullmatch(row['sha256']) and
                hashlib.sha256(raw).hexdigest() == row['sha256'], 'ART_CODE_HASH_REJECTED')
        require(visual.git(root, 'hash-object', '--', relative) ==
                visual.git(root, 'rev-parse', ident['reviewedCandidateCommit'] + ':' + relative), 'ART_CODE_NOT_REVIEWED')
    require(REQUIRED_CODE <= seen, 'ART_REQUIRED_CODE_MISSING')
    result = {key: ident[key] for key in IDENTITY_FIELDS}
    result.update(schemaVersion=1, executionProfile=visual.ART_ONLY, scope=SCOPE,
                  status='ART_ONLY_SOURCE_BOUND_NOT_NATIVE_PASS', g3Gate='NOT_EVALUATED',
                  codeContractSha256=visual.sha(contract_path), codeFileCount=len(rows),
                  regressionPlan='NOT_REQUESTED_ART_ONLY_DIAGNOSTIC')
    destination = visual.outdir(root) / PREPARED
    require(destination.resolve() == destination.absolute() and not destination.is_symlink(), 'ART_PREPARE_DESTINATION_REJECTED')
    visual.write(destination, result)
    print('ART_ONLY_REVIEWED_SOURCE_CONTRACT_BOUND_NOT_NATIVE_PASS')
    return result


def finalize(root):
    ident = visual.identity(root)
    require(ident.get('executionProfile') == visual.ART_ONLY and
            ident.get('regressionPlan') == 'NOT_REQUESTED_ART_ONLY_DIAGNOSTIC' and
            ident.get('priorRegressionFailures') == 'UNCHANGED_NOT_SUPERSEDED' and
            ident.get('g3Gate') == 'NOT_EVALUATED' and ident.get('deviceQa') == 'NOT_RUN', 'ART_SCOPE_REJECTED')
    for field, env in (('sourceCommit', 'GITHUB_SHA'), ('runId', 'GITHUB_RUN_ID'), ('runAttempt', 'GITHUB_RUN_ATTEMPT')):
        require(ident.get(field) == os.environ.get(env), 'ART_RUN_REJECTED')
    require(ident['runAttempt'] == '1', 'ART_ATTEMPT_REJECTED')
    require(os.environ.get('ART_GUARD_OUTCOME') == 'success' and
            os.environ.get('ART_EXECUTION_PROFILE') == visual.ART_ONLY and
            os.environ.get('ART_PREPARE_ORIGINAL_OUTCOME') == 'skipped' and
            all(os.environ.get(key) == 'skipped' for key in REGRESSION_ENV), 'ART_ACTUAL_SKIP_REQUIRED')
    outcomes = {key: os.environ.get('ART_' + key.upper() + '_OUTCOME') for key in ('prepare', 'start', 'capture', 'finish')}
    require(all(value in OUTCOMES for value in outcomes.values()), 'ART_STEP_OUTCOME_REJECTED')
    if outcomes['start'] != 'skipped':
        require(outcomes['prepare'] == 'success', 'ART_PREPARE_REQUIRED_BEFORE_NATIVE')
        require(outcomes['finish'] != 'skipped', 'ART_CLEANUP_MUST_BE_ATTEMPTED')
    request_path = root / visual.REQUEST
    require(request_path.resolve() == request_path.absolute() and request_path.is_file(), 'ART_FIXED_REQUEST_REQUIRED')
    request = visual.read_diagnostic_request(request_path)
    require(visual.request_execution_profile(request) == visual.ART_ONLY and request['schemaVersion'] == 2, 'ART_REQUEST_REJECTED')
    require(request['sourceCommit'] == ident['reviewedCandidateCommit'] and request['requestId'] == ident['requestId'] and
            request['purpose'] == visual.SCOPE and request['sourceReview'] == ident['sourceReview'], 'ART_REQUEST_BINDING_REJECTED')
    require(visual.git(root, 'show', 'HEAD:' + visual.REQUEST) == request_path.read_text().strip(), 'ART_REQUEST_CHANGED')
    evidence = visual.outdir(root)
    session_path = evidence / 'safe-session.json'
    if session_path.exists() or session_path.is_symlink():
        require(session_path.resolve() == session_path.absolute() and session_path.is_file(), 'ART_SESSION_PATH_REJECTED')
        session = visual.read_json(session_path, 16384)
        require(all(session.get(key) == value for key, value in ident.items()) and
                session.get('stagesStarted') in ([], ['capture']), 'ART_SESSION_CONTRADICTS_SKIP')
    # An unexpected existing result is never erased, relabeled NOT_RUN or hidden.
    # These are fixed current-attempt paths, not a caller-defined skip list.
    forbidden = [evidence / name for name in (
        'regression-edit', 'regression-play-core', 'regression-play-world',
        'safe-regression-edit.json', 'safe-regression-play-core.json', 'safe-regression-play-world.json',
        'original-g3-preparation.json', 'original-g3-captures', 'independent-g3-case-captures',
        'regression-play-summary.json', 'world-progress.json')]
    forbidden += [root / visual.TASK / 'artifacts' / name for name in (
        'visual-regression-edit', 'visual-regression-play-core', 'visual-regression-world')]
    require(not any(path.exists() or path.is_symlink() for path in forbidden), 'ART_EXISTING_REGRESSION_EVIDENCE_PRESERVED_REJECTED')
    result = {key: ident[key] for key in IDENTITY_FIELDS}
    result.update(schemaVersion=1, scope=SCOPE, executionProfile=visual.ART_ONLY,
                  status='ART_ONLY_DIAGNOSTIC_REGRESSIONS_NOT_RUN', regressionEdit='NOT_RUN',
                  regressionPlayCore='NOT_RUN', regressionPlayWorld='NOT_RUN', fullG3='NOT_RUN', androidBuild='NOT_RUN',
                  g3Gate='NOT_EVALUATED', deviceQa='NOT_RUN', priorRegressionFailures='UNCHANGED_NOT_SUPERSEDED',
                  captureVerdict='UNCHANGED_SEPARATE_NATIVE_NUNIT_RECEIPTS',
                  nativeStepOutcomes=outcomes, cleanupVerdict='UNCHANGED_SEPARATE_SAFE_FINISH_RECEIPT',
                  sourceReceiptSha256=visual.sha(evidence / 'source-receipt.json'), requestSha256=visual.sha(request_path))
    destination = evidence / NAME
    require(destination.resolve() == destination.absolute() and not destination.is_symlink(), 'ART_DESTINATION_REJECTED')
    visual.write(destination, result)
    print('ART_ONLY_DIAGNOSTIC_REGRESSIONS_NOT_RUN_NOT_G3_PASS')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'finalize'))
    args = parser.parse_args()
    try:
        (prepare if args.action == 'prepare' else finalize)(Path(__file__).resolve().parents[3]); return 0
    except Exception:
        print('ART_ONLY_RECEIPT_REJECTED_NO_REGRESSION_OR_G3_CLAIM'); return 1


if __name__ == '__main__':
    raise SystemExit(main())
