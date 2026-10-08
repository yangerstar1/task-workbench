"""Postprocess Actions-rendered evidence. No model generation occurs here."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw
p=argparse.ArgumentParser(); p.add_argument('output'); args=p.parse_args()
out=Path(args.output); review=out/'review'
def sheet(files,destination,columns=4):
    cells=[]
    for path in files:
        im=Image.open(path).convert('RGB'); im.thumbnail((320,280))
        tile=Image.new('RGB',(320,310),(38,38,38)); tile.paste(im,((320-im.width)//2,10))
        ImageDraw.Draw(tile).text((10,290),path.parent.name+'/'+path.stem,fill=(235,235,235))
        cells.append(tile)
    result=Image.new('RGB',(columns*320,((len(cells)+columns-1)//columns)*310),(38,38,38))
    for i,im in enumerate(cells): result.paste(im,((i%columns)*320,(i//columns)*310))
    result.save(destination)
sheet(sorted(review.glob('turntable-*.png')),review/'turntable-contact-sheet.jpg')
for directory in sorted(review.iterdir()):
    if not directory.is_dir(): continue
    frames=sorted(directory.glob('*.png'))
    if not frames: continue
    subprocess.run(['ffmpeg','-y','-framerate','15','-i',str(directory/'%04d.png'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p',str(review/(directory.name+'.mp4'))],check=True)
    picks=[frames[round(i*(len(frames)-1)/7)] for i in range(8)]
    sheet(picks,review/(directory.name+'-contact-sheet.jpg'))
# Match the upload allowlist; raw animation-frame directories stay runner-local.
patterns=['*.blend','*.glb','*.fbx','*.json','*.png','source-commit.txt','blender-upstream.sha256',
          'review/*.mp4','review/*-contact-sheet.jpg','review/turntable-*.png']
files=sorted({p for pattern in patterns for p in out.glob(pattern) if p.is_file()})
(out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n' for p in files))
print(json.dumps({'files':len(files),'output':str(out),'visual_approval':False}))

early_patterns=['review/turntable-*.png','review/turntable-contact-sheet.jpg','static-review.json','pouncer-basecolor.png','source-commit.txt']
early=sorted({p for pattern in early_patterns for p in out.glob(pattern) if p.is_file()})
(out/'STATIC_SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(out))+'\n' for p in early))
