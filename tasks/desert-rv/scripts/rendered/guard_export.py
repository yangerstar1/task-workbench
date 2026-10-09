#!/usr/bin/env python3
"""Last host-side boundary; publish only verified allowlist or one fixed failure status."""
import hashlib,json,os,pathlib,re,shutil,subprocess,tempfile
import startup_diagnostic as startup
ROOT=pathlib.Path(__file__).resolve().parents[4]
TASK=ROOT/'tasks/desert-rv'
CODES={'editor-startup','request-identity','process-identity','duplicate-window','game-window-unavailable','window-identity','window-not-viewable','window-size','window-resized','ffmpeg-exited','video-frame-heartbeat','editor-stop-not-success','editor-disappeared','capture-watchdog','capture-validation-failed','encoder-shutdown','encoder-not-started','encoder-exited-before-stop','encoder-stop-pipe','encoder-stop-timeout','encoder-exit-nonzero','encoder-missing-video','capture-not-started','NONE','UNAVAILABLE'}
STATES={'NOT_ATTEMPTED','SUCCEEDED','FAILED'}
PHASES=('editor-spawn','executeMethod-entered','playmode-entered','view-created','X11-window-verified','first-encoded-frame','duration-complete')
CONTROL_FIELDS={'schema','mode','activation','licenseReturn','renderProcess','privateCleanup','captureFailureCode','renderPhases'}
def unique_object(pairs):
    out={}
    for key,value in pairs:
        if key in out:raise ValueError()
        out[key]=value
    return out
def read_control(p):
    p=safe(p)
    if not p.is_file() or p.stat().st_size>4096:raise ValueError()
    value=json.loads(p.read_text(),object_pairs_hook=unique_object)
    if not isinstance(value,dict) or set(value) not in (CONTROL_FIELDS,CONTROL_FIELDS|{'startupDiagnostics'}):raise ValueError()
    if type(value['schema']) is not int or value['schema']!=1 or value['mode']!='RENDERED_CONTROL_ONLY_NOT_ACCEPTANCE':raise ValueError()
    if any(type(value[k]) is not str or value[k] not in STATES for k in ('activation','licenseReturn','renderProcess','privateCleanup')):raise ValueError()
    if type(value['captureFailureCode']) is not str or value['captureFailureCode'] not in CODES:raise ValueError()
    phases=value['renderPhases']
    if not isinstance(phases,list) or phases!=[p for p in PHASES if p in phases]:raise ValueError()
    if 'startupDiagnostics' in value:startup.validate(value['startupDiagnostics'],set(startup.source_map(TASK/'unity').values()))
    return value
def failure_details(control):
    # Reconstruct from finite enums only. Never copy arbitrary receipt fields, logs, or traces.
    result={key:control[key] for key in ('activation','licenseReturn','renderProcess','privateCleanup','captureFailureCode','renderPhases')}
    if 'startupDiagnostics' in control:result['startupDiagnostics']=control['startupDiagnostics']
    return result
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
    stage=pathlib.Path(tempfile.mkdtemp(prefix='.rendered-public-',dir=TASK));code='EVIDENCE_UNAVAILABLE';ok=False;control=None
    try:
        if subprocess.run(['git','diff','--quiet','--exit-code'],cwd=ROOT).returncode or subprocess.run(['git','diff','--cached','--quiet','--exit-code'],cwd=ROOT).returncode:
            code='PROTECTED_SOURCE_CHANGED';raise ValueError()
        try:control=read_control(TASK/'rendered-control-export/status.json')
        except Exception:control=None
        # Detail visibility does not grant success: preserve the actual native outcome gate.
        if os.environ.get('NATIVE_OUTCOME')!='success':code='NATIVE_PROCESS_NOT_SUCCESS';raise ValueError()
        if control is None:code='CONTROL_STATUS_SCHEMA_INVALID_OR_UNAVAILABLE';raise ValueError()
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
        report={'status':'RENDERED_DIAGNOSTIC_FAILED_NOT_ACCEPTED','failureCode':code,'videoExported':False}
        if control is not None:report['diagnosticDetails']=failure_details(control)
        (stage/'status.json').write_text(json.dumps(report)+'\n')
    os.rename(stage,final)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as output:output.write("export_ready=true\n")
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
