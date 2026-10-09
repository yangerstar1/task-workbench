"""Test-only private snapshot fixture using the four pinned official package files.

Other test assets/reports remain synthetic; this helper does not run Unity or
establish native provenance for a synthetic report.
"""
import hashlib
import json
from pathlib import Path
import strict_output as strict


def install_package_snapshot(project):
    project = Path(project)
    snapshot = project/'CandidatePackageSnapshot'
    snapshot.mkdir(parents=True, exist_ok=False)
    def write(name, value):
        path = project/name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value); return path
    # Use the genuinely reviewed project controls, independently pinned by both
    # native and host implementations. Synthetic reduced package graphs are not
    # evidence of the current project's dependency identity.
    controls = Path(__file__).resolve().parents[2]/'unity/Packages'
    (project/'Packages').mkdir(parents=True, exist_ok=True)
    manifest = project/'Packages/manifest.json'; lock = project/'Packages/packages-lock.json'
    manifest.write_bytes((controls/'manifest.json').read_bytes())
    lock.write_bytes((controls/'packages-lock.json').read_bytes())
    write('ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.3.19f1\n')
    rows = []
    for name, (size, expected, _) in strict.PACKAGE_FILES.items():
        source = Path(__file__).parent/'fixtures/urp-17.3.0'/name[len(strict.PACKAGE_PREFIX):]
        data = source.read_bytes()
        assert len(data) == size and hashlib.sha256(data).hexdigest() == expected
        target = snapshot/name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
        rows.append(dict(path=name, bytes=size, sha256=expected))
    (snapshot/'manifest.json').write_text(json.dumps(dict(schema=1, editorVersion='6000.3.19f1',
        packageName=strict.PACKAGE_NAME, packageVersion='17.3.0', packageSource='builtin',
        manifestSha256=strict.sha(manifest), lockSha256=strict.sha(lock), files=rows)))
    return snapshot
