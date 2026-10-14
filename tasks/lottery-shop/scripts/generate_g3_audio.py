#!/usr/bin/env python3
"""Original procedural shop sounds; no downloaded samples or copied melodies.
Requires NumPy for offline generation only. Runtime reads the authored PCM WAVs.
"""
import argparse, hashlib, json, math, wave
from pathlib import Path
import numpy as np
RATE = 22050
RNG = np.random.default_rng(20261014)

def grid(seconds):
    return np.arange(round(seconds * RATE), dtype=np.float64) / RATE

def noise(seconds, low=80, high=7000):
    n = round(seconds * RATE)
    freq = np.fft.rfftfreq(n, 1 / RATE)
    spectrum = RNG.normal(size=len(freq)) + 1j * RNG.normal(size=len(freq))
    curve = np.zeros_like(freq)
    band = (freq > low) & (freq < high)
    curve[band] = np.sin(np.pi * (freq[band] - low) / (high - low)) ** .45
    x = np.fft.irfft(spectrum * curve, n)
    return x / max(np.std(x), 1e-9)

def add(target, signal, offset, gain=1):
    start = round(offset * RATE)
    length = min(len(signal), len(target) - start)
    if length > 0:
        target[start:start + length] += signal[:length] * gain

def struck(frequency, seconds, decay=.13, metal=False):
    t = grid(seconds)
    ratios = [1, 2.73, 4.19, 5.43] if metal else [1, 2.003, 3.987, 6.01]
    y = sum(np.sin(2 * np.pi * frequency * ratio * t) * np.exp(-t / (decay / (1 + .45 * i))) / (1 + i) ** 1.7 for i, ratio in enumerate(ratios) if frequency * ratio < RATE / 2 - 200)
    return y * (1 - np.exp(-t / .0025))

def tapered(y, seconds=.012):
    y = y.copy(); count = min(round(seconds * RATE), len(y) // 2)
    y[:count] *= np.linspace(0, 1, count)
    y[-count:] *= np.linspace(1, 0, count)
    return y

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--output', type=Path, required=True); args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True); records = []
    def save(name, y, peak, loop=False, description=''):
        y = np.nan_to_num(y); y -= np.mean(y)
        if not loop: y = tapered(y)
        else:
            # A short wrap blend removes a discontinuity without a silent gap.
            count = min(512, len(y)//8); ramp = np.linspace(0, 1, count)
            y[-count:] = y[-count:]*(1-ramp) + y[:count]*ramp
            y[-1] = y[0]
        y *= peak / max(np.max(np.abs(y)), 1e-9)
        pcm = np.round(y * 32767).astype('<i2')
        path = args.output / (name + '.wav')
        with wave.open(str(path), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm.tobytes())
        records.append(dict(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size, sampleRate=RATE, channels=1, seconds=len(y)/RATE, peak=float(np.max(np.abs(y))), rms=float(np.sqrt(np.mean(y*y))), loop=loop, description=description))
    t = grid(2)
    rub = noise(2, 600, 6200) * (.65 + .16*np.sin(2*np.pi*37*t) + .08*np.sin(2*np.pi*113*t))
    rub += .21 * noise(2, 120, 1700)
    for at in RNG.uniform(0, 1.98, 110):
        grain = noise(.012, 900, 8500) * np.exp(-grid(.012) / .0025)
        add(rub, grain, float(at), .10)
    save('scratch_loop', rub, .58, True, 'Granular foil/paper friction; live speed changes pitch and level, not a timed scrape sample.')
    t = grid(.44); paper = noise(.44, 400, 5100) * (np.exp(-((t-.10)/.055)**2) + .5*np.exp(-((t-.27)/.05)**2))
    paper += .20 * struck(185,.44,.055)
    save('ticket_take', paper, .58, description='Two paper flexes and a soft desktop contact for a committed ticket purchase.')
    t=grid(.12); press = struck(390,.12,.022) + .09*noise(.12,900,6500)*np.exp(-t/.009)
    save('ui_press',press,.45,description='Short wooden button tap, only after a valid pointer release.')
    coins = np.zeros(round(.82*RATE))
    for at,f,g in [(0,1640,1),(.065,2230,.7),(.14,1870,.55),(.255,2760,.35)]:
        add(coins,struck(f,.42,.10,True),at,g)
    add(coins,struck(190,.2,.045),.03,.25)
    save('coin_settle',coins,.60,description='Several inharmonic metal contacts falling into a tray; positive net settlement only.')
    t=grid(.28); flat = .8*struck(150,.28,.045) + .15*noise(.28,170,2200)*np.exp(-t/.045)
    save('settle_flat',flat,.48,description='Quiet paper/wood close; loss or break-even has no celebratory coins.')
    high=np.zeros(round(1.25*RATE))
    for at,f,g in [(0,587.33,.6),(.10,739.99,.50),(.21,880,.42),(.34,1174.66,.28)]: add(high,struck(f,.8,.25,True),at,g)
    add(high,coins,.14,.4)
    save('prize_high',high,.62,description='Short layered struck-metal flourish, only a confirmed positive-net raw prize of at least 20 ticket prices; no gameplay wait.')
    t=grid(.4); transfer = .24*noise(.4,400,3000)*np.exp(-((t-.05)/.025)**2)
    add(transfer,struck(420,.22,.065),.04,.7); add(transfer,struck(560,.22,.065),.15,.42)
    save('transfer',transfer,.50,description='Soft two-part receipt acknowledgement for real money movement, distinct from a prize.')
    t=grid(.22); reveal=noise(.22,700,6500)*np.exp(-t/.045)*(1-np.exp(-t/.004))
    save('paper_reveal',reveal,.45,description='Brief coating lift at confirmed reveal; not a second reward.')
    t=grid(16); ambient=.25*noise(16,70,1100)*(.5+.12*np.sin(2*np.pi*t/16))
    ambient += .08*np.sin(2*np.pi*100*t) + .025*np.sin(2*np.pi*200*t)
    ambient += .12*noise(16,120,3300)*(np.exp(-((t-5)/1.8)**2)+.65*np.exp(-((t-12)/2)**2))
    save('shop_ambient',ambient,.35,True,'Subtle original indoor fan/air and two distant street swells; no recorded people or real-world audio.')
    music=np.zeros(32*RATE)
    chords=[(146.83,220,293.66,369.99),(123.47,185,246.94,293.66),(98,146.83,196,293.66),(110,164.81,220,293.66)]
    for bar in range(8):
        notes=chords[bar//2]
        for beat,index,gain in [(0,0,.43),(1.5,2,.23),(2.5,1,.27),(3.25,3,.16)]:
            note=struck(notes[index],2.6,.65)
            start=bar*4+beat
            # Circular tails make the original eight-bar texture truly loopable.
            for echo,scale in [(0,gain),(.18,gain*.12),(.37,gain*.06)]:
                offset=round((start+echo)*RATE)%len(music); indices=(np.arange(len(note))+offset)%len(music)
                music[indices]+=note*scale
    save('shop_music',music,.42,True,'Original sparse eight-bar felt-pluck texture at 60 bpm; independently adjustable and initially quiet.')
    (args.output/'audio-manifest.json').write_text(json.dumps({'schemaVersion':1,'origin':'ORIGINAL_PROCEDURAL_PCM_NO_THIRD_PARTY_SAMPLES','generator':'tasks/lottery-shop/scripts/generate_g3_audio.py','numpyVersion':np.__version__,'seed':20261014,'files':records},indent=2)+'\n')
    print(json.dumps({'clips':len(records),'bytes':sum(r['bytes'] for r in records),'peakMaximum':max(r['peak'] for r in records)},indent=2))
if __name__=='__main__':main()
