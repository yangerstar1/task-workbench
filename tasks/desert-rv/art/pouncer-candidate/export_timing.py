"""Read actual GLB sampler and FBX AnimationStack time ranges, not authoring metadata."""
import json
import struct

def inspect_glb(path):
    b=path.read_bytes(); size,kind=struct.unpack_from('<II',b,12); doc=json.loads(b[20:20+size]); offset=20+size; binary=b''
    while offset<len(b):
        length,kind=struct.unpack_from('<II',b,offset); offset+=8
        if kind==0x004e4942:binary=b[offset:offset+length]
        offset+=length
    result={}
    for animation in doc.get('animations',[]):
        values=[]
        for index in {s['input'] for s in animation['samplers']}:
            ac=doc['accessors'][index]; view=doc['bufferViews'][ac['bufferView']]
            if ac['componentType']!=5126 or ac['type']!='SCALAR' or ac.get('sparse'):raise ValueError('Unexpected GLB timing accessor')
            start=view.get('byteOffset',0)+ac.get('byteOffset',0); stride=view.get('byteStride',4)
            values.extend(struct.unpack_from('<f',binary,start+i*stride)[0] for i in range(ac['count']))
        result[animation['name']]={'start':min(values),'end':max(values),'duration':max(values)-min(values)}
    return result

def inspect_fbx(path):
    b=path.read_bytes(); version=struct.unpack_from('<I',b,23)[0]; fmt='<QQQB' if version>=7500 else '<IIIB'; hs=struct.calcsize(fmt); stacks={}; stack_defaults={}
    def node(p):
        end,count,length,nlen=struct.unpack_from(fmt,b,p)
        if not end:return p+hs,None
        name=b[p+hs:p+hs+nlen].decode(); pos=p+hs+nlen; props=[];children=[]
        for _ in range(count):
            t=chr(b[pos]);pos+=1
            if t in 'SR':
                ln=struct.unpack_from('<I',b,pos)[0];pos+=4;v=b[pos:pos+ln];pos+=ln;props.append(v.decode(errors='replace') if t=='S' else None)
            elif t in 'YCLFDI':
                f={'Y':'h','C':'?','L':'q','F':'f','D':'d','I':'i'}[t];props.append(struct.unpack_from('<'+f,b,pos)[0]);pos+=struct.calcsize(f)
            elif t in 'fdlibc':
                _,_,ln=struct.unpack_from('<III',b,pos);pos+=12+ln;props.append(None)
            else:raise ValueError('Unknown FBX property '+t)
        while pos<end-hs:
            pos,child=node(pos)
            if child:children.append(child)
        current=(name,props,children)
        if name=='PropertyTemplate' and props and props[0]=='FbxAnimStack':
            for cname,cprops,cchildren in children:
                if cname=='Properties70':
                    for pn,pp,pc in cchildren:
                        if pn=='P' and pp and pp[0] in ('LocalStart','LocalStop'):stack_defaults[pp[0]]=pp[-1]/46186158000
        if name=='AnimationStack':
            values=stack_defaults.copy()
            for cname,cprops,cchildren in children:
                if cname=='Properties70':
                    for pn,pp,pc in cchildren:
                        if pn=='P' and pp and pp[0] in ('LocalStart','LocalStop'):values[pp[0]]=pp[-1]/46186158000
            label=str(props[1]).split('\x00')[0].split('|')[-1]
            if 'LocalStart' in values and 'LocalStop' in values:stacks[label]={'start':values['LocalStart'],'end':values['LocalStop'],'duration':values['LocalStop']-values['LocalStart']}
        return end,current
    pos=27
    while pos<len(b)-hs and struct.unpack_from(fmt,b,pos)[0]:pos,_=node(pos)
    return stacks
