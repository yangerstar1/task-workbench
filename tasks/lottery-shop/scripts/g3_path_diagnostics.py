#!/usr/bin/env python3
"""Metadata-only checkout diagnosis, never a source/APK acceptance decision.
Production executes this committed, standard-library-only module with python -I -B.
No unknown file contents, link targets, raw names or exception text are exported.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import stat
import subprocess
import time

TASK = 'tasks/lottery-shop'
MAX_NODES, MAX_DEPTH, MAX_SECONDS, MAX_BYTES = 100000, 32, 20, 256 * 1024
MAX_GROUPS, MAX_MEMBERS, MAX_PATH_BYTES = 128, 128, 16 * 1024 * 1024
MAX_TOTAL_SECONDS = 30
FILE_NAME = 'diagnostic.json'
DIRECTORY_RE = r'lottery-g3-pathdiag-[0-9a-f]{24}'
BUCKETS = {
    TASK+'/unity/Library/Bee/Android':'LIBRARY_BEE_ANDROID',TASK+'/unity/Library/Bee':'LIBRARY_BEE',
    TASK+'/unity/Library/Artifacts':'LIBRARY_ARTIFACTS',TASK+'/unity/Library/PackageCache':'LIBRARY_PACKAGE_CACHE',
    TASK+'/unity/Library':'LIBRARY_OTHER',TASK+'/unity/.utmp':'UNITY_UTMP',TASK+'/unity/Temp':'UNITY_TEMP',TASK+'/unity/Obj':'UNITY_OBJ',
    TASK+'/unity/Logs':'UNITY_LOGS',TASK+'/unity/UserSettings':'UNITY_USER_SETTINGS',
    TASK+'/build/G3/Android':'APK_OUTPUT',TASK+'/build':'BUILD_OUTPUT',TASK+'/evidence':'EVIDENCE_OUTPUT',
    TASK+'/artifacts':'ARTIFACT_OUTPUT',TASK+'/unity/Assets':'UNITY_SOURCE',TASK+'/unity/Packages':'UNITY_PACKAGES',
    TASK+'/unity/ProjectSettings':'UNITY_SETTINGS',TASK+'/ci':'REVIEW_CONTROL',TASK+'/scripts':'SCRIPT_SOURCE',
    '.github/workflows':'WORKFLOW_SOURCE'}
# Labels are fixed vocabulary, not strings learned from the checkout. Leaf names
# are always hashed, even when identical to a known directory label.
KNOWN_DIRECTORIES = frozenset(('tasks','lottery-shop','unity','Assets','Packages','ProjectSettings','Library','Bee',
    'Android','Artifacts','PackageCache','Temp','Obj','Logs','UserSettings','artifacts','evidence','build','G3',
    'ci','scripts','.github','workflows','Fonts','Rendering','Resources','Editor','Tests','EditMode','PlayMode',
    '.gradle','gradle','caches','transforms','libs','jniLibs','arm64-v8a','unityLibrary','launcher','src','main',
    'Debug','Release','il2cppOutput','IL2CPP','il2cpp_cache','Burst','burst','StagingArea','obj','bin','generated',
    'intermediates','outputs','symbols','LibraryArtifacts','Builds','Build','output','unity-builder',
    '.utmp','tools','.cache','.local','.config','share','unity3d','Unity','Caches','ShaderCache','BurstCache','ScriptAssemblies',
    'BuildPlayerData','Il2cppBuildCache','il2cppOutputProject','com.unity.burst','com.unity.collections',
    'G0','G2','Core','Persistence','Ads','Interaction','Scenes','Settings','fonts','process-g3'))
CODES = frozenset(('OK','MISSING','UNSAFE','MALFORMED','IO_ERROR','NODE_LIMIT','DEPTH_LIMIT','TIME_LIMIT',
    'NAME_LIMIT','CHANGED','ROOT_MISMATCH','INVALID_ENVIRONMENT','OUTPUT_UNSAFE','OUTPUT_EXISTS',
    'OUTPUT_CHANGED','IDENTITY_MISMATCH','INTERNAL_ERROR'))

class DiagnosticError(ValueError):
    def __init__(self, code):
        self.code = code if code in CODES else 'INTERNAL_ERROR'
        super().__init__(self.code)


def sha_name(name):
    return hashlib.sha256(name.encode('utf-8','surrogateescape')).hexdigest()


def bucket(name):
    return next((BUCKETS[p] for p in sorted(BUCKETS,key=len,reverse=True)
                 if name==p or name.startswith(p+'/')), 'OTHER_CHECKOUT')


def path_shape(name):
    """Fixed labels or indexed full segment hashes; no unknown basename/extension."""
    parts=name.split('/') if name else []
    rows=[]
    for i,part in enumerate(parts[:12]):
        if i<len(parts)-1 and part in KNOWN_DIRECTORIES: rows.append(part)
        else: rows.append('u'+str(i)+'_'+sha_name(part))
    if len(parts)>12:rows.append('TRUNCATED')
    return '/'.join(rows) or 'UNKNOWN'


def kind(mode):
    return next((name for predicate,name in ((stat.S_ISREG,'regular'),(stat.S_ISDIR,'directory'),
        (stat.S_ISLNK,'symbolic_link'),(stat.S_ISFIFO,'fifo'),(stat.S_ISSOCK,'socket'),
        (stat.S_ISCHR,'character_device'),(stat.S_ISBLK,'block_device')) if predicate(mode)), 'unknown')


def stamp(info):
    return (info.st_dev,info.st_ino,info.st_mode,info.st_nlink)


def authority_stamp(info):
    # Directory nlink legitimately changes when our exclusive child is created.
    return (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid)


def content_stamp(info):
    return stamp(info)+(info.st_size,info.st_mtime_ns,info.st_ctime_ns)


def bounded_number(n):return n if type(n) is int and 0<=n<=2147483647 else -1


def absolute_parts(path):
    text=os.fspath(path)
    if not text.startswith('/') or '\x00' in text or any(p in ('.','..','') for p in text.split('/')[1:]):
        raise DiagnosticError('ROOT_MISMATCH')
    parts=text.split('/')[1:]
    if len(parts)>64 or len(text.encode('utf-8','surrogateescape'))>8192:raise DiagnosticError('ROOT_MISMATCH')
    return parts


def directory_anchor(path):
    """Retain initial ancestor identities/permissions for later re-anchoring."""
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    chain=[authority_stamp(os.fstat(fd))]
    try:
        for part in absolute_parts(path):
            info=os.stat(part,dir_fd=fd,follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode):raise DiagnosticError('UNSAFE')
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            observed=os.fstat(child)
            if stamp(observed)!=stamp(info) or authority_stamp(observed)!=authority_stamp(info):
                os.close(child);raise DiagnosticError('CHANGED')
            chain.append(authority_stamp(observed));os.close(fd);fd=child
        return fd,tuple(chain)
    except BaseException:
        os.close(fd);raise


def open_directory(path):
    return directory_anchor(path)[0]


def scan_pass(root_fd, deadline, max_nodes=MAX_NODES, max_depth=MAX_DEPTH):
    nodes={};errors=[];path_bytes=0;visited=0
    def walk(fd,prefix,depth):
        nonlocal path_bytes,visited
        if time.monotonic()>deadline:raise DiagnosticError('TIME_LIMIT')
        with os.scandir(fd) as it:
            for entry in it:
                if time.monotonic()>deadline:raise DiagnosticError('TIME_LIMIT')
                name=entry.name;relative=prefix+'/'+name if prefix else name
                visited+=1
                if visited>max_nodes:raise DiagnosticError('NODE_LIMIT')
                if relative in nodes:raise DiagnosticError('CHANGED')
                name_bytes=len(relative.encode('utf-8','surrogateescape'));path_bytes+=name_bytes
                if name_bytes>8192 or path_bytes>MAX_PATH_BYTES:raise DiagnosticError('NAME_LIMIT')
                info=os.stat(name,dir_fd=fd,follow_symlinks=False);nodes[relative]=stamp(info)
                if not prefix and name=='.git':
                    if not stat.S_ISDIR(info.st_mode):errors.append('UNSAFE')
                    continue
                if stat.S_ISDIR(info.st_mode):
                    if depth>=max_depth:raise DiagnosticError('DEPTH_LIMIT')
                    child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                    try:
                        if stamp(os.fstat(child))!=stamp(info):raise DiagnosticError('CHANGED')
                        walk(child,relative,depth+1)
                        if stamp(os.fstat(child))!=stamp(info):raise DiagnosticError('CHANGED')
                    finally:os.close(child)
    try:
        walk(root_fd,'',0)
        if time.monotonic()>deadline:raise DiagnosticError('TIME_LIMIT')
    except DiagnosticError as error:errors.append(error.code)
    except OSError:errors.append('IO_ERROR')
    return nodes,errors


def member(name,entry):
    return dict(pathClass=bucket(name),relativePathSha256=sha_name(name),pathShape=path_shape(name),
                kind=kind(entry[2]),nlink=bounded_number(entry[3]),depth=len(name.split('/')))


def collect(root_fd, max_nodes=MAX_NODES, max_depth=MAX_DEPTH, seconds=MAX_SECONDS):
    start=time.monotonic();deadline=start+seconds;root_before=stamp(os.fstat(root_fd))
    before,errors1=scan_pass(root_fd,deadline,max_nodes,max_depth)
    after,errors2=scan_pass(root_fd,deadline,max_nodes,max_depth)
    root_after=stamp(os.fstat(root_fd))
    if time.monotonic()>deadline:errors2.append('TIME_LIMIT')
    stable=not errors1 and not errors2 and before==after and root_before==root_after
    inode_groups={};special=[]
    for name,entry in after.items():
        if stat.S_ISREG(entry[2]):inode_groups.setdefault(entry[:2],[]).append((name,entry))
        elif not stat.S_ISDIR(entry[2]):special.append((name,entry))
    interesting=[v for v in inode_groups.values() if any(e[3]!=1 for _,e in v)]
    # Priority assists the actual OTHER_CHECKOUT incident without granting it trust.
    interesting.sort(key=lambda rows:(all(bucket(n).startswith('LIBRARY_') for n,_ in rows),sha_name(min(n for n,_ in rows))))
    groups=[];truncated=len(interesting)>MAX_GROUPS or len(special)>MAX_GROUPS;remaining=MAX_BYTES-16384
    def budgeted(row):
        nonlocal remaining,truncated
        if time.monotonic()>start+MAX_TOTAL_SECONDS:raise DiagnosticError('TIME_LIMIT')
        size=len(json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii'))+2
        if size>remaining:truncated=True;return False
        remaining-=size;return True
    for rows in interesting[:MAX_GROUPS]:
        rows.sort(key=lambda row:sha_name(row[0]));counts={e[3] for _,e in rows}
        if len(rows)>MAX_MEMBERS:truncated=True
        row=dict(observedCheckoutMembers=len(rows),observedNlinkValues=sorted(bounded_number(n) for n in counts),
            membershipEqualsNlink=stable and len(counts)==1 and len(rows)==next(iter(counts)),
            members=[member(n,e) for n,e in rows[:MAX_MEMBERS]],membersTruncated=len(rows)>MAX_MEMBERS)
        if not budgeted(row):break
        groups.append(row)
    special.sort(key=lambda row:sha_name(row[0]));special_rows=[]
    for n,e in special[:MAX_GROUPS]:
        row=member(n,e)
        if not budgeted(row):break
        special_rows.append(row)
    return dict(scope='CHECKOUT_WITH_OPAQUE_ROOT_DOT_GIT_DIRECTORY',atomicSnapshot=False,
        firstPassEntries=len(before),secondPassEntries=len(after),enumerationComplete=not errors1 and not errors2,
        stable=stable,complete=stable and not truncated,reportTruncated=truncated,
        errors=sorted(set(errors1+errors2+([] if stable or errors1 or errors2 else ['CHANGED']))),
        limits=dict(nodes=max_nodes,depth=max_depth,seconds=seconds,reportBytes=MAX_BYTES,groups=MAX_GROUPS,membersPerGroup=MAX_MEMBERS,pathBytesPerPass=MAX_PATH_BYTES),
        hardlinkGroups=groups,specialNodes=special_rows,
        missingLinkLocation='UNDETERMINED',creator='UNDETERMINED',priorRunCause='UNDETERMINED')


def read_known(root_fd,relative,limit):
    """Only named pipeline JSON records. Never opens a scanned unknown path."""
    fd=os.dup(root_fd)
    try:
        parts=relative.split('/')
        for part in parts[:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
        info=os.stat(parts[-1],dir_fd=fd,follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>limit:raise DiagnosticError('UNSAFE')
        file_fd=os.open(parts[-1],os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW,dir_fd=fd)
        try:
            if content_stamp(os.fstat(file_fd))!=content_stamp(info):raise DiagnosticError('CHANGED')
            data=os.read(file_fd,limit+1)
            if len(data)>limit or content_stamp(os.fstat(file_fd))!=content_stamp(info) or content_stamp(os.stat(parts[-1],dir_fd=fd,follow_symlinks=False))!=content_stamp(info):raise DiagnosticError('CHANGED')
            value=json.loads(data)
            if not isinstance(value,dict):raise DiagnosticError('MALFORMED')
            return value,hashlib.sha256(data).hexdigest(),'OK'
        finally:os.close(file_fd)
    except FileNotFoundError:return None,None,'MISSING'
    except DiagnosticError as error:return None,None,error.code
    except (OSError,ValueError,TypeError):return None,None,'MALFORMED'
    finally:os.close(fd)


def identity(root_fd,head,env):
    fields={'sourceCommit':r'[0-9a-f]{40}','runId':r'[1-9][0-9]{0,19}','runAttempt':r'[1-9][0-9]{0,5}'}
    names={'sourceCommit':'GITHUB_SHA','runId':'GITHUB_RUN_ID','runAttempt':'GITHUB_RUN_ATTEMPT'}
    expected={k:env.get(names[k]) if re.fullmatch(pattern,env.get(names[k],'')) else None for k,pattern in fields.items()}
    cold,_,cold_status=read_known(root_fd,TASK+'/evidence/g3/android/cold-build-baseline.json',16384)
    snapshot,snapshot_sha,snapshot_status=read_known(root_fd,TASK+'/evidence/pre-unity-source.json',1024*1024)
    review,_,review_status=read_known(root_fd,TASK+'/ci/g3-preflight.review.json',256*1024)
    observed={k:(cold.get(k) if cold and isinstance(cold.get(k),str) and re.fullmatch(pattern,cold[k]) else None) for k,pattern in fields.items()}
    observed['gitHead']=head
    validations={k:('MISSING' if expected[k] is None or observed[k] is None else 'MATCH' if expected[k]==observed[k] else 'MISMATCH') for k in fields}
    validations['gitHead']='MATCH' if head==expected['sourceCommit'] else 'MISMATCH'
    validations['job']='MATCH' if env.get('GITHUB_JOB')=='android' and cold and cold.get('job')=='android' else 'MISMATCH'
    validations['coldObservation']='MATCH' if cold and cold.get('status')=='VERIFIED_BEFORE_UNITY' and cold.get('cachePolicy')=='LIBRARY_UTMP_INTERNAL_HARDLINKS_V2' and cold.get('libraryAbsent') is True and cold.get('utmpAbsent') is True and cold.get('buildAbsent') is True and cold.get('cacheRestored') is False else 'MISSING_OR_MISMATCH'
    validations['snapshotBytes']='MATCH' if snapshot_sha and cold and cold.get('preUnitySourceSha256')==snapshot_sha else 'MISSING_OR_MISMATCH'
    source_map=review.get('sourceFiles') if review else None;wanted={};prefix=TASK+'/unity/'
    if isinstance(source_map,dict) and len(source_map)<=4096:
        wanted={n[len(prefix):]:v for n,v in source_map.items() if isinstance(n,str) and n.startswith(prefix) and n[len(prefix):].split('/',1)[0] in ('Assets','Packages','ProjectSettings')}
        wanted['Assets/Resources/ProbeChinese.otf']='a6a530f3e7e7a2c299470c42efff2e109fcc0a5be92686b96d5e84a05f3ecb2b'
    validations['snapshotReviewRelation']='MATCH' if snapshot and wanted and snapshot==wanted else 'MISSING_OR_MISMATCH'
    request=(review.get('requestId') if review else None)
    validations['requestRelation']='MATCH' if isinstance(request,str) and re.fullmatch(r'lottery-g3-[0-9]{8}-[0-9]{2}',request) and cold and cold.get('requestId')==request else 'MISSING_OR_MISMATCH'
    return dict(expected=expected,observed=observed,validation=validations,
        recordReadStatus=dict(cold=cold_status,snapshot=snapshot_status,review=review_status),
        authority='CONSISTENCY_OBSERVATIONS_ONLY_NOT_SOURCE_APPROVAL')


def git_environment():
    # No inherited Git repository/object/config/trace variables or HOME/XDG.
    return {'PATH':'/usr/bin:/bin','LC_ALL':'C','GIT_CONFIG_NOSYSTEM':'1',
            'GIT_CONFIG_SYSTEM':'/dev/null','GIT_CONFIG_GLOBAL':'/dev/null','GIT_NO_REPLACE_OBJECTS':'1'}


def git_value(root,argument):
    # Fixed read-only Git commands; cap pipe bytes while reading, not afterward.
    child=subprocess.Popen(['/usr/bin/git','--no-replace-objects','--git-dir='+str(root/'.git'),'--work-tree='+str(root),'rev-parse',argument],env=git_environment(),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    raw=bytearray();deadline=time.monotonic()+5
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout,selectors.EVENT_READ)
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0 or not selector.select(remaining):raise DiagnosticError('TIME_LIMIT')
                chunk=os.read(child.stdout.fileno(),8193-len(raw))
                if not chunk:break
                raw.extend(chunk)
                if len(raw)>8192:raise DiagnosticError('NAME_LIMIT')
        if child.wait(timeout=max(0.01,deadline-time.monotonic()))!=0:raise DiagnosticError('ROOT_MISMATCH')
        if time.monotonic()>deadline:raise DiagnosticError('TIME_LIMIT')
        return bytes(raw)
    finally:
        if child.poll() is None:child.kill()
        child.wait(timeout=5);child.stdout.close()


def checked_root(env):
    root=Path(env.get('GITHUB_WORKSPACE',''))
    fd=open_directory(root)
    try:
        git_info=os.stat('.git',dir_fd=fd,follow_symlinks=False)
        if not stat.S_ISDIR(git_info.st_mode):raise DiagnosticError('ROOT_MISMATCH')
        git_fd=os.open('.git',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
        try:
            if stamp(os.fstat(git_fd))!=stamp(git_info):raise DiagnosticError('CHANGED')
            top=git_value(root,'--show-toplevel')
            if top.rstrip(b'\n')!=os.fsencode(root):raise DiagnosticError('ROOT_MISMATCH')
            head=git_value(root,'HEAD').decode('ascii').strip()
            if stamp(os.stat('.git',dir_fd=fd,follow_symlinks=False))!=stamp(git_info):raise DiagnosticError('CHANGED')
        finally:os.close(git_fd)
        if not re.fullmatch('[0-9a-f]{40}',head) or head!=env.get('GITHUB_SHA'):raise DiagnosticError('ROOT_MISMATCH')
        return root,fd,head
    except BaseException:os.close(fd);raise


def output_handles(root,env):
    temp=Path(env.get('RUNNER_TEMP',''));parts=absolute_parts(temp);root_parts=absolute_parts(root)
    if parts[:len(root_parts)]==root_parts or root_parts[:len(parts)]==parts:raise DiagnosticError('OUTPUT_UNSAFE')
    temp_fd,temp_chain=directory_anchor(temp);output_fd=None;parent=None;parent_chain=[]
    try:
        info=os.fstat(temp_fd)
        if info.st_uid!=os.geteuid() or not info.st_mode&stat.S_IWUSR or not info.st_mode&stat.S_IXUSR or info.st_mode&0o022:raise DiagnosticError('OUTPUT_UNSAFE')
        output=Path(env.get('GITHUB_OUTPUT',''));output_parts=absolute_parts(output)
        if output_parts[:len(parts)]!=parts or len(output_parts)<=len(parts):raise DiagnosticError('OUTPUT_UNSAFE')
        parent=os.dup(temp_fd)
        for part in output_parts[len(parts):-1]:
            info=os.stat(part,dir_fd=parent,follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o022:raise DiagnosticError('OUTPUT_UNSAFE')
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
            if stamp(os.fstat(child))!=stamp(info):os.close(child);raise DiagnosticError('OUTPUT_CHANGED')
            parent_chain.append((part,authority_stamp(info)))
            os.close(parent);parent=child
        before=os.stat(output.name,dir_fd=parent,follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_uid!=os.geteuid() or before.st_mode&0o022 or not before.st_mode&stat.S_IWUSR or before.st_size>65536:raise DiagnosticError('OUTPUT_UNSAFE')
        output_fd=os.open(output.name,os.O_WRONLY|os.O_APPEND|os.O_NONBLOCK|os.O_NOFOLLOW,dir_fd=parent)
        if stamp(os.fstat(output_fd))!=stamp(before):raise DiagnosticError('OUTPUT_CHANGED')
        authority=dict(tempPath=temp,tempChain=temp_chain,tempStamp=authority_stamp(os.fstat(temp_fd)),parents=tuple(parent_chain),
            leafAuthority=authority_stamp(before),leafStamp=stamp(before),leafContent=content_stamp(before),leafSize=before.st_size)
        channel=(output_fd,parent,output.name,authority)
        recheck_output(temp_fd,channel)
        return temp,temp_fd,channel
    except BaseException:
        if output_fd is not None:os.close(output_fd)
        if parent is not None:os.close(parent)
        os.close(temp_fd);raise


def recheck_output(temp_fd,channel,appended_bytes=0):
    """Rewalk every named ancestor against the original admission, before writes."""
    output_fd,parent_fd,output_name,initial=channel
    fresh=None
    try:
        fresh,chain=directory_anchor(initial['tempPath'])
        if chain!=initial['tempChain'] or authority_stamp(os.fstat(temp_fd))!=initial['tempStamp'] or authority_stamp(os.fstat(fresh))!=initial['tempStamp']:
            raise DiagnosticError('OUTPUT_CHANGED')
        for name,expected in initial['parents']:
            info=os.stat(name,dir_fd=fresh,follow_symlinks=False)
            if authority_stamp(info)!=expected or not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o022:
                raise DiagnosticError('OUTPUT_CHANGED')
            child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fresh)
            if authority_stamp(os.fstat(child))!=expected:
                os.close(child);raise DiagnosticError('OUTPUT_CHANGED')
            os.close(fresh);fresh=child
        if authority_stamp(os.fstat(fresh))!=authority_stamp(os.fstat(parent_fd)):
            raise DiagnosticError('OUTPUT_CHANGED')
        named=os.stat(output_name,dir_fd=fresh,follow_symlinks=False);opened=os.fstat(output_fd)
        for info in (named,opened):
            if authority_stamp(info)!=initial['leafAuthority'] or stamp(info)!=initial['leafStamp'] or info.st_nlink!=1 or not stat.S_ISREG(info.st_mode) or info.st_size!=initial['leafSize']+appended_bytes:
                raise DiagnosticError('OUTPUT_CHANGED')
            if appended_bytes==0 and content_stamp(info)!=initial['leafContent']:raise DiagnosticError('OUTPUT_CHANGED')
    except OSError:raise DiagnosticError('OUTPUT_CHANGED') from None
    finally:
        if fresh is not None:os.close(fresh)


def encode_report(report):
    raw=(json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'\n').encode('ascii')
    if len(raw)>MAX_BYTES:raise DiagnosticError('OUTPUT_UNSAFE')
    return raw


def publish(temp_fd,channel,raw):
    output_fd,parent_fd,output_name=channel[:3]
    if len(raw)>MAX_BYTES:raise DiagnosticError('OUTPUT_UNSAFE')
    # Compare to the original admission, not two current views of changed fds.
    recheck_output(temp_fd,channel)
    before=os.fstat(output_fd)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_uid!=os.geteuid() or before.st_mode&0o022 or not before.st_mode&stat.S_IWUSR:raise DiagnosticError('OUTPUT_UNSAFE')
    if stamp(os.stat(output_name,dir_fd=parent_fd,follow_symlinks=False))!=stamp(before):raise DiagnosticError('OUTPUT_CHANGED')
    dirname='lottery-g3-pathdiag-'+secrets.token_hex(12)
    try:os.mkdir(dirname,mode=0o700,dir_fd=temp_fd)
    except FileExistsError:raise DiagnosticError('OUTPUT_EXISTS')
    created=os.stat(dirname,dir_fd=temp_fd,follow_symlinks=False)
    directory_fd=os.open(dirname,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=temp_fd)
    try:
        info=os.fstat(directory_fd)
        if stamp(info)!=stamp(created) or info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700:raise DiagnosticError('OUTPUT_UNSAFE')
        recheck_output(temp_fd,channel)
        try:file_fd=os.open(FILE_NAME,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory_fd)
        except FileExistsError:raise DiagnosticError('OUTPUT_EXISTS')
        try:
            file_info=os.fstat(file_fd)
            if not stat.S_ISREG(file_info.st_mode) or file_info.st_nlink!=1:raise DiagnosticError('OUTPUT_UNSAFE')
            recheck_output(temp_fd,channel)
            view=memoryview(raw)
            while view:view=view[os.write(file_fd,view):]
            os.fsync(file_fd)
            after=os.stat(FILE_NAME,dir_fd=directory_fd,follow_symlinks=False)
            if stamp(after)!=stamp(file_info) or after.st_size!=len(raw):raise DiagnosticError('OUTPUT_CHANGED')
            os.fchmod(file_fd,0o400);file_info=os.fstat(file_fd)
        finally:os.close(file_fd)
        if stamp(os.fstat(output_fd))!=stamp(before) or stamp(os.stat(output_name,dir_fd=parent_fd,follow_symlinks=False))!=stamp(before):raise DiagnosticError('OUTPUT_CHANGED')
        if stamp(os.stat(dirname,dir_fd=temp_fd,follow_symlinks=False))!=stamp(info) or stamp(os.stat(FILE_NAME,dir_fd=directory_fd,follow_symlinks=False))!=stamp(file_info):raise DiagnosticError('OUTPUT_CHANGED')
        os.fchmod(directory_fd,0o500);info=os.fstat(directory_fd)
        recheck_output(temp_fd,channel)
        line=('diagnostic_relative_path='+dirname+'/'+FILE_NAME+'\n').encode('ascii')
        if os.write(output_fd,line)!=len(line):raise DiagnosticError('OUTPUT_CHANGED')
        os.fsync(output_fd)
        recheck_output(temp_fd,channel,appended_bytes=len(line))
        if stamp(os.fstat(output_fd))!=stamp(before) or stamp(os.stat(output_name,dir_fd=parent_fd,follow_symlinks=False))!=stamp(before):raise DiagnosticError('OUTPUT_CHANGED')
        if stamp(os.stat(dirname,dir_fd=temp_fd,follow_symlinks=False))!=stamp(info) or stamp(os.stat(FILE_NAME,dir_fd=directory_fd,follow_symlinks=False))!=stamp(file_info):raise DiagnosticError('OUTPUT_CHANGED')
    finally:os.close(directory_fd)
    return dirname


def main():
    deadline=time.monotonic()+MAX_TOTAL_SECONDS
    root,root_fd,head=checked_root(os.environ)
    root_initial=authority_stamp(os.fstat(root_fd))
    try:
        temp,temp_fd,channel=output_handles(root,os.environ)
        try:
            report=dict(schemaVersion=1,status='DIAGNOSTIC_ONLY',acceptance='NONE',sourceAudit='NOT_EVALUATED',apkVerification='NOT_EVALUATED',
                identity=identity(root_fd,head,os.environ),scan=collect(root_fd),
                confidentiality='HASHES_ARE_DICTIONARY_GUESSABLE_NO_RAW_UNKNOWN_NAMES_OR_CONTENT',
                nativeExecution='NOT_PERFORMED_BY_DIAGNOSTIC')
            # Root and output-directory paths must still identify the anchored fds.
            for path,fd in ((root,root_fd),(temp,temp_fd)):
                current=open_directory(path)
                try:
                    if stamp(os.fstat(current))!=stamp(os.fstat(fd)):raise DiagnosticError('CHANGED')
                finally:os.close(current)
            if authority_stamp(os.fstat(root_fd))!=root_initial:raise DiagnosticError('CHANGED')
            recheck_output(temp_fd,channel)
            raw=encode_report(report)
            if time.monotonic()>deadline:raise DiagnosticError('TIME_LIMIT')
            publish(temp_fd,channel,raw)
            print('G3_PATH_DIAGNOSTIC status=DIAGNOSTIC_ONLY complete='+str(report['scan']['complete']).lower()+' stable='+str(report['scan']['stable']).lower())
        finally:os.close(channel[0]);os.close(channel[1]);os.close(temp_fd)
    finally:os.close(root_fd)

if __name__=='__main__':
    try:main()
    except Exception as error:
        code=error.code if isinstance(error,DiagnosticError) and error.code in CODES else 'INTERNAL_ERROR'
        print('G3_PATH_DIAGNOSTIC_ERROR code='+code,file=sys.stderr);sys.exit(1)
