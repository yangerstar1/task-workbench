"""Synthetic adversarial checks plus unchanged official repository examples.

Nothing here executes Unity or constitutes project-native/visual acceptance.
"""
import copy
from pathlib import Path
import re
import tempfile
import unittest

import yaml

from strict_output import StrictError
import urp_material_metadata as u


# Independently transcribed from the official 6000.3/staging Runtime/Materials/Lit.mat.
# Deliberately not generated from the validator's expected-value constants.
ASSET_VERSION_YAML = '''--- !u!114 &-8081582795363580827
MonoBehaviour:
  m_ObjectHideFlags: 11
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 0}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {fileID: 11500000, guid: d0353a89b1f911e48b9e16bdc9f2e058, type: 3}
  m_Name:
  m_EditorClassIdentifier:
  version: 10
'''


def material_yaml(asset, metadata=ASSET_VERSION_YAML, material_id=2100000):
    return ('%YAML 1.1\n--- !u!21 &'+str(material_id)+'\n'
        + yaml.safe_dump({'Material': asset}, sort_keys=False) + metadata)


class MaterialMetadataTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/'Material_00.mat'
        self.asset = dict(m_Name='Material_00', m_Shader=dict(fileID=4800000,
            guid='933532a4fcc9baf4fa0491de14d08ed7', type=3),
            m_Parent={'fileID': 0}, m_SavedProperties=dict(m_TexEnvs=[]))

    def parse(self, text=None, expected_local_id=None):
        self.path.write_text(text if text is not None else material_yaml(self.asset))
        return u.read_material_asset(self.path, expected_local_id)

    def reject(self, text=None, code=None):
        with self.assertRaisesRegex(StrictError, code or '^URP_MATERIAL_'):
            self.parse(text)

    def test_valid_minimal_material_with_official_metadata(self):
        self.assertEqual(self.parse(), self.asset)

    def test_official_urp_lit_file_is_admitted_unchanged(self):
        path = Path(__file__).parent/'fixtures/urp-17.3-Lit.mat'
        self.assertEqual(u.read_material_asset(path)['m_Name'], 'Lit')

    def test_official_mixed_pipeline_file_rejected(self):
        path = Path(__file__).parent/'fixtures/urp-17.3-CHNOS-Hex-Array.mat'
        with self.assertRaisesRegex(StrictError, 'URP_MATERIAL_DOCUMENTS'):
            u.read_material_asset(path)

    def test_official_full_editor_class_identifier(self):
        text = material_yaml(self.asset).replace('m_EditorClassIdentifier:',
            'm_EditorClassIdentifier: Unity.RenderPipelines.Universal.Editor::UnityEditor.Rendering.Universal.AssetVersion')
        self.assertEqual(self.parse(text), self.asset)

    def test_metadata_first_supported(self):
        text = material_yaml(self.asset)
        self.assertEqual(self.parse('%YAML 1.1\n'+ASSET_VERSION_YAML+text.split('\n', 1)[1].split('--- !u!114')[0]), self.asset)

    def test_material_local_id_bound_to_native_readback(self):
        self.assertEqual(self.parse(expected_local_id=2100000), self.asset)
        with self.assertRaisesRegex(StrictError, 'URP_MATERIAL_LOCAL_ID'):
            self.parse(expected_local_id=123)

    def test_metadata_required(self):
        self.reject(material_yaml(self.asset, ''), 'URP_MATERIAL_DOCUMENTS')

    def test_extra_document_rejected(self):
        self.reject(material_yaml(self.asset)+'--- !u!114 &77\nMonoBehaviour: {}\n')

    def test_duplicate_or_zero_document_ids_rejected(self):
        for bad in ('2100000', '0', str(2**63), '-'+str(2**63+1)):
            with self.subTest(bad=bad):
                self.reject(material_yaml(self.asset).replace('-8081582795363580827', bad))

    def test_metadata_class_header_root_and_stripped_rejected(self):
        for before, after in (('!u!114', '!u!115'), ('MonoBehaviour:', 'ScriptableObject:'),
                ('&-8081582795363580827', '&-8081582795363580827 stripped')):
            with self.subTest(after=after): self.reject(material_yaml(self.asset).replace(before, after))

    def test_metadata_numeric_fields_exact_integer(self):
        for field, value in (('version', '9'), ('version', '11'), ('version', '10.0'),
                ('version', '"10"'), ('version', 'true'), ('m_ObjectHideFlags', '0'),
                ('m_ObjectHideFlags', '3'), ('m_Enabled', '0'), ('m_EditorHideFlags', '1')):
            text = re.sub(r'  '+field+r': .*', '  '+field+': '+value, material_yaml(self.asset))
            with self.subTest(field=field, value=value): self.reject(text, 'URP_MATERIAL_VERSION_VALUE')

    def test_metadata_null_references_must_be_exact(self):
        for field in ('m_CorrespondingSourceObject', 'm_PrefabInstance', 'm_PrefabAsset', 'm_GameObject'):
            for value in ('{fileID: 1}', '{fileID: false}', '{fileID: 0, guid: '+ 'a'*32+'}', '{}'):
                text = re.sub(r'  '+field+r': .*', '  '+field+': '+value, material_yaml(self.asset))
                with self.subTest(field=field, value=value): self.reject(text, 'URP_MATERIAL_VERSION_REFERENCE')

    def test_metadata_script_reference_exact(self):
        for before, after in (('11500000', '11500001'), ('11500000', 'true'),
                ('d0353a89b1f911e48b9e16bdc9f2e058', 'a'*32), ('type: 3}', 'type: 2}')):
            text = material_yaml(self.asset, ASSET_VERSION_YAML.replace(before, after))
            with self.subTest(after=after): self.reject(text, 'URP_MATERIAL_VERSION_SCRIPT')

    def test_metadata_extra_or_missing_field(self):
        for metadata in (ASSET_VERSION_YAML+'  secret: 1\n', ASSET_VERSION_YAML.replace('  m_Enabled: 1\n','')):
            self.reject(material_yaml(self.asset, metadata), 'URP_MATERIAL_VERSION_SCHEMA')

    def test_metadata_name_and_arbitrary_editor_identifier_rejected(self):
        for field in ('m_Name', 'm_EditorClassIdentifier'):
            self.reject(material_yaml(self.asset, ASSET_VERSION_YAML.replace(field+':', field+': fixture-secret')),
                'URP_MATERIAL_VERSION_IDENTITY')

    def test_duplicate_metadata_and_nested_material_keys_rejected(self):
        self.reject(material_yaml(self.asset, ASSET_VERSION_YAML+'  version: 10\n'), 'URP_MATERIAL_DUPLICATE_YAML_KEY')
        self.reject(material_yaml(self.asset).replace('  m_Name: Material_00', '  m_Name: wrong\n  m_Name: Material_00'),
            'URP_MATERIAL_DUPLICATE_YAML_KEY')
        self.reject(material_yaml(self.asset).replace('    fileID: 4800000', '    fileID: 1\n    fileID: 4800000'),
            'URP_MATERIAL_DUPLICATE_YAML_KEY')

    def test_aliases_anchors_and_merges_rejected(self):
        self.reject(material_yaml(self.asset).replace('m_Parent:', 'm_Parent: &borrowed\n  arbitrary: *borrowed\n  ignored:'),
            'URP_MATERIAL_YAML_ANCHOR')
        self.reject(material_yaml(self.asset, ASSET_VERSION_YAML.replace('  m_Name:', '  <<: {version: 10}\n  m_Name:')),
            'URP_MATERIAL_YAML_KEY')

    def test_unity_directives_and_unknown_documents_rejected(self):
        for after in ('%TAG !x! wrong:\n', '---\nUnknown: 1\n', 'fixture-secret\n'):
            self.reject(material_yaml(self.asset).replace('%YAML 1.1\n', '%YAML 1.1\n'+after))

    def test_material_cannot_reference_metadata_script_or_arbitrary_object(self):
        for field, value in (('m_Parent', {'fileID': 1}), ('m_Parent', 'bogus'),
                ('m_Script', {'fileID': 11500000, 'guid': u.URP_ASSET_VERSION_GUID, 'type': 3}),
                ('extra', {'fileID': 1, 'guid': 'a'*32, 'type': 3})):
            with self.subTest(field=field):
                asset = copy.deepcopy(self.asset); asset[field] = value
                self.reject(material_yaml(asset), 'URP_MATERIAL_REFERENCE')

    def test_material_shader_reference_is_exact(self):
        for field, value in (('fileID', 4800001), ('fileID', True), ('type', 2), ('guid', 'a'*32)):
            asset = copy.deepcopy(self.asset); asset['m_Shader'][field] = value
            with self.subTest(field=field): self.reject(material_yaml(asset), 'URP_MATERIAL_SHADER_REFERENCE')

    def test_only_texture_bindings_may_hold_regular_texture_references(self):
        texture = {'fileID': 2800000, 'guid': '1'*32, 'type': 3}
        self.asset['m_SavedProperties']['m_TexEnvs'] = [{'_BaseMap': {'m_Texture': texture}}]
        self.assertEqual(self.parse(), self.asset)
        for guid in (u.URP_ASSET_VERSION_GUID, u.URP_LIT_GUID):
            texture['guid'] = guid
            self.reject(code='URP_MATERIAL_TEXTURE_REFERENCE')


if __name__ == '__main__':
    unittest.main()
