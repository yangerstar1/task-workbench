"""Offline boundary fixtures: no Docker, Unity, download, or Actions mutation."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile
import journey_interaction_reachability as probe


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
            root=Path(d);copy_path=root/'journey-interaction-project';copy_path.mkdir()
            keep=copy_path/'keep';keep.write_text('untouched')
            with mock.patch.multiple(probe,TASK=root,COPY=copy_path,OWNER=root/'absent',PROJECT=root/'unity'):
                with self.assertRaises(Exception): probe.cleanup()
            self.assertEqual(keep.read_text(),'untouched')




import journey_interaction_report as v

class ReportValidationTests(unittest.TestCase):
    def setUp(self):
        self.rows=[dict(path=f'Assets/Fixture/{i:04}.asset',sha256='a'*64,bytes=1,kind='asset',packageName='',packageVersion='') for i in range(772)]
        self.rows += [dict(path=f'Packages/com.unity.render-pipelines.universal/Fixture/{i:04}.shader',sha256='a'*64,bytes=1,kind='package',packageName='com.unity.render-pipelines.universal',packageVersion='17.3.0') for i in range(24)]
        self.input={'dependencies':self.rows}; self.sha='b'*64
        self.report=dict(schemaVersion=2,status='incomplete',unityVersion='6000.3.19f1',**v.SCOPES,
            sourceUnchanged=False,copiesDeleted=False,setupRestored=False,sourceFiles=[],samples=[],cleanupErrors=[],
            dependencyCheck=dict(status='verified-native-closure',inputPath=v.INPUT_PATH,inputSha256=self.sha,snapshotError='',snapshotFailureCode='',snapshotFailurePath='',
                expectedCount=796,actualCount=796,passed=True,actualDependencies=copy.deepcopy(self.rows),mismatches=[]))
    def check(self): return v.verify_native_report(self.report,self.input,self.sha)
    def test_matching_closure_is_not_completed_gameplay(self):
        out=self.check(); self.assertTrue(out['nativeClosureMatched']); self.assertFalse(out['diagnosticComplete']); self.assertFalse(out['gameplayAccepted'])
    def test_exact_missing_path_is_preserved(self):
        c=self.report['dependencyCheck']; old=c['actualDependencies'].pop(); c.update(status='dependency-mismatch',passed=False,actualCount=795)
        c['mismatches']=[dict(path=old['path'],issue='missing',expectedPresent=True,actualPresent=False,expected=old,actual=None)]
        self.assertEqual(self.check()['dependencyMismatchCount'],1)
        out=v.public_report(self.report,self.input,self.sha)
        self.assertEqual(out['dependencyCheck']['mismatches'][0]['expected']['sha256'],'a'*64)
    def test_changed_package_hash_must_be_reported(self):
        c=self.report['dependencyCheck']; c['actualDependencies'][-1]['sha256']='c'*64
        c.update(status='dependency-mismatch',passed=False)
        with self.assertRaises(ValueError): self.check()
        c['mismatches']=[dict(path=self.rows[-1]['path'],issue='changed',expectedPresent=True,actualPresent=True,expected=self.rows[-1],actual=c['actualDependencies'][-1])]
        self.assertEqual(self.check()['dependencyMismatchCount'],1)
    def test_package_version_drift_rejected(self):
        self.report['dependencyCheck']['actualDependencies'][-1]['packageVersion']='0.0.0'
        with self.assertRaises(ValueError): self.check()
    def test_unknown_keys_fail_closed(self):
        self.report['privateExtra']='do not export'
        with self.assertRaises(ValueError): self.check()
    def test_public_errors_contain_only_digests(self):
        c=self.report['dependencyCheck']; c.update(passed=False,status='dependency-verification-failed',snapshotError='private /home/secret/private-source.cs')
        self.report['status']='dependency-verification-failed'; self.report['cleanupErrors']=['private /home/secret/cleanup.log']
        public=v.public_report(self.report,self.input,self.sha)
        self.assertNotIn('/home/secret',json.dumps(public)); self.assertTrue(public['dependencyCheck']['snapshotErrorDigest']['present'])
    def test_known_missing_snapshot_path_survives_without_raw_exception(self):
        c=self.report['dependencyCheck']; path=self.rows[0]['path']
        c.update(passed=False,status='dependency-verification-failed',snapshotFailureCode='MISSING_DEPENDENCY_BYTES_OR_META',snapshotFailurePath=path,snapshotError='InvalidOperationException: Missing dependency bytes/meta: '+path)
        self.report['status']='dependency-verification-failed'
        out=v.public_report(self.report,self.input,self.sha)
        self.assertEqual(out['dependencyCheck']['snapshotFailure']['path'],path)
        self.assertEqual(out['dependencyCheck']['snapshotFailure']['expected']['sha256'],'a'*64)
        self.assertNotIn('InvalidOperationException',json.dumps(out))
        for unsafe in ('/home/private/x','Assets/../private','Other/private','Assets/private\nlog'):
            c['snapshotFailurePath']=unsafe
            with self.assertRaises(ValueError): self.check()
    def test_forged_completion_without_observations_rejected(self):
        self.report.update(status='observations-complete-not-gameplay-acceptance',sourceUnchanged=True,copiesDeleted=True,setupRestored=True)
        with self.assertRaises(ValueError): self.check()
    def test_unknown_relative_dependency_can_be_preserved(self):
        c=self.report['dependencyCheck']; extra=dict(self.rows[0],path='Assets/Unexpected.asset'); c['actualDependencies'].append(extra)
        c.update(status='dependency-mismatch',passed=False,actualCount=797)
        c['mismatches']=[dict(path=extra['path'],issue='unexpected',expectedPresent=False,actualPresent=True,expected=None,actual=extra)]
        self.assertEqual(v.public_report(self.report,self.input,self.sha)['dependencyCheck']['mismatches'][0]['path'],'Assets/Unexpected.asset')
    def test_duplicate_json_and_nonfinite_values_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'synthetic.json'
            for text in ('{"x":1,"x":2}','{"x":NaN}'):
                path.write_text(text)
                with self.assertRaises(ValueError): v.load_bounded(path)
    def test_hierarchy_slashes_and_global_id_are_safe(self):
        surface=dict(hierarchy='Root[0]/Cache - region-2/optional/example[1]',type='BoxCollider',objectId='GlobalObjectId_V1-2-'+'a'*32+'-123-0',mesh='',meshSha256='',enabled=True,active=True,trigger=False,min=dict(x=0,y=0,z=0),max=dict(x=1,y=1,z=1))
        v.surface(surface)
        surface['objectId']='/private/invalid';
        with self.assertRaises(ValueError): v.surface(surface)


if __name__ == '__main__':
    unittest.main()
