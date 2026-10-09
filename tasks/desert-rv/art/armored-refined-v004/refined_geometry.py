"""Original v004 geometry. Pure Python, no engine, external asset or process calls.
Every part keeps a single declared owner bone; foot vertices remain rigid.
"""
import math

def loft(sections,sides=16):
    v=[(x+w*math.cos(j*math.tau/sides),y,z+h*math.sin(j*math.tau/sides)) for x,y,z,w,h in sections for j in range(sides)]
    f=[(i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j) for i in range(len(sections)-1) for j in range(sides)]
    return v,[tuple(reversed(range(sides)))]+f+[tuple((len(sections)-1)*sides+j for j in range(sides))]

def tube(a,b,r1,r2,sides=12):
    def sub(x,y):return tuple(i-j for i,j in zip(x,y))
    def cross(x,y):return (x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0])
    def unit(x):n=math.sqrt(sum(t*t for t in x));return tuple(t/n for t in x)
    axis=unit(sub(b,a));u=unit(cross(axis,(0,0,1) if abs(axis[2])<.95 else (1,0,0)));w=cross(axis,u)
    sections=[(0,r1*.84),(.08,r1),(.88,r2),(1,r2*.84)]
    v=[tuple(a[k]+(b[k]-a[k])*t+r*(u[k]*math.cos(j*math.tau/sides)+w[k]*math.sin(j*math.tau/sides)) for k in range(3)) for t,r in sections for j in range(sides)]
    f=[(i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j) for i in range(3) for j in range(sides)]
    return v,[tuple(reversed(range(sides)))]+f+[tuple(3*sides+j for j in range(sides))]

def build(motion):
    parts=[]
    def emit(name,geometry,bone,tile):parts.append(dict(name=name,verts=geometry[0],faces=geometry[1],bone=bone,tile=tile))
    def L(name,sections,bone,tile,sides=16):emit(name,loft(sections,sides),bone,tile)
    def T(name,a,b,r1,r2,bone,tile,sides=12):emit(name,tube(a,b,r1,r2,sides),bone,tile)
    def add(p,q):return tuple(a+b for a,b in zip(p,q))
    def lerp(a,b,t):return tuple(x+(y-x)*t for x,y in zip(a,b))
    L('Thorax_Undershell',[(0,-.94,.66,.29,.17),(0,-.65,.72,.57,.26),(0,-.1,.74,.60,.28),(0,.54,.70,.52,.23),(0,.94,.63,.29,.14)],'body',3,20)
    # Three pressed salvage shells: dark rolled lip under painted crown, nested curved sections.
    for i,(y,w,z) in enumerate([(-.55,.62,.91),(-.13,.67,1.),(.29,.62,.97)]):
        sections=[(0,y-.25,z-.025,w*.70,.035),(0,y-.20,z+.015,w*.92,.085),(0,y-.12,z+.025,w,.105),(0,y+.09,z,w*.96,.10),(0,y+.19,z-.065,w*.78,.065),(0,y+.24,z-.09,w*.68,.026)]
        L('ShellRolledRim_%d'%i,sections,'body',6,20)
        L('ShellPaintCrown_%d'%i,[(x,yy,zz+.009,ww*.950,hh*.94) for x,yy,zz,ww,hh in sections],'body',0 if i!=1 else 1,20)
        # Broad spinal reinforcement instead of isolated triangular spikes.
        L('ShellSpine_%d'%i,[(0,y-.19,z+.10,.07,.015),(0,y-.08,z+.14,.085,.025),(0,y+.08,z+.12,.074,.022),(0,y+.17,z+.055,.05,.012)],'body',6,10)
        for sign in (-1,1):
            # Two deliberate fasteners per panel, large enough to read at medium range.
            for off in (-.10,.09):
                a=(sign*w*.71,y+off,z+.066);T('ShellAnchor_%d_%s_%s'%(i,sign,off),a,add(a,(0,0,.025)),.026,.025,'body',6,8)
    # Side ventilation gives the creature a mechanical core under protective layers.
    for sign in (-1,1):
        for i in range(5):
            y=-.43+i*.17
            T('CoolingLouvre_%s_%d'%(sign,i),(sign*.565,y,.69),(sign*.59,y,.84),.022,.024,'body',2,8)
        L('FlankSill_'+str(sign),[(sign*.48,-.75,.63,.032,.03),(sign*.60,-.45,.63,.043,.035),(sign*.60,.26,.62,.04,.03),(sign*.46,.60,.61,.028,.024)],'body',6,10)
    L('ChiselRam',motion.RAM_SECTIONS,'ram',0,16)
    for sign in (-1,1):
        L('RamBladeRail_'+str(sign),[(sign*.37,-1.02,.63,.04,.045),(sign*.40,-1.35,.51,.045,.037),(sign*.37,-1.55,.45,.018,.018)],'ram',6,12)
        L('EyeRecess_'+str(sign),[(sign*.44,-.89,.76,.10,.043),(sign*.46,-1.03,.735,.085,.032)],'ram',7,12)
        L('AmberEye_'+str(sign),[(sign*.473,-.92,.775,.023,.018),(sign*.478,-1.005,.755,.023,.016)],'ram',4,12)
        # Ram nose has protected intake slits, not painted-on face marks.
        for j in range(3):
            y=-1.05-j*.10;T('RamIntake_%s_%d'%(sign,j),(sign*.21,y,.64-j*.055),(sign*.29,y,.64-j*.055),.016,.016,'ram',2,8)
    for k in motion.LEGS:
        h,f=motion.HIP[k],motion.FOOT[k];n=motion.knee(h,f,k);upper='upper.'+k;lower='lower.'+k;foot='foot.'+k
        # Joint axis, inset bearing cap, telescoped structural links: all within original radial envelope.
        T('UpperLink_'+k,h,n,.087,.076,upper,2,16)
        T('UpperPaintShroud_'+k,lerp(h,n,.14),lerp(h,n,.79),.109,.09,upper,0,16)
        T('KneeBearing_'+k,add(n,(-.10,0,0)),add(n,(.10,0,0)),.088,.088,lower,2,16)
        for sign in (-1,1):
            T('KneeHub_'+k+str(sign),add(n,(sign*.097,0,0)),add(n,(sign*.113,0,0)),.062,.055,lower,6,12)
        T('ShinCylinder_'+k,lerp(n,f,.07),lerp(n,f,.88),.077,.056,lower,6,16)
        T('ShinPaintGuard_'+k,lerp(n,f,.16),lerp(n,f,.72),.103,.071,lower,0,16)
        # A narrow outside link creates a readable channel without crossing bones/limbs.
        offset=(.05,0,0)
        T('ShinReturnLink_'+k,add(lerp(n,f,.22),offset),add(lerp(n,f,.70),offset),.025,.019,lower,2,10)
        x,y,z=f
        L('HeelRubber_'+k,[(x,y+.16,.065,.105,.048),(x,y+.06,.060,.144,.054),(x,y-.13,.056,.141,.05),(x,y-.20,.05,.108,.044)],foot,7,16)
        L('InstepPlate_'+k,[(x,y+.14,.108,.082,.027),(x,y+.02,.118,.135,.034),(x,y-.12,.095,.135,.027),(x,y-.19,.072,.092,.020)],foot,0,16)
        for j,dx in enumerate((-.088,0,.088)):
            L('ToeShoe_%s_%d'%(k,j),[(x+dx,y-.12,.063,.032,.024),(x+dx,y-.22,.049,.034,.033),(x+dx,y-.285,.035,.026,.029)],foot,6,12)
        # Two tread bridges visible in profile, minimum world rest Z remains >=.005.
        for off in (-.07,.08):
            T('SoleTread_'+k+str(off),(x-.112,y+off,.027),(x+.112,y+off,.027),.018,.018,foot,2,10)
    return parts

def core_geometry():
    # Core raised 20mm inside unchanged lid; domed reactor with six separated lobes; one rigid renderer/material slot.
    # Dark static radiator hardware is kept on the body, never included in the emissive renderer.
    verts=[];faces=[]
    for sector in range(6):
        start=sector*math.tau/6+.045; end=(sector+1)*math.tau/6-.045;base=len(verts)
        for ring in range(3):
            r=(.22,.65,1)[ring]
            for j in range(6):
                a=start+(end-start)*j/5;x=.268*r*math.cos(a);y=.78+.185*r*math.sin(a)
                verts.append((x,y,.916-.30*(y-.78)+(.012,.009,-.010)[ring]))
        for i in range(2):
            for j in range(5):q=base+i*6+j;faces.append((q,q+1,q+7,q+6))
        top=list(range(base,base+6))+[base+6,base+12]+list(range(base+13,base+18))+[base+11,base+5]
        # Explicit boundary of the 3x6 grid, closed with a recessed backing skin.
        boundary=list(range(base,base+6))+[base+11,base+17]+list(range(base+16,base+11,-1))+[base+6]
        lower=len(verts)
        verts.extend((verts[i][0],verts[i][1],verts[i][2]-.035) for i in boundary)
        faces.append(tuple(reversed(range(lower,len(verts)))))
        for i,a in enumerate(boundary):b=boundary[(i+1)%len(boundary)];faces.append((a,b,lower+(i+1)%len(boundary),lower+i))
    return verts,faces

def cover_geometry(sign,cavity):
    verts,faces=cavity.cover(sign)
    # Integral underside pressed ribs; they follow the runtime-owned door, not an animator bone.
    for y,w,z in ((.57,.40,.965),(.81,.43,.94),(1.01,.25,.884)):
        a=(sign*.055,y,z-.038);b=(sign*w,y,z-.080)
        rv,rf=tube(a,b,.018,.018,8);offset=len(verts);verts.extend(rv);faces.extend(tuple(offset+i for i in f) for f in rf)
    return verts,faces
