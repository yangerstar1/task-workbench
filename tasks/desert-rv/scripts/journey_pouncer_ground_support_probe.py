"""One-use yielding R3 production-AI diagnostic with exact current prepared assets; no BuildPlayer."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import uuid
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / 'tasks/desert-rv'
sys.path[:0] = [str(TASK / 'scripts'), str(TASK / 'art/import-candidate'), str(TASK / 'art/journey-preparation')]
# A fresh private bytecode prefix prevents consuming native-created .pyc files during privileged cleanup.
sys.pycache_prefix = '/tmp/journey-pouncer-ground-support-python-' + uuid.uuid4().hex
sys.dont_write_bytecode = True
import verify_evidence as source
from journey_keyboard_look_native import file_bytes, raw_pin, safe_path, protected_inventory, settings_diff, apply_settings_diff, SETTINGS
from strict_output import verify_staged_inventory
import generated_export as generated

BASE = '65299f98cadb82183c631f0418672ead3313e71f'
PRODUCTION_BASE = '2915b8b1e5be8b800a3d71f186b5316a8f626bc8'
BRANCH = 'journey-pouncer-ground-support-2915'
REF = 'refs/heads/' + BRANCH
REPOSITORY = 'yangerstar1/task-workbench'
OWNER_NAME = 'yangerstar1'
WORKFLOW = '.github/workflows/desert-rv-pouncer-ground-support.yml'
REQUEST = '.github/dispatch/desert-rv-pouncer-ground-support-2915-r2-20261011.json'
NONCE = 'desert-rv-pouncer-ground-support-2915-r2-20261011-once'
PRODUCER = dict(commit=PRODUCTION_BASE, runId=38091066745,
    artifactId=11685769353, artifactName='journey-preparation-UNREVIEWED-38091066745-1',
    artifactBytes=19825311, artifactSha256='98448f817201ca54b7206ba535040a6ef5641bc2151c0da8ebe3fcb6caa60957',
    sourceStateSha256='9ef70e6f285d93241b84b6e9dd3aa4daaeb5d7e8f5bd77230531607c1d6f558a',
    generatedReceiptSha256='e25634798fd3ed6d90758225ea1952b95691a6aada5e3b6f545f04c6696d66ba')
RUN_URL = 'https://github.com/' + REPOSITORY + '/actions/runs/' + str(PRODUCER['runId'])
STRICT_PINS = dict(armored='ea1220af8d5bbf44c55e9ab01160ba326c3eeb119d80fe67a4e9eafef1c30bda',
    pouncer='6ced7f1850a821be0b3451ac8036b3408e328a41a4e207837b7ecb427c879c11',
    weapon='981477dca3aaae9116761c4aa748d304d30d366be6bf53e917f860fce97a8cd1')

PROJECT = TASK / 'unity'
COPY = TASK / 'journey-pouncer-ground-support-project'
PRIVATE = TASK / 'journey-pouncer-ground-support-private'
OWNER = TASK / 'journey-pouncer-ground-support-owner.json'
MARKER = '.journey-pouncer-ground-support-owner.json'
INPUT_REL = 'JourneyEvidence/R3ContinuousContact/consumer-input.json'
RAW_REL = 'JourneyEvidence/R3ContinuousContact/native-r3-continuous-contact.json'
ARTIFACTS = TASK / 'artifacts/journey-pouncer-ground-playmode'
AUTHOR_ARTIFACTS = TASK / 'artifacts/journey-pouncer-ground-author'
AUTHOR_INPUT = 'JourneyEvidence/PouncerGroundSupport/author-input.json'
AUTHOR_RAW = 'JourneyEvidence/PouncerGroundSupport/native-authoring.json'
FOCUSED_INPUT = 'JourneyEvidence/PouncerGroundSupport/focused-input.json'
FOCUSED_RAW = 'JourneyEvidence/PouncerGroundSupport/native-focused-support.json'
SEALED = PRIVATE / 'derived-owner.json'
DERIVED = PRIVATE / 'derived-scenes.json'
SCENES = tuple('Assets/DesertRV/Scenes/Journey/' + n + '.unity' for n in ('FirstStation','Scrapyard','NightBeacon'))
BOOTSTRAP = 'Assets/DesertRV/Scenes/Journey/JourneyBootstrap.unity'
AUTHOR_TEST = 'DesertRV.Tests.JourneyPouncerSupportBindingTests.BindPinnedPreparedScenes_SaveReloadPreservesSourceAndPoses'
FOCUSED_TEST = 'DesertRV.Tests.JourneyPouncerPreparedSupportTests.RealPreparedR3_PouncerCrossesSupportAtBothCadences'
AUTHOR_SOURCES = tuple('Assets/DesertRV/' + n + '.cs' for n in ('Editor/JourneyCandidateAssetIntegration','Runtime/RegionBinding','Runtime/BeastActor','Runtime/PouncerPawContactConstraint','Runtime/PouncerGroundSupport','Tests/EditMode/JourneyPouncerSupportBindingTests'))
NEW_DEPENDENCIES = ('Assets/DesertRV/Runtime/PouncerGroundSupport.cs','Assets/DesertRV/Runtime/PouncerGroundSupport.cs.meta')
FOCUSED_SOURCES = tuple('Assets/DesertRV/' + n + '.cs' for n in ('Runtime/PouncerGroundSupport','Runtime/PouncerPawContactConstraint','Runtime/BeastActor','Runtime/RegionBinding','Editor/JourneyCandidateMeshMeasurement','Tests/PlayMode/JourneyPouncerPreparedSupportTests'))
# Filled from the frozen, reviewed source delta before this one-use request is sealed.
UNITY_CHANGES = {'Assets/DesertRV/Tests/PouncerGround/DesertRV.PouncerGroundTests.asmdef', 'Assets/DesertRV/Tests/PlayMode/JourneyR3ContinuousContactTests.cs', 'Assets/DesertRV/Tests/CandidateArt/PouncerPawContactConstraintTests.cs', 'Assets/DesertRV/Tests/PouncerGround/PouncerGroundSupportTests.cs', 'Assets/DesertRV/Runtime/PouncerGroundSupport.cs', 'Assets/DesertRV/Runtime/PouncerGroundSupport.cs.meta', 'Assets/DesertRV/Runtime/BeastActor.cs', 'Assets/DesertRV/Tests/PlayMode/JourneyPouncerPreparedSupportTests.cs', 'Assets/DesertRV/Editor/JourneyCandidateAssetIntegration.cs', 'Assets/DesertRV/Tests/PouncerGround.meta', 'Assets/DesertRV/Tests/EditMode/JourneyPouncerSupportBindingTests.cs.meta', 'Assets/DesertRV/Tests/PouncerGround/PouncerGroundSupportTests.cs.meta', 'Assets/DesertRV/Tests/PouncerGround/DesertRV.PouncerGroundTests.asmdef.meta', 'Assets/DesertRV/Runtime/RegionBinding.cs', 'Assets/DesertRV/Tests/PlayMode/JourneyPouncerPreparedSupportTests.cs.meta', 'Assets/DesertRV/Tests/PlayMode/JourneyR3ContinuousContactTests.cs.meta', 'Assets/DesertRV/Runtime/PouncerPawContactConstraint.cs', 'Assets/DesertRV/Tests/EditMode/JourneyPouncerSupportBindingTests.cs'}
GENERIC_TESTS = ('DesertRV.Tests.PouncerGroundSupportTests.FollowsRaisedRoadUpAndDownAtNormalMovementCadence', 'DesertRV.Tests.PouncerGroundSupportTests.FollowsRaisedRoadUpAndDownAtLowMovementCadence', 'DesertRV.Tests.PouncerGroundSupportTests.MixedSoleUsesFiniteHighSideInsteadOfExtrapolatedPawCenterPlane', 'DesertRV.Tests.PouncerGroundSupportTests.SafeDropKeepsFifteenMillimeterRoadClearanceWithoutExtraVerticalLookAhead', 'DesertRV.Tests.PouncerGroundSupportTests.BlocksWallAndCeilingBeforeAnyRootWrite', 'DesertRV.Tests.PouncerGroundSupportTests.RejectsExcessiveRiseDropAndMissingSupportTransactionally', 'DesertRV.Tests.PouncerGroundSupportTests.UnboundPropIsNotSupportAndStillBlocksCapsuleMovement', 'DesertRV.Tests.PouncerGroundSupportTests.InvalidDynamicForeignDisabledAndTriggerBindingsFailWithoutWrites', 'DesertRV.Tests.PouncerGroundSupportTests.GentleSlopesMatchNativeBoxFacesAndSteepUnsupportedSlopesReject', 'DesertRV.Tests.PouncerGroundSupportTests.PausedBoundPoseDoesNotMoveAndSupportFailureRequiresExplicitReset', 'DesertRV.Tests.PouncerGroundSupportTests.StationarySupportDoesNotTurnExistingBodyContactIntoPawFailure', 'DesertRV.Tests.PouncerGroundSupportTests.SuccessfulRootMoveSynchronizesColliderWithoutAutomaticPhysicsSync', 'DesertRV.Tests.PouncerGroundSupportTests.DeathKeepsDisabledCapsuleAndResetRestoresGroundedLifecycle')
EXPORT = TASK / 'journey-pouncer-ground-support-export'
REPORT = EXPORT / 'report.json'
SNAPSHOT_SOURCES = tuple('Assets/DesertRV/' + name for name in (
    'Runtime/JourneyMotor.cs', 'Runtime/BeastActor.cs', 'Runtime/JourneyDirector.cs',
    'Runtime/JourneySession.cs', 'Runtime/MobileInputAdapter.cs',
    'Runtime/JourneyActions.cs', 'Runtime/JourneyActions.Geometry.cs', 'Runtime/PouncerPawContactConstraint.cs',
    'Runtime/PouncerGroundSupport.cs', 'Runtime/RegionBinding.cs', 'Editor/JourneyCandidateAssetIntegration.cs',
    'Tests/EditMode/JourneyPouncerSupportBindingTests.cs', 'Tests/PlayMode/JourneyPouncerPreparedSupportTests.cs',
    'Tests/PouncerGround/PouncerGroundSupportTests.cs', 'Tests/CandidateArt/PouncerPawContactConstraintTests.cs',
    'Tests/PlayMode/JourneyR3ContinuousContactTests.cs'))
TEST = 'DesertRV.Tests.JourneyR3ContinuousContactTests.RealR3_ContinuousAIAndStaticControl'
SOURCE_NAME = 'tasks/desert-rv/SOURCE-STATE.json'
PREFIX = 'tasks/desert-rv/unity/'
MAX_REPORT = 8 * 1024**2
MAX_NATIVE_REPORT = 24 * 1024**2
TEST_ADDITIONS = {'Assets/DesertRV/Tests/PlayMode/JourneyR3ContinuousContactTests.cs',
    'Assets/DesertRV/Tests/PlayMode/JourneyR3ContinuousContactTests.cs.meta'}
CHANGED_FILES = frozenset({
    '.github/dispatch/desert-rv-pouncer-ground-support-2915-r2-20261011.json',
    '.github/workflows/desert-rv-pouncer-ground-support.yml',
    'tasks/desert-rv/SOURCE-STATE.json',
    'tasks/desert-rv/scripts/journey_pouncer_ground_support_probe.py',
    'tasks/desert-rv/unity/Assets/DesertRV/Tests/PouncerGround/PouncerGroundSupportTests.cs',
})


def require(ok, code):
    if not ok:
        raise ValueError('R3_NATURAL_CONTACT_' + code)


def failure_code(error):
    # Exact owned diagnostic codes only; never disclose arbitrary exception text.
    if type(error) is ValueError and re.fullmatch(r'(?:R3_NATURAL_CONTACT|R3_CONTINUOUS|POUNCER_SUPPORT_REPORT)_[A-Z0-9_]{1,96}', str(error)):
        return str(error)
    name = type(error).__name__
    allowed = {'ValueError','StrictError','FileNotFoundError','PermissionError','OSError','KeyError','TypeError','TimeoutExpired','CalledProcessError'}
    return 'R3_NATURAL_CONTACT_EXCEPTION_' + (name if name in allowed else 'OtherError').upper()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'DUPLICATE_JSON')
        result[key] = value
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: require(False, 'NONFINITE_JSON'))


def read(path, limit=MAX_REPORT):
    return parse(file_bytes(path, limit))


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, stderr=subprocess.DEVNULL)


def write_new(path, value):
    safe_path(path)
    require(not path.exists(), 'OUTPUT_EXISTS')
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    require(len(raw) <= MAX_REPORT, 'OUTPUT_LIMIT')
    with path.open('xb') as stream:
        stream.write(raw)


def output(value):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
        stream.write(value + '\n')


def validate_identity(env, event, head, parents, request, tracked, present, changed, source_sha):
    require(env.get('GITHUB_ACTIONS') == 'true' and env.get('GITHUB_REPOSITORY') == REPOSITORY and
        env.get('GITHUB_REPOSITORY_VISIBILITY') == 'public', 'REPOSITORY')
    require(env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and env.get('RUNNER_OS') == 'Linux', 'HOSTED')
    require(env.get('GITHUB_ACTOR') == env.get('GITHUB_TRIGGERING_ACTOR') == OWNER_NAME, 'OWNER')
    require(env.get('GITHUB_EVENT_NAME') == 'push' and env.get('GITHUB_REF') == REF and
        env.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/' + WORKFLOW + '@' + REF, 'WORKFLOW')
    require(re.fullmatch('[a-f0-9]{40}', head or '') and env.get('GITHUB_SHA') == head and
        parents == [BASE] and head != BASE, 'HEAD_PARENT')
    require(re.fullmatch('[1-9][0-9]*', env.get('GITHUB_RUN_ID', '')) and env.get('GITHUB_RUN_ATTEMPT') == '1', 'ATTEMPT')
    require(type(event) is dict and event.get('before') == BASE and event.get('after') == head and
        event.get('ref') == REF and all(event.get(k) is False for k in ('created','deleted','forced')), 'PUSH')
    repo = event.get('repository', {})
    require(repo.get('full_name') == REPOSITORY and repo.get('private') is False and repo.get('fork') is False and
        repo.get('default_branch') == 'main' and repo.get('owner', {}).get('login') == OWNER_NAME, 'PUBLIC_REPO')
    require(event.get('sender', {}).get('login') == OWNER_NAME and event.get('head_commit', {}).get('id') == head, 'SENDER')
    require(present is False and set(changed) == CHANGED_FILES and len(changed) == len(CHANGED_FILES) and request == tracked and 0 < len(request) <= 2048, 'REQUEST_GIT')
    value = parse(request)
    require(type(value) is dict and type(value.get('schema')) is int, 'REQUEST_SCHEMA')
    require(value == dict(schema=1, requestId=NONCE, baseCommit=BASE, sourceStateSha256=source_sha,
        producerArtifactSha256=PRODUCER['artifactSha256']), 'REQUEST')
    return value


def dispatch():
    head = git('rev-parse', 'HEAD').decode().strip()
    parents = [r.split(' ', 1)[1] for r in git('cat-file', '-p', 'HEAD').decode().split('\n\n', 1)[0].splitlines() if r.startswith('parent ')]
    present = subprocess.run(['git', 'cat-file', '-e', BASE + ':' + REQUEST], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    state = file_bytes(ROOT / SOURCE_NAME, 4 * 1024**2)
    require(state == git('show', 'HEAD:' + SOURCE_NAME), 'TRACKED_SOURCE')
    return validate_identity(os.environ, read(Path(os.environ['GITHUB_EVENT_PATH'])), head, parents,
        file_bytes(ROOT / REQUEST, 2048), git('show', 'HEAD:' + REQUEST), present,
        git('diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').decode().splitlines(), sha(state))


def api(path):
    raw = subprocess.check_output(['gh', 'api', '/repos/' + REPOSITORY + path], stderr=subprocess.DEVNULL, timeout=60)
    require(len(raw) <= 8 * 1024**2, 'API_SIZE')
    return parse(raw)


def validate_producer_api(run, artifact, jobs):
    require(run.get('id') == PRODUCER['runId'] and run.get('run_attempt') == 1 and
        run.get('head_sha') == PRODUCER['commit'] and run.get('head_branch') == 'wip/combat-feedback-20261010' and
        run.get('path') == '.github/workflows/desert-rv-tracer-shader-prepare.yml' and run.get('event') == 'push' and
        run.get('status') == 'completed' and run.get('conclusion') == 'success', 'PRODUCER_RUN')
    require(artifact.get('id') == PRODUCER['artifactId'] and artifact.get('name') == PRODUCER['artifactName'] and
        artifact.get('expired') is False and artifact.get('size_in_bytes') == PRODUCER['artifactBytes'] and
        artifact.get('digest') == 'sha256:' + PRODUCER['artifactSha256'] and
        artifact.get('workflow_run', {}).get('id') == PRODUCER['runId'] and
        artifact['workflow_run'].get('head_sha') == PRODUCER['commit'], 'PRODUCER_ARTIFACT')
    candidates = [j for j in jobs.get('jobs', []) if j.get('name') == 'prepare' and j.get('run_id') == PRODUCER['runId']]
    require(len(candidates) == 1 and candidates[0].get('status') == 'completed' and candidates[0].get('conclusion') == 'success', 'PRODUCER_JOB')
    steps = {s['name']: s.get('conclusion') for s in candidates[0].get('steps', [])}
    names = ['Native strict ' + k + ' import and actual capture' for k in generated.KINDS]
    names += ['Reuse exact strict quality gate and preserve ' + k + ' reports' for k in generated.KINDS]
    names += ['Native original FX, four scenes, integration and diagnostic scope', 'Verify actual preparation test, saved outputs and final scope pins']
    require(all(steps.get(n) == 'success' for n in names), 'PRODUCER_STEPS')


def extract(zip_path, destination):
    raw = file_bytes(zip_path, 32 * 1024**2)
    require(raw_pin(raw) == dict(sha256=PRODUCER['artifactSha256'], bytes=PRODUCER['artifactBytes']), 'ZIP_PIN')
    require(not destination.exists(), 'EXTRACT_EXISTS')
    with zipfile.ZipFile(zip_path) as archive:
        rows = archive.infolist()
        require(len(rows) <= 2048 and len(rows) == len({r.filename for r in rows}) and
            sum(r.file_size for r in rows) <= 256 * 1024**2, 'ZIP_BOUNDS')
        for row in rows:
            p = PurePosixPath(row.filename)
            require(not p.is_absolute() and p.parts and '..' not in p.parts and '\\' not in row.filename and
                p.as_posix() == row.filename.rstrip('/') and not row.flag_bits & 1 and
                stat.S_IFMT(row.external_attr >> 16) in (0, stat.S_IFREG, stat.S_IFDIR), 'ZIP_PATH')
        archive.extractall(destination)


def bundle_assets(folder, producer_source):
    require(sha(file_bytes(folder / 'generated/receipt.json')) == PRODUCER['generatedReceiptSha256'], 'RECEIPT_PIN')
    require(sha((json.dumps(producer_source, indent=2) + '\n').encode()) == PRODUCER['sourceStateSha256'], 'PRODUCER_SOURCE_FORMAT')
    assets = {}; refs = []
    for kind in generated.KINDS:
        part = folder / kind; receipt = read(part / 'receipt.json'); expected = STRICT_PINS[kind]
        verify_staged_inventory(part, receipt['files'], expected)
        require(receipt['status'] == 'STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED' and receipt['approved'] is False and
            receipt['kind'] == kind and receipt['importCommit'] == PRODUCER['commit'] and
            receipt['importRunUrl'] == RUN_URL and receipt['nativeCases'] == 26, 'STRICT_IDENTITY')
        for row in receipt['files']:
            if row['path'] == 'CandidateArtImports.meta' or row['path'].startswith('CandidateArtImports/'):
                name = 'Assets/DesertRV/' + row['path']; raw = file_bytes(part / row['path'])
                require(name not in assets or assets[name] == raw, 'ASSET_COLLISION')
                assets[name] = raw
        refs.append(dict(kind=kind, path=kind + '/receipt.json', sha256=expected,
            nativeXmlSha256=receipt['nativeXmlSha256'], nativeCases=26))
    require(len(assets) == 83, 'STRICT_ASSET_COUNT')
    receipt = read(folder / 'generated/receipt.json')
    verify_staged_inventory(folder / 'generated', receipt['files'], PRODUCER['generatedReceiptSha256'])
    require(receipt['schema'] == generated.SCHEMA and receipt['status'] == 'GENERATED_JOURNEY_SAVED_UNREVIEWED' and
        receipt['sourceCommit'] == PRODUCER['commit'] and receipt['importRunUrl'] == RUN_URL and receipt['runAttempt'] == 1 and
        receipt['unityVersion'] == generated.UNITY and receipt['sourceStateSha256'] == PRODUCER['sourceStateSha256'] and
        receipt['strictReceipts'] == refs and all(receipt[k] is False for k in ('approved','visualReviewed','gameplayReviewed','audioAuditioned','scopeReusable')), 'GENERATED_IDENTITY')
    for row in receipt['files']:
        if row['path'].startswith('Assets/'):
            require(row['path'] not in assets, 'ASSET_COLLISION')
            assets[row['path']] = file_bytes(folder / 'generated' / row['path'])
    require(len(assets) == 158, 'ASSET_COUNT')
    require(receipt['nativeManifestPath'] == 'native-authored-assets.json', 'NATIVE_PATH')
    native_raw = file_bytes(folder / 'generated/native-authored-assets.json')
    require(sha(native_raw) == receipt['nativeManifestSha256'], 'NATIVE_PIN')
    native = parse(native_raw)
    require(set(native) == generated.NATIVE_KEYS and native['schema'] == 3 and
        native['status'] == 'ACTUAL_NATIVE_JOURNEY_ASSETS_UNREVIEWED' and native['sourceCommit'] == PRODUCER['commit'] and
        native['unityVersion'] == generated.UNITY and native['importRunUrl'] == RUN_URL and native['approved'] is False, 'NATIVE_IDENTITY')
    require(receipt['dependencies'] == [dict(row, owner=next(r['owner'] for r in receipt['dependencies'] if r['path'] == row['path'])) for row in native['dependencies']], 'PREPARED_CLOSURE')
    known = {'preparation.json'} | {kind + '/' + row['path'] for kind in (*generated.KINDS, 'generated')
        for row in read(folder / kind / 'receipt.json')['files']} | {kind + '/receipt.json' for kind in (*generated.KINDS, 'generated')}
    # Three bounded producer keyboard reports are inert evidence, never project input or public output here.
    known.update('keyboard-look/' + n for n in ('isolation-report.json','native-report.json','source-report.json'))
    known.add('region-hud/native-report.json')
    known.add('combat-feedback/native-report.json')
    require({p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()} == known and
        all(not p.is_symlink() for p in folder.rglob('*')), 'BUNDLE_INVENTORY')
    summary = read(folder / 'preparation.json')
    require(summary['sourceCommit'] == PRODUCER['commit'] and summary['status'] == 'PREPARED_EDITOR_SCOPE_UNREVIEWED' and
        summary['generatedExport']['sha256'] == PRODUCER['generatedReceiptSha256'] and
        summary['nativeXmlSha256'] == receipt['nativeAuthoringXmlSha256'], 'PREPARED_SUMMARY')
    return assets, receipt


def consumer_input(assets, receipt, before, after, consumer_commit):
    require(re.fullmatch('[a-f0-9]{40}', consumer_commit or '') and consumer_commit not in {BASE, PRODUCER['commit']}, 'CONSUMER_COMMIT')
    old = {r['path'][len(PREFIX):]: r for r in before['files'] + before['restoredFiles'] if r['path'].startswith(PREFIX)}
    current = {r['path'][len(PREFIX):]: r for r in after['files'] + after['restoredFiles'] if r['path'].startswith(PREFIX)}
    delta = {name for name in set(old) | set(current) if old.get(name) != current.get(name)}
    require(delta == UNITY_CHANGES and set(old) <= set(current), 'EXPLICIT_PRODUCTION_SOURCE_OVERLAY')
    overlay = [dict(path=name, before=None if name not in old else dict(sha256=old[name]['sha256'], bytes=old[name]['size']),
        after=dict(sha256=current[name]['sha256'], bytes=current[name]['size'])) for name in sorted(delta)]
    controls = receipt['packageControls']
    require(len(controls) == 3 and {r['path'] for r in controls} == {'Packages/manifest.json','Packages/packages-lock.json','ProjectSettings/ProjectVersion.txt'}, 'PACKAGE_CONTROLS')
    for row in controls:
        require(set(row) == {'path','sha256','bytes'} and raw_pin(file_bytes(PROJECT / row['path'])) ==
            {k: row[k] for k in ('sha256','bytes')}, 'PACKAGE_CONTROL_BYTES')
    lock = read(PROJECT / 'Packages/packages-lock.json')['dependencies']
    seen = set(); rows = []; changes = []; counts = {}
    for original in receipt['dependencies']:
        require(set(original) == generated.DEPENDENCY_KEYS | {'owner'}, 'DEPENDENCY_SCHEMA')
        row = {k: original[k] for k in generated.DEPENDENCY_KEYS}; name = row['path']; owner = original['owner']
        require(type(name) is str and generated.rel(name) and name not in seen and type(row['bytes']) is int and
            0 < row['bytes'] <= 128 * 1024**2 and generated.digest(row['sha256']), 'DEPENDENCY_PATH')
        seen.add(name); counts[owner] = counts.get(owner, 0) + 1
        if row['kind'] == 'package':
            package = row['packageName']; item = lock.get(package, {})
            require(owner == 'official-package' and re.fullmatch(r'com\.unity\.[a-z0-9.-]+', package) and
                name.startswith('Packages/' + package + '/') and row['packageVersion'] == item.get('version') and
                (item.get('source') == 'builtin' or item.get('source') == 'registry' and item.get('url') == 'https://packages.unity.com'), 'OFFICIAL_PACKAGE')
        else:
            require(row['kind'] == 'asset' and name.startswith('Assets/') and row['packageName'] == row['packageVersion'] == '', 'ASSET_DEPENDENCY')
            if owner == 'source':
                require(name in old and name in current and old[name]['sha256'] == row['sha256'] and old[name]['size'] == row['bytes'], 'PRODUCER_SOURCE_DEPENDENCY')
                actual = raw_pin(file_bytes(PROJECT / name))
                require(actual == dict(sha256=current[name]['sha256'], bytes=current[name]['size']), 'CONSUMER_SOURCE_DEPENDENCY')
                if actual != dict(sha256=row['sha256'], bytes=row['bytes']):
                    require(name in UNITY_CHANGES, 'UNDECLARED_SOURCE_DEPENDENCY')
                    changes.append(dict(path=name, before=dict(sha256=row['sha256'], bytes=row['bytes']), after=actual))
                    row.update(actual)
            else:
                require(owner in {'strict','generated'} and name in assets and name not in current and
                    raw_pin(assets[name]) == dict(sha256=row['sha256'], bytes=row['bytes']), 'ARTIFACT_DEPENDENCY')
                require((owner == 'strict') == name.startswith('Assets/DesertRV/CandidateArtImports'), 'ASSET_OWNER')
        rows.append(row)
    require(counts == {'source':636,'strict':64,'generated':72,'official-package':24} and
        len(rows) == 796, 'EXACT_PRODUCER_CLOSURE_COUNTS')
    for name in NEW_DEPENDENCIES:
        require(name in current and name not in old and name not in seen and name in UNITY_CHANGES, 'NEW_SOURCE_DEPENDENCY')
        pin = raw_pin(file_bytes(PROJECT / name))
        require(pin == dict(sha256=current[name]['sha256'], bytes=current[name]['size']), 'NEW_SOURCE_PIN')
        rows.append(dict(path=name, kind='asset', packageName='', packageVersion='', **pin)); seen.add(name)
        changes.append(dict(path=name, before=None, after=pin))
    require(all((n[:-5] if n.endswith('.meta') else n + '.meta') in seen for n in seen), 'DEPENDENCY_META_PAIR')
    return dict(schema=1, status='VERIFIED_2915_PREPARED_WITH_EXPLICIT_SOURCE_AND_SCENE_OVERLAY_NOT_APPROVED',
        producerCommit=PRODUCER['commit'], producerRunId=str(PRODUCER['runId']),
        producerArtifactSha256=PRODUCER['artifactSha256'], consumerCommit=consumer_commit, currentProductionCommit=consumer_commit,
        productionSourceOverlay=overlay, dependencies=sorted(rows, key=lambda r:r['path']), dependencyChanges=sorted(changes, key=lambda r:r['path']))


def owner_identity():
    return dict(consumerCommit=os.environ['GITHUB_SHA'], runId=os.environ['GITHUB_RUN_ID'], runAttempt=os.environ['GITHUB_RUN_ATTEMPT'])


def write_input(relative, value):
    write_new(COPY / relative, value)
    path = (COPY / relative).with_suffix('.sha256')
    safe_path(path); require(not path.exists(), 'INPUT_SIDECAR_EXISTS')
    with path.open('x') as stream: stream.write(sha(file_bytes(COPY / relative)) + '\n')


def pins_for(paths, union):
    return [dict(path=name, sha256=union[name]['sha256']) for path in paths for name in (path,path+'.meta')]


def scene_rows(union, paths=SCENES):
    return [dict(path=name, sha256=union[name]['sha256'], metaSha256=union[name+'.meta']['sha256']) for name in paths]


def author_input(after, assets):
    union = {r['path'][len(PREFIX):]: dict(sha256=r['sha256'],bytes=r['size']) for r in after['files']+after['restoredFiles'] if r['path'].startswith(PREFIX)}
    union.update({name:raw_pin(raw) for name,raw in assets.items()})
    return dict(schema=1,status='PINNED_POUNCER_SUPPORT_AUTHOR_INPUT',sourceCommit=os.environ['GITHUB_SHA'],
        producerGeneratedReceiptSha256=PRODUCER['generatedReceiptSha256'],sourcePins=pins_for(AUTHOR_SOURCES,union),scenes=scene_rows(union))


def create_copy(after, assets, expectation):
    safe_path(COPY); safe_path(OWNER)
    require(not COPY.exists() and not OWNER.exists(), 'COPY_EXISTS')
    rows = {r['path'][len(PREFIX):]: dict(sha256=r['sha256'], bytes=r['size']) for r in after['files'] + after['restoredFiles'] if r['path'].startswith(PREFIX)}
    require(protected_inventory(PROJECT)[0] == rows and not set(rows) & set(assets), 'SOURCE_UNION')
    union = {**rows, **{n:raw_pin(raw) for n,raw in assets.items()}}
    COPY.mkdir(mode=0o700); info = COPY.stat()
    marker = dict(**owner_identity(), token=uuid.uuid4().hex)
    write_new(COPY / MARKER, marker)
    write_new(OWNER, dict(schema=1, **marker, device=info.st_dev, inode=info.st_ino,
        sourceStateSha256=sha(file_bytes(ROOT / SOURCE_NAME)), union=union, inputSha256=sha((json.dumps(expectation, indent=2) + '\n').encode())))
    output('copy_created=true')
    for name in sorted(union):
        target = COPY / name; target.parent.mkdir(parents=True, exist_ok=True)
        raw = assets[name] if name in assets else file_bytes(PROJECT / name)
        require(raw_pin(raw) == union[name], 'COPY_SOURCE_CHANGED')
        with target.open('xb') as stream: stream.write(raw)
    require(protected_inventory(COPY)[0] == union, 'COPY_UNION')
    write_input(AUTHOR_INPUT, expectation)
    source.verify_source_state()
    output('copy_ready=true')


def stage():
    source.guard()
    require(not PRIVATE.exists() and not OWNER.exists() and not COPY.exists() and not EXPORT.exists(), 'FRESH_STAGE')
    PRIVATE.mkdir(mode=0o700)
    repo = api(''); require(repo.get('private') is False and repo.get('fork') is False, 'PRODUCER_PUBLIC')
    run = api('/actions/runs/' + str(PRODUCER['runId']))
    artifact = api('/actions/artifacts/' + str(PRODUCER['artifactId']))
    jobs = api('/actions/runs/' + str(PRODUCER['runId']) + '/attempts/1/jobs?per_page=100')
    validate_producer_api(run, artifact, jobs)
    for name, value in (('run',run),('artifact',artifact),('jobs',jobs)):
        write_new(PRIVATE / (name + '.json'), value)
    fetched = api('/contents/' + SOURCE_NAME + '?ref=' + PRODUCER['commit'])
    require(fetched.get('type') == 'file' and fetched.get('encoding') == 'base64', 'PRODUCER_SOURCE_RESPONSE')
    raw = base64.b64decode(fetched['content']); require(sha(raw) == PRODUCER['sourceStateSha256'], 'PRODUCER_SOURCE_PIN')
    (PRIVATE / 'producer-SOURCE-STATE.json').write_bytes(raw); before = parse(raw)
    zip_path = PRIVATE / 'prepared-input.zip'
    with zip_path.open('xb') as stream:
        subprocess.run(['gh','api','/repos/' + REPOSITORY + '/actions/artifacts/' + str(PRODUCER['artifactId']) + '/zip'],
            stdout=stream, stderr=subprocess.DEVNULL, check=True, timeout=180)
    extract(zip_path, PRIVATE / 'prepared-input')
    assets, receipt = bundle_assets(PRIVATE / 'prepared-input', before)
    after = source.verify_source_state()
    expectation = consumer_input(assets, receipt, before, after, os.environ['GITHUB_SHA'])
    write_new(PRIVATE / 'consumer-template.json', expectation)
    create_copy(after, assets, author_input(after, assets))


def load_owner():
    safe_path(COPY); safe_path(OWNER)
    value = read(OWNER)
    require(set(value) == {'schema','consumerCommit','runId','runAttempt','token','device','inode','sourceStateSha256','union','inputSha256'} and
        type(value['union']) is dict and 1 <= len(value['union']) <= 4096 and
        all(type(value[k]) is str and re.fullmatch('[a-f0-9]{64}', value[k]) for k in ('sourceStateSha256','inputSha256')), 'OWNER_SCHEMA')
    for name, pin in value['union'].items():
        require(type(name) is str and generated.rel(name) and name.startswith(('Assets/','Packages/','ProjectSettings/')) and
            type(pin) is dict and set(pin) == {'sha256','bytes'} and type(pin['sha256']) is str and
            re.fullmatch('[a-f0-9]{64}', pin['sha256']) and type(pin['bytes']) is int and 0 <= pin['bytes'] <= 128*1024**2, 'OWNER_UNION')
    require(value.get('schema') == 1 and all(value.get(k) == v for k,v in owner_identity().items()) and
        re.fullmatch('[a-f0-9]{32}', value.get('token','')), 'OWNER_IDENTITY')
    info = COPY.lstat(); original = PROJECT.stat()
    require(stat.S_ISDIR(info.st_mode) and (info.st_dev,info.st_ino) == (value['device'],value['inode']) and
        (info.st_dev,info.st_ino) != (original.st_dev,original.st_ino), 'OWNER_INODE')
    require(read(COPY / MARKER) == dict(**owner_identity(),token=value['token']), 'OWNER_MARKER')
    return value


def derive_expectation(owner):
    template = read(PRIVATE / 'consumer-template.json')
    scenes = [dict(path=name,beforeSha256=owner['union'][name]['sha256'],afterSha256=sha(file_bytes(COPY/name))) for name in SCENES]
    new_pins = {name:raw_pin(file_bytes(COPY/name)) for name in SCENES}
    rows = []; changes = list(template['dependencyChanges'])
    for original in template['dependencies']:
        row = dict(original); name = row['path']
        if name in SCENES:
            before = dict(sha256=row['sha256'],bytes=row['bytes'])
            require(before == owner['union'][name], 'DERIVED_BEFORE_PIN')
            row.update(new_pins[name]); changes.append(dict(path=name,before=before,after=new_pins[name]))
        rows.append(row)
    require(len(rows)==798 and len({r['path'] for r in rows})==798 and all(n in {r['path'] for r in rows} for n in SCENES), 'DERIVED_CLOSURE')
    template.update(dependencies=rows,dependencyChanges=sorted(changes,key=lambda r:r['path']))
    return template, scenes, new_pins


def seal_derived():
    from journey_pouncer_support_reports import verify_author_report
    dispatch(); source.verify_source_state(); owner = load_owner()
    require(not SEALED.exists() and not DERIVED.exists(), 'DERIVED_EXISTS')
    require(sha(file_bytes(COPY/AUTHOR_INPUT))==owner['inputSha256'] and
        file_bytes((COPY/AUTHOR_INPUT).with_suffix('.sha256'),128).decode().strip()==owner['inputSha256'], 'AUTHOR_INPUT_CHANGED')
    xml = inspect_xml(AUTHOR_ARTIFACTS, (AUTHOR_TEST,*GENERIC_TESTS))
    require(xml['result']=='Passed' and os.environ.get('AUTHOR_OUTCOME')=='success', 'AUTHOR_NATIVE_FAILED')
    changes, settings = inspect_isolated_union(owner)
    require([r['path'] for r in changes]==sorted(SCENES) and all(r['before'] and r['after'] for r in changes), 'EXACT_DERIVED_SCENE_CHANGES')
    expectation, scenes, new_pins = derive_expectation(owner)
    raw = file_bytes(COPY/AUTHOR_RAW,1024**2)
    require(verify_author_report(parse(raw),dict(sourceCommit=os.environ['GITHUB_SHA'],unityVersion=generated.UNITY),
        owner['inputSha256'],expectation['dependencies'],scenes,complete=True), 'AUTHOR_RECEIPT_INCOMPLETE')
    receipt = dict(schema=1,status='VERIFIED_CONSUMER_DERIVED_SCENES_NOT_APPROVED',approved=False,
        producer=PRODUCER,consumerCommit=os.environ['GITHUB_SHA'],authorInputSha256=owner['inputSha256'],
        authorReport=raw_pin(raw),authorXmlSha256=xml['sha256'],scenes=changes,
        productionSourceOverlay=expectation['productionSourceOverlay'],dependencyChanges=expectation['dependencyChanges'])
    write_new(DERIVED,receipt); derived_sha = sha(file_bytes(DERIVED))
    expectation['derivedReceiptSha256']=derived_sha
    union = dict(owner['union']); union.update(new_pins)
    focused = dict(schema=1,status='PINNED_POUNCER_SUPPORT_FOCUSED_INPUT',sourceCommit=os.environ['GITHUB_SHA'],
        producerCommit=PRODUCER['commit'],producerGeneratedReceiptSha256=PRODUCER['generatedReceiptSha256'],
        derivedReceiptSha256=derived_sha,sourcePins=pins_for(FOCUSED_SOURCES,union),scenes=scene_rows(union,(BOOTSTRAP,SCENES[-1])))
    write_input(INPUT_REL,expectation); write_input(FOCUSED_INPUT,focused)
    inputs = {name:sha(file_bytes(COPY/name)) for name in (AUTHOR_INPUT,INPUT_REL,FOCUSED_INPUT)}
    write_new(SEALED,dict(schema=1,**owner_identity(),ownerSha256=sha(file_bytes(OWNER)),derivedReceiptSha256=derived_sha,scenePins=new_pins,inputs=inputs))
    output('derived_ready=true')


def active_owner(owner):
    sealed = read(SEALED)
    require(set(sealed)=={'schema','consumerCommit','runId','runAttempt','ownerSha256','derivedReceiptSha256','scenePins','inputs'} and
        sealed['schema']==1 and all(sealed.get(k)==v for k,v in owner_identity().items()) and
        sealed['ownerSha256']==sha(file_bytes(OWNER)) and sealed['derivedReceiptSha256']==sha(file_bytes(DERIVED)), 'DERIVED_OWNER')
    require(type(sealed['scenePins']) is dict and set(sealed['scenePins'])==set(SCENES) and
        type(sealed['inputs']) is dict and set(sealed['inputs'])=={AUTHOR_INPUT,INPUT_REL,FOCUSED_INPUT}, 'DERIVED_OWNER_KEYS')
    for pin in sealed['scenePins'].values():
        require(type(pin) is dict and set(pin)=={'sha256','bytes'} and generated.digest(pin['sha256']) and type(pin['bytes']) is int and 0<pin['bytes']<=128*1024**2,'DERIVED_SCENE_PIN')
    for name,digest in sealed['inputs'].items():
        require(generated.digest(digest) and sha(file_bytes(COPY/name))==digest and
            file_bytes((COPY/name).with_suffix('.sha256'),128).decode().strip()==digest,'DERIVED_INPUT_CHANGED')
    require(sealed['inputs'][AUTHOR_INPUT]==owner['inputSha256'],'DERIVED_AUTHOR_INPUT')
    return dict(owner,union={**owner['union'],**sealed['scenePins']},inputSha256=sealed['inputs'][INPUT_REL]),sealed


def bounded_xml_failure(case):
    failures = list(case.iter('failure'))
    require(len(failures) <= 4, 'XML_FAILURE_COUNT')
    if not failures:
        return None
    # Raw NUnit message/stack can contain credentials, absolute workspace paths,
    # or private exception text. Export their hashes and fixed classifications only.
    messages = '\n'.join(''.join(n.itertext()) for f in failures for n in f.findall('message'))
    stacks = '\n'.join(''.join(n.itertext()) for f in failures for n in f.findall('stack-trace'))
    require(len(messages.encode()) + len(stacks.encode()) <= 128 * 1024, 'XML_FAILURE_LIMIT')
    exceptions = ('NullReferenceException', 'MissingMethodException', 'MissingFieldException',
        'TypeLoadException', 'TargetInvocationException', 'AssertionException', 'FileNotFoundException',
        'ArgumentException', 'InvalidOperationException', 'TimeoutException', 'IndexOutOfRangeException',
        'KeyNotFoundException', 'NotSupportedException', 'UnhandledLogMessageException')
    codes = ('ACTUAL_CAPSULE_SHAPE', 'CLEANUP_OR_SOURCE_MUTATION', 'DELTA_BOUND',
        'DEPENDENCY_BYTES_DIFFER', 'DIRECTOR_OWNER', 'EXACTLY_ONE_OBSERVED_FRAME_PER_YIELD',
        'FIRST_WAVE_TWO_POUNCERS', 'FOREIGN_COLLIDER', 'FOREIGN_DIRECTOR', 'OBSERVER_ORDER',
        'PIN_MISSING', 'PRODUCTION_BIND_R3', 'SOURCE_ALREADY_LOADED', 'POUNCER_PAW_CONTACT_FAILED')
    frame = None
    for line in stacks.splitlines():
        match = re.match(r'^\s*(?:at )?(DesertRV\.[A-Za-z0-9_.+<>`:]{1,220})\s*\(', line)
        if not match:
            continue
        frame = dict(method=match[1].replace(':', '.'), sourceFile=None, line=None)
        for name in SNAPSHOT_SOURCES:
            location = re.search(r'(?:/|\\)' + re.escape(Path(name).name) + r':(?:line )?([1-9][0-9]{0,5})(?:\D|$)', line)
            if location:
                frame.update(sourceFile=name, line=int(location[1]))
                break
        break
    return dict(messageSha256=sha(messages.encode()), stackSha256=sha(stacks.encode()),
        exceptionClasses=[name for name in exceptions if re.search(r'\b' + name + r'\b', messages + '\n' + stacks)],
        assertionCodes=[code for code in codes if re.search(r'\b' + code + r'\b', messages)],
        firstProjectStackFrame=frame)


def inspect_xml(folder=None, expected=None):
    folder = ARTIFACTS if folder is None else folder
    expected = (TEST,) if expected is None else tuple(expected)
    require(0<len(expected)<=32 and len(set(expected))==len(expected),'XML_EXPECTED_CASES')
    safe_path(folder)
    paths = list(folder.rglob('*.xml'))
    require(len(paths) == 1, 'XML_COUNT')
    raw = file_bytes(paths[0], 1024**2)
    require(b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper(), 'XML_DECLARATION')
    root = ET.fromstring(raw); cases = list(root.iter('test-case'))
    require(root.tag == 'test-run' and len(cases) == len(expected) and
        sorted(c.get('fullname','') for c in cases)==sorted(expected) and
        root.get('total') == str(len(expected)) and root.get('skipped') == root.get('inconclusive') == '0', 'XML_EXACT_CASE')
    require(all(c.get('result') in {'Passed','Failed'} for c in cases),'XML_RESULT')
    passed = sum(c.get('result')=='Passed' for c in cases); failed=len(cases)-passed
    result = 'Failed' if failed else 'Passed'
    require(root.get('passed')==str(passed) and root.get('failed')==str(failed) and
        root.get('result') in ({'Passed'} if not failed else {'Failed','Failed(Child)'}),'XML_RESULT')
    rows = [dict(fullname=c.get('fullname'),result=c.get('result'),failure=bounded_xml_failure(c) if c.get('result')=='Failed' else None) for c in sorted(cases,key=lambda c:c.get('fullname'))]
    if len(rows)==1: return dict(sha256=sha(raw),**rows[0])
    return dict(sha256=sha(raw),result=result,cases=rows)


def differences(expected, actual):
    rows = []
    for name in sorted(set(expected) | set(actual)):
        if expected.get(name) != actual.get(name):
            require(type(name) is str and re.fullmatch(r'(?:Assets|Packages|ProjectSettings)/[A-Za-z0-9_./ -]{1,480}', name) and
                all(p not in ('','.','..') for p in name.split('/')), 'DIFF_PATH')
            rows.append(dict(path=name, before=expected.get(name), after=actual.get(name)))
    require(len(rows) <= 4096, 'DIFF_LIMIT')
    return rows


def inspect_isolated_union(owner):
    actual, directories = protected_inventory(COPY)
    expected_directories = {'Assets', 'Packages', 'ProjectSettings'}
    for name in owner['union']:
        expected_directories.update(p.as_posix() for p in PurePosixPath(name).parents if p.as_posix() != '.')
    require(directories == expected_directories, 'COPY_DIRECTORIES')
    for path in COPY.iterdir():
        safe_path(path)
        if path.name in {'Library','Temp','Logs','obj','UserSettings','JourneyEvidence'}:
            require(path.is_dir(), 'COPY_OPERATIONAL_TYPE')
        else:
            require(path.name in {'Assets','Packages','ProjectSettings',MARKER}, 'COPY_UNEXPECTED_ROOT')
    changes = differences({k:v for k,v in owner['union'].items() if k != SETTINGS},
        {k:v for k,v in actual.items() if k != SETTINGS})
    before = file_bytes(PROJECT / SETTINGS, 65536)
    require(raw_pin(before) == owner['union'][SETTINGS], 'FORMAL_SETTINGS_CHANGED')
    after = file_bytes(COPY / SETTINGS, 65536)
    allowed_empty = []
    diff = settings_diff(before, after, allowed_empty)
    if diff:
        require(apply_settings_diff(before, diff) == after, 'SETTINGS_RECONSTRUCTION')
    return changes, dict(status='COMPLETE_DIFF' if diff else 'UNCHANGED', before=raw_pin(before),
        after=raw_pin(after), diff=diff, allowedEmptySensitiveFields=allowed_empty)


def finish():
    value = dict(schema=1, status='INCOMPLETE_NOT_GAMEPLAY_ACCEPTANCE', **owner_identity(),
        currentProductionCommit=os.environ['GITHUB_SHA'], consumerParentCommit=BASE, producer=PRODUCER,
        approved=False, gameplayReviewed=False, scopeReusable=False,
        nativeOutcome=os.environ.get('NATIVE_OUTCOME','unknown'), sourceUnchanged=False,
        isolatedInputsVerified=False, inputUnchanged=False, xml=None, nativeReport=None,
        nativeSummary=None, nativeReportRejection=None, nativeRedactedReport=None, settings=None, changes=[], sourceSnapshots=[], checks=[],
        authorOutcome=os.environ.get('AUTHOR_OUTCOME','unknown'),authorXml=None,nativeAuthorReport=None,nativeFocusedReport=None,
        authorReportComplete=False,focusedReportComplete=False,derivedScenesSealed=False,derivedReceipt=None)
    require(all(value[k] in {'success','failure','cancelled','skipped','unknown'} for k in ('nativeOutcome','authorOutcome')), 'OUTCOME')
    safe_path(EXPORT); require(not EXPORT.exists(), 'EXPORT_EXISTS')
    EXPORT.mkdir(mode=0o700)
    owner = None; original_owner = None; sealed = None
    try:
        original_owner = owner = load_owner()
        if SEALED.exists():
            owner,sealed = active_owner(owner); value['derivedScenesSealed']=True
    except Exception as error:
        value['checks'].extend(('OWNED_COPY_UNAVAILABLE', failure_code(error)))
    try:
        dispatch(); source.verify_source_state()
        if owner is not None:
            require(sha(file_bytes(ROOT / SOURCE_NAME)) == owner['sourceStateSha256'], 'SOURCE_STATE_CHANGED')
        git('diff','--quiet','--exit-code'); git('diff','--cached','--quiet','--exit-code')
        value['sourceUnchanged'] = True
    except Exception as error:
        value['checks'].extend(('FORMAL_SOURCE_INVARIANCE_FAILED', failure_code(error)))
    if owner is not None:
        try:
            value['changes'], value['settings'] = inspect_isolated_union(owner)
            value['isolatedInputsVerified'] = not value['changes']
        except Exception as error:
            value['checks'].extend(('ISOLATED_UNION_OR_SETTINGS_REJECTED', failure_code(error)))
        try:
            input_name = INPUT_REL if sealed is not None else AUTHOR_INPUT
            require(sha(file_bytes(COPY / input_name)) == owner['inputSha256'] and
                file_bytes((COPY / input_name).with_suffix('.sha256'),128).decode().strip() == owner['inputSha256'], 'INPUT_CHANGED')
            value['inputUnchanged'] = True
        except Exception as error:
            value['checks'].extend(('CONSUMER_INPUT_CHANGED', failure_code(error)))
    try:
        value['xml'] = inspect_xml(ARTIFACTS,(FOCUSED_TEST,TEST))
    except Exception as error:
        value['checks'].extend(('EXACT_PLAYMODE_CASES_XML_UNAVAILABLE', failure_code(error)))
    try:
        value['authorXml']=inspect_xml(AUTHOR_ARTIFACTS,(AUTHOR_TEST,*GENERIC_TESTS))
    except Exception as error:
        value['checks'].extend(('EXACT_AUTHOR_CASES_XML_UNAVAILABLE',failure_code(error)))
    if original_owner is not None:
        try:
            from journey_pouncer_support_reports import verify_author_report
            expectation,scenes,_ = derive_expectation(original_owner)
            raw = file_bytes(COPY/AUTHOR_RAW,1024**2)
            value['authorReportComplete']=verify_author_report(parse(raw),dict(sourceCommit=os.environ['GITHUB_SHA'],unityVersion=generated.UNITY),
                original_owner['inputSha256'],expectation['dependencies'],scenes,complete=False)
            value['nativeAuthorReport']=dict(path='native-authoring.json',**raw_pin(raw))
            with (EXPORT/'native-authoring.json').open('xb') as stream: stream.write(raw)
        except Exception as error:
            value['checks'].extend(('SAFE_AUTHOR_REPORT_UNAVAILABLE',failure_code(error)))
    if sealed is not None and value['inputUnchanged']:
        try:
            from journey_pouncer_support_reports import verify_focused_report
            raw=file_bytes(COPY/FOCUSED_RAW,65536)
            value['focusedReportComplete']=verify_focused_report(parse(raw),dict(sourceCommit=os.environ['GITHUB_SHA'],unityVersion=generated.UNITY,
                derivedReceiptSha256=sealed['derivedReceiptSha256'],sourcePinCount=len(FOCUSED_SOURCES)*2),sealed['inputs'][FOCUSED_INPUT],complete=False)
            value['nativeFocusedReport']=dict(path='native-focused-support.json',**raw_pin(raw))
            with (EXPORT/'native-focused-support.json').open('xb') as stream: stream.write(raw)
        except Exception as error:
            value['checks'].extend(('SAFE_FOCUSED_REPORT_UNAVAILABLE',failure_code(error)))
    if owner is not None and sealed is not None and value['inputUnchanged']:
        raw = None
        try:
            from journey_r3_continuous_contact_report import verify_native_report
            raw = file_bytes(COPY / RAW_REL, MAX_NATIVE_REPORT)
            native = parse(raw)
            pins = {name: row['sha256'] for name,row in owner['union'].items()}
            pins[INPUT_REL] = owner['inputSha256']
            pins[INPUT_REL.replace('.json','.sha256')] = sha(file_bytes((COPY / INPUT_REL).with_suffix('.sha256')))
            summary = verify_native_report(native, read(COPY / INPUT_REL), owner['inputSha256'], pins)
            value['nativeSummary'] = summary
            value['nativeReport'] = dict(path='native-r3-continuous-contact.json', **raw_pin(raw))
            # Keep the validated original bytes, never turn a host fixture into native evidence.
            with (EXPORT / 'native-r3-continuous-contact.json').open('xb') as stream: stream.write(raw)
        except Exception as error:
            code = failure_code(error)
            value['nativeReportRejection'] = dict(code=code)
            location = getattr(error, 'report_location', None)
            digest = getattr(error, 'value_sha256', None)
            if (type(location) is str and re.fullmatch(r'\$(?:\.[A-Za-z][A-Za-z0-9_]*|\.[<]unknown[>]|\[[0-9]{1,4}\]){0,32}', location) and
                    type(digest) is str and re.fullmatch('[a-f0-9]{64}', digest)):
                value['nativeReportRejection'].update(location=location, valueSha256=digest)
            value['checks'].extend(('BOUNDED_ORIGINAL_NATIVE_REPORT_UNAVAILABLE', code))
            if raw is not None and value['nativeReport'] is None:
                try:
                    from journey_r3_continuous_contact_report import redact_native_report
                    redacted = redact_native_report(raw, code, value['nativeOutcome']=='failure' or
                        value['xml'] is not None and value['xml']['result']=='Failed')
                    name = 'native-r3-continuous-contact-redacted.json'
                    with (EXPORT / name).open('xb') as stream: stream.write(redacted)
                    value['nativeRedactedReport'] = dict(path=name,mode='FAILED_REDACTED',**raw_pin(redacted))
                except Exception as projection_error:
                    value['checks'].extend(('BOUNDED_REDACTED_NATIVE_REPORT_UNAVAILABLE',failure_code(projection_error)))
    snapshots = [
        ('producer-SOURCE-STATE.json', PRIVATE / 'producer-SOURCE-STATE.json', PRODUCER['sourceStateSha256']),
        ('producer-generated-receipt.json', PRIVATE / 'prepared-input/generated/receipt.json', PRODUCER['generatedReceiptSha256']),
    ]
    if owner is not None:
        snapshots += [
            ('consumer-SOURCE-STATE.json', ROOT / SOURCE_NAME, owner['sourceStateSha256']),
            ('author-input.json',COPY/AUTHOR_INPUT,original_owner['inputSha256']),
        ]
        if sealed is not None:
            snapshots += [('consumer-input.json',COPY/INPUT_REL,owner['inputSha256']),
                ('focused-input.json',COPY/FOCUSED_INPUT,sealed['inputs'][FOCUSED_INPUT]),
                ('derived-scenes.json',DERIVED,sealed['derivedReceiptSha256'])]
            value['derivedReceipt']=dict(path='derived-scenes.json',**raw_pin(file_bytes(DERIVED)))
        snapshots += [('source/' + Path(name).name, COPY / name, owner['union'][name]['sha256']) for name in SNAPSHOT_SOURCES if name in owner['union']]
        if any(name not in owner['union'] for name in SNAPSHOT_SOURCES):
            value['checks'].append('REQUIRED_SOURCE_SNAPSHOT_MISSING')
    for name, path, expected in snapshots:
        try:
            raw = file_bytes(path, MAX_REPORT); require(sha(raw) == expected, 'SNAPSHOT_PIN')
            target = EXPORT / name; target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream: stream.write(raw)
            value['sourceSnapshots'].append(dict(path=name, **raw_pin(raw)))
        except Exception as error:
            value['checks'].extend(('SOURCE_SNAPSHOT_UNAVAILABLE', failure_code(error)))
    complete = (value['sourceUnchanged'] and value['isolatedInputsVerified'] and value['inputUnchanged'] and value['derivedScenesSealed'] and
        value['authorOutcome']=='success' and value['authorXml'] is not None and value['authorXml']['result']=='Passed' and
        value['authorReportComplete'] and value['focusedReportComplete'] and
        value['xml'] is not None and value['xml']['result'] == 'Passed' and value['nativeOutcome'] == 'success' and
        value['nativeSummary'] is not None and value['nativeSummary']['diagnosticComplete'] and not value['checks'])
    if complete: value['status'] = 'DIAGNOSTIC_COMPLETED_NOT_GAMEPLAY_ACCEPTANCE'
    elif value['nativeRedactedReport'] is not None:
        value['status'] = 'FAILED_REDACTED_DIAGNOSTIC_NOT_GAMEPLAY_ACCEPTANCE'
    elif value['nativeReport'] is not None:
        value['status'] = 'FAILED_OR_PARTIAL_DIAGNOSTIC_NOT_GAMEPLAY_ACCEPTANCE'
    write_new(REPORT, value)
    output('report_ready=true'); output('diagnostic_complete=' + str(complete).lower())
    return 0 if complete else 2


def cleanup():
    # Fixed owned disposable copy only. shutil.rmtree does not follow child symlinks.
    require(COPY == TASK / 'journey-pouncer-ground-support-project' and shutil.rmtree.avoids_symlink_attacks, 'CLEANUP_PATH')
    load_owner(); shutil.rmtree(COPY)
    require(not COPY.exists(), 'CLEANUP_INCOMPLETE')


def main():
    try:
        require(len(sys.argv) == 2 and sys.argv[1] in {'dispatch','stage','seal-derived','finish','cleanup'}, 'COMMAND')
        command = sys.argv[1].replace('-','_')
        if command == 'dispatch': dispatch()
        elif command == 'stage': stage()
        elif command == 'seal_derived': seal_derived()
        elif command == 'finish': return finish()
        else: cleanup()
        return 0
    except Exception as error:
        print(failure_code(error))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
