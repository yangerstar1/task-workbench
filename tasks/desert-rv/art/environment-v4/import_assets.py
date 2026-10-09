"""Copy verified CC0 originals and derive a documented URP metallic-smoothness map.
This is offline image-data preparation, not Unity or Blender execution.
The source manifest records the exact original file bytes separately from derivations.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,uuid,re
from PIL import Image
BASE=Path(__file__).resolve().parents[2]
OUT=BASE/'unity/Assets/DesertRV/Art/EnvironmentV4'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',required=True,type=Path,help='Caller-provided directory containing the verified polyhaven and kenney_factory input folders')
IN=parser.parse_args().source.expanduser().resolve()
IDS=['aerial_sand','asphalt_02','concrete_floor_worn_001','rusty_metal_02','sand_03','painted_plaster_wall','corrugated_iron_03']
MODELS=['pipe-large-valve','pipe-large-bend','machine-bed','catwalk-stairs','catwalk-straight','hopper-square','crane-magnet']
NS=uuid.UUID('9cba2185-7059-4f5a-9b6f-6446d7bd7a31')
TEMPLATE=(BASE/'unity/Assets/DesertRV/Art/cabin-finish-normal.png.meta').read_text()
records=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def guid(p):return uuid.uuid5(NS,str(p.relative_to(BASE))).hex
def texture_meta(p,normal=False,linear=False):
 s=TEMPLATE.replace('cb5c8cd41cc4dff419616b765f0ef79d',guid(p))
 s=s.replace('sRGBTexture: 0','sRGBTexture: '+str(0 if normal or linear else 1))
 s=s.replace('textureType: 1','textureType: '+str(1 if normal else 0))
 s=s.replace('maxTextureSize: 2048','maxTextureSize: 1024').replace('maxTextureSize: 4096','maxTextureSize: 1024')
 s=s.replace('wrapU: 1','wrapU: 0').replace('wrapV: 1','wrapV: 0').replace('wrapW: 1','wrapW: 0')
 s=s.replace('aniso: 8','aniso: 4').replace('streamingMipmaps: 0','streamingMipmaps: 1')
 s=s.replace('textureCompression: 0','textureCompression: 1').replace('compressionQuality: 100','compressionQuality: 70')
 if linear:s=s.replace('alphaUsage: 0','alphaUsage: 1')
 p.with_suffix(p.suffix+'.meta').write_text(s)
def copy(src,dst,source_url,author,normal=False,linear=False):
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
 texture_meta(dst,normal,linear) if dst.suffix in ('.jpg','.png') else None
 records.append({'path':str(dst.relative_to(BASE)),'sha256':sha(dst),'bytes':dst.stat().st_size,'license':'CC0-1.0','source_url':source_url,'author':author,'source_filename':src.name,'modified':False})
OUT.mkdir(parents=True,exist_ok=True)
for id in IDS:
 author={'concrete_floor_worn_001':'Dimitrios Savva / Rico Cilliers','sand_03':'Charlotte Baglioni','painted_plaster_wall':'Amal Kumar','corrugated_iron_03':'Charlotte Baglioni'}.get(id,'Rob Tuytel')
 for suffix in ['diff','nor_gl']:
  src=IN/'polyhaven'/id/f'{id}_{suffix}_1k.jpg';copy(src,OUT/src.name,f'https://polyhaven.com/a/{id}',author,normal=suffix=='nor_gl')
 src=IN/'polyhaven'/id/f'{id}_rough_1k.jpg';rough=Image.open(src).convert('L')
 # Non-metals: R=0. Rust-coated metal is deliberately treated as dielectric; oxidation is not clean metal.
 # G/B = white, A = 1 - linear roughness. URP Lit consumes metallic R and smoothness A.
 metallic=Image.new('L',rough.size,0);white=Image.new('L',rough.size,255)
 dst=OUT/f'{id}_metallic_smoothness_1k.png';Image.merge('RGBA',(metallic,white,white,rough.point(lambda x:255-x))).save(dst)
 texture_meta(dst,linear=True)
 records.append({'path':str(dst.relative_to(BASE)),'sha256':sha(dst),'bytes':dst.stat().st_size,'license':'CC0-1.0','source_url':f'https://polyhaven.com/a/{id}','author':author,'source_filename':src.name,'source_sha256':sha(src),'modified':True,'derivation':'R=0, G=B=255, A=255-roughness. No color transform; stored linear. All oxidation treated as dielectric.'})
for id in MODELS:
 src=IN/'kenney_factory/Models/FBX format'/f'{id}.fbx';copy(src,OUT/'Factory'/src.name,'https://kenney.nl/assets/factory-kit','Kenney')
 # Stable import settings; no scripts mutate importers during protected scene-authoring.
 template=(BASE/'unity/Assets/DesertRV/Art/station-polish.fbx.meta').read_text()
 template=re.sub(r'guid: [0-9a-f]{32}', 'guid: '+guid(OUT/'Factory'/src.name),template, count=1)
 for before,after in [('materialImportMode: 1','materialImportMode: 0'),('meshCompression: 2','meshCompression: 0'),('generateSecondaryUV: 1','generateSecondaryUV: 0'),('animationType: 2','animationType: 0'),('importVisibility: 1','importVisibility: 0'),('importBlendShapes: 1','importBlendShapes: 0')]:template=template.replace(before,after)
 (OUT/'Factory'/(src.name+'.meta')).write_text(template)
tex=IN/'kenney_factory/Models/FBX format/Textures/colormap.png'
copy(tex,OUT/'Factory/colormap.png','https://kenney.nl/assets/factory-kit','Kenney')
shutil.copyfile(IN/'kenney_factory/License.txt',OUT/'Factory/LICENSE.txt')
(OUT/'LICENSES.md').write_text('''# Third-party Environment V4 assets\n\nPoly Haven material maps: CC0 1.0. See https://polyhaven.com/license and the per-asset source URLs, artist credits, exact SHA-256, and derivation records in asset-provenance.json. Commercial use, adaptation and redistribution permitted. Attribution is voluntary.\n\nKenney Factory Kit 3.0: CC0 1.0. Original LICENSE.txt is retained in Factory. Original models and atlas are copied unchanged. https://kenney.nl/assets/factory-kit\n\nThe retained original RV and previous self-authored assets have not been replaced.\n''')
(OUT/'asset-provenance.json').write_text(json.dumps({'schema':1,'copied_on':'2026-10-09','verification':'License pages reviewed and originals downloaded by asset researcher; individual bytes hashed here. Unity import and visual suitability remain pending.','assets':records},ensure_ascii=False,indent=2)+'\n')
for p in [OUT,*OUT.rglob('*')]:
 if p.name.endswith('.meta') or p.with_name(p.name+'.meta').exists():continue
 meta=p.with_name(p.name+'.meta')
 meta.write_text(f'fileFormatVersion: 2\nguid: {guid(p)}\n'+('folderAsset: yes\nDefaultImporter:\n' if p.is_dir() else 'DefaultImporter:\n')+'  externalObjects: {}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n')
print(f'Prepared {len(records)} verified/derived assets, {sum(r["bytes"] for r in records):,} bytes')
