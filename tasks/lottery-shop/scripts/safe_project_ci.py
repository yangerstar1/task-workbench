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
import play_split_ci as split

PHASES = {
    'capture': ('playmode', 'visual-candidate', 'Lottery.G3.VisualCandidate.Tests', 1800),
    'regression-edit': ('editmode', 'visual-regression-edit', 'Lottery.Probe.Tests;Lottery.G2.EditMode.Tests;Lottery.G3.EditMode.Tests', 480),
    'regression-play-core': ('playmode', split.FOLDERS['core'], 'Lottery.G2.PlayMode.Tests;Lottery.G3.PlayMode.Tests', 720),
    'regression-play-world': ('playmode', split.FOLDERS['world'], 'Lottery.G2.PlayMode.Tests;Lottery.G3.PlayMode.Tests', 480),
}
COUNTER_LIGHT_DIAGNOSTIC = False
COUNTER_LIGHT_DIAGNOSTIC_FAULT = ''
COVERAGE = 'generateAdditionalMetrics;generateHtmlReport;generateBadgeReport;dontClear'
RETURN_COMMAND = 'unity-editor -logFile /dev/stdout -quit -returnlicense -username "$UNITY_EMAIL" -password "$UNITY_PASSWORD" -projectPath "/BlankProject"'
MARKER = b'SAFE_PROJECT_NATIVE_EXIT_CODE='
COMPILER_PREFIX_LIMIT = 512
COMPILER_ERROR_LIMIT = 24
COMPILER_ASSET = re.compile(r'Assets/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.cs')
COMPILER_HEADER = re.compile(rb'(?:/github/workspace/tasks/lottery-shop/unity/)?(Assets/[A-Za-z0-9_./-]+\.cs)\(([1-9][0-9]{0,6}),([1-9][0-9]{0,6})\): error (CS[0-9]{4}):')


def compiler_assets(root, ident):
    # Only names in the independently reviewed commit, never paths from output
    # or untracked/generated files. Missing metadata disables this optional
    # diagnostic; it cannot change the existing native/test verdict or guards.
    try:
        commit = ident['reviewedCandidateCommit']
        private.require(re.fullmatch(r'[0-9a-f]{40}', commit), 'COMPILER_SOURCE_REJECTED')
        prefix = private.TASK + '/unity/'
        paths = private.git(root, 'ls-tree', '-r', '--name-only', commit, '--', prefix + 'Assets').splitlines()
        return frozenset(p[len(prefix):] for p in paths if p.startswith(prefix)
                         and len(p[len(prefix):]) <= 240
                         and COMPILER_ASSET.fullmatch(p[len(prefix):])
                         and all(x not in ('.', '..') for x in p[len(prefix):].split('/')))
    except (KeyboardInterrupt, InterruptedError):
        raise
    except Exception:
        return frozenset()


class ProcessScan(private.Scan):
    def __init__(self, compiler_files=()):
        super().__init__()
        self.compiler_files = frozenset(compiler_files)
        self.compiler_errors = []
        self.compiler_prefix = b''
        self.compiler_skip_line = False

    def compiler_feed(self, chunk):
        if not self.compiler_files or len(self.compiler_errors) >= COMPILER_ERROR_LIMIT:
            return
        # A line is eligible only from its actual start. Retain at most the
        # bounded header, discard every byte after a match/invalid long prefix.
        for index, part in enumerate(chunk.split(b'\n')):
            if index:
                self.compiler_prefix = b''; self.compiler_skip_line = False
            if self.compiler_skip_line or len(self.compiler_errors) >= COMPILER_ERROR_LIMIT:
                continue
            self.compiler_prefix += part[:COMPILER_PREFIX_LIMIT - len(self.compiler_prefix)]
            match = COMPILER_HEADER.match(self.compiler_prefix)
            if match:
                path = match.group(1).decode('ascii')
                if path in self.compiler_files:
                    self.compiler_errors.append(dict(code=match.group(4).decode('ascii'), path=path,
                                                     line=int(match.group(2)), column=int(match.group(3))))
                self.compiler_skip_line = True; self.compiler_prefix = b''
            elif len(self.compiler_prefix) == COMPILER_PREFIX_LIMIT:
                self.compiler_skip_line = True; self.compiler_prefix = b''

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
        self.compiler_feed(chunk)


def identity(root):
    value = visual.identity(root)
    private.require(value['runId'] == os.environ.get('GITHUB_RUN_ID') and value['runAttempt'] == os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'IDENTITY_REJECTED')
    return value


def name(ident):
    return 'lottery-visual-safe-' + ident['runId'] + '-' + ident['runAttempt']


# Fixed metadata only: never inspect container Env, command lines or license files.
OWNER_LABELS = ('lottery.visual.source', 'lottery.visual.reviewed', 'lottery.visual.run', 'lottery.visual.attempt')
OWNER_FIELDS = ('sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt')
OWNER_FORMAT = '{{.Name}}|{{.Config.Image}}|{{.HostConfig.PidMode}}|{{.HostConfig.Privileged}}|{{.HostConfig.AutoRemove}}|{{.State.Running}}|' + '|'.join('{{index .Config.Labels "' + key + '"}}' for key in OWNER_LABELS)
QUIESCENT_MARKER = b'SAFE_PROJECT_QUIESCENT\n'
# The entire container belongs exclusively to this attempt. Keep its original
# PID 1 and this stopper alive; stop all other processes, including escaped
# project process groups. /proc is read for PID/state only, never argv or Env.
# Isolated PID namespace and exact original labels are checked before execution.
QUIESCE_COMMAND = r"""set +x
set +v
IFS= read -r init_name < /proc/1/comm || exit 125
[[ "$init_name" == sleep ]] || exit 125
other_live() {
  local path pid line tail state count=0
  for path in /proc/[0-9]*/stat; do
    ((count+=1)); ((count <= 4096)) || return 2
    pid=${path#/proc/}; pid=${pid%/stat}
    [[ "$pid" == 1 || "$pid" == "$$" ]] && continue
    if ! IFS= read -r line 2>/dev/null < "$path"; then
      [[ -d "${path%/stat}" ]] && return 2
      continue
    fi
    tail=${line##*) }; state=${tail%% *}
    [[ "$tail" != "$line" && "$state" =~ ^[RSDZTWtXxKPI]$ ]] || return 2
    [[ "$state" == Z || "$state" == X || "$state" == x ]] && continue
    if [[ "$1" == check ]]; then return 0; fi
    kill -s "$1" "$pid" 2>/dev/null || true
  done
  return 1
}
for sig in TERM KILL; do
  other_live "$sig"; status=$?; ((status != 2)) || exit 125
  for ((attempt=0; attempt<20; attempt++)); do
    other_live check; status=$?
    ((status != 2)) || exit 125
    if ((status == 1)); then
      printf 'SAFE_PROJECT_QUIESCENT\n'; exit 0
    fi
    sleep 0.1
  done
done
exit 125
"""


class ExactBytesScan:
    """Compare a fixed response incrementally; retain no received output."""
    def __init__(self, expected):
        self.expected = expected; self.offset = 0; self.carry = b''

    def feed(self, chunk):
        private.require(self.expected[self.offset:self.offset + len(chunk)] == chunk, 'OWNED_STOP_NOT_PROVEN')
        self.offset += len(chunk)

    @property
    def complete(self):
        return self.offset == len(self.expected)


def quiesce_owned(ident):
    try:
        private.require(re.fullmatch(r'[0-9a-f]{40}', ident['sourceCommit']) and
                        re.fullmatch(r'[0-9a-f]{40}', ident['reviewedCandidateCommit']) and
                        re.fullmatch(r'[1-9][0-9]{0,19}', ident['runId']) and ident['runAttempt'] == '1', 'STOP_IDENTITY_REJECTED')
        expected = ('/' + name(ident) + '|' + private.IMAGE + '||false|true|true|' +
                    '|'.join(ident[key] for key in OWNER_FIELDS) + '\n').encode('ascii')
        scan = ExactBytesScan(expected)
        code, scan = private.captured(['docker', 'inspect', '--format', OWNER_FORMAT, name(ident)], 10, scan=scan)
        if code != 0 or not scan.complete: return False
        scan = ExactBytesScan(QUIESCENT_MARKER)
        code, scan = private.captured(['docker', 'exec', name(ident), '/bin/bash', '-c', QUIESCE_COMMAND], 15, scan=scan)
        return code == 0 and scan.complete
    except BaseException:
        return False


def block_session(root, ident, value, record):
    value['status'] = 'BLOCKED'; retain_for_finish = False
    # Persist the block before stopping: an interrupted stopper cannot leave
    # a READY receipt. No other test or activation may use the retained container.
    try:
        private.write(file(root, 'session'), value)
        retain_for_finish = value['activationSucceeded'] is True and value['cleanup'] is None and quiesce_owned(ident)
    finally:
        if not retain_for_finish:
            value['cleanup'] = private.cleanup(name(ident))
        record['cleanup'] = value['cleanup']


def file(root, phase):
    private.require(phase in ('start', 'finish', 'session') or phase in PHASES, 'PHASE_REJECTED')
    return visual.outdir(root) / ('safe-' + phase + '.json')


def session(root, ident):
    value = private.read(file(root, 'session'))
    private.require(all(value[k] == ident[k] for k in ('sourceCommit', 'runId', 'runAttempt')), 'SESSION_IDENTITY_REJECTED')
    return value


def process_receipt(ident, phase):
    record = dict(ident, schemaVersion=1, phase=phase, status='NOT_STARTED', dockerExitCode=None, nativeExitCode=None,
                nativeExitMarkerCount=0, observations={key: 0 for key in private.TOKENS}, compilerErrors=[], cleanup=None,
                image=private.IMAGE, mechanismSourcePin=private.PIN, nativeOutput='BOUNDED_MEMORY_ONLY_NO_RAW_LOG',
                testVerdict='SEPARATE_EXACT_NUNIT_VALIDATOR_REQUIRED')
    if phase == 'capture':
        record.update(counterLightDiagnostic=COUNTER_LIGHT_DIAGNOSTIC, counterLightDiagnosticFault=COUNTER_LIGHT_DIAGNOSTIC_FAULT)
    if phase in split.PHASES.values():
        shard = phase.removeprefix('regression-play-')
        record.update(shard=shard, plannedCaseCount=len(split.names(shard)), testSelectionSha256=split.selection_hash(shard),
                      processBudgetSeconds=PHASES[phase][3], nativeStartedAtNs=None)
    return record


def shell(command):
    return 'set +x\nset +v\n' + command + '\ncode=$?\nprintf "\\nSAFE_PROJECT_NATIVE_EXIT_CODE=%d\\n" "$code"\nexit "$code"\n'


def native(ident, command, seconds, record, compiler_files=()):
    scan = ProcessScan(compiler_files)
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
        record['compilerErrors'] = scan.compiler_errors
        scan.carry = b''; scan.compiler_prefix = b''


def project_argv(phase, ident):
    platform, folder, assemblies, _ = PHASES[phase]
    argv = ['unity-editor', '-batchmode', '-logFile', '/dev/stdout', '-projectPath', '/github/workspace/' + private.TASK + '/unity',
            '-coverageResultsPath', '/github/workspace/CodeCoverage', '-runTests', '-testPlatform', platform,
            '-testResults', '/github/workspace/' + private.TASK + '/artifacts/' + folder + '/' + platform + '-results.xml',
            '-enableCodeCoverage', '-debugCodeOptimization', '-coverageOptions', COVERAGE, '-assemblyNames', assemblies]
    if phase != 'regression-edit': argv += ['-force-glcore', '-screen-width', '1280', '-screen-height', '720']
    argv += ['-job-worker-count', '2', '-probeCommit', ident['sourceCommit'], '-probeRunId', ident['runId']]
    if phase in ('capture', 'performance-probe') or phase in split.PHASES.values(): argv += ['-probeRunAttempt', ident['runAttempt']]
    if phase in split.PHASES.values():
        shard = phase.removeprefix('regression-play-')
        argv += ['-g3RegressionProgress', '1', '-probeReviewedCommit', ident['reviewedCandidateCommit'],
                 '-g3RegressionShard', shard, '-testFilter', split.selection(shard)]
    if phase == 'performance-probe': argv += ['-g3PerformanceProbe', '1', '-probeReviewedCommit', ident['reviewedCandidateCommit']]
    if phase == 'capture' and COUNTER_LIGHT_DIAGNOSTIC:
        argv += ['-counterLightDiagnostic', '1']
        if COUNTER_LIGHT_DIAGNOSTIC_FAULT:
            argv += ['-counterLightDiagnosticFault', COUNTER_LIGHT_DIAGNOSTIC_FAULT]
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
        command = ['docker', 'run', '--detach', '--rm', '--log-driver=none', '--name', name(ident), '--cpus=4', '--memory=12g',
                   *[item for key, field in zip(OWNER_LABELS, OWNER_FIELDS) for item in ('--label', key + '=' + ident[field])],
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
        if phase in split.PHASES.values():
            split.contract(root)
            # Only fixed outputs for this shard; never erase the sibling's proof.
            outputs = [artifacts / 'test-progress.json', visual.outdir(root) / (phase + '-progress.json')]
            if phase == split.PHASES['world']:
                outputs += [artifacts / 'world-progress.jsonl', visual.outdir(root) / 'world-progress.json']
            for progress in outputs:
                if progress.exists(): progress.unlink()
        if phase == 'performance-probe':
            for receipt in (artifacts / 'performance-receipt.json', visual.outdir(root) / 'performance-receipt.json'):
                if receipt.exists(): receipt.unlink()
        compiler_files = compiler_assets(root, ident)
        record['nativeStartedAtNs'] = time.time_ns()
        record['processBudgetSeconds'] = seconds
        native(ident, shell(shlex.join(project_argv(phase, ident))), seconds, record, compiler_files)
        # Normal NUnit/test failure still permits the other exact suites to run.
        # Missing exits, native licensing failures or synchronous timeouts do not.
        healthy_exit = record['nativeExitMarkerCount'] == 1 and record['nativeExitCode'] == record['dockerExitCode']
        licensing_failure = record['observations']['invalidLicenseXml400'] or record['observations']['nativeActivationAborted']
        if not healthy_exit or licensing_failure:
            block_session(root, ident, value, record)
    except (KeyboardInterrupt, InterruptedError):
        record['status'] = 'CANCELLED'; block_session(root, ident, value, record)
    except Exception:
        record['status'] = 'SESSION_OR_TEST_ADAPTER_FAILED'
        block_session(root, ident, value, record)
    finally:
        private.write(file(root, 'session'), value); save(root, phase, record, started)
    return 0 if record['status'] == 'NATIVE_SUCCEEDED' else 1


def finish(root):
    ident = identity(root); record = process_receipt(ident, 'finish'); started = time.monotonic(); value = None
    try:
        value = session(root, ident)
        returnable = value['activationSucceeded'] is True and (value['status'] == 'READY' or
                     (value['status'] == 'BLOCKED' and value['cleanup'] is None and quiesce_owned(ident)))
        if returnable:
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


def configure_performance():
    # Explicit independent profile only. No caller-supplied module/path/command.
    global visual, PHASES
    import performance_probe_ci
    visual = performance_probe_ci
    PHASES = {'performance-probe': ('playmode', 'performance-probe', 'Lottery.G3.PerformanceDiagnostic.Tests', 600)}


def main():
    global COUNTER_LIGHT_DIAGNOSTIC, COUNTER_LIGHT_DIAGNOSTIC_FAULT
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('start', *PHASES, 'performance-probe', 'finish'))
    parser.add_argument('--performance-only', action='store_true')
    parser.add_argument('--counter-light-diagnostic', action='store_true')
    parser.add_argument('--counter-light-diagnostic-fault', default='')
    args = parser.parse_args()
    if args.counter_light_diagnostic or args.counter_light_diagnostic_fault:
        if args.phase != 'capture' or args.performance_only or not args.counter_light_diagnostic:
            print('SAFE_PROJECT_DIAGNOSTIC_PROFILE_REJECTED'); return 1
        allowed_cases = ('pendant-zero', 'boardwash-zero', 'counter-pair-zero', 'daylight-zero', 'reading-zero',
                         'shelf-zero', 'all-direct-zero', 'probe-intensity-zero', 'global-reflection-zero',
                         'reflection-controls-zero', 'ambient-sh-zero', 'counter-and-reflection-controls-zero',
                         'oak-specular-highlights-off', 'oak-normal-flat', 'oak-roughness-one', 'oak-texture-only', 'oak-target-mask')
        allowed_faults = {case + ':' + point for case in allowed_cases for point in ('after-mutation', 'before-capture', 'after-png', 'before-receipt')}
        allowed_faults |= {'negative:camera-target', 'negative:material-slot', 'negative:probe-transform', 'negative:urp-camera'}
        if args.counter_light_diagnostic_fault and args.counter_light_diagnostic_fault not in allowed_faults:
            print('SAFE_PROJECT_DIAGNOSTIC_FAULT_REJECTED'); return 1
        COUNTER_LIGHT_DIAGNOSTIC = True
        COUNTER_LIGHT_DIAGNOSTIC_FAULT = args.counter_light_diagnostic_fault
    if args.performance_only:
        if args.phase not in ('start', 'performance-probe', 'finish'):
            print('SAFE_PROJECT_PROFILE_REJECTED'); return 1
        configure_performance()
    elif args.phase == 'performance-probe':
        print('SAFE_PROJECT_PROFILE_REJECTED'); return 1
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
