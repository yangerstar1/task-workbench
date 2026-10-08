#!/usr/bin/env python3
"""Synthetic safety contracts, never substitute these for native screenshots."""
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from environment_evidence import (assert_preserved, valid_generated_name, inspect_png,
    inspect_capture, collect_generated, inspect_native_report, GENERATED, REGIONS, VIEWS, RENDER_TEST,
    package_unaccepted, protection_differences, FAILED_STATUS, IMAGES, write_protection_diagnostic, validated_unity_dependencies, CLEARANCE_FILES, inspect_clearance, CAMERAS)

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
                images.append(dict(region=r,view=v,cameraModel=CAMERAS[v][0],fieldOfView=CAMERAS[v][1],width=1440,height=900,minimum=.1,maximum=.8,sceneHash='a'*32))
        report=dict(status='captured-environment-only-not-gameplay-acceptance',graphicsDeviceType='OpenGLCore',graphicsDeviceName='llvmpipe',bufferSceneTransitionsChecked=3,captureBuffersReleased=True,images=images)
        (d/'capture-report.json').write_text(json.dumps(report))
        (d.parent/'candidate-layout.json').write_text(json.dumps(dict(passed=True,mode='candidate-layout-only-not-gameplay-approval',sceneDependencyHashes=['b'*32]*4)))
        for region in (1,2,3):
            zones=['driving-corridor','vehicle-spawn','dismount','cabin-workbench']
            if region<3:zones.append('salvage-access')
            if region>1:zones.append('power-access')
            (d.parent/f'clearance-region-{region}.json').write_text(json.dumps(dict(region=region,passed=True,checkedZones=zones,distantMeshes=4)))
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
    def test_eighteen_real_file_contract(self):
        d,r=self.capture();self.assertEqual(len(inspect_capture(self.root)['images']),18)
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
    def test_unaccepted_export_is_exact_and_marked_failed(self):
        self.capture();out=self.root/'partial'
        package_unaccepted(self.root,out,{'Assets/a.mat':'a'*64},{'Assets/a.mat':'b'*64},{'commit':'c'*40})
        self.assertEqual({p.name for p in out.iterdir()},IMAGES|CLEARANCE_FILES|{'capture-report.json','candidate-layout.json','protected-source-failure.json','SHA256SUMS.json'})
        for name in ['capture-report.json','candidate-layout.json','protected-source-failure.json','SHA256SUMS.json']:
            self.assertEqual(json.loads((out/name).read_text())['status'],FAILED_STATUS)
        d=json.loads((out/'protected-source-failure.json').read_text());self.assertFalse(d['accepted'])
    def test_unaccepted_export_cannot_bypass_no_mismatch(self):
        self.capture()
        with self.assertRaises(ValueError):package_unaccepted(self.root,self.root/'partial',{'a':'a'*64},{'a':'a'*64},{})
    def test_unaccepted_export_still_rejects_black_pixels(self):
        d,r=self.capture();self.image(d/'FirstStation-ground.png',True)
        with self.assertRaises(ValueError):package_unaccepted(self.root,self.root/'partial',{'a':'a'*64},{'a':'b'*64},{})
        self.assertFalse((self.root/'partial').exists())
    def test_unaccepted_export_rejects_missing_layout_hash(self):
        d,r=self.capture();(d.parent/'candidate-layout.json').write_text('{"passed":true}')
        with self.assertRaises(ValueError):package_unaccepted(self.root,self.root/'partial',{'a':'a'*64},{'a':'b'*64},{})
    def test_diagnostic_rejects_unsafe_paths_and_nonhash_contents(self):
        for p in ['/secret','../secret','a\nsecret']:
            with self.assertRaises(ValueError):protection_differences({p:'a'*64},{p:'b'*64})
        with self.assertRaises(ValueError):protection_differences({'a':'password'},{'a':'b'*64})
    def test_partial_workflow_is_failure_only(self):
        r=Path(__file__).resolve().parents[3];w=(r/'.github/workflows/desert-rv-environment.yml').read_text()
        self.assertIn("if: failure() && steps.native.outcome == 'success' && steps.package.outcome == 'failure'",w)
        self.assertIn("if: failure() && steps.partial.outcome == 'success'",w)
        self.assertIn('path: tasks/desert-rv/evidence/environment-unaccepted/',w)
        self.assertNotIn('continue-on-error',w)
    def test_source_diagnosis_survives_absent_or_corrupt_images(self):
        out=self.root/'diagnostic'
        write_protection_diagnostic(out,{'Assets/a.mat':'a'*64},{'Assets/a.mat':'b'*64},{'commit':'c'*40})
        self.assertEqual({p.name for p in out.iterdir()},{'protected-source-failure.json'})
        report=json.loads((out/'protected-source-failure.json').read_text())
        self.assertEqual(report['status'],FAILED_STATUS)
        self.assertEqual(report['changedFiles'],[dict(path='Assets/a.mat',beforeSha256='a'*64,afterSha256='b'*64)])
    def test_source_diagnosis_upload_precedes_partial_validation(self):
        r=Path(__file__).resolve().parents[3];w=(r/'.github/workflows/desert-rv-environment.yml').read_text()
        self.assertLess(w.index('name: Upload only independent source hash diagnosis'),w.index('name: Preserve unaccepted pixels'))
        self.assertIn("if: failure() && steps.source_diag.outputs.present == 'true'",w)
    def test_official_package_metadata_positive(self):
        for source_name in ('builtin','registry'):
            e=dict(version='1.6.0',depth=0,source=source_name,dependencies={'com.unity.ext.nunit':'2.0.5'})
            if source_name=='registry':e['url']='https://packages.unity.com'
            out=validated_unity_dependencies({'dependencies':{'com.unity.test-framework':e}},True)
            self.assertEqual(out['com.unity.test-framework']['version'],'1.6.0')
        self.assertEqual(validated_unity_dependencies({'dependencies':{'com.unity.test-framework':'1.6.0'}}),{'com.unity.test-framework':'1.6.0'})
    def test_official_linux_sdk_underscores_are_preserved(self):
        names=['com.unity.sdk.linux-arm64','com.unity.sdk.linux-x86_64','com.unity.toolchain.linux-x86_64-linux','com.unity.sysroot.base']
        value={'dependencies':{name:'1.1.0' for name in names}}
        self.assertEqual(set(validated_unity_dependencies(value)),set(names))
        for name in names:
            lock={'dependencies':{name:dict(version='1.1.0',depth=0,source='registry',dependencies={},url='https://packages.unity.com')}}
            self.assertIn(name,validated_unity_dependencies(lock,True))
    def test_package_diagnostic_rejects_paths_tokens_and_foreign_packages(self):
        for version in ('file:../secret','https://private.example/token','git+https://example.com/a','Bearer secret'):
            with self.assertRaises(ValueError):validated_unity_dependencies({'dependencies':{'com.unity.test-framework':version}})
        with self.assertRaises(ValueError):validated_unity_dependencies({'dependencies':{'org.private.package':'1.0.0'}})
    def test_package_diagnostic_rejects_private_registry_and_extra_fields(self):
        good=dict(version='1.6.0',depth=0,source='registry',dependencies={},url='https://packages.unity.com')
        for patch in ({'url':'https://private.example'},{'token':'secret'},{'source':'git'},{'depth':-1},{'url':'https://packages.unity.com/?token=x'}):
            e=dict(good,**patch)
            with self.assertRaises(ValueError):validated_unity_dependencies({'dependencies':{'com.unity.test-framework':e}},True)
        with self.assertRaises(ValueError):validated_unity_dependencies({'dependencies':{},'scopedRegistries':[]})
    def test_all_region_clearance_required(self):
        self.capture();self.assertEqual(len(inspect_clearance(self.root)),3)
        p=self.root/'JourneyEvidence/clearance-region-2.json';p.unlink()
        with self.assertRaises(ValueError):inspect_clearance(self.root)
    def test_clearance_failures_and_unknown_zones_rejected(self):
        self.capture();p=self.root/'JourneyEvidence/clearance-region-1.json';original=json.loads(p.read_text())
        for patch in ({'passed':False},{'region':2},{'distantMeshes':0},{'checkedZones':['token']},{'extra':'secret'}):
            p.write_text(json.dumps(dict(original,**patch)))
            with self.assertRaises(ValueError):inspect_clearance(self.root)
    def test_editor_camera_provenance_and_fov_are_required(self):
        d,r=self.capture();r['images'][0]['cameraModel']='PlayMode';self.rewrite(d,r)
        with self.assertRaises(ValueError):inspect_capture(self.root)
        r['images'][0]['cameraModel']='regression-editor';r['images'][0]['fieldOfView']=66;self.rewrite(d,r)
        with self.assertRaises(ValueError):inspect_capture(self.root)
    def test_missing_motor_reference_view_rejected(self):
        d,r=self.capture();(d/'Scrapyard-motor-driving-editor.png').unlink()
        with self.assertRaises(ValueError):inspect_capture(self.root)
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
