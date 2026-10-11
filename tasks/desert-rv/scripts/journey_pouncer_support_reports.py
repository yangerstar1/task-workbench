"""Closed native receipt checks. These do not replace native XML or host byte checks.

Callers must bound/decode JSON with duplicate-key and nonfinite-number rejection.
With complete=False, safe incomplete receipts are accepted and return False;
completed receipts return True, but never authorize promotion without the XML gate.
"""
import math
import re

UNITY = '6000.3.19f1'
PRODUCER = '2915b8b1e5be8b800a3d71f186b5316a8f626bc8'
RECEIPT_SHA = 'e25634798fd3ed6d90758225ea1952b95691a6aada5e3b6f545f04c6696d66ba'
SCENES = tuple('Assets/DesertRV/Scenes/Journey/' + name + '.unity'
               for name in ('FirstStation', 'Scrapyard', 'NightBeacon'))
BEFORE = (
    '8dac5cd36c3d34a59f00d28075a786424d3837bfec05b36c6cf0c57cbd4d6e16',
    '4ab0e61c56b1a922cfd33473f69d8c74fcd4899da5bfb0d8020680e723e70de7',
    'f491acb525b971fa78f3dda56e859da839b3fca2d3af395ac4b31066b62e7e33',
)
AUTHOR_FLAGS = set('saved reloaded bindingsValid posesUnchanged colliderGeometryUnchanged healthUnchanged approvalFlagsUnchanged sceneMetasUnchanged sourcesUnchanged existingSerializedStateUnchanged'.split())
AUTHOR_KEYS = AUTHOR_FLAGS | set('schema status sourceCommit inputSha256 unityVersion failureStage failureCode approved scenes dependencies'.split())
AUTHOR_STAGES = set('input scene-authoring scene-reload source-safety dependencies final-pins scene-lifecycle'.split())
AUTHOR_CODES = set('''NONFINITE_SCENE_VALUE UNSTABLE_SERIALIZED_ASSET_REFERENCE UNSTABLE_SERIALIZED_OBJECT_REFERENCE REGION_INVENTORY_CHANGED ACTOR_INVENTORY_CHANGED PREPARED_ACTORS_REQUIRED UNEXPECTED_COLLIDER_TYPE APPROVAL_GATE_OPENED REGION_STRUCTURE_INVALID PRODUCTION_APPROVAL_OPENED NONFINITE_REGION_VALUE AUTHORIZED_SERIALIZED_ARRAY_NOT_FOUND EXISTING_COMPONENT_MISSING SERIALIZED_OBJECT_REFERENCE_UNRESOLVED SCENE_COLLIDERS_ABSENT ROOT_POSES_CHANGED COLLIDER_GEOMETRY_CHANGED ACTOR_HEALTH_CHANGED EXISTING_REGION_BINDING_CHANGED EXISTING_SERIALIZED_STATE_CHANGED EXACT_SUPPORT_BOXES_ABSENT SERIALIZED_SUPPORT_REFERENCES_INVALID SUPPORT_COMPONENT_INVENTORY_INVALID SUPPORT_ARRAY_NOT_SERIALIZED SUPPORT_BOX_NOT_SERIALIZED ARMORED_SUPPORT_WAS_ADDED POUNCER_SUPPORT_NOT_UNIQUE SUPPORT_OBJECT_REFERENCES_INVALID SUPPORT_REFERENCE_NOT_SERIALIZED PRODUCTION_SUPPORT_VALIDATION_FAILED CROSS_SCENE_ACTOR_REFERENCE_ADDED SOURCE_PIN_INVENTORY_INVALID SOURCE_PIN_CHANGED ORDINARY_RESTORED_SCENE_REQUIRED PINNED_BATCH_EDITMODE_REQUIRED INITIAL_SCENE_STATE_NOT_ISOLATED AUTHOR_INPUT_HASH_INVALID AUTHOR_INPUT_IDENTITY_INVALID SCENE_PIN_INVENTORY_INVALID PREPARED_SCENE_PIN_CHANGED PRODUCTION_BINDER_ABSENT PREPARED_SCENE_ALREADY_DERIVED DERIVED_SCENE_SAVE_FAILED DERIVED_SCENE_WAS_NOT_WRITTEN DERIVED_SCENE_CLOSE_FAILED DERIVED_SCENE_REMAINS_LOADED RELOADED_SCENE_OR_META_CHANGED RELOADED_SCENE_CLOSE_FAILED AUTHOR_INPUT_CHANGED SCENE_META_CHANGED NATIVE_DEPENDENCY_SNAPSHOT_INVALID FINAL_SCENE_PIN_CHANGED NATIVE_OPERATION_FAILED INITIAL_SCENE_SETUP_NOT_RESTORED'''.split())
DEP_KEYS = set('path sha256 kind packageName packageVersion bytes'.split())
BUILTINS = {'Resources/unity_builtin_extra', 'Library/unity default resources'}
AUTHOR_COMPLETE = 'COMPLETED_DERIVED_SCENES_UNREVIEWED'
AUTHOR_INCOMPLETE = 'INCOMPLETE_DERIVED_SCENES_UNREVIEWED'
FOCUSED_COMPLETE = 'COMPLETED_FOCUSED_SUPPORT_UNREVIEWED'
FOCUSED_INCOMPLETE = 'INCOMPLETE_FOCUSED_SUPPORT_UNREVIEWED'
FOCUSED_FLAGS = set('inputVerified replayDetached scenesUnloaded originalScenesPreserved sourcesUnchanged timeRestored cursorRestored'.split())
FOCUSED_KEYS = FOCUSED_FLAGS | set('schema status sourceCommit producerCommit producerGeneratedReceiptSha256 derivedReceiptSha256 inputSha256 unityVersion failureCode nativeErrorCount sourcePinCount scenePinCount approved cases'.split())
FOCUSED_CODES = set('''ACTIVE_SCENE ANIMATOR_CHANGED CAPTURE_CADENCE CASE_INVENTORY CLEANUP_EXCEPTION CLEANUP_FAILED CLEANUP_OR_NATIVE_ERROR CONSUMER_BYTES_DIFFER CORRECTED_CLEARANCE CROSSING_OR_TRANSITION_NOT_OBSERVED DIRECTOR_OWNER FIRST_WAVE_INVENTORY FIXTURE_ADVANCE FIXTURE_BINDINGS FIXTURE_COLLECT FIXTURE_INSTALL FIXTURE_MUTATED FOREIGN_COLLIDER FOREIGN_DIRECTOR FRAME_BOUND INDEPENDENT_SOLE_CLEARANCE INITIAL_SUPPORT_WRONG INPUT_HASH INPUT_MISSING INPUT_PROVENANCE INPUT_SCHEMA LEG_INVALID LEG_REPORT_INVENTORY MOVEMENT_OUTSIDE_PRODUCTION_AI_PHASE NATIVE_OR_OBSERVER_FAILURE NONFINITE_SAMPLE NONWALKABLE_SUPPORT NOT_PLAYMODE OBSERVATION_GAP OBSERVER_EXCEPTION PAW_BINDINGS PAW_LIMIT PAW_REPORT_FAILED PAW_REPORT_FRESH PLAYING_REQUIRED POUNCER_REQUIRED PREPARED_ROAD_EDGE PREPARED_SUPPORT_HEIGHTS PRODUCTION_BIND_R3 READABLE_NATIVE_SKIN REGION_ID REPORT_SIZE_BOUND REQUIRED_SOURCE_PIN ROOT_NOT_ON_ACTUAL_SUPPORT SAVED_MODEL_BINDING SAVED_SUPPORT_BINDING SAVED_SUPPORT_INVENTORY SCENE_PIN_INVENTORY SKIN_INVENTORY SOLE_INVENTORY_EMPTY SOURCE_ALREADY_LOADED SOURCE_PIN_HASH SOURCE_PIN_INVENTORY START_JOURNEY STATIONARY_INPUT_REQUIRED SUPPORT_MISSING TEST_EXCEPTION UNCHANGED_PAW_BUDGET UNITY_ERROR WEIGHT_STREAM_INVENTORY'''.split())
CASE_ORDER = ('rise-30hz', 'drop-30hz', 'rise-5hz', 'drop-5hz')
CASE_FLAGS = set('completed actorYUnchangedAtSetup boundSupportValid modelUnchanged targetStationary'.split())
CASE_INTS = set('frameBound frames firstFrame lastFrame stalkFrames windupFrames walkFrames animatorWindupFrames stalkToWindupCount walkToWindupCount blendedWalkToWindupFrames riseCount dropCount mixedSupportSamples lowSupportSamples highSupportSamples selectedSoleVertices correctedLegFrames aiMovementFrames independentSamples independentCrossingSamples independentTransitionSamples'.split())
CASE_FLOATS = set('captureDelta aiDelta actualDeltaMin actualDeltaMax initialSupportY finalSupportY measuredSurfaceRise horizontalTravel maxRootStep maxRootSupportError maxRootCenterGroundDelta maxPawCorrection maxPawResidual maxCorrectedClearanceError maxSkinningAgreementError'.split())
CASE_VECTORS = {'fixtureActorRoot', 'initialRoot', 'finalRoot', 'target'}
CASE_KEYS = CASE_FLAGS | CASE_INTS | CASE_FLOATS | CASE_VECTORS | {'name'}


def require(ok, code):
    if not ok:
        raise ValueError('POUNCER_SUPPORT_REPORT_' + code)


def keys(value, expected, code):
    require(type(value) is dict and set(value) == expected, code)


def digest(value, length=64):
    return type(value) is str and re.fullmatch('[a-f0-9]{' + str(length) + '}', value) is not None


def integer(value, low=0, high=2**31 - 1):
    return type(value) is int and low <= value <= high


def number(value, low=-1000000, high=1000000):
    return type(value) in (int, float) and low <= value <= high and math.isfinite(value)


def path(value):
    return (type(value) is str and 0 < len(value) <= 512 and not value.startswith('/') and
            not any(c in value for c in '\\:') and all(ord(c) >= 32 for c in value) and
            all(part not in ('', '.', '..') for part in value.split('/')))


def identity(value, expectation, input_sha, early=False):
    require(type(expectation) is dict and digest(expectation.get('sourceCommit'), 40) and
            expectation.get('unityVersion') == UNITY and digest(input_sha), 'EXPECTED_IDENTITY')
    require(type(value['schema']) is int and value['schema'] == 1 and value['unityVersion'] == UNITY and
            value['approved'] is False, 'IDENTITY')
    require(value['sourceCommit'] == expectation['sourceCommit'] or early and value['sourceCommit'] == '', 'SOURCE_IDENTITY')
    require(value['inputSha256'] == input_sha or early and value['inputSha256'] == '', 'INPUT_IDENTITY')


def dependencies(rows):
    require(type(rows) is list and len(rows) <= 20000, 'DEPENDENCY_LIST')
    previous = None
    for row in rows:
        keys(row, DEP_KEYS, 'DEPENDENCY_KEYS')
        p = row['path']
        require(path(p) and (previous is None or previous < p), 'DEPENDENCY_PATH_ORDER')
        previous = p
        require(type(row['kind']) is str and type(row['packageName']) is str and type(row['packageVersion']) is str and
                type(row['sha256']) is str and integer(row['bytes'], 0, 2**63 - 1), 'DEPENDENCY_TYPES')
        if row['kind'] == 'builtin':
            require(p in BUILTINS and row['sha256'] == row['packageName'] == row['packageVersion'] == '' and row['bytes'] == 0, 'BUILTIN_DEPENDENCY')
        else:
            require(digest(row['sha256']) and row['bytes'] > 0, 'DEPENDENCY_BYTES')
            if row['kind'] == 'asset':
                require(p.startswith('Assets/') and row['packageName'] == row['packageVersion'] == '', 'ASSET_DEPENDENCY')
            else:
                require(row['kind'] == 'package' and re.fullmatch(r'com\.unity\.[a-z0-9.-]+', row['packageName']) and
                        p.startswith('Packages/' + row['packageName'] + '/') and
                        re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?', row['packageVersion']), 'PACKAGE_DEPENDENCY')


def verify_author_report(value, expectation, input_sha, actual_dependencies, scene_pins, complete=True):
    """Return native receipt completeness; caller independently gates exact XML and bytes."""
    require(type(complete) is bool, 'COMPLETE_MODE')
    keys(value, AUTHOR_KEYS, 'AUTHOR_KEYS')
    require(value['status'] in (AUTHOR_COMPLETE, AUTHOR_INCOMPLETE), 'AUTHOR_STATUS')
    done = value['status'] == AUTHOR_COMPLETE
    require(not complete or done, 'AUTHOR_INCOMPLETE')
    require(type(value['scenes']) is list and len(value['scenes']) <= 3, 'AUTHOR_SCENES')
    early = not done and value['failureStage'] == 'input' and not value['scenes']
    identity(value, expectation, input_sha, early=early)
    require(type(value['failureStage']) is str and type(value['failureCode']) is str, 'AUTHOR_FAILURE_TYPES')
    require(all(type(value[name]) is bool for name in AUTHOR_FLAGS), 'AUTHOR_FLAG_TYPES')
    require(type(scene_pins) is list and len(scene_pins) == 3, 'EXPECTED_SCENE_PINS')
    for i, pin in enumerate(scene_pins):
        keys(pin, {'path', 'beforeSha256', 'afterSha256'}, 'EXPECTED_SCENE_KEYS')
        require(pin['path'] == SCENES[i] and pin['beforeSha256'] == BEFORE[i] and digest(pin['afterSha256']), 'EXPECTED_SCENE_IDENTITY')
    for i, row in enumerate(value['scenes']):
        keys(row, {'path', 'beforeSha256', 'afterSha256', 'actorCount', 'pouncerCount', 'supportCount'}, 'AUTHOR_SCENE_KEYS')
        require(all(row[name] == scene_pins[i][name] for name in scene_pins[i]) and row['afterSha256'] != row['beforeSha256'], 'AUTHOR_SCENE_PIN')
        require(all(type(row[name]) is int and row[name] == expected for name, expected in
                    (('actorCount', 3), ('pouncerCount', 2), ('supportCount', 2))), 'AUTHOR_SCENE_COUNTS')
    dependencies(actual_dependencies)
    dependency_pins = {row['path']: row['sha256'] for row in actual_dependencies}
    require(all(dependency_pins.get(pin['path']) == pin['afterSha256'] for pin in scene_pins), 'EXPECTED_DEPENDENCY_SCENE_PINS')
    dependencies(value['dependencies'])
    require(not value['dependencies'] or value['dependencies'] == actual_dependencies, 'AUTHOR_DEPENDENCIES')
    if done:
        require(len(value['scenes']) == 3 and all(value[name] for name in AUTHOR_FLAGS) and
                value['failureStage'] == value['failureCode'] == '' and value['dependencies'] and
                value['dependencies'] == actual_dependencies, 'AUTHOR_COMPLETION')
    else:
        require(value['failureStage'] in AUTHOR_STAGES and (value['failureCode'] == '' or value['failureCode'] in AUTHOR_CODES), 'AUTHOR_FAILURE_CODE')
    return done


def near(value, expected, tolerance=1e-7):
    return abs(value - expected) <= tolerance


def focused_case(row, index):
    keys(row, CASE_KEYS, 'FOCUSED_CASE_KEYS')
    require(row['name'] == CASE_ORDER[index], 'FOCUSED_CASE_ORDER')
    require(all(type(row[name]) is bool for name in CASE_FLAGS), 'FOCUSED_CASE_FLAGS')
    require(all(integer(row[name]) for name in CASE_INTS) and all(number(row[name]) for name in CASE_FLOATS), 'FOCUSED_CASE_NUMBERS')
    for name in CASE_VECTORS:
        keys(row[name], {'x', 'y', 'z'}, 'FOCUSED_VECTOR_KEYS')
        require(all(number(v) for v in row[name].values()), 'FOCUSED_VECTOR_FINITE')
    cadence, bound = ((1 / 30, 240) if index < 2 else (.2, 120))
    require(near(row['captureDelta'], cadence) and near(row['aiDelta'], min(cadence, .1)) and row['frameBound'] == bound and
            0 <= row['frames'] <= bound, 'FOCUSED_CADENCE_BOUND')
    # Failure may happen partway through a frame, after counters advanced but before
    # frames/lastFrame were committed. Only the final incomplete case may have it.
    observed = row['frames'] + (not row['completed'])
    counters = CASE_INTS - {'frameBound', 'frames', 'firstFrame', 'lastFrame', 'selectedSoleVertices', 'correctedLegFrames'}
    require(all(row[n] <= observed for n in counters) and row['correctedLegFrames'] <= 4 * observed and
            row['selectedSoleVertices'] <= 1000000, 'FOCUSED_COUNTER_BOUND')
    require(row['lowSupportSamples'] + row['highSupportSamples'] <= row['independentSamples'] and
            row['independentCrossingSamples'] <= row['independentSamples'] and row['independentTransitionSamples'] <= row['independentSamples'], 'FOCUSED_SAMPLE_COUNTS')
    require(all(row[n] >= 0 for n in CASE_FLOATS - {'initialSupportY', 'finalSupportY'}), 'FOCUSED_NEGATIVE_METRIC')
    if row['frames']:
        require(row['firstFrame'] > 0 and row['lastFrame'] - row['firstFrame'] + 1 == row['frames'], 'FOCUSED_FRAME_CONTIGUITY')
    else:
        # INITIAL_SUPPORT_WRONG can fail after firstFrame is recorded and before
        # the first completed frame updates frames/lastFrame.
        require(row['lastFrame'] == 0 and (not row['completed'] or row['firstFrame'] == 0), 'FOCUSED_EMPTY_FRAMES')
    if not row['completed']:
        return
    drop = index % 2 == 1
    start, finish = ((.035, -.04) if drop else (-.04, .035))
    require(all(row[n] for n in CASE_FLAGS) and row['frames'] > 0 and row['selectedSoleVertices'] >= 16, 'FOCUSED_CASE_COMPLETION')
    require(near(row['actualDeltaMin'], cadence, 1e-5) and near(row['actualDeltaMax'], cadence, 1e-5) and
            row['actualDeltaMin'] <= row['actualDeltaMax'], 'FOCUSED_ACTUAL_CADENCE')
    require(near(row['initialSupportY'], start, .0001) and near(row['finalSupportY'], finish, .0001) and
            near(row['initialRoot']['y'], row['initialSupportY'], .0001) and near(row['finalRoot']['y'], row['finalSupportY'], .0001) and
            near(row['measuredSurfaceRise'], .075, .0001) and near(abs(row['finalSupportY'] - row['initialSupportY']), row['measuredSurfaceRise'], 1e-7), 'FOCUSED_SUPPORT_LEVELS')
    require(near(row['fixtureActorRoot']['x'], -1 if drop else -10) and near(row['fixtureActorRoot']['z'], 14) and
            near(row['target']['x'], -13 if drop else 3.5) and near(row['target']['z'], 14), 'FOCUSED_FIXTURE_GEOMETRY')
    require(row['dropCount' if drop else 'riseCount'] > 0 and row['horizontalTravel'] > 3 and
            all(row[n] > 0 for n in ('lowSupportSamples', 'highSupportSamples', 'aiMovementFrames', 'independentCrossingSamples', 'independentTransitionSamples',
                                    'stalkFrames', 'walkFrames', 'stalkToWindupCount', 'animatorWindupFrames', 'walkToWindupCount')) and
            row['windupFrames'] >= 2, 'FOCUSED_CROSSING_AND_TRANSITION')
    require(row['independentCrossingSamples'] == row['riseCount'] + row['dropCount'] and
            row['independentTransitionSamples'] >= row['windupFrames'] and
            row['lowSupportSamples'] + row['highSupportSamples'] == row['independentSamples'], 'FOCUSED_INDEPENDENT_COVERAGE')
    # 1e-9 only covers float-to-JSON rounding; production budgets remain unchanged.
    limits = {'maxRootStep': .0751, 'maxRootSupportError': .0001, 'maxRootCenterGroundDelta': .0751,
              'maxPawCorrection': .1, 'maxPawResidual': .004, 'maxCorrectedClearanceError': .0002, 'maxSkinningAgreementError': .00025}
    require(all(row[name] <= limit + 1e-9 for name, limit in limits.items()), 'FOCUSED_PRODUCTION_BUDGET')


def verify_focused_report(value, expectation, input_sha, complete=False):
    """Validate closed four-case telemetry, including a safe incomplete final case."""
    require(type(complete) is bool, 'COMPLETE_MODE')
    keys(value, FOCUSED_KEYS, 'FOCUSED_KEYS')
    require(value['status'] in (FOCUSED_COMPLETE, FOCUSED_INCOMPLETE), 'FOCUSED_STATUS')
    done = value['status'] == FOCUSED_COMPLETE
    require(not complete or done, 'FOCUSED_INCOMPLETE')
    require(all(type(value[n]) is bool for n in FOCUSED_FLAGS), 'FOCUSED_FLAG_TYPES')
    early = not done and not value['inputVerified']
    identity(value, expectation, input_sha, early=early)
    require(value['producerCommit'] == PRODUCER and value['producerGeneratedReceiptSha256'] == RECEIPT_SHA and
            digest(expectation.get('derivedReceiptSha256')), 'FOCUSED_PRODUCER_IDENTITY')
    require(value['derivedReceiptSha256'] == expectation['derivedReceiptSha256'] or early and value['derivedReceiptSha256'] == '', 'FOCUSED_DERIVED_IDENTITY')
    require(type(value['failureCode']) is str and (value['failureCode'] == '' or value['failureCode'] in FOCUSED_CODES), 'FOCUSED_FAILURE_CODE')
    require(integer(value['nativeErrorCount']) and integer(value['sourcePinCount'], 0, 256) and integer(value['scenePinCount'], 0, 2), 'FOCUSED_REPORT_COUNTS')
    expected_count = expectation.get('sourcePinCount', 12)
    require(integer(expected_count, 12, 256) and expected_count % 2 == 0, 'EXPECTED_SOURCE_COUNT')
    require(type(value['cases']) is list and len(value['cases']) <= 4, 'FOCUSED_CASES')
    if value['inputVerified']:
        require(value['sourcePinCount'] == expected_count and value['scenePinCount'] == 2, 'FOCUSED_PIN_COUNTS')
    else:
        require(value['sourcePinCount'] == value['scenePinCount'] == 0 and not value['cases'], 'FOCUSED_UNVERIFIED_CASES')
    for index, row in enumerate(value['cases']):
        focused_case(row, index)
        require(index == len(value['cases']) - 1 or row['completed'], 'FOCUSED_INCOMPLETE_PREFIX')
    if done:
        require(len(value['cases']) == 4 and all(c['completed'] for c in value['cases']) and all(value[n] for n in FOCUSED_FLAGS) and
                value['nativeErrorCount'] == 0 and value['failureCode'] == '', 'FOCUSED_COMPLETION')
    return done
