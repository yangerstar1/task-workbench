#!/usr/bin/env python3
"""Synthetic audit tests with real historical material bytes; never a Unity result."""
import contextlib
import hashlib
import io
import json
import shutil
import unittest
from pathlib import Path
from unittest import mock
from PIL import Image
import environment_v4_r4_audit as audit
import test_environment_v4_r4_evidence as fixtures_r4
import test_environment_evidence as fixtures_environment
import test_environment_v4_evidence as fixtures_v4


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.base=fixtures_r4.R4EvidenceTests();self.base.setUp();self.root=self.base.root;self.temp=Path(self.base.temp.name)
        self.mat=audit.r4.MATERIALS[0]
        self.freeze={row['path']:row['afterSha256'] for row in self.base.report['generatedFiles']}
        self.auditroot=self.root/audit.CAPTURE
        for phase in ('freeze','postcapture'):
            rows=[]
            for name in sorted(self.freeze):
                dst=self.auditroot/'internal'/phase/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(self.root/name,dst)
                rows.append(dict(path=name,**audit.fingerprint(dst)))
            record=dict(schema=1,phase=phase,observationPolicy=audit.POLICY,files=rows,loadedObjects=[
                dict(path=self.mat,objectType='UnityEngine.Material',localFileId=2100000,hasLocalFileId=True,isDirty=False),
                dict(path=self.mat,objectType='UnityEditor.Rendering.Universal.AssetVersion',localFileId=548166738449734787,hasLocalFileId=True,isDirty=phase=='postcapture')])
            (self.auditroot/(phase+'.json')).write_text(json.dumps(record))
        self.output=self.temp/'audit-output';self.accepted=self.temp/'accepted';self.snapshot=self.temp/'snapshot.json';self.snapshot.write_text('{"fixture":"abc"}')
        self.identity=dict(commit='a'*40,runId='12345',runAttempt='1',repository='yangerstar1/task-workbench')
    def tearDown(self):self.base.tearDown()
    def mutate_version(self):
        p=self.root/self.mat;p.write_text(p.read_text().replace('  version: 10','  version: 11'))
    def postexit(self):
        with contextlib.redirect_stdout(io.StringIO()):return audit.capture_postexit(self.root)
    def fixtures_png(self):
        env=fixtures_environment.EnvironmentContracts();env.root=self.root;env.capture()
        extra=fixtures_v4.V4EvidenceTests();extra.root=self.root;extra.contract=audit.v4.load_contract();extra.extra()
    @contextlib.contextmanager
    def patch_runtime(self):
        with mock.patch.object(audit,'OUT',self.output),mock.patch.object(audit.r4,'OUT',self.accepted),mock.patch.object(audit.source,'PROJECT',self.root),mock.patch.object(audit.legacy,'SNAPSHOT',self.snapshot),mock.patch.object(audit.legacy,'tracked_snapshot',return_value={'fixture':'abc'}),mock.patch.object(audit.legacy,'inspect_native_report',return_value='b'*64),mock.patch.object(audit.source,'identity',return_value=self.identity):yield
    def write_accepted(self):
        self.accepted.mkdir();(self.accepted/'receipt.json').write_text(json.dumps(dict(self.identity,schema=audit.r4.SCHEMA,nativeRenderXmlSha256='b'*64,protectedTrackedFilesUnchanged=True)))
        audit.v4.write_manifest(self.accepted)
    def test_three_stages_keep_original_hashes_sizes_and_dirty_objects(self):
        self.mutate_version();self.postexit();report=audit.sanitized_audit(self.root,'failure')
        self.assertEqual(report['status'],'NATIVE_RENDERED_NOT_PACKAGE_VALIDATED');self.assertFalse(report['frozenHashesReplaced'])
        self.assertEqual(set(report['phases']),{'freeze','postcapture','postexit'});self.assertEqual(len(report['differences']),1)
        row=report['differences'][0];self.assertEqual(row['path'],self.mat);self.assertEqual(row['repoPath'],'tasks/desert-rv/unity/'+self.mat)
        self.assertEqual(row['stages']['freeze']['sha256'],self.freeze[self.mat]);self.assertNotEqual(row['stages']['postexit']['sha256'],self.freeze[self.mat])
        self.assertTrue(report['loadedObjects']['postcapture'][1]['isDirty']);self.assertIsNone(report['loadedObjects']['postexit'])
        fields=row['transitions'][0]['semantic']['fields'];self.assertEqual(fields,[dict(field='114:548166738449734787:version',before=10.0,after=11.0)])
    def test_missing_generated_path_is_measured_not_replaced(self):
        (self.root/self.mat).unlink();self.postexit();row=audit.sanitized_audit(self.root,'failure')['differences'][0]
        self.assertFalse(row['stages']['postexit']['present']);self.assertIsNone(row['stages']['postexit']['sha256'])
    def test_additional_unapproved_filename_is_counted_never_exported(self):
        marker='SECRET_MARKER_FILENAME';(self.root/audit.legacy.GENERATED/(marker+'.txt')).write_text('SECRET_VALUE')
        self.postexit();report=audit.sanitized_audit(self.root,'failure');self.assertEqual(report['unapprovedGeneratedEntryCount'],1)
        self.assertNotIn(marker,json.dumps(report));self.assertNotIn('SECRET_VALUE',json.dumps(report))
    def test_unknown_material_text_never_leaks(self):
        p=self.root/self.mat;p.write_text(p.read_text()+'  UNKNOWN_SECRET_KEY: SECRET_VALUE_DO_NOT_EXPORT\n');self.postexit()
        report=audit.sanitized_audit(self.root,'failure');raw=json.dumps(report)
        self.assertNotIn('UNKNOWN_SECRET_KEY',raw);self.assertNotIn('SECRET_VALUE_DO_NOT_EXPORT',raw)
        self.assertTrue(report['differences'][0]['transitions'][0]['semantic']['unrecognizedBytesChanged'])
    def test_unknown_header_changes_are_reported_only_as_unrecognized_bytes(self):
        before=(self.root/self.mat).read_bytes();after=before.replace(b'%TAG !u!',b'%TAG SECRET_MARKER !u!')
        result=audit.semantics_diff(self.mat,before,after);self.assertEqual(result['fields'],[]);self.assertTrue(result['unrecognizedBytesChanged'])
        self.assertNotIn('SECRET_MARKER',json.dumps(result))
    def test_unknown_binary_gets_hash_and_size_only(self):
        name=audit.v4.POLISH+'/R1-Ground-Sand.asset';(self.root/name).write_bytes(b'UNKNOWN_SECRET_BYTES')
        self.postexit();report=audit.sanitized_audit(self.root,'failure')
        self.assertEqual(report['differences'][0]['transitions'][0]['semantic'],{'status':'HASH_AND_SIZE_ONLY'})
        self.assertNotIn('UNKNOWN_SECRET_BYTES',json.dumps(report))
    def test_whitelisted_shader_texture_and_normal_values_are_typed(self):
        before=(self.root/self.mat).read_bytes();after=before.replace(b'_BumpScale: 0.035',b'_BumpScale: 0.7')
        result=audit.semantics_diff(self.mat,before,after)
        self.assertEqual(result['fields'],[dict(field='21:2100000:_BumpScale',before=.035,after=.7)])
        self.assertFalse(result['unrecognizedBytesChanged'])
    def test_unknown_shader_keyword_is_not_exported(self):
        before=(self.root/self.mat).read_bytes();after=before.replace(b'  - _NORMALMAP',b'  - SECRET_TOKEN_UNKNOWN')
        result=audit.semantics_diff(self.mat,before,after);self.assertNotIn('SECRET_TOKEN_UNKNOWN',json.dumps(result))
        self.assertTrue(result['unrecognizedBytesChanged'])
    def test_duplicate_numeric_field_falls_back_without_raw_content(self):
        before=(self.root/self.mat).read_bytes();after=before.replace(b'  version: 10',b'  version: 11\n  version: 12')
        self.assertEqual(audit.semantics_diff(self.mat,before,after)['status'],'UNRECOGNIZED_CONTENT_HASH_AND_SIZE_ONLY')
    def test_original_frozen_hash_cannot_be_replaced(self):
        p=self.auditroot/'freeze.json';record=json.loads(p.read_text());record['files'][0]['sha256']='f'*64;p.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError,'frozen hash differs'):self.postexit()
    def test_native_internal_copy_cannot_change(self):
        (self.auditroot/'internal/freeze'/self.mat).write_text('CORRUPT')
        with self.assertRaises(ValueError):self.postexit()
    def test_internal_unknown_payload_is_rejected_not_exported(self):
        (self.auditroot/'internal/freeze/secret.log').write_text('secret')
        with self.assertRaisesRegex(ValueError,'outside authorized'):self.postexit()
    def test_bad_dirty_path_is_rejected(self):
        p=self.auditroot/'postcapture.json';record=json.loads(p.read_text());record['loadedObjects'][0]['path']='../secret';p.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError,'object identity'):self.postexit()
    def test_unavailable_importer_local_id_is_retained_explicitly(self):
        path=self.auditroot/'postcapture.json';record=json.loads(path.read_text())
        record['loadedObjects'].append(dict(path=self.mat,objectType='UnityEditor.NativeFormatImporter',localFileId=0,hasLocalFileId=False,isDirty=True))
        path.write_text(json.dumps(record));self.postexit();report=audit.sanitized_audit(self.root,'success')
        self.assertEqual(report['loadedObjects']['postcapture'][-1]['objectType'],'UnityEditor.NativeFormatImporter')
        self.assertFalse(report['loadedObjects']['postcapture'][-1]['hasLocalFileId'])
    def test_unavailable_local_id_cannot_claim_fabricated_number(self):
        path=self.auditroot/'postcapture.json';record=json.loads(path.read_text());record['loadedObjects'][0]['hasLocalFileId']=False;path.write_text(json.dumps(record))
        with self.assertRaises(ValueError):self.postexit()
    def test_postexit_snapshot_is_never_overwritten(self):
        self.postexit();before=(self.auditroot/'postexit.json').read_bytes();self.mutate_version()
        with self.assertRaisesRegex(ValueError,'overwriting earliest'):self.postexit()
        self.assertEqual(before,(self.auditroot/'postexit.json').read_bytes())
    def test_postexit_internal_copy_tampering_is_rejected(self):
        self.mutate_version();self.postexit();(self.auditroot/'internal/postexit'/self.mat).write_text('TAMPERED')
        with self.assertRaisesRegex(ValueError,'preserved copy differs'):audit.sanitized_audit(self.root,'failure')
    def test_postexit_unknown_keys_are_rejected(self):
        self.postexit();p=self.auditroot/'postexit.json';record=json.loads(p.read_text());record['rawLog']='SECRET';p.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError,'Postexit schema'):audit.sanitized_audit(self.root,'success')
    def test_success_outcome_cannot_conceal_drift(self):
        self.mutate_version();self.postexit()
        with self.assertRaisesRegex(ValueError,'cannot have lifecycle'):audit.sanitized_audit(self.root,'success')
    def test_failure_outcome_requires_an_observed_difference(self):
        self.postexit()
        with self.assertRaisesRegex(ValueError,'requires an actual lifecycle'):audit.sanitized_audit(self.root,'failure')
    def test_outcome_not_arbitrary_text(self):
        with self.assertRaisesRegex(ValueError,'success or failure'):audit.sanitized_audit(self.root,'UNKNOWN_SECRET')
    def test_package_wrapper_preserves_original_failure_and_hash_gate(self):
        self.mutate_version()
        with mock.patch.object(audit.source,'PROJECT',self.root),mock.patch.object(audit.r4,'package',side_effect=ValueError('Frozen generated bytes changed')) as package:
            with contextlib.redirect_stdout(io.StringIO()),self.assertRaisesRegex(ValueError,'Frozen generated bytes changed'):audit.package()
            package.assert_called_once()
        self.assertTrue((self.auditroot/'postexit.json').is_file())
        with self.assertRaisesRegex(ValueError,'Frozen generated bytes changed'):audit.r4.inspect_corrected(self.root)
    def test_failure_exports_only_twenty_validated_pngs_and_sanitized_report(self):
        self.fixtures_png();self.mutate_version();self.postexit()
        with self.patch_runtime(),contextlib.redirect_stdout(io.StringIO()):audit.diagnose('failure')
        expected=set(audit.legacy.IMAGES)|set(audit.v4.EXTRA_IMAGES)|{'lifecycle-audit.json','SHA256SUMS.json'}
        self.assertEqual({p.name for p in self.output.iterdir()},expected);audit.r4.verify_manifest(self.output)
        report=json.loads((self.output/'lifecycle-audit.json').read_text());self.assertEqual(len(report['images']),20)
        self.assertEqual(report['status'],'NATIVE_RENDERED_NOT_PACKAGE_VALIDATED')
        self.assertNotIn('originalSerializedBase64',json.dumps(report))
    def test_success_exports_audit_even_when_package_passes_without_repeating_images(self):
        self.postexit();self.write_accepted()
        with self.patch_runtime(),contextlib.redirect_stdout(io.StringIO()):audit.diagnose('success')
        self.assertEqual({p.name for p in self.output.iterdir()},{'lifecycle-audit.json','SHA256SUMS.json'})
        report=json.loads((self.output/'lifecycle-audit.json').read_text());self.assertEqual(report['images'],[])
        self.assertEqual(report['status'],'PACKAGE_VALIDATED_LIFECYCLE_AUDIT');self.assertTrue(report['loadedObjects']['postcapture'][1]['isDirty'])
    def test_success_requires_matching_real_strict_package_receipt(self):
        self.postexit()
        with self.patch_runtime(),self.assertRaises(ValueError):audit.diagnose('success')
        self.assertFalse(self.output.exists())
    def test_failure_cannot_override_existing_strict_success(self):
        self.mutate_version();self.postexit();self.write_accepted()
        with self.patch_runtime(),self.assertRaisesRegex(ValueError,'existing strict'):audit.diagnose('failure')
    def test_wrong_png_dimensions_block_entire_failure_export(self):
        self.fixtures_png();self.mutate_version();self.postexit();Image.new('RGB',(20,20)).save(self.root/'JourneyEvidence/environment/FirstStation-ground.png')
        with self.patch_runtime(),self.assertRaises(ValueError):audit.diagnose('failure')
        self.assertFalse(self.output.exists())
    def test_extra_capture_raw_log_blocks_export(self):
        self.fixtures_png();self.mutate_version();self.postexit();(self.root/'JourneyEvidence/environment/secret.log').write_text('SECRET')
        with self.patch_runtime(),self.assertRaises(ValueError):audit.diagnose('failure')
        self.assertFalse(self.output.exists())
    def test_symlinked_generated_input_is_rejected(self):
        p=self.root/self.mat;p.unlink();p.symlink_to(self.root/audit.r4.MATERIALS[1])
        with self.assertRaisesRegex(ValueError,'linked evidence'):self.postexit()
    def test_boolean_schema_is_rejected_at_every_stage(self):
        for relative in ('freeze.json','postcapture.json'):
            p=self.auditroot/relative;original=p.read_text();record=json.loads(original);record['schema']=True;p.write_text(json.dumps(record))
            with self.assertRaises(ValueError):self.postexit()
            p.write_text(original)
        self.postexit();p=self.auditroot/'postexit.json';record=json.loads(p.read_text());record['schema']=True;p.write_text(json.dumps(record))
        with self.assertRaises(ValueError):audit.sanitized_audit(self.root,'success')
    def test_boolean_native_report_schema_is_rejected(self):
        path=self.root/audit.r4.CAPTURE/audit.r4.REPORT;record=json.loads(path.read_text());record['schema']=True;path.write_text(json.dumps(record))
        with self.assertRaises(ValueError):self.postexit()
    def test_source_changes_still_block_diagnostic(self):
        self.mutate_version();self.postexit()
        with self.patch_runtime(),mock.patch.object(audit.legacy,'tracked_snapshot',return_value={'fixture':'changed'}),self.assertRaises(ValueError):audit.diagnose('failure')
        self.assertFalse(self.output.exists())


class NativeAuditSourceTests(unittest.TestCase):
    def test_native_patch_only_adds_two_observations_and_read_only_implementation(self):
        path=audit.source.PROJECT/'Assets/DesertRV/Editor/JourneySceneAuthoring.CorrectedTerrain.cs';text=path.read_text()
        start=text.index('        [Serializable] sealed class CorrectedTerrainAuditFile');end=text.index('        static void WriteCorrectedTerrainReport(',start)
        extra=text[start:end]
        original=text[:start]+text[end:]
        for phase in ('freeze','postcapture'):original=original.replace('            WriteCorrectedTerrainAuditPhase("'+phase+'",report);\n','')
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(),'38d3974a478feee192beb38810b8ec6035d43e57a0c037d5ff061322a53cc5b7')
        self.assertIn('Resources.FindObjectsOfTypeAll<Object>()',extra);self.assertIn('EditorUtility.IsDirty(item)',extra)
        self.assertIn('AssetDatabase.TryGetGUIDAndLocalFileIdentifier',extra)
        for value in ('AssetDatabase.SaveAssets(','AssetDatabase.ImportAsset(','AssetDatabase.LoadAllAssetsAtPath(','AssetDatabase.LoadAssetAtPath<','EditorSceneManager.OpenScene('):self.assertNotIn(value,extra)
    def test_existing_renderer_and_strict_package_are_byte_unchanged(self):
        paths={
          'unity/Assets/DesertRV/Tests/EditorRender/JourneyEnvironmentRenderTests.cs':'4a16e5d04dabc2a0ed78dd0be8eb6b4730e2edc9a2a40ac3b0acd20382246858',
          'scripts/environment_v4_r4_evidence.py':'958739e1d1b38bc8916e0e730d43c9f1abf52ba9ba524ffb72848f102cfa8f2f'}
        for name,expected in paths.items():self.assertEqual(hashlib.sha256((audit.source.TASK/name).read_bytes()).hexdigest(),expected)

if __name__=='__main__':unittest.main()
