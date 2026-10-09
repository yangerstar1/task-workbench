#!/usr/bin/env python3
"""Saved corrected-terrain proof layered over the unchanged V4 twenty-camera gates.
Validator unit fixtures are never native evidence or art/gameplay acceptance.
"""
import argparse
import base64
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
import environment_v4_evidence as v4
import environment_diffuse_comparison_evidence as comparison

source = v4.source
require = source.require
CAPTURE = 'JourneyEvidence/environment-v4-r4'
REPORT = 'corrected-terrain-report.json'
OUT = source.TASK / 'evidence/environment-v4-r4'
PARTIAL = source.TASK / 'evidence/environment-v4-r4-unaccepted'
STATUS = 'CORRECTED_TERRAIN_SAVED_NOT_ART_OR_GAMEPLAY_ACCEPTANCE'
SCHEMA = 'desert-rv-environment-v4-r4-renderer-proof/v1'
CORRECTED = comparison.CORRECTED
CORRECTED_SHA = '4fe4e4e5745ce34d4f8eb9668e45a5fab1acf7f6c0baa96de45ae15ff98764a3'
CORRECTED_META_SHA = 'c90d8b8ae8da299cdd47af43312699c27861d72effc9a493c7b142526bd87dd3'
CORRECTED_GUID = 'd29d00d5224659788346ab661919f5ee'
ORIGINAL_GUID = 'a57ff6e7aa6a58ebaa3a2a37a4e9698f'
MATERIALS = tuple(v4.POLISH + '/Surface-' + name + '.mat' for name in ('Sand', 'Dune'))
ROLES = (('Ground-Sand', 'Sand'), ('ReliefEast-Dune', 'Dune'), ('ReliefWest-Dune', 'Dune'))
IMPORT_SETTINGS = dict(width=1024,height=1024,textureType=0,textureShape=1,filterMode=2,
    wrapU=0,wrapV=0,wrapW=0,anisoLevel=4,maxTextureSize=1024,textureCompression=1,alphaSource=0,
    sRGBTexture=True,mipmapEnabled=True,streamingMipmaps=True,isReadable=False,standaloneOverride=False,androidOverride=False)
REPORT_KEYS = {'schema','status','postCaptureImageCount','postCaptureVerified','allOtherGeneratedBytesPreserved',
               'correctedDiffuse','materials','terrainBindings','generatedFiles'}
MATERIAL_KEYS = {'path','originalSerializedBase64','originalSha256','savedSha256','baseMapAsset','baseMapSha256','mainTexAsset','mainTexSha256','onlyAlbedoReferencesChanged','saveImportCycles','secondSaveImportBytesStable','actual'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def one(pattern, text, label):
    matches = re.findall(pattern, text, re.M)
    require(len(matches) == 1, 'Missing/duplicate ' + label)
    return matches[0]


def guid(project, asset):
    return one(r'^guid: ([0-9a-f]{32})$', source.safe(project/(asset+'.meta')).read_text(), 'asset GUID')


def corrected_material_bytes(original):
    require(isinstance(original, bytes) and 0 < len(original) < 128*1024 and original.startswith(b'%YAML 1.1\n'), 'Invalid original material serialization')
    pattern = rb'(?m)^(    - _(BaseMap|MainTex):\r?\n        m_Texture: \{fileID: 2800000, guid: )' + ORIGINAL_GUID.encode() + rb'(, type: 3\})\r?$'
    matches=re.findall(pattern, original)
    require(len(matches)==2 and {m[1] for m in matches}=={b'BaseMap',b'MainTex'}, 'Exactly two original serialized albedo aliases required')
    return re.sub(pattern, lambda m: m.group(0).replace(ORIGINAL_GUID.encode(), CORRECTED_GUID.encode()), original)


def inspect_input(project):
    comparison.inspect_assets(project)
    require(source.sha(project/CORRECTED) == CORRECTED_SHA, 'Corrected diffuse source digest differs')
    require(guid(project,CORRECTED) == CORRECTED_GUID and guid(project,comparison.ORIGINAL) == ORIGINAL_GUID, 'Diffuse asset GUID differs')
    require(source.sha(project/(CORRECTED+'.meta'))==CORRECTED_META_SHA,'Corrected texture importer source bytes differ')
    return CORRECTED_META_SHA


def documents(path):
    text = source.safe(path).read_text()
    require(text.startswith('%YAML 1.1\n'), 'Scene must be Unity text serialization')
    rows = re.findall(r'^--- !u!(\d+) &(-?\d+)(?: stripped)?\r?\n(.*?)(?=^--- !u!|\Z)', text, re.M|re.S)
    require(rows and len({row[1] for row in rows}) == len(rows), 'Missing/duplicate serialized Unity object identity')
    return {identity:(int(kind),body) for kind,identity,body in rows}


def inspect_scene_bindings(project, region, scene_path):
    docs = documents(project/scene_path)
    material_guids = {name:guid(project, v4.POLISH+'/Surface-'+name+'.mat') for _,name in ROLES}
    binding_guid = guid(project, 'Assets/DesertRV/Runtime/RegionBinding.cs')
    bindings = [(identity,body) for identity,(kind,body) in docs.items() if kind == 114 and
                re.search(r'^  m_Script: \{fileID: 11500000, guid: '+binding_guid+r', type: 3\}$',body,re.M)]
    require(len(bindings)==1,'Exactly one saved RegionBinding required')
    binding_body=bindings[0][1]
    require(one(r'^  region: (\d+)$',binding_body,'region index')==str(region),'Serialized region mismatch')
    owner=one(r'^  m_GameObject: \{fileID: (-?\d+)\}$',binding_body,'region GameObject')
    roots=[identity for identity,(kind,body) in docs.items() if kind==4 and re.search(r'^  m_GameObject: \{fileID: '+owner+r'\}$',body,re.M)]
    require(len(roots)==1,'Exactly one binding root Transform required')
    terrain=[]
    for identity,(kind,body) in docs.items():
        if kind==23 and any(re.search(r'^  - \{fileID: 2100000, guid: '+value+r', type: 2\}$',body,re.M) for value in material_guids.values()):
            terrain.append((identity,body))
    require(len(terrain)==3,'Exactly three persisted terrain MeshRenderers per scene required')
    result=[]
    for role,material in ROLES:
        objects=[identity for identity,(kind,body) in docs.items() if kind==1 and re.search(r'^  m_Name: EnvironmentV4 '+re.escape(role)+r'$',body,re.M)]
        require(len(objects)==1,'Missing/duplicate saved terrain GameObject')
        owner=objects[0];obj=docs[owner][1]
        require(one(r'^  m_IsActive: (\d+)$',obj,'terrain active flag')=='1','Inactive saved terrain')
        def component(kind):
            matches=[(identity,body) for identity,(actual,body) in docs.items() if actual==kind and re.search(r'^  m_GameObject: \{fileID: '+owner+r'\}$',body,re.M)]
            require(len(matches)==1,'Missing/duplicate terrain component')
            require(re.search(r'^  - component: \{fileID: '+matches[0][0]+r'\}$',obj,re.M),'Terrain component absent from GameObject')
            return matches[0][1]
        transform,mesh,renderer=component(4),component(33),component(23)
        require(one(r'^  m_Father: \{fileID: (-?\d+)\}$',transform,'terrain parent')==roots[0],'Wrong terrain parent')
        require(one(r'^  m_Enabled: (\d+)$',renderer,'renderer enabled flag')=='1','Disabled saved terrain')
        mesh_path=v4.POLISH+'/R'+str(region)+'-'+role+'.asset';material_path=v4.POLISH+'/Surface-'+material+'.mat'
        require(one(r'^  m_Mesh: \{fileID: 4300000, guid: ([0-9a-f]{32}), type: 2\}$',mesh,'mesh asset')==guid(project,mesh_path),'Wrong saved terrain mesh binding')
        block=one(r'^  m_Materials:\n((?:  - .*\n)+)',renderer,'terrain material list')
        require(block=='  - {fileID: 2100000, guid: '+material_guids[material]+', type: 2}\n','Wrong saved terrain material binding')
        result.append(dict(region=region,objectName='EnvironmentV4 '+role,scenePath=scene_path,meshAsset=mesh_path,
                           materialAsset=material_path,baseMapAsset=CORRECTED,baseMapSha256=CORRECTED_SHA,mainTexAsset=CORRECTED,mainTexSha256=CORRECTED_SHA))
    return result


def inspect_corrected(project):
    directory=project/CAPTURE
    comparison.unlinked_directory(directory)
    require({p.name for p in directory.iterdir()}=={REPORT},'Unexpected R4 native evidence membership')
    report=source.read_json(directory/REPORT)
    require(isinstance(report,dict) and set(report)==REPORT_KEYS,'Wrong R4 report fields')
    require(type(report['schema']) is int and report['schema']==1 and report['status']==STATUS,'Wrong R4 scope/schema')
    require(report['postCaptureVerified'] is True and report['allOtherGeneratedBytesPreserved'] is True and
            type(report['postCaptureImageCount']) is int and report['postCaptureImageCount']==20,'Missing post-twenty-capture saved-asset verification')
    meta_sha=inspect_input(project)
    expected=dict(IMPORT_SETTINGS,assetPath=CORRECTED,sha256=CORRECTED_SHA,metaSha256=meta_sha,guid=CORRECTED_GUID)
    imported=report['correctedDiffuse']
    require(isinstance(imported,dict) and imported==expected and all(type(imported[k]) is type(v) for k,v in expected.items()),'Actual corrected texture/importer identity differs')
    names=set(v4.collect_generated(project,v4.load_contract()))
    rows=report['generatedFiles']
    require(isinstance(rows,list) and len(rows)==len(names),'Wrong frozen generated count')
    frozen={}
    for row in rows:
        require(isinstance(row,dict) and set(row)=={'path','beforeSha256','afterSha256'},'Wrong frozen generated fields')
        name=row['path'];require(name in names and name not in frozen,'Unknown/duplicate frozen generated path')
        require(all(isinstance(row[k],str) and re.fullmatch('[0-9a-f]{64}',row[k]) for k in ('beforeSha256','afterSha256')),'Invalid frozen digest')
        require(source.sha(project/name)==row['afterSha256'],'Frozen generated bytes changed')
        require((row['beforeSha256']!=row['afterSha256'])==(name in MATERIALS),'Only two saved BaseMap material payloads may differ')
        frozen[name]=row
    mats=report['materials'];require(isinstance(mats,list) and len(mats)==2,'Exactly two corrected material records required')
    seen=set()
    for mat in mats:
        require(isinstance(mat,dict) and set(mat)==MATERIAL_KEYS,'Wrong corrected material fields')
        path=mat['path'];require(path in MATERIALS and path not in seen,'Wrong/duplicate corrected material identity');seen.add(path)
        require(mat['onlyAlbedoReferencesChanged'] is True and mat['secondSaveImportBytesStable'] is True and type(mat['saveImportCycles']) is int and mat['saveImportCycles']==2 and
                mat['baseMapAsset']==mat['mainTexAsset']==CORRECTED and mat['baseMapSha256']==mat['mainTexSha256']==CORRECTED_SHA,'Wrong actual corrected material BaseMap')
        encoded=mat['originalSerializedBase64'];require(isinstance(encoded,str) and len(encoded)<180000,'Oversized original material fixture')
        try:original=base64.b64decode(encoded,validate=True)
        except (ValueError,TypeError) as error:raise ValueError('Invalid original material bytes') from error
        require(digest(original)==mat['originalSha256']==frozen[path]['beforeSha256'],'Original material snapshot digest mismatch')
        current=source.safe(project/path).read_bytes()
        require(corrected_material_bytes(original)==current,'Saved material changed beyond the two albedo-alias GUIDs')
        require(digest(current)==mat['savedSha256']==frozen[path]['afterSha256'],'Saved material digest mismatch')
        require(mat['actual']['name']==Path(path).stem,'Actual material name differs from saved file')
    comparison.validate_materials([mat['actual'] for mat in mats],CORRECTED)
    expected_bindings=[]
    for region,name in enumerate(v4.legacy.REGIONS,1):
        expected_bindings.extend(inspect_scene_bindings(project,region,v4.legacy.GENERATED+'/'+name+'.unity'))
    require(report['terrainBindings']==expected_bindings,'Actual reported and independently serialized three-region bindings differ')
    return report


def before():
    inspect_input(source.PROJECT)
    v4.before()


def verify_manifest(stage):
    rows=source.read_json(stage/'SHA256SUMS.json')
    actual={p.relative_to(stage).as_posix():p for p in stage.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json'}
    require(isinstance(rows,list) and len(rows)==len(actual),'R4 hash manifest count mismatch')
    seen=set()
    for row in rows:
        require(isinstance(row,dict) and set(row)=={'path','sha256','size'},'R4 manifest fields')
        name=row['path'];require(name in actual and name not in seen,'R4 manifest unknown/duplicate file');seen.add(name)
        require(source.sha(actual[name])==row['sha256'] and actual[name].stat().st_size==row['size'],'R4 artifact readback failed')


def package():
    _package(False)


def partial():
    # The retained v4.partial independently requires an actual nonempty protected-source difference.
    _package(True)


def _package(unaccepted):
    destination=PARTIAL if unaccepted else OUT
    require(not destination.exists() and not destination.is_symlink(),'Refuse stale R4 output')
    corrected=inspect_corrected(source.PROJECT)
    require(not any(p.is_symlink() for p in destination.parents),'Linked R4 output ancestor')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.environment-v4-r4-',dir=destination.parent) as temporary:
        stage=Path(temporary)/'bundle'
        attribute='PARTIAL' if unaccepted else 'OUT';prior=getattr(v4,attribute)
        try:
            setattr(v4,attribute,stage)
            (v4.partial if unaccepted else v4.package)()
        finally:setattr(v4,attribute,prior)
        receipt=source.read_json(stage/'receipt.json')
        receipt.update(schema=SCHEMA,candidateRevision='R4_DIFFUSE_ONLY',
            correctedDiffuseSha256=CORRECTED_SHA,correctionBaselineCommit='e40671685c2ff824e30e5709585407068d0c65fc',
            correctionComparisonRun='37977926436',correctedTerrainNativeReportSha256=source.sha(source.PROJECT/CAPTURE/REPORT))
        if unaccepted:
            # Keep the old failure artifact's restricted pixel/receipt set; no generated assets or baseline material bytes.
            receipt['correctedTerrain']=dict(status=corrected['status'],postCaptureVerified=True,postCaptureImageCount=20,
                correctedDiffuse=corrected['correctedDiffuse'],terrainBindings=corrected['terrainBindings'])
        else:
            receipt['correctedTerrain']=corrected
            for row in corrected['generatedFiles']:
                require(source.sha(stage/'generated'/row['path'])==row['afterSha256'],'Packaged generated bytes differ from frozen R4 proof')
            shutil.copyfile(source.PROJECT/CAPTURE/REPORT,stage/REPORT)
            require(source.read_json(stage/REPORT)==corrected and source.sha(stage/REPORT)==receipt['correctedTerrainNativeReportSha256'],'Corrected native report copy readback failed')
        (stage/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        require(source.read_json(stage/'receipt.json')==receipt,'R4 receipt readback failed')
        (stage/'SHA256SUMS.json').unlink();v4.write_manifest(stage);verify_manifest(stage)
        require(not destination.exists() and not destination.is_symlink(),'R4 output appeared during packaging')
        stage.rename(destination)
    print('R4 saved diffuse-only candidate and retained twenty-view proof packaged; art/gameplay acceptance NOT_RUN.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('before','package','partial'));args=parser.parse_args()
    {'before':before,'package':package,'partial':partial}[args.mode]()
