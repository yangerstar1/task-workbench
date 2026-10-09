# Native TextureImporter layout regression

`armored-discovery-37846596290-orm.png.meta` is an unchanged Unity-produced source texture meta from the verified Discovery artifact for run 37846596290. SHA-256: 0ec0a8d6d882e9ae03ea61cfc2662e212e464a13b5015154c1489e597edb06af.

It proves the serialized field location, not the current strict derived texture flags. Its original source defaults are sRGBTexture=1 and isReadable=0. Tests change only these two flags to the explicitly authored derived ORM requirements (0 and 1); that test derivative is synthetic and does not establish a native derived-texture pass.

`armored-37881389424-failed-stages.json` records the actual post-NUnit failed-export stage sequence and source log hash. The native run reached GENERATED and did not reach CAPTURE. It did not expose the precise rejection code or derived meta; the schema defect is confirmed independently, but the historical run's exact cause remains unconfirmed.
