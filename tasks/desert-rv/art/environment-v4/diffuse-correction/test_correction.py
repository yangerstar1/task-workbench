"""Numerical/source checks, not visual acceptance. No engine is run by these tests."""
import hashlib,json,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
import correct_illumination as c
ROOT=Path(__file__).resolve().parents[3]
META=Path(__file__).with_name('derived-provenance.json')
RECORD=json.loads(META.read_text());SOURCE=ROOT/RECORD['source']['path'];DERIVED=ROOT/RECORD['derived']['path']
class CorrectionTests(unittest.TestCase):
 def test_exact_original_and_derived_hashes(self):
  for field,path in [('source',SOURCE),('derived',DERIVED)]:self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),RECORD[field]['sha256'])
 def test_license_and_source(self):
  self.assertEqual(RECORD['source']['source_url'],'https://polyhaven.com/a/sand_03');self.assertEqual(RECORD['source']['license'],'CC0-1.0');self.assertEqual(RECORD['derived']['license'],'CC0-1.0');self.assertFalse(RECORD['recipe']['source_modified']);self.assertFalse(RECORD['recipe']['new_noise'])
 def test_recipe_hash(self):self.assertEqual(hashlib.sha256((ROOT/RECORD['recipe']['path']).read_bytes()).hexdigest(),RECORD['recipe']['sha256'])
 def test_size_color_and_importer(self):
  with Image.open(DERIVED) as im:self.assertEqual(im.size,(1024,1024));self.assertEqual(im.mode,'RGB')
  self.assertLess(DERIVED.stat().st_size,2*1024**2)
  meta=DERIVED.with_name(DERIVED.name+'.meta').read_text()
  for text in ['sRGBTexture: 1','textureType: 0','enableMipMap: 1','filterMode: 2','aniso: 4','wrapU: 0','wrapV: 0','maxTextureSize: 1024']:self.assertIn(text,meta)
 def test_metrics_recompute_retains_fine_grain(self):
  a=c.linear(np.asarray(Image.open(SOURCE),dtype=float)/255);b=c.linear(np.asarray(Image.open(DERIVED),dtype=float)/255)
  before,after=c.metrics(a),c.metrics(b)
  self.assertLess(after['low_frequency_rms_fraction_le4'],before['low_frequency_rms_fraction_le4']*.2)
  self.assertLess(after['x_fundamental_amplitude_fraction'],.003);self.assertLess(after['z_fundamental_amplitude_fraction'],.003)
  self.assertGreater(after['grain_rms_fraction_ge16']/before['grain_rms_fraction_ge16'],.95)
  self.assertLess(after['grain_rms_fraction_ge16']/before['grain_rms_fraction_ge16'],1.05)
  self.assertTrue(np.max(np.abs(b.mean(axis=(0,1))/a.mean(axis=(0,1))-1))<.001)
 def test_no_new_border_discontinuity(self):
  y=c.linear(np.asarray(Image.open(DERIVED),dtype=float)/255)@c.WEIGHTS
  for edge,interior in [(y[:,0]-y[:,-1],np.diff(y,axis=1)),(y[0]-y[-1],np.diff(y,axis=0))]:self.assertLess(np.sqrt(np.mean(edge**2))/np.sqrt(np.mean(interior**2)),1.2)
 def test_reproduction_matches_exact_decoded_pixels(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d)/'derived.png';c.correct(SOURCE,out)
   self.assertTrue(np.array_equal(np.asarray(Image.open(out)),np.asarray(Image.open(DERIVED))))
 def test_reject_wrong_input(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'source.jpg';p.write_bytes(b'wrong')
   with self.assertRaises(ValueError):c.correct(p,Path(d)/'out.png')
 def test_reject_overwrite(self):
  with self.assertRaises(ValueError):c.correct(SOURCE,DERIVED)
 def test_original_cc0_payloads_are_all_preserved(self):
  data=json.loads((ROOT/'unity/Assets/DesertRV/Art/EnvironmentV4/asset-provenance.json').read_text())
  self.assertEqual(len(data['assets']),29)
  for row in data['assets']:self.assertEqual(hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest(),row['sha256'])
if __name__=='__main__':unittest.main()
