#!/usr/bin/env python3
"""Observe a verified producer binary. No Editor, input injection or state access."""
import contextlib,datetime,hashlib,json,os,pathlib,re,shutil,subprocess,sys,tarfile,tempfile,threading,time,zipfile
import journey_linux_export as bundle
from capture_game_window import atomic,identity,finish_encoder,stamp
from prepare_safe_diagnostic_export import safe,sha,require,inspect_png,probe_video
ROOT=pathlib.Path(__file__).resolve().parents[4];TASK=ROOT/'tasks/desert-rv'
SOURCE=TASK/'player-observer-source';WORK=TASK/'player-observer-work';RESULT=WORK/'result';PUBLIC=WORK/'public'
PREPARE_WORKFLOW='.github/workflows/desert-rv-journey-prepare.yml';REBUILD_WORKFLOW='.github/workflows/desert-rv-journey-rebuild.yml'
TITLE='DESERTRV_JOURNEY_CANDIDATE';REPO='yangerstar1/task-workbench'
PACKAGE_FILES={'manifest.json','native-build-receipt.json','player.tar.gz','control.json'}
STAGES={'START','ARTIFACT_VERIFIED','BUNDLE_VERIFIED','EXTRACTED','PLAYER_SPAWNED','WINDOW_VERIFIED','FIRST_ENCODED_FRAME','DURATION_COMPLETE','ENCODER_STOPPED','MEDIA_VERIFIED'}
FAILURES={'NONE','ARTIFACT_API','ARTIFACT_HASH','PACKAGE_SCHEMA','BUNDLE_HASH','BUNDLE_CLOSURE','EXTRACTION','DISPLAY_UNAVAILABLE','PLAYER_SPAWN','PLAYER_STARTUP','WINDOW_AMBIGUOUS','WINDOW_IDENTITY','WINDOW_FOCUS','ENCODER_START','ENCODER_HEARTBEAT','PLAYER_EXITED','ENCODER_STOP','MEDIA_INVALID','PLAYER_SHUTDOWN','BUNDLE_CHANGED','PRIVATE_CLEANUP','INTERNAL_VALIDATION','OBSERVER_PROCESS_NOT_SUCCESS'}
OBSERVED={'stage':'START','failureCode':'INTERNAL_VALIDATION'}
def mark(stage,failure):
    require(stage in STAGES and failure in FAILURES);OBSERVED.update(stage=stage,failureCode=failure)
MANIFEST_KEYS={'schema','label','sourceCommit','producerRunUrl','nativeReceiptSha256','inputSha256','generatedReceiptSha256','sourceStateSha256','bundleSha256','bundleBytes','files','nativeReceipt','playerExecuted','approved'}

def strict_json(raw):
    require(len(raw)<=16*1024**2)
    def unique(pairs):
        result={}
        for k,v in pairs:require(k not in result);result[k]=v
        return result
    return json.loads(raw,object_pairs_hook=unique)
def read(path):return strict_json(safe(path).read_bytes())
def pins():
    values={k:os.environ[k] for k in ('PRODUCER_RUN_ID','PRODUCER_COMMIT','PRODUCER_ARTIFACT_ID','PRODUCER_ZIP_SHA256')}
    for k in ('PRODUCER_RUN_ID','PRODUCER_ARTIFACT_ID'):require(re.fullmatch('[1-9][0-9]*',values[k]) is not None)
    require(re.fullmatch('[a-f0-9]{40}',values['PRODUCER_COMMIT']) is not None and re.fullmatch('[a-f0-9]{64}',values['PRODUCER_ZIP_SHA256']) is not None)
    return values
@contextlib.contextmanager
def producer_environment(p):
    # Reuse strict receipt validation against the producer, without relabeling the observer.
    keys={'GITHUB_SHA':p['PRODUCER_COMMIT'],'GITHUB_RUN_ID':p['PRODUCER_RUN_ID']};old={k:os.environ.get(k) for k in keys}
    try:os.environ.update(keys);yield
    finally:
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v

def validate_package(folder,p):
    require({f.name for f in safe(folder,False).iterdir()}==PACKAGE_FILES)
    for f in folder.iterdir():safe(f);require(f.is_file())
    m=read(folder/'manifest.json');require(isinstance(m,dict) and set(m)==MANIFEST_KEYS)
    require(m['schema']==1 and m['label']=='REUSABLE_CANDIDATE_LINUX_PLAYER_UNREVIEWED' and m['sourceCommit']==p['PRODUCER_COMMIT'] and m['producerRunUrl']=='https://github.com/'+REPO+'/actions/runs/'+p['PRODUCER_RUN_ID'] and m['playerExecuted'] is False and m['approved'] is False)
    for key in ('nativeReceiptSha256','inputSha256','generatedReceiptSha256','sourceStateSha256','bundleSha256'):require(isinstance(m[key],str) and re.fullmatch('[a-f0-9]{64}',m[key]) is not None)
    with producer_environment(p):
        raw,native=bundle.sealed_native_receipt(folder/'native-build-receipt.json');require(hashlib.sha256(raw).hexdigest()==m['nativeReceiptSha256'] and native==m['nativeReceipt'])
    require(native['requestSha256']==m['inputSha256'] and native['generatedReceiptSha256']==m['generatedReceiptSha256'])
    c=read(folder/'control.json');require(set(c)=={'schema','mode','activation','build','licenseReturn','privateCleanup','buildDiagnostic','sourceRecovery','hostDiagnostic'} and c['schema']==1 and c['mode']=='JOURNEY_LINUX_BUILD_CONTROL')
    bundle.validate_host(c['hostDiagnostic']);require(c['hostDiagnostic']['failurePhase']=='NONE')
    pin=c['hostDiagnostic']['nativeReceiptPin']
    if pin is not None:require(pin==dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    require(all(c[k]=='SUCCEEDED' for k in ('activation','build','licenseReturn','privateCleanup')))
    # Control is inspected privately. It is never republished by this observer.
    d=c['buildDiagnostic'];require(d['batchExitCode']==0 and d['batchTimedOut'] is False);bundle.native_diagnostic(d['native']);require(bundle.diagnostic_success(d['native']))
    require(c['sourceRecovery']['status']=='SUCCEEDED' and c['sourceRecovery']['sourceModesRestored'] is True and c['sourceRecovery']['afterPreserved'] is True)
    require(type(m['bundleBytes']) is int and 0<m['bundleBytes']<=8*1024**3 and (folder/'player.tar.gz').stat().st_size==m['bundleBytes'] and sha(folder/'player.tar.gz')==m['bundleSha256'])
    bundle.validate_records(m['files']);require(next(r['sha256'] for r in m['files'] if r['path']=='DesertRV.x86_64')==native['executableSha256']);bundle.verify_tar(folder/'player.tar.gz',m['files'])
    return m

def package_workflow(m):
    pin=m['nativeReceipt']['restorationProof']
    return REBUILD_WORKFLOW if isinstance(pin,dict) and pin.get('path') else PREPARE_WORKFLOW

def validate_producer_workflow(path,m):
    require(path in {PREPARE_WORKFLOW,REBUILD_WORKFLOW} and path==package_workflow(m));native=m['nativeReceipt']
    if path==REBUILD_WORKFLOW:
        pin=native['restorationProof'];require(isinstance(pin,dict) and set(pin)=={'path','sha256'} and pin['path']=='tasks/desert-rv/unity/JourneyEvidence/JourneyPreparation/restoration-revalidated.json' and re.fullmatch('[a-f0-9]{64}',pin['sha256']))
        require(re.fullmatch('[a-f0-9]{40}',native['assetProducerSourceCommit']) and re.fullmatch(r'https://github\.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]*',native['assetProducerRunUrl']) and native['assetProducerRunUrl']!=m['producerRunUrl'])
        require(re.fullmatch('[a-f0-9]{64}',native['restorationNativeXmlSha256']))
    else:
        require(native['restorationProof'] is None or native['restorationProof']=={'path':'','sha256':''})
        require(all(native[k] in ('',None) for k in ('assetProducerSourceCommit','assetProducerRunUrl','restorationNativeXmlSha256')))

def verify_stage_receipt(p,m):
    v=read(SOURCE/'verified.json');require(set(v)=={'schema','pins','manifestSha256','executableSha256','producerWorkflowPath'} and v['schema']==1 and v['pins']==p and v['manifestSha256']==sha(SOURCE/'package/manifest.json') and v['executableSha256']==m['nativeReceipt']['executableSha256']);validate_producer_workflow(v['producerWorkflowPath'],m)

def unpack_zip(archive,destination):
    require(not destination.exists());destination.mkdir()
    with zipfile.ZipFile(safe(archive)) as z:
        rows=z.infolist();require(len(rows)==4 and {r.filename for r in rows}==PACKAGE_FILES)
        for row in rows:
            limit={'manifest.json':16*1024**2,'native-build-receipt.json':32768,'control.json':1024**2,'player.tar.gz':8*1024**3}[row.filename]
            require(not row.is_dir() and ((row.external_attr>>16)&0o170000) in {0,0o100000} and 0<=row.file_size<=limit)
            with z.open(row) as src,(destination/row.filename).open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)

def extract_runtime(folder,destination,m):
    require(not destination.exists());bundle.verify_tar(folder/'player.tar.gz',m['files']);destination.mkdir()
    with tarfile.open(folder/'player.tar.gz','r:gz') as archive:
        expected={r['path']:r for r in m['files']}
        for member in archive:
            row=expected[member.name];target=destination/member.name;safe(target,False);target.parent.mkdir(parents=True,exist_ok=True)
            with archive.extractfile(member) as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
            require(sha(target)==row['sha256']);target.chmod(row['mode'])
    require(bundle.inventory(destination)==m['files'])

def api(endpoint):
    result=subprocess.run(['gh','api','repos/'+REPO+endpoint],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,check=True,timeout=60)
    return strict_json(result.stdout)
def stage():
    p=pins();require(not SOURCE.exists());temp=pathlib.Path(tempfile.mkdtemp(prefix='observer-source-',dir=TASK));ok=False
    try:
        mark('START','ARTIFACT_API');run=api('/actions/runs/'+p['PRODUCER_RUN_ID']);artifact=api('/actions/artifacts/'+p['PRODUCER_ARTIFACT_ID'])
        require(run['status']=='completed' and run['conclusion']=='success' and run['head_sha']==p['PRODUCER_COMMIT'] and run['path'] in {PREPARE_WORKFLOW,REBUILD_WORKFLOW})
        require(artifact['workflow_run']['id']==int(p['PRODUCER_RUN_ID']) and artifact['workflow_run']['head_sha']==p['PRODUCER_COMMIT'] and artifact['expired'] is False and artifact['digest']=='sha256:'+p['PRODUCER_ZIP_SHA256'] and 0<artifact['size_in_bytes']<=8*1024**3)
        require(artifact['name']=='journey-linux-CANDIDATE-NOT-PLAYTESTED-'+p['PRODUCER_RUN_ID']+'-'+str(run['run_attempt']))
        mark('START','ARTIFACT_HASH')
        with (temp/'producer.zip').open('wb') as out:subprocess.run(['gh','api','repos/'+REPO+'/actions/artifacts/'+p['PRODUCER_ARTIFACT_ID']+'/zip'],stdout=out,stderr=subprocess.DEVNULL,check=True,timeout=300)
        require((temp/'producer.zip').stat().st_size==artifact['size_in_bytes'] and sha(temp/'producer.zip')==p['PRODUCER_ZIP_SHA256'])
        mark('ARTIFACT_VERIFIED','PACKAGE_SCHEMA');unpack_zip(temp/'producer.zip',temp/'package')
        mark('ARTIFACT_VERIFIED','BUNDLE_CLOSURE');m=validate_package(temp/'package',p);validate_producer_workflow(run['path'],m)
        mark('BUNDLE_VERIFIED','EXTRACTION');extract_runtime(temp/'package',temp/'runtime',m)
        atomic(temp/'verified.json',dict(schema=1,pins=p,producerWorkflowPath=run['path'],manifestSha256=sha(temp/'package/manifest.json'),executableSha256=m['nativeReceipt']['executableSha256']));os.replace(temp,SOURCE);ok=True
    finally:
        if not ok:shutil.rmtree(temp)

def process_identity(player,exe,argv):
    require(player.poll() is None and pathlib.Path('/proc/'+str(player.pid)+'/exe').resolve()==exe.resolve())
    require(pathlib.Path('/proc/'+str(player.pid)+'/cmdline').read_bytes()==b'\0'.join(a.encode() for a in argv)+b'\0')
def metadata(p,m):
    return dict(schema=1,label='CANDIDATE_PLAYER_WINDOW_OBSERVATION_UNREVIEWED',producerSourceCommit=p['PRODUCER_COMMIT'],producerRunUrl='https://github.com/'+REPO+'/actions/runs/'+p['PRODUCER_RUN_ID'],producerWorkflowPath=package_workflow(m),assetProducerSourceCommit=m['nativeReceipt']['assetProducerSourceCommit'] or '',assetProducerRunUrl=m['nativeReceipt']['assetProducerRunUrl'] or '',restorationProofSha256=(m['nativeReceipt']['restorationProof'] or {}).get('sha256',''),restorationNativeXmlSha256=m['nativeReceipt']['restorationNativeXmlSha256'] or '',observerSourceCommit=os.environ['GITHUB_SHA'],observerRunUrl='https://github.com/'+REPO+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],producerArtifactId=int(p['PRODUCER_ARTIFACT_ID']),producerZipSha256=p['PRODUCER_ZIP_SHA256'],manifestSha256=sha(SOURCE/'package/manifest.json'),bundleSha256=m['bundleSha256'],executableSha256=m['nativeReceipt']['executableSha256'],inputsApplied=False,gameStateTelemetry='NOT_AVAILABLE',engineFrameHeartbeat='NOT_AVAILABLE',visualReviewed=False,gameplayAccepted=False,androidVerified=False)

def capture():
    WORK.mkdir(exist_ok=True);mark('START','BUNDLE_HASH');p=pins();require(sha(SOURCE/'producer.zip')==p['PRODUCER_ZIP_SHA256']);m=validate_package(SOURCE/'package',p);verify_stage_receipt(p,m);require(bundle.inventory(SOURCE/'runtime')==m['files']);require(not RESULT.exists())
    private=pathlib.Path(tempfile.mkdtemp(prefix='observer-private-',dir=WORK));media=private/'media';media.mkdir();logs=private/'logs';logs.mkdir()
    stage='EXTRACTED';failure='DISPLAY_UNAVAILABLE';player=ff=xvfb=wm=None;thread=None;frames=[0];window=None;started=None;ended=None;checks=0;code=None;encoder_code=None;termination='NONE';success=False
    result=metadata(p,m)
    try:
        env={k:v for k,v in os.environ.items() if k not in {'UNITY_LICENSE','UNITY_EMAIL','UNITY_PASSWORD','UNITY_SERIAL','GH_TOKEN','GITHUB_TOKEN'}};env['DISPLAY']=':91';env['HOME']=str(private/'home');pathlib.Path(env['HOME']).mkdir()
        with (logs/'xvfb.log').open('w') as log:xvfb=subprocess.Popen(['Xvfb',env['DISPLAY'],'-screen','0','1600x1000x24','-nolisten','tcp'],env=env,stdout=log,stderr=log)
        until=time.monotonic()+10
        while subprocess.run(['xdpyinfo','-display',env['DISPLAY']],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env).returncode!=0:require(xvfb.poll() is None and time.monotonic()<until);time.sleep(.1)
        with (logs/'wm.log').open('w') as log:wm=subprocess.Popen(['openbox','--sm-disable'],env=env,stdout=log,stderr=log)
        exe=SOURCE/'runtime/DesertRV.x86_64';argv=[str(exe),'-screen-fullscreen','0','-screen-width','1280','-screen-height','720','-force-glcore','-logFile',str(logs/'player.log')]
        failure='PLAYER_SPAWN'
        with (logs/'player-stdout.log').open('w') as log:player=subprocess.Popen(argv,env=env,cwd=SOURCE/'runtime',stdout=log,stderr=log)
        stage='PLAYER_SPAWNED';failure='PLAYER_STARTUP';until=time.monotonic()+60
        while window is None:
            process_identity(player,exe,argv);require(time.monotonic()<until)
            found=subprocess.run(['xdotool','search','--onlyvisible','--name','^'+TITLE+'$'],capture_output=True,text=True,env=env,timeout=3).stdout.split()
            failure='WINDOW_AMBIGUOUS';require(len(found)<=1)
            if found:window=found[0]
            else:failure='PLAYER_STARTUP';time.sleep(.1)
        # Existing identity helper reads DISPLAY from environment, only within this process.
        os.environ['DISPLAY']=env['DISPLAY'];failure='WINDOW_IDENTITY';require(identity(window,TITLE,player.pid)==(1280,720));stage='WINDOW_VERIFIED'
        failure='WINDOW_FOCUS';subprocess.run(['xdotool','windowactivate','--sync',window],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=5)
        failure='ENCODER_START';started=stamp()
        with (logs/'encoder.log').open('w') as log:ff=subprocess.Popen(['ffmpeg','-y','-f','x11grab','-window_id',window,'-framerate','30','-i',env['DISPLAY'],'-c:v','libx264','-preset','ultrafast','-crf','23','-pix_fmt','yuv420p','-progress','pipe:1',str(media/'real-time.mp4')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,env=env)
        def progress():
            for line in ff.stdout:
                if re.fullmatch(r'frame=[0-9]+\n',line):frames[0]=int(line.split('=',1)[1])
        thread=threading.Thread(target=progress,daemon=True);thread.start();first=None;last=0;last_change=time.monotonic()
        while True:
            now=time.monotonic();failure='PLAYER_EXITED';process_identity(player,exe,argv)
            failure='WINDOW_IDENTITY';require(identity(window,TITLE,player.pid)==(1280,720));checks+=1
            failure='WINDOW_FOCUS';require(subprocess.check_output(['xdotool','getactivewindow'],text=True,stderr=subprocess.DEVNULL,env=env,timeout=3).strip()==window)
            failure='ENCODER_HEARTBEAT';require(ff.poll() is None)
            if frames[0]>last:last=frames[0];last_change=now
            require(now-last_change<5)
            if first is None and frames[0]>0:first=now;stage='FIRST_ENCODED_FRAME'
            if first is not None and now-first>=15:stage='DURATION_COMPLETE';break
            time.sleep(.1)
        failure='ENCODER_STOP';encoder_code,method,error=finish_encoder(ff);ff=None;require(encoder_code==0 and method=='stdin-q' and error is None);thread.join(timeout=1);ended=stamp();stage='ENCODER_STOPPED'
        failure='MEDIA_INVALID';info=probe_video(media/'real-time.mp4');stream=info['streams'][0];seconds=float(info['format']['duration'])
        require(15<=seconds<=22 and stream['width']==1280 and stream['height']==720 and stream['r_frame_rate']==stream['avg_frame_rate']=='30/1')
        for i,offset in enumerate((0,5,10)):
            subprocess.run(['ffmpeg','-v','error','-ss',str(offset),'-i',str(media/'real-time.mp4'),'-frames:v','1',str(media/('frame-'+str(i)+'.png'))],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=15);inspect_png(media/('frame-'+str(i)+'.png'),(1280,720))
        stage='MEDIA_VERIFIED';failure='BUNDLE_CHANGED';require(bundle.inventory(SOURCE/'runtime')==m['files']);validate_package(SOURCE/'package',p)
        success=True;failure='NONE';result.update(captureStartUtc=started,captureEndUtc=ended,durationSeconds=seconds,captureFps=30,encodedFrameRate=stream['r_frame_rate'],averageFrameRate=stream['avg_frame_rate'],encodedFrames=frames[0],identityChecks=checks,windowId=window,playerPid=player.pid)
    except Exception:success=False
    finally:
        if ff is not None:finish_encoder(ff)
        if player is not None:
            if player.poll() is None:
                termination='OBSERVER_TERM';player.terminate()
                try:code=player.wait(timeout=10)
                except subprocess.TimeoutExpired:termination='OBSERVER_KILL';player.kill();code=player.wait();failure='PLAYER_SHUTDOWN';success=False
            else:
                code=player.returncode
                if success:failure='PLAYER_EXITED';success=False
        for proc in (wm,xvfb):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
        try:shutil.rmtree(logs);shutil.rmtree(private/'home') if (private/'home').exists() else None
        except Exception:failure='PRIVATE_CLEANUP';success=False
    bundle_preserved=False
    try:
        require(sha(SOURCE/'producer.zip')==p['PRODUCER_ZIP_SHA256']);validate_package(SOURCE/'package',p);bundle_preserved=True
    except Exception:failure='BUNDLE_CHANGED';success=False
    require(stage in STAGES and failure in FAILURES)
    result.update(stage=stage,failureCode=failure,success=success,playerExitCode=code,playerTerminationRequest=termination,encoderExitCode=encoder_code,producerBundlePreserved=bundle_preserved,rawLogsExported=False)
    public=pathlib.Path(tempfile.mkdtemp(prefix='observer-export-',dir=WORK));committed=False
    try:
        if success:
            for name in ('real-time.mp4','frame-0.png','frame-1.png','frame-2.png'):shutil.copyfile(safe(media/name),public/name)
        try:shutil.rmtree(private)
        except Exception:
            result.update(failureCode='PRIVATE_CLEANUP',success=False);success=False
            for file in public.iterdir():file.unlink()
        atomic(public/'status.json',result);atomic(public/'sha256.json',{p.name:sha(p) for p in public.iterdir()})
        for file in public.iterdir():file.chmod(0o644)
        public.chmod(0o755);os.replace(public,RESULT);committed=True
    finally:
        if not committed:shutil.rmtree(public)
    return 0 if success else 1

def export():
    require(not PUBLIC.exists());WORK.mkdir(exist_ok=True);stage=pathlib.Path(tempfile.mkdtemp(prefix='observer-public-',dir=WORK));success=False
    minimal=dict(schema=1,label='CANDIDATE_PLAYER_OBSERVER_FAILED',success=False,stage='START',failureCode='INTERNAL_VALIDATION',rawLogsExported=False)
    try:
        try:
            original_pins=read(RESULT/'sha256.json');require(isinstance(original_pins,dict) and 'status.json' in original_pins)
            allowed={'status.json','real-time.mp4','frame-0.png','frame-1.png','frame-2.png'}
            require(set(original_pins)<=allowed and {p.name for p in safe(RESULT,False).iterdir()}==set(original_pins)|{'sha256.json'})
            for name,digest in original_pins.items():require(isinstance(digest,str) and re.fullmatch('[a-f0-9]{64}',digest) is not None and sha(RESULT/name)==digest)
            status_bytes=safe(RESULT/'status.json').read_bytes();require(hashlib.sha256(status_bytes).hexdigest()==original_pins['status.json']);s=strict_json(status_bytes);require(s['schema']==1 and type(s['success']) is bool and s['stage'] in STAGES and s['failureCode'] in FAILURES and s['rawLogsExported'] is False)
            if s['label']=='CANDIDATE_PLAYER_OBSERVER_FAILED':require(set(s)==set(minimal) and s['success'] is False)
            else:
                p=pins();m=validate_package(SOURCE/'package',p);verify_stage_receipt(p,m);expected=metadata(p,m)
                fixed={'stage','failureCode','success','playerExitCode','playerTerminationRequest','encoderExitCode','producerBundlePreserved','rawLogsExported'}
                measured={'captureStartUtc','captureEndUtc','durationSeconds','captureFps','encodedFrameRate','averageFrameRate','encodedFrames','identityChecks','windowId','playerPid'}
                require(set(s)==set(expected)|fixed|(measured if 'durationSeconds' in s else set()) and all(s[k]==v for k,v in expected.items()))
                require(type(s['producerBundlePreserved']) is bool and s['playerTerminationRequest'] in {'NONE','OBSERVER_TERM','OBSERVER_KILL'})
                for key in ('playerExitCode','encoderExitCode'):require(s[key] is None or type(s[key]) is int and -255<=s[key]<=255)
                if 'durationSeconds' in s:
                    for key in ('durationSeconds','encodedFrames','identityChecks','playerPid'):require(type(s[key]) in (int,float) and __import__('math').isfinite(s[key]) and s[key]>0)
                    require(s['captureFps']==30 and s['encodedFrameRate']==s['averageFrameRate']=='30/1' and re.fullmatch('[0-9]+',s['windowId']))
                    a=datetime.datetime.fromisoformat(s['captureStartUtc']);b=datetime.datetime.fromisoformat(s['captureEndUtc']);require(a.tzinfo and b.tzinfo and 15<=(b-a).total_seconds()<=35 and len(s['captureStartUtc'])<=40 and len(s['captureEndUtc'])<=40)
                if s['success']:
                    require(s['producerBundlePreserved'] is True and s['failureCode']=='NONE' and s['stage']=='MEDIA_VERIFIED' and 'durationSeconds' in s and s['encoderExitCode']==0 and s['playerTerminationRequest']=='OBSERVER_TERM' and s['playerExitCode'] in (0,-15))
                    require(set(original_pins)==allowed)
                    for i in range(3):inspect_png(RESULT/('frame-'+str(i)+'.png'),(1280,720))
                    info=probe_video(RESULT/'real-time.mp4');st=info['streams'][0];require(15<=float(info['format']['duration'])<=22 and float(info['format']['duration'])==s['durationSeconds'] and st['width']==1280 and st['height']==720 and st['r_frame_rate']==st['avg_frame_rate']=='30/1')
            if s['success'] and os.environ.get('NATIVE_OUTCOME')!='success':s.update(success=False,failureCode='OBSERVER_PROCESS_NOT_SUCCESS')
            if s['success']:
                for name in ('real-time.mp4','frame-0.png','frame-1.png','frame-2.png'):
                    shutil.copyfile(safe(RESULT/name),stage/name);require(sha(stage/name)==original_pins[name])
                require(sha(RESULT/'status.json')==original_pins['status.json'])
            atomic(stage/'status.json',s)
        except Exception:
            for path in stage.iterdir():path.unlink()
            atomic(stage/'status.json',minimal)
        atomic(stage/'sha256.json',{p.name:sha(p) for p in stage.iterdir()});os.replace(stage,PUBLIC);success=True
        with open(os.environ['GITHUB_OUTPUT'],'a') as output:output.write('export_ready=true\n')
    finally:
        if not success:shutil.rmtree(stage)

def main():
    try:
        require(sys.argv[1:] in (['stage'], ['capture'], ['export']))
        import journey_observer_dispatch
        journey_observer_dispatch.verify_runtime(ROOT, os.environ)
        if sys.argv[1]=='export':export();return 0
        if sys.argv[1]=='stage':stage();return 0
        if sys.argv[1]=='capture':return capture()
        raise ValueError()
    except Exception:
        try:
            WORK.mkdir(exist_ok=True)
            if not RESULT.exists():
                RESULT.mkdir();atomic(RESULT/'status.json',dict(schema=1,label='CANDIDATE_PLAYER_OBSERVER_FAILED',success=False,stage=OBSERVED['stage'],failureCode=OBSERVED['failureCode'],rawLogsExported=False));atomic(RESULT/'sha256.json',{'status.json':sha(RESULT/'status.json')});(RESULT/'status.json').chmod(0o644);(RESULT/'sha256.json').chmod(0o644);RESULT.chmod(0o755)
        except Exception:pass
        print('PLAYER_OBSERVER_FIXED_FAILURE');return 1
if __name__=='__main__':raise SystemExit(main())
