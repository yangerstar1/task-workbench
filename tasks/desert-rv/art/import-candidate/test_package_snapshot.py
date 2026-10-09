"""Pinned official-package/security fixtures; no Unity or acceptance claims."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import strict_output as s
from package_test_fixture import install_package_snapshot


class PackageSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)/'unity'
        self.snapshot = install_package_snapshot(self.project)
        self.deps = [s.PACKAGE_SHADER, s.PACKAGE_ASSET_VERSION]

    def metadata(self, edit):
        path = self.snapshot/'manifest.json'; value = json.loads(path.read_text())
        edit(value); path.write_text(json.dumps(value))

    def rejects(self, code='STRICT_PACKAGE'):
        with self.assertRaisesRegex(s.StrictError, code): s.dependency_digest(self.project, self.deps)

    def copy_direct(self):
        for name in s.PACKAGE_FILES:
            target = self.project/name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.snapshot/name, target)

    def test_pins_match_independent_native_observations(self):
        self.assertEqual(s.PACKAGE_FILES, {
            'Packages/com.unity.render-pipelines.universal/Editor/AssetVersion.cs': (148, '96ed27e15286cda1fdada6923e804887b6447a905b38360e0f5561f79cd0344c', None),
            'Packages/com.unity.render-pipelines.universal/Editor/AssetVersion.cs.meta': (243, 'e7ec88783b56ae3a5adbe60d3ab71fd3b6fe269932af20218d4cc00eb3879868', 'd0353a89b1f911e48b9e16bdc9f2e058'),
            'Packages/com.unity.render-pipelines.universal/Shaders/Lit.shader': (22877, '6f4648b6b5271132cfed1d7d7c771ba0a73ef7972470d6694047804d259c0997', None),
            'Packages/com.unity.render-pipelines.universal/Shaders/Lit.shader.meta': (217, 'f0db005307ffe5480c40a402ca5bfb0b3726259031a86e255e49626228ceb008', '933532a4fcc9baf4fa0491de14d08ed7')})

    def test_canonical_paths_and_original_framing_equal_direct_bytes(self):
        expected = hashlib.sha256()
        for name in sorted(self.deps):
            for item in (name, name+'.meta'):
                data = (self.snapshot/item).read_bytes(); encoded = item.encode('utf-8')
                expected.update(str(len(encoded)).encode()+b':'+encoded+str(len(data)).encode()+b':'+data)
        actual = s.dependency_digest(self.project, self.deps)
        self.assertEqual(actual, expected.hexdigest())
        self.copy_direct(); self.assertEqual(s.dependency_digest(self.project, self.deps), actual)
        shutil.rmtree(self.snapshot); self.assertEqual(s.dependency_digest(self.project, self.deps), actual)

    def test_meta_guids_come_from_verified_official_files(self):
        self.assertEqual(s.dependency_meta_guid(self.project, s.PACKAGE_ASSET_VERSION), 'd0353a89b1f911e48b9e16bdc9f2e058')
        self.assertEqual(s.dependency_meta_guid(self.project, s.PACKAGE_SHADER), '933532a4fcc9baf4fa0491de14d08ed7')

    def test_missing_snapshot_and_missing_direct_are_not_hash_omissions(self):
        shutil.rmtree(self.snapshot); self.rejects('STRICT_PACKAGE_SNAPSHOT_REQUIRED')

    def test_missing_one_file_rejected(self):
        (self.snapshot/s.PACKAGE_ASSET_VERSION).unlink(); self.rejects('ALLOWLIST')

    def test_added_file_rejected(self):
        (self.snapshot/'private.txt').write_text('not exported'); self.rejects('ALLOWLIST')

    def test_added_empty_directory_rejected(self):
        (self.snapshot/'extra').mkdir(); self.rejects('ALLOWLIST')

    def test_snapshot_link_rejected(self):
        target=self.project/'original-snapshot';self.snapshot.rename(target);self.snapshot.symlink_to(target, target_is_directory=True)
        self.rejects('UNSAFE')

    def test_snapshot_nested_directory_link_rejected(self):
        folder=self.snapshot/'Packages';target=self.project/'held';folder.rename(target);folder.symlink_to(target, target_is_directory=True)
        self.rejects('UNSAFE')

    def test_snapshot_file_link_rejected(self):
        path=self.snapshot/s.PACKAGE_SHADER;target=self.project/'held';path.rename(target);path.symlink_to(target)
        self.rejects('UNSAFE')

    def test_direct_corruption_cannot_be_hidden_by_valid_snapshot(self):
        target=self.project/s.PACKAGE_SHADER;target.parent.mkdir(parents=True);target.write_bytes(b'x'*22877)
        self.rejects('FILE_HASH')

    def test_broken_direct_link_cannot_fallback(self):
        target=self.project/s.PACKAGE_SHADER;target.parent.mkdir(parents=True);target.symlink_to(self.project/'missing')
        self.rejects('DIRECT_UNSAFE')

    def test_direct_directory_cannot_fallback(self):
        (self.project/s.PACKAGE_SHADER).mkdir(parents=True); self.rejects('STRICT_UNSAFE_FILE')

    def test_direct_parent_link_cannot_fallback(self):
        target=self.project/'linked';target.mkdir();(self.project/'Packages'/s.PACKAGE_NAME).symlink_to(target,target_is_directory=True)
        self.rejects('DIRECT_UNSAFE')

    def test_oversized_payload_rejected_before_hashing(self):
        with (self.snapshot/s.PACKAGE_SHADER).open('wb') as stream: stream.truncate(512*1024**2+1)
        self.rejects('STRICT_OVERSIZED_FILE')

    def test_tampered_same_size_payload_rejected(self):
        path=self.snapshot/s.PACKAGE_SHADER;data=path.read_bytes();path.write_bytes(b'x'+data[1:]);self.rejects('FILE_HASH')

    def test_current_manifest_bytes_must_match_snapshot(self):
        path=self.project/'Packages/manifest.json';path.write_text(path.read_text()+'\n');self.rejects('SNAPSHOT_STALE')

    def test_current_lock_bytes_must_match_snapshot(self):
        path=self.project/'Packages/packages-lock.json';path.write_text(path.read_text()+'\n');self.rejects('SNAPSHOT_STALE')

    def test_rewritten_snapshot_hash_cannot_bless_changed_manifest_bytes(self):
        path=self.project/'Packages/manifest.json';path.write_text(path.read_text()+'\n')
        self.metadata(lambda x:x.update(manifestSha256=s.sha(path)))
        self.rejects('STRICT_PACKAGE_CONTROL_PIN')

    def test_rewritten_snapshot_hash_cannot_bless_changed_lock_bytes(self):
        path=self.project/'Packages/packages-lock.json';path.write_text(path.read_text()+'\n')
        self.metadata(lambda x:x.update(lockSha256=s.sha(path)))
        self.rejects('STRICT_PACKAGE_CONTROL_PIN')

    def test_manifest_version_pin_independent_of_claimed_hash(self):
        path=self.project/'Packages/manifest.json';path.write_text(path.read_text().replace('17.3.0','17.2.0'))
        self.metadata(lambda x:x.update(manifestSha256=s.sha(path)));self.rejects('MANIFEST_PIN')

    def test_lock_source_pin_independent_of_claimed_hash(self):
        path=self.project/'Packages/packages-lock.json';path.write_text(path.read_text().replace('builtin','registry'))
        self.metadata(lambda x:x.update(lockSha256=s.sha(path)));self.rejects('LOCK_PIN')

    def test_editor_pin(self):
        (self.project/'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.3.20f1\n');self.rejects('EDITOR_PIN')

    def test_duplicate_json_key_rejected(self):
        path=self.snapshot/'manifest.json';path.write_text(path.read_text().replace('"schema": 1','"schema": 1, "schema": 1'))
        self.rejects('STRICT_DUPLICATE_JSON_KEY')

    def test_exact_snapshot_schema(self):
        self.metadata(lambda x:x.update(secret='unexpected'));self.rejects('STRICT_SCHEMA_MISMATCH')

    def test_exact_snapshot_file_row_schema(self):
        self.metadata(lambda x:x['files'][0].update(extra='unexpected'));self.rejects('STRICT_SCHEMA_MISMATCH')

    def test_exact_snapshot_file_set(self):
        self.metadata(lambda x:x['files'].__setitem__(0,dict(x['files'][1])));self.rejects('SNAPSHOT_FILES')

    def test_snapshot_path_traversal_rejected(self):
        self.metadata(lambda x:x['files'][0].update(path='../secret'));self.rejects('SNAPSHOT_FILES')

    def test_manifest_hash_cannot_authorize_unpinned_payload(self):
        name=s.PACKAGE_ASSET_VERSION;path=self.snapshot/name;path.write_bytes(b'x'*148)
        self.metadata(lambda x:next(row for row in x['files'] if row['path']==name).update(sha256=s.sha(path)))
        self.rejects('SNAPSHOT_FILE_PIN')

    def test_boolean_schema_and_size_not_integers(self):
        self.metadata(lambda x:x.update(schema=True));self.rejects('SNAPSHOT_IDENTITY')

    def test_arbitrary_package_not_allowed_even_if_real_direct_file(self):
        for name in ('Packages/com.unity.render-pipelines.universal/Editor/Other.cs',
                     'Packages/com.unity.other/file.txt', s.PACKAGE_SHADER+'.meta', s.PACKAGE_PREFIX+'../secret'):
            with self.subTest(name=name),self.assertRaisesRegex(s.StrictError,'STRICT_DEPENDENCY_PATH'):
                s.dependency_digest(self.project,[name])

    def test_freeze_includes_controls_and_all_four_private_files(self):
        snapshot=s.dependency_snapshot(self.project,self.deps)
        self.assertEqual(len(snapshot),8)
        self.assertIn(self.project/'ProjectSettings/ProjectVersion.txt',snapshot)
        self.assertTrue(all(self.snapshot/name in snapshot for name in s.PACKAGE_FILES))
        s.verify_dependency_snapshot(self.project,self.deps,snapshot)

    def test_freeze_rejects_direct_appearance_even_identical(self):
        snapshot=s.dependency_snapshot(self.project,self.deps);self.copy_direct()
        with self.assertRaisesRegex(s.StrictError,'DEPENDENCY_INPUT_CHANGED'):s.verify_dependency_snapshot(self.project,self.deps,snapshot)

    def test_freeze_rejects_added_empty_directory(self):
        snapshot=s.dependency_snapshot(self.project,self.deps);(self.snapshot/'extra').mkdir()
        with self.assertRaisesRegex(s.StrictError,'ALLOWLIST'):s.verify_dependency_snapshot(self.project,self.deps,snapshot)

    def test_trace_reports_canonical_name_and_real_snapshot_bytes(self):
        text=io.StringIO()
        with redirect_stdout(text):s.dependency_digest(self.project,self.deps,trace=True)
        rows=[json.loads(line.split(' ',1)[1]) for line in text.getvalue().splitlines()]
        self.assertEqual(rows[0]['hashedFileCount'],4);self.assertEqual(rows[0]['missingFileCount'],0)
        self.assertTrue(all(row['exists'] and not row['projectExists'] for row in rows[1:]))
        self.assertEqual({row['file'] for row in rows[1:]},set(s.PACKAGE_FILES))
        self.assertNotIn('CandidatePackageSnapshot',text.getvalue())


class WeaponPackageScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'Candidate.prefab'

    def reject(self,text):
        import weapon_output as w
        for prefix in ('','%YAML 1.1\n--- !u!114 &1\n'):
            with self.subTest(prefix=prefix):
                self.path.write_text(prefix+text)
                with self.assertRaisesRegex(s.StrictError,'WEAPON_PACKAGE_SCRIPT_SCOPE'):
                    w._reject_package_script_reference(self.path)

    def test_quoted_reserved_guid_rejected(self):
        self.reject('guid: "'+s.PACKAGE_ASSET_VERSION_GUID+'"\n')

    def test_uppercase_reserved_guid_rejected(self):
        self.reject('guid: '+s.PACKAGE_ASSET_VERSION_GUID.upper()+'\n')

    def test_escaped_reserved_guid_rejected(self):
        self.reject('guid: "\\x64'+s.PACKAGE_ASSET_VERSION_GUID[1:]+'"\n')

    def test_duplicate_key_cannot_hide_reserved_guid(self):
        self.reject('guid: '+s.PACKAGE_ASSET_VERSION_GUID+'\nguid: '+('0'*32)+'\n')

    def test_alias_cannot_hide_reserved_guid(self):
        self.reject('source: &ref "'+s.PACKAGE_ASSET_VERSION_GUID+'"\nreference: *ref\n')

    def test_reserved_guid_in_later_document_rejected(self):
        self.reject('guid: '+('0'*32)+'\n---\nguid: '+s.PACKAGE_ASSET_VERSION_GUID+'\n')

    def test_unrelated_alias_cycle_is_bounded(self):
        import weapon_output as w
        self.path.write_text('value: &cycle [*cycle]\nguid: '+('0'*32)+'\n')
        w._reject_package_script_reference(self.path)


class PackageExporterIntegrationTests(unittest.TestCase):
    def armored(self):
        from test_strict_output import StrictExportTests
        case=StrictExportTests();case.setUp();self.addCleanup(case.tearDown)
        install_package_snapshot(case.project)
        case.imp['dependencies'] += [s.PACKAGE_SHADER,s.PACKAGE_ASSET_VERSION]
        case.imp['dependencySha256']=s.dependency_digest(case.project,case.imp['dependencies'])
        case.cap['dependencySha256']=case.imp['dependencySha256'];return case

    def test_armored_export_uses_snapshot_but_never_exports_package(self):
        case=self.armored();result=case.run_export()
        self.assertEqual(result['status'],'STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED')
        self.assertFalse(any('Package' in row['path'] for row in result['files']))

    def test_armored_snapshot_mutation_during_validation_is_rejected(self):
        case=self.armored();original=s.generated_files
        def change(*args):
            result=original(*args);(case.project/'CandidatePackageSnapshot/extra').mkdir();return result
        with patch.object(s,'generated_files',side_effect=change):case.rejected('STRICT_PACKAGE_SNAPSHOT_ALLOWLIST')

    def test_weapon_snapshot_mutation_during_validation_is_rejected(self):
        from test_weapon_output import WeaponExportTests
        import weapon_output as w
        case=WeaponExportTests();case.setUp();self.addCleanup(case.tearDown);original=w.generated_files
        def change(*args):
            result=original(*args);(case.project/'CandidatePackageSnapshot/extra').mkdir();return result
        with patch.object(w,'generated_files',side_effect=change):case.rejected('STRICT_PACKAGE_SNAPSHOT_ALLOWLIST')

    def test_weapon_candidate_meta_cannot_claim_package_shader_identity(self):
        from test_weapon_output import WeaponExportTests
        import weapon_output as w
        case=WeaponExportTests();case.setUp();self.addCleanup(case.tearDown)
        path=Path(str(case.folder)+'.meta')
        import re
        path.write_text(re.sub(r'^guid: [a-f0-9]{32}$','guid: '+w.URP_LIT_GUID,path.read_text(),flags=re.M))
        case.rejected('WEAPON_META_GUID_DUPLICATE')


    def test_weapon_editor_script_cannot_be_attached_to_prefab(self):
        from test_weapon_output import WeaponExportTests
        case=WeaponExportTests();case.setUp();self.addCleanup(case.tearDown)
        path=case.folder/'Candidate.prefab'
        path.write_text('%YAML 1.1\n--- !u!114 &1\nMonoBehaviour:\n  m_Script: {fileID: 11500000, guid: '+s.PACKAGE_ASSET_VERSION_GUID+', type: 3}\n')
        case.rehash_dependencies();case.rejected('WEAPON_PACKAGE_SCRIPT_SCOPE')

    def test_weapon_editor_script_cannot_be_referenced_by_candidate_meta(self):
        from test_weapon_output import WeaponExportTests
        case=WeaponExportTests();case.setUp();self.addCleanup(case.tearDown)
        path=case.folder/'Source/weapon_hands.fbx.meta'
        path.write_text(path.read_text()+'external: {fileID: 11500000, guid: '+s.PACKAGE_ASSET_VERSION_GUID+', type: 3}\n')
        case.rehash_dependencies();case.rejected('WEAPON_PACKAGE_SCRIPT_SCOPE')



    def test_failed_export_never_publishes_private_package_files(self):
        from test_failed_capture_output import FailedCaptureTests
        case=FailedCaptureTests();case.setUp();self.addCleanup(case.doCleanups)
        install_package_snapshot(case.project)
        case.imp['dependencies'] += [s.PACKAGE_SHADER,s.PACKAGE_ASSET_VERSION]
        case.imp['dependencySha256']=s.dependency_digest(case.project,case.imp['dependencies'])
        case.cap['dependencySha256']=case.imp['dependencySha256']
        self.assertTrue(case.run_export())
        self.assertEqual(case.summary['status'],'FAILED_DIAGNOSTICS')
        self.assertFalse(any('Package' in row['path'] for row in case.summary['files']))
        self.assertFalse(any(path.suffix in ('.cs','.shader','.meta') for path in case.out.rglob('*')))

    def test_failed_export_freezes_private_snapshot_for_shared_validation(self):
        from test_failed_capture_output import FailedCaptureTests
        import failed_capture_output as f
        case=FailedCaptureTests();case.setUp();self.addCleanup(case.doCleanups)
        install_package_snapshot(case.project)
        case.imp['dependencies'] += [s.PACKAGE_SHADER,s.PACKAGE_ASSET_VERSION]
        case.imp['dependencySha256']=s.dependency_digest(case.project,case.imp['dependencies'])
        case.cap['dependencySha256']=case.imp['dependencySha256'];case.flush()
        snap,_,imp,_,_=f.freeze(case.root)
        with tempfile.TemporaryDirectory() as temporary:
            frozen=Path(temporary);snap.materialize(frozen)
            self.assertEqual(s.dependency_digest(frozen/'unity',imp['dependencies']),imp['dependencySha256'])
        self.assertIn(case.project/'CandidatePackageSnapshot/manifest.json',snap.data)
        snap.verify();(case.project/'CandidatePackageSnapshot/extra').mkdir()
        with self.assertRaises(s.StrictError):snap.verify()


class PouncerPackageExporterTests(unittest.TestCase):
    def test_pouncer_candidate_meta_cannot_claim_package_shader_identity(self):
        from test_pouncer_output import PouncerExportTests
        import pouncer_output as p
        PouncerExportTests.setUpClass();case=PouncerExportTests();case.setUp();self.addCleanup(case.tearDown)
        path=Path(str(case.folder)+'.meta')
        import re
        path.write_text(re.sub(r'^guid: [a-f0-9]{32}$','guid: '+p.URP_LIT_GUID,path.read_text(),flags=re.M))
        case.rejected('POUNCER_META_GUID_DUPLICATE')


    def test_pouncer_editor_script_cannot_be_attached_to_prefab(self):
        from test_pouncer_output import PouncerExportTests
        PouncerExportTests.setUpClass();case=PouncerExportTests();case.setUp();self.addCleanup(case.tearDown)
        path=case.folder/'Candidate.prefab'
        path.write_text('%YAML 1.1\n--- !u!114 &1\nMonoBehaviour:\n  m_Script: {fileID: 11500000, guid: '+s.PACKAGE_ASSET_VERSION_GUID+', type: 3}\n')
        case.rehash();case.rejected('POUNCER_DEPENDENCY_GUID_CLOSURE')


    def test_pouncer_editor_script_cannot_be_referenced_by_candidate_meta(self):
        from test_pouncer_output import PouncerExportTests
        PouncerExportTests.setUpClass();case=PouncerExportTests();case.setUp();self.addCleanup(case.tearDown)
        path=case.folder/'Source/pouncer-candidate.fbx.meta'
        path.write_text(path.read_text()+'external: {fileID: 11500000, guid: '+s.PACKAGE_ASSET_VERSION_GUID+', type: 3}\n')
        case.rehash();case.rejected('POUNCER_DEPENDENCY_GUID_CLOSURE')



if __name__=='__main__':unittest.main()
