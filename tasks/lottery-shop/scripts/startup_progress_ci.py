#!/usr/bin/env python3
"""Bounded startup observations only; original native/NUnit gates stay authoritative."""
import json
import os
import re
from datetime import datetime
from pathlib import Path
import visual_candidate_ci as visual
import reflection_bake_ci as reflection

NAME='startup-progress.json'
LIMIT=32768
MAX_EVENTS=64
SCOPE='CAPTURE_STARTUP_DIAGNOSTIC_NOT_TEST_PASS'
STATUS='OBSERVATIONS_ONLY_NOT_TEST_PASS'
ROOT_FIELDS=frozenset(['schemaVersion', 'scope', 'status', 'sourceCommit', 'runId', 'runAttempt', 'startedUtc', 'diagnosticWriteFailed', 'eventLimitReached', 'errorCount', 'assertCount', 'exceptionCount', 'utfErrorCount', 'events'])
EVENT_FIELDS=frozenset(['stage', 'code', 'exceptionKind', 'elapsedMs', 'errorCount', 'assertCount', 'exceptionCount', 'utfErrorCount', 'isPlaying', 'isPlayingOrWillChangePlaymode', 'isCompiling', 'isUpdating', 'origin'])
STAGES=frozenset(['ARMED', 'PREBUILD_RETURNED', 'ERROR_LOG', 'UTF_ERROR', 'UTF_RUN_STARTED', 'UTF_RUN_FINISHED', 'BEFORE_RELOAD', 'DOMAIN_RESTORED', 'EXITING_EDIT_MODE', 'ENTERED_PLAY_MODE', 'EXITING_PLAY_MODE', 'ENTERED_EDIT_MODE', 'QUITTING'])
CODES=frozenset(['NONE', 'UNCLASSIFIED', 'SCENE_UNTITLED', 'SCENE_ACTIVE', 'REFLECTION_RECIPE', 'REFLECTION_LAYOUT', 'SHADER_COMPILE', 'SCRIPT_COMPILE', 'PREBUILD_SETUP', 'ASSEMBLY_RELOAD', 'TEST_RUNNER_CONTEXT', 'TEST_RUNNER_CANCELLED', 'TEST_RUNNER_UNEXPECTED', 'LIFECYCLE_WRITE'])
KINDS=frozenset(['NONE', 'INVALID_OPERATION', 'ARGUMENT', 'NULL_REFERENCE', 'IO', 'UNITY', 'AGGREGATE', 'OTHER'])
ORIGINS=frozenset(['NONE', 'PREBUILD_SETUP', 'GENERATE_CONTEXT', 'PREPARE_PLAY_MODE', 'ENTER_PLAY_MODE', 'TEST_PROGRESS', 'CALLBACKS', 'TASK_RUNNER', 'ASSET_DATABASE', 'REFLECTION_BAKER', 'UNKNOWN'])
COUNTERS=('errorCount','assertCount','exceptionCount','utfErrorCount')
FLAGS=('isPlaying','isPlayingOrWillChangePlaymode','isCompiling','isUpdating')
require=visual.require


def integer(value,low,high):return type(value) is int and low<=value<=high


def validate_startup(value,ident):
    require(type(value) is dict and set(value)==ROOT_FIELDS,'STARTUP_FIELDS_REJECTED')
    require(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['scope']==SCOPE and value['status']==STATUS,'STARTUP_SCHEMA_REJECTED')
    for key in ('sourceCommit','runId','runAttempt'):require(value[key]==ident[key],'STARTUP_IDENTITY_REJECTED')
    require(type(value['startedUtc']) is str and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,7})?Z',value['startedUtc']) is not None,'STARTUP_UTC_REJECTED')
    datetime.fromisoformat(value['startedUtc'].replace('Z','+00:00'))
    require(all(type(value[k]) is bool for k in ('diagnosticWriteFailed','eventLimitReached')) and all(integer(value[k],0,1000000) for k in COUNTERS),'STARTUP_COUNTERS_REJECTED')
    events=value['events'];require(type(events) is list and 1<=len(events)<=MAX_EVENTS,'STARTUP_EVENTS_REJECTED')
    last_time=0;last_counts={k:0 for k in COUNTERS}
    for event in events:
        require(type(event) is dict and set(event)==EVENT_FIELDS,'STARTUP_EVENT_FIELDS_REJECTED')
        require(type(event['stage']) is str and event['stage'] in STAGES and type(event['code']) is str and event['code'] in CODES and type(event['exceptionKind']) is str and event['exceptionKind'] in KINDS and type(event['origin']) is str and event['origin'] in ORIGINS,'STARTUP_ENUM_REJECTED')
        require(integer(event['elapsedMs'],last_time,3600000) and all(integer(event[k],last_counts[k],value[k]) for k in COUNTERS),'STARTUP_EVENT_CLOCK_OR_COUNTER_REJECTED')
        require(all(type(event[k]) is bool for k in FLAGS),'STARTUP_EVENT_FLAGS_REJECTED')
        last_time=event['elapsedMs'];last_counts={k:event[k] for k in COUNTERS}
    require(events[0]['stage']=='ARMED','STARTUP_ARMED_MISSING')
    # Duplicate categories may increment root counters without a new event.
    # Each event remains bounded above by the observed root total.
    return value


def export_startup(root):
    dest=visual.outdir(root)/NAME
    require(dest.parent.resolve()==dest.parent.absolute(),'STARTUP_PATH_REJECTED')
    if dest.exists() or dest.is_symlink():
        require(dest.is_file() or dest.is_symlink(),'STARTUP_STALE_REJECTED');dest.unlink()
    source=root/visual.TASK/'artifacts/visual-candidate'/NAME
    require(source.resolve()==source.absolute(),'STARTUP_PATH_REJECTED')
    ident=visual.identity(root)
    require(visual.HEX40.fullmatch(ident.get('sourceCommit','')) and visual.HEX40.fullmatch(ident.get('reviewedCandidateCommit','')) and all(type(ident.get(k)) is str and re.fullmatch(r'[1-9][0-9]*',ident[k]) for k in ('runId','runAttempt')),'STARTUP_IDENTITY_REJECTED')
    require(ident['runId']==os.environ.get('GITHUB_RUN_ID') and ident['runAttempt']==os.environ.get('GITHUB_RUN_ATTEMPT'),'STARTUP_RUN_REJECTED')
    raw=visual.bounded.bounded_read(source,LIMIT)
    receipt=validate_startup(reflection.load_receipt(raw),ident)
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    print('CAPTURE_STARTUP_OBSERVATIONS_PRESERVED_NOT_TEST_PASS')
    require(not receipt['diagnosticWriteFailed'] and not receipt['eventLimitReached'],'STARTUP_OBSERVATIONS_INCOMPLETE')


def main():
    try:export_startup(Path(__file__).resolve().parents[3]);return 0
    except BaseException:print('CAPTURE_STARTUP_DIAGNOSTIC_REJECTED');return 1


if __name__=='__main__':raise SystemExit(main())
