"""Exact four keyboard-look PlayMode cases and original source/union checkpoint."""
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import shutil
import stat
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / 'tasks/desert-rv'
PROJECT = TASK / 'unity'
REPORT = TASK / 'journey-keyboard-look-native-report.json'
SOURCE_REPORT = TASK / 'journey-keyboard-look-source-report.json'
ARTIFACTS = TASK / 'artifacts/journey-keyboard-look'
TEST_SOURCE = 'tasks/desert-rv/unity/Assets/DesertRV/Tests/PlayMode/JourneyReplayInputTests.cs'
PREFIX = 'DesertRV.Tests.JourneyReplayInputTests.'
EXPECTED = tuple(PREFIX + name for name in (
    'KeyboardLook_RateAndBounds',
    'KeyboardLook_ContextAndRelease',
    'KeyboardLook_PreservesExistingSources',
    'KeyboardLook_EditorReplayIsExclusive',
))
PREPARATION_REPORTS = TASK / 'journey-preparation-export/keyboard-look'


def require(ok, code):
    if not ok:
        raise ValueError(code)


def digest(path):
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), 'UNSAFE_INPUT')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_xml(folder):
    require(folder.is_dir() and not folder.is_symlink(), 'XML_MISSING')
    require(len(EXPECTED) == 4 and len(set(EXPECTED)) == 4, 'EXPECTED_INVENTORY')
    paths = list(folder.rglob('*.xml'))
    require(len(paths) == 1, 'XML_COUNT')
    path = paths[0]
    require(path.stat().st_size <= 1024 * 1024, 'XML_SIZE')
    sha = digest(path)
    raw = path.read_bytes()
    require(b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper(), 'XML_DECLARATION')
    root = ET.fromstring(raw)
    cases = list(root.iter('test-case'))
    names = [case.get('fullname') for case in cases]
    require(root.tag == 'test-run' and root.get('result') == 'Passed' and
            root.get('total') == '4' and root.get('passed') == '4' and
            all(root.get(key) == '0' for key in ('failed', 'skipped', 'inconclusive')) and
            len(names) == 4 and len(set(names)) == 4 and set(names) == set(EXPECTED) and
            all(case.get('result') == 'Passed' for case in cases), 'EXACT_FOUR_REQUIRED')
    results = []
    for case in cases:
        row = dict(fullname=case.get('fullname'), result=case.get('result'))
        if case.get('duration') is not None:
            duration = float(case.get('duration'))
            require(math.isfinite(duration) and 0 <= duration <= 86400, 'XML_DURATION')
            row['durationSeconds'] = duration
        results.append(row)
    return sha, sorted(results, key=lambda row: row['fullname'])


def verify_unchanged(context=None):
    from journey_tracer_native import verify_unchanged as original
    return original(context)


# Fixed same-job project copy. No caller-controlled paths and no settings restoration.
COPY = TASK / 'journey-keyboard-look-project'
OWNER = TASK / 'journey-keyboard-look-copy-owner.json'
ISOLATION_REPORT = TASK / 'journey-keyboard-look-isolation-report.json'
COPY_REL = 'tasks/desert-rv/journey-keyboard-look-project'
SETTINGS = 'ProjectSettings/ProjectSettings.asset'
SOURCE_PREFIX = 'tasks/desert-rv/unity/'
COPY_MARKER = '.journey-keyboard-look-owner.json'
MAX_DIFF = 65536
MAX_ISOLATION_REPORT = 98304
OPERATIONS = {'Library', 'Temp', 'Logs', 'obj', 'UserSettings', 'JourneyEvidence'}
SENSITIVE = re.compile(r'password|passwd|secret|credential|token|private.?key|keystore|signing|certificate', re.I)


def safe_path(path):
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'UNSAFE_PATH')
    require(path.resolve() == path.absolute(), 'UNSAFE_PATH')


def file_bytes(path, limit=128 * 1024**2):
    safe_path(path)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit, 'UNSAFE_FILE')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino, opened.st_size) == (info.st_dev, info.st_ino, info.st_size), 'FILE_CHANGED')
        raw = stream.read(limit + 1)
        require(len(raw) == info.st_size and os.fstat(stream.fileno()).st_mtime_ns == opened.st_mtime_ns, 'FILE_CHANGED')
    return raw


def raw_pin(raw):
    return dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def fixed_copy_path():
    safe_path(ROOT); safe_path(TASK); safe_path(PROJECT); safe_path(COPY); safe_path(OWNER)
    require(COPY == ROOT / COPY_REL and COPY.parent == PROJECT.parent and COPY != PROJECT, 'COPY_PATH')
    require(TASK.is_dir() and PROJECT.is_dir(), 'COPY_PATH')


def copy_baseline(env):
    import journey_tracer_source_diagnostic as diagnostic
    source, _, source_sha = diagnostic.pinned_baseline(env)
    rows = {row['path'][len(SOURCE_PREFIX):]: dict(sha256=row['sha256'], bytes=row['size'])
            for row in source['files'] + source['restoredFiles'] if row['path'].startswith(SOURCE_PREFIX)}
    require(0 < len(rows) <= 4096 and SETTINGS in rows, 'COPY_BASELINE')
    require(all(name.startswith(('Assets/', 'Packages/', 'ProjectSettings/')) and '..' not in Path(name).parts for name in rows), 'COPY_BASELINE')
    return rows, source_sha


def protected_inventory(project):
    files = {}; dirs = set()
    pending = [project / name for name in ('Assets', 'Packages', 'ProjectSettings')]
    count = total = 0
    while pending:
        folder = pending.pop(); safe_path(folder)
        require(folder.is_dir(), 'COPY_DIRECTORY')
        dirs.add(folder.relative_to(project).as_posix())
        for path in sorted(folder.iterdir()):
            count += 1; require(count <= 12000, 'COPY_LIMIT')
            safe_path(path); info = path.lstat(); name = path.relative_to(project).as_posix()
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
            else:
                raw = file_bytes(path); total += len(raw); require(total <= 1024**3, 'COPY_LIMIT')
                files[name] = raw_pin(raw)
    return files, dirs


def write_new(path, value, limit):
    safe_path(path)
    raw = (json.dumps(value, indent=2) + '\n').encode()
    require(len(raw) <= limit and not path.exists(), 'REPORT_PATH')
    with path.open('xb') as stream: stream.write(raw)


def owner_identity(env):
    value = blank_report(env)
    return {key: value[key] for key in ('sourceCommit', 'runId', 'runAttempt')}


def load_owner(env):
    fixed_copy_path()
    value = json.loads(file_bytes(OWNER, 65536))
    require(set(value) == {'schema', 'sourceCommit', 'runId', 'runAttempt', 'sourceStateSha256', 'token', 'device', 'inode', 'copyComplete', 'directories'}, 'OWNER_SCHEMA')
    require(value['schema'] == 1 and all(value[key] == item for key, item in owner_identity(env).items()), 'OWNER_IDENTITY')
    require(re.fullmatch('[a-f0-9]{32}', value['token']) and re.fullmatch('[a-f0-9]{64}', value['sourceStateSha256']), 'OWNER_SCHEMA')
    require(type(value['copyComplete']) is bool and type(value['directories']) is list and len(value['directories']) <= 12000, 'OWNER_SCHEMA')
    require(all(isinstance(name, str) and name.startswith(('Assets', 'Packages', 'ProjectSettings')) and '..' not in Path(name).parts and not name.startswith('/') for name in value['directories']), 'OWNER_SCHEMA')
    info = COPY.lstat(); original = PROJECT.stat()
    require(stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == (value['device'], value['inode']) and
            (info.st_dev, info.st_ino) != (original.st_dev, original.st_ino), 'OWNER_INODE')
    marker = json.loads(file_bytes(COPY / COPY_MARKER, 2048))
    require(marker == dict(owner_identity(env), token=value['token']), 'OWNER_MARKER')
    return value


def output(env, text):
    with open(env['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream: stream.write(text)


def create_copy(env):
    fixed_copy_path(); verify_unchanged()
    rows, source_sha = copy_baseline(env)
    actual, directories = protected_inventory(PROJECT)
    require(actual == rows, 'COPY_INITIAL_SOURCE')
    require(not COPY.exists() and not OWNER.exists(), 'COPY_EXISTS')
    COPY.mkdir(mode=0o700); info = COPY.stat()
    value = dict(schema=1, **owner_identity(env), sourceStateSha256=source_sha, token=uuid.uuid4().hex,
                 device=info.st_dev, inode=info.st_ino, copyComplete=False, directories=sorted(directories))
    write_new(COPY / COPY_MARKER, dict(owner_identity(env), token=value['token']), 2048)
    write_new(OWNER, value, 65536)
    output(env, 'copy_created=true\n')
    for name in sorted(directories, key=lambda name: (name.count('/'), name)):
        (COPY / name).mkdir()
    for name, pin in rows.items():
        source = PROJECT / name; target = COPY / name; raw = file_bytes(source)
        require(raw_pin(raw) == pin, 'COPY_INITIAL_SOURCE')
        with target.open('xb') as stream: stream.write(raw)
        require(raw_pin(file_bytes(target)) == pin and (source.stat().st_dev, source.stat().st_ino) !=
                (target.stat().st_dev, target.stat().st_ino), 'COPY_BYTES_OR_INODE')
    require(protected_inventory(COPY) == (rows, directories), 'COPY_NOT_IDENTICAL')
    verify_unchanged()
    value['copyComplete'] = True
    # Private owner state only; never updates SOURCE or any formal project bytes.
    with OWNER.open('w', encoding='utf-8') as stream: json.dump(value, stream, sort_keys=True)
    load_owner(env)
    output(env, 'copy_ready=true\n')
    return 0


class SettingsRejected(ValueError):
    def __init__(self, field, reason, before_kind='NOT_CHECKED', after_kind='NOT_CHECKED'):
        self.before_kind = before_kind
        self.after_kind = after_kind
        self.field = field if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_ ]{0,95}', field) else 'UNSAFE_FIELD_NAME'
        self.reason = reason
        super().__init__('SETTINGS_REJECTED')


EMPTY_KINDS = {'EMPTY_NULL', 'EMPTY_STRING'}
VALUE_KINDS = EMPTY_KINDS | {'ABSENT', 'NONEMPTY_OR_UNSAFE', 'NOT_CHECKED'}


def empty_setting_kind(field, block, value):
    if block is None: return 'ABSENT'
    if len(block) != 1 or re.fullmatch(r'  ' + re.escape(field) + r':[ \t]*(?:null|Null|NULL|~|\'\'|"")?[ \t]*\n', block[0]) is None:
        return 'NONEMPTY_OR_UNSAFE'
    if value is None: return 'EMPTY_NULL'
    if type(value) is str and value == '': return 'EMPTY_STRING'
    return 'NONEMPTY_OR_UNSAFE'


def settings_diff(before, after, allowed_empty=None):
    require(len(before) <= MAX_DIFF and len(after) <= MAX_DIFF, 'SETTINGS_SIZE')
    old = before.decode('utf-8'); new = after.decode('utf-8')
    require(old.endswith('\n') and new.endswith('\n') and '\r' not in old + new and '\x00' not in old + new, 'SETTINGS_TEXT')
    # Public owned configuration only. No serialized object construction, custom
    # YAML tags, aliases, credentials, local absolute paths or unbounded values.
    import yaml
    def parse(text):
        require(text.splitlines()[:4] == old.splitlines()[:4], 'SETTINGS_HEADER')
        body = '\n'.join(text.splitlines()[3:])
        if any(token in body for token in ('!!', '&', '*')): raise SettingsRejected('PlayerSettings', 'YAML_ALIAS_OR_TAG')
        class UniqueLoader(yaml.SafeLoader): pass
        def mapping(loader, node):
            result = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=True)
                if type(key) not in (str, int): raise SettingsRejected('PlayerSettings', 'UNSAFE_FIELD_NAME')
                if key in result: raise SettingsRejected(str(key), 'YAML_DUPLICATE')
                result[key] = loader.construct_object(value_node, deep=True)
            return result
        UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
        try: parsed = yaml.load(body, Loader=UniqueLoader)
        except yaml.YAMLError: raise SettingsRejected('PlayerSettings', 'YAML_INVALID')
        if not isinstance(parsed, dict) or set(parsed) != {'PlayerSettings'} or not isinstance(parsed['PlayerSettings'], dict): raise SettingsRejected('PlayerSettings', 'YAML_INVALID')
        return parsed['PlayerSettings']
    old_values, new_values = parse(old), parse(new)
    # Top-level exact block comparison also detects byte-only formatting changes.
    def blocks(text):
        result = {}; key = None
        for line in text.splitlines(keepends=True)[4:]:
            match = re.match(r'^  ([A-Za-z0-9_][A-Za-z0-9_ ]*):', line)
            if match:
                key = match.group(1)
                if key in result: raise SettingsRejected(key, 'YAML_DUPLICATE')
                result[key] = []
            if key is None: raise SettingsRejected('PlayerSettings', 'YAML_INVALID')
            result[key].append(line)
        return result
    old_blocks, new_blocks = blocks(old), blocks(new)
    def inspect(value, field, depth=0):
        if depth > 12: raise SettingsRejected(field, 'VALUE_LIMIT')
        if value is None or type(value) is bool: return
        if type(value) in (int, float):
            if not math.isfinite(value) or len(str(value)) > 128: raise SettingsRejected(field, 'VALUE_LIMIT')
            return
        if isinstance(value, str):
            if len(value) > 2048 or any(not char.isprintable() for char in value): raise SettingsRejected(field, 'VALUE_LIMIT')
            if SENSITIVE.search(value) or re.search(r'gh[pousr]_|github_pat_|AKIA[0-9A-Z]{16}|-----BEGIN|Bearer\s+', value, re.I): raise SettingsRejected(field, 'SENSITIVE_VALUE')
            if re.search(r'(?:^|[\s=])(?:/[^/]|[A-Za-z]:[\\/]|~[\\/])', value): raise SettingsRejected(field, 'ABSOLUTE_PATH')
            if re.search(r'https?://[^/\s]*@|[?&](?:key|auth|access|signature)=', value, re.I): raise SettingsRejected(field, 'SENSITIVE_URL')
            return
        if isinstance(value, (list, dict)):
            if len(value) > 1024: raise SettingsRejected(field, 'VALUE_LIMIT')
            if isinstance(value, dict):
                for key, item in value.items():
                    if not isinstance(key, (str, int)) or len(str(key)) > 128: raise SettingsRejected(field, 'UNSAFE_FIELD_NAME')
                    if SENSITIVE.search(str(key)): raise SettingsRejected(field, 'SENSITIVE_FIELD')
                    inspect(item, field, depth + 1)
            else:
                for item in value: inspect(item, field, depth + 1)
            return
        raise SettingsRejected(field, 'VALUE_TYPE')
    for key in sorted(set(old_blocks) | set(new_blocks)):
        if old_blocks.get(key) == new_blocks.get(key): continue
        if SENSITIVE.search(key):
            before_kind = empty_setting_kind(key, old_blocks.get(key), old_values.get(key))
            after_kind = empty_setting_kind(key, new_blocks.get(key), new_values.get(key))
            # Existing single-line empty values only. No comments, hidden scalar,
            # added/removed credential field, nonempty value or nested structure.
            if before_kind in EMPTY_KINDS and after_kind in EMPTY_KINDS:
                if allowed_empty is not None: allowed_empty.append(dict(field=key, beforeValueKind=before_kind, afterValueKind=after_kind))
                continue
            raise SettingsRejected(key, 'SENSITIVE_FIELD', before_kind, after_kind)
        inspect(new_values.get(key), key)
    diff = ''.join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                   fromfile='before/' + SETTINGS, tofile='after/' + SETTINGS, n=0))
    require(len(diff.encode()) <= MAX_DIFF, 'SETTINGS_DIFF_SIZE')
    return diff


def apply_settings_diff(before, diff):
    original = before.decode('utf-8').splitlines(keepends=True)
    lines = diff.splitlines(keepends=True)
    require(lines[:2] == ['--- before/' + SETTINGS + '\n', '+++ after/' + SETTINGS + '\n'], 'DIFF_HEADER')
    result = []; cursor = 0; index = 2
    while index < len(lines):
        match = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@\n', lines[index])
        require(match is not None, 'DIFF_HUNK')
        start, count, new_start, new_count = (int(match.group(1)), int(match.group(2) or 1), int(match.group(3)), int(match.group(4) or 1))
        offset = start - 1 if count else start
        require(cursor <= offset <= len(original), 'DIFF_OFFSET')
        result.extend(original[cursor:offset]); index += 1
        removed = []; added = []
        while index < len(lines) and not lines[index].startswith('@@ '):
            line = lines[index]; require(line[0] in '-+', 'DIFF_LINE')
            (removed if line[0] == '-' else added).append(line[1:]); index += 1
        require(len(removed) == count and len(added) == new_count and original[offset:offset+count] == removed, 'DIFF_CONTENT')
        require(new_start == (len(result) + 1 if new_count else len(result)), 'DIFF_NEW_OFFSET')
        result.extend(added); cursor = offset + count
    result.extend(original[cursor:])
    raw = ''.join(result).encode(); require(len(raw) <= MAX_DIFF, 'DIFF_SIZE')
    return raw


def isolation_blank(env):
    return dict(schema=2, **owner_identity(env), projectPath=COPY_REL, status='FAIL', reason='COPY_CHECK_FAILED',
                copyVerified=False, sourceStateSha256='', protectedFiles=0, otherSourceUnchanged=False,
                changedPathCount=0, changedPathHashes=[], settingsStatus='NOT_CHECKED',
                settingsBefore=None, settingsAfter=None, settingsDiff='', allowedEmptySensitiveFields=[], settingsRejectedFields=[], failureClass='NONE')


def validate_isolation(value, check_diff=True):
    try:
        expected = isolation_blank(dict(GITHUB_SHA=value['sourceCommit'], GITHUB_RUN_ID=value['runId'], GITHUB_RUN_ATTEMPT=value['runAttempt']))
        require(type(value) is dict and set(value) == set(expected) and type(value['schema']) is int and value['schema'] == 2 and value['projectPath'] == COPY_REL, 'ISOLATION_SCHEMA')
        require(value['status'] in {'PASS', 'FAIL'} and value['reason'] in {'COPY_CHECK_FAILED', 'ISOLATED_COPY_VERIFIED'}, 'ISOLATION_SCHEMA')
        require(type(value['copyVerified']) is bool and type(value['otherSourceUnchanged']) is bool, 'ISOLATION_SCHEMA')
        require(type(value['protectedFiles']) is int and 0 <= value['protectedFiles'] <= 4096 and
                type(value['changedPathCount']) is int and 0 <= value['changedPathCount'] <= 12000, 'ISOLATION_SCHEMA')
        require(type(value['changedPathHashes']) is list and len(value['changedPathHashes']) == min(value['changedPathCount'], 64) and
                all(re.fullmatch('[a-f0-9]{64}', item) for item in value['changedPathHashes']), 'ISOLATION_SCHEMA')
        require(value['sourceStateSha256'] == '' or re.fullmatch('[a-f0-9]{64}', value['sourceStateSha256']), 'ISOLATION_SCHEMA')
        require(value['settingsStatus'] in {'NOT_CHECKED', 'UNCHANGED', 'COMPLETE_DIFF', 'REJECTED'} and value['failureClass'] in {'NONE', 'ValueError', 'StrictError', 'FileNotFoundError', 'PermissionError', 'OSError', 'OtherError'}, 'ISOLATION_SCHEMA')
        for key in ('settingsBefore', 'settingsAfter'):
            pin = value[key]
            require(pin is None or type(pin) is dict and set(pin) == {'sha256', 'bytes'} and re.fullmatch('[a-f0-9]{64}', pin['sha256']) and type(pin['bytes']) is int and 0 <= pin['bytes'] <= MAX_DIFF, 'ISOLATION_SCHEMA')
        allowed = value['allowedEmptySensitiveFields']
        require(type(allowed) is list and len(allowed) <= 32, 'ISOLATION_SCHEMA')
        for item in allowed:
            require(type(item) is dict and set(item) == {'field', 'beforeValueKind', 'afterValueKind'} and isinstance(item['field'], str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_ ]{0,95}', item['field']) and SENSITIVE.search(item['field']) and item['beforeValueKind'] in EMPTY_KINDS and item['afterValueKind'] in EMPTY_KINDS, 'ISOLATION_SCHEMA')
        require([item['field'] for item in allowed] == sorted({item['field'] for item in allowed}), 'ISOLATION_SCHEMA')
        require(not allowed or value['settingsStatus'] == 'COMPLETE_DIFF', 'ISOLATION_SCHEMA')
        require(type(value['settingsRejectedFields']) is list and len(value['settingsRejectedFields']) <= 1, 'ISOLATION_SCHEMA')
        for rejected in value['settingsRejectedFields']:
            require(type(rejected) is dict and set(rejected) == {'field', 'reason', 'beforeValueKind', 'afterValueKind'} and rejected['beforeValueKind'] in VALUE_KINDS and rejected['afterValueKind'] in VALUE_KINDS and isinstance(rejected['field'], str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_ ]{0,95}', rejected['field']) and rejected['reason'] in {'YAML_ALIAS_OR_TAG', 'YAML_INVALID', 'YAML_DUPLICATE', 'VALUE_LIMIT', 'SENSITIVE_VALUE', 'ABSOLUTE_PATH', 'SENSITIVE_URL', 'UNSAFE_FIELD_NAME', 'SENSITIVE_FIELD', 'VALUE_TYPE'}, 'ISOLATION_SCHEMA')
        require(not value['settingsRejectedFields'] or value['settingsStatus'] == 'REJECTED', 'ISOLATION_SCHEMA')
        require(type(value['settingsDiff']) is str and len(value['settingsDiff'].encode()) <= MAX_DIFF, 'ISOLATION_SCHEMA')
        if value['settingsStatus'] == 'COMPLETE_DIFF':
            require(value['settingsBefore'] and value['settingsAfter'] and value['settingsBefore'] != value['settingsAfter'] and value['settingsDiff'].startswith('--- before/' + SETTINGS + '\n+++ after/' + SETTINGS + '\n'), 'ISOLATION_SCHEMA')
            if check_diff:
                before = file_bytes(PROJECT / SETTINGS, MAX_DIFF)
                require(raw_pin(before) == value['settingsBefore'], 'ISOLATION_BEFORE')
                after = apply_settings_diff(before, value['settingsDiff'])
                expected_empty = []
                require(raw_pin(after) == value['settingsAfter'] and settings_diff(before, after, expected_empty) == value['settingsDiff'] and expected_empty == allowed, 'ISOLATION_DIFF')
        else: require(value['settingsDiff'] == '', 'ISOLATION_SCHEMA')
        if value['settingsStatus'] == 'UNCHANGED': require(value['settingsBefore'] is not None and value['settingsBefore'] == value['settingsAfter'], 'ISOLATION_SCHEMA')
        if value['status'] == 'PASS':
            require(value['reason'] == 'ISOLATED_COPY_VERIFIED' and value['copyVerified'] and value['otherSourceUnchanged'] and value['changedPathCount'] == 0 and value['protectedFiles'] > 0 and value['sourceStateSha256'] and value['settingsStatus'] in {'UNCHANGED', 'COMPLETE_DIFF'} and value['failureClass'] == 'NONE', 'ISOLATION_SCHEMA')
        return True
    except (ValueError, KeyError, TypeError, AttributeError, OSError, UnicodeError): return False


def inspect_copy(env):
    report = isolation_blank(env)
    try:
        owner = load_owner(env); rows, source_sha = copy_baseline(env)
        require(owner['sourceStateSha256'] == source_sha and owner['copyComplete'], 'COPY_INCOMPLETE')
        report.update(copyVerified=True, sourceStateSha256=source_sha, protectedFiles=len(rows))
        actual, directories = protected_inventory(COPY)
        changes = {name for name in set(rows) | set(actual) if name != SETTINGS and rows.get(name) != actual.get(name)}
        changes |= {name + '/' for name in set(owner['directories']) ^ directories}
        for path in COPY.iterdir():
            safe_path(path)
            if path.name in OPERATIONS: require(path.is_dir(), 'COPY_OPERATIONAL_TYPE')
            elif path.name not in {'Assets', 'Packages', 'ProjectSettings', COPY_MARKER}: changes.add(path.name)
        report.update(changedPathCount=len(changes), changedPathHashes=[hashlib.sha256(name.encode()).hexdigest() for name in sorted(changes)[:64]], otherSourceUnchanged=not changes)
        before = file_bytes(PROJECT / SETTINGS, MAX_DIFF)
        require(raw_pin(before) == rows[SETTINGS], 'FORMAL_SETTINGS_CHANGED')
        after = file_bytes(COPY / SETTINGS, MAX_DIFF)
        report.update(settingsBefore=raw_pin(before), settingsAfter=raw_pin(after), settingsStatus='REJECTED')
        allowed_empty = []
        diff = settings_diff(before, after, allowed_empty)
        report.update(settingsStatus='COMPLETE_DIFF' if diff else 'UNCHANGED', settingsDiff=diff, allowedEmptySensitiveFields=allowed_empty)
        require(not changes, 'COPY_OTHER_SOURCE_CHANGED')
        report.update(status='PASS', reason='ISOLATED_COPY_VERIFIED')
    except Exception as error:
        if isinstance(error, SettingsRejected): report['settingsRejectedFields'] = [dict(field=error.field, reason=error.reason, beforeValueKind=error.before_kind, afterValueKind=error.after_kind)]
        name = type(error).__name__
        report['failureClass'] = name if name in {'ValueError', 'StrictError', 'FileNotFoundError', 'PermissionError', 'OSError'} else 'OtherError'
    require(validate_isolation(report), 'ISOLATION_SCHEMA')
    write_new(ISOLATION_REPORT, report, MAX_ISOLATION_REPORT)
    output(env, 'report_written=true\nreport_valid=true\n' + ('copy_verified=true\n' if report['status'] == 'PASS' else ''))
    return 0 if report['status'] == 'PASS' else 2


def cleanup_copy(env):
    # Isolated (-I) CLI: stdlib only, no local imports or caller-supplied paths.
    owner = load_owner(env)
    require(shutil.rmtree.avoids_symlink_attacks, 'CLEANUP_PLATFORM')
    report = json.loads(file_bytes(ISOLATION_REPORT, MAX_ISOLATION_REPORT))
    require(validate_isolation(report, check_diff=False) and all(report[key] == value for key, value in owner_identity(env).items()), 'CLEANUP_EVIDENCE')
    parent_fd = os.open(TASK, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    copy_fd = None
    try:
        copy_fd = os.open(COPY.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        opened = os.fstat(copy_fd)
        require((opened.st_dev, opened.st_ino) == (owner['device'], owner['inode']), 'CLEANUP_INODE')
        # All removals are relative to that already-opened owned directory.
        # Links are unlinked themselves; their destinations are never traversed.
        for name in sorted(os.listdir(copy_fd)):
            if name == COPY_MARKER: continue
            info = os.stat(name, dir_fd=copy_fd, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode): shutil.rmtree(name, dir_fd=copy_fd)
            else: os.unlink(name, dir_fd=copy_fd)
        current = os.stat(COPY.name, dir_fd=parent_fd, follow_symlinks=False)
        require((current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino), 'CLEANUP_INODE')
        require(os.listdir(copy_fd) == [COPY_MARKER], 'CLEANUP_REMAINDER')
        os.unlink(COPY_MARKER, dir_fd=copy_fd)
        os.rmdir(COPY.name, dir_fd=parent_fd)
    finally:
        if copy_fd is not None: os.close(copy_fd)
        os.close(parent_fd)
    require(not COPY.exists() and not COPY.is_symlink(), 'CLEANUP_INCOMPLETE')
    return 0


def run_source(env):
    # Reuse the original independent source scan, including failure diagnostics.
    # Only this invocation's fixed report path differs; admission and baseline do not.
    import journey_tracer_source_diagnostic as diagnostic
    original = diagnostic.REPORT
    try:
        diagnostic.REPORT = SOURCE_REPORT
        return diagnostic.run(env)
    finally:
        diagnostic.REPORT = original


def blank_report(env):
    commit, run, attempt = (env.get(key, '') for key in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'))
    require(re.fullmatch('[a-f0-9]{40}', commit) and re.fullmatch('[1-9][0-9]*', run) and attempt == '1', 'IDENTITY')
    return dict(schema=2, status='FAIL', reason='CHECK_FAILED', failurePhase='NATIVE_OUTCOME', errorClass='ValueError', sourceCommit=commit,
                runId=run, runAttempt=attempt, expectedNativeCases=4, nativeCases=0,
                resultScope='DERIVED_EXACT_RESULTS', testPlatform='PlayMode', assembly='DesertRV.PlayModeTests', nativeResults=[],
                nativeXmlSha256='', sourceStateSha256='', testSourceSha256='', isolatedProjectPath=COPY_REL, isolationReportSha256='', originalSourceUnchanged=False,
                importUnionUnchanged=False, nativeOutcome='failure')


def exact_result_rows(rows):
    if type(rows) is not list or len(rows) != 4 or any(type(row) is not dict for row in rows) or [row.get('fullname') for row in rows] != sorted(EXPECTED): return False
    for row in rows:
        if set(row) not in ({'fullname', 'result'}, {'fullname', 'result', 'durationSeconds'}) or row['result'] != 'Passed': return False
        if 'durationSeconds' in row and not (type(row['durationSeconds']) in (int, float) and math.isfinite(row['durationSeconds']) and 0 <= row['durationSeconds'] <= 86400): return False
    return True


def validate_report(value):
    try:
        expected = blank_report(dict(GITHUB_SHA=value['sourceCommit'], GITHUB_RUN_ID=value['runId'], GITHUB_RUN_ATTEMPT=value['runAttempt']))
        if type(value) is not dict or set(value) != set(expected):
            return False
        if type(value['schema']) is not int or value['schema'] != 2 or type(value['expectedNativeCases']) is not int or value['expectedNativeCases'] != 4:
            return False
        if any(value[key] != expected[key] for key in ('resultScope', 'testPlatform', 'assembly', 'isolatedProjectPath')):
            return False
        if value['status'] == 'FAIL':
            if value['failurePhase'] not in {'NATIVE_OUTCOME', 'EXACT_XML', 'PIPELINE_IDENTITY', 'PIPELINE_PROTECTED', 'INITIAL_SOURCE', 'IMPORT_UNION', 'ISOLATED_COPY', 'EVIDENCE_DIGEST'} or value['errorClass'] not in {'ValueError', 'StrictError', 'FileNotFoundError', 'PermissionError', 'ParseError', 'OSError', 'OtherError'} or value['nativeOutcome'] not in {'success', 'failure', 'cancelled', 'skipped', 'unknown'}:
                return False
            expected.update(failurePhase=value['failurePhase'], errorClass=value['errorClass'], nativeOutcome=value['nativeOutcome'])
            if value['nativeCases'] == 4:
                if value['failurePhase'] in {'NATIVE_OUTCOME', 'EXACT_XML'} or not exact_result_rows(value['nativeResults']) or not re.fullmatch('[a-f0-9]{64}', value['nativeXmlSha256']): return False
                expected.update(nativeCases=4, nativeResults=value['nativeResults'], nativeXmlSha256=value['nativeXmlSha256'])
            return value == expected
        if not exact_result_rows(value['nativeResults']): return False
        return (value['status'] == 'PASS' and value['reason'] == 'EXACT_FOUR_AND_INITIAL_SOURCE_VERIFIED' and
                value['failurePhase'] == 'NONE' and value['errorClass'] == 'NONE' and
                type(value['nativeCases']) is int and value['nativeCases'] == 4 and value['nativeOutcome'] == 'success' and
                value['originalSourceUnchanged'] is True and value['importUnionUnchanged'] is True and
                all(type(value[key]) is str and re.fullmatch('[a-f0-9]{64}', value[key]) for key in
                    ('nativeXmlSha256', 'sourceStateSha256', 'testSourceSha256', 'isolationReportSha256')))
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return False


def run(env):
    report = blank_report(env)
    context = {'phase': 'NATIVE_OUTCOME'}
    outcome = env.get('NATIVE_OUTCOME')
    report['nativeOutcome'] = outcome if outcome in {'success', 'failure', 'cancelled', 'skipped'} else 'unknown'
    try:
        require(env.get('NATIVE_OUTCOME') == 'success', 'NATIVE_FAILED')
        context['phase'] = 'EXACT_XML'
        xml_sha, results = inspect_xml(ARTIFACTS)
        report.update(nativeCases=4, nativeResults=results, nativeXmlSha256=xml_sha)
        verify_unchanged(context)
        context['phase'] = 'ISOLATED_COPY'
        isolation = json.loads(file_bytes(ISOLATION_REPORT, MAX_ISOLATION_REPORT))
        require(validate_isolation(isolation) and isolation['status'] == 'PASS' and
                all(isolation[key] == value for key, value in owner_identity(env).items()), 'ISOLATED_COPY_REJECTED')
        context['phase'] = 'EVIDENCE_DIGEST'
        report.update(status='PASS', reason='EXACT_FOUR_AND_INITIAL_SOURCE_VERIFIED', failurePhase='NONE', errorClass='NONE', nativeCases=4,
                      nativeResults=results,
                      nativeXmlSha256=xml_sha, isolationReportSha256=digest(ISOLATION_REPORT), sourceStateSha256=digest(TASK / 'SOURCE-STATE.json'),
                      testSourceSha256=digest(ROOT / TEST_SOURCE), originalSourceUnchanged=True,
                      importUnionUnchanged=True, nativeOutcome='success')
    except Exception as error:
        # Fixed phase/class only. Raw native logs, error text and paths stay private.
        error_class = type(error).__name__
        report.update(failurePhase=context['phase'], errorClass=error_class if error_class in
                      {'ValueError', 'StrictError', 'FileNotFoundError', 'PermissionError', 'ParseError', 'OSError'} else 'OtherError')
    require(validate_report(report), 'REPORT_SCHEMA')
    raw = (json.dumps(report, indent=2) + '\n').encode()
    require(len(raw) <= 4096 and not REPORT.exists() and not REPORT.is_symlink(), 'REPORT_PATH')
    with REPORT.open('xb') as stream:
        stream.write(raw)
    with open(env['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write('report_written=true\nreport_valid=true\n')
        if report['status'] == 'PASS':
            output.write('native_verified=true\n')
    return 0 if report['status'] == 'PASS' else 2


def preserve(env):
    import journey_tracer_source_diagnostic as diagnostic
    identity = blank_report(env)
    _, expected, _ = diagnostic.pinned_baseline(env)
    allowed = set(expected) | diagnostic.expected_directories(expected)
    require(not PREPARATION_REPORTS.exists() and not any(p.is_symlink() for p in (PREPARATION_REPORTS, *PREPARATION_REPORTS.parents)), 'REPORT_PATH')
    require(PREPARATION_REPORTS.parent.is_dir(), 'PREPARATION_MISSING')
    sealed = []
    for path, name, limit in ((REPORT, 'native-report.json', 4096), (SOURCE_REPORT, 'source-report.json', diagnostic.MAX_REPORT), (ISOLATION_REPORT, 'isolation-report.json', MAX_ISOLATION_REPORT)):
        require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)) and 0 < path.stat().st_size <= limit, 'REPORT_PATH')
        raw = path.read_bytes(); value = diagnostic.json_bytes(raw)
        require(validate_report(value) if path == REPORT else validate_isolation(value) if path == ISOLATION_REPORT else bool(diagnostic.validate_report(value, allowed)), 'REPORT_SCHEMA')
        require(all(value[key] == identity[key] for key in ('sourceCommit', 'runId', 'runAttempt')), 'IDENTITY')
        sealed.append((name, raw))
    PREPARATION_REPORTS.mkdir()
    for name, raw in sealed:
        with (PREPARATION_REPORTS / name).open('xb') as stream:
            stream.write(raw)
        require((PREPARATION_REPORTS / name).read_bytes() == raw, 'REPORT_COPY')
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        require(argv in (['native'], ['source'], ['preserve'], ['copy'], ['isolation'], ['cleanup']), 'ARGUMENTS')
        return {'source': run_source, 'native': run, 'preserve': preserve, 'copy': create_copy, 'isolation': inspect_copy, 'cleanup': cleanup_copy}[argv[0]](os.environ)
    except Exception:
        print('KEYBOARD_LOOK_REPORT_REJECTED')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
