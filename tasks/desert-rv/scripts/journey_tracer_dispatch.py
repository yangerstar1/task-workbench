"""Single-use fresh producer and build push after exact native movement gates."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
BASE = '1019ff71443f2dbc25a0f1b5027d5b245f295b29'
BRANCH = 'journey-pouncer-ground-support-full-1019'
REF = 'refs/heads/' + BRANCH
REPOSITORY = 'yangerstar1/task-workbench'
OWNER = 'yangerstar1'
WORKFLOW = '.github/workflows/desert-rv-tracer-shader-prepare.yml'
REQUEST = '.github/dispatch/desert-rv-pouncer-ground-support-full-1019-20261011.json'
REQUEST_ID = 'desert-rv-pouncer-ground-support-full-1019-20261011-once'
SOURCE = 'tasks/desert-rv/SOURCE-STATE.json'
SELECTION = 'tasks/desert-rv/art/journey-preparation/three-strict-candidates.json'


def require(ok, code):
    if not ok:
        raise ValueError('TRACER_DISPATCH_' + code)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'DUPLICATE_KEY')
        result[key] = value
    return result


def parse(raw):
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: require(False, 'JSON_CONSTANT'))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError('TRACER_DISPATCH_BAD_JSON') from None


def parse_request(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= 2048, 'REQUEST_SIZE')
    value = parse(raw)
    require(type(value) is dict and set(value) == {
        'schema', 'requestId', 'baseCommit', 'sourceStateSha256', 'selection', 'selectionSha256', 'shortEvidence'}, 'REQUEST_KEYS')
    require(type(value['shortEvidence']) is dict and set(value['shortEvidence']) == set(SHORT) and
            all(type(value['shortEvidence'][k]) is type(v) for k,v in SHORT.items()), 'REQUEST_SHORT_TYPES')
    require(type(value['schema']) is int and value['schema'] == 1 and
            value['requestId'] == REQUEST_ID and value['baseCommit'] == BASE and
            value['selection'] == SELECTION and value['shortEvidence'] == SHORT, 'REQUEST_IDENTITY')
    require(all(isinstance(value[key], str) and re.fullmatch('[a-f0-9]{64}', value[key])
                for key in ('sourceStateSha256', 'selectionSha256')), 'REQUEST_DIGEST')
    return value


def validate(env, event, head, parents, request_raw, tracked_raw, request_in_parent,
             changed_paths, source_sha, selection_sha):
    require(env.get('GITHUB_ACTIONS') == 'true' and env.get('GITHUB_REPOSITORY') == REPOSITORY and
            env.get('GITHUB_REPOSITORY_VISIBILITY') == 'public', 'REPOSITORY')
    require(env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and env.get('RUNNER_OS') == 'Linux', 'HOSTED_RUNNER')
    require(env.get('GITHUB_ACTOR') == OWNER and env.get('GITHUB_TRIGGERING_ACTOR') == OWNER, 'ACTOR')
    require(env.get('GITHUB_EVENT_NAME') == 'push', 'EVENT')
    require(env.get('GITHUB_REF') == REF, 'BRANCH')
    require(env.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/' + WORKFLOW + '@' + REF, 'WORKFLOW')
    require(re.fullmatch('[a-f0-9]{40}', head or '') and env.get('GITHUB_SHA') == head, 'HEAD')
    require(re.fullmatch('[1-9][0-9]*', env.get('GITHUB_RUN_ID', '')) and
            env.get('GITHUB_RUN_ATTEMPT') == '1', 'REPLAY')
    require(type(event) is dict and event.get('before') == BASE and event.get('after') == head and
            event.get('ref') == REF, 'PUSH_IDENTITY')
    require(all(event.get(key) is False for key in ('created', 'deleted', 'forced')), 'PUSH_KIND')
    repository = event.get('repository', {})
    require(type(repository) is dict and repository.get('full_name') == REPOSITORY and
            repository.get('private') is False and repository.get('fork') is False and
            repository.get('default_branch') == 'main' and
            repository.get('owner', {}).get('login') == OWNER, 'PUSH_REPOSITORY')
    require(event.get('head_commit', {}).get('id') == head and event.get('sender', {}).get('login') == OWNER, 'PUSH_AUTHOR')
    require(parents == [BASE] and head != BASE, 'PARENT')
    require(request_in_parent is False and set(changed_paths) == CHANGED_FILES and request_raw == tracked_raw, 'REQUEST_GIT')
    request = parse_request(request_raw)
    require(request['sourceStateSha256'] == source_sha and request['selectionSha256'] == selection_sha, 'CURRENT_INPUTS')
    return request


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)


def safe_bytes(path, limit):
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), 'INPUT_FILE')
    require(0 < path.stat().st_size <= limit, 'INPUT_SIZE')
    return path.read_bytes()


def tracked_input(root, name, limit):
    raw = safe_bytes(root / name, limit)
    require(raw == git(root, 'show', 'HEAD:' + name), 'TRACKED_INPUT')
    return raw


def verify_identity(root, env):
    require(env.get('GITHUB_EVENT_NAME') == 'push', 'EVENT')
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    parents = [line.split(' ', 1)[1] for line in git(root, 'cat-file', '-p', 'HEAD').decode().split('\n\n', 1)[0].splitlines()
               if line.startswith('parent ')]
    require(parents == [BASE], 'PARENT')
    git(root, 'cat-file', '-e', BASE + '^{commit}')
    present = subprocess.run(['git', 'cat-file', '-e', BASE + ':' + REQUEST], cwd=root,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    request_raw = safe_bytes(root / REQUEST, 2048)
    tracked_raw = git(root, 'show', 'HEAD:' + REQUEST)
    changed = git(root, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').decode().splitlines()
    source_raw = tracked_input(root, SOURCE, 4 * 1024 * 1024)
    selection_raw = tracked_input(root, SELECTION, 1024 * 1024)
    # The full source inventory is verified by the fresh guard before image readiness;
    # later same-job guards retain this exact HEAD-bound inventory while native assets grow.
    event = parse(safe_bytes(Path(env.get('GITHUB_EVENT_PATH', '')), 4 * 1024 * 1024))
    return validate(env, event, head, parents, request_raw, tracked_raw, present, changed,
                    hashlib.sha256(source_raw).hexdigest(), hashlib.sha256(selection_raw).hexdigest())


# Prior independent native evidence only. Fresh receipts belong to the new run.
SHORT = dict(commit='1019ff71443f2dbc25a0f1b5027d5b245f295b29', runId=38111105749, runAttempt=1, jobId=114386673921,
    branch='journey-pouncer-ground-support-2915', workflow='.github/workflows/desert-rv-pouncer-ground-support.yml',
    artifactId=11692021847, artifactName='journey-pouncer-ground-support-UNREVIEWED-38111105749-1',
    artifactBytes=950762, artifactSha256='4110ccbb37a48a83c90f9f705d3bf3b3ee19491cae6f0cce130228daa6143d91',
    reportSha256='eb7aa27c6d1243132bf597c5cc5e3a0d1741a5072189083745f1e8dec1e4c60d',
    sourceStateSha256='c6224e96b67c11625c7dd58b9bc504714d922775fc9abd190fdb6445e715945e',
    unityMapSha256='3bdbb794c4b6cf54e0b4ee453a7e407673e824d4dc9fcbd76e96802d16029990')
CHANGED_FILES = frozenset({REQUEST, WORKFLOW, SOURCE,
    'tasks/desert-rv/scripts/journey_tracer_dispatch.py',
    'tasks/desert-rv/scripts/test_journey_tracer_dispatch.py',
    'tasks/desert-rv/scripts/prepare_runner.sh', 'tasks/desert-rv/scripts/verify_evidence.py',
    'tasks/desert-rv/art/journey-preparation/pipeline.py',
    'tasks/desert-rv/scripts/rendered/test_prepared_source.py',
    'tasks/desert-rv/scripts/test_journey_tracer_source_diagnostic.py'})
ADMISSION = 'tasks/desert-rv/journey-pouncer-short-admission'
ADMISSION_FILES = {'run.json', 'artifact.json', 'jobs.json', 'original.zip', 'seal.json'}
PREFIX = 'tasks/desert-rv/unity/'
SHORT_STEPS = (
    'Verify fixed-image readiness with at most one bounded fallback pull',
    'Validate bounded image observation and actual step outcome',
    'Verify immutable 2915 preparation and stage the explicit source overlay',
    'Native production binding and thirteen fixed physics regressions',
    'Seal only the three derived scenes after exact native and full source checks',
    'Native focused prepared R3 support and continuous AI observations',
    'Preserve bounded report and XML-derived outcome even when native execution fails',
    'Upload only original bounded R3 observations and source invariance',
    'Remove only the owned isolated R3 contact project', 'Prove the formal source stayed unchanged')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unity_map(state):
    rows = sorted([r for r in state['files'] + state['restoredFiles'] if r['path'].startswith(PREFIX)], key=lambda r:r['path'])
    require(len(rows) == 1017 and len({r['path'] for r in rows}) == len(rows), 'UNITY_MAP_COUNT')
    require(sha(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()) == SHORT['unityMapSha256'], 'UNITY_EQUIVALENCE')
    return rows


def validate_short_api(run, artifact, jobs):
    require(run.get('id') == SHORT['runId'] and run.get('run_attempt') == 1 and
        run.get('head_sha') == SHORT['commit'] and run.get('head_branch') == SHORT['branch'] and
        run.get('path') == SHORT['workflow'] and run.get('event') == 'push' and
        run.get('status') == 'completed' and run.get('conclusion') == 'success' and
        run.get('actor', {}).get('login') == OWNER and run.get('triggering_actor', {}).get('login') == OWNER,
        'SHORT_RUN')
    repository = run.get('repository', {})
    require(repository.get('full_name') == REPOSITORY and repository.get('private') is False and
        repository.get('fork') is False and repository.get('owner', {}).get('login') == OWNER, 'SHORT_REPOSITORY')
    require(artifact.get('id') == SHORT['artifactId'] and artifact.get('name') == SHORT['artifactName'] and
        artifact.get('expired') is False and artifact.get('size_in_bytes') == SHORT['artifactBytes'] and
        artifact.get('digest') == 'sha256:' + SHORT['artifactSha256'] and
        artifact.get('workflow_run', {}).get('id') == SHORT['runId'] and
        artifact['workflow_run'].get('head_sha') == SHORT['commit'] and
        artifact['workflow_run'].get('head_branch') == SHORT['branch'], 'SHORT_ARTIFACT')
    rows = jobs.get('jobs', [])
    require(type(rows) is list and len(rows) == 1 and rows[0].get('id') == SHORT['jobId'] and
        rows[0].get('name') == 'diagnose' and rows[0].get('run_id') == SHORT['runId'] and
        rows[0].get('status') == 'completed' and rows[0].get('conclusion') == 'success', 'SHORT_JOB')
    steps = rows[0].get('steps', [])
    require(len(steps) == len({s['name'] for s in steps}) and
        all(sum(s['name'] == n and s.get('status') == 'completed' and s.get('conclusion') == 'success'
                for s in steps) == 1 for n in SHORT_STEPS), 'SHORT_STEPS')


def short_members(raw):
    require(len(raw) == SHORT['artifactBytes'] and sha(raw) == SHORT['artifactSha256'], 'SHORT_ZIP_PIN')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = archive.infolist()
        require(len(rows) == 27 and len({r.filename for r in rows}) == 27 and
            sum(r.file_size for r in rows) <= 32 * 1024**2, 'SHORT_ZIP_BOUNDS')
        for row in rows:
            p = PurePosixPath(row.filename)
            require(not p.is_absolute() and p.parts and '..' not in p.parts and
                '\\' not in row.filename and p.as_posix() == row.filename and not row.flag_bits & 1 and
                stat.S_IFMT(row.external_attr >> 16) == stat.S_IFREG and
                0 < row.file_size <= 24 * 1024**2, 'SHORT_ZIP_MEMBER')
        return {r.filename: archive.read(r) for r in rows}


def validate_short_report(report, probe):
    require(report['schema'] == 1 and report['status'] == 'DIAGNOSTIC_COMPLETED_NOT_GAMEPLAY_ACCEPTANCE' and
        report['consumerCommit'] == report['currentProductionCommit'] == SHORT['commit'] and
        report['consumerParentCommit'] == probe.BASE and report['runId'] == str(SHORT['runId']) and
        report['runAttempt'] == '1' and report['producer'] == probe.PRODUCER and
        report['authorOutcome'] == report['nativeOutcome'] == 'success' and report['checks'] == [] and
        all(report[k] is True for k in ('sourceUnchanged','isolatedInputsVerified','inputUnchanged',
            'authorReportComplete','focusedReportComplete','derivedScenesSealed')) and
        all(report[k] is False for k in ('approved','gameplayReviewed','scopeReusable')) and
        report['nativeReportRejection'] is None and report['nativeRedactedReport'] is None, 'SHORT_SUCCESS')

def verify_short_bundle(raw, current_state):
    # Reuse the exact existing validators under the ORIGINAL consumer/input identities.
    import journey_pouncer_ground_support_probe as probe
    from journey_pouncer_support_reports import verify_author_report, verify_focused_report
    from journey_r3_continuous_contact_report import verify_native_report
    files = short_members(raw)
    require(sha(files['report.json']) == SHORT['reportSha256'], 'SHORT_REPORT_PIN')
    report = parse(files['report.json'])
    validate_short_report(report, probe)
    def pin(b): return dict(sha256=sha(b), bytes=len(b))
    expected = {'report.json': pin(files['report.json'])}
    for row in report['sourceSnapshots'] + [report[k] for k in
            ('nativeReport','nativeAuthorReport','nativeFocusedReport','derivedReceipt')]:
        require(type(row) is dict and set(row) == {'path','sha256','bytes'}, 'SHORT_EXPORT_ROW')
        name = row['path']; value = {k: row[k] for k in ('sha256','bytes')}
        require(name not in expected or expected[name] == value, 'SHORT_EXPORT_COLLISION')
        expected[name] = value
    require(set(files) == set(expected) and all(pin(files[n]) == p for n,p in expected.items()), 'SHORT_EXPORT_CLOSURE')
    for key, names in [('authorXml', (probe.AUTHOR_TEST, *probe.GENERIC_TESTS)), ('xml', (probe.FOCUSED_TEST, probe.TEST))]:
        value = report[key]
        require(value['result'] == 'Passed' and len(value['cases']) == len(names) and
            {c['fullname'] for c in value['cases']} == set(names) and
            all(c['result'] == 'Passed' and c['failure'] is None for c in value['cases']), 'SHORT_XML_CASES')
    require(sha(files['consumer-SOURCE-STATE.json']) == SHORT['sourceStateSha256'], 'SHORT_SOURCE_PIN')
    consumer_state = parse(files['consumer-SOURCE-STATE.json'])
    require(unity_map(consumer_state) == unity_map(current_state), 'UNITY_EQUIVALENCE')
    current = {r['path'][len(PREFIX):]:dict(sha256=r['sha256'], bytes=r['size']) for r in unity_map(current_state)}
    require({n for n in files if n.startswith('source/')} == {'source/' + Path(n).name for n in probe.SNAPSHOT_SOURCES}, 'SHORT_SOURCE_CLOSURE')
    for n in probe.SNAPSHOT_SOURCES:
        require(pin(files['source/' + Path(n).name]) == current[n], 'SHORT_SOURCE_SNAPSHOT')
    require(sha(files['producer-SOURCE-STATE.json']) == probe.PRODUCER['sourceStateSha256'] and
        sha(files['producer-generated-receipt.json']) == probe.PRODUCER['generatedReceiptSha256'], 'SHORT_ORIGINAL_PRODUCER')
    old_state = parse(files['producer-SOURCE-STATE.json'])
    old = {r['path'][len(PREFIX):]:dict(sha256=r['sha256'], bytes=r['size']) for r in old_state['files'] + old_state['restoredFiles'] if r['path'].startswith(PREFIX)}
    receipt = parse(files['producer-generated-receipt.json']); derived = parse(files['derived-scenes.json'])
    changes = {r['path']:r for r in derived['scenes']}
    require(set(changes) == set(probe.SCENES) and derived['consumerCommit'] == SHORT['commit'] and
        derived['producer'] == probe.PRODUCER and derived['approved'] is False, 'SHORT_DERIVED')
    dependencies = []
    for r in receipt['dependencies']:
        row = {k:v for k,v in r.items() if k != 'owner'}; n = row['path']
        if r['owner'] == 'source':
            require(old[n] == {k:row[k] for k in ('sha256','bytes')}, 'SHORT_DEPENDENCY_SOURCE')
            row.update(current[n])
        if n in changes:
            require(changes[n]['before'] == {k:row[k] for k in ('sha256','bytes')}, 'SHORT_SCENE_BEFORE')
            row.update(changes[n]['after'])
        dependencies.append(row)
    for n in probe.NEW_DEPENDENCIES:
        dependencies.append(dict(path=n,kind='asset',packageName='',packageVersion='',**current[n]))
    dependencies.sort(key=lambda r:r['path'])
    require(len(dependencies) == len({r['path'] for r in dependencies}) == 798 and
        sum(r['kind'] == 'package' for r in dependencies) == 24, 'SHORT_DEPENDENCIES')
    consumer = parse(files['consumer-input.json']); author = parse(files['author-input.json']); focused = parse(files['focused-input.json'])
    require(consumer['dependencies'] == dependencies and consumer['consumerCommit'] == consumer['currentProductionCommit'] == SHORT['commit'] and
        consumer['producerCommit'] == probe.PRODUCER['commit'] and consumer['dependencyChanges'] == derived['dependencyChanges'] and
        consumer['productionSourceOverlay'] == derived['productionSourceOverlay'] and
        consumer['derivedReceiptSha256'] == focused['derivedReceiptSha256'] == sha(files['derived-scenes.json']) and
        derived['authorInputSha256'] == sha(files['author-input.json']) and
        derived['authorReport'] == pin(files['native-authoring.json']) and
        derived['authorXmlSha256'] == report['authorXml']['sha256'], 'SHORT_INPUTS')
    for value in (author, focused):
        require(value['sourceCommit'] == SHORT['commit'] and all(current[r['path']]['sha256'] == r['sha256'] for r in value['sourcePins']), 'SHORT_SOURCE_INPUTS')
    scene_pins = [dict(path=n,beforeSha256=changes[n]['before']['sha256'],afterSha256=changes[n]['after']['sha256']) for n in probe.SCENES]
    require(verify_author_report(parse(files['native-authoring.json']), dict(sourceCommit=SHORT['commit'],unityVersion=probe.generated.UNITY),
        sha(files['author-input.json']), dependencies, scene_pins, complete=True), 'SHORT_AUTHOR')
    require(verify_focused_report(parse(files['native-focused-support.json']), dict(sourceCommit=SHORT['commit'],unityVersion=probe.generated.UNITY,
        derivedReceiptSha256=sha(files['derived-scenes.json']),sourcePinCount=len(probe.FOCUSED_SOURCES)*2), sha(files['focused-input.json']), complete=True), 'SHORT_FOCUSED')
    pins = {n:r['sha256'] for n,r in current.items()}; pins.update({r['path']:r['sha256'] for r in dependencies})
    pins[probe.INPUT_REL] = sha(files['consumer-input.json'])
    pins[probe.INPUT_REL.replace('.json','.sha256')] = sha((pins[probe.INPUT_REL] + '\n').encode())
    summary = verify_native_report(parse(files['native-r3-continuous-contact.json']), consumer, pins[probe.INPUT_REL], pins)
    require(summary == report['nativeSummary'] and summary['diagnosticComplete'] is True and
        summary['observedFrames'] == 1212 and summary['gameplayAccepted'] is False, 'SHORT_CONTINUOUS')


def api(path):
    raw = subprocess.check_output(['gh','api','/repos/' + REPOSITORY + path], stderr=subprocess.DEVNULL, timeout=60)
    require(0 < len(raw) <= 8 * 1024**2, 'SHORT_API_SIZE')
    return parse(raw)


def seal_value(env, request, evidence):
    return dict(schema=1, consumerCommit=env['GITHUB_SHA'], runId=env['GITHUB_RUN_ID'], runAttempt='1',
        sourceStateSha256=request['sourceStateSha256'], shortEvidence=SHORT,
        evidence={n:dict(sha256=sha(b),bytes=len(b)) for n,b in evidence.items()},
        scope='Prior independent 14+2 native success; full run executes its own original ten gates; not gameplay acceptance')


def admit(root, env, request):
    import verify_evidence as source
    require(source.ROOT == root, 'SOURCE_ROOT')
    # Explicit initial entrance: complete source verification precedes every network read.
    # source.guard() follows the seal in the workflow; its verify() never bypasses admission.
    current = source.verify_source_state(); unity_map(current)
    folder = root / ADMISSION
    require(not folder.exists() and not folder.is_symlink() and not any(p.is_symlink() for p in folder.parents), 'ADMISSION_EXISTS')
    folder.mkdir(mode=0o700)
    values = dict(run=api('/actions/runs/' + str(SHORT['runId'])),
        artifact=api('/actions/artifacts/' + str(SHORT['artifactId'])),
        jobs=api('/actions/runs/' + str(SHORT['runId']) + '/attempts/1/jobs?per_page=100'))
    validate_short_api(values['run'],values['artifact'],values['jobs'])
    evidence = {n + '.json': (json.dumps(v,sort_keys=True,indent=2)+'\n').encode() for n,v in values.items()}
    archive = folder/'original.zip'
    with archive.open('xb') as stream:
        subprocess.run(['gh','api','/repos/' + REPOSITORY + '/actions/artifacts/' + str(SHORT['artifactId']) + '/zip'],
            stdout=stream, stderr=subprocess.DEVNULL, check=True, timeout=180)
    raw = safe_bytes(archive, SHORT['artifactBytes']); verify_short_bundle(raw, current)
    evidence['original.zip'] = raw
    for n,b in evidence.items():
        if n != 'original.zip':
            with (folder/n).open('xb') as stream: stream.write(b)
    with (folder/'seal.json').open('x') as stream:
        json.dump(seal_value(env, request, evidence), stream, sort_keys=True, indent=2); stream.write('\n')


def verify_admission(root, env, request):
    folder = root/ADMISSION
    require(folder.is_dir() and not folder.is_symlink() and
        {p.name for p in folder.iterdir()} == ADMISSION_FILES, 'ADMISSION_FILES')
    evidence = {n:safe_bytes(folder/n, SHORT['artifactBytes'] if n == 'original.zip' else 8*1024**2)
        for n in ADMISSION_FILES - {'seal.json'}}
    require(len(evidence['original.zip']) == SHORT['artifactBytes'] and sha(evidence['original.zip']) == SHORT['artifactSha256'], 'SHORT_ZIP_PIN')
    require(parse(safe_bytes(folder/'seal.json',16384)) == seal_value(env,request,evidence), 'ADMISSION_SEAL')
    validate_short_api(*(parse(evidence[n+'.json']) for n in ('run','artifact','jobs')))
    unity_map(parse(tracked_input(root,SOURCE,4*1024**2)))


def verify(root, env):
    request = verify_identity(root, env)
    verify_admission(root, env, request)
    return request


# Only constant codes emitted by this module; exception messages from tools stay private.
FAILURE_CODES = frozenset('TRACER_DISPATCH_' + code for code in (
    'ACTOR ADMISSION_EXISTS ADMISSION_FILES ADMISSION_SEAL ARGUMENTS BAD_JSON BRANCH CURRENT_INPUTS '
    'DUPLICATE_KEY EVENT HEAD HOSTED_RUNNER INPUT_FILE INPUT_SIZE JSON_CONSTANT PARENT PUSH_AUTHOR '
    'PUSH_IDENTITY PUSH_KIND PUSH_REPOSITORY REPLAY REPOSITORY REQUEST_DIGEST REQUEST_GIT REQUEST_IDENTITY '
    'REQUEST_KEYS REQUEST_SHORT_TYPES REQUEST_SIZE SHORT_API_SIZE SHORT_ARTIFACT SHORT_AUTHOR SHORT_CONTINUOUS '
    'SHORT_DEPENDENCIES SHORT_DEPENDENCY_SOURCE SHORT_DERIVED SHORT_EXPORT_CLOSURE SHORT_EXPORT_COLLISION '
    'SHORT_EXPORT_ROW SHORT_FOCUSED SHORT_INPUTS SHORT_JOB SHORT_ORIGINAL_PRODUCER SHORT_REPORT_PIN '
    'SHORT_REPOSITORY SHORT_RUN SHORT_SCENE_BEFORE SHORT_SOURCE_CLOSURE SHORT_SOURCE_INPUTS SHORT_SOURCE_PIN '
    'SHORT_SOURCE_SNAPSHOT SHORT_STEPS SHORT_SUCCESS SHORT_XML_CASES SHORT_ZIP_BOUNDS SHORT_ZIP_MEMBER '
    'SHORT_ZIP_PIN SOURCE_ROOT TRACKED_INPUT UNITY_EQUIVALENCE UNITY_MAP_COUNT WORKFLOW '
).split())


def failure_code(error):
    return str(error) if type(error) is ValueError and str(error) in FAILURE_CODES else 'TRACER_PRODUCER_IDENTITY_OR_SHORT_ADMISSION_REJECTED'


def main():
    try:
        require(sys.argv[1:] in (['--admit'], ['--verify-only']), 'ARGUMENTS')
        request = verify_identity(ROOT, os.environ)
        if sys.argv[1:] == ['--admit']:
            admit(ROOT, os.environ, request)
        verify_admission(ROOT, os.environ, request)
        if sys.argv[1:] == ['--admit']:
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
                stream.write('selection=' + SELECTION + '\nselection_sha256=' + request['selectionSha256'] + '\n')
    except Exception as error:
        code = failure_code(error)
        print(code)
        raise SystemExit(2) from None
    print('TRACER_PRODUCER_IDENTITY_AND_PRIOR_SHORT_EVIDENCE_VERIFIED')


if __name__ == '__main__':
    main()
