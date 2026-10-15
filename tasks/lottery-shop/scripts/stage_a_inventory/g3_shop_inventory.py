#!/usr/bin/env python3
"""Stage-A bounded observation. Never grants a source waiver or G3/Android PASS.

Python 3.11+, Linux. Does not execute Unity, mutate project files, or upload data.
Only its explicit output file is created (O_EXCL, mode 0600).
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

BASE = Path(__file__).absolute().parent
PIN = '02a6440209c26bcc94c50fdf73a87345b563b5ed'
POLICY_SHA256 = 'c2517fcb7c1c03498b0a750412bbce7cce1f63d74af20680850cf852d2fb7928'
SHOP = 'Assets/G3/Shop/Resources/G3/Shop'
SCOPE = 'Assets/G3/Shop'
SCHEMA = 1
MAX_ENTRIES = 2048
MAX_TOTAL = 256 * 1024 * 1024
MAX_FILE = 64 * 1024 * 1024
MAX_REPORT = 4 * 1024 * 1024
MAX_MESHES = 512  # Observation budget, NOT an inferred FBX bound or formal allow rule.
MAX_TRANSPARENT_INDEX = 4095  # Diagnostic budget only; native count remains unproved.
CONTEXTS = {'SHOP_IMPORT_INVENTORY_DIAGNOSTIC', 'ANDROID_COLD_IMPORT_INVENTORY_DIAGNOSTIC'}
SCOPE_LABEL = 'SHOP_INVENTORY_DIAGNOSTIC_NOT_SOURCE_WAIVER_NOT_G3_PASS'
HEX64 = re.compile(r'[0-9a-f]{64}\Z')

class Rejected(ValueError):
    pass

def require(ok, code):
    if not ok:
        raise Rejected(code)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)+'\n').encode()

def unique(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, 'JSON_DUPLICATE_KEY')
        out[key] = value
    return out

def parse_json(data):
    require(len(data) <= MAX_REPORT, 'JSON_TOO_LARGE')
    try:
        return json.loads(data, object_pairs_hook=unique, parse_constant=lambda _: require(False, 'JSON_NONFINITE'))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise Rejected('JSON_INVALID') from None

def valid_path(value):
    require(type(value) is str and 0 < len(value) <= 240 and re.fullmatch(r'[A-Za-z0-9_. /-]+', value), 'PATH_REJECTED')
    parts = value.split('/')
    require(all(p not in ('', '.', '..') and not p.endswith((' ', '.')) for p in parts), 'PATH_REJECTED')
    return value

def identity(value):
    fields = {'sourceCommit', 'gameSourceCommit', 'triggerCommit', 'runId', 'runAttempt', 'context'}
    require(type(value) is dict and set(value) == fields, 'IDENTITY_FIELDS')
    for key in ('sourceCommit', 'gameSourceCommit', 'triggerCommit'):
        require(type(value[key]) is str and re.fullmatch('[0-9a-f]{40}', value[key]), 'IDENTITY_COMMIT')
    require(value['gameSourceCommit'] == PIN, 'GAME_SOURCE_MISMATCH')
    for key in ('runId', 'runAttempt'):
        require(type(value[key]) is str and re.fullmatch('[1-9][0-9]{0,19}', value[key]), 'IDENTITY_RUN')
    require(value['context'] in CONTEXTS, 'IDENTITY_CONTEXT')
    return value.copy()

def stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

class SecureTree:
    """Anchored no-follow dirfds, no multiply-linked files; detects concurrent changes.

    Requires a stopped/quiescent writer. Rechecks are not a claim of atomic hostile
    filesystem snapshot or protection against a privileged kernel adversary.
    """
    def __init__(self, root):
        self.root = Path(root)
        require(self.root.is_absolute() and str(self.root) == os.path.normpath(str(self.root)), 'ROOT_NOT_ABSOLUTE')
        self.fds = {}
        self.dirs = {}
        self.files = {}
        self.total = 0
        self.inodes = set()
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self.anchor_fds = [fd]
        self.anchors = []
        prefix = '/'
        try:
            for part in self.root.parts[1:]:
                before = os.stat(part, dir_fd=fd, follow_symlinks=False)
                require(stat.S_ISDIR(before.st_mode), 'DIRECTORY_LINK_OR_TYPE')
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                require(stamp(before) == stamp(os.fstat(child)), 'DIRECTORY_RACE')
                self.anchors.append((fd, part, (before.st_dev, before.st_ino, before.st_mode)))
                self.anchor_fds.append(child)
                fd = child
            self.fds[''] = fd
            self.dirs[''] = stamp(os.fstat(fd))
        except BaseException:
            self.close()
            raise

    def close(self):
        for fd in set(list(getattr(self, 'fds', {}).values()) + getattr(self, 'anchor_fds', [])):
            os.close(fd)
        self.fds = {}; self.anchor_fds = []

    def __enter__(self): return self
    def __exit__(self, *_): self.close()

    def directory(self, rel):
        if rel in self.fds: return self.fds[rel]
        valid_path(rel)
        parent, _, name = rel.rpartition('/')
        fd = self.directory(parent)
        before = os.stat(name, dir_fd=fd, follow_symlinks=False)
        require(stat.S_ISDIR(before.st_mode), 'DIRECTORY_LINK_OR_TYPE')
        child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        self.fds[rel] = child
        require(stamp(before) == stamp(os.fstat(child)), 'DIRECTORY_RACE')
        self.dirs[rel] = stamp(before)
        return child

    def exists(self, rel):
        valid_path(rel)
        parent, _, name = rel.rpartition('/')
        try:
            fd = self.directory(parent)
            os.stat(name, dir_fd=fd, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False

    def read(self, rel, limit=MAX_FILE):
        valid_path(rel)
        parent, _, name = rel.rpartition('/')
        fd = self.directory(parent)
        before = os.stat(name, dir_fd=fd, follow_symlinks=False)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'FILE_LINK_OR_TYPE')
        require(not before.st_mode & 0o111, 'FILE_EXECUTABLE')
        require(0 < before.st_size <= limit, 'FILE_SIZE')
        require(rel not in self.files and (before.st_dev, before.st_ino) not in self.inodes, 'FILE_ALIAS')
        readfd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            require(stamp(before) == stamp(os.fstat(readfd)), 'FILE_RACE')
            chunks = []; count = 0
            while True:
                data = os.read(readfd, min(1048576, limit + 1 - count))
                if not data: break
                count += len(data); require(count <= limit, 'FILE_SIZE'); chunks.append(data)
            require(count == before.st_size and stamp(before) == stamp(os.fstat(readfd)), 'FILE_CHANGED_DURING_READ')
        finally:
            os.close(readfd)
        require(stamp(before) == stamp(os.stat(name, dir_fd=fd, follow_symlinks=False)), 'FILE_REPLACED')
        self.total += count; require(self.total <= MAX_TOTAL, 'TOTAL_SIZE')
        self.inodes.add((before.st_dev, before.st_ino)); self.files[rel] = stamp(before)
        return b''.join(chunks)

    def walk(self, rel, allowed_dirs, classify):
        fd = self.directory(rel)
        result = []
        names = sorted(os.listdir(fd))
        for name in names:
            path = rel+'/'+name
            valid_path(path)
            s = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISDIR(s.st_mode):
                require(path in allowed_dirs, 'UNKNOWN_DIRECTORY')
                result.extend(self.walk(path, allowed_dirs, classify))
            else:
                require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'FILE_LINK_OR_TYPE')
                classify(path)  # Reject unknown names before reading/hash/export.
                result.append(path)
            require(len(result) <= MAX_ENTRIES, 'ENTRY_LIMIT')
        return result

    def identity_unchanged(self):
        for fd, name, prior in self.anchors:
            now = os.stat(name, dir_fd=fd, follow_symlinks=False)
            require((now.st_dev, now.st_ino, now.st_mode) == prior, 'ANCESTOR_REPLACED')
        for rel, old in self.dirs.items():
            now = os.fstat(self.fds[rel])
            require((now.st_dev, now.st_ino, now.st_mode) == old[:3], 'DIRECTORY_REPLACED')
            if rel:
                parent, _, name = rel.rpartition('/')
                current = os.stat(name, dir_fd=self.fds[parent], follow_symlinks=False)
                require((current.st_dev, current.st_ino, current.st_mode) == old[:3], 'DIRECTORY_REPLACED')

    def finish(self):
        for fd, name, prior in self.anchors:
            now = os.stat(name, dir_fd=fd, follow_symlinks=False)
            require((now.st_dev, now.st_ino, now.st_mode) == prior, 'ANCESTOR_REPLACED')
        for rel, old in self.dirs.items():
            require(stamp(os.fstat(self.fds[rel])) == old, 'DIRECTORY_CHANGED')
            if rel:
                parent, _, name = rel.rpartition('/')
                require(stamp(os.stat(name, dir_fd=self.fds[parent], follow_symlinks=False)) == old, 'DIRECTORY_REPLACED')
        for rel, old in self.files.items():
            parent, _, name = rel.rpartition('/')
            require(stamp(os.stat(name, dir_fd=self.fds[parent], follow_symlinks=False)) == old, 'INPUT_DRIFT')


def load_local(path, limit=MAX_REPORT):
    path = Path(path).absolute()
    with SecureTree(path.parent) as tree:
        raw = tree.read(path.name, limit); tree.finish(); return raw


def load_policy():
    raw = load_local(BASE/'policy.json')
    require(sha(raw) == POLICY_SHA256, 'POLICY_DRIFT')
    return Policy(parse_json(raw))

class Policy:
    def __init__(self, p):
        self.raw = p
        self.sources = {x['path']: x for x in p['sourceFiles']}
        require(len(self.sources) == len(p['sourceFiles']), 'SOURCE_DUPLICATE')
        self.pothos = set(p['pothos'])
        self.digest_changes = set(p['digestOnlyTrackedChanges'])
        self.allowed_dirs = set()
        for path in self.sources:
            if path.startswith(SCOPE+'/'):
                for parent in PurePosixPath(path).parents:
                    text = str(parent)
                    if text == SCOPE or text.startswith(SCOPE+'/'): self.allowed_dirs.add(text)
        self.generated = {}
        self.missing_meta = set()
        for path in self.sources:
            if path.startswith(SHOP+'/') and not path.endswith('.meta') and path+'.meta' not in self.sources:
                self.missing_meta.add(path+'.meta')
                self.generated[path+'.meta'] = 'SOURCE_PAIRED_META'
        for path in self.allowed_dirs:
            if path+'.meta' not in self.sources:
                self.generated[path+'.meta'] = 'SOURCE_DIRECTORY_META'
        self.names = {x['name']: x for x in p['materials']}
        self.outputs = ['LotteryShop_Runtime'] + [PurePosixPath(x).stem+'_Runtime' for x in p['toolModels']]
        for directory in ('Materials', 'Generated', 'Reflections'):
            self.allowed_dirs.add(SHOP+'/'+directory)
            self.generated[SHOP+'/'+directory+'.meta'] = 'GENERATED_DIRECTORY_META'
        def add(path, kind):
            require(path not in self.sources and path not in self.generated, 'RECIPE_COLLISION')
            self.generated[path] = kind; self.generated[path+'.meta'] = 'GENERATED_ASSET_META'
        for item in p['materials']:
            require(re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}', item['name']), 'RECIPE_NAME')
            add(SHOP+'/Materials/'+item['name']+'.mat', 'GENERATED_MATERIAL')
            if item['roughnessTexture']:
                add(SHOP+'/Materials/'+item['name']+'_MetallicSmoothness.asset', 'GENERATED_PACKED_TEXTURE')
        for name in self.outputs: add(SHOP+'/'+name+'.prefab', 'GENERATED_RUNTIME_PREFAB')
        add(SHOP+'/G3VisualPipeline.asset', 'GENERATED_PIPELINE')
        add(SHOP+'/G3ContactRenderer.asset', 'GENERATED_RENDERER_DATA')
        for name in ('Day.exr','Night.exr'): add(SHOP+'/Reflections/'+name, 'REFLECTION_EXR')
        add(SHOP+'/Reflections/reflection-receipt.json', 'REFLECTION_RECEIPT_DIGEST_ONLY')

    def classify(self, path):
        valid_path(path)
        if path in self.sources:
            return 'TRACKED_POTHOS_META' if path in self.pothos else 'TRACKED_DIGEST_ONLY' if path in self.digest_changes else 'FROZEN_SOURCE'
        if path in self.generated: return self.generated[path]
        prefix = SHOP+'/Generated/'
        if path.startswith(prefix):
            suffix = path[len(prefix):]
            if suffix.endswith('.meta'): suffix = suffix[:-5]
            require(suffix.endswith('.asset'), 'UNKNOWN_PATH')
            stem = suffix[:-6]
            for output in self.outputs:
                if not stem.startswith(output+'_'): continue
                group = stem[len(output)+1:]
                if group in self.names and not self.names[group]['transparent']:
                    return 'BOUNDED_MESH_CANDIDATE_META' if path.endswith('.meta') else 'BOUNDED_MESH_CANDIDATE'
                match = re.fullmatch(r'([A-Za-z][A-Za-z0-9_]*)_glass_(0|[1-9][0-9]{0,3})', group)
                if match and match[1] in self.names and self.names[match[1]]['transparent'] and int(match[2]) <= MAX_TRANSPARENT_INDEX:
                    return 'BOUNDED_MESH_CANDIDATE_META' if path.endswith('.meta') else 'BOUNDED_MESH_CANDIDATE'
        raise Rejected('UNKNOWN_PATH')

    def limit(self, path, role):
        if path.endswith('.meta'): return 65536
        if role == 'GENERATED_MATERIAL': return 262144
        if role == 'REFLECTION_EXR': return 8388608
        if role == 'REFLECTION_RECEIPT_DIGEST_ONLY': return 16384
        return MAX_FILE

# Strict grammar adapted from the pinned reflection_bake_ci.py validator.
# Projection eligibility is deliberately separate from semantic approval.
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


def texture_projection(data):
    trace = None
    require(len(data) <= 65536, "META_SIZE")
    try: text = data.decode('utf-8')
    except UnicodeError: raise Rejected('META_ENCODING') from None
    lines = text.splitlines()
    require('\r' not in text and '\x00' not in text and text.isascii(), 'META_ENCODING')
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
            ok=re.fullmatch(NUMBER,value) is not None and math.isfinite(float(value)) and len(value) <= 32 and abs(float(value)) <= 2147483648
        elif kind=='TextureImporter' and key in META_SECTIONS:
            ok=value==''
        elif kind=='TextureImporter' and key in META_EMPTY:
            ok=value==''
        elif kind=='TextureImporter' and key in {'internalIDToNameTable','externalObjects'}:
            ok=value==('[]' if key=='internalIDToNameTable' else '{}')
        elif kind=='TextureImporter' and key in {'spritePivot','spriteBorder'}:
            axes=('x','y') if key=='spritePivot' else ('x','y','z','w')
            pattern=r'\{' + ', '.join(axis+': ('+NUMBER+')' for axis in axes) + r'\}'
            vector=re.fullmatch(pattern,value);ok=vector is not None and all(len(v) <= 32 and math.isfinite(float(v)) and abs(float(v)) <= 2147483648 for v in vector.groups())
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
    required={('root','fileFormatVersion'):'2',('root','TextureImporter'):'',('TextureImporter','userData'):'',('TextureImporter','assetBundleName'):'',('TextureImporter','assetBundleVariant'):''}
    require(('root','guid') in seen and all(seen.get(key)==value for key,value in required.items()), 'REFLECTION_META_IMPORT_REJECTED')
    for n in range(platform+1):require(('platformSettings:'+str(n),'buildTarget') in seen, 'REFLECTION_META_PLATFORM_REJECTED')

    return {scope+"/"+key: value for (scope,key),value in sorted(seen.items())}


# Finite diagnostic alphabet only. None of these labels is copied from input.
META_FLOW_ASSETS = ('MODEL_INTERIOR', 'MODEL_LAMP', 'MODEL_STAMP', 'MODEL_BOX',
                    'SOURCE_PAIRED_META', 'SOURCE_DIRECTORY_META',
                    'GENERATED_DIRECTORY_META', 'GENERATED_ASSET_META',
                    'BOUNDED_MESH_META', 'OTHER_META')
META_FLOW_FIELDS = ('MODEL_EXTERNAL_FIRST', 'MODEL_EXTERNAL_SECOND',
                    'MODEL_INTERNAL_ID_FIRST', 'MODEL_INTERNAL_ID_SECOND',
                    'MODEL_OTHER', 'OTHER')
META_FLOW_SHAPES = ('MATERIAL_CORE_KNOWN', 'MATERIAL_LEGACY_KNOWN',
                    'MATERIAL_CORE_UNKNOWN_NAME', 'TYPED_IDENTIFIER_OTHER',
                    'INTEGER_PAIR_BOUNDED', 'INTEGER_PAIR_OTHER',
                    'RGBA_FINITE_BOUNDED', 'RGBA_OTHER',
                    'REFERENCE_BOUNDED_NONCANONICAL', 'REFERENCE_OTHER',
                    'DUPLICATE_KEYS', 'NESTED_COLLECTION', 'YAML_SPECIAL',
                    'LIMIT', 'OTHER')
META_FLOW_CODES = frozenset('META_UNSUPPORTED_FLOW__' + asset + '__' + field + '__' + shape
                            for asset in META_FLOW_ASSETS for field in META_FLOW_FIELDS
                            for shape in META_FLOW_SHAPES)


def meta_flow_asset(path, role):
    # Exact frozen source identities, then already-classified policy role only.
    models = {SHOP + '/LotteryShop_Interior.fbx.meta': 'MODEL_INTERIOR',
              SHOP + '/Tool_inspection_lamp.fbx.meta': 'MODEL_LAMP',
              SHOP + '/Tool_large_prize_stamp.fbx.meta': 'MODEL_STAMP',
              SHOP + '/Tool_small_prize_box.fbx.meta': 'MODEL_BOX'}
    if path in models: return models[path]
    roles = {'SOURCE_PAIRED_META': 'SOURCE_PAIRED_META',
             'SOURCE_DIRECTORY_META': 'SOURCE_DIRECTORY_META',
             'GENERATED_DIRECTORY_META': 'GENERATED_DIRECTORY_META',
             'GENERATED_ASSET_META': 'GENERATED_ASSET_META',
             'BOUNDED_MESH_CANDIDATE_META': 'BOUNDED_MESH_META'}
    return roles.get(role, 'OTHER_META')


def meta_flow_field(containers, depth, key):
    if containers.get(0) != ('ModelImporter', ''): return 'OTHER'
    if depth == 4:
        owner = containers.get(2)
        if owner == ('externalObjects', ''):
            if key == 'first': return 'MODEL_EXTERNAL_FIRST'
            if key == 'second': return 'MODEL_EXTERNAL_SECOND'
        if owner == ('internalIDToNameTable', ''):
            if key == 'first': return 'MODEL_INTERNAL_ID_FIRST'
            if key == 'second': return 'MODEL_INTERNAL_ID_SECOND'
    return 'MODEL_OTHER'


def meta_flow_shape(value, material_names):
    """Classify a REJECTED flow; never parses YAML or returns input text.

    Maximum 1024 ASCII characters, eight flat pairs, zero nested collections.
    No recursion, deserialization, eval, name/path/GUID export or acceptance.
    Numbers are only tested after lexical length bounds. The supplied material
    set comes from the exact-hash frozen policy; membership emits one fixed label.
    """
    if type(value) is not str or not 0 < len(value) <= 1024 or not value.isascii():
        return 'LIMIT'
    if any(c in value for c in '&*!'): return 'YAML_SPECIAL'
    if value.count('{') > 1 or value.count('}') > 1 or '[' in value or ']' in value:
        return 'NESTED_COLLECTION'
    if not (value.startswith('{') and value.endswith('}')): return 'OTHER'
    parts = value[1:-1].split(',')
    if len(parts) > 8: return 'LIMIT'
    pairs = {}
    for part in parts:
        if ':' not in part: return 'OTHER'
        key, scalar = (x.strip(' ') for x in part.split(':', 1))
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}|-?[0-9]{1,19}', key):
            return 'OTHER'
        if key in pairs: return 'DUPLICATE_KEYS'
        pairs[key] = scalar
    keys = set(pairs)
    if keys == {'type', 'assembly', 'name'}:
        name = pairs['name']
        bounded_name = re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', name) is not None
        if pairs['type'] == 'Material' and bounded_name:
            known = name in material_names
            if pairs['assembly'] == 'UnityEngine.CoreModule':
                return 'MATERIAL_CORE_KNOWN' if known else 'MATERIAL_CORE_UNKNOWN_NAME'
            if pairs['assembly'] == 'UnityEngine' and known: return 'MATERIAL_LEGACY_KNOWN'
        return 'TYPED_IDENTIFIER_OTHER'
    if len(pairs) == 1 and re.fullmatch(r'-?[0-9]{1,19}', next(iter(pairs))):
        key, scalar = next(iter(pairs.items()))
        bounded = (re.fullmatch(r'[0-9]{1,3}', key) is not None and
                   re.fullmatch(r'-?[0-9]{1,19}', scalar) is not None and
                   -(2**63) <= int(scalar) < 2**63)
        return 'INTEGER_PAIR_BOUNDED' if bounded else 'INTEGER_PAIR_OTHER'
    if keys == {'r', 'g', 'b', 'a'}:
        bounded = all(len(v) <= 32 and re.fullmatch(NUMBER, v) is not None and
                      math.isfinite(float(v)) and abs(float(v)) <= 2147483648
                      for v in pairs.values())
        return 'RGBA_FINITE_BOUNDED' if bounded else 'RGBA_OTHER'
    if keys in ({'fileID'}, {'fileID', 'guid', 'type'}):
        file_id = pairs['fileID']
        bounded = (re.fullmatch(r'-?[0-9]{1,19}', file_id) is not None and
                   -(2**63) <= int(file_id) < 2**63)
        if len(keys) == 3:
            bounded = (bounded and re.fullmatch(r'[0-9a-f]{32}', pairs['guid']) is not None
                       and pairs['type'] in {'0', '1', '2', '3'})
        return 'REFERENCE_BOUNDED_NONCANONICAL' if bounded else 'REFERENCE_OTHER'
    return 'OTHER'


def meta_flow_failure(asset, containers, depth, key, value, material_names):
    asset = asset if asset in META_FLOW_ASSETS else 'OTHER_META'
    field = meta_flow_field(containers, depth, key)
    shape = meta_flow_shape(value, material_names)
    code = 'META_UNSUPPORTED_FLOW__' + asset + '__' + field + '__' + shape
    # Defense in depth: arbitrary diagnostic text never reaches the envelope.
    return code if code in META_FLOW_CODES else 'META_UNSUPPORTED_FLOW'


def screen_other_meta(raw, asset='OTHER_META', material_names=frozenset()):
    """Conservative YAML-shaped screen; never a native-importer schema approval.

    Accept canonical block mapping/list-of-mapping syntax, empty collections,
    and narrow numeric/GUID reference/vector flows. Ambiguous syntax is refused,
    not silently skipped. Every accepted value remains digest-only.
    """
    try: text = raw.decode('utf-8')
    except UnicodeError: raise Rejected('META_ENCODING') from None
    require(text.isascii() and '\x00' not in text and '\r' not in text, 'META_ENCODING_OR_SIZE')
    lines = text.splitlines()
    require(0 < len(lines) <= 1024, 'META_ENCODING_OR_SIZE')
    seen = {}  # One mapping at each current effective indentation level.
    containers = {}
    previous = None
    sensitive = {'userData', 'assetBundleName', 'assetBundleVariant'}
    number = r'-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?'
    for line in lines:
        require(0 < len(line) <= 1024, 'META_LINE_SIZE')
        match = re.fullmatch(r'( *)(- )?([A-Za-z_][A-Za-z0-9_]*):[ ]*(.*)', line)
        require(match is not None, 'META_UNSUPPORTED_SYNTAX')
        spaces, dash, key, value = match.groups()
        physical = len(spaces); depth = physical + (2 if dash else 0)
        require(physical % 2 == 0 and depth <= 20, 'META_UNSUPPORTED_STRUCTURE')
        value = value.rstrip(' ')
        require(not re.search(r'password|passcode|secret|token|credential|license|privatekey|apikey', key, re.I), 'META_SENSITIVE_KEY')
        if key in sensitive:
            require(value in ('', '""', "''"), 'META_SENSITIVE_OR_BUNDLE_VALUE')
        # New child mappings must have an explicitly empty, non-sensitive owner.
        if dash:
            owner = containers.get(physical)
            require(owner is not None and owner[1] == '' and owner[0] not in sensitive,
                    'META_UNSUPPORTED_STRUCTURE')
            for level in list(seen):
                if level >= depth: del seen[level]
            for level in list(containers):
                if level >= depth: del containers[level]
        elif previous is None:
            require(depth == 0, 'META_UNSUPPORTED_STRUCTURE')
        elif depth > previous:
            owner = containers.get(previous)
            require(depth == previous + 2 and owner is not None and owner[1] == '' and owner[0] not in sensitive,
                    'META_UNSUPPORTED_STRUCTURE')
            seen[depth] = set()
        else:
            require(depth in seen, 'META_UNSUPPORTED_STRUCTURE')
        for level in list(containers):
            if level > depth: del containers[level]
        for level in list(seen):
            if level > depth: del seen[level]
        scope = seen.setdefault(depth, set())
        require(key not in scope, 'META_DUPLICATE_KEY'); scope.add(key)
        if value not in ('', '""', "''", '{}', '[]'):
            if value.startswith('{'):
                # Unity object references and numeric vectors, with no strings,
                # nested maps, arbitrary keys, aliases, or sensitive-key slots.
                reference = re.fullmatch(r'\{fileID: -?[0-9]{1,19}(?:, guid: [0-9a-f]{32}, type: [0-9]{1,3})?\}', value)
                vector = None
                for axes in [('x','y'), ('x','y','z'), ('x','y','z','w')]:
                    vector = re.fullmatch(r'\{' + ', '.join(axis+': ('+number+')' for axis in axes) + r'\}', value)
                    if vector: break
                # Unity's documented sample null avatar reference only, in its exact slot.
                # No nonzero IDs, other fields, nested slots or arbitrary maps.
                null_avatar = (asset in {'MODEL_INTERIOR', 'MODEL_LAMP', 'MODEL_STAMP', 'MODEL_BOX'} and not dash and depth == 2 and
                               containers.get(0) == ('ModelImporter', '') and
                               key == 'lastHumanDescriptionAvatarSource' and value == '{instanceID: 0}')
                if not (null_avatar or reference is not None or (vector is not None and all(len(v) <= 32 and math.isfinite(float(v)) and abs(float(v)) <= 2147483648 for v in vector.groups()))):
                    # All other unsupported flows retain the finite rejection diagnostic.
                    raise Rejected(meta_flow_failure(asset, containers, depth, key, value, material_names))
            else:
                # Canonical plain scalar only. Quotes/escapes, YAML tags/anchors,
                # aliases, comments, flow lists, block scalars, complex keys and
                # scalar continuation lines are rejected rather than interpreted.
                require(re.fullmatch(r'[A-Za-z0-9_./,: +()-]+', value) is not None,
                        'META_UNSUPPORTED_SCALAR')
        containers[depth] = (key, value)
        previous = depth


def observe(tree, policy, phase):
    paths = tree.walk(SCOPE, policy.allowed_dirs, policy.classify)
    if tree.exists(SCOPE+'.meta'): paths.append(SCOPE+'.meta')
    for path in policy.sources:
        if not path.startswith(SCOPE+'/'): paths.append(path)
    paths = sorted(set(paths))
    require(len(paths) <= MAX_ENTRIES, 'ENTRY_LIMIT')
    require(set(policy.sources).issubset(paths), 'FROZEN_SOURCE_MISSING')
    if phase == 'BEFORE': require(set(paths) == set(policy.sources), 'BEFORE_NOT_COLD_SOURCE')
    records = []
    mesh_count = 0
    for path in paths:
        role = policy.classify(path)
        mesh_count += role == 'BOUNDED_MESH_CANDIDATE'
        require(mesh_count <= MAX_MESHES, 'MESH_OBSERVATION_LIMIT')
        raw = tree.read(path, policy.limit(path, role))
        digest = sha(raw)
        source = policy.sources.get(path)
        if source and (phase == 'BEFORE' or role == 'FROZEN_SOURCE'):
            require(digest == source['sha256'] and len(raw) == source['bytes'], 'FROZEN_INPUT_DRIFT')
        row = {'path': path, 'role': role, 'bytes': len(raw), 'sha256': digest, 'projection': 'DIGEST_ONLY_UNREVIEWED'}
        # Immutable bytes from public frozen inputs need no new content projection.
        if path in policy.pothos or (source is None and (path.endswith('.png.meta') or path.endswith('.exr.meta'))):
            row['safeFields'] = texture_projection(raw)
            row['projection'] = 'STRICT_TEXTURE_FIELDS_ONLY'
            if path.endswith('/Day.exr.meta'):
                require(row['safeFields'].get('root/guid') == 'b90a2a9e9f0d4c1bab2f613e26d9c771', 'REFLECTION_GUID')
            if path.endswith('/Night.exr.meta'):
                require(row['safeFields'].get('root/guid') == 'a54ec87d23ac49ea83e7cf7bad94381a', 'REFLECTION_GUID')
        elif source is None and path.endswith('.meta'):
            screen_other_meta(raw, meta_flow_asset(path, role), frozenset(policy.names))
        records.append(row)
    tree.finish()
    return records


def snapshot(root, ident, policy, phase):
    require(phase in ('BEFORE', 'AFTER'), 'PHASE_REJECTED')
    with SecureTree(root) as tree:
        records = observe(tree, policy, phase)
    return {'schemaVersion': SCHEMA, 'scope': SCOPE_LABEL, 'identity': identity(ident),
            'policySha256': POLICY_SHA256, 'phase': phase, 'files': records,
            'nativeExecutionAttested': False, 'formalSourceWaiver': False, 'g3Pass': False}


def validate_before(before, expected, policy):
    fields = {'schemaVersion','scope','identity','policySha256','phase','files','nativeExecutionAttested','formalSourceWaiver','g3Pass'}
    require(type(before) is dict and set(before) == fields, 'BEFORE_SCHEMA')
    require(type(before['schemaVersion']) is int and before['schemaVersion'] == SCHEMA and before['scope'] == SCOPE_LABEL, 'BEFORE_SCHEMA')
    require(before['phase'] == 'BEFORE' and before['policySha256'] == POLICY_SHA256, 'BEFORE_CONTEXT')
    require(identity(before['identity']) == identity(expected), 'BEFORE_IDENTITY_MISMATCH')
    require(before['nativeExecutionAttested'] is False and before['formalSourceWaiver'] is False and before['g3Pass'] is False, 'BEFORE_CLAIMS')
    require(type(before['files']) is list and len(before['files']) == len(policy.sources), 'BEFORE_FILES')
    for row in before['files']:
        require(type(row) is dict, 'BEFORE_RECORD_TYPE')
        require(type(row.get('path')) is str and row['path'] in policy.sources, 'BEFORE_PATHS')
        path = row['path']; expected_row = policy.sources[path]
        fields = {'path','role','bytes','sha256','projection'}
        projected = path in policy.pothos
        if projected: fields.add('safeFields')
        require(set(row) == fields, 'BEFORE_RECORD')
        require(type(row['role']) is str and row['role'] == policy.classify(path), 'BEFORE_RECORD')
        expected_projection = 'STRICT_TEXTURE_FIELDS_ONLY' if projected else 'DIGEST_ONLY_UNREVIEWED'
        require(type(row['projection']) is str and row['projection'] == expected_projection, 'BEFORE_PROJECTION_LABEL')
        require(type(row['bytes']) is int and row['bytes'] == expected_row['bytes'] and
                type(row['sha256']) is str and HEX64.fullmatch(row['sha256']) and row['sha256'] == expected_row['sha256'], 'BEFORE_HASH')
        if projected:
            fields = row['safeFields']
            require(type(fields) is dict and len(fields) <= 256 and
                    all(type(k) is str and type(v) is str and len(k) <= 128 and len(v) <= 512 for k,v in fields.items()), 'BEFORE_SAFE_FIELDS')
            raw = load_local(BASE/'pinned/Textures'/PurePosixPath(path).name, 65536)
            require(sha(raw) == expected_row['sha256'] and fields == texture_projection(raw), 'BEFORE_PROJECTION_TAMPERED')
    require([row['path'] for row in before['files']] == sorted(policy.sources), 'BEFORE_PATHS')


def compare(before, after, policy, native_exit):
    require(type(native_exit) is int and 0 <= native_exit <= 255, 'NATIVE_EXIT_INVALID')
    validate_before(before, after['identity'], policy)
    old = {x['path']:x for x in before['files']}
    new = {x['path']:x for x in after['files']}
    differences = []
    for path in sorted(policy.pothos):
        a, b = old[path], new[path]
        require(a['safeFields']['root/guid'] == b['safeFields']['root/guid'], 'TRACKED_GUID_CHANGED')
        fields = sorted(set(a['safeFields']) | set(b['safeFields']))
        differences.append({'path':path, 'beforeSha256':a['sha256'], 'afterSha256':b['sha256'],
            'rawBytesChanged':a['sha256'] != b['sha256'],
            'safeFieldChanges':[{'field':f,'before':a['safeFields'].get(f),'after':b['safeFields'].get(f)} for f in fields if a['safeFields'].get(f) != b['safeFields'].get(f)],
            'semanticApproval':'NOT_REVIEWED'})
    tracked = [{'path':p,'beforeSha256':old[p]['sha256'],'afterSha256':new[p]['sha256'],
                'beforeBytes':old[p]['bytes'],'afterBytes':new[p]['bytes'], 'contentExported':False}
               for p in sorted(policy.digest_changes) if old[p]['sha256'] != new[p]['sha256']]
    missing = sorted(set(policy.generated)-set(new))
    missing_mesh_meta = sorted(p+'.meta' for p,r in new.items() if r['role']=='BOUNDED_MESH_CANDIDATE' and p+'.meta' not in new)
    orphan_meta = sorted(p for p in new if p.endswith('.meta') and policy.classify(p)=='BOUNDED_MESH_CANDIDATE_META' and p[:-5] not in new)
    return {'schemaVersion':SCHEMA, 'scope':SCOPE_LABEL, 'identity':after['identity'], 'policySha256':POLICY_SHA256,
        'status':'INCONCLUSIVE_OBSERVATION_ONLY', 'nativeExitCodeReportedByCaller':native_exit,
        'nativeExecutionAttested':False, 'formalSourceWaiver':False, 'g3Pass':False,
        'files':after['files'], 'pothosFieldDiff':differences, 'digestOnlyTrackedDiff':tracked,
        'missingRecipeCandidates':missing, 'missingMeshMeta':missing_mesh_meta, 'orphanMeshMeta':orphan_meta,
        'unknownGeneratedMeshSet':'REQUIRES_NATIVE_FBX_MAPPING_AND_FRESH_REVIEW',
        'outsideShopCoverage':'ONLY_EXPLICIT_RECIPE_AND_FIVE_TRACKED_CHANGE_FILES; KEEP_WHOLE_PROJECT_GUARD',
        'remainingProof':['NATIVE_RUN_AND_CLEANUP','EXACT_GENERATED_SET','NON_TEXTURE_META_SCHEMAS','SERIALIZED_REFERENCE_CONSISTENCY',
                         'REFLECTION_RECEIPT_EXR_AND_DEPENDENCY_VALIDATION','SETTINGS_SAFE_FIELD_DIFF','FORMAL_G3_AND_ANDROID']}


def write_new(path, obj):
    raw = canonical(obj); require(len(raw) <= MAX_REPORT, 'REPORT_SIZE')
    destination = Path(path).absolute()
    # Output parent must already exist, be outside the input project, and have no
    # symlink ancestors. Caller supplies isolated private staging, never artifacts/**.
    with SecureTree(destination.parent) as parent:
        name = valid_path(destination.name)
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent.fds[''])
        try:
            at = 0
            while at < len(raw): at += os.write(fd, raw[at:])
            os.fsync(fd)
            written = os.fstat(fd)
            require(written.st_nlink == 1 and written.st_size == len(raw), 'OUTPUT_LINK_CHANGED')
            require(stamp(os.stat(name, dir_fd=parent.fds[''], follow_symlinks=False)) == stamp(written), 'OUTPUT_REPLACED')
            parent.identity_unchanged()
        finally: os.close(fd)
    return sha(raw)


class RedactedArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs['allow_abbrev'] = False
        super().__init__(*args, **kwargs)

    def error(self, message):
        # argparse's message may contain arbitrary caller data. Never echo it.
        raise Rejected('CLI_ARGUMENTS')

class Once(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        used = getattr(namespace, '_seen_options', None)
        if used is None: used = set(); setattr(namespace, '_seen_options', used)
        require(self.dest not in used, 'CLI_ARGUMENTS')
        used.add(self.dest); setattr(namespace, self.dest, values)


def main():
    try:
        argv = sys.argv[1:]
        if any(x.startswith(('-h', '--help')) for x in argv):
            require(argv in (['-h'], ['--help'], ['before','-h'], ['before','--help'], ['after','-h'], ['after','--help']), 'CLI_ARGUMENTS')
        parser = RedactedArgumentParser(description=__doc__)
        sub = parser.add_subparsers(dest='command', required=True)
        for name in ('before','after'):
            p = sub.add_parser(name)
            p.add_argument('--project', required=True, type=Path, action=Once)
            p.add_argument('--identity', required=True, type=Path, action=Once)
            p.add_argument('--output', required=True, type=Path, action=Once)
            if name == 'after':
                p.add_argument('--before', required=True, type=Path, action=Once)
                p.add_argument('--before-sha256', required=True, action=Once)
                p.add_argument('--native-exit', required=True, type=int, action=Once)
        args = parser.parse_args(argv)
        project = args.project.absolute(); output = args.output.absolute()
        require(project not in output.parents and output != project, 'OUTPUT_INSIDE_PROJECT')
        policy = load_policy(); ident = identity(parse_json(load_local(args.identity)))
        if args.command == 'before':
            result = snapshot(project, ident, policy, 'BEFORE')
        else:
            require(HEX64.fullmatch(args.before_sha256), 'BEFORE_EXPECTED_HASH')
            raw = load_local(args.before)
            require(sha(raw) == args.before_sha256, 'BEFORE_SNAPSHOT_TAMPERED')
            before = parse_json(raw)
            validate_before(before, ident, policy)
            after = snapshot(project, ident, policy, 'AFTER')
            result = compare(before, after, policy, args.native_exit)
            result['beforeSnapshotSha256'] = args.before_sha256
        checksum = write_new(output, result)
        print(json.dumps({'status':'CAPTURED_NOT_APPROVED','reportSha256':checksum}))
        # Zero means the BEFORE capture succeeded. AFTER always signals unresolved
        # review, so it cannot accidentally become a shell G3/pass gate.
        return 0 if args.command == 'before' else 2
    except Rejected as error:
        print(json.dumps({'status':'BLOCKED','code':str(error)})); return 3
    except (OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError):
        # No exception messages, filesystem names, file text, environment or logs.
        print(json.dumps({'status':'BLOCKED','code':'INPUT_OR_IO_REJECTED'})); return 3

if __name__ == '__main__': sys.exit(main())
