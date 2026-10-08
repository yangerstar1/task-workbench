# Task workbench

A small, public workspace for finite, reviewed computational tasks. Source, inputs,
stage checkpoints and results are tied together by hashes. It uses standard public
GitHub Actions, not a continuously running server or an autonomous agent platform.


## Current development and version policy (2026-10-08)

GitHub is the source of truth for code, project documentation, version history and
reviewed release deliverables. Execution should use bounded jobs on standard
public GitHub Actions runners. The temporary interactive cloud-computer route
is discontinued; do not rely on its installed tools or authentication surviving.
No independent coding task or paid runner is implied by this policy.

- Commit every identifiable project version with a useful change description.
  Preserve unfinished work on a branch; do not label it a tested release.
- Update the README and relevant design, build and recovery instructions in the
  same version as the implementation. Record known limitations and actual tests.
- Give verified release versions immutable tags and reviewed GitHub Release
  assets. Bind each binary to its source commit, workflow run and SHA256.
- Keep source and distributable assets in Git, subject to size and license limits.
  Keep generated installers/builds in Releases, not duplicated throughout Git.
- Never commit passwords, tokens, license credentials, signing keys, local
  authentication stores, or non-redistributable materials.
- Reconstruct disposable build environments from pinned tooling and dependency
  declarations. Persist results before a job ends. GitHub is not a persistent VM.
- Do not maintain a separate Space as the project documentation source.

### Verified state and remaining blocker

The generic data-summary complete/checkpoint/recover path has passed real Actions
runs, including byte verification:
[recovery evidence](https://github.com/yangerstar1/task-workbench/releases/tag/task-recover-20261008-001).
This establishes a small task's recovery path, not a successful Unity build.

The Unity workflow below is still an unverified proof. It currently requires
three repository secrets; neither a working Personal-license setup nor the four
native tests nor a newly built Android APK has been verified. Its outputs currently
expire as Actions artifacts after seven days. Release archival for Unity is still
to be implemented after the licensing and build path is verified. Do not treat
the release policy above as evidence that this implementation already exists.

## What is ready to try

- **data-summary:** an original eight-row, fictional CSV. One stage validates and
  aggregates it; another produces a ranked report. No account secrets or external
  workload API. This is the first infrastructure proof, not a large-workload benchmark.
- **unity-proof:** the separately reviewed original Unity 6000.3.19f1 sample, retained
  byte for byte under `tasks/unity-proof/`. A root workflow adapts its paths. Four real
  native tests and a new ARM64 IL2CPP APK are required. Account activation and native
  execution remain unverified until that independent workflow actually succeeds.

All checked-in material is intended for public visibility. Do not add private work,
licensed game assets that cannot be redistributed, credentials, or personal data.

## Start without a new token or login

The maintainer can commit one of `examples/*-request.json` as
`requests/current.json` on **main**, with a fresh request ID. Only this exact path
triggers the generic workflow. The initial repository contains no current request,
so installing the framework does not start work. The repository's existing authorized
writer can submit a request; no new credential is needed. GitHub's manual Run workflow
button also works. No PR, schedule, Release, or workflow-completion trigger exists.
The concurrency group queues up to GitHub's supported 100 pending runs; it does not
cancel an older pending request when a third request arrives. Submit finite work,
not a stream intended to occupy runners permanently.

`task`, `mode`, and resume IDs have a closed schema. There is no command, URL, code,
repository, branch, or filesystem-path input. Execution uses the triggering commit.
Only reviewed tasks added to the code's static allowlist can be dispatched.

## Progress, recovery and evidence

1. `complete` runs both stages and checks all output bytes.
2. `checkpoint` ends after the successful index stage. Its status is CHECKPOINT,
   never COMPLETED. Record the request ID and GitHub run ID.
3. `recover` uses a new request ID and both recorded source IDs. It first verifies
   the source run in this repository, then downloads the fixed evidence files from
   its Release. If the Release is absent, it can use that exact run's seven-day artifact.
   A finished failed run can supply a genuinely successful stage checkpoint.
4. Recovery pins the complete tracked tree, file modes and actual content, excluding
   only `requests/current.json`. Changing code, workflow, dependency, or input requires
   a fresh computation. Both source and recovery commits are recorded.
5. Every valid checkpoint is published in a separate, narrowly privileged job as
   `task-<requestId>`. Release state explicitly says COMPLETED, CHECKPOINT or
   FAILED_WITH_CHECKPOINT. Raw task failure stays a failed workflow. Releases contain
   the receipt, stage files and SHA256SUMS. Publication checks the returned asset
   inventory and GitHub SHA256 digests; later recovery downloads and hashes every byte.
   Assets are uploaded to a draft first and published only after verification. An
   interrupted draft is left for review and is never treated as reusable completion.

An identical already-completed request is verified and reused, not silently run again.
A conflicting or unfinished ID fails; use a new ID to continue. Releases are not
overwritten or deleted. A failure before the first checkpoint has no recoverable
stage. A hard runner cancellation may prevent evidence upload; only already uploaded
bytes survive. If both Release and artifact are unavailable, recompute from Git.
Seven-day artifacts are temporary transfer, not the only long-term record. Releases
remain available while this repository and its assets are retained; keep an independent
copy for data that must survive repository/account loss.

## Capacity and cost boundary

This template uses public standard `ubuntu-24.04` runners, short bounded jobs and the
built-in scoped GITHUB_TOKEN. It does not enable paid runners, LFS, paid cache,
external AI/API services, GPU, or cloud VMs. Generic jobs are limited to 10 minutes
plus five minutes for evidence publication. Unity has its own 30/45-minute limits.
GitHub can queue jobs and apply abuse or platform limits; free public Actions is not
unlimited simultaneous hardware or a 24-hour VPS. More than 16 GB RAM, GPU work and
persistent interactive applications are unsupported here. A large legitimate task
must fit a reviewed stage's real memory/disk/time budget and persist useful results
between finite jobs. No automatic continuation loop exists.

Add a future task by reviewing its public inputs/license, resource estimate, finite
stages, source dependencies, output validation and recovery contract, then changing
the static code/catalog and workflow choices in a reviewed commit. A manifest alone
cannot authorize arbitrary execution or grant access to secrets.

## Unity plugin notes

Run the separate Unity workflow manually only after its three Personal activation
secrets are securely configured. The generic task neither reads nor receives them.
Missing secrets fail explicitly. `tasks/unity-proof/README.md` retains the original
proof's exact scope and action pins. Its embedded workflow is an inert original copy;
GitHub runs only `.github/workflows/unity-proof.yml`. Scripts run from the plugin
directory; GameCI project/output and artifact paths are adapted in that wrapper.
No existing game code or assets are included. Unity proof artifacts last seven days;
the generic Release publisher currently applies only to data-summary. Unity Release
archival is a separate future step, not claimed as implemented.

## Local verification

Run `python3 -m unittest discover -s tests -v` for the pure-Python source tests.
They do not claim GitHub scheduling, account licensing, Unity, APK or device execution.
Actual acceptance requires the first committed complete request, a separate checkpoint
request and a recover request, each with matching run/commit/hash evidence. Keep their
statuses separate from the subsequent Unity activation proof.

Official references: [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions),
[artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts),
[GameCI activation](https://game.ci/docs/github/activation/).
