import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
from unittest import mock
import import_desert_rv_source as subject

PATH = subject.PREFIX + 'unity/Assets/Test.cs'
COMMIT = '1' * 40


def pack(contents=None, mutate=None, extra=None, mode=0o100644):
    contents = {PATH: b'// user-owned test'} if contents is None else contents
    manifest = {'sourceCommit': COMMIT, 'files': [{'path': p, 'size': len(b), 'mode': '100644', 'sha256': hashlib.sha256(b).hexdigest(), 'sourceBlobSha': None, 'exportBlobSha': subject.git_blob(b)} for p, b in contents.items()]}
    if mutate:
        mutate(manifest)
    m = json.dumps(manifest).encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        for path, data in [*contents.items(), (subject.MANIFEST_PATH, m), *(extra or [])]:
            entry = zipfile.ZipInfo(path)
            entry.external_attr = mode << 16
            archive.writestr(entry, data)
    raw = out.getvalue()
    return raw, hashlib.sha256(raw).hexdigest(), hashlib.sha256(m).hexdigest(), COMMIT


class ArchiveSafety(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(subject.validate_archive(*pack())[PATH], b'// user-owned test')

    def test_hostile_paths(self):
        for name in ['/tmp/x', 'C:/x', subject.PREFIX + '../x', subject.PREFIX + 'unity/Assets/../x', subject.PREFIX + 'unity\\Assets\\x', subject.PREFIX + 'unity/Assets/.git/config', subject.PREFIX + 'unity/Assets/.github/workflows/x', subject.PREFIX + 'unity/Assets/.env', subject.PREFIX + 'other.cs', subject.PREFIX + 'unity/Assets/x\n', subject.PREFIX + 'unity/Assets/x.', subject.PREFIX + 'unity/Assets/key.pem']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                subject.validate_archive(*pack({name: b'x'}))

    def test_nonregular_modes(self):
        for mode in [0o120777, 0o100755, 0o040755, 0o106644, 0o020600, 0o100600, 0o644]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                subject.validate_archive(*pack(mode=mode))

    def test_duplicate(self):
        with self.assertRaises(ValueError):
            subject.validate_archive(*pack(extra=[(PATH, b'x')]))

    def test_case_collision(self):
        with self.assertRaises(ValueError):
            subject.validate_archive(*pack(extra=[(PATH.lower(), b'x')]))

    def test_unlisted(self):
        with self.assertRaises(ValueError):
            subject.validate_archive(*pack(extra=[(PATH + '.meta', b'x')]))

    def test_secret(self):
        with self.assertRaises(ValueError):
            subject.validate_archive(*pack({PATH: b'-----BEGIN PRIVATE KEY-----'}))

    def test_manifest_fields(self):
        for field, value in [('mode', '100755'), ('size', -1), ('size', True), ('sha256', '0' * 64), ('exportBlobSha', '0' * 40), ('sourceBlobSha', 'bogus')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                subject.validate_archive(*pack(mutate=lambda m: m['files'][0].update({field: value})))

    def test_review_pins(self):
        args = list(pack())
        for index in [1, 2, 3]:
            altered = args.copy()
            altered[index] = '0' * (40 if index == 3 else 64)
            with self.subTest(index=index), self.assertRaises(ValueError):
                subject.validate_archive(*altered)

    def test_duplicate_manifest_entry(self):
        with self.assertRaises(ValueError):
            subject.validate_archive(*pack(mutate=lambda m: m['files'].append(m['files'][0])))

    def test_size_limits(self):
        for limit in ['MAX_ARCHIVE', 'MAX_TOTAL', 'MAX_FILE', 'MAX_FILES']:
            with self.subTest(limit=limit), mock.patch.object(subject, limit, 1), self.assertRaises(ValueError):
                subject.validate_archive(*pack())

    def test_json_duplicate_keys(self):
        with self.assertRaises(ValueError):
            json.loads('{"files":[],"files":[]}', object_pairs_hook=subject.strict_object)

    def test_file_directory_collision(self):
        with self.assertRaises(ValueError):
            subject.validate_archive(*pack({PATH: b'x', PATH + '/child': b'y'}))

    def test_directory_entry(self):
        with self.assertRaises(ValueError):
            subject.validate_archive(*pack(extra=[(PATH + '/', b'')]))

    def test_nul_path(self):
        args = list(pack())
        raw = args[0].replace(b'Test.cs', b'Te\x00t.cs')
        args[0] = raw
        args[1] = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):
            subject.validate_archive(*args)

    def test_manifest_source_commit(self):
        with self.assertRaises(ValueError):
            subject.validate_archive(*pack(mutate=lambda m: m.update(sourceCommit='2' * 40)))

    def test_exact_gitignore_exception(self):
        self.assertIn(subject.PREFIX + '.gitignore', subject.validate_archive(*pack({subject.PREFIX + '.gitignore': b'/build/\n'})))

    def test_unapproved_download_url(self):
        with mock.patch.multiple(subject, ARCHIVE_SHA256='1' * 64, MANIFEST_SHA256='2' * 64, SOURCE_COMMIT=COMMIT, ARCHIVE_URL='https://evil.example/source.zip'), self.assertRaises(ValueError):
            subject.download()

    def test_unarmed_download(self):
        with mock.patch.object(subject, 'ARCHIVE_SHA256', ''), self.assertRaises(ValueError):
            subject.download()


class PreserveTree(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.before = os.getcwd()
        os.chdir(self.temp.name)
        subprocess.run(['git', 'init', '-q'], check=True)
        self.env = dict(os.environ, GIT_AUTHOR_NAME='test', GIT_AUTHOR_EMAIL='test@example.invalid', GIT_COMMITTER_NAME='test', GIT_COMMITTER_EMAIL='test@example.invalid')
        Path('keep.txt').write_text('preserve')
        subject.git('add', 'keep.txt', env=self.env)
        subject.git('commit', '-qm', 'base', env=self.env)
        self.base = subject.git('rev-parse', 'HEAD', env=self.env).strip().decode()
        self.env['GIT_INDEX_FILE'] = str(Path(self.temp.name) / 'alternate-index')

    def tearDown(self):
        os.chdir(self.before)
        self.temp.cleanup()

    def test_import_and_idempotence(self):
        files = subject.validate_archive(*pack())
        commit = subject.build_commit(files, self.base, self.env)
        self.assertEqual(subject.git('show', commit + ':keep.txt', env=self.env), b'preserve')
        self.assertEqual(subject.git('show', commit + ':' + PATH, env=self.env), files[PATH])
        self.assertEqual(subject.build_commit(files, commit, self.env), commit)
        self.assertFalse(Path(PATH).exists())

    def test_existing_collision_rejected(self):
        files = subject.validate_archive(*pack())
        commit = subject.build_commit(files, self.base, self.env)
        files[PATH] = b'new'
        with self.assertRaises(ValueError):
            subject.build_commit(files, commit, self.env)

    def test_ancestor_file_rejected(self):
        sha = subject.git('hash-object', '-w', '--stdin', data=b'x', env=self.env).strip().decode()
        subject.git('read-tree', self.base, env=self.env)
        subject.git('update-index', '--add', '--cacheinfo', '100644,' + sha + ',tasks', env=self.env)
        tree = subject.git('write-tree', env=self.env).strip().decode()
        commit = subject.git('commit-tree', tree, '-p', self.base, data=b'collision', env=self.env).strip().decode()
        with self.assertRaises(ValueError):
            subject.build_commit(subject.validate_archive(*pack()), commit, self.env)


if __name__ == '__main__':
    unittest.main()
