import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location("workbench", Path(__file__).resolve().parents[1] / "scripts/workbench.py")
w = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(w)


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.ctx = {"repository": "example/task-workbench", "commit": "a" * 40, "runId": "123", "runAttempt": "1", "sourceSha256": "b" * 64}
        self.req = {"schema": "task-workbench/request-v1", "task": "data-summary", "mode": "complete", "resumeRunId": "", "resumeRequestId": "", "requestId": "first"}

    def tearDown(self):
        self.tmp.cleanup()

    def reject_request(self, **changes):
        with self.assertRaises(ValueError):
            w.validate_request(dict(self.req, **changes))

    def produce(self, mode="complete", fail=False):
        out = self.base / "out"
        def injected_failure(_):
            raise RuntimeError("deliberate local-test report failure")
        r = w.run_task(self.ctx, dict(self.req, mode=mode), output=out, report_builder=injected_failure if fail else None)
        return out, r

    def test_valid_request(self):
        self.assertEqual(w.validate_request(self.req), self.req)

    def test_unknown_task(self):
        self.reject_request(task="shell")

    def test_unknown_mode(self):
        self.reject_request(mode="loop")

    def test_unknown_field(self):
        self.reject_request(command="echo arbitrary")

    def test_path_request_id(self):
        self.reject_request(requestId="../escape")

    def test_recovery_requires_pair(self):
        self.reject_request(mode="recover", resumeRunId="123")

    def test_resume_injection(self):
        self.reject_request(mode="recover", resumeRunId="123;echo bad", resumeRequestId="old")

    def test_wrong_type(self):
        self.reject_request(resumeRunId=123)

    def test_unexpected_resume_complete(self):
        self.reject_request(resumeRunId="123")

    def test_recovery_needs_new_request_id(self):
        self.reject_request(mode="recover", resumeRunId="123", resumeRequestId="first")

    def test_known_original_result(self):
        self.assertEqual(w.make_index(), {"rowCount": 8, "totals": {"books": 30, "tools": 24, "plants": 14}, "totalUnits": 68})

    def test_complete_and_full_validation(self):
        out, r = self.produce()
        self.assertEqual(r["status"], "COMPLETED")
        self.assertEqual(w.verify_publish(self.ctx, out), r)

    def test_checkpoint_is_not_complete(self):
        out, r = self.produce("checkpoint")
        self.assertEqual(r["status"], "CHECKPOINT")
        self.assertFalse((out / "result.json").exists())
        w.verify_publish(self.ctx, out)

    def test_failed_second_stage_remains_failed_and_recoverable(self):
        out, r = self.produce(fail=True)
        self.assertEqual(r["status"], "FAILED_WITH_CHECKPOINT")
        w.verify_publish(self.ctx, out)
        ctx = dict(self.ctx, runId="124", commit="c" * 40)
        req = dict(self.req, mode="recover", requestId="second", resumeRunId="123", resumeRequestId="first")
        recovered = self.base / "recovered"
        rr = w.run_task(ctx, req, output=recovered, resume=out)
        self.assertEqual(rr["status"], "COMPLETED")
        self.assertEqual(rr["stages"][0]["status"], "RESTORED_VERIFIED")
        self.assertEqual(rr["restoredFrom"], self.ctx)
        w.verify_publish(ctx, recovered)

    def test_wrong_source_digest(self):
        out, _ = self.produce("checkpoint")
        with self.assertRaises(ValueError):
            w.validate_checkpoint(out, dict(self.ctx, sourceSha256="c" * 64))

    def test_foreign_repository(self):
        out, _ = self.produce("checkpoint")
        with self.assertRaises(ValueError):
            w.validate_checkpoint(out, dict(self.ctx, repository="other/repo"))

    def test_wrong_run(self):
        out, _ = self.produce("checkpoint")
        with self.assertRaises(ValueError):
            w.validate_checkpoint(out, self.ctx, "999")

    def test_tampered_index(self):
        out, _ = self.produce("checkpoint")
        (out / "index.json").write_text('{}')
        with self.assertRaises(ValueError):
            w.validate_checkpoint(out, self.ctx)

    def test_extra_payload_rejected(self):
        out, _ = self.produce("checkpoint")
        (out / "run.sh").write_text('echo wrong')
        with self.assertRaises(ValueError):
            w.validate_checkpoint(out, self.ctx)

    def test_symlink_rejected(self):
        out, _ = self.produce("checkpoint")
        (out / "index.json").unlink()
        (out / "index.json").symlink_to(w.ROOT / "tasks/catalog.json")
        with self.assertRaises(ValueError):
            w.validate_checkpoint(out, self.ctx)

    def test_duplicate_json_field_rejected(self):
        p = self.base / "bad.json"
        p.write_text('{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            w.read_json(p)

    def test_existing_output_not_overwritten(self):
        self.produce()
        with self.assertRaises(FileExistsError):
            self.produce()

    def test_full_tree_pin_excludes_only_exact_request(self):
        root = self.base / "git"
        root.mkdir()
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / "README.md").write_text("original")
        (root / "requests").mkdir()
        (root / "requests/current.json").write_text("request1")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        initial = w.content_identity(root)
        (root / "requests/current.json").write_text("request2")
        self.assertEqual(initial, w.content_identity(root))
        (root / "README.md").write_text("changed")
        self.assertNotEqual(initial, w.content_identity(root))
        (root / "README.md").write_text("original")
        subprocess.run(["git", "update-index", "--chmod=+x", "README.md"], cwd=root, check=True)
        self.assertNotEqual(initial, w.content_identity(root))

    def test_metadata_refuses_foreign_workflow(self):
        m = {"id":123,"repository":{"full_name":self.ctx["repository"]},"path":".github/workflows/evil.yml","event":"push","head_branch":"main"}
        with patch.object(w, "api", return_value=m), self.assertRaises(ValueError):
            w.verify_run_metadata(self.ctx, "123")

    def test_metadata_pins_attempt(self):
        m = {"id":123,"repository":{"full_name":self.ctx["repository"]},"path":w.WORKFLOW,"event":"push","head_branch":"main","run_attempt":1}
        with patch.object(w, "api", return_value=m) as api:
            w.verify_run_metadata(self.ctx, "123", "1")
            self.assertTrue(api.call_args.args[0].endswith('/attempts/1'))
            with self.assertRaises(ValueError):
                w.verify_run_metadata(self.ctx, "123", "2")

    def test_release_only_explicit_404_is_absent(self):
        with patch.object(w.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, '{"status":"404"}', '')):
            self.assertIsNone(w.release_for(self.ctx, "first"))
        with patch.object(w.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, '{"status":"403"}', '')):
            with self.assertRaises(ValueError):
                w.release_for(self.ctx, "first")

    def test_draft_release_not_reused(self):
        with self.assertRaises(ValueError):
            w.fetch_release(self.ctx, {"draft": True}, self.base / "download")

    def test_false_completed_report_rejected_even_with_updated_hashes(self):
        out, _ = self.produce()
        r = w.read_json(out / "receipt.json")
        (out / "result.json").write_text('{}')
        r["files"]["result.json"] = w.sha(out / "result.json")
        (out / "receipt.json").write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError, "Report differs"):
            w.verify_publish(self.ctx, out)

    def test_receipt_identity_cannot_disagree_with_checkpoint(self):
        out, _ = self.produce()
        r = w.read_json(out / "receipt.json")
        r["identity"]["runId"] = "999"
        (out / "receipt.json").write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            w.verify_publish(self.ctx, out, exact=False)

    def unsafe_zip(self, name, symbolic=False):
        archive = self.base / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr('checkpoint.json', '{}')
            if symbolic:
                info = zipfile.ZipInfo('index.json')
                info.external_attr = 0o120777 << 16
                z.writestr(info, 'outside')
            else:
                z.writestr('index.json', '{}')
                z.writestr(name, 'bad')
        meta = {"id":123,"repository":{"full_name":self.ctx["repository"]},"path":w.WORKFLOW,"event":"push","head_branch":"main","status":"completed","conclusion":"failure","run_attempt":1}
        arts = {"total_count":1,"artifacts":[{"id":7,"name":"workbench-123-1","expired":False,"size_in_bytes":archive.stat().st_size}]}
        def copy_zip(args, stdout):
            stdout.write(archive.read_bytes())
        with patch.object(w, "ROOT", self.base), patch.object(w, "api", side_effect=[meta, arts]), patch.object(w.subprocess, "check_call", side_effect=copy_zip):
            with self.assertRaises(ValueError):
                w.fetch(self.ctx, "123", self.base / "download")
        self.assertFalse((self.base / "escape").exists())

    def test_zip_traversal_rejected_before_extraction(self):
        self.unsafe_zip('../escape')

    def test_zip_absolute_path_rejected(self):
        self.unsafe_zip('/escape')

    def test_zip_symlink_rejected(self):
        self.unsafe_zip('', symbolic=True)


if __name__ == "__main__":
    unittest.main()
