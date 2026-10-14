#!/usr/bin/env python3
"""Separate 14-frame evidence from one exact PASS; never the 23/37/G3 gate."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import time
import xml.etree.ElementTree as ET
import g3_ci
import visual_candidate_ci as visual
import reflection_bake_ci as baked
import play_split_ci as split

require = visual.require
SCOPE = 'EXACT_PASSED_G3_CASE_14_FRAMES_NOT_23_FRAME_OR_SUITE_PASS'
FILES = tuple(visual.ORIGINAL_G3_FILES)
EXPORT = 'export-receipt.json'


def destination(root):
    return visual.outdir(root) / 'independent-g3-case-captures'


def regular(path, maximum):
    require(path.resolve() == path.absolute(), 'INDEPENDENT_FRAME_PATH_REJECTED')
    return visual.bounded.bounded_read(path, maximum)


def clear(root):
    folder = destination(root)
    require(folder.resolve() == folder.absolute(), 'INDEPENDENT_FRAME_DESTINATION_REJECTED')
    for name in (*FILES, EXPORT):
        p = folder / name
        if p.exists() or p.is_symlink():
            require(p.is_file() or p.is_symlink(), 'INDEPENDENT_FRAME_STALE_REJECTED')
            p.unlink()


def identity(root):
    ident = visual.identity(root)
    require(visual.HEX40.fullmatch(ident.get('sourceCommit', '')) and visual.HEX40.fullmatch(ident.get('reviewedCandidateCommit', '')), 'INDEPENDENT_FRAME_IDENTITY_REJECTED')
    for key, env in (('runId', 'GITHUB_RUN_ID'), ('runAttempt', 'GITHUB_RUN_ATTEMPT')):
        require(ident[key] == os.environ.get(env) and isinstance(ident[key], str) and ident[key].isascii() and ident[key].isdigit() and not ident[key].startswith('0'), 'INDEPENDENT_FRAME_RUN_REJECTED')
    return ident


def preparation(root, ident):
    path = visual.outdir(root) / 'original-g3-preparation.json'
    raw = regular(path, 8192); value = baked.load_receipt(raw)
    require(set(value) == {'schemaVersion','scope','sourceCommit','runId','runAttempt','preparedAtUtc','preparedAtNs','fixedFiles','status'}, 'INDEPENDENT_FRAME_PREPARATION_REJECTED')
    require(type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and value['scope'] == visual.SCOPE and value['status'] == 'FIXED_OUTPUTS_CLEARED_BEFORE_PLAY_NOT_A_PASS' and value['fixedFiles'] == list(FILES), 'INDEPENDENT_FRAME_PREPARATION_REJECTED')
    require(all(value[k] == ident[k] for k in ('sourceCommit','runId','runAttempt')), 'INDEPENDENT_FRAME_PREPARATION_IDENTITY_REJECTED')
    ns = value['preparedAtNs']
    require(type(ns) is int and 0 < ns <= time.time_ns() and isinstance(value['preparedAtUtc'],str) and len(value['preparedAtUtc']) <= 40, 'INDEPENDENT_FRAME_PREPARATION_CLOCK_REJECTED')
    stamp = datetime.fromisoformat(value['preparedAtUtc'].replace('Z','+00:00'))
    require(stamp.tzinfo is not None and stamp.utcoffset().total_seconds() == 0 and abs(stamp.timestamp()-ns/1e9) < 1, 'INDEPENDENT_FRAME_PREPARATION_CLOCK_REJECTED')
    return ns, hashlib.sha256(raw).hexdigest()


def exact_case(root, ident, prepared_ns):
    path = split.paths(root, 'core')[0] / 'playmode-results.xml'
    require(path.stat().st_mtime_ns >= prepared_ns, 'INDEPENDENT_FRAME_STALE_XML')
    checked = split.inspect(root, 'core', preserve=False)
    target = [c for c in checked['cases'] if c['fullname'] == visual.ORIGINAL_G3_CASE]
    require(len(target) == 1 and target[0]['result'] == 'Passed', 'INDEPENDENT_FRAME_TARGET_NOT_PASSED')
    tree = ET.fromstring(regular(path, 10*1024*1024))
    case = next(c for c in tree.iter('test-case') if c.get('fullname') == visual.ORIGINAL_G3_CASE)
    require(case.find('failure') is None, 'INDEPENDENT_FRAME_TARGET_NOT_PASSED')
    native_path = visual.outdir(root) / 'safe-regression-play-core.json'
    require(native_path.stat().st_mtime_ns >= prepared_ns, 'INDEPENDENT_FRAME_STALE_NATIVE')
    return checked['counts'], checked['rawXmlSha256'], checked['nativeReceiptSha256']


def export(root):
    clear(root); ident = identity(root); ns, prep_hash = preparation(root,ident)
    counts, xml_hash, native_hash = exact_case(root,ident,ns)
    source = root / visual.TASK / 'artifacts/g3-play/captures'
    originals = {}
    for name in FILES:
        path = source/name; originals[name] = regular(path,128*1024 if name == 'render-receipt.json' else 4*1024*1024)
        require(path.stat().st_mtime_ns >= ns, 'INDEPENDENT_FRAME_STALE_ORIGINAL')
    # Strict duplicate-key parse before preserving the original JSON bytes.
    receipt = baked.load_receipt(originals['render-receipt.json'])
    screened = json.dumps(receipt).encode().replace(b'&',b'&amp;').replace(b'<',b'&lt;').replace(b'>',b'&gt;')
    visual.bounded.require_safe_xml(b'<test-run><output>'+screened+b'</output></test-run>')
    checked = g3_ci.inspect_captures(source,ident,list(visual.ORIGINAL_G3_FRAMES))
    require(checked == receipt, 'INDEPENDENT_FRAME_RECEIPT_CHANGED')
    for frame in receipt['frames']:
        require(hashlib.sha256(originals[frame['file']]).hexdigest() == frame['sha256'] and len(originals[frame['file']]) == frame['bytes'], 'INDEPENDENT_FRAME_ORIGINAL_CHANGED')
    proof = dict(schemaVersion=2,scope=SCOPE,sourceCommit=ident['sourceCommit'],reviewedCandidateCommit=ident['reviewedCandidateCommit'],runId=ident['runId'],runAttempt=ident['runAttempt'],originalCase=visual.ORIGINAL_G3_CASE,originalCaseResult='Passed',frameOwningShard='core',owningShardCounts=counts,owningShardAllPassed=counts['failed']==0,completePlayRegression='NOT_EVALUATED_BY_THIS_EXPORT',rawXmlSha256=xml_hash,nativeReceiptSha256=native_hash,preparationReceiptSha256=prep_hash,legacyReceiptSha256=hashlib.sha256(originals['render-receipt.json']).hexdigest(),legacyReceiptRunAttempt='NOT_PRESENT_IN_LEGACY_SCHEMA',attemptBinding='FIXED_OUTPUTS_CLEARED_BEFORE_ATTEMPT_AND_RECREATED_AFTER_PREPARATION',mainDayFrames=list(visual.ORIGINAL_G3_FRAMES[:-1]),separateProtectedFixtureFrame='challenge-protected',visual23FrameGate='NOT_EVALUATED_BY_THIS_EXPORT',g3Gate='NOT_EVALUATED',visualReview='PENDING',deviceQa='NOT_RUN')
    folder = destination(root); folder.mkdir(parents=True,exist_ok=True)
    try:
        for name in FILES:(folder/name).write_bytes(originals[name])
        visual.write(folder/EXPORT,proof)
    except BaseException:
        clear(root);raise
    print('INDEPENDENT_G3_CASE_FRAMES_EXPORTED_NOT_23_FRAME_OR_SUITE_PASS')


def main():
    try:export(Path(__file__).resolve().parents[3]);return 0
    except BaseException:print('INDEPENDENT_G3_CASE_FRAMES_REJECTED');return 1


if __name__ == '__main__':raise SystemExit(main())
