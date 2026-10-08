"""Copy immutable model bytes plus verified framing evidence; no Blender/Unity or regeneration."""
import argparse,copy,hashlib,json,os,shutil,stat,zipfile
from pathlib import Path
from asset_validation import technical_failures
LOCKS=[{'run':37841477090,'artifact':11579827076,'source':'4c3ca2434a15544667e96fd46577169ed44369ad','bytes':25059567,'zip_sha256':'f831242adfea3fe442c5334455193963f79d8251afa4e5dbedfc3a53b01034e5','original_result':'failure'}, {'run':37848499672,'artifact':11580746875,'source':'d685e2fed7aa4f40906ed6ecfa42a4bef50a5eaa','bytes':2106282,'zip_sha256':'b1166cf2c6483683f9e54d14b9dd9a24eb64e2f4627500bd3a3495e5ec03723a','original_result':'success'}]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def unpack(z,out,lock):
 if out.exists():raise ValueError('Refuse reused extraction directory')
 if z.stat().st_size!=lock['bytes'] or sha(z)!=lock['zip_sha256']:raise ValueError('Immutable ZIP identity differs')
 with zipfile.ZipFile(z) as f:
  if f.testzip():raise ValueError('ZIP CRC failure')
  for i in f.infolist():
   p=Path(i.filename)
   if p.is_absolute() or '..' in p.parts or stat.S_ISLNK(i.external_attr>>16):raise ValueError('Unsafe ZIP entry')
  f.extractall(out)
 for line in (out/'SHA256SUMS').read_text().splitlines():
  digest,name=line.split('  ',1)
  if Path(name).name!=name or sha(out/name)!=digest:raise ValueError('Inner manifest mismatch')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--r9',type=Path,required=True);ap.add_argument('--r10',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 if a.output.exists():raise ValueError('Refuse existing package')
 a.output.mkdir(parents=True);old=a.output/'evidence/r9';new=a.output/'evidence/r10';unpack(a.r9,old,LOCKS[0]);unpack(a.r10,new,LOCKS[1])
 eq=read(new/'asset-equivalence.json');combined=read(new/'combined-technical-evidence.json');framing=read(new/'viewmodel-validation.json');original=read(old/'validation.json');package=read(old/'package-validation.json')
 expected={f'{size}:{gate}' for size in ('1280x720','1600x720') for gate in ('target_fit','core_fully_visible')}
 if set(package['technical_failures'])!=expected or package['technical_pass'] is not False:raise ValueError('Original failure scope differs')
 if combined['source_run']!=LOCKS[0]['run'] or combined['source_original_result']!='failure' or combined['new_full_run'] or not combined['combined_technical_evidence_pass'] or combined['remaining_failures']:raise ValueError('Combined report invalid')
 if any(eq[k] is not True for k in ('identical_mesh_skin_bone_animation','all_source_files_byte_identical','camera_projection_unchanged')) or eq['model_reexported']:raise ValueError('Asset changed during framing')
 if eq['asset_fingerprints_before']!=eq['asset_fingerprints_after']:raise ValueError('Fingerprint mismatch')
 if eq['baseline']['zip_sha256']!=LOCKS[0]['zip_sha256']:raise ValueError('Wrong baseline')
 for name,digest in eq['baseline']['files'].items():
  if sha(old/name)!=digest:raise ValueError('Baseline payload differs')
 if framing['technical_failures']:raise ValueError('New framing failed')
 merged=copy.deepcopy(original);merged['viewmodels']=framing['viewmodels'];failures=technical_failures(merged)
 if failures:raise ValueError('Independent combined gate failed: '+str(failures))
 if package['glb_animation_names']!=['Fire','Idle','Reload'] or set(package['fbx_animation_stacks'])!={'Fire','Idle','Reload'} or package['fbx_carrier_curve_connections']:raise ValueError('Original export gate differs')
 # Preserve all original reports separately; root payload offers immutable asset/video bytes and corrected preview only.
 payload=['weapon_hands.blend','weapon_hands.glb','weapon_hands.fbx','clip-manifest.json','weapon-presentation-contract.json','carrier-channel-cleanup.json','side_Idle.mp4','side_Fire.mp4','side_Reload.mp4']
 for name in payload:shutil.copyfile(old/name,a.output/name)
 for p in new.glob('*.png'):shutil.copyfile(p,a.output/p.name)
 merged.update(scope='FULL_CANDIDATE',candidate_only=True,approved=False,visual_approved=False,unity_import_verified=False,evidence_kind='Combined immutable R9 model/motion plus separately verified framing correction',original_full_run_result='failure',new_full_render_run=False)
 (a.output/'validation.json').write_text(json.dumps(merged,indent=2)+'\n')
 provenance={'scope':'FULL_CANDIDATE','package_type':'combined_verified_evidence','candidate_only':True,'technical_pass':True,'visual_approved':False,'auditioned':False,'unity_verified':False,'production_accepted':False,'new_full_render_run':False,'sources':LOCKS,'package_commit':os.environ.get('GITHUB_SHA'),'package_run':os.environ.get('GITHUB_RUN_ID'),'presentation_instance_offset_m':[-.015,0,0],'model_files_byte_identical':{n:sha(a.output/n) for n in payload},'original_reports_unchanged':['evidence/r9/validation.json','evidence/r9/package-validation.json'],'texture_contract':'Original exports use solid-color PBR materials; no external model textures omitted.'}
 (a.output/'combined-candidate-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 (a.output/'package-validation.json').write_text(json.dumps({'scope':'FULL_CANDIDATE','status':'COMBINED_TECHNICAL_EVIDENCE_NOT_VISUAL_APPROVAL','technical_pass':True,'technical_failures':[],'original_full_run_result':'failure','new_full_run':False,'visual_approved':False,'unity_verified':False},indent=2)+'\n')
 (a.output/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(a.output))+'\n' for p in sorted(a.output.rglob('*')) if p.is_file()))
 print(json.dumps({'technical_pass':True,'visual_approved':False,'new_full_run':False,'sources':[x['run'] for x in LOCKS]}))
if __name__=='__main__':main()
