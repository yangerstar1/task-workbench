#!/usr/bin/env python3
"""Synthetic private-log and process fixtures only; no Unity, X11, Docker or licensing."""
import importlib.util,json,pathlib,tempfile,unittest
from unittest.mock import patch
import startup_diagnostic as diag
HERE=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('startup_capture_under_test',HERE.parent/'capture_game_window.py');capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
class StartupDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.project=self.root/'project';self.logs=self.root/'logs';self.logs.mkdir()
        p=self.project/'Assets/DesertRV/Runtime/PublicKnown.cs';p.parent.mkdir(parents=True);p.write_text('// synthetic public-source fixture')
    def tearDown(self):self.tmp.cleanup()
    def classify(self,text):
        (self.logs/'editor.log').write_text(text);return diag.classify(self.logs,self.project,143,1,'SIGTERM_ON_CAPTURE_FAILURE')
    def test_known_code_and_public_basename_are_bound_without_original_message(self):
        r=self.classify('/home/PRIVATE_USER/repo/Assets/DesertRV/Runtime/PublicKnown.cs(3,8): error CS0246: PRIVATE_PASSWORD secret@example.invalid\n')
        self.assertTrue(r['compileErrors']);self.assertEqual(r['compilerDiagnostics'],[dict(code='CS0246',sourceBasename='PublicKnown.cs')]);self.assertNotIn('PRIVATE',json.dumps(r));self.assertNotIn('example.invalid',json.dumps(r));self.assertNotIn('/home',json.dumps(r))
    def test_unknown_source_and_code_do_not_echo_original_values(self):
        r=self.classify('/home/PRIVATE_USER/PrivateToken.cs(3,8): error CS9999: private data\n');self.assertEqual(r['compilerDiagnostics'],[dict(code='UNKNOWN_CSHARP_ERROR',sourceBasename='UNKNOWN_PROJECT_SOURCE')])
    def test_execute_method_resolution_failure_is_only_boolean(self):
        r=self.classify('executeMethod class PRIVATE_CLASS could not be found\n');self.assertTrue(r['executeMethodNotFound']);self.assertNotIn('PRIVATE_CLASS',json.dumps(r))
    def test_license_and_graphics_errors_are_fixed_enums_only(self):
        r=self.classify('No valid Unity Editor license found PRIVATE_SERIAL\nFailed to initialize graphics PRIVATE_DRIVER_PATH\n');self.assertEqual(r['licenseStatus'],'NO_VALID_LICENSE');self.assertEqual(r['graphicsStatus'],'DEVICE_INIT_FAILURE');self.assertNotIn('PRIVATE',json.dumps(r))
    def test_activation_and_return_logs_are_never_read(self):
        (self.logs/'activation.log').write_text('No valid license found PRIVATE_SERIAL\n');(self.logs/'return.log').write_text('error CS0246 PRIVATE_TOKEN\n');r=diag.classify(self.logs,self.project);self.assertEqual(r['scanStatus'],'NO_LOGS');self.assertFalse(r['compileErrors']);self.assertEqual(r['licenseStatus'],'NONE_OBSERVED')
    def test_cold_start_progress_has_no_paths_or_guessed_completion(self):
        r=self.classify('Initialize engine version: 6000.3.19f1\nMono config path = /PRIVATE/path\nStart importing Assets/PRIVATE.fbx\nBegin MonoManager ReloadAssembly\nShaderCompiler /PRIVATE/socket\n');self.assertEqual(r['startupProgress'],['engine-version-reported','mono-runtime-configured','asset-import-observed','assembly-reload-started','shader-compilation-observed']);self.assertNotIn('PRIVATE',json.dumps(r))
    def test_shell_status_and_requested_term_are_not_invented_signal_diagnosis(self):
        r=self.classify('');self.assertEqual(r['editorWaitExitCode'],143);self.assertEqual(r['captureExitCode'],1);self.assertEqual(r['terminationRequest'],'SIGTERM_ON_CAPTURE_FAILURE')
    def test_symlink_log_rejected(self):
        target=self.root/'private';target.write_text('error CS0246 PRIVATE');(self.logs/'editor.log').symlink_to(target);r=diag.classify(self.logs,self.project);self.assertEqual(r['scanStatus'],'UNREADABLE');self.assertEqual(r['compilerDiagnostics'],[])
    def test_long_line_is_bounded_and_never_echoed(self):
        with patch.object(diag,'MAX_LINE',40):r=self.classify('PRIVATE'*100+'\n');self.assertEqual(r['scanStatus'],'BOUNDED');self.assertNotIn('PRIVATE',json.dumps(r))
    def test_unknown_report_field_rejected(self):
        r=diag.empty_report();r['raw']='PRIVATE'
        with self.assertRaises(Exception):diag.validate(r,{'PublicKnown.cs'})
    def test_nonpublic_diagnostic_basename_rejected(self):
        r=diag.empty_report();r['compileErrors']=True;r['compilerDiagnostics']=[dict(code='CS0246',sourceBasename='PRIVATE.cs')]
        with self.assertRaises(Exception):diag.validate(r,{'PublicKnown.cs'})
    def test_unknown_error_code_rejected(self):
        r=diag.empty_report();r['compileErrors']=True;r['compilerDiagnostics']=[dict(code='CS9999',sourceBasename='PublicKnown.cs')]
        with self.assertRaises(Exception):diag.validate(r,{'PublicKnown.cs'})
    def test_forged_scan_license_or_signal_enum_rejected(self):
        for key,value in [('scanStatus','PRIVATE'),('licenseStatus','PRIVATE'),('terminationRequest','PRIVATE')]:
            r=diag.empty_report();r[key]=value
            with self.assertRaises(Exception):diag.validate(r,{'PublicKnown.cs'})
    def test_boolean_or_nonfinite_exit_status_rejected(self):
        for value in (True,float('nan'),-9,256):
            r=diag.empty_report();r['editorWaitExitCode']=value
            with self.assertRaises(Exception):diag.validate(r,set())
    def test_native_library_message_only_sets_fixed_boolean(self):
        r=self.classify('/PRIVATE/Unity: error while loading shared libraries: /PRIVATE/libsecret.so\n');self.assertTrue(r['nativeLibraryFailure']);self.assertNotIn('PRIVATE',json.dumps(r))
    def test_real_nul_separated_arguments_accept_only_complete_canonical_token(self):
        project='/github/workspace/tasks/desert-rv/unity';method=capture.ENTRIES['window-smoke'];args=['/opt/unity/Editor/Unity','-projectPath',project,'-executeMethod',method,'-force-glcore']
        raw=('\0'.join(args)+'\0').encode();self.assertTrue(capture.parse_unity_argv(raw,project,'window-smoke'))
        for replacement in (method+'.Extra','prefix'+method,'DesertRV.Editor.JourneyRenderedDiagnosticRunner.RunWindowSmoke'):
            self.assertFalse(capture.parse_unity_argv(raw.replace(method.encode(),replacement.encode()),project,'window-smoke'))
    def test_duplicate_or_misplaced_execute_method_argument_rejected(self):
        project='/p';method=capture.ENTRIES['window-smoke']
        for args in (['Unity','-projectPath',project,'-logFile',method],['Unity','-projectPath',project,'-executeMethod',method,'-executeMethod',method],['Unity','-projectPath',project,'-executeMethod',method,'-batchmode']):self.assertFalse(capture.parse_unity_argv(('\0'.join(args)+'\0').encode(),project,'window-smoke'))
    def test_timeout_parent_and_unity_child_are_distinct_but_owned(self):
        proc=self.root/'proc';(proc/'20').mkdir(parents=True);(proc/'20/stat').write_text('20 (Unity) S 10 0 0');self.assertTrue(capture.owned_descendant(20,10,proc));self.assertFalse(capture.owned_descendant(10,10,proc));self.assertFalse(capture.owned_descendant(20,11,proc))
    def test_bounded_owned_descendant_chain_handles_timeout_helper(self):
        proc=self.root/'proc';(proc/'20').mkdir(parents=True);(proc/'20/stat').write_text('20 (Unity worker) S 15 0 0');(proc/'15').mkdir();(proc/'15/stat').write_text('15 (helper) S 10 0 0');self.assertTrue(capture.owned_descendant(20,10,proc))
    def test_editor_bridge_dependency_is_one_way_and_tokens_agree(self):
        root=HERE.parents[1];bridge=root/'unity/Assets/DesertRV/Editor/JourneyRenderedCommandLine.cs';runtime=root/'unity/Assets/DesertRV/Runtime/Diagnostics/JourneyRenderedDiagnosticRunner.cs';shell=HERE.parent/'run_rendered_diagnostic.sh'
        self.assertIn('public static void RunWindowSmoke() => JourneyRenderedDiagnosticRunner.RunWindowSmoke();',bridge.read_text())
        for token in capture.ENTRIES.values():self.assertIn('"'+token+'"',runtime.read_text());self.assertIn('entry='+token,shell.read_text())
        self.assertNotIn('nameof(JourneyRenderedCommandLine)',runtime.read_text());self.assertNotIn('typeof(JourneyRenderedCommandLine)',runtime.read_text());self.assertIn('count == 1',runtime.read_text())
    def test_classifier_runs_before_private_log_deletion(self):
        shell=(HERE.parent/'run_rendered_diagnostic.sh').read_text();self.assertIn('startup_diagnostic.py',shell);self.assertIn('--editor-exit "$editor_status"',shell)
if __name__=='__main__':unittest.main()
