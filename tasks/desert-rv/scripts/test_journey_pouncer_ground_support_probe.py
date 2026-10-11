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
import journey_pouncer_ground_support_probe as probe


def identity_fixture():
    head = 'a' * 40
    env = dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=probe.REPOSITORY, GITHUB_REPOSITORY_VISIBILITY='public',
        RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Linux', GITHUB_ACTOR=probe.OWNER_NAME,
        GITHUB_TRIGGERING_ACTOR=probe.OWNER_NAME, GITHUB_EVENT_NAME='push', GITHUB_REF=probe.REF,
        GITHUB_WORKFLOW_REF=probe.REPOSITORY + '/' + probe.WORKFLOW + '@' + probe.REF,
        GITHUB_SHA=head, GITHUB_RUN_ID='123', GITHUB_RUN_ATTEMPT='1', GITHUB_EVENT_PATH='/tmp/fixture-event.json')
    event = dict(before=probe.BASE, after=head, ref=probe.REF, created=False, deleted=False, forced=False,
        repository=dict(full_name=probe.REPOSITORY, private=False, fork=False, default_branch='main', owner=dict(login=probe.OWNER_NAME)),
        sender=dict(login=probe.OWNER_NAME), head_commit=dict(id=head))
    digest = 'b' * 64
    raw = json.dumps(dict(schema=1, requestId=probe.NONCE, baseCommit=probe.BASE,
        sourceStateSha256=digest, producerArtifactSha256=probe.PRODUCER['artifactSha256'])).encode()
    return [env,event,head,[probe.BASE],raw,raw,False,sorted(probe.CHANGED_FILES),digest]


class Boundaries(unittest.TestCase):
    def test_diagnostic_errors_preserve_only_owned_codes_or_exception_class(self):
        self.assertEqual(probe.failure_code(ValueError('R3_NATURAL_CONTACT_DEPENDENCY_PATH')),'R3_NATURAL_CONTACT_DEPENDENCY_PATH')
        for message in ('private /home/runner/secret','R3_NATURAL_CONTACT_OK\nprivate-secret','R3_NATURAL_CONTACT_'+'X'*200):
            value=probe.failure_code(ValueError(message))
            self.assertEqual(value,'R3_NATURAL_CONTACT_EXCEPTION_VALUEERROR')
            self.assertNotIn('secret',value)
        self.assertEqual(probe.failure_code(FileNotFoundError('/home/runner/private')),'R3_NATURAL_CONTACT_EXCEPTION_FILENOTFOUNDERROR')
        self.assertEqual(probe.failure_code(RuntimeError('private')),'R3_NATURAL_CONTACT_EXCEPTION_OTHERERROR')

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

    def test_failed_xml_exports_first_project_frame_and_fixed_codes_without_private_text(self):
        with tempfile.TemporaryDirectory() as d,mock.patch.object(probe,'ARTIFACTS',Path(d)):
            raw=f'''<test-run result="Failed" total="1" passed="0" failed="1" skipped="0" inconclusive="0"><test-case fullname="{probe.TEST}" result="Failed"><failure><message><![CDATA[System.NullReferenceException: hidden-secret /home/private. DEPENDENCY_BYTES_DIFFER]]></message><stack-trace><![CDATA[  at System.Reflection.RuntimeMethodInfo.Invoke (hidden-secret) [0x01] in /private/private.cs:12
  at DesertRV.Tests.JourneyR3ContinuousContactTests.VerifyDependencies () [0x23] in /github/private/workspace/Assets/DesertRV/Tests/PlayMode/JourneyR3ContinuousContactTests.cs:421
]]></stack-trace></failure></test-case></test-run>'''
            (Path(d)/'result.xml').write_text(raw)
            value=probe.inspect_xml();failure=value['failure']
            self.assertEqual(value['result'],'Failed')
            self.assertEqual(failure['exceptionClasses'],['NullReferenceException'])
            self.assertEqual(failure['assertionCodes'],['DEPENDENCY_BYTES_DIFFER'])
            self.assertEqual(failure['firstProjectStackFrame'],dict(method='DesertRV.Tests.JourneyR3ContinuousContactTests.VerifyDependencies',sourceFile='Assets/DesertRV/Tests/PlayMode/JourneyR3ContinuousContactTests.cs',line=421))
            self.assertEqual(len(failure['messageSha256']),64)
            safe=json.dumps(value)
            self.assertNotIn('hidden-secret',safe);self.assertNotIn('/github/private',safe);self.assertNotIn('/home/private',safe)

    def test_unity_colon_stack_keeps_actual_paw_failure_as_failure(self):
        xml=probe.ET.fromstring('<test-case><failure><message>[Error] POUNCER_PAW_CONTACT_FAILED: private event body</message><stack-trace>UnityEngine.Debug:LogError (object)\nDesertRV.PouncerPawContactConstraint:LateUpdate () (at Assets/DesertRV/Runtime/PouncerPawContactConstraint.cs:71)</stack-trace></failure></test-case>')
        failure=probe.bounded_xml_failure(xml)
        self.assertEqual(failure['assertionCodes'],['POUNCER_PAW_CONTACT_FAILED'])
        self.assertEqual(failure['firstProjectStackFrame'],dict(method='DesertRV.PouncerPawContactConstraint.LateUpdate',sourceFile='Assets/DesertRV/Runtime/PouncerPawContactConstraint.cs',line=71))
        self.assertNotIn('private event body',json.dumps(failure))

    def test_preserves_owned_validator_code_without_arbitrary_exception_text(self):
        self.assertEqual(probe.failure_code(ValueError('R3_CONTINUOUS_CLOSED_KEYS_BEAST')),'R3_CONTINUOUS_CLOSED_KEYS_BEAST')
        for message in ('R3_CONTINUOUS_PRIVATE /home/account','R3_CONTINUOUS_BAD\nprivate','OtherError secret'):
            self.assertEqual(probe.failure_code(ValueError(message)),'R3_NATURAL_CONTACT_EXCEPTION_VALUEERROR')

    def test_refuses_cleanup_without_matching_owner(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);copy_path=root/'journey-pouncer-ground-support-project';copy_path.mkdir()
            keep=copy_path/'keep';keep.write_text('untouched')
            with mock.patch.multiple(probe,TASK=root,COPY=copy_path,OWNER=root/'absent',PROJECT=root/'unity'):
                with self.assertRaises(Exception): probe.cleanup()
            self.assertEqual(keep.read_text(),'untouched')


class ProducerAndIsolation(unittest.TestCase):
    def test_exact_producer_metadata_rejects_stale_or_failed_inputs(self):
        run = dict(id=probe.PRODUCER['runId'],run_attempt=1,head_sha=probe.PRODUCER['commit'],
            head_branch='wip/combat-feedback-20261010',path='.github/workflows/desert-rv-tracer-shader-prepare.yml',
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
        self.assertEqual(text.count('uses: game-ci/unity-test-runner@'),2)
        self.assertIn('testMode: playmode',text)
        self.assertIn('-assemblyNames DesertRV.PlayModeTests -testFilter '+probe.FOCUSED_TEST+';'+probe.TEST,text)
        self.assertIn('testMode: editmode',text)
        self.assertIn('seal-derived',text)
        self.assertIn('17406791cf1e438bea2dac20671668e05d83db5ed38c916744815db4584a8264',text)
        self.assertNotIn('BuildPlayer',text);self.assertNotIn('unity-builder',text)
        self.assertNotIn('workflow_dispatch:',text)
        self.assertIn('contents: read',text);self.assertIn('actions: read',text)
        self.assertIn('persist-credentials: false',text)



class ActualRunnerShellRoute(unittest.TestCase):
    OLD_ROUTE = '  if [[ "${GITHUB_REF:-}" == refs/heads/journey-tracer-shader-fix-6648 ]]; then\n'
    NEW_ROUTE = ('  if [[ "${GITHUB_REF:-}" == refs/heads/journey-pouncer-ground-support-2915 ]]; then\n'
        '    /usr/bin/python3 "$(dirname "${BASH_SOURCE[0]}")/journey_pouncer_ground_support_probe.py" dispatch\n'
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
            for name in ('journey_pouncer_ground_support_probe.py','journey_tracer_dispatch.py','journey_rebuild_dispatch.py'):
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
            ('journey-pouncer-ground-support-2915','journey_pouncer_ground_support_probe.py','dispatch'),
            ('journey-tracer-shader-fix-6648','journey_tracer_dispatch.py','--verify-only'),
            ('journey-linux-export-recovery-938','journey_rebuild_dispatch.py','--verify-only')):
            with self.subTest(branch=branch):
                code,record=self.runner(source,'refs/heads/'+branch)
                self.assertEqual(code,0);self.assertEqual(record,dict(name=name,args=[arg]))
        self.assertEqual(self.runner(source,'refs/heads/main','workflow_dispatch'),(0,None))

    def test_actual_shell_keeps_hosted_linux_action_gate(self):
        for key,value in dict(RUNNER_ENVIRONMENT='self-hosted',RUNNER_OS='Windows',GITHUB_ACTIONS='false').items():
            with self.subTest(key=key):
                code,record=self.runner(self.source(),probe.REF,extra={key:value})
                self.assertNotEqual(code,0);self.assertIsNone(record)

    def test_prepared_producer_is_separate_from_r1_consumer_parent(self):
        self.assertEqual(probe.PRODUCER['commit'],probe.PRODUCTION_BASE)
        self.assertEqual(probe.BASE,probe.PRODUCTION_BASE)
        self.assertEqual(probe.PRODUCER['runId'],38091066745)
        self.assertNotEqual(identity_fixture()[2],probe.PRODUCER['commit'])


def closure_fixture(root):
    project = root/'unity'
    assets = {}; before = []; dependencies = []
    def dependency(name, owner, package='', version=''):
        raw = ('fixture '+name).encode(); pin = probe.raw_pin(raw)
        row = dict(path=name, **pin, kind='package' if package else 'asset', packageName=package, packageVersion=version, owner=owner)
        dependencies.append(row)
        if owner == 'source':
            path=project/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            before.append(dict(path=probe.PREFIX+name,sha256=pin['sha256'],size=pin['bytes']))
        elif owner != 'official-package': assets[name]=raw
    for owner,count,prefix in (('source',318,'Assets/Original'),('strict',32,'Assets/DesertRV/CandidateArtImports/Fixture'),('generated',36,'Assets/Generated')):
        for i in range(count):
            for suffix in ('.asset','.asset.meta'):dependency(f'{prefix}/{i:03}'+suffix,owner)
    for i in range(12):
        for suffix in ('.shader','.shader.meta'):dependency(f'Packages/com.unity.render-pipelines.universal/Fixture/{i:02}'+suffix,'official-package','com.unity.render-pipelines.universal','17.3.0')
    controls=[]
    for name,raw in [('Packages/manifest.json',b'{}'),('Packages/packages-lock.json',json.dumps(dict(dependencies={'com.unity.render-pipelines.universal':dict(version='17.3.0',source='registry',url='https://packages.unity.com')})).encode()),('ProjectSettings/ProjectVersion.txt',b'm_EditorVersion: 6000.3.19f1\n')]:
        path=project/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        pin=probe.raw_pin(raw);controls.append(dict(path=name,**pin));before.append(dict(path=probe.PREFIX+name,sha256=pin['sha256'],size=pin['bytes']))
    after=copy.deepcopy(before)
    for name in sorted(probe.TEST_ADDITIONS | set(probe.NEW_DEPENDENCIES)):
        raw=b'test-only fixture';path=project/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        after.append(dict(path=probe.PREFIX+name,sha256=probe.sha(raw),size=len(raw)))
    return project, assets, dict(packageControls=controls,dependencies=dependencies), dict(files=before,restoredFiles=[]), dict(files=after,restoredFiles=[])


class ExactCurrentProduction(unittest.TestCase):
    def test_complete_current_dependency_closure_preserves_producer_and_has_no_override(self):
        with tempfile.TemporaryDirectory() as d:
            project,assets,receipt,before,after=closure_fixture(Path(d))
            original=copy.deepcopy(receipt)
            with mock.patch.multiple(probe,PROJECT=project,UNITY_CHANGES=probe.TEST_ADDITIONS|set(probe.NEW_DEPENDENCIES)):
                result=probe.consumer_input(assets,receipt,before,after,'c'*40)
            self.assertEqual(len(result['dependencies']),798)
            self.assertEqual(sum(r['kind']=='package' for r in result['dependencies']),24)
            self.assertEqual([r['path'] for r in result['dependencyChanges']],list(probe.NEW_DEPENDENCIES))
            self.assertTrue(all(r['before'] is None for r in result['dependencyChanges']))
            self.assertEqual(result['currentProductionCommit'],'c'*40)
            self.assertEqual(result['producerCommit'],probe.PRODUCTION_BASE)
            self.assertNotEqual(result['consumerCommit'],probe.BASE)
            self.assertEqual(receipt,original)

    def test_rejects_runtime_change_even_outside_prepared_dependency_closure(self):
        with tempfile.TemporaryDirectory() as d:
            project,assets,receipt,before,after=closure_fixture(Path(d))
            # An original source outside the receipt still belongs to the exact source union.
            raw=b'original';name='Assets/Other.cs';(project/name).write_bytes(raw)
            row=dict(path=probe.PREFIX+name,sha256=probe.sha(raw),size=len(raw))
            before['files'].append(row);after['files'].append(dict(row,sha256='a'*64))
            with mock.patch.multiple(probe,PROJECT=project,UNITY_CHANGES=probe.TEST_ADDITIONS|set(probe.NEW_DEPENDENCIES)),self.assertRaisesRegex(ValueError,'EXPLICIT_PRODUCTION_SOURCE_OVERLAY'):
                probe.consumer_input(assets,receipt,before,after,'c'*40)

    def test_rejects_missing_extra_test_package_pin_and_producer_consumer_alias(self):
        for mutation in ('missing-test','extra-source','package-pin','source-pin','artifact-pin','consumer-alias'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
                project,assets,receipt,before,after=closure_fixture(Path(d));head='c'*40
                if mutation=='missing-test': after['files'].pop()
                if mutation=='extra-source': after['files'].append(dict(path=probe.PREFIX+'Assets/Other.cs',sha256='a'*64,size=1))
                if mutation=='package-pin': receipt['packageControls'][0]['sha256']='a'*64
                if mutation=='source-pin': receipt['dependencies'][0]['sha256']='a'*64
                if mutation=='artifact-pin': assets[next(iter(assets))]=b'changed'
                if mutation=='consumer-alias':head=probe.BASE
                with mock.patch.multiple(probe,PROJECT=project,UNITY_CHANGES=probe.TEST_ADDITIONS|set(probe.NEW_DEPENDENCIES)),self.assertRaises(ValueError):
                    probe.consumer_input(assets,receipt,before,after,head)

    def test_exact_route_rejects_unreviewed_changed_file_or_missing_delta(self):
        for changed in (sorted(probe.CHANGED_FILES)+['README.md'],sorted(probe.CHANGED_FILES-{probe.WORKFLOW})):
            args=identity_fixture();args[7]=changed
            with self.assertRaisesRegex(ValueError,'REQUEST_GIT'):probe.validate_identity(*args)


class OwnedCopyAndExport(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.task=self.root/'tasks/desert-rv';self.task.mkdir(parents=True)
        self.project=self.task/'unity';self.project.mkdir()
        self.copy=self.task/'journey-pouncer-ground-support-project'
        self.env=dict(GITHUB_SHA='c'*40,GITHUB_RUN_ID='123',GITHUB_RUN_ATTEMPT='1',GITHUB_OUTPUT=str(self.root/'output'),NATIVE_OUTCOME='failure',AUTHOR_OUTCOME='success')
        self.patch=mock.patch.multiple(probe,ROOT=self.root,TASK=self.task,PROJECT=self.project,COPY=self.copy,OWNER=self.task/'owner.json',PRIVATE=self.task/'private',ARTIFACTS=self.task/'artifacts',AUTHOR_ARTIFACTS=self.task/'author-artifacts',SEALED=self.task/'private/derived-owner.json',DERIVED=self.task/'private/derived-scenes.json',EXPORT=self.task/'export',REPORT=self.task/'export/report.json')
        self.patch.start();self.envpatch=mock.patch.dict(os.environ,self.env);self.envpatch.start()
        self.source=(self.root/probe.SOURCE_NAME);self.source.write_text('{}')
        self.rows=[]
        for name in [*dict.fromkeys([*probe.SNAPSHOT_SOURCES,*probe.SCENES,*[n for p in probe.FOCUSED_SOURCES for n in (p,p+'.meta')]]),'Packages/manifest.json','Packages/packages-lock.json',probe.SETTINGS]:
            raw=b'{}' if name.startswith('Packages/') else b'%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n--- !u!129 &1\nPlayerSettings:\n  productName: Fixture\n' if name==probe.SETTINGS else b'public test source'
            p=self.project/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            self.rows.append(dict(path=probe.PREFIX+name,sha256=probe.sha(raw),size=len(raw)))
        self.after=dict(files=self.rows,restoredFiles=[]);self.expectation=dict(consumerCommit='c'*40,dependencies=[])
        import journey_pouncer_support_reports as support_reports
        self.beforepatch=mock.patch.object(support_reports,'BEFORE',tuple(probe.sha((self.project/n).read_bytes()) for n in probe.SCENES));self.beforepatch.start()
    def tearDown(self):
        self.beforepatch.stop();self.envpatch.stop();self.patch.stop();self.temp.cleanup()
    def stage_fixture(self):
        with mock.patch.object(probe.source,'verify_source_state'):
            probe.create_copy(self.after,{'Assets/Prepared.asset':b'exact prepared'},self.expectation)
    def test_copy_is_complete_owned_and_cleanup_does_not_follow_child_links(self):
        self.stage_fixture();owner=probe.load_owner()
        self.assertEqual(probe.protected_inventory(self.copy)[0],owner['union'])
        self.assertEqual(probe.read(self.copy/probe.AUTHOR_INPUT),self.expectation)
        outside=self.root/'outside';outside.mkdir();keep=outside/'keep';keep.write_text('untouched')
        (self.copy/'Library').symlink_to(outside,target_is_directory=True)
        probe.cleanup();self.assertFalse(self.copy.exists());self.assertEqual(keep.read_text(),'untouched')
    def test_copy_refuses_unlisted_formal_input_and_asset_collision(self):
        (self.project/'Assets/unlisted.txt').write_text('unexpected')
        with mock.patch.object(probe.source,'verify_source_state'),self.assertRaisesRegex(ValueError,'SOURCE_UNION'):
            probe.create_copy(self.after,{},self.expectation)
        self.assertFalse(self.copy.exists())
        (self.project/'Assets/unlisted.txt').unlink()
        with mock.patch.object(probe.source,'verify_source_state'),self.assertRaisesRegex(ValueError,'SOURCE_UNION'):
            probe.create_copy(self.after,{probe.SNAPSHOT_SOURCES[0]:b'override'},self.expectation)
        self.assertFalse(self.copy.exists())

    def test_cleanup_refuses_changed_marker_and_other_run(self):
        self.stage_fixture();marker=self.copy/probe.MARKER;old=marker.read_bytes();marker.write_text('{}')
        with self.assertRaises(ValueError):probe.cleanup()
        self.assertTrue(self.copy.exists());marker.write_bytes(old)
        with mock.patch.dict(os.environ,GITHUB_RUN_ID='124'),self.assertRaises(ValueError):probe.cleanup()
        self.assertTrue(self.copy.exists())
    def test_failed_native_xml_and_source_invariance_survive_missing_report(self):
        self.stage_fixture();probe.ARTIFACTS.mkdir();(probe.ARTIFACTS/'result.xml').write_text(f'<test-run result="Failed" total="1" passed="0" failed="1" skipped="0" inconclusive="0"><test-case fullname="{probe.TEST}" result="Failed"/></test-run>')
        with mock.patch.object(probe,'dispatch'),mock.patch.object(probe.source,'verify_source_state'),mock.patch.object(probe,'git',return_value=b''):
            self.assertEqual(probe.finish(),2)
        result=probe.read(probe.REPORT)
        self.assertTrue(result['sourceUnchanged']);self.assertTrue(result['isolatedInputsVerified']);self.assertIsNone(result['xml'])
        self.assertIn('EXACT_PLAYMODE_CASES_XML_UNAVAILABLE',result['checks'])
        self.assertFalse(result['approved']);self.assertEqual(result['nativeOutcome'],'failure')
        self.assertNotIn(str(self.root),probe.REPORT.read_text())
        self.assertEqual({p.name for p in probe.EXPORT.iterdir()},{'report.json','consumer-SOURCE-STATE.json','author-input.json','source'})
    def prepare_partial_report(self, completed=False, seal_mutation=None):
        from test_journey_r3_continuous_contact_report import fixture
        import journey_r3_continuous_contact_report as reports
        native,expected,_,_=fixture()
        self.expectation.update(expected);self.expectation['consumerCommit']=self.env['GITHUB_SHA']
        for base in reports.SOURCE_PATHS:
            for name in (base,base+'.meta'):
                path=self.project/name
                if path.exists():continue
                raw=b'public host fixture source';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
                self.rows.append(dict(path=probe.PREFIX+name,sha256=probe.sha(raw),size=len(raw)))
        self.stage_fixture();owner=probe.load_owner()
        self.seal_fixture(owner, seal_mutation)
        owner,_=probe.active_owner(owner)
        pins={name:row['sha256'] for name,row in owner['union'].items()}
        pins[probe.INPUT_REL]=owner['inputSha256']
        pins[probe.INPUT_REL.replace('.json','.sha256')]=probe.sha(probe.file_bytes((self.copy/probe.INPUT_REL).with_suffix('.sha256')))
        native.update(status='completed' if completed else 'fixture-incomplete',consumerCommit=self.env['GITHUB_SHA'])
        native['dependencyCheck']['inputSha256']=owner['inputSha256']
        for row in native['sourceFiles']:row['sha256']=pins[row['path']]
        if not completed:
            native['sequences']=native['sequences'][:1];native['sequences'][0]['completed']=False;native['sequences'][0]['frames']=native['sequences'][0]['frames'][:5]
        probe.ARTIFACTS.mkdir();(probe.ARTIFACTS/'result.xml').write_text(f'<test-run result="Failed" total="2" passed="1" failed="1" skipped="0" inconclusive="0"><test-case fullname="{probe.FOCUSED_TEST}" result="Passed"/><test-case fullname="{probe.TEST}" result="Failed"><failure><message>POUNCER_PAW_CONTACT_FAILED</message><stack-trace>DesertRV.PouncerPawContactConstraint:LateUpdate () (at Assets/DesertRV/Runtime/PouncerPawContactConstraint.cs:71)</stack-trace></failure></test-case></test-run>')
        return native

    def seal_fixture(self, owner, before_seal=None):
        # Synthetic scenes model the real stage -> native author -> seal -> finish flow.
        # Only dispatch/source provenance is mocked; isolation, XML, receipt validators
        # and actual files/input/owner hashes are exercised by the production helper.
        from test_journey_pouncer_support_reports import author_fixture, focused_fixture
        probe.PRIVATE.mkdir()
        template=copy.deepcopy(self.expectation)
        for row in template['dependencies']:
            row.update(kind='asset',packageName='',packageVersion='')
        for i,name in enumerate(probe.SCENES):
            template['dependencies'][i]=dict(path=name,kind='asset',packageName='',packageVersion='',**owner['union'][name])
            with (self.copy/name).open('ab') as stream:stream.write(b' derived production binding')
        template['dependencies'].sort(key=lambda r:r['path'])
        template['productionSourceOverlay']=copy.deepcopy(template['dependencyChanges'])
        probe.write_new(probe.PRIVATE/'consumer-template.json',template)
        expectation,scenes,_=probe.derive_expectation(owner)
        native,_,_=author_fixture()
        native.update(sourceCommit=self.env['GITHUB_SHA'],inputSha256=owner['inputSha256'],
            scenes=[dict(row,actorCount=3,pouncerCount=2,supportCount=2) for row in scenes],dependencies=expectation['dependencies'])
        probe.write_new(self.copy/probe.AUTHOR_RAW,native)
        probe.AUTHOR_ARTIFACTS.mkdir()
        names=(probe.AUTHOR_TEST,*probe.GENERIC_TESTS)
        cases=''.join(f'<test-case fullname="{name}" result="Passed"/>' for name in names)
        (probe.AUTHOR_ARTIFACTS/'result.xml').write_text(f'<test-run result="Passed" total="{len(names)}" passed="{len(names)}" failed="0" skipped="0" inconclusive="0">{cases}</test-run>')
        if before_seal: before_seal()
        with mock.patch.object(probe,'dispatch'),mock.patch.object(probe.source,'verify_source_state'):
            probe.seal_derived()
        active,sealed=probe.active_owner(owner)
        focused=focused_fixture();focused.update(sourceCommit=self.env['GITHUB_SHA'],derivedReceiptSha256=sealed['derivedReceiptSha256'],inputSha256=sealed['inputs'][probe.FOCUSED_INPUT])
        probe.write_new(self.copy/probe.FOCUSED_RAW,focused)

    def test_seal_refuses_unapproved_runtime_or_meta_change(self):
        def mutate(): (self.copy/probe.SNAPSHOT_SOURCES[0]).write_bytes(b'unapproved runtime')
        with self.assertRaisesRegex(ValueError,'EXACT_DERIVED_SCENE_CHANGES'):
            self.prepare_partial_report(seal_mutation=mutate)
        self.assertFalse(probe.SEALED.exists());self.assertFalse((self.copy/probe.INPUT_REL).exists())

    def test_seal_refuses_one_missing_derived_scene(self):
        def mutate(): (self.copy/probe.SCENES[0]).write_bytes((self.project/probe.SCENES[0]).read_bytes())
        with self.assertRaisesRegex(ValueError,'EXACT_DERIVED_SCENE_CHANGES'):
            self.prepare_partial_report(seal_mutation=mutate)
        self.assertFalse(probe.SEALED.exists())

    def test_seal_requires_all_fourteen_exact_passed_native_cases(self):
        def mutate():
            p=probe.AUTHOR_ARTIFACTS/'result.xml';p.write_text(p.read_text().replace(probe.GENERIC_TESTS[0],'Unknown.Native.Case'))
        with self.assertRaisesRegex(ValueError,'XML_EXACT_CASE'):
            self.prepare_partial_report(seal_mutation=mutate)
        self.assertFalse(probe.SEALED.exists())

    def test_seal_refuses_failed_original_serialized_state_proof(self):
        def mutate():
            p=self.copy/probe.AUTHOR_RAW;v=probe.read(p);v['existingSerializedStateUnchanged']=False;p.write_text(json.dumps(v))
        with self.assertRaises(ValueError):self.prepare_partial_report(seal_mutation=mutate)
        self.assertFalse(probe.SEALED.exists());self.assertFalse(probe.DERIVED.exists())

    def test_seal_refuses_changed_native_dependency_snapshot(self):
        def mutate():
            p=self.copy/probe.AUTHOR_RAW;v=probe.read(p);v['dependencies'][0]['sha256']='f'*64;p.write_text(json.dumps(v))
        with self.assertRaises(ValueError):self.prepare_partial_report(seal_mutation=mutate)
        self.assertFalse(probe.SEALED.exists())

    def test_sealed_derivative_keeps_original_owner_and_rejects_later_input_change(self):
        self.prepare_partial_report();owner=probe.load_owner();active,sealed=probe.active_owner(owner)
        receipt=probe.read(probe.DERIVED)
        self.assertEqual(receipt['producer'],probe.PRODUCER)
        self.assertEqual([r['path'] for r in receipt['scenes']],sorted(probe.SCENES))
        for path in probe.SCENES:
            self.assertNotEqual(owner['union'][path],active['union'][path])
            self.assertEqual(owner['union'][path],probe.raw_pin((self.project/path).read_bytes()))
        p=self.copy/probe.FOCUSED_INPUT;p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'DERIVED_INPUT_CHANGED'):probe.active_owner(owner)

    def test_partial_original_bytes_export_but_native_failure_still_fails(self):
        native=self.prepare_partial_report();raw=(json.dumps(native,indent=1)+'\n').encode();(self.copy/probe.RAW_REL).write_bytes(raw)
        with mock.patch.object(probe,'dispatch'),mock.patch.object(probe.source,'verify_source_state'),mock.patch.object(probe,'git',return_value=b''):
            self.assertEqual(probe.finish(),2)
        result=probe.read(probe.REPORT)
        self.assertEqual(result['status'],'FAILED_OR_PARTIAL_DIAGNOSTIC_NOT_GAMEPLAY_ACCEPTANCE')
        self.assertEqual(result['xml']['result'],'Failed');self.assertEqual(result['nativeOutcome'],'failure')
        self.assertFalse(result['nativeSummary']['diagnosticComplete']);self.assertEqual(result['nativeSummary']['observedFrames'],5)
        self.assertEqual((probe.EXPORT/'native-r3-continuous-contact.json').read_bytes(),raw)
        self.assertIn('diagnostic_complete=false',(self.root/'output').read_text())

    def test_complete_strict_report_uses_raw_route_and_native_failed_xml_still_fails(self):
        native=self.prepare_partial_report(completed=True);raw=json.dumps(native).encode();(self.copy/probe.RAW_REL).write_bytes(raw)
        with mock.patch.object(probe,'dispatch'),mock.patch.object(probe.source,'verify_source_state'),mock.patch.object(probe,'git',return_value=b''):
            self.assertEqual(probe.finish(),2)
        result=probe.read(probe.REPORT)
        self.assertEqual((probe.EXPORT/result['nativeReport']['path']).read_bytes(),raw)
        self.assertTrue(result['nativeSummary']['diagnosticComplete']);self.assertEqual(result['nativeSummary']['observedFrames'],1212)
        self.assertIsNone(result['nativeRedactedReport']);self.assertIsNone(result['nativeReportRejection'])
        self.assertEqual(result['xml']['result'],'Failed');self.assertEqual(result['nativeOutcome'],'failure')
        self.assertIn('diagnostic_complete=false',(self.root/'output').read_text())
    def test_complete_strict_report_and_passed_native_remain_on_original_success_route(self):
        native=self.prepare_partial_report(completed=True);raw=json.dumps(native).encode();(self.copy/probe.RAW_REL).write_bytes(raw)
        producer_source=b'public host producer source';producer_receipt=b'public host producer receipt'
        (probe.PRIVATE/'prepared-input/generated').mkdir(parents=True,exist_ok=True)
        (probe.PRIVATE/'producer-SOURCE-STATE.json').write_bytes(producer_source)
        (probe.PRIVATE/'prepared-input/generated/receipt.json').write_bytes(producer_receipt)
        producer=dict(probe.PRODUCER,sourceStateSha256=probe.sha(producer_source),generatedReceiptSha256=probe.sha(producer_receipt))
        (probe.ARTIFACTS/'result.xml').write_text(f'<test-run result="Passed" total="2" passed="2" failed="0" skipped="0" inconclusive="0"><test-case fullname="{probe.FOCUSED_TEST}" result="Passed"/><test-case fullname="{probe.TEST}" result="Passed"/></test-run>')
        with mock.patch.object(probe,'dispatch'),mock.patch.object(probe.source,'verify_source_state'),mock.patch.object(probe,'git',return_value=b''),mock.patch.object(probe,'PRODUCER',producer),mock.patch.dict(os.environ,NATIVE_OUTCOME='success'):
            self.assertEqual(probe.finish(),0)
        result=probe.read(probe.REPORT)
        self.assertEqual(result['status'],'DIAGNOSTIC_COMPLETED_NOT_GAMEPLAY_ACCEPTANCE');self.assertEqual(result['checks'],[])
        self.assertEqual((probe.EXPORT/result['nativeReport']['path']).read_bytes(),raw)
        self.assertEqual(result['nativeSummary']['observedFrames'],1212);self.assertTrue(result['nativeSummary']['diagnosticComplete'])
        self.assertIsNone(result['nativeRedactedReport']);self.assertIsNone(result['nativeReportRejection'])
        self.assertFalse(result['approved']);self.assertFalse(result['gameplayReviewed'])
        self.assertIn('diagnostic_complete=true',(self.root/'output').read_text())

    def test_oversize_native_file_keeps_failure_evidence_without_reading_or_exporting_raw(self):
        self.prepare_partial_report();(self.copy/probe.RAW_REL).write_bytes(b' '*(probe.MAX_NATIVE_REPORT+1))
        with mock.patch.object(probe,'dispatch'),mock.patch.object(probe.source,'verify_source_state'),mock.patch.object(probe,'git',return_value=b''):
            self.assertEqual(probe.finish(),2)
        result=probe.read(probe.REPORT)
        self.assertIsNone(result['nativeReport']);self.assertIsNone(result['nativeRedactedReport'])
        self.assertEqual(result['xml']['result'],'Failed');self.assertEqual(result['nativeOutcome'],'failure')
        self.assertIn('BOUNDED_ORIGINAL_NATIVE_REPORT_UNAVAILABLE',result['checks'])
        self.assertFalse(any(p.name.startswith('native-r3-') for p in probe.EXPORT.iterdir()))
    def test_oversize_subtree_projects_safe_neighbor_frames_without_raw_export(self):
        native=self.prepare_partial_report();native['colliders']=[{}]*4097;raw=json.dumps(native).encode();(self.copy/probe.RAW_REL).write_bytes(raw)
        with mock.patch.object(probe,'dispatch'),mock.patch.object(probe.source,'verify_source_state'),mock.patch.object(probe,'git',return_value=b''):
            self.assertEqual(probe.finish(),2)
        result=probe.read(probe.REPORT);data=probe.read(probe.EXPORT/result['nativeRedactedReport']['path'])
        self.assertEqual(result['nativeReportRejection']['code'],'R3_CONTINUOUS_ARRAY_BOUND');self.assertIsNone(result['nativeReport'])
        self.assertIsNone(data['data']['colliders']);self.assertEqual(len(data['data']['sequences'][0]['frames']),5)
        self.assertEqual(data['omissions'][0]['length'],4097);self.assertTrue(data['nativeFailure'])

    def test_rejected_native_exports_one_pinned_safe_projection_and_keeps_native_failure(self):
        native=self.prepare_partial_report();native['colliders']=[dict(id=1,instanceId=-1,scene='unknown-private-scene',path='/private/account',type='MeshCollider',role='world',trigger=False,min=dict(x=0,y=0,z=0),max=dict(x=1,y=1,z=1))]
        raw=json.dumps(native).encode();(self.copy/probe.RAW_REL).write_bytes(raw)
        with mock.patch.object(probe,'dispatch'),mock.patch.object(probe.source,'verify_source_state'),mock.patch.object(probe,'git',return_value=b''):
            self.assertEqual(probe.finish(),2)
        result=probe.read(probe.REPORT);row=result['nativeRedactedReport']
        self.assertEqual(set(row),{'path','mode','bytes','sha256'});self.assertEqual(row['mode'],'FAILED_REDACTED')
        packed=(probe.EXPORT/row['path']).read_bytes();self.assertEqual(probe.raw_pin(packed),{k:row[k] for k in ('bytes','sha256')})
        data=probe.parse(packed);self.assertTrue(data['nativeFailure']);self.assertFalse(data['semanticsValidated']);self.assertFalse(data['diagnosticComplete'])
        self.assertEqual(data['sourceRaw'],probe.raw_pin(raw));self.assertEqual(len(data['data']['sequences'][0]['frames']),5)
        self.assertEqual(result['status'],'FAILED_REDACTED_DIAGNOSTIC_NOT_GAMEPLAY_ACCEPTANCE')
        self.assertIsNone(result['nativeReport']);self.assertIsNone(result['nativeSummary'])
        self.assertEqual(result['xml']['result'],'Failed');self.assertEqual(result['nativeOutcome'],'failure')
        expected={'report.json',row['path']} | {p['path'] for p in result['sourceSnapshots']} | {result[k]['path'] for k in ('nativeAuthorReport','nativeFocusedReport') if result[k] is not None}
        self.assertEqual({p.relative_to(probe.EXPORT).as_posix() for p in probe.EXPORT.rglob('*') if p.is_file()},expected)
        for p in probe.EXPORT.rglob('*.json'):
            for secret in ('unknown-private-scene','/private/account'):self.assertNotIn(secret,p.read_text())
        self.assertIn('diagnostic_complete=false',(self.root/'output').read_text())
    def test_nonfinite_native_json_gets_failed_safe_projection(self):
        native=self.prepare_partial_report();native['sequences'][0]['frames'][1]['dt']=float('nan')
        raw=json.dumps(native).encode();(self.copy/probe.RAW_REL).write_bytes(raw)
        with mock.patch.object(probe,'dispatch'),mock.patch.object(probe.source,'verify_source_state'),mock.patch.object(probe,'git',return_value=b''):
            self.assertEqual(probe.finish(),2)
        result=probe.read(probe.REPORT);data=probe.read(probe.EXPORT/result['nativeRedactedReport']['path'])
        self.assertEqual(result['nativeReportRejection']['code'],'R3_NATURAL_CONTACT_NONFINITE_JSON')
        self.assertIsNone(data['data']['sequences'][0]['frames'][1]['dt']);self.assertEqual(data['omissionCount'],1)
        self.assertTrue(data['nativeFailure']);self.assertIsNone(result['nativeReport'])

    def test_truncated_native_json_still_exports_bounded_failed_metadata(self):
        self.prepare_partial_report();raw=b'{"sequences":[{"private-key":"private-body",'
        (self.copy/probe.RAW_REL).write_bytes(raw)
        with mock.patch.object(probe,'dispatch'),mock.patch.object(probe.source,'verify_source_state'),mock.patch.object(probe,'git',return_value=b''):
            self.assertEqual(probe.finish(),2)
        result=probe.read(probe.REPORT);data=probe.read(probe.EXPORT/result['nativeRedactedReport']['path'])
        self.assertIsNone(data['data']);self.assertEqual(data['sourceRaw'],probe.raw_pin(raw));self.assertTrue(data['nativeFailure'])
        self.assertEqual(data['omissions'][0]['code'],'R3_CONTINUOUS_REDACTED_JSON_PARSE')
        self.assertEqual(result['xml']['result'],'Failed');self.assertIsNone(result['nativeReport'])
        self.assertNotIn('private-key',json.dumps(data));self.assertNotIn('private-body',json.dumps(data))

    def test_unsafe_partial_is_not_exported_and_rejection_context_is_bounded(self):
        native=self.prepare_partial_report();native['sequences'][0]['frames'][2]['motor']['privateExtra']='/private/account/secret'
        (self.copy/probe.RAW_REL).write_text(json.dumps(native))
        with mock.patch.object(probe,'dispatch'),mock.patch.object(probe.source,'verify_source_state'),mock.patch.object(probe,'git',return_value=b''):
            self.assertEqual(probe.finish(),2)
        result=probe.read(probe.REPORT);reason=result['nativeReportRejection']
        self.assertIsNone(result['nativeReport']);self.assertFalse((probe.EXPORT/'native-r3-continuous-contact.json').exists())
        self.assertEqual(reason['code'],'R3_CONTINUOUS_CLOSED_KEYS_MOTOROBSERVATION')
        self.assertEqual(reason['location'],'$.sequences[0].frames[2].motor.<unknown>');self.assertEqual(len(reason['valueSha256']),64)
        self.assertNotIn('/private/account',probe.REPORT.read_text());self.assertNotIn('privateExtra',probe.REPORT.read_text())

    def test_stage_failure_still_checks_formal_source_without_owner(self):
        with mock.patch.object(probe,'dispatch'),mock.patch.object(probe.source,'verify_source_state'),mock.patch.object(probe,'git',return_value=b''):
            self.assertEqual(probe.finish(),2)
        result=probe.read(probe.REPORT)
        self.assertTrue(result['sourceUnchanged']);self.assertIn('OWNED_COPY_UNAVAILABLE',result['checks'])


class SharedGuardAdmission(unittest.TestCase):
    def test_shared_guard_calls_exact_new_dispatch_before_source_checks(self):
        args=identity_fixture()
        with mock.patch.dict(os.environ,args[0],clear=True),mock.patch.object(probe.source,'read_json',return_value=args[1]),mock.patch.object(probe.source,'identity'),mock.patch.object(probe.source,'verify_source_state'),mock.patch.object(probe,'dispatch') as admission:
            probe.source.guard()
        admission.assert_called_once_with()

    def test_shared_guard_propagates_refused_new_dispatch(self):
        args=identity_fixture()
        with mock.patch.dict(os.environ,args[0],clear=True),mock.patch.object(probe,'dispatch',side_effect=ValueError('refused')),mock.patch.object(probe.source,'verify_source_state') as verify:
            with self.assertRaisesRegex(ValueError,'refused'):probe.source.guard()
        verify.assert_not_called()

    def test_shared_guard_never_routes_arbitrary_branch_to_new_admission(self):
        import journey_rebuild_dispatch
        args=identity_fixture();args[0]['GITHUB_REF']='refs/heads/arbitrary'
        with mock.patch.dict(os.environ,args[0],clear=True),mock.patch.object(journey_rebuild_dispatch,'verify'),mock.patch.object(probe,'dispatch') as admission:
            with self.assertRaisesRegex(ValueError,'Trusted repository/ref required'):probe.source.guard()
        admission.assert_not_called()


if __name__ == '__main__':unittest.main()
