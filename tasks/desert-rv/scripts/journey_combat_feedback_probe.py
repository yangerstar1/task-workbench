"""Single-use source-only exact-seven EditMode gate; never a player/producer proof."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import types
import xml.etree.ElementTree as ET

# Required for the bounded -I cleanup entry point; this directory is checked
# against HEAD by the workflow before privileged cleanup.
if sys.argv[1:] == ['cleanup']:
    # Execute only the HEAD-checked helper source, never runner-written bytecode.
    helper = Path(__file__).resolve().with_name('journey_keyboard_look_native.py')
    isolated = types.ModuleType('combat_feedback_cleanup_copy')
    isolated.__file__ = str(helper)
    exec(compile(helper.read_bytes(), str(helper), 'exec'), isolated.__dict__)
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import journey_keyboard_look_native as isolated
    import journey_tracer_dispatch as admission
    import verify_evidence as source

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / 'tasks/desert-rv'
BASE = 'ec4d6329d9ef372d3d4518b9fcc113c1c5e0c877'
BRANCH = 'wip/combat-feedback-20261010'
REF = 'refs/heads/' + BRANCH
WORKFLOW = '.github/workflows/desert-rv-combat-feedback.yml'
REQUEST = '.github/dispatch/desert-rv-combat-feedback-r2-20261010.json'
REQUEST_ID = 'desert-rv-combat-feedback-r2-20261010-once'
SOURCE = 'tasks/desert-rv/SOURCE-STATE.json'
SCRIPT = 'tasks/desert-rv/scripts/journey_combat_feedback_probe.py'
TEST_SOURCE = 'tasks/desert-rv/unity/Assets/DesertRV/Tests/EditMode/JourneyCombatFeedbackTests.cs'
CHANGED = {WORKFLOW, REQUEST, SOURCE, SCRIPT, TEST_SOURCE,
           'tasks/desert-rv/scripts/test_journey_combat_feedback_probe.py'}
PREFIX = 'DesertRV.Tests.JourneyCombatFeedbackTests.'
EXPECTED = tuple(sorted(PREFIX + name for name in (
    'ContactUsesActualDamageAndCameraRelativeBearing',
    'ContactCueRejectsNoLossExpiresAndClearsOnRegionPlacement',
    'RearWarningRequiresLiveBehindInRangeThreatAndClearsWithState',
    'RearWarningDoesNotSeeThroughWorldCover',
    'RepairNoticeReportsCappedVehicleGainAndLeavesPlayerHealthAlone',
    'DriverPromptAndFailureShareExistingCableAndLineOfSightGates',
    'DisconnectExplainsChargePauseWhileExistingWaveAndThreatRemain',
)))
ARTIFACTS = TASK / 'artifacts/journey-combat-feedback'
EXPORT = TASK / 'journey-combat-feedback-export'
COPY_REL = 'tasks/desert-rv/journey-combat-feedback-project'
OUTCOMES = {'success', 'failure', 'cancelled', 'skipped', 'unknown'}


def require(ok, code='REJECTED'):
    if not ok:
        raise ValueError('COMBAT_FEEDBACK_' + code)


def pin(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return admission.git(ROOT, *args)


def read(path, limit=4 * 1024**2):
    return isolated.file_bytes(path, limit)


def identity(env):
    return isolated.owner_identity(env)


def parse_request(raw):
    require(0 < len(raw) <= 2048, 'REQUEST_SIZE')
    value = admission.parse(raw)
    require(type(value) is dict and set(value) == {'schema', 'requestId', 'baseCommit', 'sourceStateSha256'}, 'REQUEST_KEYS')
    require(type(value['schema']) is int and value['schema'] == 1 and value['requestId'] == REQUEST_ID and value['baseCommit'] == BASE, 'REQUEST_IDENTITY')
    require(type(value['sourceStateSha256']) is str and re.fullmatch('[a-f0-9]{64}', value['sourceStateSha256']), 'REQUEST_HASH')
    return value


def validate_identity(env, event, head, parents, request_raw, tracked_raw, present, changed, source_sha):
    require(env.get('GITHUB_ACTIONS') == 'true' and env.get('GITHUB_REPOSITORY') == admission.REPOSITORY and env.get('GITHUB_REPOSITORY_VISIBILITY') == 'public', 'REPOSITORY')
    require(env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and env.get('RUNNER_OS') == 'Linux', 'RUNNER')
    require(env.get('GITHUB_ACTOR') == env.get('GITHUB_TRIGGERING_ACTOR') == admission.OWNER, 'ACTOR')
    require(env.get('GITHUB_EVENT_NAME') == 'push' and env.get('GITHUB_REF') == REF, 'REF')
    require(env.get('GITHUB_WORKFLOW_REF') == admission.REPOSITORY + '/' + WORKFLOW + '@' + REF, 'WORKFLOW')
    require(env.get('GITHUB_SHA') == head and re.fullmatch('[a-f0-9]{40}', head or '') and head != BASE, 'HEAD')
    require(re.fullmatch('[1-9][0-9]*', env.get('GITHUB_RUN_ID', '')) and env.get('GITHUB_RUN_ATTEMPT') == '1', 'REPLAY')
    require(type(event) is dict and event.get('before') == BASE and event.get('after') == head and event.get('ref') == REF, 'PUSH')
    require(all(event.get(key) is False for key in ('created', 'deleted', 'forced')), 'PUSH_KIND')
    repo = event.get('repository', {})
    require(type(repo) is dict and repo.get('full_name') == admission.REPOSITORY and repo.get('private') is False and repo.get('fork') is False and repo.get('default_branch') == 'main' and repo.get('owner', {}).get('login') == admission.OWNER, 'PUSH_REPOSITORY')
    require(event.get('sender', {}).get('login') == admission.OWNER and event.get('head_commit', {}).get('id') == head, 'SENDER')
    require(parents == [BASE] and present is False and set(changed) == CHANGED and len(changed) == len(CHANGED) and request_raw == tracked_raw, 'PARENT_OR_CHANGES')
    value = parse_request(request_raw)
    require(value['sourceStateSha256'] == source_sha, 'SOURCE_STATE')
    return value


def verify_fixture_change(before, after):
    # The first native run proved six passes. Its seventh fixture tried to leave
    # a region while on foot. Permit only this exact missing setup transition.
    require(pin(before) == 'ae5bb28fe470bf88f4736d7b0917e8da607ef0e64832017ce3492bb43a2bf1d3', 'FIXTURE_PARENT')
    advance = b'            Production.Advance(state, "RamPart", "test-ram");\n'
    driving = b'            Production.Call(state, "SetControl", Production.Enum("ControlMode", "Driving"));\n'
    require(before.count(advance) == 1 and after == before.replace(advance, driving + advance, 1), 'FIXTURE_CHANGE')


def verify_dispatch(env):
    head = git('rev-parse', 'HEAD').decode().strip()
    parents = [line[7:] for line in git('cat-file', '-p', 'HEAD').decode().split('\n\n', 1)[0].splitlines() if line.startswith('parent ')]
    present = subprocess.run(['git', 'cat-file', '-e', BASE + ':' + REQUEST], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    changed = git('diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').decode().splitlines()
    state = admission.tracked_input(ROOT, SOURCE, 4 * 1024**2)
    for name in (WORKFLOW, SCRIPT, 'tasks/desert-rv/scripts/prepare_runner.sh'):
        admission.tracked_input(ROOT, name, 1024**2)
    event = admission.parse(read(Path(env.get('GITHUB_EVENT_PATH', '')), 4 * 1024**2))
    value = validate_identity(env, event, head, parents, read(ROOT / REQUEST, 2048), git('show', 'HEAD:' + REQUEST), present, changed, pin(state))
    # Production/project/asset bytes stay equal to the native-tested parent.
    # The only Unity change is the exact one-line test-fixture correction above.
    require(git('diff', '--name-only', BASE, 'HEAD', '--', 'tasks/desert-rv/unity').decode().splitlines() == [TEST_SOURCE], 'GAME_SOURCE_CHANGED')
    verify_fixture_change(git('show', BASE + ':' + TEST_SOURCE), admission.tracked_input(ROOT, TEST_SOURCE, 1024**2))
    return value


def verify_unchanged(context=None):
    verify_dispatch(os.environ)
    git('diff', '--quiet', '--exit-code')
    git('diff', '--cached', '--quiet', '--exit-code')
    source.verify_source_state()


def copy_baseline(env):
    verify_dispatch(env)
    state = source.verify_source_state()
    rows = {row['path'][len(isolated.SOURCE_PREFIX):]: {'sha256': row['sha256'], 'bytes': row['size']}
            for row in state['files'] + state['restoredFiles'] if row['path'].startswith(isolated.SOURCE_PREFIX)}
    require(0 < len(rows) <= 4096 and isolated.SETTINGS in rows, 'BASELINE')
    return rows, pin(read(ROOT / SOURCE))


def configure_copy():
    # Reuse the established byte-identical source copier, settings validator,
    # owner identity, inode fencing and descriptor-relative cleanup unchanged.
    isolated.COPY_REL = COPY_REL
    isolated.COPY = ROOT / COPY_REL
    isolated.OWNER = TASK / 'journey-combat-feedback-copy-owner.json'
    isolated.ISOLATION_REPORT = TASK / 'journey-combat-feedback-isolation-report.json'
    isolated.COPY_MARKER = '.journey-combat-feedback-owner.json'
    isolated.copy_baseline = copy_baseline
    isolated.verify_unchanged = verify_unchanged


def guard(env):
    verify_unchanged()
    version = read(isolated.PROJECT / 'ProjectSettings/ProjectVersion.txt', 4096).decode()
    require('m_EditorVersion: 6000.3.19f1' in version.splitlines(), 'EDITOR_VERSION')
    names = source.expected_cases()
    require(len(names) == 210 and set(EXPECTED) <= names, 'INVENTORY')
    require(set(re.findall(r'\[Test\] public void (\w+)\(', read(ROOT / TEST_SOURCE).decode())) == {name[len(PREFIX):] for name in EXPECTED}, 'TEST_SOURCE')
    for path in (TASK / 'artifacts', TASK / 'build', TASK / 'evidence', EXPORT, isolated.COPY, isolated.OWNER, isolated.ISOLATION_REPORT):
        isolated.safe_path(path)
        require(not path.exists(), 'DIRTY_OUTPUT')


def inspect_xml(folder):
    isolated.safe_path(folder)
    require(folder.is_dir(), 'XML_MISSING')
    paths = list(folder.rglob('*.xml'))
    require(len(paths) == 1, 'XML_COUNT')
    raw = read(paths[0], 1024**2)
    require(b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper(), 'XML_DECLARATION')
    root = ET.fromstring(raw)
    cases = list(root.iter('test-case'))
    require(root.tag == 'test-run' and root.get('total') == '7' and len(cases) == 7 and sorted(case.get('fullname', '') for case in cases) == list(EXPECTED), 'EXACT_SEVEN')
    rows = []
    for case in sorted(cases, key=lambda item: item.get('fullname')):
        require(case.get('result') in {'Passed', 'Failed'}, 'XML_RESULT')
        row = {'fullname': case.get('fullname'), 'result': case.get('result')}
        if case.get('duration') is not None:
            duration = float(case.get('duration'))
            require(math.isfinite(duration) and 0 <= duration <= 86400, 'XML_DURATION')
            row['durationSeconds'] = duration
        rows.append(row)
    passed = sum(row['result'] == 'Passed' for row in rows)
    require(root.get('passed') == str(passed) and root.get('failed') == str(7 - passed) and all(root.get(key) == '0' for key in ('skipped', 'inconclusive')), 'XML_COUNTS')
    require(root.get('result') in ({'Passed'} if passed == 7 else {'Failed', 'Failed(Child)'}), 'XML_SUMMARY')
    return pin(raw), rows


def derived_xml(rows):
    passed = sum(row['result'] == 'Passed' for row in rows)
    root = ET.Element('test-run', {'result': 'Passed' if passed == 7 else 'Failed', 'total': '7', 'passed': str(passed), 'failed': str(7 - passed), 'skipped': '0', 'inconclusive': '0'})
    for row in rows:
        attributes = {'fullname': row['fullname'], 'result': row['result']}
        if 'durationSeconds' in row: attributes['duration'] = str(row['durationSeconds'])
        ET.SubElement(root, 'test-case', attributes)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'


def finish(env):
    report = dict(schema=1, purpose='SOURCE_ONLY_EXACT_SEVEN_EDITMODE', status='INCOMPLETE', **identity(env),
                  runtimeBaseCommit=BASE, requestId=REQUEST_ID, expectedNativeCases=7, totalPreparedEditModeCases=210,
                  nativeCases=0, nativeOutcome=env.get('NATIVE_OUTCOME') if env.get('NATIVE_OUTCOME') in OUTCOMES else 'unknown',
                  nativeResults=[], originalXmlSha256='', derivedXmlSha256='', sourceStateSha256='',
                  testSourceSha256='', originalSourceUnchanged=False, isolatedSourceVerified=False,
                  checks={name: 'NOT_CHECKED' for name in ('identity', 'source', 'isolation', 'nativeXml')})
    configure_copy()
    derived = None
    def check(name, action):
        try:
            action()
            report['checks'][name] = 'PASS'
        except Exception:
            # Fixed check names only. No exception text, native output, paths,
            # settings values or environment variables are exported.
            report['checks'][name] = 'FAIL'
    def check_identity():
        verify_dispatch(env)
        report['sourceStateSha256'] = pin(read(ROOT / SOURCE))
        report['testSourceSha256'] = pin(read(ROOT / TEST_SOURCE))
    def check_source():
        verify_unchanged()
        report['originalSourceUnchanged'] = True
    def check_isolation():
        require(isolated.inspect_copy(env) == 0, 'ISOLATION')
        report['isolatedSourceVerified'] = True
    def check_xml():
        nonlocal derived
        digest, rows = inspect_xml(ARTIFACTS)
        passed = all(row['result'] == 'Passed' for row in rows)
        require(report['nativeOutcome'] == ('success' if passed else 'failure'), 'NATIVE_OUTCOME')
        derived = derived_xml(rows)
        report.update(nativeCases=7, nativeResults=rows, originalXmlSha256=digest, derivedXmlSha256=pin(derived))
    for name, action in (('identity', check_identity), ('source', check_source), ('isolation', check_isolation), ('nativeXml', check_xml)):
        check(name, action)
    complete = all(value == 'PASS' for value in report['checks'].values())
    report['status'] = ('PASS' if report['nativeOutcome'] == 'success' else 'NATIVE_FAILED') if complete else 'INCOMPLETE'
    isolated.safe_path(EXPORT)
    require(not EXPORT.exists(), 'EXPORT_EXISTS')
    EXPORT.mkdir()
    isolated.write_new(EXPORT / 'report.json', report, 8192)
    if derived is not None:
        with (EXPORT / 'derived-exact-seven.xml').open('xb') as stream: stream.write(derived)
    isolated.output(env, 'report_ready=true\n')
    return 0 if report['status'] == 'PASS' else 2


def main():
    try:
        require(sys.argv[1:] in (['dispatch'], ['guard'], ['copy'], ['finish'], ['cleanup']), 'ARGUMENTS')
        command = sys.argv[1]
        configure_copy()
        if command == 'dispatch': verify_dispatch(os.environ)
        elif command == 'guard': guard(os.environ)
        elif command == 'copy': return isolated.create_copy(os.environ)
        elif command == 'finish': return finish(os.environ)
        else: return isolated.cleanup_copy(os.environ)
        return 0
    except Exception:
        print('COMBAT_FEEDBACK_PROBE_REJECTED')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
