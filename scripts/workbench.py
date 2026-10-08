#!/usr/bin/env python3
"""Small trusted task runner. No dynamic imports, commands, URLs, or user paths."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "workbench-out"
RESUME = ROOT / "workbench-resume"
FILES = {"checkpoint.json", "index.json", "result.json", "receipt.json", "SHA256SUMS", "release-notes.md"}
FIELDS = {"schema", "task", "mode", "resumeRunId", "resumeRequestId", "requestId"}
WORKFLOW = ".github/workflows/workbench.yml"


def need(ok, why):
    if not ok:
        raise ValueError(why)


def pairs(items):
    result = {}
    for k, v in items:
        need(k not in result, "Duplicate JSON field")
        result[k] = v
    return result


def read_json(path):
    safe_file(path)
    need(path.stat().st_size <= 1024 * 1024, "Oversized JSON")
    return json.loads(path.read_text(), object_pairs_hook=pairs)


def safe_file(path):
    path = Path(path)
    need(path.is_file() and not path.is_symlink(), "Missing file or symbolic link: " + path.name)
    for parent in path.parents:
        need(not parent.is_symlink(), "Linked ancestor")


def sha(path):
    safe_file(path)
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    need(not path.exists() and not path.is_symlink(), "Output already exists")
    data = json.dumps(value, sort_keys=True, indent=2) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x") as stream:
        stream.write(data)
    temporary.replace(path)


def content_identity(root=ROOT):
    # Entire tracked tree, including modes; only the one request file is excluded.
    raw = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=root)
    entries = []
    for row in raw.decode().split("\0"):
        if not row:
            continue
        info, name = row.split("\t", 1)
        mode, blob, stage = info.split()
        need(stage == "0" and mode in ("100644", "100755"), "Unmerged, linked or submodule source")
        if name == "requests/current.json":
            continue
        entries.append({"path": name, "mode": mode, "sha256": sha(root / name)})
    need(entries, "Empty source tree")
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def trusted_context(unity=False):
    need(os.environ.get("GITHUB_ACTIONS") == "true", "This entry requires GitHub Actions")
    need(os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted" and os.environ.get("RUNNER_OS") == "Linux", "Standard hosted Linux required")
    event = read_json(Path(os.environ["GITHUB_EVENT_PATH"]))
    repo = event["repository"]
    need(repo.get("private") is False and repo.get("fork") is False, "Public original repository required")
    need(repo["full_name"] == os.environ["GITHUB_REPOSITORY"], "Repository identity mismatch")
    need(repo["default_branch"] == "main" and os.environ["GITHUB_REF"] == "refs/heads/main", "Trusted main branch required")
    need(os.environ["GITHUB_EVENT_NAME"] in (["workflow_dispatch"] if unity else ["push", "workflow_dispatch"]), "Untrusted event")
    commit = os.environ["GITHUB_SHA"]
    need(re.fullmatch(r"[0-9a-f]{40}", commit), "Invalid commit")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    need(head == commit, "Checkout identity mismatch")
    run, attempt = os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]
    need(re.fullmatch(r"[1-9][0-9]*", run) and re.fullmatch(r"[1-9][0-9]*", attempt), "Invalid run identity")
    return {"repository": repo["full_name"], "commit": commit, "runId": run, "runAttempt": attempt,
            "sourceSha256": content_identity()}


def validate_request(value):
    need(isinstance(value, dict) and set(value) == FIELDS, "Request fields differ from fixed schema")
    need(value["schema"] == "task-workbench/request-v1" and value["task"] == "data-summary", "Unknown task")
    need(value["mode"] in ("complete", "checkpoint", "recover"), "Unknown mode")
    need(isinstance(value["requestId"], str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", value["requestId"]), "Invalid request ID")
    need(isinstance(value["resumeRunId"], str), "Resume ID must be a string")
    need(bool(re.fullmatch(r"[1-9][0-9]{0,19}", value["resumeRunId"])) if value["mode"] == "recover" else value["resumeRunId"] == "", "Invalid resume request")
    need(isinstance(value["resumeRequestId"], str), "Resume request ID must be a string")
    need(bool(re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", value["resumeRequestId"])) if value["mode"] == "recover" else value["resumeRequestId"] == "", "Invalid resume request identity")
    need(value["requestId"] != value["resumeRequestId"], "Recovery requires a fresh request ID")
    return value


def request():
    if os.environ["GITHUB_EVENT_NAME"] == "push":
        return validate_request(read_json(ROOT / "requests/current.json"))
    return validate_request({"schema": "task-workbench/request-v1", "task": os.environ["TASK_ID"],
                             "mode": os.environ["TASK_MODE"], "resumeRunId": os.environ.get("RESUME_RUN_ID", ""),
                             "resumeRequestId": os.environ.get("RESUME_REQUEST_ID", ""),
                             "requestId": "manual-" + os.environ["GITHUB_RUN_ID"]})


def catalog():
    value = read_json(ROOT / "tasks/catalog.json")
    schema = read_json(ROOT / "schemas/catalog.schema.json")
    expected_tasks = schema["properties"]["tasks"]["properties"]
    need(set(value) == {"schema", "tasks"}, "Unknown catalog field")
    need(value["schema"] == "task-workbench/catalog-v1" and set(value["tasks"]) == {"data-summary", "unity-proof"}, "Unexpected task catalog")
    for name, entry in value["tasks"].items():
        expected = {key: spec["const"] for key, spec in expected_tasks[name]["properties"].items()}
        need(entry == expected, "Catalog/schema mismatch")
    t = value["tasks"]["data-summary"]
    need(t["runner"] == "ubuntu-24.04" and t["stages"] == ["index", "report"] and t["secrets"] == [] and t["timeoutMinutes"] == 10, "Task contract mismatch")
    need(t["input"] == "tasks/data-summary/input.csv" and t["inputSha256"] == sha(ROOT / t["input"]), "Input pin mismatch")
    return t


def make_index():
    t = catalog()
    rows = list(csv.DictReader(io.StringIO((ROOT / t["input"]).read_text())))
    need(0 < len(rows) <= 10000, "Bounded nonempty input required")
    totals = {}
    for row in rows:
        need(set(row) == {"category", "units"} and re.fullmatch(r"[a-z]{1,24}", row["category"]), "Invalid row")
        need(re.fullmatch(r"[0-9]{1,6}", row["units"]), "Invalid quantity")
        totals[row["category"]] = totals.get(row["category"], 0) + int(row["units"])
    return {"rowCount": len(rows), "totals": totals, "totalUnits": sum(totals.values())}


def validate_checkpoint(directory, ctx, expected_run=None):
    need(directory.is_dir() and not directory.is_symlink(), "Checkpoint directory missing or linked")
    actual = {p.name for p in directory.iterdir()}
    need(actual <= FILES and {"checkpoint.json", "index.json"} <= actual, "Unexpected checkpoint payload")
    for p in directory.iterdir():
        safe_file(p)
        need(p.stat().st_size <= 1024 * 1024, "Oversized checkpoint file")
    cp = read_json(directory / "checkpoint.json")
    need(set(cp) == {"schema", "task", "stage", "stageStatus", "identity", "inputSha256", "indexSha256"}, "Checkpoint fields mismatch")
    need(cp["schema"] == "task-workbench/checkpoint-v1" and cp["task"] == "data-summary" and cp["stage"] == "index" and cp["stageStatus"] == "PASSED", "Unsuccessful or foreign checkpoint")
    need(cp["identity"]["repository"] == ctx["repository"] and cp["identity"]["sourceSha256"] == ctx["sourceSha256"], "Source/task revision changed; restart required")
    if expected_run:
        need(cp["identity"]["runId"] == expected_run, "Checkpoint run mismatch")
    need(cp["inputSha256"] == catalog()["inputSha256"], "Checkpoint input mismatch")
    need(cp["indexSha256"] == sha(directory / "index.json"), "Checkpoint output hash mismatch")
    need(read_json(directory / "index.json") == make_index(), "Checkpoint result independently disagrees with input")
    return cp


def api(path):
    # Only hard-coded GitHub API paths assembled from validated repository/run IDs.
    raw = subprocess.check_output(["gh", "api", path], text=True)
    need(len(raw) <= 2 * 1024 * 1024, "Unexpected API response size")
    return json.loads(raw, object_pairs_hook=pairs)


def release_for(ctx, request_id):
    need(re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", request_id), "Invalid release identity")
    path = "repos/" + ctx["repository"] + "/releases/tags/task-" + request_id
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    need(len(result.stdout) <= 2 * 1024 * 1024, "Unexpected release response")
    value = json.loads(result.stdout, object_pairs_hook=pairs)
    if result.returncode:
        need(value.get("status") == "404" or value.get("status") == 404, "Release lookup failed")
        return None
    return value


def fetch_release(ctx, release, destination):
    need(release.get("draft") is False, "Incomplete draft Release is not reusable")
    assets = release["assets"]
    names = [a["name"] for a in assets]
    need(len(names) == len(set(names)) and set(names) <= FILES and {"checkpoint.json", "index.json", "receipt.json", "SHA256SUMS", "release-notes.md"} <= set(names), "Release payload inventory mismatch")
    need(sum(a["size"] for a in assets) <= 2 * 1024 * 1024, "Release payload too large")
    destination.mkdir(exist_ok=False)
    for a in assets:
        need(type(a["id"]) is int and a["id"] > 0 and 0 < a["size"] <= 1024 * 1024, "Invalid release asset")
        target = destination / a["name"]
        with target.open("xb") as f:
            subprocess.check_call(["gh", "api", "repos/" + ctx["repository"] + "/releases/assets/" + str(a["id"]), "-H", "Accept: application/octet-stream"], stdout=f)
        need(target.stat().st_size == a["size"] and a.get("digest") == "sha256:" + sha(target), "Release byte/hash mismatch")
    return read_json(destination / "receipt.json")


def verify_run_metadata(ctx, run, attempt=None):
    need(re.fullmatch(r"[1-9][0-9]{0,19}", run), "Invalid source run")
    suffix = ""
    if attempt is not None:
        need(re.fullmatch(r"[1-9][0-9]{0,9}", attempt), "Invalid source attempt")
        suffix = "/attempts/" + attempt
    value = api("repos/" + ctx["repository"] + "/actions/runs/" + run + suffix)
    need(str(value["id"]) == run and value["repository"]["full_name"] == ctx["repository"], "Foreign source run")
    need(value["path"] == WORKFLOW and value["event"] in ("push", "workflow_dispatch") and value["head_branch"] == "main", "Untrusted source workflow")
    if attempt is not None:
        need(str(value["run_attempt"]) == attempt, "Source attempt mismatch")
    return value


def fetch(ctx, run, destination, current=False):
    need(re.fullmatch(r"[1-9][0-9]{0,19}", run), "Invalid source run")
    need(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", ctx["repository"]), "Invalid repository")
    prefix = "repos/" + ctx["repository"] + "/actions/"
    metadata = api(prefix + "runs/" + run)
    need(str(metadata["id"]) == run and metadata["repository"]["full_name"] == ctx["repository"], "Foreign source run")
    need(metadata["path"] == WORKFLOW and metadata["event"] in ("push", "workflow_dispatch") and metadata["head_branch"] == "main", "Untrusted source workflow")
    if not current:
        need(metadata["status"] == "completed" and metadata["conclusion"] in ("success", "failure"), "Checkpoint run is not finished")
    name = "workbench-" + run + "-" + str(metadata["run_attempt"])
    artifacts = api(prefix + "runs/" + run + "/artifacts?per_page=100")
    need(artifacts["total_count"] <= 100, "Unexpected artifact inventory")
    matches = [a for a in artifacts["artifacts"] if a["name"] == name]
    need(len(matches) == 1 and not matches[0]["expired"] and 0 < matches[0]["size_in_bytes"] <= 2 * 1024 * 1024, "Missing/expired/oversized checkpoint; recompute from Git")
    aid = matches[0]["id"]
    need(type(aid) is int and aid > 0, "Invalid artifact ID")
    temp = ROOT / "workbench-transfer"
    temp.mkdir(exist_ok=False)
    archive = temp / "payload.zip"
    with archive.open("xb") as target:
        subprocess.check_call(["gh", "api", prefix + "artifacts/" + str(aid) + "/zip"], stdout=target)
    need(archive.stat().st_size <= 2 * 1024 * 1024, "Downloaded artifact exceeds cap")
    destination.mkdir(exist_ok=False)
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        need(len(names) == len(set(names)) and set(names) <= FILES and {"checkpoint.json", "index.json"} <= set(names), "Unsafe archive members")
        need(sum(i.file_size for i in infos) <= 2 * 1024 * 1024, "Expanded payload too large")
        for info in infos:
            need(not info.is_dir() and ((info.external_attr >> 16) & 0o170000) != 0o120000, "Archive links forbidden")
            with (destination / info.filename).open("xb") as f:
                f.write(z.read(info))
    cp = validate_checkpoint(destination, ctx, run)
    need(cp["identity"]["commit"] == metadata["head_sha"] and cp["identity"]["runAttempt"] == str(metadata["run_attempt"]), "Receipt differs from GitHub run identity")
    return metadata


def run_task(ctx, req, output=OUT, resume=RESUME, report_builder=None):
    output.mkdir(exist_ok=False)
    status, error, resumed = "FAILED", None, None
    stages = []
    try:
        catalog()
        if req["mode"] == "recover":
            resumed = validate_checkpoint(resume, ctx, req["resumeRunId"])
            shutil.copyfile(resume / "index.json", output / "index.json")
        else:
            write_json(output / "index.json", make_index())
        cp = {"schema": "task-workbench/checkpoint-v1", "task": "data-summary", "stage": "index", "stageStatus": "PASSED",
              "identity": ctx, "inputSha256": catalog()["inputSha256"], "indexSha256": sha(output / "index.json")}
        write_json(output / "checkpoint.json", cp)
        stages.append({"stage": "index", "status": "RESTORED_VERIFIED" if resumed else "PASSED"})
        status = "CHECKPOINT"
        if req["mode"] != "checkpoint":
            value = read_json(output / "index.json")
            if report_builder:
                report_builder(value)  # Injection only in local tests, never a dispatch input.
            result = {"schema": "task-workbench/result-v1", "task": "data-summary", "rowCount": value["rowCount"],
                      "totalUnits": value["totalUnits"], "rankedCategories": sorted(value["totals"].items(), key=lambda p: (-p[1], p[0]))}
            write_json(output / "result.json", result)
            stages.append({"stage": "report", "status": "PASSED"})
            status = "COMPLETED"
    except Exception as exc:
        status = "FAILED_WITH_CHECKPOINT" if (output / "checkpoint.json").exists() else "FAILED"
        error = {"type": type(exc).__name__, "message": str(exc)[:500]}
    receipt = {"schema": "task-workbench/receipt-v1", "identity": ctx, "request": req, "status": status, "stages": stages,
               "restoredFrom": resumed["identity"] if resumed else None, "error": error,
               "scope": "Original bounded CSV task only; Unity/game/device stages have not run",
               "files": {p.name: sha(p) for p in sorted(output.iterdir())}}
    write_json(output / "receipt.json", receipt)
    (output / "release-notes.md").write_text("Task: data-summary\nStatus: " + status + "\nCommit: " + ctx["commit"] + "\nRun: " + ctx["runId"] + "\nThis is a bounded public sample, not Unity or device acceptance.\n")
    (output / "SHA256SUMS").write_text("".join(sha(p) + "  " + p.name + "\n" for p in sorted(output.iterdir()) if p.name != "SHA256SUMS"))
    return receipt


def verify_publish(ctx, directory=OUT, exact=True):
    cp = validate_checkpoint(directory, ctx, ctx["runId"] if exact else None)
    r = read_json(directory / "receipt.json")
    need(r["identity"] == cp["identity"], "Receipt/checkpoint identity mismatch")
    need((not exact or r["identity"] == ctx) and r["status"] in ("COMPLETED", "CHECKPOINT", "FAILED_WITH_CHECKPOINT"), "Invalid publish receipt")
    need(set(r["files"]) == ({"checkpoint.json", "index.json", "result.json"} if r["status"] == "COMPLETED" else {"checkpoint.json", "index.json"}), "Unexpected evidence inventory")
    for name, value in r["files"].items():
        need(sha(directory / name) == value, "Evidence hash changed")
    need(r["stages"] and r["stages"][0] in ({"stage": "index", "status": "PASSED"}, {"stage": "index", "status": "RESTORED_VERIFIED"}), "Missing verified stage")
    if r["status"] == "COMPLETED":
        need(r["stages"][1:] == [{"stage": "report", "status": "PASSED"}] and r["error"] is None, "False completion")
        index = make_index()
        expected = {"schema": "task-workbench/result-v1", "task": "data-summary", "rowCount": index["rowCount"],
                    "totalUnits": index["totalUnits"], "rankedCategories": [list(p) for p in sorted(index["totals"].items(), key=lambda p: (-p[1], p[0]))]}
        need(read_json(directory / "result.json") == expected, "Report differs from source computation")
    else:
        need(len(r["stages"]) == 1 and ((r["error"] is None) == (r["status"] == "CHECKPOINT")), "Partial status mismatch")
    sums = "".join(sha(p) + "  " + p.name + "\n" for p in sorted(directory.iterdir()) if p.name != "SHA256SUMS")
    need((directory / "SHA256SUMS").read_text() == sums, "Checksum list differs")
    return r


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["run", "publish", "guard-unity"])
    args = parser.parse_args()
    ctx = trusted_context(args.operation == "guard-unity")
    if args.operation == "guard-unity":
        return
    if args.operation == "publish":
        fetch(ctx, ctx["runId"], OUT, current=True)
        r = verify_publish(ctx)
        validate_request(r["request"])
        tag = "task-" + r["request"]["requestId"]
        subprocess.check_call(["gh", "release", "create", tag, "--repo", ctx["repository"], "--target", ctx["commit"],
                               "--title", "data-summary " + r["status"], "--notes-file", str(OUT / "release-notes.md"),
                               "--latest=false", "--draft"] + [str(p) for p in sorted(OUT.iterdir())])
        # REST tag lookup excludes drafts. CLI resolves the owned draft by tag.
        draft_info = json.loads(subprocess.check_output(["gh", "release", "view", tag, "--repo", ctx["repository"], "--json", "apiUrl"], text=True), object_pairs_hook=pairs)
        base = "https://api.github.com/repos/" + ctx["repository"] + "/releases/"
        need(isinstance(draft_info.get("apiUrl"), str) and draft_info["apiUrl"].startswith(base), "Foreign draft API URL")
        draft_id = draft_info["apiUrl"][len(base):]
        need(re.fullmatch(r"[1-9][0-9]*", draft_id), "Invalid draft release ID")
        release = api("repos/" + ctx["repository"] + "/releases/" + draft_id)
        need(release["tag_name"] == tag and release["target_commitish"] == ctx["commit"], "Draft target mismatch")
        expected = {p.name: p.stat().st_size for p in OUT.iterdir()}
        need({a["name"]: a["size"] for a in release["assets"]} == expected, "Published asset inventory differs")
        # Current GitHub REST also supplies digest; do not claim byte re-download.
        for asset in release["assets"]:
            need(asset.get("digest") == "sha256:" + sha(OUT / asset["name"]), "Published asset digest missing or different")
        need(release.get("draft") is True, "Expected a private draft before publication")
        subprocess.check_call(["gh", "release", "edit", tag, "--repo", ctx["repository"], "--draft=false", "--latest=false"])
        release = api("repos/" + ctx["repository"] + "/releases/tags/" + tag)
        need(release.get("draft") is False, "Release publication not confirmed")
        ref = api("repos/" + ctx["repository"] + "/git/ref/tags/" + tag)
        need(ref["object"]["type"] == "commit" and ref["object"]["sha"] == ctx["commit"], "Release tag does not identify the measured commit")
        print("Verified Release: " + release["html_url"])
        return
    req = request()
    previous = release_for(ctx, req["requestId"])
    if previous:
        old = fetch_release(ctx, previous, RESUME)
        verify_publish(ctx, RESUME, exact=False)
        need(old["request"] == req and old["status"] == "COMPLETED", "Request ID already exists with a different or unfinished result; use a fresh ID")
        m = verify_run_metadata(ctx, old["identity"]["runId"], old["identity"]["runAttempt"])
        need(m["head_sha"] == old["identity"]["commit"] and m["status"] == "completed", "Old result source identity mismatch")
        print("REUSED_VERIFIED_COMPLETED_RESULT " + previous["html_url"])
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("Reused a previously completed result after re-downloading and verifying every SHA: " + previous["html_url"] + "\n")
        return
    if req["mode"] == "recover":
        saved = release_for(ctx, req["resumeRequestId"])
        if saved:
            prior = fetch_release(ctx, saved, RESUME)
            verify_publish(ctx, RESUME, exact=False)
            m = verify_run_metadata(ctx, req["resumeRunId"], prior["identity"]["runAttempt"])
            need(m["status"] == "completed" and m["conclusion"] in ("success", "failure"), "Source run unfinished")
            need(prior["identity"]["runId"] == req["resumeRunId"] and prior["identity"]["commit"] == m["head_sha"] and prior["identity"]["runAttempt"] == str(m["run_attempt"]), "Recovery source identity mismatch")
        else:
            fetch(ctx, req["resumeRunId"], RESUME)
            prior = verify_publish(ctx, RESUME, exact=False)
        need(prior["request"]["requestId"] == req["resumeRequestId"], "Wrong recovery request")
    r = run_task(ctx, req)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
        f.write("data-summary: " + r["status"] + "\nCommit: " + ctx["commit"] + "\n")
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write("checkpoint=" + str((OUT / "checkpoint.json").exists()).lower() + "\n")
    if r["status"].startswith("FAILED"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
