#!/usr/bin/env python3
"""Classify private Editor/stdout logs before deletion. Never export text, paths or credentials."""
import argparse,json,os,pathlib,re
import license_observation as licensing
import launcher_context
SCANS={'COMPLETE','BOUNDED','NO_LOGS','UNREADABLE','UNAVAILABLE'}
LICENSE={'NONE_OBSERVED','NO_VALID_LICENSE','VALIDATION_FAILURE','CLIENT_UNAVAILABLE','CLIENT_ERROR_REPORTED','ERROR_THEN_SUCCESS_REPORTED','LATER_ERROR_AFTER_SUCCESS','SUCCESS_EVENT_REPORTED','PROGRESS_EVENTS_ONLY','MULTIPLE_STREAM_HISTORIES','BOUNDED_EVENT_HISTORY'}
GRAPHICS={'NONE_OBSERVED','DISPLAY_FAILURE','DEVICE_INIT_FAILURE','OPENGL_ERROR','NULL_BACKEND'}
PROGRESS=('engine-version-reported','mono-runtime-configured','asset-refresh-observed','asset-import-observed','package-manager-observed','compiler-command-observed','script-compilation-started','script-compilation-finished','assembly-reload-started','assembly-reload-finished','shader-compilation-observed','project-load-complete')
CODES={'CS0006','CS0012','CS0016','CS0029','CS0030','CS0101','CS0103','CS0104','CS0106','CS0111','CS0117','CS0118','CS0120','CS0121','CS0122','CS0136','CS0161','CS0200','CS0234','CS0246','CS0266','CS0535','CS0619','CS1001','CS1002','CS1003','CS1022','CS1026','CS1061','CS1068','CS1069','CS1501','CS1502','CS1503','CS1513','CS1519','CS1525','CS1617','CS1705','UNKNOWN_CSHARP_ERROR'}
UNKNOWN_SOURCE='UNKNOWN_PROJECT_SOURCE'
FIELDS={'schema','mode','scanStatus','compileErrors','compilerDiagnostics','diagnosticsTruncated','executeMethodNotFound','licenseStatus','graphicsStatus','nativeLibraryFailure','startupProgress','editorWaitExitCode','captureExitCode','terminationRequest','rawLogsExported','licenseObservations','launcherContext'}
MAX_BYTES=64*1024*1024;MAX_LINE=16384;MAX_DIAGNOSTICS=8

def safe(path):
    p=pathlib.Path(path)
    if p.is_symlink() or any(x.is_symlink() for x in p.parents):raise ValueError()
    return p

def source_map(project):
    root=safe(pathlib.Path(project));base=safe(root/'Assets/DesertRV');result={}
    if not base.is_dir():return result
    for directory,dirs,files in os.walk(base,followlinks=False):
        d=safe(pathlib.Path(directory))
        for name in dirs:safe(d/name)
        for name in files:
            if re.fullmatch(r'[A-Za-z0-9_.-]{1,96}\.cs',name):
                p=safe(d/name)
                if p.is_file():result[p.relative_to(root).as_posix()]=name
    return result

def empty_report(editor=None,capture=None,termination='NONE'):
    return dict(schema=1,mode='EDITOR_STARTUP_FIXED_DIAGNOSTIC',scanStatus='UNAVAILABLE',compileErrors=False,compilerDiagnostics=[],diagnosticsTruncated=False,executeMethodNotFound=False,licenseStatus='NONE_OBSERVED',graphicsStatus='NONE_OBSERVED',nativeLibraryFailure=False,startupProgress=[],editorWaitExitCode=editor,captureExitCode=capture,terminationRequest=termination,rawLogsExported=False,licenseObservations=licensing.empty(),launcherContext=launcher_context.empty())

def validate(report,known_basenames):
    if not isinstance(report,dict) or set(report)!=FIELDS:raise ValueError()
    if type(report['schema']) is not int or report['schema']!=1 or report['mode']!='EDITOR_STARTUP_FIXED_DIAGNOSTIC':raise ValueError()
    if report['scanStatus'] not in SCANS or report['licenseStatus'] not in LICENSE or report['graphicsStatus'] not in GRAPHICS:raise ValueError()
    if report['terminationRequest'] not in {'NONE','SIGTERM_ON_CAPTURE_FAILURE','SIGTERM_ON_SHELL_CLEANUP'}:raise ValueError()
    for key in ('compileErrors','diagnosticsTruncated','executeMethodNotFound','nativeLibraryFailure','rawLogsExported'):
        if type(report[key]) is not bool:raise ValueError()
    if report['rawLogsExported'] is not False:raise ValueError()
    for key in ('editorWaitExitCode','captureExitCode'):
        if report[key] is not None and (type(report[key]) is not int or not 0<=report[key]<=255):raise ValueError()
    progress=report['startupProgress']
    if not isinstance(progress,list) or progress!=[p for p in PROGRESS if p in progress]:raise ValueError()
    diagnostics=report['compilerDiagnostics']
    if not isinstance(diagnostics,list) or len(diagnostics)>MAX_DIAGNOSTICS:raise ValueError()
    pairs=[]
    for item in diagnostics:
        if not isinstance(item,dict) or set(item)!={'code','sourceBasename'}:raise ValueError()
        if item['code'] not in CODES or item['sourceBasename'] not in set(known_basenames)|{UNKNOWN_SOURCE}:raise ValueError()
        pairs.append((item['code'],item['sourceBasename']))
    if pairs!=sorted(set(pairs)) or (pairs and not report['compileErrors']):raise ValueError()
    licensing.validate_streams(report['licenseObservations'])
    launcher_context.validate(report['launcherContext'])
    return report

def classify(log_directory,project,editor=None,capture=None,termination='NONE'):
    names=source_map(project);r=empty_report(editor,capture,termination);seen=set();diagnostics=set();bytes_read=0;found=False;bounded=False
    try:
        for filename in ('editor.log','rendered.log'): # activation.log and return.log are NEVER opened.
            path=safe(pathlib.Path(log_directory)/filename)
            if not path.exists():continue
            if not path.is_file():raise ValueError()
            found=True
            with path.open('rb') as stream:
                while bytes_read<MAX_BYTES:
                    data=stream.readline(MAX_LINE+1)
                    if not data:break
                    bytes_read+=len(data)
                    if len(data)>MAX_LINE:
                        bounded=True
                        while data and not data.endswith(b'\n') and bytes_read<MAX_BYTES:
                            data=stream.readline(MAX_LINE+1);bytes_read+=len(data)
                        continue
                    line=data.decode('utf-8','replace');low=line.lower()
                    stream_name='editor' if filename=='editor.log' else 'stdout'
                    r['licenseObservations'][stream_name]=licensing.add(r['licenseObservations'][stream_name],licensing.event(line))
                    codes=re.findall(r'\berror\s+(CS[0-9]{4})\b',line)
                    if codes or 'scripts have compiler errors' in low or 'scripts have compilation errors' in low:r['compileErrors']=True
                    location=re.search(r'(?P<source>Assets/DesertRV/[A-Za-z0-9_./-]+\.cs)\([0-9]+(?:,[0-9]+)?\)',line.replace('\\','/'))
                    basename=names.get(location.group('source'),UNKNOWN_SOURCE) if location else UNKNOWN_SOURCE
                    for code in codes:diagnostics.add((code if code in CODES else 'UNKNOWN_CSHARP_ERROR',basename))
                    if re.search(r'executeMethod.*(?:not found|could not be found|does not exist)',line,re.I):r['executeMethodNotFound']=True
                    if re.search(r'no valid (?:unity editor )?license|license (?:file )?not found',low):r['licenseStatus']='NO_VALID_LICENSE'
                    elif re.search(r'licens(?:e|ing).*validation fail|failed to (?:validate|activate).*licens',low):r['licenseStatus']='VALIDATION_FAILURE'
                    elif r['licenseStatus']=='NONE_OBSERVED' and re.search(r'failed to connect.*licensing client|licensing client.*(?:not found|unavailable)',low):r['licenseStatus']='CLIENT_UNAVAILABLE'
                    if r['licenseStatus']=='NONE_OBSERVED' and '[licensing::' in low and 'error' in low:r['licenseStatus']='CLIENT_ERROR_REPORTED'
                    if re.search(r'(?:cannot|unable to|could not) open display',low):r['graphicsStatus']='DISPLAY_FAILURE'
                    elif re.search(r'failed to (?:initialize graphics|create graphics device|initialize gfx)',low):r['graphicsStatus']='DEVICE_INIT_FAILURE'
                    elif r['graphicsStatus']=='NONE_OBSERVED' and 'libgl error:' in low:r['graphicsStatus']='OPENGL_ERROR'
                    elif r['graphicsStatus']=='NONE_OBSERVED' and 'nullgfxdevice' in low:r['graphicsStatus']='NULL_BACKEND'
                    if 'error while loading shared libraries:' in low:r['nativeLibraryFailure']=True
                    tokens={
                      'engine-version-reported':'initialize engine version:', 'mono-runtime-configured':'mono config path',
                      'asset-refresh-observed':'asset pipeline refresh', 'script-compilation-started':'starting script compilation',
                      'script-compilation-finished':'script compilation finished', 'assembly-reload-started':'begin monomanager reloadassembly',
                      'assembly-reload-finished':'completed reload, in', 'shader-compilation-observed':'shadercompiler', 'project-load-complete':'project load complete'}
                    for marker,token in tokens.items():
                        if token in low:seen.add(marker)
                    if re.search(r'compiling shader|shader compilation',low):seen.add('shader-compilation-observed')
                    if 'importing assets/' in low or 'importing packages/' in low:seen.add('asset-import-observed')
                    if '[package manager]' in low:seen.add('package-manager-observed')
                    if 'csc.exe' in low or 'csc.dll' in low:seen.add('compiler-command-observed')
                    if 'script compilation time:' in low:seen.add('script-compilation-finished')
                if bytes_read>=MAX_BYTES:bounded=True;break
        r['scanStatus']='BOUNDED' if bounded else 'COMPLETE' if found else 'NO_LOGS'
    except Exception:r['scanStatus']='UNREADABLE'
    r['compilerDiagnostics']=[dict(code=c,sourceBasename=n) for c,n in sorted(diagnostics)[:MAX_DIAGNOSTICS]]
    r['diagnosticsTruncated']=len(diagnostics)>MAX_DIAGNOSTICS;r['startupProgress']=[p for p in PROGRESS if p in seen]
    r['launcherContext']=launcher_context.load(pathlib.Path(log_directory)/'launcher-context.json')
    r['licenseStatus']=licensing.status(r['licenseObservations'],r['licenseStatus'])
    return validate(r,set(names.values()))

def load_report(path,project):
    try:
        p=safe(path)
        if not p.is_file() or p.stat().st_size>8192:raise ValueError()
        def unique(pairs):
            d={}
            for k,v in pairs:
                if k in d:raise ValueError()
                d[k]=v
            return d
        return validate(json.loads(p.read_text(),object_pairs_hook=unique),set(source_map(project).values()))
    except Exception:return empty_report()

def main():
    p=argparse.ArgumentParser();p.add_argument('--logs',required=True);p.add_argument('--project',required=True);p.add_argument('--output',required=True);p.add_argument('--editor-exit',default='unknown');p.add_argument('--capture-exit',default='unknown');p.add_argument('--termination',default='NONE');a=p.parse_args()
    try:
        def code(v):return None if v=='unknown' else int(v)
        report=classify(a.logs,a.project,code(a.editor_exit),code(a.capture_exit),a.termination)
        out=safe(a.output);out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(report)+'\n');os.replace(tmp,out)
    except Exception:return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
