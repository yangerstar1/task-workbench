"""Exact production-HUD fixture captures. No player/device/gameplay acceptance."""
import csv
from contextlib import contextmanager
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
WORLD_DIAGNOSTIC=TASK/'mobile-hud-world-diagnostic/world-diagnostic.json'
WORLD_STEMS=('desktop-foot-region-1','desktop-foot-region-3')
WORLD_FILES=frozenset(['EVIDENCE.txt']+[stem+suffix for stem in WORLD_STEMS for suffix in ('.png','-fit.csv')])
WORLD_EVIDENCE='Authored, loaded world camera + production UGUI layout fixture. HUD values are controlled fixture data. Not live gameplay or physical-device acceptance. Saved scenes opened read-only for capture; no scenes saved or replaced.\n'

# Diagnostics expose only fixed phases and codes, never arbitrary exception text/paths.
SAFE_ERROR_CODES=frozenset({
 'MOBILE_HUD_ARGUMENTS','MOBILE_HUD_WORLD_NATIVE_OUTCOME','MOBILE_HUD_WORLD_MODE',
 'MOBILE_HUD_WORLD_SOURCE_MISSING','MOBILE_HUD_WORLD_INVENTORY','MOBILE_HUD_WORLD_SCOPE',
 'MOBILE_HUD_WORLD_PREPARATION','MOBILE_HUD_WORLD_RESTORATION','MOBILE_HUD_WORLD_EXPORT_EXISTS',
 'MOBILE_HUD_WORLD_EXPORT','MOBILE_HUD_WORLD_REPORT_CHANGED','MOBILE_HUD_WORLD_COPY_CHANGED',
 'MOBILE_HUD_PNG_SHAPE','MOBILE_HUD_PNG_BLANK','MOBILE_HUD_FIT_SCHEMA','MOBILE_HUD_FIT_ROW',
 'MOBILE_HUD_FIT_CLIPPED','UNSAFE_PATH','UNSAFE_FILE','FILE_CHANGED','REPORT_PATH','IDENTITY',
 'MOBILE_HUD_NATIVE_OUTCOME','MOBILE_HUD_EXPORT_EXISTS','MOBILE_HUD_EXPORT_INVENTORY',
 'MOBILE_HUD_REPORT_CHANGED','MOBILE_HUD_ISOLATION','MOBILE_HUD_XML_COUNT','MOBILE_HUD_XML_DECLARATION',
 'MOBILE_HUD_EXACT_TEN','MOBILE_HUD_CAPTURE_INVENTORY','MOBILE_HUD_CAPTURE_SCHEMA',
 'MOBILE_HUD_CAPTURE_ENTRY','MOBILE_HUD_CAPTURE_HASH','MOBILE_HUD_CAPTURE_ROWS',
 'RESTORE_CONSUMER_IDENTITY','RESTORE_PRIVATE_PROOF_CHANGED','RESTORE_ORIGINAL_ZIP_CHANGED',
 'RESTORE_PUBLIC_BUNDLE_CHANGED','RESTORE_PRODUCER_SOURCE_CHANGED','RESTORE_POLICY_CHANGED',
 'RESTORE_SOURCE_TRANSITION_CHANGED','RESTORE_ASSET_INVENTORY_CHANGED','RESTORE_OLD_SCOPE_FORBIDDEN',
 'RESTORE_SAFE_REPORT_CHANGED','RESTORE_NATIVE_INPUT_CHANGED','RESTORE_NATIVE_XML_COUNT',
 'RESTORE_NATIVE_XML_SIZE','RESTORE_NATIVE_NOT_PASSED','RESTORE_NATIVE_PROOF_CHANGED',
 'RESTORE_NATIVE_REPORT_IDENTITY','RESTORE_NATIVE_REPORT_NOT_READY','RESTORE_NATIVE_SCENE_SET',
 'RESTORE_NATIVE_SCENE_PIN','RESTORE_NATIVE_DEPENDENCY_BYTES_CHANGED','RESTORE_NATIVE_GROUNDING_CHANGED',
 'RESTORE_GENERATED_RECEIPT','RESTORE_STRICT_IDENTITY','RESTORE_GENERATED_IDENTITY',
 'RESTORE_ORIGINAL_EVIDENCE_BYTES','RESTORE_NATIVE_ASSET_SET','RESTORE_TOPLEVEL_ALLOWLIST',
 'RESTORE_PRODUCER_SUMMARY','RESTORE_ORIGINAL_CLOSURE_CHANGED','RESTORE_PACKAGE_CONTROLS',
 'RESTORE_PACKAGE_CONTROL_COUNT','RESTORE_UNREVIEWED_SOURCE_CHANGE','RESTORE_EXACT_SOURCE_DIFF',
 'MOBILE_HUD_DIAGNOSTIC_EXISTS','MOBILE_HUD_DIAGNOSTIC_SCHEMA','MOBILE_HUD_DIAGNOSTIC_CHANGED',
 'MOBILE_HUD_DIAGNOSTIC_DIRECTORY'})

class GateFailure(ValueError):
 def __init__(self,phase,code):
  self.phase=phase;self.code=code;super().__init__(code)

def safe_error_code(error):
 if isinstance(error,PermissionError):return 'PERMISSION_DENIED'
 if isinstance(error,FileNotFoundError):return 'FILE_MISSING'
 if isinstance(error,FileExistsError):return 'OUTPUT_EXISTS'
 if isinstance(error,OSError):return 'IO_ERROR'
 if isinstance(error,UnicodeError):return 'TEXT_ENCODING_INVALID'
 if isinstance(error,json.JSONDecodeError):return 'JSON_INVALID'
 if isinstance(error,csv.Error):return 'CSV_INVALID'
 if isinstance(error,(KeyError,TypeError)):return 'SCHEMA_INVALID'
 if isinstance(error,ValueError) and str(error) in SAFE_ERROR_CODES:return str(error)
 return 'VALIDATION_FAILED'

@contextmanager
def gate_phase(phase):
 try:yield
 except GateFailure:raise
 except Exception as error:raise GateFailure(phase,safe_error_code(error)) from error


DIAGNOSTIC_PHASES=frozenset({'COMPLETE','ARGUMENTS','NATIVE_OUTCOME','WORLD_GATE','PREPARATION_READ',
 'PREPARATION_IDENTITY','RESTORATION_VERIFY','CAPTURE_VALIDATION','PREPARATION_PIN','EXPORT_VERIFY',
 'EXPORT_CREATE','EXPORT_COPY','EXPORT_REPORT','OUTPUT_WRITE','DIAGNOSTIC_WRITE'})
DIAGNOSTIC_GENERIC_CODES=frozenset({'NONE','PERMISSION_DENIED','FILE_MISSING','OUTPUT_EXISTS','IO_ERROR',
 'TEXT_ENCODING_INVALID','JSON_INVALID','CSV_INVALID','SCHEMA_INVALID','VALIDATION_FAILED'})
DIAGNOSTIC_DOMAIN='tasks/desert-rv/unity/JourneyEvidence/MobileHudWorld'

def diagnostic_identity():
 try:return isolated.owner_identity(os.environ)
 except (ValueError,TypeError):return None

def world_inventory_diagnostic():
 # Only known names may leave this process; unknown entries contribute a count.
 value=dict(pathDomain=DIAGNOSTIC_DOMAIN,state='UNREADABLE',missingNames=[],unexpectedCount=None)
 try:
  isolated.safe_path(WORLD_SOURCE)
  if not WORLD_SOURCE.exists():
   return dict(value,state='MISSING',missingNames=sorted(WORLD_FILES),unexpectedCount=0)
  if not WORLD_SOURCE.is_dir():return dict(value,state='NOT_DIRECTORY')
  known=set();unknown=0
  for index,path in enumerate(WORLD_SOURCE.iterdir()):
   if index>=4096:return dict(value,state='LIMIT_EXCEEDED')
   if path.name in WORLD_FILES:known.add(path.name)
   else:unknown+=1
  return dict(value,state='READABLE',missingNames=sorted(WORLD_FILES-known),unexpectedCount=unknown)
 except ValueError:return dict(value,state='UNSAFE')
 except OSError:return value

def validate_world_diagnostic(value):
 keys={'schema','label','status','identity','phase','code','inventory'}
 require(type(value) is dict and set(value)==keys and type(value['schema']) is int and value['schema']==1 and
         value['label']=='MOBILE_HUD_WORLD_HOST_DIAGNOSTIC' and value['identity']==diagnostic_identity() and
         value['phase'] in DIAGNOSTIC_PHASES and value['code'] in SAFE_ERROR_CODES|DIAGNOSTIC_GENERIC_CODES,
         'MOBILE_HUD_DIAGNOSTIC_SCHEMA')
 require((value['status']=='PASSED' and value['phase']=='COMPLETE' and value['code']=='NONE') or
         (value['status']=='FAILED' and value['phase']!='COMPLETE' and value['code']!='NONE'),'MOBILE_HUD_DIAGNOSTIC_SCHEMA')
 row=value['inventory']
 require(type(row) is dict and set(row)=={'pathDomain','state','missingNames','unexpectedCount'} and
         row['pathDomain']==DIAGNOSTIC_DOMAIN and row['state'] in {'MISSING','READABLE','UNREADABLE','UNSAFE','NOT_DIRECTORY','LIMIT_EXCEEDED'} and
         type(row['missingNames']) is list and all(type(name) is str and name in WORLD_FILES for name in row['missingNames']) and
         row['missingNames']==sorted(set(row['missingNames'])),'MOBILE_HUD_DIAGNOSTIC_SCHEMA')
 if row['state'] in {'MISSING','READABLE'}:
  require(type(row['unexpectedCount']) is int and 0<=row['unexpectedCount']<=4096,'MOBILE_HUD_DIAGNOSTIC_SCHEMA')
  if row['state']=='MISSING':require(row['missingNames']==sorted(WORLD_FILES) and row['unexpectedCount']==0,'MOBILE_HUD_DIAGNOSTIC_SCHEMA')
 else:require(row['missingNames']==[] and row['unexpectedCount'] is None,'MOBILE_HUD_DIAGNOSTIC_SCHEMA')
 if value['status']=='PASSED':require(row['state']=='READABLE' and row['missingNames']==[] and row['unexpectedCount']==0,'MOBILE_HUD_DIAGNOSTIC_SCHEMA')
 return value

def write_world_diagnostic(phase,code):
 value=dict(schema=1,label='MOBILE_HUD_WORLD_HOST_DIAGNOSTIC',status='PASSED' if code=='NONE' else 'FAILED',
            identity=diagnostic_identity(),phase=phase,code=code,inventory=world_inventory_diagnostic())
 validate_world_diagnostic(value)
 isolated.safe_path(WORLD_DIAGNOSTIC)
 require(not WORLD_DIAGNOSTIC.exists(),'MOBILE_HUD_DIAGNOSTIC_EXISTS')
 WORLD_DIAGNOSTIC.parent.mkdir(exist_ok=True)
 require(not any(WORLD_DIAGNOSTIC.parent.iterdir()),'MOBILE_HUD_DIAGNOSTIC_DIRECTORY')
 isolated.write_new(WORLD_DIAGNOSTIC,value,8192)
 copied=source.json_bytes(raw(WORLD_DIAGNOSTIC,8192))
 require(validate_world_diagnostic(copied)==value,'MOBILE_HUD_DIAGNOSTIC_CHANGED')
 # This flag is emitted only after exclusive creation and read-back validation.
 isolated.output(os.environ,'world_diagnostic_written=true\n')
 return value

def world_inventory(folder):
 isolated.safe_path(folder)
 require(folder.exists(),'MOBILE_HUD_WORLD_SOURCE_MISSING')
 require(folder.is_dir() and {p.name for p in folder.iterdir()}==WORLD_FILES,'MOBILE_HUD_WORLD_INVENTORY')
 require(raw(folder/'EVIDENCE.txt',1024).decode('utf-8')==WORLD_EVIDENCE,'MOBILE_HUD_WORLD_SCOPE')
 for stem in WORLD_STEMS:
  profile,mode,background=stem.split('-',2);validate_image_fit(folder,stem,profile,mode,background)
 return [pin(folder/name) for name in sorted(WORLD_FILES)]

def load_restoration():
 # The explicit restored path reuses the complete current native/source gate.
 path=str(TASK/'art/journey-preparation')
 if path not in sys.path:sys.path.insert(0,path)
 import restore_preparation
 return restore_preparation

def world_report(folder):
 preparation=TASK/'journey-preparation-export/preparation.json'
 with gate_phase('PREPARATION_READ'):value=source.json_bytes(raw(preparation,1024**2))
 with gate_phase('PREPARATION_IDENTITY'):
  identity=isolated.owner_identity(os.environ)
  mode=os.environ.get('WORLD_CAPTURE_MODE','same-workspace')
  require(mode in ('same-workspace','restored'),'MOBILE_HUD_WORLD_MODE')
  require(type(value) is dict and value.get('status')=='PREPARED_EDITOR_SCOPE_UNREVIEWED' and
          value.get('visualApproved') is False and value.get('gameplayAccepted') is False and
          value.get('nativeCase')=='DesertRV.Tests.JourneyPreparationTests.PrepareVerifiedSameWorkspaceJourney','MOBILE_HUD_WORLD_PREPARATION')
  if mode=='same-workspace':require(value.get('sourceCommit')==identity['sourceCommit'],'MOBILE_HUD_WORLD_PREPARATION')
 lineage={}
 if mode=='restored':
  with gate_phase('RESTORATION_VERIFY'):
   restore=load_restoration();restore.verify()
   restored=source.json_bytes(raw(restore.REPORT,1024**2))
   require(restored.get('label')=='RESTORED_JOURNEY_NATIVE_REVALIDATED_UNREVIEWED' and
           restored.get('sourceCommit')==identity['sourceCommit'] and
           restored.get('producerRunUrl')=='https://github.com/yangerstar1/task-workbench/actions/runs/'+identity['runId'] and
           restored.get('assetProducerSourceCommit')==value.get('sourceCommit') and
           restored.get('assetProducerRunUrl')==restore.RUN_URL and
           restored.get('generatedReceiptSha256')==value.get('generatedExport',{}).get('sha256')==restore.PRODUCER['generatedReceiptSha256'] and
           restored.get('sourceBytesUnchanged') is True and restored.get('originalAssetsUnchanged') is True and
           restored.get('structureValidated') is True and restored.get('approved') is False and restored.get('scopeReused') is False,
           'MOBILE_HUD_WORLD_RESTORATION')
   lineage=dict(assetProducerSourceCommit=restored['assetProducerSourceCommit'],assetProducerRunUrl=restored['assetProducerRunUrl'],
                restoration=pin(restore.REPORT))
 with gate_phase('CAPTURE_VALIDATION'):files=world_inventory(folder)
 with gate_phase('PREPARATION_PIN'):preparation_pin=pin(preparation)
 return dict(schema=1,**identity,scope='AUTHORED_WORLD_CAMERA_WITH_PRODUCTION_HUD_FIXTURE_NOT_GAMEPLAY',
             preparation=preparation_pin,**lineage,files=files,deviceExecuted=False,gameplayAccepted=False,approved=False)

def verify_world():
 with gate_phase('EXPORT_VERIFY'):
  isolated.safe_path(WORLD_EXPORT)
  require(WORLD_EXPORT.is_dir() and {p.name for p in WORLD_EXPORT.iterdir()}=={'captures','world-report.json'},'MOBILE_HUD_WORLD_EXPORT')
  report=source.json_bytes(raw(WORLD_EXPORT/'world-report.json',16384))
  require(report==world_report(WORLD_EXPORT/'captures'),'MOBILE_HUD_WORLD_REPORT_CHANGED')
  return [pin(WORLD_EXPORT/'world-report.json'),*report['files']]

def world():
 with gate_phase('NATIVE_OUTCOME'):require(os.environ.get('NATIVE_OUTCOME')=='success','MOBILE_HUD_WORLD_NATIVE_OUTCOME')
 original=world_report(WORLD_SOURCE)
 with gate_phase('EXPORT_CREATE'):
  isolated.safe_path(WORLD_EXPORT);require(not WORLD_EXPORT.exists(),'MOBILE_HUD_WORLD_EXPORT_EXISTS')
  WORLD_EXPORT.mkdir();destination=WORLD_EXPORT/'captures';destination.mkdir()
 with gate_phase('EXPORT_COPY'):
  expected={Path(row['path']).name:row for row in original['files']}
  for name in sorted(WORLD_FILES):
   data=raw(WORLD_SOURCE/name)
   require(sha(data)==expected[name]['sha256'] and len(data)==expected[name]['bytes'],'MOBILE_HUD_WORLD_COPY_CHANGED')
   # Exclusive creation and safe reads prevent overwrite or symlink-following copy fallbacks.
   with (destination/name).open('xb') as stream:stream.write(data)
 with gate_phase('EXPORT_REPORT'):
  copied=world_report(destination)
  for old,new in zip(original['files'],copied['files']):
   require(Path(old['path']).name==Path(new['path']).name and old['sha256']==new['sha256'] and old['bytes']==new['bytes'],'MOBILE_HUD_WORLD_COPY_CHANGED')
  require({k:v for k,v in original.items() if k!='files'}=={k:v for k,v in copied.items() if k!='files'},'MOBILE_HUD_WORLD_COPY_CHANGED')
  isolated.write_new(WORLD_EXPORT/'world-report.json',copied,16384)
 verify_world()
 with gate_phase('OUTPUT_WRITE'):isolated.output(os.environ,'world_verified=true\nexport_ready=true\n')

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
 is_world=sys.argv[1:]==['world']
 try:
  with gate_phase('ARGUMENTS'):require(sys.argv[1:] in (['native'],['world']),'MOBILE_HUD_ARGUMENTS')
  with gate_phase('NATIVE_GATE' if sys.argv[1]=='native' else 'WORLD_GATE'):
   {'native':native,'world':world}[sys.argv[1]]()
  if is_world:
   with gate_phase('DIAGNOSTIC_WRITE'):write_world_diagnostic('COMPLETE','NONE')
 except GateFailure as error:
  # Preserve the first gate failure even if durable diagnostics are independently blocked.
  print('MOBILE_HUD_GATE_FAILED phase='+error.phase+' code='+error.code)
  if is_world:
   try:write_world_diagnostic(error.phase,error.code)
   except Exception as diagnostic_error:
    print('MOBILE_HUD_DIAGNOSTIC_NOT_PUBLISHED code='+safe_error_code(diagnostic_error))
  return 2
 print('MOBILE_HUD_'+sys.argv[1].upper()+'_VERIFIED');return 0
if __name__=='__main__':raise SystemExit(main())
