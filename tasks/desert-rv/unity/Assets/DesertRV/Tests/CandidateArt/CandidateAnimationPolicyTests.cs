using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
namespace DesertRV.Tests
{
    public sealed class CandidateAnimationPolicyTests
    {
        static bool Call(string method,params object[] args)=> (bool)Type.GetType("DesertRV.Editor.JourneyCandidateArtImport, Assembly-CSharp-Editor",true).GetMethod(method,BindingFlags.Static|BindingFlags.NonPublic).Invoke(null,args);
        [Test] public void RenderTargetCleanupDetachesCameraBeforeDestroy()
        {
            var host=new GameObject("Candidate render cleanup regression");var camera=host.AddComponent<Camera>();
            RenderTexture target=null;var previous=RenderTexture.active;
            try
            {
                target=new RenderTexture(16,16,16);Assert.That(target.Create(),Is.True);
                camera.targetTexture=target;RenderTexture.active=target;
                var method=Type.GetType("DesertRV.Editor.JourneyCandidateArtCapture, Assembly-CSharp-Editor",true).GetMethod("ReleaseCandidateRenderTarget",BindingFlags.Static|BindingFlags.NonPublic);
                method.Invoke(null,new object[]{camera,target});
                Assert.That((bool)camera.targetTexture,Is.False);Assert.That((bool)RenderTexture.active,Is.False);Assert.That((bool)target,Is.False);
            }
            finally
            {
                try {camera.targetTexture=null;RenderTexture.active=previous;}
                finally {try {if(target){target.Release();UnityEngine.Object.DestroyImmediate(target);}}finally {UnityEngine.Object.DestroyImmediate(host);}}
            }
        }
        [Test] public void OpenCoreEmissionSurvivesRealSaveReimportAndReload()
        {
            string path="Assets/__OpenCoreEmission_"+Guid.NewGuid().ToString("N")+".mat";
            Material closed=null;Material loaded=null;
            try
            {
                var shader=Shader.Find("Universal Render Pipeline/Lit");Assert.That(shader,Is.Not.Null);
                closed=new Material(shader);closed.SetColor("_EmissionColor",Color.black);
                closed.globalIlluminationFlags=MaterialGlobalIlluminationFlags.EmissiveIsBlack;closed.DisableKeyword("_EMISSION");
                var emission=new Color(.12f,.025f,.002f,1);var baseColor=new Color(.85f,.255f,.025f,1);
                var method=Type.GetType("DesertRV.Editor.JourneyCandidateArtImport, Assembly-CSharp-Editor",true).GetMethod("CreatePersistedOpenCoreMaterial",BindingFlags.Static|BindingFlags.NonPublic);
                loaded=(Material)method.Invoke(null,new object[]{closed,baseColor,emission,path});
                Assert.That(UnityEditor.EditorUtility.IsPersistent(loaded),Is.True);
                UnityEditor.AssetDatabase.SaveAssets();Resources.UnloadAsset(loaded);loaded=null;
                UnityEditor.AssetDatabase.ImportAsset(path,UnityEditor.ImportAssetOptions.ForceUpdate|UnityEditor.ImportAssetOptions.ForceSynchronousImport);
                loaded=UnityEditor.AssetDatabase.LoadAssetAtPath<Material>(path);
                Assert.That(loaded,Is.Not.Null);Assert.That(loaded.IsKeywordEnabled("_EMISSION"),Is.True);
                Assert.That((loaded.globalIlluminationFlags & MaterialGlobalIlluminationFlags.AnyEmissive)!=0,Is.True);
                Assert.That((loaded.globalIlluminationFlags & MaterialGlobalIlluminationFlags.EmissiveIsBlack)==0,Is.True);
                var actual=loaded.GetColor("_EmissionColor");Assert.That(actual.r,Is.EqualTo(emission.r).Within(.000001f));Assert.That(actual.g,Is.EqualTo(emission.g).Within(.000001f));Assert.That(actual.b,Is.EqualTo(emission.b).Within(.000001f));
                var actualBase=loaded.GetColor("_BaseColor");Assert.That(actualBase.r,Is.EqualTo(baseColor.r).Within(.000001f));Assert.That(actualBase.g,Is.EqualTo(baseColor.g).Within(.000001f));Assert.That(actualBase.b,Is.EqualTo(baseColor.b).Within(.000001f));
                Assert.That(closed.IsKeywordEnabled("_EMISSION"),Is.False);Assert.That(closed.GetColor("_EmissionColor"),Is.EqualTo(Color.black));
                Assert.That(closed.globalIlluminationFlags,Is.EqualTo(MaterialGlobalIlluminationFlags.EmissiveIsBlack));
            }
            finally
            {
                try {if(System.IO.File.Exists(path)||System.IO.File.Exists(path+".meta"))Assert.That(UnityEditor.AssetDatabase.DeleteAsset(path),Is.True,"Temporary emission material cleanup failed.");}
                finally {if(closed)UnityEngine.Object.DestroyImmediate(closed);}
            }
        }
        [Test] public void OnlyArmoredAttackGetsTheSourceLoopException()
        {
            Assert.That(Call("AllowedLoop","armored","Attack"),Is.True);
            foreach(string kind in new[]{"pouncer","weapon"})Assert.That(Call("AllowedLoop",kind,"Attack"),Is.False);
            foreach(string state in new[]{"Windup","Recover","Hit","Death","Fire","Reload"})Assert.That(Call("AllowedLoop","armored",state),Is.False);
            Assert.That(Call("AllowedLoop","weapon","Idle"),Is.True);Assert.That(Call("AllowedLoop","pouncer","Walk"),Is.True);
        }
        [Test] public void MissingNativeAnimatorGetsCreatedAndReused()
        {
            var root=new GameObject("Missing native Animator regression");
            try
            {
                var method=Type.GetType("DesertRV.Editor.JourneyCandidateArtImport, Assembly-CSharp-Editor",true).GetMethod("EnsureNativeAnimator",BindingFlags.Static|BindingFlags.NonPublic);
                Assert.That((bool)root.GetComponent<Animator>(),Is.False);
                var first=(Animator)method.Invoke(null,new object[]{root.transform});
                Assert.That((bool)first,Is.True);first.applyRootMotion=false;
                var reused=(Animator)method.Invoke(null,new object[]{root.transform});
                Assert.That(reused==first,Is.True);
                Assert.That(root.GetComponents<Animator>().Length,Is.EqualTo(1));
                UnityEngine.Object.DestroyImmediate(first);
                Assert.That((bool)first,Is.False);
                var replacement=(Animator)method.Invoke(null,new object[]{root.transform});
                Assert.That((bool)replacement,Is.True);replacement.applyRootMotion=false;
                Assert.That(root.GetComponents<Animator>().Length,Is.EqualTo(1));
            }
            finally {UnityEngine.Object.DestroyImmediate(root);}
        }
        [Test] public void EqualKeyValuesDoNotExcuseUnsafeTangents()
        {
            foreach(float t in new[]{float.NaN,.000001f,-.000001f,1f,-1f})Assert.That(Call("SafeConstantTangent",t),Is.False);
            foreach(float t in new[]{0f,float.PositiveInfinity,float.NegativeInfinity})Assert.That(Call("SafeConstantTangent",t),Is.True);
        }
    }
}
