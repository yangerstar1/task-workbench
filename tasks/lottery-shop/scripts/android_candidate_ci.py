#!/usr/bin/env python3
"""Opt-in cold diagnostic APK. Fixed commands; no native log/settings export."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import stat
import struct
import time
import zipfile
import activation_probe as private
import safe_project_ci as safe
import visual_candidate_ci as visual
import g3_ci as g3
import stage_a_inventory_ci as inventory

IMAGE = 'unityci/editor@sha256:74948775af2bb36829b546bf210dfab28fd1745d50a31acbd72d1dd0774886cb'
SCOPE = 'DIAGNOSTIC_ANDROID_CANDIDATE_NOT_G3_PASS'
PACKAGE = 'com.buyuqi.lotteryprobe.candidate'
BUILD = private.TASK + '/build/AndroidCandidate/Android'
APK = 'LotteryCandidate.apk'
OUT = private.TASK + '/artifacts/android-candidate-delivery'
require = private.require


def regular(path, root, maximum):
    g3.check_ancestors(root, path)
    info = g3.regular_unaliased(path, root)
    require(info.st_size <= maximum, 'INPUT_LIMIT')
    return path.read_bytes()


def load(path, root, maximum=65536):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'DUPLICATE_KEY'); value[key] = item
        return value
    return json.loads(regular(path, root, maximum), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE')))


def identity(root):
    ident = visual.identity(root)
    require(ident['runId'] == os.environ.get('GITHUB_RUN_ID') and ident['runAttempt'] == os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'FIRST_ATTEMPT_REQUIRED')
    request = visual.read_diagnostic_request(root / visual.REQUEST)
    visual.request_profile(request)
    require(request['schemaVersion'] == 3 and request['sourceCommit'] == ident['reviewedCandidateCommit'] and request['requestId'] == ident['requestId'], 'APK_NOT_AUTHORIZED')
    return {key: ident[key] for key in ('sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt', 'requestId')}


def name(ident):
    require(re.fullmatch('[1-9][0-9]{0,19}', ident['runId']) and ident['runAttempt'] == '1', 'CONTAINER_IDENTITY')
    return 'lottery-android-candidate-' + ident['runId'] + '-1'


class SignatureScan(safe.ProcessScan):
    def __init__(self):
        super().__init__(); self.line = b''; self.skip = False; self.certificates = []
    def feed(self, chunk):
        super().feed(chunk)
        for index, part in enumerate(chunk.split(b'\n')):
            if index:
                match = re.fullmatch(rb'Signer #1 certificate SHA-256 digest: ([0-9a-f]{64})\r?', self.line)
                if not self.skip and b'certificate SHA-256 digest:' in self.line:
                    require(match is not None, 'CERTIFICATE_FORMAT_OR_MULTIPLE_SIGNERS')
                    require(len(self.certificates) < 2, 'CERTIFICATE_COUNT')
                    self.certificates.append(match[1].decode('ascii'))
                self.line = b''; self.skip = False
            if not self.skip:
                if len(self.line) + len(part) > 256: self.skip = True; self.line = b''
                else: self.line += part


def process(ident, command, seconds, scan=None):
    scan = scan or safe.ProcessScan()
    result = dict(status='NOT_STARTED', dockerExitCode=None, nativeExitCode=None, nativeExitMarkerCount=0,
                  observations={key: 0 for key in private.TOKENS})
    try:
        code, scan = private.captured(['docker', 'exec', name(ident), '/bin/bash', '-c', command], seconds, scan=scan)
        result['dockerExitCode'] = code
        good = scan.exit_markers == 1 and scan.native_exit == code == 0
        good = good and not scan.counts['invalidLicenseXml400'] and not scan.counts['nativeActivationAborted']
        result['status'] = 'NATIVE_SUCCEEDED' if good else 'NATIVE_FAILED'
    except TimeoutError: result['status'] = 'PROCESS_TIMEOUT'
    except (KeyboardInterrupt, InterruptedError): result['status'] = 'CANCELLED'
    except Exception: result['status'] = 'ADAPTER_REJECTED'
    finally:
        result.update(nativeExitCode=scan.native_exit, nativeExitMarkerCount=scan.exit_markers, observations=scan.counts)
        scan.carry = b''; scan.compiler_prefix = b''
        if isinstance(scan, SignatureScan): scan.line = b''
    return result


def build_argv(ident):
    return ['unity-editor', '-batchmode', '-quit', '-logFile', '/dev/stdout', '-projectPath',
            '/github/workspace/' + private.TASK + '/unity', '-buildTarget', 'Android', '-executeMethod',
            'Lottery.G3.Editor.G3Build.BuildAndroidDiagnostic', '-force-glcore', '-job-worker-count', '2',
            '-probeCommit', ident['sourceCommit'], '-probeReviewedCommit', ident['reviewedCandidateCommit'],
            '-probeRunId', ident['runId'], '-probeRunAttempt', ident['runAttempt']]


def inspect_apk(root, ident):
    folder = root / BUILD; apk = folder / APK
    g3.check_ancestors(root, apk); info = g3.regular_unaliased(apk, root)
    require(1024**2 <= info.st_size <= 512*1024**2, 'APK_SIZE')
    receipt = load(folder / 'diagnostic-build-receipt.json', root)
    require(set(receipt) == {'schemaVersion', 'sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt', 'build'} and type(receipt['schemaVersion']) is int and receipt['schemaVersion'] == 1, 'BUILD_RECEIPT_SCHEMA')
    require(all(receipt[k] == ident[k] for k in ('sourceCommit', 'reviewedCandidateCommit', 'runId', 'runAttempt')), 'BUILD_IDENTITY')
    expected = dict(scope=SCOPE, sourceCommit=ident['sourceCommit'], runId=ident['runId'], unityVersion='6000.3.19f1',
        buildResult='Succeeded', buildTarget='Android', scriptingBackend='IL2CPP', architecture='ARM64', minSdk=26,
        targetSdk=35, graphicsApis='OpenGLES3', rulesSha256=g3.RULES_SHA, standardsDigest=g3.STANDARDS_DIGEST,
        runtimeScene=g3.SCENE, fakeAd='DEVELOPMENT_FAKE_ONLY', versionCode=39, versionName='0.0.39',
        applicationIdentifier=PACKAGE, normalRuntimeFixture='NONE', coldBuild=True, deviceQa='NOT_RUN',
        renderedFrameQa='NOT_RUN', gameplayQa='NOT_RUN', signing='development-debug', finalQuality='NOT_PASSED')
    data = receipt['build']
    require(type(data) is dict and set(data) == set(expected) | {'apkBytes', 'apkSha256', 'builtAtUtc', 'editorRevision'}, 'BUILD_FIELDS')
    require(all(type(data[k]) is type(v) and data[k] == v for k,v in expected.items()), 'BUILD_DECLARATIONS')
    require(type(data['editorRevision']) is str and re.fullmatch(r'6000\.3\.19f1 \(7689f4515d75\)', data['editorRevision']), 'EDITOR_REVISION')
    digest = visual.sha(apk)
    require(type(data['apkBytes']) is int and data['apkBytes'] == info.st_size and data['apkSha256'] == digest, 'APK_HASH')
    with zipfile.ZipFile(apk) as archive:
        entries = archive.infolist(); names = [x.filename for x in entries]
        require(len(entries) < 100000 and len(set(names)) == len(names) and sum(x.file_size for x in entries) <= 1024**3, 'APK_ZIP_BOUNDS')
        require(all(not x.flag_bits & 1 and not stat.S_ISLNK(x.external_attr >> 16) and not x.filename.startswith(('/', '\\')) and '\\' not in x.filename and '..' not in x.filename.split('/') for x in entries), 'APK_ZIP_PATH')
        require({'AndroidManifest.xml', 'classes.dex', 'lib/arm64-v8a/libil2cpp.so', 'lib/arm64-v8a/libunity.so'} <= set(names), 'APK_REQUIRED_FILES')
        for item in entries:
            if item.filename.startswith('lib/') and not item.is_dir():
                require(item.filename.startswith('lib/arm64-v8a/') and item.file_size >= 20, 'APK_ABI')
                with archive.open(item) as source: head = source.read(20)
                require(head[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', head, 18)[0] == 183, 'APK_ELF')
        item = archive.getinfo('AndroidManifest.xml'); require(item.file_size <= 2*1024**2, 'AXML_SIZE')
        manifest = g3.parse_binary_manifest(archive.read(item))
        require(manifest == dict(package=PACKAGE, versionCode=39, versionName='0.0.39'), 'APK_COMPILED_IDENTITY')
    return dict(apkSha256=digest, apkBytes=info.st_size, binaryManifest=manifest,
                architecture='ARM64', minSdkDeclared=26, targetSdkDeclared=35, graphicsApisDeclared='OpenGLES3')


def settings_baseline(root):
    directory = root / private.TASK / 'unity/ProjectSettings'
    require(not directory.is_symlink() and directory.is_dir(), 'SETTINGS_DIRECTORY')
    paths = visual.git(root, 'ls-files', '--', private.TASK + '/unity/ProjectSettings').splitlines()
    require(1 <= len(paths) <= 128, 'SETTINGS_COUNT')
    result = {}
    for path in paths:
        target = root / path; relative = target.relative_to(directory).as_posix()
        require(re.fullmatch('[A-Za-z0-9_.-]+', relative), 'SETTINGS_PATH')
        result[relative] = regular(target, root, 2*1024**2)
    # Original credential/layout checks only; never invoke old formal guards.
    g3.g2.validate_credential_layout(root)
    require(not g3.g2.settings_findings(root), 'SETTINGS_BEFORE_SENSITIVE')
    require(not g3.g2.ps4_scalar_span(result['ProjectSettings.asset'])[1], 'SETTINGS_BEFORE_PS4')
    inventory.settings_gate(root, result, g3.g2)
    return result


def run(root):
    visual.guard(root); ident = identity(root); started = time.monotonic()
    destination = root / OUT
    require(not destination.exists() and not destination.is_symlink(), 'FRESH_DELIVERY_REQUIRED')
    require(not destination.parent.is_symlink(), 'DELIVERY_PARENT_LINK')
    g3.check_ancestors(root, destination.parent)
    destination.parent.mkdir(exist_ok=True)
    result = dict(schemaVersion=1, scope=SCOPE, **ident, status='NOT_STARTED', image=IMAGE,
        mechanismSourcePin=private.PIN, requestSha256=visual.sha(root/visual.REQUEST),
        sourceApproval='FIXED_ACTOR_ATTESTED_INDEPENDENT_ANDROID_REVIEW_NOT_CRYPTOGRAPHIC_SIGNATURE', deviceQa='NOT_RUN', g3Gate='NOT_EVALUATED', finalQuality='NOT_PASSED',
        packageData='ISOLATED_FROM_EXISTING_FORMAL_PACKAGE', signing='EPHEMERAL_DEBUG_CERTIFICATE_NO_UPGRADE_PROMISE',
        nativeOutput='BOUNDED_MEMORY_ONLY_NO_RAW_LOG', rawSettingsExported=False,
        activation=None, build=None, signature=None, licenseReturn=None, cleanup=None, apk=None, settings=None)
    activated = False; healthy = False; baseline = None; native_ready = False
    try:
        for path in (root/private.TASK/'unity/Library', root/private.TASK/'unity/.utmp', root/private.TASK/'build'):
            require(not path.exists() and not path.is_symlink(), 'COLD_BUILD_REQUIRED')
        baseline = settings_baseline(root)
        upstream = root / '.visual-safe-upstream'
        require(private.git(upstream, 'rev-parse', 'HEAD') == private.PIN, 'UPSTREAM_PIN')
        for file, command in [('activate.sh', private.NATIVE_COMMAND), ('return_license.sh', safe.RETURN_COMMAND)]:
            text = regular(upstream/'dist/platforms/ubuntu'/file, upstream, 65536).decode('utf-8')
            require(command in re.sub(r'\s+', ' ', text.replace('\\\n', '')), 'UPSTREAM_COMMAND')
        code, _ = private.captured(['docker', 'pull', '--platform=linux/amd64', IMAGE], 600)
        require(code == 0, 'IMAGE_PULL')
        env = dict(os.environ); env['UNITY_SERIAL'] = private.derive_serial(env.pop('UNITY_LICENSE', ''))
        require(all(env.get(k) and len(env[k]) <= 4096 for k in ('UNITY_EMAIL', 'UNITY_PASSWORD')), 'CREDENTIAL_INPUT')
        command = ['docker', 'run', '--platform=linux/amd64', '--detach', '--rm', '--log-driver=none', '--name', name(ident),
            '--cpus=2', '--memory=12g', '--workdir', '/github/workspace', '--env', 'UNITY_SERIAL', '--env', 'UNITY_EMAIL', '--env', 'UNITY_PASSWORD',
            '--volume', str(root)+':/github/workspace', '--volume', str(upstream/'dist/BlankProject')+':/activation-blank-src:ro',
            '--volume', str(upstream/'dist/unity-config')+':/usr/share/unity3d/config:ro', IMAGE,
            '/bin/bash', '-c', 'mkdir -p /BlankProject && exec sleep infinity']
        code, _ = private.captured(command, 60, env=env); env.clear(); require(code == 0, 'CONTAINER_START')
        result['activation'] = process(ident, private.SHELL.replace('ACTIVATION_NATIVE_EXIT_CODE', 'SAFE_PROJECT_NATIVE_EXIT_CODE'), 180)
        activated = result['activation']['status'] == 'NATIVE_SUCCEEDED'; require(activated, 'ACTIVATION_FAILED')
        result['build'] = process(ident, safe.shell(shlex.join(build_argv(ident))), 2400)
        healthy = result['build']['nativeExitMarkerCount'] == 1 and result['build']['nativeExitCode'] == result['build']['dockerExitCode']
        healthy = healthy and not result['build']['observations']['invalidLicenseXml400'] and not result['build']['observations']['nativeActivationAborted']
        require(result['build']['status'] == 'NATIVE_SUCCEEDED', 'BUILD_FAILED')
        result['settings'] = inventory.settings_gate(root, baseline, g3.g2)
        result['apk'] = inspect_apk(root, ident)
        scan = SignatureScan()
        # Tool selection is confined to fixed SDK build-tools under the pinned image.
        command = 'set -o pipefail\nmapfile -t tools < <(find /opt/unity/Editor/Data/PlaybackEngines/AndroidPlayer/SDK/build-tools -maxdepth 2 -type f -name apksigner | sort -V)\n' + \
            'test "${#tools[@]}" -ge 1 && test "${#tools[@]}" -le 16 && "${tools[-1]}" verify --verbose --print-certs /github/workspace/' + BUILD + '/' + APK
        result['signature'] = process(ident, safe.shell(command), 120, scan)
        require(result['signature']['status'] == 'NATIVE_SUCCEEDED' and len(scan.certificates) == 1, 'SIGNATURE_FAILED')
        result['signature']['certificateSha256'] = scan.certificates[0]
        native_ready = True; result['status'] = 'VERIFIED_PENDING_CLEANUP'
    except TimeoutError: result['status'] = 'PROCESS_TIMEOUT'
    except (KeyboardInterrupt, InterruptedError): result['status'] = 'CANCELLED'
    except Exception: result['status'] = 'BUILD_OR_SAFETY_REJECTED'
    finally:
        if activated and (result['build'] is None or healthy):
            result['licenseReturn'] = process(ident, safe.shell(safe.RETURN_COMMAND), 180)
        result['cleanup'] = private.cleanup(name(ident))
        baseline = None
        complete = native_ready and result['licenseReturn'] and result['licenseReturn']['status'] == 'NATIVE_SUCCEEDED' and result['cleanup']['status'] == 'ABSENCE_VERIFIED'
        # Fresh staging only after container cleanup; never upload a native-created file.
        require(not destination.exists() and not destination.is_symlink(), 'NATIVE_CREATED_DELIVERY_REJECTED')
        g3.check_ancestors(root, destination.parent / 'checked-child')
        destination.mkdir()
        if complete:
            # Container is gone before copy; exact bytes are checked again.
            source = root/BUILD/APK
            try:
                g3.check_ancestors(root, source); g3.regular_unaliased(source, root)
                require(visual.sha(source) == result['apk']['apkSha256'], 'APK_CHANGED')
                target = destination/APK; require(not target.exists(), 'DELIVERY_EXISTS')
                shutil.copyfile(source, target)
                require(visual.sha(target) == result['apk']['apkSha256'], 'COPY_CHANGED')
                result['status'] = 'INSTALLABLE_DIAGNOSTIC_APK_NOT_DEVICE_TESTED'
            except Exception:
                (destination/APK).unlink(missing_ok=True); result['status'] = 'DELIVERY_REJECTED'
        elif native_ready: result['status'] = 'CLEANUP_OR_LICENSE_RETURN_NOT_VERIFIED'
        result['elapsedMs'] = int((time.monotonic()-started)*1000)
        with (destination/'diagnostic-apk-receipt.json').open('x', encoding='utf-8') as output:
            json.dump(result, output, indent=2, sort_keys=True, allow_nan=False); output.write('\n')
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write('safe_receipt=true\n')
    print('ANDROID_CANDIDATE_RECEIPT_WRITTEN')
    return 0 if result['status'] == 'INSTALLABLE_DIAGNOSTIC_APK_NOT_DEVICE_TESTED' else 1


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('command', choices=('run', 'cleanup'))
    args = parser.parse_args(); root = Path(__file__).resolve().parents[3]
    def stop(_signal, _frame): raise InterruptedError('CANCELLED')
    signal.signal(signal.SIGTERM, stop)
    try:
        if args.command == 'run': return run(root)
        # Recovery only owns this request's exact container. No other sessions.
        result = private.cleanup(name(identity(root)))
        print('ANDROID_CANDIDATE_CLEANUP_' + result['status'])
        return 0 if result['status'] == 'ABSENCE_VERIFIED' else 1
    except BaseException:
        print('ANDROID_CANDIDATE_ADAPTER_REJECTED'); return 1


if __name__ == '__main__': raise SystemExit(main())
