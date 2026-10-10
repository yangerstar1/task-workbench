#!/usr/bin/env python3
"""Synthetic corruption cases and optional read-only negative exported-player fixture."""
import io
import json
import os
import pathlib
import struct
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import journey_linux_export as exporter
import test_journey_linux_export as exporter_fixtures
import verify_tracer_shader as gate


def asset(objects, externals=()):
    """Construct a minimal v22 byte fixture, returning mutation offsets as well."""
    meta = bytearray(gate.UNITY.encode() + b'\0' + struct.pack('<iB', 24, 0))
    marks = {'typeCount': 48 + len(meta)}
    classes = list(dict.fromkeys(item[1] for item in objects))
    meta += struct.pack('<i', len(classes))
    for class_id in classes:
        meta += struct.pack('<iBh', class_id, 0, -1) + b'\0' * (32 if class_id == 114 else 16)
    marks['objectCount'] = 48 + len(meta)
    meta += struct.pack('<i', len(objects))
    payload = bytearray()
    marks['objects'] = []
    for path_id, class_id, raw in objects:
        meta += b'\0' * (-len(meta) % 4)
        payload += b'\0' * (-len(payload) % 4)
        marks['objects'].append(48 + len(meta))
        meta += struct.pack('<qqIi', path_id, len(payload), len(raw), classes.index(class_id))
        payload += raw
    meta += struct.pack('<i', 0)  # Script identifiers.
    marks['externalCount'] = 48 + len(meta)
    meta += struct.pack('<i', len(externals))
    for name in externals:
        meta += b'\0' + b'\0' * 16 + struct.pack('<i', 0) + name.encode() + b'\0'
    marks['refCount'] = 48 + len(meta)
    meta += struct.pack('<i', 0) + b'\0'
    data_offset = (48 + len(meta) + 15) // 16 * 16
    marks['data'] = data_offset
    header = struct.pack('>IIII', 0, 0, 22, 0) + b'\0' * 4
    header += struct.pack('>Iqqq', len(meta), data_offset + len(payload), data_offset, 0)
    return bytes(header + meta + b'\0' * (data_offset - 48 - len(meta)) + payload), marks


def registry_body(entries):
    raw = bytearray(struct.pack('<i', len(entries)))
    for name, file_id, path_id in entries:
        text = name.encode()
        raw += struct.pack('<iqi', file_id, path_id, len(text)) + text
        raw += b'\0' * (-len(raw) % 4)
    return bytes(raw + b'\0')


def fixtures(entries=None, shader_class=48, external='sharedassets0.assets'):
    entries = [(gate.TARGET, 1, 17)] if entries is None else entries
    manager, marks = asset([(5, 94, registry_body(entries))], [external])
    shader, shader_marks = asset([(17, shader_class, b'SYNTHETIC_SHADER_OBJECT')])
    return {gate.GLOBAL: manager, 'DesertRV_Data/sharedassets0.assets': shader}, marks, shader_marks


def inspect(files, target=gate.TARGET):
    data = files[gate.GLOBAL]
    meta = gate.serialized(data)
    entries, info = gate.registry(data, meta)
    def load(name):
        gate.check(name in files, 'SHADER_FILE_MISSING')
        return files[name]
    return gate.resolve_shader(load, meta, entries, target), info


def changed(raw, offset, fmt, *values):
    result = bytearray(raw)
    struct.pack_into(fmt, result, offset, *values)
    return bytes(result)


class ParserTests(unittest.TestCase):
    def rejected(self, code, callback):
        with self.assertRaises(gate.Rejected) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_external_and_same_file_class48_resolution(self):
        files, _, _ = fixtures()
        shader, info = inspect(files)
        self.assertEqual((shader['classId'], shader['pathId'], info['entryCount']), (48, 17, 1))
        data, _ = asset([(5, 94, registry_body([(gate.TARGET, 0, 17)])), (17, 48, b'LOCAL_SHADER')])
        shader, _ = inspect({gate.GLOBAL: data})
        self.assertEqual(shader['path'], gate.GLOBAL)

    def test_target_bytes_outside_registry_are_not_inclusion(self):
        files, _, _ = fixtures([('Other Shader', 1, 17)])
        files['DesertRV_Data/sharedassets0.assets'], _ = asset([(17, 48, gate.TARGET.encode())])
        self.rejected('MISSING_SHADER', lambda: inspect(files))

    def test_duplicate_names_are_rejected_even_when_target_is_unique(self):
        for name in (gate.TARGET, 'Other Shader'):
            files, _, _ = fixtures([(gate.TARGET, 1, 17), (name, 1, 17), (name, 1, 17)])
            with self.subTest(name=name):
                self.rejected('REGISTRY_DUPLICATE', lambda: inspect(files))

    def test_dangling_external_null_missing_object_and_wrong_class(self):
        for entries, class_id, code in [([(gate.TARGET, 2, 17)], 48, 'REGISTRY_POINTER'),
                                       ([(gate.TARGET, -1, 17)], 48, 'REGISTRY_POINTER'),
                                       ([(gate.TARGET, 1, 0)], 48, 'SHADER_NULL'),
                                       ([(gate.TARGET, 1, 999)], 48, 'SHADER_OBJECT_MISSING'),
                                       ([(gate.TARGET, 1, 17)], 21, 'SHADER_CLASS_MISMATCH')]:
            files, _, _ = fixtures(entries, class_id)
            with self.subTest(code=code):
                self.rejected(code, lambda: inspect(files))

    def test_missing_external_is_not_resolved_using_basename_or_host_file(self):
        files, _, _ = fixtures(external='elsewhere/sharedassets0.assets')
        self.rejected('SHADER_FILE_MISSING', lambda: inspect(files))

    def test_external_paths_cannot_escape_or_alias(self):
        for name in ('../sharedassets0.assets', '/sharedassets0.assets', 'a/../../secret',
                     'a\\sharedassets0.assets', 'a//sharedassets0.assets', './sharedassets0.assets',
                     'archive:/outside', 'sharedassets0.assets\nTOKEN'):
            files, _, _ = fixtures(external=name)
            with self.subTest(name=name):
                with self.assertRaises(gate.Rejected):
                    inspect(files)

    def test_registry_reads_are_bounded_by_object_not_whole_file(self):
        files, marks, _ = fixtures()
        files[gate.GLOBAL] = changed(files[gate.GLOBAL], marks['data'] + 16, '<i', 2048)
        self.rejected('SERIALIZED_TRUNCATED', lambda: inspect(files))

    def test_registry_counts_names_and_tail_fail_closed(self):
        raw, _ = asset([(5, 94, registry_body([(gate.TARGET, 0, 17)])), (17, 48, b'SHADER')])
        meta = gate.serialized(raw)
        offset = meta['objects'][5]['offset']
        for position, fmt, value, code in [(offset, '<i', -1, 'REGISTRY_COUNT'),
                                          (offset, '<i', 10001, 'REGISTRY_COUNT'),
                                          (offset + 16, '<i', 0, 'REGISTRY_NAME'),
                                          (offset + 16, '<i', 2049, 'REGISTRY_NAME')]:
            with self.subTest(code=code, value=value):
                self.rejected(code, lambda: gate.registry(changed(raw, position, fmt, value), meta))
        tail = offset + meta['objects'][5]['bytes'] - 1
        self.rejected('REGISTRY_TRAILING', lambda: gate.registry(changed(raw, tail, '<B', 1), meta))
        self.rejected('REGISTRY_NAME', lambda: gate.registry(changed(raw, offset + 20, '<B', 255), meta))

    def test_metadata_types_bounds_versions_and_oversize_rejected(self):
        files, marks, _ = fixtures()
        raw = files[gate.GLOBAL]
        obj = marks['objects'][0]
        cases = [(8, '>I', 21, 'SERIALIZED_VERSION'), (16, '<B', 1, 'SERIALIZED_ENDIAN'),
                 (24, '>q', len(raw) + 1, 'SERIALIZED_HEADER'),
                 (20, '>I', len(raw), 'SERIALIZED_METADATA'),
                 (marks['typeCount'] - 1, '<B', 1, 'SERIALIZED_TYPE_TREE'),
                 (marks['typeCount'], '<i', 4097, 'SERIALIZED_COUNT'),
                 (marks['objectCount'], '<i', -1, 'SERIALIZED_COUNT'),
                 (marks['externalCount'], '<i', 4097, 'SERIALIZED_COUNT'),
                 (marks['refCount'], '<i', 1, 'SERIALIZED_REF_TYPES'),
                 (obj, '<q', 0, 'SERIALIZED_OBJECT'),
                 (obj + 8, '<q', -1, 'SERIALIZED_OBJECT'),
                 (obj + 16, '<I', len(raw), 'SERIALIZED_OBJECT'),
                 (obj + 20, '<i', 7, 'SERIALIZED_OBJECT')]
        for position, fmt, value, code in cases:
            with self.subTest(code=code, position=position):
                self.rejected(code, lambda: gate.serialized(changed(raw, position, fmt, value)))
        with patch.object(gate, 'MAX_ASSET_BYTES', len(raw) - 1):
            self.rejected('SERIALIZED_SIZE', lambda: gate.serialized(raw))
        self.rejected('SERIALIZED_SIZE', lambda: gate.serialized(raw[:47]))

    def test_duplicate_objects_overlapping_spans_and_unterminated_metadata(self):
        raw, marks = asset([(11, 48, b'FIRST'), (12, 48, b'SECOND')])
        self.rejected('SERIALIZED_OBJECT', lambda: gate.serialized(changed(raw, marks['objects'][1], '<q', 11)))
        self.rejected('SERIALIZED_OVERLAP', lambda: gate.serialized(changed(raw, marks['objects'][1] + 8, '<q', 0)))
        self.rejected('SERIALIZED_STRING', lambda: gate.serialized(raw[:48] + b'X' * 33 + raw[81:]))

    def test_duplicate_json_and_unsafe_report_fields_are_rejected(self):
        self.rejected('JSON_INVALID', lambda: gate.strict_json(b'{"same":1,"same":2}'))
        self.rejected('JSON_INVALID', lambda: gate.strict_json(b'{"bad":NaN}'))
        for field, value in [('rawLogs', 'PRIVATE_TOKEN'), ('failureCode', 'PRIVATE_TOKEN'),
                             ('sourceCommit', '/private/token'), ('playerExecuted', True)]:
            report = gate.empty_report()
            report[field] = value
            self.rejected('INTERNAL_ERROR', lambda: gate.validate_report(report))


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.base = exporter_fixtures.JourneyLinuxExportTests()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.addCleanup(self.base.tearDown)
        self.root, self.build = self.base.root, self.base.build
        self.package = self.root / 'package'
        self.package.mkdir()
        self.files, _, _ = fixtures()
        self.prepare()

    def prepare(self, generated=None):
        for name, data in self.files.items():
            path = self.build / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        native = self.base.receipt()
        if generated is not None:
            native['generatedReceiptSha256'] = exporter.sha(generated / 'receipt.json')
        native_raw = json.dumps(native).encode()
        control = self.base.control()
        control['hostDiagnostic']['nativeReceiptPin'] = dict(sha256=gate.sha_bytes(native_raw), bytes=len(native_raw))
        rows = exporter.inventory(self.build)
        exporter.tar_bundle(self.build, rows, self.package / 'player.tar.gz')
        manifest = dict(schema=1, label='REUSABLE_CANDIDATE_LINUX_PLAYER_UNREVIEWED',
                        sourceCommit='a' * 40, producerRunUrl=exporter.producer_url(), nativeReceipt=native,
                        nativeReceiptSha256=gate.sha_bytes(native_raw), inputSha256=native['requestSha256'],
                        generatedReceiptSha256=native['generatedReceiptSha256'], sourceStateSha256='e' * 64,
                        bundleSha256=exporter.sha(self.package / 'player.tar.gz'),
                        bundleBytes=(self.package / 'player.tar.gz').stat().st_size,
                        files=rows, playerExecuted=False, approved=False)
        (self.package / 'native-build-receipt.json').write_bytes(native_raw)
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        (self.package / 'control.json').write_text(json.dumps(control))

    def verify(self, generated=None, project=None):
        return gate.verify_package(self.package, exporter, 'a' * 40, exporter.producer_url(), generated, project)

    def test_full_synthetic_package_pass_uses_original_validators_without_writes(self):
        before = {p.name: (exporter.sha(p), p.stat().st_mode) for p in self.package.iterdir()}
        with (patch.object(exporter, 'verify_tar', wraps=exporter.verify_tar) as tar_check,
              patch.object(exporter, 'validate_records', wraps=exporter.validate_records) as inventory_check):
            result = self.verify()
        self.assertTrue(result['shaderRegistryPass'])
        self.assertEqual(result['resolvedShader']['classId'], 48)
        tar_check.assert_called_once()
        self.assertGreaterEqual(inventory_check.call_count, 1)
        self.assertEqual(before, {p.name: (exporter.sha(p), p.stat().st_mode) for p in self.package.iterdir()})

    def test_missing_target_produces_pinned_failure_report(self):
        self.files, _, _ = fixtures([('Other Shader', 1, 17)])
        self.prepare()
        result = self.verify()
        self.assertEqual(result['failureCode'], 'MISSING_SHADER')
        self.assertTrue(result['packageValidated'])
        self.assertEqual(len(result['packagePins']), 4)
        self.assertFalse(result['shaderRegistryPass'])

    def test_hash_identity_duplicate_metadata_and_symlink_tampering_fail(self):
        path = self.package / 'manifest.json'
        original = path.read_bytes()
        for key, value in [('bundleSha256', '0' * 64), ('sourceCommit', 'b' * 40),
                           ('bundleBytes', True), ('nativeReceiptSha256', '0' * 64)]:
            with self.subTest(key=key):
                data = json.loads(original)
                data[key] = value
                path.write_text(json.dumps(data))
                self.assertEqual(self.verify()['failureCode'], 'PACKAGE_INVALID')
        path.write_bytes(original.replace(b'"schema":', b'"schema":99,"schema":', 1))
        self.assertEqual(self.verify()['failureCode'], 'JSON_INVALID')
        path.write_bytes(original)
        destination = self.root / 'foreign.json'
        destination.write_bytes(original)
        path.unlink()
        path.symlink_to(destination)
        self.assertEqual(self.verify()['failureCode'], 'PACKAGE_INVALID')

    def test_rehashed_malicious_tar_still_rejected_by_original_tar_verifier(self):
        path = self.package / 'player.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            item = tarfile.TarInfo('../SECRET')
            item.size = 1
            archive.addfile(item, io.BytesIO(b'X'))
        manifest = json.loads((self.package / 'manifest.json').read_text())
        manifest.update(bundleSha256=exporter.sha(path), bundleBytes=path.stat().st_size)
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        result = self.verify()
        self.assertEqual(result['failureCode'], 'PACKAGE_INVALID')
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertFalse((self.root / 'SECRET').exists())

    def dependencies(self):
        project, folder = self.root / 'unity', self.root / 'generated'
        folder.mkdir(exist_ok=True)
        material = ('Material:\n  m_Shader: {fileID: 4800000, guid: ' + gate.SHADER_GUID + ', type: 3}\n').encode()
        rows = []
        for name in (gate.MATERIAL, gate.MATERIAL + '.meta', gate.SHADER, gate.SHADER + '.meta'):
            package = name.startswith('Packages/')
            raw = material if name == gate.MATERIAL else b'SYNTHETIC_DEPENDENCY'
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            rows.append(dict(path=name, sha256=gate.sha_bytes(raw), bytes=len(raw),
                             kind='package' if package else 'asset',
                             packageName='com.unity.render-pipelines.universal' if package else '',
                             packageVersion='17.3.0' if package else ''))
        authored = dict(schema=3, status='ACTUAL_NATIVE_JOURNEY_ASSETS_UNREVIEWED',
                        sourceCommit='a' * 40, importRunUrl=exporter.producer_url(),
                        unityVersion=gate.UNITY, approved=False, dependencies=rows)
        (folder / 'native-authored-assets.json').write_text(json.dumps(authored))
        generated = dict(schema='desert-rv-generated-journey/v1', status='GENERATED_JOURNEY_SAVED_UNREVIEWED',
                         sourceCommit='a' * 40, importRunUrl=exporter.producer_url(), unityVersion=gate.UNITY, approved=False,
                         nativeManifestPath='native-authored-assets.json',
                         nativeManifestSha256=exporter.sha(folder / 'native-authored-assets.json'),
                         dependencies=[dict(row, owner='official-package' if row['kind'] == 'package' else 'source') for row in rows])
        (folder / 'receipt.json').write_text(json.dumps(generated))
        self.prepare(folder)
        return folder, project

    def test_native_dependency_closure_and_material_guid_are_bound(self):
        folder, project = self.dependencies()
        result = self.verify(folder, project)
        self.assertTrue(result['shaderRegistryPass'])
        self.assertEqual(len(result['nativeDependencies']['entries']), 4)
        material = project / gate.MATERIAL
        material.write_text(material.read_text().replace(gate.SHADER_GUID, '0' * 32))
        self.assertEqual(self.verify(folder, project)['failureCode'], 'DEPENDENCY_INVALID')

    def test_native_dependency_receipt_omission_mismatch_and_missing_file_rejected(self):
        folder, project = self.dependencies()
        original = (folder / 'receipt.json').read_bytes()
        receipt = json.loads(original)
        receipt['dependencies'].pop()
        (folder / 'receipt.json').write_text(json.dumps(receipt))
        self.prepare(folder)  # Rebind outer pin to test inner closure validation.
        self.assertEqual(self.verify(folder, project)['failureCode'], 'DEPENDENCY_INVALID')
        (folder / 'receipt.json').write_bytes(original)
        self.prepare(folder)
        (folder / 'native-authored-assets.json').unlink()
        self.assertFalse(self.verify(folder, project)['shaderRegistryPass'])

    def test_cli_failure_outputs_bounded_report_and_cannot_override_shader(self):
        task = self.root / 'tasks/desert-rv'
        task.mkdir(parents=True)
        script = task / 'scripts/player/verify_tracer_shader.py'
        output = self.root / 'github-output'
        for arguments, code in [([], 'EXPORT_NOT_SUCCESS'), (['--shader', 'Other Shader'], 'ARGUMENTS_INVALID')]:
            with (self.subTest(arguments=arguments), patch.object(gate, '__file__', str(script)),
                  patch.dict(os.environ, {'EXPORT_OUTCOME': 'failure', 'GITHUB_OUTPUT': str(output)})):
                self.assertEqual(gate.main(arguments), 1)
            result = json.loads((task / gate.REPORT_NAME).read_text())
            self.assertEqual(result['failureCode'], code)
            self.assertEqual(result['targetShader'], gate.TARGET)
            self.assertIn('report_written=true\nreport_valid=true\nshader_registry_pass=false\n', output.read_text())
            (task / gate.REPORT_NAME).unlink()

    def test_cli_pass_requires_native_dependency_proof_and_preserves_existing_report(self):
        folder, project = self.dependencies()
        task = self.root / 'tasks/desert-rv'
        task.mkdir(parents=True)
        script = task / 'scripts/player/verify_tracer_shader.py'
        output = self.root / 'github-output'
        # Use the real gate; supply its fixed generated directory through an isolated task root.
        expected_folder = task / 'journey-preparation-export/generated'
        expected_folder.parent.mkdir(parents=True)
        folder.rename(expected_folder)
        with (patch.object(gate, '__file__', str(script)), patch.object(exporter, 'PUBLIC', self.package),
              patch.object(exporter, 'TASK', task), patch.object(exporter, 'PROJECT', project),
              patch.dict(os.environ, {'EXPORT_OUTCOME': 'success', 'GITHUB_OUTPUT': str(output)})):
            self.assertEqual(gate.main([]), 0)
            before = (task / gate.REPORT_NAME).read_bytes()
            self.assertEqual(gate.main([]), 1)
            self.assertEqual((task / gate.REPORT_NAME).read_bytes(), before)
        self.assertIn('shader_registry_pass=true\n', output.read_text())


@unittest.skipUnless(os.environ.get('JOURNEY_SHADER_NEGATIVE_EXPORT'), 'Optional original negative exported-player fixture not provided')
class ExistingNegativeExportTests(unittest.TestCase):
    def test_original_target_absence_and_known_included_diagnostic_shaders(self):
        package = pathlib.Path(os.environ['JOURNEY_SHADER_NEGATIVE_EXPORT'])
        manifest = gate.strict_json((package / 'manifest.json').read_bytes())
        before = {p.name: (exporter.sha(p), p.stat().st_mode) for p in package.iterdir()}
        with patch.dict(os.environ, {'GITHUB_SHA': manifest['sourceCommit'], 'GITHUB_RUN_ID': manifest['producerRunUrl'].rsplit('/', 1)[1]}):
            result = gate.verify_package(package, exporter, manifest['sourceCommit'], manifest['producerRunUrl'])
        self.assertEqual(result['failureCode'], 'MISSING_SHADER')
        self.assertTrue(result['packageValidated'])
        self.assertEqual(result['registry']['entryCount'], 256)
        self.assertFalse(result['shaderRegistryPass'])
        # Positive diagnostics exercise the same parser, never the CLI's fixed target.
        with tarfile.open(package / 'player.tar.gz', 'r:gz') as archive:
            names = [gate.GLOBAL, 'DesertRV_Data/sharedassets0.assets']
            data = {name: archive.extractfile(name).read(gate.MAX_ASSET_BYTES + 1) for name in names}
        pins = {row['path']: row['sha256'] for row in manifest['files']}
        for name, raw in data.items():
            self.assertEqual(gate.sha_bytes(raw), pins[name])
        for name in ('Universal Render Pipeline/Lit', 'Universal Render Pipeline/Particles/Unlit'):
            shader, _ = inspect(data, name)
            self.assertEqual(shader['classId'], 48)
        self.assertEqual(before, {p.name: (exporter.sha(p), p.stat().st_mode) for p in package.iterdir()})


if __name__ == '__main__':
    unittest.main()
