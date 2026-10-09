#!/usr/bin/env python3
"""Fixed BodyStudy standalone proof; one owned window, no input, no desktop fallback."""
import datetime,hashlib,json,math,os,pathlib,re,shutil,subprocess,sys,tempfile,threading,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from capture_game_window import identity,finish_encoder,atomic,stamp
from prepare_safe_diagnostic_export import safe,sha,read_json,inspect_png,probe_video,require
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'rendered'))
import startup_diagnostic as startup
TITLE='DESERTRV_REFERENCE_PLAYER'
MODE='BODY_STUDY_LINUX_PLAYER_CANDIDATE_ONLY'
SCENE='tasks/desert-rv/unity/Assets/DesertRV/Scenes/BodyStudy.unity'
ROOT=pathlib.Path(__file__).resolve().parents[4]
TASK=ROOT/'tasks/desert-rv'
EVIDENCE=TASK/'player-private-evidence'
PUBLIC=TASK/'player-public-export'

BUILD_STAGES={'NOT_OBSERVED','EXECUTE_METHOD_ENTERED','TARGET_CHECKED','SCENE_VALIDATED','BUILD_PLAYER_ENTERED','BUILD_PLAYER_RETURNED','BUILD_RECEIPT_WRITTEN'}
BUILD_FAILURES={'NONE','LINUX_TARGET_UNSUPPORTED','PROJECT_COMPILE_ERRORS','REFERENCE_BUILD_FAILED','BUILD_DIAGNOSTIC_UNAVAILABLE'}
PLAYER_FAILURES={'PLAYER_STARTUP_FAILED','PLAYER_WINDOW_FAILED','PLAYER_CAPTURE_FAILED'}
def empty_build_native():
    return dict(mode='BODY_STUDY_BUILD_FIXED_DIAGNOSTIC',stage='NOT_OBSERVED',exceptionKind='NONE',buildResult='UNAVAILABLE',targetChecked=False,targetSupported=False,buildReportAvailable=False,settingsRestored=False,totalErrors=0,totalWarnings=0)
def validate_build_native(value):
    require(isinstance(value,dict) and set(value)==set(empty_build_native()))
    require(value['mode']=='BODY_STUDY_BUILD_FIXED_DIAGNOSTIC' and value['stage'] in BUILD_STAGES)
    require(value['exceptionKind'] in {'NONE','FILE_NOT_FOUND','UNAUTHORIZED_ACCESS','IO','INVALID_OPERATION','OTHER'})
    require(value['buildResult'] in {'UNAVAILABLE','SUCCEEDED','FAILED','CANCELLED','UNKNOWN'})
    for k in ('targetChecked','targetSupported','buildReportAvailable','settingsRestored'):require(type(value[k]) is bool)
    for k in ('totalErrors','totalWarnings'):require(type(value[k]) is int and 0<=value[k]<=2147483647)
    require(value['targetChecked'] or value['targetSupported'] is False)
    require(value['buildReportAvailable']==(value['buildResult']!='UNAVAILABLE'))
    if not value['buildReportAvailable']:require(value['totalErrors']==value['totalWarnings']==0)
    return value
def empty_build():return dict(native=empty_build_native(),logClassification=startup.empty_report(),failureCode='BUILD_DIAGNOSTIC_UNAVAILABLE')
def validate_build(value):
    require(isinstance(value,dict) and set(value)=={'native','logClassification','failureCode'} and value['failureCode'] in BUILD_FAILURES)
    native=validate_build_native(value['native']);startup.validate(value['logClassification'],set(startup.source_map(TASK/'unity').values()))
    if value['failureCode']=='NONE':require(native['stage']=='BUILD_RECEIPT_WRITTEN' and native['buildResult']=='SUCCEEDED' and native['targetChecked'] and native['targetSupported'] and native['settingsRestored'] and native['exceptionKind']=='NONE' and not value['logClassification']['compileErrors'])
    if value['failureCode']=='LINUX_TARGET_UNSUPPORTED':require(native['targetChecked'] and not native['targetSupported'])
    if value['failureCode']=='PROJECT_COMPILE_ERRORS':require(value['logClassification']['compileErrors'])
    return value
def record_build(logs):
    logs=safe(logs,False);native=empty_build_native()
    if (logs/'build-diagnostic-native.json').exists():native=validate_build_native(read_json(logs/'build-diagnostic-native.json'))
    classified=startup.classify(logs,TASK/'unity')
    failure='REFERENCE_BUILD_FAILED'
    if native['targetChecked'] and not native['targetSupported']:failure='LINUX_TARGET_UNSUPPORTED'
    elif classified['compileErrors']:failure='PROJECT_COMPILE_ERRORS'
    elif native['stage']=='BUILD_RECEIPT_WRITTEN' and native['buildResult']=='SUCCEEDED' and native['settingsRestored']:failure='NONE'
    value=validate_build(dict(native=native,logClassification=classified,failureCode=failure))
    EVIDENCE.mkdir(exist_ok=True);atomic(EVIDENCE/'build-diagnostic.json',value)
def fixed_control(values):
    require(len(values)==5 and all(v in {'NOT_ATTEMPTED','SUCCEEDED','FAILED'} for v in values))
    result=dict(zip(('activation','build','player','licenseReturn','privateCleanup'),values))
    result['buildDiagnostic']=validate_build(read_json(EVIDENCE/'build-diagnostic.json')) if (EVIDENCE/'build-diagnostic.json').exists() else empty_build()
    result['captureFailureCode']='NONE'
    result['containerSource']=source_diagnostic()
    if (EVIDENCE/'failure.json').exists():
        detail=read_json(EVIDENCE/'failure.json');require(set(detail)=={'failureCode'} and detail['failureCode'] in PLAYER_FAILURES);result['captureFailureCode']=detail['failureCode']
    # Only fixed-schema control is made readable. Private logs, build, handshake stay private.
    atomic(TASK/'player-control.json',result);os.chmod(safe(TASK/'player-control.json'),0o644)
    if result['player']=='SUCCEEDED':
        for name in ('summary.json','real-time.mp4','frame-0.png','frame-1.png','frame-2.png'):os.chmod(safe(EVIDENCE/name),0o644)
        os.chmod(safe(EVIDENCE,False),0o755)

def tracked_names():
    names=subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'ls-files','-z'],cwd=ROOT).decode().split('\0')
    return [n for n in names if n]
def tracked():return {n:sha(ROOT/n) for n in tracked_names()}
def declared_names():
    manifest=read_json(TASK/'SOURCE-STATE.json');require(manifest.get('schema')=='desert-rv-source-state/v1' and isinstance(manifest.get('files'),list))
    tracked_set=set(tracked_names());result=set()
    for row in manifest['files']:
        require(isinstance(row,dict) and isinstance(row.get('path'),str) and row['path'] in tracked_set and re.fullmatch('[a-f0-9]{64}',row.get('sha256','')))
        result.add(row['path'])
    return result
def empty_source():return dict(scope='SOURCE_STATE_DECLARED_FILES_ONLY',status='UNAVAILABLE',changedCount=0,truncated=False,files=[])
def validate_source(value):
    require(isinstance(value,dict) and set(value)=={'scope','status','changedCount','truncated','files'} and value['scope']=='SOURCE_STATE_DECLARED_FILES_ONLY')
    require(value['status'] in {'UNCHANGED','DIFFERENCES','UNAVAILABLE'})
    require(type(value['changedCount']) is int and value['changedCount']>=0 and type(value['truncated']) is bool and isinstance(value['files'],list) and len(value['files'])<=32)
    require(value['truncated']==(value['changedCount']>len(value['files'])))
    if value['status']!='DIFFERENCES':require(value['changedCount']==0 and value['files']==[])
    else:require(value['changedCount']>0)
    known=declared_names() if value['files'] else set();previous=''
    for row in value['files']:
        require(isinstance(row,dict) and set(row)=={'path','status','beforeSha256','afterSha256'})
        name=row['path'];require(name in known and name>previous and not pathlib.PurePosixPath(name).is_absolute() and '..' not in pathlib.PurePosixPath(name).parts);previous=name
        require(row['status'] in {'CHANGED','MISSING','UNREADABLE','ADDED'})
        for key in ('beforeSha256','afterSha256'):require(row[key] is None or isinstance(row[key],str) and re.fullmatch('[a-f0-9]{64}',row[key]))
        if row['status'] in {'MISSING','UNREADABLE'}:require(row['afterSha256'] is None)
        if row['status']=='CHANGED':require(row['beforeSha256'] is not None and row['afterSha256'] is not None and row['beforeSha256']!=row['afterSha256'])
        if row['status']=='ADDED':require(row['beforeSha256'] is None and row['afterSha256'] is not None)
    return value
def source_diagnostic():
    try:
        before=read_json(TASK/'player-source-before.json');names=sorted(declared_names());require(isinstance(before,dict) and set(before)<=set(tracked_names()))
        require(all(isinstance(v,str) and re.fullmatch('[a-f0-9]{64}',v) for v in before.values()));changes=[]
        for name in names:
            expected=before.get(name);actual=None;status=None
            try:
                file=ROOT/name
                if not file.exists():status='MISSING'
                else:actual=sha(file);status='ADDED' if expected is None else 'CHANGED' if actual!=expected else None
            except Exception:status='UNREADABLE'
            if status:changes.append(dict(path=name,status=status,beforeSha256=expected,afterSha256=actual))
        return validate_source(dict(scope='SOURCE_STATE_DECLARED_FILES_ONLY',status='DIFFERENCES' if changes else 'UNCHANGED',changedCount=len(changes),truncated=len(changes)>32,files=changes[:32]))
    except Exception:return empty_source()

def source_unchanged():require(read_json(TASK/'player-source-before.json')==tracked())
def tree_hash(root):
    records=[]
    for p in sorted(safe(root,False).rglob('*')):
        safe(p,False)
        if p.is_file():records.append((p.relative_to(root).as_posix(),sha(p)))
    require(records);return hashlib.sha256(json.dumps(records).encode()).hexdigest()
def verify_build(folder):
    folder=safe(folder,False);r=read_json(folder/'build-receipt.json')
    require(set(r)=={'mode','sourceCommit','sceneSha256','executableSha256','executable','targetSupported','buildSucceeded','settingsRestored','temporarySettingsOverridden','buildTarget','backend','candidateDefine','width','height','fullscreen'})
    require(r['mode']==MODE and r['sourceCommit']==os.environ['GITHUB_SHA'] and r['executable']=='DesertRV.x86_64')
    require(all(r[k] is True for k in ('targetSupported','buildSucceeded','settingsRestored','temporarySettingsOverridden')))
    require(r['buildTarget']=='StandaloneLinux64' and r['backend']=='Mono2x' and r['candidateDefine']=='DESERTRV_REFERENCE_WINDOW_PROBE' and r['fullscreen']=='Windowed')
    require(type(r['width']) is int and type(r['height']) is int and (r['width'],r['height'])==(1280,720))
    require(r['sceneSha256']==sha(ROOT/SCENE));exe=safe(folder/r['executable'])
    require(r['executableSha256']==sha(exe) and os.access(exe,os.X_OK));return exe,r

def verify_player(pid,exe,argv):
    require(pathlib.Path('/proc',str(pid),'exe').resolve()==exe.resolve())
    raw=pathlib.Path('/proc',str(pid),'cmdline').read_bytes()
    require(raw.endswith(b'\0') and raw[:-1].decode().split('\0')==argv)

def capture(folder,private):
    source_unchanged();exe,build=verify_build(folder);build_tree=tree_hash(folder)
    h=safe(private,False)/'handshake';h.mkdir();EVIDENCE.mkdir()
    env=dict(os.environ)
    for key in ('UNITY_LICENSE','UNITY_EMAIL','UNITY_PASSWORD','UNITY_SERIAL'):env.pop(key,None)
    env['DESERTRV_PLAYER_HANDSHAKE']=str(h)
    argv=[str(exe),'-screen-fullscreen','0','-screen-width','1280','-screen-height','720','-force-glcore','-logFile',str(private/'player.log')]
    player=None;ff=None;thread=None;frames=[0];checks=0;window=None;began=None;failure='PLAYER_STARTUP_FAILED';success=False
    started=time.monotonic()
    with (private/'player-stdout.log').open('w') as plog,(private/'ffmpeg.log').open('w') as flog:
      try:
        player=subprocess.Popen(argv,env=env,stdout=plog,stderr=plog)
        while not (h/'request.json').exists():
            require(player.poll() is None and time.monotonic()-started<60);time.sleep(.1)
        request=read_json(h/'request.json');require(set(request)=={'pid','scene'} and request['pid']==player.pid and request['scene']=='BodyStudy')
        verify_player(player.pid,exe,argv);failure='PLAYER_WINDOW_FAILED';until=time.monotonic()+15
        while time.monotonic()<until:
            found=subprocess.run(['xdotool','search','--onlyvisible','--name','^'+TITLE+'$'],capture_output=True,text=True).stdout.split()
            require(len(found)<=1)
            if found:window=found[0];require(identity(window,TITLE,player.pid)==(1280,720));break
            time.sleep(.1)
        require(window is not None)
        subprocess.run(['xdotool','windowactivate','--sync',window],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
        until=time.monotonic()+5
        while not (h/'frame.json').exists() or read_json(h/'frame.json').get('focused') is not True:
            require(player.poll() is None and time.monotonic()<until);time.sleep(.1)
        began=stamp();video=EVIDENCE/'real-time.mp4';failure='PLAYER_CAPTURE_FAILED'
        ff=subprocess.Popen(['ffmpeg','-y','-f','x11grab','-window_id',window,'-framerate','30','-i',os.environ['DISPLAY'],'-c:v','libx264','-preset','ultrafast','-crf','23','-pix_fmt','yuv420p','-progress','pipe:1',str(video)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=flog,text=True)
        def progress():
            for line in ff.stdout:
                if line.startswith('frame='):frames[0]=int(line.split('=',1)[1])
        thread=threading.Thread(target=progress,daemon=True);thread.start()
        last_video=0;last_frame=-1;last_wall=-1;last_change=time.monotonic();last_encoded=time.monotonic();ready=False
        while True:
            now=time.monotonic();require(now-started<100 and player.poll() is None and ff.poll() is None)
            verify_player(player.pid,exe,argv);require(identity(window,TITLE,player.pid)==(1280,720));checks+=1
            require(subprocess.check_output(['xdotool','getactivewindow'],text=True,stderr=subprocess.DEVNULL).strip()==window)
            if frames[0]>last_video:last_video=frames[0];last_encoded=now
            require(now-last_encoded<5)
            beat=read_json(h/'frame.json');require(set(beat)=={'frame','wall','focused'})
            require(type(beat['frame']) is int and type(beat['wall']) in (int,float) and beat['wall']>=last_wall and beat['focused'] is True)
            require(beat['frame']>=last_frame)
            if beat['frame']>last_frame:last_change=now;last_frame=beat['frame'];last_wall=beat['wall']
            require(now-last_change<3)
            if not ready and frames[0]>0:atomic(h/'ready.json',{'ready':True});ready=True
            if (h/'duration-complete.json').exists():
                require(ready and read_json(h/'duration-complete.json')=={'seconds':15,'screenshots':3});break
            time.sleep(.1)
        code,method,error=finish_encoder(ff);ff=None;require(code==0 and method=='stdin-q' and error is None)
        thread.join(timeout=1);atomic(h/'stopped.json',{'stopped':True});require(player.wait(timeout=15)==0)
        require(tree_hash(folder)==build_tree);source_unchanged()
        for i in range(3):inspect_png(h/f'frame-{i}.png',(1280,720));shutil.copyfile(h/f'frame-{i}.png',EVIDENCE/f'frame-{i}.png')
        video_info=probe_video(video);stream=video_info['streams'][0];duration=float(video_info['format']['duration'])
        require(15<=duration<=22 and stream['width']==1280 and stream['height']==720 and stream['r_frame_rate']=='30/1' and stream['avg_frame_rate']=='30/1')
        summary=dict(mode=MODE,sourceCommit=os.environ['GITHUB_SHA'],candidateOnly=True,humanPlaytest=False,gameplayAccepted=False,androidVerified=False,visualReviewed=False,inputsApplied=False,sourceVerified=True,durationSeconds=duration,nominalCaptureFps=30,encodedFrameRate=stream['r_frame_rate'],averageFrameRate=stream['avg_frame_rate'],captureStartUtc=began,captureEndUtc=stamp(),identityChecks=checks,encodedProgressFrames=frames[0],windowId=window,playerPid=player.pid,playerExecutableSha256=build['executableSha256'],buildTreeSha256=build_tree,sceneSha256=build['sceneSha256'],playerExitCode=0,encoderExitCode=0,encoderStopMethod='stdin-q',screenshots=3)
        atomic(EVIDENCE/'summary.json',summary);success=True;return 0
      except Exception:
        atomic(EVIDENCE/'failure.json',{'failureCode':failure});return 1
      finally:
        if ff is not None:finish_encoder(ff)
        if player is not None and player.poll() is None:
            player.terminate()
            try:player.wait(timeout=5)
            except subprocess.TimeoutExpired:player.kill();player.wait()
        if not success:
            # No failed video or screenshots will ever be exported.
            for p in EVIDENCE.glob('*.mp4'):p.unlink()

def export():
    require(not PUBLIC.exists());stage=pathlib.Path(tempfile.mkdtemp(prefix='player-export-',dir=TASK));success=False
    try:
        c=read_json(TASK/'player-control.json')
        require(set(c)=={'activation','build','player','licenseReturn','privateCleanup','buildDiagnostic','captureFailureCode','containerSource'})
        validate_build(c['buildDiagnostic']);validate_source(c['containerSource']);require(c['captureFailureCode'] in PLAYER_FAILURES|{'NONE'})
        states=[c[k] for k in ('activation','build','player','licenseReturn','privateCleanup')]
        allowed={'NOT_ATTEMPTED','SUCCEEDED','FAILED'};require(all(v in allowed for v in states))
        ok=os.environ.get('NATIVE_OUTCOME')=='success' and all(v=='SUCCEEDED' for v in states) and c['captureFailureCode']=='NONE' and c['buildDiagnostic']['failureCode']=='NONE'
        try:source_unchanged();preserved=True
        except Exception:preserved=False
        ok=ok and preserved
        if ok:
            s=read_json(EVIDENCE/'summary.json');require(s['mode']==MODE and s['sourceCommit']==os.environ['GITHUB_SHA'] and s['sourceVerified'] is True)
            # Output schema is exact; no unknown producer fields can become public.
            keys={'mode','sourceCommit','candidateOnly','humanPlaytest','gameplayAccepted','androidVerified','visualReviewed','inputsApplied','sourceVerified','durationSeconds','nominalCaptureFps','encodedFrameRate','averageFrameRate','captureStartUtc','captureEndUtc','identityChecks','encodedProgressFrames','windowId','playerPid','playerExecutableSha256','buildTreeSha256','sceneSha256','playerExitCode','encoderExitCode','encoderStopMethod','screenshots'}
            require(set(s)==keys)
            require(s['candidateOnly'] is True and all(s[k] is False for k in ('humanPlaytest','gameplayAccepted','androidVerified','visualReviewed','inputsApplied')))
            require(type(s['playerExitCode']) is int and type(s['encoderExitCode']) is int and s['playerExitCode']==0 and s['encoderExitCode']==0 and s['encoderStopMethod']=='stdin-q' and s['screenshots']==3 and s['nominalCaptureFps']==30)
            require(all(re.fullmatch('[a-f0-9]{64}',s[k]) for k in ('playerExecutableSha256','buildTreeSha256','sceneSha256')))
            require(s['sceneSha256']==sha(ROOT/SCENE))
            for key in ('identityChecks','encodedProgressFrames','playerPid'):
                require(type(s[key]) is int and s[key]>0)
            require(isinstance(s['windowId'],str) and re.fullmatch('[0-9]+',s['windowId']))
            require(s['encodedFrameRate']==s['averageFrameRate']=='30/1')
            require(type(s['durationSeconds']) in (int,float) and math.isfinite(s['durationSeconds']))
            start=datetime.datetime.fromisoformat(s['captureStartUtc']);end=datetime.datetime.fromisoformat(s['captureEndUtc'])
            require(start.tzinfo is not None and end.tzinfo is not None and 15<=(end-start).total_seconds()<=40)
            require(len(s['captureStartUtc'])<=40 and len(s['captureEndUtc'])<=40)
            for i in range(3):inspect_png(EVIDENCE/f'frame-{i}.png',(1280,720))
            info=probe_video(EVIDENCE/'real-time.mp4');st=info['streams'][0];seconds=float(info['format']['duration'])
            require(15<=seconds<=22 and seconds==s['durationSeconds'] and st['width']==1280 and st['height']==720 and st['r_frame_rate']==st['avg_frame_rate']=='30/1')
            atomic(stage/'summary.json',s)
            for n in ['real-time.mp4','frame-0.png','frame-1.png','frame-2.png']:shutil.copyfile(safe(EVIDENCE/n),stage/n)
            atomic(stage/'sha256.json',{p.name:sha(p) for p in stage.iterdir()})
        else:
            failure='NATIVE_PROCESS_NOT_SUCCESS'
            if c['buildDiagnostic']['failureCode']!='NONE':failure=c['buildDiagnostic']['failureCode']
            if c['captureFailureCode']!='NONE':failure=c['captureFailureCode']
            if not preserved:failure='SOURCE_PRESERVATION_FAILED'
            atomic(stage/'status.json',dict(mode=MODE,status='FAILED_NOT_ACCEPTED',failureCode=failure,videoExported=False,sourcePreserved=preserved,hostSource=source_diagnostic(),control=c))
        os.replace(stage,PUBLIC);success=True
    finally:
        if not success:shutil.rmtree(stage)
    with open(os.environ['GITHUB_OUTPUT'],'a') as output:output.write('export_ready=true\n')

def main():
    try:
        command=sys.argv[1]
        if command=='before':
            require(not PUBLIC.exists() and not EVIDENCE.exists() and not (TASK/'player-control.json').exists());atomic(TASK/'player-source-before.json',tracked())
        elif command=='build-diagnostic':record_build(pathlib.Path(sys.argv[2]))
        elif command=='capture':return capture(pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]))
        elif command=='control':
            fixed_control(sys.argv[2:])
        elif command=='export':export()
        else:raise ValueError()
    except Exception:print('PLAYER_SMOKE_FIXED_VALIDATION_FAILED');return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
