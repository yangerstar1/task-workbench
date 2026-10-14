#!/usr/bin/env python3
"""Two-stage composition. Never launches Unity/Docker or fetches network/credentials.
CI prepare invokes the unchanged source guard. CI finalize reruns pinned validators.
Postdownload requires outside-supplied artifact digest/identity and redoes the same gates.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
import verify_and_measure as inc
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import post_capture_safety as telemetry

HERE = Path(__file__).resolve().parent
TASK = 'tasks/lottery-shop'
EVIDENCE = TASK+'/evidence/visual-candidate'
PREPARED = TASK+'/artifacts/counter-light-diagnostic/prepared-context.json'
SCOPE = 'COMPOSED_COUNTER_LIGHT_DIAGNOSTIC_NOT_ART_APPROVAL_NOT_G3_PASS'
STAGES = ('capture','regression-edit','regression-play-core','regression-play-world')
ENV_KEYS = {'GITHUB_EVENT_NAME':'push','GITHUB_REPOSITORY':'yangerstar1/task-workbench','GITHUB_REPOSITORY_OWNER':'yangerstar1',
            'GITHUB_ACTOR':'yangerstar1','GITHUB_TRIGGERING_ACTOR':'yangerstar1','GITHUB_REF':'refs/heads/lottery-shop-g0-20261011'}
MUTATION_ALLOWLIST = {
 TASK+'/unity/Assets/G3/Shop/Resources/G3/Shop/Textures/Pothos_v26_BaseColor.png.meta',
 TASK+'/unity/Assets/G3/Shop/Resources/G3/Shop/Textures/Pothos_v26_Normal.png.meta',
 TASK+'/unity/Assets/G3/Shop/Resources/G3/Shop/Textures/Pothos_v26_Roughness.png.meta',
 TASK+'/unity/Assets/GeneratedProbe/Probe.unity', TASK+'/unity/Assets/GeneratedProbe/ProbeSurface.mat',
 TASK+'/unity/ProjectSettings/GraphicsSettings.asset', TASK+'/unity/ProjectSettings/ProjectSettings.asset',
 TASK+'/unity/ProjectSettings/QualitySettings.asset'}
require = inc.require

def verify_native_budget(stage, process):
    # Exact existing process contracts; this check does not set native timeouts.
    budgets = {'capture': 1800, 'regression-edit': 480,
               'regression-play-core': 720, 'regression-play-world': 480}
    budget = process.get('processBudgetSeconds')
    require(stage in budgets and type(budget) is int and budget == budgets[stage],
            'ORIGINAL_NATIVE_BUDGET_CHANGED')

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def compact(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def read(p, maximum=2097152): return inc.load(p, maximum)
def write(p,v): p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(json.dumps(v,indent=2,sort_keys=True).encode()+b'\n')
def identity(v, wanted): require(all(v.get(k)==value for k,value in wanted.items()),'UPSTREAM_IDENTITY_MISMATCH')
def fixed(p):
    require(p.is_file() and p.resolve()==p.absolute(),'MISSING_OR_LINKED_EVIDENCE: '+p.name)
    return p

def modules():
    pins=read(HERE/'dependency-pins.json')
    for name,expected in pins.items(): require(digest(fixed(HERE/'pinned_dependencies'/name))==expected,'PINNED_DEPENDENCY_CHANGED')
    sys.path.insert(0,str(HERE/'pinned_dependencies'))
    for name in ('visual_candidate_ci','probe_ci','play_split_ci','reflection_bake_ci','activation_probe'):
        if name in sys.modules:
            require(Path(sys.modules[name].__file__).resolve()==(HERE/'pinned_dependencies'/(name+'.py')).resolve(),'DEPENDENCY_MODULE_SHADOWED')
    return importlib.import_module('visual_candidate_ci'),importlib.import_module('play_split_ci'),importlib.import_module('activation_probe')

def git(root,*args):
    p=subprocess.run(['git','-C',str(root),*args],capture_output=True,check=True,timeout=60)
    require(len(p.stdout)<=16*1024*1024,'GIT_READ_BOUND')
    return p.stdout

def context(root):
    require(all(os.environ.get(k)==v for k,v in ENV_KEYS.items()),'CI_CONTEXT_REQUIRED')
    require(os.environ.get('GITHUB_WORKFLOW_REF','').split('@')[0] == 'yangerstar1/task-workbench/.github/workflows/lottery-visual-candidate.yml','EXPECTED_WORKFLOW_CONTEXT_REQUIRED')
    source=os.environ.get('GITHUB_SHA','');run=os.environ.get('GITHUB_RUN_ID','');attempt=os.environ.get('GITHUB_RUN_ATTEMPT','')
    require(re.fullmatch('[0-9a-f]{40}',source) and re.fullmatch('[1-9][0-9]*',run) and attempt=='1','CI_IDENTITY_INVALID')
    require(git(root,'rev-parse','HEAD').decode().strip()==source,'CI_CHECKOUT_MISMATCH')
    reviewed=git(root,'rev-parse','HEAD^').decode().strip()
    return {'sourceCommit':source,'reviewedCandidateCommit':reviewed,'runId':run,'runAttempt':attempt}

def code_contract(root, reviewed):
    contract=read(HERE/'code-contract.json')
    require(git(root,'show',reviewed+':'+TASK+'/scripts/counter_light_diagnostics/code-contract.json') == (HERE/'code-contract.json').read_bytes(), 'CODE_CONTRACT_NOT_IN_REVIEWED_SOURCE')
    for row in contract['files']:
        committed=git(root,'show',reviewed+':'+row['repositoryPath'])
        require(hashlib.sha256(committed).hexdigest()==row['sha256'],'REVIEWED_HELPER_PLAN_OR_VALIDATOR_MISSING_OR_CHANGED')
        require(digest(fixed(root/row['repositoryPath']))==row['sha256'],'EXECUTING_CODE_DIFFERS_FROM_REVIEW')
    return contract

def prepare(root):
    telemetry.checkpoint('CONTEXT')
    v,_,_=modules(); ident=context(root)
    # This is the actual unchanged gate, before native/import mutations.
    original=v.guard(root); identity(original,ident)
    v.snapshot(root,False)
    contract=code_contract(root,ident['reviewedCandidateCommit'])
    receipt={'schemaVersion':1,'scope':SCOPE,'repository':'yangerstar1/task-workbench','workflowPath':'.github/workflows/lottery-visual-candidate.yml',**ident,'guardSourceReceiptSha256':digest(root/EVIDENCE/'source-receipt.json'),
             'sourceBeforeSha256':digest(root/EVIDENCE/'source-before.json'), 'codeContractSha256':hashlib.sha256(compact(contract)).hexdigest(),
             'dependencyPinsSha256':digest(HERE/'dependency-pins.json')}
    write(root/PREPARED,receipt)
    return receipt

@contextmanager
def identity_env(ident):
    mapping={'GITHUB_SHA':ident['sourceCommit'],'GITHUB_RUN_ID':ident['runId'],'GITHUB_RUN_ATTEMPT':ident['runAttempt']}
    old={k:os.environ.get(k) for k in mapping};os.environ.update(mapping)
    try: yield
    finally:
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v

def native_process(row, phase, ident, ap):
    identity(row,ident)
    require(row.get('scope')=='DIAGNOSTIC_VISUAL_CANDIDATE_NOT_G3_PASS' and row.get('phase')==phase and row.get('schemaVersion')==1,'NATIVE_PROCESS_SCOPE')
    require(row.get('image')==ap.IMAGE and row.get('mechanismSourcePin')==ap.PIN,'NATIVE_MECHANISM_DRIFT')
    require(row.get('status')=='NATIVE_SUCCEEDED' and all(type(row.get(k)) is int and row[k]==v for k,v in {'nativeExitCode':0,'dockerExitCode':0,'nativeExitMarkerCount':1}.items()),'NATIVE_PROCESS_FAILED')
    require(row.get('compilerErrors')==[] and row.get('observations',{}).get('invalidLicenseXml400')==0 and row.get('observations',{}).get('nativeActivationAborted')==0,'NATIVE_COMPILER_OR_LICENSE_FAILURE')
    if phase=='capture':require(row.get('counterLightDiagnostic') is True and row.get('counterLightDiagnosticFault')=='','MISSING_NATIVE_DIAGNOSTIC_OPT_IN')


def input_paths(evidence, diag):
    required=['source-receipt.json','source-before.json','source-after.json','source-changes.json','safe-finish.json','safe-session.json']
    for stage in STAGES:required += ['safe-'+stage+'.json',stage+'/raw-test-results.xml',stage+'/test-receipt.json']
    required += ['captures/capture-receipt.json']+['captures/'+f+'.png' for f in inc.FRAMES]
    paths={'upstream/'+name:fixed(evidence/name) for name in required}
    paths.update({'diagnostic/'+name:fixed(diag/name) for name in ['diagnostic-receipt.json']+[inc.filename(x) for x in inc.CASES+['baseline-before','baseline-after']]})
    return paths


def verify_bound_inputs(bundle, ident):
    """Called only after CI context/source checks, or external archive digest verification.
    A caller-controlled 'passed' field is never used instead of these computations.
    """
    v,split,ap=modules();up=bundle/'upstream';diag=bundle/'diagnostic'
    if telemetry.ACTIVE: telemetry.checkpoint('UPSTREAM_NATIVE')
    prepared=read(bundle/'prepared-context.json');identity(prepared,ident)
    require(prepared['scope']==SCOPE and prepared['schemaVersion']==1 and prepared.get('repository')=='yangerstar1/task-workbench' and prepared.get('workflowPath')=='.github/workflows/lottery-visual-candidate.yml','PREPARED_CONTEXT_SCOPE')
    require(prepared['guardSourceReceiptSha256']==digest(up/'source-receipt.json') and prepared['sourceBeforeSha256']==digest(up/'source-before.json'),'REAL_GUARD_INPUT_BINDING_MISMATCH')
    source=read(up/'source-receipt.json');identity(source,ident)
    require(source.get('sourceReview',{}).get('sourceCommit')==ident['reviewedCandidateCommit'] and source.get('sourceReview',{}).get('status')=='APPROVED_FOR_DIAGNOSTIC_CAPTURE_ONLY','REVIEWED_SOURCE_NOT_APPROVED')
    for phase in STAGES:native_process(read(up/('safe-'+phase+'.json')),phase,ident,ap)
    native_process(read(up/'safe-finish.json'),'finish',ident,ap)
    finish=read(up/'safe-finish.json');session=read(up/'safe-session.json');identity(session,ident)
    require(finish.get('cleanup')=={'status':'ABSENCE_VERIFIED','removalExitCode':0} and session.get('status')=='CLOSED' and session.get('cleanup')==finish['cleanup'],'OWNED_NATIVE_CLEANUP_UNVERIFIED')
    if telemetry.ACTIVE: telemetry.checkpoint('SOURCE_MUTATION')
    before=read(up/'source-before.json');after=read(up/'source-after.json');changes=read(up/'source-changes.json')
    for row in (before,after,changes):identity(row,ident)
    old={x['path']:x for x in before['files']};new={x['path']:x for x in after['files']}
    require(len(old)==len(before['files']) and len(new)==len(after['files']) and set(old)==set(new),'SOURCE_SNAPSHOT_COVERAGE_DRIFT')
    changed={k for k in old if old[k]!=new[k]}
    require(changed==set(changes['changedPaths']) and changed<=MUTATION_ALLOWLIST,'UNREVIEWED_SOURCE_MUTATION')
    contract=read(bundle/'code-contract.json')
    require(hashlib.sha256(compact(contract)).hexdigest()==prepared['codeContractSha256'],'CODE_CONTRACT_NOT_PREPARED')
    for row in contract['files']:
        require(row['repositoryPath'] in old and old[row['repositoryPath']]['sha256']==row['sha256'] and old[row['repositoryPath']]==new[row['repositoryPath']],'REVIEWED_DIAGNOSTIC_CODE_MUTATED_OR_MISSING')
    results={}
    # Rebuild only disposable validator input paths. No Unity invocation, no changes to original evidence.
    with tempfile.TemporaryDirectory(prefix='counter-light-gates-') as tmp, identity_env(ident):
        root=Path(tmp);ev=root/EVIDENCE;shutil.copytree(up,ev)
        ci=root/TASK/'ci';ci.mkdir(parents=True)
        for name in ('g2-test-contract.json','g3-test-contract.json'):shutil.copyfile(HERE/'pinned_dependencies'/name,ci/name)
        for stage in STAGES:
            if telemetry.ACTIVE: telemetry.checkpoint({'capture':'REGRESSION_CAPTURE','regression-edit':'REGRESSION_EDIT','regression-play-core':'REGRESSION_CORE','regression-play-world':'REGRESSION_WORLD'}[stage])
            old_receipt=read(up/stage/'test-receipt.json');identity(old_receipt,ident)
            xml=up/stage/'raw-test-results.xml'
            require(old_receipt.get('rawXmlSha256')==digest(xml),'STALE_XML_RECEIPT_BINDING')
            phase_dir = 'visual-candidate' if stage=='capture' else 'visual-regression-edit' if stage=='regression-edit' else split.FOLDERS[stage.removeprefix('regression-play-')]
            dest=root/TASK/'artifacts'/phase_dir;dest.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(xml,dest/('editmode-results.xml' if stage=='regression-edit' else 'playmode-results.xml'))
            # Bind actual XML wall times to the current native process as well as hashes.
            import xml.etree.ElementTree as ET
            v.bounded.require_safe_xml(xml.read_bytes()); tree=ET.fromstring(xml.read_bytes())
            process=read(up/('safe-'+stage+'.json')); started=process.get('nativeStartedAtNs')
            require(type(started) is int and started>0,'NATIVE_START_TIME_REQUIRED')
            t0=datetime.fromisoformat(tree.attrib['start-time'].replace('Z','+00:00')).timestamp()
            t1=datetime.fromisoformat(tree.attrib['end-time'].replace('Z','+00:00')).timestamp()
            require(started/1e9-1 <= t0 <= t1 <= started/1e9+process['elapsedMs']/1000+1,'STALE_NATIVE_XML_TIME')
            verify_native_budget(stage, process)
            # Native root/result/assembly/fullname/counters are checked by unchanged originals.
            v.export_tests(root,stage)
            calculated=read(ev/stage/'test-receipt.json')
            require(calculated==old_receipt,'UPSTREAM_NATIVE_RECEIPT_NOT_REPRODUCIBLE')
            results[stage]={'rawXmlSha256':digest(xml),'nativeReceiptSha256':digest(up/('safe-'+stage+'.json'))}
        if telemetry.ACTIVE: telemetry.checkpoint('PLAY_AGGREGATE')
        split.aggregate(root)
        if telemetry.ACTIVE: telemetry.checkpoint('NORMAL_CAPTURE')
        src=root/TASK/'artifacts/visual-candidate/captures';shutil.copytree(up/'captures',src)
        v.export_captures(root,True)
        require(digest(ev/'captures/capture-receipt.json')==digest(up/'captures/capture-receipt.json'),'NORMAL_RECEIPT_REWRITE')
    if telemetry.ACTIVE: telemetry.checkpoint('DIAGNOSTIC_VALIDATE')
    measured=inc._validate_increment(diag,up/'captures',up/'capture/raw-test-results.xml',ident['sourceCommit'])
    return {'recomputedExistingGates':results,'normalReceiptSha256':digest(up/'captures/capture-receipt.json'),
            'diagnosticReceiptSha256':digest(diag/'diagnostic-receipt.json'),'measurements':measured['measurements']}


def finalize(root,diag,output):
    telemetry.checkpoint('CONTEXT')
    ident=context(root)
    telemetry.checkpoint('CONTRACT')
    contract=code_contract(root,ident['reviewedCandidateCommit'])
    telemetry.checkpoint('PREPARED')
    prepared=read(root/PREPARED);identity(prepared,ident)
    require(prepared['dependencyPinsSha256']==digest(HERE/'dependency-pins.json'),'DEPENDENCY_PINS_CHANGED_AFTER_PREPARE')
    require(hashlib.sha256(compact(contract)).hexdigest()==prepared['codeContractSha256'],'CODE_CHANGED_AFTER_PREPARE')
    require(not output.exists(),'BUNDLE_OUTPUT_ALREADY_EXISTS')
    output.mkdir(parents=True)
    telemetry.checkpoint('INPUT_PATHS')
    paths=input_paths(root/EVIDENCE,diag)
    telemetry.checkpoint('COPY_INPUTS')
    for name,source in paths.items():
        destination=output/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
    shutil.copyfile(root/PREPARED,output/'prepared-context.json');write(output/'code-contract.json',contract)
    # No success gate exists unless every call below actually returns successfully.
    result=verify_bound_inputs(output,ident)
    bindings=[{'path':str(p.relative_to(output)),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(output.rglob('*')) if p.is_file()]
    gate={'schemaVersion':1,'scope':SCOPE,**ident,'bindings':bindings,'codeContractSha256':prepared['codeContractSha256'],
          'dependencyPinsSha256':digest(HERE/'dependency-pins.json'),'checks':{k:v for k,v in result.items() if k!='measurements'}}
    telemetry.checkpoint('GATE_WRITE')
    write(output/'counter-light-gate.json',gate)
    return gate


def verify_download(zip_path, expected, expected_artifact_id, expected_artifact_sha256, expected_code_contract_sha256):
    # These expectations MUST originate outside the downloaded archive, from the
    # authenticated repository run/artifact API and independent reviewed-source check.
    require(type(expected_artifact_id) is int and expected_artifact_id>0,'EXTERNAL_ARTIFACT_ID_REQUIRED')
    require(re.fullmatch('[0-9a-f]{64}',expected_artifact_sha256 or '') and digest(fixed(zip_path))==expected_artifact_sha256,'EXTERNAL_ARTIFACT_DIGEST_MISMATCH')
    require(re.fullmatch('[0-9a-f]{64}',expected_code_contract_sha256 or ''),'EXTERNAL_CODE_CONTRACT_DIGEST_REQUIRED')
    require(set(expected)=={'sourceCommit','reviewedCandidateCommit','runId','runAttempt'} and all(expected.values()),'EXTERNAL_EXPECTATIONS_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='counter-light-download-') as tmp:
        root=Path(tmp)
        with zipfile.ZipFile(zip_path) as archive:
            infos=archive.infolist();require(len(infos)<=160 and sum(i.file_size for i in infos)<=256*1024*1024,'ARTIFACT_BOUND')
            seen=set()
            for info in infos:
                p=PurePosixPath(info.filename)
                require(not p.is_absolute() and '..' not in p.parts and '\\' not in info.filename and info.filename not in seen and not stat.S_ISLNK(info.external_attr>>16),'UNSAFE_OR_DUPLICATE_ZIP_ENTRY')
                seen.add(info.filename)
                require(info.file_size<=16*1024*1024,'ARTIFACT_ENTRY_BOUND')
                archive.extract(info,root)
        gate=read(root/'counter-light-gate.json');identity(gate,expected)
        require(gate.get('schemaVersion')==1 and gate.get('scope')==SCOPE,'GATE_SCOPE_MISSING')
        require(gate.get('dependencyPinsSha256')==digest(HERE/'dependency-pins.json'),'GATE_PINNED_VALIDATOR_IDENTITY_MISMATCH')
        require(gate.get('codeContractSha256')==expected_code_contract_sha256,'REVIEWED_HELPER_PLAN_VALIDATOR_IDENTITY_MISMATCH')
        require(hashlib.sha256(compact(read(root/'code-contract.json'))).hexdigest()==expected_code_contract_sha256,'CODE_CONTRACT_DIGEST_MISMATCH')
        local_contract=read(HERE/'code-contract.json')
        require(hashlib.sha256(compact(local_contract)).hexdigest()==expected_code_contract_sha256,'LOCAL_VERIFIER_CONTRACT_IS_NOT_REVIEWED_VERSION')
        for row in local_contract['files']:
            prefix=TASK+'/scripts/counter_light_diagnostics/'
            if row['repositoryPath'].startswith(prefix):
                require(digest(fixed(HERE/row['repositoryPath'][len(prefix):]))==row['sha256'],'LOCAL_VERIFIER_OR_PLAN_VERSION_DRIFT')
        bindings=gate.get('bindings',[]);require(type(bindings) is list and len(bindings)>50,'GATE_BINDINGS_MISSING')
        seen=set()
        for row in bindings:
            rel=PurePosixPath(row['path']);require(not rel.is_absolute() and '..' not in rel.parts and row['path'] not in seen,'UNSAFE_GATE_BINDING')
            seen.add(row['path']);p=fixed(root/row['path'])
            require(p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],'BOUND_EVIDENCE_TAMPERED')
        actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
        require(actual==seen|{'counter-light-gate.json'},'UNBOUND_OR_MISSING_ARTIFACT_FILE')
        result=verify_bound_inputs(root,expected)
        return {'scope':SCOPE,'boundNativeEvidenceRecomputed':True,'externalArtifactId':expected_artifact_id,
                'externalArtifactSha256':expected_artifact_sha256,**expected,**result}


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message): raise ValueError('CLI_ARGUMENTS')

def main():
    p=SafeArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    for mode in ('prepare','finalize'):
        x=sub.add_parser(mode);x.add_argument('--repo-root',type=Path,required=True)
        if mode=='finalize':x.add_argument('--diagnostic',type=Path,required=True);x.add_argument('--output',type=Path,required=True)
    x=sub.add_parser('postdownload');x.add_argument('--archive',type=Path,required=True)
    for flag in ('source-commit','reviewed-commit','run-id','run-attempt','artifact-sha256','code-contract-sha256'):x.add_argument('--expected-'+flag,required=True)
    x.add_argument('--expected-artifact-id',type=int,required=True);x.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.mode in ('prepare','finalize'): telemetry.begin('counter-light',a.mode)
    if a.mode=='prepare':prepare(a.repo_root)
    elif a.mode=='finalize':finalize(a.repo_root,a.diagnostic,a.output)
    else:
        expected={'sourceCommit':a.expected_source_commit,'reviewedCandidateCommit':a.expected_reviewed_commit,'runId':a.expected_run_id,'runAttempt':a.expected_run_attempt}
        result=verify_download(a.archive,expected,a.expected_artifact_id,a.expected_artifact_sha256,a.expected_code_contract_sha256);write(a.output,result)

if __name__=='__main__':
    try:
        main()
        if telemetry.ACTIVE:
            telemetry.checkpoint('DONE');telemetry.persist('COMPLETED','NONE')
    except BaseException as error:
        raise SystemExit(telemetry.fail(error)) from None
