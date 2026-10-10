"""Fresh exact-seven feedback gate in the producer's owned isolated project.

This is same-commit native primitive evidence, not rendered-player acceptance.
"""
import hashlib
import math
import os
from pathlib import Path
import re
import sys

import journey_keyboard_look_native as isolated
import journey_tracer_source_diagnostic as source
import journey_combat_feedback_probe as feedback

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / 'tasks/desert-rv'
REPORT = TASK / 'journey-combat-feedback-full-native-report.json'
ARTIFACTS = TASK / 'artifacts/journey-combat-feedback-full'
PREPARATION_REPORTS = TASK / 'journey-preparation-export/combat-feedback'
TEST_SOURCE = feedback.TEST_SOURCE
EXPECTED = feedback.EXPECTED
MAX_REPORT = 8192
OUTCOMES = {'success', 'failure', 'cancelled', 'skipped', 'unknown'}
PHASES = {'NATIVE_OUTCOME', 'EXACT_XML', 'PIPELINE_IDENTITY', 'PIPELINE_PROTECTED',
          'INITIAL_SOURCE', 'IMPORT_UNION', 'ISOLATED_COPY', 'EVIDENCE_DIGEST'}
ERRORS = {'ValueError', 'StrictError', 'FileNotFoundError', 'PermissionError', 'ParseError', 'OSError', 'OtherError'}
require = isolated.require


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inspect_xml(folder):
    xml_sha, rows = feedback.inspect_xml(folder)
    require(all(row['result'] == 'Passed' for row in rows), 'EXACT_SEVEN_FEEDBACK_REQUIRED')
    return xml_sha, rows


def blank_report(env):
    return dict(schema=1, **isolated.owner_identity(env), status='FAIL', reason='CHECK_FAILED',
                failurePhase='NATIVE_OUTCOME', errorClass='ValueError', nativeOutcome='failure',
                expectedNativeCases=7, nativeCases=0, nativeResults=[], nativeXmlSha256='',
                resultScope='FEEDBACK_PRIMITIVES_NOT_RENDERED_PLAYER_ACCEPTANCE',
                testPlatform='EditMode', assembly='DesertRV.EditModeTests',
                isolatedProjectPath=isolated.COPY_REL, isolationReportSha256='',
                sourceStateSha256='', testSourceSha256='',
                originalSourceUnchanged=False, importUnionUnchanged=False)


def exact_results(rows):
    if type(rows) is not list or len(rows) != 7 or any(type(row) is not dict for row in rows):
        return False
    return ([row.get('fullname') for row in rows] == list(EXPECTED) and
            all(set(row) in ({'fullname', 'result'}, {'fullname', 'result', 'durationSeconds'}) and
                row['result'] == 'Passed' and
                ('durationSeconds' not in row or type(row['durationSeconds']) in (int, float) and
                 math.isfinite(row['durationSeconds']) and 0 <= row['durationSeconds'] <= 86400)
                for row in rows))


def validate_report(value):
    try:
        expected = blank_report(dict(GITHUB_SHA=value['sourceCommit'], GITHUB_RUN_ID=value['runId'], GITHUB_RUN_ATTEMPT=value['runAttempt']))
        require(type(value) is dict and set(value) == set(expected), 'REPORT_SCHEMA')
        require(type(value['schema']) is int and value['schema'] == 1 and
                type(value['expectedNativeCases']) is int and value['expectedNativeCases'] == 7 and
                type(value['nativeCases']) is int and type(value['originalSourceUnchanged']) is bool and
                type(value['importUnionUnchanged']) is bool, 'REPORT_SCHEMA')
        for key in ('resultScope', 'testPlatform', 'assembly', 'isolatedProjectPath'):
            require(value[key] == expected[key], 'REPORT_SCOPE')
        if value['status'] == 'FAIL':
            require(value['failurePhase'] in PHASES and value['errorClass'] in ERRORS and value['nativeOutcome'] in OUTCOMES, 'REPORT_FAILURE')
            expected.update(failurePhase=value['failurePhase'], errorClass=value['errorClass'], nativeOutcome=value['nativeOutcome'])
            if value['nativeCases'] == 7:
                require(value['failurePhase'] not in {'NATIVE_OUTCOME', 'EXACT_XML'} and
                        exact_results(value['nativeResults']) and re.fullmatch('[a-f0-9]{64}', value['nativeXmlSha256']), 'REPORT_RESULTS')
                expected.update(nativeCases=7, nativeResults=value['nativeResults'], nativeXmlSha256=value['nativeXmlSha256'])
            return value == expected
        require(exact_results(value['nativeResults']), 'REPORT_RESULTS')
        require(all(type(value[key]) is str and re.fullmatch('[a-f0-9]{64}', value[key]) for key in
                    ('nativeXmlSha256', 'sourceStateSha256', 'testSourceSha256', 'isolationReportSha256')), 'REPORT_DIGEST')
        expected.update(status='PASS', reason='EXACT_SEVEN_FEEDBACK_AND_INITIAL_SOURCE_VERIFIED',
                        failurePhase='NONE', errorClass='NONE', nativeOutcome='success', nativeCases=7,
                        originalSourceUnchanged=True, importUnionUnchanged=True)
        expected.update({key: value[key] for key in ('nativeResults', 'nativeXmlSha256', 'sourceStateSha256',
                        'testSourceSha256', 'isolationReportSha256')})
        return value == expected
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return False


def run(env):
    report = blank_report(env)
    outcome = env.get('NATIVE_OUTCOME')
    report['nativeOutcome'] = outcome if outcome in OUTCOMES else 'unknown'
    context = {'phase': 'NATIVE_OUTCOME'}
    try:
        require(outcome == 'success', 'NATIVE_FAILED')
        context['phase'] = 'EXACT_XML'
        xml_sha, rows = inspect_xml(ARTIFACTS)
        report.update(nativeCases=7, nativeResults=rows, nativeXmlSha256=xml_sha)
        isolated.verify_unchanged(context)
        context['phase'] = 'ISOLATED_COPY'
        raw = isolated.file_bytes(isolated.ISOLATION_REPORT, isolated.MAX_ISOLATION_REPORT)
        isolation = source.json_bytes(raw)
        source_sha = sha(isolated.file_bytes(TASK / 'SOURCE-STATE.json', 4 * 1024**2))
        require(isolated.validate_isolation(isolation) and isolation['status'] == 'PASS' and
                isolation['sourceStateSha256'] == source_sha and
                all(isolation[key] == value for key, value in isolated.owner_identity(env).items()), 'ISOLATED_COPY_REJECTED')
        context['phase'] = 'EVIDENCE_DIGEST'
        pins = dict(testSourceSha256=sha(isolated.file_bytes(ROOT / TEST_SOURCE)))
        report.update(status='PASS', reason='EXACT_SEVEN_FEEDBACK_AND_INITIAL_SOURCE_VERIFIED',
                      failurePhase='NONE', errorClass='NONE', isolationReportSha256=sha(raw),
                      sourceStateSha256=source_sha, **pins, originalSourceUnchanged=True, importUnionUnchanged=True)
    except Exception as error:
        error_class = type(error).__name__
        report.update(failurePhase=context['phase'], errorClass=error_class if error_class in ERRORS else 'OtherError')
    require(validate_report(report), 'REPORT_SCHEMA')
    isolated.write_new(REPORT, report, MAX_REPORT)
    isolated.output(env, 'report_written=true\nreport_valid=true\n' +
                    ('native_verified=true\n' if report['status'] == 'PASS' else ''))
    return 0 if report['status'] == 'PASS' else 2


def preserve(env):
    raw = isolated.file_bytes(REPORT, MAX_REPORT)
    value = source.json_bytes(raw)
    require(validate_report(value) and all(value[key] == item for key, item in isolated.owner_identity(env).items()), 'REPORT_IDENTITY')
    isolated.safe_path(PREPARATION_REPORTS)
    require(not PREPARATION_REPORTS.exists() and PREPARATION_REPORTS.parent.is_dir(), 'REPORT_PATH')
    PREPARATION_REPORTS.mkdir()
    target = PREPARATION_REPORTS / 'native-report.json'
    with target.open('xb') as stream:
        stream.write(raw)
    require(isolated.file_bytes(target, MAX_REPORT) == raw, 'REPORT_COPY')
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        require(argv in (['native'], ['preserve']), 'ARGUMENTS')
        return {'native': run, 'preserve': preserve}[argv[0]](os.environ)
    except Exception:
        print('COMBAT_FEEDBACK_FULL_REPORT_REJECTED')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
