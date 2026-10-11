"""Exact production-HUD fixture captures. No player/device/gameplay acceptance."""
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET
from PIL import Image, ImageStat
import journey_keyboard_look_native as isolated
import journey_tracer_source_diagnostic as source

ROOT=Path(__file__).resolve().parents[3]
TASK=ROOT/'tasks/desert-rv'
ARTIFACTS=TASK/'artifacts/journey-mobile-hud'
CAPTURE_SOURCE=TASK/'journey-keyboard-look-project/JourneyEvidence/MobileHudNative'
EXPORT=TASK/'mobile-hud-native-export'
PREFIX='DesertRV.Tests.JourneyMobileHudTests.'
EXPECTED=tuple(PREFIX+n for n in (
 'LayoutKeepsTargetsSeparatedAndAimClear_SmallPhone','LayoutKeepsTargetsSeparatedAndAimClear_Compact','LayoutKeepsTargetsSeparatedAndAimClear_Wide','LayoutKeepsTargetsSeparatedAndAimClear_Desktop',
 'AndroidScaleRejectsInvalidMetricsAndTracksRenderPixels','SemanticLineBreaksRetainCableCostRiskAndNumbers',
 'InteractionLabelsUseExistingSelectorAndRemainFourCharacters','PauseRegionConsumesPointerAndClearRegionsResetsIt',
 'ActionPriorityAndTwoThumbOwnershipSurviveDragging','RenderProductionHudAndMeasureEveryVisibleLabel'))
PROFILES={'desktop':(960,540),'compact':(1920,1080),'wide':(2400,1080),'small':(1920,960)}
MODES=('foot','drive','pause','loading','failed','complete')
BACKGROUNDS=('day','glare','night')
STEMS=tuple(p+'-'+m+'-'+b for m,b in (('foot','glare'),('drive','day'),('pause','night')) for p in ('desktop','compact','wide'))+('small-foot-glare','compact-loading-glare','compact-failed-night','compact-complete-day')
MANIFEST='capture-manifest.json'
CAPTURE_FILES=frozenset([MANIFEST]+[stem+suffix for stem in STEMS for suffix in ('.png','-fit.csv')])
SCOPE='NATIVE_SIMULATED_DEVICE_PRODUCTION_HUD_FIXTURE_NOT_GAMEPLAY_OR_DEVICE_ACCEPTANCE'
require=isolated.require

def raw(path,limit=16*1024**2):return isolated.file_bytes(path,limit)
def sha(data):return hashlib.sha256(data).hexdigest()
def pin(path):
 data=raw(path);return dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(data),bytes=len(data))

def inspect_xml():
 isolated.safe_path(ARTIFACTS)
 paths=list(ARTIFACTS.rglob('*.xml'));require(len(paths)==1,'MOBILE_HUD_XML_COUNT')
 data=raw(paths[0],1024**2);require(b'<!DOCTYPE' not in data.upper() and b'<!ENTITY' not in data.upper(),'MOBILE_HUD_XML_DECLARATION')
 root=ET.fromstring(data);cases=list(root.iter('test-case'));names=[x.get('fullname') for x in cases]
 require(root.tag=='test-run' and root.get('result')=='Passed' and root.get('total')==root.get('passed')=='10' and
         all(root.get(k)=='0' for k in ('failed','skipped','inconclusive')) and len(names)==len(set(names))==10 and
         set(names)==set(EXPECTED) and all(x.get('result')=='Passed' for x in cases),'MOBILE_HUD_EXACT_TEN')
 return dict(**pin(paths[0]),cases=sorted(names),count=10)

def capture_inventory(folder):
 isolated.safe_path(folder);require(folder.is_dir() and {p.name for p in folder.iterdir()}==CAPTURE_FILES,'MOBILE_HUD_CAPTURE_INVENTORY')
 value=source.json_bytes(raw(folder/MANIFEST,65536))
 require(type(value) is dict and set(value)=={'source','evidence','files'} and
         value['source']=='production JourneyHud graph and pinned CJK font' and
         value['evidence']=='native simulated-device UI render; no physical-device or gameplay acceptance' and
         type(value['files']) is list and len(value['files'])==26,'MOBILE_HUD_CAPTURE_SCHEMA')
 names=[]
 for entry in value['files']:
  require(type(entry) is dict and set(entry)=={'name','bytes','sha256'} and entry['name'] in CAPTURE_FILES-{MANIFEST} and
          type(entry['bytes']) is int and 0<entry['bytes']<=16*1024**2,'MOBILE_HUD_CAPTURE_ENTRY')
  names.append(entry['name']);data=raw(folder/entry['name'])
  require(len(data)==entry['bytes'] and sha(data)==entry['sha256'],'MOBILE_HUD_CAPTURE_HASH')
 require(len(set(names))==26 and set(names)==CAPTURE_FILES-{MANIFEST},'MOBILE_HUD_CAPTURE_ROWS')
 for stem in STEMS:
  profile,mode,background=stem.split('-')
  validate_image_fit(folder,stem,profile,mode,background)
 return [pin(folder/name) for name in sorted(CAPTURE_FILES)]

def validate_image_fit(folder,stem,profile,mode,background):
 with Image.open(io.BytesIO(raw(folder/(stem+'.png')))) as image:
  require(image.format=='PNG' and image.size==PROFILES[profile] and image.mode in ('RGB','RGBA'),'MOBILE_HUD_PNG_SHAPE')
  image.load();require(max(ImageStat.Stat(image.convert('RGB')).stddev)>2,'MOBILE_HUD_PNG_BLANK')
 text=raw(folder/(stem+'-fit.csv'),65536).decode('utf-8')
 reader=csv.DictReader(io.StringIO(text));rows=list(reader)
 require(reader.fieldnames==['profile','mode','background','label','font','available_height','preferred_height'] and 1<=len(rows)<=80,'MOBILE_HUD_FIT_SCHEMA')
 for row in rows:
  require(set(row)==set(reader.fieldnames) and (row['profile'],row['mode'],row['background'])==(profile,mode,background) and
          0<len(row['label'])<=128,'MOBILE_HUD_FIT_ROW')
  numbers=[float(row[k]) for k in ('font','available_height','preferred_height')]
  require(all(math.isfinite(x) for x in numbers) and (12 if row['label']=='Journey label' else 14)<=numbers[0]<=128 and 0<numbers[1]<=1000 and
          0<numbers[2]<=numbers[1]+1,'MOBILE_HUD_FIT_CLIPPED')

WORLD_SOURCE=TASK/'unity/JourneyEvidence/MobileHudWorld'
WORLD_EXPORT=TASK/'mobile-hud-world-export'
WORLD_STEMS=('desktop-foot-region-1','desktop-foot-region-3')
WORLD_FILES=frozenset(['EVIDENCE.txt']+[stem+suffix for stem in WORLD_STEMS for suffix in ('.png','-fit.csv')])
WORLD_EVIDENCE='Authored, loaded world camera + production UGUI layout fixture. HUD values are controlled fixture data. Not live gameplay or physical-device acceptance. No scenes opened, saved or replaced.\n'

def world_inventory(folder):
 isolated.safe_path(folder);require(folder.is_dir() and {p.name for p in folder.iterdir()}==WORLD_FILES,'MOBILE_HUD_WORLD_INVENTORY')
 require(raw(folder/'EVIDENCE.txt',1024).decode('utf-8')==WORLD_EVIDENCE,'MOBILE_HUD_WORLD_SCOPE')
 for stem in WORLD_STEMS:
  profile,mode,background=stem.split('-',2);validate_image_fit(folder,stem,profile,mode,background)
 return [pin(folder/name) for name in sorted(WORLD_FILES)]

def world_report(folder):
 preparation=TASK/'journey-preparation-export/preparation.json';value=source.json_bytes(raw(preparation,1024**2))
 require(value['sourceCommit']==os.environ['GITHUB_SHA'] and value['status']=='PREPARED_EDITOR_SCOPE_UNREVIEWED' and
         value['visualApproved'] is False and value['gameplayAccepted'] is False and
         value['nativeCase']=='DesertRV.Tests.JourneyPreparationTests.PrepareVerifiedSameWorkspaceJourney','MOBILE_HUD_WORLD_PREPARATION')
 return dict(schema=1,**isolated.owner_identity(os.environ),scope='AUTHORED_WORLD_CAMERA_WITH_PRODUCTION_HUD_FIXTURE_NOT_GAMEPLAY',
             preparation=pin(preparation),files=world_inventory(folder),deviceExecuted=False,gameplayAccepted=False,approved=False)

def verify_world():
 isolated.safe_path(WORLD_EXPORT)
 require(WORLD_EXPORT.is_dir() and {p.name for p in WORLD_EXPORT.iterdir()}=={'captures','world-report.json'},'MOBILE_HUD_WORLD_EXPORT')
 report=source.json_bytes(raw(WORLD_EXPORT/'world-report.json',16384))
 require(report==world_report(WORLD_EXPORT/'captures'),'MOBILE_HUD_WORLD_REPORT_CHANGED')
 return [pin(WORLD_EXPORT/'world-report.json'),*report['files']]

def world():
 require(os.environ.get('NATIVE_OUTCOME')=='success','MOBILE_HUD_WORLD_NATIVE_OUTCOME')
 world_report(WORLD_SOURCE);isolated.safe_path(WORLD_EXPORT);require(not WORLD_EXPORT.exists(),'MOBILE_HUD_WORLD_EXPORT_EXISTS')
 WORLD_EXPORT.mkdir();destination=WORLD_EXPORT/'captures';destination.mkdir()
 for name in sorted(WORLD_FILES):shutil.copyfile(WORLD_SOURCE/name,destination/name)
 isolated.write_new(WORLD_EXPORT/'world-report.json',world_report(destination),16384)
 verify_world();isolated.output(os.environ,'world_verified=true\nexport_ready=true\n')

def current_report(folder):
 identity=isolated.owner_identity(os.environ)
 isolation_raw=raw(isolated.ISOLATION_REPORT,isolated.MAX_ISOLATION_REPORT);isolation=source.json_bytes(isolation_raw)
 source_sha=sha(raw(TASK/'SOURCE-STATE.json',4*1024**2))
 require(isolated.validate_isolation(isolation) and isolation['status']=='PASS' and isolation['sourceStateSha256']==source_sha and
         all(isolation[k]==v for k,v in identity.items()),'MOBILE_HUD_ISOLATION')
 return dict(schema=1,status='EXACT_TEN_AND_13_RENDER_FIXTURES_VERIFIED',**identity,scope=SCOPE,
             sourceStateSha256=source_sha,isolationReportSha256=sha(isolation_raw),nativeXml=inspect_xml(),
             captures=capture_inventory(folder),deviceExecuted=False,gameplayAccepted=False,approved=False)

def verify():
 isolated.safe_path(EXPORT)
 require(EXPORT.is_dir() and {p.name for p in EXPORT.iterdir()}=={'captures','native-report.json'},'MOBILE_HUD_EXPORT_INVENTORY')
 report=source.json_bytes(raw(EXPORT/'native-report.json',65536))
 require(report==current_report(EXPORT/'captures'),'MOBILE_HUD_REPORT_CHANGED')
 return dict(report=pin(EXPORT/'native-report.json'),nativeXml=report['nativeXml'],captures=report['captures'],scope=SCOPE)

def native():
 require(os.environ.get('NATIVE_OUTCOME')=='success','MOBILE_HUD_NATIVE_OUTCOME')
 isolated.verify_unchanged();current_report(CAPTURE_SOURCE)
 isolated.safe_path(EXPORT);require(not EXPORT.exists(),'MOBILE_HUD_EXPORT_EXISTS')
 EXPORT.mkdir();destination=EXPORT/'captures';destination.mkdir()
 for name in sorted(CAPTURE_FILES):shutil.copyfile(CAPTURE_SOURCE/name,destination/name)
 isolated.write_new(EXPORT/'native-report.json',current_report(destination),65536)
 verify();isolated.output(os.environ,'native_verified=true\nexport_ready=true\n')

def main():
 require(sys.argv[1:] in (['native'],['world']),'MOBILE_HUD_ARGUMENTS')
 try: {'native':native,'world':world}[sys.argv[1]]()
 except Exception:
  print('MOBILE_HUD_NATIVE_OR_CAPTURE_GATE_FAILED');return 2
 print('MOBILE_HUD_'+sys.argv[1].upper()+'_VERIFIED');return 0
if __name__=='__main__':raise SystemExit(main())
