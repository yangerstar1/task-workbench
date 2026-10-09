"""One fixed R4 twenty-view corrected terrain production verification push. No generic dispatch, command, rebuild nonce, or manual impersonation."""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BASE='e40671685c2ff824e30e5709585407068d0c65fc'
REPOSITORY='yangerstar1/task-workbench'
OWNER='yangerstar1'
WORKFLOW='.github/workflows/desert-rv-environment-v4-r4.yml'
REQUEST='.github/dispatch/desert-rv-environment-v4-r4-20261009.json'
MANIFEST='.github/dispatch/desert-rv-environment-v4-r4-20261009-files.json'
REQUEST_ID='desert-rv-environment-v4-r4-20261009-once-d28e54a9'
SOURCE_STATE='tasks/desert-rv/SOURCE-STATE.json'
CANDIDATE='tasks/desert-rv/art/environment-v4/candidate-r4-file-manifest.json'
CANDIDATE_SHA='5ec86228cb5b283028197641d739ddf2aec6ff156a99f0217eebe562d63f68ab'
PAYLOAD_PATHS=('.github/workflows/desert-rv-environment-v4-r4.yml', 'tasks/desert-rv/art/environment-v4/candidate-r4-file-manifest.json', 'tasks/desert-rv/art/environment-v4/r4-native-yaml-fixture.json', 'tasks/desert-rv/art/environment-v4/test_candidate_r4.py', 'tasks/desert-rv/scripts/environment_v4_r4_dispatch.py', 'tasks/desert-rv/scripts/environment_v4_r4_evidence.py', 'tasks/desert-rv/scripts/prepare_runner.sh', 'tasks/desert-rv/scripts/test_environment_diffuse_comparison_dispatch.py', 'tasks/desert-rv/scripts/test_environment_diffuse_comparison_r1_dispatch.py', 'tasks/desert-rv/scripts/test_environment_terrain_probe_dispatch.py', 'tasks/desert-rv/scripts/test_environment_v4_r3_dispatch.py', 'tasks/desert-rv/scripts/test_environment_v4_r4_dispatch.py', 'tasks/desert-rv/scripts/test_environment_v4_r4_evidence.py', 'tasks/desert-rv/scripts/test_environment_v4_r4_runner_prefix.py', 'tasks/desert-rv/scripts/verify_evidence.py', 'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneySceneAuthoring.CorrectedTerrain.cs', 'tasks/desert-rv/unity/Assets/DesertRV/Editor/JourneySceneAuthoring.CorrectedTerrain.cs.meta', 'tasks/desert-rv/unity/Assets/DesertRV/Tests/EditorRender/JourneyEnvironmentRenderTests.cs')  # Exact reviewed delta, excluding circular controls.


def require(ok,code):
 if not ok:raise ValueError('ENVIRONMENT_V4_R4_DISPATCH_'+code)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def digest(value):return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value)
def path_ok(path):return isinstance(path,str) and re.fullmatch('[A-Za-z0-9._/-]{1,240}',path) and not path.startswith('/') and '..' not in Path(path).parts and Path(path).as_posix()==path

def decode(raw,limit):
 require(isinstance(raw,bytes) and 0<len(raw)<=limit,'JSON_SIZE')
 def unique(pairs):
  value={}
  for k,v in pairs:require(k not in value,'DUPLICATE_KEY');value[k]=v
  return value
 try:return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:require(False,'JSON_CONSTANT'))
 except (UnicodeError,json.JSONDecodeError):raise ValueError('ENVIRONMENT_V4_R4_DISPATCH_BAD_JSON') from None

def parse_request(raw):
 r=decode(raw,4096)
 require(isinstance(r,dict) and set(r)=={'schema','requestId','baseCommit','candidateManifestSha256','filesManifestSha256','sourceStateSha256'},'REQUEST_KEYS')
 require(type(r['schema']) is int and r['schema']==1 and r['requestId']==REQUEST_ID and r['baseCommit']==BASE,'REQUEST_IDENTITY')
 require(r['candidateManifestSha256']==CANDIDATE_SHA and digest(r['filesManifestSha256']) and digest(r['sourceStateSha256']),'REQUEST_DIGEST')
 return r

def parse_manifest(raw):
 m=decode(raw,2*1024*1024)
 require(isinstance(m,dict) and set(m)=={'schema','requestId','baseCommit','candidateManifestSha256','files'},'MANIFEST_KEYS')
 require(type(m['schema']) is int and m['schema']==1 and m['requestId']==REQUEST_ID and m['baseCommit']==BASE and m['candidateManifestSha256']==CANDIDATE_SHA,'MANIFEST_IDENTITY')
 require(isinstance(m['files'],list) and 1<=len(m['files'])<=200,'MANIFEST_COUNT')
 seen=set();total=0
 for item in m['files']:
  require(isinstance(item,dict) and set(item)=={'path','sha256','size','mode'},'FILE_KEYS')
  name=item['path'];require(path_ok(name) and name not in seen and name not in {REQUEST,MANIFEST,SOURCE_STATE},'FILE_PATH');seen.add(name)
  require(digest(item['sha256']) and type(item['size']) is int and 0<=item['size']<=40*1024*1024 and item['mode'] in ('100644','100755'),'FILE_IDENTITY');total+=item['size']
 require(total<=60*1024*1024,'PAYLOAD_SIZE')
 require({WORKFLOW,'tasks/desert-rv/scripts/environment_v4_r4_dispatch.py'}<=seen,'REQUIRED_PAYLOAD')
 require(seen==set(PAYLOAD_PATHS) and len(PAYLOAD_PATHS)==len(seen),'PAYLOAD_SET')
 return m

def validate_identity(env,event,head,parents,request_raw,tracked_request,request_in_parent,changed_paths,manifest_raw,state_raw,candidate_raw):
 require(re.fullmatch('[a-f0-9]{40}',BASE or ''),'UNFINALIZED_PARENT')
 require(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')==REPOSITORY and env.get('GITHUB_REPOSITORY_VISIBILITY')=='public','REPOSITORY')
 require(env.get('GITHUB_ACTOR')==OWNER and env.get('GITHUB_TRIGGERING_ACTOR')==OWNER,'ACTOR')
 require(env.get('GITHUB_REF')=='refs/heads/main','BRANCH')
 require(env.get('GITHUB_EVENT_NAME')=='push','EVENT')
 require(env.get('GITHUB_WORKFLOW_REF')==REPOSITORY+'/'+WORKFLOW+'@refs/heads/main','WORKFLOW')
 require(re.fullmatch('[a-f0-9]{40}',head or '') and env.get('GITHUB_SHA')==head and head!=BASE,'HEAD')
 require(re.fullmatch('[1-9][0-9]*',env.get('GITHUB_RUN_ID','')) and env.get('GITHUB_RUN_ATTEMPT')=='1','REPLAY')
 require(isinstance(event,dict) and event.get('before')==BASE and event.get('after')==head and event.get('ref')=='refs/heads/main','PUSH_IDENTITY')
 require(event.get('created') is False and event.get('deleted') is False and event.get('forced') is False,'PUSH_KIND')
 repo=event.get('repository',{})
 require(isinstance(repo,dict) and repo.get('full_name')==REPOSITORY and repo.get('visibility')=='public' and repo.get('private') is False and repo.get('fork') is False and repo.get('default_branch')=='main' and repo.get('owner',{}).get('login')==OWNER,'PUSH_REPOSITORY')
 require(event.get('head_commit',{}).get('id')==head and event.get('sender',{}).get('login')==OWNER,'PUSH_AUTHOR')
 require(parents==[BASE],'PARENT')
 require(request_in_parent is False and request_raw==tracked_request,'REQUEST_GIT')
 request=parse_request(request_raw);manifest=parse_manifest(manifest_raw)
 require(sha(candidate_raw)==CANDIDATE_SHA,'CANDIDATE_PIN')
 require(sha(manifest_raw)==request['filesManifestSha256'] and sha(state_raw)==request['sourceStateSha256'],'REQUEST_PIN')
 require(set(changed_paths)=={item['path'] for item in manifest['files']}|{REQUEST,MANIFEST,SOURCE_STATE} and len(changed_paths)==len(set(changed_paths)),'CHANGED_SET')
 return manifest

def git(root,*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL)
def safe_bytes(path,limit):
 require(path.is_file() and not any(p.is_symlink() for p in (path,*path.parents)),'INPUT_FILE')
 require(path.stat().st_size<=limit,'INPUT_SIZE');return path.read_bytes()
def tracked_bytes(root,path,limit):
 row=git(root,'ls-tree','HEAD','--',path).decode().strip().split('\t')
 require(len(row)==2 and row[1]==path,'TRACKED_PATH')
 fields=row[0].split();require(len(fields)==3 and fields[0] in ('100644','100755') and fields[1]=='blob','GIT_MODE')
 size=int(git(root,'cat-file','-s',fields[2]));require(size<=limit,'TRACKED_SIZE')
 raw=git(root,'cat-file','blob',fields[2]);require(len(raw)==size,'TRACKED_SIZE');return raw,fields[0]

def verify(root,env):
 require(re.fullmatch('[a-f0-9]{40}',BASE or ''),'UNFINALIZED_PARENT')
 head=git(root,'rev-parse','HEAD').decode().strip()
 parents=[line.split(' ',1)[1] for line in git(root,'cat-file','-p','HEAD').decode().split('\n\n',1)[0].splitlines() if line.startswith('parent ')]
 require(parents==[BASE],'PARENT');git(root,'cat-file','-e',BASE+'^{commit}')
 present=subprocess.run(['git','cat-file','-e',BASE+':'+REQUEST],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
 try:event=decode(safe_bytes(Path(env.get('GITHUB_EVENT_PATH','')),4*1024*1024),4*1024*1024)
 except OSError:raise ValueError('ENVIRONMENT_V4_R4_DISPATCH_EVENT_FILE') from None
 tracked={}
 for name,limit in [(REQUEST,4096),(MANIFEST,2*1024*1024),(SOURCE_STATE,4*1024*1024),(CANDIDATE,2*1024*1024)]:
  raw=safe_bytes(root/name,limit);git_raw,mode=tracked_bytes(root,name,limit)
  require(mode=='100644' and raw==git_raw,'TRACKED_CONTROL');tracked[name]=raw
 changed=git(root,'diff-tree','--no-commit-id','--name-only','-r','HEAD').decode().splitlines()
 manifest=validate_identity(env,event,head,parents,tracked[REQUEST],tracked[REQUEST],present,changed,tracked[MANIFEST],tracked[SOURCE_STATE],tracked[CANDIDATE])
 for item in manifest['files']:
  raw=safe_bytes(root/item['path'],40*1024*1024);git_raw,mode=tracked_bytes(root,item['path'],40*1024*1024)
  require(mode==item['mode'] and len(raw)==item['size'] and sha(raw)==item['sha256'] and raw==git_raw,'PAYLOAD_BYTES')
 return sha(tracked[MANIFEST])

def main():
 require(sys.argv[1:] in ([],['--verify-only']),'ARGUMENTS')
 manifest_sha=verify(ROOT,os.environ)
 if not sys.argv[1:]:
  with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream:stream.write('environment_manifest_sha256='+manifest_sha+'\n')
 print('ENVIRONMENT_V4_R4_FIXED_PUSH_IDENTITY_VERIFIED')
if __name__=='__main__':main()
