"""Exact XML and real source/union negatives; host fixtures are not native passes."""
from contextlib import ExitStack
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
import journey_tracer_native as n


def xml_bytes(names=None):
    root=ET.Element('test-run',dict(result='Passed',total='10',passed='10',failed='0',skipped='0',inconclusive='0'))
    for name in names or n.EXPECTED:ET.SubElement(root,'test-case',dict(fullname=name,result='Passed'))
    return ET.tostring(root)


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.xml=self.root/'native.xml';self.xml.write_bytes(xml_bytes())
    def tearDown(self):self.temp.cleanup()

    def test_exact_cases_and_source_declarations_match(self):
        self.assertEqual(n.inspect_xml(self.root),hashlib.sha256(self.xml.read_bytes()).hexdigest())
        source=(n.ROOT/n.TEST_SOURCE).read_text()
        self.assertEqual(source.count('[Test]'),2);self.assertEqual(source.count('[TestCase('),8)
        self.assertEqual(len(n.EXPECTED),10);self.assertEqual(len(set(n.EXPECTED)),10)
        for name in n.EXPECTED:self.assertIn(name[len(n.PREFIX):].split('(')[0],source)

    def test_all_omitted_duplicated_extra_failed_and_root_counts_reject(self):
        cases=list(n.EXPECTED)
        for names in (cases[:-1],cases+[cases[0]],cases[:-1]+[cases[0]],cases[:-1]+['Unrelated.Test']):
            self.xml.write_bytes(xml_bytes(names))
            with self.subTest(names=names),self.assertRaises(ValueError):n.inspect_xml(self.root)
        for key,value in [('result','Failed'),('total','11'),('passed','9'),('failed','1'),('skipped','1'),('inconclusive','1')]:
            root=ET.fromstring(xml_bytes());root.set(key,value);self.xml.write_bytes(ET.tostring(root))
            with self.subTest(key=key),self.assertRaises(ValueError):n.inspect_xml(self.root)
        for value in ('Failed','Skipped','Inconclusive','Unknown'):
            root=ET.fromstring(xml_bytes());root.find('test-case').set('result',value);self.xml.write_bytes(ET.tostring(root))
            with self.subTest(value=value),self.assertRaises(ValueError):n.inspect_xml(self.root)

    def test_multiple_oversized_linked_and_entity_xml_reject(self):
        other=self.root/'other.xml';other.write_bytes(xml_bytes())
        with self.assertRaisesRegex(ValueError,'XML_COUNT'):n.inspect_xml(self.root)
        other.unlink();self.xml.write_bytes(b' '*(1024*1024+1))
        with self.assertRaisesRegex(ValueError,'XML_SIZE'):n.inspect_xml(self.root)
        self.xml.write_bytes(b'<!DOCTYPE test-run [<!ENTITY leak "TOKEN_NEVER_PUBLIC">]>'+xml_bytes())
        with self.assertRaisesRegex(ValueError,'XML_DECLARATION'):n.inspect_xml(self.root)
        self.xml.unlink();target=self.root/'payload';target.write_bytes(xml_bytes());self.xml.symlink_to(target)
        with self.assertRaisesRegex(ValueError,'UNSAFE_INPUT'):n.inspect_xml(self.root)

    def test_failure_report_is_fixed_valid_bounded_nonoverwriting_and_token_safe(self):
        env=dict(GITHUB_SHA='a'*40,GITHUB_RUN_ID='9876',GITHUB_RUN_ATTEMPT='1',NATIVE_OUTCOME='success',GITHUB_OUTPUT=str(self.root/'output'))
        report=self.root/'report.json'
        with mock.patch.object(n,'REPORT',report),mock.patch.object(n,'ARTIFACTS',self.root),mock.patch.object(n,'verify_unchanged',side_effect=ValueError('TOKEN_NEVER_PUBLIC')):
            self.assertEqual(n.run(env),2);value=json.loads(report.read_text());self.assertTrue(n.validate_report(value))
            self.assertNotIn('TOKEN_NEVER_PUBLIC',report.read_text());self.assertLess(report.stat().st_size,4096)
            self.assertNotIn('native_verified',Path(env['GITHUB_OUTPUT']).read_text())
            before=report.read_bytes()
            with self.assertRaisesRegex(ValueError,'REPORT_PATH'):n.run(env)
            self.assertEqual(report.read_bytes(),before)
            report.unlink();report.symlink_to(self.xml)
            with self.assertRaisesRegex(ValueError,'REPORT_PATH'):n.run(env)
            self.assertEqual(self.xml.read_bytes(),xml_bytes())
        for changes in ({'privateLog':'TOKEN_NEVER_PUBLIC'},{'schema':True},{'expectedNativeCases':True},
                        {'nativeCases':10},{'originalSourceUnchanged':True},{'status':'PASS'},{'failurePhase':'TOKEN_NEVER_PUBLIC'},{'errorClass':'TOKEN_NEVER_PUBLIC'}):
            self.assertFalse(n.validate_report(dict(value,**changes)))


class RealInitialSourceTests(unittest.TestCase):
    def test_actual_pipeline_snapshot_rejects_source_import_and_directory_side_effects(self):
        sys.path[:0]=[str(n.TASK/'art/journey-preparation'),str(n.TASK/'scripts/rendered')]
        import pipeline as p
        import prepared_source as ps
        import verify_evidence as source
        with tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
            root=Path(temp);task=root/'tasks/desert-rv';project=task/'unity';private=project/'JourneyEvidence/JourneyPreparation'
            git=lambda *args:subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()
            git('init');git('config','user.name','Local fixture');git('config','user.email','fixture@example.invalid')
            for directory in source.SOURCE_ROOTS:(root/directory).mkdir(parents=True,exist_ok=True)
            for directory in ('Assets','Packages','ProjectSettings'):(project/directory).mkdir(exist_ok=True)
            original=project/'Assets/original.cs';original.write_text('fixture source')
            selection=task/'art/journey-preparation/selection.json';selection.write_text('{}')
            test= root/n.TEST_SOURCE;test.parent.mkdir(parents=True);test.write_bytes((n.ROOT/n.TEST_SOURCE).read_bytes())
            validator=task/'art/import-candidate/strict_output.py';validator.write_text('fixture validator pin')
            export=task/'PUBLIC-EXPORT.json';export.write_text('{}')
            files=[original,selection,test,validator]
            state_path=task/'SOURCE-STATE.json';state_path.write_text(json.dumps(dict(files=[dict(path=str(path.relative_to(root)),sha256=source.sha(path),size=path.stat().st_size) for path in files],restoredFiles=[])))
            git('add','.');git('commit','-m','initial source');head=git('rev-parse','HEAD')
            env=dict(GITHUB_REPOSITORY='yangerstar1/task-workbench',GITHUB_REF='refs/heads/main',GITHUB_ACTOR='yangerstar1',GITHUB_TRIGGERING_ACTOR='yangerstar1',GITHUB_ACTIONS='true',RUNNER_ENVIRONMENT='github-hosted',GITHUB_REPOSITORY_VISIBILITY='public',GITHUB_SHA=head,GITHUB_RUN_ID='9876',GITHUB_RUN_ATTEMPT='1')
            stack.enter_context(mock.patch.dict(os.environ,env,clear=True))
            stack.enter_context(mock.patch.multiple(n,ROOT=root,TASK=task,PROJECT=project,REPORT=task/'report.json',ARTIFACTS=task/'artifacts/tracer'))
            stack.enter_context(mock.patch.multiple(p,REPO=root,ROOT=task,PROJECT=project,PRIVATE=private,PUBLIC=task/'journey-preparation-export'))
            stack.enter_context(mock.patch.multiple(ps,ROOT=root,TASK=task,PROJECT=project))
            stack.enter_context(mock.patch.multiple(source,ROOT=root,TASK=task,PROJECT=project))
            # Only pin generation is substituted to keep this small file fixture focused.
            pins=[dict(path=str(validator.relative_to(root)),sha256=source.sha(validator))]
            stack.enter_context(mock.patch.object(p,'validation_sources',return_value=pins))
            private.mkdir(parents=True)
            current=dict(sourceCommit=head,runId='9876',selection=str(selection.relative_to(root)),selectionSha256=source.sha(selection),protected=p.protected(),completed=[],assetFiles={},validationSourcePins=pins,initialIdentity=source.identity(),initialSourceDirectories={name:sorted(p.directories(project/name)) for name in ('Assets','Packages','ProjectSettings')})
            p.save(current);n.verify_unchanged()
            n.ARTIFACTS.mkdir(parents=True);(n.ARTIFACTS/'native.xml').write_bytes(xml_bytes())
            output=root/'output';env.update(NATIVE_OUTCOME='success',GITHUB_OUTPUT=str(output))
            self.assertEqual(n.run(env),0);self.assertIn('native_verified=true',output.read_text());n.REPORT.unlink()
            # Native import cannot silently rewrite checked-in material/source bytes.
            before=original.read_bytes();original.write_text('changed by import')
            with self.assertRaises(Exception):n.verify_unchanged()
            self.assertEqual(n.run(env),2);failure=json.loads(n.REPORT.read_text());self.assertEqual(failure['status'],'FAIL');self.assertEqual(failure['failurePhase'],'PIPELINE_PROTECTED');self.assertEqual(failure['errorClass'],'StrictError');n.REPORT.unlink();original.write_bytes(before)
            for name,is_dir in [('Assets/leftover-test-scene.unity',False),('Assets/undeclared-empty',True),('Assets/DesertRV/CandidateArtImports',True),('CandidateImportInput',True),('CandidatePackageSnapshot',True),('JourneyEvidence/CandidateArt',True)]:
                path=project/name;path.parent.mkdir(parents=True,exist_ok=True)
                if is_dir:path.mkdir()
                else:path.write_bytes(b'undeclared')
                with self.subTest(path=name),self.assertRaises(Exception):n.verify_unchanged()
                if is_dir:path.rmdir()
                else:path.unlink()
            # The check never removes evidence to manufacture a pass.
            state_before=(private/'state.json').read_bytes();n.verify_unchanged();self.assertEqual((private/'state.json').read_bytes(),state_before)


if __name__=='__main__':unittest.main()
