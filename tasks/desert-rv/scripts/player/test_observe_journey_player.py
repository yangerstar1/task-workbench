#!/usr/bin/env python3
"""Synthetic archives and source contracts only; no Unity, player or network."""
import copy,io,json,os,pathlib,tarfile,tempfile,unittest,zipfile,shutil
from unittest.mock import patch
import observe_journey_player as o
import test_journey_linux_export as fixture
class ObserveTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.JourneyLinuxExportTests();self.f.setUp();self.addCleanup(self.f.tearDown);self.addCleanup(self.f.doCleanups)
  self.task,self.raw=self.f.success_fixture();fixture.x.stage();fixture.x.export();self.package=self.task/'public';self.root=self.f.root
  self.p=dict(PRODUCER_RUN_ID='123',PRODUCER_COMMIT='a'*40,PRODUCER_ARTIFACT_ID='456',PRODUCER_ZIP_SHA256='c'*64)
  # The main exporter stays unchanged. Adapt only this synthetic consumer package
  # to the recovery producer's exact additional control field.
  control=json.loads((self.package/'control.json').read_text());host=o.bundle.empty_host()
  host.update(lastPhase='STAGED',completedPhases=['PREFLIGHT','RECORD','STAGE','STAGED'],
              nativeReceiptPin=dict(sha256=o.sha(self.package/'native-build-receipt.json'),bytes=len(self.raw)))
  records=json.loads((self.package/'manifest.json').read_text())['files']
  rows=[dict(path=r['path'],kind='FILE',mode=r['mode'],bytes=r['size'],sha256=r['sha256']) for r in records]
  host['runtime']=dict(observed=True,totalEntries=len(rows),omittedEntries=0,entries=rows)
  control['hostDiagnostic']=host;(self.package/'control.json').write_text(json.dumps(control));self.control_fixture=copy.deepcopy(control)
 def control(self):return json.loads((self.package/'control.json').read_text())
 def write_control(self,value):(self.package/'control.json').write_text(json.dumps(value))
 def reject_control(self,value):
  self.write_control(value)
  with self.assertRaises(ValueError):o.validate_package(self.package,self.p)
 def test_recovery_control_schema_and_exact_receipt_pin_accepted(self):
  control=self.control();self.assertEqual(set(control),{'schema','mode','activation','build','licenseReturn','privateCleanup','buildDiagnostic','sourceRecovery','hostDiagnostic'})
  self.assertEqual(control['hostDiagnostic'],o.bundle.validate_host(control['hostDiagnostic']))
  self.assertEqual(o.validate_package(self.package,self.p)['nativeReceiptSha256'],control['hostDiagnostic']['nativeReceiptPin']['sha256'])
 def test_missing_and_unknown_control_fields_rejected(self):
  for field in list(self.control()):
   value=self.control();value.pop(field)
   with self.subTest(field=field):self.reject_control(value)
   self.set_control_fixture()
  value=self.control();value['rawPrivateLog']='MUST_NOT_PASS';self.reject_control(value)
 def set_control_fixture(self):self.write_control(copy.deepcopy(self.control_fixture))
 def test_missing_and_unknown_host_fields_rejected(self):
  original=self.control()
  for field in list(original['hostDiagnostic']):
   value=copy.deepcopy(original);value['hostDiagnostic'].pop(field)
   with self.subTest(field=field):self.reject_control(value)
  value=copy.deepcopy(original);value['hostDiagnostic']['rawException']='MUST_NOT_PASS';self.reject_control(value)
 def test_host_failure_or_unknown_phase_and_code_rejected(self):
  original=self.control()
  for update in (dict(failurePhase='STAGE_ARCHIVE',failureCode='PERMISSION_DENIED'),
                 dict(lastPhase='UNKNOWN'),dict(failurePhase='UNKNOWN',failureCode='OTHER_ERROR'),
                 dict(failurePhase='STAGE',failureCode='PRIVATE_EXCEPTION_TEXT'),dict(failurePhase='STAGE',failureCode='NONE')):
   value=copy.deepcopy(original);value['hostDiagnostic'].update(update)
   with self.subTest(update=update):self.reject_control(value)
 def test_wrong_receipt_host_pin_hash_or_size_rejected(self):
  original=self.control()
  for pin in (dict(sha256='f'*64,bytes=len(self.raw)),dict(sha256=o.sha(self.package/'native-build-receipt.json'),bytes=len(self.raw)+1),
              dict(sha256='__UNFINALIZED__',bytes=len(self.raw)),dict(sha256='f'*64,bytes=True),dict(sha256='f'*64,bytes=0),{'sha256':'f'*64,'bytes':10,'raw':'private'}):
   value=copy.deepcopy(original);value['hostDiagnostic']['nativeReceiptPin']=pin
   with self.subTest(pin=pin):self.reject_control(value)
 def test_absent_optional_host_receipt_pin_does_not_replace_original_receipt_gate(self):
  value=self.control();value['hostDiagnostic']['nativeReceiptPin']=None;self.write_control(value)
  o.validate_package(self.package,self.p)
  (self.package/'native-build-receipt.json').write_bytes(self.raw+b' ')
  with self.assertRaises(ValueError):o.validate_package(self.package,self.p)
 def test_runtime_diagnostic_private_or_traversal_path_rejected(self):
  original=self.control()
  for name in ('../secret','/tmp/private','DesertRV_Data/private.log','DesertRV_Data/.credentials','DesertRV_Data/credentials.json','unknown.bin'):
   value=copy.deepcopy(original);value['hostDiagnostic']['runtime']['entries'][0]['path']=name
   with self.subTest(name=name):self.reject_control(value)
 def test_runtime_diagnostic_counts_unknown_fields_and_order_rejected(self):
  original=self.control()
  mutations=[lambda r:r.update(totalEntries=True),lambda r:r.update(omittedEntries=1),lambda r:r.update(observed=False),
             lambda r:r.update(entries=list(reversed(r['entries']))),lambda r:r['entries'][0].update(raw='private'),
             lambda r:r['entries'][0].update(kind='UNKNOWN'),lambda r:r['entries'][0].update(mode=True),
             lambda r:r['entries'][0].update(bytes=-1),lambda r:r['entries'][0].update(sha256='__UNFINALIZED__')]
  for mutate in mutations:
   value=copy.deepcopy(original);mutate(value['hostDiagnostic']['runtime']);self.reject_control(value)
 def test_host_source_and_line_must_be_closed_and_paired(self):
  original=self.control()
  for update in (dict(failureSource='/tmp/private.log',failureLine=1),dict(failureSource=o.bundle.HOST_SOURCE_PATHS[0],failureLine=0),dict(failureSource='',failureLine=1)):
   value=copy.deepcopy(original);value['hostDiagnostic'].update(update);self.reject_control(value)
 def test_host_completed_phases_reject_duplicates_and_unknown(self):
  original=self.control()
  for done in (['STAGED','STAGED'],['PRIVATE_PHASE'],['NONE']):
   value=copy.deepcopy(original);value['hostDiagnostic']['completedPhases']=done;self.reject_control(value)
 def stage_fixture(self,run_update=None,artifact_update=None):
  # A synthetic branch producer ZIP exercises real stage validation, never a download/run.
  manifest=json.loads((self.package/'manifest.json').read_text());native=manifest['nativeReceipt']
  native.update(restorationProof=dict(path='tasks/desert-rv/unity/JourneyEvidence/JourneyPreparation/restoration-revalidated.json',sha256='d'*64),
                assetProducerSourceCommit='f'*40,assetProducerRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/456',restorationNativeXmlSha256='e'*64)
  raw=(json.dumps(native,indent=2)+'\n').encode();(self.package/'native-build-receipt.json').write_bytes(raw)
  manifest['nativeReceiptSha256']=o.sha(self.package/'native-build-receipt.json');(self.package/'manifest.json').write_text(json.dumps(manifest))
  control=self.control();control['hostDiagnostic']['nativeReceiptPin']=dict(sha256=manifest['nativeReceiptSha256'],bytes=len(raw));self.write_control(control)
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as archive:
   for name in sorted(o.PACKAGE_FILES):archive.writestr(name,(self.package/name).read_bytes())
  zip_raw=out.getvalue();pins=dict(self.p,PRODUCER_ZIP_SHA256=o.hashlib.sha256(zip_raw).hexdigest())
  run=dict(status='completed',conclusion='success',head_sha=pins['PRODUCER_COMMIT'],head_branch='journey-linux-export-recovery-938',path=o.REBUILD_WORKFLOW,run_attempt=1)
  artifact=dict(workflow_run=dict(id=int(pins['PRODUCER_RUN_ID']),head_sha=pins['PRODUCER_COMMIT']),expired=False,digest='sha256:'+pins['PRODUCER_ZIP_SHA256'],size_in_bytes=len(zip_raw),name='journey-linux-CANDIDATE-NOT-PLAYTESTED-123-1')
  run.update(run_update or {});artifact.update(artifact_update or {})
  stack=__import__('contextlib').ExitStack();self.addCleanup(stack.close)
  source=self.root/'staged-observer-source';stack.enter_context(patch.object(o,'SOURCE',source));stack.enter_context(patch.object(o,'TASK',self.root))
  stack.enter_context(patch.dict(os.environ,pins))
  def api(endpoint):
   self.assertIn(endpoint,('/actions/runs/123','/actions/artifacts/456'));return run if endpoint=='/actions/runs/123' else artifact
  def transfer(args,**kwargs):
   self.assertEqual(args,['gh','api','repos/'+o.REPO+'/actions/artifacts/456/zip']);kwargs['stdout'].write(zip_raw)
   return o.subprocess.CompletedProcess(args,0)
  stack.enter_context(patch.object(o,'api',side_effect=api));download=stack.enter_context(patch.object(o.subprocess,'run',side_effect=transfer))
  return source,pins,download
 def test_branch_producer_stages_exact_original_verified_package(self):
  source,pins,download=self.stage_fixture();o.stage();download.assert_called_once()
  verified=json.loads((source/'verified.json').read_text());self.assertEqual(verified['pins'],pins);self.assertEqual(verified['producerWorkflowPath'],o.REBUILD_WORKFLOW)
  self.assertEqual((source/'package/native-build-receipt.json').read_bytes(),(self.package/'native-build-receipt.json').read_bytes())
  self.assertEqual(o.sha(source/'producer.zip'),pins['PRODUCER_ZIP_SHA256'])
  self.assertEqual(o.bundle.inventory(source/'runtime'),json.loads((source/'package/manifest.json').read_text())['files'])
 def test_branch_producer_unsuccessful_run_is_rejected_before_zip(self):
  source,pins,download=self.stage_fixture(run_update=dict(conclusion='failure'))
  with self.assertRaises(ValueError):o.stage()
  download.assert_not_called();self.assertFalse(source.exists())
 def test_branch_producer_wrong_build_commit_is_rejected_before_zip(self):
  source,pins,download=self.stage_fixture(run_update=dict(head_sha='f'*40))
  with self.assertRaises(ValueError):o.stage()
  download.assert_not_called();self.assertFalse(source.exists())
 def test_branch_producer_wrong_workflow_is_rejected_before_zip(self):
  source,pins,download=self.stage_fixture(run_update=dict(path='.github/workflows/other.yml'))
  with self.assertRaises(ValueError):o.stage()
  download.assert_not_called();self.assertFalse(source.exists())
 def test_branch_producer_wrong_artifact_digest_is_rejected_before_zip(self):
  source,pins,download=self.stage_fixture(artifact_update=dict(digest='sha256:'+'f'*64))
  with self.assertRaises(ValueError):o.stage()
  download.assert_not_called();self.assertFalse(source.exists())
 def test_new_observer_does_not_relabel_old_producer(self):
  with patch.dict(os.environ,{'GITHUB_SHA':'e'*40,'GITHUB_RUN_ID':'789'}):
   m=o.validate_package(self.package,self.p);self.assertEqual(m['sourceCommit'],'a'*40);self.assertEqual(os.environ['GITHUB_SHA'],'e'*40)
   with patch.object(o,'SOURCE',self.task):
    shutil.copytree(self.package,self.task/'package');v=o.metadata(self.p,m)
   self.assertEqual(v['producerSourceCommit'],'a'*40);self.assertEqual(v['observerSourceCommit'],'e'*40)
 def restored_manifest(self):
  m=o.validate_package(self.package,self.p);n=m['nativeReceipt'];n.update(restorationProof=dict(path='tasks/desert-rv/unity/JourneyEvidence/JourneyPreparation/restoration-revalidated.json',sha256='d'*64),assetProducerSourceCommit='f'*40,assetProducerRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/456',restorationNativeXmlSha256='e'*64);return m
 def test_exact_rebuild_workflow_requires_restoration_receipt(self):
  m=self.restored_manifest();o.validate_producer_workflow(o.REBUILD_WORKFLOW,m)
  with self.assertRaises(ValueError):o.validate_producer_workflow(o.PREPARE_WORKFLOW,m)
  original=o.validate_package(self.package,self.p)
  with self.assertRaises(ValueError):o.validate_producer_workflow(o.REBUILD_WORKFLOW,original)
 def test_unknown_workflow_and_missing_restore_xml_rejected(self):
  m=self.restored_manifest()
  with self.assertRaises(ValueError):o.validate_producer_workflow('.github/workflows/other-rebuild.yml',m)
  m['nativeReceipt']['restorationNativeXmlSha256']=''
  with self.assertRaises(ValueError):o.validate_producer_workflow(o.REBUILD_WORKFLOW,m)
 def test_original_asset_run_cannot_be_current_build_run(self):
  m=self.restored_manifest();m['nativeReceipt']['assetProducerRunUrl']=m['producerRunUrl']
  with self.assertRaises(ValueError):o.validate_producer_workflow(o.REBUILD_WORKFLOW,m)
 def test_receipt_original_bytes_must_match_manifest(self):
  (self.package/'native-build-receipt.json').write_bytes(self.raw+b' ')
  with self.assertRaises(ValueError):o.validate_package(self.package,self.p)
 def test_tampered_archive_rejected(self):
  (self.package/'player.tar.gz').write_bytes(b'tampered')
  with self.assertRaises(ValueError):o.validate_package(self.package,self.p)
 def test_wrong_producer_commit_rejected(self):
  self.p['PRODUCER_COMMIT']='f'*40
  with self.assertRaises(ValueError):o.validate_package(self.package,self.p)
 def test_producer_control_failure_rejected(self):
  c=json.loads((self.package/'control.json').read_text());c['privateCleanup']='FAILED';(self.package/'control.json').write_text(json.dumps(c))
  with self.assertRaises(ValueError):o.validate_package(self.package,self.p)
 def test_extract_writes_only_verified_files_and_preserves_bundle(self):
  m=o.validate_package(self.package,self.p);original=o.sha(self.package/'player.tar.gz');dest=self.root/'runtime';o.extract_runtime(self.package,dest,m)
  self.assertEqual(o.bundle.inventory(dest),m['files']);self.assertEqual(o.sha(self.package/'player.tar.gz'),original)
 def test_unsafe_tar_cannot_create_files(self):
  m=o.validate_package(self.package,self.p)
  with tarfile.open(self.package/'player.tar.gz','w:gz') as t:
   i=tarfile.TarInfo('../escape');i.size=1;t.addfile(i,io.BytesIO(b'x'))
  dest=self.root/'runtime'
  with self.assertRaises(ValueError):o.extract_runtime(self.package,dest,m)
  self.assertFalse(dest.exists());self.assertFalse((self.root/'escape').exists())
 def test_zip_requires_exact_four_public_files(self):
  archive=self.root/'bad.zip'
  with zipfile.ZipFile(archive,'w') as z:z.writestr('../secret','secret')
  with self.assertRaises(ValueError):o.unpack_zip(archive,self.root/'zipout')
  self.assertFalse((self.root/'secret').exists())
 def test_zip_duplicate_members_rejected(self):
  archive=self.root/'duplicate.zip'
  with zipfile.ZipFile(archive,'w') as z:
   for name in o.PACKAGE_FILES:z.writestr(name,b'x')
   with __import__('warnings').catch_warnings():
    __import__('warnings').simplefilter('ignore');z.writestr('manifest.json',b'x')
  with self.assertRaises(ValueError):o.unpack_zip(archive,self.root/'zipout')
 def test_private_duplicate_json_key_rejected(self):
  with self.assertRaises(ValueError):o.strict_json(b'{"x":"private","x":1}')
 def test_process_pid_and_exact_argv_rejected_on_mismatch(self):
  class Player:
   pid=999999999
   def poll(self):return 1
  with self.assertRaises(ValueError):o.process_identity(Player(),self.root/'fake',['fake'])
 def test_capture_no_input_no_rebuild_no_fullscreen_fallback(self):
  import inspect
  s=inspect.getsource(o.capture);self.assertIn("'-window_id',window",s);self.assertNotIn('window_id or',s)
  for bad in ('Begin(', 'Replay(', 'SessionState', 'xdotool\',\'key', 'xdotool\',\'click', 'unity-editor', 'BuildPlayer'):self.assertNotIn(bad,s)
  self.assertIn('producerBundlePreserved=bundle_preserved',s);self.assertNotIn('rmtree(SOURCE',s);self.assertIn('finish_encoder(ff)',s)
 def test_workflow_credentials_only_download_and_exact_readonly_mount(self):
  root=pathlib.Path(__file__).resolve().parents[4];s=(root/'.github/workflows/desert-rv-player-observe.yml').read_text()
  for secret in ('secrets.UNITY_LICENSE','UNITY_EMAIL','UNITY_PASSWORD','activate.sh','prepare_runner.sh'):self.assertNotIn(secret,s)
  self.assertIn('GH_TOKEN: ${{ github.token }}',s);self.assertNotIn('--env GH_TOKEN',s);self.assertIn('$GITHUB_WORKSPACE:/github/workspace:ro',s)
 def guarded_success(self,native='success'):
  from contextlib import ExitStack
  source=self.root/'source';source.mkdir();shutil.copytree(self.package,source/'package');work=self.root/'work';work.mkdir();result=work/'result';result.mkdir()
  stack=ExitStack();self.addCleanup(stack.close)
  for key,value in dict(SOURCE=source,WORK=work,RESULT=result,PUBLIC=work/'public').items():stack.enter_context(patch.object(o,key,value))
  stack.enter_context(patch.dict(os.environ,dict(self.p,GITHUB_SHA='e'*40,GITHUB_RUN_ID='789',NATIVE_OUTCOME=native,GITHUB_OUTPUT=str(work/'output'))))
  m=o.validate_package(source/'package',self.p);(source/'verified.json').write_text(json.dumps(dict(schema=1,pins=self.p,producerWorkflowPath=o.PREPARE_WORKFLOW,manifestSha256=o.sha(source/'package/manifest.json'),executableSha256=m['nativeReceipt']['executableSha256'])));s=o.metadata(self.p,m);s.update(stage='MEDIA_VERIFIED',failureCode='NONE',success=True,playerExitCode=-15,playerTerminationRequest='OBSERVER_TERM',encoderExitCode=0,producerBundlePreserved=True,rawLogsExported=False,captureStartUtc='2026-10-09T00:00:00+00:00',captureEndUtc='2026-10-09T00:00:16+00:00',durationSeconds=16,captureFps=30,encodedFrameRate='30/1',averageFrameRate='30/1',encodedFrames=480,identityChecks=160,windowId='123',playerPid=42)
  (result/'status.json').write_text(json.dumps(s));(result/'sha256.json').write_text('{}')
  for name in ('real-time.mp4','frame-0.png','frame-1.png','frame-2.png'):(result/name).write_bytes(b'SYNTHETIC_TEST_MEDIA')
  (result/'sha256.json').write_text(json.dumps({p.name:o.sha(p) for p in result.iterdir() if p.name!='sha256.json'}))
  stack.enter_context(patch.object(o,'inspect_png'));stack.enter_context(patch.object(o,'probe_video',return_value=dict(format=dict(duration='16'),streams=[dict(width=1280,height=720,r_frame_rate='30/1',avg_frame_rate='30/1')])));return work,result
 def test_verified_success_guard_copies_only_fixed_media(self):
  work,_=self.guarded_success();o.export();self.assertEqual({p.name for p in (work/'public').iterdir()},{'status.json','sha256.json','real-time.mp4','frame-0.png','frame-1.png','frame-2.png'})
  s=json.loads((work/'public/status.json').read_text());self.assertEqual(s['producerSourceCommit'],'a'*40);self.assertEqual(s['observerSourceCommit'],'e'*40);self.assertEqual(s['engineFrameHeartbeat'],'NOT_AVAILABLE')
 def test_docker_failure_cannot_export_previous_success_video(self):
  work,_=self.guarded_success('failure');o.export();self.assertEqual({p.name for p in (work/'public').iterdir()},{'status.json','sha256.json'});self.assertEqual(json.loads((work/'public/status.json').read_text())['failureCode'],'OBSERVER_PROCESS_NOT_SUCCESS')
 def test_unrequested_player_exit_prevents_media_export(self):
  work,result=self.guarded_success();s=json.loads((result/'status.json').read_text());s['playerTerminationRequest']='NONE';(result/'status.json').write_text(json.dumps(s));o.export();self.assertFalse((work/'public/real-time.mp4').exists())
 def test_valid_mp4_replaced_after_capture_is_rejected_by_original_hash(self):
  import base64,zlib,struct
  work,result=self.guarded_success();video=zlib.decompress(base64.b64decode(SYNTHETIC_MP4));(result/'real-time.mp4').write_bytes(video)
  (result/'sha256.json').write_text(json.dumps({p.name:o.sha(p) for p in result.iterdir() if p.name!='sha256.json'}))
  # Legal ISO-BMFF free box changes bytes while leaving valid 1280x720/30fps/16s video.
  (result/'real-time.mp4').write_bytes(video+struct.pack('>I4s',8,b'free'));o.export();self.assertFalse((work/'public/real-time.mp4').exists())
 def test_valid_png_replaced_after_capture_is_rejected_by_original_hash(self):
  from PIL import Image,ImageDraw
  work,result=self.guarded_success();p=result/'frame-0.png';image=Image.new('RGB',(1280,720),'red');ImageDraw.Draw(image).rectangle((0,0,640,720),fill='blue');image.save(p)
  (result/'sha256.json').write_text(json.dumps({p.name:o.sha(p) for p in result.iterdir() if p.name!='sha256.json'}))
  image.putpixel((1,1),(0,255,0));image.save(p);o.export();self.assertFalse((work/'public/frame-0.png').exists())
 def test_missing_and_unknown_original_hash_entries_rejected(self):
  work,result=self.guarded_success();pins=json.loads((result/'sha256.json').read_text());pins.pop('frame-0.png');(result/'sha256.json').write_text(json.dumps(pins));o.export();self.assertFalse((work/'public/real-time.mp4').exists())
  shutil.rmtree(work/'public');pins['frame-0.png']=o.sha(result/'frame-0.png');pins['raw-private.log']='a'*64;(result/'sha256.json').write_text(json.dumps(pins));o.export();self.assertFalse((work/'public/real-time.mp4').exists())
 def test_status_bytes_are_pinned_even_if_parsed_content_unchanged(self):
  work,result=self.guarded_success();p=result/'status.json';p.write_text(p.read_text()+' ');o.export();self.assertFalse((work/'public/real-time.mp4').exists())
 def test_postcopy_media_tamper_cannot_escape_host_gate(self):
  work,result=self.guarded_success();copy=shutil.copyfile
  def tamper(src,dst):
   copy(src,dst)
   if pathlib.Path(dst).name=='real-time.mp4':pathlib.Path(dst).write_bytes(b'CHANGED_AFTER_COPY')
  with patch.object(o.shutil,'copyfile',side_effect=tamper):o.export()
  self.assertEqual({p.name for p in (work/'public').iterdir()},{'status.json','sha256.json'})
 def test_native_failure_exports_no_media(self):
  work=self.root/'work';work.mkdir();result=work/'result';result.mkdir();(result/'status.json').write_text(json.dumps(dict(schema=1,label='CANDIDATE_PLAYER_OBSERVER_FAILED',success=False,stage='START',failureCode='ARTIFACT_API',rawLogsExported=False)));(result/'real-time.mp4').write_bytes(b'PRIVATE_UNVERIFIED')
  with patch.object(o,'WORK',work),patch.object(o,'RESULT',result),patch.object(o,'PUBLIC',work/'public'),patch.dict(os.environ,{'GITHUB_OUTPUT':str(work/'output'),'NATIVE_OUTCOME':'failure'}):o.export()
  self.assertEqual({p.name for p in (work/'public').iterdir()},{'status.json','sha256.json'})
 def test_raw_unknown_failure_fields_are_not_republished(self):
  work=self.root/'work';work.mkdir();result=work/'result';result.mkdir();(result/'status.json').write_text(json.dumps(dict(schema=1,label='CANDIDATE_PLAYER_OBSERVER_FAILED',success=False,stage='START',failureCode='ARTIFACT_API',rawLogsExported=False,raw='SECRET')))
  with patch.object(o,'WORK',work),patch.object(o,'RESULT',result),patch.object(o,'PUBLIC',work/'public'),patch.dict(os.environ,{'GITHUB_OUTPUT':str(work/'output'),'NATIVE_OUTCOME':'failure'}):o.export()
  self.assertNotIn('SECRET',(work/'public/status.json').read_text())
 def test_fixed_failure_main_never_destroys_existing_bundle(self):
  source=self.root/'preserved';source.mkdir();original=source/'player.tar.gz';original.write_bytes(b'original');work=self.root/'work'
  with patch.object(o,'SOURCE',source),patch.object(o,'WORK',work),patch.object(o,'RESULT',work/'result'),patch.object(o.sys,'argv',['observe','capture']):self.assertEqual(o.main(),1)
  self.assertEqual(original.read_bytes(),b'original');status=json.loads((work/'result/status.json').read_text());self.assertFalse(status['success']);self.assertIn(status['failureCode'],o.FAILURES)
# zlib/base64 of an explicitly synthetic red lavfi 1280x720/30fps/16s clip; never game evidence.
SYNTHETIC_MP4='eNrtWk9oXEUYn80am4aqFWLroeAUg4oku+/tbtYk+EpqqAaxoIcWhMo6+2Ze3mPfv8zMJtmCsIiH4lXxkFy8aS+CiFQFIQfRm4gXW+khXkRR9OTJw/rNyy47bVGk9GDlm/3Nm9/MfN83v/lmIZPlEUJooHt5pLKEkAliWqg1tum7Sd5wCSFTgRSCkMpCwpkGm3P3Tg4GL10/8/PnP15bu/LO3FV67dHfft+uNRt0nvqZFNQFKuuus0jrrnCXgiWYWKuAQfXsi2eem2/Q0+dXwZILHyZWs7wXi0DTmuPU52tOrQ6Dodb5crW6tbVV2Yy4yGKWVjK5XjWrVEKdxGCT5TrKUrVMfdZmvudQKQLPpVy048zveM4yfChLWdxTwvRoIjweMaq6bWAOzVUPzOHZktxzKw6YwIMm0bbgLRPLeLQkS9eF5zapH8osYS1wdamWIo4jBRaL24vc10D8jQSeXDB+MUuFV3PnXJcGTOlWrjpRDk7DABt5KwsCJYyTDiU4KM+t0zjLOiyEXms0WKMqjnwxHnBoKos1/Chh2uiIUi1kzMAIxttxV7Jey8+SnBWKIDlasiiFEGAombEJJEuECbUlovVQ58A6ogfTXm1hRFtJlEKXKl+kwu+aWIW/SYoUKjSp9j1fBjRpQyZMLqHj1RcqDt0wy3tOpQk0N3GKlm17zSUgSovca9Aoh7TC4UHWG3BEG55D+oRMfyguvbH84Jtkouzukes5Oeq8dWfLB5/9gkAgEAgEAoFA3Db2zH9Hp3foY/1DU0O+YvFXnxzzvsXftfiexffHfJdYnFp8xeJW/F0r/q4Vf9eKv2vF37Hi71jxd6z4qB/1o37Uj/pRP+pH/agf9d/V+qc/EpdeL4fPPkGmzn5FShOf7JOTrz1+Z8sr3e8QCAQCgUAgEIjbRh9/Ykb9qB/1o37Uj/pRP+pH/XeP/un3kizbhLE42Qw5uaGUfyLkVJ+UiMG4lG60urm/Qv6xTBBy+FstWQf4Bd0p1izfGu1U/xbPf7HupFngm6I7K7hW0J4QsdJjj2Hcwvfw8wmPGBCa8Jv3/jSo2iPnvig68yGP5WjGvO5uW543r7+vsZTHwthM/ZFEaQBkZjMpgtoyZ/nB3AkuRWBt40hXxvSAT32sdDsG/qnSils2l80b/3+TCtg4bHsNyNrI4qEXwL7pVtyliuu4NI7a5tV8y+XhwQCeVbBaLT2z98jgB3J8HdrvSyvHfr1nxRwKPB4of3nk/RKZDL+euGAydzRnKh8KMHWmreUwu8ePjQIrXWR+KLS0Xxx6Ma7U+FtQ+P9pkgHjvrWxoY9pD70NcxetI4fx++43CcOKFev/uU5fwRxgxfqfqzNK+5n199qByrpcm5vUy4koWlNO2rcmuGlJluexfWmZiw6uZrOXdZYVtyJWOBe3G7i+BHB9eQpuL/W/AAcaifs='
if __name__=='__main__':unittest.main()
