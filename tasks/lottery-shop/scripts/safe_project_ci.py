#!/usr/bin/env python3
"""Pinned-command Unity project runs with private bounded process output."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import signal
import time
import activation_probe as private
import visual_candidate_ci as visual

PHASES = {
    'capture': ('playmode', 'visual-candidate', 'Lottery.G3.VisualCandidate.Tests', 1800),
    'regression-edit': ('editmode', 'visual-regression-edit', 'Lottery.Probe.Tests;Lottery.G2.EditMode.Tests;Lottery.G3.EditMode.Tests', 480),
    'regression-play': ('playmode', 'visual-regression-play', 'Lottery.G2.PlayMode.Tests;Lottery.G3.PlayMode.Tests', 480),
}
COVERAGE = 'generateAdditionalMetrics;generateHtmlReport;generateBadgeReport;dontClear'
RETURN_COMMAND = 'unity-editor -logFile /dev/stdout -quit -returnlicense -username "$UNITY_EMAIL" -password "$UNITY_PASSWORD" -projectPath "/BlankProject"'
MARKER = b'SAFE_PROJECT_NATIVE_EXIT_CODE='


class ProcessScan(private.Scan):
    def feed(self, chunk):
        self.total += len(chunk)
        private.require(self.total <= private.MAX_OUTPUT, 'OUTPUT_LIMIT')
        joined = self.carry + chunk
        for key, token in private.TOKENS.items():
            self.counts[key] += joined.count(token) - self.carry.count(token)
        for match in re.finditer(rb'(?:^|\n)SAFE_PROJECT_NATIVE_EXIT_CODE=([0-9]{1,3})\r?\n', joined):
            if match.end() > len(self.carry):
                self.native_exit = int(match.group(1)); self.exit_markers += 1
        self.carry = joined[-256:]


def identity(root):
    value = visual.identity(root)
    private.require(value['runId'] == os.environ.get('GITHUB_RUN_ID') and value['runAttempt'] == os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'IDENTITY_REJECTED')
    return value


def name(ident):
    return 'lottery-visual-safe-' + ident['runId'] + '-' + ident['runAttempt']


def file(root, phase):
    private.require(phase in ('start', 'finish', 'session') or phase in PHASES, 'PHASE_REJECTED')
    return visual.outdir(root) / ('safe-' + phase + '.json')


def session(root, ident):
    value = private.read(file(root, 'session'))
    private.require(all(value[k] == ident[k] for k in ('sourceCommit', 'runId', 'runAttempt')), 'SESSION_IDENTITY_REJECTED')
    return value


def process_receipt(ident, phase):
    return dict(ident, schemaVersion=1, phase=phase, status='NOT_STARTED', dockerExitCode=None, nativeExitCode=None,
                nativeExitMarkerCount=0, observations={key: 0 for key in private.TOKENS}, cleanup=None,
                image=private.IMAGE, mechanismSourcePin=private.PIN, nativeOutput='BOUNDED_MEMORY_ONLY_NO_RAW_LOG',
                testVerdict='SEPARATE_EXACT_NUNIT_VALIDATOR_REQUIRED')


def shell(command):
    return 'set +x\nset +v\n' + command + '\ncode=$?\nprintf "\\nSAFE_PROJECT_NATIVE_EXIT_CODE=%d\\n" "$code"\nexit "$code"\n'


def native(ident, command, seconds, record):
    scan = ProcessScan()
    try:
        code, scan = private.captured(['docker', 'exec', name(ident), '/bin/bash', '-c', command], seconds, scan=scan)
        record['dockerExitCode'] = code
        consistent = scan.exit_markers == 1 and scan.native_exit == code
        rejected = scan.counts['invalidLicenseXml400'] > 0 or scan.counts['nativeActivationAborted'] > 0
        record['status'] = 'NATIVE_SUCCEEDED' if consistent and code == 0 and not rejected else ('INCONSISTENT_NATIVE_RESULT' if code == 0 else 'NATIVE_FAILED')
    except TimeoutError: record['status'] = 'PROCESS_TIMEOUT'
    except ValueError: record['status'] = 'OUTPUT_LIMIT_OR_INPUT_REJECTED'
    except (KeyboardInterrupt, InterruptedError): record['status'] = 'CANCELLED'
    except Exception: record['status'] = 'ADAPTER_FAILED'
    finally:
        record['nativeExitCode'] = scan.native_exit
        record['nativeExitMarkerCount'] = scan.exit_markers
        record['observations'] = scan.counts
        scan.carry = b''


def project_argv(phase, ident):
    platform, folder, assemblies, _ = PHASES[phase]
    argv = ['unity-editor', '-batchmode', '-logFile', '/dev/stdout', '-projectPath', '/github/workspace/' + private.TASK + '/unity',
            '-coverageResultsPath', '/github/workspace/CodeCoverage', '-runTests', '-testPlatform', platform,
            '-testResults', '/github/workspace/' + private.TASK + '/artifacts/' + folder + '/' + platform + '-results.xml',
            '-enableCodeCoverage', '-debugCodeOptimization', '-coverageOptions', COVERAGE, '-assemblyNames', assemblies]
    if phase != 'regression-edit': argv += ['-force-glcore', '-screen-width', '1280', '-screen-height', '720']
    argv += ['-job-worker-count', '2', '-probeCommit', ident['sourceCommit'], '-probeRunId', ident['runId']]
    if phase == 'capture': argv += ['-probeRunAttempt', ident['runAttempt']]
    return argv


def save(root, phase, record, started):
    record['elapsedMs'] = int((time.monotonic() - started) * 1000)
    record['recordedAtUtc'] = datetime.now(timezone.utc).isoformat()
    private.write(file(root, phase), record)
    print('SAFE_PROJECT_RECEIPT_WRITTEN')


def start(root):
    visual.guard(root); ident = identity(root); record = process_receipt(ident, 'start'); started = time.monotonic()
    value = dict(ident, status='STARTING', activationSucceeded=False, stagesStarted=[], cleanup=None)
    # A request/run attempt creates at most one owned container and activation.
    private.require(not file(root, 'session').exists(), 'SESSION_ALREADY_ATTEMPTED')
    private.write(file(root, 'session'), value)
    upstream = root / '.visual-safe-upstream'
    try:
        private.require(private.git(upstream, 'rev-parse', 'HEAD') == private.PIN, 'UPSTREAM_PIN_REJECTED')
        activate = (upstream / 'dist/platforms/ubuntu/activate.sh').read_text()
        returned = (upstream / 'dist/platforms/ubuntu/return_license.sh').read_text()
        private.require(private.NATIVE_COMMAND in re.sub(r'\s+', ' ', activate.replace('\\\n', '')), 'ACTIVATION_COMMAND_REJECTED')
        private.require(RETURN_COMMAND in re.sub(r'\s+', ' ', returned.replace('\\\n', '')), 'RETURN_COMMAND_REJECTED')
        code, _ = private.captured(['docker', 'pull', private.IMAGE], 600)
        private.require(code == 0, 'IMAGE_PULL_FAILED')
        env = dict(os.environ); env['UNITY_SERIAL'] = private.derive_serial(env.pop('UNITY_LICENSE', ''))
        private.require(all(env.get(k) and len(env[k]) <= 4096 for k in ('UNITY_EMAIL', 'UNITY_PASSWORD')), 'INPUT_REJECTED')
        command = ['docker', 'run', '--detach', '--rm', '--log-driver=none', '--name', name(ident), '--cpus=2', '--memory=12g',
                   '--workdir', '/github/workspace', '--env', 'UNITY_SERIAL', '--env', 'UNITY_EMAIL', '--env', 'UNITY_PASSWORD',
                   '--volume', str(root) + ':/github/workspace',
                   '--volume', str(upstream / 'dist/BlankProject') + ':/activation-blank-src:ro',
                   '--volume', str(upstream / 'dist/unity-config') + ':/usr/share/unity3d/config:ro',
                   private.IMAGE, '/bin/bash', '-c', 'mkdir -p /BlankProject && exec sleep infinity']
        code, _ = private.captured(command, 60, env=env)
        private.require(code == 0, 'CONTAINER_START_FAILED')
        activation = private.SHELL.replace('ACTIVATION_NATIVE_EXIT_CODE', 'SAFE_PROJECT_NATIVE_EXIT_CODE')
        native(ident, activation, 180, record)
        value['activationSucceeded'] = record['status'] == 'NATIVE_SUCCEEDED'
        value['status'] = 'READY' if value['activationSucceeded'] else 'BLOCKED'
    except TimeoutError: record['status'] = 'PROCESS_TIMEOUT'; value['status'] = 'BLOCKED'
    except (KeyboardInterrupt, InterruptedError): record['status'] = 'CANCELLED'; value['status'] = 'BLOCKED'
    except Exception: record['status'] = 'START_ADAPTER_FAILED'; value['status'] = 'BLOCKED'
    finally:
        if value['status'] != 'READY':
            value['cleanup'] = private.cleanup(name(ident)); record['cleanup'] = value['cleanup']
        private.write(file(root, 'session'), value); save(root, 'start', record, started)
    return 0 if value['status'] == 'READY' else 1


def test(root, phase):
    ident = identity(root); value = session(root, ident); record = process_receipt(ident, phase); started = time.monotonic()
    try:
        private.require(value['status'] == 'READY' and value['activationSucceeded'] and phase not in value['stagesStarted'], 'SESSION_NOT_READY_OR_PHASE_REPEATED')
        value['stagesStarted'].append(phase); private.write(file(root, 'session'), value)
        platform, folder, _, seconds = PHASES[phase]
        artifacts = root / private.TASK / 'artifacts' / folder; artifacts.mkdir(parents=True, exist_ok=True)
        # Fixed native destination only; never reuse a prior stage's XML.
        xml = artifacts / (platform + '-results.xml')
        if xml.exists(): xml.unlink()
        native(ident, shell(shlex.join(project_argv(phase, ident))), seconds, record)
        # Normal NUnit/test failure still permits the other exact suites to run.
        # Missing exits, native licensing failures or synchronous timeouts do not.
        healthy_exit = record['nativeExitMarkerCount'] == 1 and record['nativeExitCode'] == record['dockerExitCode']
        licensing_failure = record['observations']['invalidLicenseXml400'] or record['observations']['nativeActivationAborted']
        if not healthy_exit or licensing_failure:
            value['status'] = 'BLOCKED'
            value['cleanup'] = private.cleanup(name(ident)); record['cleanup'] = value['cleanup']
    except (KeyboardInterrupt, InterruptedError):
        record['status'] = 'CANCELLED'; value['status'] = 'BLOCKED'; value['cleanup'] = private.cleanup(name(ident)); record['cleanup'] = value['cleanup']
    except Exception:
        record['status'] = 'SESSION_OR_TEST_ADAPTER_FAILED'
        value['status'] = 'BLOCKED'; value['cleanup'] = private.cleanup(name(ident)); record['cleanup'] = value['cleanup']
    finally:
        private.write(file(root, 'session'), value); save(root, phase, record, started)
    return 0 if record['status'] == 'NATIVE_SUCCEEDED' else 1


def finish(root):
    ident = identity(root); record = process_receipt(ident, 'finish'); started = time.monotonic(); value = None
    try:
        value = session(root, ident)
        if value['status'] == 'READY' and value['activationSucceeded']:
            # Ownership derives from this attempt's unique container and recorded
            # successful activation. No other machine/session is selected.
            native(ident, shell(RETURN_COMMAND), 180, record)
        else:
            record['status'] = 'RETURN_NOT_RUN_SESSION_BLOCKED'
    except Exception: record['status'] = 'RETURN_NOT_RUN_OWNERSHIP_UNVERIFIED'
    finally:
        record['returnStatus'] = record['status']
        record['cleanup'] = private.cleanup(name(ident))
        if record['cleanup']['status'] != 'ABSENCE_VERIFIED': record['status'] = 'CLEANUP_NOT_VERIFIED'
        if value is not None:
            value['status'] = 'CLOSED'; value['cleanup'] = record['cleanup']; private.write(file(root, 'session'), value)
        save(root, 'finish', record, started)
    return 0 if record['status'] == 'NATIVE_SUCCEEDED' else 1


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=('start', *PHASES, 'finish')); args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    def stop(_signal, _frame): raise InterruptedError('CANCELLED')
    signal.signal(signal.SIGTERM, stop)
    try:
        if args.phase == 'start': return start(root)
        if args.phase == 'finish': return finish(root)
        return test(root, args.phase)
    except BaseException:
        print('SAFE_PROJECT_ADAPTER_REJECTED'); return 1


if __name__ == '__main__': raise SystemExit(main())
