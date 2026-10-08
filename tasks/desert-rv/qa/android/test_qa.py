#!/usr/bin/env python3
import copy, json, struct, unittest, zlib, binascii, os
from unittest.mock import patch
from pathlib import Path
from qa import check_run, check_bytes, digest, png_size, check_video_report, check_qa_run, execution_preflight
from input_plan import validate
from kvm_acl import parse as parse_acl, grant as grant_acl

class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.pin={'runId':'123','runAttempt':'1','commit':'a'*40,'apkSha256':digest(b'apk'),'apkBytes':3}
        self.receipt=dict(self.pin,status='succeeded',architecture='ARM64',backend='IL2CPP',scope='traversal-test-only-no-combat-not-complete-game')
        self.raw=json.dumps(self.receipt).encode(); self.pin['receiptSha256']=digest(self.raw)
        self.run=dict(id=123,run_attempt=1,repository=dict(full_name='yangerstar1/task-workbench',private=False,fork=False),event='workflow_dispatch',head_branch='main',actor={'login':'yangerstar1'},triggering_actor={'login':'yangerstar1'},path='.github/workflows/desert-rv-android.yml',conclusion='success',status='completed',head_sha='a'*40)
    def test_good_run(self): check_run(self.run,self.pin)
    def test_run_rejections(self):
        for key,value in [('id',124),('run_attempt',2),('event','push'),('head_branch','other'),('conclusion','failure'),('status','in_progress'),('path','evil.yml'),('head_sha','b'*40),('actor',{'login':'other'}),('triggering_actor',{'login':'other'})]:
            r=copy.deepcopy(self.run);r[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):check_run(r,self.pin)
    def test_repo_rejections(self):
        for k,v in [('full_name','other/repo'),('private',True),('fork',True)]:
            r=copy.deepcopy(self.run);r['repository'][k]=v
            with self.subTest(key=k),self.assertRaises(ValueError):check_run(r,self.pin)
    def test_bytes(self):check_bytes(b'apk',self.raw,self.receipt,self.pin)
    def test_altered_apk(self):
        with self.assertRaises(ValueError):check_bytes(b'bpk',self.raw,self.receipt,self.pin)
    def test_altered_receipt(self):
        with self.assertRaises(ValueError):check_bytes(b'apk',self.raw+b' ',self.receipt,self.pin)
    def test_altered_verification(self):
        v=dict(self.receipt,commit='b'*40)
        with self.assertRaises(ValueError):check_bytes(b'apk',self.raw,v,self.pin)
    @staticmethod
    def png(w=2,h=2):
        def chunk(kind,data): return struct.pack('>I',len(data))+kind+data+struct.pack('>I',binascii.crc32(kind+data)&0xffffffff)
        return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\xff\0\0\xff'*w)*h))+chunk(b'IEND',b'')
    def test_png_complete_pixels(self): self.assertEqual(png_size(self.png()),(2,2))
    def test_png_truncation_and_corruption_rejected(self):
        good=self.png()
        for bad in (good[:24],good[:-1],good[:-12],good+b'extra',good[:45]+bytes([good[45]^1])+good[46:]):
            with self.subTest(size=len(bad)),self.assertRaises(ValueError):png_size(bad)
    def test_png_missing_pixel_rows_rejected(self):
        def chunk(kind,data): return struct.pack('>I',len(data))+kind+data+struct.pack('>I',binascii.crc32(kind+data)&0xffffffff)
        bad=self.png()[:33]+chunk(b'IDAT',zlib.compress(b'\0'))+chunk(b'IEND',b'')
        with self.assertRaises(ValueError):png_size(bad)
    def test_video_decoded_report(self):
        check_video_report({'streams':[{'codec_type':'video','width':1280,'height':720,'duration':'30','nb_read_frames':'900'}]},1280,720)
    def test_video_missing_corrupt_or_wrong_size_report_rejected(self):
        base={'streams':[{'codec_type':'video','width':1280,'height':720,'duration':'30','nb_read_frames':'900'}]}
        for key,value in [('width',720),('height',1280),('duration','nan'),('duration','0'),('duration','122'),('nb_read_frames','0')]:
            report=copy.deepcopy(base);report['streams'][0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):check_video_report(report,1280,720)
        with self.assertRaises(ValueError):check_video_report({},1280,720)
    def test_live_qa_identity(self):
        run=copy.deepcopy(self.run);run.update(path='.github/workflows/desert-rv-android-qa.yml',status='in_progress')
        env={'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'a'*40}
        check_qa_run(run,env)
        for key,value in [('run_attempt',2),('path','other.yml'),('head_sha','b'*40),('status','completed'),('actor',{'login':'other'})]:
            changed=copy.deepcopy(run);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):check_qa_run(changed,env)
    def test_execution_without_hosted_context_blocks_before_api(self):
        with patch.dict(os.environ,{},clear=True),patch('qa.api') as api:
            with self.assertRaises(ValueError):execution_preflight()
            api.assert_not_called()
    def test_self_declared_environment_is_not_enough(self):
        env=dict(GITHUB_ACTIONS='true',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_REPOSITORY='yangerstar1/task-workbench',GITHUB_REF='refs/heads/main',GITHUB_ACTOR='yangerstar1',GITHUB_TRIGGERING_ACTOR='yangerstar1',QA_MODE='capture-only',GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1',SOURCE_RUN_ID='123',GITHUB_SHA='a'*40)
        run=copy.deepcopy(self.run);run.update(path='.github/workflows/desert-rv-android-qa.yml',status='in_progress',head_sha='b'*40)
        with patch.dict(os.environ,env,clear=True),patch('qa.api',return_value=run):
            with self.assertRaises(ValueError):execution_preflight()
    def test_acl_exact_parse(self):
        self.assertEqual(parse_acl('# file: /dev/kvm\nuser::rw-\ngroup::rw-\nother::---\n'),{'user:':'rw-','group:':'rw-','other:':'---'})
    def test_acl_malformed_rejected(self):
        for text in ('user::rwx\nuser::rw-','default:user::rw-','user:someone:rw-','user::rwx #effective:r--'):
            with self.assertRaises(RuntimeError):parse_acl(text)
    def test_acl_later_run_or_retry_blocked_before_device(self):
        for number,attempt in [('5','1'),('4','2'),('3','1')]:
            with patch.dict(os.environ,{'GITHUB_RUN_NUMBER':number,'GITHUB_RUN_ATTEMPT':attempt},clear=True),patch('kvm_acl.os.stat') as stat:
                with self.assertRaises(RuntimeError):grant_acl()
                stat.assert_not_called()
    def test_acl_no_explicit_input_blocks_before_device(self):
        with patch.dict(os.environ,{'GITHUB_RUN_NUMBER':'4','GITHUB_RUN_ATTEMPT':'1','QA_MODE':'capture-only'},clear=True),patch('kvm_acl.os.stat') as stat:
            with self.assertRaises(RuntimeError):grant_acl()
            stat.assert_not_called()
    def test_unobserved_plan_blocks(self):
        plan=json.loads(Path(__file__).with_name('coordinates.json').read_text())
        with self.assertRaises(AssertionError):validate(plan,1280)
    def test_plan_bounds(self):
        s={'sourceScreenshotSha256':'a'*64,'captureRunId':'123','intervalMs':16,'frames':[[[1,2],[3,4]],[[2,3],[4,5]]]}
        plan={'status':'reviewed','screens':{'1280x720':s}}
        self.assertEqual(validate(plan,1280)['width'],1280)
        for bad in [-1,1280,float('nan'),float('inf')]:
            p=copy.deepcopy(plan);p['screens']['1280x720']['frames'][0][0][0]=bad
            with self.subTest(bad=bad),self.assertRaises(AssertionError):validate(p,1280)

if __name__=='__main__':unittest.main()
