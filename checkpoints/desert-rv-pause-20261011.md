# Desert RV paused source checkpoint

Saved on 2026-10-11 UTC at the owner's request before focusing development on the scratch-ticket game.

## Preserved source

- Repository: yangerstar1/task-workbench
- Original branch: journey-android-c15
- Source commit: ff346508f3e5d2b20b58243b19f6845eb0d8b53d
- Source tree: 3f39514e2eb1b8911c75428fa5682303bc508a4f
- Checkpoint branch: archive/desert-rv-pause-20261011
- This checkpoint adds only this status document. Existing code, assets, workflows and evidence remain unchanged.

## Verified remote build state

Actions run: https://github.com/yangerstar1/task-workbench/actions/runs/38157559986
The run is completed with conclusion failure. It is bound to the source commit above. Prior diagnostics recorded 17 native test passes followed by a material-loaded-dirty validation failure. An Android APK was not completed by that run. This is a recoverable source checkpoint, not a release-quality or device-accepted game.

Previously archived Linux candidate: https://github.com/yangerstar1/task-workbench/releases/tag/desert-rv-linux-candidate-20261009-37999653419 . This is an older candidate and does not establish Android or full visual/gameplay acceptance.

## Uncommitted r7 boundary

A subsequent r7 candidate was reportedly frozen as 12 changed files, but its upload was canceled at the fourth blob before a tree, commit or branch update existed. The current workspace and available handoff records do not contain those complete candidate bytes or their exact frozen manifest. Three reported standalone blobs do not constitute a recoverable source version. Do not label this checkpoint r7, claim r7 was uploaded, or substitute reconstructed changes without a new review.

The owner has now requested saving/uploading existing work. The complete verified r6 source is retained by this branch and its parent commit; missing uncommitted r7 changes are explicitly not included. No new build, signing, release publication or gameplay completion is claimed by this checkpoint.

## Resume instructions

1. Start from the exact source commit above, not from an ambiguous latest branch.
2. Read the linked run and its logs before changing material import/authoring validation.
3. If the original r7 bytes are recovered, verify their manifest and review them against this source before applying.
4. Preserve source, assets, licenses and unresolved visual/gameplay issues. Do not weaken tests merely to obtain a green build.
5. Use a new development branch for further fixes; leave this checkpoint intact. Bind every eventual binary to its source commit, workflow run and SHA256, and distinguish build success from actual Android device and visual/gameplay acceptance.
