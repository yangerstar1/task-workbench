"""Offline fail-closed stage from a separately authorized Actions artifact download.
Never downloads, runs Blender/Unity, edits production assets or sets review approvals.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

REPO = 'yangerstar1/task-workbench'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def require(condition, message):
    if not condition:
        raise ValueError(message)

def relative(value):
    require(isinstance(value, str) and value and '\\' not in value and ':' not in value,
            'Invalid relative filename')
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(s not in ('', '.', '..') for s in value.split('/')), 'Unsafe artifact path')
    return path

def verify(contract, run, artifact, archive):
    require(contract['schema'] == 1, 'Unsupported contract')
    mode=contract.get('mode'); scope=contract.get('scope')
    require(mode in ('DISCOVERY_ONLY','STRICT_BINDING'), 'Explicit import mode required')
    require(scope in ('FULL_CANDIDATE','DEATH_DIAGNOSTIC_NOT_FULL','PARTIAL_DIAGNOSTIC_NOT_FULL'), 'Explicit source scope required')
    if mode=='STRICT_BINDING':
        require(scope=='FULL_CANDIDATE', 'Partial diagnostic cannot enter strict binding')
    else:
        require(not any(key in contract for key in ('bindings','clips','materials')), 'Discovery cannot contain strict binding keys')
    require(contract['repository'] == REPO, 'Repository mismatch')
    require(re.fullmatch(r'[a-f0-9]{40}', contract['sourceCommit']), 'Exact source SHA required')
    require(run['repository']['full_name'] == REPO and run['head_sha'] == contract['sourceCommit'], 'Run source mismatch')
    require(run['status'] == 'completed' and run['conclusion'] == 'success', 'Generation run did not succeed')
    require(contract['runUrl'] == f'https://github.com/{REPO}/actions/runs/{run["id"]}', 'Run URL mismatch')
    require(artifact['name'] == contract['artifactName'] and not artifact['expired'], 'Wrong/expired artifact')
    require(artifact['workflow_run']['id'] == run['id'] and artifact['workflow_run']['head_sha'] == contract['sourceCommit'], 'Artifact run/source mismatch')
    require(digest(archive.read_bytes()) == contract['artifactSha256'], 'Archive hash mismatch')
    # GitHub supplied digest is mandatory: caller cannot just relabel a local ZIP.
    require(artifact.get('digest') == 'sha256:' + contract['artifactSha256'], 'GitHub artifact digest missing or mismatched')
    require(contract['files'] and len({f['file'].casefold() for f in contract['files']}) == len(contract['files']), 'Duplicate/case-colliding inputs')
    for file in contract['files']:
        relative(file['file'])
        require(PurePosixPath(file['file']).suffix.lower() in {'.fbx', '.png', '.tga'}, 'Unsupported payload type')
        require(re.fullmatch(r'[a-f0-9]{64}', file['sha256']), 'Exact file SHA required')

def stage(contract_path, run_path, artifact_path, archive, output):
    contract = json.loads(contract_path.read_text())
    run = json.loads(run_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    verify(contract, run, artifact, archive)
    require(not output.exists(), 'Never overwrite staged inputs')
    approved = {f['file']: f['sha256'] for f in contract['files']}
    payload = {}
    with zipfile.ZipFile(archive) as z:
        names = [i.filename for i in z.infolist()]
        require(len({n.casefold() for n in names}) == len(names), 'Duplicate ZIP entries')
        # Validate ALL paths even though only allowlisted model/texture files are copied.
        for info in z.infolist():
            relative(info.filename.rstrip('/'))
            require(not stat.S_ISLNK(info.external_attr >> 16), 'Symlink ZIP entry')
            require(not info.flag_bits & 1, 'Encrypted ZIP unsupported')
            require(info.file_size <= 512 * 1024 * 1024, 'Artifact member too large')
        for name, sha in approved.items():
            data = z.read(name)
            require(digest(data) == sha, 'Payload hash mismatch: ' + name)
            payload[name] = data
    output.mkdir(parents=True)
    for name, data in payload.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return {'status': 'staged-not-imported-or-reviewed', 'mode': contract['mode'], 'scope': contract['scope'], 'sourceCommit': contract['sourceCommit'],
            'runUrl': contract['runUrl'], 'artifactName': contract['artifactName'],
            'contractSha256': digest(contract_path.read_bytes()), 'files': sorted(payload)}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for key in ('contract', 'run', 'artifact', 'archive', 'output'):
        p.add_argument('--' + key, type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(stage(args.contract, args.run, args.artifact, args.archive, args.output), indent=2))
