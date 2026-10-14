#!/usr/bin/env python3
"""Two native Play runs, exact frozen 34+3 identity union; no synthetic NUnit XML."""
import hashlib
import os
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET
import activation_probe as private
import reflection_bake_ci as strict
import visual_candidate_ci as visual

require = visual.require
SHARDS = ('core', 'world')
PHASES = {s: 'regression-play-' + s for s in SHARDS}
FOLDERS = {'core': 'visual-regression-play-core', 'world': 'visual-regression-world'}
# Fixed per-process envelopes. Run31 completed 29 core cases before its old 480s deadline.
# Exact test identities, assertions and WORLD route bounds are unchanged.
BUDGET_SECONDS = {'core': 720, 'world': 480}
FROZEN = {'Lottery.G2.PlayMode.Tests.dll': ['Lottery.G2.PlayMode.Tests.G2PlayTests.BuyHalfScratchPanelReturnRevealAndClaimCommitsOneTicket',
                                   'Lottery.G2.PlayMode.Tests.G2PlayTests.UiHitConsumesGestureAndPanelPreservesTicket',
                                   'Lottery.G2.PlayMode.Tests.G2PlayTests.SecondTouchCannotTakeOverAndTouchUsesSameUvProjection',
                                   'Lottery.G2.PlayMode.Tests.G2PlayTests.PointerExitReentryAndFocusCancelDoNotBridge',
                                   'Lottery.G2.PlayMode.Tests.G2PlayTests.BackCancelsCaptureAndReturnsToCommittedTicket',
                                   'Lottery.G2.PlayMode.Tests.G2PlayTests.SaveFailureNeverShowsUncommittedScratch',
                                   'Lottery.G2.PlayMode.Tests.G2PlayTests.UnknownBuyBlocksInputUntilOriginalCommitIsRecovered',
                                   'Lottery.G2.PlayMode.Tests.G2PlayTests.ActualUrpFramesShowCommittedMaskAndSettlement'],
 'Lottery.G3.PlayMode.Tests.dll': ['Lottery.G3.PlayMode.Tests.G3PlayTests.ActualUrpFramesShowOneDayAndDisclosedSeparateProtectedFixture',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.BoostPreselectionCancelsExplicitlyOnBackAndRestartButRulesRetainIntent',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.ChallengeSelectionPersistsBeforeRevealAndPanelCompletesOnlyCommittedCell',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.CurrentAndNextConfigurationKeepExactSparseSlotsAndLevelsAcrossReload',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.DayFlowUsesInputSystemForBothTicketsShoppingConfigurationPhoneAndNight',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.DisplayTokensRejectStaleCallbacksAndInvalidateOnDisable',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.ExistingStoreOrIncompleteFilesCannotBeReplacedByDiagnosticStart',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.FixedSeventyFiveStepEconomyUsesDeclaredLocalContextsAndRealTransactionsV2',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.MaximumAmountGlyphsStayInsideReviewedTextSafeBounds',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.NoChangeRejectionAndRecoveredReceiptHaveDistinctAccurateFeedback',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.NormalNewRunUsesUninjectedStartupRandomStockWholeDayAndSavedResume',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.PhysicalGuttersBreakBrushAndNeverScratchNeighboringLogicalCells',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.RuntimeResultGlyphShaderCannotLeakBehindUnrevealedMask',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.SafeAreasAndTwentyByNineViewportKeepPaperAspectAndActionHitRegions',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.SaveFailureAndUnknownBuyHideUnconfirmedPixelsAndRecoverOneTransaction',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.SecondaryTouchFocusPauseAndBackNeverTransferCapturedStroke',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.UiConsumesWholeGestureAndTableScratchCannotRotateCamera',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.QaEvidenceDayEndExportsAllTwentyNineLedgerRowsAndCommandReceipts',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.QaEvidenceInvalidSchemaAndInvariantSnapshotsFailClosed',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.QaEvidenceNumberCopyPreservesConfirmedMaskConfigurationAndStore',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.QaEvidenceSelectedChallengeKeepsCommitmentAndHidesUnrevealedOutcomes',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.QaEvidenceTouchScrollAndControlsFitBothLandscapeSafeAreasWithoutScratch',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.QaEvidenceUnknownCommitAndCorruptStoreWithholdStateWithoutRecoveryWrites',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.PhysicalPhoneProjectsRealGlassAndRestoresCameraWithoutChangingTicket',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.PhoneSendRequiresReleaseAndSavedPendingPacketSurvivesReload',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.PhysicalPhoneKeysMeetProjectedReferenceTargetsAndOcclusionBlocksTap',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.WorldInputEntryToTicketRackAndTableUsesConcurrentMoveLookAndRelease',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.WorldInputTableToPhysicalPhoneAndBackPreservesTicketAndCamera',
                                   'Lottery.G3.PlayMode.Tests.G3PlayTests.WorldInputStorageToolShelfDrawerAndPointerOwnershipArePhysical']}
WORLD = frozenset((
    'Lottery.G3.PlayMode.Tests.G3PlayTests.WorldInputEntryToTicketRackAndTableUsesConcurrentMoveLookAndRelease',
    'Lottery.G3.PlayMode.Tests.G3PlayTests.WorldInputTableToPhysicalPhoneAndBackPreservesTicketAndCamera',
    'Lottery.G3.PlayMode.Tests.G3PlayTests.WorldInputStorageToolShelfDrawerAndPointerOwnershipArePhysical',
))


def expected(shard):
    require(shard in SHARDS, 'PLAY_SHARD_REJECTED')
    return {assembly: [n for n in names if (n in WORLD) == (shard == 'world')]
            for assembly, names in FROZEN.items() if any((n in WORLD) == (shard == 'world') for n in names)}


def names(shard):
    return sorted(n for cases in expected(shard).values() for n in cases)


def selection(shard):
    # UTF supports a semicolon-separated regex list. Full anchors and escaped
    # dots select exact identities, never a prefix, fixture, category or negation.
    return ';'.join('^' + re.escape(n) + '$' for n in names(shard))


def selection_hash(shard):
    return hashlib.sha256(selection(shard).encode('ascii')).hexdigest()


def contract(root):
    observed = {}
    for label in ('g2', 'g3'):
        profile = visual.read_json(root / visual.TASK / ('ci/' + label + '-test-contract.json'))['profiles']['play']
        require(not set(observed).intersection(profile), 'PLAY_CONTRACT_ASSEMBLY_REPEATED')
        observed.update(profile)
    require(observed == FROZEN, 'PLAY_FROZEN_CONTRACT_CHANGED')
    core, world = set(names('core')), set(names('world'))
    all_names = [n for cases in FROZEN.values() for n in cases]
    require(len(core) == 34 and len(world) == 3 and not core & world and core | world == set(all_names)
            and len(all_names) == len(set(all_names)) == 37, 'PLAY_PARTITION_REJECTED')
    return observed


def identity(root):
    ident = visual.identity(root)
    require(all(ident.get(k) == os.environ.get(env) for k, env in
                (('sourceCommit','GITHUB_SHA'),('runId','GITHUB_RUN_ID'),('runAttempt','GITHUB_RUN_ATTEMPT'))), 'PLAY_RUN_IDENTITY_REJECTED')
    require(visual.HEX40.fullmatch(ident.get('sourceCommit','')) and visual.HEX40.fullmatch(ident.get('reviewedCandidateCommit',''))
            and ident['sourceCommit'] != ident['reviewedCandidateCommit'] and ident['runAttempt'] == '1'
            and re.fullmatch('[1-9][0-9]*', ident['runId']), 'PLAY_SOURCE_IDENTITY_REJECTED')
    return ident


def paths(root, shard):
    require(shard in SHARDS, 'PLAY_SHARD_REJECTED')
    return root / visual.TASK / 'artifacts' / FOLDERS[shard], visual.outdir(root) / PHASES[shard]


def regular(path, maximum):
    require(path.resolve() == path.absolute(), 'PLAY_FIXED_PATH_REJECTED')
    return visual.bounded.bounded_read(path, maximum)



def validate_suite_results(tree):
    # NUnit testcasecount describes discovery and can exceed executed cases
    # after filtering (observed in native run22). Validate execution counters,
    # not that discovery field, at EVERY suite level including namespaces.
    for suite in tree.iter('test-suite'):
        children = list(suite.iter('test-case'))
        require(all(c.get('result') in ('Passed', 'Failed') for c in children), 'PLAY_SUITE_INCOMPLETE_CASE_REJECTED')
        passed = sum(c.get('result') == 'Passed' for c in children)
        failed = len(children) - passed
        counts = dict(total=len(children), passed=passed, failed=failed, skipped=0, inconclusive=0)
        require(all(suite.get(key) == str(value) for key, value in counts.items()), 'PLAY_SUITE_COUNTS_REJECTED')
        require(suite.get('result') in (('Passed',) if failed == 0 else ('Failed', 'Failed(Child)')), 'PLAY_SUITE_RESULT_REJECTED')
        if failed == 0:
            require(not list(suite.iter('failure')), 'PLAY_SUITE_FAILURE_REJECTED')


def validate_tree(tree, shard):
    wanted = expected(shard); wanted_names = names(shard)
    cases = list(tree.iter('test-case'))
    assemblies = [a for a in tree.iter('test-suite') if a.get('type') == 'Assembly']
    require(tree.tag == 'test-run' and len(cases) == len(wanted_names) and {c.get('fullname') for c in cases} == set(wanted_names), 'PLAY_EXACT_CASES_REJECTED')
    require(len(assemblies) == len(wanted) and {a.get('name') for a in assemblies} == set(wanted), 'PLAY_ASSEMBLIES_REJECTED')
    owned = []
    for assembly in assemblies:
        children = list(assembly.iter('test-case'))
        require(len(children) == len(wanted[assembly.get('name')]) and {c.get('fullname') for c in children} == set(wanted[assembly.get('name')]), 'PLAY_CASE_OWNERSHIP_REJECTED')
        fixtures = [f for f in assembly.iter('test-suite') if f.get('type') == 'TestFixture']
        wanted_fixtures = {n.rsplit('.', 1)[0] for n in wanted[assembly.get('name')]}
        require(len(fixtures) == len(wanted_fixtures) and {f.get('fullname') for f in fixtures} == wanted_fixtures,
                'PLAY_FIXTURE_IDENTITY_REJECTED')
        fixture_owned = []
        for fixture in fixtures:
            fixture_cases = list(fixture.iter('test-case'))
            fixture_name = fixture.get('fullname')
            require(fixture.get('classname') == fixture_name and fixture.get('name') == fixture_name.rsplit('.', 1)[1]
                    and {c.get('fullname') for c in fixture_cases} == {n for n in wanted[assembly.get('name')] if n.rsplit('.', 1)[0] == fixture_name},
                    'PLAY_FIXTURE_OWNERSHIP_REJECTED')
            require(all(c.get('classname') == fixture_name and c.get('methodname') == c.get('fullname').rsplit('.', 1)[1]
                        and c.get('name') == c.get('methodname') for c in fixture_cases), 'PLAY_CASE_CLASS_METHOD_REJECTED')
            fixture_owned.extend(fixture_cases)
        require(len(fixture_owned) == len(children) and set(fixture_owned) == set(children), 'PLAY_FIXTURE_ORPHAN_REJECTED')
        owned.extend(children)
    require(len(owned) == len(cases) and set(owned) == set(cases), 'PLAY_ORPHANED_CASE_REJECTED')
    require(all(c.get('result') in ('Passed', 'Failed') for c in cases), 'PLAY_SKIP_OR_INCOMPLETE_REJECTED')
    require(all(c.get('result') != 'Passed' or c.find('failure') is None for c in cases), 'PLAY_PASSED_CASE_FAILURE_REJECTED')
    passed = sum(c.get('result') == 'Passed' for c in cases); failed = len(cases) - passed
    counts = dict(total=len(cases), passed=passed, failed=failed, skipped=0, inconclusive=0)
    require(all(tree.get(k) == str(v) for k, v in counts.items()), 'PLAY_NATIVE_COUNTS_REJECTED')
    require(tree.get('result') in (('Passed',) if not failed else ('Failed','Failed(Child)')), 'PLAY_ROOT_RESULT_REJECTED')
    validate_suite_results(tree)
    if not failed:
        require(all(s.get('result') == 'Passed' for s in tree.iter('test-suite')) and not list(tree.iter('failure')), 'PLAY_SUITE_FAILURE_REJECTED')
    return cases, counts


def native_receipt(root, shard, ident, failed, xml_path):
    path = visual.outdir(root) / ('safe-' + PHASES[shard] + '.json')
    raw = regular(path, 32768); receipt = strict.load_receipt(raw)
    require(all(receipt.get(k) == ident[k] for k in ('sourceCommit','reviewedCandidateCommit','runId','runAttempt'))
            and receipt.get('scope') == visual.SCOPE and receipt.get('phase') == PHASES[shard], 'PLAY_NATIVE_IDENTITY_REJECTED')
    require(type(receipt.get('schemaVersion')) is int and receipt['schemaVersion'] == 1
            and receipt.get('image') == private.IMAGE and receipt.get('mechanismSourcePin') == private.PIN
            and receipt.get('nativeOutput') == 'BOUNDED_MEMORY_ONLY_NO_RAW_LOG'
            and receipt.get('testVerdict') == 'SEPARATE_EXACT_NUNIT_VALIDATOR_REQUIRED', 'PLAY_NATIVE_PIN_REJECTED')
    require(receipt.get('shard') == shard and type(receipt.get('plannedCaseCount')) is int and receipt['plannedCaseCount'] == len(names(shard))
            and receipt.get('testSelectionSha256') == selection_hash(shard) and type(receipt.get('processBudgetSeconds')) is int
            and receipt['processBudgetSeconds'] == BUDGET_SECONDS[shard], 'PLAY_NATIVE_SELECTION_REJECTED')
    start = receipt.get('nativeStartedAtNs')
    require(type(start) is int and 0 < start <= time.time_ns() and xml_path.stat().st_mtime_ns >= start, 'PLAY_STALE_XML_REJECTED')
    code = 2 if failed else 0
    require(type(receipt.get('nativeExitMarkerCount')) is int and receipt['nativeExitMarkerCount'] == 1
            and type(receipt.get('nativeExitCode')) is int and type(receipt.get('dockerExitCode')) is int
            and receipt['nativeExitCode'] == receipt['dockerExitCode'] == code
            and receipt.get('status') == ('NATIVE_FAILED' if failed else 'NATIVE_SUCCEEDED'), 'PLAY_NATIVE_EXIT_REJECTED')
    obs = receipt.get('observations')
    require(type(obs) is dict and set(obs) == set(private.TOKENS) and all(type(v) is int and v >= 0 for v in obs.values())
            and obs['invalidLicenseXml400'] == obs['nativeActivationAborted'] == 0, 'PLAY_NATIVE_LICENSE_REJECTED')
    return hashlib.sha256(raw).hexdigest()


def inspect(root, shard, preserve=True):
    ident = identity(root); contract(root); source, target = paths(root, shard)
    target_receipt = target / 'test-receipt.json'
    if preserve:
        for filename in ('test-receipt.json', 'raw-test-results.xml', 'raw-test-report-receipt.json'):
            old = target / filename
            require(old.resolve() == old.absolute(), 'PLAY_FIXED_PATH_REJECTED')
            if old.exists(): old.unlink()
    xml_path = source / 'playmode-results.xml'; raw = regular(xml_path, 10*1024*1024)
    text = raw.decode('utf-8-sig')
    require('\x00' not in text and '<!DOCTYPE' not in text and '<!ENTITY' not in text, 'PLAY_XML_ENCODING_REJECTED')
    visual.bounded.require_safe_xml(raw)
    if preserve:
        target.mkdir(parents=True, exist_ok=True)
        # Keep original bytes even for failed or malformed case identities.
        # Do not rename any aggregate into an alleged native XML report.
        visual.bounded.export_raw_test_report(source, target)
        require((target / 'raw-test-results.xml').read_bytes() == raw, 'PLAY_XML_CHANGED_DURING_EXPORT')
    tree = ET.fromstring(raw); cases, counts = validate_tree(tree, shard)
    native_hash = native_receipt(root, shard, ident, counts['failed'], xml_path)
    value = dict(ident, schemaVersion=1, stage=PHASES[shard], shard=shard,
                 nativeResult=tree.get('result'), expectedCases=counts['total'], counts=counts,
                 allExpectedPassed=counts['failed'] == 0, rawXmlSha256=hashlib.sha256(raw).hexdigest(),
                 nativeReceiptSha256=native_hash, processBudgetSeconds=BUDGET_SECONDS[shard],
                 cases=[dict(fullname=c.get('fullname'), result=c.get('result')) for c in cases])
    if preserve: visual.write(target_receipt, value)
    return value


def export(root, shard):
    value = inspect(root, shard)
    require(value['allExpectedPassed'], 'PLAY_NATIVE_SHARD_FAILED_OR_INCOMPLETE')
    return value


def aggregate(root):
    ident = identity(root); contract(root)
    rows=[]; cases=[]
    for shard in SHARDS:
        try:
            receipt = inspect(root, shard)
            rows.append(dict(shard=shard, status='PASSED' if receipt['allExpectedPassed'] else 'FAILED',
                             expectedCases=receipt['expectedCases'], rawXmlSha256=receipt['rawXmlSha256'],
                             nativeReceiptSha256=receipt['nativeReceiptSha256'], counts=receipt['counts']))
            cases.extend(receipt['cases'])
        except Exception:
            rows.append(dict(shard=shard,status='REJECTED_OR_MISSING',expectedCases=len(names(shard))))
    union = len(cases) == 37 and len({c['fullname'] for c in cases}) == 37 and {c['fullname'] for c in cases} == set(names('core') + names('world'))
    passed = union and all(r['status'] == 'PASSED' for r in rows)
    value = dict(ident,schemaVersion=2, status='PASSED' if passed else 'FAILED',
                 evidenceKind='TWO_NATIVE_NUNIT_REPORTS_NOT_ONE_37_CASE_NATIVE_RUN',
                 expectedCases=37, exactDisjointUnionVerified=union, allExpectedPassed=passed,
                 processBudgetSecondsByShard=dict(BUDGET_SECONDS), totalPlayProcessEnvelopeSeconds=sum(BUDGET_SECONDS.values()),
                 shards=rows, cases=cases)
    visual.write(visual.outdir(root) / 'regression-play-summary.json', value)
    require(passed, 'PLAY_SPLIT_AGGREGATE_FAILED')
    return value
