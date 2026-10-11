"""Finite actual PNG/CSV/hash/XML corruption checks; never native execution."""
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import xml.etree.ElementTree as ET
from PIL import Image,ImageDraw
import journey_mobile_hud_native as gate

class MobileHudNativeGateTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  change=patch.object(gate,'ROOT',self.root);change.start();self.addCleanup(change.stop)
  self.folder=self.root/'captures';self.folder.mkdir();self.entries=[]
  cache={}
  for profile,size in gate.PROFILES.items():
   image=Image.new('RGB',size,(210,215,220));draw=ImageDraw.Draw(image);draw.rectangle((50,50,size[0]-50,200),fill=(15,25,35))
   stream=io.BytesIO();image.save(stream,format='PNG');cache[profile]=stream.getvalue()
  for stem in gate.STEMS:
   profile,mode,background=stem.split('-')
   self.write(stem+'.png',cache[profile])
   self.write(stem+'-fit.csv',('profile,mode,background,label,font,available_height,preferred_height\n'+','.join((profile,mode,background,'Objective text','16','42','40'))+'\n').encode())
  self.manifest=dict(source='production JourneyHud graph and pinned CJK font',evidence='native simulated-device UI render; no physical-device or gameplay acceptance',files=self.entries)
  self.save()
 def write(self,name,data):
  (self.folder/name).write_bytes(data);self.entries.append(dict(name=name,bytes=len(data),sha256=gate.sha(data)))
 def save(self): (self.folder/gate.MANIFEST).write_text(json.dumps(self.manifest))
 def refresh(self,name):
  data=(self.folder/name).read_bytes()
  entry=next(x for x in self.entries if x['name']==name);entry.update(bytes=len(data),sha256=gate.sha(data));self.save()
 def test_actual_thirteen_pngs_and_fit_metrics_match_exact_inventory(self):
  result=gate.capture_inventory(self.folder);self.assertEqual(len(result),27);self.assertEqual(len(gate.STEMS),13)
 def test_missing_extra_and_changed_capture_cannot_pass(self):
  name=gate.STEMS[0]+'.png';p=self.folder/name;original=p.read_bytes();p.unlink()
  with self.assertRaisesRegex(ValueError,'MOBILE_HUD_CAPTURE_INVENTORY'):gate.capture_inventory(self.folder)
  p.write_bytes(original);extra=self.folder/'old-snapshot.png';extra.write_bytes(original)
  with self.assertRaisesRegex(ValueError,'MOBILE_HUD_CAPTURE_INVENTORY'):gate.capture_inventory(self.folder)
  extra.unlink();p.write_bytes(original+b'changed')
  with self.assertRaisesRegex(ValueError,'MOBILE_HUD_CAPTURE_HASH'):gate.capture_inventory(self.folder)
 def test_resealed_wrong_size_or_blank_png_cannot_pass(self):
  name=gate.STEMS[0]+'.png';p=self.folder/name
  for size,code in [((8,8),'MOBILE_HUD_PNG_SHAPE'),(gate.PROFILES[gate.STEMS[0].split('-')[0]],'MOBILE_HUD_PNG_BLANK')]:
   Image.new('RGB',size,(0,0,0)).save(p);self.refresh(name)
   with self.subTest(size=size),self.assertRaisesRegex(ValueError,code):gate.capture_inventory(self.folder)
 def test_resealed_clipped_small_or_nonfinite_text_cannot_pass(self):
  name=gate.STEMS[0]+'-fit.csv';p=self.folder/name;original=p.read_text()
  for font,available,preferred in [('16','42','50'),('10','42','40'),('16','42','NaN')]:
   p.write_text(original.replace('16,42,40',','.join((font,available,preferred))));self.refresh(name)
   with self.subTest(values=(font,available,preferred)),self.assertRaisesRegex(ValueError,'MOBILE_HUD_FIT_CLIPPED'):gate.capture_inventory(self.folder)
 def test_duplicate_manifest_rows_cannot_hide_omitted_file(self):
  self.manifest['files'][-1]=copy.deepcopy(self.manifest['files'][0]);self.save()
  with self.assertRaisesRegex(ValueError,'MOBILE_HUD_CAPTURE_ROWS'):gate.capture_inventory(self.folder)
 def test_only_two_authored_world_views_and_exact_evidence_scope_pass(self):
  world=self.root/'world';world.mkdir();(world/'EVIDENCE.txt').write_text(gate.WORLD_EVIDENCE)
  for stem in gate.WORLD_STEMS:
   (world/(stem+'.png')).write_bytes((self.folder/'desktop-foot-glare.png').read_bytes())
   profile,mode,background=stem.split('-',2)
   (world/(stem+'-fit.csv')).write_text('profile,mode,background,label,font,available_height,preferred_height\n'+','.join((profile,mode,background,'Objective text','16','42','40'))+'\n')
  self.assertEqual(len(gate.world_inventory(world)),5)
  (world/'EVIDENCE.txt').write_text('Live gameplay accepted')
  with self.assertRaisesRegex(ValueError,'MOBILE_HUD_WORLD_SCOPE'):gate.world_inventory(world)
  (world/'EVIDENCE.txt').write_text(gate.WORLD_EVIDENCE);(world/'extra.png').write_bytes(b'old snapshot')
  with self.assertRaisesRegex(ValueError,'MOBILE_HUD_WORLD_INVENTORY'):gate.world_inventory(world)
 def test_exact_ten_native_cases_reject_missing_duplicate_extra_and_failure(self):
  folder=self.root/'xml';folder.mkdir();p=folder/'result.xml'
  def value():
   root=ET.Element('test-run',result='Passed',total='10',passed='10',failed='0',skipped='0',inconclusive='0')
   for name in gate.EXPECTED:ET.SubElement(root,'test-case',fullname=name,result='Passed')
   return root
  with patch.object(gate,'ARTIFACTS',folder):
   ET.ElementTree(value()).write(p);self.assertEqual(gate.inspect_xml()['count'],10)
   for mutation in ('missing','duplicate','extra','failure'):
    root=value()
    if mutation=='missing':root.remove(root[0])
    if mutation=='duplicate':root[1].set('fullname',root[0].get('fullname'))
    if mutation=='extra':ET.SubElement(root,'test-case',fullname='Other',result='Passed')
    if mutation=='failure':root[0].set('result','Failed')
    ET.ElementTree(root).write(p)
    with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'MOBILE_HUD_EXACT_TEN'):gate.inspect_xml()


class MobileHudWorldRoundtripTests(unittest.TestCase):
 """Synthetic PNGs exercise the real host exporter, not native/world visual acceptance."""
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.task=self.root/'tasks/desert-rv';self.world=self.task/'unity/JourneyEvidence/MobileHudWorld'
  self.export=self.task/'mobile-hud-world-export';self.prep=self.task/'journey-preparation-export/preparation.json'
  self.world.mkdir(parents=True);self.prep.parent.mkdir(parents=True)
  self.commit='a'*40;self.run='123';self.output=self.root/'output.txt'
  self.env=dict(GITHUB_SHA=self.commit,GITHUB_RUN_ID=self.run,GITHUB_RUN_ATTEMPT='1',NATIVE_OUTCOME='success',GITHUB_OUTPUT=str(self.output),WORLD_CAPTURE_MODE='same-workspace')
  for name,value in [('ROOT',self.root),('TASK',self.task),('WORLD_SOURCE',self.world),('WORLD_EXPORT',self.export),('WORLD_DIAGNOSTIC',self.task/'mobile-hud-world-diagnostic/world-diagnostic.json')]:
   change=patch.object(gate,name,value);change.start();self.addCleanup(change.stop)
  change=patch.dict(os.environ,self.env);change.start();self.addCleanup(change.stop)
  self.preparation=dict(sourceCommit=self.commit,status='PREPARED_EDITOR_SCOPE_UNREVIEWED',visualApproved=False,gameplayAccepted=False,
   nativeCase='DesertRV.Tests.JourneyPreparationTests.PrepareVerifiedSameWorkspaceJourney',generatedExport=dict(sha256='c'*64))
  self.prep.write_text(json.dumps(self.preparation))
  (self.world/'EVIDENCE.txt').write_text(gate.WORLD_EVIDENCE)
  for stem in gate.WORLD_STEMS:
   image=Image.new('RGB',(960,540),(170,150,80));ImageDraw.Draw(image).rectangle((50,50,500,220),fill=(10,30,50));image.save(self.world/(stem+'.png'))
   profile,mode,background=stem.split('-',2)
   (self.world/(stem+'-fit.csv')).write_text('profile,mode,background,label,font,available_height,preferred_height\n'+','.join((profile,mode,background,'Objective text','16','42','40'))+'\n')
 def call(self):
  log=io.StringIO()
  with patch.object(gate.sys,'argv',['journey_mobile_hud_native.py','world']),redirect_stdout(log):status=gate.main()
  return status,log.getvalue().strip()
 def fail(self,phase,code):
  status,log=self.call();self.assertEqual(status,2)
  self.assertEqual(log.splitlines()[0],'MOBILE_HUD_GATE_FAILED phase='+phase+' code='+code)
  self.assertFalse(self.output.exists() and 'world_verified=true' in self.output.read_text())
 def test_complete_world_entry_copies_pins_reports_and_writes_exact_success_outputs(self):
  original={p.name:p.read_bytes() for p in self.world.iterdir()};prepared=self.prep.read_bytes()
  self.assertEqual(self.call(),(0,'MOBILE_HUD_WORLD_VERIFIED'))
  self.assertEqual(self.output.read_text(),'world_verified=true\nexport_ready=true\nworld_diagnostic_written=true\n')
  self.assertEqual({p.name for p in self.export.iterdir()},{'captures','world-report.json'})
  self.assertEqual({p.name:p.read_bytes() for p in (self.export/'captures').iterdir()},original)
  report=json.loads((self.export/'world-report.json').read_bytes())
  self.assertEqual((report['sourceCommit'],report['runId'],report['runAttempt']),(self.commit,self.run,'1'))
  self.assertEqual(report['preparation'],gate.pin(self.prep));self.assertEqual(len(report['files']),5)
  self.assertFalse(report['approved']);self.assertFalse(report['deviceExecuted']);self.assertFalse(report['gameplayAccepted'])
  self.assertEqual(len(gate.verify_world()),6);self.assertEqual(self.prep.read_bytes(),prepared)
  self.assertEqual({p.name:p.read_bytes() for p in self.world.iterdir()},original)
 def test_second_world_run_cannot_overwrite_existing_export(self):
  self.assertEqual(self.call()[0],0);self.output.unlink()
  original={p.relative_to(self.export).as_posix():p.read_bytes() for p in self.export.rglob('*') if p.is_file()}
  self.fail('EXPORT_CREATE','MOBILE_HUD_WORLD_EXPORT_EXISTS')
  self.assertEqual({p.relative_to(self.export).as_posix():p.read_bytes() for p in self.export.rglob('*') if p.is_file()},original)
 def diagnostic(self):
  value=json.loads(gate.WORLD_DIAGNOSTIC.read_bytes());self.assertEqual(gate.validate_world_diagnostic(value),value)
  return value
 def test_diagnostic_success_has_fixed_schema_current_identity_and_empty_missing_list(self):
  self.assertEqual(self.call()[0],0);value=self.diagnostic()
  self.assertEqual((value['status'],value['phase'],value['code']),('PASSED','COMPLETE','NONE'))
  self.assertEqual(value['identity'],dict(sourceCommit=self.commit,runId=self.run,runAttempt='1'))
  self.assertEqual(value['inventory'],dict(pathDomain=gate.DIAGNOSTIC_DOMAIN,state='READABLE',missingNames=[],unexpectedCount=0))
  self.assertEqual({p.name for p in gate.WORLD_DIAGNOSTIC.parent.iterdir()},{'world-diagnostic.json'})
 def test_missing_root_diagnostic_lists_only_exact_five_allowed_names(self):
  for path in self.world.iterdir():path.unlink()
  self.world.rmdir();self.fail('CAPTURE_VALIDATION','MOBILE_HUD_WORLD_SOURCE_MISSING');value=self.diagnostic()
  self.assertEqual(value['inventory']['missingNames'],sorted(gate.WORLD_FILES));self.assertEqual(value['inventory']['unexpectedCount'],0)
  self.assertEqual(value['inventory']['state'],'MISSING');self.assertEqual(self.output.read_text(),'world_diagnostic_written=true\n')
 def test_missing_one_capture_diagnostic_lists_exact_missing_name(self):
  name=gate.WORLD_STEMS[0]+'.png';(self.world/name).unlink()
  self.fail('CAPTURE_VALIDATION','MOBILE_HUD_WORLD_INVENTORY');value=self.diagnostic()
  self.assertEqual(value['inventory']['missingNames'],[name]);self.assertEqual(value['inventory']['unexpectedCount'],0)
 def test_unknown_extra_name_is_counted_and_never_written_or_printed(self):
  secret_name='PRIVATE-CREDENTIAL-NAME.txt';(self.world/secret_name).write_text('PRIVATE CONTENT')
  status,log=self.call();self.assertEqual(status,2);value=self.diagnostic()
  self.assertEqual(value['inventory']['unexpectedCount'],1);self.assertEqual(value['inventory']['missingNames'],[])
  self.assertNotIn(secret_name,gate.WORLD_DIAGNOSTIC.read_text()+log);self.assertNotIn('PRIVATE CONTENT',gate.WORLD_DIAGNOSTIC.read_text()+log)
 def test_unreadable_world_directory_does_not_guess_missing_files(self):
  if os.geteuid()==0:self.skipTest('Root can bypass Unix read permissions.')
  self.world.chmod(0)
  try:
   self.fail('CAPTURE_VALIDATION','PERMISSION_DENIED');value=self.diagnostic()
   self.assertEqual(value['inventory']['state'],'UNREADABLE');self.assertEqual(value['inventory']['missingNames'],[])
   self.assertIsNone(value['inventory']['unexpectedCount'])
  finally:self.world.chmod(0o700)
 def test_diagnostic_no_overwrite_preserves_original_bytes_and_emits_no_new_flag(self):
  self.assertEqual(self.call()[0],0);original=gate.WORLD_DIAGNOSTIC.read_bytes();self.output.unlink()
  status,log=self.call();self.assertEqual(status,2)
  self.assertEqual(log.splitlines(),['MOBILE_HUD_GATE_FAILED phase=EXPORT_CREATE code=MOBILE_HUD_WORLD_EXPORT_EXISTS',
   'MOBILE_HUD_DIAGNOSTIC_NOT_PUBLISHED code=MOBILE_HUD_DIAGNOSTIC_EXISTS'])
  self.assertEqual(gate.WORLD_DIAGNOSTIC.read_bytes(),original);self.assertFalse(self.output.exists())
 def test_diagnostic_permission_failure_keeps_original_capture_error(self):
  if os.geteuid()==0:self.skipTest('Root can bypass Unix read permissions.')
  (self.world/(gate.WORLD_STEMS[0]+'.png')).unlink();gate.WORLD_DIAGNOSTIC.parent.mkdir();gate.WORLD_DIAGNOSTIC.parent.chmod(0)
  try:
   status,log=self.call();self.assertEqual(status,2)
   self.assertEqual(log.splitlines(),['MOBILE_HUD_GATE_FAILED phase=CAPTURE_VALIDATION code=MOBILE_HUD_WORLD_INVENTORY',
    'MOBILE_HUD_DIAGNOSTIC_NOT_PUBLISHED code=PERMISSION_DENIED'])
   self.assertFalse(self.output.exists())
  finally:gate.WORLD_DIAGNOSTIC.parent.chmod(0o700)
  self.assertFalse(gate.WORLD_DIAGNOSTIC.exists())
 def test_diagnostic_schema_rejects_injected_names_codes_domains_and_identity(self):
  self.assertEqual(self.call()[0],0);value=self.diagnostic()
  for key,replacement in [('phase','PRIVATE PHASE'),('code','PRIVATE CODE'),('identity',dict(sourceCommit='b'*40,runId='124',runAttempt='1'))]:
   changed=copy.deepcopy(value);changed[key]=replacement
   with self.assertRaisesRegex(ValueError,'MOBILE_HUD_DIAGNOSTIC_SCHEMA'):gate.validate_world_diagnostic(changed)
  for key,replacement in [('pathDomain','/private'),('missingNames',['private.txt']),('unexpectedCount',-1)]:
   changed=copy.deepcopy(value);changed['inventory'][key]=replacement
   with self.assertRaisesRegex(ValueError,'MOBILE_HUD_DIAGNOSTIC_SCHEMA'):gate.validate_world_diagnostic(changed)
 def test_missing_capture_tree_reports_specific_first_phase(self):
  for path in self.world.iterdir():path.unlink()
  self.world.rmdir();self.fail('CAPTURE_VALIDATION','MOBILE_HUD_WORLD_SOURCE_MISSING');self.assertFalse(self.export.exists())
 def test_native_failure_wins_over_missing_preparation_and_missing_capture(self):
  self.prep.unlink();os.environ['NATIVE_OUTCOME']='failure'
  self.fail('NATIVE_OUTCOME','MOBILE_HUD_WORLD_NATIVE_OUTCOME');self.assertFalse(self.export.exists())
 def test_missing_preparation_has_fixed_read_phase(self):
  self.prep.unlink();self.fail('PREPARATION_READ','FILE_MISSING')
 def test_malformed_preparation_never_prints_raw_error_or_contents(self):
  self.prep.write_text('{"private-token":"DO-NOT-PRINT"')
  self.fail('PREPARATION_READ','JSON_INVALID')
 def test_preparation_producer_cannot_masquerade_as_current_consumer(self):
  self.preparation['sourceCommit']='b'*40;self.prep.write_text(json.dumps(self.preparation))
  self.fail('PREPARATION_IDENTITY','MOBILE_HUD_WORLD_PREPARATION')
 def test_invalid_current_identity_cannot_export(self):
  os.environ['GITHUB_RUN_ATTEMPT']='2';self.fail('PREPARATION_IDENTITY','IDENTITY')
 def test_invalid_world_mode_is_explicit(self):
  os.environ['WORLD_CAPTURE_MODE']='guess';self.fail('PREPARATION_IDENTITY','MOBILE_HUD_WORLD_MODE')
 def test_actual_read_permission_failure_is_safe_and_actionable(self):
  if os.geteuid()==0:self.skipTest('Root can bypass Unix read permissions.')
  self.prep.chmod(0)
  try:self.fail('PREPARATION_READ','PERMISSION_DENIED')
  finally:self.prep.chmod(0o600)
  self.assertFalse(self.export.exists())
 def test_actual_capture_permission_failure_does_not_start_copy(self):
  if os.geteuid()==0:self.skipTest('Root can bypass Unix read permissions.')
  path=self.world/(gate.WORLD_STEMS[0]+'-fit.csv');path.chmod(0)
  try:self.fail('CAPTURE_VALIDATION','PERMISSION_DENIED')
  finally:path.chmod(0o600)
  self.assertFalse(self.export.exists())
 def test_invalid_csv_dimensions_stop_full_export(self):
  path=self.world/(gate.WORLD_STEMS[0]+'-fit.csv');path.write_text(path.read_text().replace('16,42,40','16,42,70'))
  self.fail('CAPTURE_VALIDATION','MOBILE_HUD_FIT_CLIPPED');self.assertFalse(self.export.exists())
 def test_wrong_csv_region_stops_full_export(self):
  path=self.world/(gate.WORLD_STEMS[0]+'-fit.csv');path.write_text(path.read_text().replace('region-1','region-3'))
  self.fail('CAPTURE_VALIDATION','MOBILE_HUD_FIT_ROW');self.assertFalse(self.export.exists())
 def test_symlinked_capture_cannot_be_copied(self):
  path=self.world/(gate.WORLD_STEMS[0]+'.png');outside=self.root/'outside.png';path.rename(outside);path.symlink_to(outside)
  self.fail('CAPTURE_VALIDATION','UNSAFE_PATH');self.assertFalse(self.export.exists())
 def test_source_change_between_validation_and_copy_cannot_be_resealed(self):
  real=gate.world_report
  def mutate(folder):
   report=real(folder)
   if folder==self.world:
    path=self.world/'EVIDENCE.txt';path.write_bytes(path.read_bytes()+b'changed')
   return report
  with patch.object(gate,'world_report',mutate):self.fail('EXPORT_COPY','MOBILE_HUD_WORLD_COPY_CHANGED')
  self.assertFalse((self.export/'world-report.json').exists())
 def test_report_tamper_is_detected_on_verification(self):
  self.assertEqual(self.call()[0],0)
  path=self.export/'world-report.json';value=json.loads(path.read_text());value['runId']='124';path.write_text(json.dumps(value))
  with self.assertRaisesRegex(gate.GateFailure,'MOBILE_HUD_WORLD_REPORT_CHANGED'):gate.verify_world()
 def restored_fixture(self):
  os.environ['WORLD_CAPTURE_MODE']='restored';self.preparation['sourceCommit']='b'*40;self.prep.write_text(json.dumps(self.preparation))
  report=self.task/'unity/JourneyEvidence/JourneyPreparation/restoration-revalidated.json';report.parent.mkdir()
  value=dict(label='RESTORED_JOURNEY_NATIVE_REVALIDATED_UNREVIEWED',sourceCommit=self.commit,
   producerRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/'+self.run,
   assetProducerSourceCommit='b'*40,assetProducerRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/100',
   generatedReceiptSha256='c'*64,sourceBytesUnchanged=True,originalAssetsUnchanged=True,structureValidated=True,approved=False,scopeReused=False)
  report.write_text(json.dumps(value));checks=[]
  module=SimpleNamespace(REPORT=report,RUN_URL=value['assetProducerRunUrl'],PRODUCER=dict(generatedReceiptSha256='c'*64),verify=lambda:checks.append('verified'))
  return module,value,checks
 def test_restored_branch_keeps_distinct_producer_and_consumer_and_calls_native_gate(self):
  # Boundary stub only; all world reads, images, CSVs, copies, pins, reports and outputs are real.
  restore,value,checks=self.restored_fixture();original=self.prep.read_bytes()
  with patch.object(gate,'load_restoration',return_value=restore):
   self.assertEqual(self.call(),(0,'MOBILE_HUD_WORLD_VERIFIED'));self.assertEqual(len(gate.verify_world()),6)
  self.assertGreaterEqual(len(checks),4);report=json.loads((self.export/'world-report.json').read_text())
  self.assertEqual(report['sourceCommit'],self.commit);self.assertEqual(report['assetProducerSourceCommit'],'b'*40)
  self.assertEqual(report['restoration'],gate.pin(restore.REPORT));self.assertEqual(self.prep.read_bytes(),original)
 def test_restored_branch_rejects_failed_native_source_gate(self):
  restore,value,checks=self.restored_fixture()
  def reject():raise ValueError('PRIVATE-UPSTREAM-TOKEN-NOT-ALLOWED')
  restore.verify=reject
  with patch.object(gate,'load_restoration',return_value=restore):self.fail('RESTORATION_VERIFY','VALIDATION_FAILED')
  self.assertFalse(self.export.exists())
 def test_allowlisted_upstream_valueerror_subclass_keeps_exact_fixed_code(self):
  restore,value,checks=self.restored_fixture()
  class StrictFailure(ValueError):pass
  def reject():raise StrictFailure('RESTORE_NATIVE_DEPENDENCY_BYTES_CHANGED')
  restore.verify=reject
  with patch.object(gate,'load_restoration',return_value=restore):self.fail('RESTORATION_VERIFY','RESTORE_NATIVE_DEPENDENCY_BYTES_CHANGED')
 def test_second_restoration_invariance_check_prevents_success_after_copy(self):
  restore,value,checks=self.restored_fixture()
  def verify():
   checks.append('verified')
   if len(checks)==2:raise ValueError('RESTORE_PUBLIC_BUNDLE_CHANGED')
  restore.verify=verify
  with patch.object(gate,'load_restoration',return_value=restore):self.fail('RESTORATION_VERIFY','RESTORE_PUBLIC_BUNDLE_CHANGED')
  self.assertFalse((self.export/'world-report.json').exists())
 def test_restored_branch_rejects_relabelled_original_producer(self):
  restore,value,checks=self.restored_fixture();value['assetProducerSourceCommit']=self.commit;restore.REPORT.write_text(json.dumps(value))
  with patch.object(gate,'load_restoration',return_value=restore):self.fail('RESTORATION_VERIFY','MOBILE_HUD_WORLD_RESTORATION')

if __name__=='__main__':unittest.main()
