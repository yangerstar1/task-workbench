#!/usr/bin/env python3
"""Original deterministic mechanical synthesis. No recorded/third-party samples.
Run only in the approved Actions asset job. Not auditioned or visually accepted.
R2 clip: 60 fps, frames 1..100, duration (100-1)/60 = 1.65 seconds.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import wave

RATE = 48000
DURATION = 1.65
# fixed magazine: grasp/pull follower, present and seat NEW strip, release follower
CUES = [(12, 'glove_contact', .035, 240, .11),
        (23, 'follower_latch', .060, 1650, .38),
        (35, 'strip_pickup', .045, 950, .13),
        (48, 'strip_guide', .080, 2700, .14),
        (60, 'strip_slide', .100, 1150, .18),
        (68, 'strip_seat', .075, 780, .32),
        (82, 'follower_touch', .035, 310, .10),
        (91, 'spring_release', .095, 1350, .30)]

def synthesize():
    rng = random.Random(0xD35E47)
    samples = [0.0] * round(RATE * DURATION)
    for frame, name, duration, frequency, gain in CUES:
        offset = round((frame - 1) / 60 * RATE)
        previous = 0.0
        for i in range(round(duration * RATE)):
            index = offset + i
            if index >= len(samples): break
            t = i / RATE
            noise = rng.uniform(-1, 1)
            highpass = noise - previous
            previous = noise
            envelope = (1 - math.exp(-t * 1600)) * math.exp(-t * 7 / duration)
            resonant = math.sin(2 * math.pi * frequency * t) + .3 * math.sin(2 * math.pi * frequency * 2.37 * t)
            samples[index] += gain * envelope * (.60 * resonant + .18 * highpass)
    # Fixed headroom, no peak-dependent normalization or external sample content.
    return b''.join(struct.pack('<h', round(max(-.95, min(.95, v)) * 32767)) for v in samples)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(args.output), 'wb') as output:
        output.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        output.writeframes(synthesize())
    manifest = {'origin': 'Original deterministic mathematical synthesis; no third-party samples',
                'duration_seconds': DURATION, 'sample_rate': RATE, 'channels': 1,
                'format': 'PCM signed 16-bit', 'clip_reference': 'R2 Reload frames 1..100 at 60 fps',
                'cues': [{'frame': f, 'seconds': (f - 1) / 60, 'action': n} for f,n,*_ in CUES],
                'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
                'auditioned': False, 'visual_sync_approved': False,
                'note': 'Review exact generated WAV against actual imported clip before approval.'}
    args.output.with_suffix('.provenance.json').write_text(json.dumps(manifest, indent=2)+'\n')
if __name__ == '__main__': main()
