#!/usr/bin/env python3
"""Validate everything first, then atomically publish a strict game-only artifact directory."""
import argparse, datetime, hashlib, json, math, os, pathlib, re, shutil, subprocess, tempfile
from PIL import Image, ImageStat

ACTIVITIES={'physical-installation','reload','threatened-action','threatened-stationary','driving-traversal',
    'walking-exploration-candidate','empty-powered-wait','stationary-no-action','Menu','Loading','Paused','Failed','Completed'}
def require(ok):
    if not ok: raise ValueError('diagnostic-evidence-validation-failed')
def safe(path, is_file=True):
    p=pathlib.Path(path).absolute()
    require(not p.is_symlink() and not any(x.is_symlink() for x in p.parents))
    if is_file: require(p.is_file())
    return p
def sha(path):
    digest=hashlib.sha256()
    with safe(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()
def read_json(path):
    p=safe(path);require(p.stat().st_size<=16*1024**2)
    return json.loads(p.read_text(),parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite-json')))
def finite(value):return type(value) in (int,float) and math.isfinite(value) and value>=0
def inspect_png(path,size):
    # Same CRC/full decoding/nonblank thresholds as existing environment_evidence.inspect_png.
    p=safe(path);require(p.stat().st_size<=10*1024**2)
    with Image.open(p) as checked: checked.verify()
    with Image.open(p) as im:
        require(im.format=='PNG' and im.size==size);im.load();rgb=im.convert('RGB');extrema=rgb.getextrema()
        require(max(x[1] for x in extrema)>=26 and max(x[1]-x[0] for x in extrema)>=16)
        require(max(ImageStat.Stat(rgb).stddev)>=2)
def probe_video(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0',
        '-show_entries','stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames:format=duration',
        '-of','json',str(safe(path))],text=True))
def prepare(src,dst,probe=probe_video,mode="journey"):
    require(mode in {"journey","window-smoke"});smoke=mode=="window-smoke"
    src=safe(src,False);require(src.is_dir());dst=safe(dst,False);require(not dst.exists());safe(dst.parent,False)
    log=safe(src/'timeline.jsonl');require(log.stat().st_size<=256*1024**2)
    rows=[json.loads(line,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite-json'))) for line in log.read_text().splitlines()]
    samples=[r for r in rows if r.get('kind')=='sample'];captures=[r for r in rows if r.get('kind')=='capture']
    require(samples and captures)
    byframe={};previous_frame=-1;previous_wall=-1
    for s in samples:
        require(type(s.get('frame'))==int and s['frame']>previous_frame and finite(s.get('wall')) and s['wall']>=previous_wall)
        if smoke:
            require(s.get('mode')=='WINDOW_SMOKE_ONLY' and s.get('status')=='RenderingOnly' and s.get('activityEvidence')=='RenderingOnly')
        else:
            require(type(s.get('generation'))==int and s['generation']>=0 and s.get('activityEvidence') in ACTIVITIES)
            require(s.get('status') in {'Menu','Loading','Playing','Paused','Failed','Completed'})
        require(type(s.get('screenWidth'))==int and type(s.get('screenHeight'))==int and 320<=s['screenWidth']<=4096 and 200<=s['screenHeight']<=2160 and s['screenWidth']>=s['screenHeight'])
        byframe[s['frame']]=s;previous_frame=s['frame'];previous_wall=s['wall']
    names=set();previous_frame=-1;previous_wall=-1;validated=[]
    for r in captures:
        name=r.get('detail','');require(isinstance(name,str) and re.fullmatch(r'frame-[0-9]{8,}\.png',name))
        require(name not in names and type(r.get('frame'))==int and r['frame']>previous_frame and r['frame'] in byframe)
        require(int(name[6:-4])==r['frame'] and finite(r.get('wall')) and r['wall']>=previous_wall)
        sample=byframe[r['frame']];require(r['wall']>=sample['wall'] and r['wall']-sample['wall']<5)
        inspect_png(src/name,(sample['screenWidth'],sample['screenHeight']))
        names.add(name);validated.append((src/name,name));previous_frame=r['frame'];previous_wall=r['wall']
    scope=read_json(src/('window-smoke-scope.json' if smoke else 'diagnostic-scope.json'));commit=scope.get('sourceCommit','');require(re.fullmatch('[a-f0-9]{40}',commit))
    if smoke:
        require(scope.get('mode')=='WINDOW_SMOKE_ONLY' and scope.get('scenePath')=='Assets/DesertRV/Scenes/BodyStudy.unity' and scope.get('softwareRendererVerified') is True)
        require(re.fullmatch('[a-f0-9]{64}',scope.get('sceneSha256','')) and re.fullmatch('[a-f0-9]{32}',scope.get('dependencyHash','')))
        require(any(r.get('kind')=='stop' and r.get('detail')=='window-smoke-ended' for r in rows))
        require(29<=samples[-1]['wall']<=31 and len(captures)>=25)
    receipt=read_json(src/'capture-receipt.json')
    require('failureCode' in receipt and receipt['failureCode'] is None and 'encoderFailureCode' in receipt and receipt['encoderFailureCode'] is None)
    require(receipt.get('editorStopAcknowledged') is True and type(receipt.get('editorExitCode')) is int and receipt['editorExitCode']==0)
    require(type(receipt.get('encoderExitCode')) is int and receipt['encoderExitCode']==0 and receipt.get('encoderStopMethod')=='stdin-q')
    require(receipt.get('mode')=='VERIFIED_GAME_WINDOW_CAPTURE' and receipt.get('sourceVerified') is True and receipt.get('nominalCaptureFps')==30)
    require(re.fullmatch(r'DESERTRV_GAME_[a-f0-9]{32}',receipt.get('title','')) and re.fullmatch('[0-9]+',receipt.get('windowId','')))
    require(type(receipt.get('pid'))==int and receipt['pid']>0 and type(receipt.get('identityChecks'))==int and receipt['identityChecks']>0)
    require(type(receipt.get('encodedProgressFrames'))==int and receipt['encodedProgressFrames']>0)
    video=safe(src/'real-time.mp4');require(sha(video)==receipt.get('videoSha256'))
    data=probe(video);stream=data['streams'][0];require(stream.get('r_frame_rate')=='30/1')
    rate=stream.get('avg_frame_rate','');require(isinstance(rate,str) and re.fullmatch(r'[0-9]+/[1-9][0-9]*',rate))
    numerator,denominator=map(int,rate.split('/'));average=numerator/denominator;require(finite(average) and 29.9<=average<=30.1)
    duration=float(data['format']['duration']);require(finite(duration) and duration+1>=samples[-1]['wall'])
    require(stream.get('width')==receipt.get('width') and stream.get('height')==receipt.get('height'))
    begin=datetime.datetime.fromisoformat(receipt['captureStartUtc'].replace('Z','+00:00'));end=datetime.datetime.fromisoformat(receipt['captureEndUtc'].replace('Z','+00:00'))
    require(begin.tzinfo is not None and end.tzinfo is not None);wall=(end-begin).total_seconds()
    require(finite(wall) and abs(wall-duration)<=max(3.,wall*.03) and receipt['identityChecks']>=wall*2)
    buckets={}
    for a,b in zip(samples,samples[1:]):
        if smoke or a['generation']==b['generation']:buckets[b['activityEvidence']]=buckets.get(b['activityEvidence'],0.)+b['wall']-a['wall']
    summary=dict(mode='WINDOW_SMOKE_ONLY_NOT_GAMEPLAY' if smoke else 'AUTOMATED_EDITOR_DIAGNOSTIC_NOT_ACCEPTANCE',sourceCommit=commit,humanPlaytest=False,
        visualApproved=False,gameplayAccepted=False,androidVerified=False,audioCaptured=False,videoSourceVerified=True,
        sampleCount=len(samples),screenshotCount=len(captures),captureStartUtc=begin.isoformat(),captureEndUtc=end.isoformat(),
        captureWallSeconds=wall,videoSeconds=duration,nominalCaptureFps=30,encodedFrameRate='30/1',averageFrameRate=average,
        width=stream['width'],height=stream['height'],replayWallSeconds=samples[-1]['wall'],activityWallSeconds=buckets,
        completedObserved=any(s['status']=='Completed' for s in samples),failedObserved=any(s['status']=='Failed' for s in samples),
        screenshotTimes=[{'frame':r['frame'],'wall':r['wall']} for r in captures])
    if smoke:summary.update(windowPipelineVerified=True,softwareRendererVerified=True,gameplayInputsApplied=False,gameplaySessionStarted=False)
    # No output directory is visible until all validation/copy/hash work succeeds.
    staging=pathlib.Path(tempfile.mkdtemp(prefix='.diagnostic-export-',dir=dst.parent))
    try:
        for path,name in validated+[(video,'real-time.mp4')]:shutil.copyfile(safe(path),staging/name)
        (staging/'diagnostic-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        hashes={p.name:sha(p) for p in staging.iterdir() if p.is_file()}
        (staging/'export-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
        require(not dst.exists());os.rename(staging,dst)
    finally:
        if staging.exists():shutil.rmtree(staging)
    return summary

def main():
    ap=argparse.ArgumentParser();ap.add_argument('evidence');ap.add_argument('export');ap.add_argument('--mode',choices=['journey','window-smoke'],default='journey');args=ap.parse_args()
    try:prepare(pathlib.Path(args.evidence),pathlib.Path(args.export),mode=args.mode)
    except Exception:
        # Separate fixed-string failure receipt; never expose raw exception/log/path data or partial success export.
        dst=safe(pathlib.Path(args.export).with_name(pathlib.Path(args.export).name+'-failed'),False)
        if not dst.exists():
            dst.mkdir();(dst/'status.json').write_text('{"status":"FAILED_DIAGNOSTIC_EXPORT_NOT_ACCEPTED","videoExported":false}\n')
        return 1
    return 0
if __name__=='__main__':raise SystemExit(main())

