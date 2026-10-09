"""Dedicated same-job prepared Journey proof. The original fresh-source guard is never weakened."""
import json,os,pathlib,re,sys
ROOT=pathlib.Path(__file__).resolve().parents[4]
TASK=ROOT/'tasks/desert-rv';PROJECT=TASK/'unity'
sys.path.insert(0,str(TASK/'scripts'));import verify_evidence as original
STATE=PROJECT/'JourneyEvidence/JourneyPreparation/state.json'
PROOF=PROJECT/'JourneyEvidence/JourneyPreparation/prepared-source.json'
JOURNEY='Assets/DesertRV/Scenes/Journey'
CANDIDATES='Assets/DesertRV/CandidateArtImports'
# Native operational state only: never treated as source, copied to public exports, or restored across runs.
OPERATIONAL={'Library','Temp','Logs','obj','UserSettings','JourneyEvidence'}
def require(ok,code):
    if not ok:raise ValueError(code)
def sha(path):return original.sha(path)
def read(path):return original.read_json(path)
def walk(folder):
    files={};dirs=set()
    require(folder.is_dir() and not folder.is_symlink(),'PREPARED_ROOT')
    for path in folder.rglob('*'):
        require(not path.is_symlink(),'PREPARED_SYMLINK')
        rel=path.relative_to(folder).as_posix()
        if path.is_file():files[rel]=sha(path)
        else:require(path.is_dir(),'PREPARED_FILE_TYPE');dirs.add(rel)
    return files,dirs

def verify_original(identity):
    require(original.identity()==identity,'PREPARED_ORIGINAL_IDENTITY')
    source=read(TASK/'SOURCE-STATE.json')
    # Same SOURCE-STATE bytes were verified by the real fresh guard before any native execution.
    for row in source['files']:
        path=ROOT/row['path'];require(sha(path)==row['sha256'] and path.stat().st_size==row['size'],'PREPARED_ORIGINAL_CHANGED')
    for row in source['restoredFiles']:
        path=ROOT/row['path'];require(sha(path)==row['sha256'] and path.stat().st_size==row['size'],'PREPARED_RESTORATION_CHANGED')
    return source

def verify_asset_union(source,initial_dirs,added,package_snapshot=None):
    base='tasks/desert-rv/unity/';expected={row['path'][len(base):]:row['sha256'] for row in source['files'] if row['path'].startswith(base)}
    expected.update({row['path'][len(base):]:row['sha256'] for row in source['restoredFiles'] if row['path'].startswith(base)})
    require(not set(expected)&set(added),'PREPARED_CANNOT_REPLACE_SOURCE')
    for path in added:
        require(path.startswith(CANDIDATES+'/') or path==CANDIDATES+'.meta' or path.startswith(JOURNEY+'/') or path==JOURNEY+'.meta','PREPARED_ADDITION_PATH')
    expected.update(added)
    for name in ('Assets','Packages','ProjectSettings'):
        files,dirs=walk(PROJECT/name);want={p[len(name)+1:]:h for p,h in expected.items() if p.startswith(name+'/')}
        require(files==want,'PREPARED_ASSET_FILE_UNION')
        desired=set(initial_dirs[name])
        for path in added:
            if path.startswith(name+'/'):
                desired.update(p.as_posix() for p in pathlib.Path(path[len(name)+1:]).parents if p!=pathlib.Path('.'))
        require(dirs==desired,'PREPARED_ASSET_DIRECTORY_UNION')
    # The private package snapshot has its own strict pins and exact inventory;
    # it is never a general operational-directory exemption.
    package_roots=set()
    if package_snapshot is not None:
        files,dirs=walk(PROJECT/'CandidatePackageSnapshot')
        require(files==package_snapshot,'PREPARED_PACKAGE_SNAPSHOT_CHANGED')
        required_dirs={p.as_posix() for name in files for p in pathlib.Path(name).parents if p!=pathlib.Path('.')}
        require(dirs==required_dirs,'PREPARED_PACKAGE_DIRECTORY_UNION')
        package_roots.add('CandidatePackageSnapshot')
    # No new executable/source files outside the exact native-added Assets sets.
    root_expected={p for p in expected if '/' not in p}
    for path in PROJECT.iterdir():
        require(not path.is_symlink(),'PREPARED_UNITY_ROOT_SYMLINK')
        if path.is_dir():require(path.name in OPERATIONAL|package_roots|{'Assets','Packages','ProjectSettings'},'PREPARED_UNKNOWN_UNITY_DIRECTORY')
        else:require(path.name in root_expected,'PREPARED_UNKNOWN_UNITY_ROOT_FILE')
    # Preserve exact inventories for all non-Unity coverage roots; the existing Python bytecode exception is unchanged.
    for directory in original.SOURCE_ROOTS:
        if directory=='tasks/desert-rv/unity':continue
        files,_=walk(ROOT/directory)
        python_roots={'tasks/desert-rv/scripts','tasks/desert-rv/art/import-candidate','tasks/desert-rv/art/journey-preparation'}
        names={directory+'/'+name for name in files if not (directory in python_roots and '__pycache__' in pathlib.Path(name).parts)}
        want={row['path'] for row in source['files'] if row['path'].startswith(directory+'/')}
        require(names==want,'PREPARED_OTHER_SOURCE_INVENTORY')

def verified_package_snapshot(state):
    # Reuse the strict canonical resolver, including its unchanged four official
    # byte pins, snapshot manifest, project controls and no-fallback rules.
    sys.path.insert(0,str(TASK/'art/import-candidate'))
    from strict_output import dependency_input_paths,PACKAGE_ASSETS,PACKAGE_FILES
    inputs=dependency_input_paths(PROJECT,sorted(PACKAGE_ASSETS))
    snapshot=PROJECT/'CandidatePackageSnapshot'
    names={'manifest.json'}|set(PACKAGE_FILES)
    expected={name:sha(snapshot/name) for name in names}
    require({snapshot/name for name in names}<=inputs,'PREPARED_PRIVATE_PACKAGE_SNAPSHOT_REQUIRED')
    prefix=str(snapshot.relative_to(ROOT))+'/'
    require([row['kind'] for row in state['completed']]==['armored','pouncer','weapon'],'PREPARED_THREE_RESULTS')
    for row in state['completed']:
        pinned={name[len(prefix):]:value for name,value in row['proof'].items() if name.startswith(prefix)}
        require(pinned==expected,'PREPARED_PACKAGE_STAGE_PROOF_CHANGED')
        require(all(row['proof'].get(str(path.relative_to(ROOT)))==sha(path) for path in inputs),'PREPARED_PACKAGE_INPUT_PROOF_CHANGED')
    return expected

def journey_files(fx):
    require(fx['status']=='ORIGINAL_NATIVE_FX_AUTHORED_UNCALIBRATED' and fx['protectedSourcesUnchanged'] is True and fx['failures']==[],'PREPARED_FX_NOT_READY')
    allowed={JOURNEY+'/'+n for n in ('JourneyBootstrap.unity','FirstStation.unity','Scrapyard.unity','NightBeacon.unity','JourneyContent.asset')}
    allowed.update(JOURNEY+'/Region-'+str(i)+'-Sky.mat' for i in (1,2,3))
    for row in fx['outputs']:
        name=row['path'];require(re.fullmatch(re.escape(JOURNEY)+r'/CandidateFx/[a-z0-9-]+/(Flash\.(png|mat)|Arc\.(png|mat)|MuzzleFlash\.prefab|ArcPresentation\.prefab)',name),'PREPARED_FX_ADDITION')
        require(sha(PROJECT/name)==row['sha256'],'PREPARED_FX_BYTES_CHANGED');allowed.add(name)
    require(len(fx['outputs'])==6 and len({x['path'] for x in fx['outputs']})==6,'PREPARED_FX_INVENTORY')
    fx_folders={str(pathlib.Path(x['path']).parent) for x in fx['outputs']};require(len(fx_folders)==1,'PREPARED_FX_FOLDER')
    for path in (PROJECT/JOURNEY).glob('Layout-*.mat'):
        require(re.fullmatch(r'Layout-[0-9A-F]{6}\.mat',path.name),'PREPARED_LAYOUT_MATERIAL_NAME');allowed.add(str(path.relative_to(PROJECT)))
    allowed|={name+'.meta' for name in tuple(allowed)}
    allowed|={JOURNEY+'.meta',JOURNEY+'/CandidateFx.meta',next(iter(fx_folders))+'.meta'}
    actual={JOURNEY+'/'+name:sha(PROJECT/JOURNEY/name) for name in walk(PROJECT/JOURNEY)[0]}
    actual[JOURNEY+'.meta']=sha(PROJECT/(JOURNEY+'.meta'))
    require(set(actual)==allowed,'PREPARED_JOURNEY_ADDITION_INVENTORY')
    native=read(PROJECT/'JourneyEvidence/JourneyPreparation/authored-assets.json')
    require(native['status']=='ACTUAL_NATIVE_JOURNEY_ASSETS_UNREVIEWED' and native['sourceCommit']==os.environ['GITHUB_SHA'] and len(native['files'])==len(actual) and {r['path']:r['sha256'] for r in native['files']}==actual,'PREPARED_NATIVE_ASSET_SNAPSHOT_CHANGED')
    return actual

def pin(path):return dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
def verify_data_pin(value):
    name=value['path'];require(isinstance(name,str) and not pathlib.PurePosixPath(name).is_absolute() and '..' not in pathlib.PurePosixPath(name).parts and '\\' not in name,'PREPARED_DATA_PATH')
    require(sha(ROOT/name)==value['sha256'],'PREPARED_DATA_BYTES_CHANGED')

def seal():
    require(not PROOF.exists(),'PREPARED_PROOF_EXISTS');s=read(STATE);source=verify_original(s['initialIdentity'])
    require([r['kind'] for r in s['completed']]==['armored','pouncer','weapon'],'PREPARED_THREE_RESULTS')
    fx_path=PROJECT/'JourneyEvidence/journey-candidate-fx.json';fx=read(fx_path)
    added={**s['assetFiles'],**journey_files(fx)}
    verify_asset_union(source,s['initialSourceDirectories'],added,verified_package_snapshot(s))
    data=[STATE,PROJECT/'JourneyEvidence/JourneyPreparation/authored-assets.json',fx_path,PROJECT/'JourneyEvidence/journey-candidate-integration.json',PROJECT/'JourneyEvidence/journey-diagnostic-scope.json']
    for item in s['completed']:
        receipt=TASK/'journey-preparation-export'/item['kind']/'receipt.json';require(sha(receipt)==item['exportReceiptSha256'],'PREPARED_STRICT_RECEIPT_CHANGED');data.append(receipt)
    proof=dict(schema='desert-rv-prepared-source/v1',initialIdentity=s['initialIdentity'],initialSourceDirectories=s['initialSourceDirectories'],addedAssets=added,dataPins=[pin(path) for path in data])
    PROOF.write_text(json.dumps(proof,indent=2)+'\n')
    # Source proof identity is also tied to the actual immutable integration/scope pins by the caller's verify_inputs.
    verify()

def verify():
    proof=read(PROOF);require(proof.get('schema')=='desert-rv-prepared-source/v1','PREPARED_SCHEMA')
    source=verify_original(proof['initialIdentity'])
    expected={str(path.relative_to(ROOT)) for path in (STATE,PROJECT/'JourneyEvidence/JourneyPreparation/authored-assets.json',PROJECT/'JourneyEvidence/journey-candidate-fx.json',PROJECT/'JourneyEvidence/journey-candidate-integration.json',PROJECT/'JourneyEvidence/journey-diagnostic-scope.json')}
    expected.update('tasks/desert-rv/journey-preparation-export/'+kind+'/receipt.json' for kind in ('armored','pouncer','weapon'))
    require(len(proof['dataPins'])==8 and {p['path'] for p in proof['dataPins']}==expected,'PREPARED_EXACT_DATA_PINS')
    for item in proof['dataPins']:verify_data_pin(item)
    integrated=read(PROJECT/'JourneyEvidence/journey-candidate-integration.json')
    require(integrated['status']=='STRICT_CANDIDATES_BOUND_UNREVIEWED' and integrated['protectedSourcesUnchanged'] is True and integrated['failures']==[],'PREPARED_INTEGRATION_NOT_READY')
    for row in integrated['protectedFiles']:
        require(row['path'].startswith(('Assets/','Packages/','ProjectSettings/')) and '..' not in pathlib.PurePosixPath(row['path']).parts and '\\' not in row['path'],'PREPARED_NATIVE_PROTECTED_PATH')
        require(sha(PROJECT/row['path'])==row['sha256'],'PREPARED_NATIVE_PROTECTED_BYTES_CHANGED')
    s=read(STATE);require(proof['initialIdentity']==s['initialIdentity'] and proof['initialSourceDirectories']==s['initialSourceDirectories'],'PREPARED_INITIAL_PROOF_CHANGED');fx=read(PROJECT/'JourneyEvidence/journey-candidate-fx.json')
    require(proof['addedAssets']=={**s['assetFiles'],**journey_files(fx)},'PREPARED_GENERATED_PROOF_CHANGED')
    verify_asset_union(source,proof['initialSourceDirectories'],proof['addedAssets'],verified_package_snapshot(s))
    return proof
if __name__=='__main__':
    try:verify()
    except Exception as error:print('PREPARED_SOURCE_PROOF_FAILED');raise SystemExit(1)
    print('PREPARED_SOURCE_PROOF_PASS_UNREVIEWED')
