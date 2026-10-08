#!/usr/bin/env python3
"""Objective PCM/timing checks only. Passing is never listening or sync approval."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import wave

RATE = 48000
DURATION = 1.65
# Independent contract copied from the actual fixed-magazine Reload animation.
# Never derive this from the WAV's untrusted provenance.
CUES = [(12, 'glove_contact', .035), (23, 'follower_latch', .060),
        (35, 'strip_pickup', .045), (48, 'strip_guide', .080),
        (60, 'strip_slide', .100), (68, 'strip_seat', .075),
        (82, 'follower_touch', .035), (91, 'spring_release', .095)]


def rms(values):
    return math.sqrt(sum(v * v for v in values) / len(values)) if values else 0.0


def dbfs(value):
    return round(20 * math.log10(value), 4) if value > 0 else None


def analyze(path):
    """Return report, including failures, even for a corrupted/incorrect WAV."""
    path = Path(path)
    result = {'file': path.name, 'objective_checks_passed': False,
              'auditioned': False, 'perceptual_quality_approved': False,
              'unity_import_verified': False, 'visual_sync_approved': False,
              'failures': []}
    errors = result['failures']
    try:
        raw = path.read_bytes()
        with wave.open(str(path), 'rb') as wav:
            channels, width, rate, frames, compression, _ = wav.getparams()
            payload = wav.readframes(frames)
        result.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), channels=channels,
                      sample_width_bytes=width, sample_rate=rate, frame_count=frames,
                      duration_seconds=frames / rate, compression=compression)
        if (channels, width, rate, frames, compression) != (1, 2, RATE, 79200, 'NONE'):
            errors.append('Expected exactly mono PCM16 48000 Hz, 79200 samples / 1.65 seconds.')
        if len(payload) != frames * width * channels:
            errors.append('Truncated PCM payload.')
        if errors:
            return result
        ints = struct.unpack('<%dh' % frames, payload)
        samples = [v / 32767 for v in ints]
        peak = max(map(abs, samples))
        full_rms = rms(samples)
        result.update(peak_linear=peak, peak_dbfs=dbfs(peak), rms_dbfs=dbfs(full_rms),
                      dc_offset=sum(samples) / frames, clipped_sample_count=sum(abs(v) >= 32767 for v in ints),
                      crest_factor_db=dbfs(peak / full_rms) if full_rms else None,
                      exact_zero_fraction=sum(v == 0 for v in ints) / frames)
        if not .08 <= peak <= .85:
            errors.append('Peak must be between -21.94 and -1.41 dBFS before game mix.')
        if not .004 <= full_rms <= .2:
            errors.append('Global RMS is silent/too weak or excessively loud.')
        if abs(result['dc_offset']) > .001:
            errors.append('DC offset exceeds 0.001 full scale.')
        if result['clipped_sample_count']:
            errors.append('Clipped PCM samples.')
        allowed = [False] * frames
        event_reports = []
        for frame, action, duration in CUES:
            first = round((frame - 1) / 60 * RATE)
            count = round(duration * RATE)
            last = first + count
            allowed[first:last] = [True] * count
            values = samples[first:last]
            nonzero = [i for i, v in enumerate(values) if abs(v) >= 2 / 32767]
            event_peak = max(map(abs, values))
            event_rms = rms(values)
            first_signal = nonzero[0] / RATE if nonzero else None
            peak_index = max(range(count), key=lambda i: abs(values[i]))
            edge_step = max(abs(samples[first] - samples[first - 1]), abs(samples[last - 1] - samples[last]))
            # 10ms block envelopes make event timing/strength auditable without claiming to hear it.
            envelope = [round(rms(values[i:i+480]), 7) for i in range(0, count, 480)]
            event_reports.append({'frame': frame, 'action': action, 'start_seconds': first / RATE,
                                  'duration_seconds': duration, 'peak_dbfs': dbfs(event_peak),
                                  'rms_dbfs': dbfs(event_rms), 'onset_delay_seconds': first_signal,
                                  'peak_seconds': (first + peak_index) / RATE,
                                  'boundary_step_linear': edge_step, 'rms_10ms_linear': envelope,
                                  'runtime_gain': .4, 'estimated_runtime_peak_dbfs': dbfs(event_peak * .4)})
            if first_signal is None or first_signal > .002:
                errors.append(action + ': missing or delayed event onset (>2ms).')
            if event_rms < .004 or event_peak < .035:
                errors.append(action + ': event energy too weak for objective candidate gate.')
            if edge_step > .001:
                errors.append(action + ': boundary discontinuity exceeds -60dBFS.')
        result['events'] = event_reports
        stray = sum(v != 0 and not permitted for v, permitted in zip(ints, allowed))
        result['nonzero_samples_outside_authored_events'] = stray
        if stray:
            errors.append('Unexpected content outside authored cue windows.')
        first_nonzero = next((i for i, v in enumerate(ints) if v != 0), frames)
        last_nonzero = next((i for i in range(frames-1, -1, -1) if ints[i] != 0), -1)
        result['leading_silence_seconds'] = first_nonzero / RATE
        result['trailing_silence_seconds'] = (frames - 1 - last_nonzero) / RATE
        result['objective_checks_passed'] = not errors
    except (OSError, EOFError, wave.Error, struct.error, ZeroDivisionError, ValueError) as exc:
        errors.append('Unreadable WAV: ' + str(exc))
    return result


def validate_provenance(wav, provenance, generator, expected_commit=None, expected_run=None):
    errors = []
    if (provenance.get('duration_seconds'), provenance.get('sample_rate'), provenance.get('channels'), provenance.get('format')) != (1.65, 48000, 1, 'PCM signed 16-bit'):
        errors.append('Provenance audio format/duration mismatch.')
    if provenance.get('sha256') != hashlib.sha256(Path(wav).read_bytes()).hexdigest():
        errors.append('Provenance WAV hash mismatch.')
    if provenance.get('generator_sha256') != hashlib.sha256(Path(generator).read_bytes()).hexdigest():
        errors.append('Provenance generator hash mismatch.')
    expected = [(f, n, (f - 1) / 60, d) for f, n, d in CUES]
    actual = [(c.get('frame'), c.get('action'), c.get('seconds'), c.get('duration_seconds')) for c in provenance.get('cues', [])]
    if expected != actual:
        errors.append('Provenance event contract mismatch.')
    if provenance.get('auditioned') is not False or provenance.get('visual_sync_approved') is not False:
        errors.append('Generation cannot confer audition/sync approval.')
    if not provenance.get('github_run_id') or not provenance.get('source_commit'):
        errors.append('Missing actual Actions source/run provenance.')
    if expected_commit is not None and provenance.get('source_commit') != expected_commit:
        errors.append('Provenance source commit is not the expected Actions commit.')
    if expected_run is not None and provenance.get('github_run_id') != expected_run:
        errors.append('Provenance run is not the expected Actions run.')
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wav', type=Path, required=True)
    parser.add_argument('--repeat-wav', type=Path, required=True)
    parser.add_argument('--generator', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--expected-run', required=True)
    args = parser.parse_args()
    report = analyze(args.wav)
    try:
        provenance = json.loads(args.wav.with_suffix('.provenance.json').read_text())
        report['failures'].extend(validate_provenance(args.wav, provenance, args.generator, args.expected_commit, args.expected_run))
        report['source_commit'] = provenance.get('source_commit')
        report['github_run_id'] = provenance.get('github_run_id')
        report['byte_identical_repeat'] = args.wav.read_bytes() == args.repeat_wav.read_bytes()
        if not report['byte_identical_repeat']:
            report['failures'].append('Separate deterministic generation was not byte identical.')
    except (OSError, ValueError) as exc:
        report['failures'].append('Missing/invalid verification input: ' + str(exc))
    report['objective_checks_passed'] = not report['failures']
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['objective_checks_passed'] else 1)


if __name__ == '__main__':
    main()
