"""Strict saved-material envelope for the separately verified URP 17.3.0 pin.

This is structural validation, not evidence that a candidate ran in Unity.
Callers must still verify package bytes, PBR values, texture/source identities,
native evidence and dependency closure. No package-script wildcard is granted.
"""
import re

import yaml

from strict_output import StrictError, require, safe

URP_LIT_GUID = '933532a4fcc9baf4fa0491de14d08ed7'
URP_ASSET_VERSION_GUID = 'd0353a89b1f911e48b9e16bdc9f2e058'
URP_ASSET_VERSION_CLASS = (
    'Unity.RenderPipelines.Universal.Editor::'
    'UnityEditor.Rendering.Universal.AssetVersion')
_HEADER = re.compile(r'^--- !u!([1-9][0-9]*) &(-?[1-9][0-9]*)$', re.M)
_NULL_FIELDS = ('m_CorrespondingSourceObject', 'm_PrefabInstance', 'm_PrefabAsset', 'm_GameObject')
_VERSION_FIELDS = frozenset((*_NULL_FIELDS, 'm_ObjectHideFlags', 'm_Enabled',
    'm_EditorHideFlags', 'm_Script', 'm_Name', 'm_EditorClassIdentifier', 'version'))


class _UniqueLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        require(not self.check_event(yaml.AliasEvent), 'URP_MATERIAL_YAML_ALIAS')
        event = self.peek_event()
        require(getattr(event, 'anchor', None) is None, 'URP_MATERIAL_YAML_ANCHOR')
        return super().compose_node(parent, index)


def _mapping(loader, node, deep=False):
    value = {}
    for key_node, item_node in node.value:
        require(isinstance(key_node, yaml.ScalarNode)
            and key_node.tag == 'tag:yaml.org,2002:str', 'URP_MATERIAL_YAML_KEY')
        key = loader.construct_scalar(key_node)
        require(key not in value, 'URP_MATERIAL_DUPLICATE_YAML_KEY')
        if key == 'guid':
            require(isinstance(item_node, yaml.ScalarNode), 'URP_MATERIAL_REFERENCE')
            item = loader.construct_scalar(item_node)
        else:
            item = loader.construct_object(item_node, deep=deep)
        value[key] = item
    return value


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _null_reference(value):
    return isinstance(value, dict) and set(value) == {'fileID'} \
        and type(value['fileID']) is int and value['fileID'] == 0


def _asset_version(value):
    require(isinstance(value, dict) and set(value) == _VERSION_FIELDS,
        'URP_MATERIAL_VERSION_SCHEMA')
    for key, expected in (('m_ObjectHideFlags', 11), ('m_Enabled', 1),
            ('m_EditorHideFlags', 0), ('version', 10)):
        require(type(value[key]) is int and value[key] == expected,
            'URP_MATERIAL_VERSION_VALUE')
    require(all(_null_reference(value[key]) for key in _NULL_FIELDS),
        'URP_MATERIAL_VERSION_REFERENCE')
    script = value['m_Script']
    require(isinstance(script, dict) and set(script) == {'fileID', 'guid', 'type'}
        and type(script['fileID']) is int and script['fileID'] == 11500000
        and type(script['type']) is int and script['type'] == 3
        and script['guid'] == URP_ASSET_VERSION_GUID, 'URP_MATERIAL_VERSION_SCRIPT')
    require(value['m_Name'] in (None, '')
        and value['m_EditorClassIdentifier'] in (None, '', URP_ASSET_VERSION_CLASS),
        'URP_MATERIAL_VERSION_IDENTITY')


def _material_references(asset):
    """A versioning script may occur only in its verified hidden document."""
    shader = asset.get('m_Shader')
    require(isinstance(shader, dict) and set(shader) == {'fileID', 'guid', 'type'}
        and type(shader['fileID']) is int and shader['fileID'] == 4800000
        and type(shader['type']) is int and shader['type'] == 3
        and shader['guid'] == URP_LIT_GUID, 'URP_MATERIAL_SHADER_REFERENCE')
    for key in (*_NULL_FIELDS, 'm_Parent'):
        require(key not in asset or _null_reference(asset[key]), 'URP_MATERIAL_REFERENCE')
    pending = [((), asset)]
    count = 0
    while pending:
        path, value = pending.pop()
        count += 1
        require(count <= 100000, 'URP_MATERIAL_YAML_NODE_LIMIT')
        if isinstance(value, dict):
            if {'guid', 'fileID', 'instanceID'} & value.keys():
                if path == ('m_Shader',):
                    require(set(value) == {'fileID', 'guid', 'type'}
                        and type(value['fileID']) is int and value['fileID'] == 4800000
                        and type(value['type']) is int and value['type'] == 3
                        and value['guid'] == URP_LIT_GUID, 'URP_MATERIAL_SHADER_REFERENCE')
                elif len(path) == 1 and path[0] in (*_NULL_FIELDS, 'm_Parent'):
                    require(_null_reference(value), 'URP_MATERIAL_REFERENCE')
                elif len(path) == 5 and path[:2] == ('m_SavedProperties', 'm_TexEnvs') \
                        and type(path[2]) is int and isinstance(path[3], str) and path[4] == 'm_Texture':
                    require(_null_reference(value) or (
                        set(value) == {'fileID', 'guid', 'type'}
                        and type(value['fileID']) is int and value['fileID'] != 0
                        and type(value['type']) is int and value['type'] == 3
                        and isinstance(value['guid'], str)
                        and re.fullmatch('[a-f0-9]{32}', value['guid']) is not None
                        and value['guid'] not in {URP_ASSET_VERSION_GUID, URP_LIT_GUID}),
                        'URP_MATERIAL_TEXTURE_REFERENCE')
                else:
                    require(False, 'URP_MATERIAL_REFERENCE')
            pending.extend((path+(key,), item) for key, item in value.items())
        elif isinstance(value, list):
            pending.extend((path+(index,), item) for index, item in enumerate(value))


def read_material_asset(path, expected_local_id=None):
    """Return the sole Material; require one exact official AssetVersion peer.

    The official 6000.3/staging assets prove both blank and fully-qualified
    EditorClassIdentifier forms. Document order and generated subasset IDs vary.
    All other metadata fields and script-reference values are exact, not inferred.
    """
    path = safe(path)
    require(path.stat().st_size < 32*1024**2, 'URP_MATERIAL_YAML_SIZE')
    data = path.read_text(encoding='utf-8')
    headers = list(_HEADER.finditer(data))
    require(len(headers) == 2 and data[:headers[0].start()] in (
        '%YAML 1.1\n', '%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n'),
        'URP_MATERIAL_DOCUMENTS')
    ids = [int(header.group(2)) for header in headers]
    require(len(set(ids)) == 2 and all(-(2**63) <= value < 2**63 for value in ids),
        'URP_MATERIAL_LOCAL_IDS')
    require(sorted(int(header.group(1)) for header in headers) == [21, 114],
        'URP_MATERIAL_DOCUMENTS')
    material = None
    for index, header in enumerate(headers):
        body = data[header.end():headers[index+1].start() if index+1 < len(headers) else len(data)]
        try:
            documents = list(yaml.load_all(body, Loader=_UniqueLoader))
        except yaml.YAMLError as error:
            raise StrictError('URP_MATERIAL_YAML') from error
        require(len(documents) == 1 and isinstance(documents[0], dict),
            'URP_MATERIAL_DOCUMENTS')
        document = documents[0]
        if header.group(1) == '21':
            require(set(document) == {'Material'} and isinstance(document['Material'], dict),
                'URP_MATERIAL_DOCUMENTS')
            require(expected_local_id is None or (type(expected_local_id) is int
                and ids[index] == expected_local_id), 'URP_MATERIAL_LOCAL_ID')
            material = document['Material']
            _material_references(material)
        else:
            require(set(document) == {'MonoBehaviour'}, 'URP_MATERIAL_DOCUMENTS')
            _asset_version(document['MonoBehaviour'])
    return material
