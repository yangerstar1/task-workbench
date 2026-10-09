using System;
using System.IO;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.Build;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class CandidateLinuxBoundaryTests
    {
        static Type Builder => Type.GetType("DesertRV.Editor.JourneyCandidateLinuxBuild, Assembly-CSharp-Editor",true);
        static Type Identity => Type.GetType("DesertRV.JourneyCandidateLinuxIdentity, Assembly-CSharp",true);
        static object Call(string name, params object[] args) => Builder.GetMethod(name,BindingFlags.Public|BindingFlags.NonPublic|BindingFlags.Static).Invoke(null,args);
        static bool Profile(BuildTarget target, BuildOptions options, string[] defines) => (bool)Call("ValidBuildProfile",target,options,defines);
        [Test] public void ExactLinuxDevelopmentProfileAccepted() => Assert.IsTrue(Profile(BuildTarget.StandaloneLinux64,BuildOptions.Development,new[]{"DESERTRV_CANDIDATE_LINUX"}));
        [Test] public void MissingDefineRejected() => Assert.IsFalse(Profile(BuildTarget.StandaloneLinux64,BuildOptions.Development,new string[0]));
        [Test] public void ExtraDefineRejected() => Assert.IsFalse(Profile(BuildTarget.StandaloneLinux64,BuildOptions.Development,new[]{"DESERTRV_CANDIDATE_LINUX","OTHER"}));
        [Test] public void NonLinuxRejected() => Assert.IsFalse(Profile(BuildTarget.Android,BuildOptions.Development,new[]{"DESERTRV_CANDIDATE_LINUX"}));
        [Test] public void NonDevelopmentRejected() => Assert.IsFalse(Profile(BuildTarget.StandaloneLinux64,BuildOptions.None,new[]{"DESERTRV_CANDIDATE_LINUX"}));
        [Test] public void ExtraBuildOptionsRejected() => Assert.IsFalse(Profile(BuildTarget.StandaloneLinux64,BuildOptions.Development|BuildOptions.AutoRunPlayer,new[]{"DESERTRV_CANDIDATE_LINUX"}));
        [Test] public void OrdinaryEntrypointHasNoCandidateLease() => Assert.IsFalse((bool)Call("AllowsCandidateBuild",new object[]{null}));
        [Test] public void RuntimeCapabilityInactiveInEditor() => Assert.IsFalse((bool)Identity.GetProperty("Active").GetValue(null));
        [Test] public void EmptySerializedIdentityRejected()
        {
            var go=new GameObject("identity-fixture");try { var component=go.AddComponent(Identity);Assert.IsFalse((bool)Identity.GetMethod("ValidIdentity").Invoke(component,null)); }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
        [Test] public void NullManifestCannotSupplyRealAssets() => Assert.IsFalse((bool)Identity.GetMethod("UnapprovedContent").Invoke(null,new object[]{null}));
        [Test] public void ProductionGateStillRejectsUnapprovedFormalScenes()
        {
            var old=EditorBuildSettings.scenes;const string settings="ProjectSettings/EditorBuildSettings.asset";var bytes=File.ReadAllBytes(settings);
            var checks=Type.GetType("DesertRV.Editor.JourneyContentChecks, Assembly-CSharp-Editor",true);
            var field=checks.GetField("ValidatedBuildFingerprint",BindingFlags.Static|BindingFlags.NonPublic);var fingerprint=field.GetValue(null);
            try
            {
                field.SetValue(null,null);EditorBuildSettings.scenes=new[]{new EditorBuildSettingsScene("Assets/DesertRV/Scenes/Journey/JourneyBootstrap.unity",true)};
                var gate=Type.GetType("DesertRV.Editor.JourneyProductionBuildGate, Assembly-CSharp-Editor",true);
                var error=Assert.Throws<TargetInvocationException>(()=>gate.GetMethod("OnPreprocessBuild").Invoke(Activator.CreateInstance(gate),new object[]{null}));
                Assert.IsInstanceOf<BuildFailedException>(error.InnerException);
            }
            finally { EditorBuildSettings.scenes=old;File.WriteAllBytes(settings,bytes);field.SetValue(null,fingerprint); }
        }
        static object Request(string[] files,string[] directories)
        {
            var type=Builder.GetNestedType("Request");var result=Activator.CreateInstance(type);
            var field=type.GetField("files");var itemType=field.FieldType.GetElementType();var items=Array.CreateInstance(itemType,files.Length);
            for(int i=0;i<files.Length;i++) { var item=Activator.CreateInstance(itemType);itemType.GetField("path").SetValue(item,"tasks/desert-rv/unity/"+files[i]);items.SetValue(item,i); }
            field.SetValue(result,items);type.GetField("directories").SetValue(result,directories);return result;
        }
        static void InventoryFixture(Action<string,object> test)
        {
            string root=Path.Combine(Path.GetTempPath(),"journey-linux-inventory-"+Guid.NewGuid().ToString("N"));
            try
            {
                foreach(var name in new[]{"Assets","Packages","ProjectSettings"})Directory.CreateDirectory(Path.Combine(root,name));
                File.WriteAllText(Path.Combine(root,"Assets","Real.asset"),"fixture");File.WriteAllText(Path.Combine(root,"Assets","Real.asset.meta"),"fixture-meta");
                test(root,Request(new[]{"Assets/Real.asset","Assets/Real.asset.meta"},new string[0]));
            }
            finally { if(Directory.Exists(root))Directory.Delete(root,true); }
        }
        static void RejectInventory(string root,object request)
        {
            var error=Assert.Throws<TargetInvocationException>(()=>Call("VerifyInventory",request,root));Assert.IsInstanceOf<BuildFailedException>(error.InnerException);
        }
        [Test] public void ExactPhysicalInventoryAccepted() => InventoryFixture((root,request)=>Call("VerifyInventory",request,root));
        [Test] public void UnlistedExecutableScriptRejected() => InventoryFixture((root,request)=>{File.WriteAllText(Path.Combine(root,"Assets","Injected.cs"),"class Executable {}");RejectInventory(root,request);});
        [Test] public void UnlistedMetaRejected() => InventoryFixture((root,request)=>{File.WriteAllText(Path.Combine(root,"Assets","Injected.meta"),"guid");RejectInventory(root,request);});
        [Test] public void MissingSceneMetaRejected() => InventoryFixture((root,request)=>{File.Delete(Path.Combine(root,"Assets","Real.asset.meta"));RejectInventory(root,request);});
        [Test] public void UndeclaredEmptyDirectoryRejected() => InventoryFixture((root,request)=>{Directory.CreateDirectory(Path.Combine(root,"Assets","Extra"));RejectInventory(root,request);});
        [Test] public void AtomicJsonReplacementKeepsOnlyCompleteLatestFile()
        {
            string root=Path.Combine(Path.GetTempPath(),"journey-linux-json-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
            try { string path=Path.Combine(root,"receipt.json");Call("PersistJson",path,"{\"phase\":1}");Call("PersistJson",path,"{\"phase\":2}");Assert.AreEqual("{\"phase\":2}",File.ReadAllText(path));Assert.IsFalse(File.Exists(path+".tmp")); }
            finally { Directory.Delete(root,true); }
        }
    }
}
