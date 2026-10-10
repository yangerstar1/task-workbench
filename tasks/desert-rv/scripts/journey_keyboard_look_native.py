"""Exact four keyboard-look PlayMode cases and original source/union checkpoint."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
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


from journey_tracer_native import verify_unchanged


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
    return dict(schema=1, status='FAIL', reason='CHECK_FAILED', failurePhase='NATIVE_OUTCOME', errorClass='ValueError', sourceCommit=commit,
                runId=run, runAttempt=attempt, expectedNativeCases=4, nativeCases=0,
                resultScope='DERIVED_EXACT_RESULTS', testPlatform='PlayMode', assembly='DesertRV.PlayModeTests', nativeResults=[],
                nativeXmlSha256='', sourceStateSha256='', testSourceSha256='', originalSourceUnchanged=False,
                importUnionUnchanged=False, nativeOutcome='failure')


def validate_report(value):
    try:
        expected = blank_report(dict(GITHUB_SHA=value['sourceCommit'], GITHUB_RUN_ID=value['runId'], GITHUB_RUN_ATTEMPT=value['runAttempt']))
        if type(value) is not dict or set(value) != set(expected):
            return False
        if type(value['schema']) is not int or value['schema'] != 1 or type(value['expectedNativeCases']) is not int or value['expectedNativeCases'] != 4:
            return False
        if any(value[key] != expected[key] for key in ('resultScope', 'testPlatform', 'assembly')):
            return False
        if value['status'] == 'FAIL':
            if value['failurePhase'] not in {'NATIVE_OUTCOME', 'EXACT_XML', 'PIPELINE_IDENTITY', 'PIPELINE_PROTECTED', 'INITIAL_SOURCE', 'IMPORT_UNION', 'EVIDENCE_DIGEST'} or value['errorClass'] not in {'ValueError', 'StrictError', 'FileNotFoundError', 'PermissionError', 'ParseError', 'OSError', 'OtherError'} or value['nativeOutcome'] not in {'success', 'failure', 'cancelled', 'skipped', 'unknown'}:
                return False
            expected.update(failurePhase=value['failurePhase'], errorClass=value['errorClass'], nativeOutcome=value['nativeOutcome'])
            return value == expected
        rows = value['nativeResults']
        if type(rows) is not list or len(rows) != 4 or [row.get('fullname') for row in rows] != sorted(EXPECTED):
            return False
        for row in rows:
            if type(row) is not dict or set(row) not in ({'fullname', 'result'}, {'fullname', 'result', 'durationSeconds'}) or row['result'] != 'Passed':
                return False
            if 'durationSeconds' in row and not (type(row['durationSeconds']) in (int, float) and math.isfinite(row['durationSeconds']) and 0 <= row['durationSeconds'] <= 86400):
                return False
        return (value['status'] == 'PASS' and value['reason'] == 'EXACT_FOUR_AND_INITIAL_SOURCE_VERIFIED' and
                value['failurePhase'] == 'NONE' and value['errorClass'] == 'NONE' and
                type(value['nativeCases']) is int and value['nativeCases'] == 4 and value['nativeOutcome'] == 'success' and
                value['originalSourceUnchanged'] is True and value['importUnionUnchanged'] is True and
                all(type(value[key]) is str and re.fullmatch('[a-f0-9]{64}', value[key]) for key in
                    ('nativeXmlSha256', 'sourceStateSha256', 'testSourceSha256')))
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
        verify_unchanged(context)
        context['phase'] = 'EVIDENCE_DIGEST'
        report.update(status='PASS', reason='EXACT_FOUR_AND_INITIAL_SOURCE_VERIFIED', failurePhase='NONE', errorClass='NONE', nativeCases=4,
                      nativeResults=results,
                      nativeXmlSha256=xml_sha, sourceStateSha256=digest(TASK / 'SOURCE-STATE.json'),
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
    for path, name, limit in ((REPORT, 'native-report.json', 4096), (SOURCE_REPORT, 'source-report.json', diagnostic.MAX_REPORT)):
        require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)) and 0 < path.stat().st_size <= limit, 'REPORT_PATH')
        raw = path.read_bytes(); value = diagnostic.json_bytes(raw)
        require(validate_report(value) if path == REPORT else bool(diagnostic.validate_report(value, allowed)), 'REPORT_SCHEMA')
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
        require(argv in (['native'], ['source'], ['preserve']), 'ARGUMENTS')
        return {'source': run_source, 'native': run, 'preserve': preserve}[argv[0]](os.environ)
    except Exception:
        print('KEYBOARD_LOOK_REPORT_REJECTED')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
