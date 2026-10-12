#!/usr/bin/env python3
"""SYNTHETIC validator tests only. Never native .NET/Unity/device evidence."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import os
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
    if (s,p)==process.WAITING_CASE:
        return dict(status='PASS',scenario=s,point=p,recoveryStatus='COMMITTED',beforeHash=before,expectedHash=after,recoveredHash=before,finalHash=after,finalCashMinor=28500,finalCommands=10,attemptCommandOccurrences=1,staleRevisionReplayUnchanged=True,waitingPollUnchanged=True,reservedStockRejected=True,reservedCashRejected=True,duplicateRewardUnchanged=True,waitingObservation=process.waiting_observation(False),observation=process.waiting_observation(True))
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
    def testEverySixBySixAndWaitingBoundaryValidated(self):
        rows=[dict(case(s,p),exitSignal='SIGKILL',childExitCode=-9) for s,p in process.CASES]
        self.assertEqual(len(process.validate_suite(rows)),37)
    def testMissingOrReorderedCaseRejected(self):
        rows=[dict(case(s,p),exitSignal='SIGKILL',childExitCode=-9) for s,p in process.CASES]
        for data in (rows[:-1],list(reversed(rows))):
            with self.assertRaises(ValueError):process.validate_suite(data)
    def testFakeKillExitRejected(self):
        rows=[dict(case(s,p),exitSignal='SIGKILL',childExitCode=-9) for s,p in process.CASES];rows[0]['childExitCode']=0
        with self.assertRaises(ValueError):process.validate_suite(rows)
    def testIndependentMoneyAndLoanAndPhaseRejected(self):
        for s,p in process.COMMIT_CASES:
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
    def testWaitingKillRequiresOriginalResourcesAndLateReward(self):
        original=case(*process.WAITING_CASE)
        process.validate_waiting(original)
        for group,key,value in [('waitingObservation','rewardRecorded',True),('waitingObservation','stockQuantity',0),('waitingObservation','cashMinor',28500),('observation','stockId','another-stock'),('observation','quality','rare'),('observation','drawerQuality','rare'),('waitingObservation','drawerReserved',False),('observation','adSuccesses',2),('observation','ledgerCount',2),('observation','drawerPriceMinor',3000)]:
            row=copy.deepcopy(original);row[group][key]=value
            with self.assertRaises(ValueError):process.validate_waiting(row)
        for key in ('waitingPollUnchanged','reservedStockRejected','reservedCashRejected','duplicateRewardUnchanged'):
            row=copy.deepcopy(original);row[key]=False
            with self.assertRaises(ValueError):process.validate_waiting(row)
    def testWaitingKillCannotBeReplacedByCommitOrFakeExit(self):
        rows=[dict(case(s,p),exitSignal='SIGKILL',childExitCode=-9) for s,p in process.CASES]
        for replacement in (dict(rows[-1],childExitCode=0),dict(rows[0]),dict(rows[-1],recoveredHash='2'*64)):
            data=rows[:-1]+[replacement]
            with self.assertRaises(ValueError):process.validate_suite(data)
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
    def makeReviewedGit(self,root):
        def git(*args):return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.DEVNULL,text=True).strip()
        git('init','-q');source=root/ci.TASK/'scripts/source.cs';source.parent.mkdir(parents=True);source.write_text('reviewed source\n')
        def commit(message):
            git('add','-A');git('-c','user.name=Synthetic Fixture','-c','user.email=fixture@example.invalid','commit','-q','-m',message)
        commit('reviewed source');reviewed=git('rev-parse','HEAD')
        review=dict(schemaVersion=1,status='APPROVED_FOR_TRIGGER',requestId=ci.REQUEST['requestId'],reviewedSourceCommit=reviewed,reviewerId='synthetic-fresh-001',sourceFiles=ci.reviewed_files(root,committed=True),deviceQa='NOT_RUN',finalQuality='NOT_PASSED')
        target=root/ci.REVIEW_PATH;target.parent.mkdir(parents=True);target.write_text(json.dumps(review));commit('review metadata')
        def trigger():
            (root/ci.REQUEST_PATH).write_text(json.dumps(ci.REQUEST));commit('unique request')
        return git,commit,trigger,review,source
    def testFreshReviewAcceptsRealGitMetadataThenRequestOnly(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
            self.assertEqual(ci.verify_preflight(root)['reviewedSourceCommit'],review['reviewedSourceCommit'])
            ci.check_working_inputs(root,review['sourceFiles'],allow_generated_unity=False)
    def testFreshReviewRejectsAutomaticInputsAndArbitraryTreeDriftInRealGit(self):
        names=[ci.TASK+'/Directory.Build.targets',ci.TASK+'/Directory.Build.props',ci.TASK+'/NuGet.Config',ci.TASK+'/scripts/Directory.Build.targets',ci.TASK+'/global.json',ci.TASK+'/arbitrary-input.bin','Directory.Build.targets','tasks/NuGet.Config','outside-unrelated-source.py']
        for name in names:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root)
                injected=root/name;injected.parent.mkdir(parents=True,exist_ok=True);injected.write_text('SYNTHETIC_UNREVIEWED_INPUT');commit('unreviewed input');trigger()
                with self.assertRaises(ValueError):ci.verify_preflight(root)
    def testFreshReviewRejectsWorkingBytesModesLinksAndIgnoredNewInput(self):
        for attack in ('bytes','mode','symlink','untracked','ignored'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as d:
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
                if attack=='bytes':source.write_text('unreviewed working bytes')
                elif attack=='mode':source.chmod(0o755)
                elif attack=='symlink':source.unlink();source.symlink_to('/dev/null')
                else:
                    extra=root/ci.TASK/'Directory.Build.props';extra.write_text('SYNTHETIC_UNREVIEWED_IMPORT')
                    if attack=='ignored':(root/'.git/info/exclude').write_text('Directory.Build.props\n')
                with self.assertRaises(ValueError):ci.verify_preflight(root)
    def testFreshReviewRequiresCommittedMetadataAndRequestBytes(self):
        for name in ci.REVIEW_EXCEPTIONS:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
                path=root/name;path.write_text(path.read_text()+'\n')
                with self.assertRaises(ValueError):ci.verify_preflight(root)
    def testFreshReviewRejectsCommittedModeLinkAndDeletionDrift(self):
        for attack in ('mode','symlink','deletion'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as d:
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root)
                if attack=='mode':source.chmod(0o755)
                else:
                    source.unlink()
                    if attack=='symlink':source.symlink_to('/dev/null')
                commit('unreviewed tree type drift');trigger()
                with self.assertRaises(ValueError):ci.verify_preflight(root)
    def testInitialPreflightDoesNotExemptDirtyUnitySettings(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root)
            settings=root/ci.TASK/'unity/ProjectSettings/ProjectSettings.asset';settings.parent.mkdir(parents=True);settings.write_text('reviewed settings')
            commit('reviewed settings addition');review['reviewedSourceCommit']=git('rev-parse','HEAD');review['sourceFiles']=ci.reviewed_files(root,committed=True)
            (root/ci.REVIEW_PATH).write_text(json.dumps(review));commit('updated review metadata');trigger();ci.verify_preflight(root)
            settings.write_text('unreviewed pre-build settings')
            with self.assertRaises(ValueError):ci.verify_preflight(root)
            with self.assertRaises(ValueError):ci.check_working_inputs(root,review['sourceFiles'],allow_restored_font=True)
    def testOnlyExactRestoredFontAllowedBeforeFirstSnapshot(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
            font=root/ci.TASK/'unity/Assets/Resources/ProbeChinese.otf';font.parent.mkdir(parents=True);font.write_bytes(b'synthetic font')
            with self.assertRaises(ValueError):ci.check_working_inputs(root,review['sourceFiles'])
            with patch.object(ci.legacy,'FONT_SHA',hashlib.sha256(b'synthetic font').hexdigest()):ci.check_working_inputs(root,review['sourceFiles'],allow_restored_font=True)
            font.write_bytes(b'wrong font')
            with self.assertRaises(ValueError):ci.check_working_inputs(root,review['sourceFiles'],allow_restored_font=True)
    def testOutputRootSymlinksAreRejectedBeforeOutputPruning(self):
        for name in sorted(ci.OUTPUT_ROOTS):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as target:
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
                output=root/name;output.parent.mkdir(parents=True,exist_ok=True);output.symlink_to(target,target_is_directory=True)
                with self.assertRaises(ValueError):ci.verify_preflight(root)
                with self.assertRaises(ValueError):ci.check_working_inputs(root,review['sourceFiles'],allow_generated_unity=True)
    def testOutputLinksAreRejectedBeforeLegacyGuardCanWrite(self):
        for attack in ('evidence-root','guard-receipt','nested-stage-directory','artifact-file'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside:
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
                sentinel=Path(outside)/'guard-receipt.json';sentinel.write_text('DO_NOT_WRITE')
                if attack=='evidence-root':
                    (root/ci.TASK/'evidence').symlink_to(outside,target_is_directory=True)
                else:
                    relative={'guard-receipt':'evidence/guard-receipt.json','nested-stage-directory':'evidence/g3/edit','artifact-file':'artifacts/g3-process/compile.log'}[attack]
                    destination=root/ci.TASK/relative;destination.parent.mkdir(parents=True)
                    destination.symlink_to(outside if attack=='nested-stage-directory' else sentinel,target_is_directory=attack=='nested-stage-directory')
                with patch.object(ci.legacy,'guard') as guarded_write:
                    with self.assertRaises(ValueError):ci.guard(root)
                    guarded_write.assert_not_called()
                self.assertEqual(sentinel.read_text(),'DO_NOT_WRITE')
    def testFailedProcessGuardCannotDeleteOrWriteThroughLinkedEvidence(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside:
            root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
            destination=Path(outside)/'g3/process';destination.mkdir(parents=True)
            receipt=destination/'process-receipt.json';diagnostic=destination/'process-diagnostic.json'
            receipt.write_text('PRESERVE_RECEIPT');diagnostic.write_text('PRESERVE_DIAGNOSTIC')
            (root/ci.TASK/'evidence').symlink_to(outside,target_is_directory=True)
            with patch.object(process,'failure') as diagnostic_write:
                with self.assertRaises(ValueError):process.run_new(root)
                diagnostic_write.assert_not_called()
            self.assertEqual(receipt.read_text(),'PRESERVE_RECEIPT');self.assertEqual(diagnostic.read_text(),'PRESERVE_DIAGNOSTIC')
    def testEveryMutatingCiCommandRejectsOutputLinkBeforeAnyGuardWrite(self):
        for command in ('guard','restore-font','snapshot','audit','tests','captures','apk','diagnostics'):
            with self.subTest(command=command),tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside:
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
                sentinel=Path(outside)/'guard-receipt.json';sentinel.write_text('UNCHANGED')
                (root/ci.TASK/'evidence').symlink_to(outside,target_is_directory=True)
                with patch('sys.argv',['g3_ci.py',command,'--root',str(root)]),patch.object(ci.legacy,'guard') as writer:
                    with self.assertRaises(ValueError):ci.main()
                    writer.assert_not_called()
                self.assertEqual(sentinel.read_text(),'UNCHANGED')
                self.assertEqual([p.name for p in Path(outside).iterdir()],['guard-receipt.json'])
    def testRegressionDelegationCannotCleanBeforeG3GuardClosure(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside:
            root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
            (root/ci.TASK/'evidence').symlink_to(outside,target_is_directory=True)
            with patch.object(process.regression,'main') as legacy_runner:
                with self.assertRaises(ValueError):process.run_regression(root)
                legacy_runner.assert_not_called()
    def testAllOutputSubtreesRejectHardlinkedFilesBeforeGuardWrite(self):
        for name in sorted(ci.OUTPUT_ROOTS):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside:
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
                sentinel=Path(outside)/'sentinel';sentinel.write_text('NO_ALIAS_WRITE')
                output=root/name/'nested/file.json';output.parent.mkdir(parents=True);os.link(sentinel,output)
                with patch.object(ci.legacy,'guard') as writer:
                    with self.assertRaisesRegex(ValueError,'multiply-linked'):ci.guard(root,allow_generated_unity=True)
                    writer.assert_not_called()
                self.assertEqual(sentinel.read_text(),'NO_ALIAS_WRITE');self.assertEqual(sentinel.stat().st_nlink,2)
    def testHardlinkedReceiptsCannotBeOverwrittenDeletedOrDiagnosed(self):
        for relative in ('evidence/guard-receipt.json','evidence/g3/process/process-receipt.json','evidence/g3/process/process-diagnostic.json'):
            with self.subTest(relative=relative),tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside:
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
                sentinel=Path(outside)/'sentinel';sentinel.write_text('PRESERVE_INODE')
                output=root/ci.TASK/relative;output.parent.mkdir(parents=True,exist_ok=True);os.link(sentinel,output)
                with patch.object(ci.legacy,'guard') as writer,patch.object(process,'failure') as diagnostic:
                    with self.assertRaises(ValueError):process.run_new(root)
                    writer.assert_not_called();diagnostic.assert_not_called()
                self.assertTrue(output.exists());self.assertEqual(sentinel.read_text(),'PRESERVE_INODE');self.assertEqual(output.read_text(),'PRESERVE_INODE')
    def testSourceAndControlHardlinksRejectedWithoutChangingBytes(self):
        for location in ('source','review','request'):
            with self.subTest(location=location),tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside:
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
                path=source if location=='source' else root/(ci.REVIEW_PATH if location=='review' else ci.REQUEST_PATH)
                original=path.read_bytes();sentinel=Path(outside)/'sentinel';sentinel.write_bytes(original);path.unlink();os.link(sentinel,path)
                with self.assertRaises(ValueError):ci.verify_preflight(root)
                self.assertEqual(path.read_bytes(),original);self.assertEqual(sentinel.read_bytes(),original)
    def testOutputFifosAndSpecialFileTypesRefusedWithoutOpening(self):
        for name in sorted(ci.OUTPUT_ROOTS):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
                fifo=root/name/'nested/not-a-file';fifo.parent.mkdir(parents=True);os.mkfifo(fifo)
                with patch.object(ci.legacy,'guard') as writer:
                    with self.assertRaisesRegex(ValueError,'Non-regular'):ci.guard(root,allow_generated_unity=True)
                    writer.assert_not_called()
    def testRestoredFontAndGeneratedUnityFilesRejectHardlinks(self):
        for child in ('Assets/Resources/ProbeChinese.otf','ProjectSettings/Other.asset'):
            with self.subTest(child=child),tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside:
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
                sentinel=Path(outside)/'sentinel';sentinel.write_bytes(b'SYNTHETIC_SAFE_BYTES')
                path=root/ci.TASK/'unity'/child;path.parent.mkdir(parents=True);os.link(sentinel,path)
                with self.assertRaisesRegex(ValueError,'multiply-linked'):ci.check_working_inputs(root,review['sourceFiles'],allow_generated_unity=True)
    def testNonregularReviewControlRejectedBeforeJsonRead(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
            control=root/ci.REVIEW_PATH;control.unlink();os.mkfifo(control)
            with patch.object(ci,'bounded_read') as reader:
                with self.assertRaisesRegex(ValueError,'Non-regular'):ci.verify_preflight(root)
                reader.assert_not_called()
    def testInitialUnityCacheRejectedButRegularLaterOutputTypesAllowed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger()
            for name in sorted(ci.OUTPUT_ROOTS):
                path=root/name/'nested/file.txt';path.parent.mkdir(parents=True);path.write_text('regular generated output')
            with self.assertRaisesRegex(ValueError,'Initial Unity runtime'):ci.verify_preflight(root)
            ci.verify_preflight(root,allow_generated_unity=True)
    def testFreshReviewRejectsOmittedTaskRootInputFromSourceMap(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root)
            # The full repository anchor catches review-time additions too unless
            # the exact new commit is reviewed and all executed bytes are bound.
            source.write_text('changed reviewed input');commit('changed source');review['reviewedSourceCommit']=git('rev-parse','HEAD')
            (root/ci.REVIEW_PATH).write_text(json.dumps(review));commit('stale source map');trigger()
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
        prepare=(ROOT/ci.TASK/'scripts/g3_prepare_runner.sh').read_text()
        self.assertIn('set -euo pipefail',prepare);self.assertLess(prepare.index('g3_ci.py guard'),prepare.index('sudo rm -rf'))
        self.assertLess(text.index('name: Native regression-edit'),text.index('name: Native regression-play'));self.assertLess(text.index('name: Native regression-play'),text.index('name: Native edit'))

if __name__=='__main__':unittest.main()
