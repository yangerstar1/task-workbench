#!/usr/bin/env python3
"""Bounded source-bound offline reflection originals; no logs or free paths."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct

import visual_candidate_ci as visual

TASK = visual.TASK
SOURCE = TASK + '/unity/Assets/G3/Shop/Resources/G3/Shop/Reflections'
FILES = ('Day.exr', 'Day.exr.meta', 'Night.exr', 'Night.exr.meta', 'reflection-receipt.json')
EXR_LIMIT = 8 * 1024 * 1024
TEXT_LIMIT = 16 * 1024
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
require = visual.require


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_fixed(root, directory, name, limit):
    require(name in FILES, 'REFLECTION_FILE_REJECTED')
    path = root / directory / name
    require(path.resolve() == path.absolute(), 'REFLECTION_LINK_REJECTED')
    return visual.bounded.bounded_read(path, limit)


def exr_size(data):
    # OpenEXR's bounded typed header, not an image decoder. Unity's successful
    # Cubemap import and receipt provide the separate import/format check.
    require(len(data) >= 64 and data[:4] == b'\x76\x2f\x31\x01', 'REFLECTION_EXR_REJECTED')
    version = struct.unpack_from('<I', data, 4)[0]
    require(version & 255 == 2 and version & ~0x602 == 0, 'REFLECTION_EXR_VERSION_REJECTED')
    at = 8; attributes = {}
    def word():
        nonlocal at
        end = data.find(b'\0', at, min(len(data), at + 256, TEXT_LIMIT))
        require(end >= at, 'REFLECTION_EXR_HEADER_REJECTED')
        value = data[at:end]; at = end + 1
        return value
    while True:
        name = word()
        if not name: break
        require(name not in attributes and len(attributes) < 32, 'REFLECTION_EXR_HEADER_REJECTED')
        kind = word()
        require(at + 4 <= min(len(data), TEXT_LIMIT), 'REFLECTION_EXR_HEADER_REJECTED')
        size = struct.unpack_from('<I', data, at)[0]; at += 4
        require(at + size <= min(len(data), TEXT_LIMIT), 'REFLECTION_EXR_HEADER_REJECTED')
        attributes[name] = (kind, data[at:at + size]); at += size
    require(b'dataWindow' in attributes, 'REFLECTION_EXR_WINDOW_MISSING')
    kind, window = attributes[b'dataWindow']
    require(kind == b'box2i' and len(window) == 16, 'REFLECTION_EXR_WINDOW_REJECTED')
    x0,y0,x1,y1 = struct.unpack('<4i', window)
    require(x0 == y0 == 0 and x1 >= 0 and y1 >= 0, 'REFLECTION_EXR_WINDOW_REJECTED')
    return x1 + 1, y1 + 1


# Narrow generated TextureImporter YAML subset. Keys belong to exact scopes;
# repeated keys within a mapping are rejected, including identical duplicates.
# serializedVersion remains legal in distinct Unity nested mappings/list items.
META_NUMERIC = {
    'TextureImporter': set("serializedVersion isReadable streamingMipmaps streamingMipmapsPriority vTOnly ignoreMipmapLimit grayScaleToAlpha generateCubemap cubemapConvolution seamlessCubemap textureFormat maxTextureSize textureCompression nPOTScale lightmap compressionQuality spriteMode spriteExtrude spriteMeshType alignment spritePixelsToUnits spriteGenerateFallbackPhysicsShape alphaUsage alphaSource alphaIsTransparency spriteTessellationDetail textureType textureShape singleChannelComponent flipbookRows flipbookColumns maxTextureSizeSet compressionQualitySet textureFormatSet ignorePngGamma applyGammaDecoding swizzle cookieLightType pSDRemoveMatte".split()),
    'mipmaps': set("mipMapMode enableMipMap sRGBTexture linearTexture fadeOut borderMipMap mipMapsPreserveCoverage alphaTestReferenceValue mipMapFadeDistanceStart mipMapFadeDistanceEnd".split()),
    'bumpmap': set("convertToNormalMap externalNormalMap heightScale normalMapFilter flipGreenChannel".split()),
    'textureSettings': set("serializedVersion filterMode aniso mipBias wrapU wrapV wrapW".split()),
    'platformSettings': set("serializedVersion maxTextureSize resizeAlgorithm textureFormat textureCompression compressionQuality crunchedCompression allowsAlphaSplitting overridden ignorePlatformSupport androidETC2FallbackOverride forceMaximumCompressionQuality_BC6H_BC7".split()),
    'spriteSheet': {'serializedVersion','internalID'},
}
META_SECTIONS = {'mipmaps','bumpmap','textureSettings','platformSettings','spriteSheet'}
META_EMPTY = {'userData','assetBundleName','assetBundleVariant','mipmapLimitGroupName'}
META_PLATFORMS = {'DefaultTexturePlatform','Standalone','Android','iPhone','WebGL'}
NUMBER = r'-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?'


def validate_meta(data, trace=None):
    text = data.decode('utf-8'); lines = text.splitlines()
    require(len(lines) <= 256 and all(len(line) <= 512 for line in lines), 'REFLECTION_META_SIZE_REJECTED')
    seen = {}; section = None; sprite_child = None; root_owner = None; platform = -1; targets = set()
    for line in lines:
        if trace is not None:trace.meta('UNKNOWN','UNKNOWN')
        match = re.fullmatch(r'( *)(- )?([A-Za-z_][A-Za-z0-9_]*):[ ]*(.*)', line)
        require(match is not None, 'REFLECTION_META_LINE_REJECTED')
        if trace is not None:trace.meta('UNKNOWN',match[3])
        indent=len(match[1]); dash=match[2] is not None; key=match[3]; value=match[4].rstrip(' ')
        if indent > 0:
            require(root_owner == 'TextureImporter', 'REFLECTION_META_STRUCTURE_REJECTED')
        if indent == 0:
            require(not dash and key in {'fileFormatVersion','guid','TextureImporter'}, 'REFLECTION_META_ROOT_REJECTED')
            scope='root'; section=None; sprite_child=None; root_owner=key
        elif indent == 2 and dash:
            require(section == 'platformSettings' and key == 'serializedVersion', 'REFLECTION_META_LIST_REJECTED')
            platform+=1; require(platform < 8, 'REFLECTION_META_LIST_REJECTED'); scope='platformSettings:'+str(platform)
        elif indent == 2:
            require(not dash and ('root','TextureImporter') in seen, 'REFLECTION_META_STRUCTURE_REJECTED')
            scope='TextureImporter'; section=key if key in META_SECTIONS else None; sprite_child=None
        elif indent == 4:
            require(not dash and section in META_SECTIONS, 'REFLECTION_META_STRUCTURE_REJECTED')
            require(section != 'platformSettings' or platform >= 0, 'REFLECTION_META_LIST_REJECTED')
            scope=section+':'+str(platform) if section == 'platformSettings' else section
            sprite_child=key if section=='spriteSheet' and key=='spriteCustomMetadata' else None
        elif indent == 6:
            require(not dash and section=='spriteSheet' and sprite_child=='spriteCustomMetadata', 'REFLECTION_META_STRUCTURE_REJECTED')
            scope='spriteCustomMetadata'
        else:
            require(False, 'REFLECTION_META_STRUCTURE_REJECTED')
        if trace is not None:trace.meta(scope,key)
        location=(scope,key);require(location not in seen, 'REFLECTION_META_DUPLICATE_KEY');seen[location]=value
        kind=scope.split(':')[0]
        if kind == 'root':
            ok=(key=='fileFormatVersion' and value=='2') or (key=='guid' and re.fullmatch(r'[0-9a-f]{32}',value)) or (key=='TextureImporter' and value=='')
        elif key in META_NUMERIC.get(kind,set()):
            ok=re.fullmatch(NUMBER,value) is not None and math.isfinite(float(value))
        elif kind=='TextureImporter' and key in META_SECTIONS:
            ok=value==''
        elif kind=='TextureImporter' and key in META_EMPTY:
            ok=value==''
        elif kind=='TextureImporter' and key in {'internalIDToNameTable','externalObjects'}:
            ok=value==('[]' if key=='internalIDToNameTable' else '{}')
        elif kind=='TextureImporter' and key in {'spritePivot','spriteBorder'}:
            axes=('x','y') if key=='spritePivot' else ('x','y','z','w')
            pattern=r'\{' + ', '.join(axis+': ('+NUMBER+')' for axis in axes) + r'\}'
            vector=re.fullmatch(pattern,value);ok=vector is not None and all(math.isfinite(float(v)) for v in vector.groups())
        elif kind=='platformSettings' and key=='buildTarget':
            ok=value in META_PLATFORMS and value not in targets;targets.add(value)
        elif kind=='spriteSheet' and key in {'sprites','outline','physicsShape','bones','vertices','edges','weights','secondaryTextures'}:
            ok=value=='[]'
        elif kind=='spriteSheet' and key in {'customData','spriteCustomMetadata'}:ok=value==''
        elif kind=='spriteCustomMetadata' and key=='entries':ok=value=='[]'
        elif kind=='spriteSheet' and key=='indices':ok=value in ('','[]')
        elif kind=='spriteSheet' and key=='nameFileIdTable':ok=value=='{}'
        elif kind=='spriteSheet' and key=='spriteID':
            # Empty ID is Unity's non-sprite cubemap default. The mandatory
            # import contract below still requires textureShape == 2.
            ok=value=='' or re.fullmatch(r'[0-9a-f]{32}',value) is not None
        else:ok=False
        require(ok, 'REFLECTION_META_FIELD_OR_VALUE_REJECTED')
    if ('spriteSheet','spriteCustomMetadata') in seen:
        require(seen.get(('spriteCustomMetadata','entries'))=='[]', 'REFLECTION_META_STRUCTURE_REJECTED')
    required={('root','fileFormatVersion'):'2',('root','TextureImporter'):'',('TextureImporter','textureShape'):'2',('mipmaps','sRGBTexture'):'0',('mipmaps','enableMipMap'):'1'}
    require(('root','guid') in seen and all(seen.get(key)==value for key,value in required.items()), 'REFLECTION_META_IMPORT_REJECTED')
    for n in range(platform+1):require(('platformSettings:'+str(n),'buildTarget') in seen, 'REFLECTION_META_PLATFORM_REJECTED')


def unique_json_object(pairs):
    result={}
    for key,value in pairs:
        require(key not in result, 'REFLECTION_JSON_DUPLICATE_KEY');result[key]=value
    return result


def load_receipt(raw):
    return json.loads(raw,object_pairs_hook=unique_json_object)


SHOP = 'Assets/G3/Shop/Resources/G3/Shop'
RECIPE = 'G3_SHOP_STATIC_REFLECTION_V2'
GUIDS = {'day': 'b90a2a9e9f0d4c1bab2f613e26d9c771', 'night': 'a54ec87d23ac49ea83e7cf7bad94381a'}
RECIPE_SOURCES = ('Assets/G3/Interaction/G3ShopEnvironment.cs', 'Assets/G3/Editor/G3ShopReflectionBaker.cs',
                  'Assets/G3/Interaction/G3ContactOcclusionFeature.cs',
                  'Assets/G3/Interaction/G3ContactOcclusionFeature.cs.meta',
                  'Assets/G3/Editor/G3ShopArtImporter.cs', 'Assets/G3/Editor/G3Build.cs',
                  'Packages/manifest.json', 'Packages/packages-lock.json')
DEPENDENCIES = (SHOP + '/LotteryShop_Runtime.prefab', SHOP + '/G3VisualPipeline.asset')


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def source_digest(root, receipt):
    unity = root / TASK / 'unity'; shop = unity / SHOP
    require(shop.is_dir() and shop.resolve() == shop.absolute(), 'REFLECTION_INPUT_DIRECTORY_REJECTED')
    files = set(RECIPE_SOURCES)
    for path in shop.rglob('*'):
        require(not path.is_symlink(), 'REFLECTION_INPUT_LINK_REJECTED')
        if path.is_file():
            rel = path.relative_to(unity).as_posix()
            if not rel.startswith(SHOP + '/Reflections/') and rel != SHOP + '/Reflections.meta': files.add(rel)
    require(len(files) <= 2048 and all((unity / path).is_file() for path in DEPENDENCIES), 'REFLECTION_INPUT_SET_REJECTED')
    parts = [RECIPE + '\n' + receipt['unityVersion'] + '\n' + receipt['colorSpace'] + '\n']; total = 0
    for rel in sorted(files):
        require(not any(c in rel for c in '\r\n|') and (unity / rel).resolve() == (unity / rel).absolute(), 'REFLECTION_INPUT_PATH_REJECTED')
        data = visual.bounded.bounded_read(unity / rel, 64 * 1024 * 1024); total += len(data)
        require(total <= 256 * 1024 * 1024, 'REFLECTION_INPUT_BYTES_REJECTED')
        parts.append(rel + '|' + digest(data) + '\n')
    for path, key in zip(DEPENDENCIES, ('runtimeDependencyHash', 'pipelineDependencyHash')):
        parts.append(path + '|' + receipt[key] + '\n')
    return digest(''.join(parts).encode('utf-8'))


def validate_receipt(receipt, ident):
    fields = {'schemaVersion','status','recipe','sourceDigest','sourceCommit','runId','runAttempt','unityVersion','day','night',
              'colorSpace','runtimeDependencyHash','pipelineDependencyHash','captureRenderers','captureTriangles'}
    require(isinstance(receipt, dict) and set(receipt) == fields, 'REFLECTION_RECEIPT_FIELDS_REJECTED')
    require(type(receipt['schemaVersion']) is int and receipt['schemaVersion'] == 1 and receipt['status'] == 'COMPLETE_BAKED_STATIC_REFLECTIONS' and receipt['recipe'] == RECIPE, 'REFLECTION_COMPLETENESS_REJECTED')
    for key in ('sourceCommit','runId','runAttempt'):
        require(receipt[key] == ident[key], 'REFLECTION_IDENTITY_REJECTED')
    require(receipt['unityVersion'] == '6000.3.19f1' and receipt['colorSpace'] == 'Gamma', 'REFLECTION_RECIPE_REJECTED')
    require(integer(receipt['captureRenderers'],1,4096) and integer(receipt['captureTriangles'],1,2000000), 'REFLECTION_CAPTURE_GEOMETRY_REJECTED')
    require(isinstance(receipt['sourceDigest'], str) and HEX64.fullmatch(receipt['sourceDigest']), 'REFLECTION_SOURCE_DIGEST_REJECTED')
    for key in ('runtimeDependencyHash','pipelineDependencyHash'):
        require(isinstance(receipt[key], str) and re.fullmatch(r'[0-9a-f]{32}', receipt[key]), 'REFLECTION_DEPENDENCY_REJECTED')
    for key, file in (('day','Day.exr'),('night','Night.exr')):
        value = receipt[key]
        require(isinstance(value, dict) and set(value) == {'file','sha256','metaSha256','metaGuid','format','shape','bytes','metaBytes','sourceWidth','sourceHeight','faceSize','mipCount','linear','specular','pixelSampleCount','maxChannelRange'}, 'REFLECTION_TEXTURE_FIELDS_REJECTED')
        require(value['file'] == file and value['metaGuid'] == GUIDS[key] and value['format'] == 'RGBAHalf' and value['shape'] == 'Cube', 'REFLECTION_TEXTURE_IDENTITY_REJECTED')
        require(type(value['faceSize']) is int and value['faceSize'] == 128 and type(value['mipCount']) is int and value['mipCount'] == 8 and value['linear'] is True and value['specular'] is True, 'REFLECTION_IMPORT_REJECTED')
        require(integer(value['pixelSampleCount'],98304,98304) and type(value['maxChannelRange']) in (int,float) and math.isfinite(value['maxChannelRange']) and .01 < value['maxChannelRange'] <= 65504, 'REFLECTION_BACKGROUND_ONLY_REJECTED')
        for field in ('sha256','metaSha256'):
            require(isinstance(value[field], str) and HEX64.fullmatch(value[field]), 'REFLECTION_HASH_REJECTED')
        require(integer(value['bytes'],64,EXR_LIMIT) and integer(value['metaBytes'],1,TEXT_LIMIT) and integer(value['sourceWidth'],128,2048) and integer(value['sourceHeight'],128,2048), 'REFLECTION_TEXTURE_SIZE_REJECTED')
    return receipt


def export_reflections(root, trace=None):
    def mark(stage,role="NONE"):
        if trace is not None:trace.stage=stage;trace.fileRole=role;trace.metaScope='NONE';trace.metaField='NONE'
    mark("DESTINATION")
    dest = visual.outdir(root) / 'reflections'
    require(dest.resolve() == dest.absolute(), 'REFLECTION_DESTINATION_REJECTED')
    # Clear only these five previous exported files, so a failed revalidation
    # cannot upload a stale successful set. No project assets are removed here.
    for name in FILES:
        path = dest / name
        if path.exists() or path.is_symlink():
            require(path.is_file() and not path.is_symlink(), 'REFLECTION_STALE_OUTPUT_REJECTED'); path.unlink()
    mark("IDENTITY")
    ident = visual.identity(root)
    require(ident['runId'] == os.environ.get('GITHUB_RUN_ID') and ident['runAttempt'] == os.environ.get('GITHUB_RUN_ATTEMPT') and visual.HEX40.fullmatch(ident.get('reviewedCandidateCommit','')), 'REFLECTION_RUN_IDENTITY_REJECTED')
    if trace is not None:trace.bind(ident)
    mark('RECEIPT_READ','RECEIPT')
    raw = read_fixed(root,SOURCE,'reflection-receipt.json',TEXT_LIMIT)
    mark('RECEIPT_VALIDATE','RECEIPT')
    receipt = validate_receipt(load_receipt(raw),ident)
    mark('SOURCE_DIGEST','RECEIPT')
    require(source_digest(root,receipt) == receipt['sourceDigest'], 'REFLECTION_SOURCE_INPUT_CHANGED')
    originals = {'reflection-receipt.json': raw}
    for key in ('day','night'):
        mark('ORIGINAL_READ',key.upper())
        value=receipt[key]; name=value['file']
        data=read_fixed(root,SOURCE,name,EXR_LIMIT); meta=read_fixed(root,SOURCE,name+'.meta',TEXT_LIMIT)
        mark('ORIGINAL_HASH',key.upper())
        require(len(data)==value['bytes'] and digest(data)==value['sha256'] and len(meta)==value['metaBytes'] and digest(meta)==value['metaSha256'], 'REFLECTION_ORIGINAL_HASH_REJECTED')
        mark('EXR_HEADER',key.upper())
        require(exr_size(data)==(value['sourceWidth'],value['sourceHeight']), 'REFLECTION_EXR_DIMENSIONS_REJECTED')
        mark('META_VALIDATE',key.upper())
        validate_meta(meta,trace)
        mark('META_GUID',key.upper())
        require(re.findall(r'^guid: ([0-9a-f]{32})$',meta.decode('utf-8'),re.M)==[value['metaGuid']], 'REFLECTION_META_GUID_REJECTED')
        originals[name]=data; originals[name+'.meta']=meta
    mark('EXPORT_COPY')
    dest.mkdir(parents=True,exist_ok=True)
    for name in FILES:(dest/name).write_bytes(originals[name])
    mark('COMPLETE')
    print('SOURCE_BOUND_REFLECTION_ORIGINALS_VERIFIED')


DIAGNOSTIC_NAME = 'reflection-export-diagnostic.json'
DIAGNOSTIC_SCOPE = 'REFLECTION_EXPORT_DIAGNOSTIC_NOT_NATIVE_OR_VISUAL_PASS'
DIAGNOSTIC_CODES = frozenset(['REFLECTION_BACKGROUND_ONLY_REJECTED', 'REFLECTION_BAKE_EVIDENCE_REJECTED', 'REFLECTION_CAPTURE_GEOMETRY_REJECTED', 'REFLECTION_COMPLETENESS_REJECTED', 'REFLECTION_DEPENDENCY_REJECTED', 'REFLECTION_DESTINATION_REJECTED', 'REFLECTION_EXR_DIMENSIONS_REJECTED', 'REFLECTION_EXR_HEADER_REJECTED', 'REFLECTION_EXR_REJECTED', 'REFLECTION_EXR_VERSION_REJECTED', 'REFLECTION_EXR_WINDOW_MISSING', 'REFLECTION_EXR_WINDOW_REJECTED', 'REFLECTION_FILE_REJECTED', 'REFLECTION_HASH_REJECTED', 'REFLECTION_IDENTITY_REJECTED', 'REFLECTION_IMPORT_REJECTED', 'REFLECTION_INPUT_BYTES_REJECTED', 'REFLECTION_INPUT_DIRECTORY_REJECTED', 'REFLECTION_INPUT_LINK_REJECTED', 'REFLECTION_INPUT_PATH_REJECTED', 'REFLECTION_INPUT_SET_REJECTED', 'REFLECTION_JSON_DUPLICATE_KEY', 'REFLECTION_LINK_REJECTED', 'REFLECTION_META_DUPLICATE_KEY', 'REFLECTION_META_FIELD_OR_VALUE_REJECTED', 'REFLECTION_META_GUID_REJECTED', 'REFLECTION_META_IMPORT_REJECTED', 'REFLECTION_META_LINE_REJECTED', 'REFLECTION_META_LIST_REJECTED', 'REFLECTION_META_PLATFORM_REJECTED', 'REFLECTION_META_ROOT_REJECTED', 'REFLECTION_META_SIZE_REJECTED', 'REFLECTION_META_STRUCTURE_REJECTED', 'REFLECTION_ORIGINAL_HASH_REJECTED', 'REFLECTION_RECEIPT_FIELDS_REJECTED', 'REFLECTION_RECIPE_REJECTED', 'REFLECTION_RUN_IDENTITY_REJECTED', 'REFLECTION_SOURCE_DIGEST_REJECTED', 'REFLECTION_SOURCE_INPUT_CHANGED', 'REFLECTION_STALE_OUTPUT_REJECTED', 'REFLECTION_TEXTURE_FIELDS_REJECTED', 'REFLECTION_TEXTURE_IDENTITY_REJECTED', 'REFLECTION_TEXTURE_SIZE_REJECTED']) | {'NONE','UNKNOWN'}
DIAGNOSTIC_STAGES = frozenset({'DESTINATION','IDENTITY','RECEIPT_READ','RECEIPT_VALIDATE','SOURCE_DIGEST','ORIGINAL_READ','ORIGINAL_HASH','EXR_HEADER','META_VALIDATE','META_GUID','EXPORT_COPY','COMPLETE'})
META_FIELD_CODES = frozenset().union(*META_NUMERIC.values(),META_SECTIONS,META_EMPTY,{'fileFormatVersion','guid','TextureImporter','internalIDToNameTable','externalObjects','spritePivot','spriteBorder','buildTarget','sprites','outline','physicsShape','bones','vertices','edges','weights','secondaryTextures','indices','nameFileIdTable','spriteID','customData','spriteCustomMetadata','entries'})
META_SCOPE_CODES = {'root':'ROOT','TextureImporter':'TEXTURE_IMPORTER','mipmaps':'MIPMAPS','bumpmap':'BUMPMAP','textureSettings':'TEXTURE_SETTINGS','platformSettings':'PLATFORM_SETTINGS','spriteSheet':'SPRITE_SHEET','spriteCustomMetadata':'SPRITE_CUSTOM_METADATA'}


class ExportTrace:
    def __init__(self):
        self.ident=None;self.stage='DESTINATION';self.fileRole='NONE';self.metaScope='NONE';self.metaField='NONE'
    def bind(self,ident):
        require(visual.HEX40.fullmatch(ident.get('sourceCommit','')) and visual.HEX40.fullmatch(ident.get('reviewedCandidateCommit','')) and all(re.fullmatch(r'[1-9][0-9]*',ident.get(k,'')) for k in ('runId','runAttempt')), 'REFLECTION_RUN_IDENTITY_REJECTED')
        self.ident={k:ident[k] for k in ('sourceCommit','runId','runAttempt')}
    def meta(self,scope,key):
        self.metaScope=META_SCOPE_CODES.get(scope.split(':')[0],'UNKNOWN')
        self.metaField=key if key in META_FIELD_CODES else 'UNKNOWN'
    def receipt(self,error=None):
        require(self.ident is not None and self.stage in DIAGNOSTIC_STAGES,'REFLECTION_RUN_IDENTITY_REJECTED')
        code='NONE';kind='NONE'
        if error is not None:
            code=error.args[0] if type(error) is ValueError and len(error.args)==1 and type(error.args[0]) is str and error.args[0] in DIAGNOSTIC_CODES-{'NONE'} else 'UNKNOWN'
            kind='VALIDATION' if isinstance(error,ValueError) else 'IO' if isinstance(error,OSError) else 'UNKNOWN'
        return dict(schemaVersion=1,scope=DIAGNOSTIC_SCOPE,**self.ident,status='FAILED' if error is not None else 'COMPLETE',stage=self.stage,fileRole=self.fileRole,metaScope=self.metaScope,metaField=self.metaField,errorCode=code,exceptionKind=kind)


def diagnostic_path(root):
    p=visual.outdir(root)/DIAGNOSTIC_NAME
    require(p.parent.resolve()==p.parent.absolute() and not p.is_symlink(),'REFLECTION_DESTINATION_REJECTED')
    return p


def run(root):
    trace=ExportTrace()
    try:
        dest=diagnostic_path(root)
        if dest.exists():
            require(dest.is_file(),'REFLECTION_STALE_OUTPUT_REJECTED');dest.unlink()
        export_reflections(root,trace)
    except BaseException as error:
        if trace.ident is not None:
            try:
                payload=json.dumps(trace.receipt(error),sort_keys=True).encode('utf-8')
                require(len(payload)<=2048,'REFLECTION_RECEIPT_FIELDS_REJECTED')
                dest=diagnostic_path(root);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(payload)
            except BaseException:pass
        print('REFLECTION_BAKE_EVIDENCE_REJECTED');return 1
    try:
        payload=json.dumps(trace.receipt(),sort_keys=True).encode('utf-8')
        require(len(payload)<=2048,'REFLECTION_RECEIPT_FIELDS_REJECTED')
        dest=diagnostic_path(root);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(payload)
    except BaseException:
        print('REFLECTION_EXPORT_DIAGNOSTIC_WRITE_REJECTED');return 1
    return 0


def main():
    return run(Path(__file__).resolve().parents[3])


if __name__ == '__main__':raise SystemExit(main())
