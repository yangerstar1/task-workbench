"""Synthetic adversarial tests, not evidence of a Unity render or native pass.

The Armored fixture is built here from the checked-in contract. Weapon's much
larger import-only asset fixture is reused, but failure samples, native execution
attributes, expected selections and rejection assertions are independently set.
Run with the existing import-candidate directory on PYTHONPATH.
"""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import struct
import unittest
from unittest.mock import patch
import zlib

from PIL import Image, ImageDraw, PngImagePlugin
import strict_output
import failed_capture_output as f


NATIVE_CASES = [
    'DesertRV.Tests.CandidateMeshMeasurementTests.ScaledTranslatedRotatedHierarchyMatchesIndependentSkinning',
    'DesertRV.Tests.CandidateMeshMeasurementTests.RejectsBlendShapesAndTruncatedSkinQuality',
    'DesertRV.Tests.CandidateMeshMeasurementTests.StaticMeshesAndFourMillimetreGateUseWorldVertices',
    'DesertRV.Tests.CandidateArtImportTests.ExecutePinnedDiscoveryOrBindingDiagnostics',
    'DesertRV.Tests.CandidateAnimationPolicyTests.OnlyArmoredAttackGetsTheSourceLoopException',
    'DesertRV.Tests.CandidateAnimationPolicyTests.EqualKeyValuesDoNotExcuseUnsafeTangents',
    'DesertRV.Tests.CandidateAnimationPolicyTests.MissingNativeAnimatorGetsCreatedAndReused',
    'DesertRV.Tests.CandidateAnimationPolicyTests.OpenCoreEmissionSurvivesRealSaveReimportAndReload',
    'DesertRV.Tests.CandidateAnimationPolicyTests.RenderTargetCleanupDetachesCameraBeforeDestroy',
    'DesertRV.Tests.CandidateMaterialIdentityTests.PersistedWeaponMaterialIdentitySurvivesNeutralSamplingAndRejectsImpostors',
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def native_xml(failed=True):
    return ('<test-run result="' + ('Failed' if failed else 'Passed') + '">' + ''.join(
        '<test-case fullname="' + name + '" result="' + ('Failed' if failed and name == f.ENTRY else 'Passed') +
        '" runstate="Runnable" start-time="2026-10-08T12:00:00Z" '
        'end-time="2026-10-08T12:00:01Z" duration="1.0"/>'
        for i, name in enumerate(NATIVE_CASES)) + '</test-run>')


class FailedCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='synthetic-failed-export-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'task'
        self.project = self.root / 'unity'
        self.ev = self.project / 'JourneyEvidence/CandidateArt'
        self.ev.mkdir(parents=True)
        self.out = self.root / 'runner-output'
        self.out.mkdir()
        contract = Path(strict_output.__file__).parent / 'contracts/armored-full-strict-37850840062.json'
        self.c = json.loads(contract.read_text())
        self.c['id'] = 'synthetic-failure-fixture'
        # The known schema permits non-textured candidate materials. This keeps
        # the fixture independent of ORM test generators and derived constants.
        self.c['files'] = [r for r in self.c['files'] if r['file'].endswith('.fbx')]
        for material in self.c['materials']:
            for key in ('baseColorFile', 'normalFile', 'metallicSmoothnessFile', 'occlusionFile', 'ormFile'):
                material[key] = ''
        self.prefix = 'Assets/DesertRV/CandidateArtImports/' + self.c['id']
        self.folder = self.project / self.prefix
        self.guid = 0
        for row in self.c['files']:
            data = ('SYNTHETIC INPUT; NOT REAL FBX: ' + row['file']).encode()
            path = self.write(self.prefix + '/Source/' + row['file'], data)
            row['sha256'] = sha(data)
            self.meta(path)
        cp = self.write('CandidateImportInput/contract.json', json.dumps(self.c))
        self.write(self.prefix + '/contract.json', cp.read_bytes())
        for name in ('Candidate.prefab', 'Candidate.controller', 'Materials/Material_00.mat',
                     'Materials/Material_01.mat', 'Materials/Core_Open.mat'):
            self.write(self.prefix + '/' + name, '%YAML 1.1\nSyntheticFixture: {}\n')
            self.meta(self.folder / name)
        for path in (self.folder, self.folder.parent, self.folder / 'Source', self.folder / 'Materials', self.folder / 'contract.json'):
            self.meta(path)
        deps = [self.prefix + '/' + n for n in ('Candidate.prefab', 'Candidate.controller',
            'Materials/Material_00.mat', 'Materials/Material_01.mat', 'Materials/Core_Open.mat')]
        deps.extend(self.prefix + '/Source/' + r['file'] for r in self.c['files'])
        self.imp = dict(mode='STRICT_BINDING', scope='FULL_CANDIDATE', kind='armored',
            status='candidate-structure-imported-unreviewed', contractSha256=sha(cp.read_bytes()),
            prefab=self.prefix + '/Candidate.prefab', dependencyHash='c' * 32, dependencies=deps,
            dependencySha256=self.dependency_hash(deps), candidateOnly=True, visualReviewed=False,
            gameplayReviewed=False, derivedTextures=[], rootCurves=[], failures=[],
            stillRequired=['SYNTHETIC PRIVATE TEXT: never export'], importedAnimatorPaths=['Bulwark_Rig'])
        for key in ('runUrl', 'sourceCommit', 'artifactName', 'artifactSha256'):
            self.imp[key] = self.c[key]
        self.imp['clips'] = [dict(row, frameRate=60, floatBindings=120, objectBindings=0) for row in self.c['clips']]
        neutral = copy.deepcopy(self.c['bindings']['neutralBaseline'])
        for clip in self.c['clips']:
            for group, name, axes in [('Position', 'position', 'xyz'), ('Rotation', 'rotation', 'xyzw'), ('Scale', 'scale', 'xyz')]:
                for axis in axes:
                    value = neutral[name][axis]
                    self.imp['rootCurves'].append(dict(state=clip['state'], property='m_Local' + group + '.' + axis,
                        keys=2, minimum=value, maximum=value, constant=True, tangentsSafe=True))
        self.cap = dict(graphicsDeviceType='OpenGLCore', graphicsDeviceName='llvmpipe (LLVM fixture)',
            status='not-complete', scope='real-Animator-pose-diagnostics-only', prefab=self.imp['prefab'],
            dependencySha256=self.imp['dependencySha256'], visualAccepted=False, gameplayAccepted=False,
            armoredAttackLoopIntent='PRIVATE narrative must be discarded', notCovered=['PRIVATE full stack here'],
            neutralRoot=neutral, neutralMeshWorldMin=dict(x=0,y=0,z=0),
            neutralMeshWorldMax=dict(x=1,y=2,z=3), neutralMeshWorldSize=dict(x=1,y=2,z=3), frames=[])
        labels = ['Idle-0.000', 'Idle-0.250', 'Walk-0.000', 'Walk-0.250', 'Windup-0.000',
                  'Attack-0.000', 'Attack-0.250', 'Recover-0.000', 'Hit-0.000', 'Death-0.000']
        for i, label in enumerate(labels):
            image = Image.new('RGB', (960,540), (25,43,61))
            ImageDraw.Draw(image).polygon([(110+i,32),(842,240+i),(321,498)], fill=(150+i,98,60))
            buffer = io.BytesIO(); image.save(buffer, format='PNG'); data = buffer.getvalue()
            name = f'frame-{i:04}.png'; (self.ev / name).write_bytes(data)
            self.cap['frames'].append(dict(image=name, requestedState=label, imageSha256=sha(data),
                meshPoseSha256=sha(('synthetic mesh ' + label).encode()), advanceSeconds=0, normalizedTime=0,
                worldMinY=0, groundReferenceY=0, rootLocalPositionDelta=0, rootLocalAngleDelta=0,
                rootLocalScaleDelta=0, stateHash=100+i, sampledVertices=1000, outsideViewportVertices=0,
                behindCameraVertices=0, belowReferenceVertices=0, transitioning=False, groundDiagnosticApplicable=True,
                rootLocalPosition=copy.deepcopy(neutral['position']), rootLocalRotation=copy.deepcopy(neutral['rotation']),
                rootLocalScale=copy.deepcopy(neutral['scale']), meshWorldMin=dict(x=0,y=0,z=0),
                meshWorldMax=dict(x=1,y=2,z=3), meshWorldSize=dict(x=1,y=2,z=3), meshSizeRatioToNeutral=dict(x=1,y=1,z=1)))
        self.native = self.root / 'artifacts/candidate-art/results.xml'
        self.native.parent.mkdir(parents=True); self.native.write_text(native_xml())
        self.summary = dict(status='FAILED_NOT_ACCEPTED', approved=False, errorCode='STRICT_NATIVE_FAILED',
            importCommit='a'*40, importRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/123')
        self.flush()

    def write(self, relative, data):
        path = self.project / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode()); return path

    def meta(self, path):
        self.guid += 1
        Path(str(path)+'.meta').write_text(f'fileFormatVersion: 2\nguid: {self.guid:032x}\nDefaultImporter: {{}}\n')

    def dependency_hash(self, names):
        # Independent encoding, not the exporter's digest helper.
        data = bytearray()
        for name in sorted(names):
            for filename in (name, name+'.meta'):
                raw = (self.project/filename).read_bytes(); encoded = filename.encode()
                data.extend(str(len(encoded)).encode()+b':'+encoded+str(len(raw)).encode()+b':'+raw)
        return sha(data)

    def flush(self):
        (self.ev/'import-report.json').write_text(json.dumps(self.imp))
        (self.ev/'capture-report.json').write_text(json.dumps(self.cap))

    def run_export(self, flush=True, native='failure', protected='success'):
        if flush: self.flush()
        return f.try_export_failed(self.root, self.out, self.c, self.summary, native, protected)

    def document(self):
        return json.loads((self.out/'failed-diagnostics.json').read_text())

    def rejected(self, **kwargs):
        before = copy.deepcopy(self.summary)
        self.assertFalse(self.run_export(**kwargs))
        self.assertEqual(before, self.summary)
        self.assertEqual([], list(self.out.iterdir()))
        self.assertFalse(list(self.out.parent.glob('.failed-*')))

    def set_ground(self, index, value):
        row = self.cap['frames'][index]
        row.update(worldMinY=value, belowReferenceVertices=10)
        row['meshWorldMin']['y'] = value
        row['meshWorldSize']['y'] = 2-value
        row['meshSizeRatioToNeutral']['y'] = (2-value)/2

    def test_import_rejection_summary_is_closed_and_keeps_original_failure(self):
        from contextlib import redirect_stdout
        output=io.StringIO()
        self.imp['dependencies']=['SECRET_PRIVATE_PATH']
        self.imp['prefab']='SECRET_PRIVATE_PATH'
        self.imp['status']='SECRET_PRIVATE_STATUS'
        self.imp['dependencyHash']='SECRET_HASH'
        self.imp['dependencySha256']='SECRET_HASH'
        with redirect_stdout(output):
            f.import_rejection_summary(self.c,self.imp,strict_output.StrictError('SECRET_EXCEPTION'))
        value=json.loads(output.getvalue().split(' ',1)[1])
        self.assertEqual(value['code'],'UNCLASSIFIED_IMPORT_REJECTION')
        self.assertEqual(value['prefab'],'UNEXPECTED_PREFAB')
        self.assertFalse(value['dependencySha256Valid'])
        self.assertNotIn('SECRET',output.getvalue())
        output=io.StringIO()
        with redirect_stdout(output):
            f.import_rejection_summary(self.c,self.imp,strict_output.StrictError('POUNCER_DEPENDENCY_INVENTORY'))
        self.assertEqual(json.loads(output.getvalue().split(' ',1)[1])['code'],'POUNCER_DEPENDENCY_INVENTORY')

    def test_collection_stage_reports_only_fixed_allowlisted_labels(self):
        from contextlib import redirect_stdout
        output=io.StringIO()
        with redirect_stdout(output):
            self.assertTrue(self.run_export())
        labels=output.getvalue().splitlines()
        self.assertEqual(labels,['FAILED_CAPTURE_COLLECTION_STAGE='+x for x in
            ('GUARD','FREEZE','NATIVE','IMPORT','GENERATED','CAPTURE','SNAPSHOT','STAGING','COMMIT')])
        output=io.StringIO()
        with redirect_stdout(output),self.assertRaises(ValueError):
            f.collection_stage('SECRET/path?token=private')
        self.assertEqual(output.getvalue(),'')

    def test_failed_native_exports_only_bounded_safe_diagnostics(self):
        (self.ev/'private.log').write_text('SECRET STACK')
        self.assertTrue(self.run_export())
        self.assertEqual(self.summary['status'], 'FAILED_DIAGNOSTICS')
        self.assertIs(self.summary['approved'], False)
        self.assertEqual((self.summary['nativeCases'],self.summary['nativeFailedCases'],self.summary['images']), (10,1,8))
        names = {p.relative_to(self.out).as_posix() for p in self.out.rglob('*') if p.is_file()}
        self.assertEqual(names, {'receipt.json','failed-diagnostics.json'} | {r['path'] for r in self.summary['files']})
        for name in names:
            self.assertNotIn(Path(name).suffix, ('.fbx','.prefab','.controller','.mat','.log','.xml','.cs'))
            if name.endswith('.json'):
                text = (self.out/name).read_text()
                for secret in ('PRIVATE','SECRET','failures','notCovered','stillRequired','reason','stack'):
                    self.assertNotIn(secret, text)
        self.assertEqual(self.document()['graphicsRenderer'], 'llvmpipe')
        self.assertNotIn('graphicsDeviceName', self.document())
        for row in self.summary['files']:
            self.assertEqual(sha((self.out/row['path']).read_bytes()), row['sha256'])

    def test_worst_measured_ground_is_selected_and_four_mm_still_fails(self):
        self.set_ground(9,-.42); self.set_ground(6,-.14); self.set_ground(2,-.09); self.set_ground(7,-.06)
        self.cap['frames'][0]['belowReferenceVertices']=999
        self.assertTrue(self.run_export())
        selected = [r['path'] for r in self.summary['files'] if r['path'].endswith('.png')]
        self.assertEqual(selected[:4], ['frames/frame-0009.png','frames/frame-0006.png','frames/frame-0002.png','frames/frame-0007.png'])
        self.assertFalse(self.document()['frames'][9]['groundWithinFourMillimeters'])
        self.assertAlmostEqual(self.document()['frames'][9]['groundDeltaY'], -.42)

    def test_only_one_real_partial_frame_is_sufficient(self):
        self.cap['frames']=self.cap['frames'][:1]; self.set_ground(0,-.00401)
        self.assertTrue(self.run_export()); self.assertEqual(self.summary['images'],1)
        self.assertEqual(self.document()['captureStatus'],'not-complete')

    def test_successful_native_quality_failure_remains_diagnostics(self):
        self.native.write_text(native_xml(False));self.summary['errorCode']='STRICT_GROUND_PENETRATION';self.set_ground(0,-.006)
        self.assertTrue(self.run_export(native='success'));self.assertIs(self.summary['approved'],False)

    def test_protected_failure_forbids_export(self): self.rejected(protected='failure')
    def test_exact_unity_failed_child_aggregate_exports_failed_diagnostics(self):
        self.native.write_text(native_xml().replace('<test-run result="Failed">',
            '<test-run result="Failed(Child)" testcasecount="10" total="10" passed="9" failed="1" inconclusive="0" skipped="0">'))
        self.assertTrue(self.run_export())
        self.assertEqual(self.summary['status'], 'FAILED_DIAGNOSTICS')
        self.assertIs(self.summary['approved'], False)
        self.assertEqual(self.summary['nativeFailedCases'], 1)

    def test_failed_child_aggregate_count_mismatch_and_unknown_suffix_reject(self):
        for result, passed in [('Failed(Child)', '10'), ('Failed(Forged)', '9')]:
            with self.subTest(result=result):
                self.native.write_text(native_xml().replace('<test-run result="Failed">',
                    '<test-run result="'+result+'" testcasecount="10" total="10" passed="'+passed+'" failed="1" inconclusive="0" skipped="0">'))
                self.rejected()

    def actual_xml_results(self, root):
        return {c.attrib['fullname']:c.attrib['result'] for c in root.iter('test-case')}

    def assert_actual_public_unity_failed_child_report(self, name):
        import xml.etree.ElementTree as ET
        data=(Path(__file__).parent / 'fixtures' / name).read_bytes()
        root=ET.fromstring(data)
        results=self.actual_xml_results(root)
        self.assertEqual(len(results),6)
        self.assertEqual(list(results.values()).count('Failed'),1)
        f.validate_native_aggregate(root,results)
        # Historical XML remains unchanged. Six-case history may validate the
        # aggregate parser, but cannot satisfy this revision's seven-case gate.
        self.native.write_bytes(data);self.rejected()

    def test_actual_public_armored_unity_failed_child_report(self):
        self.assert_actual_public_unity_failed_child_report('armored-failed-child-37866263641.xml')

    def test_actual_public_pouncer_unity_failed_child_report(self):
        self.assert_actual_public_unity_failed_child_report('pouncer-failed-child-37866416129.xml')

    def test_actual_failed_child_rejects_each_bad_aggregate(self):
        import xml.etree.ElementTree as ET
        original=(Path(__file__).parent / 'fixtures' / 'armored-failed-child-37866263641.xml').read_bytes()
        for field, value in [('testcasecount','7'),('total','5'),('passed','6'),('failed','0'),
                             ('inconclusive','1'),('skipped','1'),('result','Failed(ChildForged)')]:
            with self.subTest(field=field):
                root=ET.fromstring(original);root.set(field,value)
                with self.assertRaises(ValueError):
                    f.validate_native_aggregate(root,self.actual_xml_results(root))
        root=ET.fromstring(original)
        for case in root.iter('test-case'):case.set('result','Passed')
        root.set('passed','6');root.set('failed','0')
        with self.assertRaises(ValueError):
            f.validate_native_aggregate(root,self.actual_xml_results(root))

    def test_cancelled_native_forbids_export(self): self.rejected(native='cancelled')
    def test_unapproved_failure_code_forbids_export(self): self.summary['errorCode']='STRICT_SCHEMA_MISMATCH';self.rejected()
    def test_raw_exception_code_forbids_export(self): self.summary['errorCode']='at /secret/path token=SECRET';self.rejected()
    def test_missing_current_identity(self): self.summary.pop('importCommit');self.rejected()
    def test_wrong_report_identity(self): self.imp['sourceCommit']='b'*40;self.rejected()
    def test_wrong_contract_argument(self): self.c['sourceCommit']='b'*40;self.rejected()
    def test_boolean_schema_is_not_integer_version_one(self):
        self.c['schema']=True
        data=json.dumps(self.c).encode()
        self.write('CandidateImportInput/contract.json',data);self.write(self.prefix+'/contract.json',data)
        self.imp['contractSha256']=sha(data)
        self.rejected()
    def test_import_not_successful(self): self.imp['status']='not-complete';self.rejected()
    def test_import_failure_text_forbids_export(self): self.imp['failures']=['SECRET'];self.rejected()
    def shared_unrelated_fields(self):
        self.imp['muzzle']={'privateToken':'SECRET MUZZLE', 'approved':True, 'nested':{'visualReviewed':True}}
        self.imp['weaponCalibration']=['SECRET CALIBRATION', {'approved':True, 'sceneCalibrated':True}]
        self.cap['weapon']={'SECRET WEAPON':{'approved':True, 'visualAccepted':True, 'gameplayAccepted':True}}

    def test_armored_known_shared_fields_are_removed_without_interpreting_their_values(self):
        self.shared_unrelated_fields()
        self.assertTrue(self.run_export())
        expected=['import-report.json.muzzle','import-report.json.weaponCalibration','capture-report.json.weapon']
        self.assertEqual(self.summary['normalizedAwayFields'],expected)
        doc=self.document();self.assertEqual(doc['normalizedAwayFields'],expected)
        for key in ('approved','visualApproved','gameplayAccepted','calibratedForScene'):
            self.assertIs(doc[key],False);self.assertIs(self.summary[key],False)
        self.assertTrue(all(b'SECRET' not in p.read_bytes() for p in self.out.rglob('*') if p.is_file()))
        self.assertEqual(doc['rawReportSha256']['import-report.json'],sha((self.ev/'import-report.json').read_bytes()))

    def test_armored_unrelated_fields_cannot_mask_common_capture_approval(self):
        self.shared_unrelated_fields();self.cap['visualAccepted']=True;self.rejected()

    def test_armored_unrelated_fields_cannot_mask_common_import_approval(self):
        self.shared_unrelated_fields();self.imp['visualReviewed']=True;self.rejected()

    def test_armored_unknown_shared_lookalike_is_still_rejected(self):
        self.shared_unrelated_fields();self.cap['weaponExtra']={'SECRET':True};self.rejected()

    def test_armored_null_shared_fields_are_also_explicitly_recorded(self):
        self.imp['muzzle']=None;self.imp['weaponCalibration']=None;self.cap['weapon']=None
        self.assertTrue(self.run_export());self.assertEqual(len(self.summary['normalizedAwayFields']),3)
    def test_unknown_capture_field(self): self.cap['rawLogs']='SECRET';self.rejected()
    def test_unknown_frame_field(self): self.cap['frames'][0]['rawStack']='SECRET';self.rejected()
    def test_unknown_nested_field(self): self.cap['neutralRoot']['renderers'][0]['private']='SECRET';self.rejected()
    def test_nonfinite_number(self): self.cap['frames'][0]['worldMinY']=float('nan');self.rejected()
    def test_infinite_number(self): self.cap['frames'][0]['normalizedTime']=float('inf');self.rejected()
    def test_boolean_is_not_a_number(self): self.cap['frames'][0]['worldMinY']=False;self.rejected()
    def test_null_graphics(self): self.cap['graphicsDeviceType']='Null';self.rejected()
    def test_approval_is_never_accepted(self): self.cap['visualAccepted']=True;self.rejected()
    def test_future_kind_is_not_generalized(self): self.c['kind']='pouncer';self.rejected()
    def test_nonweapon_ground_policy_cannot_be_disabled(self): self.cap['frames'][0]['groundDiagnosticApplicable']=False;self.rejected()
    def test_bad_state_label(self): self.cap['frames'][0]['requestedState']='http://secret';self.rejected()
    def test_duplicate_state_label(self): self.cap['frames'][1]['requestedState']=self.cap['frames'][0]['requestedState'];self.rejected()
    def test_path_escape(self): self.cap['frames'][0]['image']='../../secret.png';self.rejected()
    def test_image_symlink(self):
        path=self.ev/'frame-0000.png';path.unlink();path.symlink_to(self.ev/'frame-0001.png');self.rejected()
    def test_source_symlink(self):
        path=self.folder/'Source'/self.c['modelFile'];path.unlink();path.symlink_to(self.folder/'Candidate.prefab');self.rejected()
    def test_changed_source_bytes(self):
        (self.folder/'Source'/self.c['modelFile']).write_bytes(b'CHANGED');self.rejected()
    def test_fake_native_without_execution_timestamps(self):
        self.native.write_text(self.native.read_text().replace('start-time="2026-10-08T12:00:00Z" ',''));self.rejected()
    def test_native_entry_skipped(self):
        self.native.write_text(self.native.read_text().replace('result="Failed" runstate=', 'result="Skipped" runstate=', 1));self.rejected()
    def test_native_entry_not_runnable(self):
        self.native.write_text(self.native.read_text().replace('runstate="Runnable"','runstate="NotRunnable"',1));self.rejected()
    def test_native_missing_runstate(self):
        self.native.write_text(self.native.read_text().replace(' runstate="Runnable"','',1));self.rejected()
    def test_native_case_not_executed(self):
        self.native.write_text(self.native.read_text().replace('runstate="Runnable"','runstate="Runnable" executed="False"',1));self.rejected()
    def test_native_wrong_fullname(self):
        self.native.write_text(self.native.read_text().replace('RenderTargetCleanupDetachesCameraBeforeDestroy','Forged'));self.rejected()
    def test_native_five_cases(self):
        import xml.etree.ElementTree as ET
        root=ET.fromstring(self.native.read_bytes());root.remove(list(root)[-1]);self.native.write_bytes(ET.tostring(root));self.rejected()
    def test_native_duplicate_case(self):
        self.native.write_text(self.native.read_text().replace(NATIVE_CASES[-1], NATIVE_CASES[0]));self.rejected()
    def test_native_nan_duration(self): self.native.write_text(self.native.read_text().replace('duration="1.0"','duration="nan"'));self.rejected()
    def test_real_unity_space_separated_timestamp_format(self):
        self.native.write_text(self.native.read_text().replace('2026-10-08T12:', '2026-10-08 12:'))
        self.assertTrue(self.run_export())
    def test_output_symlink_is_never_replaced(self):
        original=self.out;target=self.root/'other-output';target.mkdir();original.rmdir();original.symlink_to(target, target_is_directory=True)
        self.rejected();self.assertTrue(original.is_symlink());self.assertEqual([],list(target.iterdir()))
    def test_no_frames_or_measurements_cannot_create_false_evidence(self):
        self.cap['frames']=[];self.rejected()

    def test_missing_png_keeps_safe_numbers(self):
        (self.ev/'frame-0000.png').unlink();self.assertTrue(self.run_export())
        row=self.document()['frames'][0];self.assertEqual(row['imageState'],'MISSING');self.assertIsNone(row['exportedImage'])

    def test_bad_png_keeps_safe_numbers(self):
        path=self.ev/'frame-0000.png';path.write_bytes(b'SECRET not a PNG');self.cap['frames'][0]['imageSha256']=sha(path.read_bytes())
        self.assertTrue(self.run_export());self.assertEqual(self.document()['frames'][0]['imageState'],'INVALID_PNG')

    def test_wrong_png_hash_keeps_numbers_but_excludes_image(self):
        self.cap['frames'][0]['imageSha256']='0'*64;self.assertTrue(self.run_export())
        self.assertEqual(self.document()['frames'][0]['imageState'],'HASH_MISMATCH')

    def test_blank_wrong_dimensions_metadata_and_crc_are_not_exported(self):
        mutations=[]
        for size in ((960,540),(32,32)):
            buf=io.BytesIO();Image.new('RGB',size).save(buf,format='PNG');mutations.append(buf.getvalue())
        image=Image.open(self.ev/'frame-0002.png');meta=PngImagePlugin.PngInfo();meta.add_text('private','SECRET')
        buf=io.BytesIO();image.save(buf,format='PNG',pnginfo=meta);mutations.append(buf.getvalue())
        corrupted=bytearray((self.ev/'frame-0003.png').read_bytes());corrupted[-1]^=1;mutations.append(bytes(corrupted))
        for i,data in enumerate(mutations):
            (self.ev/f'frame-{i:04}.png').write_bytes(data);self.cap['frames'][i]['imageSha256']=sha(data)
        self.assertTrue(self.run_export())
        self.assertEqual([r['imageState'] for r in self.document()['frames'][:4]],['INVALID_PNG']*4)

    def test_crc_correct_hidden_idat_text_is_not_exported(self):
        path=self.ev/'frame-0000.png'
        chunks=png_chunks(path.read_bytes())
        chunks=[(tag, body+b'SECRET RAW STACK' if tag==b'IDAT' else body) for tag,body in chunks]
        data=png_bytes(chunks);path.write_bytes(data);self.cap['frames'][0]['imageSha256']=sha(data)
        self.assertTrue(self.run_export())
        self.assertEqual(self.document()['frames'][0]['imageState'],'INVALID_PNG')
        self.assertIsNone(self.document()['frames'][0]['exportedImage'])
        self.assertTrue(all(b'SECRET RAW STACK' not in p.read_bytes() for p in self.out.rglob('*') if p.is_file()))

    def test_all_missing_pngs_still_commit_safe_numbers_without_images(self):
        for path in self.ev.glob('*.png'):path.unlink()
        self.assertTrue(self.run_export());self.assertEqual(self.summary['images'],0)
        self.assertEqual({p.name for p in self.out.iterdir()},{'receipt.json','failed-diagnostics.json'})

    def test_change_after_freeze_rejects_without_payload_or_summary_mutation(self):
        original=f.sanitize_capture
        def changed(*args):
            result=original(*args);(self.folder/'Source'/self.c['modelFile']).write_bytes(b'CHANGED DURING VALIDATION');return result
        with patch.object(f,'sanitize_capture',side_effect=changed):self.rejected()

    def test_report_change_after_freeze_rejected(self):
        original=f.sanitize_capture
        def changed(*args):
            result=original(*args);(self.ev/'capture-report.json').write_text('SECRET');return result
        with patch.object(f,'sanitize_capture',side_effect=changed):self.rejected()

    def test_missing_png_appearing_after_freeze_rejected(self):
        path=self.ev/'frame-0000.png';data=path.read_bytes();path.unlink();original=f.sanitize_capture
        def changed(*args):
            result=original(*args);path.write_bytes(data);return result
        with patch.object(f,'sanitize_capture',side_effect=changed):self.rejected()

    def test_atomic_commit_failure_preserves_original_safe_receipt_state(self):
        with patch.object(Path,'replace',side_effect=OSError('SECRET EXCEPTION STACK')):self.rejected()

    def test_injected_unlisted_staging_log_cannot_escape_atomic_commit(self):
        original=Path.write_bytes
        def inject(path,data):
            result=original(path,data)
            if path.name=='receipt.json' and path.parent.name.startswith('.failed-diagnostics-'):
                original(path.parent/'unlisted.log',b'SECRET STACK INJECTION')
            return result
        with patch.object(Path,'write_bytes',inject):self.rejected()

    def test_injected_staging_symlink_cannot_escape_atomic_commit(self):
        original=Path.write_bytes
        def inject(path,data):
            result=original(path,data)
            if path.name=='receipt.json' and path.parent.name.startswith('.failed-diagnostics-'):
                (path.parent/'source-asset').symlink_to(self.folder/'Candidate.prefab')
            return result
        with patch.object(Path,'write_bytes',inject):self.rejected()

    def test_duplicate_json_is_not_accepted(self):
        (self.ev/'capture-report.json').write_text('{"frames":[],"frames":[]}');self.rejected(flush=False)


class WeaponFailureTests(unittest.TestCase):
    def setUp(self):
        # Reuse only a large independently maintained imported-asset fixture.
        # The assertions and failure picture below do not reuse exporter labels,
        # counts, selection logic or expected diagnostic values.
        import test_weapon_output
        self.fixture=test_weapon_output.WeaponExportTests();self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.x=self.fixture;self.x.out.mkdir()
        self.complete_capture=copy.deepcopy(self.x.cap)
        self.x.native.write_text(native_xml())
        self.summary=dict(status='FAILED_NOT_ACCEPTED',approved=False,errorCode='STRICT_NATIVE_FAILED',
            importCommit='a'*40,importRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/123')
        row=copy.deepcopy(self.x.cap['weapon']['samples'][0]);row['poseAccepted']=False
        row['left']['wristGap']=.027;row['left']['reason']='SECRET failure stack';row['left']['solved']=False
        self.x.cap['weapon'].update(status='failed-imported-arm-count-mechanics',mechanicsPassed=False,
            samples=[row],maxWristGapWorld=.027,failures=['SECRET whole failure'])
        frame=copy.deepcopy(self.x.cap['frames'][0]);frame['requestedState']='FAILED-Reload-0-plus-12-0.000000';frame['normalizedTime']=0
        self.x.cap.update(status='not-complete',frames=[frame])

    def run_export(self):
        self.x.flush()
        return f.try_export_failed(self.x.root,self.x.out,self.x.c,self.summary,'failure','success')

    def test_partial_failed_mechanics_keeps_failed_frame_and_finite_metrics(self):
        self.assertTrue(self.run_export());doc=json.loads((self.x.out/'failed-diagnostics.json').read_text())
        self.assertEqual((self.summary['images'],self.summary['weaponSamples']),(1,1))
        self.assertEqual(doc['frames'][0]['requestedState'],'FAILED-Reload-0-plus-12-0.000000')
        self.assertAlmostEqual(doc['weaponSamples'][0]['left']['wristGap'],.027)
        self.assertIs(doc['weaponSamples'][0]['poseAccepted'],False)
        self.assertIsNone(doc['frames'][0]['groundWithinFourMillimeters'])
        self.assertNotIn('SECRET',json.dumps(doc));self.assertNotIn('reason',json.dumps(doc))

    def test_complete_capture_followed_by_native_cleanup_failure_remains_failed(self):
        self.x.cap=self.complete_capture
        self.assertTrue(self.run_export())
        self.assertEqual((self.summary['observedFrames'],self.summary['weaponSamples'],self.summary['images']),(25,4463,8))
        self.assertEqual(self.summary['status'],'FAILED_DIAGNOSTICS')
        self.assertIs(self.summary['approved'],False)

    def test_unknown_sample_or_arm_schema_rejected(self):
        self.x.cap['weapon']['samples'][0]['left']['rawStack']='SECRET'
        self.assertFalse(self.run_export());self.assertEqual([],list(self.x.out.iterdir()))

    def test_unmeasured_failure_label_is_rejected(self):
        self.x.cap['frames'][0]['requestedState']='FAILED-Reload-11-plus-1-1.000000'
        self.assertFalse(self.run_export())

    def test_ordinary_picture_cannot_be_invented_for_dense_unphotographed_sample(self):
        self.x.cap['frames'][0]['requestedState']='Reload-0-plus-12-0.000000'
        self.assertFalse(self.run_export())

    def test_no_frames_can_still_export_measured_failure_numbers(self):
        self.x.cap['frames']=[];self.assertTrue(self.run_export());self.assertEqual(self.summary['images'],0)


def png_chunks(data):
    result=[];offset=8
    while offset<len(data):
        length=int.from_bytes(data[offset:offset+4],'big')
        result.append((data[offset+4:offset+8],data[offset+8:offset+8+length]));offset+=length+12
    return result


def png_bytes(chunks):
    return b'\x89PNG\r\n\x1a\n'+b''.join(struct.pack('>I',len(body))+tag+body+
        struct.pack('>I',zlib.crc32(tag+body)&0xffffffff) for tag,body in chunks)


class PngStructureTests(unittest.TestCase):
    def setUp(self):
        image=Image.new('RGB',(960,540),(20,40,60));ImageDraw.Draw(image).rectangle((100,40,400,330),fill=(200,70,40))
        out=io.BytesIO();image.save(out,format='PNG');self.original=out.getvalue()
        self.chunks=png_chunks(self.original)
        self.header=self.chunks[0][1]
        self.compressed=b''.join(body for tag,body in self.chunks if tag==b'IDAT')
        self.raw=zlib.decompress(self.compressed)

    def state(self,data):return f.image_state(data,sha(data))

    def test_valid_rgb24_and_split_idat_preserve_original_bytes(self):
        self.assertEqual(self.state(self.original),'VERIFIED')
        n=len(self.compressed)//2
        split=png_bytes([(b'IHDR',self.header),(b'IDAT',self.compressed[:n]),(b'IDAT',self.compressed[n:]),(b'IEND',b'')])
        self.assertEqual(self.state(split),'VERIFIED')

    def test_crc_correct_covert_payloads_and_structural_violations(self):
        secret=b'SECRET STACK /home/user/token=abc'
        base=[(b'IHDR',self.header),(b'IDAT',self.compressed),(b'IEND',b'')]
        variants={
            'IEND with payload':[(b'IHDR',self.header),(b'IDAT',self.compressed),(b'IEND',secret)],
            'gAMA tail':[(b'IHDR',self.header),(b'gAMA',struct.pack('>I',45455)+secret),*base[1:]],
            'gAMA ordinary unsupported metadata':[(b'IHDR',self.header),(b'gAMA',struct.pack('>I',45455)),*base[1:]],
            'cHRM text in fixed-size metadata':[(b'IHDR',self.header),(b'cHRM',secret[:32].ljust(32,b' ')),*base[1:]],
            'IHDR payload':[(b'IHDR',self.header+secret),*base[1:]],
            'duplicate IHDR':[(b'IHDR',self.header),*base],
            'IDAT raw tail':[(b'IHDR',self.header),(b'IDAT',self.compressed+secret),(b'IEND',b'')],
            'IDAT second zlib stream':[(b'IHDR',self.header),(b'IDAT',self.compressed+zlib.compress(secret)),(b'IEND',b'')],
            'extra IDAT second stream':[(b'IHDR',self.header),(b'IDAT',self.compressed),(b'IDAT',zlib.compress(secret)),(b'IEND',b'')],
            'decoded tail':[(b'IHDR',self.header),(b'IDAT',zlib.compress(self.raw+secret)),(b'IEND',b'')],
            'short decoded image':[(b'IHDR',self.header),(b'IDAT',zlib.compress(self.raw[:-1])),(b'IEND',b'')],
            'truncated zlib':[(b'IHDR',self.header),(b'IDAT',self.compressed[:-1]),(b'IEND',b'')],
            'invalid scanline filter':[(b'IHDR',self.header),(b'IDAT',zlib.compress(b'\xff'+self.raw[1:])),(b'IEND',b'')],
            'IDAT after IEND':[*base,(b'IDAT',secret)],
            'duplicate IEND':[*base,(b'IEND',b'')],
            'missing IDAT':[(b'IHDR',self.header),(b'IEND',b'')],
        }
        for label,chunks in variants.items():
            with self.subTest(label=label):self.assertEqual(self.state(png_bytes(chunks)),'INVALID_PNG')
        self.assertEqual(self.state(self.original+secret),'INVALID_PNG')

    def test_rgba_hidden_color_cannot_look_nonblank_after_alpha_is_discarded(self):
        for alpha in (0,255):
            with self.subTest(alpha=alpha):
                image=Image.open(io.BytesIO(self.original)).convert('RGBA');image.putalpha(alpha)
                out=io.BytesIO();image.save(out,format='PNG')
                self.assertEqual(self.state(out.getvalue()),'INVALID_PNG')


if __name__ == '__main__':
    unittest.main()
