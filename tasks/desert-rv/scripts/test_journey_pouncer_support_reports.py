"""Host validation tests use synthetic records; they are not native Unity proof."""
import copy
import math
import unittest

import journey_pouncer_support_reports as reports

SOURCE, INPUT, DERIVED = '1' * 40, '2' * 64, '3' * 64
EXPECTATION = {'sourceCommit': SOURCE, 'unityVersion': reports.UNITY, 'derivedReceiptSha256': DERIVED, 'sourcePinCount': 12}


def author_fixture():
    pins = [{'path': path, 'beforeSha256': reports.BEFORE[i], 'afterSha256': str(i + 4) * 64}
            for i, path in enumerate(reports.SCENES)]
    deps = sorted([{'path': p['path'], 'sha256': p['afterSha256'], 'kind': 'asset',
                    'packageName': '', 'packageVersion': '', 'bytes': 100 + i}
                   for i, p in enumerate(pins)], key=lambda p: p['path'])
    value = dict.fromkeys(reports.AUTHOR_FLAGS, True)
    value.update(schema=1, status=reports.AUTHOR_COMPLETE, sourceCommit=SOURCE, inputSha256=INPUT,
                 unityVersion=reports.UNITY, failureStage='', failureCode='', approved=False,
                 scenes=[dict(p, actorCount=3, pouncerCount=2, supportCount=2) for p in pins], dependencies=copy.deepcopy(deps))
    return value, deps, pins


def focused_case(index):
    row = dict.fromkeys(reports.CASE_FLAGS, True)
    row.update(dict.fromkeys(reports.CASE_INTS, 0))
    row.update(dict.fromkeys(reports.CASE_FLOATS, 0.0))
    for name in reports.CASE_VECTORS:
        row[name] = {'x': 0.0, 'y': 0.0, 'z': 14.0}
    drop = index % 2 == 1
    cadence = 1 / 30 if index < 2 else .2
    row.update(name=reports.CASE_ORDER[index], frameBound=240 if index < 2 else 120,
               frames=20, firstFrame=100, lastFrame=119, selectedSoleVertices=40,
               stalkFrames=15, windupFrames=5, walkFrames=15, animatorWindupFrames=2,
               stalkToWindupCount=1, walkToWindupCount=1, blendedWalkToWindupFrames=3,
               correctedLegFrames=50, aiMovementFrames=14, independentSamples=7,
               independentCrossingSamples=1, independentTransitionSamples=5,
               lowSupportSamples=1 if drop else 2, highSupportSamples=6 if drop else 5,
               mixedSupportSamples=1, dropCount=1 if drop else 0, riseCount=0 if drop else 1,
               captureDelta=cadence, aiDelta=min(cadence, .1), actualDeltaMin=cadence, actualDeltaMax=cadence,
               initialSupportY=.035 if drop else -.04, finalSupportY=-.04 if drop else .035,
               measuredSurfaceRise=.075, horizontalTravel=5.0, maxRootStep=.075,
               maxRootSupportError=.00005, maxRootCenterGroundDelta=.075, maxPawCorrection=.1,
               maxPawResidual=.004, maxCorrectedClearanceError=.0002, maxSkinningAgreementError=.00025)
    row['fixtureActorRoot'].update(x=-1 if drop else -10, y=-.04)
    row['initialRoot'].update(x=-1 if drop else -10, y=row['initialSupportY'])
    row['finalRoot'].update(x=-6 if drop else -5, y=row['finalSupportY'])
    row['target'].update(x=-13 if drop else 3.5, y=.9)
    return row


def focused_fixture():
    value = dict.fromkeys(reports.FOCUSED_FLAGS, True)
    value.update(schema=1, status=reports.FOCUSED_COMPLETE, sourceCommit=SOURCE,
                 producerCommit=reports.PRODUCER, producerGeneratedReceiptSha256=reports.RECEIPT_SHA,
                 derivedReceiptSha256=DERIVED, inputSha256=INPUT, unityVersion=reports.UNITY,
                 failureCode='', nativeErrorCount=0, sourcePinCount=12, scenePinCount=2,
                 approved=False, cases=[focused_case(i) for i in range(4)])
    return value


class AuthorReportTests(unittest.TestCase):
    def verify(self, value, complete=True, deps=None, pins=None):
        _, expected_deps, expected_pins = author_fixture()
        return reports.verify_author_report(value, EXPECTATION, INPUT,
                                            expected_deps if deps is None else deps,
                                            expected_pins if pins is None else pins, complete)

    def test_completed_receipt_and_nonpromoting_inspection(self):
        value, _, _ = author_fixture()
        self.assertTrue(self.verify(value))
        self.assertTrue(self.verify(value, complete=False))

    def test_every_incomplete_prefix_is_retained_but_not_complete(self):
        for count in range(4):
            with self.subTest(count=count):
                value, _, _ = author_fixture()
                value.update(status=reports.AUTHOR_INCOMPLETE, failureStage='scene-reload', failureCode='NATIVE_OPERATION_FAILED',
                             scenes=value['scenes'][:count], dependencies=[])
                for flag in reports.AUTHOR_FLAGS:
                    value[flag] = False
                self.assertFalse(self.verify(value, complete=False))
                with self.assertRaises(ValueError):
                    self.verify(value)

    def test_early_input_failure_allows_absent_pin_only_with_empty_prefix(self):
        value, _, _ = author_fixture()
        value.update(status=reports.AUTHOR_INCOMPLETE, failureStage='input', failureCode='', inputSha256='', scenes=[], dependencies=[])
        self.assertFalse(self.verify(value, complete=False))
        value['scenes'] = author_fixture()[0]['scenes'][:1]
        with self.assertRaises(ValueError):
            self.verify(value, complete=False)

    def test_closed_keys_identity_types_and_all_success_flags(self):
        mutations = [('unexpected', 'private/path'), ('schema', True), ('approved', True), ('sourceCommit', '9' * 40),
                     ('inputSha256', '9' * 64), ('unityVersion', '6000.3.20f1'), ('status', 'Passed'),
                     ('failureCode', '/runner/private/exception'), ('failureStage', 'done')]
        mutations += [(flag, False) for flag in reports.AUTHOR_FLAGS]
        mutations += [(flag, 1) for flag in reports.AUTHOR_FLAGS]
        for key, replacement in mutations:
            with self.subTest(key=key, replacement=replacement):
                value, _, _ = author_fixture(); value[key] = replacement
                with self.assertRaises(ValueError): self.verify(value)
        for key in reports.AUTHOR_KEYS:
            value, _, _ = author_fixture(); del value[key]
            with self.subTest(missing=key), self.assertRaises(ValueError): self.verify(value)

    def test_scene_order_digest_counts_and_extra_fields_fail_closed(self):
        for key, replacement in [('path', reports.SCENES[1]), ('beforeSha256', 'f' * 64), ('afterSha256', 'A' * 64),
                                 ('actorCount', True), ('pouncerCount', 1), ('supportCount', 3), ('extra', 0)]:
            value, _, _ = author_fixture(); value['scenes'][0][key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify(value)
        value, _, _ = author_fixture(); value['scenes'].reverse()
        with self.assertRaises(ValueError): self.verify(value)
        value, _, pins = author_fixture(); pins[0]['afterSha256'] = pins[0]['beforeSha256']; value['scenes'][0].update(pins[0])
        with self.assertRaises(ValueError): self.verify(value, pins=pins)

    def test_dependency_mismatch_unsafe_path_duplicate_and_bool_size(self):
        for key, replacement in [('sha256', 'f' * 64), ('path', 'Assets/../private'), ('bytes', True), ('kind', 'source'), ('extra', '')]:
            value, _, _ = author_fixture(); value['dependencies'][0][key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify(value)
        value, _, _ = author_fixture(); value['dependencies'].append(value['dependencies'][0])
        with self.assertRaises(ValueError): self.verify(value)
        value, _, _ = author_fixture(); value['dependencies'] = []
        with self.assertRaises(ValueError): self.verify(value)

    def test_incomplete_nonempty_dependencies_still_match_and_strings_stay_bounded(self):
        value, _, _ = author_fixture(); value.update(status=reports.AUTHOR_INCOMPLETE, failureStage='dependencies', failureCode='NATIVE_OPERATION_FAILED')
        self.assertFalse(self.verify(value, complete=False))
        value['dependencies'][0]['bytes'] += 1
        with self.assertRaises(ValueError): self.verify(value, complete=False)

    def test_expected_dependency_closure_agrees_with_observed_scene_hashes(self):
        value, deps, _ = author_fixture()
        deps[0]['sha256'] = 'f' * 64; value['dependencies'] = copy.deepcopy(deps)
        with self.assertRaisesRegex(ValueError, '^POUNCER_SUPPORT_REPORT_EXPECTED_DEPENDENCY_SCENE_PINS$'):
            self.verify(value, deps=deps)
        value, _, _ = author_fixture(); value.update(status=reports.AUTHOR_INCOMPLETE, failureStage='input', failureCode='private error')
        with self.assertRaises(ValueError): self.verify(value, complete=False)

    def test_official_package_and_builtin_dependency_types(self):
        rows = [{'path': 'Packages/com.unity.test-framework/package.json', 'sha256': 'a' * 64, 'kind': 'package',
                 'packageName': 'com.unity.test-framework', 'packageVersion': '1.6.0', 'bytes': 30},
                {'path': 'Resources/unity_builtin_extra', 'sha256': '', 'kind': 'builtin', 'packageName': '', 'packageVersion': '', 'bytes': 0}]
        reports.dependencies(rows)
        for key, replacement in [('packageName', 'com.evil.tool'), ('packageVersion', '../1.0'), ('bytes', -1)]:
            changed = copy.deepcopy(rows); changed[0][key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError): reports.dependencies(changed)


class FocusedReportTests(unittest.TestCase):
    def verify(self, value, complete=True):
        return reports.verify_focused_report(value, EXPECTATION, INPUT, complete=complete)

    def test_completed_four_cases_pass_and_inspection_returns_completeness(self):
        self.assertTrue(self.verify(focused_fixture()))
        self.assertTrue(self.verify(focused_fixture(), complete=False))

    def test_partial_prefix_and_failed_frame_are_retained_without_promotion(self):
        value = focused_fixture(); value.update(status=reports.FOCUSED_INCOMPLETE, failureCode='PAW_LIMIT', cases=value['cases'][:2])
        row = value['cases'][-1]; row.update(completed=False, maxPawCorrection=.12, stalkFrames=21)
        self.assertFalse(self.verify(value, complete=False))
        with self.assertRaises(ValueError): self.verify(value)
        value['cases'].append(focused_case(2))
        with self.assertRaises(ValueError): self.verify(value, complete=False)

    def test_early_input_failure_cannot_claim_observed_cases(self):
        value = focused_fixture()
        value.update(status=reports.FOCUSED_INCOMPLETE, inputVerified=False, failureCode='INPUT_MISSING',
                     sourceCommit='', derivedReceiptSha256='', inputSha256='', sourcePinCount=0, scenePinCount=0, cases=[])
        self.assertFalse(self.verify(value, complete=False))
        value['cases'] = [focused_case(0)]
        with self.assertRaises(ValueError): self.verify(value, complete=False)

    def test_first_frame_failure_and_extreme_integer_are_bounded(self):
        value = focused_fixture(); value.update(status=reports.FOCUSED_INCOMPLETE, failureCode='INITIAL_SUPPORT_WRONG', cases=value['cases'][:1])
        row = value['cases'][0]
        for name in reports.CASE_INTS:
            row[name] = 0
        row.update(completed=False, firstFrame=100, frameBound=240)
        self.assertFalse(self.verify(value, complete=False))
        row['maxRootSupportError'] = 10**500
        with self.assertRaisesRegex(ValueError, '^POUNCER_SUPPORT_REPORT_FOCUSED_CASE_NUMBERS$'):
            self.verify(value, complete=False)

    def test_identity_approvals_closed_fields_counts_and_cleanup_gate(self):
        mutations = [('unexpected', ''), ('schema', True), ('approved', True), ('sourceCommit', '8' * 40),
                     ('derivedReceiptSha256', '8' * 64), ('producerCommit', '8' * 40), ('producerGeneratedReceiptSha256', '8' * 64),
                     ('inputSha256', '8' * 64), ('failureCode', 'stack/private/path'), ('nativeErrorCount', 1),
                     ('nativeErrorCount', False), ('sourcePinCount', 14), ('scenePinCount', 1)]
        mutations += [(flag, False) for flag in reports.FOCUSED_FLAGS]
        mutations += [(flag, 1) for flag in reports.FOCUSED_FLAGS]
        for key, replacement in mutations:
            value = focused_fixture(); value[key] = replacement
            with self.subTest(key=key, replacement=replacement), self.assertRaises(ValueError): self.verify(value)

    def test_missing_reordered_duplicate_and_nonfinite_cases_fail(self):
        for cases in ([focused_case(1)], [focused_case(0), focused_case(0)], []):
            value = focused_fixture(); value['cases'] = cases
            with self.subTest(cases=len(cases)), self.assertRaises(ValueError): self.verify(value)
        for field in reports.CASE_FLOATS:
            for bad in (math.nan, math.inf, -math.inf, True):
                value = focused_fixture(); value['cases'][0][field] = bad
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError): self.verify(value)
        value = focused_fixture(); value['cases'][0]['target']['x'] = math.nan
        with self.assertRaises(ValueError): self.verify(value)

    def test_each_budget_cadence_frame_and_transition_is_enforced(self):
        mutations = [('captureDelta', .1), ('aiDelta', .2), ('actualDeltaMin', .2), ('frameBound', 241),
                     ('frames', 241), ('lastFrame', 121), ('correctedLegFrames', 1000), ('independentSamples', 1000),
                     ('maxRootStep', .076), ('maxRootSupportError', .0002), ('maxRootCenterGroundDelta', .08),
                     ('maxPawCorrection', .101), ('maxPawResidual', .005), ('maxCorrectedClearanceError', .0003),
                     ('maxSkinningAgreementError', .0003), ('horizontalTravel', 3), ('measuredSurfaceRise', .05),
                     ('initialSupportY', .035), ('riseCount', 0), ('lowSupportSamples', 0), ('highSupportSamples', 0),
                     ('independentCrossingSamples', 0), ('independentTransitionSamples', 0), ('stalkToWindupCount', 0),
                     ('walkToWindupCount', 0), ('windupFrames', 1), ('animatorWindupFrames', 0), ('selectedSoleVertices', 15)]
        for key, replacement in mutations:
            value = focused_fixture(); value['cases'][0][key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify(value)

    def test_case_keys_bool_vectors_and_drop_direction_are_closed(self):
        for key in reports.CASE_KEYS:
            value = focused_fixture(); del value['cases'][0][key]
            with self.subTest(missing=key), self.assertRaises(ValueError): self.verify(value)
        value = focused_fixture(); value['cases'][0]['target']['privatePath'] = '/private'
        with self.assertRaises(ValueError): self.verify(value)
        value = focused_fixture(); value['cases'][1]['dropCount'] = 0
        with self.assertRaises(ValueError): self.verify(value)
        value = focused_fixture(); value['cases'][0]['frames'] = True
        with self.assertRaises(ValueError): self.verify(value)


if __name__ == '__main__':
    unittest.main()
