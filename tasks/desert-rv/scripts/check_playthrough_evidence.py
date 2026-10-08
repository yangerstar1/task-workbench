#!/usr/bin/env python3
"""Fail-closed evidence inspection. Never treats a plan end or test count as acceptance."""
import argparse, json, pathlib, sys

def inspect(rows):
    samples = [r for r in rows if r.get('kind') == 'sample']
    errors = []
    def need(ok, text):
        if not ok: errors.append(text)
    need(bool(samples), 'No runtime samples')
    if not samples: return errors, {}
    need(any(r.get('kind') == 'stop' for r in rows), 'Missing terminal recorder event')
    need(not any(r.get('kind') == 'input-rejected' for r in rows), 'Rejected input requires investigation')
    generations = sorted({s['generation'] for s in samples if s['generation'] > 0})
    successful = []
    for generation in generations:
        run = [s for s in samples if s['generation'] == generation]
        if run[-1]['status'] == 'Completed': successful.append(run)
    need(bool(successful), 'No genuinely completed recorded generation')
    active, idle = 0., 0.
    activity_seconds = {}
    need(any(s['status'] == 'Paused' for s in samples), 'No pause scenario recorded')
    need(any(s['status'] == 'Failed' for s in samples), 'No real failure recorded')
    need(any(s.get('loadError') for s in samples), 'No load-error recovery scenario recorded')
    failed = [s for s in samples if s['status'] == 'Failed']
    need(any(b['generation'] > a['generation'] and b['region'] == 1 and b['upgrades'] == 0 and b['playerHealth'] == 100 and b['vehicleHealth'] == 300 and b['loaded'] == 12 and b['reserve'] == 96 for a in failed for b in samples), 'No whole-run reset baseline after failure')
    storm_contexts = set()
    for a, b in zip(samples, samples[1:]):
        need(b['wall'] >= a['wall'], 'Wall clock reversed')
        if b['generation'] == a['generation']:
            dt = b['stormTime'] - a['stormTime']
            need(dt >= -1e-6, 'Storm clock reversed within a generation')
            if a['status'] == b['status'] == 'Playing' and a['progress'] <= a['stormFront'] and b['playerHealth'] < a['playerHealth']:
                storm_contexts.add('cabin' if a['cabin'] else a['control'])
            if a['status'] == b['status'] == 'Paused':
                need(abs(dt) < 1e-6 and a['playerHealth'] == b['playerHealth'], 'Paused simulation advanced')
            if b['status'] == 'Playing':
                active += max(0., dt)
                bucket = b.get('activityEvidence', 'unclassified')
                activity_seconds[bucket] = activity_seconds.get(bucket, 0.) + max(0., dt)
                if (a['player'] == b['player'] and not b['installing'] and not b['reloading'] and not b['power']): idle += max(0., dt)
    need({'Driving', 'OnFoot', 'cabin'} <= storm_contexts, 'Missing storm-exposure health-loss evidence in driving, walking or cabin (damage source still requires video review)')
    for run in successful:
        regions = []
        for s in run:
            if s['status'] == 'Playing' and (not regions or regions[-1] != s['region']): regions.append(s['region'])
        need(regions == [1, 2, 3], 'Completed run lacks ordered physical regional traversal')
        for region in (1, 2, 3):
            rs = [s for s in run if s['region'] == region]
            need(any(s['control'] == 'Driving' and abs(s['speed']) > .5 for s in rs), f'Region {region}: no driving')
            need(any(s['control'] == 'OnFoot' for s in rs), f'Region {region}: no walking')
            if region >= 2:
                need(any(s['power'] for s in rs), f'Region {region}: no connected defense')
        for part, upgrade in [('ramPart', 1), ('coil', 2)]:
            need(any(s[part] for s in run), f'No recorded pickup: {part}')
            need(any(s['upgrades'] & upgrade for s in run), f'No installed upgrade: {upgrade}')
            installation = 0.; proved = False
            for a, b in zip(run, run[1:]):
                if a['installing'] and a['cabin']: installation += max(0., b['stormTime'] - a['stormTime'])
                if not (a['upgrades'] & upgrade) and b['upgrades'] & upgrade:
                    proved = installation >= 5 - max(.05, b['dt'] * 2)
                if not b['installing']: installation = 0.
            need(proved, f'No uninterrupted five-second physical cabin installation: {upgrade}')
        need(any(s['cabin'] and s['installing'] for s in run), 'No cabin installation')
        end = run[-1]
        need(end['safety'] and not end['power'] and end['region'] == 3, 'Completion lacks disconnected safe-zone position')
        need(any(r.get('kind') == 'ram-gate-contact' and run[0]['wall'] <= r['wall'] <= end['wall'] for r in rows), 'No physical gate-contact evidence in completed run')
    return errors, {'recordedPlayingSeconds': active, 'stationaryNonActionSeconds': idle, 'activityEvidenceSeconds': activity_seconds,
        'completedGenerations': len(successful), 'gameplayAcceptance': False, 'claim': 'automated-input-diagnostic-only; not visual/device/20-minute approval'}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('directory'); args = ap.parse_args()
    root = pathlib.Path(args.directory)
    rows = [json.loads(line) for line in (root/'timeline.jsonl').read_text().splitlines()]
    errors, summary = inspect(rows)
    for r in rows:
        if r.get('kind') == 'capture' and not (root/r['detail']).is_file(): errors.append('Missing captured PNG '+r['detail'])
    if not any(r.get('kind') == 'capture' for r in rows): errors.append('No screenshots')
    if not (root/'real-time.mp4').is_file(): errors.append('Missing independent original-speed video')
    summary.update(passed=not errors, errors=errors)
    (root/'inspection.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2)); return 1 if errors else 0
if __name__ == '__main__': sys.exit(main())
