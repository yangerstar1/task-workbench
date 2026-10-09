"""Synthetic security/schema fixtures. These files never claim real Unity evidence.

Run beside strict_output.py (or put its directory on PYTHONPATH). Every native XML,
FBX marker and rendered-looking image below is explicitly a synthetic test input.
"""
import copy
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from package_test_fixture import install_package_snapshot
from PIL import Image, ImageDraw
import yaml
from test_urp_material_metadata import ASSET_VERSION_YAML
import strict_output as strict
import weapon_output as w

CONTRACT = Path(__file__).parent/'contracts/weapon-combined-strict-37849553855.json'
PRODUCTION_EDITOR = Path(__file__).parents[2]/'unity/Assets/DesertRV/Editor'


class WeaponExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='weapon-synthetic-test-')
        self.root = Path(self.tmp.name)/'desert-rv'; self.project = self.root/'unity'; self.out = self.root/'safe-export'
        self.c = json.loads(CONTRACT.read_text()); self.c['id']='weapon-synthetic-fixture'
        self.prefix = 'Assets/DesertRV/CandidateArtImports/'+self.c['id']; self.folder=self.project/self.prefix
        self.ev=self.project/'JourneyEvidence/CandidateArt';self.ev.mkdir(parents=True)
        self.guid=0
        self.write(self.prefix+'/Source/weapon_hands.fbx',b'EXPLICITLY SYNTHETIC FBX SECURITY TEST; NOT A REAL NATIVE ASSET')
        self.c['files'][0]['sha256']=w.sha(self.folder/'Source/weapon_hands.fbx')
        self.meta(self.folder/'Source/weapon_hands.fbx')
        self.save_contract()
        for name in ('Candidate.prefab','Candidate.controller'):
            self.write(self.prefix+'/'+name,'%YAML 1.1\n--- !u!1 &1\nSyntheticFixture: {}\n');self.meta(self.folder/name)
        for path in (self.folder,self.folder.parent,self.folder/'Source',self.folder/'Materials'):
            self.meta(path)
        self.meta(self.folder/'contract.json')
        for i,m in enumerate(self.c['materials']):
            path=self.folder/f'Materials/Material_{i:02}.mat';self.material(i,m);self.meta(path)
        for path in w.ORIGINAL_SCRIPTS:
            self.write(path,'// Synthetic protected original script fixture.\n');self.meta(self.project/path)
        self.imp=dict(mode='STRICT_BINDING',scope='FULL_CANDIDATE',kind='weapon',status='candidate-structure-imported-unreviewed',
            contractSha256=w.sha(self.project/'CandidateImportInput/contract.json'),prefab=self.prefix+'/Candidate.prefab',
            dependencyHash='a'*32,runUrl=self.c['runUrl'],sourceCommit=self.c['sourceCommit'],artifactName=self.c['artifactName'],
            artifactSha256=self.c['artifactSha256'],candidateOnly=True,visualReviewed=False,gameplayReviewed=False,
            importedAnimatorPaths=[''],rootCurves=[],derivedTextures=[],failures=[],stillRequired=w.IMPORT_LIMITS.copy(),
            clips=[dict(row,frameRate=60,floatBindings=100,objectBindings=0) for row in self.c['clips']])
        self.imp['dependencies']=[self.prefix+'/'+name for name in ['Candidate.prefab','Candidate.controller','Source/weapon_hands.fbx']
            +[f'Materials/Material_{i:02}.mat' for i in range(7)]]+sorted(w.ORIGINAL_SCRIPTS)+[w.PACKAGE_SHADER, w.PACKAGE_ASSET_VERSION]
        self.imp['weaponCalibration']=self.calibration()
        self.imp['muzzle']=dict(calibratedForScene=False,sourceAxisDerived=True,forwardAdapterPath=self.c['bindings']['muzzle']+'/CandidateShotMuzzleAxis',
            forwardAdapterWorld=dict(x=0,y=0,z=-1),sourceBoneLocalForwardAxis='+Y',sourceHead=dict(x=0,y=.35,z=.072),
            sourceTail=dict(x=0,y=.385,z=.072),importedWorldPosition=dict(x=0,y=.072,z=-.35),importedBasisX=dict(x=1,y=0,z=0),
            importedBasisY=dict(x=0,y=0,z=-1),importedBasisZ=dict(x=0,y=1,z=0),gate=w.MUZZLE_GATE)
        self.cap=dict(graphicsDeviceType='OpenGLCore',graphicsDeviceName='llvmpipe (LLVM synthetic fixture)',status='captured-unreviewed',
            scope='real-Animator-pose-diagnostics-only',prefab=self.imp['prefab'],visualAccepted=False,gameplayAccepted=False,
            armoredAttackLoopIntent=w.LOOP_INTENT,notCovered=w.CAPTURE_LIMITS.copy(),frames=[],
            neutralRoot=dict(position=w.ZERO.copy(),rotation=dict(x=0,y=0,z=0,w=1),scale=w.ONE.copy(),
                renderers=[dict(path='weapon_hands/Forged_Main_Housing',worldCenter=dict(x=.4,y=.5,z=.6),worldExtents=dict(x=.4,y=.5,z=.6))]),
            neutralMeshWorldMin=w.ZERO.copy(),neutralMeshWorldMax=dict(x=.8,y=1,z=1.2),neutralMeshWorldSize=dict(x=.8,y=1,z=1.2))
        self.cap['weapon']=dict(status='imported-arm-count-mechanics-passed-unreviewed',mechanicsPassed=True,
            gameplayAccepted=False,visualAccepted=False,sceneCalibrated=False,scope=w.MECHANICS_SCOPE,sampleRateHz=200,
            maxWristGapWorld=.0002,maxShoulderDriftWorld=.000001,maxTargetDriftWorld=.000001,samples=[],failures=[])
        pitch=dict(x=.006,y=.012,z=-.004)
        for state,t,before,added,position,rotation,label in w.sample_schedule():
            ik=state=='Reload';strip={k:v*before/100 if ik else 0 for k,v in pitch.items()}
            sample=dict(state=state,animatorPoseSha256=hashlib.sha256(f'synthetic {state} {t}'.encode()).hexdigest(),normalized=t,
                loadedBefore=before,plannedAdded=added,ikApplied=ik,poseAccepted=True,incomingLocalOffset=strip,
                leftLocalOffset={k:v*w.grip_weight(t) for k,v in strip.items()},worldPitch=w.rotate(rotation,pitch),
                subjectWorldPosition=position.copy(),subjectWorldRotation=rotation.copy())
            for side in ('left','right'):
                arm=self.imp['weaponCalibration'][side]; upper=arm['upperLengthRig']*100; fore=arm['foreLengthRig']*100
                sample[side]=dict(solved=ik,measured=True,measurementsFinite=True,reason=None if ik else 'Unmodified Animator pose observed; no IK executed.',
                    upperLength=upper,foreLength=fore,expectedUpperLength=upper,expectedForeLength=fore,wristGap=.0002,
                    shoulderDrift=.000001,targetDrift=.000001 if ik else 0,targetDistance=.5)
            self.cap['weapon']['samples'].append(sample)
            if label:
                i=len(self.cap['frames']);name=f'frame-{i:04}.png';p=self.ev/name
                # Asymmetric, independently changing pixels: row/axis swaps cannot self-validate.
                image=Image.new('RGB',(960,540),(31,43,59));draw=ImageDraw.Draw(image)
                draw.polygon([(70+i,35),(840,210+i),(290,480)],fill=(170+i,81,47+i))
                draw.rectangle((100,150,130,440),fill=(21,180,230));image.save(p)
                self.cap['frames'].append(dict(image=name,requestedState=label,imageSha256=w.sha(p),
                    meshPoseSha256=hashlib.sha256(('synthetic-mesh-'+label).encode()).hexdigest(),advanceSeconds=0,
                    normalizedTime=t,worldMinY=0,groundReferenceY=0,rootLocalPositionDelta=0,rootLocalAngleDelta=0,rootLocalScaleDelta=0,
                    stateHash=1,sampledVertices=900,outsideViewportVertices=0,behindCameraVertices=0,belowReferenceVertices=0,
                    transitioning=False,groundDiagnosticApplicable=False,rootLocalPosition=w.ZERO.copy(),rootLocalScale=w.ONE.copy(),
                    rootLocalRotation=dict(x=0,y=0,z=0,w=1),meshWorldMin=w.ZERO.copy(),meshWorldMax=dict(x=.8,y=1,z=1.2),
                    meshWorldSize=dict(x=.8,y=1,z=1.2),meshSizeRatioToNeutral=w.ONE.copy()))
        install_package_snapshot(self.project)
        self.rehash_dependencies()
        self.native=self.root/'artifacts/candidate-art/results.xml';self.native.parent.mkdir(parents=True)
        self.names=sorted(__import__('candidate_native_cases').NATIVE_NAMES)
        self.native.write_text('<test-run result="Passed">'+''.join('<test-case fullname="'+name+'" result="Passed"/>' for name in self.names)+'</test-run>')
        self.flush()

    def tearDown(self): self.tmp.cleanup()

    def write(self,relative,content):
        p=self.project/relative;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(content if isinstance(content,bytes) else content.encode());return p

    def meta(self,path,texture=False):
        self.guid+=1;p=Path(str(path)+'.meta');p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text('fileFormatVersion: 2\nguid: '+f'{self.guid:032x}'+'\n'+
            ('TextureImporter:\n  mipmaps:\n    sRGBTexture: 0\n  isReadable: 1\n  textureType: 0\n' if texture else 'DefaultImporter: {}\n'))

    def save_contract(self):
        data=json.dumps(self.c);self.write('CandidateImportInput/contract.json',data);self.write(self.prefix+'/contract.json',data)

    def material(self,index,m,texture_guid=None):
        asset=dict(m_Name=m['sourceName']+'_Candidate',m_Shader=dict(fileID=4800000,guid=w.URP_LIT_GUID,type=3),
            m_SavedProperties=dict(m_Colors=[{'_BaseColor':m['baseColor']}],
                m_Floats=[{'_Metallic':m['metallic']},{'_Smoothness':m['smoothness']},{'_Cull':0}],m_TexEnvs=[]))
        if texture_guid:
            asset['m_SavedProperties']['m_TexEnvs']=[{key:dict(m_Texture=dict(fileID=2800000,guid=texture_guid,type=3))}
                for key in ('_MetallicGlossMap','_OcclusionMap')]
        self.write(self.prefix+f'/Materials/Material_{index:02}.mat','%YAML 1.1\n--- !u!21 &2100000\n'+yaml.safe_dump({'Material':asset},sort_keys=False)+ASSET_VERSION_YAML)

    def calibration(self):
        source_hash=self.c['files'][0]['sha256']
        evidence=f'Unity6000.3.19f1: {self.prefix}/Source/weapon_hands.fbx sha256={source_hash} neutral=Idle seconds=0 discovery={w.DISCOVERY_SHA}'
        result=dict(neutralState='Idle',neutralPoseEvidence=evidence,sourceSha256=source_hash,rigRoot=w.RIG,neutralTimeSeconds=0,
            rigWorldScale=100,positionToleranceWorld=.001,numericToleranceWorld=.00001,sceneCalibrated=False,visualApproved=False,materials=[])
        for side in ('left','right'):
            upper=self.c['weapon'][side+'UpperSource'];fore=self.c['weapon'][side+'ForeSource']
            result[side]=dict(self.c['weapon'][side],calibrated=True,upperLengthRig=upper*.01,foreLengthRig=fore*.01,
                sourceUpperLength=upper,sourceForeLength=fore,sourceToRigScale=.01,upperAxisLocal=dict(x=0,y=1,z=0),
                foreAxisLocal=dict(x=0,y=1,z=0),poleRigLocal=dict(x=1,y=0,z=0),shoulderLocal=dict(x=.003,y=-.0034,z=.0027),
                elbowLocal=dict(x=0,y=upper*.01,z=0),tipLocal=dict(x=0,y=fore*.01,z=0),upperScale=w.ONE.copy(),foreScale=w.ONE.copy(),
                upperBindRotation=dict(x=0,y=0,z=0,w=1),foreBindRotation=dict(x=0,y=0,z=0,w=1),neutralPoseEvidence=evidence)
        for i,m in enumerate(self.c['materials']):
            result['materials'].append(dict(sourceName=m['sourceName'],materialPath=self.prefix+f'/Materials/Material_{i:02}.mat',
                shader='Universal Render Pipeline/Lit',actualName=m['sourceName']+'_Candidate',materialGuid=w._meta_guid(self.folder/f'Materials/Material_{i:02}.mat'),materialLocalId=2100000,expectedColor=m['baseColor'].copy(),actualColor=m['baseColor'].copy(),
                expectedMetallic=m['metallic'],actualMetallic=m['metallic'],expectedSmoothness=m['smoothness'],actualSmoothness=m['smoothness'],actualCull=0))
        return result

    def rehash_dependencies(self):
        self.imp['dependencySha256']=w.dependency_digest(self.project,self.imp['dependencies'])
        self.cap['dependencySha256']=self.imp['dependencySha256']

    def flush(self,pretty=False):
        for name,value in [('import-report.json',self.imp),('capture-report.json',self.cap)]:
            (self.ev/name).write_text(json.dumps(value,indent=4 if pretty else None))

    def run_export(self,flush=True,**kwargs):
        if flush:self.flush()
        with patch.dict(os.environ,{'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'123'}):
            return w.export(self.root,self.out,**kwargs)

    def rejected(self,code=None,**kwargs):
        with self.assertRaises(w.StrictError):self.run_export(**kwargs)
        receipt=json.loads((self.out/'receipt.json').read_text())
        self.assertEqual(receipt['status'],'FAILED_NOT_ACCEPTED');self.assertFalse(receipt['approved'])
        self.assertEqual(list(self.out.iterdir()),[self.out/'receipt.json'])
        self.assertNotIn('fixture-secret',(self.out/'receipt.json').read_text())
        self.assertFalse(list(self.out.parent.glob('.weapon-safe-*')))
        if code:self.assertEqual(receipt['errorCode'],code)

    def test_persisted_display_name_is_observed_not_source_identity(self):
        # Emulate a valid native filename-derived display name without guessing it in production.
        p=self.folder/'Materials/Material_00.mat';old=self.c['materials'][0]['sourceName']+'_Candidate'
        p.write_text(p.read_text().replace('m_Name: '+old,'m_Name: Material_00'))
        self.imp['weaponCalibration']['materials'][0]['actualName']='Material_00'
        self.rehash_dependencies();self.run_export()
    def test_observed_name_must_match_disk(self):
        self.imp['weaponCalibration']['materials'][0]['actualName']='same-name-impostor';self.rejected('WEAPON_MATERIAL_ASSET')
    def test_material_guid_identity_cannot_be_spoofed(self):
        self.imp['weaponCalibration']['materials'][0]['materialGuid']='f'*32;self.rejected('WEAPON_MATERIAL_PERSISTENT_IDENTITY')
    def test_material_local_id_must_match_actual_document(self):
        self.imp['weaponCalibration']['materials'][0]['materialLocalId']=2100001;self.rejected('WEAPON_MATERIAL_LOCAL_ID')
    def test_matching_name_does_not_excuse_wrong_material_path(self):
        self.imp['weaponCalibration']['materials'][0]['materialPath']=self.prefix+'/Materials/Material_01.mat';self.rejected('WEAPON_MATERIAL_READBACK')
    def test_material_identity_native_case_is_required(self):
        self.native.write_text(self.native.read_text().replace(w.MATERIAL_IDENTITY_CASE,'Synthetic.UnrecognizedCase'))
        self.rejected()
    def test_staging_unlisted_file_cannot_escape(self):
        original=w.shutil.copyfile
        def inject(src,dest,*args,**kwargs):
            result=original(src,dest,*args,**kwargs)
            for parent in Path(dest).parents:
                if parent.name.startswith('.weapon-safe-'):
                    (parent/'unlisted.log').write_text('SECRET');break
            return result
        with patch.object(w.shutil,'copyfile',inject):self.rejected('STRICT_STAGING_ALLOWLIST')
    def test_full_synthetic_export_is_explicitly_unaccepted(self):
        result=self.run_export();self.assertEqual((result['images'],result['weaponSamples'],result['nativeCases']),(25,4463,w.NATIVE_CASES))
        for key in ('approved','calibratedForScene','visualApproved','gameplayAccepted'):self.assertIs(result[key],False)
        self.assertEqual((result['denseSamples'],result['worldSamples'],result['imageSamples']),(4303,135,25))
        for row in result['files']:self.assertEqual(w.sha(self.out/row['path']),row['sha256'])
        self.assertNotIn('results.xml',[row['path'] for row in result['files']])

    def test_readable_large_native_style_json(self):
        self.flush(pretty=True);self.assertGreater((self.ev/'capture-report.json').stat().st_size,8*1024**2)
        self.assertEqual(self.run_export(flush=False)['weaponSamples'],4463)

    def test_exact_schedule(self):
        rows=w.sample_schedule();self.assertEqual(len(rows),4463)
        self.assertEqual(sum(row[0]!='Reload' for row in rows),10)
        self.assertEqual(len({row[6] for row in rows if row[6]}),25)
        self.assertEqual(rows[4302][2:4],(3,5));self.assertEqual(rows[4438][0],'Idle')

    def test_export_scope_matches_real_production_diagnostics(self):
        source=(PRODUCTION_EDITOR/'CandidateWeaponDiagnostics.cs').read_text()
        scopes=re.findall(r'public\s+string\s+scope\s*=\s*"([^"\r\n]*)"\s*;',source)
        self.assertEqual(scopes,[w.MECHANICS_SCOPE])
        self.assertIn('result.status="imported-arm-count-mechanics-passed-unreviewed"',source)
        self.assertIn('reason="Unmodified Animator pose observed; no IK executed."',source)

    def test_failed_native(self):self.rejected('STRICT_NATIVE_FAILED',native='failure')
    def test_failed_original_tracked(self):self.rejected('STRICT_PROTECTED_SOURCE_FAILED',protected='failure')
    def test_missing_native_policy_case(self):
        self.native.write_text('<test-run result="Passed"><test-case fullname="'+self.names[0]+'" result="Passed"/></test-run>')
        self.rejected('STRICT_NATIVE_FAILED')
    def test_duplicate_native_xml(self):
        (self.native.parent/'extra.xml').write_bytes(self.native.read_bytes());self.rejected('STRICT_NATIVE_COUNT')
    def test_failed_native_case(self):
        self.native.write_text(self.native.read_text().replace('result="Passed"/>','result="Failed"/>',1));self.rejected('STRICT_NATIVE_FAILED')
    def test_old_four_native_cases_are_not_enough(self):
        self.native.write_text(self.native.read_text().replace('<test-case fullname="'+w.EMISSION_CASE+'" result="Passed"/>',''))
        self.rejected('STRICT_NATIVE_FAILED')
    def test_stale_native_case_shared_helper_cannot_misreport_five(self):
        self.native.write_text(self.native.read_text().replace('<test-case fullname="'+w.EMISSION_CASE+'" result="Passed"/>',''))
        with patch.object(w,'native_report',return_value=w.sha(self.native)):self.rejected('WEAPON_NATIVE_VERSION')
    def test_source_contract_missing_field(self):
        self.c['weapon'].pop('sourceToRigScale');self.save_contract();self.rejected('STRICT_SCHEMA_MISMATCH')
    def test_contract_approval_extra(self):
        self.c['approved']=True;self.save_contract();self.rejected('STRICT_SCHEMA_MISMATCH')
    def test_contract_wrong_unit_policy(self):
        self.c['weapon']['positionToleranceRig']=.001;self.save_contract();self.rejected('WEAPON_SOURCE_UNITS')
    def test_contract_wrong_discovery(self):
        self.c['weapon']['discoveryReportSha256']='e'*64;self.save_contract();self.rejected('WEAPON_DISCOVERY_PIN')
    def test_contract_path_escape(self):
        self.c['files'][0]['file']='../secret.fbx';self.save_contract();self.rejected('WEAPON_INPUT_ALLOWLIST')
    def test_contract_case_collision(self):
        self.c['files'].append(dict(file='WEAPON_HANDS.fbx',sha256='a'*64));self.save_contract();self.rejected('WEAPON_INPUT_ALLOWLIST')
    def test_duplicate_json_key(self):
        self.write('CandidateImportInput/contract.json','{"mode":"STRICT_BINDING","mode":"DISCOVERY_ONLY"}');self.rejected('STRICT_DUPLICATE_JSON_KEY')
    def test_import_approval(self):self.imp['visualReviewed']=True;self.rejected('WEAPON_APPROVAL_FORBIDDEN')
    def test_calibration_approval(self):self.imp['weaponCalibration']['sceneCalibrated']=True;self.rejected('WEAPON_APPROVAL_FORBIDDEN')
    def test_muzzle_scene_approval(self):self.imp['muzzle']['calibratedForScene']=True;self.rejected('WEAPON_MUZZLE_APPROVAL_OR_AXIS')
    def test_capture_gameplay_approval(self):self.cap['weapon']['gameplayAccepted']=True;self.rejected('WEAPON_APPROVAL_FORBIDDEN')
    def test_calibration_path_is_actual_string(self):
        self.imp['weaponCalibration']['left']['upperArm']={'instanceID':17};self.rejected('WEAPON_CALIBRATION_PATHS')
    def test_calibration_wrong_rig_scale(self):self.imp['weaponCalibration']['rigWorldScale']=1;self.rejected('WEAPON_RIG_SCALE')
    def test_calibration_world_tolerance(self):self.imp['weaponCalibration']['positionToleranceWorld']=.1;self.rejected('WEAPON_WORLD_TOLERANCE')
    def test_calibration_bad_source_length(self):self.imp['weaponCalibration']['left']['upperLengthRig']=.3;self.rejected('WEAPON_CALIBRATION_LENGTH')
    def test_calibration_zero_quaternion(self):self.imp['weaponCalibration']['left']['foreBindRotation']['w']=0;self.rejected('STRICT_INVALID_QUATERNION')
    def test_calibration_stretched_arm(self):self.imp['weaponCalibration']['right']['upperScale']['x']=1.1;self.rejected('WEAPON_ARM_SCALE')
    def test_wrong_muzzle_forward(self):self.imp['muzzle']['forwardAdapterWorld']=dict(x=0,y=0,z=1);self.rejected('WEAPON_MUZZLE_FORWARD')
    def test_wrong_source_muzzle_observation(self):self.imp['muzzle']['importedWorldPosition']['z']=.35;self.rejected('WEAPON_MUZZLE_SOURCE_OBSERVATION')
    def test_material_count(self):self.imp['weaponCalibration']['materials'].pop();self.rejected('WEAPON_MATERIAL_READBACK_COUNT')
    def test_material_report_color(self):self.imp['weaponCalibration']['materials'][0]['actualColor']['r']=.9;self.rejected('WEAPON_MATERIAL_COLOR')
    def test_material_disk_differs_despite_rehashed_dependencies(self):
        p=self.folder/'Materials/Material_00.mat';p.write_text(p.read_text().replace('_Cull: 0','_Cull: 2'));self.rehash_dependencies();self.rejected('WEAPON_MATERIAL_ASSET_VALUES')
    def test_unknown_material_guid_dependency(self):
        p=self.folder/'Candidate.prefab';p.write_text(p.read_text()+'  reference: {guid: abcdefabcdefabcdefabcdefabcdefab}\n')
        self.rehash_dependencies();self.rejected('WEAPON_DEPENDENCY_GUID_CLOSURE')
    def test_required_script_dependency_missing(self):
        self.imp['dependencies'].remove('Assets/DesertRV/Runtime/WeaponArmReach.cs');self.rehash_dependencies();self.rejected('WEAPON_REQUIRED_DEPENDENCIES')
    def test_source_dependency_hash_mutation(self):
        (self.folder/'Source/weapon_hands.fbx').write_bytes(b'changed');self.rejected('WEAPON_DEPENDENCY_HASH')
    def test_source_digest_mismatch_even_after_dependency_rehash(self):
        (self.folder/'Source/weapon_hands.fbx').write_bytes(b'changed');self.rehash_dependencies();self.rejected('WEAPON_GENERATED_SOURCE')
    def test_bad_dependency_path(self):
        self.imp['dependencies'].append('../fixture-secret');self.rejected('STRICT_DEPENDENCY_PATH')
    def test_missing_dependency_meta(self):
        Path(str(self.folder/'Candidate.prefab')+'.meta').unlink();self.rejected('STRICT_UNSAFE_FILE')
    def test_extra_report_field(self):self.imp['rawLogs']='fixture-secret';self.rejected('STRICT_SCHEMA_MISMATCH')
    def test_missing_neutral_mesh_evidence(self):self.cap.pop('neutralMeshWorldSize');self.rejected('STRICT_SCHEMA_MISMATCH')
    def test_missing_frame_geometry(self):self.cap['frames'][0].pop('meshWorldSize');self.rejected('STRICT_SCHEMA_MISMATCH')
    def test_missing_mechanics_samples(self):self.cap['weapon']['samples'].pop();self.rejected('WEAPON_SAMPLE_COUNT')
    def test_duplicate_sample_replaces_world_case(self):
        self.cap['weapon']['samples'][4350]=copy.deepcopy(self.cap['weapon']['samples'][0]);self.rejected('WEAPON_SAMPLE_INVENTORY')
    def test_wrong_dense_timestamp(self):self.cap['weapon']['samples'][44]['normalized']+=.001;self.rejected('WEAPON_SAMPLE_INVENTORY')
    def test_wrong_count(self):self.cap['weapon']['samples'][0]['plannedAdded']=11;self.rejected('WEAPON_SAMPLE_INVENTORY')
    def test_reload_must_apply_ik(self):self.cap['weapon']['samples'][0]['ikApplied']=False;self.rejected('WEAPON_IK_POLICY')
    def test_idle_must_not_apply_ik(self):self.cap['weapon']['samples'][4438]['ikApplied']=True;self.rejected('WEAPON_IK_POLICY')
    def test_idle_must_not_claim_solver_pass(self):self.cap['weapon']['samples'][4438]['left']['solved']=True;self.rejected('WEAPON_SAMPLE_DIAGNOSTICS_STATE')
    def test_fire_pose_rejected(self):self.cap['weapon']['samples'][4443]['poseAccepted']=False;self.rejected('WEAPON_IK_POLICY')
    def test_idle_gap_cannot_be_skipped(self):self.cap['weapon']['samples'][4438]['left']['wristGap']=.002;self.rejected('WEAPON_SAMPLE_METRIC_LIMIT')
    def test_reload_gap_cannot_be_skipped(self):self.cap['weapon']['samples'][0]['right']['wristGap']=.002;self.rejected('WEAPON_SAMPLE_METRIC_LIMIT')
    def test_unmeasured_finite_zero_is_not_evidence(self):self.cap['weapon']['samples'][0]['left']['measured']=False;self.rejected('WEAPON_SAMPLE_DIAGNOSTICS_STATE')
    def test_nan_json_rejected(self):self.cap['weapon']['samples'][0]['left']['wristGap']=float('nan');self.rejected('STRICT_NONFINITE_JSON')
    def test_boolean_metric_rejected(self):self.cap['weapon']['samples'][0]['left']['wristGap']=False;self.rejected('WEAPON_SAMPLE_NUMBER')
    def test_metric_reason_cannot_leak_raw_log(self):self.cap['weapon']['samples'][0]['left']['reason']='fixture-secret';self.rejected('WEAPON_SAMPLE_DIAGNOSTICS_STATE')
    def test_wrong_segment_measurement(self):self.cap['weapon']['samples'][0]['left']['upperLength']+=.01;self.rejected('WEAPON_SAMPLE_FIXED_LENGTH')
    def test_wrong_metric_summary(self):self.cap['weapon']['maxWristGapWorld']=0;self.rejected('WEAPON_METRIC_SUMMARY')
    def test_wrong_world_translation(self):self.cap['weapon']['samples'][4303]['subjectWorldPosition']['y']=1;self.rejected('WEAPON_WORLD_SAMPLE_TRANSFORM')
    def test_wrong_world_rotation(self):self.cap['weapon']['samples'][4318]['subjectWorldRotation']=dict(x=0,y=0,z=0,w=1);self.rejected('WEAPON_WORLD_SAMPLE_TRANSFORM')
    def test_wrong_world_pitch_space(self):self.cap['weapon']['samples'][4318]['worldPitch']['x']+=.01;self.rejected('WEAPON_WORLD_PITCH')
    def test_count_carrier_wrong_parent_units(self):self.cap['weapon']['samples'][500]['incomingLocalOffset']['x']*=100;self.rejected('WEAPON_COUNT_CARRIER')
    def test_no_source_pose_variation(self):
        for row in self.cap['weapon']['samples']:
            if row['state']=='Fire':row['animatorPoseSha256']='a'*64
        self.rejected('WEAPON_ANIMATOR_POSE_NOT_VARYING')
    def test_wrong_image_count(self):self.cap['frames'].pop();self.rejected('WEAPON_FRAME_COUNT')
    def test_wrong_image_label(self):self.cap['frames'][0]['requestedState']='Idle-0';self.rejected('WEAPON_FRAME_IDENTITY')
    def test_image_traversal(self):self.cap['frames'][0]['image']='../fixture-secret.png';self.rejected('WEAPON_FRAME_IDENTITY')
    def test_black_image(self):
        p=self.ev/'frame-0000.png';Image.new('RGB',(960,540)).save(p);self.cap['frames'][0]['imageSha256']=w.sha(p);self.rejected('STRICT_BLANK_IMAGE')
    def test_wrong_image_dimensions(self):
        p=self.ev/'frame-0000.png';Image.new('RGB',(540,960),(250,1,99)).save(p);self.cap['frames'][0]['imageSha256']=w.sha(p);self.rejected('STRICT_IMAGE_DIMENSIONS')
    def test_wrong_image_bytes(self):(self.ev/'frame-0000.png').write_bytes(b'fixture-secret');self.rejected('WEAPON_FRAME_IDENTITY')
    def test_vertices_outside_camera(self):self.cap['frames'][0]['outsideViewportVertices']=1;self.rejected('WEAPON_FRAME_VISIBILITY')
    def test_root_scale_changed(self):self.cap['frames'][0]['rootLocalScale']['x']=.01;self.rejected('WEAPON_FRAME_ROOT_DRIFT')
    def test_mesh_dimensions_mismatch(self):self.cap['frames'][0]['meshWorldSize']['x']=.01;self.rejected('STRICT_MESH_DIMENSIONS')
    def test_null_graphics(self):self.cap['graphicsDeviceType']='Null';self.rejected('WEAPON_REAL_GRAPHICS_REQUIRED')
    def test_unknown_generated_file(self):(self.folder/'secret.log').write_text('fixture-secret');self.rejected('WEAPON_GENERATED_ALLOWLIST')
    def test_empty_generated_directory_not_whitelisted(self):(self.folder/'extra').mkdir();self.rejected('WEAPON_GENERATED_DIRECTORY')
    def test_generated_directory_symlink(self):(self.folder/'escape').symlink_to('/tmp');self.rejected('WEAPON_SYMLINK_FORBIDDEN')
    def test_frame_symlink(self):
        p=self.ev/'frame-0000.png';p.unlink();p.symlink_to(self.ev/'frame-0001.png');self.rejected('STRICT_UNSAFE_FILE')
    def test_extra_raw_evidence_forbidden(self):(self.ev/'Editor.log').write_text('fixture-secret');self.rejected('WEAPON_EVIDENCE_ALLOWLIST')
    def test_atomic_commit_failure_exports_no_partial_payload(self):
        old=Path.replace
        def fail(path,target):
            if path.name.startswith('.weapon-safe-'):raise OSError('fixture-secret')
            return old(path,target)
        with patch.object(Path,'replace',fail):self.rejected('INVALID_EVIDENCE')
    def test_payload_mutation_during_copy(self):
        old=shutil.copyfile
        def mutate(source,target,*args,**kwargs):
            result=old(source,target,*args,**kwargs)
            if Path(source).name=='frame-0000.png':Path(target).write_bytes(b'fixture-secret')
            return result
        with patch.object(shutil,'copyfile',mutate):self.rejected('WEAPON_SOURCE_CHANGED_DURING_EXPORT')
    def test_protected_dependency_mutation_during_copy(self):
        old=shutil.copyfile
        def mutate(source,target,*args,**kwargs):
            result=old(source,target,*args,**kwargs)
            if Path(source).name=='frame-0000.png':self.write('Assets/DesertRV/Runtime/WeaponArmReach.cs','// changed during copy')
            return result
        with patch.object(shutil,'copyfile',mutate):self.rejected('WEAPON_DEPENDENCY_CHANGED_DURING_EXPORT')
    def test_report_mutation_during_copy(self):
        old=shutil.copyfile
        def mutate(source,target,*args,**kwargs):
            result=old(source,target,*args,**kwargs)
            if Path(source).name=='frame-0000.png':(self.ev/'import-report.json').write_text('fixture-secret')
            return result
        with patch.object(shutil,'copyfile',mutate):self.rejected('WEAPON_REPORT_CHANGED_DURING_EXPORT')
    def test_image_changed_after_validation_before_staging_is_rejected(self):
        original=w.generated_files
        def change(*args,**kwargs):
            result=original(*args,**kwargs);(self.ev/'frame-0000.png').write_bytes(b'not a png');return result
        with patch.object(w,'generated_files',change):self.rejected('WEAPON_INPUT_CHANGED_DURING_VALIDATION')
    def test_contract_changed_after_validation_before_staging_is_rejected(self):
        original=w.generated_files
        def change(*args,**kwargs):
            result=original(*args,**kwargs);(self.folder/'contract.json').write_text('{"unvalidated":true}');return result
        with patch.object(w,'generated_files',change):self.rejected('WEAPON_INPUT_CHANGED_DURING_VALIDATION')
    def test_source_changed_after_validation_before_staging_is_rejected(self):
        original=w.generated_files
        def change(*args,**kwargs):
            result=original(*args,**kwargs);(self.folder/'Source/weapon_hands.fbx').write_bytes(b'fixture-secret');return result
        with patch.object(w,'generated_files',change):self.rejected('WEAPON_INPUT_CHANGED_DURING_VALIDATION')
    def test_meta_changed_after_validation_before_staging_is_rejected(self):
        original=w.generated_files
        def change(*args,**kwargs):
            result=original(*args,**kwargs);(self.folder/'Source.meta').write_text('fixture-secret');return result
        with patch.object(w,'generated_files',change):self.rejected('WEAPON_INPUT_CHANGED_DURING_VALIDATION')
    def test_report_changed_while_parsing_is_rejected(self):
        original=w.read_capture
        def change(path):
            result=original(path);Path(path).write_text('{"fixture-secret":true}');return result
        with patch.object(w,'read_capture',change):self.rejected('WEAPON_INPUT_CHANGED_DURING_VALIDATION')
    def test_unexpected_exception_is_safe_code(self):
        with patch.object(w,'validate_import',side_effect=RuntimeError('fixture-secret')):self.rejected('INVALID_EVIDENCE')
    def test_summary_does_not_preserve_arbitrary_data(self):
        out=self.out;out.mkdir();summary=dict(importCommit='a'*40,importRunUrl='https://github.com/yangerstar1/task-workbench/actions/runs/123',rawLog='fixture-secret')
        result=w.export_weapon(self.root,out,self.c,summary,'success','success');self.assertNotIn('rawLog',result)
    def test_existing_output_never_overwritten(self):
        self.out.mkdir();(self.out/'keep').write_text('existing')
        with self.assertRaises(w.StrictError):self.run_export()
        self.assertEqual((self.out/'keep').read_text(),'existing')

    def add_asymmetric_orm(self):
        m=self.c['materials'][0];m['ormFile']='technical/weapon_orm.png';m['smoothness']=1
        src=self.folder/'Source'/m['ormFile'];src.parent.mkdir(parents=True)
        image=Image.new('RGBA',(2,2));image.putdata([(11,40,90,255),(23,71,133,255),(48,121,177,255),(82,198,229,255)]);image.save(src)
        self.meta(src);self.meta(src.parent);self.c['files'].append(dict(file=m['ormFile'],sha256=w.sha(src)))
        dst=self.folder/'Derived/ORM_00.png';dst.parent.mkdir();self.meta(dst.parent)
        image=Image.new('RGBA',(2,2));image.putdata([(90,11,0,215),(133,23,0,184),(177,48,0,134),(229,82,0,57)]);image.save(dst);self.meta(dst,True)
        self.material(0,m,w._meta_guid(dst));self.save_contract();self.imp['contractSha256']=w.sha(self.project/'CandidateImportInput/contract.json')
        self.imp['weaponCalibration']['materials'][0].update(expectedSmoothness=1,actualSmoothness=1)
        self.imp['dependencies'].append(self.prefix+'/Derived/ORM_00.png')
        self.imp['derivedTextures']=[dict(source=self.prefix+'/Source/'+m['ormFile'],sourceSha256=w.sha(src),derived=self.prefix+'/Derived/ORM_00.png',
            derivedSha256=w.sha(dst),decodedPixelSha256=hashlib.sha256(image.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes()).hexdigest(),
            mapping='R=source.B; G=source.R; B=0; A=255-source.G',width=2,height=2,sRGB=False,sourceModified=False)]
        self.rehash_dependencies();return src,dst

    def test_asymmetric_texture_conversion_and_material_binding(self):
        self.add_asymmetric_orm();self.assertEqual(self.run_export()['images'],25)
    def test_texture_channels_wrong(self):
        src,dst=self.add_asymmetric_orm();Image.new('RGBA',(2,2),(90,12,0,215)).save(dst)
        self.imp['derivedTextures'][0]['derivedSha256']=w.sha(dst);self.rehash_dependencies();self.rejected('STRICT_ORM_PIXEL_MAPPING')
    def test_texture_row_orientation_wrong(self):
        src,dst=self.add_asymmetric_orm()
        with Image.open(dst) as image:self.imp['derivedTextures'][0]['decodedPixelSha256']=hashlib.sha256(image.tobytes()).hexdigest()
        self.rejected('STRICT_ORM_IMPORTED_PIXEL_HASH')
    def test_texture_gamma_wrong(self):
        src,dst=self.add_asymmetric_orm();meta=Path(str(dst)+'.meta');meta.write_text(meta.read_text().replace('sRGBTexture: 0','sRGBTexture: 1'))
        self.rehash_dependencies();self.rejected('STRICT_ORM_IMPORT_SETTINGS')


if __name__=='__main__':unittest.main()
