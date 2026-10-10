"""Single-use fresh producer and build push after exact native movement gates."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = '061fd618abb456df8d4bfb2d33c0db9c01eb1e9c'
BRANCH = 'wip/combat-feedback-20261010'
REF = 'refs/heads/' + BRANCH
REPOSITORY = 'yangerstar1/task-workbench'
OWNER = 'yangerstar1'
WORKFLOW = '.github/workflows/desert-rv-tracer-shader-prepare.yml'
REQUEST = '.github/dispatch/desert-rv-combat-feedback-full-20261010.json'
REQUEST_ID = 'desert-rv-combat-feedback-full-061f-20261010-once'
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
        'schema', 'requestId', 'baseCommit', 'sourceStateSha256', 'selection', 'selectionSha256'}, 'REQUEST_KEYS')
    require(type(value['schema']) is int and value['schema'] == 1 and
            value['requestId'] == REQUEST_ID and value['baseCommit'] == BASE and
            value['selection'] == SELECTION, 'REQUEST_IDENTITY')
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
    require(request_in_parent is False and REQUEST in changed_paths and request_raw == tracked_raw, 'REQUEST_GIT')
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


def verify(root, env):
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


def main():
    try:
        require(sys.argv[1:] in ([], ['--verify-only']), 'ARGUMENTS')
        request = verify(ROOT, os.environ)
        if not sys.argv[1:]:
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
                stream.write('selection=' + SELECTION + '\nselection_sha256=' + request['selectionSha256'] + '\n')
    except Exception:
        print('TRACER_PRODUCER_IDENTITY_REJECTED')
        raise SystemExit(2) from None
    print('TRACER_PRODUCER_IDENTITY_VERIFIED')


if __name__ == '__main__':
    main()
