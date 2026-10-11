"""Host-only validator boundary fixtures. These are not Unity observations."""
import copy
import unittest
from journey_r3_continuous_contact_report import *


def vec(x=0,y=0,z=0): return dict(x=x,y=y,z=z)


def complete(value, kind, field=''):
    if value is None: return None
    if kind.endswith('[]'): return [complete(v,kind[:-2],field) for v in value]
    if kind in SCHEMA:
        for key, sub in SCHEMA[kind].items():
            target=kind+'.'+key
            if key not in value:
                value[key]=[] if sub.endswith('[]') else None if sub in SCHEMA else vec() if sub=='v' else False if sub=='b' else 0 if sub in {'i','n'} else EXACT_TEXT.get(key,{'sourceQuery':'clear','sourceSquareDistanceRaw':'Infinity'}.get(key,''))
            value[key]=complete(value[key],sub,target)
    return value


def fixture():
    digest='a'*64; consumer='b'*40
    expectation=dict(producerCommit=PRODUCER,consumerCommit=consumer,producerRunId='38070456519',dependencies=[{} for _ in range(796)],dependencyChanges=[])
    paths={INPUT,INPUT.replace('.json','.sha256')} | {p for base in SOURCE_PATHS for p in (base,base+'.meta')}
    pins={p:digest for p in paths}
    native=dict(schemaVersion=1,status='completed',failureCode='',producerCommit=PRODUCER,consumerCommit=consumer,producerRunId='38070456519',unityVersion='6000.3.19f1',frameBound=2000,
                physicsAutoSyncTransforms=False,replayDetached=True,sceneUnloaded=True,sourceFilesUnchanged=True,timeRestored=True,originalFixedDelta=.02,
                dependencyCheck=dict(passed=True,expectedCount=796,actualCount=796,inputSha256=digest,mismatches=[]),sourceFiles=[dict(path=p,sha256=digest) for p in sorted(paths)],colliders=[],sequences=[])
    tick=100;time=0
    for name,live,yaw,dt,plan in PLANS:
        beasts=[dict(id=i,health=65,phase='Idle',active=live,enabled=True,dead=False,position=vec(x,0,z),bottom=vec(x,.36,z),top=vec(x,.91,z),physicsMin=vec(),physicsMax=vec(),radius=.36,
                     axisDistance=1,axisInside=False,proxyOverlap=False,penetration=False,penetrationDepth=0,actualAIHitBufferColliderIds=[0]*16,aiQuery=None) for i,(x,z) in enumerate(((-7,33),(7,39)),10)]
        seq=dict(name=name,completed=True,liveEnemies=live,yawOffset=yaw,requestedCaptureDelta=dt,initialVehicleHealth=300,initialPlayerHealth=100,upgrades='Ram, Arc',sourceSpawn=vec(),initialVehicle=vec(1.7,0,24),
                 plan=[dict(name=n,frames=f,throttle=t,steering=s) for n,f,t,s in plan],authoredEnemies=copy.deepcopy(beasts),frames=[])
        for step,count,throttle,steering in plan:
            for _ in range(count):
                tick+=1;time+=dt
                seq['frames'].append(dict(frame=tick,sequenceFrame=len(seq['frames']),step=step,gameTime=time,realTime=time*2,dt=dt,captureDelta=dt,aiDelta=min(dt,.1),timeScale=1,fixedDelta=.02,unscaledDelta=dt,
                    vehicleHealthBeforeAI=300,vehicleHealthBeforeMotor=300,vehicleHealthAfter=300,beforeAI=vec(),after=vec(),status='Playing',control='Driving',
                    motor=dict(translation=None,rotationRawIds=[],rotationFullIds=[],rotationRawCount=0,rotationFullCount=0,rotationNearest=0,throttle=throttle,steering=steering,powerConnected=False),
                    actualMotor32BufferColliderIds=[0]*32,actualRotation32BufferColliderIds=[0]*32,beastsBeforeAI=copy.deepcopy(beasts),beastsBeforeMotor=copy.deepcopy(beasts),beastsAfter=copy.deepcopy(beasts),
                    arcBeforeDirector=dict(sourceBlocker=0,targets=[dict(beast=i,inRange=False,clearLine=True,firstLOSBlocker=None) for i in (10,11)]),arcAfterDirector=dict(sourceBlocker=0,targets=[dict(beast=i,inRange=False,clearLine=True,firstLOSBlocker=None) for i in (10,11)]),motorObstacleContact=[],arcPresented=[]))
        native['sequences'].append(seq);tick+=2;time+=dt*2
    return complete(native,"Report"),expectation,digest,pins


class Boundaries(unittest.TestCase):
    def setUp(self): self.value,self.expected,self.digest,self.pins=fixture()
    def verify(self): return verify_native_report(self.value,self.expected,self.digest,self.pins)
    def reject(self):
        with self.assertRaises((ValueError,KeyError)): self.verify()
    def test_complete_is_observation_not_acceptance(self):
        result=self.verify();self.assertTrue(result['diagnosticComplete']);self.assertFalse(result['gameplayAccepted']);self.assertEqual(sum(x['frames'] for x in result['sequences']),1212)
    def test_wrong_producer(self): self.value['producerCommit']='c'*40;self.reject()
    def test_wrong_consumer(self): self.value['consumerCommit']='c'*40;self.reject()
    def test_stale_dependency(self): self.value['dependencyCheck']['inputSha256']='c'*64;self.reject()
    def test_closure_change(self): self.expected['dependencyChanges']=[{}];self.reject()
    def test_source_replacement(self): self.value['sourceFiles'][0]['sha256']='c'*64;self.reject()
    def test_missing_cleanup(self): self.value['timeRestored']=False;self.reject()
    def test_missing_sequence(self): self.value['sequences'].pop();self.reject()
    def test_missing_frame(self): self.value['sequences'][1]['frames'].pop();self.reject()
    def test_manual_same_frame_loop(self): self.value['sequences'][1]['frames'][1]['frame']=self.value['sequences'][1]['frames'][0]['frame'];self.reject()
    def test_wrong_slow_ai_delta(self): self.value['sequences'][2]['frames'][0]['aiDelta']=.2;self.reject()
    def test_input_not_applied(self): self.value['sequences'][1]['frames'][250]['motor']['throttle']=0;self.reject()
    def test_nonnative_nan(self): self.value['sequences'][0]['frames'][0]['dt']=float('nan');self.reject()
    def test_forced_spawn(self): self.value['sequences'][1]['authoredEnemies'][0]['position']['x']=1;self.reject()
    def test_full_query_reference_escape(self): self.value['sequences'][0]['frames'][0]['motor']['rotationFullIds']=[999];self.reject()
    def test_native_inline_absent_objects(self):
        for f in self.value['sequences'][0]['frames']:
            f['motor']['translation']=complete(dict(performed=False),'Query')
            for b in f['beastsBeforeAI']: b['aiQuery']=complete(dict(recorded=False),'AIQuery')
            for t in f['arcBeforeDirector']['targets']: t['firstLOSBlocker']=complete(dict(present=False),'Hit')
        self.assertTrue(self.verify()['diagnosticComplete'])
    def test_actual_events_are_summarized(self):
        self.value['colliders']=[complete(dict(id=1,instanceId=100,path='JourneyBootstrap/GEO-coach_body_shell',type='MeshCollider',role='retained-rv',min=vec(),max=vec()),'ColliderIdentity')]
        f=self.value['sequences'][1]['frames'][300]
        h=dict(present=True,collider=1,distance=0,point=vec(),normal=vec(0,0,-1))
        f['motorObstacleContact']=[complete(dict(frame=f['frame'],speed=.15,hit=h),'Contact')]
        f['arcPresented']=[complete(dict(frame=f['frame'],target=10,sequence=1,pulse=1),'ArcEvent')]
        result=self.verify()['sequences'][1]
        self.assertEqual(result['obstacleContacts'],1);self.assertEqual(result['arcPresented'],1)
    def test_event_different_frame_rejected(self):
        f=self.value['sequences'][1]['frames'][300]
        f['arcPresented']=[complete(dict(frame=f['frame']-1,target=10,sequence=1,pulse=1),'ArcEvent')]
        self.reject()
    def test_unknown_top_level_cannot_export(self): self.value['privateExtra']='/home/runner/secret';self.reject()
    def test_unknown_nested_cannot_export(self): self.value['sequences'][1]['frames'][0]['motor']['privateExtra']='secret';self.reject()
    def test_private_path_cannot_export(self):
        self.value['colliders']=[complete(dict(id=1,instanceId=100,path='/home/runner/secret',type='MeshCollider',role='world',scene=''),'ColliderIdentity')];self.reject()
    def test_private_scene_cannot_export(self):
        self.value['colliders']=[complete(dict(id=1,instanceId=100,path='JourneyBootstrap',type='MeshCollider',role='world',scene='/home/runner/secret'),'ColliderIdentity')];self.reject()
    def test_free_text_cannot_export(self): self.value['sequences'][1]['fixture']='private account contents';self.reject()
    def test_required_field_missing(self): self.value['sequences'][1]['frames'][0]['motor'].pop('translation');self.reject()
    def test_authored_name_overrides_and_persistent_scene(self):
        self.value['colliders']=[complete(dict(id=1,instanceId=-100,path='Region 3 environment/region-3/wave-1-pouncer-1',type='CapsuleCollider',role='beast',scene='Assets/DesertRV/Scenes/Journey/NightBeacon.unity'),'ColliderIdentity'), complete(dict(id=2,instanceId=-101,path='JourneyBootstrap/Cabin fitted details',type='MeshCollider',role='retained-rv',scene=''),'ColliderIdentity')]
        self.assertTrue(self.verify()['diagnosticComplete'])
    def test_terminal_state_keeps_observations(self):
        f=self.value['sequences'][2]['frames'][-1];f['status']='Failed';f['vehicleHealthAfter']=0;f['motor']['throttle']=0
        self.assertTrue(self.verify()['diagnosticComplete'])

class PartialBoundaries(unittest.TestCase):
    def setUp(self):
        self.value,self.expected,self.digest,self.pins=fixture()
        self.value['status']='fixture-incomplete'
        self.value['sequences']=self.value['sequences'][:2]
        self.value['sequences'][-1]['completed']=False
        self.value['sequences'][-1]['frames']=self.value['sequences'][-1]['frames'][:251]
    def verify(self): return verify_native_report(self.value,self.expected,self.digest,self.pins)
    def test_exact_partial_prefix_preserves_observation_without_full_case_pass(self):
        result=self.verify()
        self.assertFalse(result['diagnosticComplete']);self.assertFalse(result['gameplayAccepted'])
        self.assertEqual(result['status'],'FAILED_PARTIAL_OBSERVATION_NOT_ACCEPTANCE')
        self.assertEqual(result['observedFrames'],491);self.assertEqual(result['expectedFrames'],1212)
        self.assertEqual([s['completed'] for s in result['sequences']],[True,False])
    def test_actual_persistent_scene_rejection_hash_now_accepts_safe_partial(self):
        # Observed value hash from native run 38097078202; remaining DTO is synthetic.
        scene='DontDestroyOnLoad'
        self.assertEqual(hashlib.sha256(json.dumps(scene,separators=(',',':')).encode()).hexdigest(),
                         '6454b79f26bc846f408ac63de1cb0ecfe9a18e0f5a316c7b074d3afd80e7a307')
        self.value['colliders']=[complete(dict(id=1,instanceId=-100,path='JourneyBootstrap',
            type='MeshCollider',role='retained-rv',scene=scene),'ColliderIdentity')]
        result=self.verify()
        self.assertEqual(result['status'],'FAILED_PARTIAL_OBSERVATION_NOT_ACCEPTANCE')
        self.assertFalse(result['diagnosticComplete']);self.assertFalse(result['gameplayAccepted'])
        self.assertEqual(result['observedFrames'],491)
    def test_unknown_runtime_scene_still_rejected_with_precise_location(self):
        for scene in ('DontDestroyOnLoad/private','DontDestroyOnLoad(Clone)','/home/runner/secret','OtherRuntimeScene'):
            with self.subTest(scene=scene):
                self.value['colliders']=[complete(dict(id=1,instanceId=-100,path='JourneyBootstrap',
                    type='MeshCollider',role='retained-rv',scene=scene),'ColliderIdentity')]
                with self.assertRaises(ValueError) as caught:self.verify()
                self.assertEqual(str(caught.exception),'R3_CONTINUOUS_SCENE_TEXT')
                self.assertEqual(caught.exception.report_location,'$.colliders[0].scene')
                self.assertEqual(caught.exception.value_sha256,
                    hashlib.sha256(json.dumps(scene,separators=(',',':')).encode()).hexdigest())
    def test_empty_recorded_prefix_is_explicitly_partial(self):
        self.value['sequences']=[]
        result=self.verify();self.assertEqual(result['observedFrames'],0);self.assertFalse(result['diagnosticComplete'])
    def test_partial_cleanup_failure_stays_false_and_visible(self):
        self.value['timeRestored']=False;self.value['sourceFilesUnchanged']=False
        result=self.verify();self.assertFalse(result['cleanup']['timeRestored']);self.assertFalse(result['diagnosticComplete'])
    def test_recorded_observer_exception_remains_partial_failure(self):
        self.value['failureCode']='OBSERVER_NullReferenceException'
        result=self.verify();self.assertEqual(result['failureCode'],'OBSERVER_NullReferenceException');self.assertFalse(result['diagnosticComplete'])
    def test_partial_does_not_allow_extra_sequence_or_nonprefix_frames(self):
        self.value['sequences'][0]['completed']=False
        with self.assertRaisesRegex(ValueError,'PARTIAL_SEQUENCE_ORDER'):self.verify()
        self.value['sequences'][0]['completed']=True
        self.value['sequences'][-1]['frames'].pop(5)
        with self.assertRaises(ValueError):self.verify()
    def test_partial_completed_sequence_cannot_hide_missing_frames(self):
        self.value['sequences'][-1]['completed']=True
        with self.assertRaisesRegex(ValueError,'FRAME_COUNT'):self.verify()
    def test_partial_unknown_nested_field_has_safe_location_and_value_hash(self):
        self.value['sequences'][1]['frames'][3]['motor']['privateAccountName']='private account body'
        with self.assertRaises(ValueError) as caught:self.verify()
        error=caught.exception
        self.assertEqual(str(error),'R3_CONTINUOUS_CLOSED_KEYS_MOTOROBSERVATION')
        self.assertEqual(error.report_location,'$.sequences[1].frames[3].motor.<unknown>')
        self.assertEqual(len(error.value_sha256),64)
        self.assertNotIn('private',error.report_location)
    def test_partial_private_path_has_exact_field_and_no_raw_value(self):
        self.value['colliders']=[complete(dict(id=1,instanceId=100,path='/home/account/secret',type='MeshCollider',role='world',scene=''),'ColliderIdentity')]
        with self.assertRaises(ValueError) as caught:self.verify()
        error=caught.exception
        self.assertEqual(str(error),'R3_CONTINUOUS_COLLIDER_PATH');self.assertEqual(error.report_location,'$.colliders[0].path')
        self.assertEqual(error.value_sha256,hashlib.sha256(json.dumps('/home/account/secret',separators=(',',':')).encode()).hexdigest())
    def test_partial_bad_field_type_and_nonfinite_have_precise_locations(self):
        self.value['sequences'][1]['frames'][3]['dt']='secret'
        with self.assertRaises(ValueError) as caught:self.verify()
        self.assertEqual(caught.exception.report_location,'$.sequences[1].frames[3].dt')
        self.value['sequences'][1]['frames'][3]['dt']=float('nan')
        with self.assertRaises(ValueError) as caught:self.verify()
        self.assertEqual(str(caught.exception),'R3_CONTINUOUS_NONFINITE');self.assertEqual(caught.exception.report_location,'$.sequences[1].frames[3].dt')
        self.value['sequences'][1]['frames'][3]['dt']=1/30
        self.value['sequences'][1]['frames'][3]['beforeAI']['x']=float('nan')
        with self.assertRaises(ValueError) as caught:self.verify()
        self.assertEqual(caught.exception.report_location,'$.sequences[1].frames[3].beforeAI.x')
    def test_complete_claim_cannot_use_partial_relaxations(self):
        self.value['status']='completed'
        with self.assertRaises(ValueError):self.verify()


class RedactedBoundaries(unittest.TestCase):
    def setUp(self):
        self.value,_,_,_=fixture()
        self.value['status']='fixture-incomplete';self.value['sequences']=self.value['sequences'][:1]
        self.value['sequences'][0]['completed']=False;self.value['sequences'][0]['frames']=self.value['sequences'][0]['frames'][:2]
    def project(self,value=None,raw=None):
        raw=raw if raw is not None else json.dumps(self.value if value is None else value).encode()
        packed=redact_native_report(raw,'R3_CONTINUOUS_SCENE_TEXT',True)
        self.assertLessEqual(len(packed),MAX_REDACTED_BYTES)
        result=json.loads(packed)
        self.assertEqual(set(result),{'schema','mode','semanticsValidated','diagnosticComplete','gameplayAccepted','nativeFailure','rawReportExported','sourceRaw','strictValidationCode','omissionCount','omissionsDropped','omissions','data'})
        self.assertEqual(result['mode'],'FAILED_REDACTED');self.assertTrue(result['nativeFailure'])
        for key in ('semanticsValidated','diagnosticComplete','gameplayAccepted','rawReportExported'):self.assertFalse(result[key])
        self.assertEqual(result['sourceRaw'],dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        self.assertEqual(result['omissionCount'],len(result['omissions'])+result['omissionsDropped'])
        for row in result['omissions']:
            self.assertEqual(set(row),{'location','code','type','jsonBytes','length','sha256'})
            self.assertRegex(row['location'],r'^\$(?:\.[A-Za-z][A-Za-z0-9_]*|\.[<]unknown[>]|\[[0-9]{1,4}\]){0,32}$')
            self.assertRegex(row['code'],r'^R3_CONTINUOUS_[A-Z0-9_]+$');self.assertRegex(row['sha256'],r'^[a-f0-9]{64}$')
        return result
    def test_complete_and_partial_remain_semantically_unvalidated(self):
        for status in ('completed','fixture-incomplete'):
            self.value['status']=status
            result=self.project();self.assertEqual(result['omissionCount'],0)
            self.assertEqual(result['data'],self.value)
    def test_unknown_scene_and_private_path_keep_numeric_contact_frames(self):
        self.value['colliders']=[complete(dict(id=1,instanceId=-8,path='/home/account/secret',scene='private-scene',type='MeshCollider',role='world'),'ColliderIdentity')]
        result=self.project();text=json.dumps(result)
        self.assertNotIn('/home/account/secret',text);self.assertNotIn('private-scene',text)
        self.assertEqual(result['data']['colliders'][0]['id'],1)
        self.assertIsNone(result['data']['colliders'][0]['scene']);self.assertIsNone(result['data']['colliders'][0]['path'])
        self.assertEqual(result['data']['sequences'],self.value['sequences'])
        self.assertEqual({r['code'] for r in result['omissions']},{'R3_CONTINUOUS_SCENE_TEXT','R3_CONTINUOUS_COLLIDER_PATH'})
    def test_unknown_keys_never_appear_even_when_their_values_are_safe(self):
        self.value['sequences'][0]['frames'][0]['private-account-name']=7
        result=self.project();self.assertNotIn('private-account-name',json.dumps(result))
        self.assertEqual(result['omissions'][0]['location'],'$.sequences[0].frames[0].<unknown>')
        self.assertEqual(result['data']['sequences'][0]['frames'][1],self.value['sequences'][0]['frames'][1])
    def test_nan_wrong_type_and_vector_unknown_preserve_siblings_and_indexes(self):
        frame=self.value['sequences'][0]['frames'][0]
        frame['dt']=float('nan');frame['control']=['secret'];frame['beforeAI']['privateKey']='privateBody'
        frame['beforeAI']['x']='secret';frame['beforeAI']['y']=3
        result=self.project();copy=result['data']['sequences'][0]['frames'][0]
        self.assertIsNone(copy['dt']);self.assertIsNone(copy['control']);self.assertIsNone(copy['beforeAI']['x'])
        self.assertEqual(copy['beforeAI']['y'],3);self.assertEqual(len(result['data']['sequences'][0]['frames']),2)
        for secret in ('NaN','secret','privateKey','privateBody'):self.assertNotIn(secret,json.dumps(result))
        self.assertEqual(result['omissionCount'],4)
    def test_deep_mistyped_leaf_is_omitted_without_losing_neighbor_frames(self):
        deep='privateBody'
        for _ in range(27):deep=[deep]
        self.value['sequences'][0]['frames'][0]['step']=deep
        result=self.project();self.assertEqual(result['omissions'][0]['code'],'R3_CONTINUOUS_DEPTH')
        self.assertIsNone(result['data']['sequences'][0]['frames'][0]['step'])
        self.assertEqual(result['data']['sequences'][0]['frames'][1],self.value['sequences'][0]['frames'][1])
        self.assertNotIn('privateBody',json.dumps(result))
    def test_oversize_array_and_string_are_hashed_as_whole_subtrees(self):
        self.value['colliders']=[{}]*4097;self.value['scope']='private'*1000
        result=self.project();self.assertIsNone(result['data']['colliders']);self.assertIsNone(result['data']['scope'])
        self.assertEqual({r['code'] for r in result['omissions']},{'R3_CONTINUOUS_ARRAY_BOUND','R3_CONTINUOUS_STRING_BOUND'})
        self.assertEqual(result['data']['sequences'],self.value['sequences'])
    def test_omissions_are_bounded_and_dropped_count_is_explicit(self):
        self.value.update({'private-field-'+str(i):'secret-'+str(i) for i in range(200)})
        result=self.project();self.assertEqual(len(result['omissions']),128);self.assertEqual(result['omissionCount'],200)
        self.assertEqual(result['omissionsDropped'],72);self.assertEqual(result['data']['sequences'],self.value['sequences'])
        self.assertNotIn('private-field',json.dumps(result));self.assertNotIn('secret-',json.dumps(result))
    def test_missing_required_field_is_recorded_without_fabrication(self):
        del self.value['sequences'][0]['frames'][0]['motor']
        result=self.project();row=result['omissions'][0]
        self.assertEqual(row['type'],'missing');self.assertTrue(row['location'].endswith('.motor'))
        self.assertIsNone(result['data']['sequences'][0]['frames'][0]['motor'])
    def test_truncated_duplicate_or_deep_json_keeps_only_safe_raw_fingerprint(self):
        for raw in (b'{"private-field":"secret",',b'{"schemaVersion":1,"schemaVersion":2}',b'['*1500+b'0'+b']'*1500):
            result=self.project(raw=raw)
            self.assertIsNone(result['data']);self.assertIn(result['omissions'][0]['code'],{'R3_CONTINUOUS_REDACTED_JSON_PARSE','R3_CONTINUOUS_CLOSED_KEYS_REPORT'})
            self.assertNotIn('private-field',json.dumps(result));self.assertNotIn('secret',json.dumps(result))
    def test_output_budget_omits_subtrees_and_raw_limit_is_enforced(self):
        from unittest import mock
        import journey_r3_continuous_contact_report as module
        self.value['colliders']=[complete(dict(id=i,instanceId=i,path='JourneyBootstrap',scene='',type='MeshCollider',role='world'),'ColliderIdentity') for i in range(1000)]
        raw=json.dumps(self.value,separators=(',',':')).encode()
        with mock.patch.object(module,'MAX_REDACTED_BYTES',300*1024):
            result=self.project(raw=raw)
            self.assertIn('R3_CONTINUOUS_REDACTED_JSON_BUDGET',{r['code'] for r in result['omissions']})
            self.assertLessEqual(len(json.dumps(result,separators=(',',':')).encode()),300*1024)
            with self.assertRaisesRegex(ValueError,'REDACTED_RAW_BOUND'):redact_native_report(b' '* (300*1024+1),'R3_CONTINUOUS_SCHEMA',True)
    def test_every_fixed_string_source_is_accepted_by_its_existing_field_gate(self):
        for field,value in EXACT_TEXT.items():
            closed_schema(value,'s',('Sequence.' if field=='fixture' else 'Report.')+field)
        for scene in ('','DontDestroyOnLoad','Assets/DesertRV/Scenes/Journey/JourneyBootstrap.unity','Assets/DesertRV/Scenes/Journey/NightBeacon.unity'):
            closed_schema(scene,'s','ColliderIdentity.scene')
        for name in COLLIDER_NODE_NAMES:closed_schema(name,'s','ColliderIdentity.path')
        values={'ColliderIdentity.type':['BoxCollider','MeshCollider','CapsuleCollider','SphereCollider','CharacterController'],
            'ColliderIdentity.role':['retained-rv','walker','beast','world'],'Beast.phase':['Idle','Stalk','Windup','Attack','Recover','Hit','Dead'],
            'AIQuery.route':['','no-move-in-this-phase','home-forward-then-tangent-if-blocked','windup-eligible-no-move','stalk-forward-then-tangent-if-blocked','attack-forward'],
            'Frame.status':['Menu','Loading','Playing','Paused','Failed','Completed'],'Frame.control':['Driving','OnFoot'],
            'Sequence.upgrades':['Ram, Arc'],'Report.status':['completed','fixture-incomplete'],
            'ArcObservation.sourceQuery':['clear','missing-binding','nonconvex-triangles','nonconvex-aabb-distance-lower-bound','native-supported-closest-point','unsupported-solid-collider','nonconvex-triangles-invalid-geometry'],
            'ArcObservation.sourceSquareDistanceRaw':['NaN','Infinity','-Infinity','0','-0','1.3E-05'],
            'Report.failureCode':['']+['OBSERVER_'+name for name in ('NullReferenceException','MissingMethodException','MissingFieldException','TypeLoadException','TargetInvocationException','AssertionException','ArgumentException','InvalidOperationException','IndexOutOfRangeException','KeyNotFoundException')],
            'Report.unityVersion':['6000.3.19f1'],'Report.producerRunId':['38070456519'],
            'Report.producerCommit':[PRODUCER],'Report.consumerCommit':['b'*40],'Pin.sha256':['a'*64],
            'Pin.path':[INPUT,INPUT.replace('.json','.sha256')]+[x for path in SOURCE_PATHS for x in (path,path+'.meta')],
            'DependencyCheck.inputSha256':['a'*64],'Sequence.name':[p[0] for p in PLANS],'Step.name':[row[0] for p in PLANS for row in p[4]]}
        for field,choices in values.items():
            for value in choices:closed_schema(value,'s',field)


if __name__=='__main__': unittest.main()
