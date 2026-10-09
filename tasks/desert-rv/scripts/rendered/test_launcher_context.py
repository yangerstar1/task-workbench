import json,os,pathlib,tempfile,unittest,subprocess
from unittest.mock import patch
import launcher_context as c
import startup_diagnostic as d
class LauncherContextTests(unittest.TestCase):
 def test_same_launchers_only_emit_booleans(self):
  with patch.dict(os.environ,{'HOME':'/private/user_canary','XDG_RUNTIME_DIR':'/private/ipc_canary'},clear=True):a=c.snapshot();r=c.compare(a,c.snapshot())
  self.assertTrue(all(v['equal'] for v in r['fields'].values()));self.assertNotIn('canary',json.dumps(r));self.assertNotIn('digest',json.dumps(r));self.assertEqual(r['scope'],c.SCOPE)
 def test_changed_home_and_default_profile_roots(self):
  with patch.dict(os.environ,{'HOME':'/a'},clear=True):a=c.snapshot()
  with patch.dict(os.environ,{'HOME':'/b'},clear=True):b=c.snapshot()
  r=c.compare(a,b);self.assertFalse(r['fields']['home']['equal']);self.assertFalse(r['fields']['profileConfigRoot']['equal']);self.assertTrue(r['fields']['uid']['equal'])
 def test_xdg_override_distinct_from_home(self):
  with patch.dict(os.environ,{'HOME':'/a','XDG_CONFIG_HOME':'/fixed'},clear=True):a=c.snapshot()
  with patch.dict(os.environ,{'HOME':'/b','XDG_CONFIG_HOME':'/fixed'},clear=True):b=c.snapshot()
  self.assertTrue(c.compare(a,b)['fields']['profileConfigRoot']['equal'])
 def test_unset_and_empty_are_distinct(self):
  with patch.dict(os.environ,{},clear=True):a=c.snapshot()
  with patch.dict(os.environ,{'XDG_RUNTIME_DIR':''},clear=True):b=c.snapshot()
  r=c.compare(a,b)['fields']['xdgRuntime'];self.assertFalse(r['equal']);self.assertFalse(r['beforePresent']);self.assertTrue(r['afterPresent'])
 def test_exists_without_reading_contents(self):
  with tempfile.TemporaryDirectory() as td:
   with patch.dict(os.environ,{'HOME':td},clear=True),patch.object(pathlib.Path,'read_text',side_effect=AssertionError('no contents')):a=c.snapshot()
   self.assertTrue(a['home']['exists'])
 def test_changed_uid_only_boolean(self):
  with patch('os.getuid',return_value=1001):a=c.snapshot()
  with patch('os.getuid',return_value=1002):b=c.snapshot()
  r=c.compare(a,b);self.assertFalse(r['fields']['uid']['equal']);self.assertNotIn('1001',json.dumps(r))
 def test_schema_rejects_raw_or_numeric_details(self):
  a=c.snapshot()
  for name,value in [('raw','secret'),('equal',1)]:
   r=c.compare(a,a);r['fields']['home'][name]=value
   with self.assertRaises(ValueError):c.validate(r)
 def test_missing_report_unavailable(self):self.assertEqual(c.load('/nonexistent/launcher-context.json'),c.empty())
 def test_cli_roundtrip_private_only(self):
  with tempfile.TemporaryDirectory() as td:
   with patch('sys.argv',['probe','before',td]):self.assertEqual(c.main(),0)
   with patch('sys.argv',['probe','after',td]):self.assertEqual(c.main(),0)
   self.assertEqual(c.load(pathlib.Path(td)/'launcher-context.json')['status'],'OBSERVED')
 def test_symlink_report_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);(p/'real').write_text(json.dumps(c.empty()));(p/'link').symlink_to(p/'real');self.assertEqual(c.load(p/'link'),c.empty())
 def test_diagnostic_embeds_only_valid_context(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);(p/'Assets/DesertRV').mkdir(parents=True);a=c.snapshot();(p/'launcher-context.json').write_text(json.dumps(c.compare(a,a)))
   self.assertEqual(d.classify(p,p)['launcherContext']['status'],'OBSERVED')
 def test_probe_order_and_no_auth_change(self):
  s=pathlib.Path(__file__).resolve().parent
  entry=(s/'container_entry.sh').read_text();raw=(s.parent/'run_rendered_diagnostic.sh').read_text()
  self.assertLess(entry.index('launcher_context.py before'),entry.index("source /gameci/platforms/ubuntu/activate.sh"))
  self.assertLess(raw.index('launcher_context.py" after'),raw.index('15m "$UNITY_EDITOR"'))
  self.assertIn('env -u UNITY_LICENSE -u UNITY_EMAIL -u UNITY_PASSWORD -u UNITY_SERIAL',entry)
 def test_probe_failure_does_not_skip_original_launch(self):
  scripts=pathlib.Path(__file__).resolve().parent
  for path in (scripts/'container_entry.sh',scripts.parent/'run_rendered_diagnostic.sh'):
   fragment=next(line for line in path.read_text().splitlines() if 'launcher_context.py' in line)
   shell='set -e\ntimeout() { return 1; }\nprivate=/unused\nprivate_logs=/unused\nscript_dir=/unused\n'+fragment+'\nprintf ORIGINAL_LAUNCH_REACHED\n'
   result=subprocess.run(['bash','-c',shell],capture_output=True,text=True)
   self.assertEqual(result.returncode,0);self.assertEqual(result.stdout,'ORIGINAL_LAUNCH_REACHED')
   self.assertIn('--kill-after=1s 3s',fragment)
if __name__=='__main__':unittest.main()
