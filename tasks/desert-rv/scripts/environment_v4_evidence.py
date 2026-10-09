#!/usr/bin/env python3
"""Independent V4 renderer proof. Existing 18-view validation is reused unchanged.
This is not strict combat import, gameplay validation, Android, or art acceptance.
"""
import argparse
import json
import math
import shutil
from pathlib import Path
import environment_evidence as legacy
import verify_evidence as source

CONTRACT = source.TASK / 'art/environment-v4/generated-contract.json'
POLISH = legacy.GENERATED + '/EnvironmentV4'
EXTRA = 'JourneyEvidence/environment-v4'
CLOSEUP_VIEWS = ('forecourt-eye-height', 'garage-eye-height')
EXTRA_IMAGES = {f'FirstStation-{view}.png' for view in CLOSEUP_VIEWS}
EXTRA_REPORTS = {f'region-{region}-authoring.json' for region in (1,2,3)} | {'closeup-capture-report.json'}
OUT = source.TASK / 'evidence/environment-v4'
PARTIAL = source.TASK / 'evidence/environment-v4-unaccepted'
STATUS = 'ENVIRONMENT_V4_NATIVE_PIXELS_ONLY_NOT_GAMEPLAY_OR_ART_ACCEPTANCE'
require = source.require


def load_contract():
    contract = source.read_json(CONTRACT)
    require(contract.get('schema') == 1 and contract.get('generated_folder') == POLISH, 'Wrong V4 generated contract')
    files, metas = contract.get('files'), contract.get('metadata_files')
    require(isinstance(files,list) and isinstance(metas,list) and len(files)==97 and len(metas)==98, 'Wrong exact V4 file counts')
    require(len(set(files))==len(files) and len(set(metas))==len(metas), 'Duplicate V4 contract path')
    require(set(metas)=={p+'.meta' for p in files}|{POLISH+'.meta'}, 'V4 metadata contract differs')
    for name in files+metas:
        require(isinstance(name,str) and '*' not in name and '..' not in Path(name).parts and '\\' not in name and
                (name==POLISH+'.meta' or name.startswith(POLISH+'/') and len(Path(name).parts)==len(Path(POLISH).parts)+1), 'Unsafe V4 contract path')
    keys=contract.get('region_mesh_keys');materials=contract.get('material_names')
    require(isinstance(keys,dict) and set(keys)=={'1','2','3'} and isinstance(materials,list) and len(materials)==14 and len(set(materials))==14, 'Wrong V4 region/material contract')
    require({r:len(keys[r]) for r in keys}=={'1':35,'2':25,'3':23}, 'Wrong V4 mesh count')
    exact={POLISH+'/Surface-'+mat+'.mat' for mat in materials}
    exact|={POLISH+'/R'+r+'-'+key+'.asset' for r in keys for key in keys[r]}
    require(set(files)==exact, 'V4 files differ from finite mesh/material membership')
    return contract


def collect_generated(project, contract):
    folder=project/legacy.GENERATED
    source.safe(Path(str(folder)+'.meta'))
    files=[p for p in folder.rglob('*') if p.is_file()]+[Path(str(folder)+'.meta')]
    require(195<len(files)<400,'Invalid bounded V4 generated count')
    names={p.relative_to(project).as_posix() for p in files}
    expected=set(contract['files'])|set(contract['metadata_files'])
    actual={n for n in names if n==POLISH+'.meta' or n.startswith(POLISH+'/')}
    require(actual==expected, 'Native V4 generated membership differs: '+json.dumps(sorted(actual^expected)))
    required={legacy.GENERATED+'/'+n+'.unity' for n in ('JourneyBootstrap',*legacy.REGIONS)}|{legacy.GENERATED+'/JourneyContent.asset'}
    require(required<=names,'Missing authored scene or manifest')
    for name in names:
        require(name in expected or legacy.valid_generated_name(name),'Non-allowlisted generated file')
        path=source.safe(project/name)
        require(path.stat().st_size<=40*1024**2,'Oversized generated file')
        if not name.endswith('.meta'):require(name+'.meta' in names,'Generated asset has no meta')
        text=path.read_text()
        require(text.startswith('fileFormatVersion: 2') if name.endswith('.meta') else text.startswith('%YAML 1.1'),'Generated output is not Unity text serialization')
    require(sum(p.stat().st_size for p in files)<=100*1024**2,'Oversized complete V4 generated bundle')
    return sorted(names)


def finite_vector(value, eye=False):
    require(isinstance(value,dict) and set(value)=={'x','y','z'},'Bad V4 camera vector')
    require(all(type(v) in (int,float) and math.isfinite(v) and abs(v)<1000 for v in value.values()),'Nonfinite/unbounded V4 camera vector')
    if eye:require(abs(value['y']-1.62)<.0001,'Closeup is not the authored eye height')
    return value


def inspect_extra(project, contract):
    directory=project/EXTRA
    require({p.name for p in directory.iterdir()}==EXTRA_IMAGES|EXTRA_REPORTS,'Unexpected or missing V4 extra evidence')
    report=source.read_json(directory/'closeup-capture-report.json')
    require(set(report)=={'status','graphicsDevice','savedSceneBytesPreserved','captureBuffersReleased','images'},'Unexpected closeup report fields')
    require(report['status']=='ACTUAL_EDITOR_EYE_HEIGHT_VIEWS_NOT_INPUT_PLAYTHROUGH' and report['graphicsDevice']=='OpenGLCore' and
            report['savedSceneBytesPreserved'] is True and report['captureBuffersReleased'] is True,'Closeup scope/device/preservation invalid')
    require(isinstance(report['images'],list) and len(report['images'])==2,'Exactly two closeups required')
    seen=set();images=[]
    for row in report['images']:
        require(isinstance(row,dict) and set(row)=={'view','file','position','lookAt','fieldOfView'},'Unexpected closeup camera fields')
        view=row['view'];require(view in CLOSEUP_VIEWS and view not in seen,'Unknown/duplicate closeup');seen.add(view)
        name='FirstStation-'+view+'.png'
        require(row['file']==EXTRA+'/'+name and type(row['fieldOfView']) in (int,float) and row['fieldOfView']==66,'Closeup filename or FOV changed')
        at=finite_vector(row['position'],eye=True);look=finite_vector(row['lookAt'])
        require(sum((at[k]-look[k])**2 for k in at)>.25,'Degenerate closeup look direction')
        legacy.inspect_png(directory/name)
        images.append(dict(view=view,file=name,position=at,lookAt=look,fieldOfView=66,width=1440,height=900,sha256=source.sha(directory/name)))
    receipts=[]
    material_files={POLISH+'/Surface-'+m+'.mat' for m in contract['material_names']}
    cumulative=set(material_files)
    for region in (1,2,3):
        row=source.read_json(directory/f'region-{region}-authoring.json')
        fields={'region','meshCount','rendererCount','triangles','importedModelRenderers','importedModelTriangles','addedLights','status','generatedFiles'}
        require(isinstance(row,dict) and set(row)==fields,'Unexpected V4 native authoring fields')
        require(row['region']==region and row['status']=='authored-not-visually-accepted','Wrong V4 authoring region/scope')
        for key in fields-{'status','generatedFiles'}:require(type(row[key]) is int,'Invalid V4 count type')
        mesh_count=len(contract['region_mesh_keys'][str(region)])
        require(row['meshCount']==mesh_count and 0<row['triangles']<=90000,'Invalid V4 generated mesh count/triangle budget')
        require(0<row['importedModelRenderers']<=20 and 0<row['importedModelTriangles']<=18000,'Invalid V4 imported model budget')
        require(row['rendererCount']==mesh_count+row['importedModelRenderers'] and row['addedLights']=={1:2,2:1,3:2}[region],'Invalid V4 renderer/light budget')
        cumulative|={POLISH+'/R'+str(region)+'-'+key+'.asset' for key in contract['region_mesh_keys'][str(region)]}
        require(isinstance(row['generatedFiles'],list) and len(row['generatedFiles'])==len(set(row['generatedFiles'])) and
                set(row['generatedFiles'])==cumulative,'Actual authoring file list does not match cumulative finite contract')
        receipts.append(dict(row,generatedFiles=sorted(cumulative)))
    return dict(scope=STATUS,closeupCapture=dict(graphicsDevice='OpenGLCore',savedSceneBytesPreserved=True,captureBuffersReleased=True),images=images,authoring=receipts)


def before():
    load_contract()
    legacy.before()


def write_manifest(destination):
    records=[dict(path=p.relative_to(destination).as_posix(),sha256=source.sha(p),size=p.stat().st_size) for p in sorted(destination.rglob('*')) if p.is_file()]
    (destination/'SHA256SUMS.json').write_text(json.dumps(records,indent=2)+'\n')


def package():
    require(not OUT.exists(),'Refuse stale V4 output')
    contract=load_contract();before=source.read_json(legacy.SNAPSHOT)
    legacy.assert_preserved(before,legacy.tracked_snapshot(source.ROOT))
    native=legacy.inspect_native_report(source.TASK/'artifacts/environment')
    capture=legacy.inspect_capture(source.PROJECT)
    extra=inspect_extra(source.PROJECT,contract)
    names=collect_generated(source.PROJECT,contract)
    OUT.mkdir(parents=True);records=[]
    for name in names:
        src=source.PROJECT/name;dest=OUT/'generated'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
        records.append(dict(path=name,sha256=source.sha(src),size=src.stat().st_size))
    for name in sorted(legacy.IMAGES):shutil.copyfile(source.PROJECT/'JourneyEvidence/environment'/name,OUT/name)
    for name in sorted(EXTRA_IMAGES):shutil.copyfile(source.PROJECT/EXTRA/name,OUT/name)
    for report in capture['clearance']:
        (OUT/f"clearance-region-{report['region']}.json").write_text(json.dumps(dict(report,status='CANDIDATE_CLEARANCE_ONLY_NOT_GAMEPLAY_APPROVAL'),indent=2)+'\n')
    (OUT/'environment-v4-receipts.json').write_text(json.dumps(extra,indent=2)+'\n')
    receipt=source.identity();receipt.update(schema='desert-rv-environment-v4-renderer-proof/v1',scope=STATUS,
        strictCombatIntegration='NOT_RUN',newMonsterIntegration='NOT_RUN',playthrough='NOT_RUN',android='NOT_RUN',visualAcceptance='NOT_ACCEPTED',
        protectedTrackedFilesUnchanged=True,protectedTrackedFileCount=len(before),protectedSnapshotSha256=source.sha(legacy.SNAPSHOT),
        nativeRenderTest=legacy.RENDER_TEST,nativeRenderXmlSha256=native,generatedContractSha256=source.sha(CONTRACT),generated=records,capture=capture,extra=extra)
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');write_manifest(OUT)
    print('Twenty real Unity camera captures, exact new asset membership, and unchanged tracked source verified. Art/gameplay acceptance NOT_RUN.')


def partial():
    # Same narrow source-failure rule as the established workflow. No generated scene, logs, or raw XML are exported.
    require(not PARTIAL.exists(),'Refuse stale V4 unaccepted output')
    contract=load_contract();native=legacy.inspect_native_report(source.TASK/'artifacts/environment')
    before=source.read_json(legacy.SNAPSHOT);after=legacy.tracked_snapshot(source.ROOT)
    differences=legacy.protection_differences(before,after)
    require(isinstance(differences,list) and len(differences)>0,
            'A source-failure artifact requires an actual nonempty protected-source difference')
    capture=legacy.inspect_capture(source.PROJECT);extra=inspect_extra(source.PROJECT,contract)
    PARTIAL.mkdir(parents=True)
    for name in sorted(legacy.IMAGES):shutil.copyfile(source.PROJECT/'JourneyEvidence/environment'/name,PARTIAL/name)
    for name in sorted(EXTRA_IMAGES):shutil.copyfile(source.PROJECT/EXTRA/name,PARTIAL/name)
    receipt=source.identity();receipt.update(schema='desert-rv-environment-v4-renderer-proof/v1',status=legacy.FAILED_STATUS,accepted=False,
        scope='Unaccepted V4 actual pixels only; source protection failed; not integrated with strict combat/gameplay',protectedTrackedFilesUnchanged=False,
        changedFiles=differences,nativeRenderXmlSha256=native,capture=capture,extra=extra)
    (PARTIAL/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');write_manifest(PARTIAL)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('before','package','partial'));args=parser.parse_args()
    {'before':before,'package':package,'partial':partial}[args.mode]()
