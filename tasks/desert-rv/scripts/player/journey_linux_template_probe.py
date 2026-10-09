"""Fixed official Linux module metadata probe. Never starts Unity or copies module bytes."""
import hashlib,json,os,re,stat,sys,unicodedata
from pathlib import Path,PurePosixPath

ROOT=Path(__file__).resolve().parents[4] if len(Path(__file__).resolve().parents)>4 else None
ENGINE=Path('/opt/unity/Editor/Data/PlaybackEngines/LinuxStandaloneSupport')
IMAGE='unityci/editor@sha256:17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264'
VERSION='6000.3.19f1'
VERSION_FILE=Path('/opt/unity/version')
SCAN_OUTPUT=Path('/probe-output/module-metadata.json')
PRIVATE=ROOT/'tasks/desert-rv/linux-template-probe-private' if ROOT else None
PUBLIC=ROOT/'tasks/desert-rv/linux-template-probe-public-export' if ROOT else None
MAX_ENTRIES=20000;MAX_FILE=4*1024**3;MAX_BYTES=32*1024**3;MAX_JSON=12*1024**2
HEX=re.compile('[a-f0-9]{64}')
CODES={'NONE','MODULE_MISSING','UNSAFE_ROOT','ENTRY_BUDGET','BYTE_BUDGET','FILE_CHANGED','UNSUPPORTED_KIND','IO_ERROR','INPUT_REJECTED'}

def require(ok,code='INPUT_REJECTED'):
 if not ok:raise ValueError(code)

def digest(raw):return hashlib.sha256(raw).hexdigest()
def safe_name(name):
 if not isinstance(name,str) or not 0<len(name)<=768 or any(unicodedata.category(c) in {'Cc','Cs'} for c in name):return False
 p=PurePosixPath(name)
 return not p.is_absolute() and p.as_posix()==name and all(x not in ('.','..') for x in p.parts) and bool(p.parts)

def sensitive(name):
 p=PurePosixPath(name)
 return p.suffix.lower() in {'.ulf','.alf','.lic','.key','.pem','.pfx','.p12'} or any(x.lower() in {'credentials','credentials.json','activation.log','return.log','secrets'} for x in p.parts)
def run_identity(commit,run):
 require(isinstance(commit,str) and re.fullmatch('[a-f0-9]{40}',commit) and isinstance(run,str) and re.fullmatch('[1-9][0-9]*',run))
 return dict(sourceCommit=commit,runUrl='https://github.com/yangerstar1/task-workbench/actions/runs/'+run,runAttempt=1)
def blank(commit,run):
 return dict(schema=1,label='OFFICIAL_LINUX_TEMPLATE_METADATA_ONLY',**run_identity(commit,run),image=IMAGE,unityVersion=VERSION,moduleRoot=ENGINE.as_posix(),complete=False,failureCode='NONE',entries=[],omissions=[],totalEntries=0,totalFileBytes=0,moduleBytesExported=False,editorStarted=False,licenseUsed=False,producerRestored=False)
def read_file(path,expected):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  before=os.fstat(fd);require(stat.S_ISREG(before.st_mode) and before.st_ino==expected.st_ino and before.st_dev==expected.st_dev and before.st_size==expected.st_size,'FILE_CHANGED')
  h=hashlib.sha256()
  with os.fdopen(fd,'rb',closefd=False) as stream:
   for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
  after=os.fstat(fd);require((before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino),'FILE_CHANGED')
  return h.hexdigest()
 finally:os.close(fd)
def inside_link_target(root,parent,target):
 # Resolve only components already proven inside the fixed module. Never stat an escaped target.
 current=list(parent.relative_to(root).parts);pending=target.split('/');seen=set();links=0
 if target.startswith('/'):
  prefix=root.as_posix()+'/'
  if not target.startswith(prefix):return None
  current=[];pending=target[len(prefix):].split('/')
 while pending:
  item=pending.pop(0)
  if item in ('','.'):continue
  if item=='..':
   if not current:return None
   current.pop();continue
  current.append(item);candidate=root.joinpath(*current)
  if candidate.is_symlink():
   links+=1
   if links>40 or tuple(current) in seen:return None
   seen.add(tuple(current));value=os.readlink(candidate);current.pop()
   if value.startswith('/'):
    prefix=root.as_posix()+'/'
    if not value.startswith(prefix):return None
    current=[];value=value[len(prefix):]
   pending=value.split('/')+pending
 name='/'.join(current)
 return name if safe_name(name) and not sensitive(name) else None
def scan(root,commit,run):
 result=blank(commit,run)
 try:
  require(root.is_dir(),'MODULE_MISSING');require(not any(x.is_symlink() for x in (root,*root.parents)),'UNSAFE_ROOT')
  pending=[root]
  while pending:
   folder=pending.pop()
   for p in sorted(folder.iterdir(),key=lambda x:x.name):
    result['totalEntries']+=1;require(result['totalEntries']<=MAX_ENTRIES,'ENTRY_BUDGET')
    name=p.relative_to(root).as_posix();info=p.lstat()
    if not safe_name(name) or sensitive(name):
     result['omissions'].append(dict(pathSha256=digest(name.encode('utf-8','surrogateescape')),reason='SENSITIVE' if sensitive(name) else 'INVALID_NAME'));continue
    kind='FILE' if stat.S_ISREG(info.st_mode) else 'DIRECTORY' if stat.S_ISDIR(info.st_mode) else 'SYMLINK' if stat.S_ISLNK(info.st_mode) else 'OTHER'
    row=dict(path=name,kind=kind,mode=stat.S_IMODE(info.st_mode),bytes=info.st_size if kind=='FILE' else 0,sha256='',targetWithinModule=False,target='',targetSha256='')
    if kind=='FILE':
     require(info.st_size<=MAX_FILE,'BYTE_BUDGET');result['totalFileBytes']+=info.st_size;require(result['totalFileBytes']<=MAX_BYTES,'BYTE_BUDGET');row['sha256']=read_file(p,info)
    elif kind=='DIRECTORY':pending.append(p)
    elif kind=='SYMLINK':
     target=os.readlink(p);row['targetSha256']=digest(target.encode('utf-8','surrogateescape'))
     try:
      relative=inside_link_target(root,p.parent,target)
      if relative is not None:row['targetWithinModule']=True;row['target']=relative
     except (ValueError,RuntimeError,OSError):pass
    else:result['entries'].append(row);raise ValueError('UNSUPPORTED_KIND')
    result['entries'].append(row)
  result['complete']=not result['omissions']
 except (ValueError,OSError) as error:
  result['failureCode']=str(error) if str(error) in CODES-{'NONE'} else 'IO_ERROR';result['complete']=False
 result['entries'].sort(key=lambda x:x['path']);result['omissions'].sort(key=lambda x:x['pathSha256'])
 return result
def validate(value,commit,run):
 expected=blank(commit,run);require(isinstance(value,dict) and set(value)==set(expected))
 for key in ('schema','label','sourceCommit','runUrl','runAttempt','image','unityVersion','moduleRoot','moduleBytesExported','editorStarted','licenseUsed','producerRestored'):require(type(value[key]) is type(expected[key]) and value[key]==expected[key])
 require(type(value['complete']) is bool and value['failureCode'] in CODES)
 require(type(value['totalEntries']) is int and 0<=value['totalEntries']<=MAX_ENTRIES+1 and type(value['totalFileBytes']) is int and 0<=value['totalFileBytes']<=MAX_BYTES+MAX_FILE)
 require(isinstance(value['entries'],list) and isinstance(value['omissions'],list) and len(value['entries'])+len(value['omissions'])<=value['totalEntries'])
 previous='';total=0
 for row in value['entries']:
  require(isinstance(row,dict) and set(row)=={'path','kind','mode','bytes','sha256','targetWithinModule','target','targetSha256'})
  require(safe_name(row['path']) and not sensitive(row['path']) and row['path']>previous);previous=row['path']
  require(row['kind'] in {'FILE','DIRECTORY','SYMLINK','OTHER'} and type(row['mode']) is int and 0<=row['mode']<=0o7777 and type(row['bytes']) is int and 0<=row['bytes']<=MAX_FILE and type(row['targetWithinModule']) is bool)
  if row['kind']=='FILE':require(isinstance(row['sha256'],str) and HEX.fullmatch(row['sha256']));total+=row['bytes']
  else:require(row['bytes']==0 and row['sha256']=='')
  if row['kind']=='SYMLINK':
   require(isinstance(row['targetSha256'],str) and HEX.fullmatch(row['targetSha256']))
   require(safe_name(row['target']) and not sensitive(row['target']) if row['targetWithinModule'] else row['target']=='')
  else:require(row['targetWithinModule'] is False and row['target']==row['targetSha256']=='')
  if row['kind']=='OTHER':require(value['complete'] is False and value['failureCode']=='UNSUPPORTED_KIND')
 require(total<=value['totalFileBytes'])
 if value['totalEntries']>MAX_ENTRIES:require(value['complete'] is False and value['failureCode']=='ENTRY_BUDGET')
 if value['totalFileBytes']>MAX_BYTES:require(value['complete'] is False and value['failureCode']=='BYTE_BUDGET')
 hashes=[]
 for row in value['omissions']:
  require(isinstance(row,dict) and set(row)=={'pathSha256','reason'} and isinstance(row['pathSha256'],str) and HEX.fullmatch(row['pathSha256']) and row['reason'] in {'INVALID_NAME','SENSITIVE'});hashes.append(row['pathSha256'])
 require(hashes==sorted(set(hashes)))
 if value['complete']:require(value['totalEntries']<=MAX_ENTRIES and value['totalFileBytes']<=MAX_BYTES and value['failureCode']=='NONE' and not value['omissions'] and value['entries'] and len(value['entries'])==value['totalEntries'] and total==value['totalFileBytes'])
 return value
def unique(pairs):
 result={}
 for key,value in pairs:require(key not in result);result[key]=value
 return result
def parse(raw):
 require(isinstance(raw,bytes) and 0<len(raw)<=MAX_JSON)
 return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:require(False))
def main():
 require(sys.argv[1:] in (['scan'],['export']))
 if sys.argv[1]=='scan':
  commit=os.environ.get('PROBE_SOURCE_COMMIT','');run=os.environ.get('PROBE_RUN_ID','');require(VERSION_FILE.read_text().strip()==VERSION)
  value=scan(ENGINE,commit,run);validate(value,commit,run);raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode();require(len(raw)<=MAX_JSON)
  target=SCAN_OUTPUT;require(target.parent.is_dir() and not target.exists() and not target.is_symlink());target.write_bytes(raw);target.chmod(0o644)
  print('LINUX_TEMPLATE_METADATA_CAPTURED complete='+str(value['complete']).lower());return
 require(ROOT is not None and os.environ.get('GITHUB_EVENT_NAME')=='push')
 sys.path.insert(0,str(ROOT/'tasks/desert-rv/scripts'));import journey_rebuild_dispatch as dispatch;import verify_evidence as source
 dispatch.verify(ROOT,os.environ);source.verify_source_state()
 require(PRIVATE.is_dir() and not PRIVATE.is_symlink() and {p.name for p in PRIVATE.iterdir()}=={'module-metadata.json'})
 path=PRIVATE/'module-metadata.json';require(path.is_file() and not any(p.is_symlink() for p in (path,*path.parents)) and path.stat().st_size<=MAX_JSON)
 raw=path.read_bytes();value=validate(parse(raw),os.environ['GITHUB_SHA'],os.environ['GITHUB_RUN_ID'])
 require(not PUBLIC.exists() and not PUBLIC.is_symlink());PUBLIC.mkdir();(PUBLIC/'module-metadata.json').write_bytes(raw)
 receipt=dict(schema=1,label='OFFICIAL_LINUX_TEMPLATE_METADATA_RECEIPT',**run_identity(os.environ['GITHUB_SHA'],os.environ['GITHUB_RUN_ID']),image=IMAGE,toolsDockerfileSha256=source.sha(ROOT/'tasks/desert-rv/scripts/player/TemplateProbe.Dockerfile'),probeScriptSha256=source.sha(ROOT/'tasks/desert-rv/scripts/player/journey_linux_template_probe.py'),sourceStateSha256=source.sha(source.TASK/'SOURCE-STATE.json'),requestSha256=source.sha(ROOT/dispatch.REQUEST),metadata=dict(path='module-metadata.json',sha256=digest(raw),bytes=len(raw)),complete=value['complete'],failureCode=value['failureCode'],moduleBytesExported=False,editorStarted=False,licenseUsed=False,producerRestored=False)
 (PUBLIC/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
 with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('export_ready=true\n')
 print('LINUX_TEMPLATE_METADATA_EXPORTED complete='+str(value['complete']).lower())

if __name__=='__main__':
 try:main()
 except Exception:print('LINUX_TEMPLATE_PROBE_REJECTED');sys.exit(1)
