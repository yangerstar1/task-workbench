#!/usr/bin/env python3
"""Actual child-process SIGKILL; synthetic inputs, production pure-Core source."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import g2_ci as ci

POINTS = ("BeforeWrite", "TempHalfWritten", "TempFlushed", "BeforePublish", "AfterPublish", "BeforeResponse")
SCENARIOS = ("buy", "scratch", "claim", "ad")


def validate_case(data, scenario, point):
    expected_keys = {"status", "scenario", "point", "recoveryStatus", "beforeHash", "expectedHash", "recoveredHash", "finalHash",
                     "finalCashMinor", "finalCommands", "attemptCommandOccurrences", "staleRevisionReplayUnchanged"}
    ci.require(isinstance(data, dict) and set(data) == expected_keys, "Process case schema mismatch")
    published = point in {"AfterPublish", "BeforeResponse"}
    ci.require(data["status"] == "PASS" and data["scenario"] == scenario and data["point"] == point and
               data["recoveryStatus"] == ("COMMITTED" if published else "PROVEN_NOT_COMMITTED"), "Process boundary mismatch")
    for field in ("beforeHash", "expectedHash", "recoveredHash", "finalHash"):
        ci.require(isinstance(data[field], str) and re.fullmatch(r"[0-9a-f]{64}", data[field]), "Process state hash malformed")
    ci.require(data["beforeHash"] != data["expectedHash"] and data["finalHash"] == data["expectedHash"] and
               data["recoveredHash"] == data["expectedHash" if published else "beforeHash"], "Process state recovery mismatch")
    ci.require(type(data["finalCashMinor"]) is int and 0 <= data["finalCashMinor"] <= 1030000 and
               type(data["finalCommands"]) is int and 1 <= data["finalCommands"] <= 32 and
               type(data["attemptCommandOccurrences"]) is int and data["attemptCommandOccurrences"] == 1 and
               data["staleRevisionReplayUnchanged"] is True, "Process replay invariant mismatch")
    return data


def kill_at_marker(child, marker, point, timeout=15):
    """Only the child launched by this harness is terminated; marker text is bounded."""
    try:
        end = time.monotonic() + timeout
        while not marker.is_file() and child.poll() is None and time.monotonic() < end: time.sleep(.02)
        ci.require(marker.is_file() and ci.bounded_read(marker, 100).decode("ascii") == point and child.poll() is None, "Kill checkpoint not reached")
        os.kill(child.pid, signal.SIGKILL)
        ci.require(child.wait(timeout=10) == -signal.SIGKILL, "Child was not terminated by SIGKILL")
    finally:
        if child.poll() is None: child.kill(); child.wait(timeout=10)


STAGES = {"guard", "workspace", "sdk_inventory", "restore", "build", "binary", "prepare", "checkpoint", "verify", "result", "receipt"}
ASSERTIONS = {"ARGUMENTS", "CRASH_APPLY", "KILL_POINT_NOT_REACHED", "SETUP_BUY", "SETUP_SCRATCH", "SETUP_REVEAL",
              "AD_BEGIN", "AD_REWARD", "AD_RECORD", "AD_COMMITTING", "PREPARE_DIRECTORY", "PREPARE_EQUAL",
              "PREPARE_APPLY", "RECOVERY_BOUNDARY", "RECOVERY_REPLAY", "STALE_REPLAY", "STATE_INVARIANTS",
              "EXACTLY_ONCE", "WALLET_STOCK", "RESULT_WRITE", "UNCLASSIFIED"}
EXCEPTIONS = {"CalledProcessError", "TimeoutExpired", "FileNotFoundError", "ValueError", "OSError", "PermissionError",
              "IOException", "InvalidDataException", "InvalidOperationException", "UnauthorizedAccessException",
              "ArgumentException", "FormatException", "OverflowException", "NullReferenceException", "Other"}


def compiler_errors(raw, task):
    """Export only compiler identifiers and known source coordinates, never messages."""
    ci.require(len(raw) <= 2 * 1024 * 1024, "Compiler diagnostic input exceeds bound")
    paths = [task / "scripts/process-probe/Program.cs", task / "scripts/process-probe/G2.ProcessProbe.csproj"]
    paths += [p for part in ("Core", "Persistence", "Ads") for p in (task / "unity/Assets/G2" / part).rglob("*.cs")]
    aliases = {}
    for path in paths:
        relative = path.relative_to(task).as_posix()
        ci.require(re.fullmatch(r"[A-Za-z0-9_./-]+", relative), "Unsafe source diagnostic path")
        for alias in (str(path), relative): aliases[alias] = relative
    aliases["Program.cs"] = "scripts/process-probe/Program.cs"
    found = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        match = re.match(r"^\s*(.*?)\s*:\s*error ((?:CS|MSB|NETSDK|NU)[0-9]{4,5})(?=[:\s])", line)
        if not match: continue
        prefix, code = match.groups(); line_number = 0; column = 0
        location = re.fullmatch(r"(.*?)\(([0-9]{1,7}),([0-9]{1,7})\)", prefix)
        if location: prefix, line_number, column = location.group(1), int(location.group(2)), int(location.group(3))
        item = {"code": code, "file": aliases.get(prefix, "UNMAPPED"), "line": line_number, "column": column}
        if item not in found: found.append(item)
        if len(found) == 32: break
    return found


def worker_error(raw):
    ci.require(len(raw) <= 2 * 1024 * 1024, "Worker diagnostic input exceeds bound")
    found = None
    for line in raw.decode("utf-8", errors="replace").splitlines():
        match = re.fullmatch(r"G2_PROBE_ERROR ([A-Z_]{1,48}) ([A-Za-z]{1,48})", line)
        if match and match.group(1) in ASSERTIONS and match.group(2) in EXCEPTIONS:
            found = {"assertId": match.group(1), "exceptionType": match.group(2)}
    return found


def write_failure(task, identity, context, error):
    stage = context.get("stage"); ci.require(stage in STAGES, "Invalid diagnostic stage")
    name = type(error).__name__; name = name if name in EXCEPTIONS else "Other"
    code = error.returncode if isinstance(error, subprocess.CalledProcessError) else None
    data = dict(identity, schemaVersion=1, status="FAIL", scope="G2_PROCESS_DIAGNOSTIC_NOT_TEST_PASS",
                stage=stage, exceptionType=name, exitCode=code if type(code) is int and -255 <= code <= 255 else None,
                scenario=context.get("scenario") if context.get("scenario") in SCENARIOS else None,
                point=context.get("point") if context.get("point") in POINTS else None,
                dotnetSdk=context.get("sdk") if re.fullmatch(r"8\.0\.[0-9]+", context.get("sdk", "")) else None,
                compilerErrors=[], workerError=None, diagnosticRead="NO_LOG", deviceQa="NOT_RUN")
    work = task / "artifacts/g2-process"
    try:
        if stage in {"restore", "build", "binary"}:
            data["compilerErrors"] = compiler_errors(ci.bounded_read(work / "compile.log", 2 * 1024 * 1024), task)
            data["diagnosticRead"] = "BOUNDED_CODES_ONLY"
        elif stage in {"prepare", "checkpoint", "verify", "result"}:
            data["workerError"] = worker_error(ci.bounded_read(work / "worker.log", 2 * 1024 * 1024))
            data["diagnosticRead"] = "BOUNDED_FIXED_IDENTIFIERS_ONLY"
    except Exception:
        data["diagnosticRead"] = "REFUSED_OR_UNAVAILABLE"
    output = task / "evidence/g2/process"
    (output / "process-receipt.json").unlink(missing_ok=True)
    ci.write_json(output / "process-diagnostic.json", data)


def main(root=None):
    root = root or Path(__file__).resolve().parents[3]; task = root / ci.TASK
    output = task / "evidence/g2/process/process-receipt.json"
    output.unlink(missing_ok=True); output.with_name("process-diagnostic.json").unlink(missing_ok=True)
    identity = {}; context = {"stage": "guard"}
    try:
        identity = ci.legacy.guard(root); ci.verify_inputs(root)
        context["stage"] = "workspace"
        work = task / "artifacts/g2-process"
        ci.require(not work.exists(), "Refusing to reuse old process fixture output")
        work.mkdir(parents=True)
        env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1",
                   DOTNET_CLI_HOME=str(work / "dotnet-home"), NUGET_PACKAGES=str(work / "nuget"))
        context["stage"] = "sdk_inventory"
        sdk_output = subprocess.check_output(["dotnet", "--list-sdks"], text=True, env=env, stderr=subprocess.DEVNULL, timeout=15)
        sdks = [line.split(" ", 1)[0] for line in sdk_output.splitlines() if re.match(r"8\.0\.[0-9]+ \[", line)]
        ci.require(sdks, "Runner has no installed .NET 8 SDK; no download fallback")
        sdk = max(sdks, key=lambda x: tuple(map(int, x.split(".")))); context["sdk"] = sdk
        ci.write_json(work / "global.json", {"sdk": {"version": sdk, "rollForward": "disable", "allowPrerelease": False}})
        project = task / "scripts/process-probe/G2.ProcessProbe.csproj"
        intermediate = str(work / "obj") + "/"
        # No package feed, extra action or credential; reference packs must already be installed.
        commands = [("restore", ["dotnet", "restore", str(project), "--configfile", str(project.parent / "NuGet.Config"), "-p:BaseIntermediateOutputPath=" + intermediate]),
                    ("build", ["dotnet", "build", str(project), "--no-restore", "-c", "Release", "-o", str(work / "bin"), "-p:BaseIntermediateOutputPath=" + intermediate])]
        with (work / "compile.log").open("wb") as log:
            for stage, command in commands:
                context["stage"] = stage
                subprocess.run(command, cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90, check=True)
        context["stage"] = "binary"
        binary = work / "bin/Lottery.G2.ProcessProbe.dll"
        ci.require(binary.is_file(), "Pure-Core process fixture binary missing")
        sources = sorted(p for part in ("Core", "Persistence", "Ads") for p in (task / "unity/Assets/G2" / part).rglob("*.cs"))
        source_hashes = [{"path": p.relative_to(task).as_posix(), "sha256": ci.digest(p)} for p in sources]
        ci.require(0 < len(sources) <= 64, "Unexpected pure-Core source set")
        cases = []; deadline = time.monotonic() + 300
        with (work / "worker.log").open("wb") as log:
            for scenario in SCENARIOS:
                for point in POINTS:
                    context.update(stage="prepare", scenario=scenario, point=point)
                    ci.require(time.monotonic() < deadline, "Process fixture total time exceeded")
                    directory = work / (scenario + "-" + point)
                    def command(mode): return ["dotnet", str(binary), mode, scenario, point, str(directory)]
                    subprocess.run(command("prepare"), cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=15, check=True)
                    context["stage"] = "checkpoint"
                    child = subprocess.Popen(command("crash"), cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT)
                    kill_at_marker(child, directory / "ready", point)
                    context["stage"] = "verify"
                    subprocess.run(command("verify"), cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=15, check=True)
                    context["stage"] = "result"
                    data = json.loads(ci.bounded_read(directory / "result.json", 8192))
                    cases.append(dict(validate_case(data, scenario, point), exitSignal="SIGKILL", childExitCode=-9))
        context["stage"] = "receipt"
        ci.write_json(output, dict(identity, scope="SYNTHETIC_FIXTURES_REAL_LINUX_DOTNET_PROCESS_KILL_NOT_UNITY_NOT_ANDROID",
                      status="PASS", dotnetSdk=sdk, rulesSha256=ci.RULES_SHA, sourceFiles=source_hashes,
                      workerBinarySha256=ci.digest(binary), cases=cases, count=len(cases), deviceQa="NOT_RUN",
                      unityProcessKill="NOT_RUN", androidForceStop="NOT_RUN", powerLossQa="NOT_RUN"))
    except Exception as error:
        write_failure(task, identity, context, error)
        raise
    print("24 real Linux/.NET SIGKILL recovery cases passed; Unity/Android kill remains NOT_RUN.")


if __name__ == "__main__":
    try: main()
    except Exception:
        print("G2 process probe failed; inspect bounded process-diagnostic.json. No raw logs exported.", file=sys.stderr)
        sys.exit(1)
