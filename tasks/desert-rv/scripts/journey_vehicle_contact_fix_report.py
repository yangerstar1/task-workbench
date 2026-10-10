"""Closed, bounded validation of original Motor fix regression JSON; no observation rewriting."""
import math
import struct
import re

INPUT_PATH = 'JourneyEvidence/VehicleContactFix/consumer-input.json'
INPUT_ROUTE = 'editor-owned Accelerate/Brake -> MobileInputAdapter.Sample/Throttle -> production JourneyMotor.Tick; W/S-equivalent, no OS events'
QUERY_ROUTE = 'raw/all/overlap queries sampled immediately before motor Tick; motorBufferHits is actual private buffer prefix using mirrored rawCount; obstacleEvents are actual callbacks; predictedAllowed is legacy geometry-only allowance excluding ram kills and the candidate escape/fallback logic'
NATURAL_ROUTE = 'controlled same-PlayMode-frame calls to unchanged BeastActor.Update with fixed observed Time.deltaTime; no actor placement after exterior spawn; not automatic frame timing or human play'
DEPENDENCY_KEYS = {'path','sha256','bytes','kind','packageName','packageVersion'}
SOURCE_REQUIRED = {INPUT_PATH, INPUT_PATH.replace('.json','.sha256'),
    'Assets/DesertRV/Scenes/BodyStudy.unity','Assets/DesertRV/Scenes/BodyStudy.unity.meta',
    'Assets/DesertRV/Scenes/Journey/JourneyContent.asset','Assets/DesertRV/Scenes/Journey/JourneyContent.asset.meta',
    'Assets/DesertRV/Runtime/JourneyMotor.cs','Assets/DesertRV/Runtime/BeastActor.cs','Assets/DesertRV/Runtime/MobileInputAdapter.cs',
    'Assets/DesertRV/Tests/PlayMode/JourneyVehicleContactFixPhysicsTests.cs'}
SOURCE_REQUIRED.update(p+'.meta' for p in list(SOURCE_REQUIRED) if p.endswith('.cs'))
CASES = [(f'{kind}-{fps}-{direction}', 'no-beast' if kind=='baseline' else 'synthetic-overlap', 1/fps, 1 if direction=='W' else -1)
    for fps in (60,30,5) for direction in ('W','S') for kind in ('baseline','pouncer','two-pouncers','armored')]
CASES += [(name,'wall-and-ram-control',1/60,-1 if name=='reverse-ram-installed' else 1)
    for name in ('wall-beast-behind','front-ram','front-no-ram','reverse-ram-installed','initial-wall-overlap')]
CASES += [(f'capacity-{n}','synthetic-self-buffer-saturation',1/30,1) for n in (31,32,33)]
CASES += [(f'deep-front-60-{direction}','synthetic-overlap',1/60,1 if direction=='W' else -1) for direction in ('W','S')]
CASES += [(f'capacity-{n}-with-wall','synthetic-mixed-buffer-wall',1/30,1) for n in (32,33)]
CASES += [('escape-against-wall','synthetic-escape-with-wall',1/60,-1)]
CASES += [('natural-production-update','exterior-spawn-production-ai',1/60,-1)]


GEOMETRY = [
    ('pouncer-side-W','pouncer',.2,True), ('pouncer-side-S','pouncer',-.2,True),
    ('armored-side-W','armored',.2,True), ('armored-side-S','armored',-.2,True),
    ('pouncer-front-W','pouncer',.2,False), ('pouncer-front-S','pouncer',-.2,True),
    ('pouncer-front-long-W','pouncer',7,False), ('pouncer-corner-W','pouncer',.2,False),
    ('pouncer-corner-S','pouncer',-.2,True), ('pouncer-deep-W','pouncer',.2,False),
    ('pouncer-deep-S','pouncer',-.2,False), ('pouncer-zero','pouncer',0,False),
    ('pouncer-boundary-inside-S','pouncer',-.2,True), ('pouncer-boundary-outside-S','pouncer',-.2,False),
    ('pouncer-axis-epsilon-S','pouncer',-.2,False), ('pouncer-tilted-side-W','pouncer',.2,True),
    ('pouncer-tilted-side-S','pouncer',-.2,True), ('armored-tilted-front-W','armored',.2,False),
    ('armored-tilted-front-S','armored',-.2,True), ('pouncer-other-hit-S','pouncer',-.2,False),
    ('pouncer-heading37-side-W','pouncer',.2,True), ('pouncer-heading37-side-S','pouncer',-.2,True),
    ('pouncer-heading37-front-W','pouncer',.2,False), ('pouncer-heading37-front-S','pouncer',-.2,True),
]


def require(ok, code):
    if not ok: raise ValueError('VEHICLE_CONTACT_FIX_REPORT_' + code)


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



def single(value):
    # JsonUtility encodes Single values. Reproduce the native Single arithmetic
    # for geometry tolerances and Vector3.Dot instead of changing the threshold.
    return struct.unpack('<f',struct.pack('<f',value))[0]


def geometry_passed(row):
    start,end,radius=(single(row[k]) for k in ('startAxisDistance','endAxisDistance','radius'))
    initial,final=(single(row[k]) for k in ('initialDepth','finalDepth'))
    agreement=(row['initialOverlap']==(start<radius) and row['finalOverlap']==(end<radius))
    if row['initialOverlap'] and start>single(.00001):
        agreement=agreement and abs(single(initial-single(radius-start)))<single(.0002)
    if row['finalOverlap'] and end>single(.00001):
        agreement=agreement and abs(single(final-single(radius-end)))<single(.0002)
    return (row['allowed']==row['expectedAllowed'] and agreement and
        (not row['allowed'] or row['initialOverlap'] and final<=single(initial+single(.0002)) and single(end+single(.00001))>=start))


def total_travel(frames):
    return single(sum(single(f['actualDistance']) for f in frames))


def dot(left,right):
    parts=[single(single(left[k])*single(right[k])) for k in ('x','y','z')]
    return single(single(parts[0]+parts[1])+parts[2])


def regression_passed(report):
    cases=report['cases']
    if len(cases)!=38 or sum(len(c['frames']) for c in cases)!=2500 or len(report['geometryChecks'])!=24 or not all(geometry_passed(g) for g in report['geometryChecks']):return False
    for case in cases:
        primary=total_travel(f for f in case['frames'] if f['phase'] in {'live','capacity','baseline'})
        if case['requiredLiveMove'] and primary<=single(.02 if case['requestedCapacity']>0 else .2):return False
        if case['requiredLiveBlock'] and primary>=single(.005):return False
        if case['placement']=='no-beast' and not case['baselineMoved']:return False
        if case['placement']=='synthetic-overlap' and not (case['liveActorsSurvived'] and case['deathConfirmed'] and case['released']):return False
        if case['requestedCapacity']>0:
            count=case['requestedCapacity']
            if case['actualCapacity']!=count or any(f['allCount']!=count or f['rawCount']!=min(32,count) for f in case['frames']):return False
            if case['placement']=='synthetic-self-buffer-saturation' and any(not h['self'] for f in case['frames'] for h in f['allHits']):return False
            if case['placement']=='synthetic-mixed-buffer-wall' and (not case['wallHeld'] or any(not any(solid_near_hit(h) for h in f['allHits']) for f in case['frames'])):return False
    named={c['name']:c for c in cases}
    behind=named['wall-beast-behind']
    if not behind['wallHeld'] or behind['deathConfirmed'] or not single(1.25)<=single(behind['end']['z'])<=single(1.41):return False
    ram=named['front-ram']
    def frontal(frame,hit):
        point={k:single(single(hit['point'][k])-single(frame['before'][k])) for k in ('x','y','z')}
        normal={k:-single(hit['normal'][k]) for k in ('x','y','z')}
        return hit['beast'] and not hit['dead'] and hit['distance']>0 and dot(point,frame['forward'])>single(1.8) and dot(normal,frame['forward'])>single(.45)
    if not ram['deathConfirmed'] or ram['end']['z']<6 or not any(f['speedAtCast']>3 and any(frontal(f,h) for h in f['allHits']) for f in ram['frames']):return False
    for name in ('front-no-ram','reverse-ram-installed'):
        case=named[name]
        if case['deathConfirmed'] or not single(2.7)<=abs(single(case['end']['z']))<=single(2.95):return False
    initial=named['initial-wall-overlap']
    if not initial['wallHeld'] or total_travel(initial['frames'])>=single(.005):return False
    escape=named['escape-against-wall']
    if not (escape['wallHeld'] and escape['liveActorsSurvived'] and escape['deathConfirmed']) or escape['released'] or not any(f['phase']=='live' and any(h['beast'] and h['distance']==0 for h in f['allHits']) and any(solid_near_hit(h) for h in f['allHits']) for f in escape['frames']):return False
    return True


def solid_near_hit(hit):
    return not (hit['self'] or hit['walker'] or hit['upward'] or hit['beast']) and 0<hit['distance']<single(.1)


def verify_native_report(report, expectation, input_sha, pins):
    keys(report, ('schemaVersion','scope','regressionsPassed','geometryChecks','status','failureCode','unityVersion','inputRoute','queryRoute','naturalRoute','referenceProducerRunId',
        'proxyExtents','proxyCenterY','maximumDeltaTime','replayDetached','sceneUnloaded','sourceFilesUnchanged','anySyntheticLockReleased',
        'anyNaturalProxyOverlap','dependencyCheck','sourceFiles','colliders','cases'))
    require(type(report['schemaVersion']) is int and report['schemaVersion']==2 and report['scope']=='motor-initial-live-capsule-escape-and-translation-buffer' and report['unityVersion']=='6000.3.19f1' and
        report['status'] in {'fixture-incomplete','completed'} and report['failureCode'] in {'','DEPENDENCY_VERIFICATION_FAILED'},'IDENTITY')
    require(report['inputRoute']==INPUT_ROUTE and report['queryRoute']==QUERY_ROUTE and report['naturalRoute']==NATURAL_ROUTE and
        report['referenceProducerRunId']=='38054694730','ROUTES')
    vector(report['proxyExtents']);require(all(abs(report['proxyExtents'][k]-v)<.000001 for k,v in dict(x=1.05,y=1.12,z=2.7).items()),'PROXY')
    number(report['proxyCenterY']);require(abs(report['proxyCenterY']-1.45)<.000001,'PROXY')
    number(report['maximumDeltaTime'],0,10)
    for k in ('replayDetached','sceneUnloaded','sourceFilesUnchanged','anySyntheticLockReleased','anyNaturalProxyOverlap','regressionsPassed'):boolean(report[k])
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
    sequence(report['geometryChecks'],24)
    for index,row in enumerate(report['geometryChecks']):
        keys(row,('name','kind','travel','initialOverlap','initialDepth','finalOverlap','finalDepth','allowed','expectedAllowed','passed','startAxisDistance','endAxisDistance','radius','endpoint1','endpoint2','boxCenter','boxForward'))
        name,kind,travel,expected_allowed=GEOMETRY[index]
        require(row['name']==name and row['kind']==kind and row['expectedAllowed']==expected_allowed,'GEOMETRY_IDENTITY')
        number(row['travel'],-10,10);require(single(row['travel'])==single(travel),'GEOMETRY_TRAVEL')
        for key in ('initialDepth','finalDepth','startAxisDistance','endAxisDistance'):number(row[key],0,100)
        number(row['radius'],.001,10)
        for key in ('initialOverlap','finalOverlap','allowed','expectedAllowed','passed'):boolean(row[key])
        for key in ('endpoint1','endpoint2','boxCenter','boxForward'):vector(row[key])
        angle=math.radians(37 if '-heading37-' in name else 0)
        require(all(abs(row['boxCenter'][k]-v)<1e-5 for k,v in dict(x=0,y=1.45,z=0).items()),'GEOMETRY_BOX_CENTER')
        require(all(abs(row['boxForward'][k]-v)<1e-5 for k,v in dict(x=math.sin(angle),y=0,z=math.cos(angle)).items()),'GEOMETRY_HEADING')
        require(row['passed']==geometry_passed(row),'GEOMETRY_PREDICATE')
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
    sequence(report['cases'],38);frame_count=0;approach_count=0
    for index,case in enumerate(report['cases']):
        keys(case,('name','placement','outcome','dt','throttle','requestedCapacity','actualCapacity','ramInstalled','liveStationary',
            'deathConfirmed','released','baselineMoved','wallHeld','requiredLiveMove','requiredLiveBlock','liveActorsSurvived','liveActorHealthBefore','liveActorHealthAfter','start','end','actorColliders','frames','approach'))
        name,placement,dt,throttle=CASES[index]
        require(case['name']==name and case['placement']==placement and case['outcome'] in {'recorded','natural-proxy-overlap',
            'natural-vehicle-contact-without-proxy-overlap','bounded-approach-ended-without-contact'},'CASE_IDENTITY')
        number(case['dt'],0,.2+1e-6);number(case['throttle'],-1,1)
        require(abs(case['dt']-dt)<1e-6 and case['throttle']==throttle,'CASE_INPUT')
        for k in ('requestedCapacity','actualCapacity'):integer(case[k],0,512)
        for k in ('ramInstalled','liveStationary','deathConfirmed','released','baselineMoved','wallHeld','requiredLiveMove','requiredLiveBlock','liveActorsSurvived'):boolean(case[k])
        require(not(case['requiredLiveMove'] and case['requiredLiveBlock']),'CONFLICTING_REGRESSION_REQUIREMENT')
        for key in ('liveActorHealthBefore','liveActorHealthAfter'):
            sequence(case[key],2)
            for value in case[key]:integer(value,0,100000)
        require(len(case['liveActorHealthBefore'])==len(case['liveActorHealthAfter']),'HEALTH_PAIR')
        if case['liveActorsSurvived']:
            require(len(case['liveActorHealthBefore'])>0 and case['liveActorHealthBefore']==case['liveActorHealthAfter'] and all(v>0 for v in case['liveActorHealthAfter']),'SURVIVING_ACTOR_HEALTH')
        if placement in {'synthetic-self-buffer-saturation','synthetic-mixed-buffer-wall'}:
            capacity=int(name.split('-')[1]);require(case['requestedCapacity']==capacity,'CAPACITY_IDENTITY')
        else:require(case['requestedCapacity']==case['actualCapacity']==0,'UNEXPECTED_CAPACITY')
        expected_ram=placement in {'synthetic-overlap','wall-and-ram-control','synthetic-escape-with-wall','exterior-spawn-production-ai'} and name!='front-no-ram'
        require(case['ramInstalled']==expected_ram,'RAM_CONFIGURATION')

        expected_block = name.startswith('deep-front-') or (name.startswith('two-pouncers-') and throttle > 0) or placement=='synthetic-mixed-buffer-wall' or name=='escape-against-wall'
        expected_move = placement in {'no-beast','synthetic-overlap','synthetic-self-buffer-saturation'} and not expected_block
        require(case['requiredLiveMove']==expected_move and case['requiredLiveBlock']==expected_block,'REGRESSION_REQUIREMENTS')
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
    require(frame_count<=2520 and approach_count<=720,'TOTAL_FRAMES')
    released=any(c['placement']=='synthetic-overlap' and c['liveStationary'] and c['deathConfirmed'] and c['released'] for c in report['cases'])
    natural_overlap=any(f['proxyOverlaps'] for c in report['cases'] for f in c['approach'])
    if report['status']=='completed':
        for case in report['cases']:
            fps=round(1/case['dt']); placement=case['placement']
            if placement=='no-beast': phases=['baseline']*fps
            elif placement in {'synthetic-overlap','synthetic-escape-with-wall'}:phases=['live']*fps+['after-death-same-held-direction']*fps
            elif placement=='wall-and-ram-control':phases=['control']*120
            elif placement in {'synthetic-self-buffer-saturation','synthetic-mixed-buffer-wall'}:phases=['capacity']*6
            else:phases=['natural-after-approach-W']*60+['natural-after-approach-S']*60+['natural-after-death-S']*60
            require([f['phase'] for f in case['frames']]==phases,'COMPLETE_FRAME_INVENTORY')
            if placement=='exterior-spawn-production-ai':require(1<=len(case['approach'])<=720,'COMPLETE_NATURAL_APPROACH')
            else:require(case['approach']==[],'UNEXPECTED_APPROACH')
        require(len(report['cases'])==38 and frame_count==2500 and len(report['geometryChecks'])==24 and SOURCE_REQUIRED<=seen and report['anySyntheticLockReleased']==released and
            report['anyNaturalProxyOverlap']==natural_overlap,'COMPLETED_SCOPE')
    actual_regression=regression_passed(report)
    if report['status']=='completed':require(report['regressionsPassed']==actual_regression,'REGRESSION_PREDICATE')
    else:require(not report['regressionsPassed'],'INCOMPLETE_REGRESSION_CLAIM')
    complete=(report['status']=='completed' and dep['passed'] and report['replayDetached'] and report['sceneUnloaded'] and
        report['sourceFilesUnchanged'] and report['failureCode']=='' and all(c['baselineMoved'] for c in report['cases'] if c['placement']=='no-beast'))
    return dict(diagnosticComplete=complete,gameplayAccepted=False,caseCount=len(report['cases']),frameCount=frame_count,approachCount=approach_count,
        regressionsPassed=actual_regression and report['regressionsPassed'],geometryCheckCount=len(report['geometryChecks']),nativeClosureMatched=dep['passed'],dependencyMismatchCount=len(dep['mismatches']),anySyntheticLockReleased=released,anyNaturalProxyOverlap=natural_overlap)
