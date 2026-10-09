#!/usr/bin/env python3
"""Add one self-describing emission proof after the unchanged strict R4/audit gates.
Native inputs are read-only. A new proof failure never publishes the final strict bundle.
"""
import argparse
import json
import math
import re
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import environment_v4_r4_audit as audit

r4, v4, legacy, source = audit.r4, audit.v4, audit.legacy, audit.source
require = source.require
TARGET = legacy.GENERATED + '/Layout-FFC261.mat'
PROOF = 'emission-proof.json'
SCHEMA = 'desert-rv-single-beacon-emission-proof/v1'
REVISION = 'SINGLE_BEACON_EMISSION_LIFECYCLE_R1'
STATUS = 'NATIVE_EMISSION_LIFECYCLE_VALIDATED_NOT_ART_OR_GAMEPLAY_ACCEPTANCE'
SCOPE = 'Warm beacon GI/emission lifecycle correction plus the retained two-terrain-material R4 subproof.'
VALIDATOR = 'UnityEditor.Rendering.Universal.ShaderGUI.LitShader'
SHADER = 'Universal Render Pipeline/Lit'
LIFECYCLE_MARKER = 'CORRECTED_BEACON_EMISSION_LIFECYCLE '
OBSERVATION_MARKER = 'CORRECTED_BEACON_EMISSION_OBSERVATION '
MAX_PROOF = 32768
HDR = dict(r=2.5, g=1.9, b=.95, a=2.5)
BASE_COLOR = dict(r=1.0, g=.76, b=.38, a=1.0)
GI_DISCLOSURE = {
    'mode': 'BakedEmissive', 'value': 2, 'futureBakeEligible': True,
    'bakePerformedByThisFix': False, 'originalVisibleHdrPreserved': True,
    'meaning': 'This material is eligible to contribute to a future GI bake. This fix performs no bake and changes no Light, LightingSettings, or existing baked data.'}
IDENTITY_KEYS = {'repository','commit','runId','runAttempt','editorVersion','exportManifestSha256','sourceStateSha256'}
LIFECYCLE_KEYS = {'path','beforeSha256','savedSha256','metaSha256','validator','beforeGIFlags','afterGIFlags','saveImportCycles',
                  'beforeEmissionKeyword','afterEmissionKeyword','secondSaveStable','allNativeObjectsClean','beforeEmissionColor','afterEmissionColor'}
OBSERVATION_KEYS = {'phase','path','shader','rendererCount','giFlags','loadedObjectCount','dirtyLoadedObjectCount',
                    'materialPresent','rendererEnabled','singleMaterial','expectedMaterialIdentity','expectedEmissionColor','expectedGI',
                    'emissionKeyword','materialDirty','keywords','emissionColor'}
PROOF_KEYS = {'schema','producerRevision','status','scope','identity','native','authoredGiSemantics','legacyTerrainSubproof',
              'target','authorLifecycle','observations','phaseFiles','auditLoadedObjects','serializedMaterial','images','visualAcceptance','gameplayIntegration'}
OBJECT_TYPES = {'UnityEngine.Material','UnityEditor.Rendering.Universal.AssetVersion','UnityEditor.NativeFormatImporter'}
PHASES = ('freeze','postcapture','postexit')


def exact(value, keys, label):
    require(type(value) is dict and set(value) == keys, 'Emission ' + label + ' fields')


def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'Emission digest')
    return value


def integer(value, minimum, maximum, label):
    require(type(value) is int and minimum <= value <= maximum, 'Emission ' + label)
    return value


def color(value, expected=HDR):
    exact(value, set(HDR), 'color')
    require(all(type(v) in (int,float) and math.isfinite(v) and abs(v-expected[k]) <= 1e-6 for k,v in value.items()),
            'Emission original authored color changed')
    return value


def unique_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Emission duplicate JSON field')
            result[key] = value
        return result
    def reject_constant(value):
        raise ValueError('Emission nonfinite JSON constant')
    try:
        return json.loads(text, object_pairs_hook=unique, parse_constant=reject_constant)
    except (ValueError, TypeError, RecursionError):
        raise ValueError('Invalid bounded emission JSON') from None


def validate_lifecycle(row):
    exact(row, LIFECYCLE_KEYS, 'lifecycle')
    require(row['path'] == TARGET and row['validator'] == VALIDATOR, 'Emission target/installed validator')
    for key in ('beforeSha256','savedSha256','metaSha256'): digest(row[key])
    require(type(row['beforeGIFlags']) is int and row['beforeGIFlags'] in (0,2,4), 'Emission unexpected original GI mode')
    require(type(row['afterGIFlags']) is int and row['afterGIFlags'] == 2 and
            type(row['saveImportCycles']) is int and row['saveImportCycles'] == 2, 'Emission authored GI/cycle count')
    require(type(row['beforeEmissionKeyword']) is bool and row['afterEmissionKeyword'] is True and
            row['secondSaveStable'] is True and row['allNativeObjectsClean'] is True, 'Emission stable enabled state')
    color(row['beforeEmissionColor']); color(row['afterEmissionColor'])
    require(row['beforeEmissionColor'] == row['afterEmissionColor'], 'Emission before/after native HDR differs')
    return row


def validate_observation(row, phase):
    exact(row, OBSERVATION_KEYS, 'observation')
    require(row['phase'] == phase and row['path'] == TARGET and row['shader'] == SHADER, 'Emission observation identity')
    require(type(row['rendererCount']) is int and row['rendererCount'] == 1 and
            type(row['giFlags']) is int and row['giFlags'] == 2, 'Emission observed renderer/GI')
    integer(row['loadedObjectCount'], 1, 32, 'loaded object count')
    require(type(row['dirtyLoadedObjectCount']) is int and row['dirtyLoadedObjectCount'] == 0, 'Emission loaded subobject dirty')
    for key in ('materialPresent','rendererEnabled','singleMaterial','expectedMaterialIdentity','expectedEmissionColor','expectedGI','emissionKeyword'):
        require(row[key] is True, 'Emission observed state not confirmed')
    require(row['materialDirty'] is False and row['keywords'] == ['_EMISSION'], 'Emission observed material dirty/keyword mismatch')
    color(row['emissionColor'])
    return row


def native_markers(directory):
    """The existing Passed-single-case identity gate remains mandatory, not a log grep."""
    native_sha = legacy.inspect_native_report(directory)
    matches = [p for p in directory.rglob('*.xml') if source.sha(p) == native_sha]
    require(len(matches) == 1, 'Emission unique native XML identity')
    raw = source.safe(matches[0]).read_bytes()
    require(len(raw) <= 10*1024**2 and b'<!DOCTYPE' not in raw and b'<!ENTITY' not in raw, 'Emission XML bound/entity declaration')
    root = ET.fromstring(raw); cases = list(root.iter('test-case'))
    require(root.tag == 'test-run' and root.get('result') == 'Passed' and len(cases) == 1 and
            cases[0].get('fullname') == legacy.RENDER_TEST and cases[0].get('result') == 'Passed', 'Emission native case identity')
    outputs = cases[0].findall('output')
    require(len(outputs) == 1 and not list(outputs[0]), 'Emission case output count/shape')
    text = outputs[0].text or ''
    require(len(text.encode('utf-8')) <= 2*1024**2, 'Emission case output exceeds bound')
    records = []
    for line in text.splitlines():
        if LIFECYCLE_MARKER.strip() in line or OBSERVATION_MARKER.strip() in line:
            prefix = LIFECYCLE_MARKER if line.startswith(LIFECYCLE_MARKER) else OBSERVATION_MARKER
            require(line.startswith(prefix) and len(line.encode('utf-8')) <= 8192, 'Emission marker format/bound')
            records.append((prefix, unique_json(line[len(prefix):])))
    require(len(records) == 3 and [p for p,_ in records] == [LIFECYCLE_MARKER,OBSERVATION_MARKER,OBSERVATION_MARKER],
            'Emission exact three ordered markers required')
    authored = validate_lifecycle(records[0][1])
    observations = {phase:validate_observation(records[index][1], phase) for index,phase in enumerate(('author-reload','postcapture'),1)}
    require(all(row['emissionColor'] == authored['afterEmissionColor'] for row in observations.values()), 'Emission native phase HDR differs')
    require(source.sha(matches[0]) == native_sha, 'Emission XML changed during read')
    return native_sha, authored, observations


def validate_identity(row):
    exact(row, IDENTITY_KEYS, 'identity')
    require(row['repository'] == source.REPOSITORY and row['editorVersion'] == source.VERSION and
            type(row['commit']) is str and re.fullmatch('[a-f0-9]{40}',row['commit']) and
            type(row['runId']) is str and re.fullmatch('[1-9][0-9]{0,19}',row['runId']) and row['runAttempt'] == '1', 'Emission run identity')
    digest(row['exportManifestSha256']); digest(row['sourceStateSha256'])


def serialized_material(path):
    path=source.safe(path); require(0 < path.stat().st_size <= 65536, 'Emission material byte bound')
    raw=path.read_bytes()
    semantic = audit.material_semantics(raw)
    require(semantic.get('supported') is True, 'Emission unsupported typed material')
    fields = semantic['fields']; prefix = '21:2100000:'
    require(fields.get(prefix+'m_LightmapFlags') == 2 and fields.get(prefix+'m_ValidKeywords') == ['_EMISSION'], 'Emission serialized GI/keyword')
    emission = color(fields.get(prefix+'_EmissionColor')); base = color(fields.get(prefix+'_BaseColor'),BASE_COLOR)
    shader = fields.get(prefix+'m_Shader'); exact(shader, {'fileID','guid','type'}, 'serialized shader')
    require(shader['fileID'] == 4800000 and shader['type'] == 3 and type(shader['guid']) is str and
            re.fullmatch('[a-f0-9]{32}',shader['guid']), 'Emission serialized shader identity')
    return dict(giFlags=2,validKeywords=['_EMISSION'],emissionColor=emission,baseColor=base,shader=shader,
                unrecognizedBytesSha256=semantic['unrecognizedBytesSha256'])


def inspect_pngs(stage):
    expected = legacy.IMAGES | v4.EXTRA_IMAGES
    actual = {p.relative_to(stage).as_posix() for p in stage.rglob('*.png')}
    require(actual == expected and len(expected) == 20, 'Emission original twenty PNG closure')
    rows = []
    for name in sorted(expected):
        path = stage/name; legacy.inspect_png(path)
        rows.append(dict(file=name,sha256=source.sha(path),size=path.stat().st_size))
    return rows


def bundle_closure(stage, receipt, with_proof):
    require(stage.is_dir() and not stage.is_symlink() and not any(p.is_symlink() for p in stage.parents) and
            not any(p.is_symlink() for p in stage.rglob('*')), 'Emission linked bundle')
    generated = receipt.get('generated')
    require(type(generated) is list and 243 < len(generated) < 400, 'Emission generated closure count')
    names = set()
    for row in generated:
        exact(row, {'path','sha256','size'}, 'generated row')
        name = row['path']; require(type(name) is str and name not in names and len(name) < 256 and
            name.startswith(legacy.GENERATED) and '..' not in Path(name).parts and '\\' not in name and
            Path(name).as_posix() == name and re.fullmatch(r'[A-Za-z0-9_./-]+',name), 'Emission generated path')
        digest(row['sha256']); integer(row['size'],1,40*1024**2,'generated size')
        require(source.sha(stage/'generated'/name) == row['sha256'] and (stage/'generated'/name).stat().st_size == row['size'], 'Emission generated readback')
        names.add(name)
    require({TARGET,TARGET+'.meta'} <= names, 'Emission generated target missing')
    expected = {'generated/'+name for name in names} | legacy.IMAGES | v4.EXTRA_IMAGES | legacy.CLEARANCE_FILES | {
        'receipt.json','SHA256SUMS.json',r4.REPORT,'environment-v4-receipts.json'}
    if with_proof: expected.add(PROOF)
    actual = {p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
    require(actual == expected, 'Emission whole bundle closed set')


def validate_phase_files(rows, authored, stage):
    exact(rows, {'material','meta'}, 'phase files')
    for kind, path, expected_sha in (('material',TARGET,authored['savedSha256']),('meta',TARGET+'.meta',authored['metaSha256'])):
        exact(rows[kind], set(PHASES), 'phase file stages')
        for phase in PHASES:
            row=rows[kind][phase]; exact(row, {'sha256','size'}, 'phase fingerprint')
            digest(row['sha256']); integer(row['size'],1,65536,'phase size')
            require(row['sha256'] == expected_sha and source.sha(stage/'generated'/path) == expected_sha and
                    (stage/'generated'/path).stat().st_size == row['size'], 'Emission three-phase/packaged hash mismatch')


def validate_loaded(rows):
    exact(rows, {'freeze','postcapture','postexitObservable'}, 'audit objects')
    require(rows['postexitObservable'] is False, 'Emission fabricated postexit loaded objects')
    for phase in ('freeze','postcapture'):
        objects=rows[phase]; require(type(objects) is list and len(objects) <= 32, 'Emission audit object bound')
        seen=set(); material_count=0
        for row in objects:
            exact(row, {'objectType','localFileId','hasLocalFileId','isDirty'}, 'audit object')
            require(row['objectType'] in OBJECT_TYPES and type(row['hasLocalFileId']) is bool and row['isDirty'] is False, 'Emission audit dirty/unknown object')
            integer(row['localFileId'],-2**63,2**63-1,'local file ID')
            require(row['hasLocalFileId'] or row['localFileId'] == 0, 'Emission audit missing local identity')
            key=(row['objectType'],row['localFileId'],row['hasLocalFileId']); require(key not in seen,'Emission duplicate audit object'); seen.add(key)
            if row['objectType'] == 'UnityEngine.Material':
                require(row['hasLocalFileId'] and row['localFileId'] == 2100000, 'Emission material local identity')
                material_count += 1
        require(material_count <= 1, 'Emission duplicate observed Material')
        # Scene restoration may unload the material before either audit snapshot. Empty is
        # reported honestly; the earlier scene observation independently requires a loaded material.


def validate_exported_proof(stage):
    """Pure exported-bundle validation; no native XML, project, environment, or source-tree read."""
    stage=Path(stage); r4.verify_manifest(stage)
    path=source.safe(stage/PROOF); require(path.stat().st_size <= MAX_PROOF,'Emission proof bound')
    proof=unique_json(path.read_text()); exact(proof, PROOF_KEYS, 'proof')
    require(proof['schema'] == SCHEMA and proof['producerRevision'] == REVISION and proof['status'] == STATUS and
            proof['scope'] == SCOPE and proof['target'] == TARGET and proof['authoredGiSemantics'] == GI_DISCLOSURE and
            proof['visualAcceptance'] == 'NOT_ACCEPTED' and proof['gameplayIntegration'] == 'NOT_RUN','Emission proof scope/disclosure')
    require(all(type(proof['authoredGiSemantics'][k]) is type(v) for k,v in GI_DISCLOSURE.items()), 'Emission disclosure scalar types')
    validate_identity(proof['identity']); authored=validate_lifecycle(proof['authorLifecycle'])
    exact(proof['observations'], {'author-reload','postcapture'}, 'observations')
    for phase,row in proof['observations'].items():
        validate_observation(row,phase)
        require(row['emissionColor'] == authored['afterEmissionColor'],'Emission native phase HDR differs')
    receipt=source.read_json(stage/'receipt.json'); bundle_closure(stage,receipt,True)
    require(receipt.get('schema') == r4.SCHEMA and receipt.get('candidateRevision') == 'R4_DIFFUSE_ONLY' and
            receipt.get('protectedTrackedFilesUnchanged') is True and all(receipt.get(k) == v for k,v in proof['identity'].items()), 'Emission retained receipt/source identity')
    native=proof['native']; exact(native,{'test','xmlSha256','caseResult','caseCount','markerSource'},'native identity')
    require(native['test'] == legacy.RENDER_TEST and native['xmlSha256'] == receipt.get('nativeRenderXmlSha256') and
            native['caseResult'] == 'Passed' and type(native['caseCount']) is int and native['caseCount'] == 1 and
            native['markerSource'] == 'UNIQUE_PASSED_NUNIT_CASE_OUTPUT', 'Emission native identity mismatch')
    digest(native['xmlSha256'])
    expected_subproof=dict(receiptSchema=r4.SCHEMA,candidateRevision='R4_DIFFUSE_ONLY',appliesOnlyTo=list(r4.MATERIALS),
        wholePackageDiffuseOnly=False,receiptSha256=source.sha(stage/'receipt.json'),correctedTerrainReportSha256=source.sha(stage/r4.REPORT))
    require(type(proof['legacyTerrainSubproof']) is dict and proof['legacyTerrainSubproof'].get('wholePackageDiffuseOnly') is False and
            proof['legacyTerrainSubproof'] == expected_subproof and
            expected_subproof['correctedTerrainReportSha256'] == receipt.get('correctedTerrainNativeReportSha256'), 'Emission sand subproof scope/hash')
    validate_phase_files(proof['phaseFiles'],authored,stage); validate_loaded(proof['auditLoadedObjects'])
    material=proof['serializedMaterial']
    exact(material, {'giFlags','validKeywords','emissionColor','baseColor','shader','unrecognizedBytesSha256'}, 'typed material')
    color(material['emissionColor']); color(material['baseColor'],BASE_COLOR); digest(material['unrecognizedBytesSha256'])
    exact(material['shader'], {'fileID','guid','type'}, 'typed shader')
    require(type(material['giFlags']) is int and type(material['shader']['fileID']) is int and type(material['shader']['type']) is int and
            material == serialized_material(stage/'generated'/TARGET), 'Emission packaged typed material differs')
    require(proof['images'] == inspect_pngs(stage), 'Emission packaged PNG proof differs')
    return proof


def build_proof(stage):
    receipt=source.read_json(stage/'receipt.json'); bundle_closure(stage,receipt,False)
    raw_identity=source.identity(); identity={k:raw_identity[k] for k in IDENTITY_KEYS}; validate_identity(identity)
    require(all(receipt.get(k) == v for k,v in identity.items()),'Emission source identity differs from strict package')
    native, authored, observations=native_markers(source.TASK/'artifacts/environment')
    require(native == receipt.get('nativeRenderXmlSha256'), 'Emission native XML differs from strict package')
    measured=audit.sanitized_audit(source.PROJECT,'success')
    phase_files={}
    for kind,path in (('material',TARGET),('meta',TARGET+'.meta')):
        phases={}
        for phase in PHASES:
            matches=[r for r in measured['phases'][phase] if r['path'] == path]
            require(len(matches) == 1 and matches[0]['present'] is True,'Emission measured target phase missing')
            phases[phase]={k:matches[0][k] for k in ('sha256','size')}
        phase_files[kind]=phases
    loaded={phase:[{k:r[k] for k in ('objectType','localFileId','hasLocalFileId','isDirty')}
                   for r in measured['loadedObjects'][phase] if r['path'] == TARGET] for phase in ('freeze','postcapture')}
    loaded['postexitObservable']=False
    proof=dict(schema=SCHEMA,producerRevision=REVISION,status=STATUS,scope=SCOPE,identity=identity,
        native=dict(test=legacy.RENDER_TEST,xmlSha256=native,caseResult='Passed',caseCount=1,markerSource='UNIQUE_PASSED_NUNIT_CASE_OUTPUT'),
        authoredGiSemantics=GI_DISCLOSURE,legacyTerrainSubproof=dict(receiptSchema=r4.SCHEMA,candidateRevision='R4_DIFFUSE_ONLY',
            appliesOnlyTo=list(r4.MATERIALS),wholePackageDiffuseOnly=False,receiptSha256=source.sha(stage/'receipt.json'),
            correctedTerrainReportSha256=source.sha(stage/r4.REPORT)),target=TARGET,authorLifecycle=authored,observations=observations,
        phaseFiles=phase_files,auditLoadedObjects=loaded,serializedMaterial=serialized_material(stage/'generated'/TARGET),images=inspect_pngs(stage),
        visualAcceptance='NOT_ACCEPTED',gameplayIntegration='NOT_RUN')
    validate_phase_files(phase_files,authored,stage); validate_loaded(loaded)
    return proof


def package():
    destination=r4.OUT
    require(not destination.exists() and not destination.is_symlink(),'Refuse stale emission output')
    require(not any(p.is_symlink() for p in destination.parents),'Linked emission output ancestor')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.environment-emission-',dir=destination.parent) as temporary:
        stage=Path(temporary)/'bundle'
        try:
            r4.OUT=stage
            audit.package()  # Original real postexit capture and complete strict R4 package, unchanged.
        finally:
            r4.OUT=destination
        r4.verify_manifest(stage)
        original={p.relative_to(stage).as_posix():source.sha(p) for p in stage.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.json'}
        proof=build_proof(stage)
        text=json.dumps(proof,indent=2,allow_nan=False)+'\n'; require(len(text.encode()) <= MAX_PROOF,'Emission proof exceeds bound')
        (stage/PROOF).write_text(text)
        require(unique_json(source.safe(stage/PROOF).read_text()) == proof,'Emission proof write/readback failed')
        (stage/'SHA256SUMS.json').unlink(); v4.write_manifest(stage)
        require(validate_exported_proof(stage) == proof,'Emission exported proof readback failed')
        require(all(source.sha(stage/name) == sha for name,sha in original.items()),'Emission wrapper changed retained payload')
        require(not destination.exists() and not destination.is_symlink(),'Emission output appeared during packaging')
        stage.rename(destination)
    print('Whole producer package: single warm-beacon BakedEmissive lifecycle proof plus retained R4 sand subproof; no art/gameplay acceptance or GI bake.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('mode',choices=('package','diagnose'))
    parser.add_argument('--package-outcome',choices=('success','failure')); args=parser.parse_args()
    if args.mode == 'diagnose':
        if args.package_outcome is None: parser.error('--package-outcome is required for diagnose')
        audit.diagnose(args.package_outcome)
    else:
        if args.package_outcome is not None: parser.error('--package-outcome is only valid with diagnose')
        package()
