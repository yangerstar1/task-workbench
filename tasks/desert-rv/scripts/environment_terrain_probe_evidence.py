"""Eight-image channel-ablation evidence only. Production twenty-view gates stay unchanged."""
import argparse,json,math,re,shutil,xml.etree.ElementTree as ET
from pathlib import Path
import verify_evidence as source
import environment_evidence as legacy

STATUS='DIAGNOSTIC_CHANNEL_ABLATION_NOT_ART_ACCEPTANCE'
VARIANTS=('original','normal-off','diffuse-flat','diffuse-flat-normal-off')
CAMERAS={'overview':(54,{'x':31,'y':39,'z':-17},{'x':0,'y':0,'z':28}),
         'ground':(58,{'x':-5,'y':1.65,'z':-7},{'x':2,'y':2.2,'z':25})}
IMAGES={f'Scrapyard-{view}-{variant}.png' for view in CAMERAS for variant in VARIANTS}
RENDER_TEST='DesertRV.Tests.JourneyTerrainProbeTests.AuthorAndCaptureEightChannelAblations'
CAPTURE='JourneyEvidence/terrain-probe'
OUT=source.TASK/'evidence/terrain-probe'
ART='Assets/DesertRV/Art/EnvironmentV4/'
REPORT_KEYS={'status','graphicsDeviceType','graphicsDeviceName','savedSceneAndMaterialBytesPreserved','captureBuffersReleased','terrainRenderers','flatDiffuseSrgbBytes','originalMaterials','images'}
IMAGE_KEYS={'file','view','variant','sceneHash','width','height','fieldOfView','minimum','maximum','normalEnabled','flatDiffuse','cameraPosition','cameraTarget'}
MATERIAL_KEYS={'name','shader','baseMapAsset','normalMapAsset','normalScale','smoothness','metallic','baseScale','baseOffset','baseColor'}
require=source.require

def close(a,b):return type(a) in (float,int) and math.isfinite(a) and abs(a-b)<.00001

def vector(value,expected):return isinstance(value,dict) and set(value)==set(expected) and all(close(value[k],v) for k,v in expected.items())

def inspect_native(directory):
 paths=list(directory.rglob('*.xml'));require(0<len(paths)<=20,'Native XML count')
 for p in paths:require(source.safe(p).stat().st_size<=10*1024**2,'Native XML size')
 reports=[p for p in paths if ET.parse(p).getroot().tag=='test-run'];require(len(reports)==1,'One diagnostic native report required')
 root=ET.parse(reports[0]).getroot();cases=list(root.iter('test-case'))
 require(root.get('result')=='Passed' and len(cases)==1,'Wrong native case count or failed run')
 require(cases[0].get('fullname')==RENDER_TEST and cases[0].get('result')=='Passed','Wrong diagnostic native test')
 return source.sha(reports[0])

def validate_report(report):
 require(isinstance(report,dict) and set(report)==REPORT_KEYS,'Probe report fields')
 require(report['status']==STATUS and report['graphicsDeviceType']=='OpenGLCore','Probe scope/device')
 name=report['graphicsDeviceName'];require(isinstance(name,str) and len(name)<256 and 'llvmpipe' in name.lower(),'Expected actual Mesa device')
 require(report['savedSceneAndMaterialBytesPreserved'] is True and report['captureBuffersReleased'] is True,'Probe preservation/cleanup')
 require(type(report['terrainRenderers']) is int and report['terrainRenderers']==3,'Three terrain renderer groups')
 require(report['flatDiffuseSrgbBytes']==[108,96,79] and all(type(x) is int for x in report['flatDiffuseSrgbBytes']),'Wrong source mean texture')
 materials=report['originalMaterials'];require(isinstance(materials,list) and len(materials)==2,'Original material count')
 names=set()
 for m in materials:
  require(isinstance(m,dict) and set(m)==MATERIAL_KEYS,'Material fields')
  require(m['name'] in ('Surface-Sand','Surface-Dune') and m['name'] not in names,'Material identity');names.add(m['name'])
  require(m['shader']=='Universal Render Pipeline/Lit','Production Lit required')
  require(m['baseMapAsset']==ART+'sand_03_diff_1k.jpg' and m['normalMapAsset']==ART+'sand_03_nor_gl_1k.jpg','Production texture identity')
  require(close(m['normalScale'],.035) and close(m['smoothness'],.04) and close(m['metallic'],0),'Production BRDF identity')
  require(vector(m['baseScale'],{'x':1,'y':1}) and vector(m['baseOffset'],{'x':0,'y':0}),'Production UV transform')
  require(vector(m['baseColor'],{'r':1.75,'g':1.52,'b':1.16,'a':1}),'Production base tint')
 records=report['images'];require(isinstance(records,list) and len(records)==8,'Eight diagnostic records required')
 seen=set();hashes=set()
 for r in records:
  require(isinstance(r,dict) and set(r)==IMAGE_KEYS,'Image record fields')
  view=r['view'];variant=r['variant'];require(view in CAMERAS and variant in VARIANTS,'Unknown probe view/state')
  file=f'Scrapyard-{view}-{variant}.png';require(r['file']==file and file not in seen,'File identity/duplicate');seen.add(file)
  require(r['normalEnabled'] is (not variant.endswith('normal-off')) and r['flatDiffuse'] is variant.startswith('diffuse-flat'),'Channel ablation state')
  fov,at,look=CAMERAS[view];require(close(r['fieldOfView'],fov) and vector(r['cameraPosition'],at) and vector(r['cameraTarget'],look),'Original fixed camera pose')
  require(type(r['width']) is int and type(r['height']) is int and (r['width'],r['height'])==(1440,900),'Capture dimensions')
  low,high=r['minimum'],r['maximum'];require(all(type(x) in (int,float) and math.isfinite(x) for x in (low,high)) and 0<=low<=high<=1 and high-low>=.06 and high>=.1,'Capture pixel range')
  require(isinstance(r['sceneHash'],str) and re.fullmatch('[0-9a-f]{32}',r['sceneHash']),'Scene dependency hash');hashes.add(r['sceneHash'])
 require(seen==IMAGES and len(hashes)==1,'Incomplete channel set or changed saved scene')
 return report

def inspect_capture(project):
 directory=project/CAPTURE
 require(directory.is_dir() and {p.name for p in directory.iterdir()}==IMAGES|{'probe-report.json'},'Probe capture closed set')
 report=validate_report(source.read_json(directory/'probe-report.json'))
 for name in IMAGES:legacy.inspect_png(directory/name)
 layout=source.read_json(project/'JourneyEvidence/candidate-layout.json');require(layout.get('passed') is True,'Candidate layout gate')
 clearance=legacy.inspect_clearance(project)
 return report,clearance

def package():
 require(not OUT.exists(),'Refuse stale diagnostic output')
 protected=source.read_json(legacy.SNAPSHOT);legacy.assert_preserved(protected,legacy.tracked_snapshot(source.ROOT))
 native=inspect_native(source.TASK/'artifacts/terrain-probe')
 capture,clearance=inspect_capture(source.PROJECT)
 identity=source.identity();require(identity['runAttempt']=='1','Diagnostic replay')
 OUT.mkdir(parents=True)
 for name in sorted(IMAGES):shutil.copyfile(source.PROJECT/CAPTURE/name,OUT/name)
 receipt=dict(identity,schema='desert-rv-terrain-channel-probe/v1',scope=STATUS,visualAcceptance='NOT_ACCEPTED',gameplayIntegration='NOT_RUN',
  protectedTrackedFilesUnchanged=True,protectedTrackedFileCount=len(protected),protectedSnapshotSha256=source.sha(legacy.SNAPSHOT),
  nativeRenderTest=RENDER_TEST,nativeRenderXmlSha256=native,capture=capture,clearance=clearance,
  imageHashes=[dict(file=name,sha256=source.sha(OUT/name)) for name in sorted(IMAGES)])
 (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 rows=[dict(path=p.name,sha256=source.sha(p),size=p.stat().st_size) for p in sorted(OUT.iterdir())]
 (OUT/'SHA256SUMS.json').write_text(json.dumps(rows,indent=2)+'\n')
 require({p.name for p in OUT.iterdir()}==IMAGES|{'receipt.json','SHA256SUMS.json'},'Sanitized diagnostic output set')
 print('Eight actual fixed-camera channel ablations verified. Diagnostic only, no visual acceptance.')

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=('before','package'));args=parser.parse_args()
 if args.command=='before':legacy.before()
 else:package()
