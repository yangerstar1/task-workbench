"""Real filesystem request fixtures; these are not native build evidence."""
import json,unittest
import xml.etree.ElementTree as ET
from unittest import mock
from pathlib import Path
import linux_build_input as linux
import test_generated_export as fixtures

class LinuxBuildInputTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.GeneratedExportTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.export();p=fixtures.p;self.fixture.prepared.walk=p.walk
        for name,value in [('ROOT',p.ROOT),('TASK',p.TASK),('PROJECT',p.PROJECT),('prepared_source',self.fixture.prepared),('BOUNDARY_SOURCE','tasks/desert-rv/unity/Assets/Original.cs')]:
            patch=mock.patch.object(linux,name,value);patch.start();self.addCleanup(patch.stop)
        self.receipt=linux.TASK/'journey-preparation-export/generated/receipt.json'
        self.input=linux.PROJECT/'JourneyEvidence/JourneyPreparation/linux-build-input.json'
        self.xml=linux.TASK/'artifacts/journey-linux-boundary/result.xml';self.xml.parent.mkdir(parents=True)
        root=ET.Element('test-run',result='Passed',total='17',passed='17',failed='0',skipped='0',inconclusive='0')
        for name in linux.BOUNDARY_NAMES:ET.SubElement(root,'test-case',fullname=name,result='Passed')
        ET.ElementTree(root).write(self.xml)
        self.boundary=linux.PROJECT/'JourneyEvidence/JourneyPreparation/linux-boundary-verified.json';self.boundary.write_text(json.dumps(linux.boundary_evidence()))
    def change_receipt(self,key,value):
        receipt=json.loads(self.receipt.read_text());receipt[key]=value;self.receipt.write_text(json.dumps(receipt))
    def rejects(self,code):
        with self.assertRaisesRegex(Exception,code):linux.prepare()
        self.assertFalse(self.input.exists())
    def test_exact_four_bundle_request_pins_real_bytes_and_all_directories(self):
        request=linux.prepare();self.assertEqual(request,json.loads(self.input.read_text()))
        self.assertEqual(self.input.with_suffix('.sha256').read_text().strip(),linux.sha(self.input))
        for row in request['files']:self.assertEqual(row['sha256'],linux.sha(linux.ROOT/row['path']))
        expected=sorted(n+'/'+d for n in ('Assets','Packages','ProjectSettings') for d in fixtures.p.walk(linux.PROJECT/n)[1])
        self.assertEqual(expected,request['directories']);self.assertEqual(5,len(request['scenes']))
        self.assertEqual('StandaloneLinux64',request['target']);self.assertTrue(request['development']);self.assertFalse(request['approved'])
        self.assertEqual({'source','strict','generated','official-package','unity-builtin'},{d['owner'] for d in request['dependencies']})
    def test_other_source_commit_rejected(self):self.change_receipt('sourceCommit','b'*40);self.rejects('REAL_GENERATED_EXPORT')
    def test_other_producer_run_rejected(self):self.change_receipt('importRunUrl',fixtures.RUN+'1');self.rejects('REAL_GENERATED_EXPORT')
    def test_approval_true_rejected(self):self.change_receipt('approved',True);self.rejects('REAL_GENERATED_EXPORT')
    def test_claimed_reusable_scope_rejected(self):self.change_receipt('scopeReusable',True);self.rejects('REAL_GENERATED_EXPORT')
    def test_unlisted_script_rejected(self):self.fixture.fixture.write('Assets/Injected.cs',b'executable');self.rejects('ASSET_FILE_UNION')
    def test_unlisted_meta_rejected(self):self.fixture.fixture.write('Assets/Injected.cs.meta',b'guid');self.rejects('ASSET_FILE_UNION')
    def test_extra_empty_directory_rejected(self):(linux.PROJECT/'Assets/ExtraEmpty').mkdir();self.rejects('DIRECTORY_UNION')
    def test_changed_source_bytes_rejected(self):self.fixture.fixture.write('Assets/Original.cs',b'changed');self.rejects('ORIGINAL_CHANGED')
    def test_missing_scene_meta_rejected(self):
        (linux.PROJECT/(fixtures.p.JOURNEY+'/FirstStation.unity.meta')).unlink();self.rejects('ADDITION_INVENTORY')
    def test_symlink_source_rejected(self):
        path=linux.PROJECT/'Assets/Original.cs';data=path.read_bytes();path.unlink();outside=linux.ROOT/'external';outside.write_bytes(data);path.symlink_to(outside);self.rejects('linked|SYMLINK|UNSAFE')
    def test_native_manifest_modified_after_export_rejected(self):
        path=self.receipt.parent/'native-authored-assets.json';path.write_text(path.read_text()+' ');self.rejects('STAGING_HASH')
    def test_grounding_evidence_is_pinned_in_native_build_request(self):
        request=linux.prepare();name=str((linux.PROJECT/linux.generated.GROUND_PATH).relative_to(linux.ROOT))
        self.assertEqual([r['sha256'] for r in request['files'] if r['path']==name],[linux.sha(linux.PROJECT/linux.generated.GROUND_PATH)])
    def test_grounding_export_tampering_is_rejected(self):
        path=self.receipt.parent/linux.generated.GROUND_EXPORT;path.write_text(path.read_text()+' ');self.rejects('STAGING_HASH')
    def test_grounding_receipt_hash_mismatch_is_rejected(self):self.change_receipt('spawnGroundingSha256','0'*64);self.rejects('LINUX_GROUNDING_CHANGED')
    def test_grounding_receipt_path_cannot_be_redirected(self):self.change_receipt('spawnGroundingPath','../private');self.rejects('LINUX_GROUNDING_PATH')
    def test_generated_receipt_unknown_dependency_cannot_authorize_file(self):
        value=json.loads(self.receipt.read_text());value['dependencies'].append(dict(path='Assets/Injected.cs',kind='asset',owner='source',sha256='a'*64,bytes=5,packageName='',packageVersion=''));self.receipt.write_text(json.dumps(value));self.rejects('DEPENDENCIES_CHANGED')
    def test_pinned_strict_receipt_tamper_rejected(self):
        path=linux.TASK/'journey-preparation-export/weapon/receipt.json';path.write_text(path.read_text()+' ');self.rejects('STRICT_RECEIPT_CHANGED')
    def test_request_not_overwritten(self):
        linux.prepare();before=self.input.read_bytes()
        with self.assertRaisesRegex(Exception,'REQUEST_EXISTS'):linux.prepare()
        self.assertEqual(before,self.input.read_bytes())
    def test_post_resolution_mutation_prevents_request(self):
        original=linux.prepared_source.verify;calls=[]
        def verify():
            calls.append(1)
            if len(calls)==2:self.fixture.fixture.write('Assets/Original.cs',b'changed at final proof')
            return original()
        with mock.patch.object(linux.prepared_source,'verify',side_effect=verify):self.rejects('ORIGINAL_CHANGED')
    def test_missing_native_boundary_xml_rejected(self):self.xml.unlink();self.rejects('BOUNDARY_XML_COUNT')
    def test_duplicate_native_boundary_xml_rejected(self):(self.xml.parent/'extra.xml').write_bytes(self.xml.read_bytes());self.rejects('BOUNDARY_XML_COUNT')
    def test_native_boundary_count_mismatch_rejected(self):
        root=ET.parse(self.xml).getroot();root.set('passed','16');ET.ElementTree(root).write(self.xml);self.rejects('BOUNDARY_NATIVE_FAILED')
    def test_native_boundary_duplicate_name_rejected(self):
        root=ET.parse(self.xml).getroot();root[1].set('fullname',root[0].get('fullname'));ET.ElementTree(root).write(self.xml);self.rejects('BOUNDARY_NATIVE_FAILED')
    def test_native_boundary_wrong_fullname_with_valid_prefix_rejected(self):
        root=ET.parse(self.xml).getroot();root[0].set('fullname','DesertRV.Tests.CandidateLinuxBoundaryTests.Invented');ET.ElementTree(root).write(self.xml);self.rejects('BOUNDARY_NATIVE_FAILED')
    def test_native_boundary_failed_case_rejected(self):
        root=ET.parse(self.xml).getroot();root[0].set('result','Failed');ET.ElementTree(root).write(self.xml);self.rejects('BOUNDARY_NATIVE_FAILED')
    def test_native_boundary_receipt_wrong_source_rejected(self):
        value=json.loads(self.boundary.read_text());value['sourceCommit']='f'*40;self.boundary.write_text(json.dumps(value));self.rejects('BOUNDARY_PROOF_CHANGED')
    def test_native_boundary_xml_changed_after_verified_rejected(self):self.xml.write_text(self.xml.read_text()+' ');self.rejects('BOUNDARY_PROOF_CHANGED')
    def test_native_boundary_fixture_inventory_matches_actual_test_source(self):
        path=Path(__file__).resolve().parents[2]/'unity/Assets/DesertRV/Tests/CandidateLinux/CandidateLinuxBoundaryTests.cs'
        import re
        self.assertEqual(set(linux.BOUNDARY_NAMES),{'DesertRV.Tests.CandidateLinuxBoundaryTests.'+n for n in re.findall(r'\[Test\] public void (\w+)\(',path.read_text())})
class RestoredBuildRequestTests(unittest.TestCase):
    def setUp(self):
        LinuxBuildInputTests.setUp(self)
        import types,sys
        self.root=linux.PROJECT/'JourneyEvidence/JourneyPreparation'
        names=dict(INPUT='restoration-input.json',REPORT='restoration-revalidated.json',VERIFIED='restoration-native-verified.json',SOURCE_PROOF='restoration-source-proof.json')
        self.restore=types.SimpleNamespace(**{k:self.root/v for k,v in names.items()})
        receipt=json.loads(self.receipt.read_text());self.report=dict(scenes=receipt['integrationOutputs'])
        self.restore.REPORT.write_text(json.dumps(self.report));self.restore.INPUT.write_text(json.dumps(dict(files=[dict(path='tasks/desert-rv/unity/Assets/Original.cs',sha256=linux.sha(linux.PROJECT/'Assets/Original.cs'))],directories=[])))
        self.restore.VERIFIED.write_text('{}');self.restore.SOURCE_PROOF.write_text('{}')
        self.native=linux.TASK/'artifacts/journey-restoration/result.xml';self.native.parent.mkdir(parents=True);self.native.write_text('<fixture/>')
        self.restore.pin=lambda p:dict(path=str(p.relative_to(linux.ROOT)),sha256=linux.sha(p))
        self.restore.PRODUCER=dict(sourceCommit='b'*40,generatedReceiptSha256=linux.sha(self.receipt));self.restore.RUN_URL='https://github.com/yangerstar1/task-workbench/actions/runs/123'
        self.restore.current_run=lambda:'https://github.com/yangerstar1/task-workbench/actions/runs/'+__import__('os').environ['GITHUB_RUN_ID']
        self.restore.native_evidence=lambda:self.restore.pin(self.native)
        self.restore.verify=mock.Mock(return_value=({},dict(receipt=receipt),dict(nativeXml=self.restore.pin(self.native))))
        patch=mock.patch.dict(sys.modules,restore_preparation=self.restore);patch.start();self.addCleanup(patch.stop)
    def test_original_producer_and_new_consumer_identities_are_distinct_and_pinned(self):
        request=linux.prepare_restored();self.assertEqual('b'*40,request['assetProducerSourceCommit']);self.assertEqual(self.restore.RUN_URL,request['assetProducerRunUrl']);self.assertNotEqual(request['sourceCommit'],request['assetProducerSourceCommit'])
        self.assertEqual(self.restore.pin(self.restore.REPORT),request['restorationProof']);self.assertEqual(linux.sha(self.native),request['restorationNativeXmlSha256'])
    def test_both_current_native_xml_and_input_and_source_proof_are_pinned(self):
        request=linux.prepare_restored();pins={r['path']:r['sha256'] for r in request['files']}
        for path in (self.native,self.xml,self.restore.INPUT,self.restore.REPORT,self.restore.SOURCE_PROOF):self.assertEqual(linux.sha(path),pins[str(path.relative_to(linux.ROOT))])
    def test_failed_restoration_cannot_prepare_build(self):
        self.restore.verify.side_effect=ValueError('RESTORE_NATIVE_NOT_PASSED')
        with self.assertRaisesRegex(Exception,'NATIVE_NOT_PASSED'):linux.prepare_restored()
        self.assertFalse(self.input.exists())
    def test_current_boundary_failure_stops_restored_build(self):
        self.xml.unlink()
        with self.assertRaisesRegex(Exception,'BOUNDARY_XML_COUNT'):linux.prepare_restored()
        self.assertFalse(self.input.exists())
    def test_request_recheck_rejects_changed_producer_identity(self):
        value=linux.prepare_restored();value['assetProducerSourceCommit']='e'*40;self.input.write_text(json.dumps(value));self.input.with_suffix('.sha256').write_text(linux.sha(self.input))
        with self.assertRaisesRegex(Exception,'RESTORATION_PROOF_CHANGED'):linux.verify()
    def test_request_recheck_rejects_changed_native_xml_pin(self):
        linux.prepare_restored();self.native.write_text('changed')
        with self.assertRaisesRegex(Exception,'RESTORATION_PROOF_CHANGED'):linux.verify()
    def test_missing_restoration_marker_does_not_fall_back_to_unverified_restore(self):
        value=linux.prepare_restored();value['restorationProof']=None;self.input.write_text(json.dumps(value))
        with self.assertRaisesRegex(Exception,'UNDECLARED_RESTORATION'):linux.verify()
    def test_existing_build_request_is_not_overwritten(self):
        linux.prepare_restored();before=self.input.read_bytes()
        with self.assertRaisesRegex(Exception,'REQUEST_EXISTS'):linux.prepare_restored()
        self.assertEqual(before,self.input.read_bytes())

if __name__=='__main__':unittest.main(verbosity=2)
