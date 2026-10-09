"""One immutable STRICT-only push, never a manual-event impersonation or approval."""
import hashlib, json, os, re, subprocess, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = '120f6d6f0d34dbe432854c31ae91945ccd8496ab'
PRODUCER_COMMIT = '10d52332b0808017a3f7d39e6920d008b113ba6f'
CONTRACT_SHA = '67b4b04c71f9c837a192990c37e15be7c73c4571d73dc3323c527c2f10b7bcd7'
REPOSITORY = 'yangerstar1/task-workbench'
OWNER = 'yangerstar1'
WORKFLOW = '.github/workflows/desert-rv-armored-v004-r1-strict.yml'
REQUEST_ID = 'armored-v004-r1-strict-20261009-once-c8521e4b'
REQUEST = '.github/dispatch/' + REQUEST_ID + '.json'
MANIFEST = '.github/dispatch/' + REQUEST_ID + '-files.json'
CONTRACT = 'tasks/desert-rv/art/import-candidate/contracts/armored-v004-r1-full-strict-37955418340-capsule-r2.json'
CONTRACT_ID = 'armored-v004-r1-full-strict-37955418340-capsule-r2'
SOURCE_STATE = 'tasks/desert-rv/SOURCE-STATE.json'
PRODUCER_WORKFLOW = '.github/workflows/desert-rv-armored-refined-technical.yml'
ART_MANIFEST_SHA = 'e7cc6db0032ed5265e4696eb2069d25c5bde20612e7eff67fb038b2137cf7264'
ART_SOURCE_COMMIT = '4137776d60283ff6b38f46664758b497a275a84e'
EXECUTION_MANIFEST_SHA = 'a80e25b084e03aa855f18de6c312aafe11ad6a989ea2cb5709bbe68ef60008df'
PAYLOAD_PATHS = frozenset((WORKFLOW, CONTRACT,
    'tasks/desert-rv/scripts/armored_v004_strict_dispatch.py',
    'tasks/desert-rv/scripts/test_armored_v004_strict_dispatch.py',
    'tasks/desert-rv/scripts/prepare_runner.sh', 'tasks/desert-rv/scripts/verify_evidence.py'))
INPUT_FILES = frozenset(('bulwark-candidate.fbx', 'bulwark-animations.fbx', 'bulwark-basecolor.png', 'bulwark-orm.png'))

def require(ok, code):
    if not ok: raise ValueError('ARMORED_STRICT_' + code)
def sha(raw): return hashlib.sha256(raw).hexdigest()
def hexval(value, length=64): return isinstance(value, str) and re.fullmatch('[a-f0-9]{' + str(length) + '}', value)
def decode(raw, limit=4*1024*1024):
    require(isinstance(raw, bytes) and 0 < len(raw) <= limit, 'JSON_SIZE')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'DUPLICATE_KEY'); result[key] = value
        return result
    try: return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: require(False, 'JSON_CONSTANT'))
    except (UnicodeError, json.JSONDecodeError): raise ValueError('ARMORED_STRICT_BAD_JSON') from None

def parse_contract(raw):
    require(hexval(PRODUCER_COMMIT, 40) and hexval(CONTRACT_SHA), 'UNFINALIZED_PRODUCER_CONTRACT')
    require(sha(raw) == CONTRACT_SHA, 'CONTRACT_PIN')
    c = decode(raw)
    require(isinstance(c, dict) and set(c) == {'schema','mode','scope','id','kind','repository','runUrl','sourceCommit','artifactId','artifactName','artifactSha256','files','modelFile','clips','materials','bindings'}, 'CONTRACT_KEYS')
    require(type(c['schema']) is int and c['schema'] == 1 and c['mode'] == 'STRICT_BINDING' and c['scope'] == 'FULL_CANDIDATE' and c['kind'] == 'armored' and c['id'] == CONTRACT_ID, 'STRICT_BINDING')
    require(c['repository'] == REPOSITORY and c['sourceCommit'] == PRODUCER_COMMIT, 'PRODUCER_PIN')
    match = re.fullmatch('https://github.com/' + REPOSITORY + '/actions/runs/([1-9][0-9]*)', c['runUrl']) if isinstance(c['runUrl'], str) else None
    require(match and type(c['artifactId']) is int and c['artifactId'] > 0 and hexval(c['artifactSha256']), 'ARTIFACT_IDENTITY')
    require(c['artifactName'] == 'armored-v004-r1-technical-source-' + match.group(1) + '-1', 'ARTIFACT_NAME')
    require(isinstance(c['files'], list) and len(c['files']) == 4, 'INPUT_COUNT')
    for f in c['files']:
        require(isinstance(f, dict) and set(f) == {'file','sha256'} and f['file'] in INPUT_FILES and hexval(f['sha256']), 'INPUT_PIN')
    require({f['file'] for f in c['files']} == INPUT_FILES, 'INPUT_SET')
    sys.path.insert(0,str(ROOT/'tasks/desert-rv/art/import-candidate'))
    from strict_output import contract_shape
    contract_shape(c)
    return c

def validate(env, event, head, parents, request_raw, tracked_request, request_in_parent, changed, manifest_raw, state_raw, contract_raw):
    require(hexval(BASE, 40), 'UNFINALIZED_PARENT')
    require(env.get('GITHUB_ACTIONS') == 'true' and env.get('GITHUB_REPOSITORY') == REPOSITORY and env.get('GITHUB_REPOSITORY_VISIBILITY') == 'public', 'REPOSITORY')
    require(env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and env.get('RUNNER_OS') == 'Linux', 'RUNNER')
    require(env.get('GITHUB_ACTOR') == OWNER and env.get('GITHUB_TRIGGERING_ACTOR') == OWNER, 'ACTOR')
    require(env.get('GITHUB_REF') == 'refs/heads/main' and env.get('GITHUB_EVENT_NAME') == 'push', 'EVENT_BRANCH')
    require(env.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/' + WORKFLOW + '@refs/heads/main', 'WORKFLOW')
    require(hexval(head,40) and head != BASE and env.get('GITHUB_SHA') == head and env.get('GITHUB_WORKFLOW_SHA') == head, 'HEAD')
    require(re.fullmatch('[1-9][0-9]*', env.get('GITHUB_RUN_ID','')) and env.get('GITHUB_RUN_ATTEMPT') == '1', 'REPLAY')
    require(isinstance(event,dict) and event.get('before') == BASE and event.get('after') == head and event.get('ref') == 'refs/heads/main', 'PUSH_IDENTITY')
    require(event.get('created') is False and event.get('deleted') is False and event.get('forced') is False, 'PUSH_KIND')
    repository = event.get('repository', {})
    require(isinstance(repository,dict) and repository.get('full_name') == REPOSITORY and repository.get('private') is False and repository.get('fork') is False and repository.get('default_branch') == 'main' and repository.get('owner',{}).get('login') == OWNER, 'PUSH_REPOSITORY')
    require(event.get('head_commit',{}).get('id') == head and event.get('sender',{}).get('login') == OWNER, 'PUSH_AUTHOR')
    require(parents == [BASE], 'PARENT')
    require(request_in_parent is False and request_raw == tracked_request, 'REQUEST_GIT')
    r = decode(request_raw,4096)
    require(isinstance(r,dict) and set(r) == {'schema','requestId','baseCommit','contractSha256','filesManifestSha256','sourceStateSha256'}, 'REQUEST_KEYS')
    require(type(r['schema']) is int and r['schema'] == 1 and r['requestId'] == REQUEST_ID and r['baseCommit'] == BASE, 'REQUEST_IDENTITY')
    require(r['contractSha256'] == CONTRACT_SHA and r['filesManifestSha256'] == sha(manifest_raw) and r['sourceStateSha256'] == sha(state_raw), 'REQUEST_PIN')
    parse_contract(contract_raw)
    m = decode(manifest_raw)
    require(isinstance(m,dict) and set(m) == {'schema','requestId','baseCommit','files'} and type(m['schema']) is int and m['schema'] == 1 and m['requestId'] == REQUEST_ID and m['baseCommit'] == BASE, 'MANIFEST_IDENTITY')
    require(isinstance(m['files'],list) and len(m['files']) == len(PAYLOAD_PATHS), 'MANIFEST_COUNT')
    for item in m['files']:
        require(isinstance(item,dict) and set(item) == {'path','sha256','priorSha256','size','mode'}, 'FILE_KEYS')
        require(item['path'] in PAYLOAD_PATHS and hexval(item['sha256']) and (item['priorSha256'] is None or hexval(item['priorSha256'])) and type(item['size']) is int and 0 < item['size'] <= 1024*1024 and item['mode'] == '100644', 'FILE_IDENTITY')
    require({x['path'] for x in m['files']} == PAYLOAD_PATHS, 'MANIFEST_PATHS')
    require(len(changed) == len(set(changed)) and set(changed) == PAYLOAD_PATHS | {REQUEST,MANIFEST,SOURCE_STATE}, 'CHANGED_SET')
    return m

def git(root,*args): return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL)
def safe_bytes(path,limit=4*1024*1024):
    require(path.is_file() and not any(p.is_symlink() for p in (path,*path.parents)), 'INPUT_FILE')
    require(path.stat().st_size <= limit, 'INPUT_SIZE'); return path.read_bytes()
def tracked_bytes(root,path,ref='HEAD',limit=4*1024*1024):
    row=git(root,'ls-tree',ref,'--',path).decode().strip().split('\t')
    require(len(row)==2 and row[1]==path, 'TRACKED_PATH')
    fields=row[0].split(); require(len(fields)==3 and fields[:2]==['100644','blob'], 'GIT_MODE')
    size=int(git(root,'cat-file','-s',fields[2])); require(size<=limit, 'TRACKED_SIZE')
    raw=git(root,'cat-file','blob',fields[2]); require(len(raw)==size, 'TRACKED_SIZE'); return raw
def exists_at(root,ref,path):
    return subprocess.run(['git','cat-file','-e',ref+':'+path],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0

def verify(root,env):
    require(hexval(BASE,40), 'UNFINALIZED_PARENT')
    head=git(root,'rev-parse','HEAD').decode().strip()
    parents=[x.split(' ',1)[1] for x in git(root,'cat-file','-p','HEAD').decode().split('\n\n',1)[0].splitlines() if x.startswith('parent ')]
    require(parents==[BASE], 'PARENT');git(root,'cat-file','-e',BASE+'^{commit}')
    event=decode(safe_bytes(Path(env.get('GITHUB_EVENT_PATH',''))))
    tracked={}
    for name in (REQUEST,MANIFEST,SOURCE_STATE,CONTRACT):
        raw=safe_bytes(root/name);require(raw==tracked_bytes(root,name), 'TRACKED_CONTROL');tracked[name]=raw
    changed=git(root,'diff-tree','--no-commit-id','--name-only','-r','HEAD').decode().splitlines()
    manifest=validate(env,event,head,parents,tracked[REQUEST],tracked[REQUEST],exists_at(root,BASE,REQUEST),changed,tracked[MANIFEST],tracked[SOURCE_STATE],tracked[CONTRACT])
    for item in manifest['files']:
        raw=safe_bytes(root/item['path']);require(raw==tracked_bytes(root,item['path']) and len(raw)==item['size'] and sha(raw)==item['sha256'], 'PAYLOAD_BYTES')
        prior=sha(tracked_bytes(root,item['path'],BASE)) if exists_at(root,BASE,item['path']) else None
        require(prior==item['priorSha256'], 'PRIOR_BYTES')
    return parse_contract(tracked[CONTRACT])

def verify_input(root,env):
    c=verify(root,env);directory=root/'tasks/desert-rv/unity/CandidateImportInput'
    require(safe_bytes(directory/'contract.json')==safe_bytes(root/CONTRACT), 'STAGED_CONTRACT')
    run=decode(safe_bytes(directory/'run.json'));artifact=decode(safe_bytes(directory/'artifact.json'))
    from importlib import import_module
    sys.path.insert(0,str(root/'tasks/desert-rv/art/import-candidate'))
    import_module('stage_artifact').verify(c,run,artifact,directory/'artifact.zip')
    require(run.get('event')=='push' and run.get('path')==PRODUCER_WORKFLOW and run.get('head_branch')=='main' and run.get('run_attempt')==1 and run.get('actor',{}).get('login')==OWNER and run.get('triggering_actor',{}).get('login')==OWNER, 'PRODUCER_RUN')
    require(run.get('repository',{}).get('private') is False and run.get('repository',{}).get('fork') is False, 'PRODUCER_REPOSITORY')
    require(artifact.get('id')==c['artifactId'], 'PRODUCER_ARTIFACT')
    with zipfile.ZipFile(directory/'artifact.zip') as archive:
        def member(name):
            require(archive.getinfo(name).file_size<=1024*1024, 'PRODUCER_METADATA_SIZE');return archive.read(name)
        require(sha(member('source-manifest.json'))==ART_MANIFEST_SHA and sha(member('execution-manifest.json'))==EXECUTION_MANIFEST_SHA, 'PRODUCER_MANIFESTS')
        declaration=decode(member('producer-contract.json'))
        require(declaration.get('scope')=='FULL_CANDIDATE' and declaration.get('status')=='FULL_SOURCE_ASSETS_NOT_UNITY_APPROVAL' and declaration.get('errors')==[] and declaration.get('artSourceCommit')==ART_SOURCE_COMMIT and declaration.get('executionCommit')==PRODUCER_COMMIT and str(declaration.get('runId'))==str(run['id']) and declaration.get('sourceManifestSha256')==ART_MANIFEST_SHA and declaration.get('executionManifestSha256')==EXECUTION_MANIFEST_SHA, 'PRODUCER_DECLARATION')
        require(declaration.get('visualApproved') is False and declaration.get('unityVerified') is False, 'PRODUCER_NOT_APPROVAL')
    for item in c['files']:
        raw=safe_bytes(directory/'payload'/item['file'],512*1024*1024);require(sha(raw)==item['sha256'], 'STAGED_PAYLOAD')
        if item['file'].endswith('.png'):
            import struct
            require(raw[:8]==b'\x89PNG\r\n\x1a\n' and len(raw)>=24 and struct.unpack('>II',raw[16:24])==(1024,1024), 'TEXTURE_1024')
            from PIL import Image
            with Image.open(directory/'payload'/item['file']) as picture:
                require(picture.format=='PNG' and picture.size==(1024,1024), 'TEXTURE_1024');picture.verify()
            with Image.open(directory/'payload'/item['file']) as picture:picture.load()
    return c

def main():
    require(sys.argv[1:] in ([],['--verify-only'],['--verify-input'],['--native-gate']), 'ARGUMENTS')
    mode=sys.argv[1:];verify(ROOT,os.environ)
    if mode==['--verify-input']:verify_input(ROOT,os.environ)
    elif mode==['--native-gate']:
        sys.path.insert(0,str(ROOT/'tasks/desert-rv/art/import-candidate'))
        from strict_output import native_report
        from candidate_native_cases import NATIVE_COUNT
        native_hash=native_report(ROOT/'tasks/desert-rv')
        print('ARMORED_STRICT_NATIVE_GATE cases='+str(NATIVE_COUNT)+' xmlSha256='+native_hash+' approved=false')
    elif not mode:
        with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream:
            stream.write('contract='+CONTRACT+'\ncontract_sha256='+CONTRACT_SHA+'\n')
    print('ARMORED_V004_STRICT_FIXED_PUSH_VERIFIED_NOT_ACCEPTED')
if __name__=='__main__':main()
