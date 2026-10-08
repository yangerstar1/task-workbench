"""Assemble contact sheet and immutable output hashes after Actions rendering."""
import pathlib,sys,hashlib,json,struct
from asset_validation import inspect_fbx_animation, technical_failures, delivered_file, CARRIERS
p=pathlib.Path(sys.argv[1])
required=['weapon_hands.blend','weapon_hands.glb','weapon_hands.fbx','validation.json','clip-manifest.json','weapon-presentation-contract.json']+[f'studio_{i:02d}.png' for i in range(8)]+['viewmodel_1280x720.png','viewmodel_1600x720.png']+[f'side_{s}.mp4' for s in ['Idle','Fire','Reload']]
required += [f'reload_count_{before:02d}_plus_{added:02d}_frame_{frame:03d}.png' for before,added in [(0,12),(3,5),(11,1)] for frame in [1,60,100]]
missing=[x for x in required if not (p/x).is_file() or (p/x).stat().st_size==0]
if missing:raise SystemExit(f'Missing evidence: {missing}')
data=(p/'weapon_hands.glb').read_bytes(); assert data[:4]==b'glTF'; size,kind=struct.unpack_from('<II',data,12); doc=json.loads(data[20:20+size]); names={x['name'] for x in doc.get('animations',[])}
node_names={n.get('name','') for n in doc.get('nodes',[])}
expected={f'{prefix}_{i:02d}' for prefix in ['LoadedNail','IncomingNail'] for i in range(12)}
if not expected.issubset(node_names):raise SystemExit(f'Missing independently countable nail nodes: {sorted(expected-node_names)}')
report={'independent_nail_nodes':24,'required_artifacts_present':True,'glb_animation_names':sorted(names),'glb_skins':len(doc.get('skins',[])),'glb_materials':len(doc.get('materials',[])),'visual_approval':False,'status':'CANDIDATE_AWAITING_PIXEL_REVIEW'}
if not {'Idle','Fire','Reload'}.issubset(names):raise SystemExit(f'Missing GLB actions: {names}')
if not report['glb_skins']:raise SystemExit('Missing GLB skin')
validation=json.loads((p/'validation.json').read_text()); failures=technical_failures(validation)
fbx_report=inspect_fbx_animation(p/'weapon_hands.fbx');stacks=fbx_report['stacks']; report['fbx_animation_stacks']=stacks;report['fbx_carrier_curve_connections']=fbx_report['carrier_curve_connections']
if fbx_report['carrier_curve_connections']:failures.append('fbx_carrier_channels_present')
if len(stacks)!=3 or {name.split('|')[-1] for name in stacks}!={'Idle','Fire','Reload'}:failures.append('fbx_clip_set_mismatch')
carriers={i for i,n in enumerate(doc.get('nodes',[])) if n.get('name') in CARRIERS}
if any(c['target'].get('node') in carriers for a in doc.get('animations',[]) for c in a['channels']):failures.append('glb_carrier_channels_present')
report['technical_failures']=failures; report['technical_pass']=not failures; report['status']='REJECTED_TECHNICAL_GATE' if failures else 'TECHNICAL_PASS_VISUAL_REVIEW_REQUIRED'
(p/'package-validation.json').write_text(json.dumps(report,indent=2))
(p/'SHA256SUMS').write_text('\n'.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name for f in sorted(p.iterdir()) if delivered_file(f))+'\n')
print(json.dumps(report,indent=2))

if failures:raise SystemExit('Candidate rejected: '+', '.join(failures))
