"""Source-only checks of the narrow Unity package persistence boundary.

These tests do not run Unity, replace native evidence, or change the 10-case gate.
"""
import hashlib
from pathlib import Path
import re
import unittest

import strict_output as strict

ROOT = Path(__file__).resolve().parents[2] / 'unity'
EDITOR = ROOT / 'Assets/DesertRV/Editor'


class PackageSnapshotSourceTests(unittest.TestCase):
    def setUp(self):
        self.source = (EDITOR / 'CandidatePackageSnapshot.cs').read_text()

    def test_native_and_host_share_the_exact_four_byte_pins(self):
        found = re.findall(r'new FileRecord\{path=PackageRoot\+"([^"]+)",bytes=(\d+),sha256="([a-f0-9]{64})"\}', self.source)
        pins = {strict.PACKAGE_PREFIX.rstrip('/') + path: (int(size), sha) for path, size, sha in found}
        self.assertEqual(len(found), 4)
        self.assertEqual(pins, {path: (size, sha) for path, (size, sha, _) in strict.PACKAGE_FILES.items()})

    def test_native_guards_the_reviewed_project_control_bytes(self):
        for name, relative in [('ProjectManifestSha', 'Packages/manifest.json'), ('ProjectLockSha', 'Packages/packages-lock.json')]:
            pin = re.search(r'const string ' + name + r'="([a-f0-9]{64})";', self.source).group(1)
            self.assertEqual(pin, hashlib.sha256((ROOT / relative).read_bytes()).hexdigest())
        self.assertIn('Application.unityVersion=="6000.3.19f1"', self.source)
        self.assertIn('Sha("Packages/manifest.json")==ProjectManifestSha&&Sha("Packages/packages-lock.json")==ProjectLockSha', self.source)

    def test_actual_registered_package_and_resolved_identity_are_checked(self):
        for phrase in ['PackageInfo.FindForAssetPath(PackageRoot+"/Shaders/Lit.shader")',
                       'PackageInfo.FindForAssetPath(PackageRoot+"/Editor/AssetVersion.cs")',
                       'info.name==PackageName&&info.version==PackageVersion',
                       'info.source==PackageSource.BuiltIn', 'info.assetPath==PackageRoot',
                       'Path.IsPathRooted(info.resolvedPath)', 'Directory.Exists(info.resolvedPath)',
                       'metadata.name==PackageName&&metadata.version==PackageVersion',
                       'scriptInfo.source==info.source&&scriptInfo.assetPath==PackageRoot',
                       'Path.IsPathRooted(scriptInfo.resolvedPath)', 'Path.DirectorySeparatorChar==resolvedRoot']:
            self.assertIn(phrase, self.source)

    def test_declared_package_set_and_virtual_resolved_bytes_cannot_be_substituted(self):
        for phrase in ['expected.SetEquals(dependencies.Where(p=>p.StartsWith("Packages/",StringComparison.Ordinal)))',
                       'byte[] original=File.ReadAllBytes(pin.path),physical=File.ReadAllBytes(resolved)',
                       'original.LongLength==pin.bytes&&Hash(original)==pin.sha256&&original.SequenceEqual(physical)',
                       'payload.Add(pin.path,original)']:
            self.assertIn(phrase, self.source)

    def test_private_write_is_create_new_and_byte_checked(self):
        self.assertIn('const string SnapshotRoot="CandidatePackageSnapshot"', self.source)
        self.assertEqual(self.source.count('FileMode.CreateNew'), 2)
        self.assertIn('new UTF8Encoding(false)', self.source)
        self.assertIn('SequenceEqual(manifestBytes)', self.source)
        self.assertIn('SequenceEqual(payload[pin.path])', self.source)
        self.assertIn('Sha(SnapshotRoot+"/"+pin.path)==pin.sha256', self.source)
        for forbidden in ['FileMode.Create,', 'File.WriteAll', 'AssetDatabase.CreateAsset', 'AssetDatabase.Refresh', 'AssetDatabase.SaveAssets']:
            self.assertNotIn(forbidden, self.source)

    def test_snapshot_rejects_unapproved_tree_and_links(self):
        for phrase in ['FileAttributes.ReparsePoint', 'directories.Contains(relative)', 'files.Contains(relative)', 'found.SetEquals(files)']:
            self.assertIn(phrase, self.source)
        self.assertEqual(self.source.count('ValidateSnapshotTree();'), 2)

    def test_manifest_has_no_machine_paths_or_extra_public_payload(self):
        manifest = self.source.split('sealed class Manifest', 1)[1].split('[Serializable] sealed class PackageIdentity', 1)[0]
        self.assertIn('public int schema=1;', manifest)
        self.assertIn('public string editorVersion,packageName,packageVersion,packageSource,manifestSha256,lockSha256;', manifest)
        self.assertIn('public FileRecord[] files;', manifest)
        self.assertNotIn('resolvedPath', manifest)
        self.assertNotIn('absolutePath', manifest)

    def test_import_hook_is_after_native_save_before_original_dependency_hash(self):
        source = (EDITOR / 'JourneyCandidateArtImport.cs').read_text()
        hook = 'CandidatePackageSnapshot.Capture(dependencies);'
        self.assertEqual(source.count(hook), 1)
        save = source.index('AssetDatabase.SaveAssets(); AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);')
        deps = source.index('var dependencies=AssetDatabase.GetDependencies(report.prefab,true);report.dependencies=dependencies;')
        self.assertLess(save, deps)
        self.assertLess(deps, source.index(hook))
        self.assertLess(source.index(hook), source.index('report.dependencySha256=JourneyContentChecks.DependencySha256(report.prefab);'))

    def test_original_csharp_digest_uses_original_canonical_names(self):
        source = (EDITOR / 'JourneyContentChecks.cs').read_text()
        body = source.split('public static string DependencySha256(', 1)[1].split('\n        }', 1)[0]
        self.assertNotIn('CandidatePackageSnapshot', body)
        self.assertIn("Encoding.UTF8.GetBytes(file.Replace('\\\\','/'))", body)
        self.assertIn('File.ReadAllBytes(file)', body)
        self.assertIn('StringComparer.Ordinal', body)


if __name__ == '__main__':
    unittest.main()
