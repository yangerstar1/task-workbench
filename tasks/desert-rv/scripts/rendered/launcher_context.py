#!/usr/bin/env python3
"""Private launcher snapshots; export equality/existence only, never profile contents."""
import hashlib,json,os,pathlib,sys
KEYS=('uid','effectiveUid','home','xdgConfig','xdgData','xdgCache','xdgRuntime','profileConfigRoot','profileDataRoot')
SCOPE='PRE_ACTIVATION_WRAPPER_VS_PRE_RAW_EDITOR_LAUNCHER'

def safe(path):
    p=pathlib.Path(path)
    if p.is_symlink() or any(x.is_symlink() for x in p.parents):raise ValueError()
    return p

def snapshot():
    home=os.environ.get('HOME');config=os.environ.get('XDG_CONFIG_HOME');data=os.environ.get('XDG_DATA_HOME')
    values=dict(uid=str(os.getuid()),effectiveUid=str(os.geteuid()),home=home,xdgConfig=config,xdgData=data,xdgCache=os.environ.get('XDG_CACHE_HOME'),xdgRuntime=os.environ.get('XDG_RUNTIME_DIR'),profileConfigRoot=config or (str(pathlib.Path(home)/'.config') if home else None),profileDataRoot=data or (str(pathlib.Path(home)/'.local/share') if home else None))
    result={}
    for key,value in values.items():
        exists=None if key in ('uid','effectiveUid') else bool(value and pathlib.Path(value).is_dir())
        result[key]=dict(digest=hashlib.sha256(json.dumps(value).encode()).hexdigest(),present=value is not None,exists=exists)
    return result

def empty():return dict(scope=SCOPE,status='UNAVAILABLE',fields={})
def compare(before,after):
    fields={}
    for key in KEYS:
        a=before[key];b=after[key]
        fields[key]=dict(equal=a['digest']==b['digest'],beforePresent=a['present'],afterPresent=b['present'],beforeExists=a['exists'],afterExists=b['exists'])
    return validate(dict(scope=SCOPE,status='OBSERVED',fields=fields))
def validate(value):
    if not isinstance(value,dict) or set(value)!={'scope','status','fields'} or value['scope']!=SCOPE:raise ValueError()
    if value['status']=='UNAVAILABLE':
        if value['fields']!={}:raise ValueError()
        return value
    if value['status']!='OBSERVED' or not isinstance(value['fields'],dict) or set(value['fields'])!=set(KEYS):raise ValueError()
    for key,item in value['fields'].items():
        if not isinstance(item,dict) or set(item)!={'equal','beforePresent','afterPresent','beforeExists','afterExists'}:raise ValueError()
        for name,v in item.items():
            if name.endswith('Exists') and key in ('uid','effectiveUid'):
                if v is not None:raise ValueError()
            elif type(v) is not bool:raise ValueError()
    return value

def load(path):
    try:
        p=safe(path)
        if p.stat().st_size>4096:raise ValueError()
        return validate(json.loads(p.read_text()))
    except Exception:return empty()
def main():
    try:
        operation,path=sys.argv[1:];root=safe(path)
        if operation=='before':
            out=root/'launcher-before.private.json';safe(out).write_text(json.dumps(snapshot()))
        elif operation=='after':
            before=safe(root/'launcher-before.private.json');out=safe(root/'launcher-context.json')
            if before.stat().st_size>4096:raise ValueError()
            out.write_text(json.dumps(compare(json.loads(before.read_text()),snapshot())))
        else:return 1
    except Exception:return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
