"""Four real diffuse-comparison images only. Existing twenty/eight-view gates are unchanged."""
import argparse
import hashlib
import json
import math
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
import verify_evidence as source
import environment_evidence as legacy

STATUS = 'DIAGNOSTIC_DIFFUSE_COMPARISON_NOT_ART_ACCEPTANCE'
VARIANTS = ('original', 'illumination-corrected')
CAMERAS = {'overview': (54, {'x': 31, 'y': 39, 'z': -17}, {'x': 0, 'y': 0, 'z': 28}),
           'ground': (58, {'x': -5, 'y': 1.65, 'z': -7}, {'x': 2, 'y': 2.2, 'z': 25})}
IMAGES = {f'Scrapyard-{view}-{variant}.png' for view in CAMERAS for variant in VARIANTS}
RENDER_TEST = 'DesertRV.Tests.JourneyDiffuseComparisonTests.AuthorAndCaptureFourDiffuseComparisons'
CAPTURE = 'JourneyEvidence/diffuse-comparison'
OUT = source.TASK / 'evidence/diffuse-comparison'
ART = 'Assets/DesertRV/Art/EnvironmentV4/'
ORIGINAL = ART + 'sand_03_diff_1k.jpg'
CORRECTED = 'Assets/DesertRV/Art/TerrainDiffuseCorrection/sand_03_diff_illumination_corrected_1k.png'
REQUIRED_ASSETS = (ORIGINAL, CORRECTED)
GENERATED = 'Assets/DesertRV/Scenes/Journey/EnvironmentV4/'
TERRAIN_BINDINGS = [dict(objectName='EnvironmentV4 '+role, scenePath='Assets/DesertRV/Scenes/Journey/Scrapyard.unity',
                         meshAsset=GENERATED+'R2-'+role+'.asset', materialAsset=GENERATED+'Surface-'+material+'.mat')
                    for role, material in (('Ground-Sand', 'Sand'), ('ReliefEast-Dune', 'Dune'), ('ReliefWest-Dune', 'Dune'))]
ASSET_KEYS = {'assetPath', 'sha256', 'width', 'height'}
REPORT_KEYS = {'status', 'graphicsDeviceType', 'graphicsDeviceName', 'savedSceneAndMaterialBytesPreserved',
               'captureBuffersReleased', 'terrainRenderers', 'protectedSavedAssetCount', 'warmupRenderCount',
               'diffuseAssets', 'terrainBindings', 'originalMaterials', 'images'}
IMAGE_KEYS = {'file', 'view', 'variant', 'sceneHash', 'width', 'height', 'fieldOfView', 'minimum', 'maximum',
              'normalEnabled', 'materialParametersPreserved', 'warmupRenderCount', 'cameraPosition', 'cameraTarget', 'actualMaterials'}
MATERIAL_KEYS = {'name', 'shader', 'baseMapAsset', 'normalMapAsset', 'normalScale', 'smoothness', 'metallic',
                 'baseScale', 'baseOffset', 'normalUvScale', 'normalUvOffset', 'baseColor', 'keywords', 'normalKeyword'}
require = source.require


def close(a, b):
    return type(a) in (float, int) and math.isfinite(a) and abs(a-b) < .00001


def vector(value, expected):
    return isinstance(value, dict) and set(value) == set(expected) and all(close(value[k], v) for k, v in expected.items())


def unlinked_directory(path):
    require(path.is_dir() and not path.is_symlink() and not any(p.is_symlink() for p in path.parents), 'Missing or linked evidence directory')


def inspect_native(directory):
    unlinked_directory(directory)
    paths = list(directory.rglob('*.xml'))
    require(0 < len(paths) <= 20, 'Native XML count')
    for path in paths:
        require(source.safe(path).stat().st_size <= 10*1024**2, 'Native XML size')
    roots = [(path, ET.parse(path).getroot()) for path in paths]
    reports = [(path, root) for path, root in roots if root.tag == 'test-run']
    require(len(reports) == 1, 'One diffuse comparison native report required')
    path, root = reports[0]
    cases = list(root.iter('test-case'))
    require(root.get('result') == 'Passed' and len(cases) == 1, 'Wrong native case count or failed run')
    require(cases[0].get('fullname') == RENDER_TEST and cases[0].get('result') == 'Passed', 'Wrong diffuse comparison native test')
    require(not list(root.iter('failure')) and not list(root.iter('error')) and
            all(suite.get('result') == 'Passed' for suite in root.iter('test-suite')), 'Native nested failure')
    return source.sha(path)


def validate_materials(materials, diffuse):
    require(isinstance(materials, list) and len(materials) == 2, 'Material count')
    names = set()
    for material in materials:
        require(isinstance(material, dict) and set(material) == MATERIAL_KEYS, 'Material fields')
        require(material['name'] in ('Surface-Sand', 'Surface-Dune') and material['name'] not in names, 'Material identity')
        names.add(material['name'])
        require(material['shader'] == 'Universal Render Pipeline/Lit', 'Production Lit required')
        require(material['baseMapAsset'] == diffuse and material['normalMapAsset'] == ART+'sand_03_nor_gl_1k.jpg', 'Actual diffuse/normal texture identity')
        require(close(material['normalScale'], .035) and close(material['smoothness'], .04) and close(material['metallic'], 0), 'Production BRDF identity')
        require(vector(material['baseScale'], {'x': 1, 'y': 1}) and vector(material['baseOffset'], {'x': 0, 'y': 0}) and
                vector(material['normalUvScale'], {'x': 1, 'y': 1}) and vector(material['normalUvOffset'], {'x': 0, 'y': 0}), 'Production UV transforms')
        require(vector(material['baseColor'], {'r': 1.75, 'g': 1.52, 'b': 1.16, 'a': 1}), 'Production base tint')
        keywords = material['keywords']
        require(material['normalKeyword'] is True and isinstance(keywords, list) and 0 < len(keywords) <= 64 and
                all(isinstance(k, str) and re.fullmatch('[A-Z0-9_]{1,80}', k) for k in keywords) and
                keywords == sorted(set(keywords)) and '_NORMALMAP' in keywords, 'Actual normal keyword and keyword set')
    return {material['name']: material for material in materials}


def validate_report(report):
    require(isinstance(report, dict) and set(report) == REPORT_KEYS, 'Comparison report fields')
    require(report['status'] == STATUS and report['graphicsDeviceType'] == 'OpenGLCore', 'Comparison scope/device')
    device = report['graphicsDeviceName']
    require(isinstance(device, str) and len(device) < 256 and 'llvmpipe' in device.lower(), 'Expected actual Mesa device')
    require(report['savedSceneAndMaterialBytesPreserved'] is True and report['captureBuffersReleased'] is True, 'Comparison preservation/cleanup')
    for key, count in (('terrainRenderers', 3), ('protectedSavedAssetCount', 6), ('warmupRenderCount', 1)):
        require(type(report[key]) is int and report[key] == count, 'Wrong '+key)
    require(report['terrainBindings'] == TERRAIN_BINDINGS, 'Exact original terrain object/scene/mesh/material roles required')
    assets = report['diffuseAssets']
    require(isinstance(assets, list) and len(assets) == 2, 'Required diffuse asset count')
    assets_seen = set(); asset_hashes = set()
    for asset in assets:
        require(isinstance(asset, dict) and set(asset) == ASSET_KEYS, 'Diffuse asset fields')
        require(asset['assetPath'] in REQUIRED_ASSETS and asset['assetPath'] not in assets_seen, 'Diffuse asset identity/duplicate')
        require(isinstance(asset['sha256'], str) and re.fullmatch('[0-9a-f]{64}', asset['sha256']), 'Diffuse asset digest')
        require(type(asset['width']) is int and type(asset['height']) is int and (asset['width'], asset['height']) == (1024, 1024), 'Diffuse asset dimensions')
        assets_seen.add(asset['assetPath']); asset_hashes.add(asset['sha256'])
    require(assets_seen == set(REQUIRED_ASSETS) and len(asset_hashes) == 2, 'Distinct original and corrected assets required')
    originals = validate_materials(report['originalMaterials'], ORIGINAL)
    require(originals['Surface-Sand']['keywords'] == originals['Surface-Dune']['keywords'], 'Original terrain keyword mismatch')
    records = report['images']
    require(isinstance(records, list) and len(records) == 4, 'Four comparison records required')
    seen = set(); scene_hashes = set()
    for record in records:
        require(isinstance(record, dict) and set(record) == IMAGE_KEYS, 'Image record fields')
        view, variant = record['view'], record['variant']
        require(view in CAMERAS and variant in VARIANTS, 'Unknown comparison view/state')
        name = f'Scrapyard-{view}-{variant}.png'
        require(record['file'] == name and name not in seen, 'File identity/duplicate'); seen.add(name)
        require(record['normalEnabled'] is True and record['materialParametersPreserved'] is True, 'Normal and all material parameters must be retained')
        require(type(record['warmupRenderCount']) is int and record['warmupRenderCount'] == 1, 'Exactly one same-camera/state warmup render required')
        actual = validate_materials(record['actualMaterials'], ORIGINAL if variant == 'original' else CORRECTED)
        for key in originals:
            expected = dict(originals[key], baseMapAsset=ORIGINAL if variant == 'original' else CORRECTED)
            require(actual[key] == expected, 'A material property other than BaseMap changed')
        fov, at, look = CAMERAS[view]
        require(close(record['fieldOfView'], fov) and vector(record['cameraPosition'], at) and vector(record['cameraTarget'], look), 'Original fixed camera pose')
        require(type(record['width']) is int and type(record['height']) is int and (record['width'], record['height']) == (1440, 900), 'Capture dimensions')
        low, high = record['minimum'], record['maximum']
        require(all(type(x) in (int, float) and math.isfinite(x) for x in (low, high)) and
                0 <= low <= high <= 1 and high-low >= .06 and high >= .1, 'Capture pixel range')
        require(isinstance(record['sceneHash'], str) and re.fullmatch('[0-9a-f]{32}', record['sceneHash']), 'Scene dependency hash')
        scene_hashes.add(record['sceneHash'])
    require(seen == IMAGES and len(scene_hashes) == 1, 'Incomplete comparison set or changed saved scene')
    return report


def inspect_assets(project, reported=None):
    assets = []; decoded = set()
    for name in REQUIRED_ASSETS:
        path = source.safe(project/name)
        require(0 < path.stat().st_size <= 10*1024**2, 'Diffuse input size')
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            require(image.size == (1024, 1024) and image.format == ('JPEG' if name == ORIGINAL else 'PNG'), 'Required diffuse input format/dimensions')
            image.load(); rgb = image.convert('RGB')
            decoded.add(hashlib.sha256(rgb.tobytes()).hexdigest())
        assets.append(dict(assetPath=name, sha256=source.sha(path), width=1024, height=1024))
    require(len(decoded) == 2 and len({row['sha256'] for row in assets}) == 2, 'Corrected diffuse must have genuinely different pixels')
    if reported is not None:
        require({row['assetPath']: row for row in assets} == {row['assetPath']: row for row in reported}, 'Reported diffuse inputs differ from actual source bytes')
    return assets


def inspect_capture(project):
    directory = project/CAPTURE
    unlinked_directory(directory)
    require({path.name for path in directory.iterdir()} == IMAGES | {'comparison-report.json'}, 'Comparison capture closed set')
    report = validate_report(source.read_json(directory/'comparison-report.json'))
    inspect_assets(project, report['diffuseAssets'])
    decoded = set()
    for name in sorted(IMAGES):
        legacy.inspect_png(directory/name)
        with Image.open(directory/name) as image:
            decoded.add(hashlib.sha256(image.convert('RGB').tobytes()).hexdigest())
    require(len(decoded) == 4, 'Duplicated comparison pixels')
    layout = source.read_json(project/'JourneyEvidence/candidate-layout.json')
    require(layout.get('passed') is True, 'Candidate layout gate')
    return report, legacy.inspect_clearance(project)


def before():
    inspect_assets(source.PROJECT)
    legacy.before()


def package():
    require(not OUT.exists() and not OUT.is_symlink(), 'Refuse stale comparison output')
    protected = source.read_json(legacy.SNAPSHOT)
    legacy.assert_preserved(protected, legacy.tracked_snapshot(source.ROOT))
    native = inspect_native(source.TASK/'artifacts/diffuse-comparison')
    capture, clearance = inspect_capture(source.PROJECT)
    identity = source.identity()
    require(identity['runAttempt'] == '1', 'Comparison replay')
    require(not any(path.is_symlink() for path in (OUT.parent, *OUT.parents)), 'Linked output ancestor')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Only a complete, read-back-verified closed set becomes the final artifact folder.
    with tempfile.TemporaryDirectory(prefix='.diffuse-comparison-', dir=OUT.parent) as temporary:
        stage = Path(temporary)/'bundle'; stage.mkdir()
        for name in sorted(IMAGES):
            source_path = source.PROJECT/CAPTURE/name
            shutil.copyfile(source_path, stage/name)
            require(source.sha(stage/name) == source.sha(source_path), 'Screenshot copy verification failed')
        receipt = dict(identity, schema='desert-rv-diffuse-comparison/v1', scope=STATUS,
                       visualAcceptance='NOT_ACCEPTED', gameplayIntegration='NOT_RUN',
                       protectedTrackedFilesUnchanged=True, protectedTrackedFileCount=len(protected),
                       protectedSnapshotSha256=source.sha(legacy.SNAPSHOT), nativeRenderTest=RENDER_TEST,
                       nativeRenderXmlSha256=native, capture=capture, clearance=clearance,
                       imageHashes=[dict(file=name, sha256=source.sha(stage/name)) for name in sorted(IMAGES)])
        (stage/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
        require(source.read_json(stage/'receipt.json') == receipt, 'Receipt save verification failed')
        rows = [dict(path=path.name, sha256=source.sha(path), size=path.stat().st_size) for path in sorted(stage.iterdir())]
        (stage/'SHA256SUMS.json').write_text(json.dumps(rows, indent=2)+'\n')
        require(source.read_json(stage/'SHA256SUMS.json') == rows, 'Hash manifest save verification failed')
        require({path.name for path in stage.iterdir()} == IMAGES | {'receipt.json', 'SHA256SUMS.json'}, 'Sanitized comparison output set')
        require(not OUT.exists() and not OUT.is_symlink(), 'Comparison output appeared during packaging')
        stage.rename(OUT)
    print('Four actual fixed-camera diffuse comparisons verified. Diagnostic only; no visual acceptance.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('before', 'package'))
    args = parser.parse_args()
    before() if args.command == 'before' else package()
