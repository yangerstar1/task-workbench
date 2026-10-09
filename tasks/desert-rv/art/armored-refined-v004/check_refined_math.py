"""Pure numeric source-envelope check, NOT Blender/Unity evaluation or crossfade acceptance."""
import json,math
import numpy as np
import motion,refined_geometry as g,cavity_geometry as c
from pathlib import Path
P=json.loads(Path(__file__).with_name('parameters.json').read_text())
parts=g.build(motion)
for name,geom in [('rim',c.bowl_wall()),('floor',c.bowl_floor()),('core',g.core_geometry())]:parts.append(dict(name=name,verts=geom[0],faces=geom[1],bone='body'))
rest={k:(np.array(motion.HIP[k]),np.array(motion.knee(motion.HIP[k],motion.FOOT[k],k)),np.array(motion.FOOT[k])) for k in motion.LEGS}
bybone={}
for p in parts:bybone.setdefault(p['bone'],[]).extend(p['verts'])
bybone={b:np.array(v) for b,v in bybone.items()}
def rotate(v,a,b):
    a=a/np.linalg.norm(a);b=b/np.linalg.norm(b);cross=np.cross(a,b);dot=float(np.dot(a,b));skew=np.array([[0,-cross[2],cross[1]],[cross[2],0,-cross[0]],[-cross[1],cross[0],0]])
    assert dot>-.99999
    return v@(np.eye(3)+skew+skew@skew/(1+dot)).T
reports=[]
for clip,duration in P['clips'].items():
    worst={'z':100,'clip':clip}
    for frame in range(round(duration*240)+1):
        pose=motion.sample(clip,frame/240);shift=np.array([0,0,pose['z']]);transformed={}
        for bone,vs in bybone.items():
            if bone=='body':out=vs+shift
            elif bone=='ram':
                a=pose['ram'];r=np.array([[1,0,0],[0,math.cos(a),-math.sin(a)],[0,math.sin(a),math.cos(a)]]);pivot=np.array([0,-.79,.66]);out=(vs-pivot)@r.T+pivot+shift
            else:
                kind,k=bone.split('.',1);h,n,f=rest[k];hh=h+shift;ff=np.array(pose['feet'][k]);nn=np.array(motion.knee(hh,ff,k,minimum_z=pose.get('knee_clearance')))
                if kind=='upper':out=rotate(vs-h,n-h,nn-hh)+hh
                elif kind=='lower':out=rotate(vs-n,f-n,ff-nn)+nn
                else:out=vs+ff-f
            z=float(out[:,2].min())
            if z<worst['z']:worst=dict(z=z,clip=clip,frame=frame,bone=bone,vertex=int(out[:,2].argmin()))
        for sign in (-1,1):
            vs=np.array(g.cover_geometry(sign,c)[0]);pivot=np.array([sign*.48,.78,.86]);a=sign*pose['gate'];r=np.array([[math.cos(a),0,math.sin(a)],[0,1,0],[-math.sin(a),0,math.cos(a)]]);out=(vs-pivot)@r.T+pivot+shift;z=float(out[:,2].min())
            if z<worst['z']:worst=dict(z=z,clip=clip,frame=frame,bone='runtime-plate-'+str(sign),vertex=int(out[:,2].argmin()))
    reports.append(worst)
print(json.dumps({'scope':'source geometry transforms only; no Unity local-TRS blend','hz':240,'worst':reports,'passed':all(r['z']>=-.004 for r in reports)},indent=2))
raise SystemExit(0 if all(r['z']>=-.004 for r in reports) else 1)
