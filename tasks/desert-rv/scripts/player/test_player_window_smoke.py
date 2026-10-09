#!/usr/bin/env python3
import json,os,pathlib,tempfile,unittest
from unittest.mock import patch
import player_window_smoke as p
class PlayerWindowTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.r=pathlib.Path(self.t.name);self.scene=self.r/p.SCENE;self.scene.parent.mkdir(parents=True);self.scene.write_text('saved scene');self.build=self.r/'build';self.build.mkdir();self.exe=self.build/'DesertRV.x86_64';self.exe.write_bytes(b'executable');self.exe.chmod(0o700)
  self.receipt=dict(mode=p.MODE,sourceCommit='a'*40,sceneSha256=p.sha(self.scene),executableSha256=p.sha(self.exe),executable=self.exe.name,targetSupported=True,buildSucceeded=True,settingsRestored=True,temporarySettingsOverridden=True,buildTarget="StandaloneLinux64",backend="Mono2x",candidateDefine="DESERTRV_REFERENCE_WINDOW_PROBE",width=1280,height=720,fullscreen="Windowed")
  self.root=patch.object(p,'ROOT',self.r);self.root.start();self.env=patch.dict(os.environ,{'GITHUB_SHA':'a'*40});self.env.start()
 def tearDown(self):self.root.stop();self.env.stop();self.t.cleanup()
 def write(self): (self.build/'build-receipt.json').write_text(json.dumps(self.receipt))
 def test_valid_exact_receipt(self):self.write();self.assertEqual(p.verify_build(self.build)[0],self.exe)
 def test_executable_hash_mismatch(self):
  self.write();self.exe.write_text('changed')
  with self.assertRaises(ValueError):p.verify_build(self.build)
 def test_scene_hash_mismatch(self):
  self.write();self.scene.write_text('changed')
  with self.assertRaises(ValueError):p.verify_build(self.build)
 def test_unsupported_target_rejected(self):
  self.receipt['targetSupported']=False;self.write()
  with self.assertRaises(ValueError):p.verify_build(self.build)
 def test_extra_receipt_fields_rejected(self):
  self.receipt['rawLog']='secret';self.write()
  with self.assertRaises(ValueError):p.verify_build(self.build)
 def test_receipt_traversal_rejected(self):
  self.receipt['executable']='../other';self.write()
  with self.assertRaises(ValueError):p.verify_build(self.build)
 def test_symlink_tree_rejected(self):
  (self.build/'linked').symlink_to(self.scene)
  with self.assertRaises(ValueError):p.tree_hash(self.build)
 def test_tree_change_invalidates(self):
  a=p.tree_hash(self.build);(self.build/'assembly.dll').write_text('new');self.assertNotEqual(a,p.tree_hash(self.build))
 def test_non_success_never_copies_video(self):
  task=self.r/'task';task.mkdir();ev=task/'player-private-evidence';ev.mkdir();(ev/'real-time.mp4').write_text('do not export');(task/'player-control.json').write_text(json.dumps(dict(activation='SUCCEEDED',build='SUCCEEDED',player='FAILED',licenseReturn='SUCCEEDED',privateCleanup='SUCCEEDED')))
  with patch.object(p,'TASK',task),patch.object(p,'PUBLIC',task/'public'),patch.object(p,'EVIDENCE',ev),patch.object(p,'source_unchanged'),patch.dict(os.environ,{'NATIVE_OUTCOME':'failure','GITHUB_OUTPUT':str(task/'output')}):p.export()
  self.assertEqual([f.name for f in (task/'public').iterdir()],['status.json'])
 def test_cleanup_failure_and_native_failure_each_block_media(self):
  task=self.r/'task';task.mkdir();ev=task/'private';ev.mkdir()
  for native,cleanup in [('failure','SUCCEEDED'),('success','FAILED')]:
   out=task/(native+cleanup);(task/'player-control.json').write_text(json.dumps(dict(activation='SUCCEEDED',build='SUCCEEDED',player='SUCCEEDED',licenseReturn='SUCCEEDED',privateCleanup=cleanup)))
   with patch.object(p,'TASK',task),patch.object(p,'PUBLIC',out),patch.object(p,'EVIDENCE',ev),patch.object(p,'source_unchanged'),patch.dict(os.environ,{'NATIVE_OUTCOME':native,'GITHUB_OUTPUT':str(task/'output')}):p.export()
   self.assertEqual([f.name for f in out.iterdir()],['status.json'])
 def test_no_partial_public_on_validation_failure(self):
  task=self.r/'task';task.mkdir();(task/'player-control.json').write_text('{"raw":"secret"}')
  with patch.object(p,'TASK',task),patch.object(p,'PUBLIC',task/'public'):
   with self.assertRaises(ValueError):p.export()
  self.assertFalse((task/'public').exists());self.assertFalse(list(task.glob('player-export-*')))
 def test_success_export_is_atomic_allowlist_and_rejects_raw_fields(self):
  from PIL import Image
  task=self.r/'task';task.mkdir();ev=task/'private';ev.mkdir();video=ev/'real-time.mp4';video.write_bytes(b'fixture video, ffprobe mocked')
  image=Image.new('RGB',(1280,720),'black');image.paste((255,180,50),(0,0,640,720))
  for i in range(3):image.save(ev/f'frame-{i}.png')
  summary=dict(mode=p.MODE,sourceCommit='a'*40,candidateOnly=True,humanPlaytest=False,gameplayAccepted=False,androidVerified=False,visualReviewed=False,inputsApplied=False,sourceVerified=True,durationSeconds=15.5,nominalCaptureFps=30,encodedFrameRate='30/1',averageFrameRate='30/1',captureStartUtc='2026-10-09T00:00:00+00:00',captureEndUtc='2026-10-09T00:00:16+00:00',identityChecks=100,encodedProgressFrames=465,windowId='123',playerPid=42,playerExecutableSha256='b'*64,buildTreeSha256='c'*64,sceneSha256=p.sha(self.scene),playerExitCode=0,encoderExitCode=0,encoderStopMethod='stdin-q',screenshots=3)
  (task/'player-control.json').write_text(json.dumps(dict(activation='SUCCEEDED',build='SUCCEEDED',player='SUCCEEDED',licenseReturn='SUCCEEDED',privateCleanup='SUCCEEDED')))
  probe={'streams':[dict(width=1280,height=720,r_frame_rate='30/1',avg_frame_rate='30/1')],'format':{'duration':'15.5'}}
  with patch.object(p,'TASK',task),patch.object(p,'PUBLIC',task/'public'),patch.object(p,'EVIDENCE',ev),patch.object(p,'source_unchanged'),patch.object(p,'probe_video',return_value=probe),patch.dict(os.environ,{'NATIVE_OUTCOME':'success','GITHUB_OUTPUT':str(task/'output')}):
   bad=dict(summary,rawLog='DO_NOT_EXPORT');(ev/'summary.json').write_text(json.dumps(bad))
   with self.assertRaises(ValueError):p.export()
   self.assertFalse((task/'public').exists())
   (ev/'summary.json').write_text(json.dumps(summary));p.export()
  self.assertEqual({f.name for f in (task/'public').iterdir()},{'summary.json','real-time.mp4','frame-0.png','frame-1.png','frame-2.png','sha256.json'})
 def test_tracked_uses_only_exact_process_local_safe_directory(self):
  with patch.object(p.subprocess,'check_output',return_value=b'') as call:
   self.assertEqual(p.tracked(),{})
  self.assertEqual(call.call_args.args[0],['git','-c','safe.directory='+str(self.r),'ls-files','-z'])
  self.assertEqual(call.call_args.kwargs,{'cwd':self.r})
 def test_prepare_step_has_own_required_secret_scope(self):
  # Check text boundaries without adding a YAML dependency to the Actions runner.
  workflow=(pathlib.Path(__file__).resolve().parents[4]/'.github/workflows/desert-rv-player-smoke.yml').read_text()
  steps=workflow.split('      - name: ')
  prepare=[s for s in steps if 'run: bash tasks/desert-rv/scripts/prepare_runner.sh' in s]
  self.assertEqual(len(prepare),1)
  for key in ('UNITY_LICENSE','UNITY_EMAIL','UNITY_PASSWORD'):
   self.assertIn(key+': ${{ secrets.'+key+' }}',prepare[0])
  preflight=next(s for s in steps if s.startswith('Validate fixed source'))
  self.assertNotIn('prepare_runner.sh',preflight);self.assertNotIn('secrets.UNITY_',preflight)
  self.assertLess(workflow.index('run: bash tasks/desert-rv/scripts/prepare_runner.sh'),workflow.index('docker build --build-arg'))
  self.assertLess(workflow.index('docker build --build-arg'),workflow.index('name: Official batch build'))
 def test_source_guards_runtime_and_batch_only(self):
  root=pathlib.Path(__file__).resolve().parents[4];base=root/'tasks/desert-rv';shell=(base/'scripts/player/container_entry.sh').read_text();cs=(base/'unity/Assets/DesertRV/Runtime/Diagnostics/ReferencePlayerWindowProbe.cs').read_text();builder=(base/'unity/Assets/DesertRV/Editor/PlayerBuild.cs').read_text()
  self.assertTrue(cs.startswith('#if DESERTRV_REFERENCE_WINDOW_PROBE && !UNITY_EDITOR'))
  for forbidden in ['SessionState','JourneyDirector','Input.','transform.position','Time.timeScale']:self.assertNotIn(forbidden,cs)
  self.assertIn('now - begin >= 15',cs);self.assertIn('IsBuildTargetSupported',builder);self.assertIn('File.WriteAllBytes(settingsPath, originalSettings)',builder)
  self.assertIn('unity-editor -projectPath',shell);self.assertNotIn('/opt/unity/Editor/Unity',shell);self.assertIn('env -u UNITY_LICENSE -u UNITY_EMAIL -u UNITY_PASSWORD -u UNITY_SERIAL',shell)
if __name__=='__main__':unittest.main()
