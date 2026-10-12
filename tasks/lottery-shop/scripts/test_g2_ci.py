"""SYNTHETIC fixtures. These checks never claim Unity, rendered-frame or Core PASS."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import zlib
import g2_ci as ci
import run_g2_process_probe as process


def synthetic_xml(assemblies):
    n=sum(map(len,assemblies.values()))
    root=ET.Element('test-run',result='Passed',total=str(n),passed=str(n),failed='0',skipped='0',inconclusive='0')
    for name,names in assemblies.items():
        suite=ET.SubElement(root,'test-suite',type='Assembly',name=name,result='Passed')
        for case in names: ET.SubElement(suite,'test-case',fullname=case,result='Passed')
    return root


def png(seed=0,flat=False):
    def chunk(kind,data): return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    row=bytes([10,20,30])*1280 if flat else bytes(v for x in range(1280) for v in ((x+seed)%256,(x//7+seed)%256,70))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1280,720,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+row)*720))+chunk(b'IEND',b'')


class G2SyntheticTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)
        self.assemblies={'Lottery.Probe.Tests.dll':sorted(ci.G0_CASES),'Lottery.G2.EditMode.Tests.dll':['Lottery.G2.EditMode.Tests.Fixture.One','Lottery.G2.EditMode.Tests.Fixture.Two']}
    def write_xml(self,root):
        ET.ElementTree(root).write(self.path/'results.xml',encoding='utf-8');return self.path
    def test_synthetic_exact_two_assembly_report(self):
        _,_,result=ci.inspect_tests(self.write_xml(synthetic_xml(self.assemblies)),self.assemblies)
        self.assertEqual(result['passed'],8)
    def test_case_cannot_move_between_expected_assemblies(self):
        root=synthetic_xml(self.assemblies);a,b=list(root);case=list(b)[0];b.remove(case);a.append(case)
        with self.assertRaises(ValueError):ci.inspect_tests(self.write_xml(root),self.assemblies)
    def test_orphan_cannot_hide_beside_empty_assembly(self):
        root=synthetic_xml(self.assemblies);b=list(root)[1]
        for case in list(b):b.remove(case);root.append(case)
        with self.assertRaises(ValueError):ci.inspect_tests(self.write_xml(root),self.assemblies)
    def test_missing_extra_duplicate_failed_skipped_are_rejected(self):
        for mode in ('missing','extra','duplicate','failed','skipped'):
            with self.subTest(mode=mode):
                root=synthetic_xml(self.assemblies);suite=list(root)[1]
                if mode=='missing':suite.remove(list(suite)[0])
                elif mode=='extra':ET.SubElement(suite,'test-case',fullname='Lottery.Other',result='Passed')
                elif mode=='duplicate':suite.append(copy.deepcopy(list(suite)[0]))
                else:list(suite)[0].set('result',mode.title())
                with self.assertRaises(ValueError):ci.inspect_tests(self.write_xml(root),self.assemblies)
    def test_encoded_sensitive_xml_not_accepted(self):
        root=synthetic_xml(self.assemblies);ET.SubElement(root,'output').text='SYNTHETIC password example'
        with self.assertRaises(ValueError):ci.inspect_tests(self.write_xml(root),self.assemblies)
    def test_g0_contract_must_remain_exact_six(self):
        contract={'schemaVersion':1,'status':'FROZEN_FOR_CI','rulesSha256':ci.RULES_SHA,'profiles':{'edit':self.assemblies,'play':{'Lottery.G2.PlayMode.Tests.dll':['Lottery.G2.PlayMode.Tests.Fixture.One']}}}
        path=self.path/'contract.json';ci.write_json(path,contract);ci.load_contract(path)
        contract['profiles']['edit']['Lottery.Probe.Tests.dll'].pop();ci.write_json(path,contract)
        with self.assertRaises(ValueError):ci.load_contract(path)
    def test_unfrozen_empty_or_duplicate_contract_rejected(self):
        contract={'schemaVersion':1,'status':'AWAITING_TEST_IDENTITIES','rulesSha256':ci.RULES_SHA,'profiles':{}}
        path=self.path/'contract.json';ci.write_json(path,contract)
        with self.assertRaises(ValueError):ci.load_contract(path)
    def test_only_exact_generated_g2_scene_paths_allowed(self):
        for name in ci.GENERATED:self.assertEqual(ci.legacy.mutation_kind(name),'G2_GENERATED_SCENE')
        for name in ('Assets/G2/Scenes/Other.unity','Assets/G2/Scenes/G2Slice.cs','Assets/G2/Rendering/Unknown.asset'):
            self.assertEqual(ci.legacy.mutation_kind(name),'UNEXPECTED_SOURCE_CHANGE')
    def test_pinned_lock_drift_emits_fail_and_withholds_generated_exports(self):
        task=self.path/ci.TASK;common=task/'evidence';common.mkdir(parents=True)
        lock=task/'unity/Packages/packages-lock.json';lock.parent.mkdir(parents=True);lock.write_text('{}')
        def fake_audit(root,identity,additional_generated_kinds):
            ci.write_json(common/'source-mutations.json',dict(identity,status='PASS',changes=[]))
            (common/'generated-assets.zip').write_bytes(b'SYNTHETIC')
        with mock.patch.object(ci.legacy,'audit',fake_audit),self.assertRaises(ValueError):ci.audit_stage(self.path,'edit',{'sourceCommit':'a'*40})
        receipt=json.loads((common/'g2/edit/source-mutations.json').read_text())
        self.assertEqual(receipt['status'],'FAIL');self.assertFalse((common/'g2/edit/generated-assets.zip').exists())
    def test_unexpected_audit_error_still_writes_small_fail_receipt(self):
        task=self.path/ci.TASK;(task/'evidence').mkdir(parents=True)
        with mock.patch.object(ci.legacy,'audit',side_effect=RuntimeError('SYNTHETIC internal failure')),self.assertRaises(RuntimeError):
            ci.audit_stage(self.path,'play',{'sourceCommit':'b'*40})
        text=(task/'evidence/g2/play/source-mutations.json').read_text();self.assertIn('FAIL',text);self.assertNotIn('internal failure',text)
    def test_synthetic_varied_png_is_decodable_not_render_evidence(self):self.assertEqual(ci.png_dimensions(png()),(1280,720))
    def test_flat_truncated_crc_and_metadata_png_rejected(self):
        values=[png(flat=True),png()[:-1],png()[:50]+bytes([png()[50]^1])+png()[51:],b'\x89PNG\r\n\x1a\n']
        for value in values:
            with self.assertRaises(ValueError):ci.png_dimensions(value)
    def test_synthetic_four_frame_receipt_binding(self):
        identity={'sourceCommit':'a'*40,'runId':'123'};receipt={'schemaVersion':1,'scope':'G2_CAMERA_RENDER_NOT_DEVICE_TESTED',**identity,'unityVersion':ci.legacy.VERSION,'rulesSha256':ci.RULES_SHA,
            'captureMethod':'URP_STANDARD_REQUEST_READPIXELS','graphicsDeviceType':'OpenGLCore','graphicsDeviceName':'SYNTHETIC fixture','width':1280,'height':720,'sourceViewportWidth':1280,'sourceViewportHeight':720,
            'inputEvidence':'SIMULATED_INPUT_SYSTEM','deviceQa':'NOT_RUN','visualReview':'PENDING','frames':[]}
        for i,stage in enumerate(ci.FRAMES):
            raw=png(i);name=stage+'.png';(self.path/name).write_bytes(raw)
            receipt['frames'].append({'stage':stage,'file':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'stateSha256':str(i)*64})
        ci.write_json(self.path/'render-receipt.json',receipt);self.assertEqual(len(ci.inspect_captures(self.path,identity)['frames']),4)
        for key,value in [('graphicsDeviceType','Null'),('sourceCommit','b'*40),('deviceQa','PASS'),('sourceViewportWidth',True)]:
            bad=copy.deepcopy(receipt);bad[key]=value;ci.write_json(self.path/'render-receipt.json',bad)
            with self.assertRaises(ValueError):ci.inspect_captures(self.path,identity)
        bad=copy.deepcopy(receipt);bad['frames'][0]['file']='../initial.png';ci.write_json(self.path/'render-receipt.json',bad)
        with self.assertRaises(ValueError):ci.inspect_captures(self.path,identity)
    def test_process_receipt_recovery_boundary_not_just_pass_label(self):
        d={'status':'PASS','scenario':'buy','point':'AfterPublish','recoveryStatus':'COMMITTED','beforeHash':'a'*64,'expectedHash':'b'*64,'recoveredHash':'b'*64,'finalHash':'b'*64,
           'finalCashMinor':29000,'finalCommands':1,'attemptCommandOccurrences':1,'staleRevisionReplayUnchanged':True}
        process.validate_case(d,'buy','AfterPublish')
        for key,value in [('recoveredHash','a'*64),('attemptCommandOccurrences',2),('staleRevisionReplayUnchanged',False),('recoveryStatus','PROVEN_NOT_COMMITTED')]:
            bad=dict(d);bad[key]=value
            with self.assertRaises(ValueError):process.validate_case(bad,'buy','AfterPublish')
    @unittest.skipUnless(sys.platform=='linux','SIGKILL fixture requires Linux')
    def test_supervisor_actually_kills_owned_python_fixture_not_core_or_unity(self):
        marker=self.path/'ready'
        child=subprocess.Popen([sys.executable,'-c','import pathlib,sys,time;pathlib.Path(sys.argv[1]).write_text("BeforePublish");time.sleep(60)',str(marker)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        process.kill_at_marker(child,marker,'BeforePublish',timeout=5);self.assertEqual(child.returncode,-9)
    def test_supervisor_rejects_child_exit_without_marker(self):
        child=subprocess.Popen([sys.executable,'-c','pass'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        with self.assertRaises(ValueError):process.kill_at_marker(child,self.path/'absent','BeforeWrite',timeout=5)


if __name__=='__main__':unittest.main()
