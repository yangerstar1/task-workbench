#!/usr/bin/env python3
"""Synthetic safety contracts, never substitute these for native screenshots."""
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from environment_evidence import (assert_preserved, valid_generated_name, inspect_png,
    inspect_capture, collect_generated, inspect_native_report, GENERATED, REGIONS, VIEWS, RENDER_TEST)

class EnvironmentContracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def image(self,path,black=False):
        im=Image.new('RGB',(1440,900),(0,0,0) if black else (60,50,20))
        if not black:im.paste((200,180,90),(100,100,600,600))
        im.save(path)
    def capture(self):
        d=self.root/'JourneyEvidence/environment';d.mkdir(parents=True)
        images=[]
        for r in REGIONS:
            for v in VIEWS:
                self.image(d/f'{r}-{v}.png')
                images.append(dict(region=r,view=v,width=1440,height=900,minimum=.1,maximum=.8,sceneHash='a'*32))
        report=dict(status='captured-environment-only-not-gameplay-acceptance',graphicsDeviceType='OpenGLCore',graphicsDeviceName='llvmpipe',bufferSceneTransitionsChecked=3,captureBuffersReleased=True,images=images)
        (d/'capture-report.json').write_text(json.dumps(report))
        (d.parent/'candidate-layout.json').write_text('{"passed":true}')
        return d,report
    def rewrite(self,d,report):(d/'capture-report.json').write_text(json.dumps(report))
    def test_unchanged_source(self):assert_preserved({'a':'one'},{'a':'one'})
    def test_altered_added_removed_originals_fail(self):
        for after in ({'a':'two'},{},{'a':'one','b':'new'}):
            with self.assertRaises(ValueError):assert_preserved({'a':'one'},after)
    def test_white_list_positive(self):
        for n in ['FirstStation.unity','JourneyBootstrap.unity.meta','JourneyContent.asset','Layout-A0BC12.mat.meta','Region-3-Sky.mat']:
            self.assertTrue(valid_generated_name(GENERATED+'/'+n))
        self.assertTrue(valid_generated_name(GENERATED+'.meta'))
    def test_white_list_negative(self):
        for n in ['../Original.unity','secret.txt','Unity.ulf','x.log','nested/FirstStation.unity','FirstStation.cs','Region-4-Sky.mat']:
            self.assertFalse(valid_generated_name(GENERATED+'/'+n))
        self.assertFalse(valid_generated_name('/'+GENERATED+'/FirstStation.unity'))
    def test_actual_png_and_black_rejection(self):
        p=self.root/'image.png';self.image(p);inspect_png(p);self.image(p,True)
        with self.assertRaises(ValueError):inspect_png(p)
    def test_wrong_dimensions_and_format_rejected(self):
        p=self.root/'image.png';Image.new('RGB',(5,5)).save(p)
        with self.assertRaises(ValueError):inspect_png(p)
        Image.new('RGB',(1440,900)).save(p,format='JPEG')
        with self.assertRaises(ValueError):inspect_png(p)
    def test_symlink_rejected(self):
        p=self.root/'real.png';self.image(p);q=self.root/'alias.png';q.symlink_to(p)
        with self.assertRaises(ValueError):inspect_png(q)
    def test_twelve_real_file_contract(self):
        d,r=self.capture();self.assertEqual(len(inspect_capture(self.root)['images']),12)
        self.assertNotIn('path',inspect_capture(self.root)['images'][0])
    def test_null_graphics_fails(self):
        d,r=self.capture();r['graphicsDeviceType']='Null';self.rewrite(d,r)
        with self.assertRaises(ValueError):inspect_capture(self.root)
    def test_wrong_renderer_fails(self):
        d,r=self.capture();r['graphicsDeviceName']='NVIDIA';self.rewrite(d,r)
        with self.assertRaises(ValueError):inspect_capture(self.root)
    def test_duplicate_view_fails(self):
        d,r=self.capture();r['images'][-1]=r['images'][0];self.rewrite(d,r)
        with self.assertRaises(ValueError):inspect_capture(self.root)
    def test_missing_image_fails(self):
        d,r=self.capture();(d/'FirstStation-ground.png').unlink()
        with self.assertRaises(ValueError):inspect_capture(self.root)
    def test_extra_log_fails(self):
        d,r=self.capture();(d/'license.log').write_text('never upload')
        with self.assertRaises(ValueError):inspect_capture(self.root)
    def test_fabricated_range_cannot_override_black_pixels(self):
        d,r=self.capture();self.image(d/'FirstStation-ground.png',True)
        with self.assertRaises(ValueError):inspect_capture(self.root)
    def test_nan_range_fails(self):
        d,r=self.capture();r['images'][0]['minimum']=float('nan');self.rewrite(d,r)
        with self.assertRaises(ValueError):inspect_capture(self.root)
    def test_wrong_layout_fails(self):
        d,r=self.capture();(d.parent/'candidate-layout.json').write_text('{"passed":false}')
        with self.assertRaises(ValueError):inspect_capture(self.root)
    def assets(self):
        folder=self.root/GENERATED;folder.mkdir(parents=True)
        Path(str(folder)+'.meta').write_text('fileFormatVersion: 2\n')
        for n in ['JourneyBootstrap.unity','FirstStation.unity','Scrapyard.unity','NightBeacon.unity','JourneyContent.asset']:
            (folder/n).write_text('%YAML 1.1\n');(folder/(n+'.meta')).write_text('fileFormatVersion: 2\n')
        return folder
    def test_generated_assets_positive(self):self.assets();self.assertEqual(len(collect_generated(self.root)),11)
    def test_generated_missing_meta_fails(self):
        f=self.assets();(f/'FirstStation.unity.meta').unlink()
        with self.assertRaises(ValueError):collect_generated(self.root)
    def test_generated_extra_secret_fails(self):
        f=self.assets();(f/'Unity.ulf').write_text('no')
        with self.assertRaises(ValueError):collect_generated(self.root)
    def test_generated_symlink_fails(self):
        f=self.assets();(f/'FirstStation.unity').unlink();(f/'FirstStation.unity').symlink_to(f/'Scrapyard.unity')
        with self.assertRaises(ValueError):collect_generated(self.root)
    def test_buffer_lifecycle_is_required(self):
        d,r=self.capture();r['captureBuffersReleased']=False;self.rewrite(d,r)
        with self.assertRaises(ValueError):inspect_capture(self.root)
        r['captureBuffersReleased']=True;r['bufferSceneTransitionsChecked']=2;self.rewrite(d,r)
        with self.assertRaises(ValueError):inspect_capture(self.root)
    def test_crc_corruption_rejected(self):
        p=self.root/'image.png';self.image(p);b=bytearray(p.read_bytes());b[-5]^=1;p.write_bytes(b)
        with self.assertRaises(Exception):inspect_png(p)
    def test_capture_cleanup_always_restores_and_checks_sources(self):
        r=Path(__file__).resolve().parents[1]
        s=(r/'unity/Assets/DesertRV/Editor/JourneySceneAuthoring.cs').read_text()
        self.assertIn('if(target) { try { target.Release(); } finally { Object.DestroyImmediate(target); } }',s)
        self.assertIn('try { if(pixels) Object.DestroyImmediate(pixels); }\n                    finally',s)
        self.assertIn('buffersReleased=true;\n                }\n                finally',s)
        self.assertIn('try { RestoreSceneSetup(setup); } finally { VerifyProtectedFiles(protectedFiles); }',s)
    def test_native_inventory_exact(self):
        p=self.root/'result.xml';p.write_text(f'<test-run result="Passed"><test-case fullname="{RENDER_TEST}" result="Passed"/></test-run>')
        inspect_native_report(self.root)
        p.write_text('<test-run result="Passed"><test-case fullname="wrong" result="Passed"/></test-run>')
        with self.assertRaises(ValueError):inspect_native_report(self.root)
    def test_workflow_is_separate_owner_manual_standard_runner(self):
        r=Path(__file__).resolve().parents[3];s=(r/'.github/workflows/desert-rv-environment.yml').read_text()
        for x in ['workflow_dispatch:',"github.triggering_actor == 'yangerstar1'",'runs-on: ubuntu-24.04','-force-glcore','DesertRV.EditorRenderTests','environment_evidence.py before','environment_evidence.py package','sha256:17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264']:
            self.assertIn(x,s)
        for x in ['enableGpu','--gpus','self-hosted','continue-on-error','-nographics','actions/cache','contents: write']:
            self.assertNotIn(x,s)
        upload=s.split('name: Upload only sanitized environmental evidence')[1]
        self.assertIn('path: tasks/desert-rv/evidence/environment/',upload)
        self.assertNotIn('always()',upload)

if __name__=='__main__':unittest.main()
