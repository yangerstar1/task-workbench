"""Closed restoration/source transition fixtures. No fixture is native play evidence."""
import copy,hashlib,json,os,tempfile,unittest,zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock
import restore_preparation as r

class SourceTransitionTests(unittest.TestCase):
 def setUp(self):
  self.name='tasks/desert-rv/art/journey-preparation/restore_preparation.py';self.oldname='tasks/desert-rv/scripts/verify_evidence.py'
  self.before=dict(schema='fixture',coverageRoots=['unity'],coverageFiles=['original.yml'],restoredFiles=[],files=[dict(path=self.oldname,sha256='a'*64,size=1)])
  self.after=copy.deepcopy(self.before);self.after['coverageFiles'].append('.github/workflows/desert-rv-journey-rebuild.yml')
  self.after['files']=[dict(path=self.oldname,sha256='b'*64,size=2),dict(path=self.name,sha256='c'*64,size=3),dict(path=r.POLICY,sha256='d'*64,size=4)]
  self.policy=dict(schema=1,status='REVIEWED_DIAGNOSTIC_RESTORATION_SOURCE_ONLY',producer=r.PRODUCER,changes=[dict(path=self.name,beforeSha256='',beforeBytes=0,afterSha256='c'*64,afterBytes=3),dict(path=self.oldname,beforeSha256='a'*64,beforeBytes=1,afterSha256='b'*64,afterBytes=2)])
 def check(self):return r.source_transition(self.policy,self.before,self.after,'d'*64)
 def rejects(self,code):
  with self.assertRaisesRegex(Exception,code):self.check()
 def test_exact_reviewed_added_and_changed_source_accepted(self):self.assertEqual(self.policy['changes'],self.check())
 def test_exact_reviewed_container_change_requires_its_own_hash_pin(self):
  name='tasks/desert-rv/scripts/player/journey_linux_container.sh'
  self.before['files'].append(dict(path=name,sha256='e'*64,size=20))
  self.after['files'].append(dict(path=name,sha256='f'*64,size=21))
  self.policy['changes'].append(dict(path=name,beforeSha256='e'*64,beforeBytes=20,afterSha256='f'*64,afterBytes=21));self.policy['changes'].sort(key=lambda x:x['path'])
  self.assertEqual(self.policy['changes'],self.check())
  self.after['files'][-1]['sha256']='a'*64;self.rejects('EXACT_SOURCE_DIFF')
  self.after['files'][-1]['sha256']='f'*64;self.after['files'][-1]['path']='tasks/desert-rv/scripts/player/unreviewed_container.sh';self.rejects('UNREVIEWED_SOURCE')
 def test_four_exact_cache_and_image_host_paths_need_individual_byte_pins(self):
  for name in ('tasks/desert-rv/scripts/rendered/prepared_source.py','tasks/desert-rv/scripts/rendered/test_prepared_source.py','tasks/desert-rv/scripts/environment_image_precheck.py','tasks/desert-rv/scripts/test_environment_image_precheck.py'):
   self.after['files'].append(dict(path=name,sha256='e'*64,size=9))
   self.policy['changes'].append(dict(path=name,beforeSha256='',beforeBytes=0,afterSha256='e'*64,afterBytes=9))
  self.policy['changes'].sort(key=lambda row:row['path']);self.assertEqual(self.policy['changes'],self.check())
  self.after['files'][-1]['sha256']='f'*64;self.rejects('EXACT_SOURCE_DIFF')
 def test_unlisted_runtime_change_rejected(self):self.after['files'].append(dict(path='tasks/desert-rv/unity/Assets/DesertRV/Runtime/JourneyActions.cs',sha256='e'*64,size=9));self.rejects('UNREVIEWED_SOURCE')
 def test_unlisted_asset_change_rejected(self):self.after['files'].append(dict(path='tasks/desert-rv/unity/Assets/Original.asset',sha256='e'*64,size=9));self.rejects('UNREVIEWED_SOURCE')
 def test_contract_change_rejected(self):self.after['files'].append(dict(path='tasks/desert-rv/art/import-candidate/contracts/weapon.json',sha256='e'*64,size=9));self.rejects('UNREVIEWED_SOURCE')
 def test_source_deletion_rejected(self):self.after['files']=[x for x in self.after['files'] if x['path']!=self.oldname];self.rejects('UNREVIEWED_SOURCE')
 def test_old_hash_difference_rejected(self):self.policy['changes'][1]['beforeSha256']='e'*64;self.rejects('EXACT_SOURCE_DIFF')
 def test_new_hash_difference_rejected(self):self.policy['changes'][0]['afterSha256']='e'*64;self.rejects('EXACT_SOURCE_DIFF')
 def test_new_byte_count_difference_rejected(self):self.policy['changes'][0]['afterBytes']=4;self.rejects('EXACT_SOURCE_DIFF')
 def test_missing_reviewed_change_rejected(self):self.policy['changes'].pop();self.rejects('EXACT_SOURCE_DIFF')
 def test_duplicate_reviewed_change_rejected(self):self.policy['changes'].append(self.policy['changes'][0]);self.rejects('EXACT_SOURCE_DIFF')
 def test_policy_dispatch_sha_mismatch_rejected(self):self.after['files'][-1]['sha256']='e'*64;self.rejects('POLICY_SOURCE_PIN')
 def test_policy_cannot_be_previous_source(self):self.before['files'].append(self.after['files'][-1]);self.rejects('POLICY_SOURCE_PIN')
 def test_coverage_root_changes_rejected(self):self.after['coverageRoots'].append('private');self.rejects('SOURCE_DOMAIN_CHANGED')
 def test_extra_coverage_file_rejected(self):self.after['coverageFiles'].append('arbitrary.yml');self.rejects('SOURCE_COVERAGE_CHANGED')
 def test_restored_file_exception_changes_rejected(self):self.after['restoredFiles'].append({});self.rejects('SOURCE_DOMAIN_CHANGED')
 def test_unknown_metadata_changes_rejected(self):self.after['ignored']=True;self.rejects('SOURCE_METADATA_CHANGED')
 def test_producer_identity_changes_rejected(self):self.policy['producer']=dict(r.PRODUCER,sourceCommit='0'*40);self.rejects('POLICY_IDENTITY')
 def test_no_prefix_allows_other_entry_script(self):self.after['files'].append(dict(path='tasks/desert-rv/art/journey-preparation/unsafe.py',sha256='e'*64,size=9));self.rejects('UNREVIEWED_SOURCE')

class PhysicalRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.project=self.root/'unity';self.project.mkdir();p=mock.patch.object(r,'PROJECT',self.project);p.start();self.addCleanup(p.stop)
  self.source=self.root/'source';self.source.write_bytes(b'original bytes')
  self.name='Assets/DesertRV/Scenes/Journey/FirstStation.unity';self.bundle=dict(paths={self.name:self.source},assets={self.name:r.sha(self.source)})
 def test_exact_bytes_restored_without_moving_original(self):
  r.restore_assets(self.bundle);self.assertEqual(self.source.read_bytes(),(self.project/self.name).read_bytes());self.assertEqual(b'original bytes',self.source.read_bytes())
 def test_existing_target_never_overwritten(self):
  target=self.project/self.name;target.parent.mkdir(parents=True);target.write_bytes(b'existing')
  with self.assertRaisesRegex(Exception,'COLLISION'):r.restore_assets(self.bundle)
  self.assertEqual(b'existing',target.read_bytes())
 def test_parent_symlink_rejected(self):
  (self.project/'Assets').symlink_to(self.root,target_is_directory=True)
  with self.assertRaisesRegex(Exception,'PARENT_SYMLINK'):r.restore_assets(self.bundle)
 def test_copy_hash_changed_rejected(self):
  self.bundle['assets'][self.name]='f'*64
  with self.assertRaisesRegex(Exception,'COPY_CHANGED'):r.restore_assets(self.bundle)
 def test_extra_empty_directory_rejected(self):
  folder=self.root/'bundle';folder.mkdir();(folder/'file').write_bytes(b'a');(folder/'unknown').mkdir()
  with self.assertRaisesRegex(Exception,'UNDECLARED_BUNDLE_DIRECTORY'):r.public_tree(folder)
 def test_bundle_symlink_rejected(self):
  folder=self.root/'bundle';folder.mkdir();(folder/'link').symlink_to(self.source)
  with self.assertRaisesRegex(Exception,'SYMLINK'):r.public_tree(folder)
 def test_bundle_real_file_change_changes_proof(self):
  folder=self.root/'bundle';folder.mkdir();path=folder/'file';path.write_bytes(b'a');before=r.public_tree(folder);path.write_bytes(b'b');self.assertNotEqual(before,r.public_tree(folder))
 def test_native_xml_is_current_exact_fullname(self):
  with mock.patch.object(r,'TASK',self.root),mock.patch.object(r,'ROOT',self.root):
   folder=self.root/'artifacts/journey-restoration';folder.mkdir(parents=True);path=folder/'result.xml'
   xml=ET.Element('test-run',result='Passed',total='1',passed='1',failed='0',skipped='0',inconclusive='0');ET.SubElement(xml,'test-case',fullname=r.NATIVE_NAME,result='Passed');ET.ElementTree(xml).write(path)
   self.assertEqual(r.sha(path),r.native_evidence()['sha256'])
   xml[0].set('fullname','DesertRV.Tests.JourneyRestorationTests.Pretend');ET.ElementTree(xml).write(path)
   with self.assertRaisesRegex(Exception,'NATIVE_NOT_PASSED'):r.native_evidence()
 def test_native_failed_case_and_wrong_root_count_rejected(self):
  with mock.patch.object(r,'TASK',self.root),mock.patch.object(r,'ROOT',self.root):
   folder=self.root/'artifacts/journey-restoration';folder.mkdir(parents=True);path=folder/'result.xml'
   for key,val in [('result','Failed'),('passed','0'),('total','2'),('skipped','1')]:
    attrs=dict(result='Passed',total='1',passed='1',failed='0',skipped='0',inconclusive='0');attrs[key]=val
    xml=ET.Element('test-run',**attrs);ET.SubElement(xml,'test-case',fullname=r.NATIVE_NAME,result='Passed');ET.ElementTree(xml).write(path)
    with self.assertRaisesRegex(Exception,'NATIVE_NOT_PASSED'):r.native_evidence()
 def test_native_duplicate_xml_rejected(self):
  with mock.patch.object(r,'TASK',self.root):
   folder=self.root/'artifacts/journey-restoration';folder.mkdir(parents=True);(folder/'a.xml').write_text('');(folder/'b.xml').write_text('')
   with self.assertRaisesRegex(Exception,'XML_COUNT'):r.native_evidence()
 def test_zip_wrapper_sha_must_be_original_not_repacked(self):
  path=self.root/'repacked.zip';path.write_bytes(b'not the original transport')
  with self.assertRaisesRegex(Exception,'ZIP_IDENTITY'):r.extract_original(path,self.root/'out')
 def test_zip_unsafe_member_rejected_even_if_transport_fixture_pin_matches(self):
  for member in ('../outside','/absolute','a/../outside','a\\b'):
   path=self.root/'fixture.zip'
   with zipfile.ZipFile(path,'w') as archive:archive.writestr(member,b'x')
   with mock.patch.dict(r.PRODUCER,artifactSha256=r.sha(path),artifactBytes=path.stat().st_size):
    with self.assertRaisesRegex(Exception,'ZIP_PATH'):r.extract_original(path,self.root/'out')
 def test_zip_duplicate_path_rejected(self):
  path=self.root/'fixture.zip'
  import warnings
  with warnings.catch_warnings():
   warnings.simplefilter('ignore')
   with zipfile.ZipFile(path,'w') as archive:archive.writestr('file',b'x');archive.writestr('file',b'y')
  with mock.patch.dict(r.PRODUCER,artifactSha256=r.sha(path),artifactBytes=path.stat().st_size):
   with self.assertRaisesRegex(Exception,'ZIP_BOUNDS'):r.extract_original(path,self.root/'out')

class ProducerApiTests(unittest.TestCase):
 def setUp(self):
  self.run=dict(id=r.PRODUCER['runId'],run_attempt=1,head_sha=r.PRODUCER['sourceCommit'],status='completed',conclusion='failure',head_branch='main',event='workflow_dispatch',path='.github/workflows/desert-rv-journey-prepare.yml')
  self.artifact=dict(id=r.PRODUCER['artifactId'],name=r.PRODUCER['artifactName'],expired=False,size_in_bytes=r.PRODUCER['artifactBytes'],digest='sha256:'+r.PRODUCER['artifactSha256'],workflow_run=dict(id=r.PRODUCER['runId'],head_sha=r.PRODUCER['sourceCommit']))
  names={7:'Native strict armored import and actual capture',8:'Reuse exact strict quality gate and preserve armored reports',10:'Native strict pouncer import and actual capture',11:'Reuse exact strict quality gate and preserve pouncer reports',13:'Native strict weapon import and actual capture',14:'Reuse exact strict quality gate and preserve weapon reports',15:'Require exact three-candidate union and freeze real selections',16:'Native exact candidate Linux boundary tests',17:'Require exact seventeen passing candidate boundary cases',18:'Native original FX, four scenes, integration and diagnostic scope',19:'Verify actual preparation test, saved outputs and final scope pins'}
  self.jobs=dict(jobs=[dict(name='prepare',run_id=r.PRODUCER['runId'],status='completed',steps=[dict(number=n,name=name,conclusion='success') for n,name in names.items()])])
 def check(self):r.validate_producer_api(self.run,self.artifact,self.jobs)
 def test_later_linux_failure_does_not_erase_passed_producer(self):self.check()
 def test_failed_native_authoring_rejected(self):
  self.jobs['jobs'][0]['steps'][-2]['conclusion']='failure'
  with self.assertRaisesRegex(Exception,'AUTHORING_NOT_PASSED'):self.check()
 def test_failed_any_strict_stage_rejected(self):
  self.jobs['jobs'][0]['steps'][0]['conclusion']='failure'
  with self.assertRaisesRegex(Exception,'AUTHORING_NOT_PASSED'):self.check()
 def test_other_head_rejected(self):
  self.run['head_sha']='0'*40
  with self.assertRaisesRegex(Exception,'PRODUCER_RUN'):self.check()
 def test_rerun_attempt_rejected(self):
  self.run['run_attempt']=2
  with self.assertRaisesRegex(Exception,'PRODUCER_RUN'):self.check()
 def test_other_wrapper_digest_rejected(self):
  self.artifact['digest']='sha256:'+'0'*64
  with self.assertRaisesRegex(Exception,'PRODUCER_ARTIFACT'):self.check()
 def test_expired_artifact_rejected(self):
  self.artifact['expired']=True
  with self.assertRaisesRegex(Exception,'PRODUCER_ARTIFACT'):self.check()
 def test_duplicate_job_rejected(self):
  self.jobs['jobs'].append(self.jobs['jobs'][0])
  with self.assertRaisesRegex(Exception,'PRODUCER_JOB'):self.check()

class DiagnosticExportTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  for key,val in [('EXPORT',self.root/'safe'),('HOST_STATUS',self.root/'status.json'),('DIAGNOSTIC',self.root/'native.json')]:
   patch=mock.patch.object(r,key,val);patch.start();self.addCleanup(patch.stop)
  patch=mock.patch.dict(os.environ,GITHUB_SHA='c'*40,GITHUB_RUN_ID='77');patch.start();self.addCleanup(patch.stop)
  self.value=dict(schema=1,label='RESTORATION_NATIVE_DIAGNOSTIC_ONLY',sourceCommit='c'*40,producerRunUrl=r.current_run(),stage='IMPORTER_IDENTITIES',completed=False,importerIdentities=[],dependencyDifferences=[],errorClass='IMPORTER_IDENTITY',dependencyExpectedCount=792,dependencyActualCount=792,dependencyAddedCount=0,dependencyMissingCount=0,runIdentity='MATCHED',consumerIdentityMatched=True)
 def test_preflight_failure_has_only_fixed_nonbuildable_receipt(self):
  r.HOST_STATUS.write_text(json.dumps(dict(command='stage',errorCode='RESTORE_EXACT_SOURCE_DIFF')))
  receipt=r.diagnose();self.assertEqual('RESTORATION_NOT_READY',receipt['status']);self.assertFalse(receipt['buildReady']);self.assertFalse(receipt['scopeReusable']);self.assertEqual([],receipt['files'])
 def test_native_fixed_diagnostic_is_safe_exported(self):
  r.DIAGNOSTIC.write_text(json.dumps(self.value));receipt=r.diagnose();self.assertEqual(1,len(receipt['files']));self.assertFalse(receipt['buildReady']);self.assertEqual(self.value,json.loads((r.EXPORT/'native-diagnostic.json').read_text()))
 def test_unknown_native_field_is_not_exported(self):
  self.value['privateLog']='secret';r.DIAGNOSTIC.write_text(json.dumps(self.value));receipt=r.diagnose();self.assertEqual([],receipt['files']);self.assertEqual('DIAGNOSTIC_SCHEMA_REJECTED',receipt['failure']['errorCode']);self.assertNotIn('secret',(r.EXPORT/'receipt.json').read_text())
 def test_wrong_consumer_native_diagnostic_not_exported(self):
  self.value['sourceCommit']='d'*40;r.DIAGNOSTIC.write_text(json.dumps(self.value));self.assertEqual([],r.diagnose()['files'])
 def test_arbitrary_importer_path_rejected(self):
  self.value['importerIdentities']=[dict(kind='armored',path='private/secret',producerDependencyHash='a'*32,currentDependencyHash='b'*32,producerDependencySha256='c'*64,currentDependencySha256='d'*64)]
  with self.assertRaisesRegex(Exception,'IMPORTER_PIN'):r.bounded_native_diagnostic(self.value)
 def test_invalid_host_status_text_is_omitted(self):
  r.HOST_STATUS.write_text(json.dumps(dict(command='stage',errorCode='/private/unknown filename')));receipt=r.diagnose();self.assertEqual('NATIVE_OR_PREFLIGHT_NOT_READY',receipt['failure']['errorCode'])
 def test_added_unknown_dependency_can_be_reported_without_its_path(self):
  self.value.update(dependencyActualCount=793,dependencyAddedCount=1);r.DIAGNOSTIC.write_text(json.dumps(self.value));receipt=r.diagnose();self.assertEqual(1,len(receipt['files']));self.assertEqual([],self.value['dependencyDifferences'])
 def test_inconsistent_dependency_counts_rejected(self):
  self.value['dependencyAddedCount']=1
  with self.assertRaisesRegex(Exception,'DIAGNOSTIC_COUNTS'):r.bounded_native_diagnostic(self.value)
 def test_missing_run_identity_survives_as_nonbuildable_fixed_diagnostic(self):
  self.value.update(stage='INPUT',producerRunUrl='',consumerIdentityMatched=False,runIdentity='MISSING',errorClass='RUN_ID_ARGUMENT',dependencyExpectedCount=0,dependencyActualCount=0)
  r.DIAGNOSTIC.write_text(json.dumps(self.value));receipt=r.diagnose();self.assertEqual(1,len(receipt['files']));self.assertFalse(receipt['buildReady']);self.assertEqual('',json.loads((r.EXPORT/'native-diagnostic.json').read_text())['producerRunUrl'])
 def test_missing_identity_cannot_claim_completed_or_later_stage(self):
  self.value.update(stage='INPUT',producerRunUrl='',consumerIdentityMatched=False,runIdentity='MISSING',errorClass='RUN_ID_ARGUMENT',dependencyExpectedCount=0,dependencyActualCount=0)
  for key,val in [('completed',True),('stage','SAVED_BINDINGS')]:
   with self.assertRaisesRegex(Exception,'UNBOUND_IDENTITY'):r.bounded_native_diagnostic(dict(self.value,**{key:val}))
 def test_unmatched_identity_cannot_fall_back_to_old_producer_url(self):
  self.value.update(stage='INPUT',producerRunUrl=r.RUN_URL,consumerIdentityMatched=False,runIdentity='MISMATCH',errorClass='RUN_ID_ARGUMENT',dependencyExpectedCount=0,dependencyActualCount=0)
  with self.assertRaisesRegex(Exception,'UNBOUND_IDENTITY'):r.bounded_native_diagnostic(self.value)
 def test_all_four_cli_identity_failure_kinds_are_bounded(self):
  self.value.update(stage='INPUT',producerRunUrl='',consumerIdentityMatched=False,errorClass='RUN_ID_ARGUMENT',dependencyExpectedCount=0,dependencyActualCount=0)
  for state in ('MISSING','DUPLICATE','MALFORMED','MISMATCH'):r.bounded_native_diagnostic(dict(self.value,runIdentity=state))
 def test_native_cli_is_explicit_actions_run_id_and_build_env_is_preserved(self):
  import yaml
  root=Path(__file__).resolve().parents[4];workflow=yaml.safe_load((root/'.github/workflows/desert-rv-journey-rebuild.yml').read_text());steps=workflow['jobs']['rebuild']['steps'];native=next(s for s in steps if s.get('id')=='restore_native')
  self.assertEqual(1,native['with']['customParameters'].count('-journeyRestorationRunId'));self.assertIn('-journeyRestorationRunId ${{ github.run_id }}',native['with']['customParameters'])
  linux=next(s for s in steps if s.get('id')=='linux_native')['run'];self.assertIn('--env GITHUB_SHA --env GITHUB_RUN_ID --env GITHUB_RUN_ATTEMPT',linux)
 def test_same_prefix_unknown_error_and_stage_rejected(self):
  for key,val in [('stage','PRIVATE'),('errorClass','STACKTRACE')]:
   changed=dict(self.value,**{key:val})
   with self.assertRaisesRegex(Exception,'DIAGNOSTIC_SCHEMA'):r.bounded_native_diagnostic(changed)

class AssetLifecycleDiagnosticTests(unittest.TestCase):
 def setUp(self):
  DiagnosticExportTests.setUp(self)
  # Synthetic objects use one known dependency path to exercise object/path distinction without guessing the real five objects.
  self.name='Assets/DesertRV/Fixture.asset';self.expected={self.name:dict(path=self.name,sha256='a'*64,bytes=12)}
  patch=mock.patch.object(r,'diagnostic_dependencies',return_value=self.expected);patch.start();self.addCleanup(patch.stop)
  self.first=dict(path=self.name,type='UnityEngine.Material',captureGateMembership='UNKNOWN',identityState='RESOLVED',guid='1'*32,localId=2100000,dirty='DIRTY',transition='PREEXISTING',diskState='AVAILABLE',sha256='a'*64,bytes=12)
  self.second=dict(self.first,localId=2100001)
  self.value.update(schema=2,stage='WORLD_HUD_CAPTURE',errorClass='DIRTY_DEPENDENCY',assetLifecycle=[self.snapshot(0,'RESTORATION_ENTRY',[self.first,self.second])])
  patch=mock.patch.object(r,'ANDROID',True);patch.start();self.addCleanup(patch.stop)
 def snapshot(self,index,stage,dirty=(),cleared=(),unobserved=(),changes=()):
  return dict(sequence=index,stage=stage,status='CAPTURED',errorCode='NONE',preexistingBaseline=index==0,captureGateBound=False,captureGateObjectCount=0,declaredDependencyCount=len(self.expected),observedPathCount=1 if dirty or cleared or unobserved else 0,objectCount=len(dirty),distinctPathCount=len({x['path'] for x in dirty}),enteredDirtyCount=sum(x['transition']=='ENTERED' for x in dirty),retainedDirtyCount=sum(x['transition']=='RETAINED' for x in dirty),clearedCount=len(cleared),unobservedCount=len(unobserved),diskMismatchCount=0,diskUnavailableCount=0,dirtyDependencies=list(dirty),clearedDependencies=list(cleared),unobservedDependencies=list(unobserved),diskChanges=list(changes))
 def test_lifecycle_preserves_two_objects_one_path_and_unobserved_is_not_clean(self):
  retained=dict(self.first,transition='RETAINED');unloaded=dict(self.second,dirty='NOT_OBSERVED',transition='UNOBSERVED')
  self.value['assetLifecycle'].append(self.snapshot(1,'CAPTURE_ENTRY',[retained],unobserved=[unloaded]))
  r.DIAGNOSTIC.write_text(json.dumps(self.value));receipt=r.diagnose()
  self.assertFalse(receipt['buildReady']);self.assertEqual(1,len(receipt['files']));self.assertEqual(self.value,json.loads((r.EXPORT/'native-diagnostic.json').read_text()))
 def test_lifecycle_can_report_cleared_only_as_observed_clean(self):
  cleared=[dict(x,dirty='CLEAN',transition='CLEARED') for x in (self.first,self.second)]
  self.value['assetLifecycle'].append(self.snapshot(1,'CAPTURE_ENTRY',cleared=cleared));r.bounded_native_diagnostic(self.value)
  self.value['assetLifecycle'][1]['clearedDependencies'][0]['dirty']='NOT_OBSERVED'
  with self.assertRaisesRegex(Exception,'LIFECYCLE_OBJECT'):r.bounded_native_diagnostic(self.value)
 def test_current_android_export_cannot_downgrade_to_historical_schema(self):
  self.value.pop('assetLifecycle');self.value['schema']=1;r.DIAGNOSTIC.write_text(json.dumps(self.value));receipt=r.diagnose()
  self.assertEqual([],receipt['files']);self.assertEqual('DIAGNOSTIC_SCHEMA_REJECTED',receipt['failure']['errorCode'])
 def test_lifecycle_missing_empty_unknown_fields_and_stages_reject(self):
  import copy
  for change in (lambda v:v.pop('assetLifecycle'),lambda v:v.update(assetLifecycle=[]),lambda v:v['assetLifecycle'][0].update(privateLog='not-public'),lambda v:v['assetLifecycle'][0].update(stage='PRIVATE')):
   bad=copy.deepcopy(self.value);change(bad)
   with self.subTest(value=bad),self.assertRaises(Exception):r.bounded_native_diagnostic(bad)
 def test_lifecycle_unknown_path_type_guid_count_sequence_and_identity_reject(self):
  import copy
  for target,key,value in [('row','path','/private/unknown'),('row','type','Type /private'),('row','guid','not-guid'),('row','localId',True),('snapshot','objectCount',1),('snapshot','sequence',1),('root','sourceCommit','d'*40)]:
   bad=copy.deepcopy(self.value);part=bad if target=='root' else bad['assetLifecycle'][0] if target=='snapshot' else bad['assetLifecycle'][0]['dirtyDependencies'][0];part[key]=value
   with self.subTest(key=key),self.assertRaises(Exception):r.bounded_native_diagnostic(bad)
 def test_lifecycle_lost_object_and_duplicate_resolved_identity_reject(self):
  self.value['assetLifecycle'].append(dict(self.snapshot(1,'CAPTURE_ENTRY'),observedPathCount=1))
  with self.assertRaisesRegex(Exception,'LOST_OBJECT'):r.bounded_native_diagnostic(self.value)
  self.value['assetLifecycle']=[self.snapshot(0,'RESTORATION_ENTRY',[self.first,self.first])]
  with self.assertRaisesRegex(Exception,'DUPLICATE'):r.bounded_native_diagnostic(self.value)
 def test_lifecycle_unavailable_identity_duplicates_remain_observed(self):
  unknown=dict(self.first,identityState='UNAVAILABLE',guid='',localId=0)
  self.value['assetLifecycle']=[self.snapshot(0,'RESTORATION_ENTRY',[unknown,unknown])];r.bounded_native_diagnostic(self.value)
  self.assertEqual(2,self.value['assetLifecycle'][0]['objectCount']);self.assertEqual(1,self.value['assetLifecycle'][0]['distinctPathCount'])
 def test_lifecycle_disk_changes_must_match_producer_then_previous_sample(self):
  change=dict(path=self.name,beforeState='AVAILABLE',beforeSha256='a'*64,beforeBytes=12,afterState='AVAILABLE',afterSha256='b'*64,afterBytes=13)
  self.value['assetLifecycle']=[self.snapshot(0,'RESTORATION_ENTRY',[dict(self.first,sha256='b'*64,bytes=13)],changes=[change])];self.value['assetLifecycle'][0]['diskMismatchCount']=1
  r.bounded_native_diagnostic(self.value)
  change['beforeSha256']='f'*64
  with self.assertRaisesRegex(Exception,'DISK_CHAIN'):r.bounded_native_diagnostic(self.value)
 def test_early_android_argument_failure_remains_schema2_without_claiming_identity(self):
  self.value.update(stage='INPUT',producerRunUrl='',consumerIdentityMatched=False,runIdentity='UNVALIDATED',errorClass='DIAGNOSTIC_ARGUMENT',dependencyExpectedCount=0,dependencyActualCount=0,assetLifecycle=[])
  r.DIAGNOSTIC.write_text(json.dumps(self.value));receipt=r.diagnose();self.assertFalse(receipt['buildReady']);self.assertEqual(1,len(receipt['files']))
  self.assertEqual(self.value,json.loads((r.EXPORT/'native-diagnostic.json').read_text()))
 def test_android_diagnostic_schema_argument_is_explicit_container_parameter(self):
  import yaml
  root=Path(__file__).resolve().parents[4];workflow=yaml.safe_load((root/'.github/workflows/desert-rv-journey-android.yml').read_text());native=next(s for s in workflow['jobs']['prepare']['steps'] if s.get('id')=='restore_native')
  args=native['with']['customParameters'].split();self.assertEqual(1,args.count('-journeyRestorationDiagnosticSchema'));self.assertEqual('2',args[args.index('-journeyRestorationDiagnosticSchema')+1]);self.assertEqual(1,args.count('-journeyRestorationRunId'))
 def test_gate_membership_bound_at_original_gate_preserves_object_scope(self):
  bound=[dict(self.first,transition='RETAINED',captureGateMembership='INCLUDED'),dict(self.second,transition='RETAINED',captureGateMembership='INCLUDED')]
  sample=self.snapshot(1,'CAPTURE_GATE_BEFORE',bound);sample.update(captureGateBound=True,captureGateObjectCount=2);self.value['assetLifecycle'].append(sample)
  r.bounded_native_diagnostic(self.value)
  sample['captureGateObjectCount']=1
  with self.assertRaisesRegex(Exception,'LIFECYCLE_COUNTS'):r.bounded_native_diagnostic(self.value)
 def test_schema2_fixed_size_budget_allows_128k_to_512k_without_truncation(self):
  raw=json.dumps(self.value);r.DIAGNOSTIC.write_text(raw+' '*(129*1024-len(raw)))
  receipt=r.diagnose();self.assertEqual(1,len(receipt['files']));self.assertEqual(self.value,json.loads((r.EXPORT/'native-diagnostic.json').read_text()))
 def test_schema2_oversize_is_rejected_with_specific_code(self):
  raw=json.dumps(self.value);r.DIAGNOSTIC.write_text(raw+' '*(512*1024+1-len(raw)))
  receipt=r.diagnose();self.assertEqual([],receipt['files']);self.assertEqual('RESTORE_DIAGNOSTIC_SIZE',receipt['failure']['errorCode'])
 def test_first_success_after_failed_entry_remains_preexisting_baseline(self):
  failed=self.snapshot(0,'RESTORATION_ENTRY');failed.update(status='FAILED',errorCode='IO')
  baseline=self.snapshot(1,'RESTORATION_SCENE_RESTORE_BEFORE',[self.first,self.second]);baseline['preexistingBaseline']=True
  self.value['assetLifecycle']=[failed,baseline];r.bounded_native_diagnostic(self.value)
  baseline['preexistingBaseline']=False
  with self.assertRaisesRegex(Exception,'LIFECYCLE_SEQUENCE'):r.bounded_native_diagnostic(self.value)
 def test_lifecycle_failed_snapshot_is_explicit_and_does_not_invent_clean(self):
  failure=self.snapshot(1,'POSES_AFTER');failure.update(status='FAILED',errorCode='IO');self.value['assetLifecycle'].append(failure)
  self.value['assetLifecycle'].append(self.snapshot(2,'RESTORATION_SCENE_RESTORE_BEFORE',[dict(x,transition='RETAINED') for x in (self.first,self.second)]));r.bounded_native_diagnostic(self.value)
  failure['objectCount']=1
  with self.assertRaisesRegex(Exception,'LIFECYCLE_FAILED'):r.bounded_native_diagnostic(self.value)

class NativeReportTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name);project=root/'tasks/desert-rv/unity';project.mkdir(parents=True)
  selected=json.loads((r.ROOT/r.SELECTION).read_text());selection=root/r.SELECTION;selection.parent.mkdir(parents=True);selection.write_text(json.dumps(selected))
  for key,val in [('ROOT',root),('PROJECT',project),('SOURCE_PROOF',project/'source-proof.json'),('INPUT',project/'input.json')]:
   patch=mock.patch.object(r,key,val);patch.start();self.addCleanup(patch.stop)
  r.SOURCE_PROOF.write_text('{}');r.INPUT.write_text('{}');patch=mock.patch.dict(os.environ,GITHUB_SHA='c'*40,GITHUB_RUN_ID='77');patch.start();self.addCleanup(patch.stop)
  rows=[]
  for region in selected['integration']['regions']:
   for actor in region['guards']+region['roadBeasts']+[e for wave in region['waves'] for e in wave['enemies']]:
    hit=dict(actor['position'],y=-.04);rows.append(dict(id=actor['id'],kind=actor['kind'],region=region['region'],scene=r.generated.REGION_SCENES[region['region']],floor='Route foundation',layer=0,declaredPosition=actor['position'],resolvedPosition=hit,hitPoint=hit,hitNormal=dict(x=0,y=1,z=0),yaw=actor['yaw']))
  ground=dict(schema=1,status='ACTUAL_NATIVE_ROOT_GROUNDING_UNREVIEWED',sourceCommit='c'*40,source=r.generated.GROUND_SOURCE,selectionSha256=r.sha(selection),readyInputSha256=r.sha(r.INPUT),approved=False,rows=rows)
  outputs=[]
  for name in ('JourneyBootstrap.unity','FirstStation.unity','Scrapyard.unity','NightBeacon.unity','JourneyContent.asset'):
   path='Assets/DesertRV/Scenes/Journey/'+name;file=project/path;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('fixture '+name);outputs.append(dict(path=path,sha256=r.sha(file),dependencyHash='a'*32,dependencySha256='b'*64))
  self.bundle=dict(receipt=dict(integrationOutputs=copy.deepcopy(outputs)),native=dict(dependencies=[]),ground=copy.deepcopy(ground))
  self.report=dict(schema=1,label=r.REPORT_LABEL,sourceCommit='c'*40,producerRunUrl=r.current_run(),assetProducerSourceCommit=r.PRODUCER['sourceCommit'],assetProducerRunUrl=r.RUN_URL,generatedReceiptSha256=r.PRODUCER['generatedReceiptSha256'],sourceTransitionProof=r.pin(r.SOURCE_PROOF),requestSha256=r.sha(r.INPUT),unityVersion=r.generated.UNITY,sourceBytesUnchanged=True,originalAssetsUnchanged=True,structureValidated=True,productionApprovalRejected=True,approved=False,scopeReused=False,scenes=outputs,dependencies=[],grounding=ground)
 def check(self):return r.validate_native_report(self.report,self.bundle)
 def test_current_report_matches_pinned_bytes(self):self.check()
 def test_old_consumer_report_is_rejected(self):
  self.report['sourceCommit']=r.PRODUCER['sourceCommit']
  with self.assertRaisesRegex(Exception,'REPORT_IDENTITY'):self.check()
 def test_approval_or_scope_reuse_is_rejected(self):
  for key in ('approved','scopeReused'):
   self.report[key]=True
   with self.assertRaisesRegex(Exception,'NOT_READY'):self.check()
   self.report[key]=False
 def test_structure_or_protection_false_is_rejected(self):
  for key in ('structureValidated','sourceBytesUnchanged','originalAssetsUnchanged','productionApprovalRejected'):
   self.report[key]=False
   with self.assertRaisesRegex(Exception,'NOT_READY'):self.check()
   self.report[key]=True
 def test_changed_native_dependency_is_rejected(self):
  self.report['dependencies'].append(dict(path='Assets/unknown'))
  with self.assertRaisesRegex(Exception,'DEPENDENCY_BYTES_CHANGED'):self.check()
 def test_duplicate_scene_is_rejected(self):
  self.report['scenes'][0]=self.report['scenes'][1]
  with self.assertRaisesRegex(Exception,'SCENE_SET'):self.check()
 def test_scene_byte_tampering_is_rejected(self):
  (r.PROJECT/self.report['scenes'][0]['path']).write_text('changed')
  with self.assertRaisesRegex(Exception,'SCENE_PIN'):self.check()
 def test_actual_grounding_beyond_precision_bound_is_rejected(self):
  row=self.report['grounding']['rows'][0];row['resolvedPosition']=dict(row['resolvedPosition'],y=-.03);row['hitPoint']=dict(row['hitPoint'],y=-.03)
  with self.assertRaisesRegex(Exception,'GROUNDING_CHANGED'):self.check()
 def test_unknown_report_field_cannot_be_publicly_exported(self):
  self.report['privateLog']='do not export'
  with self.assertRaisesRegex(Exception,'REPORT_IDENTITY'):self.check()

if __name__=='__main__':unittest.main(verbosity=2)
