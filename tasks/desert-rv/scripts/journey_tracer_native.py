"""Exact ten native tracer cases and initial source/import immutability checkpoint."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / 'tasks/desert-rv'
PROJECT = TASK / 'unity'
REPORT = TASK / 'journey-tracer-native-report.json'
ARTIFACTS = TASK / 'artifacts/journey-tracer-material'
TEST_SOURCE = 'tasks/desert-rv/unity/Assets/DesertRV/Tests/EditMode/JourneyTracerMaterialTests.cs'
PREFIX = 'DesertRV.Tests.JourneyTracerMaterialTests.'
EXPECTED = (
    PREFIX + 'ImportedMaterialReferencesExactPackageShaderAndOrangeColor',
    PREFIX + 'ImportedMaterialReimportDoesNotRewriteSourceBytes',
    *[PREFIX + 'SerializedSceneRetainsMaterialAndShaderDependency("' + name + '")'
      for name in ('JourneyActions', 'FirstStationJourney')],
    *[PREFIX + 'AwakeAndFirePreserveCombatWithOrWithoutTracer("' + name + '","' + kind + '")'
      for kind in ('valid', 'missing', 'wrong-shader') for name in ('JourneyActions', 'FirstStationJourney')],
)


def require(ok, code):
    if not ok:
        raise ValueError(code)


def digest(path):
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), 'UNSAFE_INPUT')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_xml(folder):
    require(folder.is_dir() and not folder.is_symlink(), 'XML_MISSING')
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
            root.get('total') == '10' and root.get('passed') == '10' and
            all(root.get(key) == '0' for key in ('failed', 'skipped', 'inconclusive')) and
            len(names) == 10 and len(set(names)) == 10 and set(names) == set(EXPECTED) and
            all(case.get('result') == 'Passed' for case in cases), 'EXACT_TEN_REQUIRED')
    return sha


def verify_unchanged(context=None):
    context = {} if context is None else context
    context['phase'] = 'PIPELINE_IDENTITY'
    sys.path[:0] = [str(TASK / 'art/journey-preparation'), str(TASK / 'scripts/rendered')]
    import pipeline
    import prepared_source
    pipeline.guard()
    context['phase'] = 'PIPELINE_PROTECTED'
    state = pipeline.state()
    require(state.get('completed') == [] and state.get('assetFiles') == {} and 'phase' not in state, 'BEFORE_STRICT_ONLY')
    pipeline.check_state(state)
    context['phase'] = 'INITIAL_SOURCE'
    source = prepared_source.verify_original(state['initialIdentity'])
    context['phase'] = 'IMPORT_UNION'
    prepared_source.verify_asset_union(source, state['initialSourceDirectories'], {})
    require(pipeline.import_inventory() == {}, 'IMPORTS_CHANGED')
    for path in (PROJECT / 'CandidateImportInput', PROJECT / 'CandidatePackageSnapshot',
                 PROJECT / 'JourneyEvidence/CandidateArt', PROJECT / 'Assets/DesertRV/Scenes/Journey'):
        require(not path.exists() and not path.is_symlink(), 'PREEXISTING_IMPORT')


def blank_report(env):
    commit, run, attempt = (env.get(key, '') for key in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'))
    require(re.fullmatch('[a-f0-9]{40}', commit) and re.fullmatch('[1-9][0-9]*', run) and attempt == '1', 'IDENTITY')
    return dict(schema=1, status='FAIL', reason='CHECK_FAILED', failurePhase='NATIVE_OUTCOME', errorClass='ValueError', sourceCommit=commit,
                runId=run, runAttempt=attempt, expectedNativeCases=10, nativeCases=0,
                nativeXmlSha256='', sourceStateSha256='', testSourceSha256='', originalSourceUnchanged=False,
                importUnionUnchanged=False, nativeOutcome='failure')


def validate_report(value):
    try:
        expected = blank_report(dict(GITHUB_SHA=value['sourceCommit'], GITHUB_RUN_ID=value['runId'], GITHUB_RUN_ATTEMPT=value['runAttempt']))
        if type(value) is not dict or set(value) != set(expected):
            return False
        if type(value['schema']) is not int or value['schema'] != 1 or type(value['expectedNativeCases']) is not int or value['expectedNativeCases'] != 10:
            return False
        if value['status'] == 'FAIL':
            if value['failurePhase'] not in {'NATIVE_OUTCOME', 'EXACT_XML', 'PIPELINE_IDENTITY', 'PIPELINE_PROTECTED', 'INITIAL_SOURCE', 'IMPORT_UNION', 'EVIDENCE_DIGEST'} or value['errorClass'] not in {'ValueError', 'StrictError', 'FileNotFoundError', 'PermissionError', 'ParseError', 'OSError', 'OtherError'} or value['nativeOutcome'] not in {'success', 'failure', 'cancelled', 'skipped', 'unknown'}:
                return False
            expected.update(failurePhase=value['failurePhase'], errorClass=value['errorClass'], nativeOutcome=value['nativeOutcome'])
            return value == expected
        return (value['status'] == 'PASS' and value['reason'] == 'EXACT_TEN_AND_INITIAL_SOURCE_VERIFIED' and
                value['failurePhase'] == 'NONE' and value['errorClass'] == 'NONE' and
                type(value['nativeCases']) is int and value['nativeCases'] == 10 and value['nativeOutcome'] == 'success' and
                value['originalSourceUnchanged'] is True and value['importUnionUnchanged'] is True and
                all(type(value[key]) is str and re.fullmatch('[a-f0-9]{64}', value[key]) for key in
                    ('nativeXmlSha256', 'sourceStateSha256', 'testSourceSha256')))
    except (KeyError, TypeError, ValueError):
        return False


def run(env):
    report = blank_report(env)
    context = {'phase': 'NATIVE_OUTCOME'}
    outcome = env.get('NATIVE_OUTCOME')
    report['nativeOutcome'] = outcome if outcome in {'success', 'failure', 'cancelled', 'skipped'} else 'unknown'
    try:
        require(env.get('NATIVE_OUTCOME') == 'success', 'NATIVE_FAILED')
        context['phase'] = 'EXACT_XML'
        xml_sha = inspect_xml(ARTIFACTS)
        verify_unchanged(context)
        context['phase'] = 'EVIDENCE_DIGEST'
        report.update(status='PASS', reason='EXACT_TEN_AND_INITIAL_SOURCE_VERIFIED', failurePhase='NONE', errorClass='NONE', nativeCases=10,
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


if __name__ == '__main__':
    try:
        result = run(os.environ)
    except Exception:
        print('TRACER_NATIVE_REPORT_REJECTED')
        result = 2
    raise SystemExit(result)
