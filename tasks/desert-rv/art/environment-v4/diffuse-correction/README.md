# CC0 sand base-color illumination correction

This is a separate derived texture for a four-image native comparison, not a visually accepted production replacement. Public run `37966407444` at `551be26a3faa9ffbeb3a4a57bce8d65b592b788d` captured two fixed cameras with four channel ablations. Disabling the normal map retained the grid; replacing diffuse with its average color removed it. The average-color control is not delivered as finished art.

Source: Poly Haven `sand_03` by Charlotte Baglioni, [CC0](https://polyhaven.com/license), [original asset](https://polyhaven.com/a/sand_03). The original source JPEG, normal map and all existing source assets remain unchanged. `derived-provenance.json` records original and derived file hashes, attribution, license, exact recipe and numerical results.

## Reproducible operation

`correct_illumination.py SOURCE_JPEG OUTPUT_PNG` requires Python, Pillow and NumPy. It refuses an incorrect input SHA or any existing output. It decodes sRGB to linear RGB, estimates luminance illumination with a periodic Gaussian low-pass filter (sigma 48 pixels on the 1024-pixel, 2 m tile), divides out that illumination, restores each original mean color with one global channel gain, and encodes RGB8 PNG. No procedural noise, added grain, resampling, AI image, forced mip, shader change or geometry change is used. The illumination gain ranges only from 0.909 to 1.078.

The original two axis fundamental amplitudes are approximately 3.95% and 4.19% of mean luminance. The derived map reduces them to 0.219% and 0.179%. Frequencies at least 16 cycles per tile retain 100.3% of their original relative RMS. The original mean color is retained within 0.03% after RGB8 quantization. These numerical checks do not prove successful Unity sampling or attractive terrain.

The new PNG is 1024×1024 RGB sRGB, with repeat wrap, trilinear mips and anisotropy 4. It is an additional source asset, not an overwrite. Its diffuse-only use must preserve the existing standard URP Lit shader, original weak normal map, lighting, geometry, 2 m world UVs and tint. The separate comparison checks original versus corrected diffuse at the original Scrapyard overview and ground cameras, with one identical warm-up render before each readback. Review dune edges as well as texture repetition; a smooth map must not conceal geometry seams.
