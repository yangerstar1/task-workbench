# Original G3 audio

These ten PCM WAV files were generated specifically for this project by
`tasks/lottery-shop/scripts/generate_g3_audio.py`. There are no downloaded
samples, third-party recordings, copied songs, voices, or paid services.
They may be redistributed with this project and its source. They are not
represented as downloaded CC0 assets or as professionally recorded foley.

The constrained asset-download environment led to original procedural PCM.
The source generator, fixed seed and hashes are recorded in audio-manifest.json.
Runtime uses native Unity AudioSources grouped into Environment, Interaction
and Music, with independent saved gains; no external audio SDK is used.
These are runtime sound assets, not test doubles.

Friction changes pitch and gain with valid moving scratch input, stops on
release/out-of-bounds/panel/commit/focus/pause, and has an 85 ms stale-sample
cutoff. Non-positive net results do not get a prize flourish. Audio does not
modify money, game RNG, ticket reveals or economic save contents.

Listening, real Unity import/playback, phone output latency and final V-04
quality remain to be reviewed on the integrated playable build.
