"""Synthetic material-schema regressions; never native/visual acceptance evidence."""
import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import unittest
from unittest.mock import patch

import pouncer_output as p
from strict_output import StrictError
import test_material_metadata_integration as fixtures


class PouncerMainTexAliasTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.MaterialIntegrationTests()
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.f.spec['baseColorFile'] = 'source.png'
        source = self.f.project/self.f.prefix/'Source/source.png'
        source.parent.mkdir(); source.write_bytes(b'synthetic texture identity fixture')
        Path(str(source)+'.meta').write_text('fileFormatVersion: 2\nguid: '+'1'*32+'\n')
        self.base = dict(m_Texture=dict(fileID=2800000, guid='1'*32, type=3),
            m_Scale=dict(x=1, y=1), m_Offset=dict(x=0, y=0))
        self.alias = copy.deepcopy(self.base)
        self.rows = [{'_BaseMap': self.base}, {'_MainTex': self.alias}]
        self.f.asset['m_SavedProperties']['m_TexEnvs'] = self.rows

    def validate(self):
        self.f.save(); self.f.pouncer()

    def rejected(self, code='POUNCER_MAIN_TEX_ALIAS'):
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(StrictError, code):
            self.validate()

    def observe_rejection(self, code):
        text = io.StringIO()
        with redirect_stdout(text), self.assertRaisesRegex(StrictError, code):
            self.validate()
        lines = text.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        marker, value = lines[0].split(' ', 1)
        self.assertEqual(marker, 'CANDIDATE_POUNCER_TEXTURE_REJECTION')
        return json.loads(value), text.getvalue()

    def test_exact_official_alias_passes(self):
        self.validate()

    def test_alias_order_does_not_bypass_base_validation(self):
        self.rows.reverse(); self.validate()
        self.base['m_Texture']['guid'] = '2'*32
        self.alias['m_Texture']['guid'] = '2'*32
        self.rejected('POUNCER_MATERIAL_TEXTURE_BINDING')

    def test_matching_uv_values_pass_without_creating_an_independent_transform(self):
        for binding in (self.base, self.alias):
            binding['m_Scale'] = dict(x=2, y=.5)
            binding['m_Offset'] = dict(x=.125, y=-.25)
        self.validate()

    def test_previous_absent_or_null_maintex_remains_allowed(self):
        self.rows.pop(); self.validate()
        self.rows.append({'_MainTex': {'m_Texture': {'fileID': 0}}}); self.validate()

    def test_alias_requires_exact_guid_fileid_and_type(self):
        for key, value in [('guid', '2'*32), ('fileID', 2800001), ('type', 2)]:
            with self.subTest(key=key):
                self.alias['m_Texture'] = copy.deepcopy(self.base['m_Texture'])
                self.alias['m_Texture'][key] = value
                self.rejected('POUNCER_MAIN_TEX_ALIAS|URP_MATERIAL_TEXTURE_REFERENCE')

    def test_uv_difference_has_no_added_tolerance(self):
        for key in ('m_Scale', 'm_Offset'):
            with self.subTest(key=key):
                self.alias[key]['x'] += 1e-7
                self.rejected(); self.alias[key] = copy.deepcopy(self.base[key])

    def test_alias_and_base_require_complete_exact_uv_schema(self):
        for target in (self.base, self.alias):
            for key in ('m_Scale', 'm_Offset'):
                with self.subTest(target=target is self.base, key=key):
                    old = target.pop(key); self.rejected(); target[key] = old
        self.alias['extra'] = 1; self.rejected()

    def test_uv_rejects_nonfinite_boolean_and_string_values(self):
        for value in (float('nan'), float('inf'), True, '1'):
            with self.subTest(value=value):
                self.base['m_Scale']['x'] = value
                self.alias['m_Scale']['x'] = value
                self.rejected()

    def test_populated_maintex_requires_declared_base_map(self):
        self.rows.pop(0); self.rejected()

    def test_material_without_declared_texture_cannot_gain_maintex_image(self):
        self.f.spec['baseColorFile'] = ''
        self.base['m_Texture'] = dict(fileID=0)
        self.rejected('POUNCER_UNDECLARED_TEXTURE')

    def test_matching_alias_cannot_authorize_wrong_source_guid(self):
        for binding in (self.base, self.alias): binding['m_Texture']['guid'] = '2'*32
        self.rejected('POUNCER_MATERIAL_TEXTURE_BINDING')

    def test_other_nonempty_role_stays_rejected_even_with_same_image(self):
        self.rows.append({'_EmissionMap': copy.deepcopy(self.base)})
        self.rejected('POUNCER_UNDECLARED_TEXTURE')

    def test_pbr_and_emission_gates_stay_required(self):
        floats = self.f.asset['m_SavedProperties']['m_Floats']
        floats[0]['_Metallic'] = .9; self.rejected('POUNCER_MATERIAL_VALUES')
        floats[0]['_Metallic'] = .3
        self.f.asset['m_SavedProperties']['m_Colors'][1]['_EmissionColor']['r'] = .1
        self.rejected('POUNCER_UNDECLARED_EMISSION')

    def test_duplicate_alias_role_is_not_collapsed(self):
        self.rows.append({'_MainTex': copy.deepcopy(self.alias)})
        self.rejected('POUNCER_MATERIAL_PROPERTIES')

    def test_diagnostic_has_known_role_and_identity_booleans_only(self):
        self.rows.append({'_BumpMap': copy.deepcopy(self.base)})
        row, text = self.observe_rejection('POUNCER_UNDECLARED_TEXTURE')
        self.assertEqual(row, dict(materialIndex=0, role='_BumpMap', declaredBaseColor=True,
            textureIdentityMatchesBaseMap=True, scaleMatchesBaseMap=True, offsetMatchesBaseMap=True))
        self.assertNotIn('1'*32, text); self.assertNotIn('source.png', text)

    def test_diagnostic_never_prints_unknown_role_or_resource_path(self):
        secret = 'private-resource/path/DO_NOT_LOG'
        self.rows.append({secret: copy.deepcopy(self.base)})
        row, text = self.observe_rejection('POUNCER_UNDECLARED_TEXTURE')
        self.assertEqual(row['role'], 'OTHER'); self.assertNotIn(secret, text)

    def test_alias_rejection_diagnostic_shows_uv_difference_without_values(self):
        self.alias['m_Offset']['x'] = .1234567
        row, text = self.observe_rejection('POUNCER_MAIN_TEX_ALIAS')
        self.assertEqual(row['role'], '_MainTex')
        self.assertTrue(row['textureIdentityMatchesBaseMap'])
        self.assertTrue(row['scaleMatchesBaseMap']); self.assertFalse(row['offsetMatchesBaseMap'])
        self.assertNotIn('.1234567', text)

    def test_observation_exception_cannot_mask_original_error(self):
        self.rows.append({'_BumpMap': copy.deepcopy(self.base)})
        with patch.object(p.json, 'dumps', side_effect=RuntimeError('DO_NOT_LOG')):
            self.rejected('POUNCER_UNDECLARED_TEXTURE')


if __name__ == '__main__':
    unittest.main()
