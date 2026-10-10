"""One fixed observer push; manual input remains explicit. Never validates a native result."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
REPOSITORY = 'yangerstar1/task-workbench'
OWNER = 'yangerstar1'
WORKFLOW = '.github/workflows/desert-rv-player-observe.yml'
REQUEST = '.github/dispatch/desert-rv-player-observe-20261010-8d7fe37f.json'
REQUEST_ID = 'desert-rv-player-observe-20261010-once-8d7fe37f'
BASE = 'e420b4d3f9ddacbc984f8693d4bba32e6ea76bb5'
PUSH_REF = 'refs/heads/journey-player-observer-fa18'
MANUAL_REF = 'refs/heads/main'
POLICY = 'tasks/desert-rv/art/journey-preparation/restoration-transition.json'
POLICY_SHA256 = '568887d4921833a448903c549d9ee5b526eb3dff45aa53129c7aa9a521479777'
SOURCE_STATE = 'tasks/desert-rv/SOURCE-STATE.json'
PIN_FIELDS = {
    'PRODUCER_RUN_ID': 'producerRunId',
    'PRODUCER_COMMIT': 'producerCommit',
    'PRODUCER_ARTIFACT_ID': 'producerArtifactId',
    'PRODUCER_ZIP_SHA256': 'producerZipSha256',
}
# Exact successful producer pins verified from original local artifact bytes; rechecked by API at runtime.
EXPECTED_PRODUCER = {
    'PRODUCER_RUN_ID': '38022081522',
    'PRODUCER_COMMIT': '98565627e6a4fb3e977cfbeebbafac0043616725',
    'PRODUCER_ARTIFACT_ID': '11660491222',
    'PRODUCER_ZIP_SHA256': '2d14658fae692f56b3fca61a4e56acc90be96d5737ff9565c79fac2986f7752e',
}
CHANGED_PATHS = {
    WORKFLOW, REQUEST, SOURCE_STATE,
    'tasks/desert-rv/scripts/environment_image_precheck.py',
    'tasks/desert-rv/scripts/journey_observer_dispatch.py',
    'tasks/desert-rv/scripts/player/observe_journey_player.py',
    'tasks/desert-rv/scripts/player/test_observe_journey_player.py',
    'tasks/desert-rv/scripts/test_environment_image_precheck.py',
    'tasks/desert-rv/scripts/test_journey_observer_dispatch.py',
}


def require(ok, code):
    if not ok:
        raise ValueError('OBSERVER_DISPATCH_' + code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def hex_string(value, length):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{' + str(length) + '}', value) is not None


def producer_pins(values):
    require(isinstance(values, dict) and set(values) == set(PIN_FIELDS), 'PIN_KEYS')
    for key in ('PRODUCER_RUN_ID', 'PRODUCER_ARTIFACT_ID'):
        require(isinstance(values[key], str) and re.fullmatch('[1-9][0-9]{0,19}', values[key]), 'PIN_ID')
    require(hex_string(values['PRODUCER_COMMIT'], 40) and hex_string(values['PRODUCER_ZIP_SHA256'], 64), 'PIN_DIGEST')
    return values


def decode(raw, limit):
    require(isinstance(raw, bytes) and 0 < len(raw) <= limit, 'JSON_SIZE')
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'DUPLICATE_KEY')
            value[key] = item
        return value
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: require(False, 'JSON_CONSTANT'))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError('OBSERVER_DISPATCH_BAD_JSON') from None


def parse_request(raw):
    value = decode(raw, 4096)
    require(isinstance(value, dict) and set(value) == {
        'schema', 'requestId', 'baseCommit', 'policySha256', 'sourceStateSha256', *PIN_FIELDS.values()
    }, 'REQUEST_KEYS')
    require(type(value['schema']) is int and value['schema'] == 1 and
            value['requestId'] == REQUEST_ID and value['baseCommit'] == BASE, 'REQUEST_IDENTITY')
    require(hex_string(value['policySha256'], 64) and hex_string(value['sourceStateSha256'], 64), 'REQUEST_DIGEST')
    pins = producer_pins({key: value[field] for key, field in PIN_FIELDS.items()})
    require(pins == EXPECTED_PRODUCER, 'REQUEST_PRODUCER')
    return value, pins


def validate_context(env, event, head):
    require(env.get('GITHUB_ACTIONS') == 'true' and env.get('GITHUB_REPOSITORY') == REPOSITORY and
            env.get('GITHUB_REPOSITORY_VISIBILITY') == 'public', 'REPOSITORY')
    require(env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and env.get('RUNNER_OS') == 'Linux', 'RUNNER')
    require(env.get('GITHUB_ACTOR') == OWNER and env.get('GITHUB_TRIGGERING_ACTOR') == OWNER, 'ACTOR')
    require(env.get('GITHUB_EVENT_NAME') in {'push', 'workflow_dispatch'}, 'EVENT')
    expected_ref = PUSH_REF if env['GITHUB_EVENT_NAME'] == 'push' else MANUAL_REF
    require(env.get('GITHUB_REF') == expected_ref, 'BRANCH')
    require(env.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/' + WORKFLOW + '@' + expected_ref, 'WORKFLOW')
    require(hex_string(head, 40) and env.get('GITHUB_SHA') == head, 'HEAD')
    require(re.fullmatch('[1-9][0-9]*', env.get('GITHUB_RUN_ID', '')) and
            re.fullmatch('[1-9][0-9]*', env.get('GITHUB_RUN_ATTEMPT', '')), 'RUN')
    require(isinstance(event, dict), 'EVENT_JSON')
    repo = event.get('repository', {})
    require(isinstance(repo, dict) and repo.get('full_name') == REPOSITORY and
            repo.get('private') is False and repo.get('fork') is False and
            repo.get('default_branch') == 'main' and repo.get('visibility') == 'public' and
            isinstance(repo.get('owner'), dict) and repo['owner'].get('login') == OWNER, 'EVENT_REPOSITORY')


def validate_push(env, event, head, parents, request_raw, tracked_raw, request_in_parent,
                  changed_paths, policy_raw, state_raw):
    require(hex_string(BASE, 40), 'UNFINALIZED_PARENT')
    producer_pins(EXPECTED_PRODUCER)  # Unresolved/empty template fields fail before any download.
    require(env.get('GITHUB_EVENT_NAME') == 'push', 'EVENT')
    require(env.get('GITHUB_RUN_ATTEMPT') == '1', 'REPLAY')
    require(event.get('before') == BASE and event.get('after') == head and
            event.get('ref') == PUSH_REF and head != BASE, 'PUSH_IDENTITY')
    require(event.get('created') is False and event.get('deleted') is False and event.get('forced') is False, 'PUSH_KIND')
    require(isinstance(event.get('head_commit'), dict) and event['head_commit'].get('id') == head and
            isinstance(event.get('sender'), dict) and event['sender'].get('login') == OWNER, 'PUSH_AUTHOR')
    require(parents == [BASE], 'PARENT')
    require(request_in_parent is False and request_raw == tracked_raw, 'REQUEST_GIT')
    require(set(changed_paths) == CHANGED_PATHS and len(changed_paths) == len(CHANGED_PATHS), 'CHANGED_SET')
    request, pins = parse_request(request_raw)
    require(sha(policy_raw) == request['policySha256'] == POLICY_SHA256, 'POLICY')
    require(sha(state_raw) == request['sourceStateSha256'], 'SOURCE_STATE')
    return pins


def git(root, *args):
    # Exact checkout only; container root must not change global trust configuration.
    return subprocess.check_output(['git', '-c', 'safe.directory=' + str(root.resolve()), *args],
                                   cwd=root, stderr=subprocess.DEVNULL)


def safe_bytes(path, limit):
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), 'INPUT_FILE')
    require(path.stat().st_size <= limit, 'INPUT_SIZE')
    return path.read_bytes()


def tracked_bytes(root, name, limit):
    row = git(root, 'ls-tree', 'HEAD', '--', name).decode().strip().split('\t')
    require(len(row) == 2 and row[1] == name, 'TRACKED_PATH')
    fields = row[0].split()
    require(len(fields) == 3 and fields[0] == '100644' and fields[1] == 'blob', 'GIT_MODE')
    size = int(git(root, 'cat-file', '-s', fields[2]))
    require(size <= limit, 'TRACKED_SIZE')
    raw = git(root, 'cat-file', 'blob', fields[2])
    require(len(raw) == size and raw == safe_bytes(root / name, limit), 'TRACKED_BYTES')
    return raw


def verify(root, env):
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    event = decode(safe_bytes(Path(env.get('GITHUB_EVENT_PATH', '')), 4 * 1024**2), 4 * 1024**2)
    validate_context(env, event, head)
    if env['GITHUB_EVENT_NAME'] == 'workflow_dispatch':
        return producer_pins({key: env.get('MANUAL_' + key, '') for key in PIN_FIELDS})
    require(hex_string(BASE, 40), 'UNFINALIZED_PARENT')
    producer_pins(EXPECTED_PRODUCER)
    parents = [line.split(' ', 1)[1] for line in git(root, 'cat-file', '-p', 'HEAD').decode().split('\n\n', 1)[0].splitlines() if line.startswith('parent ')]
    require(parents == [BASE], 'PARENT')
    git(root, 'cat-file', '-e', BASE + '^{commit}')
    parent_tree = git(root, 'ls-tree', BASE, '--', REQUEST)
    request_raw = tracked_bytes(root, REQUEST, 4096)
    policy_raw = tracked_bytes(root, POLICY, 1024**2)
    state_raw = tracked_bytes(root, SOURCE_STATE, 4 * 1024**2)
    # Recheck actual current payload against HEAD too; SOURCE-STATE covers its full source domain.
    for name in CHANGED_PATHS - {REQUEST, SOURCE_STATE}:
        tracked_bytes(root, name, 4 * 1024**2)
    changed = git(root, 'diff-tree', '--no-commit-id', '--name-only', '-z', '-r', 'HEAD').decode().rstrip('\0').split('\0')
    return validate_push(env, event, head, parents, request_raw, request_raw, bool(parent_tree),
                         changed, policy_raw, state_raw)


def verify_runtime(root, env):
    event_sha = env.get('OBSERVER_EVENT_SHA256', '')
    require(hex_string(event_sha, 64), 'EVENT_PIN')
    event_path = Path(env.get('GITHUB_EVENT_PATH', ''))
    require(sha(safe_bytes(event_path, 4 * 1024**2)) == event_sha, 'EVENT_BYTES')
    expected = verify(root, env)
    require(sha(safe_bytes(event_path, 4 * 1024**2)) == event_sha, 'EVENT_BYTES')
    supplied = producer_pins({key: env.get(key, '') for key in PIN_FIELDS})
    require(supplied == expected, 'RUNTIME_PINS')
    return supplied


def main():
    require(sys.argv[1:] in ([], ['--verify-only']), 'ARGUMENTS')
    event_path = Path(os.environ.get('GITHUB_EVENT_PATH', ''))
    event_sha = sha(safe_bytes(event_path, 4 * 1024**2))
    pins = verify(ROOT, os.environ)
    require(sha(safe_bytes(event_path, 4 * 1024**2)) == event_sha, 'EVENT_BYTES')
    if not sys.argv[1:]:
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            for key, value in pins.items():
                stream.write(key.lower() + '=' + value + '\n')
            stream.write('observer_event_sha256=' + event_sha + '\n')
    print('PLAYER_OBSERVER_REQUEST_IDENTITY_VERIFIED')


if __name__ == '__main__':
    main()
