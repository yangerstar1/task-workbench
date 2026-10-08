#!/usr/bin/env python3
"""Synthetic unit fixtures only; no Unity/video/playthrough acceptance evidence."""
import hashlib,json,pathlib,tempfile,unittest
from PIL import Image
import prepare_safe_diagnostic_export as export

class SafeExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.src=self.root/'raw';self.src.mkdir();self.dst=self.root/'public'
        im=Image.new('RGB',(320,200));im.putdata([(x%256,y%256,(x+y)%256) for y in range(200) for x in range(320)])
        self.rows=[]
        for frame in (1,2):
            name=f'frame-{frame:08}.png';im.save(self.src/name)
            self.rows += [dict(kind='sample',frame=frame,wall=frame,generation=1,activityEvidence='driving-traversal',status='Playing',screenWidth=320,screenHeight=200),
                          dict(kind='capture',frame=frame,wall=frame+.01,detail=name)]
        self.write_rows()
        (self.src/'diagnostic-scope.json').write_text(json.dumps({'sourceCommit':'a'*40}))
        video=b'SYNTHETIC VIDEO UNIT FIXTURE; probe is mocked, not runtime evidence';(self.src/'real-time.mp4').write_bytes(video)
        self.receipt=dict(mode='VERIFIED_GAME_WINDOW_CAPTURE',sourceVerified=True,nominalCaptureFps=30,title='DESERTRV_GAME_'+'b'*32,
            windowId='123',pid=42,identityChecks=30,encodedProgressFrames=90,videoSha256=hashlib.sha256(video).hexdigest(),width=320,height=200,
            captureStartUtc='2026-01-01T00:00:00+00:00',captureEndUtc='2026-01-01T00:00:03+00:00')
        self.write_receipt()
    def tearDown(self):self.tmp.cleanup()
    def write_rows(self):(self.src/'timeline.jsonl').write_text('\n'.join(json.dumps(r) for r in self.rows))
    def write_receipt(self):(self.src/'capture-receipt.json').write_text(json.dumps(self.receipt))
    @staticmethod
    def probe(_):return {'streams':[{'width':320,'height':200,'r_frame_rate':'30/1','avg_frame_rate':'30/1'}],'format':{'duration':'3'}}
    def reject(self):
        with self.assertRaises(Exception):export.prepare(self.src,self.dst,self.probe)
        self.assertFalse(self.dst.exists());self.assertFalse(list(self.root.glob('.diagnostic-export-*')))
    def test_valid_fixture_exports_allowlist_atomically(self):
        summary=export.prepare(self.src,self.dst,self.probe)
        self.assertFalse(summary['gameplayAccepted'])
        self.assertEqual({p.name for p in self.dst.iterdir()},{'frame-00000001.png','frame-00000002.png','real-time.mp4','diagnostic-summary.json','export-sha256.json'})
    def test_duplicate_frame_rejected(self):self.rows.append(self.rows[0]);self.write_rows();self.reject()
    def test_nonfinite_time_rejected(self):self.rows[0]['wall']=float('nan');self.write_rows();self.reject()
    def test_reversed_capture_time_rejected(self):self.rows[-1]['wall']=.5;self.write_rows();self.reject()
    def test_blank_png_rejected(self):Image.new('RGB',(320,200)).save(self.src/'frame-00000001.png');self.reject()
    def test_broken_crc_rejected(self):
        p=self.src/'frame-00000001.png';data=bytearray(p.read_bytes());data[29]^=1;p.write_bytes(data);self.reject()
    def test_symlink_file_rejected(self):
        p=self.src/'frame-00000001.png';other=self.root/'image.png';p.rename(other);p.symlink_to(other);self.reject()
    def test_symlink_parent_rejected(self):
        link=self.root/'linked';link.symlink_to(self.src,target_is_directory=True)
        with self.assertRaises(Exception):export.prepare(link,self.dst,self.probe)
        self.assertFalse(self.dst.exists())
    def test_video_identity_failure_rejected(self):self.receipt['sourceVerified']=False;self.write_receipt();self.reject()
    def test_modified_video_rejected(self):(self.src/'real-time.mp4').write_bytes(b'changed');self.reject()
    def test_late_activity_validation_leaves_no_partial(self):self.rows[2]['activityEvidence']='unknown';self.write_rows();self.reject()
    def test_metadata_strings_never_exported(self):
        self.rows[0]['loadError']='SECRET LOG PATH AND RAW TRACE';self.write_rows();export.prepare(self.src,self.dst,self.probe)
        self.assertNotIn('SECRET',(self.dst/'diagnostic-summary.json').read_text())
if __name__=='__main__':unittest.main()
