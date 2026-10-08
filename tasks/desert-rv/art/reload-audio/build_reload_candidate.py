#!/usr/bin/env python3
"""Small standard-library-only candidate producer for the existing public Actions workflow."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
TASK = HERE.parents[1]
REPO = TASK.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REPOSITORY') != 'yangerstar1/task-workbench':
        raise SystemExit('Use the approved public task-workbench Actions workflow.')
    manifest_path = HERE / 'source-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for item in manifest['preserved_existing_audio']:
        actual = hashlib.sha256((REPO / item['path']).read_bytes()).hexdigest()
        if actual != item['sha256']:
            raise SystemExit('Existing sound changed; review new baseline before generating: ' + item['path'])
    for item in manifest['candidate_source_files']:
        if hashlib.sha256((REPO / item['path']).read_bytes()).hexdigest() != item['sha256']:
            raise SystemExit('Candidate source manifest mismatch: ' + item['path'])
    if args.output.exists():
        raise SystemExit('Candidate output must be a new directory; nothing will be overwritten.')
    args.output.mkdir(parents=True)
    generator = TASK / 'art/scripts/make_reload_foley.py'
    output = args.output / 'reload.wav'
    repeat = args.output / 'repeat/reload.wav'
    for path in (output, repeat):
        subprocess.run([sys.executable, str(generator), '--output', str(path)], check=True)
    subprocess.run([sys.executable, str(HERE / 'validate_reload.py'), '--wav', str(output),
                    '--repeat-wav', str(repeat), '--generator', str(generator),
                    '--report', str(args.output / 'audio-analysis.json'),
                    '--expected-commit', os.environ['GITHUB_SHA'],
                    '--expected-run', os.environ['GITHUB_RUN_ID']], check=True)
    # Only a generated artifact, never an approval or an automatic production import.
    status = {'source_commit': os.environ['GITHUB_SHA'], 'github_run_id': os.environ['GITHUB_RUN_ID'],
              'wav_generated': True, 'objective_audio_validation_passed': True,
              'file': 'reload.wav', 'candidate_only': True, 'auditioned': False,
              'unity_import_verified': False, 'visual_sync_approved': False,
              'commercial_quality_approved': False, 'preserved_existing_audio_count': 9,
              'target_after_review': 'Assets/DesertRV/Audio/reload.wav',
              'source_manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    (args.output / 'generation-status.json').write_text(json.dumps(status, indent=2) + '\n')
    (args.output / 'source-manifest.json').write_bytes(manifest_path.read_bytes())
    (args.output / 'reload.wav.meta').write_bytes((HERE / 'reload.wav.meta').read_bytes())
    files = sorted(p for p in args.output.iterdir() if p.is_file() and p.name != 'SHA256SUMS')
    (args.output / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in files))


if __name__ == '__main__':
    main()
