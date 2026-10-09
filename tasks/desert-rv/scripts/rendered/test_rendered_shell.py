#!/usr/bin/env python3
"""Source/fixture tests only: never launches Unity, Docker, X11, or real licensing."""
import base64,hashlib,importlib.util,json,os,pathlib,subprocess,sys,tempfile,unittest
from unittest.mock import patch
import verify_inputs as checks
HERE=pathlib.Path(__file__).parent
SCRIPTS=HERE.parent
class RenderedShellTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.env=dict(GITHUB_REPOSITORY='yangerstar1/task-workbench',GITHUB_REF='refs/heads/main',GITHUB_ACTOR='yangerstar1',GITHUB_TRIGGERING_ACTOR='yangerstar1',GITHUB_ACTIONS='true',RUNNER_ENVIRONMENT='github-hosted',GITHUB_REPOSITORY_VISIBILITY='public',GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_SHA='a'*40)
        self.patcher=patch.object(checks,'ROOT',self.root);self.patcher.start();self.ep=patch.dict(os.environ,self.env);self.ep.start()
        p=self.root/'tasks/desert-rv/unity/Assets/DesertRV/Scenes/BodyStudy.unity';p.parent.mkdir(parents=True);p.write_text('synthetic existing-scene fixture')
    def tearDown(self):self.ep.stop();self.patcher.stop();self.tmp.cleanup()
    def test_smoke_needs_no_gameplay_scope_or_plan(self):checks.verify('window-smoke')
    def test_private_runner_rejected(self):
        with patch.dict(os.environ,GITHUB_REPOSITORY_VISIBILITY='private'):
            with self.assertRaises(Exception):checks.verify('window-smoke')
    def test_missing_gameplay_inputs_fail(self):
        with self.assertRaises(Exception):checks.verify('journey')
    def test_symlink_scene_rejected(self):
        p=self.root/'tasks/desert-rv/unity/Assets/DesertRV/Scenes/BodyStudy.unity';target=self.root/'other';p.rename(target);p.symlink_to(target)
        with self.assertRaises(Exception):checks.verify('window-smoke')
    def test_license_parser_matches_pinned_official_algorithm_with_synthetic_bytes(self):
        serial='F'+('A'*26);license='<DeveloperData Value="'+base64.b64encode(b'xxxx'+serial.encode()).decode()+'"/>'
        out=subprocess.run([sys.executable,str(HERE/'serial_from_license.py')],env={**os.environ,'UNITY_LICENSE':license},capture_output=True,text=True)
        self.assertEqual(out.returncode,0);self.assertEqual(out.stdout,serial);self.assertEqual(out.stderr,'')
    def test_invalid_license_produces_no_output(self):
        out=subprocess.run([sys.executable,str(HERE/'serial_from_license.py')],env={**os.environ,'UNITY_LICENSE':'synthetic invalid'},capture_output=True,text=True)
        self.assertNotEqual(out.returncode,0);self.assertEqual(out.stdout+out.stderr,'')
    def test_rendered_shell_never_uses_gameci_batch_wrapper(self):
        s=(SCRIPTS/'run_rendered_diagnostic.sh').read_text();self.assertIn('"$UNITY_EDITOR"',s);self.assertNotIn('unity-editor ',s)
        self.assertIn('openbox --sm-disable',s);self.assertIn('15m',s);self.assertIn('-force-glcore',s)
    def test_credentials_removed_from_rendered_child_and_return_trapped(self):
        s=(HERE/'container_entry.sh').read_text();self.assertIn('trap cleanup EXIT',s);self.assertIn('return_license.sh',s)
        self.assertIn('env -u UNITY_LICENSE -u UNITY_EMAIL -u UNITY_PASSWORD -u UNITY_SERIAL',s);self.assertNotIn('cat "$private',s)
    def test_window_capture_has_no_fullscreen_fallback_and_failed_stop_withholds_video(self):
        s=(SCRIPTS/'capture_game_window.py').read_text();self.assertIn("'-window_id',window",s);self.assertIn("type(editor_exit) is int and editor_exit==0",s)
        self.assertNotIn("'-video_size'",s)
    def test_official_sha_manifest_has_exact_pinned_action(self):
        p=json.loads((HERE/'official-gameci-pins.json').read_text());self.assertEqual(p['commit'],'0ff419b913a3630032cbe0de48a0099b5a9f0ed9');self.assertEqual(len(p['files']),4)
    def test_smoke_contains_no_journey_mutation_or_input_calls(self):
        p=HERE.parents[1]/'unity/Assets/DesertRV/Runtime/Diagnostics/JourneyWindowSmokeEvidence.cs'
        s=p.read_text();self.assertIn('>= 30',s);self.assertIn('WINDOW_SMOKE_ONLY',s)
        for forbidden in ('.Begin()', '.Restart()', '.Damage', '.TryCollect', '.TryFire', 'SetControl(', 'TouchInputState', 'MobileInputAdapter'):
            self.assertNotIn(forbidden,s)
if __name__=='__main__':unittest.main()
