#!/usr/bin/env python3
"""SYNTHETIC validator tests only. Never native .NET/Unity/device evidence."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import g3_ci as ci
import g3_process as process

ROOT=Path(__file__).resolve().parents[3]


def axml(version=3,package='com.buyuqi.lotteryprobe',namespace='http://schemas.android.com/apk/res/android',duplicate=False):
    strings=['manifest','package',package,'versionCode','versionName','0.0.3',namespace]
    payload=b'';offsets=[]
    for text in strings:
        raw=text.encode();offsets.append(len(payload));payload+=bytes([len(text),len(raw)])+raw+b'\0'
    start=28+4*len(strings);pool=struct.pack('<HHIIIIII',1,28,start+len(payload),len(strings),0,0x100,start,0)+b''.join(struct.pack('<I',o) for o in offsets)+payload
    def attr(ns,key,typ,value):return struct.pack('<IIIHBBI',ns,key,0xffffffff,8,0,typ,value)
    attrs=[attr(0xffffffff,1,3,2),attr(6,3,16,version),attr(6,4,3,5)]
    if duplicate:attrs.append(attrs[1])
    chunk=struct.pack('<HHI',0x102,16,36+20*len(attrs))+struct.pack('<II',1,0xffffffff)+struct.pack('<IIHHHHHH',0xffffffff,0,20,20,len(attrs),0,0,0)+b''.join(attrs)
    return struct.pack('<HHI',3,8,8+len(pool)+len(chunk))+pool+chunk


def case(s,p):
    before='a'*64;after='b'*64
    return dict(status='PASS',scenario=s,point=p,recoveryStatus='COMMITTED' if p in ('AfterPublish','BeforeResponse') else 'PROVEN_NOT_COMMITTED',beforeHash=before,expectedHash=after,recoveredHash=after if p in ('AfterPublish','BeforeResponse') else before,finalHash=after,finalCashMinor=process.CASH[s],finalCommands=process.COMMANDS[s],attemptCommandOccurrences=1,staleRevisionReplayUnchanged=True,observation=process.expected_observation(s))

class G3ValidatorTests(unittest.TestCase):
    def testBaselineExactContractPreserved(self):
        p=ci.baseline_contract(ROOT/ci.TASK);self.assertEqual(sum(map(len,p['edit'].values())),45);self.assertEqual(sum(map(len,p['play'].values())),8)
    def testDraftContractCannotTrigger(self):
        with tempfile.TemporaryDirectory() as d:
            task=Path(d);(task/'ci').mkdir();(task/'ci/g3-test-contract.json').write_text(json.dumps(dict(schemaVersion=1,status='DRAFT_NOT_FROZEN',rulesSha256=ci.RULES_SHA,profiles={},frames=[])))
            with self.assertRaises(ValueError):ci.load_contract(task)
    def testRequestIdentityMatchesReview(self):self.assertEqual(json.loads((ROOT/ci.TASK/'ci/g3-request.review.json').read_text()),ci.REQUEST)
    def testScopedLegacyConfigurationRestores(self):
        values=tuple(getattr(ci.legacy,n) for n in ('BASE','SCOPE','REQUEST_PATH','mutation_kind'))
        with ci.configured():
            self.assertEqual(ci.legacy.BASE,ci.BASE);self.assertEqual(ci.legacy.REQUEST_PATH,ci.REQUEST_PATH)
            self.assertEqual(ci.legacy.mutation_kind(ci.SCENE),'G3_GENERATED_SCENE')
            self.assertEqual(ci.legacy.mutation_kind('Assets/G3/unknown.cs'),'UNEXPECTED_SOURCE_CHANGE')
        self.assertEqual(tuple(getattr(ci.legacy,n) for n in ('BASE','SCOPE','REQUEST_PATH','mutation_kind')),values)
    def testCompiledAxmIdentity(self):self.assertEqual(ci.parse_binary_manifest(axml()),dict(package='com.buyuqi.lotteryprobe',versionCode=3,versionName='0.0.3'))
    def testCompiledVersionIsReadRatherThanDeclared(self):self.assertEqual(ci.parse_binary_manifest(axml(version=2))['versionCode'],2)
    def testTruncatedAxmRejected(self):
        raw=axml()
        for n in (0,7,30,len(raw)-1):
            with self.assertRaises(ValueError):ci.parse_binary_manifest(raw[:n])
    def testWrongVersionNamespaceRejected(self):
        with self.assertRaises(ValueError):ci.parse_binary_manifest(axml(namespace='not-android'))
    def testDuplicateVersionRejected(self):
        with self.assertRaises(ValueError):ci.parse_binary_manifest(axml(duplicate=True))
    def testMalformedStringPoolRejected(self):
        raw=bytearray(axml());struct.pack_into('<I',raw,16,99999)
        with self.assertRaises(ValueError):ci.parse_binary_manifest(raw)
    def testEverySixBySixBoundaryValidated(self):
        rows=[dict(case(s,p),exitSignal='SIGKILL',childExitCode=-9) for s,p in process.CASES]
        self.assertEqual(len(process.validate_suite(rows)),36)
    def testMissingOrReorderedCaseRejected(self):
        rows=[dict(case(s,p),exitSignal='SIGKILL',childExitCode=-9) for s,p in process.CASES]
        for data in (rows[:-1],list(reversed(rows))):
            with self.assertRaises(ValueError):process.validate_suite(data)
    def testFakeKillExitRejected(self):
        rows=[dict(case(s,p),exitSignal='SIGKILL',childExitCode=-9) for s,p in process.CASES];rows[0]['childExitCode']=0
        with self.assertRaises(ValueError):process.validate_suite(rows)
    def testIndependentMoneyAndLoanAndPhaseRejected(self):
        for s,p in process.CASES:
            row=case(s,p);row['observation']['cashMinor']+=1
            with self.assertRaises(ValueError):process.validate_case(row,s,p)
        row=case('repay','AfterPublish');row['observation']['motherBorrowedMinor']=5000
        with self.assertRaises(ValueError):process.validate_case(row,'repay','AfterPublish')
        row=case('night','AfterPublish');row['observation']['phase']='DAY_OPEN'
        with self.assertRaises(ValueError):process.validate_case(row,'night','AfterPublish')
    def testWrongRecoveryStateOrDuplicateReplayRejected(self):
        row=case('challenge','BeforeWrite');row['recoveredHash']=row['expectedHash']
        with self.assertRaises(ValueError):process.validate_case(row,'challenge','BeforeWrite')
        row=case('consumable','AfterPublish');row['attemptCommandOccurrences']=2
        with self.assertRaises(ValueError):process.validate_case(row,'consumable','AfterPublish')
    def testReviewManifestExcludesOnlyRequestAndReview(self):
        files=ci.reviewed_files(ROOT);self.assertNotIn(ci.REQUEST_PATH,files);self.assertNotIn(ci.TASK+'/ci/g3-preflight.review.json',files)
        self.assertIn(ci.TASK+'/scripts/process-g3/Program.cs',files);self.assertIn('.github/workflows/lottery-g3.yml',files)
        self.assertEqual(files[ci.TASK+'/fonts/NotoSansCJKsc-Regular.otf.xz'],ci.legacy.FONT_COMPRESSED_SHA)
    def testProcessCompileInputsMatchReceipt(self):
        import glob
        import xml.etree.ElementTree as ET
        project=ROOT/ci.TASK/'scripts/process-g3/G3.ProcessProbe.csproj'
        xml=ET.parse(project).getroot();paths=set()
        for node in xml.findall('.//Compile'):
            paths.update(Path(p).resolve() for p in glob.glob(str(project.parent/node.get('Include')),recursive=True))
        actual={p.resolve() for p in process.source_paths(ROOT/ci.TASK) if p.suffix=='.cs'}
        self.assertEqual(paths,actual)
        self.assertEqual(xml.find('.//EnableDefaultCompileItems').text,'false')
        self.assertIn('LOTTERY_G3_TEST_FIXTURE',xml.find('.//DefineConstants').text)
        self.assertNotIn(ROOT/ci.TASK/'unity/Assets/G2/Core/RunState.cs',paths)
    def testFreshReviewMustApproveExactSourceMap(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);target=root/ci.TASK/'ci/g3-preflight.review.json';target.parent.mkdir(parents=True)
            review=dict(schemaVersion=1,status='APPROVED_FOR_TRIGGER',requestId=ci.REQUEST['requestId'],reviewedSourceCommit='a'*40,reviewerId='fresh-reviewer-001',sourceFiles={'source.cs':'b'*64},deviceQa='NOT_RUN',finalQuality='NOT_PASSED')
            target.write_text(json.dumps(review))
            with patch.object(ci,'reviewed_files',return_value=review['sourceFiles']),patch.object(ci.subprocess,'run'):
                self.assertEqual(ci.verify_preflight(root)['status'],'APPROVED_FOR_TRIGGER')
                for key,value in [('status','DRAFT_NOT_APPROVED'),('deviceQa','PASS'),('finalQuality','PASS'),('sourceFiles',{'source.cs':'c'*64})]:
                    changed=copy.deepcopy(review);changed[key]=value;target.write_text(json.dumps(changed))
                    with self.assertRaises(ValueError):ci.verify_preflight(root)
    def testMixedTriggerCommitRefused(self):
        with patch.object(ci.legacy,'guard',return_value={}),patch.object(ci.legacy,'git',return_value=ci.REQUEST_PATH+'\nother.cs'),patch.object(ci,'verify_preflight'):
            with self.assertRaises(ValueError):ci.guard(ROOT)
    def testUnknownGeneratedProbeAssetRejected(self):
        with ci.configured():
            self.assertEqual(ci.legacy.mutation_kind('Assets/GeneratedProbe/extra.asset'),'UNEXPECTED_SOURCE_CHANGE')
            self.assertEqual(ci.legacy.mutation_kind('Assets/GeneratedProbe/Probe.unity'),'GENERATED_PROBE_ASSET')
    def testWorkflowMaintainsLockedActionsAndNoCache(self):
        text=(ROOT/'.github/workflows/lottery-g3.yml').read_text()
        self.assertIn('group: unity-personal-proof',text);self.assertIn('androidVersionCode: 3',text);self.assertNotIn('actions/cache',text);self.assertNotIn('workflow_dispatch',text)
        actions=set(__import__('re').findall(r'uses: ([^\s]+)',text))
        self.assertEqual(actions,{'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683','actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02','game-ci/unity-test-runner@0ff419b913a3630032cbe0de48a0099b5a9f0ed9','game-ci/unity-builder@d829bfc901f2347c8fe18898f06712b66916ef42'})
        self.assertLess(text.index('name: Native regression-edit'),text.index('name: Native regression-play'));self.assertLess(text.index('name: Native regression-play'),text.index('name: Native edit'))

if __name__=='__main__':unittest.main()
