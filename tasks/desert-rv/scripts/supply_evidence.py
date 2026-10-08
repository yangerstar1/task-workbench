#!/usr/bin/env python3
"""Nine real supply editor-fixture views; never input/playthrough/production approval."""
import argparse,difflib,json,math,re,shutil,tempfile,os
from pathlib import Path
import xml.etree.ElementTree as ET
import environment_evidence as env
import verify_evidence as source

VIEWS=('directions-before','ammo-before','repair-sealed-after-ammo')
IMAGES={f'{region}-{view}.png' for region in env.REGIONS for view in VIEWS}
TEST='DesertRV.Tests.JourneySupplyRenderTests.AuthorAndCaptureSupplyViews'
STATUS='EDITOR_VISUAL_FIXTURE_NOT_INPUT_PLAYTHROUGH'
OUT=source.TASK/'evidence/supplies'
def require(ok,msg):source.require(ok,msg)
def vector(v):
 require(isinstance(v,dict) and set(v)=={'x','y','z'} and all(type(n) in (int,float) and math.isfinite(n) and abs(n)<10000 for n in v.values()),'Invalid camera vector')
def inspect_report(project):
 folder=project/'JourneyEvidence/supplies';report=source.read_json(folder/'capture-report.json')
 require(set(report)=={'status','graphicsDeviceType','graphicsDeviceName','bufferSceneTransitionsChecked','captureBuffersReleased','savedScenes','fixtures','images'},'Unexpected capture fields')
 require(report['status']==STATUS and report['graphicsDeviceType']=='OpenGLCore' and 'llvmpipe' in report['graphicsDeviceName'].lower(),'Not actual software OpenGL fixture')
 require(report['bufferSceneTransitionsChecked']==3 and report['captureBuffersReleased'] is True,'Capture buffer lifecycle failed')
 rows=report['images'];require(isinstance(rows,list) and len(rows)==9,'Exactly nine images required')
 seen=set()
 for row in rows:
  require(set(row)=={'region','view','file','cameraPosition','lookAt'} and type(row['region']) is int and row['region'] in (1,2,3) and row['view'] in VIEWS,'Invalid image record')
  name=f"{env.REGIONS[row['region']-1]}-{row['view']}.png"
  require(row['file']=='JourneyEvidence/supplies/'+name and name not in seen,'Wrong or duplicate image identity');seen.add(name)
  vector(row['cameraPosition']);vector(row['lookAt']);env.inspect_png(folder/name)
 require(seen==IMAGES and {p.name for p in folder.iterdir()}==IMAGES|{'capture-report.json'},'Screenshot allowlist mismatch')
 required={env.GENERATED+'/'+n+'.unity'+ext for n in ('JourneyBootstrap',*env.REGIONS) for ext in ('','.meta')}
 hashes=report['savedScenes'];require(len(hashes)==8 and {x['path'] for x in hashes}==required,'Saved scene hash inventory mismatch')
 for row in hashes:
  require(set(row)=={'path','beforeSha256','afterSha256'} and re.fullmatch('[a-f0-9]{64}',row['beforeSha256']) and row['beforeSha256']==row['afterSha256']==source.sha(project/row['path']),'Saved scene altered by fixture')
 fixtures=report['fixtures'];require(len(fixtures)==3 and {f['region'] for f in fixtures}=={1,2,3},'Missing choice fixtures')
 ids=(('apron-ammo','garage-kit'),('container-ammo','canopy-kit'),('tower-ammo','relay-kit'))
 for row in fixtures:
  require(set(row)=={'region','reserveBefore','reserveAfter','repairBefore','repairAfter','selectedId','blockedId','otherRejected','selectedOfferHidden','otherSealed','selectedBoxStillPresent'},'Unexpected fixture fields')
  require(all(type(row[k]) is int for k in ('region','reserveBefore','reserveAfter','repairBefore','repairAfter')),'Invalid fixture numeric fields')
  region=row['region'];selected,blocked=ids[region-1]
  require(row['selectedId']==f'region-{region}/optional/{selected}' and row['blockedId']==f'region-{region}/optional/{blocked}','Choice identity mismatch')
  require(row['reserveBefore']==96 and row['reserveAfter']==96+(12 if region==1 else 18) and row['repairBefore']==row['repairAfter']==2,'Fixture reward mismatch')
  require(all(row[k] is True for k in ('otherRejected','selectedOfferHidden','otherSealed','selectedBoxStillPresent')),'Fixture did not exercise real rule rejection and view state')
 return report

def native(directory):
 paths=list(directory.rglob('*.xml'));require(0<len(paths)<=20,'Missing native XML')
 reports=[]
 for p in paths:
  require(source.safe(p).stat().st_size<=10*1024**2,'Native XML too large')
  root=ET.parse(p).getroot()
  if root.tag=='test-run':reports.append((p,root))
 require(len(reports)==1,'One native test run required');p,root=reports[0];cases=list(root.iter('test-case'))
 require(root.get('result')=='Passed' and len(cases)==1 and cases[0].get('fullname')==TEST and cases[0].get('result')=='Passed','Wrong/failed supply native test')
 return source.sha(p)

def inspect_placement(project):
 reports=[]
 for region in (1,2,3):
  r=source.read_json(project/f'JourneyEvidence/supply-placement-region-{region}.json')
  require(set(r)=={'status','region','supplies'} and r['region']==region and r['status']=='NATIVE_STATIC_PLACEMENT_ONLY_NOT_GAMEPLAY_ACCEPTANCE' and len(r['supplies'])==2,'Invalid placement report')
  for x in r['supplies']:
   require(set(x)=={'id','group','casePosition','stand','interaction','reachDistance','approachSamples','lineOfSight','walkingCapsuleClear','caseClear','optionalOnly'},'Unexpected placement fields')
   require(x['group']==f'region-{region}/optional-choice' and x['id'].startswith(f'region-{region}/optional/'),'Wrong placement identity')
   for k in ('casePosition','stand','interaction'):vector(x[k])
   require(type(x['reachDistance']) in (int,float) and math.isfinite(x['reachDistance']) and 0<x['reachDistance']<=2.2 and type(x['approachSamples']) is int and 2<=x['approachSamples']<=100,'Invalid reach geometry')
   require(all(x[k] is True for k in ('lineOfSight','walkingCapsuleClear','caseClear','optionalOnly')),'Placement check failed')
  reports.append(r)
 return reports

def package():
 require(not OUT.exists(),'Stale supply export')
 before=source.read_json(env.SNAPSHOT);env.assert_preserved(before,env.tracked_snapshot(source.ROOT))
 xml=native(source.TASK/'artifacts/supplies');report=inspect_report(source.PROJECT);placement=inspect_placement(source.PROJECT);clearance=env.inspect_clearance(source.PROJECT);names=env.collect_generated(source.PROJECT)
 OUT.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.supply-',dir=OUT.parent))
 try:
  for name in sorted(IMAGES):shutil.copyfile(source.PROJECT/'JourneyEvidence/supplies'/name,stage/name)
  records=[];diff=[]
  for name in names:
   p=source.PROJECT/name;dest=stage/'generated'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
   records.append(dict(path=name,sha256=source.sha(p),size=p.stat().st_size));diff.extend(difflib.unified_diff([],p.read_text().splitlines(True),fromfile='/dev/null',tofile='b/'+name))
  receipt=source.identity();receipt.update(scope=STATUS,status='VERIFIED_EDITOR_FIXTURE_NOT_ACCEPTED',accepted=False,inputPlaythrough='NOT_RUN',androidApk='NOT_RUN',productionApproval=False,protectedTrackedFilesUnchanged=True,protectedTrackedFileCount=len(before),nativeTest=TEST,nativeXmlSha256=xml,capture=report,placement=placement,clearance=clearance,generated=records)
  (stage/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');(stage/'generated-new-scenes.diff').write_text(''.join(diff))
  hashes=[dict(path=p.relative_to(stage).as_posix(),sha256=source.sha(p),size=p.stat().st_size) for p in sorted(stage.rglob('*')) if p.is_file()]
  (stage/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2)+'\n');stage.rename(OUT)
 finally:
  if stage.exists():shutil.rmtree(stage)
 print('Nine validated editor fixture images; original tracked source unchanged; no gameplay or production approval.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['package']);p.parse_args();package()
