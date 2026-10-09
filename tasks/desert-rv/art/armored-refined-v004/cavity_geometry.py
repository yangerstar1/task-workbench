"""Shared original cavity geometry, independently testable without Blender."""
import math

def bowl_wall():
    n=32; verts=[]
    for rx,ry,bottom in ((.48,.35,False),(.365,.255,False),(.365,.255,True),(.48,.35,True)):
        for j in range(n):
            a=j*math.tau/n; x=rx*math.cos(a); y=.78+ry*math.sin(a)
            verts.append((x,y,.65 if bottom else .97-.30*(y-.55)))
    faces=[]
    for ring in range(4):
        nxt=(ring+1)%4
        for j in range(n):faces.append((ring*n+j,ring*n+(j+1)%n,nxt*n+(j+1)%n,nxt*n+j))
    return verts,faces

def bowl_floor():
    n=32; verts=[(.48*math.cos(j*math.tau/n),.78+.35*math.sin(j*math.tau/n),z) for z in (.65,.625) for j in range(n)]
    faces=[tuple(range(n)),tuple(reversed(range(n,2*n)))]+[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    return verts,faces

def core_disk():
    verts=[(0,.78,.902)]; faces=[]
    for rx,ry,lift in ((.14,.11,0),(.285,.205,-.012)):
        for j in range(32):
            a=j*math.tau/32; x=rx*math.cos(a); y=.78+ry*math.sin(a)
            verts.append((x,y,.902-.30*(y-.78)+lift+(.009 if j%4==0 else 0)))
    for j in range(32):faces.append((0,1+j,1+(j+1)%32)); faces.append((1+j,33+j,33+(j+1)%32,1+(j+1)%32))
    verts += [(x,y,z-.06) for x,y,z in verts[33:65]]
    for j in range(32):faces.append((33+j,65+j,65+(j+1)%32,33+(j+1)%32))
    faces.append(tuple(reversed(range(65,97))))
    return verts,faces

def cover(sign):
    sections=[(.405,.13,1.015),(.50,.375,1.045),(.69,.50,1.03),(.90,.45,.965),(1.145,.09,.865)]
    verts=[]
    for dz in (0,-.035):
        for y,w,z in sections:
            for u in (0,.45,1):verts.append((sign*(-.012+(w+.012)*u),y,z-.135*u*u+dz))
    n=len(sections)*3; faces=[]
    for layer in (0,n):
        for i in range(len(sections)-1):
            for j in range(2):
                a=layer+i*3+j; faces.append((a,a+1,a+4,a+3) if layer==0 else (a+3,a+4,a+1,a))
    border=[0,1,2]+[i*3+2 for i in range(1,len(sections))]+[n-2,n-3]+[i*3 for i in range(len(sections)-2,0,-1)]
    for a,b in zip(border,border[1:]+border[:1]):faces.append((a,b,b+n,a+n))
    return verts,faces
