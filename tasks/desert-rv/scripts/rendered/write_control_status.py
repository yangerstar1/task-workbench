#!/usr/bin/env python3
# Fixed enums and explicit safe files only; never expose container-private logs or credential state.
import json,os,pathlib,re,sys
from guard_export import CODES
base=pathlib.Path('/github/workspace/tasks/desert-rv');allowed={'NOT_ATTEMPTED','SUCCEEDED','FAILED'}
if len(sys.argv)!=5 or not all(x in allowed for x in sys.argv[1:]):raise SystemExit(1)
report=dict(mode='RENDERED_CONTROL_ONLY_NOT_ACCEPTANCE',activation=sys.argv[1],licenseReturn=sys.argv[2],renderProcess=sys.argv[3],privateCleanup=sys.argv[4],captureFailureCode='UNAVAILABLE')
try:
    p=base/'rendered-private-evidence/capture-receipt.json'
    if not p.is_symlink() and not any(x.is_symlink() for x in p.parents):
        value=json.loads(p.read_text()).get('failureCode');report['captureFailureCode']=value if value in CODES else 'NONE' if value is None else 'UNAVAILABLE'
except Exception:pass
out=base/'rendered-control-export';out.mkdir(exist_ok=True);os.chmod(out,0o755)
p=out/'status.json';p.write_text(json.dumps(report)+'\n');os.chmod(p,0o644)
if json.loads(p.read_text())!=report:raise SystemExit(1)
export=base/'rendered-export'
if export.is_dir() and not export.is_symlink():
    files=list(export.iterdir())
    if all(p.is_file() and not p.is_symlink() and (p.name in {'diagnostic-summary.json','export-sha256.json','real-time.mp4'} or re.fullmatch(r'frame-[0-9]{8,}\.png',p.name)) for p in files):
        for p in files:os.chmod(p,0o644)
        os.chmod(export,0o755)
