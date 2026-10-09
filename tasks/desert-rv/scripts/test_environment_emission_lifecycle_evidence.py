#!/usr/bin/env python3
"""Synthetic unit fixtures and real non-root read-only filesystem tests, not native evidence."""
import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock
import environment_emission_lifecycle_evidence as emission
import test_environment_v4_r4_audit as previous

# Float32 values emitted by Unity's original Color multiplication. These are
# deliberately not Python's exact decimal 1.9/.95 and are not real run evidence.
FLOAT32_HDR = dict(r=2.5,g=1.899999976158142,b=.949999988079071,a=2.5)
MATERIAL = b'''%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!21 &2100000
Material:
  m_ObjectHideFlags: 0
  m_Shader: {fileID: 4800000, guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, type: 3}
  m_ValidKeywords:
  - _EMISSION
  m_InvalidKeywords: []
  m_LightmapFlags: 2
  m_SavedProperties:
    m_Colors:
    - _BaseColor: {r: 1, g: 0.76, b: 0.38, a: 1}
    - _EmissionColor: {r: 2.5, g: 1.9, b: 0.95, a: 2.5}
'''
META = b'fileFormatVersion: 2\nguid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n'


def marker_records():
    life=dict(path=emission.TARGET,beforeSha256=hashlib.sha256(MATERIAL.replace(b'm_LightmapFlags: 2',b'm_LightmapFlags: 4')).hexdigest(),
        savedSha256=hashlib.sha256(MATERIAL).hexdigest(),metaSha256=hashlib.sha256(META).hexdigest(),validator=emission.VALIDATOR,
        beforeGIFlags=4,afterGIFlags=2,saveImportCycles=2,beforeEmissionKeyword=False,afterEmissionKeyword=True,
        secondSaveStable=True,allNativeObjectsClean=True,beforeEmissionColor=dict(FLOAT32_HDR),afterEmissionColor=dict(FLOAT32_HDR))
    obs=dict(path=emission.TARGET,shader=emission.SHADER,rendererCount=1,giFlags=2,loadedObjectCount=1,dirtyLoadedObjectCount=0,
        materialPresent=True,rendererEnabled=True,singleMaterial=True,expectedMaterialIdentity=True,expectedEmissionColor=True,expectedGI=True,
        emissionKeyword=True,materialDirty=False,keywords=['_EMISSION'],emissionColor=dict(FLOAT32_HDR))
    return [(emission.LIFECYCLE_MARKER,life),(emission.OBSERVATION_MARKER,dict(obs,phase='author-reload')),
            (emission.OBSERVATION_MARKER,dict(obs,phase='postcapture'))]


def write_xml(path, records=None, output=None):
    root=ET.Element('test-run',result='Passed');case=ET.SubElement(root,'test-case',fullname=emission.legacy.RENDER_TEST,result='Passed')
    ET.SubElement(case,'output').text = output if output is not None else '\n'.join(prefix+json.dumps(row) for prefix,row in (marker_records() if records is None else records))+'\nPRIVATE_UNRELATED_LOG_MUST_NOT_EXPORT\n'
    path.parent.mkdir(parents=True,exist_ok=True);ET.ElementTree(root).write(path,encoding='unicode')


class MarkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name);self.xml=self.directory/'result.xml';write_xml(self.xml)
    def tearDown(self): self.temp.cleanup()
    def parse(self): return emission.native_markers(self.directory)
    def test_exact_three_markers_keep_actual_float32_hdr(self):
        sha,life,obs=self.parse();self.assertEqual(sha,emission.source.sha(self.xml));self.assertEqual(life['beforeEmissionColor'],FLOAT32_HDR)
        self.assertEqual(obs['postcapture']['emissionColor'],FLOAT32_HDR)
    def test_missing_duplicate_reordered_marker_and_duplicate_phase_fail(self):
        cases=[];base=marker_records();cases.extend([base[:2],base+[base[0]],[base[1],base[0],base[2]]])
        duplicate=copy.deepcopy(base);duplicate[2][1]['phase']='author-reload';cases.append(duplicate)
        for rows in cases:
            with self.subTest(rows=len(rows)):
                write_xml(self.xml,rows)
                with self.assertRaises(ValueError):self.parse()
    def test_nonfinite_boolean_enum_unknown_key_wrong_target_and_validator_fail(self):
        changes=[(0,'beforeGIFlags',True),(0,'afterGIFlags',0),(0,'saveImportCycles',True),(0,'secondSaveStable',1),
                 (0,'validator','Unknown.ShaderGUI'),(0,'path','../PRIVATE'),(0,'extra','PRIVATE'),
                 (2,'loadedObjectCount',False),(2,'dirtyLoadedObjectCount',1),(2,'materialDirty',True),
                 (2,'giFlags',4),(2,'emissionKeyword',False),(2,'keywords',[]),(2,'expectedMaterialIdentity',False),
                 (2,'rendererCount',2),(2,'loadedObjectCount',33),(2,'loadedObjectCount',0)]
        for index,key,value in changes:
            rows=marker_records();rows[index][1][key]=value;write_xml(self.xml,rows)
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.parse()
        for value in (float('nan'),float('inf'),-float('inf')):
            rows=marker_records();rows[0][1]['beforeEmissionColor']['g']=value;write_xml(self.xml,rows)
            with self.assertRaises(ValueError):self.parse()
    def test_hdr_1e6_bound_and_exact_native_before_after_agreement(self):
        for index,key in ((0,'beforeEmissionColor'),(0,'afterEmissionColor'),(2,'emissionColor')):
            rows=marker_records();rows[index][1][key]['g']+=2e-6;write_xml(self.xml,rows)
            with self.assertRaises(ValueError):self.parse()
        rows=marker_records();rows[0][1]['beforeEmissionColor']['g']=1.9;write_xml(self.xml,rows)
        with self.assertRaisesRegex(ValueError,'before/after'):self.parse()
    def test_duplicate_json_key_oversized_or_prefixed_marker_rejected(self):
        normal='\n'.join(p+json.dumps(r) for p,r in marker_records())
        for bad in (normal.replace('"beforeGIFlags": 4','"beforeGIFlags": 4, "beforeGIFlags": 4'),
                    normal.replace(emission.LIFECYCLE_MARKER,'prefix '+emission.LIFECYCLE_MARKER),
                    emission.LIFECYCLE_MARKER+'{"x":"'+'x'*9000+'"}'):
            write_xml(self.xml,output=bad)
            with self.assertRaises(ValueError):self.parse()
    def test_only_unique_passed_case_output_is_accepted(self):
        write_xml(self.xml);self.xml.write_text(self.xml.read_text().replace('Passed','Failed'))
        with self.assertRaises(ValueError):self.parse()
        write_xml(self.xml);tree=ET.parse(self.xml);root=tree.getroot();case=root.find('test-case')
        text=case.find('output').text;case.remove(case.find('output'));ET.SubElement(root,'output').text=text;tree.write(self.xml,encoding='unicode')
        with self.assertRaises(ValueError):self.parse()
        write_xml(self.xml);shutil.copyfile(self.xml,self.directory/'duplicate.xml')
        with self.assertRaises(ValueError):self.parse()
    def test_serialized_material_cross_check_rejects_black_keyword_off_and_wrong_gi(self):
        p=self.directory/'target.mat';p.write_bytes(MATERIAL);self.assertEqual(emission.serialized_material(p)['emissionColor'],emission.HDR)
        for old,new in ((b'm_LightmapFlags: 2',b'm_LightmapFlags: 4'),(b'  - _EMISSION',b'  - _NORMALMAP'),
                        (b'g: 1.9',b'g: 1.8'),(b'r: 2.5',b'r: 0'),(b'&2100000',b'&2100001')):
            p.write_bytes(MATERIAL.replace(old,new))
            with self.assertRaises(ValueError):emission.serialized_material(p)
    def test_actual_zero_loaded_audit_rows_allowed_without_invention(self):
        emission.validate_loaded(dict(freeze=[],postcapture=[],postexitObservable=False))
        dirty=dict(objectType='UnityEditor.Rendering.Universal.AssetVersion',localFileId=123,hasLocalFileId=True,isDirty=True)
        with self.assertRaises(ValueError):emission.validate_loaded(dict(freeze=[],postcapture=[dirty],postexitObservable=False))


class PackagingTests(unittest.TestCase):
    fixtures_png=previous.AuditTests.fixtures_png
    host_runtime=previous.ReadOnlyHostExitTests.host_runtime
    native_readonly=previous.ReadOnlyHostExitTests.native_readonly
    assert_pixels_bundle=previous.ReadOnlyHostExitTests.assert_pixels_bundle
    tearDown=previous.AuditTests.tearDown
    def setUp(self):
        previous.ReadOnlyHostExitTests.setUp(self)
        self.identity.update(editorVersion=emission.source.VERSION,exportManifestSha256='c'*64,sourceStateSha256='d'*64)
        for suffix,data in (('',MATERIAL),('.meta',META)):
            name=emission.TARGET+suffix;path=self.root/name;path.write_bytes(data);sha=emission.source.sha(path)
            self.base.report['generatedFiles'].append(dict(path=name,beforeSha256=sha,afterSha256=sha))
            self.freeze[name]=sha
            for phase in ('freeze','postcapture'):
                copy_path=self.auditroot/'internal'/phase/name;copy_path.parent.mkdir(parents=True,exist_ok=True);copy_path.write_bytes(data)
                record_path=self.auditroot/(phase+'.json');record=json.loads(record_path.read_text())
                record['files'].append(dict(path=name,sha256=sha,size=len(data)))
                if not suffix and phase=='postcapture':
                    record['loadedObjects'].append(dict(path=name,objectType='UnityEngine.Material',localFileId=2100000,hasLocalFileId=True,isDirty=False))
                record_path.write_text(json.dumps(record))
        self.base.report['generatedFiles'].sort(key=lambda r:r['path']);self.base.save();write_xml(self.xml)
    def run_package(self):
        with self.native_readonly(),self.host_runtime(),contextlib.redirect_stdout(io.StringIO()):emission.package()
    def diagnose_failure(self):
        emission.audit.diagnose('failure')
        report=self.assert_pixels_bundle('NATIVE_RENDERED_DIAGNOSTIC_ONLY')
        self.assertTrue(all(row['status']=='VERIFIED' for row in report['phaseAvailability'].values()))
        self.assertNotIn('differences',report)
        self.assertFalse(any(p.name.startswith('.environment-emission-') for p in self.accepted.parent.iterdir()))
        return report
    def refresh_manifest(self):
        (self.accepted/'SHA256SUMS.json').unlink();emission.v4.write_manifest(self.accepted)
    def test_full_original_strict_package_then_add_one_proof_and_independent_consumer(self):
        with mock.patch.object(emission.audit,'package',wraps=emission.audit.package) as original:
            self.run_package();original.assert_called_once()
        proof=emission.validate_exported_proof(self.accepted)
        self.assertEqual(proof['producerRevision'],emission.REVISION);self.assertFalse(proof['legacyTerrainSubproof']['wholePackageDiffuseOnly'])
        self.assertTrue(proof['authoredGiSemantics']['futureBakeEligible']);self.assertFalse(proof['authoredGiSemantics']['bakePerformedByThisFix'])
        self.assertEqual(proof['auditLoadedObjects']['freeze'],[])
        self.assertEqual(proof['native']['xmlSha256'],emission.source.sha(self.xml))
        self.assertNotIn('PRIVATE_UNRELATED_LOG',json.dumps(proof));self.assertNotIn('PRIVATE_UNRELATED_LOG',''.join(p.name for p in self.accepted.rglob('*')))
        with (mock.patch.object(emission.source,'PROJECT',Path('/not-a-native-project')),mock.patch.object(emission.source,'TASK',Path('/not-a-source-task')),
             mock.patch.object(emission.legacy,'inspect_native_report',side_effect=AssertionError('must not read native')),
             mock.patch.object(emission.source,'identity',side_effect=AssertionError('must not read environment'))):
            self.assertEqual(emission.validate_exported_proof(self.accepted),proof)
        with self.host_runtime(),contextlib.redirect_stdout(io.StringIO()):
            emission.audit.diagnose('success')
            self.assertEqual(json.loads((self.output/'lifecycle-audit.json').read_text())['packageOutcome'],'success')
    def test_postcapture_dirty_marker_after_real_strict_success_keeps_twenty_png_fallback(self):
        rows=marker_records();rows[2][1]['materialDirty']=True;write_xml(self.xml,rows)
        called=[]
        original=emission.r4.package
        def strict():
            original();called.append(emission.r4.OUT.is_dir())
        with self.native_readonly(),self.host_runtime(),contextlib.redirect_stdout(io.StringIO()),mock.patch.object(emission.r4,'package',strict):
            with self.assertRaisesRegex(ValueError,'dirty/keyword'):emission.package()
            self.assertEqual(called,[True]);self.assertFalse(self.accepted.exists());self.diagnose_failure()
    def test_wrong_postcapture_gi_after_real_strict_success_keeps_twenty_png_fallback(self):
        rows=marker_records();rows[2][1]['giFlags']=4;write_xml(self.xml,rows)
        with self.native_readonly(),self.host_runtime(),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'renderer/GI'):emission.package()
            self.assertFalse(self.accepted.exists());self.diagnose_failure()
    def test_actual_audit_subobject_dirty_is_not_hidden_by_clean_marker(self):
        p=self.auditroot/'postcapture.json';record=json.loads(p.read_text());record['loadedObjects'].append(
            dict(path=emission.TARGET,objectType='UnityEditor.Rendering.Universal.AssetVersion',localFileId=123,hasLocalFileId=True,isDirty=True));p.write_text(json.dumps(record))
        with self.native_readonly(),self.host_runtime(),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'audit dirty'):emission.package()
            self.diagnose_failure()
    def test_exported_proof_scalar_hash_hdr_scope_and_closure_tampering_fail(self):
        self.run_package();path=self.accepted/emission.PROOF;original=json.loads(path.read_text())
        mutations=[lambda p:p['phaseFiles']['meta']['postexit'].update(sha256='e'*64),
            lambda p:p['observations']['postcapture'].update(materialDirty=True),
            lambda p:p['authorLifecycle']['afterEmissionColor'].update(g=1.8),
            lambda p:p['authoredGiSemantics'].update(futureBakeEligible=1),
            lambda p:p['legacyTerrainSubproof'].update(wholePackageDiffuseOnly=0),
            lambda p:p['identity'].update(sourceStateSha256='f'*64),
            lambda p:p['native'].update(xmlSha256='f'*64),
            lambda p:p['serializedMaterial']['baseColor'].update(r=True),
            lambda p:p['serializedMaterial']['shader'].update(fileID=4800000.0),lambda p:p.update(unknown='PRIVATE')]
        for change in mutations:
            value=copy.deepcopy(original);change(value);path.write_text(json.dumps(value));self.refresh_manifest()
            with self.assertRaises(ValueError):emission.validate_exported_proof(self.accepted)
        path.write_text(json.dumps(original)+' '*emission.MAX_PROOF);self.refresh_manifest()
        with self.assertRaisesRegex(ValueError,'proof bound'):emission.validate_exported_proof(self.accepted)
        path.write_text(json.dumps(original));self.refresh_manifest()
        (self.accepted/'unexpected.log').write_text('PRIVATE');self.refresh_manifest()
        with self.assertRaisesRegex(ValueError,'closed set'):emission.validate_exported_proof(self.accepted)
    def test_generated_mat_meta_and_png_crosschecks_fail_even_with_rewritten_manifest(self):
        self.run_package()
        for relative in ('generated/'+emission.TARGET,'generated/'+emission.TARGET+'.meta','NightBeacon-ground.png'):
            path=self.accepted/relative;original=path.read_bytes();path.write_bytes(original+b'changed');self.refresh_manifest()
            with self.subTest(relative=relative),self.assertRaises(ValueError):emission.validate_exported_proof(self.accepted)
            path.write_bytes(original);self.refresh_manifest()
    def test_packaged_missing_png_failure_never_blocks_native_twenty_png_fallback(self):
        original=emission.build_proof
        def missing(stage):
            (stage/'NightBeacon-ground.png').unlink();return original(stage)
        with self.native_readonly(),self.host_runtime(),contextlib.redirect_stdout(io.StringIO()),mock.patch.object(emission,'build_proof',missing):
            with self.assertRaises(ValueError):emission.package()
            self.diagnose_failure()
    def test_proof_write_readback_failure_cleans_stage_then_preserves_original_pixels(self):
        original=Path.write_text
        def corrupt(path,data,*args,**kwargs):
            return original(path,'{}' if path.name==emission.PROOF else data,*args,**kwargs)
        with self.native_readonly(),self.host_runtime(),contextlib.redirect_stdout(io.StringIO()),mock.patch.object(Path,'write_text',corrupt):
            with self.assertRaisesRegex(ValueError,'write/readback'):emission.package()
            self.diagnose_failure()
    def test_atomic_final_publish_failure_leaves_no_strictout_or_stage(self):
        original=Path.rename
        def denied(path,target):
            if Path(target)==self.accepted:raise PermissionError('synthetic publish failure')
            return original(path,target)
        with self.native_readonly(),self.host_runtime(),contextlib.redirect_stdout(io.StringIO()),mock.patch.object(Path,'rename',denied):
            with self.assertRaises(PermissionError):emission.package()
            self.diagnose_failure()
    def test_three_phase_mismatch_and_wrong_yaml_emission_not_accepted(self):
        for phase in ('freeze','postcapture'):
            rows=self.auditroot/(phase+'.json');record=json.loads(rows.read_text())
            target=next(r for r in record['files'] if r['path']==emission.TARGET);target['sha256']='f'*64;rows.write_text(json.dumps(record))
            break
        with self.native_readonly(),self.host_runtime(),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ValueError):emission.package()
            self.assertFalse(self.accepted.exists())
    def test_success_does_not_modify_old_receipt_or_old_native_source_files(self):
        saved=[];original=emission.build_proof
        def inspect(stage):
            saved.append((stage/'receipt.json').read_bytes());return original(stage)
        with mock.patch.object(emission,'build_proof',inspect):self.run_package()
        self.assertEqual((self.accepted/'receipt.json').read_bytes(),saved[0])
        self.assertEqual(json.loads(saved[0])['candidateRevision'],'R4_DIFFUSE_ONLY')
        self.assertEqual(len(list(self.accepted.glob('*.png'))),20)
        self.assertFalse(any(p.suffix in ('.xml','.log') for p in self.accepted.rglob('*')))


if __name__=='__main__':unittest.main()
