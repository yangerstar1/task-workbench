"""Bounded diagnostics for failed Armored/Weapon native captures; never acceptance.

Install beside strict_output.py and weapon_output.py. The existing dispatcher owns
the failure, exit status and output directory. This helper returns False on any
unsafe input, never exposes an exception, and changes summary only after commit.
"""
import copy
from datetime import datetime
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
import xml.etree.ElementTree as ET
import zlib

import strict_output as strict

NATIVE_NAMES = frozenset((
    'DesertRV.Tests.CandidateMeshMeasurementTests.ScaledTranslatedRotatedHierarchyMatchesIndependentSkinning',
    'DesertRV.Tests.CandidateMeshMeasurementTests.RejectsBlendShapesAndTruncatedSkinQuality',
    'DesertRV.Tests.CandidateMeshMeasurementTests.StaticMeshesAndFourMillimetreGateUseWorldVertices',
    'DesertRV.Tests.CandidateMaterialIdentityTests.PersistedWeaponMaterialIdentitySurvivesNeutralSamplingAndRejectsImpostors',
    'DesertRV.Tests.CandidateArtImportTests.ExecutePinnedDiscoveryOrBindingDiagnostics',
    'DesertRV.Tests.CandidateAnimationPolicyTests.OnlyArmoredAttackGetsTheSourceLoopException',
    'DesertRV.Tests.CandidateAnimationPolicyTests.EqualKeyValuesDoNotExcuseUnsafeTangents',
    'DesertRV.Tests.CandidateAnimationPolicyTests.MissingNativeAnimatorGetsCreatedAndReused',
    'DesertRV.Tests.CandidateAnimationPolicyTests.OpenCoreEmissionSurvivesRealSaveReimportAndReload',
    'DesertRV.Tests.CandidateAnimationPolicyTests.RenderTargetCleanupDetachesCameraBeforeDestroy',
))
ENTRY = 'DesertRV.Tests.CandidateArtImportTests.ExecutePinnedDiscoveryOrBindingDiagnostics'
FAILURE_CODES = frozenset((
    'STRICT_NATIVE_FAILED', 'NATIVE_FAILED', 'NATIVE_CASE_MISSING_OR_FAILED',
    'STRICT_CAPTURE_STATUS', 'STRICT_FRAME_COUNT', 'STRICT_FRAME_INVENTORY',
    'STRICT_GROUND_PENETRATION', 'STRICT_ROOT_SAMPLE_DRIFT', 'STRICT_ROOT_VECTOR_DRIFT',
    'STRICT_ROOT_QUATERNION_DRIFT', 'STRICT_POSE_NOT_VARYING',
    'STRICT_WEAKPOINT_STATUS', 'STRICT_WEAKPOINT_INVENTORY', 'STRICT_WEAKPOINT_STATE',
    'STRICT_CORE_MATERIAL_STATE', 'STRICT_CORE_NOT_RESTORED',
    'STRICT_PLATE_NOT_CHANGED_OR_RESTORED',
    'POUNCER_CAPTURE_STATUS','POUNCER_FRAME_COUNT','POUNCER_FRAME_INVENTORY',
    'POUNCER_GROUND_PENETRATION','POUNCER_ROOT_SAMPLE_DRIFT','POUNCER_ROOT_VECTOR_DRIFT',
    'POUNCER_ROOT_QUATERNION_DRIFT','POUNCER_POSE_NOT_VARYING','POUNCER_TRANSITION_INCOMPLETE','POUNCER_RESET_INCOMPLETE',
    'WEAPON_CAPTURE_STATUS', 'WEAPON_FRAME_COUNT', 'WEAPON_MECHANICS_STATUS',
    'WEAPON_SAMPLE_COUNT', 'WEAPON_IK_POLICY', 'WEAPON_SAMPLE_DIAGNOSTICS_STATE',
    'WEAPON_SAMPLE_FIXED_LENGTH', 'WEAPON_SAMPLE_METRIC_LIMIT', 'WEAPON_SAMPLE_REACH',
    'WEAPON_FRAME_VISIBILITY', 'WEAPON_FRAME_ROOT_DRIFT',
    'WEAPON_ANIMATOR_POSE_NOT_VARYING', 'WEAPON_MESH_POSE_NOT_VARYING',
))
RUN_URL = r'https://github.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]*'
FRAME_FIELDS = frozenset(('image requestedState imageSha256 meshPoseSha256 advanceSeconds '
    'normalizedTime worldMinY groundReferenceY rootLocalPositionDelta rootLocalAngleDelta '
    'rootLocalScaleDelta stateHash sampledVertices outsideViewportVertices behindCameraVertices '
    'belowReferenceVertices transitioning groundDiagnosticApplicable rootLocalPosition '
    'rootLocalRotation rootLocalScale meshWorldMin meshWorldMax meshWorldSize '
    'meshSizeRatioToNeutral').split())
CAPTURE_FIELDS = frozenset(('graphicsDeviceType graphicsDeviceName status scope prefab '
    'dependencySha256 visualAccepted gameplayAccepted armoredAttackLoopIntent notCovered frames '
    'neutralRoot neutralMeshWorldMin neutralMeshWorldMax neutralMeshWorldSize').split())
ARM_METRICS = ('upperLength', 'foreLength', 'wristGap', 'shoulderDrift', 'targetDrift',
               'targetDistance', 'expectedUpperLength', 'expectedForeLength')
MAX_IMAGES = 8
MAX_SNAPSHOT = 768 * 1024**2


def require(ok):
    if not ok:
        raise ValueError('UNSAFE_FAILED_DIAGNOSTICS')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def shape(value, fields, optional=()):
    require(type(value) is dict and set(fields) <= set(value) <= set(fields) | set(optional))


def number(value, low=-10000, high=10000):
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high)


def text_list(value, maximum=20):
    # Raw free text is bounded for parsing only. It is NEVER included in output.
    require(type(value) is list and len(value) <= maximum
            and all(type(x) is str and len(x) <= 4096 for x in value))


def decode(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    def bad(_):
        raise ValueError('UNSAFE_FAILED_DIAGNOSTICS')
    return json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=bad)


def safe_node(path, directory=False):
    path = Path(path)
    require(not path.is_symlink() and all(not p.is_symlink() for p in path.parents))
    require(path.is_dir() if directory else path.is_file())
    return path


class Snapshot:
    """Freeze candidate bytes before semantic validation; recheck original bytes.

    Missing images are recorded as missing. Links, special nodes and oversized
    files are never treated as harmless missing images.
    """
    def __init__(self, root):
        self.root = safe_node(Path(root).absolute(), True)
        self.data = {}
        self.missing = set()
        self.total = 0

    def add(self, path, limit=512 * 1024**2, missing=False):
        path = Path(path).absolute()
        require(self.root in path.parents)
        require(not path.is_symlink() and all(not p.is_symlink() for p in path.parents))
        if path in self.data:
            return self.data[path]
        if not path.exists() and missing:
            self.missing.add(path)
            return None
        safe_node(path)
        require(path.stat().st_size <= limit)
        before = path.stat()
        data = path.read_bytes()
        safe_node(path)
        after = path.stat()
        require((before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns)
                == (after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns)
                and len(data) == after.st_size and len(data) <= limit)
        self.total += len(data)
        require(self.total <= MAX_SNAPSHOT and len(self.data) < 1000)
        self.data[path] = data
        return data

    def materialize(self, destination):
        for path, data in self.data.items():
            out = destination / path.relative_to(self.root)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)

    def verify(self):
        for path, data in self.data.items():
            safe_node(path)
            require(path.stat().st_size == len(data) and digest(path.read_bytes()) == digest(data))
        for path in self.missing:
            require(not path.exists() and not path.is_symlink()
                    and all(not p.is_symlink() for p in path.parents))


def freeze(root):
    """Only structural parsing is used to find files; trust checks run afterwards."""
    snap = Snapshot(root)
    project = snap.root / 'unity'
    evidence = safe_node(project / 'JourneyEvidence/CandidateArt', True)
    contract = decode(snap.add(project / 'CandidateImportInput/contract.json', 8 * 1024**2))
    imp = decode(snap.add(evidence / 'import-report.json', 8 * 1024**2))
    capture = decode(snap.add(evidence / 'capture-report.json', 32 * 1024**2))
    base = safe_node(project / 'Assets/DesertRV/CandidateArtImports', True)
    snap.add(Path(str(base) + '.meta'), 1024**2)
    for path in base.rglob('*'):
        require(not path.is_symlink())
        if path.is_dir():
            continue
        snap.add(path)
    require(type(imp) is dict and type(imp.get('dependencies')) is list
            and len(imp['dependencies']) <= 300)
    for name in imp['dependencies']:
        require(strict.rel(name) and (name.startswith('Assets/DesertRV/')
                or re.fullmatch(r'Packages/com\.unity\.[a-z0-9_.-]+/.+', name)
                or name in ('Resources/unity_builtin_extra', 'Library/unity default resources')))
        for item in (name, name + '.meta'):
            snap.add(project / item, missing=not name.startswith('Assets/'))
    require(type(capture) is dict and type(capture.get('frames')) is list
            and len(capture['frames']) <= 202)
    for frame in capture['frames']:
        require(type(frame) is dict and type(frame.get('image')) is str
                and re.fullmatch(r'frame-[0-9]{4}\.png', frame['image']))
        snap.add(evidence / frame['image'], 10 * 1024**2, missing=True)
    native_dir = safe_node(snap.root / 'artifacts/candidate-art', True)
    paths = list(native_dir.rglob('*.xml'))
    require(0 < len(paths) <= 20)
    for path in paths:
        snap.add(path, 10 * 1024**2)
    return snap, contract, imp, capture, paths


def validate_native_aggregate(root, results):
    """Exact NUnit outcome/count consistency, independent of historical case inventory.

    Production calls this only after validating the current exact test names.
    Historical public XML fixtures exercise this parser without changing their cases.
    """
    require(root.get('result') in ('Passed', 'Failed', 'Failed(Child)'))
    require(all(value in ('Passed', 'Failed') for value in results.values()))
    require((root.get('result') in ('Failed', 'Failed(Child)')) == ('Failed' in results.values()))
    if root.get('result') == 'Failed(Child)':
        expected = dict(testcasecount=len(results), total=len(results),
                        passed=sum(v == 'Passed' for v in results.values()),
                        failed=sum(v == 'Failed' for v in results.values()), inconclusive=0, skipped=0)
        require(all(root.get(key) == str(value) for key, value in expected.items()))


def validate_native(snap, paths):
    reports = []
    for path in paths:
        data = snap.data[path.absolute()]
        require(b'<!DOCTYPE' not in data.upper() and b'<!ENTITY' not in data.upper())
        root = ET.fromstring(data)
        if root.tag == 'test-run':
            reports.append((data, root))
    require(len(reports) == 1)
    data, root = reports[0]
    cases = list(root.iter('test-case'))
    require(root.get('result') in ('Passed', 'Failed', 'Failed(Child)') and len(cases) == len(NATIVE_NAMES)
            and {c.get('fullname') for c in cases} == NATIVE_NAMES)
    results = {}
    for case in cases:
        require(case.get('result') in ('Passed', 'Failed')
                and case.get('runstate') == 'Runnable'
                and case.get('label', '') not in ('Invalid', 'Ignored', 'Skipped', 'NotRunnable')
                and case.get('executed', 'True').lower() == 'true')
        start = datetime.fromisoformat(case.attrib['start-time'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(case.attrib['end-time'].replace('Z', '+00:00'))
        duration = float(case.attrib['duration'])
        require(start.tzinfo is not None and end.tzinfo is not None and end >= start
                and math.isfinite(duration) and 0 <= duration <= 86400)
        results[case.attrib['fullname']] = case.attrib['result']
    validate_native_aggregate(root, results)
    return dict(sha256=digest(data), cases=len(NATIVE_NAMES), passed=sum(v == 'Passed' for v in results.values()),
                failed=sum(v == 'Failed' for v in results.values()), entryResult=results[ENTRY],
                caseResults=[dict(fullname=name, result=results[name]) for name in sorted(NATIVE_NAMES)])


def image_state(data, expected):
    if data is None:
        return 'MISSING'
    if digest(data) != expected:
        return 'HASH_MISMATCH'
    try:
        from PIL import Image, ImageStat
        # The real capture uses TextureFormat.RGB24. Accept only that precise
        # non-interlaced encoding, with no ancillary chunks or hidden alpha.
        require(len(data) <= 10 * 1024**2 and data[:8] == b'\x89PNG\r\n\x1a\n')
        cursor, chunks, compressed = 8, [], bytearray()
        while cursor < len(data):
            require(cursor + 12 <= len(data) and len(chunks) < 1024)
            size = struct.unpack('>I', data[cursor:cursor+4])[0]
            end = cursor + 12 + size
            require(end <= len(data))
            tag = data[cursor+4:cursor+8]
            body = data[cursor+8:cursor+8+size]
            require(tag in (b'IHDR', b'IDAT', b'IEND')
                    and (zlib.crc32(tag + body) & 0xffffffff)
                    == struct.unpack('>I', data[cursor+8+size:end])[0])
            if tag == b'IHDR':
                require(not chunks and size == 13
                        and struct.unpack('>IIBBBBB', body) == (960, 540, 8, 2, 0, 0, 0))
            elif tag == b'IDAT':
                require(chunks and chunks[-1] in (b'IHDR', b'IDAT'))
                compressed.extend(body)
            else:
                require(size == 0 and chunks and chunks[-1] == b'IDAT' and end == len(data))
            chunks.append(tag)
            cursor = end
        require(chunks and chunks[0] == b'IHDR' and chunks[-1] == b'IEND'
                and chunks.count(b'IHDR') == chunks.count(b'IEND') == 1)
        # Pillow deliberately ignores data after a zlib stream. Verify the
        # complete compressed stream ourselves so an IDAT cannot carry a second
        # stream or arbitrary tail after the image pixels.
        expected = 540 * (1 + 960 * 3)
        decoder = zlib.decompressobj()
        scanlines = decoder.decompress(bytes(compressed), expected + 1)
        require(len(scanlines) == expected and decoder.eof
                and not decoder.unused_data and not decoder.unconsumed_tail
                and decoder.flush() == b'')
        require(all(scanlines[row * (1 + 960 * 3)] in range(5) for row in range(540)))
        with Image.open(io.BytesIO(data)) as im:
            require(im.format == 'PNG' and im.size == (960, 540))
            im.verify()  # Includes PNG chunk CRC verification.
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            require(im.mode == 'RGB' and not getattr(im, 'is_animated', False))
            # Unity EncodeToPNG does not emit text/EXIF/ICC chunks. Do not export
            # an image carrying hidden arbitrary report or private metadata.
            require(not im.info)
            rgb = im.convert('RGB')
            ranges = rgb.getextrema()
            require(max(v[1] for v in ranges) >= 26
                    and max(v[1] - v[0] for v in ranges) >= 16
                    and max(ImageStat.Stat(rgb).stddev) >= 2)
        return 'VERIFIED'
    except Exception:
        return 'INVALID_PNG'


def arm_shape(value):
    shape(value, (*ARM_METRICS, 'solved', 'measured', 'measurementsFinite', 'reason'))
    for field in ('solved', 'measured', 'measurementsFinite'):
        require(type(value[field]) is bool)
    require(value['reason'] is None or type(value['reason']) is str and len(value['reason']) <= 4096)
    for key in ARM_METRICS:
        number(value[key], 0, 10000)
    # Only declared numbers/booleans survive; reason is never copied.
    return {k: value[k] for k in (*ARM_METRICS, 'solved', 'measured', 'measurementsFinite')}


def weapon_rows(value):
    import weapon_output as weapon
    shape(value, ('status', 'mechanicsPassed', 'gameplayAccepted', 'visualAccepted',
        'sceneCalibrated', 'scope', 'sampleRateHz', 'maxWristGapWorld',
        'maxShoulderDriftWorld', 'maxTargetDriftWorld', 'samples', 'failures'))
    require(value['status'] in ('not-complete', 'failed-imported-arm-count-mechanics',
                                'imported-arm-count-mechanics-passed-unreviewed')
            and type(value['mechanicsPassed']) is bool
            and value['scope'] == weapon.MECHANICS_SCOPE
            and value['gameplayAccepted'] is False and value['visualAccepted'] is False
            and value['sceneCalibrated'] is False
            and type(value['sampleRateHz']) is int and value['sampleRateHz'] == 200)
    text_list(value['failures'])
    for key in ('maxWristGapWorld', 'maxShoulderDriftWorld', 'maxTargetDriftWorld'):
        number(value[key], 0, 10000)
    samples = value['samples']
    schedule = weapon.sample_schedule()
    require(type(samples) is list and len(samples) <= 4463)
    result = []
    for index, row in enumerate(samples):
        shape(row, ('state', 'animatorPoseSha256', 'normalized', 'loadedBefore', 'plannedAdded',
            'ikApplied', 'poseAccepted', 'left', 'right', 'incomingLocalOffset', 'leftLocalOffset',
            'worldPitch', 'subjectWorldPosition', 'subjectWorldRotation'))
        state, t, before, added, position, rotation, _ = schedule[index]
        require(row['state'] == state and type(row['loadedBefore']) is int
                and row['loadedBefore'] == before and type(row['plannedAdded']) is int
                and row['plannedAdded'] == added and strict.digest(row['animatorPoseSha256'])
                and type(row['ikApplied']) is bool and row['ikApplied'] is (state == 'Reload')
                and type(row['poseAccepted']) is bool)
        number(row['normalized'], 0, 1)
        require(abs(row['normalized'] - t) <= 1e-6)
        require(row['poseAccepted'] or index == len(samples) - 1)
        for key in ('incomingLocalOffset', 'leftLocalOffset', 'worldPitch', 'subjectWorldPosition'):
            strict.vec(row[key])
        strict.vec(row['subjectWorldRotation'], True)
        require(strict.distance(row['subjectWorldPosition'], position) <= 1e-5
                and strict.angle(row['subjectWorldRotation'], rotation) <= .001)
        clean = {k: copy.deepcopy(row[k]) for k in row if k not in ('left', 'right')}
        clean['sampleIndex'] = index
        clean['left'], clean['right'] = arm_shape(row['left']), arm_shape(row['right'])
        result.append(clean)
    return result, schedule


def frame_shape(frame, index, kind, neutral):
    shape(frame, FRAME_FIELDS)
    require(frame['image'] == f'frame-{index:04}.png' and strict.digest(frame['imageSha256'])
            and strict.digest(frame['meshPoseSha256']))
    for key in ('advanceSeconds', 'normalizedTime', 'worldMinY', 'groundReferenceY'):
        number(frame[key])
    require(0 <= frame['advanceSeconds'] <= .5 and type(frame['transitioning']) is bool
            and frame['groundDiagnosticApplicable'] is (kind != 'weapon')
            and type(frame['stateHash']) is int and -2**31 <= frame['stateHash'] < 2**31
            and type(frame['sampledVertices']) is int and 0 < frame['sampledVertices'] <= 20000000)
    for key in ('outsideViewportVertices', 'behindCameraVertices', 'belowReferenceVertices'):
        require(type(frame[key]) is int and 0 <= frame[key] <= frame['sampledVertices'])
    for key in ('rootLocalPositionDelta', 'rootLocalScaleDelta', 'rootLocalAngleDelta'):
        number(frame[key], 0, 10000)
    for key in ('rootLocalPosition', 'rootLocalScale', 'meshSizeRatioToNeutral'):
        strict.vec(frame[key])
    strict.vec(frame['rootLocalRotation'], True)
    strict.mesh_dimensions(frame['meshWorldMin'], frame['meshWorldMax'], frame['meshWorldSize'])
    require(abs(frame['worldMinY'] - frame['meshWorldMin']['y']) <= .00001)
    for axis in 'xyz':
        ratio = frame['meshWorldSize'][axis] / neutral['neutralMeshWorldSize'][axis]
        require(abs(ratio - frame['meshSizeRatioToNeutral'][axis]) <= max(.00001, abs(ratio) * .000001))
    for field, baseline, delta in (('rootLocalPosition', 'position', 'rootLocalPositionDelta'),
                                    ('rootLocalScale', 'scale', 'rootLocalScaleDelta')):
        require(abs(strict.distance(frame[field], neutral['neutralRoot'][baseline]) - frame[delta]) <= .000002)
    require(abs(strict.angle(frame['rootLocalRotation'], neutral['neutralRoot']['rotation'])
                - frame['rootLocalAngleDelta']) <= .002)


def sanitize_capture(c, imp, capture, snap):
    kind = c['kind']
    shape(capture, CAPTURE_FIELDS, ('weapon',))
    require(capture['status'] in ('not-complete', 'captured-unreviewed')
            and capture['scope'] == 'real-Animator-pose-diagnostics-only'
            and capture['visualAccepted'] is False and capture['gameplayAccepted'] is False
            and capture['graphicsDeviceType'] == 'OpenGLCore'
            and type(capture['graphicsDeviceName']) is str
            and re.fullmatch(r'[A-Za-z0-9 ().,_/+\-]{1,240}', capture['graphicsDeviceName'])
            and 'llvmpipe' in capture['graphicsDeviceName'].lower()
            and capture['prefab'] == imp['prefab']
            and capture['dependencySha256'] == imp['dependencySha256'])
    # Known narrative fields are never passed through, even when well formed.
    text_list(capture['notCovered'])
    require(type(capture['armoredAttackLoopIntent']) is str and len(capture['armoredAttackLoopIntent']) <= 4096)
    neutral = capture['neutralRoot']
    shape(neutral, ('position', 'rotation', 'scale', 'renderers'))
    strict.vec(neutral['position']); strict.vec(neutral['rotation'], True); strict.vec(neutral['scale'])
    require(type(neutral['renderers']) is list and 1 <= len(neutral['renderers']) <= 2000)
    paths = set()
    for row in neutral['renderers']:
        shape(row, ('path', 'worldCenter', 'worldExtents'))
        require(strict.rel(row['path']) and row['path'] not in paths)
        paths.add(row['path'])
        strict.vec(row['worldCenter']); strict.vec(row['worldExtents'])
        require(all(v >= 0 for v in row['worldExtents'].values()))
    strict.mesh_dimensions(capture['neutralMeshWorldMin'], capture['neutralMeshWorldMax'], capture['neutralMeshWorldSize'])
    if kind != 'weapon':
        if kind=='pouncer':
            import pouncer_output as enemy_validator
        else:
            enemy_validator=strict
        enemy_validator.compare_baseline(c['bindings']['neutralBaseline'], neutral)
        samples, schedule = [], []
        labels = enemy_validator.expected_labels()
    else:
        samples, schedule = weapon_rows(capture['weapon'])
        labels = {schedule[row['sampleIndex']][6] for row in samples if schedule[row['sampleIndex']][6]}
        for row in samples:
            if not row['poseAccepted']:
                labels.add(f"FAILED-{row['state']}-{row['loadedBefore']}-plus-{row['plannedAdded']}-{row['normalized']:.6f}")
    frames = capture['frames']
    require(type(frames) is list and len(frames) <= (202 if kind == 'armored' else 184 if kind == 'pouncer' else 26)
            and (frames or samples))
    seen = set()
    result = []
    for index, frame in enumerate(frames):
        frame_shape(frame, index, kind, capture)
        label = frame['requestedState']
        require(type(label) is str and label in labels and label not in seen)
        seen.add(label)
        if kind == 'weapon':
            # Match each picture to a measured sample, including the optional
            # failure picture emitted before the throwing quality assertion.
            matches = []
            for row in samples:
                normal = schedule[row['sampleIndex']][6]
                failed = f"FAILED-{row['state']}-{row['loadedBefore']}-plus-{row['plannedAdded']}-{row['normalized']:.6f}"
                if label == normal or label == failed and not row['poseAccepted']:
                    matches.append(row)
            require(matches and any(abs(frame['normalizedTime'] - row['normalized']) <= 1e-5 for row in matches))
        clean = copy.deepcopy(frame)
        path = snap.root / 'unity/JourneyEvidence/CandidateArt' / frame['image']
        clean['imageState'] = image_state(snap.data.get(path), frame['imageSha256'])
        clean['groundDeltaY'] = frame['worldMinY'] - frame['groundReferenceY']
        clean['groundWithinFourMillimeters'] = (clean['groundDeltaY'] >= -.004) if kind != 'weapon' else None
        clean['exportedImage'] = None
        result.append(clean)
    # Omit renderer paths and all narrative fields from the public document.
    return dict(captureStatus=capture['status'], graphicsDeviceType='OpenGLCore',
        graphicsRenderer='llvmpipe', frameCount=len(result), weaponSampleCount=len(samples),
        neutralRoot={k: copy.deepcopy(neutral[k]) for k in ('position', 'rotation', 'scale')},
        neutralMeshWorldMin=capture['neutralMeshWorldMin'], neutralMeshWorldMax=capture['neutralMeshWorldMax'],
        neutralMeshWorldSize=capture['neutralMeshWorldSize'], frames=result, weaponSamples=samples)


def select_images(frames, kind):
    available = [i for i, row in enumerate(frames) if row['imageState'] == 'VERIFIED']
    if kind != 'weapon':
        # Actual measured signed distance, NOT below-vertex count or frame order.
        worst = sorted(available, key=lambda i: (frames[i]['groundDeltaY'], i))
        selected = worst[:min(4, len(worst))]
    else:
        selected = [i for i in available if frames[i]['requestedState'].startswith('FAILED-')][:4]
    # Representatives from different legal state families, then chronology.
    families = set()
    for i in available:
        family = frames[i]['requestedState'].removeprefix('FAILED-').split('-')[0]
        if family not in families:
            families.add(family)
            if i not in selected and len(selected) < MAX_IMAGES:
                selected.append(i)
    for i in available:
        if len(selected) == MAX_IMAGES:
            break
        if i not in selected:
            selected.append(i)
    return selected


def validate_staged(staged, records, receipt_bytes):
    """The atomic directory commit must not carry any unlisted payload."""
    safe_node(staged, True)
    expected = {row['path']: (row['sha256'], row['bytes']) for row in records}
    require(len(expected) == len(records))
    expected['receipt.json'] = (digest(receipt_bytes), len(receipt_bytes))
    directories = {parent.as_posix() for name in expected for parent in Path(name).parents
                   if parent != Path('.')}
    actual_files, actual_directories = set(), set()
    for path in staged.rglob('*'):
        require(not path.is_symlink())
        name = path.relative_to(staged).as_posix()
        if path.is_dir():
            require(name in directories)
            actual_directories.add(name)
        else:
            safe_node(path)
            require(name in expected)
            expected_hash, expected_size = expected[name]
            require(path.stat().st_size == expected_size and digest(path.read_bytes()) == expected_hash)
            actual_files.add(name)
    require(actual_files == set(expected) and actual_directories == directories)


COLLECTION_STAGES = frozenset(('GUARD', 'FREEZE', 'NATIVE', 'IMPORT', 'GENERATED',
                               'CAPTURE', 'SNAPSHOT', 'STAGING', 'COMMIT'))


def collection_stage(stage):
    # Controlled stage names only. No exception, path, input value or raw report
    # is printed; failed diagnostics remain false/nonzero and never acceptance.
    require(stage in COLLECTION_STAGES)
    print('FAILED_CAPTURE_COLLECTION_STAGE=' + stage)


def _export(root, output, c, summary, native, protected):
    collection_stage('GUARD')
    code = summary.get('errorCode')
    require(code in FAILURE_CODES and native in ('success', 'failure') and protected == 'success')
    require(strict.digest(summary.get('importCommit'), 40)
            and type(summary.get('importRunUrl')) is str and re.fullmatch(RUN_URL, summary['importRunUrl']))
    output = safe_node(Path(output).absolute(), True)
    require(not any(output.iterdir()))
    collection_stage('FREEZE')
    snap, contract, imp, capture, native_paths = freeze(root)
    require(contract == c and c.get('kind') in ('armored', 'weapon', 'pouncer')
            and type(c.get('schema')) is int and c['schema'] == 1)
    validator = strict
    if c['kind'] == 'weapon':
        import weapon_output as validator
    elif c['kind']=='pouncer':
        import pouncer_output as validator
    files = validator.contract_shape(c)
    normalized_away = []
    if c['kind'] != 'weapon':
        # These are known shared JsonUtility fields for another kind. Their
        # values are neither interpreted nor trusted, including nested flags.
        # Preserve the frozen raw bytes/hash but validate only Armored's view.
        imp, capture = dict(imp), dict(capture)
        for name, report, fields in (
                ('import-report.json', imp, ('muzzle', 'weaponCalibration')),
                ('capture-report.json', capture, ('weapon',))):
            for field in fields:
                if field in report:
                    del report[field]
                    normalized_away.append(name + '.' + field)
    collection_stage('NATIVE')
    native_info = validate_native(snap, native_paths)
    if native == 'success':
        require(native_info['failed'] == 0)
    # Reusing the full import and generated-assets checks only proves import
    # identity/bytes. Capture quality thresholds continue to fail in the caller.
    frozen = Path(tempfile.mkdtemp(prefix='.failed-input-', dir=output.parent))
    staged = None
    try:
        snap.materialize(frozen)
        project = frozen / 'unity'
        collection_stage('IMPORT')
        prefix = validator.validate_import(project, c, project / 'CandidateImportInput/contract.json', imp)
        collection_stage('GENERATED')
        validator.generated_files(project, c, prefix, imp, files)
        collection_stage('CAPTURE')
        safe_capture = sanitize_capture(c, imp, capture, snap)
        source_identity = {key: c[key] for key in ('sourceCommit', 'runUrl', 'artifactId', 'artifactName',
                                                   'artifactSha256', 'mode', 'scope', 'kind')}
        source_identity.update(importCommit=summary['importCommit'], importRunUrl=summary['importRunUrl'],
            contractSha256=digest(snap.data[snap.root / 'unity/CandidateImportInput/contract.json']),
            dependencySha256=imp['dependencySha256'])
        document = dict(schema=1, status='FAILED_DIAGNOSTICS', approved=False,
            visualApproved=False, gameplayAccepted=False, calibratedForScene=False,
            errorCode=code, protectedSource='UNCHANGED', identity=source_identity,
            native=native_info, normalizedAwayFields=normalized_away, **safe_capture)
        document['rawReportSha256'] = {name: digest(snap.data[snap.root / 'unity/JourneyEvidence/CandidateArt' / name])
            for name in ('import-report.json', 'capture-report.json')}
        require(len(json.dumps(document, allow_nan=False)) <= 16 * 1024**2)
        collection_stage('SNAPSHOT')
        snap.verify()
        collection_stage('STAGING')
        staged = Path(tempfile.mkdtemp(prefix='.failed-diagnostics-', dir=output.parent))
        records = []
        for index in select_images(document['frames'], c['kind']):
            frame = document['frames'][index]
            relative = 'frames/' + frame['image']
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            data = snap.data[snap.root / 'unity/JourneyEvidence/CandidateArt' / frame['image']]
            require(image_state(data, frame['imageSha256']) == 'VERIFIED')
            path.write_bytes(data)
            require(digest(path.read_bytes()) == frame['imageSha256'])
            frame['exportedImage'] = relative
            records.append(dict(path=relative, sha256=digest(data), bytes=len(data)))
        data = (json.dumps(document, indent=2, allow_nan=False) + '\n').encode()
        require(len(data) <= 16 * 1024**2)
        (staged / 'failed-diagnostics.json').write_bytes(data)
        records.append(dict(path='failed-diagnostics.json', sha256=digest(data), bytes=len(data)))
        result = dict(source_identity, status='FAILED_DIAGNOSTICS', approved=False,
            errorCode=code, visualApproved=False, gameplayAccepted=False, calibratedForScene=False,
            protectedSource='UNCHANGED', nativeXmlSha256=native_info['sha256'], nativeCases=len(NATIVE_NAMES),
            nativeFailedCases=native_info['failed'], images=len(records)-1,
            observedFrames=len(document['frames']), weaponSamples=len(document['weaponSamples']), files=records)
        result['normalizedAwayFields'] = normalized_away
        receipt_bytes = (json.dumps(result, indent=2, allow_nan=False) + '\n').encode()
        (staged / 'receipt.json').write_bytes(receipt_bytes)
        snap.verify()
        validate_staged(staged, records, receipt_bytes)
        safe_node(output, True)
        require(not any(output.iterdir()))
        # Replace the empty runner-owned directory in one atomic operation.
        collection_stage('COMMIT')
        staged.replace(output)
        staged = None
        summary.clear()
        summary.update(result)
        return True
    finally:
        shutil.rmtree(frozen, ignore_errors=True)
        if staged is not None:
            shutil.rmtree(staged, ignore_errors=True)


def try_export_failed(root, output, c, summary, native, protected):
    """Try bounded failure diagnostics. Caller MUST still re-raise its error.

    False: summary and output are unchanged; caller writes its original safe
    receipt. True: the same output has committed FAILED_DIAGNOSTICS, approved=false;
    caller must not overwrite that receipt and must still return nonzero.
    """
    try:
        return _export(root, output, c, summary, native, protected)
    except Exception:
        return False
