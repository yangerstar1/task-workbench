"""Validate the exact immutable R9 artifact before bounded reuse."""
import pathlib,sys,hashlib,json,zipfile
base=pathlib.Path(__file__).parent
locked=json.loads((base/'viewmodel-baseline.json').read_text())
archive=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2])
if archive.stat().st_size!=locked['zip_bytes'] or hashlib.sha256(archive.read_bytes()).hexdigest()!=locked['zip_sha256']:raise SystemExit('Source artifact ZIP identity mismatch')
with zipfile.ZipFile(archive) as z:
 if z.testzip():raise SystemExit('Source ZIP CRC failure')
 for item in z.infolist():
  p=pathlib.PurePosixPath(item.filename)
  if p.is_absolute() or '..' in p.parts:raise SystemExit('Unsafe archive path')
 z.extractall(out)
for name,expected in locked['files'].items():
 if hashlib.sha256((out/name).read_bytes()).hexdigest()!=expected:raise SystemExit('Pinned source file mismatch: '+name)
for line in (out/'SHA256SUMS').read_text().splitlines():
 digest,name=line.split('  ',1)
 if pathlib.PurePosixPath(name).name!=name or hashlib.sha256((out/name).read_bytes()).hexdigest()!=digest:raise SystemExit('Source manifest mismatch: '+name)
if (out/'source-commit.txt').read_text().strip()!=locked['source_commit']:raise SystemExit('Source commit mismatch')
print('Verified exact R9 ZIP, pinned asset/video/validation hashes, source commit and full original checksum manifest.')
