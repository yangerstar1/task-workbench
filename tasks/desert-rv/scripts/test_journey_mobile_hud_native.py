"""Finite actual PNG/CSV/hash/XML corruption checks; never native execution."""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from PIL import Image,ImageDraw
import journey_mobile_hud_native as gate

class MobileHudNativeGateTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  change=patch.object(gate,'ROOT',self.root);change.start();self.addCleanup(change.stop)
  self.folder=self.root/'captures';self.folder.mkdir();self.entries=[]
  cache={}
  for profile,size in gate.PROFILES.items():
   image=Image.new('RGB',size,(210,215,220));draw=ImageDraw.Draw(image);draw.rectangle((50,50,size[0]-50,200),fill=(15,25,35))
   stream=io.BytesIO();image.save(stream,format='PNG');cache[profile]=stream.getvalue()
  for stem in gate.STEMS:
   profile,mode,background=stem.split('-')
   self.write(stem+'.png',cache[profile])
   self.write(stem+'-fit.csv',('profile,mode,background,label,font,available_height,preferred_height\n'+','.join((profile,mode,background,'Objective text','16','42','40'))+'\n').encode())
  self.manifest=dict(source='production JourneyHud graph and pinned CJK font',evidence='native simulated-device UI render; no physical-device or gameplay acceptance',files=self.entries)
  self.save()
 def write(self,name,data):
  (self.folder/name).write_bytes(data);self.entries.append(dict(name=name,bytes=len(data),sha256=gate.sha(data)))
 def save(self): (self.folder/gate.MANIFEST).write_text(json.dumps(self.manifest))
 def refresh(self,name):
  data=(self.folder/name).read_bytes()
  entry=next(x for x in self.entries if x['name']==name);entry.update(bytes=len(data),sha256=gate.sha(data));self.save()
 def test_actual_thirteen_pngs_and_fit_metrics_match_exact_inventory(self):
  result=gate.capture_inventory(self.folder);self.assertEqual(len(result),27);self.assertEqual(len(gate.STEMS),13)
 def test_missing_extra_and_changed_capture_cannot_pass(self):
  name=gate.STEMS[0]+'.png';p=self.folder/name;original=p.read_bytes();p.unlink()
  with self.assertRaisesRegex(ValueError,'MOBILE_HUD_CAPTURE_INVENTORY'):gate.capture_inventory(self.folder)
  p.write_bytes(original);extra=self.folder/'old-snapshot.png';extra.write_bytes(original)
  with self.assertRaisesRegex(ValueError,'MOBILE_HUD_CAPTURE_INVENTORY'):gate.capture_inventory(self.folder)
  extra.unlink();p.write_bytes(original+b'changed')
  with self.assertRaisesRegex(ValueError,'MOBILE_HUD_CAPTURE_HASH'):gate.capture_inventory(self.folder)
 def test_resealed_wrong_size_or_blank_png_cannot_pass(self):
  name=gate.STEMS[0]+'.png';p=self.folder/name
  for size,code in [((8,8),'MOBILE_HUD_PNG_SHAPE'),(gate.PROFILES[gate.STEMS[0].split('-')[0]],'MOBILE_HUD_PNG_BLANK')]:
   Image.new('RGB',size,(0,0,0)).save(p);self.refresh(name)
   with self.subTest(size=size),self.assertRaisesRegex(ValueError,code):gate.capture_inventory(self.folder)
 def test_resealed_clipped_small_or_nonfinite_text_cannot_pass(self):
  name=gate.STEMS[0]+'-fit.csv';p=self.folder/name;original=p.read_text()
  for font,available,preferred in [('16','42','50'),('10','42','40'),('16','42','NaN')]:
   p.write_text(original.replace('16,42,40',','.join((font,available,preferred))));self.refresh(name)
   with self.subTest(values=(font,available,preferred)),self.assertRaisesRegex(ValueError,'MOBILE_HUD_FIT_CLIPPED'):gate.capture_inventory(self.folder)
 def test_duplicate_manifest_rows_cannot_hide_omitted_file(self):
  self.manifest['files'][-1]=copy.deepcopy(self.manifest['files'][0]);self.save()
  with self.assertRaisesRegex(ValueError,'MOBILE_HUD_CAPTURE_ROWS'):gate.capture_inventory(self.folder)
 def test_only_two_authored_world_views_and_exact_evidence_scope_pass(self):
  world=self.root/'world';world.mkdir();(world/'EVIDENCE.txt').write_text(gate.WORLD_EVIDENCE)
  for stem in gate.WORLD_STEMS:
   (world/(stem+'.png')).write_bytes((self.folder/'desktop-foot-glare.png').read_bytes())
   profile,mode,background=stem.split('-',2)
   (world/(stem+'-fit.csv')).write_text('profile,mode,background,label,font,available_height,preferred_height\n'+','.join((profile,mode,background,'Objective text','16','42','40'))+'\n')
  self.assertEqual(len(gate.world_inventory(world)),5)
  (world/'EVIDENCE.txt').write_text('Live gameplay accepted')
  with self.assertRaisesRegex(ValueError,'MOBILE_HUD_WORLD_SCOPE'):gate.world_inventory(world)
  (world/'EVIDENCE.txt').write_text(gate.WORLD_EVIDENCE);(world/'extra.png').write_bytes(b'old snapshot')
  with self.assertRaisesRegex(ValueError,'MOBILE_HUD_WORLD_INVENTORY'):gate.world_inventory(world)
 def test_exact_ten_native_cases_reject_missing_duplicate_extra_and_failure(self):
  folder=self.root/'xml';folder.mkdir();p=folder/'result.xml'
  def value():
   root=ET.Element('test-run',result='Passed',total='10',passed='10',failed='0',skipped='0',inconclusive='0')
   for name in gate.EXPECTED:ET.SubElement(root,'test-case',fullname=name,result='Passed')
   return root
  with patch.object(gate,'ARTIFACTS',folder):
   ET.ElementTree(value()).write(p);self.assertEqual(gate.inspect_xml()['count'],10)
   for mutation in ('missing','duplicate','extra','failure'):
    root=value()
    if mutation=='missing':root.remove(root[0])
    if mutation=='duplicate':root[1].set('fullname',root[0].get('fullname'))
    if mutation=='extra':ET.SubElement(root,'test-case',fullname='Other',result='Passed')
    if mutation=='failure':root[0].set('result','Failed')
    ET.ElementTree(root).write(p)
    with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'MOBILE_HUD_EXACT_TEN'):gate.inspect_xml()

if __name__=='__main__':unittest.main()
