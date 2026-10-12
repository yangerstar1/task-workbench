#!/usr/bin/env python3
"""Synthetic-only tests for the non-authoritative G3 metadata collector."""
import sys
sys.dont_write_bytecode = True
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import tempfile
import time
import types
import unittest
from unittest import mock

import g3_path_diagnostics as diag


class DiagnosticFixture(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(prefix='g3-diag-test-')
        self.base = Path(self.fixture.name)
        self.root = self.base / 'checkout'
        self.temp = self.base / 'runner'
        self.root.mkdir()
        self.temp.mkdir(mode=0o700)
        self.commands = self.temp / '_runner_file_commands'
        self.commands.mkdir(mode=0o700)
        self.output = self.commands / 'set_output_synthetic'
        self.output.write_bytes(b'')
        self.output.chmod(0o600)
        self.env = dict(GITHUB_WORKSPACE=str(self.root), RUNNER_TEMP=str(self.temp),
                        GITHUB_OUTPUT=str(self.output), GITHUB_SHA='a' * 40,
                        GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='2', GITHUB_JOB='android')

    def tearDown(self):
        for directory, dirs, files in os.walk(self.base, followlinks=False):
            os.chmod(directory, 0o700)
        self.fixture.cleanup()

    @contextlib.contextmanager
    def root_handle(self):
        fd = diag.open_directory(self.root)
        try:
            yield fd
        finally:
            os.close(fd)

    @contextlib.contextmanager
    def output_handles(self):
        _, fd, channel = diag.output_handles(self.root, self.env)
        try:
            yield fd, channel
        finally:
            os.close(channel[0])
            os.close(channel[1])
            os.close(fd)

    def collect(self, **kwargs):
        with self.root_handle() as fd:
            return diag.collect(fd, **kwargs)

    def assert_refused(self, operation):
        with self.assertRaises((diag.DiagnosticError, OSError)):
            operation()

    def initialize_git(self):
        env = dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), HOME=str(self.base),
                   GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, LC_ALL='C')
        subprocess.run(['git', 'init', '--quiet', str(self.root)], env=env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (self.root / 'synthetic-source').write_bytes(b'synthetic only\n')
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], env=env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Synthetic Test',
                        '-c', 'user.email=synthetic@example.invalid', 'commit', '--quiet', '-m', 'fixture'],
                       env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.env['GITHUB_SHA'] = subprocess.check_output(
            ['git', '-C', str(self.root), 'rev-parse', 'HEAD'], env=env).decode('ascii').strip()
        return dict(env, **self.env)


class EnumerationTests(DiagnosticFixture):
    def test_internal_hardlinks_report_metadata_without_acceptance(self):
        directory = self.root / 'tasks/lottery-shop/unity/Library/Bee/Android'
        directory.mkdir(parents=True)
        first = directory / 'private-name-one'
        first.write_bytes(b'UNKNOWN_CONTENT_MUST_NOT_BE_READ')
        os.link(first, directory / 'private-name-two')
        result = self.collect()
        self.assertTrue(result['stable'])
        self.assertTrue(result['complete'])
        self.assertFalse(result['atomicSnapshot'])
        group, = result['hardlinkGroups']
        self.assertEqual(group['observedCheckoutMembers'], 2)
        self.assertEqual(group['observedNlinkValues'], [2])
        self.assertTrue(group['membershipEqualsNlink'])
        self.assertEqual({m['pathClass'] for m in group['members']}, {'LIBRARY_BEE_ANDROID'})
        exported = json.dumps(result)
        self.assertNotIn('private-name', exported)
        self.assertNotIn('UNKNOWN_CONTENT', exported)
        self.assertNotIn('PASS', exported)

    def test_external_hardlink_is_unresolved_not_accepted(self):
        external = self.base / 'outside-sensitive-name'
        external.write_bytes(b'outside sensitive content')
        os.link(external, self.root / 'in-checkout')
        group, = self.collect()['hardlinkGroups']
        self.assertEqual(group['observedCheckoutMembers'], 1)
        self.assertEqual(group['observedNlinkValues'], [2])
        self.assertFalse(group['membershipEqualsNlink'])
        self.assertNotIn('outside-sensitive-name', json.dumps(group))

    def test_fifo_and_symlink_are_observed_without_opening(self):
        os.mkfifo(self.root / 'private-fifo')
        target = self.base / 'unknown-target'
        target.mkdir()
        (target / 'must-not-enumerate').write_bytes(b'PRIVATE CONTENT')
        (self.root / 'private-link').symlink_to(target, target_is_directory=True)
        actual_open = os.open

        def directories_only(path, flags, *args, **kwargs):
            self.assertTrue(flags & os.O_DIRECTORY, 'collector opened an unknown non-directory')
            return actual_open(path, flags, *args, **kwargs)

        with self.root_handle() as fd, mock.patch.object(diag.os, 'open', side_effect=directories_only), \
                mock.patch.object(diag.os, 'read', side_effect=AssertionError('content read')), \
                mock.patch.object(diag.os, 'readlink', side_effect=AssertionError('target read')):
            result = diag.collect(fd)
        self.assertTrue(result['stable'])
        self.assertEqual(result['secondPassEntries'], 2)
        self.assertEqual({m['kind'] for m in result['specialNodes']}, {'fifo', 'symbolic_link'})
        self.assertNotIn('must-not-enumerate', json.dumps(result))

    def test_real_socket_metadata_when_executor_supports_sockets(self):
        if os.environ.get('G3_DIAGNOSTIC_SKIP_AF_UNIX') == '1':
            self.skipTest('Real AF_UNIX fixture disabled after verified executor denial; synthetic branches remain covered')
        try:
            sock = socket.socket(socket.AF_UNIX)
        except PermissionError:
            self.skipTest('Executor denies AF_UNIX creation; socket branches have separate synthetic coverage')
        self.addCleanup(sock.close)
        sock.bind(str(self.root / 'private-socket'))
        result = self.collect()
        self.assertTrue(result['stable'])
        self.assertEqual([m['kind'] for m in result['specialNodes']], ['socket'])

    def test_socket_metadata_branch_with_synthetic_lstat(self):
        entries = {'private-socket': (1, 10, stat.S_IFSOCK | 0o600, 1)}
        with self.root_handle() as fd, mock.patch.object(diag, 'scan_pass', return_value=(entries, [])):
            result = diag.collect(fd)
        self.assertTrue(result['stable'])
        self.assertEqual([m['kind'] for m in result['specialNodes']], ['socket'])
        self.assertNotIn('private-socket', json.dumps(result))

    def test_unknown_names_unicode_newlines_and_commands_are_redacted(self):
        names = ['secret token=XYZ\n::error::injected', '隐私文件', os.fsdecode(b'bad-\xff-name'), 'Assets']
        for name in names:
            (self.root / name).symlink_to('/never-follow-this-private-target')
        result = self.collect()
        exported = json.dumps(result)
        for name in names:
            self.assertNotIn(name, exported)
        self.assertNotIn('never-follow', exported)
        self.assertEqual(len(result['specialNodes']), len(names))
        self.assertEqual(diag.path_shape('tasks/lottery-shop/unity/Assets/private.cs').split('/')[:4],
                         ['tasks', 'lottery-shop', 'unity', 'Assets'])
        self.assertTrue(diag.path_shape('Assets').startswith('u0_'))

    def test_node_limit_marks_incomplete(self):
        for i in range(4):
            (self.root / str(i)).write_bytes(b'')
        result = self.collect(max_nodes=2)
        self.assertFalse(result['stable'])
        self.assertFalse(result['complete'])
        self.assertIn('NODE_LIMIT', result['errors'])
        self.assertLessEqual(result['firstPassEntries'], 2)

    def test_depth_limit_marks_incomplete(self):
        (self.root / 'one/two/three').mkdir(parents=True)
        result = self.collect(max_depth=1)
        self.assertIn('DEPTH_LIMIT', result['errors'])
        self.assertFalse(result['complete'])

    def test_time_limit_marks_incomplete(self):
        result = self.collect(seconds=-1)
        self.assertIn('TIME_LIMIT', result['errors'])
        self.assertFalse(result['stable'])

    def assert_scan_deadline_exceeded(self, result):
        self.assertIn('TIME_LIMIT', result['errors'])
        self.assertFalse(result['enumerationComplete'])
        self.assertFalse(result['complete'])
        self.assertFalse(result['stable'])
        self.assertTrue(all(not group['membershipEqualsNlink']
                            for group in result['hardlinkGroups']))

    def test_final_second_pass_stat_over_deadline_is_incomplete(self):
        first = self.root / 'first'
        first.write_bytes(b'synthetic metadata fixture')
        os.link(first, self.root / 'second')
        actual_stat = os.stat
        elapsed = 0.0
        calls = 0
        with self.root_handle() as fd:
            def late_final_stat(path, *args, **kwargs):
                nonlocal elapsed, calls
                info = actual_stat(path, *args, **kwargs)
                if kwargs.get('dir_fd') == fd and path in ('first', 'second'):
                    calls += 1
                    if calls == 4:
                        elapsed = 21.0
                return info

            with mock.patch.object(diag.os, 'stat', side_effect=late_final_stat), \
                    mock.patch.object(diag.time, 'monotonic', side_effect=lambda: elapsed):
                result = diag.collect(fd)
        self.assertEqual(calls, 4)
        self.assertGreater(elapsed, result['limits']['seconds'])
        self.assert_scan_deadline_exceeded(result)
        self.assertEqual(len(result['hardlinkGroups']), 1)

    def test_final_empty_iterator_over_deadline_is_incomplete(self):
        elapsed = 0.0
        calls = 0

        @contextlib.contextmanager
        def late_empty_iterator(fd):
            nonlocal calls
            calls += 1
            pass_number = calls

            def entries():
                nonlocal elapsed
                if pass_number == 2:
                    elapsed = 21.0
                yield from ()

            yield entries()

        with self.root_handle() as fd, \
                mock.patch.object(diag.os, 'scandir', side_effect=late_empty_iterator), \
                mock.patch.object(diag.time, 'monotonic', side_effect=lambda: elapsed):
            result = diag.collect(fd)
        self.assertEqual(calls, 2)
        self.assertEqual(result['secondPassEntries'], 0)
        self.assertGreater(elapsed, result['limits']['seconds'])
        self.assert_scan_deadline_exceeded(result)

    def test_final_root_stat_over_deadline_is_incomplete(self):
        actual_fstat = os.fstat
        elapsed = 0.0
        with self.root_handle() as fd:
            calls = 0

            def late_root_stat(other_fd):
                nonlocal calls, elapsed
                info = actual_fstat(other_fd)
                if other_fd == fd:
                    calls += 1
                    if calls == 2:
                        elapsed = 21.0
                return info

            with mock.patch.object(diag.os, 'fstat', side_effect=late_root_stat), \
                    mock.patch.object(diag.time, 'monotonic', side_effect=lambda: elapsed):
                result = diag.collect(fd)
        self.assertEqual(calls, 2)
        self.assert_scan_deadline_exceeded(result)

    def test_aggregate_path_byte_limit_marks_incomplete(self):
        for name in ('first-name', 'second-name', 'third-name'):
            (self.root / name).write_bytes(b'')
        with mock.patch.object(diag, 'MAX_PATH_BYTES', 15):
            result = self.collect()
        self.assertIn('NAME_LIMIT', result['errors'])
        self.assertFalse(result['complete'])

    def test_duplicate_directory_entries_are_changed(self):
        (self.root / 'repeated').write_bytes(b'')

        @contextlib.contextmanager
        def repeated_entries(fd):
            yield iter([types.SimpleNamespace(name='repeated'), types.SimpleNamespace(name='repeated')])

        with self.root_handle() as fd, mock.patch.object(diag.os, 'scandir', side_effect=repeated_entries):
            result = diag.collect(fd)
        self.assertIn('CHANGED', result['errors'])
        self.assertFalse(result['stable'])

    def test_transient_scan_error_is_sanitized_and_incomplete(self):
        with self.root_handle() as fd, mock.patch.object(diag.os, 'scandir', side_effect=PermissionError('PRIVATE ERROR PATH')):
            result = diag.collect(fd)
        self.assertIn('IO_ERROR', result['errors'])
        self.assertFalse(result['complete'])
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_inode_replaced_between_passes_is_changed(self):
        source = self.root / 'record'
        source.write_bytes(b'old')
        original = diag.scan_pass
        calls = 0

        def replace_after_first(*args, **kwargs):
            nonlocal calls
            value = original(*args, **kwargs)
            calls += 1
            if calls == 1:
                source.rename(self.base / 'old-record')
                source.write_bytes(b'new')
            return value

        with mock.patch.object(diag, 'scan_pass', side_effect=replace_after_first):
            result = self.collect()
        self.assertIn('CHANGED', result['errors'])
        self.assertFalse(result['stable'])

    def test_link_count_changed_between_passes_is_changed(self):
        source = self.root / 'record'
        source.write_bytes(b'old')
        original = diag.scan_pass
        calls = 0

        def relink_after_first(*args, **kwargs):
            nonlocal calls
            value = original(*args, **kwargs)
            calls += 1
            if calls == 1:
                os.link(source, self.base / 'external-link')
            return value

        with mock.patch.object(diag, 'scan_pass', side_effect=relink_after_first):
            result = self.collect()
        self.assertFalse(result['stable'])
        self.assertFalse(result['hardlinkGroups'][0]['membershipEqualsNlink'])

    def test_root_link_count_changed_between_passes_is_changed(self):
        actual_fstat = os.fstat
        with self.root_handle() as fd:
            calls = 0

            def changing_root(other_fd):
                nonlocal calls
                info = actual_fstat(other_fd)
                if other_fd != fd:
                    return info
                calls += 1
                return types.SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino,
                                             st_mode=info.st_mode, st_nlink=info.st_nlink + (calls > 1))

            with mock.patch.object(diag.os, 'fstat', side_effect=changing_root):
                result = diag.collect(fd)
        self.assertFalse(result['stable'])
        self.assertIn('CHANGED', result['errors'])

    def test_group_and_member_bounds_do_not_claim_full_report(self):
        for index in range(3):
            source = self.root / ('group-' + str(index))
            source.write_bytes(b'')
            os.link(source, self.root / ('alias-' + str(index)))
        with mock.patch.object(diag, 'MAX_GROUPS', 1), mock.patch.object(diag, 'MAX_MEMBERS', 1):
            result = self.collect()
        self.assertTrue(result['stable'])
        self.assertTrue(result['reportTruncated'])
        self.assertFalse(result['complete'])
        self.assertEqual(len(result['hardlinkGroups']), 1)
        self.assertEqual(len(result['hardlinkGroups'][0]['members']), 1)
        self.assertTrue(result['hardlinkGroups'][0]['membersTruncated'])

    def test_large_report_is_prebudgeted_and_marked_truncated(self):
        entries = {}
        for group in range(150):
            for member in range(3):
                name = '/'.join(['unknown-segment-' + str(i) for i in range(12)] +
                                ['group-' + str(group) + '-member-' + str(member)])
                entries[name] = (1, group + 1000, stat.S_IFREG | 0o600, 3)
        with self.root_handle() as fd, mock.patch.object(diag, 'scan_pass', return_value=(entries, [])):
            result = diag.collect(fd)
        self.assertTrue(result['stable'])
        self.assertTrue(result['reportTruncated'])
        self.assertFalse(result['complete'])
        self.assertLess(len(result['hardlinkGroups']), diag.MAX_GROUPS)
        self.assertLessEqual(len(diag.encode_report({'scan': result})), diag.MAX_BYTES)

    def test_dot_git_is_opaque_but_its_entry_type_is_checked(self):
        git = self.root / '.git'
        git.mkdir()
        (git / 'private-name').write_bytes(b'PRIVATE')
        self.assertEqual(self.collect()['secondPassEntries'], 1)
        git.rename(self.base / 'git-metadata')
        git.symlink_to(self.base / 'git-metadata', target_is_directory=True)
        result = self.collect()
        self.assertFalse(result['stable'])
        self.assertIn('UNSAFE', result['errors'])
        self.assertNotIn('private-name', json.dumps(result))


class OutputTests(DiagnosticFixture):
    def assert_main_refuses_output_drift(self, mutate):
        """Exercise real main/collection/publication with identity checks isolated."""
        sentinel = b'existing=SENTINEL_UNCHANGED\n'
        self.output.write_bytes(sentinel)
        actual_collect = diag.collect
        actual_mkdir = os.mkdir
        changed_outputs = []
        diagnostic_creates = []
        root_fd = diag.open_directory(self.root)

        def change_during_collect(fd):
            changed_outputs.extend(mutate() or [self.output])
            return actual_collect(fd)

        def observed_mkdir(path, *args, **kwargs):
            if os.fsdecode(path).startswith('lottery-g3-pathdiag-'):
                diagnostic_creates.append(path)
            return actual_mkdir(path, *args, **kwargs)

        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(diag, 'checked_root', return_value=(self.root, root_fd, 'a' * 40)), \
                mock.patch.object(diag, 'identity', return_value={'authority': 'SYNTHETIC_TEST_ONLY'}), \
                mock.patch.object(diag, 'collect', side_effect=change_during_collect) as collect, \
                mock.patch.object(diag.os, 'mkdir', side_effect=observed_mkdir), \
                mock.patch.object(diag.os, 'write', wraps=os.write) as write, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assert_refused(diag.main)
        collect.assert_called_once()
        self.assertEqual(diagnostic_creates, [], 'output drift must be rejected before creating diagnostics')
        write.assert_not_called()
        self.assertTrue(changed_outputs)
        for output in changed_outputs:
            self.assertEqual(output.read_bytes(), sentinel)
        self.assertFalse(list(self.base.rglob('lottery-g3-pathdiag-*')))

    def nest_runner(self):
        anchor = self.base / 'runner-ancestor'
        anchor.mkdir(mode=0o700)
        self.temp.rename(anchor / 'runner')
        self.temp = anchor / 'runner'
        self.commands = self.temp / '_runner_file_commands'
        self.output = self.commands / 'set_output_synthetic'
        self.env.update(RUNNER_TEMP=str(self.temp), GITHUB_OUTPUT=str(self.output))
        return anchor

    def test_main_runner_becoming_world_writable_is_refused_before_creation(self):
        self.assert_main_refuses_output_drift(lambda: self.temp.chmod(0o777))

    def test_main_output_parent_moved_outside_runner_is_refused_before_creation(self):
        moved = self.base / 'moved-output-parent'

        def mutate():
            self.commands.rename(moved)
            return [moved / self.output.name]

        self.assert_main_refuses_output_drift(mutate)

    def test_main_runner_moved_and_same_path_recreated_is_refused_before_creation(self):
        moved = self.base / 'moved-runner'

        def mutate():
            self.temp.rename(moved)
            self.temp.mkdir(mode=0o700)
            return [moved / '_runner_file_commands' / self.output.name]

        self.assert_main_refuses_output_drift(mutate)

    def test_main_output_parent_swapped_for_same_mode_directory_is_refused(self):
        moved = self.temp / 'old-output-parent'

        def mutate():
            self.commands.rename(moved)
            self.commands.mkdir(mode=0o700)
            self.output.write_bytes(b'existing=SENTINEL_UNCHANGED\n')
            self.output.chmod(0o600)
            return [moved / self.output.name, self.output]

        self.assert_main_refuses_output_drift(mutate)

    def test_main_runner_ancestor_identity_swap_is_refused_before_creation(self):
        anchor = self.nest_runner()
        moved = self.base / 'old-runner-ancestor'

        def mutate():
            anchor.rename(moved)
            anchor.mkdir(mode=0o700)
            (moved / 'runner').rename(self.temp)

        self.assert_main_refuses_output_drift(mutate)

    def test_main_initial_safe_runner_mode_is_preserved(self):
        self.assert_main_refuses_output_drift(lambda: self.temp.chmod(0o750))

    def test_main_initial_safe_output_parent_mode_is_preserved(self):
        self.assert_main_refuses_output_drift(lambda: self.commands.chmod(0o750))

    def test_main_initial_safe_output_leaf_mode_is_preserved(self):
        self.assert_main_refuses_output_drift(lambda: self.output.chmod(0o640))

    def test_main_initial_runner_ancestor_mode_is_preserved(self):
        anchor = self.nest_runner()
        self.assert_main_refuses_output_drift(lambda: anchor.chmod(0o750))

    def test_main_output_leaf_identity_swap_is_refused_before_creation(self):
        moved = self.commands / 'old-output'

        def mutate():
            self.output.rename(moved)
            self.output.write_bytes(b'existing=SENTINEL_UNCHANGED\n')
            self.output.chmod(0o600)
            return [moved, self.output]

        self.assert_main_refuses_output_drift(mutate)

    def test_main_initial_output_anchor_owners_are_preserved(self):
        anchor = self.nest_runner()
        actual_stat, actual_fstat = os.stat, os.fstat
        for target in (anchor, self.temp, self.commands, self.output):
            with self.subTest(target=target.name):
                original = actual_stat(target)
                changed = False

                def altered_owner(info):
                    if changed and (info.st_dev, info.st_ino) == (original.st_dev, original.st_ino):
                        fields = {key: getattr(info, key) for key in dir(info) if key.startswith('st_')}
                        fields['st_uid'] = original.st_uid + 1
                        return types.SimpleNamespace(**fields)
                    return info

                def mutate():
                    nonlocal changed
                    changed = True

                with mock.patch.object(diag.os, 'stat', side_effect=lambda *a, **kw: altered_owner(actual_stat(*a, **kw))), \
                        mock.patch.object(diag.os, 'fstat', side_effect=lambda *a, **kw: altered_owner(actual_fstat(*a, **kw))):
                    self.assert_main_refuses_output_drift(mutate)

    def test_exact_new_file_readonly_and_append_only_output(self):
        self.output.write_bytes(b'existing=unchanged\n')
        raw = b'{"status":"DIAGNOSTIC_ONLY"}\n'
        with self.output_handles() as (fd, channel):
            name = diag.publish(fd, channel, raw)
        self.assertRegex(name, '^' + diag.DIRECTORY_RE + '$')
        folder = self.temp / name
        self.assertEqual([p.name for p in folder.iterdir()], ['diagnostic.json'])
        self.assertEqual((folder / 'diagnostic.json').read_bytes(), raw)
        self.assertEqual(stat.S_IMODE(folder.stat().st_mode), 0o500)
        self.assertEqual(stat.S_IMODE((folder / 'diagnostic.json').stat().st_mode), 0o400)
        self.assertEqual(self.output.read_text(), 'existing=unchanged\ndiagnostic_relative_path=' + name + '/diagnostic.json\n')

    def test_unsafe_runner_temp_permissions(self):
        self.temp.chmod(0o777)
        self.assert_refused(lambda: diag.output_handles(self.root, self.env))
        self.assertEqual(self.output.read_bytes(), b'')

    def test_unsafe_output_parent_permissions(self):
        self.commands.chmod(0o777)
        self.assert_refused(lambda: diag.output_handles(self.root, self.env))
        self.assertEqual(self.output.read_bytes(), b'')

    def test_unsafe_output_leaf_permissions(self):
        self.output.chmod(0o666)
        self.assert_refused(lambda: diag.output_handles(self.root, self.env))
        self.assertEqual(self.output.read_bytes(), b'')

    def test_temp_cannot_be_checkout_or_its_ancestor(self):
        for path in (self.root, self.base, self.root / 'nested'):
            with self.subTest(path=path):
                env = dict(self.env, RUNNER_TEMP=str(path))
                self.assert_refused(lambda: diag.output_handles(self.root, env))

    def test_output_cannot_be_outside_temp(self):
        sentinel = self.base / 'outside-output'
        sentinel.write_bytes(b'SENTINEL')
        self.assert_refused(lambda: diag.output_handles(self.root, dict(self.env, GITHUB_OUTPUT=str(sentinel))))
        self.assertEqual(sentinel.read_bytes(), b'SENTINEL')

    def test_output_symlink_hardlink_fifo_directory_refused(self):
        sentinel = self.base / 'sentinel'
        sentinel.write_bytes(b'UNCHANGED')
        for variant in ('symlink', 'hardlink', 'fifo', 'directory'):
            with self.subTest(variant=variant):
                self.output.unlink(missing_ok=True)
                if variant == 'symlink':
                    self.output.symlink_to(sentinel)
                elif variant == 'hardlink':
                    os.link(sentinel, self.output)
                elif variant == 'fifo':
                    os.mkfifo(self.output)
                elif variant == 'directory':
                    self.output.mkdir()
                try:
                    self.assert_refused(lambda: diag.output_handles(self.root, self.env))
                    self.assertEqual(sentinel.read_bytes(), b'UNCHANGED')
                finally:
                    if variant == 'directory':
                        self.output.rmdir()
                    else:
                        self.output.unlink()

    def test_socket_output_branch_refused_with_synthetic_lstat(self):
        actual_stat = os.stat

        def socket_stat(path, *args, **kwargs):
            info = actual_stat(path, *args, **kwargs)
            if path == self.output.name and kwargs.get('dir_fd') is not None:
                return types.SimpleNamespace(st_mode=stat.S_IFSOCK | 0o600, st_nlink=1,
                                             st_uid=os.geteuid(), st_size=0)
            return info

        with mock.patch.object(diag.os, 'stat', side_effect=socket_stat):
            self.assert_refused(lambda: diag.output_handles(self.root, self.env))
        self.assertEqual(self.output.read_bytes(), b'')

    def test_output_ancestor_symlink_refused(self):
        alternative = self.base / 'actual-commands'
        alternative.mkdir()
        sentinel = alternative / self.output.name
        sentinel.write_bytes(b'UNCHANGED')
        self.output.unlink()
        self.commands.rmdir()
        self.commands.symlink_to(alternative, target_is_directory=True)
        self.assert_refused(lambda: diag.output_handles(self.root, self.env))
        self.assertEqual(sentinel.read_bytes(), b'UNCHANGED')

    def test_temp_ancestor_symlink_refused(self):
        link = self.base / 'runner-link'
        link.symlink_to(self.temp, target_is_directory=True)
        env = dict(self.env, RUNNER_TEMP=str(link), GITHUB_OUTPUT=str(link / '_runner_file_commands' / self.output.name))
        self.assert_refused(lambda: diag.output_handles(self.root, env))

    def test_existing_random_namespace_never_overwritten(self):
        token = 'f' * 24
        folder = self.temp / ('lottery-g3-pathdiag-' + token)
        folder.mkdir(mode=0o700)
        sentinel = folder / 'diagnostic.json'
        sentinel.write_bytes(b'KEEP')
        with self.output_handles() as (fd, channel), mock.patch.object(diag.secrets, 'token_hex', return_value=token):
            self.assert_refused(lambda: diag.publish(fd, channel, b'{}'))
        self.assertEqual(sentinel.read_bytes(), b'KEEP')
        self.assertEqual(self.output.read_bytes(), b'')

    def test_existing_diagnostic_in_new_namespace_never_overwritten(self):
        actual_mkdir = os.mkdir
        created = []

        def prepopulate(name, *args, **kwargs):
            actual_mkdir(name, *args, **kwargs)
            path = self.temp / name / diag.FILE_NAME
            path.write_bytes(b'KEEP')
            created.append(path)

        with self.output_handles() as (fd, channel), mock.patch.object(diag.os, 'mkdir', side_effect=prepopulate):
            self.assert_refused(lambda: diag.publish(fd, channel, b'{}'))
        self.assertEqual(created[0].read_bytes(), b'KEEP')
        self.assertEqual(self.output.read_bytes(), b'')

    def test_replaced_output_handle_is_refused_before_creation(self):
        with self.output_handles() as (fd, channel):
            self.output.rename(self.commands / 'old-output')
            self.output.write_bytes(b'KEEP')
            self.assert_refused(lambda: diag.publish(fd, channel, b'{}'))
        self.assertEqual(self.output.read_bytes(), b'KEEP')
        self.assertFalse(list(self.temp.glob('lottery-g3-pathdiag-*')))

    def test_directory_swap_before_publication_is_refused(self):
        sentinel = self.base / 'private-data'
        sentinel.write_bytes(b'KEEP')
        actual_fsync = os.fsync
        swapped = False

        def swap_after_write(fd):
            nonlocal swapped
            actual_fsync(fd)
            if not swapped:
                swapped = True
                folder, = self.temp.glob('lottery-g3-pathdiag-*')
                folder.rename(self.temp / 'moved-diagnostic')
                folder.mkdir(mode=0o700)
                (folder / 'diagnostic.json').symlink_to(sentinel)

        with self.output_handles() as (fd, channel), mock.patch.object(diag.os, 'fsync', side_effect=swap_after_write):
            self.assert_refused(lambda: diag.publish(fd, channel, b'{}'))
        self.assertEqual(sentinel.read_bytes(), b'KEEP')
        self.assertEqual(self.output.read_bytes(), b'')

    def test_output_size_limit_refuses_before_creation(self):
        with self.output_handles() as (fd, channel):
            self.assert_refused(lambda: diag.publish(fd, channel, b'x' * (diag.MAX_BYTES + 1)))
        self.assertFalse(list(self.temp.glob('lottery-g3-pathdiag-*')))
        self.assertEqual(self.output.read_bytes(), b'')


class IdentityAndCliTests(DiagnosticFixture):
    def initialize_foreign_git(self):
        foreign = self.base / 'foreign-checkout'
        foreign.mkdir()
        env = dict(PATH='/usr/bin:/bin', HOME=str(self.base), LC_ALL='C',
                   GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        commands = [
            ['/usr/bin/git', 'init', '--quiet', str(foreign)],
            ['/usr/bin/git', '-C', str(foreign), 'add', '.'],
            ['/usr/bin/git', '-C', str(foreign), '-c', 'user.name=Synthetic Test',
             '-c', 'user.email=synthetic@example.invalid', 'commit', '--quiet', '-m', 'foreign fixture'],
        ]
        (foreign / 'foreign-source').write_bytes(b'foreign synthetic checkout only\n')
        for command in commands:
            subprocess.run(command, env=env, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        head = subprocess.check_output(['/usr/bin/git', '-C', str(foreign), 'rev-parse', 'HEAD'],
                                       env=env).decode('ascii').strip()
        return foreign, head

    def test_real_git_identity_ignores_inherited_git_home_and_xdg_environment(self):
        self.initialize_git()
        foreign, foreign_head = self.initialize_foreign_git()
        self.assertNotEqual(foreign_head, self.env['GITHUB_SHA'])
        poison_home = self.base / 'poison-home'
        poison_home.mkdir()
        (poison_home / '.gitconfig').write_text('INVALID SYNTHETIC CONFIG [\n')
        poison_xdg = self.base / 'poison-xdg'
        (poison_xdg / 'git').mkdir(parents=True)
        (poison_xdg / 'git/config').write_text('INVALID SYNTHETIC CONFIG [\n')
        inherited = dict(
            PATH='/synthetic-no-git-on-path', HOME=str(poison_home), XDG_CONFIG_HOME=str(poison_xdg),
            GIT_DIR=str(foreign / '.git'), GIT_WORK_TREE=str(self.root),
            GIT_COMMON_DIR=str(foreign / '.git'), GIT_OBJECT_DIRECTORY=str(foreign / '.git/objects'),
            GIT_ALTERNATE_OBJECT_DIRECTORIES=str(foreign / '.git/objects'),
            GIT_CONFIG_SYSTEM=str(poison_home / '.gitconfig'),
            GIT_CONFIG_GLOBAL=str(poison_home / '.gitconfig'), GIT_CONFIG_NOSYSTEM='0',
            GIT_CONFIG_COUNT='not-an-integer', GIT_CONFIG_KEY_0='core.worktree',
            GIT_CONFIG_VALUE_0=str(foreign), GIT_CONFIG_PARAMETERS="'core.worktree=foreign'",
            GIT_NAMESPACE='synthetic-poison', GIT_REPLACE_REF_BASE='refs/synthetic-poison/',
            GIT_DIAGNOSTIC_TEST_SENTINEL='MUST_NOT_INHERIT',
        )
        actual_popen = subprocess.Popen
        with mock.patch.dict(os.environ, inherited, clear=True), \
                mock.patch.object(diag.subprocess, 'Popen', wraps=actual_popen) as popen:
            root, fd, head = diag.checked_root(self.env)
            try:
                self.assertEqual(root, self.root)
                self.assertEqual(head, self.env['GITHUB_SHA'])
            finally:
                os.close(fd)
        self.assertEqual(popen.call_count, 2)

        def option_value(argv, option):
            if option in argv:
                return argv[argv.index(option) + 1]
            return next((arg.split('=', 1)[1] for arg in argv if arg.startswith(option + '=')), None)

        for call in popen.call_args_list:
            argv = call.args[0]
            self.assertEqual(argv[0], '/usr/bin/git')
            self.assertIn('--no-replace-objects', argv)
            self.assertEqual(option_value(argv, '--git-dir'), str(self.root / '.git'))
            self.assertEqual(option_value(argv, '--work-tree'), str(self.root))
            child_environment = call.kwargs.get('env')
            self.assertIsInstance(child_environment, dict, 'Git requires an explicit clean environment')
            for key, value in inherited.items():
                with self.subTest(inherited_variable=key):
                    self.assertNotEqual(child_environment.get(key), value)
        self.assertEqual(self.output.read_bytes(), b'')

    def test_inherited_git_dir_cannot_supply_foreign_checkout_identity(self):
        self.initialize_git()
        foreign, foreign_head = self.initialize_foreign_git()
        env = dict(self.env, GITHUB_SHA=foreign_head)

        def check_foreign_identity():
            _, fd, _ = diag.checked_root(env)
            os.close(fd)

        with mock.patch.dict(os.environ, dict(GIT_DIR=str(foreign / '.git'),
                                             GIT_WORK_TREE=str(self.root)), clear=False):
            self.assert_refused(check_foreign_identity)
        self.assertEqual(self.output.read_bytes(), b'')

    def write_record(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(value, sort_keys=True) + '\n').encode()
        path.write_bytes(raw)
        return path, raw

    def identity_records(self):
        snapshot = {'Assets/source.cs': 'b' * 64,
                    'Assets/Resources/ProbeChinese.otf': 'a6a530f3e7e7a2c299470c42efff2e109fcc0a5be92686b96d5e84a05f3ecb2b'}
        _, raw = self.write_record(diag.TASK + '/evidence/pre-unity-source.json', snapshot)
        self.write_record(diag.TASK + '/ci/g3-preflight.review.json', dict(
            requestId='lottery-g3-20261012-06', sourceFiles={diag.TASK + '/unity/Assets/source.cs': 'b' * 64}))
        cold = dict(sourceCommit=self.env['GITHUB_SHA'], runId='123', runAttempt='2', job='android',
                    status='VERIFIED_BEFORE_UNITY', cachePolicy='LIBRARY_INTERNAL_HARDLINKS_V1',
                    libraryAbsent=True, buildAbsent=True, cacheRestored=False,
                    requestId='lottery-g3-20261012-06', preUnitySourceSha256=hashlib.sha256(raw).hexdigest(),
                    unrelatedSecret='MUST_NOT_EXPORT')
        self.write_record(diag.TASK + '/evidence/g3/android/cold-build-baseline.json', cold)
        return cold

    def test_identity_observations_are_separate_and_non_authoritative(self):
        self.identity_records()
        with self.root_handle() as fd:
            result = diag.identity(fd, self.env['GITHUB_SHA'], self.env)
        self.assertEqual(result['expected']['runId'], '123')
        self.assertEqual(result['observed']['runId'], '123')
        self.assertTrue(all(value == 'MATCH' for value in result['validation'].values()))
        self.assertIn('NOT_SOURCE_APPROVAL', result['authority'])
        self.assertNotIn('MUST_NOT_EXPORT', json.dumps(result))
        self.assertNotIn('PASS', json.dumps(result))

    def test_stale_identity_remains_observed_without_validation(self):
        self.identity_records()
        with self.root_handle() as fd:
            result = diag.identity(fd, self.env['GITHUB_SHA'], dict(self.env, GITHUB_RUN_ID='999'))
        self.assertEqual(result['expected']['runId'], '999')
        self.assertEqual(result['observed']['runId'], '123')
        self.assertEqual(result['validation']['runId'], 'MISMATCH')

    def test_invalid_identity_fields_and_missing_records_are_sanitized(self):
        with self.root_handle() as fd:
            result = diag.identity(fd, 'a' * 40, dict(self.env, GITHUB_RUN_ID='PRIVATE\n::error::'))
        self.assertIsNone(result['expected']['runId'])
        self.assertIsNone(result['observed']['runId'])
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertEqual(result['recordReadStatus']['cold'], 'MISSING')

    def test_known_record_symlink_or_hardlink_never_read(self):
        sentinel = self.base / 'private.json'
        sentinel.write_bytes(b'{"private":"KEEP"}')
        for variant in ('symlink', 'hardlink'):
            with self.subTest(variant=variant):
                path = self.root / 'record.json'
                if variant == 'symlink':
                    path.symlink_to(sentinel)
                else:
                    os.link(sentinel, path)
                with self.root_handle() as fd, mock.patch.object(diag.os, 'read', side_effect=AssertionError('unsafe read')):
                    value, digest, status = diag.read_known(fd, 'record.json', 1024)
                self.assertIsNone(value)
                self.assertIsNone(digest)
                self.assertEqual(status, 'UNSAFE')
                path.unlink()
        self.assertEqual(sentinel.read_bytes(), b'{"private":"KEEP"}')

    def test_known_record_in_place_rewrite_is_detected(self):
        path = self.root / 'record.json'
        path.write_bytes(b'{"value":"old"}')
        actual_read = os.read

        def mutate_after_read(fd, size):
            data = actual_read(fd, size)
            path.write_bytes(b'{"value":"new"}')
            return data

        with self.root_handle() as fd, mock.patch.object(diag.os, 'read', side_effect=mutate_after_read):
            value, digest, status = diag.read_known(fd, 'record.json', 1024)
        self.assertEqual(status, 'CHANGED')
        self.assertIsNone(value)

    def test_root_symlink_ancestor_is_rejected(self):
        link = self.base / 'checkout-link'
        link.symlink_to(self.root, target_is_directory=True)
        self.assert_refused(lambda: diag.open_directory(link))

    def test_root_git_symlink_is_refused_before_git_exec(self):
        outside = self.base / 'outside-git'
        outside.mkdir()
        (self.root / '.git').symlink_to(outside, target_is_directory=True)
        with mock.patch.object(diag, 'git_value', side_effect=AssertionError('Git must not follow unsafe metadata')) as child:
            self.assert_refused(lambda: diag.checked_root(self.env))
        child.assert_not_called()

    def test_cli_real_git_reports_only_diagnostic_status(self):
        env = self.initialize_git()
        source = self.root / 'source-hardlink'
        source.write_bytes(b'PRIVATE_CONTENT')
        os.link(source, self.root / 'alias-hardlink')
        completed = subprocess.run([sys.executable, '-I', '-B', str(Path(diag.__file__).resolve())],
                                   env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        self.assertIn(b'status=DIAGNOSTIC_ONLY', completed.stdout)
        self.assertNotIn(b'PASS', completed.stdout)
        line = self.output.read_text().strip()
        self.assertRegex(line, r'^diagnostic_relative_path=' + diag.DIRECTORY_RE + '/diagnostic.json$')
        report = json.loads((self.temp / line.split('=', 1)[1]).read_text())
        self.assertEqual(report['status'], 'DIAGNOSTIC_ONLY')
        self.assertEqual(report['acceptance'], 'NONE')
        self.assertEqual(report['sourceAudit'], 'NOT_EVALUATED')
        self.assertNotIn('PRIVATE_CONTENT', json.dumps(report))

    def test_cli_git_failure_does_not_print_git_or_exception_paths(self):
        env = dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), HOME=str(self.base), **self.env)
        completed = subprocess.run([sys.executable, '-I', '-B', str(Path(diag.__file__).resolve())],
                                   env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, b'')
        self.assertRegex(completed.stderr.decode(), r'^G3_PATH_DIAGNOSTIC_ERROR code=[A-Z_]+\n$')
        self.assertNotIn(str(self.root).encode(), completed.stderr)
        self.assertNotIn(b'fatal:', completed.stderr)
        self.assertNotIn(b'Traceback', completed.stderr)
        self.assertEqual(self.output.read_bytes(), b'')

    def test_cli_head_mismatch_is_refused_without_artifact(self):
        env = self.initialize_git()
        env['GITHUB_SHA'] = '0' * 40
        completed = subprocess.run([sys.executable, '-I', '-B', str(Path(diag.__file__).resolve())],
                                   env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(self.output.read_bytes(), b'')
        self.assertFalse(list(self.temp.glob('lottery-g3-pathdiag-*')))


if __name__ == '__main__':
    unittest.main()
