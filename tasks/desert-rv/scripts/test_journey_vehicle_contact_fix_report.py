"""Host-only schema/guard fixtures for r3, never native evidence."""
import copy
import math
import unittest
import journey_vehicle_contact_fix_report as reports


def synthetic_report(expectation=None,pins=None,complete=False):
    if expectation is None:
        rows=[dict(path=f'Assets/Fixture/{i:04}.asset',sha256='a'*64,bytes=1,kind='asset',packageName='',packageVersion='') for i in range(772)]
        rows += [dict(path=f'Packages/com.unity.render-pipelines.universal/Fixture/{i:04}.shader',sha256='a'*64,bytes=1,kind='package',packageName='com.unity.render-pipelines.universal',packageVersion='17.3.0') for i in range(24)]
        expectation=dict(dependencies=rows,consumerCommit='c'*40)
    pins=pins or {p:'d'*64 for p in reports.SOURCE_REQUIRED}
    input_sha=pins.get(reports.INPUT_PATH,'b'*64)
    report=dict(schemaVersion=2,scope='motor-initial-live-capsule-escape-and-translation-buffer',regressionsPassed=False,geometryChecks=[],
        status='fixture-incomplete',failureCode='',unityVersion='6000.3.19f1',inputRoute=reports.INPUT_ROUTE,
        queryRoute=reports.QUERY_ROUTE,naturalRoute=reports.NATURAL_ROUTE,referenceProducerRunId='38054694730',
        proxyExtents=dict(x=1.05,y=1.12,z=2.7),proxyCenterY=1.45,maximumDeltaTime=.3333333,
        replayDetached=False,sceneUnloaded=False,sourceFilesUnchanged=False,anySyntheticLockReleased=False,anyNaturalProxyOverlap=False,
        dependencyCheck=dict(status='verified-native-closure',inputSha256=input_sha,failureCode='',passed=True,expectedCount=796,actualCount=796,
            actualDependencies=copy.deepcopy(expectation['dependencies']),mismatches=[]),
        sourceFiles=[dict(path=p,sha256=pins[p]) for p in sorted(reports.SOURCE_REQUIRED)],colliders=[],cases=[])
    if not complete:return report,expectation,input_sha,pins
    def vec(z=0):return dict(x=0,y=0,z=z)
    def hit(collider=1,beast=False,distance=0,self_hit=False):
        return dict(collider=collider,distance=distance,point=vec(2),normal=vec(-1),self=self_hit,walker=False,upward=False,beast=beast,dead=False)
    for identifier,role in ((1,'synthetic-self'),(2,'synthetic-wall'),(3,'actual-pouncer')):
        report['colliders'].append(dict(id=identifier,hierarchy='HostOnlyFixture/'+str(identifier),type='BoxCollider',mesh='',meshGuid='',role=role,trigger=False,convex=False,
            min=vec(),max=vec(1),capsuleCenter=vec(),capsuleRadius=0,capsuleHeight=0))
    for name,placement,dt,throttle in reports.CASES:
        fps=round(1/dt);capacity=int(name.split('-')[1]) if name.startswith('capacity-') else 0
        block=name.startswith('deep-front-') or name.startswith('two-pouncers-') and throttle>0 or placement=='synthetic-mixed-buffer-wall' or name=='escape-against-wall'
        move=placement in {'no-beast','synthetic-overlap','synthetic-self-buffer-saturation'} and not block
        if placement=='no-beast':phases=['baseline']*fps
        elif placement in {'synthetic-overlap','synthetic-escape-with-wall'}:phases=['live']*fps+['after-death-same-held-direction']*fps
        elif placement=='wall-and-ram-control':phases=['control']*120
        elif capacity:phases=['capacity']*6
        else:phases=['natural-after-approach-W']*60+['natural-after-approach-S']*60+['natural-after-death-S']*60
        frames=[]
        for i,phase in enumerate(phases):
            all_hits=[]
            if capacity:
                all_hits=[hit(self_hit=True) for _ in range(capacity)]
                if block:all_hits[-1]=hit(2,distance=.03)
            elif name=='escape-against-wall':all_hits=[hit(3,beast=True),hit(2,distance=.03)]
            elif name=='front-ram' and i==0:all_hits=[hit(3,beast=True,distance=.1)]
            raw=copy.deepcopy(all_hits[:32]);distance=(.01 if capacity else .5/fps) if move else 0
            frames.append(dict(frame=i,rawCount=len(raw),allCount=len(all_hits),vehicleHealth=100,phase=phase,state='Playing',control='Driving',dt=dt,throttle=throttle,
                speedBefore=0,speedAtCast=4 if name=='front-ram' and i==0 else 0,speedAfter=0,intendedDistance=distance,actualDistance=distance,predictedAllowed=0,
                castExecuted=True,rawSaturated=len(raw)==32,powerConnected=False,before=vec(),after=vec(distance),center=vec(),forward=vec(1),
                overlaps=[],rawHits=raw,allHits=all_hits,motorBufferHits=copy.deepcopy(raw),obstacleEvents=[]))
        has_health=placement in {'synthetic-overlap','synthetic-escape-with-wall'}
        health=[100]*(2 if name.startswith('two-pouncers-') else 1) if has_health else []
        approach=[] if placement!='exterior-spawn-production-ai' else [dict(step=0,healthBefore=100,healthAfter=100,actualUpdateDelta=dt,positions=[vec(),vec()],phases=['Stalk','Stalk'],proxyOverlaps=[])]
        end_z={'wall-beast-behind':1.3,'front-ram':6.5,'front-no-ram':2.8,'reverse-ram-installed':-2.8}.get(name,.5 if move else 0)
        report['cases'].append(dict(name=name,placement=placement,outcome='recorded',dt=dt,throttle=throttle,requestedCapacity=capacity,actualCapacity=capacity,
            ramInstalled=placement in {'synthetic-overlap','wall-and-ram-control','synthetic-escape-with-wall','exterior-spawn-production-ai'} and name!='front-no-ram',
            liveStationary=block,deathConfirmed=has_health or name=='front-ram',released=placement=='synthetic-overlap',baselineMoved=placement=='no-beast',
            wallHeld=placement=='synthetic-mixed-buffer-wall' or name in {'wall-beast-behind','initial-wall-overlap','escape-against-wall'},start=vec(),end=vec(end_z),
            requiredLiveMove=move,requiredLiveBlock=block,liveActorsSurvived=has_health,liveActorHealthBefore=health,liveActorHealthAfter=health.copy(),
            actorColliders=[3] if has_health else [],frames=frames,approach=approach))
    for name,kind,travel,expected in reports.GEOMETRY:
        angle=math.radians(37 if '-heading37-' in name else 0)
        report['geometryChecks'].append(dict(name=name,kind=kind,travel=travel,initialOverlap=True,initialDepth=.5,finalOverlap=True,finalDepth=.5,
            allowed=expected,expectedAllowed=expected,passed=True,startAxisDistance=.5,endAxisDistance=.5,radius=1,endpoint1=vec(),endpoint2=vec(1),
            boxCenter=dict(x=0,y=1.45,z=0),boxForward=dict(x=math.sin(angle),y=0,z=math.cos(angle))))
    report.update(status='completed',replayDetached=True,sceneUnloaded=True,sourceFilesUnchanged=True,anySyntheticLockReleased=True,regressionsPassed=True)
    return report,expectation,input_sha,pins


class FixReportValidation(unittest.TestCase):
    def test_complete_host_fixture_is_bounded_and_never_gameplay_acceptance(self):
        result=reports.verify_native_report(*synthetic_report(complete=True))
        self.assertTrue(result['diagnosticComplete']);self.assertTrue(result['regressionsPassed']);self.assertFalse(result['gameplayAccepted'])
        self.assertEqual((result['caseCount'],result['frameCount'],result['geometryCheckCount']),(38,2500,24))

    def test_geometry_predicate_is_recomputed_and_failed_original_is_preservable(self):
        args=synthetic_report(complete=True);r=args[0];r['geometryChecks'][0]['allowed']=False
        with self.assertRaisesRegex(ValueError,'GEOMETRY_PREDICATE'):reports.verify_native_report(*args)
        r['geometryChecks'][0]['passed']=False;r['regressionsPassed']=False
        result=reports.verify_native_report(*args);self.assertFalse(result['regressionsPassed'])

    def test_independent_native_penetration_disagreement_cannot_pass(self):
        for key,value in [('initialOverlap',False),('initialDepth',.7),('finalDepth',.7),('endAxisDistance',.4)]:
            args=synthetic_report(complete=True);args[0]['geometryChecks'][0][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'GEOMETRY_PREDICATE'):reports.verify_native_report(*args)

    def test_heading_and_exact_geometry_inventory_are_required(self):
        for mutation in (lambda r:r['geometryChecks'].pop(),lambda r:r['geometryChecks'][20]['boxForward'].update(x=0),
                         lambda r:r['geometryChecks'][0].update(name='other'),lambda r:r['geometryChecks'][0].update(expectedAllowed=False)):
            args=synthetic_report(complete=True);mutation(args[0])
            with self.assertRaises(ValueError):reports.verify_native_report(*args)

    def test_move_block_health_and_saturation_regressions_are_recomputed(self):
        mutations=[lambda c:[f.update(actualDistance=0) for f in c['frames']],lambda c:c.update(actualCapacity=31),lambda c:c.update(liveActorsSurvived=False)]
        names=['capacity-32','capacity-32','pouncer-60-W']
        for name,mutation in zip(names,mutations):
            args=synthetic_report(complete=True);r=args[0];mutation(next(c for c in r['cases'] if c['name']==name))
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'REGRESSION_PREDICATE'):reports.verify_native_report(*args)
            r['regressionsPassed']=False;self.assertFalse(reports.verify_native_report(*args)['regressionsPassed'])
        args=synthetic_report(complete=True);next(c for c in args[0]['cases'] if c['name']=='pouncer-60-W')['liveActorHealthAfter'][0]=0
        with self.assertRaisesRegex(ValueError,'SURVIVING_ACTOR_HEALTH'):reports.verify_native_report(*args)

    def test_world_wall_and_front_ram_guards_are_recomputed(self):
        for name,mutation in [('wall-beast-behind',lambda c:c['end'].update(z=6)),('front-ram',lambda c:c.update(deathConfirmed=False)),
            ('front-no-ram',lambda c:c.update(deathConfirmed=True)),('initial-wall-overlap',lambda c:c.update(wallHeld=False)),
            ('escape-against-wall',lambda c:c.update(released=True)),('capacity-33-with-wall',lambda c:c.update(wallHeld=False))]:
            args=synthetic_report(complete=True);r=args[0];mutation(next(c for c in r['cases'] if c['name']==name))
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'REGRESSION_PREDICATE'):reports.verify_native_report(*args)
            r['regressionsPassed']=False;self.assertFalse(reports.verify_native_report(*args)['regressionsPassed'])

    def test_exact_case_frames_configuration_source_and_schema(self):
        for mutation in (lambda r:r['cases'].pop(),lambda r:r['cases'][0]['frames'].pop(),lambda r:r['sourceFiles'].pop(),
            lambda r:r['cases'][0].update(requiredLiveMove=False),lambda r:r['cases'][0].update(ramInstalled=True),
            lambda r:r.update(schemaVersion=1),lambda r:r.update(scope='other'),lambda r:r.update(privateExtra='never export'),
            lambda r:r['sourceFiles'][0].update(path='/private/secret'),lambda r:r['cases'][0]['frames'][0].update(actualDistance=float('nan'))):
            args=synthetic_report(complete=True);mutation(args[0])
            with self.assertRaises(ValueError):reports.verify_native_report(*args)

    def test_failed_dependency_and_cleanup_are_preserved_without_acceptance(self):
        args=synthetic_report();dep=args[0]['dependencyCheck'];row=dep['actualDependencies'][-1];row['sha256']='e'*64
        dep.update(passed=False,status='failed',failureCode='DEPENDENCY_VERIFICATION_FAILED',mismatches=[row['path']])
        result=reports.verify_native_report(*args);self.assertFalse(result['diagnosticComplete']);self.assertFalse(result['regressionsPassed'])
        self.assertEqual(result['dependencyMismatchCount'],1)
        for key in ('replayDetached','sceneUnloaded','sourceFilesUnchanged'):
            args=synthetic_report(complete=True);args[0][key]=False
            self.assertFalse(reports.verify_native_report(*args)['diagnosticComplete'])


if __name__=='__main__':unittest.main()
