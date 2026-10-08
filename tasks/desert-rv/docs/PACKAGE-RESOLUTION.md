# Pin the actual Unity 6000.3.19f1 package graph

Evidence: https://github.com/yangerstar1/task-workbench/actions/runs/37828779077, artifact 11572264929. ZIP SHA256: `76b7750763706ddc0e65d769d140bd3f4382acccd6f06f55d6e55580a0588699`.

This run had **NATIVE_FAILED / DEPENDENCY_EVIDENCE_ONLY**: C# test compilation failed before NUnit or environment rendering. The independent, strict allowlist exporter nevertheless captured Unity's actual resolved dependency graph. It is not test, image, scene, or art acceptance.

The two source changes were package configuration only. Unity added official Linux arm64/x86_64 SDK and Linux toolchain packages at 1.1.0, with sysroot.base 1.1.0. It resolved Test Framework to the Editor-bound 1.6.0 and NUnit to Editor-bound 2.0.5 rather than the obsolete registry versions in the original lock.

The sanitized graph was serialized and independently matched BOTH native post-run raw SHA256 values before adoption:
- manifest: `ff5edd2247eb107f03c05a21ed1a6be81108a5bb50273c6c4fd33bac489e4651`
- lock: `384d89273ce2266897a6cce8f348f8d20bfd58f59506ec713a4831abdae8eb74`

The checked-in lock now uses that resolved graph. The manifest also explicitly requests the matching core Test Framework 1.6.0 instead of retaining an obsolete 1.4.6 request that the Editor overrides. All SDK entries retain their exact observed official registry versions. This is a prospective reproducibility fix; a fresh run still must prove the files remain unchanged.

The historical PUBLIC-EXPORT manifest stays immutable. SOURCE-STATE is refreshed for current code. No original scene, shader, material, model, texture, GUID, or ProjectSettings is changed. The full before/after tracked-byte protection remains mandatory; no post-run restore, wildcard exemption, or test-success substitution is permitted.
