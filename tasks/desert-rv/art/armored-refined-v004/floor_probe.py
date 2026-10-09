"""Exact rigid limb-vertex floor regression; no Blender import or execution."""
import math,sys,json
import motion as m
from pathlib import Path

def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def rot(v,a,b):
    a=m.norm(a);b=m.norm(b);k=cross(a,b);c=m.dot(a,b)
    return m.add(m.add(v,cross(k,v)),m.mul(cross(k,cross(k,v)),1/(1+c)))
def strut(a,b,r1,r2,sides=10):
    axis=m.norm(m.sub(b,a));helper=(0,0,1) if abs(axis[2])<.95 else (1,0,0);u=m.norm(cross(axis,helper));v=cross(axis,u)
    return [m.add(m.add(a,m.mul(m.sub(b,a),t)),m.mul(m.add(m.mul(u,math.cos(j*math.tau/sides)),m.mul(v,math.sin(j*math.tau/sides))),r)) for t,r in ((0,r1),(.12,r1*1.05),(.8,r2),(1,r2*.85)) for j in range(sides)]
def diagnose(pose,guard=True):
    rows=[]
    for k in m.LEGS:
        h,f=m.HIP[k],m.FOOT[k];n=m.knee(h,f,k)
        nh=m.add(h,(0,0,pose['z']));nf=pose['feet'][k];nn=m.knee(nh,nf,k,minimum_z=pose.get('knee_clearance') if guard else None)
        for name,vs,resth,restt,newh,newt in [('UpperArm',strut(h,n,.12,.10),h,n,nh,nn),('Greave',strut(n,f,.13,.085),n,f,nn,nf),('KneePin',strut(m.add(n,(-.10,0,0)),m.add(n,(.10,0,0)),.09,.09,12),n,f,nn,nf)]:
            points=[m.add(newh,rot(m.sub(v,resth),m.sub(restt,resth),m.sub(newt,newh))) for v in vs]
            i=min(range(len(points)),key=lambda i:points[i][2]);rows.append({'mesh':name+'_'+k,'bone':('upper.' if name=='UpperArm' else 'lower.')+k,'local_vertex':i,'rest_vertex':vs[i],'world_vertex':points[i],'min_z':points[i][2],'knee':nn,'ankle':nf,'body_z':pose['z']})
    return min(rows,key=lambda r:r['min_z'])
