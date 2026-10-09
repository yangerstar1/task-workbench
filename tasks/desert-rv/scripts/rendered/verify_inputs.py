#!/usr/bin/env python3
"""Read-only preflight: missing prepared game input is a blocker, never authored here."""
import argparse,hashlib,json,math,os,pathlib,re,subprocess
ROOT=pathlib.Path(os.environ.get('GITHUB_WORKSPACE',os.getcwd())).absolute()
def require(ok):
    if not ok:raise ValueError('rendered-input-preflight-failed')
def path(value):
    require(isinstance(value,str) and value and not pathlib.PurePosixPath(value).is_absolute() and '..' not in pathlib.PurePosixPath(value).parts)
    p=ROOT/value;require(p.is_file() and not p.is_symlink() and not any(x.is_symlink() for x in p.parents));return p
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(value,sha):
    require(re.fullmatch('[a-f0-9]{64}',sha or ''));p=path(value);require(p.stat().st_size<16*1024**2 and digest(p)==sha);return json.loads(p.read_text())
def verify_gameci(folder,pins):
    require(subprocess.check_output(['git','-C',str(folder),'rev-parse','HEAD'],text=True).strip()==pins['commit'])
    for name,want in pins['files'].items():
        p=folder/name;require(p.is_file() and not p.is_symlink() and not any(x.is_symlink() for x in p.parents));data=p.read_bytes()
        require(hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==want)
def verify(mode,receipt='',receipt_sha='',scope='',scope_sha='',plan='',plan_sha=''):
    require(os.environ.get('GITHUB_REPOSITORY')=='yangerstar1/task-workbench' and os.environ.get('GITHUB_REF')=='refs/heads/main')
    require(os.environ.get('GITHUB_ACTOR')=='yangerstar1' and os.environ.get('GITHUB_TRIGGERING_ACTOR')=='yangerstar1')
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted')
    require(os.environ.get('GITHUB_REPOSITORY_VISIBILITY')=='public' and os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch')
    for name in ('rendered-private-evidence','rendered-export','rendered-export-failed','rendered-control-export','rendered-public-export'):
        require(not (ROOT/'tasks/desert-rv'/name).exists() and not (ROOT/'tasks/desert-rv'/name).is_symlink())
    if mode=='window-smoke':
        path('tasks/desert-rv/unity/Assets/DesertRV/Scenes/BodyStudy.unity');return
    require(mode=='journey')
    r=load(receipt,receipt_sha);require(r.get('status')=='STRICT_CANDIDATES_BOUND_UNREVIEWED' and r.get('candidateOnly') is True)
    require(r.get('sourceCommit')==os.environ['GITHUB_SHA'] and r.get('protectedSourcesUnchanged') is True)
    require(r.get('failures')==[] and r.get('rolledBack') is False and all(r.get(k) is False for k in ('visualReviewed','gameplayReviewed','audioAuditioned')))
    outputs=r.get('outputs');require(isinstance(outputs,list) and outputs)
    names=set()
    for f in outputs:
        require(isinstance(f,dict));p=path('tasks/desert-rv/unity/'+f['path']);require(digest(p)==f['sha256']);names.add(f['path'])
    require({'Assets/DesertRV/Scenes/Journey/'+n+'.unity' for n in ('JourneyBootstrap','FirstStation','Scrapyard','NightBeacon')}<=names)
    s=load(scope,scope_sha);require(s.get('label')=='EDITOR_DIAGNOSTIC_UNAPPROVED_CONTENT' and s.get('sourceCommit')==os.environ['GITHUB_SHA'])
    require(isinstance(s.get('files'),list) and s['files'])
    for pin in s['files']:
        require(digest(path('tasks/desert-rv/unity/'+pin['path']))==pin['sha256'])
    p=load(plan,plan_sha);maximum=p.get('maximumWallSeconds');require(type(maximum) in (int,float) and math.isfinite(maximum) and 0<maximum<=120)
    require(isinstance(p.get('steps'),list) and p['steps']);total=0
    for step in p['steps']:
        duration=step.get('seconds');require(type(duration) in (int,float) and math.isfinite(duration) and duration>0);total+=duration
        require(step.get('command','') in ('','Begin','Pause','Restart','RetryLoad'))
    require(total<=maximum)
    # The pinned plan must cite the observation reviewed by the operator; this does not manufacture it.
    observation=p.get('observedEvidence',{})
    require(re.fullmatch(r'https://github\.com/yangerstar1/task-workbench/actions/runs/[0-9]+',observation.get('runUrl','')))
    require(re.fullmatch('[a-f0-9]{64}',observation.get('artifactSha256','')))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--gameci');ap.add_argument('--mode',choices=['window-smoke','journey'],required=True);a=ap.parse_args()
    try:
        if a.gameci:verify_gameci(pathlib.Path(a.gameci),json.loads(pathlib.Path(__file__).with_name('official-gameci-pins.json').read_text()))
        verify(a.mode,*(os.environ.get(k,'') for k in ('PREPARATION_RECEIPT','PREPARATION_SHA256','DIAGNOSTIC_SCOPE','SCOPE_SHA256','INPUT_PLAN','PLAN_SHA256')))
    except Exception:print('RENDERED_INPUT_PREFLIGHT_FAILED');return 1
    print('RENDERED_INPUT_PREFLIGHT_PASS_NOT_GAMEPLAY_APPROVAL');return 0
if __name__=='__main__':raise SystemExit(main())
