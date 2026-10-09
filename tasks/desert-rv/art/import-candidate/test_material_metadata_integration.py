"""Direct integration tests: material envelope cannot replace PBR/source gates."""
import copy
from pathlib import Path
import tempfile
import unittest

from strict_output import StrictError
from test_urp_material_metadata import ASSET_VERSION_YAML, material_yaml
import pouncer_output as p
import weapon_output as w


class MaterialIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        self.prefix = 'Assets/DesertRV/CandidateArtImports/synthetic'
        self.path = self.project/self.prefix/'Materials/Material_00.mat'
        self.path.parent.mkdir(parents=True)
        Path(str(self.path)+'.meta').write_text('fileFormatVersion: 2\nguid: '+ 'f'*32+'\n')
        self.spec = dict(sourceName='OriginalSourceMaterial', metallic=.3, smoothness=.6,
            baseColor=dict(r=.2, g=.3, b=.4, a=1), baseColorFile='', normalFile='',
            metallicSmoothnessFile='', occlusionFile='', ormFile='')
        self.asset = dict(m_Name='Material_00',
            m_Shader=dict(fileID=4800000, guid='933532a4fcc9baf4fa0491de14d08ed7', type=3),
            m_SavedProperties=dict(m_Floats=[{'_Metallic': .3}, {'_Smoothness': .6}, {'_Cull': 2}],
            m_Colors=[{'_BaseColor': self.spec['baseColor'].copy()}, {'_EmissionColor': dict(r=0,g=0,b=0,a=1)}],
            m_TexEnvs=[{'_BaseMap': {'m_Texture': {'fileID': 0}}}]))
        self.readback = dict(sourceName=self.spec['sourceName'],
            materialPath=self.prefix+'/Materials/Material_00.mat', shader='Universal Render Pipeline/Lit',
            expectedColor=self.spec['baseColor'].copy(), actualColor=self.spec['baseColor'].copy(),
            expectedMetallic=.3, actualMetallic=.3, expectedSmoothness=.6, actualSmoothness=.6,
            actualCull=0, actualName='Material_00', materialGuid='f'*32, materialLocalId=2100000)

    def save(self, metadata=ASSET_VERSION_YAML):
        self.path.write_text(material_yaml(self.asset, metadata))

    def pouncer(self):
        return p.material_file(self.project, self.prefix, self.spec, 0)

    def weapon(self):
        return w.material_file(self.project, self.prefix, self.spec, 0, self.readback)

    def test_pouncer_material_path_name_passes_and_source_guess_fails(self):
        self.save(); self.pouncer()
        self.asset['m_Name'] = self.spec['sourceName']+'_Candidate'; self.save()
        with self.assertRaisesRegex(StrictError, 'POUNCER_MATERIAL_ASSET'): self.pouncer()

    def test_pouncer_pbr_emission_and_undeclared_texture_gates_remain(self):
        original = copy.deepcopy(self.asset)
        edits = [
            (lambda a: a['m_SavedProperties']['m_Floats'][0].update(_Metallic=.9), 'POUNCER_MATERIAL_VALUES'),
            (lambda a: a['m_SavedProperties']['m_Colors'][0]['_BaseColor'].update(r=.9), 'POUNCER_MATERIAL_VALUES'),
            (lambda a: a['m_SavedProperties']['m_Colors'][1]['_EmissionColor'].update(r=1), 'POUNCER_UNDECLARED_EMISSION'),
            (lambda a: a['m_SavedProperties']['m_TexEnvs'].append({'_UnexpectedMap': {'m_Texture': dict(fileID=2800000, guid='a'*32, type=3)}}), 'POUNCER_UNDECLARED_TEXTURE')]
        for edit, error in edits:
            with self.subTest(error=error):
                self.asset = copy.deepcopy(original); edit(self.asset); self.save()
                with self.assertRaisesRegex(StrictError, error): self.pouncer()

    def test_pouncer_source_texture_identity_remains(self):
        self.spec['baseColorFile'] = 'source.png'
        source = self.project/self.prefix/'Source/source.png'; source.parent.mkdir()
        Path(str(source)+'.meta').write_text('fileFormatVersion: 2\nguid: '+'1'*32+'\n')
        texture = dict(fileID=2800000, guid='1'*32, type=3)
        self.asset['m_SavedProperties']['m_TexEnvs'] = [{'_BaseMap': {'m_Texture': texture}}]
        self.save(); self.pouncer()
        texture['guid'] = '2'*32; self.save()
        with self.assertRaisesRegex(StrictError, 'POUNCER_MATERIAL_TEXTURE_BINDING'): self.pouncer()

    def test_weapon_native_name_guid_and_local_id_remain_bound(self):
        self.asset['m_SavedProperties']['m_Floats'][2]['_Cull'] = 0
        self.save(); self.weapon()
        original = copy.deepcopy(self.readback)
        for field, value, error in (('actualName', 'impostor', 'WEAPON_MATERIAL_ASSET'),
                ('materialGuid', 'e'*32, 'WEAPON_MATERIAL_PERSISTENT_IDENTITY'),
                ('materialLocalId', 2100001, 'WEAPON_MATERIAL_LOCAL_ID'),
                ('sourceName', 'impostor', 'WEAPON_MATERIAL_READBACK')):
            with self.subTest(field=field):
                self.readback = copy.deepcopy(original); self.readback[field] = value
                with self.assertRaisesRegex(StrictError, error): self.weapon()

    def test_weapon_pbr_and_texture_gates_remain(self):
        self.asset['m_SavedProperties']['m_Floats'][2]['_Cull'] = 0
        self.save(); self.weapon()
        original = copy.deepcopy(self.asset)
        for edit, error in (
            (lambda a: a['m_SavedProperties']['m_Floats'][0].update(_Metallic=.9), 'WEAPON_MATERIAL_ASSET_VALUES'),
            (lambda a: a['m_SavedProperties']['m_Colors'][0]['_BaseColor'].update(r=.9), 'WEAPON_MATERIAL_ASSET_VALUES'),
            (lambda a: a['m_SavedProperties']['m_TexEnvs'][0]['_BaseMap'].update(m_Texture=dict(fileID=2800000, guid='a'*32, type=3)), 'WEAPON_UNDECLARED_TEXTURE')):
            with self.subTest(error=error):
                self.asset = copy.deepcopy(original); edit(self.asset); self.save()
                with self.assertRaisesRegex(StrictError, error): self.weapon()

    def test_both_material_functions_use_strict_metadata_gate(self):
        self.save(ASSET_VERSION_YAML.replace('version: 10', 'version: 9'))
        with self.assertRaisesRegex(StrictError, 'URP_MATERIAL_VERSION_VALUE'): self.pouncer()
        self.asset['m_SavedProperties']['m_Floats'][2]['_Cull'] = 0
        self.save(ASSET_VERSION_YAML.replace('version: 10', 'version: 9'))
        with self.assertRaisesRegex(StrictError, 'URP_MATERIAL_VERSION_VALUE'): self.weapon()


if __name__ == '__main__':
    unittest.main()
