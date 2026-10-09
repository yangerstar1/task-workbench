"""Filesystem-only prepared-source counterexamples; no synthetic fixture is native acceptance."""
import copy,json,tempfile,unittest,os,stat,subprocess
from pathlib import Path
from unittest import mock
import prepared_source as p

class PreparedSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.patch=mock.patch.multiple(p,ROOT=root,TASK=root/'tasks/desert-rv',PROJECT=root/'tasks/desert-rv/unity',STATE=root/'tasks/desert-rv/unity/JourneyEvidence/JourneyPreparation/state.json',PROOF=root/'tasks/desert-rv/unity/JourneyEvidence/JourneyPreparation/prepared-source.json');self.patch.start()
        for name in ('Assets','Packages','ProjectSettings'):(p.PROJECT/name).mkdir(parents=True)
        self.files={}
        for name in ('Assets/Original.cs','Assets/Original.cs.meta','Packages/manifest.json','ProjectSettings/ProjectVersion.txt'):
            path=self.write(name,b'original source bytes');self.files['tasks/desert-rv/unity/'+name]=path
        self.source={'files':[dict(path=n,sha256=p.sha(f),size=f.stat().st_size) for n,f in self.files.items()],'restoredFiles':[]}
        self.dirs={name:sorted(p.walk(p.PROJECT/name)[1]) for name in ('Assets','Packages','ProjectSettings')}
        self.roots=mock.patch.object(p.original,'SOURCE_ROOTS',('tasks/desert-rv/unity',));self.roots.start()
        source_file=p.TASK/'SOURCE-STATE.json';source_file.write_text(json.dumps(self.source))
        self.identity=mock.patch.object(p.original,'identity',side_effect=lambda:dict(commit='synthetic-source-fixture',sourceStateSha256=p.sha(source_file)));self.identity.start()
        self.original_identity=p.original.identity()
        self.added={}
        # Tiny bytes solely exercise the proof's membership/hash boundary, not Unity formats.
        for name in ('JourneyBootstrap.unity','FirstStation.unity','Scrapyard.unity','NightBeacon.unity','JourneyContent.asset'):
            self.add(p.JOURNEY+'/'+name);self.add(p.JOURNEY+'/'+name+'.meta')
        self.add(p.JOURNEY+'.meta')
    def tearDown(self):self.identity.stop();self.roots.stop();self.patch.stop();self.tmp.cleanup()
    def write(self,path,data=b'generated fixture'):
        full=p.PROJECT/path;full.parent.mkdir(parents=True,exist_ok=True);full.write_bytes(data);return full
    def add(self,path,data=b'generated fixture'):
        full=self.write(path,data);self.added[path]=p.sha(full);return full
    def verify(self):p.verify_asset_union(self.source,self.dirs,self.added)
    def test_original_and_exact_generated_set_pass(self):self.verify();p.verify_original(self.original_identity)
    def test_unlisted_cs_is_rejected(self):
        self.write(p.JOURNEY+'/Injected.cs')
        with self.assertRaisesRegex(ValueError,'FILE_UNION'):self.verify()
    def test_unlisted_meta_is_rejected(self):
        self.write(p.JOURNEY+'/Injected.cs.meta')
        with self.assertRaisesRegex(ValueError,'FILE_UNION'):self.verify()
    def test_missing_scene_meta_is_rejected(self):
        (p.PROJECT/(p.JOURNEY+'/FirstStation.unity.meta')).unlink()
        with self.assertRaisesRegex(ValueError,'FILE_UNION'):self.verify()
    def test_original_source_change_is_rejected(self):
        self.write('Assets/Original.cs',b'changed')
        with self.assertRaisesRegex(ValueError,'ORIGINAL_CHANGED'):p.verify_original(self.original_identity)
    def test_rewriting_source_manifest_cannot_redefine_original(self):
        changed=copy.deepcopy(self.source);changed['files'][0]['sha256']='0'*64;(p.TASK/'SOURCE-STATE.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError,'ORIGINAL_IDENTITY'):p.verify_original(self.original_identity)
    def test_old_proof_with_new_scene_bytes_is_rejected(self):
        self.write(p.JOURNEY+'/FirstStation.unity',b'new scene after old receipt')
        with self.assertRaisesRegex(ValueError,'FILE_UNION'):self.verify()
    def test_external_symlink_is_rejected(self):
        external=Path(self.tmp.name)/'external';external.write_bytes(b'outside')
        (p.PROJECT/'Assets/linked.asset').symlink_to(external)
        with self.assertRaisesRegex(ValueError,'SYMLINK'):self.verify()
    def test_unknown_empty_asset_directory_is_rejected(self):
        (p.PROJECT/'Assets/unknown-empty').mkdir()
        with self.assertRaisesRegex(ValueError,'DIRECTORY_UNION'):self.verify()
    def test_operational_cache_is_allowed_but_never_part_of_added_assets(self):
        self.write('Library/runtime-cache.bin');self.write('Logs/runtime.log');self.verify()
        self.assertFalse(any(n.startswith('Library/') for n in self.added))
    def test_operational_root_symlink_is_rejected(self):
        external=Path(self.tmp.name)/'external-dir';external.mkdir();(p.PROJECT/'Library').symlink_to(external,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'ROOT_SYMLINK'):self.verify()
    def test_unknown_unity_root_directory_is_rejected(self):
        (p.PROJECT/'AlternateAssets').mkdir()
        with self.assertRaisesRegex(ValueError,'UNKNOWN_UNITY_DIRECTORY'):self.verify()
    def test_addition_cannot_replace_original(self):
        self.added['Assets/Original.cs']=p.sha(p.PROJECT/'Assets/Original.cs')
        with self.assertRaisesRegex(ValueError,'CANNOT_REPLACE'):self.verify()
    def test_addition_outside_two_candidate_roots_is_rejected(self):
        self.add('Assets/Other/unknown.asset')
        with self.assertRaisesRegex(ValueError,'ADDITION_PATH'):self.verify()
    def test_data_pin_fails_after_actual_receipt_change(self):
        receipt=self.write('JourneyEvidence/receipt.json',b'old receipt');pin=p.pin(receipt);p.verify_data_pin(pin);receipt.write_bytes(b'new receipt')
        with self.assertRaisesRegex(ValueError,'DATA_BYTES_CHANGED'):p.verify_data_pin(pin)
    def make_native_journey_fixture(self):
        for n in ('Region-1-Sky.mat','Region-2-Sky.mat','Region-3-Sky.mat','Layout-ABCDEF.mat'):
            self.add(p.JOURNEY+'/'+n);self.add(p.JOURNEY+'/'+n+'.meta')
        folder=p.JOURNEY+'/CandidateFx/fixture-r1';outputs=[]
        for n in ('Flash.png','Flash.mat','Arc.png','Arc.mat','MuzzleFlash.prefab','ArcPresentation.prefab'):
            path=folder+'/'+n;self.add(path);self.add(path+'.meta');outputs.append(dict(path=path,sha256=self.added[path]))
        self.add(p.JOURNEY+'/CandidateFx.meta');self.add(folder+'.meta')
        record=dict(schema=3,status='ACTUAL_NATIVE_JOURNEY_ASSETS_UNREVIEWED',sourceCommit='fixture-sha',files=[dict(path=n,sha256=h) for n,h in self.added.items()])
        self.write('JourneyEvidence/JourneyPreparation/authored-assets.json',json.dumps(record).encode())
        return dict(status='ORIGINAL_NATIVE_FX_AUTHORED_UNCALIBRATED',protectedSourcesUnchanged=True,failures=[],outputs=outputs)
    def test_exact_native_author_asset_snapshot_is_consumed(self):
        fx=self.make_native_journey_fixture()
        with mock.patch.dict(os.environ,{'GITHUB_SHA':'fixture-sha'}):self.assertEqual(p.journey_files(fx),self.added)
    def test_scene_meta_changed_after_native_author_is_rejected(self):
        fx=self.make_native_journey_fixture();self.write(p.JOURNEY+'/FirstStation.unity.meta',b'changed after native test')
        with mock.patch.dict(os.environ,{'GITHUB_SHA':'fixture-sha'}):
            with self.assertRaisesRegex(ValueError,'NATIVE_ASSET_SNAPSHOT_CHANGED'):p.journey_files(fx)
    def test_fx_meta_missing_after_native_author_is_rejected(self):
        fx=self.make_native_journey_fixture();(p.PROJECT/(p.JOURNEY+'/CandidateFx/fixture-r1/Flash.png.meta')).unlink()
        with mock.patch.dict(os.environ,{'GITHUB_SHA':'fixture-sha'}):
            with self.assertRaisesRegex(ValueError,'ADDITION_INVENTORY'):p.journey_files(fx)
    def test_non_python_backup_cache_is_not_a_blanket_exemption(self):
        name='tasks/desert-rv/backup-assets';(p.ROOT/name/'__pycache__').mkdir(parents=True);(p.ROOT/name/'__pycache__/hidden.asset').write_bytes(b'unknown')
        with mock.patch.object(p.original,'SOURCE_ROOTS',('tasks/desert-rv/unity',name)):
            with self.assertRaisesRegex(ValueError,'OTHER_SOURCE_INVENTORY'):self.verify()
    def python_sources(self):
        for name in p.PYTHON_SOURCE_ROOTS:
            path=p.ROOT/name/'declared.py';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'declared source')
            self.source['files'].append(dict(path=str(path.relative_to(p.ROOT)),sha256=p.sha(path),size=path.stat().st_size))
        return mock.patch.object(p.original,'SOURCE_ROOTS',('tasks/desert-rv/unity',)+p.PYTHON_SOURCE_ROOTS)
    def test_inaccessible_python_cache_is_pruned_before_hash_or_recursion(self):
        self.assertNotEqual(os.geteuid(),0,'Run permission regression as the real non-root host user')
        with self.python_sources():
            for name in p.PYTHON_SOURCE_ROOTS:
                for suffix in ('__pycache__','nested/__pycache__'):
                    with self.subTest(root=name,cache=suffix):
                        cache=p.ROOT/name/suffix;cache.mkdir(parents=True)
                        pyc=cache/'prepare_safe_diagnostic_export.cpython-310.pyc';pyc.write_bytes(b'unreadable bytecode')
                        pyc.chmod(0)
                        try:
                            with self.assertRaises(PermissionError):p.sha(pyc)
                            self.verify() # Actual original outer asset/source union path.
                            cache.chmod(0)
                            with self.assertRaises(PermissionError):list(cache.iterdir())
                            self.verify() # Must not even enter the excluded cache directory.
                        finally:cache.chmod(0o700);pyc.chmod(0o600)
    def test_cache_entry_file_or_symlink_is_rejected_in_every_python_root(self):
        with self.python_sources():
            for name in p.PYTHON_SOURCE_ROOTS:
                cache=p.ROOT/name/'__pycache__';cache.write_bytes(b'not a directory')
                with self.assertRaisesRegex(ValueError,'CACHE_DIRECTORY'):self.verify()
                cache.unlink();outside=p.ROOT/'outside';outside.mkdir(exist_ok=True);cache.symlink_to(outside,target_is_directory=True)
                with self.assertRaisesRegex(ValueError,'SYMLINK'):self.verify()
                cache.unlink()
    def test_python_source_and_unknown_files_remain_checked(self):
        with self.python_sources():
            for name in p.PYTHON_SOURCE_ROOTS:
                added=p.ROOT/name/'unlisted.py';added.write_bytes(b'unknown')
                with self.assertRaisesRegex(ValueError,'OTHER_SOURCE_INVENTORY'):self.verify()
                added.unlink();declared=p.ROOT/name/'declared.py';declared.chmod(0)
                try:
                    with self.assertRaises(PermissionError):self.verify()
                finally:declared.chmod(0o600)
    def test_unity_cache_names_are_not_exempt(self):
        for name in ('Assets','Packages','ProjectSettings'):
            cache=p.PROJECT/name/'__pycache__';cache.mkdir();file=cache/'unknown.pyc';file.write_bytes(b'unknown')
            with self.assertRaisesRegex(ValueError,'FILE_UNION'):self.verify()
            file.unlink();cache.rmdir()
    def test_python_subdirectory_walk_does_not_inherit_root_exemption(self):
        with self.python_sources():
            cache=p.ROOT/p.PYTHON_SOURCE_ROOTS[0]/'nested/__pycache__';cache.mkdir(parents=True);file=cache/'entry.pyc';file.write_bytes(b'cache')
            self.assertEqual(p.walk(cache.parent)[0],{'__pycache__/entry.pyc':p.sha(file)})
    def exercise_public_host_chain(self):
        # Real filesystem/exporter/archive/consumer operations with explicitly synthetic
        # native receipt/runtime bytes. This does not claim a Unity or playable build.
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'player'))
        import test_journey_linux_export as fixture
        import journey_linux_export as export
        import observe_journey_player as observer
        import pipeline
        case=fixture.JourneyLinuxExportTests();case.setUp()
        try:
            task,raw=case.success_fixture();logs=case.root/'preflight';logs.mkdir()
            with mock.patch.object(export,'verify_union',side_effect=self.verify),mock.patch.object(pipeline,'guard'):
                export.preflight(logs)
                export.stage()
                self.verify() # Actual host union after the container's stage.
                export.save_native_receipt_observation()
                control=case.control();control['hostDiagnostic']=export.host_state()
                (task/'control.json').write_text(json.dumps(control))
                self.assertEqual(export.export(),0)
                pins=dict(PRODUCER_RUN_ID='123',PRODUCER_COMMIT='a'*40,PRODUCER_ARTIFACT_ID='456',PRODUCER_ZIP_SHA256='c'*64)
                manifest=observer.validate_package(task/'public',pins)
                observer.extract_runtime(task/'public',task/'extracted',manifest)
                self.assertEqual(export.inventory(task/'extracted'),manifest['files'])
                self.assertEqual((task/'public/native-build-receipt.json').read_bytes(),raw)
                self.assertFalse(manifest['playerExecuted'])
        finally:case.doCleanups();case.tearDown()
    def test_nonroot_inaccessible_cache_survives_stage_outer_union_export_and_consumer(self):
        with self.python_sources():
            cache=p.ROOT/p.PYTHON_SOURCE_ROOTS[0]/'__pycache__';cache.mkdir()
            file=cache/'prepare_safe_diagnostic_export.cpython-310.pyc';file.write_bytes(b'private bytecode');file.chmod(0);cache.chmod(0)
            try:self.exercise_public_host_chain()
            finally:cache.chmod(0o700);file.chmod(0o600)
    @unittest.skipUnless(os.environ.get('JOURNEY_HOSTED_ROOT_CACHE_TEST')=='1','Only the verified hosted Actions pre-license fixture creates root-owned cache files')
    def test_hosted_root_owned_cache_crosses_actual_host_union(self):
        # This opt-in must pass the real tracked Git/event/owner/public/branch/attempt
        # guard before sudo. The local fixture never substitutes a synthetic identity.
        import journey_rebuild_dispatch as dispatch
        dispatch.verify(dispatch.ROOT,os.environ)
        uid,gid=os.getuid(),os.getgid();self.assertNotEqual(uid,0)
        fixture=Path(self.tmp.name)
        self.assertEqual(fixture.parent.resolve(),Path(tempfile.gettempdir()).resolve())
        self.assertEqual(fixture.resolve(),fixture);self.assertEqual(fixture.lstat().st_uid,uid)
        self.assertTrue(stat.S_ISDIR(fixture.lstat().st_mode));self.assertEqual(stat.S_IMODE(fixture.lstat().st_mode),0o700)
        with self.python_sources():
            for name in p.PYTHON_SOURCE_ROOTS:
                cache=p.ROOT/name/'__pycache__';cache.mkdir()
                pyc=cache/'prepare_safe_diagnostic_export.cpython-310.pyc';pyc.write_bytes(b'hosted root bytecode permission fixture')
                self.assertTrue(cache.is_relative_to(fixture) and pyc.is_relative_to(fixture))
                self.assertFalse(cache.is_symlink() or pyc.is_symlink())
                def sudo(*args):subprocess.run(['sudo','-n','--',*args],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    sudo('/usr/bin/chmod','0600',str(pyc));sudo('/usr/bin/chmod','0700',str(cache))
                    sudo('/usr/bin/chown','0:0',str(pyc),str(cache))
                    self.assertEqual(cache.lstat().st_uid,0);self.assertEqual(stat.S_IMODE(cache.lstat().st_mode),0o700)
                    with self.assertRaises(PermissionError):p.sha(pyc)
                    with self.assertRaises(PermissionError):list(cache.iterdir())
                    self.verify()
                    self.exercise_public_host_chain()
                finally:
                    # Only these two freshly created fixed descendants; never recursive
                    # ownership changes, project directories, or caller-supplied paths.
                    sudo('/usr/bin/chown',str(uid)+':'+str(gid),str(cache),str(pyc))
                self.assertEqual(pyc.lstat().st_uid,uid);self.assertEqual(stat.S_IMODE(pyc.lstat().st_mode),0o600)
        print('JOURNEY_HOSTED_ROOT_CACHE_UNION: passed; root0700/file0600; non-root reader; 3 exact Python roots')
    def package_fixture(self):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'art/import-candidate'))
        from package_test_fixture import install_package_snapshot
        from strict_output import dependency_input_paths,PACKAGE_ASSETS
        snapshot=install_package_snapshot(p.PROJECT)
        paths=dependency_input_paths(p.PROJECT,sorted(PACKAGE_ASSETS))
        proof={str(path.relative_to(p.ROOT)):p.sha(path) for path in paths}
        state={'completed':[dict(kind=kind,proof=dict(proof)) for kind in ('armored','pouncer','weapon')]}
        for name in ('Packages/manifest.json','Packages/packages-lock.json','ProjectSettings/ProjectVersion.txt'):
            self.files['tasks/desert-rv/unity/'+name]=p.PROJECT/name
        self.source={'files':[dict(path=n,sha256=p.sha(f),size=f.stat().st_size) for n,f in self.files.items()],'restoredFiles':[]}
        self.dirs={name:sorted(p.walk(p.PROJECT/name)[1]) for name in ('Packages','ProjectSettings')}|{'Assets':self.dirs['Assets']}
        return snapshot,state
    def test_only_three_exact_stage_package_proofs_allow_private_root(self):
        snapshot,state=self.package_fixture();pins=p.verified_package_snapshot(state)
        self.assertEqual(len(pins),5);p.verify_asset_union(self.source,self.dirs,self.added,pins)
        self.assertNotIn('CandidatePackageSnapshot',p.OPERATIONAL)
        with self.assertRaisesRegex(ValueError,'UNKNOWN_UNITY_DIRECTORY'):self.verify()
    def test_missing_one_kind_package_proof_is_rejected(self):
        snapshot,state=self.package_fixture();state['completed'][1]['proof'].pop(next(k for k in state['completed'][1]['proof'] if k.endswith('Lit.shader.meta')))
        with self.assertRaisesRegex(ValueError,'PACKAGE_STAGE_PROOF'):p.verified_package_snapshot(state)
    def test_old_package_stage_hash_cannot_bless_current_bytes(self):
        snapshot,state=self.package_fixture();key=next(k for k in state['completed'][0]['proof'] if k.endswith('manifest.json') and 'CandidatePackageSnapshot' in k)
        state['completed'][0]['proof'][key]='0'*64
        with self.assertRaisesRegex(ValueError,'PACKAGE_STAGE_PROOF'):p.verified_package_snapshot(state)
    def test_missing_package_control_proof_is_rejected(self):
        snapshot,state=self.package_fixture();key='tasks/desert-rv/unity/Packages/packages-lock.json';del state['completed'][2]['proof'][key]
        with self.assertRaisesRegex(ValueError,'PACKAGE_INPUT_PROOF'):p.verified_package_snapshot(state)
    def test_private_package_unknown_file_fails_existing_strict_resolver(self):
        snapshot,state=self.package_fixture();(snapshot/'unknown.cs').write_bytes(b'extra')
        with self.assertRaisesRegex(Exception,'SNAPSHOT_ALLOWLIST'):p.verified_package_snapshot(state)
    def test_private_package_unknown_empty_directory_after_verification_is_rejected(self):
        snapshot,state=self.package_fixture();pins=p.verified_package_snapshot(state);(snapshot/'extra').mkdir()
        with self.assertRaisesRegex(ValueError,'PACKAGE_DIRECTORY_UNION'):p.verify_asset_union(self.source,self.dirs,self.added,pins)
    def test_private_package_symlink_cannot_be_operational_exemption(self):
        snapshot,state=self.package_fixture();pins=p.verified_package_snapshot(state);target=p.PROJECT/'external-snapshot';snapshot.rename(target);snapshot.symlink_to(target,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'PREPARED_ROOT'):p.verify_asset_union(self.source,self.dirs,self.added,pins)
if __name__=='__main__':unittest.main(verbosity=2)
