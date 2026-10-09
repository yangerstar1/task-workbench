"""Bounded, independently checked Armored strict-candidate export. Never approval."""
import hashlib,json,math,re,shutil,tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

class StrictError(ValueError): pass
def require(ok,code):
 if not ok: raise StrictError(code)
def safe(p):
 p=Path(p);require(p.is_file() and not p.is_symlink() and all(not x.is_symlink() for x in p.parents),'STRICT_UNSAFE_FILE')
 require(p.stat().st_size<=512*1024**2,'STRICT_OVERSIZED_FILE');return p
def sha(p):return hashlib.sha256(safe(p).read_bytes()).hexdigest()
def read(p):
 p=safe(p);require(p.stat().st_size<=8*1024**2,'STRICT_OVERSIZED_JSON')
 def pairs(items):
  d={}
  for k,v in items:require(k not in d,'STRICT_DUPLICATE_JSON_KEY');d[k]=v
  return d
 return json.loads(p.read_text(),object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(StrictError('STRICT_NONFINITE_JSON')))
def keys(value,required,optional=()):require(isinstance(value,dict) and set(required)<=set(value)<=set(required)|set(optional),'STRICT_SCHEMA_MISMATCH')
def finite(x,low=-10000,high=10000):return type(x) in (int,float) and math.isfinite(x) and low<=x<=high
def digest(x,length=64):return isinstance(x,str) and re.fullmatch('[a-f0-9]{'+str(length)+'}',x)
def vec(v,quat=False):
 keys(v,('x','y','z','w') if quat else ('x','y','z'));require(all(finite(n) for n in v.values()),'STRICT_INVALID_VECTOR')
 if quat:require(abs(sum(n*n for n in v.values())-1)<.002,'STRICT_INVALID_QUATERNION')
def rel(s,empty=False):
 return isinstance(s,str) and ((empty and s=='') or (len(s)<=256 and not s.startswith('/') and ':' not in s and '\\' not in s and all(x not in ('','.','..') for x in s.split('/')) and not any(ord(c)<32 for c in s)))
def payload_name(name):return isinstance(name,str) and re.fullmatch(r'(?:technical/)?[A-Za-z0-9_-]+\.(?:fbx|png|tga)',name)
STATES={'Idle':2.,'Walk':.6,'Windup':1.1,'Attack':1.2,'Recover':2.,'Hit':.28,'Death':1.8}
ROOT_PROPERTIES={f'm_Local{kind}.{axis}' for kind,axes in [('Position','xyz'),('Rotation','xyzw'),('Scale','xyz')] for axis in axes}
NATIVE='DesertRV.Tests.CandidateArtImportTests.ExecutePinnedDiscoveryOrBindingDiagnostics'

def distance(a,b):return math.sqrt(sum((a[k]-b[k])**2 for k in ('x','y','z')))
def angle(a,b):
 dot=abs(sum(a[k]*b[k] for k in ('x','y','z','w')))/math.sqrt(sum(v*v for v in a.values())*sum(v*v for v in b.values()))
 return math.degrees(2*math.acos(min(1,dot)))
def baseline_shape(b):
 keys(b,('position','rotation','scale','renderers'));vec(b['position']);vec(b['rotation'],True);vec(b['scale'])
 require(all(v>0 for v in b['scale'].values()),'STRICT_NEUTRAL_SCALE')
 require(isinstance(b['renderers'],list) and len(b['renderers'])==4 and len({x['path'] for x in b['renderers']})==4,'STRICT_NEUTRAL_RENDERER_INVENTORY')
 for r in b['renderers']:
  keys(r,('path','worldCenter','worldExtents'));require(rel(r['path']),'STRICT_NEUTRAL_PATH');vec(r['worldCenter']);vec(r['worldExtents']);require(all(v>0 for v in r['worldExtents'].values()),'STRICT_NEUTRAL_EXTENTS')
def compare_baseline(expected,actual):
 baseline_shape(actual)
 require(distance(expected['position'],actual['position'])<=1e-5 and distance(expected['scale'],actual['scale'])<=1e-5 and angle(expected['rotation'],actual['rotation'])<=.001,'STRICT_NEUTRAL_ROOT_MISMATCH')
 require({r['path'] for r in expected['renderers']}=={r['path'] for r in actual['renderers']},'STRICT_NEUTRAL_RENDERER_INVENTORY')
 rows={r['path']:r for r in actual['renderers']}
 for r in expected['renderers']:
  require(distance(r['worldCenter'],rows[r['path']]['worldCenter'])<=.0001 and distance(r['worldExtents'],rows[r['path']]['worldExtents'])<=.0001,'STRICT_NEUTRAL_BOUNDS_MISMATCH')
def mesh_dimensions(minimum,maximum,size):
 for v in (minimum,maximum,size):vec(v)
 require(all(size[k]>0 and abs((maximum[k]-minimum[k])-size[k])<=.00001 for k in ('x','y','z')),'STRICT_MESH_DIMENSIONS')

def verify_staged_inventory(staged,records,receipt_sha):
 require(staged.is_dir() and not staged.is_symlink() and all(not p.is_symlink() for p in staged.parents),'STRICT_STAGING_UNSAFE')
 expected={r['path'] for r in records}|{'receipt.json'};directories=set()
 require(len(expected)==len(records)+1,'STRICT_STAGING_DUPLICATE')
 for name in expected:
  require(rel(name),'STRICT_STAGING_PATH')
  directories.update(p.as_posix() for p in Path(name).parents if p!=Path('.'))
 for record in records:require(sha(staged/record['path'])==record['sha256'] and (staged/record['path']).stat().st_size==record['bytes'],'STRICT_STAGING_HASH')
 require(sha(staged/'receipt.json')==receipt_sha,'STRICT_STAGING_RECEIPT')
 files=set();actual_dirs=set()
 for p in staged.rglob('*'):
  require(not p.is_symlink(),'STRICT_STAGING_UNSAFE')
  name=p.relative_to(staged).as_posix()
  if p.is_dir():actual_dirs.add(name)
  elif p.is_file():files.add(name)
  else:raise StrictError('STRICT_STAGING_UNSAFE')
 require(files==expected and actual_dirs==directories,'STRICT_STAGING_ALLOWLIST')

def contract_shape(c):
 keys(c,('schema','mode','scope','id','kind','repository','runUrl','sourceCommit','artifactId','artifactName','artifactSha256','files','modelFile','clips','materials','bindings'))
 require(type(c['schema']) is int and c['schema']==1 and c['mode']=='STRICT_BINDING' and c['scope']=='FULL_CANDIDATE' and c['kind']=='armored','STRICT_ARMORED_FULL_ONLY')
 require(c['repository']=='yangerstar1/task-workbench' and re.fullmatch(r'https://github.com/yangerstar1/task-workbench/actions/runs/[1-9][0-9]*',c['runUrl']) and digest(c['sourceCommit'],40) and digest(c['artifactSha256']),'STRICT_SOURCE_IDENTITY')
 require(type(c['artifactId']) is int and c['artifactId']>0 and re.fullmatch('[a-z0-9][a-z0-9-]{3,79}',c['id']) and isinstance(c['artifactName'],str) and re.fullmatch('[A-Za-z0-9_.-]{1,160}',c['artifactName']),'STRICT_CONTRACT_IDENTITY')
 require(isinstance(c['files'],list) and 1<=len(c['files'])<=32,'STRICT_INPUT_COUNT');files={}
 for f in c['files']:
  keys(f,('file','sha256'));require(payload_name(f['file']) and digest(f['sha256']) and f['file'].lower() not in {n.lower() for n in files},'STRICT_INPUT_ALLOWLIST');files[f['file']]=f['sha256']
 require(c['modelFile'] in files and c['modelFile'].endswith('.fbx'),'STRICT_MODEL_FILE')
 require(isinstance(c['clips'],list) and len(c['clips'])==7 and {x['state'] for x in c['clips']}==set(STATES),'STRICT_CLIP_INVENTORY')
 for x in c['clips']:
  keys(x,('state','file','take','seconds','loop','poseExpectation'))
  require(x['file'] in files and x['file'].endswith('.fbx') and isinstance(x['take'],str) and 0<len(x['take'])<160 and not any(ord(n)<32 for n in x['take']),'STRICT_CLIP_SOURCE')
  require(finite(x['seconds'],0,5) and abs(x['seconds']-STATES[x['state']])<.00001 and type(x['loop']) is bool and x['loop']==(x['state'] in ('Idle','Walk','Attack')) and x['poseExpectation'] in ('held','varying'),'STRICT_CLIP_TIMING')
 require(isinstance(c['materials'],list) and 1<=len(c['materials'])<=32,'STRICT_MATERIAL_COUNT')
 textures=('baseColorFile','normalFile','metallicSmoothnessFile','occlusionFile','ormFile');seen=set()
 for m in c['materials']:
  keys(m,('sourceName','baseColor','metallic','smoothness'),textures)
  require(isinstance(m['sourceName'],str) and re.fullmatch('[A-Za-z0-9_. -]{1,120}',m['sourceName']) and m['sourceName'] not in seen,'STRICT_MATERIAL_IDENTITY');seen.add(m['sourceName'])
  keys(m['baseColor'],('r','g','b','a'));require(all(finite(v,0,1) for v in m['baseColor'].values()) and finite(m['metallic'],0,1) and finite(m['smoothness'],0,1),'STRICT_MATERIAL_VALUES')
  for key in textures:require(not m.get(key) or (m[key] in files and not m[key].endswith('.fbx')),'STRICT_TEXTURE_SOURCE')
  require(not m.get('ormFile') or not(m.get('metallicSmoothnessFile') or m.get('occlusionFile')),'STRICT_TEXTURE_ROLE_CONFLICT')
 b=c['bindings'];keys(b,('animatorPath','body','weakPointRoot','core','plates','plateRenderers','openEuler','openEmission','openBaseColor','colliderCenter','colliderRadius','colliderHeight','neutralBaseline'))
 for k in ('animatorPath','body','weakPointRoot','core'):require(rel(b[k],empty=k=='animatorPath'),'STRICT_BINDING_PATH')
 for k in ('plates','plateRenderers'):require(isinstance(b[k],list) and len(b[k])==2 and len(set(b[k]))==2 and all(rel(p) for p in b[k]),'STRICT_PLATE_BINDINGS')
 require(len(b['openEuler'])==2,'STRICT_OPEN_ANGLES')
 for v in b['openEuler']:vec(v)
 vec(b['colliderCenter']);require(finite(b['colliderRadius'],.15,1.5) and finite(b['colliderHeight'],.4,4) and b['colliderHeight']>=2*b['colliderRadius'],'STRICT_COLLIDER')
 for k in ('openEmission','openBaseColor'):
  keys(b[k],('r','g','b','a'));require(all(finite(v,0,64) for v in b[k].values()) and max(b[k].values())>0,'STRICT_OPEN_COLOR')
 baseline_shape(b['neutralBaseline'])
 require({x['path'] for x in b['neutralBaseline']['renderers']}=={b['body'],b['core'],*b['plateRenderers']},'STRICT_NEUTRAL_RENDERER_ROLES')
 return files

def native_report(root):
 paths=list((root/'artifacts/candidate-art').rglob('*.xml'));require(0<len(paths)<=20,'STRICT_NATIVE_MISSING');reports=[]
 for p in paths:
  require(safe(p).stat().st_size<=10*1024**2,'STRICT_NATIVE_OVERSIZE');r=ET.parse(p).getroot()
  if r.tag=='test-run':reports.append((p,r))
 require(len(reports)==1,'STRICT_NATIVE_COUNT');p,r=reports[0];cases=list(r.iter('test-case'))
 require(r.get('result')=='Passed' and len(cases)==6 and {c.get('fullname') for c in cases}=={NATIVE,'DesertRV.Tests.CandidateAnimationPolicyTests.OnlyArmoredAttackGetsTheSourceLoopException','DesertRV.Tests.CandidateAnimationPolicyTests.EqualKeyValuesDoNotExcuseUnsafeTangents','DesertRV.Tests.CandidateAnimationPolicyTests.MissingNativeAnimatorGetsCreatedAndReused','DesertRV.Tests.CandidateAnimationPolicyTests.OpenCoreEmissionSurvivesRealSaveReimportAndReload','DesertRV.Tests.CandidateAnimationPolicyTests.RenderTargetCleanupDetachesCameraBeforeDestroy'} and all(c.get('result')=='Passed' for c in cases),'STRICT_NATIVE_FAILED')
 return sha(p)

def inspect_png(path,size=(960,540)):
 from PIL import Image,ImageStat
 p=safe(path);require(p.stat().st_size<=10*1024**2,'STRICT_IMAGE_OVERSIZE')
 with Image.open(p) as im:im.verify()
 with Image.open(p) as im:
  require(im.format=='PNG' and im.size==size,'STRICT_IMAGE_DIMENSIONS');im.load();rgb=im.convert('RGB');ranges=rgb.getextrema()
  require(max(v[1] for v in ranges)>=26 and max(v[1]-v[0] for v in ranges)>=16 and max(ImageStat.Stat(rgb).stddev)>=2,'STRICT_BLANK_IMAGE')

def dependency_digest(project,dependencies):
 require(isinstance(dependencies,list) and 1<=len(dependencies)<=300 and len(dependencies)==len(set(dependencies)),'STRICT_DEPENDENCY_LIST');h=hashlib.sha256()
 for name in sorted(dependencies):
  require(rel(name) and (name.startswith('Assets/DesertRV/') or re.match(r'Packages/com\.unity\.[a-z0-9_.-]+/',name) or name in ('Resources/unity_builtin_extra','Library/unity default resources')),'STRICT_DEPENDENCY_PATH')
  if name.startswith('Assets/DesertRV/'):
   safe(project/name);safe(project/(name+'.meta'))
  for item in (name,name+'.meta'):
   p=project/item
   if not p.exists():continue
   data=safe(p).read_bytes();encoded=item.encode();h.update(str(len(encoded)).encode()+b':'+encoded+str(len(data)).encode()+b':'+data)
 return h.hexdigest()

def derived_record(project,prefix,record,m,index,files):
 from PIL import Image
 import yaml
 keys(record,('source','sourceSha256','derived','derivedSha256','decodedPixelSha256','mapping','width','height','sRGB','sourceModified'))
 src=prefix+'/Source/'+m['ormFile'];dst=prefix+'/Derived/ORM_'+str(index).zfill(2)+'.png'
 require(record['source']==src and record['derived']==dst and record['sourceSha256']==files[m['ormFile']]==sha(project/src) and record['derivedSha256']==sha(project/dst),'STRICT_ORM_IDENTITY')
 require(record['mapping']=='R=source.B; G=source.R; B=0; A=255-source.G' and record['sRGB'] is False and record['sourceModified'] is False,'STRICT_ORM_FLAGS')
 require(type(record['width']) is int and type(record['height']) is int and 1<=record['width']<=4096 and 1<=record['height']<=4096,'STRICT_ORM_DIMENSIONS')
 with Image.open(safe(project/src)) as im:im.load();original=im.convert('RGBA')
 with Image.open(safe(project/dst)) as im:im.verify()
 with Image.open(project/dst) as im:im.load();actual=im.convert('RGBA')
 require(original.size==actual.size==(record['width'],record['height']),'STRICT_ORM_DIMENSIONS')
 expected=bytes(v for r,g,b,a in original.getdata() for v in (b,r,0,255-g))
 require(actual.tobytes()==expected,'STRICT_ORM_PIXEL_MAPPING')
 pixel=actual.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()
 require(hashlib.sha256(pixel).hexdigest()==record['decodedPixelSha256'],'STRICT_ORM_IMPORTED_PIXEL_HASH')
 meta=yaml.safe_load(safe(Path(str(project/dst)+'.meta')).read_text());imp=meta.get('TextureImporter',{})
 require(imp.get('sRGBTexture')==0 and imp.get('isReadable')==1 and imp.get('textureType')==0,'STRICT_ORM_IMPORT_SETTINGS')
 require(sha(project/src)==record['sourceSha256'],'STRICT_ORM_SOURCE_CHANGED')
 return dst


def validate_import(project,c,contract_path,report):
 required=('mode','scope','kind','status','contractSha256','prefab','dependencyHash','dependencySha256','dependencies','runUrl','sourceCommit','artifactName','artifactSha256','candidateOnly','visualReviewed','gameplayReviewed','derivedTextures','rootCurves','clips','failures','stillRequired','importedAnimatorPaths')
 keys(report,required,('muzzle','weaponCalibration'))
 require(report['mode']=='STRICT_BINDING' and report['scope']=='FULL_CANDIDATE' and report['kind']=='armored' and report['status']=='candidate-structure-imported-unreviewed' and report['failures']==[],'STRICT_IMPORT_STATUS')
 require(report['candidateOnly'] is True and report['visualReviewed'] is False and report['gameplayReviewed'] is False,'STRICT_APPROVAL_FORBIDDEN')
 for k in ('runUrl','sourceCommit','artifactName','artifactSha256'):require(report[k]==c[k],'STRICT_IMPORT_SOURCE_MISMATCH')
 prefix='Assets/DesertRV/CandidateArtImports/'+c['id'];require(report['prefab']==prefix+'/Candidate.prefab' and report['contractSha256']==sha(contract_path),'STRICT_IMPORT_CONTRACT')
 needed={prefix+'/Candidate.prefab',prefix+'/Candidate.controller',prefix+'/Source/'+c['modelFile'],prefix+'/Materials/Core_Open.mat'}
 needed.update(prefix+'/Source/'+x['file'] for x in c['clips'])
 for i,m in enumerate(c['materials']):
  needed.add(prefix+f'/Materials/Material_{i:02}.mat')
  for k in ('baseColorFile','normalFile','metallicSmoothnessFile','occlusionFile'):
   if m.get(k):needed.add(prefix+'/Source/'+m[k])
  if m.get('ormFile'):needed.add(prefix+f'/Derived/ORM_{i:02}.png')
 require(isinstance(report['dependencies'],list) and needed<=set(report['dependencies']),'STRICT_REQUIRED_DEPENDENCIES')
 require(digest(report['dependencyHash'],32) and digest(report['dependencySha256']) and report['dependencySha256']==dependency_digest(project,report['dependencies']),'STRICT_DEPENDENCY_HASH')
 require(isinstance(report['importedAnimatorPaths'],list) and all(rel(p,True) for p in report['importedAnimatorPaths']),'STRICT_ANIMATOR_PATHS')
 require(all(p==c['bindings']['animatorPath'] for p in report['importedAnimatorPaths']),'STRICT_ANIMATOR_ROOT_MISMATCH')
 require(isinstance(report['stillRequired'],list) and len(report['stillRequired'])<=10 and all(isinstance(v,str) and len(v)<200 and '\n' not in v for v in report['stillRequired']),'STRICT_NOT_COVERED_FIELDS')
 require(isinstance(report['clips'],list) and len(report['clips'])==7 and {r['state'] for r in report['clips']}==set(STATES),'STRICT_IMPORTED_CLIPS')
 specs={x['state']:x for x in c['clips']}
 for x in report['clips']:
  keys(x,('state','file','take','poseExpectation','seconds','frameRate','floatBindings','objectBindings','loop'));p=specs[x['state']]
  require(all(x[k]==p[k] for k in ('file','take','poseExpectation','loop')) and finite(x['frameRate'],1,1000) and finite(x['seconds'],0,5) and abs(x['seconds']-p['seconds'])<=1/x['frameRate']+.0001,'STRICT_IMPORTED_CLIP_MISMATCH')
  require(type(x['floatBindings']) is int and x['floatBindings']>0 and x['objectBindings']==0,'STRICT_CLIP_CURVES')
 rows=report['rootCurves'];require(isinstance(rows,list) and len(rows)==70 and {(x['state'],x['property']) for x in rows}=={(st,p) for st in STATES for p in ROOT_PROPERTIES},'STRICT_ROOT_CURVE_INVENTORY')
 for x in rows:
  keys(x,('state','property','keys','minimum','maximum','constant','tangentsSafe'));require(type(x['keys']) is int and x['keys']>0 and finite(x['minimum']) and finite(x['maximum']) and 0<=x['maximum']-x['minimum']<.00001 and x['constant'] is True and x['tangentsSafe'] is True,'STRICT_ROOT_CURVE_MOTION')
 baseline=c['bindings']['neutralBaseline']
 for state in STATES:
  values={x['property']:x['minimum'] for x in rows if x['state']==state}
  for group,key in [('Position','position'),('Scale','scale')]:
   actual={a:values['m_Local'+group+'.'+a] for a in ('x','y','z')};require(distance(actual,baseline[key])<=.00001,'STRICT_ROOT_CURVE_NEUTRAL_MISMATCH')
  rotation={a:values['m_LocalRotation.'+a] for a in ('x','y','z','w')};vec(rotation,True);require(abs(sum(v*v for v in rotation.values())-1)<=.00001 and angle(rotation,baseline['rotation'])<=.001,'STRICT_ROOT_CURVE_NEUTRAL_MISMATCH')
 return prefix


def expected_labels():
 labels={f'{s}-{t}' for s in STATES for t in ('0.000','0.250','0.500','0.750','0.999')}
 elapsed=('0.000','0.016','0.049','0.116','0.236','0.486','0.986')
 for t in ('0.25','0.5','0.75'):
  labels.update(f'Attack-{t}-Recover-{e}' for e in elapsed)
  for s in set(STATES)-{'Death'}:labels.update(f'{s}-{t}-Death-{e}' for e in elapsed)
 labels.update(f'Attack-1.1-Recover-{e}' for e in elapsed)
 labels.update(('Attack-overrun-1.0','Attack-overrun-1.1','animator-reset-0','animator-reset-1'))
 labels.update(f'weakpoint-{s}-{v}' for s in ('closed-before','open','closed-after') for v in ('front','side','rear'))
 return labels


def validate_capture(folder,prefix,imp,capture,baseline):
 keys(capture,('graphicsDeviceType','graphicsDeviceName','status','scope','prefab','dependencySha256','visualAccepted','gameplayAccepted','armoredAttackLoopIntent','notCovered','frames','neutralRoot','neutralMeshWorldMin','neutralMeshWorldMax','neutralMeshWorldSize'),('weapon',))
 require(capture['status']=='captured-unreviewed' and capture['scope']=='real-Animator-pose-diagnostics-only' and capture['visualAccepted'] is False and capture['gameplayAccepted'] is False,'STRICT_CAPTURE_STATUS')
 require(capture['graphicsDeviceType']=='OpenGLCore' and isinstance(capture['graphicsDeviceName'],str) and re.fullmatch(r'[A-Za-z0-9 ().,_/+\-]{1,240}',capture['graphicsDeviceName']) and 'llvmpipe' in capture['graphicsDeviceName'].lower(),'STRICT_REAL_SOFTWARE_GRAPHICS_REQUIRED')
 require(capture['prefab']==prefix+'/Candidate.prefab' and capture['dependencySha256']==imp['dependencySha256'],'STRICT_CAPTURE_DEPENDENCY')
 require(capture['armoredAttackLoopIntent']=='Only source-authored Armored Attack loops to cover attackClock>1.2 and normalized CrossFade overrun. Gameplay clock/movement/damage unchanged.','STRICT_LOOP_INTENT')
 require(capture['notCovered']==['Authoritative combat/weakpoint event state','Gameplay interruption and reload counts','Whole-session restart','Three-region walkthrough','Android device'],'STRICT_CAPTURE_LIMITATIONS')
 compare_baseline(baseline,capture['neutralRoot'])
 mesh_dimensions(capture['neutralMeshWorldMin'],capture['neutralMeshWorldMax'],capture['neutralMeshWorldSize'])
 frames=capture['frames'];require(isinstance(frames,list) and len(frames)==202,'STRICT_FRAME_COUNT');labels=expected_labels()
 require(len(labels)==202 and {f['requestedState'] for f in frames}==labels,'STRICT_FRAME_INVENTORY')
 fields=('image','requestedState','imageSha256','meshPoseSha256','advanceSeconds','normalizedTime','worldMinY','groundReferenceY','rootLocalPositionDelta','rootLocalAngleDelta','rootLocalScaleDelta','stateHash','sampledVertices','outsideViewportVertices','behindCameraVertices','belowReferenceVertices','transitioning','groundDiagnosticApplicable','rootLocalPosition','rootLocalRotation','rootLocalScale','meshWorldMin','meshWorldMax','meshWorldSize','meshSizeRatioToNeutral')
 for i,f in enumerate(frames):
  keys(f,fields);require(f['image']==f'frame-{i:04}.png' and digest(f['imageSha256']) and digest(f['meshPoseSha256']) and sha(folder/f['image'])==f['imageSha256'],'STRICT_FRAME_IDENTITY')
  inspect_png(folder/f['image'])
  for k in ('advanceSeconds','normalizedTime','worldMinY','groundReferenceY'):require(finite(f[k]),'STRICT_FRAME_NUMBER')
  require(0<=f['advanceSeconds']<=.5 and f['groundDiagnosticApplicable'] is True and type(f['transitioning']) is bool and type(f['stateHash']) is int and -2**31<=f['stateHash']<2**31,'STRICT_FRAME_STATE')
  require(f['worldMinY']>=f['groundReferenceY']-.004,'STRICT_GROUND_PENETRATION')
  require(type(f['sampledVertices']) is int and 1<=f['sampledVertices']<=20000000,'STRICT_MESH_COUNT')
  for k in ('outsideViewportVertices','behindCameraVertices','belowReferenceVertices'):require(type(f[k]) is int and 0<=f[k]<=f['sampledVertices'],'STRICT_MESH_DIAGNOSTIC')
  for k,limit in [('rootLocalPositionDelta',1e-5),('rootLocalScaleDelta',1e-5),('rootLocalAngleDelta',.001)]:require(finite(f[k],0,limit),'STRICT_ROOT_SAMPLE_DRIFT')
  for k in ('rootLocalPosition','rootLocalScale','meshSizeRatioToNeutral'):vec(f[k])
  vec(f['rootLocalRotation'],True);mesh_dimensions(f['meshWorldMin'],f['meshWorldMax'],f['meshWorldSize'])
  require(abs(f['worldMinY']-f['meshWorldMin']['y'])<=.00001,'STRICT_MESH_MIN_Y')
  for k in ('x','y','z'):
   ratio=f['meshWorldSize'][k]/capture['neutralMeshWorldSize'][k]
   require(abs(ratio-f['meshSizeRatioToNeutral'][k])<=max(.00001,abs(ratio)*.000001),'STRICT_MESH_RATIO')
  for field,basefield,delta in [('rootLocalPosition','position','rootLocalPositionDelta'),('rootLocalScale','scale','rootLocalScaleDelta')]:
   measured=distance(f[field],capture['neutralRoot'][basefield]);require(measured<=.00001 and abs(measured-f[delta])<=.000002,'STRICT_ROOT_VECTOR_DRIFT')
  require(angle(f['rootLocalRotation'],capture['neutralRoot']['rotation'])<=.001,'STRICT_ROOT_QUATERNION_DRIFT')
 for s in STATES:require(len({f['meshPoseSha256'] for f in frames if re.fullmatch(s+r'-0\.[0-9]{3}',f['requestedState'])})>=2,'STRICT_POSE_NOT_VARYING')
 return {f['requestedState']:f for f in frames}


def quaternion_multiply(a,b):
 x,y,z,w=(a[k] for k in ('x','y','z','w'));X,Y,Z,W=(b[k] for k in ('x','y','z','w'))
 return dict(x=w*X+x*W+y*Z-z*Y,y=w*Y-x*Z+y*W+z*X,z=w*Z+x*Y-y*X+z*W,w=w*W-x*X-y*Y-z*Z)

def unity_euler(v):
 q=[]
 for axis in ('x','y','z'):
  h=math.radians(v[axis])/2;d=dict(x=0.,y=0.,z=0.,w=math.cos(h));d[axis]=math.sin(h);q.append(d)
 return quaternion_multiply(quaternion_multiply(q[1],q[0]),q[2])

def validate_weakpoint(report,prefix,frames,angles):
 keys(report,('status','scope','calibratedForScene','visualAccepted','limitation','samples'))
 require(report['status']=='editor-fixture-captured-unreviewed' and report['scope']=='explicit-Editor-fixture-real-presenter-not-full-gameplay' and report['calibratedForScene'] is False and report['visualAccepted'] is False,'STRICT_WEAKPOINT_STATUS')
 require(report['limitation']=='Fixture assigns actor combat references/phase using reflection, then uses real BeastCombatState window and actor.WeakPointExposed. Not a world encounter, collision test or end-to-end playthrough. Whole body is vulnerable during Recover; no directional damage rule.','STRICT_WEAKPOINT_LIMITATION')
 rows=report['samples'];require(isinstance(rows,list) and len(rows)==9 and {(x['state'],x['view']) for x in rows}=={(s,v) for s in ('closed-before','open','closed-after') for v in ('front','side','rear')},'STRICT_WEAKPOINT_INVENTORY')
 by={}
 for x in rows:
  keys(x,('state','view','coreMaterial','imageLabel','fieldOfView','distance','weakPointExposed','bodyUnchanged','localPlateRotations','cameraPosition'))
  label='weakpoint-'+x['state']+'-'+x['view'];require(x['imageLabel']==label and label in frames,'STRICT_WEAKPOINT_IMAGE_LINK')
  require(x['fieldOfView']==60 and x['distance']==3 and x['bodyUnchanged'] is True and x['weakPointExposed'] is (x['state']=='open'),'STRICT_WEAKPOINT_STATE')
  require(rel(x['coreMaterial']) and re.fullmatch(re.escape(prefix)+r'/Materials/(?:Material_[0-9]{2}|Core_Open)\.mat',x['coreMaterial']),'STRICT_CORE_MATERIAL_PATH')
  require((x['coreMaterial']==prefix+'/Materials/Core_Open.mat')==(x['state']=='open'),'STRICT_CORE_MATERIAL_STATE')
  require(isinstance(x['localPlateRotations'],list) and len(x['localPlateRotations'])==2,'STRICT_PLATE_ROTATIONS')
  for q in x['localPlateRotations']:vec(q,True)
  vec(x['cameraPosition']);by[(x['state'],x['view'])]=x
 for v in ('front','side','rear'):
  a,b,c=(by[(s,v)] for s in ('closed-before','open','closed-after'))
  require(a['coreMaterial']==c['coreMaterial'],'STRICT_CORE_NOT_RESTORED')
  for i in range(2):
   qa,qb,qc=(x['localPlateRotations'][i] for x in (a,b,c))
   required=quaternion_multiply(qa,unity_euler(angles[i]))
   require(abs(sum(qa[k]*qc[k] for k in qa))>1-1e-6 and abs(sum(required[k]*qb[k] for k in qa))>1-1e-6 and abs(sum(qa[k]*qb[k] for k in qa))<.99,'STRICT_PLATE_NOT_CHANGED_OR_RESTORED')


def generated_files(project,c,prefix,imp,files):
 base=project/'Assets/DesertRV/CandidateArtImports';folder=project/prefix
 allowed={'Source.meta','contract.json','contract.json.meta','Candidate.prefab','Candidate.prefab.meta','Candidate.controller','Candidate.controller.meta','Materials.meta'}
 for name in files:allowed.update(('Source/'+name,'Source/'+name+'.meta'))
 if any(n.startswith('technical/') for n in files):allowed.add('Source/technical.meta')
 for i in range(len(c['materials'])):allowed.update((f'Materials/Material_{i:02}.mat',f'Materials/Material_{i:02}.mat.meta'))
 allowed.update(('Materials/Core_Open.mat','Materials/Core_Open.mat.meta'))
 derived=imp['derivedTextures'];expected=[(i,m) for i,m in enumerate(c['materials']) if m.get('ormFile')]
 require(isinstance(derived,list) and len(derived)==len(expected),'STRICT_DERIVED_COUNT')
 if expected:allowed.add('Derived.meta')
 for rec,(i,m) in zip(derived,expected):
  dst=derived_record(project,prefix,rec,m,i,files);name=dst[len(prefix)+1:];allowed.update((name,name+'.meta'))
 actual=set()
 for p in base.rglob('*'):
  require(not p.is_symlink(),'STRICT_SYMLINK_FORBIDDEN')
  if p.is_file():actual.add(p.relative_to(base).as_posix())
 require(actual=={c['id']+'/'+n for n in allowed}|{c['id']+'.meta'},'STRICT_GENERATED_ALLOWLIST')
 require(sha(folder/'contract.json')==sha(project/'CandidateImportInput/contract.json'),'STRICT_GENERATED_CONTRACT')
 for n,h in files.items():require(sha(folder/'Source'/n)==h,'STRICT_GENERATED_SOURCE')
 result=[(folder/n,Path('CandidateArtImports')/c['id']/n) for n in sorted(allowed)]
 result.append((base/(c['id']+'.meta'),Path('CandidateArtImports')/(c['id']+'.meta')))
 result.append((Path(str(base)+'.meta'),Path('CandidateArtImports.meta')))
 guids=set()
 for p,dest in result:
  safe(p)
  if p.suffix=='.meta':
   require(p.stat().st_size<1000000,'STRICT_META_SIZE');s=p.read_text();matches=re.findall(r'^guid: ([a-f0-9]{32})$',s,re.M)
   require(len(matches)==1 and matches[0] not in guids,'STRICT_META_GUID');guids.add(matches[0])
  elif p.suffix in ('.mat','.prefab','.controller'):
   require(p.stat().st_size<32*1024**2 and p.read_text().startswith('%YAML 1.1'),'STRICT_UNITY_YAML')
 return result


def export_strict(root,output,c,summary,native,protected):
 files=contract_shape(c);contract_path=root/'unity/CandidateImportInput/contract.json'
 summary.update(sourceCommit=c['sourceCommit'],runUrl=c['runUrl'],artifactSha256=c['artifactSha256'],contractSha256=sha(contract_path),artifactId=c['artifactId'],artifactName=c['artifactName'],mode=c['mode'],scope=c['scope'],kind=c['kind'])
 require(native=='success','STRICT_NATIVE_FAILED');require(protected=='success','STRICT_PROTECTED_SOURCE_FAILED')
 require(digest(summary.get('importCommit'),40) and re.fullmatch(r'[1-9][0-9]*',summary.get('importRunUrl','').rsplit('/',1)[-1]),'STRICT_CURRENT_RUN_IDENTITY')
 native_hash=native_report(root);project=root/'unity';evidence=project/'JourneyEvidence/CandidateArt'
 imp=read(evidence/'import-report.json');capture=read(evidence/'capture-report.json');weak=read(evidence/'weakpoint-fixture-report.json')
 prefix=validate_import(project,c,contract_path,imp);frames=validate_capture(evidence,prefix,imp,capture,c['bindings']['neutralBaseline']);validate_weakpoint(weak,prefix,frames,c['bindings']['openEuler'])
 payload=generated_files(project,c,prefix,imp,files)
 require({p.name for p in evidence.iterdir()}=={'import-report.json','capture-report.json','weakpoint-fixture-report.json'}|{f['image'] for f in capture['frames']},'STRICT_EVIDENCE_ALLOWLIST')
 payload.extend((evidence/f['image'],Path('frames')/f['image']) for f in capture['frames'])
 # Armored has no muzzle observation. Exclude the nullable weapon-only field rather than export unrelated default text.
 imp.pop('muzzle',None)
 imp.pop('weaponCalibration',None)
 capture.pop('weapon',None)
 require(imp['stillRequired']==['Actual Unity camera rendering and human visual review','Interrupted/repeated runtime flows','Full three-region playthrough','Android device acceptance','Explicit production review and unchanged production gate'],'STRICT_IMPORT_LIMITATIONS')
 require(sum(safe(p).stat().st_size for p,_ in payload)<512*1024**2,'STRICT_EXPORT_SIZE')
 staged=Path(tempfile.mkdtemp(prefix='.strict-safe-',dir=output.parent))
 try:
  records=[]
  for p,dest in payload:
   d=staged/dest;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d);records.append({'path':dest.as_posix(),'sha256':sha(d),'bytes':d.stat().st_size})
  for name,obj in [('import-report.json',imp),('capture-report.json',capture),('weakpoint-fixture-report.json',weak)]:
   d=staged/name;d.write_text(json.dumps(obj,indent=2)+'\n');records.append({'path':name,'sha256':sha(d),'bytes':d.stat().st_size})
  result=dict(summary,status='STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED',approved=False,errorCode=None,files=records,nativeXmlSha256=native_hash,nativeCases=6,images=202,weakpointImages=9,protectedSource='UNCHANGED',rawReportSha256={n:sha(evidence/n) for n in ('import-report.json','capture-report.json','weakpoint-fixture-report.json')})
  receipt_bytes=(json.dumps(result,indent=2)+'\n').encode()
  (staged/'receipt.json').write_bytes(receipt_bytes)
  verify_staged_inventory(staged,records,hashlib.sha256(receipt_bytes).hexdigest())
  require(not any(output.iterdir()),'STRICT_EXPORT_NOT_EMPTY')
  # Linux atomically replaces the empty runner-owned directory. No payload is visible before this commit.
  staged.replace(output)
  summary.update(result)
 finally:
  if staged.exists():shutil.rmtree(staged)
 return summary
