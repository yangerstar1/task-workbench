"""Fail-closed bounded evidence packager. Original outputs remain isolated per Actions run.
Uses stdlib; ffprobe verifies actual video streams. Never executes Blender or downloads assets.
"""
import argparse, hashlib, json, os, shutil, struct, subprocess
from pathlib import Path
from artifact_io import fresh_output
HERE=Path(__file__).resolve().parent
P=json.loads((HERE/'parameters.json').read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def expected(phase):
    if phase=='static':
        return ['bulwark-basecolor.png','bulwark-static-review.blend','static-checks.json']+[f'review/static-{i:02}.png' for i in range(8)]+['review/static-weakpoint-open.png']
    names=list(P['clips'])+[f'SYNTHETIC_Interrupt_{x}' for x in (.07,.42,.91)]
    return ['bulwark-basecolor.png','bulwark-review.blend','bulwark-candidate.glb','bulwark-candidate.fbx','evaluated-validation.json','clip-manifest.json','output-sha256.json']+[f'review/{n}.mp4' for n in names]+[f'review/{n}-{f:.2f}.png' for n in names for f in (0,.25,.5,.75,1)]+[f'review/turntable-{i:02}.png' for i in range(16)]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); ap.add_argument('--phase',choices=['static','motion'],required=True); a=ap.parse_args()
    root=Path(a.root).resolve(); phase=a.phase
    required_root=Path(os.environ['RUNNER_TEMP'])/f"bulwark-{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}"
    if root!=required_root:raise ValueError('Output does not belong to current run/attempt')
    provenance=json.loads((root/'provenance.json').read_text())
    for key,env in [('source_commit','GITHUB_SHA'),('run_id','GITHUB_RUN_ID'),('run_attempt','GITHUB_RUN_ATTEMPT')]:
        if str(provenance[key])!=os.environ[env]:raise ValueError('Provenance mismatch: '+key)
    if provenance['source_manifest_sha256']!=sha(HERE/'source-manifest.json'):raise ValueError('Source changed since provenance')
    src=root/phase; dst=fresh_output(root/(phase+'-package')); files=expected(phase); errors=[]; total_bytes=0
    for name in files:
        f=src/name
        if not f.is_file() or f.is_symlink(): errors.append('missing/invalid '+name); continue
        total_bytes+=f.stat().st_size
        if total_bytes>1024*1024*1024:errors.append('package exceeds 1GiB'); break
        if f.stat().st_size>256*1024*1024:errors.append('oversized '+name); continue
        target=dst/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(f,target)
        try:
            if f.suffix=='.png':
                raw=f.read_bytes()[:24]
                if raw[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('invalid PNG signature')
                w,h=struct.unpack('>II',raw[16:24])
                if (w,h) not in ((960,540),(512,512)):raise ValueError('unexpected PNG size')
            elif f.suffix=='.mp4':
                probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,nb_frames:format=duration','-of','json',str(f)],timeout=20))
                stream=probe['streams'][0]; duration=float(probe['format']['duration'])
                stem=f.stem
                seconds=P['clips'].get(stem)
                if seconds is None:seconds=min(.35,float(stem.rsplit('_',1)[1]))+.6
                expected_frames=round(seconds*P['fps'])+1
                if int(stream.get('nb_frames',-1))!=expected_frames:raise ValueError('incomplete frame count')
                if abs(duration-expected_frames/P['fps'])>.04:raise ValueError('incomplete duration')
                if stream['codec_name']!='h264' or (stream['width'],stream['height'])!=(960,540) or not .2<duration<3:raise ValueError('unexpected video format/duration')
            elif f.suffix=='.glb' and f.read_bytes()[:4]!=b'glTF':raise ValueError('invalid GLB')
            elif f.suffix=='.fbx' and not f.read_bytes().startswith(b'Kaydara FBX Binary'):raise ValueError('invalid binary FBX')
        except (ValueError,KeyError,IndexError,subprocess.SubprocessError) as exc:errors.append(name+': '+str(exc))
    exit_path=root/(phase+'.exit')
    if not exit_path.is_file() or exit_path.read_text().strip()!='0':errors.append('generation process did not exit successfully')
    try:
        if phase=='static':
            checks=json.loads((src/'static-checks.json').read_text())
            if len(checks)!=9 or any(c['errors'] for c in checks):errors.append('static technical checks failed')
        else:
            report=json.loads((src/'evaluated-validation.json').read_text())
            if report['failures'] or report['status']!='technical_checks_passed_visual_review_still_required':errors.append('motion technical checks failed')
            clips=json.loads((src/'clip-manifest.json').read_text())
            if {c['name'] for c in clips}!=set(P['clips']):errors.append('seven clip manifest mismatch')
            for c in clips:
                if c['root_motion'] or abs(c['duration_seconds']-P['clips'][c['name']])>1e-8:errors.append('clip timing/root mismatch')
            recorded=json.loads((src/'output-sha256.json').read_text())
            for name in files:
                if name=='output-sha256.json':continue
                if (src/name).is_file() and recorded.get(name)!=sha(src/name):errors.append('generator checksum mismatch '+name)
    except (OSError,ValueError,KeyError) as exc:errors.append('missing/invalid technical report: '+str(exc))
    # Only explicit own sources/provenance/logs are bundled; no ref directory or broad source glob.
    shutil.copyfile(root/'provenance.json',dst/'provenance.json')
    shutil.copyfile(root/'blender-upstream.sha256',dst/'blender-upstream.sha256')
    shutil.copyfile(HERE/'source-manifest.json',dst/'source-manifest.json')
    log=root/(phase+'.log')
    if log.is_file():
        with log.open('rb') as stream:
            stream.seek(max(0,log.stat().st_size-10*1024*1024)); (dst/'generation.log').write_bytes(stream.read())
    status={'status':'PARTIAL_FAILED_NOT_A_SUCCESS' if errors else 'COMPLETE_TECHNICAL_EVIDENCE_NOT_VISUAL_APPROVAL','phase':phase,'errors':errors,'visual_approved':False,'unity_verified':False,'run_id':provenance['run_id'],'run_attempt':provenance['run_attempt'],'source_commit':provenance['source_commit']}
    (dst/'STATUS.json').write_text(json.dumps(status,indent=2)+'\n')
    (dst/'SHA256SUMS').write_text(''.join(sha(f)+'  '+str(f.relative_to(dst))+'\n' for f in sorted(dst.rglob('*')) if f.is_file()))
    print(json.dumps(status,indent=2)); return 1 if errors else 0
if __name__=='__main__':raise SystemExit(main())
