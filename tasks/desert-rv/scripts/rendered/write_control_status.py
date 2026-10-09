#!/usr/bin/env python3
# Fixed enums only; never copy process logs, credentials, paths, or exception strings.
import json,os,pathlib,re,sys
from guard_export import CODES,PHASES,STATES,safe,unique_object
BASE=pathlib.Path('/github/workspace/tasks/desert-rv')
CAPTURE_FIELDS={'mode','sourceVerified','visualReviewed','audioCaptured','captureStartUtc','captureEndUtc','nominalCaptureFps','identityChecks','encodedProgressFrames','windowId','title','pid','width','height','failureCode','editorExitCode','editorStopAcknowledged','encoderExitCode','encoderStopMethod','encoderFailureCode','videoSha256'}
def read_small(path):
    p=safe(path)
    if not p.is_file() or p.stat().st_size>16384:raise ValueError()
    return json.loads(p.read_text(),object_pairs_hook=unique_object)
def capture_detail(path):
    try:
        value=read_small(path)
        needed={'mode','sourceVerified','failureCode','editorExitCode','editorStopAcknowledged','encoderExitCode','encoderStopMethod','encoderFailureCode'}
        if not isinstance(value,dict) or not needed<=set(value)<=CAPTURE_FIELDS:raise ValueError()
        if value['mode']!='VERIFIED_GAME_WINDOW_CAPTURE' or type(value['sourceVerified']) is not bool:raise ValueError()
        if type(value['editorStopAcknowledged']) is not bool or value['encoderStopMethod'] not in ('none','stdin-q'):raise ValueError()
        for k in ('editorExitCode','encoderExitCode'):
            if value[k] is not None and (type(value[k]) is not int or not -255<=value[k]<=255):raise ValueError()
        if value['encoderFailureCode'] is not None and value['encoderFailureCode'] not in CODES:raise ValueError()
        if value['sourceVerified']:
            if value['failureCode'] is not None or value['encoderFailureCode'] is not None or value['editorStopAcknowledged'] is not True or value['editorExitCode']!=0 or value['encoderExitCode']!=0 or value['encoderStopMethod']!='stdin-q':raise ValueError()
            return 'NONE'
        code=value['failureCode']
        if type(code) is not str or code not in CODES-{'NONE','UNAVAILABLE'}:raise ValueError()
        return code
    except Exception:return 'UNAVAILABLE'
def read_phases(path):
    try:
        value=read_small(path)
        if not isinstance(value,dict) or set(value)!={'schema','phases'} or type(value['schema']) is not int or value['schema']!=1:raise ValueError()
        phases=value['phases']
        if not isinstance(phases,list) or phases!=[p for p in PHASES if p in phases]:raise ValueError()
        return phases
    except Exception:return []
def summarize_progress(directory,evidence):
    directory=safe(pathlib.Path(directory));evidence=safe(pathlib.Path(evidence))
    phases=[]
    for phase in PHASES:
        marker=safe(directory/phase)
        if marker.is_file() and marker.stat().st_size==1 and marker.read_text()=='1':phases.append(phase)
    evidence.mkdir(parents=True,exist_ok=True)
    out=evidence/'render-progress.json';tmp=evidence/'render-progress.tmp'
    tmp.write_text(json.dumps({'schema':1,'phases':phases})+'\n');os.replace(tmp,out)
def write_status(values,base=BASE):
    if len(values)!=4 or not all(type(v) is str and v in STATES for v in values):raise ValueError()
    report=dict(schema=1,mode='RENDERED_CONTROL_ONLY_NOT_ACCEPTANCE',activation=values[0],licenseReturn=values[1],renderProcess=values[2],privateCleanup=values[3],
        captureFailureCode=capture_detail(base/'rendered-private-evidence/capture-receipt.json'),renderPhases=read_phases(base/'rendered-private-evidence/render-progress.json'))
    out=safe(base/'rendered-control-export');out.mkdir(exist_ok=True);os.chmod(out,0o755)
    p=safe(out/'status.json');p.write_text(json.dumps(report)+'\n');os.chmod(p,0o644)
    if read_small(p)!=report:raise ValueError()
    export=safe(base/'rendered-export')
    if export.is_dir():
        files=list(export.iterdir())
        if all(p.is_file() and not p.is_symlink() and (p.name in {'diagnostic-summary.json','export-sha256.json','real-time.mp4'} or re.fullmatch(r'frame-[0-9]{8,}\.png',p.name)) for p in files):
            for p in files:os.chmod(p,0o644)
            os.chmod(export,0o755)
def main():
    try:
        if len(sys.argv)==4 and sys.argv[1]=='--record-progress':summarize_progress(sys.argv[2],sys.argv[3])
        else:write_status(sys.argv[1:])
    except Exception:return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
