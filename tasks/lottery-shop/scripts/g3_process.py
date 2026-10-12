#!/usr/bin/env python3
"""Retain 25 real G2 kills, then add six G3 command families x six windows."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import g3_ci as ci
import run_g2_process_probe as regression

POINTS=regression.POINTS
SCENARIOS=('challenge','consumable','replacement','borrow','repay','night')
CASES=tuple((s,p) for s in SCENARIOS for p in POINTS)
COMMON=regression.CASE_KEYS|{'observation'}
CASH=dict(challenge=29000,consumable=26000,replacement=8000,borrow=40000,repay=35000,night=28500)
COMMANDS=dict(challenge=2,consumable=4,replacement=2,borrow=1,repay=2,night=3)
ASSERTIONS={'ARGUMENTS','CRASH_APPLY','KILL_POINT_NOT_REACHED','SETUP','PREPARE_DIRECTORY','PREPARE_EQUAL','PREPARE_APPLY','INDEPENDENT_INVARIANTS','RECOVERY_BOUNDARY','RECOVERY_REPLAY','STALE_REPLAY','EXACTLY_ONCE','RESULT_WRITE'}


def expected_observation(scenario):
    mother=20000 if scenario=='replacement' else 10000 if scenario in ('borrow','repay') else 0
    return dict(cashMinor=CASH[scenario],principalMinor=300000,interestDueMinor=1500,interestPaidMinor=1500 if scenario=='night' else 0,
                motherBorrowedMinor=mother,motherOutstandingMinor=5000 if scenario=='repay' else mother,motherLoanCount=1 if mother else 0,motherDueNight=7 if mother else 0,
                toolCount=6 if scenario=='replacement' else 0,drawerCount=0,phase='DAY_COMPLETE' if scenario=='night' else 'DAY_OPEN',
                selectedCell=0 if scenario=='challenge' else -1,safeCount=0,copyMinor=5000 if scenario=='consumable' else 0,
                fixtureLabel='SYNTHETIC_INVENTORY_BOUNDARY_FIXTURE' if scenario=='replacement' else 'G3_DIAGNOSTIC_VECTOR_NOT_NATURAL')


def validate_case(data,scenario,point):
    ci.require((scenario,point) in CASES and isinstance(data,dict) and set(data)==COMMON,'G3 process case schema')
    published=point in ('AfterPublish','BeforeResponse')
    ci.require(data['status']=='PASS' and data['scenario']==scenario and data['point']==point and data['recoveryStatus']==('COMMITTED' if published else 'PROVEN_NOT_COMMITTED'),'G3 commit window evidence')
    for key in ('beforeHash','expectedHash','recoveredHash','finalHash'):ci.require(isinstance(data[key],str) and re.fullmatch(r'[0-9a-f]{64}',data[key]),'G3 process hash')
    ci.require(data['beforeHash']!=data['expectedHash'] and data['finalHash']==data['expectedHash'] and data['recoveredHash']==data['expectedHash' if published else 'beforeHash'],'G3 recovery hash mismatch')
    for key,value in (('finalCashMinor',CASH[scenario]),('attemptCommandOccurrences',1)):
        ci.require(type(data[key]) is int and data[key]==value,'G3 independent money/exactly-once mismatch')
    ci.require(type(data['finalCommands']) is int and data['finalCommands']==COMMANDS[scenario] and data['staleRevisionReplayUnchanged'] is True,'G3 replay failed')
    expected=expected_observation(scenario);observed=data['observation']
    ci.require(isinstance(observed,dict) and set(observed)==set(expected) and all(type(observed[k]) is type(v) and observed[k]==v for k,v in expected.items()),'G3 independent fixed observation differs')
    return data


def validate_suite(cases):
    ci.require(isinstance(cases,list) and len(cases)==36,'G3 requires exactly36 commit kills')
    for data,(s,p) in zip(cases,CASES):
        ci.require(data.get('exitSignal')=='SIGKILL' and type(data.get('childExitCode')) is int and data['childExitCode']==-signal.SIGKILL,'Missing actualSIGKILL')
        validate_case({k:v for k,v in data.items() if k not in ('exitSignal','childExitCode')},s,p)
    return cases


def source_paths(task):
    paths=[task/'scripts/process-g3/Program.cs',task/'scripts/process-g3/G3.ProcessProbe.csproj',task/'scripts/process-g3/NuGet.Config']
    paths += [task/'unity/Assets/G2/Core'/name for name in ('NumberTicketRules.cs','ScratchMask.cs')]
    paths+=[p for part in ('Core','Persistence','Ads') for p in (task/'unity/Assets/G3'/part).rglob('*.cs')]
    return sorted(paths)


def failure(task,identity,context,error):
    typ=type(error).__name__;typ=typ if typ in regression.EXCEPTIONS else 'Other'
    codes=[];worker=None
    work=task/'artifacts/g3-process'
    try:
        if context['stage'] in ('restore','build','binary'):
            aliases={str(p):p.relative_to(task).as_posix() for p in source_paths(task)}
            raw=ci.bounded_read(work/'compile.log',2*1024*1024).decode('utf-8',errors='replace')
            for line in raw.splitlines():
                m=re.match(r'^\s*(.*?)\s*:\s*error ((?:CS|MSB|NETSDK|NU)[0-9]{4,5})(?=[:\s])',line)
                if m:
                    prefix,code=m.groups();line_number=column=0
                    location=re.fullmatch(r'(.*?)\(([0-9]{1,7}),([0-9]{1,7})\)',prefix)
                    if location:prefix,line_number,column=location[1],int(location[2]),int(location[3])
                    item=dict(file=aliases.get(prefix,'UNMAPPED'),line=line_number,column=column,code=code)
                    if item not in codes:codes.append(item)
                if len(codes)>=32:break
        elif context['stage'] in ('prepare','checkpoint','verify','result'):
            for line in ci.bounded_read(work/'worker.log',2*1024*1024).decode('utf-8',errors='replace').splitlines():
                m=re.fullmatch(r'G3_PROBE_ERROR ([A-Z_]{1,48}) ([A-Za-z]{1,48})',line)
                if m and m[1] in ASSERTIONS and m[2] in regression.EXCEPTIONS:worker=dict(assertId=m[1],exceptionType=m[2])
    except Exception:pass
    code=error.returncode if isinstance(error,subprocess.CalledProcessError) else None
    ci.write_json(task/'evidence/g3/process/process-diagnostic.json',dict(identity,status='FAIL',scope='BOUNDED_IDENTIFIERS_ONLY_NOT_TEST_PASS',stage=context['stage'],scenario=context.get('scenario'),point=context.get('point'),exceptionType=typ,exitCode=code if type(code) is int and -255<=code<=255 else None,compilerErrors=codes,workerError=worker,deviceQa='NOT_RUN'))


def run_new(root):
    task=root/ci.TASK;output=task/'evidence/g3/process/process-receipt.json';output.unlink(missing_ok=True)
    output.with_name('process-diagnostic.json').unlink(missing_ok=True)
    identity={};context=dict(stage='guard')
    try:
        identity=ci.guard(root);ci.verify_inputs(root)
        baseline=json.loads(ci.bounded_read(task/'evidence/g2/process/process-receipt.json',256*1024))
        ci.require(baseline.get('sourceCommit')==identity['sourceCommit'] and baseline.get('runId')==identity['runId'] and baseline.get('runAttempt')==identity['runAttempt'] and baseline.get('requestId')==identity['requestId'] and baseline.get('status')=='PASS' and baseline.get('count')==25,'Same-source G2 process regression required first')
        regression.validate_suite(baseline['cases'])
        context['stage']='workspace';work=task/'artifacts/g3-process';ci.require(not work.exists(),'Refuse reused G3 process output');work.mkdir(parents=True)
        env=dict(os.environ,DOTNET_CLI_TELEMETRY_OPTOUT='1',DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1',DOTNET_CLI_HOME=str(work/'dotnet-home'),NUGET_PACKAGES=str(work/'nuget'))
        context['stage']='sdk_inventory'
        sdks=subprocess.check_output(['dotnet','--list-sdks'],text=True,env=env,stderr=subprocess.DEVNULL,timeout=15)
        sdks=[line.split(' ',1)[0] for line in sdks.splitlines() if re.match(r'8\.0\.[0-9]+ \[',line)]
        ci.require(sdks,'Installed .NET8 required; no download fallback');sdk=max(sdks,key=lambda s:tuple(map(int,s.split('.'))))
        ci.write_json(work/'global.json',dict(sdk=dict(version=sdk,rollForward='disable',allowPrerelease=False)))
        project=task/'scripts/process-g3/G3.ProcessProbe.csproj';intermediate=str(work/'obj')+'/'
        commands=[('restore',['dotnet','restore',str(project),'--configfile',str(project.parent/'NuGet.Config'),'-p:BaseIntermediateOutputPath='+intermediate]),('build',['dotnet','build',str(project),'--no-restore','-c','Release','-o',str(work/'bin'),'-p:BaseIntermediateOutputPath='+intermediate])]
        with (work/'compile.log').open('wb') as log:
            for stage,command in commands:
                context['stage']=stage;subprocess.run(command,cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90,check=True)
        context['stage']='binary';binary=work/'bin/Lottery.G3.ProcessProbe.dll';ci.require(binary.is_file(),'Missing G3 process binary')
        files=source_paths(task);ci.require(0<len(files)<=96,'G3 process source count');sources=[dict(path=p.relative_to(task).as_posix(),sha256=ci.digest(p)) for p in files]
        cases=[];deadline=time.monotonic()+360
        with (work/'worker.log').open('wb') as log:
            for scenario,point in CASES:
                context.update(stage='prepare',scenario=scenario,point=point);ci.require(time.monotonic()<deadline,'G3 process total bounded time exceeded')
                directory=work/(scenario+'-'+point)
                def command(mode):return ['dotnet',str(binary),mode,scenario,point,str(directory)]
                subprocess.run(command('prepare'),cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=15,check=True)
                context['stage']='checkpoint';child=subprocess.Popen(command('crash'),cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT)
                regression.kill_at_marker(child,directory/'ready',point)
                context['stage']='verify';subprocess.run(command('verify'),cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=15,check=True)
                context['stage']='result';data=json.loads(ci.bounded_read(directory/'result.json',8192));cases.append(dict(validate_case(data,scenario,point),exitSignal='SIGKILL',childExitCode=-9))
        context['stage']='receipt';validate_suite(cases)
        ci.write_json(output,dict(identity,status='PASS',scope='SYNTHETIC_FIXTURES_REAL_LINUX_DOTNET_PROCESS_KILL_NOT_UNITY_NOT_ANDROID',count=36,cases=cases,dotnetSdk=sdk,sourceFiles=sources,workerBinarySha256=ci.digest(binary),g2RegressionReceiptSha256=ci.digest(task/'evidence/g2/process/process-receipt.json'),unityProcessKill='NOT_RUN',androidForceStop='NOT_RUN',powerLossQa='NOT_RUN',deviceQa='NOT_RUN'))
    except Exception as error:failure(task,identity,context,error);raise
    print('36 actual .NET process SIGKILL cases passed; Unity/Android kill and physical input remain NOT_RUN.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('regression','new'));args=parser.parse_args()
    try:
        with ci.configured():
            root=Path(__file__).resolve().parents[3]
            if args.stage=='regression':ci.guard(root);regression.main(root)
            else:run_new(root)
    except Exception:
        print('G3 process verification failed; no raw logs exported.',file=sys.stderr);sys.exit(1)
