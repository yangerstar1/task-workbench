"""Fixed bounded plan; original 60Hz frame numbers never retimed."""
import json
from pathlib import Path
ART=Path(__file__).resolve().parent.parent/'armored-refined-v004'
P=json.loads((ART/'parameters.json').read_text())
REMAINING=['Idle','Walk','Windup','Attack','Recover','Hit','Death','SYNTHETIC_Interrupt_0.07','SYNTHETIC_Interrupt_0.42','SYNTHETIC_Interrupt_0.91']
REUSED=[]
def count(clip):
    if clip in P['clips']: duration=P['clips'][clip]
    elif clip in REMAINING:duration=min(.35,float(clip.rsplit('_',1)[1]))+.6
    else:raise ValueError('Unknown clip')
    return round(duration*P['fps'])+1

def frames(clip):
    n=count(clip); result=list(range(1,n+1,2))
    if result[-1]!=n:result.append(n)
    return result

def chunks(clip):
    result=frames(clip)
    return [result[i:i+24] for i in range(0,len(result),24)]

def matrix():return [{'clip':c,'chunk':i,'frames':f} for c in REMAINING for i,f in enumerate(chunks(c))]
if __name__=='__main__':print(json.dumps({'include':matrix()},separators=(',',':')))
