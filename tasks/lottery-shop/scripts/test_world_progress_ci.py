#!/usr/bin/env python3
"""Source and Python boundary models only. Does not launch Unity or Docker."""
import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import world_progress_ci as world

IDENT = dict(sourceCommit='1'*40, reviewedCandidateCommit='2'*40, runId='12345', runAttempt='1')
KEY = next(iter(world.CASE_SEGMENTS))
SEGMENT = world.CASE_SEGMENTS[KEY][0]
VEC = '(0.0000,0.0000,0.0000)'


def route(segment=SEGMENT, phase='BEGIN', elapsed='0.0000', frames=0):
    return (f'WORLD_ROUTE_V1 segment={segment} phase={phase} elapsed={elapsed} limit=45 frames={frames} stationaryFrames=0'
            f' body={VEC} origin={VEC} destination={VEC} remaining=1.0000 minRemaining=1.0000 lastStep=0.0000'
            f' pathMeters=0.0000 maxFrameWall=0.0000 maxUnscaledDelta=0.0000 command={VEC} camera={VEC} cameraEuler={VEC}'
            ' moveId=-1 lookId=-1 mode=1 focused=True awaitingRelease=False cameraWrite=True')


def ray():
    return ('WORLD_RAY_V2 kind=CHARACTER_CONTROLLER trigger=False ownBody=True environment=False hitDistance=0.2000'
            f' horizontalReach=0.2000 body={VEC} camera={VEC} target={VEC} pixel={VEC} rayOrigin={VEC} rayDirection={VEC}'
            ' foreignHits=2 foreignDistance=0.9000 foreignController=False foreignTarget=True foreignNearestTies=1')


def record(sample=None, key=KEY, sequence=1):
    return dict(schemaVersion=1, scope=world.SCOPE, status='OBSERVATIONS_ONLY_NOT_TEST_PASS', sequence=sequence,
                caseKey=key, utc='2026-10-14T01:20:47.0870200Z', sample=sample or route(), **IDENT)


def encode(rows):
    return b''.join((json.dumps(row,separators=(',',':'))+'\n').encode() for row in rows)


def source_concat(expression, values, vector_expression):
    """Evaluate only the existing source's literal/variable/formatter concatenation.

    This deliberately does not consult either diagnostic regexp or route()/ray().
    It is a narrow source model, not a C# compiler or Unity runtime assertion.
    """
    parts=[];start=0;depth=0;quoted=False;escaped=False
    for i,ch in enumerate(expression):
        if quoted:
            if escaped:escaped=False
            elif ch=='\\':escaped=True
            elif ch=='"':quoted=False
        elif ch=='"':quoted=True
        elif ch=='(':depth+=1
        elif ch==')':depth-=1
        elif ch=='+' and depth==0:
            parts.append(expression[start:i].strip());start=i+1
    parts.append(expression[start:].strip())
    result=[]
    for part in parts:
        if part.startswith('"'):
            result.append(json.loads(part))
        elif part.startswith('WorldNumber(') and part.endswith(')'):
            result.append(format(values[part[len('WorldNumber('):-1]],'.4f'))
        elif part.startswith('WorldVector(') and part.endswith(')'):
            xyz=values[part[len('WorldVector('):-1]]
            result.append(source_concat(vector_expression,dict(zip(('value.x','value.y','value.z'),xyz)),vector_expression))
        else:
            result.append(str(values[part]))
    return ''.join(result)


class WorldProgressTests(unittest.TestCase):
    def check(self, rows):
        return world.decode_records(encode(rows), IDENT)

    def test_partial_route_and_ray_are_diagnostics_never_pass(self):
        rows=[record(),record(ray(),sequence=2)]
        got=self.check(rows)
        self.assertEqual(got['observations'],rows)
        self.assertFalse(got['partialFinalRecordDiscarded'])
        self.assertEqual(got['status'],'OBSERVATIONS_ONLY_NOT_TEST_PASS')
        self.assertNotIn('allExpectedPassed',got)

    def test_each_killed_append_offset_retains_exact_committed_prefix(self):
        first=encode([record()]);second=encode([record(ray(),sequence=2)])
        for offset in range(len(second)):
            got=world.decode_records(first+second[:offset],IDENT)
            self.assertEqual(got['observations'],[record()])
            self.assertEqual(got['partialFinalRecordDiscarded'],offset>0)
        self.assertEqual(len(world.decode_records(first+second,IDENT)['observations']),2)

    def test_valid_json_without_newline_is_not_committed(self):
        got=world.decode_records(encode([record()])+encode([record(ray(),sequence=2)]).rstrip(b'\n'),IDENT)
        self.assertEqual(got['observations'],[record()]);self.assertTrue(got['partialFinalRecordDiscarded'])

    def test_private_and_invalid_utf8_tail_never_exported(self):
        got=world.decode_records(encode([record()])+b'\xff<License>SYNTHETIC_PRIVATE</License>',IDENT)
        self.assertTrue(got['partialFinalRecordDiscarded']);self.assertNotIn('PRIVATE',json.dumps(got))

    def test_complete_corrupt_or_private_row_cannot_be_skipped(self):
        for value in (b'{}\n',b'\xff\n',b'SYNTHETIC_PRIVATE\n',b'\n'):
            with self.subTest(value=value),self.assertRaises(ValueError) as raised:
                world.decode_records(encode([record()])+value,IDENT)
            self.assertNotIn('SYNTHETIC_PRIVATE',str(raised.exception))

    def test_all_identity_fields_must_match(self):
        for key in IDENT:
            row=record();row[key]='9'*40 if 'Commit' in key else '99'
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'WORLD_IDENTITY_REJECTED'):
                self.check([row])

    def test_unknown_top_fields_and_case_rejected(self):
        for key,value in [('message','SYNTHETIC_PRIVATE'),('scope','ALL_PASSED'),('caseKey','f'*64),('schemaVersion',True),('status','PASSED'),('sample',None)]:
            row=record();row[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.check([row])

    def test_duplicate_json_key_rejected(self):
        data=encode([record()]).replace(b'"schemaVersion":1',b'"schemaVersion":1,"schemaVersion":1')
        with self.assertRaises(ValueError):world.decode_records(data,IDENT)

    def test_sequence_must_be_contiguous_actual_int(self):
        for value in [0,2,True,'1']:
            row=record();row['sequence']=value
            with self.subTest(value=value),self.assertRaises(ValueError):self.check([row])

    def test_utc_malformed_non_utc_and_regression_rejected(self):
        for value in ['SYNTHETIC_PRIVATE','2026-99-14T01:00:00Z','2026-10-14T01:00:00+01:00']:
            row=record();row['utc']=value
            with self.subTest(value=value),self.assertRaises(ValueError):self.check([row])
        row=record(ray(),sequence=2);row['utc']='2026-10-13T00:00:00Z'
        with self.assertRaises(ValueError):self.check([record(),row])

    def test_sample_has_no_arbitrary_text_field_or_undefined_number(self):
        for value in [route()+' secret=SYNTHETIC_PRIVATE',route()+'\n',route().replace('phase=BEGIN','phase=PRIVATE'),
                      route().replace('segment='+SEGMENT,'segment=PRIVATE'),route().replace('0.0000','NaN',1),
                      route().replace('0.0000','Infinity',1),route().replace('0.0000','0e9999',1),
                      route().replace('focused=True','focused=1'),ray().replace('kind=CHARACTER_CONTROLLER','kind=PRIVATE')]:
            with self.subTest(value=value),self.assertRaises(ValueError):self.check([record(value)])

    def test_segment_must_belong_to_case(self):
        key=next(k for k in world.CASE_SEGMENTS if k!=KEY)
        with self.assertRaisesRegex(ValueError,'WORLD_SEGMENT_CASE_REJECTED'):self.check([record(key=key)])

    def test_route_order_and_eight_sample_limit(self):
        for phase in ['SAMPLE','REACHED','ABORTED']:
            with self.subTest(phase=phase),self.assertRaises(ValueError):self.check([record(route(phase=phase))])
        with self.assertRaises(ValueError):self.check([record(),record(sequence=2)])
        rows=[record()]+[record(route(phase='SAMPLE',elapsed=f'{i*5}.0000',frames=i),sequence=i+1) for i in range(1,9)]
        rows.append(record(route(phase='ABORTED',elapsed='45.1000',frames=9),sequence=10))
        self.assertEqual(len(self.check(rows)['observations']),10)
        rows[-1]['sample']=route(phase='SAMPLE',elapsed='45.1000',frames=9)
        with self.assertRaises(ValueError):self.check(rows)
        rows=[record(),record(route(phase='REACHED',elapsed='1.0000',frames=1),sequence=2),record(route(phase='SAMPLE',elapsed='2.0000',frames=2),sequence=3)]
        with self.assertRaises(ValueError):self.check(rows)

    def test_route_negative_elapsed_regression_and_stationary_count_rejected(self):
        bads=[route(elapsed='-0.5000'),route().replace('stationaryFrames=0','stationaryFrames=1')]
        for sample in bads:
            with self.subTest(sample=sample),self.assertRaises(ValueError):self.check([record(sample)])
        rows=[record(),record(route(phase='SAMPLE',elapsed='5.0000',frames=10),sequence=2),record(route(phase='SAMPLE',elapsed='4.0000',frames=9),sequence=3)]
        with self.assertRaises(ValueError):self.check(rows)

    def test_ray_per_case_limit_and_obstructed_observations(self):
        rows=[record(ray(),sequence=i) for i in range(1,3)]
        self.assertEqual(len(self.check(rows)['observations']),2)
        rows.append(record(ray(),sequence=3))
        with self.assertRaises(ValueError):self.check(rows)
        nohit=ray().replace('kind=CHARACTER_CONTROLLER','kind=NONE').replace('hitDistance=0.2000','hitDistance=-1.0000')
        self.check([record(nohit)])

    def test_all_ten_routes_maximum_samples_seven_rays_fit_byte_event_limits(self):
        rows=[]
        for key,segments in world.CASE_SEGMENTS.items():
            for segment in segments:
                rows.append(record(route(segment),key,len(rows)+1))
                for i in range(1,9):rows.append(record(route(segment,'SAMPLE',f'{i*5}.0000',i),key,len(rows)+1))
                rows.append(record(route(segment,'REACHED','44.0000',9),key,len(rows)+1))
            for i in range(3 if 'ENTRY_TO_INVENTORY' in segments else 2):rows.append(record(ray(),key,len(rows)+1))
        data=encode(rows)
        self.assertEqual(len(rows),107);self.assertLess(len(data),world.LIMIT)
        self.assertTrue(all(len(line)+1<=world.MAX_RECORD_BYTES for line in data.splitlines()))
        self.assertEqual(len(world.decode_records(data,IDENT)['observations']),107)

    def test_size_count_and_empty_rejected(self):
        for data in [b'',b'x',b'x'*(world.LIMIT+1),b'{}\n'*129,encode([record()]).replace(b'WORLD_ROUTE',b'X'*4096+b'WORLD_ROUTE')]:
            with self.subTest(length=len(data)),self.assertRaises(ValueError):world.decode_records(data,IDENT)

    def test_export_fixed_paths_removes_stale_output_and_accepts_timeout_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/world.visual.TASK/world.SOURCE;source.parent.mkdir(parents=True)
            destination=world.visual.outdir(root)/world.DESTINATION;destination.parent.mkdir(parents=True)
            destination.write_text('STALE')
            with patch.object(world.visual,'identity',return_value=IDENT):
                world.export(root);missing=json.loads(destination.read_text())
                self.assertEqual(missing['status'],'NOT_AVAILABLE');self.assertEqual(missing['observations'],[])
                self.assertTrue(all(missing[k]==v for k,v in IDENT.items()));self.assertNotIn('allExpectedPassed',missing)
                source.write_bytes(encode([record()])+b'PARTIAL_PRIVATE')
                world.export(root);got=json.loads(destination.read_text())
                self.assertTrue(got['partialFinalRecordDiscarded']);self.assertNotIn('PRIVATE',destination.read_text())
                source.write_bytes(encode([record()])+b'PRIVATE\n')
                with self.assertRaises(ValueError):world.export(root)
                self.assertFalse(destination.exists())
                wrong=record();wrong['sourceCommit']='9'*40;source.write_bytes(encode([wrong]))
                with self.assertRaisesRegex(ValueError,'WORLD_IDENTITY_REJECTED'):world.export(root)
                self.assertFalse(destination.exists())
                source.write_bytes(b'')
                with self.assertRaisesRegex(ValueError,'WORLD_RECORD_COUNT_REJECTED'):world.export(root)
                self.assertFalse(destination.exists())

    def test_source_symlinks_and_destination_parent_alias_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/world.visual.TASK/world.SOURCE;source.parent.mkdir(parents=True)
            target=root/'private-data';target.write_bytes(encode([record()]))
            source.symlink_to(target)
            with patch.object(world.visual,'identity',return_value=IDENT):
                with self.assertRaisesRegex(ValueError,'WORLD_SOURCE_REJECTED'):world.export(root)
                source.unlink();source.write_bytes(encode([record()]))
                destination=world.visual.outdir(root)/world.DESTINATION;destination.parent.mkdir(parents=True)
                destination.symlink_to(root/'absent-private-data')
                world.export(root);self.assertFalse(destination.is_symlink());self.assertFalse((root/'absent-private-data').exists())
                destination.unlink();destination.parent.rmdir();destination.parent.symlink_to(root)
                with self.assertRaisesRegex(ValueError,'WORLD_DESTINATION_REJECTED'):world.export(root)

    def test_existing_csharp_formatter_expressions_accept_independent_numeric_fixtures(self):
        root=Path(__file__).resolve().parents[3]
        source=(root/world.visual.TASK/'unity/Assets/G3/Tests/PlayMode/G3WorldInteractionTests.cs').read_text()
        vector=re.search(r'static string WorldVector\(Vector3 value\)=>(.*?);',source).group(1)
        self.assertIn('value.ToString("F4",System.Globalization.CultureInfo.InvariantCulture)',source)
        def expression(method):
            body=source[source.index('        string '+method+'('):]
            return body[body.index('return ')+7:body.index(';',body.index('return '))]
        # Independent numeric fixture, including signs and nonzero fractions. The
        # literal labels, field order, separators and vector formatting come from C#.
        route_values={
            'sample.Segment':SEGMENT,'phase':'BEGIN','Time.realtimeSinceStartup-sample.Started':0.0,
            'sample.Frames':0,'sample.StationaryFrames':0,'body':(1.3125,.0250,1.4065),
            'sample.Origin':(1.3125,.0250,1.4065),'sample.Destination':(-.6500,0,.9000),
            'WorldDistance(body,sample.Destination)':2.0268,'sample.MinRemaining':2.0268,
            'sample.LastStep':0.0,'sample.PathMeters':0.0,'sample.MaxFrameWall':.2345,
            'sample.MaxFrameDelta':.2345,'new Vector3(sample.LastCommand.x,0,sample.LastCommand.y)':(-.75,0,.25),
            'app.SceneCamera.transform.position':(1.3125,1.6050,1.4065),'app.SceneCamera.transform.eulerAngles':(8,270,0),
            'Router.MoveTouchId':-1,'Router.LookTouchId':-1,'(int)Router.Mode':1,'Router.IsFocused':True,
            'Router.AwaitingRelease':False,'P.View.Walk.CameraWriteEnabled':True}
        actual_route=source_concat(expression('WorldWalkDiagnostic'),route_values,vector)
        self.assertIn('body=(1.3125,0.0250,1.4065)',actual_route)
        self.assertIn('command=(-0.7500,0.0000,0.2500)',actual_route)
        self.check([record(actual_route)])
        ray_values={
            'kind':'CHARACTER_CONTROLLER','(hitAny&&hit.collider.isTrigger)':False,
            '(hitAny&&P.View.Walk.OwnsBodyCollider(hit.collider))':True,
            '(hitAny&&hit.collider.transform.IsChildOf(P.View.Environment.transform))':False,
            'hitAny?hit.distance:-1':.0687,'reach':.0723,'body':(1.3125,.0250,1.4065),
            'app.SceneCamera.transform.position':(1.3125,1.6050,1.4065),'target':(2.345,.75,2.02),
            'new Vector3(pixel.x,pixel.y,0)':(319.9999,180,0),'ray.origin':(1.3265,1.5934,1.4148),
            'ray.direction':(.7004,-.5799,.4161),'foreign.Length':3,
            'foreign.Length>0?selected.distance:-1':1.4732,'(foreign.Length>0&&selected.collider is CharacterController)':False,
            '(foreign.Length>0&&selected.collider.GetComponentInParent<G3WorldTarget>()!=null)':True,
            '(foreign.Length>0?foreign.Count(x=>x.distance==selected.distance):0)':1}
        actual_ray=source_concat(expression('WorldRayDiagnostic'),ray_values,vector)
        self.assertIn('pixel=(319.9999,180.0000,0.0000)',actual_ray)
        self.assertIn('rayDirection=(0.7004,-0.5799,0.4161)',actual_ray)
        self.check([record(actual_route),record(actual_ray,sequence=2)])

    def test_source_grammar_case_keys_and_explicit_world_gate(self):
        root=Path(__file__).resolve().parents[3]
        text=(root/world.visual.TASK/'unity/Assets/G3/Tests/PlayMode/G3WorldProgress.cs').read_text()
        for key,expected in [('RoutePattern',world.ROUTE_PATTERN),('RayPattern',world.RAY_PATTERN)]:
            self.assertEqual(re.search('const string '+key+'=@"([^"]+)";',text).group(1),expected)
        names=re.findall(r'name=="([^"]+)"',text)
        self.assertEqual({hashlib.sha256(name.encode()).hexdigest() for name in names},set(world.CASE_SEGMENTS))
        allowed=world.visual.regression_case_keys(root);self.assertTrue(set(world.CASE_SEGMENTS)<=allowed);self.assertEqual(len(allowed),37)
        for value in ['MaximumBytes=262144, MaximumRecords=128, MaximumRecordBytes=4096','Arg("-g3RegressionShard")=="world"',
                      'Arg("-g3RegressionProgress")=="1"','Arg("-assemblyNames")==Assemblies','Arg("-testPlatform")=="playmode"',
                      'FileMode.CreateNew:FileMode.Append','stream.Flush(true)','writeFailed=true',world.SOURCE]:self.assertIn(value,text)
        for forbidden in ['.Message','.StackTrace','.Output','GetEnvironmentVariable','File.WriteAllText','File.ReadAllText','Debug.LogError']:
            self.assertNotIn(forbidden,text)

    def test_source_keeps_all_three_tests_budgets_movement_and_output(self):
        root=Path(__file__).resolve().parents[3]
        text=(root/world.visual.TASK/'unity/Assets/G3/Tests/PlayMode/G3WorldInteractionTests.cs').read_text()
        self.assertEqual(text.count('[UnityTest,Timeout(180000)]'),3)
        self.assertEqual(text.count('WriteWorldDiagnostic(WorldWalkDiagnostic('),3)
        self.assertIn('G3WorldProgress.Record(sample);TestContext.Out.WriteLine(sample)',text)
        self.assertIn('if(!(elapsed<45))Assert.That(elapsed,Is.LessThan(45)',text)
        self.assertIn('WorldRayDiagnostic(target,pixel);WriteWorldDiagnostic(diagnostic);Assert.That(physical,Is.Not.Null',text)
        self.assertIn('BindPresentationTarget(640,360)',text)
        for forbidden in ['renderFrameInterval','SceneCamera.enabled','Time.timeScale','ReadPixels','EncodeToPNG']:
            self.assertNotIn(forbidden,text)


if __name__=='__main__':unittest.main(verbosity=2)
