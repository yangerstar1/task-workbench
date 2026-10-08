#!/usr/bin/env python3
"""One authorized run only; no chmod, groups, udev, or recurring grant."""
import errno, json, os, pathlib, re, signal, subprocess, sys, time
DEVICE='/dev/kvm'
def require(ok,msg):
    if not ok: raise RuntimeError(msg)
def output(args):return subprocess.check_output(args,text=True)
def parse(text):
    entries=[s.strip() for s in text.splitlines() if s.strip() and not s.startswith('#')]
    result={}
    for s in entries:
        require(re.fullmatch(r'(user|group|mask|other):[0-9]*:[r-][w-][x-]',s) is not None,'Complex ACL refused')
        k,v=s.rsplit(':',1);require(k not in result,'Duplicate ACL');result[k]=v
    return result
def snapshot():return output(['getfacl','-p','-n',DEVICE])
def paths():
    w=pathlib.Path(os.environ['QA_WORK']);return w/'kvm-original.acl',w/'kvm-acl-active.json'
def restore():
    backup,active=paths()
    if not active.exists():return
    data=json.loads(active.read_text());require(data['uid']==os.getuid() and data['runId']==os.environ['GITHUB_RUN_ID'],'Restore identity mismatch')
    pidfile=pathlib.Path(os.environ['QA_WORK'])/'emulator-group.pid'
    if pidfile.exists():
        pid=int(pidfile.read_text());require(pid>1,'Invalid emulator process group')
        try:os.killpg(pid,signal.SIGTERM)
        except ProcessLookupError:pass
        time.sleep(2)
        try:os.killpg(pid,signal.SIGKILL)
        except ProcessLookupError:pass
        pidfile.unlink()
    subprocess.run(['sudo','setfacl','--restore='+str(backup)],check=True)
    require(parse(snapshot())==parse(backup.read_text()),'Original ACL restoration mismatch')
    active.unlink()
    (pathlib.Path(os.environ['QA_OUT'])/'kvm-acl-restored.json').write_text(json.dumps({'status':'RESTORED','runId':data['runId']})+'\n')
def grant():
    require(os.environ.get('GITHUB_RUN_NUMBER')=='4' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','ACL authorization is limited to next run #4 attempt 1')
    require(os.environ.get('ALLOW_ONCE_KVM_ACL')=='true' and os.environ.get('QA_MODE')=='capture-only','Explicit one-run ACL input required')
    uid=os.getuid();require(uid!=0,'Nonroot runner required')
    st=os.stat(DEVICE);import stat
    require(stat.S_ISCHR(st.st_mode) and st.st_uid==0,'Existing root-owned KVM character device required')
    try:os.getxattr(DEVICE,'system.posix_acl_access')
    except OSError as e:require(e.errno==errno.ENODATA,'Filesystem ACL support not confirmed')
    backup,active=paths();require(not backup.exists() and not active.exists(),'Existing ACL state refused')
    raw=snapshot();original=parse(raw)
    require(set(original)=={'user:','group:','other:'},'Extended ACL refused')
    require(original['user:']=='rw-' and original['other:']=='---' and 'x' not in original['group:'],'Unexpected baseline permissions')
    backup.write_text(raw)
    # Set restore marker before mutation, including the failure path.
    active.write_text(json.dumps({'uid':uid,'runId':os.environ['GITHUB_RUN_ID']}))
    try:
        subprocess.run(['sudo','setfacl','-n','-m',f'u:{uid}:rw,m::rw',DEVICE],check=True)
        actual=parse(snapshot());expected=dict(original,**{f'user:{uid}':'rw-','mask:':'rw-'})
        require(actual==expected,'ACL change exceeds exact current-user grant')
        require(os.access(DEVICE,os.R_OK|os.W_OK),'Current user still cannot access KVM')
        (pathlib.Path(os.environ['QA_OUT'])/'kvm-acl-grant.json').write_text(json.dumps({'status':'GRANTED_THIS_RUN_ONLY','uid':uid,'runId':os.environ['GITHUB_RUN_ID'],'originalAcl':original,'newAcl':actual,'otherEffectivePermissionsUnchanged':True})+'\n')
    except BaseException:
        restore();raise
if __name__=='__main__':
    {'grant':grant,'restore':restore}[sys.argv[1]]()
