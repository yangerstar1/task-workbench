"""Real filesystem fixtures for the fixed metadata-only probe; never executes Unity or Docker."""
import copy,hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
import journey_linux_template_probe as p

class MetadataTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.parent=Path(self.temp.name);self.root=self.parent/'module';self.root.mkdir();self.commit='a'*40;self.run='123'
  self.file=self.root/'Variations'/'observed_variant'/'UnityPlayer.so';self.file.parent.mkdir(parents=True);self.file.write_bytes(b'fixture bytes');self.file.chmod(0o755)
 def scan(self):return p.scan(self.root,self.commit,self.run)
 def check(self,x):return p.validate(x,self.commit,self.run)
 def reject(self,x):
  with self.assertRaises(ValueError):self.check(x)
 def test_complete_real_files_mode_size_hash(self):
  x=self.check(self.scan());self.assertTrue(x['complete']);self.assertEqual(3,x['totalEntries']);row=x['entries'][-1];self.assertEqual((0o755,13,p.digest(b'fixture bytes')),(row['mode'],row['bytes'],row['sha256']))
 def test_unknown_legal_hidden_unicode_names_preserved(self):
  for name in ('.official-data','Library[1].so','官方.so','file:name'):(self.root/name).write_bytes(b'plain fixture')
  x=self.check(self.scan());self.assertTrue(x['complete']);self.assertTrue({'.official-data','Library[1].so','官方.so','file:name'}<={r['path'] for r in x['entries']})
 def test_control_name_redacted_not_claimed_complete(self):
  (self.root/'not\npublic').write_bytes(b'private fixture');x=self.check(self.scan());self.assertFalse(x['complete']);self.assertEqual('INVALID_NAME',x['omissions'][0]['reason']);self.assertNotIn('not\\npublic',json.dumps(x))
 def test_sensitive_name_redacted(self):
  (self.root/'credentials.json').write_bytes(b'private fixture');x=self.check(self.scan());self.assertFalse(x['complete']);self.assertEqual('SENSITIVE',x['omissions'][0]['reason']);self.assertNotIn('credentials.json',json.dumps(x))
 def test_inside_symlink_not_traversed(self):
  (self.root/'alias').symlink_to('Variations');x=self.check(self.scan());row=next(r for r in x['entries'] if r['path']=='alias');self.assertTrue(row['targetWithinModule']);self.assertEqual('Variations',row['target']);self.assertEqual(4,x['totalEntries'])
 def test_external_symlink_never_exposes_target(self):
  (self.root/'alias').symlink_to('/outside/private-target');x=self.check(self.scan());row=next(r for r in x['entries'] if r['path']=='alias');self.assertFalse(row['targetWithinModule']);self.assertEqual('',row['target']);self.assertEqual(p.digest(b'/outside/private-target'),row['targetSha256']);self.assertNotIn('private-target',json.dumps(x))
 def test_escape_then_return_chain_remains_external(self):
  outside=self.parent/'outside';outside.mkdir();(outside/'back').symlink_to(self.root/'Variations');(self.root/'alias').symlink_to('../outside/back');x=self.check(self.scan());row=next(r for r in x['entries'] if r['path']=='alias');self.assertFalse(row['targetWithinModule'])
 def test_internal_chain_cannot_escape(self):
  (self.root/'a').symlink_to('b');(self.root/'b').symlink_to('/outside/no-read');x=self.check(self.scan());self.assertTrue(all(not r['targetWithinModule'] for r in x['entries'] if r['kind']=='SYMLINK'))
 def test_symlink_cycle_bounded(self):
  (self.root/'a').symlink_to('b');(self.root/'b').symlink_to('a');x=self.check(self.scan());self.assertTrue(all(not r['targetWithinModule'] for r in x['entries'] if r['kind']=='SYMLINK'))
 def test_linked_root_rejected(self):
  link=self.parent/'link';link.symlink_to(self.root);x=p.scan(link,self.commit,self.run);self.assertEqual('UNSAFE_ROOT',x['failureCode']);self.assertFalse(x['complete'])
 def test_missing_root_reports_fixed_failure(self):
  x=p.scan(self.parent/'missing',self.commit,self.run);self.check(x);self.assertEqual('MODULE_MISSING',x['failureCode'])
 def test_entry_budget_reports_no_false_complete(self):
  with mock.patch.object(p,'MAX_ENTRIES',1):x=self.check(self.scan());self.assertEqual('ENTRY_BUDGET',x['failureCode'])
 def test_file_budget_reports_no_false_complete(self):
  with mock.patch.object(p,'MAX_FILE',2):x=self.check(self.scan());self.assertEqual('BYTE_BUDGET',x['failureCode'])
 def test_total_budget_reports_no_false_complete(self):
  with mock.patch.object(p,'MAX_BYTES',2):x=self.check(self.scan());self.assertEqual('BYTE_BUDGET',x['failureCode'])
 def test_host_complete_cannot_exceed_entry_budget(self):
  x=self.scan()
  with mock.patch.object(p,'MAX_ENTRIES',2):self.reject(x)
 def test_host_complete_cannot_exceed_byte_budget(self):
  x=self.scan()
  with mock.patch.object(p,'MAX_BYTES',2):self.reject(x)
 def test_incomplete_entry_grace_requires_matching_failure(self):
  x=self.scan();x['complete']=False;x['failureCode']='IO_ERROR'
  with mock.patch.object(p,'MAX_ENTRIES',2):self.reject(x)
 def test_incomplete_byte_grace_requires_matching_failure(self):
  x=self.scan();x['complete']=False;x['failureCode']='IO_ERROR'
  with mock.patch.object(p,'MAX_BYTES',2):self.reject(x)
 def test_fifo_recorded_without_opening(self):
  os.mkfifo(self.root/'fifo');x=self.check(self.scan());self.assertEqual('UNSUPPORTED_KIND',x['failureCode']);self.assertFalse(x['complete'])
 def test_actual_file_identity_swap_rejected(self):
  old=self.file.stat();self.file.unlink();self.file.write_bytes(b'changed longer data')
  with self.assertRaisesRegex(ValueError,'FILE_CHANGED'):p.read_file(self.file,old)
 def test_extra_top_key_rejected(self):x=self.scan();x['unexpected']='value';self.reject(x)
 def test_wrong_commit_run_image_root_version_rejected(self):
  for key in ('sourceCommit','runUrl','image','moduleRoot','unityVersion'):
   x=self.scan();x[key]='wrong';self.reject(x)
 def test_wrong_mode_promises_rejected(self):
  for key in ('moduleBytesExported','editorStarted','licenseUsed','producerRestored'):
   x=self.scan();x[key]=True;self.reject(x)
 def test_bad_schema_attempt_types_rejected(self):
  for key in ('schema','runAttempt'):
   x=self.scan();x[key]=True;self.reject(x)
 def test_incomplete_rows_cannot_claim_complete(self):x=self.scan();x['entries'].pop();self.reject(x)
 def test_duplicate_unsorted_path_rejected(self):
  x=self.scan();x['entries'].append(copy.deepcopy(x['entries'][0]));x['totalEntries']+=1;self.reject(x)
 def test_path_traversal_rejected(self):
  for name in ('../outside','/outside','a/../b','a//b','a/./b'):
   x=self.scan();x['entries'][0]['path']=name;self.reject(x)
 def test_extra_row_key_rejected(self):x=self.scan();x['entries'][0]['secret']='x';self.reject(x)
 def test_mode_type_rejected(self):x=self.scan();x['entries'][0]['mode']=True;self.reject(x)
 def test_invalid_file_digest_rejected(self):x=self.scan();x['entries'][-1]['sha256']='x';self.reject(x)
 def test_external_target_text_rejected(self):
  (self.root/'a').symlink_to('/outside');x=self.scan();row=next(r for r in x['entries'] if r['path']=='a');row['target']='/outside';self.reject(x)
 def test_duplicate_json_rejected(self):
  with self.assertRaises(ValueError):p.parse(b'{"schema":1,"schema":1}')
 def test_nonfinite_json_rejected(self):
  with self.assertRaises(ValueError):p.parse(b'{"value":NaN}')
 def test_oversize_json_rejected(self):
  with mock.patch.object(p,'MAX_JSON',2):
   with self.assertRaises(ValueError):p.parse(b'{"a":1}')
 def test_shallow_script_mount_can_import(self):
  target=self.parent/'probe.py';target.write_bytes(Path(p.__file__).read_bytes());subprocess.run([sys.executable,'-c','import runpy,sys; runpy.run_path(sys.argv[1],run_name="fixture")',str(target)],check=True,capture_output=True)
 def test_shallow_script_actual_main_scan_writes_valid_bytes(self):
  target=self.parent/'probe.py';target.write_bytes(Path(p.__file__).read_bytes());version=self.parent/'version';version.write_text(p.VERSION+'\n');output=self.parent/'metadata.json'
  bootstrap="import runpy,sys,pathlib,os; data=runpy.run_path(sys.argv[1],run_name='fixture'); entry=data['main']; g=entry.__globals__; g['ENGINE']=pathlib.Path(sys.argv[2]); g['VERSION_FILE']=pathlib.Path(sys.argv[3]); g['SCAN_OUTPUT']=pathlib.Path(sys.argv[4]); sys.argv=[sys.argv[1],'scan']; entry()"
  result=subprocess.run([sys.executable,'-c',bootstrap,str(target),str(self.root),str(version),str(output)],env=dict(os.environ,PROBE_SOURCE_COMMIT=self.commit,PROBE_RUN_ID=self.run),check=True,capture_output=True,text=True)
  self.assertIn('complete=true',result.stdout);self.assertEqual(0o644,output.stat().st_mode & 0o777)
  with mock.patch.object(p,'ENGINE',self.root):self.assertTrue(self.check(p.parse(output.read_bytes()))['complete'])
 def test_pinned_docker_layer_only_official_python(self):
  source=Path(p.__file__).with_name('TemplateProbe.Dockerfile').read_text();self.assertIn('FROM '+p.IMAGE,source);self.assertIn('apt-get install -y --no-install-recommends python3',source);self.assertNotIn('COPY ',source);self.assertNotIn('unity-editor',source)

if __name__=='__main__':unittest.main()
