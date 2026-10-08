#!/usr/bin/env python3
"""Fail-closed environment-only evidence. Never upload a workspace or Unity logs."""
import argparse
import difflib
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageStat
import verify_evidence as source

REGIONS = ('FirstStation', 'Scrapyard', 'NightBeacon')
VIEWS = ('overview', 'ground', 'landmark', 'cabin')
IMAGES = {f'{r}-{v}.png' for r in REGIONS for v in VIEWS}
CLEARANCE_FILES = {f'clearance-region-{i}.json' for i in (1,2,3)}
GENERATED = 'Assets/DesertRV/Scenes/Journey'
RENDER_TEST = 'DesertRV.Tests.JourneyEnvironmentRenderTests.AuthorAndCaptureTwelveRealEnvironmentViews'
SNAPSHOT = source.TASK / 'environment-before.json'
OUT = source.TASK / 'evidence/environment'
PARTIAL = source.TASK / 'evidence/environment-unaccepted'
DIAGNOSTIC = source.TASK / 'evidence/environment-source-diagnostic'
PACKAGE_DIAGNOSTIC = source.TASK / 'evidence/environment-package-diagnostic'
FAILED_STATUS = 'FAILED_PROTECTED_SOURCE_CHECK_NOT_ACCEPTED'


def require(ok, message):
    source.require(ok, message)


def tracked_snapshot(root):
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    return {p: source.sha(root / p) for p in paths if p}


def assert_preserved(before, after):
    changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    require(not changed, 'Original tracked files changed during environment authoring: ' + json.dumps(changed[:100]))


def valid_generated_name(name):
    if name == GENERATED + '.meta':
        return True
    prefix = GENERATED + '/'
    if not name.startswith(prefix):
        return False
    leaf = name[len(prefix):]
    return bool(re.fullmatch(r'(?:JourneyBootstrap|FirstStation|Scrapyard|NightBeacon)\.unity(?:\.meta)?|JourneyContent\.asset(?:\.meta)?|Region-[123]-Sky\.mat(?:\.meta)?|Layout-[A-F0-9]{6}\.mat(?:\.meta)?', leaf))


def inspect_png(path):
    source.safe(path)
    require(path.stat().st_size <= 10 * 1024**2, 'Oversized screenshot')
    with Image.open(path) as checked:
        checked.verify()  # PNG chunk CRC validation before full pixel decoding.
    with Image.open(path) as im:
        require(im.format == 'PNG' and im.size == (1440, 900), 'Invalid image format or dimensions')
        im.load()
        rgb = im.convert('RGB')
        extrema = rgb.getextrema()
        require(max(x[1] for x in extrema) >= 26 and max(x[1]-x[0] for x in extrema) >= 16,
                'Blank or near-black screenshot')
        require(max(ImageStat.Stat(rgb).stddev) >= 2, 'Uniform screenshot')


def inspect_native_report(directory):
    paths = list(directory.rglob('*.xml'))
    require(len(paths) <= 20, 'Too many native XML reports')
    for p in paths:
        require(source.safe(p).stat().st_size <= 10*1024**2, 'Oversized native XML')
    reports = [p for p in paths if ET.parse(p).getroot().tag == 'test-run']
    require(len(reports) == 1, 'Exactly one native render report required')
    root = ET.parse(reports[0]).getroot()
    cases = list(root.iter('test-case'))
    require(root.get('result') == 'Passed' and len(cases) == 1, 'Render native test failed or wrong count')
    require(cases[0].get('fullname') == RENDER_TEST and cases[0].get('result') == 'Passed', 'Wrong render native test')
    return source.sha(reports[0])


def inspect_clearance(project):
    common={'driving-corridor','vehicle-spawn','dismount','cabin-workbench'}
    allowed=common|{'salvage-access','power-access','short-approach-Ram salvage interaction',
                    'short-approach-Coil interaction','short-approach-Power interaction'}
    reports=[]
    for region in (1,2,3):
        value=source.read_json(project/f'JourneyEvidence/clearance-region-{region}.json')
        require(set(value)=={'region','passed','checkedZones','distantMeshes'},'Unexpected clearance fields')
        require(value['region']==region and value['passed'] is True and value['distantMeshes']==4,
                'Missing region clearance or incorrect distant mesh inventory')
        zones=value['checkedZones']
        require(isinstance(zones,list) and all(isinstance(z,str) for z in zones) and len(zones)==len(set(zones)),
                'Invalid clearance zone list')
        required=common|({'salvage-access'} if region==1 else {'salvage-access','power-access'} if region==2 else {'power-access'})
        require(required<=set(zones)<=allowed,'Missing or unknown checked clearance zones')
        reports.append(dict(region=region,passed=True,checkedZones=sorted(zones),distantMeshes=4))
    return reports


def inspect_capture(project):
    capture = project / 'JourneyEvidence/environment'
    require({p.name for p in capture.iterdir()} == IMAGES | {'capture-report.json'}, 'Unexpected or missing capture files')
    report = source.read_json(capture / 'capture-report.json')
    require(report.get('status') == 'captured-environment-only-not-gameplay-acceptance', 'Wrong capture scope')
    require(report.get('graphicsDeviceType') == 'OpenGLCore', 'Real OpenGL graphics required')
    require(report.get('bufferSceneTransitionsChecked') == 3 and report.get('captureBuffersReleased') is True,
            'Capture buffer scene transitions and explicit release not proven')
    device = report.get('graphicsDeviceName', '')
    require(isinstance(device, str) and 'llvmpipe' in device.lower() and len(device) < 256, 'Expected software Mesa llvmpipe')
    records = report.get('images')
    require(isinstance(records, list) and len(records) == 12, 'Twelve captures required')
    seen = set(); clean = []
    for record in records:
        require(record.get('region') in REGIONS and record.get('view') in VIEWS, 'Unknown viewpoint')
        name = record['region'] + '-' + record['view'] + '.png'
        require(name not in seen, 'Duplicate capture'); seen.add(name)
        require((record.get('width'), record.get('height')) == (1440, 900), 'Wrong reported size')
        low, high = record.get('minimum'), record.get('maximum')
        require(all(type(v) in (int, float) and math.isfinite(v) for v in (low, high)) and
                0 <= low <= high <= 1 and high-low >= .06 and high >= .1, 'Invalid native pixel range')
        require(re.fullmatch('[a-f0-9]{32}', record.get('sceneHash', '')), 'Missing scene dependency hash')
        inspect_png(capture / name)
        clean.append(dict(region=record['region'], view=record['view'], file=name,
                          width=1440,height=900,sceneHash=record['sceneHash'],sha256=source.sha(capture/name)))
    require(seen == IMAGES, 'Incomplete regions/views')
    layout = source.read_json(project / 'JourneyEvidence/candidate-layout.json')
    require(layout.get('passed') is True, 'Candidate layout failed')
    return dict(graphicsDeviceType='OpenGLCore', graphicsDeviceName=device, candidateLayoutPassed=True, bufferSceneTransitionsChecked=3, captureBuffersReleased=True, clearance=inspect_clearance(project), images=clean)


def collect_generated(project):
    folder = project / GENERATED
    source.safe(Path(str(folder)+'.meta'))
    files = [p for p in folder.rglob('*') if p.is_file()] + [Path(str(folder)+'.meta')]
    require(0 < len(files) < 100, 'Invalid generated file count')
    names = {p.relative_to(project).as_posix() for p in files}
    required = {GENERATED+'/'+n+'.unity' for n in ('JourneyBootstrap',*REGIONS)} | {GENERATED+'/JourneyContent.asset'}
    require(required <= names, 'Missing scene or content manifest')
    for name in names:
        require(valid_generated_name(name), 'Non-allowlisted generated file')
        p = source.safe(project / name)
        require(p.stat().st_size <= 40*1024**2, 'Oversized generated file')
        if not name.endswith('.meta'):
            require(name+'.meta' in names, 'Generated asset has no meta')
        text = p.read_text()
        require(text.startswith('fileFormatVersion: 2') if name.endswith('.meta') else text.startswith('%YAML 1.1'), 'Non-Unity serialized output')
    require(sum(p.stat().st_size for p in files) <= 100*1024**2, 'Oversized generated bundle')
    return sorted(names)


def before():
    source.guard()
    require(not SNAPSHOT.exists() and not (source.PROJECT/GENERATED).exists() and
            not (source.PROJECT/'JourneyEvidence').exists(), 'Authoring outputs must be fresh')
    source.verify_source_state()
    SNAPSHOT.write_text(json.dumps(tracked_snapshot(source.ROOT),sort_keys=True))
    print('Protected tracked source snapshot saved; authoring outputs fresh.')


def package():
    require(not OUT.exists(), 'Refuse stale output')
    protected = source.read_json(SNAPSHOT)
    assert_preserved(protected, tracked_snapshot(source.ROOT))
    # Full current source inventory includes generated files now, so verify the exact
    # protected files via snapshot and hash the pre-execution SOURCE-STATE instead.
    native_hash = inspect_native_report(source.TASK/'artifacts/environment')
    capture = inspect_capture(source.PROJECT)
    names = collect_generated(source.PROJECT)
    OUT.mkdir(parents=True)
    for report in capture['clearance']:
        (OUT/f"clearance-region-{report['region']}.json").write_text(json.dumps(dict(report,status='CANDIDATE_CLEARANCE_ONLY_NOT_GAMEPLAY_APPROVAL'),indent=2)+'\n')
    records=[]; diffs=[]
    for name in names:
        p=source.PROJECT/name; dest=OUT/'generated'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        records.append(dict(path=name,sha256=source.sha(p),size=p.stat().st_size))
        diffs.extend(difflib.unified_diff([],p.read_text().splitlines(True),fromfile='/dev/null',tofile='b/'+name))
    for name in sorted(IMAGES):shutil.copyfile(source.PROJECT/'JourneyEvidence/environment'/name,OUT/name)
    (OUT/'generated-new-scenes.diff').write_text(''.join(diffs))
    receipt=source.identity();receipt.update(schema='desert-rv-environment-evidence/v1',
        scope='Environment candidate screenshots only; gameplay, device execution, production art acceptance NOT_RUN',
        protectedTrackedFilesUnchanged=True,protectedTrackedFileCount=len(protected),
        protectedSnapshotSha256=source.sha(SNAPSHOT),nativeRenderTest=RENDER_TEST,nativeRenderXmlSha256=native_hash,
        generated=records,capture=capture,editModeRules='NOT_RUN',playModeRules='NOT_RUN',androidApk='NOT_RUN')
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    hashes=[dict(path=p.relative_to(OUT).as_posix(),sha256=source.sha(p),size=p.stat().st_size) for p in sorted(OUT.rglob('*')) if p.is_file()]
    (OUT/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2)+'\n')
    print('Verified twelve real captures and unchanged tracked source; sanitized allowlisted bundle ready.')


def protection_differences(before, after):
    changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    require(0 < len(changed) <= 2000, 'Partial evidence requires bounded actual source mismatch')
    result=[]
    for path in changed:
        require(isinstance(path,str) and len(path)<=300 and not path.startswith('/') and
                '..' not in Path(path).parts and Path(path).as_posix()==path and
                not any(ord(c)<32 for c in path), 'Unsafe protection diagnostic path')
        old,new=before.get(path),after.get(path)
        require(all(x is None or (isinstance(x,str) and re.fullmatch('[a-f0-9]{64}',x)) for x in (old,new)),
                'Invalid protection diagnostic hash')
        result.append(dict(path=path,beforeSha256=old,afterSha256=new))
    return result


def package_unaccepted(project, destination, before, after, run_identity):
    # No logs, XML, material contents, generated scenes, or arbitrary native JSON.
    # Still require successful native pixels/layout. A failed source check never
    # becomes a verified package or approval merely because screenshots exist.
    require(not destination.exists(), 'Refuse stale unaccepted output')
    differences=protection_differences(before,after)
    capture=inspect_capture(project)
    layout=source.read_json(project/'JourneyEvidence/candidate-layout.json')
    hashes=layout.get('sceneDependencyHashes')
    require(layout.get('mode')=='candidate-layout-only-not-gameplay-approval' and
            isinstance(hashes,list) and len(hashes)==4 and
            all(isinstance(h,str) and re.fullmatch('[a-f0-9]{32}',h) for h in hashes), 'Invalid layout provenance')
    destination.mkdir(parents=True)
    for name in sorted(IMAGES):shutil.copyfile(project/'JourneyEvidence/environment'/name,destination/name)
    for report in capture['clearance']:
        (destination/f"clearance-region-{report['region']}.json").write_text(json.dumps(dict(report,status=FAILED_STATUS),indent=2)+'\n')
    capture['status']=FAILED_STATUS
    (destination/'capture-report.json').write_text(json.dumps(capture,indent=2)+'\n')
    (destination/'candidate-layout.json').write_text(json.dumps(dict(status=FAILED_STATUS,
        mode=layout['mode'],passed=True,sceneDependencyHashes=hashes),indent=2)+'\n')
    diagnostic=dict(run_identity,status=FAILED_STATUS,accepted=False,
                    protectedTrackedFilesUnchanged=False,changedFiles=differences)
    (destination/'protected-source-failure.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
    allowed=IMAGES|CLEARANCE_FILES|{'capture-report.json','candidate-layout.json','protected-source-failure.json'}
    require({p.name for p in destination.iterdir()}==allowed,'Unexpected partial export')
    manifest=[dict(path=p.name,sha256=source.sha(p),size=p.stat().st_size) for p in sorted(destination.iterdir())]
    (destination/'SHA256SUMS.json').write_text(json.dumps(dict(status=FAILED_STATUS,files=manifest),indent=2)+'\n')


def write_protection_diagnostic(destination, before, after, run_identity):
    require(not destination.exists(), 'Refuse stale source diagnostic')
    differences=protection_differences(before,after)
    destination.mkdir(parents=True)
    payload=dict(run_identity,status=FAILED_STATUS,accepted=False,
                 protectedTrackedFilesUnchanged=False,changedFiles=differences)
    (destination/'protected-source-failure.json').write_text(json.dumps(payload,indent=2)+'\n')


def diagnose():
    before=source.read_json(SNAPSHOT);after=tracked_snapshot(source.ROOT)
    if before==after:
        print('No tracked source mismatch to export. Native failure, if any, remains a failure.')
        return
    ident=source.identity();ident['scope']='Protected source hash mismatch only; no image, scene or gameplay acceptance'
    write_protection_diagnostic(DIAGNOSTIC,before,after,ident)
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:output.write('present=true\n')
    print(FAILED_STATUS + ': independent safe source mismatch JSON saved.')


def validated_unity_dependencies(value, locked=False):
    require(isinstance(value,dict) and set(value)=={'dependencies'}, 'Unexpected package root fields')
    dependencies=value['dependencies']
    require(isinstance(dependencies,dict) and len(dependencies)<=200, 'Invalid package count')
    def version_map(items):
        require(isinstance(items,dict) and len(items)<=200,'Invalid dependency map')
        for key,version in items.items():
            require(isinstance(key,str) and re.fullmatch(r'com\.unity\.[a-z0-9_.-]+',key) and len(key)<=120,
                    'Non-Unity or unsafe package name')
            require(isinstance(version,str) and re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?',version) and len(version)<=60,
                    'Non-version dependency; URLs, paths and tokens are forbidden')
        return dict(sorted(items.items()))
    if not locked:return version_map(dependencies)
    result={}
    for name,entry in dependencies.items():
        require(isinstance(entry,dict) and set(entry)<={'version','depth','source','dependencies','url'} and
                {'version','depth','source','dependencies'}<=set(entry),'Unexpected package lock fields')
        version_map({name:entry['version']})
        require(type(entry['depth']) is int and 0<=entry['depth']<=20,'Invalid dependency depth')
        require(entry['source'] in ('builtin','registry'),'Unsupported source; git, local paths and private registries forbidden')
        if entry['source']=='registry':require(entry.get('url')=='https://packages.unity.com','Non-official registry forbidden')
        else:require('url' not in entry,'Builtin dependency must not carry registry URL')
        result[name]=dict(version=entry['version'],depth=entry['depth'],source=entry['source'],
                          dependencies=version_map(entry['dependencies']))
        if entry['source']=='registry':result[name]['url']='https://packages.unity.com'
    return dict(sorted(result.items()))


def diagnose_packages():
    # Separate export: failure here cannot remove the already-uploaded path/hash diagnosis.
    require(not PACKAGE_DIAGNOSTIC.exists(),'Refuse stale package diagnosis')
    before=source.read_json(SNAPSHOT);after=tracked_snapshot(source.ROOT)
    names=['tasks/desert-rv/unity/Packages/manifest.json','tasks/desert-rv/unity/Packages/packages-lock.json']
    require(any(before.get(n)!=after.get(n) for n in names),'No package mutation to diagnose')
    report=dict(source.identity(),status=FAILED_STATUS,accepted=False,scope='Allowlisted Unity package resolution diagnosis only')
    for name,locked,label in zip(names,(False,True),('manifest','lock')):
        raw=subprocess.check_output(['git','show','HEAD:'+name],cwd=source.ROOT)
        require(len(raw)<=4*1024**2 and hashlib.sha256(raw).hexdigest()==before[name], 'Original package bytes do not match protected snapshot')
        original=json.loads(raw)
        resolved=source.read_json(source.ROOT/name)
        report[label]=dict(beforeSha256=before[name],afterSha256=after[name],
            before=validated_unity_dependencies(original,locked),after=validated_unity_dependencies(resolved,locked))
    PACKAGE_DIAGNOSTIC.mkdir(parents=True)
    (PACKAGE_DIAGNOSTIC/'unity-package-resolution.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Strict Unity dependency metadata saved; no raw package files or arbitrary fields exported.')


def partial():
    inspect_native_report(source.TASK/'artifacts/environment')
    ident=source.identity();ident['scope']='Unaccepted environment pixels for diagnosis; protected source check FAILED; gameplay/APK NOT_RUN'
    package_unaccepted(source.PROJECT,PARTIAL,source.read_json(SNAPSHOT),tracked_snapshot(source.ROOT),ident)
    print(FAILED_STATUS + ': bounded screenshots and source hash diagnosis only.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('before','package','partial','diagnose','diagnose-packages'))
    args=parser.parse_args(); {'before':before,'package':package,'partial':partial,'diagnose':diagnose,'diagnose-packages':diagnose_packages}[args.mode]()
