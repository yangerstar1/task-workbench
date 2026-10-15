#!/usr/bin/env python3
"""Synthetic reflection evidence negatives, no Unity/Docker or pixel decoding."""
import ast
import copy
import re
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import reflection_bake_ci as bake

IDENT=dict(scope=bake.visual.SCOPE,sourceCommit='1'*40,reviewedCandidateCommit='2'*40,runId='123',runAttempt='1')
ENV=dict(GITHUB_SHA=IDENT['sourceCommit'],GITHUB_RUN_ID=IDENT['runId'],GITHUB_RUN_ATTEMPT=IDENT['runAttempt'])


def exr(width=128,height=768):
    return b'\x76\x2f\x31\x01'+struct.pack('<I',2)+b'dataWindow\0box2i\0'+struct.pack('<I',16)+struct.pack('<4i',0,0,width-1,height-1)+b'\0'+b'\0'*128


def meta(guid):
    return ('fileFormatVersion: 2\nguid: '+guid+'\nTextureImporter:\n  externalObjects: {}\n  serializedVersion: 13\n  mipmaps:\n    enableMipMap: 1\n    sRGBTexture: 0\n  textureShape: 2\n  platformSettings:\n  - serializedVersion: 4\n    buildTarget: DefaultTexturePlatform\n    textureFormat: 17\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n').encode()


def fixture(root):
    unity=root/bake.TASK/'unity'
    for name in bake.RECIPE_SOURCES+bake.DEPENDENCIES:
        p=unity/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'SYNTHETIC_SOURCE')
    receipt=dict(schemaVersion=1,status='COMPLETE_BAKED_STATIC_REFLECTIONS',recipe=bake.RECIPE,sourceCommit=IDENT['sourceCommit'],runId=IDENT['runId'],runAttempt=IDENT['runAttempt'],unityVersion='6000.3.19f1',colorSpace='Gamma',runtimeDependencyHash='a'*32,pipelineDependencyHash='b'*32,captureRenderers=39,captureTriangles=70000)
    source=root/bake.SOURCE;source.mkdir(parents=True)
    for key,name in (('day','Day.exr'),('night','Night.exr')):
        data=exr();m=meta(bake.GUIDS[key]);(source/name).write_bytes(data);(source/(name+'.meta')).write_bytes(m)
        receipt[key]=dict(file=name,sha256=bake.digest(data),metaSha256=bake.digest(m),metaGuid=bake.GUIDS[key],format='RGBAHalf',shape='Cube',bytes=len(data),metaBytes=len(m),sourceWidth=128,sourceHeight=768,faceSize=128,mipCount=8,linear=True,specular=True,pixelSampleCount=98304,maxChannelRange=.5)
    receipt['sourceDigest']=bake.source_digest(root,receipt)
    (source/'reflection-receipt.json').write_text(json.dumps(receipt))
    bake.visual.write(bake.visual.outdir(root)/'source-receipt.json',IDENT)
    return receipt


class ReflectionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.receipt=fixture(self.root)
        self.env=patch.dict(os.environ,ENV);self.env.start();self.addCleanup(self.env.stop)
    def save(self):
        (self.root/bake.SOURCE/'reflection-receipt.json').write_text(json.dumps(self.receipt))
    def export(self):
        bake.export_reflections(self.root)
    def test_recipe_sources_exactly_match_native_policy_and_pinned_verifier(self):
        expected = {
            'Assets/G3/Interaction/G3ShopEnvironment.cs',
            'Assets/G3/Editor/G3ShopReflectionBaker.cs',
            'Assets/G3/Interaction/G3ContactOcclusionFeature.cs',
            'Assets/G3/Interaction/G3ContactOcclusionFeature.cs.meta',
            'Assets/G3/Editor/G3ShopArtImporter.cs',
            'Assets/G3/Editor/G3Build.cs',
            'Packages/manifest.json', 'Packages/packages-lock.json',
        }
        self.assertEqual(len(bake.RECIPE_SOURCES), 8)
        self.assertEqual(set(bake.RECIPE_SOURCES), expected)
        repository = Path(__file__).resolve().parents[3]
        source = (repository / bake.TASK / 'unity/Assets/G3/Editor/G3ShopReflectionBaker.cs').read_text()
        block = source.split('static readonly string[] RecipeSources={', 1)[1].split('};', 1)[0]
        native = re.findall(r'"([^"]+)"', block)
        self.assertEqual(len(native), 8)
        self.assertEqual(set(native), expected)
        policy = json.loads((repository / bake.TASK / 'scripts/stage_a_inventory/policy.json').read_text())
        self.assertEqual(len(policy['recipeSources']), 8)
        self.assertEqual(set(policy['recipeSources']), expected)
        pinned = repository / bake.TASK / 'scripts/counter_light_diagnostics/pinned_dependencies/reflection_bake_ci.py'
        constants = [node for node in ast.parse(pinned.read_text()).body
                     if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'RECIPE_SOURCES' for t in node.targets)]
        self.assertEqual(len(constants), 1)
        self.assertEqual(ast.literal_eval(constants[0].value), bake.RECIPE_SOURCES)

    def test_each_contact_feature_source_and_meta_mutation_rejects_export(self):
        for name in ('Assets/G3/Interaction/G3ContactOcclusionFeature.cs',
                     'Assets/G3/Interaction/G3ContactOcclusionFeature.cs.meta'):
            with self.subTest(name=name):
                path = self.root / bake.TASK / 'unity' / name
                before = path.read_bytes()
                try:
                    path.write_bytes(before + b'CHANGED')
                    with self.assertRaisesRegex(ValueError, 'REFLECTION_SOURCE_INPUT_CHANGED'):
                        self.export()
                finally:
                    path.write_bytes(before)
                self.assertFalse((bake.visual.outdir(self.root)/'reflections/reflection-receipt.json').exists())

    def test_each_contact_feature_source_and_meta_missing_rejects_export(self):
        for name in ('Assets/G3/Interaction/G3ContactOcclusionFeature.cs',
                     'Assets/G3/Interaction/G3ContactOcclusionFeature.cs.meta'):
            with self.subTest(name=name):
                path = self.root / bake.TASK / 'unity' / name
                before = path.read_bytes()
                try:
                    path.unlink()
                    with self.assertRaises(ValueError):
                        self.export()
                finally:
                    path.write_bytes(before)
                self.assertFalse((bake.visual.outdir(self.root)/'reflections/reflection-receipt.json').exists())

    def test_legacy_six_source_digest_cannot_pass_current_eight_source_contract(self):
        legacy = tuple(name for name in bake.RECIPE_SOURCES if 'G3ContactOcclusionFeature' not in name)
        self.assertEqual(len(legacy), 6)
        with patch.object(bake, 'RECIPE_SOURCES', legacy):
            legacy_digest = bake.source_digest(self.root, self.receipt)
        self.assertNotEqual(legacy_digest, self.receipt['sourceDigest'])
        self.receipt['sourceDigest'] = legacy_digest
        self.save()
        with self.assertRaisesRegex(ValueError, 'REFLECTION_SOURCE_INPUT_CHANGED'):
            self.export()

    def test_contact_feature_symlink_cannot_replace_bound_source(self):
        for name in ('Assets/G3/Interaction/G3ContactOcclusionFeature.cs',
                     'Assets/G3/Interaction/G3ContactOcclusionFeature.cs.meta'):
            with self.subTest(name=name):
                path = self.root / bake.TASK / 'unity' / name
                before = path.read_bytes()
                target = self.root / 'outside-bound-source'
                target.write_bytes(before)
                try:
                    path.unlink(); path.symlink_to(target)
                    with self.assertRaisesRegex(ValueError, 'REFLECTION_INPUT_PATH_REJECTED'):
                        self.export()
                finally:
                    path.unlink(); path.write_bytes(before); target.unlink()

    def test_valid_five_originals_preserved_byte_exact(self):
        self.export();out=bake.visual.outdir(self.root)/'reflections'
        self.assertEqual({p.name for p in out.iterdir()},set(bake.FILES))
        for name in bake.FILES:self.assertEqual((out/name).read_bytes(),(self.root/bake.SOURCE/name).read_bytes())
    def test_wrong_source_run_attempt_and_unbound_rejected(self):
        for key in ('sourceCommit','runId','runAttempt'):
            value=copy.deepcopy(self.receipt);value[key]='LOCAL_UNBOUND'
            with self.subTest(key=key),self.assertRaises(ValueError):bake.validate_receipt(value,IDENT)
        with patch.dict(os.environ,GITHUB_RUN_ATTEMPT='2'),self.assertRaises(ValueError):self.export()
    def test_unknown_fields_free_paths_and_missing_fields_rejected(self):
        for change in (lambda x:x.update(rawLog='SYNTHETIC_PRIVATE'),lambda x:x['day'].update(path='/tmp/private'),lambda x:x.pop('sourceDigest'),lambda x:x['night'].pop('linear'),lambda x:x['day'].update(file='../Day.exr')):
            value=copy.deepcopy(self.receipt);change(value)
            with self.assertRaises(ValueError):bake.validate_receipt(value,IDENT)
    def test_duplicate_json_keys_at_every_level_never_export_raw_hidden_values(self):
        original=json.dumps(self.receipt)
        variants=[original.replace('"schemaVersion": 1','"schemaVersion": "SYNTHETIC_PRIVATE_SECRET", "schemaVersion": 1',1),
                  original.replace('"file": "Day.exr"','"file": "SYNTHETIC_PRIVATE_SECRET", "file": "Day.exr"',1),
                  original.replace('"file": "Night.exr"','"file": "SYNTHETIC_PRIVATE_SECRET", "file": "Night.exr"',1),
                  original.replace('"schemaVersion": 1','"schemaVersion": 1, "schemaVersion": 1',1),
                  original.replace('"schemaVersion": 1','"schemaVersion": 1, "schema\\u0056ersion": 1',1)]
        for raw in variants:
            with self.subTest(raw=variants.index(raw)):
                (self.root/bake.SOURCE/'reflection-receipt.json').write_text(raw)
                with self.assertRaises(ValueError):self.export()
                self.assertFalse((bake.visual.outdir(self.root)/'reflections/reflection-receipt.json').exists())
        with self.assertRaises(ValueError):bake.load_receipt('{"nested": {"x": 1,"x": 2}}')
    def test_incomplete_wrong_recipe_or_import_contract_rejected(self):
        for change in (lambda x:x.update(status='BAKE_IN_PROGRESS'),lambda x:x.update(recipe='old'),lambda x:x.update(unityVersion='6000.3.1f1'),lambda x:x.update(colorSpace='Linear'),lambda x:x['day'].update(mipCount=7),lambda x:x['night'].update(faceSize=64),lambda x:x['day'].update(format='RGBA32'),lambda x:x['night'].update(shape='2D'),lambda x:x['day'].update(linear=False),lambda x:x['night'].update(specular=False)):
            value=copy.deepcopy(self.receipt);change(value)
            with self.assertRaises(ValueError):bake.validate_receipt(value,IDENT)
    def test_integer_bounds_bool_and_malformed_hashes_rejected(self):
        for key,bad in [('bytes',8388609),('metaBytes',16385),('sourceWidth',127),('sourceHeight',2049),('faceSize',True),('mipCount',8.0),('sha256','a'*63),('metaSha256','Z'*64),('metaGuid','c'*32)]:
            value=copy.deepcopy(self.receipt);value['day'][key]=bad
            with self.subTest(key=key),self.assertRaises(ValueError):bake.validate_receipt(value,IDENT)
        for key in ('runtimeDependencyHash','pipelineDependencyHash','sourceDigest'):
            value=copy.deepcopy(self.receipt);value[key]='not-a-hash'
            with self.assertRaises(ValueError):bake.validate_receipt(value,IDENT)
    def test_missing_file_and_corrupt_original_hash_rejected(self):
        p=self.root/bake.SOURCE/'Day.exr';original=p.read_bytes();p.unlink()
        with self.assertRaises(ValueError):self.export()
        p.write_bytes(original+b'CHANGED')
        with self.assertRaises(ValueError):self.export()
    def test_static_geometry_and_non_background_pixels_required(self):
        for field,bad in [('captureRenderers',0),('captureRenderers',4097),('captureRenderers',True),('captureTriangles',0),('captureTriangles',2000001)]:
            value=copy.deepcopy(self.receipt);value[field]=bad
            with self.subTest(field=field,bad=bad),self.assertRaises(ValueError):bake.validate_receipt(value,IDENT)
        for field,bad in [('pixelSampleCount',98303),('pixelSampleCount',98305),('pixelSampleCount',True),('maxChannelRange',0),('maxChannelRange',.01),('maxChannelRange',-1),('maxChannelRange',65505),('maxChannelRange',True),('maxChannelRange',float('nan')),('maxChannelRange',float('inf'))]:
            value=copy.deepcopy(self.receipt);value['day'][field]=bad
            with self.subTest(field=field,bad=bad),self.assertRaises(ValueError):bake.validate_receipt(value,IDENT)
    def test_meta_corruption_and_guid_mismatch_rejected(self):
        p=self.root/bake.SOURCE/'Night.exr.meta';p.write_bytes(meta('f'*32))
        with self.assertRaises(ValueError):self.export()
        self.receipt['night'].update(metaSha256=bake.digest(p.read_bytes()),metaBytes=p.stat().st_size);self.save()
        with self.assertRaises(ValueError):self.export()
    def test_source_dimension_and_exr_header_mismatch_rejected(self):
        self.receipt['day']['sourceWidth']=256;self.save()
        with self.assertRaises(ValueError):self.export()
        for value in [b'NOT_EXR'*32,exr()[:30],exr().replace(b'box2i',b'float'),exr().replace(struct.pack('<I',2),struct.pack('<I',0x1002),1)]:
            with self.assertRaises(ValueError):bake.exr_size(value)
    def test_changed_recipe_or_generated_source_is_not_valid_cache(self):
        for name in (bake.RECIPE_SOURCES[0],bake.DEPENDENCIES[0]):
            p=self.root/bake.TASK/'unity'/name;old=p.read_bytes();p.write_bytes(b'CHANGED')
            with self.assertRaises(ValueError):self.export()
            p.write_bytes(old)
        self.receipt['runtimeDependencyHash']='d'*32;self.save()
        with self.assertRaises(ValueError):self.export()
    def test_reflection_outputs_excluded_from_input_digest_only(self):
        before=bake.source_digest(self.root,self.receipt);source=self.root/bake.SOURCE
        (source/'ignored-output.tmp').write_bytes(b'GENERATED');(source.parent/'Reflections.meta').write_bytes(b'GENERATED')
        self.assertEqual(before,bake.source_digest(self.root,self.receipt))
        (source.parent/'NewMaterial.mat').write_bytes(b'NEW_INPUT')
        self.assertNotEqual(before,bake.source_digest(self.root,self.receipt))
    def test_text_and_external_reference_baits_rejected(self):
        original=meta(bake.GUIDS['day'])
        for marker in [b'userData: ',b'assetBundleName: ',b'assetBundleVariant: ']:
            with self.assertRaises(ValueError):bake.validate_meta(original.replace(marker,marker+b'SYNTHETIC_PASSWORD_OR_ACCOUNT'))
        for change in [original.replace(b'externalObjects: {}',b'externalObjects: {fileID: 1}'),original+b'  arbitrary: /tmp/private\n',original+b'  path: license_xml\n',original.replace(b'textureShape: 2',b'textureShape: 1')]:
            with self.assertRaises(ValueError):bake.validate_meta(change)
    def test_meta_unknown_names_wrong_scope_and_same_mapping_duplicates_rejected(self):
        original=meta(bake.GUIDS['day'])
        changes=[original+b'  SYNTHETIC_PRIVATE_SECRET: 1\n',original+b'  textureShape: 1\n',original+b'  textureShape: 2\n',
                 original.replace(b'    sRGBTexture: 0',b'    sRGBTexture: 0\n    sRGBTexture: 1'),
                 original.replace(b'    enableMipMap: 1',b'    enableMipMap: 1\n    enableMipMap: 0'),
                 original.replace(b'    sRGBTexture: 0',b'    sRGBTexture: 0\n    sRGBTexture: 0'),
                 original.replace(b'    sRGBTexture: 0',b'  sRGBTexture: 0'),
                 original.replace(b'    textureFormat: 17',b'    textureFormat: 17\n    textureFormat: -1'),
                 original.replace(b'  mipmaps:',b'  mipmaps:\n    SYNTHETIC_PRIVATE_SECRET: 0'),
                 original+b'guid: '+bake.GUIDS['day'].encode()+b'\n']
        for changed in changes:
            with self.subTest(change=changes.index(changed)),self.assertRaises(ValueError):bake.validate_meta(changed)
    def test_meta_serialized_versions_across_real_nested_scopes_and_items_allowed(self):
        value=meta(bake.GUIDS['day']).replace(b'  platformSettings:',b'  textureSettings:\n    serializedVersion: 2\n    filterMode: 2\n    mipBias: -100\n  spritePivot: {x: 0.5, y: 0.5}\n  spriteBorder: {x: 0, y: 0, z: 0, w: 0}\n  platformSettings:')
        value=value.replace(b'  userData:',b'  - serializedVersion: 4\n    buildTarget: Android\n    textureFormat: -1\n  spriteSheet:\n    serializedVersion: 2\n    sprites: []\n    indices: \n    nameFileIdTable: {}\n  userData:')
        bake.validate_meta(value)
        with self.assertRaises(ValueError):bake.validate_meta(value.replace(b'buildTarget: Android',b'buildTarget: DefaultTexturePlatform'))
    def test_fixed_files_and_parent_symlink_rejected(self):
        with self.assertRaises(ValueError):bake.read_fixed(self.root,bake.SOURCE,'../unknown',bake.EXR_LIMIT)
        p=self.root/bake.SOURCE/'Day.exr';data=p.read_bytes();p.unlink();target=self.root/'other';target.write_bytes(data);p.symlink_to(target)
        with self.assertRaises(ValueError):self.export()
    def test_oversize_receipt_rejected_and_stale_exports_cleared(self):
        self.export();p=self.root/bake.SOURCE/'reflection-receipt.json';p.write_bytes(b' '*16385)
        with self.assertRaises(ValueError):self.export()
        self.assertEqual(list((bake.visual.outdir(self.root)/'reflections').iterdir()),[])
    def test_no_partial_originals_exported_if_second_texture_fails(self):
        p=self.root/bake.SOURCE/'Night.exr';p.write_bytes(b'INVALID')
        with self.assertRaises(ValueError):self.export()
        out=bake.visual.outdir(self.root)/'reflections';self.assertFalse(out.exists())
    def test_cli_failure_never_prints_exception_or_raw_payload(self):
        script=Path(bake.__file__)
        result=subprocess.run([sys.executable,str(script)],capture_output=True,text=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(result.returncode,1);self.assertEqual(result.stdout,'REFLECTION_BAKE_EVIDENCE_REJECTED\n');self.assertEqual(result.stderr,'')
    def test_workflow_fixed_five_paths_and_existing_twenty_three_frames_kept(self):
        root=Path(__file__).resolve().parents[3];text=(root/bake.visual.WORKFLOW).read_text()
        self.assertEqual(text.count('scripts/reflection_bake_ci.py'),1)
        self.assertIn('scripts/test_reflection_bake_ci.py -v',text)
        expected=[bake.TASK+'/evidence/visual-candidate/reflections/'+name for name in bake.FILES]
        lines=[line.strip() for line in text.splitlines() if '/reflections/' in line]
        self.assertEqual(lines,expected)
        for frame in bake.visual.FRAMES:self.assertIn('/captures/'+frame+'.png',text)
        self.assertEqual(len(bake.visual.FRAMES),23)
        self.assertNotIn('reflection-receipt.json.meta',text)
        self.assertIn("steps.guard.outcome == 'success' && steps.capture.outcome != 'skipped'",text)



class EmptySpriteMetadataCompatibilityTests(unittest.TestCase):
    def test_current_root_owner_rejects_children_below_scalar_root(self):
        valid=(b'fileFormatVersion: 2\nTextureImporter:\n  mipmaps:\n    enableMipMap: 1\n    sRGBTexture: 0\n  textureShape: 2\nguid: '+bake.GUIDS['day'].encode()+b'\n')
        for suffix in (b'  spriteSheet:\n    customData: \n',b'  spriteSheet:\n    spriteCustomMetadata:\n      entries: []\n',b'  serializedVersion: 12\n',b'  bumpmap:\n    convertToNormalMap: 0\n'):
            with self.subTest(suffix=suffix):
                with self.assertRaises(ValueError):bake.validate_meta(valid+suffix)
        scalar_last=valid.replace(b'fileFormatVersion: 2\n',b'')+b'fileFormatVersion: 2\n'
        with self.assertRaises(ValueError):bake.validate_meta(scalar_last+b'  spriteSheet:\n    customData: \n')
    def test_valid_root_order_still_accepts_complete_importer(self):
        valid=(b'fileFormatVersion: 2\nTextureImporter:\n  mipmaps:\n    enableMipMap: 1\n    sRGBTexture: 0\n  textureShape: 2\nguid: '+bake.GUIDS['day'].encode()+b'\n')
        bake.validate_meta(valid)
        bake.validate_meta(valid.replace(b'fileFormatVersion: 2\n',b'')+b'fileFormatVersion: 2\n')
    def sprite_meta(self, suffix):
        return meta(bake.GUIDS['day']).replace(b'  userData:',b'  spriteSheet:\n    serializedVersion: 2\n    sprites: []\n'+suffix+b'  userData:')
    def test_exact_empty_official_sprite_metadata_is_accepted(self):
        for suffix in (b'    customData: \n', b'    spriteCustomMetadata:\n      entries: []\n', b'    customData: \n    spriteCustomMetadata:\n      entries: []\n'):
            with self.subTest(suffix=suffix):bake.validate_meta(self.sprite_meta(suffix))
    def test_empty_metadata_negative_values_structure_duplicates_fail_closed(self):
        bad=(b'    customData: secret\n',b'    customData: {}\n',b'    customData: []\n',b'    customData: \"\"\n',b'    customData: \n    customData: \n',b'  customData: \n',b'      customData: \n',b'    spriteCustomMetadata: {}\n',b'    spriteCustomMetadata: []\n',b'    spriteCustomMetadata: secret\n',b'    spriteCustomMetadata:\n',b'    spriteCustomMetadata:\n      entries: {}\n',b'    spriteCustomMetadata:\n      entries: [secret]\n',b'    spriteCustomMetadata:\n      entries: \n',b'    spriteCustomMetadata:\n      entries: []\n      entries: []\n',b'    spriteCustomMetadata:\n      unexpected: []\n',b'    spriteCustomMetadata:\n      entries: []\n      customData: \n',b'    spriteCustomMetadata:\n      entries: []\n    spriteCustomMetadata:\n      entries: []\n',b'    entries: []\n',b'  spriteCustomMetadata:\n    entries: []\n',b'    spriteCustomMetadata:\n    entries: []\n',b'    spriteCustomMetadata:\n        entries: []\n',b'    spriteCustomMetadata:\n      - entries: []\n',b'    spriteCustomMetadata:\n      entries: []\n    bones: []\n      entries: []\n',b'    spriteCustomMetadata:\n      entries: []\n  userData: \n      entries: []\n',b'    customData: &anchor\n',b'    customData: *anchor\n',b'    customData: !!str\n',b'    spriteCustomMetadata:\n      entries: [ ]\n')
        for suffix in bad:
            with self.subTest(suffix=suffix):
                with self.assertRaises(ValueError):bake.validate_meta(self.sprite_meta(suffix))
    def test_empty_sprite_id_is_limited_by_existing_cubemap_contract(self):
        for value in (b'',b'0123456789abcdef0123456789abcdef'):
            payload=self.sprite_meta(b'    spriteID: '+value+b'\n');bake.validate_meta(payload)
            with self.assertRaises(ValueError):bake.validate_meta(payload.replace(b'textureShape: 2',b'textureShape: 1'))
            with self.assertRaises(ValueError):bake.validate_meta(payload.replace(b'sRGBTexture: 0',b'sRGBTexture: 1'))
        for value in (b'0',b'null',b'{}',b'[]',b'\"\"',b'ABCDEF0123456789ABCDEF0123456789',b'g'*32,b'0'*31,b'0'*33,b'&anchor',b'*anchor'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):bake.validate_meta(self.sprite_meta(b'    spriteID: '+value+b'\n'))
    def test_new_key_diagnostics_are_bounded_and_other_unknowns_redacted(self):
        for field,scope in [('customData','SPRITE_SHEET'),('spriteCustomMetadata','SPRITE_SHEET'),('entries','SPRITE_CUSTOM_METADATA')]:
            suffix=(b'    '+field.encode()+b': secret\n') if field!='entries' else b'    spriteCustomMetadata:\n      entries: [secret]\n'
            trace=bake.ExportTrace();trace.bind(IDENT);trace.stage='META_VALIDATE';trace.fileRole='DAY'
            try:bake.validate_meta(self.sprite_meta(suffix),trace)
            except ValueError as error:d=trace.receipt(error)
            else:self.fail('must reject')
            self.assertEqual((d['metaScope'],d['metaField']),(scope,field));self.assertNotIn('secret',json.dumps(d));self.assertEqual(d['status'],'FAILED')
        trace=bake.ExportTrace();trace.bind(IDENT);trace.stage='META_VALIDATE'
        try:bake.validate_meta(self.sprite_meta(b'    spriteCustomMetadata:\n      arbitrary_secret_key: []\n'),trace)
        except ValueError as error:d=trace.receipt(error)
        self.assertEqual(d['metaField'],'UNKNOWN');self.assertNotIn('arbitrary_secret_key',json.dumps(d))


class ExportDiagnosticTests(unittest.TestCase):
    setUp=ReflectionEvidenceTests.setUp
    save=ReflectionEvidenceTests.save
    def diagnostic(self):return json.loads((bake.visual.outdir(self.root)/bake.DIAGNOSTIC_NAME).read_text())
    def test_official_empty_extensions_export_exact_original_bytes(self):
        payload=meta(bake.GUIDS['day']).replace(b'  userData:',b'  spriteSheet:\n    serializedVersion: 2\n    sprites: []\n    customData: \n    spriteID: \n    spriteCustomMetadata:\n      entries: []\n  userData:')
        self.alter_meta(payload);self.assertEqual(bake.run(self.root),0)
        self.assertEqual((bake.visual.outdir(self.root)/'reflections/Day.exr.meta').read_bytes(),payload)
    def test_nonempty_extension_cannot_export_any_original(self):
        payload=meta(bake.GUIDS['day']).replace(b'  userData:',b'  spriteSheet:\n    customData: SECRET_PAYLOAD\n  userData:')
        self.alter_meta(payload);self.assertEqual(bake.run(self.root),1)
        self.assertFalse((bake.visual.outdir(self.root)/'reflections').exists());d=self.diagnostic()
        self.assertEqual((d['metaScope'],d['metaField']),('SPRITE_SHEET','customData'));self.assertNotIn('SECRET_PAYLOAD',json.dumps(d))
    def test_diagnostic_complete_is_fixed_bound_sidecar(self):
        self.assertEqual(bake.run(self.root),0);d=self.diagnostic()
        self.assertEqual(set(d),{'schemaVersion','scope','sourceCommit','runId','runAttempt','status','stage','fileRole','metaScope','metaField','errorCode','exceptionKind'})
        self.assertEqual((d['status'],d['stage'],d['errorCode']),('COMPLETE','COMPLETE','NONE'))
        self.assertEqual(d['sourceCommit'],IDENT['sourceCommit']);self.assertLess(len(json.dumps(d)),2048)
        for name in bake.FILES:self.assertEqual((bake.visual.outdir(self.root)/'reflections'/name).read_bytes(),(self.root/bake.SOURCE/name).read_bytes())
    def test_diagnostic_receipt_reject_stays_nonzero_and_no_originals(self):
        self.receipt['recipe']='OLD';self.save();self.assertEqual(bake.run(self.root),1);d=self.diagnostic()
        self.assertEqual((d['stage'],d['errorCode']),('RECEIPT_VALIDATE','REFLECTION_COMPLETENESS_REJECTED'))
        self.assertFalse((bake.visual.outdir(self.root)/'reflections/reflection-receipt.json').exists())
    def test_diagnostic_source_digest_stage(self):
        (self.root/bake.TASK/'unity'/bake.RECIPE_SOURCES[0]).write_text('CHANGED');self.assertEqual(bake.run(self.root),1)
        self.assertEqual((self.diagnostic()['stage'],self.diagnostic()['errorCode']),('SOURCE_DIGEST','REFLECTION_SOURCE_INPUT_CHANGED'))
    def alter_meta(self,payload):
        p=self.root/bake.SOURCE/'Day.exr.meta';p.write_bytes(payload);self.receipt['day'].update(metaSha256=bake.digest(payload),metaBytes=len(payload));self.save()
    def test_diagnostic_unknown_meta_key_never_exports_key_or_value(self):
        self.alter_meta(meta(bake.GUIDS['day'])+b'  SECRET_ACCOUNT: PRIVATE_VALUE\n');self.assertEqual(bake.run(self.root),1);d=self.diagnostic()
        self.assertEqual((d['stage'],d['fileRole'],d['metaScope'],d['metaField']),('META_VALIDATE','DAY','TEXTURE_IMPORTER','UNKNOWN'))
        self.assertNotIn('PRIVATE_VALUE',json.dumps(d));self.assertNotIn('SECRET_ACCOUNT',json.dumps(d))
    def test_diagnostic_known_meta_field_only_no_value(self):
        self.alter_meta(meta(bake.GUIDS['day']).replace(b'userData: ',b'userData: SECRET_TOKEN'));self.assertEqual(bake.run(self.root),1);d=self.diagnostic()
        self.assertEqual(d['metaField'],'userData');self.assertNotIn('SECRET_TOKEN',json.dumps(d))
    def test_diagnostic_duplicate_json_code_without_raw_content(self):
        p=self.root/bake.SOURCE/'reflection-receipt.json';p.write_text(p.read_text().replace('"schemaVersion": 1','"schemaVersion": "SECRET_TOKEN", "schemaVersion": 1'));self.assertEqual(bake.run(self.root),1);d=self.diagnostic()
        self.assertEqual(d['errorCode'],'REFLECTION_JSON_DUPLICATE_KEY');self.assertNotIn('SECRET_TOKEN',json.dumps(d))
    def test_diagnostic_unknown_exception_is_enum_only(self):
        with patch.object(bake,'source_digest',side_effect=RuntimeError('SECRET_PATH_OR_LOG')):self.assertEqual(bake.run(self.root),1)
        d=self.diagnostic();self.assertEqual((d['errorCode'],d['exceptionKind']),('UNKNOWN','UNKNOWN'));self.assertNotIn('SECRET_PATH_OR_LOG',json.dumps(d))
    def test_diagnostic_unknown_valueerror_does_not_leak_message(self):
        with patch.object(bake,'source_digest',side_effect=ValueError('SECRET_FREE_TEXT')):self.assertEqual(bake.run(self.root),1)
        d=self.diagnostic();self.assertEqual((d['errorCode'],d['exceptionKind']),('UNKNOWN','VALIDATION'));self.assertNotIn('SECRET_FREE_TEXT',json.dumps(d))
    def test_diagnostic_unbound_identity_no_receipt(self):
        with patch.dict(os.environ,GITHUB_RUN_ATTEMPT='2'):self.assertEqual(bake.run(self.root),1)
        self.assertFalse((bake.visual.outdir(self.root)/bake.DIAGNOSTIC_NAME).exists())
    def test_diagnostic_stale_success_cleared_before_unbound_failure(self):
        self.assertEqual(bake.run(self.root),0)
        with patch.dict(os.environ,GITHUB_SHA='3'*40):self.assertEqual(bake.run(self.root),1)
        self.assertFalse((bake.visual.outdir(self.root)/bake.DIAGNOSTIC_NAME).exists())
    def test_diagnostic_symlink_destination_not_followed(self):
        target=self.root/'private-target';target.write_text('DO_NOT_TOUCH');dest=bake.visual.outdir(self.root)/bake.DIAGNOSTIC_NAME;dest.symlink_to(target)
        self.assertEqual(bake.run(self.root),1);self.assertEqual(target.read_text(),'DO_NOT_TOUCH')
    def test_diagnostic_write_failure_cannot_green_job(self):
        original=Path.write_bytes
        def fail_diag(path,data):
            if path.name==bake.DIAGNOSTIC_NAME:raise OSError('SECRET_DISK_PATH')
            return original(path,data)
        with patch.object(Path,'write_bytes',fail_diag):self.assertEqual(bake.run(self.root),1)
    def test_diagnostic_workflow_adds_one_exact_file_no_glob(self):
        w=(Path(__file__).resolve().parents[3]/'.github/workflows/lottery-visual-candidate.yml').read_text();line='tasks/lottery-shop/evidence/visual-candidate/'+bake.DIAGNOSTIC_NAME
        self.assertEqual(w.count(line),1);self.assertNotIn('reflection-export-*',w)


    def test_diagnostic_original_hash_and_exr_stages_remain_distinct(self):
        p=self.root/bake.SOURCE/'Day.exr';p.write_bytes(b'BAD_HEADER'*20);self.assertEqual(bake.run(self.root),1);self.assertEqual(self.diagnostic()['stage'],'ORIGINAL_HASH')
        self.receipt['day'].update(sha256=bake.digest(p.read_bytes()),bytes=p.stat().st_size);self.save();self.assertEqual(bake.run(self.root),1)
        self.assertEqual((self.diagnostic()['stage'],self.diagnostic()['errorCode']),('EXR_HEADER','REFLECTION_EXR_REJECTED'))
    def test_diagnostic_invalid_meta_syntax_has_no_stale_prior_field(self):
        self.alter_meta(meta(bake.GUIDS['day'])+b'SECRET_UNPARSEABLE_LINE\n');self.assertEqual(bake.run(self.root),1);d=self.diagnostic()
        self.assertEqual((d['metaScope'],d['metaField']),('UNKNOWN','UNKNOWN'));self.assertNotIn('SECRET_UNPARSEABLE_LINE',json.dumps(d))
    def test_diagnostic_unknown_utf8_has_no_prior_meta_context(self):
        self.alter_meta(b'\xff');self.assertEqual(bake.run(self.root),1);d=self.diagnostic()
        self.assertEqual((d['stage'],d['metaScope'],d['metaField']),('META_VALIDATE','NONE','NONE'))
    def test_diagnostic_bound_identity_rejects_free_text(self):
        bad=dict(IDENT,runId='SECRET_ID');bake.visual.write(bake.visual.outdir(self.root)/'source-receipt.json',bad)
        with patch.dict(os.environ,GITHUB_RUN_ID='SECRET_ID'):self.assertEqual(bake.run(self.root),1)
        self.assertFalse((bake.visual.outdir(self.root)/bake.DIAGNOSTIC_NAME).exists())
    def test_diagnostic_failure_write_does_not_mask_original_failure(self):
        self.receipt['recipe']='OLD';self.save();original=Path.write_bytes
        def fail_diag(path,data):
            if path.name==bake.DIAGNOSTIC_NAME:raise OSError('SECRET_PATH')
            return original(path,data)
        with patch.object(Path,'write_bytes',fail_diag):self.assertEqual(bake.run(self.root),1)
        self.assertFalse((bake.visual.outdir(self.root)/'reflections/reflection-receipt.json').exists())

if __name__=='__main__':unittest.main()
