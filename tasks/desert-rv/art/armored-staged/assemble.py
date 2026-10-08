"""Verify complete chunks, then assemble original-timebase videos. No Blender execution."""
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path
import plan
from staged import verify_source,verify_receipt,base_receipt,atomic_json,sha
from artifact_io import fresh_output

def probe(path):
    result=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,nb_frames,duration:format=duration','-of','json',str(path)],timeout=30))
    stream=result['streams'][0]
    if stream['codec_name']!='h264' or (stream['width'],stream['height'])!=(960,540):raise ValueError('Video codec/size invalid')
    subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(path),'-f','null','-'],check=True,timeout=60)
    return stream

def validate_chunks(root,clip,lock):
    found={}; receipt_sources=[]
    for path in sorted(Path(root).rglob('stage-receipt.json')):
        r=json.loads(path.read_text())
        if r.get('stage')!='chunk' or r.get('clip')!=clip:continue
        if r['art_source_manifest_sha256']!=lock['source_manifest_sha256'] or r['execution_manifest_sha256']!=sha(Path(__file__).parent/'execution-manifest.json'):raise ValueError('Mixed source/execution in clip')
        if r['status']!='COMPLETE_TECHNICAL_EVIDENCE_NOT_VISUAL_APPROVAL':continue
        index=r['chunk']
        if not isinstance(index,int) or not 0<=index<len(plan.chunks(clip)):raise ValueError('Chunk out of bounds')
        expected=plan.chunks(clip)[index]
        if r['original_frame_indices']!=expected or [f['original_frame'] for f in r['frames']]!=expected:raise ValueError('Chunk coverage differs')
        for frame in r['frames']:
            n=frame['original_frame'];expected_name=f'frames/{n:04}.png'
            if frame['file']!=expected_name or frame['original_time_seconds']!=(n-1)/60:raise ValueError('Invalid original frame/time')
            f=path.parent/expected_name
            if f.is_symlink() or sha(f)!=frame['sha256']:raise ValueError('Frame hash mismatch')
            if n in found and sha(found[n])!=sha(f):raise ValueError('Conflicting duplicate frame')
            found[n]=f
        receipt_sources.append({'run_id':r['run_id'],'run_attempt':r['run_attempt'],'chunk':index,'receipt_sha256':sha(path)})
    if sorted(found)!=plan.frames(clip):raise ValueError('Missing chunks; refusing incomplete video')
    return found,receipt_sources

def main():
    p=argparse.ArgumentParser();p.add_argument('--clip',required=True);p.add_argument('--technical',required=True);p.add_argument('--chunks');p.add_argument('--legacy');p.add_argument('--output',required=True);a=p.parse_args()
    lock=verify_source();technical=verify_receipt(a.technical,'technical',lock);out=fresh_output(a.output)
    r=base_receipt('assembled_clip',lock);r['clip']=a.clip;r['technical_receipt_sha256']=sha(Path(a.technical)/'stage-receipt.json')
    try:
        target=out/(a.clip+'.mp4')
        if a.clip in plan.REUSED:
            for name,digest in lock['reused_clips'][a.clip].items():
                f=Path(a.legacy)/name
                if f.is_symlink() or sha(f)!=digest:raise ValueError('Legacy evidence mismatch')
                shutil.copyfile(f,out/f.name)
            stats=probe(target)
            if int(stats['nb_frames'])!=plan.count(a.clip):raise ValueError('Incomplete legacy video')
            r.update(reused=True,original_run_id=lock['reused_run_id'],original_artifact_id=lock['reused_artifact_id'],original_source_commit=lock['source_commit'],sampling='original completed 60fps video, byte-identical reuse')
        else:
            files,sources=validate_chunks(a.chunks,a.clip,lock);frame_numbers=plan.frames(a.clip);total_duration=plan.count(a.clip)/60
            concat=out/'frames.ffconcat';lines=['ffconcat version 1.0']
            frame_dir=out/'frames';frame_dir.mkdir()
            for i,n in enumerate(frame_numbers):
                dest=frame_dir/f'{n:04}.png';shutil.copyfile(files[n],dest)
                # Absolute paths are rejected by ffconcat unless explicitly allowed; names
                # below are locally generated and contain no untrusted path text.
                duration=(frame_numbers[i+1]-n)/60 if i+1<len(frame_numbers) else 1/60
                lines += [f"file 'frames/{n:04}.png'",'option framerate 60',f'duration {duration:.12f}']
            lines += [f"file 'frames/{frame_numbers[-1]:04}.png'",'option framerate 60'];concat.write_text('\n'.join(lines)+'\n')
            subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(concat),'-fps_mode','vfr','-enc_time_base','1:60000','-c:v','libx264','-crf','23','-pix_fmt','yuv420p','-video_track_timescale','60000','-t',f'{total_duration:.12f}',str(target)],check=True,timeout=120)
            stats=probe(target)
            if int(stats['nb_frames'])!=len(frame_numbers) or abs(float(stats['duration'])-total_duration)>.0001:raise ValueError('Encoded frame count/duration differs from exact source timeline')
            # Verify presentation timestamps, not merely total length.
            timing=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','frame=best_effort_timestamp_time','-of','json',str(target)],timeout=30))
            actual=[float(f['best_effort_timestamp_time']) for f in timing['frames']]
            if len(actual)!=len(frame_numbers) or any(abs(t-(n-1)/60)>.0001 for t,n in zip(actual,frame_numbers)):raise ValueError('Video timestamps retimed source frames')
            r.update(reused=False,sampling='every second original 60Hz sample; exact final endpoint included; VFR nominal 30Hz',original_frame_indices=frame_numbers,original_timestamps_seconds=[(n-1)/60 for n in frame_numbers],expected_encoded_seconds=total_duration,chunk_sources=sources)
        r['actual_video']=stats;r['status']='COMPLETE_TECHNICAL_EVIDENCE_NOT_VISUAL_APPROVAL'
    except Exception as exc:r['error']=str(exc);raise
    finally:
        r['files']={str(f.relative_to(out)):sha(f) for f in out.rglob('*') if f.is_file() and f.name!='stage-receipt.json'}
        atomic_json(out/'stage-receipt.json',r)
if __name__=='__main__':main()
