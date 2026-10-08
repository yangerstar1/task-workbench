"""Read-only exact decoded GLB comparison. No Blender or third-party dependencies."""
import argparse,hashlib,json,struct
from pathlib import Path

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load(path):
 raw=Path(path).read_bytes();assert raw[:4]==b'glTF';chunks={};offset=12
 while offset<len(raw):
  size,kind=struct.unpack_from('<II',raw,offset);offset+=8;chunks[kind]=raw[offset:offset+size];offset+=size
 j=json.loads(chunks[0x4e4f534a]);binary=chunks[0x004e4942]
 def accessor(index):
  a=j['accessors'][index];assert 'sparse' not in a
  view=j['bufferViews'][a['bufferView']];assert view.get('buffer',0)==0
  fmt={5120:'b',5121:'B',5122:'h',5123:'H',5125:'I',5126:'f'}[a['componentType']]
  width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
  size=struct.calcsize('<'+fmt*width);start=view.get('byteOffset',0)+a.get('byteOffset',0);stride=view.get('byteStride',size)
  values=[list(struct.unpack_from('<'+fmt*width,binary,start+i*stride)) for i in range(a['count'])]
  return {'componentType':a['componentType'],'type':a['type'],'normalized':a.get('normalized',False),'values':values}
 def node_name(i):return j['nodes'][i]['name']
 meshes={}
 for n in j['nodes']:
  if 'mesh' not in n:continue
  primitives=[]
  for p in j['meshes'][n['mesh']]['primitives']:
   primitives.append({'attributes':{key:accessor(index) for key,index in p['attributes'].items()},'indices':accessor(p['indices']),'material':p.get('material'),'mode':p.get('mode',4)})
  meshes[n['name']]={'primitives':primitives,'skin':n.get('skin')}
 skins=[{'joints':[node_name(i) for i in s['joints']],'inverse_bind':accessor(s['inverseBindMatrices'])} for s in j['skins']]
 nodes={n['name']:{k:v for k,v in n.items() if k not in ('mesh','children')}|{'children':[node_name(i) for i in n.get('children',[])]} for n in j['nodes']}
 animations={}
 for animation in j['animations']:
  channels={}
  for channel in animation['channels']:
   sampler=animation['samplers'][channel['sampler']];target=channel['target']
   channels[node_name(target['node'])+'/'+target['path']]={'interpolation':sampler.get('interpolation','LINEAR'),'time':accessor(sampler['input']),'value':accessor(sampler['output'])}
  animations[animation['name']]=channels
 images=[]
 for image in j.get('images',[]):
  v=j['bufferViews'][image['bufferView']];start=v.get('byteOffset',0)
  images.append({'mimeType':image['mimeType'],'sha256':hashlib.sha256(binary[start:start+v['byteLength']]).hexdigest()})
 return {'file_sha256':hashlib.sha256(raw).hexdigest(),'geometry_weights':meshes,'skin':skins,'nodes':nodes,'materials':j.get('materials',[]),'textures':j.get('textures',[]),'images':images,'animations':animations}

def canonical_geometry(meshes):
 # Triangle order and equivalent duplicate corner indices may change on re-export.
 # Preserve exact full corner attributes, material, multiplicity and winding.
 result={}
 for name,mesh in meshes.items():
  primitives=[]
  for p in mesh['primitives']:
   assert p['mode']==4
   ids=[row[0] for row in p['indices']['values']];assert len(ids)%3==0
   vertices=[json.dumps({key:a['values'][i] for key,a in p['attributes'].items()},sort_keys=True) for i in range(len(p['attributes']['POSITION']['values']))]
   triangles=[]
   for i in range(0,len(ids),3):
    t=tuple(vertices[n] for n in ids[i:i+3]);triangles.append(min(t,t[1:]+t[:1],t[2:]+t[:2]))
   primitives.append({'attributes':p['attributes'],'material':p['material'],'mode':p['mode'],'oriented_corner_triangles':sorted(triangles)})
  result[name]={'skin':mesh['skin'],'primitives':primitives}
 return result

def compare(old,new):
 a,b=load(old),load(new);sections=['skin','nodes','materials','textures','images'];report={'scope':'READONLY_GLB_LINEAGE_NOT_UNITY_VALIDATION','old_sha256':a['file_sha256'],'new_sha256':b['file_sha256'],'exact_sections':{},'non_death':{},'errors':[],'visual_approval':False}
 report['geometry_raw_index_order_equal']=a['geometry_weights']==b['geometry_weights']
 ga,gb=canonical_geometry(a['geometry_weights']),canonical_geometry(b['geometry_weights'])
 report['geometry_exact_surface']={'old':digest(ga),'new':digest(gb),'equal':ga==gb,'method':'Exact vertex attributes plus oriented triangle corner multiset including weights/UV/normals/material; only triangle enumeration and equal duplicate indices canonicalized'}
 if ga!=gb:report['errors'].append('Exact oriented surface differs')
 for section in sections:
  x,y=digest(a[section]),digest(b[section]);report['exact_sections'][section]={'old':x,'new':y,'equal':x==y}
  if x!=y:report['errors'].append(section+' differs')
 for name in ['Idle','Walk','Windup','Attack','Recover','Hit']:
  x,y=digest(a['animations'][name]),digest(b['animations'][name]);equal=x==y
  report['non_death'][name]={'old':x,'new':y,'exact_decoded_equal':equal}
  if not equal:
   changes=[]
   for key,channel in a['animations'][name].items():
    other=b['animations'][name][key]
    if channel==other:continue
    values=channel['value']['values'];actual=other['value']['values']
    delta=max((abs(x-y) for xs,ys in zip(values,actual) for x,y in zip(xs,ys)),default=0) if len(values)==len(actual) else None
    changes.append({'channel':key,'old_samples':len(values),'new_samples':len(actual),'max_numeric_delta':delta,'time_equal':channel['time']==other['time']})
   report['non_death'][name]['changed_channels']=changes;report['errors'].append(name+' is not exact')
 report['death_changed']=a['animations']['Death']!=b['animations']['Death'];report['passed']=not report['errors'];return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--old',required=True);p.add_argument('--new',required=True);p.add_argument('--output',required=True);a=p.parse_args();r=compare(a.old,a.new);Path(a.output).write_text(json.dumps(r,indent=2));print(json.dumps({'passed':r['passed'],'errors':r['errors']}));raise SystemExit(0 if r['passed'] else 1)
