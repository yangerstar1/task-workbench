#!/usr/bin/env python3
import base64, json, re, sys
from pathlib import Path

def validate(plan, width):
    assert plan.get('status') == 'reviewed', 'Screenshot review required'
    s=plan['screens'][str(width)+'x720']
    assert re.fullmatch('[a-f0-9]{64}',s['sourceScreenshotSha256']), 'Source PNG hash required'
    assert re.fullmatch('[1-9][0-9]*',s['captureRunId']), 'Capture run required'
    assert type(s['intervalMs']) is int and 16 <= s['intervalMs'] <= 100
    assert type(s['frames']) is list and 2 <= len(s['frames']) <= 120
    for frame in s['frames']:
        assert len(frame)==2
        for point in frame:
            assert len(point)==2
            assert all(type(v) in (int,float) for v in point)
            assert 0 <= point[0] < width and 0 <= point[1] < 720
    return dict(width=width,height=720,intervalMs=s['intervalMs'],frames=s['frames'])
if __name__=='__main__':
    width=int(sys.argv[1]); assert width in (1280,1600)
    plan=json.loads(Path(__file__).with_name('coordinates.json').read_text())
    print(base64.b64encode(json.dumps(validate(plan,width),separators=(',',':')).encode()).decode())
