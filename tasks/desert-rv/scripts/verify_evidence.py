#!/usr/bin/env python3
"""Bounded, allowlisted CI evidence for the saved TraversalHarness test package."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

TASK = Path(__file__).resolve().parents[1]
ROOT = TASK.parents[1]
PROJECT = TASK / 'unity'
VERSION = '6000.3.19f1'
REPOSITORY = 'yangerstar1/task-workbench'
OWNER = 'yangerstar1'
SCOPE = 'Saved TraversalHarness Android test package; not the complete game; device execution NOT_RUN'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def safe(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Missing or linked evidence file')
    require(not any(p.is_symlink() for p in path.parents), 'Linked evidence ancestor')
    return path


def sha(path):
    h = hashlib.sha256()
    with safe(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    path = safe(path)
    require(path.stat().st_size <= 4 * 1024**2, 'JSON evidence exceeds size limit')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON field')
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def identity():
    commit = os.environ['GITHUB_SHA']
    require(re.fullmatch('[a-f0-9]{40}', commit), 'Invalid commit identity')
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require(actual == commit, 'Checkout commit differs from run')
    run, attempt = os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT']
    require(re.fullmatch('[1-9][0-9]*', run) and re.fullmatch('[1-9][0-9]*', attempt), 'Invalid run identity')
    return dict(repository=REPOSITORY, commit=commit, runId=run, runAttempt=attempt,
                editorVersion=VERSION, exportManifestSha256=sha(TASK / 'PUBLIC-EXPORT.json'), scope=SCOPE)


def guard():
    require(os.environ.get('GITHUB_ACTIONS') == 'true', 'GitHub Actions required')
    require(os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted' and os.environ.get('RUNNER_OS') == 'Linux', 'Standard hosted Linux required')
    require(os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'Manual dispatch required')
    require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY and os.environ.get('GITHUB_REF') == 'refs/heads/main', 'Trusted repository/main required')
    require(os.environ.get('GITHUB_ACTOR') == OWNER and os.environ.get('GITHUB_TRIGGERING_ACTOR') == OWNER, 'Owner dispatch and owner rerun required')
    repo = read_json(os.environ['GITHUB_EVENT_PATH'])['repository']
    require(repo.get('full_name') == REPOSITORY and repo.get('private') is False and repo.get('fork') is False and repo.get('default_branch') == 'main', 'Public original repository required')
    identity()
    manifest = read_json(TASK / 'PUBLIC-EXPORT.json')
    entries = manifest.get('files', [])
    require(isinstance(entries, list) and len(entries) > 0, 'Nonempty export inventory required')
    seen = set()
    for entry in entries:
        name = entry.get('path', '')
        require(isinstance(name, str) and name.startswith('tasks/desert-rv/') and '..' not in Path(name).parts and name not in seen, 'Invalid/duplicate export path')
        seen.add(name)
        path = ROOT / name
        require(sha(path) == entry.get('sha256') and safe(path).stat().st_size == entry.get('size'), 'Export bytes differ from manifest')
    version = safe(PROJECT / 'ProjectSettings/ProjectVersion.txt').read_text()
    require(('m_EditorVersion: ' + VERSION) in version.splitlines(), 'Unity version must match pinned editor')
    # Never accept a checked-in binary as this run\'s output.
    for directory in [TASK / 'build', TASK / 'evidence', TASK / 'artifacts', PROJECT / 'build']:
        require(not directory.exists(), 'Output directory already exists before native execution')
    print('Trusted source/run and clean native output paths verified.')


def expected_cases():
    names = read_json(TASK / 'scripts/expected_test_cases.json')
    require(isinstance(names, list) and len(names) >= 1 and len(names) == len(set(names)), 'Invalid fixed test inventory')
    return set(names)


def inspect_tests(directory):
    reports = []
    paths = list(Path(directory).rglob('*.xml'))
    require(len(paths) <= 20, 'Too many XML files')
    for path in paths:
        require(safe(path).stat().st_size <= 10 * 1024**2, 'Oversized test report')
        root = ET.parse(path).getroot()
        if root.tag == 'test-run':
            reports.append((path, root))
    require(len(reports) == 1, 'Exactly one native NUnit test-run report required')
    path, root = reports[0]
    cases = list(root.iter('test-case'))
    names = [c.get('fullname') for c in cases]
    expected = expected_cases()
    require(len(names) == len(expected) and set(names) == expected, 'Native test inventory mismatch, empty, omitted or duplicated cases')
    # Reconstruct only reviewed names and enum statuses. Never publish stdout,
    # stack traces, environment fields or native result attachments.
    allowed = {'Passed', 'Failed', 'Skipped', 'Inconclusive'}
    summary = [dict(name=c.get('fullname'), result=c.get('result') if c.get('result') in allowed else 'Unknown') for c in cases]
    evidence = TASK / 'evidence/tests'
    evidence.mkdir(parents=True, exist_ok=True)
    result = dict(identity(), schema='desert-rv-tests/v1', originalXmlSha256=sha(path),
                  cases=summary, passed=sum(c['result'] == 'Passed' for c in summary),
                  verdict='COLLECTED_NOT_YET_VERIFIED')
    (evidence / 'test-results.json').write_text(json.dumps(result, indent=2) + '\n')
    require(root.get('result') == 'Passed' and all(c['result'] == 'Passed' for c in summary), 'Native run failed or skipped tests')
    require(int(root.get('total', '-1')) == len(expected) and int(root.get('passed', '-1')) == len(expected) and int(root.get('failed', '-1')) == 0, 'Native NUnit counts mismatch')
    result['verdict'] = 'PASSED'
    (evidence / 'test-results.json').write_text(json.dumps(result, indent=2) + '\n')
    return result



def inspect_apk_bytes(apk):
    apk = safe(apk)
    require(1024**2 < apk.stat().st_size <= 1024**3, 'APK byte size outside bounds')
    with zipfile.ZipFile(apk) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        require(len(infos) <= 30000 and len(names) == len(set(names)), 'APK inventory invalid')
        require(sum(item.file_size for item in infos) <= 3 * 1024**3, 'APK uncompressed payload exceeds bound')
        require(all(not name.startswith('/') and '..' not in Path(name).parts for name in names), 'Unsafe APK member path')
        required = {'AndroidManifest.xml', 'classes.dex', 'lib/arm64-v8a/libil2cpp.so', 'lib/arm64-v8a/libunity.so'}
        require(required <= set(names), 'Missing Android/ARM64 IL2CPP contents')
        require(not any(name.startswith('lib/') and not name.startswith('lib/arm64-v8a/') and not name.endswith('/') for name in names), 'Unexpected non-ARM64 native library')
        require(archive.testzip() is None, 'APK ZIP CRC mismatch')
    return dict(apkSha256=sha(apk), apkBytes=apk.stat().st_size)



def inspect_receipt(data, base, apk_result):
    expected = dict(schemaVersion=1, status='succeeded', stage='complete',
        scope='traversal-test-only-no-combat-not-complete-game', project='desert-rv/unity',
        scene='Assets/DesertRV/Scenes/TraversalHarness.unity', unityVersion=VERSION,
        version='0.1.0-dev.' + base['commit'][:12], commit=base['commit'],
        runId=base['runId'], runAttempt=base['runAttempt'],
        buildIdentitySha256=hashlib.sha256((base['commit'] + ':' + base['runId'] + ':' + base['runAttempt']).encode()).hexdigest(),
        target='Android', architecture='ARM64', backend='IL2CPP', development=True,
        signing='debug-only', apk='DesertRV.apk',
        sceneSha256=sha(PROJECT / 'Assets/DesertRV/Scenes/TraversalHarness.unity'),
        referenceSceneSha256=sha(PROJECT / 'Assets/DesertRV/Scenes/BodyStudy.unity'),
        fontSha256='a6a530f3e7e7a2c299470c42efff2e109fcc0a5be92686b96d5e84a05f3ecb2b',
        **apk_result)
    require(type(data) is dict and set(data) == set(expected), 'Native receipt fields differ from allowlist')
    require(all(type(data[k]) is type(v) and data[k] == v for k, v in expected.items()), 'Native receipt identity/configuration/hash mismatch')
    require(sha(PROJECT / 'Assets/DesertRV/UI/Fonts/NotoSansCJKsc-Regular.otf') == expected['fontSha256'], 'Restored font changed')
    return expected


def verify_apk():
    base = identity()
    count = os.environ['EXPECTED_TEST_COUNT']
    xml_hash = os.environ['EXPECTED_TEST_XML_SHA256']
    require(count == str(len(expected_cases())) and re.fullmatch('[a-f0-9]{64}', xml_hash), 'Missing successful test-job identity')
    directory = TASK / 'build/android-traversal-harness'
    apk = directory / 'DesertRV.apk'
    receipt = directory / 'build-receipt.json'
    result = inspect_apk_bytes(apk)
    native = inspect_receipt(read_json(receipt), base, result)
    # Do not tolerate reauthoring source assets during this build.
    subprocess.check_call(['git', 'diff', '--exit-code', '--quiet', '--', 'tasks/desert-rv/unity/Assets'], cwd=ROOT)
    output = TASK / 'evidence/android'
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(apk, output / 'DesertRV.apk')
    (output / 'build-receipt.json').write_text(json.dumps(native, indent=2) + '\n')
    independent = dict(base, schema='desert-rv-apk-verification/v1', **result,
                       projectPath='tasks/desert-rv/unity', nativeReceiptSha256=sha(receipt),
                       editModeTestsPassed=int(count), originalTestXmlSha256=xml_hash,
                       nativeReceiptFieldsVerified=True, zipCrcAndArm64Il2cppVerified=True,
                       deviceExecution='NOT_RUN', gameAcceptance='NOT_COMPLETE_GAME')
    (output / 'verification.json').write_text(json.dumps(independent, indent=2) + '\n')
    (output / 'SHA256SUMS').write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in sorted(output.iterdir())))
    print('New APK/receipt/scene bytes and current run identity verified; device execution NOT_RUN.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['guard', 'tests', 'apk'])
    args = parser.parse_args()
    if args.mode == 'guard':
        guard()
    elif args.mode == 'tests':
        result = inspect_tests(TASK / 'artifacts/tests')
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write('test_count=' + str(result['passed']) + '\n')
            f.write('test_xml_sha256=' + result['originalXmlSha256'] + '\n')
        print('Exact native test inventory passed; safe evidence saved.')
    else:
        verify_apk()


if __name__ == '__main__':
    main()
