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
 def control(self,**changes):
  native=p.empty_build_native();native.update(stage='BUILD_RECEIPT_WRITTEN',targetChecked=True,targetSupported=True,buildReportAvailable=True,settingsRestored=True,buildResult='SUCCEEDED')
  result=dict(activation='SUCCEEDED',build='SUCCEEDED',player='SUCCEEDED',licenseReturn='SUCCEEDED',privateCleanup='SUCCEEDED',buildDiagnostic=dict(native=native,logClassification=p.startup.empty_report(),failureCode='NONE',batchExitCode=0,batchTimedOut=False),captureFailureCode='NONE',containerSource=p.empty_source(),sourceRecovery=self.recovery());result.update(changes);return result
 def recovery(self):
  result=p.empty_recovery();result.update(status='SUCCEEDED',sourceModesRestored=True,afterPreserved=True);result['settingsDiff']=dict(classification='NO_CHANGE',changedFields=[],unknownLineCount=0);return result
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
  task=self.r/'task';task.mkdir();ev=task/'player-private-evidence';ev.mkdir();(ev/'real-time.mp4').write_text('do not export');(task/'player-control.json').write_text(json.dumps(self.control(player='FAILED')))
  with patch.object(p,'TASK',task),patch.object(p,'PUBLIC',task/'public'),patch.object(p,'EVIDENCE',ev),patch.object(p,'source_unchanged'),patch.dict(os.environ,{'NATIVE_OUTCOME':'failure','GITHUB_OUTPUT':str(task/'output')}):p.export()
  self.assertEqual([f.name for f in (task/'public').iterdir()],['status.json'])
 def test_cleanup_failure_and_native_failure_each_block_media(self):
  task=self.r/'task';task.mkdir();ev=task/'private';ev.mkdir()
  for native,cleanup in [('failure','SUCCEEDED'),('success','FAILED')]:
   out=task/(native+cleanup);(task/'player-control.json').write_text(json.dumps(self.control(privateCleanup=cleanup)))
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
  (task/'player-control.json').write_text(json.dumps(self.control()))
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
 def test_fixed_control_is_host_readable_under_private_umask(self):
  task=self.r/'task';task.mkdir();ev=task/'private';ev.mkdir(mode=0o700);private=task/'unexported.log';private.write_text('PRIVATE')
  os.chmod(private,0o600);old=os.umask(0o077)
  try:
   with patch.object(p,'TASK',task),patch.object(p,'EVIDENCE',ev):p.fixed_control(['SUCCEEDED','FAILED','NOT_ATTEMPTED','SUCCEEDED','SUCCEEDED'])
  finally:os.umask(old)
  self.assertEqual((task/'player-control.json').stat().st_mode & 0o777,0o644)
  self.assertEqual(ev.stat().st_mode & 0o777,0o700);self.assertEqual(private.stat().st_mode & 0o777,0o600)
 def test_compile_before_method_entered_preserves_safe_code(self):
  task=self.r/'task';project=task/'unity';cs=project/'Assets/DesertRV/Editor/PublicBuild.cs';cs.parent.mkdir(parents=True);cs.write_text('source')
  logs=self.r/'logs';logs.mkdir();(logs/'editor.log').write_text('Assets/DesertRV/Editor/PublicBuild.cs(3,4): error CS0246: PRIVATE_CANARY\n')
  ev=task/'evidence'
  with patch.object(p,'TASK',task),patch.object(p,'EVIDENCE',ev):p.record_build(logs)
  result=json.loads((ev/'build-diagnostic.json').read_text());self.assertEqual(result['native']['stage'],'NOT_OBSERVED');self.assertEqual(result['failureCode'],'PROJECT_COMPILE_ERRORS');self.assertEqual(result['logClassification']['compilerDiagnostics'],[{'code':'CS0246','sourceBasename':'PublicBuild.cs'}]);self.assertNotIn('PRIVATE_CANARY',json.dumps(result))
 def test_real_unsupported_and_failed_build_report_are_distinct(self):
  task=self.r/'task';task.mkdir();logs=self.r/'logs';logs.mkdir();ev=task/'evidence'
  native=p.empty_build_native();native.update(stage='TARGET_CHECKED',targetChecked=True,targetSupported=False,exceptionKind='INVALID_OPERATION')
  (logs/'build-diagnostic-native.json').write_text(json.dumps(native))
  with patch.object(p,'TASK',task),patch.object(p,'EVIDENCE',ev):p.record_build(logs)
  self.assertEqual(json.loads((ev/'build-diagnostic.json').read_text())['failureCode'],'LINUX_TARGET_UNSUPPORTED')
  native.update(stage='BUILD_PLAYER_RETURNED',targetSupported=True,buildReportAvailable=True,buildResult='FAILED',totalErrors=3,totalWarnings=7,settingsRestored=True)
  (logs/'build-diagnostic-native.json').write_text(json.dumps(native))
  with patch.object(p,'TASK',task),patch.object(p,'EVIDENCE',ev):p.record_build(logs)
  result=json.loads((ev/'build-diagnostic.json').read_text());self.assertEqual(result['failureCode'],'REFERENCE_BUILD_FAILED');self.assertEqual(result['native']['totalErrors'],3)
 def test_source_mismatch_still_exports_fixed_failure_only(self):
  task=self.r/'task';task.mkdir();ev=task/'private';ev.mkdir();(task/'player-control.json').write_text(json.dumps(self.control(player='FAILED')))
  with patch.object(p,'TASK',task),patch.object(p,'PUBLIC',task/'public'),patch.object(p,'EVIDENCE',ev),patch.object(p,'source_unchanged',side_effect=ValueError()),patch.dict(os.environ,{'NATIVE_OUTCOME':'failure','GITHUB_OUTPUT':str(task/'output')}):p.export()
  result=json.loads((task/'public/status.json').read_text());self.assertFalse(result['sourcePreserved']);self.assertEqual(result['failureCode'],'SOURCE_PRESERVATION_FAILED');self.assertFalse(result['videoExported'])
 def test_native_build_diagnostic_rejects_raw_exception_and_false_report(self):
  native=p.empty_build_native();native['exceptionKind']='System.Exception PRIVATE_PATH'
  with self.assertRaises(ValueError):p.validate_build_native(native)
  native=p.empty_build_native();native['totalErrors']=5
  with self.assertRaises(ValueError):p.validate_build_native(native)
 def test_build_diagnostic_recorded_before_private_removal(self):
  scripts=pathlib.Path(__file__).resolve().parent;shell=(scripts/'container_entry.sh').read_text();builder=(scripts.parents[1]/'unity/Assets/DesertRV/Editor/PlayerBuild.cs').read_text()
  self.assertIn('build-diagnostic "$private" "$build_exit"',shell);self.assertIn('export DESERTRV_PLAYER_DIAGNOSTIC=',shell)
  self.assertIn('finally\n            {\n                PersistDiagnostic(diagnostic);',builder);self.assertIn('report.summary.totalErrors',builder);self.assertIn('diagnostic.targetSupported = supported',builder)
 def test_probe_uses_compatible_atomic_replace_not_move_overwrite(self):
  runtime=pathlib.Path(__file__).resolve().parents[4]/'tasks/desert-rv/unity/Assets/DesertRV/Runtime/Diagnostics/ReferencePlayerWindowProbe.cs'
  text=runtime.read_text();self.assertNotIn('File.Move(path + ".tmp", path, true)',text)
  self.assertIn('if (File.Exists(path)) File.Replace(temporary, path, null);',text);self.assertIn('else File.Move(temporary, path);',text)
 def source_fixture(self):
  task=self.r/'task';task.mkdir();name='ProjectSettings.asset';file=self.r/name;file.write_bytes(b'before');before=p.sha(file)
  (task/'player-source-before.json').write_text(json.dumps({name:before,'outside.txt':'d'*64}))
  (task/'SOURCE-STATE.json').write_text(json.dumps({'schema':'desert-rv-source-state/v1','files':[{'path':name,'sha256':before}]}))
  return task,name,file,before
 def test_source_diagnostic_reports_only_declared_path_and_hash_difference(self):
  task,name,file,before=self.source_fixture();file.write_bytes(b'after PRIVATE_CONTENT')
  with patch.object(p,'TASK',task),patch.object(p,'tracked_names',return_value=[name,'outside.txt']):result=p.source_diagnostic()
  self.assertEqual(result['status'],'DIFFERENCES');self.assertEqual(result['files'],[dict(path=name,status='CHANGED',beforeSha256=before,afterSha256=p.sha(file))]);self.assertNotIn('PRIVATE_CONTENT',json.dumps(result));self.assertNotIn('outside.txt',json.dumps(result))
 def test_source_diagnostic_distinguishes_missing_and_unreadable(self):
  task,name,file,before=self.source_fixture()
  with patch.object(p,'TASK',task),patch.object(p,'tracked_names',return_value=[name,'outside.txt']),patch.object(p,'sha',side_effect=PermissionError()):result=p.source_diagnostic()
  self.assertEqual(result['files'][0]['status'],'UNREADABLE');self.assertIsNone(result['files'][0]['afterSha256'])
  file.unlink()
  with patch.object(p,'TASK',task),patch.object(p,'tracked_names',return_value=[name,'outside.txt']):result=p.source_diagnostic()
  self.assertEqual(result['files'][0]['status'],'MISSING')
 def test_source_diagnostic_rejects_non_declared_names_and_raw_bytes(self):
  task,name,file,before=self.source_fixture();value=dict(scope='SOURCE_STATE_DECLARED_FILES_ONLY',status='DIFFERENCES',changedCount=1,truncated=False,files=[dict(path='outside.txt',status='CHANGED',beforeSha256='a'*64,afterSha256='b'*64)])
  with patch.object(p,'TASK',task),patch.object(p,'tracked_names',return_value=[name,'outside.txt']):
   with self.assertRaises(ValueError):p.validate_source(value)
   value['files'][0]['path']=name;value['files'][0]['raw']='private'
   with self.assertRaises(ValueError):p.validate_source(value)
 def test_record_build_then_capture_init_reuses_only_valid_diagnostic(self):
  task=self.r/'task';task.mkdir();logs=self.r/'logs';logs.mkdir();ev=task/'evidence'
  native=self.control()['buildDiagnostic']['native'];(logs/'build-diagnostic-native.json').write_text(json.dumps(native))
  with patch.object(p,'TASK',task),patch.object(p,'EVIDENCE',ev):
   p.record_build(logs,0);(ev/'source-recovery.json').write_text(json.dumps(self.recovery()));self.assertEqual(p.prepare_capture_evidence(),ev)
   self.assertEqual({x.name for x in ev.iterdir()},{'build-diagnostic.json','source-recovery.json'})
   (ev/'real-time.mp4').write_bytes(b'stale')
   with self.assertRaises(ValueError):p.prepare_capture_evidence()
 def test_capture_init_rejects_symlink_or_failed_build(self):
  task=self.r/'task';task.mkdir();ev=task/'evidence';ev.mkdir();(ev/'build-diagnostic.json').write_text(json.dumps(p.empty_build()))
  with patch.object(p,'TASK',task),patch.object(p,'EVIDENCE',ev):
   with self.assertRaises(ValueError):p.prepare_capture_evidence()
  link=task/'linked';link.symlink_to(ev,target_is_directory=True)
  with patch.object(p,'EVIDENCE',link):
   with self.assertRaises(ValueError):p.prepare_capture_evidence()
 def test_real_batch_exit_and_timeout_are_not_inferred_from_elapsed_time(self):
  task=self.r/'task';task.mkdir();logs=self.r/'logs';logs.mkdir();ev=task/'evidence'
  for code in (0,1,124,137,143):
   with patch.object(p,'TASK',task),patch.object(p,'EVIDENCE',ev):p.record_build(logs,code)
   result=json.loads((ev/'build-diagnostic.json').read_text());self.assertEqual(result['batchExitCode'],code);self.assertEqual(result['batchTimedOut'],code==124)
 def recovery_fixture(self):
  task=self.r/'tasks/desert-rv';task.mkdir(exist_ok=True);logs=self.r/'logs';logs.mkdir()
  text='  productName: ORIGINAL\n  defaultScreenWidth: 1280\n  defaultScreenHeight: 720\n  resizableWindow: 1\n  fullscreenMode: 3\n  scriptingBackend:\n    Standalone: 0\n'
  before={}
  for name in p.RECOVERY_PATHS:
   file=self.r/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text(text if name==p.SETTINGS_PATH else 'unchanged public source');os.chmod(file,0o644);before[name]=p.sha(file)
  (task/'player-source-before.json').write_text(json.dumps(before));(task/'SOURCE-STATE.json').write_text(json.dumps({'schema':'desert-rv-source-state/v1','files':[dict(path=n,sha256=v) for n,v in before.items()]}))
  return task,logs,before
 def test_exact_settings_backup_restores_bytes_and_four_original_modes(self):
  task,logs,before=self.recovery_fixture();ev=task/'evidence'
  with patch.object(p,'TASK',task),patch.object(p,'EVIDENCE',ev),patch.object(p,'tracked_names',return_value=list(p.RECOVERY_PATHS)):
   p.snapshot_recovery(logs);file=self.r/p.SETTINGS_PATH;file.write_text(file.read_text().replace('ORIGINAL','PRIVATE_DIAGNOSTIC_VALUE').replace('resizableWindow: 1','resizableWindow: 0'))
   for name in p.RECOVERY_PATHS:os.chmod(self.r/name,0o600)
   self.assertEqual(p.recover_source(logs),0);result=json.loads((ev/'source-recovery.json').read_text())
  self.assertEqual(result['before']['status'],'DIFFERENCES');self.assertEqual(result['settingsDiff']['classification'],'OWNED_FIELDS_ONLY');self.assertTrue(result['settingsBackupRestored']);self.assertNotIn('PRIVATE_DIAGNOSTIC_VALUE',json.dumps(result))
  for name in p.RECOVERY_PATHS:self.assertEqual(p.sha(self.r/name),before[name]);self.assertEqual((self.r/name).stat().st_mode&0o777,0o644)
 def test_recovery_never_restores_other_source_bytes(self):
  task,logs,before=self.recovery_fixture();ev=task/'evidence'
  with patch.object(p,'TASK',task),patch.object(p,'EVIDENCE',ev),patch.object(p,'tracked_names',return_value=list(p.RECOVERY_PATHS)):
   p.snapshot_recovery(logs);file=self.r/p.RECOVERY_PATHS[0];file.write_text('OTHER_CHANGED');self.assertEqual(p.recover_source(logs),1)
  self.assertEqual(file.read_text(),'OTHER_CHANGED');self.assertEqual(json.loads((ev/'source-recovery.json').read_text())['status'],'FAILED')
 def test_unknown_settings_changes_are_classified_without_raw_content(self):
  task,logs,before=self.recovery_fixture();original=(self.r/p.SETTINGS_PATH).read_bytes();result=p.settings_diff(original,original+b'  privateUnlistedKey: SECRET\n')
  self.assertEqual(result['classification'],'OTHER_SETTINGS_CHANGE');self.assertGreater(result['unknownLineCount'],0);self.assertNotIn('SECRET',json.dumps(result));self.assertEqual(p.settings_diff(original,b'not yaml')['classification'],'UNAVAILABLE')
 def test_recovery_backup_must_match_source_declared_bytes(self):
  task,logs,before=self.recovery_fixture();ev=task/'evidence'
  with patch.object(p,'TASK',task),patch.object(p,'EVIDENCE',ev),patch.object(p,'tracked_names',return_value=list(p.RECOVERY_PATHS)):
   p.snapshot_recovery(logs);(logs/'ProjectSettings.original').write_text('TAMPERED');self.assertEqual(p.recover_source(logs),1)
  self.assertEqual(p.sha(self.r/p.SETTINGS_PATH),before[p.SETTINGS_PATH])
 def test_bounded_build_and_atomic_phase_source_contracts(self):
  root=pathlib.Path(__file__).resolve().parents[4];shell=(root/'tasks/desert-rv/scripts/player/container_entry.sh').read_text();builder=(root/'tasks/desert-rv/unity/Assets/DesertRV/Editor/PlayerBuild.cs').read_text();workflow=(root/'.github/workflows/desert-rv-player-smoke.yml').read_text()
  self.assertIn('65m unity-editor',shell);self.assertIn('else\n  build_exit=$?;',shell);self.assertIn('timeout-minutes: 100',workflow)
  self.assertLess(shell.index('snapshot-recovery'),shell.index('65m unity-editor'));self.assertLess(shell.index('build-diagnostic "$private" "$build_exit"'),shell.index('recover-source "$private"'))
  self.assertIn('if (File.Exists(destination)) File.Replace(temporary, destination, null);',builder)
  for stage in ('TARGET_CHECKED','SCENE_VALIDATED','BUILD_PLAYER_ENTERED','BUILD_RECEIPT_WRITTEN'):self.assertIn('diagnostic.stage = "'+stage+'"; PersistDiagnostic(diagnostic);',builder)
 def test_shell_preserves_batch_exit_before_any_later_command(self):
  import subprocess
  shell=(pathlib.Path(__file__).resolve().parent/'container_entry.sh').read_text();start=shell.index('if timeout --signal=TERM --kill-after=30s 65m unity-editor');end=shell.index('\nfi',start)+3;fragment=shell[start:end]
  with tempfile.TemporaryDirectory() as private:
   for code in (0,1,124,137):
    script='set -e\ntimeout() { return '+str(code)+'; }\nprivate='+private+'\n'+fragment+'\nprintf "%s %s" "$build_exit" "$built"\n'
    result=subprocess.run(['bash','-c',script],capture_output=True,text=True)
    self.assertEqual(result.returncode,0);self.assertEqual(result.stdout,str(code)+(' SUCCEEDED' if code==0 else ' FAILED'))
 def test_source_guards_runtime_and_batch_only(self):
  root=pathlib.Path(__file__).resolve().parents[4];base=root/'tasks/desert-rv';shell=(base/'scripts/player/container_entry.sh').read_text();cs=(base/'unity/Assets/DesertRV/Runtime/Diagnostics/ReferencePlayerWindowProbe.cs').read_text();builder=(base/'unity/Assets/DesertRV/Editor/PlayerBuild.cs').read_text()
  self.assertTrue(cs.startswith('#if DESERTRV_REFERENCE_WINDOW_PROBE && !UNITY_EDITOR'))
  for forbidden in ['SessionState','JourneyDirector','Input.','transform.position','Time.timeScale']:self.assertNotIn(forbidden,cs)
  self.assertIn('now - begin >= 15',cs);self.assertIn('IsBuildTargetSupported',builder);self.assertIn('File.WriteAllBytes(settingsPath, originalSettings)',builder)
  self.assertIn('unity-editor -projectPath',shell);self.assertNotIn('/opt/unity/Editor/Unity',shell);self.assertIn('env -u UNITY_LICENSE -u UNITY_EMAIL -u UNITY_PASSWORD -u UNITY_SERIAL',shell)
if __name__=='__main__':unittest.main()
