using System;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEditor;
using UnityEditor.SceneManagement;
namespace DesertRV.Tests
{
    public sealed class CandidateArtImportTests
    {
        [Serializable] sealed class Mode { public string mode,kind,id; public ColliderBindings bindings; }
        [Serializable] sealed class ColliderBindings { public Vector3 colliderCenter; public float colliderHeight,colliderRadius; }
        static void RequireSweepGeometry(GameObject instance,float bottom,float top,float radius)
        {
            var actorType=Type.GetType("DesertRV.BeastActor, Assembly-CSharp",true);
            var actor=instance.GetComponent(actorType);
            var method=actorType.GetMethod("TryGetSweepCapsule",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic);
            object[] args={Vector3.zero,Vector3.zero,0f};
            Assert.That((bool)method.Invoke(actor,args),Is.True);
            Assert.That(Vector3.Distance((Vector3)args[0],instance.transform.TransformPoint(Vector3.up*bottom)),Is.LessThan(.00001f));
            Assert.That(Vector3.Distance((Vector3)args[1],instance.transform.TransformPoint(Vector3.up*top)),Is.LessThan(.00001f));
            Assert.That((float)args[2],Is.EqualTo(radius));
        }
        static void RequireSweepShapeRegression()
        {
            var scene=EditorSceneManager.NewPreviewScene(); GameObject instance=null;
            try
            {
                instance=new GameObject("native capsule shape regression");
                EditorSceneManager.MoveGameObjectToScene(instance,scene);
                var actor=(Behaviour)instance.AddComponent(Type.GetType("DesertRV.BeastActor, Assembly-CSharp",true));actor.enabled=false;
                var capsule=instance.AddComponent<CapsuleCollider>();
                foreach(bool armored in new[]{false,true})
                {
                    capsule.center=new Vector3(0,armored?.775f:.725f,0);capsule.height=armored?1.55f:1.27f;capsule.radius=armored?.5f:.36f;
                    instance.transform.SetPositionAndRotation(Vector3.zero,Quaternion.identity);Physics.SyncTransforms();
                    RequireSweepGeometry(instance,armored?.5f:.45f,armored?1.05f:1f,capsule.radius);
                    Assert.That(capsule.bounds.min.y,Is.EqualTo(armored?0f:.09f).Within(.00001f));
                    Assert.That(capsule.bounds.max.y,Is.EqualTo(armored?1.55f:1.36f).Within(.00001f));
                    instance.transform.SetPositionAndRotation(new Vector3(3,2,-4),Quaternion.Euler(11,37,9));
                    RequireSweepGeometry(instance,armored?.5f:.45f,armored?1.05f:1f,capsule.radius);
                }
                var query=actor.GetType().GetMethod("TryGetSweepCapsule",System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic);
                object[] rejected={Vector3.zero,Vector3.zero,0f};
                instance.transform.localScale=new Vector3(1,2,1);
                Assert.That((bool)query.Invoke(actor,rejected),Is.False,"Unsupported scale must fail closed.");
                instance.transform.localScale=Vector3.one;capsule.direction=0;
                Assert.That((bool)query.Invoke(actor,rejected),Is.False,"Unsupported direction must fail closed.");
                capsule.direction=1;capsule.enabled=false;
                Assert.That((bool)query.Invoke(actor,rejected),Is.False,"Disabled capsule must fail closed.");
                UnityEngine.Object.DestroyImmediate(capsule);
                Assert.That((bool)query.Invoke(actor,rejected),Is.False,"Missing capsule must fail closed.");
            }
            finally { if(instance)UnityEngine.Object.DestroyImmediate(instance);EditorSceneManager.ClosePreviewScene(scene); }
        }
        static void RequireArmoredCapsuleContract()
        {
            var c=JsonUtility.FromJson<Mode>(File.ReadAllText("CandidateImportInput/contract.json"));
            if(c.mode!="STRICT_BINDING" || c.kind!="armored")return;
            Assert.That(c.bindings.colliderCenter,Is.EqualTo(new Vector3(0,.775f,0)));
            Assert.That(c.bindings.colliderHeight,Is.EqualTo(1.55f));
            Assert.That(c.bindings.colliderRadius,Is.EqualTo(.5f));
            string path="Assets/DesertRV/CandidateArtImports/"+c.id+"/Candidate.prefab";
            var prefab=AssetDatabase.LoadAssetAtPath<GameObject>(path);
            Assert.That(prefab,Is.Not.Null,"Persisted candidate must exist.");
            var scene=EditorSceneManager.NewPreviewScene(); GameObject instance=null;
            try
            {
                instance=(GameObject)PrefabUtility.InstantiatePrefab(prefab,scene);
                foreach(var behaviour in instance.GetComponentsInChildren<MonoBehaviour>(true))behaviour.enabled=false;
                instance.SetActive(true); Physics.SyncTransforms();
                Assert.That(instance.transform.position,Is.EqualTo(Vector3.zero));
                Assert.That(instance.transform.localScale,Is.EqualTo(Vector3.one));
                Assert.That(Quaternion.Angle(instance.transform.rotation,Quaternion.identity),Is.LessThan(.001f));
                var capsule=instance.GetComponent<CapsuleCollider>();
                Assert.That(capsule,Is.Not.Null); Assert.That(capsule.direction,Is.EqualTo(1));
                Assert.That(capsule.center,Is.EqualTo(c.bindings.colliderCenter));
                Assert.That(capsule.height,Is.EqualTo(c.bindings.colliderHeight));
                Assert.That(capsule.radius,Is.EqualTo(c.bindings.colliderRadius));
                RequireSweepGeometry(instance,.5f,1.05f,.5f);
                Assert.That(capsule.bounds.min.y,Is.EqualTo(0).Within(.00001f),"Native capsule bottom must meet root ground.");
                Assert.That(capsule.bounds.max.y,Is.EqualTo(1.55f).Within(.00001f));
                Debug.Log("CANDIDATE_ARMORED_CAPSULE bottom="+capsule.bounds.min.y+" top="+capsule.bounds.max.y+" contract="+c.id);
            }
            finally { if(instance)UnityEngine.Object.DestroyImmediate(instance); EditorSceneManager.ClosePreviewScene(scene); }
        }
        static void RequireNestedWeaponDiagnosticsJsonRoundTrip()
        {
            // Exercise the actual nested Sample through Unity's serializer. A custom
            // diagnostics struct without [Serializable] silently loses these fields.
            var sampleType=Type.GetType("DesertRV.Editor.CandidateWeaponDiagnostics+Sample, Assembly-CSharp-Editor",true);
            var sample=Activator.CreateInstance(sampleType);
            var diagnosticsType=sampleType.GetField("left").FieldType;
            Assert.That(diagnosticsType.GetFields(System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.Public).Length,Is.EqualTo(12));
            string[] measures={"upperLength","foreLength","wristGap","shoulderDrift","targetDrift","targetDistance","expectedUpperLength","expectedForeLength"};
            foreach(string side in new[]{"left","right"})
            {
                var diagnostics=Activator.CreateInstance(diagnosticsType);
                diagnosticsType.GetField("solved").SetValue(diagnostics,side=="left");
                diagnosticsType.GetField("measured").SetValue(diagnostics,true);
                diagnosticsType.GetField("measurementsFinite").SetValue(diagnostics,true);
                diagnosticsType.GetField("reason").SetValue(diagnostics,side+"-serialization-probe");
                for(int i=0;i<measures.Length;i++)diagnosticsType.GetField(measures[i]).SetValue(diagnostics,(side=="left"?.01f:.02f)*(i+1));
                sampleType.GetField(side).SetValue(sample,diagnostics);
            }
            string json=JsonUtility.ToJson(sample);
            var restored=JsonUtility.FromJson(json,sampleType);
            foreach(string side in new[]{"left","right"})
            {
                Assert.That(json,Does.Contain("\""+side+"\":"),"Actual nested arm diagnostics must be serialized.");
                var expected=sampleType.GetField(side).GetValue(sample);var actual=sampleType.GetField(side).GetValue(restored);
                foreach(var field in diagnosticsType.GetFields(System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.Public))
                    Assert.That(field.GetValue(actual),Is.EqualTo(field.GetValue(expected)),"Nested diagnostics round-trip: "+side+"."+field.Name);
            }
            Debug.Log("CANDIDATE_WEAPON_SAMPLE_SERIALIZATION sides=2 measuredFieldsPerSide=12 roundTrip=true");
        }
        [Test] public void ExecutePinnedDiscoveryOrBindingDiagnostics()
        {
            RequireNestedWeaponDiagnosticsJsonRoundTrip();
            RequireSweepShapeRegression();
            var scan=Type.GetType("DesertRV.Editor.JourneyCandidateArtDiscovery, Assembly-CSharp-Editor",true).GetMethod("ContainsStrictRootFields");
            Assert.That(scan.Invoke(null,new object[]{"{\"mode\":\"DISCOVERY_ONLY\",\"files\":[]}"}),Is.False);
            Assert.That(scan.Invoke(null,new object[]{"{\"note\":\"bindings\",\"nested\":{\"clips\":null}}"}),Is.False);
            foreach(string key in new[]{"bindings","clips","materials","weapon"})
                foreach(string value in new[]{"null","[]","{}"})
                    Assert.That(scan.Invoke(null,new object[]{"{\""+key+"\":"+value+"}"}),Is.True);
            Assert.That(scan.Invoke(null,new object[]{"{\"\\u0062indings\":null}"}),Is.True);
            var mode=JsonUtility.FromJson<Mode>(File.ReadAllText("CandidateImportInput/contract.json")).mode;
            Assert.That(mode,Is.EqualTo("DISCOVERY_ONLY").Or.EqualTo("STRICT_BINDING"));
            string type=mode=="DISCOVERY_ONLY"?"JourneyCandidateArtDiscovery":"JourneyCandidateArtCapture";
            string method=mode=="DISCOVERY_ONLY"?"Discover":"ImportAndCapture";
            Type.GetType("DesertRV.Editor."+type+", Assembly-CSharp-Editor",true).GetMethod(method).Invoke(null,null);
            RequireArmoredCapsuleContract();
        }
    }
}
