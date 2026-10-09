#!/usr/bin/env python3
"""Last host-side boundary; publish only verified allowlist or one fixed failure status."""
import hashlib,json,os,pathlib,re,shutil,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[4]
TASK=ROOT/'tasks/desert-rv'
CODES={'editor-startup','request-identity','process-identity','duplicate-window','game-window-unavailable','window-identity','window-not-viewable','window-size','window-resized','ffmpeg-exited','video-frame-heartbeat','editor-stop-not-success','editor-disappeared','capture-watchdog','capture-validation-failed','encoder-shutdown','encoder-not-started','encoder-exited-before-stop','encoder-stop-pipe','encoder-stop-timeout','encoder-exit-nonzero','encoder-missing-video','capture-not-started','NONE','UNAVAILABLE'}
def safe(p):
    if p.is_symlink() or any(x.is_symlink() for x in p.parents):raise ValueError()
    return p
def sha(p):
    h=hashlib.sha256()
    with safe(p).open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()
def main():
    final=safe(TASK/'rendered-public-export')
    if final.exists():return 1
    stage=pathlib.Path(tempfile.mkdtemp(prefix='.rendered-public-',dir=TASK));code='EVIDENCE_UNAVAILABLE';ok=False
    try:
        if subprocess.run(['git','diff','--quiet','--exit-code'],cwd=ROOT).returncode or subprocess.run(['git','diff','--cached','--quiet','--exit-code'],cwd=ROOT).returncode:
            code='PROTECTED_SOURCE_CHANGED';raise ValueError()
        if os.environ.get('NATIVE_OUTCOME')!='success':code='NATIVE_PROCESS_NOT_SUCCESS';raise ValueError()
        control=json.loads(safe(TASK/'rendered-control-export/status.json').read_text())
        if control.get('privateCleanup')!='SUCCEEDED':code='PRIVATE_CLEANUP_FAILED';raise ValueError()
        if control.get('activation')!='SUCCEEDED':code='ACTIVATION_FAILED';raise ValueError()
        if control.get('licenseReturn')!='SUCCEEDED':code='LICENSE_RETURN_FAILED';raise ValueError()
        if control.get('renderProcess')!='SUCCEEDED':
            detail=control.get('captureFailureCode','UNAVAILABLE');code='CAPTURE_'+detail if detail in CODES else 'RENDERED_PROCESS_FAILED';raise ValueError()
        source=safe(TASK/'rendered-export');hashes=json.loads(safe(source/'export-sha256.json').read_text())
        names={p.name for p in source.iterdir()};allowed={'diagnostic-summary.json','real-time.mp4','export-sha256.json'}
        if not isinstance(hashes,dict) or set(hashes)|{'export-sha256.json'}!=names or len(names)>140:raise ValueError()
        for name in names:
            if name not in allowed and not re.fullmatch(r'frame-[0-9]{8,}\.png',name):raise ValueError()
            p=safe(source/name)
            if not p.is_file() or (name in hashes and sha(p)!=hashes[name]):raise ValueError()
        summary=json.loads((source/'diagnostic-summary.json').read_text())
        allowed_keys={'mode','sourceCommit','humanPlaytest','visualApproved','gameplayAccepted','androidVerified','audioCaptured','videoSourceVerified','sampleCount','screenshotCount','captureStartUtc','captureEndUtc','captureWallSeconds','videoSeconds','nominalCaptureFps','encodedFrameRate','averageFrameRate','width','height','replayWallSeconds','activityWallSeconds','completedObserved','failedObserved','screenshotTimes','windowPipelineVerified','softwareRendererVerified','gameplayInputsApplied','gameplaySessionStarted'}
        if not set(summary)<=allowed_keys or summary.get('sourceCommit')!=os.environ.get('GITHUB_SHA'):raise ValueError()
        if summary.get('mode') not in {'AUTOMATED_EDITOR_DIAGNOSTIC_NOT_ACCEPTANCE','WINDOW_SMOKE_ONLY_NOT_GAMEPLAY'}:raise ValueError()
        if any(summary.get(k) is not False for k in ('humanPlaytest','visualApproved','gameplayAccepted','androidVerified')):raise ValueError()
        for name in names:shutil.copyfile(source/name,stage/name)
        ok=True
    except Exception:
        # No partial video/images escape even if a later check failed.
        for p in stage.iterdir():p.unlink()
        (stage/'status.json').write_text(json.dumps({'status':'RENDERED_DIAGNOSTIC_FAILED_NOT_ACCEPTED','failureCode':code,'videoExported':False})+'\n')
    os.rename(stage,final)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as output:output.write("export_ready=true\n")
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
