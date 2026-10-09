"""Explicit same-job candidate Linux build request; no cross-run scope restoration."""
import json,os,sys
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];TASK=ROOT/'tasks/desert-rv';PROJECT=TASK/'unity'
sys.path.insert(0,str(TASK/'art/import-candidate'));sys.path.insert(0,str(TASK/'scripts/rendered'))
from strict_output import read,sha,require,digest,verify_staged_inventory,safe
import generated_export as generated
import prepared_source

BOUNDARY_NAMES=('DesertRV.Tests.CandidateLinuxBoundaryTests.ExactLinuxDevelopmentProfileAccepted', 'DesertRV.Tests.CandidateLinuxBoundaryTests.MissingDefineRejected', 'DesertRV.Tests.CandidateLinuxBoundaryTests.ExtraDefineRejected', 'DesertRV.Tests.CandidateLinuxBoundaryTests.NonLinuxRejected', 'DesertRV.Tests.CandidateLinuxBoundaryTests.NonDevelopmentRejected', 'DesertRV.Tests.CandidateLinuxBoundaryTests.ExtraBuildOptionsRejected', 'DesertRV.Tests.CandidateLinuxBoundaryTests.OrdinaryEntrypointHasNoCandidateLease', 'DesertRV.Tests.CandidateLinuxBoundaryTests.RuntimeCapabilityInactiveInEditor', 'DesertRV.Tests.CandidateLinuxBoundaryTests.EmptySerializedIdentityRejected', 'DesertRV.Tests.CandidateLinuxBoundaryTests.NullManifestCannotSupplyRealAssets', 'DesertRV.Tests.CandidateLinuxBoundaryTests.ProductionGateStillRejectsUnapprovedFormalScenes', 'DesertRV.Tests.CandidateLinuxBoundaryTests.ExactPhysicalInventoryAccepted', 'DesertRV.Tests.CandidateLinuxBoundaryTests.UnlistedExecutableScriptRejected', 'DesertRV.Tests.CandidateLinuxBoundaryTests.UnlistedMetaRejected', 'DesertRV.Tests.CandidateLinuxBoundaryTests.MissingSceneMetaRejected', 'DesertRV.Tests.CandidateLinuxBoundaryTests.UndeclaredEmptyDirectoryRejected', 'DesertRV.Tests.CandidateLinuxBoundaryTests.AtomicJsonReplacementKeepsOnlyCompleteLatestFile')
BOUNDARY_SOURCE='tasks/desert-rv/unity/Assets/DesertRV/Tests/CandidateLinux/CandidateLinuxBoundaryTests.cs'

def boundary_evidence():
    folder=TASK/'artifacts/journey-linux-boundary'
    paths=list(folder.rglob('*.xml'));require(len(paths)==1,'LINUX_BOUNDARY_XML_COUNT')
    path=safe(paths[0]);require(path.stat().st_size<=10*1024**2,'LINUX_BOUNDARY_XML_SIZE')
    xml=ET.parse(path).getroot();cases=list(xml.iter('test-case'));names=[c.get('fullname') for c in cases]
    require(xml.tag=='test-run' and xml.get('result')=='Passed' and xml.get('total')=='17' and xml.get('passed')=='17' and
            all(xml.get(k)=='0' for k in ('failed','skipped','inconclusive')) and len(names)==17 and len(set(names))==17 and
            set(names)==set(BOUNDARY_NAMES) and all(c.get('result')=='Passed' for c in cases),'LINUX_BOUNDARY_NATIVE_FAILED')
    return dict(schema=1,status='EXACT_NATIVE_BOUNDARY_PASSED',sourceCommit=os.environ['GITHUB_SHA'],
                producerRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/'+os.environ['GITHUB_RUN_ID'],
                nativeXml=dict(path=str(path.relative_to(ROOT)),sha256=sha(path)),nativeCases=sorted(names),
                source=dict(path=BOUNDARY_SOURCE,sha256=sha(ROOT/BOUNDARY_SOURCE)))
def verify_boundary():
    from pipeline import state,check_state
    current=state();require(current.get('phase')=='ready-input-frozen','LINUX_BOUNDARY_STAGE')
    check_state(current);prepared_source.verify_original(current['initialIdentity'])
    result=boundary_evidence();destination=PROJECT/'JourneyEvidence/JourneyPreparation/linux-boundary-verified.json'
    require(not destination.exists(),'LINUX_BOUNDARY_ALREADY_RECORDED')
    destination.write_text(json.dumps(result,indent=2)+'\n');return result
def bound_boundary():
    result=boundary_evidence();receipt=PROJECT/'JourneyEvidence/JourneyPreparation/linux-boundary-verified.json'
    require(read(receipt)==result,'LINUX_BOUNDARY_PROOF_CHANGED');return result

def prepare():
    proof=prepared_source.verify();boundary=bound_boundary();state=read(prepared_source.STATE)
    receipt_path=TASK/'journey-preparation-export/generated/receipt.json';receipt=read(receipt_path)
    commit=os.environ['GITHUB_SHA'];run='https://github.com/yangerstar1/task-workbench/actions/runs/'+os.environ['GITHUB_RUN_ID']
    require(receipt['schema']==generated.SCHEMA and receipt['status']=='GENERATED_JOURNEY_SAVED_UNREVIEWED' and receipt['sourceCommit']==commit and receipt['importRunUrl']==run and receipt['unityVersion']==generated.UNITY and receipt['approved'] is False and receipt['scopeReusable'] is False,'LINUX_REAL_GENERATED_EXPORT_REQUIRED')
    require(receipt['sourceStateSha256']==sha(TASK/'SOURCE-STATE.json'),'LINUX_SOURCE_STATE_CHANGED')
    verify_staged_inventory(receipt_path.parent,receipt['files'],sha(receipt_path))
    strict,refs=generated.strict_sources(TASK,state,PROJECT,commit,run);require(refs==receipt['strictReceipts'],'LINUX_THREE_RECEIPTS_CHANGED')
    native=read(receipt_path.parent/'native-authored-assets.json')
    require(sha(receipt_path.parent/'native-authored-assets.json')==receipt['nativeManifestSha256'],'LINUX_NATIVE_MANIFEST_CHANGED')
    require(receipt.get('spawnGroundingPath')==generated.GROUND_EXPORT,'LINUX_GROUNDING_PATH')
    ground_path=PROJECT/generated.GROUND_PATH;ground,ground_sha=generated.sealed_json(ground_path,proof,ROOT)
    require(receipt.get('spawnGroundingSha256')==ground_sha==sha(receipt_path.parent/generated.GROUND_EXPORT),'LINUX_GROUNDING_CHANGED')
    generated.validate_spawn_grounding(ground,native,state,PROJECT,commit,ground_sha)
    source_state=read(TASK/'SOURCE-STATE.json');prefix='tasks/desert-rv/unity/'
    source={r['path'][len(prefix):]:r['sha256'] for r in source_state['files']+source_state['restoredFiles'] if r['path'].startswith(prefix)}
    authored={r['path']:r['sha256'] for r in native['files']}
    require(proof['addedAssets']=={**strict,**authored},'LINUX_EXACT_NATIVE_ASSET_UNION')
    dependencies=generated.native_closure(native,authored,source,strict,PROJECT,commit,run)
    require(dependencies==receipt['dependencies'],'LINUX_DEPENDENCIES_CHANGED')
    pins={r['path']:r for r in source_state['files']+source_state['restoredFiles']}
    for name,h in {**strict,**authored}.items():pins[prefix+name]=dict(path=prefix+name,sha256=h,size=(PROJECT/name).stat().st_size)
    records=[dict(path=name,sha256=sha(ROOT/name)) for name in sorted(pins)]
    records.append(dict(path='tasks/desert-rv/SOURCE-STATE.json',sha256=sha(TASK/'SOURCE-STATE.json')))
    for kind in generated.KINDS:
        name='tasks/desert-rv/journey-preparation-export/'+kind+'/receipt.json';records.append(dict(path=name,sha256=sha(ROOT/name)))
    records.append(dict(path=str(receipt_path.relative_to(ROOT)),sha256=sha(receipt_path)))
    records.append(dict(path=str(ground_path.relative_to(ROOT)),sha256=ground_sha))
    records.append(boundary['nativeXml'])
    boundary_receipt=PROJECT/'JourneyEvidence/JourneyPreparation/linux-boundary-verified.json';records.append(dict(path=str(boundary_receipt.relative_to(ROOT)),sha256=sha(boundary_receipt)))
    request=dict(schema=1,label='CANDIDATE_LINUX_DEVELOPMENT_ONLY',sourceCommit=commit,producerRunUrl=run,generatedReceiptSha256=sha(receipt_path),
                 boundaryNativeXmlSha256=boundary['nativeXml']['sha256'],boundaryNativeCases=17,define='DESERTRV_CANDIDATE_LINUX',target='StandaloneLinux64',development=True,approved=False,files=records,dependencies=dependencies,scenes=receipt['integrationOutputs'],
                 directories=sorted(name+'/'+directory for name in ('Assets','Packages','ProjectSettings') for directory in prepared_source.walk(PROJECT/name)[1]))
    destination=PROJECT/'JourneyEvidence/JourneyPreparation/linux-build-input.json';require(not destination.exists(),'LINUX_BUILD_REQUEST_EXISTS')
    prepared_source.verify();destination.write_text(json.dumps(request,indent=2)+'\n');destination.with_suffix('.sha256').write_text(sha(destination)+'\n')
    return request
if __name__=='__main__':
    from pipeline import guard
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('prepare','verify','verify-boundary'));args=parser.parse_args()
    guard()
    if args.command=='prepare':prepare()
    elif args.command=='verify-boundary':verify_boundary()
    else:prepared_source.verify();bound_boundary()
