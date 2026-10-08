"""Dependency-free authoring contract. Metres, seconds, Blender Z-up, forward -Y.
Gameplay owns translation, collision and damage. Sampling does NOT inflict damage.
"""
import math, json
from pathlib import Path
P=json.loads((Path(__file__).resolve().parent/'parameters.json').read_text())
RAM_SECTIONS=[(0,-.77,.66,.28,.18),(0,-1.02,.61,.51,.19),(0,-1.30,.52,.61,.145),(0,-1.49,.48,.53,.070)]
SIDES = (("L", 1), ("R", -1))
LEGS = tuple(f"{p}.{s}" for p in ("fore", "hind") for s, _ in SIDES)
HIP = {k: ((.53 if k.endswith("L") else -.53), -.52 if k.startswith("fore") else .58, .69) for k in LEGS}
FOOT = {k: ((.76 if k.endswith("L") else -.76), -.63 if k.startswith("fore") else .70, .105) for k in LEGS}
UPPER = .47
LOWER = .47

def add(a,b): return tuple(x+y for x,y in zip(a,b))
def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def mul(a,s): return tuple(x*s for x in a)
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def length(a): return math.sqrt(dot(a,a))
def norm(a): return mul(a,1/max(length(a),1e-12))
def smooth(t):
    t=max(0,min(1,t)); return t*t*(3-2*t)
def mix(a,b,t): return a+(b-a)*t

def knee(hip,foot,key):
    """Exact two-link construction; rejects unreachable targets instead of stretching."""
    d=sub(foot,hip); r=length(d)
    if not 1e-6 < r < UPPER+LOWER-1e-5: raise ValueError((key,'unreachable',r))
    axis=norm(d); preferred=(0,1 if key.startswith('fore') else -1,0)
    bend=norm(sub(preferred,mul(axis,dot(preferred,axis))))
    along=(UPPER*UPPER-LOWER*LOWER+r*r)/(2*r)
    height=math.sqrt(max(0,UPPER*UPPER-along*along))
    return add(add(hip,mul(axis,along)),mul(bend,height))

def gait(t,key,speed,period):
    phase=(t/period+(0 if key in ('fore.L','hind.R') else .5))%1
    travel=speed*period*.5
    if phase<=.5:
        return (-travel/2+speed*period*phase,0,True)
    u=(phase-.5)*2
    return (mix(travel/2,-travel/2,smooth(u)),.14*math.sin(math.pi*u)**2,False)

def sample(clip,t):
    z=0.; gate=0.; ram=0.; feet={k:FOOT[k] for k in LEGS}; contact={k:True for k in LEGS}
    if clip=='Idle': z=.007*(1-math.cos(t*math.tau/2))
    elif clip=='Walk':
        z=.01*(1-math.cos(t*math.tau*2/P['walk_stride_seconds']))
        for k in LEGS:
            y,h,c=gait(t,k,P['walk_speed_mps'],P['walk_stride_seconds']); feet[k]=add(FOOT[k],(0,y,h)); contact[k]=c
    elif clip=='Windup':
        u=smooth((t-.55)/(P['clips']['Windup']-.55)); z=-.13*u; ram=-.12*u
        for k in LEGS:
            start=0 if k in ('fore.L','hind.R') else .25
            a=max(0,min(1,(t-start)/.30)); y,_,_=gait(0,k,P['charge_speed_mps'],P['charge_stride_seconds'])
            feet[k]=add(FOOT[k],(0,y*smooth(a),.08*math.sin(math.pi*a)**2)); contact[k]=a in (0,1)
    elif clip=='Attack':
        # Full-speed charge for the entire state. Only gameplay collision ends it.
        z=-.13+.025*math.sin(math.pi*t/P['charge_stride_seconds'])**2; ram=-.12
        for k in LEGS:
            y,h,c=gait(t,k,P['charge_speed_mps'],P['charge_stride_seconds']); feet[k]=add(FOOT[k],(0,y,h)); contact[k]=c
    elif clip=='Recover':
        # Gate stays open throughout the actual 2s gameplay vulnerability window.
        # Boundary gate changes are intentionally not disguised by premature opening/closing.
        u=smooth(t/P['weakpoint_seconds']); z=mix(-.13,-.18,smooth(t/.18)) if t<.18 else mix(-.18,0,smooth((t-.18)/(P['weakpoint_seconds']-.18)))
        gate=1.12; ram=mix(-.12,.04,smooth(t/.18)) if t<.18 else .04*(1-smooth((t-.18)/(P['weakpoint_seconds']-.18)))
        for k in LEGS:
            start=.20 if k in ('fore.L','hind.R') else .85
            a=max(0,min(1,(t-start)/.55)); y,_,_=gait(0,k,P['charge_speed_mps'],P['charge_stride_seconds'])
            feet[k]=add(FOOT[k],(0,y*(1-smooth(a)),.085*math.sin(math.pi*a)**2)); contact[k]=a in (0,1)
    elif clip=='Hit': z=-.065*math.sin(math.pi*min(t/P['clips']['Hit'],1))**2; ram=.10*math.sin(math.pi*min(t/P['clips']['Hit'],1))**2
    elif clip=='Death': z=P['death_settle_z']*smooth(t/.8); gate=1.12*smooth(t/.7); ram=.18*smooth(t/.6)
    else: raise ValueError(clip)
    return {'z':z,'gate':gate,'ram':ram,'feet':feet,'contact':contact}

def interrupted(phase,t):
    """Synthetic hard-stop settle from the EXACT sampled charge pose.
    Frozen world root. Airborne feet settle vertically, planted feet never slide.
    This is preview evidence, not an implemented Unity transition controller.
    """
    a=sample('Attack',phase); u=smooth(t/.24)
    out=dict(a); out['z']=mix(a['z'],-.18,u); out['gate']=mix(a['gate'],1.12,u)
    out['feet']={k:(v[0],v[1],mix(v[2],FOOT[k][2],u)) for k,v in a['feet'].items()}
    out['contact']={k: a['contact'][k] or t>=.24 for k in LEGS}
    return out

def travel(clip,t):
    return P['walk_speed_mps']*t if clip=='Walk' else P['charge_speed_mps']*t if clip=='Attack' else 0.
