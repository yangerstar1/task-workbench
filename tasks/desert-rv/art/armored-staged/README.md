# R3 staged execution — no new art revision

The original R3 art source files are immutable. art-lock.json binds their full manifest, original commit 4521975dc47d914959e274a197224d0af7a47b04, and old completed evidence. New execution code has its own execution-manifest.json and every receipt records both identities. Do not relabel old videos as newly generated.

## Observed failure and valid retained evidence

Run 37827225328 reached the real 80-minute timeout (exit 124), not a reported geometry rejection. Attack.mp4 has no moov atom and is invalid. Artifact 11576761904 retains Idle/Walk/Windup, each SHA-verified and fully decoded: 121/37/67 frames respectively, 960x540 H.264 at 60fps. The original videos and five stills per completed clip are pinned individually in art-lock.json. They may be reused only byte-identically and with the old run/artifact/source attribution. They are not visual approval.

## Execution order

1. Standard Python: `python test_staged.py`. This checks the immutable source, plan and codec fixture, never Blender or Unity.
2. Approved free Actions Blender: `blender -b --factory-startup --threads 4 --python-exit-code 1 --python tasks/desert-rv/art/armored-staged/staged.py -- --stage technical --output EMPTY_DIR`.
   - Executes original generator except its last monolithic dispatch.
   - Uses the original create_action function and complete first validation loop from original review_action, unmodified: every original 60Hz frame for all seven clips and all three interruptions.
   - Writes per-clip numeric evidence immediately, then runs the original rejection/report/export tail, with no image/video render calls. FBX/GLB, skeleton-only animation FBX, blend, clips and evaluated reports are produced before spending time on motion imagery.
   - Existing root/foot/floor/camera/binding/channel gates remain mandatory. A technical error still blocks exports.
3. Obtain the fixed matrix with `python plan.py`. It includes only Attack, Recover, Hit, Death and three interruptions, in chunks of at most 24 actual rendered frames. Max-parallel must be 2. No static images or already-complete clips are rerendered.
4. Each independent Actions job downloads the verified technical artifact and runs staged.py with `--stage chunk --technical TECH_DIR --clip CLIP --chunk INDEX --output EMPTY_DIR`.
   - Blender geometry, camera, materials, Cycles 24 samples and 960x540 remain unchanged.
   - Render every second original 60Hz frame, including the exact final original frame even when it falls between the 30Hz samples. Each PNG is hashed and its original frame/time recorded immediately, not after a long video completes.
   - Upload partial outputs and logs with if: always. A partial receipt is not completion. A later chunk retry can pass `--resume VERIFIED_PARTIAL_DIR`; completed frames are reused only with source/clip/chunk/frame/hash matches. Failed/incomplete frames are not reused.
5. Standard Python `assemble.py --clip CLIP --technical TECH_DIR --chunks DOWNLOADED_CHUNKS --output EMPTY_DIR` refuses missing/conflicting chunks, verifies every image, then assembles a complete clip.
   - VFR encoding preserves original 60Hz timestamps exactly, normally spacing actual samples at 1/30 second. The final exposure remains 1/60, preserving the original video duration exactly rather than silently stretching to CFR30.
   - Receipt records actual frame indices, timestamp list, measured stream duration/frame count, source and execution identities. ffprobe checks every timestamp, and ffmpeg fully decodes the video before declaring it complete.
6. For a retained clip, use assemble.py with `--clip Idle|Walk|Windup --legacy OLD_ARTIFACT_DIR --technical TECH_DIR --output EMPTY_DIR`. This copies pinned bytes only and explicitly attributes the original run/artifact. No new rendering occurs.

## Suggested workflow boundaries

Independent manual public owner/main workflow; standard ubuntu-24.04, contents/actions read as required for artifact retrieval, fixed actions commits, checkout credentials disabled, official checksum-verified Blender 4.2.3. Technical job <=15 minutes. Each <=24-frame render chunk <=15 minutes plus setup/upload buffer, max parallel 2. Per-clip assembly <=5 minutes. Each job uploads its own terminal or partial receipt and logs immediately. Do not replace the earlier full workflow or silently dispatch all clips again.

No sources outside the exact new staged-directory allowlist need publishing. The copied armored-candidate folder in the preparation overlay exists only for tests and must not be republished. Geometry, timing, renderer quality, technical thresholds and original export logic are unchanged. These scripts have not themselves run Blender/Unity; technical and rendered outcomes remain pending real Actions execution.


## Floor-fix source identity

After real technical run 37841397139 found 99 greave floor penetrations, the art source was deliberately revised. This is no longer byte-identical R3. art-lock.json now pins the revised manifest and obtains its exact source commit from the actual workflow checkout. It separately retains the historical R3 commit/manifest/run/artifact and unchanged video bytes. Idle/Walk/Windup have a 240Hz source-kinematic equivalence proof, not a claim of new-rendered or pixel-equivalent evidence. Recovery/interruption knee solutions changed and require a fresh technical pass and new renders. Previous failed technical receipts cannot authorize rendering this revised source.
