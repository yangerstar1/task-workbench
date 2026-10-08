"""No Blender/Unity. Fixtures test orchestration, exact timing and failure rejection only."""
import ast, hashlib, json, subprocess, tempfile, unittest, zlib, struct
from pathlib import Path
import plan, staged, assemble
HERE=Path(__file__).resolve().parent
class StagedTests(unittest.TestCase):
    def test_immutable_source_and_executor(self):staged.verify_source()
    def test_bounded_remaining_only(self):
        matrix=plan.matrix();self.assertLessEqual(len(matrix),16)
        self.assertTrue(all(0<len(x['frames'])<=24 for x in matrix))
        self.assertEqual({x['clip'] for x in matrix},set(plan.REMAINING));self.assertFalse(set(plan.REUSED)&set(plan.REMAINING))
        for c in plan.REMAINING:
            frames=[f for chunk in plan.chunks(c) for f in chunk]
            self.assertEqual(frames,plan.frames(c));self.assertEqual(frames[-1],plan.count(c))
            self.assertTrue(all(b-a in (1,2) for a,b in zip(frames,frames[1:])))
    def test_numeric_prefix_is_full_original_loop(self):
        tree=ast.parse((plan.ART/'animate.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='review_action')
        first=next(n for n in fn.body if isinstance(n,ast.For));text=ast.unparse(first)
        for token in ('sole hovering','link stretch','baked ankle target mismatch','support slip','contact height','validate_frame'):self.assertIn(token,text)
        self.assertNotIn('render(',text);self.assertIn('range(1, count + 1)',text)
    def test_python_parses(self):
        for path in HERE.glob('*.py'):ast.parse(path.read_text())
    def test_partial_chunk_cannot_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'stage-receipt.json';lock=staged.verify_source()
            p.write_text(json.dumps({'stage':'chunk','clip':'Attack','status':'PARTIAL_NOT_COMPLETE','art_source_manifest_sha256':lock['source_manifest_sha256'],'execution_manifest_sha256':staged.sha(HERE/'execution-manifest.json')}))
            with self.assertRaisesRegex(ValueError,'Missing chunks'):assemble.validate_chunks(tmp,'Attack',lock)
    def test_fake_technical_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock=staged.verify_source();Path(tmp,'stage-receipt.json').write_text(json.dumps({'stage':'technical','status':'COMPLETE_TECHNICAL_EVIDENCE_NOT_VISUAL_APPROVAL','art_source_manifest_sha256':lock['source_manifest_sha256'],'files':{}}))
            with self.assertRaisesRegex(ValueError,'missing required'):staged.verify_receipt(tmp,'technical',lock)
    def test_vfr_preserves_source_endpoint_duration(self):
        # Tiny synthetic codec fixture, never game evidence. Verifies the final 1/60
        # exposure does not disappear when most samples are spaced by 1/30.
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            def chunk(t,data):return struct.pack('>I',len(data))+t+data+struct.pack('>I',zlib.crc32(t+data)&0xffffffff)
            png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',16,16,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\0'*48)*16))+chunk(b'IEND',b'')
            (d/'fixture.png').write_bytes(png)
            for original_count in (5,18):
                ids=list(range(1,original_count+1,2))
                if ids[-1]!=original_count:ids.append(original_count)
                lines=['ffconcat version 1.0']
                for i,n in enumerate(ids):
                    duration=(ids[i+1]-n)/60 if i+1<len(ids) else 1/60
                    lines += ["file 'fixture.png'",'option framerate 60',f'duration {duration:.12f}']
                lines += ["file 'fixture.png'",'option framerate 60'];(d/'frames.ffconcat').write_text('\n'.join(lines)+'\n')
                target=d/f'{original_count}.mp4'
                subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(d/'frames.ffconcat'),'-fps_mode','vfr','-enc_time_base','1:60000','-c:v','libx264','-crf','23','-pix_fmt','yuv420p','-video_track_timescale','60000','-t',f'{original_count/60:.12f}',str(target)],check=True,timeout=30)
                data=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=duration,nb_frames:frame=best_effort_timestamp_time','-of','json',str(target)],timeout=10))
                self.assertEqual(int(data['streams'][0]['nb_frames']),len(ids));self.assertAlmostEqual(float(data['streams'][0]['duration']),original_count/60,places=5)
                self.assertEqual(len(data['frames']),len(ids))
                for f,n in zip(data['frames'],ids):self.assertAlmostEqual(float(f['best_effort_timestamp_time']),(n-1)/60,places=5)
if __name__=='__main__':unittest.main(verbosity=2)
