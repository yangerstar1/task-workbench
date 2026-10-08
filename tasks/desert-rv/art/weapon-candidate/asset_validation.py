"""Export artifact validation and exact allow-listed GLB channel cleanup."""
import json, struct, pathlib
CARRIERS={'IncomingOffset','LeftReloadOffset'}
def read_glb(path):
    raw=pathlib.Path(path).read_bytes()
    if raw[:4]!=b'glTF':raise ValueError('Not GLB')
    size,kind=struct.unpack_from('<II',raw,12)
    if kind!=0x4E4F534A:raise ValueError('Missing GLB JSON')
    return raw,json.loads(raw[20:20+size]),20+size

def strip_carrier_animation_channels(path):
    raw,doc,tail=read_glb(path); carriers={i for i,n in enumerate(doc['nodes']) if n.get('name') in CARRIERS}; removed={}
    if len(carriers)!=2:raise ValueError('Missing expected offset carrier nodes')
    for clip in doc.get('animations',[]):
        old=clip['channels']; clip['channels']=[c for c in old if c['target'].get('node') not in carriers]; removed[clip.get('name','')]=len(old)-len(clip['channels'])
    data=json.dumps(doc,separators=(',',':')).encode();data+=b' '*((-len(data))%4)
    output=b'glTF'+struct.pack('<II',2,20+len(data)+len(raw)-tail)+struct.pack('<II',len(data),0x4E4F534A)+data+raw[tail:]
    pathlib.Path(path).write_bytes(output);return removed

def inspect_fbx_animation(path):
    raw=pathlib.Path(path).read_bytes()
    if not raw.startswith(b'Kaydara FBX Binary  \x00\x1a\x00'):raise ValueError('Expected binary FBX')
    version=struct.unpack_from('<I',raw,23)[0]; wide=version>=7500; header=25 if wide else 13; fmt='<QQQB' if wide else '<IIIB'; found=[]; models={}; curve_nodes=set(); connections=[]
    def node(at):
        end,count,property_bytes,name_len=struct.unpack_from(fmt,raw,at)
        if not end:return at+header
        name=raw[at+header:at+header+name_len].decode();cursor=at+header+name_len; props=[]
        for _ in range(count):
            tag=chr(raw[cursor]);cursor+=1
            if tag in 'SR':
                length=struct.unpack_from('<I',raw,cursor)[0];cursor+=4;val=raw[cursor:cursor+length];cursor+=length
                props.append(val.decode(errors='replace') if tag=='S' else val)
            elif tag in 'YCFDIL':
                typ={'Y':'h','C':'?','F':'f','D':'d','I':'i','L':'q'}[tag];props.append(struct.unpack_from('<'+typ,raw,cursor)[0]);cursor+=struct.calcsize('<'+typ)
            elif tag in 'fdilbc':
                length,encoding,byte_count=struct.unpack_from('<III',raw,cursor);cursor+=12+byte_count
            else:raise ValueError(f'Unknown FBX property {tag}')
        if name=='Model' and len(props)>=2:models[props[0]]=props[1].split('\x00')[0]
        if name=='AnimationCurveNode' and props:curve_nodes.add(props[0])
        if name=='C' and len(props)>=3:connections.append(props)
        if name=='AnimationStack':found.append(next((p.split('\x00')[0] for p in props if isinstance(p,str)),''))
        while cursor<end-header:cursor=node(cursor)
        return end
    cursor=27
    while cursor<len(raw)-header:
        if not any(raw[cursor:cursor+header]):break
        cursor=node(cursor)
    carrier_curves=[{'curve_node':c[1],'carrier':models[c[2]],'property':c[3] if len(c)>3 else ''} for c in connections if c[1] in curve_nodes and models.get(c[2]) in CARRIERS]
    parents={models[c[1]]:models[c[2]] for c in connections if c[0]=='OO' and c[1] in models and c[2] in models}
    return {'stacks':found,'carrier_curve_connections':carrier_curves,'model_names':sorted(models.values()),'model_parents':parents}

def fbx_animation_stacks(path):
    return inspect_fbx_animation(path)['stacks']

def technical_failures(validation):
    failures=[]
    if validation.get('weight_errors'):failures.append('skin_weights')
    if set(validation.get('mesh_groups',{}))!={'weapon','hands'}:failures.append('missing_mesh_budgets')
    for name,data in validation.get('mesh_groups',{}).items():
        if not data.get('in_budget'):failures.append('triangle_budget:'+name)
    views=validation.get('viewmodels',{})
    if set(views)!={'1280x720','1600x720'}:failures.append('missing_aspect_evidence')
    for name,data in views.items():
        for field in ['target_fit','core_fully_visible','center_clear','sleeves_reach_lower_edge']:
            if data.get(field) is not True:failures.append(name+':'+field)
    if len(views)==2:
        a,b=views.values()
        if a.get('rig_location')!=b.get('rig_location') or a.get('rig_euler')!=b.get('rig_euler'):failures.append('aspect_pose_mismatch')
    samples=validation.get('loading_surface_samples',[])
    if len(samples)!=42:failures.append('missing_loading_surface_samples')
    elif any(s.get('intersections') for s in samples):failures.append('loading_surface_intersections')
    skin=validation.get('incoming_skin_contract',{})
    if skin.get('same_rig') is not True or skin.get('positive_weight_bones')!=['reload_strip'] or skin.get('carrier_parent_of_reload_strip')!='IncomingOffset' or skin.get('renderer_reparented') is not False:failures.append('incoming_skin_contract')
    muzzle=validation.get('muzzle',{})
    if muzzle.get('parent')!='weapon' or max([abs(a-b) for a,b in zip(muzzle.get('head_xyz',[99]*3),[0,.35,.072])])>.00001:failures.append('muzzle_source_position')
    return failures

def delivered_file(path):
    return path.is_file() and (path.suffix in {'.png','.mp4','.json','.glb','.fbx','.blend','.log'} or path.name in {'source-commit.txt','blender-upstream.sha256'})
