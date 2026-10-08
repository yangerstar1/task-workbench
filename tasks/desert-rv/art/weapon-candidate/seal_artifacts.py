"""Run only in a later workflow step, after Blender/tee/ffmpeg have exited."""
import hashlib,pathlib,sys
from asset_validation import delivered_file
folder=pathlib.Path(sys.argv[1])
if not folder.is_dir():raise SystemExit('No output directory to seal')
files=sorted(p for p in folder.iterdir() if delivered_file(p))
(folder/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
print(f'Sealed {len(files)} completed files; no producers are active.')
