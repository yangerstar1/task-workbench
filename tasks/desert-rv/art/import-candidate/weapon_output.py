"""Fail-closed Weapon STRICT export. Native candidate evidence is never scene approval.

Install next to strict_output.py. This module does not run Unity, dispatch a workflow,
edit source assets, or infer a native pass from its synthetic regression fixtures.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET

from urp_material_metadata import read_material_asset

from strict_output import (StrictError, require, safe, sha, read, keys, finite,
    digest, vec, rel, payload_name, native_report, inspect_png, dependency_digest,
    derived_record, distance, angle, unity_euler, mesh_dimensions, observe_dependency_mismatch,
    PACKAGE_SHADER, PACKAGE_ASSET_VERSION, PACKAGE_ASSET_VERSION_GUID, DEPENDENCY_HASH_SCOPE, dependency_meta_guid, dependency_snapshot, verify_dependency_snapshot)

STATES = {'Idle': 2.0, 'Fire': .22, 'Reload': 1.65}
MATERIALS = ('Graphite_Parkerized', 'Brushed_Steel', 'Glove_Graphite',
             'Cuff_Safety_Orange', 'Glove_Seam', 'Powdercoat_Ivory', 'Oxide_Red')
TEXTURES = ('baseColorFile', 'normalFile', 'metallicSmoothnessFile', 'occlusionFile', 'ormFile')
RIG = 'DesertRV_WeaponHands_Rig/root'
DISCOVERY_SHA = '0df7e5ed696af8e0a1069a933c593299b4f6061da4762d95a371bff0c70cebe3'
SOURCE_LENGTHS = {'leftUpperSource': .3757658898830414, 'leftForeSource': .33503732085227966,
                  'rightUpperSource': .4036087393760681, 'rightForeSource': .3350372910499573}
IMPORT_LIMITS = ['Actual Unity camera rendering and human visual review',
    'Interrupted/repeated runtime flows', 'Full three-region playthrough',
    'Android device acceptance', 'Explicit production review and unchanged production gate']
CAPTURE_LIMITS = ['Authoritative combat/weakpoint event state',
    'Authoritative gameplay interruptions and reload commits', 'Whole-session restart',
    'Three-region walkthrough', 'Android device']
MECHANICS_SCOPE = ('Real imported Animator and actual presenter count projection. Reload alone applies runtime fixed-length IK; '
                   'Idle/Fire are measured without extra correction. No gameplay commit/FX/reticle acceptance.')
MUZZLE_GATE = ('BLOCKED: source-axis-derived adapter only; verify actual barrel geometry, gameplay camera, '
               'obstruction/reticle alignment and author the flash before scene use. No flash is bound; '
               'WeaponPresentation.ValidateBindings must fail until completed.')
LOOP_INTENT = ('Only source-authored Armored Attack loops to cover attackClock>1.2 and normalized CrossFade overrun. '
               'Gameplay clock/movement/damage unchanged.')
ORIGINAL_SCRIPTS = {'Assets/DesertRV/Runtime/WeaponPresentation.cs', 'Assets/DesertRV/Runtime/WeaponArmReach.cs'}
# Matched to the pinned official Lit.shader.meta by the shared resolver.
URP_LIT_GUID = '933532a4fcc9baf4fa0491de14d08ed7'
NATIVE_CASES = 10
EMISSION_CASE = 'DesertRV.Tests.CandidateAnimationPolicyTests.OpenCoreEmissionSurvivesRealSaveReimportAndReload'
MATERIAL_IDENTITY_CASE = 'DesertRV.Tests.CandidateMaterialIdentityTests.PersistedWeaponMaterialIdentitySurvivesNeutralSamplingAndRejectsImpostors'
ZERO = dict(x=0, y=0, z=0)
ONE = dict(x=1, y=1, z=1)


def close(value, expected, tolerance=1e-6):
    return finite(value) and abs(value - expected) <= tolerance


def norm(value):
    return math.sqrt(sum(x*x for x in value.values()))


def unit(value):
    vec(value)
    require(abs(norm(value)-1) <= 2e-5, 'WEAPON_UNIT_VECTOR')


def rotate(q, value):
    x, y, z, w = (q[k] for k in ('x', 'y', 'z', 'w'))
    vx, vy, vz = (value[k] for k in ('x', 'y', 'z'))
    tx, ty, tz = 2*(y*vz-z*vy), 2*(z*vx-x*vz), 2*(x*vy-y*vx)
    return dict(x=vx+w*tx+y*tz-z*ty, y=vy+w*ty+z*tx-x*tz, z=vz+w*tz+x*ty-y*tx)


def color(value):
    keys(value, ('r', 'g', 'b', 'a'))
    require(all(finite(x, 0, 1) for x in value.values()), 'WEAPON_COLOR')


def contract_shape(c):
    keys(c, ('schema', 'mode', 'scope', 'id', 'kind', 'repository', 'runUrl', 'sourceCommit',
        'artifactId', 'artifactName', 'artifactSha256', 'files', 'modelFile', 'clips', 'materials', 'bindings', 'weapon'))
    require(type(c['schema']) is int and c['schema'] == 1 and c['mode'] == 'STRICT_BINDING'
        and c['scope'] == 'FULL_CANDIDATE' and c['kind'] == 'weapon', 'WEAPON_FULL_ONLY')
    require(c['repository'] == 'yangerstar1/task-workbench'
        and isinstance(c['runUrl'], str) and re.fullmatch(r'https://github.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]*', c['runUrl'])
        and digest(c['sourceCommit'], 40) and digest(c['artifactSha256']), 'WEAPON_SOURCE_IDENTITY')
    require(type(c['artifactId']) is int and c['artifactId'] > 0 and isinstance(c['id'], str)
        and re.fullmatch(r'[a-z0-9][a-z0-9-]{3,79}', c['id']) and isinstance(c['artifactName'], str)
        and re.fullmatch(r'[A-Za-z0-9_.-]{1,160}', c['artifactName']), 'WEAPON_CONTRACT_IDENTITY')
    require(isinstance(c['files'], list) and 1 <= len(c['files']) <= 32, 'WEAPON_INPUT_COUNT')
    files = {}
    for row in c['files']:
        keys(row, ('file', 'sha256'))
        require(payload_name(row['file']) and digest(row['sha256'])
            and row['file'].lower() not in {n.lower() for n in files}, 'WEAPON_INPUT_ALLOWLIST')
        files[row['file']] = row['sha256']
    require(c['modelFile'] == 'weapon_hands.fbx' and c['modelFile'] in files
        and {n for n in files if n.endswith('.fbx')} == {c['modelFile']}, 'WEAPON_MODEL_FILE')
    require(isinstance(c['clips'], list) and len(c['clips']) == 3, 'WEAPON_CLIP_INVENTORY')
    seen = set()
    for row in c['clips']:
        keys(row, ('state', 'file', 'take', 'seconds', 'loop', 'poseExpectation'))
        state = row['state']
        require(isinstance(state, str) and state in STATES and state not in seen, 'WEAPON_CLIP_INVENTORY')
        seen.add(state)
        require(row['file'] == c['modelFile'] and row['take'] == state and close(row['seconds'], STATES[state], 1e-7)
            and row['loop'] is (state == 'Idle') and row['poseExpectation'] == 'varying', 'WEAPON_CLIP_POLICY')
    require(isinstance(c['materials'], list) and len(c['materials']) == 7, 'WEAPON_MATERIAL_COUNT')
    texture_files = set()
    for index, m in enumerate(c['materials']):
        keys(m, ('sourceName', 'baseColor', 'metallic', 'smoothness', 'doubleSided'), TEXTURES)
        require(m['sourceName'] == MATERIALS[index] and m['doubleSided'] is True, 'WEAPON_MATERIAL_IDENTITY')
        color(m['baseColor'])
        require(finite(m['metallic'], 0, 1) and finite(m['smoothness'], 0, 1), 'WEAPON_MATERIAL_VALUES')
        for key in TEXTURES:
            if key in m:
                require(isinstance(m[key], str) and (m[key] == '' or m[key] in files and not m[key].endswith('.fbx')), 'WEAPON_TEXTURE_SOURCE')
                if m[key]: texture_files.add(m[key])
        require(not m.get('ormFile') or not (m.get('metallicSmoothnessFile') or m.get('occlusionFile')), 'WEAPON_TEXTURE_ROLE_CONFLICT')
        # Native ORM readback expects the declared scalar to match the converted material.
        require(not m.get('ormFile') or m['smoothness'] == 1, 'WEAPON_ORM_SMOOTHNESS')
    require(set(files) == {c['modelFile']} | texture_files, 'WEAPON_UNUSED_INPUT')
    b = c['bindings']
    keys(b, ('animatorPath', 'body', 'leftHand', 'rightHand', 'muzzle', 'incomingOffset',
        'leftReloadOffset', 'loadedNails', 'incomingNails'))
    expected = {'animatorPath': '', 'body': 'Forged_Main_Housing',
        'leftHand': RIG+'/LeftReloadOffset/arm.L/hand.L', 'rightHand': RIG+'/arm.R/hand.R',
        'muzzle': RIG+'/weapon/Muzzle', 'incomingOffset': RIG+'/IncomingOffset', 'leftReloadOffset': RIG+'/LeftReloadOffset'}
    require(all(b[k] == v for k, v in expected.items()), 'WEAPON_BINDING_PATH')
    for key, label in [('loadedNails', 'LoadedNail'), ('incomingNails', 'IncomingNail')]:
        require(b[key] == [f'{label}_{i:02}' for i in range(12)], 'WEAPON_NAIL_INVENTORY')
    w = c['weapon']
    keys(w, ('rigRoot', 'left', 'right', 'neutralState', 'neutralTimeSeconds', 'discoveryReportSha256',
        'sourceToRigScale', *SOURCE_LENGTHS, 'positionToleranceRig', 'numericToleranceRig',
        'sourceMuzzleForwardLocal', 'sourceMuzzleUpLocal'))
    require(w['rigRoot'] == RIG and w['neutralState'] == 'Idle' and close(w['neutralTimeSeconds'], 0, 0)
        and w['discoveryReportSha256'] == DISCOVERY_SHA, 'WEAPON_DISCOVERY_PIN')
    for side, suffix in [('left', 'L'), ('right', 'R')]:
        keys(w[side], ('upperArm', 'forearm', 'wristTip', 'wristTarget'))
        upper = RIG+'/upperarm.'+suffix
        require(w[side] == dict(upperArm=upper, forearm=upper+'/forearm.'+suffix,
            wristTip=upper+'/forearm.'+suffix+'/WristTip.'+suffix,
            wristTarget=b[side+'Hand']+'/WristTarget.'+suffix), 'WEAPON_ARM_PATH')
    require(close(w['sourceToRigScale'], .01, 1e-10) and close(w['positionToleranceRig'], 1e-5, 1e-12)
        and close(w['numericToleranceRig'], 1e-7, 1e-14)
        and all(close(w[k], v, 1e-9) for k, v in SOURCE_LENGTHS.items()), 'WEAPON_SOURCE_UNITS')
    for key, expected in [('sourceMuzzleForwardLocal', dict(x=0, y=1, z=0)), ('sourceMuzzleUpLocal', dict(x=0, y=0, z=1))]:
        vec(w[key]); require(distance(w[key], expected) <= 1e-7, 'WEAPON_SOURCE_MUZZLE_AXIS')
    return files


def _unity_yaml(path):
    import yaml
    data = safe(path).read_text()
    require(len(data) < 32*1024**2 and data.startswith('%YAML 1.1'), 'WEAPON_UNITY_YAML')
    # Unity's tag directive is not available to subsequent documents in PyYAML.
    data = re.sub(r'^%.*\n', '', data, flags=re.M)
    data = re.sub(r'^--- !u!\d+ &-?\d+(?: stripped)?$', '---', data, flags=re.M)
    return list(yaml.safe_load_all(data))


def _reject_package_script_reference(path):
    """The URP editor script is legal only in its verified .mat peer document.

    Compose retains duplicate mapping entries and decodes quoted/escaped scalar
    values without constructing objects. Keep the older general closure intact.
    """
    import yaml
    path=safe(path);require(path.stat().st_size<32*1024**2,'WEAPON_PACKAGE_SCRIPT_SCOPE')
    data=path.read_text(encoding='utf-8')
    data=re.sub(r'^%.*\n','',data,flags=re.M)
    data=re.sub(r'^--- !u!\d+ &-?\d+(?: stripped)?$','---',data,flags=re.M)
    visited={}
    try:
        for document in yaml.compose_all(data,Loader=yaml.SafeLoader):
            pending=[document]
            while pending:
                node=pending.pop()
                if node is None or id(node) in visited:continue
                visited[id(node)]=node;require(len(visited)<=100000,'WEAPON_PACKAGE_SCRIPT_SCOPE')
                if isinstance(node,yaml.ScalarNode):
                    require(node.value.strip().lower()!=PACKAGE_ASSET_VERSION_GUID,'WEAPON_PACKAGE_SCRIPT_SCOPE')
                elif isinstance(node,yaml.MappingNode):
                    pending.extend(child for pair in node.value for child in pair)
                elif isinstance(node,yaml.SequenceNode):pending.extend(node.value)
    except yaml.YAMLError as error:
        raise StrictError('WEAPON_PACKAGE_SCRIPT_SCOPE') from error


def _meta_guid(path):
    p = safe(Path(str(path)+'.meta'))
    require(p.stat().st_size < 1000000, 'WEAPON_META_SIZE')
    guids = re.findall(r'^guid: ([a-f0-9]{32})$', p.read_text(), re.M)
    require(len(guids) == 1, 'WEAPON_META_GUID')
    return guids[0]


def material_file(project, prefix, m, index, readback):
    path = f'{prefix}/Materials/Material_{index:02}.mat'
    keys(readback, ('sourceName', 'materialPath', 'shader', 'expectedColor', 'actualColor',
        'expectedMetallic', 'actualMetallic', 'expectedSmoothness', 'actualSmoothness', 'actualCull',
        'actualName', 'materialGuid', 'materialLocalId'))
    require(readback['sourceName'] == m['sourceName'] and readback['materialPath'] == path
        and readback['shader'] == 'Universal Render Pipeline/Lit', 'WEAPON_MATERIAL_READBACK')
    for key in ('expectedColor', 'actualColor'):
        color(readback[key]); require(all(close(readback[key][a], m['baseColor'][a], 1e-5) for a in 'rgba'), 'WEAPON_MATERIAL_COLOR')
    for key, field in [('expectedMetallic','metallic'), ('actualMetallic','metallic'),
                       ('expectedSmoothness','smoothness'), ('actualSmoothness','smoothness')]:
        require(close(readback[key], m[field], 1e-5), 'WEAPON_MATERIAL_SCALAR')
    require(close(readback['actualCull'], 0, 1e-5), 'WEAPON_MATERIAL_CULL')
    require(isinstance(readback['actualName'],str) and re.fullmatch(r'[A-Za-z0-9_. -]{1,160}',readback['actualName']), 'WEAPON_MATERIAL_NAME_OBSERVATION')
    require(digest(readback['materialGuid'],32) and readback['materialGuid']==_meta_guid(project/path)
        and type(readback['materialLocalId']) is int and readback['materialLocalId']!=0, 'WEAPON_MATERIAL_PERSISTENT_IDENTITY')
    material_headers=re.findall(r'^--- !u!21 &(-?[0-9]+)$',safe(project/path).read_text(),re.M)
    require(len(material_headers)==1 and int(material_headers[0])==readback['materialLocalId'], 'WEAPON_MATERIAL_LOCAL_ID')
    asset = read_material_asset(project/path, expected_local_id=readback['materialLocalId'])
    props = asset.get('m_SavedProperties', {})
    require(asset.get('m_Name') == readback['actualName']
        and asset.get('m_Shader', {}).get('guid') == URP_LIT_GUID, 'WEAPON_MATERIAL_ASSET')
    def properties(name):
        rows = props.get(name, [])
        require(isinstance(rows, list) and all(isinstance(r, dict) and len(r) == 1 for r in rows), 'WEAPON_MATERIAL_ASSET')
        merged = {}
        for row in rows:
            require(not set(merged).intersection(row), 'WEAPON_MATERIAL_ASSET'); merged.update(row)
        return merged
    floats, colors, textures = properties('m_Floats'), properties('m_Colors'), properties('m_TexEnvs')
    require(all(close(floats.get(k), value, 1e-5) for k, value in
        [('_Metallic', m['metallic']), ('_Smoothness', m['smoothness']), ('_Cull', 0)]), 'WEAPON_MATERIAL_ASSET_VALUES')
    actual = colors.get('_BaseColor'); color(actual)
    require(all(close(actual[k], m['baseColor'][k], 1e-5) for k in 'rgba'), 'WEAPON_MATERIAL_ASSET_VALUES')
    roles = {'_BaseMap': m.get('baseColorFile'), '_BumpMap': m.get('normalFile'),
        '_MetallicGlossMap': m.get('metallicSmoothnessFile'), '_OcclusionMap': m.get('occlusionFile')}
    for key, source in roles.items():
        derived = m.get('ormFile') and key in ('_MetallicGlossMap', '_OcclusionMap')
        target = f'{prefix}/Derived/ORM_{index:02}.png' if derived else prefix+'/Source/'+source if source else None
        value = textures.get(key, {}).get('m_Texture', {})
        if target:
            require(value.get('guid') == _meta_guid(project/target) and type(value.get('fileID')) is int
                and value['fileID'] != 0, 'WEAPON_MATERIAL_TEXTURE_BINDING')
        else:
            require(value.get('fileID', 0) == 0 and not value.get('guid'), 'WEAPON_UNDECLARED_TEXTURE')


def calibration_shape(value, c, prefix, project):
    keys(value, ('neutralState', 'neutralPoseEvidence', 'sourceSha256', 'rigRoot', 'neutralTimeSeconds',
        'rigWorldScale', 'positionToleranceWorld', 'numericToleranceWorld', 'left', 'right',
        'materials', 'sceneCalibrated', 'visualApproved'))
    w = c['weapon']; source_hash = next(f['sha256'] for f in c['files'] if f['file'] == c['modelFile'])
    evidence = f'Unity6000.3.19f1: {prefix}/Source/{c["modelFile"]} sha256={source_hash} neutral=Idle seconds=0 discovery={DISCOVERY_SHA}'
    require(value['sceneCalibrated'] is False and value['visualApproved'] is False, 'WEAPON_APPROVAL_FORBIDDEN')
    require(value['neutralState'] == 'Idle' and close(value['neutralTimeSeconds'], 0, 0)
        and value['neutralPoseEvidence'] == evidence and value['sourceSha256'] == source_hash
        and value['rigRoot'] == RIG, 'WEAPON_CALIBRATION_IDENTITY')
    require(close(value['rigWorldScale'], 100, .001), 'WEAPON_RIG_SCALE')
    scale = value['rigWorldScale']
    require(close(value['positionToleranceWorld'], w['positionToleranceRig']*scale, 1e-9)
        and close(value['numericToleranceWorld'], w['numericToleranceRig']*scale, 1e-11), 'WEAPON_WORLD_TOLERANCE')
    for side in ('left', 'right'):
        a = value[side]
        keys(a, ('upperArm', 'forearm', 'wristTip', 'wristTarget', 'calibrated', 'upperLengthRig',
            'foreLengthRig', 'sourceUpperLength', 'sourceForeLength', 'sourceToRigScale', 'upperAxisLocal',
            'foreAxisLocal', 'poleRigLocal', 'shoulderLocal', 'elbowLocal', 'tipLocal', 'upperScale',
            'foreScale', 'upperBindRotation', 'foreBindRotation', 'neutralPoseEvidence'))
        require(a['calibrated'] is True and a['neutralPoseEvidence'] == evidence, 'WEAPON_MATH_CALIBRATION')
        for key in ('upperArm', 'forearm', 'wristTip', 'wristTarget'):
            require(a[key] == w[side][key], 'WEAPON_CALIBRATION_PATHS')
        require(close(a['sourceToRigScale'], w['sourceToRigScale'], 1e-9), 'WEAPON_CALIBRATION_UNITS')
        for joint in ('Upper', 'Fore'):
            src, actual = a['source'+joint+'Length'], a[joint.lower()+'LengthRig']
            require(close(src, w[side+joint+'Source'], 1e-7) and finite(actual, 1e-6, .1)
                and abs(actual-src*w['sourceToRigScale']) <= w['positionToleranceRig'], 'WEAPON_CALIBRATION_LENGTH')
        for key in ('upperAxisLocal', 'foreAxisLocal', 'poleRigLocal'): unit(a[key])
        for key in ('shoulderLocal', 'elbowLocal', 'tipLocal', 'upperScale', 'foreScale'): vec(a[key])
        for key in ('upperScale', 'foreScale'):
            require(distance(a[key], ONE) <= 2e-5, 'WEAPON_ARM_SCALE')
        for key in ('upperBindRotation', 'foreBindRotation'): vec(a[key], True)
        for position, axis in [('elbowLocal', 'upperAxisLocal'), ('tipLocal', 'foreAxisLocal')]:
            length = norm(a[position]); require(length > w['numericToleranceRig'], 'WEAPON_ARM_AXIS')
            require(distance({k:v/length for k,v in a[position].items()}, a[axis]) <= 2e-5, 'WEAPON_ARM_AXIS')
    require(isinstance(value['materials'], list) and len(value['materials']) == 7, 'WEAPON_MATERIAL_READBACK_COUNT')
    for i, m in enumerate(c['materials']): material_file(project, prefix, m, i, value['materials'][i])


def muzzle_shape(value, c):
    keys(value, ('calibratedForScene', 'sourceAxisDerived', 'forwardAdapterPath', 'forwardAdapterWorld',
        'sourceBoneLocalForwardAxis', 'sourceHead', 'sourceTail', 'importedWorldPosition',
        'importedBasisX', 'importedBasisY', 'importedBasisZ', 'gate'))
    require(value['calibratedForScene'] is False and value['sourceAxisDerived'] is True
        and value['sourceBoneLocalForwardAxis'] == '+Y' and value['gate'] == MUZZLE_GATE,
        'WEAPON_MUZZLE_APPROVAL_OR_AXIS')
    require(value['forwardAdapterPath'] == c['bindings']['muzzle']+'/CandidateShotMuzzleAxis', 'WEAPON_MUZZLE_ADAPTER_PATH')
    observed = {'sourceHead': dict(x=0,y=.35,z=.072), 'sourceTail': dict(x=0,y=.385,z=.072),
        'importedWorldPosition': dict(x=0,y=.072,z=-.35), 'importedBasisX': dict(x=1,y=0,z=0),
        'importedBasisY': dict(x=0,y=0,z=-1), 'importedBasisZ': dict(x=0,y=1,z=0)}
    for key, expected in observed.items():
        vec(value[key]); require(distance(value[key], expected) <= 1e-5, 'WEAPON_MUZZLE_SOURCE_OBSERVATION')
    unit(value['forwardAdapterWorld'])
    require(distance(value['forwardAdapterWorld'], value['importedBasisY']) <= 1e-5, 'WEAPON_MUZZLE_FORWARD')


def validate_import(project, c, contract_path, report):
    keys(report, ('mode', 'scope', 'kind', 'status', 'contractSha256', 'prefab', 'dependencyHash',
        'dependencySha256', 'dependencies', 'runUrl', 'sourceCommit', 'artifactName', 'artifactSha256',
        'candidateOnly', 'visualReviewed', 'gameplayReviewed', 'derivedTextures', 'rootCurves', 'clips',
        'failures', 'stillRequired', 'importedAnimatorPaths', 'muzzle', 'weaponCalibration'))
    require(report['mode'] == c['mode'] and report['scope'] == c['scope'] and report['kind'] == 'weapon'
        and report['status'] == 'candidate-structure-imported-unreviewed' and report['failures'] == [], 'WEAPON_IMPORT_STATUS')
    require(report['candidateOnly'] is True and report['visualReviewed'] is False and report['gameplayReviewed'] is False,
        'WEAPON_APPROVAL_FORBIDDEN')
    for key in ('runUrl', 'sourceCommit', 'artifactName', 'artifactSha256'):
        require(report[key] == c[key], 'WEAPON_IMPORT_SOURCE_MISMATCH')
    prefix = 'Assets/DesertRV/CandidateArtImports/'+c['id']
    require(report['prefab'] == prefix+'/Candidate.prefab' and report['contractSha256'] == sha(contract_path), 'WEAPON_IMPORT_CONTRACT')
    require(report['stillRequired'] == IMPORT_LIMITS, 'WEAPON_IMPORT_LIMITATIONS')
    require(report['importedAnimatorPaths'] in ([], ['']) and report['rootCurves'] == [], 'WEAPON_ANIMATOR_ROOT')
    require(isinstance(report['clips'], list) and len(report['clips']) == 3, 'WEAPON_IMPORTED_CLIPS')
    seen = set(); specs = {x['state']:x for x in c['clips']}
    for row in report['clips']:
        keys(row, ('state','file','take','poseExpectation','seconds','frameRate','floatBindings','objectBindings','loop'))
        state = row['state']; require(isinstance(state,str) and state in specs and state not in seen, 'WEAPON_IMPORTED_CLIPS'); seen.add(state)
        spec = specs[state]
        require(all(row[k] == spec[k] for k in ('file','take','poseExpectation','loop')) and type(row['loop']) is bool
            and finite(row['frameRate'], 1, 1000) and finite(row['seconds'], 0, 3)
            and abs(row['seconds']-spec['seconds']) <= 1/row['frameRate']+.0001
            and type(row['floatBindings']) is int and 0 < row['floatBindings'] < 100000
            and type(row['objectBindings']) is int and row['objectBindings'] == 0, 'WEAPON_IMPORTED_CLIP_MISMATCH')
    needed = {prefix+'/Candidate.prefab', prefix+'/Candidate.controller', prefix+'/Source/'+c['modelFile'], PACKAGE_SHADER} | ORIGINAL_SCRIPTS
    for i,m in enumerate(c['materials']):
        needed.add(prefix+f'/Materials/Material_{i:02}.mat')
        for key in TEXTURES[:-1]:
            if m.get(key): needed.add(prefix+'/Source/'+m[key])
        if m.get('ormFile'): needed.add(prefix+f'/Derived/ORM_{i:02}.png')
    deps = report['dependencies']
    require(isinstance(deps,list) and all(isinstance(p,str) for p in deps) and needed <= set(deps), 'WEAPON_REQUIRED_DEPENDENCIES')
    actual_dependency_sha256=dependency_digest(project,deps)
    valid_dependency_identity=digest(report['dependencyHash'],32) and digest(report['dependencySha256'])
    if not valid_dependency_identity or report['dependencySha256']!=actual_dependency_sha256:
        observe_dependency_mismatch(project,deps,report['dependencyHash'],report['dependencySha256'],actual_dependency_sha256)
    require(valid_dependency_identity and report['dependencySha256'] == actual_dependency_sha256, 'WEAPON_DEPENDENCY_HASH')
    # Check all serialized GUID references of candidate YAML against declared dependencies.
    guid_set = {URP_LIT_GUID}
    for path in deps:
        guid = dependency_meta_guid(project, path)
        if guid is not None: guid_set.add(guid)
    for path in deps:
        if path.startswith(prefix+'/') and Path(path).suffix in ('.prefab','.controller','.mat'):
            data = safe(project/path).read_text()
            require(all(g in guid_set or g in {'00000000000000000000000000000000',
                '0000000000000000e000000000000000','0000000000000000f000000000000000'}
                for g in re.findall(r'\bguid: ([a-f0-9]{32})\b', data)), 'WEAPON_DEPENDENCY_GUID_CLOSURE')
            if Path(path).suffix != '.mat': _reject_package_script_reference(project/path)
    calibration_shape(report['weaponCalibration'], c, prefix, project)
    muzzle_shape(report['muzzle'], c)
    return prefix


def sample_schedule():
    """Exact native loop order: 13*331 + 3*3*3*5 + 2*5 + 3*5 = 4463."""
    q0 = dict(x=0,y=0,z=0,w=1)
    phases = (0.,34/99,54/99,67/99,1.)
    scenarios = ((0,12),(3,5),(11,1))
    rows = []
    for before, added in [(b,12-b) for b in range(12)]+[(3,5)]:
        rows.extend(('Reload', step/330, before, added, ZERO, q0, None) for step in range(331))
    for offset in (0,100,200):
        for euler in ((0,0,0),(12,37,-4),(-18,143,6)):
            rotation = unity_euler(dict(zip(('x','y','z'),euler)))
            for before,added in scenarios:
                rows.extend(('Reload',t,before,added,dict(x=offset,y=0,z=0),rotation,None) for t in phases)
    for state in ('Idle','Fire'):
        rows.extend((state,t,12,0,ZERO,q0,f'{state}-{t:.6f}') for t in (0,.25,.5,.75,.999))
    for before,added in scenarios:
        rows.extend(('Reload',t,before,added,ZERO,q0,f'Reload-{before}-plus-{added}-{t:.6f}') for t in phases)
    return rows


def grip_weight(t):
    frame = 1+min(1,max(0,t))*99
    if frame < 30 or frame >= 73: return 0
    if frame < 35: return (frame-30)/5
    if frame <= 68: return 1
    return (73-frame)/5


def diagnostics_shape(d, binding, calibration, ik):
    fields = ('upperLength','foreLength','wristGap','shoulderDrift','targetDrift',
              'targetDistance','expectedUpperLength','expectedForeLength')
    keys(d, ('solved','measured','measurementsFinite','reason',*fields))
    reasons = (None,'') if ik else ('Unmodified Animator pose observed; no IK executed.',)
    require(d['solved'] is ik and d['measured'] is True and d['measurementsFinite'] is True
        and d['reason'] in reasons, 'WEAPON_SAMPLE_DIAGNOSTICS_STATE')
    require(all(finite(d[k],0,5) for k in fields), 'WEAPON_SAMPLE_NUMBER')
    scale = calibration['rigWorldScale']; tolerance = calibration['positionToleranceWorld']; epsilon = calibration['numericToleranceWorld']
    for joint in ('Upper','Fore'):
        expected = binding[joint.lower()+'LengthRig']*scale
        require(close(d['expected'+joint+'Length'],expected,1e-7)
            and abs(d[joint.lower()+'Length']-expected) <= tolerance, 'WEAPON_SAMPLE_FIXED_LENGTH')
    require(d['wristGap'] <= tolerance and d['shoulderDrift'] <= epsilon and d['targetDrift'] <= epsilon,
        'WEAPON_SAMPLE_METRIC_LIMIT')
    require(abs(d['expectedUpperLength']-d['expectedForeLength'])-tolerance <= d['targetDistance']
        <= d['expectedUpperLength']+d['expectedForeLength']+tolerance, 'WEAPON_SAMPLE_REACH')


def validate_weapon(value, calibration):
    keys(value, ('status','mechanicsPassed','gameplayAccepted','visualAccepted','sceneCalibrated','scope',
        'sampleRateHz','maxWristGapWorld','maxShoulderDriftWorld','maxTargetDriftWorld','samples','failures'))
    require(value['status'] == 'imported-arm-count-mechanics-passed-unreviewed' and value['mechanicsPassed'] is True
        and value['failures'] == [] and value['scope'] == MECHANICS_SCOPE, 'WEAPON_MECHANICS_STATUS')
    require(value['gameplayAccepted'] is False and value['visualAccepted'] is False
        and value['sceneCalibrated'] is False, 'WEAPON_APPROVAL_FORBIDDEN')
    require(type(value['sampleRateHz']) is int and value['sampleRateHz'] == 200, 'WEAPON_SAMPLE_RATE')
    samples = value['samples']; schedule = sample_schedule()
    require(isinstance(samples,list) and len(samples) == len(schedule) == 4463, 'WEAPON_SAMPLE_COUNT')
    maxima = {'wristGap':0.,'shoulderDrift':0.,'targetDrift':0.}; hashes = {s:set() for s in STATES}
    image_samples = []; base_pitch = None
    for row, (state,t,before,added,position,rotation,label) in zip(samples,schedule):
        keys(row, ('state','animatorPoseSha256','normalized','loadedBefore','plannedAdded','ikApplied','poseAccepted',
            'left','right','incomingLocalOffset','leftLocalOffset','worldPitch','subjectWorldPosition','subjectWorldRotation'))
        require(row['state'] == state and close(row['normalized'], t, 1e-6)
            and type(row['loadedBefore']) is int and row['loadedBefore'] == before
            and type(row['plannedAdded']) is int and row['plannedAdded'] == added, 'WEAPON_SAMPLE_INVENTORY')
        ik = state == 'Reload'
        require(row['ikApplied'] is ik and row['poseAccepted'] is True, 'WEAPON_IK_POLICY')
        require(digest(row['animatorPoseSha256']), 'WEAPON_ANIMATOR_POSE_HASH'); hashes[state].add(row['animatorPoseSha256'])
        for key in ('incomingLocalOffset','leftLocalOffset','worldPitch','subjectWorldPosition'): vec(row[key])
        vec(row['subjectWorldRotation'],True)
        require(distance(row['subjectWorldPosition'],position) <= 1e-5
            and angle(row['subjectWorldRotation'],rotation) <= .001, 'WEAPON_WORLD_SAMPLE_TRANSFORM')
        if base_pitch is None: base_pitch = row['worldPitch']
        require(.001 < norm(row['worldPitch']) < .1 and distance(row['worldPitch'],rotate(rotation,base_pitch)) <= 1e-6,
            'WEAPON_WORLD_PITCH')
        # Both carrier parents are the pinned root, whose native world basis is identity and scale 100.
        expected_strip = {k:v*before/calibration['rigWorldScale'] if ik else 0 for k,v in base_pitch.items()}
        expected_hand = {k:v*grip_weight(t) for k,v in expected_strip.items()}
        require(distance(row['incomingLocalOffset'],expected_strip) <= 1e-7
            and distance(row['leftLocalOffset'],expected_hand) <= 1e-7, 'WEAPON_COUNT_CARRIER')
        for side in ('left','right'):
            diagnostics_shape(row[side],calibration[side],calibration,ik)
            for key in maxima: maxima[key] = max(maxima[key],row[side][key])
        if label: image_samples.append((label,row))
    require(all(len(hashes[s]) >= 2 for s in STATES), 'WEAPON_ANIMATOR_POSE_NOT_VARYING')
    for key in maxima:
        field = 'max'+key[0].upper()+key[1:]+'World'
        require(close(value[field],maxima[key],1e-9), 'WEAPON_METRIC_SUMMARY')
    return image_samples


def validate_capture(folder,prefix,imp,capture):
    keys(capture, ('graphicsDeviceType','graphicsDeviceName','status','scope','prefab','dependencySha256',
        'visualAccepted','gameplayAccepted','armoredAttackLoopIntent','notCovered','frames','weapon',
        'neutralRoot','neutralMeshWorldMin','neutralMeshWorldMax','neutralMeshWorldSize'))
    require(capture['status'] == 'captured-unreviewed' and capture['scope'] == 'real-Animator-pose-diagnostics-only'
        and capture['visualAccepted'] is False and capture['gameplayAccepted'] is False, 'WEAPON_CAPTURE_STATUS')
    require(capture['graphicsDeviceType'] == 'OpenGLCore' and isinstance(capture['graphicsDeviceName'],str)
        and re.fullmatch(r'[A-Za-z0-9 ().,_/+\-]{1,240}',capture['graphicsDeviceName'])
        and 'llvmpipe' in capture['graphicsDeviceName'].lower(), 'WEAPON_REAL_GRAPHICS_REQUIRED')
    require(capture['prefab'] == prefix+'/Candidate.prefab' and capture['dependencySha256'] == imp['dependencySha256'],
        'WEAPON_CAPTURE_DEPENDENCY')
    require(capture['notCovered'] == CAPTURE_LIMITS and capture['armoredAttackLoopIntent'] == LOOP_INTENT,
        'WEAPON_CAPTURE_LIMITATIONS')
    # The shared Armored capture serializes genuine neutral geometry for every kind.
    extended = {'neutralRoot','neutralMeshWorldMin','neutralMeshWorldMax','neutralMeshWorldSize'}
    require(not extended.intersection(capture) or extended <= set(capture), 'WEAPON_NEUTRAL_SCHEMA')
    if extended <= set(capture):
        neutral = capture['neutralRoot']; keys(neutral, ('position','rotation','scale','renderers'))
        vec(neutral['position']);vec(neutral['rotation'],True);vec(neutral['scale'])
        require(distance(neutral['position'],ZERO)<=1e-5 and distance(neutral['scale'],ONE)<=1e-5
            and angle(neutral['rotation'],dict(x=0,y=0,z=0,w=1))<=.001, 'WEAPON_NEUTRAL_ROOT')
        require(isinstance(neutral['renderers'],list) and 1<=len(neutral['renderers'])<=2000,'WEAPON_NEUTRAL_RENDERERS')
        seen=set()
        for row in neutral['renderers']:
            keys(row,('path','worldCenter','worldExtents'));require(rel(row['path']) and row['path'] not in seen,'WEAPON_NEUTRAL_RENDERERS');seen.add(row['path'])
            vec(row['worldCenter']);vec(row['worldExtents'])
            require(all(finite(v,0,20) for v in row['worldExtents'].values()) and norm(row['worldExtents'])>0,'WEAPON_NEUTRAL_EXTENTS')
        mesh_dimensions(capture['neutralMeshWorldMin'],capture['neutralMeshWorldMax'],capture['neutralMeshWorldSize'])
    image_samples = validate_weapon(capture['weapon'],imp['weaponCalibration'])
    frames = capture['frames']; require(isinstance(frames,list) and len(frames) == 25, 'WEAPON_FRAME_COUNT')
    mesh_hashes = {state:set() for state in STATES}
    for i,(frame,(label,sample)) in enumerate(zip(frames,image_samples)):
        keys(frame, ('image','requestedState','imageSha256','meshPoseSha256','advanceSeconds','normalizedTime',
            'worldMinY','groundReferenceY','rootLocalPositionDelta','rootLocalAngleDelta','rootLocalScaleDelta',
            'stateHash','sampledVertices','outsideViewportVertices','behindCameraVertices','belowReferenceVertices',
            'transitioning','groundDiagnosticApplicable','rootLocalPosition','rootLocalRotation','rootLocalScale',
            'meshWorldMin','meshWorldMax','meshWorldSize','meshSizeRatioToNeutral'))
        require(frame['image'] == f'frame-{i:04}.png' and frame['requestedState'] == label
            and digest(frame['imageSha256']) and digest(frame['meshPoseSha256'])
            and sha(folder/frame['image']) == frame['imageSha256'], 'WEAPON_FRAME_IDENTITY')
        inspect_png(folder/frame['image'])
        require(close(frame['advanceSeconds'],0,0) and close(frame['normalizedTime'],sample['normalized'],1e-5)
            and finite(frame['worldMinY']) and close(frame['groundReferenceY'],0,1e-5)
            and type(frame['stateHash']) is int and -2**31 <= frame['stateHash'] < 2**31
            and frame['transitioning'] is False and frame['groundDiagnosticApplicable'] is False, 'WEAPON_FRAME_STATE')
        require(type(frame['sampledVertices']) is int and 0 < frame['sampledVertices'] <= 20000000, 'WEAPON_FRAME_VERTEX_COUNT')
        for key in ('outsideViewportVertices','behindCameraVertices','belowReferenceVertices'):
            require(type(frame[key]) is int and frame[key] == 0, 'WEAPON_FRAME_VISIBILITY')
        for key,limit in [('rootLocalPositionDelta',1e-5),('rootLocalAngleDelta',.001),('rootLocalScaleDelta',1e-5)]:
            require(finite(frame[key],0,limit), 'WEAPON_FRAME_ROOT_DRIFT')
        for key in ('rootLocalPosition','meshWorldMin','meshWorldMax','meshWorldSize','meshSizeRatioToNeutral'):
            if key in frame: vec(frame[key])
        if 'rootLocalPosition' in frame: require(distance(frame['rootLocalPosition'],ZERO)<=1e-5,'WEAPON_FRAME_ROOT_DRIFT')
        if 'rootLocalScale' in frame: vec(frame['rootLocalScale']); require(distance(frame['rootLocalScale'],ONE)<=1e-5,'WEAPON_FRAME_ROOT_DRIFT')
        if 'rootLocalRotation' in frame:
            vec(frame['rootLocalRotation'],True);require(angle(frame['rootLocalRotation'],dict(x=0,y=0,z=0,w=1))<=.001,'WEAPON_FRAME_ROOT_DRIFT')
        extra = {'rootLocalPosition','rootLocalRotation','rootLocalScale','meshWorldMin','meshWorldMax','meshWorldSize','meshSizeRatioToNeutral'}
        require(not extra.intersection(frame) or (extra <= set(frame) and extended <= set(capture)), 'WEAPON_FRAME_GEOMETRY_SCHEMA')
        if extra <= set(frame):
            mesh_dimensions(frame['meshWorldMin'],frame['meshWorldMax'],frame['meshWorldSize'])
            require(close(frame['worldMinY'],frame['meshWorldMin']['y'],1e-5),'WEAPON_FRAME_MESH_MINIMUM')
            for axis in 'xyz':
                expected=frame['meshWorldSize'][axis]/capture['neutralMeshWorldSize'][axis]
                require(finite(expected,.01,100) and close(frame['meshSizeRatioToNeutral'][axis],expected,1e-4),'WEAPON_FRAME_MESH_RATIO')
        mesh_hashes[sample['state']].add(frame['meshPoseSha256'])
    require(all(len(mesh_hashes[s]) >= 2 for s in STATES), 'WEAPON_MESH_POSE_NOT_VARYING')
    return frames


def generated_files(project,c,prefix,imp,files):
    base = project/'Assets/DesertRV/CandidateArtImports'; folder = project/prefix
    allowed = {'Source.meta','contract.json','contract.json.meta','Candidate.prefab','Candidate.prefab.meta',
        'Candidate.controller','Candidate.controller.meta','Materials.meta'}
    for name in files: allowed.update(('Source/'+name,'Source/'+name+'.meta'))
    if any(n.startswith('technical/') for n in files): allowed.add('Source/technical.meta')
    for i in range(7): allowed.update((f'Materials/Material_{i:02}.mat',f'Materials/Material_{i:02}.mat.meta'))
    expected = [(i,m) for i,m in enumerate(c['materials']) if m.get('ormFile')]
    require(isinstance(imp['derivedTextures'],list) and len(imp['derivedTextures']) == len(expected), 'WEAPON_DERIVED_COUNT')
    if expected: allowed.add('Derived.meta')
    for rec,(i,m) in zip(imp['derivedTextures'],expected):
        dst = derived_record(project,prefix,rec,m,i,files); name = dst[len(prefix)+1:]; allowed.update((name,name+'.meta'))
    actual = set()
    allowed_dirs = {p for n in allowed for p in [str(a) for a in Path(n).parents] if p != '.'}
    for p in base.rglob('*'):
        require(not p.is_symlink(), 'WEAPON_SYMLINK_FORBIDDEN')
        if p.is_file(): actual.add(p.relative_to(base).as_posix())
        elif p.is_dir(): require(p.relative_to(base).as_posix() in {c['id']}|{c['id']+'/'+d for d in allowed_dirs}, 'WEAPON_GENERATED_DIRECTORY')
        else: require(False,'WEAPON_UNSAFE_GENERATED_NODE')
    require(actual == {c['id']+'/'+n for n in allowed}|{c['id']+'.meta'}, 'WEAPON_GENERATED_ALLOWLIST')
    require(sha(folder/'contract.json') == sha(project/'CandidateImportInput/contract.json'), 'WEAPON_GENERATED_CONTRACT')
    for name,h in files.items(): require(sha(folder/'Source'/name) == h, 'WEAPON_GENERATED_SOURCE')
    result = [(folder/n,Path('CandidateArtImports')/c['id']/n) for n in sorted(allowed)]
    result.extend([(base/(c['id']+'.meta'),Path('CandidateArtImports')/(c['id']+'.meta')),
                   (Path(str(base)+'.meta'),Path('CandidateArtImports.meta'))])
    guids = set()
    for p,_ in result:
        safe(p)
        if p.suffix == '.meta':
            _reject_package_script_reference(p)
            guid = _meta_guid(Path(str(p)[:-5])); require(guid not in guids and guid not in {URP_LIT_GUID, PACKAGE_ASSET_VERSION_GUID},'WEAPON_META_GUID_DUPLICATE');guids.add(guid)
        elif p.suffix in ('.mat','.prefab','.controller'): _unity_yaml(p)
    return result


def _safe_identity(summary):
    value = {'status':'FAILED_NOT_ACCEPTED','approved':False,'errorCode':'UNVERIFIED_INPUT'}
    if digest(summary.get('importCommit'),40) and isinstance(summary.get('importRunUrl'),str) and re.fullmatch(
        r'https://github.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]*',summary['importRunUrl']):
        value.update(importCommit=summary['importCommit'],importRunUrl=summary['importRunUrl'])
    return value


def read_capture(path):
    """4463 JsonUtility-pretty samples exceed the generic helper's 8 MiB cap."""
    path=safe(path)
    if path.stat().st_size<=8*1024**2:return read(path)
    require(path.stat().st_size<=32*1024**2,'WEAPON_CAPTURE_OVERSIZED')
    def pairs(items):
        result={}
        for k,v in items:require(k not in result,'STRICT_DUPLICATE_JSON_KEY');result[k]=v
        return result
    def nonfinite(_):raise StrictError('STRICT_NONFINITE_JSON')
    return json.loads(path.read_text(),object_pairs_hook=pairs,parse_constant=nonfinite)


def weapon_native_report(root):
    result=native_report(root)
    # A stale shared helper must not turn a four-case pass into a five-case receipt.
    matching=[p for p in (root/'artifacts/candidate-art').rglob('*.xml') if sha(p)==result]
    require(len(matching)==1,'WEAPON_NATIVE_VERSION')
    cases=list(ET.parse(safe(matching[0])).getroot().iter('test-case'))
    require(len(cases)==NATIVE_CASES and sum(c.get('fullname')==EMISSION_CASE for c in cases)==1
        and sum(c.get('fullname')==MATERIAL_IDENTITY_CASE for c in cases)==1,
        'WEAPON_NATIVE_VERSION')
    return result


def frozen_read(path, reader=read):
    before=sha(path);value=reader(path)
    require(sha(path)==before,'WEAPON_INPUT_CHANGED_DURING_VALIDATION')
    return value,before


def input_snapshot(project,evidence,contract_path,report_hashes):
    """Freeze every potentially exported byte BEFORE any payload validation."""
    base=project/'Assets/DesertRV/CandidateArtImports'
    paths=[contract_path,Path(str(base)+'.meta')]
    for p in base.rglob('*'):
        require(not p.is_symlink(),'WEAPON_SYMLINK_FORBIDDEN')
        if p.is_file():paths.append(p)
    paths.extend(p for p in evidence.iterdir() if p.is_file() or p.is_symlink())
    require(len(paths)<=400,'WEAPON_INPUT_SNAPSHOT_COUNT')
    require(sum(safe(p).stat().st_size for p in paths)<544*1024**2,'WEAPON_INPUT_SNAPSHOT_SIZE')
    result={p:sha(p) for p in paths}
    require(all(result[evidence/name]==h for name,h in report_hashes.items()),'WEAPON_INPUT_CHANGED_DURING_VALIDATION')
    return result


def verify_snapshot(snapshot):
    require(all(sha(path)==expected for path,expected in snapshot.items()),'WEAPON_INPUT_CHANGED_DURING_VALIDATION')


def export_weapon(root,output,c,summary,native,protected):
    """Dispatcher entry; output must be an empty runner-owned directory.

    Only native NUnit + verified reports and unchanged original tracked assets can
    authorize this bounded export. The caller catches StrictError and writes a safe
    failure receipt. No raw exception/report text is appended to the receipt.
    """
    root,output = Path(root),Path(output)
    identity = _safe_identity(summary); summary.clear(); summary.update(identity)
    files = contract_shape(c); project = root/'unity'; contract_path = project/'CandidateImportInput/contract.json'
    contract,contract_hash=frozen_read(contract_path)
    require(contract == c, 'WEAPON_CONTRACT_ARGUMENT_MISMATCH')
    summary.update(**{k:c[k] for k in ('sourceCommit','runUrl','artifactSha256','artifactId','artifactName','mode','scope','kind')},contractSha256=contract_hash)
    require(native == 'success','STRICT_NATIVE_FAILED');require(protected == 'success','STRICT_PROTECTED_SOURCE_FAILED')
    require('importCommit' in summary,'WEAPON_CURRENT_RUN_IDENTITY')
    require(output.is_dir() and not output.is_symlink() and all(not p.is_symlink() for p in output.parents)
        and not any(output.iterdir()),'WEAPON_EXPORT_NOT_EMPTY_OR_UNSAFE')
    native_hash = weapon_native_report(root); evidence = project/'JourneyEvidence/CandidateArt'
    imp,import_hash=frozen_read(evidence/'import-report.json')
    capture,capture_hash=frozen_read(evidence/'capture-report.json',read_capture)
    raw_hashes={'import-report.json':import_hash,'capture-report.json':capture_hash}
    dependency_frozen=dependency_snapshot(project,imp['dependencies'])
    snapshot=input_snapshot(project,evidence,contract_path,raw_hashes)
    require(snapshot[contract_path]==contract_hash,'WEAPON_INPUT_CHANGED_DURING_VALIDATION')
    prefix = validate_import(project,c,contract_path,imp)
    frames = validate_capture(evidence,prefix,imp,capture)
    payload = generated_files(project,c,prefix,imp,files)
    require({p.name for p in evidence.iterdir()} == {'import-report.json','capture-report.json'}|{f['image'] for f in frames},
        'WEAPON_EVIDENCE_ALLOWLIST')
    require(all(p.is_file() and not p.is_symlink() for p in evidence.iterdir()), 'WEAPON_UNSAFE_EVIDENCE_NODE')
    payload.extend((evidence/f['image'],Path('frames')/f['image']) for f in frames)
    require(sum(safe(p).stat().st_size for p,_ in payload)<512*1024**2,'WEAPON_EXPORT_SIZE')
    verify_snapshot(snapshot)
    verify_dependency_snapshot(project,imp['dependencies'],dependency_frozen)
    # Use the BEFORE-validation hashes; never bless newly changed bytes here.
    source_records = [(p,dest,snapshot[p]) for p,dest in payload]
    staged = Path(tempfile.mkdtemp(prefix='.weapon-safe-',dir=output.parent))
    try:
        records = []
        for p,dest,expected in source_records:
            d = staged/dest;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(safe(p),d)
            require(sha(d) == expected == sha(p),'WEAPON_SOURCE_CHANGED_DURING_EXPORT')
            records.append(dict(path=dest.as_posix(),sha256=expected,bytes=d.stat().st_size))
        for name,obj in [('import-report.json',imp),('capture-report.json',capture)]:
            require(sha(evidence/name) == raw_hashes[name], 'WEAPON_REPORT_CHANGED_DURING_EXPORT')
            d=staged/name;d.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
            records.append(dict(path=name,sha256=sha(d),bytes=d.stat().st_size))
        require(dependency_digest(project,imp['dependencies']) == imp['dependencySha256'], 'WEAPON_DEPENDENCY_CHANGED_DURING_EXPORT')
        require(sha(staged/'CandidateArtImports'/c['id']/'contract.json')==contract_hash,'WEAPON_STAGED_CONTRACT')
        for name,expected in files.items():
            require(sha(staged/'CandidateArtImports'/c['id']/'Source'/name)==expected,'WEAPON_STAGED_SOURCE')
        for frame in frames:
            path=staged/'frames'/frame['image']
            require(sha(path)==frame['imageSha256'],'WEAPON_STAGED_FRAME_IDENTITY');inspect_png(path)
        result=dict(summary,status='STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED',approved=False,errorCode=None,
            files=records,nativeXmlSha256=native_hash,nativeCases=NATIVE_CASES,images=25,weaponSamples=4463,
            denseSamples=4303,worldSamples=135,imageSamples=25,protectedSource='UNCHANGED',
            calibratedForScene=False,visualApproved=False,gameplayAccepted=False,rawReportSha256=raw_hashes,
            dependencyHashScope=DEPENDENCY_HASH_SCOPE)
        require(weapon_native_report(root)==native_hash,'WEAPON_NATIVE_CHANGED_DURING_EXPORT')
        verify_snapshot(snapshot)
        verify_dependency_snapshot(project,imp['dependencies'],dependency_frozen)
        receipt_bytes=(json.dumps(result,indent=2,allow_nan=False)+'\n').encode()
        (staged/'receipt.json').write_bytes(receipt_bytes)
        import strict_output
        strict_output.verify_staged_inventory(staged,records,hashlib.sha256(receipt_bytes).hexdigest())
        require(not output.is_symlink() and not any(output.iterdir()),'WEAPON_EXPORT_NOT_EMPTY_OR_UNSAFE')
        staged.replace(output)
        summary.update(result)
    finally:
        if staged.exists():shutil.rmtree(staged)
    return summary


def export(root,output,native='success',protected='success'):
    """Standalone safe wrapper for tests / CLI; never replace an existing export."""
    root,output=Path(root),Path(output)
    require(not output.exists() and not output.is_symlink() and all(not p.is_symlink() for p in output.parents), 'WEAPON_EXPORT_EXISTS_OR_UNSAFE')
    output.mkdir(parents=True)
    summary=_safe_identity(dict(importCommit=os.environ.get('GITHUB_SHA'),
        importRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/'+os.environ.get('GITHUB_RUN_ID','')))
    try:
        return export_weapon(root,output,read(root/'unity/CandidateImportInput/contract.json'),summary,native,protected)
    except StrictError as error:
        code=str(error)
        summary['errorCode']=code if re.fullmatch(r'(?:STRICT|WEAPON|URP)_[A-Z0-9_]{1,100}',code) else 'INVALID_EVIDENCE'
        raise StrictError(summary['errorCode']) from None
    except Exception:
        summary['errorCode']='INVALID_EVIDENCE'
        raise StrictError('INVALID_EVIDENCE') from None
    finally:
        if summary.get('status')!='STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED':
            (output/'receipt.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path('tasks/desert-rv'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--native',required=True);parser.add_argument('--protected',required=True)
    args=parser.parse_args()
    try:export(args.root,args.output,args.native,args.protected)
    except StrictError as error:raise SystemExit(str(error))
