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
        self.input={'dependencies':self.rows,'consumerCommit':'c'*40}; self.sha='b'*64
        self.report=dict(schemaVersion=3,status='incomplete',unityVersion='6000.3.19f1',**v.SCOPES,
            sourceUnchanged=False,copiesDeleted=False,setupRestored=False,sourceFiles=[],samples=[],cleanupErrors=[],
            powerAnchorRegression=dict(scope=v.POWER_SCOPE,helper=v.POWER_HELPER,authoringSource=None,endpointConsumerCommit=None,passed=False,endpoints=[],samples=[]),
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


class PowerEndpointValidationTests(unittest.TestCase):
    def check(self): return v.verify_native_report(self.report,self.input,self.sha)
    def setUp(self):
        ReportValidationTests.setUp(self)
        pin=dict(path=v.AUTHORING_SOURCE,sha256='d'*64)
        self.report['sourceFiles']=[pin]
        regression=self.report['powerAnchorRegression']
        regression.update(authoringSource=pin,endpointConsumerCommit=self.input['consumerCommit'],passed=True)
        vec=lambda x=0,y=0,z=0:dict(x=x,y=y,z=z)
        def collider(name,identity):
            return dict(hierarchy='Root[0]/'+name+'['+str(identity)+']',type='BoxCollider',
                objectId='GlobalObjectId_V1-2-'+'a'*32+'-'+str(identity)+'-0',mesh='',meshSha256='',
                enabled=True,active=True,trigger=False,min=vec(),max=vec(1,1,1))
        vectors={'foot','eye','target','hitPoint','hitNormal','driverLinecastPoint','driverLinecastNormal'}
        numbers={'distance','limit','hitDistance','endpointDistance','savedVehicleDistance','driverEntryDistance','driverLinecastDistance','driverLinecastEndpointDistance'}
        bools={'withinRange','productionCanReachPoint','hasFirstHit','acceptedSurfaceIsFirstHit','supported','standingCapsuleClear','driverDistancePromptPredicate','driverDistanceEnterPredicate','driverLinecastHasHit','driverLinecastAllowsGeometry'}
        for region in (2,3):
            saved=vec(0,1,region);endpoint=vec(0,1,region-.05)
            regression['endpoints'].append(dict(region=region,savedPoint=saved,authoringHelperPoint=endpoint))
            for offset,label in ((-.45,'-0.45'),(0,'0'),(.45,'0.45')):
                row={**{k:vec() for k in vectors},**{k:0 for k in numbers},**{k:False for k in bools},
                    'region':region,'purpose':'power-connect-and-disconnect','approach':'cabinet-front-lateral-'+label,
                    'predicate':'JourneyRaycast.CanReachPoint','acceptedSurface':collider('Power cabinet',1),
                    'firstHit':collider('Power cabinet face',2),'support':collider('Road surface',3),'driverLinecastHit':None,'standingBlockers':[]}
                row.update(foot=vec(offset,.025,region-1.15),eye=vec(offset,1.545,region-1.15),target=saved,
                    limit=2.5,distance=1,withinRange=True,hasFirstHit=True,supported=True,standingCapsuleClear=True)
                self.report['samples'].append(row)
                revised=copy.deepcopy(row);revised.update(target=endpoint,productionCanReachPoint=True,hasFirstHit=False,firstHit=None)
                regression['samples'].append(revised)

    def test_six_synthetic_pairs_are_separate_from_original_observations(self):
        public=v.public_report(self.report,self.input,self.sha)
        self.assertEqual(len(public['samples']),6)
        self.assertEqual(len(public['powerAnchorRegression']['samples']),6)
        self.assertTrue(public['summary']['powerAnchorRegressionPassed'])
        self.assertFalse(public['summary']['diagnosticComplete'])
        self.assertFalse(public['summary']['gameplayAccepted'])
        self.assertIn('historical-prepared-geometry',public['powerAnchorRegression']['scope'])

    def test_same_feet_surface_range_and_targets_are_required(self):
        for field,value in (('foot',dict(x=7,y=1,z=1)),('eye',dict(x=7,y=1,z=1)),('limit',3),('target',dict(x=7,y=1,z=1))):
            original=copy.deepcopy(self.report)
            self.report['powerAnchorRegression']['samples'][0][field]=value
            with self.assertRaises(ValueError):self.check()
            self.report=original
        self.report['powerAnchorRegression']['samples'][0]['acceptedSurface']['objectId']='GlobalObjectId_V1-2-'+'b'*32+'-1-0'
        with self.assertRaises(ValueError):self.check()

    def test_unreachable_new_endpoint_cannot_claim_pass(self):
        self.report['powerAnchorRegression']['samples'][0]['productionCanReachPoint']=False
        with self.assertRaises(ValueError):self.check()
        self.report['powerAnchorRegression']['passed']=False
        public=v.public_report(self.report,self.input,self.sha)
        self.assertFalse(public['powerAnchorRegression']['passed'])
        self.assertEqual(len(public['powerAnchorRegression']['samples']),6)

    def test_wrong_helper_identity_and_missing_historical_block_fail(self):
        for key,value in (('endpointConsumerCommit','f'*40),('helper','Other.Helper'),('scope','fresh scene approval')):
            original=copy.deepcopy(self.report);self.report['powerAnchorRegression'][key]=value
            with self.assertRaises(ValueError):self.check()
            self.report=original
        self.report['samples'][0]['productionCanReachPoint']=True
        with self.assertRaises(ValueError):self.check()

    def test_unknown_regression_fields_and_incomplete_pass_rejected(self):
        self.report['powerAnchorRegression']['privateExtra']='untrusted'
        with self.assertRaises(ValueError):self.check()
        del self.report['powerAnchorRegression']['privateExtra']
        self.report['powerAnchorRegression']['samples'].pop()
        with self.assertRaises(ValueError):self.check()


    def test_partial_endpoint_failure_preserves_available_rows(self):
        value=self.report['powerAnchorRegression']
        value.update(passed=False,endpoints=value['endpoints'][:1],samples=value['samples'][:2])
        public=v.public_report(self.report,self.input,self.sha)
        self.assertEqual(len(public['powerAnchorRegression']['samples']),2)
        self.assertFalse(public['summary']['diagnosticComplete'])
        probe.validate_native_outcome(public,'failure',{'result':'Failed'})
        probe.validate_native_outcome(public,'failure',None)
        for outcome,xml in (('success',{'result':'Passed'}),('success',{'result':'Failed'}),('failure',{'result':'Passed'}),('skipped',None)):
            with self.assertRaises(ValueError):probe.validate_native_outcome(public,outcome,xml)


if __name__ == '__main__':
    unittest.main()
