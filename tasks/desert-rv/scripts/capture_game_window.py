#!/usr/bin/env python3
"""Capture one verified Unity GameView drawable, never the desktop. No fallback."""
import argparse, datetime, hashlib, json, os, pathlib, re, signal, subprocess, threading, time

def stamp(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(path, obj):
    tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(obj)); os.replace(tmp,path)
def alive(pid):
    try: os.kill(pid,0); return True
    except ProcessLookupError: return False

def identity(window, title, pid):
    props=subprocess.check_output(['xprop','-id',window,'WM_NAME','_NET_WM_NAME','_NET_WM_PID'],text=True,stderr=subprocess.DEVNULL)
    p=re.search(r'_NET_WM_PID\([^)]*\)\s*=\s*([0-9]+)',props)
    names=re.findall(r'(?:^|\n)(?:WM_NAME|_NET_WM_NAME)\([^)]*\)\s*=\s*"([^"\n]*)"',props)
    if not p or int(p.group(1))!=pid or not names or any(n!=title for n in names): raise RuntimeError('window-identity')
    info=subprocess.check_output(['xwininfo','-id',window],text=True,stderr=subprocess.DEVNULL)
    if 'Map State: IsViewable' not in info: raise RuntimeError('window-not-viewable')
    size=tuple(int(re.search(r'\b'+k+r':\s*([0-9]+)',info).group(1)) for k in ('Width','Height'))
    if size[0]<size[1] or not (320<=size[0]<=4096 and 200<=size[1]<=2160): raise RuntimeError('window-size')
    return size

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('handshake'); ap.add_argument('video'); ap.add_argument('receipt'); ap.add_argument('launcher_pid',type=int); a=ap.parse_args()
    h=pathlib.Path(a.handshake); video=pathlib.Path(a.video); receipt=pathlib.Path(a.receipt)
    start=time.monotonic(); ff=None; frames=[0]; checks=0; valid=False; began=None; ended=None; failure='capture-not-started'
    request=None; window=None; size=None
    try:
        while not (h/'request.json').exists():
            if not alive(a.launcher_pid) or time.monotonic()-start>600: raise RuntimeError('editor-startup')
            time.sleep(.1)
        request=json.loads((h/'request.json').read_text())
        title=request['title']; pid=request['pid']
        if not re.fullmatch(r'DESERTRV_GAME_[a-f0-9]{32}',title) or type(pid)!=int or pid<=0: raise RuntimeError('request-identity')
        # Window is discovered by exact title, then bound to the actual Unity executable PID.
        expected=pathlib.Path(os.environ['UNITY_EDITOR']).resolve()
        if pathlib.Path(f'/proc/{pid}/exe').resolve()!=expected: raise RuntimeError('process-identity')
        until=time.monotonic()+15
        while time.monotonic()<until:
            found=subprocess.run(['xdotool','search','--onlyvisible','--name','^'+title+'$'],capture_output=True,text=True)
            ids=found.stdout.split()
            if len(ids)==1: window=ids[0]; size=identity(window,title,pid); break
            if len(ids)>1: raise RuntimeError('duplicate-window')
            time.sleep(.1)
        if window is None: raise RuntimeError('game-window-unavailable')
        began=stamp()
        ff=subprocess.Popen(['ffmpeg','-nostdin','-y','-f','x11grab','-window_id',window,'-framerate','30',
            '-i',os.environ['DISPLAY'],'-c:v','libx264','-preset','ultrafast','-crf','23','-pix_fmt','yuv420p',
            '-progress','pipe:1',str(video)],stdout=subprocess.PIPE,stderr=open(h/'ffmpeg-private.log','w'),text=True)
        def progress():
            for line in ff.stdout:
                if line.startswith('frame='): frames[0]=int(line.split('=',1)[1])
        threading.Thread(target=progress,daemon=True).start()
        ready=False; frame_start=time.monotonic(); last_frame=0; last_progress=time.monotonic()
        while True:
            if identity(window,title,pid)!=size: raise RuntimeError('window-resized')
            checks+=1; atomic(h/'heartbeat.json',{'valid':True,'checks':checks})
            if ff.poll() is not None: raise RuntimeError('ffmpeg-exited')
            if frames[0]!=last_frame: last_frame=frames[0]; last_progress=time.monotonic()
            if time.monotonic()-last_progress>5: raise RuntimeError('video-frame-heartbeat')
            if not ready and frames[0]>0:
                atomic(h/'ready.json',{'valid':True,'title':title,'pid':pid,'windowId':window}); ready=True
            if (h/'stop.json').exists():
                valid=ready; failure=None if valid else 'stopped-before-first-frame'; break
            if not alive(a.launcher_pid): raise RuntimeError('editor-disappeared')
            if time.monotonic()-frame_start>2400: raise RuntimeError('capture-watchdog')
            time.sleep(.1)
    except Exception as exc:
        # Fixed error codes only. No subprocess stderr, raw exception, path or activation output.
        failure=str(exc) if isinstance(exc,RuntimeError) and re.fullmatch('[a-z-]+',str(exc)) else 'capture-validation-failed'
        atomic(h/'invalid.json',{'valid':False,'code':failure})
    finally:
        if ff is not None and ff.poll() is None:
            ff.send_signal(signal.SIGINT)
            try: ff.wait(timeout=10)
            except subprocess.TimeoutExpired: ff.kill(); ff.wait(); valid=False; failure='encoder-shutdown'
        ended=stamp()
        report={'mode':'VERIFIED_GAME_WINDOW_CAPTURE','sourceVerified':valid,'visualReviewed':False,'audioCaptured':False,
            'captureStartUtc':began,'captureEndUtc':ended,'nominalCaptureFps':30,'identityChecks':checks,'encodedProgressFrames':frames[0],
            'windowId':window,'title':request.get('title') if request else None,'pid':request.get('pid') if request else None,
            'width':size[0] if size else None,'height':size[1] if size else None,'failureCode':failure}
        if valid and video.is_file():
            digest=hashlib.sha256()
            with video.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            report['videoSha256']=digest.hexdigest()
        atomic(receipt,report); atomic(h/'stopped.json',{'stopped':True})
    return 0 if valid else 1
if __name__=='__main__':raise SystemExit(main())
