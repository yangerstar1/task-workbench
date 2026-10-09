"""Pinned FULL Pouncer safe export; no Unity execution or production approval.

Install beside strict_output.py. Source facts come from the 37858279048 Discovery
and the reviewed 37856618820 STRICT contract, not another character's bindings.
Pillow and PyYAML are the same runner dependencies as the shared strict exporter.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from strict_output import observe_dependency_mismatch
from urp_material_metadata import read_material_asset

from strict_output import (StrictError, require, safe, sha, read, keys, finite,
    digest, vec, rel, native_report, inspect_png, dependency_digest, distance,
    angle, mesh_dimensions, ROOT_PROPERTIES, PACKAGE_SHADER, PACKAGE_ASSET_VERSION, PACKAGE_ASSET_VERSION_GUID,
    DEPENDENCY_HASH_SCOPE, dependency_meta_guid, dependency_input_paths)

CONTRACT_SHA = '863d2d87052f02bb9315db1e5f1129d5ca43dbf8978f1bf680cf8e344c4eb735'
CONTRACT_CANONICAL_SHA = 'f9eeb203052101001ac3e8336f5c995c3ed70b8927f5b7dfe532b52af84f156d'
DISCOVERY_SHA = 'de5b5d9dda1d1c426af4724f62e85b0f37567853c8b5303a1f666271c1c4b2ce'
STATES = {'Idle': 2., 'Walk': .4, 'Windup': .78, 'Attack': .8,
          'Recover': 1.3, 'Hit': .28, 'Death': 1.8}
MATERIALS = ('AmberEye', 'Keratin', 'MouthAndPupil', 'Sandstone_BaseColorTexture',
             'ToothL-1.08', 'ToothL-1.23', 'ToothR-1.08', 'ToothR-1.23', 'VentralJaw')
TEXTURES = ('baseColorFile', 'normalFile', 'metallicSmoothnessFile', 'occlusionFile', 'ormFile')
URP_LIT_GUID = '933532a4fcc9baf4fa0491de14d08ed7'
ACTOR_SCRIPT = 'Assets/DesertRV/Runtime/BeastActor.cs'
BUILTINS = {'Resources/unity_builtin_extra', 'Library/unity default resources'}
BUILTIN_GUIDS = {'00000000000000000000000000000000',
    '0000000000000000e000000000000000', '0000000000000000f000000000000000'}
NATIVE_NAMES = {
    'DesertRV.Tests.CandidateMeshMeasurementTests.ScaledTranslatedRotatedHierarchyMatchesIndependentSkinning',
    'DesertRV.Tests.CandidateMeshMeasurementTests.RejectsBlendShapesAndTruncatedSkinQuality',
    'DesertRV.Tests.CandidateMeshMeasurementTests.StaticMeshesAndFourMillimetreGateUseWorldVertices',
    'DesertRV.Tests.CandidateMaterialIdentityTests.PersistedWeaponMaterialIdentitySurvivesNeutralSamplingAndRejectsImpostors',
    'DesertRV.Tests.CandidateArtImportTests.ExecutePinnedDiscoveryOrBindingDiagnostics',
    *('DesertRV.Tests.CandidateAnimationPolicyTests.' + name for name in (
        'OnlyArmoredAttackGetsTheSourceLoopException', 'EqualKeyValuesDoNotExcuseUnsafeTangents',
        'MissingNativeAnimatorGetsCreatedAndReused', 'OpenCoreEmissionSurvivesRealSaveReimportAndReload',
        'RenderTargetCleanupDetachesCameraBeforeDestroy'))}
IMPORT_LIMITS = ['Actual Unity camera rendering and human visual review',
    'Interrupted/repeated runtime flows', 'Full three-region playthrough',
    'Android device acceptance', 'Explicit production review and unchanged production gate']
CAPTURE_LIMITS = ['Authoritative combat/weakpoint event state',
    'Gameplay interruption and reload counts', 'Whole-session restart',
    'Three-region walkthrough', 'Android device']
LOOP_INTENT = ('Only source-authored Armored Attack loops to cover attackClock>1.2 and normalized '
               'CrossFade overrun. Gameplay clock/movement/damage unchanged.')


def close(actual, expected, tolerance=1e-5):
    return finite(actual) and abs(actual-expected) <= tolerance


def baseline_shape(value):
    keys(value, ('position', 'rotation', 'scale', 'renderers'))
    vec(value['position']); vec(value['rotation'], True); vec(value['scale'])
    rows = value['renderers']
    require(isinstance(rows, list) and len(rows) == 27, 'POUNCER_NEUTRAL_RENDERER_INVENTORY')
    seen = set()
    for row in rows:
        keys(row, ('path', 'worldCenter', 'worldExtents'))
        require(rel(row['path']) and row['path'] not in seen, 'POUNCER_NEUTRAL_RENDERER_INVENTORY')
        seen.add(row['path']); vec(row['worldCenter']); vec(row['worldExtents'])
        require(all(v > 0 for v in row['worldExtents'].values()), 'POUNCER_NEUTRAL_EXTENTS')


def contract_shape(c):
    """This release intentionally admits just the reviewed new FULL contract."""
    keys(c, ('schema', 'mode', 'scope', 'id', 'kind', 'repository', 'runUrl', 'sourceCommit',
        'artifactId', 'artifactName', 'artifactSha256', 'files', 'modelFile', 'clips', 'materials', 'bindings'))
    require(type(c['schema']) is int and c['schema'] == 1 and c['kind'] == 'pouncer'
        and c['mode'] == 'STRICT_BINDING' and c['scope'] == 'FULL_CANDIDATE', 'POUNCER_FULL_ONLY')
    canonical = json.dumps(c, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    require(hashlib.sha256(canonical).hexdigest() == CONTRACT_CANONICAL_SHA, 'POUNCER_REVIEWED_CONTRACT_MISMATCH')
    # The pin covers source identity, all nine material values, all 27 bounds,
    # all seven exact take names, bindings and the independent rig anchor TRS.
    baseline_shape(c['bindings']['neutralBaseline'])
    return {row['file']: row['sha256'] for row in c['files']}


def compare_baseline(expected, actual):
    baseline_shape(actual)
    require(distance(expected['position'], actual['position']) <= 1e-5
        and distance(expected['scale'], actual['scale']) <= 1e-5
        and angle(expected['rotation'], actual['rotation']) <= .001, 'POUNCER_NEUTRAL_ROOT_MISMATCH')
    rows = {r['path']: r for r in actual['renderers']}
    require(set(rows) == {r['path'] for r in expected['renderers']}, 'POUNCER_NEUTRAL_RENDERER_INVENTORY')
    for row in expected['renderers']:
        observed = rows[row['path']]
        require(distance(row['worldCenter'], observed['worldCenter']) <= .0001
            and distance(row['worldExtents'], observed['worldExtents']) <= .0001, 'POUNCER_NEUTRAL_BOUNDS_MISMATCH')


def _yaml_documents(data):
    import yaml
    # Do not let a duplicate YAML key hide a second texture/shader reference.
    class UniqueLoader(yaml.SafeLoader):
        pass
    def mapping(loader, node, deep=False):
        value = {}
        for key_node, item_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            require(key not in value, 'POUNCER_DUPLICATE_YAML_KEY')
            # Unity GUIDs are strings even when all 32 characters are digits.
            if key == 'guid':
                require(isinstance(item_node, yaml.ScalarNode), 'POUNCER_DEPENDENCY_GUID_CLOSURE')
                item = loader.construct_scalar(item_node)
            else: item = loader.construct_object(item_node, deep=deep)
            value[key] = item
        return value
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    return list(yaml.load_all(data, Loader=UniqueLoader))


def _unity_yaml(path):
    data = safe(path).read_text()
    require(len(data) < 32*1024**2 and data.startswith('%YAML 1.1'), 'POUNCER_UNITY_YAML')
    data = re.sub(r'^%.*\n', '', data, flags=re.M)
    data = re.sub(r'^--- !u!\d+ &-?\d+(?: stripped)?$', '---', data, flags=re.M)
    return _yaml_documents(data)


def _meta_yaml(path):
    path = safe(path); require(path.stat().st_size < 1000000, 'POUNCER_META_SIZE')
    docs = _yaml_documents(path.read_text())
    require(len(docs) == 1 and isinstance(docs[0], dict)
        and type(docs[0].get('fileFormatVersion')) is int and docs[0]['fileFormatVersion'] == 2,
        'POUNCER_META_YAML')
    return docs[0]


def _require_guids(value, allowed):
    pending = [value]; visited = set()
    while pending:
        node = pending.pop()
        if not isinstance(node, (dict, list)) or id(node) in visited: continue
        visited.add(id(node)); require(len(visited) <= 100000, 'POUNCER_YAML_NODE_LIMIT')
        if isinstance(node, dict):
            if 'guid' in node:
                require(digest(node['guid'], 32) and node['guid'] in allowed | BUILTIN_GUIDS,
                    'POUNCER_DEPENDENCY_GUID_CLOSURE')
            pending.extend(node.values())
        else: pending.extend(node)


def _meta_guid(path):
    p = safe(Path(str(path)+'.meta'))
    require(p.stat().st_size < 1000000, 'POUNCER_META_SIZE')
    values = re.findall(r'^guid: ([a-f0-9]{32})$', p.read_text(), re.M)
    require(len(values) == 1 and values[0] not in BUILTIN_GUIDS, 'POUNCER_META_GUID')
    return values[0]


def material_file(project, prefix, spec, index):
    """Independently read the saved assets; Pouncer has no weapon readback."""
    asset = read_material_asset(project/f'{prefix}/Materials/Material_{index:02}.mat')
    props = asset.get('m_SavedProperties', {})
    require(asset.get('m_Name') == f'Material_{index:02}'
        and asset.get('m_Shader', {}).get('guid') == URP_LIT_GUID, 'POUNCER_MATERIAL_ASSET')
    def properties(name):
        rows = props.get(name, [])
        require(isinstance(rows, list) and all(isinstance(r, dict) and len(r) == 1 for r in rows), 'POUNCER_MATERIAL_PROPERTIES')
        result = {}
        for row in rows:
            require(not set(result).intersection(row), 'POUNCER_MATERIAL_PROPERTIES'); result.update(row)
        return result
    floats, colors, textures = (properties(k) for k in ('m_Floats', 'm_Colors', 'm_TexEnvs'))
    require(all(close(floats.get(k), v) for k, v in (
        ('_Metallic', spec['metallic']), ('_Smoothness', spec['smoothness']), ('_Cull', 2))), 'POUNCER_MATERIAL_VALUES')
    color = colors.get('_BaseColor'); keys(color, ('r', 'g', 'b', 'a'))
    require(all(close(color[a], spec['baseColor'][a]) for a in 'rgba'), 'POUNCER_MATERIAL_VALUES')
    emission = colors.get('_EmissionColor', dict(r=0, g=0, b=0, a=0))
    keys(emission, ('r', 'g', 'b', 'a'))
    require(all(close(emission[a], 0) for a in 'rgb'), 'POUNCER_UNDECLARED_EMISSION')
    require('_EMISSION' not in asset.get('m_ValidKeywords', [])
        and '_EMISSION' not in str(asset.get('m_ShaderKeywords', '')).split(), 'POUNCER_UNDECLARED_EMISSION')
    for role, binding in textures.items():
        require(isinstance(binding, dict), 'POUNCER_MATERIAL_TEXTURE_BINDING')
        texture = binding.get('m_Texture', {})
        require(isinstance(texture, dict), 'POUNCER_MATERIAL_TEXTURE_BINDING')
        if role == '_BaseMap' and spec['baseColorFile']:
            require(texture.get('guid') == _meta_guid(project/(prefix+'/Source/'+spec['baseColorFile']))
                and type(texture.get('fileID')) is int and texture['fileID'] != 0, 'POUNCER_MATERIAL_TEXTURE_BINDING')
        else:
            require(type(texture.get('fileID', 0)) is int and texture.get('fileID', 0) == 0
                and not texture.get('guid'), 'POUNCER_UNDECLARED_TEXTURE')
    require(not spec['baseColorFile'] or '_BaseMap' in textures, 'POUNCER_MATERIAL_TEXTURE_BINDING')


def required_dependencies(c, prefix):
    return {prefix+'/Candidate.prefab', prefix+'/Candidate.controller', PACKAGE_SHADER, PACKAGE_ASSET_VERSION, ACTOR_SCRIPT,
        *(prefix+'/Source/'+f['file'] for f in c['files']),
        *(prefix+f'/Materials/Material_{i:02}.mat' for i in range(9))}


def dependency_shape(c, prefix, deps):
    required = required_dependencies(c, prefix)
    require(isinstance(deps, list) and all(isinstance(p, str) for p in deps)
        and len(deps) == len(set(deps)) and required <= set(deps) <= required | BUILTINS,
        'POUNCER_DEPENDENCY_INVENTORY')


def validate_import(project, c, contract_path, report):
    keys(report, ('mode', 'scope', 'kind', 'status', 'contractSha256', 'prefab', 'dependencyHash',
        'dependencySha256', 'dependencies', 'runUrl', 'sourceCommit', 'artifactName', 'artifactSha256',
        'candidateOnly', 'visualReviewed', 'gameplayReviewed', 'derivedTextures', 'rootCurves', 'clips',
        'failures', 'stillRequired', 'importedAnimatorPaths'), ('muzzle', 'weaponCalibration'))
    require(report['mode'] == c['mode'] and report['scope'] == c['scope'] and report['kind'] == 'pouncer'
        and report['status'] == 'candidate-structure-imported-unreviewed' and report['failures'] == [], 'POUNCER_IMPORT_STATUS')
    require(report['candidateOnly'] is True and report['visualReviewed'] is False
        and report['gameplayReviewed'] is False, 'POUNCER_APPROVAL_FORBIDDEN')
    # These two known weapon-only fields are not evidence for this kind. Unity
    # may serialize an unused inline class as a default object rather than null;
    # discard the whole value during normalization, without interpreting it.
    for k in ('runUrl', 'sourceCommit', 'artifactName', 'artifactSha256'):
        require(report[k] == c[k], 'POUNCER_IMPORT_SOURCE_MISMATCH')
    prefix = 'Assets/DesertRV/CandidateArtImports/'+c['id']
    require(report['prefab'] == prefix+'/Candidate.prefab'
        and report['contractSha256'] == sha(contract_path) == CONTRACT_SHA, 'POUNCER_IMPORT_CONTRACT')
    require(report['stillRequired'] == IMPORT_LIMITS, 'POUNCER_IMPORT_LIMITATIONS')
    require(report['importedAnimatorPaths'] in ([], ['']), 'POUNCER_ANIMATOR_ROOT')
    require(report['derivedTextures'] == [], 'POUNCER_DERIVED_FORBIDDEN')
    rows = report['clips']; specs = {r['state']: r for r in c['clips']}; seen = set()
    require(isinstance(rows, list) and len(rows) == 7, 'POUNCER_IMPORTED_CLIPS')
    for row in rows:
        keys(row, ('state', 'file', 'take', 'poseExpectation', 'seconds', 'frameRate', 'floatBindings', 'objectBindings', 'loop'))
        state = row['state']
        require(isinstance(state, str) and state in specs and state not in seen, 'POUNCER_IMPORTED_CLIPS'); seen.add(state)
        spec = specs[state]
        require(all(row[k] == spec[k] for k in ('file', 'take', 'poseExpectation', 'loop'))
            and type(row['loop']) is bool and close(row['frameRate'], 100, 1e-6)
            and close(row['seconds'], spec['seconds'], .0101)
            and type(row['floatBindings']) is int and row['floatBindings'] == 480
            and type(row['objectBindings']) is int and row['objectBindings'] == 0, 'POUNCER_IMPORTED_CLIP_MISMATCH')
    rows = report['rootCurves']; seen = set(); baseline = c['bindings']['rigCurveBaseline']
    require(isinstance(rows, list) and len(rows) == 70, 'POUNCER_RIG_CURVE_INVENTORY')
    for row in rows:
        keys(row, ('state', 'property', 'keys', 'minimum', 'maximum', 'constant', 'tangentsSafe'))
        require(isinstance(row['state'], str) and row['state'] in STATES and isinstance(row['property'], str)
            and row['property'] in ROOT_PROPERTIES and (row['state'], row['property']) not in seen,
            'POUNCER_RIG_CURVE_INVENTORY'); seen.add((row['state'], row['property']))
        require(type(row['keys']) is int and 0 < row['keys'] <= 100000 and finite(row['minimum'])
            and finite(row['maximum']) and 0 <= row['maximum']-row['minimum'] < 1e-5
            and row['constant'] is True and row['tangentsSafe'] is True, 'POUNCER_RIG_CURVE_MOTION')
    for state in STATES:
        values = {r['property']: r['minimum'] for r in rows if r['state'] == state}
        for group, field in (('Position', 'position'), ('Scale', 'scale')):
            actual = {a: values['m_Local'+group+'.'+a] for a in 'xyz'}
            require(distance(actual, baseline[field]) <= 1e-5, 'POUNCER_RIG_CURVE_BASELINE')
        rotation = {a: values['m_LocalRotation.'+a] for a in 'xyzw'}; vec(rotation, True)
        require(abs(sum(v*v for v in rotation.values())-1) <= 1e-5
            and angle(rotation, baseline['rotation']) <= .001, 'POUNCER_RIG_CURVE_BASELINE')
    deps = report['dependencies']; dependency_shape(c, prefix, deps)
    actual_dependency_sha256=dependency_digest(project,deps)
    valid_dependency_identity=digest(report['dependencyHash'],32) and digest(report['dependencySha256'])
    if not valid_dependency_identity or report['dependencySha256']!=actual_dependency_sha256:
        observe_dependency_mismatch(project,deps,report['dependencyHash'],report['dependencySha256'],actual_dependency_sha256)
    require(valid_dependency_identity and report['dependencySha256']==actual_dependency_sha256, 'POUNCER_DEPENDENCY_HASH')
    guid_set = {URP_LIT_GUID}
    for path in deps:
        guid = dependency_meta_guid(project, path)
        if guid is not None:
            require(guid not in guid_set or path == PACKAGE_SHADER, 'POUNCER_DEPENDENCY_GUID_DUPLICATE')
            guid_set.add(guid)
    for path in deps:
        if path.startswith(prefix+'/') and Path(path).suffix in ('.mat', '.prefab', '.controller'):
            docs = _unity_yaml(project/path)
            require(docs and all(isinstance(d, dict) for d in docs), 'POUNCER_UNITY_YAML')
            allowed = guid_set if Path(path).suffix == '.mat' else guid_set - {PACKAGE_ASSET_VERSION_GUID}
            _require_guids(docs, allowed)
    for i, spec in enumerate(c['materials']): material_file(project, prefix, spec, i)
    return prefix


def sample_schedule():
    """Actual C# traversal order and per-frame Animator.Update step."""
    result = [(f'{s}-{t:.3f}', 0.) for s in STATES for t in (0., .25, .5, .75, .999)]
    elapsed = ('0.000', '0.016', '0.049', '0.116', '0.236', '0.486', '0.986')
    steps = (0., .016, .033, .067, .12, .25, .5)
    def sequence(prefix): result.extend((prefix+'-'+t, step) for t, step in zip(elapsed, steps))
    for t in ('0.25', '0.5', '0.75'): sequence('Attack-'+t+'-Recover')
    for state in STATES:
        if state != 'Death':
            for t in ('0.25', '0.5', '0.75'): sequence(state+'-'+t+'-Death')
    result.extend((f'animator-reset-{i}', 0.) for i in range(2))
    return result


def expected_labels():
    return {label for label, _ in sample_schedule()}


def validate_capture(folder, prefix, imp, capture, baseline):
    keys(capture, ('graphicsDeviceType', 'graphicsDeviceName', 'status', 'scope', 'prefab', 'dependencySha256',
        'visualAccepted', 'gameplayAccepted', 'armoredAttackLoopIntent', 'notCovered', 'frames', 'neutralRoot',
        'neutralMeshWorldMin', 'neutralMeshWorldMax', 'neutralMeshWorldSize'), ('weapon',))
    require(capture['status'] == 'captured-unreviewed' and capture['scope'] == 'real-Animator-pose-diagnostics-only'
        and capture['visualAccepted'] is False and capture['gameplayAccepted'] is False, 'POUNCER_CAPTURE_STATUS')
    # The known weapon-only field is ignored here and wholly removed on export.
    require(capture['graphicsDeviceType'] == 'OpenGLCore' and isinstance(capture['graphicsDeviceName'], str)
        and re.fullmatch(r'[A-Za-z0-9 ().,_/+\-]{1,240}', capture['graphicsDeviceName'])
        and 'llvmpipe' in capture['graphicsDeviceName'].lower(), 'POUNCER_REAL_SOFTWARE_GRAPHICS_REQUIRED')
    require(capture['prefab'] == prefix+'/Candidate.prefab'
        and capture['dependencySha256'] == imp['dependencySha256'], 'POUNCER_CAPTURE_DEPENDENCY')
    require(capture['armoredAttackLoopIntent'] == LOOP_INTENT and capture['notCovered'] == CAPTURE_LIMITS,
        'POUNCER_CAPTURE_LIMITATIONS')
    compare_baseline(baseline, capture['neutralRoot'])
    mesh_dimensions(capture['neutralMeshWorldMin'], capture['neutralMeshWorldMax'], capture['neutralMeshWorldSize'])
    frames = capture['frames']; schedule = sample_schedule()
    require(isinstance(frames, list) and len(frames) == len(schedule) == 184, 'POUNCER_FRAME_COUNT')
    fields = ('image', 'requestedState', 'imageSha256', 'meshPoseSha256', 'advanceSeconds', 'normalizedTime',
        'worldMinY', 'groundReferenceY', 'rootLocalPositionDelta', 'rootLocalAngleDelta', 'rootLocalScaleDelta',
        'stateHash', 'sampledVertices', 'outsideViewportVertices', 'behindCameraVertices', 'belowReferenceVertices',
        'transitioning', 'groundDiagnosticApplicable', 'rootLocalPosition', 'rootLocalRotation', 'rootLocalScale',
        'meshWorldMin', 'meshWorldMax', 'meshWorldSize', 'meshSizeRatioToNeutral')
    for i, (frame, (label, step)) in enumerate(zip(frames, schedule)):
        keys(frame, fields)
        require(frame['requestedState'] == label, 'POUNCER_FRAME_INVENTORY')
        require(frame['image'] == f'frame-{i:04}.png' and digest(frame['imageSha256'])
            and digest(frame['meshPoseSha256']) and sha(folder/frame['image']) == frame['imageSha256'], 'POUNCER_FRAME_IDENTITY')
        inspect_png(folder/frame['image'])
        for k in ('normalizedTime', 'worldMinY', 'groundReferenceY'):
            require(finite(frame[k]), 'POUNCER_FRAME_NUMBER')
        require(close(frame['advanceSeconds'], step, 1e-6) and frame['groundDiagnosticApplicable'] is True
            and type(frame['transitioning']) is bool and type(frame['stateHash']) is int
            and -2**31 <= frame['stateHash'] < 2**31, 'POUNCER_FRAME_STATE')
        # The native fixture instantiates the default-position prefab, not a
        # movable floor. A forged reference must not relax the 4 mm limit.
        require(close(frame['groundReferenceY'], 0, 1e-7), 'POUNCER_GROUND_REFERENCE')
        require(frame['worldMinY'] >= frame['groundReferenceY']-.004, 'POUNCER_GROUND_PENETRATION')
        require(type(frame['sampledVertices']) is int and 1 <= frame['sampledVertices'] <= 20000000, 'POUNCER_MESH_COUNT')
        for k in ('outsideViewportVertices', 'behindCameraVertices', 'belowReferenceVertices'):
            require(type(frame[k]) is int and 0 <= frame[k] <= frame['sampledVertices'], 'POUNCER_MESH_DIAGNOSTIC')
        for k, limit in (('rootLocalPositionDelta', 1e-5), ('rootLocalScaleDelta', 1e-5), ('rootLocalAngleDelta', .001)):
            require(finite(frame[k], 0, limit), 'POUNCER_ROOT_SAMPLE_DRIFT')
        for k in ('rootLocalPosition', 'rootLocalScale', 'meshSizeRatioToNeutral'): vec(frame[k])
        vec(frame['rootLocalRotation'], True)
        mesh_dimensions(frame['meshWorldMin'], frame['meshWorldMax'], frame['meshWorldSize'])
        require(close(frame['worldMinY'], frame['meshWorldMin']['y']), 'POUNCER_MESH_MIN_Y')
        for a in 'xyz':
            ratio = frame['meshWorldSize'][a]/capture['neutralMeshWorldSize'][a]
            require(close(frame['meshSizeRatioToNeutral'][a], ratio, max(1e-5, abs(ratio)*1e-6)), 'POUNCER_MESH_RATIO')
        for field, anchor, delta in (('rootLocalPosition', 'position', 'rootLocalPositionDelta'),
                ('rootLocalScale', 'scale', 'rootLocalScaleDelta')):
            measured = distance(frame[field], baseline[anchor])
            require(measured <= 1e-5 and abs(measured-frame[delta]) <= .000002, 'POUNCER_ROOT_VECTOR_DRIFT')
        require(angle(frame['rootLocalRotation'], baseline['rotation']) <= .001, 'POUNCER_ROOT_QUATERNION_DRIFT')
    for state in STATES:
        direct = [f for f in frames if re.fullmatch(state+r'-0\.[0-9]{3}', f['requestedState'])]
        require(len({f['meshPoseSha256'] for f in direct}) >= 2,
            'POUNCER_POSE_NOT_VARYING')
        require(len({f['stateHash'] for f in direct}) == 1 and all(not f['transitioning']
            and close(f['normalizedTime'], float(f['requestedState'].rsplit('-', 1)[1]), 1e-5)
            for f in direct), 'POUNCER_DIRECT_STATE')
    state_hashes = {state: frames[i*5]['stateHash'] for i, state in enumerate(STATES)}
    require(len(set(state_hashes.values())) == 7, 'POUNCER_DIRECT_STATE')
    for frame in frames:
        label = frame['requestedState']
        if label.endswith('-0.986'):
            target = label.rsplit('-', 2)[1]
            require(frame['transitioning'] is False and frame['stateHash'] == state_hashes[target], 'POUNCER_TRANSITION_INCOMPLETE')
        elif label.startswith('animator-reset-'):
            require(frame['transitioning'] is False and frame['stateHash'] == state_hashes['Idle']
                and close(frame['normalizedTime'], 0, 1e-5), 'POUNCER_RESET_INCOMPLETE')
    return frames


def generated_files(project, c, prefix, imp, files):
    base = project/'Assets/DesertRV/CandidateArtImports'; folder = project/prefix
    allowed = {'Source.meta', 'Materials.meta', 'contract.json', 'contract.json.meta',
        'Candidate.prefab', 'Candidate.prefab.meta', 'Candidate.controller', 'Candidate.controller.meta'}
    for name in files: allowed.update(('Source/'+name, 'Source/'+name+'.meta'))
    for i in range(9): allowed.update((f'Materials/Material_{i:02}.mat', f'Materials/Material_{i:02}.mat.meta'))
    actual = set(); dirs = {c['id'], c['id']+'/Source', c['id']+'/Materials'}
    for path in base.rglob('*'):
        require(not path.is_symlink(), 'POUNCER_SYMLINK_FORBIDDEN')
        if path.is_file(): actual.add(path.relative_to(base).as_posix())
        elif path.is_dir(): require(path.relative_to(base).as_posix() in dirs, 'POUNCER_GENERATED_DIRECTORY')
        else: require(False, 'POUNCER_UNSAFE_GENERATED_NODE')
    require(actual == {c['id']+'/'+name for name in allowed} | {c['id']+'.meta'}, 'POUNCER_GENERATED_ALLOWLIST')
    require(sha(folder/'contract.json') == CONTRACT_SHA, 'POUNCER_GENERATED_CONTRACT')
    for name, expected in files.items(): require(sha(folder/'Source'/name) == expected, 'POUNCER_GENERATED_SOURCE')
    result = [(folder/name, Path('CandidateArtImports')/c['id']/name) for name in sorted(allowed)]
    result.extend(((base/(c['id']+'.meta'), Path('CandidateArtImports')/(c['id']+'.meta')),
                   (Path(str(base)+'.meta'), Path('CandidateArtImports.meta'))))
    guids = set(); meta_documents = []
    for path, _ in result:
        safe(path)
        if path.suffix == '.meta':
            guid = _meta_guid(Path(str(path)[:-5]))
            require(guid not in guids and guid not in {URP_LIT_GUID, PACKAGE_ASSET_VERSION_GUID}, 'POUNCER_META_GUID_DUPLICATE'); guids.add(guid)
            document = _meta_yaml(path)
            require(document.get('guid') == guid, 'POUNCER_META_GUID')
            meta_documents.append(document)
        elif path.suffix in ('.mat', '.prefab', '.controller'): _unity_yaml(path)
    # The outer guid declares this meta's own asset identity. All other nested
    # GUIDs, including ModelImporter.externalObjects, must stay in the verified
    # dependency/export closure. Folder and copied-contract metas count too.
    known = guids | {URP_LIT_GUID}
    for name in imp['dependencies']:
        guid = dependency_meta_guid(project, name)
        if guid is not None: known.add(guid)
    for document in meta_documents: _require_guids(document, known - {PACKAGE_ASSET_VERSION_GUID})
    return result


def pouncer_native_report(root):
    result = native_report(root)
    matching = [p for p in (root/'artifacts/candidate-art').rglob('*.xml') if sha(p) == result]
    require(len(matching) == 1, 'POUNCER_NATIVE_VERSION')
    cases = list(ET.parse(safe(matching[0])).getroot().iter('test-case'))
    require(len(cases) == 10 and {c.get('fullname') for c in cases} == NATIVE_NAMES
        and all(c.get('result') == 'Passed' for c in cases), 'POUNCER_NATIVE_VERSION')
    return result


def frozen_read(path):
    before = sha(path); result = read(path)
    require(sha(path) == before, 'POUNCER_INPUT_CHANGED_DURING_VALIDATION')
    return result, before


def snapshot_paths(root, c, deps):
    project = root/'unity'; base = project/'Assets/DesertRV/CandidateArtImports'
    evidence = project/'JourneyEvidence/CandidateArt'; prefix = base.relative_to(project).as_posix()+'/'+c['id']
    dependency_shape(c, prefix, deps)
    paths = {project/'CandidateImportInput/contract.json', Path(str(base)+'.meta')}
    for folder in (base, evidence, root/'artifacts/candidate-art'):
        require(folder.is_dir() and not folder.is_symlink(), 'POUNCER_UNSAFE_INPUT_DIRECTORY')
        nodes = list(folder.rglob('*'))
        require(len(nodes) <= 600, 'POUNCER_INPUT_SNAPSHOT_COUNT')
        for p in nodes:
            require(not p.is_symlink(), 'POUNCER_SYMLINK_FORBIDDEN')
            if p.is_file() and (folder != root/'artifacts/candidate-art' or p.suffix == '.xml'): paths.add(p)
            else: require(p.is_dir() or (folder == root/'artifacts/candidate-art' and p.is_file()), 'POUNCER_UNSAFE_INPUT_NODE')
    paths.update(dependency_input_paths(project, deps))
    require(len(paths) <= 600 and sum(safe(p).stat().st_size for p in paths) < 544*1024**2,
        'POUNCER_INPUT_SNAPSHOT_SIZE')
    return paths


def verify_snapshot(root, c, deps, snapshot):
    require(snapshot_paths(root, c, deps) == set(snapshot)
        and all(sha(path) == expected for path, expected in snapshot.items()), 'POUNCER_INPUT_CHANGED_DURING_VALIDATION')


def _safe_identity(summary):
    result = dict(status='FAILED_NOT_ACCEPTED', approved=False, errorCode='UNVERIFIED_INPUT')
    if digest(summary.get('importCommit'), 40) and isinstance(summary.get('importRunUrl'), str) and re.fullmatch(
            r'https://github.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]*', summary['importRunUrl']):
        result.update(importCommit=summary['importCommit'], importRunUrl=summary['importRunUrl'])
    return result


def _empty_output(output):
    require(output.is_dir() and not output.is_symlink() and all(not p.is_symlink() for p in output.parents)
        and not any(output.iterdir()), 'POUNCER_EXPORT_NOT_EMPTY_OR_UNSAFE')


def _verify_staging(staged, records, receipt_hash):
    require(staged.is_dir() and not staged.is_symlink(), 'POUNCER_STAGING_UNSAFE_NODE')
    files = {r['path'] for r in records} | {'receipt.json'}
    require(len(files) == len(records)+1 and all(rel(name) for name in files), 'POUNCER_STAGING_INVENTORY')
    directories = {parent.as_posix() for name in files for parent in Path(name).parents if parent != Path('.')}
    require(all(sha(staged/r['path']) == r['sha256'] and (staged/r['path']).stat().st_size == r['bytes'] for r in records)
        and sha(staged/'receipt.json') == receipt_hash, 'POUNCER_STAGING_CHANGED')
    # Inventory comes last so an added node during the final hash reads is not
    # silently committed simply because it was absent from an earlier walk.
    actual_files, actual_dirs = set(), set()
    for path in staged.rglob('*'):
        require(not path.is_symlink(), 'POUNCER_STAGING_UNSAFE_NODE')
        name = path.relative_to(staged).as_posix()
        if path.is_file(): actual_files.add(name)
        elif path.is_dir(): actual_dirs.add(name)
        else: require(False, 'POUNCER_STAGING_UNSAFE_NODE')
    require(actual_files == files and actual_dirs == directories, 'POUNCER_STAGING_INVENTORY')


def export_pouncer(root, output, c, summary, native, protected):
    """Dispatcher entry: it owns receipt-only failure handling for its empty output."""
    root, output = Path(root), Path(output)
    identity = _safe_identity(summary); summary.clear(); summary.update(identity)
    files = contract_shape(c); project = root/'unity'; contract_path = project/'CandidateImportInput/contract.json'
    contract, contract_hash = frozen_read(contract_path)
    require(contract == c and contract_hash == CONTRACT_SHA, 'POUNCER_REVIEWED_CONTRACT_MISMATCH')
    summary.update(**{k: c[k] for k in ('sourceCommit', 'runUrl', 'artifactSha256', 'artifactId', 'artifactName',
        'mode', 'scope', 'kind')}, contractSha256=contract_hash)
    require(native == 'success', 'STRICT_NATIVE_FAILED'); require(protected == 'success', 'STRICT_PROTECTED_SOURCE_FAILED')
    require('importCommit' in summary, 'POUNCER_CURRENT_RUN_IDENTITY'); _empty_output(output)
    evidence = project/'JourneyEvidence/CandidateArt'
    imp, ih = frozen_read(evidence/'import-report.json'); capture, ch = frozen_read(evidence/'capture-report.json')
    raw_hashes = {'import-report.json': ih, 'capture-report.json': ch}
    snapshot = {p: sha(p) for p in snapshot_paths(root, c, imp['dependencies'])}
    require(snapshot[contract_path] == contract_hash and all(snapshot[evidence/k] == v for k, v in raw_hashes.items()),
        'POUNCER_INPUT_CHANGED_DURING_VALIDATION')
    native_hash = pouncer_native_report(root)
    prefix = validate_import(project, c, contract_path, imp)
    frames = validate_capture(evidence, prefix, imp, capture, c['bindings']['neutralBaseline'])
    payload = generated_files(project, c, prefix, imp, files)
    require({p.name for p in evidence.iterdir()} == set(raw_hashes) | {f['image'] for f in frames}, 'POUNCER_EVIDENCE_ALLOWLIST')
    require(all(p.is_file() and not p.is_symlink() for p in evidence.iterdir()), 'POUNCER_UNSAFE_EVIDENCE_NODE')
    payload.extend((evidence/f['image'], Path('frames')/f['image']) for f in frames)
    require(sum(safe(p).stat().st_size for p, _ in payload) < 512*1024**2, 'POUNCER_EXPORT_SIZE')
    verify_snapshot(root, c, imp['dependencies'], snapshot)
    # Only the hashes captured BEFORE validation may authorize exported bytes.
    source_records = [(p, dest, snapshot[p]) for p, dest in payload]
    staged = Path(tempfile.mkdtemp(prefix='.pouncer-safe-', dir=output.parent))
    try:
        records = []
        for path, dest, expected in source_records:
            target = staged/dest; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(safe(path), target)
            require(sha(target) == expected == sha(path), 'POUNCER_SOURCE_CHANGED_DURING_EXPORT')
            records.append(dict(path=dest.as_posix(), sha256=expected, bytes=target.stat().st_size))
        # Omit only the three known, inapplicable weapon fields. Their values are
        # never used as Pouncer evidence; all other fields have strict schemas.
        safe_import = {k: v for k, v in imp.items() if k not in ('muzzle', 'weaponCalibration')}
        safe_capture = {k: v for k, v in capture.items() if k != 'weapon'}
        for name, obj in (('import-report.json', safe_import), ('capture-report.json', safe_capture)):
            require(sha(evidence/name) == raw_hashes[name], 'POUNCER_REPORT_CHANGED_DURING_EXPORT')
            path = staged/name; path.write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n')
            records.append(dict(path=name, sha256=sha(path), bytes=path.stat().st_size))
        require(dependency_digest(project, imp['dependencies']) == imp['dependencySha256'], 'POUNCER_DEPENDENCY_CHANGED_DURING_EXPORT')
        require(sha(staged/'CandidateArtImports'/c['id']/'contract.json') == CONTRACT_SHA, 'POUNCER_STAGED_CONTRACT')
        for name, expected in files.items():
            require(sha(staged/'CandidateArtImports'/c['id']/'Source'/name) == expected, 'POUNCER_STAGED_SOURCE')
        for frame in frames:
            path = staged/'frames'/frame['image']
            require(sha(path) == frame['imageSha256'], 'POUNCER_STAGED_FRAME_IDENTITY'); inspect_png(path)
        require(pouncer_native_report(root) == native_hash, 'POUNCER_NATIVE_CHANGED_DURING_EXPORT')
        verify_snapshot(root, c, imp['dependencies'], snapshot)
        result = dict(summary, status='STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED', approved=False, errorCode=None,
            files=records, nativeXmlSha256=native_hash, nativeCases=10, images=184, weakpointImages=0,
            directImages=35, attackRecoverImages=21, deathTransitionImages=126, resetImages=2,
            protectedSource='UNCHANGED', calibratedForScene=False, visualApproved=False, gameplayAccepted=False,
            rawReportSha256=raw_hashes, discoverySha256=DISCOVERY_SHA,
            normalizedAwayFields=['import-report.json:muzzle', 'import-report.json:weaponCalibration', 'capture-report.json:weapon'],
            dependencyHashScope=DEPENDENCY_HASH_SCOPE)
        receipt = (json.dumps(result, indent=2, allow_nan=False)+'\n').encode()
        (staged/'receipt.json').write_bytes(receipt)
        # Require the whole staging tree, not merely hashes of listed files.
        _verify_staging(staged, records, hashlib.sha256(receipt).hexdigest())
        _empty_output(output); staged.replace(output); summary.update(result)
    finally:
        if staged.exists(): shutil.rmtree(staged)
    return summary


def export(root, output, native='success', protected='success'):
    """Standalone wrapper: failures expose a fixed-code receipt, never raw logs."""
    root, output = Path(root), Path(output)
    require(not output.exists() and not output.is_symlink() and all(not p.is_symlink() for p in output.parents),
        'POUNCER_EXPORT_EXISTS_OR_UNSAFE')
    output.mkdir(parents=True)
    summary = _safe_identity(dict(importCommit=os.environ.get('GITHUB_SHA'),
        importRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/'+os.environ.get('GITHUB_RUN_ID', '')))
    try:
        return export_pouncer(root, output, read(root/'unity/CandidateImportInput/contract.json'), summary, native, protected)
    except StrictError as error:
        code = str(error)
        summary['errorCode'] = code if re.fullmatch(r'(?:STRICT|POUNCER|URP)_[A-Z0-9_]{1,100}', code) else 'INVALID_EVIDENCE'
        raise StrictError(summary['errorCode']) from None
    except Exception:
        summary['errorCode'] = 'INVALID_EVIDENCE'
        raise StrictError('INVALID_EVIDENCE') from None
    finally:
        if summary.get('status') != 'STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED':
            (output/'receipt.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('tasks/desert-rv'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native', required=True); parser.add_argument('--protected', required=True)
    args = parser.parse_args()
    try: export(args.root, args.output, args.native, args.protected)
    except StrictError as error: raise SystemExit(str(error))
