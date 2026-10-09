"""Execute only rejection-stubbed shell prefixes and mocked shared guard routing; never cleanup or Unity."""
import os,subprocess,unittest,importlib
from pathlib import Path
from unittest import mock
from contextlib import ExitStack
ROUTES = [('r4', 'desert-rv-environment-v4-r4.yml', 'environment_v4_r4_dispatch'), ('v4', 'desert-rv-environment-v4.yml', 'environment_v4_dispatch'), ('r2', 'desert-rv-environment-v4-r2.yml', 'environment_v4_r2_dispatch'), ('r3', 'desert-rv-environment-v4-r3.yml', 'environment_v4_r3_dispatch'), ('discovery', 'desert-rv-armored-v004-r1-discovery.yml', 'armored_v004_discovery_dispatch'), ('strict', 'desert-rv-armored-v004-r1-strict.yml', 'armored_v004_strict_dispatch'), ('rebuild', 'desert-rv-journey-rebuild.yml', 'journey_rebuild_dispatch'), ('probe', 'desert-rv-environment-terrain-probe.yml', 'environment_terrain_probe_dispatch'), ('comparison', 'desert-rv-environment-diffuse-comparison.yml', 'environment_diffuse_comparison_dispatch'), ('comparison_r1', 'desert-rv-environment-diffuse-comparison-r1.yml', 'environment_diffuse_comparison_r1_dispatch')]
class RunnerPrefixTests(unittest.TestCase):
 def run_prefix(self,updates=None):
  script=(Path(__file__).parent/'prepare_runner.sh').read_text().split('test -n "${UNITY_LICENSE:-}"',1)[0]
  script=script.replace('/usr/bin/python3','python_stub')
  script='python_stub() { printf "ROUTED:%s\\n" "$*"; return 91; }\n'+script+'\nprintf "PREFIX_ACCEPTED\\n"\n'
  env={k:v for k,v in os.environ.items() if not k.startswith(('GITHUB_','RUNNER_','UNITY_'))}
  env.update(RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',GITHUB_ACTIONS='true',GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF='yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r4.yml@refs/heads/main')
  env.update(updates or {})
  return subprocess.run(['bash','-c',script],env=env,capture_output=True,text=True)
 def assert_route(self,workflow,helper):
  result=self.run_prefix({'GITHUB_WORKFLOW_REF':'yangerstar1/task-workbench/.github/workflows/'+workflow+'@refs/heads/main'})
  self.assertEqual(result.returncode,91);self.assertIn(helper+'.py',result.stdout);self.assertNotIn('PREFIX_ACCEPTED',result.stdout)
  for _,_,other in ROUTES:
   if other!=helper:self.assertNotIn(other+'.py',result.stdout)
 def test_r4_exact_route(self):self.assert_route('desert-rv-environment-v4-r4.yml','environment_v4_r4_dispatch')
 def test_v4_exact_route(self):self.assert_route('desert-rv-environment-v4.yml','environment_v4_dispatch')
 def test_r2_exact_route(self):self.assert_route('desert-rv-environment-v4-r2.yml','environment_v4_r2_dispatch')
 def test_r3_exact_route(self):self.assert_route('desert-rv-environment-v4-r3.yml','environment_v4_r3_dispatch')
 def test_discovery_exact_route(self):self.assert_route('desert-rv-armored-v004-r1-discovery.yml','armored_v004_discovery_dispatch')
 def test_strict_exact_route(self):self.assert_route('desert-rv-armored-v004-r1-strict.yml','armored_v004_strict_dispatch')
 def test_rebuild_exact_route(self):self.assert_route('desert-rv-journey-rebuild.yml','journey_rebuild_dispatch')
 def test_comparison_r1_exact_route(self):self.assert_route('desert-rv-environment-diffuse-comparison-r1.yml','environment_diffuse_comparison_r1_dispatch')
 def test_comparison_exact_route(self):self.assert_route('desert-rv-environment-diffuse-comparison.yml','environment_diffuse_comparison_dispatch')
 def test_probe_exact_route(self):self.assert_route('desert-rv-environment-terrain-probe.yml','environment_terrain_probe_dispatch')
 def test_unknown_workflow_reaches_only_existing_closed_rebuild_helper(self):self.assert_route('untrusted.yml','journey_rebuild_dispatch')
 def test_private_runner_stops_before_helper(self):
  r=self.run_prefix({'RUNNER_ENVIRONMENT':'self-hosted'});self.assertNotEqual(r.returncode,0);self.assertNotIn('ROUTED',r.stdout)
 def test_nonlinux_stops_before_helper(self):
  r=self.run_prefix({'RUNNER_OS':'macOS'});self.assertNotEqual(r.returncode,0);self.assertNotIn('ROUTED',r.stdout)
 def test_local_execution_stops_before_helper(self):
  r=self.run_prefix({'GITHUB_ACTIONS':'false'});self.assertNotEqual(r.returncode,0);self.assertNotIn('ROUTED',r.stdout)
 def test_missing_workflow_cannot_enter_r4_branch(self):
  r=self.run_prefix({'GITHUB_WORKFLOW_REF':''});self.assertEqual(r.returncode,91);self.assertNotIn('environment_v4_r4_dispatch.py',r.stdout)
 def test_existing_manual_prefix_is_unchanged(self):
  r=self.run_prefix({'GITHUB_EVENT_NAME':'workflow_dispatch'});self.assertEqual(r.returncode,0);self.assertIn('PREFIX_ACCEPTED',r.stdout);self.assertNotIn('ROUTED',r.stdout)
class SharedGuardRoutingTests(unittest.TestCase):
 def test_every_exact_route_and_unknown_fallback(self):
  import verify_evidence as v
  modules={name:importlib.import_module(name) for _,_,name in ROUTES}
  for _,workflow,expected in ROUTES+[('unknown','untrusted.yml','journey_rebuild_dispatch')]:
   with self.subTest(workflow=workflow),ExitStack() as stack:
    env=dict(GITHUB_ACTIONS='true',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF=v.REPOSITORY+'/.github/workflows/'+workflow+'@refs/heads/main')
    stack.enter_context(mock.patch.dict(os.environ,env,clear=True))
    calls={name:stack.enter_context(mock.patch.object(module,'verify',side_effect=ValueError('ROUTE:'+name))) for name,module in modules.items()}
    with self.assertRaisesRegex(ValueError,'ROUTE:'+expected):v.guard()
    for name,call in calls.items():self.assertEqual(call.call_count,1 if name==expected else 0)
if __name__=='__main__':unittest.main()
