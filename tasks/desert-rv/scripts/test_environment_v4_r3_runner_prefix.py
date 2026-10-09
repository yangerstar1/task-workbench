"""Test guard routing only; never execute runner cleanup or any engine locally."""
import os,subprocess,unittest
from pathlib import Path
class RunnerPrefixTests(unittest.TestCase):
 def run_prefix(self,updates=None):
  script=(Path(__file__).parent/'prepare_runner.sh').read_text().split('test -n "${UNITY_LICENSE:-}"',1)[0]
  # Stub is deliberately rejection-only. Each identity helper has separate actual Git tests.
  script=script.replace('/usr/bin/python3','python_stub')
  script='python_stub() { printf "ROUTED:%s\\n" "$*"; return 91; }\n'+script+'\nprintf "PREFIX_ACCEPTED\\n"\n'
  env={k:v for k,v in os.environ.items() if not k.startswith(('GITHUB_','RUNNER_','UNITY_'))}
  env.update(RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',GITHUB_ACTIONS='true',GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF='yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r3.yml@refs/heads/main')
  env.update(updates or {})
  return subprocess.run(['bash','-c',script],env=env,capture_output=True,text=True)
 def test_v4_workflow_routes_only_to_v4_helper(self):
  r=self.run_prefix();self.assertEqual(r.returncode,91);self.assertIn('environment_v4_r3_dispatch.py',r.stdout);self.assertNotIn('journey_rebuild_dispatch.py',r.stdout)
 def test_previous_v4_workflow_keeps_its_exact_helper(self):
  r=self.run_prefix({'GITHUB_WORKFLOW_REF':'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4.yml@refs/heads/main'});self.assertEqual(r.returncode,91);self.assertIn('environment_v4_dispatch.py',r.stdout);self.assertNotIn('environment_v4_r3_dispatch.py',r.stdout)
 def test_previous_r2_workflow_keeps_its_exact_helper(self):
  r=self.run_prefix({'GITHUB_WORKFLOW_REF':'yangerstar1/task-workbench/.github/workflows/desert-rv-environment-v4-r2.yml@refs/heads/main'});self.assertEqual(r.returncode,91);self.assertIn('environment_v4_r2_dispatch.py',r.stdout);self.assertNotIn('environment_v4_r3_dispatch.py',r.stdout)
 def test_discovery_workflow_keeps_its_exact_helper(self):
  r=self.run_prefix({'GITHUB_WORKFLOW_REF':'yangerstar1/task-workbench/.github/workflows/desert-rv-armored-v004-r1-discovery.yml@refs/heads/main'});self.assertEqual(r.returncode,91);self.assertIn('armored_v004_discovery_dispatch.py',r.stdout);self.assertNotIn('environment_v4_r3_dispatch.py',r.stdout)
 def test_rebuild_workflow_keeps_original_helper(self):
  r=self.run_prefix({'GITHUB_WORKFLOW_REF':'yangerstar1/task-workbench/.github/workflows/desert-rv-journey-rebuild.yml@refs/heads/main'});self.assertEqual(r.returncode,91);self.assertIn('journey_rebuild_dispatch.py',r.stdout)
 def test_unknown_workflow_is_rejected_by_existing_closed_guard(self):
  r=self.run_prefix({'GITHUB_WORKFLOW_REF':'untrusted'});self.assertEqual(r.returncode,91);self.assertNotIn('PREFIX_ACCEPTED',r.stdout)
 def test_private_runner_stops_before_helper(self):
  r=self.run_prefix({'RUNNER_ENVIRONMENT':'self-hosted'});self.assertNotEqual(r.returncode,0);self.assertNotIn('ROUTED',r.stdout)
 def test_nonlinux_stops_before_helper(self):
  r=self.run_prefix({'RUNNER_OS':'macOS'});self.assertNotEqual(r.returncode,0);self.assertNotIn('ROUTED',r.stdout)
 def test_local_execution_stops_before_helper(self):
  r=self.run_prefix({'GITHUB_ACTIONS':'false'});self.assertNotEqual(r.returncode,0);self.assertNotIn('ROUTED',r.stdout)
 def test_missing_workflow_cannot_take_v4_branch(self):
  r=self.run_prefix({'GITHUB_WORKFLOW_REF':''});self.assertEqual(r.returncode,91);self.assertNotIn('environment_v4_r3_dispatch.py',r.stdout)
 def test_original_manual_prefix_remains_unchanged(self):
  r=self.run_prefix({'GITHUB_EVENT_NAME':'workflow_dispatch'});self.assertEqual(r.returncode,0);self.assertIn('PREFIX_ACCEPTED',r.stdout);self.assertNotIn('ROUTED',r.stdout)
class SharedGuardRoutingTests(unittest.TestCase):
 def test_exact_new_and_retained_routes(self):
  import verify_evidence as v
  from unittest import mock
  import environment_v4_dispatch,environment_v4_r2_dispatch,environment_v4_r3_dispatch,armored_v004_discovery_dispatch,journey_rebuild_dispatch
  modules=[environment_v4_dispatch,environment_v4_r2_dispatch,environment_v4_r3_dispatch,armored_v004_discovery_dispatch,journey_rebuild_dispatch]
  cases=[('desert-rv-environment-v4.yml',environment_v4_dispatch),('desert-rv-environment-v4-r2.yml',environment_v4_r2_dispatch),('desert-rv-environment-v4-r3.yml',environment_v4_r3_dispatch),('desert-rv-armored-v004-r1-discovery.yml',armored_v004_discovery_dispatch),('desert-rv-journey-rebuild.yml',journey_rebuild_dispatch),('untrusted.yml',journey_rebuild_dispatch)]
  from contextlib import ExitStack
  for workflow,expected in cases:
   with self.subTest(workflow=workflow),ExitStack() as stack:
    env=dict(GITHUB_ACTIONS='true',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF=v.REPOSITORY+'/.github/workflows/'+workflow+'@refs/heads/main')
    stack.enter_context(mock.patch.dict(os.environ,env,clear=True))
    calls={m:stack.enter_context(mock.patch.object(m,'verify',side_effect=ValueError('ROUTE:'+m.__name__))) for m in modules}
    with self.assertRaisesRegex(ValueError,'ROUTE:'+expected.__name__):v.guard()
    for module,call in calls.items():self.assertEqual(call.call_count,1 if module is expected else 0)
if __name__=='__main__':unittest.main()
