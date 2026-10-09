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
  return dict(restorationProof={'path':'','sha256':''},assetProducerSourceCommit='',assetProducerRunUrl='',restorationNativeXmlSha256='',schema=1,label=x.MODE,sourceCommit='a'*40,producerRunUrl=x.producer_url(),generatedReceiptSha256='b'*64,requestSha256='c'*64,executableSha256=x.sha(self.build/'DesertRV.x86_64'),unityVersion='6000.3.19f1',target='StandaloneLinux64',backend='Mono2x',define='DESERTRV_CANDIDATE_LINUX',executable='DesertRV.x86_64',scenes=x.SCENES,candidateOnly=True,development=True,detailedBuildReport=True,performanceTestResourcesExcluded=True,settingsRestored=True,sourceBytesUnchanged=True,approved=False,visualReviewed=False,gameplayReviewed=False,audioAuditioned=False,temporarySettingsFiles=['ProjectSettings/ProjectSettings.asset'],boundaryNativeXmlSha256='d'*64,boundaryNativeCases=17,temporarySettingsApiFields=['scriptingBackend.Standalone','fullScreenMode','defaultScreenWidth','defaultScreenHeight','productName','resizableWindow'])
 def control(self):
  recovery=x.recovery.empty_recovery();recovery.update(status='SUCCEEDED',sourceModesRestored=True,afterPreserved=True)
  return dict(schema=1,mode='JOURNEY_LINUX_BUILD_CONTROL',activation='SUCCEEDED',build='SUCCEEDED',licenseReturn='SUCCEEDED',privateCleanup='SUCCEEDED',buildDiagnostic=dict(batchExitCode=0,batchTimedOut=False,native=self.diagnostic(),logClassification=x.recovery.startup.empty_report()),sourceRecovery=recovery)
 def diagnostic(self):
  return dict(performanceResources=self.performance(),primaryInventory=self.inventory(),verificationInventory=self.inventory(),activeTargetAtEntry='LINUX64',activeTargetBeforeBuild='LINUX64',activeTargetAfterBuild='LINUX64',reportTarget='LINUX64',schema=1,label='CANDIDATE_LINUX_BUILD_DIAGNOSTIC',stage='RECEIPT_WRITTEN',exceptionKind='NONE',buildResult='SUCCEEDED',settingsRestored=True,sourceBytesUnchanged=True,receiptWritten=True,buildReportAvailable=True,leaseActiveAtBuildReturn=True,assemblyReloadObserved=False,totalErrors=0,totalWarnings=0,primaryFailureCode='NONE',primaryExceptionKind='NONE',restorationFailureCode='NONE',restorationExceptionKind='NONE',verificationFailureCode='NONE',verificationExceptionKind='NONE',leaseClosedReason='EXPLICIT',buildErrorKinds=[],primaryCallbackGate='NONE',primarySceneRole='NONE',verificationCallbackGate='NONE',verificationSceneRole='NONE',primaryRootMismatch=self.root_observation(),verificationRootMismatch=self.root_observation(),buildMessages=[],buildMessagesTruncated=False)
 def test_performance_source_order_profile_private_cleanup_and_report_are_explicit(self):
  source=(pathlib.Path(__file__).resolve().parents[2]/'unity/Assets/DesertRV/Editor/JourneyCandidateLinuxBuild.cs').read_text()
  begin=source.split('static InventoryObservation BeginPerformanceIsolation',1)[1].split('static string[] ExpectedPerformancePayloads',1)[0]
  self.assertLess(begin.index('PerformancePreference.Suppress()'),begin.index('RequirePerformanceInventory'))
  self.assertIn('const BuildOptions CandidateOptions = BuildOptions.Development | BuildOptions.DetailedBuildReport;',source)
  self.assertIn('options == CandidateOptions',source);self.assertIn('public int callbackOrder => 1;',source)
  self.assertIn('item.sourceAssetGUID.ToString()',source);self.assertIn('IsPerformancePacked(path,guid,observation.jsonGuids)',source)
  self.assertIn('VerifyPackedPerformanceExclusion(result,diagnostic.performanceResources,lease.processed.ToArray())',source)
  self.assertNotIn('scenes.SetEquals(Paths)',source)
  move=source.split('static void MovePerformanceFiles',1)[1].split('internal static void IsolatePerformanceResources',1)[0]
  self.assertIn('File.Copy(source,target,false)',move);self.assertIn('Directory.Delete(directory,false)',move);self.assertNotIn('Directory.Delete(directory,true)',move)
  shell=pathlib.Path(__file__).with_name('journey_linux_container.sh').read_text()
  self.assertLess(shell.index('export DESERTRV_PERFORMANCE_PRIVATE="$private"'),shell.index('65m unity-editor'))
  self.assertIn('rm -rf "$private" "$build"',shell)
 def test_exact_performance_version_uses_resolved_lock_node(self):
  root=pathlib.Path(__file__).resolve().parents[2]
  lock=json.loads((root/'unity/Packages/packages-lock.json').read_text())
  resolved=lock['dependencies']['com.unity.test-framework.performance']['version']
  requirement=lock['dependencies']['com.unity.collections']['dependencies']['com.unity.test-framework.performance']
  self.assertEqual(resolved,'3.5.0');self.assertEqual(requirement,'3.0.3');self.assertNotEqual(resolved,requirement)
  source=(root/'unity/Assets/DesertRV/Editor/JourneyCandidateLinuxBuild.cs').read_text()
  self.assertIn('const string PerformanceVersion = "'+resolved+'";',source)
  self.assertIn('Check(info.version==PerformanceVersion,"PERFORMANCE_PACKAGE_VERSION")',source)
 def test_performance_identity_observation_is_fixed_and_version_fail_closed(self):
  good=self.performance()
  for identity in ('REGISTERED_3_0_3','MISSING','NAME_MISMATCH','OTHER_VERSION','/tmp/private','3.5.1'):
   value=dict(good,packageIdentity=identity)
   with self.assertRaises(ValueError):x.performance_observation(value)
  for code in ('PERFORMANCE_PACKAGE_MISSING','PERFORMANCE_PACKAGE_NAME','PERFORMANCE_PACKAGE_VERSION','PERFORMANCE_PACKAGE_SOURCE'):
   self.assertIn(code,x.FAILURE_CODES)
 def performance(self):
  rows=[dict(path='Assets/Resources',change='ADDED',kind='DIRECTORY',sha256='',bytes=0,measurement='NOT_APPLICABLE')]+[dict(path=p,change='ADDED',kind='FILE',sha256='e'*64,bytes=23,measurement='ACTUAL_BYTES') for p in x.PERFORMANCE_FILES]
  return dict(status='PACKED_VERIFIED',packageIdentity='REGISTERED_3_5_0',packageVerified=True,baselineAbsent=True,preferenceRestored=True,synchronousImportCompleted=True,exactInventoryRestored=True,packedReportAvailable=True,packedContainers=4,packedObjects=100,packedSourceObjects=80,packedJsonHits=0,packedScenePaths=[],callbackScenePaths=sorted(x.SCENES),jsonGuids=['a'*32,'b'*32],generated=dict(observed=True,truncated=False,totalChanges=6,addedFiles=5,removedFiles=0,addedDirectories=1,removedDirectories=0,unsafePathsOmitted=0,entries=sorted(rows,key=lambda r:r['path'])))
 def test_performance_proof_requires_real_report_coverage_and_exact_closure(self):
  import copy
  good=self.performance();x.performance_observation(good);self.assertTrue(x.performance_success(good))
  for change in [dict(packedObjects=0),dict(callbackScenePaths=[]),dict(callbackScenePaths=sorted(x.SCENES)[:3]),dict(packedSourceObjects=0),dict(packedJsonHits=1),dict(packedReportAvailable=False),dict(jsonGuids=['a'*32,'a'*32]),dict(status='RAW_PRIVATE_PAYLOAD'),dict(privatePath='/tmp/private')]:
   value=copy.deepcopy(good);value.update(change)
   with self.assertRaises(ValueError):x.performance_observation(value)
  for change in [dict(path='Assets/Resources/Unknown.json'),dict(sha256='SECRET'),dict(bytes=65537)]:
   value=copy.deepcopy(good);value['generated']['entries'][2].update(change)
   with self.assertRaises(ValueError):x.performance_observation(value)
  value=copy.deepcopy(good);value['preferenceRestored']=False;x.performance_observation(value);self.assertFalse(x.performance_success(value))
 def test_performance_proof_unavailable_is_not_exclusion(self):
  value=dict(status='NOT_ARMED',packageIdentity='NOT_OBSERVED',packageVerified=False,baselineAbsent=False,preferenceRestored=False,synchronousImportCompleted=False,exactInventoryRestored=False,packedReportAvailable=False,packedContainers=0,packedObjects=0,packedSourceObjects=0,packedJsonHits=0,packedScenePaths=[],callbackScenePaths=[],jsonGuids=[],generated=self.inventory())
  x.performance_observation(value);self.assertFalse(x.performance_success(value))
 def inventory(self):return dict(observed=False,truncated=False,totalChanges=0,addedFiles=0,removedFiles=0,addedDirectories=0,removedDirectories=0,unsafePathsOmitted=0,entries=[])
 def inventory_change(self):
  d=self.inventory();d.update(observed=True,totalChanges=3,addedFiles=1,removedFiles=1,addedDirectories=1,entries=[dict(path='Assets/Generated',kind='DIRECTORY',change='ADDED',sha256='',bytes=0,measurement='NOT_APPLICABLE'),dict(path='Assets/Old.asset',kind='FILE',change='REMOVED',sha256='a'*64,bytes=15,measurement='EXPECTED_PIN_PRIOR_SIZE'),dict(path='ProjectSettings/Generated.asset',kind='FILE',change='ADDED',sha256='b'*64,bytes=19,measurement='ACTUAL_BYTES')]);return d
 def test_inventory_delta_has_exact_sorted_paths_hashes_sizes_and_independent_phases(self):
  d=self.diagnostic();d['primaryInventory']=self.inventory_change();d['primaryFailureCode']='INVENTORY_SET';d['primaryExceptionKind']='BUILD_FAILED';x.native_diagnostic(d);self.assertFalse(x.diagnostic_success(d));self.assertFalse(d['verificationInventory']['observed'])
 def test_inventory_private_path_traversal_unknown_fields_hash_size_rejected(self):
  for key,value in [('path','/private/log'),('path','Assets/../private.log'),('path','Assets/foo\nPRIVATE'),('sha256','TOKEN'),('bytes',True),('raw','SECRET')]:
   d=self.inventory_change();d['entries'][2][key]=value
   with self.assertRaises(ValueError):x.inventory_observation(d)
 def test_inventory_missing_duplicate_unsorted_and_wrong_counts_rejected(self):
  d=self.inventory_change();d['entries'].pop()
  with self.assertRaises(ValueError):x.inventory_observation(d)
  d=self.inventory_change();d['entries'][1]=d['entries'][0]
  with self.assertRaises(ValueError):x.inventory_observation(d)
  d=self.inventory_change();d['entries'].reverse()
  with self.assertRaises(ValueError):x.inventory_observation(d)
  d=self.inventory_change();d['addedFiles']=2
  with self.assertRaises(ValueError):x.inventory_observation(d)
 def test_inventory_truncation_and_unavailable_measurements_are_explicit(self):
  d=self.inventory_change();d['entries']=d['entries'][:1];d['truncated']=True;x.inventory_observation(d)
  d=self.inventory_change();d['entries'][1].update(bytes=-1,measurement='EXPECTED_PIN_SIZE_UNAVAILABLE');x.inventory_observation(d)
  d=self.inventory_change();d['entries'][2].update(bytes=129*1024**2,sha256='',measurement='SIZE_ONLY_LIMIT');x.inventory_observation(d)
  d['entries'][2].update(bytes=-1,measurement='UNREADABLE');x.inventory_observation(d)
 def root_observation(self):return dict(observed=False,rootBytesMatch=False,rootDependencyBytesMatch=False,slot='NONE',expectedImportHash='',observedImportHash='')
 def test_primary_and_secondary_diagnostic_reasons_remain_distinct(self):
  d=self.diagnostic();d.update(stage='BUILD_PLAYER_RETURNED',buildResult='FAILED',totalErrors=2,exceptionKind='BUILD_FAILED',primaryFailureCode='ROOT_IMPORT_HASH',primaryExceptionKind='BUILD_FAILED',verificationFailureCode='IMPORT_FINGERPRINT',verificationExceptionKind='BUILD_FAILED',sourceBytesUnchanged=False,receiptWritten=False)
  d['primaryRootMismatch'].update(observed=True,slot='BOOTSTRAP',expectedImportHash='a'*32,observedImportHash='b'*32,rootBytesMatch=True,rootDependencyBytesMatch=True)
  self.assertEqual(x.native_diagnostic(d)['primaryFailureCode'],'ROOT_IMPORT_HASH');self.assertFalse(x.diagnostic_success(d))
 def test_diagnostic_rejects_raw_error_text_secrets_and_private_paths(self):
  base=dict(category='CANDIDATE_GATE',code='ROOT_IMPORT_HASH',source='',line=0,text='Candidate build gate rejected: ROOT_IMPORT_HASH')
  x.safe_build_message(base)
  for key,value in [('text','token=SECRET'),('text','x'*10000),('source','/home/private/name.cs'),('code','UNLISTED'),('line',True)]:
   m=dict(base);m[key]=value
   with self.assertRaises(ValueError):x.safe_build_message(m)
 def test_compiler_message_requires_actual_public_source_and_exact_reconstruction(self):
  sources=x.recovery.startup.source_map(x.PROJECT);source=next(iter(sources));m=dict(category='CS_COMPILATION',code='CS1501',source=source,line=12,text='C# compiler diagnostic: CS1501 at '+source+':12');x.safe_build_message(m)
  for code,source_value in [('CS9999',source),('CS1501','Assets/DesertRV/PRIVATE_SECRET.cs')]:
   n=dict(m,code=code,source=source_value)
   with self.assertRaises(ValueError):x.safe_build_message(n)
 def test_diagnostic_counts_null_report_and_unknown_fields_fail_closed(self):
  for key,value in [('totalErrors',-1),('totalWarnings',True),('buildReportAvailable',False),('rawError','SECRET'),('primaryCallbackGate','ARBITRARY'),('activeTargetBeforeBuild','/private/path')]:
   d=self.diagnostic();d[key]=value
   with self.assertRaises(ValueError):x.native_diagnostic(d)
 def test_root_hash_diagnostic_and_schema_cannot_export_private_fields(self):
  d=self.diagnostic();d['primaryRootMismatch'].update(observed=True,slot='BOOTSTRAP',expectedImportHash='a'*32,observedImportHash='b'*32,rootBytesMatch=True,rootDependencyBytesMatch=True);x.native_diagnostic(d)
  for key,value in [('slot','/home/private'),('expectedImportHash','TOKEN'),('raw','SECRET')]:
   n=dict(d);n['primaryRootMismatch']=dict(d['primaryRootMismatch']);n['primaryRootMismatch'][key]=value
   with self.assertRaises(ValueError):x.native_diagnostic(n)
 def test_nonzero_build_errors_or_recorded_failure_cannot_stage_success(self):
  for key,value in [('totalErrors',1),('primaryFailureCode','ROOT_IMPORT_HASH')]:
   d=self.diagnostic();d[key]=value;self.assertFalse(x.diagnostic_success(d))
 def test_restoration_provenance_exact_shape_and_input_binding(self):
  n=self.receipt();n.update(restorationProof=dict(path='tasks/desert-rv/unity/JourneyEvidence/JourneyPreparation/restoration-revalidated.json',sha256='e'*64),assetProducerSourceCommit='f'*40,assetProducerRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/456',restorationNativeXmlSha256='d'*64);x.native_receipt(n);x.restoration_matches(n,n)
  bad=dict(n);bad['assetProducerSourceCommit']='a'*40
  with self.assertRaises(ValueError):x.restoration_matches(n,bad)
  n['restorationProof']['path']='../foreign.json'
  with self.assertRaises(ValueError):x.native_receipt(n)
 def test_csharp_failure_code_contract_and_primary_before_finally(self):
  import re
  root=pathlib.Path(__file__).resolve().parents[4];cs=(root/'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneyCandidateLinuxBuild.cs').read_text();part=cs.split('static readonly HashSet<string> FailureCodes')[1].split('static Lease active')[0]
  self.assertEqual(set(re.findall(r'"([A-Z_]+)"',part)),x.FAILURE_CODES)
  self.assertIn('Report(result,diagnostic)',cs);self.assertIn('diagnostic.stage="BUILD_PLAYER_RETURNED"',cs);self.assertIn('diagnostic.primaryFailureCode == "NONE"',cs);self.assertIn('diagnostic.verificationFailureCode == "NONE"',cs)
  self.assertLess(cs.index('RememberFailure(diagnostic,"PRIMARY","UNCLASSIFIED_EXCEPTION"'),cs.index('Close();diagnosticContext="RESTORATION"'))
  self.assertIn('DtdProcessing=DtdProcessing.Prohibit',cs);self.assertIn('DesertRV.Tests.JourneyRestorationTests.RevalidatePinnedRestoredJourney',cs)
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
