"""Host-only exporter regressions. Synthetic rows are not native evidence."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

import journey_cabin_entry_native as n


def vector(x=0, y=0, z=0):
    return dict(x=x, y=y, z=z)


def baseline():
    state=json.loads((n.TASK/'SOURCE-STATE.json').read_bytes())
    return {row['path']:row for row in state['files']+state['restoredFiles']}


def fixture(entered=False):
    value = dict(schemaVersion=2, status='completed', unityVersion='6000.3.19f1',
        fixture='saved-RV-with-reconstructed-authored-road', referenceRun='38034314713',
        referenceBootstrapSha256='a31e108cf90a6244847d414670e4922150c73f45d38d6365cb3f795ed728d09f',
        referenceRegionSha256='ee6ded8b1e4c6284f6d40218a5b7b3768c95b2b4fee23c46d3f09162880e87e0',
        sourceScene=n.SCENE, route='standard-exit; settle-1s; held-forward-max-6s; stop-on-cabin-floor',
        maximumDeltaTime=1/3, referenceGeometryMatched=True, allEntered=entered, allRegressionsPassed=entered, regressionRoute=n.REGRESSION_ROUTE,
        replayDetached=True, sceneUnloaded=True, sourceFilesUnchanged=True,
        controller=dict(height=1.7, radius=.3, center=vector(0,.85,0), stepOffset=.3, skinWidth=.08, slopeLimit=45, minMoveDistance=0),
        lowerCollider=1, upperCollider=2, floorCollider=3, roadCollider=4, savedRvColliderCount=4,
        sourceFiles=[dict(path=name, sha256=n.pin((n.isolated.PROJECT/name).read_bytes())) for name in (n.SCENE,n.SCENE+'.meta',n.AUTHOR,n.MOTOR,n.ADAPTER)],
        colliders=[], cases=[])
    for i, name in enumerate(('GEO-entry_step_lower','GEO-entry_step','GEO-interior_floor','Road surface','GEO-coach_body_shell'),1):
        value['colliders'].append(dict(id=i,hierarchy=name,type='BoxCollider',meshAsset='',meshGuid='',meshLocalId='',
            authoredBy=n.SCENE if i!=4 else n.AUTHOR+':DressEnvironment/Road surface',enabled=True,active=True,trigger=False,convex=False,min=vector(),max=vector(1,1,1)))
    value['colliders'][3].update(min=vector(-4,-.065,-17),max=vector(4,.035,77))
    value['colliders'][4].update(min=vector(-1.14,.62,-2.91),max=vector(1.14,2.75,3))
    for name, delta in n.TIMESTEPS:
        end=vector(-1,.83,.6) if entered else vector(-2.26,.04,.6)
        frame=dict(frame=0,flags=4 if entered else 1,supportCollider=3 if entered else 4,droppedContacts=0,
            phase='forward',elapsed=delta,delta=delta,footHeight=.8 if entered else .04,intendedDistance=3.1*delta,forwardDistance=0,
            doorAngle=90,verticalSpeedBefore=-2,verticalSpeedAfter=-2,position=end,supportPoint=vector(),groundedBefore=True,groundedAfter=True,insideCabin=entered,
            contacts=[dict(collider=3 if entered else 1,point=vector(),normal=vector(-1,0,0),moveDirection=vector(1,0,0),moveLength=delta)])
        value['cases'].append(dict(name=name,outcome='entered' if entered else 'blocked',delta=delta,exit=vector(-2.26,.04,.6),end=end,
            exited=True,lowerSupported=False,upperSupported=False,floorSupported=entered,enteredCabin=entered,
            firstSideContactFrame=-1 if entered else 0,firstConstrainedFrame=-1 if entered else 0,firstPersistentBlockFrame=-1,frames=[frame],regressions=regressions(entered,delta)))
    return value


def regressions(entered, delta):
    road=vector(-2.26,.06,.6); exit=vector(-2.26,.04,.6)
    target=vector(-2.26,.06,-.9); blocked=vector(-1.5,.06,-.9)
    def frame(phase, position):
        return dict(frame=0,phase=phase,position=position,flags=4,grounded=True,supportCollider=4,
                    verticalSpeed=-1,insideCabin=False,intendedDistance=0 if phase=='settle' else 3.1*delta,
                    forwardDistance=0,sideCollider=5 if phase=='push' else 0,sidePoint=vector(),
                    sideNormal=vector(-1,0,0) if phase=='push' else vector(),contactCount=1)
    driver=dict(enterAttempted=True,enterSucceeded=True,exitAttempted=True,exitSucceeded=True,
                controlBefore='OnFoot',controlAfterEnter='Driving',controlAfterExit='OnFoot',
                contextBefore='OnFoot',contextAfterEnter='Driving',contextAfterExit='OnFoot',
                controllerBefore=True,controllerAfterEnter=False,controllerAfterExit=True,
                positionBefore=road,positionAfterEnter=road,positionAfterExit=exit)
    pushes=[frame('push',blocked) for _ in range(math.ceil(.5/delta))]
    side=[frame('approach',target)]+pushes
    for i,value in enumerate(side):value['frame']=i
    return [dict(name='downstairs',outcome='passed' if entered else 'entry-not-reached',
                 start=vector(-1,.83,.6) if entered else exit,end=road if entered else exit,
                 standardReset=False,frames=[frame('backward',road)] if entered else [],driver=[]),
            dict(name='road-grounded',outcome='passed',start=road,end=road,standardReset=False,frames=[frame('settle',road)],driver=[]),
            dict(name='driver-cycle',outcome='passed',start=road,end=exit,standardReset=False,frames=[],driver=[driver]),
            dict(name='sidewall',outcome='passed',start=exit,end=blocked,standardReset=False,frames=side,driver=[])]


def xml(result='Failed'):
    root=ET.Element('test-run',result=result,total='1',passed='1' if result=='Passed' else '0',failed='0' if result=='Passed' else '1',skipped='0',inconclusive='0')
    case=ET.SubElement(root,'test-case',fullname=n.EXPECTED,result=result,duration='1.25')
    ET.SubElement(case,'failure').text='PRIVATE_RAW_LOG_MUST_NEVER_EXPORT'
    return ET.tostring(root)


class SchemaTests(unittest.TestCase):
    def test_all_five_failed_entry_cases_are_valid_complete_observations(self):
        for entered in (False,True):
            value=fixture(entered)
            self.assertTrue(n.validate_physics(value)); self.assertTrue(n.physics_complete(value))
            n.verify_physics_sources(value, baseline())
        value=fixture(); value.update(status='fixture-incomplete',cases=value['cases'][:2],replayDetached=False)
        self.assertTrue(n.validate_physics(value));self.assertFalse(n.physics_complete(value))

    def test_missing_extra_reordered_cadence_and_inconsistent_outcome_reject(self):
        for mutate in (lambda v:v['cases'].pop(),lambda v:v['cases'].append(v['cases'][0]),
                       lambda v:v['cases'].reverse(),lambda v:v.update(allEntered=True),
                       lambda v:v['cases'][0].update(enteredCabin=True),
                       lambda v:v['cases'][0].update(floorSupported=True),
                       lambda v:v['cases'][0]['frames'][0].update(delta=.2)):
            value=fixture();mutate(value);self.assertFalse(n.validate_physics(value))

    def test_arbitrary_fields_private_paths_and_unbounded_numbers_reject(self):
        for mutate in (lambda v:v.update(log='PRIVATE_TOKEN'),lambda v:v.update(unityVersion='private'),
                       lambda v:v['colliders'][0].update(hierarchy='/private/SECRET'),
                       lambda v:v['colliders'][0].update(meshAsset='Assets/../SECRET'),
                       lambda v:v['colliders'][0].update(authoredBy='PRIVATE_TOKEN'),
                       lambda v:v['sourceFiles'][0].update(path='/private/SECRET'),
                       lambda v:v['cases'][0]['frames'][0].update(delta=float('nan')),
                       lambda v:v['cases'][0]['frames'][0].update(droppedContacts=10001),
                       lambda v:v['cases'][0]['frames'][0].update(contacts=v['cases'][0]['frames'][0]['contacts']*9),
                       lambda v:v['cases'][0]['frames'][0]['contacts'][0].update(collider=999)):
            value=fixture();mutate(value);self.assertFalse(n.validate_physics(value))

    def test_unknown_scene_identity_and_changed_source_pin_never_export(self):
        for mutate in (lambda v:v['colliders'][0].update(hierarchy='SECRET_HOST_PATH'),
                       lambda v:v['sourceFiles'][0].update(sha256='a'*64),
                       lambda v:v['sourceFiles'].append(dict(path='Assets/DesertRV/SECRET',sha256='a'*64))):
            value=fixture();mutate(value)
            with self.assertRaises(ValueError):n.verify_physics_sources(value, baseline())

    def test_current_mesh_or_scene_hash_cannot_replace_authenticated_source_pin(self):
        value=fixture(); original=baseline()
        original['tasks/desert-rv/unity/'+n.SCENE]=dict(sha256='0'*64)
        with self.assertRaises(ValueError):n.verify_physics_sources(value, original)

    def test_native_cleanup_and_geometry_are_required_for_complete_not_raw_retention(self):
        for key in ('referenceGeometryMatched','replayDetached','sceneUnloaded','sourceFilesUnchanged'):
            value=fixture();value[key]=False
            self.assertTrue(n.validate_physics(value));self.assertFalse(n.physics_complete(value))

    def test_regression_inventory_states_and_aggregate_are_strict(self):
        for mutate in (lambda v:v['cases'][0]['regressions'].pop(),
                       lambda v:v['cases'][0]['regressions'].reverse(),
                       lambda v:v['cases'][0]['regressions'][0].update(name='unknown'),
                       lambda v:v['cases'][0]['regressions'][1].update(detail='PRIVATE_TOKEN'),
                       lambda v:v['cases'][0]['regressions'][2]['driver'][0].update(contextAfterEnter='Overlay'),
                       lambda v:v['cases'][0]['regressions'][2]['driver'][0].update(exitAttempted=False),
                       lambda v:v['cases'][0]['regressions'][3]['frames'][0].update(sideNormal=vector(2,0,0)),
                       lambda v:v['cases'][0]['regressions'][3]['frames'][0].update(contactCount=10001),
                       lambda v:v['cases'][0]['regressions'][3].update(standardReset=True),
                       lambda v:v['cases'][0]['regressions'][3].update(frames=v['cases'][0]['regressions'][3]['frames']*241),
                       lambda v:v.update(allRegressionsPassed=False)):
            value=fixture(True);mutate(value);self.assertFalse(n.validate_physics(value))

    def test_safe_failed_context_and_count_only_side_witness_are_retained(self):
        value=fixture(True);value['allRegressionsPassed']=False
        driver=value['cases'][0]['regressions'][2];driver['outcome']='failed';driver['driver'][0]['contextAfterEnter']='Overlay'
        # New compact witnesses see all callbacks; they do not pretend to retain
        # detailed contacts or change the original entry array's eight-item cap.
        value['cases'][0]['regressions'][3]['frames'][0]['contactCount']=160
        self.assertTrue(n.validate_physics(value));self.assertTrue(n.physics_complete(value))
        value['cases'][0]['frames'][0]['contacts']*=9
        self.assertFalse(n.validate_physics(value))

    def test_passed_regressions_require_observed_ground_descent_wall_and_driver_metrics(self):
        for mutate in (lambda r:r[0].update(start=vector(-1,.2,.6)),
                       lambda r:r[0]['frames'][-1].update(grounded=False),
                       lambda r:r[1]['frames'][0].update(position=vector(-2.26,-1,.6)),
                       lambda r:r[1]['frames'][0].update(supportCollider=3),
                       lambda r:r[2]['driver'][0].update(positionAfterEnter=vector(9,9,9)),
                       lambda r:r[3]['frames'][-1].update(sideCollider=1),
                       lambda r:r[3]['frames'][-1].update(forwardDistance=1),
                       lambda r:r[3]['frames'][-1].update(position=vector(0,.06,-.9))):
            value=fixture(True);mutate(value['cases'][0]['regressions'])
            self.assertFalse(n.validate_physics(value))


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.raw=self.root/'native-entry-probe.json';self.artifacts=self.root/'native';self.artifacts.mkdir()
        self.xml=self.artifacts/'results.xml';self.xml.write_bytes(xml())
        self.report=self.root/'public.json';self.isolation=self.root/'isolation.json';self.isolation.write_text('{}')
        self.env=dict(GITHUB_SHA='a'*40,GITHUB_RUN_ID='1234',GITHUB_RUN_ATTEMPT='1',GITHUB_OUTPUT=str(self.root/'outputs'),NATIVE_OUTCOME='failure')
        self.raw.write_text(json.dumps(fixture()))
        self.patches=[mock.patch.multiple(n,REPORT=self.report,RAW_REPORT=self.raw,ARTIFACTS=self.artifacts),
                      mock.patch.object(n.dispatch,'verify',return_value=dict(sourceStateSha256=n.pin((n.TASK/'SOURCE-STATE.json').read_bytes()))),
                      mock.patch.object(n.isolated,'verify_unchanged'),mock.patch.object(n.isolated,'ISOLATION_REPORT',self.isolation),
                      mock.patch.object(n.isolated,'validate_isolation',return_value=True)]
        for patch in self.patches:patch.start()
        self.isolation.write_text(json.dumps(dict(status='PASS',sourceCommit='a'*40,runId='1234',runAttempt='1')))
        self.request=Path(n.dispatch.REQUEST)
        self.request_raw=b'fixture exact request'
        self.original=n.isolated.file_bytes
        self.patcher=mock.patch.object(n.isolated,'file_bytes',side_effect=lambda p,limit=128*1024**2:self.request_raw if p==n.ROOT/self.request else self.original(p,limit))
        self.patcher.start()
    def tearDown(self):
        self.patcher.stop()
        for patch in reversed(self.patches):patch.stop()
        self.temp.cleanup()
    def read(self):
        value=json.loads(self.report.read_text());self.assertTrue(n.validate_report(value));return value

    def test_failed_native_assertion_retains_all_five_cases_and_exact_failed_xml(self):
        self.assertEqual(n.run(self.env),0);value=self.read()
        self.assertEqual(value['status'],'DIAGNOSTIC_COMPLETE');self.assertFalse(value['physics']['allEntered'])
        self.assertEqual(len(value['physics']['cases']),5);self.assertEqual(value['nativeResults'][0]['result'],'Failed')
        self.assertEqual(value['nativeXmlSha256'],hashlib.sha256(self.xml.read_bytes()).hexdigest())
        self.assertNotIn('PRIVATE_RAW_LOG',self.report.read_text());self.assertIn('report_valid=true',(self.root/'outputs').read_text())
        self.raw.unlink();self.assertEqual(len(self.read()['physics']['cases']),5)

    def test_success_retains_separate_one_case_identity(self):
        self.raw.write_text(json.dumps(fixture(True)));self.xml.write_bytes(xml('Passed'))
        self.assertEqual(n.run(dict(self.env,NATIVE_OUTCOME='success')),0);value=self.read()
        self.assertEqual(value['nativeCases'],1);self.assertEqual(value['expectedNativeCases'],1)
        self.assertEqual(value['purpose'],'NATIVE_DIAGNOSTIC_ONLY')

    def test_source_failure_keeps_valid_physics_but_never_claims_complete(self):
        with mock.patch.object(n.isolated,'verify_unchanged',side_effect=ValueError('PRIVATE_TOKEN')):
            self.assertEqual(n.run(self.env),2)
        value=self.read();self.assertEqual(value['checks']['originalSource'],'FAIL');self.assertIsNotNone(value['physics'])
        self.assertFalse(value['diagnosticComplete']);self.assertNotIn('PRIVATE_TOKEN',self.report.read_text())

    def test_invalid_payload_returns_only_fixed_failure_status(self):
        self.raw.write_text('{"secret":"PRIVATE_TOKEN"}')
        self.assertEqual(n.run(self.env),2);value=self.read()
        self.assertIsNone(value['physics']);self.assertEqual(value['checks']['physics'],'FAIL')
        self.assertNotIn('PRIVATE_TOKEN',self.report.read_text())

    def test_observed_failed_child_root_retains_exact_failed_leaf_and_physics(self):
        # Run 38044711804 reports a failed test-run as Failed(Child), while its
        # one actual test-case result remains Failed. Only that root spelling is
        # added; native outcome/counts/leaf and complete physics still agree.
        self.xml.write_bytes(xml().replace(b'result="Failed"', b'result="Failed(Child)"', 1))
        self.assertEqual(n.run(self.env),0);value=self.read()
        self.assertEqual(value['nativeResults'][0]['result'],'Failed')
        self.assertEqual(value['nativeCases'],1);self.assertTrue(value['diagnosticComplete'])
        self.assertEqual(len(value['physics']['cases']),5);self.assertFalse(value['physics']['allEntered'])
        self.assertNotIn('PRIVATE_RAW_LOG',self.report.read_text())

    def test_failed_child_spelling_is_only_accepted_for_failed_root_and_exact_failed_leaf(self):
        for root_result in ('Unknown', 'failed', 'Failed(Parent)', 'Failed (Child)', 'Failed(Child)Extra', 'Error', 'Passed(Child)'):
            self.xml.write_bytes(xml().replace(b'result="Failed"', ('result="'+root_result+'"').encode(), 1))
            with self.subTest(root=root_result),self.assertRaises(ValueError):n.inspect_xml()
        for raw in (xml('Passed').replace(b'result="Passed"',b'result="Failed(Child)"',1),
                    xml().replace(b'result="Failed"',b'result="Failed(Child)"'),
                    xml().replace(b'result="Failed"',b'result="Failed(Child)"',1).replace(b'failed="1"',b'failed="0"')):
            self.xml.write_bytes(raw)
            with self.assertRaises(ValueError):n.inspect_xml()

    def test_exact_xml_rejects_missing_extra_failed_counts_and_private_declarations(self):
        for raw in (b'<!DOCTYPE secret><test-run/>',xml().replace(b'total="1"',b'total="2"'),xml().replace(n.EXPECTED.encode(),b'Unrelated.Test'),b'<test-run/>'):
            self.xml.write_bytes(raw)
            with self.assertRaises((ValueError,ET.ParseError)):n.inspect_xml()
        self.xml.write_bytes(xml());(self.artifacts/'extra.xml').write_bytes(xml())
        with self.assertRaises(ValueError):n.inspect_xml()

    def test_outcome_mismatch_and_false_pass_remain_incomplete(self):
        self.xml.write_bytes(xml('Passed'))
        self.assertEqual(n.run(dict(self.env,NATIVE_OUTCOME='success')),2)
        self.assertFalse(self.read()['diagnosticComplete'])

    def test_failed_regression_blocks_native_pass_even_when_every_entry_passed(self):
        value=fixture(True);value['allRegressionsPassed']=False
        value['cases'][0]['regressions'][3]['outcome']='failed'
        self.raw.write_text(json.dumps(value))
        self.assertEqual(n.run(self.env),0);report=self.read()
        self.assertTrue(report['diagnosticComplete']);self.assertTrue(report['physics']['allEntered'])
        self.assertFalse(report['physics']['allRegressionsPassed'])
        self.report.unlink();self.xml.write_bytes(xml('Passed'))
        self.assertEqual(n.run(dict(self.env,NATIVE_OUTCOME='success')),2)
        self.assertFalse(self.read()['diagnosticComplete'])

    def test_symlink_payload_rejected_without_dereference(self):
        self.raw.unlink();self.raw.symlink_to(self.xml)
        self.assertEqual(n.run(self.env),2);self.assertIsNone(self.read()['physics'])

    def test_exact_four_mib_raw_budget_accepts_and_one_extra_byte_rejects(self):
        self.assertEqual(n.MAX_PHYSICS,4*1024**2);self.assertEqual(n.MAX_REPORT,8*1024**2)
        raw=self.raw.read_bytes();self.raw.write_bytes(raw+b' '*(n.MAX_PHYSICS-len(raw)))
        self.assertEqual(n.run(self.env),0);self.assertTrue(self.read()['diagnosticComplete'])
        self.assertLessEqual(self.report.stat().st_size,n.MAX_REPORT)
        self.report.unlink()
        with self.raw.open('ab') as stream:stream.write(b' ')
        self.assertEqual(n.run(self.env),2);value=self.read()
        self.assertIsNone(value['physics']);self.assertEqual(value['checks']['physics'],'FAIL')


class WorkflowTests(unittest.TestCase):
    def test_full_native_sequence_and_diagnostics_before_owned_cleanup(self):
        import yaml
        raw=(n.ROOT/n.dispatch.WORKFLOW).read_text();workflow=yaml.load(raw,Loader=yaml.BaseLoader)
        self.assertEqual(workflow['on']['push']['paths'],[n.dispatch.REQUEST])
        steps=workflow['jobs']['prepare']['steps'];order=[step.get('id') for step in steps]
        native=[s for s in steps if s.get('uses','').startswith('game-ci/unity-test-runner@')]
        self.assertEqual([s['id'] for s in native],['tracer_native','keyboard_native','cabin_native','region_hud_native','combat_feedback_native','armored','pouncer','weapon','linux_boundary','author'])
        cabin=native[2];self.assertIn('always()',cabin['if']);self.assertIn("steps.keyboard_copy.outputs.copy_ready == 'true'",cabin['if'])
        self.assertNotIn('keyboard_native.outcome',cabin['if']);self.assertEqual(cabin['with']['projectPath'],n.isolated.COPY_REL)
        self.assertEqual(cabin['with']['customParameters'],'-assemblyNames DesertRV.PlayModeTests -testFilter '+n.EXPECTED+' -force-glcore -job-worker-count 2')
        for earlier,later in (('keyboard_native','cabin_native'),('cabin_native','keyboard_isolation'),('keyboard_isolation','cabin_report'),('cabin_report','keyboard_cleanup')):
            self.assertLess(order.index(earlier),order.index(later))
        report=next(s for s in steps if s.get('id')=='cabin_report');self.assertIn('always()',report['if']);self.assertNotIn('success',report['if'])
        upload=next(s for s in steps if s.get('with',{}).get('name','').startswith('journey-cabin-entry-native-'))
        self.assertEqual(upload['with']['path'],str(n.REPORT.relative_to(n.ROOT)))
        self.assertLess(steps.index(upload),order.index('keyboard_cleanup'))
        for forbidden in ('restore_preparation.py','prepare-restored','continue-on-error:','path: tasks/desert-rv/artifacts/'):
            self.assertNotIn(forbidden,raw)
        self.assertNotIn(n.RAW_REPORT.relative_to(n.ROOT).as_posix(),upload['with']['path'])
        self.assertLess(order.index('keyboard_cleanup'),order.index('stage_armored'))
        self.assertLess(order.index('stage_armored'),order.index('linux_native'))

    def test_failed_incomplete_or_skipped_native_gate_cannot_start_producer(self):
        import re
        import yaml
        steps=yaml.load((n.ROOT/n.dispatch.WORKFLOW).read_text(),Loader=yaml.BaseLoader)['jobs']['prepare']['steps']
        by_id={step['id']:step for step in steps if 'id' in step}
        condition=by_id['stage_armored']['if']
        terms=condition.split(' && ')
        self.assertEqual(terms[0],'success()')
        expected={
            'tracer_source.outcome':'success','tracer_source.outputs.source_unchanged':'true',
            'tracer_verify.outcome':'success','tracer_verify.outputs.native_verified':'true',
            'keyboard_source.outcome':'success','keyboard_source.outputs.source_unchanged':'true',
            'keyboard_verify.outcome':'success','keyboard_verify.outputs.native_verified':'true',
            'keyboard_isolation.outputs.copy_verified':'true','keyboard_cleanup.outcome':'success',
            'cabin_native.outcome':'success','cabin_report.outcome':'success',
            'cabin_report.outputs.diagnostic_complete':'true',
            'region_hud_native.outcome':'success','region_hud_verify.outcome':'success',
            'region_hud_verify.outputs.native_verified':'true',
            'combat_feedback_native.outcome':'success','combat_feedback_verify.outcome':'success',
            'combat_feedback_verify.outputs.native_verified':'true'}
        parsed=[]
        for term in terms[1:]:
            match=re.fullmatch(r"steps\.([a-z_]+\.(?:outcome|outputs\.[a-z_]+)) == '(success|true)'",term)
            self.assertIsNotNone(match,term);parsed.append(match.groups())
        self.assertEqual(dict(parsed),expected);self.assertEqual(len(parsed),len(expected))
        allowed=lambda values,success=True: success and all(values.get(key,'')==value for key,value in parsed)
        self.assertTrue(allowed(expected));self.assertFalse(allowed(expected,False))
        for key in expected:
            for bad in ('','false','failure','skipped','cancelled'):
                with self.subTest(gate=key,value=bad):
                    self.assertFalse(allowed(dict(expected,**{key:bad})))
            absent=dict(expected);absent.pop(key);self.assertFalse(allowed(absent))
        # A complete failed diagnosis has a valid report, but never authorizes imports.
        self.assertFalse(allowed(dict(expected,**{'cabin_native.outcome':'failure'})))

    def test_skipped_stage_cannot_fall_through_into_later_native_or_build(self):
        import re
        import yaml
        steps=yaml.load((n.ROOT/n.dispatch.WORKFLOW).read_text(),Loader=yaml.BaseLoader)['jobs']['prepare']['steps']
        by_id={step['id']:step for step in steps if 'id' in step}
        predecessors={'armored':'stage_armored','stage_pouncer':'collect_armored',
            'pouncer':'stage_pouncer','stage_weapon':'collect_pouncer','weapon':'stage_weapon',
            'ready':'collect_weapon','linux_boundary':'ready','boundary_verify':'linux_boundary',
            'author':'boundary_verify','linux_input':'finish','linux_native':'linux_input',
            'linux_verify':'linux_native'}
        for step,prior in predecessors.items():
            with self.subTest(step=step):
                self.assertEqual(by_id[step]['if'],"success() && steps."+prior+".outcome == 'success'")
                self.assertLess(steps.index(by_id[prior]),steps.index(by_id[step]))
        for kind in ('armored','pouncer','weapon'):
            self.assertEqual(by_id['collect_'+kind]['if'],"always() && steps.stage_"+kind+".outcome == 'success'")
        self.assertEqual(by_id['linux_public']['if'],"always() && steps.linux_native.outcome != 'skipped'")
        self.assertIn('steps.linux_public.outputs.export_ready',by_id['shader_registry']['if'])
        chain=['stage_armored','armored','collect_armored','stage_pouncer','pouncer',
               'collect_pouncer','stage_weapon','weapon','collect_weapon','ready',
               'linux_boundary','boundary_verify','author','finish','linux_input',
               'linux_native','linux_verify','linux_public']
        terms=re.findall(r"steps\.([a-z_.]+) == '(success|true)'",by_id['stage_armored']['if'])
        for rejected in ('failure','skipped','cancelled',''):
            # Actions success() stays true when a prior step merely skipped. Evaluate
            # the actual YAML dependencies with that behavior through the full chain.
            values=dict(terms);values['cabin_native.outcome']=rejected
            for ident in chain:
                allowed=True
                for term in by_id[ident]['if'].split(' && '):
                    if term in ('success()','always()'):continue
                    match=re.fullmatch(r"steps\.([a-z_.]+) (==|!=) '([a-z]+)'",term)
                    self.assertIsNotNone(match,term)
                    key,op,wanted=match.groups();equal=values.get(key,'')==wanted
                    allowed=allowed and (equal if op=='==' else not equal)
                values[ident+'.outcome']='success' if allowed else 'skipped'
            with self.subTest(cabinOutcome=rejected):
                self.assertEqual([values[ident+'.outcome'] for ident in chain],['skipped']*len(chain))


if __name__=='__main__':
    unittest.main()
