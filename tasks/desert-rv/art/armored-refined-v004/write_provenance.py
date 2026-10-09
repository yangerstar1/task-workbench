"""Create run binding before generation. No private sources or environment dump."""
import argparse, hashlib, json, os
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(); p.add_argument('--root',required=True); p.add_argument('--workflow',required=True); a=p.parse_args(); root=Path(a.root).resolve()
if (root/'provenance.json').exists():raise ValueError('Refuse reused provenance')
manifest=json.loads((HERE/'source-manifest.json').read_text())
for name,digest in manifest['sha256'].items():
    if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=digest:raise ValueError('Source checksum mismatch '+name)
workflow=Path(a.workflow)
record={'source_commit':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],'run_attempt':os.environ['GITHUB_RUN_ATTEMPT'],'repository':os.environ['GITHUB_REPOSITORY'],'run_url':os.environ['GITHUB_SERVER_URL']+'/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],'source_manifest_sha256':hashlib.sha256((HERE/'source-manifest.json').read_bytes()).hexdigest(),'source_files':manifest['sha256'],'workflow_sha256':hashlib.sha256(workflow.read_bytes()).hexdigest(),'blender_distribution':'https://download.blender.org/release/Blender4.2/blender-4.2.3-linux-x64.tar.xz','blender_upstream_checksum_url':'https://download.blender.org/release/Blender4.2/blender-4.2.3.sha256','verified_binary_archive_checksum':(root/'blender-upstream.sha256').read_text().strip(),'private_reference_uploaded':False,'visual_approved':False,'unity_verified':False}
(root/'provenance.json').write_text(json.dumps(record,indent=2)+'\n')
