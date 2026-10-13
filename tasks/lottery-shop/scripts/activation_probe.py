#!/usr/bin/env python3
"""One existing-license activation diagnostic. Never outputs native raw bytes."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time

TASK = "tasks/lottery-shop"
REQUEST = TASK + "/ci/activation-probe-request.json"
WORKFLOW = ".github/workflows/lottery-activation-probe.yml"
SCOPE = "ACTIVATION_DIAGNOSTIC_ONLY_NOT_GAME_OR_G3_PASS"
PIN = "0ff419b913a3630032cbe0de48a0099b5a9f0ed9"
IMAGE = "unityci/editor@sha256:17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264"
MAX_OUTPUT = 8 * 1024 * 1024
NATIVE_COMMAND = 'unity-editor -logFile /dev/stdout -quit -serial "$UNITY_SERIAL" -username "$UNITY_EMAIL" -password "$UNITY_PASSWORD" -projectPath "/BlankProject"'
# Same Personal conditional as the pinned entrypoint, inside this disposable
# container only. Never read, retain or print the resulting machine identifier.
SHELL = '''set +x
set +v
if [[ "$UNITY_SERIAL" = F* ]]; then
  dbus-uuidgen > /etc/machine-id && mkdir -p /var/lib/dbus/ && ln -sf /etc/machine-id /var/lib/dbus/machine-id || exit 125
fi
cp -a /activation-blank-src/. /BlankProject/ || exit 125
''' + NATIVE_COMMAND + '''
code=$?
printf '\\nACTIVATION_NATIVE_EXIT_CODE=%d\\n' "$code"
exit "$code"
'''
TOKENS = {
    "entitlementActivated": b"[Licensing::Module] Successfully activated the entitlement license",
    "invalidLicenseXml400": b"[Licensing::Client] Error: Code 400 while processing request (status: license_xml is invalid.",
    "nativeActivationAborted": b"[Licensing::Module] License activation has failed. Aborting.",
    "ulfActivated": b"[Licensing::Client] Successfully activated ULF license",
}


def require(ok, code):
    if not ok:
        raise ValueError(code)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def read(path, maximum=8192):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= maximum, "INVALID_BOUNDED_INPUT")
    return json.loads(path.read_text())


def git(root, *args):
    r = subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
    require(r.returncode == 0 and len(r.stdout) < 65536, "GIT_METADATA_FAILED")
    return r.stdout.decode("ascii").strip()


def evidence(root):
    return root / TASK / "evidence/activation-probe"


def guard(root):
    expected = dict(GITHUB_EVENT_NAME="push", GITHUB_REPOSITORY="yangerstar1/task-workbench",
                    GITHUB_REPOSITORY_OWNER="yangerstar1", GITHUB_ACTOR="yangerstar1", GITHUB_TRIGGERING_ACTOR="yangerstar1",
                    GITHUB_REF="refs/heads/lottery-shop-g0-20261011")
    require(all(os.environ.get(k) == v for k, v in expected.items()), "CONTEXT_REJECTED")
    event = read(Path(os.environ["GITHUB_EVENT_PATH"]), 1024 * 1024)
    require(event.get("repository", {}).get("private") is False and event["repository"].get("fork") is False and not event.get("deleted"), "EVENT_REJECTED")
    head = os.environ.get("GITHUB_SHA", "")
    require(re.fullmatch("[0-9a-f]{40}", head) and git(root, "rev-parse", "HEAD") == head, "SOURCE_REJECTED")
    req = read(root / REQUEST)
    require(set(req) == {"schemaVersion", "requestId", "sourceCommit", "purpose", "sourceReview"}, "REQUEST_FIELDS_REJECTED")
    require(type(req["schemaVersion"]) is int and req["schemaVersion"] == 1 and req["purpose"] == SCOPE, "REQUEST_SCOPE_REJECTED")
    require(re.fullmatch(r"lottery-activation-[0-9]{8}-[0-9]{2,3}", req["requestId"]), "REQUEST_ID_REJECTED")
    require(req["sourceCommit"] == git(root, "rev-parse", "HEAD^") and git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD") == REQUEST, "REQUEST_ONLY_CHILD_REQUIRED")
    review = req["sourceReview"]
    require(isinstance(review, dict) and set(review) == {"sourceCommit", "status", "reviewedAtUtc", "reviewId", "reviewer"}, "REVIEW_FIELDS_REJECTED")
    require(review["sourceCommit"] == req["sourceCommit"] and review["status"] == "APPROVED_FOR_ACTIVATION_DIAGNOSTIC_ONLY" and review["reviewer"] == "independent-source-review", "REVIEW_REJECTED")
    require(re.fullmatch(r"activation-source-[0-9]{8}-[0-9]{2,3}", review["reviewId"]), "REVIEW_ID_REJECTED")
    stamp = datetime.fromisoformat(review["reviewedAtUtc"].replace("Z", "+00:00"))
    require(stamp.tzinfo is not None and stamp.utcoffset().total_seconds() == 0 and stamp <= datetime.now(timezone.utc), "REVIEW_TIME_REJECTED")
    require(git(root, "diff", "--name-only", "HEAD", "--", REQUEST, WORKFLOW, TASK + "/scripts") == "", "SOURCE_DIRTY")
    require(re.fullmatch(r"[1-9][0-9]*", os.environ.get("GITHUB_RUN_ID", "")) and os.environ.get("GITHUB_RUN_ATTEMPT") == "1", "FIRST_RUN_ATTEMPT_REQUIRED")
    value = dict(scope=SCOPE, sourceCommit=head, reviewedCandidateCommit=req["sourceCommit"], requestId=req["requestId"],
                 runId=os.environ["GITHUB_RUN_ID"], runAttempt=os.environ["GITHUB_RUN_ATTEMPT"], sourceReview=review,
                 approvalBasis="FIXED_ACTOR_ATTESTATION_NOT_CRYPTOGRAPHIC_SIGNATURE")
    write(evidence(root) / "source-receipt.json", value)
    return value


def derive_serial(license_text):
    # Exact DeveloperData/base64/four-byte-prefix mechanism of pinned input.ts;
    # stricter bounds fail closed. Values never enter output/receipts/host argv.
    require(isinstance(license_text, str) and 0 < len(license_text) <= 65536, "INPUT_REJECTED")
    match = re.search(r'<DeveloperData Value="([A-Za-z0-9+/=]+)"/>', license_text)
    require(match is not None, "INPUT_REJECTED")
    value = base64.b64decode(match.group(1), validate=True)[4:].decode("ascii")
    require(re.fullmatch(r"[A-Z0-9]{2}-[A-Z0-9]{4}(?:-[A-Z0-9]{4}){4}", value), "INPUT_REJECTED")
    return value


class Scan:
    def __init__(self):
        self.counts = {key: 0 for key in TOKENS}
        self.carry = b""
        self.total = 0
        self.native_exit = None
        self.exit_markers = 0

    def feed(self, chunk):
        self.total += len(chunk)
        require(self.total <= MAX_OUTPUT, "OUTPUT_LIMIT")
        # Only constant-byte matches; malformed UTF-8 is never decoded or echoed.
        joined = self.carry + chunk
        for key, token in TOKENS.items():
            self.counts[key] += joined.count(token) - self.carry.count(token)
        for match in re.finditer(rb"(?:^|\n)ACTIVATION_NATIVE_EXIT_CODE=([0-9]{1,3})\r?\n", joined):
            if match.end() > len(self.carry):
                self.native_exit = int(match.group(1)); self.exit_markers += 1
        self.carry = joined[-256:]


def captured(command, timeout, env=None, scan=None):
    scan = scan or Scan()
    start = time.monotonic()
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            if time.monotonic() - start > timeout:
                raise TimeoutError("TIMEOUT")
            for key, _ in selector.select(.2):
                chunk = os.read(key.fd, 8192)
                if chunk: scan.feed(chunk)
                else: selector.unregister(key.fileobj)
        return child.wait(timeout=5), scan
    finally:
        selector.close()
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL); child.wait(timeout=5)
        child.stdout.close()
        scan.carry = b""


def cleanup(name):
    # Only this attempt's exact container name. A successful empty query is the
    # absence proof; rm alone may fail simply because --rm already removed it.
    removed_code = None
    try:
        removed = subprocess.run(["docker", "rm", "--force", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        removed_code = removed.returncode
        verified = subprocess.run(["docker", "ps", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.Names}}"],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20)
        if verified.returncode != 0 or len(verified.stdout) > 256:
            return dict(status="ABSENCE_CHECK_FAILED", removalExitCode=removed_code)
        if verified.stdout.strip() == b"":
            return dict(status="ABSENCE_VERIFIED", removalExitCode=removed_code)
        return dict(status="CONTAINER_STILL_PRESENT", removalExitCode=removed_code)
    except subprocess.TimeoutExpired:
        return dict(status="CLEANUP_TIMEOUT", removalExitCode=removed_code)
    except BaseException:
        return dict(status="CLEANUP_FAILED", removalExitCode=removed_code)


def diagnose(root):
    ident = guard(root)
    upstream = root / ".activation-upstream"
    require(git(upstream, "rev-parse", "HEAD") == PIN, "UPSTREAM_PIN_REJECTED")
    activate = (upstream / "dist/platforms/ubuntu/activate.sh").read_text()
    require(NATIVE_COMMAND in re.sub(r"\s+", " ", activate.replace("\\\n", "")), "UPSTREAM_COMMAND_REJECTED")
    result = dict(ident, schemaVersion=1, image=IMAGE, mechanismSourcePin=PIN, maximumNativeInvocations=1,
                  status="NOT_STARTED", activationStatus="NOT_STARTED", cleanup=None, dockerExitCode=None, nativeExitCode=None, nativeExitMarkerCount=0,
                  observations={key: 0 for key in TOKENS}, rawOutput="MEMORY_ONLY_NOT_LOGGED_OR_UPLOADED",
                  gameTests="NOT_RUN", deviceQa="NOT_RUN", g3Gate="NOT_EVALUATED")
    name = "lottery-activation-" + ident["runId"] + "-" + ident["runAttempt"]
    started = time.monotonic(); scanner = Scan()
    try:
        # Pull output is captured with the same bounded non-logging path.
        pull, _ = captured(["docker", "pull", IMAGE], 600)
        if pull != 0:
            result.update(status="IMAGE_PULL_FAILED", dockerExitCode=pull); raise RuntimeError("IMAGE_PULL_FAILED")
        env = dict(os.environ)
        env["UNITY_SERIAL"] = derive_serial(env.pop("UNITY_LICENSE", ""))
        require(all(env.get(k) and len(env[k]) <= 4096 for k in ("UNITY_EMAIL", "UNITY_PASSWORD")), "INPUT_REJECTED")
        # No project checkout, Docker socket, host home, or host license mount.
        # BlankProject/config are the same public pinned action inputs; root and
        # its transient activation files are inside the disposable container.
        command = ["docker", "run", "--rm", "--log-driver=none", "--name", name, "--cpus=2", "--memory=12g",
                   "--workdir", "/BlankProject", "--env", "UNITY_SERIAL", "--env", "UNITY_EMAIL", "--env", "UNITY_PASSWORD",
                   "--volume", str(upstream / "dist/BlankProject") + ":/activation-blank-src:ro",
                   "--volume", str(upstream / "dist/unity-config") + ":/usr/share/unity3d/config:ro",
                   IMAGE, "/bin/bash", "-c", SHELL]
        code, scanner = captured(command, 180, env, scanner)
        result.update(dockerExitCode=code, nativeExitCode=scanner.native_exit, nativeExitMarkerCount=scanner.exit_markers)
        # Process status is authoritative. Text observations cannot grant success.
        ok = code == 0 and scanner.exit_markers == 1 and scanner.native_exit == 0
        contradicted = scanner.counts["invalidLicenseXml400"] > 0 or scanner.counts["nativeActivationAborted"] > 0
        result["status"] = "INCONSISTENT_NATIVE_RESULT" if ok and contradicted else ("ACTIVATION_SUCCEEDED_ONLY" if ok else "ACTIVATION_FAILED")
    except TimeoutError:
        result["status"] = "PROCESS_TIMEOUT"
    except ValueError:
        result["status"] = "INPUT_OR_OUTPUT_BOUND_REJECTED"
    except (KeyboardInterrupt, InterruptedError):
        result["status"] = "CANCELLED"
    except Exception:
        if result["status"] != "IMAGE_PULL_FAILED": result["status"] = "ADAPTER_FAILED"
    finally:
        result["activationStatus"] = result["status"]
        result["cleanup"] = cleanup(name)
        if result["cleanup"]["status"] != "ABSENCE_VERIFIED": result["status"] = "CLEANUP_NOT_VERIFIED"
        # Retain known observations even if a later timeout/cancel hid process exit.
        result["nativeExitCode"] = scanner.native_exit
        result["nativeExitMarkerCount"] = scanner.exit_markers
        scanner.carry = b""
        result["observations"] = scanner.counts
        result["elapsedMs"] = int((time.monotonic() - started) * 1000)
        result["recordedAtUtc"] = datetime.now(timezone.utc).isoformat()
        write(evidence(root) / "activation-receipt.json", result)
        print("ACTIVATION_DIAGNOSTIC_RECEIPT_WRITTEN")
    return 0 if result["status"] == "ACTIVATION_SUCCEEDED_ONLY" else 1


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=("guard", "diagnose")); args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    def stop(_signal, _frame): raise InterruptedError("CANCELLED")
    signal.signal(signal.SIGTERM, stop)
    try:
        if args.mode == "guard": guard(root); print("ACTIVATION_DIAGNOSTIC_SOURCE_GUARD_OK"); return 0
        return diagnose(root)
    except BaseException:
        # Never render exception text, argv, env, raw subprocess output or tracebacks.
        print("ACTIVATION_DIAGNOSTIC_ADAPTER_REJECTED"); return 1


if __name__ == "__main__":
    raise SystemExit(main())
