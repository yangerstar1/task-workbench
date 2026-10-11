#!/usr/bin/env python3
"""Actual Git/ZIP/XML corruption checks. No Unity, Android process, network or auth."""
import copy
import json
import os
from pathlib import Path
import struct
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

import journey_android as a
a.load_build_modules()
import test_verify_tracer_shader as fixtures
import test_journey_linux_export as linux_fixtures

class AndroidArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def apk(self, files):
        path=self.root/'fixture.apk'
        with zipfile.ZipFile(path,'w') as archive:
            for name,raw in files.items():archive.writestr(name,raw)
        return path
    def files(self, include_lit=True, lit_class=48):
        entries=[(a.shader.TARGET,1,17)]
        if include_lit:entries.append((a.SURFACE_SHADER,1,23))
        manager,_=fixtures.asset([(5,94,fixtures.registry_body(entries))],['sharedassets0.assets'])
        packed,_=fixtures.asset([(17,48,b'SYNTHETIC_UNLIT_SHADER'),(23,lit_class,b'SYNTHETIC_LIT_SHADER')])
        files={a.shader.GLOBAL:manager,'DesertRV_Data/sharedassets0.assets':packed};result={}
        for name,raw in files.items():
            raw=bytearray(raw);struct.pack_into('<i',raw,48+len(a.shader.UNITY)+1,13)
            result[name.replace('DesertRV_Data/','assets/bin/Data/')]=bytes(raw)
        return result
    def test_android_registry_resolves_actual_class48_and_target13(self):
        result=a.apk_shader(self.apk(self.files()));self.assertEqual(result['registry']['target'],13)
        self.assertEqual(result['resolvedShader']['classId'],48);self.assertFalse(result['renderingVerified'])
        self.assertEqual(result['surfaceShader'],'Universal Render Pipeline/Lit')
        self.assertEqual((result['resolvedSurfaceShader']['classId'],result['resolvedSurfaceShader']['pathId']),(48,23))
    def test_unlit_alone_and_lit_marker_outside_registry_cannot_pass(self):
        files=self.files(include_lit=False);files['assets/lit-marker.txt']=a.SURFACE_SHADER.encode()
        with self.assertRaisesRegex(Exception,'MISSING_SHADER'):a.apk_shader(self.apk(files))
    def test_lit_registry_pointer_must_resolve_packed_class48(self):
        with self.assertRaisesRegex(Exception,'SHADER_CLASS_MISMATCH'):a.apk_shader(self.apk(self.files(lit_class=21)))
    def test_linux_serialized_assets_are_not_android_evidence(self):
        files=self.files();name='assets/bin/Data/globalgamemanagers';raw=bytearray(files[name]);struct.pack_into('<i',raw,48+len(a.shader.UNITY)+1,24);files[name]=bytes(raw)
        with self.assertRaisesRegex(Exception,'SERIALIZED_PLATFORM'):a.apk_shader(self.apk(files))
    def test_split_asset_order_is_numeric_and_missing_chunks_fail(self):
        files=self.files();name='assets/bin/Data/sharedassets0.assets';raw=files.pop(name)
        for i in range(12):files[name+'.split'+str(i)]=raw[len(raw)*i//12:len(raw)*(i+1)//12]
        a.apk_shader(self.apk(files));files.pop(name+'.split5')
        with self.assertRaisesRegex(Exception,'ANDROID_SHADER_MISSING'):a.apk_shader(self.apk(files))
    def test_direct_plus_split_shadow_and_escape_fail(self):
        files=self.files();files['assets/bin/Data/sharedassets0.assets.split0']=b'unexpected'
        with self.assertRaisesRegex(Exception,'ANDROID_SHADER_AMBIGUOUS'):a.apk_shader(self.apk(files))
        files,_,_=fixtures.fixtures(external='../outside'); converted={}
        for name,raw in files.items():
            raw=bytearray(raw);struct.pack_into('<i',raw,48+len(a.shader.UNITY)+1,13);converted[name.replace('DesertRV_Data/','assets/bin/Data/')]=bytes(raw)
        with self.assertRaises(Exception):a.apk_shader(self.apk(converted))
    def test_marker_text_outside_registry_never_passes(self):
        files=self.files();name='assets/bin/Data/globalgamemanagers';files[name]=files[name].replace(a.shader.TARGET.encode(),b'X'*len(a.shader.TARGET));files['assets/'+a.shader.TARGET.replace('/','-')]=a.shader.TARGET.encode()
        with self.assertRaisesRegex(Exception,'MISSING_SHADER'):a.apk_shader(self.apk(files))
    def test_exact_xml_rejects_duplicate_missing_failed_and_extra_cases(self):
        folder=self.root/'artifacts';folder.mkdir();path=folder/'result.xml';names={'Case.One','Case.Two'}
        def write():
            root=ET.Element('test-run',result='Passed',total='2',passed='2',failed='0',skipped='0',inconclusive='0')
            for name in names:ET.SubElement(root,'test-case',fullname=name,result='Passed')
            return root
        with patch.object(a,'ROOT',self.root):
            root=write();ET.ElementTree(root).write(path);self.assertEqual(a.exact_xml(folder,names)['count'],2)
            for mutation in ('duplicate','missing','failed','extra'):
                root=write()
                if mutation=='duplicate':root[1].set('fullname',root[0].get('fullname'))
                if mutation=='missing':root.remove(root[0])
                if mutation=='failed':root[0].set('result','Failed')
                if mutation=='extra':ET.SubElement(root,'test-case',fullname='Other',result='Passed')
                ET.ElementTree(root).write(path)
                with self.subTest(mutation=mutation),self.assertRaisesRegex(Exception,'ANDROID_NATIVE_GATE'):a.exact_xml(folder,names)
    def test_native_receipt_requires_android_development_unreviewed_profile(self):
        fixture=linux_fixtures.JourneyLinuxExportTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        value=fixture.receipt();value.update(label=a.LABEL,target='Android',backend='IL2CPP',define='DESERTRV_CANDIDATE_ANDROID',executable=a.APK,temporarySettingsApiFields=a.FIELDS)
        a.native_receipt(value)
        for key,bad in [('target','StandaloneLinux64'),('define','DESERTRV_CANDIDATE_LINUX'),('backend','Mono2x'),('approved',True),('development',False),('performanceTestResourcesExcluded',False),('sourceCommit','f'*40)]:
            altered=copy.deepcopy(value);altered[key]=bad
            with self.subTest(key=key),self.assertRaises(Exception):a.native_receipt(altered)
        altered=copy.deepcopy(value);altered['privateLog']='secret'
        with self.assertRaisesRegex(Exception,'ANDROID_RECEIPT_SCHEMA'):a.native_receipt(altered)
    def test_android_diagnostic_does_not_satisfy_linux_success(self):
        fixture=linux_fixtures.JourneyLinuxExportTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        diagnostic=fixture.diagnostic();diagnostic.update(label='CANDIDATE_ANDROID_BUILD_DIAGNOSTIC',reportTarget='ANDROID')
        a.linux.native_diagnostic(diagnostic,platform='ANDROID');self.assertTrue(a.linux.diagnostic_success(diagnostic,target='ANDROID'))
        self.assertFalse(a.linux.diagnostic_success(diagnostic))
        with self.assertRaises(Exception):a.linux.native_diagnostic(diagnostic)
    def test_unvalidated_failure_never_exports_staged_apk_or_raw_logs(self):
        staged=self.root/'staged';staged.mkdir();(staged/a.APK).write_bytes(b'not-authorized');(staged/'editor.log').write_text('private')
        with patch.object(a,'PUBLIC',self.root/'public'),patch.object(a,'STAGED',staged),patch.dict(os.environ,GITHUB_SHA='a'*40,GITHUB_RUN_ID='123',NATIVE_OUTCOME='failure',UNION_OUTCOME='success'):
            a.export();self.assertEqual({p.name for p in a.PUBLIC.iterdir()},{'status.json'})
            self.assertNotIn('private', (a.PUBLIC/'status.json').read_text())
    def test_duplicate_json_keys_and_unknown_public_fields_rejected(self):
        path=self.root/'bad.json';path.write_text('{"schema":1,"schema":2}')
        with self.assertRaises(Exception):a.sealed(path)
        with self.assertRaisesRegex(Exception,'ANDROID_MANIFEST_SCHEMA'):a.validate_manifest({'secret':'never publish'}, {})

class AndroidFirstFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for name in ('CONTROL','OBSERVATION','STATE','PUBLIC','STAGED'):
            value=self.root/name.lower();change=patch.object(a,name,value);change.start();self.addCleanup(change.stop)
        a.STATE.mkdir()
        change=patch.dict(os.environ,GITHUB_SHA='a'*40,GITHUB_RUN_ID='123',GITHUB_OUTPUT=str(self.root/'outputs'))
        change.start();self.addCleanup(change.stop)
    def command(self,name):
        with patch.object(a,'dispatch',return_value={}),patch.object(sys,'argv',['journey_android.py',name]):a.main()
    def test_real_stage_receipt_failure_survives_cleanup_and_stays_first(self):
        a.observe(exit_code=0);(a.STATE/'android-build-receipt.json').write_text('{}')
        with patch.object(a,'verify',return_value={}),self.assertRaisesRegex(ValueError,'ANDROID_RECEIPT_SCHEMA'):self.command('stage')
        failure=a.sealed(a.CONTROL)['firstFailure']
        self.assertEqual(failure,dict(command='stage',stage='NATIVE_RECEIPT',code='ANDROID_RECEIPT_SCHEMA',exceptionClass='ValueError'))
        a.control(['SUCCEEDED','FAILED','SUCCEEDED','SUCCEEDED']);a.record_failure('restore',RuntimeError('private path and token'))
        self.assertEqual(a.sealed(a.CONTROL)['firstFailure'],failure)
        self.command('control-report');self.assertIn('control_valid=true',Path(os.environ['GITHUB_OUTPUT']).read_text())
    def test_real_export_failure_retains_safe_unknown_class_without_apk_or_message(self):
        a.atomic(a.CONTROL,a.control_value(['SUCCEEDED']*4))
        with patch.dict(os.environ,NATIVE_OUTCOME='success',UNION_OUTCOME='success'),patch.object(a,'verify',side_effect=RuntimeError('secret-token /private/path')):
            with self.assertRaises(RuntimeError):self.command('export')
        value=a.sealed(a.CONTROL)
        self.assertEqual(value['firstFailure'],dict(command='export',stage='EXPORT',code=None,exceptionClass='RuntimeError'))
        self.assertNotIn('secret',a.CONTROL.read_text());self.assertNotIn('/private',a.CONTROL.read_text());self.assertFalse((a.PUBLIC/a.APK).exists())
        self.command('control-report');self.assertIn('control_valid=true',Path(os.environ['GITHUB_OUTPUT']).read_text())
        for key,bad in [('code','ANDROID_FAKE_SECRET'),('command','arbitrary'),('stage','private-stage'),('exceptionClass','UnknownSecret')]:
            altered=copy.deepcopy(value);altered['firstFailure'][key]=bad
            with self.subTest(key=key),self.assertRaises(ValueError):a.validate_control(altered)

class AndroidDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.patch=patch.object(a,'ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        self.task=self.root/'tasks/desert-rv';self.task.mkdir(parents=True)
        self.patch_task=patch.object(a,'TASK',self.task);self.patch_task.start();self.addCleanup(self.patch_task.stop)
        self.command('init','--quiet');self.command('config','user.email','fixture@example.invalid');self.command('config','user.name','Fixture')
        (self.task/'SOURCE-STATE.json').write_text('{}');selection=self.root/a.SELECTION;selection.parent.mkdir(parents=True);selection.write_text('{}')
        self.command('add','.');self.command('commit','--quiet','-m','base');self.base=self.command('rev-parse','HEAD').strip()
        p=patch.object(a,'BASE',self.base);p.start();self.addCleanup(p.stop)
        request=self.root/a.REQUEST;request.parent.mkdir(parents=True)
        request.write_text(json.dumps(dict(schema=1,requestId=a.REQUEST_ID,baseCommit=self.base,sourceStateSha256=a.sha(self.task/'SOURCE-STATE.json'),selection=a.SELECTION,selectionSha256=a.sha(selection),image=a.IMAGE)))
        self.command('add','.');self.command('commit','--quiet','-m','candidate');self.head=self.command('rev-parse','HEAD').strip()
        self.event=dict(before=self.base,after=self.head,ref=a.REF,created=False,deleted=False,forced=False,sender=dict(login='yangerstar1'),head_commit=dict(id=self.head),repository=dict(full_name=a.REPO,private=False,fork=False,default_branch='main',owner=dict(login='yangerstar1')))
        self.event_path=self.root/'event.json';self.write_event()
        self.env=dict(GITHUB_ACTIONS='true',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',GITHUB_REPOSITORY=a.REPO,GITHUB_REPOSITORY_VISIBILITY='public',GITHUB_ACTOR='yangerstar1',GITHUB_TRIGGERING_ACTOR='yangerstar1',GITHUB_EVENT_NAME='push',GITHUB_REF=a.REF,GITHUB_WORKFLOW_REF=a.REPO+'/'+a.WORKFLOW+'@'+a.REF,GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_ID='123',GITHUB_SHA=self.head,GITHUB_EVENT_PATH=str(self.event_path))
    def command(self,*args):return subprocess.check_output(['git',*args],cwd=self.root,stderr=subprocess.DEVNULL).decode()
    def write_event(self):self.event_path.write_text(json.dumps(self.event))
    def test_exact_parent_owner_new_request_and_current_bytes_admitted(self):self.assertEqual(a.dispatch(self.env)['baseCommit'],self.base)
    def test_other_actor_ref_workflow_retry_or_head_fail(self):
        for key,bad in [('GITHUB_ACTOR','other'),('GITHUB_TRIGGERING_ACTOR','other'),('GITHUB_REF','refs/heads/main'),('GITHUB_WORKFLOW_REF','other'),('GITHUB_RUN_ATTEMPT','2'),('GITHUB_SHA','f'*40),('RUNNER_ENVIRONMENT','self-hosted')]:
            with self.subTest(key=key),self.assertRaises(Exception):a.dispatch(dict(self.env,**{key:bad}))
    def test_created_forced_deleted_push_and_wrong_parent_fail(self):
        for key in ('created','forced','deleted'):
            self.event[key]=True;self.write_event()
            with self.subTest(key=key),self.assertRaisesRegex(Exception,'ANDROID_EVENT'):a.dispatch(self.env)
            self.event[key]=False
        self.event['before']='f'*40;self.write_event()
        with self.assertRaisesRegex(Exception,'ANDROID_EVENT'):a.dispatch(self.env)
    def test_current_inventory_and_request_mutation_fail(self):
        (self.task/'SOURCE-STATE.json').write_text('{"changed":true}')
        with self.assertRaisesRegex(Exception,'ANDROID_REQUEST'):a.dispatch(self.env)

class AndroidPreparedInputTests(unittest.TestCase):
    def setUp(self):
        import test_linux_build_input
        from journey_pouncer_ground_support_probe import GENERIC_TESTS
        self.fixture=test_linux_build_input.LinuxBuildInputTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        state=a.prepared.PROJECT/'JourneyEvidence/JourneyPreparation'
        for name,value in dict(ROOT=a.prepared.ROOT,TASK=a.prepared.TASK,PROJECT=a.prepared.PROJECT,STATE=state,
                               INPUT=state/'android-build-input.json',GATES=a.prepared.TASK/'journey-android-native-gates.json').items():
            changed=patch.object(a,name,value);changed.start();self.addCleanup(changed.stop)
        for folder,names in [('journey-android-playmode',a.source.expected_cases('playmode')),('journey-android-ground',GENERIC_TESTS)]:
            destination=a.TASK/'artifacts'/folder;destination.mkdir(parents=True)
            root=ET.Element('test-run',result='Passed',total=str(len(names)),passed=str(len(names)),failed='0',skipped='0',inconclusive='0')
            for name in names:ET.SubElement(root,'test-case',fullname=name,result='Passed')
            ET.ElementTree(root).write(destination/'result.xml')
        # The renderer gate has separate real PNG/CSV/XML corruption tests. Here
        # exercise request binding with real on-disk records returned by that gate.
        hud=a.TASK/'mobile-hud-native-export';hud.mkdir()
        for name in ('native-report.json','result.xml','capture.png'):(hud/name).write_bytes(('fixture '+name).encode())
        def hud_verified():
            def pin(name):
                path=hud/name;return dict(path=str(path.relative_to(a.ROOT)),sha256=a.sha(path),bytes=path.stat().st_size)
            return dict(report=pin('native-report.json'),nativeXml=pin('result.xml'),captures=[pin('capture.png')],scope=a.mobile_hud.SCOPE)
        changed=patch.object(a.mobile_hud,'verify',side_effect=hud_verified);changed.start();self.addCleanup(changed.stop)
        world=a.TASK/'mobile-hud-world-export';world.mkdir();(world/'world-report.json').write_text('bounded authored world fixture')
        def world_verified():
            path=world/'world-report.json';return [dict(path=str(path.relative_to(a.ROOT)),sha256=a.sha(path),bytes=path.stat().st_size)]
        changed=patch.object(a.mobile_hud,'verify_world',side_effect=world_verified);changed.start();self.addCleanup(changed.stop)
        a.GATES.write_text(json.dumps(a.gate_values()))
    def test_android_input_reuses_actual_complete_union_and_pins_all_native_gates(self):
        a.prepare();value=a.verify();self.assertEqual(value['target'],'Android');self.assertEqual(value['define'],'DESERTRV_CANDIDATE_ANDROID')
        self.assertEqual(a.prepared.verify()['target'],'StandaloneLinux64');self.assertFalse(value['approved'])
        pins={row['path']:row['sha256'] for row in value['files']}
        for path in [a.GATES,a.STATE/'linux-build-input.json',a.TASK/'artifacts/journey-android-playmode/result.xml',a.TASK/'artifacts/journey-android-ground/result.xml',a.TASK/'mobile-hud-native-export/native-report.json',a.TASK/'mobile-hud-native-export/result.xml',a.TASK/'mobile-hud-native-export/capture.png']:
            self.assertEqual(pins[str(path.relative_to(a.ROOT))],a.sha(path))
    def test_gate_xml_cannot_change_between_preparation_and_build(self):
        a.prepare();path=a.TASK/'artifacts/journey-android-playmode/result.xml';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(Exception,'ANDROID_GATES_CHANGED'):a.verify()
    def test_hud_render_evidence_cannot_change_between_preparation_and_build(self):
        a.prepare();path=a.TASK/'mobile-hud-native-export/capture.png';path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaisesRegex(Exception,'ANDROID_GATES_CHANGED'):a.verify()
    def test_prepared_asset_bytes_cannot_change_before_android_build(self):
        a.prepare();path=a.PROJECT/'Assets/Original.cs';path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaises(Exception):a.verify()

class AndroidRestoredDispatchTests(AndroidDispatchTests):
    def setUp(self):
        for key,value in dict(REQUEST='.github/dispatch/desert-rv-journey-android-c15-restored-r2-20261011.json',REQUEST_ID=a.RESTORE_REQUEST_ID).items():
            changed=patch.object(a,key,value);changed.start();self.addCleanup(changed.stop)
        super().setUp()
        changed=patch.object(a,'RESTORED',True);changed.start();self.addCleanup(changed.stop)
        policy=self.root/a.RESTORE_POLICY;policy.write_text('{"schema":1}')
        request=self.root/a.REQUEST;value=json.loads(request.read_text());value['restorationPolicySha256']=a.sha(policy);request.write_text(json.dumps(value))
        self.command('add','.');self.command('commit','--quiet','--amend','--no-edit');self.head=self.command('rev-parse','HEAD').strip()
        self.event['after']=self.head;self.event['head_commit']['id']=self.head;self.write_event()
        self.env.update(GITHUB_SHA=self.head,JOURNEY_ANDROID_RESTORATION=a.RESTORE_REQUEST_ID)
    def test_restored_policy_bytes_and_explicit_route_are_required(self):
        a.dispatch(self.env)
        with self.assertRaisesRegex(Exception,'ANDROID_RESTORATION_ROUTE'):
            a.dispatch(dict(self.env,JOURNEY_ANDROID_RESTORATION='other'))
        (self.root/a.RESTORE_POLICY).write_text('{"changed":true}')
        with self.assertRaisesRegex(Exception,'ANDROID_REQUEST'):a.dispatch(self.env)

class AndroidRestoredReceiptTests(unittest.TestCase):
    def test_current_receipt_requires_exact_separate_restoration_identity(self):
        fixture=linux_fixtures.JourneyLinuxExportTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        native=fixture.receipt();native.update(label=a.LABEL,target='Android',backend='IL2CPP',define='DESERTRV_CANDIDATE_ANDROID',executable=a.APK,temporarySettingsApiFields=a.FIELDS,
            restorationProof=dict(path='tasks/desert-rv/unity/JourneyEvidence/JourneyPreparation/restoration-revalidated.json',sha256='e'*64),
            assetProducerSourceCommit='9c95f1009a597cf4573e286d0098b7bc47a62321',assetProducerRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/38135035401',restorationNativeXmlSha256='f'*64)
        with patch.object(a,'RESTORED',True),patch.object(a,'verify',return_value=copy.deepcopy(native)):
            self.assertEqual(a.native_receipt(native),native)
            for key,bad in [('assetProducerSourceCommit','a'*40),('assetProducerRunUrl',a.linux.producer_url()),('restorationProof',None),('restorationNativeXmlSha256','0'*64)]:
                altered=copy.deepcopy(native);altered[key]=bad
                with self.subTest(key=key),self.assertRaisesRegex(Exception,'ANDROID_RESTORATION_PROOF'):a.native_receipt(altered)
        with patch.object(a,'RESTORED',False),self.assertRaisesRegex(Exception,'ANDROID_FRESH_ONLY'):a.native_receipt(native)

if __name__=='__main__':unittest.main()
