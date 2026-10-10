"""Bounded, read-only post-native source diagnostics; never a new source baseline."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / 'tasks/desert-rv'
PROJECT = TASK / 'unity'
REPORT = TASK / 'journey-tracer-source-report.json'
PREFIX = 'tasks/desert-rv/unity/'
MATERIAL = PREFIX + 'Assets/DesertRV/Art/Materials/JourneyNailTrajectory.mat'
SEMANTIC_PATHS = (PREFIX + 'Packages/manifest.json', PREFIX + 'Packages/packages-lock.json', MATERIAL, MATERIAL + '.meta')
MAX_REPORT = 65536
MAX_RECORDS = 64
MAX_FILES = 4096
MAX_ENTRIES = 12000
MAX_FILE_BYTES = 128 * 1024**2
MAX_TOTAL_BYTES = 1024**3
MAX_SEMANTIC_BYTES = 65536
MAX_SEMANTIC_CHANGES = 32

PACKAGE_NAMES = frozenset(('com.unity.burst', 'com.unity.collections', 'com.unity.ext.nunit', 'com.unity.mathematics', 'com.unity.modules.animation', 'com.unity.modules.audio', 'com.unity.modules.imageconversion', 'com.unity.modules.imgui', 'com.unity.modules.jsonserialize', 'com.unity.modules.particlesystem', 'com.unity.modules.physics', 'com.unity.modules.screencapture', 'com.unity.modules.terrain', 'com.unity.modules.ui', 'com.unity.nuget.mono-cecil', 'com.unity.render-pipelines.core', 'com.unity.render-pipelines.universal', 'com.unity.render-pipelines.universal-config', 'com.unity.sdk.linux-arm64', 'com.unity.sdk.linux-x86_64', 'com.unity.searcher', 'com.unity.shadergraph', 'com.unity.sysroot.base', 'com.unity.test-framework', 'com.unity.test-framework.performance', 'com.unity.toolchain.linux-x86_64-linux', 'com.unity.ugui'))
GUIDS = {'650dd9526735d5b46b79224bc6e94025', '08312e0642d110846fd9059c27072a1e', 'd0353a89b1f911e48b9e16bdc9f2e058'}
ASSET_IDS = {0, 2100000, 4800000, 11500000}
CHECKS = ('dispatchIdentity', 'initialState', 'pipelineProtected', 'initialSource', 'initialAssetUnion', 'emptyImportWorkspace')
ERRORS = {'NONE', 'ValueError', 'StrictError', 'FileNotFoundError', 'PermissionError', 'OSError', 'OtherError'}
TYPES = {'ABSENT', 'FILE', 'DIRECTORY', 'SYMLINK', 'OTHER', 'UNREADABLE', 'OVER_LIMIT'}
OPERATIONAL = {'Library', 'Temp', 'Logs', 'obj', 'UserSettings', 'JourneyEvidence'}
BYTECODE_ROOTS = {'tasks/desert-rv/scripts', 'tasks/desert-rv/art/import-candidate', 'tasks/desert-rv/art/journey-preparation'}
FIXTURE = re.compile(re.escape(PREFIX) + r'Assets/JourneyTracerTest_[0-9a-f]{32}\.unity(?:\.meta)?$')


def require(ok):
    if not ok:
        raise ValueError('TRACER_SOURCE_DIAGNOSTIC_REJECTED')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def safe_name(name):
    return isinstance(name, str) and len(name) <= 512 and '\\' not in name and not name.startswith('/') and all(
        part not in {'', '.', '..'} for part in name.split('/')) and all(ch.isprintable() for ch in name)


def json_bytes(raw):
    require(0 < len(raw) <= 4 * 1024**2)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result); result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: require(False))


def error_class(error):
    value = type(error).__name__
    return value if value in ERRORS else 'OtherError'


def attempt(action):
    try:
        action()
        return dict(status='PASS', errorClass='NONE')
    except Exception as error:
        return dict(status='FAIL', errorClass=error_class(error))


def pinned_baseline(env):
    """Authenticate HEAD's original request, without trusting native-modified files.

    This function only permits diagnostic reads. The unchanged admission helper is
    still checked independently and remains required by the original native gate.
    """
    import journey_tracer_dispatch as dispatch
    import verify_evidence as original
    git = lambda *args: dispatch.git(ROOT, *args)
    head = git('rev-parse', 'HEAD').decode().strip()
    parents = [line.split(' ', 1)[1] for line in git('cat-file', '-p', 'HEAD').decode().split('\n\n', 1)[0].splitlines() if line.startswith('parent ')]
    git('cat-file', '-e', dispatch.BASE + '^{commit}')
    raw = git('show', 'HEAD:' + dispatch.SOURCE)
    request = git('show', 'HEAD:' + dispatch.REQUEST)
    selection = git('show', 'HEAD:' + dispatch.SELECTION)
    present = subprocess.run(['git', 'cat-file', '-e', dispatch.BASE + ':' + dispatch.REQUEST], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    changed = git('diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').decode().splitlines()
    event = json_bytes(dispatch.safe_bytes(Path(env.get('GITHUB_EVENT_PATH', '')), 4 * 1024**2))
    dispatch.validate(env, event, head, parents, request, request, present, changed, sha(raw), sha(selection))
    source = json_bytes(raw)
    require(source.get('schema') == 'desert-rv-source-state/v1' and source.get('coverageRoots') == list(original.SOURCE_ROOTS) and source.get('coverageFiles') == list(original.SOURCE_FILES))
    require(source.get('baselineGameCommit') == original.BASELINE_COMMIT and source.get('baselineExportManifestSha256') == original.BASELINE_EXPORT_SHA)
    require(source.get('restoredFiles') == [dict(path=original.FONT_PATH, sha256=original.FONT_SHA, size=16437340)])
    require(type(source.get('files')) is list and 0 < len(source['files']) <= MAX_FILES)
    expected = {}
    for row in source['files'] + source['restoredFiles']:
        require(type(row) is dict and set(row) == {'path', 'sha256', 'size'})
        name = row['path']
        require(safe_name(name) and name not in expected and (name in original.SOURCE_FILES or any(name.startswith(root + '/') for root in original.SOURCE_ROOTS)))
        require(digest(row['sha256']) and type(row['size']) is int and 0 <= row['size'] <= MAX_FILE_BYTES)
        expected[name] = dict(type='FILE', sha256=row['sha256'], bytes=row['size'])
    public_name = 'tasks/desert-rv/PUBLIC-EXPORT.json'
    public_raw = git('show', 'HEAD:' + public_name)
    require(len(public_raw) <= 1024**2 and sha(public_raw) == original.BASELINE_EXPORT_SHA)
    for name, value in ((dispatch.SOURCE, raw), (dispatch.REQUEST, request), (public_name, public_raw)):
        expected[name] = dict(type='FILE', sha256=sha(value), bytes=len(value))
    return source, expected, sha(raw)


def observation(path, budget):
    """Never follow links, read devices/FIFOs, or print a link target."""
    value = dict(type='ABSENT', sha256='', bytes=0)
    try:
        if any(parent.is_symlink() for parent in path.parents):
            return dict(type='UNREADABLE', sha256='', bytes=None)
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            target = os.readlink(path).encode('utf-8', 'surrogateescape')
            return dict(type='SYMLINK', sha256=sha(target), bytes=info.st_size)
        if stat.S_ISDIR(info.st_mode):
            return dict(type='DIRECTORY', sha256='', bytes=0)
        if not stat.S_ISREG(info.st_mode):
            return dict(type='OTHER', sha256='', bytes=info.st_size)
        if info.st_size > MAX_FILE_BYTES or info.st_size > budget['remaining']:
            budget['complete'] = False
            return dict(type='OVER_LIMIT', sha256='', bytes=info.st_size)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            require(stat.S_ISREG(opened.st_mode) and (opened.st_dev, opened.st_ino, opened.st_size) == (info.st_dev, info.st_ino, info.st_size))
            h = hashlib.sha256(); count = 0
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk: break
                count += len(chunk)
                require(count <= info.st_size and count <= budget['remaining'])
                h.update(chunk)
            require(count == info.st_size and os.fstat(stream.fileno()).st_mtime_ns == opened.st_mtime_ns)
        budget['remaining'] -= count
        return dict(type='FILE', sha256=h.hexdigest(), bytes=count)
    except FileNotFoundError:
        return value
    except Exception:
        budget['complete'] = False
        return dict(type='UNREADABLE', sha256='', bytes=None)


def expected_directories(expected):
    result = {PREFIX + name for name in ('Assets', 'Packages', 'ProjectSettings')}
    for name in expected:
        result.update(parent.as_posix() for parent in Path(name).parents if parent != Path('.'))
    return result


def scan_paths(source):
    """Source roots only. Unity operational trees are not report contents."""
    names = set(); complete = True; visited = 0
    pending = []
    for name in source['coverageRoots']:
        if name != PREFIX[:-1]: pending.append((ROOT / name, name in BYTECODE_ROOTS))
    unity = ROOT / PREFIX[:-1]
    names.add(PREFIX[:-1])
    try:
        require(unity.is_dir() and not any(path.is_symlink() for path in (unity, *unity.parents)))
        for entry in os.scandir(unity):
            name = PREFIX + entry.name; names.add(name)
            mode = entry.stat(follow_symlinks=False).st_mode
            if entry.name in {'Assets', 'Packages', 'ProjectSettings'} and stat.S_ISDIR(mode): pending.append((Path(entry.path), False))
            elif entry.name in OPERATIONAL and stat.S_ISDIR(mode): names.discard(name)
    except Exception:
        complete = False
    while pending:
        folder, prune_bytecode = pending.pop()
        names.add(folder.relative_to(ROOT).as_posix())
        if any(path.is_symlink() for path in (folder, *folder.parents)) or not folder.is_dir():
            complete = False; continue
        try:
            entries = list(os.scandir(folder))
            require(len(entries) <= MAX_ENTRIES)
            for entry in entries:
                visited += 1
                if visited > MAX_ENTRIES: return names, False
                mode = entry.stat(follow_symlinks=False).st_mode
                if prune_bytecode and entry.name == '__pycache__' and stat.S_ISDIR(mode): continue
                path = Path(entry.path); name = path.relative_to(ROOT).as_posix(); names.add(name)
                if stat.S_ISDIR(mode): pending.append((path, prune_bytecode))
        except Exception:
            complete = False
    return names, complete


def version(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:-(?:pre|exp|preview)\.[0-9]{1,4})?', value) is not None


def semantic_value(value, rule):
    if value is None: return None
    if rule == 'version' and version(value): return value
    if rule == 'number' and type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1000000: return value
    if rule == 'color' and type(value) in (int, float) and math.isfinite(value) and abs(value) <= 10: return value
    if rule == 'guid' and isinstance(value, str) and value in GUIDS: return value
    if rule == 'asset_id' and type(value) is int and value in ASSET_IDS: return value
    if isinstance(rule, set) and isinstance(value, str) and value in rule: return value
    return '<redacted>'


def package_fields(raw, known, lock):
    value = json_bytes(raw); require(type(value) is dict and type(value.get('dependencies')) is dict)
    fields = {}
    for name in sorted(known):
        row = value['dependencies'].get(name)
        if not lock:
            fields['dependencies.' + name] = semantic_value(row, 'version'); continue
        require(row is None or type(row) is dict)
        for key, rule in (('version', 'version'), ('depth', 'number'), ('source', {'builtin', 'registry', 'git', 'local', 'embedded'}), ('url', {'https://packages.unity.com'})):
            fields['dependencies.' + name + '.' + key] = semantic_value(None if row is None else row.get(key), rule)
        deps = {} if row is None else row.get('dependencies', {})
        require(type(deps) is dict)
        for dependency in sorted(known):
            if dependency in deps: fields['dependencies.' + name + '.dependencies.' + dependency] = semantic_value(deps[dependency], 'version')
    return fields


def material_fields(raw, meta):
    import yaml
    text = raw.decode('utf-8')
    text = re.sub(r'^%(?:YAML|TAG)[^\n]*\n', '', text, flags=re.M)
    text = re.sub(r'^--- !u![0-9]+ &-?[0-9]+\s*$', '---', text, flags=re.M)
    docs = list(yaml.safe_load_all(text)); require(0 < len(docs) <= 2 and all(type(item) is dict for item in docs))
    fields = {}
    if meta:
        require(len(docs) == 1); value = docs[0]
        fields['fileFormatVersion'] = semantic_value(value.get('fileFormatVersion'), 'number')
        fields['guid'] = semantic_value(value.get('guid'), 'guid')
        imp = value.get('NativeFormatImporter', {}); require(type(imp) is dict)
        fields['NativeFormatImporter.mainObjectFileID'] = semantic_value(imp.get('mainObjectFileID'), 'asset_id')
        # userData and bundle names are deliberately excluded, even if altered.
        return fields
    value = next((item['Material'] for item in docs if 'Material' in item), None); require(type(value) is dict)
    numeric = ('serializedVersion', 'm_ObjectHideFlags', 'm_ModifiedSerializedProperties', 'm_LightmapFlags', 'm_EnableInstancingVariants', 'm_DoubleSidedGI', 'm_CustomRenderQueue', 'm_AllowLocking')
    for key in numeric: fields['Material.' + key] = semantic_value(value.get(key), 'number')
    fields['Material.m_Name'] = semantic_value(value.get('m_Name'), {'JourneyNailTrajectory'})
    shader = value.get('m_Shader', {}); require(type(shader) is dict)
    for key, rule in (('fileID', 'asset_id'), ('guid', 'guid'), ('type', 'number')): fields['Material.m_Shader.' + key] = semantic_value(shader.get(key), rule)
    tags = value.get('stringTagMap', {}); require(type(tags) is dict)
    fields['Material.stringTagMap.RenderType'] = semantic_value(tags.get('RenderType'), {'Opaque', 'Transparent', 'TransparentCutout'})
    saved = value.get('m_SavedProperties', {}); require(type(saved) is dict)
    floats = saved.get('m_Floats', []); require(type(floats) is list and len(floats) <= 128)
    allowed = {'_AddPrecomputedVelocity', '_AlphaClip', '_AlphaToMask', '_Blend', '_BlendOp', '_Cull', '_Cutoff', '_DstBlend', '_DstBlendAlpha', '_QueueOffset', '_SampleGI', '_SrcBlend', '_SrcBlendAlpha', '_Surface', '_XRMotionVectorsPass', '_ZWrite'}
    for row in floats:
        require(type(row) is dict and len(row) == 1)
        for key in row:
            if key in allowed: fields['Material.m_Floats.' + key] = semantic_value(row[key], 'number')
    colors = saved.get('m_Colors', []); require(type(colors) is list and len(colors) <= 128)
    for row in colors:
        require(type(row) is dict and len(row) == 1)
        for key in row:
            if key in {'_BaseColor', '_Color'}:
                require(type(row[key]) is dict)
                for channel in ('r', 'g', 'b', 'a'): fields['Material.m_Colors.' + key + '.' + channel] = semantic_value(row[key].get(channel), 'color')
    asset = next((item['MonoBehaviour'] for item in docs if 'MonoBehaviour' in item), {})
    require(type(asset) is dict)
    fields['AssetVersion.version'] = semantic_value(asset.get('version'), 'number')
    script = asset.get('m_Script', {}); require(type(script) is dict)
    fields['AssetVersion.m_Script.guid'] = semantic_value(script.get('guid'), 'guid')
    fields['AssetVersion.m_EditorClassIdentifier'] = semantic_value(asset.get('m_EditorClassIdentifier'), {'Unity.RenderPipelines.Universal.Editor::UnityEditor.Rendering.Universal.AssetVersion'})
    return fields


def semantic_diff(name, before, after):
    value = dict(status='NOT_ALLOWLISTED', changes=[], truncated=False, otherChangesPossible=True)
    if name not in SEMANTIC_PATHS: return value
    value['status'] = 'UNAVAILABLE'
    try:
        require(before['type'] == after['type'] == 'FILE' and before['bytes'] <= MAX_SEMANTIC_BYTES and after['bytes'] <= MAX_SEMANTIC_BYTES)
        import journey_tracer_dispatch as dispatch
        original = dispatch.git(ROOT, 'show', 'HEAD:' + name)
        path = ROOT / name; require(not any(p.is_symlink() for p in (path, *path.parents)))
        require(path.stat().st_size <= MAX_SEMANTIC_BYTES)
        with path.open('rb') as stream: current = stream.read(MAX_SEMANTIC_BYTES + 1)
        require(len(original) <= MAX_SEMANTIC_BYTES and len(current) <= MAX_SEMANTIC_BYTES and sha(original) == before['sha256'] and sha(current) == after['sha256'])
        if name in SEMANTIC_PATHS[:2]:
            original_json = json_bytes(original); known = set(PACKAGE_NAMES)
            require(all(re.fullmatch(r'com\.unity\.[a-z0-9._-]{1,100}', key) for key in known))
            if name.endswith('packages-lock.json'):
                for row in original_json['dependencies'].values():
                    require(type(row) is dict)
                    require(type(row.get('dependencies', {})) is dict)
            require(len(known) <= 128 and all(re.fullmatch(r'com\.unity\.[a-z0-9._-]{1,100}', key) for key in known))
            left, right = (package_fields(raw, known, name.endswith('packages-lock.json')) for raw in (original, current))
        else:
            left, right = (material_fields(raw, name.endswith('.meta')) for raw in (original, current))
        changes = [dict(field=field, before=left.get(field), after=right.get(field)) for field in sorted(set(left) | set(right)) if left.get(field) != right.get(field)]
        value.update(status='ALLOWLIST_ONLY', changes=changes[:MAX_SEMANTIC_CHANGES], truncated=len(changes) > MAX_SEMANTIC_CHANGES)
    except Exception:
        pass
    return value


def collect_changes(source, expected):
    allowed_dirs = expected_directories(expected)
    observed, complete = scan_paths(source)
    budget = dict(remaining=MAX_TOTAL_BYTES, complete=True)
    records = []; counts = dict(declaredSource=0, fixtureResidue=0, undeclared=0)
    order = list(SEMANTIC_PATHS) + sorted(set(expected) - set(SEMANTIC_PATHS))
    for name in order:
        if name not in expected: continue
        after = observation(ROOT / name, budget); before = expected[name]
        if before != after:
            counts['declaredSource'] += 1
            records.append(dict(category='DECLARED_SOURCE', path=name, pathSha256=sha(name.encode()), before=before, after=after, semantics=semantic_diff(name, before, after)))
    for name in sorted(observed - set(expected)):
        after = observation(ROOT / name, budget)
        if name in allowed_dirs and after['type'] == 'DIRECTORY': continue
        directory = name in allowed_dirs
        fixture = FIXTURE.fullmatch(name) is not None
        counts['declaredSource' if directory else 'fixtureResidue' if fixture else 'undeclared'] += 1
        records.append(dict(category='DECLARED_SOURCE' if directory else 'FIXTURE_RESIDUE' if fixture else 'UNDECLARED', path=name if directory or fixture else None, pathSha256=sha(name.encode('utf-8', 'surrogateescape')), before=dict(type='DIRECTORY' if directory else 'ABSENT', sha256='', bytes=0), after=after, semantics=dict(status='NOT_ALLOWLISTED', changes=[], truncated=False, otherChangesPossible=True)))
    return dict(complete=complete and budget['complete'], truncated=len(records) > MAX_RECORDS,
                observedChanges=counts, records=records[:MAX_RECORDS])


def check_original_gates(env, source):
    sys.path[:0] = [str(TASK / 'art/journey-preparation'), str(TASK / 'scripts/rendered')]
    import journey_tracer_dispatch as dispatch
    import pipeline
    import prepared_source
    results = {key: dict(status='FAIL', errorClass='OtherError') for key in CHECKS}
    results['dispatchIdentity'] = attempt(lambda: dispatch.verify(ROOT, env))
    state = None
    try:
        state = pipeline.state()
        require(state.get('completed') == [] and state.get('assetFiles') == {} and 'phase' not in state)
        results['initialState'] = dict(status='PASS', errorClass='NONE')
    except Exception as error:
        results['initialState'] = dict(status='FAIL', errorClass=error_class(error))
    if state is not None:
        results['pipelineProtected'] = attempt(lambda: pipeline.check_state(state))
        results['initialSource'] = attempt(lambda: prepared_source.verify_original(state['initialIdentity']))
        results['initialAssetUnion'] = attempt(lambda: prepared_source.verify_asset_union(source, state['initialSourceDirectories'], {}))
    def empty():
        require(pipeline.import_inventory() == {})
        for path in (PROJECT / 'CandidateImportInput', PROJECT / 'CandidatePackageSnapshot', PROJECT / 'JourneyEvidence/CandidateArt', PROJECT / 'Assets/DesertRV/Scenes/Journey'):
            require(not path.exists() and not path.is_symlink())
    results['emptyImportWorkspace'] = attempt(empty)
    return results


def blank_report(env):
    commit, run, attempt_id = (env.get(key, '') for key in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'))
    require(isinstance(commit, str) and re.fullmatch('[0-9a-f]{40}', commit) and isinstance(run, str) and re.fullmatch('[1-9][0-9]{0,19}', run) and attempt_id == '1')
    outcome = env.get('NATIVE_OUTCOME')
    return dict(schema=1, status='SOURCE_UNVERIFIED', sourceCommit=commit, runId=run, runAttempt='1',
                nativeOutcome=outcome if outcome in {'success', 'failure', 'cancelled', 'skipped'} else 'unknown',
                baseline='ORIGINAL_HEAD_SOURCE_STATE', baselineSourceStateSha256='', baselineAuthenticated=False,
                sourceUnchanged=False, complete=False, truncated=False, errorClass='NONE',
                checks={key: dict(status='NOT_RUN', errorClass='NONE') for key in CHECKS},
                observedChanges=dict(declaredSource=0, fixtureResidue=0, undeclared=0), records=[])


def allowed_semantic_field(name, field):
    if name in SEMANTIC_PATHS[:2]:
        if name.endswith('manifest.json'):
            return field in {'dependencies.' + package for package in PACKAGE_NAMES}
        return (field in {'dependencies.' + package + '.' + key for package in PACKAGE_NAMES for key in ('version', 'depth', 'source', 'url')} or
                field in {'dependencies.' + package + '.dependencies.' + dependency for package in PACKAGE_NAMES for dependency in PACKAGE_NAMES})
    if name == MATERIAL + '.meta':
        return field in {'fileFormatVersion', 'guid', 'NativeFormatImporter.mainObjectFileID'}
    if name != MATERIAL: return False
    scalars = {'Material.' + key for key in ('serializedVersion', 'm_ObjectHideFlags', 'm_ModifiedSerializedProperties', 'm_LightmapFlags', 'm_EnableInstancingVariants', 'm_DoubleSidedGI', 'm_CustomRenderQueue', 'm_AllowLocking', 'm_Name')}
    scalars |= {'Material.m_Shader.' + key for key in ('fileID', 'guid', 'type')}
    scalars |= {'Material.stringTagMap.RenderType', 'AssetVersion.version', 'AssetVersion.m_Script.guid', 'AssetVersion.m_EditorClassIdentifier'}
    scalars |= {'Material.m_Floats.' + key for key in ('_AddPrecomputedVelocity', '_AlphaClip', '_AlphaToMask', '_Blend', '_BlendOp', '_Cull', '_Cutoff', '_DstBlend', '_DstBlendAlpha', '_QueueOffset', '_SampleGI', '_SrcBlend', '_SrcBlendAlpha', '_Surface', '_XRMotionVectorsPass', '_ZWrite')}
    scalars |= {'Material.m_Colors.' + key + '.' + channel for key in ('_BaseColor', '_Color') for channel in ('r', 'g', 'b', 'a')}
    return field in scalars


def validate_report(value, allowed_paths=None):
    require(type(value) is dict)
    expected = blank_report(dict(GITHUB_SHA=value['sourceCommit'], GITHUB_RUN_ID=value['runId'], GITHUB_RUN_ATTEMPT=value['runAttempt'], NATIVE_OUTCOME=value['nativeOutcome']))
    require(set(value) == set(expected) and type(value['schema']) is int and value['schema'] == 1 and value['baseline'] == 'ORIGINAL_HEAD_SOURCE_STATE')
    require(value['nativeOutcome'] == expected['nativeOutcome'] and value['status'] in {'SOURCE_UNCHANGED', 'SOURCE_CHANGED', 'SOURCE_UNVERIFIED'} and value['errorClass'] in ERRORS)
    require(all(type(value[key]) is bool for key in ('baselineAuthenticated', 'sourceUnchanged', 'complete', 'truncated')))
    require(value['baselineSourceStateSha256'] == '' or digest(value['baselineSourceStateSha256']))
    require(type(value['checks']) is dict and set(value['checks']) == set(CHECKS))
    for row in value['checks'].values():
        require(type(row) is dict and set(row) == {'status', 'errorClass'} and row['status'] in {'PASS', 'FAIL', 'NOT_RUN'} and row['errorClass'] in ERRORS)
        require((row['status'] == 'FAIL') == (row['errorClass'] != 'NONE'))
    require(type(value['observedChanges']) is dict and set(value['observedChanges']) == {'declaredSource', 'fixtureResidue', 'undeclared'} and all(type(count) is int and 0 <= count <= MAX_ENTRIES + MAX_FILES for count in value['observedChanges'].values()))
    require(type(value['records']) is list and len(value['records']) <= MAX_RECORDS)
    seen = set()
    for row in value['records']:
        require(type(row) is dict and set(row) == {'category', 'path', 'pathSha256', 'before', 'after', 'semantics'} and digest(row['pathSha256']) and row['pathSha256'] not in seen)
        seen.add(row['pathSha256'])
        require(row['category'] in {'DECLARED_SOURCE', 'FIXTURE_RESIDUE', 'UNDECLARED'})
        if row['category'] == 'UNDECLARED': require(row['path'] is None)
        else:
            require(safe_name(row['path']) and sha(row['path'].encode()) == row['pathSha256'])
            if row['category'] == 'FIXTURE_RESIDUE': require(FIXTURE.fullmatch(row['path']) is not None)
            else: require(allowed_paths is not None and row['path'] in allowed_paths)
        for item in (row['before'], row['after']):
            require(type(item) is dict and set(item) == {'type', 'sha256', 'bytes'} and item['type'] in TYPES)
            require(item['sha256'] == '' or digest(item['sha256']))
            require(item['bytes'] is None or type(item['bytes']) is int and 0 <= item['bytes'] <= 2**63 - 1)
            require((item['type'] in {'FILE', 'SYMLINK'}) == bool(item['sha256']))
        semantic = row['semantics']
        require(type(semantic) is dict and set(semantic) == {'status', 'changes', 'truncated', 'otherChangesPossible'} and semantic['status'] in {'NOT_ALLOWLISTED', 'UNAVAILABLE', 'ALLOWLIST_ONLY'})
        require(type(semantic['truncated']) is bool and semantic['otherChangesPossible'] is True and type(semantic['changes']) is list and len(semantic['changes']) <= MAX_SEMANTIC_CHANGES)
        require(semantic['status'] != 'ALLOWLIST_ONLY' or row['category'] == 'DECLARED_SOURCE' and row['path'] in SEMANTIC_PATHS)
        require(semantic['status'] == 'ALLOWLIST_ONLY' or not semantic['changes'] and not semantic['truncated'])
        require(not semantic['changes'] or row['category'] == 'DECLARED_SOURCE' and row['path'] in SEMANTIC_PATHS and semantic['status'] == 'ALLOWLIST_ONLY')
        for change in semantic['changes']:
            require(type(change) is dict and set(change) == {'field', 'before', 'after'} and isinstance(change['field'], str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,300}', change['field']))
            require(allowed_semantic_field(row['path'], change['field']))
            for item in (change['before'], change['after']):
                require(item is None or type(item) in (int, float) and math.isfinite(item) and (abs(item) <= 1000000 or item in ASSET_IDS) or isinstance(item, str) and (version(item) or item in GUIDS or item in {'<redacted>', 'builtin', 'registry', 'git', 'local', 'embedded', 'https://packages.unity.com', 'JourneyNailTrajectory', 'Opaque', 'Transparent', 'TransparentCutout', 'Unity.RenderPipelines.Universal.Editor::UnityEditor.Rendering.Universal.AssetVersion'}))
    categories = {'DECLARED_SOURCE': 'declaredSource', 'FIXTURE_RESIDUE': 'fixtureResidue', 'UNDECLARED': 'undeclared'}
    actual_counts = {key: sum(row['category'] == category for row in value['records']) for category, key in categories.items()}
    require(all(actual_counts[key] <= value['observedChanges'][key] for key in actual_counts))
    require(value['truncated'] or actual_counts == value['observedChanges'])
    require(len(value['records']) <= sum(value['observedChanges'].values()))
    require(value['truncated'] == (len(value['records']) < sum(value['observedChanges'].values())))
    clean = value['baselineAuthenticated'] and value['complete'] and not value['truncated'] and value['errorClass'] == 'NONE' and not any(value['observedChanges'].values()) and all(row['status'] == 'PASS' for row in value['checks'].values())
    require(value['sourceUnchanged'] == clean and value['status'] == ('SOURCE_UNCHANGED' if clean else 'SOURCE_CHANGED' if any(value['observedChanges'].values()) else 'SOURCE_UNVERIFIED'))
    require(not value['baselineAuthenticated'] or digest(value['baselineSourceStateSha256']))
    if not value['baselineAuthenticated']: require(not value['records'] and value['baselineSourceStateSha256'] == '')
    require(len(json.dumps(value, separators=(',', ':')).encode()) <= MAX_REPORT)
    return value


def run(env):
    value = blank_report(env); allowed_paths = None
    try:
        source, expected, source_sha = pinned_baseline(env)
        allowed_paths = set(expected) | expected_directories(expected)
        value.update(baselineAuthenticated=True, baselineSourceStateSha256=source_sha)
        # Deliberately independent of NATIVE_OUTCOME and of each other.
        value['checks'] = check_original_gates(env, source)
        value.update(collect_changes(source, expected))
        clean = value['complete'] and not value['truncated'] and not any(value['observedChanges'].values()) and all(row['status'] == 'PASS' for row in value['checks'].values())
        value.update(sourceUnchanged=clean, status='SOURCE_UNCHANGED' if clean else 'SOURCE_CHANGED' if any(value['observedChanges'].values()) else 'SOURCE_UNVERIFIED')
    except Exception as error:
        value['errorClass'] = error_class(error)
    while len(json.dumps(value, separators=(',', ':')).encode()) + 1 > MAX_REPORT and value['records']:
        value['records'].pop(); value['truncated'] = True; value['sourceUnchanged'] = False; value['status'] = 'SOURCE_CHANGED'
    validate_report(value, allowed_paths)
    raw = (json.dumps(value, separators=(',', ':'), sort_keys=True) + '\n').encode()
    require(len(raw) <= MAX_REPORT and not any(path.is_symlink() for path in (REPORT, *REPORT.parents)))
    with REPORT.open('xb') as stream: stream.write(raw)
    require(REPORT.read_bytes() == raw)
    validate_report(json_bytes(REPORT.read_bytes()), allowed_paths)
    with open(env['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
        stream.write('report_written=true\nreport_valid=true\nsource_unchanged=' + ('true' if value['sourceUnchanged'] else 'false') + '\n')
    return 0 if value['sourceUnchanged'] else 2


if __name__ == '__main__':
    try:
        code = run(os.environ)
    except Exception:
        print('TRACER_SOURCE_REPORT_UNAVAILABLE')
        code = 2
    raise SystemExit(code)
