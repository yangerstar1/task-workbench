"""Immutable-archive verified copying only. No model/animation edits, renders, or Blender."""
import argparse,hashlib,json,os,shutil,stat,subprocess,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
LOCKS=json.loads((HERE/'combined-inputs.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def extract(a,archives,work):
 z=archives/(str(a['id'])+'.zip');o=work/str(a['id'])
 if z.stat().st_size!=a['bytes'] or sha(z)!=a['digest']:raise ValueError('Archive differs '+str(a['id']))
 with zipfile.ZipFile(z) as f:
  if f.testzip():raise ValueError('CRC failure')
  for n in f.infolist():
   p=Path(n.filename)
   if p.is_absolute() or '..' in p.parts or stat.S_ISLNK(n.external_attr>>16):raise ValueError('Unsafe archive entry')
  f.extractall(o)
 p=o/'technical' if a['kind']=='technical' else o;r=read(p/'stage-receipt.json')
 if r['status']!='COMPLETE_TECHNICAL_EVIDENCE_NOT_VISUAL_APPROVAL':raise ValueError('Incomplete source')
 for n,h in r['files'].items():
  if Path(n).is_absolute() or '..' in Path(n).parts or sha(p/n)!=h:raise ValueError('Source receipt mismatch')
 return p,r
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--archives',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--work',type=Path,required=True);a=ap.parse_args()
 if a.output.exists() or a.work.exists():raise ValueError('Refuse reused output')
 a.output.mkdir(parents=True);a.work.mkdir(parents=True)
 technical,tr=extract(LOCKS[0],a.archives,a.work);validation=read(technical/'evaluated-validation.json')
 if validation['failures'] or len(validation['frame_checks'])!=2798:raise ValueError('Technical evidence gate differs')
 for p in technical.iterdir():
  if p.is_file():shutil.copyfile(p,a.output/p.name)
 review=a.output/'review';review.mkdir();receipts=a.output/'evidence';receipts.mkdir();sources=[]
 from staged import verify_source, ART
 lock=verify_source();art=ART
 if sha(art/'source-manifest.json')!=tr['art_source_manifest_sha256']:raise ValueError('Current art source differs from technical output')
 for name in ['source-manifest.json','historical-clip-equivalence.json']:
  shutil.copyfile(art/name,receipts/name)
 for item in LOCKS[1:]:
  p,r=extract(item,a.archives,a.work);clip=item['clip']
  if r['clip']!=clip or r['art_source_manifest_sha256']!=tr['art_source_manifest_sha256'] or r['execution_manifest_sha256']!=tr['execution_manifest_sha256']:raise ValueError('Mixed source/executor')
  legacy=clip in ('Idle','Walk','Windup')
  if r['reused']!=legacy:raise ValueError('Wrong historical identity')
  if legacy and (str(r['original_run_id'])!='37827225328' or str(r['original_artifact_id'])!='11576761904' or r['original_source_commit']!='4521975dc47d914959e274a197224d0af7a47b04'):raise ValueError('Historical attribution differs')
  video=p/(clip+'.mp4');subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(video),'-f','null','-'],check=True,timeout=60)
  probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=nb_frames,duration,width,height','-of','json',str(video)],timeout=30))['streams'][0]
  if probe['nb_frames']!=r['actual_video']['nb_frames'] or abs(float(probe['duration'])-float(r['actual_video']['duration']))>.0001:raise ValueError('Decoded video differs')
  if not legacy:
   timing=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','frame=best_effort_timestamp_time','-of','json',str(video)],timeout=30))
   ts=[float(x['best_effort_timestamp_time']) for x in timing['frames']]
   if len(ts)!=len(r['original_timestamps_seconds']) or any(abs(x-y)>.0001 for x,y in zip(ts,r['original_timestamps_seconds'])):raise ValueError('Source timeline differs')
  shutil.copyfile(video,review/video.name);shutil.copyfile(p/'stage-receipt.json',receipts/(clip+'-original-receipt.json'))
  frames=sorted((p/'frames').glob('*.png')) if not legacy else sorted(p.glob('*.png'))
  if not frames:raise ValueError('No representative images')
  for index in sorted({0,len(frames)//2,len(frames)-1}):shutil.copyfile(frames[index],review/(clip+'-representative-'+str(index)+'.png'))
  sources.append({**item,'historical':legacy,'original_run':r.get('original_run_id'),'original_artifact':r.get('original_artifact_id'),'original_source':r.get('original_source_commit'),'video_sha256':sha(video),'receipt_sha256':sha(p/'stage-receipt.json'),'source_receipt_paths_refer_to_original_archive':True})
 provenance={'scope':'FULL_CANDIDATE','package_type':'verified_technical_and_complete_motion_evidence','technical_pass':True,'visual_approved':False,'unity_verified':False,'production_accepted':False,'package_run':os.environ.get('GITHUB_RUN_ID'),'package_commit':os.environ.get('GITHUB_SHA'),'model_source':LOCKS[0],'art_manifest_sha256':tr['art_source_manifest_sha256'],'execution_manifest_sha256':tr['execution_manifest_sha256'],'clips':sources,'older_monolithic_run':{'id':37827225328,'result':'failure','reason':'80min timeout','unchanged':True},'new_rendering':False,'historical_clip_equivalence':'Original video bytes remain historical; revised Recover/interrupt art source is not falsely attributed to old footage. Source-level unchanged motion equivalence is recorded in the locked art source.'}
 (a.output/'combined-candidate-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 (a.output/'package-validation.json').write_text(json.dumps({'scope':'FULL_CANDIDATE','technical_pass':True,'all_ten_clip_receipts_verified':True,'new_rendering':False,'visual_approved':False,'unity_verified':False},indent=2)+'\n')
 (a.output/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(a.output))+'\n' for p in sorted(a.output.rglob('*')) if p.is_file()))
 print('Verified 2798 technical checks, ten complete videos, immutable model bytes and explicit historical clip identities.')
if __name__=='__main__':main()
