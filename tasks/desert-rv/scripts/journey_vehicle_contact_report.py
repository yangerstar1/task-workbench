"""Closed, bounded validation of the original vehicle-contact JSON; no observation rewriting."""
import math
import re

INPUT_PATH = 'JourneyEvidence/VehicleContact/consumer-input.json'
INPUT_ROUTE = 'editor-owned Accelerate/Brake -> MobileInputAdapter.Sample/Throttle -> production JourneyMotor.Tick; W/S-equivalent, no OS events'
QUERY_ROUTE = 'raw/all/overlap queries sampled immediately before motor Tick; motorBufferHits is actual private buffer prefix using mirrored rawCount; obstacleEvents are actual callbacks; predictedAllowed excludes ram kills'
NATURAL_ROUTE = 'controlled same-PlayMode-frame calls to unchanged BeastActor.Update with fixed observed Time.deltaTime; no actor placement after exterior spawn; not automatic frame timing or human play'
DEPENDENCY_KEYS = {'path','sha256','bytes','kind','packageName','packageVersion'}
SOURCE_REQUIRED = {INPUT_PATH, INPUT_PATH.replace('.json','.sha256'),
    'Assets/DesertRV/Scenes/BodyStudy.unity','Assets/DesertRV/Scenes/BodyStudy.unity.meta',
    'Assets/DesertRV/Scenes/Journey/JourneyContent.asset','Assets/DesertRV/Scenes/Journey/JourneyContent.asset.meta',
    'Assets/DesertRV/Runtime/JourneyMotor.cs','Assets/DesertRV/Runtime/BeastActor.cs','Assets/DesertRV/Runtime/MobileInputAdapter.cs',
    'Assets/DesertRV/Tests/PlayMode/JourneyVehicleContactPhysicsTests.cs'}
SOURCE_REQUIRED.update(p+'.meta' for p in list(SOURCE_REQUIRED) if p.endswith('.cs'))
CASES = [(f'{kind}-{fps}-{direction}', 'no-beast' if kind=='baseline' else 'synthetic-overlap', 1/fps, 1 if direction=='W' else -1)
    for fps in (60,30,5) for direction in ('W','S') for kind in ('baseline','pouncer','two-pouncers','armored')]
CASES += [(name,'wall-and-ram-control',1/60,-1 if name=='reverse-ram-installed' else 1)
    for name in ('wall-beast-behind','front-ram','front-no-ram','reverse-ram-installed','initial-wall-overlap')]
CASES += [(f'capacity-{n}','synthetic-self-buffer-saturation',1/30,1) for n in (31,32,33)]
CASES += [('natural-production-update','exterior-spawn-production-ai',1/60,-1)]


def require(ok, code):
    if not ok: raise ValueError('VEHICLE_CONTACT_REPORT_' + code)


def keys(value, expected):
    require(type(value) is dict and set(value)==set(expected), 'KEYS')


def boolean(value): require(type(value) is bool, 'BOOL')
def integer(value, low=0, high=1000000): require(type(value) is int and low <= value <= high, 'INT')
def number(value, low=-1000000, high=1000000): require(type(value) in (int,float) and math.isfinite(value) and low <= value <= high, 'NUMBER')
def sequence(value, limit): require(type(value) is list and len(value)<=limit, 'LIST')
def digest(value): require(type(value) is str and re.fullmatch('[a-f0-9]{64}',value), 'DIGEST')
def vector(value):
    keys(value, ('x','y','z'))
    for v in value.values(): number(v)

def relative(value):
    require(type(value) is str and 0<len(value)<=512 and not value.startswith('/') and '\\' not in value and
        all(c.isprintable() for c in value) and all(p not in ('','.','..') for p in value.split('/')), 'RELATIVE_PATH')

def dependencies(rows):
    sequence(rows,2048); found={}
    for row in rows:
        keys(row,DEPENDENCY_KEYS);relative(row['path']);digest(row['sha256']);integer(row['bytes'],1,128*1024**2)
        require(row['path'] not in found,'DUPLICATE_DEPENDENCY');found[row['path']]=row
        if row['kind']=='asset':
            require(row['path'].startswith('Assets/') and row['packageName']==row['packageVersion']=='','ASSET')
        else:
            require(row['kind']=='package' and type(row['packageName']) is str and re.fullmatch(r'com\.unity\.[a-z0-9.-]+',row['packageName']) and
                row['path'].startswith('Packages/'+row['packageName']+'/') and type(row['packageVersion']) is str and
                re.fullmatch(r'[A-Za-z0-9.+-]{1,64}',row['packageVersion']),'PACKAGE')
    return found


def verify_native_report(report, expectation, input_sha, pins):
    keys(report, ('schemaVersion','status','failureCode','unityVersion','inputRoute','queryRoute','naturalRoute','referenceProducerRunId',
        'proxyExtents','proxyCenterY','maximumDeltaTime','replayDetached','sceneUnloaded','sourceFilesUnchanged','anySyntheticLockReleased',
        'anyNaturalProxyOverlap','dependencyCheck','sourceFiles','colliders','cases'))
    require(type(report['schemaVersion']) is int and report['schemaVersion']==1 and report['unityVersion']=='6000.3.19f1' and
        report['status'] in {'fixture-incomplete','completed'} and report['failureCode'] in {'','DEPENDENCY_VERIFICATION_FAILED'},'IDENTITY')
    require(report['inputRoute']==INPUT_ROUTE and report['queryRoute']==QUERY_ROUTE and report['naturalRoute']==NATURAL_ROUTE and
        report['referenceProducerRunId']=='38054694730','ROUTES')
    vector(report['proxyExtents']);require(all(abs(report['proxyExtents'][k]-v)<.000001 for k,v in dict(x=1.05,y=1.12,z=2.7).items()),'PROXY')
    number(report['proxyCenterY']);require(abs(report['proxyCenterY']-1.45)<.000001,'PROXY')
    number(report['maximumDeltaTime'],0,10)
    for k in ('replayDetached','sceneUnloaded','sourceFilesUnchanged','anySyntheticLockReleased','anyNaturalProxyOverlap'):boolean(report[k])
    sequence(report['sourceFiles'],1024); seen=set()
    for row in report['sourceFiles']:
        keys(row,('path','sha256'));relative(row['path']);digest(row['sha256'])
        require(row['path'] not in seen and pins.get(row['path'])==row['sha256'],'SOURCE_PIN');seen.add(row['path'])
    dep=report['dependencyCheck'];keys(dep,('status','inputSha256','failureCode','passed','expectedCount','actualCount','actualDependencies','mismatches'))
    require(dep['status'] in {'not-started','checking','failed','verified-native-closure'} and
        dep['failureCode'] in {'','DEPENDENCY_VERIFICATION_FAILED'},'DEPENDENCY_STATUS');boolean(dep['passed'])
    expected=dependencies(expectation['dependencies']);actual=dependencies(dep['actualDependencies'])
    require(len(expected)==796 and sum(r['kind']=='package' for r in expected.values())==24,'EXPECTED_CLOSURE')
    integer(dep['expectedCount'],0,796);integer(dep['actualCount'],0,2048)
    require(dep['inputSha256'] in (None,'',input_sha),'INPUT_PIN');sequence(dep['mismatches'],2048)
    for path in dep['mismatches']:relative(path)
    mismatches=sorted(p for p in set(expected)|set(actual) if expected.get(p)!=actual.get(p))
    require(dep['mismatches']==sorted(set(dep['mismatches'])),'MISMATCH_UNIQUE')
    if dep['expectedCount']:
        require(dep['expectedCount']==796 and dep['actualCount']==len(actual) and dep['mismatches']==mismatches,'ACTUAL_CLOSURE')
    else:require(not dep['passed'] and dep['actualCount']==0 and not dep['mismatches'],'UNSTARTED_CLOSURE')
    if dep['passed']:
        require(dep['status']=='verified-native-closure' and dep['inputSha256']==input_sha and dep['failureCode']=='' and
            dep['expectedCount']==dep['actualCount']==796 and not mismatches,'CLOSURE_MATCH')
    else:require(dep['status']!='verified-native-closure','FALSE_CLOSURE')
    sequence(report['colliders'],512);ids=set()
    for row in report['colliders']:
        keys(row,('id','hierarchy','type','mesh','meshGuid','role','trigger','convex','min','max','capsuleCenter','capsuleRadius','capsuleHeight'))
        integer(row['id'],1,512);require(row['id'] not in ids,'COLLIDER_ID');ids.add(row['id']);relative(row['hierarchy'])
        require(row['type'] in {'MeshCollider','BoxCollider','CapsuleCollider','SphereCollider','CharacterController','WheelCollider'} and
            row['role'] in {'retained-rv','authored-road','actual-armored','actual-pouncer','synthetic-self','synthetic-wall','observed'},'COLLIDER_ENUM')
        boolean(row['trigger']);boolean(row['convex'])
        for k in ('min','max','capsuleCenter'):vector(row[k])
        require(all(row['min'][k]<=row['max'][k] for k in ('x','y','z')),'COLLIDER_BOUNDS')
        for k in ('capsuleRadius','capsuleHeight'):number(row[k],0,1000)
        if row['mesh']:
            relative(row['mesh']);require(row['mesh'] in seen and row['mesh'] in pins,'MESH_PIN')
            require(type(row['meshGuid']) is str and re.fullmatch('[a-f0-9]{32}',row['meshGuid']),'MESH_GUID')
        else:require(row['mesh'] in (None,'') and row['meshGuid'] in (None,''),'EMPTY_MESH')
    def collider_ids(rows,limit=512):
        if rows is None:return
        sequence(rows,limit);require(len(rows)==len(set(rows)),'DUPLICATE_IDS')
        for value in rows:integer(value,1,512);require(value in ids,'UNKNOWN_ID')
    def hits(rows,limit):
        sequence(rows,limit)
        for hit in rows:
            keys(hit,('collider','distance','point','normal','self','walker','upward','beast','dead'))
            integer(hit['collider'],0,512);require(hit['collider']==0 or hit['collider'] in ids,'UNKNOWN_HIT')
            number(hit['distance'],0,10000);vector(hit['point']);vector(hit['normal'])
            for key in ('self','walker','upward','beast','dead'):boolean(hit[key])
            require(not hit['dead'] or hit['beast'],'DEAD_BEAST')
    sequence(report['cases'],33);frame_count=0;approach_count=0
    for index,case in enumerate(report['cases']):
        keys(case,('name','placement','outcome','dt','throttle','requestedCapacity','actualCapacity','ramInstalled','liveStationary',
            'deathConfirmed','released','baselineMoved','wallHeld','start','end','actorColliders','frames','approach'))
        name,placement,dt,throttle=CASES[index]
        require(case['name']==name and case['placement']==placement and case['outcome'] in {'recorded','natural-proxy-overlap',
            'natural-vehicle-contact-without-proxy-overlap','bounded-approach-ended-without-contact'},'CASE_IDENTITY')
        number(case['dt'],0,.2+1e-6);number(case['throttle'],-1,1)
        require(abs(case['dt']-dt)<1e-6 and case['throttle']==throttle,'CASE_INPUT')
        for k in ('requestedCapacity','actualCapacity'):integer(case[k],0,512)
        for k in ('ramInstalled','liveStationary','deathConfirmed','released','baselineMoved','wallHeld'):boolean(case[k])
        vector(case['start']);vector(case['end']);collider_ids(case['actorColliders'],2)
        sequence(case['frames'],512);sequence(case['approach'],720);frame_count+=len(case['frames']);approach_count+=len(case['approach'])
        for i,frame in enumerate(case['frames']):
            keys(frame,('frame','rawCount','allCount','vehicleHealth','phase','state','control','dt','throttle','speedBefore','speedAtCast',
                'speedAfter','intendedDistance','actualDistance','predictedAllowed','castExecuted','rawSaturated','powerConnected',
                'before','after','center','forward','overlaps','rawHits','allHits','motorBufferHits','obstacleEvents'))
            integer(frame['frame'],0,511);require(frame['frame']==i,'FRAME_ORDER')
            require(frame['phase'] in {'baseline','live','after-death-same-held-direction','control','capacity','natural-after-approach-W',
                'natural-after-approach-S','natural-after-death-S'} and frame['state'] in {'Menu','Loading','Playing','Paused','Failed','Completed'} and
                frame['control'] in {'Driving','OnFoot'},'FRAME_ENUM')
            integer(frame['rawCount'],0,32);integer(frame['allCount'],0,512);integer(frame['vehicleHealth'],0,100000)
            for k in ('dt','throttle','speedBefore','speedAtCast','speedAfter','intendedDistance','actualDistance','predictedAllowed'):number(frame[k])
            require(abs(frame['dt']-dt)<1e-6 and -1<=frame['throttle']<=1,'FRAME_INPUT')
            for k in ('castExecuted','rawSaturated','powerConnected'):boolean(frame[k])
            require(frame['rawSaturated']==(frame['rawCount']==32),'RAW_SATURATION')
            for k in ('before','after','center','forward'):vector(frame[k])
            collider_ids(frame['overlaps']);hits(frame['rawHits'],32);hits(frame['motorBufferHits'],32);hits(frame['allHits'],512);hits(frame['obstacleEvents'],32)
            require(len(frame['rawHits'])==len(frame['motorBufferHits'])==frame['rawCount'] and len(frame['allHits'])==frame['allCount'],'HIT_COUNTS')
            if not frame['castExecuted']:require(frame['rawCount']==frame['allCount']==0 and not frame['obstacleEvents'],'UNEXECUTED_CAST')
        for i,frame in enumerate(case['approach']):
            keys(frame,('step','healthBefore','healthAfter','actualUpdateDelta','positions','phases','proxyOverlaps'))
            integer(frame['step'],0,719);require(frame['step']==i and placement=='exterior-spawn-production-ai','APPROACH_ORDER')
            for k in ('healthBefore','healthAfter'):integer(frame[k],0,100000)
            number(frame['actualUpdateDelta'],0,.100001);sequence(frame['positions'],2);sequence(frame['phases'],2)
            require(len(frame['positions'])==len(frame['phases'])==2,'ACTORS')
            for v in frame['positions']:vector(v)
            require(all(p in {'Idle','Stalk','Windup','Attack','Recover','Hit','Dead'} for p in frame['phases']),'BEAST_PHASE')
            collider_ids(frame['proxyOverlaps'],2)
    require(frame_count<=2200 and approach_count<=720,'TOTAL_FRAMES')
    released=any(c['placement']=='synthetic-overlap' and c['liveStationary'] and c['deathConfirmed'] and c['released'] for c in report['cases'])
    natural_overlap=any(f['proxyOverlaps'] for c in report['cases'] for f in c['approach'])
    if report['status']=='completed':
        for case in report['cases']:
            fps=round(1/case['dt']); placement=case['placement']
            if placement=='no-beast': phases=['baseline']*fps
            elif placement=='synthetic-overlap':phases=['live']*fps+['after-death-same-held-direction']*fps
            elif placement=='wall-and-ram-control':phases=['control']*120
            elif placement=='synthetic-self-buffer-saturation':phases=['capacity']*6
            else:phases=['natural-after-approach-W']*60+['natural-after-approach-S']*60+['natural-after-death-S']*60
            require([f['phase'] for f in case['frames']]==phases,'COMPLETE_FRAME_INVENTORY')
            if placement=='exterior-spawn-production-ai':require(1<=len(case['approach'])<=720,'COMPLETE_NATURAL_APPROACH')
            else:require(case['approach']==[],'UNEXPECTED_APPROACH')
        require(len(report['cases'])==33 and SOURCE_REQUIRED<=seen and report['anySyntheticLockReleased']==released and
            report['anyNaturalProxyOverlap']==natural_overlap,'COMPLETED_SCOPE')
    complete=(report['status']=='completed' and dep['passed'] and report['replayDetached'] and report['sceneUnloaded'] and
        report['sourceFilesUnchanged'] and report['failureCode']=='' and all(c['baselineMoved'] for c in report['cases'] if c['placement']=='no-beast'))
    return dict(diagnosticComplete=complete,gameplayAccepted=False,caseCount=len(report['cases']),frameCount=frame_count,approachCount=approach_count,
        nativeClosureMatched=dep['passed'],dependencyMismatchCount=len(dep['mismatches']),anySyntheticLockReleased=released,anyNaturalProxyOverlap=natural_overlap)
