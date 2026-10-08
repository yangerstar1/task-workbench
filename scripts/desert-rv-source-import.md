# Reviewed Desert RV source import

This is a single-purpose, finite import, not a build, general ZIP extractor or
private-repository bridge. It never accesses the original private repository.

The repository owner may manually dispatch `desert-rv-source-import.yml` on public
`main`. There are no inputs, schedules, pull-request or push triggers. Both the
original actor and rerun actor must be `yangerstar1`. Standard `ubuntu-24.04` only;
15-minute limit; no new credential, paid runner or third-party service.

Before enabling the import, review and fix all four constants in
`import_desert_rv_source.py`: this public repository's exact Release ZIP URL,
archive SHA-256, embedded manifest SHA-256, and original source commit. Blank
values intentionally fail closed. Changing these pins requires a reviewed commit;
a dispatcher cannot supply a new URL or hash. Publishing an archive alone does
not run this workflow.

The manifest is `tasks/desert-rv/PUBLIC-EXPORT.json`. Its `sourceCommit` and
`files` array bind every exported file's repository-relative `path`, integer
`size`, `mode` (`100644` only), `sha256`, `exportBlobSha` and optional
`sourceBlobSha`. The manifest does not list itself: its complete bytes are pinned
separately. ZIP files use those repository-relative paths, no directories and no
symlinks. Only the three Unity source roots, the exact font backup/restore files,
README, notices, manifest and exact project `.gitignore` are allowed.

Validation checks both complete-download hashes and every member. It rejects
traversal, absolute/Windows/control-character/hidden paths (except that exact
`.gitignore`), duplicate and case-colliding paths, unknown files, executable or
special modes, conflicting file/directory entries and common credential patterns.
It bounds compressed download to 128 MiB, expanded bytes to 192 MiB, each member
to 32 MiB and count to 5,000. Pattern detection is defense in depth, not a substitute
for the prior source/license/secret audit that establishes the pinned package.

All validation precedes Git writes. Files are never extracted to the checkout.
Git plumbing writes raw blobs without running source code, filters or hooks.
The alternate index starts from the exact triggering commit. Files outside the
manifest survive unchanged; differing existing files or ancestor collisions fail
closed. Identical imports are idempotent. There is no overwrite or delete mode.

Only this job grants the existing `GITHUB_TOKEN` `contents: write`; checkout does
not persist credentials. The public source download is unauthenticated. The token
is supplied through environment-only HTTP authentication for the final remote
operations, never placed in a URL, Git config file, command argument or output.
Before pushing, the current remote HEAD must equal the dispatch commit. A normal
non-force fast-forward push also rejects a concurrent update. Re-dispatch from
fresh main after investigating a race. Do not bypass this check with force/rebase.

The final summary reports the verified remote commit, file/byte count, source
commit and both pinned hashes. No Unity run, APK publication or downstream workflow
is dispatched. Import completion is not evidence that the game builds or runs.

## Verification

Run only the standard-library tests:

    python3 -m unittest discover -s scripts -p test_import_desert_rv_source.py -v

They cover valid imports, bad pins and manifest fields, path/symlink/mode/size
attacks, duplicate entries, secret patterns, existing-file preservation, collision
rejection and idempotence using a disposable local Git repository. Real Actions
push/permission behavior must be verified on the actual manually dispatched run.
