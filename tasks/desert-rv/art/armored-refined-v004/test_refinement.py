import ast,hashlib,json,unittest,math
from collections import Counter
from pathlib import Path
import refined_geometry as g,cavity_geometry as c,motion,surface_atlas
HERE=Path(__file__).resolve().parent
class RefinedSourceTests(unittest.TestCase):
 def test_every_closed_part_is_manifold(self):
  parts=g.build(motion)+[dict(name='core',verts=g.core_geometry()[0],faces=g.core_geometry()[1])]+[dict(name='door'+str(s),verts=g.cover_geometry(s,c)[0],faces=g.cover_geometry(s,c)[1]) for s in (-1,1)]
  for p in parts:
   edges=Counter(tuple(sorted((a,b))) for f in p['faces'] for a,b in zip(f,f[1:]+f[:1]));self.assertTrue(all(n==2 for n in edges.values()),p['name'])
   self.assertTrue(all(math.isfinite(n) for v in p['verts'] for n in v))
 def test_budget_and_semantic_detail(self):
  parts=g.build(motion);tris=sum(sum(len(f)-2 for f in p['faces']) for p in parts)
  self.assertLess(tris+2000,18000);names=[p['name'] for p in parts]
  for role in ('ShellRolledRim','ShellPaintCrown','KneeBearing','ShinCylinder','InstepPlate','ToeShoe','SoleTread'):self.assertTrue(any(n.startswith(role) for n in names),role)
 def test_animation_is_unchanged(self):
  self.assertEqual(hashlib.sha256((HERE/'motion.py').read_bytes()).hexdigest(),'4edc78bd7ff6ec22d8ad378a71871f983f76262857c8bf9cec03a06f8ed7e010')
 def test_physical_material_values(self):
  for tile in range(8):
   for u,v in ((0,0),(.5,.5),(1,1),(.1,.9)):
    rgb,orm=surface_atlas.texel(tile,u,v,(.5,.3,.1));self.assertTrue(all(0<=x<=1 for x in (*rgb,*orm)))
 def test_cc0_file_is_pinned(self):
  d=json.loads((HERE/'materials/ASSET-LICENSE.json').read_text());self.assertEqual(d['license'],'CC0-1.0');self.assertEqual(hashlib.sha256((HERE/'materials'/d['file']).read_bytes()).hexdigest(),d['sha256'])
 def test_syntax_and_no_network_execution(self):
  for f in HERE.glob('*.py'):ast.parse(f.read_text(),filename=f.name)
  for n in ('refined_geometry.py','surface_atlas.py','generate.py'):
   s=(HERE/n).read_text()
   for call in ('requests.','urllib.','os.system(','subprocess.'):self.assertNotIn(call,s)
 def test_texture_and_review_dimensions_are_distinct(self):
  from package_evidence import validate_png_dimensions
  for name in ('bulwark-basecolor.png','bulwark-orm.png'):
   validate_png_dimensions(name,1024,1024)
   for size in ((512,512),(960,540)):
    with self.assertRaises(ValueError):validate_png_dimensions(name,*size)
  validate_png_dimensions('review/static-01.png',960,540)
  with self.assertRaises(ValueError):validate_png_dimensions('review/static-01.png',1024,1024)
  with self.assertRaises(ValueError):validate_png_dimensions('unknown.png',1024,1024)
 def test_core_stays_below_unchanged_closed_lids(self):
  tris=[]
  for sign in (-1,1):
   verts,faces=c.cover(sign)
   for face in faces:
    tris.extend([verts[i] for i in (face[0],face[j],face[j+1])] for j in range(1,len(face)-1))
  gaps=[]
  for x,y,z in g.core_geometry()[0]:
   hits=[]
   for a,b,d in tris:
    bx,by=b[0]-a[0],b[1]-a[1];dx,dy=d[0]-a[0],d[1]-a[1];det=bx*dy-dx*by
    if abs(det)<1e-10:continue
    u=((x-a[0])*dy-(y-a[1])*dx)/det;v=(bx*(y-a[1])-by*(x-a[0]))/det
    if u>=-1e-8 and v>=-1e-8 and u+v<=1+1e-8:
     height=a[2]+u*(b[2]-a[2])+v*(d[2]-a[2])
     if height>z:hits.append(height-z)
   self.assertTrue(hits);gaps.append(min(hits))
  self.assertGreaterEqual(min(gaps),.010)
 def test_steel_and_paint_have_separate_roughness(self):
  _,paint=surface_atlas.texel(0,.5,.5,(.5,.3,.1));_,steel=surface_atlas.texel(6,.5,.5,(.5,.3,.1))
  self.assertGreater(paint[1]-steel[1],.20);self.assertEqual(paint[2],0);self.assertGreaterEqual(steel[2],.85)
if __name__=='__main__':unittest.main()
