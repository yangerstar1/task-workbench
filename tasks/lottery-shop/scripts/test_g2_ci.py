"""SYNTHETIC fixtures. These checks never claim Unity, rendered-frame or Core PASS."""
import copy
import hashlib
import json
import os
import re
import shutil
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
        (self.path/ci.TASK/'unity/ProjectSettings').mkdir(parents=True)
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
    def sparse_patterns(self):
        root=Path(ci.__file__).resolve().parents[3]
        workflow=(root/'.github/workflows/lottery-g2.yml').read_text()
        blocks=re.findall(r'^          sparse-checkout: \|\n((?:            /[^\n]+\n)+)',workflow,re.M)
        self.assertEqual(len(blocks),2,'Both native jobs must declare explicit sparse inputs')
        expected=['/tasks/lottery-shop/','/.github/workflows/lottery-g2.yml','/.github/workflows/lottery-g0.yml']
        patterns=[line.strip() for line in blocks[0].splitlines()]
        self.assertEqual(patterns,expected)
        self.assertEqual([line.strip() for line in blocks[1].splitlines()],patterns)
        return root,patterns
    def materialize_sparse_fixture(self,root,patterns):
        target=self.path/'sparse';target.mkdir()
        for pattern in patterns:
            source=root/pattern.strip('/');destination=target/pattern.strip('/')
            destination.parent.mkdir(parents=True,exist_ok=True)
            if pattern.endswith('/'):
                shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__'))
            else:shutil.copyfile(source,destination)
        return target
    def run_sparse_g0_suite(self,target,case=None):
        command=[sys.executable,'-m','unittest']
        command += [case] if case else ['discover','-s','tasks/lottery-shop/scripts','-p','test_probe_ci.py']
        environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(target/'tasks/lottery-shop/scripts'))
        return subprocess.run(command,cwd=target,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    def test_exact_declared_sparse_inputs_run_preserved_g0_regressions(self):
        root,patterns=self.sparse_patterns();target=self.materialize_sparse_fixture(root,patterns)
        result=self.run_sparse_g0_suite(target)
        self.assertEqual(result.returncode,0,'Preserved G0 suite failed in exact declared G2 sparse checkout')
        self.assertIn(b'Ran 63 tests',result.stderr)
    def test_sparse_fixture_detects_missing_preserved_workflow(self):
        root,patterns=self.sparse_patterns();patterns.remove('/.github/workflows/lottery-g0.yml')
        target=self.materialize_sparse_fixture(root,patterns)
        result=self.run_sparse_g0_suite(target,'test_probe_ci.SourceMutationSyntheticTests.test_refused_before_baseline_cannot_remain_in_public_artifact_path')
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'FileNotFoundError',result.stderr)
    def test_settings_preflight_accepts_only_empty_credential_scalars(self):
        path=self.path/ci.TASK/'unity/ProjectSettings/ProjectSettings.asset'
        for scalar in ('', '\'\'', '""', 'null', '~'):
            path.write_text('PlayerSettings:\n  ps4Passcode: '+scalar+'\n  metroCertificatePassword: \n')
            ci.source_preflight(self.path)
    def test_settings_preflight_refuses_nonempty_and_block_values_without_echo(self):
        path=self.path/ci.TASK/'unity/ProjectSettings/ProjectSettings.asset'
        for key in ('ps4Passcode','ps4NPTitleSecret','metroCertificatePassword','apiKey','private_key','token'):
            path.write_text('PlayerSettings:\n  '+key+': SYNTHETIC_NOT_A_CREDENTIAL\n')
            findings=ci.settings_findings(self.path)
            self.assertEqual(findings,[{'path':'ProjectSettings/ProjectSettings.asset','kind':'NONEMPTY_CREDENTIAL_SETTING','sha256':ci.digest(path)}])
            with self.assertRaises(ValueError):ci.source_preflight(self.path)
        path.write_text('PlayerSettings:\n  ps4Passcode: |\n    SYNTHETIC_NOT_A_CREDENTIAL\n')
        with self.assertRaises(ValueError):ci.source_preflight(self.path)
    def test_settings_preflight_refuses_symlink(self):
        path=self.path/ci.TASK/'unity/ProjectSettings/ProjectSettings.asset'
        path.symlink_to(self.path/'outside')
        with self.assertRaises(ValueError):ci.source_preflight(self.path)
    def test_regenerated_credential_blocks_archive_and_emits_hash_only_fail(self):
        task=self.path/ci.TASK;common=task/'evidence';common.mkdir(parents=True)
        path=task/'unity/ProjectSettings/ProjectSettings.asset'
        path.write_text('PlayerSettings:\n  ps4Passcode: SYNTHETIC_NOT_A_CREDENTIAL\n')
        stale=common/'g2/edit/generated-assets.zip';stale.parent.mkdir(parents=True);stale.write_bytes(b'SYNTHETIC')
        with mock.patch.object(ci.legacy,'audit') as audit,self.assertRaises(ValueError):ci.audit_stage(self.path,'edit',{'sourceCommit':'a'*40})
        audit.assert_not_called();self.assertFalse(stale.exists())
        raw=(common/'g2/edit/source-mutations.json').read_text();receipt=json.loads(raw)
        self.assertEqual(receipt['status'],'FAIL');self.assertEqual(receipt['failedStage'],'SETTINGS_CREDENTIAL_PREFLIGHT')
        self.assertEqual(set(receipt['changes'][0]),{'path','kind','sha256'})
        self.assertNotIn('SYNTHETIC_NOT_A_CREDENTIAL',raw);self.assertNotIn('ps4Passcode',raw)
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
    def test_process_project_selects_csharp_pipeline_and_exact_ignore_exception(self):
        task=Path(ci.__file__).resolve().parents[1];project=task/'scripts/process-probe/G2.ProcessProbe.csproj'
        self.assertTrue(project.is_file());self.assertFalse(project.with_suffix('.proj').exists())
        document=ET.fromstring(project.read_text());self.assertEqual(document.get('Sdk'),'Microsoft.NET.Sdk')
        self.assertEqual(document.findtext('PropertyGroup/TargetFramework'),'net8.0')
        self.assertIn('!scripts/process-probe/G2.ProcessProbe.csproj',(task/'.gitignore').read_text().splitlines())
        worker=(project.parent/'Program.cs').read_text()
        self.assertTrue(set(re.findall(r'check = "([A-Z_]+)"',worker)) <= process.ASSERTIONS)
    def test_compiler_diagnostics_export_only_allowlisted_coordinates(self):
        task=self.path/ci.TASK;source=task/'scripts/process-probe/Program.cs'
        raw=(str(source)+'(12,3): error CS0029: SYNTHETIC_SECRET_VALUE [/unapproved/token]\n'+
             '/unapproved/SYNTHETIC_SECRET_VALUE.cs(9,2): error CS0103: hidden\n'+
             '/sdk/tool.targets(21,7): error NETSDK1005: hidden\n').encode()
        values=process.compiler_errors(raw,task)
        self.assertEqual(values[0],{'code':'CS0029','file':'scripts/process-probe/Program.cs','line':12,'column':3})
        self.assertEqual(values[1]['file'],'UNMAPPED');self.assertEqual(values[2]['code'],'NETSDK1005')
        self.assertNotIn('SYNTHETIC_SECRET_VALUE',json.dumps(values));self.assertNotIn('/sdk',json.dumps(values))
    def test_worker_diagnostics_accept_only_fixed_assertion_and_exception_identities(self):
        raw=b'SYNTHETIC_SECRET_VALUE\nG2_PROBE_ERROR WALLET_STOCK InvalidOperationException\n'
        self.assertEqual(process.worker_error(raw),{'assertId':'WALLET_STOCK','exceptionType':'InvalidOperationException'})
        for raw in (b'G2_PROBE_ERROR SECRET_VALUE InvalidOperationException',b'G2_PROBE_ERROR WALLET_STOCK SecretValue',b'G2_PROBE_ERROR WALLET_STOCK InvalidOperationException extra'):
            self.assertIsNone(process.worker_error(raw))
    def test_process_diagnostic_bounds_and_refuses_oversize_logs(self):
        task=self.path/ci.TASK;work=task/'artifacts/g2-process';work.mkdir(parents=True)
        (work/'compile.log').write_bytes(b'SYNTHETIC'*(300000))
        process.write_failure(task,{'sourceCommit':'a'*40},{'stage':'build'},ValueError('SYNTHETIC_SECRET_VALUE'))
        raw=(task/'evidence/g2/process/process-diagnostic.json').read_text()
        self.assertEqual(json.loads(raw)['diagnosticRead'],'REFUSED_OR_UNAVAILABLE');self.assertNotIn('SYNTHETIC_SECRET_VALUE',raw)
    def test_process_build_failure_exports_bounded_receipt_and_removes_stale_pass(self):
        task=self.path/ci.TASK;out=task/'evidence/g2/process';out.mkdir(parents=True);(out/'process-receipt.json').write_text('SYNTHETIC_STALE_PASS')
        def fail_build(command,**kwargs):
            if command[1]=='restore':return subprocess.CompletedProcess(command,0)
            kwargs['stdout'].write(b'Program.cs(42,8): error CS0103: SYNTHETIC_SECRET_VALUE\n');kwargs['stdout'].flush()
            raise subprocess.CalledProcessError(1,command)
        with mock.patch.object(process.ci.legacy,'guard',return_value={'sourceCommit':'a'*40}),mock.patch.object(process.ci,'verify_inputs'),mock.patch.object(process.subprocess,'check_output',return_value='8.0.425 [/SYNTHETIC]\n'),mock.patch.object(process.subprocess,'run',side_effect=fail_build):
            with self.assertRaises(subprocess.CalledProcessError):process.main(self.path)
        self.assertFalse((out/'process-receipt.json').exists());raw=(out/'process-diagnostic.json').read_text();receipt=json.loads(raw)
        self.assertEqual(receipt['stage'],'build');self.assertEqual(receipt['exceptionType'],'CalledProcessError')
        self.assertEqual(receipt['compilerErrors'][0]['code'],'CS0103');self.assertEqual(receipt['dotnetSdk'],'8.0.425')
        self.assertNotIn('SYNTHETIC_SECRET_VALUE',raw);self.assertLess(len(raw),8192)
    def test_process_missing_sdk_has_diagnostic_without_external_download(self):
        task=self.path/ci.TASK
        with mock.patch.object(process.ci.legacy,'guard',return_value={'sourceCommit':'b'*40}),mock.patch.object(process.ci,'verify_inputs'),mock.patch.object(process.subprocess,'check_output',side_effect=FileNotFoundError('SYNTHETIC_SECRET_VALUE')):
            with self.assertRaises(FileNotFoundError):process.main(self.path)
        raw=(task/'evidence/g2/process/process-diagnostic.json').read_text();data=json.loads(raw)
        self.assertEqual(data['stage'],'sdk_inventory');self.assertEqual(data['exceptionType'],'FileNotFoundError');self.assertNotIn('SYNTHETIC_SECRET_VALUE',raw)
    def test_edit_checkpoint_precedes_play_and_uses_subset_of_final_safe_paths(self):
        root=Path(ci.__file__).resolve().parents[3];workflow=(root/'.github/workflows/lottery-g2.yml').read_text()
        start=workflow.index('      - name: Preserve successful EditMode and process evidence before PlayMode')
        end=workflow.index('      - name: Record PlayMode baseline after successful EditMode gate')
        block=workflow[start:end]
        self.assertLess(workflow.index('        id: editaudit'),start)
        self.assertLess(end,workflow.index('        id: play'))
        self.assertIn("success() && steps.editverify.outputs.edit_passed == 'true' && steps.editaudit.outcome == 'success'",block)
        self.assertIn('actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02',block)
        checkpoint=[line.strip() for line in block.splitlines() if line.startswith('            tasks/')]
        final=workflow[workflow.index('      - name: Export only bounded non-APK evidence'):workflow.index('  android:')]
        finalpaths=[line.strip() for line in final.splitlines() if line.startswith('            tasks/')]
        self.assertEqual(len(checkpoint),14);self.assertTrue(set(checkpoint) <= set(finalpaths))
        self.assertTrue(all('/edit/' in path or path.endswith('/process/process-receipt.json') for path in checkpoint))
        self.assertIn('if-no-files-found: error',block)
    def test_workflow_exports_only_bounded_process_receipts_on_failure(self):
        root=Path(ci.__file__).resolve().parents[3];workflow=(root/'.github/workflows/lottery-g2.yml').read_text()
        final=workflow[workflow.index('      - name: Export only bounded non-APK evidence'):workflow.index('  android:')]
        paths=[line.strip() for line in final.splitlines() if line.startswith('            tasks/') and 'process/' in line]
        self.assertEqual(paths,['tasks/lottery-shop/evidence/g2/process/process-receipt.json','tasks/lottery-shop/evidence/g2/process/process-diagnostic.json'])
        self.assertNotIn('compile.log',workflow);self.assertNotIn('worker.log',workflow)
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
