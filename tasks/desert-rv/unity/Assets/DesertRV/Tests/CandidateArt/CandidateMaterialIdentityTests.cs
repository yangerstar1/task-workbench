using System;
using System.Reflection;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;

namespace DesertRV.Tests
{
    public sealed class CandidateMaterialIdentityTests
    {
        [Test] public void PersistedWeaponMaterialIdentitySurvivesNeutralSamplingAndRejectsImpostors()
        {
            string folder="Assets/__WeaponMaterialIdentity_"+Guid.NewGuid().ToString("N");
            GameObject visual=null;Material first=null,second=null,impostor=null;AnimationClip clip=null;
            try
            {
                Assert.That(AssetDatabase.CreateFolder("Assets",folder.Substring("Assets/".Length)),Is.Not.Empty);
                var shader=Shader.Find("Universal Render Pipeline/Lit");Assert.That(shader,Is.Not.Null);
                first=new Material(shader){name="Graphite_Parkerized_Candidate"};first.SetFloat("_Metallic",.6f);
                second=new Material(shader){name="Brushed_Steel_Candidate"};second.SetFloat("_Metallic",.85f);
                string firstNameBeforeCreate=first.name,secondNameBeforeCreate=second.name;
                AssetDatabase.CreateAsset(first,folder+"/Material_00.mat");AssetDatabase.CreateAsset(second,folder+"/Material_01.mat");
                Debug.Log("WEAPON_MATERIAL_NATIVE_REGRESSION beforeCreate="+firstNameBeforeCreate+","+secondNameBeforeCreate+" afterCreate="+first.name+","+second.name);
                AssetDatabase.SaveAssets();Resources.UnloadAsset(first);Resources.UnloadAsset(second);first=null;second=null;
                AssetDatabase.ImportAsset(folder+"/Material_00.mat",ImportAssetOptions.ForceUpdate|ImportAssetOptions.ForceSynchronousImport);
                AssetDatabase.ImportAsset(folder+"/Material_01.mat",ImportAssetOptions.ForceUpdate|ImportAssetOptions.ForceSynchronousImport);
                first=AssetDatabase.LoadAssetAtPath<Material>(folder+"/Material_00.mat");second=AssetDatabase.LoadAssetAtPath<Material>(folder+"/Material_01.mat");
                Assert.That(first.GetFloat("_Metallic"),Is.EqualTo(.6f).Within(.000001f));Assert.That(second.GetFloat("_Metallic"),Is.EqualTo(.85f).Within(.000001f));
                visual=new GameObject("Synthetic material identity regression, not art acceptance");var renderer=visual.AddComponent<MeshRenderer>();
                renderer.sharedMaterials=new[]{first,second};
                var type=Type.GetType("DesertRV.Editor.CandidateWeaponBinding, Assembly-CSharp-Editor",true);
                var capture=type.GetMethod("CaptureMaterialIdentity",BindingFlags.Public|BindingFlags.Static);
                var validate=type.GetMethod("ValidateMaterialIdentityUnchanged",BindingFlags.Public|BindingFlags.Static);
                var snapshot=capture.Invoke(null,new object[]{visual,folder,2});
                clip=new AnimationClip();
                AnimationUtility.SetEditorCurve(clip,EditorCurveBinding.FloatCurve("",typeof(Transform),"m_LocalPosition.x"),AnimationCurve.Linear(0,0,1,1));
                clip.SampleAnimation(visual,.5f);
                Assert.DoesNotThrow(()=>validate.Invoke(null,new[]{(object)visual,snapshot}));
                Assert.That(renderer.sharedMaterials[0]==first&&renderer.sharedMaterials[1]==second,Is.True);
                // A same-name transient clone must never pass a persistent identity gate.
                impostor=new Material(first){name=first.name};renderer.sharedMaterials=new[]{impostor,second};
                var failure=Assert.Throws<TargetInvocationException>(()=>validate.Invoke(null,new[]{(object)visual,snapshot}));
                Assert.That(failure.InnerException,Is.TypeOf<InvalidOperationException>());
                // Merely preserving the set is insufficient: swapping two persistent slots is rejected.
                renderer.sharedMaterials=new[]{second,first};
                failure=Assert.Throws<TargetInvocationException>(()=>validate.Invoke(null,new[]{(object)visual,snapshot}));
                Assert.That(failure.InnerException,Is.TypeOf<InvalidOperationException>());
                renderer.sharedMaterials=new[]{first,second};Assert.DoesNotThrow(()=>validate.Invoke(null,new[]{(object)visual,snapshot}));
            }
            finally
            {
                try {if(visual)UnityEngine.Object.DestroyImmediate(visual);if(clip)UnityEngine.Object.DestroyImmediate(clip);if(impostor)UnityEngine.Object.DestroyImmediate(impostor);}
                finally {if(AssetDatabase.IsValidFolder(folder))Assert.That(AssetDatabase.DeleteAsset(folder),Is.True,"Temporary material identity fixture cleanup failed.");}
            }
        }
    }
}
