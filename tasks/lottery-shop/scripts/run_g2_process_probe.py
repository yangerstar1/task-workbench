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


def main():
    root = Path(__file__).resolve().parents[3]; task = root / ci.TASK
    identity = ci.legacy.guard(root); ci.verify_inputs(root)
    output = task / "evidence/g2/process/process-receipt.json"
    output.unlink(missing_ok=True)
    work = task / "artifacts/g2-process"
    ci.require(not work.exists(), "Refusing to reuse old process fixture output")
    work.mkdir(parents=True)
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1",
               DOTNET_CLI_HOME=str(work / "dotnet-home"), NUGET_PACKAGES=str(work / "nuget"))
    sdk_output = subprocess.check_output(["dotnet", "--list-sdks"], text=True, env=env, timeout=15)
    sdks = [line.split(" ", 1)[0] for line in sdk_output.splitlines() if re.match(r"8\.0\.[0-9]+ \[", line)]
    ci.require(sdks, "Runner has no installed .NET 8 SDK; no download fallback")
    sdk = max(sdks, key=lambda x: tuple(map(int, x.split("."))))
    ci.write_json(work / "global.json", {"sdk": {"version": sdk, "rollForward": "disable", "allowPrerelease": False}})
    project = task / "scripts/process-probe/G2.ProcessProbe.proj"
    intermediate = str(work / "obj") + "/"
    # No package feed, extra action or credential; reference packs must already be installed.
    commands = [["dotnet", "restore", str(project), "--configfile", str(project.parent / "NuGet.Config"), "-p:BaseIntermediateOutputPath=" + intermediate],
                ["dotnet", "build", str(project), "--no-restore", "-c", "Release", "-o", str(work / "bin"), "-p:BaseIntermediateOutputPath=" + intermediate]]
    with (work / "compile.log").open("wb") as log:
        for command in commands:
            subprocess.run(command, cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90, check=True)
    binary = work / "bin/Lottery.G2.ProcessProbe.dll"
    ci.require(binary.is_file(), "Pure-Core process fixture binary missing")
    sources = sorted(p for part in ("Core", "Persistence", "Ads") for p in (task / "unity/Assets/G2" / part).rglob("*.cs"))
    source_hashes = [{"path": p.relative_to(task).as_posix(), "sha256": ci.digest(p)} for p in sources]
    ci.require(0 < len(sources) <= 64, "Unexpected pure-Core source set")
    cases = []; deadline = time.monotonic() + 300
    with (work / "worker.log").open("wb") as log:
        for scenario in SCENARIOS:
            for point in POINTS:
                ci.require(time.monotonic() < deadline, "Process fixture total time exceeded")
                directory = work / (scenario + "-" + point)
                def command(mode): return ["dotnet", str(binary), mode, scenario, point, str(directory)]
                subprocess.run(command("prepare"), cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=15, check=True)
                child = subprocess.Popen(command("crash"), cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT)
                kill_at_marker(child, directory / "ready", point)
                subprocess.run(command("verify"), cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=15, check=True)
                data = json.loads(ci.bounded_read(directory / "result.json", 8192))
                cases.append(dict(validate_case(data, scenario, point), exitSignal="SIGKILL", childExitCode=-9))
    ci.write_json(output, dict(identity, scope="SYNTHETIC_FIXTURES_REAL_LINUX_DOTNET_PROCESS_KILL_NOT_UNITY_NOT_ANDROID",
                  status="PASS", dotnetSdk=sdk, rulesSha256=ci.RULES_SHA, sourceFiles=source_hashes,
                  workerBinarySha256=ci.digest(binary), cases=cases, count=len(cases), deviceQa="NOT_RUN",
                  unityProcessKill="NOT_RUN", androidForceStop="NOT_RUN", powerLossQa="NOT_RUN"))
    print("24 real Linux/.NET SIGKILL recovery cases passed; Unity/Android kill remains NOT_RUN.")


if __name__ == "__main__":
    try: main()
    except Exception:
        print("G2 process probe failed; no PASS receipt exported. Compile/worker logs remain unexported.", file=sys.stderr)
        sys.exit(1)
