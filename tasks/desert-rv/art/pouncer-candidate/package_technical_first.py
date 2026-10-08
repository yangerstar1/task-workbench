import hashlib,sys
from pathlib import Path
out=Path(sys.argv[1]);mode=sys.argv[2]
if mode=='technical':
    files=sorted(p for p in out.glob('*') if p.is_file() and p.suffix in ('.blend','.glb','.fbx','.json','.txt'))
    name='SHA256SUMS'
else:
    files=sorted(list(out.glob('opaque-*.png'))+[out/'opaque-scope.json']);name='OPAQUE_SHA256SUMS'
    if len(files)!=5 or not all(p.is_file() for p in files):raise RuntimeError('Expected exactly four opaque images and scope')
(out/name).write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
