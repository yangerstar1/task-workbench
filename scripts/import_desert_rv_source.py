#!/usr/bin/env python3
"""Import one pinned, reviewed public archive. Never execute or extract its files."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import urllib.request
import zipfile

REPOSITORY = 'yangerstar1/task-workbench'
PREFIX = 'tasks/desert-rv/'
MANIFEST_PATH = PREFIX + 'PUBLIC-EXPORT.json'
# Fixed after source/license review and public Release digest verification.
ARCHIVE_URL = 'https://github.com/yangerstar1/task-workbench/releases/download/desert-rv-source-20261008-001/desert-rv-public-source-2d85e6d69cb0.zip'
ARCHIVE_SHA256 = '0efb5f3f8d1342b08eabf481a31df42b6bd62da95cc2fdee69d3ec0cc26b5e40'
MANIFEST_SHA256 = '003d3ba2c39fc626e85053371a7b454358a35f291d5a82e30ff5be1999aec2f9'
SOURCE_COMMIT = '2d85e6d69cb073a595d1f4c4ee2373310c5edc82'
MAX_ARCHIVE = 128 * 1024 * 1024
MAX_TOTAL = 192 * 1024 * 1024
MAX_FILE = 32 * 1024 * 1024
MAX_FILES = 5000
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
SHA1 = re.compile(r'[0-9a-f]{40}\Z')
SECRET = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}|sk-(?:proj-)?[A-Za-z0-9_-]{32,}')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(path):
    require(isinstance(path, str) and path.startswith(PREFIX), 'path outside target')
    require(len(path) < 512 and not any(ord(c) < 32 or ord(c) == 127 for c in path), 'invalid path characters')
    require('\\' not in path and ':' not in path, 'non-POSIX path')
    parts = path.split('/')
    require(all(p and p not in ('.', '..') and not p.endswith((' ', '.')) for p in parts), 'noncanonical path')
    require(path == PREFIX + '.gitignore' or not any(p.startswith('.') for p in parts), 'hidden path forbidden')
    require(not any(p.lower() in ('credentials', 'secrets', 'id_rsa', 'id_ed25519') or p.lower().endswith(('.pem', '.p12', '.pfx', '.key', '.keystore', '.jks', '.env')) for p in parts), 'sensitive filename forbidden')
    relative = path[len(PREFIX):]
    allowed = relative in ('.gitignore', 'PUBLIC-EXPORT.json', 'README.md', 'ASSET-NOTICES.md', 'scripts/backup/restore_unity_font.py', 'backup-assets/fonts/NotoSansCJKsc-Regular.otf.xz') or relative.startswith(('unity/Assets/', 'unity/Packages/', 'unity/ProjectSettings/'))
    require(allowed, 'path not allowlisted')
    return path


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def validate_archive(raw, archive_sha, manifest_sha, source_commit):
    require(len(raw) <= MAX_ARCHIVE, 'archive too large')
    require(SHA256.fullmatch(archive_sha) and hashlib.sha256(raw).hexdigest() == archive_sha, 'archive hash mismatch')
    require(SHA256.fullmatch(manifest_sha) and SHA1.fullmatch(source_commit), 'invalid review pins')
    files = {}
    seen = set()
    total = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        require(0 < len(entries) <= MAX_FILES, 'invalid file count')
        for entry in entries:
            require(entry.orig_filename == entry.filename, 'NUL-truncated ZIP path')
            name = safe_path(entry.filename)
            require(name.casefold() not in seen, 'duplicate/case-colliding path')
            seen.add(name.casefold())
            require(not entry.is_dir(), 'directory entries forbidden')
            mode = entry.external_attr >> 16
            require(stat.S_IFMT(mode) == stat.S_IFREG and (mode & 0o7777) == 0o644, 'nonregular or executable ZIP member')
            require(not entry.flag_bits & 1 and entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'unsupported ZIP encoding')
            require(0 <= entry.file_size <= MAX_FILE, 'member too large')
            total += entry.file_size
            require(total <= MAX_TOTAL, 'expanded archive too large')
            with archive.open(entry) as member:
                data = member.read(MAX_FILE + 1)
            require(len(data) == entry.file_size, 'member size mismatch')
            require(not SECRET.search(data), 'credential pattern detected')
            files[name] = data
    require(MANIFEST_PATH in files, 'missing manifest')
    require(hashlib.sha256(files[MANIFEST_PATH]).hexdigest() == manifest_sha, 'manifest hash mismatch')
    manifest = json.loads(files[MANIFEST_PATH], object_pairs_hook=strict_object)
    require(manifest.get('sourceCommit') == source_commit, 'source commit mismatch')
    listed = manifest.get('files')
    require(isinstance(listed, list) and 0 < len(listed) < MAX_FILES, 'invalid manifest file list')
    names = set()
    for item in listed:
        require(isinstance(item, dict), 'invalid manifest entry')
        path = safe_path(item.get('path'))
        require(path != MANIFEST_PATH and path not in names, 'manifest duplicate or self-reference')
        names.add(path)
        require(path in files and item.get('mode') == '100644', 'missing file or bad mode')
        data = files[path]
        require(type(item.get('size')) is int and item['size'] == len(data), 'manifest size mismatch')
        require(item.get('sha256') == hashlib.sha256(data).hexdigest(), 'file hash mismatch')
        require(item.get('exportBlobSha') == git_blob(data), 'blob hash mismatch')
        require(item.get('sourceBlobSha') is None or isinstance(item['sourceBlobSha'], str) and SHA1.fullmatch(item['sourceBlobSha']), 'invalid source blob hash')
    require(names == set(files) - {MANIFEST_PATH}, 'unlisted file')
    # Git cannot represent a file and its descendants in the same tree.
    require(not any('/'.join(p.split('/')[:n]) in files for p in files for n in range(1, len(p.split('/')))), 'file/directory collision')
    return files


def download():
    require(SHA256.fullmatch(ARCHIVE_SHA256) and SHA256.fullmatch(MANIFEST_SHA256) and SHA1.fullmatch(SOURCE_COMMIT), 'import is not armed')
    require(re.fullmatch(r'https://github\.com/yangerstar1/task-workbench/releases/download/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\.zip', ARCHIVE_URL), 'unapproved release URL')
    # No authentication on public download; only GitHub release redirects permitted.
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            from urllib.parse import urlparse
            parsed = urlparse(newurl)
            require(parsed.scheme == 'https' and parsed.hostname in ('github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'), 'unapproved redirect')
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    with urllib.request.build_opener(Redirect).open(ARCHIVE_URL, timeout=60) as response:
        raw = response.read(MAX_ARCHIVE + 1)
    return validate_archive(raw, ARCHIVE_SHA256, MANIFEST_SHA256, SOURCE_COMMIT)


def git(*args, data=None, env=None):
    # No clean/smudge filters, hooks, source binaries, shell interpolation or source commands.
    result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', *args], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    require(result.returncode == 0, 'Git operation failed: ' + args[0])
    return result.stdout


def build_commit(files, base, env):
    git('read-tree', base, env=env)
    existing = {}
    for entry in git('ls-tree', '-rz', base, env=env).split(b'\0'):
        if entry:
            header, path = entry.split(b'\t', 1)
            mode, kind, sha = header.decode().split()
            existing[path.decode()] = (mode, kind, sha)
    existing_folded = {p.casefold(): p for p in existing}
    for path, data in files.items():
        require(path.casefold() not in existing_folded or existing_folded[path.casefold()] == path, 'existing case collision')
        require(path not in existing or existing[path] == ('100644', 'blob', git_blob(data)), 'existing file differs; refusing overwrite: ' + path)
        for n in range(1, len(path.split('/'))):
            require('/'.join(path.split('/')[:n]) not in existing, 'existing ancestor is not directory')
        require(not any(p.startswith(path + '/') for p in existing), 'existing directory collision')
    for path, data in sorted(files.items()):
        sha = git('hash-object', '-w', '--stdin', data=data, env=env).strip().decode()
        require(sha == git_blob(data), 'written blob mismatch')
        git('update-index', '--add', '--cacheinfo', '100644,' + sha + ',' + path, env=env)
    tree = git('write-tree', env=env).strip().decode()
    before = git('rev-parse', base + '^{tree}', env=env).strip().decode()
    if tree == before:
        return base
    commit = git('commit-tree', tree, '-p', base, data=('Import audited Desert RV source ' + SOURCE_COMMIT + '\n').encode(), env=env).strip().decode()
    changed = set(git('diff-tree', '--no-commit-id', '--name-only', '-r', '-z', base, commit, env=env).decode().strip('\0').split('\0'))
    require(changed <= set(files), 'commit escaped manifest')
    return commit


def main():
    require(os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' and os.environ.get('GITHUB_REPOSITORY') == REPOSITORY and os.environ.get('GITHUB_REF') == 'refs/heads/main' and os.environ.get('GITHUB_ACTOR') == 'yangerstar1' and os.environ.get('GITHUB_TRIGGERING_ACTOR') == 'yangerstar1', 'untrusted invocation')
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    require(event.get('repository', {}).get('private') is False and event['repository'].get('default_branch') == 'main', 'not public main repository')
    files = download()
    base = git('rev-parse', 'HEAD').strip().decode()
    require(base == os.environ.get('GITHUB_SHA'), 'checkout does not match dispatch')
    token = os.environ['GH_TOKEN']
    env = {k: v for k, v in os.environ.items() if k not in ('GH_TOKEN', 'GITHUB_TOKEN')}
    env.update(GIT_AUTHOR_NAME='github-actions[bot]', GIT_COMMITTER_NAME='github-actions[bot]', GIT_AUTHOR_EMAIL='41898282+github-actions[bot]@users.noreply.github.com', GIT_COMMITTER_EMAIL='41898282+github-actions[bot]@users.noreply.github.com', GIT_TERMINAL_PROMPT='0')
    with tempfile.TemporaryDirectory() as temporary:
        env['GIT_INDEX_FILE'] = str(Path(temporary) / 'index')
        commit = build_commit(files, base, env)
        # Token exists only in the push process environment, never in .git/config/URL/logs.
        push_env = dict(env, GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader', GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + base64.b64encode(('x-access-token:' + token).encode()).decode())
        remote = 'https://github.com/' + REPOSITORY + '.git'
        observed = git('ls-remote', remote, 'refs/heads/main', env=push_env).decode().split()[0]
        require(observed == base, 'main advanced; rerun from its new HEAD')
        # Ordinary fast-forward push only. A race also fails server-side: no force, no rebase.
        if commit != base:
            git('push', remote, commit + ':refs/heads/main', env=push_env)
        observed = git('ls-remote', remote, 'refs/heads/main', env=push_env).decode().split()[0]
        require(observed == commit, 'remote verification inconclusive')
    summary = f'Imported and verified {len(files)} files ({sum(map(len, files.values()))} bytes).\n\nCommit: https://github.com/{REPOSITORY}/commit/{commit}\n\nArchive SHA-256: {ARCHIVE_SHA256}\n\nManifest SHA-256: {MANIFEST_SHA256}\n\nSource commit: {SOURCE_COMMIT}\n\nAll manifest sizes, modes, SHA-256 and Git blob hashes verified. Existing paths preserved. No source code executed.\n'
    print(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
            output.write(summary)


if __name__ == '__main__':
    main()
