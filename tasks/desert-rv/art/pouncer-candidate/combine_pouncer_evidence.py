"""Immutable seven-clip technical evidence package; no generation or rendering."""
import argparse,copy,hashlib,json,os,shutil,stat,zipfile
from pathlib import Path
from compare_glb_lineage import compare
HERE=Path(__file__).resolve().parent
LOCKS=json.loads((HERE/'combined-pouncer-inputs.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def unpack(z,out,lock):
 if out.exists():raise ValueError('Extraction directory already exists')
 if z.stat().st_size!=lock['bytes'] or sha(z)!=lock['zip_sha256']:raise ValueError('ZIP identity mismatch')
 with zipfile.ZipFile(z) as f:
  if f.testzip():raise ValueError('CRC failure')
  for i in f.infolist():
   p=Path(i.filename)
   if p.is_absolute() or '..' in p.parts or stat.S_ISLNK(i.external_attr>>16):raise ValueError('Unsafe entry')
  f.extractall(out)
 for l in (out/'SHA256SUMS').read_text().splitlines():
  h,n=l.split('  ',1);p=Path(n)
  if p.is_absolute() or '..' in p.parts or sha(out/p)!=h:raise ValueError('Source inner hash mismatch')
def main():
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise ValueError('Refuse existing output')
 work=a.output.parent/(a.output.name+'-source')
 if work.exists():raise ValueError('Refuse existing staging')
 for key,lock in LOCKS.items():unpack(a.inputs/(key+'.zip'),work/key,lock)
 old,new,opaque=(work/k for k in ('r3','technical','opaque'))
 original=read(old/'validation.json');gate=read(new/'technical-gate.json');pictures=read(opaque/'opaque-receipt.json')
 if original['status']!='technical_fail' or set(original['errors'])!={'Death penetrates floor >4mm','Death torso is not resting on the floor'}:raise ValueError('Historical failure scope differs')
 if gate['status']!='DEATH_TECHNICAL_PASS_NOT_FULL' or gate['errors'] or not gate['source_native_pass']:raise ValueError('Death native gate failed')
 if not gate['geometry_weights_rig_unchanged'] or not gate['non_death_actions_unchanged']:raise ValueError('Source boundaries changed')
 for fmt in ('glb','fbx'):
  r=gate['serialized_native_checks'][fmt]
  if not r['passed'] or r['maximum_penetration_m']>.004 or abs(r['duration_seconds']-1.8)>1e-6 or r['root_matrix_max_delta']>1e-5:raise ValueError('Serialized Death gate failed')
  if r['file_sha256']!=sha(new/('pouncer-candidate.'+fmt)):raise ValueError('Serialized model hash differs')
 if gate['maximum_penetration_m']>.004 or gate['max_visual_translation_per10ms']>.03:raise ValueError('Native bounds changed')
 if pictures['fingerprints_before']!=pictures['fingerprints_after'] or not pictures['asset_data_unchanged'] or pictures['visual_approval']:raise ValueError('Render changed protected assets or approved them')
 if pictures['artifact_id']!=LOCKS['technical']['artifact'] or pictures['source_commit']!=LOCKS['technical']['source']:raise ValueError('Pictures are from another model')
 for n,h in pictures['source_sha256'].items():
  if sha(new/n)!=h:raise ValueError('Picture source identity differs')
 if len(pictures['images'])!=4 or {(i['seconds'],i['azimuth_degrees']) for i in pictures['images'] if i['seconds']==1.8}!={(1.8,135.0),(1.8,315.0)}:raise ValueError('Four-view contract changed')
 lineage=compare(old/'pouncer-candidate.glb',new/'pouncer-candidate.glb')
 if not lineage['passed'] or not lineage['death_changed']:raise ValueError('Historical non-Death equivalence failed')
 clips=read(old/'clip-manifest.json')
 for fmt,times in gate['serialized_times'].items():
  if set(times)!=set(clips):raise ValueError('Seven clip set mismatch')
  for n,c in clips.items():
   if abs(times[n]['duration']-c['seconds_requested'])>1e-6:raise ValueError('Duration differs')
 a.output.mkdir(parents=True)
 def cp(root,n,dest=None):
  target=a.output/(dest or n);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/n,target)
 for n in ['pouncer-candidate.blend','pouncer-candidate.glb','pouncer-candidate.fbx']:cp(new,n)
 for n in ['pouncer-basecolor.png','clip-manifest.json','parameters.json']:cp(old,n)
 for root,key in [(old,'r3'),(new,'technical'),(opaque,'opaque')]:
  for f in sorted(root.glob('*.json')):cp(root,f.name,'evidence/'+key+'/'+f.name)
  if (root/'source-commit.txt').exists():cp(root,'source-commit.txt','evidence/'+key+'/source-commit.txt')
 for name in ['Idle','Walk','Windup','Attack','Recover','Hit','InterruptAttack25ToRecover','InterruptAttack50ToRecover','InterruptAttack75ToRecover']:
  cp(old,'review/'+name+'.mp4','review/historical-r3/'+name+'.mp4')
 for n in ['turntable-02.png','turntable-07.png']:cp(old,'review/'+n,'review/historical-r3/'+n)
 for row in pictures['images']:
  if sha(opaque/row['file'])!=row['sha256']:raise ValueError('Picture changed')
  cp(opaque,row['file'],'review/current-death/'+row['file'])
 (a.output/'glb-lineage.json').write_text(json.dumps(lineage,indent=2)+'\n')
 validation={'scope':'FULL_CANDIDATE','status':'COMBINED_SEVEN_CLIP_TECHNICAL_PASS','technical_pass':True,'visual_approval':False,'unity_verified':False,'production_accepted':False,'geometry_and_six_non_death_clips_exact_glb_equivalence':True,'serialized_animation_times':gate['serialized_times'],'historical_motion_bounds_m':{k:v for k,v in original['checks']['motion_bounds_m'].items() if k!='Death'},'current_death':gate,'new_full_render_run':False,'death_visual_evidence':'Four opaque stills only; no new full Death video; visual approval pending','historical_interrupt_scope':'Synthetic R3 transitions; runtime controller not measured'}
 (a.output/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
 provenance={'scope':'FULL_CANDIDATE','technical_pass':True,'candidate_only':True,'visual_approved':False,'unity_verified':False,'production_accepted':False,'new_full_render_run':False,'sources':LOCKS,'package_commit':os.environ.get('GITHUB_SHA'),'package_run':os.environ.get('GITHUB_RUN_ID'),'models_from_successful_technical_artifact':{p.name:sha(p) for p in a.output.glob('pouncer-candidate.*')},'historical_failure_unchanged':'evidence/r3/validation.json','current_death_source':LOCKS['technical'],'historical_six_clips_source':LOCKS['r3'],'historical_equivalence':'glb-lineage.json','limitations':['Current Death has four static views, no new full video','Historical interruption synthesis is not Unity controller proof','FBX new Death independently imported at200Hz; full Unity import still required']}
 (a.output/'combined-candidate-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 (a.output/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(a.output))+'\n' for p in sorted(a.output.rglob('*')) if p.is_file()))
 print(json.dumps({'technical_pass':True,'scope':'FULL_CANDIDATE','visual_approved':False,'new_full_render_run':False}))
if __name__=='__main__':main()
