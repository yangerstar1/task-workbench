#!/usr/bin/env python3
"""Synthetic byte fixtures only: never launch an executable or invoke Unity/authentication."""
import json,os,pathlib,tempfile,unittest
from unittest.mock import patch
import journey_linux_export as x
class JourneyLinuxExportTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.t.name);self.build=self.root/'build';self.build.mkdir()
  for name in ['DesertRV.x86_64','UnityPlayer.so','DesertRV_Data/Managed/Assembly-CSharp.dll','MonoBleedingEdge/EmbedRuntime/libmonobdwgc-2.0.so']:
   p=self.build/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'SYNTHETIC_NOT_EXECUTABLE_'+name.encode())
  self.env=patch.dict(os.environ,{'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'123'});self.env.start()
 def tearDown(self):self.env.stop();self.t.cleanup()
 def receipt(self):
  return dict(schema=1,label=x.MODE,sourceCommit='a'*40,producerRunUrl=x.producer_url(),generatedReceiptSha256='b'*64,requestSha256='c'*64,executableSha256=x.sha(self.build/'DesertRV.x86_64'),unityVersion='6000.3.19f1',target='StandaloneLinux64',backend='Mono2x',define='DESERTRV_CANDIDATE_LINUX',executable='DesertRV.x86_64',scenes=x.SCENES,candidateOnly=True,development=True,settingsRestored=True,sourceBytesUnchanged=True,approved=False,visualReviewed=False,gameplayReviewed=False,audioAuditioned=False,temporarySettingsFiles=['ProjectSettings/ProjectSettings.asset'],boundaryNativeXmlSha256='d'*64,boundaryNativeCases=17,temporarySettingsApiFields=['scriptingBackend.Standalone','fullScreenMode','defaultScreenWidth','defaultScreenHeight','productName','resizableWindow'])
 def control(self):
  recovery=x.recovery.empty_recovery();recovery.update(status='SUCCEEDED',sourceModesRestored=True,afterPreserved=True)
  return dict(schema=1,mode='JOURNEY_LINUX_BUILD_CONTROL',activation='SUCCEEDED',build='SUCCEEDED',licenseReturn='SUCCEEDED',privateCleanup='SUCCEEDED',buildDiagnostic=dict(batchExitCode=0,batchTimedOut=False,native=self.diagnostic(),logClassification=x.recovery.startup.empty_report()),sourceRecovery=recovery)
 def diagnostic(self):
  return dict(schema=1,label='CANDIDATE_LINUX_BUILD_DIAGNOSTIC',stage='RECEIPT_WRITTEN',exceptionKind='NONE',buildResult='SUCCEEDED',settingsRestored=True,sourceBytesUnchanged=True,receiptWritten=True)
 def success_fixture(self):
  from contextlib import ExitStack
  task=self.root/'task';task.mkdir();state=task/'state';state.mkdir();generated=task/'journey-preparation-export/generated';generated.mkdir(parents=True);(generated/'receipt.json').write_text('{}');(task/'SOURCE-STATE.json').write_text('{}')
  r=dict(schema=1,label='CANDIDATE_LINUX_DEVELOPMENT_ONLY',sourceCommit='a'*40,producerRunUrl=x.producer_url(),approved=False,generatedReceiptSha256=x.sha(generated/'receipt.json'),boundaryNativeXmlSha256='d'*64,boundaryNativeCases=17)
  (state/'linux-build-input.json').write_text(json.dumps(r));(state/'linux-build-input.sha256').write_text(x.sha(state/'linux-build-input.json'))
  receipt=self.receipt();receipt.update(requestSha256=x.sha(state/'linux-build-input.json'),generatedReceiptSha256=r['generatedReceiptSha256'])
  raw=(json.dumps(receipt,indent=4)+'\n').encode();(state/'linux-build-receipt.json').write_bytes(raw);(state/'linux-build-diagnostic.json').write_text(json.dumps(self.diagnostic()));(task/'control.json').write_text(json.dumps(self.control()))
  stack=ExitStack();self.addCleanup(stack.close)
  for k,v in dict(TASK=task,STATE=state,BUILD=self.build,STAGED=task/'staged',PUBLIC=task/'public',CONTROL=task/'control.json').items():stack.enter_context(patch.object(x,k,v))
  stack.enter_context(patch.object(x,'verify_union',return_value={}));stack.enter_context(patch.dict(os.environ,{'NATIVE_OUTCOME':'success','UNION_OUTCOME':'success','GITHUB_OUTPUT':str(task/'gh')}))
  return task,raw
 def test_success_preserves_receipt_bytes_and_verifiable_runtime(self):
  task,raw=self.success_fixture();x.stage();x.export();public=task/'public'
  self.assertEqual({p.name for p in public.iterdir()},{'manifest.json','control.json','native-build-receipt.json','player.tar.gz'})
  m=json.loads((public/'manifest.json').read_text());self.assertEqual((public/'native-build-receipt.json').read_bytes(),raw);self.assertEqual(x.sha(public/'native-build-receipt.json'),m['nativeReceiptSha256']);x.verify_tar(public/'player.tar.gz',m['files']);self.assertFalse(m['playerExecuted'])
 def test_failed_native_diagnostic_cannot_stage_stale_receipt(self):
  task,_=self.success_fixture();d=self.diagnostic();d['exceptionKind']='IO';(task/'state/linux-build-diagnostic.json').write_text(json.dumps(d))
  with self.assertRaises(ValueError):x.stage()
  self.assertFalse((task/'staged').exists())
 def test_tampered_staged_archive_leaves_no_public_directory(self):
  task,_=self.success_fixture();x.stage();(task/'staged/player.tar.gz').write_bytes(b'TAMPERED')
  with self.assertRaises(ValueError):x.export()
  self.assertFalse((task/'public').exists())
 def test_success_labels_with_nonzero_batch_exit_only_export_failure(self):
  task,_=self.success_fixture();x.stage();c=self.control();c['buildDiagnostic']['batchExitCode']=1;(task/'control.json').write_text(json.dumps(c));x.export()
  self.assertEqual({p.name for p in (task/'public').iterdir()},{'status.json'})
 def test_raw_receipt_duplicate_key_cannot_export_hidden_value(self):
  task,_=self.success_fixture();p=task/'state/linux-build-receipt.json';raw=p.read_text();p.write_text(raw.replace('"label":', '"label":"PRIVATE_HIDDEN", "label":',1))
  with self.assertRaises(ValueError):x.stage()
  self.assertFalse((task/'staged').exists())
 def test_runtime_file_root_cannot_be_directory(self):
  (self.build/'UnityPlayer.so').unlink();(self.build/'UnityPlayer.so').mkdir();(self.build/'UnityPlayer.so/nested').write_bytes(b'x')
  with self.assertRaises(ValueError):x.inventory(self.build)
 def test_closed_runtime_roundtrip_and_normalized_metadata(self):
  records=x.inventory(self.build);bundle=self.root/'player.tar.gz';x.tar_bundle(self.build,records,bundle);x.verify_tar(bundle,records);self.assertEqual(len(records),4)
 def test_binary_tamper_rejected_before_packaging(self):
  records=x.inventory(self.build);(self.build/'UnityPlayer.so').write_text('changed')
  with self.assertRaises(ValueError):x.tar_bundle(self.build,records,self.root/'bad.tar.gz')
 def test_unknown_top_level_and_private_log_rejected(self):
  bad=self.build/'activation.log';bad.write_text('PRIVATE')
  with self.assertRaises(ValueError):x.inventory(self.build)
  bad.unlink();(self.build/'DesertRV_Data/secret.ulf').write_text('PRIVATE')
  with self.assertRaises(ValueError):x.inventory(self.build)
 def test_symlink_rejected_and_debug_symbols_not_exported(self):
  link=self.build/'DesertRV_Data/linked';link.symlink_to(self.build/'UnityPlayer.so')
  with self.assertRaises(ValueError):x.inventory(self.build)
  link.unlink();(self.build/'DesertRV_Data/Managed/symbols.pdb').write_text('DEBUG_PRIVATE')
  debug=self.build/'DesertRV_BackUpThisFolder_ButDontShipItWithYourGame';debug.mkdir();(debug/'debug.txt').write_text('DEBUG_PRIVATE')
  self.assertEqual(len(x.inventory(self.build)),4)
 def test_missing_mono_runtime_fails_closed(self):
  import shutil
  shutil.rmtree(self.build/'MonoBleedingEdge')
  with self.assertRaises(ValueError):x.inventory(self.build)
 def test_archive_record_traversal_and_arbitrary_modes_rejected(self):
  records=x.inventory(self.build);records[0]['path']='../private'
  with self.assertRaises(ValueError):x.validate_records(records)
  records=x.inventory(self.build);records[0]['mode']=0o777
  with self.assertRaises(ValueError):x.validate_records(records)
 def test_receipt_requires_exact_candidate_profile_and_all_unreviewed_flags(self):
  self.assertEqual(x.native_receipt(self.receipt())['backend'],'Mono2x')
  for key,value in [('approved',True),('define','OTHER'),('scenes',x.SCENES[:1]),('temporarySettingsFiles',['ProjectSettings/EditorBuildSettings.asset'])]:
   r=self.receipt();r[key]=value
   with self.assertRaises(ValueError):x.native_receipt(r)
 def test_receipt_rejects_raw_values_or_missing_request_hash(self):
  r=self.receipt();r['rawLog']='secret'
  with self.assertRaises(ValueError):x.native_receipt(r)
  r=self.receipt();r.pop('requestSha256')
  with self.assertRaises(ValueError):x.native_receipt(r)
 def test_cleanup_native_or_union_failure_never_exports_player(self):
  for native,union,cleanup in [('failure','success','SUCCEEDED'),('success','failure','SUCCEEDED'),('success','success','FAILED')]:
   task=self.root/(native+union+cleanup);task.mkdir();control=self.control();control['privateCleanup']=cleanup;(task/'control.json').write_text(json.dumps(control));output=task/'public'
   with patch.object(x,'TASK',task),patch.object(x,'CONTROL',task/'control.json'),patch.object(x,'PUBLIC',output),patch.dict(os.environ,{'NATIVE_OUTCOME':native,'UNION_OUTCOME':union,'GITHUB_OUTPUT':str(task/'github-output')}):x.export()
   self.assertEqual({p.name for p in output.iterdir()},{'status.json'});self.assertFalse(json.loads((output/'status.json').read_text())['playerExported'])
 def test_bad_control_has_no_partial_public_export(self):
  control=self.root/'control.json';control.write_text('{"raw":"PRIVATE"}');output=self.root/'public'
  with patch.object(x,'TASK',self.root),patch.object(x,'CONTROL',control),patch.object(x,'PUBLIC',output):
   with self.assertRaises(ValueError):x.export()
  self.assertFalse(output.exists())
 def test_no_player_launch_and_pinned_batch_workflow(self):
  root=pathlib.Path(__file__).resolve().parents[4];shell=(root/'tasks/desert-rv/scripts/player/journey_linux_container.sh').read_text();flow=(root/'.github/workflows/desert-rv-journey-prepare.yml').read_text()
  self.assertIn('65m unity-editor',shell);self.assertIn('else\n  build_exit=$?',shell);self.assertIn('JourneyCandidateLinuxBuild.BuildPreparedLinuxDiagnostic',shell)
  self.assertNotIn('"$build/DesertRV.x86_64"',shell);self.assertNotIn('capture_game_window.py',shell);self.assertIn('GIT_CONFIG_VALUE_0=/github/workspace',shell)
  self.assertIn('linux_build_input.py prepare',flow);self.assertIn('linux_build_input.py verify',flow);self.assertNotIn('uses: ./.github/actions/desert-rv-rendered',flow);self.assertIn('UNION_OUTCOME:',flow)
  self.assertLess(shell.index('[[ ! -e "$build"'),shell.index('trap cleanup EXIT'));self.assertLess(flow.index('DesertRV.CandidateLinuxTests'),flow.index('id: author'));self.assertIn('linux_build_input.py verify-boundary',flow)
if __name__=='__main__':unittest.main()
