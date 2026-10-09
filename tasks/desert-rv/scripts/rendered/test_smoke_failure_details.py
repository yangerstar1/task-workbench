#!/usr/bin/env python3
"""Synthetic control/phase tests; no Unity, display, Docker or real license invocation."""
import importlib.util,json,os,pathlib,subprocess,tempfile,time,types,unittest
from unittest.mock import patch
import guard_export as guard
import write_control_status as writer
HERE=pathlib.Path(__file__).parent
class FailureDetailsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.task=self.root/'tasks/desert-rv';self.task.mkdir(parents=True)
        self.control=dict(schema=1,mode='RENDERED_CONTROL_ONLY_NOT_ACCEPTANCE',activation='SUCCEEDED',licenseReturn='SUCCEEDED',renderProcess='FAILED',privateCleanup='SUCCEEDED',captureFailureCode='editor-startup',renderPhases=['editor-spawn'])
    def tearDown(self):self.tmp.cleanup()
    def control_file(self,data=None,text=None):
        folder=self.task/'rendered-control-export';folder.mkdir(exist_ok=True);p=folder/'status.json';p.write_text(text if text is not None else json.dumps(self.control if data is None else data));return p
    def run_guard(self,native='failure'):
        with patch.object(guard,'ROOT',self.root),patch.object(guard,'TASK',self.task),patch.dict(os.environ,NATIVE_OUTCOME=native,GITHUB_OUTPUT=str(self.root/'outputs')),patch.object(guard.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)):
            result=guard.main()
        folder=self.task/'rendered-public-export';self.assertEqual([p.name for p in folder.iterdir()],['status.json']);return result,json.loads((folder/'status.json').read_text())
    def test_native_failure_preserves_success_gate_but_exposes_validated_capture_stage(self):
        self.control_file();code,r=self.run_guard();self.assertEqual(code,1);self.assertFalse(r['videoExported']);self.assertEqual(r['failureCode'],'NATIVE_PROCESS_NOT_SUCCESS');self.assertEqual(r['diagnosticDetails']['captureFailureCode'],'editor-startup');self.assertEqual(r['diagnosticDetails']['renderPhases'],['editor-spawn'])
    def test_old_success_shaped_control_never_bypasses_failed_native(self):
        self.control.update(renderProcess='SUCCEEDED',captureFailureCode='NONE',renderPhases=list(guard.PHASES));self.control_file();code,r=self.run_guard();self.assertEqual(code,1);self.assertFalse(r['videoExported'])
    def test_extra_field_invalidates_all_details(self):
        self.control['rawException']='PRIVATE_RAW_TEXT';self.control_file();_,r=self.run_guard();self.assertNotIn('diagnosticDetails',r);self.assertNotIn('PRIVATE_RAW_TEXT',json.dumps(r))
    def test_unknown_enum_not_published(self):
        self.control['captureFailureCode']='PRIVATE_TEXT';self.control_file();_,r=self.run_guard();self.assertNotIn('diagnosticDetails',r)
    def test_duplicate_json_key_rejected(self):
        p=self.control_file();data=p.read_text();p.write_text(data[:-1]+',"schema":1}');_,r=self.run_guard();self.assertNotIn('diagnosticDetails',r)
    def test_missing_control_schema_rejected(self):
        self.control.pop('schema');self.control_file();_,r=self.run_guard();self.assertNotIn('diagnosticDetails',r)
    def test_boolean_schema_is_not_integer_schema(self):
        self.control['schema']=True;self.control_file();_,r=self.run_guard();self.assertNotIn('diagnosticDetails',r)
    def test_missing_capture_receipt_cannot_become_none_success(self):
        writer.write_status(['SUCCEEDED','SUCCEEDED','FAILED','SUCCEEDED'],self.task);p=self.task/'rendered-control-export/status.json';v=guard.read_control(p);self.assertEqual(v['captureFailureCode'],'UNAVAILABLE')
    def test_foreign_json_cannot_become_none_success(self):
        p=self.root/'capture.json';p.write_text('{"private":"text"}');self.assertEqual(writer.capture_detail(p),'UNAVAILABLE')
    def test_explicit_failed_capture_projection_is_allowed(self):
        p=self.root/'capture.json';p.write_text(json.dumps(dict(mode='VERIFIED_GAME_WINDOW_CAPTURE',sourceVerified=False,failureCode='game-window-unavailable',editorExitCode=None,editorStopAcknowledged=False,encoderExitCode=None,encoderStopMethod='none',encoderFailureCode='encoder-not-started')));self.assertEqual(writer.capture_detail(p),'game-window-unavailable')
    def test_contradictory_source_success_rejected(self):
        p=self.root/'capture.json';p.write_text(json.dumps(dict(mode='VERIFIED_GAME_WINDOW_CAPTURE',sourceVerified=True,failureCode='editor-stop-not-success',editorExitCode=0,editorStopAcknowledged=True,encoderExitCode=0,encoderStopMethod='stdin-q',encoderFailureCode=None)));self.assertEqual(writer.capture_detail(p),'UNAVAILABLE')
    def test_phase_snapshot_contains_only_fixed_marker_names_and_one_byte_contents(self):
        markers=self.root/'markers';markers.mkdir();(markers/'editor-spawn').write_text('1');(markers/'executeMethod-entered').write_text('PRIVATE');(markers/'private-log').write_text('do not export')
        out=self.root/'evidence';writer.summarize_progress(markers,out);v=json.loads((out/'render-progress.json').read_text());self.assertEqual(v,dict(schema=1,phases=['editor-spawn']))
    def test_phase_unknown_duplicates_or_reordering_rejected(self):
        for phases in (['private'],['editor-spawn','editor-spawn'],['view-created','editor-spawn']):
            data={**self.control,'renderPhases':phases}
            with self.assertRaises(Exception):guard.read_control(self.control_file(data))
    def test_symlink_control_rejected(self):
        p=self.control_file();real=self.root/'control';p.rename(real);p.symlink_to(real)
        with self.assertRaises(Exception):guard.read_control(p)
    def test_native_success_still_requires_cleanup_success(self):
        self.control['privateCleanup']='FAILED';self.control_file();_,r=self.run_guard('success');self.assertEqual(r['failureCode'],'PRIVATE_CLEANUP_FAILED')
    def test_capture_failure_cancels_owned_timeout_process_instead_of_waiting_watchdog(self):
        source=(HERE.parent/'run_rendered_diagnostic.sh').read_text();a=source.index('if [[ "$capture_status" != 0 ]]');b=source.index('set -e',a);owned=source[a:b]
        script='set +e\ntimeout --signal=TERM --kill-after=1s 5s sleep 4 & unity_pid=$!\nsleep .05\ncapture_status=1\n'+owned+'\n[[ "$editor_status" != 0 ]]\n'
        start=time.monotonic();r=subprocess.run(['bash','-c',script],capture_output=True,text=True,timeout=2)
        self.assertEqual(r.returncode,0);self.assertLess(time.monotonic()-start,1.5)
    def test_reload_callback_and_actual_argv_remain_explicit(self):
        p=HERE.parents[1]/'unity/Assets/DesertRV/Runtime/Diagnostics/JourneyRenderedDiagnosticRunner.cs';s=p.read_text()
        self.assertIn('[InitializeOnLoad]',s);self.assertIn('EditorApplication.playModeStateChanged += OnPlayMode',s);self.assertIn('PlayModeStateChange.EnteredPlayMode',s)
        for phase in ('executeMethod-entered','playmode-entered','view-created','duration-complete'):self.assertIn('MarkPhase("'+phase+'")',s)
        shell=(HERE.parent/'run_rendered_diagnostic.sh').read_text();self.assertIn('"$UNITY_EDITOR" -projectPath "$DESERTRV_UNITY_PROJECT"',shell);self.assertIn('-executeMethod "$entry"',shell)
if __name__=='__main__':unittest.main()
