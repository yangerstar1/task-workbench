"""Offline control-plane/file-copy fixtures. These tests do not claim Unity/art success."""
import copy, hashlib, json, os, shutil, tempfile, unittest
from pathlib import Path
from unittest import mock
import pipeline as p

ORIGINAL_REPO=p.REPO
SELECTION=Path(__file__).with_name('three-strict-candidates.json')
class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.patch=mock.patch.multiple(p,REPO=self.root,ROOT=self.root/'tasks/desert-rv',PROJECT=self.root/'tasks/desert-rv/unity',PRIVATE=self.root/'tasks/desert-rv/unity/JourneyEvidence/JourneyPreparation',PUBLIC=self.root/'tasks/desert-rv/journey-preparation-export')
        self.patch.start();p.PROJECT.mkdir(parents=True);p.PRIVATE.mkdir(parents=True);p.PUBLIC.mkdir()
    def tearDown(self):self.patch.stop();self.temp.cleanup()
    def file(self,path,data=b'fixture'):
        target=p.PROJECT/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data);return target
    def candidate(self,name):
        prefix=str(p.IMPORTS)+'/'+name
        self.file(prefix+'/Source/model.fbx',b'fixture bytes, not a native FBX');self.file(prefix+'/Source/model.fbx.meta',b'guid: '+b'a'*32+b'\n')
        self.file(prefix+'.meta',b'guid: '+name.encode()+b'\n');self.file(str(p.IMPORTS)+'.meta',b'fixed shared root meta')
        return p.import_inventory()
    def test_checked_selection_real_contract_hashes_and_all_existing_shape_gates(self):
        plan=json.loads(SELECTION.read_text())
        for source in plan['sources']:
            dest=self.root/source['contract'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ORIGINAL_REPO/source['contract']).read_bytes())
        p.validate_selection(plan)
    def test_wrong_kind_order_is_rejected(self):
        plan=json.loads(SELECTION.read_text());plan['sources'].reverse()
        with self.assertRaises(Exception):p.validate_selection(plan)
    def test_selection_traversal_path_is_rejected(self):
        plan=json.loads(SELECTION.read_text());plan['sources'][0]['contract']='../private.json'
        with self.assertRaises(Exception):p.validate_selection(plan)
    def test_all_declared_directories_must_match_union(self):
        expected=self.candidate('first');p.assert_union(expected)
        (p.PROJECT/p.IMPORTS/'first/empty-hidden').mkdir()
        with self.assertRaisesRegex(Exception,'DIRECTORY_UNION'):p.assert_union(expected)
    def test_unknown_file_cannot_hide_in_validation_view(self):
        expected=self.candidate('first');self.file(str(p.IMPORTS)+'/first/unexpected.log',b'unknown')
        with self.assertRaisesRegex(Exception,'ASSET_UNION'):p.assert_union(expected)
    def test_shared_meta_is_part_of_exact_union(self):
        expected=self.candidate('first');self.file(str(p.IMPORTS)+'.meta',b'changed')
        with self.assertRaisesRegex(Exception,'ASSET_UNION'):p.assert_union(expected)
    def test_two_candidates_remain_in_original_project(self):
        first=self.candidate('first');expected=self.candidate('second');p.assert_union(expected)
        self.assertTrue(all(p.sha(p.PROJECT/path)==h for path,h in first.items()))
    def test_earlier_asset_mutation_blocks_next_kind(self):
        first=self.candidate('first');self.candidate('second');self.file(str(p.IMPORTS)+'/first/Source/model.fbx',b'modified')
        with self.assertRaisesRegex(Exception,'EARLIER_ASSET'):p.current_scope({'assetFiles':first},{'id':'second'})
    def test_undeclared_third_candidate_is_not_filtered_away(self):
        first=self.candidate('first');self.candidate('second');self.candidate('intruder')
        with self.assertRaisesRegex(Exception,'UNDECLARED'):p.current_scope({'assetFiles':first},{'id':'second'})
    def test_foreign_empty_directory_is_not_filtered_away(self):
        first=self.candidate('first');self.candidate('second');(p.PROJECT/p.IMPORTS/'intruder').mkdir()
        with self.assertRaisesRegex(Exception,'UNKNOWN_CANDIDATE_DIRECTORY'):p.current_scope({'assetFiles':first},{'id':'second'})
    def test_current_unknown_file_is_kept_for_existing_exporter_to_reject(self):
        actual=self.candidate('current');self.file(str(p.IMPORTS)+'/current/unknown.bin',b'unknown')
        current=p.current_scope({'assetFiles':{}},{'id':'current'})
        self.assertIn(str(p.IMPORTS)+'/current/unknown.bin',current)
        with self.assertRaises(Exception):p.assert_union(actual)
    def setup_copy(self):
        current=self.candidate('current')
        self.file('CandidateImportInput/contract.json',b'{}');self.file('CandidateImportInput/payload/model.fbx',b'real fixture bytes')
        self.file('JourneyEvidence/CandidateArt/capture-report.json',b'{}')
        xml=p.ROOT/'artifacts/journey-strict-armored';xml.mkdir(parents=True);(xml/'real.xml').write_text('<fixture-not-native-success/>')
        return current,xml
    def test_view_copies_bytes_and_guids_without_moving_original_assets(self):
        current,xml=self.setup_copy();view,sources=p.copy_snapshot({'kind':'armored','id':'current'},current,xml)
        p.verify_snapshot(sources)
        for source,(relative,h) in sources.items():self.assertEqual(source.read_bytes(),(view/relative).read_bytes());self.assertEqual(p.sha(source),h)
        self.assertEqual(p.import_inventory(),current)
    def test_empty_current_directories_are_preserved_in_view(self):
        current,xml=self.setup_copy();(p.PROJECT/p.IMPORTS/'current/unknown-empty').mkdir()
        view,_=p.copy_snapshot({'kind':'armored','id':'current'},current,xml)
        self.assertTrue((view/'unity'/p.IMPORTS/'current/unknown-empty').is_dir())
    def test_actual_input_mutation_after_copy_is_detected(self):
        current,xml=self.setup_copy();_,sources=p.copy_snapshot({'kind':'armored','id':'current'},current,xml)
        self.file('JourneyEvidence/CandidateArt/capture-report.json',b'changed')
        with self.assertRaisesRegex(Exception,'INPUT_CHANGED'):p.verify_snapshot(sources)
    def test_cross_kind_dependency_fails_before_snapshot_copy(self):
        current,xml=self.setup_copy();self.file(str(p.IMPORTS)+'/other/Candidate.prefab',b'fixture');self.file(str(p.IMPORTS)+'/other/Candidate.prefab.meta',b'guid: '+b'b'*32)
        deps=[str(p.IMPORTS)+'/other/Candidate.prefab'];imp=dict(dependencies=deps,dependencySha256=p.dependency_digest(p.PROJECT,deps))
        self.file('JourneyEvidence/CandidateArt/import-report.json',json.dumps(imp).encode())
        with self.assertRaisesRegex(Exception,'CROSS_KIND'):p.copy_snapshot({'kind':'armored','id':'current'},current,xml)
    def test_protected_source_detects_added_and_changed_files(self):
        source=self.file('Assets/DesertRV/Runtime/Original.cs',b'original');before=p.protected();source.write_bytes(b'changed');self.assertNotEqual(before,p.protected())
        source.write_bytes(b'original');self.file('ProjectSettings/extra.asset',b'new');self.assertNotEqual(before,p.protected())
    def test_new_candidates_do_not_pollute_original_source_snapshot(self):
        self.file('Assets/DesertRV/Runtime/Original.cs',b'original');before=p.protected();self.candidate('first');self.assertEqual(before,p.protected())
    def test_symlink_file_is_not_accepted(self):
        original=self.file('Assets/Original.txt',b'original');link=p.PROJECT/'Assets/link.txt';link.symlink_to(original)
        with self.assertRaises(Exception):p.tree(p.PROJECT/'Assets')
    def test_ready_cannot_run_without_three_native_successes(self):
        s={'completed':[],'assetFiles':{}}
        with mock.patch.object(p,'state',return_value=s),mock.patch.object(p,'check_state'):
            with self.assertRaisesRegex(Exception,'THREE_STRICT_SUCCESSES'):p.ready()
    def test_failed_native_finish_is_not_prepared(self):
        with self.assertRaisesRegex(Exception,'AUTHORING_NATIVE_FAILED'):p.finish('failure')
    def test_failed_nunit_aggregate_is_not_hidden_by_one_passed_case(self):
        xml=p.ROOT/'artifacts/journey-preparation';xml.mkdir(parents=True)
        (xml/'results.xml').write_text('<test-run result="Failed"><test-case fullname="DesertRV.Tests.JourneyPreparationTests.PrepareVerifiedSameWorkspaceJourney" result="Passed"/></test-run>')
        with self.assertRaisesRegex(Exception,'NATIVE_ENTRY_NOT_PASSED'):p.finish('success')
    def test_actual_xml_inventory_records_version_pinned_fullnames_without_a_second_gate(self):
        for count in (10,26):
            folder=p.ROOT/'artifacts'/('fixture-'+str(count));folder.mkdir(parents=True)
            xml=folder/'native.xml';xml.write_text('<test-run result="Passed">'+''.join('<test-case fullname="Fixture.Case'+str(i)+'" result="Passed"/>' for i in range(count))+'</test-run>')
            pin,names=p.native_inventory(folder,p.sha(xml));self.assertEqual(len(names),count);self.assertEqual(pin['sha256'],p.sha(xml))
    def test_duplicate_native_fullnames_are_rejected(self):
        folder=p.ROOT/'artifacts/fixture';folder.mkdir(parents=True);xml=folder/'native.xml'
        xml.write_text('<test-run result="Passed"><test-case fullname="Duplicate" result="Passed"/><test-case fullname="Duplicate" result="Passed"/></test-run>')
        with self.assertRaisesRegex(Exception,'NATIVE_INVENTORY'):p.native_inventory(folder,p.sha(xml))
    def strict_synthetic_view(self):
        import test_strict_output as fixtures
        fixture=fixtures.StrictExportTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        from package_test_fixture import install_package_snapshot
        from strict_output import PACKAGE_ASSETS
        install_package_snapshot(fixture.project)
        fixture.imp['dependencies']+=sorted(PACKAGE_ASSETS)
        fixture.imp['dependencySha256']=p.dependency_digest(fixture.project,fixture.imp['dependencies'])
        fixture.cap['dependencySha256']=fixture.imp['dependencySha256'];fixture.flush()
        shutil.copytree(fixture.project,p.PROJECT,dirs_exist_ok=True)
        xml=p.ROOT/'artifacts/journey-strict-armored';shutil.copytree(fixture.root/'artifacts/candidate-art',xml)
        # A prior independently-accounted-for fixture remains in the REAL workspace, not the validator view.
        old=str(p.IMPORTS)+'/prior';self.file(old+'/Source/old.fbx',b'prior fixture');self.file(old+'.meta',b'guid: '+b'f'*32)
        previous={path:h for path,h in p.import_inventory().items() if path.startswith(old+'/') or path==old+'.meta' or path==str(p.IMPORTS)+'.meta'}
        current=p.current_scope({'assetFiles':previous},fixture.c)
        view,sources=p.copy_snapshot(fixture.c,current,xml)
        return fixture,view,sources,previous,current
    def test_existing_strict_synthetic_gate_accepts_unchanged_copy_without_moving_assets(self):
        fixture,view,sources,previous,current=self.strict_synthetic_view()
        with mock.patch.dict(os.environ,{'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'123'}):result=p.export(view,p.PRIVATE/'synthetic-safe','success','success')
        self.assertEqual(result['status'],'STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED');self.assertFalse(result['approved'])
        self.assertEqual(result['nativeCases'],__import__('candidate_native_cases').NATIVE_COUNT)
        self.assertFalse(any('Package' in row['path'] for row in result['files']))
        p.verify_snapshot(sources);p.assert_union({**previous,**current})
        self.assertTrue((p.PROJECT/p.IMPORTS/'prior/Source/old.fbx').exists())
    def test_existing_strict_synthetic_gate_rejects_tampered_copy(self):
        fixture,view,sources,previous,current=self.strict_synthetic_view()
        (view/'unity'/fixture.prefix/'Source'/fixture.c['modelFile']).write_bytes(b'tampered snapshot')
        with mock.patch.dict(os.environ,{'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'123'}):
            with self.assertRaises(Exception):p.export(view,p.PRIVATE/'synthetic-failed','success','success')
        p.verify_snapshot(sources) # The real original was not changed to make the test pass.
    def test_workflow_uses_one_workspace_and_unchanged_strict_test_assembly(self):
        source=(ORIGINAL_REPO/'.github/workflows/desert-rv-journey-prepare.yml').read_text()
        self.assertEqual(source.count('projectPath: tasks/desert-rv/unity'),4)
        self.assertEqual(source.count('-assemblyNames DesertRV.CandidateArtTests'),3)
        self.assertEqual(source.count('-assemblyNames DesertRV.JourneyPreparationTests'),1)
        self.assertNotIn('download-artifact',source);self.assertNotIn('strategy:',source)
    def test_optional_pilot_uploads_only_the_existing_guarded_directory(self):
        source=(ORIGINAL_REPO/'.github/workflows/desert-rv-journey-prepare.yml').read_text()
        self.assertIn('id: rendered',source);self.assertIn("if: always() && steps.rendered.outputs.export_ready == 'true'",source)
        self.assertIn('path: tasks/desert-rv/rendered-public-export/',source)
        self.assertNotIn('path: tasks/desert-rv/rendered-private-evidence',source)
    def test_native_composition_preserves_existing_api_order_and_no_approval(self):
        source=(ORIGINAL_REPO/'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneyCandidatePreparation.cs').read_text()
        calls=['JourneySceneAuthoring.AuthorCandidateScenes();','JourneyCandidateAssetIntegration.AuthorFxFromEnvironment();','JourneyCandidateAssetIntegration.IntegrateFromEnvironment();','JourneyDiagnosticScope.PrepareRequestFromEnvironment();']
        self.assertEqual([source.index(c) for c in calls],sorted(source.index(c) for c in calls))
        self.assertNotIn('accepted = true',source);self.assertNotIn('CreatePrimitive',source);self.assertNotIn('BuildPipeline.BuildPlayer',source)
    def setup_package_copy(self):
        from package_test_fixture import install_package_snapshot
        from strict_output import PACKAGE_ASSETS
        current,xml=self.setup_copy();snapshot=install_package_snapshot(p.PROJECT)
        deps=[str(p.IMPORTS)+'/current/Source/model.fbx',*sorted(PACKAGE_ASSETS)]
        self.file('JourneyEvidence/CandidateArt/import-report.json',json.dumps(dict(dependencies=deps,dependencySha256=p.dependency_digest(p.PROJECT,deps))).encode())
        return current,xml,snapshot,deps
    def test_private_package_copy_retains_all_four_bytes_manifest_and_project_controls(self):
        from strict_output import PACKAGE_FILES,dependency_input_paths
        current,xml,snapshot,deps=self.setup_package_copy()
        before=p.import_inventory();view,sources=p.copy_snapshot({'kind':'armored','id':'current'},current,xml)
        expected=dependency_input_paths(p.PROJECT,deps)
        self.assertTrue(expected<=set(sources));self.assertEqual(p.import_inventory(),before)
        for path in expected:
            dest=view/'unity'/path.relative_to(p.PROJECT)
            self.assertEqual(path.read_bytes(),dest.read_bytes())
        self.assertEqual(len(p.tree(view/'unity/CandidatePackageSnapshot')),5)
        self.assertEqual(p.dependency_digest(view/'unity',deps),p.dependency_digest(p.PROJECT,deps))
        self.assertFalse(any(p.PUBLIC.iterdir()))
        self.assertTrue(all(not (view/'unity'/name).exists() for name in PACKAGE_FILES))
        p.verify_snapshot(sources)
    def test_missing_private_package_companion_is_not_silently_omitted(self):
        from strict_output import PACKAGE_ASSET_VERSION
        current,xml,snapshot,deps=self.setup_package_copy();(snapshot/(PACKAGE_ASSET_VERSION+'.meta')).unlink()
        with self.assertRaisesRegex(Exception,'SNAPSHOT_ALLOWLIST'):p.copy_snapshot({'kind':'armored','id':'current'},current,xml)
    def test_private_package_unknown_empty_directory_is_not_filtered(self):
        current,xml,snapshot,deps=self.setup_package_copy();(snapshot/'extra').mkdir()
        with self.assertRaisesRegex(Exception,'SNAPSHOT_ALLOWLIST'):p.copy_snapshot({'kind':'armored','id':'current'},current,xml)
    def test_private_snapshot_addition_during_export_is_detected(self):
        current,xml,snapshot,deps=self.setup_package_copy();view,sources=p.copy_snapshot({'kind':'armored','id':'current'},current,xml)
        (snapshot/'extra').mkdir()
        with self.assertRaisesRegex(Exception,'SNAPSHOT_ALLOWLIST'):p.verify_snapshot(sources)
    def test_private_snapshot_byte_mutation_during_export_is_detected(self):
        from strict_output import PACKAGE_SHADER
        current,xml,snapshot,deps=self.setup_package_copy();view,sources=p.copy_snapshot({'kind':'armored','id':'current'},current,xml)
        (snapshot/PACKAGE_SHADER).write_bytes(b'changed')
        with self.assertRaisesRegex(Exception,'INPUT_CHANGED'):p.verify_snapshot(sources)
    def test_new_direct_package_resolution_after_copy_is_detected(self):
        from strict_output import PACKAGE_SHADER
        current,xml,snapshot,deps=self.setup_package_copy();view,sources=p.copy_snapshot({'kind':'armored','id':'current'},current,xml)
        self.file(PACKAGE_SHADER,(snapshot/PACKAGE_SHADER).read_bytes())
        with self.assertRaisesRegex(Exception,'INPUT_SET_CHANGED'):p.verify_snapshot(sources)
    def validation_fixture(self):
        names=('strict_output.py','pouncer_output.py','weapon_output.py','verify_output.py','candidate_native_cases.py','foot_contact_output.py','paw_contact_output.py')
        for name in names:
            path=p.ROOT/'art/import-candidate'/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes((ORIGINAL_REPO/'tasks/desert-rv/art/import-candidate'/name).read_bytes())
        self.file('Assets/DesertRV/Tests/CandidateArt/Fixture.cs',b'not a native test')
        selection=p.ROOT/'art/journey-preparation/fixture.json';selection.parent.mkdir(parents=True);selection.write_text('{}')
        return dict(selection=str(selection.relative_to(p.REPO)),selectionSha256=p.sha(selection),validationSourcePins=p.validation_sources(),protected=p.protected(),assetFiles={})
    def test_exact_registry_and_both_imported_name_sources_are_pinned(self):
        state=self.validation_fixture();p.check_state(state)
        paths={row['path'] for row in state['validationSourcePins']}
        for name in ('candidate_native_cases.py','foot_contact_output.py','paw_contact_output.py'):
            self.assertIn('tasks/desert-rv/art/import-candidate/'+name,paths)
    def test_registry_or_imported_names_change_rejects_previous_validation_version(self):
        state=self.validation_fixture()
        for name in ('candidate_native_cases.py','foot_contact_output.py','paw_contact_output.py'):
            path=p.ROOT/'art/import-candidate'/name;original=path.read_bytes();path.write_bytes(original+b'\n# changed version\n')
            with self.assertRaisesRegex(Exception,'VALIDATION_VERSION_CHANGED'):p.check_state(state)
            path.write_bytes(original)
    def test_missing_native_registry_source_is_rejected(self):
        self.validation_fixture();(p.ROOT/'art/import-candidate/candidate_native_cases.py').unlink()
        with self.assertRaises(Exception):p.validation_sources()
if __name__=='__main__':unittest.main(verbosity=2)
