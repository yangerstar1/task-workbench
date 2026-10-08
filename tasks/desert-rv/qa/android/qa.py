#!/usr/bin/env python3
"""Fail-closed identity and capture checks. No emulator runs during unit tests."""
import hashlib, json, os, re, struct, subprocess, sys, urllib.request, zipfile, zlib, binascii, math
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = 'yangerstar1/task-workbench'
def require(ok, message):
    if not ok: raise ValueError(message)
def digest(data): return hashlib.sha256(data).hexdigest()
def load(path): return json.loads(Path(path).read_text())
def write(path, value): Path(path).write_text(json.dumps(value, indent=2) + '\n')
def check_run(run, pin):
    require(str(run['id']) == pin['runId'] and str(run['run_attempt']) == pin['runAttempt'], 'Build run/attempt mismatch')
    require(run['repository']['full_name'] == REPO and not run['repository']['private'] and not run['repository']['fork'], 'Public original repository required')
    require(run['event'] == 'workflow_dispatch' and run['head_branch'] == 'main', 'Owner manual main build required')
    require(run['actor']['login'] == 'yangerstar1' and run['triggering_actor']['login'] == 'yangerstar1', 'Owner build required')
    require(run['path'] == '.github/workflows/desert-rv-android.yml', 'Wrong build workflow')
    require(run['conclusion'] == 'success' and run['status'] == 'completed', 'Successful completed build required')
    require(run['head_sha'] == pin['commit'], 'Build commit mismatch')
def check_bytes(apk, receipt, verification, pin):
    require(digest(apk) == pin['apkSha256'] and len(apk) == pin['apkBytes'], 'APK bytes differ from reviewed artifact')
    require(digest(receipt) == pin['receiptSha256'], 'Reviewed receipt bytes differ')
    native = json.loads(receipt)
    for key in ('commit', 'runId', 'runAttempt', 'apkSha256', 'apkBytes'):
        require(native[key] == pin[key] and verification[key] == pin[key], 'Receipt identity mismatch: ' + key)
    require(native['status'] == 'succeeded' and native['architecture'] == 'ARM64' and native['backend'] == 'IL2CPP', 'Unexpected native build')
    require(native['scope'] == 'traversal-test-only-no-combat-not-complete-game', 'Unreviewed APK scope')
def png_size(data):
    # Android screencap produces noninterlaced, 8-bit PNGs. Reject truncated streams,
    # unknown critical chunks, bad CRCs and oversized decompression before invoking a decoder.
    require(33 <= len(data) <= 32 * 1024**2 and data[:8] == b'\x89PNG\r\n\x1a\n', 'Invalid screenshot PNG')
    offset = 8; header = None; compressed = bytearray(); ended = False; saw_idat = False; idat_closed = False
    while offset < len(data):
        require(offset + 12 <= len(data), 'Truncated PNG chunk')
        length = struct.unpack('>I', data[offset:offset+4])[0]
        kind = data[offset+4:offset+8]; end = offset + 12 + length
        require(end <= len(data), 'Truncated PNG payload')
        require(re.fullmatch(b'[A-Za-z]{4}',kind) and 65 <= kind[2] <= 90, 'Invalid PNG chunk type')
        payload = data[offset+8:offset+8+length]
        crc = struct.unpack('>I', data[offset+8+length:end])[0]
        require(binascii.crc32(kind + payload) & 0xffffffff == crc, 'PNG CRC mismatch')
        require(header is not None or kind == b'IHDR', 'PNG must begin with IHDR')
        if kind == b'IHDR':
            require(header is None and length == 13, 'Invalid or duplicate IHDR')
            w,h,depth,color,compression,filters,interlace = struct.unpack('>IIBBBBB',payload)
            require(0 < w <= 4096 and 0 < h <= 4096 and depth == 8 and color in (0,2,4,6)
                    and compression == filters == interlace == 0, 'Unsupported screenshot encoding')
            header = (w,h,color)
        elif kind == b'IDAT':
            require(not idat_closed, 'Nonconsecutive IDAT chunks')
            compressed.extend(payload); saw_idat = True
        elif kind == b'IEND':
            require(length == 0 and saw_idat and end == len(data), 'Invalid PNG end')
            ended = True; offset = end; break
        else:
            require(kind == b'PLTE' or kind[0] & 32, 'Unknown critical PNG chunk')
            if saw_idat: idat_closed = True
        offset = end
    require(ended and header is not None, 'Missing PNG image/end data')
    w,h,color = header; channels = {0:1,2:3,4:2,6:4}[color]
    row = w * channels + 1; expected = row * h
    decoder = zlib.decompressobj(); raw = decoder.decompress(bytes(compressed),expected + 1)
    require(len(raw) == expected and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
            'Incomplete or oversized PNG pixel stream')
    require(all(raw[i] <= 4 for i in range(0,len(raw),row)), 'Invalid PNG row filter')
    return w,h

def api(suffix):
    req = urllib.request.Request('https://api.github.com/repos/' + REPO + suffix,
        headers={'Authorization':'Bearer ' + os.environ['GH_TOKEN'], 'Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(req,timeout=60) as response: return json.load(response)

def check_qa_run(run, env):
    require(str(run['id']) == env['GITHUB_RUN_ID'] and str(run['run_attempt']) == env['GITHUB_RUN_ATTEMPT'], 'QA run/attempt mismatch')
    require(run['repository']['full_name'] == REPO and run['repository']['private'] is False and run['repository']['fork'] is False, 'QA public original repository required')
    require(run['event'] == 'workflow_dispatch' and run['head_branch'] == 'main', 'QA manual main dispatch required')
    require(run['actor']['login'] == run['triggering_actor']['login'] == 'yangerstar1', 'QA owner required')
    require(run['path'] == '.github/workflows/desert-rv-android-qa.yml' and run['head_sha'] == env['GITHUB_SHA'], 'QA workflow/source identity mismatch')
    require(run['status'] == 'in_progress', 'QA run must currently be executing')
    if env.get('ALLOW_ONCE_KVM_ACL') == 'true':
        require(run['run_number'] == 4 and str(run['run_attempt']) == '1' and env.get('GITHUB_RUN_NUMBER') == '4', 'One-time ACL run number mismatch')

def execution_preflight():
    # The local environment alone is not an attestation: also check the live GitHub
    # run/job, checked-out source, prior verified identity and original APK bytes.
    e = os.environ
    require(e.get('GITHUB_ACTIONS') == 'true' and e.get('RUNNER_ENVIRONMENT') == 'github-hosted'
            and e.get('RUNNER_OS') == 'Linux', 'Only standard hosted Linux Actions execution is supported')
    require(e.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' and e.get('GITHUB_REPOSITORY') == REPO
            and e.get('GITHUB_REF') == 'refs/heads/main', 'Trusted QA dispatch required')
    require(e.get('GITHUB_ACTOR') == e.get('GITHUB_TRIGGERING_ACTOR') == 'yangerstar1', 'QA owner required')
    require(e.get('QA_MODE') in ('capture-only','input-check'), 'Unknown QA mode')
    for field in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','SOURCE_RUN_ID'):
        require(re.fullmatch('[1-9][0-9]{0,19}',e.get(field,'')), 'Invalid run identity')
    require(re.fullmatch('[a-f0-9]{40}',e.get('GITHUB_SHA','')), 'Invalid QA commit')
    check_qa_run(api('/actions/runs/' + e['GITHUB_RUN_ID']),e)
    jobs = api('/actions/runs/' + e['GITHUB_RUN_ID'] + '/attempts/' + e['GITHUB_RUN_ATTEMPT'] + '/jobs?per_page=100')['jobs']
    matching = [j for j in jobs if j.get('name') == 'evidence' and j.get('status') == 'in_progress']
    require(len(matching) == 1 and 'ubuntu-24.04' in matching[0].get('labels',[])
            and matching[0].get('runner_name','').startswith('GitHub Actions '), 'Live standard hosted QA job not verified')
    require(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip() == e['GITHUB_SHA'], 'QA checkout mismatch')
    paths = ['.github/workflows/desert-rv-android-qa.yml','tasks/desert-rv/qa/android']
    subprocess.run(['git','diff','--exit-code','--quiet','HEAD','--',*paths],check=True)
    untracked = subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*paths],text=True).splitlines()
    require(not any('__pycache__' not in Path(p).parts for p in untracked), 'Untracked QA source refused')
    pin = load(HERE/'approved-builds.json').get(e['SOURCE_RUN_ID']); require(pin is not None, 'Unapproved APK source')
    identity = load(Path(e['QA_OUT'])/'identity.json')
    require(identity['source'] == pin and identity['qaCommit'] == e['GITHUB_SHA']
            and identity['qaRunId'] == e['GITHUB_RUN_ID'] and identity['qaRunAttempt'] == e['GITHUB_RUN_ATTEMPT']
            and identity['mode'] == e['QA_MODE'], 'Prior verified APK/QA identity mismatch')
    apk = Path(e['QA_WORK'])/'DesertRV.apk'
    require(not apk.is_symlink() and apk.stat().st_size == pin['apkBytes'] and digest(apk.read_bytes()) == pin['apkSha256'], 'Execution APK changed')
    require(Path(e['QA_WORK']).resolve() == Path(e['RUNNER_TEMP']).resolve()/'desert-rv-android-qa', 'Execution work path outside disposable runner temp')
    require(Path(e['QA_OUT']).resolve() == Path(e['GITHUB_WORKSPACE']).resolve()/'android-qa-evidence', 'Unexpected evidence path')
    if e['QA_MODE'] == 'input-check':
        from input_plan import validate
        plan = load(HERE/'coordinates.json')
        require(plan.get('apkSha256') == pin['apkSha256'], 'Wrong input-plan APK')
        for width in (1280,1600): validate(plan,width)
    write(Path(e['QA_OUT'])/'execution-preflight.json',dict(status='VERIFIED',qaCommit=e['GITHUB_SHA'],
        qaRunId=e['GITHUB_RUN_ID'],qaRunAttempt=e['GITHUB_RUN_ATTEMPT'],runnerLabel='ubuntu-24.04',sourceApkSha256=pin['apkSha256']))

def source():
    out = Path(os.environ['QA_OUT']); out.mkdir(parents=True, exist_ok=True)
    work = Path(os.environ['QA_WORK']); work.mkdir(parents=True, exist_ok=True)
    require(os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' and os.environ.get('GITHUB_REPOSITORY') == REPO and os.environ.get('GITHUB_REF') == 'refs/heads/main', 'Trusted dispatch required')
    require(os.environ.get('GITHUB_ACTOR') == os.environ.get('GITHUB_TRIGGERING_ACTOR') == 'yangerstar1', 'Owner required')
    require(os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted', 'Hosted runner required')
    run_id = os.environ['SOURCE_RUN_ID']; require(re.fullmatch('[1-9][0-9]{0,19}', run_id), 'Numeric source run ID required')
    pin = load(HERE / 'approved-builds.json').get(run_id); require(pin is not None, 'Source run has not been reviewed and pinned')
    head = subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
    require(head == os.environ['GITHUB_SHA'], 'QA checkout identity mismatch')
    run = api('/actions/runs/' + run_id); check_run(run, pin)
    artifacts = api('/actions/runs/' + run_id + '/artifacts?per_page=100')
    selected = [a for a in artifacts['artifacts'] if a['id'] == pin['artifactId']]
    require(len(selected) == 1 and not selected[0]['expired'] and selected[0]['name'] == pin['artifactName'], 'Reviewed artifact missing/expired')
    # gh follows authenticated GitHub artifact redirects; no arbitrary URL input.
    archive = work / 'source.zip'
    with archive.open('wb') as f:
        subprocess.run(['gh','api',f'repos/{REPO}/actions/artifacts/{pin["artifactId"]}/zip'], stdout=f, check=True, timeout=180)
    require(archive.stat().st_size == pin['artifactZipBytes'] and digest(archive.read_bytes()) == pin['artifactZipSha256'], 'Reviewed artifact ZIP bytes differ')
    with zipfile.ZipFile(archive) as z:
        names = z.namelist(); require(len(names) == len(set(names)) and len(names) <= 20, 'Invalid archive inventory')
        require(sum(i.file_size for i in z.infolist()) <= 300 * 1024**2, 'Oversized expanded archive')
        require(all('/' not in n and '\\' not in n and n not in ('.','..') for n in names), 'Unsafe archive path')
        apk, receipt, verification = z.read('DesertRV.apk'), z.read('build-receipt.json'), json.loads(z.read('verification.json'))
    check_bytes(apk, receipt, verification, pin)
    (work / 'DesertRV.apk').write_bytes(apk)
    write(out / 'identity.json', dict(source=pin, qaCommit=head, qaRunId=os.environ['GITHUB_RUN_ID'], qaRunAttempt=os.environ['GITHUB_RUN_ATTEMPT'], mode=os.environ['QA_MODE'], execution='ARM64 APK translated on Android 30 x86_64 Google APIs; not ARM hardware', scope='Saved TraversalHarness; not complete game', gameAcceptance='NOT_EVALUATED', audio='NOT_EVALUATED', physicalGpuTouchLatencyPerformance='NOT_EVALUATED'))
    if os.environ['QA_MODE'] == 'input-check':
        plan = load(HERE / 'coordinates.json')
        require(plan.get('status') == 'reviewed' and plan.get('apkSha256') == pin['apkSha256'], 'BLOCKED: screenshot-reviewed input plan for exact APK required')
    print('Exact reviewed APK and separate QA/build identities verified.')
def screenshot():
    p,w,h = sys.argv[2:]; require(png_size(Path(p).read_bytes()) == (int(w),int(h)), 'Screenshot dimensions mismatch')
    subprocess.run(['ffmpeg','-v','error','-xerror','-nostdin','-i',p,'-frames:v','1','-f','null','-'],check=True,timeout=30,stdout=subprocess.DEVNULL)

def check_video_report(report,w,h):
    streams = [s for s in report.get('streams',[]) if s.get('codec_type') == 'video']
    require(len(streams) == 1, 'Exactly one video stream required')
    stream = streams[0]
    require(stream.get('width') == w and stream.get('height') == h, 'Video dimensions mismatch')
    duration = float(stream.get('duration',report.get('format',{}).get('duration','nan')))
    require(math.isfinite(duration) and 1 <= duration <= 121, 'Unbounded or empty video duration')
    require(int(stream.get('nb_read_frames','0')) >= 2, 'Video must contain decoded frames')

def video():
    p,w,h = sys.argv[2:]
    require(0 < Path(p).stat().st_size <= 512*1024**2, 'Invalid video size')
    raw = subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',p],timeout=180)
    report = json.loads(raw); check_video_report(report,int(w),int(h))
    subprocess.run(['ffmpeg','-v','error','-xerror','-nostdin','-i',p,'-map','0:v:0','-f','null','-'],check=True,timeout=180,stdout=subprocess.DEVNULL)
    write(Path(p).with_suffix('.validation.json'),dict(status='DECODED',width=int(w),height=int(h),sha256=digest(Path(p).read_bytes()),gameAcceptance='NOT_EVALUATED'))
if __name__ == '__main__':
    try:
        {'source':source, 'preflight':execution_preflight, 'screenshot':screenshot, 'video':video}[sys.argv[1]]()
    except Exception as e:
        out = Path(os.environ.get('QA_OUT', '.')); out.mkdir(parents=True, exist_ok=True)
        write(out / 'BLOCKED.json', {'status':'BLOCKED', 'reason':str(e), 'gameAcceptance':'NOT_EVALUATED'})
        raise
