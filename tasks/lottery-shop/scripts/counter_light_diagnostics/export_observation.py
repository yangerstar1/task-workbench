#!/usr/bin/env python3
"""Independent safe collection, not a diagnostic/native/source acceptance gate.
Raw diagnostic JSON is copied only after exhaustive structural/string screening.
Only fixed PNG names with pixel-only PNG chunks can be copied; no settings/logs.
"""
import hashlib, io, json, math, os, re, struct, sys, zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import post_capture_safety as safe
import verify_and_measure as inc
TASK='tasks/lottery-shop'
SCOPE='COUNTER_LIGHT_PARTIAL_OBSERVATION_NOT_VALIDATED_NOT_ART_APPROVAL_NOT_G3_PASS'
MAX_JSON=2*1024*1024
NAMES={inc.filename(x) for x in inc.CASES+['baseline-before','baseline-after']}
S=lambda ok:safe.require(ok,'OBSERVATION_SCHEMA_REJECTED')
def obj(x,keys):S(type(x)is dict and set(x)==set(keys))
def num(x):S(type(x) in (float,int) and math.isfinite(x) and abs(x)<=1e9)
def integer(x):S(type(x)is int and -2147483648<=x<=2147483647)
def boolean(x):S(type(x)is bool)
def enum(x,choices):S(type(x)is str and x in choices)
def vector(x,keys):obj(x,keys);[num(v) for v in x.values()]
def array(x,count,fn):S(type(x)is list and len(x)==count);[fn(v) for v in x]
def digest(x,unverified=False):S(x is None or x=='' or unverified and x=='UNVERIFIED' or type(x)is str and re.fullmatch('[0-9a-f]{64}',x))
def reference(x):S(type(x)is str and (x in {'null','ABSENT'} or re.fullmatch('-?[0-9]{1,10}',x)))
SHADERS={'Universal Render Pipeline/Lit','Universal Render Pipeline/Unlit'}
GI={'None','RealtimeEmissive','BakedEmissive','EmissiveIsBlack','AnyEmissive','RealtimeEmissive, EmissiveIsBlack','BakedEmissive, EmissiveIsBlack','AnyEmissive, EmissiveIsBlack'}
KEYWORDS={'_NORMALMAP','_METALLICSPECGLOSSMAP','_SPECULARHIGHLIGHTS_OFF','_ENVIRONMENTREFLECTIONS_OFF','_EMISSION','_RECEIVE_SHADOWS_OFF','_ALPHATEST_ON','_SURFACE_TYPE_TRANSPARENT','_ALPHAPREMULTIPLY_ON'}
def controls(c):
 obj(c,inc.CONTROL_KEYS)
 array(c['lightNames'],5,lambda x:enum(x,set(inc.NAMES)))
 for k in ['lightColors','lightPositions','lightRotations']:array(c[k],5,lambda x:vector(x,{'lightColors':'rgba','lightPositions':'xyz','lightRotations':'xyzw'}[k]))
 for k in ['lightIntensities','lightRanges','lightSpotAngles','lightInnerSpotAngles']:array(c[k],5,num)
 array(c['lightShadows'],5,lambda x:enum(x,{'None','Hard','Soft'}));array(c['lightEnabled'],5,boolean);array(c['lightCullingMasks'],5,integer);array(c['ambientSH'],27,num)
 enum(c['ambientMode'],{'Skybox','Trilight','Flat','Custom'});num(c['ambientIntensity']);S(0<=c['ambientIntensity']<=8)
 for k in ['ambientSkyColor','ambientEquatorColor','ambientGroundColor','ambientLight']:
  vector(c[k],'rgba');S(all(0<=c[k][n]<=8 for n in 'rgb') and 0<=c[k]['a']<=1)
 for k in ['probeIntensity','reflectionIntensity','oakSmoothness','oakNormalStrength','oakSpecularHighlights','oakMetallic','oakCull','oakSurface','oakZWrite','oakSrcBlend','oakDstBlend']:num(c[k])
 for k in ['oakMaterialId','oakRenderQueue']:integer(c[k])
 for k in ['oakEnableInstancing','oakDoubleSidedGI']:boolean(c[k])
 for k in ['oakBaseColor','oakEmissionColor']:vector(c[k],'rgba')
 for k in ['oakBaseScale','oakBaseOffset']:vector(c[k],'xy')
 for k in ['probeTextureId','oakBaseMapId','oakBumpMapId','oakPackedMapId','oakEmissionMapId']:reference(c[k])
 enum(c['probeTextureName'],{'Day','Night'});enum(c['oakBaseMapName'],{'Walnut_v15_BaseColor','null'});enum(c['oakShader'],SHADERS);enum(c['oakGIFlags'],GI)
 S(type(c['oakKeywords'])is list and len(c['oakKeywords'])<=len(KEYWORDS));[enum(x,KEYWORDS) for x in c['oakKeywords']]
CAMERA_KEYS='instanceId targetId expectedTargetId urpInstanceId volumeTriggerId width height antiAliasing cullingMask urpStackIds urpSerializedSha256 position rotation projection worldToCamera viewport background fov aspect near far orthographic enabled allowHDR allowMSAA sRGB targetCreated format clearFlags'.split()
def camera(c):
 obj(c,CAMERA_KEYS)
 for k in 'instanceId targetId expectedTargetId urpInstanceId volumeTriggerId width height antiAliasing cullingMask'.split():integer(c[k])
 S(type(c['urpStackIds'])is list and len(c['urpStackIds'])<=16);[integer(x) for x in c['urpStackIds']];digest(c['urpSerializedSha256'])
 for k,n in [('position','xyz'),('rotation','xyzw'),('background','rgba')]:vector(c[k],n)
 for k in ['projection','worldToCamera']:array(c[k],16,num)
 array(c['viewport'],4,num)
 for k in ['fov','aspect','near','far']:num(c[k])
 for k in ['orthographic','enabled','allowHDR','allowMSAA','sRGB','targetCreated']:boolean(c[k])
 enum(c['format'],{'ARGB32'});enum(c['clearFlags'],{'Color','SolidColor','Skybox','Depth','Nothing'})
RECEIPT_KEYS='schemaVersion scope status sourceCommit runId runAttempt baselineSourceFreeze stateOrigin expectedNormalPngSha256 baselineBeforeSha256 baselineAfterSha256 stateBeforeSha256 stateAfterSha256 diskBeforeSha256 diskAfterSha256 sceneBeforeSha256 sceneAfterSha256 materialBeforeSha256 materialAfterSha256 failureCode faultRequest colorSpace graphicsDeviceType unityVersion oakShader oakBaseMap oakMaterialCoverage frameCount oakRendererInstanceId oakMaterialInstanceId ownedMaterialCountAfter ownedTargetCountAfter initialControlsJson initialControlsSha256 pixelRestoreProof diagnosticOptIn propertiesRestored elapsedMs complete restored oakBaseColor camera initialControls cases'.split()
CASE_KEYS='id file sha256 restoredPngSha256 controlsBeforeSha256 controlsAfterSha256 controlsBeforeJson controlsAfterJson bytes captured restored controlsStable propertiesRestored controls'.split()
def payload(text,h,observed,bind_observed=True):
 S(text is None or type(text)is str and len(text.encode())<=32768)
 if not text:S(observed is None);return
 parsed=inc.strict_json(text);controls(parsed);S(hashlib.sha256(text.encode()).hexdigest()==h)
 if bind_observed:S(parsed==observed)
def receipt(raw,ident):
 d=inc.strict_json(raw.decode('utf-8'));obj(d,RECEIPT_KEYS)
 S(type(d['schemaVersion'])is int and d['schemaVersion']==3)
 enum(d['scope'],{'DIAGNOSTIC_COUNTER_LIGHT_NOT_ART_APPROVAL_NOT_G3_PASS'});enum(d['status'],{'RUNNING','COMPLETE_DIAGNOSTIC_RESTORED','FAILED_DIAGNOSTIC_RESTORED','FAILED_RESTORE_NOT_PROVEN','FAILED_BUDGET_AT_RECEIPT_WRITE'})
 S(all(d[k]==v for k,v in ident.items()));S(d['baselineSourceFreeze']==inc.PLAN['frozenCommit'])
 enum(d['stateOrigin'],{'SAME_RUNTIME_PHONE_PENDING_NO_INPUT_NO_SERVICE_ACTION'});enum(d['faultRequest'],{''})
 S(d['failureCode'] is None or d['failureCode'] in {'','PRECONDITION','BASELINE_BEFORE','FINAL_RESTORE_OR_PROOF_FAILED','DIAGNOSTIC_TIME_BUDGET'}|set(inc.CASES))
 enum(d['colorSpace'],{'Gamma','Linear'});enum(d['graphicsDeviceType'],{'OpenGLCore','Null'});enum(d['unityVersion'],{'6000.3.19f1'});enum(d['oakShader'],SHADERS);enum(d['oakBaseMap'],{'Walnut_v15_BaseColor'})
 enum(d['oakMaterialCoverage'],{'ALL_MERGED_WARM_OAK_GEOMETRY_NOT_FASCIA_ONLY'});S(d['pixelRestoreProof'] is None or d['pixelRestoreProof'] in {'','VERIFIED_EXACT_PNG','UNVERIFIED'})
 for k in RECEIPT_KEYS:
  if k.endswith('Sha256'):digest(d[k],unverified=k in {'stateAfterSha256','diskAfterSha256','sceneAfterSha256','materialAfterSha256'})
 for k in ['frameCount','oakRendererInstanceId','oakMaterialInstanceId','ownedMaterialCountAfter','ownedTargetCountAfter','elapsedMs']:integer(d[k])
 for k in ['diagnosticOptIn','propertiesRestored','complete','restored']:boolean(d[k])
 vector(d['oakBaseColor'],'rgba');camera(d['camera']);controls(d['initialControls']);payload(d['initialControlsJson'],d['initialControlsSha256'],d['initialControls'])
 S(type(d['cases'])is list and len(d['cases'])<=len(inc.CASES));seen=[]
 for row in d['cases']:
  obj(row,CASE_KEYS);enum(row['id'],set(inc.CASES));S(row['id'] not in seen);seen.append(row['id'])
  S(row['file'] is None or row['file'] in {'',inc.filename(row['id'])})
  for k in ['sha256','restoredPngSha256','controlsBeforeSha256','controlsAfterSha256']:digest(row[k])
  integer(row['bytes'])
  for k in ['captured','restored','controlsStable','propertiesRestored']:boolean(row[k])
  if row['controls'] is not None:controls(row['controls'])
  for part in ['Before','After']:
   if row['controls'+part+'Json']:payload(row['controls'+part+'Json'],row['controls'+part+'Sha256'],row['controls'],bind_observed=part=='Before')
   else:S(row['controls'+part+'Json'] in ('',None))
 return d

def png(raw):
 # No tEXt/iTXt/zTXt/eXIf, ICC profiles, unknown ancillary chunks, trailing data.
 safe.require(10000<len(raw)<=8*1024*1024 and raw[:8]==b'\x89PNG\r\n\x1a\n','OBSERVATION_PNG_REJECTED')
 offset=8;parts=[];payloads=[]
 while offset<len(raw):
  safe.require(offset+12<=len(raw),'OBSERVATION_PNG_REJECTED');n=struct.unpack('>I',raw[offset:offset+4])[0];kind=raw[offset+4:offset+8];data=raw[offset+8:offset+8+n]
  safe.require(kind in {b'IHDR',b'IDAT',b'IEND'} and n<=8*1024*1024 and offset+12+n<=len(raw),'OBSERVATION_PNG_REJECTED')
  safe.require(zlib.crc32(kind+data)&0xffffffff==struct.unpack('>I',raw[offset+8+n:offset+12+n])[0],'OBSERVATION_PNG_REJECTED')
  parts.append(kind)
  if kind==b'IHDR':
   safe.require(data==struct.pack('>IIBBBBB',1280,720,8,2,0,0,0) or data==struct.pack('>IIBBBBB',1280,720,8,6,0,0,0),'OBSERVATION_PNG_REJECTED')
   expected_pixels=720*(1280*(3 if data[9]==2 else 4)+1)
  if kind==b'IDAT':payloads.append(data)
  if kind==b'IEND':safe.require(n==0 and offset+12==len(raw),'OBSERVATION_PNG_REJECTED')
  offset+=n+12
 safe.require(parts[0]==b'IHDR' and parts[-1]==b'IEND' and len(parts)>=3 and all(x==b'IDAT' for x in parts[1:-1]),'OBSERVATION_PNG_REJECTED')
 # Exactly one filter byte plus the validated RGB/RGBA scanline width per row.
 # Pillow may ignore extra inflated bytes; neither those nor a second stream may leave.
 decoder=zlib.decompressobj();pixels=decoder.decompress(b''.join(payloads),expected_pixels+1)
 safe.require(len(pixels)==expected_pixels and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,'OBSERVATION_PNG_REJECTED')
 from PIL import Image
 with Image.open(io.BytesIO(raw)) as im:
  safe.require(im.format=='PNG' and im.size==(1280,720) and im.mode in {'RGB','RGBA'},'OBSERVATION_PNG_REJECTED');im.load()
 return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def collect(root,ident,start):
 src=root/TASK/'artifacts/counter-light-diagnostic'/('run-'+ident['runId']+'-attempt-'+ident['runAttempt'])
 dst=root/TASK/'artifacts/counter-light-observation';safe.require(dst.parent.resolve()==dst.parent,'SAFE_PATH_REJECTED');safe.require(not dst.exists() and not dst.is_symlink(),'OBSERVATION_CONTEXT_REJECTED');dst.mkdir(mode=0o700)
 rows=[];failures=[]
 for name in ['diagnostic-receipt.json']+sorted(NAMES):
  try:
   p=src/name;raw=safe.regular(p,MAX_JSON if name.endswith('.json') else 8*1024*1024);safe.require(p.stat().st_mtime_ns>=start,'OBSERVATION_BINDING_REJECTED')
   if name.endswith('.json'):receipt(raw,ident)
   else:png(raw)
   safe.write_new(dst/name,raw);rows.append({'file':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
  except BaseException as error:
   failures.append({'item':'RECEIPT' if name.endswith('.json') else 'PNG_'+str(sorted(NAMES).index(name)+1),'code':safe.error_code(error)})
 report={'schemaVersion':1,'scope':SCOPE,**ident,'status':'COLLECTED_UNVALIDATED' if not failures else 'PARTIAL_OR_REJECTED_UNVALIDATED','semanticValidation':'NOT_EVALUATED','nativeAcceptance':'NOT_GRANTED','artApproval':False,'g3Pass':False,'sourceWaiver':False,'files':rows,'collectionFailures':failures}
 safe.write_new(dst/'observation-manifest.json',(json.dumps(report,sort_keys=True,indent=2)+'\n').encode())
 return report

def main():
 safe.require(len(sys.argv)==1,'CLI_ARGUMENTS');safe.begin('counter-observation','export');safe.checkpoint('CONTEXT');root=Path(os.environ['GITHUB_WORKSPACE']).absolute();ident=safe.identity();e=root/TASK/'evidence/visual-candidate'
 load=lambda name:inc.strict_json(safe.regular(e/name,32768).decode())
 import compose_evidence as composed
 bound=composed.context(root);composed.code_contract(root,bound['reviewedCandidateCommit'])
 safe.require(all(bound[k]==v for k,v in ident.items()),'OBSERVATION_CONTEXT_REJECTED')
 guard=load('source-receipt.json');capture=load('safe-capture.json');finish=load('safe-finish.json');session=load('safe-session.json')
 safe.require(all(all(r.get(k)==v for k,v in ident.items()) for r in [guard,capture,finish,session]),'OBSERVATION_CONTEXT_REJECTED')
 safe.require(guard.get('scope')=='DIAGNOSTIC_VISUAL_CANDIDATE_NOT_G3_PASS' and capture.get('phase')=='capture' and capture.get('counterLightDiagnostic') is True and capture.get('counterLightDiagnosticFault')=='','OBSERVATION_CONTEXT_REJECTED')
 safe.require(finish.get('phase')=='finish' and finish.get('cleanup')=={'status':'ABSENCE_VERIFIED','removalExitCode':0} and session.get('status')=='CLOSED' and session.get('cleanup')==finish['cleanup'],'OBSERVATION_CONTEXT_REJECTED')
 start=capture.get('nativeStartedAtNs');safe.require(type(start)is int and start>0,'OBSERVATION_CONTEXT_REJECTED');safe.checkpoint('COPY_INPUTS');report=collect(root,ident,start)
 # Collection completion cannot create the existing gate file or a suite PASS.
 safe.checkpoint('DONE');safe.persist('COMPLETED','NONE')
 output=Path(os.environ['GITHUB_OUTPUT']);safe.require(output.resolve()==output.absolute(),'SAFE_PATH_REJECTED')
 with output.open('a') as f:f.write('safe_observation=true\n')
 print(json.dumps({'status':report['status'],'scope':SCOPE,'copiedFileCount':len(report['files']),'rejectedFileCount':len(report['collectionFailures'])}))
if __name__=='__main__':
 try:main()
 except BaseException as error:raise SystemExit(safe.fail(error)) from None
