#!/usr/bin/env python3
"""Private Stage-A observer adapter for the EXISTING visual diagnostic only.

No native invocation, settings mutation, formal G3 guard adaptation or upload.
CLI accepts only before/after/publish. Identity/paths/exits are never CLI inputs.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time
import post_capture_safety as telemetry

sys.dont_write_bytecode = True
TASK = 'tasks/lottery-shop'
SCRIPT = TASK + '/scripts/stage_a_inventory_ci.py'
PACKAGE = TASK + '/scripts/stage_a_inventory'
WORKFLOW = '.github/workflows/lottery-visual-candidate.yml'
PUBLIC_NAME = 'shop-inventory-not-source-waiver-not-g3-pass.json'
MAX_JSON = 4 * 1024 * 1024
MAX_INPUT = 256 * 1024 * 1024
SCOPE = 'SHOP_INVENTORY_DIAGNOSTIC_NOT_SOURCE_WAIVER_NOT_G3_PASS'
STATES = {'NATIVE_SUCCEEDED', 'NATIVE_FAILED', 'INCONSISTENT_NATIVE_RESULT',
          'PROCESS_TIMEOUT', 'OUTPUT_LIMIT_OR_INPUT_REJECTED', 'CANCELLED',
          'ADAPTER_FAILED', 'SESSION_OR_TEST_ADAPTER_FAILED',
          'RETURN_NOT_RUN_SESSION_BLOCKED', 'RETURN_NOT_RUN_OWNERSHIP_UNVERIFIED',
          'CLEANUP_NOT_VERIFIED', 'NOT_STARTED', 'START_ADAPTER_FAILED'}

OBSERVER_CODES = ['ANCESTOR_REPLACED', 'BEFORE_CLAIMS', 'BEFORE_CONTEXT', 'BEFORE_EXPECTED_HASH', 'BEFORE_FILES', 'BEFORE_HASH', 'BEFORE_IDENTITY_MISMATCH', 'BEFORE_NOT_COLD_SOURCE', 'BEFORE_PATHS', 'BEFORE_PROJECTION_LABEL', 'BEFORE_PROJECTION_TAMPERED', 'BEFORE_RECORD', 'BEFORE_RECORD_TYPE', 'BEFORE_SAFE_FIELDS', 'BEFORE_SCHEMA', 'BEFORE_SNAPSHOT_TAMPERED', 'CLI_ARGUMENTS', 'DIRECTORY_CHANGED', 'DIRECTORY_LINK_OR_TYPE', 'DIRECTORY_RACE', 'DIRECTORY_REPLACED', 'ENTRY_LIMIT', 'FILE_ALIAS', 'FILE_CHANGED_DURING_READ', 'FILE_EXECUTABLE', 'FILE_LINK_OR_TYPE', 'FILE_RACE', 'FILE_REPLACED', 'FILE_SIZE', 'FROZEN_INPUT_DRIFT', 'FROZEN_SOURCE_MISSING', 'GAME_SOURCE_MISMATCH', 'IDENTITY_COMMIT', 'IDENTITY_CONTEXT', 'IDENTITY_FIELDS', 'IDENTITY_RUN', 'INPUT_DRIFT', 'INPUT_OR_IO_REJECTED', 'JSON_DUPLICATE_KEY', 'JSON_INVALID', 'JSON_NONFINITE', 'JSON_TOO_LARGE', 'MESH_OBSERVATION_LIMIT', 'META_DUPLICATE_KEY', 'META_ENCODING', 'META_ENCODING_OR_SIZE', 'META_LINE_SIZE', 'META_SENSITIVE_KEY', 'META_SENSITIVE_OR_BUNDLE_VALUE', 'META_SIZE', 'META_UNSUPPORTED_FLOW', 'META_UNSUPPORTED_SCALAR', 'META_UNSUPPORTED_STRUCTURE', 'META_UNSUPPORTED_SYNTAX', 'NATIVE_EXIT_INVALID', 'OUTPUT_INSIDE_PROJECT', 'OUTPUT_LINK_CHANGED', 'OUTPUT_REPLACED', 'PATH_REJECTED', 'PHASE_REJECTED', 'POLICY_DRIFT', 'RECIPE_COLLISION', 'RECIPE_NAME', 'REFLECTION_GUID', 'REFLECTION_META_DUPLICATE_KEY', 'REFLECTION_META_FIELD_OR_VALUE_REJECTED', 'REFLECTION_META_IMPORT_REJECTED', 'REFLECTION_META_LINE_REJECTED', 'REFLECTION_META_LIST_REJECTED', 'REFLECTION_META_PLATFORM_REJECTED', 'REFLECTION_META_ROOT_REJECTED', 'REFLECTION_META_SIZE_REJECTED', 'REFLECTION_META_STRUCTURE_REJECTED', 'REPORT_SIZE', 'ROOT_NOT_ABSOLUTE', 'SOURCE_DUPLICATE', 'TOTAL_SIZE', 'TRACKED_GUID_CHANGED', 'UNKNOWN_DIRECTORY', 'UNKNOWN_PATH']

# Finite diagnostic alphabet only. None of these labels is copied from input.
META_FLOW_ASSETS = ('MODEL_INTERIOR', 'MODEL_LAMP', 'MODEL_STAMP', 'MODEL_BOX',
                    'SOURCE_PAIRED_META', 'SOURCE_DIRECTORY_META',
                    'GENERATED_DIRECTORY_META', 'GENERATED_ASSET_META',
                    'BOUNDED_MESH_META', 'OTHER_META')
META_FLOW_FIELDS = ('MODEL_EXTERNAL_FIRST', 'MODEL_EXTERNAL_SECOND',
                    'MODEL_INTERNAL_ID_FIRST', 'MODEL_INTERNAL_ID_SECOND',
                    'MODEL_OTHER', 'OTHER')
META_FLOW_SHAPES = ('MATERIAL_CORE_KNOWN', 'MATERIAL_LEGACY_KNOWN',
                    'MATERIAL_CORE_UNKNOWN_NAME', 'TYPED_IDENTIFIER_OTHER',
                    'INTEGER_PAIR_BOUNDED', 'INTEGER_PAIR_OTHER',
                    'RGBA_FINITE_BOUNDED', 'RGBA_OTHER',
                    'REFERENCE_BOUNDED_NONCANONICAL', 'REFERENCE_OTHER',
                    'DUPLICATE_KEYS', 'NESTED_COLLECTION', 'YAML_SPECIAL',
                    'LIMIT', 'OTHER')
META_FLOW_CODES = frozenset('META_UNSUPPORTED_FLOW__' + asset + '__' + field + '__' + shape
                            for asset in META_FLOW_ASSETS for field in META_FLOW_FIELDS
                            for shape in META_FLOW_SHAPES)

OBSERVER_CODES += sorted(META_FLOW_CODES)

class Blocked(ValueError):
    pass

def require(ok, code):
    if not ok: raise Blocked(code)

def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)+'\n').encode()
def unique(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, 'JSON_DUPLICATE_KEY'); out[key] = value
    return out

def parse(raw):
    require(len(raw) <= MAX_JSON, 'JSON_LIMIT')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: require(False, 'JSON_NONFINITE'))

def regular(path, maximum=MAX_JSON):
    path = Path(path).absolute()
    for parent in path.parents:
        require(stat.S_ISDIR(parent.lstat().st_mode), 'PATH_ANCESTOR')
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= maximum, 'PATH_TYPE_OR_LIMIT')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        require((opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino), 'PATH_REPLACED')
        chunks = []; total = 0
        while True:
            part = os.read(fd, min(1024*1024, maximum + 1 - total))
            if not part: break
            chunks.append(part); total += len(part)
            require(total <= maximum, 'PATH_LIMIT')
        final = os.fstat(fd); current = path.lstat()
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink, s.st_mode)
        require(stamp(info) == stamp(final) == stamp(current), 'PATH_CHANGED')
        return b''.join(chunks)
    finally: os.close(fd)

def load(path): return parse(regular(path))
def write_new(path, value):
    raw = canonical(value); require(len(raw) <= MAX_JSON, 'JSON_LIMIT')
    require(path.parent.resolve() == path.parent.absolute(), 'OUTPUT_PARENT')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    except BaseException:
        raise
    require(regular(path) == raw, 'OUTPUT_READBACK')
    return sha(raw)

def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=60, check=False)
    require(result.returncode == 0 and len(result.stdout) <= 8*1024*1024, 'GIT_REJECTED')
    return result.stdout

def paths():
    root = Path(os.environ['GITHUB_WORKSPACE']).absolute()
    temp = Path(os.environ['RUNNER_TEMP']).absolute()
    require(root.resolve() == root and temp.resolve() == temp and root != temp and root not in temp.parents, 'PRIVATE_ROOT_LOCATION')
    for key in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'):
        require(re.fullmatch(r'[1-9][0-9]{0,19}', os.environ.get(key, '')), 'RUN_IDENTITY')
    require(os.environ['GITHUB_RUN_ATTEMPT'] == '1', 'ORIGINAL_FIRST_ATTEMPT_ONLY')
    home = temp / ('lottery-shop-inventory-' + os.environ['GITHUB_RUN_ID'] + '-1')
    return root, home

def modules(code):
    # Every import comes from the protected, exact-hash dependency copy.
    sys.path.insert(0, str(code))
    import visual_candidate_ci as visual
    import g2_ci as g2
    import activation_probe as private
    spec = importlib.util.spec_from_file_location('stage_a_observer', code/'inventory/g3_shop_inventory.py')
    inv = importlib.util.module_from_spec(spec); spec.loader.exec_module(inv)
    return visual, g2, private, inv

def seed_code(root, home):
    lock = load(root/PACKAGE/'dependency-lock.json')
    require(set(lock) == {'schemaVersion', 'files'} and lock['schemaVersion'] == 1 and type(lock['files']) is dict, 'DEPENDENCY_LOCK')
    require(1 <= len(lock['files']) <= 32, 'DEPENDENCY_COUNT')
    # The lock itself and all helpers must be reviewed committed source, not local overrides.
    require(git(root, 'show', 'HEAD:'+PACKAGE+'/dependency-lock.json') == regular(root/PACKAGE/'dependency-lock.json'), 'DEPENDENCY_LOCK_DRIFT')
    for target, row in lock['files'].items():
        require(re.fullmatch(r'[A-Za-z0-9_./-]+', target) and all(x not in ('', '.', '..') for x in target.split('/')), 'DEPENDENCY_PATH')
        require(type(row) is dict and set(row) == {'path', 'sha256'}, 'DEPENDENCY_RECORD')
        require(row['path'].startswith(TASK+'/scripts/') and '..' not in row['path'].split('/'), 'DEPENDENCY_PATH')
        raw = regular(root/row['path'])
        require(sha(raw) == row['sha256'] and raw == git(root, 'show', 'HEAD:'+row['path']), 'DEPENDENCY_DRIFT')
        destination = home/'code'/target; destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with destination.open('xb') as stream: stream.write(raw)
    require(regular(home/'code/stage_a_inventory_ci.py') == regular(root/SCRIPT), 'ADAPTER_COPY_DRIFT')
    write_new(home/'dependency-lock.json', lock)

def guard_identity(value, env, inv):
    require(type(value) is dict, 'GUARD_IDENTITY')
    require(value.get('scope') == 'DIAGNOSTIC_VISUAL_CANDIDATE_NOT_G3_PASS', 'GUARD_SCOPE')
    require(value.get('sourceCommit') == env.get('GITHUB_SHA') and value.get('runId') == env.get('GITHUB_RUN_ID') and value.get('runAttempt') == env.get('GITHUB_RUN_ATTEMPT'), 'GUARD_ENV_MISMATCH')
    review = value.get('sourceReview', {})
    require(review.get('sourceCommit') == value.get('reviewedCandidateCommit') and review.get('status') == 'APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY' and review.get('reviewer') == 'independent-source-review', 'GUARD_REVIEW')
    return inv.identity(dict(sourceCommit=value['reviewedCandidateCommit'], triggerCommit=value['sourceCommit'],
        gameSourceCommit=inv.PIN, runId=value['runId'], runAttempt=value['runAttempt'], context='SHOP_IMPORT_INVENTORY_DIAGNOSTIC'))

def source_manifest(root):
    names = git(root, 'ls-files', '-z', '--', TASK, WORKFLOW, '.github/workflows/lottery-activation-probe.yml').decode().split('\0')
    names = sorted(n for n in names if n)
    require(0 < len(names) <= 4096 and len(set(names)) == len(names), 'SOURCE_COUNT')
    records = {}; total_bytes = 0
    for name in names:
        require(all(x not in ('', '.', '..') for x in name.split('/')), 'SOURCE_PATH')
        size = git(root, 'cat-file', '-s', 'HEAD:'+name).strip()
        require(size.isdigit() and int(size) <= MAX_INPUT, 'SOURCE_BLOB_LIMIT')
        total_bytes += int(size); require(total_bytes <= 512*1024*1024, 'SOURCE_BYTES_LIMIT')
        raw = regular(root/name, MAX_INPUT)
        # visual.guard already checks all tracked TASK bytes/modes. This second
        # digest binds every selected byte to HEAD and to protected before state.
        blob = subprocess.run(['git','-C',str(root),'show','HEAD:'+name], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60)
        require(blob.returncode == 0 and len(blob.stdout) <= MAX_INPUT and blob.stdout == raw, 'SOURCE_BYTES')
        records[name] = {'sha256':sha(raw), 'bytes':len(raw), 'mode':stat.S_IMODE((root/name).lstat().st_mode) & 0o111}
    return records

def input_tree(root, baseline, before=False):
    """Bound the diagnostic inputs. Output/cache folders retain old ownership.

    After Unity, project mutations are observations only. Non-project code,
    controls and workflow changes fail closed. No G3 source policy is changed.
    """
    unity = TASK+'/unity/'
    tracked_changes = 0; added = 0; removed = 0; total = 0; total_bytes = 0
    for name, row in baseline.items():
        try: raw = regular(root/name, MAX_INPUT)
        except FileNotFoundError:
            require(name.startswith(unity), 'NON_PROJECT_SOURCE_MISSING'); removed += 1; continue
        changed = sha(raw) != row['sha256'] or len(raw) != row['bytes'] or (stat.S_IMODE((root/name).lstat().st_mode) & 0o111) != row['mode']
        if changed:
            require(not before and name.startswith(unity), 'NON_PROJECT_SOURCE_DRIFT'); tracked_changes += 1
    ignored = {TASK+'/'+n for n in ('artifacts', 'evidence', 'build')} | {unity+n for n in ('Library','Temp','Obj','Logs','UserSettings','.utmp')}
    for directory, dirs, files in os.walk(root/TASK, followlinks=False):
        rel = Path(directory).relative_to(root).as_posix()
        for child in dirs:
            require(stat.S_ISDIR((Path(directory)/child).lstat().st_mode), 'INPUT_DIRECTORY_TYPE')
        dirs[:] = [d for d in dirs if rel+'/'+d not in ignored]
        for filename in files:
            total += 1; require(total <= 10000, 'INPUT_COUNT')
            name = rel+'/'+filename
            raw = regular(root/name, MAX_INPUT)
            total_bytes += len(raw); require(total_bytes <= 512*1024*1024, 'INPUT_BYTES_LIMIT')
            if name in baseline: continue
            if name == unity+'Assets/Resources/ProbeChinese.otf':
                # Caller separately binds this to the unchanged original FONT_SHA.
                continue
            require(not before and name.startswith(unity), 'UNREVIEWED_INPUT')
            added += 1
    return {'status':'BOUNDED_PROJECT_MUTATIONS_OBSERVED_NOT_APPROVED', 'trackedChanged':tracked_changes,
            'untrackedProjectFiles':added, 'missingTrackedProjectFiles':removed, 'formalWholeProjectGuard':'NOT_EVALUATED_UNCHANGED'}

KEY = re.compile(r'^( *)(- )?([A-Za-z_][A-Za-z0-9_.-]*):(.*)$')
def settings_shape(raw):
    """Structural guard atop original scalar credential checks, not YAML parsing.

    Unknown keys/quoted or escaped keys/new multiline syntax cannot become
    publishable merely because the legacy regex did not recognize them.
    """
    text = raw.decode('utf-8', 'strict'); require('\x00' not in text, 'SETTINGS_ENCODING')
    lines = text.splitlines(); require(len(lines) <= 20000, 'SETTINGS_LINES')
    shape = []
    for line in lines:
        require(len(line) <= 8192, 'SETTINGS_LINE_LIMIT')
        match = KEY.fullmatch(line)
        if match:
            value = match[4].strip()
            # YAML block/alias/tag values are deliberately unpublishable until
            # a separate exact review; unchanged opaque baseline lines are bound.
            if value.startswith(('|', '>', '&', '*', '!', '"', "'", '[')):
                shape.append(('opaque', line))
            elif value.startswith('{'):
                # Only canonical numeric/GUID Unity object references may vary.
                ref = re.fullmatch(r'\{fileID: -?[0-9]+(?:, guid: [0-9a-f]{32}, type: [0-9]+)?\}', value)
                shape.append(('key-ref', match[1], match[2], match[3]) if ref else ('opaque', line))
            elif ':' in value or chr(92) in value:
                shape.append(('opaque', line))
            else: shape.append(('key', match[1], match[2], match[3]))
        else: shape.append(('opaque', line))
    return shape

def settings_gate(root, baseline_raw, g2, before=False):
    directory = root/TASK/'unity/ProjectSettings'
    current = {}
    for path in sorted(directory.rglob('*')):
        require(not path.is_symlink(), 'SETTINGS_LINK')
        if path.is_dir(): continue
        relative = path.relative_to(directory).as_posix()
        current[relative] = regular(path, 2*1024*1024)
    require(set(current) == set(baseline_raw), 'SETTINGS_FILE_SET')
    for name, raw in current.items():
        require(settings_shape(raw) == settings_shape(baseline_raw[name]), 'SETTINGS_UNKNOWN_LAYOUT')
    # Direct original pure checks, no G3/global context mutation or normalized file.
    g2.validate_credential_layout(root)
    findings = g2.settings_findings(root, include_field_ids=True)
    original = baseline_raw['ProjectSettings.asset']; now = current['ProjectSettings.asset']
    _, was_set = g2.ps4_scalar_span(original); _, now_set = g2.ps4_scalar_span(now)
    require(not was_set, 'PS4_BASELINE_NOT_EMPTY')
    if before:
        g2.source_preflight(root); require(not now_set, 'PS4_BEFORE_NOT_EMPTY')
    else:
        require(all(x['path'] == g2.SETTINGS_PATH and x['fieldIds'] == ['ps4Passcode'] for x in findings), 'SETTINGS_SENSITIVE_VALUE')
        require(bool(findings) == now_set, 'SETTINGS_FINDINGS_INCONSISTENT')
    return {'status':'ORIGINAL_CREDENTIAL_CHECKS_AND_FIXED_BASELINE_LAYOUT_SCREENED',
            'ps4':'PRIVATE_BOUNDED_SCALAR_OBSERVED' if now_set else 'EMPTY',
            'rawSettingsExported':False, 'normalizationPerformed':False, 'settingsSemanticApproval':'NOT_REVIEWED'}

def observer_cli(home, inv, ident, project, phase, native=None):
    command = [sys.executable, str(home/'code/inventory/g3_shop_inventory.py'), phase,
               '--project', str(project), '--identity', str(home/'identity.json'), '--output', str(home/(phase+'.json'))]
    if phase == 'after':
        state = load(home/'before-state.json')
        command += ['--before',str(home/'before.json'),'--before-sha256',state['beforeSha256'],'--native-exit',str(native)]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'})
    require(len(result.stdout) <= 4096 and result.stderr == b'', 'OBSERVER_OUTPUT')
    envelope = parse(result.stdout)
    if result.returncode == 3 and type(envelope) is dict and set(envelope) == {'status','code'} and envelope['status'] == 'BLOCKED' and envelope['code'] in OBSERVER_CODES:
        raise Blocked('OBSERVER_' + envelope['code'])
    require(result.returncode == (0 if phase == 'before' else 2), 'OBSERVER_EXIT')
    require(type(envelope) is dict and set(envelope) == {'status','reportSha256'} and envelope['status'] == 'CAPTURED_NOT_APPROVED', 'OBSERVER_ENVELOPE')
    raw = regular(home/(phase+'.json')); require(sha(raw) == envelope['reportSha256'], 'OBSERVER_REPORT_HASH')
    value = inv.parse_json(raw); require(value['identity'] == ident, 'OBSERVER_IDENTITY')
    if phase == 'before': inv.validate_before(value, ident, inv.load_policy())
    else: require(value.get('status') == 'INCONCLUSIVE_OBSERVATION_ONLY', 'OBSERVER_NOT_INCONCLUSIVE')
    return sha(raw)

def receipt_summary(capture, finish, session, guard, private):
    # Preserve real native return independently of collection's exit 2.
    for record, phase in ((capture, 'capture'), (finish, 'finish')):
        expected = set(guard) | {'schemaVersion','phase','status','dockerExitCode','nativeExitCode','nativeExitMarkerCount','observations','compilerErrors','cleanup','image','mechanismSourcePin','nativeOutput','testVerdict','elapsedMs','recordedAtUtc'}
        if phase == 'capture':
            expected |= {'counterLightDiagnostic','counterLightDiagnosticFault','nativeStartedAtNs','processBudgetSeconds'}
        if phase == 'finish': expected.add('returnStatus')
        require(type(record) is dict and set(record) == expected, 'NATIVE_RECEIPT_SCHEMA')
        if phase == 'capture':
            # Current safe.test capture shape only; injected diagnostic faults
            # cannot authorize publication, irrespective of native exit status.
            require(type(record['counterLightDiagnostic']) is bool and type(record['counterLightDiagnosticFault']) is str and record['counterLightDiagnosticFault'] == '', 'CAPTURE_DIAGNOSTIC_SELECTOR')
            require(type(record['nativeStartedAtNs']) is int and 0 < record['nativeStartedAtNs'] <= time.time_ns(), 'CAPTURE_NATIVE_START')
            require(type(record['processBudgetSeconds']) is int and record['processBudgetSeconds'] == 1800, 'CAPTURE_NATIVE_BUDGET')
        require(all(record[k] == v for k,v in guard.items()) and type(record['schemaVersion']) is int and record['schemaVersion'] == 1 and record['phase'] == phase, 'NATIVE_RECEIPT_IDENTITY')
        require(record['status'] in STATES and record['image'] == private.IMAGE and record['mechanismSourcePin'] == private.PIN, 'NATIVE_RECEIPT_CONTEXT')
        require(record['nativeOutput'] == 'BOUNDED_MEMORY_ONLY_NO_RAW_LOG' and record['testVerdict'] == 'SEPARATE_EXACT_NUNIT_VALIDATOR_REQUIRED', 'NATIVE_RECEIPT_CONTEXT')
        require(type(record['observations']) is dict and set(record['observations']) == set(private.TOKENS) and all(type(x) is int and 0 <= x <= 10000000 for x in record['observations'].values()), 'NATIVE_OBSERVATIONS')
    def completed_native_result(record):
        # Exact pure decision from frozen safe_project_ci.native: all completed
        # exits, marker consistency and BOTH licensing rejection observations.
        # Exception statuses have no completed native result and cannot publish.
        docker, native, markers = (record[k] for k in ('dockerExitCode', 'nativeExitCode', 'nativeExitMarkerCount'))
        require(type(docker) is int and 0 <= docker <= 255 and
                type(native) is int and 0 <= native <= 255 and
                type(markers) is int and 0 <= markers <= 10000000, 'NATIVE_RESULT_FIELDS')
        consistent = markers == 1 and native == docker
        rejected = record['observations']['invalidLicenseXml400'] > 0 or record['observations']['nativeActivationAborted'] > 0
        status = 'NATIVE_SUCCEEDED' if consistent and docker == 0 and not rejected else ('INCONSISTENT_NATIVE_RESULT' if docker == 0 else 'NATIVE_FAILED')
        return status, consistent, rejected
    capture_status, healthy_exit, licensing_rejection = completed_native_result(capture)
    return_status, _, _ = completed_native_result(finish)
    require(capture['status'] == capture_status, 'CAPTURE_NATIVE_STATUS')
    require(finish['returnStatus'] == return_status, 'RETURN_NATIVE_STATUS')
    # Original safe.test blocks/cleans the session for either condition; its
    # safe.finish could not subsequently make a successful license return.
    require(healthy_exit and not licensing_rejection, 'CAPTURE_SESSION_WOULD_BE_BLOCKED')
    code = capture['nativeExitCode']
    require(set(session) == set(guard) | {'status','activationSucceeded','stagesStarted','cleanup'} and all(session[k] == v for k,v in guard.items()), 'SESSION_IDENTITY')
    require(session['status'] == 'CLOSED' and session['activationSucceeded'] is True and type(session['stagesStarted']) is list and session['stagesStarted'].count('capture') == 1, 'SESSION_NOT_CLOSED')
    for value in (session['cleanup'], finish['cleanup']):
        require(type(value) is dict and set(value) == {'status','removalExitCode'} and value['status'] == 'ABSENCE_VERIFIED' and (value['removalExitCode'] is None or type(value['removalExitCode']) is int), 'CLEANUP_NOT_VERIFIED')
    require(finish['status'] == finish['returnStatus'] == return_status == 'NATIVE_SUCCEEDED', 'LICENSE_RETURN_NOT_SUCCEEDED')
    return {'captureStatus':capture['status'], 'captureNativeExit':code, 'licenseReturnStatus':finish['returnStatus'],
            'containerCleanup':'ABSENCE_VERIFIED', 'regressionVerdicts':'ORIGINAL_UNCHANGED_SEPARATE_RECEIPTS'}

def stopped(guard):
    container = 'lottery-visual-safe-'+guard['runId']+'-'+guard['runAttempt']
    result = subprocess.run(['docker','ps','--all','--filter','name=^/'+container+'$','--format','{{.Names}}'],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    require(result.returncode == 0 and result.stdout.strip() == b'', 'NATIVE_WRITER_NOT_PROVEN_ABSENT')

def context(root, home):
    require(home.resolve() == home and stat.S_IMODE(home.lstat().st_mode) == 0o700, 'PRIVATE_STATE_MODE')
    lock = load(home/'dependency-lock.json')
    for target, row in lock['files'].items():
        require(sha(regular(home/'code'/target)) == row['sha256'], 'PROTECTED_CODE_DRIFT')
    visual, g2, private, inv = modules(home/'code')
    state = load(home/'before-state.json'); guard = state['guard']
    ident = guard_identity(guard, os.environ, inv)
    require(ident == load(home/'identity.json') and regular(root/TASK/'evidence/visual-candidate/source-receipt.json') == regular(home/'source-receipt.json'), 'GUARD_RECEIPT_DRIFT')
    require(git(root,'rev-parse','HEAD').decode().strip() == ident['triggerCommit'] and git(root,'rev-parse','HEAD^').decode().strip() == ident['sourceCommit'], 'SOURCE_CONTEXT_DRIFT')
    require(sha(regular(home/'before.json')) == state['beforeSha256'], 'BEFORE_HASH_DRIFT')
    baseline = {n:regular(home/'settings'/n,2*1024*1024) for n in state['settingsFiles']}
    for n in baseline: require(sha(baseline[n]) == state['settingsFiles'][n], 'SETTINGS_BASELINE_DRIFT')
    return visual, g2, private, inv, state, ident, baseline

def before(root, home):
    require(not home.exists() and not home.is_symlink(), 'PRIVATE_STATE_EXISTS')
    home.mkdir(mode=0o700); seed_code(root, home)
    visual, g2, private, inv = modules(home/'code')
    guard = visual.guard(root); ident = guard_identity(guard, os.environ, inv)
    require(not any((root/TASK/'unity'/n).exists() for n in ('Library','Temp','Obj','Logs','UserSettings','.utmp')), 'NOT_COLD')
    require(not (root/TASK/'build/G3').exists(), 'NOT_COLD')
    records = source_manifest(root); input_tree(root, records, before=True)
    require(sha(regular(root/TASK/'unity/Assets/Resources/ProbeChinese.otf',MAX_INPUT)) == visual.bounded.FONT_SHA, 'FONT_DRIFT')
    baseline = {}
    for path in sorted((root/TASK/'unity/ProjectSettings').rglob('*')):
        if path.is_dir(): continue
        relative = path.relative_to(root/TASK/'unity/ProjectSettings').as_posix(); raw = regular(path,2*1024*1024)
        destination = home/'settings'/relative; destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with destination.open('xb') as stream: stream.write(raw)
        baseline[relative] = raw
    settings_gate(root, baseline, g2, before=True)
    write_new(home/'identity.json',ident)
    with (home/'source-receipt.json').open('xb') as stream: stream.write(regular(root/TASK/'evidence/visual-candidate/source-receipt.json'))
    before_hash = observer_cli(home,inv,ident,root/TASK/'unity','before')
    write_new(home/'before-state.json',{'schemaVersion':1,'guard':guard,'beforeSha256':before_hash,'sourceFiles':records,
        'settingsFiles':{n:sha(raw) for n,raw in baseline.items()}})

def current_observations(root,home,parts):
    visual,g2,private,inv,state,ident,baseline = parts
    telemetry.checkpoint('RECEIPTS')
    evidence = root/TASK/'evidence/visual-candidate'
    native = receipt_summary(load(evidence/'safe-capture.json'),load(evidence/'safe-finish.json'),load(evidence/'safe-session.json'),state['guard'],private)
    telemetry.checkpoint('NATIVE_WRITER_ABSENCE')
    stopped(state['guard'])
    telemetry.checkpoint('FONT')
    require(sha(regular(root/TASK/'unity/Assets/Resources/ProbeChinese.otf',MAX_INPUT)) == visual.bounded.FONT_SHA, 'FONT_DRIFT')
    telemetry.checkpoint('SETTINGS')
    settings = settings_gate(root,baseline,g2)
    telemetry.checkpoint('WORKSPACE')
    workspace = input_tree(root,state['sourceFiles'])
    return native,settings,workspace

def after(root,home):
    telemetry.checkpoint('CONTEXT')
    parts = context(root,home); visual,g2,private,inv,state,ident,baseline = parts
    native,settings,workspace = current_observations(root,home,parts)
    telemetry.checkpoint('OBSERVER')
    after_hash = observer_cli(home,inv,ident,root/TASK/'unity','after',native['captureNativeExit'])
    write_new(home/'after-state.json',{'schemaVersion':1,'afterSha256':after_hash,'native':native,'settings':settings,'workspace':workspace})

def validate_report(raw,expected_hash,inv,ident,project,before_raw,before_hash,native):
    require(sha(raw) == expected_hash and sha(before_raw) == before_hash, 'REPORT_HASH')
    value = inv.parse_json(raw); old = inv.parse_json(before_raw); policy = inv.load_policy()
    inv.validate_before(old,ident,policy)
    # Rebuild from stopped source bytes, not a permissive validator of arbitrary
    # strings supplied by the report. All schema keys/safe values must match.
    snap = inv.snapshot(project,ident,policy,'AFTER')
    expected = inv.compare(old,snap,policy,native); expected['beforeSnapshotSha256'] = before_hash
    require(value == expected and canonical(expected) == raw, 'REPORT_SCHEMA_OR_SOURCE')
    return value

def publish(root,home):
    telemetry.checkpoint('CONTEXT')
    parts = context(root,home); visual,g2,private,inv,state,ident,baseline = parts
    native,settings,workspace = current_observations(root,home,parts)
    after_state = load(home/'after-state.json')
    require(set(after_state) == {'schemaVersion','afterSha256','native','settings','workspace'} and type(after_state['schemaVersion']) is int and after_state['schemaVersion'] == 1 and
            after_state['native'] == native and after_state['settings'] == settings and after_state['workspace'] == workspace, 'AFTER_STATE_DRIFT')
    telemetry.checkpoint('REPORT')
    report = validate_report(regular(home/'after.json'),after_state['afterSha256'],inv,ident,root/TASK/'unity',regular(home/'before.json'),state['beforeSha256'],native['captureNativeExit'])
    envelope = {'schemaVersion':1,'scope':SCOPE,'status':'INCONCLUSIVE_OBSERVATION_ONLY','identity':ident,
        'collectionExitCode':2,'guardSourceReceiptSha256':sha(regular(home/'source-receipt.json')),
        'beforeSourceManifestSha256':sha(canonical(state['sourceFiles'])),'observerReportSha256':after_state['afterSha256'],'inventory':report,'native':native,
        'settingsSafety':settings,'workspaceObservation':workspace,'formalSourceWaiver':False,'g3Pass':False,
        'formalEligibility':'NOT_EVALUATED','publicationMeaning':'SAFE_DIAGNOSTIC_JSON_ONLY_NOT_NATIVE_OR_SOURCE_ACCEPTANCE'}
    destination = root/TASK/'evidence/visual-candidate'/PUBLIC_NAME
    telemetry.checkpoint('PUBLISH')
    checksum = write_new(destination,envelope)
    # Upload action has an exact path, and this output exists only after full validation.
    output = Path(os.environ['GITHUB_OUTPUT'])
    with output.open('a',encoding='utf-8') as stream: stream.write('publishable=true\nreport_sha256='+checksum+'\n')

def main():
    try:
        require(len(sys.argv) == 2 and sys.argv[1] in {'before','after','publish'}, 'CLI_ARGUMENTS')
        telemetry.begin('inventory',sys.argv[1])
        root,home = paths()
        if sys.argv[1] == 'before': before(root,home)
        else:
            require(Path(__file__).absolute() == home/'code/stage_a_inventory_ci.py', 'PROTECTED_ADAPTER_REQUIRED')
            (after if sys.argv[1] == 'after' else publish)(root,home)
        telemetry.checkpoint('DONE');telemetry.persist('COMPLETED','NONE')
        print(json.dumps({'status':'STAGE_A_COMPLETED_NOT_APPROVED','phase':sys.argv[1]})); return 0
    except BaseException as error:
        return telemetry.fail(error)

if __name__ == '__main__': raise SystemExit(main())
