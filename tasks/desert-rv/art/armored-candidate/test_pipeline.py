"""Standard Python workflow/package checks; no Blender, Unity, downloads or publication."""
import ast, hashlib, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
import package_evidence
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
WORKFLOW=ROOT/'.github/workflows/desert-rv-armored-art.yml'
class PipelineTests(unittest.TestCase):
    def test_all_python_parses(self):
        for path in HERE.glob('*.py'):ast.parse(path.read_text())
    def test_expected_outputs_unique_and_bounded(self):
        self.assertEqual(len(package_evidence.expected('static')),62)
        self.assertEqual(len(package_evidence.expected('motion')),86)
        for phase in ('static','motion'):
            names=package_evidence.expected(phase); self.assertEqual(len(names),len(set(names)))
            self.assertFalse(any('..' in name or name.startswith('/') for name in names))
    def test_workflow_security_contract(self):
        s=WORKFLOW.read_text()
        for fragment in ("github.actor == github.repository_owner","github.event.repository.private == false","github.ref == 'refs/heads/main'","runs-on: ubuntu-24.04","contents: read","persist-credentials: false","timeout-minutes: 120","sha256sum --check selected.sha256","20m blender","80m blender"):
            self.assertIn(fragment,s)
        self.assertNotIn('${{ runner.temp }}',s)
        self.assertIn('>> "$GITHUB_ENV"',s)
        self.assertIn('ART_ROOT=%s/bulwark-%s-%s',s)
        self.assertNotIn(".outcome != 'skipped'",s)
        for step in ('static','motion'):
            self.assertIn("steps."+step+".outcome == 'success'",s)
            self.assertIn("steps."+step+".outcome == 'failure'",s)
        self.assertNotIn('secrets.',s); self.assertNotIn('contents: write',s); self.assertNotIn('pull_request:',s)
        for line in s.splitlines():
            if 'uses:' in line:
                ref=line.split('@')[1].split()[0]; self.assertEqual(len(ref),40); int(ref,16)
        self.assertLess(s.index('Upload early static evidence'),s.index('Generate bounded motion'))
    def test_missing_outputs_remain_explicit_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'bulwark-123-1'; root.mkdir(); (root/'static').mkdir()
            provenance={'source_commit':'a'*40,'run_id':'123','run_attempt':'1','source_manifest_sha256':hashlib.sha256((HERE/'source-manifest.json').read_bytes()).hexdigest()}
            (root/'provenance.json').write_text(json.dumps(provenance)); (root/'blender-upstream.sha256').write_text('test-checksum'); (root/'static.exit').write_text('1')
            env={**os.environ,'RUNNER_TEMP':tmp,'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1','GITHUB_SHA':'a'*40}
            result=subprocess.run([sys.executable,str(HERE/'package_evidence.py'),'--root',str(root),'--phase','static'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,1,result.stderr)
            status=json.loads((root/'static-package/STATUS.json').read_text()); self.assertEqual(status['status'],'PARTIAL_FAILED_NOT_A_SUCCESS'); self.assertGreater(len(status['errors']),10)
            self.assertTrue((root/'static-package/SHA256SUMS').is_file())
            # Same package destination cannot be reused even for another failed attempt.
            second=subprocess.run([sys.executable,str(HERE/'package_evidence.py'),'--root',str(root),'--phase','static'],env=env,capture_output=True,text=True)
            self.assertNotEqual(second.returncode,0); self.assertIn('Refusing nonempty',second.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
