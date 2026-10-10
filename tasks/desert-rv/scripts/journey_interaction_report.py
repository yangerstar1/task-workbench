"""Bounded shape/identity validator for the untrusted native JSON, not a physics oracle.

Import verify_native_report(report, consumer_input, input_sha256). The caller must
separately establish exact producer/consumer provenance, XML result, and unchanged
project bytes. This helper never turns native observations into gameplay approval.
"""
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import PurePosixPath

INPUT_PATH = 'JourneyEvidence/InteractionReachability/consumer-input.json'
SHA = re.compile(r'[0-9a-f]{64}\Z')
DEPENDENCY_KEYS = {'path', 'sha256', 'bytes', 'kind', 'packageName', 'packageVersion'}
REPORT_KEYS = set('schemaVersion status unityVersion scope driverScope powerScope sourceUnchanged copiesDeleted setupRestored dependencyCheck sourceFiles samples cleanupErrors'.split())
CHECK_KEYS = set('status inputPath inputSha256 snapshotError snapshotFailureCode snapshotFailurePath expectedCount actualCount passed actualDependencies mismatches'.split())
SURFACE_KEYS = set('hierarchy type objectId mesh meshSha256 enabled active trigger min max'.split())
SAMPLE_KEYS = set('region purpose approach predicate foot eye target hitPoint hitNormal driverLinecastPoint driverLinecastNormal distance limit hitDistance endpointDistance savedVehicleDistance driverEntryDistance driverLinecastDistance driverLinecastEndpointDistance withinRange productionCanReachPoint hasFirstHit acceptedSurfaceIsFirstHit supported standingCapsuleClear driverDistancePromptPredicate driverDistanceEnterPredicate driverLinecastHasHit driverLinecastAllowsGeometry acceptedSurface firstHit support driverLinecastHit standingBlockers'.split())
SCOPES = {
    'scope':'saved-scene-static-native-physics; no runtime progression or input',
    'driverScope':'distance prompt predicate and native Linecast geometry only; FindInteraction/TryEnterDriver not invoked; door remains saved-closed',
    'powerScope':'same production CanReachPoint gate for connect/disconnect; no connection state or parked-RV transition exercised'}
SUPPLIES={1:['apron-ammo','garage-kit'],2:['container-ammo','canopy-kit'],3:['tower-ammo','relay-kit']}

def allowed_approaches(region,purpose):
    if purpose in (f'supply:region-{region}/optional/{item}' for item in SUPPLIES[region]):
        return {'authored-front-lateral-'+v for v in ('-0.3','0','0.3')}
    if purpose=='cabin-workbench': return {'cabin-aisle-lateral-'+v for v in ('-0.3','0','0.3')}
    if purpose=='driver-prompt-and-return-geometry': return {'door-outside-along-'+v for v in ('-0.55','0','0.55')}
    if region<=2 and purpose==('ram-salvage' if region==1 else 'coil-salvage'):
        return {'bench-front-lateral-'+v for v in ('-0.3','0','0.3')}
    if region>=2 and purpose=='power-connect-and-disconnect': return {'cabinet-front-lateral-'+v for v in ('-0.45','0','0.45')}
    return set()

def need(ok, reason):
    if not ok:
        raise ValueError(reason)

def text(value, limit=4096, nullable=False):
    need(nullable and value is None or isinstance(value, str) and len(value) <= limit,
         'Invalid or oversized text field')

def relative(value):
    text(value)
    need(bool(value) and not PurePosixPath(value).is_absolute() and '\\' not in value
         and all(p not in ('', '.', '..') for p in value.split('/'))
         and not any(ord(c) < 32 or ord(c) == 127 for c in value), 'Unsafe relative evidence path')

def number(value):
    need(type(value) in (int, float) and math.isfinite(value), 'Nonfinite/non-numeric geometry')

def boolean(value):
    need(type(value) is bool, 'Non-boolean state')

def vector(value):
    need(isinstance(value, dict) and set(value) == {'x', 'y', 'z'}, 'Invalid vector')
    for item in value.values(): number(item)

def dependency(value):
    need(isinstance(value, dict) and set(value) == DEPENDENCY_KEYS, 'Unexpected dependency fields')
    relative(value['path'])
    need(type(value['bytes']) is int and value['bytes'] >= 0, 'Invalid dependency length')
    for key in ('kind', 'packageName', 'packageVersion'): text(value[key], 128)
    if value['kind'] == 'builtin':
        need(value['path'] in ('Resources/unity_builtin_extra', 'Library/unity default resources')
             and value['sha256'] == '' and value['bytes'] == 0 and value['packageName'] == ''
             and value['packageVersion'] == '', 'Unknown builtin')
    else:
        need(value['kind'] in ('asset', 'package') and isinstance(value['sha256'], str)
             and SHA.fullmatch(value['sha256']), 'Invalid dependency kind/hash')
        need(value['path'].startswith('Assets/' if value['kind'] == 'asset' else 'Packages/'), 'Dependency path/kind mismatch')
        if value['kind']=='asset': need(value['packageName']==value['packageVersion']=='','Asset has package metadata')
        else: need(bool(value['packageName']) and bool(value['packageVersion']) and value['path'].startswith('Packages/'+value['packageName']+'/'),'Package name/path mismatch')
    return value['path']

def surface(value):
    need(isinstance(value, dict) and set(value)==SURFACE_KEYS, 'Missing/unknown collider fields')
    for key in ('hierarchy', 'type', 'objectId'): text(value[key]); need(bool(value[key]), 'Missing collider identity')
    need(len(value['hierarchy'])<=1024 and value['hierarchy'].isprintable(), 'Unsafe collider hierarchy')
    need(value['type'] in ('BoxCollider','MeshCollider','SphereCollider','CapsuleCollider','TerrainCollider','WheelCollider','CharacterController'), 'Unknown collider class')
    need(re.fullmatch(r'GlobalObjectId_V1-[0-9]+-[a-f0-9]{32}--?[0-9]+--?[0-9]+',value['objectId']), 'Invalid global collider identity')
    for key in ('enabled', 'active', 'trigger'): boolean(value[key])
    for key in ('min', 'max'): vector(value[key])
    need(all(value['min'][axis] <= value['max'][axis] for axis in ('x','y','z')), 'Invalid collider bounds')
    text(value.get('mesh'), nullable=True); text(value.get('meshSha256'), 64, nullable=True)
    if value.get('mesh'):
        relative(value['mesh']); need(value['mesh'].startswith(('Assets/','Packages/','Resources/','Library/')), 'Unknown mesh root')
    if value.get('meshSha256'): need(SHA.fullmatch(value['meshSha256']), 'Invalid mesh hash')

def verify_native_report(report, consumer_input, input_sha256):
    need(isinstance(report, dict) and report.get('schemaVersion') == 2, 'Native report schema')
    need(set(report)==REPORT_KEYS, 'Unknown/missing native report fields')
    for key,value in SCOPES.items(): need(report[key]==value, 'Unexpected native scope')
    need(report.get('unityVersion') == '6000.3.19f1', 'Wrong Unity version')
    need(report.get('status') in ('incomplete','dependency-verification-failed','observations-complete-not-gameplay-acceptance','cleanup-failed'), 'Unknown diagnostic status')
    need(isinstance(input_sha256, str) and SHA.fullmatch(input_sha256), 'Input hash invalid')
    check = report.get('dependencyCheck'); need(isinstance(check, dict), 'Missing native closure check')
    need(set(check)==CHECK_KEYS,'Unknown/missing closure fields')
    need(check.get('status') in ('not-started','checking-input','calling-production-snapshot','verified-native-closure','dependency-mismatch','dependency-verification-failed'), 'Unknown closure status')
    need(check.get('inputPath') == INPUT_PATH and check.get('inputSha256') == input_sha256, 'Wrong consumer input')
    boolean(check.get('passed')); text(check.get('snapshotError'), 16384, nullable=True)
    text(check.get('snapshotFailureCode'),128,nullable=True); text(check.get('snapshotFailurePath'),nullable=True)
    if check.get('snapshotFailureCode') or check.get('snapshotFailurePath'):
        need(check.get('snapshotFailureCode')=='MISSING_DEPENDENCY_BYTES_OR_META' and not check['passed']
             and check['status']=='dependency-verification-failed','Unknown or inconsistent snapshot failure code')
        relative(check['snapshotFailurePath'])
        need(check['snapshotFailurePath'].startswith(('Assets/','Packages/')),'Snapshot missing path outside asset/package roots')
    expected_rows = consumer_input['dependencies']
    expected = {dependency(row): row for row in expected_rows}
    need(len(expected_rows) == len(expected) == 796, 'Expected closure must contain exactly 796 unique rows')
    need(Counter(p['kind'] for p in expected_rows)=={'asset':772,'package':24},'Expected asset/package closure split')
    actual_rows = check.get('actualDependencies'); need(isinstance(actual_rows, list) and len(actual_rows) <= 4096, 'Unbounded native closure')
    actual = {dependency(row): row for row in actual_rows}
    need(len(actual) == len(actual_rows) == check.get('actualCount'), 'Duplicate/count-mismatched native dependencies')
    mismatches = check.get('mismatches'); need(isinstance(mismatches, list) and len(mismatches) <= 8192, 'Unbounded mismatch rows')
    seen = set()
    for row in mismatches:
        need(isinstance(row, dict) and set(row)=={'path','issue','expectedPresent','actualPresent','expected','actual'}, 'Invalid mismatch fields'); relative(row['path'])
        need(row['path'] not in seen, 'Duplicate mismatch path'); seen.add(row['path'])
        boolean(row['expectedPresent']); boolean(row['actualPresent'])
        need(row['expectedPresent'] == (row['path'] in expected) and row['actualPresent'] == (row['path'] in actual), 'Wrong mismatch presence')
        if row['expectedPresent']: dependency(row['expected']); need(row['expected'] == expected[row['path']], 'Wrong expected mismatch evidence')
        if row['actualPresent']: dependency(row['actual']); need(row['actual'] == actual[row['path']], 'Wrong actual mismatch evidence')
        issue = 'unexpected' if not row['expectedPresent'] else 'missing' if not row['actualPresent'] else 'changed'
        need(row['issue'] == issue, 'Wrong mismatch issue')
    differences = {p for p in expected.keys() | actual.keys() if expected.get(p) != actual.get(p)}
    if check.get('status') in ('verified-native-closure', 'dependency-mismatch'):
        need(seen == differences, 'Mismatch evidence omits or invents a path')
    closed = (check['passed'] and check.get('status') == 'verified-native-closure'
              and check.get('expectedCount') == 796 and actual == expected and not mismatches
              and not check.get('snapshotError'))
    need(not check['passed'] or closed, 'False native closure pass')
    samples = report.get('samples'); need(isinstance(samples, list) and len(samples) <= 48, 'Unbounded native samples')
    need(closed or not samples, 'Physics observations exist without the closure gate')
    for row in samples:
        need(isinstance(row, dict) and row.get('region') in (1,2,3), 'Invalid sample region')
        need(set(row)==SAMPLE_KEYS,'Unknown/missing sample fields')
        for key in ('purpose', 'approach', 'predicate'): text(row[key], 512)
        need(row['approach'] in allowed_approaches(row['region'],row['purpose']),'Unknown purpose or approach')
        predicate='JourneyActions.FindInteraction: feet-entry < 2.8; JourneyMotor.TryEnterDriver: native Linecast' if row['purpose']=='driver-prompt-and-return-geometry' else 'JourneyRaycast.CanReachPoint'
        need(row['predicate']==predicate,'Unknown interaction predicate')
        for key in ('foot','eye','target','hitPoint','hitNormal','driverLinecastPoint','driverLinecastNormal'): vector(row[key])
        for key in ('distance','limit','hitDistance','endpointDistance','savedVehicleDistance','driverEntryDistance','driverLinecastDistance','driverLinecastEndpointDistance'): number(row[key])
        for key in ('withinRange','productionCanReachPoint','hasFirstHit','acceptedSurfaceIsFirstHit','supported','standingCapsuleClear','driverDistancePromptPredicate','driverDistanceEnterPredicate','driverLinecastHasHit','driverLinecastAllowsGeometry'): boolean(row[key])
        if row['hasFirstHit']: surface(row['firstHit'])
        if row['supported']: surface(row['support'])
        if row['driverLinecastHasHit']: surface(row['driverLinecastHit'])
        if row['purpose'] != 'driver-prompt-and-return-geometry': surface(row['acceptedSurface'])
        blockers=row['standingBlockers']; need(isinstance(blockers,list) and len(blockers)<=2048, 'Unbounded standing blockers')
        for blocker in blockers: surface(blocker)
        need(row['standingCapsuleClear'] == (len(blockers)==0), 'Standing-clear flag contradicts evidence')
    for key in ('sourceUnchanged','copiesDeleted','setupRestored'): boolean(report[key])
    errors=report['cleanupErrors']; need(isinstance(errors,list) and len(errors)<=32, 'Unbounded cleanup errors')
    for error in errors: text(error,16384)
    pins=report['sourceFiles']; need(isinstance(pins,list) and len(pins)<=4096, 'Unbounded source pins')
    for pin in pins:
        need(isinstance(pin,dict) and set(pin)=={'path','sha256'},'Unknown source pin fields')
        relative(pin['path']); need(isinstance(pin['sha256'],str) and SHA.fullmatch(pin['sha256']), 'Invalid source pin')
    complete = report.get('status') == 'observations-complete-not-gameplay-acceptance'
    if complete:
        need(closed and len(samples)==48 and all(report[k] for k in ('sourceUnchanged','copiesDeleted','setupRestored')) and not errors, 'Incomplete diagnostic marked completed')
        counts=Counter((row['region'],row['purpose']) for row in samples)
        expected_counts={}
        for region in (1,2,3):
            for purpose in ('cabin-workbench','driver-prompt-and-return-geometry'): expected_counts[(region,purpose)]=3
            for supply in SUPPLIES[region]: expected_counts[(region,f'supply:region-{region}/optional/{supply}')]=3
            if region<=2: expected_counts[(region,'ram-salvage' if region==1 else 'coil-salvage')]=3
            if region>=2: expected_counts[(region,'power-connect-and-disconnect')]=3
        need(counts==expected_counts, 'Wrong interaction inventory')
        need(len({(r['region'],r['purpose'],r['approach']) for r in samples})==48, 'Duplicate approach observation')
    return {'nativeClosureMatched':closed,'diagnosticComplete':complete,'sampleCount':len(samples),
            'dependencyMismatchCount':len(mismatches),
            'interactionRayBlockedCount':sum(row['purpose']!='driver-prompt-and-return-geometry' and not row['productionCanReachPoint'] for row in samples),
            'driverLinecastBlockedCount':sum(row['purpose']=='driver-prompt-and-return-geometry' and not row['driverLinecastAllowsGeometry'] for row in samples) if complete else None,
            'gameplayAccepted':False,'scopeReusable':False}

def public_report(report, consumer_input, input_sha256, saved_scene_names=None):
    """Reconstruct a whitelisted public object; never copy native error text."""
    summary=verify_native_report(report,consumer_input,input_sha256)
    def error_digest(value):
        raw=(value or '').encode('utf-8')
        return {'present':bool(raw),'sha256':hashlib.sha256(raw).hexdigest() if raw else '', 'utf8Bytes':len(raw)}
    def clean_surface(value):
        if saved_scene_names is not None:
            parts=list(re.finditer(r'(.+?)\[([0-9]+)\](?:/|$)',value['hierarchy']))
            need(parts and parts[0].start()==0 and parts[-1].end()==len(value['hierarchy'])
                 and all(p.group(1) in saved_scene_names for p in parts), 'Collider hierarchy contains a non-scene node')
        return {key:value[key] for key in SURFACE_KEYS}
    public={'schema':'desert-rv-interaction-reachability-public/v1','nativeSchemaVersion':2,'summary':summary}
    for key in ('status','unityVersion','scope','driverScope','powerScope','sourceUnchanged','copiesDeleted','setupRestored'):
        public[key]=report[key]
    public['sourceFiles']=[{'path':p['path'],'sha256':p['sha256']} for p in report['sourceFiles']]
    check=report['dependencyCheck']
    public['dependencyCheck']={key:check[key] for key in ('status','inputPath','inputSha256','expectedCount','actualCount','passed')}
    public['dependencyCheck']['snapshotErrorDigest']=error_digest(check['snapshotError'])
    missing=check.get('snapshotFailurePath')
    public['dependencyCheck']['snapshotFailure']={
        'code':check['snapshotFailureCode'],'path':missing,
        'expected':next(({key:p[key] for key in DEPENDENCY_KEYS} for p in consumer_input['dependencies'] if p['path']==missing),None)
    } if missing else None
    public['dependencyCheck']['actualDependencies']=[{key:p[key] for key in DEPENDENCY_KEYS} for p in check['actualDependencies']]
    public['dependencyCheck']['mismatches']=[{
        'path':p['path'],'issue':p['issue'],'expectedPresent':p['expectedPresent'],'actualPresent':p['actualPresent'],
        'expected':{key:p['expected'][key] for key in DEPENDENCY_KEYS} if p['expectedPresent'] else None,
        'actual':{key:p['actual'][key] for key in DEPENDENCY_KEYS} if p['actualPresent'] else None} for p in check['mismatches']]
    public['cleanupErrorDigests']=[error_digest(error) for error in report['cleanupErrors']]
    public['samples']=[]
    surface_fields={'acceptedSurface','firstHit','support','driverLinecastHit','standingBlockers'}
    for row in report['samples']:
        clean={key:row[key] for key in SAMPLE_KEYS-surface_fields}
        for key,present in (('acceptedSurface',row['purpose']!='driver-prompt-and-return-geometry'),('firstHit',row['hasFirstHit']),('support',row['supported']),('driverLinecastHit',row['driverLinecastHasHit'])):
            clean[key]=clean_surface(row[key]) if present else None
        clean['standingBlockers']=[clean_surface(s) for s in row['standingBlockers']]
        public['samples'].append(clean)
    return public

def load_bounded(path, maximum=4*1024*1024):
    raw=path.read_bytes(); need(len(raw)<=maximum,'Native report exceeds limit')
    def unique(pairs):
        result={}
        for key,value in pairs:
            need(key not in result,'Duplicate JSON key'); result[key]=value
        return result
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON number')))
