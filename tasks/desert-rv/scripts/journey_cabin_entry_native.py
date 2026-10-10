"""Bounded actual-RV native observations, including a failed entry assertion.

This is diagnostic evidence only. It never creates a producer or player receipt.
The established keyboard helper owns all isolated-project lifecycle operations.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

import journey_keyboard_look_native as isolated
import journey_tracer_dispatch as dispatch
import journey_tracer_source_diagnostic as source

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / 'tasks/desert-rv'
REPORT = TASK / 'journey-cabin-entry-native-report.json'
ARTIFACTS = TASK / 'artifacts/journey-cabin-entry'
RAW_REPORT = isolated.COPY / 'JourneyEvidence/CabinEntry/native-entry-probe.json'
TEST_SOURCE = 'tasks/desert-rv/unity/Assets/DesertRV/Tests/PlayMode/JourneyCabinEntryPhysicsTests.cs'
EXPECTED = 'DesertRV.Tests.JourneyCabinEntryPhysicsTests.RealRV_StandardExitToCabin_AllTimesteps'
MAX_PHYSICS = 2 * 1024**2
MAX_REPORT = 2 * MAX_PHYSICS
OUTCOMES = {'success', 'failure', 'cancelled', 'skipped', 'unknown'}
SCENE = 'Assets/DesertRV/Scenes/BodyStudy.unity'
AUTHOR = 'Assets/DesertRV/Editor/JourneySceneAuthoring.cs'
MOTOR = 'Assets/DesertRV/Runtime/JourneyMotor.cs'
ADAPTER = 'Assets/DesertRV/Runtime/MobileInputAdapter.cs'
TIMESTEPS = (('fps-60', 1 / 60), ('fps-30', 1 / 30), ('fps-10', .1), ('fps-5', .2), ('fps-3', 1 / 3))


def require(ok):
    if not ok:
        raise ValueError('CABIN_ENTRY_EVIDENCE_REJECTED')


def pin(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(value):
    return type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None


def number(value, limit=1000000):
    return type(value) in (int, float) and math.isfinite(value) and abs(value) <= limit


def keys(value, fields):
    require(type(value) is dict and set(value) == set(fields.split()))


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def vector(value, limit=1000):
    return type(value) is dict and set(value) == {'x', 'y', 'z'} and all(number(part, limit) for part in value.values())


def path(value):
    return type(value) is str and len(value) <= 512 and value.startswith('Assets/DesertRV/') and re.fullmatch(r'[A-Za-z0-9 _./-]+', value) and all(part not in {'', '.', '..'} for part in value.split('/'))


def validate_physics(value):
    try:
        keys(value, 'schemaVersion status unityVersion fixture referenceRun referenceBootstrapSha256 referenceRegionSha256 sourceScene route maximumDeltaTime referenceGeometryMatched allEntered replayDetached sceneUnloaded sourceFilesUnchanged controller lowerCollider upperCollider floorCollider roadCollider savedRvColliderCount sourceFiles colliders cases')
        require(type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and value['status'] in {'fixture-incomplete', 'completed'})
        fixed = dict(unityVersion='6000.3.19f1', fixture='saved-RV-with-reconstructed-authored-road', referenceRun='38034314713',
                     referenceBootstrapSha256='a31e108cf90a6244847d414670e4922150c73f45d38d6365cb3f795ed728d09f',
                     referenceRegionSha256='ee6ded8b1e4c6284f6d40218a5b7b3768c95b2b4fee23c46d3f09162880e87e0',
                     sourceScene=SCENE, route='standard-exit; settle-1s; held-forward-max-6s; stop-on-cabin-floor')
        require(all(value[key] == item for key, item in fixed.items()))
        require(number(value['maximumDeltaTime'], 1) and value['maximumDeltaTime'] > 0)
        for key in ('referenceGeometryMatched', 'allEntered', 'replayDetached', 'sceneUnloaded', 'sourceFilesUnchanged'):
            require(type(value[key]) is bool)
        controller = value['controller']
        if controller is not None:
            keys(controller, 'height radius stepOffset skinWidth slopeLimit minMoveDistance center')
            require(vector(controller['center']) and all(number(controller[key], 180) and controller[key] >= 0 for key in controller if key != 'center'))
            require(controller['height'] > 0 and controller['radius'] > 0)
        files = value['sourceFiles']
        require(type(files) is list and 5 <= len(files) <= 261)
        for row in files:
            keys(row, 'path sha256')
            require(path(row['path']) and sha(row['sha256']))
        require(len({row['path'] for row in files}) == len(files))
        require({SCENE, SCENE + '.meta', AUTHOR, MOTOR, ADAPTER} <= {row['path'] for row in files})
        colliders = value['colliders']
        require(type(colliders) is list and len(colliders) <= 128 and integer(value['savedRvColliderCount'], 0, 127))
        for i, row in enumerate(colliders, 1):
            keys(row, 'id hierarchy type meshAsset meshGuid meshLocalId authoredBy enabled active trigger convex min max')
            require(type(row['id']) is int and row['id'] == i and type(row['hierarchy']) is str and len(row['hierarchy']) <= 512 and re.fullmatch(r'[A-Za-z0-9 _./()-]+', row['hierarchy']) and all(part not in {'', '.', '..'} for part in row['hierarchy'].split('/')))
            require(row['type'] in {'MeshCollider', 'BoxCollider', 'CapsuleCollider', 'SphereCollider'} and
                    row['authoredBy'] in {SCENE, AUTHOR + ':DressEnvironment/Road surface'})
            require(all(type(row[key]) is bool for key in ('enabled', 'active', 'trigger', 'convex')) and vector(row['min']) and vector(row['max']))
            require(all(row['min'][axis] <= row['max'][axis] for axis in ('x', 'y', 'z')))
            if row['meshAsset']:
                require(row['type'] == 'MeshCollider' and path(row['meshAsset']) and type(row['meshGuid']) is str and re.fullmatch('[a-f0-9]{32}', row['meshGuid']) and type(row['meshLocalId']) is str and re.fullmatch(r'-?[0-9]{1,20}', row['meshLocalId']))
            else:
                require(row['meshGuid'] == row['meshLocalId'] == '')
        ids = {row['id'] for row in colliders}
        for key in ('lowerCollider', 'upperCollider', 'floorCollider', 'roadCollider'):
            require(integer(value[key], 0, len(colliders)))
        cases = value['cases']
        require(type(cases) is list and len(cases) <= len(TIMESTEPS))
        for i, case in enumerate(cases):
            keys(case, 'name outcome delta exit end exited lowerSupported upperSupported floorSupported enteredCabin firstSideContactFrame firstConstrainedFrame firstPersistentBlockFrame frames')
            name, delta = TIMESTEPS[i]
            require(case['name'] == name and number(case['delta'], 1) and abs(case['delta'] - delta) <= 1e-6 and case['outcome'] in {'incomplete', 'exit-rejected', 'entered', 'blocked'})
            require(vector(case['exit']) and vector(case['end']))
            require(all(type(case[key]) is bool for key in ('exited', 'lowerSupported', 'upperSupported', 'floorSupported', 'enteredCabin')))
            frames = case['frames']
            require(type(frames) is list and len(frames) <= 450)
            for key in ('firstSideContactFrame', 'firstConstrainedFrame', 'firstPersistentBlockFrame'):
                require(integer(case[key], -1, len(frames) - 1))
            forward_started = False
            for index, frame in enumerate(frames):
                keys(frame, 'frame flags supportCollider droppedContacts phase elapsed delta footHeight intendedDistance forwardDistance doorAngle verticalSpeedBefore verticalSpeedAfter position supportPoint groundedBefore groundedAfter insideCabin contacts')
                require(type(frame['frame']) is int and frame['frame'] == index and integer(frame['flags'], 0, 7) and integer(frame['supportCollider'], 0, len(colliders)) and integer(frame['droppedContacts'], 0, 10000))
                require(frame['phase'] in {'settle', 'forward'} and not (forward_started and frame['phase'] == 'settle'))
                forward_started = forward_started or frame['phase'] == 'forward'
                require(all(number(frame[key], 1000) for key in ('elapsed', 'delta', 'footHeight', 'intendedDistance', 'forwardDistance', 'doorAngle')))
                require(all(number(frame[key], 24) and frame[key] <= 0 for key in ('verticalSpeedBefore', 'verticalSpeedAfter')))
                require(abs(frame['delta'] - delta) <= 1e-6 and abs(frame['elapsed'] - (index + 1) * delta) <= .005)
                require(abs(frame['intendedDistance'] - (3.1 * delta if frame['phase'] == 'forward' else 0)) <= 1e-5)
                require(vector(frame['position']) and vector(frame['supportPoint']) and all(type(frame[key]) is bool for key in ('groundedBefore', 'groundedAfter', 'insideCabin')))
                contacts = frame['contacts']
                require(type(contacts) is list and len(contacts) <= 8)
                for contact in contacts:
                    keys(contact, 'collider point normal moveDirection moveLength')
                    require(type(contact['collider']) is int and contact['collider'] in ids and vector(contact['point']) and vector(contact['normal'], 1.01) and vector(contact['moveDirection'], 1.01) and number(contact['moveLength'], 100) and contact['moveLength'] >= 0)
            if case['outcome'] != 'incomplete':
                require(case['outcome'] == ('entered' if case['enteredCabin'] else 'blocked' if case['exited'] else 'exit-rejected'))
                require(bool(frames) == case['exited'])
                if frames:
                    require(case['end'] == frames[-1]['position'])
                    require(case['enteredCabin'] == (frames[-1]['insideCabin'] and frames[-1]['groundedAfter'] and frames[-1]['supportCollider'] == value['floorCollider']))
                for key, collider in (('lowerSupported', 'lowerCollider'), ('upperSupported', 'upperCollider'), ('floorSupported', 'floorCollider')):
                    require(case[key] == any(frame['groundedAfter'] and frame['supportCollider'] == value[collider] for frame in frames))
        if value['status'] == 'completed':
            require(len(cases) == 5 and controller is not None and len(colliders) == value['savedRvColliderCount'] + 1 and
                    len({value[key] for key in ('lowerCollider', 'upperCollider', 'floorCollider', 'roadCollider')}) == 4 and all(value[key] > 0 for key in ('lowerCollider', 'upperCollider', 'floorCollider', 'roadCollider')))
            require(all(case['outcome'] != 'incomplete' for case in cases) and value['allEntered'] == all(case['enteredCabin'] for case in cases))
        else:
            require(value['allEntered'] is False)
        return True
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
        return False


def verify_physics_sources(value, expected):
    mandatory = {SCENE, SCENE + '.meta', AUTHOR, MOTOR, ADAPTER}
    meshes = {row['meshAsset'] for row in value['colliders'] if row['meshAsset']}
    require({row['path'] for row in value['sourceFiles']} == mandatory | meshes | {name + '.meta' for name in meshes})
    for row in value['sourceFiles']:
        original = expected.get('tasks/desert-rv/unity/' + row['path'])
        require(original is not None and original['sha256'] == row['sha256'])
        require(pin(isolated.file_bytes(isolated.PROJECT / row['path'])) == row['sha256'])
    # Only hierarchy segments already present in our saved game scene (plus the
    # one explicitly reconstructed authored road) may be exported as identities.
    scene = isolated.file_bytes(isolated.PROJECT / SCENE).decode('utf-8')
    names = set(re.findall(r'^  m_Name: (.+)$', scene, re.M)) | {'Road surface'}
    for row in value['colliders']:
        require(all(part in names for part in row['hierarchy'].split('/')))


def inspect_xml():
    isolated.safe_path(ARTIFACTS)
    require(ARTIFACTS.is_dir())
    paths = list(ARTIFACTS.rglob('*.xml'))
    require(len(paths) == 1)
    raw = isolated.file_bytes(paths[0], 1024**2)
    require(b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper())
    root = ET.fromstring(raw)
    cases = list(root.iter('test-case'))
    require(root.tag == 'test-run' and len(cases) == 1 and
            cases[0].get('fullname') == EXPECTED and root.get('total') == '1' and
            root.get('skipped') == '0' and root.get('inconclusive') == '0')
    result = cases[0].get('result')
    require(result in {'Passed', 'Failed'} and root.get('result') == result and
            root.get('passed') == ('1' if result == 'Passed' else '0') and
            root.get('failed') == ('0' if result == 'Passed' else '1'))
    row = dict(fullname=EXPECTED, result=result)
    if cases[0].get('duration') is not None:
        duration = float(cases[0].get('duration'))
        require(number(duration, 86400) and duration >= 0)
        row['durationSeconds'] = duration
    return pin(raw), [row]


def physics_complete(value):
    # The fixture schema is checked independently before any native strings leave
    # the owned project. Missing/invalid payloads never become diagnostic success.
    return validate_physics(value) and value['status'] == 'completed' and all(value[key] for key in
        ('referenceGeometryMatched', 'replayDetached', 'sceneUnloaded', 'sourceFilesUnchanged'))


def diagnostic_complete(report):
    return (all(item == 'PASS' for item in report['checks'].values()) and physics_complete(report['physics']) and
            len(report['nativeResults']) == 1 and
            (report['nativeResults'][0]['result'] == 'Passed') == report['physics']['allEntered'])


def blank(env):
    identity = isolated.owner_identity(env)
    return dict(schema=1, resultScope='ACTUAL_RV_ENTRY_PHYSICS_DIAGNOSTIC',
                purpose='NATIVE_DIAGNOSTIC_ONLY', **identity,
                requestId=dispatch.REQUEST_ID, requestSha256='', sourceStateSha256='',
                isolatedProjectPath=isolated.COPY_REL, expectedNativeCases=1,
                nativeCases=0, nativeOutcome='unknown', nativeResults=[], nativeXmlSha256='',
                fixtureSourceSha256='', physicsReportSha256='', physics=None,
                originalSourceUnchanged=False, isolatedSourceVerified=False,
                isolationReportSha256='', diagnosticComplete=False, status='INCOMPLETE',
                checks={name: 'NOT_CHECKED' for name in ('identity', 'nativeXml', 'physics', 'originalSource', 'isolation')})


def validate_report(value):
    try:
        expected = blank(dict(GITHUB_SHA=value['sourceCommit'], GITHUB_RUN_ID=value['runId'], GITHUB_RUN_ATTEMPT=value['runAttempt']))
        require(type(value) is dict and set(value) == set(expected))
        for key in ('schema', 'resultScope', 'purpose', 'requestId', 'isolatedProjectPath', 'expectedNativeCases'):
            require(type(value[key]) is type(expected[key]) and value[key] == expected[key])
        require(value['nativeOutcome'] in OUTCOMES and type(value['nativeCases']) is int and value['nativeCases'] in (0, 1))
        require(type(value['checks']) is dict and set(value['checks']) == set(expected['checks']) and
                all(item in {'NOT_CHECKED', 'PASS', 'FAIL'} for item in value['checks'].values()))
        for key in ('requestSha256', 'sourceStateSha256', 'fixtureSourceSha256', 'nativeXmlSha256', 'physicsReportSha256', 'isolationReportSha256'):
            require(value[key] == '' or sha(value[key]))
        for key in ('originalSourceUnchanged', 'isolatedSourceVerified', 'diagnosticComplete'):
            require(type(value[key]) is bool)
        require(value['originalSourceUnchanged'] == (value['checks']['originalSource'] == 'PASS'))
        require(value['isolatedSourceVerified'] == (value['checks']['isolation'] == 'PASS'))
        require(value['checks']['identity'] != 'PASS' or all(sha(value[key]) for key in ('requestSha256', 'sourceStateSha256', 'fixtureSourceSha256')))
        if value['nativeCases']:
            require(value['checks']['nativeXml'] == 'PASS' and sha(value['nativeXmlSha256']) and type(value['nativeResults']) is list and len(value['nativeResults']) == 1)
            row = value['nativeResults'][0]
            require(type(row) is dict and set(row) in ({'fullname', 'result'}, {'fullname', 'result', 'durationSeconds'}) and row['fullname'] == EXPECTED and row['result'] in {'Passed', 'Failed'})
            require('durationSeconds' not in row or number(row['durationSeconds'], 86400) and row['durationSeconds'] >= 0)
            require(value['nativeOutcome'] == ('success' if row['result'] == 'Passed' else 'failure'))
        else:
            require(value['nativeResults'] == [] and value['nativeXmlSha256'] == '' and value['checks']['nativeXml'] != 'PASS')
        require((value['physics'] is None and value['physicsReportSha256'] == '' and value['checks']['physics'] != 'PASS') or
                value['checks']['physics'] == 'PASS' and sha(value['physicsReportSha256']) and validate_physics(value['physics']))
        complete = diagnostic_complete(value)
        require(value['diagnosticComplete'] == complete and value['status'] == ('DIAGNOSTIC_COMPLETE' if complete else 'INCOMPLETE'))
        return True
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
        return False


def run(env):
    report = blank(env)
    report['nativeOutcome'] = env.get('NATIVE_OUTCOME') if env.get('NATIVE_OUTCOME') in OUTCOMES else 'unknown'
    def check(name, action):
        try:
            action()
            report['checks'][name] = 'PASS'
        except Exception:
            # No raw logs, exception text, XML messages, or caller paths are public.
            report['checks'][name] = 'FAIL'
    def identity():
        request = dispatch.verify(ROOT, env)
        report.update(requestSha256=pin(isolated.file_bytes(ROOT / dispatch.REQUEST, 2048)),
                      sourceStateSha256=request['sourceStateSha256'],
                      fixtureSourceSha256=pin(isolated.file_bytes(ROOT / TEST_SOURCE, 1024**2)))
    def xml():
        digest, rows = inspect_xml()
        require(report['nativeOutcome'] == ('success' if rows[0]['result'] == 'Passed' else 'failure'))
        report.update(nativeCases=1, nativeResults=rows, nativeXmlSha256=digest)
    def physics():
        require(report['checks']['identity'] == 'PASS')
        source_raw = isolated.file_bytes(ROOT / dispatch.SOURCE, 4 * 1024**2)
        require(pin(source_raw) == report['sourceStateSha256'])
        state = source.json_bytes(source_raw)
        expected = {row['path']: row for row in state['files'] + state['restoredFiles']}
        require(expected[TEST_SOURCE]['sha256'] == report['fixtureSourceSha256'])
        raw = isolated.file_bytes(RAW_REPORT, MAX_PHYSICS)
        value = source.json_bytes(raw)
        require(validate_physics(value))
        verify_physics_sources(value, expected)
        report.update(physics=value, physicsReportSha256=pin(raw))
    def original():
        isolated.verify_unchanged()
        report['originalSourceUnchanged'] = True
    def isolation():
        raw = isolated.file_bytes(isolated.ISOLATION_REPORT, isolated.MAX_ISOLATION_REPORT)
        value = source.json_bytes(raw)
        require(isolated.validate_isolation(value) and value['status'] == 'PASS' and
                all(value[key] == item for key, item in isolated.owner_identity(env).items()))
        report.update(isolatedSourceVerified=True, isolationReportSha256=pin(raw))
    for name, action in (('identity', identity), ('nativeXml', xml), ('physics', physics), ('originalSource', original), ('isolation', isolation)):
        check(name, action)
    report['diagnosticComplete'] = diagnostic_complete(report)
    report['status'] = 'DIAGNOSTIC_COMPLETE' if report['diagnosticComplete'] else 'INCOMPLETE'
    require(validate_report(report))
    isolated.safe_path(REPORT)
    raw = (json.dumps(report, separators=(',', ':')) + '\n').encode()
    require(len(raw) <= MAX_REPORT and not REPORT.exists())
    with REPORT.open('xb') as stream:
        stream.write(raw)
    isolated.output(env, 'report_written=true\nreport_valid=true\n' + ('diagnostic_complete=true\n' if report['diagnosticComplete'] else ''))
    return 0 if report['diagnosticComplete'] else 2


def main():
    try:
        require(sys.argv[1:] == [])
        return run(os.environ)
    except Exception:
        print('CABIN_ENTRY_REPORT_REJECTED')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
