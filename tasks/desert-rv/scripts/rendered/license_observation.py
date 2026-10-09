#!/usr/bin/env python3
"""Ordered fixed licensing facts from Editor/stdout text; no secrets or license-file reads."""
import re
MAX_EVENTS=8
# Editor messages and client process exits are different namespaces. Never map one as the other.
MESSAGE_CODES={10,200,1500}
CLIENT_EXIT_CODES=set(range(22))|{1000}
KINDS={
 'SIGNATURE_ERROR':'ERROR','IPC_CONNECT_ATTEMPT':'PROGRESS','IPC_CONNECTED':'SUCCESS','IPC_HANDSHAKE_SUCCEEDED':'SUCCESS','IPC_HANDSHAKE_FAILED':'ERROR',
 'TOKEN_MISSING':'ERROR','TOKEN_UPDATED':'SUCCESS','ULF_MISSING':'ERROR','LICENSE_FILE_MISSING':'ERROR','ENTITLEMENT_MISSING':'ERROR','ENTITLEMENTS_RESOLVED':'SUCCESS',
 'LICENSE_UPDATED':'SUCCESS','LICENSE_ACTIVATED':'SUCCESS','LICENSE_NOT_ACTIVE':'ERROR','LICENSE_VALIDATION_FAILED':'ERROR','REQUEST_SUCCEEDED':'SUCCESS','REQUEST_TIMEOUT':'ERROR',
 'CLIENT_ERROR':'ERROR','CLIENT_EXIT_OK':'SUCCESS','CLIENT_EXIT_ERROR':'ERROR','WAIT_CLIENT':'WAIT','WAIT_IPC':'WAIT','WAIT_LICENSE':'WAIT','WAIT_ENTITLEMENT':'WAIT','WAIT_HUB':'WAIT'}
STATES={'NONE_OBSERVED','PROGRESS_ONLY','ERROR_ONLY','SUCCESS_ONLY','ERROR_THEN_SUCCESS','SUCCESS_THEN_ERROR'}
NAMESPACES={'NONE','EDITOR_MESSAGE','CLIENT_EXIT'}
WAITS={'NONE','WAIT_CLIENT','WAIT_IPC','WAIT_LICENSE','WAIT_ENTITLEMENT','WAIT_HUB'}

def event(line):
    low=line.lower()
    licensing=bool(re.search(r'\[(?:licensing(?:::[a-z]+)?|licensingclient)\]',low))
    standalone=bool(re.search(r'no valid (?:unity editor )?license|license (?:file )?(?:not found|does not exist)',low))
    if not licensing and not standalone:return None
    kind=None
    # Explicit success status takes priority over misleading legacy "Error: Code 200" prefix.
    if 'status: licenses updated' in low or 'successfully updated the license' in low:kind='LICENSE_UPDATED'
    elif re.search(r'successfully activated.*(?:license|entitlement)',low):kind='LICENSE_ACTIVATED'
    elif 'successfully resolved entitlements' in low:kind='ENTITLEMENTS_RESOLVED'
    elif 'successfully updated the access token' in low:kind='TOKEN_UPDATED'
    elif 'successfully processed license management request' in low:kind='REQUEST_SUCCEEDED'
    elif 'successfully connected' in low and ('licensingclient' in low or 'licensing client' in low or 'license notification' in low):kind='IPC_CONNECTED'
    elif re.search(r'handshake.*(?:succeeded|successful)|successfully.*handshake',low):kind='IPC_HANDSHAKE_SUCCEEDED'
    elif re.search(r'failed to handshake|handshake.*failed',low):kind='IPC_HANDSHAKE_FAILED'
    elif 'signature' in low and ('error' in low or 'failed' in low):kind='SIGNATURE_ERROR'
    elif re.search(r'access token.*(?:unavailable|missing|not found)|no access token',low):kind='TOKEN_MISSING'
    elif re.search(r'\bulf\b|\.ulf\b',low) and re.search(r'not found|does not exist|could not find|missing|no such file',low):kind='ULF_MISSING'
    elif re.search(r'license file.*(?:not found|does not exist|missing)|could not find.*license file',low):kind='LICENSE_FILE_MISSING'
    elif re.search(r'no valid.*entitlement|entitlement.*(?:not found|missing|not active)',low):kind='ENTITLEMENT_MISSING'
    elif re.search(r'no valid (?:unity editor )?license|license is not active',low):kind='LICENSE_NOT_ACTIVE'
    elif re.search(r'licens.*validation fail|failed to validate.*licens',low):kind='LICENSE_VALIDATION_FAILED'
    elif re.search(r'timeoutpolicy|timed out|did not complete within.*timeout',low):kind='REQUEST_TIMEOUT'
    elif 'waiting' in low:
        if 'hub' in low:kind='WAIT_HUB'
        elif 'handshake' in low or 'ipc' in low or 'channel' in low:kind='WAIT_IPC'
        elif 'entitlement' in low:kind='WAIT_ENTITLEMENT'
        elif 'client' in low:kind='WAIT_CLIENT'
        elif 'license' in low:kind='WAIT_LICENSE'
    elif 'trying to connect' in low:kind='IPC_CONNECT_ATTEMPT'
    if kind is None and 'error' in low:kind='CLIENT_ERROR'
    code=None;namespace='NONE'
    exit_match=re.search(r'licensing\s*client.*(?:exited with|exit) (?:exit )?code\s*[:=]?\s*(\d{1,6})\b',low)
    message=re.search(r'\bcode\s*[:=]?\s*(\d{1,6})\b',low)
    if exit_match:
        value=int(exit_match.group(1));code=value if value in CLIENT_EXIT_CODES else 'OTHER';namespace='CLIENT_EXIT'
        kind='CLIENT_EXIT_OK' if value==0 else 'CLIENT_EXIT_ERROR'
    elif message:
        value=int(message.group(1));code=value if value in MESSAGE_CODES else 'OTHER';namespace='EDITOR_MESSAGE'
    if kind is None:return None
    return dict(kind=kind,codeNamespace=namespace,code=code)

def summarize(events,truncated=False):
    error=False;success=False;last=None
    for item in events:
        level=KINDS[item['kind']]
        if level=='ERROR':error=True;last='ERROR'
        elif level=='SUCCESS':success=True;last='SUCCESS'
    state='NONE_OBSERVED' if not events else 'PROGRESS_ONLY'
    if error and success:state='ERROR_THEN_SUCCESS' if last=='SUCCESS' else 'SUCCESS_THEN_ERROR'
    elif error:state='ERROR_ONLY'
    elif success:state='SUCCESS_ONLY'
    latest=events[-1]['kind'] if events else None
    return dict(events=events,truncated=truncated,sequenceState=state,lastObservedEvent=latest,lastExplicitWait=latest if latest in WAITS else 'NONE')

def empty():return {name:summarize([]) for name in ('editor','stdout')}

def add(stream,item):
    if item is None:return stream
    events=list(stream['events']);truncated=stream['truncated']
    if not events or events[-1]!=item:events.append(item)
    if len(events)>MAX_EVENTS:events=events[-MAX_EVENTS:];truncated=True
    return summarize(events,truncated)

def validate_streams(value):
    if not isinstance(value,dict) or set(value)!={'editor','stdout'}:raise ValueError()
    for stream in value.values():
        if not isinstance(stream,dict) or set(stream)!={'events','truncated','sequenceState','lastObservedEvent','lastExplicitWait'}:raise ValueError()
        if type(stream['truncated']) is not bool or not isinstance(stream['events'],list) or len(stream['events'])>MAX_EVENTS:raise ValueError()
        previous=None
        for item in stream['events']:
            if not isinstance(item,dict) or set(item)!={'kind','codeNamespace','code'} or item['kind'] not in KINDS or item['codeNamespace'] not in NAMESPACES:raise ValueError()
            code=item['code'];namespace=item['codeNamespace']
            if namespace=='NONE':
                if code is not None:raise ValueError()
            elif code!='OTHER' and (type(code) is not int or code not in (MESSAGE_CODES if namespace=='EDITOR_MESSAGE' else CLIENT_EXIT_CODES)):raise ValueError()
            if item['kind'].startswith('CLIENT_EXIT_')!=(namespace=='CLIENT_EXIT'):raise ValueError()
            if item['kind']=='CLIENT_EXIT_OK' and code!=0:raise ValueError()
            if item['kind']=='CLIENT_EXIT_ERROR' and code==0:raise ValueError()
            if item==previous:raise ValueError()
            previous=item
        if stream!=summarize(stream['events'],stream['truncated']):raise ValueError()
    return value

def status(streams,fallback):
    if any(s['truncated'] for s in streams.values()):return 'BOUNDED_EVENT_HISTORY'
    active=[s['sequenceState'] for s in streams.values() if s['events']]
    if not active:return fallback
    states=set(active)
    if len(states)>1:return 'MULTIPLE_STREAM_HISTORIES'
    state=active[0]
    return {'ERROR_THEN_SUCCESS':'ERROR_THEN_SUCCESS_REPORTED','SUCCESS_THEN_ERROR':'LATER_ERROR_AFTER_SUCCESS','SUCCESS_ONLY':'SUCCESS_EVENT_REPORTED','PROGRESS_ONLY':'PROGRESS_EVENTS_ONLY'}.get(state,fallback if fallback!='NONE_OBSERVED' else 'CLIENT_ERROR_REPORTED')
