"""Read-only drift diagnostics and real failed-native workflow regressions."""
from contextlib import ExitStack
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import journey_tracer_source_diagnostic as d

SOURCE_ROOT = d.ROOT


def entry(raw): return dict(type='FILE', sha256=d.sha(raw), bytes=len(raw))


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.task=self.root/'tasks/desert-rv';self.project=self.task/'unity'
        self.context=ExitStack();self.context.enter_context(mock.patch.multiple(d,ROOT=self.root,TASK=self.task,PROJECT=self.project,REPORT=self.task/'report.json'))
        self.source=dict(coverageRoots=['tasks/desert-rv/unity','tasks/desert-rv/scripts'])
        for name in ('Assets','Packages','ProjectSettings'):(self.project/name).mkdir(parents=True)
        (self.task/'scripts').mkdir()
        self.env=dict(GITHUB_SHA='a'*40,GITHUB_RUN_ID='9876',GITHUB_RUN_ATTEMPT='1',NATIVE_OUTCOME='failure',GITHUB_OUTPUT=str(self.root/'output'))
        self.expected={}
        self.file('tasks/desert-rv/scripts/fixture.py',b'public host fixture')
    def tearDown(self):self.context.close();self.temp.cleanup()
    def file(self,name,raw=b'public baseline'):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);self.expected[name]=entry(raw);return path
    def baseline(self):
        git=lambda *args:subprocess.check_output(['git',*args],cwd=self.root,stderr=subprocess.DEVNULL)
        git('init');git('config','user.name','Host fixture');git('config','user.email','fixture@example.invalid');git('add','.');git('commit','-m','Immutable baseline')
    def report(self):
        value=d.blank_report(self.env);value.update(baselineAuthenticated=True,baselineSourceStateSha256='b'*64,
            checks={key:dict(status='PASS',errorClass='NONE') for key in d.CHECKS})
        value.update(d.collect_changes(self.source,self.expected));clean=value['complete'] and not value['truncated'] and not any(value['observedChanges'].values())
        value.update(sourceUnchanged=clean,status='SOURCE_UNCHANGED' if clean else 'SOURCE_CHANGED' if any(value['observedChanges'].values()) else 'SOURCE_UNVERIFIED')
        return d.validate_report(value,set(self.expected)|d.expected_directories(self.expected))

    def test_file_delete_replace_link_fifo_and_boundaries_never_follow_secret(self):
        name=d.PREFIX+'Assets/owned.cs';path=self.file(name);budget=lambda:dict(remaining=d.MAX_TOTAL_BYTES,complete=True)
        self.assertEqual(d.observation(path,budget()),self.expected[name])
        path.unlink();self.assertEqual(d.observation(path,budget())['type'],'ABSENT')
        path.mkdir();self.assertEqual(d.observation(path,budget())['type'],'DIRECTORY');path.rmdir()
        outside=self.root/'private';outside.write_text('SECRET_NEVER_PUBLIC');path.symlink_to(outside)
        value=d.observation(path,budget());self.assertEqual(value['type'],'SYMLINK');self.assertNotIn('SECRET_NEVER_PUBLIC',json.dumps(value));path.unlink()
        os.mkfifo(path);self.assertEqual(d.observation(path,budget())['type'],'OTHER');path.unlink()
        path.write_bytes(b'large');limit=dict(remaining=1,complete=True);self.assertEqual(d.observation(path,limit)['type'],'OVER_LIMIT');self.assertFalse(limit['complete'])
        private=self.root/'private-directory';private.mkdir();(private/'SECRET_CHILD').write_bytes(b'SECRET_CONTENT')
        shutil.rmtree(self.project);self.project.symlink_to(private,target_is_directory=True)
        names,complete=d.scan_paths(self.source);self.assertFalse(complete);self.assertFalse(any('SECRET_CHILD' in name for name in names))

    def test_declared_drift_and_fixture_residue_are_distinct_with_unknown_path_redacted(self):
        known=d.PREFIX+'Assets/owned.cs';path=self.file(known);self.baseline();path.write_bytes(b'changed')
        fixture=d.PREFIX+'Assets/JourneyTracerTest_'+'a'*32+'.unity';(self.root/fixture).write_text('fixture leftovers')
        unknown=d.PREFIX+'Assets/SECRET_NEVER_PUBLIC.env';(self.root/unknown).write_text('PASSWORD_NEVER_PUBLIC')
        result=self.report();rows={row['category']:row for row in result['records']}
        self.assertEqual(rows['DECLARED_SOURCE']['path'],known);self.assertEqual(rows['DECLARED_SOURCE']['before'],entry(b'public baseline'));self.assertEqual(rows['DECLARED_SOURCE']['after'],entry(b'changed'))
        self.assertEqual(rows['FIXTURE_RESIDUE']['path'],fixture);self.assertEqual(rows['FIXTURE_RESIDUE']['before']['type'],'ABSENT')
        self.assertIsNone(rows['UNDECLARED']['path']);self.assertEqual(rows['UNDECLARED']['pathSha256'],d.sha(unknown.encode()))
        self.assertNotIn('SECRET_NEVER_PUBLIC',json.dumps(result));self.assertNotIn('PASSWORD_NEVER_PUBLIC',json.dumps(result))
        self.assertEqual(result['observedChanges'],dict(declaredSource=1,fixtureResidue=1,undeclared=1))

    def test_manifest_and_lock_semantics_only_known_packages_and_fixed_values(self):
        names=d.SEMANTIC_PATHS[:2]
        for name in names:self.file(name,(SOURCE_ROOT/name).read_bytes())
        self.baseline()
        for name in names:
            value=json.loads((self.root/name).read_text());key='com.unity.test-framework'
            if name.endswith('packages-lock.json'):
                value['dependencies'][key]['version']='1.6.1';value['dependencies'][key]['url']='https://TOKEN_NEVER_PUBLIC@example.invalid';value['dependencies'][key]['SECRET_FIELD']='PASSWORD_NEVER_PUBLIC'
            else:value['dependencies'][key]='1.6.1'
            value['dependencies']['com.unity.SECRET_PACKAGE']='TOKEN_NEVER_PUBLIC'
            (self.root/name).write_text(json.dumps(value))
        result=self.report();text=json.dumps(result)
        for token in ('TOKEN_NEVER_PUBLIC','PASSWORD_NEVER_PUBLIC','SECRET_FIELD','SECRET_PACKAGE'):self.assertNotIn(token,text)
        for row in result['records']:
            self.assertEqual(row['semantics']['status'],'ALLOWLIST_ONLY')
            self.assertTrue(any(change['after']=='1.6.1' for change in row['semantics']['changes']))
            self.assertEqual(row['before'],self.expected[row['path']])

    def test_nail_material_and_meta_semantics_preserve_hashes_hide_userdata(self):
        for name in (d.MATERIAL,d.MATERIAL+'.meta'):self.file(name,(SOURCE_ROOT/name).read_bytes())
        self.baseline()
        path=self.root/d.MATERIAL;path.write_text(path.read_text().replace('  version: 10','  version: 11').replace('    - _Surface: 0','    - _Surface: 1').replace('  m_Name: JourneyNailTrajectory','  m_Name: TOKEN_NEVER_PUBLIC'))
        meta=self.root/(d.MATERIAL+'.meta');meta.write_text(meta.read_text().replace('userData:', 'userData: PASSWORD_NEVER_PUBLIC').replace('mainObjectFileID: 2100000','mainObjectFileID: 0'))
        result=self.report();text=json.dumps(result)
        self.assertNotIn('TOKEN_NEVER_PUBLIC',text);self.assertNotIn('PASSWORD_NEVER_PUBLIC',text)
        changes={change['field']:change for row in result['records'] for change in row['semantics']['changes']}
        self.assertEqual(changes['AssetVersion.version']['before'],10);self.assertEqual(changes['AssetVersion.version']['after'],11)
        self.assertEqual(changes['Material.m_Floats._Surface']['after'],1)
        self.assertEqual(changes['NativeFormatImporter.mainObjectFileID']['before'],2100000)

    def test_record_and_scan_limits_are_explicit_and_cannot_pass(self):
        known=d.PREFIX+'Assets/owned.cs';self.file(known);self.baseline()
        for i in range(d.MAX_RECORDS+5):(self.project/'Assets'/('unknown'+str(i))).write_bytes(b'x')
        result=self.report();self.assertTrue(result['truncated']);self.assertEqual(len(result['records']),d.MAX_RECORDS);self.assertFalse(result['sourceUnchanged'])
        with mock.patch.object(d,'MAX_ENTRIES',2):
            self.assertFalse(d.collect_changes(self.source,self.expected)['complete'])

    def test_report_closed_keys_counts_categories_and_semantic_fields(self):
        path=self.file(d.MATERIAL,(SOURCE_ROOT/d.MATERIAL).read_bytes());self.baseline();path.write_text(path.read_text().replace('  version: 10','  version: 11'))
        result=self.report();allowed=set(self.expected)|d.expected_directories(self.expected)
        mutants=[]
        for changes in ({'privateLog':'TOKEN'},{'sourceUnchanged':True},{'status':'SOURCE_UNCHANGED'},{'schema':True},{'truncated':True}):mutants.append(dict(result,**changes))
        v=copy.deepcopy(result);v['observedChanges']['declaredSource']=0;mutants.append(v)
        v=copy.deepcopy(result);v['observedChanges']['declaredSource']=2;mutants.append(v)
        v=copy.deepcopy(result);v['observedChanges']=dict(declaredSource=0,fixtureResidue=1,undeclared=0);mutants.append(v)
        v=copy.deepcopy(result);v['records'][0]['path']=d.PREFIX+'Assets/SECRET';v['records'][0]['pathSha256']=d.sha(v['records'][0]['path'].encode());mutants.append(v)
        for field in ('TOKEN_NEVER_PUBLIC','dependencies.com.unity.SECRET.version','Material.m_Name.SECRET'):
            v=copy.deepcopy(result);v['records'][0]['semantics']['changes'][0]['field']=field;mutants.append(v)
        v=copy.deepcopy(result);v['records'][0]['path']=d.PREFIX+'Assets/other.cs';v['records'][0]['pathSha256']=d.sha(v['records'][0]['path'].encode());mutants.append(v)
        for value in mutants:
            with self.subTest(value=value),self.assertRaises(Exception):d.validate_report(value,allowed)
        v=copy.deepcopy(result);v['records'][0]['semantics']['changes'][0]['after']='TOKEN_NEVER_PUBLIC'
        with self.assertRaises(Exception):d.validate_report(v,allowed)

    def test_failed_native_always_collects_and_preserves_original_before_hash(self):
        known=d.PREFIX+'Assets/owned.cs';path=self.file(known);self.baseline();path.write_bytes(b'changed by native')
        baseline=(copy.deepcopy(self.source),copy.deepcopy(self.expected),'b'*64)
        gates={key:dict(status='FAIL',errorClass='ValueError') for key in d.CHECKS}
        with mock.patch.object(d,'pinned_baseline',return_value=baseline),mock.patch.object(d,'check_original_gates',return_value=gates) as check:
            self.assertEqual(d.run(self.env),2);check.assert_called_once()
        result=json.loads(d.REPORT.read_text());self.assertEqual(result['nativeOutcome'],'failure');self.assertEqual(result['records'][0]['before'],entry(b'public baseline'));self.assertEqual(result['records'][0]['after'],entry(b'changed by native'))
        self.assertEqual(path.read_bytes(),b'changed by native');self.assertIn('report_valid=true',Path(self.env['GITHUB_OUTPUT']).read_text());self.assertIn('source_unchanged=false',Path(self.env['GITHUB_OUTPUT']).read_text())

    def test_report_and_symlink_destination_never_overwrite(self):
        self.file(d.PREFIX+'Assets/owned.cs');self.baseline()
        baseline=(copy.deepcopy(self.source),copy.deepcopy(self.expected),'b'*64);gates={key:dict(status='PASS',errorClass='NONE') for key in d.CHECKS}
        with mock.patch.object(d,'pinned_baseline',return_value=baseline),mock.patch.object(d,'check_original_gates',return_value=gates):
            d.REPORT.write_bytes(b'foreign')
            with self.assertRaises(Exception):d.run(self.env)
            self.assertEqual(d.REPORT.read_bytes(),b'foreign');d.REPORT.unlink()
            foreign=self.root/'foreign';foreign.write_bytes(b'protected');d.REPORT.symlink_to(foreign)
            with self.assertRaises(Exception):d.run(self.env)
            self.assertEqual(foreign.read_bytes(),b'protected')


class RealWorkflowFixtureTests(unittest.TestCase):
    def test_actual_failed_native_workflow_step_exports_source_drift_without_rebaselining(self):
        import journey_tracer_dispatch as dispatch
        import verify_evidence as source
        import yaml
        with tempfile.TemporaryDirectory(prefix='tracer-source-flow-') as temp:
            root=Path(temp)
            def run(args,env=None,expected=0):
                result=subprocess.run(args,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode,expected,result.stdout.decode()[-4000:]);return result.stdout.decode().strip()
            run(['git','init']);run(['git','config','user.name','Host fixture']);run(['git','config','user.email','fixture@example.invalid'])
            (root/'host-base').write_text('host fixture');run(['git','add','.']);run(['git','commit','-m','Host fixture parent']);parent=run(['git','rev-parse','HEAD'])
            for name in source.source_inventory():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(SOURCE_ROOT/name,path)
            public='tasks/desert-rv/PUBLIC-EXPORT.json';shutil.copyfile(SOURCE_ROOT/public,root/public)
            helper=root/'tasks/desert-rv/scripts/journey_tracer_dispatch.py';helper.write_text(helper.read_text().replace(dispatch.BASE,parent))
            run(['/usr/bin/python3','tasks/desert-rv/scripts/update_source_state.py'])
            sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
            request=dict(schema=1,requestId=dispatch.REQUEST_ID,baseCommit=parent,sourceStateSha256=sha(root/dispatch.SOURCE),selection=dispatch.SELECTION,selectionSha256=sha(root/dispatch.SELECTION))
            path=root/dispatch.REQUEST;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(request));run(['git','add','.']);run(['git','commit','-m','Host source'])
            head=run(['git','rev-parse','HEAD']);event=root/'event.json';event.write_text(json.dumps(dict(before=parent,after=head,ref=dispatch.REF,created=False,deleted=False,forced=False,repository=dict(full_name=dispatch.REPOSITORY,private=False,fork=False,default_branch='main',owner=dict(login=dispatch.OWNER)),sender=dict(login=dispatch.OWNER),head_commit=dict(id=head))))
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',GITHUB_ACTIONS='true',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',GITHUB_REPOSITORY=dispatch.REPOSITORY,GITHUB_REPOSITORY_VISIBILITY='public',GITHUB_ACTOR=dispatch.OWNER,GITHUB_TRIGGERING_ACTOR=dispatch.OWNER,GITHUB_REF=dispatch.REF,GITHUB_SHA=head,GITHUB_RUN_ID='9876',GITHUB_RUN_ATTEMPT='1',GITHUB_EVENT_NAME='push',GITHUB_WORKFLOW_REF=dispatch.REPOSITORY+'/'+dispatch.WORKFLOW+'@'+dispatch.REF,GITHUB_EVENT_PATH=str(event),GITHUB_OUTPUT=str(root/'output'),NATIVE_OUTCOME='failure')
            run(['/usr/bin/python3','tasks/desert-rv/scripts/verify_evidence.py','guard'],env)
            run(['/usr/bin/python3','tasks/desert-rv/scripts/backup/restore_unity_font.py'],env)
            run(['/usr/bin/python3','tasks/desert-rv/art/journey-preparation/pipeline.py','init','--selection',dispatch.SELECTION,'--sha256',request['selectionSha256']],env)
            workflow=yaml.load((root/dispatch.WORKFLOW).read_text(),Loader=yaml.BaseLoader);steps=workflow['jobs']['prepare']['steps'];step=next(s for s in steps if s.get('id')=='keyboard_source')
            self.assertEqual(step['if'],"always() && steps.keyboard_copy.outputs.copy_created == 'true'")
            stage=next(s for s in steps if s.get('id')=='stage_armored')
            for gate in ("steps.tracer_source.outcome == 'success'","steps.tracer_source.outputs.source_unchanged == 'true'","steps.keyboard_source.outcome == 'success'","steps.keyboard_source.outputs.source_unchanged == 'true'"):
                self.assertIn(gate,stage['if'])
            # A failed native outcome must not suppress a genuinely clean source result.
            run(['bash','-e','-c',step['run']],env);report=root/'tasks/desert-rv/journey-keyboard-look-source-report.json';clean=json.loads(report.read_text());self.assertTrue(clean['sourceUnchanged']);self.assertEqual(clean['nativeOutcome'],'failure');report.unlink()
            # The exact HEAD baseline stays unchanged while native output modifies bytes.
            mat=root/d.MATERIAL;before=mat.read_bytes();mat.write_bytes(before+b'\n# changed by host fixture\n')
            lock=root/d.SEMANTIC_PATHS[1];lock_before=lock.read_bytes();value=json.loads(lock_before);value['dependencies']['com.unity.test-framework']['depth']=7;lock.write_text(json.dumps(value))
            fixture=root/(d.PREFIX+'Assets/JourneyTracerTest_'+'b'*32+'.unity');fixture.write_bytes(b'host scene residue')
            secret=root/(d.PREFIX+'Assets/SECRET_PATH.env');secret.write_bytes(b'PASSWORD_NEVER_PUBLIC')
            run(['bash','-e','-c',step['run']],env,2);failed=json.loads(report.read_text());raw=report.read_text()
            self.assertEqual(failed['status'],'SOURCE_CHANGED');self.assertFalse(failed['sourceUnchanged']);self.assertEqual(failed['nativeOutcome'],'failure');self.assertTrue(failed['baselineAuthenticated'])
            rows={row['path']:row for row in failed['records'] if row['path']}
            self.assertEqual(rows[d.MATERIAL]['before'],entry(before));self.assertEqual(rows[d.MATERIAL]['after'],entry(mat.read_bytes()))
            self.assertEqual(rows[d.SEMANTIC_PATHS[1]]['before'],entry(lock_before));self.assertIn(d.PREFIX+'Assets/JourneyTracerTest_'+'b'*32+'.unity',rows)
            self.assertNotIn('SECRET_PATH',raw);self.assertNotIn('PASSWORD_NEVER_PUBLIC',raw);self.assertLessEqual(len(raw.encode()),d.MAX_REPORT)
            self.assertEqual(sha(root/dispatch.SOURCE),request['sourceStateSha256']);self.assertEqual(mat.read_bytes(),before+b'\n# changed by host fixture\n')
            self.assertIn('report_valid=true',Path(env['GITHUB_OUTPUT']).read_text())
            # The original native/source gate remains failed; diagnostic export is no waiver.
            original=next(s for s in steps if s.get('id')=='keyboard_verify');run(['bash','-e','-c',original['run']],env,2)
            self.assertNotIn('native_verified=true',Path(env['GITHUB_OUTPUT']).read_text())


if __name__=='__main__':unittest.main()
