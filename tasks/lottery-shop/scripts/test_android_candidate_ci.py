#!/usr/bin/env python3
"""Focused synthetic adapter checks; never a native/APK/device pass."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import android_candidate_ci as ci

IDENT = dict(sourceCommit='1'*40, reviewedCandidateCommit='2'*40, runId='123', runAttempt='1', requestId='lottery-visual-20261014-39')


def request():
    review=dict(sourceCommit='2'*40,status='APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY',reviewer='independent-source-review',reviewId='visual-source-20261014-39',reviewedAtUtc='2026-10-14T00:00:00Z')
    return dict(schemaVersion=3,requestId=IDENT['requestId'],sourceCommit='2'*40,purpose=ci.visual.SCOPE,sourceReview=review,
        executionProfile=ci.visual.FULL_DIAGNOSTIC,androidBuild='DEVELOPMENT_CANDIDATE_APK',
        androidReview=dict(review,status='APPROVED_FOR_DIAGNOSTIC_ANDROID_ONLY',reviewId='android-source-20261014-39'))


def axml(package=ci.PACKAGE,version=39):
    strings=['manifest','package',package,'versionCode','versionName','0.0.39','http://schemas.android.com/apk/res/android']
    payload=b'';offsets=[]
    for text in strings:
        raw=text.encode();offsets.append(len(payload));payload+=bytes([len(text),len(raw)])+raw+b'\0'
    start=28+4*len(strings);pool=struct.pack('<HHIIIIII',1,28,start+len(payload),len(strings),0,0x100,start,0)+b''.join(struct.pack('<I',o) for o in offsets)+payload
    def attr(ns,key,typ,value):return struct.pack('<IIIHBBI',ns,key,0xffffffff,8,0,typ,value)
    attrs=[attr(0xffffffff,1,3,2),attr(6,3,16,version),attr(6,4,3,5)]
    chunk=struct.pack('<HHI',0x102,16,36+20*len(attrs))+struct.pack('<II',1,0xffffffff)+struct.pack('<IIHHHHHH',0xffffffff,0,20,20,len(attrs),0,0,0)+b''.join(attrs)
    return struct.pack('<HHI',3,8,8+len(pool)+len(chunk))+pool+chunk


def fixture(root,package=ci.PACKAGE,version=39,abi='arm64-v8a',duplicate=False):
    folder=root/ci.BUILD;folder.mkdir(parents=True);apk=folder/ci.APK
    elf=b'\x7fELF\x02\x01'+b'\0'*12+struct.pack('<H',183)
    with zipfile.ZipFile(apk,'w') as z:
        z.writestr('AndroidManifest.xml',axml(package,version));z.writestr('classes.dex',b'fixture')
        for name in ('libil2cpp.so','libunity.so'):z.writestr('lib/'+abi+'/'+name,elf)
        z.writestr('synthetic-padding',b'0'*1024**2)
        if duplicate:z.writestr('classes.dex',b'duplicate')
    data=dict(scope=ci.SCOPE,sourceCommit=IDENT['sourceCommit'],runId='123',unityVersion='6000.3.19f1',
        buildResult='Succeeded',buildTarget='Android',scriptingBackend='IL2CPP',architecture='ARM64',minSdk=26,targetSdk=35,
        graphicsApis='OpenGLES3',rulesSha256=ci.g3.RULES_SHA,standardsDigest=ci.g3.STANDARDS_DIGEST,runtimeScene=ci.g3.SCENE,
        fakeAd='DEVELOPMENT_FAKE_ONLY',versionCode=39,versionName='0.0.39',applicationIdentifier=ci.PACKAGE,
        normalRuntimeFixture='NONE',coldBuild=True,deviceQa='NOT_RUN',renderedFrameQa='NOT_RUN',gameplayQa='NOT_RUN',
        signing='development-debug',finalQuality='NOT_PASSED',apkBytes=apk.stat().st_size,apkSha256=ci.visual.sha(apk),
        builtAtUtc='2026-10-14T01:00:00Z',editorRevision='6000.3.19f1 (7689f4515d75)')
    outer=dict(schemaVersion=1,**{k:IDENT[k] for k in ('sourceCommit','reviewedCandidateCommit','runId','runAttempt')},build=data)
    (folder/'diagnostic-build-receipt.json').write_text(json.dumps(outer));return apk,outer


class RequestTests(unittest.TestCase):
    def test_explicit_separate_review(self):
        r=request();self.assertEqual(ci.visual.request_profile(r),ci.visual.FULL_DIAGNOSTIC)
        self.assertEqual(r['sourceReview']['status'],'APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY')
    def test_legacy_never_acquires_apk(self):
        for version in (1,2):
            r=request();r['schemaVersion']=version;r.pop('androidBuild');r.pop('androidReview')
            if version==1:r.pop('executionProfile')
            self.assertEqual(ci.visual.request_profile(r),ci.visual.FULL_DIAGNOSTIC)
            with tempfile.TemporaryDirectory() as d,patch.object(ci.visual,'identity',return_value=dict(IDENT,scope=ci.visual.SCOPE)),patch.object(ci.visual,'read_diagnostic_request',return_value=r),patch.dict(os.environ,GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1'):
                with self.assertRaises(ValueError):ci.identity(Path(d))
    def test_bad_capability_and_review_rejected(self):
        mutations=[lambda r:r.update(androidBuild=True),lambda r:r.pop('androidReview'),lambda r:r.update(extra='SECRET'),lambda r:r['androidReview'].update(sourceCommit='3'*40),lambda r:r['androidReview'].update(status='APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY'),lambda r:r['androidReview'].update(reviewedAtUtc='2099-01-01T00:00:00Z'),lambda r:r['androidReview'].update(extra='SECRET')]
        for mutate in mutations:
            r=request();mutate(r)
            with self.assertRaises(ValueError):ci.visual.request_profile(r)
    def test_build_command_graphics_and_real_identity(self):
        argv=ci.build_argv(IDENT);self.assertIn('-force-glcore',argv);self.assertNotIn('-nographics',argv)
        for k in ('sourceCommit','reviewedCandidateCommit','runId','runAttempt'):self.assertIn(IDENT[k],argv)
        self.assertIn('Lottery.G3.Editor.G3Build.BuildAndroidDiagnostic',argv)


class SafetyTests(unittest.TestCase):
    def test_signature_uses_only_fixed_bundled_java_and_sdk(self):
        command=ci.signature_command()
        self.assertIn('export JAVA_HOME=/opt/unity/Editor/Data/PlaybackEngines/AndroidPlayer/OpenJDK', command)
        self.assertIn('test -x "$JAVA_HOME/bin/java"', command)
        self.assertIn('export PATH="$JAVA_HOME/bin:/usr/bin:/bin"', command)
        self.assertIn('verify --verbose --print-certs /github/workspace/'+ci.BUILD+'/'+ci.APK, command)
        self.assertNotIn('apt-get',command)
        self.assertNotIn('curl',command)
    def test_signature_fixed_hex_across_chunks(self):
        raw=b'Signer #1 certificate SHA-256 digest: '+b'a'*64+b'\nSECRET_DN_and_native_noise\nSAFE_PROJECT_NATIVE_EXIT_CODE=0\n'
        for n in (1,7,512):
            scan=ci.SignatureScan()
            for i in range(0,len(raw),n):scan.feed(raw[i:i+n])
            self.assertEqual(scan.certificates,['a'*64]);self.assertEqual(scan.exit_markers,1)
    def test_signature_other_signer_and_unknown_text_rejected(self):
        for line in (b'Signer #2 certificate SHA-256 digest: '+b'a'*64,b'Signer #1 certificate SHA-256 digest: SECRET'):
            with self.assertRaises(ValueError):ci.SignatureScan().feed(line+b'\n')
        scan=ci.SignatureScan();scan.feed(b'X'*10000+b'\n');self.assertEqual(scan.certificates,[]);self.assertEqual(scan.line,b'')
    def test_output_limit_and_native_marker_required(self):
        scan=ci.SignatureScan()
        with self.assertRaises(ValueError):scan.feed(b'x'*(ci.private.MAX_OUTPUT+1))
        with patch.object(ci.private,'captured',return_value=(0,ci.safe.ProcessScan())):
            self.assertEqual(ci.process(IDENT,'FIXED',1)['status'],'NATIVE_FAILED')
    def test_process_exceptions_are_fixed_no_raw_leak(self):
        with patch.object(ci.private,'captured',side_effect=ValueError('SECRET')):
            result=ci.process(IDENT,'FIXED',1)
            self.assertEqual(result['status'],'ADAPTER_REJECTED');self.assertNotIn('SECRET',json.dumps(result))
    def test_json_duplicate_nan_links_and_oversize(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'x.json'
            for raw in ('{"x":1,"x":2}','{"x":NaN}',' ' * 65537):
                p.write_text(raw)
                with self.assertRaises(ValueError):ci.load(p,root)
            p.unlink();p.symlink_to(root/'target')
            with self.assertRaises(ValueError):ci.load(p,root)
    def test_container_name_exact_and_first_attempt(self):
        self.assertEqual(ci.name(IDENT),'lottery-android-candidate-123-1')
        for change in ({'runId':'123;echo SECRET'},{'runAttempt':'2'}):
            with self.assertRaises(ValueError):ci.name(dict(IDENT,**change))


class ApkTests(unittest.TestCase):
    def test_synthetic_apk_checks(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);apk,_=fixture(root);r=ci.inspect_apk(root,IDENT)
            self.assertEqual(r['apkSha256'],ci.visual.sha(apk));self.assertEqual(r['binaryManifest']['versionCode'],39)
    def test_old_package_version_and_abi_rejected(self):
        for args in ({'package':'com.buyuqi.lotteryprobe'},{'version':3},{'abi':'x86_64'},{'duplicate':True}):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);fixture(root,**args)
                with self.assertRaises(ValueError):ci.inspect_apk(root,IDENT)
    def test_hash_identity_unknown_receipt_and_claims_rejected(self):
        for change in (lambda r:r.update(runAttempt='2'),lambda r:r.update(extra='SECRET'),lambda r:r['build'].update(coldBuild=1),lambda r:r['build'].update(apkSha256='f'*64),lambda r:r['build'].update(deviceQa='PASSED')):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);_,r=fixture(root);change(r);(root/ci.BUILD/'diagnostic-build-receipt.json').write_text(json.dumps(r))
                with self.assertRaises(ValueError):ci.inspect_apk(root,IDENT)
    def test_file_links_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);apk,_=fixture(root);os.link(apk,apk.with_suffix('.alias'))
            with self.assertRaises(ValueError):ci.inspect_apk(root,IDENT)


class LifecycleTests(unittest.TestCase):
    def simulate(self, root, fault=None):
        (root/ci.private.TASK).mkdir(parents=True)
        requestpath=root/ci.visual.REQUEST;requestpath.parent.mkdir(parents=True);requestpath.write_text(json.dumps(request()))
        upstream=root/'.visual-safe-upstream/dist/platforms/ubuntu';upstream.mkdir(parents=True)
        (upstream/'activate.sh').write_text(ci.private.NATIVE_COMMAND)
        (upstream/'return_license.sh').write_text(ci.safe.RETURN_COMMAND)
        events=[]
        def process(ident,command,seconds,scan=None):
            kind='signature' if isinstance(scan,ci.SignatureScan) else ('return' if '-returnlicense' in command else ('build' if 'BuildAndroidDiagnostic' in command else 'activation'))
            events.append(kind)
            if kind=='build':
                path=root/ci.BUILD/ci.APK;path.parent.mkdir(parents=True);path.write_bytes(b'SYNTHETIC_APK_NOT_NATIVE')
                if fault=='planted':
                    target=root/ci.OUT;target.mkdir(parents=True);(target/'diagnostic-apk-receipt.json').write_text('SECRET')
            if kind=='signature':scan.certificates=['a'*64]
            failed=fault==kind
            return dict(status='NATIVE_FAILED' if failed else 'NATIVE_SUCCEEDED',dockerExitCode=1 if failed else 0,nativeExitCode=1 if failed else 0,nativeExitMarkerCount=1,observations={k:0 for k in ci.private.TOKENS})
        def cleanup(name):
            events.append('cleanup');self.assertEqual(name,'lottery-android-candidate-123-1')
            return dict(status='CLEANUP_FAILED' if fault=='cleanup' else 'ABSENCE_VERIFIED',removalExitCode=0)
        def inspect(root,ident):return dict(apkSha256=ci.visual.sha(root/ci.BUILD/ci.APK),apkBytes=23)
        output=root/'github-output';output.touch()
        with patch.object(ci.visual,'guard'),patch.object(ci,'identity',return_value=IDENT),patch.object(ci,'settings_baseline',return_value={}),patch.object(ci.inventory,'settings_gate',return_value={'rawSettingsExported':False}),patch.object(ci.private,'git',return_value=ci.private.PIN),patch.object(ci.private,'derive_serial',return_value='SYNTHETIC'),patch.object(ci.private,'captured',return_value=(0,None)),patch.object(ci,'process',side_effect=process),patch.object(ci,'inspect_apk',side_effect=inspect),patch.object(ci.private,'cleanup',side_effect=cleanup),patch.dict(os.environ,GITHUB_OUTPUT=str(output),UNITY_LICENSE='SYNTHETIC',UNITY_EMAIL='SYNTHETIC',UNITY_PASSWORD='SYNTHETIC'):
            if fault=='planted':
                with self.assertRaises(ValueError):ci.run(root)
                self.assertEqual(output.read_text(),'')
                self.assertIn('cleanup',events);return
            result=ci.run(root)
        payload=json.loads((root/ci.OUT/'diagnostic-apk-receipt.json').read_text())
        self.assertNotIn('SECRET',json.dumps(payload));self.assertEqual(output.read_text(),'safe_receipt=true\n')
        self.assertEqual(events[-1],'cleanup')
        if fault:
            self.assertEqual(result,1);self.assertFalse((root/ci.OUT/ci.APK).exists())
        else:
            self.assertEqual(result,0);self.assertTrue((root/ci.OUT/ci.APK).exists())
            self.assertEqual(events,['activation','build','signature','return','cleanup'])
            self.assertEqual(payload['deviceQa'],'NOT_RUN');self.assertEqual(payload['g3Gate'],'NOT_EVALUATED')
    def test_success_cleans_before_delivery(self):
        with tempfile.TemporaryDirectory() as d:self.simulate(Path(d))
    def test_failed_build_signature_return_cleanup_never_deliver(self):
        for fault in ('activation','build','signature','return','cleanup'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as d:self.simulate(Path(d),fault)
    def test_native_planted_receipt_never_sets_upload_output(self):
        with tempfile.TemporaryDirectory() as d:self.simulate(Path(d),'planted')


class WiringTests(unittest.TestCase):
    def test_workflow_keeps_original_route_and_checks_cleanup(self):
        root=Path(__file__).resolve().parents[3];s=(root/'.github/workflows/lottery-visual-candidate.yml').read_text()
        self.assertIn('test_android_candidate_ci.py -v',s);self.assertIn("needs.visual-candidate.outputs.cleanup_outcome == 'success'",s)
        self.assertIn("steps.androidbuild.outputs.safe_receipt == 'true'",s)
        self.assertIn("steps.androidcleanup.outcome == 'success'",s)
        self.assertIn('id: nativefinish',s);self.assertNotIn('continue-on-error: true',s)
    def test_original_build_entry_defaults_and_isolated_diagnostic(self):
        root=Path(__file__).resolve().parents[3];s=(root/'tasks/lottery-shop/unity/Assets/G3/Editor/G3Build.cs').read_text()
        for expected in ('BuildAndroid() => BuildAndroidInternal(false)','BuildAndroidDiagnostic() => BuildAndroidInternal(true)','diagnostic?39:3','diagnostic?"0.0.39":"0.0.3"','"com.buyuqi.lotteryprobe.candidate":"com.buyuqi.lotteryprobe"','else File.WriteAllText(Path.Combine(output,"build-receipt.json")'):
            self.assertIn(expected,s)


if __name__ == '__main__':unittest.main()
