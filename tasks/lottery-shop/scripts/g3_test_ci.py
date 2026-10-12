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
import time
import zlib
import shutil
import sys
sys.dont_write_bytecode = True  # Project imports must never write checkout inputs.
import unittest
from unittest.mock import patch
import g3_ci as ci
import g3_process as process

ROOT=Path(__file__).resolve().parents[3]


def diagnostic_shell(root):
    text=(root/'.github/workflows/lottery-g3.yml').read_text()
    start=text.index('        run: |\n',text.index('      - name: Collect independent metadata-only path diagnosis'))+len('        run: |\n')
    end=text.index('      - name: Preserve diagnostic-only filesystem metadata',start)
    return ''.join(line[10:]+'\n' for line in text[start:end].splitlines())


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

def synthetic_import_diagnostic():
    """Synthetic serializer fixtures, never observations from a native import."""
    rows=[]
    for id,sha in ci.ARTWORK.items():
        o={k:True for k in ci.IMPORT_BOOL_FIELDS};o.update({k:0 for k in ci.IMPORT_INT_FIELDS})
        o.update(artworkId=id,sourceSha256=sha,layoutSha256=sha,assetGuid='a'*32,sourceWidth=1536,sourceHeight=1024,layoutWidth=1536,layoutHeight=1024,textureWidth=1536,textureHeight=1024,textureFormat=3,wrapU=1,wrapV=1,wrapW=1,maxTextureSize=2048)
        o['defaultPlatform']=dict(overridden=False,crunchedCompression=False,allowsAlphaSplitting=False,maxTextureSize=2048,format=-1,textureCompression=0)
        o['androidPlatform']=dict(o['defaultPlatform'],overridden=True,format=3)
        # Independent fixed identities; do not compute test expected outcomes through the validator.
        o['checks']=[dict(id=k,passed=True) for k in ('BINDING_ID','SOURCE_BYTES','SOURCE_LAYOUT','TEXTURE_BINDING','TEXTURE_DIMENSIONS','TEXTURE_UNCOMPRESSED','IMPORTER_SHAPE','IMPORTER_DEFAULT','DEFAULT_PLATFORM','ANDROID_PLATFORM','COMMITTED_VERIFICATION')]
        rows.append(o)
    return dict(schemaVersion=1,sourceCommit='a'*40,runId='123',runAttempt='1',unityVersion='6000.3.19f1',stage='ANDROID_IMPORT_PREFLIGHT',artworks=rows)


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
    def assertIsolatedAuthoringManifest(self):
        # Authoring input has no generated output. Never scan the live CI root:
        # the earlier real guard legitimately wrote evidence there already.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            inputs={ci.TASK+'/scripts/process-g3/Program.cs':b'SYNTHETIC_SOURCE',
                    '.github/workflows/lottery-g3.yml':b'SYNTHETIC_WORKFLOW',
                    ci.TASK+'/Directory.Build.props':b'SYNTHETIC_REVIEWED_INPUT',
                    ci.TASK+'/fonts/OFL.txt':b'SYNTHETIC_LICENSE_MARKER_NOT_LICENSE_PROOF',
                    ci.TASK+'/ci/g2-request.review.json':b'{"syntheticOldRequest":true}\n',
                    ci.REVIEW_PATH:b'{}',ci.REQUEST_PATH:b'{}'}
            for name,raw in inputs.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            files=ci.reviewed_files(root)
            expected={name:hashlib.sha256(raw).hexdigest() for name,raw in inputs.items() if name not in ci.REVIEW_EXCEPTIONS}
            expected[ci.TASK+'/fonts/NotoSansCJKsc-Regular.otf.xz']=ci.legacy.FONT_COMPRESSED_SHA
            expected[ci.TASK+'/ci/g2-request.json']=hashlib.sha256(inputs[ci.TASK+'/ci/g2-request.review.json']).hexdigest()
            self.assertEqual(files,expected)
            generated=root/ci.TASK/'evidence/guard-receipt.json';generated.parent.mkdir();generated.write_text('{}')
            with self.assertRaisesRegex(ValueError,'Generated output in authoring source'):ci.reviewed_files(root)
    def testReviewManifestExcludesOnlyRequestAndReview(self):
        self.assertIsolatedAuthoringManifest()
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
    def testManifestHelperAfterActualGuardOutputUsesIsolatedAuthoringFixture(self):
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as metadata:
            root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger();head=git('rev-parse','HEAD')
            event=dict(after=head,ref='refs/heads/'+ci.legacy.BRANCH,deleted=False,
                       repository=dict(full_name=ci.legacy.REPOSITORY,private=False,fork=False,owner=dict(login=ci.legacy.OWNER)),sender=dict(login=ci.legacy.OWNER))
            event_path=Path(metadata)/'synthetic-event.json';event_path.write_text(json.dumps(event))
            env=dict(GITHUB_ACTIONS='true',GITHUB_EVENT_NAME='push',GITHUB_REPOSITORY=ci.legacy.REPOSITORY,GITHUB_REPOSITORY_OWNER=ci.legacy.OWNER,
                     GITHUB_ACTOR=ci.legacy.OWNER,GITHUB_TRIGGERING_ACTOR=ci.legacy.OWNER,GITHUB_REF='refs/heads/'+ci.legacy.BRANCH,
                     RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',GITHUB_SHA=head,GITHUB_RUN_ID='12345',GITHUB_RUN_ATTEMPT='1',GITHUB_EVENT_PATH=str(event_path))
            # Synthetic runner metadata only; execute the real guard and actual
            # Git ancestry check against this disposable repository's base.
            with ci.configured(),patch.dict(os.environ,env),patch.object(ci.legacy,'BASE',review['reviewedSourceCommit']):identity=ci.guard(root)
            receipt=root/ci.TASK/'evidence/guard-receipt.json';self.assertTrue(receipt.is_file())
            self.assertEqual(json.loads(receipt.read_text())['sourceCommit'],head);self.assertEqual(identity['requestId'],ci.REQUEST['requestId'])
            ci.verify_preflight(root)  # Valid runtime output still satisfies strict source closure.
            with self.assertRaisesRegex(ValueError,'Generated output in authoring source'):ci.reviewed_files(root)
            # The formerly failing helper must not inspect this runtime tree.
            with patch.dict(globals(),ROOT=root):self.assertIsolatedAuthoringManifest()
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
    def testSafeCliFailureCodesNeverPrintExceptionData(self):
        for error in (ValueError('SECRET /private/raw/path'),subprocess.CalledProcessError(97,['SECRET_COMMAND']),FileNotFoundError('/private/SECRET')):
            line=ci.failure_line('PROCESS','REGRESSION_GUARD',error)
            self.assertNotIn('SECRET',line);self.assertNotIn('/private',line);self.assertNotIn('Traceback',line)
            self.assertRegex(line,r'^G3_PROCESS_ERROR stage=REGRESSION_GUARD code=[A-Z_]+ exception=[A-Za-z]+ exit=-?[0-9]+$')
        self.assertIn('code=UNREVIEWED_WORKING_INPUT',ci.failure_line('PROCESS','REGRESSION_GUARD',ValueError('Unexpected materialized checkout input')))
    def testIndependentCliSequenceReachesOnlySyntheticSdkBoundary(self):
        # Independent Python interpreters, matching workflow order. No dotnet,
        # Unity, network, native process proof or secret access occurs here.
        with tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as external:
            root=Path(d);metadata=Path(external);task=root/ci.TASK
            def git(*args):return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.DEVNULL,text=True).strip()
            def commit(message):
                git('add','-A','-f');git('-c','user.name=Synthetic CLI Fixture','-c','user.email=fixture@example.invalid','commit','-q','-m',message)
            git('init','-q');git('-c','user.name=Synthetic CLI Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-q','-m','synthetic ancestry anchor');anchor=git('rev-parse','HEAD')
            names=ci.reviewed_files(ROOT,committed=(ROOT/'.git').exists())
            for name in names:
                source=ROOT/name
                if not source.is_file():
                    self.assertIn(name,(ci.TASK+'/fonts/NotoSansCJKsc-Regular.otf.xz',ci.TASK+'/ci/g2-request.json'));continue
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            # Only metadata pins differ in this local fixture: its actual empty
            # ancestor must replace the production repository's unavailable SHA.
            target=task/'scripts/g3_ci.py';text=target.read_text();original="BASE = '"+ci.BASE+"'";self.assertIn(original,text);target.write_text(text.replace(original,"BASE = '"+anchor+"'",1))
            request=dict(ci.REQUEST,baseCommit=anchor);(task/'ci/g3-request.review.json').write_text(json.dumps(request))
            commit('copied source with disclosed synthetic ancestry pin');reviewed=git('rev-parse','HEAD')
            review=dict(schemaVersion=1,status='APPROVED_FOR_TRIGGER',requestId=request['requestId'],reviewedSourceCommit=reviewed,reviewerId='synthetic-independent-cli',sourceFiles=ci.reviewed_files(root,committed=True),deviceQa='NOT_RUN',finalQuality='NOT_PASSED')
            (root/ci.REVIEW_PATH).write_text(json.dumps(review));commit('synthetic review metadata');(root/ci.REQUEST_PATH).write_text(json.dumps(request));commit('synthetic unique request');head=git('rev-parse','HEAD')
            event=dict(after=head,ref='refs/heads/'+ci.legacy.BRANCH,deleted=False,repository=dict(full_name=ci.legacy.REPOSITORY,private=False,fork=False,owner=dict(login=ci.legacy.OWNER)),sender=dict(login=ci.legacy.OWNER))
            event_path=metadata/'event.json';event_path.write_text(json.dumps(event))
            env=dict(os.environ,GITHUB_ACTIONS='true',GITHUB_EVENT_NAME='push',GITHUB_REPOSITORY=ci.legacy.REPOSITORY,GITHUB_REPOSITORY_OWNER=ci.legacy.OWNER,GITHUB_ACTOR=ci.legacy.OWNER,GITHUB_TRIGGERING_ACTOR=ci.legacy.OWNER,GITHUB_REF='refs/heads/'+ci.legacy.BRANCH,RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',GITHUB_SHA=head,GITHUB_RUN_ID='12345',GITHUB_RUN_ATTEMPT='1',GITHUB_EVENT_PATH=str(event_path))
            env.pop('PYTHONDONTWRITEBYTECODE',None);env.pop('PYTHONPYCACHEPREFIX',None)
            def cli(script,*args,environment=None,cwd=None):
                return subprocess.run([sys.executable,str(task/'scripts'/script),*args],cwd=cwd or root,env=environment or env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=90)
            result=cli('g3_ci.py','guard');self.assertEqual(result.returncode,0,'Independent guard CLI failed')
            receipt=task/'evidence/guard-receipt.json';self.assertTrue(receipt.is_file());receipt_before=ci.digest(receipt)
            # Match both helper commands. Exclude only this outer orchestrator
            # from its inner helper process, preventing recursive fixture launch.
            helpers_env=dict(env,PYTHONDONTWRITEBYTECODE='1')
            result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(task/'scripts'),'-p','test_*.py'],cwd=root,env=helpers_env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=90)
            self.assertEqual(result.returncode,0,'Independent baseline helper CLI failed')
            cases=['G3ValidatorTests.'+name for name in unittest.defaultTestLoader.getTestCaseNames(type(self)) if name!=self._testMethodName]
            result=cli('g3_test_ci.py',*cases,environment=helpers_env);self.assertEqual(result.returncode,0,'Independent G3 helper CLI failed')
            result=cli('g3_test_path_diagnostics.py',environment=helpers_env);self.assertEqual(result.returncode,0,'Independent metadata helper CLI failed')
            self.assertEqual(ci.digest(receipt),receipt_before)
            self.assertFalse(list((task/'scripts').rglob('*.pyc')))
            binary_dir=metadata/'bin';binary_dir.mkdir();marker=metadata/'synthetic-sdk-boundary';stub=binary_dir/'dotnet'
            stub.write_text('#!/bin/sh\n[ "$#" = 1 ] && [ "$1" = "--list-sdks" ] || exit 98\nprintf SDK_INVENTORY_ONLY > "'+str(marker)+'"\nexit 97\n');stub.chmod(0o755)
            env['PATH']=str(binary_dir)+os.pathsep+env.get('PATH','')
            result=cli('g3_process.py','regression')
            self.assertEqual(result.returncode,1);self.assertTrue(marker.is_file(),'Regression CLI never reached the safe SDK stub')
            self.assertEqual(marker.read_text(),'SDK_INVENTORY_ONLY')
            self.assertIn('stage=REGRESSION_DELEGATE code=SUBPROCESS_FAILED exception=CalledProcessError exit=97',result.stderr)
            self.assertNotIn(str(root),result.stderr);self.assertNotIn('Traceback',result.stderr)
            diagnostic=json.loads((task/'evidence/g2/process/process-diagnostic.json').read_text())
            self.assertEqual(diagnostic['stage'],'sdk_inventory');self.assertEqual(diagnostic['status'],'FAIL');self.assertEqual(diagnostic['exitCode'],97)
            self.assertFalse((task/'evidence/g2/process/process-receipt.json').exists())
            self.assertFalse(list((task/'scripts').rglob('*.pyc')))
            # New-suite CLI must independently pass its guard, then fail closed
            # because no real G2 native receipt exists. Do not synthesize a PASS.
            result=cli('g3_process.py','new',cwd=metadata)
            self.assertEqual(result.returncode,1);self.assertIn('stage=NEW_BASELINE code=EVIDENCE_FILE_MISSING',result.stderr)
            diagnostic=json.loads((task/'evidence/g3/process/process-diagnostic.json').read_text());self.assertEqual(diagnostic['stage'],'baseline');self.assertEqual(diagnostic['status'],'FAIL')
            self.assertFalse((task/'evidence/g3/process/process-receipt.json').exists());self.assertFalse(list((task/'scripts').rglob('*.pyc')))
            result=cli('g3_ci.py','guard',cwd=metadata);self.assertEqual(result.returncode,0,'Root resolution or output closure changed after independent CLIs')
            # Actual independent post-Android CLI, with disclosed synthetic cold
            # metadata and real local hardlinks. No Unity/native APK is created.
            self.makeSyntheticColdProof(root,git,review);env['GITHUB_JOB']='android'
            cache=root/ci.CACHE_ROOT/'Bee/Android/private-cache-name';cache.parent.mkdir(parents=True);cache.write_bytes(b'SYNTHETIC_CACHE_ONLY');os.link(cache,cache.with_name('internal-alias'))
            result=cli('g3_ci.py','diagnostics','--stage','android',cwd=metadata)
            self.assertEqual(result.returncode,0,'Post-Android CLI rejected complete proved-scope cache group')
            self.assertFalse((task/'evidence/g3/android/apk-receipt.json').exists())
            os.link(cache,metadata/'outside-alias');unchanged={p.relative_to(task).as_posix():ci.digest(p) for p in (task/'evidence').rglob('*') if p.is_file()}
            for command in ('apk','audit','diagnostics'):
                result=cli('g3_ci.py',command,'--stage','android',cwd=metadata)
                self.assertEqual(result.returncode,1);self.assertIn('stage=CI_'+command.upper()+' code=UNSAFE_FILE_TYPE_OR_ALIAS',result.stderr)
                self.assertIn('pathClass=LIBRARY_BEE_ANDROID',result.stderr);self.assertIn('kind=regular nlink=3 internalLinks=2',result.stderr)
                for hidden in ('private-cache-name','outside-alias',str(root),str(metadata),'SYNTHETIC_CACHE_ONLY'):self.assertNotIn(hidden,result.stderr)
            self.assertEqual((metadata/'outside-alias').read_bytes(),b'SYNTHETIC_CACHE_ONLY')
            self.assertEqual({p.relative_to(task).as_posix():ci.digest(p) for p in (task/'evidence').rglob('*') if p.is_file()},unchanged)
            # Match the independent diagnostic workflow: execute committed source
            # through isolated Python stdin, despite an intentionally dirty local
            # module and a real OTHER_CHECKOUT alias. No content from either alias
            # may be opened or exported by this metadata collector.
            sentinel=metadata/'sensitive-outside';sentinel.write_bytes(b'NEVER_EXPORT_SENTINEL')
            other=root/'unexpected-private-name';os.link(sentinel,other)
            runner=metadata/'runner-temp';runner.mkdir(mode=0o700);channel=runner/'github-output';channel.touch()
            env.update(GITHUB_WORKSPACE=str(root),RUNNER_TEMP=str(runner),GITHUB_OUTPUT=str(channel))
            committed=git('show','HEAD:'+ci.TASK+'/scripts/g3_path_diagnostics.py')
            (task/'scripts/g3_path_diagnostics.py').write_text('raise RuntimeError("DIRTY_MODULE_MUST_NOT_EXECUTE")\n')
            result=subprocess.run(['bash','-c',diagnostic_shell(ROOT)],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=50)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('status=DIAGNOSTIC_ONLY',result.stdout)
            entry=channel.read_text().strip();self.assertRegex(entry,r'^diagnostic_relative_path=lottery-g3-pathdiag-[0-9a-f]{24}/diagnostic.json$')
            path=runner/entry.split('=',1)[1];raw=path.read_text();report=json.loads(raw)
            self.assertEqual(report['status'],'DIAGNOSTIC_ONLY');self.assertEqual(report['acceptance'],'NONE')
            self.assertTrue(report['scan']['complete']);self.assertTrue(report['scan']['stable'])
            self.assertTrue(all(v=='MATCH' for v in report['identity']['validation'].values()))
            group=next(g for g in report['scan']['hardlinkGroups'] if any(m['relativePathSha256']==hashlib.sha256(b'unexpected-private-name').hexdigest() for m in g['members']))
            self.assertEqual(group['observedCheckoutMembers'],1);self.assertEqual(group['observedNlinkValues'],[2]);self.assertFalse(group['membershipEqualsNlink'])
            for hidden in ('unexpected-private-name','sensitive-outside','NEVER_EXPORT_SENTINEL','DIRTY_MODULE_MUST_NOT_EXECUTE',str(root),str(metadata)):
                self.assertNotIn(hidden,raw+result.stdout+result.stderr)
            self.assertEqual(sentinel.read_bytes(),b'NEVER_EXPORT_SENTINEL')
            self.assertEqual({p.relative_to(task).as_posix():ci.digest(p) for p in (task/'evidence').rglob('*') if p.is_file()},unchanged)
            self.assertFalse(list(root.rglob('*.pyc')))
            # Restore only this disclosed fixture mutation to prove collector
            # success never clears the original production guard rejection.
            (task/'scripts/g3_path_diagnostics.py').write_text(committed+'\n')
            result=cli('g3_ci.py','apk','--stage','android');self.assertEqual(result.returncode,1)
            self.assertFalse((task/'evidence/g3/android/apk-receipt.json').exists())

    def testArtworkImportDiagnosticAcceptsExactBoundedNativeSchema(self):
        data=synthetic_import_diagnostic();self.assertEqual(ci.validate_artwork_diagnostic(data,data),data)
    def testArtworkImportDiagnosticRejectsOtherSourceRunAttemptOrVersion(self):
        identity=synthetic_import_diagnostic()
        for key,value in [('sourceCommit','b'*40),('runId','124'),('runAttempt','2'),('unityVersion','6000.3.20f1')]:
            data=copy.deepcopy(identity);data[key]=value
            with self.assertRaises(ValueError):ci.validate_artwork_diagnostic(data,identity)
    def testArtworkImportDiagnosticRefusesUnboundedTextExtraFieldsAndWrongTypes(self):
        base=synthetic_import_diagnostic()
        for attack in ('field','text','bool','number','platform','checks'):
            data=copy.deepcopy(base);o=data['artworks'][0]
            if attack=='field':o['rawPath']='not-exportable'
            elif attack=='text':o['assetGuid']='not-a-guid'
            elif attack=='bool':o['sourcePng']=1
            elif attack=='number':o['sourceWidth']=True
            elif attack=='platform':o['androidPlatform']['secret']='not-exportable'
            else:o['checks'][0]['passed']=1
            with self.assertRaises(ValueError):ci.validate_artwork_diagnostic(data,base)
    def testArtworkImportDiagnosticRecomputesChecksAndKeepsRealFailureValues(self):
        base=synthetic_import_diagnostic();data=copy.deepcopy(base)
        data['artworks'][0]['textureCompression']=1
        with self.assertRaises(ValueError):ci.validate_artwork_diagnostic(data,base)
        data['artworks'][0]['checks'][7]['passed']=False
        self.assertEqual(ci.validate_artwork_diagnostic(data,base)['artworks'][0]['textureCompression'],1)
        for value in (False,1024,4,1):
            row=copy.deepcopy(base);key=('overridden' if type(value) is bool else {1024:'maxTextureSize',4:'format',1:'textureCompression'}[value]);row['artworks'][0]['androidPlatform'][key]=value
            with self.assertRaises(ValueError):ci.validate_artwork_diagnostic(row,base)
    def testArtworkImportExportRequiresActualFileAndNeverPromotesFailure(self):
        with tempfile.TemporaryDirectory() as d:
            task=Path(d);data=synthetic_import_diagnostic();source=task/'artifacts/g3-android-import-diagnostic.json';source.parent.mkdir()
            self.assertIsNone(ci.export_artwork_diagnostic(task,data))
            with self.assertRaises(ValueError):ci.export_artwork_diagnostic(task,data,required=True)
            source.write_text(json.dumps(data));ci.export_artwork_diagnostic(task,data,required=True)
            target=task/'evidence/g3/android/artwork-import-diagnostic.json';self.assertEqual(json.loads(target.read_text())['status'],'IMPORT_FIELDS_PASS')
            data['artworks'][0]['textureWidth']=1024;data['artworks'][0]['checks'][4]['passed']=False;source.write_text(json.dumps(data))
            ci.export_artwork_diagnostic(task,data);self.assertEqual(json.loads(target.read_text())['status'],'IMPORT_FIELDS_FAIL')
            with self.assertRaises(ValueError):ci.export_artwork_diagnostic(task,data,required=True)
    def testCommittedArtworkPlatformSettingsAreCompleteAndOriginalBytesUnchanged(self):
        root=ROOT/ci.TASK/'unity/Assets/G3/Rendering/Resources/G3'
        for id,sha in ci.ARTWORK.items():
            self.assertEqual(hashlib.sha256((root/(id+'-ticket-albedo.png')).read_bytes()).hexdigest(),sha)
            meta=(root/(id+'-ticket-albedo.png.meta')).read_text();self.assertEqual(meta.count('  platformSettings:\n'),1)
            self.assertIn('  serializedVersion: 13\n',meta);self.assertIn('  nPOTScale: 0\n',meta)
            entries=meta.split('  platformSettings:\n')[1].split('  userData:')[0].split('  - ')[1:];settings=[]
            for entry in entries:
                values={}
                for line in entry.strip().splitlines():
                    key,value=line.strip().split(': ',1);self.assertNotIn(key,values);values[key]=value if key=='buildTarget' else int(value)
                settings.append(values)
            self.assertEqual([p['buildTarget'] for p in settings],['DefaultTexturePlatform','Android'])
            for i,p in enumerate(settings):
                self.assertEqual(p,dict(serializedVersion=4,buildTarget=['DefaultTexturePlatform','Android'][i],maxTextureSize=2048,resizeAlgorithm=0,textureFormat=[-1,3][i],textureCompression=0,compressionQuality=50,crunchedCompression=0,allowsAlphaSplitting=0,overridden=i,ignorePlatformSupport=0,androidETC2FallbackOverride=0,forceMaximumCompressionQuality_BC6H_BC7=0))

    def makeSyntheticColdProof(self,root,git,review):
        # Actual temporary Git/paths/inodes; source/run/cold records are disclosed
        # synthetic fixture metadata, not observations of an executed Unity build.
        prefix=ci.TASK+'/unity/'
        before={n[len(prefix):]:sha for n,sha in review['sourceFiles'].items() if n.startswith(prefix) and n[len(prefix):].split('/',1)[0] in ('Assets','Packages','ProjectSettings')}
        before['Assets/Resources/ProbeChinese.otf']=ci.legacy.FONT_SHA
        snapshot=root/ci.TASK/'evidence/pre-unity-source.json';snapshot.parent.mkdir(parents=True,exist_ok=True);snapshot.write_text(json.dumps(before))
        proof=root/ci.TASK/'evidence/g3/android/cold-build-baseline.json';proof.parent.mkdir(parents=True,exist_ok=True)
        cold=dict(sourceCommit=git('rev-parse','HEAD'),runId='12345',runAttempt='1',requestId=ci.REQUEST['requestId'],job='android',cachePolicy='LIBRARY_INTERNAL_HARDLINKS_V1',status='VERIFIED_BEFORE_UNITY',libraryAbsent=True,buildAbsent=True,cacheRestored=False,preUnitySourceSha256=hashlib.sha256(snapshot.read_bytes()).hexdigest())
        proof.write_text(json.dumps(cold));return proof,snapshot,cold
    def testColdLibraryCompleteInternalHardlinkGroupPassesOnlyAndroidPostScope(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,GITHUB_JOB='android',GITHUB_RUN_ID='12345',GITHUB_RUN_ATTEMPT='1'):
            root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger();self.makeSyntheticColdProof(root,git,review)
            first=root/ci.CACHE_ROOT/'Bee/Android/one.bin';second=root/ci.CACHE_ROOT/'Artifacts/two.bin';first.parent.mkdir(parents=True);second.parent.mkdir(parents=True);first.write_bytes(b'SYNTHETIC_CACHE_BYTES');os.link(first,second)
            self.assertEqual(first.stat().st_nlink,2);ci.verify_preflight(root,allow_generated_unity=True,android_cache=True)
            with self.assertRaises(ci.UnsafePathError):ci.verify_preflight(root,allow_generated_unity=True)
            with self.assertRaises(ValueError):ci.verify_preflight(root,android_cache=True)
            self.assertEqual(first.read_bytes(),b'SYNTHETIC_CACHE_BYTES');self.assertEqual(second.read_bytes(),first.read_bytes())
    def testColdCacheProofRequiresExactRunAttemptSourceJobSnapshotAndAbsentObservation(self):
        for attack in ('missing','run','attempt','source','job','status','library','build','restore','snapshot_hash','snapshot_map','proof_alias','snapshot_alias'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside,patch.dict(os.environ,GITHUB_JOB='android',GITHUB_RUN_ID='12345',GITHUB_RUN_ATTEMPT='1'):
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger();proof,snapshot,cold=self.makeSyntheticColdProof(root,git,review)
                cache=root/ci.CACHE_ROOT/'a';cache.parent.mkdir(parents=True);cache.write_bytes(b'cache');os.link(cache,cache.with_name('b'))
                if attack=='missing':proof.unlink()
                elif attack=='job':os.environ['GITHUB_JOB']='tests'
                elif attack=='snapshot_hash':snapshot.write_text('{}')
                elif attack=='snapshot_map':snapshot.write_text('{}');cold['preUnitySourceSha256']=hashlib.sha256(snapshot.read_bytes()).hexdigest();proof.write_text(json.dumps(cold))
                elif attack.endswith('_alias'):os.link(proof if attack=='proof_alias' else snapshot,Path(outside)/'alias')
                else:
                    key,value={'run':('runId','12346'),'attempt':('runAttempt','2'),'source':('sourceCommit','b'*40),'status':('status','unknown'),'library':('libraryAbsent',False),'build':('buildAbsent',False),'restore':('cacheRestored',True)}[attack];cold[key]=value;proof.write_text(json.dumps(cold))
                with patch.object(ci.legacy,'guard') as writer:
                    with self.assertRaises((ValueError,FileNotFoundError)):ci.guard(root,allow_generated_unity=True,android_cache=True)
                    writer.assert_not_called()
    def testColdCacheExternalAndCrossBoundaryHardlinksRefusedWithoutWrites(self):
        for destination in ('external','evidence','build','temp','source','three_links'):
            with self.subTest(destination=destination),tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside,patch.dict(os.environ,GITHUB_JOB='android',GITHUB_RUN_ID='12345',GITHUB_RUN_ATTEMPT='1'):
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger();self.makeSyntheticColdProof(root,git,review)
                first=root/ci.CACHE_ROOT/'Bee/Android/cache.bin';first.parent.mkdir(parents=True)
                if destination=='source':os.link(source,first);sentinel=source
                else:
                    sentinel=Path(outside)/'untouched' if destination in ('external','three_links') else root/ci.TASK/{'evidence':'evidence/guard-receipt.json','build':'build/G3/Android/LotteryG3.apk','temp':'unity/Temp/staged.bin'}[destination]
                    sentinel.parent.mkdir(parents=True,exist_ok=True);sentinel.write_bytes(b'OUTSIDE_OR_PROTECTED_SENTINEL');os.link(sentinel,first)
                    if destination=='three_links':os.link(first,first.with_name('second.bin'))
                before=sentinel.read_bytes();files_before={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
                with patch.object(ci.legacy,'guard') as writer:
                    with self.assertRaises(ci.UnsafePathError):ci.guard(root,allow_generated_unity=True,android_cache=True)
                    writer.assert_not_called()
                self.assertEqual(sentinel.read_bytes(),before);self.assertEqual({p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()},files_before)
    def testColdCacheSymlinkDirectorySymlinkAndSpecialFilesRemainRefused(self):
        for kind in ('file_link','directory_link','fifo'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside,patch.dict(os.environ,GITHUB_JOB='android',GITHUB_RUN_ID='12345',GITHUB_RUN_ATTEMPT='1'):
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger();self.makeSyntheticColdProof(root,git,review)
                path=root/ci.CACHE_ROOT/'Bee/Android/unknown';path.parent.mkdir(parents=True);sentinel=Path(outside)/'sentinel';sentinel.write_bytes(b'UNCHANGED')
                if kind=='file_link':path.symlink_to(sentinel)
                elif kind=='directory_link':path.symlink_to(Path(outside),target_is_directory=True)
                else:os.mkfifo(path)
                with self.assertRaises(ci.UnsafePathError) as caught:ci.verify_preflight(root,allow_generated_unity=True,android_cache=True)
                line=ci.failure_line('CI','CI_APK',caught.exception);self.assertIn('pathClass=LIBRARY_BEE_ANDROID',line);self.assertIn('kind='+('fifo' if kind=='fifo' else 'symbolic_link'),line);self.assertEqual(sentinel.read_bytes(),b'UNCHANGED')
                self.assertNotIn(str(outside),line);self.assertNotIn('sentinel',line);self.assertNotIn('unknown',line)
    def testColdCacheIncompleteTraversalAndChangedInodeOrNlinkRefused(self):
        for attack in ('omitted','changed_inode','changed_nlink','enumeration_error'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as d,tempfile.TemporaryDirectory() as outside,patch.dict(os.environ,GITHUB_JOB='android',GITHUB_RUN_ID='12345',GITHUB_RUN_ATTEMPT='1'):
                root=Path(d);git,commit,trigger,review,source=self.makeReviewedGit(root);trigger();self.makeSyntheticColdProof(root,git,review)
                first=root/ci.CACHE_ROOT/'one.bin';second=first.with_name('two.bin');first.parent.mkdir(parents=True);first.write_bytes(b'cache');os.link(first,second)
                original_walk=os.walk;original_lstat=Path.lstat;hits=[0]
                def walking(*args,**kwargs):
                    if attack=='enumeration_error':kwargs['onerror'](PermissionError('PRIVATE_PATH_MUST_NOT_LEAK'))
                    for directory,dirs,files in original_walk(*args,**kwargs):yield directory,dirs,[x for x in files if not (attack=='omitted' and Path(directory)/x==second)]
                def lstat(path,*args,**kwargs):
                    if path==first:
                        hits[0]+=1
                        if hits[0]==2:
                            if attack=='changed_nlink':os.link(first,Path(outside)/'late_alias')
                            elif attack=='changed_inode':replacement=first.with_name('replacement');replacement.write_bytes(b'cache');os.replace(replacement,first)
                    return original_lstat(path,*args,**kwargs)
                with patch.object(ci.os,'walk',side_effect=walking),patch.object(Path,'lstat',lstat):
                    with self.assertRaises(ValueError):ci.verify_preflight(root,allow_generated_unity=True,android_cache=True)
    def testUnsafePathStdoutIsWhitelistedAndDoesNotPublishNamesContentsOrTargets(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/ci.TASK/'build/G3/Android/PRIVATE_SECRET.apk';path.parent.mkdir(parents=True);path.write_bytes(b'PRIVATE_FILE_CONTENT');os.link(path,path.with_suffix('.alias'))
            with self.assertRaises(ci.UnsafePathError) as caught:ci.regular_unaliased(path,root)
            error=caught.exception;line=ci.failure_line('CI','CI_APK',error)
            self.assertIn('pathClass=APK_OUTPUT',line);self.assertIn('kind=regular nlink=2',line);self.assertIn(hashlib.sha256(path.relative_to(root).as_posix().encode()).hexdigest(),line)
            for secret in ('PRIVATE_SECRET','PRIVATE_FILE_CONTENT',str(root)):self.assertNotIn(secret,line)
            error.path_class='SECRET';error.path_sha256='SECRET';error.kind='SECRET';error.nlink='SECRET';error.internal_links='SECRET'
            self.assertNotIn('SECRET',ci.failure_line('CI','CI_APK',error))
            error.path_class=['SECRET'];error.kind={'SECRET':True};error.path_shape='SECRET/raw/path'
            self.assertNotIn('SECRET',ci.failure_line('CI','CI_APK',error))
    def testOnlyAndroidPostCommandsRequestBoundedCacheCompatibility(self):
        for stage in ('edit','play','android'):
            for command in ('guard','restore-font','snapshot','tests','captures','apk','audit','diagnostics'):
                with self.subTest(stage=stage,command=command),patch.object(sys,'argv',['g3_ci.py',command,'--stage',stage]),patch.object(ci,'guard',side_effect=ValueError('synthetic stop before any writes')) as gate:
                    with self.assertRaises(ValueError):ci.main()
                    self.assertEqual(gate.call_args.kwargs['android_cache'],stage=='android' and command in ('apk','audit','diagnostics'))

    def runProvenanceFixture(self, attack):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'checkout';root.mkdir();runner=base/'runner';runner.mkdir(mode=0o700)
            output=runner/'output';output.touch();relative=ci.TASK+'/scripts/g3_path_diagnostics.py'
            path=root/relative;path.parent.mkdir(parents=True);raw=(ROOT/relative).read_bytes();path.write_bytes(raw)
            git_env=dict(PATH='/usr/bin:/bin',LC_ALL='C',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_SYSTEM='/dev/null',GIT_CONFIG_GLOBAL='/dev/null')
            def git(*args,input=None):return subprocess.check_output(['/usr/bin/git','-C',str(root),*args],input=input,env=git_env,stderr=subprocess.DEVNULL).decode().strip()
            git('init','-q');git('add','.');git('-c','user.name=Synthetic Provenance','-c','user.email=fixture@example.invalid','commit','-qm','source')
            head=git('rev-parse','HEAD');blob=git('rev-parse','HEAD:'+relative)
            env=dict(os.environ,GITHUB_WORKSPACE=str(root),GITHUB_SHA=head,GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1',GITHUB_JOB='android',RUNNER_TEMP=str(runner),GITHUB_OUTPUT=str(output))
            marker=b'print("UNREVIEWED_BLOB_MUST_NOT_EXECUTE")\n';shell=diagnostic_shell(ROOT);expected_success=True
            if attack=='replace_blob':
                replacement=git('hash-object','-w','--stdin',input=marker);git('replace',blob,replacement)
            elif attack=='replace_commit':
                path.write_bytes(marker);git('add','.');git('-c','user.name=Synthetic Provenance','-c','user.email=fixture@example.invalid','commit','-qm','alternate')
                alternate=git('rev-parse','HEAD');git('reset','--hard',head);git('replace',head,alternate)
            elif attack=='git_environment':
                foreign=base/'foreign';foreign.mkdir();fake_config=base/'config-fifo';os.mkfifo(fake_config)
                trace=base/'trace-sentinel';trace.write_bytes(b'UNCHANGED')
                env.update(GIT_DIR=str(foreign),GIT_WORK_TREE=str(foreign),GIT_COMMON_DIR=str(foreign),GIT_OBJECT_DIRECTORY=str(foreign),GIT_ALTERNATE_OBJECT_DIRECTORIES=str(foreign),GIT_INDEX_FILE=str(foreign/'index'),GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='include.path',GIT_CONFIG_VALUE_0=str(fake_config),GIT_CONFIG_SYSTEM=str(fake_config),GIT_CONFIG_GLOBAL=str(fake_config),GIT_TRACE=str(trace),GIT_REPLACE_REF_BASE='refs/other/',HOME=str(foreign),XDG_CONFIG_HOME=str(foreign))
            elif attack=='corrupt_named_blob':
                stored=root/'.git/objects'/blob[:2]/blob[2:];stored.chmod(0o600)
                stored.write_bytes(zlib.compress(b'blob '+str(len(marker)).encode()+b'\0'+marker));expected_success=False
            elif attack=='blocked_git_config':
                config=root/'.git/config';config.rename(root/'.git/config.original');os.mkfifo(config)
                shell=shell.replace('--kill-after=5s 40s','--kill-after=1s 1s',1);expected_success=False
            elif attack=='wrong_hash_pin':
                shell=shell.replace(hashlib.sha256(raw).hexdigest(),'0'*64);expected_success=False
            else:raise AssertionError('Unknown synthetic attack')
            started=time.monotonic();result=subprocess.run(['bash','-c',shell],cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=10)
            elapsed=time.monotonic()-started
            self.assertNotIn('UNREVIEWED_BLOB_MUST_NOT_EXECUTE',result.stdout+result.stderr)
            for secret in (str(root),str(base),'config-fifo','trace-sentinel'):self.assertNotIn(secret,result.stdout+result.stderr)
            self.assertEqual(path.read_bytes(),raw)
            if expected_success:
                self.assertEqual(result.returncode,0,result.stderr);self.assertIn('status=DIAGNOSTIC_ONLY',result.stdout)
                self.assertRegex(output.read_text(),r'^diagnostic_relative_path=lottery-g3-pathdiag-[0-9a-f]{24}/diagnostic.json\n$')
                report=json.loads((runner/output.read_text().strip().split('=',1)[1]).read_text())
                self.assertEqual(report['acceptance'],'NONE');self.assertEqual(report['identity']['observed']['gitHead'],head)
                if attack=='git_environment':self.assertEqual(trace.read_bytes(),b'UNCHANGED')
            else:
                self.assertNotEqual(result.returncode,0);self.assertEqual(output.read_bytes(),b'');self.assertFalse(list(runner.glob('lottery-g3-pathdiag-*')))
            if attack=='blocked_git_config':
                self.assertLess(elapsed,5);self.assertIn('SOURCE_OR_TIMEOUT_REJECTED',result.stderr)

    def testCommittedDiagnosticLoaderIgnoresBlobReplacement(self):self.runProvenanceFixture('replace_blob')
    def testCommittedDiagnosticLoaderIgnoresCommitReplacement(self):self.runProvenanceFixture('replace_commit')
    def testCommittedDiagnosticLoaderIgnoresGitRepositoryObjectAndConfigEnvironment(self):self.runProvenanceFixture('git_environment')
    def testCommittedDiagnosticLoaderRejectsCorruptedObjectBytesAndWrongDigest(self):
        for attack in ('corrupt_named_blob','wrong_hash_pin'):
            with self.subTest(attack=attack):self.runProvenanceFixture(attack)
    def testWholeDiagnosticLoaderTimeoutIncludesBlockedGit(self):self.runProvenanceFixture('blocked_git_config')

    def testWorkflowMaintainsLockedActionsAndNoCache(self):
        text=(ROOT/'.github/workflows/lottery-g3.yml').read_text()
        self.assertIn('/usr/bin/timeout --signal=TERM --kill-after=5s 40s /usr/bin/python3 -I -B -',text)
        self.assertIn("'/usr/bin/git', '--no-replace-objects'",text)
        raw=(ROOT/ci.TASK/'scripts/g3_path_diagnostics.py').read_bytes()
        self.assertIn("SOURCE_SHA256 = '"+hashlib.sha256(raw).hexdigest()+"'",text)
        self.assertIn("BLOB_ID = '"+hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()+"'",text)
        self.assertIn("steps.pathdiagnostics.outputs.diagnostic_relative_path != ''",text)
        self.assertIn('path: ${{ runner.temp }}/${{ steps.pathdiagnostics.outputs.diagnostic_relative_path }}',text)
        self.assertIn('group: unity-personal-proof',text);self.assertIn('androidVersionCode: 3',text);self.assertNotIn('actions/cache',text);self.assertNotIn('workflow_dispatch',text)
        actions=set(__import__('re').findall(r'uses: ([^\s]+)',text))
        self.assertEqual(actions,{'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683','actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02','game-ci/unity-test-runner@0ff419b913a3630032cbe0de48a0099b5a9f0ed9','game-ci/unity-builder@d829bfc901f2347c8fe18898f06712b66916ef42'})
        prepare=(ROOT/ci.TASK/'scripts/g3_prepare_runner.sh').read_text()
        self.assertIn('set -euo pipefail',prepare);self.assertLess(prepare.index('g3_ci.py guard'),prepare.index('sudo rm -rf'))
        self.assertLess(text.index('name: Native regression-edit'),text.index('name: Native regression-play'));self.assertLess(text.index('name: Native regression-play'),text.index('name: Native edit'))

if __name__=='__main__':unittest.main()
