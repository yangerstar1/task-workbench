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
 'lightRanges':[10,4.8,4.2,4,2],'lightSpotAngles':[115]*5,'lightInnerSpotAngles':[70]*5,'lightShadows':['Soft','Soft','Soft','None','None'],
 'lightEnabled':[True]*5,'lightCullingMasks':[-1]*5,'probeIntensity':.85,'reflectionIntensity':1,'probeTextureId':'31','probeTextureName':'Day','ambientSH':[.2]*27,
 'ambientMode':'Trilight','ambientIntensity':1,'ambientSkyColor':dict(r=.612,g=.666,b=.72,a=1),'ambientEquatorColor':dict(r=.522,g=.513,b=.459,a=1),
 'ambientGroundColor':dict(r=.306,g=.279,b=.234,a=1),'ambientLight':dict(r=.612,g=.666,b=.72,a=1),
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
 d={'schemaVersion':3,'scope':'DIAGNOSTIC_COUNTER_LIGHT_NOT_ART_APPROVAL_NOT_G3_PASS','status':'COMPLETE_DIAGNOSTIC_RESTORED',
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
  if label=='ambient-sh-zero':
   cc['ambientSH']=[0]*27
   for key in ['ambientSkyColor','ambientEquatorColor','ambientGroundColor','ambientLight']:cc[key]=dict(r=0,g=0,b=0,a=1)
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
 for row in d['cases']:row.update(sha256=('b' if row['id']=='ambient-sh-zero' else 'a')*64,bytes=10001)
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
 def test_current_day_trilight_float32_receipt_passes_semantics_and_safety(self):
  d=full_receipt()
  for controls in [d['initialControls']]+[row['controls'] for row in d['cases']]:
   for key in ('ambientSkyColor','ambientEquatorColor','ambientGroundColor','ambientLight'):
    controls[key]={k:struct.unpack('f',struct.pack('f',value))[0] for k,value in controls[key].items()}
  seal(d);self.assertEqual(e.receipt(encode(d),IDENT),d);v.validate_receipt(d,'a'*64,'b'*40)
 def test_previous_day_trilight_receipt_is_safe_but_semantically_rejected(self):
  d=full_receipt()
  old={'ambientSkyColor':dict(r=.68,g=.74,b=.80,a=1),'ambientEquatorColor':dict(r=.58,g=.57,b=.51,a=1),'ambientGroundColor':dict(r=.34,g=.31,b=.26,a=1),'ambientLight':dict(r=.68,g=.74,b=.80,a=1)}
  for controls in [d['initialControls']]+[row['controls'] for row in d['cases'] if row['id']!='ambient-sh-zero']:controls.update(copy.deepcopy(old))
  seal(d);self.assertEqual(e.receipt(encode(d),IDENT),d)
  with self.assertRaisesRegex(ValueError,'Initial Trilight color baseline drift'):v.validate_receipt(d,'a'*64,'b'*40)
 def test_v50_day_trilight_receipt_is_safe_but_semantically_rejected(self):
  d=full_receipt()
  old={'ambientSkyColor':dict(r=.51,g=.555,b=.60,a=1),'ambientEquatorColor':dict(r=.435,g=.4275,b=.3825,a=1),'ambientGroundColor':dict(r=.255,g=.2325,b=.195,a=1),'ambientLight':dict(r=.51,g=.555,b=.60,a=1)}
  for controls in [d['initialControls']]+[row['controls'] for row in d['cases'] if row['id']!='ambient-sh-zero']:controls.update(copy.deepcopy(old))
  seal(d);self.assertEqual(e.receipt(encode(d),IDENT),d)
  with self.assertRaisesRegex(ValueError,'Initial Trilight color baseline drift'):v.validate_receipt(d,'a'*64,'b'*40)
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

class MetaFlowDiagnosticTests(unittest.TestCase):
 """Synthetic rejection diagnostics, never a native/schema acceptance claim."""
 @classmethod
 def setUpClass(cls):
  import importlib.util
  spec=importlib.util.spec_from_file_location('meta_flow_observer',S/'stage_a_inventory/g3_shop_inventory.py')
  cls.inv=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.inv)
  cls.materials=frozenset(cls.inv.load_policy().names)
 def fixture(self,value,owner='externalObjects',key='first',root='ModelImporter'):
  return ('fileFormatVersion: 2\nguid: '+'a'*32+'\n'+root+':\n  '+owner+':\n  - '+key+': '+value+'\n').encode()
 def rejected(self,raw,asset='MODEL_INTERIOR'):
  with self.assertRaises(self.inv.Rejected) as caught:
   self.inv.screen_other_meta(raw,asset,self.materials)
  return str(caught.exception)
 def test_finite_alphabet_identical_at_all_three_export_boundaries(self):
  self.assertEqual(len(self.inv.META_FLOW_CODES),900)
  self.assertEqual(self.inv.META_FLOW_CODES,inventory.META_FLOW_CODES)
  self.assertEqual(self.inv.META_FLOW_CODES,safe.META_FLOW_CODES)
  for code in self.inv.META_FLOW_CODES:
   self.assertIn(code,inventory.OBSERVER_CODES)
   self.assertEqual(safe.error_code(ValueError('OBSERVER_'+code)),'OBSERVER_'+code)
   self.assertLess(len(code),200)
 def test_every_shape_has_a_bounded_explicit_example(self):
  examples={
   'MATERIAL_CORE_KNOWN':'{type: Material, assembly: UnityEngine.CoreModule, name: Warm_Oak}',
   'MATERIAL_LEGACY_KNOWN':'{type: Material, assembly: UnityEngine, name: Warm_Oak}',
   'MATERIAL_CORE_UNKNOWN_NAME':'{type: Material, assembly: UnityEngine.CoreModule, name: PRIVATE_SENTINEL}',
   'TYPED_IDENTIFIER_OTHER':'{type: PRIVATE_SENTINEL, assembly: PRIVATE_SENTINEL, name: Warm_Oak}',
   'INTEGER_PAIR_BOUNDED':'{43: -9223372036854775808}',
   'INTEGER_PAIR_OTHER':'{43: 9223372036854775808}',
   'RGBA_FINITE_BOUNDED':'{r: 1, g: -1.2e-3, b: 0, a: 1}',
   'RGBA_OTHER':'{r: 1e999, g: 0, b: 0, a: 1}',
   'REFERENCE_BOUNDED_NONCANONICAL':'{type: 3, guid: '+'b'*32+', fileID: 1}',
   'REFERENCE_OTHER':'{type: 999, guid: '+'b'*32+', fileID: 1}',
   'DUPLICATE_KEYS':'{type: Material, type: Material}',
   'NESTED_COLLECTION':'{first: {PRIVATE_SENTINEL: 1}}',
   'YAML_SPECIAL':'{first: &PRIVATE_SENTINEL 1}',
   'LIMIT':'{'+', '.join('k'+str(i)+': 1' for i in range(9))+'}',
   'OTHER':'{PRIVATE_SENTINEL: 1}'}
  self.assertEqual(set(examples),set(self.inv.META_FLOW_SHAPES))
  for expected,value in examples.items():
   with self.subTest(shape=expected):
    self.assertEqual(self.inv.meta_flow_shape(value,self.materials),expected)
    code=self.rejected(self.fixture(value))
    self.assertEqual(code,'META_UNSUPPORTED_FLOW__MODEL_INTERIOR__MODEL_EXTERNAL_FIRST__'+expected)
    self.assertNotIn('PRIVATE_SENTINEL',code);self.assertNotIn('Warm_Oak',code);self.assertNotIn('b'*32,code)
 def test_exact_four_model_identities_and_existing_roles_only(self):
  expected={'LotteryShop_Interior':'MODEL_INTERIOR','Tool_inspection_lamp':'MODEL_LAMP',
            'Tool_large_prize_stamp':'MODEL_STAMP','Tool_small_prize_box':'MODEL_BOX'}
  for name,label in expected.items():
   self.assertEqual(self.inv.meta_flow_asset(self.inv.SHOP+'/'+name+'.fbx.meta','SOURCE_PAIRED_META'),label)
  roles={'SOURCE_PAIRED_META':'SOURCE_PAIRED_META','SOURCE_DIRECTORY_META':'SOURCE_DIRECTORY_META',
         'GENERATED_DIRECTORY_META':'GENERATED_DIRECTORY_META','GENERATED_ASSET_META':'GENERATED_ASSET_META',
         'BOUNDED_MESH_CANDIDATE_META':'BOUNDED_MESH_META'}
  for role,label in roles.items():self.assertEqual(self.inv.meta_flow_asset('/PRIVATE_SENTINEL',role),label)
  self.assertEqual(self.inv.meta_flow_asset('/PRIVATE_SENTINEL','PRIVATE_SENTINEL'),'OTHER_META')
  code=self.rejected(self.fixture('{unknown: 1}'),asset='/PRIVATE_SENTINEL')
  self.assertIn('__OTHER_META__',code);self.assertNotIn('PRIVATE_SENTINEL',code)
 def test_fixed_field_ids_and_no_unknown_key_or_root_export(self):
  for owner,stem in [('externalObjects','MODEL_EXTERNAL'),('internalIDToNameTable','MODEL_INTERNAL_ID')]:
   for key in ['first','second']:
    code=self.rejected(self.fixture('{unknown: 1}',owner,key))
    self.assertIn('__'+stem+'_'+key.upper()+'__',code)
  code=self.rejected(self.fixture('{unknown: 1}','PRIVATE_SENTINEL','PRIVATE_SENTINEL'))
  self.assertIn('__MODEL_OTHER__',code);self.assertNotIn('PRIVATE_SENTINEL',code)
  code=self.rejected(self.fixture('{unknown: 1}',root='PRIVATE_SENTINEL'))
  self.assertIn('__OTHER__',code);self.assertNotIn('PRIVATE_SENTINEL',code)
 def test_known_type_assembly_and_material_membership_cannot_be_spoofed(self):
  for value in ['{type: Material, assembly: UnityEngine.CoreModule, name: Warm_Oak_PRIVATE_SENTINEL}',
                '{type: Material, assembly: UnityEngine.CoreModule, name: "Warm_Oak"}',
                '{type: Material, assembly: UnityEngine.CoreModule, name: Warm_Oak, extra: 1}',
                '{type: MaterialX, assembly: UnityEngine.CoreModule, name: Warm_Oak}',
                '{type: Material, assembly: UnityEngine.CoreModuleX, name: Warm_Oak}']:
   shape=self.inv.meta_flow_shape(value,self.materials)
   self.assertNotIn(shape,{'MATERIAL_CORE_KNOWN','MATERIAL_LEGACY_KNOWN'})
   self.assertIn(self.rejected(self.fixture(value)),self.inv.META_FLOW_CODES)
 def test_original_accepted_flow_and_plain_scalar_examples_still_accepted(self):
  for value in ['', '{}','[]','0','-1','Plain_Name',
                '{fileID: 0}','{fileID: -123, guid: '+'a'*32+', type: 3}',
                '{x: 0, y: 1}','{x: -1.5, y: 2e-3, z: 1}',
                '{x: 0, y: 0, z: 0, w: 1}']:
   with self.subTest(value=value):self.inv.screen_other_meta(self.fixture(value),'MODEL_INTERIOR',self.materials)
 def test_duplicate_nested_anchor_tag_alias_and_unknown_flows_stay_rejected(self):
  for value in ['{type: Material, type: Material}', '{a: {b: 1}}','{a: [1]}',
                '{a: &PRIVATE_SENTINEL 1}','{a: *PRIVATE_SENTINEL}','{a: !!str PRIVATE_SENTINEL}',
                '{"PRIVATE_SENTINEL": 1}','{r: NaN, g: 0, b: 0, a: 1}',
                '{r: Infinity, g: 0, b: 0, a: 1}', '{unknown: PRIVATE_SENTINEL}']:
   code=self.rejected(self.fixture(value));self.assertIn(code,self.inv.META_FLOW_CODES);self.assertNotIn('PRIVATE_SENTINEL',code)
 def test_original_utf8_size_sensitive_structure_and_duplicate_guards_remain(self):
  cases=[(b'\xff','META_ENCODING'),(b'a: '+b'x'*1024+b'\n','META_LINE_SIZE'),
         (b'password: PRIVATE_SENTINEL\n','META_SENSITIVE_KEY'),
         (b'userData: PRIVATE_SENTINEL\n','META_SENSITIVE_OR_BUNDLE_VALUE'),
         (b'a: 1\na: 2\n','META_DUPLICATE_KEY'),
         (b'"PRIVATE_SENTINEL": 1\n','META_UNSUPPORTED_SYNTAX'),
         (b'a: \n    b: 1\n','META_UNSUPPORTED_STRUCTURE'),
         (b'a: []\n  b: 1\n','META_UNSUPPORTED_STRUCTURE'),
         (b'a: \n'+b'  '*11+b'b: 1\n','META_UNSUPPORTED_STRUCTURE')]
  for raw,expected in cases:
   with self.subTest(expected=expected):self.assertEqual(self.rejected(raw),expected)
 def test_classifier_length_pair_count_depth_and_numeric_limits(self):
  for value in [None,[],{},b'x','{a: '+'x'*1024+'}','\u4e2d']:
   self.assertEqual(self.inv.meta_flow_shape(value,self.materials),'LIMIT')
  self.assertEqual(self.inv.meta_flow_shape('{'*500+'}'*500,self.materials),'NESTED_COLLECTION')
  for value in ['{43: 9223372036854775808}','{43: -9223372036854775809}','{-1: 1}']:
   self.assertEqual(self.inv.meta_flow_shape(value,self.materials),'INTEGER_PAIR_OTHER')
  for value in ['{r: 2147483649, g: 0, b: 0, a: 1}','{r: 1e999, g: 0, b: 0, a: 1}',
                '{r: '+('1'*33)+', g: 0, b: 0, a: 1}']:
   self.assertEqual(self.inv.meta_flow_shape(value,self.materials),'RGBA_OTHER')
  for value in ['{fileID: 9223372036854775808}','{fileID: 1, guid: BAD, type: 3}',
                '{type: 4, guid: '+'a'*32+', fileID: 1}']:
   self.assertEqual(self.inv.meta_flow_shape(value,self.materials),'REFERENCE_OTHER')
 def test_rejection_emits_original_two_field_envelope_exit3_no_report(self):
  raw=self.fixture('{type: Material, assembly: UnityEngine.CoreModule, name: Warm_Oak}')
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory);project=root/'project';project.mkdir();out=root/'never-written.json'
   ident={'sourceCommit':'1'*40,'gameSourceCommit':self.inv.PIN,'triggerCommit':'2'*40,
          'runId':'123','runAttempt':'1','context':'SHOP_IMPORT_INVENTORY_DIAGNOSTIC'}
   argv=['observer','before','--project',str(project),'--identity',str(root/'identity.json'),'--output',str(out)]
   def rejected_snapshot(*args):self.inv.screen_other_meta(raw,'MODEL_INTERIOR',self.materials)
   with mock.patch.object(sys,'argv',argv),mock.patch.object(self.inv,'load_policy'),\
        mock.patch.object(self.inv,'load_local',return_value=json.dumps(ident).encode()),\
        mock.patch.object(self.inv,'snapshot',side_effect=rejected_snapshot),\
        mock.patch('sys.stdout',new_callable=io.StringIO) as captured:
    self.assertEqual(self.inv.main(),3)
   payload=json.loads(captured.getvalue());self.assertEqual(set(payload),{'status','code'})
   self.assertEqual(payload['status'],'BLOCKED');self.assertIn(payload['code'],self.inv.META_FLOW_CODES)
   self.assertFalse(out.exists());self.assertNotIn('Warm_Oak',captured.getvalue());self.assertNotIn(str(root),captured.getvalue())
 def test_every_fixed_code_survives_adapter_while_unknown_and_extra_fields_fail(self):
  with tempfile.TemporaryDirectory() as directory:
   home=pathlib.Path(directory)
   for code in self.inv.META_FLOW_CODES:
    result=subprocess.CompletedProcess([],3,stdout=json.dumps({'status':'BLOCKED','code':code}).encode(),stderr=b'')
    with mock.patch.object(inventory.subprocess,'run',return_value=result),self.assertRaises(inventory.Blocked) as caught:
     inventory.observer_cli(home,None,{},home,'before')
    self.assertEqual(str(caught.exception),'OBSERVER_'+code)
   good=next(iter(self.inv.META_FLOW_CODES))
   for payload in [{'status':'BLOCKED','code':good,'extra':'PRIVATE_SENTINEL'},
                   {'status':'BLOCKED','code':good+'__PRIVATE_SENTINEL'},
                   {'status':'BLOCKED','code':float('nan')}]:
    result=subprocess.CompletedProcess([],3,stdout=json.dumps(payload).encode(),stderr=b'')
    with mock.patch.object(inventory.subprocess,'run',return_value=result),self.assertRaises(ValueError) as caught:
     inventory.observer_cli(home,None,{},home,'before')
    self.assertNotIn('PRIVATE_SENTINEL',str(caught.exception));self.assertNotEqual(str(caught.exception),'OBSERVER_'+good)
 def test_status_schema_and_collector_retain_finite_code_without_new_fields(self):
  code='OBSERVER_'+self.rejected(self.fixture('{type: Material, assembly: UnityEngine.CoreModule, name: PRIVATE_SENTINEL}'))
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory);old=copy.deepcopy(safe.ACTIVE)
   try:
    with mock.patch.dict(os.environ,{'GITHUB_WORKSPACE':str(root),'GITHUB_SHA':'b'*40,'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'1'}):
     safe.ACTIVE.clear();safe.begin('inventory','after');safe.checkpoint('OBSERVER')
     with mock.patch('sys.stdout',new_callable=io.StringIO) as captured:self.assertEqual(safe.fail(ValueError(code)),3)
     path=root/e.TASK/'evidence/visual-candidate/post-inventory-after.json';raw=path.read_bytes()
     data=json.loads(raw);self.assertEqual(set(data),safe.STATUS_KEYS);self.assertEqual(data['code'],code)
     self.assertEqual(data['acceptance'],'NOT_EVALUATED');self.assertNotIn('PRIVATE_SENTINEL',raw.decode())
     self.assertEqual(safe.screened_status(raw,path.name,IDENT),raw)
     for change in [{'code':code+'__PRIVATE_SENTINEL'},{'code':float('nan')},{'extra':'PRIVATE_SENTINEL'}]:
      bad=(json.dumps(dict(data,**change),sort_keys=True,separators=(',',':'))+'\n').encode()
      self.assertRaises(ValueError,safe.screened_status,bad,path.name,IDENT)
     report=safe.collect_statuses(root,IDENT);self.assertEqual([x['file'] for x in report['files']],[path.name])
     staged=root/e.TASK/'artifacts/post-capture-screened-status'/path.name;self.assertEqual(staged.read_bytes(),raw)
   finally:safe.ACTIVE.clear();safe.ACTIVE.update(old)
 def test_observer_no_follow_and_hardlink_guards_remain(self):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory);source=root/'file.meta';source.write_text('a: 1\n')
   linked=root/'link.meta';linked.symlink_to(source)
   with self.inv.SecureTree(root) as tree:self.assertRaises(self.inv.Rejected,tree.read,'link.meta',65536)
   linked.unlink();os.link(source,linked)
   with self.inv.SecureTree(root) as tree:self.assertRaises(self.inv.Rejected,tree.read,'file.meta',65536)
   folder=root/'real';folder.mkdir();(root/'symlink-directory').symlink_to(folder,target_is_directory=True)
   self.assertRaises(self.inv.Rejected,self.inv.SecureTree,root/'symlink-directory')
 def test_observe_calls_diagnostic_only_after_policy_classification(self):
  # Minimal synthetic policy/tree, not a Unity fixture or native result.
  path=self.inv.SHOP+'/LotteryShop_Interior.fbx.meta';raw=self.fixture('{43: 4300000}','internalIDToNameTable')
  policy=mock.Mock();policy.allowed_dirs=set();policy.sources={};policy.pothos=set();policy.names={'Warm_Oak':{}}
  policy.classify.return_value='SOURCE_PAIRED_META';policy.limit.return_value=65536
  tree=mock.Mock();tree.walk.return_value=[path];tree.exists.return_value=False;tree.read.return_value=raw
  with self.assertRaises(self.inv.Rejected) as caught:self.inv.observe(tree,policy,'AFTER')
  self.assertEqual(str(caught.exception),'META_UNSUPPORTED_FLOW__MODEL_INTERIOR__MODEL_INTERNAL_ID_FIRST__INTEGER_PAIR_BOUNDED')
  policy.classify.assert_called_once_with(path);tree.read.assert_called_once_with(path,65536)
  tree.finish.assert_not_called()

class Run33DiagnosticBindingTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import importlib.util
  spec=importlib.util.spec_from_file_location('run33_meta_observer',S/'stage_a_inventory/g3_shop_inventory.py')
  cls.inv=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.inv)
 def meta(self,value='{instanceID: 0}',key='lastHumanDescriptionAvatarSource',root='ModelImporter',nested=False):
  return ('fileFormatVersion: 2\nguid: '+'a'*32+'\n'+root+':\n'+('  humanDescription:\n  ' if nested else '')+'  '+key+': '+value+'\n').encode()
 def test_exact_native_budgets_reject_old_core_and_other_values(self):
  import compose_evidence as c
  for stage,budget in [('capture',1800),('regression-edit',480),('regression-play-core',720),('regression-play-world',480)]:
   c.verify_native_budget(stage,{'processBudgetSeconds':budget})
   for bad in [budget-1,budget+1,str(budget),float(budget),True,None]:
    with self.subTest(stage=stage,bad=bad),self.assertRaisesRegex(ValueError,'^ORIGINAL_NATIVE_BUDGET_CHANGED$'):
     c.verify_native_budget(stage,{'processBudgetSeconds':bad})
  for stage,budget in [('regression-play-core',480),('regression-play-world',720),('unknown',480)]:
   self.assertRaises(ValueError,c.verify_native_budget,stage,{'processBudgetSeconds':budget})
 def test_only_exact_model_null_avatar_slot_is_added(self):
  for asset in ['MODEL_INTERIOR','MODEL_LAMP','MODEL_STAMP','MODEL_BOX']:
   self.inv.screen_other_meta(self.meta(),asset)
  for value in ['{instanceID: 1}','{instanceID: -1}','{instanceID: 00}','{instanceID: 0.0}',
                '{instanceID: 0, instanceID: 0}','{instanceID: 0, token: PRIVATE_SENTINEL}',
                '{unknown: 0}','{instanceID: {fileID: 0}}','{instanceID: &alias 0}']:
   with self.subTest(value=value),self.assertRaises(self.inv.Rejected):
    self.inv.screen_other_meta(self.meta(value),'MODEL_INTERIOR')
  for raw,asset in [(self.meta(key='other'),'MODEL_INTERIOR'),(self.meta(root='OtherImporter'),'MODEL_INTERIOR'),
                    (self.meta(nested=True),'MODEL_INTERIOR'),(self.meta(),'OTHER_META')]:
   self.assertRaises(self.inv.Rejected,self.inv.screen_other_meta,raw,asset)
 def test_avatar_marker_screen_requires_exact_model_importer_root(self):
  import export_interior_meta as m
  result=m.project(self.meta(),{'sourceCommit':'1'*40,'runId':'123','runAttempt':'1'})
  for change in [{'key':'UNKNOWN_KEY'},{'indent':2},{'dash':True},{'tokens':['INTEGER']}]:
   bad=copy.deepcopy(result);bad['rows'][2].update(change)
   with self.subTest(change=change),self.assertRaises(m.Rejected):m.screen(bad)
 def test_fixed_avatar_projection_is_slot_bound_and_never_reconstructs_input(self):
  import export_interior_meta as m
  ident={'sourceCommit':'1'*40,'runId':'123','runAttempt':'1'}
  result=m.project(self.meta(),ident);self.assertEqual(result['rows'][-1]['tokens'],[m.AVATAR_ZERO]);m.encode(result)
  for raw in [self.meta('{instanceID: 1}'),self.meta(key='other'),self.meta(nested=True)]:
   row=m.project(raw,ident)['rows'][-1];self.assertNotIn(m.AVATAR_ZERO,row['tokens'])
  for change in [{'key':'other'},{'indent':4},{'dash':True},{'tokens':[m.AVATAR_ZERO,'INTEGER']}]:
   bad=copy.deepcopy(result);bad['rows'][-1].update(change);self.assertRaises(m.Rejected,m.screen,bad)
  self.assertRaises(m.Rejected,m.project,self.meta('{token: PRIVATE_SENTINEL}'),ident)

if __name__=='__main__':unittest.main()
