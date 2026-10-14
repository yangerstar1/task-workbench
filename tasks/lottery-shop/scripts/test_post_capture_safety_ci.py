"""SOURCE-ONLY synthetic adversarial safety/export tests; never native evidence."""
import copy, hashlib, io, json, os, pathlib, struct, subprocess, sys, tempfile, unittest, zlib
from unittest import mock
S=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(S/'counter_light_diagnostics'))
import export_observation as e
import post_capture_safety as safe
import stage_a_inventory_ci as inventory
import verify_and_measure as v
def seal(d):
 def enc(x):return json.dumps(x,separators=(',',':'))
 d['initialControlsJson']=enc(d['initialControls']);d['initialControlsSha256']=hashlib.sha256(d['initialControlsJson'].encode()).hexdigest()
 for row in d['cases']:
  row['controlsBeforeJson']=row['controlsAfterJson']=enc(row['controls']);row['controlsBeforeSha256']=row['controlsAfterSha256']=hashlib.sha256(row['controlsBeforeJson'].encode()).hexdigest()
 return d

def fixture():
 # Do not reuse the candidate's fixture or material_expected implementation.
 ctrl={'lightNames':list(v.NAMES),'lightIntensities':[.6,1.15,1.6,.55,.06],'lightColors':[dict(r=1,g=1,b=1,a=1) for _ in range(5)],
 'lightPositions':[dict(x=0,y=0,z=0) for _ in range(5)],'lightRotations':[dict(x=0,y=0,z=0,w=1) for _ in range(5)],
 'lightRanges':[10,4.8,4.2,4,2],'lightSpotAngles':[115]*5,'lightInnerSpotAngles':[70]*5,'lightShadows':['Soft','None','Soft','None','None'],
 'lightEnabled':[True]*5,'lightCullingMasks':[-1]*5,'probeIntensity':.85,'reflectionIntensity':1,'probeTextureId':'31','probeTextureName':'Day','ambientSH':[.2]*27,
 'oakShader':'Universal Render Pipeline/Lit','oakMaterialId':10,'oakKeywords':['_METALLICSPECGLOSSMAP','_NORMALMAP'],
 'oakSmoothness':1,'oakNormalStrength':.28,'oakSpecularHighlights':1,'oakBaseMapId':'21','oakBaseMapName':'Walnut_v15_BaseColor',
 'oakBaseColor':dict(r=1,g=1,b=1,a=1),'oakBaseScale':dict(x=1,y=1),'oakBaseOffset':dict(x=0,y=0),
 'oakBumpMapId':'22','oakPackedMapId':'23','oakEmissionMapId':'null','oakMetallic':0,'oakEmissionColor':dict(r=0,g=0,b=0,a=1),
 'oakCull':2,'oakSurface':0,'oakZWrite':1,'oakSrcBlend':1,'oakDstBlend':0,'oakRenderQueue':2000,
 'oakEnableInstancing':False,'oakDoubleSidedGI':False,'oakGIFlags':'None'}
 mat=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
 cam={'instanceId':1,'targetId':2,'expectedTargetId':2,'urpInstanceId':3,'volumeTriggerId':0,'width':1280,'height':720,'antiAliasing':1,'cullingMask':-1,
 'format':'ARGB32','orthographic':False,'targetCreated':True,'enabled':True,'urpStackIds':[],'urpSerializedSha256':'e'*64,
 'position':dict(x=1.57,y=1.2,z=-1.2),'rotation':dict(x=0,y=0,z=0,w=1),'background':dict(r=0,g=0,b=0,a=1),
 'projection':mat,'worldToCamera':mat,'viewport':[0,0,1,1],'allowHDR':False,'allowMSAA':True,'sRGB':False,'clearFlags':'SolidColor','fov':28,'aspect':1280/720,'near':.02,'far':30}
 d={'schemaVersion':2,'scope':'DIAGNOSTIC_COUNTER_LIGHT_NOT_ART_APPROVAL_NOT_G3_PASS','status':'COMPLETE_DIAGNOSTIC_RESTORED',
 'complete':True,'restored':True,'propertiesRestored':True,'pixelRestoreProof':'VERIFIED_EXACT_PNG','diagnosticOptIn':True,'faultRequest':'','failureCode':'',
 'elapsedMs':1000,'frameCount':42,'graphicsDeviceType':'OpenGLCore','sourceCommit':'b'*40,'baselineSourceFreeze':v.PLAN['frozenCommit'],
 'ownedMaterialCountAfter':0,'ownedTargetCountAfter':0,'colorSpace':'Gamma','unityVersion':'6000.3.19f1','camera':cam,'initialControls':ctrl,
 'oakMaterialCoverage':'ALL_MERGED_WARM_OAK_GEOMETRY_NOT_FASCIA_ONLY','cases':[]}
 for key in ('expectedNormalPngSha256','baselineBeforeSha256','baselineAfterSha256'):d[key]='a'*64
 for key in ('state','disk','scene','material'):d[key+'BeforeSha256']=d[key+'AfterSha256']='c'*64
 zeros={'pendant-zero':[1],'boardwash-zero':[4],'counter-pair-zero':[1,4],'daylight-zero':[0],'reading-zero':[2],'shelf-zero':[3],'all-direct-zero':range(5),'counter-and-reflection-controls-zero':[1,4]}
 for i,label in enumerate(v.CASES):
  cc=copy.deepcopy(ctrl)
  for n in zeros.get(label,[]):cc['lightIntensities'][n]=0
  if label in ('probe-intensity-zero','reflection-controls-zero','counter-and-reflection-controls-zero'):cc['probeIntensity']=0
  if label in ('global-reflection-zero','reflection-controls-zero','counter-and-reflection-controls-zero'):cc['reflectionIntensity']=0
  if label=='ambient-sh-zero':cc['ambientSH']=[0]*27
  if label.startswith('oak-'):cc['oakMaterialId']=100+i
  if label=='oak-specular-highlights-off':cc['oakSpecularHighlights']=0;cc['oakKeywords']=sorted(cc['oakKeywords']+['_SPECULARHIGHLIGHTS_OFF'])
  if label=='oak-normal-flat':cc['oakNormalStrength']=0
  if label=='oak-roughness-one':cc['oakSmoothness']=0
  if label in ('oak-texture-only','oak-target-mask'):
   cc.update(oakShader='Universal Render Pipeline/Unlit',oakKeywords=[],oakSmoothness=-1,oakNormalStrength=-1,oakSpecularHighlights=-1,
    oakBumpMapId='ABSENT',oakPackedMapId='ABSENT',oakEmissionMapId='ABSENT',oakMetallic=-1,oakEmissionColor=dict(r=0,g=0,b=0,a=0),oakGIFlags='None')
  if label=='oak-target-mask':cc.update(oakBaseMapId='null',oakBaseMapName='null',oakBaseColor=dict(r=1,g=0,b=1,a=1))
  d['cases'].append({'id':label,'controls':cc,'captured':True,'restored':True,'propertiesRestored':True,'restoredPngSha256':'a'*64,'file':v.filename(label),'controlsStable':True})
 return seal(d)

def full_receipt():
 d=fixture();d.update(runId='123',runAttempt='1',stateOrigin='SAME_RUNTIME_PHONE_PENDING_NO_INPUT_NO_SERVICE_ACTION',oakRendererInstanceId=6,oakMaterialInstanceId=10,oakShader='Universal Render Pipeline/Lit',oakBaseMap='Walnut_v15_BaseColor',oakBaseColor=dict(r=1,g=1,b=1,a=1))
 for row in d['cases']:row.update(sha256='a'*64,bytes=10001)
 return d
IDENT={'sourceCommit':'b'*40,'runId':'123','runAttempt':'1'}
def encode(d):return json.dumps(d).encode()
def png_bytes():
 pixels=bytes((i*19+i//41)%256 for i in range(1280*3*720));rows=b''.join(b'\0'+pixels[i*3840:(i+1)*3840] for i in range(720))
 def chunk(k,v):return struct.pack('>I',len(v))+k+v+struct.pack('>I',zlib.crc32(k+v)&0xffffffff)
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1280,720,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows,1))+chunk(b'IEND',b'')
class SafetyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name);safe.ACTIVE.clear()
  self.env=mock.patch.dict(os.environ,{'GITHUB_WORKSPACE':str(self.root),'GITHUB_SHA':'b'*40,'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1'});self.env.start();self.addCleanup(self.env.stop);self.addCleanup(safe.ACTIVE.clear)
 def test_complete_raw_receipt_is_safe_but_not_semantic_pass(self):
  d=full_receipt();self.assertEqual(e.receipt(encode(d),IDENT),d)
  d['cases'][10]['controls']['ambientSH']=[.5]*27;seal(d);e.receipt(encode(d),IDENT)
  with self.assertRaisesRegex(ValueError,'Experiment contains non-allowlisted'):v.validate_receipt(d,'a'*64,'b'*40)
 def test_extra_secret_field_rejected(self):
  d=full_receipt();d['secret']='PRIVATE_SENTINEL';self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
 def test_unknown_nested_string_rejected(self):
  for place,key in [('initialControls','oakBaseMapName'),('camera','clearFlags')]:
   d=full_receipt();d[place][key]='PRIVATE_SENTINEL';self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
 def test_payload_secret_duplicate_and_nonfinite_rejected(self):
  d=full_receipt();d['initialControlsJson']='{"secret":"PRIVATE_SENTINEL"}';self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
  raw=encode(full_receipt());self.assertRaises(ValueError,e.receipt,raw.replace(b'{',b'{"schemaVersion":2,',1),IDENT)
  d=full_receipt();d['camera']['fov']=float('nan');self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
 def test_incomplete_raw_receipt_is_safe(self):
  d=full_receipt();d.update(status='FAILED_DIAGNOSTIC_RESTORED',complete=False,failureCode='ambient-sh-zero');d['cases']=d['cases'][:11];e.receipt(encode(d),IDENT)
 def test_native_unverified_after_proofs_preserved_only_at_exact_fields(self):
  d=full_receipt();d.update(status='FAILED_RESTORE_NOT_PROVEN',complete=False,restored=False,propertiesRestored=False,pixelRestoreProof='UNVERIFIED',failureCode='FINAL_RESTORE_OR_PROOF_FAILED')
  for key in ['stateAfterSha256','diskAfterSha256','sceneAfterSha256','materialAfterSha256']:d[key]='UNVERIFIED'
  self.assertEqual(e.receipt(encode(d),IDENT),d)
  with self.assertRaises(ValueError):v.validate_receipt(d,'a'*64,'b'*40)
  for key in ['stateBeforeSha256','expectedNormalPngSha256','baselineAfterSha256','initialControlsSha256']:
   bad=copy.deepcopy(d);bad[key]='UNVERIFIED';self.assertRaises(ValueError,e.receipt,encode(bad),IDENT)
  d['stateAfterSha256']='UNVERIFIED_PRIVATE_SENTINEL';self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
 def test_wrong_identity_rejected(self):self.assertRaises(ValueError,e.receipt,encode(full_receipt()),dict(IDENT,runId='124'))
 def test_synthetic_pixel_only_png_passes(self):
  b=png_bytes();self.assertGreater(len(b),10000);self.assertEqual(e.png(b)['sha256'],hashlib.sha256(b).hexdigest())
 def test_png_trailing_payload_and_metadata_rejected(self):
  b=png_bytes();self.assertRaises(ValueError,e.png,b+b'PRIVATE_SENTINEL')
  k=b'tEXt';v=b'PRIVATE_SENTINEL';c=struct.pack('>I',len(v))+k+v+struct.pack('>I',zlib.crc32(k+v)&0xffffffff)
  self.assertRaises(ValueError,e.png,b[:33]+c+b[33:])
 def test_png_crc_geometry_and_decompression_limit(self):
  b=bytearray(png_bytes());b[30]^=1;self.assertRaises(ValueError,e.png,bytes(b))
 def test_safe_after_controls_drift_preserved_without_acceptance(self):
  d=full_receipt();row=d['cases'][0];after=copy.deepcopy(row['controls']);after['lightIntensities'][0]+=.1
  row['controlsAfterJson']=json.dumps(after,separators=(',',':'));row['controlsAfterSha256']=hashlib.sha256(row['controlsAfterJson'].encode()).hexdigest();row['controlsStable']=False
  d.update(status='FAILED_DIAGNOSTIC_RESTORED',complete=False,failureCode=row['id'])
  self.assertEqual(e.receipt(encode(d),IDENT),d)
  with self.assertRaises(ValueError):v.validate_receipt(d,'a'*64,'b'*40)
 def test_after_payload_drift_still_rejects_bad_hash_and_unsafe_strings(self):
  d=full_receipt();row=d['cases'][0];after=copy.deepcopy(row['controls']);after['lightIntensities'][0]+=.1;row['controlsAfterJson']=json.dumps(after,separators=(',',':'))
  self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
  after['oakShader']='PRIVATE_SENTINEL';row['controlsAfterJson']=json.dumps(after,separators=(',',':'));row['controlsAfterSha256']=hashlib.sha256(row['controlsAfterJson'].encode()).hexdigest()
  self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
 def test_exact_RGB_and_RGBA_inflated_lengths_no_hidden_suffix(self):
  def chunk(k,v):return struct.pack('>I',len(v))+k+v+struct.pack('>I',zlib.crc32(k+v)&0xffffffff)
  def image(channels,extra=b'',truncate=0,compressed_extra=b''):
   pixels=bytes((i*37+i//53)%256 for i in range(1280*channels*720));scan=b''.join(b'\0'+pixels[i*1280*channels:(i+1)*1280*channels] for i in range(720))
   if truncate:scan=scan[:-truncate]
   return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1280,720,8,2 if channels==3 else 6,0,0,0))+chunk(b'IDAT',zlib.compress(scan+extra,1)+compressed_extra)+chunk(b'IEND',b'')
  for channels in [3,4]:
   with self.subTest(channels=channels):
    e.png(image(channels))
    for extra in [b'X',b'PRIVATE_SETTINGS_SENTINEL_'*1000,b'X'*(4*1024*1024)]:self.assertRaises(ValueError,e.png,image(channels,extra))
    self.assertRaises(ValueError,e.png,image(channels,truncate=1))
    self.assertRaises(ValueError,e.png,image(channels,compressed_extra=zlib.compress(b'PRIVATE_SENTINEL')))
    self.assertRaises(ValueError,e.png,image(channels,compressed_extra=b'PRIVATE_SENTINEL'))
 def test_regular_rejects_symlink_hardlink_parent_symlink(self):
  p=self.root/'x';p.write_bytes(b'x');(self.root/'y').symlink_to(p);self.assertRaises(ValueError,safe.regular,self.root/'y',100)
  os.link(p,self.root/'z');self.assertRaises(ValueError,safe.regular,p,100)
 def test_fixed_error_receipt_never_copies_exception_text(self):
  safe.begin('inventory','after');safe.checkpoint('OBSERVER')
  with mock.patch('sys.stdout',new_callable=io.StringIO) as out:code=safe.fail(ValueError('/private/PRIVATE_SENTINEL'))
  self.assertEqual(code,3);self.assertNotIn('PRIVATE_SENTINEL',out.getvalue());d=json.loads((self.root/e.TASK/'evidence/visual-candidate/post-inventory-after.json').read_text());self.assertEqual(d['status'],'BLOCKED');self.assertEqual(d['phase'],'OBSERVER');self.assertEqual(d['code'],'INPUT_OR_DEPENDENCY_REJECTED')
 def test_status_staging_rejects_existing_hardlink_secret(self):
  src=self.root/e.TASK/'evidence/visual-candidate';src.mkdir(parents=True);secret=self.root/'private';secret.write_bytes(b'PRIVATE_SETTINGS_SENTINEL')
  os.link(secret,src/'post-inventory-after.json');safe.begin('inventory','after');safe.checkpoint('OBSERVER')
  with mock.patch('sys.stdout',new_callable=io.StringIO):self.assertEqual(safe.fail(ValueError('UNKNOWN_ERROR')),3)
  report=safe.collect_statuses(self.root,IDENT);dst=self.root/e.TASK/'artifacts/post-capture-screened-status'
  self.assertFalse((dst/'post-inventory-after.json').exists());self.assertEqual(report['files'],[])
  self.assertFalse(any(b'PRIVATE_SETTINGS_SENTINEL' in p.read_bytes() for p in dst.iterdir()))
 def test_status_staging_schema_identity_and_links_fail_closed(self):
  safe.begin('inventory','after');safe.checkpoint('OBSERVER');safe.persist('BLOCKED','OBSERVER_EXIT')
  src=self.root/e.TASK/'evidence/visual-candidate';good=(src/'post-inventory-after.json').read_bytes();self.assertEqual(safe.screened_status(good,'post-inventory-after.json',IDENT),good)
  data=json.loads(good)
  for changes in [{'private':'PRIVATE_SENTINEL'},{'code':'PRIVATE_SENTINEL'},{'phase':'PRIVATE_SENTINEL'},{'runId':'124'},{'schemaVersion':True},{'status':'COMPLETED'},{'status':'COMPLETED','code':'NONE'},{'component':'counter-light'},{'mode':'before'}]:
   raw=(json.dumps(dict(data,**changes),sort_keys=True,separators=(',',':'))+'\n').encode();self.assertRaises(ValueError,safe.screened_status,raw,'post-inventory-after.json',IDENT)
  self.assertRaises(ValueError,safe.screened_status,good.replace(b'{',b'{"code":"PRIVATE_SENTINEL",',1),'post-inventory-after.json',IDENT)
  (src/'post-inventory-before.json').symlink_to(src/'post-inventory-after.json')
  report=safe.collect_statuses(self.root,IDENT);self.assertEqual([x['file'] for x in report['files']],['post-inventory-after.json'])
 def test_status_staging_existing_output_blocks_no_reuse(self):
  dst=self.root/e.TASK/'artifacts/post-capture-screened-status';dst.mkdir(parents=True);(dst/'post-inventory-after.json').write_text('PRIVATE_SENTINEL')
  self.assertRaises(ValueError,safe.collect_statuses,self.root,IDENT)
 def test_status_collector_cli_outputs_only_screened_directory_flag(self):
  safe.begin('inventory','after');safe.checkpoint('OBSERVER');safe.persist('BLOCKED','OBSERVER_EXIT');output=self.root/'outputs';output.write_text('')
  p=subprocess.run([sys.executable,str(S/'post_capture_safety.py'),'collect-statuses'],capture_output=True,text=True,env={**os.environ,'GITHUB_OUTPUT':str(output)})
  self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertEqual(p.stderr,'');self.assertEqual(output.read_text(),'safe_statuses=true\n')
  dst=self.root/e.TASK/'artifacts/post-capture-screened-status';self.assertTrue((dst/'post-inventory-after.json').is_file());self.assertFalse((dst/'counter-light-gate.json').exists())
 def test_known_observer_code_retained_unknown_redacted(self):
  self.assertEqual(safe.error_code(inventory.Blocked('OBSERVER_UNKNOWN_PATH')),'OBSERVER_UNKNOWN_PATH')
  self.assertEqual(safe.error_code(inventory.Blocked('OBSERVER_PRIVATE_SENTINEL')),'INPUT_OR_DEPENDENCY_REJECTED')
 def test_observer_exit_preserves_allowlisted_nested_error(self):
  home=self.root/'home';home.mkdir();(home/'before-state.json').write_text(json.dumps({'beforeSha256':'a'*64}))
  result=subprocess.CompletedProcess([],3,stdout=b'{"status":"BLOCKED","code":"UNKNOWN_PATH"}',stderr=b'')
  with mock.patch.object(inventory.subprocess,'run',return_value=result):
   self.assertRaisesRegex(inventory.Blocked,'OBSERVER_UNKNOWN_PATH',inventory.observer_cli,home,None,{},self.root,'after',0)
 def test_partial_export_is_independent_never_writes_gate(self):
  src=self.root/e.TASK/'artifacts/counter-light-diagnostic/run-123-attempt-1';src.mkdir(parents=True)
  (src/'diagnostic-receipt.json').write_bytes(encode(full_receipt()));name=e.inc.filename('ambient-sh-zero');(src/name).write_bytes(png_bytes());(src/'arbitrary.log').write_text('PRIVATE_SENTINEL')
  d=e.collect(self.root,IDENT,1);self.assertFalse(d['g3Pass']);self.assertEqual(len(d['files']),2);self.assertEqual(len(d['collectionFailures']),18)
  dest=self.root/e.TASK/'artifacts/counter-light-observation';self.assertFalse((dest/'arbitrary.log').exists());self.assertFalse((dest/'counter-light-gate.json').exists());self.assertNotIn('PRIVATE_SENTINEL',(dest/'observation-manifest.json').read_text())
 def test_bad_receipt_does_not_suppress_safe_png(self):
  src=self.root/e.TASK/'artifacts/counter-light-diagnostic/run-123-attempt-1';src.mkdir(parents=True);(src/'diagnostic-receipt.json').write_text('{"secret":"PRIVATE_SENTINEL"}');(src/e.inc.filename('baseline-before')).write_bytes(png_bytes())
  d=e.collect(self.root,IDENT,1);self.assertEqual(len(d['files']),1);self.assertNotEqual(d['files'][0]['file'],'diagnostic-receipt.json')
 def test_malformed_cli_no_raw_stdout_stderr(self):
  p=subprocess.run([sys.executable,str(S/'counter_light_diagnostics/compose_evidence.py'),'PRIVATE_SENTINEL'],capture_output=True,text=True)
  self.assertNotEqual(p.returncode,0);self.assertEqual(p.stderr,'');self.assertNotIn('PRIVATE_SENTINEL',p.stdout)
if __name__=='__main__':unittest.main()
