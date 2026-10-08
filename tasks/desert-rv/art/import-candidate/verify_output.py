"""Export only verified discovery evidence; failures expose safe codes, never logs."""
import hashlib
import json
import re
import os
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET

EXPECTED='DesertRV.Tests.CandidateArtImportTests.ExecutePinnedDiscoveryOrBindingDiagnostics'
class EvidenceError(ValueError): pass
def require(ok,code):
    if not ok: raise EvidenceError(code)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def safe_file(p):
    require(p.is_file() and not p.is_symlink() and all(not a.is_symlink() for a in p.parents),'UNSAFE_FILE')
    require(p.stat().st_size<=512*1024*1024,'FILE_TOO_LARGE')
def export(root,output,native='success',protected='success'):
    require(not output.exists(),'EXPORT_ALREADY_EXISTS')
    output.mkdir(parents=True)
    summary={'status':'FAILED_NOT_ACCEPTED','approved':False,'errorCode':'UNVERIFIED_INPUT'}
    head=os.environ.get('GITHUB_SHA','');run=os.environ.get('GITHUB_RUN_ID','')
    if re.fullmatch('[a-f0-9]{40}',head) and re.fullmatch('[0-9]+',run):
        summary.update(importCommit=head,importRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/'+run)
    try:
        contract_path=root/'unity/CandidateImportInput/contract.json';safe_file(contract_path)
        contract=json.loads(contract_path.read_text())
        require(contract.get('mode')=='DISCOVERY_ONLY','DISCOVERY_ONLY_EXPORT')
        require(re.fullmatch('[a-z0-9][a-z0-9-]{3,79}',contract.get('id','')),'INVALID_ID')
        require(re.fullmatch('[a-f0-9]{40}',contract.get('sourceCommit','')),'INVALID_SOURCE')
        require(re.fullmatch('[a-f0-9]{64}',contract.get('artifactSha256','')),'INVALID_HASH')
        require(re.fullmatch('https://github.com/yangerstar1/task-workbench/actions/runs/[0-9]+',contract.get('runUrl','')),'INVALID_RUN')
        summary.update(sourceCommit=contract['sourceCommit'],runUrl=contract['runUrl'],artifactSha256=contract['artifactSha256'],contractSha256=sha(contract_path))
        require(native=='success','NATIVE_FAILED');require(protected=='success','PROTECTED_SOURCE_FAILED')
        cases=[]
        for p in (root/'artifacts/candidate-art').rglob('*.xml'):
            safe_file(p)
            try: cases.extend(ET.parse(p).getroot().iter('test-case'))
            except ET.ParseError: continue
        matches=[c for c in cases if c.attrib.get('fullname')==EXPECTED]
        require(len(matches)==1 and matches[0].get('result')=='Passed','NATIVE_CASE_MISSING_OR_FAILED')
        evidence=root/'unity/JourneyEvidence/CandidateArtDiscovery/discovery-report.json';safe_file(evidence)
        report=json.loads(evidence.read_text())
        require(set(report)<=set('mode status scope contractSha256 runUrl sourceCommit artifactName artifactSha256 approved bindingCalibrated limitation models failures'.split()),'REPORT_EXTRA_FIELDS')
        require(report.get('mode')=='DISCOVERY_ONLY' and report.get('scope')==contract['scope'],'MODE_SCOPE_MISMATCH')
        require(report.get('status')=='discovered-unreviewed-not-bound' and report.get('failures')==[],'DISCOVERY_FAILED')
        require(report.get('approved') is False and report.get('bindingCalibrated') is False,'APPROVAL_FORBIDDEN')
        for key in ('sourceCommit','runUrl','artifactName','artifactSha256'):
            require(report.get(key)==contract[key],'REPORT_IDENTITY_MISMATCH')
        require(report.get('contractSha256')==sha(contract_path),'REPORT_CONTRACT_MISMATCH')
        files={f['file']:f['sha256'] for f in contract['files']}
        for name,h in files.items():
            require(re.fullmatch(r'[A-Za-z0-9_-]+\.(fbx|png|tga)',name) and re.fullmatch('[a-f0-9]{64}',h),'UNSAFE_CONTRACT_FILE')
        models=report.get('models',[])
        require(len(models)==len({m.get('file') for m in models}),'DUPLICATE_MODELS')
        require(models and {m.get('file') for m in models}=={n for n in files if n.endswith('.fbx')},'MODEL_SET_MISMATCH')
        base=root/'unity/Assets/DesertRV/CandidateArtDiscovery';candidate=base/contract['id']
        require(not (root/'unity/Assets/DesertRV/CandidateArtImports').exists(),'STRICT_OUTPUT_FORBIDDEN')
        allowed={Path(contract['id']+'.meta'),Path(contract['id'])/'Source.meta',Path(contract['id'])/'discovery-contract.json',Path(contract['id'])/'discovery-contract.json.meta'}
        allowed.update(Path(contract['id'])/'Source'/n for n in files)
        allowed.update(Path(contract['id'])/'Source'/(n+'.meta') for n in files)
        actual=set()
        for p in base.rglob('*'):
            require(not p.is_symlink(),'SYMLINK_FORBIDDEN')
            if p.is_file(): actual.add(p.relative_to(base))
        require(actual==allowed,'OUTPUT_ALLOWLIST_MISMATCH')
        for n,h in files.items(): require(sha(candidate/'Source'/n)==h,'OUTPUT_SOURCE_HASH_MISMATCH')
        require(sha(candidate/'discovery-contract.json')==sha(contract_path),'OUTPUT_CONTRACT_MISMATCH')
        staged=[(evidence,Path('discovery-report.json'))]
        if Path(str(base)+'.meta').exists(): staged.append((Path(str(base)+'.meta'),Path('CandidateArtDiscovery.meta')))
        for rel in sorted(allowed): staged.append((base/rel,Path('CandidateArtDiscovery')/rel))
        for p,rel in staged:
            safe_file(p)
            if p.suffix=='.meta':
                require(p.stat().st_size<1000000 and re.search(r'^guid: [a-f0-9]{32}$',p.read_text(),re.M),'INVALID_META')
        # All checks complete before copying any payload into export.
        records=[]
        for p,rel in staged:
            dest=output/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
            records.append({'path':rel.as_posix(),'sha256':sha(dest),'bytes':dest.stat().st_size})
        summary.update(status='DISCOVERED_UNREVIEWED_NOT_BOUND',errorCode=None,files=records)
    except EvidenceError as e:
        summary['errorCode']=str(e)
        raise
    except Exception:
        summary['errorCode']='INVALID_EVIDENCE'
        raise EvidenceError('INVALID_EVIDENCE') from None
    finally:
        (output/'receipt.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--protected',required=True);a=p.parse_args()
    try: export(Path('tasks/desert-rv'),Path('tasks/desert-rv/artifacts/candidate-art-export'),a.native,a.protected)
    except EvidenceError as e: raise SystemExit(str(e))
