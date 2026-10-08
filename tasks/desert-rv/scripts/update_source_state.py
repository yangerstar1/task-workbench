#!/usr/bin/env python3
"""Refresh the reviewable current-source inventory; never rewrites export provenance.

Run only on a clean source tree before opening Unity. Review the diff before commit.
The inventory deliberately has no current HEAD field: the run receipt binds the
checked-out Git commit, avoiding a self-referential commit/hash cycle.
"""
import json
from pathlib import Path
import verify_evidence as source


def main():
    source.require(source.sha(source.TASK / 'PUBLIC-EXPORT.json') == source.BASELINE_EXPORT_SHA,
                   'Historical manifest changed; do not rewrite its provenance')
    names = sorted(source.source_inventory())
    result = dict(schema='desert-rv-source-state/v1',
        baselineGameCommit=source.BASELINE_COMMIT,
        baselineExportManifestSha256=source.BASELINE_EXPORT_SHA,
        status='current-reviewed-source-not-native-execution-evidence',
        coverageRoots=list(source.SOURCE_ROOTS), coverageFiles=list(source.SOURCE_FILES),
        restoredFiles=[dict(path=source.FONT_PATH, sha256=source.FONT_SHA, size=16437340)],
        files=[dict(path=name, sha256=source.sha(source.ROOT / name),
                    size=(source.ROOT / name).stat().st_size) for name in names])
    (source.TASK / 'SOURCE-STATE.json').write_text(json.dumps(result, indent=2) + '\n')
    source.verify_source_state()
    print('Verified current-source inventory:', len(names), 'files. Review before committing.')


if __name__ == '__main__':
    main()
