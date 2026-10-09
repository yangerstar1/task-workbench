#!/usr/bin/env python3
"""Synthetic protocol processes only. No Unity, X11, Docker or licensing."""
import importlib.util,json,os,pathlib,subprocess,sys,tempfile,types,unittest
from unittest.mock import patch
SCRIPTS=pathlib.Path(__file__).parent.parent
spec=importlib.util.spec_from_file_location('capture_shutdown_under_test',SCRIPTS/'capture_game_window.py')
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
class InputPipe:
    def __init__(self,broken=False):self.data='';self.broken=broken
    def write(self,data):
        if self.broken:raise BrokenPipeError()
        self.data+=data
    def flush(self):pass
    def close(self):pass
class Process:
    def __init__(self,code=0,premature=False,broken=False,timeout=False):
        self.final=code;self.returncode=code if premature else None;self.stdin=InputPipe(broken);self.stdout=['frame=30\n'];self.timeout=timeout;self.killed=False
    def poll(self):return self.returncode
    def wait(self,timeout=None):
        if self.timeout and not self.killed:raise subprocess.TimeoutExpired('synthetic-encoder',timeout)
        self.returncode=-9 if self.killed else self.final;return self.returncode
    def kill(self):self.killed=True;self.returncode=-9
class Thread:
    def __init__(self,target,daemon=True):self.target=target
    def start(self):self.target()
    def join(self,timeout=None):pass
class CaptureShutdownTests(unittest.TestCase):
    def run_capture(self,proc,editor_exit=0,video_exists=True):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory);h=root/'handshake';h.mkdir();video=root/'synthetic.mp4';receipt=root/'receipt.json'
            (h/'request.json').write_text(json.dumps({'title':'DESERTRV_GAME_'+'a'*32,'pid':os.getpid()}));(h/'stop.json').write_text(json.dumps({'editorExitCode':editor_exit}))
            if video_exists:video.write_bytes(b'SYNTHETIC PROTOCOL FIXTURE NOT GAMEVIEW')
            with patch.object(sys,'argv',['capture',str(h),str(video),str(receipt),str(os.getpid())]),patch.dict(os.environ,UNITY_EDITOR=sys.executable,DISPLAY='synthetic'),patch.object(capture,'verify_owned_process',return_value=None),patch.object(capture,'identity',return_value=(320,200)),patch.object(capture.subprocess,'run',return_value=types.SimpleNamespace(stdout='123\n')),patch.object(capture.subprocess,'Popen',return_value=proc),patch.object(capture.threading,'Thread',Thread):
                code=capture.main()
            return code,json.loads(receipt.read_text())
    def test_q_zero_exit_and_successful_editor_stop_is_the_only_success(self):
        proc=Process();code,r=self.run_capture(proc);self.assertEqual(code,0);self.assertTrue(r['sourceVerified']);self.assertEqual(proc.stdin.data,'q\n');self.assertEqual(r['encoderExitCode'],0);self.assertIsNone(r['failureCode']);self.assertIn('videoSha256',r)
    def test_reviewer_counterexample_encoder_exit_one_cannot_succeed(self):
        code,r=self.run_capture(Process(code=1));self.assertEqual(code,1);self.assertFalse(r['sourceVerified']);self.assertEqual(r['failureCode'],'encoder-exit-nonzero');self.assertNotIn('videoSha256',r)
    def test_editor_failure_cannot_succeed_even_if_encoder_exits_zero(self):
        code,r=self.run_capture(Process(),editor_exit=3);self.assertEqual(code,1);self.assertFalse(r['editorStopAcknowledged']);self.assertEqual(r['failureCode'],'editor-stop-not-success');self.assertNotIn('videoSha256',r)
    def test_encoder_premature_exit_rejected(self):
        code,r=self.run_capture(Process(premature=True));self.assertEqual(code,1);self.assertFalse(r['sourceVerified']);self.assertNotIn('videoSha256',r)
    def test_broken_owned_input_pipe_rejected(self):
        code,r=self.run_capture(Process(broken=True));self.assertEqual(code,1);self.assertEqual(r['encoderFailureCode'],'encoder-stop-pipe');self.assertNotIn('videoSha256',r)
    def test_encoder_stop_timeout_rejected(self):
        code,r=self.run_capture(Process(timeout=True));self.assertEqual(code,1);self.assertEqual(r['encoderFailureCode'],'encoder-stop-timeout');self.assertNotIn('videoSha256',r)
    def test_missing_video_after_successful_exit_rejected(self):
        code,r=self.run_capture(Process(),video_exists=False);self.assertEqual(code,1);self.assertEqual(r['failureCode'],'encoder-missing-video');self.assertNotIn('videoSha256',r)
if __name__=='__main__':unittest.main()
