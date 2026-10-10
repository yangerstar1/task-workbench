"""Offline boundary fixtures: no Docker, Unity, download, or Actions mutation."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest import mock
import zipfile
import journey_vehicle_contact_probe as probe


def identity_fixture():
    head = 'a' * 40
    env = dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=probe.REPOSITORY, GITHUB_REPOSITORY_VISIBILITY='public',
        RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Linux', GITHUB_ACTOR=probe.OWNER_NAME,
        GITHUB_TRIGGERING_ACTOR=probe.OWNER_NAME, GITHUB_EVENT_NAME='push', GITHUB_REF=probe.REF,
        GITHUB_WORKFLOW_REF=probe.REPOSITORY + '/' + probe.WORKFLOW + '@' + probe.REF,
        GITHUB_SHA=head, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1')
    event = dict(before=probe.BASE, after=head, ref=probe.REF, created=False, deleted=False, forced=False,
        repository=dict(full_name=probe.REPOSITORY, private=False, fork=False, default_branch='main', owner=dict(login=probe.OWNER_NAME)),
        sender=dict(login=probe.OWNER_NAME), head_commit=dict(id=head))
    digest = 'b' * 64
    raw = json.dumps(dict(schema=1, requestId=probe.NONCE, baseCommit=probe.BASE,
        sourceStateSha256=digest, producerArtifactSha256=probe.PRODUCER['artifactSha256'])).encode()
    return [env,event,head,[probe.BASE],raw,raw,False,[probe.REQUEST],digest]


class Boundaries(unittest.TestCase):
    def test_diagnostic_errors_preserve_only_owned_codes_or_exception_class(self):
        self.assertEqual(probe.failure_code(ValueError('VEHICLE_CONTACT_DEPENDENCY_PATH')),'VEHICLE_CONTACT_DEPENDENCY_PATH')
        for message in ('private /home/runner/secret','VEHICLE_CONTACT_OK\nprivate-secret','VEHICLE_CONTACT_'+'X'*200):
            value=probe.failure_code(ValueError(message))
            self.assertEqual(value,'VEHICLE_CONTACT_EXCEPTION_VALUEERROR')
            self.assertNotIn('secret',value)
        self.assertEqual(probe.failure_code(FileNotFoundError('/home/runner/private')),'VEHICLE_CONTACT_EXCEPTION_FILENOTFOUNDERROR')
        self.assertEqual(probe.failure_code(RuntimeError('private')),'VEHICLE_CONTACT_EXCEPTION_OTHERERROR')

    def test_exact_one_use_identity(self):
        self.assertEqual(probe.validate_identity(*identity_fixture())['baseCommit'], probe.BASE)

    def test_rejects_wrong_actor_attempt_workflow_ref_and_event(self):
        for key,value in dict(GITHUB_ACTOR='other', GITHUB_TRIGGERING_ACTOR='other', GITHUB_RUN_ATTEMPT='2',
            GITHUB_WORKFLOW_REF='other', GITHUB_REF='refs/heads/main', GITHUB_EVENT_NAME='workflow_dispatch',
            GITHUB_REPOSITORY_VISIBILITY='private', RUNNER_ENVIRONMENT='self-hosted').items():
            with self.subTest(key=key):
                args=identity_fixture(); args[0][key]=value
                with self.assertRaises(ValueError): probe.validate_identity(*args)

    def test_rejects_new_branch_force_replay_wrong_parent_request(self):
        for key in ('created','forced','deleted'):
            args=identity_fixture(); args[1][key]=True
            with self.assertRaises(ValueError): probe.validate_identity(*args)
        for index,value in ((3,['f'*40]),(3,[probe.BASE,probe.BASE]),(6,True),(7,[]),(8,'c'*64)):
            args=identity_fixture(); args[index]=value
            with self.assertRaises(ValueError): probe.validate_identity(*args)
        args=identity_fixture(); args[4]=args[4].replace(probe.NONCE.encode(),b'reused');args[5]=args[4]
        with self.assertRaises(ValueError): probe.validate_identity(*args)

    def test_rejects_duplicate_or_nonfinite_json(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}'):
            with self.assertRaises(ValueError): probe.parse(raw)

    def test_exact_archive_bytes_and_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for index,name in enumerate(('assets/valid.txt','../escape.txt','/absolute.txt','a\\b.txt')):
                path=root/f'{index}.zip'
                with zipfile.ZipFile(path,'w') as z: z.writestr(name,b'fixture')
                pin=dict(probe.PRODUCER,artifactSha256=hashlib.sha256(path.read_bytes()).hexdigest(),artifactBytes=path.stat().st_size)
                with mock.patch.object(probe,'PRODUCER',pin):
                    if index==0:
                        probe.extract(path,root/'good');self.assertEqual((root/'good/assets/valid.txt').read_bytes(),b'fixture')
                    else:
                        with self.assertRaises(ValueError): probe.extract(path,root/f'bad{index}')
            with self.assertRaises(ValueError): probe.extract(root/'0.zip',root/'wrong-pin')

    def test_source_difference_contains_only_relative_hashes(self):
        before={'Assets/Original.cs':dict(sha256='a'*64,bytes=1)}
        after={'Assets/Original.cs':dict(sha256='b'*64,bytes=2)}
        self.assertEqual(probe.differences(before,after),[dict(path='Assets/Original.cs',before=before['Assets/Original.cs'],after=after['Assets/Original.cs'])])
        with self.assertRaises(ValueError): probe.differences({}, {'/private/secret':{}})
        with self.assertRaises(ValueError): probe.differences({}, {'Assets/../private':{}})

    def test_xml_requires_exact_case_and_preserves_failure(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(probe,'ARTIFACTS',Path(d)):
            path=Path(d)/'result.xml'
            for result in ('Passed','Failed'):
                path.write_text(f'<test-run result="{result}" total="1" passed="{int(result=="Passed")}" failed="{int(result=="Failed")}" skipped="0" inconclusive="0"><test-case fullname="{probe.TEST}" result="{result}"/></test-run>')
                self.assertEqual(probe.inspect_xml()['result'],result)
            path.write_text(path.read_text().replace(probe.TEST,'Other.Test'))
            with self.assertRaises(ValueError): probe.inspect_xml()
            path.write_text('<!DOCTYPE test-run [<!ENTITY private SYSTEM "file:///private">]><test-run/>')
            with self.assertRaises(ValueError): probe.inspect_xml()

    def test_refuses_cleanup_without_matching_owner(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);copy_path=root/'journey-vehicle-contact-project';copy_path.mkdir()
            keep=copy_path/'keep';keep.write_text('untouched')
            with mock.patch.multiple(probe,TASK=root,COPY=copy_path,OWNER=root/'absent',PROJECT=root/'unity'):
                with self.assertRaises(Exception): probe.cleanup()
            self.assertEqual(keep.read_text(),'untouched')


class ProducerAndIsolation(unittest.TestCase):
    def test_exact_producer_metadata_rejects_stale_or_failed_inputs(self):
        run = dict(id=probe.PRODUCER['runId'],run_attempt=1,head_sha=probe.PRODUCER['commit'],
            head_branch='journey-tracer-shader-fix-6648',path='.github/workflows/desert-rv-tracer-shader-prepare.yml',
            event='push',status='completed',conclusion='success')
        artifact = dict(id=probe.PRODUCER['artifactId'],name=probe.PRODUCER['artifactName'],expired=False,
            size_in_bytes=probe.PRODUCER['artifactBytes'],digest='sha256:'+probe.PRODUCER['artifactSha256'],
            workflow_run=dict(id=probe.PRODUCER['runId'],head_sha=probe.PRODUCER['commit']))
        names=['Native strict '+k+' import and actual capture' for k in probe.generated.KINDS]
        names+=['Reuse exact strict quality gate and preserve '+k+' reports' for k in probe.generated.KINDS]
        names+=['Native original FX, four scenes, integration and diagnostic scope', 'Verify actual preparation test, saved outputs and final scope pins']
        jobs=dict(jobs=[dict(name='prepare',run_id=probe.PRODUCER['runId'],status='completed',conclusion='success',
            steps=[dict(name=n,conclusion='success') for n in names])])
        probe.validate_producer_api(run,artifact,jobs)
        for key,value in [('id',38034314713),('head_sha','a'*40),('run_attempt',2),('conclusion','failure')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                probe.validate_producer_api(dict(run,**{key:value}),artifact,jobs)
        for key,value in [('id',11665232715),('expired',True),('digest','sha256:'+'a'*64),('size_in_bytes',1)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                probe.validate_producer_api(run,dict(artifact,**{key:value}),jobs)
        jobs['jobs'][0]['steps'][-1]['conclusion']='skipped'
        with self.assertRaises(ValueError):probe.validate_producer_api(run,artifact,jobs)

    def test_playmode_settings_copy_uses_existing_bounded_diff_and_never_changes_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);project=root/'unity';owned=root/'copy'
            for parent in (project,owned):
                for name in ('Assets','Packages','ProjectSettings'):(parent/name).mkdir(parents=True)
                (parent/'Assets/example.txt').write_text('public source')
                (parent/'Packages/manifest.json').write_text('{}')
            before=b'%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!129 &1\nPlayerSettings:\n  productName: Original\n  AndroidKeystorePass: \n'
            after=before.replace(b'productName: Original',b'productName: Temporary').replace(b'AndroidKeystorePass: \n',b'AndroidKeystorePass: null\n')
            (project/probe.SETTINGS).write_bytes(before);(owned/probe.SETTINGS).write_bytes(after)
            owner=dict(union=probe.protected_inventory(project)[0])
            with mock.patch.multiple(probe,PROJECT=project,COPY=owned):
                changes,settings=probe.inspect_isolated_union(owner)
                self.assertEqual(changes,[]);self.assertEqual(settings['status'],'COMPLETE_DIFF')
                self.assertEqual(probe.apply_settings_diff(before,settings['diff']),after)
                self.assertEqual((project/probe.SETTINGS).read_bytes(),before)
                (owned/'Assets/example.txt').write_text('changed')
                self.assertEqual(len(probe.inspect_isolated_union(owner)[0]),1)
                (owned/probe.SETTINGS).write_bytes(after.replace(b'AndroidKeystorePass: null',b'AndroidKeystorePass: credential-value'))
                with self.assertRaises(ValueError):probe.inspect_isolated_union(owner)

    def test_workflow_has_one_native_case_no_build_and_fixed_readiness(self):
        text=(probe.ROOT/probe.WORKFLOW).read_text()
        self.assertEqual(text.count('uses: game-ci/unity-test-runner@'),1)
        self.assertIn('testMode: playmode',text)
        self.assertIn('-assemblyNames DesertRV.PlayModeTests -testFilter '+probe.TEST,text)
        self.assertIn('17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264',text)
        self.assertNotIn('BuildPlayer',text);self.assertNotIn('unity-builder',text)
        self.assertNotIn('workflow_dispatch:',text)
        self.assertIn('contents: read',text);self.assertIn('actions: read',text)
        self.assertIn('persist-credentials: false',text)



import journey_vehicle_contact_report as reports


def synthetic_report(expectation=None,pins=None,complete=False):
    if expectation is None:
        rows=[dict(path=f'Assets/Fixture/{i:04}.asset',sha256='a'*64,bytes=1,kind='asset',packageName='',packageVersion='') for i in range(772)]
        rows += [dict(path=f'Packages/com.unity.render-pipelines.universal/Fixture/{i:04}.shader',sha256='a'*64,bytes=1,kind='package',packageName='com.unity.render-pipelines.universal',packageVersion='17.3.0') for i in range(24)]
        expectation=dict(dependencies=rows,consumerCommit='c'*40)
    pins=pins or {p:'d'*64 for p in reports.SOURCE_REQUIRED}
    input_sha=pins.get(reports.INPUT_PATH,'b'*64)
    report=dict(schemaVersion=1,status='fixture-incomplete',failureCode='',unityVersion='6000.3.19f1',inputRoute=reports.INPUT_ROUTE,
        queryRoute=reports.QUERY_ROUTE,naturalRoute=reports.NATURAL_ROUTE,referenceProducerRunId='38054694730',
        proxyExtents=dict(x=1.05,y=1.12,z=2.7),proxyCenterY=1.45,maximumDeltaTime=.3333333,
        replayDetached=False,sceneUnloaded=False,sourceFilesUnchanged=False,anySyntheticLockReleased=False,anyNaturalProxyOverlap=False,
        dependencyCheck=dict(status='verified-native-closure',inputSha256=input_sha,failureCode='',passed=True,expectedCount=796,actualCount=796,
            actualDependencies=copy.deepcopy(expectation['dependencies']),mismatches=[]),
        sourceFiles=[dict(path=p,sha256=pins[p]) for p in sorted(reports.SOURCE_REQUIRED)],colliders=[],cases=[])
    if complete:
        vec=lambda:dict(x=0,y=0,z=0)
        for name,placement,dt,throttle in reports.CASES:
            fps=round(1/dt)
            if placement=='no-beast': phases=['baseline']*fps
            elif placement=='synthetic-overlap': phases=['live']*fps+['after-death-same-held-direction']*fps
            elif placement=='wall-and-ram-control': phases=['control']*120
            elif placement=='synthetic-self-buffer-saturation': phases=['capacity']*6
            else:phases=['natural-after-approach-W']*60+['natural-after-approach-S']*60+['natural-after-death-S']*60
            frames=[dict(frame=i,rawCount=0,allCount=0,vehicleHealth=100,phase=phase,state='Playing',control='Driving',dt=dt,throttle=throttle,
                speedBefore=0,speedAtCast=0,speedAfter=0,intendedDistance=0,actualDistance=0,predictedAllowed=0,castExecuted=False,rawSaturated=False,
                powerConnected=False,before=vec(),after=vec(),center=vec(),forward=vec(),overlaps=[],rawHits=[],allHits=[],motorBufferHits=[],obstacleEvents=[])
                for i,phase in enumerate(phases)]
            approach=[] if placement!='exterior-spawn-production-ai' else [dict(step=0,healthBefore=100,healthAfter=100,actualUpdateDelta=dt,
                positions=[vec(),vec()],phases=['Stalk','Stalk'],proxyOverlaps=[])]
            report['cases'].append(dict(name=name,placement=placement,outcome='recorded',dt=dt,throttle=throttle,requestedCapacity=0,actualCapacity=0,
                ramInstalled=False,liveStationary=False,deathConfirmed=False,released=False,baselineMoved=True,wallHeld=False,start=vec(),end=vec(),
                actorColliders=[],frames=frames,approach=approach))
        report.update(status='completed',replayDetached=True,sceneUnloaded=True,sourceFilesUnchanged=True)
    return report,expectation,input_sha,pins


class OriginalReportValidation(unittest.TestCase):
    def test_complete_synthetic_shape_is_never_gameplay_acceptance(self):
        args=synthetic_report(complete=True); result=reports.verify_native_report(*args)
        self.assertTrue(result['diagnosticComplete']);self.assertFalse(result['gameplayAccepted']);self.assertEqual(result['caseCount'],33)
        self.assertEqual(result['frameCount'],2128)

    def test_incomplete_report_preserves_exact_mismatched_dependency_paths(self):
        args=synthetic_report();dep=args[0]['dependencyCheck'];row=dep['actualDependencies'][-1]
        row['sha256']='e'*64;dep.update(passed=False,status='failed',failureCode='DEPENDENCY_VERIFICATION_FAILED',mismatches=[row['path']])
        result=reports.verify_native_report(*args)
        self.assertFalse(result['diagnosticComplete']);self.assertEqual(result['dependencyMismatchCount'],1)
        dep['mismatches']=[]
        with self.assertRaises(ValueError):reports.verify_native_report(*args)

    def test_unknown_keys_private_paths_or_wrong_source_pins_fail_closed(self):
        for mutation in (
            lambda a:a[0].update(privateExtra='never export'),
            lambda a:a[0]['sourceFiles'][0].update(path='/home/runner/private'),
            lambda a:a[0]['sourceFiles'][0].update(sha256='e'*64),
            lambda a:a[0].update(failureCode='private exception /home/runner'),
            lambda a:a[0].update(queryRoute='rewritten observations')):
            args=synthetic_report();mutation(args)
            with self.assertRaises(ValueError):reports.verify_native_report(*args)

    def test_completed_report_requires_every_expected_case_frame_and_source(self):
        for mutation in (
            lambda r:r['cases'].pop(),lambda r:r['cases'][0]['frames'].pop(),
            lambda r:r['sourceFiles'].pop(),lambda r:r['cases'][0].update(name='unknown')):
            args=synthetic_report(complete=True);mutation(args[0])
            with self.assertRaises(ValueError):reports.verify_native_report(*args)

    def test_false_source_or_cleanup_cannot_be_complete(self):
        for key in ('replayDetached','sceneUnloaded','sourceFilesUnchanged'):
            args=synthetic_report(complete=True);args[0][key]=False
            self.assertFalse(reports.verify_native_report(*args)['diagnosticComplete'])

    def test_wrong_raw_count_nonfinite_or_unknown_collider_rejected(self):
        for mutation in (
            lambda f:f.update(rawCount=32),lambda f:f.update(speedAfter=float('nan')),
            lambda f:f.update(overlaps=[999])):
            args=synthetic_report(complete=True);mutation(args[0]['cases'][0]['frames'][0])
            with self.assertRaises(ValueError):reports.verify_native_report(*args)



class ActualRunnerShellRoute(unittest.TestCase):
    OLD_ROUTE = '  if [[ "${GITHUB_REF:-}" == refs/heads/journey-tracer-shader-fix-6648 ]]; then\n'
    NEW_ROUTE = ('  if [[ "${GITHUB_REF:-}" == refs/heads/journey-vehicle-contact-ed21 ]]; then\n'
        '    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/journey_vehicle_contact_probe.py" dispatch\n'
        '  elif [[ "${GITHUB_REF:-}" == refs/heads/journey-tracer-shader-fix-6648 ]]; then\n')

    def runner(self,source,ref,event='push',extra=None):
        # Execute the actual Bash admission prefix. The cut is before license,
        # removal, disk, Docker or network work. Spies record executable/arguments.
        marker='test -n "${UNITY_LICENSE:-}"'
        self.assertEqual(source.count(marker),1)
        prefix=source[:source.index(marker)]
        self.assertNotIn('sudo',prefix);self.assertNotIn('docker',prefix)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);script=root/'prepare_runner.sh';script.write_text(prefix)
            record=root/'route.json'
            for name in ('journey_vehicle_contact_probe.py','journey_tracer_dispatch.py','journey_rebuild_dispatch.py'):
                (root/name).write_text('import json,os,sys\nfrom pathlib import Path\nPath(os.environ["ROUTE_RECORD"]).write_text(json.dumps(dict(name=Path(__file__).name,args=sys.argv[1:])))\n')
            env=dict(PATH='/usr/bin:/bin',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',GITHUB_ACTIONS='true',
                GITHUB_EVENT_NAME=event,GITHUB_REF=ref,ROUTE_RECORD=str(record))
            env.update(extra or {})
            result=subprocess.run(['/usr/bin/bash',str(script)],env=env,text=True,capture_output=True,timeout=10)
            return result.returncode,json.loads(record.read_text()) if record.exists() else None

    def source(self):return (probe.TASK/'scripts/prepare_runner.sh').read_text()

    def test_actual_shell_routes_new_and_legacy_branches(self):
        source=self.source()
        for branch,name,arg in (
            ('journey-vehicle-contact-ed21','journey_vehicle_contact_probe.py','dispatch'),
            ('journey-tracer-shader-fix-6648','journey_tracer_dispatch.py','--verify-only'),
            ('journey-linux-export-recovery-938','journey_rebuild_dispatch.py','--verify-only')):
            with self.subTest(branch=branch):
                code,record=self.runner(source,'refs/heads/'+branch)
                self.assertEqual(code,0);self.assertEqual(record,dict(name=name,args=[arg]))
        self.assertEqual(self.runner(source,'refs/heads/main','workflow_dispatch'),(0,None))

    def test_actual_old_shell_reproduces_recorded_wrong_dispatcher(self):
        current=self.source();self.assertEqual(current.count(self.NEW_ROUTE),1)
        old=current.replace(self.NEW_ROUTE,self.OLD_ROUTE,1)
        self.assertEqual(hashlib.sha256(old.encode()).hexdigest(),'243a14295864364d73726374d0d45793f0acb38948b4d8f1b8df8149e4f9ff94')
        code,record=self.runner(old,probe.REF)
        self.assertEqual(code,0);self.assertEqual(record,dict(name='journey_rebuild_dispatch.py',args=['--verify-only']))
        # This is the historical routing defect; the new shell must not repeat it.
        self.assertNotEqual(self.runner(current,probe.REF)[1],record)

    def test_actual_shell_keeps_hosted_linux_action_gate(self):
        for key,value in dict(RUNNER_ENVIRONMENT='self-hosted',RUNNER_OS='Windows',GITHUB_ACTIONS='false').items():
            with self.subTest(key=key):
                code,record=self.runner(self.source(),probe.REF,extra={key:value})
                self.assertNotEqual(code,0);self.assertIsNone(record)

    def test_consumer_parent_is_separate_from_actual_production(self):
        self.assertEqual(probe.BASE,'da02a3a4a16c09c18cf63bc99499291b4ff1af54')
        self.assertEqual(probe.PREPARED_PRODUCTION_BASE,'ed21b214f327b3ec439b9b3d7fec6b41a16d8a85')
        self.assertEqual(probe.PRODUCER['commit'],probe.PREPARED_PRODUCTION_BASE)
        self.assertNotEqual(probe.BASE,probe.PREPARED_PRODUCTION_BASE)



if __name__ == "__main__": unittest.main()
