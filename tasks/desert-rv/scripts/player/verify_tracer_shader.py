#!/usr/bin/env python3
"""Read-only, fail-closed URP Unlit inclusion gate for the fixed Linux export.

Self-authored bounded parser for the observed serialized-v22/no-type-tree layout.
Format reference: AssetStudio/SerializedFile.cs (metadata layout only).
Class IDs: Unity Manual/ClassIDReference.html (94 registry, 48 shader).
No shader program decoding, archive extraction, player execution, or rendering proof.
"""
import hashlib
import json
import os
import pathlib
import re
import struct
import sys
import tarfile

TARGET = 'Universal Render Pipeline/Unlit'
UNITY = '6000.3.19f1'
GLOBAL = 'DesertRV_Data/globalgamemanagers'
MATERIAL = 'Assets/DesertRV/Art/Materials/JourneyNailTrajectory.mat'
SHADER = 'Packages/com.unity.render-pipelines.universal/Shaders/Unlit.shader'
SHADER_GUID = '650dd9526735d5b46b79224bc6e94025'
REPORT_NAME = 'journey-tracer-shader-report.json'
MAX_ASSET_BYTES = 128 * 1024**2
MAX_METADATA_BYTES = 32 * 1024**2
MAX_JSON_BYTES = 4 * 1024**2
MANIFEST_KEYS = {'schema', 'label', 'sourceCommit', 'producerRunUrl',
                 'nativeReceiptSha256', 'inputSha256', 'generatedReceiptSha256',
                 'sourceStateSha256', 'bundleSha256', 'bundleBytes', 'files',
                 'nativeReceipt', 'playerExecuted', 'approved'}
CODES = frozenset(('NONE ARGUMENTS_INVALID EXPORT_NOT_SUCCESS IDENTITY_INVALID '
                  'PACKAGE_INVALID PACKAGE_CHANGED JSON_INVALID IO_UNAVAILABLE '
                  'SERIALIZED_SIZE SERIALIZED_HEADER SERIALIZED_VERSION '
                  'SERIALIZED_ENDIAN SERIALIZED_METADATA SERIALIZED_UNITY '
                  'SERIALIZED_PLATFORM SERIALIZED_TYPE_TREE SERIALIZED_COUNT '
                  'SERIALIZED_TYPE SERIALIZED_OBJECT SERIALIZED_OVERLAP '
                  'SERIALIZED_EXTERNAL SERIALIZED_REF_TYPES SERIALIZED_STRING '
                  'SERIALIZED_TRUNCATED REGISTRY_COUNT REGISTRY_NAME '
                  'REGISTRY_DUPLICATE REGISTRY_POINTER REGISTRY_TRAILING '
                  'MISSING_SHADER SHADER_NULL SHADER_FILE_MISSING '
                  'SHADER_OBJECT_MISSING SHADER_CLASS_MISMATCH '
                  'DEPENDENCY_INVALID INTERNAL_ERROR').split())


class Rejected(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def check(condition, code):
    if not condition:
        raise Rejected(code)


def digest(value, width=64):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{%d}' % width, value) is not None


def number(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def safe_relative(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_./ +()\-]{1,256}', name):
        return False
    parts = name.split('/')
    return all(part and not part.startswith('.') for part in parts) and '\\' not in name


class Reader:
    """Every operation is confined to its metadata or object boundary."""
    def __init__(self, data, start=0, end=None):
        self.data, self.pos = data, start
        self.end = len(data) if end is None else end
        check(0 <= start <= self.end <= len(data), 'SERIALIZED_TRUNCATED')

    def take(self, length):
        check(number(length, 0, self.end - self.pos), 'SERIALIZED_TRUNCATED')
        result = self.data[self.pos:self.pos + length]
        self.pos += length
        return result

    def unpack(self, fmt):
        values = struct.unpack(fmt, self.take(struct.calcsize(fmt)))
        return values[0] if len(values) == 1 else values

    def align(self):
        check(not any(self.take((-self.pos) % 4)), 'SERIALIZED_METADATA')

    def cstring(self, limit=256):
        end = self.data.find(b'\0', self.pos, min(self.end, self.pos + limit + 1))
        check(end >= 0, 'SERIALIZED_STRING')
        raw = self.take(end - self.pos)
        self.take(1)
        try:
            text = raw.decode('utf-8')
        except UnicodeError:
            raise Rejected('SERIALIZED_STRING') from None
        check(all(ch.isprintable() for ch in text), 'SERIALIZED_STRING')
        return text

    def count(self, maximum):
        value = self.unpack('<i')
        check(number(value, 0, maximum), 'SERIALIZED_COUNT')
        return value


def serialized(data):
    check(type(data) is bytes and 48 <= len(data) <= MAX_ASSET_BYTES, 'SERIALIZED_SIZE')
    legacy_meta, legacy_size, version, legacy_offset = struct.unpack_from('>IIII', data)
    check(version == 22, 'SERIALIZED_VERSION')
    check((legacy_meta, legacy_size, legacy_offset) == (0, 0, 0), 'SERIALIZED_HEADER')
    check(data[16] == 0 and data[17:20] == b'\0' * 3, 'SERIALIZED_ENDIAN')
    meta_size, file_size, data_offset, reserved = struct.unpack_from('>Iqqq', data, 20)
    check(file_size == len(data) and reserved == 0, 'SERIALIZED_HEADER')
    end = 48 + meta_size
    check(0 < meta_size <= MAX_METADATA_BYTES and end <= data_offset <= file_size and
          data_offset % 16 == 0 and 0 <= data_offset - end < 16 and
          not any(data[end:data_offset]), 'SERIALIZED_METADATA')
    r = Reader(data, 48, end)
    check(r.cstring(32) == UNITY, 'SERIALIZED_UNITY')
    check(r.unpack('<i') == 24, 'SERIALIZED_PLATFORM')
    check(r.unpack('<B') == 0, 'SERIALIZED_TYPE_TREE')
    classes = []
    for _ in range(r.count(4096)):
        class_id, stripped, script_index = r.unpack('<iBh')
        check(class_id >= 0 and stripped in (0, 1) and script_index >= -1, 'SERIALIZED_TYPE')
        r.take(32 if class_id == 114 else 16)
        classes.append(class_id)
    objects = {}
    spans = []
    for _ in range(r.count(250000)):
        r.align()
        path_id, relative, size, type_index = r.unpack('<qqIi')
        check(path_id != 0 and path_id not in objects and 0 <= type_index < len(classes), 'SERIALIZED_OBJECT')
        offset = data_offset + relative
        check(relative >= 0 and data_offset <= offset <= offset + size <= len(data), 'SERIALIZED_OBJECT')
        objects[path_id] = dict(classId=classes[type_index], offset=offset, bytes=size)
        if size:
            spans.append((offset, offset + size))
    spans.sort()
    check(all(left[1] <= right[0] for left, right in zip(spans, spans[1:])), 'SERIALIZED_OVERLAP')
    for _ in range(r.count(250000)):
        check(r.unpack('<i') >= 0, 'SERIALIZED_METADATA')
        r.align()
        r.unpack('<q')
    externals = []
    for _ in range(r.count(4096)):
        check(r.cstring() == '', 'SERIALIZED_EXTERNAL')
        r.take(16)
        check(r.unpack('<i') in (0, 1, 2, 3), 'SERIALIZED_EXTERNAL')
        name = r.cstring()
        check(safe_relative(name) and name not in externals, 'SERIALIZED_EXTERNAL')
        externals.append(name)
    # Unsupported reference type tables fail explicitly rather than skip unchecked bytes.
    check(r.count(4096) == 0, 'SERIALIZED_REF_TYPES')
    check(r.cstring() == '' and r.pos == end, 'SERIALIZED_METADATA')
    return dict(objects=objects, externals=externals)


def registry(data, meta):
    candidates = [(key, row) for key, row in meta['objects'].items() if row['classId'] == 94]
    check(len(candidates) == 1, 'REGISTRY_COUNT')
    path_id, row = candidates[0]
    check(5 <= row['bytes'] <= 4 * 1024**2, 'REGISTRY_COUNT')
    r = Reader(data, row['offset'], row['offset'] + row['bytes'])
    count = r.unpack('<i')
    check(number(count, 1, 10000), 'REGISTRY_COUNT')
    entries = {}
    for _ in range(count):
        file_id, object_id, length = r.unpack('<iqi')
        check(0 <= file_id <= len(meta['externals']) and object_id >= 0, 'REGISTRY_POINTER')
        check(number(length, 1, 2048), 'REGISTRY_NAME')
        try:
            name = r.take(length).decode('utf-8')
        except UnicodeError:
            raise Rejected('REGISTRY_NAME') from None
        check(all(ch.isprintable() for ch in name), 'REGISTRY_NAME')
        check(name not in entries, 'REGISTRY_DUPLICATE')
        r.align()
        entries[name] = (file_id, object_id)
    # Exactly the observed final zero byte; no unbounded or guessed tail format.
    check(r.take(r.end - r.pos) == b'\0', 'REGISTRY_TRAILING')
    return entries, dict(path=GLOBAL, sha256=sha_bytes(data), bytes=len(data),
                         serializedVersion=22, unityVersion=UNITY, target=24,
                         registryClassId=94, registryPathId=path_id,
                         registryObjectBytes=row['bytes'], entryCount=count)


def resolve_shader(load, meta, entries, name):
    """Internal diagnostic parameter; the CLI always checks TARGET."""
    check(name in entries, 'MISSING_SHADER')
    file_id, path_id = entries[name]
    check(path_id != 0, 'SHADER_NULL')
    asset_name = GLOBAL if file_id == 0 else 'DesertRV_Data/' + meta['externals'][file_id - 1]
    check(safe_relative(asset_name), 'SERIALIZED_EXTERNAL')
    data = load(asset_name)
    asset_meta = meta if file_id == 0 else serialized(data)
    check(path_id in asset_meta['objects'], 'SHADER_OBJECT_MISSING')
    obj = asset_meta['objects'][path_id]
    check(obj['classId'] == 48 and obj['bytes'] > 0, 'SHADER_CLASS_MISMATCH')
    return dict(path=asset_name, sha256=sha_bytes(data), bytes=len(data),
                fileId=file_id, pathId=path_id, classId=48,
                objectOffset=obj['offset'], objectBytes=obj['bytes'])


def strict_json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            check(key not in value, 'JSON_INVALID')
            value[key] = item
        return value
    check(len(raw) <= MAX_JSON_BYTES, 'JSON_INVALID')
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: check(False, 'JSON_INVALID'))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise Rejected('JSON_INVALID') from None


def read_sealed(path, exporter, limit=MAX_JSON_BYTES):
    path = exporter.safe(path)
    check(path.stat().st_size <= limit, 'PACKAGE_INVALID')
    raw = path.read_bytes()
    check(len(raw) <= limit, 'PACKAGE_INVALID')
    return raw, strict_json(raw)


def empty_report():
    return dict(schema=1, status='FAILED', failureCode='INTERNAL_ERROR', targetShader=TARGET,
                sourceCommit='', producerRunUrl='', packageValidated=False, packagePins=[],
                registry=None, resolvedShader=None, nativeDependencies=None,
                shaderRegistryPass=False, playerExecuted=False, renderingVerified=False)


def dependency_proof(folder, project, exporter, native):
    raw, generated = read_sealed(folder / 'receipt.json', exporter)
    check(sha_bytes(raw) == native['generatedReceiptSha256'], 'DEPENDENCY_INVALID')
    check(generated['schema'] == 'desert-rv-generated-journey/v1' and
          generated['status'] == 'GENERATED_JOURNEY_SAVED_UNREVIEWED' and generated['approved'] is False and
          generated['unityVersion'] == UNITY and generated['sourceCommit'] == native['sourceCommit'] and
          generated['importRunUrl'] == native['producerRunUrl'] and
          generated['nativeManifestPath'] == 'native-authored-assets.json', 'DEPENDENCY_INVALID')
    native_raw, authored = read_sealed(folder / 'native-authored-assets.json', exporter)
    check(sha_bytes(native_raw) == generated['nativeManifestSha256'] and
          type(authored['schema']) is int and authored['schema'] == 3 and
          authored['status'] == 'ACTUAL_NATIVE_JOURNEY_ASSETS_UNREVIEWED' and
          authored['sourceCommit'] == native['sourceCommit'] and authored['importRunUrl'] == native['producerRunUrl'] and
          authored['unityVersion'] == UNITY and authored['approved'] is False, 'DEPENDENCY_INVALID')
    native_rows, exported_rows = authored['dependencies'], generated['dependencies']
    check(isinstance(native_rows, list) and isinstance(exported_rows, list) and
          0 < len(native_rows) == len(exported_rows) <= 8192, 'DEPENDENCY_INVALID')
    def indexed(rows, exported):
        result = {}
        keys = {'path', 'sha256', 'bytes', 'kind', 'packageName', 'packageVersion'}
        for row in rows:
            check(isinstance(row, dict) and set(row) == keys | ({'owner'} if exported else set()), 'DEPENDENCY_INVALID')
            check(safe_relative(row['path']) and row['path'] not in result, 'DEPENDENCY_INVALID')
            result[row['path']] = {key: row[key] for key in keys}
        return result
    rows = indexed(native_rows, False)
    check(rows == indexed(exported_rows, True), 'DEPENDENCY_INVALID')
    selected = []
    for name in (MATERIAL, MATERIAL + '.meta', SHADER, SHADER + '.meta'):
        check(name in rows, 'DEPENDENCY_INVALID')
        row = rows[name]
        package = name.startswith('Packages/')
        check(digest(row['sha256']) and number(row['bytes'], 1, 128 * 1024**2) and
              row['kind'] == ('package' if package else 'asset') and
              row['packageName'] == ('com.unity.render-pipelines.universal' if package else '') and
              row['packageVersion'] == ('17.3.0' if package else ''), 'DEPENDENCY_INVALID')
        selected.append(dict(path=name, sha256=row['sha256'], bytes=row['bytes']))
        if not package:
            check(row['bytes'] <= 32768, 'DEPENDENCY_INVALID')
            actual = exporter.safe(project / name)
            check(actual.stat().st_size == row['bytes'] and exporter.sha(actual) == row['sha256'], 'DEPENDENCY_INVALID')
    material = exporter.safe(project / MATERIAL).read_text()
    check(len(material) <= 32768 and material.count('m_Shader:') == 1 and
          'm_Shader: {fileID: 4800000, guid: ' + SHADER_GUID + ', type: 3}' in material, 'DEPENDENCY_INVALID')
    return dict(generatedReceiptSha256=sha_bytes(raw), nativeManifestSha256=sha_bytes(native_raw),
                shaderGuid=SHADER_GUID, entries=selected,
                scope='NATIVE_AUTHORING_DEPENDENCY_CLOSURE_AND_SOURCE_MATERIAL')


def verify_package(package, exporter, expected_commit, expected_run, generated=None, project=None):
    """Uses the existing exporter's receipt, control, inventory and tar validators."""
    result = empty_report()
    phase = 'PACKAGE_INVALID'
    try:
        check(digest(expected_commit, 40) and isinstance(expected_run, str) and
              re.fullmatch(r'https://github\.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]{0,19}', expected_run), 'IDENTITY_INVALID')
        package = exporter.safe(package, False)
        check({p.name for p in package.iterdir()} == {'manifest.json', 'native-build-receipt.json', 'control.json', 'player.tar.gz'}, 'PACKAGE_INVALID')
        manifest_raw, m = read_sealed(package / 'manifest.json', exporter)
        control_raw, control = read_sealed(package / 'control.json', exporter)
        native_raw, native = exporter.sealed_native_receipt(package / 'native-build-receipt.json')
        check(isinstance(m, dict) and set(m) == MANIFEST_KEYS and type(m['schema']) is int and m['schema'] == 1 and
              m['label'] == 'REUSABLE_CANDIDATE_LINUX_PLAYER_UNREVIEWED' and
              m['sourceCommit'] == native['sourceCommit'] == expected_commit and
              m['producerRunUrl'] == native['producerRunUrl'] == expected_run and
              m['playerExecuted'] is False and m['approved'] is False, 'PACKAGE_INVALID')
        for key in ('nativeReceiptSha256', 'inputSha256', 'generatedReceiptSha256', 'sourceStateSha256', 'bundleSha256'):
            check(digest(m[key]), 'PACKAGE_INVALID')
        check(m['nativeReceipt'] == native and sha_bytes(native_raw) == m['nativeReceiptSha256'] and
              native['requestSha256'] == m['inputSha256'] and
              native['generatedReceiptSha256'] == m['generatedReceiptSha256'], 'PACKAGE_INVALID')
        exporter.validate_control(control)
        check(control['hostDiagnostic']['failurePhase'] == 'NONE' and
              all(control[k] == 'SUCCEEDED' for k in ('activation', 'build', 'licenseReturn', 'privateCleanup')) and
              control['sourceRecovery']['status'] == 'SUCCEEDED' and control['buildDiagnostic'] is not None and
              control['buildDiagnostic']['batchExitCode'] == 0 and exporter.diagnostic_success(control['buildDiagnostic']['native']), 'PACKAGE_INVALID')
        check(control['hostDiagnostic']['nativeReceiptPin'] == dict(sha256=sha_bytes(native_raw), bytes=len(native_raw)), 'PACKAGE_INVALID')
        exporter.validate_records(m['files'])
        records = {row['path']: row for row in m['files']}
        check(records['DesertRV.x86_64']['sha256'] == native['executableSha256'], 'PACKAGE_INVALID')
        archive_path = exporter.safe(package / 'player.tar.gz')
        check(number(m['bundleBytes'], 1, 8 * 1024**3) and archive_path.stat().st_size == m['bundleBytes'] and
              exporter.sha(archive_path) == m['bundleSha256'], 'PACKAGE_INVALID')
        exporter.verify_tar(archive_path, m['files'])
        result.update(sourceCommit=expected_commit, producerRunUrl=expected_run, packageValidated=True,
                      packagePins=[dict(path=name, sha256=sha_bytes(raw), bytes=len(raw)) for name, raw in
                                   [('manifest.json', manifest_raw), ('control.json', control_raw), ('native-build-receipt.json', native_raw)]] +
                                  [dict(path='player.tar.gz', sha256=m['bundleSha256'], bytes=m['bundleBytes'])])
        phase = 'SERIALIZED_METADATA'
        with tarfile.open(archive_path, 'r:gz') as archive:
            def load(name):
                check(safe_relative(name) and name in records, 'SHADER_FILE_MISSING')
                row = records[name]
                check(48 <= row['size'] <= MAX_ASSET_BYTES, 'SERIALIZED_SIZE')
                member = archive.getmember(name)
                check(member.isfile() and member.size == row['size'], 'PACKAGE_CHANGED')
                with archive.extractfile(member) as stream:
                    data = stream.read(MAX_ASSET_BYTES + 1)
                check(len(data) == row['size'] and sha_bytes(data) == row['sha256'], 'PACKAGE_CHANGED')
                return data
            data = load(GLOBAL)
            meta = serialized(data)
            entries, result['registry'] = registry(data, meta)
            result['resolvedShader'] = resolve_shader(load, meta, entries, TARGET)
        check(exporter.sha(archive_path) == m['bundleSha256'] and
              exporter.sha(package / 'manifest.json') == sha_bytes(manifest_raw) and
              exporter.sha(package / 'control.json') == sha_bytes(control_raw) and
              exporter.sha(package / 'native-build-receipt.json') == sha_bytes(native_raw), 'PACKAGE_CHANGED')
        if generated is not None:
            phase = 'DEPENDENCY_INVALID'
            check(project is not None, 'DEPENDENCY_INVALID')
            result['nativeDependencies'] = dependency_proof(generated, project, exporter, native)
        result.update(status='PASSED', failureCode='NONE', shaderRegistryPass=True)
    except Rejected as error:
        result['failureCode'] = error.code
    except OSError:
        result['failureCode'] = 'IO_UNAVAILABLE'
    except (ValueError, TypeError, KeyError, IndexError, tarfile.TarError, OverflowError):
        result['failureCode'] = phase
    return validate_report(result)


def validate_report(value):
    check(isinstance(value, dict) and set(value) == set(empty_report()), 'INTERNAL_ERROR')
    check(type(value['schema']) is int and value['schema'] == 1 and value['targetShader'] == TARGET and
          value['failureCode'] in CODES and value['status'] in ('PASSED', 'FAILED'), 'INTERNAL_ERROR')
    check(all(type(value[k]) is bool for k in ('packageValidated', 'shaderRegistryPass', 'playerExecuted', 'renderingVerified')) and
          value['playerExecuted'] is False and value['renderingVerified'] is False and
          value['shaderRegistryPass'] == (value['status'] == 'PASSED') == (value['failureCode'] == 'NONE'), 'INTERNAL_ERROR')
    if value['packageValidated']:
        check(digest(value['sourceCommit'], 40) and re.fullmatch(r'https://github\.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]{0,19}', value['producerRunUrl']) and
              [r['path'] for r in value['packagePins']] == ['manifest.json', 'control.json', 'native-build-receipt.json', 'player.tar.gz'], 'INTERNAL_ERROR')
    else:
        check(value['sourceCommit'] == value['producerRunUrl'] == '' and value['packagePins'] == [] and
              value['registry'] is value['resolvedShader'] is value['nativeDependencies'] is None, 'INTERNAL_ERROR')
    for row in value['packagePins']:
        check(set(row) == {'path', 'sha256', 'bytes'} and digest(row['sha256']) and number(row['bytes'], 1, 8 * 1024**3), 'INTERNAL_ERROR')
    reg = value['registry']
    if reg is not None:
        check(set(reg) == {'path', 'sha256', 'bytes', 'serializedVersion', 'unityVersion', 'target', 'registryClassId', 'registryPathId', 'registryObjectBytes', 'entryCount'} and
              reg['path'] == GLOBAL and digest(reg['sha256']) and number(reg['bytes'], 48, MAX_ASSET_BYTES) and
              reg['serializedVersion'] == 22 and reg['unityVersion'] == UNITY and reg['target'] == 24 and reg['registryClassId'] == 94 and
              type(reg['registryPathId']) is int and reg['registryPathId'] != 0 and number(reg['registryObjectBytes'], 5, 4 * 1024**2) and number(reg['entryCount'], 1, 10000), 'INTERNAL_ERROR')
    shader = value['resolvedShader']
    if shader is not None:
        check(reg is not None and set(shader) == {'path', 'sha256', 'bytes', 'fileId', 'pathId', 'classId', 'objectOffset', 'objectBytes'} and
              safe_relative(shader['path']) and shader['path'].startswith('DesertRV_Data/') and digest(shader['sha256']) and
              number(shader['bytes'], 48, MAX_ASSET_BYTES) and number(shader['fileId'], 0, 4096) and number(shader['pathId'], 1, 2**63 - 1) and
              shader['classId'] == 48 and number(shader['objectOffset'], 48, shader['bytes']) and number(shader['objectBytes'], 1, shader['bytes'] - shader['objectOffset']), 'INTERNAL_ERROR')
    proof = value['nativeDependencies']
    if proof is not None:
        check(set(proof) == {'generatedReceiptSha256', 'nativeManifestSha256', 'shaderGuid', 'entries', 'scope'} and
              digest(proof['generatedReceiptSha256']) and digest(proof['nativeManifestSha256']) and proof['shaderGuid'] == SHADER_GUID and
              proof['scope'] == 'NATIVE_AUTHORING_DEPENDENCY_CLOSURE_AND_SOURCE_MATERIAL' and
              [r['path'] for r in proof['entries']] == [MATERIAL, MATERIAL + '.meta', SHADER, SHADER + '.meta'], 'INTERNAL_ERROR')
        check(all(set(row) == {'path', 'sha256', 'bytes'} and digest(row['sha256']) and number(row['bytes'], 1, 128 * 1024**2) for row in proof['entries']), 'INTERNAL_ERROR')
    check(not value['shaderRegistryPass'] or value['packageValidated'] and reg is not None and shader is not None, 'INTERNAL_ERROR')
    check(len(json.dumps(value)) <= 16384, 'INTERNAL_ERROR')
    return value


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    task = pathlib.Path(__file__).resolve().parents[2]
    result = empty_report()
    try:
        check(not argv, 'ARGUMENTS_INVALID')
        check(os.environ.get('EXPORT_OUTCOME') == 'success', 'EXPORT_NOT_SUCCESS')
        import journey_linux_export as exporter
        result = verify_package(exporter.PUBLIC, exporter, os.environ.get('GITHUB_SHA', ''),
                                'https://github.com/yangerstar1/task-workbench/actions/runs/' + os.environ.get('GITHUB_RUN_ID', ''),
                                exporter.TASK / 'journey-preparation-export/generated', exporter.PROJECT)
    except Rejected as error:
        result['failureCode'] = error.code
    except Exception:
        result['failureCode'] = 'INTERNAL_ERROR'
    try:
        raw = (json.dumps(validate_report(result), indent=2, sort_keys=True) + '\n').encode()
        path = task / REPORT_NAME
        check(not any(p.is_symlink() for p in (path, *path.parents)), 'IO_UNAVAILABLE')
        # Exclusive create prevents overwriting an earlier or foreign result.
        with path.open('xb') as stream:
            stream.write(raw)
        check(path.read_bytes() == raw, 'IO_UNAVAILABLE')
        validate_report(strict_json(path.read_bytes()))
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write('report_written=true\nreport_valid=true\nshader_registry_pass=' +
                         ('true' if result['shaderRegistryPass'] else 'false') + '\n')
    except Exception:
        print('JOURNEY_TRACER_SHADER_REPORT_UNAVAILABLE')
        return 1
    print('JOURNEY_TRACER_SHADER_' + result['status'] + ' ' + result['failureCode'])
    return 0 if result['shaderRegistryPass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
