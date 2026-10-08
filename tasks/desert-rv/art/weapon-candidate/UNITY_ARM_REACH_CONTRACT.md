# Minimal imported arm reach contract (candidate, not implemented/verified Unity behavior)

## Exact transforms and authority

For each side L/R:
- upperarm.L/R: shoulder pivot, child of root
- forearm.L/R: elbow pivot, child of upperarm
- WristTip.L/R: exported empty at actual forearm tail, child of forearm
- WristTarget.L/R: exported empty at actual glove/cuff wrist center, child of hand
- hand/arm.L remain under LeftReloadOffset; they are separate from the upperarm/forearm chain

The FBX/GLB contains the baked common reload, including the standard-count arm rotations and finger poses. Live Blender constraints are NOT exported or required. Partial loading moves the incoming strip and hand chain together through the existing count carriers. The only extra runtime correction rotates upperarm and forearm to the resulting wrist target. It never moves/scales the hand, carriers, gun, shoulder, elbow local position or fingers.

## Import-time calibration, no guessed axes

Use actual imported world positions S=upperarm.position, E=forearm.position, W=WristTip.position in a known neutral pose. Store L1=|E-S|, L2=|W-E| and both bind local rotations. Cross-check source lengths recorded in weapon-presentation-contract.json after scale conversion. Reject nonuniform rig scale, degenerate lengths, wrong hierarchy, absent markers or a WristTip/WristTarget neutral gap above tolerance.

Derive the bend pole by projecting E-S perpendicular to W-S. Store its normalized direction in rig-local coordinates and its sign. Do not assume local X/Y/Z on Unity-imported bones. Source Blender bones run along their own +Y, but imported segment vectors and bind rotations are authoritative.

## Minimal interface and solve

SolveArm(upperarm, forearm, wristTip, wristTarget, calibratedL1, calibratedL2, rigLocalPole, rigRoot) returns success plus reach/length/seam diagnostics.

Run in this exact order after authoritative Animator sampling:
1. Sample the existing Idle/Fire/Reload phase. Restore the base animation pose every tick; do not compound last frame's IK.
2. Apply the count snapshot's IncomingOffset and LeftReloadOffset once, as absolute rest-relative offsets.
3. Read S, E, tip, target T from the resulting pose. Solve arm rotations only.
4. Check residuals; then render. No ammo, damage, reload-commit or clock events are generated.

Let d=|T-S|, direction=(T-S)/d. Reject unreachable d > L1+L2 or d < |L1-L2| (small numeric tolerance only). No stretching or silent target clamping is permitted for an accepted pose.

Project the imported animated elbow's E-S perpendicular to direction for the preferred bend plane. If degenerate, use the calibrated rig-local pole transformed to world and projected onto that plane. Keep the calibrated hemisphere to prevent elbow flipping. Reject an unresolved degenerate pole.

Compute a=(L1²-L2²+d²)/(2d), h=sqrt(max(0,L1²-a²)), desiredElbow=S+a*direction+h*pole.

Rotate upperarm by the world-space shortest arc from its current E-S vector to desiredElbow-S, preserving its existing twist. After hierarchy evaluation, rotate forearm by the shortest arc from its actual WristTip.position-forearm.position vector to T-forearm.position. Do not assign either bone's local position or scale. Re-read the actual transforms and verify fixed segment lengths and wrist residual.

## Pause, reset and failure cases

Paused playback reuses the same authoritative sampled phase and count snapshot, then deterministically applies the same offsets and solve; it must not accumulate rotations or advance timers. Epoch/sequence changes clear cached pole continuity and restore the calibrated/base pose before sampling. Disable/rebind restores the base state.

Actual Unity tests must cover 0+12, 3+5, 11+1 through frames 1–100; pause/resume at 35, 60 and 68; cancel; epoch change; reach limits; straight-arm/zero-distance degeneracy; both sides; and zero motion over repeated paused samples. Record forearm/upperarm length preservation, actual WristTip-to-WristTarget gap, shoulder stability and imported axes. Independently reject visible sleeve/hand distortion even with small residuals.

This is a bounded analytic two-bone solver, not a dependency on an unavailable IK package. Until it is implemented and tested on the imported artifact, the diagnostic asset is not Unity-ready.
