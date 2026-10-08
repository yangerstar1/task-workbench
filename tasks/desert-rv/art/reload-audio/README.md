# Original reload-audio candidate

Status: source and objective verifier prepared. No production WAV has been generated in the dot workspace. No listening, Unity import, animation-sync, or commercial-quality approval is claimed. The tiny `reload-audio-only` mode in the existing `desert-rv-weapon-art.yml` is the only proposed generation route; publishing/running is owned by the existing authorized publisher.

## What is reused and what is new

The source baseline is `19cc064551488607caf6cd7b9139f7be90bfd707` in `yangerstar1/task-workbench`. It contains **nine** original WAVs: arc, engine, hit, pickup, shot, step, threat, upgrade, and wind. All are inventoried by exact SHA-256 in `source-manifest.json`; none is overwritten, resampled, or regenerated. The six `JourneyActions` slots are shot, hit, reload, pickup, upgrade, wind; the original reload slot is unwired because `reload.wav` is absent. Arc has its separate presenter. Engine/step/threat are retained even when not part of those six slots.

`art/scripts/make_reload_foley.py` already existed. This change retains its deterministic original synthesis and cue choices, adds a 4ms tail fade to avoid abrupt event edges, rejects overload instead of clipping it, refuses overwrites, and records source/run/file hashes. This is original **synthesized mechanical sound**, not a recording of a real firearm or downloaded Foley. It uses only Python's standard library, fixed-seed noise, and mathematical resonances. No paid API or external sample is involved. Existing project-authored provenance is documented in `ASSET-NOTICES.md`; this candidate does not grant a new blanket license or certify perceptual quality.

## Generate and measure on the existing public runner

Choose `reload-audio-only` in the existing weapon-art workflow after its candidate source changes are reviewed and published. This path runs no Blender, Unity, emulator, package install, or new workflow. It runs fixture tests, verifies the retained nine audio hashes and candidate source hashes, generates the WAV twice into new directories, independently measures it, compares exact bytes, checks that tracked source remains untouched, and uploads the artifact. It has a five-minute timeout.

The equivalent runner command is:

```
python3 -m unittest discover -s tasks/desert-rv/art/reload-audio -p 'test_*.py' -v
python3 tasks/desert-rv/art/reload-audio/build_reload_candidate.py --output reload-audio-output
```

The output is `reload.wav`, `reload.provenance.json`, `audio-analysis.json`, `generation-status.json`, the reviewed source manifest, and `SHA256SUMS`. A passing job certifies objective generation only. If generation/measurement fails, no successful generation receipt is written and no success artifact is uploaded.

## Timing and mix contract

- Mono, signed 16-bit PCM, 48,000 Hz; exactly 79,200 samples / **1.65 seconds**, matching authority and the Reload animation's frames 1–100 at 60 fps.
- Frame 12 / 0.183333s: glove contact
- Frame 23 / 0.366667s: follower latch
- Frame 35 / 0.566667s: new strip pickup
- Frame 48 / 0.783333s: strip guide
- Frame 60 / 0.983333s: strip slide
- Frame 68 / 1.116667s: strip seat
- Frame 82 / 1.350000s: follower touch
- Frame 91 / 1.500000s: spring release; authored tail ends at 1.595s

Frames match the actual `art/weapon-candidate/build_weapon.py` Reload keys. Audio seating at frame 68 must never move ammunition or enable firing early. Authority still commits once after 1.65 seconds. All partial reloads retain this duration; sound contains no count-dependent repeated bullet noises.

The dedicated `JourneyActions.reloadAudio` voice owns playback at volume 0.4, fixed pitch 1, non-looping. `WeaponPresentation` only samples animation and never schedules audio or AnimationEvents. Normal pause retains timer, clip, and voice position with Pause/UnPause. Successful driver entry, install, bind, stale generation, loading/terminal state, completion, and component disable clear the reload timer/snapshot and stop/clear the voice. Failed driver entry does not cancel. Cancel never refills ammo or increments epoch. A lifecycle fixture does not prove audible behavior.

## Objective checks and limits

The independent validator checks format/length, clipping, peak/RMS/DC, every expected cue's onset within 2ms, per-cue energy, exact silence outside authored windows, sub -60dBFS boundary discontinuities, head/tail silence, and per-event 10ms RMS envelopes. It reports each cue's peak and estimated post-volume-0.4 peak. Two independent generations must be byte-identical. These establish non-silence, timing and headroom; they **cannot establish that the mechanical timbre is convincing, comfortably audible over wind/shot audio, or pleasant**.

Local tests use a distinctly named synthetic sine fixture only; they do not render this source sound. Real waveform measurements remain pending until the Actions artifact exists. This environment exposes no listening/audition tool, so no claim of hearing has been made.

## After the real artifact exists

1. Verify its source commit, SHA256SUMS, provenance, and objective report before staging. Preserve all nine original WAVs.
2. Stage the verified WAV at `Assets/DesertRV/Audio/reload.wav` with the supplied `reload.wav.meta` only in the authorized scene/build integration. Mono PCM, preload enabled, no background loading, no looping; avoid platform recompression that moves short transient cues. This source candidate alone does not add a fake WAV or replace a scene audio reference.
3. Run the exact new EditMode lifecycle cases and the full existing suite on public Unity Actions. Tests are authored but **not run in Unity here**. Update source-state inventory and aggregate expected cases after the final integration.
4. In a real audio-enabled PlayMode/Android run, capture or listen to full, one-round and low-reserve reloads; repeated reload input; failed and successful driver entry; install/cancel; pause at 0.35s and 1.10s and resume; background/focus loss; disable/re-enable; death, loading and whole-run restart. Assert audible events resume once at the retained position, never leak into driving/terminal/new-session state, and do not exceed the 1.65s authority. Inspect DSP/sample timing under a frame hitch too.
5. Listen to the exact generated WAV alone and in the real game mix with wind, shots, hits and arc present. Use actual imported animation/playthrough evidence for sync. Record reviewer, tool/device, artifact hash, date, mix levels, findings and decision. Only after this should perceptual and sync flags be separately accepted; never change them because a file is non-empty.
