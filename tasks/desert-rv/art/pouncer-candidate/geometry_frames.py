"""Pure numeric rotation-minimizing section frames; no Blender or geometry creation.
Tests may execute here; asset construction remains Actions-only.
"""
import math

def add(a,b):return tuple(x+y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def mul(a,s):return tuple(x*s for x in a)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def unit(a):
    n=math.sqrt(dot(a,a))
    if n<1e-10:raise ValueError('Degenerate section centerline')
    return mul(a,1/n)
def rotate(v,axis,angle):
    c=math.cos(angle); s=math.sin(angle)
    return add(add(mul(v,c),mul(cross(axis,v),s)),mul(axis,dot(axis,v)*(1-c)))
def transport_frames(centers):
    if len(centers)<2:raise ValueError('At least two sections required')
    edges=[unit(sub(b,a)) for a,b in zip(centers,centers[1:])]
    tangents=[edges[0]]+[unit(add(a,b)) for a,b in zip(edges,edges[1:])]+[edges[-1]]
    first=tangents[0]; reference=(1,0,0) if abs(first[0])<.95 else (0,1,0)
    right=unit(sub(reference,mul(first,dot(reference,first))))
    up=unit(cross(right,first))
    # Pick orientation ONCE. Never independently flip a ring toward world-up.
    if up[2]<0:right=mul(right,-1); up=mul(up,-1)
    result=[(right,up,first)]
    for previous,current in zip(tangents,tangents[1:]):
        axis=cross(previous,current); sine=math.sqrt(dot(axis,axis)); cosine=max(-1,min(1,dot(previous,current)))
        if cosine<-.9999:raise ValueError('Centerline reverses; add intermediate anatomical sections')
        if sine>1e-10:right=rotate(right,mul(axis,1/sine),math.atan2(sine,cosine))
        right=unit(sub(right,mul(current,dot(right,current))))
        up=unit(cross(right,current)); result.append((right,up,current))
    return result
