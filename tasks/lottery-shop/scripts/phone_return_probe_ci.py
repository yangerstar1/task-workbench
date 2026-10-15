#!/usr/bin/env python3
"""One fixed phone-return functional observation; no timing or G3 acceptance."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import probe_ci as bounded
import visual_candidate_ci as original

TASK = "tasks/lottery-shop"
SCOPE = "PHONE_RETURN_FUNCTIONAL_DIAGNOSTIC_NOT_G3_PASS"
REQUEST = TASK + "/ci/phone-return-probe-request.json"
WORKFLOW = ".github/workflows/lottery-phone-return-probe.yml"
ASSEMBLY = "Lottery.G3.PlayMode.Tests.dll"
CASE = "Lottery.G3.PlayMode.Tests.G3PlayTests.PhoneReturnFunctionalObservationOnly"
require, read_json, write, git, sha = original.require, original.read_json, original.write, original.git, original.sha
HEX40 = original.HEX40
FILTER = "^" + re.escape(CASE) + "$"


def outdir(root):
    return root / TASK / "evidence/phone-return-probe"


def guard(root):
    env = os.environ
    require(env.get("GITHUB_RUN_ATTEMPT") == "1", "Independent phone-return diagnostic requires first attempt")
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
    require(request["schemaVersion"] == 1 and request["purpose"] == SCOPE, "Request is not a independent phone-return diagnostic")
    require(re.fullmatch(r"lottery-phone-return-[0-9]{8}-[0-9]{2,3}", request["requestId"]), "Invalid request identity")
    require(HEX40.fullmatch(request["sourceCommit"]) and request["sourceCommit"] == git(root, "rev-parse", "HEAD^"), "Trigger must directly follow the separately reviewed candidate source")
    review = request["sourceReview"]
    require(isinstance(review, dict) and set(review) == {"sourceCommit", "status", "reviewedAtUtc", "reviewId", "reviewer"}, "Bounded independent source-review receipt required")
    require(review["sourceCommit"] == request["sourceCommit"] and review["status"] == "APPROVED_FOR_PHONE_RETURN_DIAGNOSTIC_ONLY" and review["reviewer"] == "independent-source-review", "Source review does not cover this candidate")
    require(re.fullmatch(r"phone-return-source-[0-9]{8}-[0-9]{2,3}", review["reviewId"]), "Invalid independent review identity")
    reviewed_at = datetime.fromisoformat(review["reviewedAtUtc"].replace("Z", "+00:00"))
    require(reviewed_at.tzinfo is not None and reviewed_at.utcoffset().total_seconds() == 0 and reviewed_at <= datetime.now(timezone.utc), "Invalid review UTC timestamp")
    changed = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()
    require(changed == [REQUEST], "Trigger commit must change only phone-return-probe-request.json")
    require(git(root, "diff", "--name-only", "HEAD", "--", TASK, WORKFLOW) == "", "Checkout changed before candidate guard")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        require(re.fullmatch(r"[1-9][0-9]*", env.get(key, "")), "Invalid run identity")
    identity = {"scope": SCOPE, "sourceCommit": source, "reviewedCandidateCommit": request["sourceCommit"],
                "requestId": request["requestId"], "runId": env["GITHUB_RUN_ID"], "runAttempt": env["GITHUB_RUN_ATTEMPT"],
                "executionProfile": "PHONE_RETURN_ONLY_DIAGNOSTIC", "legacyRegression": "NOT_RUN", "deviceQa": "NOT_RUN", "g3Gate": "NOT_EVALUATED", "sourceApproval": "FIXED_ACTOR_ATTESTED_INDEPENDENT_DIAGNOSTIC_REVIEW_NOT_CRYPTOGRAPHIC_SIGNATURE", "sourceReview": review}
    write(outdir(root) / "source-receipt.json", identity)
    return identity


def identity(root):
    value = read_json(outdir(root) / "source-receipt.json", 8192)
    require(value.get("scope") == SCOPE and value.get("sourceCommit") == os.environ.get("GITHUB_SHA"), "Source receipt mismatch")
    return value


# Observability only: identical disposable-runner paths, command order and 30 GiB
# gate. The unchanged workflow two-minute cap is the only execution envelope.
DISK_PATHS = ('/usr/share/dotnet', '/opt/ghc', '/usr/local/.ghcup',
              '/usr/local/lib/android', '/opt/hostedtoolcache/CodeQL')
DISK_REQUIRED_BYTES = 30 * 1024**3
DISK_IDENTITY_KEYS = ('sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt', 'requestId')
DISK_FIELDS = {'schemaVersion', 'scope', 'phase', 'status', 'stage', 'cleanupPaths', 'requiredFreeBytes',
               'freeBeforeBytes', 'freeAfterBytes', 'guardExitCode', 'cleanupExitCode', 'thresholdExitCode',
               'helperReturnCode', 'helperReturnMarkerCount', *DISK_IDENTITY_KEYS}
DISK_STAGES = {'GUARD', 'MEASURE_BEFORE', 'CLEANUP', 'MEASURE_AFTER', 'THRESHOLD', 'COMPLETE'}
DISK_FAILURES = {'GUARD_OR_IDENTITY_REJECTED', 'BEFORE_MEASUREMENT_FAILED', 'CLEANUP_LAUNCH_OR_EXIT_REJECTED',
                 'AFTER_MEASUREMENT_FAILED', 'CLEANUP_FAILED', 'INSUFFICIENT_IMAGE_DISK_SPACE', 'INTERRUPTED'}


def disk_identity(root):
    ident = identity(root)
    require(all(type(ident.get(k)) is str and HEX40.fullmatch(ident[k])
                for k in DISK_IDENTITY_KEYS[:2]), 'DISK_SOURCE_REJECTED')
    require(type(ident.get('runId')) is str and re.fullmatch(r'[1-9][0-9]{0,19}', ident['runId'])
            and ident.get('runAttempt') == '1', 'DISK_RUN_REJECTED')
    require(ident['runId'] == os.environ.get('GITHUB_RUN_ID')
            and ident['runAttempt'] == os.environ.get('GITHUB_RUN_ATTEMPT'), 'DISK_RUN_MISMATCH')
    require(type(ident.get('requestId')) is str and
            re.fullmatch(r'lottery-phone-return-[0-9]{8}-[0-9]{2,3}', ident['requestId']), 'DISK_REQUEST_REJECTED')
    return {key: ident[key] for key in DISK_IDENTITY_KEYS}


def write_disk_receipt(root, value):
    # Atomic replacement retains the last complete fixed-schema snapshot if the
    # runner interrupts this step. This private state is never upload-allowlisted.
    path = outdir(root) / 'runner-disk-preparation-state.json'
    data = json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n'
    require(len(data.encode('utf-8')) <= 4096, 'DISK_RECEIPT_LIMIT')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(data, encoding='utf-8')
    temporary.replace(path)


def prepare_runner_disk(root):
    # No exception strings, subprocess output, environment dump or directory
    # enumeration is ever copied into this receipt or sent to the job log.
    receipt = dict(schemaVersion=1, scope=SCOPE, phase='RUNNER_DISK_PREPARATION',
                   status='IN_PROGRESS', stage='GUARD', cleanupPaths=list(DISK_PATHS),
                   requiredFreeBytes=DISK_REQUIRED_BYTES, freeBeforeBytes=-1, freeAfterBytes=-1,
                   guardExitCode=None, cleanupExitCode=None, thresholdExitCode=None,
                   helperReturnCode=None, helperReturnMarkerCount=0,
                   **{key: 'UNAVAILABLE' for key in DISK_IDENTITY_KEYS})
    try:
        receipt.update(disk_identity(root))
    except Exception:
        pass
    write_disk_receipt(root, receipt)

    def stage(name):
        receipt['stage'] = name
        write_disk_receipt(root, receipt)

    def finish(status, code):
        receipt.update(status=status, helperReturnCode=code, helperReturnMarkerCount=1)
        write_disk_receipt(root, receipt)
        # A successful preparation cannot permit activation before export validation.
        read_disk_receipt(root)
        return code

    def free_bytes():
        value = shutil.disk_usage(root).free
        require(type(value) is int and 0 <= value <= 2**63-1, 'DISK_MEASUREMENT_REJECTED')
        return value

    class PhaseRejected(Exception):
        pass

    def observed_phase(name, action, failure):
        stage(name)  # A receipt-write error must not be mislabeled as an action error.
        try:
            return action()
        except KeyboardInterrupt:
            raise PhaseRejected('INTERRUPTED') from None
        except Exception:
            raise PhaseRejected(failure) from None

    def guarded_identity():
        guard(root)  # Same full independent-request guard, still before cleanup.
        return disk_identity(root)

    def cleanup():
        result = subprocess.run(['sudo', 'rm', '-rf', *DISK_PATHS], cwd=root,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, check=False)
        require(type(result.returncode) is int and -255 <= result.returncode <= 255,
                'DISK_CLEANUP_EXIT_REJECTED')
        return result.returncode

    try:
        receipt.update(observed_phase('GUARD', guarded_identity, 'GUARD_OR_IDENTITY_REJECTED'))
        receipt['guardExitCode'] = 0
        receipt['freeBeforeBytes'] = observed_phase('MEASURE_BEFORE', free_bytes, 'BEFORE_MEASUREMENT_FAILED')
        receipt['cleanupExitCode'] = observed_phase('CLEANUP', cleanup, 'CLEANUP_LAUNCH_OR_EXIT_REJECTED')
        receipt['freeAfterBytes'] = observed_phase('MEASURE_AFTER', free_bytes, 'AFTER_MEASUREMENT_FAILED')
        if receipt['cleanupExitCode'] != 0:
            return finish('CLEANUP_FAILED', 1)
        stage('THRESHOLD')
        receipt['thresholdExitCode'] = int(receipt['freeAfterBytes'] < DISK_REQUIRED_BYTES)
        if receipt['thresholdExitCode']:
            return finish('INSUFFICIENT_IMAGE_DISK_SPACE', 1)
        stage('COMPLETE')
        return finish('DISK_PREPARATION_SUCCEEDED', 0)
    except PhaseRejected as rejected:
        if receipt['stage'] == 'GUARD' and rejected.args[0] != 'INTERRUPTED':
            receipt['guardExitCode'] = 1
        return finish(rejected.args[0], 1)


def validate_disk_receipt(value, ident):
    require(type(value) is dict and set(value) == DISK_FIELDS, 'DISK_FIELDS_REJECTED')
    require(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
            and value['scope'] == SCOPE and value['phase'] == 'RUNNER_DISK_PREPARATION', 'DISK_SCHEMA_REJECTED')
    require(all(type(value[key]) is str and value[key] == ident[key] for key in DISK_IDENTITY_KEYS),
            'DISK_BINDING_REJECTED')
    require(type(value['cleanupPaths']) is list and value['cleanupPaths'] == list(DISK_PATHS)
            and type(value['requiredFreeBytes']) is int and value['requiredFreeBytes'] == DISK_REQUIRED_BYTES,
            'DISK_SCOPE_REJECTED')
    require(type(value['stage']) is str and value['stage'] in DISK_STAGES
            and type(value['status']) is str and value['status'] in DISK_FAILURES | {'IN_PROGRESS', 'DISK_PREPARATION_SUCCEEDED'},
            'DISK_ENUM_REJECTED')
    for key in ('freeBeforeBytes', 'freeAfterBytes'):
        require(type(value[key]) is int and -1 <= value[key] <= 2**63-1, 'DISK_BYTES_REJECTED')
    for key in ('guardExitCode', 'thresholdExitCode', 'helperReturnCode'):
        require(value[key] is None or type(value[key]) is int and value[key] in (0, 1), 'DISK_EXIT_REJECTED')
    require(value['cleanupExitCode'] is None or type(value['cleanupExitCode']) is int
            and -255 <= value['cleanupExitCode'] <= 255, 'DISK_CLEANUP_EXIT_REJECTED')
    require(type(value['helperReturnMarkerCount']) is int and value['helperReturnMarkerCount'] in (0, 1),
            'DISK_MARKER_REJECTED')
    stage, status = value['stage'], value['status']
    before, after = value['freeBeforeBytes'], value['freeAfterBytes']
    guard_code, cleanup_code, threshold_code = (value[k] for k in ('guardExitCode', 'cleanupExitCode', 'thresholdExitCode'))
    # Closed snapshot state machine. An interrupted/unfinished stage is never a
    # successful cleanup, threshold check or completed preparation.
    if stage == 'GUARD':
        require(guard_code in (None, 1) and cleanup_code is threshold_code is None and before == after == -1,
                'DISK_STAGE_REJECTED')
    else:
        require(guard_code == 0, 'DISK_GUARD_REQUIRED')
        if stage == 'MEASURE_BEFORE':
            require(before == after == -1 and cleanup_code is threshold_code is None, 'DISK_STAGE_REJECTED')
        elif stage == 'CLEANUP':
            require(before >= 0 and after == -1 and cleanup_code is threshold_code is None, 'DISK_STAGE_REJECTED')
        elif stage == 'MEASURE_AFTER':
            require(before >= 0 and cleanup_code is not None and threshold_code is None
                    and (after >= 0 if status == 'CLEANUP_FAILED' else after == -1), 'DISK_STAGE_REJECTED')
        else:
            require(before >= 0 and after >= 0 and cleanup_code == 0, 'DISK_STAGE_REJECTED')
            if stage == 'COMPLETE':
                require(threshold_code == 0 and after >= DISK_REQUIRED_BYTES, 'DISK_THRESHOLD_REQUIRED')
            else:
                require(threshold_code == (1 if status == 'INSUFFICIENT_IMAGE_DISK_SPACE' else None),
                        'DISK_STAGE_REJECTED')
    if status == 'IN_PROGRESS':
        require(value['helperReturnMarkerCount'] == 0 and value['helperReturnCode'] is None
                and guard_code != 1, 'DISK_UNFINISHED_REJECTED')
    else:
        success = status == 'DISK_PREPARATION_SUCCEEDED'
        require(value['helperReturnMarkerCount'] == 1 and value['helperReturnCode'] == (0 if success else 1),
                'DISK_TERMINAL_REJECTED')
        expected = {'GUARD_OR_IDENTITY_REJECTED': 'GUARD', 'BEFORE_MEASUREMENT_FAILED': 'MEASURE_BEFORE',
                    'CLEANUP_LAUNCH_OR_EXIT_REJECTED': 'CLEANUP', 'AFTER_MEASUREMENT_FAILED': 'MEASURE_AFTER',
                    'CLEANUP_FAILED': 'MEASURE_AFTER', 'INSUFFICIENT_IMAGE_DISK_SPACE': 'THRESHOLD',
                    'DISK_PREPARATION_SUCCEEDED': 'COMPLETE'}
        require(stage == expected[status] if status != 'INTERRUPTED' else stage in DISK_STAGES - {'THRESHOLD', 'COMPLETE'},
                'DISK_STATUS_STAGE_REJECTED')
        if status == 'GUARD_OR_IDENTITY_REJECTED':require(guard_code == 1, 'DISK_GUARD_EXIT_REQUIRED')
        if status == 'CLEANUP_FAILED':require(cleanup_code != 0, 'DISK_CLEANUP_FAILURE_REQUIRED')
        if status == 'INSUFFICIENT_IMAGE_DISK_SPACE':require(after < DISK_REQUIRED_BYTES, 'DISK_THRESHOLD_FAILURE_REQUIRED')
    return value


def read_disk_receipt(root):
    raw = read_regular(outdir(root) / 'runner-disk-preparation-state.json', 4096)
    value = json.loads(raw, object_pairs_hook=unique_pairs)
    return validate_disk_receipt(value, disk_identity(root))


def export_disk_receipt(root, step_outcome):
    target = outdir(root) / 'runner-disk-preparation.json'
    target.unlink(missing_ok=True)
    value = read_disk_receipt(root)
    require(step_outcome in ('success', 'failure', 'cancelled'), 'DISK_STEP_OUTCOME_REJECTED')
    require((step_outcome == 'success') == (value['status'] == 'DISK_PREPARATION_SUCCEEDED'),
            'DISK_STEP_RESULT_MISMATCH')
    write(target, value)
    return value


def export_diagnostics(root):
    export_disk_receipt(root, os.environ.get('RUNNER_DISK_STEP_OUTCOME'))
    outcome = os.environ.get('PHONE_RETURN_STEP_OUTCOME')
    require(outcome in ('success', 'failure', 'cancelled', 'skipped'), 'PHONE_STEP_OUTCOME_REJECTED')
    if outcome != 'skipped':
        export(root)  # Retains the previous exact phone-step outcome condition.


FLAGS = {'setupComplete','routeComplete','cleanupComplete','deadlineExceeded','phoneOpened','cameraRestored','finalSeated','phoneFocused'}
HASHES = {'initialStateHash','stateHash','initialTicketHash','ticketHash'}
VECTORS = {'position':3,'cameraPositionBefore':3,'cameraPositionAfter':3,'cameraRotationBefore':4,'cameraRotationAfter':4}
FIELDS = {'schemaVersion','scope','testIdentity','sourceCommit','reviewedCandidateCommit','runId','runAttempt','renderer','status','stage','timing','elapsedMs','mode','initialPaidMinor','paidMinor','initialScratch','scratch','routes'} | FLAGS | HASHES | set(VECTORS)
STAGES = {'SETUP','READY','TICKET_READY','BEFORE_PHONE','PHONE_OPEN','PHONE_CLOSED','FINAL_SEAT','ROUTE_COMPLETE','WALK','TEARDOWN'}

def number(v, lo, hi):
    return type(v) in (int,float) and math.isfinite(v) and lo <= v <= hi

def validate_observation(v, ident):
    require(type(v) is dict and set(v)==FIELDS, 'PHONE_FIELDS_REJECTED')
    require(type(v['schemaVersion']) is int and v['schemaVersion']==1 and v['scope']==SCOPE and v['testIdentity']==CASE, 'PHONE_IDENTITY_REJECTED')
    require(all(type(v[k]) is str and v[k]==ident[k] for k in ('sourceCommit','reviewedCandidateCommit','runId','runAttempt')), 'PHONE_SOURCE_REJECTED')
    require(v['renderer'] in ('llvmpipe','other','unknown') and v['stage'] in STAGES, 'PHONE_ENUM_REJECTED')
    require(v['status'] in ('INCONCLUSIVE','FUNCTIONAL_ROUTE_AND_STATE_OBSERVED') and v['timing'] in ('NOT_OBSERVED','NO_OVERRUN_OBSERVED','TIMING_FAIL'), 'PHONE_RESULT_REJECTED')
    require(all(type(v[k]) is bool for k in FLAGS), 'PHONE_FLAGS_REJECTED')
    require(number(v['elapsedMs'],0,480000) and type(v['mode']) is int and -1<=v['mode']<=32, 'PHONE_CLOCK_MODE_REJECTED')
    for k in HASHES:
        require(type(v[k]) is str and (v[k]=='UNAVAILABLE' or re.fullmatch('[0-9a-f]{64}',v[k])), 'PHONE_HASH_REJECTED')
    for k in ('initialPaidMinor','paidMinor'):
        require(type(v[k]) is int and -1<=v[k]<=10**12, 'PHONE_PAID_REJECTED')
    for k in ('initialScratch','scratch'):
        require(number(v[k],-1,1), 'PHONE_SCRATCH_REJECTED')
    for k,n in VECTORS.items():
        require(type(v[k]) is list and len(v[k])==n and all(number(x,-1000,1000) for x in v[k]), 'PHONE_VECTOR_REJECTED')
    routes=v['routes'];require(type(routes) is list and len(routes)<=4, 'PHONE_ROUTES_REJECTED')
    for i,r in enumerate(routes):
        require(type(r) is dict and set(r)=={'segment','frames','outcome','elapsedMs','pathMeters','maxFrameWall','remaining','position'}, 'PHONE_ROUTE_FIELDS_REJECTED')
        require(type(r['segment']) is int and r['segment']==i and type(r['frames']) is int and 0<=r['frames']<=1000000, 'PHONE_ROUTE_INDEX_REJECTED')
        require(r['outcome'] in ('BEGIN','MOVING','REACHED','ABORTED'), 'PHONE_ROUTE_STATUS_REJECTED')
        require(number(r['elapsedMs'],0,480000) and number(r['pathMeters'],0,10000) and number(r['maxFrameWall'],0,480) and number(r['remaining'],0,1000), 'PHONE_ROUTE_NUMERIC_REJECTED')
        require(type(r['position']) is list and len(r['position'])==3 and all(number(x,-1000,1000) for x in r['position']), 'PHONE_ROUTE_POSITION_REJECTED')
        if i<len(routes)-1: require(r['outcome']=='REACHED', 'PHONE_ROUTE_ORDER_REJECTED')
        if r['elapsedMs']>=45000: require(v['timing']=='TIMING_FAIL', 'PHONE_HIDDEN_TIMING_FAILURE')
    if v['routeComplete'] or v['status']=='FUNCTIONAL_ROUTE_AND_STATE_OBSERVED':
        require(v['setupComplete'] and v['phoneOpened'] and v['cameraRestored'] and v['finalSeated'] and not v['phoneFocused'], 'PHONE_FUNCTIONAL_FLAGS_REJECTED')
        require(len(routes)==4 and all(r['outcome']=='REACHED' and r['remaining']<=.091 and r['frames']>0 for r in routes), 'PHONE_INCOMPLETE_ROUTE')
        require(v['initialStateHash']==v['stateHash']!='UNAVAILABLE' and v['initialTicketHash']==v['ticketHash']!='UNAVAILABLE', 'PHONE_STATE_CHANGED')
        require(v['initialPaidMinor']==v['paidMinor']>0 and 0<v['initialScratch']==v['scratch']<1, 'PHONE_TICKET_CHANGED')
        require(v['cameraPositionBefore']==v['cameraPositionAfter'] and v['cameraRotationBefore']==v['cameraRotationAfter'], 'PHONE_CAMERA_CHANGED')
    if v['status']=='FUNCTIONAL_ROUTE_AND_STATE_OBSERVED':
        require(v['routeComplete'] and v['cleanupComplete'] and not v['deadlineExceeded'] and v['elapsedMs']<180000 and v['stage']=='TEARDOWN', 'PHONE_COMPLETION_DEADLINE_REJECTED')
    return v

def verify_preparation(root):
    """Same-job authored assets, exact successful native prerequisite; no raw exports."""
    import reflection_bake_ci as reflection
    ident=identity(root)
    native=read_json(outdir(root)/'safe-phone-return-prepare.json',65536)
    require(all(native[k]==ident[k] for k in ('sourceCommit','reviewedCandidateCommit','runId','runAttempt')),
            'PHONE_PREPARATION_SOURCE_REJECTED')
    require(native['phase']=='phone-return-prepare' and native['processBudgetSeconds']==1800 and
            native['status']=='NATIVE_SUCCEEDED' and native['nativeExitCode']==native['dockerExitCode']==0 and
            native['nativeExitMarkerCount']==1, 'PHONE_PREPARATION_NATIVE_REQUIRED')
    require(type(native['nativeStartedAtNs']) is int and native['nativeStartedAtNs']>0, 'PHONE_PREPARATION_START_REQUIRED')
    source=root/TASK/'unity/Assets/G3/Shop/Resources/G3/Shop'
    # The bake receipt is rebound to this exact run by the existing Editor baker.
    raw=read_regular(source/'Reflections/reflection-receipt.json',reflection.TEXT_LIMIT,native['nativeStartedAtNs'])
    receipt=reflection.validate_receipt(reflection.load_receipt(raw),ident)
    require(reflection.source_digest(root,receipt)==receipt['sourceDigest'], 'PHONE_PREPARATION_INPUT_DRIFT')
    prefab=read_regular(source/'LotteryShop_Runtime.prefab',8*1024*1024)
    require(len(prefab)>0, 'PHONE_PREPARATION_PREFAB_MISSING')
    outputs=[]
    for key in ('day','night'):
        item=receipt[key]
        data=read_regular(source/'Reflections'/item['file'],reflection.EXR_LIMIT)
        meta=read_regular(source/'Reflections'/(item['file']+'.meta'),reflection.TEXT_LIMIT)
        require(len(data)==item['bytes'] and reflection.digest(data)==item['sha256'] and
                len(meta)==item['metaBytes'] and reflection.digest(meta)==item['metaSha256'], 'PHONE_PREPARATION_CUBE_HASH_REJECTED')
        require(reflection.exr_size(data)==(item['sourceWidth'],item['sourceHeight']), 'PHONE_PREPARATION_CUBE_DIMENSIONS_REJECTED')
        reflection.validate_meta(meta)
        require(re.findall(r'^guid: ([0-9a-f]{32})$',meta.decode('utf-8'),re.M)==[item['metaGuid']], 'PHONE_PREPARATION_CUBE_GUID_REJECTED')
        outputs.append(dict(role=key.upper(),bytes=len(data),sha256=reflection.digest(data),metaSha256=reflection.digest(meta)))
    summary=dict(ident,schemaVersion=1,status='AUTHORED_PREPARATION_OBSERVED_NOT_FUNCTIONAL_PASS',
                 preparationBudgetSeconds=1800,caseBudgetSeconds=180,phoneProcessBudgetSeconds=480,
                 prefabSha256=reflection.digest(prefab),prefabBytes=len(prefab),reflectionSourceSha256=receipt['sourceDigest'],
                 reflectionReceiptSha256=reflection.digest(raw),cubes=outputs)
    write(outdir(root)/'preparation-observation.json',summary)
    return summary


def unique_pairs(pairs):
    value={}
    for key,item in pairs:
        require(key not in value, 'PHONE_DUPLICATE_JSON_KEY')
        value[key]=item
    return value

def read_regular(path, limit, started_ns=0):
    require(not path.is_symlink() and path.is_file() and path.stat().st_size<=limit and path.stat().st_mtime_ns>=started_ns, 'PHONE_FILE_REJECTED')
    data=path.read_bytes(); require(len(data)<=limit, 'PHONE_FILE_LIMIT');return data

def test_summary(data):
    # No raw XML, assertion messages, captured output or stack traces are exported.
    require(len(data)<=1048576 and b'<!DOCTYPE' not in data.upper() and b'<!ENTITY' not in data.upper(), 'PHONE_XML_REJECTED')
    tree=ET.fromstring(data);cases=list(tree.iter('test-case'));assemblies=[n for n in tree.iter('test-suite') if n.get('type')=='Assembly']
    require(tree.tag=='test-run' and len(cases)==1 and cases[0].get('fullname')==CASE and len(assemblies)==1 and assemblies[0].get('name')==ASSEMBLY and list(assemblies[0].iter('test-case'))==cases, 'PHONE_EXACT_CASE_REJECTED')
    passed=all(n.get('result')=='Passed' for n in [tree,*tree.iter('test-suite'),*cases]) and tree.get('total')=='1' and tree.get('passed')=='1' and all(tree.get(k)=='0' for k in ('failed','skipped','inconclusive'))
    return 'EXACT_CASE_PASSED' if passed else 'EXACT_CASE_NOT_PASSED'

def export(root):
    ident=identity(root);target=outdir(root)/'phone-return-observation.json'
    target.unlink(missing_ok=True)
    result=dict(ident, schemaVersion=1,status='INCONCLUSIVE',timing='NOT_OBSERVED',native='UNAVAILABLE',nunit='UNAVAILABLE',observation=None,segmentOutcomes=['NOT_REACHED']*4)
    try:
        verify_preparation(root)
        native=read_json(outdir(root)/'safe-phone-return-probe.json',65536)
        require(all(native[k]==ident[k] for k in ('sourceCommit','reviewedCandidateCommit','runId','runAttempt')) and native['phase']=='phone-return-probe' and native['processBudgetSeconds']==480, 'PHONE_NATIVE_BINDING_REJECTED')
        started=native['nativeStartedAtNs'];require(type(started) is int and started>0,'PHONE_START_REJECTED')
        result['native']='NATIVE_SUCCEEDED' if native['status']=='NATIVE_SUCCEEDED' and native['nativeExitCode']==native['dockerExitCode']==0 and native['nativeExitMarkerCount']==1 else 'NATIVE_NOT_SUCCEEDED'
        source=root/TASK/'artifacts/phone-return-probe'
        try:
            value=json.loads(read_regular(source/'phone-return.json',65536,started),object_pairs_hook=unique_pairs)
            result['observation']=validate_observation(value,ident);result['timing']=value['timing']
            for row in value['routes']:
                result['segmentOutcomes'][row['segment']]='REACHED' if row['outcome']=='REACHED' else 'ABORTED_OR_UNOBSERVED_AT_END'
        except Exception:
            result['observation']=None
        try: result['nunit']=test_summary(read_regular(source/'playmode-results.xml',1048576,started))
        except Exception: result['nunit']='MISSING_OR_REJECTED'
        if result['native']=='NATIVE_SUCCEEDED' and result['nunit']=='EXACT_CASE_PASSED' and result['observation'] and result['observation']['status']=='FUNCTIONAL_ROUTE_AND_STATE_OBSERVED':
            result['status']='FUNCTIONAL_ROUTE_AND_STATE_OBSERVED'
    except Exception:
        pass
    write(target,result)
    require(result['status']=='FUNCTIONAL_ROUTE_AND_STATE_OBSERVED','PHONE_OBSERVATION_INCOMPLETE')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('guard','disk-prepare','prepare','export','export-diagnostics'));args=parser.parse_args();root=Path(__file__).resolve().parents[3]
    if args.command=='guard': guard(root)
    elif args.command=='disk-prepare': require(prepare_runner_disk(root)==0,'RUNNER_DISK_PREPARATION_REJECTED')
    elif args.command=='prepare': identity(root);bounded.restore(root)
    elif args.command=='export-diagnostics': export_diagnostics(root)
    else: export(root)

if __name__=='__main__':
    try: main()
    except BaseException:
        print('PHONE_RETURN_DIAGNOSTIC_REJECTED',file=sys.stderr);sys.exit(1)
