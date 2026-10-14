#!/usr/bin/env python3
"""Synthetic source-only Trilight protocol tests. No Unity execution/visual approval."""
import copy, hashlib, json, struct, tempfile, zlib
from pathlib import Path
import unittest
import numpy as np
from test_post_capture_safety_ci import full_receipt, seal, encode, IDENT, e, v

ROOT=Path(__file__).resolve().parents[3]
NATIVE=ROOT/'tasks/lottery-shop/unity/Assets/G3/Tests/VisualCandidate/CounterLightDiagnosticCapture.cs'
COLORS=('ambientSkyColor','ambientEquatorColor','ambientGroundColor','ambientLight')
NEW=('ambientMode','ambientIntensity')+COLORS
CASES=['pendant-zero','boardwash-zero','counter-pair-zero','daylight-zero','reading-zero','shelf-zero',
 'all-direct-zero','probe-intensity-zero','global-reflection-zero','reflection-controls-zero','ambient-sh-zero',
 'counter-and-reflection-controls-zero','oak-specular-highlights-off','oak-normal-flat','oak-roughness-one','oak-texture-only','oak-target-mask']

def ambient(d):return next(r for r in d['cases'] if r['id']=='ambient-sh-zero')
def check(d):v.validate_receipt(d,'a'*64,'b'*40)

class AmbientDiagnosticTests(unittest.TestCase):
 def test_new_complete_synthetic_receipt_passes_semantics_and_safety(self):
  d=full_receipt();check(d);self.assertEqual(e.receipt(encode(d),IDENT),d)
 def test_explicit_schema_three_only(self):
  for schema in (2,4,True,'3',3.0):
   d=full_receipt();d['schemaVersion']=schema
   with self.subTest(schema=schema):
    self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
    self.assertRaises(ValueError,check,d)
 def test_missing_each_new_field_rejected(self):
  for key in NEW:
   d=full_receipt();del d['initialControls'][key];seal(d)
   with self.subTest(key=key):
    self.assertRaises(ValueError,check,d);self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
 def test_unknown_control_keys_rejected(self):
  for where in ('initial','case'):
   d=full_receipt();c=d['initialControls'] if where=='initial' else ambient(d)['controls'];c['unexpected']='PRIVATE_SENTINEL';seal(d)
   self.assertRaises(ValueError,check,d);self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
 def test_new_scalar_shape_and_bounds_rejected(self):
  for value in (True,'1',None,float('nan'),float('inf'),-1,9,1e10):
   d=full_receipt();d['initialControls']['ambientIntensity']=value;seal(d)
   with self.subTest(value=value):
    self.assertRaises(ValueError,check,d);self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
 def test_new_color_shape_and_bounds_rejected(self):
  for color in (None,{},dict(r=0,g=0,b=0,a=1,x=0),dict(r=True,g=0,b=0,a=1),dict(r='PRIVATE_SENTINEL',g=0,b=0,a=1),dict(r=float('nan'),g=0,b=0,a=1),dict(r=1e10,g=0,b=0,a=1)):
   d=full_receipt();d['initialControls']['ambientEquatorColor']=color;seal(d)
   self.assertRaises(ValueError,check,d);self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
 def test_unknown_mode_string_rejected_by_both(self):
  d=full_receipt();d['initialControls']['ambientMode']='PRIVATE_SENTINEL';seal(d)
  self.assertRaises(ValueError,check,d);self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
 def test_known_wrong_mode_preserved_for_diagnostics_but_not_accepted(self):
  for mode in ('Skybox','Flat','Custom'):
   d=full_receipt();ambient(d)['controls']['ambientMode']=mode;seal(d)
   e.receipt(encode(d),IDENT);self.assertRaises(ValueError,check,d)
 def test_all_27_effective_SH_components_must_be_exact_zero(self):
  for index in range(27):
   d=full_receipt();ambient(d)['controls']['ambientSH'][index]=1e-30;seal(d)
   with self.subTest(index=index):
    e.receipt(encode(d),IDENT);self.assertRaises(ValueError,check,d)
 def test_all_three_source_colors_and_alias_must_be_exact_zero_RGB(self):
  for key in COLORS:
   for component in 'rgb':
    d=full_receipt();ambient(d)['controls'][key][component]=1e-30;seal(d)
    with self.subTest(key=key,component=component):self.assertRaises(ValueError,check,d)
 def test_source_color_alpha_must_be_preserved(self):
  for key in COLORS:
   d=full_receipt();ambient(d)['controls'][key]['a']=0;seal(d);self.assertRaises(ValueError,check,d)
 def test_alias_mismatch_rejected_semantically_preserved_safely(self):
  d=full_receipt();ambient(d)['controls']['ambientLight']['r']=.1;seal(d)
  e.receipt(encode(d),IDENT);self.assertRaises(ValueError,check,d)
 def test_ambient_intensity_cannot_change_for_ablation(self):
  d=full_receipt();ambient(d)['controls']['ambientIntensity']=0;seal(d)
  e.receipt(encode(d),IDENT);self.assertRaises(ValueError,check,d)
 def test_other_16_cases_preserve_all_ambient_fields(self):
  for label in CASES:
   if label=='ambient-sh-zero':continue
   for key in NEW+('ambientSH',):
    d=full_receipt();c=next(r for r in d['cases'] if r['id']==label)['controls']
    if key in COLORS:c[key]['r']=0
    elif key=='ambientMode':c[key]='Flat'
    elif key=='ambientIntensity':c[key]=0
    else:c[key][0]=0
    seal(d)
    with self.subTest(label=label,key=key):self.assertRaises(ValueError,check,d)
 def test_ambient_cannot_mutate_direct_reflection_or_material(self):
  for key in ('lightIntensities','probeIntensity','reflectionIntensity','probeTextureId','oakSmoothness'):
   d=full_receipt();c=ambient(d)['controls']
   if key=='lightIntensities':c[key][0]=0
   elif key=='probeTextureId':c[key]='32'
   else:c[key]=0
   seal(d)
   with self.subTest(key=key):self.assertRaises(ValueError,check,d)
 def test_initial_trilight_baseline_must_match_real_day_source(self):
  for key in COLORS[:3]:
   d=full_receipt();d['initialControls'][key]['g']+=.01;seal(d);self.assertRaises(ValueError,check,d)
 def test_restoration_failure_never_becomes_acceptance(self):
  for key,value in [('restored',False),('propertiesRestored',False),('complete',False),('pixelRestoreProof','UNVERIFIED'),('sceneAfterSha256','d'*64),('stateAfterSha256','UNVERIFIED')]:
   d=full_receipt();d[key]=value;e.receipt(encode(d),IDENT);self.assertRaises(ValueError,check,d)
 def test_case_restore_proof_requires_original_png(self):
  for key,value in [('restored',False),('propertiesRestored',False),('restoredPngSha256','c'*64)]:
   d=full_receipt();ambient(d)[key]=value;e.receipt(encode(d),IDENT);self.assertRaises(ValueError,check,d)
 def test_safe_actual_after_drift_is_preserved_but_semantically_rejected(self):
  for key in ('ambientIntensity','ambientSkyColor','ambientSH'):
   d=full_receipt();row=ambient(d);after=copy.deepcopy(row['controls'])
   if key=='ambientIntensity':after[key]=.5
   elif key=='ambientSH':after[key][0]=.1
   else:after[key]['r']=.1
   row['controlsAfterJson']=json.dumps(after,separators=(',',':'));row['controlsAfterSha256']=hashlib.sha256(row['controlsAfterJson'].encode()).hexdigest();row['controlsStable']=False
   self.assertEqual(e.receipt(encode(d),IDENT),d);self.assertRaises(ValueError,check,d)
 def test_unsettled_SH_before_render_is_safely_retained_and_rejected(self):
  d=full_receipt();d.update(status='FAILED_DIAGNOSTIC_RESTORED',complete=False,failureCode='ambient-sh-zero');d['cases']=d['cases'][:11];row=ambient(d)
  row['controls']['ambientSH']=copy.deepcopy(d['initialControls']['ambientSH']);seal(d)
  row.update(file=None,sha256=None,bytes=0,captured=False,controlsStable=False,controlsAfterJson=None,controlsAfterSha256=None)
  self.assertEqual(e.receipt(encode(d),IDENT),d);self.assertRaises(ValueError,check,d)
 def test_before_payload_must_match_observed_control_structure(self):
  d=full_receipt();ambient(d)['controls']['ambientIntensity']=.5
  self.assertRaises(ValueError,check,d);self.assertRaises(ValueError,e.receipt,encode(d),IDENT)
 def test_same_encoded_png_is_rejected_even_with_zero_controls(self):
  d=full_receipt();ambient(d)['sha256']='a'*64
  e.receipt(encode(d),IDENT);self.assertRaisesRegex(ValueError,'encoded image unchanged',check,d)
 def test_actual_decoded_pixel_equality_is_rejected(self):
  a=np.zeros((720,1280,3));self.assertRaisesRegex(ValueError,'decoded pixels unchanged',v.validate_ambient_pixel_effect,a,a.copy())
 def test_different_pixel_only_PNG_encoding_cannot_fake_an_effect(self):
  pixels=bytes((i*19+i//41)%256 for i in range(1280*3*720));rows=b''.join(b'\0'+pixels[i*3840:(i+1)*3840] for i in range(720))
  def chunk(k,x):return struct.pack('>I',len(x))+k+x+struct.pack('>I',zlib.crc32(k+x)&0xffffffff)
  def image(level):return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1280,720,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows,level))+chunk(b'IEND',b'')
  a,b=image(1),image(9);self.assertNotEqual(a,b);e.png(a);e.png(b)
  with tempfile.TemporaryDirectory() as temp:
   pa,pb=Path(temp)/'a.png',Path(temp)/'b.png';pa.write_bytes(a);pb.write_bytes(b)
   aa=v.png(pa,hashlib.sha256(a).hexdigest(),len(a));bb=v.png(pb,hashlib.sha256(b).hexdigest(),len(b))
   self.assertRaisesRegex(ValueError,'decoded pixels unchanged',v.validate_ambient_pixel_effect,aa,bb)
 def test_one_actual_RGB_code_difference_is_sufficient_no_art_threshold(self):
  a=np.zeros((720,1280,3));b=a.copy();b[42,10,1]=1;v.validate_ambient_pixel_effect(a,b)
 def test_decoded_geometry_drift_rejected(self):
  self.assertRaises(ValueError,v.validate_ambient_pixel_effect,np.zeros((720,1280,3)),np.zeros((1,1,3)))
 def test_case_sequence_unchanged_and_no_case_can_be_deleted(self):
  self.assertEqual(v.CASES,CASES)
  d=full_receipt();d['cases'].pop(10);self.assertRaises(ValueError,check,d)
 def test_native_records_actual_getters_and_schema_three(self):
  source=NATIVE.read_text();self.assertIn('public int schemaVersion = 3;',source)
  for name in NEW:self.assertIn('RenderSettings.'+name,source)
  self.assertIn('ambientSH = Enumerable.Range(0, 27).Select(i => RenderSettings.ambientProbe[i/9, i%9]).ToArray()',source)
 def test_native_ambient_case_changes_only_source_RGB_not_final_SH(self):
  source=NATIVE.read_text();block=source.split('case "ambient-sh-zero":',1)[1].split('case "counter-and-reflection-controls-zero":',1)[0]
  for key in COLORS[:3]:self.assertIn('RenderSettings.'+key+' = ZeroRgb(',block)
  for prohibited in ('ambientProbe =','ambientMode =','ambientIntensity =','reflectionIntensity =','probe.intensity =','lights['):self.assertNotIn(prohibited,block)
  self.assertIn('new Color(0, 0, 0, value.a)',source)
 def test_native_checks_effective_27_before_and_after_render(self):
  source=NATIVE.read_text();block=source.split('void RunCase(string id)',1)[1].split('bool WithinBudget()',1)[0]
  self.assertEqual(block.count('RequireAmbientCase(id);'),2)
  self.assertLess(block.index('row.controlsBeforeJson'),block.index('RequireAmbientCase(id);'))
  self.assertLess(block.index('row.controlsAfterJson'),block.rindex('RequireAmbientCase(id);'))
  self.assertIn('channel < 3',source);self.assertIn('coefficient < 9',source);self.assertIn('effective[channel, coefficient] == (zero ? 0f : ambient[channel, coefficient])',source)
 def test_native_restore_independently_restores_all_sources_and_proof(self):
  source=NATIVE.read_text();block=source.split('void Restore(List<Exception> errors)',1)[1].split('void RestoreCamera()',1)[0]
  for field in ('ambientMode','ambientIntensity','ambientSkyColor','ambientEquatorColor','ambientGroundColor','ambientProbe'):
   self.assertIn('RenderSettings.'+field+' = ',block)
  for field in ('ambientMode','ambientIntensity'):
   self.assertIn('if(RenderSettings.'+field+' != ',block)
  for field in COLORS[:3]:self.assertIn('if(!RenderSettings.'+field+'.Equals(',block)
  self.assertIn('Hash(GuardState())',source);self.assertIn('PER_CASE_RESTORED_PIXEL_MISMATCH',source)
 def test_composer_uses_the_strict_increment_and_original_bound_gates(self):
  source=(ROOT/'tasks/lottery-shop/scripts/counter_light_diagnostics/compose_evidence.py').read_text()
  self.assertIn("inc._validate_increment(diag,up/'captures',up/'capture/raw-test-results.xml',ident['sourceCommit'])",source)
  self.assertLess(source.index('v.export_captures(root,True)'),source.index('inc._validate_increment'))
 def test_decoded_effect_check_is_wired_after_bound_original_png_read(self):
  source=(ROOT/'tasks/lottery-shop/scripts/counter_light_diagnostics/verify_and_measure.py').read_text()
  start=source.index('def _validate_increment(');end=source.index('def validate_ambient_pixel_effect(')
  block=source[start:end]
  self.assertIn("base = png(normal/'phone-mom-pending.png', pending['sha256'], pending['bytes'])",block)
  self.assertIn("images = {r['id']:png(diag/r['file'],r['sha256'],r['bytes'])",block)
  self.assertIn("validate_ambient_pixel_effect(base,images['ambient-sh-zero'])",block)
 def test_new_suite_runs_before_native_using_pinned_image_python(self):
  source=(ROOT/'.github/workflows/lottery-visual-candidate.yml').read_text()
  command='"$LIGHT_ENV/bin/python" tasks/lottery-shop/scripts/test_ambient_diagnostic_ci.py -v'
  self.assertEqual(source.count(command),1);self.assertLess(source.index(command),source.index('id: safestart'))

if __name__=='__main__':unittest.main()
