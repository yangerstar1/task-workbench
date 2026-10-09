"""One reviewed push request; manual dispatch retains its explicit policy pin."""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
BASE='4bcc86731f7a030ee31b78017ad9ad27f1997383'
BRANCH='journey-linux-export-recovery-938'
REF='refs/heads/'+BRANCH
REPOSITORY='yangerstar1/task-workbench'
OWNER='yangerstar1'
REQUEST='.github/dispatch/desert-rv-rebuild-linux-symbol-20261009.json'
REQUEST_ID='desert-rv-rebuild-linux-symbol-20261009-once'
POLICY='tasks/desert-rv/art/journey-preparation/restoration-transition.json'

def require(ok,code):
 if not ok:raise ValueError('JOURNEY_DISPATCH_'+code)

def parse_request(raw):
 require(isinstance(raw,bytes) and 0<len(raw)<=2048,'REQUEST_SIZE')
 def unique(pairs):
  result={}
  for key,value in pairs:
   require(key not in result,'DUPLICATE_KEY');result[key]=value
  return result
 try:value=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:require(False,'JSON_CONSTANT'))
 except (UnicodeError,json.JSONDecodeError):raise ValueError('JOURNEY_DISPATCH_BAD_JSON') from None
 require(isinstance(value,dict) and set(value)=={'schema','requestId','baseCommit','policySha256'},'REQUEST_KEYS')
 require(type(value['schema']) is int and value['schema']==1 and value['requestId']==REQUEST_ID and value['baseCommit']==BASE,'REQUEST_IDENTITY')
 require(isinstance(value['policySha256'],str) and re.fullmatch('[a-f0-9]{64}',value['policySha256']),'REQUEST_POLICY_FORMAT')
 return value

def validate(env,event,head,parents,request_raw,tracked_raw,request_in_parent,changed_paths,policy_sha):
 require(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')==REPOSITORY and env.get('GITHUB_REPOSITORY_VISIBILITY')=='public','REPOSITORY')
 require(env.get('RUNNER_ENVIRONMENT')=='github-hosted' and env.get('RUNNER_OS')=='Linux','HOSTED_RUNNER')
 require(env.get('GITHUB_ACTOR')==OWNER and env.get('GITHUB_TRIGGERING_ACTOR')==OWNER,'ACTOR')
 require(env.get('GITHUB_REF')==('refs/heads/main' if env.get('GITHUB_EVENT_NAME')=='workflow_dispatch' else REF),'BRANCH')
 require(re.fullmatch('[a-f0-9]{40}',head or '') and env.get('GITHUB_SHA')==head,'HEAD')
 require(re.fullmatch('[1-9][0-9]*',env.get('GITHUB_RUN_ID','')) and re.fullmatch('[1-9][0-9]*',env.get('GITHUB_RUN_ATTEMPT','')),'RUN')
 require(re.fullmatch('[a-f0-9]{64}',policy_sha or ''),'POLICY_FORMAT')
 if env.get('GITHUB_EVENT_NAME')=='workflow_dispatch':
  require(env.get('MANUAL_TRANSITION_SHA')==policy_sha,'MANUAL_POLICY');return policy_sha
 require(env.get('GITHUB_EVENT_NAME')=='push','EVENT')
 require(env.get('GITHUB_WORKFLOW_REF')==REPOSITORY+'/.github/workflows/desert-rv-journey-rebuild.yml@'+REF,'WORKFLOW')
 require(env.get('GITHUB_RUN_ATTEMPT')=='1','REPLAY')
 require(isinstance(event,dict) and event.get('before')==BASE and event.get('after')==head and event.get('ref')==REF,'PUSH_IDENTITY')
 require(event.get('created') is False and event.get('deleted') is False and event.get('forced') is False,'PUSH_KIND')
 repository=event.get('repository',{})
 require(isinstance(repository,dict) and repository.get('full_name')==REPOSITORY and repository.get('private') is False and repository.get('fork') is False and repository.get('owner',{}).get('login')==OWNER,'PUSH_REPOSITORY')
 require(event.get('head_commit',{}).get('id')==head and event.get('sender',{}).get('login')==OWNER,'PUSH_AUTHOR')
 require(parents==[BASE] and head!=BASE,'PARENT')
 require(request_in_parent is False and REQUEST in changed_paths and request_raw==tracked_raw,'REQUEST_GIT')
 request=parse_request(request_raw)
 require(request['policySha256']==policy_sha,'REQUEST_POLICY')
 return policy_sha

def git(root,*args):
 return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL)

def safe_bytes(path,limit):
 require(path.is_file() and not any(p.is_symlink() for p in (path,*path.parents)),'INPUT_FILE')
 require(path.stat().st_size<=limit,'INPUT_SIZE');return path.read_bytes()

def verify(root,env):
 head=git(root,'rev-parse','HEAD').decode().strip()
 policy_sha=hashlib.sha256(safe_bytes(root/POLICY,1024*1024)).hexdigest()
 event={};parents=[];request_raw=tracked_raw=b'';present=False;changed=[]
 if env.get('GITHUB_EVENT_NAME')=='push':
  event_path=Path(env.get('GITHUB_EVENT_PATH',''))
  try:event=json.loads(safe_bytes(event_path,4*1024*1024))
  except (UnicodeError,json.JSONDecodeError):raise ValueError('JOURNEY_DISPATCH_EVENT_JSON') from None
  parents=[line.split(' ',1)[1] for line in git(root,'cat-file','-p','HEAD').decode().split('\n\n',1)[0].splitlines() if line.startswith('parent ')]
  require(parents==[BASE],'PARENT')
  git(root,'cat-file','-e',BASE+'^{commit}')
  present=subprocess.run(['git','cat-file','-e',BASE+':'+REQUEST],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
  request_raw=safe_bytes(root/REQUEST,2048);tracked_raw=git(root,'show','HEAD:'+REQUEST)
  changed=git(root,'diff-tree','--no-commit-id','--name-only','-r','HEAD').decode().splitlines()
 return validate(env,event,head,parents,request_raw,tracked_raw,present,changed,policy_sha)

def main():
 require(sys.argv[1:] in ([],['--verify-only']),'ARGUMENTS')
 policy_sha=verify(ROOT,os.environ)
 if not sys.argv[1:]:
  with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream:stream.write('transition_sha256='+policy_sha+'\n')
 print('JOURNEY_REBUILD_DISPATCH_IDENTITY_VERIFIED')

if __name__=='__main__':main()
