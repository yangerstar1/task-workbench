"""Read-only source contract guard; does not execute C#, Unity or Blender."""
import argparse, hashlib, json, re
from pathlib import Path
P=json.loads((Path(__file__).resolve().parent/'parameters.json').read_text())
def validate(path):
    source=Path(path).read_text(); checks={
        'walk_speed_mps':r'MoveToward\(target,\s*armored\s*\?\s*([\d.]+)f',
        'charge_speed_mps':r'attackDirection\s*\*\s*\(armored\s*\?\s*([\d.]+)',
        'windup_seconds':r'phaseTime\s*>=\s*\(armored\s*\?\s*([\d.]+)f',
        'charge_timeout_seconds':r'attackClock\s*>\s*\(armored\s*\?\s*([\d.]+)f',
        'weakpoint_seconds':r'TryBeginRecovery\([^;]+armored\s*\?\s*([\d.]+)',
        'hit_seconds':r'BeastPhase.Hit\s*\?\s*([\d.]+)f'}
    observed={}
    for key,pattern in checks.items():
        match=re.search(pattern,source)
        if not match: raise ValueError('Runtime contract pattern not found: '+key)
        observed[key]=float(match.group(1))
        if observed[key]!=P['runtime_contract'][key]: raise ValueError('Runtime mismatch: '+key)
    return {'status':'source_contract_matches','actor_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'observed':observed,'not_verified':['Unity playback','collision interrupt transition','gate CrossFade appearance','variable-speed home/tangent paths']}
if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--actor',required=True); args=parser.parse_args(); print(json.dumps(validate(args.actor),indent=2))
