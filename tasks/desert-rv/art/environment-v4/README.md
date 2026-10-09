# Environment V4 candidate

This is a new, independent scene-authoring candidate based on public `8b45b3c40e0752eed65ede5f3136a50761bd1a38`. It is not part of the byte-fixed restoration package. It retains the original RV and gameplay bindings. Unity compilation, real camera captures, clearance tests and gameplay validation remain required in the public GitHub Actions producer before visual review.

## What the actual previous images show

- Driving: large uniform flat roof and road dominate; detail has no readable medium-scale hierarchy.
- Walking: homogeneous sand reaches a ruler-straight horizon; objects look independently placed rather than belonging to a site.
- Scrapyard: a few detached boxes and repeated bright ribs, not a dense industrial work area.
- Night beacon: large unlit empty ground and isolated structures, with weak relationships between lights and fittings.

## Candidate approach

1. Physically scaled CC0 surfaces, muted palette and roughness, preserving source RV materials.
2. Anchored station roof machinery, layered canopy support, coherent garage service yard and drainage.
3. Ground transitions, patches, tire paths, low shoulder relief, and distant geological layers.
4. Distinct scrapyard sorting walls / service equipment and a layered beacon compound.
5. New decoration is baked into shared-material spatial batches. New colliders are limited to explicit large ground relief/structures; tiny decoration does not obstruct the route.

Every generated mesh/material is written only inside the new Journey/EnvironmentV4 directory. The producer must enumerate exact files in its export contract, not wildcard the directory. Original source files and original RV assets remain protected. No original byte-fixed package may silently receive these assets.
