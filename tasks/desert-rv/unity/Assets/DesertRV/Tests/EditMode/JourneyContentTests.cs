using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace DesertRV.Tests
{
    // Reflection preserves the repository's test-asmdef isolation from Assembly-CSharp.
    public sealed class JourneyContentTests
    {
        static Type EditorType(string name) => Type.GetType("DesertRV.Editor."+name+", Assembly-CSharp-Editor",true);
        static Type RuntimeType(string name) => Type.GetType("DesertRV."+name+", Assembly-CSharp",true);
        static object Field(Type type,string name) => type.GetField(name,BindingFlags.Public|BindingFlags.Static).GetValue(null);
        static List<string> Check(UnityEngine.Object manifest)
        { var errors = new List<string>(); EditorType("JourneyContentChecks").GetMethod("ValidateManifest").Invoke(null,new object[] {manifest,errors}); return errors; }
        [Test] public void Manifest_MissingAssetFailsClosed()
        { Assert.That(Check(null).Any(e=>e.Contains("Missing JourneyContent")),Is.True); }
        [Test] public void Manifest_EmptyReviewsCannotPass()
        {
            var manifest = ScriptableObject.CreateInstance(RuntimeType("JourneyContentManifest"));
            try { var errors=Check(manifest); Assert.That(errors.Any(e=>e.Contains("Pouncer: real prefab missing")),Is.True); Assert.That(errors.Any(e=>e.Contains("Armored: real prefab missing")),Is.True); Assert.That(errors.Any(e=>e.Contains("Weapon viewmodel: real prefab missing")),Is.True); }
            finally { UnityEngine.Object.DestroyImmediate(manifest); }
        }
        [Test] public void Manifest_ApprovalBooleanDoesNotReplaceAssetEvidence()
        {
            var manifest=ScriptableObject.CreateInstance(RuntimeType("JourneyContentManifest"));
            try
            {
                foreach (string key in new[] {"pouncer","armored","weapon"})
                { var review=manifest.GetType().GetField(key).GetValue(manifest); review.GetType().GetField("accepted").SetValue(review,true); }
                Assert.That(Check(manifest).Count,Is.GreaterThanOrEqualTo(3));
            }
            finally { UnityEngine.Object.DestroyImmediate(manifest); }
        }
        [Test] public void Authoring_UsesNewPathsAndPreservesLegacyScenes()
        {
            var type=EditorType("JourneySceneAuthoring"); var paths=(string[])Field(type,"RegionPaths");
            Assert.That(paths,Has.Length.EqualTo(3)); Assert.That(paths.Distinct().Count(),Is.EqualTo(3));
            foreach(string path in paths) { Assert.That(path,Does.StartWith("Assets/DesertRV/Scenes/Journey/")); Assert.That(path,Is.Not.EqualTo("Assets/DesertRV/Scenes/TraversalHarness.unity")); Assert.That(path,Is.Not.EqualTo(Field(type,"SourcePath"))); }
            Assert.That(Field(type,"BootstrapPath"),Is.EqualTo("Assets/DesertRV/Scenes/Journey/JourneyBootstrap.unity"));
        }
        [Test] public void Authoring_OffsetsLeaveFiniteCompactRegions()
        { var offsets=(double[])Field(EditorType("JourneySceneAuthoring"),"RegionOffsets"); Assert.That(offsets,Is.EqualTo(new double[]{0,100,200})); }
        [Test] public void Animator_RequiresAllSevenRuntimeNamedStates()
        { Assert.That((string[])Field(EditorType("JourneyContentChecks"),"EnemyStates"),Is.EquivalentTo(new[]{"Idle","Walk","Windup","Attack","Recover","Hit","Death"})); }
        [Test] public void Evidence_MissingDependencyCannotProduceReviewDigest()
        { var result=EditorType("JourneyContentChecks").GetMethod("DependencySha256").Invoke(null,new object[]{"Assets/does-not-exist.prefab"}); Assert.That(result,Is.EqualTo("")); }
    }
}
