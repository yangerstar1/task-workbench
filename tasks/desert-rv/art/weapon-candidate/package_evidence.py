"""Assemble contact sheet and immutable output hashes after Actions rendering."""
import pathlib,sys,hashlib,json,struct
p=pathlib.Path(sys.argv[1])
required=['weapon_hands.blend','weapon_hands.glb','weapon_hands.fbx','validation.json','clip-manifest.json']+[f'studio_{i:02d}.png' for i in range(8)]+['viewmodel_1280x720.png','viewmodel_1600x720.png']+[f'side_{s}.mp4' for s in ['Idle','Fire','Reload']]
missing=[x for x in required if not (p/x).is_file() or (p/x).stat().st_size==0]
if missing:raise SystemExit(f'Missing evidence: {missing}')
data=(p/'weapon_hands.glb').read_bytes(); assert data[:4]==b'glTF'; size,kind=struct.unpack_from('<II',data,12); doc=json.loads(data[20:20+size]); names={x['name'] for x in doc.get('animations',[])}
report={'required_artifacts_present':True,'glb_animation_names':sorted(names),'glb_skins':len(doc.get('skins',[])),'glb_materials':len(doc.get('materials',[])),'visual_approval':False,'status':'CANDIDATE_AWAITING_PIXEL_REVIEW'}
if not {'Idle','Fire','Reload'}.issubset(names):raise SystemExit(f'Missing GLB actions: {names}')
if not report['glb_skins']:raise SystemExit('Missing GLB skin')
(p/'package-validation.json').write_text(json.dumps(report,indent=2))
(p/'SHA256SUMS').write_text('\n'.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name for f in sorted(p.iterdir()) if f.is_file() and f.name!='SHA256SUMS')+'\n')
print(json.dumps(report,indent=2))
