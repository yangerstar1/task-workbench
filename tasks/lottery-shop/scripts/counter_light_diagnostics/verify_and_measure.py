#!/usr/bin/env python3
"""Read-only diagnostics validation and code-value statistics; never art approval.
Uses original PNG files, writes JSON only when --output is explicitly given.
Does not launch Unity, change assets, copy frames, or replace existing gate tools.
Image dependencies load only inside image/matrix work; metadata-only prepare is stdlib.
"""
import argparse
import copy
import math
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / 'diagnostic_plan.json').read_text())
CASES = PLAN['cases']
NAMES = ['Soft window daylight', 'Warm counter pendant', 'Table reading pendant', 'Shelf ambient fill', 'Counter board wash']
EXPECTED = [.6, 1.15, 1.6, .55, .06]
CASE = 'Lottery.G3.VisualCandidate.Tests.VisualCandidateCaptureTests.ScenarioStateCaptureRetainsTwentyThreeViewsFromRealTransactionsV2'
FRAMES = ['entry-whole-shop', 'table-empty', 'number-half', 'number-half-20x9', 'phone-room-standing', 'phone-table-before',
          'phone-contacts', 'phone-mom-pending', 'phone-mom-claimed', 'phone-table-return', 'challenge-two-safe-three-tools',
          'shelf-before-open', 'shelf-after-open', 'challenge-returned-from-shelf', 'closing-day-table',
          'exterior-day-far-front', 'exterior-day-near-window-left-oblique', 'exterior-day-near-door-right-oblique',
          'night-table', 'exterior-night-far-front', 'exterior-night-near-window-left-oblique', 'exterior-night-near-door-right-oblique', 'night-bill']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def strict_json(text):
    def pairs(items):
        value = {}
        for k,v in items:
            require(k not in value, 'Duplicate JSON key')
            value[k] = v
        return value
    return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def load(path, maximum=2097152):
    require(path.is_file() and not path.is_symlink(), 'Missing or symlink JSON: ' + path.name)
    require(path.stat().st_size <= maximum, 'Oversized JSON')
    return strict_json(path.read_text())


def png(path, digest=None, count=None, size=(1280, 720)):
    import numpy as np
    from PIL import Image
    require(path.is_file() and not path.is_symlink(), 'Missing or symlink PNG: ' + path.name)
    b = path.read_bytes()
    require(10000 < len(b) <= 8*1024*1024, 'PNG byte bound')
    require(digest is None or sha(b) == digest, 'PNG hash mismatch: ' + path.name)
    require(count is None or len(b) == count, 'PNG length mismatch: ' + path.name)
    with Image.open(path) as im:
        require(im.format == 'PNG' and im.size == size, 'PNG format/geometry mismatch')
        return np.array(im.convert('RGB'), dtype=np.float64)


def near(a, b):
    return abs(a-b) <= 1e-6


def checked_payload(text, digest, observation):
    require(type(text) is str and len(text.encode('utf-8')) <= 32768, 'Control payload missing/oversized')
    require(sha(text.encode('utf-8')) == digest, 'Control hash is not bound to payload')
    value = strict_json(text)
    require(value == observation, 'Control payload differs from structured observation')
    return value


def validate_camera(c):
    import numpy as np
    require(type(c) is dict, 'Camera missing')
    for k in ['instanceId','targetId','expectedTargetId','urpInstanceId','volumeTriggerId','width','height','antiAliasing','cullingMask']:
        require(type(c.get(k)) is int, 'Camera integer observation missing: '+k)
    require(c['targetId'] != 0 and c['targetId'] == c['expectedTargetId'] and c['urpInstanceId'] != 0, 'Actual camera target/URP binding missing')
    require((c['width'],c['height'],c.get('format')) == (1280,720,'ARGB32'), 'Diagnostic camera target drift')
    require(c.get('orthographic') is False and c.get('targetCreated') is True and c.get('enabled') is True, 'Camera mode/target mismatch')
    require(type(c.get('urpStackIds')) is list and all(type(x) is int for x in c['urpStackIds']), 'URP stack missing')
    require(re.fullmatch('[0-9a-f]{64}',c.get('urpSerializedSha256','')) is not None, 'URP snapshot digest missing')
    for key, names in [('position',{'x','y','z'}),('rotation',{'x','y','z','w'}),('background',{'r','g','b','a'})]:
        require(type(c.get(key)) is dict and set(c[key]) == names and all(type(x) in (int,float) and math.isfinite(x) for x in c[key].values()), 'Camera vector missing: '+key)
    require(abs(sum(x*x for x in c['rotation'].values())-1) < .001, 'Camera rotation invalid')
    for key in ('projection','worldToCamera'):
        require(type(c.get(key)) is list and len(c[key]) == 16 and all(type(x) in (int,float) and math.isfinite(x) for x in c[key]), 'Camera matrix missing: '+key)
        require(abs(float(np.linalg.det(np.array(c[key]).reshape(4,4)))) > 1e-10, 'Camera matrix singular')
    require(type(c.get('viewport')) is list and len(c['viewport']) == 4 and all(type(x) in (int,float) and math.isfinite(x) for x in c['viewport']), 'Camera viewport missing')
    require(all(type(c.get(k)) is bool for k in ('allowHDR','allowMSAA','sRGB')) and c.get('clearFlags') in ('Color','SolidColor'), 'Camera render configuration missing')
    require(c['viewport'][2] > 0 and c['viewport'][3] > 0, 'Camera viewport invalid')
    for key in ('fov','aspect','near','far'):
        require(type(c.get(key)) in (int,float) and math.isfinite(c[key]), 'Camera scalar missing: '+key)
    require(0 < c['fov'] < 180 and 0 < c['near'] < c['far'] and c['aspect'] > 0, 'Camera projection invalid')


MATERIAL_KEYS = {'oakMaterialId','oakShader','oakKeywords','oakSmoothness','oakNormalStrength','oakSpecularHighlights',
    'oakBaseMapId','oakBaseMapName','oakBaseColor','oakBaseScale','oakBaseOffset','oakBumpMapId','oakPackedMapId','oakEmissionMapId',
    'oakMetallic','oakEmissionColor','oakCull','oakSurface','oakZWrite','oakSrcBlend','oakDstBlend','oakRenderQueue','oakEnableInstancing','oakDoubleSidedGI','oakGIFlags'}
CONTROL_KEYS = MATERIAL_KEYS | {'lightNames','lightIntensities','lightColors','lightPositions','lightRotations','lightRanges',
    'lightSpotAngles','lightInnerSpotAngles','lightShadows','lightEnabled','lightCullingMasks','probeIntensity','reflectionIntensity','probeTextureId','probeTextureName','ambientSH'}


def validate_controls_shape(c):
    require(type(c) is dict and set(c)==CONTROL_KEYS, 'Missing/unexpected controls')
    finite=lambda x:type(x) in (int,float) and math.isfinite(x)
    vector=lambda x,keys:type(x) is dict and set(x)==set(keys) and all(finite(v) for v in x.values())
    for key,keys in [('lightColors','rgba'),('lightPositions','xyz'),('lightRotations','xyzw')]:
        require(type(c[key]) is list and len(c[key])==5 and all(vector(x,keys) for x in c[key]), 'Light vector observation missing: '+key)
    for key in ('lightIntensities','lightRanges','lightSpotAngles','lightInnerSpotAngles'):
        require(type(c[key]) is list and len(c[key])==5 and all(finite(x) for x in c[key]), 'Light scalar observation missing')
    require(c['lightEnabled']==[True]*5 and all(type(x) is bool for x in c['lightEnabled']), 'Light enabled observation invalid')
    require(c['lightShadows']==['Soft','None','Soft','None','None'], 'Table-key light shadows drift')
    require(type(c['lightCullingMasks']) is list and len(c['lightCullingMasks'])==5 and all(type(x) is int for x in c['lightCullingMasks']), 'Light masks missing')
    require(type(c['ambientSH']) is list and len(c['ambientSH'])==27 and all(finite(x) for x in c['ambientSH']), 'SH observations missing')
    for key,keys in [('oakBaseColor','rgba'),('oakEmissionColor','rgba'),('oakBaseScale','xy'),('oakBaseOffset','xy')]:
        require(vector(c[key],keys), 'Material vector observation missing: '+key)
    for key in ('probeIntensity','reflectionIntensity','oakSmoothness','oakNormalStrength','oakSpecularHighlights','oakMetallic','oakCull','oakSurface','oakZWrite','oakSrcBlend','oakDstBlend'):
        require(finite(c[key]),'Material/control scalar missing: '+key)
    require(type(c['oakMaterialId']) is int and c['oakMaterialId']!=0 and type(c['oakRenderQueue']) is int,'Material identity/queue missing')
    require(type(c['oakEnableInstancing']) is bool and type(c['oakDoubleSidedGI']) is bool,'Material boolean observation missing')
    require(type(c['oakKeywords']) is list and all(type(x) is str for x in c['oakKeywords']) and c['oakKeywords']==sorted(set(c['oakKeywords'])),'Material keywords invalid')
    for key in ('oakShader','oakBaseMapId','oakBaseMapName','oakBumpMapId','oakPackedMapId','oakEmissionMapId','oakGIFlags','probeTextureId','probeTextureName'):
        require(type(c[key]) is str and len(c[key])>0,'Material/reference observation missing: '+key)


def material_expected(initial, label, actual_id):
    expected = {k:copy.deepcopy(initial[k]) for k in MATERIAL_KEYS}
    if label.startswith('oak-'):
        require(type(actual_id) is int and actual_id != 0 and actual_id != initial['oakMaterialId'], 'Material clone identity missing')
        expected['oakMaterialId'] = actual_id
    if label == 'oak-specular-highlights-off':
        expected['oakSpecularHighlights']=0
        expected['oakKeywords']=sorted(set(initial['oakKeywords']) | {'_SPECULARHIGHLIGHTS_OFF'})
    elif label == 'oak-normal-flat': expected['oakNormalStrength']=0
    elif label == 'oak-roughness-one': expected['oakSmoothness']=0
    elif label in ('oak-texture-only','oak-target-mask'):
        expected.update(oakShader='Universal Render Pipeline/Unlit',oakKeywords=[],oakSmoothness=-1,oakNormalStrength=-1,oakSpecularHighlights=-1,
            oakBumpMapId='ABSENT',oakPackedMapId='ABSENT',oakEmissionMapId='ABSENT',oakMetallic=-1,
            oakEmissionColor={'r':0,'g':0,'b':0,'a':0},oakSurface=0,oakZWrite=1,oakSrcBlend=1,oakDstBlend=0,oakRenderQueue=2000,
            oakEnableInstancing=False,oakDoubleSidedGI=False,oakGIFlags='None')
        if label == 'oak-target-mask':
            expected.update(oakBaseMapId='null',oakBaseMapName='null',oakBaseColor={'r':1,'g':0,'b':1,'a':1})
    return expected


def validate_receipt(d, normal_sha, commit):
    require(d.get('schemaVersion') == 2 and d.get('scope') == 'DIAGNOSTIC_COUNTER_LIGHT_NOT_ART_APPROVAL_NOT_G3_PASS', 'Wrong scope/schema')
    require(d.get('status') == 'COMPLETE_DIAGNOSTIC_RESTORED' and d.get('complete') is True and d.get('restored') is True and d.get('propertiesRestored') is True and d.get('pixelRestoreProof') == 'VERIFIED_EXACT_PNG', 'Diagnostic not complete/restored')
    require(d.get('diagnosticOptIn') is True and d.get('faultRequest','') == '', 'Opt-in missing or fault-injected capture')
    require(d.get('failureCode','') in ('',None), 'Complete receipt has failureCode')
    require(type(d.get('elapsedMs')) is int and 0 < d['elapsedMs'] < 180000, 'Diagnostic budget missing/expired')
    require(type(d.get('frameCount')) is int and d['frameCount'] >= 0 and d.get('graphicsDeviceType') == 'OpenGLCore', 'Frame/device observations missing or invalid')
    require(d.get('sourceCommit') == commit and re.fullmatch('[0-9a-f]{40}',commit), 'Source identity mismatch')
    require(d.get('baselineSourceFreeze') == PLAN['frozenCommit'], 'Frozen baseline identity mismatch')
    for field in ('expectedNormalPngSha256','baselineBeforeSha256','baselineAfterSha256'):
        require(d.get(field) == normal_sha, 'Baseline equality missing: '+field)
    for part in ('state','disk','scene','material'):
        before,after = d.get(part+'BeforeSha256'),d.get(part+'AfterSha256')
        require(type(before) is str and re.fullmatch('[0-9a-f]{64}',before) and before == after, 'Restoration digest mismatch: '+part)
    require(d.get('ownedMaterialCountAfter') == 0 and d.get('ownedTargetCountAfter') == 0, 'Owned resource leak')
    require(d.get('colorSpace') == 'Gamma' and d.get('unityVersion') == '6000.3.19f1', 'Runtime identity drift')
    validate_camera(d.get('camera'))
    initial = checked_payload(d.get('initialControlsJson'),d.get('initialControlsSha256'),d.get('initialControls'))
    validate_controls_shape(initial)
    require(initial['lightNames'] == NAMES and len(initial['lightIntensities']) == 5 and all(near(a,b) for a,b in zip(initial['lightIntensities'],EXPECTED)), 'Initial light values drift')
    require(near(initial['probeIntensity'],.85) and initial['reflectionIntensity'] == 1 and len(initial['ambientSH']) == 27, 'Initial indirect values drift')
    require(initial['oakShader'] == 'Universal Render Pipeline/Lit' and initial['oakKeywords'] == sorted(initial['oakKeywords']), 'Initial Lit shader/keywords invalid')
    require(d.get('oakMaterialCoverage') == 'ALL_MERGED_WARM_OAK_GEOMETRY_NOT_FASCIA_ONLY', 'Target coverage not disclosed')
    require([x['id'] for x in d['cases']] == CASES, 'Case identity/order drift')
    zero={'pendant-zero':[1],'boardwash-zero':[4],'counter-pair-zero':[1,4],'daylight-zero':[0],'reading-zero':[2],'shelf-zero':[3],
          'all-direct-zero':list(range(5)),'counter-and-reflection-controls-zero':[1,4]}
    probe_zero={'probe-intensity-zero','reflection-controls-zero','counter-and-reflection-controls-zero'}
    global_zero={'global-reflection-zero','reflection-controls-zero','counter-and-reflection-controls-zero'}
    for row in d['cases']:
        label=row['id']; controls=row.get('controls')
        require(row.get('captured') is True and row.get('propertiesRestored') is True and row.get('restored') is True and row.get('restoredPngSha256') == normal_sha, 'Case restoration/capture missing: '+label)
        require(row.get('file') == filename(label), 'Unsafe or wrong case filename')
        require(row.get('controlsStable') is True, 'Controls not stable')
        checked_payload(row.get('controlsBeforeJson'),row.get('controlsBeforeSha256'),controls)
        checked_payload(row.get('controlsAfterJson'),row.get('controlsAfterSha256'),controls)
        require(row['controlsBeforeJson'] == row['controlsAfterJson'], 'Controls changed during render')
        validate_controls_shape(controls)
        expected=copy.deepcopy(initial)
        expected['lightIntensities']=[0 if i in zero.get(label,[]) else x for i,x in enumerate(initial['lightIntensities'])]
        expected['probeIntensity']=0 if label in probe_zero else initial['probeIntensity']
        expected['reflectionIntensity']=0 if label in global_zero else initial['reflectionIntensity']
        expected['ambientSH']=[0]*27 if label=='ambient-sh-zero' else initial['ambientSH']
        expected.update(material_expected(initial,label,controls.get('oakMaterialId')))
        require(controls == expected, 'Experiment contains non-allowlisted control/material mutation: '+label)


def filename(label):
    return 'DIAGNOSTIC__phone-mom-pending__' + label + '.png'


def stats(a):
    import numpy as np
    # Gamma/LDR image code values, intentionally NOT a radiometric light-energy estimate.
    v = a.reshape(-1, 3)
    y = v @ np.array([.2126, .7152, .0722])
    return {'pixels':len(v), 'meanRGBCode':v.mean(axis=0).tolist(), 'p95RGBCode':np.percentile(v,95,axis=0).tolist(),
            'p99RGBCode':np.percentile(v,99,axis=0).tolist(), 'anyChannelAtLeast250Fraction':float((v.max(axis=1)>=250).mean()),
            'allChannelsAtLeast250Fraction':float((v.min(axis=1)>=250).mean()), 'yellowCodeIndexMean':float(((v[:,0]+v[:,1])/2-v[:,2]).mean()),
            'weightedCodeStddev':float(y.std())}


def measures(base, cases):
    import numpy as np
    result = {}
    for key,(x0,y0,x1,y1) in PLAN['rois'].items():
        b = base[y0:y1,x0:x1]; by_case = {}
        for label,img in cases.items():
            roi = img[y0:y1,x0:x1]; delta = roi-b
            by_case[label] = {'stats':stats(roi), 'meanSignedRGBCodeDelta':delta.mean(axis=(0,1)).tolist(),
                             'meanAbsoluteRGBCodeDelta':float(np.abs(delta).mean()), 'maxAbsoluteRGBCodeDelta':float(np.abs(delta).max())}
        result[key] = {'rectangle':[x0,y0,x1,y1], 'baseline':stats(b), 'cases':by_case}
    mask = cases.get('oak-target-mask')
    if mask is not None:
        hit = (mask[:,:,0] >= 250) & (mask[:,:,1] <= 5) & (mask[:,:,2] >= 250)
        coverage = {name:float(hit[y0:y1,x0:x1].mean()) for name,(x0,y0,x1,y1) in PLAN['rois'].items()}
        result['oakMaskCoverage'] = coverage
        result['materialInterpretationTargetConfirmed'] = coverage['fascia_lit'] >= .95 and coverage['phone_screen_control'] < .001 and coverage['green_wall_control'] < .001
    return result


def _validate_increment(diag, normal, xml, commit):
    d = load(diag/'diagnostic-receipt.json')
    n = load(normal/'capture-receipt.json', 2*1024*1024)
    require(n.get('complete') is True and n.get('sourceCommit') == commit, 'Normal receipt incomplete or mismatched source')
    require([f['stage'] for f in n['frames']] == FRAMES, 'Original exact 23-frame sequence changed')
    require(str(n['runId']) == str(d['runId']) and str(n['runAttempt']) == str(d['runAttempt']), 'Run/attempt pairing mismatch')
    for f in n['frames']:
        require(f['file'] == f['stage']+'.png', 'Unsafe normal file name')
        png(normal/f['file'], f['sha256'], f['bytes'], size=(f['width'],f['height']))
    pending = next(f for f in n['frames'] if f['stage']=='phone-mom-pending')
    validate_receipt(d, pending['sha256'], commit)
    require(d['camera']['position'] == pending['cameraPosition'] and d['camera']['fov'] == pending['cameraFov'], 'Diagnostic camera differs from normal phone camera')
    require(xml.stat().st_size <= 8*1024*1024 and not xml.is_symlink(), 'XML bound/symlink')
    tests = [t for t in ET.parse(xml).getroot().iter('test-case') if t.attrib.get('fullname') == CASE]
    require(len(tests) == 1 and tests[0].attrib.get('result') == 'Passed', 'Matching native case not passed')
    expected_files = {filename(x) for x in CASES+['baseline-before','baseline-after']}
    require({p.name for p in diag.glob('*.png')} == expected_files, 'Diagnostic PNG set incomplete/unexpected')
    base = png(normal/'phone-mom-pending.png', pending['sha256'], pending['bytes'])
    for label in ('baseline-before','baseline-after'):
        png(diag/filename(label), pending['sha256'])
    images = {r['id']:png(diag/r['file'],r['sha256'],r['bytes']) for r in d['cases']}
    return {'scope':'DIAGNOSTIC_ARTIFACT_INTEGRITY_AND_DESCRIPTIVE_PIXELS_NOT_ART_APPROVAL', 'diagnosticIncrementConsistent':True,
            'existingNormalValidatorStillRequired':True, 'sourceCommit':commit, 'measurements':measures(base,images)}


def validate_native(*args, **kwargs):
    raise ValueError('MISSING_BOUND_UPSTREAM_GATE_AND_EXTERNAL_ARTIFACT_PROVENANCE')


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='mode', required=True)
    b = sub.add_parser('baseline'); b.add_argument('png',type=Path); b.add_argument('--sha256', required=True); b.add_argument('--output',type=Path)
    v = sub.add_parser('native'); v.add_argument('--diagnostic',type=Path,required=True); v.add_argument('--normal',type=Path,required=True)
    v.add_argument('--xml',type=Path,required=True); v.add_argument('--source-commit',required=True); v.add_argument('--output',type=Path)
    a = p.parse_args()
    if a.mode == 'baseline':
        img = png(a.png,a.sha256)
        result = {'scope':'EXISTING_RUN24_BASELINE_DESCRIPTIVE_PIXELS_ONLY', 'newNativeExperimentRun':False, 'sha256':a.sha256, 'measurements':measures(img,{})}
    else:
        raise ValueError('Loose native input rejected: use compose_evidence.py CI or anchored postdownload entrypoint')
    text = json.dumps(result,indent=2)+'\n'
    if a.output: a.output.write_text(text)
    else: print(text,end='')

if __name__ == '__main__': main()
