"""Three fixed strict stages in one hosted Unity workspace; existing quality gates remain authoritative."""
import argparse, hashlib, json, os, re, shutil, stat, subprocess, sys
from pathlib import Path
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[4]
ROOT = REPO/'tasks/desert-rv'
PROJECT = ROOT/'unity'
PRIVATE = PROJECT/'JourneyEvidence/JourneyPreparation'
PUBLIC = ROOT/'journey-preparation-export'
IMPORTS = Path('Assets/DesertRV/CandidateArtImports')
KINDS = ('armored','pouncer','weapon')
sys.path.insert(0,str(ROOT/'art/import-candidate'))
from strict_output import read, sha, require, safe, dependency_digest, dependency_input_paths, digest, verify_staged_inventory, rel
from prepare_input import prepare
from verify_output import export

def tree(folder):
    result={}
    if not folder.exists(): return result
    require(folder.is_dir() and not folder.is_symlink(),'PREP_UNSAFE_DIRECTORY')
    for path in sorted(folder.rglob('*')):
        require(not path.is_symlink(),'PREP_SYMLINK')
        if path.is_file(): result[path.relative_to(folder).as_posix()]=sha(path)
        else: require(path.is_dir(),'PREP_NONREGULAR_FILE')
    return result

def directories(folder):
    return {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_dir()}

def expected_directories(files):
    return {p.as_posix() for name in files for p in Path(name).parents if p!=Path('.')}

def protected():
    result={}
    for name in ('Assets','Packages','ProjectSettings'):
        for rel,value in tree(PROJECT/name).items():
            path=(Path(name)/rel).as_posix()
            if not (path==str(IMPORTS)+'.meta' or path.startswith(str(IMPORTS)+'/')): result[path]=value
    return result

def state():
    value=read(PRIVATE/'state.json')
    require(value['sourceCommit']==os.environ.get('GITHUB_SHA') and value['runId']==os.environ.get('GITHUB_RUN_ID'),'PREP_JOB_IDENTITY_CHANGED')
    return value

def save(value):
    (PRIVATE/'state.json').write_text(json.dumps(value,indent=2)+'\n')

def guard():
    require(os.environ.get('GITHUB_REPOSITORY')=='yangerstar1/task-workbench','PREP_REPOSITORY')
    if os.environ.get('GITHUB_REF')!='refs/heads/main':
        sys.path.insert(0,str(ROOT/'scripts'))
        if os.environ.get('GITHUB_REF')=='refs/heads/journey-tracer-shader-fix-6648':
            import journey_tracer_dispatch
            journey_tracer_dispatch.verify(REPO,os.environ)
        else:
            import journey_rebuild_dispatch
            journey_rebuild_dispatch.verify(REPO,os.environ) # Existing fixed recovery branch remains unchanged.
    require(os.environ.get('GITHUB_ACTOR')=='yangerstar1' and os.environ.get('GITHUB_TRIGGERING_ACTOR')=='yangerstar1','PREP_ACTOR')
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted' and os.environ.get('GITHUB_REPOSITORY_VISIBILITY')=='public','PREP_PUBLIC_HOSTED_ONLY')
    require(digest(os.environ.get('GITHUB_SHA'),40) and re.fullmatch('[1-9][0-9]*',os.environ.get('GITHUB_RUN_ID','')),'PREP_JOB_IDENTITY')

def validate_selection(value):
    require(set(value)=={'schema','sources','fx','integration','spawnRootHeightSource'} and value['schema']==1,'PREP_SELECTION_SCHEMA')
    require(value['spawnRootHeightSource']=='scene-physical-floor','PREP_EXPLICIT_SPAWN_ROOT_SOURCE')
    sources=value['sources'];require(isinstance(sources,list) and [s['kind'] for s in sources]==list(KINDS),'PREP_THREE_ORDERED_KINDS')
    ids=[]
    for item in sources:
        require(set(item)=={'kind','contract','sha256'} and digest(item['sha256']),'PREP_SOURCE_SELECTION')
        require(re.fullmatch(r'tasks/desert-rv/art/import-candidate/contracts/[a-z0-9-]+\.json',item['contract']),'PREP_CHECKED_CONTRACT_PATH')
        path=REPO/item['contract'];require(sha(path)==item['sha256'],'PREP_CONTRACT_HASH')
        c=read(path);require(c.get('mode')=='STRICT_BINDING' and c.get('scope')=='FULL_CANDIDATE' and c.get('kind')==item['kind'],'PREP_FULL_STRICT_ONLY')
        module=__import__('strict_output' if item['kind']=='armored' else item['kind']+'_output');module.contract_shape(c);ids.append(c['id'])
    require(len(set(ids))==3,'PREP_DUPLICATE_CANDIDATE_ID')
    require(isinstance(value['fx'],dict) and isinstance(value['integration'],dict),'PREP_AUTHORING_SELECTION')
    arc_pose_source(value['integration'])

def validation_sources():
    files=[ROOT/'art/import-candidate'/name for name in ('strict_output.py','pouncer_output.py','weapon_output.py','verify_output.py','candidate_native_cases.py','foot_contact_output.py','paw_contact_output.py')]
    files+=sorted((PROJECT/'Assets/DesertRV/Tests/CandidateArt').glob('*.cs'))
    require(len(files)>7,'PREP_NATIVE_SOURCE_INVENTORY_MISSING')
    return [dict(path=str(path.relative_to(REPO)),sha256=sha(path)) for path in files]

def native_inventory(folder,expected_sha):
    matches=[path for path in folder.rglob('*.xml') if sha(path)==expected_sha]
    require(len(matches)==1,'PREP_EXACT_NATIVE_XML')
    xml=ET.parse(safe(matches[0])).getroot();cases=list(xml.iter('test-case'));names=[c.get('fullname') for c in cases]
    require(xml.tag=='test-run' and xml.get('result')=='Passed' and cases and all(c.get('result')=='Passed' for c in cases) and
            all(isinstance(n,str) and n for n in names) and len(set(names))==len(names),'PREP_NATIVE_INVENTORY')
    return dict(path=str(matches[0].relative_to(REPO)),sha256=expected_sha),sorted(names)

def init(selection,selection_sha):
    guard();require(re.fullmatch(r'tasks/desert-rv/art/journey-preparation/[a-z0-9-]+\.json',selection) and digest(selection_sha),'PREP_SELECTION_PATH')
    path=REPO/selection;require(sha(path)==selection_sha,'PREP_SELECTION_HASH')
    subprocess.run(['git','ls-files','--error-unmatch',selection],cwd=REPO,check=True,stdout=subprocess.DEVNULL)
    plan=read(path);validate_selection(plan)
    for source in plan['sources']:subprocess.run(['git','ls-files','--error-unmatch',source['contract']],cwd=REPO,check=True,stdout=subprocess.DEVNULL)
    require(not PRIVATE.exists() and not PUBLIC.exists() and not (PROJECT/IMPORTS).exists() and not (PROJECT/(str(IMPORTS)+'.meta')).exists(),'PREP_FRESH_WORKSPACE_REQUIRED')
    require(not (PROJECT/'CandidateImportInput').exists() and not (PROJECT/'CandidatePackageSnapshot').exists() and not (PROJECT/'JourneyEvidence/CandidateArt').exists() and not (PROJECT/'Assets/DesertRV/Scenes/Journey').exists(),'PREP_PREEXISTING_OUTPUT')
    sys.path.insert(0,str(ROOT/'scripts'));import verify_evidence as original_guard
    original_guard.guard() # The full unchanged fresh guard runs here before any native output, not a fabricated marker.
    identity=original_guard.identity();initial_dirs={name:sorted(directories(PROJECT/name)) for name in ('Assets','Packages','ProjectSettings')}
    PRIVATE.mkdir(parents=True);PUBLIC.mkdir()
    save(dict(schema=1,sourceCommit=os.environ['GITHUB_SHA'],runId=os.environ['GITHUB_RUN_ID'],selection=selection,selectionSha256=selection_sha,plan=plan,protected=protected(),completed=[],assetFiles={},validationSourcePins=validation_sources(),initialIdentity=identity,initialSourceDirectories=initial_dirs))

def check_state(s):
    require(sha(REPO/s['selection'])==s['selectionSha256'],'PREP_SELECTION_CHANGED')
    require(s['validationSourcePins']==validation_sources(),'PREP_VALIDATION_VERSION_CHANGED')
    require(protected()==s['protected'],'PREP_PROTECTED_SOURCE_CHANGED')
    for path,h in s['assetFiles'].items():require(sha(PROJECT/path)==h,'PREP_EARLIER_ASSET_CHANGED')

def prepare_report_directory():
    # Native GameCI runs as root. Keep this one directory host-created so its later
    # cross-parent rename can update '..' without changing ownership/permissions.
    reports=PROJECT/'JourneyEvidence/CandidateArt'
    require(not reports.exists() and not reports.is_symlink(),'PREP_REPORT_DESTINATION_EXISTS')
    require(reports.parent.is_dir() and not any(path.is_symlink() for path in (reports.parent,*reports.parents)),'PREP_REPORT_PARENT_UNSAFE')
    reports.mkdir()

class ArchiveStageFailure(RuntimeError):
    def __init__(self,phase,kind,error):
        super().__init__('PREP_ARCHIVE_STAGE_FAILED')
        require(phase in {'ARCHIVE_MKDIR','INPUT_RENAME','REPORT_RENAME','PROOF_REHASH','STATE_SAVE'},'PREP_DIAGNOSTIC_PHASE')
        archive=PRIVATE/'native'/kind
        paths={'INPUT':PROJECT/'CandidateImportInput','INPUT_PARENT':PROJECT,'REPORT':PROJECT/'JourneyEvidence/CandidateArt',
               'REPORT_PARENT':PROJECT/'JourneyEvidence','ARCHIVE_PARENT':archive.parent,'ARCHIVE':archive,'ARCHIVED_INPUT':archive/'input','ARCHIVED_REPORT':archive/'art'}
        directories=[]
        for role,path in paths.items():
            try:
                info=path.lstat();is_dir=stat.S_ISDIR(info.st_mode)
                directories.append(dict(role=role,exists=True,isDirectory=is_dir,mode=format(stat.S_IMODE(info.st_mode),'04o'),currentUidWritable=bool(is_dir and not path.is_symlink() and os.access(path,os.W_OK))))
            except OSError:directories.append(dict(role=role,exists=False,isDirectory=False,mode=None,currentUidWritable=False))
        self.diagnostic=dict(phase=phase,errorClass=type(error).__name__ if type(error).__name__ in {'PermissionError','FileNotFoundError','FileExistsError','OSError','StrictError'} else 'OtherError',directories=directories)

def stage(kind):
    s=state();check_state(s);require(len(s['completed'])<3 and KINDS[len(s['completed'])]==kind,'PREP_WRONG_STAGE_ORDER')
    selected=s['plan']['sources'][len(s['completed'])]
    prepare(REPO/selected['contract'],selected['sha256'],PROJECT/'CandidateImportInput','STRICT_BINDING')
    prepare_report_directory()

def import_inventory():
    result={(IMPORTS/rel).as_posix():h for rel,h in tree(PROJECT/IMPORTS).items()}
    meta=PROJECT/(str(IMPORTS)+'.meta')
    if meta.exists():result[str(IMPORTS)+'.meta']=sha(meta)
    return result

def assert_union(expected):
    require(import_inventory()==expected,'PREP_ASSET_UNION_MISMATCH')
    names=[str(Path(p).relative_to(IMPORTS)) for p in expected if p.startswith(str(IMPORTS)+'/')]
    require(directories(PROJECT/IMPORTS)==expected_directories(names),'PREP_ASSET_DIRECTORY_UNION_MISMATCH')

def current_scope(s,c):
    """Do not conceal foreign/unknown files before the legacy one-candidate validator sees its view."""
    actual=import_inventory();prefix=str(IMPORTS)+'/'+c['id']
    for path,h in s['assetFiles'].items():require(actual.get(path)==h,'PREP_EARLIER_ASSET_CHANGED')
    current={p:h for p,h in actual.items() if p==prefix+'.meta' or p.startswith(prefix+'/') or p==str(IMPORTS)+'.meta'}
    require(set(actual)==set(s['assetFiles'])|set(current),'PREP_UNDECLARED_CANDIDATE_OUTPUT')
    known_dirs=expected_directories([str(Path(p).relative_to(IMPORTS)) for p in s['assetFiles'] if p.startswith(str(IMPORTS)+'/')])
    require(all(d in known_dirs or d==c['id'] or d.startswith(c['id']+'/') for d in directories(PROJECT/IMPORTS)),'PREP_UNKNOWN_CANDIDATE_DIRECTORY')
    return current

def copy_snapshot(c,current,xml):
    view=PRIVATE/'validation-view'/c['kind'];require(not view.exists(),'PREP_VIEW_EXISTS')
    evidence=PROJECT/'JourneyEvidence/CandidateArt';inputs=PROJECT/'CandidateImportInput'
    sources={}
    for folder,relative in ((inputs,Path('unity/CandidateImportInput')),(evidence,Path('unity/JourneyEvidence/CandidateArt'))):
        for name,h in tree(folder).items():sources[(folder/name)]=((relative/name),h)
    for path,h in current.items():sources[PROJECT/path]=(Path('unity')/path,h)
    report_path=evidence/'import-report.json'
    if report_path.exists():
        imp=read(report_path);deps=imp.get('dependencies') or []
        if deps:
            require(dependency_digest(PROJECT,deps)==imp.get('dependencySha256'),'PREP_NATIVE_DEPENDENCY_HASH')
            for name in deps:
                require(not name.startswith(str(IMPORTS)+'/') or name.startswith(str(IMPORTS)+'/'+c['id']+'/'),'PREP_CROSS_KIND_DEPENDENCY')
            # Keep canonical dependency names and original physical paths. The strict
            # resolver includes private package bytes/manifest and project controls.
            for path in dependency_input_paths(PROJECT,deps):
                sources[path]=(Path('unity')/path.relative_to(PROJECT),sha(path))
    if c['kind']=='pouncer':
        # The existing strict Pouncer exporter also freezes its statically called
        # solver. Unity's serialized asset dependencies do not include that C# helper.
        from paw_contact_output import SOLVER
        for name in (SOLVER,SOLVER+'.meta'):
            path=PROJECT/name;sources[path]=(Path('unity')/name,sha(path))
    paths=list(xml.rglob('*.xml'));require(0<len(paths)<=20,'PREP_NATIVE_XML_MISSING')
    for path in paths:sources[path]=(Path('artifacts/candidate-art')/path.relative_to(xml),sha(path))
    for path,(rel,h) in sources.items():
        dest=view/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(safe(path),dest);require(sha(dest)==h,'PREP_COPY_CHANGED')
    # Empty/unknown current directories must also survive into the view, then the union proof rejects them.
    candidate=PROJECT/IMPORTS/c['id']
    for rel in directories(candidate): (view/'unity'/IMPORTS/c['id']/rel).mkdir(parents=True,exist_ok=True)
    return view,sources

def verify_snapshot(sources):
    require(all(sha(path)==h for path,(_,h) in sources.items()),'PREP_INPUT_CHANGED_DURING_VALIDATION')
    report=PROJECT/'JourneyEvidence/CandidateArt/import-report.json'
    if report in sources:
        imp=read(report);deps=imp.get('dependencies') or []
        if deps:
            require(dependency_input_paths(PROJECT,deps)<=set(sources),'PREP_DEPENDENCY_INPUT_SET_CHANGED')
            require(dependency_digest(PROJECT,deps)==imp.get('dependencySha256'),'PREP_NATIVE_DEPENDENCY_HASH')

def collect(kind,native):
    s=state();check_state(s);require(len(s['completed'])<3 and KINDS[len(s['completed'])]==kind,'PREP_WRONG_STAGE_ORDER')
    selected=s['plan']['sources'][len(s['completed'])];c=read(PROJECT/'CandidateImportInput/contract.json')
    require(sha(PROJECT/'CandidateImportInput/contract.json')==selected['sha256'] and c['kind']==kind,'PREP_STAGED_CONTRACT_CHANGED')
    current=current_scope(s,c);view,sources=copy_snapshot(c,current,ROOT/'artifacts'/('journey-strict-'+kind))
    validated=PRIVATE/'validated-export'/kind;validated.parent.mkdir(exist_ok=True)
    result=export(view,validated,native,'success') # Existing strict validator checks real XML, PBR, poses, images and exact per-kind asset allowlist.
    require(native=='success' and result['status']=='STRICT_CANDIDATE_CAPTURED_NOT_ACCEPTED' and result['approved'] is False,'PREP_NATIVE_NOT_READY')
    native_xml,native_cases=native_inventory(ROOT/'artifacts'/('journey-strict-'+kind),result['nativeXmlSha256'])
    require(result['nativeCases']==len(native_cases),'PREP_NATIVE_RECEIPT_INVENTORY_MISMATCH')
    verify_snapshot(sources);check_state(s)
    for name,h in result['rawReportSha256'].items():require(sha(PROJECT/'JourneyEvidence/CandidateArt'/name)==h,'PREP_RAW_REPORT_CHANGED')
    exported={}
    for row in result['files']:
        if row['path']=='CandidateArtImports.meta' or row['path'].startswith('CandidateArtImports/'):
            path='Assets/DesertRV/'+row['path'];require(sha(PROJECT/path)==row['sha256'],'PREP_EXPORTED_ASSET_CHANGED');exported[path]=row['sha256']
    require(exported==current,'PREP_CURRENT_EXPORT_SET_MISMATCH')
    merged={**s['assetFiles'],**exported};assert_union(merged) # Exact files AND directories of all validated candidates, never just filtered views.
    require(not (PUBLIC/kind).exists(),'PREP_PUBLIC_STAGE_EXISTS');validated.rename(PUBLIC/kind)
    phase='ARCHIVE_MKDIR'
    try:
        archive=PRIVATE/'native'/kind;archive.mkdir(parents=True)
        phase='INPUT_RENAME';(PROJECT/'CandidateImportInput').rename(archive/'input')
        phase='REPORT_RENAME';(PROJECT/'JourneyEvidence/CandidateArt').rename(archive/'art')
        phase='PROOF_REHASH';proof={}
        for path,(rel,h) in sources.items():
            if path.is_relative_to(PROJECT/'CandidateImportInput'):path=archive/'input'/path.relative_to(PROJECT/'CandidateImportInput')
            elif path.is_relative_to(PROJECT/'JourneyEvidence/CandidateArt'):path=archive/'art'/path.relative_to(PROJECT/'JourneyEvidence/CandidateArt')
            require(sha(path)==h,'PREP_ARCHIVE_CHANGED');proof[str(path.relative_to(REPO))]=h
        s['completed'].append(dict(kind=kind,id=c['id'],proof=proof,exportReceiptSha256=sha(PUBLIC/kind/'receipt.json'),nativeXml=native_xml,nativeCases=native_cases))
        s['assetFiles']=merged;phase='STATE_SAVE';save(s)
    except Exception as error:raise ArchiveStageFailure(phase,kind,error) from None

def arc_pose_source(integration):
    # Preserve raw JSON null intent before Unity inline serialization can materialize a DTO.
    require(isinstance(integration,dict) and 'arcModulePose' in integration,'PREP_EXPLICIT_ARC_POSE_INTENT')
    pose=integration['arcModulePose']
    require(pose is None or isinstance(pose,dict),'PREP_EXPLICIT_ARC_POSE_INTENT')
    return 'scene-geometry' if pose is None else 'selection'

def ready():
    s=state();check_state(s);require([x['kind'] for x in s['completed']]==list(KINDS),'PREP_THREE_STRICT_SUCCESSES_REQUIRED');assert_union(s['assetFiles'])
    require(not (PROJECT/'JourneyEvidence/CandidateArt').exists(),'PREP_RAW_REPORT_DESTINATION_EXISTS')
    for result in s['completed']:
        require(sha(PUBLIC/result['kind']/'receipt.json')==result['exportReceiptSha256'],'PREP_EXPORT_RECEIPT_CHANGED')
        receipt=read(PUBLIC/result['kind']/'receipt.json');verify_staged_inventory(PUBLIC/result['kind'],receipt['files'],result['exportReceiptSha256'])
        require(all(sha(REPO/p)==h for p,h in result['proof'].items()),'PREP_EARLIER_PROOF_CHANGED')
    requests=[];proof=[]
    for item in s['completed']:
        kind=item['kind'];archive=PRIVATE/'native'/kind;dest=PROJECT/'JourneyEvidence/CandidateArt'/kind;dest.parent.mkdir(exist_ok=True);(archive/'art').rename(dest)
        before=str((archive/'art').relative_to(REPO))+'/'
        item['proof']={(str(dest.relative_to(REPO))+'/'+p[len(before):] if p.startswith(before) else p):h for p,h in item['proof'].items()}
        require(all(sha(REPO/p)==h for p,h in item['proof'].items()),'PREP_FINAL_RAW_ARCHIVE_CHANGED')
        imp=read(dest/'import-report.json');c=read(archive/'input/contract.json');prefab=imp['prefab'];contract=str(Path(prefab).parent/'contract.json')
        require(sha(PROJECT/contract)==imp['contractSha256'],'PREP_COPIED_CONTRACT_CHANGED')
        requests.append(dict(kind=kind,sourceModelPath=str(Path(contract).parent/'Source'/c['modelFile']),prefab=dict(path=prefab,sha256=sha(PROJECT/prefab),dependencyHash=imp['dependencyHash'],dependencySha256=imp['dependencySha256']),contract=dict(path=contract,sha256=sha(PROJECT/contract)),importReport=dict(path=str(dest.relative_to(PROJECT)/'import-report.json'),sha256=sha(dest/'import-report.json'))))
        proof.append(dict(path=str((PUBLIC/kind/'receipt.json').relative_to(REPO)),sha256=item['exportReceiptSha256']))
    payload=dict(schema=1,status='THREE_NATIVE_STRICT_EXPORTS_VERIFIED_NOT_APPROVED',sourceCommit=s['sourceCommit'],selectionSha256=s['selectionSha256'],spawnRootHeightSource=s['plan']['spawnRootHeightSource'],fx=s['plan']['fx'],integration=s['plan']['integration'],arcModulePoseSource=arc_pose_source(s['plan']['integration']),validatedExportReceipts=proof,validationSourcePins=s['validationSourcePins'],nativeProofs=[dict(kind=x['kind'],xml=x['nativeXml'],cases=x['nativeCases']) for x in s['completed']])
    payload['integration']['candidates']=requests
    target=PRIVATE/'ready-input.json';require(not target.exists(),'PREP_READY_INPUT_EXISTS');target.write_text(json.dumps(payload,indent=2)+'\n')
    (PRIVATE/'ready-input.sha256').write_text(sha(target)+'\n');s['phase']='ready-input-frozen';s['readyInputSha256']=sha(target);save(s)

def finish(native):
    require(native=='success','PREP_AUTHORING_NATIVE_FAILED')
    reports=[];cases=[]
    for path in (ROOT/'artifacts/journey-preparation').rglob('*.xml'):
        xml=ET.parse(safe(path)).getroot()
        if xml.tag=='test-run':reports.append((path,xml));cases.extend(xml.iter('test-case'))
    require(len(reports)==1 and reports[0][1].get('result')=='Passed' and len(cases)==1 and cases[0].get('fullname')=='DesertRV.Tests.JourneyPreparationTests.PrepareVerifiedSameWorkspaceJourney' and cases[0].get('result')=='Passed','PREP_NATIVE_ENTRY_NOT_PASSED')
    receipt=PROJECT/'JourneyEvidence/journey-candidate-integration.json';r=read(receipt)
    require(r.get('status')=='STRICT_CANDIDATES_BOUND_UNREVIEWED' and r.get('sourceCommit')==os.environ['GITHUB_SHA'] and r.get('candidateOnly') is True and r.get('protectedSourcesUnchanged') is True and r.get('failures')==[] and r.get('rolledBack') is False and all(r.get(k) is False for k in ('visualReviewed','gameplayReviewed','audioAuditioned')),'PREP_INTEGRATION_NOT_READY')
    expected={'Assets/DesertRV/Scenes/Journey/'+name for name in ('JourneyBootstrap.unity','FirstStation.unity','Scrapyard.unity','NightBeacon.unity','JourneyContent.asset')}
    require(isinstance(r.get('outputs'),list) and len(r['outputs'])==5 and {item['path'] for item in r['outputs']}==expected,'PREP_EXACT_SAVED_OUTPUTS')
    for item in r['outputs']:require(sha(PROJECT/item['path'])==item['sha256'],'PREP_SCENE_OUTPUT_CHANGED')
    scope=PROJECT/'JourneyEvidence/journey-diagnostic-scope.json';sc=read(scope)
    require(sc['label']=='EDITOR_DIAGNOSTIC_UNAPPROVED_CONTENT' and sc['sourceCommit']==os.environ['GITHUB_SHA'],'PREP_SCOPE_IDENTITY')
    require(isinstance(sc.get('files'),list) and len(sc['files'])>0,'PREP_SCOPE_EMPTY')
    for item in sc['files']:
        require(rel(item['path']) and item['path'].startswith(('Assets/DesertRV/','JourneyEvidence/CandidateArt/')),'PREP_SCOPE_PATH')
        require(sha(PROJECT/item['path'])==item['sha256'],'PREP_SCOPE_PIN_CHANGED')
    sys.path.insert(0,str(ROOT/'scripts/rendered'));import prepared_source;prepared_source.seal()
    from generated_export import export_generated
    generated=export_generated(prepared_source,sha(reports[0][0]))
    # Exact generated assets are persisted; same-job report paths are historical evidence, never a restored scope.
    out=dict(generatedExport=generated,status='PREPARED_EDITOR_SCOPE_UNREVIEWED',pathsAreSameJobOnly=True,renderedObservationProduced=False,sourceCommit=os.environ['GITHUB_SHA'],visualApproved=False,gameplayAccepted=False,preparation_receipt=str(receipt.relative_to(REPO)),preparation_sha256=sha(receipt),diagnostic_scope=str(scope.relative_to(REPO)),scope_sha256=sha(scope),nativeXmlSha256=sha(reports[0][0]),nativeCase=cases[0].get('fullname'))
    (PUBLIC/'preparation.json').write_text(json.dumps(out,indent=2)+'\n')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:
            for name in ('preparation_receipt','preparation_sha256','diagnostic_scope','scope_sha256'):f.write(name+'='+out[name]+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['init','stage','collect','ready','finish']);p.add_argument('--selection');p.add_argument('--sha256');p.add_argument('--kind',choices=KINDS);p.add_argument('--native',choices=['success','failure','cancelled','skipped']);a=p.parse_args()
    try:
        guard()
        if a.command=='init':init(a.selection,a.sha256)
        elif a.command=='stage':stage(a.kind)
        elif a.command=='collect':collect(a.kind,a.native)
        elif a.command=='ready':ready()
        else:finish(a.native)
    except Exception as error:
        code=str(error) if re.fullmatch('[A-Z][A-Z0-9_]{0,100}',str(error)) else type(error).__name__
        print('JOURNEY_PREPARATION_NOT_READY: '+code)
        failure=dict(status='NOT_READY',approved=False,command=a.command,kind=a.kind,errorCode=code)
        if isinstance(error,ArchiveStageFailure):failure['archiveDiagnostic']=error.diagnostic
        if PUBLIC.is_dir(): (PUBLIC/'not-ready.json').write_text(json.dumps(failure,indent=2)+'\n')
        return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
