"""Offline positive/negative fixtures. Temporary synthetic pixels are never native evidence."""
import copy
import hashlib
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
import environment_diffuse_comparison_evidence as comparison

TASK = Path(__file__).resolve().parents[1]


def valid():
    materials = []
    for name in ('Surface-Sand', 'Surface-Dune'):
        materials.append(dict(name=name, shader='Universal Render Pipeline/Lit', baseMapAsset=comparison.ORIGINAL,
                              normalMapAsset=comparison.ART+'sand_03_nor_gl_1k.jpg', normalScale=.035, smoothness=.04,
                              metallic=0, baseScale={'x': 1, 'y': 1}, baseOffset={'x': 0, 'y': 0},
                              normalUvScale={'x': 1, 'y': 1}, normalUvOffset={'x': 0, 'y': 0},
                              baseColor={'r': 1.75, 'g': 1.52, 'b': 1.16, 'a': 1}, keywords=['_NORMALMAP'], normalKeyword=True))
    images = []
    for variant in comparison.VARIANTS:
        for view, (fov, at, look) in comparison.CAMERAS.items():
            actual = copy.deepcopy(materials)
            for material in actual:
                material['baseMapAsset'] = comparison.ORIGINAL if variant == 'original' else comparison.CORRECTED
            images.append(dict(file=f'Scrapyard-{view}-{variant}.png', view=view, variant=variant, sceneHash='a'*32,
                               width=1440, height=900, fieldOfView=fov, minimum=.1, maximum=.8, normalEnabled=True,
                               materialParametersPreserved=True, warmupRenderCount=1, cameraPosition=at.copy(),
                               cameraTarget=look.copy(), actualMaterials=actual))
    assets = [dict(assetPath=path, sha256=letter*64, width=1024, height=1024)
              for path, letter in zip(comparison.REQUIRED_ASSETS, 'ab')]
    return dict(status=comparison.STATUS, graphicsDeviceType='OpenGLCore', graphicsDeviceName='llvmpipe (LLVM fixture)',
                savedSceneAndMaterialBytesPreserved=True, captureBuffersReleased=True, terrainRenderers=3,
                protectedSavedAssetCount=6, warmupRenderCount=1, diffuseAssets=assets, originalMaterials=materials, images=images)


class ReportTests(unittest.TestCase):
    def test_valid_report(self):
        self.assertEqual(comparison.validate_report(valid())['status'], comparison.STATUS)

    def test_exact_four_set(self):
        self.assertEqual(comparison.IMAGES, {f'Scrapyard-{view}-{variant}.png' for view in ('overview', 'ground')
                                           for variant in ('original', 'illumination-corrected')})

    def test_per_image_actual_map_is_distinct_by_variant(self):
        report = valid()
        for record in report['images']:
            expected = comparison.ORIGINAL if record['variant'] == 'original' else comparison.CORRECTED
            self.assertTrue(all(material['baseMapAsset'] == expected for material in record['actualMaterials']))
            self.assertTrue(all(material['normalKeyword'] and material['normalScale'] == .035 for material in record['actualMaterials']))


def add_mutation(name, mutate):
    def test(self):
        value = valid(); mutate(value)
        with self.assertRaises((ValueError, TypeError, KeyError)):
            comparison.validate_report(value)
    setattr(ReportTests, 'test_reject_'+name, test)


for name, mutate in {
    'extra_report_field': lambda d: d.update(secret='not-exported'),
    'wrong_scope': lambda d: d.update(status='ACCEPTED'),
    'fake_device': lambda d: d.update(graphicsDeviceType='Null'),
    'wrong_gpu': lambda d: d.update(graphicsDeviceName='fake'),
    'lost_material_preservation': lambda d: d.update(savedSceneAndMaterialBytesPreserved=False),
    'lost_buffers': lambda d: d.update(captureBuffersReleased=False),
    'renderer_count': lambda d: d.update(terrainRenderers=4),
    'bool_renderer_count': lambda d: d.update(terrainRenderers=True),
    'saved_scene_count': lambda d: d.update(protectedSavedAssetCount=5),
    'zero_warmup': lambda d: d.update(warmupRenderCount=0),
    'bool_warmup': lambda d: d.update(warmupRenderCount=True),
    'missing_diffuse_asset': lambda d: d['diffuseAssets'].pop(),
    'duplicate_diffuse_asset': lambda d: d['diffuseAssets'].__setitem__(1, copy.deepcopy(d['diffuseAssets'][0])),
    'same_diffuse_hash': lambda d: d['diffuseAssets'][1].update(sha256='a'*64),
    'bad_diffuse_hash': lambda d: d['diffuseAssets'][1].update(sha256='not-a-hash'),
    'diffuse_path_traversal': lambda d: d['diffuseAssets'][1].update(assetPath='../arbitrary.png'),
    'diffuse_size': lambda d: d['diffuseAssets'][1].update(width=512),
    'diffuse_extra_field': lambda d: d['diffuseAssets'][1].update(secret='no'),
    'extra_material': lambda d: d['originalMaterials'].append(d['originalMaterials'][0]),
    'duplicate_material': lambda d: d['originalMaterials'][1].update(name='Surface-Sand'),
    'wrong_shader': lambda d: d['originalMaterials'][0].update(shader='Unlit/Color'),
    'wrong_original_diffuse': lambda d: d['originalMaterials'][0].update(baseMapAsset=comparison.CORRECTED),
    'wrong_normal': lambda d: d['originalMaterials'][0].update(normalMapAsset='Assets/unverified.jpg'),
    'normal_strength': lambda d: d['originalMaterials'][0].update(normalScale=1),
    'normal_nan': lambda d: d['originalMaterials'][0].update(normalScale=float('nan')),
    'smoothness': lambda d: d['originalMaterials'][0].update(smoothness=.5),
    'metallic': lambda d: d['originalMaterials'][0].update(metallic=1),
    'texture_scale': lambda d: d['originalMaterials'][0]['baseScale'].update(x=2),
    'texture_offset': lambda d: d['originalMaterials'][0]['baseOffset'].update(y=1),
    'normal_uv_scale': lambda d: d['originalMaterials'][0]['normalUvScale'].update(x=2),
    'normal_uv_offset': lambda d: d['originalMaterials'][0]['normalUvOffset'].update(y=1),
    'base_tint': lambda d: d['originalMaterials'][0]['baseColor'].update(r=1),
    'base_tint_infinity': lambda d: d['originalMaterials'][0]['baseColor'].update(r=float('inf')),
    'material_extra': lambda d: d['originalMaterials'][0].update(arbitrary='no'),
    'missing_normal_keyword': lambda d: d['originalMaterials'][0].update(keywords=[]),
    'normal_keyword_false': lambda d: d['originalMaterials'][0].update(normalKeyword=False),
    'duplicate_keyword': lambda d: d['originalMaterials'][0].update(keywords=['_NORMALMAP', '_NORMALMAP']),
    'invalid_keyword': lambda d: d['originalMaterials'][0].update(keywords=['_NORMALMAP', 'arbitrary script']),
    'keyword_mismatch_originals': lambda d: d['originalMaterials'][0].update(keywords=['_EMISSION', '_NORMALMAP']),
    'missing_image': lambda d: d['images'].pop(),
    'extra_image': lambda d: d['images'].append(d['images'][0]),
    'duplicate_image': lambda d: d['images'].__setitem__(1, copy.deepcopy(d['images'][0])),
    'old_probe_variant': lambda d: d['images'][0].update(variant='normal-off'),
    'unknown_view': lambda d: d['images'][0].update(view='cabin'),
    'file_traversal': lambda d: d['images'][0].update(file='../other.png'),
    'absolute_file': lambda d: d['images'][0].update(file='/tmp/other.png'),
    'normal_disabled': lambda d: d['images'][0].update(normalEnabled=False),
    'normal_bool_type': lambda d: d['images'][0].update(normalEnabled=1),
    'parameters_changed': lambda d: d['images'][0].update(materialParametersPreserved=False),
    'image_zero_warmup': lambda d: d['images'][0].update(warmupRenderCount=0),
    'image_two_warmups': lambda d: d['images'][0].update(warmupRenderCount=2),
    'image_bool_warmup': lambda d: d['images'][0].update(warmupRenderCount=True),
    'wrong_width': lambda d: d['images'][0].update(width=1280),
    'wrong_height_type': lambda d: d['images'][0].update(height=900.),
    'wrong_fov': lambda d: d['images'][0].update(fieldOfView=55),
    'wrong_position': lambda d: d['images'][0]['cameraPosition'].update(y=40),
    'wrong_target': lambda d: d['images'][0]['cameraTarget'].update(z=29),
    'extra_vector_axis': lambda d: d['images'][0]['cameraTarget'].update(w=1),
    'nan_fov': lambda d: d['images'][0].update(fieldOfView=float('nan')),
    'nan_pixel': lambda d: d['images'][0].update(minimum=float('nan')),
    'infinite_pixel': lambda d: d['images'][0].update(maximum=float('inf')),
    'bool_pixel': lambda d: d['images'][0].update(minimum=False),
    'blank_pixel_range': lambda d: d['images'][0].update(minimum=.8),
    'different_scene_hash': lambda d: d['images'][0].update(sceneHash='b'*32),
    'wrong_scene_hash': lambda d: d['images'][0].update(sceneHash='none'),
    'record_extra': lambda d: d['images'][0].update(command='no'),
    'actual_materials_missing': lambda d: d['images'][0].update(actualMaterials=[]),
    'actual_original_has_corrected_map': lambda d: d['images'][0]['actualMaterials'][0].update(baseMapAsset=comparison.CORRECTED),
    'corrected_variant_retains_original_map': lambda d: d['images'][2]['actualMaterials'][0].update(baseMapAsset=comparison.ORIGINAL),
    'actual_normal_removed': lambda d: d['images'][2]['actualMaterials'][0].update(normalMapAsset=''),
    'actual_normal_reduced': lambda d: d['images'][2]['actualMaterials'][0].update(normalScale=0),
    'actual_keyword_changed': lambda d: d['images'][2]['actualMaterials'][0].update(keywords=['_EMISSION', '_NORMALMAP']),
    'actual_tint_drift': lambda d: d['images'][2]['actualMaterials'][0]['baseColor'].update(r=1.7500001),
}.items():
    add_mutation(name, mutate)


class FixtureBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.directory = self.root/comparison.CAPTURE; self.directory.mkdir(parents=True)
        for i, name in enumerate(sorted(comparison.IMAGES)):
            image = Image.new('RGB', (1440, 900), (35+i*5, 50, 70))
            ImageDraw.Draw(image).rectangle((200+i*3, 100, 1100, 700), fill=(185, 160-i*5, 110))
            image.save(self.directory/name)
        for i, name in enumerate(comparison.REQUIRED_ASSETS):
            path = self.root/name; path.parent.mkdir(parents=True, exist_ok=True)
            image = Image.new('RGB', (1024, 1024), (100+i*10, 85, 70))
            ImageDraw.Draw(image).rectangle((200, 100, 800, 700), fill=(145-i*10, 130, 110)); image.save(path)
        self.report = valid(); self.report['diffuseAssets'] = comparison.inspect_assets(self.root)
        self.save_report()
        (self.root/'JourneyEvidence/candidate-layout.json').write_text('{"passed":true}')
        for region in (1, 2, 3):
            zones = ['driving-corridor', 'vehicle-spawn', 'dismount', 'cabin-workbench']
            if region in (1, 2): zones.append('salvage-access')
            if region in (2, 3): zones.append('power-access')
            (self.root/f'JourneyEvidence/clearance-region-{region}.json').write_text(json.dumps(
                dict(region=region, passed=True, checkedZones=zones, distantMeshes=4)))

    def save_report(self):
        (self.directory/'comparison-report.json').write_text(json.dumps(self.report))

    def reject_capture(self):
        with self.assertRaises((ValueError, OSError)):
            comparison.inspect_capture(self.root)


class CaptureTests(FixtureBase):
    def test_valid_capture(self):
        report, clearance = comparison.inspect_capture(self.root)
        self.assertEqual(len(report['images']), 4); self.assertEqual([x['region'] for x in clearance], [1, 2, 3])

    def test_missing_png(self):
        (self.directory/next(iter(comparison.IMAGES))).unlink(); self.reject_capture()

    def test_extra_capture_file(self):
        (self.directory/'raw.log').write_text('no'); self.reject_capture()

    def test_old_eight_probe_file(self):
        (self.directory/'Scrapyard-ground-normal-off.png').write_bytes(b'no'); self.reject_capture()

    def test_bad_png(self):
        (self.directory/next(iter(comparison.IMAGES))).write_bytes(b'not png'); self.reject_capture()

    def test_wrong_png_dimensions(self):
        Image.new('RGB', (10, 10)).save(self.directory/next(iter(comparison.IMAGES))); self.reject_capture()

    def test_blank_png(self):
        Image.new('RGB', (1440, 900), (0, 0, 0)).save(self.directory/next(iter(comparison.IMAGES))); self.reject_capture()

    def test_uniform_bright_png(self):
        Image.new('RGB', (1440, 900), (200, 200, 200)).save(self.directory/next(iter(comparison.IMAGES))); self.reject_capture()

    def test_duplicate_png_pixels(self):
        names = sorted(comparison.IMAGES)
        with Image.open(self.directory/names[0]) as image:
            image.save(self.directory/names[1], compress_level=1)
        self.reject_capture()

    def test_linked_png(self):
        path = self.directory/next(iter(comparison.IMAGES)); target = self.root/'linked.png'; path.rename(target); path.symlink_to(target)
        self.reject_capture()

    def test_linked_directory(self):
        target = self.root/'elsewhere'; self.directory.rename(target); self.directory.symlink_to(target, target_is_directory=True)
        self.reject_capture()

    def test_duplicate_json_key(self):
        path = self.directory/'comparison-report.json'; path.write_text('{"status":"a","status":"b"}'); self.reject_capture()

    def test_layout_failed(self):
        (self.root/'JourneyEvidence/candidate-layout.json').write_text('{"passed":false}'); self.reject_capture()

    def test_each_clearance_required(self):
        for region in (1, 2, 3):
            with self.subTest(region=region):
                path = self.root/f'JourneyEvidence/clearance-region-{region}.json'; original = path.read_bytes(); path.unlink()
                self.reject_capture(); path.write_bytes(original)

    def test_clearance_failed(self):
        path = self.root/'JourneyEvidence/clearance-region-2.json'; data = json.loads(path.read_text()); data['passed'] = False
        path.write_text(json.dumps(data)); self.reject_capture()

    def test_missing_corrected_asset(self):
        (self.root/comparison.CORRECTED).unlink(); self.reject_capture()

    def test_linked_corrected_asset(self):
        path = self.root/comparison.CORRECTED; target = self.root/'linked-asset.png'; path.rename(target); path.symlink_to(target)
        self.reject_capture()

    def test_wrong_actual_asset_hash(self):
        self.report['diffuseAssets'][1]['sha256'] = 'f'*64; self.save_report(); self.reject_capture()

    def test_wrong_actual_asset_dimensions(self):
        Image.new('RGB', (512, 512)).save(self.root/comparison.CORRECTED); self.reject_capture()

    def test_wrong_actual_asset_format(self):
        Image.new('RGB', (1024, 1024)).save(self.root/comparison.CORRECTED, format='JPEG'); self.reject_capture()

    def test_reencoded_identical_asset_pixels(self):
        with Image.open(self.root/comparison.ORIGINAL) as image:
            image.convert('RGB').save(self.root/comparison.CORRECTED)
        with self.assertRaises(ValueError): comparison.inspect_assets(self.root)


class PackageTests(FixtureBase):
    def setup_package(self, stack, attempt='1'):
        snapshot = self.root/'before.json'; snapshot.write_text('{"tracked":"abc"}')
        out = self.root/'sanitized'
        identity = dict(repository='yangerstar1/task-workbench', commit='b'*40, runId='1', runAttempt=attempt,
                        editorVersion='6000.3.19f1', sourceStateSha256='c'*64)
        for target, name, value in ((comparison, 'OUT', out), (comparison.source, 'TASK', self.root),
                                    (comparison.source, 'PROJECT', self.root), (comparison.legacy, 'SNAPSHOT', snapshot)):
            stack.enter_context(patch.object(target, name, value))
        stack.enter_context(patch.object(comparison.legacy, 'tracked_snapshot', return_value={'tracked': 'abc'}))
        stack.enter_context(patch.object(comparison, 'inspect_native', return_value='d'*64))
        stack.enter_context(patch.object(comparison.source, 'identity', return_value=identity))
        return out

    def test_package_outputs_only_four_png_receipt_hashes(self):
        with ExitStack() as stack:
            out = self.setup_package(stack); comparison.package()
        self.assertEqual({path.name for path in out.iterdir()}, comparison.IMAGES | {'receipt.json', 'SHA256SUMS.json'})
        receipt = json.loads((out/'receipt.json').read_text())
        self.assertEqual(receipt['scope'], comparison.STATUS); self.assertEqual(receipt['visualAcceptance'], 'NOT_ACCEPTED')
        self.assertEqual(receipt['nativeRenderTest'], comparison.RENDER_TEST)
        hashes = json.loads((out/'SHA256SUMS.json').read_text()); self.assertEqual(len(hashes), 5)
        for row in hashes:
            self.assertEqual(hashlib.sha256((out/row['path']).read_bytes()).hexdigest(), row['sha256'])
            self.assertEqual((out/row['path']).stat().st_size, row['size'])

    def test_changed_tracked_source_stops_before_output(self):
        with ExitStack() as stack:
            out = self.setup_package(stack)
            stack.enter_context(patch.object(comparison.legacy, 'tracked_snapshot', return_value={'tracked': 'changed'}))
            with self.assertRaises(ValueError): comparison.package()
            self.assertFalse(out.exists())

    def test_stale_output_rejected(self):
        with ExitStack() as stack:
            out = self.setup_package(stack); out.mkdir()
            with self.assertRaises(ValueError): comparison.package()

    def test_replay_rejected(self):
        with ExitStack() as stack:
            out = self.setup_package(stack, attempt='2')
            with self.assertRaises(ValueError): comparison.package()
            self.assertFalse(out.exists())

    def test_png_copy_save_failure_does_not_publish_partial(self):
        with ExitStack() as stack:
            out = self.setup_package(stack)
            stack.enter_context(patch.object(comparison.shutil, 'copyfile', side_effect=OSError('fixture disk full')))
            with self.assertRaises(OSError): comparison.package()
            self.assertFalse(out.exists()); self.assertFalse(list(out.parent.glob('.diffuse-comparison-*')))

    def test_corrupt_png_copy_is_not_published(self):
        with ExitStack() as stack:
            out = self.setup_package(stack)
            stack.enter_context(patch.object(comparison.shutil, 'copyfile', side_effect=lambda src, dst: dst.write_bytes(b'corrupt')))
            with self.assertRaises(ValueError): comparison.package()
            self.assertFalse(out.exists())

    def test_receipt_save_failure_does_not_publish_partial(self):
        with ExitStack() as stack:
            out = self.setup_package(stack)
            stack.enter_context(patch.object(Path, 'write_text', side_effect=OSError('fixture disk full')))
            with self.assertRaises(OSError): comparison.package()
            self.assertFalse(out.exists()); self.assertFalse(list(out.parent.glob('.diffuse-comparison-*')))

    def test_hash_manifest_save_failure_does_not_publish_partial(self):
        original = Path.write_text
        def fail_manifest(path, text, *args, **kwargs):
            if path.name == 'SHA256SUMS.json': raise OSError('fixture manifest disk full')
            return original(path, text, *args, **kwargs)
        with ExitStack() as stack:
            out = self.setup_package(stack)
            stack.enter_context(patch.object(Path, 'write_text', fail_manifest))
            with self.assertRaises(OSError): comparison.package()
            self.assertFalse(out.exists())

    def test_before_checks_assets_then_unchanged_source_gate(self):
        with patch.object(comparison.source, 'PROJECT', self.root), patch.object(comparison.legacy, 'before') as before:
            comparison.before(); before.assert_called_once_with()

    def test_before_missing_asset_never_calls_source_gate(self):
        (self.root/comparison.CORRECTED).unlink()
        with patch.object(comparison.source, 'PROJECT', self.root), patch.object(comparison.legacy, 'before') as before:
            with self.assertRaises(ValueError): comparison.before()
            before.assert_not_called()


class NativeTests(unittest.TestCase):
    def check(self, text, passed=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'results.xml').write_text(text)
            if passed: self.assertEqual(len(comparison.inspect_native(root)), 64)
            else:
                with self.assertRaises(ValueError): comparison.inspect_native(root)

    def xml(self, name=comparison.RENDER_TEST, result='Passed', count=1):
        return '<test-run result="'+result+'">'+('<test-case fullname="'+name+'" result="'+result+'"/>')*count+'</test-run>'

    def test_native_exact_case(self): self.check(self.xml(), True)
    def test_native_old_twenty_case(self): self.check(self.xml(name=comparison.legacy.RENDER_TEST))
    def test_native_old_eight_case(self): self.check(self.xml(name='DesertRV.Tests.JourneyTerrainProbeTests.AuthorAndCaptureEightChannelAblations'))
    def test_native_failed(self): self.check(self.xml(result='Failed'))
    def test_native_extra_case(self): self.check(self.xml(count=2))
    def test_native_no_case(self): self.check(self.xml(count=0))
    def test_native_nested_failure(self):
        self.check(self.xml().replace('</test-run>', '<test-suite result="Failed"/></test-run>'))
    def test_native_failure_element(self):
        self.check(self.xml().replace('</test-run>', '<failure/></test-run>'))
    def test_native_missing_report(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError): comparison.inspect_native(Path(temp))
    def test_native_two_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'a.xml').write_text(self.xml()); (root/'b.xml').write_text(self.xml())
            with self.assertRaises(ValueError): comparison.inspect_native(root)
    def test_native_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); target = root/'data.txt'; target.write_text(self.xml()); (root/'a.xml').symlink_to(target)
            with self.assertRaises(ValueError): comparison.inspect_native(root)


class ImplementationTests(unittest.TestCase):
    def test_original_production_and_eight_view_gates_byte_exact(self):
        expected = {'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.EnvironmentPolish.cs': 'b829eda4869721b7956cb279b53e0a6b7e1194ef91880c80e2d712110a8366d9', 'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.EnvironmentPolishCapture.cs': 'fa6cbe1f1252801ec1b0f62b864104d715f781dc01567b50ec82c9a0b30f097e', 'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.TerrainProbe.cs': 'e0c8643bd5a399095aad86e49b9929d04e9737385f373e04a35e8208e81b21d1', 'scripts/environment_evidence.py': 'c8039deefc987c742b3a558f783cf8ea49fd642760c7bf71d5fb6381aeab4b6d', 'scripts/environment_v4_evidence.py': '7f8bd56d466260bbf57653a76f3845deea81d9f96d03a093366376dcfeba6548', 'scripts/environment_terrain_probe_evidence.py': 'bffbd79990a82a9d2aed171892eafb5dda97b8ab186714c00dbbac126e5abf12', 'scripts/test_environment_terrain_probe_evidence.py': '419e70c01df1b0543aad50dbfafc915a263faaf2583d07c43b3da4c8f043decc', 'unity/Assets/DesertRV/Tests/EditorTerrainProbe/JourneyTerrainProbeTests.cs': 'cd8cf81e2af6b148947582db282d2292510d6447ea477b5fc65793e32fc04cc9', 'unity/Assets/DesertRV/Tests/EditorTerrainProbe/DesertRV.EditorTerrainProbeTests.asmdef': '50932f8f3a39fd70c4d358278dec5f222d7ee4190fa75977c58fe05b5e481ff4'}
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((TASK/name).read_bytes()).hexdigest(), digest, name)

    def test_comparison_source_fixed_two_by_two_and_only_basemap_mutation(self):
        text = (TASK/'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.DiffuseComparison.cs').read_text()
        for required in ('new[]{"original","illumination-corrected"}', 'new[]{"overview","ground"}', 'records.Count!=4',
                         'new Material(original)', 'm.SetTexture("_BaseMap",diffuse)', 'saved.Count!=6',
                         'warmup<1', 'savedSceneAndMaterialBytesPreserved=preserved', 'VerifyProtectedFiles(protectedFiles)',
                         'SequenceEqual(File.ReadAllBytes(item.Key))', 'AssertDiffuseComparisonMaterial(terrain[i].sharedMaterial,originals[i],diffuse)',
                         'shader.GetPropertyCount()', 'case ShaderPropertyType.Texture:', 'GetTextureScale(property)',
                         'GetTextureOffset(property)', 'GetShaderPassEnabled', 'shaderKeywords', 'ReadDiffuseComparisonMaterial',
                         'File.ReadAllText(reportPath)!=report', 'encoded.SequenceEqual(File.ReadAllBytes(destination))',
                         'target.Release()', 'RestoreSceneSetup(setup)', comparison.CORRECTED):
            self.assertIn(required, text)
        self.assertEqual(text.count('RenderPipeline.SubmitRenderRequest(camera,request)'), 2)
        for forbidden in ('SaveAssets', 'CreateAsset', 'SetAtmosphere(', 'light.intensity', 'RenderSettings.', 'SetTextureScale(',
                          'SetTextureOffset(', 'DisableKeyword(', 'EnableKeyword(', 'SetFloat(', 'SetColor(', 'meanDiffuse',
                          'normal-off', 'diffuse-flat', 'SaveScene('):
            self.assertNotIn(forbidden, text)

    def test_diffuse_assets_load_after_final_scene_transition(self):
        text = (TASK/'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.DiffuseComparison.cs').read_text()
        final_open = text.rindex('EditorSceneManager.OpenScene(')
        self.assertLess(text.index('AuthorCandidateScenes();'), final_open)
        for variable in ('originalDiffuse', 'correctedDiffuse'):
            load = text.index(variable+'=AssetDatabase.LoadAssetAtPath<Texture2D>')
            self.assertGreater(load, final_open)
            self.assertLess(load, text.index('new Material(original)'))
            self.assertNotIn(variable+'.hideFlags', text)
        self.assertGreater(text.index('diffuseAssets=new[]{originalDiffuse,correctedDiffuse}'), final_open)

    def test_independent_exact_single_native_case(self):
        root = TASK/'unity/Assets/DesertRV/Tests/EditorDiffuseComparison'
        text = (root/'JourneyDiffuseComparisonTests.cs').read_text()
        self.assertEqual(text.count('[Test,'), 1)
        self.assertIn('Timeout(600000)', text); self.assertIn('AuthorAndCaptureFourDiffuseComparisons', text)
        self.assertIn('"AuthorAndCaptureDiffuseComparison"', text)
        asm = json.loads((root/'DesertRV.EditorDiffuseComparisonTests.asmdef').read_text())
        self.assertEqual(asm['name'], 'DesertRV.EditorDiffuseComparisonTests'); self.assertEqual(asm['includePlatforms'], ['Editor'])
        self.assertFalse(asm['autoReferenced']); self.assertEqual(asm['optionalUnityReferences'], ['TestAssemblies'])

    def test_new_unity_asset_guids_unique(self):
        paths = [TASK/'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.DiffuseComparison.cs.meta',
                 TASK/'unity/Assets/DesertRV/Tests/EditorDiffuseComparison.meta']
        paths += list((TASK/'unity/Assets/DesertRV/Tests/EditorDiffuseComparison').glob('*.meta'))
        import re
        guids = [re.search(r'^guid: ([0-9a-f]{32})$', path.read_text(), re.M).group(1) for path in paths]
        all_guids = []
        for path in (TASK/'unity/Assets').rglob('*.meta'):
            match = re.search(r'^guid: ([0-9a-f]{32})$', path.read_text(), re.M)
            if match: all_guids.append(match.group(1))
        self.assertEqual(len(paths), 4)
        for guid in guids: self.assertEqual(all_guids.count(guid), 1)


if __name__ == '__main__':
    unittest.main()
