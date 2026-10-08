using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class JourneyDiagnosticScopeTests
    {
        static Type T(string name) => Type.GetType("DesertRV." + name + ", Assembly-CSharp", true);
        static object Call(object obj, string name, params object[] args) => obj.GetType().GetMethod(name).Invoke(obj, args);
        static void Set(object obj, string field, object value) => obj.GetType().GetField(field).SetValue(obj, value);
        static object Scope(string method, params object[] args) => T("Editor.JourneyDiagnosticScope").GetMethod(method).Invoke(null, args);
        [TearDown] public void CloseScope() => Scope("Close");
        [Test] public void DiagnosticScope_DefaultClosedAndCannotOpenOutsidePlayMode()
        {
            Scope("Close");
            Assert.That(T("Editor.JourneyDiagnosticScope").GetProperty("Active").GetValue(null), Is.False);
            var e = Assert.Throws<TargetInvocationException>(() => Scope("Open", "not-a-request.json"));
            Assert.That(e.InnerException, Is.TypeOf<InvalidOperationException>());
        }
        [Test] public void DiagnosticScope_ClosedCannotValidateRegion()
        {
            Scope("Close"); object[] args = { null, null };
            Assert.That(Scope("ValidateRegion", args), Is.False);
            Assert.That(args[1].ToString(), Does.Contain("closed"));
        }
        [Test] public void DiagnosticScope_RejectsUnlabeledOrUnpinnedRequest()
        {
            var requestType = T("Editor.JourneyDiagnosticScope").GetNestedType("Request");
            var request = Activator.CreateInstance(requestType);
            object[] args = { request, new string('a', 40), null };
            Assert.That(Scope("CheckRequest", args), Is.False);
        }
        [Test] public void PinnedSourceByteChange_IsRejectedBeforeLoading()
        {
            string path = "Assets/DesertRV/diagnostic-hash-test-" + Guid.NewGuid().ToString("N") + ".txt";
            try
            {
                System.IO.File.WriteAllText(path, "first source bytes");
                var scopeType = T("Editor.JourneyDiagnosticScope");
                var pin = Activator.CreateInstance(scopeType.GetNestedType("Pin"));
                Set(pin, "path", path); Set(pin, "kind", "source"); Set(pin, "sha256", Scope("HashFile", path));
                var request = Activator.CreateInstance(scopeType.GetNestedType("Request"));
                Set(request, "label", "EDITOR_DIAGNOSTIC_UNAPPROVED_CONTENT"); Set(request, "sourceCommit", new string('a', 40));
                var pins = Array.CreateInstance(pin.GetType(), 1); pins.SetValue(pin, 0); Set(request, "files", pins);
                System.IO.File.WriteAllText(path, "changed source bytes");
                object[] args = { request, new string('a', 40), null };
                Assert.That(Scope("CheckRequest", args), Is.False);
                Assert.That(args[2].ToString(), Does.StartWith("Changed file hash:"));
            }
            finally { if (System.IO.File.Exists(path)) System.IO.File.Delete(path); }
        }
        [Test] public void StaleSceneOrModelDependencyHash_IsRejected()
        {
            string path = "Assets/DesertRV/diagnostic-dependency-test-" + Guid.NewGuid().ToString("N") + ".txt";
            try
            {
                System.IO.File.WriteAllText(path, "pinned bytes but changed dependency");
                var scopeType = T("Editor.JourneyDiagnosticScope");
                var pin = Activator.CreateInstance(scopeType.GetNestedType("Pin"));
                Set(pin, "path", path); Set(pin, "kind", "scene"); Set(pin, "sha256", Scope("HashFile", path)); Set(pin, "dependencyHash", "stale");
                var request = Activator.CreateInstance(scopeType.GetNestedType("Request"));
                Set(request, "label", "EDITOR_DIAGNOSTIC_UNAPPROVED_CONTENT"); Set(request, "sourceCommit", new string('a', 40));
                var pins = Array.CreateInstance(pin.GetType(), 1); pins.SetValue(pin, 0); Set(request, "files", pins);
                object[] args = { request, new string('a', 40), null };
                Assert.That(Scope("CheckRequest", args), Is.False);
                Assert.That(args[2].ToString(), Does.StartWith("Changed scene/model dependency hash:"));
            }
            finally { if (System.IO.File.Exists(path)) System.IO.File.Delete(path); }
        }
#if UNITY_EDITOR_LINUX
        [Test] public void PinnedPath_RejectsSymlinkFileAndParentChain()
        {
            string folder = "Assets/DesertRV/diagnostic-link-test-" + Guid.NewGuid().ToString("N");
            string target = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "diagnostic-target-" + Guid.NewGuid().ToString("N"));
            System.IO.Directory.CreateDirectory(folder); System.IO.Directory.CreateDirectory(target);
            System.IO.File.WriteAllText(System.IO.Path.Combine(target, "source.txt"), "external bytes");
            try
            {
                foreach (var pair in new[] {
                    new[] { System.IO.Path.Combine(target, "source.txt"), folder + "/file-link" },
                    new[] { target, folder + "/directory-link" } })
                {
                    var start = new System.Diagnostics.ProcessStartInfo("/bin/ln") { UseShellExecute = false };
                    start.Arguments = "-s " + pair[0] + " " + pair[1]; // Generated GUID/temp paths contain no user-controlled shell content.
                    using (var proc = System.Diagnostics.Process.Start(start)) { proc.WaitForExit(); Assert.That(proc.ExitCode, Is.Zero); }
                }
                object[] fileArgs = { folder + "/file-link", null };
                object[] dirArgs = { folder + "/directory-link/source.txt", null };
                Assert.That(Scope("IsPinnedPathSafe", fileArgs), Is.False);
                Assert.That(Scope("IsPinnedPathSafe", dirArgs), Is.False);
            }
            finally
            {
                System.IO.File.Delete(folder + "/file-link");
                System.IO.Directory.Delete(folder + "/directory-link");
                System.IO.Directory.Delete(folder);
                System.IO.Directory.Delete(target, true);
            }
        }
#endif
        [Test] public void StructureValidation_DoesNotGrantProductionApproval()
        {
            var root = new GameObject("structure fixture, never gameplay evidence");
            try
            {
                var binding = root.AddComponent(T("RegionBinding"));
                Set(binding, "region", 3); Set(binding, "spawn", root.transform);
                var exit = root.AddComponent<BoxCollider>();
                Set(binding, "exitVolume", exit); Set(binding, "safeZone", exit);
                Set(binding, "powerPoint", root.transform); Set(binding, "powerSurface", exit);
                var enemyGo = new GameObject("unit-test actor"); enemyGo.transform.SetParent(root.transform);
                var enemy = enemyGo.AddComponent(T("BeastActor"));
                var enemies = Array.CreateInstance(T("BeastActor"), 1); enemies.SetValue(enemy, 0);
                var wave = Activator.CreateInstance(T("RegionWave")); Set(wave, "enemies", enemies);
                var waves = Array.CreateInstance(T("RegionWave"), 1); waves.SetValue(wave, 0); Set(binding, "waves", waves);
                object[] reason = { null };
                Assert.That(Call(binding, "ValidateStructure", reason), Is.True, reason[0] as string);
                Assert.That(Call(binding, "Validate", reason), Is.False, "Structure must not satisfy visual approval.");
                Assert.That(binding.GetType().GetField("environmentVerified").GetValue(binding), Is.False);
                Assert.That(binding.GetType().GetField("combatAssetsVerified").GetValue(binding), Is.False);
                Set(binding, "spawn", null);
                Assert.That(Call(binding, "ValidateStructure", reason), Is.False, "Diagnostics must reject broken structure.");
            }
            finally { UnityEngine.Object.DestroyImmediate(root); }
        }
    }
}
