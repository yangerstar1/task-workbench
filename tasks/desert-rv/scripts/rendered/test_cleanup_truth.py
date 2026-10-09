#!/usr/bin/env python3
"""Extracted real cleanup function with shell mocks; never activates or returns a real license."""
import importlib.util,json,os,pathlib,subprocess,tempfile,types,unittest
from unittest.mock import patch
HERE=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('guard_under_test',HERE/'guard_export.py');guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
class CleanupTruthTests(unittest.TestCase):
    def cleanup(self,rm_failure=False,write_failure=False):
        source=(HERE/'container_entry.sh').read_text();start=source.index('cleanup() {');function=source[start:source.index('\n}\n',start)+3]
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);private=root/'private';private.mkdir();record=root/'arguments'
            script='''set +x
set -euo pipefail
private="$1"; record="$2"; activation=SUCCEEDED; returned=NOT_ATTEMPTED; render=SUCCEEDED; attempted=1
timeout() { return 0; }
rm() { %s; }
python3() { printf '%%s\\n' "$@" > "$record"; %s; }
%s
trap cleanup EXIT
true
''' % ('return 1' if rm_failure else 'command rm "$@"','return 1' if write_failure else 'return 0' if rm_failure else '[[ ! -e "$private" ]]',function)
            result=subprocess.run(['bash','-c',script,'fixture',str(private),str(record)],capture_output=True,text=True)
            return result.returncode,record.read_text().splitlines() if record.exists() else [],result.stdout,result.stderr
    def test_real_success_requires_removal_before_status_write(self):
        code,args,_,_=self.cleanup();self.assertEqual(code,0);self.assertEqual(args[-1],'SUCCEEDED')
    def test_reviewer_counterexample_rm_failure_is_nonzero_and_cleanup_failed(self):
        code,args,_,_=self.cleanup(rm_failure=True);self.assertNotEqual(code,0);self.assertEqual(args[-1],'FAILED')
    def test_status_write_failure_cannot_exit_success(self):
        code,_,_,error=self.cleanup(write_failure=True);self.assertNotEqual(code,0);self.assertIn('RENDERED_CONTROL_WRITE_FAILED',error)
    def test_native_failure_blocks_old_success_control_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);task=root/'tasks/desert-rv';control=task/'rendered-control-export';control.mkdir(parents=True)
            (control/'status.json').write_text(json.dumps(dict(schema=1,mode='RENDERED_CONTROL_ONLY_NOT_ACCEPTANCE',captureFailureCode='NONE',renderPhases=[],activation='SUCCEEDED',licenseReturn='SUCCEEDED',renderProcess='SUCCEEDED',privateCleanup='SUCCEEDED')))
            with patch.object(guard,'ROOT',root),patch.object(guard,'TASK',task),patch.dict(os.environ,NATIVE_OUTCOME='failure',GITHUB_OUTPUT=str(root/'outputs')),patch.object(guard.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)):
                code=guard.main()
            self.assertEqual(code,1);out=task/'rendered-public-export';self.assertEqual([p.name for p in out.iterdir()],['status.json']);self.assertEqual(json.loads((out/'status.json').read_text())['failureCode'],'NATIVE_PROCESS_NOT_SUCCESS')
    def test_cleanup_failure_blocks_video_even_with_success_native_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);task=root/'tasks/desert-rv';control=task/'rendered-control-export';control.mkdir(parents=True)
            (control/'status.json').write_text(json.dumps(dict(schema=1,mode='RENDERED_CONTROL_ONLY_NOT_ACCEPTANCE',captureFailureCode='NONE',renderPhases=[],activation='SUCCEEDED',licenseReturn='SUCCEEDED',renderProcess='SUCCEEDED',privateCleanup='FAILED')))
            with patch.object(guard,'ROOT',root),patch.object(guard,'TASK',task),patch.dict(os.environ,NATIVE_OUTCOME='success',GITHUB_OUTPUT=str(root/'outputs')),patch.object(guard.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)):
                self.assertEqual(guard.main(),1)
            self.assertEqual(json.loads((task/'rendered-public-export/status.json').read_text())['failureCode'],'PRIVATE_CLEANUP_FAILED')
if __name__=='__main__':unittest.main()
