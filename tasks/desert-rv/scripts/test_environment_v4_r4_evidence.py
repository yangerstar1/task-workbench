#!/usr/bin/env python3
"""Real R3 serialized excerpts inside synthetic validator scaffolding, never R4 native proof."""
import base64
import copy
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import environment_v4_r4_evidence as r4

FIXTURE = r4.source.TASK/'art/environment-v4/r4-native-yaml-fixture.json'


class R4EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'project';self.root.mkdir()
        self.fixture=json.loads(FIXTURE.read_text())
        self.assertEqual(self.fixture['sourceRun'],'37961223152')
        contract=r4.v4.load_contract();names=set(contract['files'])|set(contract['metadata_files'])|{r4.v4.legacy.GENERATED+'.meta'}
        for name in ('JourneyBootstrap.unity','FirstStation.unity','Scrapyard.unity','NightBeacon.unity','JourneyContent.asset'):
            names|={r4.v4.legacy.GENERATED+'/'+name,r4.v4.legacy.GENERATED+'/'+name+'.meta'}
        for name in names:
            self.write(name,'fileFormatVersion: 2\nguid: '+'b'*32+'\n' if name.endswith('.meta') else '%YAML 1.1\n--- !u!43 &4300000\nMesh:\n  m_Name: SYNTHETIC_UNIT_SCAFFOLD\n')
        for name,text in self.fixture['files'].items():self.write(name,text)
        for name in (r4.CORRECTED,r4.comparison.ORIGINAL):
            for suffix in ('','.meta'):
                dest=self.root/(name+suffix);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(r4.source.PROJECT/(name+suffix),dest)
        before={name:r4.source.sha(self.root/name) for name in names}
        mats=[]
        for name in r4.MATERIALS:
            path=self.root/name;original=path.read_bytes();path.write_bytes(r4.corrected_material_bytes(original))
            actual=dict(name=path.stem,shader='Universal Render Pipeline/Lit',baseMapAsset=r4.CORRECTED,
                normalMapAsset=r4.comparison.ART+'sand_03_nor_gl_1k.jpg',keywords=['_NORMALMAP'],normalScale=.035,smoothness=.04,metallic=0,
                normalKeyword=True,baseScale=dict(x=1,y=1),baseOffset=dict(x=0,y=0),normalUvScale=dict(x=1,y=1),normalUvOffset=dict(x=0,y=0),
                baseColor=dict(r=1.75,g=1.52,b=1.16,a=1))
            mats.append(dict(path=name,originalSerializedBase64=base64.b64encode(original).decode(),originalSha256=r4.digest(original),
                savedSha256=r4.source.sha(path),baseMapAsset=r4.CORRECTED,baseMapSha256=r4.CORRECTED_SHA,
                mainTexAsset=r4.CORRECTED,mainTexSha256=r4.CORRECTED_SHA,onlyAlbedoReferencesChanged=True,
                saveImportCycles=2,secondSaveImportBytesStable=True,actual=actual))
        bindings=[]
        for region,name in enumerate(r4.v4.legacy.REGIONS,1):bindings.extend(r4.inspect_scene_bindings(self.root,region,r4.v4.legacy.GENERATED+'/'+name+'.unity'))
        self.report=dict(schema=1,status=r4.STATUS,postCaptureImageCount=20,postCaptureVerified=True,allOtherGeneratedBytesPreserved=True,
            correctedDiffuse=dict(r4.IMPORT_SETTINGS,assetPath=r4.CORRECTED,sha256=r4.CORRECTED_SHA,metaSha256=r4.CORRECTED_META_SHA,guid=r4.CORRECTED_GUID),
            materials=mats,terrainBindings=bindings,generatedFiles=[dict(path=name,beforeSha256=before[name],afterSha256=r4.source.sha(self.root/name)) for name in sorted(names)])
        self.save()
    def tearDown(self):self.temp.cleanup()
    def write(self,name,text):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    def save(self):self.write(r4.CAPTURE+'/'+r4.REPORT,json.dumps(self.report))
    def reject(self,pattern=None):
        self.save()
        with self.assertRaisesRegex(ValueError,pattern or '.'):
            r4.inspect_corrected(self.root)
    def resnapshot(self,name):
        row=next(row for row in self.report['generatedFiles'] if row['path']==name)
        row['beforeSha256']=row['afterSha256']=r4.source.sha(self.root/name)
    def test_real_r3_material_and_nine_scene_excerpt_bindings_pass(self):
        report=r4.inspect_corrected(self.root);self.assertEqual(len(report['terrainBindings']),9)
        self.assertEqual(len(report['generatedFiles']),254)
    def test_single_alias_change_is_rejected(self):
        path=self.root/r4.MATERIALS[0];raw=path.read_bytes();pos=raw.index(b'    - _MainTex:');raw=raw[:pos]+raw[pos:].replace(r4.CORRECTED_GUID.encode(),r4.ORIGINAL_GUID.encode(),1);path.write_bytes(raw)
        self.reject()
    def test_other_property_change_even_with_forged_final_hash_is_rejected(self):
        path=self.root/r4.MATERIALS[0];path.write_bytes(path.read_bytes().replace(b'_BumpScale: 0.035',b'_BumpScale: 0.7'))
        sha=r4.source.sha(path);self.report['materials'][0]['savedSha256']=sha
        next(row for row in self.report['generatedFiles'] if row['path']==r4.MATERIALS[0])['afterSha256']=sha
        self.reject('beyond the two')
    def test_duplicate_albedo_field_is_rejected(self):
        original=base64.b64decode(self.report['materials'][0]['originalSerializedBase64']);original+=b'    - _BaseMap:\n        m_Texture: {fileID: 2800000, guid: '+r4.ORIGINAL_GUID.encode()+b', type: 3}\n'
        with self.assertRaises(ValueError):r4.corrected_material_bytes(original)
    def test_changed_frozen_mesh_is_rejected(self):
        path=self.root/(r4.v4.POLISH+'/R1-Ground-Sand.asset');path.write_text(path.read_text()+'  changed: 1\n');self.reject('Frozen generated bytes')
    def test_additional_material_cannot_hide(self):
        self.write(r4.v4.POLISH+'/Surface-Unapproved.mat','%YAML 1.1\n');self.reject('membership differs')
    def test_frozen_membership_cannot_omit_scene(self):
        self.report['generatedFiles'].pop();self.reject('generated count')
    def test_forged_corrected_texture_hash_is_rejected(self):
        self.report['correctedDiffuse']['sha256']='0'*64;self.reject('importer identity')
    def test_importer_source_drift_is_rejected(self):
        path=self.root/(r4.CORRECTED+'.meta');path.write_text(path.read_text().replace('filterMode: 2','filterMode: 1'));self.reject('importer source')
    def test_reported_sampler_drift_is_rejected(self):
        self.report['correctedDiffuse']['filterMode']=1;self.reject('importer identity')
    def test_boolean_cannot_stand_in_for_enum(self):
        self.report['correctedDiffuse']['textureShape']=True;self.reject('importer identity')
    def test_pre_capture_receipt_is_rejected(self):
        self.report['postCaptureVerified']=False;self.reject('post-twenty')
    def test_second_save_import_must_be_stable(self):
        self.report['materials'][0]['secondSaveImportBytesStable']=False;self.reject('actual corrected')
    def test_missing_region_binding_is_rejected(self):
        self.report['terrainBindings'].pop();self.reject('three-region bindings')
    def test_forged_scene_material_reference_fails_independent_parse(self):
        name=r4.v4.legacy.GENERATED+'/Scrapyard.unity';path=self.root/name
        guid=r4.guid(self.root,r4.MATERIALS[0]);path.write_text(path.read_text().replace(guid,'a'*32));self.resnapshot(name)
        self.reject('MeshRenderers')
    def test_forged_scene_mesh_reference_fails_independent_parse(self):
        name=r4.v4.legacy.GENERATED+'/NightBeacon.unity';path=self.root/name
        guid=r4.guid(self.root,r4.v4.POLISH+'/R3-Ground-Sand.asset');path.write_text(path.read_text().replace(guid,'a'*32));self.resnapshot(name)
        self.reject('mesh binding')
    def test_forged_scene_parent_fails_independent_parse(self):
        name=r4.v4.legacy.GENERATED+'/FirstStation.unity';path=self.root/name
        text=path.read_text();match=re.search(r'  m_Name: EnvironmentV4 Ground-Sand.*?  m_Father: \{fileID: (-?\d+)\}',text,re.S)
        self.assertIsNotNone(match);text=text[:match.start(1)]+'0'+text[match.end(1):];path.write_text(text);self.resnapshot(name)
        self.reject('terrain parent')
    def test_duplicate_native_report_member_rejected(self):
        self.write(r4.CAPTURE+'/Unity.log','not exported');self.reject('membership')
    def test_input_texture_mutation_rejected(self):
        p=self.root/r4.CORRECTED;p.write_bytes(p.read_bytes()+b'changed');self.reject('digest differs')
    def test_original_material_snapshot_hash_is_checked(self):
        self.report['materials'][0]['originalSha256']='f'*64;self.reject('snapshot digest')
    def test_partial_uses_original_source_mismatch_gate(self):
        target=Path(self.temp.name)/'unaccepted'
        with mock.patch.object(r4,'PARTIAL',target),mock.patch.object(r4.source,'PROJECT',self.root),mock.patch.object(r4.v4,'partial',side_effect=ValueError('actual nonempty protected-source difference')) as legacy:
            with self.assertRaisesRegex(ValueError,'actual nonempty'):r4.partial()
            legacy.assert_called_once();self.assertFalse(target.exists())
    def test_packaging_calls_retained_gates_before_atomic_publish(self):
        target=Path(self.temp.name)/'final';called=[]
        def retained():
            called.append(True);self.assertFalse(target.exists());stage=r4.v4.OUT;stage.mkdir()
            (stage/'receipt.json').write_text(json.dumps(dict(nativeRenderTest=r4.v4.legacy.RENDER_TEST,scope=r4.v4.STATUS)))
            for row in self.report['generatedFiles']:
                dest=stage/'generated'/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(self.root/row['path'],dest)
            (stage/'native-placeholder.txt').write_text('UNIT TEST ONLY');r4.v4.write_manifest(stage)
        with mock.patch.object(r4,'OUT',target),mock.patch.object(r4.source,'PROJECT',self.root),mock.patch.object(r4.v4,'package',side_effect=retained):r4.package()
        self.assertEqual(called,[True]);r4.verify_manifest(target)
        self.assertEqual(json.loads((target/'receipt.json').read_text())['schema'],r4.SCHEMA)
    def test_retained_gate_failure_never_publishes_partial_bundle(self):
        target=Path(self.temp.name)/'final'
        def fail():r4.v4.OUT.mkdir();(r4.v4.OUT/'partial.txt').write_text('UNIT TEST');raise ValueError('retained native gate failed')
        with mock.patch.object(r4,'OUT',target),mock.patch.object(r4.source,'PROJECT',self.root),mock.patch.object(r4.v4,'package',side_effect=fail):
            with self.assertRaisesRegex(ValueError,'retained native'):r4.package()
        self.assertFalse(target.exists())
    def test_invalid_proof_never_calls_legacy_packager(self):
        self.report['postCaptureVerified']=False;self.save()
        with mock.patch.object(r4,'OUT',Path(self.temp.name)/'final'),mock.patch.object(r4.source,'PROJECT',self.root),mock.patch.object(r4.v4,'package') as retained:
            with self.assertRaises(ValueError):r4.package()
            retained.assert_not_called()

if __name__=='__main__':unittest.main()
