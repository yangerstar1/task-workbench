#!/usr/bin/env python3
"""Synthetic validator unit fixtures only. Never upload these as Unity/game evidence."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest import mock
from PIL import Image
import environment_v4_evidence as v4

class V4EvidenceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.contract=v4.load_contract()
 def tearDown(self):self.temp.cleanup()
 def generated(self):
  folder=self.root/v4.legacy.GENERATED;folder.mkdir(parents=True)
  names=set(self.contract['files'])|set(self.contract['metadata_files'])|{v4.legacy.GENERATED+'.meta'}
  for leaf in ['JourneyBootstrap.unity','FirstStation.unity','Scrapyard.unity','NightBeacon.unity','JourneyContent.asset']:
   names|={v4.legacy.GENERATED+'/'+leaf,v4.legacy.GENERATED+'/'+leaf+'.meta'}
  for name in names:
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fileFormatVersion: 2\nguid: '+'a'*32+'\n' if name.endswith('.meta') else '%YAML 1.1\n--- !u!43 &4300000\nMesh:\n  m_Name: synthetic-validation-fixture\n')
  return names
 def extra(self):
  folder=self.root/v4.EXTRA;folder.mkdir(parents=True)
  images=[]
  for index,view in enumerate(v4.CLOSEUP_VIEWS):
   name='FirstStation-'+view+'.png'
   # Explicit synthetic checkerboard for validator branch tests, not game pixels.
   im=Image.new('RGB',(1440,900),'navy');im.paste('tan',(100,100,700,700));im.save(folder/name)
   images.append(dict(view=view,file=v4.EXTRA+'/'+name,position=dict(x=-4.85-index*4.4,y=1.62,z=4.25),lookAt=dict(x=-9.5-index*3,y=1.5,z=-1),fieldOfView=66))
  (folder/'closeup-capture-report.json').write_text(json.dumps(dict(status='ACTUAL_EDITOR_EYE_HEIGHT_VIEWS_NOT_INPUT_PLAYTHROUGH',graphicsDevice='OpenGLCore',savedSceneBytesPreserved=True,captureBuffersReleased=True,images=images)))
  cumulative={v4.POLISH+'/Surface-'+m+'.mat' for m in self.contract['material_names']}
  for region in (1,2,3):
   cumulative|={v4.POLISH+'/R'+str(region)+'-'+k+'.asset' for k in self.contract['region_mesh_keys'][str(region)]}
   count=len(self.contract['region_mesh_keys'][str(region)])
   (folder/f'region-{region}-authoring.json').write_text(json.dumps(dict(region=region,meshCount=count,rendererCount=count+2,triangles=1000,importedModelRenderers=2,importedModelTriangles=2000,addedLights={1:2,2:1,3:2}[region],status='authored-not-visually-accepted',generatedFiles=sorted(cumulative))))
  return folder
 def change(self,path,fn):
  value=json.loads(path.read_text());fn(value);path.write_text(json.dumps(value))
 def test_exact_contract_and_output_membership(self):
  names=self.generated();self.assertEqual(set(v4.collect_generated(self.root,self.contract)),names)
 def test_missing_mesh_fails(self):
  self.generated();(self.root/self.contract['files'][0]).unlink()
  with self.assertRaises(ValueError):v4.collect_generated(self.root,self.contract)
 def test_extra_mesh_cannot_hide_in_new_directory(self):
  self.generated();(self.root/v4.POLISH/'unreviewed.asset').write_text('%YAML 1.1\n')
  with self.assertRaises(ValueError):v4.collect_generated(self.root,self.contract)
 def test_binary_generated_asset_is_not_silently_accepted(self):
  self.generated();(self.root/self.contract['files'][0]).write_text('not-unity-yaml')
  with self.assertRaises(ValueError):v4.collect_generated(self.root,self.contract)
 def test_two_extra_images_and_native_budgets_validate(self):
  self.extra();report=v4.inspect_extra(self.root,self.contract);self.assertEqual(len(report['images']),2);self.assertEqual(len(report['authoring']),3)
 def test_zoomed_closeup_fails(self):
  folder=self.extra();self.change(folder/'closeup-capture-report.json',lambda r:r['images'][0].update(fieldOfView=30))
  with self.assertRaises(ValueError):v4.inspect_extra(self.root,self.contract)
 def test_floating_showcase_camera_fails(self):
  folder=self.extra();self.change(folder/'closeup-capture-report.json',lambda r:r['images'][0]['position'].update(y=4))
  with self.assertRaises(ValueError):v4.inspect_extra(self.root,self.contract)
 def test_scene_mutation_flag_fails(self):
  folder=self.extra();self.change(folder/'closeup-capture-report.json',lambda r:r.update(savedSceneBytesPreserved=False))
  with self.assertRaises(ValueError):v4.inspect_extra(self.root,self.contract)
 def test_wrong_native_mesh_count_fails(self):
  folder=self.extra();self.change(folder/'region-1-authoring.json',lambda r:r.update(meshCount=34))
  with self.assertRaises(ValueError):v4.inspect_extra(self.root,self.contract)
 def test_triangle_budget_overflow_fails(self):
  folder=self.extra();self.change(folder/'region-2-authoring.json',lambda r:r.update(triangles=90001))
  with self.assertRaises(ValueError):v4.inspect_extra(self.root,self.contract)
 def test_unlisted_native_output_fails(self):
  folder=self.extra();self.change(folder/'region-3-authoring.json',lambda r:r['generatedFiles'].append(v4.POLISH+'/unexpected.asset'))
  with self.assertRaises(ValueError):v4.inspect_extra(self.root,self.contract)
 def test_arbitrary_extra_export_fails(self):
  folder=self.extra();(folder/'Unity.log').write_text('do not export')
  with self.assertRaises(ValueError):v4.inspect_extra(self.root,self.contract)
 def test_partial_cannot_mislabel_unchanged_source(self):
  snap=self.root/'snapshot.json';snap.write_text(json.dumps({'tracked':'a'*64}))
  with mock.patch.object(v4,'PARTIAL',self.root/'partial'), mock.patch.object(v4.legacy,'SNAPSHOT',snap), mock.patch.object(v4.legacy,'inspect_native_report',return_value='b'*64), mock.patch.object(v4.legacy,'tracked_snapshot',return_value={'tracked':'a'*64}), mock.patch.object(v4.legacy,'inspect_capture') as capture:
   with self.assertRaisesRegex(ValueError,'actual source mismatch'):v4.partial()
   capture.assert_not_called();self.assertFalse((self.root/'partial').exists())
 def test_partial_independently_rejects_empty_difference_list(self):
  snap=self.root/'snapshot.json';snap.write_text(json.dumps({'tracked':'a'*64}))
  with mock.patch.object(v4,'PARTIAL',self.root/'partial'), mock.patch.object(v4.legacy,'SNAPSHOT',snap), mock.patch.object(v4.legacy,'inspect_native_report',return_value='b'*64), mock.patch.object(v4.legacy,'tracked_snapshot',return_value={'tracked':'a'*64}), mock.patch.object(v4.legacy,'protection_differences',return_value=[]), mock.patch.object(v4.legacy,'inspect_capture') as capture:
   with self.assertRaisesRegex(ValueError,'actual nonempty protected-source difference'):v4.partial()
   capture.assert_not_called();self.assertFalse((self.root/'partial').exists())
 def test_native_single_case_has_explicit_finite_timeout(self):
  source=Path(__file__).resolve().parents[1]/'unity/Assets/DesertRV/Tests/EditorRender/JourneyEnvironmentRenderTests.cs'
  text=source.read_text();self.assertEqual(text.count('[Test,'),1);self.assertIn('Timeout(600000)',text);self.assertIn('System.Diagnostics.Stopwatch.StartNew()',text)
 def test_standalone_owner_workflow_has_no_full_import_dependency(self):
  root=Path(__file__).resolve().parents[3];text=(root/'.github/workflows/desert-rv-environment-v4.yml').read_text()
  for value in ['  push:',"github.triggering_actor == 'yangerstar1'",'runs-on: ubuntu-24.04','DesertRV.EditorRenderTests','-force-glcore','environment_v4_evidence.py before','environment_v4_evidence.py package','environment_v4_dispatch.py','path: tasks/desert-rv/evidence/environment-v4/']:self.assertIn(value,text)
  for value in ['download-artifact','three-strict','create_dreamer','self-hosted','-nographics','continue-on-error','contents: write','always()']:self.assertNotIn(value,text)
if __name__=='__main__':unittest.main()
