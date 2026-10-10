"""One-use PlayMode vehicle contact diagnosis of exact ed21 prepared assets; no BuildPlayer."""
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
sys.pycache_prefix = '/tmp/journey-vehicle-contact-python-' + uuid.uuid4().hex
sys.dont_write_bytecode = True
import verify_evidence as source
from journey_keyboard_look_native import file_bytes, raw_pin, safe_path, protected_inventory, settings_diff, apply_settings_diff, SETTINGS
from strict_output import verify_staged_inventory
import generated_export as generated

BASE = 'ed21b214f327b3ec439b9b3d7fec6b41a16d8a85'
PRODUCTION_BASE = BASE
BRANCH = 'journey-vehicle-contact-ed21'
REF = 'refs/heads/' + BRANCH
REPOSITORY = 'yangerstar1/task-workbench'
OWNER_NAME = 'yangerstar1'
WORKFLOW = '.github/workflows/desert-rv-vehicle-contact.yml'
REQUEST = '.github/dispatch/desert-rv-vehicle-contact-ed21-r1-20261010.json'
NONCE = 'desert-rv-vehicle-contact-ed21-r1-20261010-once'
PRODUCER = dict(commit='ed21b214f327b3ec439b9b3d7fec6b41a16d8a85', runId=38054694730,
    artifactId=11673265859, artifactName='journey-preparation-UNREVIEWED-38054694730-1',
    artifactBytes=15842817, artifactSha256='1e9f5e73417b7454f5e85e5bfa426499c93cb045e383da6467e49eca64d878b1',
    sourceStateSha256='d18bad2fed1b311a355f53a04adfdea5f97411a69a4c6d0f7df3e5c0a58414f3',
    generatedReceiptSha256='a84668b890f0b3902540072b9f33574afc839bbec61eaff66396989b2e52c02d')
RUN_URL = 'https://github.com/' + REPOSITORY + '/actions/runs/' + str(PRODUCER['runId'])
STRICT_PINS = dict(armored='53ed6372bdbcbc5b413856a66b97788051df76af2a11986e9c5539a57661c10b',
    pouncer='6e2e1a1f7c459f5666b96d8b2c19e8cffc38286b6df6e2f5b0c741a6c2486e11',
    weapon='df86b595c5075f97cc578bb3fa8713d978091d079ea68b3f1bdd53fb59e716fc')

PROJECT = TASK / 'unity'
COPY = TASK / 'journey-vehicle-contact-project'
PRIVATE = TASK / 'journey-vehicle-contact-private'
OWNER = TASK / 'journey-vehicle-contact-owner.json'
MARKER = '.journey-vehicle-contact-owner.json'
INPUT_REL = 'JourneyEvidence/VehicleContact/consumer-input.json'
RAW_REL = 'JourneyEvidence/VehicleContact/native-contact-probe.json'
ARTIFACTS = TASK / 'artifacts/journey-vehicle-contact'
EXPORT = TASK / 'journey-vehicle-contact-export'
REPORT = EXPORT / 'report.json'
SNAPSHOT_SOURCES = tuple('Assets/DesertRV/' + name for name in (
    'Runtime/JourneyMotor.cs', 'Runtime/BeastActor.cs', 'Runtime/MobileInputAdapter.cs',
    'Tests/PlayMode/JourneyVehicleContactPhysicsTests.cs'))
TEST = 'DesertRV.Tests.JourneyVehicleContactPhysicsTests.RealRV_RecordContactLockDiscriminators'
SOURCE_NAME = 'tasks/desert-rv/SOURCE-STATE.json'
PREFIX = 'tasks/desert-rv/unity/'
MAX_REPORT = 8 * 1024**2
MAX_NATIVE_REPORT = 64 * 1024**2


def require(ok, code):
    if not ok:
        raise ValueError('VEHICLE_CONTACT_' + code)


def failure_code(error):
    # Exact owned diagnostic codes only; never disclose arbitrary exception text.
    if type(error) is ValueError and re.fullmatch(r'VEHICLE_CONTACT_[A-Z0-9_]{1,96}', str(error)):
        return str(error)
    name = type(error).__name__
    allowed = {'ValueError','StrictError','FileNotFoundError','PermissionError','OSError','KeyError','TypeError','TimeoutExpired','CalledProcessError'}
    return 'VEHICLE_CONTACT_EXCEPTION_' + (name if name in allowed else 'OtherError').upper()


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
    require(present is False and REQUEST in changed and request == tracked and 0 < len(request) <= 2048, 'REQUEST_GIT')
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
    raw = subprocess.check_output(['gh', 'api', '/repos/' + REPOSITORY + path], stderr=subprocess.DEVNULL)
    require(len(raw) <= 8 * 1024**2, 'API_SIZE')
    return parse(raw)


def validate_producer_api(run, artifact, jobs):
    require(run.get('id') == PRODUCER['runId'] and run.get('run_attempt') == 1 and
        run.get('head_sha') == PRODUCER['commit'] and run.get('head_branch') == 'journey-tracer-shader-fix-6648' and
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
    require({p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()} == known and
        all(not p.is_symlink() for p in folder.rglob('*')), 'BUNDLE_INVENTORY')
    summary = read(folder / 'preparation.json')
    require(summary['sourceCommit'] == PRODUCER['commit'] and summary['status'] == 'PREPARED_EDITOR_SCOPE_UNREVIEWED' and
        summary['generatedExport']['sha256'] == PRODUCER['generatedReceiptSha256'] and
        summary['nativeXmlSha256'] == receipt['nativeAuthoringXmlSha256'], 'PREPARED_SUMMARY')
    return assets, receipt


def consumer_input(assets, receipt, before, after, consumer_commit):
    old = {r['path'][len(PREFIX):]: r for r in before['files'] + before['restoredFiles'] if r['path'].startswith(PREFIX)}
    current = {r['path'][len(PREFIX):]: r for r in after['files'] + after['restoredFiles'] if r['path'].startswith(PREFIX)}
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
                require(actual == dict(sha256=row['sha256'], bytes=row['bytes']), 'PRODUCTION_DEPENDENCY_CHANGED')
            else:
                require(owner in {'strict','generated'} and name in assets and name not in current and
                    raw_pin(assets[name]) == dict(sha256=row['sha256'], bytes=row['bytes']), 'ARTIFACT_DEPENDENCY')
                require((owner == 'strict') == name.startswith('Assets/DesertRV/CandidateArtImports'), 'ASSET_OWNER')
        rows.append(row)
    require(counts == {'source':636,'strict':64,'generated':72,'official-package':24} and
        changes == [], 'EXACT_CLOSURE_COUNTS')
    require(all((n[:-5] if n.endswith('.meta') else n + '.meta') in seen for n in seen), 'DEPENDENCY_META_PAIR')
    return dict(schema=1, status='VERIFIED_ED21_PREPARED_ASSETS_DIAGNOSTIC_CONSUMER_NOT_APPROVED',
        producerCommit=PRODUCER['commit'], producerRunId=str(PRODUCER['runId']),
        producerArtifactSha256=PRODUCER['artifactSha256'], consumerCommit=consumer_commit, currentProductionCommit=PRODUCTION_BASE,
        dependencies=sorted(rows, key=lambda r:r['path']), dependencyChanges=sorted(changes, key=lambda r:r['path']))


def owner_identity():
    return dict(consumerCommit=os.environ['GITHUB_SHA'], runId=os.environ['GITHUB_RUN_ID'], runAttempt=os.environ['GITHUB_RUN_ATTEMPT'])


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
    write_new(COPY / INPUT_REL, expectation)
    (COPY / INPUT_REL).with_suffix('.sha256').write_text(sha(file_bytes(COPY / INPUT_REL)) + '\n')
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
    create_copy(after, assets, expectation)


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


def inspect_xml():
    safe_path(ARTIFACTS)
    paths = list(ARTIFACTS.rglob('*.xml'))
    require(len(paths) == 1, 'XML_COUNT')
    raw = file_bytes(paths[0], 1024**2)
    require(b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper(), 'XML_DECLARATION')
    root = ET.fromstring(raw); cases = list(root.iter('test-case'))
    require(root.tag == 'test-run' and len(cases) == 1 and cases[0].get('fullname') == TEST and
        root.get('total') == '1' and root.get('skipped') == root.get('inconclusive') == '0', 'XML_EXACT_CASE')
    result = cases[0].get('result'); require(result in {'Passed','Failed'} and
        root.get('passed') == ('1' if result == 'Passed' else '0') and root.get('failed') == ('0' if result == 'Passed' else '1') and
        root.get('result') in ({'Passed'} if result == 'Passed' else {'Failed','Failed(Child)'}), 'XML_RESULT')
    return dict(sha256=sha(raw), fullname=TEST, result=result)


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
        currentProductionCommit=PRODUCTION_BASE, consumerParentCommit=BASE, producer=PRODUCER,
        approved=False, gameplayReviewed=False, scopeReusable=False,
        nativeOutcome=os.environ.get('NATIVE_OUTCOME','unknown'), sourceUnchanged=False,
        isolatedInputsVerified=False, inputUnchanged=False, xml=None, nativeReport=None,
        nativeSummary=None, settings=None, changes=[], sourceSnapshots=[], checks=[])
    require(value['nativeOutcome'] in {'success','failure','cancelled','skipped','unknown'}, 'OUTCOME')
    safe_path(EXPORT); require(not EXPORT.exists(), 'EXPORT_EXISTS')
    EXPORT.mkdir(mode=0o700)
    owner = None
    try:
        owner = load_owner()
    except Exception as error:
        value['checks'].extend(('OWNED_COPY_UNAVAILABLE', failure_code(error)))
    if owner is not None:
        try:
            dispatch(); source.verify_source_state()
            require(sha(file_bytes(ROOT / SOURCE_NAME)) == owner['sourceStateSha256'], 'SOURCE_STATE_CHANGED')
            git('diff','--quiet','--exit-code'); git('diff','--cached','--quiet','--exit-code')
            value['sourceUnchanged'] = True
        except Exception as error:
            value['checks'].extend(('FORMAL_SOURCE_INVARIANCE_FAILED', failure_code(error)))
        try:
            value['changes'], value['settings'] = inspect_isolated_union(owner)
            value['isolatedInputsVerified'] = not value['changes']
        except Exception as error:
            value['checks'].extend(('ISOLATED_UNION_OR_SETTINGS_REJECTED', failure_code(error)))
        try:
            require(sha(file_bytes(COPY / INPUT_REL)) == owner['inputSha256'] and
                file_bytes((COPY / INPUT_REL).with_suffix('.sha256'),128).decode().strip() == owner['inputSha256'], 'INPUT_CHANGED')
            value['inputUnchanged'] = True
        except Exception as error:
            value['checks'].extend(('CONSUMER_INPUT_CHANGED', failure_code(error)))
    try:
        value['xml'] = inspect_xml()
    except Exception as error:
        value['checks'].extend(('EXACT_ONE_CASE_XML_UNAVAILABLE', failure_code(error)))
    if owner is not None and value['inputUnchanged']:
        try:
            from journey_vehicle_contact_report import verify_native_report
            raw = file_bytes(COPY / RAW_REL, MAX_NATIVE_REPORT)
            native = parse(raw)
            pins = {name: row['sha256'] for name,row in owner['union'].items()}
            pins[INPUT_REL] = owner['inputSha256']
            pins[INPUT_REL.replace('.json','.sha256')] = sha(file_bytes((COPY / INPUT_REL).with_suffix('.sha256')))
            summary = verify_native_report(native, read(COPY / INPUT_REL), owner['inputSha256'], pins)
            value['nativeSummary'] = summary
            value['nativeReport'] = dict(path='native-contact-probe.json', **raw_pin(raw))
            # Keep the validated original bytes, never turn a host fixture into native evidence.
            with (EXPORT / 'native-contact-probe.json').open('xb') as stream: stream.write(raw)
        except Exception as error:
            value['checks'].extend(('BOUNDED_ORIGINAL_NATIVE_REPORT_UNAVAILABLE', failure_code(error)))
    snapshots = [
        ('producer-SOURCE-STATE.json', PRIVATE / 'producer-SOURCE-STATE.json', PRODUCER['sourceStateSha256']),
    ]
    if owner is not None:
        snapshots += [
            ('consumer-SOURCE-STATE.json', ROOT / SOURCE_NAME, owner['sourceStateSha256']),
            ('consumer-input.json', COPY / INPUT_REL, owner['inputSha256']),
        ]
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
    complete = (value['sourceUnchanged'] and value['isolatedInputsVerified'] and value['inputUnchanged'] and
        value['xml'] is not None and value['xml']['result'] == 'Passed' and value['nativeOutcome'] == 'success' and
        value['nativeSummary'] is not None and value['nativeSummary']['diagnosticComplete'] and not value['checks'])
    if complete: value['status'] = 'OBSERVATIONS_COMPLETE_NOT_GAMEPLAY_ACCEPTANCE'
    write_new(REPORT, value)
    output('report_ready=true'); output('diagnostic_complete=' + str(complete).lower())
    return 0 if complete else 2


def cleanup():
    # Fixed owned disposable copy only. shutil.rmtree does not follow child symlinks.
    require(COPY == TASK / 'journey-vehicle-contact-project' and shutil.rmtree.avoids_symlink_attacks, 'CLEANUP_PATH')
    load_owner(); shutil.rmtree(COPY)
    require(not COPY.exists(), 'CLEANUP_INCOMPLETE')


def main():
    try:
        require(len(sys.argv) == 2 and sys.argv[1] in {'dispatch','stage','finish','cleanup'}, 'COMMAND')
        command = sys.argv[1]
        if command == 'dispatch': dispatch()
        elif command == 'stage': stage()
        elif command == 'finish': return finish()
        else: cleanup()
        return 0
    except Exception as error:
        print(failure_code(error))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
