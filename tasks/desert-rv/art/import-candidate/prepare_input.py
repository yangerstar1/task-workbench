"""Fetch exactly the reviewed contract's GitHub artifact using the runner's read-only token."""
import argparse, hashlib, json, os, re, shutil, subprocess
from pathlib import Path
from stage_artifact import stage, require

def api(path):
    return json.loads(subprocess.check_output(['gh','api',path]))

def prepare(contract_path, expected_sha, output, mode):
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted', 'Only hosted Actions execution')
    require(re.fullmatch('[a-f0-9]{64}',expected_sha), 'Exact reviewed contract SHA required')
    require(hashlib.sha256(contract_path.read_bytes()).hexdigest()==expected_sha,'Contract SHA mismatch')
    contract=json.loads(contract_path.read_text())
    require(contract.get('mode')==mode,'Dispatch mode differs from reviewed contract')
    if mode=='STRICT_BINDING':
        if contract.get('kind')=='weapon':
            from weapon_output import contract_shape
        else:
            from strict_output import contract_shape
        contract_shape(contract)
    require(contract['repository']=='yangerstar1/task-workbench','Wrong repository')
    repo=api('/repos/yangerstar1/task-workbench'); require(repo['private'] is False,'Free public repository required')
    match=re.fullmatch('https://github.com/yangerstar1/task-workbench/actions/runs/([0-9]+)',contract['runUrl']); require(match,'Exact run URL required')
    artifact_id=contract['artifactId']; require(type(artifact_id) is int and artifact_id>0,'Exact numeric artifactId required')
    require(not output.exists(),'Input directory exists')
    run=api('/repos/yangerstar1/task-workbench/actions/runs/'+match.group(1))
    artifact=api('/repos/yangerstar1/task-workbench/actions/artifacts/'+str(artifact_id))
    require(artifact['id']==artifact_id,'Artifact ID mismatch')
    output.mkdir(parents=True)
    for name,obj in [('run',run),('artifact',artifact)]: (output/(name+'.json')).write_text(json.dumps(obj))
    shutil.copyfile(contract_path,output/'contract.json')
    with (output/'artifact.zip').open('wb') as stream:
        subprocess.run(['gh','api','/repos/yangerstar1/task-workbench/actions/artifacts/'+str(artifact_id)+'/zip'],stdout=stream,check=True)
    result=stage(output/'contract.json',output/'run.json',output/'artifact.json',output/'artifact.zip',output/'payload')
    (output/'stage-report.json').write_text(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['DISCOVERY_ONLY','STRICT_BINDING'],required=True);p.add_argument('--contract',type=Path,required=True);p.add_argument('--sha256',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    # Only checked-in reviewed contract directory. Paths cannot select secret/host files.
    path=a.contract.resolve(); base=Path('tasks/desert-rv/art/import-candidate/contracts').resolve()
    require(base in path.parents and path.suffix=='.json' and path.is_file(),'Contract must be checked in under contracts/')
    subprocess.run(['git','ls-files','--error-unmatch',str(a.contract)],check=True,stdout=subprocess.DEVNULL)
    prepare(path,a.sha256,a.output,a.mode)
